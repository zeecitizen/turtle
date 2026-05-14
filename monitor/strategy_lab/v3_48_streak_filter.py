"""v3.48 streak-aware filter — replay today's actual trade sequence and test:
   after K consecutive losses, pause firing for a cooldown (N trades skipped),
   then resume. Measures net P&L improvement.

The regime insight (Zee, 2026-05-14): trades come in streaks — long win runs
(trending gold) then long loss runs (chop). A streak-stop sits out the chop.
"""
import csv
from pathlib import Path

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")


def load_today():
    rows = []
    with open(CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["broker_time"].startswith("2026.05.14"): continue
            rows.append({"t": r["broker_time"], "pnl": float(r["net_pnl"])})
    # already in chronological order in the file
    return rows


def baseline(rows):
    net = sum(r["pnl"] for r in rows)
    w = sum(1 for r in rows if r["pnl"] > 0)
    l = sum(1 for r in rows if r["pnl"] < 0)
    return net, w, l, len(rows)


def simulate_streak_stop(rows, k_losses, cooldown_skip):
    """After k_losses consecutive losers, skip the next `cooldown_skip` trades.
    Returns (net_pnl, trades_taken, trades_skipped)."""
    net = 0.0
    consec_losses = 0
    skip_remaining = 0
    taken = 0
    skipped = 0
    for r in rows:
        if skip_remaining > 0:
            skip_remaining -= 1
            skipped += 1
            # While skipped we still "observe" — but we don't know the result
            # without taking it. For sim we just don't count its pnl.
            # Reset loss counter optimistically only when cooldown ends.
            if skip_remaining == 0:
                consec_losses = 0   # fresh start after cooldown
            continue
        # Take the trade
        net += r["pnl"]
        taken += 1
        if r["pnl"] < 0:
            consec_losses += 1
            if consec_losses >= k_losses:
                skip_remaining = cooldown_skip
        else:
            consec_losses = 0
    return net, taken, skipped


def main():
    rows = load_today()
    bnet, bw, bl, bn = baseline(rows)
    print(f"BASELINE (no filter): {bn} trades, {bw}W/{bl}L ({100*bw/(bw+bl):.0f}% WR), net=${bnet:+.2f}")
    print()
    print(f"{'k_loss':<8} {'cooldown':<10} {'net P&L':<12} {'taken':<8} {'skipped':<9} {'vs baseline'}")
    print("-" * 65)
    best = None
    for k in [2, 3, 4, 5]:
        for cd in [3, 5, 8, 12, 20]:
            net, taken, skipped = simulate_streak_stop(rows, k, cd)
            delta = net - bnet
            tag = ""
            if best is None or net > best[0]:
                best = (net, k, cd)
            print(f"{k:<8} {cd:<10} ${net:<+10.2f} {taken:<8} {skipped:<9} ${delta:+.2f}")
    print()
    print(f"BEST: k_losses={best[1]}, cooldown_skip={best[2]} → net ${best[0]:+.2f} (vs baseline ${bnet:+.2f}, delta ${best[0]-bnet:+.2f})")


if __name__ == "__main__":
    main()
