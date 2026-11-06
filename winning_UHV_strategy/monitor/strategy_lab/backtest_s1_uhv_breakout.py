"""backtest_s1_uhv_breakout.py — re-validate Setup 1 (UHV Breakout) on 12d
of real XAU ticks (Apr 29 - May 14 2026), matching S1Trader.mq5 logic.

S1 spec (from S1Trader.mq5):
  BUY:
    1. H1 unfilled bullish FVG must exist
    2. M5 retracement must TAP the FVG
    3. In retracement, find UHV red (highest-vol red candle)
    4. Some bar after UHV red sweeps below UHV.low
    5. Green M5 bar: opens <= UHV.high AND closes > UHV.high (fresh transition)
    6. Uptrend pre-req: close[now] - close[24 bars] > 2.0
    7. Entry = bo.close; SL = UHV.low - sl_buf; TP = entry + tp_points (fixed)

S1Trader.mq5 defaults: tp_points=5.0, sl_buf=0.10, trend_lb=24, trend_th=2.0
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs

CONTRACT = 100.0
PIP = 0.10


def is_uptrend(m5, idx, lb=24, th=2.0):
    if idx < lb: return False
    return (m5[idx]["close"] - m5[idx-lb]["close"]) > th


def is_downtrend(m5, idx, lb=24, th=2.0):
    if idx < lb: return False
    return (m5[idx-lb]["close"] - m5[idx]["close"]) > th


def h1_bull_tapped_in(h1_bull, m5, retrace_bar_indices):
    """Any unfilled bullish FVG tapped by any bar in the retracement range."""
    for j in retrace_bar_indices:
        m = m5[j]
        for f in h1_bull:
            if f["t0"] >= m["time"]: continue
            if f["filled_at"] is not None and f["filled_at"] <= m["time"]: continue
            if m["low"] <= f["gap_high"] and m["high"] >= f["gap_low"]:
                return True
    return False


def h1_bear_tapped_in(h1_bear, m5, retrace_bar_indices):
    for j in retrace_bar_indices:
        m = m5[j]
        for f in h1_bear:
            if f["t0"] >= m["time"]: continue
            if f["filled_at"] is not None and f["filled_at"] <= m["time"]: continue
            if m["low"] <= f["gap_high"] and m["high"] >= f["gap_low"]:
                return True
    return False


def detect_s1_buy(m5, idx, h1_bull, sl_buf, tp_points,
                  retrace_lb=15, require_open_below=True,
                  require_sweep=True, require_fvg=True):
    """At m5[idx] (potential green breakout)."""
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None         # need green
    if not is_uptrend(m5, idx): return None

    # Retracement = last `retrace_lb` reds before idx
    start = max(0, idx - retrace_lb)
    red_idxs = [j for j in range(start, idx) if m5[j]["close"] < m5[j]["open"]]
    if not red_idxs: return None
    uhv_idx = max(red_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]

    # Breakout vs UHV
    if bo["close"] <= uhv["high"]: return None
    if require_open_below and bo["open"] > uhv["high"]: return None

    # Sweep: some bar in (uhv_idx, idx] dipped below uhv.low
    if require_sweep:
        if not any(m5[j]["low"] < uhv["low"] for j in range(uhv_idx+1, idx+1)):
            return None

    # H1 bullish FVG tap during retracement (between uhv_idx and idx)
    if require_fvg:
        if not h1_bull_tapped_in(h1_bull, m5, range(start, idx+1)):
            return None

    entry = bo["close"]
    sl    = uhv["low"] - sl_buf
    tp    = entry + tp_points
    if tp <= entry: return None
    return {"fire_time": bo["time"] + timedelta(minutes=5),
            "side": +1, "sl": sl, "tp": tp,
            "ref_uhv_t": uhv["time"]}


def detect_s1_sell(m5, idx, h1_bear, sl_buf, tp_points,
                   retrace_lb=15, require_open_above=True,
                   require_sweep=True, require_fvg=True):
    bo = m5[idx]
    if bo["close"] >= bo["open"]: return None         # need red
    if not is_downtrend(m5, idx): return None
    start = max(0, idx - retrace_lb)
    green_idxs = [j for j in range(start, idx) if m5[j]["close"] > m5[j]["open"]]
    if not green_idxs: return None
    uhv_idx = max(green_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] >= uhv["low"]: return None
    if require_open_above and bo["open"] < uhv["low"]: return None
    if require_sweep:
        if not any(m5[j]["high"] > uhv["high"] for j in range(uhv_idx+1, idx+1)):
            return None
    if require_fvg:
        if not h1_bear_tapped_in(h1_bear, m5, range(start, idx+1)):
            return None
    entry = bo["close"]
    sl    = uhv["high"] + sl_buf
    tp    = entry - tp_points
    if tp >= entry: return None
    return {"fire_time": bo["time"] + timedelta(minutes=5),
            "side": -1, "sl": sl, "tp": tp,
            "ref_uhv_t": uhv["time"]}


def s1_mirror(m5, h1_bull, h1_bear, sl_buf, tp_points,
              do_buy=True, do_sell=False, require_fvg=True, require_sweep=True,
              require_open_inside=True):
    sigs = []
    fired_uhv = set()
    for idx in range(30, len(m5)):
        if do_buy:
            s = detect_s1_buy(m5, idx, h1_bull, sl_buf, tp_points,
                              require_fvg=require_fvg,
                              require_sweep=require_sweep,
                              require_open_below=require_open_inside)
            if s and s["ref_uhv_t"] not in fired_uhv:
                sigs.append(s); fired_uhv.add(s["ref_uhv_t"])
        if do_sell:
            s = detect_s1_sell(m5, idx, h1_bear, sl_buf, tp_points,
                               require_fvg=require_fvg,
                               require_sweep=require_sweep,
                               require_open_above=require_open_inside)
            if s and s["ref_uhv_t"] not in fired_uhv:
                sigs.append(s); fired_uhv.add(s["ref_uhv_t"])
    return sigs


def replay_ticks_both(ticks, sigs, lots, contract):
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            exit_pnl = exit_why = None
            if u["side"] == +1:
                if bid <= u["sl"]:   exit_pnl, exit_why = (u["sl"]-u["e"])*ppp, "sl"
                elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"]-u["e"])*ppp, "tp"
            else:
                if ask >= u["sl"]:   exit_pnl, exit_why = (u["e"]-u["sl"])*ppp, "sl"
                elif ask <= u["tp"]: exit_pnl, exit_why = (u["e"]-u["tp"])*ppp, "tp"
            if exit_pnl is not None:
                u["pnl"], u["why"] = exit_pnl, exit_why
                done.append(u); units.remove(u)
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2:
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


def report(label, sigs, trades):
    r = stats(trades)
    print(f"  {label:<55}", end=" ")
    if not trades:
        print(f"sigs={len(sigs):>3} no closed trades"); return None
    pos = "✅" if r["total"] > 0 else "❌"
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    print(f"sigs={len(sigs):>3} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"W=${r['w_avg']:>5.1f} L=${r['l_avg']:>5.1f} "
          f"TOT=${r['total']:>+7.1f}  EV=${ev:+5.2f}  {pos}")
    return r


def main():
    print("Loading 12d M1 + ticks...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"  {len(bars_all)} M1 bars, {len(h1)} H1, "
          f"bull={len(h1_bull)} bear={len(h1_bear)}, {len(tick_files)} tick days\n")

    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    print(f"  {len(cache)} days cached\n")

    def run_variant(label, **kw):
        all_sigs = []
        all_trades = []
        for day, c in cache.items():
            sigs = s1_mirror(c["m5"], h1_bull, h1_bear, **kw)
            if not sigs: continue
            all_sigs.extend(sigs)
            done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
            all_trades.extend(done)
        return report(label, all_sigs, all_trades)

    # ──────────────────────────────────────────────────────────────
    print("="*100)
    print("  PART 1 — replicate S1Trader.mq5 defaults (BUY only, FVG req, fixed TP=5.0)")
    print("="*100)
    run_variant("Default (TP=5.0, BUY, FVG req, sweep req, fresh open)",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=True, require_sweep=True, require_open_inside=True)

    print()
    print("="*100)
    print("  PART 2 — TP sweep at 0.10 lots (BUY only, FVG req)")
    print("="*100)
    for tp in [2.0, 3.0, 4.0, 5.0, 6.0, 7.5, 10.0, 15.0]:
        run_variant(f"TP={tp:>5.1f} pts (= ${tp*10:>3.0f} @ 0.10 / ${tp*2:>3.0f} @ 0.02)",
                    sl_buf=0.10, tp_points=tp,
                    do_buy=True, do_sell=False,
                    require_fvg=True, require_sweep=True, require_open_inside=True)

    print()
    print("="*100)
    print("  PART 3 — relax filters individually (TP=5.0, BUY only)")
    print("="*100)
    run_variant("baseline (all filters on)",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=True, require_sweep=True, require_open_inside=True)
    run_variant("no FVG req",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=False, require_sweep=True, require_open_inside=True)
    run_variant("no SWEEP req",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=True, require_sweep=False, require_open_inside=True)
    run_variant("no FRESH OPEN req (open can be > uhv.high)",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=True, require_sweep=True, require_open_inside=False)
    run_variant("no FVG + no SWEEP (most permissive)",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=False,
                require_fvg=False, require_sweep=False, require_open_inside=True)

    print()
    print("="*100)
    print("  PART 4 — add SELL side (TP=5.0)")
    print("="*100)
    run_variant("BUY+SELL, FVG req",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=True,
                require_fvg=True, require_sweep=True, require_open_inside=True)
    run_variant("BUY+SELL, no FVG",
                sl_buf=0.10, tp_points=5.0,
                do_buy=True, do_sell=True,
                require_fvg=False, require_sweep=True, require_open_inside=True)

    print()
    print("="*100)
    print("  PART 5 — SL buffer sweep (TP=5.0, BUY, FVG req)")
    print("="*100)
    for slb in [0.10, 0.50, 1.00, 2.00, 3.00]:
        run_variant(f"SL_buf=${slb:.2f}",
                    sl_buf=slb, tp_points=5.0,
                    do_buy=True, do_sell=False,
                    require_fvg=True, require_sweep=True, require_open_inside=True)

    print()
    print("="*100)
    print("  PART 6 — COMBO GRID: best SL × best TP × BUY+SELL × FVG req")
    print("="*100)
    print("  (all use FVG req + sweep req + fresh open; varying SL, TP, side)")
    best = None
    for side_cfg in [("BUY only", True, False), ("BUY+SELL", True, True)]:
        for slb in [0.50, 1.00, 2.00]:
            for tp in [3.0, 5.0, 7.5, 10.0]:
                label = f"{side_cfg[0]:<10} SL=${slb:.2f} TP={tp:>4.1f}"
                r = run_variant(label,
                                sl_buf=slb, tp_points=tp,
                                do_buy=side_cfg[1], do_sell=side_cfg[2],
                                require_fvg=True, require_sweep=True,
                                require_open_inside=True)
                if r and (best is None or r["total"] > best[0]):
                    best = (r["total"], label, r)
        print()
    if best:
        print(f"  >>> BEST CONFIG: {best[1]}")
        r = best[2]
        print(f"  >>> n={r['n']}  WR={r['pwin']*100:.1f}%  TOT=${best[0]:+.1f} / 12d @ 0.10 lots")
        print(f"  >>> At 0.02 lots:  ${best[0]/5:+.1f} / 12d  =  ${best[0]/5/12:+.1f}/day")
        print(f"  >>> At 0.10 lots:  ${best[0]:+.1f} / 12d  =  ${best[0]/12:+.1f}/day")


if __name__ == "__main__":
    main()
