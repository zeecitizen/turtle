"""shano_layered_filter_test.py — candle-2 quality filters layered on LIVE filter stack.

LIVE filter stack reproduced (from shano_config.json):
  1. Shano 2-candle bigness pattern (trigger body >= 1.5x prev body, c2 same dir)
  2. UHV-in-lookback: a bar in last 20 M1 bars has highest tick_count + matches trigger color
  3. UHV swept: an interim bar broke the UHV's extreme
  4. Trigger close past UHV extreme by >= 0.3 pts
  5. Effort-result on UHV bar: body >= 50% range, both wicks <= 40% range
  6. 2-min trend filter: last 2 bars net direction matches trigger
  7. Spread <= 1.2x rolling median (per-bar avg spread)

Then layer candle-2 quality filters on top to measure marginal lift.

Validation: fire main 0.30 lot at start of bar 3, trail 25/8, SL -$10, 10-min horizon.
"""
from __future__ import annotations
import csv, math
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

TICK_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-01.csv")

MAIN_LOTS         = 0.30
CONTRACT_SIZE     = 100
MAIN_TRAIL_TRIG   = 25.0
MAIN_TRAIL_DROP   = 8.0
MAIN_SL_USD       = 10.0
MAIN_CATASTROPHIC = 50.0
MAIN_HORIZON_SEC  = 600
LATENCY_MS        = 250

BIGNESS_RATIO     = 1.5
UHV_LOOKBACK      = 20    # bars to search for UHV
TRIGGER_PAST_UHV  = 0.3   # pts past UHV extreme
EFFORT_BODY_MIN   = 0.50
EFFORT_WICK_MAX   = 0.40
TREND_BARS        = 2     # 2-min trend


# ── data ──
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
    """Returns list of (bar_dt, o, h, l, c, n_ticks, avg_spread)."""
    bars = {}
    for dt, bid, ask in ticks:
        bm = dt.replace(second=0, microsecond=0)
        mid = (bid + ask) / 2
        spr = ask - bid
        if bm not in bars:
            bars[bm] = {"o": mid, "h": mid, "l": mid, "c": mid, "n": 1, "spr_sum": spr}
        else:
            b = bars[bm]
            b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid
            b["n"] += 1; b["spr_sum"] += spr
    return [(t, b["o"], b["h"], b["l"], b["c"], b["n"], b["spr_sum"] / b["n"]) for t, b in sorted(bars.items())]


def body(bar): return abs(bar[4] - bar[1])
def rng(bar):  return bar[2] - bar[3]
def direction(bar): return -1 if bar[4] < bar[1] else 1 if bar[4] > bar[1] else 0


# ── LIVE filter implementations ──
def shano_2candle(bars, idx):
    """Returns (trigger_dir, trigger_idx) if 2-candle bigness pattern at bars[idx]."""
    if idx < 2: return None
    trigger = bars[idx - 1]; prev = bars[idx - 2]; confirm = bars[idx]
    if body(prev) <= 0: return None
    if body(trigger) < BIGNESS_RATIO * body(prev): return None
    td = direction(trigger)
    if td == 0: return None
    if direction(confirm) != td: return None
    return (td, idx - 1)


def find_uhv_in_lookback(bars, idx, lookback, color):
    """Find highest-tick-count bar in last N bars matching the trigger color (red for sell, green for buy).
    Returns (uhv_idx, uhv_bar) or None.
    """
    start = max(0, idx - lookback)
    best_idx = -1; best_n = -1
    for i in range(start, idx):
        b = bars[i]
        d = direction(b)
        if (color == -1 and d == -1) or (color == 1 and d == 1):
            if b[5] > best_n:
                best_n = b[5]; best_idx = i
    if best_idx < 0: return None
    return (best_idx, bars[best_idx])


def is_uhv_swept(bars, uhv_idx, until_idx, dir_sign):
    """Did any bar between uhv_idx+1 and until_idx-1 break UHV extreme?"""
    uhv = bars[uhv_idx]
    for i in range(uhv_idx + 1, until_idx):
        if dir_sign == -1 and bars[i][3] < uhv[3]: return True   # broke UHV low (for sell)
        if dir_sign == 1  and bars[i][2] > uhv[2]: return True   # broke UHV high (for buy)
    return False


def trigger_past_uhv(trigger_bar, uhv_bar, dir_sign):
    if dir_sign == -1:
        return trigger_bar[4] < uhv_bar[3] - TRIGGER_PAST_UHV
    return trigger_bar[4] > uhv_bar[2] + TRIGGER_PAST_UHV


def effort_result_on_uhv(uhv_bar):
    r = rng(uhv_bar)
    if r <= 0: return False
    b = body(uhv_bar)
    if b / r < EFFORT_BODY_MIN: return False
    upper = uhv_bar[2] - max(uhv_bar[1], uhv_bar[4])
    lower = min(uhv_bar[1], uhv_bar[4]) - uhv_bar[3]
    if upper / r > EFFORT_WICK_MAX: return False
    if lower / r > EFFORT_WICK_MAX: return False
    return True


