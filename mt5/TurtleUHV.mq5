//+------------------------------------------------------------------+
//|  TurtleUHV.mq5 — the TradingView indicator (turtle.pine) as an EA |
//|  (2026-10-09), so the strategy can be backtested in MT5's         |
//|  Strategy Tester on any period, and traded without TradingView.   |
//|                                                                  |
//|  A line-by-line port of the signal logic for the settings on Zee's|
//|  chart: bypass retracements (lookback 8) with backdating, the     |
//|  impulse-candle path (EMA 34/89 trend engine), camel humps (hump  |
//|  size 1, gating retracement starts + signals, cancelling unfired  |
//|  setups), UHV = loudest candle of the retracement with body >= 50%,|
//|  1-hour candle aligned, cooldown 3, Instant at Breakout from the   |
//|  trigger ARMED at the previous close. Steps run in the indicator's |
//|  own order inside each candle (it changes edge cases).            |
//|                                                                  |
//|  Settings the port does NOT implement (they are off on the chart, |
//|  and the EA refuses to start if asked for them): sweep, loud-UHV, |
//|  wick/wide-spread UHV, climax background, momentum, tick velocity,|
//|  sessions, ranging/ADX, structural trend, early bounce, offsets.  |
//|                                                                  |
//|  Volume (LAWS.md: judge on OANDA volume): InpVolSource 0 = this   |
//|  symbol's own volume (a custom symbol loaded with OANDA candles   |
//|  carries OANDA volume); 1 = OANDA volume from Common\Files\         |
//|  oanda_vol.csv (time_utc,volume), falling back to broker volume.  |
//+------------------------------------------------------------------+
#property copyright "Zee"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input group "── Indicator settings (as on Zee's chart) ──"
input int    InpBRWLB       = 8;      // bypass lookback (bars)
input int    InpCamPiv      = 1;      // camel hump size
input bool   InpCamOn       = true;   // camel gates signals
input bool   InpCamRet      = true;   // camel gates retracement starts + cancels setups
input bool   InpUhvBodyOn   = true;   // UHV body strength rule
input double InpUhvBodyPct  = 50;     // min UHV body % of range
input bool   InpHTF60       = true;   // 1-hour candle must agree (uHTD = 60)
input int    InpCooldown    = 3;      // bars between signals (uCd)
input int    InpDir         = 0;      // 0 both, 1 buys only, -1 sells only

input group "── Data ──"
input int    InpVolSource   = 0;      // 0 this symbol's volume, 1 OANDA file
input string InpOandaFile   = "oanda_vol.csv";
input int    InpUtcOffsetH  = 0;      // this symbol's time minus UTC (custom OANDA symbol: 0; Blueberry: 3)
input bool   InpExport      = true;   // write every signal to Common\Files\ea_signals.csv
input bool   InpExportState = false;  // write end-of-candle state to Common\Files\ea_state.csv (parity checks)

input group "── Trading (off = signals only) ──"
input bool   InpTrade       = false;
input double InpLots        = 0.10;
input double InpTPPrice     = 1.50;   // take-profit distance (price)
input double InpSLPrice     = 3.50;   // stop-loss distance (price)
input int    InpWindowMin   = 5;      // close this many minutes after the signal candle
input double InpMaxSpread   = 0.60;
input int    InpMagic       = 88601;
input bool   InpOnlyTVMinutes = false; // DIAGNOSTIC: trade only minutes listed in tv_signals.csv (tests the replay's selection effect)

input group "── Funded-account guards (live) ──"
input bool   InpGuards        = false;
input double InpInitialBalance = 25000;
input double InpMaxLossPct     = 10;
input double InpFloorBuffer    = 300;
input double InpDailyStop      = 500;
input double InpDailyHardClose = 800;
input int    InpNewsMin        = 3;

#define NA EMPTY_VALUE
bool IsNa(double x) { return x == EMPTY_VALUE; }

