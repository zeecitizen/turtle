"""diamonds_day_study.py — did the SIZING kill the day, or the ENTRIES? (Zee: 'run the study')

The truest data we own is the live receipts (turtle_fills.csv) — real fills, real
slippage, real chop. This study re-prices the SAME trades under different rules
instead of simulating fantasy entries:

  Q1  SIZING: what does the identical trade sequence earn at flat 0.10 lots?
      (every trade's P&L scaled by 0.10/lots — same entries, same exits, same slip)
  Q2  DISCIPLINE: which losses are now impossible under the rules shipped since
      (harvest-and-return v1.61, losing-raid-retires-lamp v1.62, slope-opposition
      guard)? Recompute both sizings on the surviving set.
  Q3  HOURS: where does the edge actually live?

Verdict criterion, fixed before running: bursts (0.30/0.60) come back ONLY if the
receipts show flat-0.10 was NOT the difference — i.e. if sizing cost < $50 of the
damage. Otherwise the RISK_CAP stays until a proper multi-day walk-forward exists.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path

TF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/turtle_fills.csv")
OUT = Path(__file__).parent / "_DIAMONDS_STUDY.md"

# Trades the SHIPPED discipline rules would have refused, from the forensic log work
# of 2026-08-04/05 (each mapped to a rule in 05_AUGUST_DIAMONDS_FINDINGS.md §6):
BLOCKED = {
    "2026.08.04 22:20:35": "hover-refire (v1.61 harvest-and-return)",
    "2026.08.04 23:13:39": "doubling a losing lamp (v1.62 retirement)",
    "2026.08.04 22:13:16": "slope-opposition (chase into stretched top)",
    "2026.08.04 22:32:05": "slope-opposition (BUY vs falling slope)",
    "2026.08.04 22:47:07": "slope-opposition (BUY vs falling slope)",
}
GHOST_LOTS = {0.10, 0.30, 0.60}          # our clicks; 0.02s were manual/foreign


def load():
    rows = []
    for r in TF.read_text(errors="ignore").splitlines():
        c = r.split(",")
        if len(c) < 8 or not c[0].startswith(("2026.08.04", "2026.08.05")):
            continue
        try:
            ts, lots, pnl = c[0], float(c[5]), float(c[7])
        except ValueError:
            continue
        if ts < "2026.08.04 20:00":       # branch went live in the evening session
            continue
        if lots not in GHOST_LOTS:
            continue
        rows.append(dict(ts=ts, side=c[4].replace("_closed", ""), lots=lots, pnl=pnl,
                         flat=pnl * 0.10 / lots, blocked=BLOCKED.get(ts)))
    return rows


def stats(rows, key):
    n = len(rows); w = sum(1 for r in rows if r[key] > 0)
    net = sum(r[key] for r in rows)
    return n, w, (w / n * 100 if n else 0), net


if __name__ == "__main__":
    rows = load()
    md = ["# Diamonds-day study — receipts, not simulation", ""]

    n, w, wr, net_real = stats(rows, "pnl")
    _, _, _, net_flat = stats(rows, "flat")
    sizing_cost = net_real - net_flat
    md += [f"## Q1 — sizing, same trades",
           f"| | trades | WR | net |", "|---|---|---|---|",
           f"| as traded (bursts) | {n} | {wr:.0f}% | **{net_real:+.2f}** |",
           f"| re-priced flat 0.10 | {n} | {wr:.0f}% | **{net_flat:+.2f}** |",
           f"", f"**Burst sizing cost on identical trades: {sizing_cost:+.2f}**", ""]

    surv = [r for r in rows if not r["blocked"]]
    _, _, wr2, net_s_real = stats(surv, "pnl")
    _, _, _, net_s_flat = stats(surv, "flat")
    md += ["## Q2 — with the shipped discipline rules applied",
           f"{len(rows) - len(surv)} trades are now impossible:", ""]
    for r in rows:
        if r["blocked"]:
            md.append(f"- {r['ts'][5:]}  {r['side']} {r['lots']:.2f}  {r['pnl']:+.2f}  — {r['blocked']}")
    md += ["", f"| surviving set | trades | WR | net |", "|---|---|---|---|",
           f"| at burst sizing | {len(surv)} | {wr2:.0f}% | {net_s_real:+.2f} |",
           f"| at flat 0.10 | {len(surv)} | {wr2:.0f}% | **{net_s_flat:+.2f}** |", ""]

    by = defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        b = by[r["ts"][11:13]]; b[0] += r["pnl"] > 0; b[1] += r["pnl"] <= 0; b[2] += r["flat"]
    md += ["## Q3 — where the edge lives (flat-0.10 P&L by broker hour)", "",
           "| hour | W/L | net (flat) |", "|---|---|---|"]
    for hh in sorted(by):
        b = by[hh]
        md.append(f"| {hh}:xx | {b[0]}/{b[1]} | {b[2]:+.2f} |")

    verdict = ("SIZING WAS THE KILLER — cap stays until multi-day walk-forward"
               if sizing_cost < -50 else
               "sizing was NOT the main cost — entries were; investigate further")
    md += ["", f"## Verdict (criterion fixed pre-run: sizing cost < -$50 ⇒ cap stays)",
           "", f"**{verdict}**", "",
           "Caveats: one evening + one night of receipts; survivor analysis of blocked "
           "trades assumes no replacement trades; flat re-pricing keeps identical exits "
           "(valid because ghost caps are lot-scaled to ~constant dollars — at 0.10 the "
           "point-distance widens, so real flat losses could differ slightly)."]
    OUT.write_text("\n".join(md), encoding="utf-8")

    print(f"  trades {n}  WR {wr:.0f}%")
    print(f"  as traded : {net_real:+8.2f}")
    print(f"  flat 0.10 : {net_flat:+8.2f}   -> sizing cost {sizing_cost:+.2f}")
    print(f"  survivors (rules applied): burst {net_s_real:+.2f} | flat {net_s_flat:+.2f}")
    print(f"  VERDICT: {verdict}")
    print(f"  written -> {OUT}")
