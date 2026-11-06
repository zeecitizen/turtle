"""VSISA frequency, wave 2 — the LOUD gate, the sweep length, and how many at once.

Wave 1 settled two things. Killing InpFakeBreak buys 4.7x the trades and +63% raw money,
but at $3,438 of drawdown it cannot be carried on a 10K funded account (10% = $1,000), so
after sizing to fit it is WORSE than shipped. And the fade loosened to 0.65/look4 buys
+46% trades for almost no drawdown. So frequency is affordable here — the question is
which gate sells it cheapest.

The funnel says the LOUD test is where the candidates die: 21,895 of 24,498 (89%) fail it.
That is InpBigPct 0.80 (>= this x swing max) and InpBigAvg 1.20 (>= this x average). This
wave asks each one what it costs to relax, instead of removing the filter wholesale.

RANKING. His brief is profit per DAY with frequency retained and a lower win rate
tolerated. But a funded account pays out of net-per-drawdown, so both are printed and
neither is allowed to hide the other.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
FADE = {"InpFadePct":"0.65","InpFadeLook":"4"}   # wave 1's cheap frequency
res=[evaluate('v1.23 SHIPPED',{}), evaluate('fade0.65/4 (wave1 best)',dict(FADE))]
# 1. the LOUD gate - 89% of candidates die here
for a in ('1.00','1.10'):
    res.append(evaluate('bigAvg %s'%a,{'InpBigAvg':a}))
for b in ('0.65','0.70'):
    res.append(evaluate('bigPct %s'%b,{'InpBigPct':b}))
res.append(evaluate('bigAvg1.10+bigPct0.70',{'InpBigAvg':'1.10','InpBigPct':'0.70'}))
# 2. a SHORTER sweep is an easier fake break - keep the filter, lower its bar
for s in ('10','15','60'):
    res.append(evaluate('sweepLook %s'%s,{'InpSweepLook':s}))
# 3. concurrency - trades currently refused because two are already open
for m in ('3','4'):
    res.append(evaluate('maxOpen %s'%m,{'InpMaxOpen':m}))
# 4. the cheap combination
res.append(evaluate('fade0.65/4 + maxOpen3',dict(FADE,InpMaxOpen='3')))
res.append(evaluate('fade0.65/4 + bigAvg1.10',dict(FADE,InpBigAvg='1.10')))
rep('VSISA wave 2 — what each gate charges for more trades', res)
