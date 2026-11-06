"""humps_mech.py - WHICH trade does the hump budget refuse?

The aggregate says budget 8 turns the aug31 window from -229.40 to +80.90 by removing
8 tickets of 106. That is one basket. An aggregate cannot say WHICH one, and "it
removed a loser" is a very different claim from "it removed the trade taken at the end
of the trend" - the second is Zee's theory, the first is luck.

Runs the same window twice (budget off, budget 8) as single backtests, then diffs the
DEAL lists so the refused basket can be named and looked at on the chart.

    py monitor/strategy_lab/humps_mech.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from rr_court import read_report, run_arm  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = ["InpNyOnly=false", "InpTargetR=0", "InpBreakEvenR=0", "InpSlMode=0",
        "InpTrendMode=0"]
ARMS = [("budget OFF", BASE + ["InpMaxHumps=0"]),
        ("budget 8", BASE + ["InpMaxHumps=8"])]


def entries(p: Path):
    """Every position OPEN in the report, as (time, type, price). 'in' deals only -
    an 'out' row is the same basket closing and would double every entry."""
    t = read_report(p)
    i = t.lower().find(">deals<")
    out = []
    if i < 0:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t[i:], re.S | re.I):
        c = [re.sub(r"<[^>]+>", "", x).replace(" ", " ").strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(c) < 12 or c[4].lower() != "in":
            continue
        out.append((c[0], c[3], c[6]))
    return out


def main():
    res = []
    for i, (label, inputs) in enumerate(ARMS):
        r = run_arm(label, inputs, "2026.08.31", "2026.09.05", 50000, 163, 4, 90 + i)
        if not r:
            continue
        r["entries"] = entries(r["report"])
        res.append(r)
    if len(res) != 2:
        sys.exit("[mech] need both arms to diff")

    off, cap = res
    t_off = [e[0] for e in off["entries"]]
    t_cap = set(e[0] for e in cap["entries"])
    refused = [e for e in off["entries"] if e[0] not in t_cap]

    print()
    print("=== ENTRIES THE HUMP BUDGET REFUSED (2026.08.31 -> 2026.09.05) ===")
    print("budget OFF opened %d tickets, net %.2f"
          % (len(off["entries"]), sum(off["day"].values())))
    print("budget 8   opened %d tickets, net %.2f"
          % (len(cap["entries"]), sum(cap["day"].values())))
    print()
    if not refused:
        print("   none - the budget never bound on this window")
    else:
        # group consecutive tickets into the baskets they belong to
        last = None
        for stamp, kind, price in refused:
            mark = "" if stamp[:16] == (last or "")[:16] else "\n"
            print("%s   %s   %-5s @ %s" % (mark, stamp, kind, price))
            last = stamp
    print()
    print("per-day  budget OFF :",
          {k: round(v, 2) for k, v in sorted(off["day"].items())})
    print("per-day  budget 8   :",
          {k: round(v, 2) for k, v in sorted(cap["day"].items())})


if __name__ == "__main__":
    main()
