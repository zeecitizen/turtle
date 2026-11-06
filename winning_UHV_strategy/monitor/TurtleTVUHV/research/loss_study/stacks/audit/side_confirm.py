"""side_confirm.py - not look-ahead: with InpDetCamConfirm > 1 (camel pivot size 1) the setups' side is the CONFIRMED camel, while the filters'
stk is the raw hump count: agreement of side with sign(stk[k]) for the cached setups (simdata/det_cache)."""
import json, glob
from _common import *          # noqa: F401,F403
import numpy as np
import sim, uhv_filters
D = sim.data("year1"); t1 = np.asarray(D["t1"]).astype(np.int64)
clear_caches(); stk = uhv_filters._prep(D)["stk"]
out = {}
for f in sorted(glob.glob(os.path.join(ROOT, "simdata", "det_cache", "setups_1_[23]_*.json"))):
    J = json.load(open(f, encoding="utf-8")); R = J.get("roughs") or []
    tt = np.array([r[0] for r in R], dtype=np.int64) - 60
    k = np.searchsorted(t1, tt); ok = (k < len(t1)) & (t1[np.minimum(k, len(t1) - 1)] == tt)
    side = np.array([r[1] for r in R])[ok]; s = stk[k[ok]]
    out[os.path.basename(f)] = {"InpDetCamConfirm": J.get("det", {}).get("InpDetCamConfirm"), "roughs": int(ok.sum()),
                                "side_equals_sign_stk": round(float(np.mean(np.sign(s) == side)), 4),
                                "stk_opposite_to_side": round(float(np.mean(np.sign(s) == -side)), 4)}
print(out)
json.dump(out, open(os.path.join(HERE, "out_side_confirm.json"), "w"), indent=1)
