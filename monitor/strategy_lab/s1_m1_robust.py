"""s1_m1_robust.py — is S1@M1 deployable? Multi-split walk-forward + real execution
cost haircut on native bars. The 34-trades/day frequency means cost matters a lot.
Pass bar = robust across splits AND positive after a conservative per-trade cost.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, replay_ticks_both, load_ticks, COMMON

def load_native(fn="latest_for_claude.csv"):
    bars = []
    for r in csv.DictReader(open(COMMON / fn)):
        try:
            bars.append({"time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                         "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
        except Exception: pass
    bars.sort(key=lambda b: b["time"]); return bars

KW = dict(sl_buf=2.0, tp_points=7.5, do_buy=True, do_sell=True, require_fvg=False, require_sweep=True)
COST = 0.40   # conservative all-in cost per 0.01-lot trade (spread already in fills + commission/slippage)

bars = load_native()
h1 = aggregate_to_tf(bars, 60); fv = find_h1_fvgs(h1)
hb = [f for f in fv if f["side"] == "bullish"]; he = [f for f in fv if f["side"] == "bearish"]
tickdays = {Path(p).stem.split("_")[-1]: p for p in glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))}
days = group_bars_by_day(bars)

# collect all M1 trades with their day, gross pnl
trades = []   # (day, gross_pnl)
for day in sorted(days):
    if day not in tickdays: continue
    db = days[day]
    if len(db) < 35: continue
    sigs = s1_mirror(db, hb, he, **KW)
    for s in sigs:
        s["fire_time"] = s["fire_time"] - timedelta(minutes=5) + timedelta(minutes=1)
    if not sigs: continue
    for t in replay_ticks_both(load_ticks(tickdays[day]), sigs, 0.01, 100.0):
        trades.append((day, t["pnl"]))

dlist = sorted(set(d for d, _ in trades))
def total(sub, net): return sum((p - (COST if net else 0)) for _, p in sub)
def wr(sub): w = sum(1 for _, p in sub if p > 0); return 100*w/len(sub) if sub else 0

print(f"S1 @ M1 — native, {len(trades)} trades over {len(dlist)} days, cost ${COST}/trade\n")
print(f"  GROSS total: ${total(trades,0):+.0f}  | NET (after cost): ${total(trades,1):+.0f}  | WR {wr(trades):.0f}%")
print(f"  per-trade NET EV: ${total(trades,1)/len(trades):+.2f}   (~{len(trades)/len(dlist):.0f} trades/day)\n")
print("  Multi-split walk-forward (NET, after cost) — OOS must stay positive:")
ok = 0; splits = [0.4, 0.5, 0.6, 0.7, 0.8]
for f in splits:
    cut = dlist[int(len(dlist)*f)]
    tr = [(d, p) for d, p in trades if d < cut]
    te = [(d, p) for d, p in trades if d >= cut]
    oos = total(te, 1)
    if oos > 0: ok += 1
    print(f"    split @ {cut} ({int(f*100)}%):  TRAIN ${total(tr,1):>+7.0f}  OOS ${oos:>+7.0f}  {'OK' if oos>0 else 'BAD'}")
print(f"\n  VERDICT: {ok}/{len(splits)} splits OOS-positive after cost  ->  "
      f"{'ROBUST — build the M1 EA' if ok>=4 else 'FRAGILE — do not deploy as-is'}")
