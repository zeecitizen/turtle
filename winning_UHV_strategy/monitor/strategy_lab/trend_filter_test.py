"""
trend_filter_test.py — test whether the OLD turtle.pine trend engine (EMA 34 / 89
on 1-min close) would have filtered out our losing probes.

Builds 1-min OHLCV from the tick CSV, computes EMAs, then for each probe in
probe_shadow_results.csv determines:
  - Is current bar's price above/below EMA-34 (fast)?
  - Is EMA-34 rising or falling vs prior bar?
  - Trend = up (above & rising), down (below & falling), neutral (otherwise)
  - Probe direction "with trend", "against trend", or "neutral"

Reports: WR/P&L by alignment + simulated outcome if we filter "against trend".
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

EMA_FAST = 34
EMA_SLOW = 89


def parse_ts(s):
    return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")


def load_all_ticks():
    """Load all tick rows across all available daily files."""
    out = []
    for p in sorted(COMMON_DIR.glob("shano_ticks_*.csv")):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                next(f, None)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 4: continue
                    try:
                        dt = parse_ts(parts[0])
                        bid = float(parts[2]); ask = float(parts[3])
                        out.append((dt, bid, ask))
                    except (ValueError, IndexError):
                        continue
        except OSError:
            pass
    return out


def build_1m_bars(ticks):
    """Resample ticks to 1-minute OHLCV using mid price."""
    bars = []  # list of (minute_dt, open, high, low, close)
    cur_min = None
    o = h = l = c = None
    for dt, bid, ask in ticks:
        mid = (bid + ask) / 2
        bm = dt.replace(second=0, microsecond=0)
        if cur_min is None:
            cur_min = bm; o = h = l = c = mid
        elif bm != cur_min:
            bars.append((cur_min, o, h, l, c))
            cur_min = bm; o = h = l = c = mid
        else:
            if mid > h: h = mid
            if mid < l: l = mid
            c = mid
    if cur_min is not None:
        bars.append((cur_min, o, h, l, c))
    return bars


def compute_ema(values, period):
    """Standard EMA computation."""
    if len(values) < period: return [None] * len(values)
    alpha = 2 / (period + 1)
    out = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for v in values[period:]:
        prev = (v - prev) * alpha + prev
        out.append(prev)
    return out


def trend_at_time(bars_dict, ema_fast, ema_slow, target_dt, bar_index_map):
    """Return ('up', 'down', 'neutral', or None) for trend at target_dt.
    bars_dict: dict[datetime] -> bar_index. ema_fast/slow: lists indexed by bar_index.
    """
    # Find latest bar <= target_dt
    bar_minute = target_dt.replace(second=0, microsecond=0)
    idx = bar_index_map.get(bar_minute)
    if idx is None:
        # find prior minute
        for delta in range(1, 30):
            t = bar_minute - timedelta(minutes=delta)
            idx = bar_index_map.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < EMA_SLOW: return None  # not enough history
    fast = ema_fast[idx]
    slow = ema_slow[idx]
    fast_prev = ema_fast[idx - 1] if idx > 0 else None
    if fast is None or slow is None or fast_prev is None: return None
    above = fast > slow
    rising = fast > fast_prev
    if above and rising: return "up"
    if (not above) and (not rising): return "down"
    return "neutral"


def main():
    print("Loading ticks and building 1-min bars...")
    ticks = load_all_ticks()
    print(f"  {len(ticks)} ticks loaded")
    bars = build_1m_bars(ticks)
    print(f"  {len(bars)} 1-min bars built")
    if not bars:
        print("no bars — abort"); return

    closes = [b[4] for b in bars]
    ema_fast = compute_ema(closes, EMA_FAST)
    ema_slow = compute_ema(closes, EMA_SLOW)
    bar_index_map = {b[0]: i for i, b in enumerate(bars)}
    print(f"  bars range: {bars[0][0]} -> {bars[-1][0]}")

    # Load probe results, simulate trend at each
    print("Analyzing probes...")
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    # Use feature_analyzer's simulator
    import sys
    sys.path.insert(0, str(LAB_DIR))
    from feature_analyzer import simulate_with_features

    feats = []
    history = []
    for r in rows:
        f = simulate_with_features(r, history)
        if f is None: continue
        feats.append(f)
        history.append({"dir": f["dir_sign"], "pnl": f["main_pnl"], "close_time": f["confirm_time"]})

    print(f"  {len(feats)} confirmed probes analyzed")

    # For each probe, determine trend alignment
    aligned_groups = defaultdict(list)
    for f in feats:
        trend = trend_at_time(None, ema_fast, ema_slow, f["entry_time"], bar_index_map)
        if trend is None:
            label = "no_trend_data"
        elif trend == "up" and f["dir_sign"] == 1:    label = "with_trend (BUY in up)"
        elif trend == "down" and f["dir_sign"] == -1: label = "with_trend (SELL in down)"
        elif trend == "up" and f["dir_sign"] == -1:   label = "AGAINST (SELL in up)"
        elif trend == "down" and f["dir_sign"] == 1:  label = "AGAINST (BUY in down)"
        else:                                          label = "neutral"
        aligned_groups[label].append(f)

    print()
    print("=" * 90)
    print("WR/P&L by trend alignment (EMA 34 vs EMA 89, 1-min XAUUSD)")
    print("=" * 90)
    overall_wr = sum(1 for f in feats if f["win"]) / max(len(feats), 1) * 100
    print(f"  baseline WR: {overall_wr:.1f}%  (n={len(feats)})")
    print()
    print(f"  {'group':<35}{'n':<6}{'wins':<6}{'WR%':<8}{'avg P&L':<10}{'total':<10}")
    for label in ["with_trend (BUY in up)", "with_trend (SELL in down)",
                  "AGAINST (BUY in down)", "AGAINST (SELL in up)",
                  "neutral", "no_trend_data"]:
        grp = aligned_groups.get(label, [])
        if not grp: continue
        n = len(grp); w = sum(1 for f in grp if f["win"])
        wr = w/n*100; avg = sum(f["main_pnl"] for f in grp) / n
        total = sum(f["main_pnl"] for f in grp)
        print(f"  {label:<35}{n:<6}{w:<6}{wr:<8.1f}${avg:+8.2f}  ${total:+8.2f}")

    # Now simulate filter: skip "against trend" probes
    print()
    print("=" * 90)
    print("FILTER COMPARISON")
    print("=" * 90)
    def is_bad_hour(f):
        return f["hour_utc"] in (4, 5, 6, 21, 22, 23)  # narrowed bad-hour set

    def label_for(f):
        trend = trend_at_time(None, ema_fast, ema_slow, f["entry_time"], bar_index_map)
        if trend is None: return "no_trend_data"
        if trend == "up" and f["dir_sign"] == 1: return "with_trend (BUY in up)"
        if trend == "down" and f["dir_sign"] == -1: return "with_trend (SELL in down)"
        if trend == "up" and f["dir_sign"] == -1: return "AGAINST (SELL in up)"
        if trend == "down" and f["dir_sign"] == 1: return "AGAINST (BUY in down)"
        return "neutral"

    scenarios = [
        ("No filter (baseline)", lambda f: False),
        ("Hour filter only (narrowed: 21-23 + 04-06)", lambda f: is_bad_hour(f)),
        ("Trend: skip AGAINST only", lambda f: label_for(f).startswith("AGAINST")),
        ("Trend: keep ONLY with_trend (skip neutral)", lambda f: not label_for(f).startswith("with_trend")),
        ("HOUR + skip AGAINST", lambda f: is_bad_hour(f) or label_for(f).startswith("AGAINST")),
        ("HOUR + skip neutral + skip AGAINST", lambda f: is_bad_hour(f) or not label_for(f).startswith("with_trend")),
    ]
    print(f"  {'scenario':<48}{'fired':<7}{'WR%':<8}{'total':<11}{'daily':<25}")
    for name, skip_fn in scenarios:
        kept = [f for f in feats if not skip_fn(f)]
        n = len(kept); w = sum(1 for f in kept if f["win"])
        wr = w/max(n,1)*100; total = sum(f["main_pnl"] for f in kept)
        by_day = defaultdict(float)
        for f in kept: by_day[f["entry_time"].strftime("%Y-%m-%d")] += f["main_pnl"]
        daily = " | ".join(f"{d[-5:]}:${p:+.0f}" for d, p in sorted(by_day.items()))
        print(f"  {name:<48}{n:<7}{wr:<8.1f}${total:+10.2f}  [{daily}]")


if __name__ == "__main__":
    main()
