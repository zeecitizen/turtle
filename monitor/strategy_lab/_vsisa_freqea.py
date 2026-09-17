"""Choosing the defaults for VSISA_PULLBACKS - a SEPARATE, frequently-trading EA.

Zee, 2026-09-17: "we're not beating the live EA here. we want a separate EA based on
VSISA which trades more frequently. i know there's a drawdown thing going on .. maybe in
future days we'd find a hack to make it less drawdown or more accurate?"

A deliberate product decision: frequency now, drawdown later, on an EA that cannot hurt
the live one. So v1.24 is NOT the benchmark here. The objective is the most trades per day
that stays clearly profitable with BOTH walk-forward halves positive - robustness is the
one thing that cannot be deferred, because a config that dies in H2 is not a drawdown
problem, it is a non-edge.

Base = "BOTH bands": v1.24's loud gate, the quiet CAP lifted (InpLowVolPct 5.0, so
no-supply AND stopping-volume reactions both qualify), and InpFakeBreak off (the gate that
rejected all 59 chart bottoms - lifting it is what admits the pullback population).
930 trades, 5.18/day, +$19,755, halves 2.52/2.36.

InpMaxOpen is the headline test. It was byte-identical at 2/3/4 when the EA took 0.8
trades a day - it never bound. At 5/day it should, and a binding cap is discarded signals:
possibly the only lever tonight that adds trades WITHOUT adding drawdown.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
BASE={"InpBigAvg":"1.10","InpBigPct":"0.70","InpLowVolPct":"5.00","InpFakeBreak":"false"}
res=[evaluate('BASE both-bands',dict(BASE))]
# 1. does the concurrency cap bind now?
for m in ('3','4','6','10'):
    res.append(evaluate('maxOpen %s'%m,dict(BASE,InpMaxOpen=m)))
# 2. the trend reader, at this much higher rate
res.append(evaluate('no camel',dict(BASE,InpTrendTF='0')))
res.append(evaluate('camel M15',dict(BASE,InpTrendTF='15')))
res.append(evaluate('camel H1',dict(BASE,InpTrendTF='60')))
# 3. exit: a fast EA may prefer banking to riding
res.append(evaluate('2R target',dict(BASE,InpTargetR='2.0',InpRatchetStart='0')))
res.append(evaluate('3R target',dict(BASE,InpTargetR='3.0',InpRatchetStart='0')))
res.append(evaluate('ratchetStart 1.5',dict(BASE,InpRatchetStart='1.50')))
# 4. the fade, which doubled frequency on the slow EA
res.append(evaluate('+ fade0.70/5',dict(BASE,InpFadePct='0.70',InpFadeLook='5')))
rep('VSISA_PULLBACKS - picking defaults inside the HIGH-FREQUENCY regime', res)
