"""robustness of the spread rules across lookbacks / tolerances (loss4a). Hypothesis only."""
import io, os, sys, contextlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import api_tight
from rules import chance
M = np.load(os.path.join(HERE, 'spread_m1.npz'))['med']
def mk_wide(N, tol):
    def r(t, A):
        k = t['k']; return t['trig_spread_pips'] > float(np.median(M[k - N + 1:k + 1])) + tol
    return r
def mk_notnarrow(N, tol):
    def r(t, A):
        k = t['k']; return t['trig_spread_pips'] >= float(np.median(M[k - N + 1:k + 1])) - tol
    return r
def mk_abs_upper():
    def r(t, A):   # the half's upper mode, hard-coded per regime: 0.6 (train regime) or 0.2 (test regime) - regime picked by the 240-bar median
        k = t['k']; m = float(np.median(M[k - 239:k + 1]))
        return t['trig_spread_pips'] >= (0.55 if m >= 0.35 else 0.15)
    return r
for nm, r in [(f'wide N{N} tol{tol}', mk_wide(N, tol)) for N in (15, 30, 60, 120, 240) for tol in (0.05, 0.15)] + \
             [(f'notnarrow N{N}', mk_notnarrow(N, 0.05)) for N in (15, 30, 60, 120, 240)] + [('upper mode (regime)', mk_abs_upper())]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        api_tight.report(r, nm)
    line = buf.getvalue().strip()
    sec = line.split('| secure: ')[1].split(' | base: ')[0]; base = line.split(' | base: ')[1]; tight = line.split('tight: ')[1].split(' | zee100')[0]
    print(f"{nm:22s} tight {tight} || secure {sec} || base {base}")
    print(f"{'':22s} {chance(r)}")
