//+------------------------------------------------------------------+
//| ZeeUHV_v13.mq5 — HIS EXIT, not ours. v1.3                        |
//|                                                                  |
//| Zee's real Feb-11 statement (account 5118408, EUR, live money,   |
//| 69 fills, +EUR835.16) measured against what we built:            |
//|                                                                  |
//|                     HIS HAND          OUR EA                     |
//|     average win     EUR +12.93        $  +9.98                   |
//|     average loss    EUR  -1.32        $-114.58                   |
//|     worst loss      EUR  -1.60        $-200.00                   |
//|     win/loss ratio      9.8 : 1          0.1 : 1                 |
//|                                                                  |
//| His statement has NO stop loss and NO take profit — both columns  |
//| are EMPTY on all 69 fills. He cut the bad ones by hand at roughly |
//| BREAKEVEN (0.14 points) and let the good ones run to 5.5 points.  |
//|                                                                  |
//| We reproduced his 94% WIN RATE with geometry — a 1-point target   |
//| against a 20-point stop — and got the INVERSE SHAPE. NullEntry    |
//| proved that win rate comes free from the geometry, so we were     |
//| never copying his edge; we were copying the one statistic any     |
//| wide-stop scalper produces for nothing.                           |
//|                                                                  |
//| His own memory has said this for months: "EXIT is the edge —      |
//| Feb 11's 94% came from the discretionary EXIT, not the entry."    |
//|                                                                  |
//| SO THIS KEEPS THE ENTRY EXACTLY AND REPLACES THE EXIT:            |
//|   InpStopPts       small (his losses were ~0.14 points)           |
//|   InpTargetPts     0 = NO fixed target, let the winner run        |
//|   InpTrailStart    arm the trail once this far in profit          |
//|   InpTrailDist     then give back at most this much               |
//|                                                                  |
//| CAVEAT WORTH STATING: he watched the screen. A hard 1-point stop  |
//| is not the same instrument as a human deciding to cut — the       |
//| spread alone is 0.21. The test will show whether a mechanical     |
//| tight stop can stand in for a hand.                               |
//|                                                                  |
//| magic 88099 — its own.                                            |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.30"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88099;  // InpMagicNumber — 88098 = ZeeUHV v1.2. Never 88094/88095/88096.

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 20;   // InpTrendLook — 20 validated
input int    InpPivot       = 2;      // InpPivot — swing pivot strength
input bool   InpRequireTrend = true;  // InpRequireTrend — false lets RANGING tape trade too (the 40% gate)
input int    InpRetraceBack = 20;   // InpRetraceBack — 20 validated
input bool   InpRequirePeak = false;  // InpRequirePeak — FALSE = Zee's spec (loudest same-coloured bar in the retracement wins). TRUE = v1's extra adjacent-bar test.
input double InpUhvBodyMin  = 0.5;   // InpUhvBodyMin — 0.5 validated. 0.3 finds more setups and loses money
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
input double InpStopPts     = 20.0;   // InpStopPts — 20 validated: 93.3% on 1,608 trades, 100% on both unseen sets
input double InpTargetPts   = 0.0;   // InpTargetPts — 0 = NO fixed target; let the winner run
input double InpTrailStart  = 1.0;   // InpTrailStart — arm the trail once this many points in profit
input double InpTrailDist   = 1.0;   // InpTrailDist — then give back at most this much    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
input int    InpMaxHoldMin  = 60;   // InpMaxHoldMin — 60 — Zee: every breakout eventually gives the bump, so give it time

input group "── Housekeeping ──"
input group "── VSA volume-fade exit (test, 2026-08-12) ──"
input bool   InpFadeExit    = false;  // InpFadeExit — close when institutional effort dies
input double InpFadeFrac    = 0.35;   // InpFadeFrac — a bar is 'dead' below this fraction of the UHV's volume
input int    InpFadeBars    = 3;      // InpFadeBars — this many CONSECUTIVE dead bars before closing

input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent SETUPS (a stack counts as one)
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data
input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseLaw2     = false;  // InpUseLaw2 — Law 2 (No Supply / No Demand) as a 4th diamond. OFF until measured.
input double InpNsdSpread   = 0.70;   // InpNsdSpread — the test bar's range must be under this fraction of the recent average
input double InpNsdVolFrac  = 0.80;   // InpNsdVolFrac — and its volume under this fraction of the prior bars

