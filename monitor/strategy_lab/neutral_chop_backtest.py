"""
Neutral-Chop Filter Backtest (2026-05-05)

Question: would relaxing the "NEUTRAL chop zone" sub-rule of the trend filter
have improved or hurt P&L over the last 5 days?

Method: for every SKIP MAIN with "NEUTRAL chop zone" reason in EA logs,
simulate firing a 0.30-lot main at the trigger price, applying current EA exit
rules (TRAIL @ $25/$8, FEAR_IDEAL @ -$60, MAIN_NO_GREEN @ 60s peak<$3, WASHOUT @ -$180,
end-of-window @ 300s). Aggregate hypothetical P&L per day.

Source data:
  EA logs:    %APPDATA%/.../MQL5/Logs/YYYYMMDD.log (UTF-16 LE, contains SKIP events)
  Tick data:  %COMMON%/Files/shano_ticks_YYYY-MM-DD.csv (1 tick/sec, ts_broker,bid,ask)
"""
import re
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs")
TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
HAWK_LOG = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\shano_hawk.log")


def load_hawk_fires():
    """Build list of (datetime_local, direction) FIRE events from shano_hawk.log.
    Hawk log uses local time (Berlin) — broker time differs. We assume the tick
    CSV timestamps are broker time and apply offset later if needed.
    """
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


# Broker time = local Berlin + 1h (server is UTC+3, Berlin is UTC+2 in summer).
# We'll match FIRE (local) to SKIP (broker) by adding 1h to FIRE.
BROKER_OFFSET_HOURS = 1

# Current EA exit-rule parameters (matches shano_config.json after today's tuning)
LOTS = 0.30
DOLLAR_PER_PT = LOTS * 100.0  # 0.30 lots × 100 oz = $30/point
FEAR_IDEAL = 60.0
WASHOUT = 180.0
TRAIL_TRIGGER = 25.0
TRAIL_DROP = 8.0
NO_GREEN_SEC = 60
NO_GREEN_PEAK = 3.0
WINDOW_SEC = 300
SLIP_COST = 1.0  # ~1 point round-trip slip+spread cost (calibration value)


def load_ticks(date_str):
    """Load tick CSV for a given YYYY-MM-DD date. Returns list of (ts, bid, ask)."""
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists():
        return []
    ticks = []
    with f.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for row in reader:
            try:
                ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S")
                bid = float(row[2])
                ask = float(row[3])
                ticks.append((ts, bid, ask))
            except (ValueError, IndexError):
                continue
    return ticks


def find_probe_dir(skip_ts_broker, fires):
    """Match a SKIP event (broker time) to the most recent FIRE within 5 minutes.
    fires is list of (local_dt, direction). Adds BROKER_OFFSET_HOURS to convert.
    """
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


