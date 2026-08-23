//+------------------------------------------------------------------+
//|  ZeeScalp.mq5 — THE BASE VIDEO, MECHANIZED                       |
//|                                                                  |
//|  Ahmad Umair Akhtar, "VSA Buy Side Scalping Strategy for Gold |  |
//|  1-Minute Setup Part 1" (base_video/, transcript                 |
//|  monitor/_loom_audio/yt_2mKEfO85D04.txt). Part 2 = the sell side.|
//|                                                                  |
//|  HIS RULES, IN HIS ORDER:                                        |
//|   1. New York session only.                                      |
//|   2. Scalp only WITH the 1-min trend — impulse breaks structure, |
//|      the retracement is the weak wave after it.                  |
//|   3. A retracement is REAL once the LAST BULLISH CANDLE'S LOW     |
//|      BREAKS (two candles are enough if that low went).           |
//|   4. Mark the LOUDEST VOLUME candle of that retracement.          |
//|   5. Enter when its HIGH breaks — on a candle that is LOW VOLUME |
//|      *AND* MOMENTUM. No momentum candle -> WAIT, do not take it. |
//|   6. Stop BELOW THAT CANDLE'S LOW (+ buffer). Structural.        |
//|   7. Target 1:2 of the risk.                                     |
//|   8. At 1:1, move the stop to breakeven — لازمی, mandatory.       |
//|                                                                  |
//|  WHY THIS EA EXISTS: ZeeUHV already shares his skeleton, but we  |
//|  invented the exits — a FIXED 5.0 stop for a FIXED 1.0 target,   |
//|  5:1 against us, breaking even only at ~83% win rate. His        |
//|  geometry is relative (risk R, take 2R, protect at 1R) and       |
//|  breaks even at ~33%. Same entry, inverted economics — and that  |
//|  shape has never been through our court.                         |
//|                                                                  |
//|  Magic 88174 · log tag [SCALP] · tickets zscalp_*                |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — from Ahmad Umair's method"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input group "── Identity & size ──"
input double InpLots         = 0.01;  // small by default: stops here are STRUCTURAL, not 5 pts
input long   InpMagic        = 88174;
input int    InpMaxOpen      = 1;

input group "── 1. Session (his: New York only) ──"
input bool   InpNyOnly       = true;  // broker hours below
input int    InpNyFromHour   = 15;    // broker 15:00 = 17:00 PKT (NY open)
input int    InpNyToHour     = 22;    // broker 22:00 = 00:00 PKT

input group "── 2. Trend ──"
input bool   InpRequireTrend = true;
input int    InpTrendLook    = 20;    // bars of structure
input int    InpPivot        = 2;     // swing strength
input bool   InpBuySide      = true;  // Part 1
input bool   InpSellSide     = true;  // Part 2, mirrored

input group "── 3-5. The setup ──"
input int    InpRetraceMax   = 20;    // how far back a retracement may reach
input double InpBrkBodyMult  = 1.0;   // MOMENTUM: breaker body >= this x avg body of last 20
input double InpBrkClosePos  = 0.55;  // and it must close in the top (1-x) of its own range

input group "── 6-8. His geometry ──"
input double InpStopBufPts   = 0.10;  // buffer beyond the UHV's low/high
input double InpTargetR      = 2.0;   // take 2R
input double InpBreakEvenR   = 1.0;   // move to breakeven at 1R (his mandatory rule)
input double InpMinStopPts   = 0.80;  // refuse absurdly tight structural stops
input double InpMaxStopPts   = 8.00;  // and absurdly wide ones

input group "── Volume source ──"
input int    InpOandaVolume  = 1;     // 1 = his eye (OANDA via oanda_vol.csv), 0 = broker
input bool   InpVerbose      = false;

datetime g_last_bar = 0;

//──────────────────────── OANDA volume table ────────────────────────
datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;

void LoadOandaVol() {
   g_ov_n = 0;
   int h = INVALID_HANDLE;
   for (int t = 0; t < 5 && h == INVALID_HANDLE; t++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) { Print("[SCALP] oanda_vol.csv not found — broker volume"); return; }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t;
      g_ov_v[g_ov_n] = (long)StringToInteger(StringSubstr(ln, c + 1));
      g_ov_n++;
   }
   FileClose(h);
}

long OandaVolAt(datetime t) {
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_ov_t[mid] == t) return g_ov_v[mid];
      if (g_ov_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return -1;
}

