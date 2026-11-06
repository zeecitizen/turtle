import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
res=[evaluate('v1.20 SHIPPED (fade off)',{})]
for pct in ('0.90','0.80','0.70'):
    res.append(evaluate('fade<=%s +sweep'%pct,{'InpFadeMode':1,'InpFadePct':pct}))
res.append(evaluate('fade<=0.80 look6 +sweep',{'InpFadeMode':1,'InpFadePct':'0.80','InpFadeLook':'6'}))
report('LAW 14 with the fake break applied to the fade path as well', res)
