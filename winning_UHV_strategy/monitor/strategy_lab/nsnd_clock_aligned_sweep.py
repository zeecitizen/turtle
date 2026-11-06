"""nsnd_clock_aligned_sweep.py — Find an NSND configuration that's
profitable using CLOCK-ALIGNED multi-TF aggregation (matches MQL5 EA's
native iHigh/iLow on PERIOD_M15/H1).

Background: original NSND backtest used stride-based aggregation in
_aggregate_bars (chunks bars[0:k], bars[k:2k]...). MQL5 EA uses MT5's
clock-aligned bars (00:00-00:15, 00:15-00:30, etc.). These give different
FVG behavior, and the +$935 backtest does NOT survive the switch.

This sweep tries to find any config that works with clock-aligned bars.
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf as agg_clock, replay_ticks, stats, group_bars_by_day
from ea_mirror_validate import nsnd_ea_mirror

CONTRACT = 100.0


def main():
    print("NSND sweep with CLOCK-ALIGNED M15/H1 aggregation (matches MQL5 EA):\n")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # Sweep configurations
    configs = []
    # Without HH/HL
    for trend in [0.5, 1.0, 2.0]:
        for vol_min in [2, 3]:
            for narrow in [0.8, 1.0, 1.2]:
                configs.append(dict(use_hhhl=False, trend_th=trend,
                                    vol_min=vol_min, narrow_frac=narrow,
                                    hhhl_lb=180, hhhl_need=2, hhhl_N=3))
    # With HH/HL (default)
    for trend in [0.5, 1.0]:
        for vol_min in [2]:
            for narrow in [1.0]:
                for hhhl_need in [2, 3]:
                    for hhhl_lb in [90, 180]:
                        configs.append(dict(use_hhhl=True, trend_th=trend,
                                            vol_min=vol_min, narrow_frac=narrow,
                                            hhhl_lb=hhhl_lb, hhhl_need=hhhl_need, hhhl_N=3))

    print(f"{'hhhl':<5} {'trend':>6} {'vmin':>5} {'narr':>5} {'hhhlLB':>7} {'need':>5}  {'n':>4} {'WR':>5} {'TOTAL':>10}  {'@0.40':>10}")
    best = None
    for cfg in configs:
        total = 0; total_n = 0; all_t = []
        for tf in tick_files:
            day = Path(tf).stem.split("_")[-1]
            if day not in days_bars: continue
            db = days_bars[day]
            if len(db) < 200: continue
            m15 = agg_clock(db, 15)
            h1  = agg_clock(db, 60)
            try:
                sigs = nsnd_ea_mirror(
                    db, m15, h1, lots=0.10, tp_usd=12.0,
                    use_hhhl=cfg["use_hhhl"], hhhl_lb=cfg["hhhl_lb"],
                    hhhl_need=cfg["hhhl_need"], hhhl_N=cfg["hhhl_N"],
                    trend_th=cfg["trend_th"], vol_min=cfg["vol_min"],
                    narrow_frac=cfg["narrow_frac"])
            except Exception as e:
                print(f"  ERR: {e}"); continue
            if not sigs: continue
            ticks = load_ticks(tf)
            if len(ticks) < 100: continue
            done = replay_ticks(ticks, sigs, 0.10, CONTRACT)
            all_t.extend(done)
        r = stats(all_t)
        if r is None: continue
        mark = ' ✅' if r['total'] > 0 else ' ❌'
        proj = r['total'] * 4
        print(f"  {str(cfg['use_hhhl']):<5} {cfg['trend_th']:>6.1f} {cfg['vol_min']:>5} {cfg['narrow_frac']:>5.1f} "
              f"{cfg['hhhl_lb']:>7} {cfg['hhhl_need']:>5}  "
              f"{r['n']:>4} {r['pwin']:>5.2f}  ${r['total']:>+8.1f}  ${proj:>+8.1f}{mark}")
        if r['total'] > 0 and (best is None or r['total'] > best[0]):
            best = (r['total'], cfg, r)

    print()
    if best:
        print(f"BEST PROFITABLE NSND (clock-aligned): {best[1]}")
        print(f"  n={best[2]['n']} WR={best[2]['pwin']:.2f} TOTAL=${best[0]:+.1f}  proj@0.40=${best[0]*4:+.1f}")
    else:
        print("NO PROFITABLE NSND CONFIG FOUND with clock-aligned aggregation.")
        print("RECOMMENDATION: do NOT deploy NsndTrader.mq5 — strategy depends on a")
        print("stride-aggregation artifact that doesn't exist in MT5's native bars.")


if __name__ == "__main__":
    main()
