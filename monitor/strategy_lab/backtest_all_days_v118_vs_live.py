"""backtest_all_days_v118_vs_live.py - run v1.18 MEDIUM config on ALL available
tick days, compare to real LIVE fills from turtle_fills.csv.

Per Zee's request 2026-06-03:
  'backtest ki report muje dikhaen jiss mein har din ka profit dikhaya hoa ho..
   phir real tick data pe current EA se comparison show kia ho'

Output:
  - Day-by-day table: BT trades, BT P&L, LIVE trades, LIVE P&L, diff
  - Cumulative equity for BT (so it matches the 23-day +$128k claim shape)
  - Summary: days traded, positive days, negative days, etc.
"""
import sys, csv, glob
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))

# Reuse exact v1.18 simulation from backtest_today_medium.py
from backtest_today_medium import (
    load_ticks, build_m5, run, COMMON, FILLS_CSV,
)


def load_live_for(day_str):
    """day_str like '2026.06.02' (CSV prefix)."""
    out = []
    if not FILLS_CSV.exists(): return out
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or not r[0].startswith(day_str): continue
            try:
                pnl = float(r[7])
                vol = r[5]
                out.append({"pnl": pnl, "vol": vol})
            except: continue
    return out


def main():
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"Found {len(tick_files)} tick days. Running v1.18 MEDIUM backtest on each...\n",
          flush=True)
    print(f"{'date':<12}{'BT n':>6}{'BT WR%':>8}{'BT P&L':>10}  | "
          f"{'LIVE n':>7}{'LIVE WR%':>10}{'LIVE P&L':>10}  | {'cumBT':>10}{'cumLIVE':>10}", flush=True)
    print("-" * 95, flush=True)

    cum_bt = 0.0; cum_live = 0.0
    bt_days_pos = bt_days_neg = bt_days_flat = 0
    live_days_pos = live_days_neg = live_days_flat = 0
    rows = []
    for path in tick_files:
        path = Path(path)
        day_str = path.stem.replace("shano_ticks_", "")              # e.g. 2026-06-02
        live_prefix = day_str.replace("-", ".")                      # e.g. 2026.06.02
        ticks = load_ticks(path)
        if len(ticks) < 100:
            print(f"{day_str:<12}{'(no ticks)':<60}", flush=True); continue
        m5 = build_m5(ticks)
        fills, bt_pnl, _ = run(ticks, m5)
        bt_n = len(fills)
        bt_w = sum(1 for f in fills if f["pnl_usd"] > 0)
        bt_l = sum(1 for f in fills if f["pnl_usd"] < 0)
        bt_wr = 100 * bt_w / max(1, bt_w + bt_l) if (bt_w + bt_l) else 0
        if bt_pnl > 0: bt_days_pos += 1
        elif bt_pnl < 0: bt_days_neg += 1
        else: bt_days_flat += 1
        cum_bt += bt_pnl

        live = load_live_for(live_prefix)
        live_n = len(live)
        live_pnl = sum(x["pnl"] for x in live)
        live_w = sum(1 for x in live if x["pnl"] > 0)
        live_l = sum(1 for x in live if x["pnl"] < 0)
        live_wr = 100 * live_w / max(1, live_w + live_l) if (live_w + live_l) else 0
        if live_pnl > 0: live_days_pos += 1
        elif live_pnl < 0: live_days_neg += 1
        else: live_days_flat += 1
        cum_live += live_pnl

        rows.append({
            "day": day_str, "bt_n": bt_n, "bt_wr": bt_wr, "bt_pnl": bt_pnl,
            "live_n": live_n, "live_wr": live_wr, "live_pnl": live_pnl,
        })
        bt_wr_s  = f"{bt_wr:5.1f}%"  if bt_n else "  -- "
        live_wr_s = f"{live_wr:5.1f}%" if live_n else "  -- "
        print(f"{day_str:<12}{bt_n:>6}{bt_wr_s:>8}{bt_pnl:>+10.2f}  | "
              f"{live_n:>7}{live_wr_s:>10}{live_pnl:>+10.2f}  | {cum_bt:>+10.2f}{cum_live:>+10.2f}",
              flush=True)

    print("\n" + "=" * 95)
    print(f"SUMMARY  -  v1.18 MEDIUM config (0.05 lots, GMT+0 sessions UTC 01:30-02:30 + 16:45-19:45)")
    print(f"           rng60_min=0.8, cooldown=30s, max_loss=$10, skim=$10, trail $5/$15")
    print("=" * 95)
    print(f"  Days with data:        {len(rows)}")
    print(f"  BACKTEST  total P&L:   ${cum_bt:+.2f}")
    print(f"            pos/neg/flat days: {bt_days_pos} / {bt_days_neg} / {bt_days_flat}")
    print(f"            total trades: {sum(r['bt_n'] for r in rows)}")
    print(f"            avg trades/day: {sum(r['bt_n'] for r in rows) / max(1, len(rows)):.1f}")
    print(f"  LIVE      total P&L:   ${cum_live:+.2f}")
    print(f"            pos/neg/flat days: {live_days_pos} / {live_days_neg} / {live_days_flat}")
    print(f"            total trades: {sum(r['live_n'] for r in rows)}")
    print(f"  DIFF (LIVE - BT):      ${cum_live - cum_bt:+.2f}")

    # Scale BT to 0.10 lots for comparison with the +$128k MEDIUM claim
    cum_bt_010 = cum_bt * 2  # 0.05 → 0.10 lots = 2× scale
    print(f"\n  At 0.10 lots scale, BT total = ${cum_bt_010:+.2f}")
    print(f"  (Original overnight Medium claim was +$128k at 0.10 lots for the validation set)")


if __name__ == "__main__":
    main()
