"""backtest_autoclose_multiday.py — find the optimal auto-close-ms window
aggregated over MULTIPLE days of S1Trader entries.

Reads:
  - All available shano_ticks_YYYY-MM-DD.csv files in Common\\Files
  - All available YYYYMMDD.log files in MT5/MQL5/Logs

For each (entry, exit_window_ms) pair, computes P&L using broker tick data
with the verified GMT+2 broker time offset. Aggregates across all days.

Designed to answer: "is the auto-close-ms unprofitability a daily fluke,
or a structural problem with the strategy?"
"""
from pathlib import Path
import re, sys, bisect
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
COMMON   = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOG_DIR  = TERMINAL / "MQL5/Logs"
LOTS     = 0.30
DOLLARS_PER_POINT = 100.0 * LOTS
BROKER_OFFSET_HOURS = 2   # EA log time - 2h = UTC (Blueberry MT5 server = GMT+2)
TICK_TOLERANCE_MS   = 250

WINDOWS = [50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000,
           10000, 20000, 30000, 60000, 120000, 300000, 600000]


def parse_log_for_date(log_path: Path, date_str: str) -> list[dict]:
    """Parse one EA log. date_str = 'YYYY-MM-DD'."""
    with open(log_path, "rb") as f:
        content = f.read().decode("utf-16le", errors="ignore")

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

    entries = []
    used_trig = set()
    for f_time, f_ms, ticket in fills:
        # Pair with the LATEST trigger before this fill that hasn't been used
        best_idx = -1
        for ti, (t_time, t_ms, side, price) in enumerate(triggers):
            if ti in used_trig: continue
            if (t_time, t_ms) <= (f_time, f_ms):
                best_idx = ti
        if best_idx < 0: continue
        used_trig.add(best_idx)
        t_time, t_ms, side, price = triggers[best_idx]
        entries.append({
            "date": date_str,
            "trigger_t": t_time, "trigger_ms": t_ms,
            "fill_t": f_time, "fill_ms": f_ms,
            "side": side, "entry": price, "ticket": ticket,
        })
    return entries


def load_tick_csv(csv_path: Path, date_str: str) -> list[tuple[int, float, float]]:
    """Load ticks for one day."""
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


def ea_log_time_to_utc_epoch_ms(date_str: str, time_str: str, ms: int) -> int:
    """Convert EA log timestamp (broker GMT+2) to UTC epoch ms."""
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dt = dt - timedelta(hours=BROKER_OFFSET_HOURS)
    return int(dt.timestamp() * 1000) + ms


