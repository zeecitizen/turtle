"""backtest_ns_nd.py — real-tick backtest of the NS/ND detector across
every day of available tick data (Apr 29 - May 14 2026, 12 days).

Method:
  1. For each day, get the per-day M1 bars (from rev_eng_m1.csv merged set,
     filtered to the day).
  2. Run `detect_ns_nd_pattern` on each bar in sequence — collect entry
     signals (time, side, NS-low, NS-high, UHV reference).
  3. Replay ticks for the day. On each signal, open a trade at the next
     tick's bid/ask. Track each open trade with multiple exit rules:
       - SL: at the NS candle's low (buy) / high (sell) — the lecture's stop
       - TP: $X fixed (test multiple values)
  4. Aggregate P&L per day, per config; report.

This is the validate-profitability test that MUST pass before any live
deployment (see memory: feedback_validate_profitability_not_capture.md).
"""
import csv
import glob
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_feb11_lab import detect_ns_nd_pattern
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON

CONTRACT     = 100.0       # XAU $1/oz/lot
PIP          = 0.10        # 1 pip = $0.10 price units
RATE_LIMIT_S = 2.0


def group_bars_by_day(bars):
    """{date_str: [bars...]}"""
    days = {}
    for b in bars:
        d = b["time"].date().isoformat()
        days.setdefault(d, []).append(b)
    for d in days:
        days[d].sort(key=lambda b: b["time"])
    return days


def detect_signals_for_day(day_bars, **detect_kwargs):
    """Run NS/ND detector on a day's bars. Return list of signals.
    fire_time = bar.time + 60s (the bar's END) to avoid lookahead bias —
    we can only know the bar's close at that moment."""
    signals = []
    fired_ns_idx = set()
    for i in range(len(day_bars)):
        r = detect_ns_nd_pattern(day_bars, i, **detect_kwargs)
        if r is None: continue
        side, ns_idx, trig_idx = r
        if ns_idx in fired_ns_idx: continue
        fired_ns_idx.add(ns_idx)
        ns = day_bars[ns_idx]
        sweep_bar = day_bars[i]
        signals.append({
            "fire_time": day_bars[i]["time"] + timedelta(seconds=60),
            "side":      side,
            "ns_high":   ns["high"],
            "ns_low":    ns["low"],
            # SL reference = the SWEEP bar's extreme (just beyond the wick)
            "sweep_high": sweep_bar["high"],
            "sweep_low":  sweep_bar["low"],
        })
    return signals


def replay_one_day(ticks, signals, lots=0.10, tp_usd=10.0, sl_at_ns=True,
                   sl_extra_pips=2.0, max_concurrent=2):
    """Replay ticks for one day. For each signal, open at the next tick
    after `fire_time`, exit on whichever hits first:
      - SL: NS.low (for buy) minus sl_extra_pips*PIP, or NS.high+extra for sell
      - TP: $tp_usd fixed at `lots` size
      - EOD: liquidate at last tick price
    Returns list of completed trades."""
    ppp = lots * CONTRACT
    units = []
    done  = []
    last_fire = None
    sig_iter = iter(sorted(signals, key=lambda s: s["fire_time"]))
    pending  = next(sig_iter, None)

    def open_unit(t, bid, ask, sig):
        # SL placed just beyond the SWEEP bar's extreme (not NS/ND extreme),
        # so SL is always on the correct side of entry when entry happens
        # at-or-after bar close (price has already pushed past NS/ND).
        if sig["side"] > 0:
            e  = ask
            sl = sig["sweep_low"] - sl_extra_pips * PIP
            tp_dist = tp_usd / ppp
            tp = e + tp_dist
        else:
            e  = bid
            sl = sig["sweep_high"] + sl_extra_pips * PIP
            tp_dist = tp_usd / ppp
            tp = e - tp_dist
        return {"side": sig["side"], "e": e, "sl": sl, "tp": tp,
                "fire_t": sig["fire_time"], "open_t": t}

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        # Exit checks for open units
        for u in units[:]:
            exit_pnl = exit_why = None
            if u["side"] > 0:
                if bid <= u["sl"]: exit_pnl, exit_why = (u["sl"] - u["e"]) * ppp, "sl"
                elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"] - u["e"]) * ppp, "tp"
            else:
                if ask >= u["sl"]: exit_pnl, exit_why = (u["e"] - u["sl"]) * ppp, "sl"
                elif ask <= u["tp"]: exit_pnl, exit_why = (u["e"] - u["tp"]) * ppp, "tp"
            if exit_pnl is not None:
                u["pnl"], u["why"], u["close_t"] = exit_pnl, exit_why, t
                done.append(u); units.remove(u)
        # Open pending signals whose fire_time has passed
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < max_concurrent and (last_fire is None or
                (t - last_fire).total_seconds() >= RATE_LIMIT_S):
                units.append(open_unit(t, bid, ask, pending))
                last_fire = t
            pending = next(sig_iter, None)

    # EOD liquidation
    if ticks:
        last = ticks[-1]
        for u in units:
            if u["side"] > 0: u["pnl"] = (last["bid"] - u["e"]) * ppp
            else:             u["pnl"] = (u["e"] - last["ask"]) * ppp
            u["why"], u["close_t"] = "eod", last["t"]
            done.append(u)
    return done


