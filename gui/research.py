"""research.py — study the session's own trades and say what to do differently.

Zee 2026-08-03: *"make sure ye software apni mistakes se seekhta hai, losses ko study karta
hai… ek bohot hi comprehensive engine run kare, learn from mistakes ka."*

What this refuses to do is dress a small sample as a discovery. Every finding carries its
sample size, and anything under a usable count is reported as "not enough evidence yet"
rather than turned into a rule. The system already lost six months to confident conclusions
drawn from backtests; this is the opposite instrument.

Findings that survive can be written straight into the playbook as lessons.
"""
from __future__ import annotations
import json, statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MIN_N = 4            # below this, a split is an anecdote, not a finding


def _pct(a, b):
    return (100.0 * a / b) if b else 0.0


def _wr(rows):
    f = [r for r in rows if r.get("usd") is not None]
    if not f:
        return None, 0
    return _pct(sum(1 for r in f if r["usd"] > 0), len(f)), len(f)


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def analyse(market="XAU", day=None):
    """Returns a report dict: headline, sections of findings, and suggested lessons."""
    import trade_book as TB
    if day is None:
        day, _ = TB.day_caption(market)
    rows = TB.book(market, day)
    took = [r for r in rows if r["verdict"] == "TAKE"]
    skipped = [r for r in rows if r["verdict"] == "SKIP"]
    filled = [r for r in took if r["usd"] is not None]
    wins = [r for r in filled if r["usd"] > 0]
    losses = [r for r in filled if r["usd"] < 0]

    rep = {"market": market, "day": day,
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "counts": {"judged": len(rows), "taken": len(took), "skipped": len(skipped),
                      "filled": len(filled), "wins": len(wins), "losses": len(losses)},
           "sections": [], "suggested": [], "headline": ""}

    net = sum(r["usd"] for r in filled)
    rep["net"] = net

    # ---------- headline -------------------------------------------------
    if not filled:
        rep["headline"] = (f"{len(rows)} setups judged, none reached a fill. "
                           "Nothing here can be validated on money yet.")
    else:
        wr, n = _wr(took)
        avg_w = statistics.mean([r["usd"] for r in wins]) if wins else 0.0
        avg_l = statistics.mean([abs(r["usd"]) for r in losses]) if losses else 0.0
        ratio = (avg_l / avg_w) if avg_w else 0.0
        rep["headline"] = (f"{n} fills, {wr:.0f}% won, net ${net:+.2f}. "
                           f"Average win ${avg_w:.2f} against average loss ${avg_l:.2f}"
                           + (f" — one loss eats {ratio:.1f} winners." if ratio else "."))
        rep["sections"].append({
            "title": "The ratio, not the win rate",
            "body": (f"Win rate {wr:.0f}% on {n} fills. Average win ${avg_w:.2f}, average "
                     f"loss ${avg_l:.2f}."
                     + (f" At {ratio:.1f} losers-to-winners this is only profitable above "
                        f"{100 * ratio / (1 + ratio):.0f}% accuracy."
                        if ratio > 0 else "")),
            "n": n, "solid": n >= MIN_N})

    # ---------- did the skips earn their keep? ---------------------------
    # The two questions the playbook demands after every session.
    sk_filled = [r for r in skipped if r["usd"] is not None]
    if skipped:
        rep["sections"].append({
            "title": "What the skips were worth",
            "body": (f"{len(skipped)} setups were skipped. "
                     + (f"{len(sk_filled)} of them can be scored: they would have netted "
                        f"${sum(r['usd'] for r in sk_filled):+.2f}."
                        if sk_filled else
                        "None of them were traded, so their cost is unmeasured — the "
                        "engine only records what it took.")),
            "n": len(skipped), "solid": len(sk_filled) >= MIN_N})

    # ---------- by side ---------------------------------------------------
    by_side = defaultdict(list)
    for r in filled:
        by_side[r["side"]].append(r)
    if len(by_side) > 1:
        parts, worst = [], None
        for s, rs in by_side.items():
            wr, n = _wr(rs)
            tot = sum(x["usd"] for x in rs)
            parts.append(f"{s}: {n} fills, {wr:.0f}% won, ${tot:+.2f}")
            if worst is None or tot < worst[1]:
                worst = (s, tot, n)
        solid = all(len(rs) >= MIN_N for rs in by_side.values())
        rep["sections"].append({
            "title": "Buys against sells",
            "body": "   ·   ".join(parts) + ("" if solid else
                    "   (too few of one side to call this a pattern)"),
            "n": len(filled), "solid": solid})
        if solid and worst and worst[1] < 0:
            rep["suggested"].append(
                f"{worst[0]}s lost ${abs(worst[1]):.2f} across {worst[2]} fills today — "
                f"require a clearly confirmed trend before taking another {worst[0]}.")

    # ---------- did the numbers behind the setup matter? -----------------
    for field, label, better_high in (("strength", "strength score", True),
                                      ("brk_body", "breakout body", True),
                                      ("uhv_vol", "UHV volume", True)):
        vals = [(r, _num(r.get(field))) for r in filled]
        vals = [(r, v) for r, v in vals if v is not None]
        if len(vals) < MIN_N * 2:
            continue
        vals.sort(key=lambda x: x[1])
        half = len(vals) // 2
        lo = [r for r, _ in vals[:half]]
        hi = [r for r, _ in vals[-half:]]
        lo_net, hi_net = sum(r["usd"] for r in lo), sum(r["usd"] for r in hi)
        lo_wr, _ = _wr(lo)
        hi_wr, _ = _wr(hi)
        gap = hi_net - lo_net
        rep["sections"].append({
            "title": f"Does {label} predict anything?",
            "body": (f"Low half ({half}): {lo_wr:.0f}% won, ${lo_net:+.2f}.   "
                     f"High half ({half}): {hi_wr:.0f}% won, ${hi_net:+.2f}."
                     + ("   The split is real." if abs(gap) > max(5.0, abs(lo_net) * 0.5)
                        else "   No meaningful separation.")),
            "n": len(vals), "solid": len(vals) >= MIN_N * 2})
        if abs(gap) > max(5.0, abs(lo_net) * 0.5) and len(vals) >= MIN_N * 2:
            direction = "above" if hi_net > lo_net else "below"
            cut = vals[half][1]
            rep["suggested"].append(
                f"On this session, {label} {direction} {cut:.2f} carried the money "
                f"(${hi_net if direction == 'above' else lo_net:+.2f} vs "
                f"${lo_net if direction == 'above' else hi_net:+.2f}). Worth watching, "
                f"not yet worth a filter.")

    # ---------- time of day ----------------------------------------------
    by_hour = defaultdict(list)
    for r in filled:
        h = (r.get("time") or "")[:2]
        if h.isdigit():
            by_hour[h].append(r)
    bad = [(h, sum(x["usd"] for x in rs), len(rs)) for h, rs in by_hour.items()
           if len(rs) >= MIN_N and sum(x["usd"] for x in rs) < 0]
    if by_hour:
        rep["sections"].append({
            "title": "When the damage happened",
            "body": ("   ·   ".join(f"{h}:00 → ${sum(x['usd'] for x in rs):+.2f} ({len(rs)})"
                                    for h, rs in sorted(by_hour.items()))
                     or "no fills to place in time"),
            "n": len(filled),
            "solid": any(len(rs) >= MIN_N for rs in by_hour.values())})

    # ---------- the losses, one by one -----------------------------------
    if losses:
        lines = []
        for r in sorted(losses, key=lambda x: x["usd"]):
            lines.append(f"{r['time']}  {r['side']} {r['lots']} @ {r['entry']} → "
                         f"${r['usd']:+.2f}"
                         + (f"   — Zee: {r['zee_comment'][:80]}" if r["zee_comment"]
                            else "   — not yet commented"))
        uncommented = sum(1 for r in losses if not r["zee_comment"])
        rep["sections"].append({
            "title": f"Every loss ({len(losses)})",
            "body": "\n".join(lines)
                    + (f"\n\n{uncommented} of these have no comment from you yet. Open each "
                       "one and press Derive Learnings — that is the only input that has "
                       "ever improved this system." if uncommented else ""),
            "n": len(losses), "solid": True})
        biggest = min(losses, key=lambda x: x["usd"])
        if abs(biggest["usd"]) > 3 * (statistics.mean([r["usd"] for r in wins]) if wins else 1):
            rep["suggested"].append(
                f"The worst trade (${biggest['usd']:+.2f} at {biggest['time']}) was larger "
                f"than three average winners. Whatever let that one through matters more "
                f"than anything else in this report.")

    # ---------- what Claude already promised ------------------------------
    try:
        import lessons as L
        ls = L.load()
        if ls:
            rep["sections"].append({
                "title": f"Rules already in force ({len(ls)})",
                "body": "\n".join(f"· {e['rule']}" for e in ls[-8:])
                        + "\n\nCheck each loss above against these: a loss that broke a rule "
                          "already written is a discipline problem, not a knowledge problem.",
                "n": len(ls), "solid": True})
    except Exception:
        pass

    if not rep["suggested"]:
        rep["suggested"].append(
            "Nothing in this session separates cleanly enough to become a rule. That is a "
            "finding, not a failure — the sample is small and forcing a filter onto it is "
            "how the last six months were lost.")
    return rep


