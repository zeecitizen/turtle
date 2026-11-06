"""
Filter Relaxation Backtest Framework (2026-05-05 night session)

Run any number of filter relaxations against historical EA logs + tick CSVs.
For each candidate relaxation, identifies SKIP MAIN events that the new
threshold would have unblocked, simulates a 0.30-lot main fire from the
tick stream, applies current EA exit rules, and aggregates P&L per day.

Decision rule: only deploy a relaxation if
  - Net P&L > 0 across all valid days
  - No single day shows < -$120 hypothetical loss
  - Fear-ideal trip rate < 25% of allowed trades
  - At least 5 trades sampled

Source data:
  EA logs:    %APPDATA%\\...\\MQL5\\Logs\\YYYYMMDD.log (UTF-16 LE)
  Tick CSV:   %COMMON%\\Files\\shano_ticks_YYYY-MM-DD.csv
  Hawk log:   monitor\\shano_hawk.log (FIRE direction)
"""
import re
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs")
TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
HAWK_LOG = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\shano_hawk.log")
REPORT_PATH = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\RELAXATION_REPORT.md")

# Current EA exit-rule parameters (matches shano_config.json, post-tuning 2026-05-05)
LOTS = 0.30
DOLLAR_PER_PT = LOTS * 100.0
FEAR_IDEAL = 60.0
WASHOUT = 180.0
TRAIL_TRIGGER = 25.0
TRAIL_DROP = 8.0
NO_GREEN_SEC = 60
NO_GREEN_PEAK = 3.0
WINDOW_SEC = 300
SLIP_COST = 1.0
DEDUP_WINDOW_SEC = 60
BROKER_OFFSET_HOURS = 1


def load_ticks(date_str):
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists():
        return []
    ticks = []
    with f.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            try:
                ticks.append((datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S"), float(row[2]), float(row[3])))
            except (ValueError, IndexError):
                continue
    return ticks


def load_hawk_fires():
    fires = []
    if not HAWK_LOG.exists():
        return fires
    pat = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})[\d.]*\].+FIRE (BUY|SELL)")
    for line in HAWK_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.search(line)
        if m:
            try:
                ts_local = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
                fires.append((ts_local, m.group(2).lower()))
            except ValueError:
                continue
    return fires


def find_probe_dir(skip_ts_broker, fires):
    target_local = skip_ts_broker - timedelta(hours=BROKER_OFFSET_HOURS)
    best = None
    for ts, d in fires:
        if ts > target_local:
            continue
        delta = (target_local - ts).total_seconds()
        if delta > 300:
            continue
        if best is None or delta < best[0]:
            best = (delta, d)
    return best[1] if best else None


def find_tick(ticks, target_ts):
    lo, hi = 0, len(ticks) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if ticks[mid][0] < target_ts:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(ticks) and ticks[lo][0] >= target_ts:
        return lo, ticks[lo]
    return None, None


def simulate_main(ticks, start_idx, direction, entry_price):
    if start_idx is None or start_idx >= len(ticks):
        return ("no_data", 0.0, 0)
    start_ts = ticks[start_idx][0]
    peak_pnl = 0.0
    end_ts = start_ts + timedelta(seconds=WINDOW_SEC)
    pnl = 0.0
    age = 0
    for i in range(start_idx, len(ticks)):
        ts, bid, ask = ticks[i]
        if ts > end_ts:
            cur = bid if direction == "buy" else ask
            move_pts = (cur - entry_price) if direction == "buy" else (entry_price - cur)
            pnl = move_pts * DOLLAR_PER_PT - SLIP_COST
            age = int((ts - start_ts).total_seconds())
            return ("window_end", pnl, age)
        cur = bid if direction == "buy" else ask
        move_pts = (cur - entry_price) if direction == "buy" else (entry_price - cur)
        pnl = move_pts * DOLLAR_PER_PT - SLIP_COST
        peak_pnl = max(peak_pnl, pnl)
        age = int((ts - start_ts).total_seconds())
        if pnl <= -WASHOUT:
            return ("washout", -WASHOUT, age)
        if peak_pnl >= TRAIL_TRIGGER and (peak_pnl - pnl) >= TRAIL_DROP:
            return ("trail", peak_pnl - TRAIL_DROP, age)
        if pnl <= -FEAR_IDEAL:
            return ("fear_ideal", -FEAR_IDEAL, age)
        if age >= NO_GREEN_SEC and peak_pnl < NO_GREEN_PEAK and pnl < 0:
            return ("no_green", pnl, age)
    return ("eod", pnl, age)


# ─── Filter-specific skip parsers ──────────────────────────────────────────
# Each returns dict with fields needed to evaluate "would_allow" under new params.

def parse_uhv_skip(line):
    m = re.search(r"trigger close ([\d.]+) did NOT break (above|below) (high|low) of UHV bar (\d+) ago by margin ([\d.]+)pt \[H=([\d.]+) L=([\d.]+)", line)
    if not m: return None
    return {
        "type": "uhv",
        "trigger": float(m.group(1)),
        "side": m.group(2),  # "above" → BUY, "below" → SELL
        "margin": float(m.group(5)),
        "H": float(m.group(6)),
        "L": float(m.group(7)),
    }

