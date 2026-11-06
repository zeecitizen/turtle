"""Optuna (TPE) search for a TRUE 1-minute Trinity (Zee 2026-10-14: "develop an EA that works successfully on 1 min
scale and with 0.01 lots ... daily profit of $10+ ... try in a loop until you reach this goal").

Saad and VSISA engines on 1-MINUTE candles (S_InpTF = V_InpTF = 1), Diamond on M1 behind its 94% filter
(chop >= 0.45), all at 0.01 lots, $500 account, XAUUSD_TK real ticks + $4/lot, 200 ms. Every trial = a real MT5
run on Jan 6 - Jun 30; `--validate N` runs the top N on the unseen Jul 1 - Oct 8.
Fitness = net per weekday ($/day) - penalty when the drawdown passes $150 (30% of the account).
    py optuna_tri1m.py --rig axi --trials 50 --seed 1
    py optuna_tri1m.py --rig axi --validate 6"""
import argparse, json, re, sys
from pathlib import Path
import optuna
import axi_rig

HERE = Path(__file__).parent
STORAGE = f"sqlite:///{(HERE / 'optuna_tri1m.db').as_posix()}"
STUDY = "tri1m_janjun"
LOG = HERE / "zee_optuna_tri1m.jsonl"
EA, SYM = "Trinity_1min", "XAUUSD_TK"
TUNE, HOLD = ("2026.01.06", "2026.07.01"), ("2026.07.01", "2026.10.08")
DAYS = {"tune": 125, "hold": 71}           # weekdays in each period (fixed denominator: idle days count)
DD_CAP = 150.0
FIXED = {"S_InpTF": 1, "V_InpTF": 1, "D_InpTF": 1, "S_InpLots": 0.01, "V_InpLots": 0.01, "D_InpLots": 0.01, "D_InpStackMult": 1,
         "V_InpVerbose": "false", "V_InpMetaMode": 0, "V_InpRegimeMode": 0, "V_InpExhMode": 0, "InpDiaLog": "false", "InpDiaMinER": 0.45}


def to_inputs(p):
    s = dict(FIXED)
    s.update({"InpUseSaad": "true" if p["saad"] else "false", "InpUseVsisa": "true" if p["vsisa"] else "false",
              "InpUseDia": "true" if p["dia"] else "false",
              "S_InpEmaFast": p["ema_f"], "S_InpEmaSlow": p["ema_s"], "S_InpMinRangeAtr": p["min_rng"], "S_InpBreakPips": p["brk"],
              "S_InpSlPips": p["sl"], "S_InpMaxRiskUsd": p["maxrisk"], "S_InpMinTpPips": p["min_tp"],
              "S_InpLongTrailUsd": p["trail"], "S_InpShortTrailUsd": p["trail"], "S_InpBeTpPct": p["be"],
              "S_InpChopEr": p["chop"], "S_InpChopErLook": p["chop_n"], "S_InpHtfMin": p["htf"], "S_InpTrailAtr": p["tatr"],
              "S_InpSwingLook": p["swing"], "S_InpSessFrom": p["sess_from"], "S_InpSessTo": min(24, p["sess_from"] + p["sess_len"]),
              "S_InpTrendAlign": "true" if p["align"] else "false", "S_InpBreakBars": p["brk_bars"], "S_InpMaxBars": p["max_bars"],
              "V_InpSlBufPts": p["v_slbuf"], "V_InpMinSlPts": p["v_minsl"], "V_InpMaxSlPts": p["v_maxsl"], "V_InpBigPct": p["v_big"],
              "V_InpLowVolPct": p["v_low"], "V_InpRatchetStart": p["v_rs"], "V_InpTrendTF": p["v_ttf"]})
    return {k: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in s.items()}


def dd_usd(r):
    m = re.match(r"([\d\s]+\.\d+)", str(r.get("dd", "")))
    return float(m.group(1).replace(" ", "")) if m else 0.0


def backtest(p, frm, to, tag="opt1m_"):
    for _ in range(3):
        try:
            r = axi_rig.run(EA, SYM, "M1", to_inputs(p), frm=frm, to=to, tag=tag + axi_rig.RIG.name, timeout=1800, exec_mode=200, deposit=500)
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    return r


