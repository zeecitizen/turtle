//+------------------------------------------------------------------+
//| ZeeUHV_Loud_Breakout.mq5 — the contradiction, put on trial live. |
//|                                                                  |
//| Zee, 2026-08-16: "regarding the loud breakout -> make it a       |
//| separate EA called ZeeUHV_Loud_Breakout so we can run it on the  |
//| LIVE market to check if it really gives 100% winrate over 45+    |
//| breakouts"                                                        |
//|                                                                  |
//| WHAT IT IS. Zee's own rule says the breakout must be QUIETER than |
//| the UHV — supply exhausted. Wyckoff's "Push Through Supply" says  |
//| the opposite: a LOUD bar cutting through proves buyers took       |
//| control. Both cannot be right, so this EA runs the loud version.  |
//|                                                                  |
//| WHY IT DESERVES A LIVE TEST rather than dismissal:               |
//|     live window 11-13 Aug   45 trades   100.00%   +$96.34        |
//|     E/trade +2.14 against the shipped engine's +1.27             |
//| Forty-five straight wins at our 88.06% baseline is a 0.33%       |
//| coincidence — a hundred times less likely than the 13-trade      |
//| result that turned out to be noise. This is a REAL effect.       |
//|                                                                  |
//| WHY IT IS NOT PROMOTED. It fails elsewhere, and badly:            |
//|     Mar 02-16   132 trades   58.33%   E -2.31  (shipped -1.65)   |
//|     Jun 01-15   242 trades   73.55%   E -0.35  (shipped -0.23)   |
//| So it is REGIME-DEPENDENT, not wrong. The live market is the      |
//| only instrument that can say which regime we are in now.          |
//|                                                                  |
//| IT KEEPS BOTH RULES AT ONCE. The breakout must still be quieter   |
//| than the UHV (Zee's rule, InpBrkVolMax) AND at least 80% of its   |
//| volume (Wyckoff's, InpBrkVolMin). So it takes the LOUD END of the |
//| quiet breakouts — the narrow band where the two ideas overlap.    |
//|                                                                  |
//| magic 88104, its own. Never 88094 (live ZeeUHV) or 88095-88103.   |
//| Every log line is tagged [LOUD]. Run it ALONGSIDE the live EA:    |
//| different magic means neither can touch the other's positions,    |
//| and the comparison is then like-for-like on the same tape.        |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.1"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88104;  // InpMagicNumber — 88094 = ZeeUHV, tester only

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 20;   // InpTrendLook — 20 validated
input int    InpPivot       = 2;      // InpPivot — swing pivot strength
input bool   InpRequireTrend = true;  // InpRequireTrend — false lets RANGING tape trade too (the 40% gate)
input int    InpRetraceBack = 20;   // InpRetraceBack — 20 validated
input double InpUhvBodyMin  = 0.5;   // InpUhvBodyMin — 0.5 validated. 0.3 finds more setups and loses money
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
// ZEE'S CALL, 2026-08-15. The 20-point stop stopped doing anything the moment the hold
// came down to 5 minutes — it was an unused parameter carrying the whole tail risk.
//
// Measured on the live window (11-13 Aug), real ticks, at hold 5. Stops of 20, 12, 8 and 5
// are IDENTICAL TO THE CENT — no trade's adverse excursion reached even 5 points inside
// five minutes, so the stop never fired at any of them:
//     stop 20 / 12 / 8 / 5   67 trades  88.06%  +85.04     tightening is FREE
//     stop 3                 67 trades  83.58%  +63.94     starts binding, starts costing
//     stop 2                 67 trades  77.61%  +53.68
//
// And it is not only free here — at hold 5 it is BETTER in the two hostile months:
//     March   -443.66 -> -375.44        April   -296.24 -> -232.84
//     May     -154.02 -> -191.86        (the honest cost)
//
// What it actually buys is the tail. Eight tickets share one stop, so a failed setup at
// 0.10 lots costs 8 x 0.10 x stop x 100:
//     stop 20   $1,600   38.8% of the account    2.6 losing setups to ruin
//     stop  5     $400    9.7%                  10.3
// The 14 Aug stale-quote accident took $695 of a possible $1,600. Capped at $400 now.
input double InpStopPts     = 5.0;    // InpStopPts — 5, Zee 2026-08-15. Free at hold 5, and it caps the tail 4x.
input double InpTargetPts   = 1.0;    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
// ZEE'S CALL, 2026-08-15: 5 minutes. He noticed his live trades nearly all finish inside
// three ("since all trades last nearly under 3 minutes .. would 90%+ trades still go into
// profit?") and asked for it to be measured on the LIVE window rather than on backtest
// periods — 11 Aug 01:51 to 14 Aug, the clean 14/14 run, excluding the two stale-quote
// trades of the 14th.
//
// Measured there, real ticks, 163 ms delay:
//     hold  win%     net    avgL    drawdown
//        3  68.66%  +67.60  -1.74     0.5%
//        4  82.09%  +93.44  -1.57     0.5%     best money
//        5  88.06%  +85.04  -4.86     1.0%     <- SHIPPED: keeps the win rate AND the money
//       60  89.06%  +29.84 -14.51     3.6%     the old setting
//
// Nearly 3x the money at a third of the drawdown, for one point of win rate. The mechanism
// is the average loss: -1.57 at four minutes against -14.51 at sixty. A short clock stops a
// failing trade bleeding for another 55 minutes.
//
// NOT a free lunch, recorded so it is not forgotten: across THREE periods the 60-minute
// hold wins overall, because March and May prefer it. What makes 5 more than a 3-day fit is
// that a SECOND, independent August window (10-13 Aug) also preferred short holds. It is a
// property of this regime, and this is the regime being traded. If the tape turns into
// March, revisit this line first.
input int    InpMaxHoldMin  = 5;    // InpMaxHoldMin — 5, Zee 2026-08-15, fitted to the live window

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent SETUPS (a stack counts as one)
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data

