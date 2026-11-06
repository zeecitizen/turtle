"""Lifecycle pages for the PXBT account 1364880 trades of 13-14 Oct 2026 (Zee: "i want to have a lifecycle page for
each of the setups explaining why that particular trade failed to make money ... please leave no stone unturned").
Data: PXBT's own XAUUSDp candles (testing/pxbt_live_M1/M15.csv, dumped from the broker), the account's deals
(PXBT journal on Claude's PC + Zee's statement), the old v1.11's own log on Claude's PC, the full-year MT5 trade
split (testing/saad_trades_tkfull_tagged.csv) and the MT5 fix tests (testing/saad_fix_runs.jsonl).
Writes dashboard/claude_trader/trades/<ticket>.html and trades/review-20261014.html."""
import json, html, math
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
OUT = Path(r"C:\Users\zeesh\turtle\dashboard\claude_trader\trades")
m1 = pd.read_csv(T / "pxbt_live_M1.csv"); m1["t"] = pd.to_datetime(m1.time, format="%Y.%m.%d %H:%M"); m1 = m1.set_index("t")
m15 = pd.read_csv(T / "pxbt_live_M15.csv"); m15["t"] = pd.to_datetime(m15.time, format="%Y.%m.%d %H:%M"); m15 = m15.set_index("t")
FIX = {}
fp = T / "saad_fix_runs.jsonl"
if fp.exists():
    for ln in open(fp):
        r = json.loads(ln); FIX[(r["variant"], r["per"])] = r
YEAR = pd.read_csv(T / "saad_trades_tkfull_tagged.csv")


def pkt(ts):  # server (UTC) -> PKT 12-hour
    t = pd.Timestamp(ts) + pd.Timedelta(hours=5)
    return t.strftime("%I:%M:%S %p").lstrip("0") + (" (next day)" if t.date() != pd.Timestamp(ts).date() else "")


def pkt_short(ts):
    t = pd.Timestamp(ts) + pd.Timedelta(hours=5)
    return t.strftime("%I:%M %p").lstrip("0")


def money(x):
    return ("+" if x > 0 else "−" if x < 0 else "") + "$" + f"{abs(x):,.0f}"


def year_stat(mask):
    g = YEAR[mask]
    return len(g), 100 * (g.net > 0).mean() if len(g) else 0, g.net.sum()


def svg_chart(bars, ema9, ema50, setup_t, levels, entry, exit_, side, step, title_note=""):
    """Inline SVG candles + EMAs (9 blue, 50 red, thick) + levels + entry/exit markers. bars: DataFrame index=time."""
    W, H, L, R, TOP, BOT = 880, 400, 10, 74, 16, 34
    n = len(bars)
    pw = (W - L - R) / max(n, 1)
    vals = list(bars.low) + list(bars.high) + [v for v in levels.values() if v] + [entry[1], exit_[1]]
    vals += [v for v in ema9 if not math.isnan(v)] + [v for v in ema50 if not math.isnan(v)]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 + 0.2; lo -= pad; hi += pad
    y = lambda p: TOP + (hi - p) / (hi - lo) * (H - TOP - BOT)
    x = lambda i: L + (i + 0.5) * pw
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="price chart" class="chart">']
    # grid + price labels
    stepv = [0.5, 1, 2, 5, 10][min(4, sum((hi - lo) > k for k in (4, 9, 22, 45)))]
    p = math.ceil(lo / stepv) * stepv
    while p < hi:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(p):.1f}" y2="{y(p):.1f}" class="grid"/><text x="{W - R + 6}" y="{y(p) + 4:.1f}" class="ax">{p:.0f}</text>' if stepv >= 1 else
                   f'<line x1="{L}" x2="{W - R}" y1="{y(p):.1f}" y2="{y(p):.1f}" class="grid"/><text x="{W - R + 6}" y="{y(p) + 4:.1f}" class="ax">{p:.1f}</text>')
        p += stepv
    idx = list(bars.index)
    if setup_t in idx:
        i = idx.index(setup_t)
        out.append(f'<rect x="{x(i) - pw * 0.55:.1f}" y="{TOP}" width="{pw * 1.1:.1f}" height="{H - TOP - BOT}" class="setupbg"/>')
        out.append(f'<text x="{x(i):.1f}" y="{TOP + 11}" class="lbl" text-anchor="middle">setup</text>')
    for i, (t, b) in enumerate(bars.iterrows()):
        up = b.close >= b.open
        out.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(b.high):.1f}" y2="{y(b.low):.1f}" class="{"wu" if up else "wd"}"/>')
        top, bot = y(max(b.open, b.close)), y(min(b.open, b.close))
        out.append(f'<rect x="{x(i) - pw * 0.34:.1f}" y="{top:.1f}" width="{pw * 0.68:.1f}" height="{max(bot - top, 0.8):.1f}" class="{"cu" if up else "cd"}"/>')
        if i % max(1, n // 8) == 0:
            out.append(f'<text x="{x(i):.1f}" y="{H - 12}" class="ax" text-anchor="middle">{pkt_short(t)}</text>')
    for arr, cls in ((ema50, "e50"), (ema9, "e9")):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(arr) if not math.isnan(v))
        out.append(f'<polyline points="{pts}" class="{cls}" fill="none"/>')
    names = {"stop": ("sl", "stop"), "tp1": ("tp", "TP1"), "ctc": ("ctc", "75% → breakeven"), "entry": ("en", "entry")}
    for k, v in levels.items():
        if not v: continue
        cls, nm = names[k]
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{cls}"/><text x="{L + 4}" y="{y(v) - 4:.1f}" class="lbl {cls}t">{nm} {v:.2f}</text>')

    def bar_of(ts):
        ts = pd.Timestamp(ts).floor(step)
        return idx.index(ts) if ts in idx else None
    ei, xi = bar_of(entry[0]), bar_of(exit_[0])
    if ei is not None:
        yy = y(entry[1]); d = 1 if side > 0 else -1
        out.append(f'<path d="M{x(ei):.1f},{yy:.1f} l-7,{12 * d} l14,0 z" class="mk en"/>')
    if xi is not None:
        yy = y(exit_[1])
        out.append(f'<path d="M{x(xi) - 6:.1f},{yy - 6:.1f} l12,12 M{x(xi) + 6:.1f},{yy - 6:.1f} l-12,12" class="mkx"/>')
    out.append('</svg>')
    legend = ('<div class="legend"><span class="k e9k"></span>EMA 9 (M15)<span class="k e50k"></span>EMA 50 (M15)'
              '<span class="k enk"></span>entry ▲▼<span class="k slk"></span>stop<span class="k tpk"></span>TP1<span class="k ctck"></span>breakeven trigger'
              '<span class="k xk"></span>exit ✕' + (f' · {title_note}' if title_note else '') + '</div>')
    return "\n".join(out) + legend


