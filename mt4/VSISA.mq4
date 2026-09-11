//+------------------------------------------------------------------+
//|  VSISA.mq4 — Volume Spread Imbalance Shift Analysis, MT4 port      |
//|                                                                    |
//|  Zee 2026-09-11: "we want to compile and attach this EA VSISA to    |
//|  ... AXI MT4".                                                      |
//|                                                                    |
//|  THIS IS A PORT, NOT A RECOMPILE. MQL4 and MQL5 are different       |
//|  languages: no CTrade, no PositionSelectByTicket, no iRealVolume.   |
//|  Every rule and every default below is kept identical to            |
//|  mt5/VSISA.mq5 v1.00 so the two can be compared; only the platform  |
//|  plumbing differs. If you change a rule, change it in BOTH files.   |
//|                                                                    |
//|  ONE PIECE OF LUCK: the MT5 build was measured reading BROKER TICK  |
//|  COUNT (iRealVolume returned 0 reads for gold CFD against 8,006,496 |
//|  tick-count fallbacks). MT4's Volume[] IS tick count, so the volume |
//|  semantics carry over exactly rather than being approximated.       |
//|                                                                    |
//|  THE ENGINE, UNCHANGED:                                            |
//|    1. a CLUSTER of 2 same-direction bars on big volume — effort;    |
//|    2. a REACTION bar closing the other way — names the side;        |
//|    3. that reaction on LOW volume — the resting orders are gone;    |
//|    4. enter at its close, stop past the extreme, target 2.5R.       |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

//--- money -----------------------------------------------------------------
input double InpLots        = 0.10;   // InpLots - lot size per ticket
input int    InpTickets     = 1;      // InpTickets - tickets per decision
input int    InpMagicNumber = 88201;  // InpMagicNumber - VSISA
input int    InpMaxOpen     = 1;      // InpMaxOpen - max concurrent decisions
input int    InpSlippage    = 30;     // InpSlippage - points

//--- THE FEED --------------------------------------------------------------
// MT4 reads the same shared Common\Files the OANDA bridge writes to, so this
// works here exactly as it does on MT5. Default 0: every receipt VSISA owns was
// earned on broker tick volume, and OANDA coverage is not yet continuous enough
// to re-earn them (23 days, with whole-session outages).
input int    InpOandaVolume = 0;      // InpOandaVolume - 1 = judge on OANDA volume
input bool   InpOandaStrict = true;   // InpOandaStrict - missing minute = no trade

//--- LAW 4: the cluster ----------------------------------------------------
input int    InpClusterBars = 2;      // InpClusterBars - 2 or 3 effort bars
input bool   InpRisingVol   = false;  // InpRisingVol - each cluster bar louder
input bool   InpStrictDir   = true;   // InpStrictDir - every cluster bar closes its way

//--- LAW 5: what "big" means -----------------------------------------------
input int    InpVolLookback = 100;    // InpVolLookback - bars defining "recent"
input int    InpBigMode     = 1;      // InpBigMode - 0 every bar loud, 1 only loudest
input double InpBigPct      = 0.80;   // InpBigPct - >= this x lookback max
input double InpBigAvg      = 1.20;   // InpBigAvg - and >= this x lookback average

//--- LAW 3: the low-volume reaction. THE TRIGGER. --------------------------
input int    InpQuietRef    = 0;      // InpQuietRef - 0 vs CLUSTER, 1 vs lookback avg
input double InpLowVolPct   = 1.00;   // InpLowVolPct - reaction <= this x reference
input double InpBodyFrac    = 0.35;   // InpBodyFrac - body >= this x its range
input bool   InpEngulf      = false;  // InpEngulf - reaction must engulf last cluster bar

//--- LAW 8: geometry -------------------------------------------------------
input int    InpSlBufPts    = 30;     // InpSlBufPts - points beyond the extreme
input int    InpMinSlPts    = 60;     // InpMinSlPts - floor
input int    InpMaxSlPts    = 900;    // InpMaxSlPts - refuse absurd risk
input double InpTargetR     = 2.5;    // InpTargetR - TP as a multiple of risk
input double InpBreakEvenR  = 1.0;    // InpBreakEvenR - >0: stop to entry at this R

