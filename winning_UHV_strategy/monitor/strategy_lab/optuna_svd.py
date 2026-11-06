"""Optuna (TPE, Bayesian) tuning of saad_vsisa_diamond_hybrid (Zee 2026-10-14: "this EA with $288,367, compile it
and run ML algos on it to tune it to higher profit").

Every trial = a real MT5 Strategy Tester run (XAUUSD_TK real ticks + $4/lot, $25k, 200 ms, M5). Tunes on
Jan 6 - Jun 30 only; `--validate N` runs the top N on the unseen Jul 1 - Oct 8 and the full year.
Fitness = net - 3 x (drawdown above $13,572): more profit, but NOT by simply trading bigger than v1.00 does.
    py optuna_svd.py --rig axi --trials 40 --seed 1      (one worker per rig, shared study)
    py optuna_svd.py --rig axi --validate 8"""
import argparse, json, re, sys
from pathlib import Path
import optuna
import axi_rig

HERE = Path(__file__).parent
STORAGE = f"sqlite:///{(HERE / 'optuna_svd.db').as_posix()}"
STUDY = "svd_janjun"
LOG = HERE / "zee_optuna_svd.jsonl"
EA, SYM = "saad_vsisa_diamond_hybrid", "XAUUSD_TK"
TUNE, HOLD, FULL = ("2026.01.06", "2026.07.01"), ("2026.07.01", "2026.10.08"), ("2026.01.06", "2026.10.08")
DD_CAP = 13572.0
V100 = {"saad_gate": 3, "win": 240, "mult": 2.0, "sig_thr": 0.3, "dia": 1, "dia_gate": 2, "dia_lots": 0.02, "dia_stack": 2,
        "saad_lots": 1.0, "saad_maxrisk": 15.0, "vs_lots": 0.28, "meta_thr": 0.4, "exh_thr": 0.75, "reg_mask": 4}


def to_inputs(p):
    s = {"InpVerbose": "false", "InpHybSaadGate": p["saad_gate"], "InpHybWinMin": p["win"], "InpHybConfMult": p["mult"],
         "InpHybSigThr": p["sig_thr"], "InpHybDia": "true" if p["dia"] else "false", "InpHybDiaGate": p["dia_gate"],
         "D_InpLots": p["dia_lots"], "D_InpStackMult": p["dia_stack"], "S_InpLots": p["saad_lots"], "S_InpMaxRiskUsd": p["saad_maxrisk"],
         "InpLots": p["vs_lots"], "InpMetaThr": p["meta_thr"], "InpExhThr": p["exh_thr"], "InpRegSkipMask": p["reg_mask"]}
    return {k: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in s.items()}


def dd_usd(r):
    m = re.match(r"([\d\s]+\.\d+)", str(r.get("dd", "")))
    return float(m.group(1).replace(" ", "")) if m else 0.0


def backtest(p, frm, to, tag="optsvd_"):
    for _ in range(3):
        try:
            r = axi_rig.run(EA, SYM, "M5", to_inputs(p), frm=frm, to=to, tag=tag + axi_rig.RIG.name, timeout=1800, exec_mode=200)
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    return r


def objective(trial):
    p = {"saad_gate": trial.suggest_categorical("saad_gate", [2, 3, 4]),
         "win": trial.suggest_int("win", 30, 480, step=30),
         "mult": trial.suggest_float("mult", 1.0, 3.0, step=0.25),
         "sig_thr": trial.suggest_float("sig_thr", 0.0, 0.4, step=0.05),
         "dia": trial.suggest_int("dia", 0, 1),
         "dia_gate": trial.suggest_categorical("dia_gate", [0, 1, 2]),
         "dia_lots": trial.suggest_float("dia_lots", 0.01, 0.10, step=0.01),
         "dia_stack": trial.suggest_int("dia_stack", 1, 2),
         "saad_lots": trial.suggest_float("saad_lots", 0.5, 2.0, step=0.1),
         "saad_maxrisk": trial.suggest_float("saad_maxrisk", 9.0, 21.0, step=1.0),
         "vs_lots": trial.suggest_float("vs_lots", 0.14, 0.84, step=0.07),
         "meta_thr": trial.suggest_float("meta_thr", 0.30, 0.55, step=0.05),
         "exh_thr": trial.suggest_float("exh_thr", 0.60, 0.95, step=0.05),
         "reg_mask": trial.suggest_categorical("reg_mask", [0, 4])}
    r = backtest(p, *TUNE)
    n = r.get("trades") or 0
    net, dd = float(r.get("net", 0) or 0), dd_usd(r)
    rec = {"trial": trial.number, "period": "tune", "params": p, "net": net, "dd": dd, "trades": n, "pf": r.get("pf"),
           "wr": r.get("wr"), "error": r.get("error"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    if n < 100:
        raise optuna.TrialPruned()
    trial.set_user_attr("net", net); trial.set_user_attr("dd", dd)
    fit = net - 3.0 * max(0.0, dd - DD_CAP)
    print(f"[t{trial.number:3d} {axi_rig.RIG.name}] fit {fit:>9,.0f} net {net:>9,.0f} DD {dd:>7,.0f} | {p}", flush=True)
    return fit


def validate(study, top):
    done = sorted([t for t in study.trials if t.state.name == "COMPLETE"], key=lambda t: -t.value)[:top]
    print(f"[+] holdout Jul 1 - Oct 8 + full year for the top {len(done)} (Optuna never saw Jul-Oct)")
    for t in done:
        out = {}
        for nm, per in (("holdout", HOLD), ("full", FULL)):
            r = backtest(t.params, *per, tag="optsvdv_")
            out[nm] = (float(r.get("net", 0) or 0), dd_usd(r))
        rec = {"trial": t.number, "period": "validate", "params": t.params, "tune_net": t.user_attrs.get("net"), "tune_dd": t.user_attrs.get("dd"),
               "hold_net": out["holdout"][0], "hold_dd": out["holdout"][1], "full_net": out["full"][0], "full_dd": out["full"][1]}
        with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
        print(f"  t{t.number:3d}: Jan-Jun {rec['tune_net']:>9,.0f} DD {rec['tune_dd']:>7,.0f} | Jul-Oct {rec['hold_net']:>9,.0f} DD {rec['hold_dd']:>7,.0f}"
              f" | full {rec['full_net']:>9,.0f} DD {rec['full_dd']:>7,.0f} | {t.params}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="axi"); ap.add_argument("--trials", type=int, default=40)
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
