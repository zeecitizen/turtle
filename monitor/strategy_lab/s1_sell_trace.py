"""s1_sell_trace.py — trace why each step of S1 SELL evaluates true/false
on the 3 mirror-predicted sell setups today.

Outputs a per-check breakdown so we can see exactly which condition the
MQL5 EA might be failing on.
"""
import csv, sys
from datetime import datetime, date, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import (is_downtrend, h1_bear_tapped_in,
                                       detect_s1_sell)

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TODAY = date(2026, 5, 19)


def load_m1(path):
    bars = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except Exception:
                continue
            bars.append({"time": t, "open": float(row["open"]),
                         "high": float(row["high"]), "low": float(row["low"]),
                         "close": float(row["close"]), "vol": int(row["tick_volume"])})
    return sorted(bars, key=lambda b: b["time"])


def trace_sell(m5, idx, h1_bear, h1_bull):
    """Step-by-step check at m5[idx] — return dict of each gate's verdict."""
    bo = m5[idx]
    out = {"time": bo["time"], "bo_open": bo["open"], "bo_close": bo["close"],
           "is_red": bo["close"] < bo["open"]}
    # 1. Red?
    if not out["is_red"]:
        out["fail_at"] = "not_red"
        return out
    # 2. Downtrend?
    out["is_downtrend"] = is_downtrend(m5, idx)
    if not out["is_downtrend"]:
        # show the trend values
        out["close_now"] = m5[idx]["close"]
        out["close_24back"] = m5[idx-24]["close"] if idx >= 24 else None
        out["fail_at"] = "no_downtrend"
        return out
    # 3. Retracement greens
    start = max(0, idx - 15)
    green_idxs = [j for j in range(start, idx) if m5[j]["close"] > m5[j]["open"]]
    out["greens_count"] = len(green_idxs)
    if not green_idxs:
        out["fail_at"] = "no_greens_in_retrace"
        return out
    uhv_idx = max(green_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    out["uhv_time"] = uhv["time"]
    out["uhv_high"] = uhv["high"]
    out["uhv_low"]  = uhv["low"]
    out["uhv_vol"]  = uhv["vol"]
    # 4. Breakdown
    out["bo_close_lt_uhv_low"]  = bo["close"] < uhv["low"]
    out["bo_open_gte_uhv_low"]  = bo["open"]  >= uhv["low"]
    if not out["bo_close_lt_uhv_low"]:
        out["fail_at"] = "bo_close_not_below_uhv_low"
        return out
    if not out["bo_open_gte_uhv_low"]:
        out["fail_at"] = "bo_open_below_uhv_low (not fresh transition)"
        return out
    # 5. Sweep above uhv.high
    out["swept_above"] = any(m5[j]["high"] > uhv["high"] for j in range(uhv_idx+1, idx+1))
    if not out["swept_above"]:
        out["fail_at"] = "no_sweep_above_uhv_high"
        return out
    # 6. H1 bear FVG tap during retracement (range start..idx+1)
    out["h1_bear_fvg_tapped"] = h1_bear_tapped_in(h1_bear, m5, range(start, idx+1))
    if not out["h1_bear_fvg_tapped"]:
        out["fail_at"] = "no_h1_bear_fvg_tap"
        # show what's available
        return out
    out["fail_at"] = None  # all passed
    return out


def main():
    bars = load_m1(COMMON / "rev_eng_m1_recent.csv")
    h1 = aggregate_to_tf(bars, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    m5 = aggregate_to_tf(bars, 5)
    print(f"Loaded {len(bars)} M1, {len(m5)} M5, {len(h1)} H1, "
          f"{len(h1_bull)} bull FVGs, {len(h1_bear)} bear FVGs\n")

    # Find the M5 idxs at fire times 04:25, 07:10, 08:25
    target_fire_times = [datetime(2026,5,19,4,25), datetime(2026,5,19,7,10),
                         datetime(2026,5,19,8,25)]
    for fire_t in target_fire_times:
        # bo.time = fire_t - 5min
        bo_t = fire_t - timedelta(minutes=5)
        idx_match = next((i for i, b in enumerate(m5) if b["time"] == bo_t), None)
        if idx_match is None:
            print(f"  [skip] no M5 bar at {bo_t}")
            continue
        print(f"\n{'='*92}")
        print(f"  SELL setup at fire_time={fire_t}  (bo bar at {bo_t}, idx={idx_match})")
        print(f"{'='*92}")
        result = trace_sell(m5, idx_match, h1_bear, h1_bull)
        for k, v in result.items():
            print(f"  {k:<25} = {v}")

        # Also show what visible bearish FVGs exist
        print(f"\n  Visible bearish H1 FVGs at this time:")
        for f in h1_bear:
            if f["t0"] >= bo_t: continue
            if f["filled_at"] is not None and f["filled_at"] <= bo_t: continue
            print(f"    t0={f['t0']}  zone=[{f['gap_high']:.2f}, {f['gap_low']:.2f}]  filled_at={f['filled_at']}")


if __name__ == "__main__":
    main()
