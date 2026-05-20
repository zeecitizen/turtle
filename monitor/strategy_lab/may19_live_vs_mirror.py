"""may19_live_vs_mirror.py — compare every live S3/NSND fire today against
what the Python mirror predicts on the SAME M1 bars. Goal: surface any
live-vs-mirror divergence (= bug or data drift).
"""
import csv, sys
from datetime import datetime, date, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import s1_mirror

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TODAY  = date(2026, 5, 19)


def load_m1(path):
    bars = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except Exception:
                continue
            bars.append({"time": t, "open": float(row["open"]),
                         "high": float(row["high"]), "low": float(row["low"]),
                         "close": float(row["close"]), "vol": int(row["tick_volume"])})
    return sorted(bars, key=lambda b: b["time"])


def load_decisions(path, ea_name):
    rows = []
    if not Path(path).exists(): return rows
    with open(path) as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 14: continue
            ts = parts[0]
            if not ts.startswith("2026.05.19"): continue
            try:
                t = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except Exception: continue
            rows.append({"fire_time": t, "side": parts[2],
                         "intended_entry": float(parts[10]) if parts[10] else 0,
                         "intended_sl": float(parts[11]) if parts[11] else 0,
                         "intended_tp": float(parts[12]) if parts[12] else 0,
                         "actual_fill": float(parts[13]) if parts[13] else 0,
                         "ticket": parts[14] if len(parts) > 14 else ""})
    return rows


def load_fills_today(path):
    rows = []
    with open(path) as f:
        next(f, None)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 11: continue
            ts = parts[0]
            if not ts.startswith("2026.05.19"): continue
            try: pnl = float(parts[10])
            except: continue
            rows.append({"close_t": ts, "ticket": parts[2], "dir": parts[3],
                         "close_px": float(parts[6]) if parts[6] else 0, "pnl": pnl,
                         "comment": parts[11] if len(parts) > 11 else ""})
    return rows


