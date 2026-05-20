"""build_feb11_lab.py — generate the Feb 11 visualization page.

Step 1 (this build): TradingView-clone chart using lightweight-charts
(TradingView's own open-source chart engine — so the look IS identical).
M1 candles for 2026-02-11 sourced from rev_eng_m1.csv, which holds the
broker's aggregated minute OHLC for that day. Tick CSVs start Apr 29 so
Feb 11 cannot be tick-driven; M1 OHLC from the broker is the best truth
available for that date.

Next steps (separate commits):
  • overlay Zee's actual entry/exit markers
  • overlay v3.49 detector signals
  • stats + equity curve panel
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# CRITICAL: parse broker-time strings as if they were UTC so the unix values
# we emit match what lightweight-charts (UTC default) will display. Otherwise
# Python's local TZ shifts everything and creates mismatches between the
# chart's X-axis labels and our marker text.
UTC = timezone.utc

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import detect_on_bar, MAX_LOOKBACK

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1_CSV = COMMON / "rev_eng_m1.csv"
OUT_HTML = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\dashboard\claude_trader\feb11_lab.html")
TARGET_DATE = "2026.02.11"

# Zee's COMPLETE Feb 11 broker history (account 5118408, BlueberryMarkets-Live02).
# 69 trades, 65W/4L = +$835.06 — from the Trade History Report PDF.
# Format: (open_hms, side, entry_price, close_hms, close_price, pnl)
ZEE_TRADES = [
    ("01:32:19", "buy",  5045.07, "01:47:30", 5045.94,   7.32),
    ("01:32:20", "buy",  5045.02, "01:47:30", 5045.94,   7.74),
    ("01:59:04", "buy",  5042.17, "02:00:43", 5042.96,   6.65),
    ("01:59:04", "buy",  5042.17, "02:00:43", 5042.96,   6.65),
    ("02:09:38", "sell", 5040.68, "02:10:18", 5039.29,  11.69),
    ("02:09:39", "sell", 5040.61, "02:10:18", 5039.25,  11.44),
    ("02:29:02", "buy",  5039.03, "02:30:28", 5041.41,  20.01),
    ("02:29:02", "buy",  5039.03, "02:30:28", 5041.41,  20.01),
    ("16:49:07", "buy",  5047.93, "16:51:03", 5049.96,  17.12),
    ("16:49:07", "buy",  5047.90, "16:51:03", 5049.85,  16.45),
    ("16:49:07", "buy",  5047.24, "16:51:03", 5049.96,  22.95),
    ("16:52:21", "buy",  5050.77, "16:52:27", 5051.82,   8.85),
    ("16:54:10", "buy",  5056.74, "16:54:20", 5057.72,   8.26),
    ("16:54:10", "buy",  5056.59, "16:54:20", 5057.71,   9.44),
    ("16:58:03", "buy",  5064.26, "16:58:27", 5064.94,   5.73),
    ("16:58:03", "buy",  5064.31, "16:58:27", 5064.93,   5.23),
    ("16:58:03", "buy",  5064.29, "16:58:27", 5064.94,   5.48),
    ("17:02:45", "buy",  5055.71, "17:03:51", 5062.23,  54.93),
    ("17:02:46", "buy",  5056.24, "17:03:51", 5062.23,  50.47),
    ("17:02:47", "buy",  5056.52, "17:03:51", 5062.23,  48.11),
    ("17:36:11", "buy",  5056.53, "17:36:26", 5056.92,   3.29),
    ("17:36:11", "buy",  5056.53, "17:36:26", 5056.92,   3.29),
    ("17:36:13", "buy",  5057.05, "17:52:56", 5058.77,  14.50),
    ("17:37:26", "buy",  5045.82, "17:40:02", 5046.66,   7.08),
    ("17:37:27", "buy",  5045.33, "17:40:02", 5046.66,  11.22),
    ("17:49:59", "buy",  5048.32, "17:52:33", 5054.58,  52.78),
    ("17:49:59", "buy",  5048.37, "17:52:33", 5054.57,  52.27),
    ("17:49:59", "buy",  5048.38, "17:52:33", 5054.56,  52.10),
    ("18:24:18", "buy",  5059.26, "18:28:33", 5060.27,   8.51),
    ("18:24:19", "buy",  5059.39, "18:28:33", 5060.27,   7.42),
    ("18:24:19", "buy",  5059.42, "18:28:33", 5060.27,   7.16),
    ("18:41:50", "buy",  5078.10, "19:06:41", 5077.93,  -1.43),
    ("18:41:50", "buy",  5078.12, "19:06:41", 5077.93,  -1.60),
    ("18:41:50", "buy",  5078.11, "19:06:41", 5077.93,  -1.51),
    ("18:41:51", "buy",  5078.02, "19:06:41", 5077.93,  -0.76),
    ("18:41:51", "buy",  5077.91, "19:06:41", 5077.93,   0.17),
    ("18:41:51", "buy",  5077.91, "19:06:41", 5077.93,   0.17),
    ("19:08:59", "sell", 5083.28, "19:09:08", 5082.35,   7.82),
    ("19:08:59", "sell", 5083.24, "19:09:08", 5082.35,   7.49),
    ("19:08:59", "sell", 5083.16, "19:09:08", 5082.35,   6.82),
    ("19:08:59", "sell", 5083.17, "19:09:08", 5082.29,   7.40),
    ("19:11:05", "sell", 5083.39, "19:11:27", 5083.02,   3.11),
    ("19:11:05", "sell", 5083.31, "19:11:27", 5083.02,   2.44),
    ("19:11:06", "sell", 5083.30, "19:11:27", 5083.02,   2.36),
    ("19:11:51", "sell", 5083.79, "19:19:10", 5081.77,  16.99),
    ("19:11:51", "sell", 5083.79, "19:19:10", 5081.77,  16.99),
    ("19:11:52", "sell", 5083.75, "19:19:10", 5081.77,  16.66),
    ("19:11:52", "sell", 5083.75, "19:19:10", 5081.77,  16.66),
    ("19:20:34", "sell", 5084.21, "19:20:40", 5082.52,  14.21),
    ("19:20:34", "sell", 5084.24, "19:20:40", 5082.52,  14.47),
    ("19:20:34", "sell", 5084.21, "19:20:40", 5082.52,  14.21),
    ("19:20:35", "sell", 5084.15, "19:20:40", 5082.52,  13.71),
    ("19:26:06", "sell", 5089.16, "19:26:50", 5087.43,  14.55),
    ("19:26:06", "sell", 5089.38, "19:26:50", 5087.43,  16.40),
    ("19:26:06", "sell", 5089.41, "19:26:50", 5087.43,  16.65),
    ("19:29:31", "buy",  5086.34, "19:39:03", 5086.44,   0.84),
    ("19:29:31", "buy",  5086.34, "19:39:03", 5086.44,   0.84),
    ("19:29:32", "buy",  5086.34, "19:39:03", 5086.44,   0.84),
    ("19:32:48", "buy",  5084.71, "19:37:34", 5085.41,   5.89),
    ("19:32:48", "buy",  5084.83, "19:37:34", 5085.41,   4.88),
    ("19:36:19", "buy",  5082.91, "19:37:19", 5084.17,  10.60),
    ("19:36:19", "buy",  5082.93, "19:37:19", 5084.17,  10.43),
    ("19:38:39", "buy",  5083.28, "19:38:50", 5084.59,  11.02),
    ("19:38:59", "buy",  5086.33, "19:39:03", 5086.44,   0.92),
    ("19:38:59", "buy",  5086.29, "19:39:03", 5086.44,   1.26),
    ("19:41:59", "sell", 5091.09, "19:42:54", 5090.93,   1.35),
    ("19:41:59", "sell", 5091.09, "19:42:54", 5090.94,   1.26),
    ("19:42:26", "sell", 5093.18, "19:42:40", 5092.05,   9.50),
    ("19:42:27", "sell", 5092.97, "19:42:40", 5092.09,   7.40),
]


def build_zee_markers():
    """Per minute, aggregate Zee's trades into ONE marker (lightweight-charts
    only supports ONE marker per time on a series). Same-minute trades
    summed into a single label like '3× BUY (+$24)' or 'BUY (+$7)'."""
    by_open  = {}   # minute → list of (is_buy, pnl)
    by_close = {}   # minute → list of pnl (for exit dots)
    for (open_hms, side, entry, close_hms, close_price, pnl) in ZEE_TRADES:
        t_o = (datetime.strptime(f"2026.02.11 {open_hms}",  "%Y.%m.%d %H:%M:%S")
               .replace(second=0, tzinfo=UTC))
        t_c = (datetime.strptime(f"2026.02.11 {close_hms}", "%Y.%m.%d %H:%M:%S")
               .replace(second=0, tzinfo=UTC))
        by_open.setdefault(int(t_o.timestamp()), []).append((side, pnl))
        by_close.setdefault(int(t_c.timestamp()), []).append(pnl)

    markers = []
    # entry markers
    for ts, trades in by_open.items():
        sides = set(t[0] for t in trades)
        n = len(trades)
        net = sum(t[1] for t in trades)
        if "buy" in sides and "sell" not in sides:
            shape, pos, label = "arrowUp", "belowBar", "BUY"
        elif "sell" in sides and "buy" not in sides:
            shape, pos, label = "arrowDown", "aboveBar", "SELL"
        else:
            shape, pos, label = "square", "inBar", "MIXED"
        text = label if n == 1 else f"{n}× {label}"
        markers.append({"time": ts, "position": pos, "color": "#3179f5",
                        "shape": shape, "text": text})
    # exit markers (aggregate P&L for that minute)
    for ts, pnls in by_close.items():
        net = sum(pnls)
        is_win = net > 0
        sign = "+" if is_win else ""
        n = len(pnls)
        text = f"{sign}${net:.2f}" if n == 1 else f"{n}× {sign}${net:.2f}"
        markers.append({"time": ts, "position": "aboveBar",
                        "color": "#26a69a" if is_win else "#ef5350",
                        "shape": "circle", "text": text})
    markers.sort(key=lambda m: m["time"])
    return markers


def detect_with_uhv_time(bars, idx_bo, lookback_floor_time=None):
    """Detector with FIVE quality rules (Zee's catches 2026-05-15):

      A. BROKEN-ZONE SELECTION — find the max-vol opposite-color
         candle (red for buy, green for sell) in the lookback whose
         high (or low) is already CROSSED by the breakout's close.
         This naturally bounds the "retracement" to bars the breakout
         actually clears, so we don't try to compare against an
         older un-cleared high.

      B. LOCAL-PEAK UHV — the chosen UHV must be a true local volume
         peak: vol > prev_bar.vol AND vol > next_bar.vol (regardless
         of color). Without this, the detector picks "fake UHVs" like
         Feb 11 23:47 (v=139) when 23:46 right next to it has v=277.
         If the candidate isn't a local peak, NO signal — we do NOT
         fall back to a smaller-volume candidate.

      C. FRESH-BREAKOUT — bo.open <= uhv.high  AND  bo.close > uhv.high
         (buy; symmetric for sell). The breakout transitions THROUGH
         the UHV level rather than continuing past it.

      D. UHV > BREAKOUT VOLUME — bo.vol < uhv.vol. If the breakout
         out-volumes the UHV candidate, the breakout itself is the
         high-volume bar, not the candidate.

      E. NEW-UHV (one UHV per retracement) — enforced by the caller
         via NEW-UHV post-selection cutoff (uhv_time > last_bo_<side>_t).

    Returns (side, uhv_time, uhv_h, uhv_l) or None.
    """
    bo = bars[idx_bo]
    if bo["close"] > bo["open"]:                                 # green → buy
        ui, uv = -1, -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if lookback_floor_time is not None and c["time"] <= lookback_floor_time:
                break
            if c["high"] >= bo["close"]:                continue      # high not yet cleared
            if c["close"] < c["open"] and c["vol"] > uv:
                ui, uv = k, c["vol"]
        if ui < 0:                                              return None
        # B. local-peak check (prev/next neighbors, regardless of color)
        prev_v = bars[ui - 1]["vol"] if ui - 1 >= 0           else -1
        next_v = bars[ui + 1]["vol"] if ui + 1 < len(bars)    else -1
        if not (uv > prev_v and uv > next_v):                   return None
        uhv = bars[ui]
        if bo["close"] <= uhv["high"]:                          return None
        if bo["open"]  >  uhv["high"]:                          return None
        if bo["vol"]   >= uhv["vol"]:                           return None
        # F. BREAKOUT NOT VOLUME-MINIMUM: the breakout bar cannot have
        # BOTH neighbors with higher volume (i.e., it can't be a strict
        # local volume minimum). Feb 11 23:25 sell was the exemplar —
        # vol=103 sandwiched between prev 23:24 vol=115 and next 23:26
        # vol=131, with even bigger 23:27-29 (258/192/322) after — the
        # real sell move was downstream, not at 23:25. By contrast
        # 23:15 buy (vol=54) is OK because next 23:16 vol=41 (lower);
        # and 23:51 buy (vol=104) is OK because prev 23:50 vol=87
        # (lower). The breakout can be small as long as it's not
        # bracketed by larger bars on BOTH sides.
        prev_b = bars[idx_bo - 1]["vol"] if idx_bo - 1 >= 0          else -1
        next_b = bars[idx_bo + 1]["vol"] if idx_bo + 1 < len(bars)   else -1
        if bo["vol"] < prev_b and bo["vol"] < next_b:
            return None
        return (+1, uhv["time"], uhv["high"], uhv["low"])
    if bo["close"] < bo["open"]:                                 # red → sell
        ui, uv = -1, -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if lookback_floor_time is not None and c["time"] <= lookback_floor_time:
                break
            if c["low"] <= bo["close"]:                  continue      # low not yet cleared
            if c["close"] > c["open"] and c["vol"] > uv:
                ui, uv = k, c["vol"]
        if ui < 0:                                              return None
        prev_v = bars[ui - 1]["vol"] if ui - 1 >= 0           else -1
        next_v = bars[ui + 1]["vol"] if ui + 1 < len(bars)    else -1
        if not (uv > prev_v and uv > next_v):                   return None
        uhv = bars[ui]
        if bo["close"] >= uhv["low"]:                           return None
        if bo["open"]  <  uhv["low"]:                           return None
        if bo["vol"]   >= uhv["vol"]:                           return None
        if idx_bo - 1 >= 0 and bo["vol"] <= bars[idx_bo - 1]["vol"]:
            return None
        return (-1, uhv["time"], uhv["high"], uhv["low"])
    return None


def _trend_dir(bars, idx, lookback=60, threshold=1.0):
    """Proxy for 'daily trend' on intraday data: compare current close
    to the close `lookback` bars ago (default 1 hour). Returns +1/-1/0."""
    if idx < lookback: return 0
    delta = bars[idx]["close"] - bars[idx - lookback]["close"]
    if delta >  threshold: return +1
    if delta < -threshold: return -1
    return 0


# Module-level cache for aggregated bars (keyed by id(bars), k, len(bars))
# Aggregations are pure-functional given the input bars, so this is safe.
_AGG_CACHE = {}


def _aggregate_bars(bars, k):
    """Aggregate consecutive bars into stride-k bars. Returns (agg, agg_end)
    where agg_end[i] = last orig-bar index contained in agg[i]. Cached by
    id(bars) so we don't re-aggregate on every detector call."""
    key = (id(bars), k, len(bars))
    if key in _AGG_CACHE:
        return _AGG_CACHE[key]
    agg = []
    agg_end = []
    for start in range(0, len(bars), k):
        chunk = bars[start:start + k]
        if not chunk: continue
        agg.append({
            "high": max(b["high"] for b in chunk),
            "low":  min(b["low"]  for b in chunk),
        })
        agg_end.append(min(start + k, len(bars)) - 1)
    _AGG_CACHE[key] = (agg, agg_end)
    return agg, agg_end


def _fvg_visible_at_tf(agg, agg_end, current_idx, price_low, price_high,
                       is_bullish, lookback_agg=30, min_prior_taps=0):
    """Check for an unfilled FVG visible at orig-idx `current_idx`, on the
    given aggregated timeframe. An FVG is 'visible' only if its 3rd bar's
    LAST orig-idx is strictly less than current_idx (no lookahead).

    Overlap check: FVG zone intersects [price_low, price_high].

    min_prior_taps: if > 0, the FVG must have been tapped at least this many
    times BEFORE the current bar (excluding the current bar's overlap as a
    tap). A 'tap' = an agg bar between FVG formation and now whose range
    intersected the FVG zone; distinct taps must be separated by at least
    one non-intersecting bar. Set to 1 for 'second-tap-only' entries."""
    horizon = -1
    for i in range(len(agg) - 1, -1, -1):
        if agg_end[i] < current_idx:
            horizon = i; break
    if horizon < 2: return False
    for i in range(max(2, horizon - lookback_agg), horizon + 1):
        if is_bullish:
            gap_low, gap_high = agg[i - 2]["high"], agg[i]["low"]
        else:
            gap_low, gap_high = agg[i]["high"], agg[i - 2]["low"]
        if gap_high <= gap_low: continue
        # Unfilled?
        filled = False
        for j in range(i + 1, horizon + 1):
            if is_bullish and agg[j]["low"] < gap_low:  filled = True; break
            if not is_bullish and agg[j]["high"] > gap_high: filled = True; break
        if filled: continue
        # Current bar overlap?
        if not (price_low <= gap_high and price_high >= gap_low): continue
        # Prior-tap count requirement?
        if min_prior_taps > 0:
            taps, in_zone = 0, False
            for j in range(i + 1, horizon + 1):
                is_in = (agg[j]["low"] <= gap_high) and (agg[j]["high"] >= gap_low)
                if is_in and not in_zone:
                    taps += 1; in_zone = True
                elif not is_in:
                    in_zone = False
            if taps < min_prior_taps: continue
        return True
    return False


def _has_unfilled_bullish_fvg_overlap(bars, idx, ns_low, ns_high, lookback=30,
                                       timeframes=(1, 5, 15, 60),
                                       min_prior_taps=0):
    """Bullish FVG at ANY of the given timeframes overlapping [ns_low, ns_high].
    min_prior_taps=1 → require at least one prior tap of this FVG (second-tap entry)."""
    for k in timeframes:
        agg, agg_end = _aggregate_bars(bars, k)
        if _fvg_visible_at_tf(agg, agg_end, idx, ns_low, ns_high,
                              is_bullish=True, lookback_agg=lookback,
                              min_prior_taps=min_prior_taps):
            return True
    return False


def _has_unfilled_bearish_fvg_overlap(bars, idx, nd_low, nd_high, lookback=30,
                                       timeframes=(1, 5, 15, 60),
                                       min_prior_taps=0):
    for k in timeframes:
        agg, agg_end = _aggregate_bars(bars, k)
        if _fvg_visible_at_tf(agg, agg_end, idx, nd_low, nd_high,
                              is_bullish=False, lookback_agg=lookback,
                              min_prior_taps=min_prior_taps):
            return True
    return False


def detect_ns_nd_pattern(bars, idx_bo,
                         ns_lookback=15,        # search NS within this many bars before bo
                         vol_compare_n=4,       # NS vol must be < at least 2 of prev N bars
                         vol_compare_min=2,     # minimum number of prev bars NS must undercut
                         narrow_range_frac=1.0, # NS range must be < this × avg-range-of-prev-5
                         uhv_lookback=20,       # UHV must exist within this many bars before NS
                         uhv_vol_mult=1.30,     # UHV vol must be > this × avg-20 vol
                         require_fvg=True,      # NS bar must overlap an unfilled FVG of right direction
                         require_trend=True,    # only NS in uptrend, only ND in downtrend
                         trend_lookback=60,     # 1-hour proxy for daily trend
                         fvg_timeframes=(1, 5, 15, 60),  # FVG checked at these strides
                         fvg_min_prior_taps=0):           # 1 = require second-tap entry
    """VSA No-Supply / No-Demand detector — per Zee's lectures + his own
    written definition (2026-05-15 chat):

      1. DIRECTION:
         NS (buy) = up candle (close > open) is wrong here — Zee
         clarified NS is the SAME DIRECTION as the prior move it's
         decaying. Actually his lecture says NS = small RED candle in
         an uptrend retracement. ND = small GREEN candle in a downtrend
         retracement. (I.e., NS is opposite to the trade you're about
         to take.) Keeping that.

         > Update: re-reading Zee's chat: 'It is an up candle (the
         close is higher than the open)' — Zee is describing ND, the
         SELL setup. So ND = green candle, NS = red candle (symmetric).

      2. NARROW SPREAD — high-low range is unusually small vs recent.

      3. VOLUME — visibly lower than the previous 2 or more candles
         (not "below absolute average" — RELATIVE to the immediate
         prior bars).

    Entry trigger (Zee's actual style, 19:08 sell on 19:07 ND):
      • Wait for the NS/ND to be SWEPT by a subsequent candle
        (wick goes past NS.low for NS, or past ND.high for ND).
      • Enter on the SWEEP, before a confirmed close-past-range break.
      • That's why 19:08 sold at the upper wick top (5083.28), not
        after a close below 19:07's low — the sweep itself is the
        trigger when momentum is exhausted.

    Returns (side, pattern_idx, trigger_idx). pattern_idx is the
    NS/ND bar; trigger_idx is the sweeping bar.
    """
    if idx_bo < ns_lookback + vol_compare_n + 2: return None

    def is_ns_nd_candle(k, is_buy_setup):
        c = bars[k]
        if is_buy_setup:
            if c["close"] >= c["open"]: return False     # NS = red
        else:
            if c["close"] <= c["open"]: return False     # ND = green
        # Volume: lower than at least vol_compare_min of prev vol_compare_n
        lower_count = sum(1 for j in range(k - vol_compare_n, k) if j >= 0 and bars[j]["vol"] > c["vol"])
        if lower_count < vol_compare_min: return False
        # Narrow spread: range < narrow_range_frac × avg-range of prev 5
        prev5_ranges = [bars[j]["high"] - bars[j]["low"] for j in range(max(0, k-5), k)]
        if not prev5_ranges: return False
        avg_rng = sum(prev5_ranges) / len(prev5_ranges)
        rng = c["high"] - c["low"]
        if rng > narrow_range_frac * avg_rng: return False
        return True

    # avg vol over prev 20 (for UHV multiplier reference)
    window_vols = [b["vol"] for b in bars[max(0, idx_bo - 20):idx_bo]]
    avg_vol = sum(window_vols) / len(window_vols) if window_vols else 0

    def has_prior_uhv(ns_idx, is_buy_setup):
        # Buy setup: prior UHV = big RED vol bar (supply exhaustion).
        # Sell setup: prior UHV = big GREEN vol bar (demand exhaustion).
        for j in range(ns_idx - 1, max(ns_idx - uhv_lookback - 1, -1), -1):
            c = bars[j]
            if is_buy_setup:
                if c["close"] >= c["open"]: continue       # red only
            else:
                if c["close"] <= c["open"]: continue       # green only
            if c["vol"] >= uhv_vol_mult * avg_vol:
                return True
        return False

    bo = bars[idx_bo]
    trend = _trend_dir(bars, idx_bo, lookback=trend_lookback) if require_trend else 0

    # ---- BUY (No Supply): bo is sweeping a recent NS's low ----
    if not require_trend or trend >= 0:
        for k in range(idx_bo - 1, max(idx_bo - ns_lookback - 1, -1), -1):
            ns = bars[k]
            if not is_ns_nd_candle(k, is_buy_setup=True):  continue
            if not has_prior_uhv(k, is_buy_setup=True):    continue
            if require_fvg and not _has_unfilled_bullish_fvg_overlap(
                bars, k, ns["low"], ns["high"], timeframes=fvg_timeframes,
                min_prior_taps=fvg_min_prior_taps): continue
            if bo["low"] >= ns["low"]:                     continue
            already = any(bars[m]["low"] < ns["low"] for m in range(k + 1, idx_bo))
            if already: continue
            return (+1, k, idx_bo)

    # ---- SELL (No Demand): bo is sweeping a recent ND's high ----
    if not require_trend or trend <= 0:
        for k in range(idx_bo - 1, max(idx_bo - ns_lookback - 1, -1), -1):
            nd = bars[k]
            if not is_ns_nd_candle(k, is_buy_setup=False): continue
            if not has_prior_uhv(k, is_buy_setup=False):   continue
            if require_fvg and not _has_unfilled_bearish_fvg_overlap(
                bars, k, nd["low"], nd["high"], timeframes=fvg_timeframes,
                min_prior_taps=fvg_min_prior_taps): continue
            if bo["high"] <= nd["high"]:                   continue
            already = any(bars[m]["high"] > nd["high"] for m in range(k + 1, idx_bo))
            if already: continue
            return (-1, k, idx_bo)

    return None


def run_ns_nd_detector(bars):
    """Walk Feb 11 M1 bars; emit one signal per NS/ND break (deduped so
    the same NS/ND isn't re-fired on subsequent bars)."""
    signals = []
    fired_ns_idx = set()
    for i in range(len(bars)):
        r = detect_ns_nd_pattern(bars, i)
        if r is None: continue
        side, ns_idx, uhv_idx = r
        if ns_idx in fired_ns_idx: continue
        fired_ns_idx.add(ns_idx)
        signals.append({
            "time":     bars[i]["time"],
            "side":     side,
            "ns_time":  bars[ns_idx]["time"],
            "ns_h":     bars[ns_idx]["high"],
            "ns_l":     bars[ns_idx]["low"],
            "uhv_time": bars[uhv_idx]["time"],
            "uhv_h":    bars[uhv_idx]["high"],
            "uhv_l":    bars[uhv_idx]["low"],
        })
    return signals


def build_ns_nd_markers(ns_nd_signals):
    """Three markers per NS/ND signal:
      • Break candle — arrow, with text "NS HH:MM" or "ND HH:MM"
      • NS/ND candle — small cyan/magenta dot tagged "NS" or "ND"
      • UHV candle — amber dot tagged "UHV" (deduplicated)
    """
    markers = []
    seen_ns, seen_uhv = set(), set()
    for s in ns_nd_signals:
        is_buy = s["side"] > 0
        ns_label = datetime.fromtimestamp(s["ns_time"], tz=UTC).strftime("%H:%M")
        markers.append({
            "time": s["time"],
            "position": "belowBar" if is_buy else "aboveBar",
            "color":    "#00bcd4" if is_buy else "#e91e63",   # cyan for NS-buy, magenta for ND-sell
            "shape":    "arrowUp" if is_buy else "arrowDown",
            "text":     ("NS " if is_buy else "ND ") + ns_label,
        })
        ns_key = (s["ns_time"], is_buy)
        if ns_key not in seen_ns:
            seen_ns.add(ns_key)
            markers.append({
                "time":     s["ns_time"],
                "position": "aboveBar" if is_buy else "belowBar",
                "color":    "#00bcd4" if is_buy else "#e91e63",
                "shape":    "circle",
                "text":     "NS" if is_buy else "ND",
            })
        uhv_key = (s["uhv_time"], is_buy)
        if uhv_key not in seen_uhv:
            seen_uhv.add(uhv_key)
            markers.append({
                "time":     s["uhv_time"],
                "position": "aboveBar" if is_buy else "belowBar",
                "color":    "#ffb74d",
                "shape":    "circle",
                "text":     "UHV",
            })
    return markers


def ns_nd_alignment(ns_nd_signals):
    """For each Zee entry minute, was there a NS/ND signal within ±5 min of same side?
    Wider window because Zee often enters BEFORE the confirmed break (anticipating
    the NS/ND setup) or pyramids — multiple entries on the same setup over 3-5 min."""
    WINDOW = 5 * 60
    matched = 0
    for (open_hms, side, *_) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        for s in ns_nd_signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= WINDOW:
                matched += 1
                break
    return {
        "n_det":   len(ns_nd_signals),
        "n_zee":   len(ZEE_TRADES),
        "matched": matched,
        "missed":  len(ZEE_TRADES) - matched,
    }


def run_detector_on_feb11(bars):
    """Walk Feb 11 M1 bars; for each minute the detector fires, record the
    breakout candle and the matched UHV candle's time.

    Bounds the detector's selection window by `last_bo_<side>_t` so the
    UHV chosen is THE biggest red bar of THIS retracement (the bars
    strictly after the prior same-side breakout). Combined with the
    detector's no-fall-back selection rule, this means a single
    retracement has exactly one UHV — and if the breakout candle
    doesn't actually clear that UHV's high, there's no signal at all
    (no falling back to a smaller, closer red bar)."""
    signals = []
    last_bo_buy_t = None       # unix time of last buy breakout candle
    last_bo_sell_t = None
    for i, b in enumerate(bars):
        if i < MAX_LOOKBACK + 2: continue
        # For buy detection, the buy retracement starts after last buy breakout.
        # We pass the floor to detect_with_uhv_time; for sell candles the buy
        # floor is irrelevant (detector picks side based on bo color anyway).
        floor = last_bo_buy_t if b["close"] > b["open"] else last_bo_sell_t
        r = detect_with_uhv_time(bars, i, floor)
        if r is None: continue
        side, uhv_time, uhv_h, uhv_l = r
        if side > 0: last_bo_buy_t  = b["time"]
        else:        last_bo_sell_t = b["time"]
        signals.append({
            "time": b["time"], "side": side,
            "uhv_time": uhv_time, "uhv_h": uhv_h, "uhv_l": uhv_l,
        })
    return signals


def build_detector_markers(detector_signals):
    """Two markers per detector signal:
      • on the BREAKOUT candle — arrow with text 'UHV HH:MM' showing the
        time of the candle being broken out of
      • on the UHV REFERENCE candle — small ring tagged 'UHV' so you can
        visually trace breakout → UHV
    UHV markers are deduplicated (one UHV is often referenced by many
    subsequent breakouts — we only mark each unique UHV once)."""
    markers = []
    seen_uhv = {}    # uhv_time → side-tag
    for s in detector_signals:
        is_buy = s["side"] > 0
        uhv_t  = s["uhv_time"]
        # uhv_t is unix seconds — format HH:MM using UTC so the label matches
        # what lightweight-charts will display on its (UTC) X-axis.
        uhv_label = datetime.fromtimestamp(uhv_t, tz=UTC).strftime("%H:%M")
        # breakout marker — arrow tagged with UHV time
        markers.append({
            "time": s["time"],
            "position": "belowBar" if is_buy else "aboveBar",
            "color": "#26a69a" if is_buy else "#ef5350",
            "shape": "arrowUp" if is_buy else "arrowDown",
            "text": f"UHV {uhv_label}",
        })
        # UHV marker — once per unique UHV bar
        key = (uhv_t, is_buy)
        if key not in seen_uhv:
            seen_uhv[key] = True
            markers.append({
                "time": uhv_t,
                # UHV is the OPPOSITE colour of the breakout — for a buy
                # breakout the UHV is a red candle, so mark its HIGH (above
                # bar); for a sell breakout the UHV is green, mark its LOW.
                "position": "aboveBar" if is_buy else "belowBar",
                "color": "#ffb74d",     # amber so UHV stands out from
                                        # both the green/red breakout arrows
                                        # AND from Zee's blue
                "shape": "circle",
                "text": "UHV",
            })
    return markers


def trade_stats():
    n = len(ZEE_TRADES)
    wins = sum(1 for t in ZEE_TRADES if t[5] > 0)
    losses = sum(1 for t in ZEE_TRADES if t[5] < 0)
    flat = n - wins - losses
    net = sum(t[5] for t in ZEE_TRADES)
    avg_win  = (sum(t[5] for t in ZEE_TRADES if t[5] > 0) / wins)   if wins else 0
    avg_loss = (sum(t[5] for t in ZEE_TRADES if t[5] < 0) / losses) if losses else 0
    best  = max(t[5] for t in ZEE_TRADES)
    worst = min(t[5] for t in ZEE_TRADES)
    return {"n": n, "wins": wins, "losses": losses, "flat": flat, "net": net,
            "wr": (wins / (wins + losses) if (wins + losses) else 0),
            "avg_win": avg_win, "avg_loss": avg_loss,
            "best": best, "worst": worst}


def detector_alignment(detector_signals):
    """For each Zee entry minute, was there a detector signal within ±N minutes
    of the same side? Returns alignment stats."""
    det_by_time = {(s["time"], s["side"]): s for s in detector_signals}
    det_minutes = sorted(set(s["time"] for s in detector_signals))
    WINDOW = 3 * 60   # ±3 min tolerance

    matched = 0
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        # any detector signal of same side within ±3 min?
        for s in detector_signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= WINDOW:
                matched += 1
                break
    return {
        "n_det":   len(detector_signals),
        "n_zee":   len(ZEE_TRADES),
        "matched": matched,
        "missed":  len(ZEE_TRADES) - matched,
    }


def trade_stats():
    n = len(ZEE_TRADES)
    wins = sum(1 for t in ZEE_TRADES if t[5] > 0)
    losses = sum(1 for t in ZEE_TRADES if t[5] < 0)
    net = sum(t[5] for t in ZEE_TRADES)
    avg_win  = (sum(t[5] for t in ZEE_TRADES if t[5] > 0) / wins)   if wins else 0
    avg_loss = (sum(t[5] for t in ZEE_TRADES if t[5] < 0) / losses) if losses else 0
    best  = max(t[5] for t in ZEE_TRADES)
    worst = min(t[5] for t in ZEE_TRADES)
    return {"n": n, "wins": wins, "losses": losses, "net": net,
            "wr": (wins / (wins + losses) if (wins + losses) else 0),
            "avg_win": avg_win, "avg_loss": avg_loss,
            "best": best, "worst": worst}


def load_feb11_bars():
    bars = []
    with open(M1_CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            if not r["time_iso"].startswith(TARGET_DATE):
                continue
            # Treat the broker-time string AS UTC so the unix we emit matches
            # what lightweight-charts will display on its (UTC-default) axis.
            t = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S").replace(tzinfo=UTC)
            bars.append({
                "time": int(t.timestamp()),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "vol": int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Feb 11 Lab — XAUUSD M1 (real data)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  :root {
    --bg: #131722; --panel: #1e222d; --text: #d1d4dc; --muted: #787b86;
    --accent: #2962ff; --green: #26a69a; --red: #ef5350;
    --border: #2a2e39;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
  }
  .topbar {
    height: 44px; background: var(--panel); border-bottom: 1px solid var(--border);
    display: flex; align-items: center; padding: 0 16px; gap: 18px;
  }
  .symbol { font-weight: 600; font-size: 15px; }
  .symbol .muted { color: var(--muted); font-weight: 400; font-size: 12px; margin-left: 8px; }
  .price { color: var(--muted); font-size: 12px; }
  .price .v { color: var(--text); font-weight: 600; }
  .badge {
    margin-left: auto; padding: 4px 10px; border-radius: 4px;
    background: rgba(38,166,154,0.15); color: var(--green);
    font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  }
  .badge.warn { background: rgba(239,83,80,0.15); color: var(--red); }
  .layout {
    display: grid; grid-template-columns: 1fr 280px;
    height: calc(100vh - 44px);
  }
  #chart { background: var(--bg); }
  .side {
    background: var(--panel); border-left: 1px solid var(--border);
    padding: 16px; overflow-y: auto;
  }
  .side h3 {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px;
    color: var(--muted); margin: 0 0 8px 0; font-weight: 600;
  }
  .stat {
    display: flex; justify-content: space-between; padding: 6px 0;
    border-bottom: 1px solid var(--border);
  }
  .stat:last-child { border: 0; }
  .stat .k { color: var(--muted); }
  .stat .v { font-variant-numeric: tabular-nums; }
  .stat .v.green { color: var(--green); }
  .stat .v.red { color: var(--red); }
  .section { margin-bottom: 22px; }
  .pill {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    background: var(--bg); border: 1px solid var(--border); font-size: 11px;
  }
  .footnote { color: var(--muted); font-size: 11px; line-height: 1.5; margin-top: 14px; }
</style>
</head>
<body>
<div class="topbar">
  <div class="symbol">XAUUSD <span class="muted">· 1m · Gold Spot vs US Dollar</span></div>
  <div class="price">@ <span class="v" id="b-time">—</span></div>
  <div class="price">O <span class="v" id="b-open">—</span></div>
  <div class="price">H <span class="v" id="b-high">—</span></div>
  <div class="price">L <span class="v" id="b-low">—</span></div>
  <div class="price">C <span class="v" id="b-close">—</span></div>
  <div class="price">Δ <span class="v" id="b-chg">—</span></div>
  <div class="badge" id="day-badge">FEB 11 — VERIFIED REAL-MONEY DAY</div>
</div>

<div class="layout">
  <div id="chart"></div>
  <div class="side">
    <div class="section">
      <h3>Day overview</h3>
      <div class="stat"><span class="k">Date</span><span class="v">2026-02-11</span></div>
      <div class="stat"><span class="k">Bars (M1)</span><span class="v" id="s-bars">—</span></div>
      <div class="stat"><span class="k">Day range</span><span class="v" id="s-range">—</span></div>
      <div class="stat"><span class="k">Open → Close</span><span class="v" id="s-oc">—</span></div>
      <div class="stat"><span class="k">Daily Δ</span><span class="v" id="s-delta">—</span></div>
    </div>
    <div class="section">
      <h3>Zee's full broker day</h3>
      <div class="stat"><span class="k">Net P&L (full day)</span><span class="v green">+$835</span></div>
      <div class="stat"><span class="k">Wins / Losses</span><span class="v">65 / 4</span></div>
      <div class="stat"><span class="k">Win rate</span><span class="v">94%</span></div>
    </div>
    <div class="section">
      <h3>Layers</h3>
      <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;">
        <input type="checkbox" id="tog-zee" checked>
        <span style="color:#3179f5;font-weight:600;">●</span>
        <span>Zee's trades (real broker fills)</span>
      </label>
      <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;">
        <input type="checkbox" id="tog-det">
        <span><span style="color:#26a69a;">▲</span><span style="color:#ef5350;">▼</span></span>
        <span>UHV-breakout detector <span style="color:#787b86;">(green=buy / red=sell)</span></span>
      </label>
      <label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;">
        <input type="checkbox" id="tog-ns" checked>
        <span><span style="color:#00bcd4;">▲</span><span style="color:#e91e63;">▼</span></span>
        <span>NS / ND detector <span style="color:#787b86;">(VSA — Zee's method)</span></span>
      </label>
    </div>
    <div class="section">
      <h3>Zee's trades (markers on chart)</h3>
      <div class="stat"><span class="k">Total</span><span class="v" id="zt-n">—</span></div>
      <div class="stat"><span class="k">Wins / Losses</span><span class="v" id="zt-wl">—</span></div>
      <div class="stat"><span class="k">Win rate</span><span class="v" id="zt-wr">—</span></div>
      <div class="stat"><span class="k">Net P&L</span><span class="v" id="zt-net">—</span></div>
      <div class="stat"><span class="k">Avg win</span><span class="v green" id="zt-aw">—</span></div>
      <div class="stat"><span class="k">Avg loss</span><span class="v red" id="zt-al">—</span></div>
      <div class="stat"><span class="k">Best / Worst</span><span class="v" id="zt-bw">—</span></div>
    </div>
    <div class="section">
      <h3>UHV-breakout detector vs Zee</h3>
      <div class="stat"><span class="k">Signals (day)</span><span class="v" id="det-n">—</span></div>
      <div class="stat"><span class="k">Caught Zee's entries</span><span class="v" id="det-m">—</span></div>
      <div class="stat"><span class="k">Catch rate</span><span class="v" id="det-mp">—</span></div>
      <div class="stat"><span class="k">Missed</span><span class="v" id="det-miss">—</span></div>
    </div>
    <div class="section">
      <h3>NS / ND detector vs Zee (VSA)</h3>
      <div class="stat"><span class="k">Signals (day)</span><span class="v" id="ns-n">—</span></div>
      <div class="stat"><span class="k">Caught Zee's entries</span><span class="v" id="ns-m">—</span></div>
      <div class="stat"><span class="k">Catch rate</span><span class="v" id="ns-mp">—</span></div>
      <div class="stat"><span class="k">Missed</span><span class="v" id="ns-miss">—</span></div>
      <div class="footnote">
        NS / ND = No Supply / No Demand (VSA). Detector waits for a UHV,
        then a small dead-volume candle (NS = red, ND = green), then a
        sweep-and-break trigger. "Caught" = same-side signal within ±3 min.
      </div>
    </div>
    <div class="footnote">
      Chart engine: <span class="pill">lightweight-charts</span> (TradingView's open-source).<br>
      Data: M1 OHLC from broker for 2026-02-11 — tick CSVs only exist from Apr 29 onward, so this day uses M1 bars as the most accurate available source.
    </div>
  </div>
</div>

<script>
const BARS        = __BARS_JSON__;
const ZEE_MARKERS = __ZEE_MARKERS_JSON__;
const DET_MARKERS = __DET_MARKERS_JSON__;
const NS_MARKERS  = __NS_MARKERS_JSON__;
const STATS       = __STATS_JSON__;
const ALIGN       = __ALIGN_JSON__;
const NS_ALIGN    = __NS_ALIGN_JSON__;
let SHOW_ZEE = true;
let SHOW_DET = false;
let SHOW_NS  = true;

const chart = LightweightCharts.createChart(document.getElementById('chart'), {
  layout: {
    background: { type: 'solid', color: '#131722' },
    textColor: '#d1d4dc',
  },
  grid: {
    vertLines: { color: '#1e222d' },
    horzLines: { color: '#1e222d' },
  },
  rightPriceScale: { borderColor: '#2a2e39' },
  timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
  crosshair: {
    mode: LightweightCharts.CrosshairMode.Normal,
  },
});

// Reserve the bottom 25% for the volume overlay
chart.priceScale('right').applyOptions({
  scaleMargins: { top: 0.05, bottom: 0.26 },
});

const series = chart.addCandlestickSeries({
  upColor: '#26a69a', downColor: '#ef5350',
  borderUpColor: '#26a69a', borderDownColor: '#ef5350',
  wickUpColor: '#26a69a', wickDownColor: '#ef5350',
});
series.setData(BARS);

// Volume histogram — overlaid in the bottom 22% of the same pane, colored
// green/red to match candle direction. Lets us SEE which bars carry the
// volume the v3.49 detector treats as UHV candidates.
const volumeSeries = chart.addHistogramSeries({
  priceFormat: { type: 'volume' },
  priceScaleId: 'volume',
  color: '#26a69a',
});
chart.priceScale('volume').applyOptions({
  scaleMargins: { top: 0.78, bottom: 0 },
});
const volumeData = BARS.map(b => ({
  time: b.time,
  value: b.vol,
  color: b.close >= b.open ? 'rgba(38,166,154,0.55)' : 'rgba(239,83,80,0.55)',
}));
volumeSeries.setData(volumeData);

function refreshMarkers() {
  // lightweight-charts only accepts ONE marker per time-stamp per series.
  // Merge layer markers and, on collisions, keep the FIRST (priority by
  // insertion order: Zee → NS → DET).
  let merged = [];
  const seen = new Set();
  function add(arr) {
    for (const m of arr) {
      if (seen.has(m.time)) continue;
      seen.add(m.time);
      merged.push(m);
    }
  }
  if (SHOW_ZEE) add(ZEE_MARKERS);
  if (SHOW_NS)  add(NS_MARKERS);
  if (SHOW_DET) add(DET_MARKERS);
  merged.sort((a, b) => a.time - b.time);
  series.setMarkers(merged);
}
refreshMarkers();

// Layer toggle handlers
document.getElementById('tog-zee').addEventListener('change', (e) => {
  SHOW_ZEE = e.target.checked; refreshMarkers();
});
document.getElementById('tog-det').addEventListener('change', (e) => {
  SHOW_DET = e.target.checked; refreshMarkers();
});
document.getElementById('tog-ns').addEventListener('change', (e) => {
  SHOW_NS = e.target.checked; refreshMarkers();
});

// Stats panel
if (STATS) {
  document.getElementById('zt-n').textContent  = STATS.n;
  document.getElementById('zt-wl').textContent = STATS.wins + ' / ' + STATS.losses;
  document.getElementById('zt-wr').textContent = (STATS.wr * 100).toFixed(0) + '%';
  const netEl = document.getElementById('zt-net');
  netEl.textContent = (STATS.net >= 0 ? '+$' : '-$') + Math.abs(STATS.net).toFixed(2);
  netEl.className = 'v ' + (STATS.net >= 0 ? 'green' : 'red');
  document.getElementById('zt-aw').textContent = '+$' + STATS.avg_win.toFixed(2);
  document.getElementById('zt-al').textContent = '$' + STATS.avg_loss.toFixed(2);
  document.getElementById('zt-bw').textContent =
      '+$' + STATS.best.toFixed(2) + ' / ' +
      (STATS.worst >= 0 ? '+' : '') + '$' + STATS.worst.toFixed(2);
}
if (ALIGN) {
  document.getElementById('det-n').textContent  = ALIGN.n_det;
  document.getElementById('det-m').textContent  = ALIGN.matched + ' / ' + ALIGN.n_zee;
  document.getElementById('det-mp').textContent =
    (100 * ALIGN.matched / Math.max(1, ALIGN.n_zee)).toFixed(0) + '%';
  document.getElementById('det-miss').textContent = ALIGN.missed;
}
if (NS_ALIGN) {
  document.getElementById('ns-n').textContent  = NS_ALIGN.n_det;
  document.getElementById('ns-m').textContent  = NS_ALIGN.matched + ' / ' + NS_ALIGN.n_zee;
  document.getElementById('ns-mp').textContent =
    (100 * NS_ALIGN.matched / Math.max(1, NS_ALIGN.n_zee)).toFixed(0) + '%';
  document.getElementById('ns-miss').textContent = NS_ALIGN.missed;
}

// Top-bar OHLC + TIME crosshair sync — read the actual hovered candle's time
chart.subscribeCrosshairMove(param => {
  if (!param || !param.time || !param.seriesData.size) return;
  const v = param.seriesData.get(series);
  if (!v) return;
  const d = new Date(param.time * 1000);
  // Use UTC getters — lightweight-charts displays times in UTC by default
  // (and we now feed it UTC-frame unix values). This keeps the top-bar
  // "@ HH:MM" in sync with both the X-axis labels AND the marker text.
  document.getElementById('b-time').textContent =
      String(d.getUTCHours()).padStart(2,'0') + ':' +
      String(d.getUTCMinutes()).padStart(2,'0');
  document.getElementById('b-open').textContent  = v.open.toFixed(2);
  document.getElementById('b-high').textContent  = v.high.toFixed(2);
  document.getElementById('b-low').textContent   = v.low.toFixed(2);
  document.getElementById('b-close').textContent = v.close.toFixed(2);
  const chg = v.close - v.open;
  const el = document.getElementById('b-chg');
  el.textContent = (chg >= 0 ? '+' : '') + chg.toFixed(2);
  el.style.color = chg >= 0 ? '#26a69a' : '#ef5350';
});

// Sidebar day stats
if (BARS.length) {
  const opens = BARS.map(b => b.open);
  const highs = BARS.map(b => b.high);
  const lows  = BARS.map(b => b.low);
  const closes = BARS.map(b => b.close);
  const dHigh = Math.max(...highs);
  const dLow  = Math.min(...lows);
  const dOpen = BARS[0].open;
  const dClose = BARS[BARS.length-1].close;
  const dDelta = dClose - dOpen;
  document.getElementById('s-bars').textContent  = BARS.length.toLocaleString();
  document.getElementById('s-range').textContent = dHigh.toFixed(2) + ' / ' + dLow.toFixed(2);
  document.getElementById('s-oc').textContent    = dOpen.toFixed(2) + ' → ' + dClose.toFixed(2);
  const deltaEl = document.getElementById('s-delta');
  deltaEl.textContent = (dDelta >= 0 ? '+' : '') + dDelta.toFixed(2) +
                        ' (' + (dDelta/dOpen*100).toFixed(2) + '%)';
  deltaEl.className = 'v ' + (dDelta >= 0 ? 'green' : 'red');
}

// Fit content + resize handler
chart.timeScale().fitContent();
window.addEventListener('resize', () => {
  chart.resize(document.getElementById('chart').clientWidth,
               document.getElementById('chart').clientHeight);
});
</script>
</body>
</html>
"""


def main():
    bars = load_feb11_bars()
    if not bars:
        print(f"NO Feb 11 bars in {M1_CSV}")
        return
    zee_markers     = build_zee_markers()
    det_signals     = run_detector_on_feb11(bars)
    det_markers     = build_detector_markers(det_signals)
    ns_signals      = run_ns_nd_detector(bars)
    ns_markers      = build_ns_nd_markers(ns_signals)
    stats           = trade_stats()
    alignment       = detector_alignment(det_signals)
    ns_align        = ns_nd_alignment(ns_signals)

    html = (HTML_TEMPLATE
            .replace("__BARS_JSON__",        json.dumps(bars))
            .replace("__ZEE_MARKERS_JSON__", json.dumps(zee_markers))
            .replace("__DET_MARKERS_JSON__", json.dumps(det_markers))
            .replace("__NS_MARKERS_JSON__",  json.dumps(ns_markers))
            .replace("__STATS_JSON__",       json.dumps(stats))
            .replace("__ALIGN_JSON__",       json.dumps(alignment))
            .replace("__NS_ALIGN_JSON__",    json.dumps(ns_align)))
    OUT_HTML.write_text(html, encoding="utf-8")
    first_t = datetime.fromtimestamp(bars[0]["time"], tz=UTC).strftime("%H:%M")
    last_t  = datetime.fromtimestamp(bars[-1]["time"], tz=UTC).strftime("%H:%M")
    print(f"Wrote {len(bars)} M1 bars   range (UTC frame): {first_t} -> {last_t}")
    print(f"  Zee:        {stats['n']} trades, {stats['wins']}W/{stats['losses']}L "
          f"({stats['wr']*100:.0f}% WR), net ${stats['net']:+.2f}")
    print(f"  UHV-BO det: {alignment['n_det']} signals  "
          f"alignment {alignment['matched']}/{alignment['n_zee']}")
    print(f"  NS/ND det:  {ns_align['n_det']} signals  "
          f"alignment {ns_align['matched']}/{ns_align['n_zee']}")
    print(f"  -> {OUT_HTML}")


if __name__ == "__main__":
    main()