input group "── STALE-QUOTE GUARD — the 2026-08-14 fault (v1.20) ──"
// WHAT HAPPENED, so nobody ever removes these thinking they are paranoia:
//
// 02:15 on 14 Aug the EA fired BUY on ask 4366.17 and filled at 4360.7. Blueberry's own
// stored ticks for that half hour top out at 4363.25, and the widest spread in 4,420 ticks
// was 0.56 — that price did not exist. It DID exist 18:52-20:30 the PREVIOUS EVENING.
// SymbolInfoDouble had handed back a quote roughly six hours old.
//
// The bars were fresh, so a real setup was found and the server filled correctly. But the
// stop and target were computed from 4366.17, which put the $1 target 6.4 points above the
// actual fill — unreachable inside the hold. Eight tickets aged out: -$695.
//
// A gap guard for BARS has existed since 08-10. Nothing checked the QUOTE.
input double InpMaxQuoteDrift  = 2.0;  // InpMaxQuoteDrift — refuse if the quote disagrees with bar 0 by more than this (0 = off). The fault measured 5.4; a normal fire is ~0.1.
input int    InpMaxQuoteAgeSec = 120;  // InpMaxQuoteAgeSec — refuse if the last quote is older than this (0 = off)

input group "-- Laws of Conviction from Zee's PDF, 2026-08-16 --"
// All default OFF, so the shipped behaviour is unchanged until one earns its place.
// UHV ANATOMY — is this candle actually what we claim it is?
input double InpUhvVolMult   = 0.0; // InpUhvVolMult — 0 = off. UHV volume >= SMA(vol,20) x this. THE "is it genuinely ULTRA" test — we have only ever required it be the loudest of 20, never high in absolute terms.
input double InpUhvRangeATR  = 0.0; // InpUhvRangeATR — 0 = off. UHV range >= ATR(14) x this. Effort vs result measured against VOLATILITY (the earlier test used volume).
input double InpUhvClosePos  = 0.0; // InpUhvClosePos — 0 = off. 0.4 = the UHV must close above the bottom 40% of its own range (absorption, not collapse).
// CONTEXT
input double InpPreCompress  = 0.0; // InpPreCompress — 0 = off. The 5 bars before the UHV must average LESS than ATR(14) x this. Breakouts out of compression.
input double InpMaxPullback  = 0.0; // InpMaxPullback — 0 = off. 0.618 = the retracement may not exceed this fraction of the impulse that preceded it.
// EXECUTION
input double InpMaxSpreadPts = 0.0;

