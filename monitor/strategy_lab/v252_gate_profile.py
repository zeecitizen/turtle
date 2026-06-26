"""v252_gate_profile.py — multi-day gate operating profile.

Does NOT simulate the EA's full P&L (Python port trap per
feedback_use_mt5_tester_not_python_port). Instead, for each M5 bar across all
available tick days, computes what % of bars each v2.52 gate would have
allowed for BUY direction vs SELL direction.

This answers questions like:
  - On a clean-trend day, what % of M5 bars pass the H1Bias gate?
  - On a chop day, does HHHL block everything (as it did 2026-06-03)?
  - Which gate is most discriminating between trend days and chop days?

Output: per-day table + summary. Use to decide which gate variant to put
through the real MT5 Strategy Tester first.
"""
from __future__ import annotations
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
import glob

sys.stdout.reconfigure(encoding="utf-8")

TICK_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
PIVOT_STR = 3
LOOKBACK_M5 = 60
LOOKBACK_H1 = 24
H1_BIAS_BARS = 6


@dataclass
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: int


def build_bars(tick_csv: Path, tf_min: int) -> list[Bar]:
    bars: dict[datetime, Bar] = {}
    try:
        f = tick_csv.open(encoding="utf-8")
    except Exception:
        return []
    r = csv.DictReader(f)
    for row in r:
        ts = row.get("ts_broker") or row.get("ts")
        if not ts: continue
        try:
            dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            continue
        floor_min = (dt.minute // tf_min) * tf_min
        bar_t = dt.replace(minute=floor_min, second=0, microsecond=0)
        try:
            bid = float(row["bid"]); ask = float(row["ask"])
        except (KeyError, ValueError):
            continue
        mid = (bid + ask) / 2
        b = bars.get(bar_t)
        if b is None:
            bars[bar_t] = Bar(bar_t, mid, mid, mid, mid, 1)
        else:
            if mid > b.h: b.h = mid
            if mid < b.l: b.l = mid
            b.c = mid
            b.v += 1
    f.close()
    return sorted(bars.values(), key=lambda b: b.t)


def has_hhhl(bars: list[Bar], idx_now: int, lookback: int, pivot_str: int, want_up: bool) -> bool:
    """idx_now = index of CURRENT bar (one we're at). Look back from there."""
    if idx_now < lookback - 1: return False
    hi1 = hi2 = 0.0; lo1 = lo2 = 0.0; hi_cnt = lo_cnt = 0
    # shift 1 = bar at idx_now - 1 (most recent CLOSED, since current bar is forming).
    # Walk oldest-to-newest.
    def bar_at_shift(shift: int):
        idx = idx_now - shift
        if idx < 0 or idx >= len(bars): return None
        return bars[idx]
    for shift in range(lookback - pivot_str, pivot_str, -1):
        b = bar_at_shift(shift)
        if b is None: continue
        is_hi = True; is_lo = True
        for k in range(1, pivot_str + 1):
            bL = bar_at_shift(shift + k); bR = bar_at_shift(shift - k)
            if bL is None or bR is None:
                is_hi = is_lo = False; break
            if b.h <= bL.h or b.h <= bR.h: is_hi = False
            if b.l >= bL.l or b.l >= bR.l: is_lo = False
        if is_hi: hi2 = hi1; hi1 = b.h; hi_cnt += 1
        if is_lo: lo2 = lo1; lo1 = b.l; lo_cnt += 1
    if hi_cnt < 2 or lo_cnt < 2: return False
    return (hi1 > hi2 and lo1 > lo2) if want_up else (hi1 < hi2 and lo1 < lo2)


def has_h1_bias(h1: list[Bar], at_time: datetime, bias_bars: int, want_up: bool) -> bool:
    # find shift-1
    last = None
    for i in range(len(h1) - 1, -1, -1):
        if h1[i].t + timedelta(hours=1) <= at_time:
            last = i; break
    if last is None: return False
    older = last - (bias_bars - 1)
    if older < 0: return False
    return (h1[last].c > h1[older].c) if want_up else (h1[last].c < h1[older].c)


def has_closedelta_trend_m5(m5: list[Bar], idx_now: int, lookback: int, threshold: float, want_up: bool) -> bool:
    """Mirror of MQL5 IsUptrendM5/IsDowntrendM5."""
    if idx_now < lookback: return False
    now_close = m5[idx_now - 1].c if idx_now > 0 else m5[idx_now].c   # shift 1
    back_close = m5[idx_now - 1 - lookback].c if idx_now - 1 - lookback >= 0 else None
    if back_close is None or back_close == 0: return False
    delta = now_close - back_close
    return (delta > threshold) if want_up else (delta < -threshold)


def profile_day(date_str: str, m5: list[Bar], h1: list[Bar]) -> dict:
    """Compute gate pass rates across all M5 bars of the day."""
    out = {
        "date": date_str, "n_m5": len(m5), "n_h1": len(h1),
        "closedelta_up": 0, "closedelta_down": 0,
        "hhhl_m5_up": 0, "hhhl_m5_down": 0,
        "h1bias_up": 0, "h1bias_down": 0,
    }
    # Start from bar where lookback is satisfied
    start = max(LOOKBACK_M5 + 1, 25)
    for i in range(start, len(m5)):
        at_t = m5[i].t
        if has_closedelta_trend_m5(m5, i, 24, 7.0, True): out["closedelta_up"] += 1
        if has_closedelta_trend_m5(m5, i, 24, 7.0, False): out["closedelta_down"] += 1
        if has_hhhl(m5, i, LOOKBACK_M5, PIVOT_STR, True): out["hhhl_m5_up"] += 1
        if has_hhhl(m5, i, LOOKBACK_M5, PIVOT_STR, False): out["hhhl_m5_down"] += 1
        if has_h1_bias(h1, at_t, H1_BIAS_BARS, True): out["h1bias_up"] += 1
        if has_h1_bias(h1, at_t, H1_BIAS_BARS, False): out["h1bias_down"] += 1
    out["bars_scored"] = len(m5) - start
    return out


def main():
    csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))
    print(f"Found {len(csvs)} tick CSV days")
    print()
    fmt = "{:<11} {:>5} {:>5}  {:>7} {:>7}  {:>7} {:>7}  {:>7} {:>7}"
    print(fmt.format("date", "M5", "H1", "CD_up%", "CD_dn%", "HHHL_u%", "HHHL_d%", "H1B_u%", "H1B_d%"))
    print("-" * 90)

    all_profiles = []
    for csv_path in csvs:
        date_str = csv_path.stem.replace("shano_ticks_", "")
        try:
            m5 = build_bars(csv_path, 5)
            h1 = build_bars(csv_path, 60)
        except Exception as e:
            print(f"  {date_str} ERROR: {e}")
            continue
        if len(m5) < LOOKBACK_M5 + 2:
            continue
        p = profile_day(date_str, m5, h1)
        if p["bars_scored"] <= 0: continue
        pct = lambda k: 100 * p[k] / p["bars_scored"]
        print(fmt.format(
            date_str, p["n_m5"], p["n_h1"],
            f"{pct('closedelta_up'):>6.1f}", f"{pct('closedelta_down'):>6.1f}",
            f"{pct('hhhl_m5_up'):>6.1f}", f"{pct('hhhl_m5_down'):>6.1f}",
            f"{pct('h1bias_up'):>6.1f}", f"{pct('h1bias_down'):>6.1f}",
        ))
        all_profiles.append(p)

    if not all_profiles:
        print("(no days had enough bars)"); return

    print()
    print("Across all days:")
    tot_bars = sum(p["bars_scored"] for p in all_profiles)
    print(f"  total scored bars: {tot_bars}")
    keys = ["closedelta_up", "closedelta_down", "hhhl_m5_up", "hhhl_m5_down", "h1bias_up", "h1bias_down"]
    for k in keys:
        n = sum(p[k] for p in all_profiles)
        print(f"  {k:<22} {n:>6} bars  ({100*n/tot_bars:5.1f}%)")

    # ER gate dependence
    print()
    print("Interpretation:")
    cd_total = sum(p["closedelta_up"] + p["closedelta_down"] for p in all_profiles)
    hh_total = sum(p["hhhl_m5_up"] + p["hhhl_m5_down"] for p in all_profiles)
    h1_total = sum(p["h1bias_up"] + p["h1bias_down"] for p in all_profiles)
    print(f"  Close-delta-only (current EA): {100*cd_total/tot_bars:.1f}% of bars are 'trending' (either direction)")
    print(f"  HHHL_M5 (v2.52 strict):        {100*hh_total/tot_bars:.1f}% of bars pass")
    print(f"  H1Bias (v2.52 softer):         {100*h1_total/tot_bars:.1f}% of bars pass (always sums to 100% if data complete)")
    print()
    print("Per-day variance (std dev):")
    import statistics
    for k in keys:
        vals = [100 * p[k] / p["bars_scored"] for p in all_profiles]
        print(f"  {k:<22} mean={statistics.mean(vals):5.1f}%  stddev={statistics.stdev(vals) if len(vals)>1 else 0:5.1f}%")


if __name__ == "__main__":
    main()
