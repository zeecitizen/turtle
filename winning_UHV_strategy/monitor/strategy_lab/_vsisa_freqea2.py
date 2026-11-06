"""VSISA_PULLBACKS defaults, wave 2 - combining the three levers that worked.

Wave 1, inside the high-frequency regime:
  no camel        6.63/day  +$22,566  halves 3.20/3.01   - MORE trades AND money AND
                                                           steadier halves (opposite of
                                                           its effect on the slow EA)
  ratchetStart1.5 5.21/day  +$22,763  45% WR, ratio 5.93 - the accuracy lever, best in
                                                           the regime
  fade 0.70/5     8.99/day  +$20,161  halves 2.46/2.35   - the frequency lever
  maxOpen         does NOT bind even here (930->947) and costs ratio. Left at 2.

Objective unchanged: the most trades per day that stays clearly profitable with BOTH
halves positive. Drawdown is deferred by Zee's explicit decision; a dead H2 is not.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
B={"InpBigAvg":"1.10","InpBigPct":"0.70","InpLowVolPct":"5.00","InpFakeBreak":"false"}
NC=dict(B,InpTrendTF='0'); R15={'InpRatchetStart':'1.50'}
FD={'InpFadePct':'0.70','InpFadeLook':'5'}
res=[evaluate('BASE both-bands',dict(B))]
res.append(evaluate('noCamel+ratchet1.5',dict(NC,**R15)))
res.append(evaluate('noCamel+fade',dict(NC,**FD)))
res.append(evaluate('ratchet1.5+fade',dict(B,**R15,**FD)))
res.append(evaluate('ALL THREE',dict(NC,**R15,**FD)))
res.append(evaluate('ALL THREE +2R',dict(NC,InpTargetR='2.0',**R15,**FD)))
# ridge on the accuracy lever - it is the one carrying the win rate
for r in ('1.00','1.25','1.75','2.00'):
    res.append(evaluate('ALL THREE ratchet %s'%r,dict(NC,InpRatchetStart=r,**FD)))
rep('VSISA_PULLBACKS defaults - combining the levers', res)
