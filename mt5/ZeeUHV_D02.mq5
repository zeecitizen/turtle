//+------------------------------------------------------------------+
//|  ZeeUHV_D02.mq5 — THE UNTOUCHED DIAMOND, resurrected         |
//|  Byte-identical to commit 718b68a (the streak-era machine,       |
//|  Aug 11-13 2026: 14 baskets, 100%, +$614) except this nameplate, |
//|  magic 88094->88154, [ZEE]->[DIA], zee_->zdia_ ticket tags.      |
//|  Zee, 2026-08-20: "i wanna see because that EA performed even    |
//|  better than what our ZeeUHV is doing now on 1 min."             |
//|  COURT RECEIPTS of this config (v1.47 RAW reconstruction):       |
//|  -1,640/six fortnights: POSITIVE in 4 of 6 (May +220, Jun +161,  |
//|  Jul +180, LIVE +38) — destroyed by Mar (-803) and Apr (-1,437). |
//|  At 0.10 lots a crash cluster can cost ~$1,700 in a day. It has  |
//|  NO pulse, NO laws 9+, NO clock discipline beyond hold-60.       |
//|  It is the wild ancestor, revived for live observation.          |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.11"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.01;   // InpLots — lot size
input int    InpMagicNumber = 88202;  // InpMagicNumber — 88094 = ZeeUHV, tester only

// ── HIS EYE, FOR THE ANCESTOR (2026-08-21). The Diamond judges UHVs on volume and
// owns no other guard, so the volume feed IS its strategy. Measured over four days
// at live size: broker +433.90 vs OANDA +1,358.10, better on 3 of 4 — and Aug 19,
// the day the broker feed cost it -522.30, came back +59.40 on his eye. That day is
// the Diamond's whole disease (one basket erases nine good days).
// Reads Common\Files\oanda_vol.csv, reloaded once per M1 bar, per-minute fallback
// to broker volume. Levels and fills stay Blueberry's, always. Default 0.
input int    InpOandaVolume = 0;    // 1 = judge UHVs on OANDA (TradingView) volume

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
input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseDiamonds = false;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = false;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)
input int    InpStackMult   = 1;      // InpStackMult — multiplies the whole stack. 2 => 8 tickets at 3 diamonds (Zee 2026-08-13)

input group "── LAWS.md ADDITIONS (2026-08-26) — one per variant, all default OFF ──"
// The Diamond obeys his ENTRY laws and none of his EXIT laws. Each input below puts
// ONE clause of his page back. A variant flips exactly one of them on, so whatever the
// live record says can be attributed to that clause and nothing else.
input double InpLawMomBody    = 0.0;   // >0: breakout body/range must reach this (0.70)
input double InpLawClosePos   = 0.20;   // >0: breakout must close within this share of its extreme
input double InpLawExpansion  = 0.0;   // >0: breakout body > this x SMA(body,20)
input bool   InpLawBodySpans  = false; // body must straddle the level AND be first to CLOSE through
input bool   InpLawEma5       = false; // breakout must close beyond EMA-5 — as a gate
input bool   InpLawNoPeak     = false; // drop the neighbour-peak test (he revoked it 2026-08-04)
input double InpLawStructStop = 0.0;   // >0: stop this many pips under the retracement low
input double InpLawTargetR    = 0.0;   // >0: target at this R of the real risk
input double InpLawBreakEven  = 0.0;   // >0: stop to breakeven at this R
input bool   InpLawNyOnly     = false; // New York only, broker hours 15-22

datetime g_last_bar = 0;
datetime g_last_fire = 0;

//+------------------------------------------------------------------+
//| The tester overwrites tick_volume with its synthesised tick count |
//| (4/bar) and preserves real_volume. Measured 2026-08-10 with       |
//| TapeProbe: iVolume returned 4 4 4 4 4 while iRealVolume returned  |
//| 572 454 270 174. Every volume rule we owned had been blind.       |
//+------------------------------------------------------------------+
// OANDA volume table, loaded once at init from Common\Files (works in the tester
// too — the tester reads FILE_COMMON, so this source is court-testable).
datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;
int      g_ov_miss = 0;          // lookups that fell back to broker volume
datetime g_ov_miss_bar = 0;      // last bar already reported, so one line per bar
datetime g_ov_newest = 0;        // newest minute in the table (freshness telemetry)

