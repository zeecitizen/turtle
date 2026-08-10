"""uhv_review.py — draw every UHV the machine picks, so Zee can say yes or no.

Zee, 2026-08-10: "we were building a visual software. there we mark a UHV then its
breakout.. after the breakout the price genuinely goes into a profitable direction...
we still know that if we draw the correct drawing, then after the UHV is broken out,
we will gain a profit due to the STRATEGY ITSELF being nice. get the visual software
to draw what you'd draw, and only then mechanise it."

That is the right order and we had it backwards for six months: we mechanised a drawing
nobody had ever checked. The memory even records the suspicion — 'EA UHV detector
broken, 12 of 13 wrong: EA-flagged UHVs are NOT local volume max'. Nobody ever put the
two side by side on a chart.

So this draws them. Every UHV the detector picks on REAL archived bars, rendered as a
candle chart with the UHV marked, its breakout level drawn, and what price did next.
Zee flips through and says "that's the one" or "no, it's that other candle" — and only
what survives his eye gets mechanised.

It also measures, for each drawing, how far price travelled in the breakout direction
afterwards. That is a fact about the tape, not a simulated trade: no fills, no spread,
no P&L. It answers exactly the question he asked — after a correctly drawn breakout,
does price genuinely go the profitable way?

    py monitor/uhv_review.py              # build the gallery
    py monitor/uhv_review.py --open       # ...and open it
"""
import argparse
import csv
import statistics
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ARCHIVE = Path(__file__).with_name("tape_archive_xau.csv")
OUT = Path(__file__).parent.parent / "dashboard" / "uhv_review.html"

LOOK = 20          # bars the detector may call the UHV from
CTX = 28           # bars of context drawn to the left of the UHV
FWD = 30           # bars drawn (and measured) after the breakout
GAP = 300          # a hole bigger than this splits the tape


def load():
    rows = list(csv.DictReader(ARCHIVE.open(encoding="utf-8")))
    return [dict(t=int(r["time_unix"]), o=float(r["open"]), h=float(r["high"]),
                 l=float(r["low"]), c=float(r["close"]), v=int(r["volume"]))
            for r in rows]


def segments(bars):
    """Split at holes. A drawing that spans a weekend is a drawing of a weekend."""
    out, cur = [], [bars[0]]
    for a, b in zip(bars, bars[1:]):
        if b["t"] - a["t"] > GAP:
            if len(cur) > CTX + LOOK + FWD:
                out.append(cur)
            cur = []
        cur.append(b)
    if len(cur) > CTX + LOOK + FWD:
        out.append(cur)
    return out


def find_uhv(seg, i):
    """The loudest bar of the recent window — the candle Zee would circle.

    Deliberately the plainest possible reading of 'ultra high volume': the maximum,
    strictly above its neighbours, and clearly above the local average. If his eye
    disagrees with THIS, we learn something specific about what he actually looks at.
    """
    lo, hi = i - LOOK, i - 1
    if lo < 1:
        return None
    j = max(range(lo, hi + 1), key=lambda k: seg[k]["v"])
    if j <= 0 or j >= len(seg) - 1:
        return None
    if not (seg[j]["v"] > seg[j - 1]["v"] and seg[j]["v"] > seg[j + 1]["v"]):
        return None                                    # must be a genuine local peak
    avg = statistics.mean(seg[k]["v"] for k in range(lo, hi + 1))
    if avg <= 0 or seg[j]["v"] < 1.5 * avg:
        return None
    return j


def scan(seg):
    """Find UHV -> breakout pairs, and record what price did afterwards."""
    found, last = [], -99
    for i in range(CTX + LOOK, len(seg) - FWD):
        if i - last < 10:
            continue
        j = find_uhv(seg, i)
        if j is None:
            continue
        b = seg[i]
        up = b["c"] > seg[j]["h"] and b["c"] > b["o"]
        dn = b["c"] < seg[j]["l"] and b["c"] < b["o"]
        if not (up or dn):
            continue
        side = "buy" if up else "sell"
        entry = b["c"]
        fwd = seg[i + 1:i + 1 + FWD]
        # what the tape did next, in the breakout's own direction
        best = max((x["h"] - entry) if up else (entry - x["l"]) for x in fwd)
        worst = min((x["l"] - entry) if up else (entry - x["h"]) for x in fwd)
        end = (fwd[-1]["c"] - entry) if up else (entry - fwd[-1]["c"])
        found.append(dict(i=i, j=j, side=side, entry=entry,
                          best=best, worst=worst, end=end, seg=seg))
        last = i
    return found


