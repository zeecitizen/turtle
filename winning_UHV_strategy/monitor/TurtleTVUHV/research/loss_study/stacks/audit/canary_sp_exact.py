"""canary_sp_exact.py - the spread field sp (InpUhvMaxTrigSpread) vs ask - bid at the EXACT crossing tick (not a timestamp lookup, which hits
the first of several ticks sharing one millisecond)."""
import json
from _common import *          # noqa: F401,F403
import numpy as np
import uhv_engine
dfile = uhv_engine.det_file(base_inputs())
_S, TK = uhv_engine._setups(dfile)
T, B, A = TK["t"], TK["bid"], TK["ask"]
clear_caches()
S = uhv_engine._instant_setups(TK, 0.0, dfile)
bad, dup = 0, 0
for s in S:
    a, b = int(np.searchsorted(T, s["bar"])), int(np.searchsorted(T, s["bar"] + 60))
    seg = B[a:b]
    hit = np.nonzero(seg > s["level"])[0] if s["side"] > 0 else np.nonzero(seg < s["level"])[0]
    jj = a + int(hit[0])
    bad += abs(s["sp"] - float(A[jj] - B[jj])) > 1e-9 or T[jj] != s["t"] or s["bv"] != jj - a + 1
    dup += int(np.searchsorted(T, s["t"]) != jj)
out = {"setups": len(S), "sp_or_t_or_bv_mismatch_at_exact_tick": int(bad), "trigger_tick_shares_its_millisecond_with_an_earlier_tick": int(dup)}
print(out)
json.dump(out, open(os.path.join(HERE, "out_sp_exact.json"), "w"), indent=1)
