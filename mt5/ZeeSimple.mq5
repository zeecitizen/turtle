//+------------------------------------------------------------------+
//|  ZeeSimple.mq5 — EVERY RETRACEMENT, tiny losses, Feb-11 tempo    |
//|                                                                  |
//|  Zee, 2026-08-17: "let's create a new EA from scratch, wherein   |
//|  everything is simplified. any law that cuts off too many trades |
//|  should be skipped, and then we find the winrate we can achieve..|
//|  the losses are little and too less compared to the wins. the    |
//|  losses are near about 2 USD.. our current EA makes losses       |
//|  around 50 USD.. and this time we consider every single          |
//|  retracement, so its not just 6 setups per day but a frequency   |
//|  from this report attached"                                      |
//|                                                                  |
//|  THE TARGET SPEC (his real Feb-11 day, acct 5118408, 0.1 lots):  |
//|     69 trades · 94.2% · avg win 12.93 · avg loss -1.32 (9.8:1)   |
//|     holds 6 seconds to 3 minutes; the one bad cluster was        |
//|     scratched at -0.17 pts after 25 min. THE CUT IS THE SPEC.    |
//|                                                                  |
//|  DESIGN, and what was deliberately left OUT:                     |
//|   - NO UHV requirement. The UHV hunt is what pins ZeeUHV at      |
//|     3-6 setups/day. Here the trigger is the retracement itself:  |
//|     a counter-trend candle, then a trend-colored candle closing  |
//|     back beyond it. That happens dozens of times a day.          |
//|   - NO diamonds, no stacking ladder, no conviction laws. One     |
//|     size. Laws exist only as OPTIONAL inputs, all default OFF,   |
//|     per his rule: a law that cuts too many trades is skipped.    |
//|   - LOSSES ARE CAPPED TINY by a sub-point stop. His Feb-11       |
//|     losses were -0.13 pts; a mechanical clone cannot read the    |
//|     tape mid-candle, so the stop is the cut. Defaults are set    |
//|     from the 2026-08-17 rig sweep (see EA_SYSTEM_STATE / daily   |
//|     report of that date for the receipts).                       |
//|                                                                  |
//|  STANDING WARNING, written before the first backtest: the        |
//|  six-month post-mortem measured that Feb-11's 94% lived in the   |
//|  discretionary CUT, and six mechanical attempts failed to        |
//|  reproduce it. This is attempt seven, with its own receipts.     |
//|  Whatever the tester says, THAT is the number — not 94%.         |
//|                                                                  |
//|  ATTEMPT SEVEN'S RECEIPTS (2026-08-17, seven exits, real ticks): |
//|  every arm LOSES. Best (SL2/TP1/h120): 140-230 trades/day at     |
//|  50-56% WR, -$2.10/trade — five of six fortnights BANKRUPT the   |
//|  $4,123 tester account at 0.10 lots. The per-trade loss is       |
//|  roughly the SPREAD: an every-retracement trigger is ~a random   |
//|  entry (see NullEntry, §1.8 of the 13-Aug report), and 200       |
//|  random entries/day pay the broker 200 spreads with no edge to   |
//|  cover them. Frequency without selection is rent, not tempo.     |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude"
#property version   "1.01"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input group "── Identity ──"
input double InpLots        = 0.01; // SAFETY DEFAULT after the 2026-08-17 sweep: at 0.10 the
                                    // best exit tested still loses ~$2.10/trade at 170-230
                                    // trades/day. 0.01 caps the tuition while live-forward
                                    // evidence accumulates. Raise ONLY with new receipts.
input long   InpMagic       = 88111;

input group "── Trend (the only opinion this EA holds) ──"
input int    InpEmaFast     = 5;     // fast EMA on closes
input int    InpEmaSlow     = 20;    // slow EMA on closes
input bool   InpRequireTrend = true; // false = trade both colors of resumption blindly

input group "── Entry: every retracement resumption ──"
input int    InpTickets     = 2;     // tickets per signal (his Feb-11 fired in pairs)
input int    InpMaxOpen     = 2;     // concurrent setups
input int    InpCooldownBar = 0;     // 0 = every signal (his instruction)
input double InpMinBody     = 0.00;  // optional law, OFF: min body of resumption bar

input group "── Exit: the mechanical cut ──"
input double InpStopPts     = 2.0;   // best of 7 exits swept 2026-08-17 (still negative)
input double InpTargetPts   = 1.0;
input int    InpMaxHoldSec  = 120;   // his holds: 6s-3min. Scratch what has not worked.

input group "── Safety (not laws — plumbing) ──"
input double InpMaxSpread   = 0.50;  // refuse to enter into a blown-out spread
input int    InpMaxGapSec   = 300;   // never reason across a hole in the data
input bool   InpVerbose     = false;

int emaFastH = INVALID_HANDLE, emaSlowH = INVALID_HANDLE;
datetime g_lastBar = 0;
int      g_lastFireBar = -999999;

