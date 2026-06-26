"""v230_backtest.py — Thorough backtest of S1 v2.30 and S3 v2.30 on real ticks.

Tests the EXACT v2.30 config:
  S1: BigSpread=OFF, H1Fvg=OFF, BUY+SELL, SL=2.0, TP=7.5pts
  S3: M5Fvg=OFF, BUY+SELL, UpperWick=0.35, SL_buf=2.0, TP=peak

Uses ticks_for_testing.csv (70k M1 bars from Exness) for signal detection,
and shano_ticks_*.csv for tick-level trade replay.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

COMMON   = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "ticks_for_testing.csv"
CONTRACT = 100.0

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
# S1 v2.30 DETECTOR — BigSpread=OFF, H1Fvg=OFF, BUY+SELL
# ════════════════════════════════════════════════════════════════

def detect_s1_v230(m5, trend_lb=24, trend_thresh=2.0, retrace_lb=15,
                   sl_buf=2.0, tp_pts=7.5):
    sigs = []
    fired_bars = set()  # dedup by bar time
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"] in fired_bars:
            continue
        rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue

        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if bo["close"] <= bo["open"]:
                    continue
                trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
                if trend_move <= trend_thresh:
                    continue
                # Collect retracement reds
                reds = []
                for j in range(i - retrace_lb, i):
                    if j < 0: continue
                    if m5[j]["close"] < m5[j]["open"]:
                        reds.append(j)
                if not reds:
                    continue
                # UHV red = highest volume red
                uhv_idx = max(reds, key=lambda j: m5[j]["vol"])
                uhv_h = m5[uhv_idx]["high"]
                uhv_l = m5[uhv_idx]["low"]
                # Breakout: bo.close > uhv.high, bo.open <= uhv.high
                if bo["close"] <= uhv_h or bo["open"] > uhv_h:
                    continue
                # Sweep: some bar between uhv and bo has low < uhv_l
                swept = any(m5[k]["low"] < uhv_l for k in range(uhv_idx + 1, i))
                if not swept:
                    continue
                sl_dist = bo["close"] - (uhv_l - sl_buf)
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_pts, "sl": sl_dist,
                             "day": bo["time"].strftime("%Y-%m-%d")})
                fired_bars.add(bo["time"])

            else:  # SELL
                if bo["close"] >= bo["open"]:
                    continue
                trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
                if trend_move <= trend_thresh:
                    continue
                greens = []
                for j in range(i - retrace_lb, i):
                    if j < 0: continue
                    if m5[j]["close"] > m5[j]["open"]:
                        greens.append(j)
                if not greens:
                    continue
                uhv_idx = max(greens, key=lambda j: m5[j]["vol"])
                uhv_h = m5[uhv_idx]["high"]
                uhv_l = m5[uhv_idx]["low"]
                if bo["close"] >= uhv_l or bo["open"] < uhv_l:
                    continue
                swept = any(m5[k]["high"] > uhv_h for k in range(uhv_idx + 1, i))
                if not swept:
                    continue
                sl_dist = (uhv_h + sl_buf) - bo["close"]
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_pts, "sl": sl_dist,
                             "day": bo["time"].strftime("%Y-%m-%d")})
                fired_bars.add(bo["time"])
    return sigs


# ════════════════════════════════════════════════════════════════
# S3 v2.30 DETECTOR — M5Fvg=OFF, BUY+SELL, UpperWick=0.35
# ════════════════════════════════════════════════════════════════

def detect_s3_v230(m5, trend_lb=24, trend_thresh=1.0, retrace_lb=30,
                   tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35):
    sigs = []
    fired_reds = set()  # dedup by red ref time (matches live EA)

    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue

        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if bo["close"] <= bo["open"]:
                    continue
                # Upper wick filter
                if max_upper_wick > 0:
                    upper_wick = bo["high"] - bo["close"]
                    if upper_wick / rng > max_upper_wick:
                        continue
                # Uptrend
                trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
                if trend_move <= trend_thresh:
                    continue
                # Find retracement: reds after a green whose low got broken
                reds = []
                max_red_shift = 0
                for back_g_offset in range(2, retrace_lb + 1):
                    gi = i - back_g_offset
                    if gi < 0: break
                    g = m5[gi]
                    if g["close"] <= g["open"]: continue
                    g_l = g["low"]
                    any_broke = False
                    tmp_reds = []
                    for j_offset in range(back_g_offset - 1, 0, -1):
                        ji = i - j_offset
                        if ji < 0 or ji >= i: continue
                        r = m5[ji]
                        if r["close"] < r["open"]:
                            if r["close"] < g_l or r["low"] < g_l:
                                any_broke = True
                            tmp_reds.append(ji)
                    if any_broke and tmp_reds:
                        reds = tmp_reds
                        max_red_shift = max(i - r for r in reds)
                        break
                if not reds: continue

                # Wicking pattern
                matching_red_idx = -1
                matching_red_t = None
                for ri in reds:
                    r_l = m5[ri]["low"]
                    r_v = m5[ri]["vol"]
                    if bo["low"] >= r_l: continue
                    if bo["close"] <= r_l: continue
                    if bo["vol"] <= r_v: continue
                    matching_red_idx = ri
                    matching_red_t = m5[ri]["time"]
                    break
                if matching_red_idx < 0: continue
                if matching_red_t in fired_reds: continue

                # TP/SL
                sl = bo["low"] - sl_buf
                tp = max(m5[j]["high"] for j in range(max(0, i - tp_peak_lb), i))
                entry_est = bo["close"]
                min_tp_dist = min(0.2, sl_buf * 2.0)
                if tp <= entry_est + min_tp_dist: continue
                tp_dist = tp - entry_est
                sl_dist = entry_est - sl

                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist,
                             "day": bo["time"].strftime("%Y-%m-%d"),
                             "red_t": matching_red_t})
                fired_reds.add(matching_red_t)

            else:  # SELL (mirror)
                if bo["close"] >= bo["open"]:
                    continue
                # Downtrend
                trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
                if trend_move <= trend_thresh:
                    continue
                # Find retracement: greens after a red whose high got broken
                greens = []
                max_green_shift = 0
                for back_r_offset in range(2, retrace_lb + 1):
                    ri = i - back_r_offset
                    if ri < 0: break
                    r = m5[ri]
                    if r["close"] >= r["open"]: continue
                    r_h = r["high"]
                    any_broke = False
                    tmp_greens = []
                    for j_offset in range(back_r_offset - 1, 0, -1):
                        ji = i - j_offset
                        if ji < 0 or ji >= i: continue
                        g = m5[ji]
                        if g["close"] > g["open"]:
                            if g["close"] > r_h or g["high"] > r_h:
                                any_broke = True
                            tmp_greens.append(ji)
                    if any_broke and tmp_greens:
                        greens = tmp_greens
                        max_green_shift = max(i - g for g in greens)
                        break
                if not greens: continue

                # Wicking pattern (mirror): bo wicks ABOVE green's high, closes back below
                matching_green_idx = -1
                matching_green_t = None
                for gi in greens:
                    g_h = m5[gi]["high"]
                    g_v = m5[gi]["vol"]
                    if bo["high"] <= g_h: continue
                    if bo["close"] >= g_h: continue
                    if bo["vol"] <= g_v: continue
                    matching_green_idx = gi
                    matching_green_t = m5[gi]["time"]
                    break
                if matching_green_idx < 0: continue
                if matching_green_t in fired_reds: continue

                # TP/SL
                sl = bo["high"] + sl_buf
                trough = min(m5[j]["low"] for j in range(max(0, i - tp_peak_lb), i))
                entry_est = bo["close"]
                min_tp_dist = min(0.2, sl_buf * 2.0)
                if trough >= entry_est - min_tp_dist: continue
                tp_dist = entry_est - trough
                sl_dist = sl - entry_est

                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist,
                             "day": bo["time"].strftime("%Y-%m-%d"),
                             "red_t": matching_green_t})
                fired_reds.add(matching_green_t)
    return sigs


# ════════════════════════════════════════════════════════════════
# TICK REPLAY (handles both BUY and SELL)
# ════════════════════════════════════════════════════════════════

def replay(ticks, sigs, lots):
    ppp = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
            else:  # SELL
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            if len(units) < 3:
                e = ask if pend["side"] == "BUY" else bid
                units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    # Close remaining at market
    for u in units:
        p = ((ticks[-1]["bid"] - u["e"]) if u["side"] == "BUY" else (u["e"] - ticks[-1]["ask"])) * ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def print_results(label, all_trades, train_trades, oos_trades, nd, train_days, oos_days, daily_pnl, lots):
    n_all = len(all_trades)
    if n_all == 0:
        print(f"  No trades.\n")
        return

    w_all = sum(1 for t in all_trades if t["r"] == "W")
    wr_all = w_all / n_all * 100
    tot_all = sum(t["pnl"] for t in all_trades)
    avg_w = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w_all if w_all else 0
    l_count = n_all - w_all
    avg_l = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / l_count if l_count else 0
    ev = tot_all / n_all

    # Train/OOS
    n_train = len(train_trades)
    tot_train = sum(t["pnl"] for t in train_trades)
    n_oos = len(oos_trades)
    w_oos = sum(1 for t in oos_trades if t["r"] == "W")
    tot_oos = sum(t["pnl"] for t in oos_trades)
    wr_oos = w_oos / n_oos * 100 if n_oos else 0

    # Direction split
    buys  = [t for t in all_trades if t["side"] == "BUY"]
    sells = [t for t in all_trades if t["side"] == "SELL"]
    buy_pnl = sum(t["pnl"] for t in buys)
    sell_pnl = sum(t["pnl"] for t in sells)
    buy_wr = sum(1 for t in buys if t["r"] == "W") / len(buys) * 100 if buys else 0
    sell_wr = sum(1 for t in sells if t["r"] == "W") / len(sells) * 100 if sells else 0

    # Drawdown
    equity = 0; peak = 0; max_dd = 0
    for t in sorted(all_trades, key=lambda x: x["fire"]):
        equity += t["pnl"]
        if equity > peak: peak = equity
        dd = peak - equity
        if dd > max_dd: max_dd = dd

    # Green/red days
    green_d = sum(1 for p in daily_pnl.values() if p > 0)
    red_d = sum(1 for p in daily_pnl.values() if p <= 0)

    wf_pass = "YES ✅" if tot_train > 0 and tot_oos > 0 else "NO ❌"

    print(f"  {'─'*70}")
    print(f"  TOTAL:  n={n_all:>4}  WR={wr_all:>5.1f}%  AvgW=${avg_w:>+7.1f}  AvgL=${avg_l:>+7.1f}")
    print(f"          P&L=${tot_all:>+9.1f}  EV/trade=${ev:>+7.2f}  $/day=${tot_all/nd:>+7.1f}")
    print(f"  MaxDD:  ${max_dd:>.1f}  |  Green/Red days: {green_d}/{red_d}")
    print(f"")
    print(f"  BUY:    n={len(buys):>4}  WR={buy_wr:>5.1f}%  P&L=${buy_pnl:>+9.1f}  EV=${buy_pnl/len(buys) if buys else 0:>+7.2f}")
    print(f"  SELL:   n={len(sells):>4}  WR={sell_wr:>5.1f}%  P&L=${sell_pnl:>+9.1f}  EV=${sell_pnl/len(sells) if sells else 0:>+7.02f}")
    print(f"")
    print(f"  TRAIN ({train_days[0]}→{train_days[-1]}): n={n_train}  P&L=${tot_train:>+9.1f}")
    print(f"  OOS   ({oos_days[0]}→{oos_days[-1]}): n={n_oos}  WR={wr_oos:>5.1f}%  P&L=${tot_oos:>+9.1f}")
    print(f"  WALK-FORWARD: {wf_pass}")
    print()


def main():
    print("=" * 78)
    print("  S1 v2.30 + S3 v2.30 BACKTEST ON REAL TICKS")
    print("  (ticks_for_testing.csv from Exness)")
    print("=" * 78)
    print()

    print("Loading M1 bars from ticks_for_testing.csv ...")
    m1 = load_bars()
    m5 = build_m5(m1)
    print(f"  {len(m1)} M1 bars  |  {len(m5)} M5 bars")
    print(f"  Range: {m1[0]['time'].date()} → {m1[-1]['time'].date()}")
    print()

    # Load all tick files
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
    oos_days   = days[mid:]
    print(f"  {nd} tick days  |  TRAIN: {train_days[0]}→{train_days[-1]} ({len(train_days)}d)  |  OOS: {oos_days[0]}→{oos_days[-1]} ({len(oos_days)}d)")
    print()

    LOTS = 0.01  # Exness lot size

    for ea_name, detector in [("S1 v2.30", detect_s1_v230), ("S3 v2.30", detect_s3_v230)]:
        print("=" * 78)
        print(f"  {ea_name}  @  {LOTS} lots")
        print("=" * 78)

        sigs = detector(m5)
        all_trades, train_trades, oos_trades = [], [], []
        daily_pnl = {}

        for day in days:
            if day not in tick_cache:
                continue
            day_sigs = [s for s in sigs if s["day"] == day]
            trades   = replay(tick_cache[day], day_sigs, LOTS)
            day_pnl = sum(t["pnl"] for t in trades)
            daily_pnl[day] = day_pnl
            n = len(trades)
            w = sum(1 for t in trades if t["r"] == "W")
            wr = w / n * 100 if n else 0
            side_b = sum(1 for t in trades if t["side"] == "BUY")
            side_s = sum(1 for t in trades if t["side"] == "SELL")
            split = "TRAIN" if day in train_days else "OOS  "
            print(f"  {day} [{split}]  n={n:>3} (B{side_b}/S{side_s})  WR={wr:>5.1f}%  P&L=${day_pnl:>+8.1f}")
            all_trades.extend(trades)
            (train_trades if day in train_days else oos_trades).extend(trades)

        print_results(ea_name, all_trades, train_trades, oos_trades, nd,
                      train_days, oos_days, daily_pnl, LOTS)

    # Summary comparison
    print("=" * 78)
    print("  SAFE TO DEPLOY?")
    print("=" * 78)
    print("""
  Check these criteria for each EA:
    1. Walk-forward positive (TRAIN > 0 AND OOS > 0)
    2. Max drawdown < $20 at 0.01 lots (manageable for $126 account)
    3. Both BUY and SELL sides contribute (not one-sided)
    4. Green days > Red days (consistency)
""")

if __name__ == "__main__":
    main()
