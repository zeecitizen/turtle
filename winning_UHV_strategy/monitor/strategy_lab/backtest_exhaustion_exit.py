"""backtest_exhaustion_exit.py — Zee's question (2026-05-22):

  "Isn't there a momentum-weakening check — RSI/MACD/CVD/TD divergence — that says
   'jump out now with the $168 before it crashes'?"

The doc's own conclusion is to use exhaustion as a SCALE-OUT cue, not all-or-nothing
— which is what S3 already does (partial 50% @+1.5R + breakeven). The open question:
does timing the exit on a momentum-EXHAUSTION SIGNAL beat just reaching +1.5R?

Test: RSI(14) bearish-divergence exit (price makes a higher high, RSI makes a lower
high from an elevated level) as a runner/position exit when in profit. Mirror for
sells (bullish divergence). Compared against baseline / breakeven / partial_be on the
SAME deployed signals + 13 real-tick days. Also reports how often the divergence exit
actually FIRES (does it even engage on a fast scalp?).

  baseline    : static TP/SL
  be          : breakeven @+1R
  be_div      : breakeven + exit whole position on divergence (when in profit)
  partial_be  : bank 50% @+1.5R, BE rest, keep TP   (== deployed S3)
  partial_div : bank 50% @+1.5R, BE rest, exit runner on divergence OR TP

Run:  py backtest_exhaustion_exit.py
"""
import sys
import glob
import bisect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day,
                                      detect_signals as detect_s3)
from backtest_setups import find_h1_fvgs
from backtest_ns_nd import detect_signals_for_day

CONTRACT = 100.0
PIP = 0.10
ACTIVATE_R = 1.0
PARTIAL_R = 1.5
PARTIAL_FRAC = 0.5
BE_BUFFER = 0.30
DIV_K = 5            # bars back to compare the swing high/low
RSI_P = 14
S3 = dict(SL_BUF=2.0, TREND=2.0, TREND_LB=24, PEAK_LB=10, FVG=True, TF=5)
NS_KW = dict(require_fvg=True, require_trend=True,
             fvg_timeframes=(15,), fvg_min_prior_taps=0)


def wilder_rsi(closes, period=RSI_P):
    rsi = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi
    g = l = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        g += max(ch, 0.0)
        l += max(-ch, 0.0)
    ag, al = g / period, l / period
    rsi[period] = 100.0 - 100.0 / (1 + ag / al) if al > 0 else 100.0
    for i in range(period + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(ch, 0.0)) / period
        al = (al * (period - 1) + max(-ch, 0.0)) / period
        rsi[i] = 100.0 - 100.0 / (1 + ag / al) if al > 0 else 100.0
    return rsi


def build_div(bars):
    """Returns (times, bear[], bull[]). bear=price HH but RSI lower-high from an
    elevated level (sell-side exhaustion of a long). bull = mirror."""
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    times = [b["time"] for b in bars]
    rsi = wilder_rsi(closes)
    bear = [False] * len(bars)
    bull = [False] * len(bars)
    for i in range(RSI_P + DIV_K, len(bars)):
        if rsi[i] is None or rsi[i - DIV_K] is None:
            continue
        if highs[i] > highs[i - DIV_K] and rsi[i] < rsi[i - DIV_K] and rsi[i - DIV_K] >= 55:
            bear[i] = True
        if lows[i] < lows[i - DIV_K] and rsi[i] > rsi[i - DIV_K] and rsi[i - DIV_K] <= 45:
            bull[i] = True
    return times, bear, bull


def div_active(div, t, side):
    times, bear, bull = div
    i = bisect.bisect_right(times, t) - 1
    if i < 0:
        return False
    return bear[i] if side > 0 else bull[i]


