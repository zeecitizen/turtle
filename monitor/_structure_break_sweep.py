"""Test STRUCTURE_BREAK gate (master's trend definition: did price break the
last peak/low?) and additional newly-discovered rules. Goal: push 82% → 92%.
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
print(f"Time-window survivors: {len(tws)}\n")


# ──────────────────────────────────────────────────────────────────────────
# STRUCTURE_BREAK: did price break the last significant peak/low?
# Master labels: "broke its last low at X" → downtrend confirmed
#                "broke previous HH peak" → uptrend confirmed
# ──────────────────────────────────────────────────────────────────────────
def g_structure_break(e, lookback=20, fresh=5):
    """Did any bar in last `fresh` bars break above (BUY) the highest high of
    the prior (lookback - fresh) bars? Equivalent for SELL with lows."""
    idx = e["entry_idx"]
    if idx < lookback: return False
    earlier = bars_list[idx - lookback : idx - fresh]
    recent  = bars_list[idx - fresh   : idx]
    if e["side"] == "BUY":
        prior_high  = max(b["h"] for b in earlier)
        recent_high = max(b["h"] for b in recent)
        return recent_high > prior_high
    else:
        prior_low  = min(b["l"] for b in earlier)
        recent_low = min(b["l"] for b in recent)
        return recent_low < prior_low


# ──────────────────────────────────────────────────────────────────────────
# REJECTION_WICKS: retracement candles shouldn't show strong rejection of
# the breakout direction. For BUY (retracement down/red): if reds have long
# lower wicks = buyers stepping in early = retracement weak = bad. We want
# clean reds with no rejection.
# For SELL (retracement up/green): if greens have long upper wicks = sellers
# rejecting = trend already turning = bad.
# ──────────────────────────────────────────────────────────────────────────
def g_no_rejection_in_retracement(e, max_wick=0.45):
    uhv_idx = e["uhv_idx"]; entry_idx = e["entry_idx"]
    # Retracement bars = from origin → up to UHV. Just check UHV bar's wicks
    # plus the 2 bars immediately before UHV.
    for k in range(max(0, uhv_idx - 2), uhv_idx + 1):
        b = bars_list[k]
        rng = b["h"] - b["l"]
        if rng <= 0: continue
        body_h = max(b["o"], b["c"]); body_l = min(b["o"], b["c"])
        if e["side"] == "BUY":
            lower_w = (body_l - b["l"]) / rng
            if lower_w > max_wick: return False
        else:
            upper_w = (b["h"] - body_h) / rng
            if upper_w > max_wick: return False
    return True


# ──────────────────────────────────────────────────────────────────────────
# STRONG_TREND: not just structure break but BIG break (distance moved)
# ──────────────────────────────────────────────────────────────────────────
def g_strong_trend(e, lookback=20, min_break_pts=1.0):
    idx = e["entry_idx"]
    if idx < lookback: return False
    earlier = bars_list[idx - lookback : idx - 5]
    recent  = bars_list[idx - 5 : idx]
    if e["side"] == "BUY":
        prior_high  = max(b["h"] for b in earlier)
        recent_high = max(b["h"] for b in recent)
        return (recent_high - prior_high) >= min_break_pts
    else:
        prior_low  = min(b["l"] for b in earlier)
        recent_low = min(b["l"] for b in recent)
        return (prior_low - recent_low) >= min_break_pts


# Re-use sweep from previous script
def g_real_sweep(e, min_sweep_pts=0.30):
    uhv_h = bars_list[e["uhv_idx"]]["h"]
    uhv_l = bars_list[e["uhv_idx"]]["l"]
    max_sweep = 0.0
    for i in range(e["uhv_idx"] + 1, e["entry_idx"]):
        b = bars_list[i]
        if e["side"] == "BUY":
            max_sweep = max(max_sweep, uhv_l - b["l"])
        else:
            max_sweep = max(max_sweep, b["h"] - uhv_h)
    return max_sweep >= min_sweep_pts


def eval_subset(survs, tp_pts):
    if not survs: return (0, 0, 0.0)
    wins = 0; total = 0.0
    for e in survs:
        i = bisect.bisect_left(tick_keys, e["fill_ep"])
        pnl, _, _ = foe.forward_pnl(all_ticks[i:i+30000], e["side"], e["entry"], e["sl"], tp_pts)
        total += pnl
        if pnl > 0: wins += 1
    return (len(survs), wins, total)


# Test each new gate alone
print("=== Each gate ALONE on time-window survivors (n=34 baseline) ===")
gates = [
    ("struct_break(lb=20,fresh=5)",  lambda e: g_structure_break(e, 20, 5)),
    ("struct_break(lb=30,fresh=5)",  lambda e: g_structure_break(e, 30, 5)),
    ("struct_break(lb=10,fresh=3)",  lambda e: g_structure_break(e, 10, 3)),
    ("strong_trend(min=1.0pt)",      lambda e: g_strong_trend(e, 20, 1.0)),
    ("strong_trend(min=2.0pt)",      lambda e: g_strong_trend(e, 20, 2.0)),
    ("no_rejection_in_retr(0.45)",   lambda e: g_no_rejection_in_retracement(e, 0.45)),
    ("no_rejection_in_retr(0.30)",   lambda e: g_no_rejection_in_retracement(e, 0.30)),
    ("real_sweep(0.30)",             lambda e: g_real_sweep(e, 0.30)),
    ("real_sweep(0.50)",             lambda e: g_real_sweep(e, 0.50)),
]
for name, fn in gates:
    survs = [e for e in tws if fn(e)]
    n, w, t5 = eval_subset(survs, 5.0)
    _, _, t3 = eval_subset(survs, 3.0)
    _, _, t13 = eval_subset(survs, 1.3)
    wr5 = 100*w/max(n,1)
    n_w13 = sum(1 for e in survs for i in [bisect.bisect_left(tick_keys, e['fill_ep'])] if foe.forward_pnl(all_ticks[i:i+30000], e['side'], e['entry'], e['sl'], 1.3)[0] > 0)
    wr13 = 100*n_w13/max(n,1)
    mark5 = " ★★★" if wr5 >= 90 else " ★★" if wr5 >= 80 else " ★" if wr5 >= 70 else ""
    mark13 = " ★★★" if wr13 >= 90 else " ★★" if wr13 >= 80 else ""
    print(f"  {name:<30s}  n={n:>2d}  WR@5pt={wr5:>4.1f}%{mark5:>4s}   WR@1.3pt={wr13:>4.1f}%{mark13:>4s}   $5pt={t5:+.0f}  $1.3={t13:+.0f}")

print()
print("=== Combinations of 2 new gates (top WR-at-5pt) ===")
results = []
for r in range(1, 4):
    for combo in itertools.combinations(range(len(gates)), r):
        survs = [e for e in tws if all(gates[i][1](e) for i in combo)]
        if len(survs) < 5: continue
        n, w, t5 = eval_subset(survs, 5.0)
        _, _, t13 = eval_subset(survs, 1.3)
        wr5 = 100*w/max(n,1)
        n_w13 = sum(1 for e in survs for i in [bisect.bisect_left(tick_keys, e['fill_ep'])] if foe.forward_pnl(all_ticks[i:i+30000], e['side'], e['entry'], e['sl'], 1.3)[0] > 0)
        wr13 = 100*n_w13/max(n,1)
        label = "+".join(gates[i][0].split("(")[0] for i in combo)
        results.append((wr5, wr13, n, t5, t13, label))
results.sort(key=lambda x: -x[0])
print(f"  {'WR@5':>5s}  {'WR@1.3':>6s}  {'n':>3s}  {'$5':>7s}  {'$1.3':>7s}  config")
for wr5, wr13, n, t5, t13, label in results[:15]:
    mark = " ★★★" if wr5 >= 90 else " ★★" if wr5 >= 80 else ""
    print(f"  {wr5:>4.1f}%  {wr13:>5.1f}%  {n:>3d}  ${t5:>+6.0f}  ${t13:>+6.0f}  {label}{mark}")
