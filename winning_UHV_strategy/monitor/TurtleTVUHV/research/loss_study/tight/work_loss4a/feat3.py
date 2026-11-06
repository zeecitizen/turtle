import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from feat2 import ST, qtable, SPLIT
Z = np.load(os.path.join(HERE, 'spread_m1.npz'))
med, mean, mx = Z['med'], Z['mean'], Z['mx']
def rel(N, arr=med):
    return lambda r: r['trig_spread_pips'] / max(float(np.median(arr[r['k'] - N + 1:r['k'] + 1])), 0.05)
def diff(N, arr=med):
    return lambda r: r['trig_spread_pips'] - float(np.median(arr[r['k'] - N + 1:r['k'] + 1]))
F = {'rel10': rel(10), 'rel30': rel(30), 'rel60': rel(60), 'diff30': diff(30), 'diff120': diff(120), 'med30': lambda r: float(np.median(med[r['k']-29:r['k']+1]))}
for nm, f in F.items():
    print('---', nm)
    for st in ('tight', 'secure', 'base'):
        for line in qtable(st, f):
            print(f'  {st:6s} {line}')
T = {r['id']: r for r in ST['tight']}
for tid in ('0408-075606-B', '0407-232607-B', '0408-102512-B', '0408-121316-B', '0723-001905-S', '0722-174558-S', '0722-235911-S', '0723-140845-S', '1019-171329-S', '1023-145031-B'):
    r = T[tid]
    print(tid, 'W' if r['win'] else 'L', r['trig_spread_pips'], ' '.join(f"{nm}={f(r):.3f}" for nm, f in F.items()))
