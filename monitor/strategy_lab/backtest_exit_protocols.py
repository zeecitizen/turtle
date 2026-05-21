"""backtest_exit_protocols.py — does the "2R Free Roll" actually help OUR EAs?

Motivation: a research doc (Protecting Peak Trading Profits.pdf, 2026-05-22)
prescribes the institutional 2R-Free-Roll for our two open XAU buys:
  1. bank ~50% at +1.5R..2R   (Income tranche)
  2. drag SL to breakeven on the rest
  3. ABANDON the static TP; trail the runner with 3.0-3.5x H1-ATR (Chandelier)

That is sound *for trend runners with wide targets*. Our S3 EA is a small-TP
scalper (TP = recent peak, SL = wick low - $2). Grafting trend-runner exits onto
a scalp can DESTROY the edge (cf. v3.43-v3.49: 77-92% WR, lost thousands).
So per feedback_validate_profitability_not_capture: backtest full P&L on the
same 12 real-tick days BEFORE any live change. Same signals, four exit policies.

Policies (all use the SAME deployed-S3 signal set; only the exit differs):
  baseline    : static SL / static TP  (== current live EA)
  be          : + move SL to breakeven once price reaches +1R
  partial_be  : + bank 50% at +1.5R, BE the rest, runner still exits at static TP
  partial_atr : + bank 50% at +1.5R, BE the rest, DROP static TP,
                trail runner at peak - ATR(14,H1)*mult  (the doc's protocol)

Run:  py backtest_exit_protocols.py            (full + train/test split)
"""
import sys
import glob
import bisect
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (
    aggregate_to_tf, find_h1_fvgs, group_bars_by_day,
    detect_signals, CONTRACT_XAU,
)

# ── Deployed-S3 config (held FIXED across every exit policy) ──
REQUIRE_FVG   = True
SL_BUF        = 2.0      # SL = wicking-green low - $2  (matches live EA)
TREND_THRESH  = 2.0
TREND_LB      = 24
PEAK_LB       = 10       # TP = highest high of last 10 M5 bars
TF_MIN        = 5
LOTS          = 0.09     # live S3 lot
LIVE_MULT     = 1.0      # already at live size

# ── Protocol knobs ──
BE_R          = 1.0      # move to BE once +1R reached
BE_BUFFER     = 0.30     # stop set marginally above entry ($ spread/swap cover)
PARTIAL_R     = 1.5      # bank half at +1.5R
PARTIAL_FRAC  = 0.5      # fraction of position banked
ATR_MULT      = 3.0      # Chandelier multiplier on H1 ATR


# ── H1 ATR(14) lookup ──
def build_h1_atr(h1, period=14):
    """Returns (sorted_times, atr_values) for as-of lookup at signal time."""
    trs = []
    for i in range(1, len(h1)):
        h, l, pc = h1[i]["high"], h1[i]["low"], h1[i - 1]["close"]
        trs.append((h1[i]["time"], max(h - l, abs(h - pc), abs(l - pc))))
    times, atrs, run = [], [], []
    for t, tr in trs:
        run.append(tr)
        if len(run) > period:
            run.pop(0)
        if len(run) == period:
            times.append(t)
            atrs.append(sum(run) / period)
    return times, atrs


def atr_at(times, atrs, when):
    if not times:
        return None
    i = bisect.bisect_right(times, when) - 1
    return atrs[i] if i >= 0 else None


