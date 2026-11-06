"""Six internet gates on 2026-10-25 05-58-25 (m15). Post-hoc screen: features at entry, drop trades failing the gate."""
import sys, numpy as np
sys.path.insert(0, "research")
from _load import *
tr, st = trades()
D = sim.data("m15"); t15 = D["t15"]; o=D["o15"]; h=D["h15"]; l=D["l15"]; c=D["c15"]; atr=D["atr"]
T = np.memmap("simdata/m15_tick_raw_t.bin", dtype=np.float64, mode="r")
B = np.memmap("simdata/m15_tick_raw_bid.bin", dtype=np.float64, mode="r")
# H1 bars from M15
hk = t15 // 3600; brk = np.r_[True, hk[1:] != hk[:-1]]; hid = np.cumsum(brk) - 1
hc = np.array([c[hid == k][-1] for k in range(hid[-1] + 1)]) if False else None
last = np.r_[np.nonzero(brk)[0][1:] - 1, len(c) - 1]; hc = c[last]
def ema(x, n):
    a = 2 / (n + 1); y = np.empty_like(x); y[0] = x[0]
    for i in range(1, len(x)): y[i] = y[i-1] + a * (x[i] - y[i-1])
    return y
macd = ema(hc, 12) - ema(hc, 26); hist = macd - ema(macd, 9); e50h = ema(hc, 50)
rows = []
for x in tr:
    sd, te = x[0], x[1]
    i = np.searchsorted(t15, te, "right") - 2            # last CLOSED M15 candle = signal candle (approx)
    hh = hid[i] - 1                                      # last closed H1
    a, b = np.searchsorted(T, [te - 30, te]); a4 = np.searchsorted(T, te - 4 * 3600)
    spd = (b - a) / max(1, (b - a4) / 480)               # last 30s vs avg 30s over 4h
    s0, s1 = np.searchsorted(T, [t15[i], t15[i] + 900])
    pb = np.asarray(B[s0:s1]); rng = h[i] - l[i]
    if len(pb) > 5 and rng > 0:
        hist_, edges = np.histogram(pb, bins=10, range=(l[i], h[i])); pocp = (np.argmax(hist_) + .5) / 10
    else: pocp = .5
    poc_ok = pocp <= .3 if sd > 0 else pocp >= .7
    macd_ok = (hist[hh] > hist[hh-1]) if sd > 0 else (hist[hh] < hist[hh-1])
    slope = (e50h[hh] - e50h[hh-3]) * sd
    sw = False
    for j in (i, i - 1):                                 # signal or preceding candle sweeps a 3-bar pivot in the last 48 bars, closes back
        lo = [l[k] for k in range(j-48, j-3) if l[k] == l[k-3:k+4].min()]
        hi = [h[k] for k in range(j-48, j-3) if h[k] == h[k-3:k+4].max()]
        if sd > 0 and lo and any(l[j] < v and c[j] > v for v in lo): sw = True
        if sd < 0 and hi and any(h[j] > v and c[j] < v for v in hi): sw = True
    hr = int((te // 3600) % 24)
    rows.append((x[6], spd, poc_ok, macd_ok, slope, atr[i], sw, hr, te))
R = np.array(rows, dtype=float); p = R[:, 0]; mid = np.median(R[:, 8])
def show(name, keep):
    k = keep.astype(bool); q = p[k]; d = p[~k]
    h1, h2 = k & (R[:, 8] < mid), k & (R[:, 8] >= mid)
    lr = lambda m: 100 * (p[m] <= 0).mean() if m.sum() else 0
    print(f"{name:34s} kept {k.sum():4d} WR {100*(q>0).mean():5.1f}%  net {q.sum():+10,.0f}  worst {q.min():+7,.0f} | removed {len(d):4d} loss-rate {100*(d<=0).mean() if len(d) else 0:5.1f}%  net {d.sum():+9,.0f} | halves {p[h1].sum():+8,.0f} {p[h2].sum():+8,.0f}")
show("ALL (no gate)", np.ones(len(p)))
for q in (1.0, 1.5, 2.0): show(f"1 tick speed 30s >= {q}x 4h avg", R[:, 1] >= q)
show("2 tick-POC in tail (30%)", R[:, 2])
show("3a H1 MACD hist expanding our way", R[:, 3])
for s in (0, 0.5, 1.0): show(f"3b H1 EMA50 slope (3h) > ${s} our way", R[:, 4] > s)
for a in (1.5, 2.0, 3.0, 4.0): show(f"4 ATR(14) M15 >= ${a}", R[:, 5] >= a)
show("5 server hr 15-19 (~13-17 GMT)", (R[:, 7] >= 15) & (R[:, 7] < 19))
show("6 swept liquidity", R[:, 6])
np.save("research/gates6.npy", R)
