"""Build mt5/Saad_strategy_15min_pyramiding_max_3.mq5 (Zee 2026-10-13):
Saad_strategy_15min v1.17 (unchanged) + the scale-in pyramid exactly as tested in Saad_pyramid (report.md
sections 21-23), with the chosen settings as defaults: ATR(14) x 0.25 spacing, 5 tiers, add-ons x0.75, no
breakeven lock -> at most 1 + 0.75 + 0.56 + 0.42 + 0.32 = 3.05 lots ("max 3"). Own magic number 88330.
The pyramid code is copied verbatim from mt5/Saad_pyramid.mq5 so it is the code MT5 already judged."""
import re
SRC = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
PYR = r'C:\Users\zeesh\turtle\mt5\Saad_pyramid.mq5'
DST = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min_pyramiding_max_3.mq5'
s = open(SRC, encoding='utf-8').read()
p = open(PYR, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


engine = p[p.index("//--- scale-in pyramiding"):p.index("bool ModifySl(ulong t, double sl)")]
inputs = """//--- scale-in pyramiding (report.md sections 21-23; defaults = ATR 0.25x, 5 tiers, x0.75, no lock: +$479,815 at 1 lot, Jan 6 - Oct 8)
input bool   InpEnablePyramid = true; // InpEnablePyramid — scale-in pyramiding (anti-martingale): add to the trade as it moves our way
input double InpPyramidSpacing = 30;  // InpPyramidSpacing — pips beyond the last entry before the next add-on (used only when InpPyrSpacingAtr = 0)
input double InpPyramidMultiplier = 0.75; // InpPyramidMultiplier — add-on volume = this x the last position's volume (1 -> 0.75 -> 0.56 -> 0.42 -> 0.32)
input int    InpMaxTiers    = 5;      // InpMaxTiers — positions in total (base + add-ons): max about 3.05 lots at InpLots 1
input bool   InpPyrLockBe   = false;  // InpPyrLockBe — on each add-on move every stop to the basket's average entry (tested: costs most of the profit; keep OFF)
input double InpPyrBeBufPts = 20;     // InpPyrBeBufPts — buffer beyond the average entry, points (with InpPyrLockBe)
input double InpPyrSpacingAtr = 0.25; // InpPyrSpacingAtr — next add-on after this x ATR(14) beyond the last entry (0 = use InpPyramidSpacing pips)
input double InpPyrRiskPct = 0;       // InpPyrRiskPct — >0: add-on size = this % of equity / its $ risk (tested: worse; keep 0)
input double InpPyrMaxLots = 1.0;     // InpPyrMaxLots — cap for one add-on with InpPyrRiskPct
input double InpPyrTrailAtr = 0;      // InpPyrTrailAtr — >0: on each add-on trail every stop to price -/+ this x ATR (tested: worse; keep 0)
"""
rep("input double InpLots        = 1.00;", inputs + "input double InpLots        = 1.00;")
rep("input int    InpMagicNumber = 88302;  // InpMagicNumber — Saad_strategy [M15 variant: own magic, can run beside the M5 EA]",
    "input int    InpMagicNumber = 88330;  // InpMagicNumber — pyramiding_max_3: own magic (the plain 15-min EA is 88302)")
rep("      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;",
    "      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;\n"
    "      if (PositionGetString(POSITION_COMMENT) == \"saad_pyr\") continue;   // pyramiding add-on, managed by ManagePyramid()")
rep("int g_ctc = 0,", "int g_pyrAdds = 0, g_pyrLocks = 0; datetime g_pyrBlock = 0;\nint g_ctc = 0,")
rep("bool ModifySl(ulong t, double sl)", engine + "bool ModifySl(ulong t, double sl)")
rep("   ManageTick();\n", "   ManageTick();\n   ManagePyramid();\n")
rep('   PrintFormat("[SAAD] CTC breakevens %d', '   PrintFormat("[SAAD-PYR3] add-ons %d, basket locks %d", g_pyrAdds, g_pyrLocks);\n   PrintFormat("[SAAD] CTC breakevens %d')
rep('#property version   "1.17"', '#property version   "1.00"')
rep('PrintFormat("[SAAD-15min] v1.17 %s', 'PrintFormat("[SAAD-PYR3] v1.00 (Saad_strategy_15min v1.17 + pyramiding: ATR x%.2f, %d tiers, x%.2f) %s')
# the init print gets three extra values in front of its existing arguments
m = re.search(r'PrintFormat\("\[SAAD-PYR3\] v1\.00 \(Saad_strategy_15min v1\.17 \+ pyramiding: ATR x%\.2f, %d tiers, x%\.2f\) %s[^"]*",\s*', s)
s = s[:m.end()] + "InpPyrSpacingAtr, InpMaxTiers, InpPyramidMultiplier, " + s[m.end():]
header = """//+------------------------------------------------------------------+
//| Saad_strategy_15min_pyramiding_max_3.mq5  v1.00  (2026-10-13)     |
//| = Saad_strategy_15min v1.17, unchanged, PLUS scale-in pyramiding: |
//|   when the trade moves 0.25 x ATR(14) beyond the last entry, add  |
//|   0.75 x the last position's lots, up to 5 positions (about 3.05  |
//|   lots at InpLots 1). Add-ons carry the base trade's stop and     |
//|   close with it; no breakeven lock. Magic 88330.                  |
//| MT5 (Axi real ticks, 1 lot, $25k, Jan 6-Oct 8 2026, 200 ms):      |
//|   +$479,815 | max DD $41.8k | worst day -$12,338 | 0 losing months |
//|   Jan-Jun +$320,169, Jul-Oct +$159,646. Plain v1.17 at 3 lots      |
//|   makes more for the same risk (report.md section 23) - this EA   |
//|   exists because Zee chose it. Demo first; needs a big account.   |
//+------------------------------------------------------------------+
"""
s = header + s
open(DST, 'w', encoding='utf-8').write(s)
print('wrote', DST)
