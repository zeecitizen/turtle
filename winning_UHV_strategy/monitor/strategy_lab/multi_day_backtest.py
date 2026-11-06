"""
multi_day_backtest.py — simulate UhvSweepExhaustion v3.30 (lesson-2 entry +
peak-trail $1/$0.50 exit + 30-min time stop) over the full 88K-bar dataset
in Common\\Files\\rev_eng_m1.csv. Per-day P&L breakdown so we see if Feb 11
was an outlier or representative.

Notes:
  - Entry detection mirrors uhv_lesson2_detector.py exactly.
  - Exit emulation uses M1 OHLC sweep within each held bar (we can't see
    intra-tick, so we approximate: for buys, assume price hit bar.high then
    bar.low then bar.close in that order; for sells, low → high → close).
    This is intentionally pessimistic — real ticks would let peak-trail
    react to the actual peak before reversal.
  - Catastrophic SL: UHV.low (buy) / UHV.high (sell). If a held bar's
    extreme breaches this, we exit at that level (worst-case slippage).
  - One position at a time per lesson 2.

Usage: py monitor/strategy_lab/multi_day_backtest.py
"""
from __future__ import annotations
import csv
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

# v3.30 parameters
MAX_LOOKBACK         = 60
MAX_BARS_BACK        = 60
PEAK_BANK_USD        = 1.0
PEAK_DROP_USD        = 0.5
MAX_HOLD_SEC         = 1800
LOTS                 = 0.10
USD_PER_POINT_PER_LOT = 100.0  # XAUUSD: $1 per 0.01 lot per point ⇒ $10 per 0.10 lot per point

PNL_PER_POINT = LOTS * USD_PER_POINT_PER_LOT  # $10 per 0.10 lot per point


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float
    vol: int

    @property
    def is_green(self): return self.close > self.open
    @property
    def is_red(self):   return self.close < self.open


def load_bars(path: Path):
    bars = []
    with open(path, "r", encoding="ascii") as f:
        for r in csv.DictReader(f):
            bars.append(Bar(
                time=datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]),   close=float(r["close"]),
                vol=int(r["tick_volume"]),
            ))
    bars.sort(key=lambda b: b.time)
    return bars


def detect(bars, idx_bo):
    """v3.30 entry: lesson-2 UHV breakout. Returns dict or None."""
    bo = bars[idx_bo]

    # BUY
    if bo.is_green:
        reds = []
        found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.high >= bo.close:
                found_swing = True; break
            if c.is_red: reds.append((k, c))
        if not reds or not found_swing: return None
        k_uhv, uhv = max(reds, key=lambda kc: kc[1].vol)
        bars_back = idx_bo - k_uhv
        if bars_back > MAX_BARS_BACK: return None
        if bo.close <= uhv.high: return None
        if bo.vol >= uhv.vol: return None
        return {"side": "buy", "uhv": uhv, "bars_back": bars_back, "bo": bo}

    # SELL
    if bo.is_red:
        greens = []
        found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.low <= bo.close:
                found_swing = True; break
            if c.is_green: greens.append((k, c))
        if not greens or not found_swing: return None
        k_uhv, uhv = max(greens, key=lambda kc: kc[1].vol)
        bars_back = idx_bo - k_uhv
        if bars_back > MAX_BARS_BACK: return None
        if bo.close >= uhv.low: return None
        if bo.vol >= uhv.vol: return None
        return {"side": "sell", "uhv": uhv, "bars_back": bars_back, "bo": bo}

    return None


def simulate_trade(bars, entry_idx, sig):
    """Simulate v3.30 exit logic starting from the bar AFTER entry.
    Entry price = bo.close (we enter at breakout close).

    OHLC-only approximation:
      Per held bar, the peak P&L was hit at bar.high (buy) / bar.low (sell).
      If the bar's adverse extreme (low for buy / high for sell) crosses the
      "peak - drop" line in $ terms, peak-trail fires at the implied exit
      price (i.e. somewhere between peak extreme and close, on the way down).
      This is a reasonable approximation of how the real EA's tick-based
      trail behaves — much closer than treating high→low→close as ordered.

    Returns (close_idx, close_price, exit_reason).
    """
    side = sig["side"]
    entry_price = sig["bo"].close
    uhv = sig["uhv"]
    sl_price = uhv.low if side == "buy" else uhv.high

    peak_pnl = 0.0
    entry_time = sig["bo"].time

    # OHLC-only sim: use bar CLOSE as canonical price update. Peak and
    # peak-trail check happen on each bar close. This UNDERSHOOTS reality
    # (which checks every tick) but avoids the over-fire problem of
    # using bar.high as peak (every wick fires the trail).
    for k in range(entry_idx + 1, min(entry_idx + 1 + 60, len(bars))):
        b = bars[k]
        # Time stop (check at bar open time)
        if (b.time - entry_time).total_seconds() >= MAX_HOLD_SEC:
            return k, b.open, "time_stop"

        # SL hit during this bar (catastrophic backstop on extreme)
        if side == "buy" and b.low <= sl_price:
            return k, sl_price, "sl"
        if side == "sell" and b.high >= sl_price:
            return k, sl_price, "sl"

        # P&L at bar close
        if side == "buy":
            close_pnl = (b.close - entry_price) * PNL_PER_POINT
        else:
            close_pnl = (entry_price - b.close) * PNL_PER_POINT

        # Update peak with bar close (intra-bar peak ignored — too unknowable)
        peak_pnl = max(peak_pnl, close_pnl)

        # Peak-trail check at bar close
        if peak_pnl >= PEAK_BANK_USD and close_pnl <= (peak_pnl - PEAK_DROP_USD):
            return k, b.close, "peak_trail"

    # Ran out of bars
    last = bars[min(entry_idx + 60, len(bars) - 1)]
    return min(entry_idx + 60, len(bars) - 1), last.close, "end"


