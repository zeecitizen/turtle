"""backtest_anticipation_v3.py - strict filters + REAL PnL test.

v2 hit 23% capture but 95% false-positive. Per Zee's
"validate-profitability-not-capture" rule, FP rate alone isn't the test - if
the signals MAKE MONEY when simulated as trades, the FPs are just Zee-style
trades he didn't personally take. That's still profitable.

This version:
  1. Time filter: 16:00-20:00 UTC (88% of Zee's 69 trades are in this window).
  2. Multi-bar confirmation: detect at bar i but fire only if bar i+1 closes
     in our direction (long: i+1 close > i high; short: i+1 close < i low).
  3. Stricter wick: opposite-wick must be >= 2.0 * body and >= $1.5 absolute.
  4. SIMULATE EACH SIGNAL as a real trade with M1-bar SL/TP:
        - Enter at i+1 close
        - SL: against the swept extreme (i's low for buy, i's high for sell)
              capped at $3.0 max risk
        - TP: 1.5R fixed (Zee's most common R:R observed)
        - Time stop: 20 minutes
     Walk subsequent bars to determine hit.
  5. Report: signals/trades/wins/losses/PnL/expectancy + alignment-with-Zee.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from build_feb11_lab import load_feb11_bars, ZEE_TRADES

WINDOW_START_HOUR = 16   # UTC
WINDOW_END_HOUR   = 20
MIN_WICK_BODY     = 2.0
MIN_WICK_ABS      = 1.5
SL_MAX_USD        = 3.0
RR                = 1.5
TIME_STOP_BARS    = 20
LOTS              = 0.05
USD_PER_PRICE     = LOTS * 100   # XAUUSD: 1 point = $1 per 0.01 lot


def in_window(ts):
    h = datetime.fromtimestamp(ts, tz=UTC).hour
    return WINDOW_START_HOUR <= h < WINDOW_END_HOUR


def trend_up(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx]["close"] - bars[idx - lookback]["close"] >= threshold


def trend_down(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx - lookback]["close"] - bars[idx]["close"] >= threshold


def detect_sweep_v3(bars, idx):
    """Detect a sweep+reverse setup on bar `idx`. RETURN None or
    (side, swept_extreme) where swept_extreme = the wick low (buy) or
    wick high (sell). Confirmation by NEXT bar (i+1) is required, so this
    returns a *candidate* — the caller checks the next bar."""
    if idx < 30: return None
    b = bars[idx]
    body = abs(b["close"] - b["open"])
    if body < 0.01: return None
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]

    # Buy candidate: red bar in uptrend with strong lower wick
    if b["close"] < b["open"] and trend_up(bars, idx):
        if lower_wick >= MIN_WICK_BODY * body and lower_wick >= MIN_WICK_ABS:
            return (+1, b["low"])
    # Sell candidate: green bar in downtrend with strong upper wick
    if b["close"] > b["open"] and trend_down(bars, idx):
        if upper_wick >= MIN_WICK_BODY * body and upper_wick >= MIN_WICK_ABS:
            return (-1, b["high"])
    return None


def simulate_trade(bars, fire_idx, side, entry_price, swept_extreme):
    """Walk bars from fire_idx+1 forward. Return (pnl_usd, exit_reason, exit_idx)."""
    # SL distance from entry to swept extreme, capped
    if side > 0:
        sl_dist = max(0.1, entry_price - swept_extreme)
        if sl_dist > SL_MAX_USD: sl_dist = SL_MAX_USD
        sl_price = entry_price - sl_dist
        tp_price = entry_price + RR * sl_dist
    else:
        sl_dist = max(0.1, swept_extreme - entry_price)
        if sl_dist > SL_MAX_USD: sl_dist = SL_MAX_USD
        sl_price = entry_price + sl_dist
        tp_price = entry_price - RR * sl_dist

    for j in range(fire_idx + 1, min(fire_idx + 1 + TIME_STOP_BARS, len(bars))):
        bar = bars[j]
        if side > 0:
            # SL hit first if low touches sl_price; TP first if high reaches tp
            hit_sl = bar["low"]  <= sl_price
            hit_tp = bar["high"] >= tp_price
            if hit_sl and hit_tp:
                # Conservative: assume SL hit first (worst-case)
                return (-sl_dist * USD_PER_PRICE, "SL+TP-conservative-SL", j)
            if hit_sl:  return (-sl_dist * USD_PER_PRICE, "SL", j)
            if hit_tp:  return (+RR * sl_dist * USD_PER_PRICE, "TP", j)
        else:
            hit_sl = bar["high"] >= sl_price
            hit_tp = bar["low"]  <= tp_price
            if hit_sl and hit_tp:
                return (-sl_dist * USD_PER_PRICE, "SL+TP-conservative-SL", j)
            if hit_sl:  return (-sl_dist * USD_PER_PRICE, "SL", j)
            if hit_tp:  return (+RR * sl_dist * USD_PER_PRICE, "TP", j)
    # Time stop — close at last bar's close
    last_close = bars[min(fire_idx + TIME_STOP_BARS, len(bars) - 1)]["close"]
    pnl_price = (last_close - entry_price) if side > 0 else (entry_price - last_close)
    return (pnl_price * USD_PER_PRICE, "TIMEOUT", fire_idx + TIME_STOP_BARS)


def main():
    bars = load_feb11_bars()
    if not bars:
        print("ERROR: no bars"); return
    print(f"Loaded {len(bars)} M1 bars")
    print(f"Window: {WINDOW_START_HOUR}:00-{WINDOW_END_HOUR}:00 UTC  "
          f"Wick: >={MIN_WICK_BODY}x body & >=${MIN_WICK_ABS}  "
          f"SL_max=${SL_MAX_USD}  RR={RR}  bars_time_stop={TIME_STOP_BARS}\n")

    signals = []
    trades = []
    for i in range(len(bars) - 2):
        if not in_window(bars[i]["time"]): continue
        cand = detect_sweep_v3(bars, i)
        if not cand: continue
        side, swept = cand
        # Confirmation by next bar
        nb = bars[i + 1]
        if side > 0 and nb["close"] <= bars[i]["high"]:  continue
        if side < 0 and nb["close"] >= bars[i]["low"]:   continue
        signals.append({"time": bars[i]["time"], "side": side, "fire_idx": i + 1})
        # Simulate trade entered at i+1 close
        entry = nb["close"]
        pnl, reason, exit_idx = simulate_trade(bars, i + 1, side, entry, swept)
        trades.append({"time": bars[i + 1]["time"], "side": side, "entry": entry,
                       "pnl": pnl, "reason": reason})

    # Stats
    n = len(trades)
    if n == 0:
        print("NO TRADES fired."); return
    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    flat   = [t for t in trades if t["pnl"] == 0]
    pnl    = sum(t["pnl"] for t in trades)
    wr     = 100 * len(wins) / max(1, len(wins) + len(losses))
    exp    = pnl / n
    print(f"Trades fired: {n}")
    print(f"  buy:  {sum(1 for t in trades if t['side'] > 0)}")
    print(f"  sell: {sum(1 for t in trades if t['side'] < 0)}")
    print(f"WR: {wr:.1f}%   ({len(wins)}W / {len(losses)}L / {len(flat)}flat)")
    print(f"Total PnL: ${pnl:+.2f}  Expectancy: ${exp:+.2f}/trade")
    print(f"Avg win:   ${(sum(t['pnl'] for t in wins) / max(1, len(wins))):+.2f}")
    print(f"Avg loss:  ${(sum(t['pnl'] for t in losses) / max(1, len(losses))):+.2f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    print(f"Exit reasons: {reasons}")

    # Alignment with Zee
    matched_zee = 0
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        for s in signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= 3 * 60:
                matched_zee += 1; break
    print(f"\nAlignment with Zee (±3 min same side): {matched_zee}/{len(ZEE_TRADES)} "
          f"({100*matched_zee/len(ZEE_TRADES):.0f}%)")

    print(f"\n--- All {n} trades ---")
    for t in trades:
        ts = datetime.fromtimestamp(t["time"], tz=UTC).strftime("%H:%M")
        side = "BUY " if t["side"] > 0 else "SELL"
        marker = "✓" if t["pnl"] > 0 else ("✗" if t["pnl"] < 0 else "·")
        print(f"  {ts}  {side} @ {t['entry']:8.2f}  {marker} ${t['pnl']:+6.2f}  {t['reason']}")


if __name__ == "__main__":
    main()
