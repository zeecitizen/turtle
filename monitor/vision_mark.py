"""vision_mark.py — Claude marks the chart from what she SEES, not from the rule engine.

Zee 2026-08-03: *"LIVE chart pe interpreted vision labels hon. Kahan pe humne retracement
dhoondi, ab konsa wala UHV / breakout hai vision ke mutabiq — not text analysis, but REAL
Claude's vision of looking at a screenshot. Phir user ko 2 buttons: 'Correct, take it' /
'Ummm.. not sure this works'."*

The detector's RET/UHV/BRKT are geometry. These are Claude's own reading of the picture,
which is the thing that actually beat the rule engine. They are kept apart on purpose: when
the two disagree, that disagreement is the interesting part, and Zee's two buttons say which
eye was right.

    # Claude, after LOOKING at monitor/setup_labels/own.png:
    py monitor/vision_mark.py XAU --trend up --side BUY \
        --ret 21:14 --uhv 21:17 --brkt 21:21 \
        --note "higher lows since 21:02; UHV is the fat red bar, breakout is the green one"

Writes vision_reading.json (what Claude sees) and vision.png (the chart with her labels).
Turtle Desktop shows both and offers Zee the two buttons.
"""
from __future__ import annotations
import argparse, csv, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "strategy_lab"))

OUT_PNG = HERE / "setup_labels" / "vision.png"
OUT_JSON = HERE / "setup_labels" / "vision_reading.json"
FEEDBACK = HERE / "vision_feedback.jsonl"

G, R, GOLD, PUR, BLUE, GREY = "#16a34a", "#dc2626", "#b8860b", "#9333ea", "#2563eb", "#64748b"
TREND_COLOUR = {"up": G, "down": R, "ranging": GREY, "shifting": "#f59e0b"}


def _bars(market):
    import claude_judge as J
    import build_entry_review_m5 as B
    m = J.MARKETS[market]
    bars = J.load_bars(m["data"])
    return bars, m["tz"]


def _match(bars, tz, hhmm):
    """Find the bar whose displayed label is hh:mm (the axis the human is reading)."""
    if not hhmm:
        return None
    hhmm = hhmm.strip()
    for i, b in enumerate(bars):
        if f"{(b.t.hour + tz) % 24:02d}:{b.t.minute:02d}" == hhmm:
            return i
    return None


def draw(market, reading, back=45):
    bars, tz = _bars(market)
    if len(bars) < 20:
        raise RuntimeError(f"only {len(bars)} bars")
    hi = len(bars)
    lo = max(0, hi - back)
    seg = bars[lo:hi]

    fig, (ax, av) = plt.subplots(2, 1, figsize=(12, 6.2),
                                 gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    for x, b in enumerate(seg):
        col = G if b.c >= b.o else R
        ax.plot([x, x], [b.l, b.h], color=col, lw=1.2, solid_capstyle="round", zorder=1)
        ax.add_patch(Rectangle((x - 0.34, min(b.o, b.c)), 0.68,
                               max(abs(b.c - b.o), (b.h - b.l) * 0.02 or 0.02),
                               facecolor=col, edgecolor=col, zorder=2))
        av.add_patch(Rectangle((x - 0.34, 0), 0.68, b.v, facecolor=col, alpha=0.7,
                               edgecolor="none"))
    av.set_ylim(0, max(b.v for b in seg) * 1.15)
    for a in (ax, av):
        a.set_xlim(-0.7, len(seg) - 0.3)

    for label, key, colour in (("RET", "ret", PUR), ("UHV", "uhv", GOLD),
                               ("BRKT", "brkt", BLUE)):
        i = _match(bars, tz, reading.get(key))
        if i is None or not (lo <= i < hi):
            continue
        b = bars[i]
        x = i - lo
        ax.axvline(x, color=colour, lw=1.0, ls=":", alpha=0.55, zorder=0)
        ax.annotate(label, (x, b.h + (b.h - b.l) * 0.55), ha="center", fontsize=10,
                    fontweight="bold", color=colour,
                    bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=colour, lw=1.6,
                              alpha=0.97), zorder=5)

    tcol = TREND_COLOUR.get(reading.get("trend", "ranging"), GREY)
    ax.set_title(f"CLAUDE'S EYES  —  {reading.get('trend', '?').upper()}"
                 + (f"   ·   wants {reading['side']}" if reading.get("side") else "")
                 + (f"   ·   {reading['confidence']}" if reading.get("confidence") else ""),
                 fontsize=12, fontweight="bold", loc="left", color=tcol)
    if reading.get("note"):
        ax.set_xlabel(reading["note"][:150], fontsize=9, color="#334155", loc="left")

    ticks = list(range(0, len(seg), 8))
    ax.set_xticks([]); av.set_xticks(ticks)
    av.set_xticklabels([f"{(seg[t].t.hour + tz) % 24:02d}:{seg[t].t.minute:02d}"
                        for t in ticks], fontsize=8)
    ax.grid(True, ls=":", alpha=0.3); av.grid(True, axis="y", ls=":", alpha=0.3)
    av.set_ylabel("Vol", fontsize=9)
    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=85, bbox_inches="tight")
    plt.close(fig)
    return OUT_PNG


def mark(market, **kw):
    reading = {k: v for k, v in kw.items() if v}
    reading.update({"market": market, "ts": int(time.time()),
                    "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    png = draw(market, reading)
    reading["png"] = str(png)
    OUT_JSON.write_text(json.dumps(reading, indent=1, ensure_ascii=False), encoding="utf-8")
    return reading


def latest():
    try:
        d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
    d["age_sec"] = int(time.time()) - int(d.get("ts", 0))
    return d


def feedback(verdict, note=""):
    """Zee's answer to Claude's reading: 'correct' or 'unsure'."""
    d = latest() or {}
    rec = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "verdict": verdict, "note": note,
           "reading": {k: d.get(k) for k in
                       ("market", "trend", "side", "ret", "uhv", "brkt", "note", "utc")}}
    with FEEDBACK.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def score():
    """How often Zee has agreed with Claude's visual reading."""
    if not FEEDBACK.exists():
        return None
    ok = tot = 0
    for line in FEEDBACK.read_text(encoding="utf-8").splitlines():
        try:
            v = json.loads(line).get("verdict")
        except Exception:
            continue
        tot += 1
        ok += (v == "correct")
    return None if not tot else {"agreed": ok, "total": tot, "pct": 100.0 * ok / tot}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Claude marks the chart from vision")
    ap.add_argument("market", nargs="?", default="XAU", choices=["XAU", "BTC"])
    ap.add_argument("--trend", choices=["up", "down", "ranging", "shifting"], required=False)
    ap.add_argument("--side", choices=["BUY", "SELL", "NONE"])
    ap.add_argument("--ret", help="hh:mm of the retracement start, as shown on the axis")
    ap.add_argument("--uhv", help="hh:mm of the UHV candle")
    ap.add_argument("--brkt", help="hh:mm of the breakout candle")
    ap.add_argument("--confidence", choices=["high", "medium", "low"])
    ap.add_argument("--note", default="")
    ap.add_argument("--feedback", choices=["correct", "unsure"])
    a = ap.parse_args()
    if a.feedback:
        print(json.dumps(feedback(a.feedback, a.note), indent=1))
    else:
        if not a.trend:
            ap.error("--trend is required when marking")
        print(json.dumps(mark(a.market, trend=a.trend, side=a.side, ret=a.ret, uhv=a.uhv,
                              brkt=a.brkt, confidence=a.confidence, note=a.note), indent=1))
