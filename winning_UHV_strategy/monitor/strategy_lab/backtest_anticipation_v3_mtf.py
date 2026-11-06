"""backtest_anticipation_v3_mtf.py - same v3 rules across M1/M5/M15/M30/H1.

Per Zee's hint: "aur timeframes par bhi try kar lain". M1 v3 fired only 2
trades (too thin). Higher timeframes may carry more meaningful wicks /
fewer false positives. Each TF gets:
  - the same sweep+reverse rule (counter-trend wick >= 2x body, >=$1.5)
  - the same time window (16:00-20:00 UTC)
  - the same confirmation rule (next-bar close beyond previous bar's range)
  - the same RR=1.5 simulation against subsequent same-TF bars
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from build_feb11_lab import load_feb11_bars, ZEE_TRADES

WINDOW_START_HOUR = 16
WINDOW_END_HOUR   = 20
MIN_WICK_BODY     = 2.0
MIN_WICK_ABS      = 1.5
SL_MAX_USD        = 3.0
RR                = 1.5
TIME_STOP_BARS    = 20
USD_PER_PRICE     = 0.05 * 100


def aggregate(m1_bars, k):
    """Aggregate consecutive `k` M1 bars into one OHLC bar.
    First bar = M1 idx [0, k-1], time = first bar's time (open of bucket)."""
    out = []
    for start in range(0, len(m1_bars), k):
        chunk = m1_bars[start:start + k]
        if len(chunk) < k: break   # drop incomplete tail
        out.append({
            "time":  chunk[0]["time"],
            "open":  chunk[0]["open"],
            "high":  max(b["high"] for b in chunk),
            "low":   min(b["low"]  for b in chunk),
            "close": chunk[-1]["close"],
            "vol":   sum(b["vol"] for b in chunk),
        })
    return out


def in_window(ts):
    h = datetime.fromtimestamp(ts, tz=UTC).hour
    return WINDOW_START_HOUR <= h < WINDOW_END_HOUR


def trend_up(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx]["close"] - bars[idx - lookback]["close"] >= threshold


def trend_down(bars, idx, lookback=30, threshold=0.5):
    if idx < lookback: return False
    return bars[idx - lookback]["close"] - bars[idx]["close"] >= threshold


def detect_sweep(bars, idx, trend_lb):
    if idx < trend_lb: return None
    b = bars[idx]
    body = abs(b["close"] - b["open"])
    if body < 0.01: return None
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]
    if b["close"] < b["open"] and trend_up(bars, idx, lookback=trend_lb):
        if lower_wick >= MIN_WICK_BODY * body and lower_wick >= MIN_WICK_ABS:
            return (+1, b["low"])
    if b["close"] > b["open"] and trend_down(bars, idx, lookback=trend_lb):
        if upper_wick >= MIN_WICK_BODY * body and upper_wick >= MIN_WICK_ABS:
            return (-1, b["high"])
    return None


def simulate(bars, fire_idx, side, entry_price, swept):
    if side > 0:
        sl_dist = min(SL_MAX_USD, max(0.1, entry_price - swept))
        sl_price = entry_price - sl_dist
        tp_price = entry_price + RR * sl_dist
    else:
        sl_dist = min(SL_MAX_USD, max(0.1, swept - entry_price))
        sl_price = entry_price + sl_dist
        tp_price = entry_price - RR * sl_dist
    for j in range(fire_idx + 1, min(fire_idx + 1 + TIME_STOP_BARS, len(bars))):
        bar = bars[j]
        if side > 0:
            if bar["low"]  <= sl_price: return (-sl_dist * USD_PER_PRICE, "SL")
            if bar["high"] >= tp_price: return (+RR * sl_dist * USD_PER_PRICE, "TP")
        else:
            if bar["high"] >= sl_price: return (-sl_dist * USD_PER_PRICE, "SL")
            if bar["low"]  <= tp_price: return (+RR * sl_dist * USD_PER_PRICE, "TP")
    last_close = bars[min(fire_idx + TIME_STOP_BARS, len(bars) - 1)]["close"]
    pnl_p = (last_close - entry_price) if side > 0 else (entry_price - last_close)
    return (pnl_p * USD_PER_PRICE, "TIMEOUT")


