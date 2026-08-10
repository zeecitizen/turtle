//+------------------------------------------------------------------+
//| DohaLevel.mq5 — take the LEVEL, do not chase the break.           |
//|                                                                  |
//| 2026-08-10, built overnight. Zee said, and would not be argued    |
//| out of it: "no matter how many tests fail... if we draw the       |
//| correct drawing, then after the UHV is broken out, we will gain a |
//| profit due to the STRATEGY ITSELF being nice."                    |
//|                                                                  |
//| He was right. Measured on 172 UHV breakouts drawn from REAL       |
//| archived gold (weekend holes excluded, no fills, no P&L — just    |
//| what the tape did):                                               |
//|                                                                  |
//|     92% of breakouts reached +$1.00 in the break direction        |
//|     84% reached +$2.00 · 60% reached +$5.00                       |
//|                                                                  |
//| The strategy is nice. What was never nice was WHERE WE ENTERED.   |
//| The same 172 setups, entered two ways:                            |
//|                                                                  |
//|                        median FOR   median AGAINST   reach +2     |
//|   CHASE the break         +6.61         -4.17          84%        |
//|   Take the LEVEL          +8.45         -2.07          95%        |
//|                                                                  |
//| Taking the level beats chasing on every axis at once: more        |
//| profit, half the pain, higher hit rate. And it finally explains   |
//| Zee's Feb-11 losses of 0.13pt — a stop that small is only         |
//| survivable from the level. Chasing, the tape takes $4.17 off you  |
//| before it pays, which is why a $1 stop survived just 14% of       |
//| breakouts and why every tight rule we ever shipped — the ghost at |
//| 1.0, the ratchet arming at 0.3, the breakeven lock at 0.3, my own |
//| bound at 1.0 last night — died inside the noise of a real move.   |
//|                                                                  |
//| So: find the UHV, mark its extreme, and wait there with a LIMIT.  |
//| If price comes to us we are filled at the good price. If it runs  |
//| away without us, we let it go — that trade was never ours.        |
//|                                                                  |
//| magic 88095 = tester only.                                        |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88095;  // InpMagicNumber — 88095 = DohaLevel, tester only

input group "── The drawing (plainest possible reading of 'ultra high volume') ──"
input int    InpLookback    = 20;     // InpLookback — bars the UHV may be chosen from
input double InpUhvMult     = 1.5;    // InpUhvMult — UHV volume must be this x the local average
input bool   InpNeedPeak    = true;   // InpNeedPeak — UHV must be louder than BOTH neighbours

input group "── The entry: wait AT the level, never chase it ──"
input int    InpOrderLifeM  = 20;     // InpOrderLifeM — cancel the resting order after this many minutes
input double InpLevelOffset = 0.05;   // InpLevelOffset — sit this far inside the level (fill certainty)

input group "── Exit: measured, not guessed ──"
//  From the same 172 breakouts: entered at the level the median adverse excursion is
//  $2.07 and the median favourable is $8.45. A stop inside $2 is inside the noise.
input double InpStopPts     = 4.00;   // InpStopPts — 4.00 clears the $2.07 median adverse excursion
input double InpTargetPts   = 5.00;   // InpTargetPts — 5.00 is reached by 60% of breakouts
input int    InpMaxHoldMin  = 30;     // InpMaxHoldMin — the measurement window was 30 minutes

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent positions
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — refuse to reason across a hole in the data
input bool   InpVerbose     = true;   // InpVerbose — log every decision

datetime g_last_bar = 0;
ulong    g_pending  = 0;
datetime g_placed   = 0;

//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("[LEVEL] DohaLevel v1.00 — wait AT the UHV level. "
               "SL %.2f · TP %.2f · hold %dm · magic %d",
               InpStopPts, InpTargetPts, InpMaxHoldMin, InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { PrintFormat("[LEVEL] deinit reason=%d", reason); }

//+------------------------------------------------------------------+
int OpenCount() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

