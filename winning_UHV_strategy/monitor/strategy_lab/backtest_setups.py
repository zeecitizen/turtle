"""backtest_setups.py — validate Zee's 3 specific VSA setups on 12 days
of real tick data (Apr 29 - May 14 2026).

All setups:
  • H1 FVG must exist (unfilled) and be tapped on M5
  • Operate on M5 timeframe (built from M1 bars)
  • Uptrend context required for BUY (downtrend for SELL — symmetric)
  • Setup happens during a retracement (red candles break prior green's low)

Setup 1 — Ultra High Volume Breakout (95% claimed):
  • Find red candle with HIGHEST red volume in the retracement
  • Wait for a candle to break BELOW UHV red's low (wick-sweep or close)
  • Wait for a green candle to close ABOVE UHV red's high
  • Entry: green breakout's close
  • SL: below UHV red's low
  • TP: last recent high peak

Setup 2 — Two-bar reversal (aggressive):
  • Find ANY red volume candle in retracement
  • Find a green candle that ENGULFS the red AND has LOWER volume than it
  • Entry: engulfing green's close
  • SL: below engulfing candle
  • TP: highest red volume candle's high (the UHV red's high)

Setup 3 — Effort vs Result:
  • Find red candle in retracement
  • Find green candle that wicks BELOW red's low BUT closes back INSIDE
    red's range AND has HIGHER volume than the red
  • Entry: wicking green's close (or next green's close if big upper wick)
  • SL: below wicking green's low
  • TP: last recent high peak
"""
import csv
import glob
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON

CONTRACT = 100.0
PIP      = 0.10
RATE_LIMIT_S = 2.0


