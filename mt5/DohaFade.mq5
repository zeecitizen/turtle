//+------------------------------------------------------------------+
//| DohaFade.mq5 — Zee buys WEAKNESS. Every engine we built buys      |
//|                STRENGTH. This one finally does what he does.      |
//|                                                                  |
//| 2026-08-10, built overnight while Zee slept, from his own Feb-11  |
//| entries measured against a random-moment null baseline:           |
//|                                                                  |
//|                     fades the move   buys cheap third   BOTH      |
//|   ZEE, 13 entries         69%              50%           50%      |
//|   random moments          46%              38%           18%      |
//|   S1Trader, 8 trades       0%              12%            0%      |
//|                                                                  |
//| Our UHV engine has never once done what he does half the time,    |
//| and it never can: its buy condition is close > UHV-high, which by |
//| construction means price is RISING when it buys. Zee buys while   |
//| price is still falling, in the cheap third of the hour's range.   |
//| That is why no exit tuning and no filter change could reproduce   |
//| his day — we were measuring the wrong animal.                     |
//|                                                                  |
//| THE SIGNATURE, stated plainly:                                    |
//|   BUY  when price sits in the CHEAP third of the last hour's      |
//|        range AND the last minute moved DOWN (we are catching it   |
//|        falling, not chasing it up)                                |
//|   SELL when the mirror is true                                    |
//|                                                                  |
//| Exits use tonight's tester verdict (project_exit_interference):   |
//| a structural stop and a structural target, and NOTHING that can   |
//| close a live trade in between — no ratchet, no breakeven lock.    |
//| Both were measured harmful on real spread and slippage.           |
//|                                                                  |
//| magic 88096 = tester only. Never confusable with a live fill.     |
//|                                                                  |
//| HONEST CAVEAT, because this EA was born from 13 entries: that is  |
//| a thin sample and the separation (0.66σ) is moderate. The only    |
//| thing that promotes this is MT5's own tester on Feb 11 — which is |
//| exactly what it is built to be run through.                       |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| BarVolume — the one call every volume rule must use.              |
//|                                                                  |
//| 2026-08-10, measured with TapeProbe on XAUUSD_REAL2:              |
//|     iVolume     : 4 4 4 4 4 4 4 4 4 4 4 4 4 4 4                   |
//|     iRealVolume : 572 454 270 174 312 305 366 672 331 438 ...     |
//|                                                                  |
//| The Strategy Tester OVERWRITES tick_volume with the number of     |
//| ticks it synthesised (4 per bar in 'OHLC M1' mode) but preserves  |
//| real_volume. Every rule we own asked iVolume(), so every rule was |
//| comparing 4 against 4 and no candle was ever louder than another. |
//| That is why NsndF11 reported signals=0, why S1Trader took 8       |
//| trades where the tape offers 263 UHV candidates, and why          |
//| DohaLevel placed nothing at all. They were not failing to find    |
//| setups. They were blind.                                          |
//|                                                                  |
//| real_volume first, tick_volume as the fallback: our custom        |
//| symbols carry the truth in real_volume, while a live broker feed  |
//| often reports real_volume 0 and keeps its count in tick_volume.   |
//| This one call is correct on both.                                 |
//+------------------------------------------------------------------+
long BarVolume(ENUM_TIMEFRAMES tf, int shift) {
   long rv = iRealVolume(_Symbol, tf, shift);
   if (rv > 0) return rv;
   return iVolume(_Symbol, tf, shift);
}

long BarVolume(int shift) { return BarVolume((ENUM_TIMEFRAMES)PERIOD_CURRENT, shift); }

CTrade trade;

input double InpLots         = 0.10;  // InpLots — lot size
input int    InpMagicNumber  = 88096; // InpMagicNumber — 88096 = DohaFade, tester only

