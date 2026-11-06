import json, os, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('tight', 'secure', 'base')}
for st in ('secure', 'base'):
    T = ST[st]
    print('===', st)
    for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
        S = [r for r in T if flt(r)]
        base = sum(1 for r in S if not r['win']) / len(S)
        row = []
        for hh in range(24):
            Q = [r for r in S if int(r['t_dec'] // 3600) % 24 == hh]
            L = sum(1 for r in Q if not r['win'])
            row.append(f"{hh:02d}:{len(Q)}/{L}")
        print(f"  {part} base {100*base:.2f}%  " + ' '.join(row))
