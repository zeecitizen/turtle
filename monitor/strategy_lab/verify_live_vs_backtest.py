"""verify_live_vs_backtest.py — answer Zee's question precisely:
   "is our backtest matching reality?"

Steps:
  1. Re-run S3 mirror on the SAME 12d real-tick dataset with CURRENT
     production config (SL=$2.00, hour filter OFF). Report WR / EV.
  2. Re-run S1 (UHV) mirror on same 12d. Report WR.
  3. Re-run NSND mirror on same 12d. Report WR.
  4. Compare to live yesterday/last-night.

If backtest WR is way higher than live WR, two possible causes:
  (a) Real ticks have changed character since May 14 (regime shift)
  (b) Live EA differs from mirror somewhere (translation bug)
"""
import csv, sys, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import s1_mirror, replay_ticks_both

CONTRACT = 100.0


def main():
    print("Loading 12d real-tick dataset (Apr 29 - May 14)...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"  {len(bars_all)} M1 bars across {len(days_bars)} days")
    print(f"  {len(tick_files)} tick files: {[Path(f).stem.split('_')[-1] for f in tick_files]}\n")

    # Cache per day
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "m15": aggregate_to_tf(db, 15),
                      "ticks": ticks, "bars": db}
    print(f"  {len(cache)} days cached for tick-replay\n")

    # ────────────────────────────────────────────────────────────────────
    # 1. S3 (CURRENT LIVE CONFIG: SL=$2.00, hour filter OFF, require_fvg=False)
    # ────────────────────────────────────────────────────────────────────
    print("="*84)
    print("  S3 Mirror — current live config (SL=$2.00, no hour filter, FVG OFF)")
    print("="*84)
    s3_all_trades = []
    s3_per_day = {}
    for day, c in cache.items():
        sigs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=h1_bull, require_fvg=False)
        if not sigs: continue
        done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
        # tag side+1 for replay
        for d in done:
            if "side" not in d: d["side"] = +1
        s3_all_trades.extend(done)
        s3_per_day[day] = done
    r = stats(s3_all_trades)
    if r:
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        print(f"  S3: n={r['n']} WR={r['pwin']*100:.1f}% W=${r['w_avg']:.1f} L=${r['l_avg']:.1f} "
              f"TOT=${r['total']:+.1f}/12d @ 0.10  EV/tr=${ev:+.2f}")
    print(f"  Per-day P&L (0.10 lots):")
    for day in sorted(s3_per_day):
        ts = s3_per_day[day]
        tt = sum(t["pnl"] for t in ts)
        w = sum(1 for t in ts if t["pnl"] > 0)
        l = sum(1 for t in ts if t["pnl"] < 0)
        mark = "GREEN" if tt > 0 else "RED"
        print(f"    {day}  n={len(ts):>3}  W={w:>2} L={l:>2}  ${tt:>+8.1f}  {mark}")

    # ────────────────────────────────────────────────────────────────────
    # 2. NSND mirror — current live config
    # ────────────────────────────────────────────────────────────────────
    print()
    print("="*84)
    print("  NSND Mirror — current live config (vol_min=3, trend=2.0, HHHL=false)")
    print("="*84)
    nsnd_all_trades = []
    nsnd_per_day = {}
    h1_clock = aggregate_to_tf(bars_all, 60)
    for day, c in cache.items():
        m15 = c["m15"]
        sigs = nsnd_ea_mirror(c["bars"], m15, h1_clock,
                              vol_min=3, trend_th=2.0,
                              use_hhhl=False)
        if not sigs: continue
        done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
        nsnd_all_trades.extend(done)
        nsnd_per_day[day] = done
    r = stats(nsnd_all_trades)
    if r:
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        print(f"  NSND: n={r['n']} WR={r['pwin']*100:.1f}% W=${r['w_avg']:.1f} L=${r['l_avg']:.1f} "
              f"TOT=${r['total']:+.1f}/12d @ 0.10  EV/tr=${ev:+.2f}")

    # ────────────────────────────────────────────────────────────────────
    # 3. S1 mirror — current live config (WF-validated)
    # ────────────────────────────────────────────────────────────────────
    print()
    print("="*84)
    print("  S1 Mirror — current live config (SL=$2.00, TP=$7.5, BUY+SELL, FVG req)")
    print("="*84)
    s1_all_trades = []
    s1_per_day = {}
    for day, c in cache.items():
        sigs = s1_mirror(c["m5"], h1_bull, h1_bear,
                         sl_buf=2.0, tp_points=7.5,
                         do_buy=True, do_sell=True,
                         require_fvg=True, require_sweep=True,
                         require_open_inside=True)
        if not sigs: continue
        done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
        s1_all_trades.extend(done)
        s1_per_day[day] = done
    r = stats(s1_all_trades)
    if r:
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        print(f"  S1: n={r['n']} WR={r['pwin']*100:.1f}% W=${r['w_avg']:.1f} L=${r['l_avg']:.1f} "
              f"TOT=${r['total']:+.1f}/12d @ 0.10  EV/tr=${ev:+.2f}")

    # ────────────────────────────────────────────────────────────────────
    # 4. Compare to live
    # ────────────────────────────────────────────────────────────────────
    print()
    print("="*84)
    print("  LIVE comparison — last 24h actual fills")
    print("="*84)
    fills_path = COMMON / "turtle_fills.csv"
    live_recent = []
    with open(fills_path) as f:
        # skip header if any, then iterate
        first = f.readline()
        # detect header
        if not first[0].isdigit():
            pass
        else:
            f.seek(0)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 11: continue
            ts = parts[0]
            if not ts.startswith("2026.05.18") and not ts.startswith("2026.05.19"):
                continue
            try: pnl = float(parts[10])
            except: continue
            live_recent.append({"ts": ts, "pnl": pnl, "dir": parts[3]})
    if live_recent:
        n = len(live_recent)
        wins = [t for t in live_recent if t["pnl"] > 0]
        losses = [t for t in live_recent if t["pnl"] < 0]
        total = sum(t["pnl"] for t in live_recent)
        wr = len(wins) / max(1, len(wins)+len(losses)) * 100
        print(f"  LIVE last 24h: n={n} W={len(wins)} L={len(losses)} WR={wr:.1f}% "
              f"TOT=${total:+.2f} @ 0.02 lots")
        print(f"  Extrapolated to 0.10 lots: TOT=${total*5:+.2f}")

    # ────────────────────────────────────────────────────────────────────
    # 5. Conclusion
    # ────────────────────────────────────────────────────────────────────
    print()
    print("="*84)
    print("  ANALYSIS")
    print("="*84)
    print("  Backtest dataset: Apr 29 - May 14 (12 days of REAL bid/ask ticks)")
    print("  Live trades happening: May 18-19 (5 days AFTER backtest data ends)")
    print()
    print("  If backtest WR > live WR by a lot, two causes:")
    print("    (a) XAU market regime shifted since May 14 (recent days choppy/trend reverse)")
    print("    (b) Live EA differs from Python mirror (translation bug)")
    print()
    print("  To distinguish: dump fresh M1 + ticks for May 15-19, re-run mirror")
    print("  on THAT data. If mirror also shows lower WR there → it's market regime,")
    print("  not a bug. If mirror still shows high WR → it's a live-vs-mirror bug.")


if __name__ == "__main__":
    main()
