"""Own-money wave 2: the ENTRY gates, now that concurrency and the exit are exhausted.

Wave 1 killed the concurrency theory (maxOpen 2->4 adds 65 trades of 1,864 and saturates)
and found the exit essentially optimal - only ratchetStep 12 helped, +3.3% for LESS
drawdown. Everything left is the entry, and with the funded rules off, a gate may now be
loosened even when it costs drawdown, provided expectancy holds up.

InpStrictDir is the interesting one: it demands every setup bar close its own way, which is
exactly the "consecutive campaign" Zee questioned months ago. On VSISA, InpSetupGaps failed
- but VSISA trades sweeps and this EA trades dips, a different population, and a result on
one population is not evidence about another (learned the hard way on the session filter).
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from pb_lab import evaluate, report
R12={'InpRatchetStep':'12.00'}          # wave 1's free gain, carried into every row
res=[evaluate('PB v1.00 SHIPPED',{}), evaluate('R12 (wave1 best)',dict(R12))]
# ratchet ridge - is 12 a hill or a notch
for s in ('16.00','20.00'):
    res.append(evaluate('R step %s'%s,{'InpRatchetStep':s}))
# the loud gate, again - it paid twice already
for a,b in (('1.00','0.60'),('0.90','0.50'),('1.20','0.80')):
    res.append(evaluate('loud %s/%s'%(a,b),dict(R12,InpBigAvg=a,InpBigPct=b)))
# the reaction's own quality
for v in ('0.25','0.15'):
    res.append(evaluate('bodyFrac %s'%v,dict(R12,InpBodyFrac=v)))
# the fade - this EA's main entry path
for p in ('0.80','0.90'):
    res.append(evaluate('fadePct %s'%p,dict(R12,InpFadePct=p)))
res.append(evaluate('fadeLook 7',dict(R12,InpFadeLook='7')))
# the campaign's shape - gaps and direction
res.append(evaluate('strictDir off',dict(R12,InpStrictDir='false')))
res.append(evaluate('setupGaps 1',dict(R12,InpSetupGaps='1')))
res.append(evaluate('bigMode 0',dict(R12,InpBigMode='0')))
# risk band - refuse fewer setups as "absurd"
res.append(evaluate('maxSl 1400',dict(R12,InpMaxSlPts='1400')))
report('VSISA_Pullbacks - OWN MONEY wave 2 (entry gates)', res)