//──────────────────────── bar helpers ────────────────────────
double bOpen (int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh (int k) { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow  (int k) { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
double BodyHi(int k) { return MathMax(bOpen(k), bClose(k)); }
double BodyLo(int k) { return MathMin(bOpen(k), bClose(k)); }
bool   IsUp  (int k) { return bClose(k) > bOpen(k); }
bool   IsDn  (int k) { return bClose(k) < bOpen(k); }

long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolAt(iTime(_Symbol, PERIOD_CURRENT, k));
      if (ov > 0) return ov;
   }
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

//──────────────── 2. TREND — structure on the 1-minute ────────────────
// impulse breaks the left-side structure; we read it as HH+HL / LH+LL.
int TrendNow() {
   int hi1 = -1, hi2 = -1, lo1 = -1, lo2 = -1;
   for (int i = InpPivot + 1; i <= InpTrendLook && (hi2 < 0 || lo2 < 0); i++) {
      bool isHi = true, isLo = true;
      for (int j = i - InpPivot; j <= i + InpPivot; j++) {
         if (j == i) continue;
         if (bHigh(j) >= bHigh(i)) isHi = false;
         if (bLow(j)  <= bLow(i))  isLo = false;
      }
      if (isHi) { if (hi1 < 0) hi1 = i; else if (hi2 < 0) hi2 = i; }
      if (isLo) { if (lo1 < 0) lo1 = i; else if (lo2 < 0) lo2 = i; }
   }
   if (hi1 < 0 || hi2 < 0 || lo1 < 0 || lo2 < 0) return 0;
   bool hh = bHigh(hi1) > bHigh(hi2), hl = bLow(lo1) > bLow(lo2);
   bool lh = bHigh(hi1) < bHigh(hi2), ll = bLow(lo1) < bLow(lo2);
   if (hh && hl) return +1;
   if (lh && ll) return -1;
   return 0;
}

//──────── 3. THE RETRACEMENT — the last bullish candle whose LOW broke ────────
// his answer to "which wave is the retracement": it counts the moment the last
// with-trend candle's low (buy side) / high (sell side) is taken out.
int RetraceStart(int side) {
   for (int k = 2; k <= InpRetraceMax; k++) {
      bool withTrend = (side > 0) ? IsUp(k) : IsDn(k);
      if (!withTrend) continue;
      // was its low (buy) / high (sell) broken by any later candle?
      for (int j = k - 1; j >= 1; j--) {
         bool broken = (side > 0) ? (bLow(j) < bLow(k)) : (bHigh(j) > bHigh(k));
         if (broken) return k;                 // retracement runs from k to bar 1
      }
   }
   return -1;
}

//──────── 4. THE CANDLE — loudest volume inside that retracement ────────
int LoudestIn(int from, int to) {
   int best = -1; long bv = -1;
   for (int k = from; k >= to; k--) {
      long v = BarVolume(k);
      if (v > bv) { bv = v; best = k; }        // strict >: the OLDEST of equals wins
   }
   return best;
}

//──────── 5. THE BREAK — low volume AND momentum, else WAIT ────────
bool BreakerIsBar1(int uhv, int side) {
   if (uhv <= 1) return false;
   bool wantUp = (side > 0);
   if (wantUp && !IsUp(1)) return false;
   if (!wantUp && !IsDn(1)) return false;
   // body must CLOSE beyond the loud candle's extreme (body, not wick — Zee's law)
   bool crossed = wantUp ? (BodyHi(1) > bHigh(uhv)) : (BodyLo(1) < bLow(uhv));
   if (!crossed) return false;
   // an earlier candle already crossed -> this one is late
   for (int k = uhv - 1; k >= 2; k--) {
      bool earlier = wantUp ? (BodyHi(k) > bHigh(uhv)) : (BodyLo(k) < bLow(uhv));
      if (earlier) return false;
   }
   if (BarVolume(1) >= BarVolume(uhv)) return false;          // must be QUIETER
   // MOMENTUM — his explicit requirement, and the reason he waits when it is absent
   if (InpBrkBodyMult > 0) {
      double avg = 0; int got = 0;
      for (int q = 2; q <= 21; q++) { avg += MathAbs(bClose(q) - bOpen(q)); got++; }
      if (got > 0) avg /= got;
      if (avg > 0 && MathAbs(bClose(1) - bOpen(1)) < avg * InpBrkBodyMult) return false;
   }
   if (InpBrkClosePos > 0) {
      double rng = bHigh(1) - bLow(1);
      if (rng > 0) {
         double pos = wantUp ? (bClose(1) - bLow(1)) / rng : (bHigh(1) - bClose(1)) / rng;
         if (pos < InpBrkClosePos) return false;
      }
   }
   return true;
}

//──────────────── 8. BREAKEVEN AT 1R — his mandatory rule ────────────────
void ManageBreakEven() {
   if (InpBreakEvenR <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
      bool isBuy   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double risk  = isBuy ? (entry - sl) : (sl - entry);
      if (risk <= 0) continue;
      if (MathAbs(sl - entry) < 0.02) continue;                 // already at breakeven
      double gained = isBuy ? (cur - entry) : (entry - cur);
      if (gained >= risk * InpBreakEvenR)
         trade.PositionModify(t, NormalizeDouble(entry, _Digits), tp);
   }
}

int OpenCount() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagic) n++;
   }
   return n;
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   if (InpOandaVolume == 1) LoadOandaVol();
   PrintFormat("[SCALP] ZeeScalp v1.00 — Ahmad Umair's rules. structural stop below the "
               "loud candle · %.1fR target · breakeven at %.1fR · momentum breakout "
               "(body>=%.1fx, close>=%.2f) · NY %s · magic %d · %s volume",
               InpTargetR, InpBreakEvenR, InpBrkBodyMult, InpBrkClosePos,
               InpNyOnly ? "only" : "off", (int)InpMagic,
               (InpOandaVolume == 1 && g_ov_n > 0) ? "OANDA" : "broker");
   return INIT_SUCCEEDED;
}

