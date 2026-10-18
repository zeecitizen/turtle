"""task4_examples.py - Task 4: draw real 1-min trades (MT5, Blueberry ticks) on their candles as SVG, so the failing months can be
"scrolled" even though TradingView keeps only ~1 week of 1-minute history. Candles = MT5's own Blueberry M1 bars (bb_bars.py)."""
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bb_bars  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "saad_strategy_1min_optimized" / "optimizer_results" / "task4_examples"
OUT.mkdir(parents=True, exist_ok=True)
COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"


def ema(vals, n):
    k, e, out = 2 / (n + 1), None, []
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def svg(trade, title, path, before=45, after=25):
    t_in = bb_bars.srv_to_utc(trade["in"]).replace(second=0)
    t_out = bb_bars.srv_to_utc(trade["out"]).replace(second=0)
    day = t_in.strftime("%Y-%m-%d")
    bars = bb_bars.bars((t_in - timedelta(days=1)).strftime("%Y-%m-%d"), day)
    idx = {datetime.utcfromtimestamp(b[0]): i for i, b in enumerate(bars)}
    i_in = idx.get(t_in)
    if i_in is None:
        return False
    i_out = idx.get(t_out, min(len(bars) - 1, i_in + 5))
    closes = [b[4] for b in bars]
    e3, e6 = ema(closes, 3), ema(closes, 6)
    a, z = max(0, i_in - before), min(len(bars), max(i_out, i_in) + after)
    seg = bars[a:z]
    lo = min(min(b[3] for b in seg), trade["sl"], trade["tp"]) - 0.5
    hi = max(max(b[2] for b in seg), trade["sl"], trade["tp"]) + 0.5
    W, H, L, R, T, B = 900, 420, 50, 120, 40, 30
    x = lambda i: L + (i - a + 0.5) * (W - L - R) / (z - a)
    y = lambda p: T + (hi - p) / (hi - lo) * (H - T - B)
    cw = max(2, (W - L - R) / (z - a) * 0.6)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Segoe UI, sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>', f'<text x="{L}" y="22" font-size="14" font-weight="600" fill="#1b1f24">{title}</text>']
    for k in range(5):
        p = lo + (hi - lo) * k / 4
        s.append(f'<line x1="{L}" x2="{W - R}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#eceff3"/><text x="{W - R + 4}" y="{y(p) + 4:.1f}" fill="#667085">{p:.2f}</text>')
    for i in range(a, z):
        o, h, l, c = bars[i][1:5]
        col = "#26a69a" if c >= o else "#ef5350"
        s.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l):.1f}" stroke="{col}"/>')
        s.append(f'<rect x="{x(i) - cw / 2:.1f}" y="{y(max(o, c)):.1f}" width="{cw:.1f}" height="{max(1, abs(y(o) - y(c))):.1f}" fill="{col}"/>')
    for e, col in ((e3, "#2962ff"), (e6, "#e53935")):
        pts = " ".join(f"{x(i):.1f},{y(e[i]):.1f}" for i in range(a, z))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.5"/>')
    for p, col, lab in ((trade["en"], "#1b1f24", "entry"), (trade["sl"], "#c8372d", "stop"), (trade["tp"], "#11845b", "target")):
        s.append(f'<line x1="{x(i_in):.1f}" x2="{x(min(z - 1, i_out + 3)):.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="{col}" stroke-dasharray="5,3" stroke-width="1.5"/>')
        s.append(f'<text x="{x(min(z - 1, i_out + 3)) + 4:.1f}" y="{y(p) + 4:.1f}" fill="{col}">{lab} {p:.2f}</text>')
    up = trade["side"] == "BUY"
    s.append(f'<text x="{x(i_in) - 4:.1f}" y="{y(trade["en"]) + (18 if up else -10):.1f}" font-size="16" fill="#1b1f24">{"▲" if up else "▼"}</text>')
    s.append(f'<circle cx="{x(i_out):.1f}" cy="{y(trade["ex"]):.1f}" r="5" fill="none" stroke="{"#11845b" if trade["net"] > 0 else "#c8372d"}" stroke-width="2"/>')
    s.append(f'<text x="{L}" y="{H - 8}" fill="#667085">Blueberry 1-min candles (MT5), EMA 3 blue / 6 red. {trade["side"]} {trade["in"]} server - exit {trade["out"]} ({trade["why"]}): {trade["net"]:+,.0f} at 2 lots</text>')
    s.append("</svg>")
    path.write_text("\n".join(s), encoding="utf-8")
    return True


def main():
    M = json.load(open(sys.argv[1]))
    key = sys.argv[2]
    rows = [x for x in csv.reader(open(COMMON / M[key]["csv"], encoding="utf-8", errors="ignore")) if x and x[0] != "num" and len(x) >= 22]
    T = []
    for x in rows:
        try:
            tp = float(x[8].split()[0])
        except (ValueError, IndexError):
            continue
        T.append({"side": x[2], "in": x[4], "en": float(x[5]), "sl": float(x[6]), "tp": tp, "out": x[15], "ex": float(x[16]), "why": x[17], "net": float(x[21])})
    fast_loss = lambda t: t["net"] < 0 and (datetime.strptime(t["out"][:19], "%Y.%m.%d %H:%M:%S") - datetime.strptime(t["in"][:19], "%Y.%m.%d %H:%M:%S")).total_seconds() <= 300
    picks = [("feb_loss", "February: a typical loser - stopped out within 5 minutes", lambda t: t["in"][:7] == "2026.02" and fast_loss(t)),
             ("mar_loss", "March: a typical loser - stopped out within 5 minutes", lambda t: t["in"][:7] == "2026.03" and fast_loss(t)),
             ("oct_win", "October: a typical winner", lambda t: t["in"][:7] == "2026.10" and t["net"] > 0),
             ("oct_loss", "October: a loser", lambda t: t["in"][:7] == "2026.10" and t["net"] < 0)]
    made = []
    for name, title, cond in picks:
        cands = [t for t in T if cond(t)]
        for t in cands[len(cands) // 2:]:                  # from the middle of the month, not the first oddity
            if svg(t, title, OUT / f"{name}.svg"):
                made.append(name)
                break
    print("made:", made)


if __name__ == "__main__":
    main()
