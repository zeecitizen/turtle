"""backtest_anticipation_v1.py - capture Zee's wrong-color anticipation entries.

Goal: catch the 32 misses where Zee bought a red candle or sold a green one
(59% of Feb 11 misses, ~$700+ of his $835 day).

THEORY: Zee enters DURING a dying retracement candle, not AFTER a confirmation
candle. Signature of a "dying red" in an uptrend:
  - body shrinking (current_body < prev_body)
  - volume declining (current_vol < prev_vol or much below recent avg)
  - lower wick visible (buyers stepping in / sweep)
  - trend context is up (close > close N bars ago)
  - retracement has run a few bars (3+ reds in row, or recent swing low close)

STEP 1: print bar context around 3 biggest miss-cluster minutes so we can
        SEE what Zee saw. (Ground truth before we write the rule.)
STEP 2: implement candidate rule, fire on every Feb 11 bar.
STEP 3: alignment vs Zee + false-positive count.
"""
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

from build_feb11_lab import load_feb11_bars, ZEE_TRADES


def fmt_bar(b):
    t = datetime.fromtimestamp(b["time"], tz=UTC).strftime("%H:%M")
    body = b["close"] - b["open"]
    color = "G" if body > 0 else ("R" if body < 0 else "-")
    rng = b["high"] - b["low"]
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]
    return (f"{t} [{color}] O{b['open']:8.2f} H{b['high']:8.2f} "
            f"L{b['low']:8.2f} C{b['close']:8.2f}  body{body:+5.2f}  "
            f"rng{rng:5.2f}  upWk{upper_wick:5.2f}  loWk{lower_wick:5.2f}  v{b['vol']}")


def inspect_cluster(bars, hms, side, window=8):
    """Print bars around a Zee entry minute (3 before, 5 after, side label)."""
    t_o = int(datetime.strptime(f"2026.02.11 {hms}", "%Y.%m.%d %H:%M:%S")
              .replace(tzinfo=UTC).timestamp())
    t_min = t_o - (t_o % 60)
    idx = min(range(len(bars)), key=lambda i: abs(bars[i]["time"] - t_min))
    print(f"\n--- ZEE {side.upper()} @ {hms} (bar idx {idx}) ---")
    for j in range(max(0, idx - window), min(len(bars), idx + 5)):
        marker = " <-- ZEE ENTRY" if j == idx else ""
        print(f"  {fmt_bar(bars[j])}{marker}")


def trend_up(bars, idx, lookback=30, threshold=0.5):
    """Simple uptrend proxy: close > close N bars ago by threshold."""
    if idx < lookback: return False
    return bars[idx]["close"] - bars[idx - lookback]["close"] >= threshold


def trend_down(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx - lookback]["close"] - bars[idx]["close"] >= threshold


def detect_anticipation(bars, idx):
    """Detect a 'dying retracement' candle worthy of an anticipation entry.

    Buy setup:
      - trend up (close > close-30 + $0.5)
      - current bar red (close < open)
      - body smaller than prev bar's body (momentum dying) OR vol < prev vol
      - lower wick at least 0.5 of body (buyers absorbing) OR range < prev range
      - at least 2 of the last 4 bars were red (we ARE in a retracement)

    Returns +1 (buy), -1 (sell), or 0.
    """
    if idx < 5 or idx >= len(bars) - 1: return 0
    b  = bars[idx]
    pb = bars[idx - 1]
    body  = b["close"] - b["open"]
    pbody = pb["close"] - pb["open"]
    rng   = b["high"] - b["low"]
    prng  = pb["high"] - pb["low"]
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]

    # Are we in a retracement? Look at last 4 bars before current.
    last4 = bars[idx - 4:idx]
    n_red_recent   = sum(1 for x in last4 if x["close"] < x["open"])
    n_green_recent = sum(1 for x in last4 if x["close"] > x["open"])

    # BUY anticipation: uptrend, red bar, dying signs
    if trend_up(bars, idx) and body < 0:
        if n_red_recent < 2: return 0          # not really in retracement
        # Dying = shrinking body, lower vol, OR lower wick rejection
        dying_body = abs(body) < abs(pbody)
        dying_vol  = b["vol"] < pb["vol"]
        absorption = lower_wick >= 0.5 * abs(body) and lower_wick > 0.1
        rng_compress = rng < prng
        signals = sum([dying_body, dying_vol, absorption, rng_compress])
        if signals >= 2:
            return +1
    # SELL anticipation: downtrend, green bar, dying signs
    if trend_down(bars, idx) and body > 0:
        if n_green_recent < 2: return 0
        dying_body = abs(body) < abs(pbody)
        dying_vol  = b["vol"] < pb["vol"]
        absorption = upper_wick >= 0.5 * abs(body) and upper_wick > 0.1
        rng_compress = rng < prng
        signals = sum([dying_body, dying_vol, absorption, rng_compress])
        if signals >= 2:
            return -1
    return 0


