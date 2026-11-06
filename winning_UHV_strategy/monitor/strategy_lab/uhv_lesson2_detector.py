"""
uhv_lesson2_detector.py — pure Python forward-walking detector implementing
ONLY Zee's lessons 1+2 (M1 camel-humps + UHV breakout). No FVG, no sweep, no NSC.

BUY logic (SELL mirrors):
  1. Find swing high = the most-recent bar (within last MAX_LOOKBACK M1 bars)
     whose high >= breakout.close. The retracement is between swing high and bo.
  2. M1 trend before the swing high = HH+HL over a TREND_LOOKBACK bar window
     (two-half max/min comparison). Buy needs 'up'.
  3. UHV = highest-volume RED bar in the retracement.
  4. Breakout candle is GREEN, closes above UHV.high, body fraction >= MIN_BODY.
  5. Breakout volume < UHV volume (lesson-2 explicit rule).

Goal: capture all 20 strict lesson-2 setups Zee took on 2026.02.11. Per Zee,
extra fires (FPs) are fine — they'd be valid setups he'd have taken if attentive.
"""
from __future__ import annotations
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"
H1_CSV = COMMON / "rev_eng_h1.csv"


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
        rng = self.high - self.low
        return abs(self.close - self.open) / rng if rng > 0 else 0


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


ZEE_TEXTBOOK = {
    "01:59:04": ("buy",  5042.17),
    "02:09:38": ("sell", 5040.68),
    "02:29:02": ("buy",  5039.03),
    "16:49:07": ("buy",  5047.93),
    "16:52:21": ("buy",  5050.77),
    "16:54:10": ("buy",  5056.74),
    "16:58:03": ("buy",  5064.26),
    "17:02:45": ("buy",  5055.71),
    "17:36:11": ("buy",  5056.53),
    "17:36:13": ("buy",  5057.05),
    "17:37:26": ("buy",  5045.82),
    "17:49:59": ("buy",  5048.32),
    "18:24:18": ("buy",  5059.26),
    "18:41:50": ("buy",  5078.10),
    "19:20:34": ("sell", 5084.21),
    "19:26:06": ("sell", 5089.16),
    "19:29:31": ("buy",  5086.34),
    "19:36:19": ("buy",  5082.91),
    "19:38:39": ("buy",  5083.28),
    "19:38:59": ("buy",  5086.33),
}


def m1_trend(bars, idx_end, lookback):
    """HH+HL trend over `lookback` M1 bars ending at idx_end (exclusive).
    Two-half max/min comparison.
    """
    if lookback == 0: return "ignore"
    start = idx_end - lookback
    if start < 0: return "?"
    half = lookback // 2
    first  = bars[start : start + half]
    second = bars[start + half : idx_end]
    if not first or not second: return "?"
    hh = max(b.high for b in second) > max(b.high for b in first)
    hl = min(b.low  for b in second) > min(b.low  for b in first)
    lh = max(b.high for b in second) < max(b.high for b in first)
    ll = min(b.low  for b in second) < min(b.low  for b in first)
    if hh and hl: return "up"
    if lh and ll: return "down"
    return "flat"


