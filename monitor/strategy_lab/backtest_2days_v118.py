"""backtest_2days_v118.py - run v1.18 (live) config on June 2 + June 3 ticks.

Imports the v1.18-equivalent config & sim functions from backtest_today_medium.py
and runs them on two days back-to-back. Reports BACKTEST vs LIVE side-by-side.

v1.18 config = MEDIUM variant, GMT+0 sessions (UTC 01:30-02:30 + 16:45-19:45).
"""
import sys, csv
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))

# Import everything from the today-only script
from backtest_today_medium import (
    load_ticks, build_m5, run, COMMON, FILLS_CSV,
    LOTS, USD_PER_PRICE_LIVE, COST,
)

DAYS = ["2026-06-02", "2026-06-03"]


def load_live_for(day_str):
    """day_str like '2026.06.02' (broker-time CSV prefix)."""
    out = []
    if not FILLS_CSV.exists(): return out
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or not r[0].startswith(day_str): continue
            try:
                pnl = float(r[7])
                out.append({"t": r[0][11:], "side": r[4], "vol": r[5], "pnl": pnl})
            except: continue
    return out


def main():
    rows = []
    for day in DAYS:
        tick_path = COMMON / f"shano_ticks_{day}.csv"
        if not tick_path.exists():
            rows.append({"day": day, "err": f"no tick file ({tick_path.name})"})
            continue
        print(f"\n{'='*78}\nDay {day}  ({tick_path.name})\n{'='*78}", flush=True)
        ticks = load_ticks(tick_path)
        m5 = build_m5(ticks)
        print(f"  {len(ticks):,} ticks, {len(m5)} M5 bars")
        fills, daily_pnl, rejects = run(ticks, m5)
        n = len(fills)
        wins = sum(1 for f in fills if f["pnl_usd"] > 0)
        losses = sum(1 for f in fills if f["pnl_usd"] < 0)
        wr = 100 * wins / max(1, wins + losses) if (wins + losses) else 0

        # Live fills for same day
        broker_prefix = day.replace("-", ".")
        live = load_live_for(broker_prefix)
        live_pnl = sum(x["pnl"] for x in live)
        live_w = sum(1 for x in live if x["pnl"] > 0)
        live_l = sum(1 for x in live if x["pnl"] < 0)
        live_wr = 100 * live_w / max(1, live_w + live_l)

        print(f"\nBACKTEST (v1.18 medium, UTC sessions 01:30-02:30 + 16:45-19:45):")
        print(f"  Trades: {n}    Wins: {wins}    Losses: {losses}    WR: {wr:.1f}%")
        print(f"  Daily P&L: ${daily_pnl:+.2f}")
        if fills:
            for f in fills[:20]:
                marker = "[OK]" if f["pnl_usd"] > 0 else "[X]"
                print(f"    {f['t']:<10}{f['side']:<6}{f['entry']:>9}{f['pnl_usd']:>+8.2f}  {marker} {f['reason']}")

        print(f"\nLIVE (actual broker fills that day):")
        print(f"  Trades: {len(live)}  Wins: {live_w}  Losses: {live_l}  WR: {live_wr:.1f}%")
        print(f"  Daily P&L: ${live_pnl:+.2f}")
        if live:
            for x in live:
                marker = "[OK]" if x["pnl"] > 0 else "[X]"
                print(f"    {x['t']:<10}{x['side']:<13}vol={x['vol']:<5}{x['pnl']:>+8.2f}  {marker}")

        rows.append({"day": day, "bt_n": n, "bt_wr": wr, "bt_pnl": daily_pnl,
                     "live_n": len(live), "live_wr": live_wr, "live_pnl": live_pnl})

    print(f"\n{'='*78}\nSUMMARY - v1.18 BACKTEST vs LIVE (BOTH days)\n{'='*78}")
    print(f"{'Day':<12}{'BT trades':>11}{'BT WR%':>8}{'BT P&L':>10}  |  {'LIVE trades':>13}{'LIVE WR%':>10}{'LIVE P&L':>12}")
    print("-" * 78)
    for r in rows:
        if "err" in r:
            print(f"{r['day']:<12}{r['err']}"); continue
        print(f"{r['day']:<12}{r['bt_n']:>11}{r['bt_wr']:>7.1f}%{r['bt_pnl']:>+10.2f}  |  "
              f"{r['live_n']:>13}{r['live_wr']:>9.1f}%{r['live_pnl']:>+12.2f}")


if __name__ == "__main__":
    main()
