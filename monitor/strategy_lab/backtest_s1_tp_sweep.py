"""backtest_s1_tp_sweep.py — Find a TP placement that rescues S1.

Current S1_buy on M5: 4 trades, 50% WR, Wavg $24, Lavg $97, EV -$36/tr, -$145 total.
The TP "last recent high peak" is only ~2.4pts above entry, but the SL
(at UHV red's low) is ~9.7pts below — R:R 0.25 is fatal.

Sweep configurations:
  • TP_MODE = "fixed_usd"  (TP at entry +/- $X / lots / contract)
  • TP_MODE = "rr_multiple" (TP at entry +/- (entry-SL)*R)
  • TP_MODE = "peak"       (original — last recent high)
  • Plus a SL distance cap (skip signal if SL is too wide)

Also try SL_BUF variations.
"""
import csv, glob, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_setups import (
    aggregate_to_tf, group_bars_by_day, find_h1_fvgs,
    fvg_visible_and_tapped_at, is_uptrend, find_retracement_reds,
    replay_signals,
)
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON

CONTRACT = 100.0
PIP = 0.10


def detect_s1_buy_custom(m5_bars, idx, h1_fvgs, tp_mode, tp_value, sl_buf_pts=0.10,
                         sl_max_pts=None):
    """S1 Ultra-High-Volume Breakout BUY with configurable TP.
    Returns (entry, sl, tp, ref) or None."""
    bo = m5_bars[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5_bars, idx): return None

    reds, _ = find_retracement_reds(m5_bars, idx, max_lookback=15)
    if not reds: return None
    uhv_red_idx = max(reds, key=lambda j: m5_bars[j]["vol"])
    uhv_red = m5_bars[uhv_red_idx]

    if bo["close"] <= uhv_red["high"]: return None
    if bo["open"]  >  uhv_red["high"]: return None

    # Sweep
    swept = any(m5_bars[j]["low"] < uhv_red["low"] for j in range(uhv_red_idx+1, idx+1))
    if not swept: return None

    # H1 FVG tap during retracement
    tapped = False
    for j in reds:
        if fvg_visible_and_tapped_at(h1_fvgs, "bullish", m5_bars[j]) is not None:
            tapped = True; break
    if not tapped: return None

    entry = bo["close"]
    sl = uhv_red["low"] - sl_buf_pts

    # SL distance cap
    sl_dist_pts = entry - sl
    if sl_max_pts is not None and sl_dist_pts > sl_max_pts: return None

    # Compute TP per mode
    if tp_mode == "peak":
        high_window = [m5_bars[j]["high"] for j in range(max(0, idx-30), idx)]
        if not high_window: return None
        tp = max(high_window)
    elif tp_mode == "fixed_usd":
        # TP at entry + ($tp_value / 0.10 lots / 100) = entry + tp_value / 10
        tp = entry + tp_value / 10.0
    elif tp_mode == "rr_multiple":
        # TP at entry + (entry - sl) * R
        tp = entry + sl_dist_pts * tp_value
    else:
        return None

    if tp <= entry + 0.3: return None    # need at least 3 pip TP distance
    return entry, sl, tp, {"setup": "S1_buy", "uhv_red_t": uhv_red["time"]}


def run_config(tp_mode, tp_value, sl_buf_pts, sl_max_pts,
               days_bars, h1_fvgs, tick_files, exec_tf=5):
    all_trades = []
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        day_bars = days_bars[day]
        if len(day_bars) < 30: continue
        m5 = aggregate_to_tf(day_bars, exec_tf) if exec_tf != 1 else list(day_bars)

        signals = []
        fired_keys = set()
        for idx in range(25, len(m5)):
            r = detect_s1_buy_custom(m5, idx, h1_fvgs,
                                     tp_mode, tp_value, sl_buf_pts, sl_max_pts)
            if r is None: continue
            entry, sl, tp, ref = r
            key = ref["uhv_red_t"]
            if key in fired_keys: continue
            fired_keys.add(key)
            signals.append({
                "fire_time": m5[idx]["time"] + timedelta(minutes=exec_tf),
                "side": +1, "entry": entry, "sl": sl, "tp": tp,
                "ref": ref, "setup": "S1_buy",
            })
        if not signals: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        done = replay_signals(ticks, signals, lots=0.10)
        for d in done: d["day"] = day
        all_trades.extend(done)

    n = len(all_trades)
    if n == 0: return None
    wins = [t["pnl"] for t in all_trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in all_trades if t["pnl"] < 0]
    n_w, n_l = len(wins), len(losses)
    pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
    w_avg = sum(wins)/n_w if n_w else 0
    l_avg = -sum(losses)/n_l if n_l else 0
    total = sum(t["pnl"] for t in all_trades)
    ev = pwin*w_avg - (1-pwin)*l_avg
    return dict(n=n, pwin=pwin, w_avg=w_avg, l_avg=l_avg, ev=ev, total=total)


def main():
    print("Loading...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1_all = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1_all)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    print(f"\n=== S1 BUY TP-placement sweep (M5 exec) ===")
    print(f"{'mode':<12} {'val':>6} {'SLcap':>6} {'n':>4} {'pwin':>6} "
          f"{'Wavg':>7} {'Lavg':>7} {'EV':>8} {'TOTAL':>10}")

    configs = []
    # Baseline (original)
    configs.append(("peak",       0.0, None))
    # Fixed dollar TPs
    for tp_usd in [5, 10, 15, 20, 30, 50]:
        configs.append(("fixed_usd", tp_usd, None))
        configs.append(("fixed_usd", tp_usd, 8.0))   # also cap SL ≤ 8 pts
        configs.append(("fixed_usd", tp_usd, 5.0))   # also cap SL ≤ 5 pts
    # R:R multiples
    for r in [1.0, 1.5, 2.0, 3.0]:
        configs.append(("rr_multiple", r, None))
        configs.append(("rr_multiple", r, 8.0))
        configs.append(("rr_multiple", r, 5.0))

    best = None
    for mode, val, slcap in configs:
        res = run_config(mode, val, 0.10, slcap, days_bars, h1_fvgs, tick_files)
        if res is None:
            print(f"{mode:<12} {val:>6.1f} {str(slcap):>6} -- no trades --")
            continue
        marker = " *" if res["total"] > 0 else ""
        print(f"{mode:<12} {val:>6.1f} {str(slcap):>6} {res['n']:>4} "
              f"{res['pwin']:>6.3f} ${res['w_avg']:>5.2f} ${res['l_avg']:>5.2f} "
              f"${res['ev']:>+6.2f} ${res['total']:>+8.2f}{marker}")
        if best is None or res["total"] > best[0]:
            best = (res["total"], mode, val, slcap, res)

    print()
    if best:
        print(f"BEST: mode={best[1]} val={best[2]} sl_cap={best[3]}")
        print(f"  n={best[4]['n']} pwin={best[4]['pwin']:.3f} "
              f"Wavg=${best[4]['w_avg']:.2f} Lavg=${best[4]['l_avg']:.2f} "
              f"EV=${best[4]['ev']:+.2f}")
        print(f"  12-day total: ${best[0]:+.2f}  |  @ 0.40 lots: ${best[0]*4:+.2f}")


if __name__ == "__main__":
    main()
