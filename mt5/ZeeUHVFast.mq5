//+------------------------------------------------------------------+
//| ZeeUHVFast.mq5 — a working copy of the LIVE ZeeUHV.               |
//|                                                                  |
//| Zee, 2026-08-14: "jaan create a copy of ZeeUHV call it ZeeUHVFast |
//| .. let's make some changes to things (keep diamond untouched)"    |
//|                                                                  |
//| Copied from ZeeUHV.mq5 at v1.10 — the build now attached to his   |
//| chart, including InpStackMult = 2 (8 tickets at 3 diamonds).      |
//|                                                                  |
//| THE RULES THIS FILE EXISTS TO OBEY:                               |
//|   * magic 88102, ITS OWN. Two EAs must never be able to manage    |
//|     each other's positions, and the live EA is 88094.             |
//|   * every log line is tagged [FAST], so a glance at the Experts   |
//|     tab says which EA spoke.                                      |
//|   * `diamond` and ZeeUHV.mq5 are NOT touched by anything done     |
//|     here. If an experiment in this file turns out to be worth     |
//|     keeping, it gets promoted deliberately, after it has won in   |
//|     a kind period AND a hostile one on real ticks.                |
//|                                                                   |
//| The measured starting point, so any change has something to beat  |
//| (real ticks, 163 ms delay, 0.02 lots, 8 fortnights):              |
//|     shipped   1,597 trades   -$1,152.40   E -0.722/trade          |
//| and the validated candidate not yet promoted, rank6 + MaxOpen 8:  |
//|     rung C    2,066 trades     -$758.10   E -0.367/trade          |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88102;  // InpMagicNumber — 88102 = ZeeUHVFast, ITS OWN. Never 88094 (live ZeeUHV) or 88095-88101 (the other experiments).

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 20;   // InpTrendLook — 20 validated
input int    InpPivot       = 2;      // InpPivot — swing pivot strength
input bool   InpRequireTrend = true;  // InpRequireTrend — false lets RANGING tape trade too (the 40% gate)
input int    InpRetraceBack = 20;   // InpRetraceBack — 20 validated
input double InpUhvBodyMin  = 0.5;   // InpUhvBodyMin — 0.5 validated. 0.3 finds more setups and loses money
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
input double InpStopPts     = 20.0;   // InpStopPts — 20 validated: 93.3% on 1,608 trades, 100% on both unseen sets
input double InpTargetPts   = 1.0;    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
input int    InpMaxHoldMin  = 60;   // InpMaxHoldMin — 60 — Zee: every breakout eventually gives the bump, so give it time

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent SETUPS (a stack counts as one)
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data

input group "-- Stale-quote guard (Zee found this 2026-08-14) --"
// The EA fired at 02:15 on 14 Aug using ask 4366.17. Blueberry's own tick history for
// that half-hour tops out at 4363.25 and the spread never exceeded 0.56 - that price
// did not exist. It DID exist about six hours earlier, 18:52-20:30 the previous evening.
// The bars were fresh (it found a real setup with real volumes); only the terminal's
// cached quote was stale. The server filled correctly at 4360.7, so the stop and target
// - both computed from 4366.17 - landed 6.4 points away from the trade. -$695.
//
// A gap guard already exists for BARS (WindowContinuous). Nothing checked the QUOTE.
input double InpMaxQuoteDrift = 2.0;   // InpMaxQuoteDrift — skip if the quote disagrees with bar 0 by more than this (0 = off)
input int    InpMaxQuoteAgeSec = 90;   // InpMaxQuoteAgeSec — skip if the last quote is older than this (0 = off)

input group "-- Untested free parameters (Zee 2026-08-15) --"
// 1. HIS OWN RULE, UNGRADED. "the breakout must be QUIETER than the UHV" is enforced as
//    volume < 1.00x, so a ratio of 0.71 and one of 0.99 are treated as equally good. On
//    the 16 live fires the ratio ranged 0.70 to 0.99 and the one that went wrong was
//    0.94. 1.00 reproduces the shipped behaviour exactly.
input double InpBrkVolMax  = 1.00;  // InpBrkVolMax — breakout volume must be under this FRACTION of the UHV's