input group "-- Wyckoff / VSA composite (Zee's 2nd PDF, 2026-08-16) --"
// L1 AS A DIAMOND, at Zee's insistence and he is right. As a GATE it discards 95% of trades
// (67 -> 4) on 13 observations, and 13 wins in a row is a 19.1% coincidence at our baseline
// 88.06% win rate. As a DIAMOND it blocks nothing and only sizes up when it fires, so a
// false signal costs almost nothing while a true one pays. Correct use of a small sample.
input double InpUhvVolDia   = 2.0;  // InpUhvVolDia — LAW 6, ACTIVE. +1 diamond when UHV volume >= SMA(vol,20) x this.
input int    InpClimaxDia   = 60;   // InpClimaxDia — LAW 7, ACTIVE. +1 diamond when the UHV is the WIDEST bar of the last N.
//
// THE SQUAT BAR — and note it CONTRADICTS the effort-vs-result law tested earlier. That one
// wanted a WIDE spread on high volume; Wyckoff's squat wants a NARROW spread on high volume,
// reading it as buyers and sellers matched order-for-order. Both cannot be right, so both
// get measured.
input double InpSquatMax    = 0.0;  // InpSquatMax — 0 = off. UHV range must be UNDER ATR(14) x this (narrow = squat).
//
// EFFORT-VS-RESULT FAILURE: the bar right after the UHV fails to extend past it. Heavy
// selling with no follow-through.
input bool   InpNextFails   = false; // InpNextFails — the bar after the UHV must NOT break the UHV's low (buy) / high (sell)
//
// SELLING CLIMAX: the UHV is not merely loud, it is the WIDEST bar in recent memory.
input int    InpClimaxLook  = 0;    // InpClimaxLook — 0 = off. UHV must have the widest range of the last N bars.
//
// PUSH THROUGH SUPPLY — this DIRECTLY CONTRADICTS Zee's own rule. His breakout must be
// QUIETER than the UHV; PTS says it should be a HIGH-volume green bar cutting through. His
// rule was measured today and tightening it only removed winners, so this tests the opposite
// direction of the same dial.
input double InpBrkVolMin   = 0.8;  // InpBrkVolMin — THE POINT OF THIS EA. Breakout volume must be at least this fraction of the UHV's.

// Higher-timeframe alignment. Measured as a GATE across 8 periods: drawdown lower or
// equal in 8/8 and 18% better per trade. As a DIAMOND it was worse than shipped, so
// its value is removing bad trades rather than sizing good ones.
input int    InpHtfMinutes = 0;     // InpHtfMinutes — 0 = off · 15 = M15 · 60 = H1 (GATE)
input int    InpHtfLook    = 8;     // InpHtfLook — bars of that timeframe to measure over

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
//--- plain ATR(14): the mean true range of bars k..k+13
double AtrAt(int k) {
   double sum = 0;
   for (int i = k; i < k + 14; i++) {
      double h = bHigh(i), l = bLow(i), pc = bClose(i + 1);
      double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      sum += tr;
   }
   return sum / 14.0;
}

//--- mean volume of the 20 bars BEFORE k (k itself excluded, or it would dilute itself)
double AvgVolBefore(int k) {
   double sum = 0; int n = 0;
   for (int i = k + 1; i <= k + 20; i++) { sum += (double)BarVolume(i); n++; }
   return (n > 0) ? sum / n : 0.0;
}

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
input bool   InpImpulseOrigin = true;  // Law 9 LIVE 2026-08-17 — impulse-referenced origin (receipts in ZeeUHV v1.26)

