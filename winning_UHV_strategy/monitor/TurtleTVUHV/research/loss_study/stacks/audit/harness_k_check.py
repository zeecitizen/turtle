"""harness_k_check.py - the loss-study harness (research/loss_study/build.py -> trades.json) sets kb = the FILL minute and k = kb - 1; the
engine (and so the Turtle TV settings) uses k = the minute before the BREAKOUT tick. When the 0.3 s order delay pushes the fill into the next
minute, the harness's k IS the breakout minute - a bar that contains the breakout itself and the ticks after it (a look-ahead in the research
scores of bar-based rules for those trades, not in the engine). Count them, and how many are losers."""
import json
from _common import *          # noqa: F401,F403
import numpy as np
Z = np.load(os.path.join(HERE, "calls.npz"))
C = Z["calls"]                     # side, k, px, atr_k, extreme, level, ku, ts, uhv_v, brk_ticks, brk_px
T = json.load(open(os.path.join(ROOT, "research", "loss_study", "trades.json"), encoding="utf-8"))
ts = C[:, 7]; order = np.argsort(ts); ts_s = ts[order]
n_match, n_shift, n_shift_loss, n_other, ex = 0, 0, 0, 0, []
for t in T:
    j = int(np.searchsorted(ts_s, t["t_in"] - 0.3 + 1e-6, side="right")) - 1     # the latest breakout tick at least 0.3 s before the fill
    cand = [order[x] for x in range(max(0, j - 3), j + 1) if x >= 0 and int(C[order[x], 0]) == t["side"] and abs(C[order[x], 5] - t["level"]) < 1e-9]
    if not cand:
        n_other += 1; continue
    i = cand[-1]
    n_match += 1
    ke = int(C[i, 1])
    if t["k"] != ke:
        n_shift += 1; n_shift_loss += (not t["win"])
        if len(ex) < 5:
            ex.append({"id": t["id"], "harness_k": t["k"], "engine_k": ke, "breakout_tick_s": round(C[i, 7] % 60, 3), "fill_s": round(t["t_in"] % 60, 3), "win": t["win"]})
out = {"trades": len(T), "matched_to_engine_call": n_match, "unmatched": n_other, "harness_k_differs_from_engine_k": n_shift,
       "of_which_losers": n_shift_loss, "losers_total": sum(1 for t in T if not t["win"]), "examples": ex}
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(HERE, "out_harness_k.json"), "w"), indent=1)
