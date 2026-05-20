"""ichimoku_backtest.py — GENUINE backtest of the Ichimoku Confluence Scalp
(Strategy II from the PDF) on 12 days of real XAUUSD ticks.

Rules implemented faithfully (long; short = mirror):
  Trend: close > Kumo cloud top AND close > EMA21 AND ema21 slope up AND kijun slope up
  Trigger: RSI(9) dipped toward/below 50 in last few bars then is back above 50 (bounce)
  Entry: BUY-STOP 1 tick above the signal candle's high (must be hit within a window)
  SL: recent swing low − buffer (proxy for Bill Williams fractal)  [+ optional 0.5*ATR]
  TP: fixed $ target, or R:R multiple
Tested with standard (9,26,52) AND accelerated (5,13,26) params, TP sweep, walk-forward.

Honest engine: real tick fills (buy-stop trigger via ask, bracket exit via bid/ask).
Profit Factor reported (gross wins / gross losses) — the PDF's key metric.
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day

CONTRACT = 100.0
LOTS = 0.02


def ichimoku(m5, tenkan_n, kijun_n, spanb_n, shift=26):
    n = len(m5)
    hi = [b["high"] for b in m5]; lo = [b["low"] for b in m5]; cl = [b["close"] for b in m5]
    def donch(i, p):
        if i - p + 1 < 0: return None, None
        seg_hi = max(hi[max(0,i-p+1):i+1]); seg_lo = min(lo[max(0,i-p+1):i+1])
        return seg_hi, seg_lo
    tenkan=[None]*n; kijun=[None]*n; spanA_raw=[None]*n; spanB_raw=[None]*n
    for i in range(n):
        h,l = donch(i, tenkan_n);  tenkan[i] = (h+l)/2 if h is not None else None
        h,l = donch(i, kijun_n);   kijun[i]  = (h+l)/2 if h is not None else None
        if tenkan[i] is not None and kijun[i] is not None:
            spanA_raw[i] = (tenkan[i]+kijun[i])/2
        h,l = donch(i, spanb_n);   spanB_raw[i] = (h+l)/2 if h is not None else None
    # cloud at bar i = spans projected from `shift` bars ago
    cloud_top=[None]*n; cloud_bot=[None]*n
    for i in range(n):
        a = spanA_raw[i-shift] if i-shift>=0 else None
        b = spanB_raw[i-shift] if i-shift>=0 else None
        if a is not None and b is not None:
            cloud_top[i]=max(a,b); cloud_bot[i]=min(a,b)
    return tenkan, kijun, cloud_top, cloud_bot


def ema(vals, p):
    out=[None]*len(vals); k=2/(p+1); e=None
    for i,v in enumerate(vals):
        e = v if e is None else v*k + e*(1-k)
        out[i]=e
    return out


def rsi(vals, p):
    out=[None]*len(vals)
    if len(vals)<p+1: return out
    gains=0; losses=0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1]; gains+=max(d,0); losses+=max(-d,0)
    ag=gains/p; al=losses/p
    out[p]=100-100/(1+(ag/al if al else 999))
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1]
        ag=(ag*(p-1)+max(d,0))/p; al=(al*(p-1)+max(-d,0))/p
        out[i]=100-100/(1+(ag/al if al else 999))
    return out


def gen_signals(m5, params, swing_lb=10, tp_dollars=None, rr=None, sl_buf=0.2):
    tn,kj = params["tenkan"], params["kijun"]
    tenkan,kijun,ctop,cbot = ichimoku(m5, tn, kj, params["spanb"])
    cl=[b["close"] for b in m5]
    e21=ema(cl,21); r9=rsi(cl,9)
    sigs=[]
    start = max(params["spanb"]+26, 30)
    for i in range(start, len(m5)-1):
        if None in (ctop[i],cbot[i],e21[i],e21[i-1],kijun[i],kijun[i-1],r9[i],r9[i-1],r9[i-2]): continue
        c=cl[i]
        ema_up = e21[i]>e21[i-1]; ema_dn=e21[i]<e21[i-1]
        kj_up = kijun[i]>kijun[i-1]; kj_dn=kijun[i]<kijun[i-1]
        rsi_bounce_up = min(r9[i-2],r9[i-1])<50 and r9[i]>50
        rsi_bounce_dn = max(r9[i-2],r9[i-1])>50 and r9[i]<50
        # LONG
        if c>ctop[i] and c>e21[i] and ema_up and kj_up and rsi_bounce_up:
            swing_low=min(b["low"] for b in m5[max(0,i-swing_lb):i+1])
            entry=m5[i]["high"]+0.1
            sl=swing_low-sl_buf
            risk=entry-sl
            if risk<=0: continue
            tp = entry + (tp_dollars if tp_dollars else rr*risk)
            sigs.append({"fire_time":m5[i]["time"]+timedelta(minutes=5),"side":+1,
                         "trigger":entry,"sl":sl,"tp":tp})
        # SHORT
        elif c<cbot[i] and c<e21[i] and ema_dn and kj_dn and rsi_bounce_dn:
            swing_high=max(b["high"] for b in m5[max(0,i-swing_lb):i+1])
            entry=m5[i]["low"]-0.1
            sl=swing_high+sl_buf
            risk=sl-entry
            if risk<=0: continue
            tp=entry-(tp_dollars if tp_dollars else rr*risk)
            sigs.append({"fire_time":m5[i]["time"]+timedelta(minutes=5),"side":-1,
                         "trigger":entry,"sl":sl,"tp":tp})
    return sigs


def replay(ticks, sig, ppp, trigger_window_s=900):
    ft=sig["fire_time"]; side=sig["side"]; trig=sig["trigger"]; sl=sig["sl"]; tp=sig["tp"]
    entered=False; deadline=None
    for tk in ticks:
        t,bid,ask=tk["t"],tk["bid"],tk["ask"]
        if t<ft: continue
        if deadline is None: deadline=t.timestamp()+trigger_window_s
        if not entered:
            if t.timestamp()>deadline: return None  # buy/sell-stop never triggered
            if side>0 and ask>=trig: entered=True; entry=ask; continue
            if side<0 and bid<=trig: entered=True; entry=bid; continue
            continue
        if side>0:
            if bid<=sl: return (sl-entry)*ppp
            if bid>=tp: return (tp-entry)*ppp
        else:
            if ask>=sl: return (entry-sl)*ppp
            if ask<=tp: return (entry-tp)*ppp
    if entered and ticks:
        last=ticks[-1]
        return (last["bid"]-entry)*ppp if side>0 else (entry-last["ask"])*ppp
    return None


def stats_pf(pnls):
    if not pnls: return None
    n=len(pnls); wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
    gw=sum(wins); gl=-sum(losses)
    pf = (gw/gl) if gl>0 else 999
    return dict(n=n, wr=len(wins)/n*100, total=sum(pnls), pf=pf,
                avgw=(gw/len(wins) if wins else 0), avgl=(gl/len(losses) if losses else 0))


def run(cache, days, params, **kw):
    ppp=LOTS*CONTRACT; pnls=[]
    # signals computed on continuous M5 (built once), filtered to day
    m5=params["_m5"]
    sigs=gen_signals(m5, params, **kw)
    by_day={}
    for s in sigs:
        d=s["fire_time"].date().isoformat(); by_day.setdefault(d,[]).append(s)
    for day in days:
        if day not in cache or day not in by_day: continue
        for s in by_day[day]:
            p=replay(cache[day]["ticks"], s, ppp)
            if p is not None: pnls.append(p)
    return pnls


def rpt(label, pnls):
    r=stats_pf(pnls)
    if not r: print(f"  {label:<40} no trades"); return None
    pos="OK " if r["total"]>0 else "BAD"
    print(f"  {label:<40} n={r['n']:>3} WR={r['wr']:>4.1f}% PF={r['pf']:>4.2f} "
          f"W=${r['avgw']:>4.1f} L=${r['avgl']:>4.1f} TOT=${r['total']:>+7.1f} {pos}")
    return r


def main():
    print("Loading 12d real ticks...")
    bars=load_m1_merged(); days_bars=group_bars_by_day(bars)
    m5_full=aggregate_to_tf(bars,5)
    cache={}
    for tf in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        day=Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        ticks=load_ticks(tf)
        if len(ticks)<100: continue
        cache[day]={"ticks":ticks}
    days=sorted(cache.keys()); mid=len(days)//2; train,test=days[:mid],days[mid:]
    print(f"  {len(cache)} days, {len(m5_full)} M5 bars. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    PSTD={"tenkan":9,"kijun":26,"spanb":52,"_m5":m5_full}
    PACC={"tenkan":5,"kijun":13,"spanb":26,"_m5":m5_full}

    print("="*82); print("  Ichimoku Confluence Scalp — STANDARD (9,26,52), TP sweep, FULL 12d"); print("="*82)
    for tp in [1.5, 3.0, 5.0, 7.5]:
        rpt(f"std TP=${tp} fixed", run(cache, days, PSTD, tp_dollars=tp))
    for rr in [1.0, 1.5, 2.0]:
        rpt(f"std TP=R:R {rr}", run(cache, days, PSTD, rr=rr))

    print("\n"+"="*82); print("  ACCELERATED (5,13,26) — TP sweep, FULL 12d"); print("="*82)
    for tp in [1.5, 3.0, 5.0, 7.5]:
        rpt(f"acc TP=${tp} fixed", run(cache, days, PACC, tp_dollars=tp))
    for rr in [1.0, 1.5, 2.0]:
        rpt(f"acc TP=R:R {rr}", run(cache, days, PACC, rr=rr))

    print("\n"+"="*82); print("  WALK-FORWARD on the most promising config(s)"); print("="*82)
    for label,params,kw in [("std R:R 2.0",PSTD,dict(rr=2.0)),
                            ("acc R:R 2.0",PACC,dict(rr=2.0)),
                            ("acc TP=$5",PACC,dict(tp_dollars=5.0))]:
        print(f"  -- {label} --")
        rpt("     FULL", run(cache, days, params, **kw))
        rpt("     TRAIN", run(cache, train, params, **kw))
        rpt("     TEST(OOS)", run(cache, test, params, **kw))


if __name__ == "__main__":
    main()