// ── persistent indicator state (names follow turtle.pine) ──
bool   iR = false, rwb = false, lb = false, ibT = false, uF = false, uWB = false, uWSp = false;
int    ibTBar = -1, uBar = -1, rSB = -1, luSB = -999, k = -1;
double rCeil = NA, rFlr = NA, rIBLo = NA, rIBHi = NA, uVol = 0, uHi = NA, uLo = NA, uSl = NA, bL = NA, rceLo = NA, rceHi = NA;
// camel
int    czT = 0, czHB = -1, czL0B = -1, czLB = -1, czTr = 0, czStk = 0, czStk0 = 0;
double czHV = NA, czL0V = NA, czLV = NA;
// trend engine
double e34 = NA, e89 = NA, e34p = NA, atr = NA, atrSma = NA, volSma = NA;
double trBuf[], atrBuf[], volBuf[], c34[], c89[];
// armed setup (computed at a candle's close, used on the next candle)
bool   armB = false, armE = false;
double trigB = NA, trigE = NA;
datetime armUT = 0;
datetime lastBar = 0;
MqlRates R[];                 // R[0] = the candle being processed, R[j] = j candles earlier
int    nR = 0;
// OANDA volume
datetime ovT[]; long ovV[]; int ovN = 0, ovMiss = 0;
// trading
datetime firedCandle = 0, exitAt = 0;
ulong  pos = 0;
int    nSig = 0, nTrades = 0;
double day0 = 0; datetime dayD = 0; bool halted = false;
int    stH = INVALID_HANDLE;
long   tvMin[]; int tvN = 0;

double O(int j) { return R[j].open; }  double H(int j) { return R[j].high; }
double L(int j) { return R[j].low; }   double C(int j) { return R[j].close; }
datetime T(int j) { return R[j].time; }

long OandaVol(datetime t) {
   datetime u = t - InpUtcOffsetH * 3600;
   int lo = 0, hi = ovN - 1;
   while (lo <= hi) { int m = (lo + hi) / 2; if (ovT[m] == u) return ovV[m]; if (ovT[m] < u) lo = m + 1; else hi = m - 1; }
   return -1;
}
double V(int j) {
   if (InpVolSource == 1) { long v = OandaVol(T(j)); if (v >= 0) return (double)v; ovMiss++; }
   // The Strategy Tester overwrites tick_volume with its own synthetic tick count (4 per
   // candle on a custom symbol) and keeps real_volume - CLAUDE.md, 2026-08-10. Use the real one.
   return R[j].real_volume > 0 ? (double)R[j].real_volume : (double)R[j].tick_volume;
}
bool BodyOk(int j) {
   if (!InpUhvBodyOn) return true;
   double r = H(j) - L(j);
   return r <= 0 || MathAbs(C(j) - O(j)) / r * 100.0 >= InpUhvBodyPct;
}

