"""turtle_desk_filters_test.py — test the two genuinely-untested filters from
the Turtle Trader Desk Pine indicator, on S1 (its MQL5 descendant), on 12d real
ticks + walk-forward:

  A) NO-TRADE SESSION WINDOWS (UTC): block signals in the institutional spike windows
     - Volume fade / Friday    19:00-21:00 UTC
     - NY rollover             21:00-23:00 UTC
     - Late-Asia lull          23:00-03:00 UTC
     - Pre-London trap         04:00-07:00 UTC
     Our tick data is BROKER time (UTC+3) -> convert each signal: utc = broker_hour - 3.

  B) BREAKOUT-FAILURE EARLY EXIT: after entry, if an M5 candle CLOSES back inside the
     UHV level (below uhv_high for a buy / above uhv_low for a sell) within N bars,
     exit at that close instead of waiting for the full SL. (Tick SL/TP still active;
     whichever triggers first in TIME wins.)

Honest engine: per-signal, realistic entry at ask/bid, real tick SL/TP, M5-close
failure overlay. Baseline run through the SAME engine for apples-to-apples.
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from s1_video2_backtest import detect_buy, detect_sell

CONTRACT = 100.0
LOTS = 0.02

NO_TRADE_UTC = set([19,20, 21,22, 23,0,1,2, 4,5,6])  # vol-fade, rollover, late-asia, pre-london


def in_no_trade(sig):
    utc_hour = (sig["fire_time"].hour - 3) % 24   # broker (UTC+3) -> UTC
    return utc_hour in NO_TRADE_UTC


def m5_failure_time(m5_by_time, sig, fail_bars):
    """Return the time of the first M5 close (within fail_bars after the signal bar)
    that closes back inside the UHV level, else None."""
    bo_t = sig["bo_time"]; side = sig["side"]; lvl = sig["uhv_level"]
    # bars strictly after bo
    later = [b for b in m5_by_time if b["time"] > bo_t]
    later.sort(key=lambda b: b["time"])
    for b in later[:fail_bars]:
        if side > 0 and b["close"] < lvl: return b["time"] + timedelta(minutes=5), b["close"]
        if side < 0 and b["close"] > lvl: return b["time"] + timedelta(minutes=5), b["close"]
    return None, None


def replay_one(ticks, m5, sig, ppp, fail_bars=0):
    ft = sig["fire_time"]; side = sig["side"]; sl, tp = sig["sl"], sig["tp"]
    fail_t = fail_c = None
    if fail_bars > 0:
        fail_t, fail_c = m5_failure_time(m5, sig, fail_bars)
    entry = None
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        if t < ft: continue
        if entry is None:
            entry = ask if side > 0 else bid
            continue
        # breakout-failure exit (time-ordered vs SL/TP)
        if fail_t is not None and t >= fail_t:
            return (fail_c - entry) * ppp if side > 0 else (entry - fail_c) * ppp
        if side > 0:
            if bid <= sl: return (sl - entry) * ppp
            if bid >= tp: return (tp - entry) * ppp
        else:
            if ask >= sl: return (entry - sl) * ppp
            if ask <= tp: return (entry - tp) * ppp
    if entry is not None and ticks:
        last = ticks[-1]
        return (last["bid"]-entry)*ppp if side > 0 else (entry-last["ask"])*ppp
    return None


def gen_s1(m5, h1_bull, h1_bear):
    s=[]; fired=set()
    for idx in range(30, len(m5)):
        for det,fv in [(detect_buy,h1_bull),(detect_sell,h1_bear)]:
            sig=det(m5,idx,fv,sl_buf=2.0,tp_points=7.5,big_spread=True,spread_mult=1.3)
            if sig and sig["ref"] not in fired: s.append(sig); fired.add(sig["ref"])
    return s


def run(cache, days, h1_bull, h1_bear, session_filter=False, fail_bars=0):
    ppp = LOTS*CONTRACT; pnls=[]
    for day in days:
        if day not in cache: continue
        c = cache[day]
        for sig in gen_s1(c["m5"], h1_bull, h1_bear):
            if session_filter and in_no_trade(sig): continue
            p = replay_one(c["ticks"], c["m5"], sig, ppp, fail_bars)
            if p is not None: pnls.append(p)
    return [{"pnl":p} for p in pnls]


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<38} no trades"); return None
    ev=r["pwin"]*r["w_avg"]-(1-r["pwin"])*r["l_avg"]
    print(f"  {label:<38} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% TOT=${r['total']:>+7.1f} EV=${ev:+6.2f}")
    return r


def main():
    print("Loading 12d...")
    bars = load_m1_merged(); days_bars = group_bars_by_day(bars)
    allf = find_h1_fvgs(aggregate_to_tf(bars,60))
    h1_bull=[f for f in allf if f["side"]=="bullish"]; h1_bear=[f for f in allf if f["side"]=="bearish"]
    cache={}
    for tf in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        day=Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db=days_bars[day]
        if len(db)<30: continue
        ticks=load_ticks(tf)
        if len(ticks)<100: continue
        cache[day]={"m5":aggregate_to_tf(db,5),"ticks":ticks}
    days=sorted(cache.keys()); mid=len(days)//2; train,test=days[:mid],days[mid:]
    print(f"  {len(cache)} days. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    plans = [
        ("baseline (current S1)", dict()),
        ("+ session no-trade windows", dict(session_filter=True)),
        ("+ breakout-fail exit (3 bars)", dict(fail_bars=3)),
        ("+ breakout-fail exit (5 bars)", dict(fail_bars=5)),
        ("+ BOTH (session + fail 3)", dict(session_filter=True, fail_bars=3)),
    ]
    for label, kw in plans:
        print("="*70); print(f"  {label}"); print("="*70)
        rpt("   FULL 12d", run(cache, days, h1_bull, h1_bear, **kw))
        rpt("   TRAIN",    run(cache, train, h1_bull, h1_bear, **kw))
        rpt("   TEST(OOS)",run(cache, test,  h1_bull, h1_bear, **kw))
        print()


if __name__ == "__main__":
    main()
