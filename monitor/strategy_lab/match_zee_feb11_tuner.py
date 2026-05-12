"""
match_zee_feb11_tuner.py — find exit parameters that make the EA's behavior
on Zee's 20 Feb-11 textbook entries match his actual exits.

For each (peak_bank, peak_drop, early_stop, early_guard, time_stop) combo:
  - Simulate v3.30-style exits starting from each of Zee's 20 entries
  - Sum simulated P&L
  - Count "match-Zee" hits (exit time within ±2 min, pnl within ±$3)
  - Find the largest simulated loss

Goal: minimize loss-divergence (per-trade max-loss should be close to
Zee's -$1.60 cap), maximize total P&L match.

OHLC-approximation caveat applies — sim is conservative.
"""
from __future__ import annotations
import csv
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

PNL_PER_POINT = 100.0 * 0.10  # $10 per 0.10 lot per point

# Zee's 20 textbook lesson-2 setups on Feb 11: (entry_time, side, entry_px,
# close_time, close_px, actual_pnl)
ZEE_TRADES = [
    ("01:59:04", "buy",  5042.17, "02:00:43", 5042.96,  6.65),
    ("02:09:38", "sell", 5040.68, "02:10:18", 5039.29, 11.69),
    ("02:29:02", "buy",  5039.03, "02:30:28", 5041.41, 20.01),
    ("16:49:07", "buy",  5047.93, "16:51:03", 5049.96, 17.12),
    ("16:52:21", "buy",  5050.77, "16:52:27", 5051.82,  8.85),
    ("16:54:10", "buy",  5056.74, "16:54:20", 5057.72,  8.26),
    ("16:58:03", "buy",  5064.26, "16:58:27", 5064.94,  5.73),
    ("17:02:45", "buy",  5055.71, "17:03:51", 5062.23, 54.93),
    ("17:36:11", "buy",  5056.53, "17:36:26", 5056.92,  3.29),
    ("17:36:13", "buy",  5057.05, "17:52:56", 5058.77, 14.50),
    ("17:37:26", "buy",  5045.82, "17:40:02", 5046.66,  7.08),
    ("17:49:59", "buy",  5048.32, "17:52:33", 5054.58, 52.78),
    ("18:24:18", "buy",  5059.26, "18:28:33", 5060.27,  8.51),
    ("18:41:50", "buy",  5078.10, "19:06:41", 5077.93, -1.43),
    ("19:20:34", "sell", 5084.21, "19:20:40", 5082.52, 14.21),
    ("19:26:06", "sell", 5089.16, "19:26:50", 5087.43, 14.55),
    ("19:29:31", "buy",  5086.34, "19:39:03", 5086.44,  0.84),
    ("19:36:19", "buy",  5082.91, "19:37:19", 5084.17, 10.60),
    ("19:38:39", "buy",  5083.28, "19:38:50", 5084.59, 11.02),
    ("19:38:59", "buy",  5086.33, "19:39:03", 5086.44,  0.92),
]


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float


def load_bars(path):
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            bars.append(Bar(
                time=datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
            ))
    bars.sort(key=lambda b: b.time)
    return bars


def find_entry_bar(bars, entry_dt):
    """Find M1 bar covering entry_dt."""
    target = entry_dt.replace(second=0)
    for i, b in enumerate(bars):
        if b.time == target:
            return i
    return None


def find_uhv(bars, idx_bo, side, max_lookback=60):
    """Replicate v3.30 detector's UHV search. Returns the Bar of the UHV,
    or None. Walks back from breakout bar idx_bo for the highest-volume
    RED bar (buy) or GREEN bar (sell) between swing high/low and breakout.
    """
    # Need vol on Bar. Use a dict-style read from the underlying CSV.
    # Cheat: we kept open/high/low/close but not vol. So skip — best effort.
    # Without vol we can't pick highest-vol, so use most-recent red/green.
    bo = bars[idx_bo]
    threshold = bo.close
    for j in range(1, max_lookback + 1):
        k = idx_bo - j
        if k < 0: break
        c = bars[k]
        if side == "buy":
            if c.high >= threshold: break
            if c.close < c.open: return c  # nearest red — proxy for UHV
        else:
            if c.low <= threshold: break
            if c.close > c.open: return c
    return None


