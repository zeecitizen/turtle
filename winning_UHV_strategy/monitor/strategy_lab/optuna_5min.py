"""Optuna search for a profitable Saad_strategy_5min (M5) variant (Zee 2026-10-13: "find a profitable variant
of this EA on 5 minute timeframe using whatever tools you have").

Every trial = a real MT5 Strategy Tester run on a portable rig: XAUUSD_TK real ticks + $4/lot, 1 lot, $25k,
200 ms delay, M5. Tunes on Jan 6 - Jun 30 ONLY; `--validate N` runs the top N on the unseen Jul 1 - Oct 8.
Fitness = net - 0.5 x max drawdown (rewards smooth equity, not one lucky month); < 150 trades = pruned.
    py optuna_5min.py --rig axi --trials 50 --seed 1        (one worker per rig, shared study)
    py optuna_5min.py --rig axi --validate 8"""
import argparse, json, re, sys
from pathlib import Path
import optuna
import axi_rig

HERE = Path(__file__).parent
STORAGE = f"sqlite:///{(HERE / 'optuna_5min.db').as_posix()}"
STUDY = "saad5_janjun"
LOG = HERE / "zee_optuna5.jsonl"
EA, SYM = "Saad_strategy_5min", "XAUUSD_TK"
TUNE, HOLD = ("2026.01.06", "2026.07.01"), ("2026.07.01", "2026.10.08")
FIXED = {"InpLots": "1", "InpTp1Be": "true"}
V100 = {"sl_pips": 20, "max_risk": 9.0, "chop_er": 0.11, "chop_look": 48, "min_range": 0.55, "wick": 0.45, "maru": 0.53,
        "ham": 2.5, "break_pips": 2, "trail_usd": 2.0, "be_pct": 0.75, "partial": 0.5, "sess_from": 0, "sess_len": 24,
        "sides": 0, "min_tp": 5}


def to_inputs(p):
    s = dict(FIXED)
    s.update({"InpSlPips": p["sl_pips"], "InpMaxRiskUsd": p["max_risk"], "InpChopEr": p["chop_er"], "InpChopErLook": p["chop_look"],
              "InpMinRangeAtr": p["min_range"], "InpWickMin": p["wick"], "InpMaruBody": p["maru"], "InpHamRatio": p["ham"],
              "InpBreakPips": p["break_pips"], "InpLongTrailUsd": p["trail_usd"], "InpShortTrailUsd": p["trail_usd"],
              "InpBeTpPct": p["be_pct"], "InpPartialPct": p["partial"], "InpSessFrom": p["sess_from"],
              "InpSessTo": min(24, p["sess_from"] + p["sess_len"]), "InpMinTpPips": p["min_tp"],
              "InpBuys": "true" if p["sides"] in (0, 1) else "false", "InpSells": "true" if p["sides"] in (0, 2) else "false"})
    return {k: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in s.items()}


def dd_usd(r):
    m = re.match(r"([\d\s]+\.\d+)", str(r.get("dd", "")))
    return float(m.group(1).replace(" ", "")) if m else 0.0


def backtest(p, frm, to):
    for _ in range(3):
        try:
            r = axi_rig.run(EA, SYM, "M5", to_inputs(p), frm=frm, to=to, tag="opt5_" + axi_rig.RIG.name, timeout=1500,
                            exec_mode=200, deposit=25000, leverage="1:1000")
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    return r


def objective(trial):
    p = {"sl_pips": trial.suggest_int("sl_pips", 10, 45, step=5),
         "max_risk": trial.suggest_float("max_risk", 5.0, 15.0, step=1.0),
         "chop_er": trial.suggest_float("chop_er", 0.05, 0.30, step=0.01),
         "chop_look": trial.suggest_int("chop_look", 16, 96, step=8),
         "min_range": trial.suggest_float("min_range", 0.30, 1.20, step=0.05),
         "wick": trial.suggest_float("wick", 0.35, 0.60, step=0.05),
         "maru": trial.suggest_float("maru", 0.45, 0.75, step=0.01),
         "ham": trial.suggest_float("ham", 2.0, 3.5, step=0.25),
         "break_pips": trial.suggest_int("break_pips", 0, 6),
         "trail_usd": trial.suggest_float("trail_usd", 1.0, 5.0, step=0.5),
         "be_pct": trial.suggest_float("be_pct", 0.5, 1.0, step=0.05),
         "partial": trial.suggest_categorical("partial", [0.0, 0.5]),
         "sess_from": trial.suggest_int("sess_from", 0, 16),
         "sess_len": trial.suggest_int("sess_len", 6, 24),
         "sides": trial.suggest_int("sides", 0, 2),
         "min_tp": trial.suggest_int("min_tp", 5, 40, step=5)}
    r = backtest(p, *TUNE)
    n = r.get("trade_stats", {}).get("n") or 0
    net, dd = float(r.get("net", 0) or 0), dd_usd(r)
    rec = {"trial": trial.number, "period": "tune", "params": p, "net": net, "dd": dd, "trades": n, "pf": r.get("pf"),
           "wr": r.get("wr"), "worst_day": r.get("day_stats", {}).get("worst"), "error": r.get("error"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    if n < 150:
        raise optuna.TrialPruned()
    for k in ("net", "dd", "pf", "worst_day"): trial.set_user_attr(k, rec[k])
    trial.set_user_attr("trades", n)
    f = net - 0.5 * dd
    print(f"[t{trial.number:3d} {axi_rig.RIG.name}] fit {f:>9,.0f} net {net:>9,.0f} DD {dd:>7,.0f} PF {r.get('pf')} trades {n} | {p}", flush=True)
    return f


def validate(study, top):
    done = sorted([t for t in study.trials if t.state.name == "COMPLETE"], key=lambda t: -t.value)[:top]
    print(f"[+] MT5 holdout {HOLD[0]} - {HOLD[1]} for the top {len(done)} (never seen by Optuna)")
    for t in done:
        r = backtest(t.params, *HOLD)
        net, dd = float(r.get("net", 0) or 0), dd_usd(r)
        rec = {"trial": t.number, "period": "holdout", "params": t.params, "net": net, "dd": dd, "pf": r.get("pf"),
               "trades": r.get("trade_stats", {}).get("n"), "worst_day": r.get("day_stats", {}).get("worst"),
               "tune_net": t.user_attrs.get("net"), "tune_dd": t.user_attrs.get("dd")}
        with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
        print(f"  trial {t.number:3d}: Jan-Jun net {t.user_attrs.get('net'):>9,.0f} | Jul-Oct net {net:>9,.0f} DD {dd:>7,.0f} PF {r.get('pf')} trades {rec['trades']}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="axi"); ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--seed", type=int, default=None); ap.add_argument("--validate", type=int, default=0)
    a = ap.parse_args()
    axi_rig.use(a.rig)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(study_name=STUDY, storage=STORAGE, direction="maximize", load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=a.seed, n_startup_trials=15, multivariate=True, constant_liar=True))
    if a.validate:
        validate(study, a.validate); sys.exit()
    if a.rig == "axi" and not study.trials:
        study.enqueue_trial(V100)
    study.optimize(objective, n_trials=a.trials)