//--- the laws that ship OFF ------------------------------------------------
input int    InpWickMode    = 0;      // InpWickMode - 0 off, 1 require, 2 override
input double InpWickFrac    = 0.35;   // InpWickFrac
input bool   InpAnomaly     = false;  // InpAnomaly
input double InpAnomalyMax  = 0.70;   // InpAnomalyMax
input bool   InpFakeBreak   = false;  // InpFakeBreak
input int    InpSweepLook   = 30;     // InpSweepLook
input int    InpConfirmMode = 0;      // InpConfirmMode - 1 = no-supply test entry
input double InpTestVolPct  = 0.90;   // InpTestVolPct

//--- LAW 9: higher-timeframe trend -----------------------------------------
input int    InpTrendTF     = 60;     // InpTrendTF - 0 off, 15 M15, 60 H1
input int    InpTrendBars   = 20;     // InpTrendBars

//--- session / housekeeping ------------------------------------------------
input int    InpSessFrom    = 0;      // InpSessFrom - broker hour, inclusive
input int    InpSessTo      = 24;     // InpSessTo - broker hour, exclusive
input int    InpCoolBars    = 3;      // InpCoolBars
input bool   InpBuys        = true;   // InpBuys
input bool   InpSells       = true;   // InpSells
input bool   InpVerbose     = true;   // InpVerbose

//--- state -----------------------------------------------------------------
datetime g_last_bar = 0;
int      g_cool     = 0;
int      g_fires    = 0;
double   g_pt       = 0;      // point scaled for 3/5-digit quoting

int g_seen = 0, g_rej_dir = 0, g_rej_loud = 0, g_rej_rise = 0, g_rej_anom = 0;
int g_rej_fake = 0, g_rej_react = 0, g_rej_body = 0, g_rej_quiet = 0, g_rej_trend = 0;
int g_rej_test = 0;
long g_ov_hit = 0, g_tick_hit = 0;

//--- OANDA table -----------------------------------------------------------
datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;

//+------------------------------------------------------------------+
//| Bar accessors — MT4 signatures                                    |
//+------------------------------------------------------------------+
double bHigh(int k)  { return iHigh (Symbol(), 0, k); }
double bLow(int k)   { return iLow  (Symbol(), 0, k); }
double bOpen(int k)  { return iOpen (Symbol(), 0, k); }
double bClose(int k) { return iClose(Symbol(), 0, k); }
double bRange(int k) { return bHigh(k) - bLow(k); }
double bBody(int k)  { return MathAbs(bClose(k) - bOpen(k)); }
bool   bUp(int k)    { return bClose(k) > bOpen(k); }
bool   bDown(int k)  { return bClose(k) < bOpen(k); }

//+------------------------------------------------------------------+
//| OANDA volume table — same file, same format as the MT5 build      |
//+------------------------------------------------------------------+
void LoadOandaVol() {
   g_ov_n = 0;
   int h = INVALID_HANDLE;
   for (int t = 0; t < 5 && h == INVALID_HANDLE; t++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON |
                   FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
      if (h == INVALID_HANDLE && !IsTesting()) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[VSISA] OANDA requested but oanda_vol.csv not found - using tick volume");
      return;
   }
   ArrayResize(g_ov_t, 8192);
   ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string sT = FileReadString(h);
      if (FileIsLineEnding(h) || sT == "") continue;
      string sV = FileReadString(h);
      datetime tt = StrToTime(sT);
      if (tt <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096);
         ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = tt;
      g_ov_v[g_ov_n] = (long)StrToInteger(sV);
      g_ov_n++;
   }
   FileClose(h);
   PrintFormat("[VSISA] OANDA volume table loaded: %d minutes", g_ov_n);
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

