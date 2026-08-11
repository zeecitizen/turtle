"""
Shano Strategy Analyzer — Reverse-engineer Shano's trading strategy from her actual trades.
Reads her trade history and identifies the rules she follows.
"""
import json
from pathlib import Path

TRADES_FILE = Path(__file__).parent / "shano_trades.json"

def analyze():
    data = json.loads(TRADES_FILE.read_text("utf-8"))
    trades = data["trades"]

    print("=" * 70)
    print("SHANO'S STRATEGY ANALYSIS — 2026-04-24")
    print(f"Account: ${data['account_start']} -> ${data['account_end']} (+${data['account_end'] - data['account_start']})")
    print("=" * 70)

    # Overall stats
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)

    print(f"\nTotal trades: {len(trades)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)} | WR: {len(wins)/len(trades)*100:.0f}%")
    print(f"Gross profit: ${sum(t['pnl'] for t in wins):.2f}")
    print(f"Gross loss: ${sum(t['pnl'] for t in losses):.2f}")
    print(f"Net P&L (visible): ${total_pnl:.2f}")

    # Lot size distribution
    print("\n--- LOT SIZE ANALYSIS ---")
    lot_groups = {}
    for t in trades:
        lot = t["lots"]
        if lot not in lot_groups:
            lot_groups[lot] = {"count": 0, "wins": 0, "pnl": 0}
        lot_groups[lot]["count"] += 1
        if t["pnl"] > 0:
            lot_groups[lot]["wins"] += 1
        lot_groups[lot]["pnl"] += t["pnl"]

    for lot in sorted(lot_groups.keys()):
        g = lot_groups[lot]
        wr = g["wins"] / g["count"] * 100 if g["count"] > 0 else 0
        print(f"  {lot:.2f} lots: {g['count']} trades, {wr:.0f}% WR, P&L=${g['pnl']:+.2f}")

    # Direction analysis
    print("\n--- DIRECTION ANALYSIS ---")
    buys = [t for t in trades if t["dir"] == "buy"]
    sells = [t for t in trades if t["dir"] == "sell"]
    buy_wins = [t for t in buys if t["pnl"] > 0]
    sell_wins = [t for t in sells if t["pnl"] > 0]
    print(f"  BUY:  {len(buys)} trades, {len(buy_wins)}/{len(buys)} wins ({len(buy_wins)/len(buys)*100:.0f}%), P&L=${sum(t['pnl'] for t in buys):+.2f}")
    print(f"  SELL: {len(sells)} trades, {len(sell_wins)}/{len(sells)} wins ({len(sell_wins)/len(sells)*100:.0f}%), P&L=${sum(t['pnl'] for t in sells):+.2f}")

    # Cluster analysis — group trades within 5 min of each other
    print("\n--- TRADE CLUSTERS ---")
    clusters = []
    current_cluster = [trades[0]]

    for i in range(1, len(trades)):
        t = trades[i]
        prev = trades[i-1]
        # Parse times
        h1, m1, s1 = map(float, prev["time"].split(":"))
        h2, m2, s2 = map(float, t["time"].split(":"))
        gap = (h2 * 3600 + m2 * 60 + s2) - (h1 * 3600 + m1 * 60 + s1)

        if gap > 300:  # 5 min gap = new cluster
            clusters.append(current_cluster)
            current_cluster = [t]
        else:
            current_cluster.append(t)
    clusters.append(current_cluster)

    for i, cluster in enumerate(clusters):
        pnl = sum(t["pnl"] for t in cluster)
        start = cluster[0]["time"]
        end = cluster[-1]["time"]
        dirs = [t["dir"] for t in cluster]
        lots = [t["lots"] for t in cluster]
        buy_count = dirs.count("buy")
        sell_count = dirs.count("sell")

        print(f"\n  Cluster {i+1}: {start} -> {end} ({len(cluster)} trades)")
        print(f"    P&L: ${pnl:+.2f}")
        print(f"    Direction: {buy_count} buys, {sell_count} sells")
        print(f"    Lot progression: {' -> '.join(str(l) for l in lots)}")

        # Show each trade
        for t in cluster:
            emoji = "+" if t["pnl"] > 0 else "X"
            print(f"    {emoji} {t['time']} {t['dir'].upper():4} {t['lots']:.2f} @ {t['entry']:.3f} -> {t['exit']:.3f} = ${t['pnl']:+.2f}")

    # Pattern: Scout -> Scale analysis
    print("\n--- SCOUT -> SCALE PATTERN ---")
    print("Looking for 0.01 trades followed by larger trades in same direction...")
    for i, t in enumerate(trades):
        if t["lots"] == 0.01:
            # Look at next few trades
            following = trades[i+1:min(i+6, len(trades))]
            scaled = [f for f in following if f["lots"] >= 0.10 and f["dir"] == t["dir"]]
            if scaled:
                print(f"  Scout: {t['time']} {t['dir'].upper()} 0.01 -> Scaled to {scaled[0]['lots']} at {scaled[0]['time']}")
            else:
                # Did she switch direction?
                switched = [f for f in following if f["lots"] >= 0.08]
                if switched:
                    print(f"  Scout: {t['time']} {t['dir'].upper()} 0.01 -> {'SWITCHED' if switched[0]['dir'] != t['dir'] else 'SAME DIR'} {switched[0]['dir'].upper()} {switched[0]['lots']} at {switched[0]['time']}")

    # Hold time analysis
    print("\n--- HOLD TIME ANALYSIS ---")
    hold_times = []
    for t in trades:
        # Estimate hold time from entry/exit price distance and P&L
        price_move = abs(t["exit"] - t["entry"])
        # Can't calculate exact hold time without timestamps, but we can see the P&L per point
        pnl_per_point = t["pnl"] / price_move if price_move > 0 else 0
        hold_times.append({"trade": t, "price_move": price_move, "pnl_per_point": pnl_per_point})

    avg_move = sum(h["price_move"] for h in hold_times) / len(hold_times)
    print(f"  Avg price move per trade: {avg_move:.3f} points")
    print(f"  At 0.08 lots: 1 point = $8, at 0.20 lots: 1 point = $20")

    # Key findings
    print("\n" + "=" * 70)
    print("KEY STRATEGY RULES (Reverse-Engineered)")
    print("=" * 70)
    print("""
1. SCOUT FIRST: Start with 0.01 or 0.08 to test direction
   - If scout goes green -> scale up
   - If scout goes red -> cut fast, try opposite direction

2. PYRAMID INTO WINNERS: 0.08 -> 0.10 -> 0.20 -> 0.40
   - Only scale up when current position is in profit
   - Each add should be at a BETTER price (selling higher, buying lower)

3. DIRECTION BIAS: She reads the dominant trend and rides it
   - Cluster 2: 6 consecutive SELLs (14:55-14:58) during a down move
   - Cluster 3: 5 SELLs (15:24-15:27) during another down leg

4. CUT LOSERS FAST: Average loss = small, average win = bigger
   - Biggest loss: -$33.26 (held too long against reversal)
   - She usually cuts at -$0.74 to -$7.27

5. TRADE IN BURSTS: 5-10 trades in 2-3 minutes, then wait 20-30 min
   - This suggests she waits for a SETUP, then trades aggressively
   - The wait is for the next "strong red candle" pattern

6. HER DESCRIBED RULE: "Several red candles -> strong red candle -> green candle -> BUY"
   - This is a REVERSAL play after exhaustion
   - But her actual trades show she ALSO does CONTINUATION sells
   - She adapts between reversal and continuation based on what she sees
""")

    print("STRATEGY SUMMARY FOR AUTOMATION:")
    print("-" * 40)
    print("Entry: Scout with 0.01-0.08 lots")
    print("Confirm: If scout profits within 30s, scale to 0.10-0.20")
    print("Scale: If 2+ trades profit in same direction, go 0.40")
    print("Exit: Cut any trade that goes -$5 or more (at 0.08 lots)")
    print("Rest: After a cluster of trades, wait 15-30 min for next setup")
    print("Session: Trade only during London/NY overlap (14:00-17:00 Moscow)")

if __name__ == "__main__":
    analyze()