input group "── THE SIGNATURE (measured from Zee's own Feb-11 entries) ──"
input int    InpRangeBars    = 60;    // InpRangeBars — the 'hour' whose range defines cheap/expensive
input double InpCheapPct     = 0.30;  // InpCheapPct — 0.30 measured best: keeps 6 of Zee's 13, cuts signals 569->131
input int    InpFadeBars     = 1;     // InpFadeBars — price must have moved AGAINST us over this many bars
input double InpMinFadePts   = 2.00;  // InpMinFadePts — 2.00 measured best. A shallow fade fires 4x more for no extra catch.

input group "── Confirmation (each OFF by default: prove it before believing it) ──"
input bool   InpNeedDeadVol  = false; // InpNeedDeadVol — LEAVE OFF: measured, it cuts Zee's coverage 6/13 -> 1/13
input double InpDeadVolRatio = 0.80;  // InpDeadVolRatio — 'quiet' = below this x the 20-bar average
input bool   InpNeedSweep    = false; // InpNeedSweep — require a sweep of the range extreme first

input group "── Exit (tester verdict 2026-08-10: stop + target, nothing between) ──"
input double InpSLBufferPts  = 2.0;   // InpSLBufferPts — stop beyond the structural extreme by this
input double InpTgtRR        = 1.0;   // InpTgtRR — target = this x the stop distance
input double InpMaxRiskPts   = 0.0;   // InpMaxRiskPts — 0 = off. >0 caps what a click may cost.

input group "── Housekeeping ──"
input int    InpCooldownBars = 3;     // InpCooldownBars — minimum bars between entries
input int    InpMaxOpen      = 1;     // InpMaxOpen — concurrent positions
input bool   InpVerbose      = true;  // InpVerbose — log every decision and every refusal
input int    InpMaxGapSec    = 300;   // InpMaxGapSec — refuse if the lookback contains a hole bigger than this (0=off)

datetime g_last_bar  = 0;
datetime g_last_fire = 0;

//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("[FADE] DohaFade v1.00 — Zee buys weakness. cheap<%.2f  fade>=%.2fpt  "
               "SL=%.1f  TP=%.1fxSL  magic=%d",
               InpCheapPct, InpMinFadePts, InpSLBufferPts, InpTgtRR, InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   PrintFormat("[FADE] deinit reason=%d", reason);
}

//+------------------------------------------------------------------+
int OpenCount() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| Where does price sit in the recent range? 0 = at the low.         |
//+------------------------------------------------------------------+
bool RangePos(double &pos, double &hi, double &lo) {
   int n = InpRangeBars;
   if (Bars(_Symbol, PERIOD_CURRENT) < n + 5) return false;
   hi = iHigh(_Symbol, PERIOD_CURRENT, iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, n, 1));
   lo = iLow (_Symbol, PERIOD_CURRENT, iLowest (_Symbol, PERIOD_CURRENT, MODE_LOW,  n, 1));
   if (hi <= lo) return false;
   pos = (iClose(_Symbol, PERIOD_CURRENT, 1) - lo) / (hi - lo);
   return true;
}

//+------------------------------------------------------------------+
//| Has price moved AGAINST the side we are about to take?            |
//| This is the heart of it: Zee is catching a falling knife on       |
//| purpose, where every engine we built waits for the knife to land  |
//| and bounce — by which time he is already in.                      |
//+------------------------------------------------------------------+
double FadeAmount(int dir) {
   int n = MathMax(1, InpFadeBars);
   double now  = iClose(_Symbol, PERIOD_CURRENT, 1);
   double then = iClose(_Symbol, PERIOD_CURRENT, 1 + n);
   double move = now - then;
   return (dir > 0) ? -move : move;      // positive = it moved against us = good
}

//+------------------------------------------------------------------+
bool QuietBar() {
   long v = BarVolume(1);
   double sum = 0;
   for (int k = 2; k <= 21; k++) sum += (double)BarVolume(k);
   double avg = sum / 20.0;
   return (avg > 0 && (double)v < InpDeadVolRatio * avg);
}

