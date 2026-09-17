"""The pullback path, tested with PARAMETERS before a line of EA code is written.

Zee told me to test my own proposal: a separate entry for pullback lows with its own
tighter stop, on the grounds that smaller risk per trade is the only lever that both adds
trades AND shrinks drawdown.

The data study (108 pullback candidates, 5 sessions) half-refuted it before this ran. The
tighter stop DOES survive - buffer 120->20 costs 5 points of stop-out and lifts median R
from 1.10 to 1.46. But risk only falls 464->364 points, because risk is dominated by the
distance from the reaction close down to its low, not by the buffer. And 40% reach-2R,
after the ~16-point haircut measured twice tonight, is ~24% - an expectancy of -0.28R at a
2R target.

So this does not deserve new code yet. Every ingredient already exists as an input:
InpFakeBreak=false admits the pullback population (it is the gate that rejected all 59
bottoms), InpSlBufPts is the buffer, InpMaxSlPts caps the risk, and InpTargetMode 0 +
InpTargetR banks at a fixed R instead of riding the ratchet. If the idea has anything in
it, it shows up here; if it does not, no code was written against a negative expectancy.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
V={"InpBigAvg":"1.10","InpBigPct":"0.70"}
P=dict(V,InpFakeBreak='false')          # admit the pullback population
res=[evaluate('v1.24 SHIPPED',dict(V)), evaluate('pullback pop, buf120',dict(P))]
# does the tighter stop shrink the drawdown the way the study implied
for b in ('20','40','60'):
    res.append(evaluate('pullback buf %s'%b,dict(P,InpSlBufPts=b)))
# cap the risk outright - the real "smaller loss per trade" lever
for m in ('400','500'):
    res.append(evaluate('pullback buf40 maxSl%s'%m,dict(P,InpSlBufPts='40',InpMaxSlPts=m)))
# the population's edge was reach-2R, which suits a fixed target, not the ratchet
res.append(evaluate('pullback 2R target',dict(P,InpSlBufPts='40',InpMaxSlPts='400',
                                              InpTargetR='2.0',InpRatchetStart='0')))
res.append(evaluate('pullback 3R target',dict(P,InpSlBufPts='40',InpMaxSlPts='400',
                                              InpTargetR='3.0',InpRatchetStart='0')))
res.append(evaluate('pullback 2R + ratchet',dict(P,InpSlBufPts='40',InpMaxSlPts='400',
                                                 InpTargetR='2.0')))
rep('The pullback path, approximated with parameters', res)