def run_on_tf(label, bars, trend_lb):
    signals = []; trades = []
    for i in range(len(bars) - 2):
        if not in_window(bars[i]["time"]): continue
        cand = detect_sweep(bars, i, trend_lb)
        if not cand: continue
        side, swept = cand
        nb = bars[i + 1]
        if side > 0 and nb["close"] <= bars[i]["high"]: continue
        if side < 0 and nb["close"] >= bars[i]["low"]:  continue
        signals.append({"time": bars[i]["time"], "side": side})
        entry = nb["close"]
        pnl, reason = simulate(bars, i + 1, side, entry, swept)
        trades.append({"time": bars[i + 1]["time"], "side": side, "entry": entry,
                       "pnl": pnl, "reason": reason})

    n = len(trades)
    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    pnl    = sum(t["pnl"] for t in trades)
    wr     = 100 * len(wins) / max(1, len(wins) + len(losses)) if (wins or losses) else 0.0
    exp    = pnl / max(1, n)

    # Alignment with Zee (±3 min, same side)
    matched = 0
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        for s in signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= 3 * 60:
                matched += 1; break

    return {
        "label": label, "n": n, "wins": len(wins), "losses": len(losses),
        "wr": wr, "pnl": pnl, "exp": exp,
        "buy":  sum(1 for t in trades if t["side"] > 0),
        "sell": sum(1 for t in trades if t["side"] < 0),
        "zee_match": matched, "trades": trades,
    }


def main():
    m1 = load_feb11_bars()
    if not m1:
        print("ERROR: no bars"); return

    tfs = [
        ("M1",  m1,               30),
        ("M5",  aggregate(m1, 5),  20),
        ("M15", aggregate(m1, 15), 12),
        ("M30", aggregate(m1, 30), 8),
        ("H1",  aggregate(m1, 60), 6),
    ]
    print(f"Window 16:00-20:00 UTC  Wick>={MIN_WICK_BODY}x body & >=${MIN_WICK_ABS}  "
          f"SL_max=${SL_MAX_USD}  RR={RR}\n")
    print(f"{'TF':<5}{'bars':>6}{'sigs':>6}{'B/S':>10}{'W/L':>9}{'WR%':>7}"
          f"{'PnL':>10}{'Exp':>9}{'ZeeMatch':>11}")
    print("-" * 73)
    results = []
    for label, bars, lb in tfs:
        r = run_on_tf(label, bars, lb)
        results.append((label, bars, r))
        bs = f"{r['buy']}/{r['sell']}"
        wl = f"{r['wins']}/{r['losses']}"
        zm = f"{r['zee_match']}/{len(ZEE_TRADES)}"
        print(f"{label:<5}{len(bars):>6}{r['n']:>6}{bs:>10}{wl:>9}"
              f"{r['wr']:>6.1f}%{r['pnl']:>+9.2f}{r['exp']:>+8.2f}{zm:>11}")

    # Per-TF trade detail for the best ones
    print()
    for label, _bars, r in results:
        if r["n"] == 0: continue
        print(f"\n--- {label} trades ({r['n']}) ---")
        for t in r["trades"]:
            ts = datetime.fromtimestamp(t["time"], tz=UTC).strftime("%H:%M")
            side = "BUY " if t["side"] > 0 else "SELL"
            mark = "✓" if t["pnl"] > 0 else ("✗" if t["pnl"] < 0 else "·")
            print(f"  {ts} {side} @ {t['entry']:8.2f}  {mark} ${t['pnl']:+6.2f}  {t['reason']}")


if __name__ == "__main__":
    main()
