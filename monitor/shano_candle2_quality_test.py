"""shano_candle2_quality_test.py — Test candle-2 quality filters in Shano's pattern.

Current Shano-Zee rule for candle 2 (the confirm bar):
  "same direction as trigger, any size"

This test gates candle 2 on quality dimensions and measures how each filter
changes the WR + total P&L. The trigger bar (candle 1) stays the same:
  body >= 1.5x body of bar before it.

Quality filters tested on candle 2:
  - Strength       = body / range >= threshold (effort-result)
  - Momentum       = body in pips >= threshold
  - Speed          = ticks/sec (rolling tick density vs prev N bars)
  - Range          = high-low >= threshold or >= multiplier of ATR-20
  - Body-vs-trig   = candle2 body >= ratio * candle1 body
  - Close-near-end = close in top/bottom X% of range (commitment)

Each filter is tested in isolation (sweep its parameter), then a small set of
combined filters is tested.

Path: fire main 0.30 lot at start of bar 3 (after candle 2 closes) in trigger
direction, validate with trail 25/8, SL -$10.
"""
from __future__ import annotations
import csv, math
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

TICK_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-01.csv")

# Probe & main economics
MAIN_LOTS          = 0.30
CONTRACT_SIZE      = 100
MAIN_TRAIL_TRIG    = 25.0
MAIN_TRAIL_DROP    = 8.0
MAIN_SL_USD        = 10.0
MAIN_CATASTROPHIC  = 50.0
MAIN_HORIZON_SEC   = 600
LATENCY_MS         = 250

BIGNESS_RATIO      = 1.5    # candle 1 (trigger) bigness ratio


# ── data layer ──
def parse_ticks(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            try:
                dt = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S").replace(microsecond=int(row[1]) * 1000)
                out.append((dt, float(row[2]), float(row[3])))
            except (ValueError, IndexError):
                continue
    return out


def build_m1_bars(ticks):
    bars = {}
    for dt, bid, ask in ticks:
        bm = dt.replace(second=0, microsecond=0)
        mid = (bid + ask) / 2
        if bm not in bars:
            bars[bm] = [mid, mid, mid, mid, 1]
        else:
            b = bars[bm]
            b[1] = max(b[1], mid); b[2] = min(b[2], mid); b[3] = mid; b[4] += 1
    return [(t, b[0], b[1], b[2], b[3], b[4]) for t, b in sorted(bars.items())]


def body(bar): return abs(bar[4] - bar[1])
def rng(bar):  return bar[2] - bar[3]
def direction(bar): return -1 if bar[4] < bar[1] else 1 if bar[4] > bar[1] else 0


def shano_2candle(bars, idx):
    """Returns (trigger_dir, trigger_idx) if candle pattern at bars[idx-1]=trigger, bars[idx]=confirm
    matches Shano's basic 2-candle pattern. Else None."""
    if idx < 2: return None
    trigger = bars[idx - 1]
    prev    = bars[idx - 2]
    confirm = bars[idx]
    if body(prev) <= 0: return None
    if body(trigger) < BIGNESS_RATIO * body(prev): return None
    td = direction(trigger)
    if td == 0: return None
    if direction(confirm) != td: return None
    return (td, idx - 1)


def pnl_usd(entry, curr, dir_sign, lots):
    return (curr - entry) * dir_sign * lots * CONTRACT_SIZE


def find_first_at(ticks, target_dt):
    for t in ticks:
        if t[0] >= target_dt: return t
    return None


def simulate_main(entry_dt, dir_sign, ticks_after, lots=MAIN_LOTS):
    target = entry_dt + timedelta(milliseconds=LATENCY_MS)
    fill = find_first_at(ticks_after, target)
    if fill is None: return {"outcome": "NO_FILL"}
    fill_dt, bid, ask = fill
    entry_price = ask if dir_sign == 1 else bid
    deadline = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC)
    peak = 0.0; last_pnl = 0.0
    for t in ticks_after:
        if t[0] < fill_dt: continue
        if t[0] > deadline:
            cur = t[1] if dir_sign == 1 else t[2]
            return {"outcome": "TIMEOUT", "pnl_usd": round(pnl_usd(entry_price, cur, dir_sign, lots), 2),
                    "peak_usd": round(peak, 2)}
        cur = t[1] if dir_sign == 1 else t[2]
        pnl = pnl_usd(entry_price, cur, dir_sign, lots)
        if pnl > peak: peak = pnl
        if pnl <= -MAIN_CATASTROPHIC:
            return {"outcome": "CATASTROPHIC", "pnl_usd": round(pnl, 2), "peak_usd": round(peak, 2)}
        if pnl <= -MAIN_SL_USD:
            return {"outcome": "SL", "pnl_usd": round(pnl, 2), "peak_usd": round(peak, 2)}
        if peak >= MAIN_TRAIL_TRIG and (peak - pnl) >= MAIN_TRAIL_DROP:
            return {"outcome": "TRAIL_WIN", "pnl_usd": round(pnl, 2), "peak_usd": round(peak, 2)}
        last_pnl = pnl
    return {"outcome": "TRUNCATED", "pnl_usd": round(last_pnl, 2), "peak_usd": round(peak, 2)}


