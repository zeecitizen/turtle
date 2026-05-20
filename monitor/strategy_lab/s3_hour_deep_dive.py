"""s3_hour_deep_dive.py — verify the surprising 'Asian session edge' finding.

Investigates:
  1. Broker timezone (which hour in GMT does broker '05:00' actually mean?)
  2. Per-hour breakdown — full 24-hour histogram, not just session buckets
  3. Per-day breakdown of London-NY losses — is one bad day driving the negative?
  4. Day-of-week effect
  5. Hourly heatmap: hour × day-of-week → P&L
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, replay_ticks, stats, group_bars_by_day, find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror

CONTRACT = 100.0


def main():
    print("Loading...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # ─── 1. Broker timezone check ───
    print("\n" + "="*78)
    print("  STEP 1 — broker timezone diagnostic")
    print("="*78)
    print(f"  First M1 bar in dataset: {bars_all[0]['time']}")
    print(f"  Last M1 bar:             {bars_all[-1]['time']}")
    # Detect timezone heuristic: when is XAU most active?
    # XAU is least active during the daily rollover gap (~21:00-23:00 GMT typically)
    # Sum tick volume by hour across all days
    vol_by_hour = defaultdict(int)
    count_by_hour = defaultdict(int)
    for b in bars_all:
        vol_by_hour[b["time"].hour] += b["vol"]
        count_by_hour[b["time"].hour] += 1
    print(f"\n  Tick volume by HOUR (broker time) — XAU lowest vol = rollover ≈ 21:00 GMT")
    print(f"  {'hr':>4} {'avg_vol':>10} {'bars':>7}")
    for h in range(24):
        avg_v = vol_by_hour[h] / max(1, count_by_hour[h])
        bar = "█" * int(avg_v / 30)
        print(f"  {h:>4} {avg_v:>10.0f} {count_by_hour[h]:>7}  {bar}")
    # Find lowest-volume hour → infer GMT offset
    min_hour = min(range(24), key=lambda h: vol_by_hour[h]/max(1, count_by_hour[h]))
    print(f"\n  Lowest-volume hour: {min_hour} (broker time)")
    print(f"  If that's the XAU rollover (typically 21:00 GMT), broker offset ≈ GMT+{min_hour - 21 if min_hour >= 21 else min_hour + 3}")

    # ─── Pre-cache per-day signals ───
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        m5 = aggregate_to_tf(db, 5)
        sigs = s3_ea_mirror(m5, sl_buf=0.10, h1_fvgs=h1_fvgs, require_fvg=False)
        done = replay_ticks(ticks, sigs, 0.10, CONTRACT)
        # tag each trade with its fire_time hour and day
        for i, t in enumerate(done):
            t["fire_hour"] = sigs[i]["fire_time"].hour if i < len(sigs) else None
            t["fire_date"] = sigs[i]["fire_time"].date() if i < len(sigs) else None
            t["fire_dow"]  = sigs[i]["fire_time"].weekday() if i < len(sigs) else None  # 0=Mon
        cache[day] = {"trades": done}

    # ─── 2. Per-hour breakdown ───
    print("\n" + "="*78)
    print("  STEP 2 — per-hour P&L breakdown (all 12 days)")
    print("="*78)
    by_hour = defaultdict(list)
    for d, c in cache.items():
        for t in c["trades"]:
            if t["fire_hour"] is not None:
                by_hour[t["fire_hour"]].append(t)
    print(f"  {'hr':>4} {'n':>3} {'wins':>5} {'losses':>7} {'WR':>6} {'avgW':>7} {'avgL':>7} {'total':>10}  bar")
    for h in range(24):
        ts = by_hour.get(h, [])
        if not ts:
            print(f"  {h:>4}   0       —       —      —       —       —          —")
            continue
        wins = [x['pnl'] for x in ts if x['pnl']>0]
        losses = [x['pnl'] for x in ts if x['pnl']<0]
        n_w = len(wins); n_l = len(losses)
        wr = n_w/(n_w+n_l) if (n_w+n_l) else 0
        avg_w = sum(wins)/n_w if n_w else 0
        avg_l = -sum(losses)/n_l if n_l else 0
        total = sum(x['pnl'] for x in ts)
        bar = "▮" * max(0, int(total/30)) if total > 0 else "▯" * max(0, int(-total/30))
        print(f"  {h:>4} {len(ts):>3} {n_w:>5} {n_l:>7}  {wr:>5.2f} ${avg_w:>5.1f} ${avg_l:>5.1f} ${total:>+8.1f}  {bar}")

    # ─── 3. London-NY (08-21 broker) per-day breakdown ───
    print("\n" + "="*78)
    print("  STEP 3 — London-NY hours (08-21 broker) per-day P&L")
    print("="*78)
    print(f"  {'day':<12} {'n':>4} {'wins':>5} {'losses':>7} {'total':>10}")
    by_day = defaultdict(list)
    for day, c in cache.items():
        for t in c["trades"]:
            if 8 <= t["fire_hour"] < 21:
                by_day[day].append(t)
    total_ln = 0
    for day in sorted(by_day.keys()):
        ts = by_day[day]
        w = sum(1 for x in ts if x['pnl']>0)
        l = sum(1 for x in ts if x['pnl']<0)
        tt = sum(x['pnl'] for x in ts)
        total_ln += tt
        mark = "🟢" if tt > 0 else "🔴" if tt < 0 else "  "
        print(f"  {day:<12} {len(ts):>4} {w:>5} {l:>7}  ${tt:>+8.1f}  {mark}")
    print(f"  {'TOTAL':<12}                ${total_ln:>+8.1f}")

    # ─── 4. Day-of-week breakdown ───
    print("\n" + "="*78)
    print("  STEP 4 — day-of-week breakdown")
    print("="*78)
    DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    by_dow = defaultdict(list)
    for d, c in cache.items():
        for t in c["trades"]:
            if t["fire_dow"] is not None: by_dow[t["fire_dow"]].append(t)
    for dw in range(7):
        ts = by_dow.get(dw, [])
        if not ts:
            print(f"  {DOW[dw]}    0     —")
            continue
        w = sum(1 for x in ts if x['pnl']>0)
        l = sum(1 for x in ts if x['pnl']<0)
        wr = w/(w+l) if (w+l) else 0
        tt = sum(x['pnl'] for x in ts)
        print(f"  {DOW[dw]}  n={len(ts):>3} W={w:>2} L={l:>2}  WR={wr:.2f}  TOTAL=${tt:>+8.1f}")


if __name__ == "__main__":
    main()
