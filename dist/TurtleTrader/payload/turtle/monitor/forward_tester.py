"""forward_tester.py — Intra-candle real-time diagnostics.

Answers the questions:
  Q1. Per-candle: what's the spread, max-spread, tick density, range, slippage?
  Q2. Probe-every-candle: if we probe at second N in direction of early move,
      what's the confirm rate? fail rate? timeout rate?
  Q3. Burst-probes: if we fire 4 probes within ONE candle (at sec 5/15/25/35),
      how many confirm before bar close vs. waiting 2 candles?
  Q4. Early-direction → close: at second N, does the move so far predict the
      bar's close direction? (How early is the signal?)

Each cycle re-reads ticks, groups by bar-minute, runs intra-bar simulations
on every bar that has a known "next bar" (so we can validate across the
180-sec probe window).

Outputs:
  forward_test_per_bar.jsonl  — append-only per-bar record (diagnostics + simulated probes)
  forward_test_summary.json   — aggregated stats per test/parameter
  forward_tester.log          — human-readable progress

PROBE economics for XAUUSD on 0.01 lots:
  +$0.45 confirm = 4.5 pips ($0.45 price move) favourable
  -$3.00 fail    = 30 pips against
  PnL formula:   (curr - entry) × dir × lots × 100  (USD)
"""
from __future__ import annotations
import csv, json, math, time
from datetime import datetime, timedelta
from pathlib import Path

TICK_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-01.csv")
HERE     = Path(__file__).parent
PER_BAR  = HERE / "forward_test_per_bar.jsonl"
SUMMARY  = HERE / "forward_test_summary.json"
SEEN_F   = HERE / "forward_test_seen_bars.json"
LOG      = HERE / "forward_tester.log"

# ── Probe economics ──
PROBE_LOTS         = 0.01
CONTRACT_SIZE      = 100        # XAUUSD per lot
PROBE_CONFIRM_USD  = 0.45
PROBE_FAIL_USD     = 3.00
PROBE_TIMEOUT_SEC  = 180        # 3 min
LATENCY_MS         = 250        # average broker latency assumption

# ── Main-trade economics (matches LIVE config) ──
MAIN_LOTS          = 0.30
MAIN_TRAIL_TRIG    = 25.0       # peak USD before trail arms
MAIN_TRAIL_DROP    = 8.0        # USD drop from peak triggers exit
MAIN_SL_USD        = 10.0       # hard cut
MAIN_CATASTROPHIC  = 50.0       # outlier safety
MAIN_HORIZON_SEC   = 600        # 10-min horizon

# ── Test parameters ──
EARLY_SECONDS      = [5, 10, 15, 20]    # seconds-into-bar for direction read
BURST_SECONDS      = [5, 15, 25, 35]    # seconds for burst-probe entries
POLL_SEC           = 30                  # cycle pause

# ── Consensus sweep: X probes, Y ms apart ──
CONSENSUS_TESTS    = [
    {"X": 2, "Y_ms": 250},
    {"X": 3, "Y_ms": 250},
    {"X": 3, "Y_ms": 500},
    {"X": 4, "Y_ms": 250},
    {"X": 5, "Y_ms": 100},
    {"X": 5, "Y_ms": 500},
]
CONSENSUS_START_SEC = 5         # first probe time (seconds into bar)


