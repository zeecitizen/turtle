"""calibrate_execution_model.py — measure empirical latency and slippage against the backtest's assumptions.

For each row in turtle_fills.csv:
  1. Find the bid/ask at the SEND timestamp in shano_ticks_*.csv
  2. Compute empirical latency = actual_fill_time - send_time
  3. Compute empirical slippage = actual_fill_price - intended_price_at_send

Compare the empirical distribution to the backtest constants:
  LAT_MEAN=300ms, LAT_STDEV=100ms, LAT_MIN=150ms, LAT_MAX=600ms (Gaussian)
  SLIP_PIPS=0.5 (constant)

If empirical reality differs significantly, update those constants in
pdf4_loo_realistic.py and the simulation becomes properly calibrated.

Usage:
  python calibrate_execution_model.py
"""
from __future__ import annotations
import csv, statistics
from pathlib import Path
from datetime import datetime, timedelta

COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
FILLS_CSV = COMMON_DIR / "turtle_fills.csv"

# Backtest constants we want to validate
ASSUMED_LAT_MEAN_MS  = 300
ASSUMED_LAT_STDEV_MS = 100
ASSUMED_SLIP_PIPS    = 0.5
PIP_SIZE             = 0.10  # XAUUSD 1 pip = $0.10 price move


def load_ticks_for_dates(dates):
    """Load tick CSVs for the given set of dates. Returns dict {date: list of (dt, bid, ask)}."""
    out = {}
    for d in dates:
        path = COMMON_DIR / f"shano_ticks_{d}.csv"
        if not path.exists():
            continue
        ticks = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4: continue
                try:
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S").replace(microsecond=int(parts[1])*1000)
                    bid = float(parts[2]); ask = float(parts[3])
                    ticks.append((dt, bid, ask))
                except (ValueError, IndexError):
                    continue
        out[d] = ticks
    return out


def find_quote_at(ticks, target_dt):
    """Find the most recent tick at or before target_dt."""
    last = None
    for t in ticks:
        if t[0] > target_dt:
            return last
        last = t
    return last