int RetracementOrigin(int side) {
   bool wantRed = (side > 0);
   for (int k = 1; k <= InpRetraceBack; k++) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      int prev = -1;
      for (int j = k + 1; j <= k + 8; j++) {
         if (wantRed ? IsGreen(j) : IsRed(j)) {
            // Law 9 LIVE 2026-08-17 — same fix as ZeeUHV v1.26 (see there for receipts).
            // The reference bar must be an IMPULSE candle of the leg, never a bounce
            // inside the pullback (Zee's label #e014, forensic on the 11:08 loser).
            // This EA fires the SAME setups as ZeeUHV, so leaving it out would keep
            // half of every invalid basket alive.
            if (InpImpulseOrigin) {
               if (wantRed  && bHigh(j) <= bHigh(j + 1)) continue;
               if (!wantRed && bLow(j)  >= bLow(j + 1))  continue;
            }
            prev = j; break;
         }
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
   if (InpSquatMax > 0) {                         // narrow spread on huge volume
      double atr = AtrAt(best);
      if (atr <= 0 || rng > atr * InpSquatMax) return -1;
   }
   if (InpClimaxLook > 0) {                       // widest bar in recent memory
      for (int i = best + 1; i <= best + InpClimaxLook; i++)
         if ((bHigh(i) - bLow(i)) > rng) return -1;
   }
   if (InpNextFails && best > 1) {                // the effort had no follow-through
      if (wantRed) { if (bLow(best - 1) < bLow(best)) return -1; }
      else         { if (bHigh(best - 1) > bHigh(best)) return -1; }
   }
   // --- Laws of Conviction: is this UHV worthy of the name? ---
   if (InpUhvVolMult > 0) {                       // genuinely ULTRA, in absolute terms
      double av = AvgVolBefore(best);
      if (av <= 0 || (double)bestv < av * InpUhvVolMult) return -1;
   }
   if (InpUhvRangeATR > 0) {                      // effort vs result, against volatility
      double atr = AtrAt(best);
      if (atr <= 0 || rng < atr * InpUhvRangeATR) return -1;
   }
   if (InpUhvClosePos > 0) {                      // absorption, not collapse
      double pos = (bClose(best) - bLow(best)) / MathMax(rng, 1e-9);
      // for a BUY the UHV is RED and must hold up off its low; mirrored for a SELL
      double want = wantRed ? pos : (1.0 - pos);
      if (want < InpUhvClosePos) return -1;
   }
   if (InpPreCompress > 0) {                      // breaking out of compression
      double atr = AtrAt(best);
      double pre = 0;
      for (int i = best + 1; i <= best + 5; i++) pre += (bHigh(i) - bLow(i));
      pre /= 5.0;
      if (atr <= 0 || pre > atr * InpPreCompress) return -1;
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
      if (BarVolume(k) >= BarVolume(uhv)) return false;   // must be quieter
      // PUSH THROUGH SUPPLY tests the OTHER direction: a breakout that is too quiet may be
      // no demand rather than absorption cleared.
      if (InpBrkVolMin > 0 && (double)BarVolume(k) < (double)BarVolume(uhv) * InpBrkVolMin)
         return false;
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

int DiamondsFor(int origin, int uhv, int side) {
   int d = 0;
   // ── LAW 6 — the UHV is genuinely ULTRA in ABSOLUTE terms, not merely loudest of 20.
   // Zee, 2026-08-16, arguing against my dismissal of it: "if its so good that it has a
   // 100% winrate then why not?" He was right. As a GATE it discards 95% of trades on 13
   // observations — and 13 wins in a row is a 19.1% coincidence at our 88% baseline. As a
   // DIAMOND it blocks nothing and only sizes up when it fires. Measured: better in all
   // three periods (+1.27->+1.28, -1.65->-1.63, -0.23->-0.22).
   if (InpUhvVolDia > 0) {
      double av = AvgVolBefore(uhv);
      if (av > 0 && (double)BarVolume(uhv) >= av * InpUhvVolDia) d++;
   }
   // ── LAW 7 — SELLING CLIMAX: the UHV is not merely loud, it is the WIDEST bar in recent
   // memory. Better in all three periods, but on only 15 trades — which is exactly why it
   // is a diamond and not a gate.
   if (InpClimaxDia > 0) {
      double r7 = bHigh(uhv) - bLow(uhv);
      bool widest = true;
      for (int i = uhv + 1; i <= uhv + InpClimaxDia; i++)
         if ((bHigh(i) - bLow(i)) > r7) { widest = false; break; }
      if (widest) d++;
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
   // how a deploy is verified — the Experts tab must say Loud_Breakout AND magic 88104,
   // or you are looking at the wrong EA's trades.
   PrintFormat("[LOUD] ZeeUHV_Loud_Breakout v1.00 — Push Through Supply on trial. "
               "brk vol >= %.2f x UHV · SL %.1f / TP %.1f · magic %d"
               " · hold %d min · stack x%d (max %d tickets = %.2f lots, risk %.0f per failed setup)",
               InpBrkVolMin, InpStopPts, InpTargetPts, InpMagicNumber, InpMaxHoldMin,
               MathMax(1, InpStackMult),
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult),
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult) * InpLots,
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult) * InpLots * InpStopPts * 100.0);
   PrintFormat("[LOUD] PRICE via SymbolInfoTick + tick-history cross-check %s — refuse if "
               "the two disagree >%.2f pts or the tick is >%d s old · levels re-anchored "
               "on each fill (the 2026-08-14 -$695 fault)",
               (InpMaxQuoteDrift > 0 || InpMaxQuoteAgeSec > 0) ? "ARMED" : "*** OFF ***",
               InpMaxQuoteDrift, InpMaxQuoteAgeSec);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[LOUD] deinit reason=%d", r); }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| CurrentTick — the ONLY way this EA is allowed to learn a price.  |
//|                                                                  |
//| Zee, 2026-08-15: "can u ensure that we're using a method to pull  |
//| the latest price only while trading.. so we're using the current  |
//| price always"                                                     |
//|                                                                  |
//| The old code called SymbolInfoDouble(SYMBOL_ASK). That returns a  |
//| number and NOTHING ELSE — no timestamp, no way to know whether it |
//| is from this second or from last night. On 2026-08-14 it returned |
//| a price six hours old, twice, and the stop and target were built  |
//| on it. -$695 on one trade and a 4.43-point stop on the other.     |
//|                                                                  |
//| SymbolInfoTick returns the same price WITH tick.time, so age      |
//| becomes a fact instead of an assumption. Four checks, and the     |
//| function refuses rather than guessing:                            |
//|                                                                  |
//|   1. the call itself must succeed                                 |
//|   2. the symbol must be SYNCHRONIZED with the server              |
//|   3. the tick must be younger than InpMaxQuoteAgeSec              |
//|   4. the tick DATABASE (a different code path) must agree with it |
//|                                                                  |
//| Every refusal prints. A guard that blocks silently is             |
//| indistinguishable from a quiet market.                            |
//+------------------------------------------------------------------+
bool CurrentTick(MqlTick &out) {
   if (!SymbolInfoTick(_Symbol, out)) {
      PrintFormat("[LOUD] [BLOCKED] SymbolInfoTick failed (%d) — no price, no trade",
                  GetLastError());
      return false;
   }
   if (out.ask <= 0 || out.bid <= 0) {
      PrintFormat("[LOUD] [BLOCKED] nonsense quote bid=%.2f ask=%.2f", out.bid, out.ask);
      return false;
   }
   if (!SymbolIsSynchronized(_Symbol)) {
      Print("[LOUD] [BLOCKED] symbol is NOT synchronized with the server — refusing to trade");
      return false;
   }
   if (InpMaxQuoteAgeSec > 0) {
      long age = (long)(TimeCurrent() - out.time);
      if (age > InpMaxQuoteAgeSec) {
         PrintFormat("[LOUD] [BLOCKED] the tick is %d s old (limit %d) — this is the "
                     "2026-08-14 fault", (int)age, InpMaxQuoteAgeSec);
         return false;
      }
   }
   // The tick DATABASE is filled by a different mechanism than the symbol cache, so it
   // is an independent witness. If the cache had gone stale on 08-14, this is what would
   // have disagreed with it.
   if (InpMaxQuoteDrift > 0) {
      MqlTick h[];
      if (CopyTicks(_Symbol, h, COPY_TICKS_INFO, 0, 1) == 1 && h[0].ask > 0) {
         if (MathAbs(h[0].ask - out.ask) > InpMaxQuoteDrift) {
            PrintFormat("[LOUD] [BLOCKED] cache says %.2f, tick history says %.2f — %.2f "
                        "pts apart (limit %.2f). One of them is lying.",
                        out.ask, h[0].ask, MathAbs(h[0].ask - out.ask), InpMaxQuoteDrift);
            return false;
         }
         if (h[0].time_msc > out.time_msc) out = h[0];   // always prefer the NEWER tick
      }
   }
   return true;
}

void TryFire() {
   if (OpenCount() >= InpMaxOpen) return;
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) return;
   if (!WindowContinuous(InpTrendLook + 5)) {
      if (InpVerbose) Print("[LOUD] [SKIP] gap in lookback");
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
   else { if (InpVerbose) Print("[LOUD] [SKIP] ranging — his setup needs a trend"); return; }

   int htf = 0;
   if (InpHtfMinutes > 0) {
      ENUM_TIMEFRAMES htf_tf = (InpHtfMinutes >= 60) ? PERIOD_H1 : PERIOD_M15;
      double hnow = iClose(_Symbol, htf_tf, 1), hthen = iClose(_Symbol, htf_tf, 1 + InpHtfLook);
      if (hnow > 0 && hthen > 0) htf = (hnow > hthen) ? +1 : ((hnow < hthen) ? -1 : 0);
   }

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
      if (InpVerbose && t != 0) Print("[LOUD] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   MqlTick tk;
   if (!CurrentTick(tk)) return;          // no trustworthy price -> no trade, ever
   double ask = tk.ask;
   double bid = tk.bid;
   double px = (t > 0) ? ask : bid;

   // ── THE QUOTE MUST BE FRESH, AND IT MUST AGREE WITH THE TAPE ─────────────
   // Both refusals PRINT UNCONDITIONALLY. A guard that blocks silently is
   // indistinguishable from a quiet market, and that confusion has cost this
   // project a full day before.
   if (InpMaxQuoteAgeSec > 0) {
      datetime qt = (datetime)SymbolInfoInteger(_Symbol, SYMBOL_TIME);
      long age = (long)(TimeCurrent() - qt);
      if (qt > 0 && age > InpMaxQuoteAgeSec) {
         PrintFormat("[LOUD] [BLOCKED] quote is %d s old (limit %d) — refusing to trade on it",
                     (int)age, InpMaxQuoteAgeSec);
         return;
      }
   }
   if (InpMaxQuoteDrift > 0) {
      // bar 0's close arrives through the HISTORY path, so it is an INDEPENDENT
      // witness to the quote cache. When the two disagree, one of them is lying,
      // and on 2026-08-14 it was the quote — by 5.4 points.
      double c0 = iClose(_Symbol, PERIOD_CURRENT, 0);
      if (c0 > 0 && MathAbs(px - c0) > InpMaxQuoteDrift) {
         PrintFormat("[LOUD] [BLOCKED] quote %.2f vs tape %.2f — %.2f pts apart (limit %.2f). "
                     "This is the 2026-08-14 fault. Trade refused.",
                     px, c0, MathAbs(px - c0), InpMaxQuoteDrift);
         return;
      }
   }
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;

   if (InpMaxSpreadPts > 0 && (ask - bid) > InpMaxSpreadPts) {
      PrintFormat("[LOUD] [BLOCKED] spread %.2f over limit %.2f", ask - bid, InpMaxSpreadPts);
      return;
   }
   if (InpMaxPullback > 0) {
      // the impulse is the leg into the retracement; the pullback is origin..1
      double swing = 0, pull = 0;
      if (t > 0) {
         double lo = bLow(origin), hi = bHigh(origin);
         for (int k = origin; k <= origin + 20; k++) if (bLow(k) < lo) lo = bLow(k);
         for (int k = 1; k <= origin; k++) if (bHigh(k) > hi) hi = bHigh(k);
         swing = hi - lo;
         double pl = bLow(1);
         for (int k = 1; k <= origin; k++) if (bLow(k) < pl) pl = bLow(k);
         pull = hi - pl;
      } else {
         double hi2 = bHigh(origin), lo2 = bLow(origin);
         for (int k = origin; k <= origin + 20; k++) if (bHigh(k) > hi2) hi2 = bHigh(k);
         for (int k = 1; k <= origin; k++) if (bLow(k) < lo2) lo2 = bLow(k);
         swing = hi2 - lo2;
         double ph = bHigh(1);
         for (int k = 1; k <= origin; k++) if (bHigh(k) > ph) ph = bHigh(k);
         pull = ph - lo2;
      }
      if (swing > 0 && (pull / swing) > InpMaxPullback) return;
   }

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
   // the cap must follow the number of ACTIVE laws or the extra diamond is silently lost
   int maxdia = 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0);
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

      // SECOND LINE OF DEFENCE. The order goes out with quote-based levels so a
      // position is NEVER naked, then this resets the stop and target from the price
      // the ticket ACTUALLY filled at. Even if a bad quote gets past the guard above,
      // the target lands 1 point from the real entry instead of 6.4.
      ulong pt = trade.ResultOrder();
      if (pt > 0 && PositionSelectByTicket(pt)) {
         double fill = PositionGetDouble(POSITION_PRICE_OPEN);
         if (MathAbs(fill - px) > _Point) {
            double nsl = (t > 0) ? fill - InpStopPts   : fill + InpStopPts;
            double ntp = (t > 0) ? fill + InpTargetPts : fill - InpTargetPts;
            if (!trade.PositionModify(pt, nsl, ntp))
               PrintFormat("[LOUD] !! could not re-anchor #%I64u (%d) — still on QUOTE levels",
                           pt, trade.ResultRetcode());
            else if (MathAbs(fill - px) >= 1.0)
               PrintFormat("[LOUD] !! fill %.2f vs quote %.2f (%.2f pts) — levels re-anchored "
                           "on the fill", fill, px, MathAbs(fill - px));
         }
      }
      if (!InpStackLots) break;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      PrintFormat("[LOUD] %s @%.2f — %d diamond(s) -> %d ticket(s), %.2f lots total · "
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
            PrintFormat("[LOUD] aged out after %dm", InpMaxHoldMin);
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