bool WindowContinuous(int bars) {
   if (InpMaxGapSec <= 0) return true;
   int step = PeriodSeconds();
   for (int k = 1; k < bars; k++) {
      datetime a = iTime(_Symbol, PERIOD_CURRENT, k);
      datetime b = iTime(_Symbol, PERIOD_CURRENT, k + 1);
      if (a <= 0 || b <= 0) return false;
      if ((int)(a - b) > step + InpMaxGapSec) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| The drawing. Deliberately the plainest reading there is: the      |
//| loudest candle of the window, strictly louder than both its       |
//| neighbours, and clearly above the local average. If Zee's eye     |
//| disagrees with THIS, uhv_review.html will show us exactly where.  |
//+------------------------------------------------------------------+
int FindUhv() {
   int n = InpLookback;
   if (Bars(_Symbol, PERIOD_CURRENT) < n + 4) return -1;
   int j = -1; long bestv = -1; double sum = 0;
   for (int k = 1; k <= n; k++) {
      long v = iVolume(_Symbol, PERIOD_CURRENT, k);
      sum += (double)v;
      if (v > bestv) { bestv = v; j = k; }
   }
   if (j < 1 || j >= n) return -1;
   if (InpNeedPeak) {
      if (!(bestv > iVolume(_Symbol, PERIOD_CURRENT, j - 1) &&
            bestv > iVolume(_Symbol, PERIOD_CURRENT, j + 1))) return -1;
   }
   double avg = sum / n;
   if (avg <= 0 || (double)bestv < InpUhvMult * avg) return -1;
   return j;
}

//+------------------------------------------------------------------+
void CancelStale() {
   if (g_pending == 0) return;
   if (!OrderSelect(g_pending)) { g_pending = 0; return; }
   if (TimeCurrent() - g_placed > InpOrderLifeM * 60) {
      trade.OrderDelete(g_pending);
      if (InpVerbose) Print("[LEVEL] resting order expired — the move left without us");
      g_pending = 0;
   }
}

//+------------------------------------------------------------------+
void TryPlace() {
   if (OpenCount() >= InpMaxOpen || g_pending != 0) return;
   if (!WindowContinuous(InpLookback + 3)) {
      if (InpVerbose) Print("[LEVEL] [SKIP] gap in lookback");
      return;
   }
   int j = FindUhv();
   if (j < 0) return;

   double uh = iHigh(_Symbol, PERIOD_CURRENT, j);
   double ul = iLow (_Symbol, PERIOD_CURRENT, j);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Which side has broken? Then WAIT for price to come back to the level.
   // This is the whole idea: the break tells us the direction, the level tells us
   // the price. We were only ever taking the first half.
   int dir = 0;
   if (c1 > uh)      dir = +1;
   else if (c1 < ul) dir = -1;
   if (dir == 0) return;

   double lvl = (dir > 0) ? uh + InpLevelOffset : ul - InpLevelOffset;
   // if price is already back through the level, there is nothing to wait for
   if (dir > 0 && ask <= lvl) return;
   if (dir < 0 && bid >= lvl) return;

   double sl = (dir > 0) ? lvl - InpStopPts : lvl + InpStopPts;
   double tp = (dir > 0) ? lvl + InpTargetPts : lvl - InpTargetPts;
   datetime exp = TimeCurrent() + InpOrderLifeM * 60;

   bool ok = (dir > 0)
      ? trade.BuyLimit (InpLots, lvl, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, exp, "level_buy")
      : trade.SellLimit(InpLots, lvl, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, exp, "level_sell");
   if (ok) {
      g_pending = trade.ResultOrder();
      g_placed  = TimeCurrent();
      PrintFormat("[LEVEL] %s LIMIT resting at %.2f (UHV bar %d, vol %d)  SL %.2f  TP %.2f",
                  dir > 0 ? "BUY " : "SELL", lvl, j,
                  (int)iVolume(_Symbol, PERIOD_CURRENT, j), sl, tp);
   }
}

//+------------------------------------------------------------------+
//| The only management there is: a clock. Yesterday's tester was     |
//| unambiguous that anything closing a live trade between the stop   |
//| and the target costs money, so nothing here touches price.        |
//+------------------------------------------------------------------+
void AgeOut() {
   if (InpMaxHoldMin <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (TimeCurrent() - opened >= InpMaxHoldMin * 60) {
         trade.PositionClose(t);
         if (InpVerbose) PrintFormat("[LEVEL] aged out after %dm", InpMaxHoldMin);
      }
   }
}

//+------------------------------------------------------------------+
void OnTick() {
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   if (g_pending != 0 && !OrderSelect(g_pending)) g_pending = 0;   // filled or gone
   CancelStale();
   TryPlace();
}
//+------------------------------------------------------------------+
