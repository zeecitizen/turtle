//+------------------------------------------------------------------+
//| NullEntry.mq5 — the control experiment. NO strategy at all.       |
//|                                                                  |
//| Zee, 2026-08-12: "but isnt it the fact: that your tests don't even |
//| apply to our trades, that you're unaware on why the trades win in  |
//| the first place?"                                                 |
//|                                                                  |
//| He is right, and this is the test that should have been run first. |
//|                                                                  |
//| Every sweep so far assumed the WIN RATE COMES FROM THE UHV        |
//| DETECTION. That has never been checked. And the exit geometry is   |
//| suspicious on its own:                                            |
//|                                                                  |
//|     target  1 point                                               |
//|     stop   20 points                                              |
//|     hold   60 minutes                                             |
//|                                                                  |
//| Gold moves a dollar constantly. Over an hour, price may touch     |
//| +1 point from ALMOST ANY entry before it falls 20. If that is so, |
//| a random entry would also win ~90%, the UHV rules would be         |
//| contributing nothing, and every parameter sweep I have run would   |
//| have been measuring the SHAPE OF THE EXIT rather than his strategy.|
//|                                                                  |
//| So this EA has no rules whatsoever. It opens a position every     |
//| InpEveryMin minutes, alternating direction so it cannot inherit a  |
//| trend bias, using the IDENTICAL stop, target and hold as ZeeUHV.   |
//|                                                                  |
//| HOW TO READ THE RESULT                                            |
//|   null ~= 93%   the geometry explains the win rate. The UHV rules  |
//|                 add nothing, and every sweep needs re-reading.     |
//|   null << 93%   the detection is doing real work and his strategy  |
//|                 is what makes the money.                           |
//|                                                                  |
//| Either answer is worth more than another parameter sweep.          |
//|                                                                  |
//| magic 88097 — testing only, never on a live chart.                 |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;
input int    InpMagicNumber = 88097;
input double InpStopPts     = 20.0;   // identical to ZeeUHV
input double InpTargetPts   = 1.0;    // identical to ZeeUHV
input int    InpMaxHoldMin  = 60;     // identical to ZeeUHV
input int    InpEveryMin    = 30;     // fire this often, whatever the market is doing
input bool   InpAlternate   = true;   // alternate buy/sell so no trend bias creeps in
input bool   InpVerbose     = false;

datetime g_last = 0;
bool     g_buy  = true;

int CountMine() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//| The same age-out ZeeUHV uses, so the only difference between the
//| two EAs is WHY the trade was opened.
void AgeOut() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (TimeCurrent() - opened >= InpMaxHoldMin * 60) trade.PositionClose(t);
   }
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(20);
   PrintFormat("[NULL] NullEntry — NO strategy. Fires every %d min, SL %.0f / TP %.0f / hold %d.",
               InpEveryMin, InpStopPts, InpTargetPts, InpMaxHoldMin);
   return INIT_SUCCEEDED;
}

void OnTick() {
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last) return;
   g_last = bt;
   if (CountMine() > 0) return;                       // one at a time, like ZeeUHV
   MqlDateTime dt;
   TimeToStruct(bt, dt);
   if ((dt.hour * 60 + dt.min) % InpEveryMin != 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool buy = InpAlternate ? g_buy : true;
   g_buy = !g_buy;
   double entry = buy ? ask : bid;
   double sl = buy ? entry - InpStopPts : entry + InpStopPts;
   double tp = buy ? entry + InpTargetPts : entry - InpTargetPts;
   bool ok = buy ? trade.Buy (InpLots, _Symbol, 0, sl, tp, "null_buy")
                 : trade.Sell(InpLots, _Symbol, 0, sl, tp, "null_sell");
   if (InpVerbose && ok)
      PrintFormat("[NULL] %s @ %.2f  SL %.2f  TP %.2f", buy ? "BUY" : "SELL", entry, sl, tp);
}

double OnTester() {
   double trades = TesterStatistics(STAT_TRADES);
   if (trades < 50) return 0.0;
   return (TesterStatistics(STAT_PROFIT_TRADES) / trades) * 100.0;
}
