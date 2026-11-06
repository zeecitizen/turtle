"""backtest_exit_protocols_multi.py — does 2R-Free-Roll help S1 and NSND too?

Same idea as backtest_exit_protocols.py (which covered S3), but side-aware so it
handles S1 (BUY+SELL UHV breakout) and NSND (BUY+SELL No-Supply/No-Demand).
Holds each EA's DEPLOYED signal config FIXED; only the exit policy varies:

  baseline    : static SL / static TP            (== current live EA)
  be          : + breakeven once +BreakevenR reached
  partial_be  : + bank 50% at +PartialR, BE rest, keep static TP
  partial_atr : + bank 50%, BE rest, DROP TP, trail on 3x H1-ATR (the doc's full
                protocol — included only to confirm/deny it per strategy)

Deployed configs (from the .mq5 sources, 2026-05-22):
  S1   0.06 lots  BUY+SELL  SL=$2.00  TP=$7.5pts  H1-FVG+sweep  (big-spread filter
       NOT in this harness's signal gen → signal count differs; relative exit
       comparison still valid since the SAME signals feed every policy)
  NSND 0.03 lots  BUY+SELL  SL=$0.10  TP=$12usd   M15-FVG + trend

Per feedback_validate_profitability_not_capture: this runs BEFORE wiring the exit
into S1Trader.mq5 / NsndTrader.mq5. Deploy only what doesn't hurt OOS.

Run:  py backtest_exit_protocols_multi.py
"""
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import s1_mirror
from backtest_ns_nd import detect_signals_for_day
from backtest_exit_protocols import build_h1_atr, atr_at

CONTRACT = 100.0
PIP = 0.10

# protocol knobs (identical to the S3 run)
BE_R, BE_BUFFER = 1.0, 0.30
PARTIAL_R, PARTIAL_FRAC = 1.5, 0.5
ATR_MULT = 3.0


def norm_s1(sigs):
    """s1_mirror already gives absolute sl & tp."""
    out = []
    for s in sigs:
        out.append({"side": s["side"], "fire_time": s["fire_time"],
                    "sl_abs": s["sl"], "tp_abs": s["tp"], "tp_usd": None})
    return out


def norm_nsnd(sigs, sl_buf_pips, tp_usd):
    out = []
    for s in sigs:
        if s["side"] > 0:
            sl_abs = s["sweep_low"] - sl_buf_pips * PIP
        else:
            sl_abs = s["sweep_high"] + sl_buf_pips * PIP
        out.append({"side": s["side"], "fire_time": s["fire_time"],
                    "sl_abs": sl_abs, "tp_abs": None, "tp_usd": tp_usd})
    return out


def replay(ticks, sigs, lots, contract, policy, atr_times=None, atr_vals=None,
           max_concurrent=2):
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []

    def close_unit(u, exit_px, why):
        rem = 1.0 - u["banked_frac"]
        pnl = u["banked_pnl"] + u["side"] * (exit_px - u["e"]) * ppp * rem
        u["pnl"], u["why"] = pnl, why
        done.append(u)
        units.remove(u)

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            side = u["side"]
            R = abs(u["e"] - u["sl0"]) or PIP
            fav_px = bid if side > 0 else ask          # favourable-direction price
            prof = (bid - u["e"]) if side > 0 else (u["e"] - ask)  # $-distance in price
            be_sl = u["e"] + BE_BUFFER if side > 0 else u["e"] - BE_BUFFER

            def raise_stop(new_sl):
                if side > 0 and new_sl > u["sl"]:
                    u["sl"] = new_sl
                elif side < 0 and new_sl < u["sl"]:
                    u["sl"] = new_sl

            # partial bank + BE
            if policy in ("partial_be", "partial_atr") and not u["banked_frac"]:
                if prof >= PARTIAL_R * R:
                    u["banked_pnl"] = prof * ppp * PARTIAL_FRAC
                    u["banked_frac"] = PARTIAL_FRAC
                    raise_stop(be_sl)
            if policy == "be" and not u["be_armed"]:
                if prof >= BE_R * R:
                    raise_stop(be_sl)
                    u["be_armed"] = True
            # ATR runner trail
            if policy == "partial_atr" and u["banked_frac"] and u["atr"]:
                if side > 0:
                    u["peak"] = max(u["peak"], bid)
                    raise_stop(u["peak"] - u["atr"] * ATR_MULT)
                else:
                    u["peak"] = min(u["peak"], ask)
                    raise_stop(u["peak"] + u["atr"] * ATR_MULT)
            # exits
            hit_sl = (bid <= u["sl"]) if side > 0 else (ask >= u["sl"])
            if hit_sl:
                close_unit(u, u["sl"], "sl" if not u["banked_frac"] else "be/trail")
                continue
            use_tp = not (policy == "partial_atr" and u["banked_frac"])
            if use_tp:
                hit_tp = (bid >= u["tp"]) if side > 0 else (ask <= u["tp"])
                if hit_tp:
                    close_unit(u, u["tp"], "tp")
                    continue
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < max_concurrent:
                e = ask if pending["side"] > 0 else bid
                tp = pending["tp_abs"]
                if tp is None:
                    d = pending["tp_usd"] / ppp
                    tp = e + d if pending["side"] > 0 else e - d
                units.append({
                    "side": pending["side"], "e": e,
                    "sl": pending["sl_abs"], "sl0": pending["sl_abs"], "tp": tp,
                    "banked_frac": 0.0, "banked_pnl": 0.0, "be_armed": False,
                    "peak": e,
                    "atr": atr_at(atr_times, atr_vals, pending["fire_time"])
                    if atr_times else None,
                })
            pending = next(sig_iter, None)

    if ticks:
        last = ticks[-1]
        px = last["bid"]
        for u in units[:]:
            close_unit(u, last["bid"] if u["side"] > 0 else last["ask"], "eod")
    return done


