"""Task 4 — tuning the exit and the trend reading at the wick0 baseline.

Everything else tonight has been about which setups to TAKE. This is about what to do
with them once taken, re-tuned on top of the one change that has already proved itself
(InpWickMode 0), because the old values for these were chosen before the fake break,
the ratchet and the camel filter existed.
"""
import sys
sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report

B = {'InpWickMode': 0}
res = [evaluate('BASE wick0', B)]

# THE RATCHET. 2.0 was chosen before the camel filter cut the losers; the rung that is
# right when 51% of trades win need not be right at 61%.
for r in ('1.50', '2.50', '3.00'):
    res.append(evaluate('ratchet start %s' % r, dict(B, InpRatchetStart=r)))
res.append(evaluate('ratchet OFF', dict(B, InpRatchetStart='0')))

# THE TARGET. 5.0R was tuned with no trend filter and no ratchet at all.
for t in ('4.0', '6.0', '7.0'):
    res.append(evaluate('targetR %s' % t, dict(B, InpTargetR=t)))

# THE CAMEL ITSELF — how coarse a swing counts as structure.
for p in ('1', '3'):
    res.append(evaluate('camelPivot %s' % p, dict(B, InpCamelPivot=p)))
for l in ('60', '240'):
    res.append(evaluate('camelLook %s' % l, dict(B, InpCamelLook=l)))

report('TASK 4 — TUNING the exit and the trend, on top of wick0', res)
