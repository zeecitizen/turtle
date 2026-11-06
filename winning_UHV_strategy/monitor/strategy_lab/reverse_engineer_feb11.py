"""
reverse_engineer_feb11.py — for each of Zee's 27 Feb 11 entries, find the UHV
candle that the breakout closed above (buy) or below (sell), measure it, and
verify it was during a retracement against the H1 trend.

Inputs (written by mt5/ExportFeb11Bars.mq5):
  %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\rev_eng_m1.csv
  %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\rev_eng_h1.csv

Method (strict lessons 1+2, no FVG/sweep/NSC):
  For BUY entries:
    1. Find the breakout candle = M1 bar at entry_time whose close ≈ entry_price.
    2. Look back up to 60 M1 bars for the UHV: the most-recent RED candle whose
       HIGH is below breakout's close AND no later red candle has a higher high.
       That's the UHV the breakout cleared.
    3. Measure UHV: vol vs prior-20 avg, vs other reds in retracement window,
       body% of range, bars-back.
    4. Measure breakout candle: body/range (momentum), vol vs UHV (should be lower).
    5. Validate retracement: was the price pulling DOWN in the bars between the
       previous swing high and the UHV?
    6. Validate uptrend: H1 trend at time of breakout (last 3 H1 closes).

  For SELL entries: mirror (find green UHV the breakout closed below, etc.)

Output:
  Per-trade report card + aggregate empirical bounds for each parameter.
"""
from __future__ import annotations
import csv
import os
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

COMMON_FILES = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON_FILES / "rev_eng_m1.csv"
H1_CSV = COMMON_FILES / "rev_eng_h1.csv"

# Zee's 27 Feb 11 setups (entry HH:MM:SS, side, entry_price)
# Broker time, same as MT5 server time.
ZEE_FEB11 = [
    ("01:32:19","buy",5045.07), ("01:59:04","buy",5042.17), ("02:09:38","sell",5040.68),
    ("02:29:02","buy",5039.03), ("16:49:07","buy",5047.93), ("16:52:21","buy",5050.77),
    ("16:54:10","buy",5056.74), ("16:58:03","buy",5064.26), ("17:02:45","buy",5055.71),
    ("17:36:11","buy",5056.53), ("17:36:13","buy",5057.05), ("17:37:26","buy",5045.82),
    ("17:49:59","buy",5048.32), ("18:24:18","buy",5059.26), ("18:41:50","buy",5078.10),
    ("19:08:59","sell",5083.28), ("19:11:05","sell",5083.39), ("19:11:51","sell",5083.79),
    ("19:20:34","sell",5084.21), ("19:26:06","sell",5089.16), ("19:29:31","buy",5086.34),
    ("19:32:48","buy",5084.71), ("19:36:19","buy",5082.91), ("19:38:39","buy",5083.28),
    ("19:38:59","buy",5086.33), ("19:41:59","sell",5091.09), ("19:42:26","sell",5093.18),
]

UHV_LOOKBACK_M1 = 60   # how many M1 bars back to search for the UHV
RETR_LOOKBACK   = 30   # bars used for retracement / volume-peak context


def parse_csv(path: Path):
    """Return list of dicts with bar fields, time as datetime."""
    rows = []
    with open(path, "r", encoding="ascii") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # MT5 TimeToString format: "2026.02.11 16:49:00"
            r["time"] = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
            for k in ("open", "high", "low", "close"):
                r[k] = float(r[k])
            for k in ("tick_volume", "real_volume", "spread"):
                r[k] = int(r[k])
            rows.append(r)
    rows.sort(key=lambda r: r["time"])
    return rows


def find_breakout_bar(m1, entry_dt):
    """Find the M1 bar whose minute brackets entry_dt."""
    # Entry within that minute
    target_min = entry_dt.replace(second=0)
    for r in m1:
        if r["time"] == target_min:
            return r
    return None