def parse_fills():
    """Read turtle_fills.csv. Expected columns vary by EA version; return list of dicts."""
    if not FILLS_CSV.exists():
        print(f"[ERR] {FILLS_CSV} not found")
        return []
    out = []
    with open(FILLS_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(row)
    return out


def main():
    print(f"Loading {FILLS_CSV}...")
    fills = parse_fills()
    if not fills:
        print("No fills to analyze. Run a few live trades first, then re-run this script.")
        return

    print(f"  Found {len(fills)} fill rows")
    print(f"  Columns: {list(fills[0].keys())}")
    print()

    # Detect which columns we have. EA versions vary.
    # We need: send_time (or order_time), fill_time (or deal_time), intended_price, fill_price
    # If columns are different, print a sample row so the user can see what's available.
    print("Sample fill row:")
    for k, v in fills[0].items():
        print(f"  {k}: {v}")
    print()

    # Try common column patterns
    # Pattern 1: time (single timestamp), price, side, lots
    # Pattern 2: send_ts + fill_ts + intended_price + fill_price

    has_send_fill = any("send" in k.lower() for k in fills[0].keys()) and \
                    any("fill" in k.lower() for k in fills[0].keys())

    if not has_send_fill:
        print("=" * 80)
        print("LIMITATION: turtle_fills.csv only logs the FILL event, not the SEND event.")
        print("To measure empirical latency, the EA must log BOTH timestamps.")
        print()
        print("Recommendation: extend ShanoExitManager.mq5 to write a richer CSV with:")
        print("  - order_send_ts (TimeCurrent() right before g_trade.Buy/Sell)")
        print("  - order_fill_ts (TimeCurrent() right after, on success)")
        print("  - intended_price (bid/ask snapshot at send moment)")
        print("  - fill_price (actual fill from g_trade.ResultPrice())")
        print("  - intended_dir, lots, ticket")
        print()
        print("Alternative approach for partial calibration:")
        print("  - Use shano_live.json snapshots (1Hz) to estimate bid/ask at fill time")
        print("  - Compare fill_price to closest bid/ask snapshot")
        print("  - This gives slippage estimate but NOT latency (we don't know send time)")
        print("=" * 80)
        return

    # If we have send + fill columns, do the full calibration
    latencies_ms = []
    slippages_pips = []

    # Group fills by date so we only load the relevant tick CSVs
    fill_dates = set()
    for f in fills:
        for k in f:
            if "time" in k.lower() and f[k]:
                try:
                    dt = datetime.fromisoformat(f[k].replace(" ", "T"))
                    fill_dates.add(dt.strftime("%Y-%m-%d"))
                    break
                except Exception:
                    continue

    print(f"Loading tick data for {len(fill_dates)} dates: {sorted(fill_dates)}...")
    ticks_by_date = load_ticks_for_dates(sorted(fill_dates))
    print(f"  Loaded {sum(len(v) for v in ticks_by_date.values()):,} total ticks")
    print()

    for f in fills:
        # Extract send + fill columns (best-effort)
        send_col = next((k for k in f if "send" in k.lower()), None)
        fill_col = next((k for k in f if "fill" in k.lower() and "time" in k.lower()), None)
        if not send_col or not fill_col: continue
        try:
            send_dt = datetime.fromisoformat(f[send_col].replace(" ", "T"))
            fill_dt = datetime.fromisoformat(f[fill_col].replace(" ", "T"))
        except Exception:
            continue
        lat_ms = (fill_dt - send_dt).total_seconds() * 1000
        latencies_ms.append(lat_ms)

        # Slippage (if intended_price is logged)
        intended_col = next((k for k in f if "intended" in k.lower() or "send_price" in k.lower()), None)
        fill_price_col = next((k for k in f if "fill_price" in k.lower() or "deal_price" in k.lower()), None)
        if intended_col and fill_price_col:
            try:
                intended = float(f[intended_col])
                actual = float(f[fill_price_col])
                slip_pts = abs(actual - intended)
                slip_pips = slip_pts / PIP_SIZE
                slippages_pips.append(slip_pips)
            except Exception:
                pass

    if latencies_ms:
        print("=" * 80)
        print("EMPIRICAL LATENCY (actual broker round-trip)")
        print("=" * 80)
        s = sorted(latencies_ms); n = len(s)
        print(f"  n={n}")
        print(f"  min={min(s):.0f}ms  q25={s[n//4]:.0f}ms  median={s[n//2]:.0f}ms  q75={s[3*n//4]:.0f}ms  q95={s[int(n*0.95)]:.0f}ms  max={max(s):.0f}ms")
        print(f"  mean={statistics.mean(s):.0f}ms  stdev={statistics.stdev(s) if n > 1 else 0:.0f}ms")
        print()
        print(f"BACKTEST ASSUMPTIONS: mean={ASSUMED_LAT_MEAN_MS}ms, stdev={ASSUMED_LAT_STDEV_MS}ms, [150-600ms]")
        if abs(statistics.mean(s) - ASSUMED_LAT_MEAN_MS) > 50:
            print(f"  WARNING: empirical mean differs from assumption by {abs(statistics.mean(s) - ASSUMED_LAT_MEAN_MS):.0f}ms")
            print(f"  ACTION: update LAT_MEAN in pdf4_loo_realistic.py to {statistics.mean(s):.0f}")
        print()

    if slippages_pips:
        print("=" * 80)
        print("EMPIRICAL SLIPPAGE (actual fill vs intended price)")
        print("=" * 80)
        s = sorted(slippages_pips); n = len(s)
        print(f"  n={n}")
        print(f"  min={min(s):.2f}pips  q25={s[n//4]:.2f}  median={s[n//2]:.2f}  q75={s[3*n//4]:.2f}  q95={s[int(n*0.95)]:.2f}  max={max(s):.2f}pips")
        print(f"  mean={statistics.mean(s):.2f}pips  stdev={statistics.stdev(s) if n > 1 else 0:.2f}pips")
        print()
        print(f"BACKTEST ASSUMPTION: SLIP_PIPS={ASSUMED_SLIP_PIPS} (constant)")
        if abs(statistics.mean(s) - ASSUMED_SLIP_PIPS) > 0.2:
            print(f"  WARNING: empirical slip differs from assumption")
            print(f"  ACTION: update SLIP_PIPS in pdf4_loo_realistic.py to {statistics.mean(s):.2f} (or use distribution)")
        print()


if __name__ == "__main__":
    main()