// 2. HOUR OF DAY, never tested. The only genuine live loss opened at 02:15 broker, in thin
//    overnight tape, and our own notes carry prior evidence of a night effect. Broker-time
//    hours, allowed window [From, To). 0 and 24 = trade everything, as now.
input int    InpHourFrom   = 0;     // InpHourFrom — first broker hour allowed
input int    InpHourTo     = 24;    // InpHourTo — first broker hour NOT allowed

input group "-- VSA filters from Zee's reference, 2026-08-16 --"
// NOTE ON MAPPING, because it is the difference between testing his idea and testing
// something else: that text describes the UHV candle AS the breakout ("price must close
// near the top 20% of the bar"). In Zee's method the UHV is the LEVEL and the breakout is
// a separate, QUIETER candle later. So the close-position and next-candle rules are
// applied to the BREAKOUT bar here, not to the UHV.
//
// 8. MULTI-TIMEFRAME. "Align 1-minute UHV entries strictly with 15-minute or 1-hour trend
//    direction." Our trend gate is same-timeframe M1 structure only — this is untested.
// Zee, 2026-08-16: "the H1 alignment favorable setup you found, we can please make it a
// diamond. so it opens an additional trade for such aligned .. as a multiplier"
//
// Better than my filter version, and for a measurable reason. As a GATE, H1 alignment threw
// away half the trades (1,691 -> 826) and that is precisely what cost Feb and Jul. As a
// DIAMOND it blocks nothing — every setup still trades, the aligned ones simply carry an
// extra ticket. It also gives the conviction system something real to grade: every live
// setup so far scored D2 or D3, so the laws were never actually separating anything.
input bool   InpHtfAsDiamond = false; // InpHtfAsDiamond — H1 alignment adds a DIAMOND instead of gating
input int    InpHtfMinutes = 0;     // InpHtfMinutes — 0 = off · 15 = M15 · 60 = H1 (as a GATE)
input int    InpHtfLook    = 8;     // InpHtfLook — bars of that timeframe to measure over
//
// 1. EFFORT VS RESULT. Wide spread on high volume = genuine commitment; narrow spread on
//    high volume = churn. InpUhvBodyMin measures body/range; this measures RANGE PER UNIT
//    OF VOLUME, which is the ratio the text actually describes.
input double InpUhvEffortMin = 0.0; // InpUhvEffortMin — 0 = off. Min UHV range per 100 volume, in points
//
// 2. CLOSE POSITION. A genuine breakout closes near its extreme, not mid-bar.
input double InpBrkClosePos = 0.0;  // InpBrkClosePos — 0 = off. 0.8 = close in the top (or bottom) 20% of the breakout bar

input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = true;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)
input int    InpStackMult   = 2;      // InpStackMult — multiplies the whole stack. 2 => 8 tickets at 3 diamonds (Zee 2026-08-13)

datetime g_last_bar = 0;
datetime g_last_fire = 0;

