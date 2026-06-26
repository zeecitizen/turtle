"""Per-hour win-rate analysis on the 194 historical fires.
Goal: find the time window(s) where Zee's 92% WR claim holds true.
"""
import sys, bisect
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor")
import find_optimal_ea as foe
from collections import defaultdict
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

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
bars_list = [all_bars_by_minute[m] for m in sorted_minutes]
minute_to_idx = {m: i for i, m in enumerate(sorted_minutes)}

enriched = []
for e in entries:
    fill_ep = foe.ea_time_to_utc_ep(e["date"], e["trigger_t"], e["trigger_ms"])
    minute_ep = (fill_ep // 60000) * 60000
    if minute_ep not in minute_to_idx: continue
    entry_idx = minute_to_idx[minute_ep]
    if entry_idx < 50: continue
    uhv_idx = entry_idx - e["uhv_shift"]
    if uhv_idx < 0: continue
    e["entry_idx"] = entry_idx; e["uhv_idx"] = uhv_idx; e["fill_ep"] = fill_ep
    # Convert fill_ep back to UTC hour
    e["utc_hour"]   = datetime.fromtimestamp(fill_ep/1000, tz=timezone.utc).hour
    enriched.append(e)


def passes_3_gates(e):
    if not foe.gate_uhv_color(bars_list, e["uhv_idx"], e["side"]): return False
    if not foe.gate_max_bars(e["uhv_shift"], 8): return False
    if not foe.gate_breakout_body_close(
        bars_list, e["entry_idx"] - 1,
        bars_list[e["uhv_idx"]]["h"], bars_list[e["uhv_idx"]]["l"], e["side"]): return False
    return True


def pnl_for(e, tp_pts=5.0):
    i = bisect.bisect_left(tick_keys, e["fill_ep"])
    forward = all_ticks[i:i+30000]
    pnl, ht, _ = foe.forward_pnl(forward, e["side"], e["entry"], e["sl"], tp_pts)
    return pnl, ht


print("=== Hour-of-day breakdown (broker time = UTC+2, but ticks are UTC) ===")
print("    UTC hour ≈ broker hour - 2")
print()

# Pass 1: all 194 fires (no gates)
print("─── ALL 194 fires (no gates) ───")
print(f"{'UTC':>3s}  {'Brk':>3s}  {'n':>3s}  {'W':>3s}/{'L':>3s}  {'WR%':>5s}  {'total$':>9s}")
hour_data_all = defaultdict(list)
for e in enriched:
    pnl, ht = pnl_for(e, 5.0)
    hour_data_all[e["utc_hour"]].append(pnl)
for h in sorted(hour_data_all.keys()):
    pnls = hour_data_all[h]
    n = len(pnls); w = sum(1 for p in pnls if p > 0)
    wr = 100*w/n; total = sum(pnls)
    bar = "█" * int(wr/5)
    print(f"  {h:>2d}  {(h+2)%24:>3d}  {n:>3d}  {w:>3d}/{n-w:>3d}  {wr:>4.1f}%  ${total:>+7.2f}  {bar}")

# Pass 2: 3-gate filter survivors per hour
print()
print("─── After 3-gate filter (16 survivors) ───")
print(f"{'UTC':>3s}  {'Brk':>3s}  {'n':>3s}  {'W':>3s}/{'L':>3s}  {'WR%':>5s}  {'total$':>9s}")
hour_data_3g = defaultdict(list)
for e in enriched:
    if not passes_3_gates(e): continue
    pnl, ht = pnl_for(e, 5.0)
    hour_data_3g[e["utc_hour"]].append(pnl)
for h in sorted(hour_data_3g.keys()):
    pnls = hour_data_3g[h]
    n = len(pnls); w = sum(1 for p in pnls if p > 0)
    wr = 100*w/n; total = sum(pnls)
    bar = "█" * int(wr/5)
    print(f"  {h:>2d}  {(h+2)%24:>3d}  {n:>3d}  {w:>3d}/{n-w:>3d}  {wr:>4.1f}%  ${total:>+7.2f}  {bar}")

print()
print("=== Best HOURS with >= 3 fires, ranked by WR (all 194) ===")
candidates = []
for h, pnls in hour_data_all.items():
    if len(pnls) >= 3:
        w = sum(1 for p in pnls if p > 0)
        wr = 100*w/len(pnls); total = sum(pnls)
        candidates.append((h, len(pnls), w, wr, total))
candidates.sort(key=lambda x: -x[3])
for h, n, w, wr, total in candidates[:10]:
    print(f"  UTC {h:02d} (brk {(h+2)%24:02d}):  n={n}  WR={wr:.1f}%  total=${total:+.2f}")

# Look at session windows
print()
print("=== Session-window WR (all 194 fires) ===")
sessions = [
    ("Asia (UTC 22-06)",   lambda h: h >= 22 or h < 6),
    ("London (UTC 07-15)", lambda h: 7 <= h <= 15),
    ("NY (UTC 13-21)",     lambda h: 13 <= h <= 21),
    ("London open (07-10)",lambda h: 7 <= h <= 10),
    ("US open (13-16)",    lambda h: 13 <= h <= 16),
    ("Overlap (13-15)",    lambda h: 13 <= h <= 15),
]
for name, fn in sessions:
    pnls = [pnl_for(e, 5.0)[0] for e in enriched if fn(e["utc_hour"])]
    if not pnls: continue
    n = len(pnls); w = sum(1 for p in pnls if p > 0)
    print(f"  {name:<28s}  n={n:>3d}  WR={100*w/n:.1f}%  total=${sum(pnls):+.2f}")
