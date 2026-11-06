"""backtest_trailing_stop.py — Zee's question (2026-05-22):

  "Instead of breakeven-at-entry, move the SL up to (near) the current price to
   lock the profit, and climb it as price climbs. If it reverses we book what's
   locked. If it runs we keep going."

This is DIFFERENT from the ATR-Chandelier we rejected: that one DROPPED the TP.
Here we KEEP the static TP and add a raise-only trailing stop that activates once
the trade is +1R, then sits at  peak − distance,  floored at breakeven (so the
'lock' never gives back to a loss). We sweep the distance:
  • pts  trails: peak − $X  (X=0.5 ≈ "lock to current price", 2.0, 5.0)
  • atr  trails: peak − k×H1-ATR(14)  (k = 1.0, 1.5, 2.0, 3.0)

Compared against baseline (static TP/SL) and be (deployed breakeven). Static TP is
kept in every variant. Run on S3 (the live-trade strategy) and NSND (n big).

Verdict question: does any trail beat plain breakeven on TOTAL and out-of-sample?

Run:  py backtest_trailing_stop.py
"""
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day,
                                      detect_signals as detect_s3)
from backtest_setups import find_h1_fvgs
from backtest_ns_nd import detect_signals_for_day
from backtest_exit_protocols import build_h1_atr, atr_at

CONTRACT = 100.0
PIP = 0.10
ACTIVATE_R = 1.0      # trailing/BE arms once the trade is +this many R
BE_BUFFER = 0.30      # breakeven floor = entry ± this (price units)

# S3 deployed signal config
S3 = dict(SL_BUF=2.0, TREND=2.0, TREND_LB=24, PEAK_LB=10, FVG=True, TF=5)
# NSND deployed signal config
NS_KW = dict(require_fvg=True, require_trend=True,
             fvg_timeframes=(15,), fvg_min_prior_taps=0)
NS_SL_BUF_PIPS = 1.0
NS_TP_USD = 12.0


def replay(ticks, sigs, lots, contract, policy, atr_times, atr_vals,
           trail_mode=None, trail_k=0.0):
    """policy ∈ {baseline, be, trail}. trail keeps static TP and ratchets SL up to
    max(peak − dist, breakeven) once +ACTIVATE_R. dist = trail_k (pts) or k×ATR."""
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []

    def close_unit(u, exit_px, why):
        u["pnl"] = u["side"] * (exit_px - u["e"]) * ppp
        u["why"] = why
        done.append(u)
        units.remove(u)

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            side = u["side"]
            R = abs(u["e"] - u["sl0"]) or PIP
            prof = (bid - u["e"]) if side > 0 else (u["e"] - ask)
            be_sl = u["e"] + BE_BUFFER if side > 0 else u["e"] - BE_BUFFER

            def raise_stop(new_sl):
                if side > 0 and new_sl > u["sl"]:
                    u["sl"] = new_sl
                elif side < 0 and new_sl < u["sl"]:
                    u["sl"] = new_sl

            if prof >= ACTIVATE_R * R:
                if policy == "be":
                    raise_stop(be_sl)
                elif policy == "trail":
                    if side > 0:
                        u["peak"] = max(u["peak"], bid)
                    else:
                        u["peak"] = min(u["peak"], ask)
                    if trail_mode == "atr":
                        dist = (u["atr"] or R) * trail_k
                    else:
                        dist = trail_k
                    raw = (u["peak"] - dist) if side > 0 else (u["peak"] + dist)
                    floored = max(raw, be_sl) if side > 0 else min(raw, be_sl)
                    raise_stop(floored)

            hit_sl = (bid <= u["sl"]) if side > 0 else (ask >= u["sl"])
            if hit_sl:
                close_unit(u, u["sl"], "trail/be")
                continue
            hit_tp = (bid >= u["tp"]) if side > 0 else (ask <= u["tp"])
            if hit_tp:
                close_unit(u, u["tp"], "tp")
                continue
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2:
                e = ask if pending["side"] > 0 else bid
                tp = pending["tp_abs"]
                if tp is None:
                    d = pending["tp_usd"] / ppp
                    tp = e + d if pending["side"] > 0 else e - d
                units.append({"side": pending["side"], "e": e,
                              "sl": pending["sl_abs"], "sl0": pending["sl_abs"],
                              "tp": tp, "peak": e,
                              "atr": atr_at(atr_times, atr_vals, pending["fire_time"])})
            pending = next(sig_iter, None)
    if ticks:
        last = ticks[-1]
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