def run_anticipation(bars):
    signals = []
    for i, b in enumerate(bars):
        side = detect_anticipation(bars, i)
        if side != 0:
            signals.append({"time": b["time"], "side": side, "idx": i})
    return signals


def alignment(signals, window_sec=2*60):
    """For each Zee entry, was there a same-side anticipation signal within ±window?"""
    matched = 0; matched_indices = set()
    for ti, (open_hms, side, *_ ) in enumerate(ZEE_TRADES):
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        for s in signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= window_sec:
                matched += 1
                matched_indices.add(ti)
                break
    return matched, matched_indices


def main():
    bars = load_feb11_bars()
    if not bars:
        print("ERROR: no Feb 11 bars"); return
    print(f"Loaded {len(bars)} M1 bars\n")

    # ---- STEP 1: inspect 3 biggest miss clusters ----
    print("=" * 80)
    print("STEP 1: BAR CONTEXT FOR BIGGEST MISSED CLUSTERS")
    print("=" * 80)
    inspect_cluster(bars, "17:02:45", "buy")   # +$153 pyramid
    inspect_cluster(bars, "17:49:59", "buy")   # +$157 pyramid
    inspect_cluster(bars, "19:08:59", "sell")  # +$30 pyramid (gold reversal)
    inspect_cluster(bars, "19:11:51", "sell")  # +$67 pyramid
    inspect_cluster(bars, "19:20:34", "sell")  # +$57 pyramid

    # ---- STEP 2 + 3: run + alignment ----
    print("\n" + "=" * 80)
    print("STEP 2: ANTICIPATION DETECTOR RESULTS")
    print("=" * 80)
    signals = run_anticipation(bars)
    print(f"Signals fired: {len(signals)}")
    print(f"  buy:  {sum(1 for s in signals if s['side'] > 0)}")
    print(f"  sell: {sum(1 for s in signals if s['side'] < 0)}")

    matched, matched_idx = alignment(signals, window_sec=2*60)
    n_zee = len(ZEE_TRADES)
    print(f"\nAlignment (±2 min):  {matched}/{n_zee} ({100*matched/n_zee:.0f}%)")

    # PnL captured: sum of Zee trades whose entry matched a same-side signal
    captured_pnl = sum(ZEE_TRADES[i][5] for i in matched_idx)
    total_pnl = sum(t[5] for t in ZEE_TRADES)
    print(f"  Captured Zee PnL: ${captured_pnl:+.2f} / ${total_pnl:+.2f}  "
          f"({100*captured_pnl/total_pnl:.0f}%)")

    # False positives = signals not within ±5 min of ANY Zee entry of same side
    zee_set = []
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        zee_set.append((t_o, +1 if side == "buy" else -1))
    fp = 0
    for s in signals:
        any_zee_near = any(zs == s["side"] and abs(zt - s["time"]) <= 5 * 60
                           for zt, zs in zee_set)
        if not any_zee_near:
            fp += 1
    print(f"  False positives (no Zee entry within ±5 min same side): {fp} / {len(signals)} "
          f"({100*fp/max(1,len(signals)):.0f}%)")


if __name__ == "__main__":
    main()
