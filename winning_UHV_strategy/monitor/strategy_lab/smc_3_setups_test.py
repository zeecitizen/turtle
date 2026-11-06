"""smc_3_setups_test.py — backtest the 3 SMC setups on top of Shano-Zee.

Setup 1: Ultra High Volume Breakout (low risk confirmed entry, 95% claimed)
  H1 FVG tap → find UHV red candle in retracement → next candle sweeps low →
  green candle breaks UHV high → buy at green close

Setup 2: Two Bar Reversal (medium risk aggressive)
  H1 FVG tap → red sell candle → green engulfing with LOWER volume → buy at green close

Setup 3: Effort vs Result
  H1 FVG tap → red candle → green wicking candle (wicks below, closes back inside red body,
  HIGHER green volume than red) → buy at green close

All require: HTF uptrend, retracement context (red after green breaking last green low).

Tested as: layer each setup as filter on top of probe-confirm. If trigger candle's M5
context matches the setup, fire.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas, compute_ema, COMMON_DIR,
)

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def aggregate_to_tf_with_vol(bars_1m, minutes):
    """Return bars with (dt, o, h, l, c, vol)."""
    out = []
    cur = None; o = h = l = c = None; v = 0
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c, b_v = b[0], b[1], b[2], b[3], b[4], b[5]
        anchor = dt.minute - (dt.minute % minutes)
        if minutes >= 60:
            bm = dt.replace(minute=0, second=0, microsecond=0)
            bm_hr_offset = (dt.hour // (minutes // 60)) * (minutes // 60)
            bm = bm.replace(hour=bm_hr_offset)
        else:
            bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur is None:
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        elif bm != cur:
            out.append((cur, o, h, l, c, v))
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c; v += b_v
    if cur is not None: out.append((cur, o, h, l, c, v))
    return out


def detect_h1_fvgs(h1_bars, lookback=15):
    """Find FVG zones in last lookback H1 bars.
    Bullish FVG: bar[i-2].low > bar[i].high → zone [bar[i].high, bar[i-2].low]
    Bearish FVG: bar[i-2].high < bar[i].low → zone [bar[i-2].high, bar[i].low]"""
    fvgs = []
    n = len(h1_bars)
    start = max(2, n - lookback)
    for i in range(start, n):
        prev = h1_bars[i-2]; cur = h1_bars[i]
        if prev[3] > cur[2]:
            fvgs.append((i, h1_bars[i][0], 1, cur[2], prev[3]))  # (idx, dt, kind, lo, hi)
        if prev[2] < cur[3]:
            fvgs.append((i, h1_bars[i][0], -1, prev[2], cur[3]))
    return fvgs


def find_active_fvg_for_dir(when, h1_fvgs, h1_bar_idx, dir_sign, lookback_h1=15):
    """Find an FVG of the given direction that's still active and could be tapped."""
    # current H1 idx
    bm = when.replace(minute=0, second=0, microsecond=0)
    cur_idx = h1_bar_idx.get(bm)
    if cur_idx is None:
        for d in range(1, 24):
            t = bm - timedelta(hours=d)
            cur_idx = h1_bar_idx.get(t)
            if cur_idx is not None: break
    if cur_idx is None: return None
    # FVGs that exist by current H1 bar, of correct direction
    relevant = [f for f in h1_fvgs if f[0] <= cur_idx and f[1] >= bm - timedelta(hours=lookback_h1) and f[2] == dir_sign]
    return relevant[-1] if relevant else None