def simulate_exit(bars, entry_idx, entry_price, side, sl_price, cfg):
    """Simulate exit given config. Returns (exit_time, exit_price, pnl, reason).

    Exit logic, evaluated at each held bar's close:
      1. SL hit (worst-case fill at sl_price)
      2. Hard time stop (cfg.time_stop)
      3. Stale-loser stop (cfg.stale_secs): if elapsed >= stale_secs AND
         close_pnl <= stale_threshold, exit. Models Zee's "watch ~30s,
         if it's not working bail" behavior.
      4. Conditional early-stop (cfg.early_stop / cfg.early_guard)
      5. Peak-trail (cfg.peak_bank / cfg.peak_drop)
    """
    peak_pnl = 0.0
    entry_time = bars[entry_idx].time
    for k in range(entry_idx + 1, min(entry_idx + 1 + 60, len(bars))):
        b = bars[k]
        elapsed = (b.time - entry_time).total_seconds()

        # Hard time stop
        if cfg["time_stop"] > 0 and elapsed >= cfg["time_stop"]:
            pnl = (b.open - entry_price) * PNL_PER_POINT if side == "buy" else (entry_price - b.open) * PNL_PER_POINT
            return b.time, b.open, pnl, "time_stop"

        # SL hit (catastrophic)
        if side == "buy" and b.low <= sl_price:
            return b.time, sl_price, (sl_price - entry_price) * PNL_PER_POINT, "sl"
        if side == "sell" and b.high >= sl_price:
            return b.time, sl_price, (entry_price - sl_price) * PNL_PER_POINT, "sl"

        # Bar close pnl
        if side == "buy":
            close_pnl = (b.close - entry_price) * PNL_PER_POINT
        else:
            close_pnl = (entry_price - b.close) * PNL_PER_POINT

        # Stale-loser stop: if been holding >= stale_secs and pnl is below
        # stale_threshold, bail out. Approximates "Zee gives 30-60s then bails
        # if not working" behavior.
        if cfg.get("stale_secs", 0) > 0 and elapsed >= cfg["stale_secs"]:
            if close_pnl <= cfg.get("stale_threshold", 0):
                return b.time, b.close, close_pnl, "stale"

        # Conditional early-stop
        if cfg["early_stop"] > 0:
            apply_cut = (cfg["early_guard"] == 0 or peak_pnl < cfg["early_guard"])
            if apply_cut and close_pnl <= -cfg["early_stop"]:
                return b.time, b.close, close_pnl, "early_stop"

        peak_pnl = max(peak_pnl, close_pnl)

        # Peak-trail
        if peak_pnl >= cfg["peak_bank"] and close_pnl <= (peak_pnl - cfg["peak_drop"]):
            return b.time, b.close, close_pnl, "peak_trail"

    last = bars[min(entry_idx + 60, len(bars) - 1)]
    pnl = (last.close - entry_price) * PNL_PER_POINT if side == "buy" else (entry_price - last.close) * PNL_PER_POINT
    return last.time, last.close, pnl, "end"


def score_config(bars, cfg):
    """Returns (sum_pnl, max_loss, n_matches_zee_within_2min, results)."""
    results = []
    for hms, side, entry_px, c_hms, c_px, actual_pnl in ZEE_TRADES:
        et = datetime.strptime(f"2026.02.11 {hms}", "%Y.%m.%d %H:%M:%S")
        ct = datetime.strptime(f"2026.02.11 {c_hms}", "%Y.%m.%d %H:%M:%S")
        idx = find_entry_bar(bars, et)
        if idx is None: continue
        # SL = UHV.low for buy, UHV.high for sell — but we don't have UHV here.
        # Approximation: use bar.low/high N bars back (15) as SL.
        lookback = 15
        win = bars[max(0, idx - lookback):idx]
        if side == "buy":
            sl_price = min(b.low for b in win) if win else entry_px - 5
        else:
            sl_price = max(b.high for b in win) if win else entry_px + 5
        exit_t, exit_px, sim_pnl, reason = simulate_exit(
            bars, idx, entry_px, side, sl_price, cfg)
        results.append({
            "trade": (hms, side, entry_px),
            "zee_close": ct, "zee_pnl": actual_pnl,
            "sim_close": exit_t, "sim_pnl": sim_pnl, "reason": reason,
        })
    total_pnl = sum(r["sim_pnl"] for r in results)
    max_loss = min(r["sim_pnl"] for r in results)
    matches = sum(1 for r in results if abs((r["sim_close"] - r["zee_close"]).total_seconds()) <= 120)
    return total_pnl, max_loss, matches, results


