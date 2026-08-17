//+------------------------------------------------------------------+
//|  ZeeUHV_R1.mq5 — RUNG 1 of the ladder: every REAL retracement    |
//|                                                                  |
//|  Zee, 2026-08-18: "make an EA based on R1, call it ZeeUHV_R1.    |
//|  Look where R1 landed: 66 trades a day. Your Feb-11 was 69."     |
//|                                                                  |
//|  This is ZeeSimple v1.10 with RUNG 1 WELDED ON: the retracement  |
//|  must be REAL — a counter-trend run whose origin BODY-breaks an  |
//|  IMPULSE bar's extreme (label #e014 + Law 9), nothing else.      |
//|  EMA 5/20 trend · SL 2 / TP 1 / hold 120s · 2 tickets.           |
//|                                                                  |
//|  THE LADDER RECEIPTS THAT CREATED IT (six periods, real ticks,   |
//|  0.01 lots): 66.0 trades/day · WR 54.7% · -0.181/trade ·         |
//|  six-fortnight net -815.84. AUGUST IS POSITIVE (+27.34 = ~+270   |
//|  at 0.10); Mar/Apr/May/Jun negative. R1 is Feb-11's TEMPO in     |
//|  KIND tape — it is NOT yet an all-weather strategy. The missing  |
//|  piece is the REGIME GATE (open item #1). Until that exists,     |
//|  lots stay 0.01: this EA's job is live-forward EVIDENCE.         |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input group "── Identity ──"
input double InpLots        = 0.01; // SAFETY DEFAULT after the 2026-08-17 sweep: at 0.10 the
                                    // best exit tested still loses ~$2.10/trade at 170-230
                                    // trades/day. 0.01 caps the tuition while live-forward
                                    // evidence accumulates. Raise ONLY with new receipts.
input long   InpMagic       = 88121;

input group "── Trend (the only opinion this EA holds) ──"
input int    InpEmaFast     = 5;     // fast EMA on closes
input int    InpEmaSlow     = 20;    // slow EMA on closes
input bool   InpRequireTrend = true; // false = trade both colors of resumption blindly

input group "── Entry: every retracement resumption ──"
input int    InpTickets     = 2;     // tickets per signal (his Feb-11 fired in pairs)
input int    InpMaxOpen     = 2;     // concurrent setups
input int    InpCooldownBar = 0;     // 0 = every signal (his instruction)
input double InpMinBody     = 0.00;  // optional law, OFF: min body of resumption bar

input group "── THE LADDER (2026-08-18, Zee: 'add the laws back one rung at a time') ──"
// Each rung is a faithful port of a canonical ZeeUHV law, defaulted OFF so the live
// EA is unchanged. The ladder run measures trades/day vs expectancy at each rung to
// find the knee of the frequency-vs-edge curve between 230/day (no laws, ~random,
// pays spread rent) and ZeeUHV's 6/day (edge in kind regimes).
input bool   InpLawRetrace  = true;  // R1: REAL retracement — counter-run whose origin BODY-breaks
                                     //     an IMPULSE bar's extreme (#e014 + Law 9)
input bool   InpLawTrendStruct = false; // R2: trend by SWING STRUCTURE (HH+HL / LL+LH, pivots d=2),
                                     //     not just an EMA cross
input bool   InpLawQuietBreak = false; // R3: resumption bar QUIETER than the loudest retracement
                                     //     candle (UHV-lite: the volume law without 'ultra')

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
   PrintFormat("[R1] ZeeUHV_R1 v1.00 — EVERY retracement. SL %.2f / TP %.2f / hold %ds"
               " · %d ticket(s) · magic %d · trend %s",
               InpStopPts, InpTargetPts, InpMaxHoldSec, InpTickets, (int)InpMagic,
               InpRequireTrend ? "EMA5/20" : "OFF");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { PrintFormat("[R1] deinit reason=%d", reason); }

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

      // the retracement run: consecutive counter-trend candles ending at bar 2
      int rlen = 0;
      if (ok) for (int k = 2; k <= 22; k++) {
         if (try_side > 0 ? IsRed(k) : IsGreen(k)) rlen++;
         else break;
      }

      // ── R1: the retracement must be REAL (#e014 + Law 9) ─────────────────
      if (ok && InpLawRetrace) {
         int origin = 2 + rlen - 1;                       // oldest counter candle
         int ref = -1;                                    // the leg's impulse bar
         for (int j = origin + 1; j <= origin + 8; j++) {
            if (try_side > 0 ? IsGreen(j) : IsRed(j)) {
               if (try_side > 0 && bHigh(j) <= bHigh(j + 1)) continue;   // Law 9
               if (try_side < 0 && bLow(j)  >= bLow(j + 1))  continue;
               ref = j; break;
            }
         }
         if (ref < 0) ok = false;
         else {
            bool broke = false;                           // #e014: BODY breaks the impulse
            for (int k = 2; k <= origin; k++) {
               double blo = MathMin(bOpen(k), bClose(k));
               double bhi = MathMax(bOpen(k), bClose(k));
               if (try_side > 0 && blo < bLow(ref))  { broke = true; break; }
               if (try_side < 0 && bhi > bHigh(ref)) { broke = true; break; }
            }
            if (!broke) ok = false;
         }
      }

      // ── R2: trend by swing structure, not an EMA cross ───────────────────
      if (ok && InpLawTrendStruct) {
         double ph[2], pl[2]; int nh = 0, nl = 0;
         for (int k = 3; k <= 30 && (nh < 2 || nl < 2); k++) {
            bool isH = true, isL = true;
            for (int d = 1; d <= 2; d++) {
               if (bHigh(k) < bHigh(k - d) || bHigh(k) < bHigh(k + d)) isH = false;
               if (bLow(k)  > bLow(k - d)  || bLow(k)  > bLow(k + d))  isL = false;
            }
            if (isH && nh < 2) ph[nh++] = bHigh(k);
            if (isL && nl < 2) pl[nl++] = bLow(k);
         }
         if (nh < 2 || nl < 2) ok = false;
         else if (try_side > 0 && !(ph[0] > ph[1] && pl[0] > pl[1])) ok = false;
         else if (try_side < 0 && !(ph[0] < ph[1] && pl[0] < pl[1])) ok = false;
      }

      // ── R3: the resumption must be QUIETER than the retracement's loudest ─
      if (ok && InpLawQuietBreak) {
         long vmax = 0;
         for (int k = 2; k <= 2 + MathMax(0, rlen - 1); k++)
            vmax = MathMax(vmax, iVolume(_Symbol, PERIOD_CURRENT, k));
         if (iVolume(_Symbol, PERIOD_CURRENT, 1) >= vmax) ok = false;
      }

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
      if (InpVerbose) PrintFormat("[R1] [BLOCKED] spread %.2f", tk.ask - tk.bid);
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
      PrintFormat("[R1] %s @%.2f — %d ticket(s), every-retracement resumption",
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
      PrintFormat("[R1] ==== %d trades (%.1f/day) · WR %.2f%% · avgW %.2f · avgL %.2f · net %.2f ====",
                  (int)n, n / days, 100.0 * wins / n,
                  wins > 0 ? wsum / wins : 0, losses > 0 ? lsum / losses : 0, wsum + lsum);
   return wsum + lsum;
}
//+------------------------------------------------------------------+