input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = true;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)
input int    InpDiaMult     = 1;      // InpDiaMult — tickets PER DIAMOND. 2 => 1+dia*2 = 7 at 3 diamonds (conviction-weighted)
input int    InpStackMult   = 1;      // InpStackMult — multiplies the whole stack. 2 => 8 at 3 diamonds (same as doubling InpLots)

datetime g_last_bar = 0;
datetime g_last_fire = 0;
long     g_uhv_vol   = 0;      // the effort that justified the trade
datetime g_fade_bar  = 0;      // so the fade is judged once per bar, not per tick

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
   // v1.2: these two lines are v1's addition, NOT Zee's rule. His "largest among its
   // peers" is already satisfied by the loop above, which keeps the loudest bar OF THE
   // RIGHT COLOUR inside the retracement. These compare against the adjacent bars
   // whatever colour they are, and reject 36% of candidates on their own.
   if (InpRequirePeak) {
      if (BarVolume(best + 1) > bestv) return -1;
      if (best > 1 && BarVolume(best - 1) > bestv) return -1;
   }
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
      return (k == 1);
   }
   return false;
}

//| RESUMING AFTER A DROPOUT — Zee, 2026-08-13: "our EA should resume as
//| soon as it can.. 25 mins is too much".
//|
//| The old guard rejected the whole 25-bar window if ANY hole sat inside it,
//| so one outage cost 25 clean minutes afterwards. On a flaky connection that
//| is expensive, and it is stricter than the logic needs: the rules only ever
//| read from the retracement origin forward, which is usually far shorter.
//|
//| WHAT DID NOT CHANGE: a hole is still never reasoned across. Bars either
//| side of an outage are not comparable and a "UHV" measured over one is an
//| artefact of the router, not the market. This narrows WHERE we look for a
//| hole; it does not tolerate one.
//|
//| Worth knowing (measured 2026-08-13): during three dropouts of 33, 25 and
//| 32 minutes, OANDA recorded EVERY bar — the market was trading and only our
//| connection was down. MT5 backfills M1 history on reconnect, so in that
//| common case there is no hole to find and neither guard blanks anything.
//| This matters only for a genuine hole, e.g. broker-side.
bool WindowUsable(int from_bar) {
   if (InpMaxGapSec <= 0) return true;
   int step = PeriodSeconds();
   for (int k = 1; k < from_bar; k++) {
      datetime a = iTime(_Symbol, PERIOD_CURRENT, k);
      datetime b = iTime(_Symbol, PERIOD_CURRENT, k + 1);
      if (a <= 0 || b <= 0) return false;
      if ((int)(a - b) > step + InpMaxGapSec) return false;
   }
   return true;
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


//+------------------------------------------------------------------+
//| LAW 2 — No Supply / No Demand. The VACUUM after the footprint.   |
//|                                                                  |
//| The last piece of Zee's doctrine the EA never used. It lives in   |
//| oanda_live_matcher.py as a VETO; here it is a DIAMOND, because a  |
//| veto starves an engine whose baseline win rate comes from the     |
//| geometry rather than from selectivity — NullEntry scored 92.42%   |
//| with no rules at all, so every rule that BLOCKS costs sample and  |
//| must earn its place, while a rule that SCALES costs nothing.      |
//|                                                                  |
//| WHERE IT APPLIES: the bar immediately BEFORE the breakout — the   |
//| exhaustion point of the retracement — not the UHV candle.         |
//|   the UHV measures the institutional FOOTPRINT (heavy absorption) |
//|   No Supply / No Demand measures the VACUUM that follows it       |
//|                                                                  |
//| No Supply (buying, so the pullback is red):                       |
//|   a DOWN bar, narrow range, closing in its upper half, on volume  |
//|   below the bars before it — the sellers have dried up.           |
//| No Demand (selling) is the mirror.                                |
//+------------------------------------------------------------------+
bool NoSupplyOrDemand(int k, int side) {
   // narrow spread, measured against the recent average range
   double avg = 0; int n = 0;
   for (int j = k + 1; j <= k + 10; j++) { avg += bHigh(j) - bLow(j); n++; }
   if (n == 0) return false;
   avg /= n;
   double rng = bHigh(k) - bLow(k);
   if (avg <= 0 || rng > avg * InpNsdSpread) return false;

   // the right colour: a DOWN bar when buying (no supply), UP when selling
   if (side > 0 && !IsRed(k))   return false;
   if (side < 0 && !IsGreen(k)) return false;

   // closing away from the extreme it was pushed toward
   double pos = (rng > 0 ? (bClose(k) - bLow(k)) / rng : 0.5);
   if (side > 0 && pos < 0.5) return false;      // no supply closes in the UPPER half
   if (side < 0 && pos > 0.5) return false;      // no demand closes in the LOWER half

   // and the volume has dried up against the bars before it
   long v = BarVolume(k);
   long prior = 0; int m = 0;
   for (int j = k + 1; j <= k + 3; j++) { prior += BarVolume(j); m++; }
   if (m == 0 || prior <= 0) return false;
   return v < (prior / m) * InpNsdVolFrac;
}

int DiamondsFor(int origin, int uhv, int side) {
   int d = 0;
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
   // Law 2 — the vacuum on the bar just before the breakout
   if (InpUseLaw2 && NoSupplyOrDemand(2, side)) d++;
   return d;
}

int ClicksFor(int d) { return (d <= 1) ? 1 : ((d == 2) ? 2 : 3); }

//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("[ZEE] ZeeUHV v1.00 — HIS rules from 146 labels. SL %.1f / TP %.1f · magic %d",
               InpStopPts, InpTargetPts, InpMagicNumber);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[ZEE] deinit reason=%d", r); }

