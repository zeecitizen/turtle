"""analyze_feb11_misses.py - cluster Zee's 54 missed Feb 11 entries.

For each Zee broker trade that NO detector caught (within +/-3min UHV / +/-5min
NS/ND, same side), record what the entry bar looked like and which detector
condition failed. Output is a hour-bucketed table + a "top failure reasons"
summary so we can see whether 80% of misses share one cause.

Inputs are reused from build_feb11_lab.py (same source of truth):
  - ZEE_TRADES (hardcoded broker history)
  - load_feb11_bars() (M1 from rev_eng or tick fallback)
  - detect_with_uhv_time / detect_ns_nd_pattern (the actual rejection logic)

Output: stdout table + monitor/strategy_lab/feb11_misses.csv for follow-up.
"""
import sys, csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from build_feb11_lab import (
    load_feb11_bars, ZEE_TRADES, run_detector_on_feb11, run_ns_nd_detector,
)
from backtest_v349_multiday import MAX_LOOKBACK


OUT_CSV = Path(__file__).parent / "feb11_misses.csv"


def find_caught_set():
    """Compute the set of (entry_unix, side) Zee trades that were caught
    by ANY detector. Uses the same windows as build_feb11_lab.coverage_stats."""
    bars = load_feb11_bars()
    if not bars:
        print("ERROR: no Feb 11 bars loaded"); sys.exit(1)
    uhv = run_detector_on_feb11(bars)
    nsnd = run_ns_nd_detector(bars)
    caught = set()
    for (open_hms, side, *_ ) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        want = +1 if side == "buy" else -1
        hit_u = any(s["side"] == want and abs(s["time"] - t_o) <= 3 * 60 for s in uhv)
        hit_n = any(s["side"] == want and abs(s["time"] - t_o) <= 5 * 60 for s in nsnd)
        if hit_u or hit_n:
            caught.add((t_o, side))
    return bars, caught


def bar_index_for_minute(bars, t_minute):
    """Find the bar whose minute floor == t_minute (entry-time minute)."""
    for i, b in enumerate(bars):
        if b["time"] == t_minute:
            return i
    # Fallback: closest bar
    return min(range(len(bars)), key=lambda i: abs(bars[i]["time"] - t_minute))


def diagnose_bar(bars, idx, want_side):
    """For a missed entry at bars[idx] with desired side (+1 buy / -1 sell),
    return a list of human-readable reasons the UHV-breakout detector would
    have rejected the bar. Mirrors the rules in detect_with_uhv_time().
    Empty list means 'rule-wise it COULD fire' — those misses indicate the
    detector ran fine but happened on a different minute (e.g. Zee entered
    1-2 min before the structural break)."""
    reasons = []
    if idx < MAX_LOOKBACK + 2:
        reasons.append("too_early_in_session")
        return reasons
    bo = bars[idx]
    body = bo["close"] - bo["open"]
    if want_side > 0 and body <= 0: reasons.append("bo_not_green")
    if want_side < 0 and body >= 0: reasons.append("bo_not_red")
    if reasons:
        return reasons   # if the bar's direction itself is wrong, no point

    # Look for UHV candidate of opposite colour with higher high already cleared
    if want_side > 0:   # buy: need RED uhv with high < bo.close, high not above bo.close
        uhv = None; uv = -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx - j
            if k < 0: break
            c = bars[k]
            if c["high"] >= bo["close"]: continue
            if c["close"] < c["open"] and c["vol"] > uv:
                uv = c["vol"]; uhv = c; uhv_i = k
        if uhv is None:
            reasons.append("no_red_uhv_candidate")
            return reasons
        prev_v = bars[uhv_i - 1]["vol"] if uhv_i - 1 >= 0          else -1
        next_v = bars[uhv_i + 1]["vol"] if uhv_i + 1 < len(bars)   else -1
        if not (uv > prev_v and uv > next_v):  reasons.append("uhv_not_local_peak")
        if bo["close"] <= uhv["high"]:         reasons.append("bo_close_below_uhv_high")
        if bo["open"]  >  uhv["high"]:         reasons.append("bo_open_above_uhv_high (gap)")
        if bo["vol"]   >= uhv["vol"]:          reasons.append("bo_vol_>=_uhv_vol")
    else:               # sell: need GREEN uhv with low > bo.close
        uhv = None; uv = -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx - j
            if k < 0: break
            c = bars[k]
            if c["low"] <= bo["close"]: continue
            if c["close"] > c["open"] and c["vol"] > uv:
                uv = c["vol"]; uhv = c; uhv_i = k
        if uhv is None:
            reasons.append("no_green_uhv_candidate")
            return reasons
        prev_v = bars[uhv_i - 1]["vol"] if uhv_i - 1 >= 0          else -1
        next_v = bars[uhv_i + 1]["vol"] if uhv_i + 1 < len(bars)   else -1
        if not (uv > prev_v and uv > next_v):  reasons.append("uhv_not_local_peak")
        if bo["close"] >= uhv["low"]:          reasons.append("bo_close_above_uhv_low")
        if bo["open"]  <  uhv["low"]:          reasons.append("bo_open_below_uhv_low (gap)")
        if bo["vol"]   >= uhv["vol"]:          reasons.append("bo_vol_>=_uhv_vol")

    return reasons or ["passed_rules_but_minute_mismatch"]


