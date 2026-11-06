"""chartfeat.py - extra features for the chart-derived ideas (ANALYSIS ONLY): tested S/R at the fill, impulse bar against,
fresh camel flip after a long opposite run. Adds columns to feat.pkl."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api
A = api.A; P = api.PIP
o, h, l, c, v, atr = A.o, A.h, A.l, A.c, A.v, A.atr
df = pd.read_pickle(os.path.join(HERE, 'feat.pkl'))
byid = {t['id']: t for t in api.TRADES}
cols = {k: [] for k in ('sr_d2', 'sr_n05', 'sr_n10', 'imp_bar', 'imp_ctr', 'opp_run', 'flip_after', 'run_age', 'hh_ll')}
for tid in df.id:
    t = byid[tid]; k, ku, s = t['k'], t['ku'], t['side']; a = atr[k]; f = t['fill']
    hs, ls = A.pivots(k, p=2, look=180)
    piv = [p for b, p in (ls if s < 0 else hs) if b < ku - 1]          # older swing lows (sell) / highs (buy)
    # distance from fill to nearest older swing point on the target side (sells: lows at or below fill+..)
    d = [abs(f - p) / P for p in piv]
    cols['sr_d2'].append(min(d) if d else 99)
    cols['sr_n05'].append(sum(1 for x in d if x <= 0.5))
    cols['sr_n10'].append(sum(1 for x in d if x <= 1.0))
    # impulse bar against the trade among the last 3 closed bars (incl. UHV): range >= x ATR and body against
    best = 0.0
    for j in range(k - 2, k + 1):
        body = (c[j] - o[j]) * (-s)
        if body > 0:
            best = max(best, (h[j] - l[j]) / a)
    cols['imp_bar'].append(best)
    cols['imp_ctr'].append(max((c[j] - o[j]) * (-s) for j in range(k - 2, k + 1)) / a)
    # camel: how many opposite humps in a row right before the current same-side run
    Hk = A.humps_known(k)
    tr = Hk[:, 6][::-1] if len(Hk) else np.array([])
    i = 0
    while i < len(tr) and tr[i] == s: i += 1
    run = i; j = i
    while j < len(tr) and tr[j] == -s: j += 1
    cols['opp_run'].append(j - i)
    cols['flip_after'].append(int(run == 1 and (j - i) >= 3))
    cols['run_age'].append(k - int(Hk[-run, 0]) if run and len(Hk) >= run else 0)
    # swing structure p=2: last two highs and lows both against the trade
    if len(hs) >= 2 and len(ls) >= 2:
        if s > 0: cols['hh_ll'].append(int(hs[-1][1] < hs[-2][1] and ls[-1][1] < ls[-2][1]))
        else: cols['hh_ll'].append(int(hs[-1][1] > hs[-2][1] and ls[-1][1] > ls[-2][1]))
    else:
        cols['hh_ll'].append(0)
for k_, vv in cols.items(): df[k_] = vv
df.to_pickle(os.path.join(HERE, 'feat.pkl'))
base = df.groupby('half')['loss'].mean()
def show(name, m):
    r = []
    for hf in ('train', 'test'):
        mm = m & (df.half == hf); r.append(f"{hf} {int(df.loss[mm].sum())}L/{int(mm.sum())} lift {df.loss[mm].mean() / base[hf]:.2f}")
    print(f"{name:40s} n={int(m.sum()):5d} L={int(df.loss[m].sum()):3d} | " + ' | '.join(r))
show('sr_d2 <= 0.3 (fill at an older swing)', df.sr_d2 <= 0.3)
show('sr_d2 <= 0.5', df.sr_d2 <= 0.5)
show('sr_n10 >= 2 (2+ older swings within 1p)', df.sr_n10 >= 2)
show('sr_n10 >= 3', df.sr_n10 >= 3)
show('sr_n05 >= 2', df.sr_n05 >= 2)
show('imp_bar >= 2.5', df.imp_bar >= 2.5)
show('imp_bar >= 3.5', df.imp_bar >= 3.5)
show('imp_ctr >= 1.5', df.imp_ctr >= 1.5)
show('imp_ctr >= 2.5', df.imp_ctr >= 2.5)
show('flip_after (1st hump after 3+ opp)', df.flip_after == 1)
show('opp_run >= 5 & camStk==1', (df.opp_run >= 5) & (df.camStk == 1))
show('hh_ll structure against', df.hh_ll == 1)
show('camStk >= 6', df.camStk >= 6)
show('tr60 <= -8 (60-bar move against)', df.tr60 <= -8)
show('tr120 <= -12', df.tr120 <= -12)
show('ema120 <= -6', df.ema120 <= -6)
show('room60 <= 0.5 (fill within .5p of 60-bar extreme)', (df.room60 <= 0.5))
show('back60 >= 20 & room60<=1 (extended + at extreme)', (df.back60 >= 20) & (df.room60 <= 1))
