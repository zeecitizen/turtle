"""
multi_day_entry_density.py — runs the lesson-2 entry detector across all
64 days in the 88K-bar dataset and reports per-day signal counts plus
distributional stats. Doesn't simulate exits (those need tick data for
fidelity). This gives a clean read of how often the entry-pattern fires
in different market regimes.

Per-day metrics:
  - total signals
  - buy vs sell ratio
  - hours active (range of HH where signals fired)
  - peak hour (most signals)
  - dominant H1 trend during signal hours
"""
from __future__ import annotations
import csv
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"
H1_CSV = COMMON / "rev_eng_h1.csv"

MAX_LOOKBACK = 60
MAX_BARS_BACK = 60


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float
    vol: int

    @property
    def is_green(self): return self.close > self.open
    @property
    def is_red(self):   return self.close < self.open


def load_bars(path):
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            bars.append(Bar(
                time=datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                vol=int(r["tick_volume"]),
            ))
    bars.sort(key=lambda b: b.time)
    return bars


def detect(bars, idx_bo):
    bo = bars[idx_bo]
    # BUY
    if bo.is_green:
        reds = []; found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.high >= bo.close:
                found_swing = True; break
            if c.is_red: reds.append((k, c))
        if not reds or not found_swing: return None
        k_uhv, uhv = max(reds, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo.close <= uhv.high: return None
        if bo.vol >= uhv.vol: return None
        return {"side": "buy", "uhv_time": uhv.time, "bo": bo}
    # SELL
    if bo.is_red:
        greens = []; found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.low <= bo.close:
                found_swing = True; break
            if c.is_green: greens.append((k, c))
        if not greens or not found_swing: return None
        k_uhv, uhv = max(greens, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo.close >= uhv.low: return None
        if bo.vol >= uhv.vol: return None
        return {"side": "sell", "uhv_time": uhv.time, "bo": bo}
    return None


def h1_dir(h1, t):
    idx = None
    for i, b in enumerate(h1):
        if b.time <= t < b.time + timedelta(hours=1):
            idx = i; break
    if idx is None or idx < 2: return "?"
    c0 = h1[idx-2].close; c2 = h1[idx].close
    if c2 > c0: return "up"
    if c2 < c0: return "down"
    return "flat"


def main():
    m1 = load_bars(M1_CSV)
    h1 = load_bars(H1_CSV)
    print(f"M1 bars: {len(m1)}  H1 bars: {len(h1)}")
    print()

    # Run detector. Dedup on (UHV time, side) per v3.30 behavior.
    last_uhv = None; last_side = None
    signals = []
    for i in range(MAX_LOOKBACK + 5, len(m1)):
        sig = detect(m1, i)
        if not sig: continue
        if sig["uhv_time"] == last_uhv and sig["side"] == last_side:
            continue
        last_uhv = sig["uhv_time"]
        last_side = sig["side"]
        signals.append((sig["bo"].time, sig["side"]))

    print(f"Total deduped signals across 64 days: {len(signals)}")

    by_day = defaultdict(list)
    for t, s in signals:
        by_day[t.date()].append((t, s))

    print()
    print(f"{'date':<12} {'total':<6} {'buys':<5} {'sells':<6} {'peak_hr':<8} {'active_hrs':<11} {'h1_at_peak':<12}")
    print("-" * 75)

    day_stats = []
    for d in sorted(by_day):
        sigs = by_day[d]
        buys = sum(1 for _, s in sigs if s == "buy")
        sells = len(sigs) - buys
        hours = Counter(t.hour for t, _ in sigs)
        peak_hour, peak_count = hours.most_common(1)[0]
        active_hours = sorted(hours.keys())
        active_range = f"{active_hours[0]:02d}-{active_hours[-1]:02d}" if active_hours else "-"
        # Trend at peak hour
        peak_time = datetime.combine(d, datetime.min.time()).replace(hour=peak_hour)
        trend = h1_dir(h1, peak_time)
        day_stats.append({
            "date": d, "n": len(sigs), "buys": buys, "sells": sells,
            "peak_hour": peak_hour, "peak_count": peak_count,
            "active_range": active_range, "h1": trend
        })
        print(f"{d}   {len(sigs):<6} {buys:<5} {sells:<6} {peak_hour:02d}h({peak_count})   {active_range:<11} {trend:<12}")

    # Aggregate
    print()
    print("=" * 75)
    print("AGGREGATE OVER 64 DAYS")
    print("=" * 75)
    n_per_day = [d["n"] for d in day_stats]
    print(f"Signals per day: min={min(n_per_day)} median={statistics.median(n_per_day):.0f} mean={statistics.mean(n_per_day):.0f} max={max(n_per_day)}")

    # Outlier days (high signal count)
    print("\nTop 5 days by signal count:")
    for d in sorted(day_stats, key=lambda x: -x["n"])[:5]:
        print(f"  {d['date']}: {d['n']} signals (peak {d['peak_hour']:02d}h)")
    print("\nBottom 5 days by signal count:")
    for d in sorted(day_stats, key=lambda x: x["n"])[:5]:
        print(f"  {d['date']}: {d['n']} signals (peak {d['peak_hour']:02d}h)")

    # Peak-hour distribution
    print("\nPeak-hour distribution (when most signals fire):")
    peak_hours = Counter(d["peak_hour"] for d in day_stats)
    for h in sorted(peak_hours):
        bar = '█' * peak_hours[h]
        print(f"  {h:02d}:00  {peak_hours[h]:3d}  {bar}")

    # H1 trend distribution
    print("\nH1 trend at peak hour:")
    h1_dist = Counter(d["h1"] for d in day_stats)
    for k, v in sorted(h1_dist.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
