"""
probe_shadow.py — live experiment: watch every probe tick-by-tick and answer
"would a lower probeConfirm threshold have caught the move?"

Loop (every 1s):
  1. Read shano_live.json — find probes (lots <= 0.02) in positions.
  2. New probe → record entry_time (now), entry_price (from latest tick).
  3. Closed probe (disappeared from positions) →
     - Look up actual close P&L from EA history (matched by ticket).
     - Replay ticks from entry to close → compute MFE (max favorable points).
     - Replay 120s of ticks AFTER close → compute "missed continuation".
     - Did MFE ever cross +$0.45 / $0.30 / $0.20? Mark as would-have-confirmed.
     - For each "would-confirm" threshold: simulate main 0.40 from that tick
       through subsequent ticks with trail (trigger $8 / drop $2) and
       fearIdeal -$70 over a 600s horizon.
  4. Append row to probe_shadow_results.csv.
  5. Update probe_shadow_summary.md with rolling stats.

The tick CSV must be share-readable (FILE_SHARE_READ in EA) — we re-tail on
each cycle. Probes opened before the logger started can't be analyzed.

Run:
  python probe_shadow.py            # daemon
  python probe_shadow.py --once     # single pass over closed probes
  python probe_shadow.py --report   # just regenerate the markdown summary
"""

from __future__ import annotations
import json
import os
import sys
import time
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta

LIVE_JSON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
LAB_DIR = Path(__file__).parent
RESULTS_CSV = LAB_DIR / "probe_shadow_results.csv"
SUMMARY_MD = LAB_DIR / "probe_shadow_summary.md"
LOG_FILE = LAB_DIR / "probe_shadow.log"
STATE_FILE = LAB_DIR / ".probe_shadow_state.json"

# Backtest assumptions for "what would the main trade have done"
MAIN_LOTS = 0.40
CONTRACT_SIZE = 100
TRAIL_TRIGGER = 8.0
TRAIL_DROP = 2.0
FEAR_IDEAL = 70.0
MAIN_HORIZON_SEC = 600  # 10 min max main hold

# Thresholds to test (dollars on 0.01 lot = points of price movement)
THRESHOLDS = [0.20, 0.30, 0.45, 0.58]  # 0.58 = current

