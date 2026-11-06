"""Is fade 0.60/look4 a narrow optimum or a spike? Its neighbours decide."""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report
res=[evaluate('v1.20 SHIPPED',{})]
for lk in ('3','4','5'):
    for pct in ('0.55','0.60','0.65'):
        res.append(evaluate('fade<=%s look%s'%(pct,lk),
                            {'InpFadeMode':1,'InpFadePct':pct,'InpFadeLook':lk}))
report('LAW 14 — fine grid around 0.60/look4', res)
