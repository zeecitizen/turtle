"""The trend reader, measured in the Diamond — 9 days, full window only.

Scope cut deliberately: the EA reloads the whole 743 KB OANDA table every simulated
minute, so a 6-week M1 run costs ~43,000 file reads and about 50 minutes. Five configs
x three windows would have run past breakfast. This is the headline question - does the
camel reading beat the stale-pivot one IN THE DIAMOND - on the window the smoke test
proved costs ~13 minutes.
"""
import sys
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
from diamond_lab import evaluate, report
W=('2026.09.08','2026.09.17')
import diamond_lab as D
D.FULL=W
res=[evaluate('mode 0 TrendNow SHIPPED',{'InpTrendMode':0},halves=False),
     evaluate('mode 1 CAMEL broke_top',{'InpTrendMode':1,'InpHighTest':1},halves=False),
     evaluate('mode 2 EMA slope',{'InpTrendMode':2},halves=False)]
report('Diamond trend reader — 8-17 Sep, real ticks, every input pinned', res)
