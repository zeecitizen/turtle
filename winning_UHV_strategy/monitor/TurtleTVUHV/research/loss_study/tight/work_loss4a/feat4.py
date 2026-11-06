import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feat2 import ST, SPLIT
Z = np.load(os.path.join(HERE, 'spread_m1.npz'))
med = Z['med']
def cat(r, N):
    d = r['trig_spread_pips'] - float(np.median(med[r['k'] - N + 1:r['k'] + 1]))
    return 'narrow' if d < -0.05 else ('wide' if d > 0.05 else 'usual')
for N in (5, 15, 30, 60, 120):
    print(f'--- trigger spread vs median of last {N} bars')
    for st in ('tight', 'secure', 'base'):
        out = []
        for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
            S = [r for r in ST[st] if flt(r)]
            row = []
            for cc in ('narrow', 'usual', 'wide'):
                Q = [r for r in S if cat(r, N) == cc]; L = sum(1 for r in Q if not r['win'])
                row.append(f"{cc} {len(Q)}/{L}L {100*L/max(len(Q),1):.2f}%")
            out.append(part + ': ' + ' | '.join(row))
        print(f'  {st:6s} ' + ' || '.join(out))
