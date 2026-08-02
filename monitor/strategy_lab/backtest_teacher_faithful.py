"""backtest_teacher_faithful.py — test the 3 teacher-faithful fixes vs current
deployed configs, on 12 days of real XAU ticks.

Fixes (from re-reading lessons 2, 6-7, 10):
  S1  — breakout candle must be MOMENTUM (big body, small wicks) + LOW volume
        (teacher L2/L4: "breakout with a momentum candle on low volume")
  S3  — green wicking candle must NOT have a big upper wick (rejection);
        also test FVG-required ON (teacher L10: FVG tap = high-probability)
  NSND— trend determined on 1-DAY chart, not intraday (teacher L6: "see trend
        on one day scale")

Each EA: baseline (current live config) vs each fix vs combined.
"""
import csv, sys, glob
from datetime import datetime, timedelta, date
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats,
                                       find_h1_fvgs as find_h1_fvgs_s3)
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import (is_uptrend, is_downtrend, h1_bull_tapped_in,
                                       h1_bear_tapped_in, replay_ticks_both)
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror

CONTRACT = 100.0
PIP = 0.10


# ─────────────────────────────────────────────────────────────────────
# Daily trend helper (for NSND 1-Day fix)
# ─────────────────────────────────────────────────────────────────────
def build_daily(bars):
    """Aggregate M1 -> daily bars."""
    out = {}
    for b in bars:
        d = b["time"].date()
        if d not in out:
            out[d] = {"date": d, "open": b["open"], "high": b["high"],
                      "low": b["low"], "close": b["close"]}
        else:
            x = out[d]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
    return out


def daily_trend_at(daily, on_date, lookback_days=2):
    """Return +1 (up), -1 (down), 0 (flat) using close vs N prior trading days.
    Uses only COMPLETED prior days (strictly before on_date)."""
    days = sorted([d for d in daily if d < on_date])
    if len(days) < lookback_days + 1:
        return 0
    recent = daily[days[-1]]["close"]
    older  = daily[days[-1 - lookback_days]]["close"]
    if recent > older: return +1
    if recent < older: return -1
    return 0


# ─────────────────────────────────────────────────────────────────────
# S1 with teacher's momentum + low-vol breakout filter
# ─────────────────────────────────────────────────────────────────────
def detect_s1_buy_tf(m5, idx, h1_bull, sl_buf, tp_points,
                     retrace_lb=15, require_momentum=False, require_low_vol=False,
                     body_frac=0.6, wick_frac=0.25):
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5, idx): return None
    start = max(0, idx - retrace_lb)
    red_idxs = [j for j in range(start, idx) if m5[j]["close"] < m5[j]["open"]]
    if not red_idxs: return None
    uhv_idx = max(red_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] <= uhv["high"]: return None
    if bo["open"]  >  uhv["high"]: return None
    if not any(m5[j]["low"] < uhv["low"] for j in range(uhv_idx+1, idx+1)):
        return None
    if not h1_bull_tapped_in(h1_bull, m5, range(start, idx+1)):
        return None
    # TEACHER FIX: momentum candle (big body, small wicks)
    rng = bo["high"] - bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"] - bo["open"])
    upper_wick = bo["high"] - max(bo["open"], bo["close"])
    lower_wick = min(bo["open"], bo["close"]) - bo["low"]
    if require_momentum:
        if body / rng < body_frac: return None
        if upper_wick / rng > wick_frac: return None
        if lower_wick / rng > wick_frac: return None
    # TEACHER FIX: low-volume breakout (bo vol < UHV vol)
    if require_low_vol:
        if bo["vol"] >= uhv["vol"]: return None
    entry = bo["close"]; sl = uhv["low"] - sl_buf; tp = entry + tp_points
    return {"fire_time": bo["time"] + timedelta(minutes=5), "side": +1,
            "sl": sl, "tp": tp, "ref_uhv_t": uhv["time"]}


def detect_s1_sell_tf(m5, idx, h1_bear, sl_buf, tp_points,
                      retrace_lb=15, require_momentum=False, require_low_vol=False,
                      body_frac=0.6, wick_frac=0.25):
    bo = m5[idx]
    if bo["close"] >= bo["open"]: return None
    if not is_downtrend(m5, idx): return None
    start = max(0, idx - retrace_lb)
    green_idxs = [j for j in range(start, idx) if m5[j]["close"] > m5[j]["open"]]
    if not green_idxs: return None
    uhv_idx = max(green_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] >= uhv["low"]: return None
    if bo["open"]  <  uhv["low"]: return None
    if not any(m5[j]["high"] > uhv["high"] for j in range(uhv_idx+1, idx+1)):
        return None
    if not h1_bear_tapped_in(h1_bear, m5, range(start, idx+1)):
        return None
    rng = bo["high"] - bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"] - bo["open"])
    upper_wick = bo["high"] - max(bo["open"], bo["close"])
    lower_wick = min(bo["open"], bo["close"]) - bo["low"]
    if require_momentum:
        if body / rng < body_frac: return None
        if upper_wick / rng > wick_frac: return None
        if lower_wick / rng > wick_frac: return None
    if require_low_vol:
        if bo["vol"] >= uhv["vol"]: return None
    entry = bo["close"]; sl = uhv["high"] + sl_buf; tp = entry - tp_points
    return {"fire_time": bo["time"] + timedelta(minutes=5), "side": -1,
            "sl": sl, "tp": tp, "ref_uhv_t": uhv["time"]}


