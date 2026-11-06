"""rw_null.py - is the secure zone better than a coin? Driftless random-walk loss probability per trade from its own geometry:
the bid must climb a = (fill - bid at the decision tick) + 0.1 pip to win and fall b = stop distance - (fill - bid) to lose:
p = a / (a + b). Uses the fill (outcome-side field) ONLY to build the null, never in a rule.  HYPOTHESIS ONLY."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402

PIP = 1e-4
for st in ("tight", "zee100", "secure", "base"):
    T = AT.STACKS[st]
    for part, f in (("all", lambda t: True), ("train", lambda t: t["t_dec"] < AT.SPLIT), ("test", lambda t: t["t_dec"] >= AT.SPLIT)):
        S = [t for t in T if f(t)]
        P, P2 = [], []
        for t in S:
            s = t["side"]
            sl = abs(t["fill"] - t["stop"]) / PIP
            a = (t["fill"] - t["brk_bid"]) * s / PIP + 0.1             # from the crossing bid up to the TP (fill + 0.1 pip, hit on the bid)
            b = sl - (t["fill"] - t["brk_bid"]) * s / PIP              # from the crossing bid down to the stop
            P.append(a / (a + b))
            a2 = t["trig_spread_pips"] + 0.1                            # decision-time-only version (spread at the breakout tick)
            P2.append(a2 / (a2 + sl))
        L = sum(1 for t in S if not t["win"])
        E, E2 = sum(P), sum(P2)
        sd = np.sqrt(sum(p * (1 - p) for p in P))
        print(f"{st:7s} {part:5s} n={len(S):5d} losses={L:4d} | RW-null expected {E:6.1f} (+-{sd:4.1f}) -> null WR {100*(1-E/len(S)):.2f}% vs real {100*(1-L/len(S)):.2f}% | "
              f"spread-only null {E2:6.1f} | mean a {np.mean([(t['fill']-t['brk_bid'])*t['side']/PIP+0.1 for t in S]):.2f}p  mean spread {np.mean([t['trig_spread_pips'] for t in S]):.2f}p")
