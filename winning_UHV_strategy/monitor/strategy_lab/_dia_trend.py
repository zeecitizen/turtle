"""InpTrendMode 0 vs 1 vs 2 in the Diamond itself — the test the source never had."""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from diamond_lab import evaluate, report
res=[evaluate('mode 0 TrendNow SHIPPED',{'InpTrendMode':0}),
     evaluate('mode 1 CAMEL broke_top',{'InpTrendMode':1,'InpHighTest':1}),
     evaluate('mode 1 CAMEL rising piv',{'InpTrendMode':1,'InpHighTest':0}),
     evaluate('mode 1 CAMEL either',{'InpTrendMode':1,'InpHighTest':2}),
     evaluate('mode 2 EMA slope',{'InpTrendMode':2})]
report('ZeeUHV_Diamond — the trend reader, measured IN THE DIAMOND (6 weeks, real ticks)', res)
