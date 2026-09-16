"""Task 7 - the final combination, and its neighbours, to prove it is a plateau."""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
B={'InpWickMode':0}
res=[evaluate('v1.19 SHIPPED',{}),
     evaluate('wick0 only',B),
     evaluate('BEST: w0+sw6+st2+t10',dict(B,InpSwingMin='6',InpRatchetStep='2.0',InpTargetR='10.0'))]
# neighbours on each axis - a plateau survives them, a spike does not
for s in ('1.50','2.50','3.00'):
    res.append(evaluate('  step %s'%s,dict(B,InpSwingMin='6',InpRatchetStep=s,InpTargetR='10.0')))
for sm in ('5','8','10'):
    res.append(evaluate('  swingMin %s'%sm,dict(B,InpSwingMin=sm,InpRatchetStep='2.0',InpTargetR='10.0')))
for t in ('8.0','12.0'):
    res.append(evaluate('  targetR %s'%t,dict(B,InpSwingMin='6',InpRatchetStep='2.0',InpTargetR=t)))
for r in ('1.75','2.25'):
    res.append(evaluate('  ratchetStart %s'%r,dict(B,InpSwingMin='6',InpRatchetStep='2.0',InpTargetR='10.0',InpRatchetStart=r)))
report('TASK 7 - the night\'s best config, and whether its neighbours agree', res)