void LoadOanda() {
   int h = FileOpen(InpOandaFile, FILE_READ | FILE_SHARE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (h == INVALID_HANDLE) h = FileOpen(InpOandaFile, FILE_READ | FILE_SHARE_READ | FILE_CSV | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) { Print("[TU] OANDA volume file missing - using this symbol's volume"); return; }
   ArrayResize(ovT, 400000); ArrayResize(ovV, 400000);
   while (!FileIsEnding(h) && ovN < 400000) {
      string a = FileReadString(h); string b = FileReadString(h);
      if (a == "" || StringToInteger(a) <= 0) continue;
      ovT[ovN] = (datetime)StringToInteger(a); ovV[ovN] = StringToInteger(b); ovN++;
   }
   FileClose(h);
   PrintFormat("[TU] OANDA volume: %d minutes loaded", ovN);
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   ArraySetAsSeries(R, true);
   if (InpVolSource == 1) LoadOanda();
   if (InpOnlyTVMinutes) {
      int h = FileOpen("tv_signals.csv", FILE_READ | FILE_SHARE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
      while (h != INVALID_HANDLE && !FileIsEnding(h)) {
         string a = FileReadString(h); FileReadString(h); FileReadString(h); FileReadString(h);
         if (StringToInteger(a) > 0) { ArrayResize(tvMin, tvN + 1); tvMin[tvN++] = StringToInteger(a); }
      }
      if (h != INVALID_HANDLE) FileClose(h);
      PrintFormat("[TU] DIAGNOSTIC: trading only %d indicator signal minutes", tvN);
   }
   if (InpExport) { int h = FileOpen("ea_signals.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ','); if (h != INVALID_HANDLE) FileClose(h); }
   if (InpExportState) stH = FileOpen("ea_state.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   PrintFormat("[TU] TurtleUHV v1.00 on %s | vol %s | %s | TP %.2f SL %.2f window %d", _Symbol,
               InpVolSource == 1 ? "OANDA file" : "symbol", InpTrade ? "TRADING" : "signals only", InpTPPrice, InpSLPrice, InpWindowMin);
   return INIT_SUCCEEDED;
}

// Pine ta.ema / ta.rma / ta.sma, seeded the way Pine seeds them (SMA of the first `len` values)
double EmaStep(double prev, double src, int len, double &seed[]) {
   // Pine's documented pine_ema: sum := na(sum[1]) ? src : alpha * src + (1 - alpha) * sum[1]
   if (IsNa(prev)) return src;
   return prev + (src - prev) * 2.0 / (len + 1);
}
double RmaStep(double prev, double src, int len, double &seed[]) {
   if (!IsNa(prev)) return (prev * (len - 1) + src) / len;
   int n = ArraySize(seed); ArrayResize(seed, n + 1); seed[n] = src;
   if (n + 1 < len) return NA;
   double s = 0; for (int i = 0; i < len; i++) s += seed[i]; return s / len;
}
double SmaPush(double &buf[], double v, int len) {
   int n = ArraySize(buf); ArrayResize(buf, n + 1); buf[n] = v;
   if (n + 1 > len) { ArrayRemove(buf, 0, 1); n = len - 1; }
   if (ArraySize(buf) < len) return NA;
   for (int i = 0; i < len; i++) if (IsNa(buf[i])) return NA;
   double s = 0; for (int i = 0; i < len; i++) s += buf[i]; return s / len;
}

// TradingView's 1-hour value on history: the last COMPLETED hour as of this candle's close
bool HtfGreen(bool &ok) {
   datetime closeT = T(0) + 60;
   datetime hourOpen = (datetime)((long)closeT / 3600 * 3600 - 3600);
   // not exact: after the daily break the previous hour does not exist, and TradingView then
   // uses the last hour candle that does (parity check, 2026-10-09)
   int sh = iBarShift(_Symbol, PERIOD_H1, hourOpen, false);
   ok = sh >= 0 && iTime(_Symbol, PERIOD_H1, sh) <= hourOpen;
   if (!ok) return false;
   return iClose(_Symbol, PERIOD_H1, sh) >= iOpen(_Symbol, PERIOD_H1, sh);
}

void ResetA() {   // cancel an active retracement (impulse-candle path)
   iR = false; uVol = 0; uHi = NA; uLo = NA; uBar = -1; rceLo = NA; rceHi = NA; bL = NA; uF = false; uWSp = false;
}

void ExportSignal(bool buy, double entry) {
   nSig++;
   if (!InpExport) return;
   int h = FileOpen("ea_signals.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, (long)(T(0) - InpUtcOffsetH * 3600), buy ? 1 : -1, (long)(armUT - InpUtcOffsetH * 3600), DoubleToString(entry, _Digits));
   FileClose(h);
}

// ── one finished candle, in turtle.pine's order ──
void ProcessBar() {
   k++;
   bool iGr = C(0) > O(0), iRd = C(0) < O(0);
   // trend engine (STEP 1 / TREND ENGINE)
   double tr = (nR > 1) ? MathMax(H(0) - L(0), MathMax(MathAbs(H(0) - C(1)), MathAbs(L(0) - C(1)))) : H(0) - L(0);
   e34p = e34;
   e34 = EmaStep(e34, C(0), 34, c34);
   e89 = EmaStep(e89, C(0), 89, c89);
   atr = RmaStep(atr, tr, 14, trBuf);
   atrSma = SmaPush(atrBuf, atr, 14);
   volSma = SmaPush(volBuf, V(0), 20);
   double tRH = H(0), tRL = L(0);
   for (int j = 1; j < 20 && j < nR; j++) { tRH = MathMax(tRH, H(j)); tRL = MathMin(tRL, L(j)); }
   bool ok = !IsNa(e34) && !IsNa(e89) && !IsNa(e34p);
   bool tEmB = ok && e34 > e89, tEmBr = ok && e34 < e89, tSlB = ok && e34 > e34p, tSlBr = ok && e34 < e34p;
   bool tFS = ok && !IsNa(atr) && MathAbs(e34 - e34p) < atr * 0.1;
   bool tStB = C(0) > tRL, tStBr = C(0) < tRH, tNS = !tStB && !tStBr;
   bool tAC = !IsNa(atr) && !IsNa(atrSma) && atr < atrSma * 0.45;
   bool tIR = tAC && tFS && tNS;
   bool tBU = C(0) > tRH * 1.001, tBD = C(0) < tRL * 0.999;
   bool tRwB = (tEmB && tSlB && tStB && !tIR) || tBU, tRwBr = (tEmBr && tSlBr && tStBr && !tIR) || tBD;
   bool tVE = !IsNa(volSma) && V(0) > volSma, tAE = !IsNa(atr) && !IsNa(atrSma) && atr > atrSma;
   bool tBC = (tRwB && (tVE || tAE)) || tBU, tBCr = (tRwBr && (tVE || tAE)) || tBD;
   bool tBS = tBC || tRwB, tBSr = tBCr || tRwBr;
   double tS = (tBC || tBCr ? 30 : 0) + (tVE && tAE ? 25 : 0) + 10 + (ok && !IsNa(atr) && MathAbs(e34 - e34p) > atr * 0.2 ? 15 : 0) + (!tIR ? 10 : 0);
   bool ib = (tBS && !tBSr) || (tBS && tBSr && tS >= 50), ibr = (tBSr && !tBS) || (tBS && tBSr && tS < 50);

   // camel humps (pivot confirmed InpCamPiv candles later)
   int p = InpCamPiv;
   if (k >= 2 * p && nR > 2 * p) {
      bool isPH = true, isPL = true;
      for (int d = 1; d <= p; d++) {
         if (H(p) < H(p - d) || H(p) < H(p + d)) isPH = false;
         if (L(p) > L(p - d) || L(p) > L(p + d)) isPL = false;
      }
      if (isPH) {
         if (czT == 1) { if (H(p) >= czHV) { czHB = k - p; czHV = H(p); } }
         else { czStk0 = czStk; czL0B = czLB; czL0V = czLV; czHB = k - p; czHV = H(p); czT = 1; }
      }
      if (isPL) {
         bool redraw = false;
         if (czT == 1) { czLB = k - p; czLV = L(p); czT = -1; redraw = true; }
         else if (czT == -1 && L(p) <= czLV) { czLB = k - p; czLV = L(p); redraw = true; }
         else if (czT == 0) { czLB = k - p; czLV = L(p); czT = -1; }
         if (redraw && czHB >= 0 && czL0B >= 0) {
            czTr = czLV > czL0V ? 1 : czLV < czL0V ? -1 : 0;
            czStk = czTr == 1 ? MathMax(czStk0, 0) + 1 : czTr == -1 ? MathMin(czStk0, 0) - 1 : 0;
         }
      }
   }
   bool czRetB = !InpCamRet || czTr == 1, czRetBe = !InpCamRet || czTr == -1;
   bool camB = !InpCamOn || czTr == 1, camBe = !InpCamOn || czTr == -1;

   // bypass lookback
   double PGL = NA, PGH = NA, PRH = NA, PRL = NA; int PGi = -1, PRi = -1;
   for (int bi = 1; bi <= InpBRWLB && bi < nR; bi++) {
      if (IsNa(PGL) && C(bi) >= O(bi)) { PGL = L(bi); PGH = H(bi); PGi = bi; }
      if (IsNa(PRH) && C(bi) < O(bi)) { PRH = H(bi); PRL = L(bi); PRi = bi; }
      if (!IsNa(PGL) && !IsNa(PRH)) break;
   }
   bool bRWBearCand = czRetBe && !iR && !ibT && iGr && !IsNa(PRH) && C(0) > PRH;
   bool bIB = ib && (!iR || (iR && !rwb)) && iGr && nR > 1 && C(0) > H(1) && !bRWBearCand;
   bool bRWBullCand = czRetB && !iR && !ibT && iRd && !IsNa(PGL) && C(0) < PGL;
   bool beIB = ibr && (!iR || (iR && rwb)) && iRd && nR > 1 && C(0) < L(1) && !bRWBullCand;
   if (bIB && !ibT) {
      if (iR && !rwb) ResetA();
      rceLo = NA; rceHi = NA; ibT = true; ibTBar = k; rwb = true; rCeil = H(0); rIBLo = L(0); lb = true;
   }
   if (beIB && !ibT) {
      if (iR && rwb) ResetA();
      rceLo = NA; rceHi = NA; ibT = true; ibTBar = k; rwb = false; rFlr = L(0); rIBHi = H(0); lb = false;
   }
   if (ibT && rwb && ibr) { ibT = false; ibTBar = -1; rIBLo = NA; }
   if (ibT && !rwb && ib) { ibT = false; ibTBar = -1; rIBHi = NA; }
   if (ibT && ibTBar >= 0 && k - ibTBar >= 3) { ibT = false; ibTBar = -1; }

   bool bRet = czRetB && ibT && rwb && iRd && !IsNa(rIBLo) && C(0) < rIBLo;
   bool beRet = czRetBe && ibT && !rwb && iGr && !IsNa(rIBHi) && C(0) > rIBHi;
   if (bRet) {
      ibT = false; ibTBar = -1; iR = true; rwb = true; rSB = k; uHi = H(0); uSl = L(0); uLo = NA;
      uVol = V(0); uBar = k;
      rceLo = IsNa(rceLo) ? L(0) : MathMin(L(0), rceLo); rceHi = IsNa(rceHi) ? H(0) : MathMax(H(0), rceHi);
      bL = H(0); uF = false; uWB = (k - luSB) < InpCooldown; uWSp = BodyOk(0);
   }
   if (beRet) {
      ibT = false; ibTBar = -1; iR = true; rwb = false; rSB = k; uLo = L(0); uSl = H(0); uHi = NA;
      rceLo = IsNa(rceLo) ? L(0) : MathMin(L(0), rceLo); rceHi = IsNa(rceHi) ? H(0) : MathMax(H(0), rceHi);
      bL = L(0); uVol = V(0); uBar = k; uF = false; uWB = (k - luSB) < InpCooldown; uWSp = BodyOk(0);
   }
   // bypass start, bull side, with backdating
   if (czRetB && !iR && !ibT && iRd && !IsNa(PGL) && C(0) < PGL) {
      iR = true; rwb = true; lb = true; rCeil = PGH; rSB = k; uHi = H(0); uSl = L(0); uLo = NA;
      uVol = V(0); uBar = k; rceLo = L(0); rceHi = H(0); bL = H(0); uF = false; uWB = (k - luSB) < InpCooldown;
      uWSp = BodyOk(0);
      int bdO = 0;
      if (PGi >= 2) for (int j = PGi - 1; j >= 1; j--) if (C(j) < O(j) && C(j) < PGL) { bdO = j; break; }
      int bdU = 0; double bdV = V(0);
      for (int j = bdO; j >= 0; j--) if (C(j) < O(j) && V(j) > bdV) { bdV = V(j); bdU = j; }
      bool stale = false;
      if (bdU >= 1) for (int j = bdU - 1; j >= 0; j--) if (C(j) > O(j) && C(j) > H(bdU)) stale = true;
      if (bdO > 0 && !stale) {
         rSB = k - bdO;
         for (int j = bdO; j >= 0; j--) { rceLo = MathMin(rceLo, L(j)); rceHi = MathMax(rceHi, H(j)); }
         uVol = bdV; uBar = k - bdU; uHi = H(bdU); uSl = L(bdU); bL = H(bdU); uWSp = BodyOk(bdU);
      }
   }
   // bypass start, bear side, with backdating
   if (czRetBe && !iR && !ibT && iGr && !IsNa(PRH) && C(0) > PRH) {
      iR = true; rwb = false; lb = false; rFlr = PRL; rSB = k; uLo = L(0); uSl = H(0); uHi = NA;
      rceLo = L(0); rceHi = H(0); bL = L(0); uVol = V(0); uBar = k; uF = false; uWB = (k - luSB) < InpCooldown;
      uWSp = BodyOk(0);
      int bdO = 0;
      if (PRi >= 2) for (int j = PRi - 1; j >= 1; j--) if (C(j) > O(j) && C(j) > PRH) { bdO = j; break; }
      int bdU = 0; double bdV = V(0);
      for (int j = bdO; j >= 0; j--) if (C(j) > O(j) && V(j) > bdV) { bdV = V(j); bdU = j; }
      bool stale = false;
      if (bdU >= 1) for (int j = bdU - 1; j >= 0; j--) if (C(j) < O(j) && C(j) < L(bdU)) stale = true;
      if (bdO > 0 && !stale) {
         rSB = k - bdO;
         for (int j = bdO; j >= 0; j--) { rceLo = MathMin(rceLo, L(j)); rceHi = MathMax(rceHi, H(j)); }
         uVol = bdV; uBar = k - bdU; uLo = L(bdU); uSl = H(bdU); bL = L(bdU); uWSp = BodyOk(bdU);
      }
   }
   // STEP 3b: breakout reached without a signal -> setup will end; camel turned / expiry -> reset
   if (iR) {
      bool retExp = rSB >= 0 && k - rSB > 100;
      bool uBeF = iRd && !IsNa(bL) && uBar >= 0 && C(0) < bL && !uF;
      bool uBF  = iGr && !IsNa(bL) && uBar >= 0 && C(0) > bL && !uF;
      if ((rwb && uBF) || (!rwb && uBeF)) uWB = true;
      bool czKill = InpCamRet && !uF && (lb ? czTr != 1 : czTr != -1);
      if (retExp || czKill) {
         iR = false; ibT = false; uVol = 0; uHi = NA; uLo = NA; uBar = -1; rceLo = NA; rceHi = NA; bL = NA; uWSp = false;
      }
   }
   if (iR) {
      if (lb && (IsNa(rceLo) || L(0) < rceLo)) rceLo = L(0);
      if (!lb && (IsNa(rceHi) || H(0) > rceHi)) rceHi = H(0);
   }
   // STEP 4: UHV = loudest candle of the retracement
   if (iR && lb && iRd && !uF && V(0) > uVol) { uVol = V(0); uHi = H(0); uSl = L(0); uBar = k; bL = H(0); uWSp = BodyOk(0); }
   if (iR && !lb && iGr && !uF && V(0) > uVol) { uVol = V(0); uLo = L(0); uSl = H(0); uBar = k; bL = L(0); uWSp = BodyOk(0); }

   // STEP 5: breakout. Bull: arm for the next candle, then fire from the previous candle's arm.
   bool htfOk; bool htfG = HtfGreen(htfOk);
   bool prevArmB = armB, prevArmE = armE; double prevTrigB = trigB, prevTrigE = trigE; datetime prevUT = armUT;
   datetime uhvT = uBar >= 0 && k - uBar < nR ? T(k - uBar) : 0;
   armB = InpDir >= 0 && iR && lb && rwb && !IsNa(bL) && !uF && uBar >= 0 && uWSp && (k + 1 - luSB) >= InpCooldown
          && camB && (!InpHTF60 || (htfOk && htfG));
   trigB = bL;
   bool fireB = prevArmB && !uF && H(0) > prevTrigB && (k - luSB) >= InpCooldown;
   if (fireB) { armUT = prevUT; uF = true; luSB = k; ExportSignal(true, MathMax(O(0), prevTrigB)); }
   armE = InpDir <= 0 && iR && !lb && !rwb && !IsNa(bL) && !uF && uBar >= 0 && uWSp && (k + 1 - luSB) >= InpCooldown
          && camBe && (!InpHTF60 || (htfOk && !htfG));
   trigE = bL;
   bool fireE = prevArmE && !uF && L(0) < prevTrigE && (k - luSB) >= InpCooldown;
   if (fireE) { armUT = prevUT; uF = true; luSB = k; ExportSignal(false, MathMin(O(0), prevTrigE)); }
   if (!fireB && !fireE) armUT = uhvT; else armUT = uhvT;     // the UHV of the setup armed now
   // end the setup after a signal or a blocked breakout
   if (iR && (uF || uWB)) { iR = false; ibT = false; rceLo = NA; rceHi = NA; }
   if (stH != INVALID_HANDLE) {
      int flags = (iR ? 1 : 0) + (lb ? 2 : 0) + (rwb ? 4 : 0) + (ibT ? 8 : 0) + (uF ? 16 : 0) + (uWB ? 32 : 0) + (uWSp ? 64 : 0)
                  + (armB ? 128 : 0) + (armE ? 256 : 0) + (ib ? 512 : 0) + (ibr ? 1024 : 0);
      datetime ut = uBar >= 0 && k - uBar < nR ? T(k - uBar) : 0;
      FileWrite(stH, (long)(T(0) - InpUtcOffsetH * 3600), flags, czTr * 100 + czStk,
                ut > 0 ? (long)(ut - InpUtcOffsetH * 3600) : 0, IsNa(bL) ? "" : DoubleToString(bL, _Digits));
   }
}
void OnDeinit(const int r) { if (stH != INVALID_HANDLE) FileClose(stH); }

// ── trading on this broker's ticks, from the setup armed at the last close ──
void TradeTick() {
   if (pos != 0 && !PositionSelectByTicket(pos)) pos = 0;
   if (pos != 0 && TimeCurrent() >= exitAt) { trade.PositionClose(pos); pos = 0; }
   if (!InpTrade || pos != 0 || halted) return;
   datetime candle = iTime(_Symbol, PERIOD_M1, 0);
   if (candle == firedCandle) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool buy = armB && !uF && (k + 1 - luSB) >= InpCooldown && bid > trigB;
   bool sell = !buy && armE && !uF && (k + 1 - luSB) >= InpCooldown && bid < trigE;
   if (!buy && !sell) return;
   firedCandle = candle;
   if (InpOnlyTVMinutes) {
      long u = (long)candle - InpUtcOffsetH * 3600; bool inList = false;
      for (int i = 0; i < tvN; i++) if (tvMin[i] == u) { inList = true; break; }
      if (!inList) return;
   }
   if (ask - bid > InpMaxSpread) return;
   if (InpGuards && !GuardsOk()) return;
   double px = buy ? ask : bid;
   double sl = NormalizeDouble(buy ? px - InpSLPrice : px + InpSLPrice, _Digits);
   double tp = NormalizeDouble(buy ? px + InpTPPrice : px - InpTPPrice, _Digits);
   bool ok = buy ? trade.Buy(InpLots, _Symbol, 0, sl, tp, "TU") : trade.Sell(InpLots, _Symbol, 0, sl, tp, "TU");
   if (!ok) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if (PositionGetInteger(POSITION_MAGIC) == InpMagic) { pos = t; break; } }
   nTrades++;
   exitAt = candle + (InpWindowMin + 1) * 60;
}

bool GuardsOk() {
   MqlDateTime s; TimeToStruct(TimeCurrent(), s);
   datetime d = StringToTime(StringFormat("%04d.%02d.%02d", s.year, s.mon, s.day));
   if (d != dayD) { dayD = d; day0 = MathMax(AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)); }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double floorStop = InpInitialBalance * (1 - InpMaxLossPct / 100.0) + InpFloorBuffer;
   if (eq <= floorStop) { halted = true; Print("[TU] floor buffer reached - stopped"); return false; }
   if (eq <= day0 - InpDailyStop) return false;
   double risk = InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE) * InpSLPrice;
   if (risk >= MathMin(eq - floorStop, eq - (day0 - InpDailyStop))) return false;
   if (!MQLInfoInteger(MQL_TESTER)) {
      MqlCalendarValue v[]; datetime now = TimeTradeServer();
      if (CalendarValueHistory(v, now - InpNewsMin * 60, now + InpNewsMin * 60, NULL, "USD") < 0) return false;
      for (int i = 0; i < ArraySize(v); i++) { MqlCalendarEvent e; if (CalendarEventById(v[i].event_id, e) && e.importance == CALENDAR_IMPORTANCE_HIGH) return false; }
   }
   return true;
}

void OnTick() {
   datetime b = iTime(_Symbol, PERIOD_M1, 0);
   if (b != lastBar && b > 0) {
      lastBar = b;
      nR = CopyRates(_Symbol, PERIOD_M1, 1, 300, R);
      if (nR >= 2) ProcessBar();
   }
   TradeTick();
}

double OnTester() {
   double tr = TesterStatistics(STAT_TRADES), pr = TesterStatistics(STAT_PROFIT);
   PrintFormat("[TU] candles %d | signals %d | trades %d | won %.1f%% | net $%.2f = $%.2f/trade | max drawdown $%.2f | OANDA volume misses %d",
               k + 1, nSig, nTrades, tr > 0 ? 100.0 * TesterStatistics(STAT_PROFIT_TRADES) / tr : 0, pr, tr > 0 ? pr / tr : 0,
               TesterStatistics(STAT_EQUITY_DD), ovMiss);
   return tr > 0 ? pr / tr : 0;
}
