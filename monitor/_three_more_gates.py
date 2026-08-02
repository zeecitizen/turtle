"""Implement the 3 'visual judgment' gates Zee says are mechanizable:
  1. Weak candle rejection (wick proportion + body ratio on UHV + breakout)
  2. H1 trend bias (H1 bar direction must agree with setup)
  3. Liquidity sweep depth (the sweep before UHV must be a REAL sweep, not a fake)

Test each gate in isolation on the time-window survivors, then combine.
"""
import sys, bisect
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor")
import find_optimal_ea as foe
from datetime import datetime, timezone
import itertools

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
    if idx < 120: continue   # need lookback for H1 gate (120 M1 bars = 2 H1 bars)
    uhv_idx = idx - e["uhv_shift"]
    if uhv_idx < 0: continue
    e["entry_idx"] = idx; e["uhv_idx"] = uhv_idx; e["fill_ep"] = fill_ep
    e["utc_hour"] = datetime.fromtimestamp(fill_ep/1000, tz=timezone.utc).hour
    enriched.append(e)

GOOD_HOURS = {5, 12, 15, 19}
tws = [e for e in enriched if e["utc_hour"] in GOOD_HOURS]
print(f"Time-window survivors: {len(tws)}\n")


# ──────────────────────────────────────────────────────────────────────────
# GATE 1: Strong UHV body + breakout candle (no wick rejection)
# ──────────────────────────────────────────────────────────────────────────
def g_strong_uhv_body(e, min_ratio=0.50):
    b = bars_list[e["uhv_idx"]]
    rng = b["h"] - b["l"]
    if rng <= 0: return False
    return abs(b["c"] - b["o"]) / rng >= min_ratio


def g_no_wick_rejection(e, max_wick_ratio=0.35):
    """Both UHV and breakout candle shouldn't have huge counter-direction wicks."""
    for idx in [e["uhv_idx"], e["entry_idx"] - 1]:
        if idx < 0 or idx >= len(bars_list): return False
        b = bars_list[idx]
        rng = b["h"] - b["l"]
        if rng <= 0: continue
        body_h = max(b["o"], b["c"])
        body_l = min(b["o"], b["c"])
        upper_w = (b["h"] - body_h) / rng
        lower_w = (body_l - b["l"]) / rng
        if e["side"] == "BUY":
            # On the breakout candle: upper wick (against direction post-fire) tolerated, lower wick (rejection of low) is what matters
            # On UHV (red bear in retracement DOWN): both wicks indicate indecision; we want clean body
            if idx == e["entry_idx"] - 1:   # breakout candle for BUY = green
                if lower_w > max_wick_ratio: return False  # long lower wick on a green = bears almost won = bad
            else:   # UHV
                if upper_w > max_wick_ratio or lower_w > max_wick_ratio: return False
        else:
            if idx == e["entry_idx"] - 1:   # breakout candle for SELL = red
                if upper_w > max_wick_ratio: return False  # long upper wick on a red = bulls almost won
            else:
                if upper_w > max_wick_ratio or lower_w > max_wick_ratio: return False
    return True


# ──────────────────────────────────────────────────────────────────────────
# GATE 2: H1 trend bias
# ──────────────────────────────────────────────────────────────────────────
def g_h1_bias(e):
    """Last H1 bar's direction must agree with setup direction.
    H1 = 60 M1 bars. We use the most recent COMPLETED H1 = bars [entry-60..entry-1].
    """
    idx = e["entry_idx"]
    if idx < 60: return False
    # Approximate "last H1 close" = bars at entry-1
    # "last H1 open" = bars at entry-60
    h1_open = bars_list[idx - 60]["o"]
    h1_close = bars_list[idx - 1]["c"]
    if e["side"] == "BUY":
        return h1_close > h1_open      # H1 was bullish
    else:
        return h1_close < h1_open      # H1 was bearish