def trend_2min(bars, idx, dir_sign):
    """Net direction of last TREND_BARS bars matches trigger."""
    if idx < TREND_BARS: return False
    start = bars[idx - TREND_BARS]; cur = bars[idx]
    net = cur[4] - start[1]   # close vs start open
    return (dir_sign == 1 and net > 0) or (dir_sign == -1 and net < 0)


def spread_ok(bars, idx, lookback=20, mult=1.2):
    """Current bar avg spread <= mult * rolling median."""
    if idx < lookback: return True   # not enough history → don't gate
    cur_spr = bars[idx][6]
    prior = [bars[i][6] for i in range(idx - lookback, idx)]
    med = median(prior)
    return med == 0 or cur_spr <= mult * med


def passes_live_stack(bars, idx):
    """Returns (passed, dir, uhv_idx) or (False, None, None)."""
    m = shano_2candle(bars, idx)
    if m is None: return (False, None, None)
    td, trigger_idx = m
    uhv = find_uhv_in_lookback(bars, trigger_idx, UHV_LOOKBACK, td)
    if uhv is None: return (False, None, None)
    uhv_idx, uhv_bar = uhv
    if not is_uhv_swept(bars, uhv_idx, trigger_idx, td): return (False, None, None)
    if not trigger_past_uhv(bars[trigger_idx], uhv_bar, td): return (False, None, None)
    if not effort_result_on_uhv(uhv_bar): return (False, None, None)
    if not trend_2min(bars, idx, td): return (False, None, None)
    if not spread_ok(bars, idx): return (False, None, None)
    return (True, td, uhv_idx)


# ── candle-2 quality filters ──
def f_strength(c2, t):  return rng(c2) > 0 and body(c2) / rng(c2) >= t
def f_momentum(c2, pts): return body(c2) >= pts
def f_speed(idx, bars, mult, lookback=20):
    if idx < lookback: return False
    avg = sum(bars[i][5] for i in range(idx - lookback, idx)) / lookback
    return avg > 0 and bars[idx][5] >= mult * avg
def f_range_atr(idx, bars, mult, lookback=20):
    if idx < lookback: return False
    avg = sum((bars[i][2] - bars[i][3]) for i in range(idx - lookback, idx)) / lookback
    return avg > 0 and rng(bars[idx]) >= mult * avg
def f_body_vs_trig(c2, c1, ratio): return body(c1) > 0 and body(c2) >= ratio * body(c1)
def f_close_extreme(c2, c1, threshold=0.25):
    r = rng(c2);
    if r <= 0: return False
    pos = (c2[4] - c2[3]) / r; d = direction(c1)
    return (d == 1 and pos >= 1 - threshold) or (d == -1 and pos <= threshold)


# ── trade simulation ──
def pnl_usd(entry, curr, dir_sign, lots): return (curr - entry) * dir_sign * lots * CONTRACT_SIZE

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
            return {"outcome": "TIMEOUT", "pnl_usd": round(pnl_usd(entry_price, cur, dir_sign, lots), 2)}
        cur = t[1] if dir_sign == 1 else t[2]
        pnl = pnl_usd(entry_price, cur, dir_sign, lots)
        if pnl > peak: peak = pnl
        if pnl <= -MAIN_CATASTROPHIC:
            return {"outcome": "CATASTROPHIC", "pnl_usd": round(pnl, 2)}
        if pnl <= -MAIN_SL_USD:
            return {"outcome": "SL", "pnl_usd": round(pnl, 2)}
        if peak >= MAIN_TRAIL_TRIG and (peak - pnl) >= MAIN_TRAIL_DROP:
            return {"outcome": "TRAIL_WIN", "pnl_usd": round(pnl, 2)}
        last_pnl = pnl
    return {"outcome": "TRUNCATED", "pnl_usd": round(last_pnl, 2)}


def wilson_ci(wins, n, z=1.96):
    if n == 0: return [0.0, 0.0]
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return [round(max(0, (centre - half)) * 100, 1), round(min(1, (centre + half)) * 100, 1)]


# ── runner ──
def run_with_filter(name, predicate, bars, ticks, candidates):
    """candidates = list of (idx, dir) — patterns that already passed LIVE stack.
    predicate(c2, c1, idx, bars) -> bool, applied as final gate.
    """
    results = []
    for idx, td in candidates:
        c1 = bars[idx - 1]; c2 = bars[idx]
        try:
            keep = predicate(c2, c1, idx, bars)
        except Exception:
            keep = False
        if not keep: continue
        entry_dt = bars[idx + 1][0]
        cutoff = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC + 30)
        future = [t for t in ticks if entry_dt - timedelta(seconds=2) <= t[0] <= cutoff]
        if not future: continue
        out = simulate_main(entry_dt, td, future)
        results.append(out)

    n = len(results)
    if n == 0: return {"name": name, "n": 0}
    wins = sum(1 for r in results if r.get("outcome") == "TRAIL_WIN")
    sl   = sum(1 for r in results if r.get("outcome") == "SL")
    pnls = [r.get("pnl_usd", 0) for r in results if "pnl_usd" in r]
    total = sum(pnls); avg = total / n
    return {"name": name, "n": n, "wr_pct": round(wins/n*100, 1), "ci": wilson_ci(wins, n),
            "sl_pct": round(sl/n*100, 1), "total_pnl": round(total, 0), "avg_pnl": round(avg, 2)}


