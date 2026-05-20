"""backtest_eth_setups.py — test S3 (v2 teacher-spec) on ETHUSD across
multiple timeframes and exit strategies. Mirrors backtest_btc_research.py.

ETH characteristics (from inspection):
  • Price ~$2,200, avg M1 range $1.68
  • 14 days of bars, spread ~$2.75
  • Contract size: 1 ETH per lot (typical broker spec)
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import (aggregate_to_tf, find_h1_fvgs,
    detect_signals, replay_bars, stats, fmt)

COMMON  = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
ETH_CSV = COMMON / "ethusd.csv"
CONTRACT_ETH = 1.0


def load_eth_m1():
    bars = []
    with open(ETH_CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                tm = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
            except: continue
            bars.append({"time": tm, "open": float(r["open"]),
                         "high": float(r["high"]), "low": float(r["low"]),
                         "close": float(r["close"]), "vol": int(r["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars


def main():
    print("Loading ETH M1 bars...")
    m1 = load_eth_m1()
    days = (m1[-1]["time"] - m1[0]["time"]).total_seconds() / 86400
    avg_rng = sum(b["high"]-b["low"] for b in m1) / len(m1)
    print(f"  {len(m1)} M1 bars, span {days:.1f}d, avg-range ${avg_rng:.2f}")
    h1 = aggregate_to_tf(m1, 60)
    fvgs = find_h1_fvgs(h1)
    print(f"  {len(h1)} H1 bars, {len(fvgs)} bullish FVGs\n")

    LOTS = 0.10        # 0.10 ETH = $220 notional at $2200, sane size for $500 acct
    MULTI = 4          # report at 0.40

    # Per-TF threshold tuning. ETH typical move:
    #   M5: ~$1-$5 ; M15: ~$3-$10 ; M30: ~$5-$15 ; H1: ~$10-$30
    tf_configs = {
        "M5":  (5,  [2.0, 5.0, 10.0],  [1, 5, 10]),
        "M15": (15, [3.0, 10.0, 20.0], [3, 10, 20]),
        "M30": (30, [5.0, 15.0, 30.0], [5, 15, 30]),
        "H1":  (60, [10.0, 25.0, 50.0],[10, 30, 50]),
    }

    print(f"{'TF':<5} {'SLbuf':>6} {'Trend':>7} {'Peak':>5} {'FVG':>4}  {'result':<55}  proj@0.40")
    best = None
    for tf_name, (k, trends, sl_bufs) in tf_configs.items():
        bars = aggregate_to_tf(m1, k)
        for require_fvg in [False, True]:
            for sl_buf in sl_bufs:
                for trend in trends:
                    for peak_lb in [10, 20, 30]:
                        sigs = detect_signals(bars, fvgs, sl_buf, trend, 12,
                                              require_fvg, peak_lb, k)
                        if not sigs: continue
                        trades = replay_bars(m1, sigs, LOTS, CONTRACT_ETH)
                        r = stats(trades)
                        if r is None: continue
                        proj = r['total'] * MULTI
                        mark = ' *' if r['total'] > 0 else ''
                        fvg_lbl = 'Y' if require_fvg else 'N'
                        line = (f'{tf_name:<5} ${sl_buf:>5.0f} ${trend:>5.0f} '
                                f'{peak_lb:>5} {fvg_lbl:>4}  {fmt(r):<55}  '
                                f'${proj:>+8.1f}{mark}')
                        print(line)
                        if r['total'] > 0 and (best is None or r['total'] > best[0]):
                            best = (r['total'], tf_name, sl_buf, trend, peak_lb,
                                    require_fvg, r)
        print()
    if best:
        print(f'BEST: TF={best[1]} SL=${best[2]} Trend=${best[3]} Peak={best[4]} FVG={"Y" if best[5] else "N"}')
        print(f'  {fmt(best[6])}')
        print(f'  Projection @ 0.40: ${best[0]*MULTI:+.1f} / 14 days')


if __name__ == "__main__":
    main()