def stats(trades):
    n = len(trades)
    if n == 0:
        return None
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    nw, nl = len(wins), len(losses)
    gp, gl = sum(wins), -sum(losses)
    return dict(n=n, pwin=nw / (nw + nl) if (nw + nl) else 0,
                w=sum(wins) / nw if nw else 0, l=-sum(losses) / nl if nl else 0,
                total=sum(t["pnl"] for t in trades),
                pf=(gp / gl) if gl else float("inf"),
                worst=min((t["pnl"] for t in trades), default=0))


def fmt(r):
    if r is None:
        return "no trades"
    pf = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
    return (f"n={r['n']:>3}  WR={r['pwin']:.2f}  W=${r['w']:>5.1f}  L=${r['l']:>5.1f}  "
            f"PF={pf:>4}  worst=${r['worst']:>+6.1f}  TOTAL=${r['total']:>+8.1f}")


def run_block(title, day_keys, build_sigs_for_day, ticks_by_day, lots,
              atr_times, atr_vals):
    print(f"\n{title}  ({len(day_keys)} days)")
    print("-" * 96)
    for pol in ("baseline", "be", "partial_be", "partial_atr"):
        all_done = []
        for day in day_keys:
            sigs = build_sigs_for_day(day)
            if not sigs:
                continue
            all_done.extend(replay(ticks_by_day[day], sigs, lots, CONTRACT,
                                   pol, atr_times, atr_vals))
        print(f"  {pol:<12} {fmt(stats(all_done))}")


def main():
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    atr_times, atr_vals = build_h1_atr(h1, 14)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    m5_by_day, m1_by_day, ticks_by_day = {}, {}, {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars:
            continue
        db = days_bars[day]
        if len(db) < 30:
            continue
        ticks = load_ticks(tf)
        if len(ticks) < 100:
            continue
        m5_by_day[day] = aggregate_to_tf(db, 5)
        m1_by_day[day] = db
        ticks_by_day[day] = ticks
    days = sorted(ticks_by_day.keys())
    mid = len(days) // 2

    print("=" * 96)
    print(f"  EXIT-PROTOCOL COMPARISON — S1 & NSND deployed signals — {len(days)} real-tick days")
    print(f"  knobs: BE@+{BE_R}R(+${BE_BUFFER})  partial {PARTIAL_FRAC:.0%}@+{PARTIAL_R}R  "
          f"ATR-trail {ATR_MULT}x(H1,14)")
    print("=" * 96)

    # ── S1: BUY+SELL, FVG+sweep+fresh-open, SL=$2, TP=$7.5pts, 0.06 lots ──
    def s1_sigs(day):
        return norm_s1(s1_mirror(m5_by_day[day], h1_bull, h1_bear,
                                 sl_buf=2.0, tp_points=7.5,
                                 do_buy=True, do_sell=True,
                                 require_fvg=True, require_sweep=True,
                                 require_open_inside=True))
    print("\n### S1Trader  (0.06 lots, BUY+SELL, SL=$2, TP=$7.5pts, H1-FVG)")
    run_block("ALL DAYS", days, s1_sigs, ticks_by_day, 0.06, atr_times, atr_vals)
    run_block("TRAIN (1st half)", days[:mid], s1_sigs, ticks_by_day, 0.06, atr_times, atr_vals)
    run_block("TEST  (2nd half / OOS)", days[mid:], s1_sigs, ticks_by_day, 0.06, atr_times, atr_vals)

    # ── NSND: BUY+SELL, M15-FVG+trend, SL=$0.10, TP=$12usd, 0.03 lots ──
    NS_KW = dict(require_fvg=True, require_trend=True,
                 fvg_timeframes=(15,), fvg_min_prior_taps=0)

    def ns_sigs(day):
        return norm_nsnd(detect_signals_for_day(m1_by_day[day], **NS_KW),
                         sl_buf_pips=1.0, tp_usd=12.0)
    print("\n\n### NsndTrader  (0.03 lots, BUY+SELL, SL=$0.10, TP=$12usd, M15-FVG)")
    run_block("ALL DAYS", days, ns_sigs, ticks_by_day, 0.03, atr_times, atr_vals)
    run_block("TRAIN (1st half)", days[:mid], ns_sigs, ticks_by_day, 0.03, atr_times, atr_vals)
    run_block("TEST  (2nd half / OOS)", days[mid:], ns_sigs, ticks_by_day, 0.03, atr_times, atr_vals)


if __name__ == "__main__":
    main()
