"""
drawdown_analysis.py — analyze worst-case scenarios across the 64-day
simulated dataset. Specifically:
  - Longest losing streak (consecutive losses)
  - Maximum drawdown from peak equity
  - Per-day P&L distribution shape
  - Days with multiple back-to-back catastrophic losses

Both v3.30 baseline AND v3.40 (with smart cut) are simulated for comparison.
"""
from __future__ import annotations
import csv
import os
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

PNL_PER_POINT = 100.0 * 0.10
MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
EXIT_HORIZON_BARS = 30
PEAK_BANK_USD = 1.0
PEAK_DROP_USD = 0.5
CUT_LOSS_USD = -2.0
CUT_PEAK_USD = 1.0
CUT_MIN_BARS = 1


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float; vol: int
    @property
    def is_green(self): return self.close > self.open
    @property
    def is_red(self):   return self.close < self.open


def load_bars(p):
    bars = []
    with open(p) as f:
        for r in csv.DictReader(f):
            bars.append(Bar(
                time=datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]), vol=int(r["tick_volume"]),
            ))
    bars.sort(key=lambda b: b.time)
    return bars


def detect(bars, idx_bo):
    bo = bars[idx_bo]
    if bo.is_green:
        reds = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.high >= bo.close: break
            if c.is_red: reds.append((k, c))
        if not reds: return None
        k_uhv, uhv = max(reds, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo.close <= uhv.high or bo.vol >= uhv.vol: return None
        return {"side":"buy","bo":bo,"uhv":uhv}
    if bo.is_red:
        greens = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.low <= bo.close: break
            if c.is_green: greens.append((k, c))
        if not greens: return None
        k_uhv, uhv = max(greens, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo.close >= uhv.low or bo.vol >= uhv.vol: return None
        return {"side":"sell","bo":bo,"uhv":uhv}
    return None


def simulate_pnl(bars, idx_bo, sig, with_smart_cut=False):
    """Return signed P&L (USD) for this trade."""
    side = sig["side"]
    entry = sig["bo"].close
    sl = sig["uhv"].low if side == "buy" else sig["uhv"].high
    sl_pnl = (sl - entry) * PNL_PER_POINT if side == "buy" else (entry - sl) * PNL_PER_POINT
    peak = 0.0
    for k_off, k in enumerate(range(idx_bo + 1, min(idx_bo + 1 + EXIT_HORIZON_BARS, len(bars))), start=1):
        b = bars[k]
        if side == "buy":
            fav = (b.high - entry) * PNL_PER_POINT
            adv = (b.low - entry) * PNL_PER_POINT
            sl_hit = b.low <= sl
        else:
            fav = (entry - b.low) * PNL_PER_POINT
            adv = (entry - b.high) * PNL_PER_POINT
            sl_hit = b.high >= sl
        new_peak = max(peak, fav)
        if new_peak >= PEAK_BANK_USD:
            return new_peak - PEAK_DROP_USD
        if sl_hit:
            return sl_pnl
        if with_smart_cut and k_off >= CUT_MIN_BARS and adv <= CUT_LOSS_USD and new_peak < CUT_PEAK_USD:
            return CUT_LOSS_USD
        peak = new_peak
    return 0


def main():
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars")

    last_uhv = None; last_side = None
    trades_v3 = []
    trades_v4 = []
    for i in range(MAX_LOOKBACK + 5, len(bars) - EXIT_HORIZON_BARS):
        sig = detect(bars, i)
        if not sig: continue
        if sig["uhv"].time == last_uhv and sig["side"] == last_side: continue
        last_uhv = sig["uhv"].time
        last_side = sig["side"]
        t_v3 = simulate_pnl(bars, i, sig, with_smart_cut=False)
        t_v4 = simulate_pnl(bars, i, sig, with_smart_cut=True)
        trades_v3.append((sig["bo"].time, t_v3))
        trades_v4.append((sig["bo"].time, t_v4))

    print(f"Simulated {len(trades_v3)} trades")
    print()

    def analyze(label, trades):
        print(f"--- {label} ---")
        pnls = [t[1] for t in trades]
        net = sum(pnls)
        print(f"  Net P&L: ${net:+.2f}")

        # Longest losing streak
        max_streak = 0; cur_streak = 0
        for p in pnls:
            if p < 0:
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
            else:
                cur_streak = 0
        print(f"  Longest losing streak: {max_streak}")

        # Equity curve + max drawdown
        equity = 0; peak_eq = 0; max_dd = 0
        for p in pnls:
            equity += p
            peak_eq = max(peak_eq, equity)
            dd = peak_eq - equity
            max_dd = max(max_dd, dd)
        print(f"  Max drawdown from peak equity: ${max_dd:.2f}")
        print(f"  Peak equity:                  ${peak_eq:.2f}")
        print(f"  Drawdown ratio: {max_dd/peak_eq*100:.1f}%")

        # Per-day distribution
        by_day = {}
        for t, p in trades:
            d = t.date()
            by_day[d] = by_day.get(d, 0) + p
        day_pnls = list(by_day.values())
        prof_days = sum(1 for p in day_pnls if p > 0)
        losing_days = sum(1 for p in day_pnls if p < 0)
        print(f"  Profitable days: {prof_days}/{len(day_pnls)} ({prof_days/len(day_pnls)*100:.0f}%)")
        print(f"  Worst day: ${min(day_pnls):+.2f}")
        print(f"  Best day:  ${max(day_pnls):+.2f}")
        print(f"  Median day P&L: ${statistics.median(day_pnls):+.2f}")
        print()
        return day_pnls

    days_v3 = analyze("v3.30 baseline (no smart cut)", trades_v3)
    days_v4 = analyze("v3.40 with smart cut", trades_v4)

    # Days where smart cut helped most
    print("Top 5 days where smart cut improved P&L most:")
    deltas = []
    by_day_v3 = {}
    by_day_v4 = {}
    for t, p in trades_v3:
        by_day_v3.setdefault(t.date(), 0); by_day_v3[t.date()] += p
    for t, p in trades_v4:
        by_day_v4.setdefault(t.date(), 0); by_day_v4[t.date()] += p
    for d in by_day_v3:
        deltas.append((d, by_day_v4[d] - by_day_v3[d], by_day_v3[d], by_day_v4[d]))
    deltas.sort(key=lambda x: -x[1])
    for d, delta, v3, v4 in deltas[:5]:
        print(f"  {d}: v3.30=${v3:+.2f} → v3.40=${v4:+.2f}  (Δ ${delta:+.2f})")
    print("\nBottom 5 (where smart cut hurt most):")
    for d, delta, v3, v4 in deltas[-5:]:
        print(f"  {d}: v3.30=${v3:+.2f} → v3.40=${v4:+.2f}  (Δ ${delta:+.2f})")


if __name__ == "__main__":
    main()
