"""today_teacher_filter_check.py — for each S3 fire today, reconstruct the
wicking-green (bo) M5 candle from M1 bars and check whether the teacher
filters (upper-wick rejection <=0.35, FVG-required) would have blocked it.
Cross-reference vs win/loss outcome to see if the filters help on losers.
"""
import csv, sys
from datetime import datetime, timedelta, date
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, find_h1_fvgs, fvg_tapped_at

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

# S3 fires today: fire_time -> (ticket, outcome, pnl)
S3_TODAY = [
    ("01:30", "52667463", "WIN",  +3.26),
    ("02:35", "52677385", "LOSS", -11.16),
    ("03:10", "52686459", "LOSS", -19.22),
    ("03:20", "52689872", "LOSS", -15.12),
    ("09:35", "52799627", "WIN",  +6.96),
    ("10:50", "52812253", "WIN",  +8.72),
    ("11:15", "52818288", "LOSS", -11.96),
    ("15:10", "52853324", "WIN",  +1.86),
    ("19:15", "52921052", "WIN",  +19.02),
    ("20:40", "52928741", "LOSS", -11.48),
]


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


def main():
    bars = load_m1(COMMON / "353pm20052026.csv")
    last_t = bars[-1]["time"]
    print(f"M1 data: {bars[0]['time']} -> {last_t}\n")
    m5 = aggregate_to_tf(bars, 5)
    by_t = {b["time"]: b for b in m5}
    h1 = aggregate_to_tf(bars, 60)
    fvgs = find_h1_fvgs(h1)

    print(f"  {'fire':<6} {'out':<5} {'pnl':>7} {'upWick%':>8} {'wick<=35?':>10} "
          f"{'fvgTap?':>8}  verdict")
    print("  " + "-"*70)
    block_would_help = 0   # losers the wick filter would block
    block_would_hurt = 0   # winners the wick filter would block
    not_covered = 0
    for fire, ticket, out, pnl in S3_TODAY:
        # bo bar = fire_time - 5min, today
        h, m = map(int, fire.split(":"))
        bo_t = datetime(2026,5,19,h,m) - timedelta(minutes=5)
        bo = by_t.get(bo_t)
        if bo is None or bo_t > last_t:
            print(f"  {fire:<6} {out:<5} {pnl:>+7.2f}  (no M1 data — after {last_t.strftime('%H:%M')})")
            not_covered += 1
            continue
        rng = bo["high"] - bo["low"]
        upper_wick = bo["high"] - max(bo["open"], bo["close"])
        wick_frac = (upper_wick / rng) if rng > 0 else 0
        wick_ok = wick_frac <= 0.35
        # FVG tap: check the bo bar overlaps an unfilled bullish FVG
        fvg = fvg_tapped_at(fvgs, bo)
        # verdict
        if not wick_ok:
            if out == "LOSS":
                verdict = "wick-filter BLOCKS this LOSER (good)"
                block_would_help += 1
            else:
                verdict = "wick-filter BLOCKS this winner (bad)"
                block_would_hurt += 1
        else:
            verdict = "passes wick filter (unchanged)"
        print(f"  {fire:<6} {out:<5} {pnl:>+7.2f} {wick_frac*100:>7.0f}% "
              f"{'YES' if wick_ok else 'NO':>10} {'yes' if fvg else 'no':>8}  {verdict}")

    print()
    print(f"  Upper-wick rejection (<=0.35) effect on covered trades:")
    print(f"    blocks {block_would_help} LOSERS (saves money)")
    print(f"    blocks {block_would_hurt} winners (costs money)")
    print(f"    {not_covered} trades not covered (M1 data ends before them)")


if __name__ == "__main__":
    main()
