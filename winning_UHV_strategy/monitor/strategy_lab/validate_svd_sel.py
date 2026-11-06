"""Validate chosen optuna_svd trials on Jul-Oct and the full year.   py validate_svd_sel.py <rig> <trial> ..."""
import json, sys
import optuna, axi_rig
import optuna_svd as O
axi_rig.use(sys.argv[1])
st = optuna.load_study(study_name=O.STUDY, storage=O.STORAGE)
by = {t.number: t for t in st.trials}
for n in map(int, sys.argv[2:]):
    t = by[n]; out = {}
    for nm, per in (("holdout", O.HOLD), ("full", O.FULL)):
        r = O.backtest(t.params, *per, tag="optsvdv_")
        out[nm] = (float(r.get("net", 0) or 0), O.dd_usd(r))
    rec = {"trial": n, "period": "validate", "params": t.params, "tune_net": t.user_attrs.get("net"), "tune_dd": t.user_attrs.get("dd"),
           "hold_net": out["holdout"][0], "hold_dd": out["holdout"][1], "full_net": out["full"][0], "full_dd": out["full"][1]}
    with O.LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    print(f"t{n}: Jan-Jun {rec['tune_net']:,.0f} DD {rec['tune_dd']:,.0f} | Jul-Oct {rec['hold_net']:,.0f} DD {rec['hold_dd']:,.0f} | full {rec['full_net']:,.0f} DD {rec['full_dd']:,.0f}", flush=True)
