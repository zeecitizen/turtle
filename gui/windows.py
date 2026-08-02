"""windows.py — find the best time window, and name the session it belongs to.

Zee 2026-08-03: *"find out karta hai konsi time window mein sabse zyada profit hota hai, aur
usko sessions se match kar ke batata hai — New York open sabse acha time hai breakout ke
momentum ke liye."*

Two different questions, answered separately and honestly:

  MONEY      which hours actually made or lost money. Needs real fills, and with a handful
             of trades this is noise — so it says so instead of crowning an hour.
  MOVEMENT   which hours the market actually moves in: range, body-to-range, and volume.
             This needs no trades at all, so it is answerable from day one, and it is the
             honest basis for "New York open is best for breakout momentum".

Anything the sample cannot support is labelled, not dressed up. A time filter derived from
a thin sample is exactly the kind of overfitting that has already cost this system months.
"""
from __future__ import annotations
import statistics, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
sys.path.insert(0, str(MON))
sys.path.insert(0, str(MON / "strategy_lab"))

MIN_TRADES_PER_HOUR = 5     # below this, an hour's P&L is an anecdote

# Session windows in UTC. Gold and FX follow these; crypto ignores them but the same
# liquidity rhythm still shows up because the same desks trade it.
SESSIONS = [
    ("Sydney", 22, 7),
    ("Tokyo", 0, 9),
    ("London", 7, 16),
    ("London/NY overlap", 13, 16),
    ("New York", 12, 21),
]
KEY_MOMENTS = [
    ("London open", 7, 9),
    ("New York open", 13, 15),
    ("NY afternoon", 17, 20),
    ("Asia quiet", 2, 6),
]


def _in(h, a, b):
    return (a <= h < b) if a < b else (h >= a or h < b)


def sessions_for(hour):
    names = [n for n, a, b in SESSIONS if _in(hour, a, b)]
    return names or ["off-session"]


def moment_for(hour):
    for n, a, b in KEY_MOMENTS:
        if _in(hour, a, b):
            return n
    return None


def movement(market="XAU", bars=None):
    """How the market behaves by hour — range, body share, volume. No trades needed."""
    import claude_judge as J
    if bars is None:
        bars = J.load_bars(J.MARKETS[market]["data"])
    if len(bars) < 30:
        raise RuntimeError(f"only {len(bars)} bars of {market} data")

    by = defaultdict(list)
    for b in bars:
        by[b.t.hour].append(b)

    rows = []
    for h, bs in sorted(by.items()):
        rng = [b.h - b.l for b in bs]
        body = [abs(b.c - b.o) for b in bs]
        vol = [b.v for b in bs]
        mr = statistics.median(rng) if rng else 0.0
        mb = statistics.median(body) if body else 0.0
        rows.append({
            "hour": h,
            "bars": len(bs),
            "median_range": mr,
            "median_body": mb,
            "body_share": (mb / mr) if mr else 0.0,   # how much of the range is directional
            "median_vol": statistics.median(vol) if vol else 0.0,
            "sessions": sessions_for(h),
            "moment": moment_for(h),
        })
    return rows


def money(market="XAU"):
    """Which hours actually made money, from real fills only."""
    import trade_book as TB
    rows = []
    for h in TB.history(market):
        try:
            t = h["close_time"].replace(".", "-")
            hour = int(t[11:13])
        except Exception:
            continue
        rows.append((hour, h["usd"]))
    for e in TB._judgments():
        if e.get("market") != market or e.get("verdict") != "TAKE":
            continue
    by = defaultdict(list)
    for hour, usd in rows:
        by[hour].append(usd)
    out = []
    for h, us in sorted(by.items()):
        out.append({"hour": h, "trades": len(us), "net": sum(us),
                    "wins": sum(1 for u in us if u > 0),
                    "wr": 100.0 * sum(1 for u in us if u > 0) / len(us),
                    "sessions": sessions_for(h), "moment": moment_for(h),
                    "solid": len(us) >= MIN_TRADES_PER_HOUR})
    return out