def main():
    bars = load_m1(COMMON / "rev_eng_m1_recent.csv")
    print(f"Loaded {len(bars)} M1 bars: {bars[0]['time']} -> {bars[-1]['time']}")

    today_bars = [b for b in bars if b["time"].date() == TODAY]
    print(f"  May 19 bars: {len(today_bars)}  ({today_bars[0]['time']} -> {today_bars[-1]['time']})\n")

    h1 = aggregate_to_tf(bars, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    # CRITICAL: feed full M1 history to mirror so M5 array has the 24-bar
    # trend lookback available even for early-morning fires. Using only
    # today's bars caused mirror to skip first 2.5h of the day.
    m5_full  = aggregate_to_tf(bars,        5)
    m15_full = aggregate_to_tf(bars,       15)
    # Use full arrays for detection; filter results to TODAY's signals after.
    m5  = m5_full
    m15 = m15_full

    # ── 1. Mirror predictions for May 19 ──
    print("="*92)
    print("  S3 MIRROR predictions on May 19 (current live config: SL=$2, FVG OFF, hour-filter OFF)")
    print("="*92)
    s3_sigs_all = s3_ea_mirror(m5, sl_buf=2.0, h1_fvgs=h1_bull, require_fvg=False)
    s3_sigs = [s for s in s3_sigs_all if s["fire_time"].date() == TODAY]
    print(f"  {'#':>2} {'fire_time':<20} {'side':<5} {'sl':>8} {'tp':>8}")
    for i, s in enumerate(s3_sigs, 1):
        print(f"  {i:>2} {str(s['fire_time']):<20} {'buy':<5} {s['sl']:>8.2f} {s['tp']:>8.2f}")

    # ── 2. Live S3 fires today ──
    print()
    print("="*92)
    print("  S3 LIVE fires today (from s3_decisions.csv)")
    print("="*92)
    s3_live = load_decisions(COMMON / "s3_decisions.csv", "S3")
    print(f"  {'#':>2} {'fire_time':<20} {'side':<5} {'entry':>8} {'sl':>8} {'tp':>8} ticket")
    for i, d in enumerate(s3_live, 1):
        print(f"  {i:>2} {str(d['fire_time']):<20} {d['side']:<5} "
              f"{d['intended_entry']:>8.2f} {d['intended_sl']:>8.2f} {d['intended_tp']:>8.2f}  {d['ticket']}")

    # ── 3. Diff: mirror minus live, live minus mirror ──
    print()
    print("="*92)
    print("  S3 DIFF")
    print("="*92)
    mirror_times = {s["fire_time"] for s in s3_sigs}
    live_times   = {d["fire_time"] for d in s3_live}
    only_mirror = mirror_times - live_times
    only_live   = live_times - mirror_times
    in_both     = mirror_times & live_times
    print(f"  Both fired (mirror=live):   {len(in_both):>3}")
    print(f"  Only mirror (live missed):  {len(only_mirror):>3} {sorted(only_mirror)}")
    print(f"  Only live (mirror missed):  {len(only_live):>3} {sorted(only_live)}")

    # ── 4. NSND mirror vs live ──
    print()
    print("="*92)
    print("  NSND MIRROR predictions on May 19")
    print("="*92)
    nsnd_sigs_all = nsnd_ea_mirror(bars, m15, h1,
                                    vol_min=3, trend_th=2.0, use_hhhl=False)
    nsnd_sigs = [s for s in nsnd_sigs_all if s["fire_time"].date() == TODAY]
    print(f"  {'#':>2} {'fire_time':<20} {'side':<5} {'sl':>8} {'tp':>8}")
    for i, s in enumerate(nsnd_sigs, 1):
        side = "buy" if s.get("side", +1) == +1 else "sell"
        print(f"  {i:>2} {str(s['fire_time']):<20} {side:<5} {s.get('sl',0):>8.2f} {s.get('tp',0):>8.2f}")

    print()
    print("="*92)
    print("  NSND LIVE fires today")
    print("="*92)
    nsnd_live = load_decisions(COMMON / "nsnd_decisions.csv", "NSND")
    print(f"  {'#':>2} {'fire_time':<20} {'side':<5} {'entry':>8} {'sl':>8} {'tp':>8} ticket")
    for i, d in enumerate(nsnd_live, 1):
        print(f"  {i:>2} {str(d['fire_time']):<20} {d['side']:<5} "
              f"{d['intended_entry']:>8.2f} {d['intended_sl']:>8.2f} {d['intended_tp']:>8.2f}  {d['ticket']}")

    print()
    print("="*92)
    print("  NSND DIFF")
    print("="*92)
    nm = {s["fire_time"] for s in nsnd_sigs}
    nl = {d["fire_time"] for d in nsnd_live}
    print(f"  Both fired:           {len(nm & nl):>3}")
    print(f"  Only mirror predicted: {len(nm - nl):>3} {sorted(nm - nl)}")
    print(f"  Only live fired:       {len(nl - nm):>3} {sorted(nl - nm)}")

    # ── 5. S1 mirror — should show whether S1 had setups but didn't fire ──
    print()
    print("="*92)
    print("  S1 MIRROR on May 19 (BUY+SELL, SL=$2, TP=$7.5, FVG req)")
    print("="*92)
    s1_sigs_all = s1_mirror(m5, h1_bull, h1_bear,
                            sl_buf=2.0, tp_points=7.5,
                            do_buy=True, do_sell=True,
                            require_fvg=True, require_sweep=True,
                            require_open_inside=True)
    s1_sigs = [s for s in s1_sigs_all if s["fire_time"].date() == TODAY]
    if not s1_sigs:
        print(f"  No S1 setups detected on May 19 — explains why s1_decisions is empty.")
    else:
        for i, s in enumerate(s1_sigs, 1):
            side = "buy" if s.get("side", +1) == +1 else "sell"
            print(f"  {i:>2} {str(s['fire_time']):<20} {side:<5} {s['sl']:>8.2f} {s['tp']:>8.2f}")

    # ── 6. Live fills today + P&L summary ──
    print()
    print("="*92)
    print("  LIVE FILLS TODAY (closed positions)")
    print("="*92)
    fills = load_fills_today(COMMON / "turtle_fills.csv")
    if fills:
        for f in fills:
            mark = "+" if f["pnl"] > 0 else "-"
            print(f"  {f['close_t']:<20} {f['dir']:<14} {f['close_px']:>8.2f}  "
                  f"{mark}${abs(f['pnl']):>6.2f}  {f['comment']}")
        total = sum(f["pnl"] for f in fills)
        wins = sum(1 for f in fills if f["pnl"] > 0)
        losses = sum(1 for f in fills if f["pnl"] < 0)
        print(f"\n  TOTAL: n={len(fills)} W={wins} L={losses} "
              f"WR={wins/max(1,wins+losses)*100:.1f}% ${total:+.2f} @ 0.02 lots")
    else:
        print("  no closed fills today")


if __name__ == "__main__":
    main()