def parse_log(log_path):
    """Parse EA log for SKIP MAIN events with neutral-chop reason.

    Each log line begins with: '<tag>\t0\tHH:MM:SS.mmm\t<source>\tShanoEA: <text>'.
    We need: timestamp (server time), probe direction, ema34, ema89.

    Probe direction we trace by walking forward from each SKIP back to the most
    recent PROBE CONFIRMED line (its ticket → previous PROBE OPENED line for direction).
    Easier: match every SKIP that has 'probe BUY' or 'probe SELL' in OTHER skip
    lines in same probe-window, OR fallback to bias-direction inference.
    """
    raw = log_path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="ignore")
    lines = raw.splitlines()

    # Pre-pass: build ticket→direction map from MAIN OPENING lines (which include direction)
    ticket_to_dir = {}
    # Probe direction from "ticket=N | XAUUSD | 0.01 lots" — direction in subsequent lines.
    # Best signal: "OPENING MAIN BUY/SELL ... (probe=N)" — give us the original probe's direction.
    for line in lines:
        m = re.search(r"OPENING MAIN (BUY|SELL) [\d.]+ lots .+\(probe=(\d+)\)", line)
        if m:
            ticket_to_dir[m.group(2)] = m.group(1).lower()
        # Also pick up from "PROBE_CLOSE_WITH_MAIN | profit=$X @ price" pattern
        m2 = re.search(r"CLOSING XAUUSD ([\d.]+) lots (BUY|SELL) \| PROBE_CLOSE_WITH_MAIN.*ticket=(\d+)", line)
        if m2 and m2.group(1) == "0.01":
            ticket_to_dir[m2.group(3)] = m2.group(2).lower()

    skips = []
    last_probe_ticket = None
    last_probe_pnl = 0.0

    for i, line in enumerate(lines):
        # Track last probe seen (for direction tracing)
        m_pc = re.search(r"PROBE CONFIRMED ticket=(\d+) profit=\$(-?[\d.]+)", line)
        if m_pc:
            last_probe_ticket = m_pc.group(1)
            last_probe_pnl = float(m_pc.group(2))

        # Look for SKIP MAIN with NEUTRAL chop zone
        if "NEUTRAL chop zone" not in line:
            continue
        m_ema = re.search(r"EMA-34=([\d.]+)\s+EMA-89=([\d.]+)", line)
        if not m_ema:
            continue
        m_ts = re.search(r"(\d{2}:\d{2}:\d{2})", line[:50])
        if not m_ts:
            continue

        ema34 = float(m_ema.group(1))
        ema89 = float(m_ema.group(2))
        # Weak bias direction (we'll only allow probes that align)
        bias_dir = "buy" if ema34 > ema89 else "sell"

        # Probe direction — try map from MAIN OPENING tracing first, else infer from bias
        probe_dir = ticket_to_dir.get(last_probe_ticket) if last_probe_ticket else None

        skips.append({
            "time_str": m_ts.group(1),
            "ema34": ema34,
            "ema89": ema89,
            "bias_dir": bias_dir,
            "probe_dir": probe_dir,
            "probe_ticket": last_probe_ticket,
            "probe_pnl": last_probe_pnl,
        })
    return skips


def find_tick(ticks, target_ts):
    """Binary search for tick at-or-after target_ts. Returns (idx, tick) or (None, None)."""
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
    """Simulate a 0.30-lot main fire at entry_price (direction = buy/sell).

    Walks tick stream forward up to WINDOW_SEC. Applies current EA exit rules.
    Returns (exit_reason, pnl_dollars, age_sec).
    """
    if start_idx is None or start_idx >= len(ticks):
        return ("no_data", 0.0, 0)

    start_ts = ticks[start_idx][0]
    peak_pnl = 0.0
    end_ts = start_ts + timedelta(seconds=WINDOW_SEC)

    for i in range(start_idx, len(ticks)):
        ts, bid, ask = ticks[i]
        if ts > end_ts:
            # End-of-window — close at current
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

        # Exit checks (priority order, matching EA)
        if pnl <= -WASHOUT:
            return ("washout", -WASHOUT, age)
        if peak_pnl >= TRAIL_TRIGGER and (peak_pnl - pnl) >= TRAIL_DROP:
            return ("trail", peak_pnl - TRAIL_DROP, age)
        if pnl <= -FEAR_IDEAL:
            return ("fear_ideal", -FEAR_IDEAL, age)
        if age >= NO_GREEN_SEC and peak_pnl < NO_GREEN_PEAK and pnl < 0:
            return ("no_green", pnl, age)

    # Ran out of ticks
    return ("eod", pnl, age)


