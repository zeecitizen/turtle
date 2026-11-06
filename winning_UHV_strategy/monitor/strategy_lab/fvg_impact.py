"""fvg_impact.py — S3 WITH vs WITHOUT M5 FVG filter on real ticks.

IMPORTANT FINDING FROM SOURCE: S3Trader.mq5 is BUY-ONLY (no sell function).
S1Trader.mq5 does both BUY+SELL. S1 has NO FVG filter at all.

So this test focuses on S3 BUY signals with/without the M5 FVG gate.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

COMMON   = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "bars_for_gravity.csv"
CONTRACT = 100.0
S3_LOTS  = 0.09

# ════════════════════════════════════════════════════════════════
# DATA LOADERS
# ════════════════════════════════════════════════════════════════

def load_bars():
    bars = []
    with open(BARS_CSV, "r") as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except:
                continue
            bars.append({
                "time":  t,
                "open":  float(row["open"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
                "close": float(row["close"]),
                "vol":   int(row["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars

def load_ticks(path):
    ticks = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
            except ValueError:
                continue
            ticks.append({"t": t, "bid": float(row["bid"]), "ask": float(row["ask"])})
    return ticks

def build_m5(m1):
    m5, bucket = [], []
    for b in m1:
        if b["time"].minute % 5 == 0 and bucket:
            m5.append({"time": bucket[0]["time"],
                       "open": bucket[0]["open"],
                       "high": max(x["high"] for x in bucket),
                       "low":  min(x["low"]  for x in bucket),
                       "close": bucket[-1]["close"],
                       "vol":  sum(x["vol"]  for x in bucket)})
            bucket = [b]
        else:
            bucket.append(b)
    if bucket:
        m5.append({"time": bucket[0]["time"],
                   "open": bucket[0]["open"],
                   "high": max(x["high"] for x in bucket),
                   "low":  min(x["low"]  for x in bucket),
                   "close": bucket[-1]["close"],
                   "vol":  sum(x["vol"]  for x in bucket)})
    return m5

# ════════════════════════════════════════════════════════════════
# M5 FVG DETECTION (matching MQL5 M5FvgTappedDuringRetracement)
# ════════════════════════════════════════════════════════════════

def has_m5_fvg_tap(m5, signal_idx, retrace_back_bars, lookback=60):
    """Check if any M5 bar in the retracement taps an unfilled bullish FVG.
    Matches S3Trader.mq5 M5FvgTappedDuringRetracement logic:
      - For each retracement bar k (1..retrace_back_bars from signal_idx):
        - For each candidate FVG center i (k+1..k+lookback):
          - Gap: m5[i-2].high < m5[i].low (bullish FVG)
          - Unfilled: no bar between i+1 and k-1 has low < m5[i-2].high
          - Tap: bar k overlaps the gap zone
    """
    for k_offset in range(1, retrace_back_bars + 1):
        k = signal_idx - k_offset
        if k < 0:
            continue
        mlow  = m5[k]["low"]
        mhigh = m5[k]["high"]
        for i_offset in range(k_offset + 1, k_offset + 1 + lookback):
            i = signal_idx - i_offset
            if i - 2 < 0:
                break
            older_high = m5[i - 2]["high"]
            newer_low  = m5[i]["low"]
            if newer_low <= older_high:
                continue  # no bullish gap
            # Check unfilled: no bar between (i+1) and (k-1) has low < older_high
            filled = False
            for j in range(i + 1, k):
                if m5[j]["low"] < older_high:
                    filled = True
                    break
            if filled:
                continue
            # Tap check
            if mlow <= newer_low and mhigh >= older_high:
                return True
    return False


# ════════════════════════════════════════════════════════════════
# S3 BUY-ONLY DETECTOR (faithful to MQL5 source)
# ════════════════════════════════════════════════════════════════

def detect_s3_buys(m5, day_str, require_fvg=False,
                   trend_lb=24, trend_thresh=1.0, retrace_lb=30,
                   tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str:
            continue
        # BUY-ONLY: must be green candle
        if bo["close"] <= bo["open"]:
            continue
        rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue

        # Upper wick filter
        if max_upper_wick > 0:
            upper_wick = bo["high"] - bo["close"]
            if upper_wick / rng > max_upper_wick:
                continue

        # Uptrend check
        trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
        if trend_move <= trend_thresh:
            continue

        # Find retracement reds: reds after a green whose low got broken
        win = m5[i - retrace_lb:i]
        reds = []
        max_red_shift = 0
        for back_g_offset in range(2, retrace_lb + 1):
            gi = i - back_g_offset
            if gi < 0:
                break
            g = m5[gi]
            if g["close"] <= g["open"]:
                continue  # not green
            g_l = g["low"]
            any_broke = False
            tmp_reds = []
            for j_offset in range(back_g_offset - 1, 0, -1):
                ji = i - j_offset
                if ji < 0 or ji >= i:
                    continue
                r = m5[ji]
                if r["close"] < r["open"]:  # red
                    if r["close"] < g_l or r["low"] < g_l:
                        any_broke = True
                    tmp_reds.append(ji)
            if any_broke and tmp_reds:
                reds = tmp_reds
                max_red_shift = max(i - r for r in reds)
                break

        if not reds:
            continue

        # Wicking pattern: bo wicks below red.low, closes back inside, higher vol
        matching_red_idx = -1
        for ri in reds:
            r_l = m5[ri]["low"]
            r_v = m5[ri]["vol"]
            if bo["low"] >= r_l:
                continue
            if bo["close"] <= r_l:
                continue
            if bo["vol"] <= r_v:
                continue
            matching_red_idx = ri
            break

        if matching_red_idx < 0:
            continue

        # M5 FVG filter (optional)
        if require_fvg and not has_m5_fvg_tap(m5, i, max_red_shift):
            continue

        # TP / SL
        sl = bo["low"] - sl_buf
        tp = max(m5[j]["high"] for j in range(max(0, i - tp_peak_lb), i))
        entry_est = bo["close"]  # approximate
        min_tp_dist = min(0.2, sl_buf * 2.0)
        if tp <= entry_est + min_tp_dist:
            continue

        tp_dist = tp - entry_est
        sl_dist = entry_est - sl
        sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                     "tp": tp_dist, "sl": sl_dist, "day": day_str})
    return sigs


# ════════════════════════════════════════════════════════════════
# TICK REPLAY
# ════════════════════════════════════════════════════════════════

def replay(ticks, sigs, lots):
    ppp = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if bid <= u["e"] - u["sl"]:
                u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
            elif bid >= u["e"] + u["tp"]:
                u["pnl"] = u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            if len(units) < 3:
                e = ask  # BUY entry
                units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = (ticks[-1]["bid"] - u["e"]) * ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("Loading bars from bars_for_gravity.csv ...")
    m1 = load_bars()
    m5 = build_m5(m1)
    print(f"  {len(m1)} M1 bars  |  {len(m5)} M5 bars")
    print(f"  Range: {m1[0]['time'].date()} → {m1[-1]['time'].date()}")
    print()

    # Load tick files
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tick_cache, days = {}, []
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        ticks = load_ticks(tf)
        if len(ticks) < 500:
            continue
        tick_cache[d] = ticks
        days.append(d)
    days.sort()
    nd = len(days)
    mid = nd // 2
    train_days = days[:mid]
    test_days  = days[mid:]
    print(f"  {nd} tick days  |  TRAIN {train_days[0]}→{train_days[-1]}  |  OOS {test_days[0]}→{test_days[-1]}")
    print()

    # ── IMPORTANT CONTEXT ──
    print("=" * 80)
    print("  KEY FINDING FROM S3Trader.mq5 SOURCE CODE:")
    print("  • S3 is BUY-ONLY in the live EA (no TryS3SellSignal exists)")
    print("  • S1 does both BUY+SELL but has NO FVG filter at all")
    print("  • Only S3's BUY signals are gated by InpRequireM5Fvg=true")
    print("=" * 80)
    print()

    configs = [
        ("S3 BUY-only (no FVG)",  False),
        ("S3 BUY-only (M5 FVG)",  True),
    ]

    for label, require_fvg in configs:
        all_trades, train_trades, oos_trades = [], [], []
        daily_pnl = {}

        print(f"{'='*80}")
        print(f"  {label}")
        print(f"{'='*80}")

        for day in days:
            if day not in tick_cache:
                continue
            sigs   = detect_s3_buys(m5, day, require_fvg=require_fvg)
            trades = replay(tick_cache[day], sigs, S3_LOTS)
            day_pnl = sum(t["pnl"] for t in trades)
            daily_pnl[day] = day_pnl
            n = len(trades)
            w = sum(1 for t in trades if t["r"] == "W")
            wr = w / n * 100 if n else 0
            split = "TRAIN" if day in train_days else "OOS"
            print(f"  {day} [{split}]  n={n:>3}  WR={wr:>5.1f}%  P&L=${day_pnl:>+9.1f}")
            all_trades.extend(trades)
            (train_trades if day in train_days else oos_trades).extend(trades)

        n_all = len(all_trades)
        if n_all == 0:
            print("  No trades.\n")
            continue
        w_all  = sum(1 for t in all_trades if t["r"] == "W")
        wr_all = w_all / n_all * 100
        tot_all = sum(t["pnl"] for t in all_trades)
        avg_w  = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w_all if w_all else 0
        avg_l  = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / (n_all - w_all) if (n_all - w_all) else 0

        tot_train = sum(t["pnl"] for t in train_trades)
        n_oos = len(oos_trades)
        w_oos = sum(1 for t in oos_trades if t["r"] == "W")
        tot_oos = sum(t["pnl"] for t in oos_trades)
        wr_oos = w_oos / n_oos * 100 if n_oos else 0
        wf = "✓" if tot_train > 0 and tot_oos > 0 else " "

        green_days = sum(1 for p in daily_pnl.values() if p > 0)
        red_days   = sum(1 for p in daily_pnl.values() if p <= 0)

        print(f"  {'─'*76}")
        print(f"  ALL:   n={n_all:>4}  WR={wr_all:>5.1f}%  AvgW=${avg_w:>+7.1f}  AvgL=${avg_l:>+7.1f}  P&L=${tot_all:>+9.1f}  $/day=${tot_all/nd:>+6.1f}")
        print(f"  TRAIN: n={len(train_trades):>4}                                      P&L=${tot_train:>+9.1f}")
        print(f"  OOS:   n={n_oos:>4}  WR={wr_oos:>5.1f}%                             P&L=${tot_oos:>+9.1f}  WF={wf}")
        print(f"  Green/Red days: {green_days}/{red_days}")
        print()

    print("=" * 80)
    print("  VERDICT")
    print("=" * 80)
    print("""
  If NO-FVG is walk-forward positive and generates more trades:
    → Remove the FVG filter from S3Trader.mq5 (set InpRequireM5Fvg=false)
    → More signals, especially on trending days like today's selloff

  If WITH-FVG has better EV/trade and higher WR:
    → Keep the filter, accept fewer trades (quality > quantity)

  NOTE: S3 is buy-only, so in a DOWNTREND day (like today May 26),
  S3 won't fire AT ALL regardless of FVG filter — the uptrend check blocks it.
  To trade downtrends, S3 would need a SELL function added.
""")


if __name__ == "__main__":
    main()