double bOpen (int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh (int k) { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow  (int k) { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
bool IsGreen(int k)  { return bClose(k) > bOpen(k); }
bool IsRed  (int k)  { return bClose(k) < bOpen(k); }

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   emaFastH = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   emaSlowH = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   if (emaFastH == INVALID_HANDLE || emaSlowH == INVALID_HANDLE) return INIT_FAILED;
   PrintFormat("[ZS] ZeeSimple v1.00 — EVERY retracement. SL %.2f / TP %.2f / hold %ds"
               " · %d ticket(s) · magic %d · trend %s",
               InpStopPts, InpTargetPts, InpMaxHoldSec, InpTickets, (int)InpMagic,
               InpRequireTrend ? "EMA5/20" : "OFF");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { PrintFormat("[ZS] deinit reason=%d", reason); }

double Ema(int handle, int shift)
{
   double b[1];
   if (CopyBuffer(handle, 0, shift, 1, b) != 1) return 0;
   return b[0];
}

int OpenSetups()
{
   // a "setup" = tickets sharing one fire second; count distinct open times
   datetime seen[]; int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      bool found = false;
      for (int j = 0; j < n; j++) if (MathAbs((long)(seen[j] - ot)) <= 2) { found = true; break; }
      if (!found) { ArrayResize(seen, n + 1); seen[n++] = ot; }
   }
   return n;
}

void CloseOverdue()
{
   if (InpMaxHoldSec <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (TimeCurrent() - opened >= InpMaxHoldSec)
         trade.PositionClose(t);
   }
}

void OnTick()
{
   CloseOverdue();

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_lastBar) return;              // act once per new bar
   g_lastBar = bt;

   // never reason across a data hole (weekend, disconnect)
   if (bt - iTime(_Symbol, PERIOD_CURRENT, 1) > 60 + InpMaxGapSec) return;

   int barIdx = iBars(_Symbol, PERIOD_CURRENT);
   if (InpCooldownBar > 0 && barIdx - g_lastFireBar < InpCooldownBar) return;
   if (OpenSetups() >= InpMaxOpen) return;

   // ── trend: one EMA cross, nothing more ─────────────────────────────────
   int side = 0;
   if (InpRequireTrend) {
      double f = Ema(emaFastH, 1), s = Ema(emaSlowH, 1);
      if (f <= 0 || s <= 0) return;
      side = (f > s) ? +1 : -1;
   }

   // ── THE ENTRY: a retracement candle, then the trend takes back over ────
   //  bar 2 = counter-trend color (the retracement — ANY of them, per Zee)
   //  bar 1 = trend color, closing BEYOND bar 2's extreme (the resumption)
   for (int try_side = (side != 0 ? side : +1);
        ;
        try_side = -try_side) {
      bool ok = false;
      if (try_side > 0)
         ok = IsRed(2) && IsGreen(1) && bClose(1) > bHigh(2);
      else
         ok = IsGreen(2) && IsRed(1) && bClose(1) < bLow(2);
      if (ok && InpMinBody > 0 && MathAbs(bClose(1) - bOpen(1)) < InpMinBody) ok = false;
      if (ok) { Fire(try_side); break; }
      if (side != 0) break;                 // trend given: only its side is tried
      if (try_side < 0) break;              // trendless: both sides tried once
   }
}

void Fire(int side)
{
   MqlTick tk;
   if (!SymbolInfoTick(_Symbol, tk)) return;
   if (tk.ask - tk.bid > InpMaxSpread) {
      if (InpVerbose) PrintFormat("[ZS] [BLOCKED] spread %.2f", tk.ask - tk.bid);
      return;
   }
   double px = (side > 0) ? tk.ask : tk.bid;
   double sl = (InpStopPts   > 0) ? (side > 0 ? px - InpStopPts   : px + InpStopPts)   : 0.0;
   double tp = (InpTargetPts > 0) ? (side > 0 ? px + InpTargetPts : px - InpTargetPts) : 0.0;
   string tag = (side > 0) ? "zs_buy" : "zs_sell";
   int placed = 0;
   for (int q = 0; q < MathMax(1, InpTickets); q++) {
      bool ok = (side > 0) ? trade.Buy (InpLots, _Symbol, 0, sl, tp, tag)
                           : trade.Sell(InpLots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      placed++;
   }
   if (placed > 0) {
      g_lastFireBar = iBars(_Symbol, PERIOD_CURRENT);
      PrintFormat("[ZS] %s @%.2f — %d ticket(s), every-retracement resumption",
                  side > 0 ? "BUY" : "SELL", px, placed);
   }
}

//+------------------------------------------------------------------+
//| Tester summary — trades/day and the honest win rate              |
//+------------------------------------------------------------------+
double OnTester()
{
   double wins = 0, losses = 0, wsum = 0, lsum = 0;
   datetime t0 = 0, t1 = 0;
   if (HistorySelect(0, TimeCurrent())) {
      int total = HistoryDealsTotal();
      for (int i = 0; i < total; i++) {
         ulong tk = HistoryDealGetTicket(i);
         if (tk == 0) continue;
         if (HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic) continue;
         double p = HistoryDealGetDouble(tk, DEAL_PROFIT)
                  + HistoryDealGetDouble(tk, DEAL_SWAP)
                  + HistoryDealGetDouble(tk, DEAL_COMMISSION);
         datetime dt = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         if (t0 == 0 || dt < t0) t0 = dt;
         if (dt > t1) t1 = dt;
         if (p > 0) { wins++;   wsum += p; }
         else       { losses++; lsum += p; }
      }
   }
   double n = wins + losses;
   double days = MathMax(1.0, (double)(t1 - t0) / 86400.0);
   if (n > 0)
      PrintFormat("[ZS] ==== %d trades (%.1f/day) · WR %.2f%% · avgW %.2f · avgL %.2f · net %.2f ====",
                  (int)n, n / days, 100.0 * wins / n,
                  wins > 0 ? wsum / wins : 0, losses > 0 ? lsum / losses : 0, wsum + lsum);
   return wsum + lsum;
}
//+------------------------------------------------------------------+
