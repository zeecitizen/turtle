"""portfolio_deep.py — per-EA correlation + optimal lot allocation.

Builds each EA's daily P&L series (12d, current deployed configs), then:
  1. Per-EA risk stats (mean/day, std, Sharpe-like, worst, max DD)
  2. Pairwise correlation of daily P&L (diversification check)
  3. Lot-allocation comparison at a FIXED total risk budget (0.06 lots split
     across the 3 EAs): equal / EV-weighted / inverse-vol / Sharpe-weighted.
     Reports combined total, daily Sharpe, and max DD for each split.
"""
import sys, glob, math
from collections import defaultdict
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, find_h1_fvgs
from backtest_setups import find_h1_fvgs as find_fvgs_sided
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both
from s1_video2_backtest import detect_buy as s1_buy, detect_sell as s1_sell

CONTRACT = 100.0
BASE_LOTS = 0.02   # the lot size each EA's per-day series is computed at


def day_pnl(ticks, sigs, lots):
    if not sigs: return 0.0
    done = replay_ticks_both(ticks, sigs, lots, CONTRACT)
    return sum(t["pnl"] for t in done)


def mean(x): return sum(x)/len(x) if x else 0
def std(x):
    if len(x) < 2: return 0
    m = mean(x); return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))
def corr(a, b):
    if len(a) < 2: return 0
    ma, mb = mean(a), mean(b); sa, sb = std(a), std(b)
    if sa == 0 or sb == 0: return 0
    cov = sum((a[i]-ma)*(b[i]-mb) for i in range(len(a)))/(len(a)-1)
    return cov/(sa*sb)
def max_dd(series):
    cum=peak=dd=0
    for v in series:
        cum+=v; peak=max(peak,cum); dd=max(dd,peak-cum)
    return dd


def main():
    print(f"Loading 12d... (per-EA series @ {BASE_LOTS} lots)")
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

    days = sorted(cache.keys())
    series = {"S3": [], "S1": [], "NSND": []}
    for day in days:
        c = cache[day]
        s3 = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_bull, require_fvg=True)
        for s in s3: s["side"]=+1
        series["S3"].append(day_pnl(c["ticks"], s3, BASE_LOTS))
        s1=[]; fired=set()
        for idx in range(30, len(c["m5"])):
            for det,fv in [(s1_buy,h1_bull),(s1_sell,h1_bear)]:
                sig=det(c["m5"],idx,fv,sl_buf=2.0,tp_points=7.5,big_spread=True,spread_mult=1.3)
                if sig and sig["ref"] not in fired: s1.append(sig); fired.add(sig["ref"])
        series["S1"].append(day_pnl(c["ticks"], s1, BASE_LOTS))
        ns = nsnd_ea_mirror(c["m1"], m15, h1, vol_min=3, trend_th=2.0, use_hhhl=False)
        series["NSND"].append(day_pnl(c["ticks"], ns, BASE_LOTS))

    # 1. per-EA risk stats
    print("\n"+"="*78); print("  PER-EA RISK STATS (daily, @0.02 lots)"); print("="*78)
    print(f"  {'EA':<6} {'total':>9} {'mean/d':>8} {'std/d':>8} {'Sharpe':>7} {'worst':>8} {'maxDD':>8}")
    for ea in ["S3","S1","NSND"]:
        s=series[ea]; sh = mean(s)/std(s) if std(s) else 0
        print(f"  {ea:<6} {sum(s):>+9.1f} {mean(s):>+8.1f} {std(s):>8.1f} {sh:>7.2f} "
              f"{min(s):>+8.1f} {max_dd(s):>8.1f}")

    # 2. correlation
    print("\n"+"="*78); print("  DAILY P&L CORRELATION (lower = better diversification)"); print("="*78)
    eas=["S3","S1","NSND"]
    print("        "+"".join(f"{e:>8}" for e in eas))
    for a in eas:
        print(f"  {a:<6}"+"".join(f"{corr(series[a],series[b]):>8.2f}" for b in eas))

    # 3. lot allocation at fixed total budget 0.06 lots (=3x0.02 equal baseline)
    print("\n"+"="*78); print("  LOT ALLOCATION @ fixed 0.06-lot total budget"); print("="*78)
    BUDGET = 0.06
    # weight schemes (normalized to sum=1)
    ev = {ea: max(0.01, mean(series[ea])) for ea in eas}
    sh = {ea: max(0.01, (mean(series[ea])/std(series[ea]) if std(series[ea]) else 0)) for ea in eas}
    iv = {ea: (1/std(series[ea]) if std(series[ea]) else 0) for ea in eas}
    schemes = {
        "equal":        {ea: 1/3 for ea in eas},
        "EV-weighted":  {ea: ev[ea]/sum(ev.values()) for ea in eas},
        "Sharpe-weighted": {ea: sh[ea]/sum(sh.values()) for ea in eas},
        "inverse-vol":  {ea: iv[ea]/sum(iv.values()) for ea in eas},
    }
    print(f"  {'scheme':<16} {'S3lot':>6} {'S1lot':>6} {'NSlot':>6} {'total$':>9} {'Sharpe':>7} {'maxDD$':>8}")
    for name, w in schemes.items():
        lots = {ea: BUDGET*w[ea] for ea in eas}
        # scale each EA's 0.02 series by (lot/0.02)
        comb = [sum(series[ea][i]*(lots[ea]/BASE_LOTS) for ea in eas) for i in range(len(days))]
        sh_c = mean(comb)/std(comb) if std(comb) else 0
        print(f"  {name:<16} {lots['S3']:>6.3f} {lots['S1']:>6.3f} {lots['NSND']:>6.3f} "
              f"{sum(comb):>+9.1f} {sh_c:>7.2f} {max_dd(comb):>8.1f}")
    print("\n  Note: 'equal' = current live (each EA 0.02). Higher Sharpe = smoother equity.")


if __name__ == "__main__":
    main()
