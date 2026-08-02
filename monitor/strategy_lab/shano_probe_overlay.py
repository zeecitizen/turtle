"""shano_probe_overlay.py — does adding SHANO'S PROBE (momentum-confirmation
gate) to our EA entries raise win rate / P&L?

Shano's edge: she doesn't enter on the signal; she probes tiny and only commits
if price IMMEDIATELY moves in her favor (confirm ~0.45-0.58 pts) before it moves
against (fail). We test that as a GATE on each S1/S3/NSND signal:

  For each signal, scan ticks from fire_time for `window_s` seconds:
    - BUY: confirmed if ask rises to entry+confirm before bid falls to entry-fail
    - SELL: mirror
  Only CONFIRMED signals are taken (entry kept at signal price = filter effect).
  Skipped if it moves against first, or no move within the window (no momentum).

Compares baseline (take all) vs probe-gated, per EA + combined, on 12d real ticks.
"""
import sys, glob
from collections import defaultdict
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats, find_h1_fvgs
from backtest_setups import find_h1_fvgs as find_fvgs_sided
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both
from s1_video2_backtest import detect_buy as s1_buy, detect_sell as s1_sell

CONTRACT = 100.0
LOTS = 0.02


def probe_gate(ticks, sig, confirm, fail, window_s):
    """Return True if momentum confirms within window_s seconds after fire_time."""
    ft = sig["fire_time"]
    side = sig.get("side", +1)
    entry = None
    end = None
    for tk in ticks:
        t = tk["t"]
        if t < ft: continue
        if entry is None:
            entry = tk["ask"] if side > 0 else tk["bid"]
            end = t.timestamp() + window_s
        if t.timestamp() > end:
            return False  # no momentum within window
        if side > 0:
            if tk["bid"] <= entry - fail: return False     # went against first
            if tk["ask"] >= entry + confirm: return True    # confirmed up
        else:
            if tk["ask"] >= entry + fail: return False
            if tk["bid"] <= entry - confirm: return True
    return False


def build_cache():
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    m5_bull = find_h1_fvgs(aggregate_to_tf(bars, 5))
    allf = find_fvgs_sided(aggregate_to_tf(bars, 60))
    h1_bull = [f for f in allf if f["side"]=="bullish"]
    h1_bear = [f for f in allf if f["side"]=="bearish"]
    m15 = aggregate_to_tf(bars, 15)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db,5), "m1": db, "ticks": ticks}
    return cache, h1, m5_bull, h1_bull, h1_bear, m15


def gen_sigs(c, ea, h1, m5_bull, h1_bull, h1_bear, m15):
    if ea == "S3":
        s = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_bull, require_fvg=True)
        for x in s: x["side"]=+1
        return s
    if ea == "S1":
        s=[]; fired=set()
        for idx in range(30, len(c["m5"])):
            for det,fv in [(s1_buy,h1_bull),(s1_sell,h1_bear)]:
                sig=det(c["m5"],idx,fv,sl_buf=2.0,tp_points=7.5,big_spread=True,spread_mult=1.3)
                if sig and sig["ref"] not in fired: s.append(sig); fired.add(sig["ref"])
        return s
    if ea == "NSND":
        return nsnd_ea_mirror(c["m1"], m15, h1, vol_min=3, trend_th=2.0, use_hhhl=False)
    return []


def run(cache, refs, ea, gate=None):
    trades=[]
    for day,c in cache.items():
        sigs = gen_sigs(c, ea, *refs)
        if gate:
            confirm, fail, win = gate
            sigs = [s for s in sigs if probe_gate(c["ticks"], s, confirm, fail, win)]
        if sigs:
            trades += replay_ticks_both(c["ticks"], sigs, LOTS, CONTRACT)
    return trades


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<40} no trades"); return None
    ev=r["pwin"]*r["w_avg"]-(1-r["pwin"])*r["l_avg"]
    print(f"  {label:<40} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% TOT=${r['total']:>+8.1f} EV=${ev:+6.2f}")
    return r


def main():
    print("Loading 12d...")
    cache, h1, m5_bull, h1_bull, h1_bear, m15 = build_cache()
    refs = (h1, m5_bull, h1_bull, h1_bear, m15)
    print(f"  {len(cache)} days\n")
    # Shano-ish probe params: confirm 0.45-0.58 pts, fail similar, short window
    gates = [
        ("baseline (no probe)", None),
        ("probe c0.45/f0.45/60s", (0.45, 0.45, 60)),
        ("probe c0.58/f0.30/60s", (0.58, 0.30, 60)),
        ("probe c0.30/f0.30/30s", (0.30, 0.30, 30)),
        ("probe c0.58/f0.58/120s", (0.58, 0.58, 120)),
    ]
    for ea in ["S3","S1","NSND"]:
        print("="*72); print(f"  {ea}"); print("="*72)
        for label, gate in gates:
            rpt(label, run(cache, refs, ea, gate))
        print()


if __name__ == "__main__":
    main()
