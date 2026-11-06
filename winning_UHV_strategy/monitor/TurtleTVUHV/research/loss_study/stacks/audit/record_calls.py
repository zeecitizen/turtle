"""record_calls.py - look-ahead audit, step 1: run the real engine once on the 97.7% base setting and record the EXACT arguments the engine
passes to uhv_filters.skip() and uhv_filters.secure() for every setup (the recorder returns 'no skip', so every setup reaches the call).
Output: calls.npz (one row per call) + setups_fields.json (the instant setups' own fields). Read-only use of engine/filter code."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np
import uhv_engine, uhv_filters

BASE = json.load(open(os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json"), encoding="utf-8"))["inputs"]
rec_skip, rec_sec = [], []
_real_skip, _real_sec = uhv_filters.skip, uhv_filters.secure

def rec(fv, inp, D, side, k, px, atr_k, extreme, level=None, ku=None, ts=None, uhv_v=None, brk_ticks=None, brk_px=None):
    rec_skip.append((side, k, px, atr_k, extreme, -1 if level is None else level, -1 if ku is None else ku, -1 if ts is None else ts,
                     -1 if uhv_v is None else uhv_v, -1 if brk_ticks is None else brk_ticks, -1 if brk_px is None else brk_px))
    return None

def rec2(fv, inp, D, side, k):
    rec_sec.append((side, k)); return False

uhv_filters.skip, uhv_filters.secure = rec, rec2
try:
    inp = dict(BASE)
    inp["InpUhvMinAtrPips"] = "1e-12"        # switches lf_on on; the recorder never skips, so every setup reaches the call
    inp["InpUhvRiskMgr"] = "1"              # so secure() is called too (the recorder returns False = 'not secure' -> skip() is then called)
    t0 = time.time()
    rows, su, cnt = uhv_engine.simulate(inp)
    print("simulate with recorder: %.1fs, setups %d, skip calls %d, secure calls %d, trades %d" % (time.time() - t0, cnt["setups"], len(rec_skip), len(rec_sec), int((rows[:, 10] == 0).sum())))
finally:
    uhv_filters.skip, uhv_filters.secure = _real_skip, _real_sec

A = np.array(rec_skip, dtype=np.float64)
np.savez(os.path.join(HERE, "calls.npz"), calls=A, sec=np.array(rec_sec, dtype=np.int64),
         cols=np.array(["side", "k", "px", "atr_k", "extreme", "level", "ku", "ts", "uhv_v", "brk_ticks", "brk_px"]))
# sanity: the base run (no recorder, no filters) must give the documented 7,631 trades / 172 losses
rows0, _, cnt0 = uhv_engine.simulate(dict(BASE))
real = rows0[rows0[:, 10] == 0]
print("base run: trades %d, losses %d, WR %.2f%%, net $%.0f" % (len(real), int((real[:, 6] < 0).sum()), 100 * (real[:, 6] > 0).mean(), real[:, 6].sum()))
