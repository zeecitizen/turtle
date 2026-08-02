"""be_netsim.py — HONEST net effect of a breakeven-SL move (the test docs/recommended_improvements.md demands).

The roadmap's $686/$528 "recoverable" is an UPPER BOUND (losses saved only). This
replays each trade ONCE and computes BOTH outcomes on the same tick path:
  - baseline: original SL / TP
  - BE: once favorable >= be_trig, move stop to entry (breakeven)
so it captures losses-saved AND winners-killed → the true NET delta. Walk-forward split.

Reuses the exact S1/S3 trade generation from winrate_improvement.py.
Run:  py be_netsim.py
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from winrate_improvement import (load_m1, build_m5, load_ticks, detect_s1, detect_s3,
                                 CONTRACT, LOTS, COMMON)


def replay_dual(ticks, sigs, lots, be_trig, be_buf=0.0):
    """Each trade gets pnl_base and pnl_be from the same tick walk."""
    ppp = lots * CONTRACT
    done, units = [], []
    it = iter(sorted(sigs, key=lambda x: x["fire"])); pend = next(it, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            buy = (u["side"] == "BUY")
            fav = (bid - u["e"]) if buy else (u["e"] - ask)
            if fav >= be_trig:
                u["armed"] = True
            px_adverse = bid if buy else ask          # price that hits a long's SL / short's SL
            # baseline
            if not u["bdone"]:
                if buy and bid <= u["e"] - u["sl"]:   u["pb"] = -u["sl"]*ppp; u["bdone"]=True
                elif buy and bid >= u["e"] + u["tp"]: u["pb"] = u["tp"]*ppp;  u["bdone"]=True
                elif (not buy) and ask >= u["e"] + u["sl"]: u["pb"] = -u["sl"]*ppp; u["bdone"]=True
                elif (not buy) and ask <= u["e"] - u["tp"]: u["pb"] = u["tp"]*ppp;  u["bdone"]=True
            # BE variant
            if not u["edone"]:
                be_stop = u["e"] + be_buf if buy else u["e"] - be_buf
                if u["armed"] and buy and bid <= be_stop:        u["pe"] = (be_stop-u["e"])*ppp; u["edone"]=True
                elif u["armed"] and (not buy) and ask >= be_stop: u["pe"] = (u["e"]-be_stop)*ppp; u["edone"]=True
                elif buy and bid <= u["e"] - u["sl"]:   u["pe"] = -u["sl"]*ppp; u["edone"]=True
                elif buy and bid >= u["e"] + u["tp"]:   u["pe"] = u["tp"]*ppp;  u["edone"]=True
                elif (not buy) and ask >= u["e"] + u["sl"]: u["pe"] = -u["sl"]*ppp; u["edone"]=True
                elif (not buy) and ask <= u["e"] - u["tp"]: u["pe"] = u["tp"]*ppp;  u["edone"]=True
            if u["bdone"] and u["edone"]:
                done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"]=="BUY" else bid
            units.append({**pend, "e": e, "armed": False, "bdone": False, "edone": False,
                          "pb": None, "pe": None})
            pend = next(it, None)
    last = ticks[-1]
    for u in units:
        p = ((last["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-last["ask"]))*ppp
        if not u["bdone"]: u["pb"] = p
        if not u["edone"]: u["pe"] = p
        done.append(u)
    return done


def main():
    m1 = load_m1(); m5 = build_m5(m1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    cache, days = {}, []
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]; tks = load_ticks(tf)
        if len(tks) < 500: continue
        cache[d] = tks; days.append(d)
    days.sort(); mid = len(days)//2
    train, oos = set(days[:mid]), set(days[mid:])
    print(f"  {len(days)} days | TRAIN {days[0]}→{days[mid-1]} | OOS {days[mid]}→{days[-1]}\n")

    for trig in (0.5, 1.0, 2.0):
        print(f"══ Breakeven trigger = +${trig:.2f} (move SL to entry once {trig:.2f} favorable) ══")
        for name, det in (("S1", detect_s1), ("S3", detect_s3)):
            agg = {}  # split -> [base, be, saved, killed, n]
            for day in days:
                sigs = det(m5, day)
                for u in replay_dual(cache[day], sigs, LOTS, trig):
                    sp = "TRAIN" if day in train else "OOS"
                    a = agg.setdefault(sp, [0,0,0,0,0])
                    a[0]+=u["pb"]; a[1]+=u["pe"]; a[4]+=1
                    if u["pb"]<-0.001 and u["pe"]>=-0.001: a[2]+=1     # loss saved
                    if u["pb"]>0.001 and u["pe"]<u["pb"]-0.001: a[3]+=1 # winner clipped
            tot_b = sum(agg[s][0] for s in agg); tot_e = sum(agg[s][1] for s in agg)
            print(f"  {name}: baseline ${tot_b:+8.1f} → BE ${tot_e:+8.1f}  (net {tot_e-tot_b:+.1f})")
            for sp in ("TRAIN","OOS"):
                if sp in agg:
                    b,e,sv,kl,n = agg[sp]
                    print(f"       {sp:<5} n={n:>3}  base ${b:+7.1f} → BE ${e:+7.1f}  Δ{e-b:+6.1f}  (saved {sv} losses, clipped {kl} winners)")
        print()


if __name__ == "__main__":
    main()
