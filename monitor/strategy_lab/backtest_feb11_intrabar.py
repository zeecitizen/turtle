"""backtest_feb11_intrabar.py — the decisive test: TICK-LEVEL entry on the line-break.

Everything before entered at the M1 bar CLOSE (a minute late, after Zee's spike).
Zee entered intrabar, the instant price broke the UHV line. This models that:

  1. At each closed M1 bar, if structure trend (HH/HL) is up and there's a UHV RED
     candle in the recent retracement that price is still BELOW, ARM a buy trigger at
     that candle's HIGH (mirror for sells: UHV green, trigger at its LOW).
  2. Walk ticks. The instant ask crosses the buy trigger (price breaks the line),
     ENTER at ask — intrabar, mid-candle, like Zee. Then his peak-reversal trail exit.
  3. Triggers expire after a few minutes if unbroken; one fill per armed level.

If win rate jumps toward Zee's ~94%, the gap WAS entry timing and a native tick EA is
justified. If not, the edge is his discretionary tape-reading. Honest either way.

Run:  py backtest_feb11_intrabar.py
"""
import sys, glob
from datetime import timedelta
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
EXPIRE_MIN = 3        # an armed trigger is live for this many minutes
LEVEL_TOL = 0.10      # don't re-arm a level within this of an already-active one
MAX_CONC = 3


def trend_dir(win):
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


def arm_triggers(m1):
    """At each closed M1 bar, emit any armed break trigger (side, level, t, expiry)."""
    out = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bar = m1[i]
        td = trend_dir(m1[i - TREND_LB:i])
        win = m1[i - RETRACE_LB:i + 1]
        t = bar["time"]
        exp = t + timedelta(minutes=EXPIRE_MIN)
        if td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                uhv = max(reds, key=lambda b: b["vol"])
                if bar["close"] < uhv["high"]:           # breakout still pending
                    out.append((t, +1, uhv["high"], exp))
        elif td == -1:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens:
                uhv = max(greens, key=lambda b: b["vol"])
                if bar["close"] > uhv["low"]:
                    out.append((t, -1, uhv["low"], exp))
    return out


def replay(ticks, arms, trail_give, skim_cap=None, vel_min=0.0, vel_secs=3.0):
    """vel_min: require price to have moved >= this much in the break direction over
    the last vel_secs seconds (a genuine SPIKE, not a drift through the line). 0 = off."""
    ppp = LOTS * CONTRACT
    done = []
    arm_it = iter(arms)
    nxt = next(arm_it, None)
    active = []      # armed-but-unbroken triggers: dicts {side, level, expiry}
    units = []
    recent = []      # rolling (t, mid) for velocity gate
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        if vel_min > 0:
            recent.append((t, (bid + ask) / 2))
            cutoff = t - timedelta(seconds=vel_secs)
            while recent and recent[0][0] < cutoff:
                recent.pop(0)
        # bring armed triggers online as their bar closes
        while nxt is not None and t >= nxt[0]:
            at, side, level, exp = nxt
            if not any(u["side"] == side and abs(u["level"] - level) < LEVEL_TOL for u in active):
                active.append({"side": side, "level": level, "expiry": exp})
            nxt = next(arm_it, None)
        # expire stale triggers
        active = [a for a in active if a["expiry"] >= t]
        # fire entries on line-break
        vel = ((bid + ask) / 2 - recent[0][1]) if (vel_min > 0 and recent) else None
        for a in active[:]:
            if len(units) >= MAX_CONC:
                break
            if a["side"] > 0 and ask >= a["level"]:
                if vel_min > 0 and (vel is None or vel < vel_min):
                    continue   # broke the line but no upward spike — skip (false break)
                units.append({"side": +1, "e": ask, "peak": bid}); active.remove(a)
            elif a["side"] < 0 and bid <= a["level"]:
                if vel_min > 0 and (vel is None or -vel < vel_min):
                    continue
                units.append({"side": -1, "e": bid, "peak": ask}); active.remove(a)
        # manage open positions (peak-reversal trail)
        for u in units[:]:
            s = u["side"]
            if s > 0:
                u["peak"] = max(u["peak"], bid)
                if skim_cap is not None and bid - u["e"] >= skim_cap:
                    u["pnl"] = skim_cap * ppp; done.append(u); units.remove(u); continue
                if bid <= u["peak"] - trail_give:
                    u["pnl"] = (bid - u["e"]) * ppp; done.append(u); units.remove(u); continue
            else:
                u["peak"] = min(u["peak"], ask)
                if skim_cap is not None and u["e"] - ask >= skim_cap:
                    u["pnl"] = skim_cap * ppp; done.append(u); units.remove(u); continue
                if ask >= u["peak"] + trail_give:
                    u["pnl"] = (u["e"] - ask) * ppp; done.append(u); units.remove(u); continue
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
        cache[d] = {"arms": arm_triggers(days_b[d]), "ticks": ticks}
    days = sorted(cache); mid = len(days) // 2
    print(f"FEB-11 INTRABAR ENTRY (line-break) + peak-trail — broker ticks, {len(days)} days, "
          f"{LOTS} lots, BUY+SELL\n")
    print(f"    {'exit':<28}{'ALL':<42}OOS (test half)")
    for lbl, kw in [
        ("no vel-gate, trail$0.5",        dict(trail_give=0.5)),
        ("vel>=$0.5/3s, trail$0.5",       dict(trail_give=0.5, vel_min=0.5)),
        ("vel>=$1.0/3s, trail$0.5",       dict(trail_give=0.5, vel_min=1.0)),
        ("vel>=$1.5/2s, trail$0.5+skim$2",dict(trail_give=0.5, skim_cap=2.0, vel_min=1.5, vel_secs=2.0)),
        ("vel>=$2.0/2s, trail$0.7+skim$3",dict(trail_give=0.7, skim_cap=3.0, vel_min=2.0, vel_secs=2.0)),
    ]:
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], cache[d]["arms"], **kw)
            allt += tr
            if k >= mid:
                testt += tr
        print(f"    {lbl:<28}{stat(allt):<42}{stat(testt)}")


if __name__ == "__main__":
    main()
