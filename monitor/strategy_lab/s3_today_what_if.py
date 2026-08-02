"""s3_today_what_if.py — answer Zee's question: what would S3 have fired
today if the broker-hour filter (13/15/16) were OFF?

Reads rev_eng_m1_recent.csv (fresh dump from ExportRecentBars), runs S3
ea_mirror over today's M1 bars with require_fvg=False and reports every
signal, marking which ones would have been blocked by the hour filter.
"""
import sys, csv
from pathlib import Path
from datetime import datetime, date
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
SKIP_HOURS = {13, 15, 16}


def load_m1(path):
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
    return bars


def main():
    src = COMMON / "rev_eng_m1_recent.csv"
    if not src.exists():
        print("[ERR] rev_eng_m1_recent.csv missing. Drag ExportRecentBars script onto any MT5 chart first.")
        return
    bars = load_m1(src)
    if not bars:
        print("[ERR] no bars loaded")
        return
    today = date(2026, 5, 18)
    today_bars = [b for b in bars if b["time"].date() == today]
    print(f"Loaded {len(bars)} M1 bars total, {len(today_bars)} on {today}")
    if not today_bars:
        print("[ERR] no 2026-05-18 bars in file")
        return
    print(f"  Today range: {today_bars[0]['time']} -> {today_bars[-1]['time']}")

    # H1 FVGs from all bars (need history for fvg detection)
    h1 = aggregate_to_tf(bars, 60)
    h1_fvgs = find_h1_fvgs(h1)
    # M5 from today only (consistent with how the live EA evaluates)
    m5 = aggregate_to_tf(today_bars, 5)
    print(f"  M5 today: {len(m5)} bars\n")

    # Run mirror with SL=$2 (current production), require_fvg=False
    sigs = s3_ea_mirror(m5, sl_buf=2.0, h1_fvgs=h1_fvgs, require_fvg=False)
    print(f"  S3 raw signals today (NO filter): {len(sigs)}\n")

    print(f"  {'#':>2} {'fire_time':<20} {'sl':>8} {'tp':>8} "
          f"{'risk':>6} {'rew':>6} {'hr':>3} {'filter':>10}")
    blocked = 0
    allowed = 0
    for i, s in enumerate(sigs, 1):
        hr = s["fire_time"].hour
        status = "BLOCKED" if hr in SKIP_HOURS else "allowed"
        if hr in SKIP_HOURS: blocked += 1
        else: allowed += 1
        # entry approximated as halfway between sl and tp doesn't work; use ref-red close + sl_buf is unknown here.
        # Just report sl/tp/distance. (live entry would be ~bo.close at fire_time.)
        risk = "  ?  "
        rew  = "  ?  "
        print(f"  {i:>2} {str(s['fire_time']):<20} "
              f"{s['sl']:>8.2f} {s['tp']:>8.2f} "
              f"{risk:>6} {rew:>6} {hr:>3} {status:>10}")
    print(f"\n  Total: {len(sigs)} signals  |  {allowed} allowed by filter  |  {blocked} blocked")

    # Simulate exits using actual M1 tick highs/lows after each signal.
    # For each sig, walk forward M1 bars after fire_time and check tp/sl hits.
    print(f"\n  Per-signal hypothetical outcome (M1 high/low tracking):")
    print(f"  {'#':>2} {'fire':<20} {'sl':>8} {'tp':>8} {'outcome':<8} "
          f"{'exit_t':<20} {'P&L@0.02':>10}  {'filter':>10}")
    # build M1 lookup
    m1_by_t = {b["time"]: b for b in today_bars}
    m1_sorted = sorted(today_bars, key=lambda b: b["time"])
    block_pnl = 0.0
    allow_pnl = 0.0
    for i, s in enumerate(sigs, 1):
        hr = s["fire_time"].hour
        status = "BLOCKED" if hr in SKIP_HOURS else "allowed"
        # find first M1 bar AT or after fire_time
        future = [b for b in m1_sorted if b["time"] >= s["fire_time"]]
        outcome = "open"
        exit_t = None
        exit_px = None
        for b in future:
            if b["low"] <= s["sl"]:
                outcome, exit_t, exit_px = "SL", b["time"], s["sl"]
                break
            if b["high"] >= s["tp"]:
                outcome, exit_t, exit_px = "TP", b["time"], s["tp"]
                break
        # P&L at 0.02 lots: 1 point = $2
        # Entry approximated as bo.close. We need bo close for this sig — derive from m5
        # Get the bo bar: bo.time = fire_time - 5min
        bo_t = s["fire_time"].replace(second=0, microsecond=0)
        # find m5 bar with that time
        bo_close = None
        for mb in m5:
            if mb["time"] == s["fire_time"] - (s["fire_time"] - s["fire_time"]):
                pass
        # simpler — find m5 bar where time + 5min == fire_time
        from datetime import timedelta
        target_bo = s["fire_time"] - timedelta(minutes=5)
        for mb in m5:
            if mb["time"] == target_bo:
                bo_close = mb["close"]
                break
        if bo_close is None or exit_px is None:
            pnl_str = "    n/a"
        else:
            pnl = (exit_px - bo_close) * 2.0   # buy: gain if price up
            pnl_str = f"${pnl:>+7.2f}"
            if status == "BLOCKED": block_pnl += pnl
            else:                   allow_pnl += pnl
        exit_str = str(exit_t) if exit_t else "still open"
        print(f"  {i:>2} {str(s['fire_time']):<20} "
              f"{s['sl']:>8.2f} {s['tp']:>8.2f} {outcome:<8} "
              f"{exit_str:<20} {pnl_str:>10}  {status:>10}")

    print(f"\n  SUMMARY (0.02 lots, P&L based on intended SL/TP, ignoring slip):")
    print(f"    Allowed-by-filter trades P&L: ${allow_pnl:+.2f}")
    print(f"    BLOCKED trades P&L:           ${block_pnl:+.2f}")
    print(f"    Net cost/benefit of filter:   ${-block_pnl:+.2f}")
    print(f"    (negative means filter SAVED us money; positive means filter cost us)")


if __name__ == "__main__":
    main()
