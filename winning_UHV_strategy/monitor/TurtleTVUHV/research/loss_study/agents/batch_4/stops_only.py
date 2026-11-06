"""stops_only.py - ANALYSIS (reads outcomes; not a rule): rescore rules on the population WITHOUT the 21 exit-reason-8 trades
(Friday positions the engine closed at the week's last tick - MT5 would carry them over the weekend), so only real stop-outs count
as losses. Also lists the reason-8 losses each rule removes and their $."""
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

names = sys.argv[1:] or [n for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith("r_")]
POP = [t for t in api.TRADES if t["why"] != 8]
W8 = [t for t in api.TRADES if t["why"] == 8]
print(f"population without reason-8: {len(POP)} trades, {sum(not t['win'] for t in POP)} stop-out losses; reason-8 trades: {len(W8)}, "
      f"$ {sum(t['pnl'] for t in W8):,.0f}")
for n in names:
    f = getattr(rules, n)
    res = {}
    for part, sel in (("all", lambda t: True), ("train", lambda t: t["t_in"] < api.SPLIT), ("test", lambda t: t["t_in"] >= api.SPLIT)):
        P = [t for t in POP if sel(t)]
        N, L = len(P), sum(not t["win"] for t in P)
        R = [t for t in P if f(api._blind(t), api.A)]
        rn, rl = len(R), sum(not t["win"] for t in R)
        res[part] = (rl, rn - rl, round((rl / rn) / (L / N), 2) if rn and L else None, -sum(t["pnl"] for t in R))
    r8 = [t for t in W8 if f(api._blind(t), api.A)]
    a, tr, te = res["all"], res["train"], res["test"]
    print(f"{n:30s} stop-outs only: losers {a[0]:3d} / winners {a[1]:4d}  lift x{a[2]}  | train x{tr[2]} ({tr[0]}L/{tr[1]}W)  test x{te[2]} ({te[0]}L/{te[1]}W)"
          f"  net {a[3]:+,.0f}$  || reason-8 removed {len(r8)} ($ {sum(t['pnl'] for t in r8):,.0f})")
