"""Diamond, Zee's real brief: MAXIMISE PROFIT PER DAY, keep the frequency, a low win
rate is acceptable.

2026-09-17 going to bed: "for the UHV EA.. i want you to find a configuration of TP/SL
that retains the frequency of trades and its ok to not have a very high winrate as long
as we're profitable .. try to maximize the profit per day".

What the geometry run already answered: his 1:2-with-breakeven idea keeps all 82 trades
but takes 90% WR to 54% and +$484 to +$200. So the R-multiple target is not the way in.
That leaves the thing nobody has swept — the FLAT target against the flat 20-point stop.
TP 1 point is what makes 90% possible and also what makes the geometry absurd; every
value between 1 and 20 is unexplored, and one of them maximises money per day rather
than wins per trade.

FREQUENCY IS A CONSTRAINT HERE, NOT A METRIC. Mode 0 takes ~158 trades and mode 1 ~82,
so the trend filter that won last week is itself in tension with tonight's brief; it is
re-examined under the new objective rather than assumed.

Ranked on net per TRADING DAY. Drawdown is printed beside it because a funded account
dies on drawdown, not on a bad average.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
import diamond_lab as D
from diamond_lab import evaluate
D.FULL=("2026.09.08","2026.09.17"); DAYS=7.0
CAMEL={"InpTrendMode":1,"InpHighTest":1}
res=[]
# B FROM THE GEOMETRY RUN RETURNED NO TRADES while its no-breakeven twin took 82. That is
# a harness fault, not a verdict on his rule, so it is re-run here first - the breakeven
# question stays open until this row prints.
res.append(evaluate("B RERUN struct+2R+BE1", dict(CAMEL, InpSlMode=1, InpTargetR="2.0",
                                                  InpBreakEvenR="1.0"), halves=False))
for tp in ("1.0","3.0","5.0","10.0"):
    res.append(evaluate("camel TP%s/SL20"%tp, dict(CAMEL,InpTargetPts=tp), halves=False))
res.append(evaluate("mode0 TP1/SL20 (freq)", {"InpTrendMode":0}, halves=False))
res.append(evaluate("mode0 TP5/SL20 (freq)", {"InpTrendMode":0,"InpTargetPts":"5.0"}, halves=False))
print("\n"+"="*96); print("Diamond — profit per DAY (8-17 Sep real ticks, %.0f trading days)"%DAYS); print("="*96)
print("%-24s | %8s | %6s | %7s | %6s | %3s | %7s"%('config','net','trades','$/day','tr/day','WR','maxDD'))
print("-"*96)
for e in res:
    if e:
        f=e['full']
        print("%-24s | %+8.0f | %6d | %7.1f | %6.1f | %2.0f%% | $%-6.0f"
              %(e['name'][:24],f['net'],f['n'],f['net']/DAYS,f['n']/DAYS,f['wr'],f['dd']))
