"""compare_shano_may14.py — did our EA take trades at the same times as Shano?

Shano's trades (from her phone MT5 History, 2026-05-14, broker time).
Our trades from turtle_fills.csv (broker_time = close time; trades are quick
scalps so a +/-3min window absorbs open-vs-close skew).
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")

# (broker_time, side, lots, pnl) — XAUUSD only, from Zee's two screenshots
SHANO = [
    ("04:11:49", "buy",  0.40, None),   # pnl cut off in screenshot
    ("04:25:15", "buy",  0.04, 1.08),
    ("04:28:28", "buy",  0.60, 36.00),
    ("04:28:40", "buy",  0.01, 0.32),
    ("04:31:07", "buy",  0.08, 2.80),
    ("04:32:09", "sell", 0.20, 8.80),
    ("05:25:58", "buy",  0.60, 35.40),
    ("05:26:10", "buy",  0.01, -1.53),
    ("05:47:28", "sell", 0.01, 3.75),
    ("09:17:51", "sell", 0.01, 0.45),
    ("09:18:32", "sell", 0.01, 0.16),
    ("09:26:26", "buy",  0.60, 22.20),
    ("09:26:31", "buy",  0.01, 1.25),
    ("09:49:57", "sell", 0.60, 63.00),
    ("09:50:02", "sell", 0.01, 2.34),
    ("10:49:35", "sell", 0.20, 18.20),
    ("10:50:18", "sell", 0.10, 3.60),
    ("10:50:30", "sell", 0.10, 1.30),
]


def load_ours():
    rows = []
    with open(CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["broker_time"].startswith("2026.05.14"): continue
            if r["symbol"] != "XAUUSD": continue
            t = datetime.strptime(r["broker_time"], "%Y.%m.%d %H:%M:%S")
            side = "buy" if r["direction"].lower().startswith("buy") else "sell"
            rows.append({"t": t, "side": side, "vol": float(r["volume"]),
                         "pnl": float(r["net_pnl"])})
    rows.sort(key=lambda x: x["t"])
    return rows


def main():
    ours = load_ours()
    print(f"Our EA: {len(ours)} XAUUSD trades on 2026-05-14")
    if ours:
        print(f"  span: {ours[0]['t']:%H:%M} -> {ours[-1]['t']:%H:%M}\n")

    WIN = timedelta(minutes=3)
    print(f"{'Shano time':<11} {'side':<5} {'lot':<6} {'Shano$':<9} | {'our match (broker close t)':<28} {'our$':<9} verdict")
    print("-" * 95)
    used = set()
    matched = 0
    for (st, side, lot, pnl) in SHANO:
        zt = datetime.strptime("2026.05.14 " + st, "%Y.%m.%d %H:%M:%S")
        best, best_gap, best_i = None, WIN, None
        for i, o in enumerate(ours):
            if i in used: continue
            if o["side"] != side: continue
            gap = abs(o["t"] - zt)
            if gap <= best_gap:
                best, best_gap, best_i = o, gap, i
        pnl_s = f"${pnl:+.2f}" if pnl is not None else "  ?  "
        if best:
            used.add(best_i)
            matched += 1
            gap_s = f"{int(best_gap.total_seconds()):+d}s"
            print(f"{st:<11} {side:<5} {lot:<6} {pnl_s:<9} | {best['t']:%H:%M:%S} ({gap_s}) vol{best['vol']:<5} ${best['pnl']:<+7.2f} MATCH")
        else:
            print(f"{st:<11} {side:<5} {lot:<6} {pnl_s:<9} | {'(no EA trade within 3min)':<28} {'':<9} MISS")
    print(f"\nMatched {matched}/{len(SHANO)} of Shano's trades")

    # our trades NOT matched to any Shano trade, in her active window
    shano_lo = datetime.strptime("2026.05.14 04:00:00", "%Y.%m.%d %H:%M:%S")
    shano_hi = datetime.strptime("2026.05.14 11:00:00", "%Y.%m.%d %H:%M:%S")
    extras = [o for i, o in enumerate(ours) if i not in used and shano_lo <= o["t"] <= shano_hi]
    print(f"\nOur EA trades in 04:00-11:00 NOT aligned to a Shano trade: {len(extras)}")
    if extras:
        net_extra = sum(o["pnl"] for o in extras)
        ew = sum(1 for o in extras if o["pnl"] > 0)
        el = sum(1 for o in extras if o["pnl"] < 0)
        print(f"  ({ew}W/{el}L, net ${net_extra:+.2f}) — first few:")
        for o in extras[:8]:
            print(f"    {o['t']:%H:%M:%S} {o['side']:<5} vol{o['vol']:<5} ${o['pnl']:+.2f}")


if __name__ == "__main__":
    main()
