"""per-minute spread stats from the PrimeXBT ticks, aligned with arrays.npz bars (loss4a). Bar i covers [t[i], t[i]+60)."""
import json, os, sys
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, ROOT)
import numpy as np
import uhv_engine as U
inp = json.load(open(os.path.join(ROOT, 'settings', 'saved', '2026-11-06 09-00-00.json'), encoding='utf-8'))['inputs']
S, TK = U._setups(U.det_file(inp))
T, B, AS = np.asarray(TK['t']), np.asarray(TK['bid']), np.asarray(TK['ask'])
z = np.load(os.path.join(ROOT, 'research', 'loss_study', 'arrays.npz'))
t1 = z['t'].astype(np.int64)
sp = (AS - B) / 1e-4
idx = np.searchsorted(T, t1)
idx = np.append(idx, len(T))
med = np.full(len(t1), np.nan); mean = np.full(len(t1), np.nan); mx = np.full(len(t1), np.nan); last = np.full(len(t1), np.nan)
for i in range(len(t1)):
    a, b = idx[i], idx[i + 1]
    if b > a:
        s = sp[a:b]
        med[i] = np.median(s); mean[i] = s.mean(); mx[i] = s.max(); last[i] = s[-1]
np.savez(os.path.join(HERE, 'spread_m1.npz'), med=med, mean=mean, mx=mx, last=last)
print('ticks', len(T), 'bars', len(t1), 'nan bars', int(np.isnan(med).sum()), 'median of medians', np.nanmedian(med))
