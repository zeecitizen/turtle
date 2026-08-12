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
//| WATCHER REMOVED 2026-08-12. It defaulted to false and its guard returned
//| immediately, yet its mere presence changed the tester result: 1,608 trades at
//| 93.28% and +$2,599.10 became 1,665 at 69.43% and -$779.90 on identical data,
//| identical inputs and 97,564 identical bars. Removing it restores the number to
//| the cent. The mechanism is not yet understood, which is exactly why it is out:
//| dead code that moves live results is not dead.
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88094;  // InpMagicNumber — 88094 = ZeeUHV, tester only

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
input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = true;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)

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
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, 3))) : 1;
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
double OnTester() {
   double trades = TesterStatistics(STAT_TRADES);
   if (trades < InpMinTrades) return 0.0;
   if (TesterStatistics(STAT_PROFIT) <= 0) return 0.0;
   double wins = TesterStatistics(STAT_PROFIT_TRADES);
   return (wins / trades) * 100.0;
}

//+------------------------------------------------------------------+
void OnTick() {
   FadeExit();
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