def wilson_ci(wins, n, z=1.96):
    if n == 0: return [0.0, 0.0]
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return [round(max(0, (centre - half)) * 100, 1), round(min(1, (centre + half)) * 100, 1)]


# ── candle-2 quality filters ──
def filter_strength(c2, c1, threshold):
    """Strength = body / range >= threshold."""
    r = rng(c2)
    return r > 0 and body(c2) / r >= threshold

def filter_momentum_pts(c2, c1, threshold_pts):
    """Body in price points >= threshold."""
    return body(c2) >= threshold_pts

def filter_speed_density(c2_idx, bars, mult=1.5, lookback=20):
    """tick_count >= mult x rolling avg tick_count over lookback bars."""
    if c2_idx < lookback: return False
    avg = sum(bars[i][5] for i in range(c2_idx - lookback, c2_idx)) / lookback
    return avg > 0 and bars[c2_idx][5] >= mult * avg

def filter_range_pts(c2, c1, threshold_pts):
    return rng(c2) >= threshold_pts

def filter_range_atr(c2_idx, bars, mult=1.0, lookback=20):
    if c2_idx < lookback: return False
    avg = sum((bars[i][2] - bars[i][3]) for i in range(c2_idx - lookback, c2_idx)) / lookback
    return avg > 0 and rng(bars[c2_idx]) >= mult * avg

def filter_body_vs_trigger(c2, c1, ratio):
    """c2 body >= ratio * c1 body."""
    return body(c1) > 0 and body(c2) >= ratio * body(c1)

def filter_close_near_extreme(c2, c1, threshold=0.25):
    """Close within top/bottom threshold% of range, on trigger direction's side."""
    r = rng(c2)
    if r <= 0: return False
    pos = (c2[4] - c2[3]) / r  # 0=at low, 1=at high
    d = direction(c1)  # trigger direction
    if d == 1:
        return pos >= 1 - threshold
    return pos <= threshold


# ── runner ──
def run_filter(name, predicate_fn, bars, ticks):
    """predicate_fn(c2, c1, c2_idx, bars) -> bool. Returns stats dict."""
    results = []
    for i in range(2, len(bars) - 1):
        m = shano_2candle(bars, i)
        if m is None: continue
        td, t_idx = m
        c1 = bars[t_idx]; c2 = bars[i]
        try:
            keep = predicate_fn(c2, c1, i, bars)
        except Exception:
            keep = False
        if not keep: continue
        entry_dt = bars[i + 1][0]
        cutoff = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC + 30)
        future = [t for t in ticks if entry_dt - timedelta(seconds=2) <= t[0] <= cutoff]
        if not future: continue
        m_out = simulate_main(entry_dt, td, future)
        results.append(m_out)

    n = len(results)
    if n == 0:
        return {"name": name, "n": 0}
    wins = sum(1 for r in results if r.get("outcome") == "TRAIL_WIN")
    sl   = sum(1 for r in results if r.get("outcome") == "SL")
    cat  = sum(1 for r in results if r.get("outcome") == "CATASTROPHIC")
    timeo= sum(1 for r in results if r.get("outcome") == "TIMEOUT")
    pnls = [r.get("pnl_usd", 0) for r in results if "pnl_usd" in r]
    total = sum(pnls); avg = total / n
    wr = wins / n * 100; ci = wilson_ci(wins, n)
    return {"name": name, "n": n, "wr_pct": round(wr, 1), "ci": ci,
            "sl_pct": round(sl/n*100, 1), "cat_pct": round(cat/n*100, 1), "to_pct": round(timeo/n*100, 1),
            "total_pnl": round(total, 0), "avg_pnl": round(avg, 2)}


