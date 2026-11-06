"""v3.45 smart-cut window — replace bar_count gate with elapsed-seconds gate.

For each of today's actual closed trades from turtle_fills.csv, check if
an earlier smart cut would have helped. We don't have full tick replay,
so we approximate using the realized loss as "what actually happened" and
the spread-aware $3 floor as "what smart cut would have caught".

Theory: any trade with realized P&L worse than -$3 would have been cut at
-$3 by v3.45 smart-cut (since spread + smart-cut threshold = -$3 floor).
"""
import csv
from pathlib import Path

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")


def main():
    rows = []
    with open(CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["broker_time"].startswith("2026.05.14"): continue
            r["net_pnl"] = float(r["net_pnl"])
            rows.append(r)

    actual_net = sum(r["net_pnl"] for r in rows)
    n = len(rows)
    wins = sum(1 for r in rows if r["net_pnl"] > 0)
    losses = sum(1 for r in rows if r["net_pnl"] < 0)
    print(f"Today actual: {n} trades, WR={100*wins/(wins+losses):.0f}%, net=${actual_net:+.2f}")
    print()

    for cap in [-3.0, -4.0, -5.0, -6.0, -8.0, -10.0]:
        # Simulate: any trade with pnl < cap gets capped to cap
        sim_pnls = [max(r["net_pnl"], cap) if r["net_pnl"] < 0 else r["net_pnl"] for r in rows]
        sim_net = sum(sim_pnls)
        savings = sim_net - actual_net
        # How many trades got cut?
        cut_count = sum(1 for r in rows if r["net_pnl"] < cap)
        # Largest losers
        worst = sorted([r["net_pnl"] for r in rows if r["net_pnl"] < cap])[:5]
        print(f"smart_cut cap={cap:>5.1f}$ : sim_net=${sim_net:>+9.2f}  saves=${savings:>+8.2f}  cuts {cut_count} trades (worst saved: {[f'${x:+.1f}' for x in worst]})")

    print()
    print("Distribution of today's losses:")
    bins = [(-50, -20), (-20, -10), (-10, -5), (-5, -3), (-3, -1), (-1, 0)]
    for lo, hi in bins:
        c = sum(1 for r in rows if lo <= r["net_pnl"] < hi)
        tot = sum(r["net_pnl"] for r in rows if lo <= r["net_pnl"] < hi)
        print(f"  ${lo:>+5.0f} to ${hi:>+5.0f}: {c:>4} trades, total ${tot:+.2f}")


if __name__ == "__main__":
    main()
