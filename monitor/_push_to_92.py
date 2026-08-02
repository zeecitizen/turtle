"""Push harder toward 92% WR. Test stricter thresholds, structure_break,
and richer gate combinations to find the absolute peak WR configuration.
"""
import sys, bisect, itertools
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
    if idx < 120: continue
    uhv_idx = idx - e["uhv_shift"]
    if uhv_idx < 0: continue
    e["entry_idx"] = idx; e["uhv_idx"] = uhv_idx; e["fill_ep"] = fill_ep
    e["utc_hour"] = datetime.fromtimestamp(fill_ep/1000, tz=timezone.utc).hour
    enriched.append(e)

GOOD_HOURS = {5, 12, 15, 19}
tws = [e for e in enriched if e["utc_hour"] in GOOD_HOURS]


# Gate functions (full library)
def g_struct_break(e, lb=20, fresh=5):
    idx = e["entry_idx"]
    if idx < lb: return False
    earlier = bars_list[idx - lb : idx - fresh]
    recent  = bars_list[idx - fresh : idx]
    if e["side"] == "BUY":
        return max(b["h"] for b in recent) > max(b["h"] for b in earlier)
    else:
        return min(b["l"] for b in recent) < min(b["l"] for b in earlier)


def g_real_sweep(e, min_pts=0.30):
    uhv_h = bars_list[e["uhv_idx"]]["h"]
    uhv_l = bars_list[e["uhv_idx"]]["l"]
    max_sweep = 0.0
    for i in range(e["uhv_idx"] + 1, e["entry_idx"]):
        b = bars_list[i]
        if e["side"] == "BUY":
            max_sweep = max(max_sweep, uhv_l - b["l"])
        else:
            max_sweep = max(max_sweep, b["h"] - uhv_h)
    return max_sweep >= min_pts


def g_no_rejection_retr(e, max_wick=0.45):
    """Check UHV bar + 2 prior bars for rejection wicks."""
    for k in range(e["uhv_idx"], e["uhv_idx"] + 3):
        if k >= len(bars_list): continue
        b = bars_list[k]
        rng = b["h"] - b["l"]
        if rng <= 0: continue
        body_h = max(b["o"], b["c"]); body_l = min(b["o"], b["c"])
        if e["side"] == "BUY":
            if (body_l - b["l"]) / rng > max_wick: return False
        else:
            if (b["h"] - body_h) / rng > max_wick: return False
    return True


def g_h1_agrees(e):
    idx = e["entry_idx"]
    if idx < 60: return False
    h1_open  = bars_list[idx - 60]["o"]
    h1_close = bars_list[idx - 1]["c"]
    return (h1_close > h1_open) if e["side"] == "BUY" else (h1_close < h1_open)


def g_breakout_color(e):
    """Previous bar (breakout) must be right color."""
    idx = e["entry_idx"] - 1
    if idx < 0 or idx >= len(bars_list): return False
    b = bars_list[idx]
    if e["side"] == "BUY":
        return b["c"] > b["o"]
    else:
        return b["c"] < b["o"]


def g_uhv_strong_body(e, min_ratio=0.50):
    b = bars_list[e["uhv_idx"]]
    rng = b["h"] - b["l"]
    if rng <= 0: return False
    return abs(b["c"] - b["o"]) / rng >= min_ratio


def g_uhv_neighbor_peak(e):
    i = e["uhv_idx"]
    if i < 1 or i >= len(bars_list) - 1: return False
    return bars_list[i]["v"] > bars_list[i-1]["v"] and bars_list[i]["v"] > bars_list[i+1]["v"]


def eval_subset(survs, tp_pts):
    if not survs: return (0, 0, 0.0)
    wins = 0; total = 0.0
    for e in survs:
        i = bisect.bisect_left(tick_keys, e["fill_ep"])
        pnl, _, _ = foe.forward_pnl(all_ticks[i:i+30000], e["side"], e["entry"], e["sl"], tp_pts)
        total += pnl
        if pnl > 0: wins += 1
    return (len(survs), wins, total)