def main():
    print(f"Loading ticks from {TICK_CSV.name}...")
    ticks = parse_ticks(TICK_CSV)
    bars = build_m1_bars(ticks)
    print(f"Parsed {len(ticks):,} ticks -> {len(bars):,} M1 bars")
    print(f"LIVE stack: shano2c + UHV-in-{UHV_LOOKBACK} + swept + trigger-past-UHV-{TRIGGER_PAST_UHV}pt + effort-result-{EFFORT_BODY_MIN}/{EFFORT_WICK_MAX} + 2bar-trend + spread-1.2x")
    print()

    # Build candidate list: bars that pass the FULL LIVE stack
    candidates = []
    for i in range(UHV_LOOKBACK + 2, len(bars) - 1):
        passed, td, _ = passes_live_stack(bars, i)
        if passed: candidates.append((i, td))
    print(f"Patterns surviving LIVE stack: {len(candidates)}")
    print()

    if not candidates:
        print("No patterns survived. Aborting.")
        return

    tests = [
        ("LIVE stack baseline (no c2 filter)",      lambda c2,c1,i,bars: True),
        ("+ c2 strength: body>=30%",                 lambda c2,c1,i,bars: f_strength(c2, 0.30)),
        ("+ c2 strength: body>=50%",                 lambda c2,c1,i,bars: f_strength(c2, 0.50)),
        ("+ c2 strength: body>=70%",                 lambda c2,c1,i,bars: f_strength(c2, 0.70)),
        ("+ c2 momentum: body>=0.5pt",               lambda c2,c1,i,bars: f_momentum(c2, 0.5)),
        ("+ c2 momentum: body>=1.0pt",               lambda c2,c1,i,bars: f_momentum(c2, 1.0)),
        ("+ c2 momentum: body>=2.0pt",               lambda c2,c1,i,bars: f_momentum(c2, 2.0)),
        ("+ c2 speed: density>=1.2x",                lambda c2,c1,i,bars: f_speed(i, bars, 1.2)),
        ("+ c2 speed: density>=1.5x",                lambda c2,c1,i,bars: f_speed(i, bars, 1.5)),
        ("+ c2 range: >=1.0x ATR20",                 lambda c2,c1,i,bars: f_range_atr(i, bars, 1.0)),
        ("+ c2 range: >=1.5x ATR20",                 lambda c2,c1,i,bars: f_range_atr(i, bars, 1.5)),
        ("+ c2 body >= 0.5x c1 body",                lambda c2,c1,i,bars: f_body_vs_trig(c2, c1, 0.5)),
        ("+ c2 body >= 1.0x c1 body",                lambda c2,c1,i,bars: f_body_vs_trig(c2, c1, 1.0)),
        ("+ c2 close in top/bot 25%",                lambda c2,c1,i,bars: f_close_extreme(c2, c1, 0.25)),
        ("+ c2 close in top/bot 15%",                lambda c2,c1,i,bars: f_close_extreme(c2, c1, 0.15)),
        # Combos
        ("+ momentum>=1.0pt + close25",              lambda c2,c1,i,bars: f_momentum(c2,1.0) and f_close_extreme(c2,c1,0.25)),
        ("+ momentum>=2.0pt + close25",              lambda c2,c1,i,bars: f_momentum(c2,2.0) and f_close_extreme(c2,c1,0.25)),
        ("+ strength70 + momentum>=1.0pt",           lambda c2,c1,i,bars: f_strength(c2,0.70) and f_momentum(c2,1.0)),
    ]

    print(f"{'filter':<50s}  {'n':>4s}  {'WIN':>6s}  {'CI95':>14s}  {'SL':>5s}  {'total $':>10s}  {'avg $':>7s}  {'lift':>6s}")
    print("-" * 120)

    baseline_wr = None
    for name, fn in tests:
        s = run_with_filter(name, fn, bars, ticks, candidates)
        if s["n"] == 0:
            print(f"{name:<50s}  {'0':>4s}  no patterns")
            continue
        if baseline_wr is None: baseline_wr = s["wr_pct"]
        lift = s["wr_pct"] - baseline_wr
        print(f"{s['name']:<50s}  {s['n']:>4d}  {s['wr_pct']:>5.1f}%  {str(s['ci']):>14s}  {s['sl_pct']:>4.1f}%  ${s['total_pnl']:>+9.0f}  ${s['avg_pnl']:>+5.2f}  {lift:>+5.1f}")


if __name__ == "__main__":
    main()