def main():
    print(f"Loading ticks from {TICK_CSV.name}...")
    ticks = parse_ticks(TICK_CSV)
    bars = build_m1_bars(ticks)
    print(f"Parsed {len(ticks):,} ticks -> {len(bars):,} M1 bars")
    print(f"BIGNESS_RATIO={BIGNESS_RATIO}  MAIN_LOTS={MAIN_LOTS}  trail={MAIN_TRAIL_TRIG}/{MAIN_TRAIL_DROP}  SL=${MAIN_SL_USD}")
    print()

    # Configurations to test
    tests = [
        # Baseline: current Shano (no candle-2 filter)
        ("baseline_current_shano",          lambda c2,c1,i,bars: True),
        # Strength sweep
        ("strength_body>=30%",              lambda c2,c1,i,bars: filter_strength(c2,c1, 0.30)),
        ("strength_body>=50%",              lambda c2,c1,i,bars: filter_strength(c2,c1, 0.50)),
        ("strength_body>=70%",              lambda c2,c1,i,bars: filter_strength(c2,c1, 0.70)),
        # Momentum (body in points - 0.10pt = 1 pip)
        ("momentum_body>=0.5pt",            lambda c2,c1,i,bars: filter_momentum_pts(c2,c1, 0.5)),
        ("momentum_body>=1.0pt",            lambda c2,c1,i,bars: filter_momentum_pts(c2,c1, 1.0)),
        ("momentum_body>=2.0pt",            lambda c2,c1,i,bars: filter_momentum_pts(c2,c1, 2.0)),
        # Speed (tick density)
        ("speed_density>=1.2x",             lambda c2,c1,i,bars: filter_speed_density(i, bars, 1.2)),
        ("speed_density>=1.5x",             lambda c2,c1,i,bars: filter_speed_density(i, bars, 1.5)),
        ("speed_density>=2.0x",             lambda c2,c1,i,bars: filter_speed_density(i, bars, 2.0)),
        # Range
        ("range>=1.0pt",                    lambda c2,c1,i,bars: filter_range_pts(c2,c1, 1.0)),
        ("range>=2.0pt",                    lambda c2,c1,i,bars: filter_range_pts(c2,c1, 2.0)),
        ("range>=1.0x_ATR20",               lambda c2,c1,i,bars: filter_range_atr(i, bars, 1.0)),
        ("range>=1.5x_ATR20",               lambda c2,c1,i,bars: filter_range_atr(i, bars, 1.5)),
        # Body-vs-trigger
        ("c2_body>=0.5x_c1",                lambda c2,c1,i,bars: filter_body_vs_trigger(c2,c1, 0.5)),
        ("c2_body>=1.0x_c1",                lambda c2,c1,i,bars: filter_body_vs_trigger(c2,c1, 1.0)),
        ("c2_body>=1.5x_c1",                lambda c2,c1,i,bars: filter_body_vs_trigger(c2,c1, 1.5)),
        # Close commitment
        ("close_in_top/bot_25%",            lambda c2,c1,i,bars: filter_close_near_extreme(c2,c1, 0.25)),
        ("close_in_top/bot_15%",            lambda c2,c1,i,bars: filter_close_near_extreme(c2,c1, 0.15)),
        # Combinations (best singles stacked)
        ("strength50+momentum1+speed1.5",   lambda c2,c1,i,bars: filter_strength(c2,c1,0.50) and filter_momentum_pts(c2,c1,1.0) and filter_speed_density(i,bars,1.5)),
        ("strength50+close25+range1.0xATR", lambda c2,c1,i,bars: filter_strength(c2,c1,0.50) and filter_close_near_extreme(c2,c1,0.25) and filter_range_atr(i,bars,1.0)),
        ("strength70+momentum2",            lambda c2,c1,i,bars: filter_strength(c2,c1,0.70) and filter_momentum_pts(c2,c1,2.0)),
    ]

    # Print header
    print(f"{'filter':<40s}  {'n':>4s}  {'WIN':>6s}  {'CI95':>14s}  {'SL':>5s}  {'cat':>4s}  {'TO':>5s}  {'total $':>9s}  {'avg $':>7s}")
    print("-" * 120)

    for name, fn in tests:
        s = run_filter(name, fn, bars, ticks)
        if s["n"] == 0:
            print(f"{name:<40s}  {'0':>4s}  no patterns matched")
            continue
        print(f"{s['name']:<40s}  {s['n']:>4d}  {s['wr_pct']:>5.1f}%  {str(s['ci']):>14s}  {s['sl_pct']:>4.1f}%  {s['cat_pct']:>3.1f}%  {s['to_pct']:>4.1f}%  ${s['total_pnl']:>+8.0f}  ${s['avg_pnl']:>+5.2f}")


if __name__ == "__main__":
    main()
