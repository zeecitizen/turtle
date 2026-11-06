"""EMA-order hint study on EUR/USD M1 bars built from Zee's MT5 tick export. HYPOTHESIS ONLY (CLAUDE.md): Python fills where it likes.
Question: after two EMAs cross and X candles pass without a re-cross, does the EMA order point the way the next move goes?
Each entry is a game round: fill at the bar close (long pays the bar's average spread), +D target / -D stop, first touch in later bars,
a bar touching both counts as a LOSS, 120 minutes max (unresolved = loss). Broker hour 00 and bars with spread > 0.5 pip are skipped.
The hint's edge = win rate WITH the EMA order minus win rate AGAINST it at the same moments - the spread mostly cancels out of that."""
import collections
import sys
import numpy as np

CSV = r"C:\Users\zeesh\turtle\data\eurusd_m1\EURUSD_M1_2026-01_2026-11_from_ticks.csv"
D = np.genfromtxt(CSV, delimiter=",", skip_header=1)
t, o, h, l, c, nt, sp = D.T
t = t.astype(np.int64)
N = len(t)
hour = (t // 3600) % 24
SPLIT = 1751328000 + 365 * 86400          # 2026-07-01 00:00 (file clock): choose on Jan-Jun, judge on Jul-Nov
day = t // 86400


def outcomes(dist, maxbars=120):
    lw = np.zeros(N, np.int8); sw = np.zeros(N, np.int8)
    lfill = c + sp; sfill = c
    lopen = np.ones(N, bool); sopen = np.ones(N, bool)
    idx = np.arange(N)
    for k in range(1, maxbars + 1):
        j = np.minimum(idx + k, N - 1)
        alive = (idx + k < N) & (t[j] - t <= maxbars * 60 + 60)
        tp = h[j] >= lfill + dist; sl = l[j] <= lfill - dist
        m = lopen & alive
        lw[m & tp & ~sl] = 1
        lopen &= ~(m & (tp | sl))
        tp = l[j] + sp[j] <= sfill - dist; sl = h[j] + sp[j] >= sfill + dist
        m = sopen & alive
        sw[m & tp & ~sl] = 1
        sopen &= ~(m & (tp | sl))
    return lw, sw


def ema(x, n):
    a = 2.0 / (n + 1); out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


TFC = {}


def tf_closes(tf):
    """Closes of tf-minute bars, and for each M1 bar the index of the last COMPLETED tf bar (M1: the bar itself, known at its close)."""
    if tf in TFC:
        return TFC[tf]
    if tf == 1:
        TFC[tf] = (c.copy(), np.arange(N))
    else:
        g = t // (tf * 60)
        newb = np.r_[False, g[1:] != g[:-1]]
        last = np.r_[g[1:] != g[:-1], True]
        bid = np.cumsum(newb)                       # bucket id of each M1 bar
        closes = c[last]
        ref = np.where(last, bid, bid - 1)          # at the bucket's last M1 close that bucket is complete
        TFC[tf] = (closes, ref)
    return TFC[tf]


EM = {}


def order_state(tf, fast, slow):
    closes, ref = tf_closes(tf)
    for n in (fast, slow):
        if (tf, n) not in EM:
            EM[(tf, n)] = ema(closes, n)
    d = np.sign(EM[(tf, fast)] - EM[(tf, slow)])
    held = np.zeros(len(d), np.int64)
    same = d[1:] == d[:-1]
    for i in range(1, len(d)):
        held[i] = held[i - 1] + 1 if same[i - 1] else 0
    ok = ref >= slow * 3
    rr = np.clip(ref, 0, None)
    return np.where(ok, d[rr], 0), np.where(ok, held[rr], -1), rr


TURTLE = [(9, 50, 'Zee 9/50'), (3, 4, '1min-saved 3/4'), (14, 70, '1min-EA 14/70'), (19, 66, 'TV 19/66'), (19, 58, 'TV 19/58'),
          (19, 64, 'TV 19/64'), (21, 56, 'TV 21/56'), (20, 62, 'TV 20/62'), (17, 60, 'TV 17/60'), (16, 64, 'TV 16/64'), (21, 50, 'TV 21/50'),
          (16, 32, 'TV 16/32'), (10, 34, 'TV 10/34'), (23, 42, 'TV 23/42')]
GRID = [(f, s, f'grid {f}/{s}') for f in (5, 8, 13, 21, 34) for s in (21, 34, 55, 89, 144, 200) if s > f * 1.5]
SKIPS = (0, 3, 5, 10, 20, 30)


def study(dist, label):
    lw, sw = outcomes(dist)
    tradable = (hour != 0) & (sp <= 0.00005) & (nt >= 2)
    print(f"\n==== {label}: target {dist*1e4:.0f} pips / stop {dist*1e4:.0f} pips ====")
    print(f"coin-flip baseline (every tradable minute): long wins {lw[tradable].mean()*100:.1f}%  short wins {sw[tradable].mean()*100:.1f}%")
    R = collections.defaultdict(dict)
    for tf in (1, 5, 15):
        for fast, slow, name in TURTLE + GRID:
            s, held, rr = order_state(tf, fast, slow)
            first = np.r_[True, rr[1:] != rr[:-1]]   # the first M1 bar after each tf bar closes (one entry per tf bar)
            ww_all = np.where(s > 0, lw, sw); wa_all = np.where(s > 0, sw, lw)
            for X in SKIPS:
                at = tradable & (s != 0) & (held == X) & first
                for part, m in (('IS', at & (t < SPLIT)), ('OOS', at & (t >= SPLIT))):
                    n = int(m.sum())
                    if n < 30:
                        continue
                    ww, wa = ww_all[m].mean() * 100, wa_all[m].mean() * 100
                    e = ww_all[m].astype(float) - wa_all[m]; dd = day[m]
                    ud, inv = np.unique(dd, return_inverse=True)
                    mu = e.mean()                                 # day-clustered t: trades on one day are not independent
                    dev = np.bincount(inv, e - mu)
                    ts = e.sum() / np.sqrt((dev ** 2).sum()) if (dev ** 2).sum() > 0 else 0.0
                    R[(tf, name, X)][part] = (n, ww, wa, ww - wa, ts)
    keys = [k for k in R if 'IS' in R[k] and 'OOS' in R[k] and R[k]['IS'][0] >= 100]
    keys.sort(key=lambda k: -R[k]['IS'][3])
    print(f"{len(keys)} combinations (timeframe x EMA pair x skip). Top 12 chosen on Jan-Jun, then the same ones on Jul-Nov:")
    print(" tf   pair             skip |  IS n  with%   vs%  edge     t ||  OOS n  with%   vs%  edge     t")
    for k in keys[:12]:
        a, b = R[k]['IS'], R[k]['OOS']
        print(f" M{k[0]:<3} {k[1]:<16} {k[2]:>3} | {a[0]:5d} {a[1]:5.1f} {a[2]:5.1f} {a[3]:+5.1f} {a[4]:+5.1f} || {b[0]:5d} {b[1]:5.1f} {b[2]:5.1f} {b[3]:+5.1f} {b[4]:+5.1f}")
    print(" Zee's 9/50, the 1-minute saves and the Turtle TV pairs (OOS Jul-Nov):")
    for k in sorted([k for k in keys if not k[1].startswith('grid') and k[2] in (0, 5, 10, 20)], key=lambda k: (k[1], k[0], k[2])):
        b = R[k]['OOS']
        print(f"   M{k[0]:<3} {k[1]:<16} skip {k[2]:>2}: n {b[0]:5d}  with {b[1]:5.1f}%  against {b[2]:5.1f}%  edge {b[3]:+5.1f}  t {b[4]:+5.1f}")
    ei = np.array([R[k]['IS'][3] for k in keys]); eo = np.array([R[k]['OOS'][3] for k in keys])
    for tf in (1, 5, 15):
        sel = np.array([k[0] == tf for k in keys])
        print(f" M{tf}: mean edge IS {ei[sel].mean():+.2f}  OOS {eo[sel].mean():+.2f}  | OOS edge > 0 in {int((eo[sel] > 0).sum())}/{int(sel.sum())}")
    print(f" all: corr(IS edge, OOS edge) across combos {np.corrcoef(ei, eo)[0, 1]:+.2f}")
    return R, keys


R2, K2 = study(0.0002, "GAME GEOMETRY")
R5, K5 = study(0.0005, "WIDER CHECK")
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor")
from doctrine import python_says  # noqa: E402
print()
for R, K, lab in ((R2, K2, '2-pip'), (R5, K5, '5-pip')):
    k = K[0]; b = R[k]['OOS']
    python_says(f"{lab}: best Jan-Jun combo M{k[0]} {k[1]} skip {k[2]} judged on Jul-Nov (n {b[0]}), WITH the EMA order", b[1], need_pct=50)
    python_says(f"{lab}: same moments, AGAINST the EMA order", b[2], need_pct=50)
