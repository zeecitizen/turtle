"""Task 8 - does the ratchet want to STOP trailing after the first rung?

The step improved monotonically 1.5 -> 3.0. A very large step means: lock 2R and never
lock again, i.e. the trailing BEYOND the first rung is what costs money. Pushing it until
it turns over answers whether the right rule is a trail or a single lock.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
B={'InpWickMode':0,'InpSwingMin':'6','InpTargetR':'10.0'}
res=[evaluate('step 2.0 (ref)',dict(B,InpRatchetStep='2.0')),
     evaluate('step 3.0',dict(B,InpRatchetStep='3.0'))]
for s in ('4.0','5.0','8.0','20.0'):
    res.append(evaluate('step %s'%s,dict(B,InpRatchetStep=s)))
# and the yardstick, at the best step found so far
for sm in ('4','5','7'):
    res.append(evaluate('swingMin %s + step8'%sm,dict(B,InpSwingMin=sm,InpRatchetStep='8.0')))
report('TASK 8 - is the RIGHT rule a trail, or one lock at 2R and hands off?', res)
