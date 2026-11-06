"""Optuna (TPE Bayesian optimisation) over Saad_strategy_15min, every trial a real MT5 Strategy Tester run
(Zee 2026-10-13, "Optuna Bayesian Optimization pipeline").

Our version of the pasted pipeline:
  * runs on the portable test rigs (axi_rig), never the live terminal; one worker per rig, shared study (sqlite)
  * XAUUSD_TK real ticks + $4/lot, 1 lot, $25k, 200 ms delay; metrics parsed from MT5's own report
    (no OnTester() edit to the live EA needed)
  * search: the pasted six (EMA fast/slow, chop ER, ATR trail, pin wick/body) + the four v1.13/v1.14 tuned ones
  * fitness = the pasted one: net x win rate, minus 3 x max drawdown when the drawdown is above $2,500
  * trial 0 = v1.17's own settings, so the optimiser knows the bar to beat
  * tunes on Jan 6 - Jun 30 ONLY; `--validate` re-runs the best trials on Jul 1 - Oct 8 (never seen by Optuna)
usage:
    py optuna_mt5.py --rig axi  --trials 40          (worker 1)
    py optuna_mt5.py --rig axi2 --trials 40          (worker 2, same study)
    py optuna_mt5.py --rig axi --validate 6          (MT5 holdout of the top 6 + v1.17)"""
import argparse, json, re, sys, time
from pathlib import Path
import optuna
import axi_rig

HERE = Path(__file__).parent
STORAGE = f"sqlite:///{(HERE / 'optuna_saad.db').as_posix()}"
STUDY = "saad15_v117_janjun"
LOG = HERE / "zee_optuna.jsonl"
EA, SYM = "Saad_strategy_15min", "XAUUSD_TK"
TUNE = ("2026.01.06", "2026.07.01")
HOLD = ("2026.07.01", "2026.10.08")
FIXED = {"InpLots": "1", "InpPartialPct": "0.5", "InpTp1Be": "true"}
V117 = {"ema_fast": 9, "ema_slow": 50, "chop_er": 0.11, "trail_atr": 2.0, "wick_min": 0.45, "body_max": 0.60,
        "sl_pips": 35, "maru_body": 0.53, "min_range_atr": 0.55, "ham_ratio": 2.5}
MAP = {"ema_fast": "InpEmaFast", "ema_slow": "InpEmaSlow", "chop_er": "InpChopEr", "trail_atr": "InpTrailAtr",
       "wick_min": "InpWickMin", "body_max": "InpBodyMax", "sl_pips": "InpSlPips", "maru_body": "InpMaruBody",
       "min_range_atr": "InpMinRangeAtr", "ham_ratio": "InpHamRatio"}


def dd_usd(r):
    m = re.match(r"([\d\s]+\.\d+)", str(r.get("dd", "")))
    return float(m.group(1).replace(" ", "")) if m else 0.0


def backtest(params, frm, to):
    sets = dict(FIXED); sets.update({MAP[k]: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in params.items()})
    for attempt in range(3):                      # the rig occasionally returns an empty report on a first run
        try:
            r = axi_rig.run(EA, SYM, "M15", sets, frm=frm, to=to, tag="optuna_" + axi_rig.RIG.name,
                            timeout=900, exec_mode=200, deposit=25000, leverage="1:1000")
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    return r, sets


def fitness(r):
    net, wr, dd = float(r.get("net", 0)), float(str(r.get("wr", "0")).rstrip("%")) / 100, dd_usd(r)
    f = net * wr
    if dd > 2500: f -= 3 * dd
    return f, net, wr, dd


def objective(trial):
    p = {"ema_fast": trial.suggest_int("ema_fast", 5, 15),
         "ema_slow": trial.suggest_int("ema_slow", 30, 80),
         "chop_er": trial.suggest_float("chop_er", 0.05, 0.25, step=0.01),
         "trail_atr": trial.suggest_float("trail_atr", 1.0, 4.0, step=0.1),
         "wick_min": trial.suggest_float("wick_min", 0.30, 0.60, step=0.05),
         "body_max": trial.suggest_float("body_max", 0.20, 0.60, step=0.05),
         "sl_pips": trial.suggest_int("sl_pips", 20, 50, step=5),
         "maru_body": trial.suggest_float("maru_body", 0.40, 0.70, step=0.01),
         "min_range_atr": trial.suggest_float("min_range_atr", 0.30, 0.80, step=0.05),
         "ham_ratio": trial.suggest_float("ham_ratio", 1.5, 3.5, step=0.25)}
    r, sets = backtest(p, *TUNE)
    ts = r.get("trade_stats", {})
    rec = {"trial": trial.number, "period": "tune", "params": p, "net": r.get("net"), "wr": r.get("wr"), "dd": r.get("dd"),
           "trades": ts.get("n"), "worst_day": r.get("day_stats", {}).get("worst"), "error": r.get("error"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    if not ts.get("n") or ts["n"] < 50:
        raise optuna.TrialPruned()
    f, net, wr, dd = fitness(r)
    for k, v in (("net", net), ("wr", wr), ("dd", dd), ("trades", ts["n"]), ("worst_day", rec["worst_day"])):
        trial.set_user_attr(k, v)
    print(f"[trial {trial.number:3d} {axi_rig.RIG.name}] fitness {f:>10,.0f} | net {net:>9,.0f} WR {wr:.1%} DD {dd:,.0f} "
          f"trades {ts['n']} | {p}", flush=True)
    return f


def validate(study, top):
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    best = sorted(done, key=lambda t: -t.value)[:top]
    base = next((t for t in done if all(abs(t.params[k] - v) < 1e-9 for k, v in V117.items())), None)
    rows = ([("v1.17", V117, base)] if True else []) + [(f"trial {t.number}", t.params, t) for t in best if t is not base]
    print(f"\n[+] MT5 holdout {HOLD[0]} - {HOLD[1]} (never seen by Optuna)")
    for name, p, t in rows:
        r, _ = backtest(p, *HOLD)
        f, net, wr, dd = fitness(r)
        rec = {"trial": t.number if t else None, "period": "holdout", "name": name, "params": p, "net": net, "wr": r.get("wr"),
               "dd": r.get("dd"), "trades": r.get("trade_stats", {}).get("n"), "worst_day": r.get("day_stats", {}).get("worst"),
               "tune_net": t.user_attrs.get("net") if t else None, "tune_fitness": t.value if t else None}
        with LOG.open("a") as fh: fh.write(json.dumps(rec) + "\n")
        print(f"  {name:10s} tune net {rec['tune_net'] or 0:>9,.0f} (fitness {rec['tune_fitness'] or 0:>9,.0f}) | "
              f"HOLDOUT net {net:>9,.0f} WR {wr:.1%} DD {dd:,.0f} worst day {rec['worst_day']} trades {rec['trades']}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="axi"); ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--validate", type=int, default=0); ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    axi_rig.use(a.rig)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(study_name=STUDY, storage=STORAGE, direction="maximize", load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=a.seed, n_startup_trials=10, multivariate=True, constant_liar=True))
    if a.validate:
        validate(study, a.validate); sys.exit()
    if a.rig == "axi" and not any(all(abs(t.params.get(k, -1) - v) < 1e-9 for k, v in V117.items()) for t in study.trials):
        study.enqueue_trial(V117)                 # trial 0: v1.17 itself
    study.optimize(objective, n_trials=a.trials)
    b = study.best_trial
    print(f"\n[=== {a.rig} done ===] best so far: trial {b.number} fitness {b.value:,.0f} net {b.user_attrs.get('net'):,.0f} {b.params}")
