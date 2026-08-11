"""find_optimal_ea.py — the FINAL EA configurator.

Goal: take the 201 historical entries the EA has fired across 5 days, replay
each one against M1 bars + ticks reconstructed from the broker tick CSVs, apply
the v2.93 label-derived gates one by one, then compute forward P&L for the
survivors. The combination with the best total $ + win rate becomes the FINAL
config to lock in as v2.94.

This is NOT a parameter sweep across exits (auto-close-ms already proven dead).
This is a sweep across ENTRY GATES to find the strictest set that keeps real
positive trades and rejects the rest.
"""
from pathlib import Path
import re, sys, bisect, itertools
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
COMMON   = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOG_DIR  = TERMINAL / "MQL5/Logs"
LOTS     = 0.30
DOLLARS_PER_POINT = 100.0 * LOTS
BROKER_OFFSET_HOURS = 2

# ─────────────────────────────────────────────────────────────────────────
# Tick loading + M1 bar reconstruction
# ─────────────────────────────────────────────────────────────────────────
def load_ticks(csv_path: Path) -> list:
    """Return [(epoch_ms, bid, ask), ...]."""
    ticks = []
    with open(csv_path, "r", encoding="utf-8") as f:
        f.readline()
        for line in f:
            try:
                t, bid, ask = line.strip().split(",")
                dt = datetime.strptime(t, "%Y.%m.%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                ticks.append((int(dt.timestamp() * 1000), float(bid), float(ask)))
            except Exception:
                continue
    return ticks


def build_m1_bars(ticks: list) -> dict:
    """Group ticks into M1 bars indexed by minute_epoch_ms. Each bar:
       {open, high, low, close, volume (tick count), open_t, close_t}."""
    bars = {}
    for ep, bid, ask in ticks:
        mid = (bid + ask) / 2.0
        minute_ep = (ep // 60000) * 60000
        if minute_ep not in bars:
            bars[minute_ep] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                               "o_t": ep, "c_t": ep}
        else:
            b = bars[minute_ep]
            b["h"] = max(b["h"], mid)
            b["l"] = min(b["l"], mid)
            b["c"] = mid
            b["v"] += 1
            b["c_t"] = ep
    return bars


def ea_time_to_utc_ep(date_str: str, time_str: str, ms: int) -> int:
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dt = dt - timedelta(hours=BROKER_OFFSET_HOURS)
    return int(dt.timestamp() * 1000) + ms


# ─────────────────────────────────────────────────────────────────────────
# Entry log parsing
# ─────────────────────────────────────────────────────────────────────────
def parse_entries():
    """Return ACTUAL FILLED entries — pair triggers with [FILLED] lines.
    Each FILLED line represents one real broker fill."""
    entries = []
    trigger_re = re.compile(
        r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*S1 (BUY|SELL) LIVE TRIGGER[^\n]*"
        r"entry=([\d.]+)\s+sl=([\d.]+)\s+tp=([\d.]+).*?uhv_shift=(\d+)\s+\(vol=(\d+)\)"
    )
    fill_re = re.compile(
        r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*\[FILLED\] ticket=(\d+)"
    )
    for log_path in sorted(LOG_DIR.glob("20260*.log")):
        if log_path.stat().st_size < 1000: continue
        yyyymmdd = log_path.stem
        if len(yyyymmdd) != 8: continue
        date_str = f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
        with open(log_path, "rb") as f:
            content = f.read().decode("utf-16le", errors="ignore")
        triggers = list(trigger_re.finditer(content))
        fills    = list(fill_re.finditer(content))

        # For each fill, find the IMMEDIATELY-preceding trigger (closest before)
        for fm in fills:
            f_pos = fm.start()
            best_t = None
            for tm in triggers:
                if tm.start() < f_pos:
                    best_t = tm
                else:
                    break
            if best_t is None: continue
            entries.append({
                "date": date_str,
                "trigger_t": best_t.group(1),
                "trigger_ms": int(best_t.group(2)),
                "fill_t": fm.group(1),
                "fill_ms": int(fm.group(2)),
                "side": best_t.group(3),
                "entry": float(best_t.group(4)),
                "sl": float(best_t.group(5)),
                "tp": float(best_t.group(6)),
                "uhv_shift": int(best_t.group(7)),
                "uhv_vol": int(best_t.group(8)),
                "ticket": fm.group(3),
            })
    return entries


# ─────────────────────────────────────────────────────────────────────────
# Gate checks (the v2.93 label-derived rules)
# ─────────────────────────────────────────────────────────────────────────
def get_bar_at(bars_sorted, target_minute_ep):
    """Get bar at exact minute boundary, or None."""
    return bars_sorted.get(target_minute_ep)


def gate_hhhl(bars_list, entry_idx, side, lookback=30, pivot=2):
    """Check HH+HL (BUY) or LH+LL (SELL) over the lookback period before entry."""
    if entry_idx < lookback + pivot * 2: return False
    window = bars_list[entry_idx - lookback : entry_idx]
    # Find pivot highs/lows (a bar is a pivot if higher/lower than `pivot` bars on each side)
    highs = []
    lows = []
    for i in range(pivot, len(window) - pivot):
        b = window[i]
        is_high = all(b["h"] > window[i-j]["h"] and b["h"] > window[i+j]["h"]
                      for j in range(1, pivot+1))
        is_low  = all(b["l"] < window[i-j]["l"] and b["l"] < window[i+j]["l"]
                      for j in range(1, pivot+1))
        if is_high: highs.append(b["h"])
        if is_low:  lows.append(b["l"])
    if len(highs) < 2 or len(lows) < 2: return False
    if side == "BUY":
        # need last 2 highs ascending AND last 2 lows ascending
        return highs[-1] > highs[-2] and lows[-1] > lows[-2]
    else:
        # SELL: need lows descending AND highs descending
        return highs[-1] < highs[-2] and lows[-1] < lows[-2]


def gate_neighbor_peak(bars_list, uhv_idx):
    """UHV volume must be > both immediate neighbors."""
    if uhv_idx < 1 or uhv_idx >= len(bars_list) - 1: return False
    return bars_list[uhv_idx]["v"] > bars_list[uhv_idx - 1]["v"] and \
           bars_list[uhv_idx]["v"] > bars_list[uhv_idx + 1]["v"]


def gate_uhv_body(bars_list, uhv_idx, min_ratio=0.60):
    """UHV body / range >= min_ratio."""
    b = bars_list[uhv_idx]
    rng = b["h"] - b["l"]
    if rng <= 0: return False
    body = abs(b["c"] - b["o"])
    return body / rng >= min_ratio


def gate_uhv_color(bars_list, uhv_idx, side):
    """For BUY setup (retracement DOWN), UHV must be RED.
       For SELL setup (retracement UP), UHV must be GREEN."""
    b = bars_list[uhv_idx]
    if side == "BUY":
        return b["c"] < b["o"]   # RED
    else:
        return b["c"] > b["o"]   # GREEN


def gate_breakout_body_close(bars_list, breakout_idx, uhv_h, uhv_l, side):
    """Breakout candle must have body-closed past UHV extreme."""
    if breakout_idx >= len(bars_list): return False
    b = bars_list[breakout_idx]
    if side == "BUY":
        # body close above uhv_h AND breakout is GREEN
        return b["c"] > uhv_h and b["c"] > b["o"]
    else:
        return b["c"] < uhv_l and b["c"] < b["o"]


def gate_max_bars(uhv_shift, max_bars=8):
    """UHV must be within N bars of entry."""
    return uhv_shift <= max_bars


# ─────────────────────────────────────────────────────────────────────────
# Forward P&L simulator (canonical SL + various TP windows)
# ─────────────────────────────────────────────────────────────────────────
def forward_pnl(ticks_after, side, entry, sl, tp_pts):
    """Walk forward through ticks. Exit on SL or TP. Returns (pnl_usd, hit_type, ms_to_exit)."""
    if not ticks_after: return (0.0, "no_ticks", 0)
    start_ep = ticks_after[0][0]
    for ep, bid, ask in ticks_after:
        price = bid if side == "BUY" else ask
        if side == "BUY":
            if price <= sl:
                return ((sl - entry) * DOLLARS_PER_POINT, "SL", ep - start_ep)
            if tp_pts and (price - entry) >= tp_pts:
                return (tp_pts * DOLLARS_PER_POINT, "TP", ep - start_ep)
        else:
            if price >= sl:
                return ((entry - sl) * DOLLARS_PER_POINT, "SL", ep - start_ep)
            if tp_pts and (entry - price) >= tp_pts:
                return (tp_pts * DOLLARS_PER_POINT, "TP", ep - start_ep)
    # Held to end of available ticks — close at last tick
    last_bid, last_ask = ticks_after[-1][1], ticks_after[-1][2]
    if side == "BUY":
        return ((last_bid - entry) * DOLLARS_PER_POINT, "end", ticks_after[-1][0] - start_ep)
    else:
        return ((entry - last_ask) * DOLLARS_PER_POINT, "end", ticks_after[-1][0] - start_ep)


# ─────────────────────────────────────────────────────────────────────────
# Main: build everything, apply gates, find best config
# ─────────────────────────────────────────────────────────────────────────
def main():
    print("=== Building dataset ===")
    entries = parse_entries()
    print(f"  {len(entries)} historical entries from EA logs")

    # Load + build bars for ALL available days
    all_ticks = []
    all_bars_by_minute = {}
    for csv_path in sorted(COMMON.glob("shano_ticks_2026-06-*.csv")):
        if csv_path.stat().st_size < 1000: continue
        t = load_ticks(csv_path)
        all_ticks.extend(t)
        b = build_m1_bars(t)
        all_bars_by_minute.update(b)
    all_ticks.sort(key=lambda x: x[0])
    tick_keys = [t[0] for t in all_ticks]
    sorted_minutes = sorted(all_bars_by_minute.keys())
    bars_list = [all_bars_by_minute[m] for m in sorted_minutes]
    minute_to_idx = {m: i for i, m in enumerate(sorted_minutes)}
    print(f"  {len(all_ticks):,} ticks, {len(bars_list):,} M1 bars")
    print()

    # For each entry, find its position in bars_list AND ticks
    enriched = []
    for e in entries:
        fill_ep = ea_time_to_utc_ep(e["date"], e["trigger_t"], e["trigger_ms"])
        minute_ep = (fill_ep // 60000) * 60000
        if minute_ep not in minute_to_idx: continue
        entry_idx = minute_to_idx[minute_ep]
        if entry_idx < 50: continue   # need lookback for HHHL
        uhv_idx = entry_idx - e["uhv_shift"]
        if uhv_idx < 0: continue
        e["entry_idx"] = entry_idx
        e["uhv_idx"]   = uhv_idx
        e["fill_ep"]   = fill_ep
        enriched.append(e)
    print(f"Entries with usable bar context: {len(enriched)}/{len(entries)}")
    print()

    # ─────────────────────────────────────────────────────────────────
    # Apply gates one by one — show how many survive each
    # ─────────────────────────────────────────────────────────────────
    gates = [
        ("trend_HHHL",         lambda e: gate_hhhl(bars_list, e["entry_idx"], e["side"])),
        ("uhv_color_correct",  lambda e: gate_uhv_color(bars_list, e["uhv_idx"], e["side"])),
        ("uhv_body>=0.60",     lambda e: gate_uhv_body(bars_list, e["uhv_idx"], 0.60)),
        ("neighbor_peak",      lambda e: gate_neighbor_peak(bars_list, e["uhv_idx"])),
        ("max_bars_uhv<=8",    lambda e: gate_max_bars(e["uhv_shift"], 8)),
        ("breakout_body_close",lambda e: gate_breakout_body_close(
            bars_list, e["entry_idx"] - 1,
            bars_list[e["uhv_idx"]]["h"], bars_list[e["uhv_idx"]]["l"],
            e["side"])),
    ]

    print("=== Single-gate filter pass rate (out of {} entries) ===".format(len(enriched)))
    for name, fn in gates:
        passed = sum(1 for e in enriched if fn(e))
        print(f"  {name:>22s}: {passed:3d} pass ({100*passed/max(len(enriched),1):.1f}%)")
    print()

    # ─────────────────────────────────────────────────────────────────
    # Combination sweep — test multiple gate subsets
    # ─────────────────────────────────────────────────────────────────
    print("=== Combo sweep: which subset of gates gives best P&L? ===\n")
    gate_names = [g[0] for g in gates]

    def survivors_for_subset(subset_idx):
        active_fns = [gates[i][1] for i in subset_idx]
        return [e for e in enriched if all(fn(e) for fn in active_fns)]

    def evaluate_pnl(survs, tp_pts=5.0):
        if not survs: return (0, 0, 0, 0.0)
        wins = 0; total = 0.0; tp_count = 0
        for e in survs:
            i = bisect.bisect_left(tick_keys, e["fill_ep"])
            forward = all_ticks[i:i+10000]
            pnl, ht, _ = forward_pnl(forward, e["side"], e["entry"], e["sl"], tp_pts)
            total += pnl
            if pnl > 0: wins += 1
            if ht == "TP": tp_count += 1
        n = len(survs)
        return (n, wins, tp_count, total)

    # Test: ALL gates, then DROP each gate one at a time, then DROP pairs
    best_configs = []

    # baseline: no gates
    n, w, tp, total = evaluate_pnl(enriched, 5.0)
    print(f"  BASELINE (no gates):       n={n:>3d}  W={w:>2d}  TPhit={tp:>2d}  WR={100*w/max(n,1):.1f}%  total=${total:+.2f}")

    # all gates
    survs = survivors_for_subset(list(range(len(gates))))
    n, w, tp, total = evaluate_pnl(survs, 5.0)
    best_configs.append(("ALL_6_gates", n, w, total))
    print(f"  ALL 6 gates:               n={n:>3d}  W={w:>2d}  TPhit={tp:>2d}  WR={100*w/max(n,1):.1f}%  total=${total:+.2f}")

    # drop one
    for skip in range(len(gates)):
        subset = [i for i in range(len(gates)) if i != skip]
        survs = survivors_for_subset(subset)
        n, w, tp, total = evaluate_pnl(survs, 5.0)
        label = f"5 gates (skip {gate_names[skip]})"
        best_configs.append((label, n, w, total))
        print(f"  {label:<35s}  n={n:>3d}  W={w:>2d}  TPhit={tp:>2d}  WR={100*w/max(n,1):.1f}%  total=${total:+.2f}")

    # drop two
    print()
    for skip_pair in itertools.combinations(range(len(gates)), 2):
        subset = [i for i in range(len(gates)) if i not in skip_pair]
        survs = survivors_for_subset(subset)
        n, w, tp, total = evaluate_pnl(survs, 5.0)
        if n < 5: continue
        label = f"4 gates (skip {gate_names[skip_pair[0]]}+{gate_names[skip_pair[1]]})"
        best_configs.append((label, n, w, total))
        print(f"  {label:<55s}  n={n:>3d}  W={w:>2d}  WR={100*w/max(n,1):.1f}%  total=${total:+.2f}")

    # drop three (keep 3 gates)
    print()
    for skip_triple in itertools.combinations(range(len(gates)), 3):
        subset = [i for i in range(len(gates)) if i not in skip_triple]
        survs = survivors_for_subset(subset)
        n, w, tp, total = evaluate_pnl(survs, 5.0)
        if n < 5: continue
        skipped = "+".join(gate_names[i] for i in skip_triple)
        label = f"3 gates (skip {skipped})"
        best_configs.append((label, n, w, total))
        if total > 0 or 100*w/max(n,1) > 40:
            print(f"  {label:<75s}  n={n:>3d}  W={w:>2d}  WR={100*w/max(n,1):.1f}%  total=${total:+.2f}")

    # Final survivors using ALL gates for the report
    survivors = survivors_for_subset(list(range(len(gates))))
    print()
    print(f"=== Top 10 configs by TOTAL $ ===")
    best_configs.sort(key=lambda x: -x[3])
    for name, n, w, total in best_configs[:10]:
        wr = 100*w/max(n,1)
        print(f"  ${total:+8.2f}  n={n:>3d} WR={wr:>4.1f}%  ← {name}")

    # Use the WINNING config (top one with n>=10) for the detailed report
    winner = None
    for name, n, w, total in best_configs:
        if n >= 10 and total > 0:
            winner = (name, n, w, total)
            break
    if not winner and best_configs:
        winner = best_configs[0]

    if winner:
        print(f"\n=== WINNING CONFIG: {winner[0]} ===")
        # reconstruct survivors for the winner
        # Parse "X gates (skip A+B)" to find the skipped indices
        skipped_names = []
        if "skip " in winner[0]:
            skipped_str = winner[0].split("skip ")[1].rstrip(")")
            skipped_names = skipped_str.split("+")
        winning_subset = [i for i, gname in enumerate(gate_names) if gname not in skipped_names]
        survivors = survivors_for_subset(winning_subset)

    if not survivors:
        print("\n(No survivors — see top combos above)")
        return

    # ─────────────────────────────────────────────────────────────────
    # Forward P&L on survivors — try multiple TP/SL configs
    # ─────────────────────────────────────────────────────────────────
    print(f"=== Survivor P&L at different exit configs ===")
    print(f"  Each survivor: canonical SL from EA log, TP varies")
    print()
    print(f"  {'TP_pts':>7s}  {'Wins':>4s}  {'Losses':>6s}  {'WR%':>5s}  "
          f"{'AvgP&L':>7s}  {'TotalP&L':>9s}  {'TPhits':>6s}  {'SLhits':>6s}")
    print("  " + "-" * 70)
    for tp_pts in [2.0, 3.0, 5.0, 10.0, 20.0]:
        pnls = []
        tp_count = 0; sl_count = 0
        for e in survivors:
            # Forward ticks from fill_ep
            i = bisect.bisect_left(tick_keys, e["fill_ep"])
            forward = all_ticks[i:i+10000]   # cap to ~10k ticks forward
            pnl, ht, _ = forward_pnl(forward, e["side"], e["entry"], e["sl"], tp_pts)
            pnls.append(pnl)
            if ht == "TP": tp_count += 1
            elif ht == "SL": sl_count += 1
        n = len(pnls); wins = sum(1 for p in pnls if p > 0)
        wr = 100 * wins / n
        avg = sum(pnls) / n
        print(f"  {tp_pts:>5.1f}pt  {wins:>4d}  {n-wins:>6d}  {wr:>4.1f}%  "
              f"${avg:>+6.2f}  ${sum(pnls):>+8.2f}  {tp_count:>6d}  {sl_count:>6d}")

    # Per-day breakdown at TP=5pt
    print()
    print(f"=== Per-day survivors @ TP=5pt ===")
    by_date = defaultdict(list)
    for e in survivors:
        i = bisect.bisect_left(tick_keys, e["fill_ep"])
        forward = all_ticks[i:i+10000]
        pnl, ht, _ = forward_pnl(forward, e["side"], e["entry"], e["sl"], 5.0)
        by_date[e["date"]].append((pnl, ht, e["side"]))
    for date, plist in sorted(by_date.items()):
        n = len(plist); total = sum(p[0] for p in plist)
        wins = sum(1 for p in plist if p[0] > 0)
        emoji = "🎉" if total > 0 else "💔"
        print(f"  {emoji} {date}  n={n:>2d}  wins={wins:>2d}  total=${total:+.2f}")


if __name__ == "__main__":
    main()