def to_text(rep):
    out = [f"RESEARCH — {rep['market']}  ·  {rep['day']}",
           "=" * 72, "", rep["headline"], ""]
    c = rep["counts"]
    out.append(f"judged {c['judged']}   taken {c['taken']}   skipped {c['skipped']}   "
               f"filled {c['filled']}   wins {c['wins']}   losses {c['losses']}")
    out.append("")
    for s in rep["sections"]:
        flag = "" if s.get("solid") else "   [thin sample]"
        out += [f"— {s['title']}{flag}", s["body"], ""]
    out += ["WHAT TO DO DIFFERENTLY", "-" * 40]
    for i, s in enumerate(rep["suggested"], 1):
        out.append(f"{i}. {s}")
    return "\n".join(out)


def to_pdf(rep, out=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import textwrap

    out = Path(out or (REPO / "daily_reports" /
                       f"research_{rep['market']}_{rep['day']}.pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.patch.set_facecolor("white")
        fig.text(0.5, 0.74, "Research", ha="center", size=30, weight="bold")
        fig.text(0.5, 0.67, f"{rep['market']}   ·   {rep['day']}", ha="center", size=14,
                 color="#555")
        for i, line in enumerate(textwrap.wrap(rep["headline"], 78)):
            fig.text(0.5, 0.55 - i * 0.035, line, ha="center", size=13, color="#222")
        pdf.savefig(fig); plt.close(fig)

        for s in rep["sections"]:
            fig = plt.figure(figsize=(11.7, 8.3)); fig.patch.set_facecolor("white")
            fig.text(0.06, 0.93, s["title"], size=17, weight="bold", color="#1d4ed8")
            if not s.get("solid"):
                fig.text(0.06, 0.895, f"thin sample (n={s['n']}) — read as a hint, not a rule",
                         size=9.5, color="#b45309")
            y = 0.85
            for para in s["body"].split("\n"):
                for line in (textwrap.wrap(para, 108) or [""]):
                    fig.text(0.06, y, line, size=10, color="#222"); y -= 0.026
                    if y < 0.08:
                        break
                if y < 0.08:
                    break
            pdf.savefig(fig); plt.close(fig)

        fig = plt.figure(figsize=(11.7, 8.3)); fig.patch.set_facecolor("white")
        fig.text(0.06, 0.93, "What to do differently", size=19, weight="bold", color="#b45309")
        y = 0.85
        for i, s in enumerate(rep["suggested"], 1):
            for j, line in enumerate(textwrap.wrap(f"{i}. {s}", 100)):
                fig.text(0.06, y, line, size=11.5, color="#222"); y -= 0.032
            y -= 0.02
        pdf.savefig(fig); plt.close(fig)
    return out


if __name__ == "__main__":
    import sys
    mk = sys.argv[1].upper() if len(sys.argv) > 1 else "XAU"
    r = analyse(mk)
    print(to_text(r))
    if len(sys.argv) > 2 and sys.argv[2] == "pdf":
        print("\nPDF:", to_pdf(r))
