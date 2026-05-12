"""
smart_cut_validator.py — validate a CONDITIONAL early-cut rule:
  "Close if pnl <= -$3 AND peak < $0.30 AND bars_in_trade >= 2"

For every signal in the 17.8K dataset, walk forward bar-by-bar and:
  1. Track peak P&L
  2. Track bars elapsed
  3. Check the conditional cut on each bar

Classify each trade:
  - WIN (current logic): peak reached $1 before SL hit
  - LOSS (current logic): SL hit before peak >= $1
  - WIN-saved-by-cut: would've eventually won but cut fired early
    (peak was reaching toward $1 at the time of cut)
  - LOSS-prevented-by-cut: would've hit big SL, cut saved most of it

Goal: see net P&L impact of the conditional cut.
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

PNL_PER_POINT = 100.0 * 0.10  # $10 per 0.10 lot per point
MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
EXIT_HORIZON_BARS = 30

# Conditional cut rule
CUT_LOSS_USD = -3.0   # close if pnl <= this
CUT_PEAK_USD = 0.30   # only if peak hasn't reached this yet
CUT_MIN_BARS = 2      # don't fire in first bar (spread effects)


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


def simulate_both(bars, idx_bo, sig):
    """Simulate the trade twice:
       (a) v3.30: peak-trail $1/$0.5 + UHV.low SL (no early cut)
       (b) v3.30 + conditional cut
    Returns (current_pnl, current_outcome, smart_pnl, smart_outcome)
    """
    side = sig["side"]
    entry = sig["bo"].close
    sl = sig["uhv"].low if side == "buy" else sig["uhv"].high
    sl_pnl = (sl - entry) * PNL_PER_POINT if side == "buy" else (entry - sl) * PNL_PER_POINT

    # OHLC sim assumes fav-first ordering (matches MFE estimation)
    peak = 0.0
    current_pnl = None; current_outcome = None
    smart_pnl = None; smart_outcome = None

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

        # Current v3.30: peak-trail engages at peak >= $1
        if current_outcome is None:
            if new_peak >= 1.0:
                # win — peak-trail will fire at peak - $0.5
                current_pnl = new_peak - 0.5
                current_outcome = "win"
            elif sl_hit:
                current_pnl = sl_pnl
                current_outcome = "loss"

        # Smart cut version: same as v3.30 PLUS conditional cut
        if smart_outcome is None:
            if new_peak >= 1.0:
                smart_pnl = new_peak - 0.5
                smart_outcome = "win"
            elif sl_hit:
                smart_pnl = sl_pnl
                smart_outcome = "loss"
            elif (k_off >= CUT_MIN_BARS and adv <= CUT_LOSS_USD and new_peak < CUT_PEAK_USD):
                # CUT FIRES — close at adv level (= cut_loss_usd)
                smart_pnl = CUT_LOSS_USD  # exit at -$3
                smart_outcome = "cut"

        peak = new_peak
        if current_outcome and smart_outcome: break

    # If neither fired, assume time-stop at end of horizon
    if current_outcome is None:
        current_pnl = 0  # time stop near entry
        current_outcome = "time"
    if smart_outcome is None:
        smart_pnl = 0
        smart_outcome = "time"
    return current_pnl, current_outcome, smart_pnl, smart_outcome


def simulate_with_params(bars, cut_loss, cut_peak, cut_min_bars):
    global CUT_LOSS_USD, CUT_PEAK_USD, CUT_MIN_BARS
    CUT_LOSS_USD = cut_loss
    CUT_PEAK_USD = cut_peak
    CUT_MIN_BARS = cut_min_bars

    last_uhv = None; last_side = None
    cur_total = 0; smart_total = 0
    n = 0; n_losses_saved = 0; n_wins_killed = 0
    for i in range(MAX_LOOKBACK + 5, len(bars) - EXIT_HORIZON_BARS):
        sig = detect(bars, i)
        if not sig: continue
        if sig["uhv"].time == last_uhv and sig["side"] == last_side: continue
        last_uhv = sig["uhv"].time
        last_side = sig["side"]
        cp, co, sp, so = simulate_both(bars, i, sig)
        cur_total += cp; smart_total += sp
        n += 1
        if co == "loss" and so == "cut": n_losses_saved += 1
        if co == "win" and so == "cut": n_wins_killed += 1
    delta = smart_total - cur_total
    return cur_total, smart_total, delta, n_losses_saved, n_wins_killed


def sweep(bars):
    print(f"\n{'cut':<6} {'peak':<6} {'minB':<5} {'current':<12} {'smart':<12} {'delta':<10} {'saves':<8} {'kills':<8}")
    print("-" * 80)
    best = []
    for cut_loss in [-2, -3, -5, -8, -12]:
        for cut_peak in [0.10, 0.30, 0.50, 0.70, 1.00]:
            for cut_min_bars in [1, 2, 3]:
                cur, smart, delta, saves, kills = simulate_with_params(bars, cut_loss, cut_peak, cut_min_bars)
                print(f"{cut_loss:<6} {cut_peak:<6} {cut_min_bars:<5} ${cur:<+11.0f} ${smart:<+11.0f} ${delta:<+9.0f} {saves:<8} {kills:<8}")
                best.append((delta, cut_loss, cut_peak, cut_min_bars, saves, kills))
    best.sort(key=lambda x: -x[0])
    print("\nTop 5 by delta:")
    for d, cl, cp, mb, s, k in best[:5]:
        print(f"  cut={cl} peak={cp} min_bars={mb} → delta=${d:+.0f} (saved {s} losses, killed {k} winners)")


def main():
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars")
    import sys
    if "--sweep" in sys.argv:
        sweep(bars)
        return

    last_uhv = None; last_side = None
    trades = []
    for i in range(MAX_LOOKBACK + 5, len(bars) - EXIT_HORIZON_BARS):
        sig = detect(bars, i)
        if not sig: continue
        if sig["uhv"].time == last_uhv and sig["side"] == last_side: continue
        last_uhv = sig["uhv"].time
        last_side = sig["side"]
        cur_pnl, cur_out, smart_pnl, smart_out = simulate_both(bars, i, sig)
        trades.append((cur_pnl, cur_out, smart_pnl, smart_out))

    cur_total = sum(t[0] for t in trades)
    smart_total = sum(t[2] for t in trades)
    delta = smart_total - cur_total
    print(f"\nSimulated {len(trades)} trades.")
    print(f"  CURRENT v3.30 net P&L: ${cur_total:+.2f}")
    print(f"  SMART CUT net P&L:     ${smart_total:+.2f}")
    print(f"  Delta:                 ${delta:+.2f}  ({delta/abs(cur_total)*100:+.1f}%)")

    # Breakdown
    from collections import Counter
    cur_outcomes = Counter(t[1] for t in trades)
    smart_outcomes = Counter(t[3] for t in trades)
    print()
    print(f"Outcome distribution:")
    print(f"  Current:  {dict(cur_outcomes)}")
    print(f"  Smart:    {dict(smart_outcomes)}")

    # Where did smart change things?
    flipped_to_cut = [t for t in trades if t[1] != "cut" and t[3] == "cut"]
    print()
    print(f"Trades that flipped to CUT: {len(flipped_to_cut)}")
    by_orig = Counter(t[1] for t in flipped_to_cut)
    print(f"  Of which were originally: {dict(by_orig)}")
    # Loss prevented: orig=loss, smart=cut
    orig_loss_smart_cut = [t for t in flipped_to_cut if t[1] == "loss"]
    if orig_loss_smart_cut:
        avg_orig = sum(t[0] for t in orig_loss_smart_cut) / len(orig_loss_smart_cut)
        print(f"  Loss avoided ({len(orig_loss_smart_cut)} trades): avg orig=${avg_orig:.2f}, smart=${CUT_LOSS_USD:.2f}")
        savings = sum(t[2] - t[0] for t in orig_loss_smart_cut)
        print(f"  Total saved on these: ${savings:+.2f}")
    # Win killed: orig=win, smart=cut
    orig_win_smart_cut = [t for t in flipped_to_cut if t[1] == "win"]
    if orig_win_smart_cut:
        avg_orig = sum(t[0] for t in orig_win_smart_cut) / len(orig_win_smart_cut)
        print(f"  Win sacrificed ({len(orig_win_smart_cut)} trades): avg orig win=${avg_orig:.2f}, smart=${CUT_LOSS_USD:.2f}")
        cost = sum(t[2] - t[0] for t in orig_win_smart_cut)
        print(f"  Total cost from killed winners: ${cost:+.2f}")


if __name__ == "__main__":
    main()