def main():
    bars, caught = find_caught_set()
    print(f"Loaded {len(bars)} M1 bars. Zee trades: {len(ZEE_TRADES)}. "
          f"Caught: {len(caught)}.  Missed: {len(ZEE_TRADES) - len(caught)}")
    print()

    misses = []
    for (open_hms, side, entry, close_hms, close_price, pnl) in ZEE_TRADES:
        t_o = int(datetime.strptime(f"2026.02.11 {open_hms}", "%Y.%m.%d %H:%M:%S")
                  .replace(tzinfo=UTC).timestamp())
        if (t_o, side) in caught:
            continue
        t_min = t_o - (t_o % 60)
        idx = bar_index_for_minute(bars, t_min)
        want = +1 if side == "buy" else -1
        reasons = diagnose_bar(bars, idx, want)
        misses.append({
            "open_hms":  open_hms,
            "hour":      open_hms[:2],
            "side":      side,
            "entry":     entry,
            "pnl":       pnl,
            "bar_idx":   idx,
            "bar_open":  round(bars[idx]["open"],  2),
            "bar_close": round(bars[idx]["close"], 2),
            "bar_high":  round(bars[idx]["high"],  2),
            "bar_low":   round(bars[idx]["low"],   2),
            "bar_vol":   bars[idx]["vol"],
            "body":      round(bars[idx]["close"] - bars[idx]["open"], 2),
            "reasons":   "|".join(reasons),
            "primary":   reasons[0] if reasons else "ok",
        })

    # By-hour breakdown
    by_hour = defaultdict(lambda: {"n": 0, "pnl": 0.0, "sides": Counter()})
    for m in misses:
        h = by_hour[m["hour"]]
        h["n"] += 1
        h["pnl"] += m["pnl"]
        h["sides"][m["side"]] += 1
    print("=== MISSED ENTRIES BY HOUR ===")
    print(f"{'Hour':<6} {'N':>4} {'PnL':>8}  {'B/S':<7}")
    for hour in sorted(by_hour):
        d = by_hour[hour]
        bs = f"{d['sides'].get('buy',0)}b/{d['sides'].get('sell',0)}s"
        print(f"{hour}:00  {d['n']:>4} ${d['pnl']:>+7.2f}  {bs}")
    print()

    # By primary reason
    by_reason = Counter(m["primary"] for m in misses)
    print("=== MISSED ENTRIES BY PRIMARY REJECTION REASON ===")
    for r, n in by_reason.most_common():
        pct = 100 * n / max(1, len(misses))
        print(f"  {n:>3}  ({pct:>5.1f}%)  {r}")
    print()

    # PnL of the misses (how much is this gap COSTING us)
    miss_pnl = sum(m["pnl"] for m in misses)
    win_misses = [m for m in misses if m["pnl"] > 0]
    loss_misses = [m for m in misses if m["pnl"] < 0]
    print(f"=== COST OF MISSED ENTRIES ===")
    print(f"  Total missed P&L: ${miss_pnl:+.2f}  "
          f"({len(win_misses)} wins / {len(loss_misses)} losses among the missed)")
    print(f"  Of Zee's full +$835.16 day, missed entries account for ${miss_pnl:+.2f}")
    print()

    # Dump to CSV for ad-hoc analysis
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(misses[0].keys()))
        w.writeheader()
        for m in misses:
            w.writerow(m)
    print(f"-> {OUT_CSV}  ({len(misses)} rows)")


if __name__ == "__main__":
    main()