# ── Per-trade tick replay with selectable exit policy ──
def replay(ticks, sigs, lots, contract, policy, atr_times=None, atr_vals=None):
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []

    def close_unit(u, exit_px, why):
        # realized = already-banked partial + remainder at exit_px
        rem_frac = 1.0 - u["banked_frac"]
        pnl = u["banked_pnl"] + (exit_px - u["e"]) * ppp * rem_frac
        u["pnl"], u["why"] = pnl, why
        done.append(u)
        units.remove(u)

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            R = u["e"] - u["sl0"]
            if R <= 0:
                R = SL_BUF  # guard
            # --- partial bank + BE arming ---
            if policy in ("partial_be", "partial_atr") and not u["banked_frac"]:
                if bid >= u["e"] + PARTIAL_R * R:
                    u["banked_pnl"] = (bid - u["e"]) * ppp * PARTIAL_FRAC
                    u["banked_frac"] = PARTIAL_FRAC
                    u["sl"] = u["e"] + BE_BUFFER          # BE firewall on remainder
            if policy == "be" and not u["be_armed"]:
                if bid >= u["e"] + BE_R * R:
                    u["sl"] = max(u["sl"], u["e"] + BE_BUFFER)
                    u["be_armed"] = True
            # --- trailing for the ATR runner ---
            if policy == "partial_atr" and u["banked_frac"]:
                u["peak"] = max(u["peak"], bid)
                if u["atr"]:
                    trail = u["peak"] - u["atr"] * ATR_MULT
                    u["sl"] = max(u["sl"], trail)
            # --- exits ---
            if bid <= u["sl"]:
                close_unit(u, u["sl"], "sl" if not u["banked_frac"] else "be/trail")
                continue
            # static TP applies to all but the ATR-runner-after-partial
            use_tp = not (policy == "partial_atr" and u["banked_frac"])
            if use_tp and bid >= u["tp"]:
                close_unit(u, u["tp"], "tp")
                continue
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2:
                units.append({
                    "e": ask, "sl": pending["sl"], "sl0": pending["sl"],
                    "tp": pending["tp"], "fire_time": pending["fire_time"],
                    "banked_frac": 0.0, "banked_pnl": 0.0, "be_armed": False,
                    "peak": ask,
                    "atr": atr_at(atr_times, atr_vals, pending["fire_time"])
                    if atr_times else None,
                })
            pending = next(sig_iter, None)

    if ticks:
        last = ticks[-1]
        for u in units[:]:
            close_unit(u, last["bid"], "eod")
    return done


def stats(trades):
    n = len(trades)
    if n == 0:
        return None
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    nw, nl = len(wins), len(losses)
    total = sum(t["pnl"] for t in trades)
    gp = sum(wins)
    gl = -sum(losses)
    return dict(
        n=n, pwin=nw / (nw + nl) if (nw + nl) else 0,
        w=sum(wins) / nw if nw else 0, l=-sum(losses) / nl if nl else 0,
        total=total, pf=(gp / gl) if gl else float("inf"),
        maxloss=min((t["pnl"] for t in trades), default=0),
    )


def fmt(r):
    if r is None:
        return "no trades"
    pf = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
    return (f"n={r['n']:>3}  WR={r['pwin']:.2f}  W=${r['w']:>5.1f}  "
            f"L=${r['l']:>5.1f}  PF={pf:>4}  worst=${r['maxloss']:>+6.1f}  "
            f"TOTAL=${r['total']:>+8.1f}")


def run(day_keys, cache, h1_fvgs, atr_times, atr_vals, label):
    print(f"\n{label}  ({len(day_keys)} days)")
    print("-" * 92)
    policies = ["baseline", "be", "partial_be", "partial_atr"]
    for pol in policies:
        all_done = []
        for day in day_keys:
            c = cache[day]
            sigs = detect_signals(c["m5"], h1_fvgs, SL_BUF, TREND_THRESH,
                                  TREND_LB, REQUIRE_FVG, PEAK_LB, TF_MIN)
            if not sigs:
                continue
            all_done.extend(replay(c["ticks"], sigs, LOTS, CONTRACT_XAU,
                                   pol, atr_times, atr_vals))
        r = stats(all_done)
        print(f"  {pol:<12} {fmt(r)}")


def main():
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    atr_times, atr_vals = build_h1_atr(h1, 14)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    cache = {}
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
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}

    days = sorted(cache.keys())
    print("=" * 92)
    print(f"  EXIT-PROTOCOL COMPARISON — deployed S3 signals @ {LOTS} lots — "
          f"{len(days)} real-tick days")
    print(f"  knobs: BE@+{BE_R}R(+${BE_BUFFER})  partial {PARTIAL_FRAC:.0%}@+{PARTIAL_R}R  "
          f"ATR-trail {ATR_MULT}x(H1,14)")
    print("=" * 92)
    if not days:
        print("  NO tick days cached — check shano_ticks_*.csv in Common/Files")
        return

    run(days, cache, h1_fvgs, atr_times, atr_vals, "ALL DAYS")
    mid = len(days) // 2
    run(days[:mid], cache, h1_fvgs, atr_times, atr_vals, "TRAIN (first half)")
    run(days[mid:], cache, h1_fvgs, atr_times, atr_vals, "TEST  (second half / out-of-sample)")


if __name__ == "__main__":
    main()
