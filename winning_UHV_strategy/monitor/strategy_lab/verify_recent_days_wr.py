"""verify_recent_days_wr.py — answer "is the strategy still working?" using
M1 bars from rev_eng_m1_recent.csv (May 11-18) to compare May 18 (live-bad day)
vs May 11-14 (backtest-good days). Uses M1 high/low for fill estimation
(less precise than tick replay, but enough to detect regime shift).
"""
import csv, sys
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror
from backtest_s1_uhv_breakout import s1_mirror

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
CONTRACT = 100.0
LOTS = 0.10


def load_m1_recent(path):
    bars = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except Exception:
                continue
            bars.append({
                "time": t,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close":float(row["close"]),
                "vol":  int(row["tick_volume"]),
            })
    return sorted(bars, key=lambda b: b["time"])


def simulate_exits_from_m1(m1_bars, sigs, lots, contract):
    """Replay exits using M1 high/low (no spread; intra-bar order ambiguous).
    Same SL/TP logic as tick replay but quantized to 1-min granularity.
    Pessimistic assumption: if a bar's range hits BOTH sl and tp, count as SL (worse for us)."""
    ppp = lots * contract
    done = []
    m1_sorted = m1_bars
    for s in sorted(sigs, key=lambda x: x["fire_time"]):
        # Find first M1 bar at or after fire_time
        future = [b for b in m1_sorted if b["time"] >= s["fire_time"]]
        if not future: continue
        entry = future[0]["open"]  # approximate fill = next M1 open
        sl, tp, side = s["sl"], s["tp"], s.get("side", +1)
        outcome = None
        exit_px = None
        exit_t = None
        for b in future[1:]:  # exits start one bar after entry
            if side == +1:
                hit_sl = b["low"]  <= sl
                hit_tp = b["high"] >= tp
            else:
                hit_sl = b["high"] >= sl
                hit_tp = b["low"]  <= tp
            if hit_sl:
                outcome, exit_px, exit_t = "SL", sl, b["time"]; break
            if hit_tp:
                outcome, exit_px, exit_t = "TP", tp, b["time"]; break
        if outcome is None:
            outcome, exit_px, exit_t = "open", future[-1]["close"], future[-1]["time"]
        if side == +1:
            pnl = (exit_px - entry) * ppp
        else:
            pnl = (entry - exit_px) * ppp
        done.append({"pnl": pnl, "outcome": outcome, "fire_time": s["fire_time"],
                     "side": side, "entry": entry, "exit_px": exit_px, "exit_t": exit_t})
    return done


def per_day_report(label, trades):
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["fire_time"].date().isoformat()].append(t)
    print(f"\n  {label} per-day breakdown:")
    print(f"    {'day':<12} {'n':>3} {'W':>3} {'L':>3} {'open':>5} {'WR':>5} {'P&L':>10}")
    for day in sorted(by_day):
        ts = by_day[day]
        w = sum(1 for t in ts if t["outcome"] == "TP")
        l = sum(1 for t in ts if t["outcome"] == "SL")
        o = sum(1 for t in ts if t["outcome"] == "open")
        wr = w / max(1, w + l) * 100
        tt = sum(t["pnl"] for t in ts)
        mark = "GREEN" if tt > 0 else ("RED  " if tt < 0 else "     ")
        print(f"    {day:<12} {len(ts):>3} {w:>3} {l:>3} {o:>5}  {wr:>4.0f}% ${tt:>+8.1f}  {mark}")


