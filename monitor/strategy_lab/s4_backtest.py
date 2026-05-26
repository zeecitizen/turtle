"""s4_backtest.py — Thorough S4 v1.00 backtest on real ticks.

Faithfully replicates the MQL5 S4Trader logic:
  - M1 timeframe (NOT M5 like S1/S3)
  - HH/HL structure trend (recent 15 vs prior 15 M1 bars)
  - UHV candle in last 12 M1 bars
  - Low-volume momentum breakout candle (body>avg, body/range>0.55)
  - TP=12, SL=6 (2:1 R:R)
  - ER regime filter (>= 0.15)
  - No sweep, no big-spread, no FVG
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

def load_m1():
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


# ════════════════════════════════════════════════════════════════
# S4 DETECTOR (faithful to MQL5 TrySignal)
# ════════════════════════════════════════════════════════════════

def detect_s4(m1, day_str,
              trend_lb=30, retrace_lb=12, mom_body_frac=0.55,
              tp_pts=12.0, sl_pts=6.0, er_min=0.15):
    sigs = []
    fired_bars = set()
    half = trend_lb // 2

    for i in range(trend_lb + 2, len(m1)):
        bo = m1[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str:
            continue
        if bo["time"] in fired_bars:
            continue

        rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < mom_body_frac:
            continue

        # Avg body over retracement window
        sb = 0
        nb = 0
        for s in range(max(0, i - retrace_lb), i + 1):
            sb += abs(m1[s]["close"] - m1[s]["open"])
            nb += 1
        avg_body = sb / nb if nb > 0 else 0
        if body < avg_body:
            continue

        # Efficiency Ratio (regime filter)
        if er_min > 0:
            net = abs(m1[i]["close"] - m1[max(0, i - trend_lb)]["close"])
            path = sum(abs(m1[s]["close"] - m1[s + 1]["close"])
                       for s in range(max(0, i - trend_lb), i))
            er = net / path if path > 0 else 0
            if er < er_min:
                continue

        # HH/HL structure
        rHi = max(m1[j]["high"] for j in range(max(0, i - half), i))
        rLo = min(m1[j]["low"]  for j in range(max(0, i - half), i))
        oHi = max(m1[j]["high"] for j in range(max(0, i - trend_lb), max(0, i - half)))
        oLo = min(m1[j]["low"]  for j in range(max(0, i - trend_lb), max(0, i - half)))

        td = 0
        if rHi > oHi and rLo > oLo:
            td = 1   # uptrend
        elif rHi < oHi and rLo < oLo:
            td = -1  # downtrend

        # BUY: green momentum, uptrend, breaks above UHV red's high
        if bo["close"] > bo["open"] and td == 1:
            uhv_v = -1
            uhv_h = 0
            for s in range(max(0, i - retrace_lb), i):
                if m1[s]["close"] < m1[s]["open"]:  # red
                    if m1[s]["vol"] > uhv_v:
                        uhv_v = m1[s]["vol"]
                        uhv_h = m1[s]["high"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=1),
                             "tp": tp_pts, "sl": sl_pts,
                             "day": day_str})
                fired_bars.add(bo["time"])
                continue  # don't check sell for same bar

        # SELL: red momentum, downtrend, breaks below UHV green's low
        if bo["close"] < bo["open"] and td == -1:
            uhv_v = -1
            uhv_l = 999999
            for s in range(max(0, i - retrace_lb), i):
                if m1[s]["close"] > m1[s]["open"]:  # green
                    if m1[s]["vol"] > uhv_v:
                        uhv_v = m1[s]["vol"]
                        uhv_l = m1[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=1),
                             "tp": tp_pts, "sl": sl_pts,
                             "day": day_str})
                fired_bars.add(bo["time"])

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
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"] - u["e"]) if u["side"] == "BUY" else (u["e"] - ticks[-1]["ask"])) * ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("=" * 78)
    print("  S4 v1.00 BACKTEST — Zee's Feb-11 Entry, Mechanized")
    print("  TP=$12 / SL=$6 (2:1 R:R) — Real tick replay")
    print("=" * 78)
    print()

    m1 = load_m1()
    print(f"  {len(m1)} M1 bars  |  {m1[0]['time'].date()} → {m1[-1]['time'].date()}")

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
    oos_days = days[mid:]
    print(f"  {nd} tick days  |  TRAIN: {train_days[0]}→{train_days[-1]} ({len(train_days)}d)  |  OOS: {oos_days[0]}→{oos_days[-1]} ({len(oos_days)}d)")
    print()

    # Test multiple lot sizes for context
    for lots, label in [(0.01, "0.01 (Exness $126)"), (0.02, "0.02 (FTMO safe)"), (0.10, "0.10 (FTMO full)")]:
        print("=" * 78)
        print(f"  S4 @ {label}")
        print("=" * 78)

        all_trades, train_trades, oos_trades = [], [], []
        daily_pnl = {}

        for day in days:
            sigs = detect_s4(m1, day)
            trades = replay(tick_cache[day], sigs, lots)
            day_pnl = sum(t["pnl"] for t in trades)
            daily_pnl[day] = day_pnl
            n = len(trades)
            w = sum(1 for t in trades if t["r"] == "W")
            wr = w / n * 100 if n else 0
            side_b = sum(1 for t in trades if t["side"] == "BUY")
            side_s = sum(1 for t in trades if t["side"] == "SELL")
            split = "TRAIN" if day in train_days else "OOS  "
            marker = "🟢" if day_pnl > 0 else "🔴" if day_pnl < 0 else "⚪"
            print(f"  {day} [{split}]  n={n:>3} (B{side_b}/S{side_s})  WR={wr:>5.1f}%  P&L=${day_pnl:>+9.1f}  {marker}")
            all_trades.extend(trades)
            (train_trades if day in train_days else oos_trades).extend(trades)

        n_all = len(all_trades)
        if n_all == 0:
            print("  No trades.\n"); continue

        w_all = sum(1 for t in all_trades if t["r"] == "W")
        wr_all = w_all / n_all * 100
        tot_all = sum(t["pnl"] for t in all_trades)
        avg_w = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w_all if w_all else 0
        l_count = n_all - w_all
        avg_l = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / l_count if l_count else 0

        buys = [t for t in all_trades if t["side"] == "BUY"]
        sells = [t for t in all_trades if t["side"] == "SELL"]
        buy_pnl = sum(t["pnl"] for t in buys)
        sell_pnl = sum(t["pnl"] for t in sells)
        buy_wr = sum(1 for t in buys if t["r"] == "W") / len(buys) * 100 if buys else 0
        sell_wr = sum(1 for t in sells if t["r"] == "W") / len(sells) * 100 if sells else 0

        tot_train = sum(t["pnl"] for t in train_trades)
        n_oos = len(oos_trades)
        w_oos = sum(1 for t in oos_trades if t["r"] == "W")
        tot_oos = sum(t["pnl"] for t in oos_trades)
        wr_oos = w_oos / n_oos * 100 if n_oos else 0

        # Drawdown
        equity = 0; peak = 0; max_dd = 0; worst_day = min(daily_pnl.values())
        for t in sorted(all_trades, key=lambda x: x["fire"]):
            equity += t["pnl"]
            if equity > peak: peak = equity
            dd = peak - equity
            if dd > max_dd: max_dd = dd

        green_d = sum(1 for p in daily_pnl.values() if p > 0)
        red_d = sum(1 for p in daily_pnl.values() if p <= 0)
        wf_pass = "YES ✅" if tot_train > 0 and tot_oos > 0 else "NO ❌"

        print(f"  {'─'*74}")
        print(f"  TOTAL:  n={n_all:>4}  WR={wr_all:>5.1f}%  AvgW=${avg_w:>+7.1f}  AvgL=${avg_l:>+7.1f}")
        print(f"          P&L=${tot_all:>+9.1f}  EV/trade=${tot_all/n_all:>+7.2f}  $/day=${tot_all/nd:>+7.1f}")
        print(f"  MaxDD:  ${max_dd:>.1f}  |  Worst day: ${worst_day:>.1f}  |  Green/Red: {green_d}/{red_d}")
        print(f"")
        print(f"  BUY:    n={len(buys):>4}  WR={buy_wr:>5.1f}%  P&L=${buy_pnl:>+9.1f}  EV=${buy_pnl/len(buys) if buys else 0:>+7.2f}")
        print(f"  SELL:   n={len(sells):>4}  WR={sell_wr:>5.1f}%  P&L=${sell_pnl:>+9.1f}  EV=${sell_pnl/len(sells) if sells else 0:>+7.02f}")
        print(f"")
        print(f"  TRAIN ({train_days[0]}→{train_days[-1]}): n={len(train_trades)}  P&L=${tot_train:>+9.1f}")
        print(f"  OOS   ({oos_days[0]}→{oos_days[-1]}): n={n_oos}  WR={wr_oos:>5.1f}%  P&L=${tot_oos:>+9.1f}")
        print(f"  WALK-FORWARD: {wf_pass}")
        print()

    # ── COMPARISON WITH S1 ──
    print("=" * 78)
    print("  COMPARISON: S4 vs S1 v2.30 (both @ 0.01 lots)")
    print("=" * 78)
    print("""
  S1 v2.30 results from earlier backtest:
    n=197  WR=70.6%  P&L=+$451  $/day=+$25  MaxDD=$56  Green: 15/18  WF: YES ✅
  
  Use the S4 results above to compare:
    - Does S4 make more money per day?
    - Is it walk-forward robust?
    - Is the drawdown manageable for a $126 account?
    - Are both BUY and SELL positive?
""")


if __name__ == "__main__":
    main()
