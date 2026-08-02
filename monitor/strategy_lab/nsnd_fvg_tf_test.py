"""nsnd_fvg_tf_test.py — structure-aware re-test of NSND: vary the FVG
timeframe (NSND is an M1 strategy, so test M1/M5/M15/H1 FVG) and re-test
the 1-Day trend filter on top. Faithful reimplementation of nsnd_ea_mirror's
core with an EXPLICIT, parameterized FVG timeframe list.
"""
import csv, sys, glob
from datetime import datetime, timedelta, date
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import replay_ticks_both

CONTRACT = 100.0


def fvg_overlap(tf_bars, tf_minutes, cur_time, lo, hi, bullish, lookback=30):
    horizon = -1
    for i in range(len(tf_bars) - 1, -1, -1):
        if tf_bars[i]["time"] + timedelta(minutes=tf_minutes) <= cur_time:
            horizon = i; break
    if horizon < 2: return False
    for i in range(max(2, horizon - lookback), horizon + 1):
        if bullish:
            gap_lo = tf_bars[i-2]["high"]; gap_hi = tf_bars[i]["low"]
        else:
            gap_lo = tf_bars[i]["high"];   gap_hi = tf_bars[i-2]["low"]
        if gap_hi <= gap_lo: continue
        filled = False
        for j in range(i + 1, horizon + 1):
            if bullish and tf_bars[j]["low"] < gap_lo: filled = True; break
            if not bullish and tf_bars[j]["high"] > gap_hi: filled = True; break
        if filled: continue
        if lo <= gap_hi and hi >= gap_lo: return True
    return False


def nsnd_signals(m1, fvg_specs, vol_n=4, vol_min=3, narrow_frac=1.0,
                 uhv_lb=20, uhv_mult=1.30, trend_lb=60, trend_th=2.0,
                 ns_lb=15, sl_buf=0.10, tp_usd=12.0, lots=0.10, sell_tp_usd=None):
    """fvg_specs = list of (tf_bars, tf_minutes); a signal needs ANY to overlap.
    sell_tp_usd: if set, sells use this TP instead of tp_usd (asymmetric)."""
    if sell_tp_usd is None: sell_tp_usd = tp_usd
    sigs = []; last_bo = None
    def trend(idx):
        if idx < 1 + trend_lb: return 0
        d = m1[idx-1]["close"] - m1[idx-1-trend_lb]["close"]
        return +1 if d > trend_th else (-1 if d < -trend_th else 0)
    def is_nsnd(k, buy):
        c = m1[k]
        if buy and c["close"] >= c["open"]: return False
        if not buy and c["close"] <= c["open"]: return False
        lc = 0
        for j in range(k+1, k+1+vol_n):
            if j >= len(m1): return False
            if m1[j]["vol"] > c["vol"]: lc += 1
        if lc < vol_min: return False
        s=0;n=0
        for j in range(k+1,k+6):
            if j>=len(m1): break
            s += m1[j]["high"]-m1[j]["low"]; n+=1
        if n==0: return False
        return (c["high"]-c["low"]) <= narrow_frac*(s/n)
    def prior_uhv(k, buy, avg20):
        for j in range(k+1, k+1+uhv_lb):
            if j>=len(m1): return False
            c=m1[j]
            if buy and c["close"]>=c["open"]: continue
            if not buy and c["close"]<=c["open"]: continue
            if c["vol"] >= uhv_mult*avg20: return True
        return False
    def avg20(idx):
        if idx<21: return 0
        return sum(m1[idx-j]["vol"] for j in range(2,22))/20.0
    for idx in range(ns_lb+uhv_lb+trend_lb+5, len(m1)):
        bo = m1[idx]
        if bo["time"]==last_bo: continue
        last_bo = bo["time"]
        tr = trend(idx)
        if tr==0: continue
        buy = tr>0
        a20 = avg20(idx)
        if a20<=0: continue
        for k_off in range(2, 2+ns_lb):
            k = idx-k_off
            if not is_nsnd(k, buy): continue
            if not prior_uhv(k, buy, a20): continue
            lo=m1[k]["low"]; hi=m1[k]["high"]
            if not any(fvg_overlap(b,tm,m1[k]["time"],lo,hi,buy) for b,tm in fvg_specs):
                continue
            if buy and bo["low"]>=lo: continue
            if not buy and bo["high"]<=hi: continue
            already=False
            for m_off in range(k_off-1,1,-1):
                m=idx-m_off
                if m==k: continue
                if buy and m1[m]["low"]<lo: already=True;break
                if not buy and m1[m]["high"]>hi: already=True;break
            if already: continue
            ppp=lots*CONTRACT
            tpd=(tp_usd if buy else sell_tp_usd)/ppp
            entry=bo["close"]
            sl = bo["low"]-sl_buf if buy else bo["high"]+sl_buf
            tp = entry+tpd if buy else entry-tpd
            sigs.append({"fire_time": bo["time"]+timedelta(seconds=60),
                         "side": +1 if buy else -1, "sl":sl, "tp":tp})
            break
    return sigs


