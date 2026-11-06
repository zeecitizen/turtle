"""loss_filters.py - Zee 2026-11-06: "i've labelled the losses by writing comments ... find out what's causing the losses and try to remove the
lossy trades by fixing the system based on observations in the comments". Turns each pattern in his comments into a measurable filter on the
97.7% setting (settings/saved/2026-11-05 05-45-38.json) and reports, over ALL its trades: winners removed, losers removed, net change, and how
many of his 22 commented losses each filter removes. Python tick replay = a hypothesis (CLAUDE.md); MT5 promotes.
Run: py research/loss_filters.py"""
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import sim  # noqa: E402
import uhv_engine as U  # noqa: E402

PIP = 1e-4
inp = json.load(open(os.path.join(HERE, "settings", "saved", "2026-11-05 05-45-38.json"), encoding="utf-8"))["inputs"]
C = json.load(open(os.path.join(HERE, "settings", "loss_comments.json"), encoding="utf-8"))
tagged = [(v["trade"]["entry_time"], v["trade"]["side"]) for v in C.values()]

tr, _, _ = U.simulate(inp)
R = tr[tr[:, 10] == 0]
D = sim.data("year1")
t1, o1, h1, l1, c1 = (np.asarray(D[k]) for k in ("t1", "o1", "h1", "l1", "c1"))
atr = np.asarray(D["atr"])


def pivots(k, p=1, look=120):
    """confirmed swing highs / lows (p candles each side) among the closed bars up to k: lists of (bar, price), oldest first"""
    hs, ls = [], []
    for j in range(max(p, k - look), k - p + 1):
        if all(h1[j] >= h1[j - d] and h1[j] >= h1[j + d] for d in range(1, p + 1)):
            hs.append((j, h1[j]))
        if all(l1[j] <= l1[j - d] and l1[j] <= l1[j + d] for d in range(1, p + 1)):
            ls.append((j, l1[j]))
    return hs, ls


rows = []
for x in R:
    side, tin, fill, pnl = int(x[0]), float(x[1]), float(x[2]), float(x[6])
    k = int(np.searchsorted(t1, (tin // 60) * 60)) - 1          # the last closed candle before the entry minute
    if k < 130:
        continue
    hs, ls = pivots(k)
    f = {}
    # 1. structure: buys need the last swing high above the one before (higher high) AND a higher low; sells mirror
    if len(hs) >= 2 and len(ls) >= 2:
        hh, hl = hs[-1][1] > hs[-2][1], ls[-1][1] > ls[-2][1]
        ll, lh = ls[-1][1] < ls[-2][1], hs[-1][1] < hs[-2][1]
        f["structure"] = not ((hh and hl) if side > 0 else (ll and lh))
        f["struct_hh_only"] = not (hh if side > 0 else ll)       # only the higher high (lower low) part
    # 2. support / resistance: a sell within 1.5 pips above the lowest low of the last 60 candles (a buy below the highest high)
    lo60, hi60 = l1[k - 59:k + 1].min(), h1[k - 59:k + 1].max()
    f["sr_1.5"] = (fill - lo60) < 1.5 * PIP if side < 0 else (hi60 - fill) < 1.5 * PIP
    f["sr_3"] = (fill - lo60) < 3 * PIP if side < 0 else (hi60 - fill) < 3 * PIP
    # 3. ranging: the last 10 candles' range under 1.5 ATR
    rg = h1[k - 9:k + 1].max() - l1[k - 9:k + 1].min()
    f["range_1.5atr"] = atr[k] > 0 and rg < 1.5 * atr[k]
    f["range_2atr"] = atr[k] > 0 and rg < 2.0 * atr[k]
    # 4. market close: 20:45 - 21:15 UTC (PrimeXBT's daily close at 21:00 UTC)
    mod = tin % 86400
    f["close"] = 20 * 3600 + 45 * 60 <= mod <= 21 * 3600 + 15 * 60
    tag = any(abs(tin - t) < 3 and sd == side for t, sd in tagged)
    rows.append((pnl, tag, f, tin, side))

names = sorted({k for _, _, f, _, _ in rows for k in f})
n = len(rows); w = sum(1 for p, *_ in rows if p > 0); lz = n - w
net = sum(p for p, *_ in rows)
print(f"97.7% setting: {n} trades, {w} won ({100 * w / n:.1f}%), net ${net:,.0f} at 1 lot; his tagged losses found: {sum(r[1] for r in rows)}")
print(f"{'filter':16s} {'wins out':>8s} {'losses out':>10s} {'tagged out':>10s} {'new WR':>7s} {'net change':>11s}")
for nm in names:
    out = [(p, t) for p, t, f, *_ in rows if f.get(nm)]
    wo = sum(1 for p, _ in out if p > 0); lo = len(out) - wo; to = sum(1 for _, t in out if t)
    keep_w, keep_n = w - wo, n - len(out)
    print(f"{nm:16s} {wo:8d} {lo:10d} {to:7d}/22 {100 * keep_w / max(keep_n, 1):6.1f}% {-sum(p for p, _ in out):+11,.0f}")

import datetime as dt
print()
print("each commented loss -> the filters that would have removed it")
for p, t, f, tin, side in sorted([r for r in rows if r[1]], key=lambda r: r[3]):
    hit = [k for k in ("close", "structure", "struct_hh_only", "sr_1.5", "sr_3", "range_2atr") if f.get(k)]
    print(dt.datetime.fromtimestamp(tin, dt.timezone.utc).strftime("%m-%d %H:%M"), "BUY " if side > 0 else "SELL", f"{p:8.0f}", ", ".join(hit) or "- none -")
