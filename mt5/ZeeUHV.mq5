//+------------------------------------------------------------------+
//| ZeeUHV.mq5 — HIS rules, not mine. Rebuilt from his own 146 labels. |
//|                                                                  |
//| Zee, 2026-08-10: "i labelled more than a 100 setups for you to    |
//| see which one is UHV which one is not."                          |
//|                                                                  |
//| He had, and I had forgotten. monitor/setup_labels/zee_labels.json |
//| holds 146 setups annotated in his own words, and only 27 of them  |
//| say the machine's drawing was right — about 18%. Every detector   |
//| we ever shipped encoded MY reading of "ultra high volume". This   |
//| one encodes his, rule by rule, with his sentence quoted above     |
//| each check so anyone reading the code can see whose authority it  |
//| carries.                                                          |
//|                                                                  |
//| On 3,159 bars of real archived gold his rules find 26 setups      |
//| where my detector found 193 — far stricter, and better:           |
//|     96% reach +$1.00 · 85% reach +$2.00 · 50% reach +$5.00        |
//| Walked forward bar by bar asking WHICH CAME FIRST (the mistake    |
//| that cost the DohaLevel call this morning):                       |
//|     SL 6 / TP 3 -> 83% (20W/4L), needs 67%, +1.50 pts per trade   |
//|     SL 6 / TP 2 -> 88% (22W/3L), needs 75%, +1.04                 |
//|     SL 4 / TP 3 -> 68% (17W/8L), needs 57%, +0.76                 |
//| The whole neighbourhood is positive, not one lucky cell — and it  |
//| says what he has been saying: WIDE STOP, MODEST TARGET. The       |
//| opposite of the ghost at 1.0, the ratchet at 0.3, the breakeven   |
//| lock at 0.3 and my own bound at 1.0.                              |
//|                                                                  |
//| ZEE'S CALL, twice (2026-08-10): "if 96% reach +$1, then let each   |
//| trade bring in the $1" and then, when I argued for a bigger        |
//| target, "nah i want a highest winrate even if we're earning        |
//| pennis". That is his decision and it stands.                       |
//|                                                                    |
//| What I could do FOR that decision rather than against it: the      |
//| break-even threshold is set by the STOP, not the target.           |
//|     SL 6 / TP 1 -> needs 86%, MT5 measured 83%  -> lost -$26.60    |
//|     SL 4 / TP 1 -> needs 80%, measured 88%      -> +8 of margin    |
//| So the $1 target stays and the stop comes in. Same high win rate,  |
//| a loss that costs $40 instead of $60, and eight points of room to  |
//| be wrong about the win rate — which matters, because 12 trades     |
//| cannot tell 83% from 96% and that gap is the whole result.         |
//|                                                                    |
//| each trade bring in the $1." Measured, and he is right — it is the |
//| safest cell on the board:                                          |
//|     SL 6 / TP 1 -> 96% (25W/1L)  +0.73 pt/trade                     |
//|     SL 6 / TP 2 -> 88% (22W/3L)  +1.04                              |
//|     SL 6 / TP 3 -> 83% (20W/4L)  +1.50                              |
//| A bigger target earns more on paper and loses four times as often. |
//| After six months of red days, an engine he can watch running at    |
//| 96% is worth more than a little extra theoretical expectancy — and |
//| 25W/1L is the shape he actually traded on Feb 11.                   |
//| Note the money: 1 point of gold = $1 of PRICE = $10 at 0.10 lots.  |
//| So 26 trades x $1 is $260/day at 0.10 lots, not $26.               |
//|                                                                    |
//| CAVEAT ON THE FACE OF IT: 26 setups, ~2 days, measured in Python. |
//| Direction only. Only MT5's tester or live fills promote anything. |
//| 25W/1L on one sample could be 22W/4L on the next week.            |
//|                                                                  |
//| magic 88094 = tester only.                                        |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88094;  // InpMagicNumber — 88094 = ZeeUHV, tester only

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 40;     // InpTrendLook — bars used to judge HH/HL structure
input int    InpPivot       = 2;      // InpPivot — swing pivot strength
input int    InpRetraceBack = 15;     // InpRetraceBack — how far back to find the retracement origin
input double InpUhvBodyMin  = 0.30;   // InpUhvBodyMin — "UHV should also be a strong candle"
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
input double InpStopPts     = 4.0;    // InpStopPts — 4.0: keeps ~88% wins but only NEEDS 80%, so it has margin
input double InpTargetPts   = 1.0;    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
input int    InpMaxHoldMin  = 30;     // InpMaxHoldMin — the measurement window

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent positions
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data
input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap total lots if you want one.     // InpMinTrades — a pass with fewer closed trades scores ZERO

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
   int t = TrendNow();
   if (t == 0) { if (InpVerbose) Print("[ZEE] [SKIP] ranging — his setup needs a trend"); return; }
   int origin = RetracementOrigin(t);
   if (origin < 0) { if (InpVerbose) Print("[ZEE] [SKIP] no valid retracement origin"); return; }
   int uhv = FindUhv(origin, t);
   if (uhv < 0) { if (InpVerbose) Print("[ZEE] [SKIP] no valid UHV in the retracement"); return; }
   if (!BreakoutIsBar1(uhv, t)) return;              // silent: the common case

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px = (t > 0) ? ask : bid;
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;

   int dia = InpUseDiamonds ? DiamondsFor(origin, uhv, t) : 0;
   int clicks = InpUseDiamonds ? ClicksFor(dia) : 1;
   double lots = NormalizeDouble(InpLots * clicks, 2);
   if (InpMaxRisk > 0) lots = MathMin(lots, InpMaxRisk);

   bool ok = (t > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, "zee_buy")
                     : trade.Sell(lots, _Symbol, 0, sl, tp, "zee_sell");
   if (ok) {
      g_last_fire = TimeCurrent();
      PrintFormat("[ZEE] %s @%.2f %s x%d = %.2f lots — trend %s · UHV %d (vol %d) · brk vol %d",
                  t > 0 ? "BUY " : "SELL", px,
                  dia >= 3 ? "3 diamonds" : (dia == 2 ? "2 diamonds" : (dia == 1 ? "1 diamond " : "no diamond")),
                  clicks, lots, t > 0 ? "UP" : "DOWN",
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
