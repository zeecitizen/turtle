"""
signal_quality_scorer.py — for each lesson-2 signal detected across 64
days, compute pre-entry features + outcome metrics over the next 30 bars.
Goal: find what (if anything) predicts max favorable excursion (MFE) —
so we can pre-filter signals and improve which ~50-100 we take per day
(out of ~250 detected).

Pre-entry features:
  - vol_mult        (UHV.vol / prior-20-avg)
  - body_pct        (UHV body / range)
  - bars_back       (UHV → breakout distance)
  - bo_body_pct     (breakout body / range)
  - bo_vol_ratio    (breakout vol / UHV vol — always <1.0 by detector rule)
  - uhv_range_pts   (UHV high - low in points)
  - h1_trend        ('up'/'down'/'flat')
  - hour            (broker time hour)

Outcome metrics (over next 30 M1 bars from breakout):
  - mfe_usd         (max favorable excursion in $)
  - mae_usd         (max adverse excursion in $)
  - sl_hit          (would UHV.low/high SL be breached?)
  - profit_factor   (mfe / mae)

Output: CSV of all signals + features + outcomes for downstream analysis.
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
H1_CSV = COMMON / "rev_eng_h1.csv"
OUT_CSV = Path(__file__).parent / "signal_quality_dataset.csv"

PNL_PER_POINT = 100.0 * 0.10  # $10 per 0.10 lot per point
MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
OUTCOME_BARS = 30


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


def detect_with_features(bars, idx_bo):
    """Detect signal + return all pre-entry features."""
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
        if bo.close <= uhv.high: return None
        if bo.vol >= uhv.vol: return None
        side = "buy"
    elif bo.is_red:
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
        if bo.close >= uhv.low: return None
        if bo.vol >= uhv.vol: return None
        side = "sell"
    else:
        return None

    # Features
    prior20 = [bars[k_uhv - i].vol for i in range(1, 21) if k_uhv - i >= 0]
    vol_mult = uhv.vol / (sum(prior20) / len(prior20)) if prior20 else 0
    return {
        "side": side,
        "bo_time": bo.time, "bo_idx": idx_bo,
        "uhv_time": uhv.time,
        "uhv_high": uhv.high, "uhv_low": uhv.low,
        "vol_mult": vol_mult,
        "body_pct": uhv.body_frac,
        "uhv_range_pts": uhv.high - uhv.low,
        "bars_back": idx_bo - k_uhv,
        "bo_close": bo.close,
        "bo_body_pct": bo.body_frac,
        "bo_vol_ratio": bo.vol / uhv.vol,
    }


def h1_dir(h1, t):
    for i, b in enumerate(h1):
        if b.time <= t < b.time + timedelta(hours=1):
            if i < 2: return "?"
            c0 = h1[i-2].close; c2 = h1[i].close
            if c2 > c0: return "up"
            if c2 < c0: return "down"
            return "flat"
    return "?"


def measure_outcome(bars, idx_bo, sig, n_bars=OUTCOME_BARS):
    """Walk forward n_bars and measure MFE, MAE, SL hit, profit_factor."""
    bo = bars[idx_bo]
    entry = bo.close
    side = sig["side"]
    sl = sig["uhv_low"] if side == "buy" else sig["uhv_high"]

    mfe = 0.0; mae = 0.0
    sl_hit = False
    sl_hit_bar = None

    for k in range(idx_bo + 1, min(idx_bo + 1 + n_bars, len(bars))):
        b = bars[k]
        # Extremes in pnl
        if side == "buy":
            best = (b.high - entry) * PNL_PER_POINT
            worst = (b.low - entry) * PNL_PER_POINT
            if b.low <= sl: sl_hit = True; sl_hit_bar = k - idx_bo
        else:
            best = (entry - b.low) * PNL_PER_POINT
            worst = (entry - b.high) * PNL_PER_POINT
            if b.high >= sl: sl_hit = True; sl_hit_bar = k - idx_bo
        mfe = max(mfe, best)
        mae = min(mae, worst)
        if sl_hit: break

    pf = mfe / abs(mae) if mae < 0 else float("inf")
    return {
        "mfe_usd": mfe, "mae_usd": mae,
        "sl_hit": sl_hit, "sl_hit_bar": sl_hit_bar or 0,
        "profit_factor": pf,
    }


def main():
    m1 = load_bars(M1_CSV)
    h1 = load_bars(H1_CSV)
    print(f"M1: {len(m1)}  H1: {len(h1)}")

    last_uhv_time = None; last_side = None
    rows = []
    for i in range(MAX_LOOKBACK + 5, len(m1) - OUTCOME_BARS):
        sig = detect_with_features(m1, i)
        if not sig: continue
        if sig["uhv_time"] == last_uhv_time and sig["side"] == last_side: continue
        last_uhv_time = sig["uhv_time"]
        last_side = sig["side"]

        out = measure_outcome(m1, i, sig)
        rows.append({
            "date": sig["bo_time"].date().isoformat(),
            "time": sig["bo_time"].time().isoformat(),
            "hour": sig["bo_time"].hour,
            "side": sig["side"],
            "vol_mult": round(sig["vol_mult"], 3),
            "body_pct": round(sig["body_pct"], 3),
            "uhv_rng_pts": round(sig["uhv_range_pts"], 2),
            "bars_back": sig["bars_back"],
            "bo_body_pct": round(sig["bo_body_pct"], 3),
            "bo_vol_ratio": round(sig["bo_vol_ratio"], 3),
            "h1_trend": h1_dir(h1, sig["bo_time"]),
            "mfe_usd": round(out["mfe_usd"], 2),
            "mae_usd": round(out["mae_usd"], 2),
            "profit_factor": round(out["profit_factor"], 2) if out["profit_factor"] != float("inf") else 999.0,
            "sl_hit": out["sl_hit"],
            "sl_hit_bar": out["sl_hit_bar"],
        })

    print(f"Wrote {len(rows)} signals")
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"→ {OUT_CSV}")

    # Quick stats
    print()
    print("Quick distribution:")
    mfes = [r["mfe_usd"] for r in rows]
    maes = [r["mae_usd"] for r in rows]
    pfs  = [r["profit_factor"] for r in rows if r["profit_factor"] < 999]
    print(f"  MFE: median ${statistics.median(mfes):.2f}  mean ${statistics.mean(mfes):.2f}  max ${max(mfes):.2f}")
    print(f"  MAE: median ${statistics.median(maes):.2f}  mean ${statistics.mean(maes):.2f}  worst ${min(maes):.2f}")
    print(f"  PF:  median {statistics.median(pfs):.2f}  mean {statistics.mean(pfs):.2f}")
    sl_hit_pct = sum(1 for r in rows if r["sl_hit"]) / len(rows) * 100
    print(f"  SL-hit within 30 bars: {sl_hit_pct:.1f}%")


if __name__ == "__main__":
    main()
