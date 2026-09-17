"""Ship-verify v1.24: the COMPILED binary, on its OWN defaults, must reproduce the test.

The .set cache trap means a recompile does not change what the tester uses, so a version
is not shipped until a run that passes NO overrides returns the number the experiment
promised. Expected: 143 trades, +$13,689, 51% WR, $778 DD.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
import vsisa_lab as V
from vsisa_lab import run, stats
V.SHIPPED={k:v for k,v in V.SHIPPED.items()}
V.SHIPPED['InpBigAvg']='1.10'; V.SHIPPED['InpBigPct']='0.70'
r=run({}, *V.FULL); st=stats(r) if r else None
print('report:',r)
print('got     : n %s net %+.0f wr %.0f%% dd %.0f' % (st['n'],st['net'],st['wr'],st['dd']) if st else 'NO TRADES')
print('expected: n 143 net +13689 wr 51% dd 778')
