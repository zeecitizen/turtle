"""VSISA wave 3 — is the loosened LOUD gate a ridge or a spike, and does the exit still
have room?

Wave 2's winner, bigAvg 1.10 + bigPct 0.70, is +15% money and +19% trades over shipped
with the win rate intact. That is exactly the shape a NOISE SPIKE also has on one window,
so before it goes anywhere near the EA its neighbours have to be good too: a value that
works at 1.10 and fails at 1.05 and 1.15 is an artefact of this particular price history,
not a better reading of the law.

The second half answers the other thing he asked - "or if a change to TP/SL would bring
further profit". The ratchet, not the target, is what actually closes these trades (step
8 == step 20 proved one lock), so the rungs are swept here rather than InpTargetR alone.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
LOUD={"InpBigAvg":"1.10","InpBigPct":"0.70"}
FADE={"InpFadePct":"0.65","InpFadeLook":"4"}
res=[evaluate('v1.23 SHIPPED',{}), evaluate('LOUD 1.10/0.70 (w2 best)',dict(LOUD))]
# --- ridge test: the neighbours of the winner
for a in ('1.05','1.15','1.25'):
    res.append(evaluate('loud bigAvg %s'%a,dict(LOUD,InpBigAvg=a)))
for b in ('0.75','0.85'):
    res.append(evaluate('loud bigPct %s'%b,dict(LOUD,InpBigPct=b)))
# --- stack the two cheap frequency findings
res.append(evaluate('LOUD + fade0.65/4',dict(LOUD,**FADE)))
res.append(evaluate('LOUD + fade + sweep15',dict(LOUD,InpSweepLook='15',**FADE)))
# --- the exit: the ratchet is what really closes these
for st in ('1.50','2.50','3.00'):
    res.append(evaluate('LOUD ratchetStart %s'%st,dict(LOUD,InpRatchetStart=st)))
for sp in ('4.00','12.00'):
    res.append(evaluate('LOUD ratchetStep %s'%sp,dict(LOUD,InpRatchetStep=sp)))
res.append(evaluate('LOUD targetR 15',dict(LOUD,InpTargetR='15.0')))
rep('VSISA wave 3 — ridge test on the loud gate, and the exit', res)
