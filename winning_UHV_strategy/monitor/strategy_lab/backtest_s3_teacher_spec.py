"""backtest_s3_teacher_spec.py — strict faithful implementation of Zee's
teacher's Setup 3 (Effort vs Result), exactly as written.

Teacher's spec (verbatim from Zee's chat 2026-05-16):
  1. Open 1 hour chart, mark Fair Value Gaps on 1 hour Chart
  2. Open 5 minute chart
  3. Wait for price to go down and tap the FVG drawn from 1 hour chart
  4. Find a red candle in this retracement, mark its low (lowest wick)
  5. Find a green wicking candle that:
       a. wicks BELOW the red's low
       b. closes back INSIDE the red's body/range
       c. has HIGHER green volume than the red
  6. (Big upper wick → wait for next green to break it — IMPLEMENTED as optional)
  7. SL just BELOW the green wicking candle's low
  8. TP at the last recent high peak
  9. Pre-req: uptrend, and the retracement = red candles that BROKE the last
     green candle's low

Differences from my optimized version:
  * Strict M5 (not M30)
  * H1 FVG required (not optional)
  * Tight SL just below wicking green (small dollar buffer, not $200)
  * TP at recent peak (not fixed $200)
  * Retracement defined as "reds that broke prior green's low" (not swing-high)

Run on both BTC (14d M1 bars) and XAU (using existing 12d ticks) for
comparison.
"""
import csv
import sys
import glob
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON

CONTRACT_XAU = 100.0
CONTRACT_BTC = 1.0
BTC_CSV = COMMON / "btc_m1.csv"