# ────────── data layer ──────────
def parse_ticks(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            try:
                dt = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S").replace(microsecond=int(row[1]) * 1000)
                out.append((dt, float(row[2]), float(row[3])))
            except (ValueError, IndexError):
                continue
    return out


def group_by_bar(ticks):
    """Return dict {bar_start_dt: [(dt, bid, ask), ...]}."""
    by = {}
    for t in ticks:
        bm = t[0].replace(second=0, microsecond=0)
        by.setdefault(bm, []).append(t)
    return by


# ────────── primitives ──────────
def pnl_usd(entry, curr, dir_sign, lots=PROBE_LOTS):
    return (curr - entry) * dir_sign * lots * CONTRACT_SIZE


def tick_at_or_after(bar_ticks, target_dt):
    """Find first tick with dt >= target_dt. Returns tick or None."""
    for t in bar_ticks:
        if t[0] >= target_dt:
            return t
    return None


# ────────── per-bar diagnostics ──────────
def bar_diagnostics(bar_ticks):
    """Return per-bar stats: spread, tick density, range, body, etc."""
    if not bar_ticks:
        return None
    bids = [t[1] for t in bar_ticks]
    asks = [t[2] for t in bar_ticks]
    spreads = [a - b for b, a in zip(bids, asks)]
    mids = [(b + a) / 2 for b, a in zip(bids, asks)]
    o, c = mids[0], mids[-1]
    h, l = max(mids), min(mids)
    rng = h - l
    body = abs(c - o)
    return {
        "n_ticks": len(bar_ticks),
        "spread_avg_pts": round(sum(spreads) / len(spreads), 4),
        "spread_max_pts": round(max(spreads), 4),
        "spread_min_pts": round(min(spreads), 4),
        "range_pts": round(rng, 4),
        "body_pts": round(body, 4),
        "body_pct_of_range": round(body / rng, 3) if rng > 0 else 0,
        "open": round(o, 4), "high": round(h, 4), "low": round(l, 4), "close": round(c, 4),
        "dir": -1 if c < o else 1 if c > o else 0,
    }


# ────────── simulated probe ──────────
def simulate_probe(entry_dt, dir_sign, all_ticks_after_entry):
    """Open a probe at entry_dt with LATENCY_MS slip. Track P&L tick-by-tick.
    Return: outcome dict.
    """
    target = entry_dt + timedelta(milliseconds=LATENCY_MS)
    # find fill tick
    fill = None
    for t in all_ticks_after_entry:
        if t[0] >= target:
            fill = t; break
    if fill is None:
        return {"outcome": "NO_FILL"}
    fill_dt, bid, ask = fill
    entry_price = ask if dir_sign == 1 else bid
    intended_target_tick = tick_at_or_after(all_ticks_after_entry, entry_dt)
    intended_price = (intended_target_tick[2] if dir_sign == 1 else intended_target_tick[1]) if intended_target_tick else entry_price
    slippage_pts = (entry_price - intended_price) * dir_sign  # positive = paid more than intended

    deadline = entry_dt + timedelta(seconds=PROBE_TIMEOUT_SEC)
    for t in all_ticks_after_entry:
        if t[0] < fill_dt:
            continue
        if t[0] > deadline:
            cur = t[1] if dir_sign == 1 else t[2]
            pnl = pnl_usd(entry_price, cur, dir_sign)
            return {"outcome": "TIMEOUT", "fill_price": round(entry_price, 4),
                    "slippage_pts": round(slippage_pts, 4),
                    "elapsed_sec": (t[0] - entry_dt).total_seconds(),
                    "pnl_usd": round(pnl, 4)}
        cur = t[1] if dir_sign == 1 else t[2]   # exit at bid (close long) / ask (close short)
        pnl = pnl_usd(entry_price, cur, dir_sign)
        if pnl >= PROBE_CONFIRM_USD:
            return {"outcome": "CONFIRM", "elapsed_sec": round((t[0] - entry_dt).total_seconds(), 3),
                    "fill_price": round(entry_price, 4), "exit_price": round(cur, 4),
                    "slippage_pts": round(slippage_pts, 4), "pnl_usd": round(pnl, 4)}
        if pnl <= -PROBE_FAIL_USD:
            return {"outcome": "FAIL", "elapsed_sec": round((t[0] - entry_dt).total_seconds(), 3),
                    "fill_price": round(entry_price, 4), "exit_price": round(cur, 4),
                    "slippage_pts": round(slippage_pts, 4), "pnl_usd": round(pnl, 4)}
    return {"outcome": "TRUNCATED", "fill_price": round(entry_price, 4),
            "slippage_pts": round(slippage_pts, 4)}


def simulate_main(entry_dt, dir_sign, ticks_after):
    """Open a 0.30-lot main at entry_dt. Trail (peak >= $25 → exit on $8 drop), SL -$10."""
    target = entry_dt + timedelta(milliseconds=LATENCY_MS)
    fill = next((t for t in ticks_after if t[0] >= target), None)
    if fill is None:
        return {"outcome": "NO_FILL"}
    fill_dt, bid, ask = fill
    entry_price = ask if dir_sign == 1 else bid
    deadline = entry_dt + timedelta(seconds=MAIN_HORIZON_SEC)
    peak = 0.0
    last_pnl = 0.0
    last_dt = fill_dt
    for t in ticks_after:
        if t[0] < fill_dt:
            continue
        if t[0] > deadline:
            cur = t[1] if dir_sign == 1 else t[2]
            pnl = pnl_usd(entry_price, cur, dir_sign, MAIN_LOTS)
            return {"outcome": "TIMEOUT", "pnl_usd": round(pnl, 2),
                    "peak_usd": round(peak, 2), "elapsed_sec": (t[0] - entry_dt).total_seconds()}
        cur = t[1] if dir_sign == 1 else t[2]   # exit at bid (long) / ask (short)
        pnl = pnl_usd(entry_price, cur, dir_sign, MAIN_LOTS)
        if pnl > peak:
            peak = pnl
        if pnl <= -MAIN_CATASTROPHIC:
            return {"outcome": "CATASTROPHIC", "pnl_usd": round(pnl, 2),
                    "peak_usd": round(peak, 2),
                    "elapsed_sec": round((t[0] - entry_dt).total_seconds(), 2)}
        if pnl <= -MAIN_SL_USD:
            return {"outcome": "SL", "pnl_usd": round(pnl, 2),
                    "peak_usd": round(peak, 2),
                    "elapsed_sec": round((t[0] - entry_dt).total_seconds(), 2)}
        if peak >= MAIN_TRAIL_TRIG and (peak - pnl) >= MAIN_TRAIL_DROP:
            return {"outcome": "TRAIL_WIN", "pnl_usd": round(pnl, 2),
                    "peak_usd": round(peak, 2),
                    "elapsed_sec": round((t[0] - entry_dt).total_seconds(), 2)}
        last_pnl = pnl; last_dt = t[0]
    return {"outcome": "TRUNCATED", "pnl_usd": round(last_pnl, 2),
            "peak_usd": round(peak, 2),
            "elapsed_sec": round((last_dt - entry_dt).total_seconds(), 2)}


def simulate_consensus(bar_dt, bar_ticks, future_ticks, X, Y_ms):
    """Fire X simulated probe-direction-reads Y_ms apart starting at bar_start + 5s.
    All must agree on direction. If consensus → fire main at last_probe + LATENCY.
    Returns: {outcome, dir, all_dirs, main: {...}}.
    """
    bar_start = bar_dt
    open_mid = (bar_ticks[0][1] + bar_ticks[0][2]) / 2 if bar_ticks else None
    if open_mid is None:
        return {"outcome": "NO_DATA"}
    probe_times = [bar_start + timedelta(seconds=CONSENSUS_START_SEC, milliseconds=i * Y_ms) for i in range(X)]
    dirs = []
    for pt in probe_times:
        tick = next((t for t in bar_ticks if t[0] >= pt), None)
        if tick is None:
            return {"outcome": "NO_TICK"}
        cur_mid = (tick[1] + tick[2]) / 2
        diff = cur_mid - open_mid
        d = 1 if diff > 0 else -1 if diff < 0 else 0
        if d == 0:
            return {"outcome": "FLAT_AT_PROBE", "all_dirs": dirs + [0]}
        dirs.append(d)
    if len(set(dirs)) != 1:
        return {"outcome": "NO_CONSENSUS", "all_dirs": dirs}
    consensus_dir = dirs[0]
    last_pt = probe_times[-1]
    main = simulate_main(last_pt, consensus_dir, future_ticks)
    return {"outcome": "CONSENSUS_FIRED", "dir": consensus_dir, "all_dirs": dirs,
            "consensus_at": last_pt.isoformat(), "main": main}


# ────────── per-bar tests ──────────
def early_direction(bar_ticks, second):
    """Return -1/0/+1 based on price-vs-open at sec N. Returns None if no tick exists."""
    if not bar_ticks:
        return None
    bar_start = bar_ticks[0][0].replace(second=0, microsecond=0)
    target = bar_start + timedelta(seconds=second)
    early_tick = tick_at_or_after(bar_ticks, target)
    if early_tick is None:
        return None
    open_mid = (bar_ticks[0][1] + bar_ticks[0][2]) / 2
    early_mid = (early_tick[1] + early_tick[2]) / 2
    diff = early_mid - open_mid
    return 1 if diff > 0 else -1 if diff < 0 else 0


def run_bar_tests(bar_dt, bar_ticks, future_ticks):
    """Run all per-bar tests. future_ticks = ticks from this bar's start through following ~3 min.
    Returns dict ready to write as a JSONL row.
    """
    diag = bar_diagnostics(bar_ticks)
    if diag is None:
        return None

    # Q4: Early direction predicts bar close direction?
    early_dir = {}
    for sec in EARLY_SECONDS:
        d = early_direction(bar_ticks, sec)
        if d is not None:
            early_dir[f"sec_{sec}"] = {
                "early_dir": d,
                "close_dir": diag["dir"],
                "predicted_close_correctly": (d == diag["dir"]) if d != 0 else None,
            }

    # Q2: Probe-every-candle at each early second
    bar_start = bar_dt
    probes_per_sec = {}
    for sec in EARLY_SECONDS:
        d = early_direction(bar_ticks, sec)
        if d is None or d == 0:
            probes_per_sec[f"sec_{sec}"] = {"skipped": True}
            continue
        entry_dt = bar_start + timedelta(seconds=sec)
        # Future ticks include same-bar later ticks + next bars up to 3 min
        outcome = simulate_probe(entry_dt, d, future_ticks)
        outcome["dir"] = d
        probes_per_sec[f"sec_{sec}"] = outcome

    # Q3: Burst-probes within one candle
    burst = []
    for sec in BURST_SECONDS:
        d = early_direction(bar_ticks, sec)
        if d is None or d == 0:
            burst.append({"sec": sec, "skipped": True}); continue
        entry_dt = bar_start + timedelta(seconds=sec)
        outcome = simulate_probe(entry_dt, d, future_ticks)
        outcome["sec"] = sec
        outcome["dir"] = d
        burst.append(outcome)

    # Q5: Probe-confirms-then-main — for the sec_5 probe, if it confirmed, fire main at confirm time
    main_after_confirm = {}
    for sec_key, p in probes_per_sec.items():
        if p.get("outcome") != "CONFIRM":
            continue
        confirm_dt = bar_start + timedelta(seconds=int(sec_key.split("_")[1])) + timedelta(seconds=p["elapsed_sec"])
        d = p.get("dir")
        if d is None:
            continue
        main = simulate_main(confirm_dt, d, future_ticks)
        main_after_confirm[sec_key] = {"dir": d, "confirm_dt": confirm_dt.isoformat(), "main": main}

    # Q6: X-probes Y-ms-apart consensus → main
    consensus = {}
    for cfg in CONSENSUS_TESTS:
        key = f"X{cfg['X']}_Y{cfg['Y_ms']}ms"
        consensus[key] = simulate_consensus(bar_dt, bar_ticks, future_ticks, cfg["X"], cfg["Y_ms"])

    return {
        "bar_time": bar_dt.isoformat(),
        "diagnostics": diag,
        "early_direction": early_dir,
        "probe_at_second": probes_per_sec,
        "burst_probes": burst,
        "main_after_confirm": main_after_confirm,
        "consensus": consensus,
    }


# ────────── aggregation ──────────
def aggregate(rows):
    """Build per-test summary across all bars."""
    summary = {
        "total_bars": len(rows),
        "diagnostics": {},
        "early_direction_vs_close": {},
        "probe_at_second": {},
        "burst_probes": {},
    }
    if not rows:
        return summary

    # Diagnostics — averages
    diag_keys = ["n_ticks", "spread_avg_pts", "spread_max_pts", "range_pts", "body_pts"]
    for k in diag_keys:
        vals = [r["diagnostics"][k] for r in rows if r.get("diagnostics")]
        if vals:
            summary["diagnostics"][k] = {
                "avg": round(sum(vals) / len(vals), 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
            }

    # Early-dir → close-dir correlation
    for sec_key in [f"sec_{s}" for s in EARLY_SECONDS]:
        items = [r["early_direction"][sec_key] for r in rows if sec_key in r.get("early_direction", {})]
        items = [it for it in items if it.get("predicted_close_correctly") is not None]
        if items:
            n = len(items)
            correct = sum(1 for it in items if it["predicted_close_correctly"])
            summary["early_direction_vs_close"][sec_key] = {
                "n": n, "correct": correct, "accuracy_pct": round(correct/n*100, 1),
                "ci95_pct": wilson_ci(correct, n),
            }

    # Probe-at-second outcomes
    for sec_key in [f"sec_{s}" for s in EARLY_SECONDS]:
        items = [r["probe_at_second"][sec_key] for r in rows if sec_key in r.get("probe_at_second", {})]
        items = [it for it in items if not it.get("skipped")]
        if items:
            n = len(items)
            confirm = sum(1 for it in items if it.get("outcome") == "CONFIRM")
            fail    = sum(1 for it in items if it.get("outcome") == "FAIL")
            timeout = sum(1 for it in items if it.get("outcome") == "TIMEOUT")
            slips   = [it.get("slippage_pts", 0) for it in items if "slippage_pts" in it]
            confirm_times = [it["elapsed_sec"] for it in items if it.get("outcome") == "CONFIRM"]
            summary["probe_at_second"][sec_key] = {
                "n": n,
                "confirm_pct": round(confirm/n*100, 1),
                "fail_pct": round(fail/n*100, 1),
                "timeout_pct": round(timeout/n*100, 1),
                "ci95_confirm_pct": wilson_ci(confirm, n),
                "avg_slippage_pts": round(sum(slips)/len(slips), 4) if slips else None,
                "max_slippage_pts": round(max(slips), 4) if slips else None,
                "avg_confirm_sec": round(sum(confirm_times)/len(confirm_times), 2) if confirm_times else None,
            }

    # Burst-probes — what fraction of bars had ≥N probes confirm?
    burst_per_bar = []
    for r in rows:
        outcomes = r.get("burst_probes", [])
        confirms = sum(1 for o in outcomes if o.get("outcome") == "CONFIRM")
        not_skipped = sum(1 for o in outcomes if not o.get("skipped"))
        if not_skipped > 0:
            burst_per_bar.append({"confirms": confirms, "tried": not_skipped})
    if burst_per_bar:
        n = len(burst_per_bar)
        all_confirmed = sum(1 for b in burst_per_bar if b["confirms"] == b["tried"])
        any_confirmed = sum(1 for b in burst_per_bar if b["confirms"] > 0)
        avg_confirms  = sum(b["confirms"] for b in burst_per_bar) / n
        summary["burst_probes"] = {
            "bars_with_burst": n,
            "any_confirmed_pct": round(any_confirmed/n*100, 1),
            "all_confirmed_pct": round(all_confirmed/n*100, 1),
            "avg_confirms_per_bar": round(avg_confirms, 2),
            "ci95_any_confirmed_pct": wilson_ci(any_confirmed, n),
        }

    # Q5: Main-after-confirm — for each sec entry, what's the main WR conditional on probe confirming?
    summary["main_after_confirm"] = {}
    for sec_key in [f"sec_{s}" for s in EARLY_SECONDS]:
        items = [r["main_after_confirm"].get(sec_key) for r in rows if sec_key in r.get("main_after_confirm", {})]
        items = [it for it in items if it]
        if not items: continue
        n = len(items)
        wins   = sum(1 for it in items if it["main"].get("outcome") == "TRAIL_WIN")
        sl     = sum(1 for it in items if it["main"].get("outcome") == "SL")
        cat    = sum(1 for it in items if it["main"].get("outcome") == "CATASTROPHIC")
        timeo  = sum(1 for it in items if it["main"].get("outcome") == "TIMEOUT")
        pnls   = [it["main"].get("pnl_usd", 0) for it in items if "pnl_usd" in it["main"]]
        peaks  = [it["main"].get("peak_usd", 0) for it in items if "peak_usd" in it["main"]]
        summary["main_after_confirm"][sec_key] = {
            "n": n,
            "win_pct":  round(wins/n*100, 1), "ci95_win_pct": wilson_ci(wins, n),
            "sl_pct":   round(sl/n*100, 1),
            "cat_pct":  round(cat/n*100, 1),
            "timeout_pct": round(timeo/n*100, 1),
            "avg_pnl_usd": round(sum(pnls)/len(pnls), 2) if pnls else None,
            "total_pnl_usd": round(sum(pnls), 2) if pnls else None,
            "avg_peak_usd": round(sum(peaks)/len(peaks), 2) if peaks else None,
        }

    # Q6: Consensus → main results
    summary["consensus"] = {}
    for cfg in CONSENSUS_TESTS:
        key = f"X{cfg['X']}_Y{cfg['Y_ms']}ms"
        items = [r["consensus"].get(key) for r in rows if key in r.get("consensus", {})]
        items = [it for it in items if it]
        if not items: continue
        n_total = len(items)
        n_consensus = sum(1 for it in items if it.get("outcome") == "CONSENSUS_FIRED")
        if n_consensus == 0:
            summary["consensus"][key] = {"n_bars": n_total, "consensus_rate_pct": 0, "n_mains": 0}
            continue
        mains = [it["main"] for it in items if it.get("outcome") == "CONSENSUS_FIRED"]
        wins  = sum(1 for m in mains if m.get("outcome") == "TRAIL_WIN")
        sl    = sum(1 for m in mains if m.get("outcome") == "SL")
        cat   = sum(1 for m in mains if m.get("outcome") == "CATASTROPHIC")
        timeo = sum(1 for m in mains if m.get("outcome") == "TIMEOUT")
        pnls  = [m.get("pnl_usd", 0) for m in mains if "pnl_usd" in m]
        summary["consensus"][key] = {
            "n_bars": n_total,
            "consensus_rate_pct": round(n_consensus / n_total * 100, 1),
            "n_mains": n_consensus,
            "main_win_pct": round(wins / n_consensus * 100, 1),
            "ci95_win_pct": wilson_ci(wins, n_consensus),
            "sl_pct": round(sl / n_consensus * 100, 1),
            "cat_pct": round(cat / n_consensus * 100, 1),
            "timeout_pct": round(timeo / n_consensus * 100, 1),
            "avg_pnl_usd": round(sum(pnls) / len(pnls), 2) if pnls else None,
            "total_pnl_usd": round(sum(pnls), 2) if pnls else None,
        }

    return summary


def wilson_ci(wins, n, z=1.96):
    if n == 0: return [0.0, 0.0]
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return [round(max(0, (centre - half)) * 100, 1), round(min(1, (centre + half)) * 100, 1)]


# ────────── persistence ──────────
def load_seen():
    if not SEEN_F.exists(): return set()
    try: return set(json.loads(SEEN_F.read_text(encoding="utf-8")))
    except Exception: return set()

def save_seen(s):
    SEEN_F.write_text(json.dumps(sorted(s), indent=2), encoding="utf-8")

def append_per_bar(rows):
    with open(PER_BAR, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

def load_all_per_bar():
    if not PER_BAR.exists(): return []
    out = []
    with open(PER_BAR, "r", encoding="utf-8") as f:
        for line in f:
            try: out.append(json.loads(line))
            except Exception: continue
    return out

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ────────── main loop ──────────
def main():
    log(f"forward_tester (intra-candle) starting — {TICK_CSV.name}")
    log(f"PROBE: confirm=${PROBE_CONFIRM_USD} fail=-${PROBE_FAIL_USD} timeout={PROBE_TIMEOUT_SEC}s lat={LATENCY_MS}ms")
    log(f"early_seconds={EARLY_SECONDS}  burst_seconds={BURST_SECONDS}")
    cycle = 0
    while True:
        cycle += 1
        try:
            ticks = parse_ticks(TICK_CSV)
            bar_groups = group_by_bar(ticks)
            sorted_bars = sorted(bar_groups.keys())
            seen = load_seen()

            # A bar is "completable" if there are ticks in the bar AT LEAST 3 min after its start
            # (so we can resolve probe TIMEOUT via subsequent ticks).
            new_records = []
            for bar_dt in sorted_bars:
                key = bar_dt.isoformat()
                if key in seen: continue
                bar_ticks = bar_groups[bar_dt]
                # Future ticks: ticks from this bar's start through bar_start + 3 min
                cutoff = bar_dt + timedelta(seconds=PROBE_TIMEOUT_SEC + 30)
                future_ticks = [t for t in ticks if bar_dt <= t[0] <= cutoff]
                # Only complete if cutoff is in the past (we have data past it)
                if not ticks or ticks[-1][0] < cutoff:
                    continue
                rec = run_bar_tests(bar_dt, bar_ticks, future_ticks)
                if rec is None: continue
                new_records.append(rec)
                seen.add(key)

            if new_records:
                append_per_bar(new_records)
                save_seen(seen)

            all_rows = load_all_per_bar()
            summary = aggregate(all_rows)
            SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

            # Log progress
            log(f"cycle={cycle}  ticks={len(ticks)}  bars={len(sorted_bars)}  new_completed={len(new_records)}  total_rows={len(all_rows)}")
            if summary["diagnostics"]:
                d = summary["diagnostics"]
                log(f"  per-bar avgs: spread={d.get('spread_avg_pts',{}).get('avg')} (max {d.get('spread_max_pts',{}).get('max')})  range={d.get('range_pts',{}).get('avg')}  ticks={d.get('n_ticks',{}).get('avg')}")
            for sec_key, s in summary.get("early_direction_vs_close", {}).items():
                log(f"  early-dir@{sec_key:7s} predicts close: n={s['n']:>4d}  acc={s['accuracy_pct']:>5.1f}%  CI={s['ci95_pct']}")
            for sec_key, s in summary.get("probe_at_second", {}).items():
                log(f"  probe@{sec_key:7s}: n={s['n']:>4d}  confirm={s['confirm_pct']:>5.1f}% (CI {s['ci95_confirm_pct']})  fail={s['fail_pct']:>5.1f}%  timeout={s['timeout_pct']:>5.1f}%  slip(avg/max)={s.get('avg_slippage_pts')}/{s.get('max_slippage_pts')}  avg-confirm={s.get('avg_confirm_sec')}s")
            b = summary.get("burst_probes", {})
            if b:
                log(f"  burst-probes/bar: n={b['bars_with_burst']}  any-confirm={b['any_confirmed_pct']}% (CI {b['ci95_any_confirmed_pct']})  all-confirm={b['all_confirmed_pct']}%  avg-confirms/bar={b['avg_confirms_per_bar']}")
            log(f"  -- MAIN-AFTER-CONFIRM (0.30 lots, trail 25/8, SL -$10) --")
            for sec_key, s in summary.get("main_after_confirm", {}).items():
                log(f"  main@{sec_key:7s}: n={s['n']:>4d}  WIN={s['win_pct']:>5.1f}% (CI {s['ci95_win_pct']})  SL={s['sl_pct']:>5.1f}%  cat={s['cat_pct']:>4.1f}%  TO={s['timeout_pct']:>5.1f}%  avg-PnL=${s.get('avg_pnl_usd')}  total=${s.get('total_pnl_usd')}")
            log(f"  -- CONSENSUS (X probes Y ms apart -> main) --")
            for key, s in summary.get("consensus", {}).items():
                if s.get("n_mains", 0) == 0:
                    log(f"  {key:14s}: bars={s.get('n_bars',0)}  consensus_rate={s.get('consensus_rate_pct',0)}%  (no mains)")
                else:
                    log(f"  {key:14s}: bars={s['n_bars']}  consensus={s['consensus_rate_pct']}%  mains={s['n_mains']}  WIN={s['main_win_pct']}% (CI {s['ci95_win_pct']})  SL={s['sl_pct']}%  cat={s['cat_pct']}%  avg-PnL=${s['avg_pnl_usd']}  total=${s['total_pnl_usd']}")

            time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            log("stopped by user"); break
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}"); time.sleep(15)


if __name__ == "__main__":
    main()
