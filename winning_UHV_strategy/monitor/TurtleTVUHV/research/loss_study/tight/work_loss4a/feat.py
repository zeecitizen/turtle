"""feature table for the loss4a study - decision-time only (bars <= k, the breakout tick)."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TIGHT = os.path.dirname(HERE)
z = np.load(os.path.join(os.path.dirname(TIGHT), 'arrays.npz'))
t, o, h, l, c, v, atr = (z[k] for k in ('t', 'o', 'h', 'l', 'c', 'v', 'atr'))
P = 1e-4
SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('tight', 'secure', 'base')}

def room(r, N, extra=0.1):
    k, s = r['k'], r['side']
    T = r['brk_bid'] + s * (r['trig_spread_pips'] + extra) * P
    if s > 0:
        ext = h[k - N + 1:k + 1].max()
    else:
        ext = l[k - N + 1:k + 1].min()
    return s * (ext - T) / P

def table(stack, f, edges):
    T = ST[stack]
    out = []
    for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
        S = [r for r in T if flt(r)]
        x = np.array([f(r) for r in S]); w = np.array([r['win'] for r in S])
        row = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (x >= a) & (x < b)
            n = int(m.sum()); L = int((~w[m]).sum())
            row.append(f"[{a:g},{b:g}) {n:4d}/{L:3d}L {100*L/max(n,1):5.2f}%")
        out.append(part + ': ' + ' | '.join(row))
    return out

if __name__ == '__main__':
    edges = [-99, -0.5, 0, 0.2, 0.4, 0.7, 1.0, 1.5, 99]
    for N in (3, 5, 8, 10, 15, 20, 30):
        print(f'--- room_{N} (pips: recent extreme minus decision-time target)')
        for st in ('tight', 'secure', 'base'):
            for line in table(st, lambda r: room(r, N), edges):
                print(f'  {st:6s} {line}')