// A bar's volume is the SUM of the minutes it spans. Under strict mode one missing
// minute voids the whole bar: half a candle of his volume is not his candle.
long OandaVolSpan(datetime t, int mins) {
   if (mins <= 1) return OandaVolAt(t);
   long sum = 0;
   for (int m = 0; m < mins; m++) {
      long v = OandaVolAt(t + m * 60);
      if (v <= 0) {
         if (InpOandaStrict) return -1;
         continue;
      }
      sum += v;
   }
   if (sum > 0) return sum;
   return -1;
}

// MT4's Volume[] IS the tick count, which is exactly what the MT5 build was measured
// to be using. No fallback chain is needed here — there is only ever one number.
long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolSpan(iTime(Symbol(), 0, k), Period());
      if (ov > 0) { g_ov_hit++; return ov; }
   }
   if (InpOandaVolume == 1 && InpOandaStrict) return -1;
   g_tick_hit++;
   return (long)iVolume(Symbol(), 0, k);
}

//+------------------------------------------------------------------+
bool VolStats(int from, long &vmax, double &vavg, double &ravg) {
   vmax = 0; vavg = 0; ravg = 0;
   int n = 0;
   for (int k = from; k < from + InpVolLookback; k++) {
      long v = BarVolume(k);
      double r = bRange(k);
      if (v <= 0) continue;
      if (v > vmax) vmax = v;
      vavg += (double)v;
      ravg += r;
      n++;
   }
   if (InpOandaVolume == 1 && InpOandaStrict && n < InpVolLookback) return false;
   if (n < InpVolLookback / 2 || vmax <= 0) return false;
   vavg /= n;
   ravg /= n;
   return true;
}

int TrendDir() {
   if (InpTrendTF <= 0) return 0;
   int tf = PERIOD_H1;
   if (InpTrendTF == 15) tf = PERIOD_M15;
   else if (InpTrendTF == 30) tf = PERIOD_M30;
   else if (InpTrendTF == 60) tf = PERIOD_H1;
   else tf = PERIOD_H4;
   int n = MathMax(3, InpTrendBars);
   double now  = iClose(Symbol(), tf, 1);
   double then = iClose(Symbol(), tf, n);
   if (now == 0 || then == 0) return 0;
   if (now > then) return 1;
   if (now < then) return -1;
   return 0;
}

bool InSession() {
   int h = TimeHour(TimeCurrent());
   if (InpSessFrom <= InpSessTo) return (h >= InpSessFrom && h < InpSessTo);
   return (h >= InpSessFrom || h < InpSessTo);
}

