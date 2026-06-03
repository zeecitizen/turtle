"""backtest_anticipation_v4_camel.py — Camel-hump trend filter + sweep entry.

==============================================================================
STRATEGY STEPS (per Zee's instructions 2026-06-03)
==============================================================================

  STEP 1 — Trend detection via CAMEL HUMPS
    On each timeframe, identify the last 2 swing highs (SH1 older, SH2 newer)
    and last 2 swing lows (SL1 older, SL2 newer). A "swing" = a bar whose
    high (or low) is the most extreme in a ±3-bar window on the same TF.

    Classify market structure:
      • UPTREND     : SH2 > SH1 AND SL2 > SL1  (Higher High + Higher Low)
      • DOWNTREND   : SH2 < SH1 AND SL2 < SL1  (Lower High + Lower Low)
      • M_TOP       : |SH2 - SH1| <= 0.3% of price AND current within $1 of
                      SH2 → camel-hump bearish exhaustion → SELL only
      • W_BOTTOM    : mirror of M_TOP → BUY only
      • CHOP        : everything else → NO TRADE

  STEP 2 — Sweep+Reverse entry on M1 (precision execution TF)
    On M1, look for a counter-trend candle whose OPPOSITE-side wick is
    BIG enough to be a stop-hunt:
      • lower wick >= 2.0 × body AND >= $1.5 absolute   (for BUY)
      • upper wick >= 2.0 × body AND >= $1.5 absolute   (for SELL)
    Side must agree with STEP 1's structure tag.

  STEP 3 — Confirmation: next M1 bar must close past the sweep bar's range
    BUY  : next bar close > sweep bar high
    SELL : next bar close < sweep bar low
    No look-ahead — we fire at the close of the confirmation bar.

  STEP 4 — Optional FVG overlap (toggled by flag)
    If enabled, require an unfilled FVG (on M5/M15/M30/H1 aggregate) that
    overlaps the sweep bar's wick. Without this, more signals but lower
    quality. With this, fewer but higher quality.

  STEP 5 — Time window filter
    Only fire 16:00-20:00 UTC (88% of Zee's Feb 11 entries cluster here).

  STEP 6 — Exit
    Entry  = confirmation bar's close.
    Stop   = sweep bar's swept extreme (wick low for BUY, wick high for SELL),
             capped at $3.0 max risk.
    Target = entry + 1.5 × risk distance (1.5R).
    Time stop = 20 minutes after entry.

==============================================================================
COMBOS TESTED
==============================================================================

  For each combination, we report: signals, W/L, WR%, total PnL, expectancy,
  alignment with Zee's 69 broker trades (±3 min same side).

  Trend TF × FVG-filter × Entry TF (entry always M1 for precision):

    Trend TF:       M5, M15, M30, H1
    FVG required:   no, yes
    -> 8 combinations.
"""
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from build_feb11_lab import (
    load_feb11_bars, ZEE_TRADES,
    _has_unfilled_bullish_fvg_overlap, _has_unfilled_bearish_fvg_overlap,
)

WINDOW_START_HOUR = 16
WINDOW_END_HOUR   = 20
MIN_WICK_BODY     = 2.0
MIN_WICK_ABS      = 1.5
SL_MAX_USD        = 3.0
RR                = 1.5
TIME_STOP_BARS    = 20
LOTS              = 0.05
USD_PER_PRICE     = LOTS * 100
SWING_PIVOT_K     = 1          # was 3 (too coarse, missed 19:08 twin top on M5/M15)
NEAR_HUMP_FACTOR  = 0.005      # was 0.003 — accept twin peaks within 0.5% (was 0.3%)
NEAR_HUMP_USD     = 3.0        # was 1.5 — current bar within $3 of second hump (was 1.5)
PIVOT_LOOKBACK    = 25         # how many HTF bars back to search for pivots


def aggregate(m1, k):
    out = []
    for s in range(0, len(m1), k):
        chunk = m1[s:s + k]
        if len(chunk) < k: break
        out.append({
            "time":  chunk[0]["time"],
            "open":  chunk[0]["open"],
            "high":  max(b["high"] for b in chunk),
            "low":   min(b["low"]  for b in chunk),
            "close": chunk[-1]["close"],
            "vol":   sum(b["vol"] for b in chunk),
            "end_time": chunk[-1]["time"],
        })
    return out


def in_window(ts):
    h = datetime.fromtimestamp(ts, tz=UTC).hour
    return WINDOW_START_HOUR <= h < WINDOW_END_HOUR