def space(trial):
    return {"saad": trial.suggest_int("saad", 0, 1), "vsisa": trial.suggest_int("vsisa", 0, 1), "dia": trial.suggest_int("dia", 0, 1),
            "ema_f": trial.suggest_int("ema_f", 5, 30), "ema_s": trial.suggest_int("ema_s", 30, 200, step=10),
            "min_rng": trial.suggest_float("min_rng", 0.3, 2.0, step=0.1), "brk": trial.suggest_float("brk", 0.0, 6.0, step=0.5),
            "sl": trial.suggest_float("sl", 2.0, 40.0, step=2.0), "maxrisk": trial.suggest_float("maxrisk", 1.5, 12.0, step=0.5),
            "min_tp": trial.suggest_float("min_tp", 2.0, 40.0, step=2.0), "trail": trial.suggest_float("trail", 0.3, 4.0, step=0.1),
            "be": trial.suggest_float("be", 0.0, 1.0, step=0.25), "chop": trial.suggest_float("chop", 0.0, 0.5, step=0.05),
            "chop_n": trial.suggest_int("chop_n", 8, 60, step=4), "htf": trial.suggest_categorical("htf", [0, 5, 15, 60, 240]),
            "tatr": trial.suggest_float("tatr", 1.0, 5.0, step=0.5), "swing": trial.suggest_int("swing", 50, 600, step=50),
            "sess_from": trial.suggest_int("sess_from", 0, 16), "sess_len": trial.suggest_int("sess_len", 4, 24),
            "align": trial.suggest_int("align", 0, 1), "brk_bars": trial.suggest_int("brk_bars", 1, 4),
            "max_bars": trial.suggest_categorical("max_bars", [0, 15, 30, 60, 120, 240]),
            "v_slbuf": trial.suggest_int("v_slbuf", 20, 240, step=20), "v_minsl": trial.suggest_int("v_minsl", 20, 150, step=10),
            "v_maxsl": trial.suggest_int("v_maxsl", 150, 900, step=50), "v_big": trial.suggest_float("v_big", 0.5, 0.95, step=0.05),
            "v_low": trial.suggest_float("v_low", 0.5, 1.3, step=0.05), "v_rs": trial.suggest_categorical("v_rs", [0.0, 1.0, 1.5, 2.0, 3.0]),
            "v_ttf": trial.suggest_categorical("v_ttf", [0, 5, 15, 30, 60])}


def objective(trial):
    p = space(trial)
    if not (p["saad"] or p["vsisa"] or p["dia"]):
        raise optuna.TrialPruned()
    r = backtest(p, *TUNE)
    net, dd, n = float(r.get("net", 0) or 0), dd_usd(r), r.get("trades") or 0
    rec = {"trial": trial.number, "period": "tune", "params": p, "net": net, "dd": dd, "trades": n, "per_day": net / DAYS["tune"],
           "engines": None, "error": r.get("error"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    if n < 60:
        raise optuna.TrialPruned()
    trial.set_user_attr("net", net); trial.set_user_attr("dd", dd)
    fit = net / DAYS["tune"] - 0.1 * max(0.0, dd - DD_CAP)
    print(f"[t{trial.number:3d} {axi_rig.RIG.name}] fit {fit:7.2f} $/day {net / DAYS['tune']:6.2f} net {net:8.2f} DD {dd:7.2f} trades {n}", flush=True)
    return fit


def validate(study, top):
    done = sorted([t for t in study.trials if t.state.name == "COMPLETE"], key=lambda t: -t.value)[:top]
    for t in done:
        r = backtest(t.params, *HOLD, tag="opt1mv_")
        net, dd = float(r.get("net", 0) or 0), dd_usd(r)
        rec = {"trial": t.number, "period": "holdout", "params": t.params, "net": net, "dd": dd, "per_day": net / DAYS["hold"],
               "tune_net": t.user_attrs.get("net"), "tune_dd": t.user_attrs.get("dd"), "trades": r.get("trades")}
        with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
        print(f"  t{t.number:3d}: Jan-Jun $/day {t.user_attrs.get('net') / DAYS['tune']:6.2f} DD {t.user_attrs.get('dd'):6.0f} | "
              f"Jul-Oct $/day {net / DAYS['hold']:6.2f} DD {dd:6.0f} trades {rec['trades']}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="axi"); ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--seed", type=int, default=None); ap.add_argument("--validate", type=int, default=0)
    a = ap.parse_args()
    axi_rig.use(a.rig)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(study_name=STUDY, storage=STORAGE, direction="maximize", load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=a.seed, n_startup_trials=20, multivariate=True, constant_liar=True))
    if a.validate:
        validate(study, a.validate); sys.exit()
    study.optimize(objective, n_trials=a.trials)
