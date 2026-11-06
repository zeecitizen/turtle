"""zoom_charts.py - batch 7 study aid: for each loss and twin, a zoomed 1-min chart (y-range fitted to price action, not the stop)
plus a 5-min context panel of the prior ~10 hours. Solid = known at entry, faded = after. Writes agents/batch_7/zoom/<id>.png"""
import datetime as dt
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
z = np.load(os.path.join(LS, "arrays.npz"))
t1, o1, h1, l1, c1, v1 = (z[k] for k in ("t", "o", "h", "l", "c", "v"))
H = z["humps"]
T = {t["id"]: t for t in json.load(open(os.path.join(LS, "trades.json"), encoding="utf-8"))}
B = json.load(open(os.path.join(LS, "batch_7.json"), encoding="utf-8"))
PKT = dt.timezone(dt.timedelta(hours=5))
PIP = 1e-4


def lab(i):
    return dt.datetime.fromtimestamp(int(t1[i]), dt.timezone.utc).astimezone(PKT).strftime("%H:%M")


def draw(t, path):
    k, kb, ku, side = t["k"], t["kb"], t["ku"], t["side"]
    a, b = k - 89, kb + 30
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 0.9, 2.2])
    ax = fig.add_subplot(gs[0]); av = fig.add_subplot(gs[1], sharex=ax); a5 = fig.add_subplot(gs[2])
    fig.patch.set_facecolor("#131722")
    for axx in (ax, av, a5):
        axx.set_facecolor("#131722"); axx.tick_params(colors="#b2b5be", labelsize=8)
        for sp in axx.spines.values():
            sp.set_color("#363a45")
        axx.grid(color="#2a2e39", linewidth=0.5)
    xs = np.arange(a, b + 1)
    for i in xs:
        fut = i >= kb
        al = 0.3 if fut else 1.0
        col = "#26a69a" if c1[i] >= o1[i] else "#ef5350"
        ax.vlines(i, l1[i], h1[i], color=col, linewidth=1, alpha=al)
        ax.add_patch(plt.Rectangle((i - 0.35, min(o1[i], c1[i])), 0.7, max(abs(c1[i] - o1[i]), 2e-7), color=col, alpha=al))
        av.bar(i, v1[i], width=0.8, color="#ffb300" if i == ku else col, alpha=1.0 if i == ku else al)
    for b0, vv0, bh, vh, bb1, vv1, trr, known in H:
        b0, bh, bb1, known = int(b0), int(bh), int(bb1), int(known)
        if bb1 < a or b0 > b:
            continue
        colr = "#26a69a" if trr == 1 else "#ef5350" if trr == -1 else "#9e9e9e"
        kn = known <= k
        ax.plot([b0, bh, bb1], [vv0, vh, vv1], color=colr, linewidth=2.0 if kn else 1.0, alpha=0.9 if kn else 0.25, linestyle="-" if kn else "--")
    lo = min(l1[a:b + 1].min(), t["fill"]); hi = max(h1[a:b + 1].max(), t["fill"])
    pad = (hi - lo) * 0.06 + 0.2 * PIP
    ax.set_ylim(lo - pad, hi + pad)
    ax.axhline(t["level"], color="#ffb300", linewidth=0.9, linestyle="--")
    ax.axhline(t["extreme"], color="#ab47bc", linewidth=0.9, linestyle=":")
    ax.axvline(kb - 0.5, color="#ffffff", linewidth=0.8, alpha=0.6)
    ax.scatter([kb], [t["fill"]], marker="^" if side > 0 else "v", s=150, color="#00e5ff", zorder=5)
    # prior extremes: highest high / lowest low of last 30, 60, 90 closed bars
    for n, cc in ((30, "#90caf9"), (90, "#ce93d8")):
        ax.hlines(h1[k - n + 1:k + 1].max(), k - n + 1, k, color=cc, linewidth=0.7, linestyle="-.")
        ax.hlines(l1[k - n + 1:k + 1].min(), k - n + 1, k, color=cc, linewidth=0.7, linestyle="-.")
    ticks = list(range(a, b + 1, 10))
    av.set_xticks(ticks); av.set_xticklabels([lab(i) for i in ticks]); plt.setp(ax.get_xticklabels(), visible=False)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.5f"))
    res = "WIN" if t["win"] else "LOSS"
    ax.set_title(f"{t['id']} {res} {t['pnl']:+.0f}$  {'BUY' if side > 0 else 'SELL'} fill {t['fill']:.5f} level {t['level']:.5f} extreme {t['extreme']:.5f}  "
                 f"cam {t['camEff']:+d}x{abs(t['camStk'])}  uhv_v {t['uhv_v']:.0f} brk {t['brk_ticks_so_far']}  box {t['box']}  "
                 f"entry {dt.datetime.fromtimestamp(t['t_in'], dt.timezone.utc).astimezone(PKT):%a %H:%M:%S} PKT", color="#d1d4dc", fontsize=9, loc="left")
    # 5-min context: 10 h before, 2 h after
    s0 = kb - 600; s1 = kb + 120
    s0 -= (s0 % 5)
    bars = []
    for j in range(s0, s1, 5):
        if j + 5 > len(t1):
            break
        bars.append((j, o1[j], h1[j:j + 5].max(), l1[j:j + 5].min(), c1[j + 4], j + 4 < kb))
    for n_, (j, oo, hh, ll, cc_, known) in enumerate(bars):
        col = "#26a69a" if cc_ >= oo else "#ef5350"
        al = 1.0 if known else 0.3
        a5.vlines(n_, ll, hh, color=col, linewidth=1, alpha=al)
        a5.add_patch(plt.Rectangle((n_ - 0.35, min(oo, cc_)), 0.7, max(abs(cc_ - oo), 2e-7), color=col, alpha=al))
    nk = next(n_ for n_, bb in enumerate(bars) if bb[0] + 5 > kb - 1) if bars else 0
    a5.axvline(nk + 0.5, color="#ffffff", linewidth=0.8, alpha=0.6)
    a5.axhline(t["fill"], color="#00e5ff", linewidth=0.8, linestyle="--")
    a5.axhline(t["stop"], color="#ef5350", linewidth=0.8, linestyle="-.")
    t5 = list(range(0, len(bars), 12))
    a5.set_xticks(t5); a5.set_xticklabels([lab(bars[n_][0]) for n_ in t5])
    a5.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.5f"))
    a5.set_title("5-min context: 10h before entry (solid) + 2h after (faded); cyan = fill, red = stop", color="#d1d4dc", fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=72, facecolor=fig.get_facecolor())
    plt.close(fig)


ids = [x["id"] for x in B["losses"]] + [x["id"] for x in B["twins"]]
if len(sys.argv) > 1:
    ids = sys.argv[1:]
for tid in ids:
    draw(T[tid], os.path.join(HERE, "zoom", tid + ".png"))
print("done", len(ids))