def main():
    if not M1_CSV.exists():
        print(f"ERROR: {M1_CSV} not found"); sys.exit(1)
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars  ({bars[0].time} → {bars[-1].time})")

    last_signal_uhv_time = None
    last_signal_side     = None
    open_until_idx       = -1
    trades = []

    for i in range(MAX_LOOKBACK + 5, len(bars) - 1):
        if i <= open_until_idx:
            continue
        sig = detect(bars, i)
        if not sig: continue
        # Dedup: same UHV + side as previous fire
        if sig["uhv"].time == last_signal_uhv_time and sig["side"] == last_signal_side:
            continue
        last_signal_uhv_time = sig["uhv"].time
        last_signal_side     = sig["side"]

        # Simulate the trade
        close_idx, close_price, reason = simulate_trade(bars, i, sig)
        entry_px = sig["bo"].close
        if sig["side"] == "buy":
            pnl_usd = (close_price - entry_px) * PNL_PER_POINT
        else:
            pnl_usd = (entry_px - close_price) * PNL_PER_POINT
        trades.append({
            "entry_time": sig["bo"].time, "side": sig["side"],
            "entry_px": entry_px, "close_time": bars[close_idx].time,
            "close_px": close_price, "pnl": pnl_usd, "reason": reason,
            "uhv_time": sig["uhv"].time, "bars_back": sig["bars_back"],
        })
        open_until_idx = close_idx  # one-at-a-time

    print(f"\nSimulated {len(trades)} trades")
    if not trades:
        return

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    total = sum(t["pnl"] for t in trades)
    print(f"Total: {len(trades)}  W: {len(wins)} ({len(wins)/len(trades)*100:.1f}%)  L: {len(losses)}")
    print(f"Net P&L: ${total:+.2f}")
    print(f"Avg win:  ${sum(t['pnl'] for t in wins)/len(wins):+.2f}" if wins else "")
    print(f"Avg loss: ${sum(t['pnl'] for t in losses)/len(losses):+.2f}" if losses else "")
    print(f"Worst loss: ${min(t['pnl'] for t in losses):.2f}" if losses else "")
    print(f"Best win:   ${max(t['pnl'] for t in wins):.2f}" if wins else "")
    from collections import Counter
    print(f"Exit reasons: {dict(Counter(t['reason'] for t in trades))}")

    # Per-day breakdown
    by_day = {}
    for t in trades:
        d = t["entry_time"].date()
        by_day.setdefault(d, []).append(t)
    print()
    print(f"{'date':<12} {'n':<4} {'W':<4} {'L':<4} {'WR%':<6} {'gross+':<8} {'gross-':<8} {'NET':<10} {'worst':<8}")
    print("-" * 80)
    for d in sorted(by_day):
        ts = by_day[d]
        w = sum(1 for t in ts if t["pnl"] > 0)
        l = sum(1 for t in ts if t["pnl"] < 0)
        gp = sum(t["pnl"] for t in ts if t["pnl"] > 0)
        gl = sum(t["pnl"] for t in ts if t["pnl"] < 0)
        net = gp + gl
        worst = min((t["pnl"] for t in ts), default=0)
        print(f"{d}   {len(ts):<4} {w:<4} {l:<4} {(w/len(ts)*100 if ts else 0):<6.1f} ${gp:<7.2f} ${gl:<7.2f} ${net:<+9.2f} ${worst:<7.2f}")

    print()
    print("Aggregate over all days:")
    days_pnl = [sum(t["pnl"] for t in by_day[d]) for d in by_day]
    print(f"  Profitable days: {sum(1 for p in days_pnl if p > 0)} / {len(days_pnl)}")
    print(f"  Median day P&L: ${statistics.median(days_pnl):+.2f}")
    print(f"  Worst day:  ${min(days_pnl):.2f}")
    print(f"  Best day:   ${max(days_pnl):.2f}")


if __name__ == "__main__":
    main()
