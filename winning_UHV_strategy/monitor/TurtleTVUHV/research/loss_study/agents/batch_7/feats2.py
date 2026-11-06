"""feats2.py - batch 7: extra liquidity / time features (NY time, tick rate, local volume, range-per-tick, gaps). Writes feats2.pkl"""
import datetime as dt
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, '../..')
import api  # noqa: E402
A = api.A; PIP = 1e-4
F = pd.read_pickle('feats.pkl'); F['loss'] = ~F.win
T = {t['id']: t for t in api.TRADES}
o, h, l, c, v = A.o, A.h, A.l, A.c, A.v


def ny_offset(ts):
    y = dt.datetime.fromtimestamp(ts, dt.timezone.utc).year
    m = dt.datetime(y, 3, 1, tzinfo=dt.timezone.utc); s = m + dt.timedelta(days=(6 - m.weekday()) % 7 + 7)
    n = dt.datetime(y, 11, 1, tzinfo=dt.timezone.utc); e = n + dt.timedelta(days=(6 - n.weekday()) % 7)
    return -4 if s.timestamp() + 7 * 3600 <= ts < e.timestamp() + 6 * 3600 else -5


rows = []
for i, r in F.iterrows():
    t = T[r.id]; k = t['k']; ts = t['t_in']
    nyd = dt.datetime.fromtimestamp(ts + ny_offset(ts) * 3600, dt.timezone.utc)
    d = {'ny_min': nyd.hour * 60 + nyd.minute + nyd.second / 60, 'ny_dow': nyd.weekday(),
         'tickrate': t['brk_ticks_so_far'] / (ts % 60 + 1), 'v5': v[k - 4:k + 1].mean(), 'vmin10': v[k - 9:k + 1].min()}
    seg = slice(k - 29, k + 1)
    d['rpt30'] = np.mean((h[seg] - l[seg]) / PIP / np.sqrt(np.maximum(v[seg], 1)))
    d['gap10'] = np.mean(np.abs(o[k - 9:k + 1] - c[k - 10:k]) / PIP)
    d['lowvbars30'] = int(np.sum(v[seg] < 15))
    d['mb60_atr'] = np.max(h[k - 59:k + 1] - l[k - 59:k + 1]) / max(A.atr[k], 1e-9)
    d['mb240p'] = np.max(h[k - 239:k + 1] - l[k - 239:k + 1]) / PIP
    d['vmax60_rel'] = np.max(v[k - 59:k + 1]) / max(np.mean(v[k - 239:k + 1]), 1)
    rows.append(d)
G = pd.DataFrame(rows, index=F.index)
F = pd.concat([F, G], axis=1)
F.to_pickle('feats2.pkl')
print(F.shape)