# ──────────────────────────────────────────────────────────────────────────
# Test: rejection-wick threshold sweep (tighten the 87.5%)
# ──────────────────────────────────────────────────────────────────────────
print("=== Rejection-wick threshold sweep (with sweep≥0.30) ===")
print(f"  {'wick_max':>9s}  {'n':>3s}  {'W@1.3':>5s}  {'WR@1.3':>6s}  {'W@5':>4s}  {'WR@5':>5s}  {'$1.3':>7s}  {'$5':>7s}")
for wm in [0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20]:
    survs = [e for e in tws if g_real_sweep(e, 0.30) and g_no_rejection_retr(e, wm)]
    n13, w13, t13 = eval_subset(survs, 1.3)
    n5, w5, t5 = eval_subset(survs, 5.0)
    wr13 = 100*w13/max(n13,1); wr5 = 100*w5/max(n5,1)
    mark = " ★★★" if wr13 >= 90 else " ★★" if wr13 >= 85 else ""
    print(f"  ≤{wm:.2f}      {n13:>3d}  {w13:>5d}  {wr13:>5.1f}%  {w5:>4d}  {wr5:>4.1f}%  ${t13:>+6.0f}  ${t5:>+6.0f}{mark}")

# ──────────────────────────────────────────────────────────────────────────
# Add structure_break with various lookbacks
# ──────────────────────────────────────────────────────────────────────────
print()
print("=== + structure_break (sweep + rejection + struct_break) ===")
print(f"  {'cfg':<50s}  {'n':>3s}  {'WR@1.3':>6s}  {'WR@5':>5s}  {'$1.3':>7s}  {'$5':>7s}")
for sw in [0.30, 0.45]:
    for rw in [0.45, 0.30]:
        for lb, fr in [(10,3), (15,5), (20,5), (30,7)]:
            survs = [e for e in tws if g_real_sweep(e, sw) and g_no_rejection_retr(e, rw) and g_struct_break(e, lb, fr)]
            n13, w13, t13 = eval_subset(survs, 1.3)
            _, w5, t5 = eval_subset(survs, 5.0)
            if n13 < 4: continue
            wr13 = 100*w13/n13; wr5 = 100*w5/n13
            mark = " ★★★" if wr13 >= 90 else " ★★" if wr13 >= 85 else ""
            cfg = f"sweep={sw} wick≤{rw} struct(lb={lb},fr={fr})"
            print(f"  {cfg:<50s}  {n13:>3d}  {wr13:>5.1f}%  {wr5:>4.1f}%  ${t13:>+6.0f}  ${t5:>+6.0f}{mark}")

# ──────────────────────────────────────────────────────────────────────────
# Full multi-gate brute force
# ──────────────────────────────────────────────────────────────────────────
print()
print("=== Brute force: combinations of all gates (n>=6, top WR@1.3) ===")
all_gates = [
    ("sweep≥0.30",       lambda e: g_real_sweep(e, 0.30)),
    ("sweep≥0.45",       lambda e: g_real_sweep(e, 0.45)),
    ("wick≤0.45",        lambda e: g_no_rejection_retr(e, 0.45)),
    ("wick≤0.30",        lambda e: g_no_rejection_retr(e, 0.30)),
    ("struct_brk(20,5)", lambda e: g_struct_break(e, 20, 5)),
    ("struct_brk(10,3)", lambda e: g_struct_break(e, 10, 3)),
    ("h1_agrees",        lambda e: g_h1_agrees(e)),
    ("brk_color",        lambda e: g_breakout_color(e)),
    ("uhv_body≥0.50",    lambda e: g_uhv_strong_body(e, 0.50)),
    ("neighbor_peak",    lambda e: g_uhv_neighbor_peak(e)),
]
results = []
for r in range(2, 6):
    for combo in itertools.combinations(range(len(all_gates)), r):
        survs = [e for e in tws if all(all_gates[i][1](e) for i in combo)]
        if len(survs) < 6: continue
        n13, w13, t13 = eval_subset(survs, 1.3)
        _, w5, t5 = eval_subset(survs, 5.0)
        wr13 = 100*w13/n13
        wr5 = 100*w5/n13
        label = " + ".join(all_gates[i][0] for i in combo)
        results.append((wr13, n13, wr5, t13, t5, label))

# Show top 15 by WR@1.3 (require n>=6)
results.sort(key=lambda x: (-x[0], -x[1]))
print(f"  {'WR@1.3':>6s}  {'n':>3s}  {'WR@5':>5s}  {'$1.3':>7s}  {'$5':>7s}  config")
for wr13, n, wr5, t13, t5, label in results[:20]:
    mark = " ★★★" if wr13 >= 90 else " ★★" if wr13 >= 85 else ""
    print(f"  {wr13:>5.1f}%  {n:>3d}  {wr5:>4.1f}%  ${t13:>+6.0f}  ${t5:>+6.0f}  {label}{mark}")
