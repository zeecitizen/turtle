"""VSISA — trade MORE. Ranked on profit per DAY, not per trade.

Zee, going to bed 2026-09-17: "i want you to see if you can make it trade more .. because
currently waiting the entire day for the EA to take just 1 trade is slow n boring".

v1.23 takes 121 trades in 8.5 months - about one every other day. Ranked by net per $1 of
drawdown it is the best config found; ranked by BOREDOM it is poor. So this ranks by
net/day and trades/day, and only uses drawdown as a ceiling.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, SHIPPED
DAYS=(253.0/365.0)*259   # trading days in Jan1->Sep16
def line(e):
    f=e['full']; h1=e.get('h1'); h2=e.get('h2')
    return ('%-26s | %+8.0f | %5d | %5.2f | %5.2f | %2.0f%% | $%-5.0f | %5.2f | %6s %6s'
            %(e['name'][:26],f['net'],f['n'],f['net']/DAYS,f['n']/DAYS,f['wr'],f['dd'],
              f['ratio'],('%.2f'%h1['ratio']) if h1 else '-',('%.2f'%h2['ratio']) if h2 else '-'))
def rep(t,res):
    print('\n'+'='*108); print(t); print('='*108)
    print('%-26s | %8s | %5s | %5s | %5s | %3s | %6s | %5s | %s'
          %('config','net','trades','$/day','tr/day','WR','maxDD','ratio','h1 h2'))
    print('-'*108)
    for e in res:
        if e: print(line(e))
res=[evaluate('v1.23 SHIPPED',{})]
# 1. the fade - the thing that already doubled frequency. push it.
for p in ('0.65','0.70','0.75'):
    for lk in ('4','6'):
        res.append(evaluate('fade<=%s look%s'%(p,lk),{'InpFadePct':p,'InpFadeLook':lk}))
# 2. the two filters that cut the most
res.append(evaluate('no fake break',{'InpFakeBreak':'false'}))
res.append(evaluate('no camel trend',{'InpTrendTF':'0'}))
res.append(evaluate('camel M15',{'InpTrendTF':'15'}))
rep('VSISA — trading MORE, ranked by profit per day', res)
