"""Zee's three edits that made the 100% setting, each judged by half on the secure and base stacks (post-hoc; loss4a). For each step the
trades it DROPS vs the ones it KEEPS: loss rate, and the hypergeometric p of the dropped part losing that many by chance."""
import json, os, sys, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE); sys.path.insert(0, HERE)
from rules import p_hyper
SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('secure', 'base')}
steps = [
    ("step 1 ErMin 0.15->0.30 (zone humps 2-5, ER 0.15-0.45)", lambda r: 2 <= r['humps'] <= 5 and 0.15 <= r['er16'] < 0.45, lambda r: r['er16'] < 0.30),
    ("step 2 HumpsMax 5->3   (zone humps 2-5, ER 0.30-0.45)", lambda r: 2 <= r['humps'] <= 5 and 0.30 <= r['er16'] < 0.45, lambda r: r['humps'] > 3),
    ("step 3 ErMax 0.45->0.35 (zone humps 2-3, ER 0.30-0.45)", lambda r: 2 <= r['humps'] <= 3 and 0.30 <= r['er16'] < 0.45, lambda r: r['er16'] >= 0.35),
    ("alt: ErMax 0.45->0.35 on the wide zone (humps 2-5, ER 0.15-0.45)", lambda r: 2 <= r['humps'] <= 5 and 0.15 <= r['er16'] < 0.45, lambda r: r['er16'] >= 0.35),
]
for nm, zone, drop in steps:
    print(nm)
    for st in ('secure', 'base'):
        cells = []
        for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
            Z = [r for r in ST[st] if zone(r) and flt(r)]
            N = len(Z); K = sum(1 for r in Z if not r['win'])
            D = [r for r in Z if drop(r)]; n = len(D); x = sum(1 for r in D if not r['win'])
            kept_n, kept_L = N - n, K - x
            cells.append(f"{part}: drops {n}/{x}L ({100 * x / max(n, 1):.2f}%) keeps {kept_n}/{kept_L}L ({100 * kept_L / max(kept_n, 1):.2f}%) p {p_hyper(N, K, n, x):.3f}")
        print(f"   {st:6s} " + ' | '.join(cells))