def replay(ticks, sigs, lots, contract, policy, div):
    ppp = lots * contract
    done = []
    fired_div = 0
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []

    def close_unit(u, exit_px, why):
        rem = 1.0 - u["banked_frac"]
        u["pnl"] = u["banked_pnl"] + u["side"] * (exit_px - u["e"]) * ppp * rem
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

            def raise_stop(ns):
                if side > 0 and ns > u["sl"]:
                    u["sl"] = ns
                elif side < 0 and ns < u["sl"]:
                    u["sl"] = ns

            if policy in ("partial_be", "partial_div") and not u["banked_frac"] \
                    and prof >= PARTIAL_R * R:
                u["banked_pnl"] = prof * ppp * PARTIAL_FRAC
                u["banked_frac"] = PARTIAL_FRAC
                raise_stop(be_sl)
            if policy in ("be", "be_div") and prof >= ACTIVATE_R * R:
                raise_stop(be_sl)

            # divergence exit (only when in profit)
            if policy in ("be_div", "partial_div") and prof > 0 and div_active(div, t, side):
                fired_div += 1
                close_unit(u, bid if side > 0 else ask, "div")
                continue

            hit_sl = (bid <= u["sl"]) if side > 0 else (ask >= u["sl"])
            if hit_sl:
                close_unit(u, u["sl"], "sl/be")
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
                              "sl": pending["sl_abs"], "sl0": pending["sl_abs"], "tp": tp,
                              "banked_frac": 0.0, "banked_pnl": 0.0})
            pending = next(sig_iter, None)
    if ticks:
        last = ticks[-1]
        for u in units[:]:
            close_unit(u, last["bid"] if u["side"] > 0 else last["ask"], "eod")
    return done, fired_div


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


def fmt(label, r, fired):
    if r is None:
        return f"  {label:<14} no trades"
    pf = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
    tag = f"  div-fired={fired}" if fired else ""
    return (f"  {label:<14} n={r['n']:>3}  WR={r['pwin']:.2f}  W=${r['w']:>5.1f}  "
            f"L=${r['l']:>5.1f}  PF={pf:>4}  worst=${r['worst']:>+6.1f}  "
            f"TOTAL=${r['total']:>+8.1f}{tag}")


def run(title, day_keys, build_sigs, div_by_day, ticks_by_day, lots):
    print(f"\n{title}  ({len(day_keys)} days)")
    print("-" * 100)
    for pol in ("baseline", "be", "be_div", "partial_be", "partial_div"):
        all_done, fired = [], 0
        for day in day_keys:
            sigs = build_sigs(day)
            if not sigs:
                continue
            d, f = replay(ticks_by_day[day], sigs, lots, CONTRACT, pol, div_by_day[day])
            all_done.extend(d)
            fired += f
        print(fmt(pol, stats(all_done), fired))


def main():
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    m5_by_day, m1_by_day, ticks_by_day = {}, {}, {}
    div_m5, div_m1 = {}, {}
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
        m5 = aggregate_to_tf(db, 5)
        m5_by_day[day] = m5
        m1_by_day[day] = db
        ticks_by_day[day] = ticks
        div_m5[day] = build_div(m5)
        div_m1[day] = build_div(db)
    days = sorted(ticks_by_day.keys())
    mid = len(days) // 2

    print("=" * 100)
    print(f"  EXHAUSTION (RSI-divergence) EXIT vs deployed rules — {len(days)} real-tick days")
    print(f"  RSI({RSI_P}) bearish/bullish div, lookback {DIV_K} bars, exit only when in profit")
    print("=" * 100)

    def s3_sigs(day):
        return [{"side": +1, "fire_time": s["fire_time"], "sl_abs": s["sl"],
                 "tp_abs": s["tp"], "tp_usd": None}
                for s in detect_s3(m5_by_day[day], h1_fvgs, S3["SL_BUF"], S3["TREND"],
                                   S3["TREND_LB"], S3["FVG"], S3["PEAK_LB"], S3["TF"])]

    print("\n### S3Trader (0.09, BUY — the live-trade strategy), divergence on M5")
    run("ALL DAYS", days, s3_sigs, div_m5, ticks_by_day, 0.09)
    run("TEST (OOS)", days[mid:], s3_sigs, div_m5, ticks_by_day, 0.09)

    def ns_sigs(day):
        out = []
        for s in detect_signals_for_day(m1_by_day[day], **NS_KW):
            sl = (s["sweep_low"] - PIP) if s["side"] > 0 else (s["sweep_high"] + PIP)
            out.append({"side": s["side"], "fire_time": s["fire_time"],
                        "sl_abs": sl, "tp_abs": None, "tp_usd": 12.0})
        return out

    print("\n\n### NsndTrader (0.03, BUY+SELL, n≈93), divergence on M1")
    run("ALL DAYS", days, ns_sigs, div_m1, ticks_by_day, 0.03)
    run("TEST (OOS)", days[mid:], ns_sigs, div_m1, ticks_by_day, 0.03)


if __name__ == "__main__":
    main()