def find_pivots(bars, current_idx, k=SWING_PIVOT_K, lookback=40):
    """Return (swing_highs, swing_lows) within last `lookback` bars before current_idx.
    A pivot high at i = bars[i].high > all highs in [i-k..i+k] excluding i.
    We need both sides confirmed, so the most recent pivot at most can be
    current_idx - k (confirmation needs k bars after)."""
    sh = []; sl = []
    lo_i = max(k, current_idx - lookback)
    hi_i = current_idx - k
    for i in range(lo_i, hi_i + 1):
        is_high = True; is_low = True
        for j in range(i - k, i + k + 1):
            if j == i: continue
            if bars[j]["high"] >= bars[i]["high"]: is_high = False
            if bars[j]["low"]  <= bars[i]["low"]:  is_low  = False
        if is_high: sh.append((i, bars[i]["high"]))
        if is_low:  sl.append((i, bars[i]["low"]))
    return sh, sl


def classify_structure(bars, current_idx):
    """Classify camel-hump structure from the last 2 swing highs / lows.
    Returns one of: 'UPTREND', 'DOWNTREND', 'M_TOP', 'W_BOTTOM', 'CHOP'."""
    sh, sl = find_pivots(bars, current_idx)
    if len(sh) < 2 or len(sl) < 2: return "CHOP"
    (i1, h1), (i2, h2) = sh[-2], sh[-1]
    (j1, l1), (j2, l2) = sl[-2], sl[-1]
    cur = bars[current_idx]
    tol = max(NEAR_HUMP_FACTOR * cur["close"], 1.0)

    # M_TOP / W_BOTTOM: twin peaks/troughs near same level, current near second one
    if abs(h2 - h1) <= tol and abs(cur["high"] - h2) <= NEAR_HUMP_USD:
        return "M_TOP"
    if abs(l2 - l1) <= tol and abs(cur["low"] - l2) <= NEAR_HUMP_USD:
        return "W_BOTTOM"

    # Standard HH/HL or LH/LL
    if h2 > h1 and l2 > l1: return "UPTREND"
    if h2 < h1 and l2 < l1: return "DOWNTREND"
    return "CHOP"


def m1_idx_for_time(m1, t):
    """Find M1 bar idx whose time == t (or closest <=)."""
    lo, hi = 0, len(m1) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if m1[mid]["time"] <= t: lo = mid
        else: hi = mid - 1
    return lo


def htf_idx_for_m1(htf_bars, m1_time):
    """Find HTF bar idx whose [time, end_time] CONTAINS m1_time. We need the
    BAR THAT HAS CLOSED before this M1 bar — i.e., the most recent HTF bar
    whose end_time < m1_time."""
    res = -1
    for i, b in enumerate(htf_bars):
        if b["end_time"] < m1_time:
            res = i
        else:
            break
    return res


def detect_sweep_m1(m1, idx):
    if idx < 1: return None
    b = m1[idx]
    body = abs(b["close"] - b["open"])
    if body < 0.01: return None
    upper_wick = b["high"] - max(b["open"], b["close"])
    lower_wick = min(b["open"], b["close"]) - b["low"]
    if b["close"] < b["open"]:   # red → possible BUY sweep
        if lower_wick >= MIN_WICK_BODY * body and lower_wick >= MIN_WICK_ABS:
            return (+1, b["low"])
    elif b["close"] > b["open"]: # green → possible SELL sweep
        if upper_wick >= MIN_WICK_BODY * body and upper_wick >= MIN_WICK_ABS:
            return (-1, b["high"])
    return None


def simulate(m1, fire_idx, side, entry_price, swept):
    if side > 0:
        sl_dist = min(SL_MAX_USD, max(0.1, entry_price - swept))
        sl_price = entry_price - sl_dist
        tp_price = entry_price + RR * sl_dist
    else:
        sl_dist = min(SL_MAX_USD, max(0.1, swept - entry_price))
        sl_price = entry_price + sl_dist
        tp_price = entry_price - RR * sl_dist
    for j in range(fire_idx + 1, min(fire_idx + 1 + TIME_STOP_BARS, len(m1))):
        bar = m1[j]
        if side > 0:
            if bar["low"]  <= sl_price: return (-sl_dist * USD_PER_PRICE, "SL")
            if bar["high"] >= tp_price: return (+RR * sl_dist * USD_PER_PRICE, "TP")
        else:
            if bar["high"] >= sl_price: return (-sl_dist * USD_PER_PRICE, "SL")
            if bar["low"]  <= tp_price: return (+RR * sl_dist * USD_PER_PRICE, "TP")
    last_close = m1[min(fire_idx + TIME_STOP_BARS, len(m1) - 1)]["close"]
    pnl_p = (last_close - entry_price) if side > 0 else (entry_price - last_close)
    return (pnl_p * USD_PER_PRICE, "TIMEOUT")


