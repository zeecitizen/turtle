"""backtest_s1_bigspread.py — does relaxing S1's big-spread filter cost P&L?

S1 fires ~1.5/day with the big-spread climax filter ON; ~3/day with it OFF.
The user wants more S1 trades. Big-spread is an INPUT (InpRequireBigSpread), so
flipping it is a no-recompile change — IF the extra trades aren't net-negative.

This replays S1's FAITHFUL live cascade (BUY+SELL, exact filters) on real ticks
with the deployed exit (SL = uhv extreme ∓ $2, TP = ±$7.5pts, 0.06 lots), comparing
big-spread ON vs OFF, all-days + walk-forward. Decision rule: relax only if OFF
total >= ON total AND OFF holds out-of-sample.

Run:  py backtest_s1_bigspread.py
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import h1_bull_tapped_in, h1_bear_tapped_in

CONTRACT = 100.0
LOTS = 0.06
TREND_LB, TREND_TH = 24, 2.0
RETRACE_LB = 15
SPREAD_MULT, SPREAD_AVG = 1.3, 10
SL_BUF, TP_PTS = 2.0, 7.5


def _big_spread_ok(m5, uhv, on):
    if not on:
        return True
    rng = m5[uhv]["high"] - m5[uhv]["low"]
    avg = sum(m5[j]["high"] - m5[j]["low"] for j in range(uhv - SPREAD_AVG, uhv)) / SPREAD_AVG
    return avg > 0 and rng >= SPREAD_MULT * avg


def _s1_buy(m5, i, h1_bull, on):
    bo = m5[i]
    if bo["close"] <= bo["open"]: return None
    if bo["close"] - m5[i - TREND_LB]["close"] <= TREND_TH: return None
    reds = [j for j in range(i - RETRACE_LB, i) if j >= SPREAD_AVG and m5[j]["close"] < m5[j]["open"]]
    if not reds: return None
    uhv = max(reds, key=lambda j: m5[j]["vol"])
    if not _big_spread_ok(m5, uhv, on): return None
    uhv_h, uhv_l = m5[uhv]["high"], m5[uhv]["low"]
    if not (bo["close"] > uhv_h and bo["open"] <= uhv_h): return None
    if not any(m5[k]["low"] < uhv_l for k in range(uhv + 1, i + 1)): return None
    if not h1_bull_tapped_in(h1_bull, m5, list(range(min(reds), i + 1))): return None
    return {"side": +1, "fire_time": bo["time"] + timedelta(minutes=5), "sl_abs": uhv_l - SL_BUF}


def _s1_sell(m5, i, h1_bear, on):
    bo = m5[i]
    if bo["close"] >= bo["open"]: return None
    if bo["close"] - m5[i - TREND_LB]["close"] >= -TREND_TH: return None
    greens = [j for j in range(i - RETRACE_LB, i) if j >= SPREAD_AVG and m5[j]["close"] > m5[j]["open"]]
    if not greens: return None
    uhv = max(greens, key=lambda j: m5[j]["vol"])
    if not _big_spread_ok(m5, uhv, on): return None
    uhv_h, uhv_l = m5[uhv]["high"], m5[uhv]["low"]
    if not (bo["close"] < uhv_l and bo["open"] >= uhv_l): return None
    if not any(m5[k]["high"] > uhv_h for k in range(uhv + 1, i + 1)): return None
    if not h1_bear_tapped_in(h1_bear, m5, list(range(min(greens), i + 1))): return None
    return {"side": -1, "fire_time": bo["time"] + timedelta(minutes=5), "sl_abs": uhv_h + SL_BUF}


def signals_day(m5, h1_bull, h1_bear, on):
    out = []
    start = max(TREND_LB, RETRACE_LB + SPREAD_AVG) + 2
    for i in range(start, len(m5)):
        s = _s1_buy(m5, i, h1_bull, on)   # BUY first (live dedup blocks SELL same bar)
        if s is None:
            s = _s1_sell(m5, i, h1_bear, on)
        if s:
            out.append(s)
    return out


def replay(ticks, sigs):
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] > 0:
                if bid <= u["sl"]: u["pnl"] = (u["sl"] - u["e"]) * ppp; done.append(u); units.remove(u)
                elif bid >= u["tp"]: u["pnl"] = (u["tp"] - u["e"]) * ppp; done.append(u); units.remove(u)
            else:
                if ask >= u["sl"]: u["pnl"] = (u["e"] - u["sl"]) * ppp; done.append(u); units.remove(u)
                elif ask <= u["tp"]: u["pnl"] = (u["e"] - u["tp"]) * ppp; done.append(u); units.remove(u)
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < 2:
                e = ask if pend["side"] > 0 else bid
                tp = e + TP_PTS if pend["side"] > 0 else e - TP_PTS
                units.append({"side": pend["side"], "e": e, "sl": pend["sl_abs"], "tp": tp})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = (last["bid"] - u["e"]) * ppp if u["side"] > 0 else (u["e"] - last["ask"]) * ppp
            done.append(u)
    return done


def stat(trades):
    n = len(trades)
    if not n: return "n=0"
    w = [t["pnl"] for t in trades if t["pnl"] > 0]
    l = [t["pnl"] for t in trades if t["pnl"] < 0]
    tot = sum(t["pnl"] for t in trades)
    wr = len(w) / (len(w) + len(l)) if (w or l) else 0
    return f"n={n:>3}  WR={wr:.2f}  TOTAL=${tot:>+8.1f}  ({n/13:.1f}/day)"


def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in fvgs if f.get("side") == "bullish"]
    h1_bear = [f for f in fvgs if f.get("side") == "bearish"]
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 60: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[d] = {"m5": aggregate_to_tf(days_b[d], 5), "ticks": ticks}
    days = sorted(cache)
    mid = len(days) // 2
    print(f"S1 big-spread P&L test — {len(days)} real-tick days @ {LOTS} lots, BUY+SELL\n")
    for on in (True, False):
        lbl = "big-spread ON (live)" if on else "big-spread OFF"
        allt, traint, testt = [], [], []
        for k, d in enumerate(days):
            sg = signals_day(cache[d]["m5"], h1_bull, h1_bear, on)
            tr = replay(cache[d]["ticks"], sg)
            allt += tr
            (traint if k < mid else testt).extend(tr)
        print(f"  {lbl:<22}")
        print(f"    ALL   {stat(allt)}")
        print(f"    TRAIN {stat(traint)}")
        print(f"    TEST  {stat(testt)}\n")


if __name__ == "__main__":
    main()
