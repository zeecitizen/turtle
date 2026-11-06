"""
ea_win_boundary.py — re-measures outcomes for the 17.8K-signal dataset
using the ACTUAL EA win/loss boundary:

  - WIN: peak P&L reaches $InpPeakBankUSD (= $1) BEFORE SL hit
    (peak-trail engages → trade closes at $0.50 minimum)
  - LOSS: SL hit before peak >= $1
    (UHV.low/high breached, takes full SL distance hit)

This is the right metric because v3.30 banks profit any time peak >= $1
via peak-trail. The 30-bar SL-hit window includes plenty of trades
that already banked profit and would have closed at peak-trail before
the SL bar.
"""
from __future__ import annotations
import csv
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"
OUT_CSV = Path(__file__).parent / "ea_win_boundary_dataset.csv"

PNL_PER_POINT = 100.0 * 0.10
MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
EXIT_HORIZON_BARS = 30
PEAK_BANK_USD = 1.0


@dataclass
class Bar:
    time: datetime
    open: float; high: float; low: float; close: float
    vol: int

    @property
    def is_green(self): return self.close > self.open
    @property
    def is_red(self):   return self.close < self.open
    @property
    def body_frac(self):
        r = self.high - self.low
        return abs(self.close - self.open) / r if r > 0 else 0


def load_bars(p):
    bars = []
    with open(p) as f:
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
        return {"side": "buy", "bo": bo, "uhv": uhv, "bars_back": idx_bo - k_uhv}
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
        return {"side": "sell", "bo": bo, "uhv": uhv, "bars_back": idx_bo - k_uhv}
    return None


def measure_ea_outcome(bars, idx_bo, sig):
    """Walk forward up to EXIT_HORIZON_BARS. Return:
      win: peak >= $1 before SL hit
      loss: SL hit before peak >= $1
      neither: time-stop hit (rare with 30-min)
    """
    bo = bars[idx_bo]
    entry = bo.close
    side = sig["side"]
    sl = sig["uhv"].low if side == "buy" else sig["uhv"].high

    peak = 0.0
    win_bar = None  # bar at which peak first reached $1
    loss_bar = None

    for k in range(idx_bo + 1, min(idx_bo + 1 + EXIT_HORIZON_BARS, len(bars))):
        b = bars[k]
        # Bar's favorable and adverse extremes
        if side == "buy":
            fav_pnl = (b.high - entry) * PNL_PER_POINT
            adv = (b.low - entry) * PNL_PER_POINT
            sl_hit_bar = b.low <= sl
        else:
            fav_pnl = (entry - b.low) * PNL_PER_POINT
            adv = (entry - b.high) * PNL_PER_POINT
            sl_hit_bar = b.high >= sl

        # ASSUMPTION: within-bar order = favorable peak before adverse extreme
        # for green bars (open→low→high→close = no — actually open→high→low→close
        # is common). It's unknowable without ticks. Use BOTH possibilities:
        #   (a) If FAV reaches $1, win regardless of SL in same bar
        #   (b) If SL hits and FAV never reached $1, loss
        # This is OPTIMISTIC for wins (assumes fav-first ordering).
        new_peak = max(peak, fav_pnl)
        peak_hit_bank = new_peak >= PEAK_BANK_USD

        if peak_hit_bank and win_bar is None:
            win_bar = k - idx_bo
            peak = new_peak
            return "win", peak, win_bar, None, k

        if sl_hit_bar:
            loss_bar = k - idx_bo
            peak = new_peak
            return "loss", peak, None, loss_bar, k

        peak = new_peak

    return "neither", peak, None, None, min(idx_bo + EXIT_HORIZON_BARS, len(bars) - 1)


def main():
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars")

    last_uhv = None; last_side = None
    rows = []
    wins = losses = neither = 0
    for i in range(MAX_LOOKBACK + 5, len(bars) - EXIT_HORIZON_BARS):
        sig = detect(bars, i)
        if not sig: continue
        if sig["uhv"].time == last_uhv and sig["side"] == last_side: continue
        last_uhv = sig["uhv"].time
        last_side = sig["side"]

        outcome, peak, wb, lb, exit_idx = measure_ea_outcome(bars, i, sig)
        if outcome == "win": wins += 1
        elif outcome == "loss": losses += 1
        else: neither += 1

        # Features for downstream filtering
        prior20 = [bars[i - sig["bars_back"] - k].vol for k in range(1, 21) if i - sig["bars_back"] - k >= 0]
        vol_mult = sig["uhv"].vol / (sum(prior20) / len(prior20)) if prior20 else 0
        rows.append({
            "date": sig["bo"].time.date().isoformat(),
            "time": sig["bo"].time.time().isoformat(),
            "side": sig["side"],
            "vol_mult": round(vol_mult, 3),
            "body_pct": round(sig["uhv"].body_frac, 3),
            "uhv_rng_pts": round(sig["uhv"].high - sig["uhv"].low, 2),
            "bars_back": sig["bars_back"],
            "bo_body_pct": round(sig["bo"].body_frac, 3),
            "bo_vol_ratio": round(sig["bo"].vol / sig["uhv"].vol, 3),
            "outcome": outcome,
            "peak_usd": round(peak, 2),
            "win_bar": wb or 0,
            "loss_bar": lb or 0,
        })

    print(f"Total: {len(rows)}")
    print(f"  WIN (peak >= $1 before SL):  {wins} ({wins/len(rows)*100:.1f}%)")
    print(f"  LOSS (SL before peak >= $1): {losses} ({losses/len(rows)*100:.1f}%)")
    print(f"  NEITHER (time stop):         {neither} ({neither/len(rows)*100:.1f}%)")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\n→ {OUT_CSV}")

    # Bucket WIN rate by key features
    def bucket(key, buckets, label):
        print(f"\n{label}:")
        for lo, hi in buckets:
            sub = [r for r in rows if lo <= r[key] < hi]
            if not sub: continue
            wr = sum(1 for r in sub if r["outcome"] == "win") / len(sub) * 100
            lr = sum(1 for r in sub if r["outcome"] == "loss") / len(sub) * 100
            print(f"  {key} [{lo}, {hi}): n={len(sub):<5} WIN={wr:.1f}%  LOSS={lr:.1f}%")
    bucket("vol_mult", [(0,0.8),(0.8,1.0),(1.0,1.2),(1.2,1.5),(1.5,2.0),(2.0,3.0),(3.0,100)], "By vol_mult")
    bucket("uhv_rng_pts", [(0,1),(1,3),(3,5),(5,10),(10,50)], "By UHV range")
    bucket("bars_back", [(1,3),(3,6),(6,12),(12,25),(25,100)], "By bars_back")
    bucket("bo_vol_ratio", [(0,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0)], "By bo_vol_ratio")


if __name__ == "__main__":
    main()