def s1_mirror_tf(m5, h1_bull, h1_bear, sl_buf=2.0, tp_points=7.5,
                 require_momentum=False, require_low_vol=False):
    sigs = []; fired = set()
    for idx in range(30, len(m5)):
        for det, hb in [(detect_s1_buy_tf, h1_bull), (detect_s1_sell_tf, h1_bear)]:
            s = det(m5, idx, hb, sl_buf, tp_points,
                    require_momentum=require_momentum, require_low_vol=require_low_vol)
            if s and s["ref_uhv_t"] not in fired:
                sigs.append(s); fired.add(s["ref_uhv_t"])
    return sigs


# ─────────────────────────────────────────────────────────────────────
# S3 with teacher's upper-wick rejection filter
# ─────────────────────────────────────────────────────────────────────
def s3_filter_upper_wick(m5, sigs, max_upper_wick_frac=0.35):
    """Post-filter S3 signals: drop ones where the wicking green (the bar
    BEFORE fire_time) has a big upper wick (= rejection)."""
    by_time = {b["time"]: b for b in m5}
    kept = []
    for s in sigs:
        bo_t = s["fire_time"] - timedelta(minutes=5)
        bo = by_time.get(bo_t)
        if bo is None:
            kept.append(s); continue
        rng = bo["high"] - bo["low"]
        if rng <= 0:
            kept.append(s); continue
        upper_wick = bo["high"] - max(bo["open"], bo["close"])
        if upper_wick / rng <= max_upper_wick_frac:
            kept.append(s)
    return kept


def run_replay(cache, sigs_by_day, lots=0.10):
    trades = []
    for day, sigs in sigs_by_day.items():
        if not sigs: continue
        done = replay_ticks_both(cache[day]["ticks"], sigs, lots, CONTRACT)
        for d in done:
            if "side" not in d: d["side"] = +1
        trades.extend(done)
    return trades


def rpt(label, trades):
    r = stats(trades)
    if not r:
        print(f"  {label:<48} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<48} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d real-tick dataset...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    h1_bull_s3 = find_h1_fvgs_s3(h1)  # s3 mirror's fvg_tapped_at format (t0/gap_low/gap_high)
    daily = build_daily(bars)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "m15": aggregate_to_tf(db, 15),
                      "bars": db, "ticks": ticks, "date": db[0]["time"].date()}
    print(f"  {len(cache)} days cached\n")

    # ════════════════════════════════════════════════════════════════
    # S1 — momentum + low-vol breakout filter
    # ════════════════════════════════════════════════════════════════
    print("="*84)
    print("  S1 (UHV Breakout) — teacher's momentum + low-vol breakout candle")
    print("="*84)
    for label, mom, lv in [("baseline (current live)", False, False),
                           ("+ momentum candle only",   True,  False),
                           ("+ low-vol breakout only",  False, True),
                           ("+ BOTH (teacher-faithful)", True,  True)]:
        sigs_by_day = {}
        for day, c in cache.items():
            sigs_by_day[day] = s1_mirror_tf(c["m5"], h1_bull, h1_bear,
                                            sl_buf=2.0, tp_points=7.5,
                                            require_momentum=mom, require_low_vol=lv)
        rpt(label, run_replay(cache, sigs_by_day))

    # ════════════════════════════════════════════════════════════════
    # S3 — upper-wick rejection + FVG-on
    # ════════════════════════════════════════════════════════════════
    print()
    print("="*84)
    print("  S3 (Liquidity Sweep) — teacher's upper-wick rejection + FVG-required")
    print("="*84)
    # baseline + variants
    s3_variants = [
        ("baseline (FVG off, no wick filter)", False, None),
        ("+ upper-wick rejection (<=0.35)",     False, 0.35),
        ("+ upper-wick rejection (<=0.20)",     False, 0.20),
        ("+ FVG required (teacher core)",       True,  None),
        ("+ FVG + wick rejection (full)",       True,  0.35),
    ]
    for label, req_fvg, wick in s3_variants:
        sigs_by_day = {}
        for day, c in cache.items():
            sigs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=h1_bull_s3,
                                require_fvg=req_fvg)
            for s in sigs: s["side"] = +1
            if wick is not None:
                sigs = s3_filter_upper_wick(c["m5"], sigs, max_upper_wick_frac=wick)
            sigs_by_day[day] = sigs
        rpt(label, run_replay(cache, sigs_by_day))

    # ════════════════════════════════════════════════════════════════
    # NSND — 1-Day trend filter
    # ════════════════════════════════════════════════════════════════
    print()
    print("="*84)
    print("  NSND (No Supply/Demand) — teacher's 1-DAY trend filter")
    print("="*84)
    # baseline
    def run_nsnd(filter_1d=False, buy_only=False):
        trades = []
        for day, c in cache.items():
            sigs = nsnd_ea_mirror(c["bars"], c["m15"], h1,
                                  vol_min=3, trend_th=2.0, use_hhhl=False)
            if not sigs: continue
            if filter_1d or buy_only:
                d_trend = daily_trend_at(daily, c["date"])
                kept = []
                for s in sigs:
                    side = s.get("side", +1)
                    if buy_only and side != +1:
                        continue
                    if filter_1d:
                        # only take trades aligned with the daily trend
                        if d_trend == +1 and side != +1: continue
                        if d_trend == -1 and side != -1: continue
                        if d_trend == 0: continue   # no clear daily trend -> skip
                    kept.append(s)
                sigs = kept
            if not sigs: continue
            done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
            trades.extend(done)
        return trades
    rpt("baseline (intraday trend, both sides)", run_nsnd(filter_1d=False))
    rpt("+ 1-Day trend alignment filter",         run_nsnd(filter_1d=True))
    rpt("+ buy-only (gold bullish bias)",          run_nsnd(buy_only=True))


if __name__ == "__main__":
    main()