//+------------------------------------------------------------------+
bool SweptExtreme(int dir, double hi, double lo) {
   // did any of the last 5 bars poke beyond the range and close back inside?
   for (int k = 1; k <= 5; k++) {
      double H = iHigh(_Symbol, PERIOD_CURRENT, k);
      double L = iLow (_Symbol, PERIOD_CURRENT, k);
      double C = iClose(_Symbol, PERIOD_CURRENT, k);
      if (dir > 0 && L < lo && C > lo) return true;
      if (dir < 0 && H > hi && C < hi) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Is the window we are about to reason over CONTINUOUS?             |
//|                                                                  |
//| 2026-08-10: the first real-data run scored +$67.20 and the number |
//| was worthless. Our archive has holes — a weekend, a 15h outage —  |
//| and the EA read straight across them: price jumped 4245 -> 4338   |
//| over the weekend and it logged "faded 96.73pt", then held a trade |
//| 15 hours waiting for a gap to close. A backtest that reasons over |
//| a hole is measuring the hole, not the strategy.                   |
//+------------------------------------------------------------------+
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
void TryFire() {
   if (OpenCount() >= InpMaxOpen) return;
   if (!WindowContinuous(InpRangeBars + 2)) {
      if (InpVerbose) Print("[FADE] [SKIP] gap in lookback — refusing to reason across a hole");
      return;
   }
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBars * PeriodSeconds()) return;

   double pos, hi, lo;
   if (!RangePos(pos, hi, lo)) return;

   int dir = 0;
   if (pos <= InpCheapPct)             dir = +1;     // cheap -> he buys
   else if (pos >= 1.0 - InpCheapPct)  dir = -1;     // expensive -> he sells
   if (dir == 0) {
      if (InpVerbose) PrintFormat("[FADE] [SKIP] mid-range pos=%.2f", pos);
      return;
   }

   double fade = FadeAmount(dir);
   if (fade < InpMinFadePts) {
      if (InpVerbose) PrintFormat("[FADE] [SKIP] not fading (%.2fpt) pos=%.2f", fade, pos);
      return;
   }
   if (InpNeedDeadVol && !QuietBar()) {
      if (InpVerbose) Print("[FADE] [SKIP] bar not quiet");
      return;
   }
   if (InpNeedSweep && !SweptExtreme(dir, hi, lo)) {
      if (InpVerbose) Print("[FADE] [SKIP] no sweep");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = (dir > 0) ? ask : bid;

   // the structure says where we are wrong: the extreme of the range we faded into
   double sl  = (dir > 0) ? lo - InpSLBufferPts : hi + InpSLBufferPts;
   double dist = MathAbs(px - sl);
   if (dist <= 0) return;
   double tp  = (dir > 0) ? px + InpTgtRR * dist : px - InpTgtRR * dist;

   bool ok = (dir > 0) ? trade.Buy (InpLots, _Symbol, 0, sl, tp, "fade_buy")
                       : trade.Sell(InpLots, _Symbol, 0, sl, tp, "fade_sell");
   if (ok) {
      g_last_fire = TimeCurrent();
      PrintFormat("[FADE] %s @%.2f  pos=%.2f in [%.2f..%.2f]  faded %.2fpt  SL %.2f  TP %.2f",
                  dir > 0 ? "BUY " : "SELL", px, pos, lo, hi, fade, sl, tp);
   }
}

//+------------------------------------------------------------------+
//| The bound, if armed. Tonight's tester said a give-back rule and a |
//| breakeven lock both cost money, so there is deliberately NOTHING  |
//| here except a hard cap the user must switch on.                   |
//+------------------------------------------------------------------+
void Manage() {
   if (InpMaxRiskPts <= 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double e = PositionGetDouble(POSITION_PRICE_OPEN);
      double prof = isbuy ? (bid - e) : (e - ask);
      if (prof <= -InpMaxRiskPts) {
         trade.PositionClose(t);
         PrintFormat("[FADE] BOUND hit at %.2fpt", prof);
      }
   }
}

//+------------------------------------------------------------------+
void OnTick() {
   Manage();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;        // one decision per closed bar
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
