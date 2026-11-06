"""Robustness checks for the 5-min finalists: full Jan 6 - Oct 8, as MT5 runs. usage: py opt5_check.py RIG TRIAL EXEC [sides]"""
import sys, json, optuna
import axi_rig, optuna_5min as O
rig, trial, ex = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
optuna.logging.set_verbosity(optuna.logging.WARNING)
s = optuna.load_study(study_name=O.STUDY, storage=O.STORAGE)
p = dict(s.trials[trial].params)
if len(sys.argv) > 4: p["sides"] = int(sys.argv[4])
axi_rig.use(rig)
for _ in range(3):
    r = axi_rig.run(O.EA, O.SYM, "M5", O.to_inputs(p), frm="2026.01.06", to="2026.10.08", tag="chk5_" + rig, timeout=2000, exec_mode=ex, deposit=25000, leverage="1:1000")
    if r.get("trades", 0) > 0: break
m = r.get("months", {})
rec = {"trial": trial, "exec": ex, "sides": p["sides"], "net": r.get("net"), "pf": r.get("pf"), "dd": r.get("dd"), "trades": r.get("trade_stats", {}).get("n"),
       "worst_day": r.get("day_stats", {}).get("worst"), "janjun": round(sum(v for k, v in m.items() if k < "2026.07")), "juloct": round(sum(v for k, v in m.items() if k >= "2026.07")),
       "losing_months": [k for k, v in m.items() if v < 0], "months": m}
open("zee_opt5_check.jsonl", "a").write(json.dumps(rec) + "\n")
print(json.dumps({k: v for k, v in rec.items() if k != "months"}))
