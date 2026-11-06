"""Example-trade diagrams for dashboard/claude_trader/pyramiding.html, from the shipped EA's own MT5 verification
report (testing/Pyramiding_max_3_v101_verification_1lot.htm, +$479,814.52). Writes the HTML fragment between the
<!--EXAMPLES--> markers. Prices on the y axis are to scale; the x axis gives each distinct fill time its own slot
(fills minutes apart and exits hours later both stay readable), and the line joins the fills, not every tick."""
import html, json, re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REP = REPO / "testing" / "Pyramiding_max_3_v101_verification_1lot.htm"
PAGE = REPO / "dashboard" / "claude_trader" / "pyramiding.html"


def baskets():
    t = REP.read_text(encoding="utf-16", errors="ignore"); t = t[t.find("Deals"):]
    num = lambda s: float(s.replace(" ", "") or 0)
    out, cur, ov = [], None, 0.0
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [re.sub("<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if len(c) < 13 or not re.match(r"\d{4}\.", c[0]) or c[4] not in ("in", "out"):
            continue
        tm, typ, dr, vol, px, prof, cm = c[0], c[3], c[4], num(c[5]), num(c[6]), num(c[10]), c[12]
        if dr == "in":
            if ov < 1e-9:
                cur = {"side": "BUY" if typ == "buy" else "SELL", "in": [], "out": []}; out.append(cur)
            cur["in"].append((tm, vol, px)); ov += vol
        else:
            cur["out"].append((tm, vol, px, prof - 4 * vol, cm)); ov -= vol
    for b in out:
        b["net"] = sum(o[3] for o in b["out"]); b["tiers"] = len(b["in"])
    return out


def chart(b):
    W, H, L, R, T, Bm = 640, 280, 64, 20, 20, 46
    events = sorted({e[0] for e in b["in"]} | {e[0] for e in b["out"]})
    xs = {t: L + (W - L - R) * (i / max(1, len(events) - 1)) for i, t in enumerate(events)}
    prices = [e[2] for e in b["in"]] + [e[2] for e in b["out"]]
    stops = [float(m.group(1)) for o in b["out"] for m in [re.search(r"sl ([\d.]+)", o[4])] if m]
    lo, hi = min(prices + stops), max(prices + stops); pad = (hi - lo) * 0.12 or 1
    lo, hi = lo - pad, hi + pad
    y = lambda p: T + (H - T - Bm) * (hi - p) / (hi - lo)
    g = [f'<svg viewBox="0 0 {W} {H}" class="tchart" role="img" aria-label="price chart of this trade\'s fills">']
    for k in range(5):                                            # price grid
        p = lo + (hi - lo) * k / 4
        g.append(f'<line x1="{L}" x2="{W-R}" y1="{y(p):.1f}" y2="{y(p):.1f}" class="grid"/><text x="{L-6}" y="{y(p)+4:.1f}" class="ax" text-anchor="end">{p:.2f}</text>')
    seq = sorted([(e[0], e[2]) for e in b["in"]] + [(e[0], e[2]) for e in b["out"]])
    g.append('<polyline class="path" points="' + " ".join(f"{xs[t]:.1f},{y(p):.1f}" for t, p in seq) + '"/>')
    if stops:
        s = stops[-1]
        g.append(f'<line x1="{L}" x2="{W-R}" y1="{y(s):.1f}" y2="{y(s):.1f}" class="stop"/><text x="{W-R}" y="{y(s)-5:.1f}" class="lbl" text-anchor="end">final stop {s:.2f}</text>')
    for i, (t, v, p) in enumerate(b["in"]):
        r = 5 + 7 * v
        g.append(f'<circle cx="{xs[t]:.1f}" cy="{y(p):.1f}" r="{r:.1f}" class="e{min(i,4)+1}"/><text x="{xs[t]:.1f}" y="{y(p)-r-4:.1f}" class="lbl" text-anchor="middle">{v:g}</text>')
    for (t, v, p, net, cm) in b["out"]:
        g.append(f'<rect x="{xs[t]-6:.1f}" y="{y(p)-6:.1f}" width="12" height="12" class="{"xw" if net >= 0 else "xl"}"/>')
    shown = set()
    for t in events:                                              # time labels (date shown when it changes)
        d, hm = t[5:10], t[11:16]
        lab = hm if d in shown else f"{d} {hm}"; shown.add(d)
        anc = "end" if t == events[-1] and len(events) > 1 else ("start" if t == events[0] else "middle")
        g.append(f'<text x="{xs[t]:.1f}" y="{H-Bm+18}" class="ax" text-anchor="{anc}">{lab}</text>')
    g.append(f'<text x="{L}" y="{H-6}" class="ax">● entries (size = lots, colour = tier)   ■ exits (green = profit, red = loss)</text></svg>')
    return "".join(g)


def card(title, b, story, cls):
    rows = "".join(f"<tr><td>Tier {i+1}</td><td class='n'>{t[5:16]}</td><td class='n'>{v:g}</td><td class='n'>{p:.2f}</td></tr>" for i, (t, v, p) in enumerate(b["in"]))
    outs = "".join(f"<tr><td>Exit</td><td class='n'>{t[5:16]}</td><td class='n'>{v:g}</td><td class='n'>{p:.2f}</td><td class='n {'pos' if n >= 0 else 'neg'}'>{'+' if n >= 0 else '−'}${abs(n):,.0f}</td></tr>" for (t, v, p, n, cm) in b["out"])
    net = b["net"]
    return f"""<div class="ex {cls}"><h3>{html.escape(title)}: <span class="{'pos' if net >= 0 else 'neg'}">{'+' if net >= 0 else '−'}${abs(net):,.0f}</span></h3>
<p>{story}</p>{chart(b)}
<div class="tw"><table><thead><tr><th></th><th>Time</th><th>Lots</th><th>Price</th><th>Result</th></tr></thead><tbody>{rows}{outs}</tbody></table></div></div>"""


def bars(B):
    groups = [(k, [b for b in B if (b["tiers"] if b["tiers"] < 5 else 5) == k]) for k in range(1, 6)]
    vals = [(k, len(g), sum(b["net"] for b in g)) for k, g in groups]
    W, H, mid = 640, 240, 150
    mx = max(abs(v) for _, _, v in vals)
    sc = lambda v: (mid - 20) * abs(v) / mx
    g = [f'<svg viewBox="0 0 {W} {H}" class="tchart" role="img" aria-label="net profit by how many tiers a trade reached">',
         f'<line x1="40" x2="{W-10}" y1="{mid}" y2="{mid}" class="grid"/>']
    bw = (W - 80) / 5
    for i, (k, n, v) in enumerate(vals):
        x = 50 + i * bw; h = sc(v)
        yy = mid - h if v >= 0 else mid
        g.append(f'<rect x="{x:.0f}" y="{yy:.1f}" width="{bw-20:.0f}" height="{max(h,1):.1f}" class="{"xw" if v >= 0 else "xl"}"/>')
        ty = (yy - 6) if v >= 0 else (mid + h + 14)
        g.append(f'<text x="{x+(bw-20)/2:.0f}" y="{ty:.1f}" class="lbl" text-anchor="middle">{"+" if v >= 0 else "−"}${abs(v)/1000:,.0f}k</text>')
        g.append(f'<text x="{x+(bw-20)/2:.0f}" y="{H-24}" class="ax" text-anchor="middle">{k if k < 5 else "5+"} tier{"s" if k > 1 else ""}</text>')
        g.append(f'<text x="{x+(bw-20)/2:.0f}" y="{H-8}" class="ax" text-anchor="middle">{n} trades</text>')
    g.append("</svg>")
    return "".join(g)


if __name__ == "__main__":
    B = baskets()
    w5 = sorted([b for b in B if b["tiers"] == 5 and b["net"] > 0], key=lambda b: b["net"])
    one = sorted([b for b in B if b["tiers"] == 1 and b["net"] < 0], key=lambda b: b["net"])
    pick = [("The year's best trade, 27 Jan BUY", max(B, key=lambda b: b["net"]),
             "All 5 tiers filled within 12 minutes as gold took off. The trailing stop then rode the move all night and closed all five the next morning, $191 higher. The plain EA made +$19,150 on the same trade.", "win"),
            ("A typical full-pyramid win, 13 Jan SELL", w5[len(w5) // 2],
             "The middle winner among trades that reached 5 tiers. Half the base trade was banked at the first target; the $2 trail closed everything else a minute later.", "win"),
            ("A full pyramid that scratched, 30 Sep BUY", min([b for b in B if b["tiers"] >= 3], key=lambda b: abs(b["net"])),
             "All tiers filled, then gold came back. The base trade's stop had already moved into profit, so the early tiers won and the late ones lost: about $0 overall.", "flat"),
            ("A loser that never got going, 15 Apr BUY", one[len(one) // 2],
             "Price never moved 0.25 ATR our way, so nothing was added. It lost exactly what the plain EA loses. This is the most common kind of loss.", "loss"),
            ("The year's worst trade, 24 Jul SELL", min(B, key=lambda b: b["net"]),
             "All 5 tiers were on and the stop had moved to breakeven by Friday night, but gold gapped $26 higher at Monday's open, straight past the stop. With 3.05 lots on, the gap cost −$9,051 (the plain EA lost −$2,610 on the same gap).", "loss")]
    frag = ["<h2>Real trades from the test, drawn from their actual fills</h2>",
            '<p class="sub">Every example is a real trade of this exact EA (v1.01, default settings) from its MT5 verification run. Prices are to scale; each fill time gets its own slot along the bottom, and the line joins the fills (it doesn\'t show every price tick).</p>',
            '<div class="exs">' + "".join(card(*x) for x in pick) + "</div>",
            "<h2>Where the money comes from</h2>",
            '<p class="sub">Net profit of all 867 trades in the test, grouped by how many tiers the trade reached. Trades that never reach the top lose money; the ones that do pay for everything.</p>',
            '<div class="ladder">' + bars(B) + "</div>"]
    s = PAGE.read_text(encoding="utf-8")
    a, z = s.index("<!--EXAMPLES-->"), s.index("<!--/EXAMPLES-->")
    PAGE.write_text(s[:a] + "<!--EXAMPLES-->\n" + "\n".join(frag) + "\n" + s[z:], encoding="utf-8")
    print("examples written:", len(pick), "| tiers:", [(k, len([b for b in B if min(b['tiers'],5) == k])) for k in range(1, 6)])
