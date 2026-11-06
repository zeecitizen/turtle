"""Saad_strategy_5min v1.00 -> v1.01: the Optuna winner (study saad5_janjun, trial 126) as defaults + named comments.
Zee 2026-10-13: "find a profitable variant of this EA on 5 minute timeframe using whatever tools you have"."""
import re
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_5min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


def default(name, val, note):
    global s
    pat = re.compile(rf"^(input\s+\w+\s+{name}\s*=\s*)([^;]+)(;\s*//[^\n]*)$", re.M)
    m = pat.search(s); assert m, name
    s = s[:m.start()] + m.group(1) + val + m.group(3) + f" [v1.01: {m.group(2).strip()} -> {val}{note}]" + s[m.end():]


rep('#property version   "1.00"', '#property version   "1.01"')
rep('#include <Trade/Trade.mqh>', '#include <Trade/Trade.mqh>\n#define EA_COMMENT "Saad5 v1.01"   // every order\'s comment names the EA + version')
rep('PrintFormat("[SAAD-5min] v1.00 %s', 'PrintFormat("[SAAD-5min] v1.01 %s')
rep('InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")', 'InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, EA_COMMENT + " BUY")')
rep('rideShort ? 0 : NormalizeDouble(tp, _Digits), "saad_short");', 'rideShort ? 0 : NormalizeDouble(tp, _Digits), EA_COMMENT + " SELL");')
for n, v, note in [("InpSlPips", "15", ""), ("InpMaxRiskUsd", "8.0", ""), ("InpChopEr", "0.06", ""), ("InpChopErLook", "40", ""),
                   ("InpMinRangeAtr", "1.10", ", only big setup candles"), ("InpWickMin", "0.35", ""), ("InpMaruBody", "0.58", ""),
                   ("InpHamRatio", "2.0", ""), ("InpBreakPips", "1", ""), ("InpLongTrailUsd", "4.0", ""), ("InpShortTrailUsd", "4.0", ""),
                   ("InpMinTpPips", "30", ""), ("InpSessFrom", "8", ", no new setups before broker hour 8"),
                   ("InpBuys", "false", ", SELL ONLY: longs lost about -$28k on M5 in testing")]:
    default(n, v, note)
old_head = s[:s.index("//+------------------------------------------------------------------+\n//| Saad_strategy_15min.mq5")]
new_head = """//+------------------------------------------------------------------+
//| Saad_strategy_5min.mq5  v1.01 (2026-10-13) - 5-MINUTE variant of   |
//| Saad_strategy_15min. Attach on XAUUSD M5 only. Magic 88320.        |
//| v1.01 = the best of ~150 Optuna trials (each a real MT5 test,      |
//| tuned on Jan-Jun only), checked on unseen Jul-Oct:                 |
//|   SELL ONLY, setup candle >= 1.1 x ATR, stop 15 pips, max risk $8, |
//|   $4 trail, first target >= 30 pips, no new setups before hour 8.  |
//| MT5, Axi real ticks, 1 lot, $25k, $4/lot:                          |
//|   Jan-Jun +$13,651 | Jul-Oct (unseen) +$16,505 | PF 1.26           |
//|   full Jan 6 - Oct 8 with random delays: +$32,992, DD $9.4k,       |
//|   5 of 10 months negative.                                         |
//| CAUTION: sells only, and gold FELL ~20% over the test year; the    |
//| same settings with buys allowed made only +$4,457 (longs lost).    |
//| In a rising gold market this EA will likely struggle. Small edge   |
//| (about 1/6 of the 15-min EA's profit). DEMO FIRST.                 |
//| v1.00 (rescaled v1.17) was not profitable: Jul-Oct -$27,816.       |
//+------------------------------------------------------------------+
"""
s = new_head + s[len(old_head):]
open(p, 'w', encoding='utf-8').write(s)
print('v1.01 written')