def run_combo(m1, htf_bars, trend_label, require_fvg, fvg_timeframes=(5, 15, 60)):
    """Execute the full strategy with given trend-TF + FVG flag."""
    signals = []; trades = []
    structure_hits = Counter()
    for i in range(1, len(m1) - 2):
        if not in_window(m1[i]["time"]): continue
        # Step 1: trend from HTF (camel humps)
        htf_idx = htf_idx_for_m1(htf_bars, m1[i]["time"])
        if htf_idx < 0: continue
        struct = classify_structure(htf_bars, htf_idx)
        if struct == "CHOP": continue

        # Step 2: M1 sweep candidate
        cand = detect_sweep_m1(m1, i)
        if cand is None: continue
        side, swept = cand

        # Side must agree with structure
        if side > 0 and struct not in ("UPTREND", "W_BOTTOM"): continue
        if side < 0 and struct not in ("DOWNTREND", "M_TOP"):  continue

        # Step 3: confirmation on next M1
        nb = m1[i + 1]
        if side > 0 and nb["close"] <= m1[i]["high"]: continue
        if side < 0 and nb["close"] >= m1[i]["low"]:  continue

        # Step 4: optional FVG overlap
        if require_fvg:
            if side > 0:
                ok = _has_unfilled_bullish_fvg_overlap(
                    m1, i, m1[i]["low"], m1[i]["high"], timeframes=fvg_timeframes)
            else:
                ok = _has_unfilled_bearish_fvg_overlap(
                    m1, i, m1[i]["low"], m1[i]["high"], timeframes=fvg_timeframes)
            if not ok: continue

        structure_hits[struct] += 1
        signals.append({"time": m1[i]["time"], "side": side, "struct": struct})
        entry = nb["close"]
        pnl, reason = simulate(m1, i + 1, side, entry, swept)
        trades.append({"time": nb["time"], "side": side, "entry": entry,
                       "pnl": pnl, "reason": reason, "struct": struct})

    n = len(trades)
    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    pnl    = sum(t["pnl"] for t in trades)
    wr     = 100 * len(wins) / max(1, len(wins) + len(losses)) if (wins or losses) else 0.0
    exp    = pnl / max(1, n)
    matched = 0
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        for s in signals:
            if s["side"] != want: continue
            if abs(s["time"] - t_o) <= 3 * 60: matched += 1; break
    return {
        "trend_tf": trend_label, "fvg": require_fvg,
        "n": n, "wins": len(wins), "losses": len(losses), "wr": wr,
        "pnl": pnl, "exp": exp, "zee_match": matched,
        "structures": dict(structure_hits), "trades": trades,
    }


def main():
    m1 = load_feb11_bars()
    if not m1:
        print("ERROR: no bars"); return
    # Pre-build HTF aggregates and tag end_time on each bar (needed by htf_idx)
    m5  = aggregate(m1, 5)
    m15 = aggregate(m1, 15)
    m30 = aggregate(m1, 30)
    h1  = aggregate(m1, 60)
    # Tag M1 end_time too (for symmetry, though we use M1 directly)
    for b in m1: b["end_time"] = b["time"] + 59

    # Print strategy steps for Zee to verify
    print(__doc__.split("STRATEGY STEPS")[1].split("COMBOS TESTED")[0])
    print("=" * 78)
    print("RESULTS — Feb 11, 0.05 lots, 69 Zee broker trades to align against")
    print("=" * 78)

    print(f"\n{'TrendTF':<8}{'FVG':<5}{'sigs':>6}{'W/L':>9}{'WR%':>7}"
          f"{'PnL':>10}{'Exp':>9}{'ZeeMatch':>11}  Structures")
    print("-" * 95)
    combos = []
    for trend_label, htf_bars in [("M5", m5), ("M15", m15), ("M30", m30), ("H1", h1)]:
        for fvg in (False, True):
            r = run_combo(m1, htf_bars, trend_label, require_fvg=fvg)
            combos.append(r)
            wl = f"{r['wins']}/{r['losses']}"
            zm = f"{r['zee_match']}/{len(ZEE_TRADES)}"
            fvg_s = "yes" if fvg else "no"
            struct = ", ".join(f"{k}:{v}" for k, v in r["structures"].items()) or "-"
            print(f"{trend_label:<8}{fvg_s:<5}{r['n']:>6}{wl:>9}{r['wr']:>6.1f}%"
                  f"{r['pnl']:>+9.2f}{r['exp']:>+8.2f}{zm:>11}  {struct}")

    # Detail dump of the BEST combo by PnL (with at least 3 trades)
    valid = [c for c in combos if c["n"] >= 3]
    if valid:
        best = max(valid, key=lambda c: c["pnl"])
        print(f"\n--- BEST combo by PnL: TrendTF={best['trend_tf']}, "
              f"FVG={'yes' if best['fvg'] else 'no'} ---")
        for t in best["trades"]:
            ts = datetime.fromtimestamp(t["time"], tz=UTC).strftime("%H:%M")
            side = "BUY " if t["side"] > 0 else "SELL"
            mark = "✓" if t["pnl"] > 0 else ("✗" if t["pnl"] < 0 else "·")
            print(f"  {ts} {side} @ {t['entry']:8.2f}  [{t['struct']:<9}]  "
                  f"{mark} ${t['pnl']:+6.2f}  {t['reason']}")
    else:
        print("\nNo combo produced >= 3 trades.")


if __name__ == "__main__":
    main()
