"""nsnd_native_validation.py — THE make-or-break test for reviving NSND.

Live EA reads MT5-NATIVE M1 volume; the old backtest read reverse-engineered
(tick-reconstructed) volume that differs on 99.9% of bars (~0.66-0.75x). NS/ND
is 100% volume-driven, so +$681 was on volume that doesn't exist live.

This runs the SAME nsnd_signals detector on NATIVE bars (latest_for_claude.csv,
exported via ExportRecentBars on XAUUSDm) vs reverse-engineered, same ticks for P&L.

  edge SURVIVES on native -> NSND salvageable; align live EA + deploy.
  edge VANISHES on native -> profit was a volume artifact; keep NSND disabled.
"""
import csv, sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import replay_ticks_both
from nsnd_fvg_tf_test import nsnd_signals
CONTRACT = 100.0

def load_csv_m1(fn):
    bars = []
    for r in csv.DictReader(open(COMMON / fn)):
        try:
            bars.append({"time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                         "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
        except Exception:
            pass
    bars.sort(key=lambda b: b["time"])
    return bars

# cache tick files we actually have
TICKDAYS = {p.name[len("shano_ticks_"):-4]: p for p in COMMON.glob("shano_ticks_*.csv")}

def evaluate(m1, label):
    print(f"\n[{label}] {len(m1)} M1 bars — detecting…", flush=True)
    m15 = aggregate_to_tf(m1, 15)
    sigs = nsnd_signals(m1, [(m15, 15)])
    byday = defaultdict(list)
    for s in sigs:
        byday[s["fire_time"].strftime("%Y-%m-%d")].append(s)
    days = sorted(d for d in byday if d in TICKDAYS)
    print(f"  signals total={len(sigs)} | on days with ticks={sum(len(byday[d]) for d in days)} over {len(days)} days", flush=True)
    trades, perday = [], {}
    for d in days:
        ticks = load_ticks(TICKDAYS[d])
        t = replay_ticks_both(ticks, byday[d], 0.10, CONTRACT)
        trades += t; perday[d] = sum(x["pnl"] for x in t) if t else 0
    r = stats(trades)
    if not r:
        print("  no replayable trades"); return
    # walk-forward split on the traded days
    cut = days[len(days)//2] if len(days) >= 4 else None
    tr_tot = sum(v for d, v in perday.items() if cut and d < cut)
    oos_tot = sum(v for d, v in perday.items() if cut and d >= cut)
    print(f"  n={r['n']}  WR={r['pwin']*100:.1f}%  TOTAL=${r['total']:+.1f}  "
          f"{'OK' if r['total']>0 else 'BAD'}", flush=True)
    if cut: print(f"  walk-forward: TRAIN ${tr_tot:+.1f} | OOS(from {cut}) ${oos_tot:+.1f}", flush=True)

print("NSND detector — NATIVE vs reverse-engineered bars (same detector, same ticks)")
evaluate(load_csv_m1("latest_for_claude.csv"), "NATIVE (live reality)")
evaluate(load_m1_merged(), "REVERSE-ENG (old backtest)")