def main():
    p = COMMON / "rev_eng_m1_recent.csv"
    if not p.exists():
        print(f"[ERR] {p} not found. Need ExportRecentBars dump."); return
    bars = load_m1_recent(p)
    print(f"Loaded {len(bars)} M1 bars: {bars[0]['time']} -> {bars[-1]['time']}")

    days = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
    print(f"  {len(days)} days, {len(h1)} H1 bars, {len(h1_bull)} bull FVGs, {len(h1_bear)} bear FVGs\n")

    # ── S3: run mirror across whole range, partition by day ──
    print("="*84)
    print("  S3 mirror — current live config, M1-replay outcomes")
    print("="*84)
    all_s3_sigs = []
    for day_iso in sorted(days):
        day_bars = days[day_iso]
        if len(day_bars) < 30: continue
        m5 = aggregate_to_tf(day_bars, 5)
        sigs = s3_ea_mirror(m5, sl_buf=2.0, h1_fvgs=h1_bull, require_fvg=False)
        for s in sigs: s["side"] = +1
        all_s3_sigs.extend(sigs)
    s3_trades = simulate_exits_from_m1(bars, all_s3_sigs, LOTS, CONTRACT)
    per_day_report("S3", s3_trades)
    closed = [t for t in s3_trades if t["outcome"] != "open"]
    if closed:
        w = sum(1 for t in closed if t["outcome"] == "TP")
        l = sum(1 for t in closed if t["outcome"] == "SL")
        tot = sum(t["pnl"] for t in closed)
        print(f"\n  S3 TOTAL (closed only, {len(days)} days): "
              f"n={len(closed)} W={w} L={l} WR={w/(w+l)*100:.1f}% ${tot:+.1f} @ 0.10 lots")

    # ── S1 across same range ──
    print("\n" + "="*84)
    print("  S1 mirror — current live config (BUY+SELL, SL=$2, TP=$7.5, FVG req)")
    print("="*84)
    all_s1_sigs = []
    for day_iso in sorted(days):
        day_bars = days[day_iso]
        if len(day_bars) < 30: continue
        m5 = aggregate_to_tf(day_bars, 5)
        sigs = s1_mirror(m5, h1_bull, h1_bear,
                         sl_buf=2.0, tp_points=7.5,
                         do_buy=True, do_sell=True,
                         require_fvg=True, require_sweep=True,
                         require_open_inside=True)
        all_s1_sigs.extend(sigs)
    s1_trades = simulate_exits_from_m1(bars, all_s1_sigs, LOTS, CONTRACT)
    per_day_report("S1", s1_trades)
    closed = [t for t in s1_trades if t["outcome"] != "open"]
    if closed:
        w = sum(1 for t in closed if t["outcome"] == "TP")
        l = sum(1 for t in closed if t["outcome"] == "SL")
        tot = sum(t["pnl"] for t in closed)
        print(f"\n  S1 TOTAL (closed only, {len(days)} days): "
              f"n={len(closed)} W={w} L={l} WR={w/(w+l)*100:.1f}% ${tot:+.1f} @ 0.10 lots")

    # ── Comparison: pre-May15 (in backtest window) vs post-May15 (out-of-sample) ──
    print("\n" + "="*84)
    print("  REGIME COMPARISON")
    print("="*84)
    cutoff = date(2026, 5, 15)
    for ea_name, trades in [("S3", s3_trades), ("S1", s1_trades)]:
        old_t = [t for t in trades if t["outcome"] != "open" and t["fire_time"].date() < cutoff]
        new_t = [t for t in trades if t["outcome"] != "open" and t["fire_time"].date() >= cutoff]
        for label, ts in [("PRE-May15 (in backtest window)", old_t),
                          ("POST-May15 (OUT of backtest)  ", new_t)]:
            if not ts:
                print(f"  {ea_name} {label}: no trades"); continue
            w = sum(1 for t in ts if t["outcome"] == "TP")
            l = sum(1 for t in ts if t["outcome"] == "SL")
            tot = sum(t["pnl"] for t in ts)
            wr = w / max(1, w + l) * 100
            print(f"  {ea_name} {label}: n={len(ts):>3} W={w:>3} L={l:>3} "
                  f"WR={wr:>4.1f}% TOT=${tot:>+8.1f}")
        print()


if __name__ == "__main__":
    main()
