"""VSISA wave 4 - the remaining gates, on top of the ridge-confirmed loud setting.

Wave 3 proved loud 1.10/0.70 is a ridge and that the EXIT has nothing left: step 12 is
byte-identical to step 8, targetR 15 moves nothing. So every remaining gain has to come
from the entry, and this is the last untested set of gates - the reaction's own quality
(body, quiet, spread) and the two structural readers (camel timeframe, swing length).

Each is moved ALONE on top of LOUD so a win can be attributed. The fade dial is included
at look 5 because 4 and 6 bracket a big jump in trade count and the middle was never run.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
L={"InpBigAvg":"1.10","InpBigPct":"0.70"}
res=[evaluate('v1.23 SHIPPED',{}), evaluate('LOUD (w3 confirmed)',dict(L))]
# the reaction candle's own quality gates
for v in ('0.25','0.45'):
    res.append(evaluate('LOUD bodyFrac %s'%v,dict(L,InpBodyFrac=v)))
for v in ('0.90','1.10'):
    res.append(evaluate('LOUD lowVolPct %s'%v,dict(L,InpLowVolPct=v)))
# the structure readers
res.append(evaluate('LOUD no camel',dict(L,InpTrendTF='0')))
res.append(evaluate('LOUD camel H1',dict(L,InpTrendTF='60')))
res.append(evaluate('LOUD camelPivot 3',dict(L,InpCamelPivot='3')))
res.append(evaluate('LOUD swingMin 3',dict(L,InpSwingMin='3')))
res.append(evaluate('LOUD setupMax 14',dict(L,InpSetupMax='14')))
res.append(evaluate('LOUD setupGaps 1',dict(L,InpSetupGaps='1')))
# the frequency dial, middle value
res.append(evaluate('LOUD + fade0.65/5',dict(L,InpFadePct='0.65',InpFadeLook='5')))
res.append(evaluate('LOUD + fadeBig 0.70',dict(L,InpFadePct='0.65',InpFadeBigPct='0.70')))
rep('VSISA wave 4 - the last gates, on the confirmed loud ridge', res)
