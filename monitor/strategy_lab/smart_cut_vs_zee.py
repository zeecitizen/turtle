"""
smart_cut_vs_zee.py — verify the smart-cut rule doesn't kill any of
Zee's 20 textbook Feb 11 trades.

For each of his 20 entries:
  - Find the detector signal closest to entry time
  - Walk forward bar-by-bar starting from the breakout bar
  - Check whether the smart cut (pnl<=-$2, peak<$1) would have fired
    BEFORE peak >= $1 (win) or SL hit (loss)

Three categories:
  - PASS: peak >= $1 first → trade banked normally (smart cut moot)
  - KILLED: cut fires before peak >= $1 → Zee's trade would have been cut
  - LOSS: SL hit before peak >= $1 (matches v3.30 behavior anyway)
"""
import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

PNL_PER_POINT = 100.0 * 0.10
MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
EXIT_HORIZON_BARS = 30

# Smart cut rule
CUT_LOSS_USD = -2.0
CUT_PEAK_USD = 1.0
CUT_MIN_BARS = 1

# Zee's 20 textbook Feb 11 setups
ZEE_FEB11 = [
    ("01:59:04", "buy",  5042.17, 6.65),
    ("02:09:38", "sell", 5040.68, 11.69),
    ("02:29:02", "buy",  5039.03, 20.01),
    ("16:49:07", "buy",  5047.93, 17.12),
    ("16:52:21", "buy",  5050.77, 8.85),
    ("16:54:10", "buy",  5056.74, 8.26),
    ("16:58:03", "buy",  5064.26, 5.73),
    ("17:02:45", "buy",  5055.71, 54.93),
    ("17:36:11", "buy",  5056.53, 3.29),
    ("17:36:13", "buy",  5057.05, 14.50),
    ("17:37:26", "buy",  5045.82, 7.08),
    ("17:49:59", "buy",  5048.32, 52.78),
    ("18:24:18", "buy",  5059.26, 8.51),
    ("18:41:50", "buy",  5078.10, -1.43),
    ("19:20:34", "sell", 5084.21, 14.21),
    ("19:26:06", "sell", 5089.16, 14.55),
    ("19:29:31", "buy",  5086.34, 0.84),
    ("19:36:19", "buy",  5082.91, 10.60),
    ("19:38:39", "buy",  5083.28, 11.02),
    ("19:38:59", "buy",  5086.33, 0.92),
]


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float; vol: int


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


def find_idx(bars, dt):
    target_min = dt.replace(second=0)
    for i, b in enumerate(bars):
        if b.time == target_min:
            return i
    return None


def find_uhv(bars, idx_bo, side):
    """Replicate v3.30 detector logic to find the UHV."""
    bo = bars[idx_bo]
    for j in range(1, MAX_LOOKBACK + 1):
        k = idx_bo - j
        if k < 0: break
        c = bars[k]
        if side == "buy" and c.high >= bo.close: break
        if side == "sell" and c.low <= bo.close: break
    # Best red (buy) or green (sell) in [swing+1, idx_bo-1]
    best = None
    for j in range(1, MAX_LOOKBACK + 1):
        k = idx_bo - j
        if k < 0: break
        c = bars[k]
        if side == "buy":
            if c.high >= bo.close: break
            if c.close < c.open and (best is None or c.vol > best.vol):
                best = c
        else:
            if c.low <= bo.close: break
            if c.close > c.open and (best is None or c.vol > best.vol):
                best = c
    return best


def simulate(bars, idx_bo, side, entry_price, uhv):
    """Walk forward from idx_bo+1 using smart-cut logic.
    Returns: outcome, exit_pnl, bar_at_exit
    """
    sl = uhv.low if side == "buy" else uhv.high
    peak = 0.0

    for k_off, k in enumerate(range(idx_bo + 1, min(idx_bo + 1 + EXIT_HORIZON_BARS, len(bars))), start=1):
        b = bars[k]
        # OHLC fav-first
        if side == "buy":
            fav = (b.high - entry_price) * PNL_PER_POINT
            adv = (b.low - entry_price) * PNL_PER_POINT
            sl_hit = b.low <= sl
        else:
            fav = (entry_price - b.low) * PNL_PER_POINT
            adv = (entry_price - b.high) * PNL_PER_POINT
            sl_hit = b.high >= sl
        new_peak = max(peak, fav)

        # Peak-trail engages first if peak >= $1
        if new_peak >= 1.0:
            return "WIN", new_peak - 0.5, k_off
        if sl_hit:
            sl_pnl = (sl - entry_price) * PNL_PER_POINT if side == "buy" else (entry_price - sl) * PNL_PER_POINT
            return "SL", sl_pnl, k_off
        # Smart cut check
        if k_off >= CUT_MIN_BARS and adv <= CUT_LOSS_USD and new_peak < CUT_PEAK_USD:
            return "CUT", CUT_LOSS_USD, k_off

        peak = new_peak

    return "TIME", 0, EXIT_HORIZON_BARS


def main():
    bars = load_bars(M1_CSV)
    print(f"Smart cut rule: pnl<=${CUT_LOSS_USD}, peak<${CUT_PEAK_USD}, min_bars={CUT_MIN_BARS}")
    print()
    print(f"{'Zee entry':<10} {'side':<5} {'Zee pnl':<9} {'sim outcome':<13} {'sim pnl':<9} {'bar':<5}")
    print("-" * 65)

    pass_n = killed_n = sl_n = 0
    total_killed_pnl = 0
    for hms, side, entry, zee_pnl in ZEE_FEB11:
        et = datetime.strptime(f"2026.02.11 {hms}", "%Y.%m.%d %H:%M:%S")
        idx = find_idx(bars, et)
        if idx is None:
            print(f"{hms:<10} {side:<5} ${zee_pnl:<+8.2f} (no bar found)")
            continue
        uhv = find_uhv(bars, idx, side)
        if uhv is None:
            print(f"{hms:<10} {side:<5} ${zee_pnl:<+8.2f} (no UHV found)")
            continue
        outcome, sim_pnl, bar = simulate(bars, idx, side, entry, uhv)
        if outcome == "WIN":
            pass_n += 1
        elif outcome == "CUT":
            killed_n += 1
            total_killed_pnl += sim_pnl
        elif outcome == "SL":
            sl_n += 1
        print(f"{hms:<10} {side:<5} ${zee_pnl:<+8.2f} {outcome:<13} ${sim_pnl:<+8.2f} {bar:<5}")

    print()
    print(f"Summary across Zee's 20 textbook Feb 11 trades:")
    print(f"  PASS (peak-trail bank):  {pass_n}/20  → would have won normally")
    print(f"  KILLED by smart cut:     {killed_n}/20  → smart cut fired at ${CUT_LOSS_USD}")
    print(f"  Hit SL anyway:            {sl_n}/20  → already losses in v3.30")
    print(f"\nIf {killed_n} of Zee's trades got smart-cut, total cost: ${total_killed_pnl:.2f}")
    print(f"Vs Zee's actual sum on those 20: ${sum(z[3] for z in ZEE_FEB11):+.2f}")


if __name__ == "__main__":
    main()