//+------------------------------------------------------------------+
//| The tester overwrites tick_volume with its synthesised tick count |
//| (4/bar) and preserves real_volume. Measured 2026-08-10 with       |
//| TapeProbe: iVolume returned 4 4 4 4 4 while iRealVolume returned  |
//| 572 454 270 174. Every volume rule we owned had been blind.       |
//+------------------------------------------------------------------+
long BarVolume(int k) {
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

double bOpen(int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh(int k) { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow(int k) { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
bool IsGreen(int k) { return bClose(k) > bOpen(k); }
bool IsRed(int k) { return bClose(k) < bOpen(k); }
double BodyHi(int k) { return MathMax(bOpen(k), bClose(k)); }
double BodyLo(int k) { return MathMin(bOpen(k), bClose(k)); }

//+------------------------------------------------------------------+
//| 0. REGIME                                                         |
//|   "we cannot sell in an uptrend, we only buy in an uptrend" (e027)|
//|   "our setup only works if the market is not in a ranging         |
//|    condition" (e012)                                              |
//|   He judges trend by STRUCTURE — every complaint is phrased as    |
//|   'price made a lower low' or 'formed HH' — so this reads swing   |
//|   pivots, and returns 0 when they disagree.                       |
//+------------------------------------------------------------------+
int TrendNow() {
   double highs[]; double lows[];
   ArrayResize(highs, 0); ArrayResize(lows, 0);
   for (int k = InpTrendLook; k >= InpPivot + 1; k--) {
      bool ph = true, pl = true;
      for (int d = 1; d <= InpPivot; d++) {
         if (bHigh(k) < bHigh(k - d) || bHigh(k) < bHigh(k + d)) ph = false;
         if (bLow(k) > bLow(k - d) || bLow(k) > bLow(k + d)) pl = false;
      }
      if (ph) { int n = ArraySize(highs); ArrayResize(highs, n + 1); highs[n] = bHigh(k); }
      if (pl) { int n = ArraySize(lows);  ArrayResize(lows,  n + 1); lows[n]  = bLow(k); }
   }
   int nh = ArraySize(highs), nl = ArraySize(lows);
   if (nh < 2 || nl < 2) return 0;
   if (highs[nh-1] > highs[nh-2] && lows[nl-1] > lows[nl-2]) return +1;
   if (highs[nh-1] < highs[nh-2] && lows[nl-1] < lows[nl-2]) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| 1. THE RETRACEMENT AND WHERE IT STARTS                            |
//|   "In uptrend we take a buy -> in uptrend we find a retracement   |
//|    OF RED COLORED CANDLES" (#8)                                   |
//|   "the origin candle was a valid retracement itself as it broke   |
//|    the low of previous green" (#e025)                             |
//|   "its not a valid retracement as the last green's low wasn't     |
//|    broken by the origin, so no retracement started" (#e014)       |
//|   "the body of green candle doesnot break above the last red"(#c4)|
//|                                                                  |
//|   The BODY requirement is what every earlier detector missed: he  |
//|   rejects a retracement that only pokes past with a wick.         |
//+------------------------------------------------------------------+
int RetracementOrigin(int side) {
   bool wantRed = (side > 0);
   for (int k = 1; k <= InpRetraceBack; k++) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      int prev = -1;
      for (int j = k + 1; j <= k + 8; j++) {
         if (wantRed ? IsGreen(j) : IsRed(j)) { prev = j; break; }
      }
      if (prev < 0) continue;
      if (wantRed) { if (BodyLo(k) < bLow(prev)) return k; }
      else         { if (BodyHi(k) > bHigh(prev)) return k; }
   }
   return -1;
}

//+------------------------------------------------------------------+
//| 2. THE UHV                                                        |
//|   "a correct UHV should have been the largest volume at 5:30" (#1)|
//|   "Y has the lowest volume among its neighbors, its not a valid   |
//|    uhv because its not having highest volume" (#5)                |
//|   "for a buy setup the uhv should be a red candle" (#11)          |
//|   "uhv candle for sell case must be a green" (#24)                |
//|   "Y is not a UHV as its not in a valid retracement" (#6)         |
//|   "UHV should also be a strong candle, so that when we mitigate   |
//|    it we are mitigating strong sellers" (#loser_001)              |
//|                                                                  |
//|   Scope is his, not ours: the search runs INSIDE the retracement  |
//|   only, so a louder candle outside it can never be chosen. That   |
//|   single constraint answers most of his complaints.               |
//+------------------------------------------------------------------+
int FindUhv(int origin, int side) {
   bool wantRed = (side > 0);
   int best = -1; long bestv = -1;
   for (int k = origin; k >= 1; k--) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      long v = BarVolume(k);
      if (v > bestv) { bestv = v; best = k; }
   }
   if (best < 1) return -1;
   double rng = bHigh(best) - bLow(best);
   if (rng <= 0 || MathAbs(bClose(best) - bOpen(best)) / rng < InpUhvBodyMin) return -1;
   // 1. EFFORT VS RESULT — points of range per 100 units of volume. Low = churn.
   if (InpUhvEffortMin > 0) {
      double eff = rng / MathMax((double)bestv, 1.0) * 100.0;
      if (eff < InpUhvEffortMin) return -1;
   }
   if (BarVolume(best + 1) > bestv) return -1;      // louder than its neighbours
   if (best > 1 && BarVolume(best - 1) > bestv) return -1;
   return best;
}

//+------------------------------------------------------------------+
//| 3. THE BREAKOUT                                                   |
//|   "for a buy setup the breakout should be with a green colored    |
//|    candle" (#8) · "breakout candle in sell case must be red"(#24) |
//|   "the R cannot be considered as breakout candle since its body   |
//|    doesnot break/cross below the Y's lowest point (wick's end)"   |
//|                                                              (#33)|
//|   "14:50 would be a valid breakout candle if its volume were      |
//|    lower than the Y which it is not" (#15)                        |
//|   "we mark only 1 Breakout" (#13) · "B cannot be same candle as   |
//|    Y" (#17)                                                       |
//+------------------------------------------------------------------+
bool BreakoutIsBar1(int uhv, int side) {
   if (uhv <= 1) return false;                       // B cannot be Y
   bool wantGreen = (side > 0);
   // the FIRST true crossing must be bar 1 — if an earlier bar already crossed,
   // this one is late and he would not mark it
   for (int k = uhv - 1; k >= 1; k--) {
      if (wantGreen  && !IsGreen(k)) continue;
      if (!wantGreen && !IsRed(k))   continue;
      bool crossed = wantGreen ? (BodyHi(k) > bHigh(uhv)) : (BodyLo(k) < bLow(uhv));
      if (!crossed) continue;
      // must be quieter — InpBrkVolMax makes 'how much quieter' a measurable thing
      if ((double)BarVolume(k) >= (double)BarVolume(uhv) * InpBrkVolMax) return false;
      // 2. CLOSE POSITION on the BREAKOUT bar — near its extreme, not mid-bar
      if (InpBrkClosePos > 0) {
         double r2 = MathMax(bHigh(k) - bLow(k), 1e-9);
         double pos = wantGreen ? (bClose(k) - bLow(k)) / r2 : (bHigh(k) - bClose(k)) / r2;
         if (pos < InpBrkClosePos) return false;
      }
      return (k == 1);
   }
   return false;
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

int OpenCount() {
   // counts TICKETS. The stack is built in one pass inside TryFire, so InpMaxOpen only
   // gates NEW setups afterwards — which is what we want: one setup at a time, however
   // many tickets that setup happens to be worth.
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| THE LAWS OF CONVICTION — diamonds buy CLICKS, they never gate.     |
//|                                                                    |
//| Zee 2026-08-10: "have you tested with diamonds? because multiple    |
//| trades can bring us multiple profits aggregating to nice profits."  |
//| He is right that it was never tested: every ZeeUHV run so far fired |
//| a flat 0.10 regardless of how good the setup was, which throws away |
//| the whole point of the conviction system — that the BEST setups     |
//| should carry the MOST size.                                        |
//|                                                                    |
//| Mirrors diamonds_for() in monitor/oanda_live_matcher.py, which is   |
//| what the live machine already uses:                                 |
//|   Law 1  the sweep — price took liquidity before the setup          |
//|   Law 3  the EMA-5 close — the breakout closed decisively past it   |
//|   Law 5  the wick and the volume — clean body, quieter than the UHV |
//| and clicks_for(): 0-1 diamond -> 1 click, 2 -> 2, 3+ -> 3.          |
//+------------------------------------------------------------------+
double Ema5(int shift) {
   double k = 2.0 / 6.0, e = bClose(shift + 30);
   for (int i = shift + 29; i >= shift; i--) e = bClose(i) * k + e * (1.0 - k);
   return e;
}

//--- the higher-timeframe direction, shared by the gate and the diamond
int HtfDir() {
   int mins = (InpHtfMinutes > 0) ? InpHtfMinutes : 60;
   ENUM_TIMEFRAMES tf = (mins >= 60) ? PERIOD_H1 : PERIOD_M15;
   double now = iClose(_Symbol, tf, 1);
   double then = iClose(_Symbol, tf, 1 + InpHtfLook);
   if (now <= 0 || then <= 0) return 0;
   return (now > then) ? +1 : ((now < then) ? -1 : 0);
}

int DiamondsFor(int origin, int uhv, int side) {
   int d = 0;
   // LAW 6 — the higher timeframe agrees. Measured as a gate across 8 periods: drawdown
   // lower or equal in 8 of 8, and 18% better per trade. Here it SIZES instead of blocking.
   if (InpHtfAsDiamond) {
      int h = HtfDir();
      if (h != 0 && h == side) d++;
   }
   // Law 1 — the sweep: did price poke beyond the prior extreme on the way in?
   double hi = bHigh(uhv), lo = bLow(uhv);
   for (int k = uhv + 1; k <= uhv + 20; k++) {
      if (side > 0 && bLow(k) < lo) { d++; break; }
      if (side < 0 && bHigh(k) > hi) { d++; break; }
   }
   // Law 3 — the EMA-5 close: the breakout candle closed decisively past the mean
   double e5 = Ema5(1);
   if (side > 0 && IsGreen(1) && bClose(1) > e5 + 0.10) d++;
   if (side < 0 && IsRed(1)   && bClose(1) < e5 - 0.10) d++;
   // Law 5 — the wick and the volume
   double rng = MathMax(bHigh(1) - bLow(1), 1e-9);
   double wick = (side > 0) ? (bHigh(1) - MathMax(bOpen(1), bClose(1))) / rng
                            : (MathMin(bOpen(1), bClose(1)) - bLow(1)) / rng;
   if (wick <= 0.25 && BarVolume(1) < BarVolume(uhv)) d++;
   return d;
}

int ClicksFor(int d) { return (d <= 1) ? 1 : ((d == 2) ? 2 : 3); }

//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   // The load fingerprint. Hot-reload of an attached chart is UNRELIABLE, so this line is
   // how a deploy is verified — if the Experts tab does not say v1.10 with stack x2, the
   // chart is still running the old binary and the change did NOT take.
   PrintFormat("[FAST] ZeeUHVFast v1.00 — copy of ZeeUHV v1.10. SL %.1f / TP %.1f · magic %d"
               " · stack x%d (max %d tickets = %.2f lots, risk %.0f per failed setup)",
               InpStopPts, InpTargetPts, InpMagicNumber, MathMax(1, InpStackMult),
               4 * MathMax(1, InpStackMult), 4 * MathMax(1, InpStackMult) * InpLots,
               4 * MathMax(1, InpStackMult) * InpLots * InpStopPts * 100.0);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[FAST] deinit reason=%d", r); }

//+------------------------------------------------------------------+
void TryFire() {
   if (InpHourFrom != 0 || InpHourTo != 24) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      bool ok = (InpHourFrom <= InpHourTo)
                  ? (dt.hour >= InpHourFrom && dt.hour < InpHourTo)     // plain window
                  : (dt.hour >= InpHourFrom || dt.hour < InpHourTo);    // wraps midnight
      if (!ok) return;
   }
   if (OpenCount() >= InpMaxOpen) return;
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) return;
   if (!WindowContinuous(InpTrendLook + 5)) {
      if (InpVerbose) Print("[FAST] [SKIP] gap in lookback");
      return;
   }
//  THE 40% GATE, under test (Zee 2026-08-10: "can u check what's stopping us from
//  taking every single opportunity we get?"). Measured on real gold, the structural
//  trend reads FLAT 40.3% of the time, and update_gate()'s "flat -> the ghost waits"
//  forbids BOTH sides for those four hours in ten — before any setup rule is even
//  consulted. It is the single largest brake on trade count, and it was assumed, never
//  tested. With InpRequireTrend=false a ranging tape may still trade: we simply try
//  both sides and take whichever completes a lawful setup.
   int t = TrendNow();
   int sides[2]; int nsides = 0;
   if (t != 0) { sides[0] = t; nsides = 1; }
   else if (!InpRequireTrend) { sides[0] = +1; sides[1] = -1; nsides = 2; }
   else { if (InpVerbose) Print("[FAST] [SKIP] ranging — his setup needs a trend"); return; }

   // 8. HIGHER-TIMEFRAME ALIGNMENT — refuse a side the bigger picture disagrees with
   int htf = (InpHtfMinutes > 0) ? HtfDir() : 0;

   int origin = -1, uhv = -1, side = 0;
   for (int si = 0; si < nsides; si++) {
      int try_side = sides[si];
      if (InpHtfMinutes > 0 && htf != 0 && try_side != htf) continue;
      int o = RetracementOrigin(try_side);
      if (o < 0) continue;
      int u = FindUhv(o, try_side);
      if (u < 0) continue;
      if (!BreakoutIsBar1(u, try_side)) continue;
      origin = o; uhv = u; side = try_side; break;
   }
   if (side == 0) {
      if (InpVerbose && t != 0) Print("[FAST] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   // ─────────────────────────────────────────────────────────────────────────
   // THE STOP AND TARGET MUST COME FROM THE FILL, NOT FROM THE QUOTE.
   //
   // Zee found this on 2026-08-14 by reading his own MT5 history against my log:
   //   the EA logged   BUY @4366.17
   //   it FILLED at    4360.62 - 4360.78          (5.4 points lower)
   //   S/L was set     4346.17 = 4366.17 - 20
   //   T/P was set     4367.17 = 4366.17 + 1
   //
   // So the $1 target sat 6.4 points above the actual fill instead of 1, and could
   // not be reached inside the hold. All 8 tickets aged out at -8.7 points: -$695.
   // That loss was not the market, and it was not the 8-ticket stack. It was a
   // target measured from a price the trade never traded at.
   //
   // A normal fire for contrast (08-11): logged 4372.06, filled 4371.96, TP 4373.06
   // — 1.1 points above the fill, exactly as designed.
   //
   // The quote is still used to place the order, so a position is NEVER naked even
   // for a millisecond. The levels are then corrected from the real open price of
   // each ticket, which also means a late ticket in the stack gets its own honest
   // target rather than inheriting the first one's.
   // ─────────────────────────────────────────────────────────────────────────
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px = (t > 0) ? ask : bid;

   // ── THE QUOTE MUST BE FRESH AND IT MUST AGREE WITH THE TAPE ──────────────
   // Both checks print unconditionally when they fire. A guard that refuses a trade
   // silently is indistinguishable from a quiet market, and we have already lost a
   // day to exactly that confusion.
   if (InpMaxQuoteAgeSec > 0) {
      datetime qt = (datetime)SymbolInfoInteger(_Symbol, SYMBOL_TIME);
      long age = (long)(TimeCurrent() - qt);
      if (qt > 0 && age > InpMaxQuoteAgeSec) {
         PrintFormat("[FAST] [BLOCKED] quote is %d s old (limit %d) — not trading on it",
                     (int)age, InpMaxQuoteAgeSec);
         return;
      }
   }
   if (InpMaxQuoteDrift > 0) {
      // bar 0's close arrives through the HISTORY path, so it is an independent
      // witness to the quote cache. When they disagree, one of them is lying.
      double c0 = iClose(_Symbol, PERIOD_CURRENT, 0);
      if (c0 > 0 && MathAbs(px - c0) > InpMaxQuoteDrift) {
         PrintFormat("[FAST] [BLOCKED] quote %.2f disagrees with the tape %.2f by %.2f pts "
                     "(limit %.2f) — this is the 2026-08-14 fault, refusing the trade",
                     px, c0, MathAbs(px - c0), InpMaxQuoteDrift);
         return;
      }
   }
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;

   int dia = InpUseDiamonds ? DiamondsFor(origin, uhv, t) : 0;

   // THE STACK — Zee 2026-08-10: "the diamonds should each not only add 1 trade, but
   // add the trade in twice the lots that we already have... 0.1, then 0.2, then 0.3,
   // then 0.4 — it stacks while increasing the lot size as our conviction increases."
   //
   // So a diamond is not a multiplier on one ticket; it is ANOTHER ticket, larger than
   // the one before it. A setup with no diamonds is a single 0.10. A three-diamond
   // setup opens 0.10 + 0.20 + 0.30 + 0.40 = 1.00 across four positions, all sharing
   // the same stop and target.
   //
   // Note what this does to risk: at SL 7 a full four-deep stack risks 7 x 100 x 1.00
   // = $700 on ONE setup. The live receipts from 2026-08-06 already warn about
   // conviction sizing multiplying losses, so InpMaxRisk exists to cap the total and
   // this must be proven in the tester before it goes anywhere near live.
   // Zee, 2026-08-13: "since our winrate since past two days is 100%, let's increase the
   // multiplier of each diamond. so that instead of opening 4 trades, it opens 8 trades."
   //
   // HIS CALL, MADE WITH THE NUMBERS IN FRONT OF HIM. Measured on real ticks first, and
   // recorded here so nobody later mistakes it for an untested change:
   //
   //   * It is a PURE MULTIPLIER. Four periods at 0.02 lots gave -2451.16 against the
   //     4-ticket -1225.58 — exactly 2.000x. Per-ticket expectancy did not move
   //     ($1.40 -> $1.40) and neither did the average loss. It does not make the system
   //     better, it makes it bigger, in both directions.
   //   * AT 0.10 LOTS IT CHANGES WHAT MARCH DOES TO THE ACCOUNT. The 4-ticket stack
   //     survives March at 73.5% equity drawdown; at 8 tickets it BLEW THE ACCOUNT
   //     (93.0%). April blew up either way, but faster.
   //   * All tickets share one stop and fail together, so one lost setup costs
   //     8 x 0.10 x 20pt x $100 = $1,600, which is 38.8% of the $4,123 demo.
   //     Roughly 2.6 losing setups in a row would end it.
   //
   // The concern was put to him in those terms and he chose to ship it. Demo account.
   // The cap MUST follow the number of ACTIVE laws. A hardcoded 3 silently threw away the
   // 4th diamond once before and made a whole test return identical numbers to the cent.
   int maxdia = 3 + (InpHtfAsDiamond ? 1 : 0);
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, maxdia))) * MathMax(1, InpStackMult) : 1;
   double placed = 0, total = 0;
   for (int q = 0; q < tickets; q++) {
      double lots = NormalizeDouble(InpLots + InpStackStep * q, 2);
      if (!InpStackLots) lots = NormalizeDouble(InpLots * (InpUseDiamonds ? ClicksFor(dia) : 1), 2);
      // 1e-9 slack: 0.20 + 0.10 evaluates to 0.30000000000000004 in doubles, so a cap
      // of 0.30 silently behaved like 0.20 and the sweep returned identical numbers for
      // both. Floating point must never quietly move a risk limit.
      if (InpMaxRisk > 0 && total + lots > InpMaxRisk + 1e-9) break;
      // Zee, 2026-08-12: "measure the diamond's earnings and decide which diamond is
      // the most earner". The count must survive into the deal record to be grouped
      // later, and the comment is the only field that travels with it.
      string tag = StringFormat("zee_%s_D%d", (t > 0 ? "buy" : "sell"), dia);
      bool ok = (t > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, tag)
                        : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      total += lots; placed += 1;

      // Re-anchor this ticket's stop and target on the price it ACTUALLY filled at.
      ulong pt = trade.ResultOrder();
      if (pt > 0 && PositionSelectByTicket(pt)) {
         double fill = PositionGetDouble(POSITION_PRICE_OPEN);
         double slip = (t > 0) ? (px - fill) : (fill - px);   // + = filled better
         if (MathAbs(fill - px) > _Point) {
            double nsl = (InpStopPts   <= 0) ? 0.0
                       : ((t > 0) ? fill - InpStopPts   : fill + InpStopPts);
            double ntp = (InpTargetPts <= 0) ? 0.0
                       : ((t > 0) ? fill + InpTargetPts : fill - InpTargetPts);
            if (!trade.PositionModify(pt, nsl, ntp))
               PrintFormat("[FAST] !! could not re-anchor #%I64u (%d) — it is still on "
                           "the QUOTE levels, target %.2f", pt, trade.ResultRetcode(), tp);
         }
         // Loud, unconditional, never behind InpVerbose: a fill this far from the quote
         // is how -$695 happened, and it must be visible in the log the moment it recurs.
         if (MathAbs(slip) >= 1.0)
            PrintFormat("[FAST] !! SLIPPAGE %.2f pts — quote %.2f, filled %.2f. Levels "
                        "re-anchored on the fill.", slip, px, fill);
      }
      if (!InpStackLots) break;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      PrintFormat("[FAST] %s @%.2f — %d diamond(s) -> %d ticket(s), %.2f lots total · "
                  "UHV %d (vol %d) · brk vol %d",
                  t > 0 ? "BUY " : "SELL", px, dia, (int)placed, total,
                  uhv, (int)BarVolume(uhv), (int)BarVolume(1));
   }
}

void AgeOut() {
   if (InpMaxHoldMin <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (TimeCurrent() - opened >= InpMaxHoldMin * 60)
         if (trade.PositionClose(t) && InpVerbose)
            PrintFormat("[FAST] aged out after %dm", InpMaxHoldMin);
   }
}

//+------------------------------------------------------------------+
//| OnTester — let MT5 rank the passes by WIN RATE, in MT5's own       |
//| numbers.                                                           |
//|                                                                    |
//| Zee, 2026-08-10: "i want you to find something that has a 90%+     |
//| winrate on MT5 tester not Python. Find it using your tests."        |
//|                                                                    |
//| So the search moves inside the tester. The optimiser maximises     |
//| whatever this returns, and this returns the win rate measured by   |
//| MT5 with real spread and real execution — no Python anywhere in    |
//| the loop.                                                           |
//|                                                                    |
//| TWO GUARDS, because an unguarded win rate is trivially gamed:      |
//|   * fewer than InpMinTrades closed trades scores ZERO. Otherwise   |
//|     one lucky trade returns 100% and wins the whole optimisation.  |
//|   * a pass that LOST money scores zero however pretty its win      |
//|     rate. A 95% win rate that nets negative is the SL-30 trap he   |
//|     found this afternoon, where one loss wipes thirty wins.        |
//+------------------------------------------------------------------+
double OnTester() {
   double trades = TesterStatistics(STAT_TRADES);
   if (trades < InpMinTrades) return 0.0;
   if (TesterStatistics(STAT_PROFIT) <= 0) return 0.0;
   double wins = TesterStatistics(STAT_PROFIT_TRADES);
   return (wins / trades) * 100.0;
}

//+------------------------------------------------------------------+
void OnTick() {
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
