"""shano_analysis.py — for selected Shano trades, replay what would have happened
with the proposed $5 SL / $10 TP discipline using REAL Blueberry XAUUSD ticks.
"""
import sys, bisect
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

TICKS = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-29.csv")

# Selected Shano trades from her broker statement (29/05/2026)
# CORRECT entry times (the "open" times, not close)
# (ticket, side, entry_HMS, entry_px, actual_pnl, label)
TRADES = [
    ("9425456", "sell", "15:48:47", 4558.26, -6.16, "LOSER held 1h16m, exited at $4564.42"),
    ("9425384", "buy",  "17:02:01", 4567.83, -5.18, "LOSER (0.02 lot), exited at $4565.24"),
    ("9425932", "buy",  "17:16:03", 4564.45, +0.35, "WINNER cut in 5s @ $4564.80"),
    ("9426244", "buy",  "17:23:52", 4563.37, +0.58, "WINNER cut in 9s @ $4563.95"),
    ("9430595", "sell", "19:50:55", 4546.98, +0.47, "WINNER cut in 9s @ $4546.51"),
    ("9420839", "sell", "15:47:44", 4561.60, +0.60, "WINNER cut in 4s @ $4561.00"),
    ("9420036", "sell", "15:41:44", 4569.51, +6.12, "BEST WINNER (0.03 lot) @ $4567.47"),
    ("9420184", "sell", "15:42:12", 4565.18, +0.28, "WINNER cut in 8s @ $4564.90"),
    ("9419830", "sell", "15:39:32", 4574.88, +0.45, "WINNER cut in 6s @ $4574.43"),
    ("9419883", "sell", "15:39:48", 4572.95, +0.30, "WINNER cut in 41s @ $4572.65"),
]

print("Loading May 29 Blueberry XAUUSD ticks...")
ticks = []
with open(TICKS, encoding="utf-8") as f:
    next(f)
    for line in f:
        parts = line.strip().split(",")
        if len(parts) < 4: continue
        try:
            dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
            ms = int(parts[1]); t_ms = int(dt.timestamp() * 1000) + ms
            ticks.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
        except: continue
print(f"  {len(ticks):,} ticks loaded\n")
times = [t["t_ms"] for t in ticks]


def t_to_ms(hms_str):
    """Convert '17:05:35' → ms timestamp on 2026-05-29."""
    hh, mm, ss = map(int, hms_str.split(":"))
    return int(datetime(2026, 5, 29, hh, mm, ss).timestamp() * 1000)


def what_if(entry_px, entry_ms, side, sl_dist=5.0, tp_dist=10.0, max_hold_sec=1800):
    """Replay: from entry_ms forward, would $5 SL / $10 TP have hit? Which first?"""
    k0 = bisect.bisect_left(times, entry_ms)
    if k0 >= len(ticks): return None
    if side == "buy":
        sl = entry_px - sl_dist; tp = entry_px + tp_dist
    else:
        sl = entry_px + sl_dist; tp = entry_px - tp_dist
    for k in range(k0, min(k0 + 200000, len(ticks))):
        tk = ticks[k]
        elapsed = (tk["t_ms"] - entry_ms) / 1000
        if elapsed > max_hold_sec:
            cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
            return {"hit": "TIMEOUT", "elapsed_sec": elapsed, "pnl": cur, "px": (tk["bid"] if side == "buy" else tk["ask"])}
        if side == "buy":
            if tk["bid"] <= sl: return {"hit": "SL", "elapsed_sec": elapsed, "pnl": -sl_dist, "px": tk["bid"]}
            if tk["bid"] >= tp: return {"hit": "TP", "elapsed_sec": elapsed, "pnl": +tp_dist, "px": tk["bid"]}
        else:
            if tk["ask"] >= sl: return {"hit": "SL", "elapsed_sec": elapsed, "pnl": -sl_dist, "px": tk["ask"]}
            if tk["ask"] <= tp: return {"hit": "TP", "elapsed_sec": elapsed, "pnl": +tp_dist, "px": tk["ask"]}
    return None


def trade_peak_and_trough(entry_px, entry_ms, side, window_sec=1800):
    """For info: what was the BEST and WORST P&L this trade could have shown?
    best = maximum P&L reached (positive). worst = minimum P&L reached (most negative)."""
    k0 = bisect.bisect_left(times, entry_ms)
    if k0 >= len(ticks): return None
    end_ms = entry_ms + window_sec * 1000
    best_pnl = -1e9; worst_pnl = 1e9
    best_t = 0; worst_t = 0
    for k in range(k0, min(k0 + 200000, len(ticks))):
        tk = ticks[k]
        if tk["t_ms"] > end_ms: break
        if side == "buy":
            pnl = tk["bid"] - entry_px
        else:
            pnl = entry_px - tk["ask"]
        if pnl > best_pnl:
            best_pnl = pnl
            best_t = (tk["t_ms"] - entry_ms) / 1000
        if pnl < worst_pnl:
            worst_pnl = pnl
            worst_t = (tk["t_ms"] - entry_ms) / 1000
    return {"best_pnl": best_pnl, "best_at_sec": best_t,
            "worst_pnl": worst_pnl, "worst_at_sec": worst_t}


print(f"{'ticket':<10}{'side':<5}{'entry':>9}{'open':>10}{'actual':>9}  {'label':<40}")
print(f"{'':<10}{'':5}{'':9}{'':10}{'':9}  | $5SL/$10TP rule       | best at      | worst at")
print("-" * 165)
for tkt, side, entry_hms, entry_px, actual, label in TRADES:
    entry_ms = t_to_ms(entry_hms)
    r = what_if(entry_px, entry_ms, side, 5.0, 10.0, 1800)
    p = trade_peak_and_trough(entry_px, entry_ms, side, 1800)
    if r is None or p is None:
        print(f"  {tkt} — no tick data in range")
        continue
    rule_str = f"{r['hit']:>4} @{r['elapsed_sec']:>5.0f}s → ${r['pnl']:>+6.2f}"
    best_str = f"${p['best_pnl']:>+6.2f} @ {p['best_at_sec']:>5.0f}s"
    worst_str = f"${p['worst_pnl']:>+6.2f} @ {p['worst_at_sec']:>5.0f}s"
    print(f"{tkt:<10}{side:<5}{entry_px:>9.2f}{entry_hms:>10}${actual:>+7.2f}  {label:<40}")
    print(f"{'':<10}{'':5}{'':9}{'':10}{'':9}  | {rule_str:<22} | {best_str:<14} | {worst_str}")

print("\n" + "=" * 60)
print("LEGEND:")
print("  actual = what Shano's discretionary close earned")
print("  SL/TP rule = result if she had used $5 SL / $10 TP")
print("  peak / trough = best & worst the trade WOULD have shown in 30 min")
