"""backtest_s2_engulfing.py — backtest teacher's Setup 2 (Engulfing reversal)
on 12 days of real XAU tick data (Apr 29 - May 14 2026).

Teacher's S2 spec:
  BUY:
    - Bullish engulfing of prev RED candle in a retracement
    - bo.high > prev.high  AND  bo.low < prev.low
    - bo.vol  <  red.vol   (VSA "exhaustion of supply" — LOWER vol engulf)
    - H1 FVG tap during retracement
    - Uptrend
    - Entry: bo.close   SL: bo.low - PIP   TP: highest-vol red's high
  SELL: symmetric (engulfs prev GREEN, downtrend, etc.)

Test variants:
  v1: BUY+SELL with H1 FVG required (strict teacher spec)
  v2: BUY+SELL with H1 FVG OPTIONAL (relaxed — same trick that opened S3)
  v3: BUY only, no FVG
  v4: SELL only, no FVG

Uses tick replay (real bid/ask) for fills — same methodology as S3 mirror.
"""
import csv
import sys
import glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats)
# Use the bidirectional FVG detector from backtest_setups.py (it tags side='bullish'/'bearish')
from backtest_setups import find_h1_fvgs

CONTRACT = 100.0
PIP = 0.10
TREND_LB = 24       # M5 bars (=2h)
TREND_TH = 1.0      # price points (matches S3 default)


def is_uptrend_m5(m5, idx, lb=TREND_LB, th=TREND_TH):
    if idx < lb: return False
    return (m5[idx]["close"] - m5[idx-lb]["close"]) > th


def is_downtrend_m5(m5, idx, lb=TREND_LB, th=TREND_TH):
    if idx < lb: return False
    return (m5[idx-lb]["close"] - m5[idx]["close"]) > th


def find_retracement_reds(m5, idx, max_lb=30):
    """For a BUY: reds that broke the last green's low — same shape as S3."""
    for back_g in range(2, max_lb + 1):
        if idx - back_g < 0: break
        g = m5[idx - back_g]
        if g["close"] <= g["open"]: continue
        g_l = g["low"]
        reds = []
        any_broke = False
        for j in range(idx - back_g + 1, idx):
            r = m5[j]
            if r["close"] < r["open"]:
                if r["close"] < g_l or r["low"] < g_l: any_broke = True
                reds.append(j)
        if any_broke and reds: return reds
    return []


def find_retracement_greens(m5, idx, max_lb=30):
    """For a SELL: greens that broke last red's high."""
    for back_r in range(2, max_lb + 1):
        if idx - back_r < 0: break
        r = m5[idx - back_r]
        if r["close"] >= r["open"]: continue
        r_h = r["high"]
        greens = []
        any_broke = False
        for j in range(idx - back_r + 1, idx):
            g = m5[j]
            if g["close"] > g["open"]:
                if g["close"] > r_h or g["high"] > r_h: any_broke = True
                greens.append(j)
        if any_broke and greens: return greens
    return []


def h1_bull_fvg_tapped(h1_fvgs_bull, m5_bar):
    """Any unfilled bullish FVG that the m5 bar's range touched?"""
    for f in h1_fvgs_bull:
        if f["t0"] >= m5_bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= m5_bar["time"]: continue
        if m5_bar["low"] <= f["gap_high"] and m5_bar["high"] >= f["gap_low"]:
            return True
    return False


def h1_bear_fvg_tapped(h1_fvgs_bear, m5_bar):
    for f in h1_fvgs_bear:
        if f["t0"] >= m5_bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= m5_bar["time"]: continue
        if m5_bar["low"] <= f["gap_high"] and m5_bar["high"] >= f["gap_low"]:
            return True
    return False


