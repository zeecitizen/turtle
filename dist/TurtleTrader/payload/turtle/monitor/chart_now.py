"""chart_now.py — render the live market as a plain picture, and nothing else.

Zee 2026-08-04, after watching me fix the lifecycle with one more numeric rule: *"ye sab jo
apne kaha ye to means koi calculation hori hai. humne to apki VISION based trading intuition
develop karni thi na? koi IF ELSE conditions ni"* — and then: *"ap setup life cycle k har step
ko VISION based bana do. takay koi hard fixed rules na hon lekin apki EYES hon bass."*

He is right, and the drift was mine. The eleven-step ladder had become a second rulebook:
pivot scales, retracement-depth thresholds, volume-peak tests, body ratios. Each fix made the
arithmetic heavier and my eyes less necessary. A step that a threshold decides is not a step I
judged.

So this file draws the market and stops. Deliberately absent:

  * no UHV marker, no locked level, no breakout line — those are the computed answers, and
    seeing them would tell me what to think before I had looked
  * no trend label, no swing-high/low annotations, no step number
  * no indicator of any kind

What it draws is what a trader sees: candles with their bodies and wicks, volume beneath them
in the same colours, a price axis and a clock. Everything needed to say "that is a retracement,
that is the heavy counter-candle, that close has momentum" — and nothing that says it for me.

The lifecycle survives as vocabulary rather than as machinery. I still name the eleven steps,
but I name them from the picture: which one we are on, and why, in a sentence I could defend to
Zee with the chart in front of us both.

Usage:
    python monitor/chart_now.py            -> writes monitor/setup_labels/now.png
    python monitor/chart_now.py --bars 80  -> a wider window when context is missing
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gui"))

from claude_judge import load_bars, MARKETS                     # noqa: E402

OUT = Path(__file__).resolve().parent / "setup_labels" / "now.png"
UP, DOWN = "#26a69a", "#ef5350"          # the platform's own green and red, so my eye is
                                          # reading the same colours Zee reads


DPI = 110


def render(market="XAU", n=60, out=OUT, width_px=None, height_px=None):
    """Draw the last n candles with volume. No overlays, no opinions.

    Zee 2026-08-04, looking at Turtle NS/ND: *"can you make the live chart occupy as much width
    as is available (maximize it to cover available area)"* — and the picture he sent showed why
    the old fix was not enough. Tk can only shrink an image by whole-number factors, so a fixed
    1430x825 render inside a 1340-wide panel had to drop to factor 2 (715x412) and left half the
    window empty. Shrinking was always the wrong lever.

    So the caller now says how many pixels it actually has and the figure is BUILT at that size.
    Nothing is subsampled, nothing is guessed, and the candles are as large as the window allows.
    """
    bars = load_bars(MARKETS[market]["data"])[-n:]
    if not bars:
        raise SystemExit("no bars")

    figsize = ((width_px / DPI, height_px / DPI) if (width_px and height_px) else (13, 7.5))
    fig, (ax, av) = plt.subplots(
        2, 1, figsize=figsize, sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1], "hspace": 0.06})

    for i, b in enumerate(bars):
        c = UP if b.c >= b.o else DOWN
        # wick first so the body sits on top of it
        ax.plot([i, i], [b.l, b.h], color=c, linewidth=1.1, zorder=1)
        lo, hi = min(b.o, b.c), max(b.o, b.c)
        ax.bar(i, max(hi - lo, 0.01), bottom=lo, width=0.68,
               color=c, edgecolor=c, zorder=2)
        av.bar(i, b.v, width=0.68, color=c, alpha=0.85)

    # the axes a trader actually needs: what price, and what time
    ax.grid(alpha=0.18, linewidth=0.6)
    av.grid(alpha=0.18, linewidth=0.6)
    ax.yaxis.set_major_locator(MaxNLocator(9))
    av.set_ylabel("volume", fontsize=8)
    step = max(1, len(bars) // 12)
    ticks = list(range(0, len(bars), step))
    av.set_xticks(ticks)
    av.set_xticklabels([bars[i].t.strftime("%H:%M") for i in ticks], fontsize=8)
    ax.set_xlim(-1, len(bars))
    ax.set_title(f"{market}  ·  M1  ·  {bars[0].t:%H:%M}Z – {bars[-1].t:%H:%M}Z"
                 f"  ·  last {bars[-1].c:.2f}", fontsize=11, loc="left")
    for a in (ax, av):
        for s in a.spines.values():
            s.set_alpha(0.25)

    out.parent.mkdir(parents=True, exist_ok=True)
    # bbox_inches="tight" would crop back to the ink and undo the exact sizing
    fig.savefig(out, dpi=DPI,
                bbox_inches=(None if (width_px and height_px) else "tight"),
                facecolor="white")
    plt.close(fig)
    return out, bars


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("market", nargs="?", default="XAU")
    ap.add_argument("--bars", type=int, default=60)
    a = ap.parse_args()
    p, bars = render(a.market, a.bars)
    print(f"  {p}")
    print(f"  {len(bars)} candles  {bars[0].t:%H:%M}Z -> {bars[-1].t:%H:%M}Z  "
          f"last {bars[-1].c:.2f}")
