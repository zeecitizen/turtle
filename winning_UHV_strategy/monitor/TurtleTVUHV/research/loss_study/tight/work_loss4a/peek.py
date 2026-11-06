import json, sys, datetime as dt
import numpy as np
sys.path.insert(0, '..')
z = np.load('../arrays.npz')
t, o, h, l, c, v, atr = (z[k] for k in ('t', 'o', 'h', 'l', 'c', 'v', 'atr'))
stk = z['camStk']
T = {r['id']: r for r in json.load(open('trades_tight.json'))}
P = 1e-4
for tid in sys.argv[1:]:
    r = T[tid]
    k, kb, ku, s = r['k'], r['kb'], r['ku'], r['side']
    print(f"== {tid} side {s} level {r['level']} extreme {r['extreme']} fill {r['fill']} win {r['win']} brk_ticks {r['brk_ticks']} sp {r['trig_spread_pips']} ku=k{ku-k:+d}")
    for i in range(k - 14, kb + 3):
        tag = 'UHV' if i == ku else ('k' if i == k else ('kb' if i == kb else ''))
        ts = dt.datetime.utcfromtimestamp(int(t[i])).strftime('%H:%M')
        col = 'G' if c[i] >= o[i] else 'R'
        print(f"  {i-k:+3d} {ts} {col} o{(o[i]-r['level'])/P:+6.1f} h{(h[i]-r['level'])/P:+6.1f} l{(l[i]-r['level'])/P:+6.1f} c{(c[i]-r['level'])/P:+6.1f} v{v[i]:5.0f} stk{stk[i]:+3.0f} {tag}")
