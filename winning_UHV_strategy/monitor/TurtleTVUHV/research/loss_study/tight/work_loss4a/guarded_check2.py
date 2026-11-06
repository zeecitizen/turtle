import os, sys, io, contextlib, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import api_tight, rules
from rules import p_hyper
M = np.load(os.path.join(HERE, 'spread_m1.npz'))['med']
NY = ZoneInfo('America/New_York')
def guarded(t):
    d = dt.datetime.fromtimestamp(t['t_dec'], NY); m = d.hour * 60 + d.minute
    return not (16 * 60 + 45 <= m < 17 * 60 + 45) and t['trig_spread_pips'] < 1.0 - 1e-9
api_tight.STACKS['base_g'] = [t for t in api_tight.STACKS['base'] if guarded(t)]
def upper_mode(t, A):
    k = t['k']; m = float(np.median(M[k - 239:k + 1])); return t['trig_spread_pips'] >= (0.55 if m >= 0.35 else 0.15)
for r in rules.RULES + [upper_mode]:
    res = api_tight.score(r, 'base_g'); out = []
    for part in ('train', 'test'):
        c = res[part]; N, K, n, x = c['trades'], c['losses'], c['removed'], c['losses_removed']; e = n * K / max(N, 1)
        out.append(f"{part} WR {c['wr_before']}->{c['wr_after']} {x}L/{n} (x{x / e if e else 0:.2f}, p {p_hyper(N, K, n, x):.3f})")
    print(f"{r.__name__:32s} base_guarded: " + ' | '.join(out))
