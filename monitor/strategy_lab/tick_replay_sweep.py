"""tick_replay_sweep.py — replays each confirmed probe's main trade through
real ticks with arbitrary (probeConfirm, fearIdeal) settings.

Unlike compute_experiment.py which just clips the FINAL outcome, this walks
the tick stream and applies fearIdeal at every tick — so a trade that dips
to -$20 mid-flight and recovers to +$10 will correctly stop at -$10 if
that's the experiment's fearIdeal.

Usage:
    python tick_replay_sweep.py
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

# Fixed per Shano's rules
TRAIL_TRIGGER = 8.0
TRAIL_DROP = 2.0
MAIN_LOTS = 0.40
CONTRACT_SIZE = 100
MAIN_HORIZON_SEC = 600


def parse_tick_ts(s: str):
    return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")


def daily_tick_path(date: datetime):
    return COMMON_DIR / f"shano_ticks_{date.strftime('%Y-%m-%d')}.csv"


def read_ticks_in_range(t_start: datetime, t_end: datetime):
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        p = daily_tick_path(cur)
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                next(f, None)
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
        cur += timedelta(days=1)
    return out


def simulate_main(entry_price, dir_sign, ticks, fear_ideal):
    """Walk tick stream applying trail + custom fearIdeal. Returns (pnl, reason)."""
    if not ticks:
        return 0.0, "no_data"
    peak = 0.0
    last_profit = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry_price) * MAIN_LOTS * CONTRACT_SIZE
        else:
            profit = (entry_price - ask) * MAIN_LOTS * CONTRACT_SIZE
        last_profit = profit
        if profit > peak:
            peak = profit
        if profit <= -fear_ideal:
            return round(profit, 2), f"fearIdeal@{fear_ideal}"
        if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP:
            return round(profit, 2), f"trail (peak ${peak:.2f})"
    return round(last_profit, 2), "horizon_end"


def find_confirm_tick(probe_ticks, entry_price, dir_sign, threshold):
    """First tick where favorable move (in dollars on 0.01 lot) crossed threshold."""
    for dt, bid, ask in probe_ticks:
        if dir_sign == 1:
            fav = (bid - entry_price) * 0.01 * CONTRACT_SIZE
        else:
            fav = (entry_price - ask) * 0.01 * CONTRACT_SIZE
        if fav >= threshold:
            return (dt, bid, ask)
    return None


def f(v):
    try: return float(v) if v not in ("", None, "None") else None
    except: return None


def i(v):
    try: return int(v)
    except: return 0


def replay_probe(probe_row, probe_confirm, fear_ideal):
    """Run a single probe with custom params. Returns sim_main_pnl or None."""
    entry_time = datetime.fromisoformat(probe_row["entry_time"])
    close_time = datetime.fromisoformat(probe_row["close_time"])
    entry_price = float(probe_row["entry_price"])
    dir_sign = 1 if probe_row["dir"] == "buy" else -1

    probe_ticks = read_ticks_in_range(entry_time, close_time)
    if not probe_ticks:
        return None

    confirm = find_confirm_tick(probe_ticks, entry_price, dir_sign, probe_confirm)
    if not confirm:
        return None  # would not have confirmed

    confirm_dt = confirm[0]
    main_entry = confirm[2] if dir_sign == 1 else confirm[1]
    main_horizon_end = close_time + timedelta(seconds=MAIN_HORIZON_SEC)
    main_ticks = read_ticks_in_range(confirm_dt, main_horizon_end)

    if not main_ticks:
        return None

    pnl, _reason = simulate_main(main_entry, dir_sign, main_ticks, fear_ideal)
    return pnl


def run_variant(rows, probe_confirm, fear_ideal):
    confirms = 0
    sim_total = 0.0
    wins = 0
    losses = 0
    win_sum = 0.0
    loss_sum = 0.0
    for r in rows:
        pnl = replay_probe(r, probe_confirm, fear_ideal)
        if pnl is None:
            continue
        confirms += 1
        sim_total += pnl
        if pnl > 0:
            wins += 1; win_sum += pnl
        else:
            losses += 1; loss_sum += pnl
    return {
        "probeConfirm": probe_confirm,
        "fearIdeal": fear_ideal,
        "confirms": confirms,
        "sim_pnl": round(sim_total, 2),
        "wr": round(wins/max(confirms,1)*100, 1),
        "avg_win": round(win_sum/max(wins,1), 2),
        "avg_loss": round(loss_sum/max(losses,1), 2),
    }


def main():
    if not SHADOW_CSV.exists():
        print("no probe_shadow_results.csv yet")
        return
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"loaded {len(rows)} probes from probe_shadow_results.csv")

    grid = []
    for fi in [10, 15, 20, 25, 35, 50, 70]:
        for pc in [0.40, 0.45, 0.58]:
            grid.append((pc, fi))

    print(f"running {len(grid)} variants with PROPER tick-replay...")
    print()
    results = []
    for pc, fi in grid:
        r = run_variant(rows, pc, fi)
        results.append(r)
        print(f"  pc=${pc:.2f} fi=${fi:<3} -> confirms={r['confirms']:<3} sim=${r['sim_pnl']:+8.2f} wr={r['wr']:>5.1f}% avg+=${r['avg_win']:>6.2f} avg-=${r['avg_loss']:>7.2f}")

    print()
    print("=" * 92)
    print("  RANKED BY SIM P&L")
    print("=" * 92)
    print(f"  {'rank':<5}{'probeConfirm':<13}{'fearIdeal':<11}{'confirms':<10}{'sim P&L':<12}{'WR%':<7}{'avg+':<9}{'avg-':<9}")
    print("  " + "-" * 88)
    for idx, r in enumerate(sorted(results, key=lambda x: -x["sim_pnl"])):
        marker = '*' if idx == 0 else ' '
        print(f"  {marker} {idx+1:<3}${r['probeConfirm']:<11.2f}${r['fearIdeal']:<9}{r['confirms']:<10}${r['sim_pnl']:+8.2f}    {r['wr']:>5.1f}%  ${r['avg_win']:>6.2f}  ${r['avg_loss']:>7.2f}")


if __name__ == "__main__":
    main()
