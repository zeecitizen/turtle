"""shano_x_candle_test.py — Sweep Shano's pattern with X confirmation candles.

Shano's current pattern (X=2):
  Bar T-1 = bigness trigger: body >= 1.5x body of bar T-2
  Bar T   = same direction as trigger (any size)
  Fire probe at start of bar T+1 in trigger direction

Test sweeps X from 1 to 6:
  X=1: bigness trigger alone, fire next bar (no confirms)
  X=2: bigness + 1 confirm (CURRENT LIVE)
  X=3: bigness + 2 confirms
  X=4..6: more confirms

Two firing paths tested per X:
  Path A: fire main 0.30 lot at start of bar T+1 directly
  Path B: fire probe 0.01 lot, if it confirms (+$0.45 in <=7s) fire main at confirm time

Outcome: per-X WR, total P&L, average P&L, sample size + 95% CI.
"""
from __future__ import annotations
import csv, math
from datetime import datetime, timedelta
from pathlib import Path

TICK_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-01.csv")

# ── Probe & main economics (matches LIVE config) ──
PROBE_LOTS         = 0.01
MAIN_LOTS          = 0.30
CONTRACT_SIZE      = 100
PROBE_CONFIRM_USD  = 0.45
PROBE_FAIL_USD     = 3.00
PROBE_TIMEOUT_SEC  = 7      # Shano-Zee: ~7s confirm window (matches ProbeTimeout in EA on first scan)
MAIN_TRAIL_TRIG    = 25.0
MAIN_TRAIL_DROP    = 8.0
MAIN_SL_USD        = 10.0
MAIN_CATASTROPHIC  = 50.0
MAIN_HORIZON_SEC   = 600
LATENCY_MS         = 250

# ── Shano pattern parameters ──
BIGNESS_RATIO      = 1.5    # current body >= 1.5x prev body


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
    """Returns list of (bar_dt, open, high, low, close, n_ticks)."""
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
def direction(bar): return -1 if bar[4] < bar[1] else 1 if bar[4] > bar[1] else 0


def shano_x_pattern(bars, idx, X):
    """At bar idx (= last confirm bar), check if pattern of X bars is satisfied.
    Returns trigger direction (-1 or +1) or None.
    """
    if idx < X: return None
    trigger_idx = idx - X + 1
    if trigger_idx < 1: return None
    trigger = bars[trigger_idx]
    prev = bars[trigger_idx - 1]
    if body(prev) <= 0: return None
    if body(trigger) < BIGNESS_RATIO * body(prev): return None
    trig_dir = direction(trigger)
    if trig_dir == 0: return None
    for i in range(trigger_idx + 1, idx + 1):
        if direction(bars[i]) != trig_dir:
            return None
    return trig_dir


def pnl_usd(entry, curr, dir_sign, lots):
    return (curr - entry) * dir_sign * lots * CONTRACT_SIZE


def find_first_tick_at_or_after(ticks, target_dt):
    for t in ticks:
        if t[0] >= target_dt:
            return t
    return None


def simulate_main(entry_dt, dir_sign, ticks_after, lots=MAIN_LOTS):
    target = entry_dt + timedelta(milliseconds=LATENCY_MS)
    fill = find_first_tick_at_or_after(ticks_after, target)
    if fill is None:
        return {"outcome": "NO_FILL"}
    fill_dt, bid, ask = fill
    entry_price = ask if dir_sign == 1 else bid
    deadline = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC)
    peak = 0.0
    last_pnl = 0.0
    for t in ticks_after:
        if t[0] < fill_dt: continue
        if t[0] > deadline:
            cur = t[1] if dir_sign == 1 else t[2]
            return {"outcome": "TIMEOUT", "pnl_usd": round(pnl_usd(entry_price, cur, dir_sign, lots), 2),
                    "peak_usd": round(peak, 2), "elapsed_sec": (t[0] - entry_dt).total_seconds()}
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


def simulate_probe_then_main(entry_dt, dir_sign, ticks_after):
    """Open 0.01 probe; if it confirms within PROBE_TIMEOUT_SEC, fire main at confirm time."""
    target = entry_dt + timedelta(milliseconds=LATENCY_MS)
    fill = find_first_tick_at_or_after(ticks_after, target)
    if fill is None:
        return {"probe_outcome": "NO_FILL"}
    fill_dt, bid, ask = fill
    entry_price = ask if dir_sign == 1 else bid
    deadline = entry_dt + timedelta(seconds=PROBE_TIMEOUT_SEC)
    confirm_dt = None
    for t in ticks_after:
        if t[0] < fill_dt: continue
        if t[0] > deadline:
            return {"probe_outcome": "TIMEOUT"}
        cur = t[1] if dir_sign == 1 else t[2]
        pnl = pnl_usd(entry_price, cur, dir_sign, PROBE_LOTS)
        if pnl >= PROBE_CONFIRM_USD:
            confirm_dt = t[0]; break
        if pnl <= -PROBE_FAIL_USD:
            return {"probe_outcome": "FAIL"}
    if confirm_dt is None:
        return {"probe_outcome": "TIMEOUT"}
    main = simulate_main(confirm_dt, dir_sign, ticks_after)
    return {"probe_outcome": "CONFIRM", "confirm_dt": confirm_dt.isoformat(), "main": main}