def run_day(date_str, fires):
    log_date = date_str.replace("-", "")
    log_path = LOG_DIR / f"{log_date}.log"
    if not log_path.exists():
        return None

    skips = parse_log(log_path)
    # Dedup: collapse skips clustered within DEDUP_WINDOW_SEC into one (same setup repeating per tick)
    DEDUP_WINDOW_SEC = 60
    deduped = []
    last_ts = None
    for s in skips:
        try:
            t = datetime.strptime(s["time_str"], "%H:%M:%S")
        except ValueError:
            continue
        if last_ts is None or (t - last_ts).total_seconds() > DEDUP_WINDOW_SEC:
            deduped.append(s)
            last_ts = t
    skips = deduped
    ticks = load_ticks(date_str)

    if not ticks:
        return {"date": date_str, "skips": len(skips), "no_ticks": True}

    # Anchor date for ticks (assume tick-csv date matches log date)
    tick_date = ticks[0][0].date()

    results = {
        "date": date_str,
        "neutral_skips_total": len(skips),
        "with_known_dir": 0,
        "would_allow_count": 0,
        "would_allow_results": [],
    }

    for s in skips:
        # Build absolute timestamp
        try:
            t_only = datetime.strptime(s["time_str"], "%H:%M:%S").time()
            ts = datetime.combine(tick_date, t_only)
        except ValueError:
            continue

        # Probe direction: prefer ticket-trace from log, fall back to hawk-log timestamp match
        probe_dir = s["probe_dir"]
        if not probe_dir:
            probe_dir = find_probe_dir(ts, fires)
        if not probe_dir:
            continue
        s["probe_dir"] = probe_dir
        results["with_known_dir"] += 1

        # Relaxed rule: allow if probe_dir matches weak EMA bias_dir
        if s["probe_dir"] != s["bias_dir"]:
            continue
        results["would_allow_count"] += 1

        idx, tick = find_tick(ticks, ts)
        if idx is None:
            continue
        # Entry price: BUY at ask, SELL at bid (taker)
        entry = tick[2] if s["probe_dir"] == "buy" else tick[1]

        reason, pnl, age = simulate_main(ticks, idx, s["probe_dir"], entry)
        results["would_allow_results"].append({
            "time": s["time_str"],
            "dir": s["probe_dir"],
            "entry": entry,
            "reason": reason,
            "pnl": round(pnl, 2),
            "age": age,
            "ema_gap": round(s["ema34"] - s["ema89"], 2),
        })

    # Aggregates
    pnls = [r["pnl"] for r in results["would_allow_results"]]
    results["sum_pnl"] = round(sum(pnls), 2) if pnls else 0
    results["wins"] = sum(1 for p in pnls if p > 0)
    results["losses"] = sum(1 for p in pnls if p < 0)
    results["fear_trips"] = sum(1 for r in results["would_allow_results"] if r["reason"] == "fear_ideal")
    results["trail_wins"] = sum(1 for r in results["would_allow_results"] if r["reason"] == "trail")
    return results


def main():
    fires = load_hawk_fires()
    print(f"Loaded {len(fires)} FIRE events from shano_hawk.log")

    dates = ["2026-04-29", "2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05"]
    grand_pnl = 0.0
    grand_skips = 0
    grand_allowed = 0
    grand_fear = 0

    print(f"{'Date':<12} {'Skips':>6} {'KnownDir':>9} {'Allowed':>8} {'Wins':>5} {'Losses':>7} "
          f"{'FearTrips':>10} {'TrailWins':>10} {'Net P&L':>10}")
    print("-" * 90)
    for d in dates:
        r = run_day(d, fires)
        if r is None:
            print(f"{d:<12}  no log")
            continue
        if r.get("no_ticks"):
            print(f"{d:<12}  log={r['skips']} skips, no tick CSV")
            continue
        print(f"{d:<12} {r['neutral_skips_total']:>6} {r['with_known_dir']:>9} "
              f"{r['would_allow_count']:>8} {r['wins']:>5} {r['losses']:>7} "
              f"{r['fear_trips']:>10} {r['trail_wins']:>10} ${r['sum_pnl']:>+9.2f}")
        grand_pnl += r["sum_pnl"]
        grand_skips += r["neutral_skips_total"]
        grand_allowed += r["would_allow_count"]
        grand_fear += r["fear_trips"]

    print("-" * 90)
    print(f"{'TOTAL':<12} {grand_skips:>6} {'':>9} {grand_allowed:>8} {'':>5} {'':>7} "
          f"{grand_fear:>10} {'':>10} ${grand_pnl:>+9.2f}")
    print()
    print("Verdict:")
    if grand_pnl > 50:
        print(f"  Net +${grand_pnl:.2f} over period — relaxation looks PROFITABLE.")
        print(f"  But check fear-trips ({grand_fear}) — even if net positive, drawdown matters.")
    elif grand_pnl > 0:
        print(f"  Net +${grand_pnl:.2f} — marginally profitable. Probably not worth the added risk.")
    else:
        print(f"  Net ${grand_pnl:+.2f} — relaxation HURTS. Keep filter strict.")


if __name__ == "__main__":
    main()
