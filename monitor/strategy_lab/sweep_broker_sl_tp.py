"""sweep_broker_sl_tp.py - find broker SL/TP widths that make EA's internal
exit logic come back to life.

Currently at 0.05 lots, broker SL/TP ($25/$50) are TIGHTER than the EA's
internal SKIM ($50) and MAX_LOSS ($50). So every exit fires at broker parachute.
EA's TRAIL_ARM/TRAIL_GIVEBACK never trigger.

This script re-runs the MQL5-mirror across a grid of (broker_sl_usd, broker_tp_usd)
values to find the combo with the best 27-day NET P&L. The grid:

  broker_sl_usd: 25, 50, 75, 100  (tighten or loosen the loss parachute)
  broker_tp_usd: 50, 75, 100, 150 (let winners run further or cap them)

Per-config 27-day total reported. Best config = candidate for live deployment.
"""
import sys, glob, importlib.util
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

sys.path.insert(0, str(Path(__file__).parent))

# Dynamically import the mirror; we'll mutate its module globals per sweep
spec = importlib.util.spec_from_file_location(
    "mirror", str(Path(__file__).parent / "dry_run_mql5_mirror.py"))
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)

COMMON = mirror.COMMON


def run_sweep(broker_sl, broker_tp):
    """Patch mirror module globals and run on all days."""
    mirror.BROKER_SL_USD = broker_sl
    mirror.BROKER_TP_USD = broker_tp
    mirror.BROKER_SL_PRICE = mirror.usd_to_price_dist(broker_sl)
    mirror.BROKER_TP_PRICE = mirror.usd_to_price_dist(broker_tp)

    total_pnl_usd = 0.0
    total_n = 0
    total_w = 0
    total_l = 0
    days_pos = 0
    days_neg = 0
    reasons_agg = {}
    for path in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        ticks = mirror.load_ticks(path)
        if len(ticks) < 1000: continue
        fills = mirror.run_day_mql_mirror(ticks)
        n = len(fills)
        if n == 0: continue
        day_pnl = sum(f["exit_pnl_usd"] for f in fills)
        w = sum(1 for f in fills if f["exit_pnl_price"] > 0)
        l = sum(1 for f in fills if f["exit_pnl_price"] < 0)
        total_n += n; total_w += w; total_l += l
        total_pnl_usd += day_pnl
        if day_pnl > 0: days_pos += 1
        elif day_pnl < 0: days_neg += 1
        for f in fills:
            reasons_agg[f["reason"]] = reasons_agg.get(f["reason"], 0) + 1
    wr = 100 * total_w / max(1, total_w + total_l) if (total_w + total_l) else 0
    return {
        "broker_sl": broker_sl, "broker_tp": broker_tp,
        "n": total_n, "wr": wr, "pnl_usd": total_pnl_usd,
        "days_pos": days_pos, "days_neg": days_neg,
        "reasons": reasons_agg,
    }


def main():
    print("Sweep broker SL/TP grid on MQL5-mirror, 27 tick days, 0.05 lots")
    print("=" * 110)
    print(f"{'SL$':>6}{'TP$':>6}{'fills':>7}{'WR%':>6}{'27d_PnL$':>11}"
          f"{'days+':>7}{'days-':>7}{'$/day':>9}  reasons")
    print("-" * 110)
    SLs = [25, 50, 75, 100, 150, 200]
    TPs = [50, 75, 100, 150, 200]
    results = []
    for sl in SLs:
        for tp in TPs:
            if tp <= sl: continue   # need TP > SL for positive expectancy
            r = run_sweep(sl, tp)
            results.append(r)
            avg = r['pnl_usd'] / 27
            reasons_str = " ".join(f"{k}={v}" for k, v in sorted(r['reasons'].items()))
            print(f"{sl:>6}{tp:>6}{r['n']:>7}{r['wr']:>5.1f}%{r['pnl_usd']:>+11.2f}"
                  f"{r['days_pos']:>7}{r['days_neg']:>7}{avg:>+8.2f}  {reasons_str}")
    print("-" * 110)
    # Top 3 by PnL
    results.sort(key=lambda r: r['pnl_usd'], reverse=True)
    print("\nTOP 3 by 27-day net P&L:")
    for r in results[:3]:
        avg = r['pnl_usd'] / 27
        print(f"  SL=${r['broker_sl']} TP=${r['broker_tp']}  "
              f"→ ${r['pnl_usd']:+,.2f}/27d  (avg ${avg:+.2f}/day)  "
              f"WR={r['wr']:.1f}%  {r['days_pos']}/{r['days_pos']+r['days_neg']} winning days")


if __name__ == "__main__":
    main()
