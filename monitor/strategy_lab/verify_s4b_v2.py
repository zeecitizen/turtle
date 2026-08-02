"""verify_s4b_v2.py — Verify S4b v2.00 ATR trailing logic matches backtest exactly.

Run: python verify_s4b_v2.py
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
UHV_RANGE_MIN = 1.0
ER_MIN = 0.15
BODY_FRAC = 0.55
ATR_PERIOD = 7
ATR_SL_MULT = 2.0
ATR_TRAIL_MULT = 2.0
ATR_BE_MULT = 1.0

from datetime import timedelta

def trend_dir(bars):
    if len(bars) < TREND_LB: return 0
    seg = bars[-TREND_LB:]
    h = TREND_LB // 2
    recent, older = seg[h:], seg[:h]
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0

def efficiency_ratio(bars):
    seg = bars[-TREND_LB:]
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0

def atr(bars, period=ATR_PERIOD):
    if len(bars) < period + 1: return 0.0
    trs = []
    for i in range(-period, 0):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

def detect(m1):
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < BODY_FRAC: continue
        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        tw = m1[i - TREND_LB:i]
        if efficiency_ratio(tw) < ER_MIN: continue
        td = trend_dir(tw)
        if td == 0: continue
        cur_atr = atr(m1[:i+1])
        if cur_atr <= 0: continue

        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1), "atr": cur_atr})
                continue

        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1), "atr": cur_atr})
    return sigs

def replay(ticks, sigs):
    """Replay with ATR trailing — exact match to EA v2.00 logic."""
    ppp = LOTS * CONTRACT
    done, units = [], []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]

        for u in units[:]:
            s = u["side"]
            entry = u["e"]
            atr_v = u["atr_val"]

            if s > 0:
                cur_profit = bid - entry
            else:
                cur_profit = entry - ask

            # Update peak
            if cur_profit > u["peak"]:
                u["peak"] = cur_profit

            # Breakeven logic
            be_threshold = ATR_BE_MULT * atr_v
            if not u["be_hit"] and cur_profit >= be_threshold:
                u["be_hit"] = True
                if s > 0:
                    u["sl_price"] = max(u["sl_price"], entry)
                else:
                    u["sl_price"] = min(u["sl_price"], entry)

            # Trailing logic
            trail_dist = ATR_TRAIL_MULT * atr_v
            if s > 0:
                peak_price = entry + u["peak"]
                trail_sl = peak_price - trail_dist
                if trail_sl > u["sl_price"]:
                    u["sl_price"] = trail_sl
            else:
                peak_price = entry - u["peak"]
                trail_sl = peak_price + trail_dist
                if trail_sl < u["sl_price"]:
                    u["sl_price"] = trail_sl

            # Check SL hit
            if s > 0 and bid <= u["sl_price"]:
                u["pnl"] = (u["sl_price"] - entry) * ppp
                u["result"] = "W" if u["pnl"] > 0 else "L"
                done.append(u); units.remove(u); continue
            if s < 0 and ask >= u["sl_price"]:
                u["pnl"] = (entry - u["sl_price"]) * ppp
                u["result"] = "W" if u["pnl"] > 0 else "L"
                done.append(u); units.remove(u); continue

        # Fire new signals
        while pend and t >= pend["fire_time"]:
            if len(units) < 3:
                entry = ask if pend["side"] > 0 else bid
                atr_v = pend["atr"]
                sl_dist = ATR_SL_MULT * atr_v
                if pend["side"] > 0:
                    sl_price = entry - sl_dist
                else:
                    sl_price = entry + sl_dist
                units.append({
                    "side": pend["side"], "e": entry, "open_t": t,
                    "atr_val": atr_v, "sl_price": sl_price,
                    "peak": 0, "be_hit": False,
                })
            pend = next(it, None)

    # EOD close
    if ticks:
        last = ticks[-1]
        for u in units:
            p = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            u["pnl"] = p; u["result"] = "W" if p > 0 else "L"
            done.append(u)
    return done

def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 200: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[d] = {"m1": days_b[d], "ticks": ticks}

    days = sorted(cache)
    nd = len(days)
    mid = nd // 2

    print(f"S4b v2.00 VERIFICATION — {nd} days, {LOTS} lots")
    print(f"ATR({ATR_PERIOD}): SL={ATR_SL_MULT}x, Trail={ATR_TRAIL_MULT}x, BE@{ATR_BE_MULT}x")
    print("=" * 80)

    all_trades, train_trades, test_trades = [], [], []
    for k, d in enumerate(days):
        sigs = detect(cache[d]["m1"])
        trades = replay(cache[d]["ticks"], sigs)
        day_pnl = sum(t["pnl"] for t in trades)
        wins = sum(1 for t in trades if t["result"] == "W")
        wr = wins/len(trades) if trades else 0
        losses = [t["pnl"] for t in trades if t["pnl"] <= 0]
        avg_loss = sum(losses)/len(losses) if losses else 0
        wins_pnl = [t["pnl"] for t in trades if t["pnl"] > 0]
        avg_win = sum(wins_pnl)/len(wins_pnl) if wins_pnl else 0
        split = "TRAIN" if k < mid else "OOS"
        print(f"  {d} [{split}]  n={len(trades):>3}  WR={wr:>5.1%}  W=${avg_win:>5.1f}  L=${avg_loss:>+5.1f}  P&L=${day_pnl:>+8.1f}")
        all_trades.extend(trades)
        if k < mid:
            train_trades.extend(trades)
        else:
            test_trades.extend(trades)

    print("=" * 80)
    for lbl, t_list, n_days in [("ALL", all_trades, nd), ("TRAIN", train_trades, mid), ("OOS", test_trades, nd - mid)]:
        n = len(t_list)
        if not n:
            print(f"  {lbl}: n=0")
            continue
        w = sum(1 for t in t_list if t["result"] == "W")
        wr = w / n
        tot = sum(t["pnl"] for t in t_list)
        avg_w = sum(t["pnl"] for t in t_list if t["pnl"] > 0) / w if w else 0
        avg_l = sum(t["pnl"] for t in t_list if t["pnl"] <= 0) / (n - w) if (n - w) else 0
        print(f"  {lbl:>5}: n={n:>4} {n/n_days:>5.1f}/d  WR={wr:>5.1%}  W=${avg_w:>5.1f}  L=${avg_l:>+6.1f}  TOT=${tot:>+9.1f}")

    # Walk-forward check
    train_pnl = sum(t["pnl"] for t in train_trades)
    test_pnl = sum(t["pnl"] for t in test_trades)
    wf = "✅ WALK-FORWARD POSITIVE" if train_pnl > 0 and test_pnl > 0 else "❌ NOT WALK-FORWARD"
    print(f"\n  Train=${train_pnl:>+.0f}, Test=${test_pnl:>+.0f} → {wf}")
    print(f"\n  At 0.02 lots: daily ≈ ${sum(t['pnl'] for t in all_trades)/nd * 0.02/LOTS:.0f}/day")

if __name__ == "__main__":
    main()