# ──────────────────────────────────────────────────────────────────────────
# GATE 3: Real liquidity sweep depth (not just any touch)
# ──────────────────────────────────────────────────────────────────────────
def g_real_sweep(e, min_sweep_pts=0.30):
    """The bar between UHV and entry must have made a REAL sweep past UHV extreme."""
    uhv_h = bars_list[e["uhv_idx"]]["h"]
    uhv_l = bars_list[e["uhv_idx"]]["l"]
    max_sweep = 0.0
    for i in range(e["uhv_idx"] + 1, e["entry_idx"]):
        b = bars_list[i]
        if e["side"] == "BUY":
            sweep = uhv_l - b["l"]    # how far the low dipped below UHV.low
            max_sweep = max(max_sweep, sweep)
        else:
            sweep = b["h"] - uhv_h    # how far the high stretched above UHV.high
            max_sweep = max(max_sweep, sweep)
    return max_sweep >= min_sweep_pts


# ──────────────────────────────────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────────────────────────────────
def eval_subset(survs, tp_pts):
    if not survs: return (0, 0, 0.0)
    wins = 0; total = 0.0
    for e in survs:
        i = bisect.bisect_left(tick_keys, e["fill_ep"])
        fwd = all_ticks[i:i+30000]
        pnl, _, _ = foe.forward_pnl(fwd, e["side"], e["entry"], e["sl"], tp_pts)
        total += pnl
        if pnl > 0: wins += 1
    return (len(survs), wins, total)


# Single-gate pass rates on tws
print("=== Each gate alone on time-window survivors ===")
for name, fn in [
    ("strong_uhv_body>=0.50",  lambda e: g_strong_uhv_body(e, 0.50)),
    ("no_wick_rejection",      lambda e: g_no_wick_rejection(e, 0.35)),
    ("h1_bias_agrees",         lambda e: g_h1_bias(e)),
    ("real_sweep>=0.30pt",     lambda e: g_real_sweep(e, 0.30)),
]:
    survs = [e for e in tws if fn(e)]
    n, w, t1 = eval_subset(survs, 1.3)
    _, _, t3 = eval_subset(survs, 3.0)
    _, _, t5 = eval_subset(survs, 5.0)
    wr = 100*w/max(n,1)
    print(f"  {name:<26s}  n={n:>2d}  WR={wr:>4.1f}%  TP=1.3:${t1:+.0f}  TP=3:${t3:+.0f}  TP=5:${t5:+.0f}")

# All combinations
print()
print("=== Multi-gate combinations (added to time-window UTC{5,12,15,19}) ===")
gates_4 = [
    ("strong_uhv", lambda e: g_strong_uhv_body(e, 0.50)),
    ("no_wick",    lambda e: g_no_wick_rejection(e, 0.35)),
    ("h1_bias",    lambda e: g_h1_bias(e)),
    ("real_sweep", lambda e: g_real_sweep(e, 0.30)),
]
results = []
for r in range(1, 5):
    for combo in itertools.combinations(range(4), r):
        survs = [e for e in tws if all(gates_4[i][1](e) for i in combo)]
        if len(survs) < 5: continue
        n, w, total5 = eval_subset(survs, 5.0)
        _, _, total3 = eval_subset(survs, 3.0)
        _, _, total13 = eval_subset(survs, 1.3)
        wr = 100*w/max(n,1)
        label = "+".join(gates_4[i][0] for i in combo)
        results.append((label, n, w, wr, total5, total3, total13))

# Show all results sorted by WR at TP=5
print(f"  {'config':<45s} {'n':>3s} {'W':>2s} {'WR%':>5s} {'$5pt':>7s} {'$3pt':>7s} {'$1.3pt':>7s}")
results.sort(key=lambda x: -x[3])
for label, n, w, wr, t5, t3, t1 in results:
    print(f"  {label:<45s} {n:>3d} {w:>2d} {wr:>4.1f}% ${t5:>+6.0f} ${t3:>+6.0f} ${t1:>+6.0f}")