//+------------------------------------------------------------------+
void TryFire() {
   if (OpenCount() >= InpMaxOpen) return;
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) return;
   if (!WindowContinuous(InpTrendLook + 5)) {
      if (InpVerbose) Print("[ZEE] [SKIP] gap in lookback");
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
   else { if (InpVerbose) Print("[ZEE] [SKIP] ranging — his setup needs a trend"); return; }

   int origin = -1, uhv = -1, side = 0;
   for (int si = 0; si < nsides; si++) {
      int try_side = sides[si];
      int o = RetracementOrigin(try_side);
      if (o < 0) continue;
      int u = FindUhv(o, try_side);
      if (u < 0) continue;
      if (!BreakoutIsBar1(u, try_side)) continue;
      origin = o; uhv = u; side = try_side; break;
   }
   if (side == 0) {
      if (InpVerbose && t != 0) Print("[ZEE] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px = (t > 0) ? ask : bid;
   // ZERO MEANS "NONE", NOT "AT THE ENTRY PRICE" (fixed 2026-08-13).
   //
   // This line used to read `px + InpTargetPts` unconditionally, so InpTargetPts = 0
   // placed the take-profit ON THE ENTRY PRICE. The trade then closed the moment price
   // ticked up by one spread. Every "no target, let the winner run" configuration ever
   // measured was really "open and close at breakeven": across 63 August trades the
   // LARGEST win was $2.70, against the TP-1 baseline's $15.20, while the tape over
   // those same entries offered a median +4.62 points. The 25-minute hold never
   // happened, which is why 15 / 25 / 40 minutes all returned nearly the same number.
   //
   // That artefact produced last night's "no stop, flat 25min survives all four
   // periods, -$1,150" — a machine that barely traded, not one that survived.
   // MT5 treats 0.0 as "no level", so that is what zero must send.
   double sl = (InpStopPts   <= 0) ? 0.0 : ((t > 0) ? px - InpStopPts   : px + InpStopPts);
   double tp = (InpTargetPts <= 0) ? 0.0 : ((t > 0) ? px + InpTargetPts : px - InpTargetPts);

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
   // The cap must follow the number of ACTIVE laws, not a hardcoded 3. With Law 2
   // enabled there are four diamonds available, and a fixed cap of 3 silently threw the
   // fourth away — the Law 2 test returned results identical TO THE CENT because the
   // rule could not affect the outcome at all. A limit that quietly deletes a feature
   // is the same class of bug as a fallback that never announces itself.
   // Zee, 2026-08-13: "since our winrate since past two days is 100%, let's increase the
   // multiplier of each diamond. so that instead of opening 4 trades, it opens 8 trades".
   //
   // That sentence has two readings and they are NOT the same trade, so both are built and
   // both get measured rather than one being guessed at:
   //
   //   InpDiaMult   — each diamond is worth this many tickets.  1 + dia*2  = 7 at 3 diamonds.
   //                  Concentrates size on CONVICTION: a 0-diamond setup still opens 1.
   //   InpStackMult — multiplies the finished stack.  (1 + dia)*2 = 8 at 3 diamonds.
   //                  Doubles EVERYTHING, so it is arithmetically identical to doubling
   //                  InpLots — profit x2 and drawdown x2, no change in risk-adjusted return.
   //
   // Both default to 1, which reproduces the shipped stack exactly.
   int maxdia  = InpUseLaw2 ? 4 : 3;
   int capped  = MathMax(0, MathMin(dia, maxdia));
   int tickets = InpStackLots ? (1 + capped * InpDiaMult) * InpStackMult : 1;
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
      if (!InpStackLots) break;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      g_uhv_vol   = BarVolume(uhv);   // the effort this trade rests on
      PrintFormat("[ZEE] %s @%.2f — %d diamond(s) -> %d ticket(s), %.2f lots total · "
                  "UHV %d (vol %d) · brk vol %d",
                  t > 0 ? "BUY " : "SELL", px, dia, (int)placed, total,
                  uhv, (int)BarVolume(uhv), (int)BarVolume(1));
   }
}

//+------------------------------------------------------------------+
//| THE VOLUME-FADE EXIT — exit on INFORMATION, not on a clock.      |
//|                                                                  |
//| Two VSA reports proposed cutting the hold from 60 minutes to 8,  |
//| arguing a stalled breakout is a dead breakout. Swept over 103    |
//| days that is catastrophic: 60 min gives +$2,599 at 93.28%, and   |
//| 8 min gives -$918. The fast winners were already banked; a short |
//| clock cuts the SLOW winners, and in this market most drifting    |
//| trades still reach the target, only later.                       |
//|                                                                  |
//| This is the one proposal that survived that argument, because it |
//| uses no clock at all. If institutional effort has evaporated the |
//| reason for the trade is gone, whatever the stopwatch says.       |
//|                                                                  |
//| The anchor is the UHV's OWN volume — the effort that justified   |
//| the entry. A bar is dead below InpFadeFrac of it, and it takes   |
//| InpFadeBars CONSECUTIVE dead bars to close, so a single quiet    |
//| minute cannot eject a good trade.                                |
//|                                                                  |
//| DEFAULT OFF until measured. The Watcher was off too and still    |
//| changed the result, so the baseline is RE-VERIFIED after adding  |
//| this rather than assumed.                                        |
//+------------------------------------------------------------------+
void FadeExit() {
   if (!InpFadeExit || g_uhv_vol <= 0) return;
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_fade_bar) return;                 // judge once per bar, not per tick
   g_fade_bar = bt;
   long limit = (long)(g_uhv_vol * InpFadeFrac);
   for (int k = 1; k <= InpFadeBars; k++)
      if (BarVolume(k) >= limit) return;         // the effort is still there
   int closed = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (trade.PositionClose(t)) closed++;
   }
   if (closed && InpVerbose)
      PrintFormat("[ZEE] VOLUME FADE — %d bars under %d (%.0f%% of UHV %d), closed %d",
                  InpFadeBars, (int)limit, InpFadeFrac * 100, (int)g_uhv_vol, closed);
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
            PrintFormat("[ZEE] aged out after %dm", InpMaxHoldMin);
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
//+------------------------------------------------------------------+
//| CVaR95 — the mean of the WORST 5% of losing trades.              |
//|                                                                  |
//| The first TCER used STAT_MAX_LOSSTRADE, the single worst trade,   |
//| which lets one news spike decide a 585-config sweep. MT5 has no   |
//| CVaR statistic, but OnTester runs after the test finishes, so the |
//| whole deal history is there to be read.                           |
//|                                                                  |
//| Why this is the better tail measure: CVaR95 is always >= the      |
//| average loss, so avgLoss/CVaR95 lands in (0,1] and reaches 1 only |
//| when EVERY loss is the same size. That is exactly the property we |
//| want to reward — losses that are uniform rather than occasionally |
//| catastrophic.                                                     |
//+------------------------------------------------------------------+
double GetCVaR95() {
   if (!HistorySelect(0, TimeCurrent())) return 0.0;
   double losses[];
   int n = 0, total = HistoryDealsTotal();
   for (int i = 0; i < total; i++) {
      ulong t = HistoryDealGetTicket(i);
      if (t <= 0) continue;
      long entry = HistoryDealGetInteger(t, DEAL_ENTRY);
      if (entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;
      double pnl = HistoryDealGetDouble(t, DEAL_PROFIT)
                 + HistoryDealGetDouble(t, DEAL_SWAP)
                 + HistoryDealGetDouble(t, DEAL_COMMISSION);
      if (pnl < 0) { n++; ArrayResize(losses, n); losses[n-1] = MathAbs(pnl); }
   }
   if (n == 0) return 0.0;
   ArraySort(losses);                                  // ascending
   int k = (int)MathMax(1, MathCeil(n * 0.05));        // the worst 5%, at least one
   double sum = 0.0;
   for (int i = n - k; i < n; i++) sum += losses[i];
   return sum / k;
}

double OnTester() {
   // ── TCER with TRUE CVaR95 ───────────────────────────────────────────────────
   //     TCER = E x (avgLoss / CVaR95) x sqrt(N)
   //
   // Win rate is not used and never will be again. NullEntry — no rules at all —
   // scored 92.42% against ZeeUHV's 93.28%, because a 1-point target against a
   // 20-point stop over 60 minutes wins ~92% from ANY entry. The edge is not picking
   // winners; it is picking trades that are CHEAP TO BE WRONG ABOUT.
   //
   //   E                 expectancy per trade, and rejects any net-negative pass
   //   avgLoss/CVaR95    in (0,1]; reaches 1 only when every loss is the same size
   //   sqrt(N)           sample weight, so a lucky short run cannot outrank 1,600 trades
   //
   // STILL NOT A PROOF. The ratio can rise by shrinking the tail (wanted) or by
   // inflating the average loss (not wanted), and E only partly cancels that. Every
   // winner is frozen and run on unseen data before it is believed — the discipline
   // that caught a TP-3 config worth $4,152 in-sample and -$491 on Feb 11.
   double trades = TesterStatistics(STAT_TRADES);
   double net    = TesterStatistics(STAT_PROFIT);
   double losses = TesterStatistics(STAT_LOSS_TRADES);
   double avgLoss = MathAbs(TesterStatistics(STAT_GROSS_LOSS) / MathMax(1.0, losses));
   if (trades < InpMinTrades || net <= 0 || avgLoss <= 0) return 0.0;
   double cvar = GetCVaR95();
   if (cvar <= 0) return 0.0;
   return (net / trades) * (avgLoss / cvar) * MathSqrt(trades);
}




//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| THE TRAIL — the mechanical stand-in for his hand.                |
//|                                                                  |
//| He had no take-profit. He watched a winner and closed it when it  |
//| stopped going his way, which is why his best fill was 5.5 points  |
//| while a fixed 1-point target would have taken 1.0 and stopped.    |
//| Once a trade is InpTrailStart points ahead, the stop follows at   |
//| InpTrailDist behind the best price seen. It never moves backwards.|
//+------------------------------------------------------------------+
void Trail() {
   if (InpTrailStart <= 0 || InpTrailDist <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if (type == POSITION_TYPE_BUY) {
         if (bid - open < InpTrailStart) continue;
         double want = bid - InpTrailDist;
         if (want > sl + _Point) trade.PositionModify(t, NormalizeDouble(want, _Digits),
                                                      PositionGetDouble(POSITION_TP));
      } else {
         if (open - ask < InpTrailStart) continue;
         double want = ask + InpTrailDist;
         if (sl == 0 || want < sl - _Point) trade.PositionModify(t, NormalizeDouble(want, _Digits),
                                                                 PositionGetDouble(POSITION_TP));
      }
   }
}

void OnTick() {
   Trail();
   FadeExit();
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