def uhv_would_allow(skip, new_margin):
    """With new margin, would the trigger have broken through?"""
    if skip["side"] == "above":
        # Trigger must exceed H + new_margin
        return skip["trigger"] >= skip["H"] + new_margin
    else:
        # Trigger must drop below L - new_margin
        return skip["trigger"] <= skip["L"] - new_margin


def parse_spread_skip(line):
    m = re.search(r"spread filter \(current ([\d.]+) > ([\d.]+)x baseline ([\d.]+)\)", line)
    if not m: return None
    return {
        "type": "spread",
        "current": float(m.group(1)),
        "old_mult": float(m.group(2)),
        "baseline": float(m.group(3)),
    }

def spread_would_allow(skip, new_mult):
    return skip["current"] <= skip["baseline"] * new_mult


def parse_tickspeed_skip(line):
    m = re.search(r"UHV cross at (\d+)s > max (\d+)s", line)
    if not m: return None
    return {"type": "tick_speed", "actual": int(m.group(1)), "old_max": int(m.group(2))}

def tickspeed_would_allow(skip, new_max):
    return skip["actual"] <= new_max


# ─── Generic backtest runner ───────────────────────────────────────────────

def collect_skips(log_path, filter_type):
    """Walk log, extract all SKIP MAIN events of the given filter type with timestamps + parsed values."""
    raw = log_path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="ignore")
    parsers = {
        "uhv": parse_uhv_skip,
        "spread": parse_spread_skip,
        "tick_speed": parse_tickspeed_skip,
    }
    parser = parsers[filter_type]
    keywords = {
        "uhv": "UHV filter",
        "spread": "spread filter",
        "tick_speed": "tick-speed filter",
    }
    keyword = keywords[filter_type]
    out = []
    for line in raw.splitlines():
        if "SKIP MAIN" not in line or keyword not in line:
            continue
        m_ts = re.search(r"(\d{2}:\d{2}:\d{2})", line[:50])
        if not m_ts:
            continue
        parsed = parser(line)
        if not parsed:
            continue
        parsed["time_str"] = m_ts.group(1)
        out.append(parsed)
    # Dedup by time-window
    deduped = []
    last_ts = None
    for s in out:
        try:
            t = datetime.strptime(s["time_str"], "%H:%M:%S")
        except ValueError:
            continue
        if last_ts is None or (t - last_ts).total_seconds() > DEDUP_WINDOW_SEC:
            deduped.append(s)
            last_ts = t
    return deduped


def run_relaxation(filter_type, new_value, dates, fires, would_allow_fn):
    """Run backtest for a specific (filter_type, new_value) pair."""
    summary = {
        "filter": filter_type,
        "new_value": new_value,
        "by_day": [],
        "total_skips": 0,
        "total_allowed": 0,
        "wins": 0,
        "losses": 0,
        "fear_trips": 0,
        "trail_wins": 0,
        "no_green_exits": 0,
        "sum_pnl": 0.0,
        "trades": [],
    }
    for d in dates:
        log_date = d.replace("-", "")
        log_path = LOG_DIR / f"{log_date}.log"
        if not log_path.exists():
            continue
        skips = collect_skips(log_path, filter_type)
        ticks = load_ticks(d)
        if not ticks or not skips:
            summary["by_day"].append({"date": d, "skips": len(skips), "allowed": 0, "pnl": 0, "skipped": True})
            continue
        tick_date = ticks[0][0].date()
        day_pnl = 0.0
        day_allowed = 0
        day_fear = 0
        for s in skips:
            try:
                t_only = datetime.strptime(s["time_str"], "%H:%M:%S").time()
                ts = datetime.combine(tick_date, t_only)
            except ValueError:
                continue
            if not would_allow_fn(s, new_value):
                continue
            # Direction: from UHV side (above=buy, below=sell), or hawk fires for others
            if filter_type == "uhv":
                probe_dir = "buy" if s["side"] == "above" else "sell"
            else:
                probe_dir = find_probe_dir(ts, fires)
                if not probe_dir:
                    continue
            idx, tick = find_tick(ticks, ts)
            if idx is None:
                continue
            entry = tick[2] if probe_dir == "buy" else tick[1]
            reason, pnl, age = simulate_main(ticks, idx, probe_dir, entry)
            summary["total_allowed"] += 1
            day_allowed += 1
            day_pnl += pnl
            if pnl > 0:
                summary["wins"] += 1
            elif pnl < 0:
                summary["losses"] += 1
            if reason == "fear_ideal":
                summary["fear_trips"] += 1
                day_fear += 1
            elif reason == "trail":
                summary["trail_wins"] += 1
            elif reason == "no_green":
                summary["no_green_exits"] += 1
            summary["trades"].append({"date": d, "time": s["time_str"], "dir": probe_dir,
                                      "reason": reason, "pnl": round(pnl, 2)})
        summary["total_skips"] += len(skips)
        summary["sum_pnl"] += day_pnl
        summary["by_day"].append({"date": d, "skips": len(skips), "allowed": day_allowed,
                                   "pnl": round(day_pnl, 2), "fear_trips": day_fear})
    summary["sum_pnl"] = round(summary["sum_pnl"], 2)
    return summary


