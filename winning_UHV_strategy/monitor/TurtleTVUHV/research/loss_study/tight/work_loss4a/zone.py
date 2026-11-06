import json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('tight', 'secure', 'base')}
def cell(S):
    L = sum(1 for r in S if not r['win']); return f"{len(S):4d}/{L:2d}L"
for st in ('secure', 'base'):
    T = ST[st]
    print('=== spread (pips) at trigger,', st)
    for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
        S = [r for r in T if flt(r)]
        row = []
        for a, b in ((0, .15), (.15, .25), (.25, .35), (.35, .45), (.45, .55), (.55, .65), (.65, .75), (.75, .95), (.95, 9)):
            Q = [r for r in S if a <= r['trig_spread_pips'] < b]
            row.append(f"[{a},{b}) {cell(Q)}")
        print(f"  {part} " + ' | '.join(row))
print()
T = ST['base']
print('=== base: ER16 band x humps (the trade colour), train | test')
for lo, hi in ((0, .15), (.15, .2), (.2, .25), (.25, .3), (.3, .35), (.35, .4), (.4, .45), (.45, .55), (.55, 1.01)):
    row = []
    for hm in ((-99, 0), (1, 1), (2, 2), (3, 3), (4, 5), (6, 99)):
        tr = [r for r in T if lo <= r['er16'] < hi and hm[0] <= r['humps'] <= hm[1] and r['t_dec'] < SPLIT]
        te = [r for r in T if lo <= r['er16'] < hi and hm[0] <= r['humps'] <= hm[1] and r['t_dec'] >= SPLIT]
        row.append(f"h{hm[0]}-{hm[1]}: {cell(tr)} | {cell(te)}")
    print(f"  ER[{lo},{hi}) " + ' || '.join(row))
