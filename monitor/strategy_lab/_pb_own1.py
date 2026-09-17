"""Own-money wave 1: the concurrency cap, and the exit.

InpMaxOpen=2 on an EA that finds 10.4 setups a day is the first suspect - on VSISA at 0.8
a day it was byte-identical at 3 and 4, but this EA is 13x busier and the cap should bind
hard. The exit is the second: the handoff notes ratchetStart alone bought 4 points of win
rate, and with the daily rule lifted the ratchet can be let run instead of locking early.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from pb_lab import evaluate, report
res=[evaluate('PB v1.00 SHIPPED',{})]
for m in ('4','8','15','30'):
    res.append(evaluate('maxOpen %s'%m,{'InpMaxOpen':m}))
for s in ('1.00','2.00','2.50'):
    res.append(evaluate('ratchetStart %s'%s,{'InpRatchetStart':s}))
for s in ('4.00','12.00'):
    res.append(evaluate('ratchetStep %s'%s,{'InpRatchetStep':s}))
res.append(evaluate('breakEven 1R',{'InpBreakEvenR':'1.0'}))
res.append(evaluate('targetR 5',{'InpTargetR':'5.0'}))
report('VSISA_Pullbacks - OWN MONEY wave 1 (concurrency + exit)', res)
