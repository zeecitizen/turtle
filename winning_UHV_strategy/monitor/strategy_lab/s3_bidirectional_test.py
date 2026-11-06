"""s3_bidirectional_test.py — backtest BIDIRECTIONAL S3 with HTF gating.
S3 is currently buy-only (liquidity-sweep: green wicks below a retracement
red's low, closes inside, higher vol, in M5 uptrend, M5-FVG tap).
Sell mirror: red wicks above a retracement green's high, closes inside,
higher vol, in M5 downtrend, M5-bear-FVG tap.
HTF gate: buys only when H1 trend up, sells only when H1 trend down.
Compare to current buy-only baseline on 12d real ticks.
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats, find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both

CONTRACT = 100.0


def find_bear_fvgs(bars):
    fv = []
    for i in range(2, len(bars)):
        gh, gl = bars[i-2]["low"], bars[i]["high"]   # older.low > newer.high
        if gh <= gl: continue
        filled = next((bars[j]["time"] for j in range(i+1, len(bars)) if bars[j]["high"] > gh), None)
        fv.append({"t0": bars[i]["time"], "gap_low": gl, "gap_high": gh, "filled_at": filled})
    return fv


def bear_fvg_tapped(fvgs, bar):
    for f in fvgs:
        if f["t0"] >= bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= bar["time"]: continue
        if bar["low"] <= f["gap_high"] and bar["high"] >= f["gap_low"]:
            return True
    return False


def s3_sell_mirror(m5, bear_fvgs, trend_lb=24, trend_th=1.0, retrace_lb=30,
                   tp_peak_lb=10, sl_buf=2.0):
    """Mirror of s3_ea_mirror for SELLS (downtrend liquidity-sweep)."""
    sigs = []; fired = set(); last_t = None
    for idx in range(max(trend_lb, 30), len(m5)):
        bo = m5[idx]
        if bo["time"] == last_t: continue
        last_t = bo["time"]
        if bo["close"] >= bo["open"]: continue          # need red
        if idx < trend_lb: continue
        if m5[idx-trend_lb]["close"] - bo["close"] <= trend_th: continue  # downtrend
        # find a red whose HIGH was broken by subsequent greens (rally retrace)
        greens = []
        for back_r in range(idx-2, max(idx-retrace_lb-1, -1), -1):
            rb = m5[back_r]
            if rb["close"] >= rb["open"]: continue
            red_high = rb["high"]; tmp = []; broke = False
            for j in range(back_r+1, idx):
                b = m5[j]
                if b["close"] > b["open"]:
                    if b["close"] > red_high or b["high"] > red_high: broke = True
                    tmp.append(j)
            if broke and tmp: greens = tmp; break
        if not greens: continue
        matching = None
        for gi in greens:
            g = m5[gi]
            if bo["high"] <= g["high"]: continue   # didn't wick above
            if bo["close"] >= g["high"]: continue  # didn't close back inside
            if bo["vol"] <= g["vol"]: continue     # need higher vol
            matching = g; break
        if matching is None: continue
        if matching["time"] in fired: continue
        if not bear_fvg_tapped(bear_fvgs, bo): continue
        sl = bo["high"] + sl_buf
        tp = 0.0
        lows = [m5[j]["low"] for j in range(max(0, idx-tp_peak_lb), idx)]
        if not lows: continue
        tp = min(lows)
        if tp >= bo["close"] - min(0.2, sl_buf*2): continue
        sigs.append({"fire_time": bo["time"] + timedelta(minutes=5), "side": -1,
                     "sl": sl, "tp": tp})
        fired.add(matching["time"])
    return sigs


def h1_dir(h1, t, lb):
    prior = [b for b in h1 if b["time"] + timedelta(minutes=60) <= t]
    if len(prior) <= lb: return 0
    d = prior[-1]["close"] - prior[-1-lb]["close"]
    return 1 if d > 0 else (-1 if d < 0 else 0)


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<40} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<40} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    m5_bull = find_h1_fvgs(aggregate_to_tf(bars, 5))
    m5_bear = find_bear_fvgs(aggregate_to_tf(bars, 5))
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    print(f"  {len(cache)} days\n")

    LB = 3  # H1 trend lookback

    def run(do_buy=True, do_sell=False, gate=False):
        trades = []
        for day, c in cache.items():
            sigs = []
            if do_buy:
                bs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_bull, require_fvg=True)
                for s in bs: s["side"] = +1
                if gate: bs = [s for s in bs if h1_dir(h1, s["fire_time"], LB) > 0]
                sigs += bs
            if do_sell:
                ss = s3_sell_mirror(c["m5"], m5_bear, sl_buf=2.0)
                if gate: ss = [s for s in ss if h1_dir(h1, s["fire_time"], LB) < 0]
                sigs += ss
            if sigs:
                trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
        return trades

    print("="*80)
    print("  S3 bidirectional + HTF gating (M5-FVG, SL=$2, 12d)")
    print("="*80)
    rpt("buy-only, no gate (CURRENT LIVE)", run(True, False, False))
    rpt("buy-only + H1-up gate",            run(True, False, True))
    rpt("sell-only, no gate",               run(False, True, False))
    rpt("sell-only + H1-down gate",         run(False, True, True))
    rpt("BIDIRECTIONAL + HTF gate",         run(True, True, True))
    rpt("BIDIRECTIONAL, no gate",           run(True, True, False))


if __name__ == "__main__":
    main()