def find_uhv_buy(m1, idx_breakout, max_back=UHV_LOOKBACK_M1):
    """For a BUY: the breakout candle is a green momentum candle that closes
    above the UHV's high (lesson 2). Walk back collecting red candles that are
    INSIDE the retracement (i.e. their highs are below the breakout's high —
    they didn't break out themselves). Stop at the first candle whose high
    >= breakout.high (that's the start of the retracement / pre-retracement
    swing high). UHV = highest-volume red in that window.
    """
    bo = m1[idx_breakout]
    threshold = bo["high"]
    reds = []
    for j in range(1, max_back + 1):
        k = idx_breakout - j
        if k < 0: break
        c = m1[k]
        if c["high"] >= threshold:
            # Hit the pre-retracement swing high — retracement starts after this
            break
        if c["close"] < c["open"]:  # red
            reds.append((k, c))
    if not reds:
        return None
    best_k, _ = max(reds, key=lambda kc: kc[1]["tick_volume"])
    return best_k


def find_uhv_sell(m1, idx_breakout, max_back=UHV_LOOKBACK_M1):
    """Mirror for SELL: green candles below breakout.low until we hit the
    pre-retracement swing low."""
    bo = m1[idx_breakout]
    threshold = bo["low"]
    greens = []
    for j in range(1, max_back + 1):
        k = idx_breakout - j
        if k < 0: break
        c = m1[k]
        if c["low"] <= threshold:
            break
        if c["close"] > c["open"]:  # green
            greens.append((k, c))
    if not greens:
        return None
    best_k, _ = max(greens, key=lambda kc: kc[1]["tick_volume"])
    return best_k


def find_best_breakout(m1, m1_by_time, entry_dt, side):
    """Try 3 candidate breakout candles: entry-minute-1, entry-minute,
    entry-minute+1. Return the one that finds a UHV with the highest volume,
    or the entry-minute by default.
    """
    minute = entry_dt.replace(second=0)
    candidates = []
    for offset in (-1, 0, 1):
        bo_time = minute + timedelta(minutes=offset)
        idx = m1_by_time.get(bo_time)
        if idx is None:
            continue
        if side == "buy":
            uhv = find_uhv_buy(m1, idx)
        else:
            uhv = find_uhv_sell(m1, idx)
        if uhv is None:
            continue
        candidates.append((idx, uhv, m1[uhv]["tick_volume"], offset))
    if not candidates:
        # No UHV at any candidate — return entry-minute breakout for debugging
        return m1_by_time.get(minute), None, None
    # Prefer the candidate with the highest-volume UHV (lesson 2)
    candidates.sort(key=lambda x: (-x[2], abs(x[3])))
    idx_bo, idx_uhv, _, offset = candidates[0]
    return idx_bo, idx_uhv, offset


def measure(m1, idx_uhv, idx_breakout, side):
    """Compute the empirical metrics for one trade."""
    uhv = m1[idx_uhv]
    bo  = m1[idx_breakout]

    # 20-bar prior volume average (excluding UHV itself)
    prior_vols = [m1[idx_uhv - i]["tick_volume"] for i in range(1, 21) if idx_uhv - i >= 0]
    avg20 = statistics.mean(prior_vols) if prior_vols else 0
    vol_mult = uhv["tick_volume"] / avg20 if avg20 else 0

    # Local peak: max volume in retracement (UHV ± 15 bars)
    win_start = max(0, idx_uhv - 15)
    win_end   = min(len(m1) - 1, idx_uhv + 15)
    window_max_vol = max(m1[i]["tick_volume"] for i in range(win_start, win_end + 1))
    is_local_peak = uhv["tick_volume"] == window_max_vol

    # Body %
    rng = uhv["high"] - uhv["low"]
    body_pct = abs(uhv["close"] - uhv["open"]) / rng if rng > 0 else 0

    # Breakout candle vol vs UHV
    bo_vol_ratio = bo["tick_volume"] / uhv["tick_volume"] if uhv["tick_volume"] else 0

    # Breakout body/range ratio (momentum-ness)
    bo_rng = bo["high"] - bo["low"]
    bo_body_pct = abs(bo["close"] - bo["open"]) / bo_rng if bo_rng > 0 else 0

    # Wicks of breakout
    bo_upper_wick = (bo["high"] - max(bo["open"], bo["close"])) / bo_rng if bo_rng > 0 else 0
    bo_lower_wick = (min(bo["open"], bo["close"]) - bo["low"])  / bo_rng if bo_rng > 0 else 0

    # Bars from UHV to breakout
    bars_back = idx_breakout - idx_uhv

    # Retracement check: did price pull down (buy) / up (sell) before UHV?
    # Look at min/max in the 10 bars BEFORE the UHV
    pre_uhv = [m1[idx_uhv - i] for i in range(1, 11) if idx_uhv - i >= 0]
    if side == "buy":
        # In an uptrend retracement, we want recent bars to show prices DECREASING
        # toward the UHV. Use slope of closes.
        closes = [b["close"] for b in pre_uhv]
        # If pre-UHV closes are mostly DECREASING -> we're in a retracement (good)
        n_dec = sum(1 for i in range(len(closes)-1) if closes[i] < closes[i+1])  # closes is newest→oldest, so dec = retracing down
        retr_strength = n_dec / max(1, len(closes) - 1)
    else:
        closes = [b["close"] for b in pre_uhv]
        n_inc = sum(1 for i in range(len(closes)-1) if closes[i] > closes[i+1])
        retr_strength = n_inc / max(1, len(closes) - 1)

    return {
        "uhv_time": uhv["time"], "uhv_vol": uhv["tick_volume"],
        "uhv_avg20": avg20, "vol_mult": vol_mult, "is_local_peak": is_local_peak,
        "body_pct": body_pct, "rng": rng,
        "uhv_open": uhv["open"], "uhv_close": uhv["close"],
        "uhv_high": uhv["high"], "uhv_low": uhv["low"],
        "bars_back": bars_back,
        "bo_time": bo["time"], "bo_vol": bo["tick_volume"], "bo_vol_ratio": bo_vol_ratio,
        "bo_body_pct": bo_body_pct, "bo_upper_wick": bo_upper_wick, "bo_lower_wick": bo_lower_wick,
        "bo_close": bo["close"], "bo_high": bo["high"], "bo_low": bo["low"],
        "retr_strength": retr_strength,
    }


