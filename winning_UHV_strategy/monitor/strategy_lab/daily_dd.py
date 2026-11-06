"""The 5% DAILY rule - the limit a funded account actually dies on, never yet measured.

Every drawdown number this project has quoted is TOTAL drawdown (the 10% rule). Funded
accounts fail far more often on the DAILY rule: typically 5% of starting balance lost
within one broker day, measured on the running equity, not on the closed month.

This reads MT5's OWN deal list out of a tester report, walks it in order, and tracks the
running equity WITHIN each broker day - so a day that ran +$300 and then fell to -$400
counts its full $700 swing, which is how prop firms score it.

Reports a config's worst day, how many days would have breached, and the lot size at
which it stops breaching. No simulation: every number comes from deals MT5 executed.
"""
from __future__ import annotations
import re, sys
from collections import defaultdict
from pathlib import Path

REPORTS = Path(__file__).parent.parent.parent / "mt5" / "_tester_runs" / "axi"


def deals(stem: str):
    """(broker_day, net_pnl) per closed deal, in MT5's own order."""
    p = REPORTS / (stem + ".htm")
    if not p.exists():
        return []
    h = p.read_bytes().decode("utf-16-le", errors="replace")
    out = []
    for row in re.findall(r'<tr bgcolor="#[0-9A-F]{6}" align=right>(.*?)</tr>', h, re.S):
        c = [re.sub("<.*?>", "", x).replace("\xa0", "").strip()
             for x in re.findall(r"<td.*?>(.*?)</td>", row, re.S)]
        if len(c) >= 13 and c[3] in ("buy", "sell") and c[4] == "out":
            try:
                pnl = float(c[10].replace(" ", "")) + float(c[8].replace(" ", "") or 0)
            except ValueError:
                continue
            out.append((c[0][:10], pnl))
    return out


def daily(stem: str, balance=10000.0, pct=5.0, scale=1.0):
    """Worst intraday equity fall, and how many days breach the daily rule."""
    d = deals(stem)
    if not d:
        return None
    lim = balance * pct / 100.0
    by = defaultdict(list)
    for day, pnl in d:
        by[day].append(pnl * scale)
    worst, breaches, worst_day = 0.0, 0, ""
    for day, pnls in by.items():
        eq = peak = 0.0
        fall = 0.0
        for x in pnls:
            eq += x
            peak = max(peak, eq)
            fall = max(fall, peak - eq)      # the swing prop firms score
        fall = max(fall, -min(0.0, min(_run(pnls))))
        if fall > worst:
            worst, worst_day = fall, day
        if fall > lim:
            breaches += 1
    return {"days": len(by), "worst": worst, "worst_day": worst_day,
            "breaches": breaches, "limit": lim}


def _run(xs):
    eq = 0.0
    out = []
    for x in xs:
        eq += x
        out.append(eq)
    return out or [0.0]


def report(name: str, stem: str, balance=10000.0):
    r = daily(stem, balance)
    if not r:
        print("  %-26s no deals" % name)
        return
    safe = 1.0
    while safe > 0.02 and daily(stem, balance, scale=safe)["breaches"] > 0:
        safe -= 0.02
    print("  %-26s days %3d | worst day $%-7.0f (%s) | breaches %2d of %3d | "
          "safe at %.0f%% of lots"
          % (name, r["days"], r["worst"], r["worst_day"], r["breaches"], r["days"],
             safe * 100))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        n, _, s = arg.partition("=")
        report(n, s)
