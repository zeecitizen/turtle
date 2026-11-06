"""
no_timer_test.py — test Shano's hypothesis: remove the 50-second probe timeout
and let the -$3 fail rule (probeFail) handle exits.

For each probe in probe_shadow_results.csv:
  - Walk ticks from entry_time forward up to EXTENDED_HORIZON seconds
  - First tick where favorable >= probeConfirm → CONFIRM
  - First tick where adverse >= probeFail (-$3) → FAIL
  - Neither in EXTENDED_HORIZON → still time out (but at much longer window)

Compare confirm count vs current 50s timer, then for new confirms, simulate
main outcome and aggregate.
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

CONTRACT_SIZE = 100
PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45  # current live
PROBE_FAIL = 3.0      # current live ($3 adverse on 0.01 lot)
MAIN_LOTS = 0.40
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
FEAR_IDEAL = 50.0
MAIN_HORIZON_SEC = 600


def parse_ts(s):
    return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")


_TICK_CACHE = {}
def load_day_ticks(date):
    key = date.strftime("%Y-%m-%d")
    if key in _TICK_CACHE: return _TICK_CACHE[key]
    p = COMMON_DIR / f"shano_ticks_{key}.csv"
    out = []
    if p.exists():
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4: continue
                try:
                    dt = parse_ts(parts[0])
                    bid = float(parts[2]); ask = float(parts[3])
                    out.append((dt, bid, ask))
                except (ValueError, IndexError): continue
    _TICK_CACHE[key] = out
    return out


def ticks_in_range(t_start, t_end):
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        for tick in load_day_ticks(cur):
            if tick[0] < t_start: continue
            if tick[0] > t_end: break
            out.append(tick)
        cur += timedelta(days=1)
    return out


def replay_probe_no_timer(entry_time, entry_price, dir_sign, max_horizon_sec=300):
    """Walk ticks until probe confirms (+probeConfirm), fails (-probeFail), or
    horizon expires. Return (outcome, exit_time, exit_price, time_to_outcome_sec).

    outcome ∈ {'confirm', 'fail', 'timeout'}
    """
    horizon_end = entry_time + timedelta(seconds=max_horizon_sec)
    ticks = ticks_in_range(entry_time, horizon_end)
    for dt, bid, ask in ticks:
        if dir_sign == 1:  # buy probe
            fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            adv = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
        else:  # sell probe
            fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            adv = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
        if fav >= PROBE_CONFIRM:
            return ("confirm", dt, ask if dir_sign == 1 else bid, (dt - entry_time).total_seconds())
        if adv >= PROBE_FAIL:
            return ("fail", dt, ask if dir_sign == 1 else bid, (dt - entry_time).total_seconds())
    return ("timeout", None, None, max_horizon_sec)


def simulate_main(main_entry, dir_sign, ticks):
    if not ticks: return 0.0, "no_data"
    peak = 0.0; last_profit = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - main_entry) * MAIN_LOTS * CONTRACT_SIZE
        else:
            profit = (main_entry - ask) * MAIN_LOTS * CONTRACT_SIZE
        last_profit = profit
        if profit > peak: peak = profit
        if profit <= -FEAR_IDEAL:
            return round(profit, 2), "fearIdeal"
        if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP:
            return round(profit, 2), "trail"
    return round(last_profit, 2), "horizon_end"


def main():
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))
    print(f"Replaying {len(rows)} probes with NO 50s timeout (max horizon = 5 min)...")
    print()

    results_default = []  # current behavior (uses probe_shadow.py outcomes)
    results_notimer = []  # extended horizon

    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError):
            continue

        # Existing outcome (from probe_shadow.py — uses 50s actual close_time)
        actual_pnl = float(r["actual_pnl"]) if r.get("actual_pnl") not in (None, "", "None") else None
        existing_confirm = int(r.get("confirm_at_058", 0)) == 1 or float(r["mfe_dollars"] or 0) >= PROBE_CONFIRM
        results_default.append({
            "entry_time": entry_time,
            "dir": r["dir"],
            "actual_pnl": actual_pnl,
            "confirm": existing_confirm,
        })

        # No-timer outcome
        outcome, exit_time, exit_price, ttos = replay_probe_no_timer(entry_time, entry_price, dir_sign)
        if outcome == "confirm":
            # Simulate main from confirm tick forward
            main_horizon_end = exit_time + timedelta(seconds=MAIN_HORIZON_SEC)
            main_ticks = ticks_in_range(exit_time, main_horizon_end)
            main_pnl, _ = simulate_main(exit_price, dir_sign, main_ticks)
            results_notimer.append({
                "entry_time": entry_time, "dir": r["dir"],
                "outcome": "confirm",
                "main_pnl": main_pnl,
                "ttos": ttos,
            })
        elif outcome == "fail":
            results_notimer.append({
                "entry_time": entry_time, "dir": r["dir"],
                "outcome": "fail",
                "main_pnl": -PROBE_FAIL,  # rough probe-only loss
                "ttos": ttos,
            })
        else:
            results_notimer.append({
                "entry_time": entry_time, "dir": r["dir"],
                "outcome": "timeout",
                "main_pnl": 0,
                "ttos": ttos,
            })

    # Stats
    n_total = len(results_notimer)
    confirms = [r for r in results_notimer if r["outcome"] == "confirm"]
    fails = [r for r in results_notimer if r["outcome"] == "fail"]
    timeouts = [r for r in results_notimer if r["outcome"] == "timeout"]
    print(f"NO TIMER results (max horizon = 5 min):")
    print(f"  total probes:    {n_total}")
    print(f"  CONFIRMS:        {len(confirms)}  ({len(confirms)/n_total*100:.1f}%)")
    print(f"  FAILS (-$3):     {len(fails)}  ({len(fails)/n_total*100:.1f}%)")
    print(f"  TIMEOUTS @ 5min: {len(timeouts)}  ({len(timeouts)/n_total*100:.1f}%)")
    print()

    # For confirms, simulate main
    sim_total = sum(c["main_pnl"] for c in confirms)
    wins = [c for c in confirms if c["main_pnl"] > 0]
    losses = [c for c in confirms if c["main_pnl"] <= 0]
    wr = len(wins) / max(len(confirms), 1) * 100
    print(f"Main trade outcomes (confirmed probes only):")
    print(f"  fired mains:  {len(confirms)}")
    print(f"  WR:           {wr:.1f}%")
    print(f"  total P&L:    ${sim_total:+.2f}")
    print(f"  avg win:      ${sum(c['main_pnl'] for c in wins) / max(len(wins), 1):+.2f}")
    print(f"  avg loss:     ${sum(c['main_pnl'] for c in losses) / max(len(losses), 1):+.2f}")
    print()

    # Time-to-outcome distribution
    print("Time-to-outcome distribution (confirms + fails):")
    by_bucket = defaultdict(int)
    for r in results_notimer:
        if r["outcome"] in ("confirm", "fail"):
            t = r["ttos"]
            if t < 10: bucket = "<10s"
            elif t < 30: bucket = "10-30s"
            elif t < 50: bucket = "30-50s"
            elif t < 90: bucket = "50-90s"
            elif t < 180: bucket = "90s-3min"
            else: bucket = ">3min"
            by_bucket[bucket] += 1
    for b in ["<10s", "10-30s", "30-50s", "50-90s", "90s-3min", ">3min"]:
        n = by_bucket.get(b, 0)
        marker = " <-- BEYOND 50s timer!" if b in ("50-90s", "90s-3min", ">3min") and n > 0 else ""
        print(f"  {b:<12}: {n}{marker}")

    # Compare default vs no-timer
    print()
    print("=" * 90)
    print("COMPARISON: 50s timer vs NO timer")
    print("=" * 90)
    default_confirms = sum(1 for r in results_default if r.get("confirm"))
    notimer_confirms = len(confirms)
    delta = notimer_confirms - default_confirms
    print(f"  Default (50s timer):  {default_confirms} confirms")
    print(f"  NO timer (5min cap):  {notimer_confirms} confirms ({delta:+d} change)")

    by_day = defaultdict(float)
    for c in confirms:
        by_day[c["entry_time"].strftime("%Y-%m-%d")] += c["main_pnl"]
    print()
    print("Daily breakdown (no-timer mains):")
    for d, p in sorted(by_day.items()):
        print(f"  {d}: ${p:+.2f}")


if __name__ == "__main__":
    main()