int OpenDecisions() {
   int n = 0;
   for (int i = OrdersTotal() - 1; i >= 0; i--) {
      if (!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if (OrderSymbol() != Symbol()) continue;
      if (OrderMagicNumber() != InpMagicNumber) continue;
      if (OrderType() == OP_BUY || OrderType() == OP_SELL) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| The setup. side = +1 buy, -1 sell.                                |
//+------------------------------------------------------------------+
bool Detect(int side, double &sl_level, string &why) {
   int nb = MathMax(2, MathMin(3, InpClusterBars));
   int r  = (InpConfirmMode == 1) ? 3 : 1;   // index of the REACTION bar
   int c0 = r + 1;                            // newest CLUSTER bar
   if (Bars < c0 + nb + InpVolLookback + 2) return false;

   long vmax; double vavg, ravg;
   if (!VolStats(c0 + nb, vmax, vavg, ravg)) return false;
   g_seen++;

   long vsum = 0;
   double worst_loud = 1.0, best_loud_bar = 0.0;
   double ext = (side > 0) ? bLow(c0) : bHigh(c0);
   for (int q = 0; q < nb; q++) {
      int k = c0 + q;
      if (InpStrictDir) {
         if (side > 0 && !bDown(k)) { g_rej_dir++; return false; }
         if (side < 0 && !bUp(k))   { g_rej_dir++; return false; }
      }
      long v = BarVolume(k);
      if (v <= 0) return false;

      double loud = (double)v / (double)vmax;
      if (q == 0 || loud < worst_loud) worst_loud = loud;
      if (loud > best_loud_bar) best_loud_bar = loud;
      if (InpBigMode == 0 && (double)v < InpBigPct * (double)vmax) {
         g_rej_loud++; return false;
      }
      if ((double)v < InpBigAvg * vavg) { g_rej_loud++; return false; }

      if (InpRisingVol && q > 0) {
         long prev = BarVolume(k - 1);       // k-1 is the NEWER bar
         if (prev <= v) { g_rej_rise++; return false; }
      }
      vsum += v;
      if (side > 0) ext = MathMin(ext, bLow(k));
      else          ext = MathMax(ext, bHigh(k));
   }
   double vcluster = (double)vsum / nb;
   if (InpBigMode == 1 && best_loud_bar < InpBigPct) { g_rej_loud++; return false; }

   if (InpAnomaly) {
      if (ravg <= 0) return false;
      if (bRange(c0) > InpAnomalyMax * ravg) { g_rej_anom++; return false; }
   }

   if (InpFakeBreak) {
      double lvl = (side > 0) ? bLow(c0 + nb) : bHigh(c0 + nb);
      for (int k2 = c0 + nb; k2 < c0 + nb + InpSweepLook; k2++) {
         if (side > 0) lvl = MathMin(lvl, bLow(k2));
         else          lvl = MathMax(lvl, bHigh(k2));
      }
      if (side > 0) {
         if (ext >= lvl)       { g_rej_fake++; return false; }
         if (bClose(r) <= lvl) { g_rej_fake++; return false; }
      } else {
         if (ext <= lvl)       { g_rej_fake++; return false; }
         if (bClose(r) >= lvl) { g_rej_fake++; return false; }
      }
   }

   //--- LAW 2: the reaction names the side.
   if (side > 0 && !bUp(r))   { g_rej_react++; return false; }
   if (side < 0 && !bDown(r)) { g_rej_react++; return false; }

   double rng1 = bRange(r);
   if (rng1 <= 0) return false;
   if (bBody(r) < InpBodyFrac * rng1) { g_rej_body++; return false; }

   if (InpEngulf) {
      if (side > 0 && bClose(r) <= bHigh(c0)) return false;
      if (side < 0 && bClose(r) >= bLow(c0))  return false;
   }

   //--- LAW 3: THE TRIGGER.
   long v1 = BarVolume(r);
   if (v1 <= 0) return false;
   double vref = (InpQuietRef == 1) ? vavg : vcluster;
   bool quiet = ((double)v1 <= InpLowVolPct * vref);

   //--- LAW 6: the wick.
   double upper = bHigh(r) - MathMax(bOpen(r), bClose(r));
   double lower = MathMin(bOpen(r), bClose(r)) - bLow(r);
   bool wick = (side > 0) ? (lower >= InpWickFrac * rng1)
                          : (upper >= InpWickFrac * rng1);
   if (InpWickMode == 1 && !wick) { g_rej_quiet++; return false; }
   if (!quiet) {
      if (!(InpWickMode == 2 && wick)) { g_rej_quiet++; return false; }
   }

   //--- the no-supply test
   if (InpConfirmMode == 1) {
      long vt = BarVolume(2);
      if (vt <= 0) { g_rej_test++; return false; }
      if ((double)vt > InpTestVolPct * vref) { g_rej_test++; return false; }
      if (side > 0) {
         if (bLow(2) <= ext)         { g_rej_test++; return false; }
         if (!bUp(1))                { g_rej_test++; return false; }
         if (bClose(1) <= bClose(2)) { g_rej_test++; return false; }
      } else {
         if (bHigh(2) >= ext)        { g_rej_test++; return false; }
         if (!bDown(1))              { g_rej_test++; return false; }
         if (bClose(1) >= bClose(2)) { g_rej_test++; return false; }
      }
   }

   //--- LAW 9
   int td = TrendDir();
   if (td != 0 && td != side) { g_rej_trend++; return false; }

   //--- LAW 8: the stop sits just past the extreme the setup defended.
   if (side > 0) ext = MathMin(ext, bLow(r));
   else          ext = MathMax(ext, bHigh(r));
   if (InpConfirmMode == 1) {
      for (int k3 = 1; k3 <= 2; k3++) {
         if (side > 0) ext = MathMin(ext, bLow(k3));
         else          ext = MathMax(ext, bHigh(k3));
      }
   }
   sl_level = (side > 0) ? ext - InpSlBufPts * g_pt : ext + InpSlBufPts * g_pt;

   why = StringFormat("cluster %d bars vol %.0f (max %d avg %.0f) | reaction vol %d "
                      "= %.2fx%s%s", nb, vcluster, (int)vmax, vavg, (int)v1,
                      (double)v1 / MathMax(1.0, vref),
                      quiet ? " QUIET" : " LOUD", wick ? " +wick" : "");
   return true;
}

//+------------------------------------------------------------------+
void Fire(int side, double sl_level, string why) {
   RefreshRates();
   double entry = (side > 0) ? Ask : Bid;
   double risk  = MathAbs(entry - sl_level);

   double minr = InpMinSlPts * g_pt;
   double maxr = InpMaxSlPts * g_pt;

   // THE BROKER'S OWN FLOOR. MT4 rejects a stop closer than MODE_STOPLEVEL with error
   // 130, and on gold that level is often wider than our 60-point floor. Honour the
   // larger of the two rather than firing orders the server will refuse.
   double stopmin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if (stopmin > minr) minr = stopmin;

   if (risk < minr) {
      risk = minr;
      sl_level = (side > 0) ? entry - risk : entry + risk;
   }
   if (risk > maxr) {
      if (InpVerbose)
         PrintFormat("[VSISA] refused: risk %.0f pts > cap %d", risk / g_pt, InpMaxSlPts);
      return;
   }

   double tp = 0;
   if (InpTargetR > 0)
      tp = (side > 0) ? entry + InpTargetR * risk : entry - InpTargetR * risk;

   sl_level = NormalizeDouble(sl_level, Digits);
   if (tp > 0) tp = NormalizeDouble(tp, Digits);

   int placed = 0;
   for (int i = 0; i < MathMax(1, InpTickets); i++) {
      RefreshRates();
      double px = (side > 0) ? Ask : Bid;
      int ticket = OrderSend(Symbol(), (side > 0) ? OP_BUY : OP_SELL, InpLots, px,
                             InpSlippage, sl_level, tp,
                             StringFormat("vsisa_%d_%d", g_fires, i),
                             InpMagicNumber, 0, (side > 0) ? clrDodgerBlue : clrTomato);
      if (ticket > 0) { placed++; continue; }

      // ECN brokers reject SL/TP on the opening order (error 130). Open bare, then
      // attach the levels — otherwise the EA would look silently dead on such an account.
      int err = GetLastError();
      if (err == 130 || err == 145) {
         ticket = OrderSend(Symbol(), (side > 0) ? OP_BUY : OP_SELL, InpLots, px,
                            InpSlippage, 0, 0,
                            StringFormat("vsisa_%d_%d", g_fires, i),
                            InpMagicNumber, 0, clrGray);
         if (ticket > 0 && OrderSelect(ticket, SELECT_BY_TICKET)) {
            if (!OrderModify(ticket, OrderOpenPrice(), sl_level, tp, 0, clrGray))
               PrintFormat("[VSISA] opened %d but OrderModify failed: %d",
                           ticket, GetLastError());
            placed++;
            continue;
         }
      }
      PrintFormat("[VSISA] OrderSend failed: %d", err);
   }
   if (placed == 0) return;

   g_fires++;
   g_cool = InpCoolBars;
   if (InpVerbose)
      PrintFormat("[VSISA] #%d %s @ %s SL %s (%.0f pts) TP %s (%.1fR) | %s",
                  g_fires, (side > 0) ? "BUY" : "SELL",
                  DoubleToStr(entry, Digits), DoubleToStr(sl_level, Digits),
                  risk / g_pt, DoubleToStr(tp, Digits), InpTargetR, why);
}

//+------------------------------------------------------------------+
void BreakEvenCheck() {
   if (InpBreakEvenR <= 0) return;
   for (int i = OrdersTotal() - 1; i >= 0; i--) {
      if (!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if (OrderSymbol() != Symbol()) continue;
      if (OrderMagicNumber() != InpMagicNumber) continue;
      int type = OrderType();
      if (type != OP_BUY && type != OP_SELL) continue;

      double open = OrderOpenPrice();
      double sl   = OrderStopLoss();
      if (sl == 0) continue;
      double risk = MathAbs(open - sl);
      if (risk <= 0) continue;

      double px = (type == OP_BUY) ? Bid : Ask;
      double gained = (type == OP_BUY) ? (px - open) : (open - px);
      if (gained < InpBreakEvenR * risk) continue;
      if (type == OP_BUY  && sl >= open) continue;
      if (type == OP_SELL && sl <= open) continue;

      if (!OrderModify(OrderTicket(), open, NormalizeDouble(open, Digits),
                       OrderTakeProfit(), 0, clrGoldenrod) && InpVerbose)
         PrintFormat("[VSISA] breakeven modify failed on %d: %d",
                     OrderTicket(), GetLastError());
   }
}

//+------------------------------------------------------------------+
int OnInit() {
   // 3 AND 5 DIGIT QUOTING. On a 3-digit gold feed Point is 0.001, so "30 points"
   // would silently become a tenth of the intended stop — tight enough that the
   // spread alone would take it. Scale once, here, and use g_pt everywhere.
   g_pt = Point;
   if (Digits == 3 || Digits == 5) g_pt = Point * 10.0;

   if (InpOandaVolume == 1) LoadOandaVol();

   PrintFormat("[VSISA] MT4 v1.00 - cluster %d bars (bigmode %d, big>=%.2fxmax/%.2fxavg) "
               "| reaction<=%.2fx %s | TP %.1fR, BE %.1fR, SL buf %d pts (floor %d) | "
               "trendTF %d, confirm %d, wick %d, anomaly %d, fake %d | feed %s | "
               "%.2f lots x%d | magic %d | %s Digits=%d point=%s",
               InpClusterBars, InpBigMode, InpBigPct, InpBigAvg, InpLowVolPct,
               (InpQuietRef == 1) ? "avg" : "cluster",
               InpTargetR, InpBreakEvenR, InpSlBufPts, InpMinSlPts,
               InpTrendTF, InpConfirmMode, InpWickMode, (int)InpAnomaly,
               (int)InpFakeBreak,
               (InpOandaVolume == 1) ? (InpOandaStrict ? "OANDA-STRICT" : "OANDA")
                                     : "BROKER-TICKS",
               InpLots, InpTickets, InpMagicNumber, Symbol(), Digits,
               DoubleToStr(g_pt, 5));

   if (Period() != PERIOD_M5)
      Print("[VSISA] WARNING: this chart is not M5. Every receipt VSISA owns is M5; "
            "attach it to an M5 chart.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   PrintFormat("[VSISA] stopped, %d decisions taken", g_fires);
   PrintFormat("[VSISA] FUNNEL candidates %d | dir %d | not loud %d | not rising %d | "
               "anomaly %d | fake %d | reaction %d | body %d | not quiet %d | test %d "
               "| trend %d | FIRED %d",
               g_seen, g_rej_dir, g_rej_loud, g_rej_rise, g_rej_anom, g_rej_fake,
               g_rej_react, g_rej_body, g_rej_quiet, g_rej_test, g_rej_trend, g_fires);
   PrintFormat("[VSISA] VOLUME SOURCE OANDA %d | MT4 tick volume %d",
               (int)g_ov_hit, (int)g_tick_hit);
}

void OnTick() {
   BreakEvenCheck();

   datetime t = iTime(Symbol(), 0, 0);
   if (t == g_last_bar) return;
   g_last_bar = t;

   if (g_cool > 0) { g_cool--; return; }
   if (!InSession()) return;
   if (OpenDecisions() >= InpMaxOpen) return;
   if (!IsTradeAllowed()) return;

   double sl = 0;
   string why = "";
   if (InpBuys  && Detect(+1, sl, why)) { Fire(+1, sl, why); return; }
   if (InpSells && Detect(-1, sl, why)) { Fire(-1, sl, why); return; }
}
//+------------------------------------------------------------------+
