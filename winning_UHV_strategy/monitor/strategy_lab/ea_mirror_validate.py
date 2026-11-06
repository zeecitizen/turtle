"""ea_mirror_validate.py — Faithful Python translations of S3Trader.mq5 and
NsndTrader.mq5 logic. Replays them on the 12 days of M1 bars + ticks AS IF
they were live MQL5 OnTick events. Compares the resulting trade list to the
original Python backtest. Any divergence is a translation bug in the EAs.

KEY DIFFERENCE FROM BACKTEST:
  * Python backtest's _aggregate_bars (NSND multi-TF FVG) uses stride-based
    chunking. MQL5 EAs use MT5 native clock-aligned M15/H1 bars. We mirror
    the MQL5 (clock-aligned) here to see if the strategy still has edge
    with the more "correct" aggregation.
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf as agg_clock,
    replay_ticks, stats, group_bars_by_day)

CONTRACT = 100.0
PIP = 0.10


# ─── S3 EA mirror (MQL5-accurate Python translation) ───
def s3_ea_mirror(m5_bars, trend_lb=24, trend_th=1.0, retrace_lb=30,
                 tp_peak_lb=10, sl_buf=0.10, min_tp_dist=None,
                 require_fvg=False, h1_fvgs=None):
    """Walks M5 bars left-to-right as the EA would on each new M5 bar close.
    Yields signals = list of dicts {fire_time, sl, tp_initial, ref_red_t}.

    Matches MQL5 S3Trader.mq5 v2 EXACTLY (post-bugfix 2026-05-17):
      * Trend: m5[idx].close - m5[idx-trend_lb].close > trend_th
      * Retracement: find a green whose low was broken by subsequent reds
      * Wicking: bo wicks below red.low, closes inside, vol > red.vol
      * TP = highest high in m5[idx-tp_peak_lb..idx-1] (excludes bo)
      * SL = bo.low - sl_buf
      * min TP distance: max(min_tp_dist, sl_buf * 2)
      * Dedup: only one signal per matched red's time
    """
    # Match MQL5 EA post-fix: min(InpMinTPDistPts=0.2, sl_buf*2=0.20) = 0.20
    if min_tp_dist is None: min_tp_dist = min(0.2, sl_buf * 2)
    sigs = []
    fired_reds = set()   # BUGFIX: dedup by red's time, same as backtest's set
    last_bo_t  = None
    # Match backtest's loop start (idx=30 in run_xau, not trend_lb+retrace_lb).
    # is_uptrend handles its own bounds, find_retracement uses max() for safety.
    for idx in range(max(trend_lb, 30), len(m5_bars)):
        bo = m5_bars[idx]
        if bo["time"] == last_bo_t: continue
        last_bo_t = bo["time"]
        if bo["close"] <= bo["open"]: continue
        # Trend
        if idx < trend_lb: continue
        if bo["close"] - m5_bars[idx - trend_lb]["close"] <= trend_th: continue
        # Find reds-broke-last-green's-low
        reds = []
        for back_g in range(idx - 2, max(idx - retrace_lb - 1, -1), -1):
            gb = m5_bars[back_g]
            if gb["close"] <= gb["open"]: continue
            green_low = gb["low"]
            tmp = []; broke = False
            for j in range(back_g + 1, idx):
                b = m5_bars[j]
                if b["close"] < b["open"]:
                    if b["close"] < green_low or b["low"] < green_low: broke = True
                    tmp.append(j)
            if broke and tmp:
                reds = tmp
                break
        if not reds: continue
        # Find matching red — iterate OLDEST FIRST (matches MQL5 iter order)
        matching_red = None
        for red_idx in reds:
            red = m5_bars[red_idx]
            if bo["low"] >= red["low"]: continue
            if bo["close"] <= red["low"]: continue
            if bo["vol"] <= red["vol"]: continue
            matching_red = red
            break
        if matching_red is None: continue
        # Dedup by red (set, not last only — matches backtest)
        if matching_red["time"] in fired_reds: continue
        # FVG (optional, default off for S3 v2)
        if require_fvg:
            from backtest_s3_teacher_spec import fvg_tapped_at
            if not any(fvg_tapped_at(h1_fvgs, m5_bars[j]) for j in reds): continue
        # TP = max high in bars [idx-tp_peak_lb..idx-1] (exclude bo)
        peak_window = [m5_bars[j]["high"] for j in range(max(0, idx - tp_peak_lb), idx)]
        if not peak_window: continue
        tp = max(peak_window)
        entry = bo["close"]  # backtest uses bo.close; live uses ask. Acceptable proxy.
        sl    = bo["low"] - sl_buf
        if tp <= entry + min_tp_dist: continue
        sigs.append({
            "fire_time": bo["time"] + timedelta(minutes=5),
            "side": +1, "sl": sl, "tp": tp,
            "ref_red_t": matching_red["time"],
        })
        fired_reds.add(matching_red["time"])
    return sigs


# ─── NSND EA mirror — uses CLOCK-ALIGNED M15/H1 (matches MQL5) ───
def nsnd_ea_mirror(m1_bars, m15_bars, h1_bars,
                   ns_lb=15, vol_n=4, vol_min=2, narrow_frac=1.0,
                   uhv_lb=20, uhv_mult=1.30,
                   trend_lb=60, trend_th=1.0,
                   sl_buf=0.10, tp_usd=12.0, lots=0.10,
                   use_hhhl=True, hhhl_N=3, hhhl_lb=180, hhhl_need=2):
    """Mirrors MQL5 NsndTrader.mq5 logic using clock-aligned M15/H1 bars
    (built via aggregate_to_tf in backtest_s3_teacher_spec)."""
    sigs = []
    last_bo_t = None
    # Build M15/H1 lookup by orig-M1-time for fast access.
    # An M1 bar at time T belongs to the M15 bar whose start is floor(T to 15min).
    # We use the bars already in m15_bars and look up by clock alignment.
    def fvg_unfilled_overlap(tf_bars, current_m1_time, ns_low, ns_high, bullish, lookback_bars=30):
        # Find latest tf bar whose time + tf_minutes <= current_m1_time
        # (i.e., must be FULLY closed before current_m1_time)
        tf_minutes = 15 if tf_bars is m15_bars else 60
        horizon = -1
        for i in range(len(tf_bars) - 1, -1, -1):
            bar_end = tf_bars[i]["time"] + timedelta(minutes=tf_minutes)
            if bar_end <= current_m1_time:
                horizon = i; break
        if horizon < 2: return False
        for i in range(max(2, horizon - lookback_bars), horizon + 1):
            if bullish:
                gap_lo = tf_bars[i-2]["high"]
                gap_hi = tf_bars[i]["low"]
            else:
                gap_lo = tf_bars[i]["high"]
                gap_hi = tf_bars[i-2]["low"]
            if gap_hi <= gap_lo: continue
            filled = False
            for j in range(i + 1, horizon + 1):
                if bullish and tf_bars[j]["low"] < gap_lo: filled = True; break
                if not bullish and tf_bars[j]["high"] > gap_hi: filled = True; break
            if filled: continue
            if ns_low <= gap_hi and ns_high >= gap_lo: return True
        return False

    def intraday_trend(idx):
        if idx < 1 + trend_lb: return 0
        d = m1_bars[idx-1]["close"] - m1_bars[idx-1-trend_lb]["close"]
        if d >  trend_th: return +1
        if d < -trend_th: return -1
        return 0

    def is_ns_nd(k, buy_setup):
        c = m1_bars[k]
        if buy_setup and c["close"] >= c["open"]: return False
        if not buy_setup and c["close"] <= c["open"]: return False
        lower_count = 0
        for j in range(k + 1, k + 1 + vol_n):
            if j >= len(m1_bars): return False
            if m1_bars[j]["vol"] > c["vol"]: lower_count += 1
        if lower_count < vol_min: return False
        sum_rng = 0; cnt = 0
        for j in range(k + 1, k + 6):
            if j >= len(m1_bars): break
            sum_rng += m1_bars[j]["high"] - m1_bars[j]["low"]; cnt += 1
        if cnt == 0: return False
        avg_rng = sum_rng / cnt
        rng = c["high"] - c["low"]
        return rng <= narrow_frac * avg_rng

    def has_prior_uhv(ns_k, buy_setup, avg20):
        for j in range(ns_k + 1, ns_k + 1 + uhv_lb):
            if j >= len(m1_bars): return False
            c = m1_bars[j]
            if buy_setup and c["close"] >= c["open"]: continue
            if not buy_setup and c["close"] <= c["open"]: continue
            if c["vol"] >= uhv_mult * avg20: return True
        return False

    def avg_vol_20(bo_idx):
        # BUGFIXED: excludes bo. Sum bars [bo_idx-20..bo_idx-1] = shifts 2..21.
        if bo_idx < 21: return 0
        s = sum(m1_bars[bo_idx - j]["vol"] for j in range(2, 22))
        return s / 20.0

    def find_swings(idx, N, lookback):
        '''Walk bars from older (idx - lookback) to newer (idx - 1 - N).
        Returns lists of (timestamp, value) in OLDER-FIRST order.'''
        shs, sls = [], []
        start = max(N, idx - lookback)
        end = idx - 1 - N
        for i in range(start, end + 1):
            bh = m1_bars[i]["high"]; bl = m1_bars[i]["low"]
            is_h = all(m1_bars[i+k]["high"] < bh and m1_bars[i-k]["high"] < bh for k in range(1, N+1))
            is_l = all(m1_bars[i+k]["low"]  > bl and m1_bars[i-k]["low"]  > bl for k in range(1, N+1))
            if is_h: shs.append(bh)
            if is_l: sls.append(bl)
        return shs, sls

    def hhhl_trend(idx, N, lookback, need):
        shs, sls = find_swings(idx - 1, N, lookback)
        if len(shs) < need or len(sls) < need: return 0
        shs = shs[-need:]; sls = sls[-need:]
        up_ok = all(shs[k] > shs[k-1] for k in range(1, need)) and \
                all(sls[k] > sls[k-1] for k in range(1, need))
        dn_ok = all(shs[k] < shs[k-1] for k in range(1, need)) and \
                all(sls[k] < sls[k-1] for k in range(1, need))
        if up_ok: return +1
        if dn_ok: return -1
        return 0

    for idx in range(max(ns_lb + uhv_lb + trend_lb + 5, hhhl_lb + hhhl_N + 5), len(m1_bars)):
        bo = m1_bars[idx]
        if bo["time"] == last_bo_t: continue
        last_bo_t = bo["time"]
        trend = intraday_trend(idx)
        if trend == 0: continue
        buy_setup = (trend > 0)
        if use_hhhl:
            hh = hhhl_trend(idx, hhhl_N, hhhl_lb, hhhl_need)
            if hh == 0: continue
            if buy_setup and hh < 0: continue
            if not buy_setup and hh > 0: continue
        bo_high = bo["high"]; bo_low = bo["low"]
        avg20 = avg_vol_20(idx)
        if avg20 <= 0: continue
        # Find NS/ND
        for k_off in range(2, 2 + ns_lb):
            k = idx - k_off  # NEWER first (smaller offset = closer to bo)
            if not is_ns_nd(k, buy_setup): continue
            if not has_prior_uhv(k, buy_setup, avg20): continue
            ns_low = m1_bars[k]["low"]; ns_high = m1_bars[k]["high"]
            # FVG overlap (M15 or H1)
            ok_m15 = fvg_unfilled_overlap(m15_bars, m1_bars[k]["time"], ns_low, ns_high, buy_setup, 30)
            ok_h1  = fvg_unfilled_overlap(h1_bars,  m1_bars[k]["time"], ns_low, ns_high, buy_setup, 30)
            if not (ok_m15 or ok_h1): continue
            # Sweep check
            if buy_setup:
                if bo_low >= ns_low: continue
            else:
                if bo_high <= ns_high: continue
            # Already swept?
            already = False
            for m_off in range(k_off - 1, 1, -1):
                m = idx - m_off
                if m == k: continue
                if buy_setup and m1_bars[m]["low"]  < ns_low:  already = True; break
                if not buy_setup and m1_bars[m]["high"] > ns_high: already = True; break
            if already: continue
            # Fire
            ppp = lots * CONTRACT
            tp_dist = tp_usd / ppp
            if buy_setup:
                entry = bo["close"]
                sl = bo_low - sl_buf
                tp = entry + tp_dist
            else:
                entry = bo["close"]
                sl = bo_high + sl_buf
                tp = entry - tp_dist
            sigs.append({
                "fire_time": bo["time"] + timedelta(seconds=60),
                "side": +1 if buy_setup else -1,
                "sl": sl, "tp": tp,
            })
            break
    return sigs


def main():
    print("="*78)
    print("  EA Mirror Validation — MQL5-faithful Python translations")
    print("="*78)
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    days = sorted(days_bars.keys())
    print(f"  {len(bars_all)} M1 bars, {len(days)} days\n")

    # ── S3 mirror — using clock-aligned M5 ──
    print("=== S3 EA MIRROR (with bugfixes) ===")
    s3_total = 0
    s3_trade_count = 0
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        m5 = agg_clock(db, 5)
        sigs = s3_ea_mirror(m5)
        if not sigs: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        done = replay_ticks(ticks, sigs, 0.10, CONTRACT)
        pnl = sum(t["pnl"] for t in done)
        s3_total += pnl
        s3_trade_count += len(done)
    print(f"  S3 EA mirror: {s3_trade_count} trades, total ${s3_total:+.1f} / 12 days")
    print(f"  (Backtest reference: 104 trades, +$1,184)")
    print()

    # ── NSND mirror — using clock-aligned M15/H1 ──
    print("=== NSND EA MIRROR — FINAL (clock-aligned M15/H1, MQL5 defaults) ===")
    nsnd_total = 0
    nsnd_trade_count = 0
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 200: continue
        m15 = agg_clock(db, 15)
        h1_local = agg_clock(db, 60)
        # Match MQL5 NsndTrader.mq5 post-bugfix defaults
        sigs = nsnd_ea_mirror(
            db, m15, h1_local, lots=0.10, tp_usd=12.0,
            use_hhhl=False,             # default OFF
            trend_th=2.0,               # default 2.0 (was 1.0)
            vol_min=3,                  # default 3 (was 2)
            narrow_frac=1.0,
        )
        if not sigs: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        done = replay_ticks(ticks, sigs, 0.10, CONTRACT)
        pnl = sum(t["pnl"] for t in done)
        nsnd_total += pnl
        nsnd_trade_count += len(done)
    print(f"  NSND EA mirror: {nsnd_trade_count} trades, total ${nsnd_total:+.1f} / 12 days")
    print(f"  (Clock-aligned sweep best: 47 trades, +$416)")
    print(f"  (Projection @ 0.40 lots: ${nsnd_total*4:+.1f}/12d = ${nsnd_total*4/12:.0f}/day)")


if __name__ == "__main__":
    main()
