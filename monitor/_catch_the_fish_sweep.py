"""Apply the master's 'catch the fish in the net' theory: within the time
window, exit as fast as the first positive tick. Sweep TP from very tight
(0.3pt = past spread only) up. Also test trail variants. Find the highest
WR config that's still profitable.
"""
import sys, bisect
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor")
import find_optimal_ea as foe
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

entries = foe.parse_entries()
all_ticks = []
all_bars_by_minute = {}
for csv_path in sorted(foe.COMMON.glob("shano_ticks_2026-06-*.csv")):
    if csv_path.stat().st_size < 1000: continue
    t = foe.load_ticks(csv_path)
    all_ticks.extend(t)
    all_bars_by_minute.update(foe.build_m1_bars(t))
all_ticks.sort(key=lambda x: x[0])
tick_keys = [t[0] for t in all_ticks]
sorted_minutes = sorted(all_bars_by_minute.keys())
minute_to_idx = {m: i for i, m in enumerate(sorted_minutes)}
bars_list = [all_bars_by_minute[m] for m in sorted_minutes]

enriched = []
for e in entries:
    fill_ep = foe.ea_time_to_utc_ep(e["date"], e["trigger_t"], e["trigger_ms"])
    minute_ep = (fill_ep // 60000) * 60000
    if minute_ep not in minute_to_idx: continue
    idx = minute_to_idx[minute_ep]
    if idx < 50: continue
    uhv_idx = idx - e["uhv_shift"]
    if uhv_idx < 0: continue
    e["entry_idx"] = idx; e["uhv_idx"] = uhv_idx; e["fill_ep"] = fill_ep
    e["utc_hour"] = datetime.fromtimestamp(fill_ep/1000, tz=timezone.utc).hour
    enriched.append(e)

# Filter to time-window survivors
GOOD_HOURS = {5, 12, 15, 19}
tws = [e for e in enriched if e["utc_hour"] in GOOD_HOURS]
print(f"Time-window survivors: {len(tws)}")
print()


def forward_pnl_with_trail(ticks_after, side, entry, sl, tp_pts, trail_arm_pts=0, trail_rev_pts=0):
    """Walk forward. Exit on SL, TP, or trail. Returns (pnl_usd, hit_type)."""
    if not ticks_after: return (0.0, "no_ticks")
    peak = entry
    trail_armed = False
    for ep, bid, ask in ticks_after:
        price = bid if side == "BUY" else ask
        # Track peak in favorable direction
        if side == "BUY":
            if price > peak: peak = price
            move_fav = peak - entry
        else:
            if price < peak: peak = price
            move_fav = entry - peak

        # SL
        if side == "BUY" and price <= sl:
            return ((sl - entry) * foe.DOLLARS_PER_POINT, "SL")
        if side == "SELL" and price >= sl:
            return ((entry - sl) * foe.DOLLARS_PER_POINT, "SL")

        # TP (hard target)
        if tp_pts > 0:
            cur_fav = (price - entry) if side == "BUY" else (entry - price)
            if cur_fav >= tp_pts:
                return (tp_pts * foe.DOLLARS_PER_POINT, "TP")

        # Trail
        if trail_arm_pts > 0 and trail_rev_pts > 0:
            if not trail_armed and move_fav >= trail_arm_pts:
                trail_armed = True
            if trail_armed:
                pullback = (peak - price) if side == "BUY" else (price - peak)
                if pullback >= trail_rev_pts:
                    cur_fav = (price - entry) if side == "BUY" else (entry - price)
                    return (cur_fav * foe.DOLLARS_PER_POINT, "trail")

    last_bid, last_ask = ticks_after[-1][1], ticks_after[-1][2]
    if side == "BUY":
        return ((last_bid - entry) * foe.DOLLARS_PER_POINT, "end")
    else:
        return ((entry - last_ask) * foe.DOLLARS_PER_POINT, "end")


def evaluate(survs, tp_pts=0, arm=0, rev=0):
    pnls = []
    for e in survs:
        i = bisect.bisect_left(tick_keys, e["fill_ep"])
        forward = all_ticks[i:i+30000]
        pnl, _ = forward_pnl_with_trail(forward, e["side"], e["entry"], e["sl"], tp_pts, arm, rev)
        pnls.append(pnl)
    n = len(pnls); w = sum(1 for p in pnls if p > 0)
    return (n, w, sum(pnls))


# ─────────────────────────────────────────────────────────────────────────
# FINE TP SWEEP — catch the fish at the first profitable tick
# ─────────────────────────────────────────────────────────────────────────
print("=== Fine TP sweep (no trail) — within {5,12,15,19} UTC ===")
print(f"{'TP_pts':>7s}  {'n':>3s}  {'W':>3s}  {'WR%':>5s}  {'avg':>7s}  {'total':>9s}")
print("-" * 60)
fine_tps = [0.3, 0.5, 0.7, 1.0, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 5.0]
best_tp = None
for tp in fine_tps:
    n, w, total = evaluate(tws, tp_pts=tp)
    wr = 100*w/max(n,1); avg = total / max(n,1)
    marker = ""
    if wr >= 80:
        marker = "  ★★★ approaching 92%"
    elif wr >= 70:
        marker = "  ★★ high WR"
    print(f"  {tp:>5.1f}pt  {n:>3d}  {w:>3d}  {wr:>4.1f}%  ${avg:>+6.2f}  ${total:>+8.2f}{marker}")

# ─────────────────────────────────────────────────────────────────────────
# TRAIL sweep — tight trail to lock first profit
# ─────────────────────────────────────────────────────────────────────────
print()
print("=== Trail sweep (arm at first positive, exit on small pullback) ===")
print(f"{'arm':>5s} {'rev':>5s}  {'n':>3s}  {'W':>3s}  {'WR%':>5s}  {'avg':>7s}  {'total':>9s}")
print("-" * 65)
for arm in [0.3, 0.5, 0.7, 1.0, 1.5]:
    for rev in [0.1, 0.2, 0.3, 0.5]:
        if rev > arm: continue
        n, w, total = evaluate(tws, tp_pts=0, arm=arm, rev=rev)
        wr = 100*w/max(n,1); avg = total / max(n,1)
        marker = "  ★" if wr >= 80 else ""
        print(f"  {arm:>4.1f}pt {rev:>4.1f}pt  {n:>3d}  {w:>3d}  {wr:>4.1f}%  ${avg:>+6.2f}  ${total:>+8.2f}{marker}")

# ─────────────────────────────────────────────────────────────────────────
# TP + TRAIL combo — best of both
# ─────────────────────────────────────────────────────────────────────────
print()
print("=== TP + Trail combos — TP as ceiling, trail as floor ===")
print(f"{'TP':>5s} {'arm':>5s} {'rev':>5s}  {'n':>3s}  {'W':>3s}  {'WR%':>5s}  {'avg':>7s}  {'total':>9s}")
print("-" * 75)
for tp in [2.0, 3.0, 5.0, 8.0]:
    for arm in [0.5, 1.0]:
        for rev in [0.2, 0.3]:
            if rev > arm: continue
            n, w, total = evaluate(tws, tp_pts=tp, arm=arm, rev=rev)
            wr = 100*w/max(n,1); avg = total / max(n,1)
            marker = "  ★" if wr >= 80 else ""
            print(f"  {tp:>4.1f} {arm:>4.1f} {rev:>4.1f}  {n:>3d}  {w:>3d}  {wr:>4.1f}%  ${avg:>+6.2f}  ${total:>+8.2f}{marker}")