def h1_trend_at(h1, dt, side):
    """Check H1 trend at the time of breakout.
    Returns: 'up', 'down', 'flat'.
    Method: last 3 H1 closes — uptrend = HH+HL, downtrend = LH+LL.
    """
    # Find the H1 bar covering dt
    h1_idx = None
    for i, r in enumerate(h1):
        if r["time"] <= dt < r["time"] + timedelta(hours=1):
            h1_idx = i; break
    if h1_idx is None or h1_idx < 3:
        return "?"
    last3 = [h1[h1_idx-2], h1[h1_idx-1], h1[h1_idx]]
    closes = [b["close"] for b in last3]
    highs  = [b["high"]  for b in last3]
    lows   = [b["low"]   for b in last3]
    if highs[0] < highs[1] < highs[2] and lows[0] < lows[1] < lows[2]:
        return "up"
    if highs[0] > highs[1] > highs[2] and lows[0] > lows[1] > lows[2]:
        return "down"
    # Loose definition: just look at close slope
    if closes[2] > closes[0]: return "up-loose"
    if closes[2] < closes[0]: return "down-loose"
    return "flat"


def main():
    if not M1_CSV.exists():
        print(f"ERROR: {M1_CSV} not found.")
        print("Run mt5/ExportFeb11Bars.mq5 first (drag from MT5 Navigator → Experts).")
        sys.exit(1)
    if not H1_CSV.exists():
        print(f"WARN: {H1_CSV} not found — H1 trend check will be skipped.")
        h1 = []
    else:
        h1 = parse_csv(H1_CSV)

    m1 = parse_csv(M1_CSV)
    print(f"Loaded M1: {len(m1)} bars  ({m1[0]['time']} → {m1[-1]['time']})")
    print(f"Loaded H1: {len(h1)} bars" if h1 else "Loaded H1: 0")
    print()

    # Index m1 by time for O(1) lookup
    m1_by_time = {r["time"]: i for i, r in enumerate(m1)}

    results = []
    for entry_hms, side, price in ZEE_FEB11:
        entry_dt = datetime.strptime(f"2026.02.11 {entry_hms}", "%Y.%m.%d %H:%M:%S")
        idx_bo, idx_uhv, offset = find_best_breakout(m1, m1_by_time, entry_dt, side)
        if idx_uhv is None:
            # Diagnose: what's around the entry?
            mid = m1_by_time.get(entry_dt.replace(second=0))
            if mid is None:
                print(f"[{entry_hms} {side:4s}] BAR MISSING")
            else:
                bo = m1[mid]
                # Look for any red/green candles in the last 30 bars
                last30 = m1[max(0, mid-30):mid]
                if side == "buy":
                    reds = [c for c in last30 if c["close"] < c["open"]]
                    hi_reds = [c for c in reds if c["high"] < bo["high"]]
                    print(f"[{entry_hms} buy ] NO UHV: bo.high={bo['high']:.2f}, "
                          f"reds_in_last30={len(reds)}, reds_below_bo_high={len(hi_reds)}")
                else:
                    greens = [c for c in last30 if c["close"] > c["open"]]
                    lo_greens = [c for c in greens if c["low"] > bo["low"]]
                    print(f"[{entry_hms} sell] NO UHV: bo.low={bo['low']:.2f}, "
                          f"greens_in_last30={len(greens)}, greens_above_bo_low={len(lo_greens)}")
            continue

        m = measure(m1, idx_uhv, idx_bo, side)
        trend = h1_trend_at(h1, m["bo_time"], side) if h1 else "?"
        m["entry_hms"] = entry_hms
        m["side"]      = side
        m["entry_px"]  = price
        m["h1_trend"]  = trend
        m["bo_offset"] = offset
        results.append(m)

    # Per-trade report
    print(f"{'#':<3} {'time':<9} {'side':<5} {'UHV_time':<10} {'bk':<3} {'vol_mult':<9} {'peak':<5} {'body%':<6} {'rng':<5} {'bo_vol/uhv':<10} {'bo_body%':<8} {'retr':<5} {'h1':<10}")
    print("-" * 110)
    for i, r in enumerate(results, 1):
        print(f"{i:<3} {r['entry_hms']:<9} {r['side']:<5} "
              f"{r['uhv_time'].strftime('%H:%M:%S'):<10} {r['bars_back']:<3} "
              f"{r['vol_mult']:<9.2f} {'Y' if r['is_local_peak'] else 'N':<5} "
              f"{r['body_pct']*100:<6.1f} {r['rng']:<5.2f} "
              f"{r['bo_vol_ratio']:<10.2f} {r['bo_body_pct']*100:<8.1f} "
              f"{r['retr_strength']*100:<5.0f} {r['h1_trend']:<10}")

    # Aggregate stats
    if results:
        print()
        print("=" * 110)
        print("EMPIRICAL BOUNDS (across all detected UHVs)")
        print("=" * 110)
        def stat(label, vals, fmt="{:.2f}"):
            if not vals: return
            print(f"  {label:30s} min={fmt.format(min(vals))}  med={fmt.format(statistics.median(vals))}  mean={fmt.format(statistics.mean(vals))}  max={fmt.format(max(vals))}")
        stat("UHV vol_mult vs prior20", [r["vol_mult"] for r in results])
        stat("UHV body % of range",     [r["body_pct"]*100 for r in results], "{:.1f}%")
        stat("UHV range (points)",      [r["rng"] for r in results])
        stat("Bars from UHV to breakout", [r["bars_back"] for r in results], "{:.0f}")
        stat("Breakout vol / UHV vol",  [r["bo_vol_ratio"] for r in results])
        stat("Breakout body % of range",[r["bo_body_pct"]*100 for r in results], "{:.1f}%")
        stat("Retracement strength (% pre-UHV bars trending against trend)", [r["retr_strength"]*100 for r in results], "{:.0f}%")
        n_peak = sum(1 for r in results if r["is_local_peak"])
        print(f"  UHV is local-vol-peak in ±15 bars: {n_peak}/{len(results)} ({n_peak/len(results)*100:.0f}%)")
        # H1 trend agreement
        if h1:
            up_buys = sum(1 for r in results if r["side"] == "buy"  and "up"   in r["h1_trend"])
            n_buys  = sum(1 for r in results if r["side"] == "buy")
            dn_sells= sum(1 for r in results if r["side"] == "sell" and "down" in r["h1_trend"])
            n_sells = sum(1 for r in results if r["side"] == "sell")
            print(f"  H1 trend agrees with side: buys {up_buys}/{n_buys}, sells {dn_sells}/{n_sells}")


if __name__ == "__main__":
    main()