def detect_s2_buy(m5, idx, h1_bull, require_fvg=True):
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if idx < 1: return None
    red = m5[idx - 1]
    if red["close"] >= red["open"]: return None
    # Engulfing
    if not (bo["high"] > red["high"] and bo["low"] < red["low"]): return None
    # Lower vol engulf (VSA)
    if bo["vol"] >= red["vol"]: return None
    # Uptrend
    if not is_uptrend_m5(m5, idx): return None
    # Retracement structure
    reds = find_retracement_reds(m5, idx)
    if not reds: return None
    # H1 FVG (optional)
    if require_fvg:
        if not any(h1_bull_fvg_tapped(h1_bull, m5[j]) for j in reds): return None
    # TP = highest-vol red's high
    uhv_idx = max(reds, key=lambda j: m5[j]["vol"])
    tp = m5[uhv_idx]["high"]
    entry = bo["close"]
    sl    = bo["low"] - PIP
    if tp <= entry: return None
    return {"fire_time": bo["time"] + timedelta(minutes=5),
            "side": +1, "sl": sl, "tp": tp,
            "ref_red_t": red["time"]}


def detect_s2_sell(m5, idx, h1_bear, require_fvg=True):
    bo = m5[idx]
    if bo["close"] >= bo["open"]: return None
    if idx < 1: return None
    green = m5[idx - 1]
    if green["close"] <= green["open"]: return None
    if not (bo["high"] > green["high"] and bo["low"] < green["low"]): return None
    if bo["vol"] >= green["vol"]: return None
    if not is_downtrend_m5(m5, idx): return None
    greens = find_retracement_greens(m5, idx)
    if not greens: return None
    if require_fvg:
        if not any(h1_bear_fvg_tapped(h1_bear, m5[j]) for j in greens): return None
    uhv_idx = max(greens, key=lambda j: m5[j]["vol"])
    tp = m5[uhv_idx]["low"]
    entry = bo["close"]
    sl    = bo["high"] + PIP
    if tp >= entry: return None
    return {"fire_time": bo["time"] + timedelta(minutes=5),
            "side": -1, "sl": sl, "tp": tp,
            "ref_red_t": green["time"]}


def s2_mirror(m5, h1_bull, h1_bear, require_fvg, do_buy=True, do_sell=True):
    sigs = []
    fired_refs = set()
    for idx in range(30, len(m5)):
        if do_buy:
            s = detect_s2_buy(m5, idx, h1_bull, require_fvg)
            if s and s["ref_red_t"] not in fired_refs:
                sigs.append(s); fired_refs.add(s["ref_red_t"])
        if do_sell:
            s = detect_s2_sell(m5, idx, h1_bear, require_fvg)
            if s and s["ref_red_t"] not in fired_refs:
                sigs.append(s); fired_refs.add(s["ref_red_t"])
    return sigs


