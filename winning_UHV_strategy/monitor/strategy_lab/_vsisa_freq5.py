"""VSISA wave 5 - ridge-test the new leader, then stack what is cheap.

Wave 4's LOUD + fade 0.65/look5 is the best money of the night (+$14,719) at 1.40 trades
a day, more than double shipped. But look4 gave 198 trades and look6 ALONE (without the
loosened loud gate) was poor, so look5 sits between a good neighbour and a bad one and
must be shown to be a hill rather than a lucky notch.

Then the stack. lowVolPct 1.10 and bodyFrac 0.25 each bought trades and money on their
own; gates that are individually cheap are not automatically cheap together, because
they compete for the same marginal setups. The combinations are measured, never assumed.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
L={"InpBigAvg":"1.10","InpBigPct":"0.70"}
F5=dict(L,InpFadePct='0.65',InpFadeLook='5')
res=[evaluate('v1.23 SHIPPED',{}), evaluate('LOUD+fade0.65/5 (w4)',dict(F5))]
# ridge around the leader
res.append(evaluate('fade look6',dict(F5,InpFadeLook='6')))
res.append(evaluate('fade pct0.60/5',dict(F5,InpFadePct='0.60')))
res.append(evaluate('fade pct0.70/5',dict(F5,InpFadePct='0.70')))
# stack the cheap gates onto the leader
res.append(evaluate('leader+lowVol1.10',dict(F5,InpLowVolPct='1.10')))
res.append(evaluate('leader+body0.25',dict(F5,InpBodyFrac='0.25')))
res.append(evaluate('leader+lowVol+body',dict(F5,InpLowVolPct='1.10',InpBodyFrac='0.25')))
# a calmer stack, no fade - for the 50%-winrate shape
res.append(evaluate('LOUD+lowVol+body',dict(L,InpLowVolPct='1.10',InpBodyFrac='0.25')))
rep('VSISA wave 5 - ridge on the leader, and the stacks', res)
