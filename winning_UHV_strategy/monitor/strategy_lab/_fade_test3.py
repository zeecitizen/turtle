import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
res=[evaluate('v1.20 SHIPPED (fade off)',{})]
for pct in ('0.70','0.60','0.50'):
    for lk in ('4','6'):
        res.append(evaluate('fade<=%s look%s'%(pct,lk),
                            {'InpFadeMode':1,'InpFadePct':pct,'InpFadeLook':lk}))
res.append(evaluate('fade<=0.60 look6 big0.95',
                    {'InpFadeMode':1,'InpFadePct':'0.60','InpFadeLook':'6','InpFadeBigPct':'0.95'}))
report('LAW 14 — the tight corner: does the fade converge on something selective?', res)