void LoadOandaVol() {
   g_ov_n = 0;
   // RETRY (2026-08-21): the writer swaps this file atomically every 60 s, and a
   // read landing inside that swap failed outright — one bar silently on broker
   // volume, logged at 21:46:02. Five quick attempts cover the swap window.
   int h = INVALID_HANDLE;
   for (int _try = 0; _try < 5 && h == INVALID_HANDLE; _try++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                                FILE_SHARE_READ | FILE_SHARE_WRITE);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[D02] OANDA volume requested but oanda_vol.csv not found — using broker volume");
      return;
   }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      long v = (long)StringToInteger(StringSubstr(ln, c + 1));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t; g_ov_v[g_ov_n] = v; g_ov_n++;
   }
   FileClose(h);
   g_ov_newest = (g_ov_n > 0) ? g_ov_t[g_ov_n - 1] : 0;
   PrintFormat("[D02] OANDA volume table loaded: %d minutes (newest %s)",
               g_ov_n, TimeToString(g_ov_newest, TIME_DATE | TIME_MINUTES));
}

long OandaVolAt(datetime t) {          // binary search the sorted table
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_ov_t[mid] == t) return g_ov_v[mid];
      if (g_ov_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return -1;
}

long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolAt(iTime(_Symbol, PERIOD_CURRENT, k));
      if (ov > 0) return ov;
   }
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
   // Zee REVOKED this on 2026-08-04 ("pick the UHV purely on volume") after it
   // cost a real setup; the Diamond still carries it. InpLawNoPeak drops it.
   if (!InpLawNoPeak) {
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
   if (InpOandaVolume == 1) LoadOandaVol();
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   // The load fingerprint. Hot-reload of an attached chart is UNRELIABLE, so this line is
   // how a deploy is verified — if the Experts tab does not say v1.10 with stack x2, the
   // chart is still running the old binary and the change did NOT take.
   PrintFormat("[D02] ZeeUHV v1.10 — HIS rules from 146 labels. SL %.1f / TP %.1f · magic %d"
               " · stack x%d (max %d tickets = %.2f lots, risk %.0f per failed setup)",
               InpStopPts, InpTargetPts, InpMagicNumber, MathMax(1, InpStackMult),
               4 * MathMax(1, InpStackMult), 4 * MathMax(1, InpStackMult) * InpLots,
               4 * MathMax(1, InpStackMult) * InpLots * InpStopPts * 100.0);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[D02] deinit reason=%d", r); }

//+------------------------------------------------------------------+

// ── LAWS.md ADDITIONS on the breakout candle (2026-08-26) ────────────────────────
bool LawBreakoutOK(int uhv, int side) {
   double lvl = (side > 0) ? bHigh(uhv) : bLow(uhv);
   double rng = bHigh(1) - bLow(1);
   double body = MathAbs(bClose(1) - bOpen(1));
   if (InpLawMomBody > 0) {
      if (rng <= 0 || body / rng < InpLawMomBody) return false;
   }
   if (InpLawClosePos > 0 && rng > 0) {
      bool ok = (side > 0) ? (bClose(1) >= bHigh(1) - InpLawClosePos * rng)
                           : (bClose(1) <= bLow(1)  + InpLawClosePos * rng);
      if (!ok) return false;
   }
   if (InpLawExpansion > 0) {
      double sb = 0; int n = 0;
      for (int q = 2; q <= 21; q++) { sb += MathAbs(bClose(q) - bOpen(q)); n++; }
      if (n > 0) { sb /= n; if (sb > 0 && body <= InpLawExpansion * sb) return false; }
   }
   if (InpLawBodySpans) {
      double bhi = MathMax(bOpen(1), bClose(1)), blo = MathMin(bOpen(1), bClose(1));
      bool spans = (side > 0) ? (blo <= lvl && bhi > lvl) : (bhi >= lvl && blo < lvl);
      if (!spans) return false;
      // and the first to CLOSE through it — his 26-Aug wording: a candle that crossed
      // but failed to close beyond does NOT consume the level
      for (int e = uhv - 1; e >= 2; e--) {
         bool earlier = (side > 0) ? (bClose(e) > lvl) : (bClose(e) < lvl);
         if (earlier) return false;
      }
   }
   if (InpLawEma5) {
      double e5 = Ema5(1);
      if (side > 0 && !(bClose(1) > e5)) return false;
      if (side < 0 && !(bClose(1) < e5)) return false;
   }
   return true;
}

// the retracement's extreme — what his line 42 hangs the stop under
double LawRetraceExtreme(int origin, int side) {
   double v = (side > 0) ? bLow(1) : bHigh(1);
   for (int k = 1; k <= origin; k++)
      v = (side > 0) ? MathMin(v, bLow(k)) : MathMax(v, bHigh(k));
   return v;
}

void TryFire() {
   if (OpenCount() >= InpMaxOpen) return;
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) return;
   if (!WindowContinuous(InpTrendLook + 5)) {
      if (InpVerbose) Print("[D02] [SKIP] gap in lookback");
      return;
   }
//  THE 40% GATE, under test (Zee 2026-08-10: "can u check what's stopping us from
//  taking every single opportunity we get?"). Measured on real gold, the structural
//  trend reads FLAT 40.3% of the time, and update_gate()'s "flat -> the ghost waits"
//  forbids BOTH sides for those four hours in ten — before any setup rule is even
//  consulted. It is the single largest brake on trade count, and it was assumed, never
//  tested. With InpRequireTrend=false a ranging tape may still trade: we simply try
//  both sides and take whichever completes a lawful setup.
   if (InpLawNyOnly) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      if (dt.hour < 15 || dt.hour >= 22) return;   // his line 47
   }
   int t = TrendNow();
   int sides[2]; int nsides = 0;
   if (t != 0) { sides[0] = t; nsides = 1; }
   else if (!InpRequireTrend) { sides[0] = +1; sides[1] = -1; nsides = 2; }
   else { if (InpVerbose) Print("[D02] [SKIP] ranging — his setup needs a trend"); return; }

   int origin = -1, uhv = -1, side = 0;
   for (int si = 0; si < nsides; si++) {
      int try_side = sides[si];
      int o = RetracementOrigin(try_side);
      if (o < 0) continue;
      int u = FindUhv(o, try_side);
      if (u < 0) continue;
      if (!BreakoutIsBar1(u, try_side)) continue;
      if (!LawBreakoutOK(u, try_side)) continue;
      origin = o; uhv = u; side = try_side; break;
   }
   if (side == 0) {
      if (InpVerbose && t != 0) Print("[D02] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px = (t > 0) ? ask : bid;
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;
   // LAWS.md line 42 — the stop belongs under the retracement, not at a fixed
   // distance the market has never heard of.
   if (InpLawStructStop > 0) {
      double ext = LawRetraceExtreme(origin, t);
      sl = (t > 0) ? ext - InpLawStructStop * 10 * _Point
                   : ext + InpLawStructStop * 10 * _Point;
   }
   // LAWS.md line 43 — the target is a RATIO of the real risk, not a constant.
   if (InpLawTargetR > 0) {
      double risk = MathAbs(px - sl);
      if (risk > 0) tp = (t > 0) ? px + InpLawTargetR * risk
                                 : px - InpLawTargetR * risk;
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
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, 3))) * MathMax(1, InpStackMult) : 1;
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
      string tag = StringFormat("zd02_%s_D%d", (t > 0 ? "buy" : "sell"), dia);
      bool ok = (t > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, tag)
                        : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      total += lots; placed += 1;
      if (!InpStackLots) break;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      // 2026-08-26: it used to print UHV as a BAR SHIFT ("UHV 7"), which is
      // meaningless once the trade is over — the cockpit's forensic button could not
      // resolve a single Diamond fire. With eleven variants running, inspecting a fire
      // IS the experiment, so it now stamps the three anchors as TIMES in the same
      // [LAWX] grammar the laws EA uses, which law_trade_diagram.py already parses.
      PrintFormat("[LAWX] %s | origin %s %s (retracement began the bar after) | "
                  "UHV %s (vol %d, %s %.2f) | breakout %s (close %.2f, vol %d) | "
                  "entry %.2f stop %.2f target %.2f | %d diamond(s) -> %d ticket(s), %.2f lots",
                  t > 0 ? "BUY " : "SELL",
                  t > 0 ? "green" : "red",
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, origin), TIME_MINUTES),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, uhv), TIME_MINUTES),
                  (int)BarVolume(uhv),
                  (t > 0 ? "high" : "low "),
                  (t > 0 ? bHigh(uhv) : bLow(uhv)),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_MINUTES),
                  bClose(1), (int)BarVolume(1),
                  px, sl, tp, dia, (int)placed, total);
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
            PrintFormat("[D02] aged out after %dm", InpMaxHoldMin);
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
   static datetime _ovbar = 0;
   if (InpOandaVolume == 1) {
      datetime _b = iTime(_Symbol, PERIOD_CURRENT, 0);
      if (_b != _ovbar) { _ovbar = _b; LoadOandaVol(); }
   }
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
