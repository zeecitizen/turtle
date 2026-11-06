"""side_checks.py - NOT look-ahead, found during the audit (tick-free, the machine is short of memory):
(2) the holiday list (uhv_filters._HOLI) against trades / losses on each listed date and on holidays it leaves out (research/loss_study/
    trades.json = the base setting's trades);
(3) the filters' camel (_prep 'stk', built with uhv_diamond.CAM_PIV as imported = 1) vs the setups' camel when the scanner sets
    InpDetCamPiv != 1 (simdata/det_cache): for each waiting UHV (rough) the side IS that camel at bar k -> compare with sign(stk[k])."""
import json, glob
from _common import *          # noqa: F401,F403
import numpy as np, datetime as dt
from zoneinfo import ZoneInfo
import sim, uhv_filters
NY = ZoneInfo("America/New_York")
out = {}
T = json.load(open(os.path.join(ROOT, "research", "loss_study", "trades.json"), encoding="utf-8"))
dates = np.array([dt.datetime.fromtimestamp(x["t_in"], NY).strftime("%m-%d") for x in T])
loss = np.array([not x["win"] for x in T])
out["trades_file"] = {"trades": len(T), "losses": int(loss.sum())}
out["holiday_list_trades_losses"] = {d: [int((dates == d).sum()), int(((dates == d) & loss).sum())] for d in uhv_filters._HOLI[2026]}
missing = {"06-19 Juneteenth (US federal, NYSE shut)": "06-19", "05-14 Ascension (EU)": "05-14", "06-04 Corpus Christi (DE/AT)": "06-04",
           "10-12 Columbus Day (US bonds shut)": "10-12", "03-17 St Patrick (IE)": "03-17", "08-03 bank holiday (IE/Scotland)": "08-03",
           "11-03 US election day": "11-03"}
out["not_in_list_trades_losses"] = {k: [int((dates == d).sum()), int(((dates == d) & loss).sum())] for k, d in missing.items()}
print("listed:", out["holiday_list_trades_losses"]); print("not listed:", out["not_in_list_trades_losses"])
D = sim.data("year1")
t1 = np.asarray(D["t1"]).astype(np.int64)
clear_caches()
stk = uhv_filters._prep(D)["stk"]
res3 = {}
for f in sorted(glob.glob(os.path.join(ROOT, "simdata", "det_cache", "setups_*.json"))) + [os.path.join(ROOT, "simdata", "uhv_setups.json")]:
    J = json.load(open(f, encoding="utf-8"))
    det = J.get("det") or {"InpDetCamPiv": 1}
    piv = float(det.get("InpDetCamPiv", 1))
    if piv == 1 and not f.endswith("uhv_setups.json"):
        continue
    R = J.get("roughs") or []
    k = np.searchsorted(t1, np.array([r[0] for r in R], dtype=np.int64) - 60)
    ok = (k < len(t1)) & (t1[np.minimum(k, len(t1) - 1)] == np.array([r[0] for r in R]) - 60)
    side = np.array([r[1] for r in R])[ok]
    agree = float(np.mean(np.sign(stk[k[ok]]) == side)) if ok.any() else None
    res3[os.path.basename(f)] = {"InpDetCamPiv": piv, "roughs": int(ok.sum()), "side_equals_sign_filter_stk": None if agree is None else round(agree, 4)}
out["campiv_mismatch"] = res3
for k_, v in res3.items():
    print(k_, v)
json.dump(out, open(os.path.join(HERE, "out_side_checks.json"), "w"), indent=1, default=str)