POLL_SEC = 1.0


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [SHADOW] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_live():
    try:
        return json.loads(LIVE_JSON.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def broker_now(live: dict) -> datetime:
    """Return the EA's reported broker timestamp as datetime, falling back
    to local now() if unavailable. Broker time is what the tick CSV uses,
    so all range queries against the tick file MUST be in broker time.
    """
    ts = (live or {}).get("ts") if live else None
    if ts:
        try:
            return datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now()


def daily_tick_path(date: datetime):
    return COMMON_DIR / f"shano_ticks_{date.strftime('%Y-%m-%d')}.csv"


def parse_tick_ts(s: str):
    return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")


def read_ticks_in_range(t_start: datetime, t_end: datetime):
    """Read all tick rows where t_start <= ts <= t_end. Spans daily files."""
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        p = daily_tick_path(cur)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    next(f, None)  # header
                    for line in f:
                        parts = line.strip().split(",")
                        if len(parts) < 4:
                            continue
                        try:
                            dt = parse_tick_ts(parts[0])
                        except ValueError:
                            continue
                        if dt < t_start:
                            continue
                        if dt > t_end:
                            break
                        try:
                            bid = float(parts[2])
                            ask = float(parts[3])
                        except ValueError:
                            continue
                        out.append((dt, bid, ask))
            except OSError:
                pass
        cur += timedelta(days=1)
    return out


def find_actual_entry_tick(entry_price: float, dir_sign: int, detect_time: datetime,
                           tolerance: float = 0.10, lookback_sec: int = 8):
    """When a new probe appears in shano_live.json, our detection lags the
    actual fill by 0–2s (poll interval + EA flush latency). Find the actual
    fill tick by back-searching the tick CSV for the most recent tick whose
    fill-side price matches entry_price within tolerance.
      BUY  → entry at ASK; SELL → entry at BID.
    Returns (actual_entry_dt, bid, ask) or None if no match.
    """
    t_start = detect_time - timedelta(seconds=lookback_sec)
    ticks = read_ticks_in_range(t_start, detect_time)
    if not ticks:
        return None
    # Search newest first; most recent matching tick is the most likely fill
    for dt, bid, ask in reversed(ticks):
        target = ask if dir_sign == 1 else bid
        if abs(target - entry_price) <= tolerance:
            return (dt, bid, ask)
    return None


def load_state():
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:
        return {"tracked": {}, "analyzed_tickets": []}


def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def history_lookup(history: list, ticket: int):
    for h in history:
        if h.get("ticket") == ticket:
            return h
    return None


def simulate_main_outcome(entry_price: float, dir_sign: int, ticks: list):
    """Given an entry point (price) and direction (+1 buy, -1 sell), simulate
    a 0.40-lot main trade with trail (trigger $8, drop $2) and fearIdeal -$70
    over the supplied tick stream. Return realized P&L when an exit fires,
    or open P&L at end of stream.
    """
    if not ticks:
        return 0.0, "no_data"

    peak = 0.0
    for dt, bid, ask in ticks:
        # For BUY: profit = (bid - entry) * lots * contract
        # For SELL: profit = (entry - ask) * lots * contract
        if dir_sign == 1:
            profit = (bid - entry_price) * MAIN_LOTS * CONTRACT_SIZE
        else:
            profit = (entry_price - ask) * MAIN_LOTS * CONTRACT_SIZE

        if profit > peak:
            peak = profit

        # fearIdeal — hard stop
        if profit <= -FEAR_IDEAL:
            return round(profit, 2), "fearIdeal"

        # trail
        if peak >= TRAIL_TRIGGER:
            drop = peak - profit
            if drop >= TRAIL_DROP:
                return round(profit, 2), f"trail (peak ${peak:.2f})"

    # End of stream — return last profit as open
    return round(profit, 2), "horizon_end"


def analyze_probe(probe: dict, history: list, all_positions_now: list):
    """Run the shadow analysis on a now-closed probe. Returns a result dict
    or None if data unavailable.
    """
    ticket = probe["ticket"]
    entry_time = datetime.fromisoformat(probe["entry_time"]) if isinstance(probe["entry_time"], str) else probe["entry_time"]
    entry_price = probe["entry_price"]
    dir_sign = probe["dir_sign"]
    actual_close_time = datetime.fromisoformat(probe.get("close_time")) if isinstance(probe.get("close_time"), str) else probe.get("close_time", datetime.now())

    h = history_lookup(history, ticket)
    actual_pnl = h.get("pnl") if h else None

    # Probe lifetime ticks
    probe_ticks = read_ticks_in_range(entry_time, actual_close_time)
    if not probe_ticks:
        return None  # logger may not have data for this probe

    # Compute MFE during probe (in DOLLARS on 0.01 lot)
    mfe = 0.0
    mae = 0.0
    confirm_ticks = {}  # threshold -> first tick where it crossed
    for dt, bid, ask in probe_ticks:
        if dir_sign == 1:
            fav_dollars = (bid - entry_price) * 0.01 * CONTRACT_SIZE
        else:
            fav_dollars = (entry_price - ask) * 0.01 * CONTRACT_SIZE
        if fav_dollars > mfe:
            mfe = fav_dollars
        if fav_dollars < -mae:
            mae = -fav_dollars
        for thr in THRESHOLDS:
            if thr not in confirm_ticks and fav_dollars >= thr:
                confirm_ticks[thr] = (dt, bid, ask)

    # 120s after close — missed continuation
    after_ticks = read_ticks_in_range(actual_close_time, actual_close_time + timedelta(seconds=120))
    after_max_fav = 0.0
    for dt, bid, ask in after_ticks:
        if dir_sign == 1:
            fav = (bid - entry_price) * 0.01 * CONTRACT_SIZE
        else:
            fav = (entry_price - ask) * 0.01 * CONTRACT_SIZE
        if fav > after_max_fav:
            after_max_fav = fav

    # Simulate main outcome at each "would-have-confirmed" threshold
    main_horizon_end = actual_close_time + timedelta(seconds=MAIN_HORIZON_SEC)
    main_ticks = read_ticks_in_range(actual_close_time, main_horizon_end)

    sim_outcomes = {}
    for thr in THRESHOLDS:
        if thr not in confirm_ticks:
            sim_outcomes[thr] = (None, "didnt_cross")
            continue
        confirm_dt, confirm_bid, confirm_ask = confirm_ticks[thr]
        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        # ticks from confirm_dt forward
        forward = [t for t in probe_ticks + main_ticks if t[0] >= confirm_dt]
        sim_pnl, sim_reason = simulate_main_outcome(main_entry, dir_sign, forward)
        sim_outcomes[thr] = (sim_pnl, sim_reason)

    return {
        "ticket": ticket,
        "entry_time": entry_time.isoformat(timespec="seconds"),
        "close_time": actual_close_time.isoformat(timespec="seconds"),
        "dir": "buy" if dir_sign == 1 else "sell",
        "entry_price": round(entry_price, 3),
        "actual_pnl": actual_pnl,
        "mfe_dollars": round(mfe, 2),
        "mae_dollars": round(mae, 2),
        "after_max_fav_120s": round(after_max_fav, 2),
        "confirm_at_058": 1 if 0.58 in confirm_ticks else 0,
        "confirm_at_045": 1 if 0.45 in confirm_ticks else 0,
        "confirm_at_030": 1 if 0.30 in confirm_ticks else 0,
        "confirm_at_020": 1 if 0.20 in confirm_ticks else 0,
        "sim_main_pnl_058": sim_outcomes.get(0.58, (None,))[0],
        "sim_main_pnl_045": sim_outcomes.get(0.45, (None,))[0],
        "sim_main_pnl_030": sim_outcomes.get(0.30, (None,))[0],
        "sim_main_pnl_020": sim_outcomes.get(0.20, (None,))[0],
        "sim_reason_045": sim_outcomes.get(0.45, (None, ""))[1],
        "tick_count": len(probe_ticks),
    }


def append_result(row: dict):
    new_file = not RESULTS_CSV.exists()
    fieldnames = list(row.keys())
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        w.writerow(row)


def regenerate_summary():
    if not RESULTS_CSV.exists():
        return
    rows = []
    try:
        with open(RESULTS_CSV, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    except OSError:
        return
    if not rows:
        return

    n = len(rows)

    def safe_int(v):
        try: return int(v)
        except: return 0

    def safe_float(v):
        try: return float(v) if v not in ("", None, "None") else None
        except: return None

    actual_pnls = [safe_float(r["actual_pnl"]) for r in rows]
    actual_pnls = [x for x in actual_pnls if x is not None]
    actual_total = sum(actual_pnls)

    confirm_counts = {thr: sum(safe_int(r[f"confirm_at_{round(thr*100):03d}"]) for r in rows) for thr in THRESHOLDS}

    sim_totals = {}
    for thr in THRESHOLDS:
        col = f"sim_main_pnl_{round(thr*100):03d}"
        vals = [safe_float(r[col]) for r in rows]
        vals = [v for v in vals if v is not None]
        sim_totals[thr] = sum(vals)

    # Probes that DIDN'T confirm at $0.58 but would at $0.45 — the "missed wins"
    missed_at_045 = [r for r in rows if safe_int(r["confirm_at_058"]) == 0 and safe_int(r["confirm_at_045"]) == 1]
    missed_total_045 = sum(safe_float(r["sim_main_pnl_045"]) or 0 for r in missed_at_045)

    after_continuations = [safe_float(r["after_max_fav_120s"]) or 0 for r in rows]
    avg_after = sum(after_continuations) / len(after_continuations) if after_continuations else 0

    lines = [
        "# Probe Shadow Analysis — Live Experiment",
        f"",
        f"_Updated: {datetime.now().isoformat(timespec='seconds')}_",
        f"_Probes analyzed: **{n}**_",
        f"",
        f"## What this tests",
        f"For each probe that fired today, did its peak favorable price ever cross",
        f"a lower confirm threshold ($0.45, $0.30, $0.20)? If yes, would the",
        f"resulting main trade have made or lost money over the next 10 minutes?",
        f"",
        f"## Headline numbers",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Probes analyzed | {n} |",
        f"| Confirmed at current $0.58 threshold | {confirm_counts.get(0.58, 0)} ({confirm_counts.get(0.58, 0)*100//max(n,1)}%) |",
        f"| Would have confirmed at $0.45 | {confirm_counts.get(0.45, 0)} ({confirm_counts.get(0.45, 0)*100//max(n,1)}%) |",
        f"| Would have confirmed at $0.30 | {confirm_counts.get(0.30, 0)} ({confirm_counts.get(0.30, 0)*100//max(n,1)}%) |",
        f"| Would have confirmed at $0.20 | {confirm_counts.get(0.20, 0)} ({confirm_counts.get(0.20, 0)*100//max(n,1)}%) |",
        f"| Actual probe-only P&L | ${actual_total:+.2f} |",
        f"| Avg post-close 120s favorable continuation | ${avg_after:+.2f} |",
        f"",
        f"## Simulated main-trade P&L by threshold",
        f"",
        f"_(if we lowered probeConfirm to that value and let mains run with current trail/fearIdeal)_",
        f"",
        f"| Threshold | Sim main total P&L |",
        f"|-----------|-------------------|",
    ]
    for thr in THRESHOLDS:
        lines.append(f"| ${thr:.2f} | ${sim_totals[thr]:+.2f} |")

    lines += [
        f"",
        f"## Probes that current $0.58 missed but $0.45 would have caught",
        f"",
        f"| Count | Sim main total | Avg per missed |",
        f"|-------|----------------|---------------|",
        f"| {len(missed_at_045)} | ${missed_total_045:+.2f} | ${(missed_total_045/max(len(missed_at_045),1)):+.2f} |",
        f"",
        f"## Last 8 probes (newest first)",
        f"",
        f"| time | dir | actual P&L | MFE | conf 0.58 | conf 0.45 | sim main 0.45 | after 120s |",
        f"|------|-----|-----------|-----|-----------|-----------|---------------|-----------|",
    ]
    for r in reversed(rows[-8:]):
        lines.append(
            f"| {r['entry_time'][-8:]} | {r['dir']:<4} | "
            f"${safe_float(r['actual_pnl']) or 0:+.2f} | "
            f"${safe_float(r['mfe_dollars']) or 0:+.2f} | "
            f"{'✓' if safe_int(r['confirm_at_058']) else '·'} | "
            f"{'✓' if safe_int(r['confirm_at_045']) else '·'} | "
            f"{'$'+format(safe_float(r['sim_main_pnl_045']) or 0, '+.2f') if r['sim_main_pnl_045'] not in ('', 'None', None) else '—'} | "
            f"${safe_float(r['after_max_fav_120s']) or 0:+.2f} |"
        )

    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if args.report:
        regenerate_summary()
        log(f"summary regenerated → {SUMMARY_MD}")
        return 0

    state = load_state()
    log(f"shadow analyzer starting; tracked={len(state['tracked'])} analyzed={len(state['analyzed_tickets'])}")

    while True:
        try:
            live = load_live()
            if not live:
                time.sleep(POLL_SEC)
                continue

            history = live.get("history", [])
            now = broker_now(live)  # broker time, matches tick CSV
            current_positions = {}
            for p in live.get("positions", []):
                if p.get("lots", 1) <= 0.02:
                    current_positions[p.get("ticket")] = p

            # Detect newly-opened probes
            for ticket, p in current_positions.items():
                key = str(ticket)
                if key not in state["tracked"]:
                    # EA writes per-position: ticket, dir, lots, entry, current
                    dir_str = str(p.get("dir", "")).lower()
                    entry_price = float(p.get("entry") or p.get("open_price") or 0.0)
                    dir_sign = 1 if dir_str.startswith("b") else -1

                    # Back-search the tick stream for the actual fill tick.
                    # Without this, "now" is ~0.5–2s after the real fill, so
                    # the MFE calculation misses the early favorable move.
                    actual = find_actual_entry_tick(entry_price, dir_sign, now)
                    if actual:
                        entry_time = actual[0]
                        latency_ms = int((now - entry_time).total_seconds() * 1000)
                        log(f"tracking new probe ticket={ticket} dir={dir_str} entry={entry_price} (precise fill found, detection lag {latency_ms}ms)")
                    else:
                        entry_time = now
                        log(f"tracking new probe ticket={ticket} dir={dir_str} entry={entry_price} (no matching tick found — using detect_time)")

                    state["tracked"][key] = {
                        "ticket": ticket,
                        "entry_time": entry_time.isoformat(timespec="seconds"),
                        "entry_price": entry_price,
                        "dir_sign": dir_sign,
                    }

            # Detect closed probes
            still_tracking = {}
            for key, probe in state["tracked"].items():
                if probe["ticket"] in current_positions:
                    still_tracking[key] = probe
                else:
                    # closed
                    if probe["ticket"] in state["analyzed_tickets"]:
                        continue
                    log(f"probe closed ticket={probe['ticket']} — analyzing")
                    if not args.once:  # give EA a moment to update history
                        time.sleep(2)
                        live = load_live() or live
                        history = live.get("history", [])

                    # Find actual close time from EA history (broker time string)
                    h = history_lookup(history, probe["ticket"])
                    if h and h.get("time"):
                        try:
                            ct = datetime.strptime(h["time"], "%Y.%m.%d %H:%M:%S")
                            probe["close_time"] = ct.isoformat(timespec="seconds")
                        except ValueError:
                            probe["close_time"] = now.isoformat(timespec="seconds")
                    else:
                        probe["close_time"] = now.isoformat(timespec="seconds")

                    result = analyze_probe(probe, history, list(current_positions.values()))
                    if result:
                        append_result(result)
                        state["analyzed_tickets"].append(probe["ticket"])
                        log(f"  → MFE=${result['mfe_dollars']:+.2f} actual=${result['actual_pnl']} "
                            f"would_058={result['confirm_at_058']} 045={result['confirm_at_045']} "
                            f"sim_main_045=${result['sim_main_pnl_045']}")
                    else:
                        log(f"  → no tick data for ticket {probe['ticket']} (logger started after probe?)")

            state["tracked"] = still_tracking
            save_state(state)
            regenerate_summary()

            if args.once:
                return 0

            time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(POLL_SEC)


if __name__ == "__main__":
    sys.exit(main() or 0)