CSS = open(OUT / "67046250.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
CSS += """
.chart { width: 100%; height: auto; display: block; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; }
.chart .grid { stroke: var(--line); stroke-width: 1; }
.chart .ax { fill: var(--muted); font: 11px var(--mono); }
.chart .lbl { fill: var(--muted); font: 700 11px var(--mono); }
.chart .wu, .chart .wd { stroke-width: 1.2; } .chart .wu { stroke: var(--green); } .chart .wd { stroke: var(--red); }
.chart .cu { fill: var(--green); } .chart .cd { fill: var(--red); }
.chart .e9 { stroke: #2f6fd6; stroke-width: 3; } .chart .e50 { stroke: #d23b4b; stroke-width: 3; opacity: .85; }
.chart .sl { stroke: var(--red); stroke-width: 1.5; stroke-dasharray: 6 4; } .chart .slt { fill: var(--red); }
.chart .tp { stroke: var(--green); stroke-width: 1.5; stroke-dasharray: 6 4; } .chart .tpt { fill: var(--green); }
.chart .ctc { stroke: var(--amber); stroke-width: 1.2; stroke-dasharray: 2 4; } .chart .ctct { fill: var(--amber); }
.chart .en { stroke: var(--gold); stroke-width: 1.2; stroke-dasharray: 3 3; } .chart .ent { fill: var(--gold); }
.chart path.mk.en { fill: var(--gold); stroke: none; } .chart .mkx { stroke: var(--ink); stroke-width: 3; fill: none; }
.chart .setupbg { fill: var(--gold); opacity: .12; }
.legend { font-size: 12.5px; color: var(--muted); margin: 6px 2px 0; display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; }
.legend .k { display: inline-block; width: 18px; height: 4px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
.e9k { background: #2f6fd6; } .e50k { background: #d23b4b; } .enk { background: var(--gold); } .slk { background: var(--red); } .tpk { background: var(--green); } .ctck { background: var(--amber); } .xk { background: var(--ink); }
.neg { color: var(--red); font-weight: 700; } .strip b.neg { color: var(--red); }
.verdict { border-left: 4px solid var(--red); } .good { border-left: 4px solid var(--green); }
"""


def page(t, title_sub, strip, chart, rows, whys, year_html, prevent_html, notes_html=""):
    rows_html = "\n".join(f'<tr><td class="t">{a}</td><td class="t">{b}</td><td>{c}</td><td class="n">{d}</td><td class="n">{e}</td></tr>' for a, b, c, d, e in rows)
    strip_html = "".join(f'<div><span>{k}</span><b class="{c}">{v}</b></div>' for k, v, c in strip)
    whys_html = "\n".join(f'<div class="card {c}"><h3>{h}</h3>{b}</div>' for h, b, c in whys)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Trade {t["ticket"]}</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;800&family=Share+Tech+Mono&family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="eyebrow">PrimeXBT demo · account 1364880 · XAUUSDp · {t["day"]} · <a href="/saad-review">all trades of 13–14 Oct</a></div>
    <h1>Trade {t["ticket"]}</h1>
    <p class="sub">{title_sub}</p>
    <div class="strip">{strip_html}</div>
  </div>

  <h2>The chart (PrimeXBT's own candles)</h2>
  {chart}

  <h2>Lifecycle</h2>
  <p class="sub">PKT = Pakistan time; server = PrimeXBT's clock (UTC). Sources below.</p>
  <div class="tw"><table>
    <thead><tr><th>PKT</th><th>Server</th><th>What happened</th><th>Stop</th><th>Result</th></tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table></div>

  <h2>Why it didn't make money</h2>
{whys_html}

  <h2>One-off or a pattern? The full-year check</h2>
{year_html}

  <h2>What would have prevented it</h2>
{prevent_html}
{notes_html}
  <footer>Sources: PrimeXBT's XAUUSDp 1-minute and 15-minute candles for 12–14 Oct (downloaded from the broker), the account's deals (PrimeXBT journal on Claude's PC, matching Zee's statement), the EA's rules (Saad_strategy_15min v1.17, <code>lifecycle.md</code>) and its own target code, and the full-year MT5 test of the same EA on Axi real ticks. The trading machine's own Experts log was not available, so the EA's decisions are reconstructed from its rules; the same reconstruction gives TP1 = 4150.75 for trade 67046250, exactly what that EA logged. <a href="/saad-review">All trades of 13–14 Oct</a> · <a href="/">Dashboard</a></footer>
</div>
</body>
</html>"""


def window(bars, a, b):
    return bars[(bars.index >= a) & (bars.index <= b)]


def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def fixline(var, label):
    b, f = FIX.get(("base", "full")), FIX.get((var, "full"))
    bj, fj, bo, fo = FIX.get(("base", "tune")), FIX.get((var, "tune")), FIX.get(("base", "julo")), FIX.get((var, "julo"))
    if not (b and f):
        return f"<p><b>{label}:</b> MT5 test pending.</p>"
    s = f"<p><b>{label}</b> (MT5, full year, Axi real ticks, 1 lot): net <b>{money(f['net'])}</b> vs {money(b['net'])} today's rules"
    if bj and fj and bo and fo:
        s += f"; Jan–Jun {money(fj['net'])} vs {money(bj['net'])}; Jul–Oct {money(fo['net'])} vs {money(bo['net'])}"
    s += f"; max drawdown {f['dd']} vs {b['dd']}.</p>"
    return s


SIZE_CARD = ("The size: 2 lots on a $10,000 account",
             "<p>Over the full year (MT5, 1 lot) this EA had <b>27 losing streaks of 4+ trades</b> (longest: 11), <b>29 of 184 trading days as bad as yesterday</b>, a worst day of −$3,782 and a worst drawdown of $12,681. At <b>2 lots</b> those become a worst day of −$7,563 and a drawdown of <b>$25,361 — 254% of a $10,000 account</b>. Every stop here cost $1,500–2,200 (15–22% of the account). The strategy is profitable over the year, but at this size its ordinary bad stretches empty the account first.</p>", "warn")

TR = {}


def base_rows(*rows):
    return list(rows)


# ---------------------------------------------------------------- 67099697
t = dict(ticket=67099697, day="13 Oct 2026")
b = window(m15, pd.Timestamp("2026-10-13 15:30"), pd.Timestamp("2026-10-13 23:45"))
TR[67099697] = page(t,
    "A 2-lot BUY by Saad_strategy_15min v1.17: a pin bar bounced off the 9 EMA while the 15-minute trend was still down. Gold never got near the target, and the EA's own daily-close rule shut the trade at a small loss.",
    [("Direction", "BUY 2 lots", ""), ("Entry", "4162.51", ""), ("First stop", "4154.20", ""), ("Target (TP1)", "≈ 4169.87", ""), ("Duration", "2 h 9 min", ""), ("Result", "−$424", "neg")],
    svg_chart(b, list(b.ema9), list(b.ema50), pd.Timestamp("2026-10-13 18:30"), {"entry": 4162.51, "stop": 4154.20, "tp1": 4169.87, "ctc": 4168.03},
              ("2026-10-13 18:45:34", 4162.51), ("2026-10-13 20:55:01", 4160.39), 1, "15min"),
    [("11:45 PM", "18:45", "<b>Setup</b> (the 18:30 candle, closed 18:45): a <b>PIN BAR with a long lower wick on the 9 EMA</b> (4157.94): high 4162.06, low 4157.70, range $4.36 = 0.72 × ATR. The 50 EMA (4169.87) is <b>above</b>, so the EA's exit EMA is the 50 → TP1 = the price touching the 50 EMA. Chop (ER) 0.138, just over the 0.11 limit.", "–", ""),
     ("11:45:34 PM", "18:45:34", "Price breaks the candle's high + 2 pips (4162.26) → <b>BUY 2 lots filled at 4162.51</b>. Stop 35 pips under the candle's low: <b>4154.20</b> → risk <b>$1,662</b>. TP1 ≈ <b>4169.87</b> (+$7.36); the stop moves to the entry at 75% of the way, <b>4168.03</b>.", "4154.20", ""),
     ("12:50 AM", "19:50", "Best moment: <b>4166.45 (+$3.94)</b>. Only about half way to TP1; the 75% breakeven level was never reached.", "4154.20", "+$788 open"),
     ("12:50 – 1:55 AM", "19:50 – 20:55", "Gold drifts back down under the entry; low 4157.46 at 20:34 (−$5.05). The 15-minute candles keep closing <b>below the 50 EMA</b>.", "4154.20", ""),
     ("1:55:01 AM", "20:55:01", "<b>Daily-close rule:</b> 3–4 minutes before PrimeXBT's daily break (20:59 server), the EA closes any trade that is in loss. <b>Closed at 4160.39</b>.", "", "<span class='neg'>−$424</span>")],
    [("1. A buy against the 15-minute trend, in chop",
      "<p>At the setup the <b>9 EMA (4157.94) was $11.93 under the 50 EMA (4169.87)</b>: the 15-minute trend was down, and gold had fallen $5.63 over the previous four hours. The efficiency ratio was 0.138 — the market was moving sideways. The pin bar was a bounce inside a falling market, and the bounce stopped at +$3.94.</p>", "verdict"),
     ("2. The target was far for the move available",
      "<p>TP1 was the 50 EMA, $7.36 away, about 1.2 × the 15-minute ATR ($6.04). The best the bounce managed was $3.94. The 75% breakeven step needed $5.52, so the trade stayed at full risk the whole time.</p>", "verdict"),
     ("3. The daily-close rule decided the exit",
      "<p>The trade was −$2.12 four minutes before the daily break, so the EA closed it (it shuts losing trades before the break, keeps winners). The stop at 4154.20 was never touched: after the break gold dipped to 4154.76 (00:00 server) — 56 cents above this stop — and then rallied to 4168.69 by 03:00. Holding through the break would have meant sitting through that dip at full 2-lot risk; the rule chose a known −$424.</p>", ""),
     SIZE_CARD],
    f"""<div class="card"><p>Same EA, same rules, full year (Jan 6 – Oct 8 2026, MT5, Axi real ticks, 1 lot):</p><ul>
<li><b>BUYs against the 15-minute trend</b> (9 EMA under the 50 at the setup): {year_stat((YEAR.long) & (~YEAR.with_trend))[0]} trades, {year_stat((YEAR.long) & (~YEAR.with_trend))[1]:.0f}% won, <b>{money(year_stat((YEAR.long) & (~YEAR.with_trend))[2])}</b>. Profitable — this is where the strategy catches turns.</li>
<li><b>Setups with chop under 0.15</b>: {year_stat(YEAR.er < 0.15)[0]} trades, {year_stat(YEAR.er < 0.15)[1]:.0f}% won, <b>{money(year_stat(YEAR.er < 0.15)[2])}</b>.</li>
<li><b>Trades shut by the daily-close rule</b>: {year_stat(YEAR.exit_reason.str.contains('day close'))[0]} trades, total {money(year_stat(YEAR.exit_reason.str.contains('day close'))[2])}.</li></ul>
<p><b>So this was a normal losing trade of a profitable kind of setup</b>, not a broken rule. Report.md §10 measured the obvious fix — buy only with the trend — and it cut the year's profit by about three quarters.</p></div>""",
    f"""<div class="card"><p>No rule change would have saved this trade without costing more elsewhere (trend filters: report.md §10). What would have shrunk it: <b>the size</b> — at the designed 1 lot per $25,000 (0.4 lots on this account) this loss would have been about −$85.</p></div>""")

# ---------------------------------------------------------------- 67111138
t = dict(ticket=67111138, day="13 Oct 2026")
b = window(m15, pd.Timestamp("2026-10-13 18:00"), pd.Timestamp("2026-10-14 01:00"))
gap = FIX.get(("gapfix", "full"))
TR[67111138] = page(t,
    "A 2-lot BUY taken at the market's reopen from a setup candle formed before the daily break — a hole in the EA's gap protection. It never moved more than 51 cents our way, and the stop was hit at the exact low of the night before gold rallied $8.83.",
    [("Direction", "BUY 2 lots", ""), ("Entry", "4162.39", ""), ("First stop", "4154.77", ""), ("Target (TP1)", "≈ 4167.2", ""), ("Duration", "1 h 57 min", ""), ("Result", "−$1,524", "neg")],
    svg_chart(b, list(b.ema9), list(b.ema50), pd.Timestamp("2026-10-13 20:45"), {"entry": 4162.39, "stop": 4154.77, "tp1": 4167.23, "ctc": 4166.02},
              ("2026-10-13 22:01:49", 4162.39), ("2026-10-13 23:58:51", 4154.77), 1, "15min", "the gap between 20:45 and 22:00 = the daily break"),
    [("1:45 – 2:00 AM", "20:45 – 21:00", "<b>Setup</b>: the <b>last 15-minute candle before PrimeXBT's daily break</b> (20:45): a <b>GREEN MARUBOZU on the 9 EMA</b> (4160.91): high 4162.03, low 4158.27. Exit EMA = the 50 (4167.52), above → TP1 = touching the 50 EMA. Chop 0.187.", "–", ""),
     ("2:00 – 3:00 AM", "21:00 – 22:00", "<b>Market closed</b> (daily break). The candle closed at the break, so the EA only saw it when trading resumed.", "–", ""),
     ("3:01:49 AM", "22:01:49", "First minute after the reopen: price is above the setup's high + 2 pips (4162.23) → <b>BUY 2 lots filled at 4162.39</b>. Stop 35 pips under the setup candle's low: <b>4154.77</b> → risk <b>$1,524</b>. TP1 ≈ 4167.2 (the 50 EMA, sloping down).", "4154.77", ""),
     ("3:52 AM", "22:52", "Best moment: <b>4162.90 — only +$0.51</b>.", "4154.77", "+$102 open"),
     ("4:00 – 4:58 AM", "23:00 – 23:58", "Gold slides: candles close 4157.90, 4156.30, 4155.65, 4155.11 — making a cluster of lows at 4155.06 / 4155.48 just above the stop.", "4154.77", ""),
     ("4:58:51 AM", "23:58:51", "<b>Stop hit at 4154.77</b> — the exact low of the night, to the cent.", "", "<span class='neg'>−$1,524</span>"),
     ("5:00 – 5:15 AM", "00:00 – 00:15", "Gold rallies <b>$8.83</b> in one 15-minute candle (4154.76 → 4163.60), back above the entry.", "", "")],
    [("1. A hole in the EA's gap protection (a real bug)",
      "<p><code>InpGapCancel</code> is meant to drop a waiting setup when the market closes before it can trigger. In the code, at each new candle the EA first cancels a <i>waiting</i> setup if there was a gap, and only <b>then</b> looks for a new setup on the candle that just closed. At the reopen, the candle that just closed is the last one before the break — so a setup from it is created <b>after</b> the gap check, and its break is traded on the reopen candle, across the closure. The same thing can happen every daily reopen and every Monday open.</p>", "verdict"),
     ("2. Bought into a fading, choppy market",
      "<p>The 9 EMA (4160.91) was $6.61 under the 50 (4167.52): the 15-minute trend was down. The reopen hour is thin (tick volume 1,381 vs 1,764–4,442 in the candles before the break). The trade never got more than 51 cents in profit.</p>", "verdict"),
     ("3. The stop sat where stops get hunted",
      "<p>The stop (4154.77) was just under the night's cluster of lows (4155.06, 4155.48). Price took exactly that level and then reversed $8.83 within 15 minutes — a classic sweep of the stops under the lows. The EA's 35-pip stop is mechanical (candle low − $3.50), so it can't avoid such levels.</p>", ""),
     SIZE_CARD],
    f"""<div class="card"><p>On Axi's full year this gap case happened only <b>{int(year_stat(YEAR.gap_entry)[0])} times</b> ({money(year_stat(YEAR.gap_entry)[2])} in total) — Axi's break falls at a different hour than PrimeXBT's. So it's rare, but it's a genuine hole: the EA does something its own setting says it shouldn't.</p></div>""",
    f"""<div class="card"><p><b>Fix the gap hole</b>: don't create a setup from the last candle before a market closure. Built and tested as <code>Saad_gapfix.mq5</code>.</p>{fixline('gapfix', 'Gap fix')}<p>On Axi's year it removes just two trades, and one of them was a big winner, so it costs $861 (Jul–Oct unchanged). It makes the EA do what its own setting promises, but it is <b>not a profit fix</b>. Your call whether to ship it; I'd keep it as an option.</p></div>""")

# ---------------------------------------------------------------- 67117659
t = dict(ticket=67117659, day="14 Oct 2026")
b = window(m15, pd.Timestamp("2026-10-13 21:45"), pd.Timestamp("2026-10-14 02:15"))
TR[67117659] = page(t,
    "A 2-lot SELL that did almost everything right: it reached the 75% point (stop moved to entry) and came within 66 cents of its target — then gold jumped $14 in nine minutes and stopped it out at exactly breakeven.",
    [("Direction", "SELL 2 lots", ""), ("Entry", "4157.62", ""), ("First stop", "4166.76", ""), ("Target (TP1)", "4146.92", ""), ("Duration", "51 min", ""), ("Result", "$0", "")],
    svg_chart(b, list(b.ema9), list(b.ema50), pd.Timestamp("2026-10-14 00:15"), {"entry": 4157.62, "stop": 4166.76, "tp1": 4146.92, "ctc": 4149.60},
              ("2026-10-14 00:33:08", 4157.62), ("2026-10-14 01:23:49", 4157.62), -1, "15min"),
    [("5:15 – 5:30 AM", "00:15 – 00:30", "<b>Setup</b>: the 00:15 candle is a <b>PIN BAR on the 9 EMA</b> (4159.32) with a long <i>lower</i> wick that <b>closed red</b> (open 4162.89, close 4160.58; high 4163.26, low 4157.86). The EA's rule: a pin on the 9 EMA that closes red is a SELL. Chop 0.165.", "–", ""),
     ("5:33:08 AM", "00:33:08", "Price breaks the low − 2 pips (4157.66) → <b>SELL 2 lots at 4157.62</b>. Stop 35 pips above the high: <b>4166.76</b> → risk <b>$1,828</b>. TP1 = the last support, <b>4146.92</b> (the 17:45 swing low, $10.70 away); breakeven at 75% = <b>4149.60</b>.", "4166.76", ""),
     ("5:35 AM", "00:35", "First a squeeze against the trade to 4161.10 (−$3.48).", "4166.76", ""),
     ("6:16 – 6:17 AM", "01:16 – 01:17", "Gold falls to <b>4147.58 (+$10.04)</b>. The 75% level (4149.60) is passed → <b>stop to the entry, 4157.62</b>. TP1 (4146.92) is <b>66 cents away</b>.", "4157.62", "+$2,008 open"),
     ("6:17 – 6:23 AM", "01:17 – 01:23", "<b>Gold jumps $11.40 in six minutes</b> (4147.58 → 4158.98).", "4157.62", ""),
     ("6:23:49 AM", "01:23:49", "<b>Breakeven stop hit at 4157.62.</b> The rally carried on to 4162.69 at 01:26 and 4168.69 by 03:00.", "", "$0")],
    [("1. 66 cents short of the target",
      "<p>Had gold touched 4146.92, the EA would have banked half the position (+$1,070) and trailed the rest. The low was 4147.58. The support level itself (the 17:45 swing low) attracted buyers just above it — a common pattern: the bounce starts a little before the level.</p>", ""),
     ("2. A conflicting setup candle",
      "<p>The setup was a pin bar with a long <b>lower</b> wick — buyers rejecting lower prices — traded as a SELL because it closed red. The EA's rules allow it (the EMA and the close decide the side), but the wick told the opposite story, and the next hours rallied hard.</p>", ""),
     ("3. The breakeven step did its job",
      "<p>Without the 75% breakeven step this trade would have gone back to its full stop (4166.76): gold reached 4168.69 by 03:00, which would have been −$1,828. The rule turned a likely full loss into $0.</p>", "good")],
    f"""<div class="card"><p>Over the full year, trades that reached the 75% breakeven level but not TP1 end at about $0 by design. This was the EA working as designed on a day the move reversed just before the target.</p></div>""",
    """<div class="card"><p>Nothing to fix here — the trade risked $1,828 and lost nothing. A closer target would have banked a profit on this trade, but report.md §12 tested earlier/partial exits and they cost more than they saved over the year.</p></div>""")

# ---------------------------------------------------------------- 67138222
t = dict(ticket=67138222, day="14 Oct 2026")
b = window(m15, pd.Timestamp("2026-10-13 23:45"), pd.Timestamp("2026-10-14 05:00"))
n50 = year_stat((YEAR.long) & (YEAR.on50))
TR[67138222] = page(t,
    "A 2-lot BUY from the EA's weakest setup — a pin bar on the 50 EMA — bought after a sharp rally in a still-falling 15-minute trend, with no real target. It went 1.37 dollars our way and then fell $11 to the stop.",
    [("Direction", "BUY 2 lots", ""), ("Entry", "4169.02", ""), ("First stop", "4158.12", ""), ("Target (TP1)", "none (trail)", ""), ("Duration", "50 min", ""), ("Result", "−$2,200", "neg")],
    svg_chart(b, list(b.ema9), list(b.ema50), pd.Timestamp("2026-10-14 03:00"), {"entry": 4169.02, "stop": 4158.12},
              ("2026-10-14 03:16:49", 4169.02), ("2026-10-14 04:06:51", 4158.02), 1, "15min"),
    [("8:00 – 8:15 AM", "03:00 – 03:15", "<b>Setup</b>: a <b>PIN BAR with a long lower wick on the 50 EMA</b> (4162.78): open 4167.80, high 4168.69, low 4161.62, close 4167.78 — range $7.07 = 0.80 × ATR ($8.79, a volatile hour). It did <b>not</b> touch the 9 EMA (4161.46). Rule: a long on the 50 EMA exits at the 9 EMA — which is <b>below</b> the entry, so <b>no TP1</b>: the EA trails 2 × ATR from the second candle (\"path B\"). Chop 0.129.", "–", ""),
     ("8:16:49 AM", "03:16:49", "Break of the high + 2 pips (4168.89) → <b>BUY 2 lots at 4169.02</b>. Stop 35 pips under the low: <b>4158.12</b> → risk <b>$2,180</b> — the biggest of the day.", "4158.12", ""),
     ("8:17 AM", "03:17", "Best moment: <b>4170.39 (+$1.37)</b> — one minute after entry.", "4158.12", "+$274 open"),
     ("8:17 – 9:06 AM", "03:17 – 04:06", "Gold falls straight back through the setup candle and both EMAs.", "4158.12", ""),
     ("9:06:51 AM", "04:06:51", "<b>Stop hit, filled at 4158.02</b> (10 cents of slippage).", "", "<span class='neg'>−$2,200</span>")],
    [("1. The setup type that loses money over the year",
      f"<p>A BUY on the <b>50</b> EMA (Saad's \"inverse\" long). Over the full year this setup made <b>{n50[0]} trades, won {n50[1]:.0f}%, and lost {money(n50[2])}</b> in total, while the 9-EMA longs made money. This trade is the textbook case.</p>", "verdict"),
     ("2. Bought the top of a rally, against the trend",
      "<p>Gold had just rallied $11.48 over four hours (from 4154.76 to the high 4168.69), but the 15-minute 9 EMA (4161.46) was still under the 50 (4162.78). The entry at 4169.02 was above the candle's high, right at the top of the move, in the most volatile hour of the night (ATR $8.79).</p>", "verdict"),
     ("3. No target, the widest stop",
      "<p>With the exit EMA below the entry, the trade had no TP1 and no 75% breakeven step — only a trail that starts on the second candle. And because the candle was big, the stop was $10.90 away: $2,180 at 2 lots.</p>", ""),
     SIZE_CARD],
    f"""<div class="card"><ul><li><b>BUYs on the 50 EMA</b>, full year: {n50[0]} trades, {n50[1]:.0f}% won, <b>{money(n50[2])}</b>.</li>
<li><b>BUYs on the 9 EMA</b>, full year: {year_stat((YEAR.long) & (~YEAR.on50))[0]} trades, {year_stat((YEAR.long) & (~YEAR.on50))[1]:.0f}% won, <b>{money(year_stat((YEAR.long) & (~YEAR.on50))[2])}</b>.</li></ul></div>""",
    f"""<div class="card"><p><b>Tested and rejected:</b> switching off the BUYs on the 50 EMA (<code>InpLongRule = 0</code>, a setting that already exists).</p>{fixline('no50long', 'No 50-EMA buys')}<p>Worse in <b>both</b> halves. On their own those trades lose a little, but when they're blocked the EA takes other setups in their place, and those do worse. So the category stays. What would have shrunk this loss is the size: at 0.2 lots on this account it would have been about −$220.</p></div>""")

# ---------------------------------------------------------------- 67144848
t = dict(ticket=67144848, day="14 Oct 2026")
b = window(m15, pd.Timestamp("2026-10-14 01:30"), pd.Timestamp("2026-10-14 06:30"))
TR[67144848] = page(t,
    "A 2-lot BUY on a green candle that touched both EMAs at once — the two lines had merged, so there was no trend at all, and the chop reading was exactly at the EA's limit. It went 37 cents our way and fell $9 to the stop.",
    [("Direction", "BUY 2 lots", ""), ("Entry", "4166.69", ""), ("First stop", "4157.65", ""), ("Target (TP1)", "none (trail)", ""), ("Duration", "43 min", ""), ("Result", "−$1,812", "neg")],
    svg_chart(b, list(b.ema9), list(b.ema50), pd.Timestamp("2026-10-14 04:30"), {"entry": 4166.69, "stop": 4157.65},
              ("2026-10-14 04:45:08", 4166.69), ("2026-10-14 05:28:33", 4157.63), 1, "15min"),
    [("9:30 – 9:45 AM", "04:30 – 04:45", "<b>Setup</b>: a <b>GREEN MARUBOZU</b> (open 4161.31, close 4165.99, high 4166.30, low 4161.15) that touched <b>both</b> EMAs — 9 EMA 4162.17 and 50 EMA 4162.70, only 53 cents apart. Chop <b>0.111</b> — the EA's limit is 0.11. Exit EMA (the 50) is below the entry → <b>no TP1</b>, trail from candle 2.", "–", ""),
     ("9:45:08 AM", "04:45:08", "Break of the high + 2 pips (4166.50) → <b>BUY 2 lots at 4166.69</b>. Stop 35 pips under the low: <b>4157.65</b> → risk <b>$1,808</b>.", "4157.65", ""),
     ("9:54 AM", "04:54", "Best moment: <b>4167.06 (+$0.37)</b>.", "4157.65", "+$74 open"),
     ("9:54 – 10:28 AM", "04:54 – 05:28", "Gold falls back through the candle and both EMAs.", "4157.65", ""),
     ("10:28:33 AM", "05:28:33", "<b>Stop hit, filled at 4157.63.</b>", "", "<span class='neg'>−$1,812</span>")],
    [("1. No trend at all",
      "<p>The 9 and 50 EMAs were 53 cents apart — flat and tangled. The EA's whole idea is a rejection off an EMA <i>in a move</i>; here there was no move to rejoin. The chop reading (0.111) passed the 0.11 limit by a hair.</p>", "verdict"),
     ("2. The second buy in 90 minutes at the same area",
      "<p>67138222 had been stopped out from 4169 at 04:06. This trade bought 4166.69 forty minutes later, into the same overhead area, and failed the same way. The EA has a cooldown setting after a loss (<code>InpCoolBars</code>), but it's off by default.</p>", ""),
     ("3. No target",
      "<p>As in 67138222: exit EMA below the entry, so no TP1 and no breakeven step — the trade could only be saved by a trail that starts a candle later.</p>", ""),
     SIZE_CARD],
    f"""<div class="card"><p>Full year: setups with chop under 0.15 made {year_stat(YEAR.er < 0.15)[0]} trades and {money(year_stat(YEAR.er < 0.15)[2])} — low chop is not a losing category on its own. BUYs with no TP1 (\"path B\"): {year_stat(YEAR.pathB)[0]} trades, {year_stat(YEAR.pathB)[1]:.0f}% won, <b>{money(year_stat(YEAR.pathB)[2])}</b> — they win less often but their winners run far.</p></div>""",
    """<div class="card"><p>No single tested rule removes this kind of trade without costing more over the year (report.md §10, §12). The honest lever is <b>the size</b>: at the designed 0.4 lots for this account the loss would have been about −$362.</p></div>""")

# ---------------------------------------------------------------- 67082390 (the v1.11 copy on Claude's PC)
t = dict(ticket=67082390, day="13 Oct 2026")
w = m1[(m1.index >= pd.Timestamp("2026-10-13 15:40")) & (m1.index <= pd.Timestamp("2026-10-13 17:45"))]
e9m, e50m = ema(w.close, 9), ema(w.close, 50)
b = w[w.index >= pd.Timestamp("2026-10-13 17:00")]
TR[67082390] = page(t,
    "Not the real EA: an old v1.11 copy on Claude's PC, running on a 1-MINUTE chart by mistake, took this 0.1-lot BUY from a 48-cent \"marubozu\". It was closed by hand two minutes later and the copy was removed.",
    [("Direction", "BUY 0.1 lots", ""), ("Entry", "4156.63", ""), ("First stop", "4152.76", ""), ("Target (TP1)", "4157.89", ""), ("Duration", "1 min 48 s", ""), ("Result", "−$4.10", "neg")],
    svg_chart(b, list(e9m[b.index]), list(e50m[b.index]), pd.Timestamp("2026-10-13 17:22"), {"entry": 4156.63, "stop": 4152.76, "tp1": 4157.89},
              ("2026-10-13 17:23:13", 4156.63), ("2026-10-13 17:25:01", 4156.22), 1, "1min", "1-minute candles; EMAs on 1-minute here, as the v1.11 copy saw them"),
    [("10:16:51 PM", "17:16:51", "On Claude's PC the chart running the old <b>Saad v1.11</b> is switched to <b>M1</b>; the EA restarts on 1-minute candles (its log: \"Saad_strategy_15min (XAUUSDp,M1)\").", "–", ""),
     ("10:20 – 10:23 PM", "17:20 – 17:23", "It now treats 1-minute candles as setups: 4 setups in 3 minutes, each with a range of 50–90 cents.", "–", ""),
     ("10:23:13 PM", "17:23:13", "<b>BUY 0.10 at 4156.63</b> off the 17:22 one-minute GREEN MARUBOZU (range $0.48). v1.11's settings: stop 30 pips → <b>4152.76</b>; TP1 = next resistance 4157.89.", "4152.76", ""),
     ("10:24:59 PM", "17:24:59", "\"One click trading has been enabled\" in that terminal.", "4152.76", ""),
     ("10:25:01 PM", "17:25:01", "<b>Closed at 4156.22</b> two seconds later — a manual close (the EA logged it as \"closed\", not a stop).", "", "<span class='neg'>−$4.10</span>"),
     ("10:25:14 PM", "17:25:14", "The v1.11 copy is <b>removed</b> from the chart.", "", "")],
    [("1. The wrong chart and the wrong version",
      "<p>The 15-minute strategy ran on 1-minute candles, where its rules have no edge (report.md §5, §35: on M1 spread and noise eat everything). And it was v1.11 — six versions old, with the 30-pip stop and the broken long rule that v1.12 fixed.</p>", "verdict"),
     ("2. Two copies on one account",
      "<p>This copy shared magic number 88302 with the real EA on the trading machine. Earlier the same day it also tried to move the stop of trade 67046250 (blocked while Algo Trading was off). Two copies with one magic number can adopt and manage each other's trades.</p>", "verdict")],
    """<div class="card"><p>Not applicable — this wasn't the strategy's decision.</p></div>""",
    """<div class="card good"><p><b>One EA per account, with its own magic number.</b> The v1.11 copy is now gone from Claude's PC (its last line is the 22:25 removal; nothing since). Keep the 15-minute EA on M15 charts only.</p></div>""")

for tk, h in TR.items():
    (OUT / f"{tk}.html").write_text(h, encoding="utf-8")
    print("wrote", tk)