void OnTick() {
   ManageBreakEven();                          // every tick: 1R must not be missed

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   if (InpOandaVolume == 1) LoadOandaVol();    // keep his eye current

   if (OpenCount() >= InpMaxOpen) return;
   if (InpNyOnly) {
      int hh = (int)((TimeCurrent() / 3600) % 24);
      if (hh < InpNyFromHour || hh >= InpNyToHour) return;
   }

   int t = TrendNow();
   if (InpRequireTrend && t == 0) return;
   int sides[2]; int ns = 0;
   if (t > 0 && InpBuySide) { sides[ns++] = +1; }
   if (t < 0 && InpSellSide) { sides[ns++] = -1; }
   if (t == 0 && !InpRequireTrend) {
      if (InpBuySide)  sides[ns++] = +1;
      if (InpSellSide) sides[ns++] = -1;
   }

   for (int s = 0; s < ns; s++) {
      int side = sides[s];
      int rstart = RetraceStart(side);
      if (rstart < 0) continue;
      int uhv = LoudestIn(rstart, 2);
      if (uhv < 2) continue;
      if (!BreakerIsBar1(uhv, side)) continue;

      MqlTick tk;
      if (!SymbolInfoTick(_Symbol, tk)) return;
      double px   = (side > 0) ? tk.ask : tk.bid;
      double stop = (side > 0) ? bLow(uhv) - InpStopBufPts : bHigh(uhv) + InpStopBufPts;
      double risk = MathAbs(px - stop);
      if (risk < InpMinStopPts || risk > InpMaxStopPts) {
         if (InpVerbose) PrintFormat("[SCALP] structural stop %.2f pts out of band — skipped", risk);
         continue;
      }
      double tp = (side > 0) ? px + risk * InpTargetR : px - risk * InpTargetR;
      string tag = (side > 0) ? "zscalp_buy" : "zscalp_sell";
      bool ok = (side > 0) ? trade.Buy(InpLots, _Symbol, 0, stop, tp, tag)
                           : trade.Sell(InpLots, _Symbol, 0, stop, tp, tag);
      if (ok)
         PrintFormat("[SCALP] %s @%.2f — loud candle bar %d (vol %d) · risk %.2f pts · "
                     "stop %.2f · target %.2f (%.1fR) · breaker body %.2f",
                     side > 0 ? "BUY" : "SELL", px, uhv, (int)BarVolume(uhv), risk,
                     stop, tp, InpTargetR, MathAbs(bClose(1) - bOpen(1)));
      return;
   }
}

double OnTester() {
   double net = TesterStatistics(STAT_PROFIT);
   int n = (int)TesterStatistics(STAT_TRADES);
   int w = (int)TesterStatistics(STAT_PROFIT_TRADES);
   PrintFormat("[SCALP] ==== %d trades · %dW/%dL (%.1f%%) · net %.2f ====",
               n, w, n - w, n > 0 ? 100.0 * w / n : 0.0, net);
   return net;
}