def m5_tapped_fvg(when, fvg, m5_bars, m5_bar_idx, lookback_m5=20):
    """Return True if any M5 bar in last lookback_m5 bars overlapped the FVG zone."""
    if fvg is None: return False
    _, _, kind, zlo, zhi = fvg
    bm = when.replace(minute=(when.minute // 5) * 5, second=0, microsecond=0)
    cur_idx = m5_bar_idx.get(bm)
    if cur_idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=5 * d)
            cur_idx = m5_bar_idx.get(t)
            if cur_idx is not None: break
    if cur_idx is None: return False
    start = max(0, cur_idx - lookback_m5)
    for i in range(start, cur_idx + 1):
        bar = m5_bars[i]
        if bar[3] <= zhi and bar[2] >= zlo: return True
    return False


def is_in_retracement(m5_bars, m5_idx, dir_sign, lookback=10):
    """Check if recent M5 bars show a retracement against trade direction.
    For BUY: at least 2 red candles, with one red breaking previous green's low."""
    if m5_idx < lookback: return False
    recent = m5_bars[m5_idx - lookback:m5_idx + 1]
    if dir_sign == 1:
        # Looking for red bars after green that broke green's low
        had_green = False; saw_break = False
        for i in range(1, len(recent)):
            cur = recent[i]; prev = recent[i-1]
            if prev[4] > prev[1]: had_green = True  # prev was green
            if had_green and cur[4] < cur[1] and cur[3] < prev[3]:  # red breaking prev low
                saw_break = True; break
        return saw_break
    else:  # sell mirror
        had_red = False
        for i in range(1, len(recent)):
            cur = recent[i]; prev = recent[i-1]
            if prev[4] < prev[1]: had_red = True
            if had_red and cur[4] > cur[1] and cur[2] > prev[2]:
                return True
        return False


def htf_uptrend(when, h1_ema, h1_bar_idx, dir_sign, h1_bars):
    """Price above H1 21-EMA for buys, below for sells."""
    bm = when.replace(minute=0, second=0, microsecond=0)
    idx = h1_bar_idx.get(bm)
    if idx is None:
        for d in range(1, 24):
            t = bm - timedelta(hours=d)
            idx = h1_bar_idx.get(t)
            if idx is not None: break
    if idx is None or idx >= len(h1_ema) or h1_ema[idx] is None: return False
    ema = h1_ema[idx]
    cur_price = h1_bars[idx][4]
    if dir_sign == 1: return cur_price > ema
    else: return cur_price < ema


def find_uhv_red_in_retracement(m5_bars, m5_idx, lookback=10, dir_sign=1):
    """Find the highest-volume red (for buys) or green (for sells) candle in last N bars."""
    start = max(0, m5_idx - lookback)
    candidates = []
    for i in range(start, m5_idx + 1):
        bar = m5_bars[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: candidates.append(i)
        elif dir_sign == -1 and is_green: candidates.append(i)
    if not candidates: return None
    return max(candidates, key=lambda i: m5_bars[i][5])


def setup1_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """Setup 1: UHV breakout. Need:
    - UHV red in retracement
    - A subsequent candle swept its low (wick or close)
    - Trigger candle (m5_bars[m5_idx]) is green that broke UHV's HIGH"""
    if dir_sign != 1: return False  # buy-only for now
    uhv_idx = find_uhv_red_in_retracement(m5_bars, m5_idx - 1, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = m5_bars[uhv_idx]
    # Sweep: any bar between uhv_idx+1 and m5_idx-1 has low < uhv low
    swept = False
    for i in range(uhv_idx + 1, m5_idx):
        if m5_bars[i][3] < uhv[3]: swept = True; break
    if not swept: return False
    # Trigger green broke UHV high
    trig = m5_bars[m5_idx]
    if trig[4] <= trig[1]: return False  # must be green
    if trig[4] <= uhv[2]: return False   # must close above uhv high
    return True


def setup2_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """Setup 2: engulfing with LOWER volume than red.
    - Find red candle in retracement
    - Trigger green engulfs red AND has lower volume"""
    if dir_sign != 1: return False
    if m5_idx < 1: return False
    trig = m5_bars[m5_idx]; prev = m5_bars[m5_idx - 1]
    # Trigger must be green
    if trig[4] <= trig[1]: return False
    # Prev must be red
    if prev[4] >= prev[1]: return False
    # Engulfing: trig.close > prev.open AND trig.open < prev.close
    if trig[4] <= prev[1] or trig[1] >= prev[4]: return False
    # Volume: trig green vol < prev red vol
    if trig[5] >= prev[5]: return False
    return True


def setup3_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """Setup 3: Effort vs Result — green wicking candle with HIGHER vol than red.
    - Red candle exists in last N
    - Trigger green wicks BELOW red's low BUT closes back INSIDE red's body
    - Trigger green volume > red candle volume"""
    if dir_sign != 1: return False
    if m5_idx < 1: return False
    # Find a recent red candle to anchor (last red within lookback)
    red_idx = None
    for i in range(m5_idx - 1, max(0, m5_idx - lookback) - 1, -1):
        if m5_bars[i][4] < m5_bars[i][1]:
            red_idx = i; break
    if red_idx is None: return False
    red = m5_bars[red_idx]
    trig = m5_bars[m5_idx]
    # Trigger must be green
    if trig[4] <= trig[1]: return False
    # Trigger wicks BELOW red's low
    if trig[3] >= red[3]: return False
    # Trigger closes BACK INSIDE red's body (between red's open and close)
    red_body_lo = min(red[1], red[4])
    red_body_hi = max(red[1], red[4])
    if not (red_body_lo <= trig[4] <= red_body_hi): return False
    # Trigger volume HIGHER than red volume
    if trig[5] <= red[5]: return False
    return True


# ── Sim infra ──
def trend_at(when, ema_f, ema_s, bar_idx_2m, tf=2):
    anchor = when.minute - (when.minute % tf)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_2m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf * d)
            idx = bar_idx_2m.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_f[idx]; s = ema_s[idx]; fp = ema_f[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def get_uhv_bar(when, bars_1m, bar_idx_1m, lookback=20):
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None, None
    trigger_idx = idx - 1
    lookback_bars = bars_1m[max(0, trigger_idx - lookback):trigger_idx]
    if not lookback_bars: return None, None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    uhv_global_idx = bars_1m.index(uhv)
    return uhv, uhv_global_idx, trigger_idx


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback=20):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv is None: return False
    if dir_sign == 1 and price <= uhv[2]: return False
    if dir_sign == -1 and price >= uhv[3]: return False
    return True


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
              fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              uhv_lookback=20, horizon_sec=HORIZON_SEC):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price,
                                    ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run(label, *, require_setup=None, require_h1_fvg_tap=False,
         require_htf_uptrend=False, require_retracement=False,
         buy_only=True):
    """require_setup in {1, 2, 3, None}."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    bars_5m = aggregate_to_tf_with_vol(bars_1m, 5)
    bars_h1 = aggregate_to_tf_with_vol(bars_1m, 60)
    bar_idx_5m = {b[0]: i for i, b in enumerate(bars_5m)}
    bar_idx_h1 = {b[0]: i for i, b in enumerate(bars_h1)}
    h1_ema = compute_ema([b[4] for b in bars_h1], 21)
    h1_fvgs = detect_h1_fvgs(bars_h1, 30)

    chains = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        if buy_only and dir_sign != 1: continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Standard Shano-Zee
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # Find M5 idx for trigger time
        bm5 = entry_time.replace(minute=(entry_time.minute // 5) * 5, second=0, microsecond=0)
        m5_idx = bar_idx_5m.get(bm5)
        if m5_idx is None:
            for d in range(1, 30):
                tt = bm5 - timedelta(minutes=5 * d)
                m5_idx = bar_idx_5m.get(tt)
                if m5_idx is not None: break
        if m5_idx is None: continue

        # ── HTF UPTREND ──
        if require_htf_uptrend:
            if not htf_uptrend(entry_time, h1_ema, bar_idx_h1, dir_sign, bars_h1): continue
        # ── RETRACEMENT ──
        if require_retracement:
            if not is_in_retracement(bars_5m, m5_idx, dir_sign, lookback=10): continue
        # ── H1 FVG TAP ──
        if require_h1_fvg_tap:
            fvg = find_active_fvg_for_dir(entry_time, h1_fvgs, bar_idx_h1, dir_sign, lookback_h1=15)
            if fvg is None: continue
            if not m5_tapped_fvg(entry_time, fvg, bars_5m, bar_idx_5m, lookback_m5=20): continue
        # ── SETUP MATCH ──
        if require_setup == 1:
            if not setup1_match(bars_5m, m5_idx, dir_sign): continue
        elif require_setup == 2:
            if not setup2_match(bars_5m, m5_idx, dir_sign): continue
        elif require_setup == 3:
            if not setup3_match(bars_5m, m5_idx, dir_sign): continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append(chain)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    print(f"  {label:<70}chains={n:<3}mains={len(all_mains):<4}WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}")


print("=" * 180)
print("SMC 3-SETUPS test on Shano-Zee (descending ladder, fearI=$100, maxBurst=7)")
print("Buy-side only. All setups expect: HTF uptrend + retracement + H1 FVG tap + specific candle pattern")
print("=" * 180)
print()
print("--- BASELINE (buys only, no setup filter) ---")
run("BASELINE buys-only Shano-Zee descending")

print()
print("--- INDIVIDUAL CONTEXT FILTERS ---")
run("HTF uptrend (H1 21-EMA aligned)", require_htf_uptrend=True)
run("Retracement on M5", require_retracement=True)
run("H1 FVG tap on M5 (lookback=20 m5 bars)", require_h1_fvg_tap=True)

print()
print("--- HTF + retracement + FVG tap (CONTEXT chain, no specific setup) ---")
run("HTF + retracement + H1 FVG tap", require_htf_uptrend=True, require_retracement=True, require_h1_fvg_tap=True)

print()
print("--- SETUP 1: UHV BREAKOUT (95% claimed) ---")
run("Setup 1 only (no extra context)", require_setup=1)
run("Setup 1 + retracement", require_setup=1, require_retracement=True)
run("Setup 1 + HTF + retracement", require_setup=1, require_htf_uptrend=True, require_retracement=True)
run("FULL Setup 1: HTF + retracement + H1 FVG + UHV breakout",
    require_setup=1, require_htf_uptrend=True, require_retracement=True, require_h1_fvg_tap=True)

print()
print("--- SETUP 2: TWO BAR REVERSAL (engulfing with LOWER volume) ---")
run("Setup 2 only", require_setup=2)
run("Setup 2 + retracement", require_setup=2, require_retracement=True)
run("Setup 2 + HTF + retracement", require_setup=2, require_htf_uptrend=True, require_retracement=True)
run("FULL Setup 2: HTF + retracement + H1 FVG + engulfing(low vol)",
    require_setup=2, require_htf_uptrend=True, require_retracement=True, require_h1_fvg_tap=True)

print()
print("--- SETUP 3: EFFORT VS RESULT (green wick + close inside red, HIGHER vol) ---")
run("Setup 3 only", require_setup=3)
run("Setup 3 + retracement", require_setup=3, require_retracement=True)
run("Setup 3 + HTF + retracement", require_setup=3, require_htf_uptrend=True, require_retracement=True)
run("FULL Setup 3: HTF + retracement + H1 FVG + green wick reversal",
    require_setup=3, require_htf_uptrend=True, require_retracement=True, require_h1_fvg_tap=True)

print()
print("--- COMBOS: any of the 3 setups (OR) ---")
print("(not implemented as OR — would need union logic)")
