"""Optuna search over VSISA (M5) - adapted from optuna_5min.py (Zee 2026-10-14: "optimize the VSISA EA that runs on 5 minutes timeframe to maximize profits").
(was: Optuna search for a profitable Saad_strategy_5min (M5) variant (Zee 2026-10-13: "find a profitable variant
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
STORAGE = f"sqlite:///{(HERE / 'optuna_vsisa.db').as_posix()}"
STUDY = "vsisa_janjun"
LOG = HERE / "zee_optuna_vsisa.jsonl"
EA, SYM = "VSISA", "XAUUSD_TK"
TUNE, HOLD = ("2026.01.06", "2026.07.01"), ("2026.07.01", "2026.10.08")
FIXED = {"InpLots": "0.28", "InpVerbose": "false"}
V128 = {"big_pct": 0.70, "big_avg": 1.10, "low_vol": 1.00, "body": 0.35, "sl_buf": 120, "min_sl": 60, "max_sl": 900, "target_r": 10.0,
        "tgt_min_r": 0.5, "be_r": 0.0, "ratchet_start": 2.0, "ratchet_step": 8.0, "fake": 1, "sweep_look": 30, "fade": 1, "fade_pct": 0.65,
        "trend_tf": 30, "trend_mode": 1, "sess_from": 0, "sess_len": 24, "max_open": 2, "setup_max": 10, "strict": 1, "confirm": 0}


def to_inputs(p):
    s = dict(FIXED)
    s.update({"InpBigPct": p["big_pct"], "InpBigAvg": p["big_avg"], "InpLowVolPct": p["low_vol"], "InpBodyFrac": p["body"],
              "InpSlBufPts": p["sl_buf"], "InpMinSlPts": p["min_sl"], "InpMaxSlPts": p["max_sl"], "InpTargetR": p["target_r"],
              "InpTgtMinR": p["tgt_min_r"], "InpBreakEvenR": p["be_r"], "InpRatchetStart": p["ratchet_start"], "InpRatchetStep": p["ratchet_step"],
              "InpFakeBreak": "true" if p["fake"] else "false", "InpSweepLook": p["sweep_look"], "InpFadeMode": p["fade"], "InpFadePct": p["fade_pct"],
              "InpTrendTF": p["trend_tf"], "InpTrendMode": p["trend_mode"], "InpSessFrom": p["sess_from"], "InpSessTo": min(24, p["sess_from"] + p["sess_len"]),
              "InpMaxOpen": p["max_open"], "InpSetupMax": p["setup_max"], "InpStrictDir": "true" if p["strict"] else "false", "InpConfirmMode": p["confirm"]})
    return {k: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in s.items()}


def dd_usd(r):
    m = re.match(r"([\d\s]+\.\d+)", str(r.get("dd", "")))
    return float(m.group(1).replace(" ", "")) if m else 0.0


def backtest(p, frm, to):
    for _ in range(3):
        try:
            r = axi_rig.run(EA, SYM, "M5", to_inputs(p), frm=frm, to=to, tag="optvs_" + axi_rig.RIG.name, timeout=1500,
                            exec_mode=200, deposit=25000, leverage="1:1000")
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    return r


def objective(trial):
    p = {"big_pct": trial.suggest_float("big_pct", 0.50, 0.95, step=0.05),
         "big_avg": trial.suggest_float("big_avg", 0.90, 1.80, step=0.05),
         "low_vol": trial.suggest_float("low_vol", 0.50, 1.30, step=0.05),
         "body": trial.suggest_float("body", 0.15, 0.65, step=0.05),
         "sl_buf": trial.suggest_int("sl_buf", 40, 240, step=20),
         "min_sl": trial.suggest_int("min_sl", 30, 150, step=10),
         "max_sl": trial.suggest_int("max_sl", 400, 1600, step=100),
         "target_r": trial.suggest_float("target_r", 2.0, 15.0, step=0.5),
         "tgt_min_r": trial.suggest_float("tgt_min_r", 0.3, 2.0, step=0.1),
         "be_r": trial.suggest_categorical("be_r", [0.0, 0.5, 0.75, 1.0, 1.5, 2.0]),
         "ratchet_start": trial.suggest_categorical("ratchet_start", [0.0, 1.0, 1.5, 2.0, 3.0, 4.0]),
         "ratchet_step": trial.suggest_float("ratchet_step", 1.0, 10.0, step=0.5),
         "fake": trial.suggest_int("fake", 0, 1),
         "sweep_look": trial.suggest_int("sweep_look", 10, 80, step=5),
         "fade": trial.suggest_int("fade", 0, 1),
         "fade_pct": trial.suggest_float("fade_pct", 0.40, 0.90, step=0.05),
         "trend_tf": trial.suggest_categorical("trend_tf", [0, 15, 30, 60, 240]),
         "trend_mode": trial.suggest_int("trend_mode", 0, 1),
         "sess_from": trial.suggest_int("sess_from", 0, 14),
         "sess_len": trial.suggest_int("sess_len", 8, 24),
         "max_open": trial.suggest_int("max_open", 1, 3),
         "setup_max": trial.suggest_int("setup_max", 4, 16),
         "strict": trial.suggest_int("strict", 0, 1),
         "confirm": trial.suggest_int("confirm", 0, 2)}
    r = backtest(p, *TUNE)
    n = r.get("trade_stats", {}).get("n") or 0
    net, dd = float(r.get("net", 0) or 0), dd_usd(r)
    rec = {"trial": trial.number, "period": "tune", "params": p, "net": net, "dd": dd, "trades": n, "pf": r.get("pf"),
           "wr": r.get("wr"), "worst_day": r.get("day_stats", {}).get("worst"), "error": r.get("error"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    if n < 40:
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
        study.enqueue_trial(V128)
    study.optimize(objective, n_trials=a.trials)
