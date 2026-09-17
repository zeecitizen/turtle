"""STOPPING VOLUME: the second entry VSISA has never traded.

Born from Zee's instruction on 2026-09-17 to work backwards from the chart: "find out all
places where price rises .. apply the VSISA concepts .. see if you can manage more than 1
VSISA setups on the 5 minute timeframe".

The bottom study (59 pivot-low bottoms, 5 M5 sessions) said the law is inverted AT A
BOTTOM. A QUIET reaction is *no supply*, which belongs in an established uptrend; VSISA
only trades that one. At a bottom after heavy selling, the bars that actually produced the
move were LOUD and WIDE - *stopping volume*, demand overwhelming supply:

    quiet <=0.60 (no supply)      n= 5  reach2R  20%  medR 1.38
    quiet >=1.60 (very LOUD)      n= 2  reach2R 100%  medR 5.70
    quiet>=1.0 AND spread>=1.0    n=11  reach2R  54%  medR 3.62   <- 2.2 per session

Python's measured haircut is ~16 points of win rate, so 54% is a hypothesis, nothing more.
This is the promotion run.

NO NEW CODE IS NEEDED. InpMinVolPct is a FLOOR on the reaction's volume against the same
reference InpLowVolPct caps, and it has sat unused at 0.00 since it was added. Raising the
floor above 1.0 and lifting the cap out of the way expresses "loud reaction" exactly.
Also note the study's bottoms swept a 30-bar low 0 times in 59, so InpFakeBreak - the
filter that wins on the EA's OWN candidate set - must be off for this population to exist
at all. Both are tested.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from _vsisa_freq import rep
from vsisa_lab import evaluate
V124={"InpBigAvg":"1.10","InpBigPct":"0.70"}
# the loud-reaction band: floor at/above the reference, cap lifted out of the way
LOUD=dict(V124,InpMinVolPct="1.00",InpLowVolPct="5.00",InpReactSpread="1.00")
res=[evaluate('v1.24 SHIPPED',dict(V124))]
res.append(evaluate('STOPVOL fakeBreak off',dict(LOUD,InpFakeBreak='false')))
res.append(evaluate('STOPVOL fakeBreak on',dict(LOUD)))
# how high must the floor be
for f in ('0.80','1.20','1.60'):
    res.append(evaluate('STOPVOL floor %s'%f,dict(LOUD,InpMinVolPct=f,InpFakeBreak='false')))
# does the wide-spread half earn its place
res.append(evaluate('STOPVOL no spread test',dict(LOUD,InpReactSpread='0.00',InpFakeBreak='false')))
res.append(evaluate('STOPVOL spread 1.20',dict(LOUD,InpReactSpread='1.20',InpFakeBreak='false')))
# the WIDE BAND: keep no-supply AND take stopping volume - the most trades possible
res.append(evaluate('BOTH bands (no floor,cap5)',dict(V124,InpLowVolPct='5.00',InpFakeBreak='false')))
res.append(evaluate('BOTH bands + spread1.0',dict(V124,InpLowVolPct='5.00',InpReactSpread='1.00',InpFakeBreak='false')))
rep('STOPPING VOLUME - the loud reaction at a bottom, from the chart study', res)
