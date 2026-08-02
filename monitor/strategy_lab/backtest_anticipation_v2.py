"""backtest_anticipation_v2.py - two specific signatures observed in Zee's bars.

After inspecting 17:02 / 17:49 / 19:08 / 19:11 / 19:20 (v1 ground truth), the
"anticipation entry" miss-pattern resolves into TWO distinct mechanical
signatures:

  A) SWEEP+REVERSE buy/sell (17:02 buy, 17:49 buy, 19:20 sell)
     - bar against current trend (red in uptrend, green in downtrend)
     - wick OPPOSITE its body is at least 1.5 x the body magnitude
     - wick absolute size at least $1.0 (filter micro-bars)
     - close inside or near top/bottom of recent retracement range

  B) CLIMAX FADE (19:08 sell, 19:11 sell)
     - parabolic prior move: 5+ points in last 8 bars (one direction)
     - current bar with-trend, small body, small wick opposite trend
     - aka: spike is exhausting, fade it

We deliberately keep the rules NARROW. Better to capture 20% of Zee with
very few false positives than 80% with 97% FP rate (v1's failure).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

from build_feb11_lab import load_feb11_bars, ZEE_TRADES


def trend_up(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx]["close"] - bars[idx - lookback]["close"] >= threshold


def trend_down(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx - lookback]["close"] - bars[idx]["close"] >= threshold


def parabolic_up(bars, idx, lookback=8, threshold=5.0):
    """Last `lookback` bars moved up by at least threshold points."""
    if idx < lookback: return False
    delta = bars[idx]["close"] - bars[idx - lookback]["close"]
    return delta >= threshold


def parabolic_down(bars, idx, lookback=8, threshold=5.0):
    if idx < lookback: return False
    delta = bars[idx - lookback]["close"] - bars[idx]["close"]
    return delta >= threshold


def detect_sweep_reverse(bars, idx):
    """A) Counter-trend bar with dominant wick on the entry side.
    Buy: red bar (close < open) in uptrend with lower_wick >= 1.5 * body, >= $1.0.
    Sell: green bar in downtrend with upper_wick >= 1.5 * body, >= $1.0."""
    if idx < 30: return 0
    b = bars[idx]
    body = abs(b["close"] - b["open"])
    if body < 0.01: return 0
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]

    if b["close"] < b["open"] and trend_up(bars, idx):
        if lower_wick >= 1.5 * body and lower_wick >= 1.0:
            return +1
    if b["close"] > b["open"] and trend_down(bars, idx):
        if upper_wick >= 1.5 * body and upper_wick >= 1.0:
            return -1
    return 0


def detect_climax_fade(bars, idx):
    """B) After parabolic run, fade with-trend bars near the extreme.
    Buy: parabolic-DOWN last 8 bars, current bar red with small body (<$1)
         and lower wick visible (>=$0.2). Trade the bounce.
    Sell: parabolic-UP last 8 bars, current bar green with small body (<$1)
         and upper wick visible (>=$0.2). Trade the rejection."""
    if idx < 8: return 0
    b = bars[idx]
    body = b["close"] - b["open"]
    abs_body = abs(body)
    if abs_body < 0.01 or abs_body > 1.0: return 0
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]

    # Sell at climax-top: parabolic up + small green or red bar
    if parabolic_up(bars, idx) and upper_wick >= 0.2:
        return -1
    # Buy at climax-bottom: parabolic down + small bar with lower wick
    if parabolic_down(bars, idx) and lower_wick >= 0.2:
        return +1
    return 0


def detect_combined(bars, idx):
    s = detect_sweep_reverse(bars, idx)
    if s: return ("sweep_reverse", s)
    s = detect_climax_fade(bars, idx)
    if s: return ("climax_fade", s)
    return None


def run(bars):
    signals = []
    for i, b in enumerate(bars):
        r = detect_combined(bars, i)
        if r:
            kind, side = r
            signals.append({"time": b["time"], "side": side, "kind": kind, "idx": i})
    return signals


def analyze(signals, window_sec=2*60):
    """Per-Zee-trade alignment + per-signal false-positive."""
    matched = 0; matched_idx = set()
    matched_by_kind = {"sweep_reverse": 0, "climax_fade": 0}
    for ti, (open_hms, side, *_ ) in enumerate(ZEE_TRADES):
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        # find any same-side signal within window; record which kind matched
        for s in signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= window_sec:
                matched += 1
                matched_idx.add(ti)
                matched_by_kind[s["kind"]] += 1
                break

    zee_set = []
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        zee_set.append((t_o, +1 if side == "buy" else -1))
    fp = 0; fp_by_kind = {"sweep_reverse": 0, "climax_fade": 0}
    for s in signals:
        any_zee_near = any(zs == s["side"] and abs(zt - s["time"]) <= 5 * 60
                           for zt, zs in zee_set)
        if not any_zee_near:
            fp += 1; fp_by_kind[s["kind"]] += 1
    return matched, matched_idx, matched_by_kind, fp, fp_by_kind


def main():
    bars = load_feb11_bars()
    if not bars:
        print("ERROR: no bars"); return
    print(f"Loaded {len(bars)} M1 bars\n")
    signals = run(bars)
    sw = [s for s in signals if s["kind"] == "sweep_reverse"]
    cl = [s for s in signals if s["kind"] == "climax_fade"]
    print(f"Total signals: {len(signals)}")
    print(f"  sweep_reverse: {len(sw)}  (buy {sum(1 for s in sw if s['side']>0)} / "
          f"sell {sum(1 for s in sw if s['side']<0)})")
    print(f"  climax_fade:   {len(cl)}  (buy {sum(1 for s in cl if s['side']>0)} / "
          f"sell {sum(1 for s in cl if s['side']<0)})")
    print()

    matched, matched_idx, mbk, fp, fpbk = analyze(signals)
    n_zee = len(ZEE_TRADES)
    captured_pnl = sum(ZEE_TRADES[i][5] for i in matched_idx)
    total_pnl = sum(t[5] for t in ZEE_TRADES)
    print(f"Alignment (±2 min same side):  {matched}/{n_zee} ({100*matched/n_zee:.0f}%)")
    print(f"  by sweep_reverse: {mbk['sweep_reverse']}")
    print(f"  by climax_fade:   {mbk['climax_fade']}")
    print(f"  Captured PnL: ${captured_pnl:+.2f} / ${total_pnl:+.2f}  "
          f"({100*captured_pnl/total_pnl:.0f}%)")
    print(f"False positives (no Zee within ±5min same side): {fp}/{len(signals)} "
          f"({100*fp/max(1,len(signals)):.0f}%)")
    print(f"  by sweep_reverse: {fpbk['sweep_reverse']}/{len(sw)} "
          f"({100*fpbk['sweep_reverse']/max(1,len(sw)):.0f}%)")
    print(f"  by climax_fade:   {fpbk['climax_fade']}/{len(cl)} "
          f"({100*fpbk['climax_fade']/max(1,len(cl)):.0f}%)")
    print()
    print("--- Sample signals (first 12) ---")
    for s in signals[:12]:
        t = datetime.fromtimestamp(s["time"], tz=UTC).strftime("%H:%M")
        side = "BUY " if s["side"] > 0 else "SELL"
        print(f"  {t}  {side}  {s['kind']}")


if __name__ == "__main__":
    main()