def fmt(label, r):
    if r is None:
        return f"  {label:<22} no trades"
    pf = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
    return (f"  {label:<22} n={r['n']:>3}  WR={r['pwin']:.2f}  W=${r['w']:>5.1f}  "
            f"L=${r['l']:>5.1f}  PF={pf:>4}  worst=${r['worst']:>+6.1f}  "
            f"TOTAL=${r['total']:>+8.1f}")


VARIANTS = [
    ("baseline (static TP/SL)", "baseline", None, 0.0),
    ("breakeven @+1R",          "be",       None, 0.0),
    ("trail peak-$0.5 (≈lock)", "trail",    "pts", 0.5),
    ("trail peak-$2.0",         "trail",    "pts", 2.0),
    ("trail peak-$5.0",         "trail",    "pts", 5.0),
    ("trail peak-1.0xATR",      "trail",    "atr", 1.0),
    ("trail peak-1.5xATR",      "trail",    "atr", 1.5),
    ("trail peak-2.0xATR",      "trail",    "atr", 2.0),
    ("trail peak-3.0xATR",      "trail",    "atr", 3.0),
]


def run(title, day_keys, build_sigs, ticks_by_day, lots, atr_times, atr_vals):
    print(f"\n{title}  ({len(day_keys)} days)")
    print("-" * 96)
    for label, pol, mode, k in VARIANTS:
        all_done = []
        for day in day_keys:
            sigs = build_sigs(day)
            if not sigs:
                continue
            all_done.extend(replay(ticks_by_day[day], sigs, lots, CONTRACT,
                                   pol, atr_times, atr_vals, mode, k))
        print(fmt(label, stats(all_done)))


def main():
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    atr_times, atr_vals = build_h1_atr(h1, 14)
    h1_fvgs = find_h1_fvgs(h1)
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
    print(f"  TRAILING-STOP (keep TP) vs breakeven — {len(days)} real-tick days, arm @+{ACTIVATE_R}R")
    print("=" * 96)

    def s3_sigs(day):
        out = []
        for s in detect_s3(m5_by_day[day], h1_fvgs, S3["SL_BUF"], S3["TREND"],
                           S3["TREND_LB"], S3["FVG"], S3["PEAK_LB"], S3["TF"]):
            out.append({"side": +1, "fire_time": s["fire_time"],
                        "sl_abs": s["sl"], "tp_abs": s["tp"], "tp_usd": None})
        return out

    print("\n### S3Trader  (0.09 lots, BUY, the live-trade strategy)")
    run("ALL DAYS", days, s3_sigs, ticks_by_day, 0.09, atr_times, atr_vals)
    run("TEST (2nd half / OOS)", days[mid:], s3_sigs, ticks_by_day, 0.09, atr_times, atr_vals)

    def ns_sigs(day):
        out = []
        for s in detect_signals_for_day(m1_by_day[day], **NS_KW):
            sl = (s["sweep_low"] - NS_SL_BUF_PIPS * PIP) if s["side"] > 0 \
                else (s["sweep_high"] + NS_SL_BUF_PIPS * PIP)
            out.append({"side": s["side"], "fire_time": s["fire_time"],
                        "sl_abs": sl, "tp_abs": None, "tp_usd": NS_TP_USD})
        return out

    print("\n\n### NsndTrader  (0.03 lots, BUY+SELL, n≈93 — bigger sample)")
    run("ALL DAYS", days, ns_sigs, ticks_by_day, 0.03, atr_times, atr_vals)
    run("TEST (2nd half / OOS)", days[mid:], ns_sigs, ticks_by_day, 0.03, atr_times, atr_vals)


if __name__ == "__main__":
    main()