def analyse(market="XAU"):
    mv = movement(market)
    mn = money(market)

    # movement ranking: the honest, always-available answer
    ranked = sorted(mv, key=lambda r: (r["median_range"] * r["body_share"]), reverse=True)
    best = ranked[:3]
    worst = ranked[-3:]

    findings = []
    if best:
        b = best[0]
        label = b["moment"] or " / ".join(b["sessions"])
        findings.append(
            f"Most movement per candle: {b['hour']:02d}:00 UTC — median range "
            f"{b['median_range']:.2f} with {100 * b['body_share']:.0f}% of it directional. "
            f"That hour sits in {label}.")
    if worst:
        w = worst[0]
        findings.append(
            f"Least worth trading: {w['hour']:02d}:00 UTC — median range "
            f"{w['median_range']:.2f}, only {100 * w['body_share']:.0f}% directional "
            f"({' / '.join(w['sessions'])}). Breakouts there have nowhere to go.")

    # does the data support the New York claim?
    ny = [r for r in mv if r["moment"] == "New York open"]
    others = [r for r in mv if r["moment"] != "New York open"]
    if ny and others:
        ny_m = statistics.median([r["median_range"] * r["body_share"] for r in ny])
        ot_m = statistics.median([r["median_range"] * r["body_share"] for r in others])
        if ny_m > ot_m * 1.15:
            findings.append(
                f"The New York open does earn its reputation here: {ny_m:.2f} of directional "
                f"movement per candle against {ot_m:.2f} elsewhere "
                f"({100 * (ny_m / ot_m - 1):.0f}% more).")
        elif ny_m < ot_m * 0.85:
            findings.append(
                f"On this data the New York open is NOT the best window: {ny_m:.2f} against "
                f"{ot_m:.2f} elsewhere. Worth checking against more days before believing it.")
        else:
            findings.append(
                f"The New York open is not clearly different here ({ny_m:.2f} against "
                f"{ot_m:.2f}). This sample cannot settle it.")

    # money, only if there is enough of it
    solid = [r for r in mn if r["solid"]]
    if not mn:
        findings.append(
            "No completed trades to rank hours by profit yet. Until there are, judge windows "
            "by movement, not by money.")
    elif not solid:
        findings.append(
            f"There are trades in {len(mn)} hours but none has {MIN_TRADES_PER_HOUR}+ of "
            "them. Per-hour profit here is noise; do not build a time filter on it.")
    else:
        bestm = max(solid, key=lambda r: r["net"])
        worstm = min(solid, key=lambda r: r["net"])
        findings.append(
            f"By money, {bestm['hour']:02d}:00 UTC leads: ${bestm['net']:+.2f} over "
            f"{bestm['trades']} trades ({bestm['wr']:.0f}% won) — "
            f"{bestm['moment'] or ' / '.join(bestm['sessions'])}.")
        if worstm["net"] < 0:
            findings.append(
                f"{worstm['hour']:02d}:00 UTC is the one that bleeds: ${worstm['net']:+.2f} "
                f"over {worstm['trades']} trades.")

    findings.append(
        "Before turning any of this into a rule: Zee's own doctrine is that trash hours hide "
        "asymmetric wins, and every time-window filter tried so far has been overfitted. "
        "Treat this as where to look, not where to be forced.")

    return {"market": market, "movement": mv, "money": mn,
            "best": best, "worst": worst, "findings": findings,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def to_text(d):
    out = [f"BEST TIME WINDOW — {d['market']}", "=" * 72, "",
           "MOVEMENT BY HOUR  (UTC — needs no trades, available from day one)",
           f"  {'hour':>5} {'bars':>6} {'range':>8} {'body%':>7} {'volume':>9}   session"]
    for r in sorted(d["movement"], key=lambda r: r["hour"]):
        out.append(f"  {r['hour']:02d}:00 {r['bars']:>6} {r['median_range']:>8.2f} "
                   f"{100 * r['body_share']:>6.0f}% {r['median_vol']:>9.0f}   "
                   + (r["moment"] + " · " if r["moment"] else "")
                   + " / ".join(r["sessions"]))
    if d["money"]:
        out += ["", "MONEY BY HOUR  (real fills only)",
                f"  {'hour':>5} {'trades':>7} {'net':>10} {'win%':>6}   session"]
        for r in sorted(d["money"], key=lambda r: r["hour"]):
            out.append(f"  {r['hour']:02d}:00 {r['trades']:>7} {r['net']:>+10.2f} "
                       f"{r['wr']:>5.0f}%   "
                       + ("" if r["solid"] else "[thin] ")
                       + (r["moment"] + " · " if r["moment"] else "")
                       + " / ".join(r["sessions"]))
    out += ["", "WHAT THIS SAYS", "-" * 40]
    for i, f in enumerate(d["findings"], 1):
        out.append(f"{i}. {f}")
    return "\n".join(out)


if __name__ == "__main__":
    mk = sys.argv[1].upper() if len(sys.argv) > 1 else "XAU"
    print(to_text(analyse(mk)))
