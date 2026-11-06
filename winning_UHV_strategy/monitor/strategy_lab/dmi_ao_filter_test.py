"""
dmi_ao_filter_test.py — test the teacher's two-filter theory:

  1. DMI+ > 10 AND was < 10 within last N bars (crossing UP through 10)
  2. AO < 0 AND increasing (crossing UP toward zero from below)

Theory: combined, these signal momentum buildup → expect positive bursts.

Builds 1-min bars from tick CSV, computes DMI(14) and AO(5,34) at each probe's
entry time, then bucketizes WR by filter outcome.
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

DMI_PERIOD = 14
AO_FAST = 5
AO_SLOW = 34
DMI_THRESHOLD = 10
DMI_LOOKBACK = 14  # bars to look back for "was below 10"


def parse_ts(s):
    return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")


def load_all_ticks():
    out = []
    for p in sorted(COMMON_DIR.glob("shano_ticks_*.csv")):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                next(f, None)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 4: continue
                    try:
                        dt = parse_ts(parts[0])
                        bid = float(parts[2]); ask = float(parts[3])
                        out.append((dt, bid, ask))
                    except (ValueError, IndexError):
                        continue
        except OSError:
            pass
    return out


def build_1m_bars(ticks):
    bars = []
    cur_min = None; o = h = l = c = None
    for dt, bid, ask in ticks:
        mid = (bid + ask) / 2
        bm = dt.replace(second=0, microsecond=0)
        if cur_min is None:
            cur_min = bm; o = h = l = c = mid
        elif bm != cur_min:
            bars.append((cur_min, o, h, l, c))
            cur_min = bm; o = h = l = c = mid
        else:
            if mid > h: h = mid
            if mid < l: l = mid
            c = mid
    if cur_min is not None:
        bars.append((cur_min, o, h, l, c))
    return bars


def compute_dmi(bars, period=DMI_PERIOD):
    """Compute +DI and -DI using Wilder's smoothing.
    Returns (plus_di_list, minus_di_list, atr_list) — same length as bars, None for early bars."""
    n = len(bars)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        h = bars[i][2]; l = bars[i][3]
        ph = bars[i-1][2]; pl = bars[i-1][3]; pc = bars[i-1][4]
        up_move = h - ph
        dn_move = pl - l
        plus_dm[i]  = up_move if (up_move > dn_move and up_move > 0) else 0.0
        minus_dm[i] = dn_move if (dn_move > up_move and dn_move > 0) else 0.0
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))

    # Wilder's smoothing — initial sum then EMA-style
    plus_di = [None] * n
    minus_di = [None] * n
    atr = [None] * n
    if n <= period: return plus_di, minus_di, atr
    s_plus  = sum(plus_dm[1:period+1])
    s_minus = sum(minus_dm[1:period+1])
    s_tr    = sum(tr[1:period+1])
    if s_tr > 0:
        plus_di[period]  = 100 * s_plus  / s_tr
        minus_di[period] = 100 * s_minus / s_tr
        atr[period]      = s_tr / period
    for i in range(period + 1, n):
        s_plus  = s_plus  - s_plus / period  + plus_dm[i]
        s_minus = s_minus - s_minus / period + minus_dm[i]
        s_tr    = s_tr    - s_tr / period    + tr[i]
        if s_tr > 0:
            plus_di[i]  = 100 * s_plus  / s_tr
            minus_di[i] = 100 * s_minus / s_tr
            atr[i]      = s_tr / period
    return plus_di, minus_di, atr


def compute_ao(bars, fast=AO_FAST, slow=AO_SLOW):
    """AO = SMA(median, fast) - SMA(median, slow), where median = (h+l)/2."""
    n = len(bars)
    medians = [(b[2] + b[3]) / 2 for b in bars]
    ao = [None] * n
    for i in range(slow - 1, n):
        sma_fast = sum(medians[i-fast+1:i+1]) / fast
        sma_slow = sum(medians[i-slow+1:i+1]) / slow
        ao[i] = sma_fast - sma_slow
    return ao


def main():
    print("Loading ticks + building bars...")
    ticks = load_all_ticks()
    bars = build_1m_bars(ticks)
    print(f"  {len(ticks)} ticks, {len(bars)} bars ({bars[0][0]} -> {bars[-1][0]})")

    print("Computing DMI(14) and AO(5,34)...")
    plus_di, minus_di, atr = compute_dmi(bars)
    ao = compute_ao(bars)
    bar_index_map = {b[0]: i for i, b in enumerate(bars)}

    # Run probe simulation
    import sys
    sys.path.insert(0, str(LAB_DIR))
    from feature_analyzer import simulate_with_features

    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    feats = []; history = []
    for r in rows:
        f = simulate_with_features(r, history)
        if f is None: continue
        feats.append(f)
        history.append({"dir": f["dir_sign"], "pnl": f["main_pnl"], "close_time": f["confirm_time"]})
    print(f"  {len(feats)} confirmed probes")

    # For each probe, evaluate teacher's filters
    enriched = []
    for f in feats:
        bm = f["entry_time"].replace(second=0, microsecond=0)
        idx = bar_index_map.get(bm)
        if idx is None:
            for d in range(1, 30):
                t = bm - timedelta(minutes=d)
                idx = bar_index_map.get(t)
                if idx is not None: break
        if idx is None or idx < AO_SLOW:
            f["dmi_plus"] = None; f["dmi_minus"] = None; f["ao"] = None
            f["filter1_long"] = None; f["filter1_short"] = None; f["filter2_long"] = None; f["filter2_short"] = None
            enriched.append(f); continue

        f["dmi_plus"]  = plus_di[idx]
        f["dmi_minus"] = minus_di[idx]
        f["ao"]        = ao[idx]

        # Filter 1 (LONG variant): +DI > 10 AND was < 10 within lookback
        if f["dmi_plus"] is not None and f["dmi_plus"] > DMI_THRESHOLD:
            crossed = False
            for k in range(1, min(DMI_LOOKBACK + 1, idx + 1)):
                v = plus_di[idx - k]
                if v is not None and v < DMI_THRESHOLD:
                    crossed = True; break
            f["filter1_long"] = crossed
        else:
            f["filter1_long"] = False

        # Filter 1 (SHORT variant, mirror): -DI > 10 AND was < 10 within lookback
        if f["dmi_minus"] is not None and f["dmi_minus"] > DMI_THRESHOLD:
            crossed = False
            for k in range(1, min(DMI_LOOKBACK + 1, idx + 1)):
                v = minus_di[idx - k]
                if v is not None and v < DMI_THRESHOLD:
                    crossed = True; break
            f["filter1_short"] = crossed
        else:
            f["filter1_short"] = False

        # Filter 2 (LONG variant): AO < 0 AND increasing (last 1-3 bars)
        if f["ao"] is not None and f["ao"] < 0:
            ao_prev1 = ao[idx-1] if idx > 0 else None
            ao_prev2 = ao[idx-2] if idx > 1 else None
            increasing = (ao_prev1 is not None and f["ao"] > ao_prev1) and \
                         (ao_prev2 is None or ao_prev1 >= ao_prev2 - 0.01)
            f["filter2_long"] = increasing
        else:
            f["filter2_long"] = False

        # Filter 2 (SHORT variant, mirror): AO > 0 AND decreasing
        if f["ao"] is not None and f["ao"] > 0:
            ao_prev1 = ao[idx-1] if idx > 0 else None
            ao_prev2 = ao[idx-2] if idx > 1 else None
            decreasing = (ao_prev1 is not None and f["ao"] < ao_prev1) and \
                         (ao_prev2 is None or ao_prev1 <= ao_prev2 + 0.01)
            f["filter2_short"] = decreasing
        else:
            f["filter2_short"] = False

        enriched.append(f)

    # Stats
    valid = [f for f in enriched if f.get("dmi_plus") is not None]
    print(f"  {len(valid)} probes with valid DMI/AO (others dropped due to insufficient history)")
    print()
    overall_wr = sum(1 for f in valid if f["win"]) / max(len(valid), 1) * 100
    print(f"Overall WR on valid sample: {overall_wr:.1f}%")
    print()

    # ── Filter outcomes ──
    print("=" * 100)
    print("FILTER ANALYSIS — does the teacher's theory help?")
    print("=" * 100)

    def show(name, predicate):
        sub = [f for f in valid if predicate(f)]
        n = len(sub); w = sum(1 for f in sub if f["win"])
        wr = w / max(n, 1) * 100
        avg = sum(f["main_pnl"] for f in sub) / max(n, 1)
        total = sum(f["main_pnl"] for f in sub)
        marker = " *** PROMISING ***" if wr >= overall_wr + 12 and n >= 5 else ""
        print(f"  {name:<60}  n={n:<4}wins={w:<4}WR={wr:<5.1f}%  avg=${avg:+7.2f}  total=${total:+8.2f}{marker}")

    print()
    print("[BUY-side filters — match teacher's theory exactly]")
    show("BUY probes only (overall)",
         lambda f: f["dir_sign"] == 1)
    show("BUY + filter1 (DMI+ > 10, crossing up)",
         lambda f: f["dir_sign"] == 1 and f["filter1_long"])
    show("BUY + filter2 (AO < 0, rising)",
         lambda f: f["dir_sign"] == 1 and f["filter2_long"])
    show("BUY + BOTH filters (teacher's full rule)",
         lambda f: f["dir_sign"] == 1 and f["filter1_long"] and f["filter2_long"])
    show("BUY + EITHER filter",
         lambda f: f["dir_sign"] == 1 and (f["filter1_long"] or f["filter2_long"]))

    print()
    print("[SELL-side filters — mirror of teacher's theory]")
    show("SELL probes only (overall)",
         lambda f: f["dir_sign"] == -1)
    show("SELL + filter1 (DMI- > 10, crossing up)",
         lambda f: f["dir_sign"] == -1 and f["filter1_short"])
    show("SELL + filter2 (AO > 0, falling)",
         lambda f: f["dir_sign"] == -1 and f["filter2_short"])
    show("SELL + BOTH filters (mirror)",
         lambda f: f["dir_sign"] == -1 and f["filter1_short"] and f["filter2_short"])

    print()
    print("[Combined: BOTH directions with their respective filters]")
    show("Combined: BUY-with-both OR SELL-with-both",
         lambda f: (f["dir_sign"] == 1 and f["filter1_long"] and f["filter2_long"]) or
                   (f["dir_sign"] == -1 and f["filter1_short"] and f["filter2_short"]))
    show("Combined: BUY-either OR SELL-either",
         lambda f: (f["dir_sign"] == 1 and (f["filter1_long"] or f["filter2_long"])) or
                   (f["dir_sign"] == -1 and (f["filter1_short"] or f["filter2_short"])))


if __name__ == "__main__":
    main()
