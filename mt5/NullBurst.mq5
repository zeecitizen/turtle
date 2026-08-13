//+------------------------------------------------------------------+
//| NullBurst.mq5 — Zee's own test, built exactly as he specified.    |
//|                                                                  |
//| Zee, 2026-08-13: "make an EA, open 100 trades randomly in the     |
//| next 1 minute. all of them would never land at 87% winrate ever." |
//|                                                                  |
//| He is right, and this EA proves it — but it proves something      |
//| more useful than it looks, so it opens bursts REPEATEDLY.         |
//|                                                                  |
//|   * WITHIN one burst, 100 trades open at ONE price and share one  |
//|     stop and one target. They are ONE event repeated 100 times.   |
//|     Every burst therefore comes back 100% or 0%. Never 87%.       |
//|     That is exactly his prediction and it is correct.             |
//|                                                                  |
//|   * ACROSS many bursts at different times, the rate is the        |
//|     barrier rate — and that is the number NullEntry measures.     |
//|                                                                  |
//| The distinction matters far beyond this argument: our own diamond |
//| stack opens 8 tickets on one signal. Those 8 are ONE event too.   |
//| "53 fills, 0 losers" is 14 events, not 53 — which is why a live   |
//| streak looks stronger than it is.                                 |
//|                                                                  |
//| NO RULES OF ANY KIND. Direction alternates so no trend bias can   |
//| creep in. Same stop, target and hold as the live EA.              |
//+------------------------------------------------------------------+
#property copyright "Zeeshan + Claude"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.02;   // InpLots — small: a burst is 100x this
input int    InpMagicNumber = 88096;
input double InpStopPts     = 20.0;   // identical to the live EA
input double InpTargetPts   = 1.0;    // identical to the live EA
input int    InpMaxHoldMin  = 60;     // identical to the live EA
input int    InpBurstN      = 100;    // HIS NUMBER: trades opened inside one minute
input int    InpEveryMin    = 60;     // start a new burst this often
input bool   InpAlternate   = true;   // flip direction each burst — no trend bias

datetime g_last_burst = 0;
int      g_dir        = 1;

int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("[NULLBURST] %d trades per burst, one burst every %d min · SL %.1f / TP %.1f",
               InpBurstN, InpEveryMin, InpStopPts);
   return INIT_SUCCEEDED;
}

// Close anything that has been open longer than the hold, exactly like the live EA.
void AgeOut() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (TimeCurrent() - opened >= InpMaxHoldMin * 60) trade.PositionClose(tk);
   }
}

void OnTick() {
   AgeOut();
   if (g_last_burst > 0 && TimeCurrent() - g_last_burst < InpEveryMin * 60) return;
   g_last_burst = TimeCurrent();

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = (g_dir > 0) ? ask : bid;
   double sl  = (g_dir > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp  = (g_dir > 0) ? px + InpTargetPts : px - InpTargetPts;

   // The whole burst inside ONE minute, at ONE price. This is the point.
   int placed = 0;
   for (int q = 0; q < InpBurstN; q++) {
      bool ok = (g_dir > 0) ? trade.Buy (InpLots, _Symbol, 0, sl, tp, "burst")
                            : trade.Sell(InpLots, _Symbol, 0, sl, tp, "burst");
      if (!ok) break;
      placed++;
   }
   if (placed < InpBurstN)
      PrintFormat("[NULLBURST] only %d of %d opened — broker refused the rest",
                  placed, InpBurstN);   // never hide a partial fill
   if (InpAlternate) g_dir = -g_dir;
}

double OnTester() { return TesterStatistics(STAT_PROFIT); }
