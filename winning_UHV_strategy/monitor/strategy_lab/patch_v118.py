"""Saad_strategy_15min v1.17 -> v1.18: macro risk controls (Zee 2026-10-13 spec).
* Daily loss circuit breaker: once the day's equity (incl. open trades) is InpDayLossUsd below the
  day's starting equity -> close THIS EA's positions, drop the waiting setup, no new trades until the
  next server day. (InpEnableDayLoss; InpDayLossClose=false keeps the old v1.12 'just stop new trades'.)
* Friday close: from InpFridayCloseHour:InpFridayCloseMin server time on Friday -> close THIS EA's
  positions, drop the waiting setup, no new trades until the market reopens. Hour -1 = InpCloseLossMins
  minutes before the broker's own Friday close.
Differences from the pasted spec (on purpose): only positions with our magic + symbol are closed (never
another EA's or a manual trade); trade management keeps running after a trigger (the spec's early
return from OnTick would freeze trailing stops)."""
src = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
p = r'C:\Users\zeesh\turtle\mt5\Saad_v118test.mq5'   # TEST COPY ONLY - Zee 2026-10-13: "don't ship v1.18.. just test.."
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep('#property version   "1.17"', '#property version   "1.18"')
rep('PrintFormat("[SAAD-15min] v1.17 %s', 'PrintFormat("[SAAD-15min] v1.18 %s')
rep("input double InpDayLossUsd  = 0;      // InpDayLossUsd — no new trades today once the day lost this $ (0 = off)",
    """input bool   InpEnableDayLoss = true;  // InpEnableDayLoss — daily loss circuit breaker [v1.18, Zee]
input double InpDayLossUsd  = 1500;   // InpDayLossUsd — ...trips once the day is this $ down (equity incl. open trades vs the day's start) [v1.18: 0 -> 1500]
input bool   InpDayLossClose = true;  // InpDayLossClose — ...true: close this EA's trades + no new ones today · false: only no new trades (closed-trade P&L, the v1.12 rule)
input bool   InpFridayClose = true;   // InpFridayClose — Friday close: shut this EA's trades before the weekend, no new ones [v1.18, Zee; weekend gap cost -$2,612 on 24 Jul]
input int    InpFridayCloseHour = 21; // InpFridayCloseHour — ...from this server hour on Friday (-1 = InpCloseLossMins before the broker's close)
input int    InpFridayCloseMin  = 30; // InpFridayCloseMin — ...and minute""")

# guard state + function, placed before DayCloseCheck
rep("void DayCloseCheck()\n{", r'''//--- v1.18 macro risk controls
bool g_dayLossHit = false; int g_dayLossTrips = 0, g_friCloses = 0, g_friKey = -1;
void CloseOurs(string why)
{
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--)
      if (PositionSelectByTicket(g_pos[i].ticket)) { g_pos[i].why = why; trade.PositionClose(g_pos[i].ticket); }
   g_pSide = 0; g_aSide = 0;                          // no waiting setup / dip either
}
bool FridayLocked()
{
   if (!InpFridayClose) return false;
   MqlDateTime d; TimeToStruct(TimeCurrent(), d);
   if (d.day_of_week != 5) return false;
   if (InpFridayCloseHour < 0) return InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins;
   return d.hour > InpFridayCloseHour || (d.hour == InpFridayCloseHour && d.min >= InpFridayCloseMin);
}
// true = no new trades now
bool MacroGuards()
{
   if (InpEnableDayLoss && InpDayLossClose && InpDayLossUsd > 0 && g_dayStartEq > 0) {
      if (!g_dayLossHit && AccountInfoDouble(ACCOUNT_EQUITY) - g_dayStartEq <= -InpDayLossUsd) {
         g_dayLossHit = true; g_dayLossTrips++;
         Log(StringFormat("DAILY LOSS LIMIT: day is $%.2f down (limit $%.0f) -> closing this EA's trades, no new ones today",
                          AccountInfoDouble(ACCOUNT_EQUITY) - g_dayStartEq, InpDayLossUsd));
         CloseOurs("daily loss limit");
      }
      if (g_dayLossHit) return true;
   }
   if (FridayLocked()) {
      MqlDateTime d; TimeToStruct(TimeCurrent(), d);
      if (ArraySize(g_pos) > 0 || g_pSide != 0 || g_aSide != 0) {
         if (d.day_of_year != g_friKey && ArraySize(g_pos) > 0) { g_friKey = d.day_of_year; g_friCloses++; Log("FRIDAY CLOSE -> closing this EA's trades before the weekend"); }
         CloseOurs("Friday close");
      }
      return true;
   }
   return false;
}

void DayCloseCheck()
{''')
rep("   if (dn.day_of_year != g_dayKey) { g_dayKey = dn.day_of_year; g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY); }\n   SyncPos();\n   DayCloseCheck();",
    "   if (dn.day_of_year != g_dayKey) { g_dayKey = dn.day_of_year; g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY); g_dayLossHit = false; }\n"
    "   SyncPos();\n   bool macroLock = MacroGuards();\n   SyncPos();\n   DayCloseCheck();")
# no new setups / entries while locked
rep("         DetectSetup();\n      }\n   }\n   TryEntry();\n   TryDip();",
    "         if (!macroLock) DetectSetup();\n      }\n   }\n   if (!macroLock) { TryEntry(); TryDip(); }")
# the old block-only rule now honours the switch
rep("   if (InpDayLossUsd > 0 || InpDayTargetUsd > 0) {\n      double d = DayPnl();\n      if ((InpDayLossUsd > 0 && d <= -InpDayLossUsd)",
    "   if ((InpEnableDayLoss && InpDayLossUsd > 0) || InpDayTargetUsd > 0) {\n      double d = DayPnl();\n      if ((InpEnableDayLoss && InpDayLossUsd > 0 && d <= -InpDayLossUsd)")
rep('   PrintFormat("[SAAD] CTC breakevens %d',
    '   PrintFormat("[SAAD] v1.18: daily loss limit tripped %d days, Friday closes %d", g_dayLossTrips, g_friCloses);\n   PrintFormat("[SAAD] CTC breakevens %d')
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