def main():
    print("=== MULTI-DAY auto-close-ms backtest ===\n")
    # Discover available date overlap of (log file × tick CSV)
    available_dates = []
    for log_path in sorted(LOG_DIR.glob("20260*.log")):
        if log_path.stat().st_size < 1000: continue  # skip empty/tiny logs
        yyyymmdd = log_path.stem
        if len(yyyymmdd) != 8: continue
        date_str = f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
        tick_csv = COMMON / f"shano_ticks_{date_str}.csv"
        # Tick file must also be available for the (broker+2h)-UTC ranges
        # Since broker time is GMT+2, broker-day 06-19 spans UTC 06-18 22:00 to 06-19 22:00.
        # We need BOTH the previous-day csv AND the date csv.
        prev_dt = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        prev_csv = COMMON / f"shano_ticks_{prev_dt.strftime('%Y-%m-%d')}.csv"
        has_today = tick_csv.exists() and tick_csv.stat().st_size > 1000
        has_prev = prev_csv.exists() and prev_csv.stat().st_size > 1000
        if has_today:
            available_dates.append((date_str, tick_csv, prev_csv if has_prev else None, log_path))

    if not available_dates:
        print("No log + tick file pairs available yet.")
        print("Drag ExportRecentTicks.mq5 in MT5 first.")
        return

    print(f"Eligible days: {len(available_dates)}")
    for d, tcsv, pcsv, log in available_dates:
        prev = pcsv.name if pcsv else "—"
        print(f"  {d}  log_size={log.stat().st_size//1024}kB  ticks={tcsv.name}  prev_ticks={prev}")
    print()

    # Aggregate: load entries from each day's log and ticks from BOTH that day and the prior day
    all_entries = []
    all_ticks   = []  # (epoch_ms, bid, ask)
    seen_dates  = set()
    for date_str, tick_csv, prev_csv, log_path in available_dates:
        entries = parse_log_for_date(log_path, date_str)
        all_entries.extend(entries)
        if date_str not in seen_dates:
            all_ticks.extend(load_tick_csv(tick_csv, date_str))
            seen_dates.add(date_str)
        if prev_csv and prev_csv.stem.replace("shano_ticks_", "") not in seen_dates:
            d = prev_csv.stem.replace("shano_ticks_", "")
            all_ticks.extend(load_tick_csv(prev_csv, d))
            seen_dates.add(d)

    # Sort ticks by epoch
    all_ticks.sort(key=lambda x: x[0])
    epoch_keys = [t[0] for t in all_ticks]

    print(f"Total entries:  {len(all_entries)}")
    print(f"Total ticks:    {len(all_ticks):,}")
    print()

    if not all_entries:
        print("No entries parsed from logs."); return
    if not all_ticks:
        print("No ticks available. Drag ExportRecentTicks.mq5 in MT5."); return

    # Run backtest
    print(f"{'window':>8s}  {'n':>3s}  {'skip':>4s}  {'W':>3s}/{'L':>3s}  "
          f"{'WR%':>5s}  {'avg':>7s}  {'med':>7s}  {'total':>9s}  {'best':>7s}  {'worst':>7s}")
    print("-" * 86)

    summary = []
    for window_ms in WINDOWS:
        pnls = []
        skipped = 0
        for e in all_entries:
            fill_epoch = ea_log_time_to_utc_epoch_ms(e["date"], e["fill_t"], e["fill_ms"])
            exit_target = fill_epoch + window_ms
            i = bisect.bisect_right(epoch_keys, exit_target) - 1
            if i < 0 or i >= len(all_ticks):
                skipped += 1; continue
            tick_epoch, bid, ask = all_ticks[i]
            gap = exit_target - tick_epoch
            if gap > TICK_TOLERANCE_MS:
                skipped += 1; continue
            if e["side"] == "BUY":
                pts = bid - e["entry"]
            else:
                pts = e["entry"] - ask
            pnls.append(pts * DOLLARS_PER_POINT)

        if not pnls:
            print(f"  {window_ms:>6d}ms   (no valid trades)")
            continue
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = n - wins
        wr = 100 * wins / n
        total = sum(pnls); avg = total / n
        med = sorted(pnls)[n // 2]
        best = max(pnls); worst = min(pnls)
        summary.append((window_ms, wins, losses, wr, avg, med, total, best, worst, n, skipped))

        unit = "ms" if window_ms < 1000 else "s "
        v = window_ms if window_ms < 1000 else window_ms // 1000
        label = f"{v}{unit}"
        print(f"  {label:>6s}  {n:>3d}  {skipped:>4d}  {wins:>3d}/{losses:>3d}  "
              f"{wr:>4.1f}%  {avg:>+7.2f}  {med:>+7.2f}  {total:>+9.2f}  {best:>+7.2f}  {worst:>+7.2f}")

    # Best windows by aggregate criteria
    print()
    qualified = [s for s in summary if s[9] >= 50]
    by_total = sorted(qualified, key=lambda x: -x[6])
    by_wr    = sorted(qualified, key=lambda x: -x[3])

    print("=== Best by TOTAL $ (windows with >= 50 valid trades) ===")
    for s in by_total[:5]:
        w, win, lose, wr, avg, med, total, b, wo, n, skip = s
        print(f"  {w:>6d} ms  →  total ${total:+.2f}  (WR={wr:.1f}%, n={n}, avg ${avg:+.2f})")
    print()
    print("=== Best by WIN RATE (windows with >= 50 valid trades) ===")
    for s in by_wr[:5]:
        w, win, lose, wr, avg, med, total, b, wo, n, skip = s
        print(f"  {w:>6d} ms  →  WR={wr:.1f}%  (total ${total:+.2f}, n={n})")

    # Per-day breakdown
    print()
    print("=== Per-day P&L at 500ms (current setting) ===")
    by_date = defaultdict(list)
    for e in all_entries:
        fill_epoch = ea_log_time_to_utc_epoch_ms(e["date"], e["fill_t"], e["fill_ms"])
        exit_target = fill_epoch + 500
        i = bisect.bisect_right(epoch_keys, exit_target) - 1
        if i < 0 or i >= len(all_ticks): continue
        tick_epoch, bid, ask = all_ticks[i]
        if exit_target - tick_epoch > TICK_TOLERANCE_MS: continue
        if e["side"] == "BUY":
            pts = bid - e["entry"]
        else:
            pts = e["entry"] - ask
        by_date[e["date"]].append(pts * DOLLARS_PER_POINT)
    for date, pnls in sorted(by_date.items()):
        if not pnls: continue
        n = len(pnls); wins = sum(1 for p in pnls if p > 0)
        wr = 100 * wins / n
        total = sum(pnls)
        emoji = "🎉" if total > 0 else "💔"
        print(f"  {emoji} {date}  n={n:>2d}  WR={wr:>5.1f}%  total ${total:+.2f}")


if __name__ == "__main__":
    main()