def wilson_ci(wins, n, z=1.96):
    if n == 0: return [0.0, 0.0]
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return [round(max(0, (centre - half)) * 100, 1), round(min(1, (centre + half)) * 100, 1)]


def main():
    print(f"Loading ticks from {TICK_CSV.name}...")
    ticks = parse_ticks(TICK_CSV)
    bars = build_m1_bars(ticks)
    print(f"Parsed {len(ticks):,} ticks -> {len(bars):,} M1 bars")
    print(f"BIGNESS_RATIO={BIGNESS_RATIO}  MAIN_LOTS={MAIN_LOTS}  trail={MAIN_TRAIL_TRIG}/{MAIN_TRAIL_DROP}  SL=${MAIN_SL_USD}")
    print()

    for X in range(1, 7):
        path_a_results, path_b_results = [], []
        for i in range(X, len(bars) - 1):
            d = shano_x_pattern(bars, i, X)
            if d is None: continue
            # Entry at start of bar i+1
            entry_dt = bars[i + 1][0]
            cutoff = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC + 30)
            future_ticks = [t for t in ticks if entry_dt - timedelta(seconds=2) <= t[0] <= cutoff]
            if not future_ticks: continue

            # Path A: fire main directly
            a = simulate_main(entry_dt, d, future_ticks)
            path_a_results.append({"bar_time": bars[i][0].isoformat(), "dir": d, "main": a})

            # Path B: fire probe then main on confirm
            b = simulate_probe_then_main(entry_dt, d, future_ticks)
            path_b_results.append({"bar_time": bars[i][0].isoformat(), "dir": d, **b})

        n_a = len(path_a_results)
        if n_a == 0:
            print(f"X={X}: no Shano patterns matched in dataset")
            continue

        # Path A summary
        wins = sum(1 for r in path_a_results if r["main"].get("outcome") == "TRAIL_WIN")
        sl = sum(1 for r in path_a_results if r["main"].get("outcome") == "SL")
        cat = sum(1 for r in path_a_results if r["main"].get("outcome") == "CATASTROPHIC")
        timeo = sum(1 for r in path_a_results if r["main"].get("outcome") == "TIMEOUT")
        pnls = [r["main"].get("pnl_usd", 0) for r in path_a_results if "pnl_usd" in r["main"]]
        total_a = sum(pnls); avg_a = total_a / n_a
        wr_a = wins / n_a * 100; ci_a = wilson_ci(wins, n_a)

        # Path B summary
        b_confirmed = [r for r in path_b_results if r.get("probe_outcome") == "CONFIRM"]
        b_main_wins = sum(1 for r in b_confirmed if r["main"].get("outcome") == "TRAIL_WIN")
        b_main_pnls = [r["main"].get("pnl_usd", 0) for r in b_confirmed if "pnl_usd" in r["main"]]
        n_b_confirms = len(b_confirmed)
        n_b_total = len(path_b_results)
        confirm_rate = n_b_confirms / n_b_total * 100 if n_b_total else 0
        wr_b = b_main_wins / n_b_confirms * 100 if n_b_confirms else 0
        ci_b = wilson_ci(b_main_wins, n_b_confirms)
        total_b = sum(b_main_pnls)
        avg_b = total_b / n_b_confirms if n_b_confirms else 0

        print(f"X={X}  patterns={n_a}")
        print(f"   Path A (fire main directly):  WIN={wr_a:5.1f}% (CI {ci_a})  SL={sl/n_a*100:5.1f}%  cat={cat/n_a*100:4.1f}%  TO={timeo/n_a*100:5.1f}%   total=${total_a:>+7.0f}  avg/trade=${avg_a:>+5.2f}")
        print(f"   Path B (probe->confirm->main): probe_confirm={confirm_rate:5.1f}%  n_mains={n_b_confirms}  main_WIN={wr_b:5.1f}% (CI {ci_b})  total=${total_b:>+7.0f}  avg/main=${avg_b:>+5.2f}")
        print()


if __name__ == "__main__":
    main()
