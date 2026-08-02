"""backtest_autoclose_today.py — find the optimal auto-close-ms for TODAY's
actual fired entries against TODAY's actual broker ticks.

Inputs:
  - 32 entries from MT5 Experts log (timestamp, side, entry price)
  - shano_ticks_2026-06-19.csv (full day ticks at millisecond precision)

For each candidate exit window X ms ∈ {50, 100, 250, 500, 1000, 2000, 5000,
10000, 30000, 60000, 300000}, compute per-trade P&L if EA had closed at
exactly X ms after entry, then aggregate.

Output: which X is most profitable. Most-probable-positive-exit window.
"""
from pathlib import Path
import re, csv, sys, bisect
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
COMMON   = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TICK_CSV = COMMON / "shano_ticks_2026-06-19.csv"
LOTS     = 0.30   # current EA lot size
DOLLARS_PER_POINT_AT_LOT = 100.0 * LOTS   # XAUUSD: 1pt = $100 at 1.0 lot → $30 at 0.30 lots

# Candidate exit windows in milliseconds
WINDOWS = [50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000,
           10000, 20000, 30000, 60000, 120000, 300000, 600000]


def parse_log_entries() -> list[dict]:
    """Read today's filled entries from MT5 Experts log."""
    logs = sorted((TERMINAL / "MQL5/Logs").glob("20260619*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print("No 20260619*.log found"); return []
    with open(logs[0], "rb") as f:
        content = f.read().decode("utf-16le", errors="ignore")

    # Match: "HH:MM:SS.xxx	... S1 [BUY|SELL] LIVE TRIGGER — entry=XXXX.XX sl=...
    # then on a NEAR-FUTURE line: [FILLED] ticket=N
    trigger_re = re.compile(
        r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*S1 (BUY|SELL) LIVE TRIGGER[^\n]*entry=([\d.]+)"
    )
    fills_re = re.compile(
        r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*\[FILLED\] ticket=(\d+)"
    )

    triggers = [(m.group(1), int(m.group(2)), m.group(3), float(m.group(4)))
                for m in trigger_re.finditer(content)]
    fills = [(m.group(1), int(m.group(2)), m.group(3))
             for m in fills_re.finditer(content)]

    # Pair each fill with the most recent trigger
    entries = []
    for f_time, f_ms, ticket in fills:
        # find the latest trigger before this fill (same HH:MM:SS roughly)
        best = None
        for t_time, t_ms, side, price in triggers:
            if t_time <= f_time:
                best = (t_time, t_ms, side, price)
        if best is None: continue
        # build entry record
        entries.append({
            "trigger_t": best[0],
            "trigger_ms": best[1],
            "fill_t": f_time,
            "fill_ms": f_ms,
            "side": best[2],
            "entry": best[3],
            "ticket": ticket,
        })

    return entries


def load_ticks() -> list[tuple[int, float, float]]:
    """Load all ticks as (epoch_ms, bid, ask)."""
    if not TICK_CSV.exists():
        print(f"Tick CSV not found: {TICK_CSV}")
        print("Please drag ExportTodayTicks.mq5 onto MT5 XAUUSD chart first.")
        return []
    ticks = []
    with open(TICK_CSV, "r", encoding="utf-8") as f:
        f.readline()   # header
        for line in f:
            try:
                t, bid, ask = line.strip().split(",")
                # t = "2026.06.19 HH:MM:SS.mmm"
                dt = datetime.strptime(t, "%Y.%m.%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                epoch_ms = int(dt.timestamp() * 1000)
                ticks.append((epoch_ms, float(bid), float(ask)))
            except Exception:
                continue
    print(f"Loaded {len(ticks):,} ticks from {TICK_CSV.name}")
    return ticks


def tick_at(ticks: list, target_epoch_ms: int) -> tuple[float, float] | None:
    """Binary-search for the tick at or just after target_epoch_ms. Returns (bid, ask)."""
    epoch_keys = [t[0] for t in ticks]
    i = bisect.bisect_left(epoch_keys, target_epoch_ms)
    if i >= len(ticks):
        return None
    _, bid, ask = ticks[i]
    return bid, ask


def hh_mm_ss_ms_to_epoch(time_str: str, ms: int) -> int:
    """Convert EA-log HH:MM:SS + ms-fraction to UTC epoch_ms.
    Empirically determined: Blueberry MT5 server = GMT+2.
    EA log "10:34" corresponds to UTC "08:34" (verified by matching entry price
    4133.08 to tick CSV bid 4133.71 at UTC 08:34)."""
    BROKER_OFFSET_HOURS = 2
    dt = datetime.strptime("2026-06-19 " + time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dt = dt - timedelta(hours=BROKER_OFFSET_HOURS)
    return int(dt.timestamp() * 1000) + ms


def main():
    print("=== Backtest auto-close-ms windows on TODAY's broker ticks ===\n")
    entries = parse_log_entries()
    print(f"Parsed {len(entries)} entries from EA log\n")
    if not entries: return

    ticks = load_ticks()
    if not ticks:
        print("\n→ Drag ExportTodayTicks.mq5 from Navigator > Scripts onto XAUUSD chart")
        print("  Default date range is already 2026-06-19 (today UTC)")
        print("  Then re-run this script.")
        return

    epoch_keys = [t[0] for t in ticks]

    # For each entry, find fill tick (price + epoch)
    # For each candidate window, find the tick at fill+X ms and compute P&L
    print(f"{'window':>10s}  {'wins':>5s}  {'losses':>6s}  {'WR%':>6s}  "
          f"{'avg$':>8s}  {'med$':>8s}  {'total$':>10s}  {'best$':>8s}  {'worst$':>8s}")
    print(f"{'-'*78}")

    summary = []
    # Tolerance: only include a trade if a tick exists within this many ms of the target close moment.
    # Without this, gaps in tick data inflate results (the next tick may be seconds later).
    TICK_TOLERANCE_MS = 250

    for window_ms in WINDOWS:
        pnls = []
        skipped_gap = 0
        for e in entries:
            fill_epoch_ms = hh_mm_ss_ms_to_epoch(e["fill_t"], e["fill_ms"])
            exit_epoch_ms = fill_epoch_ms + window_ms
            # Use last tick AT-OR-BEFORE exit_epoch_ms (what EA would actually see when timer fires).
            i = bisect.bisect_right(epoch_keys, exit_epoch_ms) - 1
            if i < 0 or i >= len(ticks):
                continue
            tick_epoch, bid, ask = ticks[i]
            gap_ms = exit_epoch_ms - tick_epoch
            if gap_ms > TICK_TOLERANCE_MS:
                skipped_gap += 1
                continue
            if e["side"] == "BUY":
                pts = bid - e["entry"]
            else:
                pts = e["entry"] - ask
            pnl = pts * DOLLARS_PER_POINT_AT_LOT
            pnls.append(pnl)

        if not pnls:
            print(f"  {window_ms:>8d}ms  (no usable ticks at this offset)")
            continue
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        n = len(pnls)
        wr = 100 * wins / n
        total = sum(pnls)
        avg = total / n
        med = sorted(pnls)[n // 2]
        best = max(pnls); worst = min(pnls)
        summary.append((window_ms, wins, losses, wr, avg, med, total, best, worst, n, skipped_gap))
        unit = "ms" if window_ms < 1000 else "s "
        v = window_ms if window_ms < 1000 else window_ms // 1000
        label = f"{v}{unit}"
        print(f"  {label:>8s}  n={n:>2d}  skip={skipped_gap:>2d}  {wins:>3d}W/{losses:>2d}L  "
              f"WR={wr:>5.1f}%  avg={avg:>+7.2f}  total={total:>+9.2f}  best={best:>+7.2f}  worst={worst:>+7.2f}")

    # Pick the winners — but only consider windows with enough sample size
    print()
    qualified = [s for s in summary if s[9] >= 20]   # need n >= 20 trades for reliability
    by_total = sorted(qualified, key=lambda x: -x[6])
    by_wr    = sorted(qualified, key=lambda x: -x[3])
    print("=== Best by TOTAL $ (windows with >= 20 valid trades) ===")
    for s in by_total[:5]:
        w, win, lose, wr, avg, med, total, b, wo, n, skip = s
        print(f"  {w:>6d} ms  →  total ${total:+.2f}  ({win}W/{lose}L, WR={wr:.1f}%, n={n}, skipped={skip})")
    print()
    print("=== Best by WIN RATE (windows with >= 20 valid trades) ===")
    for s in by_wr[:5]:
        w, win, lose, wr, avg, med, total, b, wo, n, skip = s
        print(f"  {w:>6d} ms  →  WR={wr:.1f}%  (total ${total:+.2f}, {win}W/{lose}L, n={n})")


if __name__ == "__main__":
    main()