def replay_ticks_both_sides(ticks, sigs, lots, contract):
    """Tick replay supporting BOTH buy (+1) and sell (-1) sides."""
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            exit_pnl = exit_why = None
            if u["side"] == +1:   # BUY: exit on bid
                if bid <= u["sl"]:   exit_pnl, exit_why = (u["sl"]-u["e"])*ppp, "sl"
                elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"]-u["e"])*ppp, "tp"
            else:                  # SELL: exit on ask, flipped P&L
                if ask >= u["sl"]:   exit_pnl, exit_why = (u["e"]-u["sl"])*ppp, "sl"
                elif ask <= u["tp"]: exit_pnl, exit_why = (u["e"]-u["tp"])*ppp, "tp"
            if exit_pnl is not None:
                u["pnl"], u["why"] = exit_pnl, exit_why
                done.append(u); units.remove(u)
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2:
                # BUY enters at ask; SELL enters at bid
                e = ask if pending["side"] == +1 else bid
                units.append({"side": pending["side"], "e": e,
                              "sl": pending["sl"], "tp": pending["tp"],
                              "fire_time": pending["fire_time"]})
            pending = next(sig_iter, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            if u["side"] == +1:
                u["pnl"] = (last["bid"] - u["e"]) * ppp
            else:
                u["pnl"] = (u["e"] - last["ask"]) * ppp
            u["why"] = "eod"
            done.append(u)
    return done


def report_variant(label, sigs, trades_by_side):
    print(f"\n  {'='*72}")
    print(f"  VARIANT: {label}")
    print(f"  {'='*72}")
    all_trades = trades_by_side["buy"] + trades_by_side["sell"]
    n_sigs = len(sigs)
    rb = stats(trades_by_side["buy"])
    rs = stats(trades_by_side["sell"])
    ra = stats(all_trades)
    print(f"  raw sigs: {n_sigs}  |  trades closed: {len(all_trades)} "
          f"({len(trades_by_side['buy'])} buy + {len(trades_by_side['sell'])} sell)")
    if rb:
        print(f"  BUY  : n={rb['n']:>3} pw={rb['pwin']:.2f} "
              f"W=${rb['w_avg']:>5.1f} L=${rb['l_avg']:>5.1f} "
              f"TOT=${rb['total']:>+7.1f}")
    if rs:
        print(f"  SELL : n={rs['n']:>3} pw={rs['pwin']:.2f} "
              f"W=${rs['w_avg']:>5.1f} L=${rs['l_avg']:>5.1f} "
              f"TOT=${rs['total']:>+7.1f}")
    if ra:
        pos = "✅" if ra["total"] > 0 else "❌"
        print(f"  ALL  : n={ra['n']:>3} pw={ra['pwin']:.2f} "
              f"W=${ra['w_avg']:>5.1f} L=${ra['l_avg']:>5.1f} "
              f"TOT=${ra['total']:>+7.1f}  {pos}")
        ev = ra["pwin"]*ra["w_avg"] - (1-ra["pwin"])*ra["l_avg"]
        print(f"  EV per trade: ${ev:+.2f}   (0.10 lot units; div by 5 for 0.02)")
    return ra


def main():
    print("Loading 12d M1 + ticks...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"  {len(bars_all)} M1 bars, {len(h1)} H1 bars, "
          f"{len(h1_bull)} bull FVGs, {len(h1_bear)} bear FVGs, {len(tick_files)} tick days\n")

    # Per-day cache: m5 + ticks
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        m5 = aggregate_to_tf(db, 5)
        cache[day] = {"m5": m5, "ticks": ticks}
    print(f"  {len(cache)} days cached")

    variants = [
        ("v1: BUY+SELL, H1 FVG REQUIRED (strict teacher)",  True,  True,  True),
        ("v2: BUY+SELL, H1 FVG OPTIONAL",                   False, True,  True),
        ("v3: BUY only, H1 FVG OPTIONAL",                   False, True,  False),
        ("v4: SELL only, H1 FVG OPTIONAL",                  False, False, True),
    ]

    summary = []
    for label, require_fvg, do_buy, do_sell in variants:
        all_sigs = []
        trades_by_side = {"buy": [], "sell": []}
        for day, c in cache.items():
            sigs = s2_mirror(c["m5"], h1_bull, h1_bear, require_fvg,
                             do_buy=do_buy, do_sell=do_sell)
            if not sigs: continue
            all_sigs.extend(sigs)
            done = replay_ticks_both_sides(c["ticks"], sigs, 0.10, CONTRACT)
            for t in done:
                key = "buy" if t["side"] == +1 else "sell"
                trades_by_side[key].append(t)
        r = report_variant(label, all_sigs, trades_by_side)
        summary.append((label, r))

    print(f"\n\n  {'='*72}")
    print(f"  RECOMMENDATION SUMMARY  (0.10 lot baseline, divide by 5 for 0.02)")
    print(f"  {'='*72}")
    for label, r in summary:
        if r is None:
            print(f"  {label}\n    no trades")
            continue
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        print(f"  {label}")
        print(f"    n={r['n']:>3}  WR={r['pwin']*100:>4.1f}%  EV/tr=${ev:+.2f}  "
              f"TOTAL=${r['total']:+.1f} / 12d  →  ${r['total']/12:+.1f}/day")


if __name__ == "__main__":
    main()
