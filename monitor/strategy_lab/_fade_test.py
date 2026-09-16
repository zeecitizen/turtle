"""LAW 14 — the fade, judged the same way everything else has been."""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
res=[evaluate('v1.20 SHIPPED (fade off)',{})]
for pct in ('0.90','0.80','0.70'):
    res.append(evaluate('fade<=%s look12'%pct,{'InpFadeMode':1,'InpFadePct':pct}))
res.append(evaluate('fade<=0.80 look6',{'InpFadeMode':1,'InpFadePct':'0.80','InpFadeLook':'6'}))
res.append(evaluate('fade<=0.80 look20',{'InpFadeMode':1,'InpFadePct':'0.80','InpFadeLook':'20'}))
res.append(evaluate('fade<=0.80 bigPct0.95',{'InpFadeMode':1,'InpFadePct':'0.80','InpFadeBigPct':'0.95'}))
report('LAW 14 — the green-fade entry, walk-forward', res)
