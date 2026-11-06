"""Can the BUSY config be made to fit a funded account without losing its frequency?

Zee pushed back on my dismissal of LOUD + fade 0.70/look5. He is right that it deserves
this: at full lots it earns MORE per day than the v1.24 I shipped ($80.91 vs $76.25),
2.17 trades a day against 0.80, and its walk-forward halves are 5.57/5.30 where v1.24's
are a lopsided 6.58/12.09. The ONLY thing against it is $1,342 of drawdown against a 10K
account's $1,000 limit, which forces a resize down to 0.209 lots.

So the question is not "which is better at 0.28 lots" - it is whether the drawdown can be
cut to under $1,000 while KEEPING roughly two trades a day. If it can, the busy config
runs at full size and wins outright. InpDayLossStop exists for exactly this and has never
been swept.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
B={"InpBigAvg":"1.10","InpBigPct":"0.70","InpFadePct":"0.70","InpFadeLook":"5"}
res=[evaluate('v1.24 SHIPPED',{"InpBigAvg":"1.10","InpBigPct":"0.70"}),
     evaluate('BUSY fade0.70/5',dict(B))]
for d in ('200','300','400','600'):
    res.append(evaluate('BUSY dayLossStop %s'%d,dict(B,InpDayLossStop=d)))
res.append(evaluate('BUSY maxOpen 1',dict(B,InpMaxOpen='1')))
res.append(evaluate('BUSY maxSl 600',dict(B,InpMaxSlPts='600')))
res.append(evaluate('BUSY ratchetStart1.5',dict(B,InpRatchetStart='1.50')))
res.append(evaluate('BUSY dayLoss300+maxSl600',dict(B,InpDayLossStop='300',InpMaxSlPts='600')))
rep('Can the BUSY config fit $1,000 of drawdown and keep ~2 trades a day?', res)