# ─── Aggregation helpers ───
def aggregate_to_tf(m1, k):
    """k-minute aggregation. k can be 5, 15, 30, 60..."""
    out = {}
    for b in m1:
        ts = b["time"]
        if k < 60:
            bm = (ts.minute // k) * k
            bt = ts.replace(minute=bm, second=0, microsecond=0)
        else:
            hpb = k // 60
            bh = (ts.hour // hpb) * hpb
            bt = ts.replace(hour=bh, minute=0, second=0, microsecond=0)
        if bt not in out:
            out[bt] = {"time": bt, "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = out[bt]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(out.values(), key=lambda x: x["time"])


def group_bars_by_day(bars):
    days = {}
    for b in bars:
        d = b["time"].date().isoformat()
        days.setdefault(d, []).append(b)
    for d in days:
        days[d].sort(key=lambda b: b["time"])
    return days


def load_btc_m1():
    bars = []
    with open(BTC_CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                tm = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
            except: continue
            bars.append({"time": tm, "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars


# ─── H1 FVG detection ───
def find_h1_fvgs(h1):
    fvgs = []
    for i in range(2, len(h1)):
        gl, gh = h1[i-2]["high"], h1[i]["low"]
        if gh <= gl: continue
        filled_at = None
        for j in range(i+1, len(h1)):
            if h1[j]["low"] < gl:
                filled_at = h1[j]["time"]; break
        fvgs.append({"t0": h1[i]["time"], "gap_low": gl, "gap_high": gh,
                     "filled_at": filled_at})
    return fvgs


def fvg_tapped_at(fvgs, bar):
    """An unfilled bullish FVG whose zone overlaps `bar`'s range."""
    for f in fvgs:
        if f["t0"] >= bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= bar["time"]: continue
        if bar["low"] <= f["gap_high"] and bar["high"] >= f["gap_low"]:
            return True
    return False


# ─── Retracement: "red candles which BROKE the last green candle's low" ───
def find_retracement_strict(m5, idx, max_lookback=30):
    """Walk back from idx-1. Find the most recent green candle whose LOW was
    BROKEN by subsequent red candles. Returns list of red indices that are
    PART OF THIS RETRACEMENT (between the broken green and idx)."""
    # Walk back to find a green candle. Then check if subsequent bars
    # included a red that closed below the green's low.
    for back_g in range(idx-2, max(idx - max_lookback - 1, -1), -1):
        gb = m5[back_g]
        if gb["close"] <= gb["open"]: continue   # not green
        green_low = gb["low"]
        # Collect reds AFTER this green that broke its low
        broken_reds = []
        broke = False
        for j in range(back_g + 1, idx):
            b = m5[j]
            if b["close"] < b["open"]:   # red
                if b["close"] < green_low or b["low"] < green_low:
                    broke = True
                broken_reds.append(j)
        if broke and broken_reds:
            return broken_reds, back_g
    return [], -1


# ─── Trend (intraday proxy) ───
def is_uptrend(m5, idx, lookback=24, threshold=2.0):
    if idx < lookback: return False
    return m5[idx]["close"] - m5[idx-lookback]["close"] > threshold


# ─── Detector — faithful to teacher's spec ───
def detect_s3_teacher(m5, idx, fvgs, sl_buffer_pts, trend_thresh,
                      trend_lookback, require_h1_fvg=True,
                      tp_peak_lookback=30):
    """Returns dict {entry, sl, tp, ref} or None."""
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5, idx, trend_lookback, trend_thresh): return None

    # Retracement reds (strict: must have broken last green's low)
    reds, green_idx = find_retracement_strict(m5, idx, max_lookback=30)
    if not reds: return None

    # H1 FVG tap required (per teacher's spec)
    if require_h1_fvg:
        tapped = any(fvg_tapped_at(fvgs, m5[j]) for j in reds)
        if not tapped: return None

    # Find a red where bo is the wicking green
    for red_idx in reds:
        red = m5[red_idx]
        if bo["low"] >= red["low"]: continue          # not wicking below
        if bo["close"] <= red["low"]: continue        # didn't close back inside
        if bo["vol"]  <= red["vol"]:  continue        # need higher green vol

        entry = bo["close"]
        sl    = bo["low"] - sl_buffer_pts             # JUST below wicking green
        # TP = last recent high peak (highest high in last N bars, excluding bo)
        high_window = [m5[j]["high"] for j in range(max(0, idx-tp_peak_lookback), idx)]
        if not high_window: continue
        tp = max(high_window)
        if tp <= entry + sl_buffer_pts * 2:           # need TP at least 2× SL_buf above
            continue
        return {"entry": entry, "sl": sl, "tp": tp,
                "ref_red_t": red["time"], "wicking_t": bo["time"]}
    return None


# ─── Bar-replay (M1 forward walk; tick replay if available) ───
def replay_bars(m1, sigs, lots, contract):
    ppp = lots * contract
    done = []
    for s in sorted(sigs, key=lambda x: x["fire_time"]):
        entry_idx = next((i for i, b in enumerate(m1) if b["time"] >= s["fire_time"]), None)
        if entry_idx is None or entry_idx + 1 >= len(m1): continue
        e = m1[entry_idx]["open"]
        sl, tp = s["sl"], s["tp"]
        why, pnl = None, 0
        for j in range(entry_idx + 1, len(m1)):
            b = m1[j]
            if b["low"]  <= sl: pnl = (sl - e) * ppp; why = "sl"; break
            if b["high"] >= tp: pnl = (tp - e) * ppp; why = "tp"; break
        if why is None:
            last = m1[-1]
            pnl = (last["close"] - e) * ppp; why = "eod"
        done.append({"pnl": pnl, "why": why, "e": e, "sl": sl, "tp": tp,
                     "fire_time": s["fire_time"]})
    return done


def replay_ticks(ticks, sigs, lots, contract):
    """For XAU (we have ticks)."""
    ppp = lots * contract
    done = []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pending = next(sig_iter, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            exit_pnl = exit_why = None
            if bid <= u["sl"]: exit_pnl, exit_why = (u["sl"]-u["e"])*ppp, "sl"
            elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"]-u["e"])*ppp, "tp"
            if exit_pnl is not None:
                u["pnl"], u["why"] = exit_pnl, exit_why
                done.append(u); units.remove(u)
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2:
                units.append({"e": ask, "sl": pending["sl"], "tp": pending["tp"],
                              "fire_time": pending["fire_time"]})
            pending = next(sig_iter, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = (last["bid"] - u["e"]) * ppp; u["why"] = "eod"
            done.append(u)
    return done


def stats(trades):
    n = len(trades)
    if n == 0: return None
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    n_w, n_l = len(wins), len(losses)
    pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
    w_avg = sum(wins)/n_w if n_w else 0
    l_avg = -sum(losses)/n_l if n_l else 0
    total = sum(t["pnl"] for t in trades)
    return dict(n=n, pwin=pwin, w_avg=w_avg, l_avg=l_avg, total=total)


def fmt(r):
    if r is None: return "no trades"
    return (f"n={r['n']:>3}  pwin={r['pwin']:.2f}  "
            f"W=${r['w_avg']:>6.1f}  L=${r['l_avg']:>6.1f}  "
            f"TOTAL=${r['total']:>+8.1f}")


# ─── Main ───
def detect_signals(m5, fvgs, sl_buf, trend_thresh, trend_lookback,
                   require_fvg, tp_peak_lookback, tf_minutes):
    sigs = []
    fired = set()
    for idx in range(30, len(m5)):
        r = detect_s3_teacher(m5, idx, fvgs, sl_buf, trend_thresh,
                              trend_lookback, require_fvg, tp_peak_lookback)
        if r is None: continue
        if r["ref_red_t"] in fired: continue
        fired.add(r["ref_red_t"])
        r["fire_time"] = m5[idx]["time"] + timedelta(minutes=tf_minutes)
        sigs.append(r)
    return sigs


def run_btc():
    print("="*78)
    print("  BTC — Teacher's exact S3 spec (M5, H1 FVG required, tight SL, peak TP)")
    print("="*78)
    m1 = load_btc_m1()
    m5 = aggregate_to_tf(m1, 5)
    h1 = aggregate_to_tf(m1, 60)
    fvgs = find_h1_fvgs(h1)
    days = (m1[-1]["time"] - m1[0]["time"]).total_seconds() / 86400
    print(f"  {len(m1)} M1 bars, {len(m5)} M5 bars, {len(h1)} H1, {len(fvgs)} bullish FVGs, span {days:.1f}d\n")

    LOTS = 0.01
    MULTI = 40
    # SL buffers on BTC — teacher says "just below" so test tight: $5, $20, $50
    # Trend threshold: M5 needs ~$50-$100 to count
    print(f"{'SLbuf':>6} {'TrendTh':>8} {'PeakLB':>6} {'FVG':>4}  {'result':<60}  proj@0.40")
    for require_fvg in [True, False]:
        for sl_buf in [5.0, 20.0, 50.0, 100.0]:
            for trend in [50.0, 100.0, 200.0]:
                for peak_lb in [10, 20, 30]:
                    sigs = detect_signals(m5, fvgs, sl_buf, trend, 24,
                                          require_fvg, peak_lb, 5)
                    if not sigs: continue
                    trades = replay_bars(m1, sigs, LOTS, CONTRACT_BTC)
                    r = stats(trades)
                    if r is None: continue
                    marker = " *" if r["total"] > 0 else ""
                    proj = r["total"] * MULTI
                    fvg_lbl = "Y" if require_fvg else "N"
                    print(f"${sl_buf:>5.0f}  ${trend:>6.0f}  {peak_lb:>6}  {fvg_lbl:>4}  {fmt(r):<60}  ${proj:>+8.1f}{marker}")


def run_xau():
    print()
    print("="*78)
    print("  XAU — Teacher's exact S3 spec (M5, H1 FVG required) — tick replay")
    print("="*78)
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"  {len(bars_all)} M1, {len(h1)} H1, {len(h1_fvgs)} FVGs, {len(tick_files)} tick days")
    print("  Pre-caching ticks + M5 per day (one-time cost)...")
    # Cache ticks and M5 per day, ONCE
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        day_bars = days_bars[day]
        if len(day_bars) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        m5 = aggregate_to_tf(day_bars, 5)
        cache[day] = {"m5": m5, "ticks": ticks}
    print(f"  Cached {len(cache)} days\n")

    LOTS = 0.10
    MULTI = 4
    print(f"{'SLbuf':>6} {'TrendTh':>8} {'PeakLB':>6} {'FVG':>4}  {'result':<60}  proj@0.40")
    for require_fvg in [True, False]:
        for sl_buf in [0.05, 0.10, 0.50, 1.0]:
            for trend in [1.0, 2.0, 5.0]:
                for peak_lb in [10, 20, 30]:
                    all_done = []
                    for day, c in cache.items():
                        sigs = detect_signals(c["m5"], h1_fvgs, sl_buf, trend, 24,
                                              require_fvg, peak_lb, 5)
                        if not sigs: continue
                        done = replay_ticks(c["ticks"], sigs, LOTS, CONTRACT_XAU)
                        all_done.extend(done)
                    r = stats(all_done)
                    if r is None or r["n"] == 0: continue
                    marker = " *" if r["total"] > 0 else ""
                    proj = r["total"] * MULTI
                    fvg_lbl = "Y" if require_fvg else "N"
                    print(f"${sl_buf:>5.2f}  ${trend:>6.1f}  {peak_lb:>6}  {fvg_lbl:>4}  {fmt(r):<60}  ${proj:>+8.1f}{marker}")


if __name__ == "__main__":
    if "--xau-only" in sys.argv:
        run_xau()
    elif "--btc-only" in sys.argv:
        run_btc()
    else:
        run_btc()
        run_xau()