def rpt(label, trades):
    r = stats(trades)
    if not r:
        print(f"  {label:<40} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos="OK " if r["total"]>0 else "BAD"
    print(f"  {label:<40} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def build_daily(bars):
    out={}
    for b in bars:
        d=b["time"].date()
        if d not in out: out[d]={"date":d,"close":b["close"]}
        else: out[d]["close"]=b["close"]
    return out


def main():
    print("Loading 12d...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    tf = {"M1": bars, "M5": aggregate_to_tf(bars,5),
          "M15": aggregate_to_tf(bars,15), "H1": aggregate_to_tf(bars,60)}
    daily = build_daily(bars)

    cache={}
    for tfp in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        day=Path(tfp).stem.split("_")[-1]
        if day not in days_bars: continue
        db=days_bars[day]
        if len(db)<30: continue
        ticks=load_ticks(tfp)
        if len(ticks)<100: continue
        cache[day]={"m1":db,"ticks":ticks,"date":db[0]["time"].date()}
    print(f"  {len(cache)} days\n")

    # Per-day FVG specs need full-history bars; reuse global tf bars (clock-aligned).
    fvg_configs = {
        "M15+H1 (current live)": [(tf["M15"],15),(tf["H1"],60)],
        "M1 only":               [(tf["M1"],1)],
        "M5 only":               [(tf["M5"],5)],
        "M15 only":              [(tf["M15"],15)],
        "M1+M5":                 [(tf["M1"],1),(tf["M5"],5)],
        "M5+M15":                [(tf["M5"],5),(tf["M15"],15)],
    }

    def run(specs, filter_1d=False):
        trades=[]
        for day,c in cache.items():
            sigs = nsnd_signals(c["m1"], specs)
            if filter_1d:
                dt = daily_trend(daily, c["date"])
                kept=[]
                for s in sigs:
                    if dt==+1 and s["side"]!=+1: continue
                    if dt==-1 and s["side"]!=-1: continue
                    if dt==0: continue
                    kept.append(s)
                sigs=kept
            if sigs:
                trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
        return trades

    def daily_trend(daily, on_date, lb=2):
        days=sorted([d for d in daily if d<on_date])
        if len(days)<lb+1: return 0
        a=daily[days[-1]]["close"]; b=daily[days[-1-lb]]["close"]
        return +1 if a>b else (-1 if a<b else 0)

    print("="*86)
    print("  NSND — FVG timeframe sweep (vol_min=3, trend=2.0, both sides)")
    print("="*86)
    for label, specs in fvg_configs.items():
        rpt(label, run(specs))

    print()
    print("="*86)
    print("  NSND — best FVG TF + 1-Day trend filter re-test")
    print("="*86)
    # pick a couple to layer 1D on
    for label in ["M15+H1 (current live)", "M5 only", "M5+M15"]:
        rpt(f"{label} + 1D trend", run(fvg_configs[label], filter_1d=True))


if __name__ == "__main__":
    main()
