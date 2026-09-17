"""Zee's geometry for the Diamond: structural stop, 1:2 target, breakeven at 1:1.

2026-09-17, after seeing CamelTrend reach 89% and still sit on TP 1 point / SL 20:
"what if we set an SL below the last confirmed low and TP as 1:2 with breakeven at 1:1 ..
how does our UHV EA perform then? test"

Every piece already exists in the EA, and one of them is even labelled with his name for it:
    InpSlMode      1  = "defended structural low ... the deepest confirmed low"
    InpTargetR     2.0 = TP at this many R instead of the flat InpTargetPts
    InpBreakEvenR  1.0 = "at this R move the stop to entry (his 1:1 rule)"

WHY THIS MATTERS MORE THAN THE TREND SWITCH. v1.18 wins 89% of trades and still only made
+$404, because at TP 1 / SL 20 a single loss erases twenty wins. The trend filter removed
bad trades; this changes what a good one is worth. On VSISA the whole of last week's gain
came from exactly this move — the entry filters were nearly exhausted and the exit was not.

The runs are slow (the EA re-reads the whole OANDA table every simulated minute, ~13 min a
run), so this is deliberately five configs on the one window the trend test used, not a
grid. C isolates whether breakeven helps or hurts; E isolates the stop choice from the
target choice, so a win cannot be credited to the wrong half.
"""
import sys

sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')

import diamond_lab as D
from diamond_lab import evaluate, report

D.FULL = ("2026.09.08", "2026.09.17")
CAMEL = {"InpTrendMode": 1, "InpHighTest": 1}

res = [
    evaluate("A v1.18 shipped (TP1/SL20)", dict(CAMEL), halves=False),
    evaluate("B HIS ASK struct+2R+BE1", dict(CAMEL, InpSlMode=1, InpTargetR="2.0",
                                             InpBreakEvenR="1.0"), halves=False),
    evaluate("C struct+2R, no breakeven", dict(CAMEL, InpSlMode=1, InpTargetR="2.0",
                                               InpBreakEvenR="0.0"), halves=False),
    evaluate("D struct+3R+BE1", dict(CAMEL, InpSlMode=1, InpTargetR="3.0",
                                     InpBreakEvenR="1.0"), halves=False),
    evaluate("E retrace-stop+2R+BE1", dict(CAMEL, InpSlMode=0, InpTargetR="2.0",
                                           InpBreakEvenR="1.0"), halves=False),
]

report("Diamond geometry — structural stop, 1:2 target, breakeven 1:1 (8-17 Sep, real ticks)", res)