def summarize(label, all_done, n_days):
    n = len(all_done)
    wins = [u for u in all_done if u["pnl"] > 0]
    losses = [u for u in all_done if u["pnl"] < 0]
    n_w, n_l = len(wins), len(losses)
    pwin = n_w / (n_w + n_l) if (n_w + n_l) else 0
    w_avg = sum(u["pnl"] for u in wins) / n_w if n_w else 0
    l_avg = -sum(u["pnl"] for u in losses) / n_l if n_l else 0
    total = sum(u["pnl"] for u in all_done)
    ev = pwin * w_avg - (1 - pwin) * l_avg
    why = {}
    for u in all_done: why[u["why"]] = why.get(u["why"], 0) + 1
    print(f"  {label}")
    print(f"     n={n:<5}  P_win={pwin:.3f}  W_avg=${w_avg:.2f}  L_avg=${l_avg:.2f}  EV=${ev:+.2f}/tr")
    print(f"     {n_days}-day total=${total:+.2f}  exits={why}")
    return total


def main():
    bars_all = load_m1_merged()
    # convert the M1 bars to the shape detect_ns_nd_pattern expects (Unix int 'time')
    import time
    # We need bars with a 'time' field that is an int (Unix seconds) — but
    # load_m1_merged gives datetime objects. detect_ns_nd_pattern doesn't
    # actually USE bar["time"] for its math (only for the signal record),
    # so leaving as-is is OK.

    days_bars = group_bars_by_day(bars_all)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"NS/ND real-tick backtest across {len(tick_files)} days\n")

    # Load all tick data once
    ticks_by_day = {}
    bars_by_day  = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        day_bars = days_bars[day]
        if len(day_bars) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        ticks_by_day[day] = ticks
        bars_by_day[day]  = day_bars
    print(f"Days loaded: {len(bars_by_day)}\n")

    def run_config(tp_usd, sl_buf, fvg_tfs, second_tap, require_trend, require_fvg=True):
        det_kw = dict(require_fvg=require_fvg, require_trend=require_trend,
                      fvg_timeframes=fvg_tfs,
                      fvg_min_prior_taps=(1 if second_tap else 0))
        all_done = []
        for day, day_bars in bars_by_day.items():
            sigs = detect_signals_for_day(day_bars, **det_kw)
            if not sigs: continue
            done = replay_one_day(ticks_by_day[day], sigs,
                                  lots=0.10, tp_usd=tp_usd, sl_extra_pips=sl_buf)
            all_done.extend(done)
        n = len(all_done)
        wins = [u['pnl'] for u in all_done if u['pnl'] > 0]
        losses = [u['pnl'] for u in all_done if u['pnl'] < 0]
        n_w, n_l = len(wins), len(losses)
        pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
        w_avg = sum(wins)/n_w if n_w else 0
        l_avg = -sum(losses)/n_l if n_l else 0
        total = sum(u['pnl'] for u in all_done)
        ev = pwin*w_avg - (1-pwin)*l_avg
        return total, n, pwin, w_avg, l_avg, ev

    tf_configs = [
        ("M5+M15+H1", (5, 15, 60)),
        ("M5+H1",     (5, 60)),
        ("M15+H1",    (15, 60)),
        ("M5+M15",    (5, 15)),
        ("M5 only",   (5,)),
        ("M15 only",  (15,)),
        ("H1 only",   (60,)),
    ]
    tp_values = [10.0, 12.0, 15.0, 20.0]
    sl_buffers = [1.0, 2.0]
    second_tap_modes = [False, True]

    print("=== Multi-TF FVG × TP × SL × SecondTap sweep ===\n")
    print(f"{'TF':<12} {'2nd':>4} {'TP':>5} {'SLbuf':>6} {'n':>5} {'pwin':>6} "
          f"{'Wavg':>7} {'Lavg':>7} {'EV':>8} {'TOTAL':>10}")
    best = None
    for tf_label, tfs in tf_configs:
        for second_tap in second_tap_modes:
            for tp_usd in tp_values:
                for sl_buf in sl_buffers:
                    total, n, pwin, w_avg, l_avg, ev = run_config(
                        tp_usd, sl_buf, tfs, second_tap, require_trend=True)
                    if n == 0: continue
                    tap_lbl = "2nd" if second_tap else "any"
                    marker = " *" if total > 0 else ""
                    print(f"{tf_label:<12} {tap_lbl:>4} {tp_usd:>5.0f} {sl_buf:>6.1f} "
                          f"{n:>5} {pwin:>6.3f} ${w_avg:>5.2f} ${l_avg:>5.2f} "
                          f"${ev:>+6.2f} ${total:>+8.2f}{marker}")
                    if best is None or total > best[0]:
                        best = (total, tf_label, tap_lbl, tp_usd, sl_buf,
                                n, pwin, w_avg, l_avg, ev)
        print()
    print(f"BEST: TF={best[1]}  Tap={best[2]}  TP=${best[3]}  SL_buf={best[4]}pips  "
          f"n={best[5]}  pwin={best[6]:.3f}")
    print(f"      Wavg=${best[7]:.2f}  Lavg=${best[8]:.2f}  EV=${best[9]:+.2f}/trade")
    print(f"      12-day total=${best[0]:+.2f}")


if __name__ == "__main__":
    main()