def passes_decision_rule(s):
    """Strict gate: deploy only if ALL of these hold."""
    if s["sum_pnl"] <= 0: return (False, "net negative or zero")
    if s["total_allowed"] < 5: return (False, "sample too small (<5 trades)")
    if any(d.get("pnl", 0) < -120 for d in s["by_day"]):
        return (False, "single-day loss > -$120")
    fear_rate = s["fear_trips"] / max(1, s["total_allowed"])
    if fear_rate >= 0.25: return (False, f"fear-trip rate {fear_rate*100:.0f}% >= 25%")
    return (True, "passes all gates")


def main():
    fires = load_hawk_fires()
    print(f"Loaded {len(fires)} FIRE events from shano_hawk.log\n")
    dates = ["2026-04-29", "2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05"]

    # Each test: (filter_type, new_value, would_allow_fn, label)
    tests = [
        ("uhv",        0.15, uhv_would_allow,       "UHV margin 0.30 -> 0.15"),
        ("uhv",        0.10, uhv_would_allow,       "UHV margin 0.30 -> 0.10"),
        ("uhv",        0.00, uhv_would_allow,       "UHV margin 0.30 -> 0.00"),
        ("spread",     1.50, spread_would_allow,    "Spread mult 1.20 -> 1.50"),
        ("spread",     2.00, spread_would_allow,    "Spread mult 1.20 -> 2.00"),
        ("tick_speed", 25,   tickspeed_would_allow, "Tick-speed 15s -> 25s"),
        ("tick_speed", 30,   tickspeed_would_allow, "Tick-speed 15s -> 30s"),
        ("tick_speed", 60,   tickspeed_would_allow, "Tick-speed 15s -> 60s"),
    ]

    results = []
    for ftype, newv, fn, label in tests:
        s = run_relaxation(ftype, newv, dates, fires, fn)
        s["label"] = label
        ok, reason = passes_decision_rule(s)
        s["pass"] = ok
        s["pass_reason"] = reason
        results.append(s)

    # Print summary table
    print(f"{'Test':<32} {'Skips':>6} {'Allow':>6} {'Wins':>5} {'Loss':>5} {'Fear':>5} "
          f"{'Trail':>6} {'NoGrn':>6} {'Net P&L':>10} {'Verdict':<10}")
    print("-" * 110)
    for r in results:
        verdict = "DEPLOY" if r["pass"] else "skip"
        print(f"{r['label']:<32} {r['total_skips']:>6} {r['total_allowed']:>6} "
              f"{r['wins']:>5} {r['losses']:>5} {r['fear_trips']:>5} {r['trail_wins']:>6} "
              f"{r['no_green_exits']:>6} ${r['sum_pnl']:>+9.2f} {verdict:<10}")

    # Detailed per-day for passing tests
    print()
    deployable = [r for r in results if r["pass"]]
    if deployable:
        print(f"=== DEPLOYABLE: {len(deployable)} relaxation(s) ===")
        for r in deployable:
            print(f"\n>>> {r['label']}  (Net ${r['sum_pnl']:+.2f}, {r['total_allowed']} trades, {r['fear_trips']} fear)")
            for d in r["by_day"]:
                if d.get("skipped"):
                    continue
                print(f"   {d['date']}: skips={d['skips']:>3} allowed={d['allowed']:>3} "
                      f"pnl=${d['pnl']:>+8.2f} fear_trips={d.get('fear_trips',0)}")
    else:
        print("=== NO DEPLOYABLE RELAXATIONS — keep filters as-is ===")
        print("Reasons for failure:")
        for r in results:
            print(f"  {r['label']}: {r['pass_reason']}")

    # Write report
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# Filter Relaxation Backtest — {datetime.now().isoformat(timespec='minutes')}\n\n")
        f.write(f"Tested {len(tests)} relaxations across {len(dates)} days. ")
        f.write(f"Deployable: {len(deployable)}.\n\n")
        f.write("## Summary\n\n")
        f.write("| Test | Skips | Allow | Wins | Loss | Fear | Trail | NoGreen | Net P&L | Verdict |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in results:
            verdict = "**DEPLOY**" if r["pass"] else r["pass_reason"]
            f.write(f"| {r['label']} | {r['total_skips']} | {r['total_allowed']} | "
                    f"{r['wins']} | {r['losses']} | {r['fear_trips']} | {r['trail_wins']} | "
                    f"{r['no_green_exits']} | ${r['sum_pnl']:+.2f} | {verdict} |\n")
        f.write("\n## Per-day detail\n\n")
        for r in results:
            f.write(f"### {r['label']}\n\n")
            for d in r["by_day"]:
                if d.get("skipped"): continue
                f.write(f"- {d['date']}: skips={d['skips']}, allowed={d['allowed']}, "
                        f"pnl=${d['pnl']:+.2f}, fear={d.get('fear_trips',0)}\n")
            f.write("\n")
    print(f"\nReport written to {REPORT_PATH}")
    return results


if __name__ == "__main__":
    main()
