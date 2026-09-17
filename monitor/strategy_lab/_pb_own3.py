"""Own-money wave 3: combine the two REAL gains, and find out how much of maxSl is edge.

Wave 2's headline (maxSl 1400, +31% net) is mostly bigger risk per trade, not better
trading: net-per-drawdown moved 8.61 -> 8.82, about +2%. With own money and leverage that
gain is available anyway by raising lots, so it must not be double-counted as edge. The
ridge below shows whether ANY of it is real - if ratio stays flat as the band widens, it is
pure risk scaling and the right answer is to size up instead.

bigMode 0 is the genuine improvement: ratio 10.82, the lowest drawdown and shortest streak
in the whole wave, on FEWER trades. setupGaps 1 is Zee's own gapped-campaign idea, which
failed on VSISA and works here - a different population, as the session filter taught.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from pb_lab import evaluate, report
R12={'InpRatchetStep':'12.00'}
res=[evaluate('PB v1.00 SHIPPED',{}), evaluate('bigMode0 (best ratio)',dict(R12,InpBigMode='0'))]
# is the risk band edge, or just leverage? watch RATIO, not net
for m in ('1100','1800','2200'):
    res.append(evaluate('maxSl %s'%m,dict(R12,InpMaxSlPts=m)))
# the combinations
G={'InpSetupGaps':'1'}
res.append(evaluate('bigMode0 + gaps1',dict(R12,InpBigMode='0',**G)))
res.append(evaluate('bigMode0 + maxSl1400',dict(R12,InpBigMode='0',InpMaxSlPts='1400')))
res.append(evaluate('bigMode0+gaps+maxSl1400',dict(R12,InpBigMode='0',InpMaxSlPts='1400',**G)))
res.append(evaluate('gaps1 + maxSl1400',dict(R12,InpMaxSlPts='1400',**G)))
# bigMode 0 means EVERY setup bar must be loud - so its thresholds want re-tuning
for a in ('1.00','1.25'):
    res.append(evaluate('bigMode0 bigAvg %s'%a,dict(R12,InpBigMode='0',InpBigAvg=a)))
report('VSISA_Pullbacks - OWN MONEY wave 3 (combine, and test the risk band)', res)
