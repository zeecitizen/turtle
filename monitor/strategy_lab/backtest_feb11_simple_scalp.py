"""backtest_feb11_simple_scalp.py — Zee's ACTUAL Feb-11 method (his own words, 2026-05-21).

ENTRY = the simple Lesson-2 "our strategy" UHV breakout (NO sweep, NO big-spread,
NO FVG — those were added later onto S1):
  - confirm trend
  - find the ultra-high-volume candle in a retracement
  - a LOW-volume MOMENTUM candle breaks its line (high for buy / low for sell)
  - enter at that candle's close

EXIT = manual SCALP/SKIM (not TP 1:1): grab a few points fast, and scratch out
quickly if it goes against (a few seconds' grace, then cut; no fixed SL).

Runs on the BROKER tick feed (shano_ticks) at M1. Sweeps skim-target + scratch
behaviour, BUY+SELL, walk-forward. The question: is his real entry+scalp profitable?

Run:  py backtest_feb11_simple_scalp.py
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30                    # bars of same-TF structure used to read trend
RETRACE_LB = 12
MOM_BODY_FRAC = 0.55             # momentum candle: body/range >= this (small wicks)


def trend_dir(win):
    """Same-timeframe market structure ('camel humps'): HH+HL = uptrend (+1),
    LH+LL = downtrend (-1), else 0. Compares the recent half vs the older half."""
    h = len(win) // 2
    older, recent = win[:h], win[h:]
    if not older or not recent:
        return 0
    hh = max(b["high"] for b in recent) > max(b["high"] for b in older)
    hl = min(b["low"] for b in recent) > min(b["low"] for b in older)
    lh = max(b["high"] for b in recent) < max(b["high"] for b in older)
    ll = min(b["low"] for b in recent) < min(b["low"] for b in older)
    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return 0


def detect(m1, require_trend=True):
    """Simple Lesson-2 UHV breakout signals (BUY+SELL). One per breakout bar."""
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < MOM_BODY_FRAC:        # momentum candle: small wicks
            continue
        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody:                    # strong candle
            continue
        td = trend_dir(m1[i - TREND_LB:i])     # same-TF HH/HL structure
        # BUY: green momentum breaks above the UHV RED candle's high, low vol
        if bo["close"] > bo["open"]:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds and (not require_trend or td == 1):
                uhv = max(reds, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                    sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1)})
                    continue
        # SELL: red momentum breaks below the UHV GREEN candle's low, low vol
        if bo["close"] < bo["open"]:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens and (not require_trend or td == -1):
                uhv = max(greens, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                    sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1)})
    return sigs


def replay(ticks, sigs, skim, sl, scratch_s, max_conc=3):
    """Scalp: exit at +skim (skim profit). Cut at -sl (fast manual cut, if sl>0).
    If scratch_s set: once that many seconds pass and not in profit, exit at market."""
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            s = u["side"]
            prof = (bid - u["e"]) if s > 0 else (u["e"] - ask)   # current $ distance
            if prof >= skim:
                u["pnl"] = skim * ppp; done.append(u); units.remove(u); continue
            if sl > 0 and prof <= -sl:
                u["pnl"] = -sl * ppp; done.append(u); units.remove(u); continue
            if scratch_s is not None and (t - u["open_t"]).total_seconds() >= scratch_s and prof < 0:
                u["pnl"] = prof * ppp; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                units.append({"side": pend["side"], "e": ask if pend["side"] > 0 else bid, "open_t": t})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            done.append(u)
    return done


def replay_trail(ticks, sigs, trail_give, skim_cap=None, max_conc=3):
    """Zee's real exit: track the PEAK favorable price; exit the instant price
    reverses `trail_give` from that peak ('profit starts decreasing -> out').
    Optional skim_cap = grab +$ immediately if a spike reaches it. Losers end tiny
    (exit on first reversal ~ breakeven minus spread). Spread is real: buy fills at
    ask, exits at bid (and vice-versa)."""
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            s = u["side"]
            fav = bid if s > 0 else ask                 # favourable-direction price
            # update running peak (best favourable excursion)
            if s > 0:
                u["peak"] = max(u["peak"], bid)
                prof = bid - u["e"]
                if skim_cap is not None and prof >= skim_cap:
                    u["pnl"] = skim_cap * ppp; done.append(u); units.remove(u); continue
                if bid <= u["peak"] - trail_give:        # reversed from the high
                    u["pnl"] = (bid - u["e"]) * ppp; done.append(u); units.remove(u); continue
            else:
                u["peak"] = min(u["peak"], ask)
                prof = u["e"] - ask
                if skim_cap is not None and prof >= skim_cap:
                    u["pnl"] = skim_cap * ppp; done.append(u); units.remove(u); continue
                if ask >= u["peak"] + trail_give:
                    u["pnl"] = (u["e"] - ask) * ppp; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                units.append({"side": pend["side"], "e": e, "peak": (bid if pend["side"] > 0 else ask)})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            done.append(u)
    return done


def stat(trades):
    n = len(trades)
    if not n:
        return "n=0"
    w = [x["pnl"] for x in trades if x["pnl"] > 0]
    l = [x["pnl"] for x in trades if x["pnl"] < 0]
    tot = sum(x["pnl"] for x in trades)
    wr = len(w) / (len(w) + len(l)) if (w or l) else 0
    return (f"n={n:>4} {n/13:>4.1f}/d  WR={wr:.2f}  W=${(sum(w)/len(w) if w else 0):>4.1f} "
            f"L=${(-sum(l)/len(l) if l else 0):>4.1f}  TOT=${tot:>+8.1f}")


def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 200:
            continue
        ticks = load_ticks(tf)
        if len(ticks) < 100:
            continue
        cache[d] = {"m1": days_b[d], "ticks": ticks}
    days = sorted(cache); mid = len(days) // 2
    print(f"FEB-11 SIMPLE UHV-BREAKOUT + SCALP exit — broker ticks, {len(days)} days, "
          f"{LOTS} lots, BUY+SELL\n")

    # ── Zee's REAL exit: peak-reversal trail (exit on first tick down from the high) ──
    sigT = {d: detect(cache[d]["m1"], require_trend=True) for d in days}
    ne = sum(len(sigT[d]) for d in days)
    print(f"=== PEAK-REVERSAL TRAIL (Zee's actual exit) — trend ON, {ne/len(days):.0f}/day ===")
    print(f"    {'exit':<30}{'ALL':<42}OOS (test half)")
    for lbl, kw in [
        ("trail $0.2 (hair-trigger)",      dict(trail_give=0.2)),
        ("trail $0.3",                     dict(trail_give=0.3)),
        ("trail $0.5",                     dict(trail_give=0.5)),
        ("trail $0.3 + skim$1 cap",        dict(trail_give=0.3, skim_cap=1.0)),
        ("trail $0.3 + skim$2 cap",        dict(trail_give=0.3, skim_cap=2.0)),
        ("trail $0.5 + skim$2 cap",        dict(trail_give=0.5, skim_cap=2.0)),
    ]:
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_trail(cache[d]["ticks"], sigT[d], **kw)
            allt += tr
            if k >= mid:
                testt += tr
        print(f"    {lbl:<30}{stat(allt):<42}{stat(testt)}")
    print()

    # ── Zee's entry + SENSIBLE fixed TP/SL, walk-forward robustness (both halves +?) ──
    print("=== SIMPLE-UHV + STRUCTURE entry, fixed TP/SL — walk-forward (need BOTH halves +) ===")
    for lbl, (tp, sl) in [("TP5/SL5", (5, 5)), ("TP7/SL5", (7, 5)), ("TP10/SL7", (10, 7)),
                          ("TP5/SL3", (5, 3)), ("TP8/SL4", (8, 4)), ("TP12/SL6", (12, 6))]:
        train, test = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sigT[d], skim=tp, sl=sl, scratch_s=None)
            (train if k < mid else test).extend(tr)
        print(f"    {lbl:<10} TRAIN {stat(train):<40} TEST {stat(test)}")
    print()

    # ── Stability: is the 2:1 region BROADLY positive in both halves (not 1 lucky cell)? ──
    print("=== Grid stability (TRAIN / TEST totals, $) — robust = both > 0 across the region ===")
    print(f"    {'':6}" + "".join(f"SL{sl:<10}" for sl in (5, 6, 7)))
    for tp in (9, 10, 11, 12, 13, 14):
        cells = []
        for sl in (5, 6, 7):
            tr_tr, tr_te = [], []
            for k, d in enumerate(days):
                tr = replay(cache[d]["ticks"], sigT[d], skim=tp, sl=sl, scratch_s=None)
                (tr_tr if k < mid else tr_te).extend(tr)
            a = sum(x["pnl"] for x in tr_tr); b = sum(x["pnl"] for x in tr_te)
            cells.append(f"{a:>+5.0f}/{b:>+5.0f}")
        print(f"    TP{tp:<4}" + "  ".join(cells))
    # per-day P&L for TP12/SL6 (is it broad or 1-2 days?)
    print("\n=== Per-day P&L, TP12/SL6 (2:1) ===")
    pos = 0
    for d in days:
        tr = replay(cache[d]["ticks"], sigT[d], skim=12, sl=6, scratch_s=None)
        tot = sum(x["pnl"] for x in tr)
        if tot > 0:
            pos += 1
        print(f"    {d}: {len(tr):>3} tr  ${tot:>+8.1f}")
    print(f"    => {pos}/{len(days)} green days")
    print()

    for rt in (True, False):
        sig = {d: detect(cache[d]["m1"], require_trend=rt) for d in days}
        nb = sum(1 for d in days for s in sig[d] if s["side"] > 0)
        ns = sum(1 for d in days for s in sig[d] if s["side"] < 0)
        print(f"--- trend filter {'ON' if rt else 'OFF'} --- entries: {nb} buy + {ns} sell "
              f"= {(nb+ns)/len(days):.1f}/day\n    {'exit':<28}{'ALL':<42}OOS")
        for lbl, kw in [
            ("skim$1, cut$2",            dict(skim=1.0, sl=2.0, scratch_s=None)),
            ("skim$2, cut$3",            dict(skim=2.0, sl=3.0, scratch_s=None)),
            ("skim$3, cut$3",            dict(skim=3.0, sl=3.0, scratch_s=None)),
            ("skim$2, no SL, scratch10s",dict(skim=2.0, sl=0.0, scratch_s=10)),
            ("skim$2, cut$4, scratch15s",dict(skim=2.0, sl=4.0, scratch_s=15)),
        ]:
            allt, testt = [], []
            for k, d in enumerate(days):
                tr = replay(cache[d]["ticks"], sig[d], **kw)
                allt += tr
                if k >= mid:
                    testt += tr
            print(f"    {lbl:<28}{stat(allt):<42}{stat(testt)}")
        print()


if __name__ == "__main__":
    main()