def svg(ev, w=760, h=300):
    """Draw it the way a person would: candles, the UHV circled, the level, the arrow."""
    seg, i, j = ev["seg"], ev["i"], ev["j"]
    a = max(0, j - CTX)
    b = min(len(seg), i + 1 + FWD)
    win = seg[a:b]
    hi = max(x["h"] for x in win)
    lo = min(x["l"] for x in win)
    pad = (hi - lo) * 0.12 or 1
    hi += pad; lo -= pad
    n = len(win)
    cw = w / n

    def X(k): return (k + 0.5) * cw
    def Y(p): return h - (p - lo) / (hi - lo) * h

    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none">']
    lvl = seg[j]["h"] if ev["side"] == "buy" else seg[j]["l"]
    out.append(f'<line x1="0" y1="{Y(lvl):.1f}" x2="{w}" y2="{Y(lvl):.1f}" '
               f'stroke="#f0a020" stroke-width="1.5" stroke-dasharray="6 4"/>')
    out.append(f'<line x1="0" y1="{Y(ev["entry"]):.1f}" x2="{w}" y2="{Y(ev["entry"]):.1f}" '
               f'stroke="#5b8dd9" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>')
    for k, x in enumerate(win):
        gi = a + k
        up = x["c"] >= x["o"]
        col = "#2f9e44" if up else "#e03131"
        if gi == j:
            col = "#f0a020"
        elif gi == i:
            col = "#5b8dd9"
        cx = X(k)
        out.append(f'<line x1="{cx:.1f}" y1="{Y(x["h"]):.1f}" x2="{cx:.1f}" '
                   f'y2="{Y(x["l"]):.1f}" stroke="{col}" stroke-width="1"/>')
        top, bot = Y(max(x["o"], x["c"])), Y(min(x["o"], x["c"]))
        bh = max(1.0, bot - top)
        out.append(f'<rect x="{cx - cw * 0.34:.1f}" y="{top:.1f}" width="{cw * 0.68:.1f}" '
                   f'height="{bh:.1f}" fill="{col}"/>')
        if gi == j:
            out.append(f'<circle cx="{cx:.1f}" cy="{Y(x["h"]) - 9:.1f}" r="7" fill="none" '
                       f'stroke="#f0a020" stroke-width="2"/>')
            out.append(f'<text x="{cx:.1f}" y="{Y(x["h"]) - 20:.1f}" fill="#f0a020" '
                       f'font-size="11" text-anchor="middle">UHV {x["v"]:,}</text>')
        if gi == i:
            ay = Y(x["c"])
            d = -14 if ev["side"] == "buy" else 14
            out.append(f'<path d="M{cx:.1f},{ay + d:.1f} L{cx - 5:.1f},{ay + d * 1.9:.1f} '
                       f'L{cx + 5:.1f},{ay + d * 1.9:.1f} Z" fill="#5b8dd9"/>')
    out.append("</svg>")
    return "".join(out)


def main(open_it=False):
    bars = load()
    segs = segments(bars)
    events = []
    for s in segs:
        events += scan(s)
    if not events:
        print("[review] no UHV breakouts found in the archive yet")
        return

    goes = sum(1 for e in events if e["best"] >= 1.0)
    med_best = statistics.median(e["best"] for e in events)
    med_worst = statistics.median(e["worst"] for e in events)

    cards = []
    for k, e in enumerate(sorted(events, key=lambda x: x["seg"][x["i"]]["t"])):
        ts = datetime.fromtimestamp(e["seg"][e["i"]]["t"], tz=timezone.utc)
        good = e["best"] >= 1.0
        cards.append(f'''<div class="card">
  <div class="hd"><b>#{k+1}</b> <span class="{'buy' if e['side']=='buy' else 'sell'}">
    {e['side'].upper()}</span> {ts:%b %d %H:%M} UTC
    <span class="stat">went <b>{e['best']:+.2f}</b> its way ·
    against <b>{e['worst']:+.2f}</b> · after {FWD}m <b>{e['end']:+.2f}</b></span>
    <span class="verdict {'ok' if good else 'no'}">{'moved' if good else 'did not move'}</span>
  </div>{svg(e)}</div>''')

    html = f'''<meta charset="utf-8"><title>UHV drawings — do you agree?</title>
<style>
 body{{background:#12141a;color:#dfe3ea;font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;padding:22px}}
 h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#8b93a3;margin-bottom:18px}}
 .sum{{background:#1a1d25;border:1px solid #2a2f3a;border-radius:10px;padding:14px 18px;margin-bottom:22px}}
 .sum b{{color:#f0a020}}
 .card{{background:#1a1d25;border:1px solid #2a2f3a;border-radius:10px;margin-bottom:16px;overflow:hidden}}
 .hd{{padding:9px 14px;border-bottom:1px solid #2a2f3a;font-size:13px}}
 .buy{{color:#5b8dd9;font-weight:700}} .sell{{color:#e07b39;font-weight:700}}
 .stat{{color:#8b93a3;margin-left:10px}}
 .verdict{{float:right;font-weight:700}} .ok{{color:#2f9e44}} .no{{color:#e03131}}
 .key{{color:#8b93a3;font-size:13px;margin-bottom:16px}}
 .key i{{font-style:normal;padding:1px 6px;border-radius:4px}}
</style>
<h1>🔍 Every UHV the machine drew — do you agree with the circle?</h1>
<div class="sub">Real archived gold, {len(bars):,} bars ·
 {datetime.fromtimestamp(bars[0]["t"],tz=timezone.utc):%b %d} –
 {datetime.fromtimestamp(bars[-1]["t"],tz=timezone.utc):%b %d} UTC · weekend holes excluded</div>
<div class="key">
 <i style="background:#f0a020;color:#12141a">orange</i> the candle it called the UHV ·
 <i style="background:#5b8dd9;color:#12141a">blue</i> the breakout it entered on ·
 dashed orange = the level that had to break
</div>
<div class="sum">
 <b>{len(events)}</b> UHV breakouts drawn.
 After the break, price moved <b>at least $1.00</b> the right way in
 <b>{goes}</b> of them (<b>{goes/len(events)*100:.0f}%</b>).<br>
 Median best move in its favour <b>${med_best:+.2f}</b> ·
 median worst against <b>${med_worst:+.2f}</b> · window {FWD} minutes.<br>
 <span style="color:#8b93a3">This measures the TAPE, not a trade — no fills, no spread,
 no P&amp;L. It answers only: after a break, does price go?</span>
</div>
{"".join(cards)}'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[review] {len(events)} drawings -> {OUT}")
    print(f"[review] price moved >= $1.00 its way in {goes}/{len(events)} ({goes/len(events)*100:.0f}%)")
    print(f"[review] median best {med_best:+.2f} · median worst {med_worst:+.2f} over {FWD}m")
    if open_it:
        webbrowser.open(OUT.as_uri())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    main(ap.parse_args().open)