# ─── Aggregation ───
def aggregate_to_tf(m1_bars, k):
    """Aggregate M1 bars to k-min bars. Group by floor(time / k_minutes)."""
    bucketed = {}
    for b in m1_bars:
        # k-minute bucket — floor minute to nearest k
        ts = b["time"]
        bucket_min = (ts.minute // k) * k
        bucket_t   = ts.replace(minute=bucket_min, second=0, microsecond=0)
        key = bucket_t
        if key not in bucketed:
            bucketed[key] = {"time": key, "open": b["open"], "high": b["high"],
                             "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = bucketed[key]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(bucketed.values(), key=lambda x: x["time"])


def group_bars_by_day(bars):
    days = {}
    for b in bars:
        d = b["time"].date().isoformat()
        days.setdefault(d, []).append(b)
    for d in days:
        days[d].sort(key=lambda b: b["time"])
    return days


# ─── H1 FVG detection ───
def find_h1_fvgs(h1_bars):
    """Returns list of bullish FVGs (dict with t0, gap_low, gap_high, filled_at).
    A bullish FVG = h1[i-2].high < h1[i].low.
    'filled_at' = the time when the FVG was first traded through (low<gap_low).
    None if still unfilled at end of data."""
    fvgs = []
    for i in range(2, len(h1_bars)):
        gap_low  = h1_bars[i-2]["high"]
        gap_high = h1_bars[i]["low"]
        if gap_high <= gap_low: continue
        # Track when this FVG was filled (price went all the way through gap_low)
        filled_at = None
        for j in range(i+1, len(h1_bars)):
            if h1_bars[j]["low"] < gap_low:
                filled_at = h1_bars[j]["time"]; break
        fvgs.append({"t0": h1_bars[i]["time"], "gap_low": gap_low,
                     "gap_high": gap_high, "filled_at": filled_at,
                     "side": "bullish"})
    # Bearish too (for sell setups)
    for i in range(2, len(h1_bars)):
        gap_high = h1_bars[i-2]["low"]
        gap_low  = h1_bars[i]["high"]
        if gap_high <= gap_low: continue
        filled_at = None
        for j in range(i+1, len(h1_bars)):
            if h1_bars[j]["high"] > gap_high:
                filled_at = h1_bars[j]["time"]; break
        fvgs.append({"t0": h1_bars[i]["time"], "gap_low": gap_low,
                     "gap_high": gap_high, "filled_at": filled_at,
                     "side": "bearish"})
    return fvgs


def fvg_visible_and_tapped_at(fvgs, side, m5_bar):
    """Return the LATEST visible-and-tapped FVG of given side at m5_bar's time,
    or None. 'Visible' = formed before m5_bar; 'tapped' = m5_bar's range
    intersects the FVG zone; 'unfilled' = filled_at > m5_bar.time (or None)."""
    best = None
    for f in fvgs:
        if f["side"] != side: continue
        if f["t0"] >= m5_bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= m5_bar["time"]: continue
        # Tap check
        if m5_bar["low"] <= f["gap_high"] and m5_bar["high"] >= f["gap_low"]:
            if best is None or f["t0"] > best["t0"]:
                best = f
    return best


# Lookbacks below assume M5 default. Set _TF_MINUTES to scale them for
# other timeframes (e.g., 1 for M1 → all bar-lookbacks multiply by 5).
_TF_MINUTES = 5

def _scale(n_m5_bars):
    """Convert an M5-bar count into bars at the current exec timeframe."""
    return max(1, int(n_m5_bars * (5 / _TF_MINUTES)))


# ─── Uptrend detection (simple proxy) ───
def is_uptrend(m5_bars, idx, lookback=24, threshold=2.0):
    """Uptrend = close at idx is at least `threshold` price points above
    close N bars ago, where N is `lookback` SCALED for current timeframe
    (M5 default = 24 bars = 2 hours; on M1 → 120 bars = 2 hours)."""
    lookback = _scale(lookback)
    if idx < lookback: return False
    return m5_bars[idx]["close"] - m5_bars[idx-lookback]["close"] > threshold


def is_downtrend(m5_bars, idx, lookback=24, threshold=2.0):
    lookback = _scale(lookback)
    if idx < lookback: return False
    return m5_bars[idx-lookback]["close"] - m5_bars[idx]["close"] > threshold


# ─── Retracement scan: find latest red candles after a green peak ───
def find_retracement_reds(m5_bars, idx, max_lookback=15):
    """For a BUY setup, walk back from idx and collect the most recent
    contiguous-ish sequence of red candles (allowing some greens) that form
    a pullback against the prior up-move. Returns list of indices (red bars only)."""
    reds = []
    swing_high_idx = -1
    for j in range(idx - 1, max(idx - max_lookback - 1, -1), -1):
        b = m5_bars[j]
        if b["close"] >= b["open"]:    # green
            # If we already have reds and now hit a strong green, stop —
            # likely the swing-high before the retracement.
            if reds and b["high"] > m5_bars[reds[-1]]["high"]:
                swing_high_idx = j; break
        else:
            reds.append(j)
    return reds, swing_high_idx


def find_retracement_greens(m5_bars, idx, max_lookback=15):
    """SELL setup symmetric: find rally greens after a red trough."""
    greens = []
    swing_low_idx = -1
    for j in range(idx - 1, max(idx - max_lookback - 1, -1), -1):
        b = m5_bars[j]
        if b["close"] <= b["open"]:
            if greens and b["low"] < m5_bars[greens[-1]]["low"]:
                swing_low_idx = j; break
        else:
            greens.append(j)
    return greens, swing_low_idx


# ─── Setup 1: Ultra High Volume Breakout (BUY) ───
def detect_setup1_buy(m5_bars, idx, fvgs):
    """At m5_bars[idx] (potential green breakout):
      • bar must be green and close > some red's high (the UHV red)
      • UHV red = highest-vol red in the recent retracement
      • Some bar between UHV red and idx must have low < UHV red's low (sweep)
      • H1 FVG present and tapped during retracement
      • Uptrend.
    Returns (entry_price, sl, tp, ref_dict) or None."""
    bo = m5_bars[idx]
    if bo["close"] <= bo["open"]: return None      # need green breakout
    if not is_uptrend(m5_bars, idx): return None

    reds, swing_high_idx = find_retracement_reds(m5_bars, idx, max_lookback=_scale(15))
    if not reds: return None
    uhv_red_idx = max(reds, key=lambda j: m5_bars[j]["vol"])
    uhv_red = m5_bars[uhv_red_idx]

    # Breakout: bo.close > UHV red's high
    if bo["close"] <= uhv_red["high"]: return None
    # bo.open must NOT already be above UHV red's high (fresh transition)
    if bo["open"]  >  uhv_red["high"]: return None

    # Sweep: some bar between uhv_red+1 and idx has low < uhv_red.low
    swept = any(m5_bars[j]["low"] < uhv_red["low"] for j in range(uhv_red_idx+1, idx+1))
    if not swept: return None

    # H1 FVG tapped during the retracement (any red bar's range overlaps an unfilled bullish FVG)
    tapped = False
    for j in reds:
        if fvg_visible_and_tapped_at(fvgs, "bullish", m5_bars[j]) is not None:
            tapped = True; break
    if not tapped: return None

    entry = bo["close"]
    sl    = uhv_red["low"] - PIP
    # TP: most recent high peak — use the swing high or the highest high in last 30 bars
    tp_lookback = 30
    high_window = [m5_bars[j]["high"] for j in range(max(0, idx-tp_lookback), idx)]
    if not high_window: return None
    tp = max(high_window)
    if tp <= entry: return None
    return entry, sl, tp, {"setup": "S1_buy", "uhv_red_t": uhv_red["time"]}


def detect_setup1_sell(m5_bars, idx, fvgs):
    bo = m5_bars[idx]
    if bo["close"] >= bo["open"]: return None
    if not is_downtrend(m5_bars, idx): return None
    greens, swing_low_idx = find_retracement_greens(m5_bars, idx, max_lookback=_scale(15))
    if not greens: return None
    uhv_green_idx = max(greens, key=lambda j: m5_bars[j]["vol"])
    uhv_green = m5_bars[uhv_green_idx]
    if bo["close"] >= uhv_green["low"]: return None
    if bo["open"]  <  uhv_green["low"]: return None
    swept = any(m5_bars[j]["high"] > uhv_green["high"] for j in range(uhv_green_idx+1, idx+1))
    if not swept: return None
    tapped = False
    for j in greens:
        if fvg_visible_and_tapped_at(fvgs, "bearish", m5_bars[j]) is not None:
            tapped = True; break
    if not tapped: return None
    entry = bo["close"]
    sl    = uhv_green["high"] + PIP
    low_window = [m5_bars[j]["low"] for j in range(max(0, idx-_scale(30)), idx)]
    if not low_window: return None
    tp = min(low_window)
    if tp >= entry: return None
    return entry, sl, tp, {"setup": "S1_sell", "uhv_green_t": uhv_green["time"]}


# ─── Setup 2: Engulfing reversal (BUY) ───
def detect_setup2_buy(m5_bars, idx, fvgs):
    bo = m5_bars[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5_bars, idx): return None

    # Engulfing: bo.high > prev.high AND bo.low < prev.low AND prev is red
    if idx < 1: return None
    red = m5_bars[idx - 1]
    if red["close"] >= red["open"]: return None
    if not (bo["high"] > red["high"] and bo["low"] < red["low"]): return None
    # Engulfing green volume < red volume
    if bo["vol"] >= red["vol"]: return None

    reds, _ = find_retracement_reds(m5_bars, idx, max_lookback=15)
    if not reds: return None
    # Need H1 FVG tap during retracement
    tapped = False
    for j in reds:
        if fvg_visible_and_tapped_at(fvgs, "bullish", m5_bars[j]) is not None:
            tapped = True; break
    if not tapped: return None

    # TP at highest red-vol candle's high (in the retracement)
    uhv_red_idx = max(reds, key=lambda j: m5_bars[j]["vol"])
    tp = m5_bars[uhv_red_idx]["high"]
    entry = bo["close"]
    sl    = bo["low"] - PIP
    if tp <= entry: return None
    return entry, sl, tp, {"setup": "S2_buy", "red_t": red["time"]}


def detect_setup2_sell(m5_bars, idx, fvgs):
    bo = m5_bars[idx]
    if bo["close"] >= bo["open"]: return None
    if not is_downtrend(m5_bars, idx): return None
    if idx < 1: return None
    green = m5_bars[idx - 1]
    if green["close"] <= green["open"]: return None
    if not (bo["high"] > green["high"] and bo["low"] < green["low"]): return None
    if bo["vol"] >= green["vol"]: return None
    greens, _ = find_retracement_greens(m5_bars, idx, max_lookback=15)
    if not greens: return None
    tapped = False
    for j in greens:
        if fvg_visible_and_tapped_at(fvgs, "bearish", m5_bars[j]) is not None:
            tapped = True; break
    if not tapped: return None
    uhv_green_idx = max(greens, key=lambda j: m5_bars[j]["vol"])
    tp = m5_bars[uhv_green_idx]["low"]
    entry = bo["close"]
    sl    = bo["high"] + PIP
    if tp >= entry: return None
    return entry, sl, tp, {"setup": "S2_sell", "green_t": green["time"]}


# ─── Setup 3: Effort vs Result (BUY) ───
def detect_setup3_buy(m5_bars, idx, fvgs):
    """idx is the GREEN wicking candle (or the bar that breaks the wicking
    green's high if it had a big upper wick — we test the simpler form
    first: just the wicking candle itself triggers entry)."""
    bo = m5_bars[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5_bars, idx): return None
    # Need a recent red candle (in the retracement) whose low > bo's low
    # AND bo's close is BACK INSIDE the red's range (i.e., bo.close > red.low)
    # AND bo's volume > red's volume
    reds, _ = find_retracement_reds(m5_bars, idx, max_lookback=15)
    if not reds: return None
    # Try each red — find one where bo wicks below it
    for red_idx in reds:
        red = m5_bars[red_idx]
        if bo["low"] >= red["low"]: continue    # didn't wick below
        if bo["close"] <= red["low"]: continue  # didn't close back inside
        if bo["vol"]  <= red["vol"]:  continue  # need HIGHER green vol
        # H1 FVG tapped during retracement
        tapped = False
        for j in reds:
            if fvg_visible_and_tapped_at(fvgs, "bullish", m5_bars[j]) is not None:
                tapped = True; break
        if not tapped: continue
        entry = bo["close"]
        sl    = bo["low"] - PIP
        high_window = [m5_bars[j]["high"] for j in range(max(0, idx-_scale(30)), idx)]
        if not high_window: continue
        tp = max(high_window)
        if tp <= entry: continue
        return entry, sl, tp, {"setup": "S3_buy", "red_t": red["time"]}
    return None


def detect_setup3_sell(m5_bars, idx, fvgs):
    bo = m5_bars[idx]
    if bo["close"] >= bo["open"]: return None
    if not is_downtrend(m5_bars, idx): return None
    greens, _ = find_retracement_greens(m5_bars, idx, max_lookback=15)
    if not greens: return None
    for green_idx in greens:
        green = m5_bars[green_idx]
        if bo["high"] <= green["high"]: continue
        if bo["close"] >= green["high"]: continue
        if bo["vol"]   <= green["vol"]:  continue
        tapped = False
        for j in greens:
            if fvg_visible_and_tapped_at(fvgs, "bearish", m5_bars[j]) is not None:
                tapped = True; break
        if not tapped: continue
        entry = bo["close"]
        sl    = bo["high"] + PIP
        low_window = [m5_bars[j]["low"] for j in range(max(0, idx-_scale(30)), idx)]
        if not low_window: continue
        tp = min(low_window)
        if tp >= entry: continue
        return entry, sl, tp, {"setup": "S3_sell", "green_t": green["time"]}
    return None


# ─── Tick replay ───
def replay_signals(ticks, signals, lots=0.10):
    """For each signal (with absolute entry/SL/TP price levels), open at next
    tick after signal time, exit on whichever hits first. SL/TP are absolute
    price levels — they account for the strategy's own TP-at-recent-peak."""
    ppp = lots * CONTRACT
    units = []
    done  = []
    last_fire = None
    sig_iter = iter(sorted(signals, key=lambda s: s["fire_time"]))
    pending  = next(sig_iter, None)

    def open_unit(t, bid, ask, sig):
        if sig["side"] > 0:
            e = ask
        else:
            e = bid
        return {"side": sig["side"], "e": e, "sl": sig["sl"], "tp": sig["tp"],
                "fire_t": sig["fire_time"], "open_t": t, "ref": sig["ref"]}

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            exit_pnl = exit_why = None
            if u["side"] > 0:
                if bid <= u["sl"]: exit_pnl, exit_why = (u["sl"]-u["e"])*ppp, "sl"
                elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"]-u["e"])*ppp, "tp"
            else:
                if ask >= u["sl"]: exit_pnl, exit_why = (u["e"]-u["sl"])*ppp, "sl"
                elif ask <= u["tp"]: exit_pnl, exit_why = (u["e"]-u["tp"])*ppp, "tp"
            if exit_pnl is not None:
                u["pnl"], u["why"], u["close_t"] = exit_pnl, exit_why, t
                done.append(u); units.remove(u)
        while pending is not None and t >= pending["fire_time"]:
            if len(units) < 2 and (last_fire is None or
                (t - last_fire).total_seconds() >= RATE_LIMIT_S):
                units.append(open_unit(t, bid, ask, pending))
                last_fire = t
            pending = next(sig_iter, None)

    if ticks:
        last = ticks[-1]
        for u in units:
            if u["side"] > 0: u["pnl"] = (last["bid"] - u["e"]) * ppp
            else:             u["pnl"] = (u["e"] - last["ask"]) * ppp
            u["why"], u["close_t"] = "eod", last["t"]
            done.append(u)
    return done


# ─── Driver ───
def detect_all_signals_for_day(m1_bars_day, all_h1_fvgs, exec_tf=5):
    """For a single day's M1 bars, build exec-timeframe bars (5 or 1), run
    all 3 setups, return signal list with absolute SL/TP."""
    if exec_tf == 1:
        exec_bars = list(m1_bars_day)
    else:
        exec_bars = aggregate_to_tf(m1_bars_day, exec_tf)
    signals = []
    fired_keys = set()
    for idx in range(25, len(exec_bars)):
        for setup_fn, side in [
            (detect_setup1_buy, +1), (detect_setup1_sell, -1),
            (detect_setup2_buy, +1), (detect_setup2_sell, -1),
            (detect_setup3_buy, +1), (detect_setup3_sell, -1),
        ]:
            r = setup_fn(exec_bars, idx, all_h1_fvgs)
            if r is None: continue
            entry, sl, tp, ref = r
            key = (ref["setup"], list(ref.values())[1])
            if key in fired_keys: continue
            fired_keys.add(key)
            signals.append({
                "fire_time": exec_bars[idx]["time"] + timedelta(minutes=exec_tf),
                "side": side, "entry": entry, "sl": sl, "tp": tp, "ref": ref,
                "setup": ref["setup"],
            })
    return signals


def run_for_exec_tf(exec_tf, days_bars, h1_fvgs, tick_files):
    global _TF_MINUTES
    _TF_MINUTES = exec_tf
    by_setup = {"S1_buy":[], "S1_sell":[], "S2_buy":[], "S2_sell":[], "S3_buy":[], "S3_sell":[]}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        day_bars = days_bars[day]
        if len(day_bars) < 30: continue
        signals = detect_all_signals_for_day(day_bars, h1_fvgs, exec_tf=exec_tf)
        if not signals: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        done = replay_signals(ticks, signals, lots=0.10)
        for d in done:
            by_setup[d["ref"]["setup"]].append({**d, "day": day})
    return by_setup


def print_results(label, by_setup):
    print(f"\n=== {label} ===")
    print(f"{'Setup':<10} {'n':>5} {'pwin':>6} {'Wavg':>7} {'Lavg':>7} {'EV':>8} {'TOTAL':>10}")
    grand_total = 0
    for setup_name, trades in by_setup.items():
        n = len(trades)
        if n == 0:
            print(f"{setup_name:<10} {0:>5}")
            continue
        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in trades if t["pnl"] < 0]
        n_w, n_l = len(wins), len(losses)
        pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
        w_avg = sum(wins)/n_w if n_w else 0
        l_avg = -sum(losses)/n_l if n_l else 0
        total = sum(t["pnl"] for t in trades)
        ev = pwin*w_avg - (1-pwin)*l_avg
        grand_total += total
        marker = " *" if total > 0 else ""
        print(f"{setup_name:<10} {n:>5} {pwin:>6.3f} ${w_avg:>5.2f} ${l_avg:>5.2f} "
              f"${ev:>+6.2f} ${total:>+8.2f}{marker}")
    print(f"GRAND TOTAL: ${grand_total:+.2f}  |  @ 0.40 lots: ${grand_total*4:+.2f}")


def main():
    print("Loading M1 bars and H1 aggregation...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1_all = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1_all)
    print(f"  {len(bars_all)} M1 bars, {len(h1_all)} H1 bars, {len(h1_fvgs)} H1 FVGs total")
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # Run on M5 (original) and M1 for comparison
    by_setup_m5 = run_for_exec_tf(5, days_bars, h1_fvgs, tick_files)
    print_results("M5 exec timeframe (original)", by_setup_m5)
    by_setup_m1 = run_for_exec_tf(1, days_bars, h1_fvgs, tick_files)
    print_results("M1 exec timeframe", by_setup_m1)


if __name__ == "__main__":
    main()
