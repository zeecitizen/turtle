"""Task 6 — the ratchet IS the exit, so tune it as one; then combine the night's winners.

Discovery that forced this file: over the full window all 62 trades close at the STOP and
not one reaches the target. The ratchet locks at 5R exactly where the 5R target sits, so
the target can never pay out - it is decorative, which is why InpTargetR 4/5/6/7 returned
identical numbers. The trailing step is therefore the only exit parameter that matters.
"""
import sys
sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')
from vsisa_lab import evaluate, report

B = {'InpWickMode': 0}
res = [evaluate('BASE wick0 (step 1.0)', B)]

# THE STEP — how much room the trade is given between locks.
for s in ('0.50', '0.75', '1.50', '2.00'):
    res.append(evaluate('ratchet step %s' % s, dict(B, InpRatchetStep=s)))

# A higher ceiling, now that we know the ratchet - not the target - does the exiting.
res.append(evaluate('step 1.0 + targetR 10', dict(B, InpTargetR='10.0')))
res.append(evaluate('step 2.0 + targetR 10', dict(B, InpRatchetStep='2.0', InpTargetR='10.0')))

# COMBINING the night's other marginal winners with wick0.
res.append(evaluate('wick0 + swingMin 6', dict(B, InpSwingMin='6')))
res.append(evaluate('wick0 + camelPivot 3', dict(B, InpCamelPivot='3')))
res.append(evaluate('wick0 + swing6 + pivot3', dict(B, InpSwingMin='6', InpCamelPivot='3')))
res.append(evaluate('wick0 + swing6 + step2', dict(B, InpSwingMin='6', InpRatchetStep='2.0')))

report('TASK 6 — the ratchet as the real exit, and the night\'s winners combined', res)
