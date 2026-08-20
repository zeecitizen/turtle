"""line_diagram.py — THE SANITY DIAGRAM (Zee 2026-08-20, drawn by his own hand):

    "we should make the line diagram as soon as the UHV is formed and a candle is
    now expected to break it out. This line diagram shows me that the system is
    SANE. it knows which UHV its breaking and why in CLEAR CUT non negotiable TERMS."

Not a chart — a SCHEMATIC in his sketch's grammar: body-only rectangles (outlines),
the retracement reds, the UHV bold, the orange trigger line from its high, a dashed
ghost-rectangle where the breaker is expected, and the volume story below with the
'must be quieter' bar. Every element labeled in non-negotiable terms.
"""
from __future__ import annotations
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

GREEN = "#2f9e44"
RED = "#e03131"
DARKRED = "#7a1f1f"
ORANGE = "#f08c00"
LIME = "#a8cc14"
INK = "#222222"
DIM = "#888888"


def render(out=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyArrow

    import trend_eyes
    import setup_anatomy
    bars = trend_eyes.load_bars()
    a = setup_anatomy.analyze(bars)
    if not a or a.get("uhv") is None:
        return None, "no UHV formed yet — nothing to diagram (fresh leg)"
    side, u, trig = a["side"], a["uhv"], a["trigger"]
    price = a["price"]

    # window: from a little before the leg extreme to now
    ext_t = a["ext_t"]
    win = [b for b in bars if b[0] >= ext_t - timedelta(minutes=4)][-18:]
    if len(win) < 4:
        return None, "not enough bars"
    ui = next((i for i, b in enumerate(win) if b[0] == u[0]), None)

    fig, (ax, av) = plt.subplots(2, 1, figsize=(15, 9), height_ratios=[3, 1],
                                 sharex=True, facecolor="white")
    fig.subplots_adjust(right=0.70, hspace=0.06)

    opens = [win[0][3]] + [win[k - 1][3] for k in range(1, len(win))]
    for i, b in enumerate(win):
        o, c, v = opens[i], b[3], b[4]
        green = c > o
        lo, hi = min(o, c), max(o, c)
        is_uhv = (i == ui)
        col = (RED if not green else GREEN)
        lw = 4.0 if is_uhv else 2.0
        ax.add_patch(Rectangle((i - 0.32, lo), 0.64, max(hi - lo, 0.02),
                               fill=False, edgecolor=col, linewidth=lw, zorder=3))
        av.add_patch(Rectangle((i - 0.32, 0), 0.64, v, fill=False,
                               edgecolor=(DARKRED if is_uhv else (GREEN if green else RED)),
                               linewidth=4.0 if is_uhv else 1.6, zorder=3))
        if is_uhv:
            ax.annotate("THE UHV", xy=(i, hi), xytext=(i - 2.2, hi + 1.6),
                        fontsize=15, fontweight="bold", color=RED,
                        arrowprops=dict(arrowstyle="->", lw=2.4, color=RED))
            av.annotate(f"UHV vol {int(v)}", xy=(i, v), xytext=(i - 3.4, v * 1.06),
                        fontsize=12, fontweight="bold", color=DARKRED)

    # the trigger line, orange, from the UHV to beyond the right edge
    x0 = (ui if ui is not None else 0)
    ax.plot([x0, len(win) + 2.6], [trig, trig], color=ORANGE, lw=2.6, zorder=4)
    ax.text(len(win) + 2.7, trig, f" TRIGGER {trig:.2f}", color=ORANGE,
            fontsize=13, fontweight="bold", va="center")

    # the expected breaker: a dashed ghost rectangle crossing the line
    gx = len(win) + 0.9
    if side == "BUY":
        g_lo, g_hi = price - 0.15, trig + 0.55
    else:
        g_lo, g_hi = trig - 0.55, price + 0.15
    ax.add_patch(Rectangle((gx - 0.32, min(g_lo, g_hi)), 0.64, abs(g_hi - g_lo),
                           fill=False, edgecolor=LIME, linewidth=3.0,
                           linestyle="--", zorder=4))
    ax.annotate("the candle we are\nWAITING FOR", xy=(gx, max(g_lo, g_hi)),
                xytext=(gx - 4.6, max(g_lo, g_hi) + 1.7), fontsize=12,
                fontweight="bold", color=LIME, ha="center",
                arrowprops=dict(arrowstyle="->", lw=2.2, color=LIME))
    # its required volume: dashed bar UNDER the UHV's height
    req = u[4] * 0.75
    av.add_patch(Rectangle((gx - 0.32, 0), 0.64, req, fill=False, edgecolor=LIME,
                           linewidth=2.4, linestyle="--", zorder=4))
    av.annotate(f"must be < {int(u[4])}", xy=(gx, req), xytext=(gx - 3.9, u[4] * 0.92),
                fontsize=11, fontweight="bold", color=LIME)

    # current price marker
    ax.axhline(price, color=DIM, lw=1.0, ls=":")
    ax.text(len(win) + 2.7, price, f" now {price:.2f}", color=DIM, fontsize=11, va="center")

    # THE NON-NEGOTIABLE TERMS — the right-hand text block
    gate_line = ""
    try:
        r = trend_eyes.read_trend(bars)
        g = r.get("trend", "?")
        ok = (side == "BUY" and g == "UPTREND") or (side == "SELL" and g == "DOWNTREND")
        gate_line = (f"4. GATE: structure reads {g}"
                     + (" — a lawful break FIRES." if ok
                        else " — a break would be BENCHED\n   until structure confirms."))
    except Exception:
        pass
    dist = (trig - price) if side == "BUY" else (price - trig)
    pkt = (u[0] + timedelta(hours=5)).strftime("%H:%M")
    terms = (
        f"THE SANITY TERMS — {side} hunt\n"
        f"────────────────────────────\n"
        f"1. THE UHV: the {pkt} PKT candle,\n"
        f"   vol {int(u[4])} — LOUDEST counter-candle\n"
        f"   of this retracement. Non-negotiable.\n\n"
        f"2. THE TRIGGER: {trig:.2f} — its "
        f"{'HIGH' if side == 'BUY' else 'LOW'}.\n\n"
        f"3. THE BREAK: a {'GREEN' if side == 'BUY' else 'RED'} candle must\n"
        f"   CLOSE its body {'ABOVE' if side == 'BUY' else 'BELOW'} {trig:.2f}\n"
        f"   with volume BELOW {int(u[4])}.\n"
        f"   Distance now: {max(dist, 0):.2f} pts.\n\n"
        f"{gate_line}\n\n"
        f"volume: BROKER tick-count (the EA's\n"
        f"own eyes — no real vol on gold here).\n"
        f"TV's feed can disagree by a candle;\n"
        f"the machine trades the tape it fills on.\n\n"
        f"No other candle. No other line.\n"
        f"No other volume. That is the trade."
    )
    fig.text(0.72, 0.52, terms, fontsize=12.5, family="monospace", color=INK,
             va="center", ha="left",
             bbox=dict(boxstyle="round,pad=0.8", fc="#fbfbf6", ec="#c9c9b8", lw=1.2))

    lo_all = min(min(opens[i], b[3]) for i, b in enumerate(win))
    hi_all = max(max(opens[i], b[3]) for i, b in enumerate(win))
    pad = max((hi_all - lo_all) * 0.25, 1.2)
    ax.set_xlim(-1, len(win) + 4.2)
    ax.set_ylim(min(lo_all, trig) - pad, max(hi_all, trig) + pad + 1.2)
    av.set_ylim(0, max(b[4] for b in win) * 1.35)
    for axx in (ax, av):
        axx.set_xticks([]); axx.set_yticks([])
        for sp in axx.spines.values():
            sp.set_visible(False)
    from datetime import datetime as _dt
    stamp = (_dt.utcnow() + timedelta(hours=5)).strftime("%H:%M")
    ax.set_title(f"LINE DIAGRAM — the system's own sanity proof · drawn {stamp} PKT",
                 fontsize=15, fontweight="bold", loc="left", color=INK)
    av.set_ylabel("volume", fontsize=10, color=DIM)

    out = out or (Path(__file__).parent / "setup_labels" / "line_diagram.png")
    fig.savefig(str(out), dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out, f"{side} · UHV {pkt} vol {int(u[4])} · trigger {trig:.2f}"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p, msg = render()
    print(msg, "->", p)
