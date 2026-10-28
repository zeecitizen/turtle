"""Correlated hedge + reversal detail for 2026-10-25 05-58-25 (m15). Hedge data: Axi M15 bars exported by mt5/ExportRates.mq5 (2025-01 -> 2026-10)."""
import sys, numpy as np
sys.path.insert(0, "research")
from _load import *
tr, st = trades(); P0 = tr[:, 6]
D = sim.data("m15"); t15 = D["t15"]; c15 = D["c15"]
CF = r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\rates_%s_M15.csv"
for sym, cost in (("USDJPY.pro", 0.00003), ("EURUSD.pro", 0.00002), ("XAGUSD.pro", 0.0008)):
    R = np.loadtxt(CF % sym, delimiter=","); th, ch = R[:, 0].astype(np.int64), R[:, 4]
    k = np.searchsorted(th, t15, "right") - 1; ok = k >= 0; hc = np.where(ok, ch[np.clip(k, 0, None)], np.nan)
    rg = np.diff(np.log(c15)); rh = np.diff(np.log(hc))
    sel = (tr[:, 1] >= th[0] + 30 * 86400)
    for frac in (0.5, 1.0):
        pp, base, corr = [], [], []
        for x, p in zip(tr[sel], P0[sel]):
            i = np.searchsorted(t15, x[1], "right") - 2; j = np.searchsorted(t15, x[4], "right") - 1
            a, b = rg[i - 2000:i], rh[i - 2000:i]; m = np.isfinite(a) & np.isfinite(b)
            beta = np.cov(a[m], b[m])[0, 1] / np.var(b[m]); corr.append(np.corrcoef(a[m], b[m])[0, 1])
            V = 200 * x[2]                                            # 2 lots = 200 oz of gold
            ret = np.log(hc[j] / hc[i + 1]) if np.isfinite(hc[j]) and np.isfinite(hc[i + 1]) else 0
            hed = -x[0] * frac * beta * V * ret - cost * abs(frac * beta) * V
            pp.append(p + hed); base.append(p)
        pp, base = np.array(pp), np.array(base)
        print(f"{sym:11s} hedge {frac:.0%} beta | corr {np.mean(corr):+.2f} | trades {len(pp)} | net {base.sum():+9,.0f} -> {pp.sum():+9,.0f} | worst {base.min():+7,.0f} -> {pp.min():+7,.0f} | big losers avg {base[base<-3000].mean():+6,.0f} -> {pp[base<-3000].mean():+6,.0f} | WR {100*(pp>0).mean():.1f}%")
# reversal detail: the reversal trade alone
T = np.memmap("simdata/m15_tick_raw_t.bin", dtype=np.float64, mode="r"); B = np.memmap("simdata/m15_tick_raw_bid.bin", dtype=np.float64, mode="r"); A = np.memmap("simdata/m15_tick_raw_ask.bin", dtype=np.float64, mode="r")
mid = np.median(tr[:, 1])
for tp, sl in ((10, 10), (25, 25)):
    res = []
    for x, p in zip(tr, P0):
        if p > -3000: continue
        sd = -x[0]; a = np.searchsorted(T, x[4]); f = np.searchsorted(T, x[4] + 5 * 86400)
        bb, aa = np.asarray(B[a:f]), np.asarray(A[a:f]); e = aa[0] if sd > 0 else bb[0]; px = bb if sd > 0 else aa; fv = (px - e) * sd
        z = np.flatnonzero((fv >= tp) | (fv <= -sl)); z = z[0] if len(z) else len(fv) - 1
        res.append((fv[z] * 600, x[4] < mid))
    r = np.array(res); w = r[:, 0] > 0
    print(f"reversal alone 3x TP{tp}/SL{sl}: {len(r)} trades, {w.sum()} won ({100*w.mean():.0f}%), net {r[:,0].sum():+,.0f}, half1 {r[r[:,1]>0,0].sum():+,.0f} ({100*w[r[:,1]>0].mean():.0f}%), half2 {r[r[:,1]==0,0].sum():+,.0f} ({100*w[r[:,1]==0].mean():.0f}%)")