def main():
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars")

    # Zee's actual totals for the 20 textbook trades
    zee_total = sum(t[5] for t in ZEE_TRADES)
    zee_max_loss = min(t[5] for t in ZEE_TRADES)
    print(f"Zee actual: total ${zee_total:+.2f}, max loss ${zee_max_loss:.2f} (across 20 textbook setups)")
    print()

    # Grid search — focused on configs likely to help loss-cap
    bank_options          = [1.0, 2.0, 3.0]
    drop_options          = [0.5, 1.0]
    stale_secs_options    = [0, 60, 120, 180, 300]   # 0 = stale rule off
    stale_thresh_options  = [-3.0, -1.0, 0.0, 1.0]   # bail if pnl <= this
    time_options          = [1800]                   # 30-min hard backstop

    print(f"{'bank':<5} {'drop':<5} {'stale_s':<8} {'stale_T':<8} {'tstop':<6} {'sum_pnl':<10} {'max_loss':<10} {'matches':<8}")
    print("-" * 80)

    best = []
    n_tested = 0
    for bank in bank_options:
        for drop in drop_options:
            if drop >= bank: continue
            for stale_s in stale_secs_options:
                for stale_t in stale_thresh_options:
                    if stale_s == 0 and stale_t != 0: continue
                    for tstop in time_options:
                        cfg = {"peak_bank": bank, "peak_drop": drop,
                               "early_stop": 0, "early_guard": 0,
                               "time_stop": tstop,
                               "stale_secs": stale_s, "stale_threshold": stale_t}
                        total, ml, matches, _ = score_config(bars, cfg)
                        n_tested += 1
                        best.append((total, ml, matches, cfg))

    print(f"Tested {n_tested} configs.")
    print()
    def fmt(cfg):
        return f"{cfg['peak_bank']:<5} {cfg['peak_drop']:<5} {cfg.get('stale_secs',0):<8} {cfg.get('stale_threshold',0):<8} {cfg['time_stop']:<6}"

    # Top 10 by sum_pnl
    best_pnl = sorted(best, key=lambda x: -x[0])[:10]
    print(f"\nTOP 10 by total P&L (Zee actual: ${zee_total:+.2f}, max-loss ${zee_max_loss:.2f}):")
    print(f"{'bank':<5} {'drop':<5} {'stale_s':<8} {'stale_T':<8} {'tstop':<6} {'sum_pnl':<10} {'max_loss':<10} {'matches':<8}")
    for total, ml, matches, cfg in best_pnl:
        print(f"{fmt(cfg)} ${total:<+9.2f} ${ml:<+9.2f} {matches:<8}")

    print()
    # Top 10 by closest max_loss to Zee's
    best_loss = sorted(best, key=lambda x: (abs(x[1] - zee_max_loss), -x[0]))[:10]
    print(f"\nTOP 10 by closest max-loss to Zee's -$1.43:")
    print(f"{'bank':<5} {'drop':<5} {'stale_s':<8} {'stale_T':<8} {'tstop':<6} {'sum_pnl':<10} {'max_loss':<10} {'matches':<8}")
    for total, ml, matches, cfg in best_loss:
        print(f"{fmt(cfg)} ${total:<+9.2f} ${ml:<+9.2f} {matches:<8}")

    # Best blended: high pnl AND tight loss
    print()
    blended = sorted(best, key=lambda x: -(x[0] + x[1] * 10))[:10]  # penalize big losses 10x
    print(f"\nTOP 10 by BLENDED score (pnl + 10*max_loss):")
    print(f"{'bank':<5} {'drop':<5} {'stale_s':<8} {'stale_T':<8} {'tstop':<6} {'sum_pnl':<10} {'max_loss':<10} {'matches':<8}")
    for total, ml, matches, cfg in blended:
        print(f"{fmt(cfg)} ${total:<+9.2f} ${ml:<+9.2f} {matches:<8}")


if __name__ == "__main__":
    main()
