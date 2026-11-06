import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feat2 import ST, SPLIT
Z = np.load(os.path.join(HERE, 'setups.npz'))
St, Ss, Sl = Z['t'], Z['side'], Z['level']
def rebreak(r, mins, pips, same=True):
    a = np.searchsorted(St, r['t_dec'] - mins * 60); b = np.searchsorted(St, r['t_dec'] - 0.5)
    m = (np.abs(Sl[a:b] - r['level']) <= pips * 1e-4 + 1e-9)
    if same: m &= Ss[a:b] == r['side']
    return bool(m.any())
for mins in (15, 30, 60, 120):
    for pips in (0.3, 0.5, 1.0):
        for same in (True, False):
            out = []
            for st in ('tight', 'secure', 'base'):
                cell = []
                for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
                    S = [r for r in ST[st] if flt(r)]
                    base = sum(1 for r in S if not r['win']) / len(S)
                    Q = [r for r in S if rebreak(r, mins, pips, same)]; L = sum(1 for r in Q if not r['win'])
                    cell.append(f"{part} {len(Q)}/{L}L x{(L/max(len(Q),1))/base:.2f}")
                out.append(f"{st} " + ' '.join(cell))
            print(f"rebreak {mins:3d}m {pips}p {'same' if same else 'any '}: " + ' | '.join(out))
T = {r['id']: r for r in ST['tight']}
for tid in ('0408-075606-B', '0407-232607-B', '0408-102512-B', '0408-121316-B', '0723-001905-S', '0722-174558-S', '0722-235911-S', '0723-140845-S'):
    print(tid, [rebreak(T[tid], 60, p) for p in (0.3, 0.5, 1.0)], [rebreak(T[tid], 30, p) for p in (0.3, 0.5, 1.0)])