def detect_at(bars, idx_bo, p):
    bo = bars[idx_bo]
    if bo.body_frac < p["min_body"]:
        return None

    # ---- BUY ----
    if bo.is_green:
        # Walk back to find swing high; collect reds between swing high and bo.
        idx_swing = None
        reds = []
        for j in range(1, p["max_lookback"] + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.high >= bo.close:
                idx_swing = k; break
            if c.is_red:
                reds.append((k, c))
        if not reds or idx_swing is None: return None
        # bars_back from bo to UHV
        k_uhv, uhv = max(reds, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > p["max_bars_back"]: return None
        if bo.close <= uhv.high: return None
        if bo.vol >= uhv.vol: return None
        # M1 trend check: BEFORE the swing high, was structure HH+HL?
        if p["trend_lookback"] > 0:
            tr = m1_trend(bars, idx_swing, p["trend_lookback"])
            if tr != "up" and tr != "ignore": return None
        return {"side":"buy","bo":bo,"uhv":uhv,"bars_back":idx_bo - k_uhv,
                "swing_high":bars[idx_swing].time}

    # ---- SELL ----
    if bo.is_red:
        idx_swing = None
        greens = []
        for j in range(1, p["max_lookback"] + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c.low <= bo.close:
                idx_swing = k; break
            if c.is_green:
                greens.append((k, c))
        if not greens or idx_swing is None: return None
        k_uhv, uhv = max(greens, key=lambda kc: kc[1].vol)
        if (idx_bo - k_uhv) > p["max_bars_back"]: return None
        if bo.close >= uhv.low: return None
        if bo.vol >= uhv.vol: return None
        if p["trend_lookback"] > 0:
            tr = m1_trend(bars, idx_swing, p["trend_lookback"])
            if tr != "down" and tr != "ignore": return None
        return {"side":"sell","bo":bo,"uhv":uhv,"bars_back":idx_bo - k_uhv,
                "swing_low":bars[idx_swing].time}

    return None


def run(bars, p):
    feb11_start = datetime(2026, 2, 11, 0, 0)
    feb11_end   = datetime(2026, 2, 12, 0, 0)
    signals = []
    for i, bo in enumerate(bars):
        if bo.time < feb11_start or bo.time >= feb11_end: continue
        if i < max(25, p["trend_lookback"] + p["max_lookback"]): continue
        sig = detect_at(bars, i, p)
        if sig:
            sig["bo_idx"] = i
            signals.append(sig)
    return signals


def score(signals, verbose=False):
    tp = 0
    used = set()
    matches = []
    missed = []
    for hms, (side, price) in ZEE_TEXTBOOK.items():
        zt = datetime.strptime(f"2026.02.11 {hms}", "%Y.%m.%d %H:%M:%S")
        best_i = None
        best_gap = timedelta(minutes=999)
        for i, s in enumerate(signals):
            if i in used or s["side"] != side: continue
            gap = abs(s["bo"].time - zt)
            if gap <= timedelta(minutes=5) and gap < best_gap:
                best_i = i; best_gap = gap
        if best_i is not None:
            tp += 1
            used.add(best_i)
            matches.append((hms, side, signals[best_i], best_gap))
        else:
            missed.append((hms, side, price))
    fp_sigs = [s for i, s in enumerate(signals) if i not in used]
    if verbose:
        print(f"\nMatched {tp}/{len(ZEE_TEXTBOOK)}:")
        for hms, side, s, gap in matches:
            print(f"  ✓ {hms} {side:4s} → bo {s['bo'].time:%H:%M} UHV {s['uhv'].time:%H:%M} (back {s['bars_back']})  gap {gap.total_seconds()/60:+.0f}min")
        for hms, side, price in missed:
            print(f"  ✗ {hms} {side:4s} @ {price:.2f} — MISSED")
    return tp, len(fp_sigs), fp_sigs


def main():
    m1 = load_bars(M1_CSV)
    print(f"Loaded M1: {len(m1)} bars")

    # Baseline: no trend filter
    print("\n========== A) NO M1 trend filter ==========")
    p_a = {"min_body": 0.0, "max_lookback": 60, "max_bars_back": 60,
           "trend_lookback": 0}
    sigs_a = run(m1, p_a)
    tp_a, fp_a, _ = score(sigs_a, verbose=True)
    print(f"\nTP={tp_a}/{len(ZEE_TEXTBOOK)}   FP={fp_a}   total signals={len(sigs_a)}")

    # With M1 trend at varying lookbacks
    for tl in [10, 15, 20, 30]:
        print(f"\n========== B) M1 trend lookback = {tl} ==========")
        p_b = {**p_a, "trend_lookback": tl}
        sigs = run(m1, p_b)
        tp, fp, _ = score(sigs, verbose=False)
        print(f"TP={tp}/{len(ZEE_TEXTBOOK)}   FP={fp}   total signals={len(sigs)}")


if __name__ == "__main__":
    main()
