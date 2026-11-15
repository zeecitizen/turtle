//+------------------------------------------------------------------+
//| TiltLab_EUR.mq5 (2026-11-04) - LAB ONLY, tester rigs, never live.  |
//| Which "tilt" (direction signal) wins most at the gold_runner game  |
//| geometry: EUR/USD, TP 2 pips / SL 2 pips from the FILL, 1 position |
//| at a time, cooldown after each close. M1 chart.                    |
//|  InpTilt 0 = game HA tilt (engine.py ha_delta + _update_market)    |
//|          1 = VSISA setup (TriVsisa.mqh V_Detect / V_DetectFade,    |
//|              the engine's own law code, included unchanged)        |
//|          2 = SPRING (TickSpeedGauge) - NOT PORTABLE: needs the     |
//|              order book (OBI); the tester has no DOM. Refuses init.|
//|          3 = RSI double top/bottom retest (josseliani-style)       |
//|          4 = teacher: BUY DI+<10 & AO<0 (InpDmiSide 1 = mirror SELL)|
//|          5 = random control: every 15 min, alternate sides         |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
void TriVsRaw(int side) {}            // host hook TriVsisa.mqh expects
#include "TriVsisa.mqh"

input int    InpTilt      = 0;
input double InpLots      = 1.0;
input double InpTP        = 0.00020;
input double InpSL        = 0.00020;
input int    InpCoolSec   = 60;       // after a close, wait this long
input int    InpMagic     = 88990;
// 0: HA tilt
input double InpHaScale   = 0.00024;  // HA delta that = full tilt (EUR)
input double InpHaEmaSec  = 3.0;
input double InpHaThr     = 0.6;      // fire when |tilt EMA| crosses up through this
input int    InpHaBars    = 20;
// 3: RSI retest
input int    InpRsiLen    = 14;
input double InpRsiHi     = 70;
input double InpRsiLo     = 30;
input double InpCoolHi    = 60;
input double InpCoolLo    = 40;
input int    InpPivStr    = 2;
input int    InpLineMode  = 0;        // 0 Kijun (HH+LL)/2 over InpLineLen, 1 EMA InpLineLen
input int    InpLineLen   = 34;
input double InpBodyPct   = 0.50;     // share of the body beyond the line
input int    InpArmBars   = 30;       // armed setup expires after this many bars
// 4: teacher
input int    InpDmiSide   = 0;        // 0 BUY: DI+ < lvl and AO < 0 ; 1 SELL mirror: DI- < lvl and AO > 0
input double InpDmiLvl    = 10;
input int    InpAdxLen    = 14;
// 5: random
input int    InpEveryMin  = 15;

CTrade tr;
datetime g_lastBar = 0, g_lastClose = 0;
ulong    g_anchored = 0;
int      g_fires = 0, g_skipBusy = 0, g_reFail = 0;
double   g_ema = 0, g_prevAbs = 0; long g_lastMs = 0;
int      hRsi = INVALID_HANDLE, hEma = INVALID_HANDLE, hAdx = INVALID_HANDLE, hAo = INVALID_HANDLE;
bool     g_randBuy = true; int g_pend = 0; bool g_prevCond = false;
// RSI state per side: 0 idle, 1 extreme seen (tracking peak1), 2 cooled (waiting 2nd pivot), 3 armed (waiting close beyond line)
int    rsSt[2]; double rsPk[2]; int rsArm[2];

ulong MyPos() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i);
      if (t && PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == _Symbol) return t; }
   return 0;
}
bool Flat() {
   if (MyPos() != 0) return false;
   if (g_lastClose > 0 && TimeCurrent() - g_lastClose < InpCoolSec) return false;
   return true;
}
void Fire(int side, string why) {
   if (!Flat()) { g_skipBusy++; return; }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double e = side > 0 ? ask : bid;
   double sl = NormalizeDouble(side > 0 ? e - InpSL : e + InpSL, _Digits), tp = NormalizeDouble(side > 0 ? e + InpTP : e - InpTP, _Digits);
   bool ok = side > 0 ? tr.Buy(InpLots, _Symbol, 0, sl, tp, why) : tr.Sell(InpLots, _Symbol, 0, sl, tp, why);
   if (ok) g_fires++; else PrintFormat("[TILTFAIL] %s retcode %d", why, tr.ResultRetcode());
}
void Reanchor() {   // same SL/TP distances re-anchored to the actual fill
   ulong t = MyPos(); if (t == 0 || t == g_anchored) return;
   if (!PositionSelectByTicket(t)) return;
   double o = PositionGetDouble(POSITION_PRICE_OPEN); bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double sl = NormalizeDouble(buy ? o - InpSL : o + InpSL, _Digits), tp = NormalizeDouble(buy ? o + InpTP : o - InpTP, _Digits);
   g_anchored = t;
   if (MathAbs(PositionGetDouble(POSITION_SL) - sl) < _Point / 2 && MathAbs(PositionGetDouble(POSITION_TP) - tp) < _Point / 2) return;
   if (!tr.PositionModify(t, sl, tp)) g_reFail++;
}
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res) {
   if (trans.type == TRADE_TRANSACTION_DEAL_ADD && HistoryDealSelect(trans.deal))
      if (HistoryDealGetInteger(trans.deal, DEAL_MAGIC) == InpMagic && HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_OUT) g_lastClose = TimeCurrent();
}
double Buf(int h, int b, int k) { double x[1]; return CopyBuffer(h, b, k, 1, x) == 1 ? x[0] : EMPTY_VALUE; }

int OnInit() {
   tr.SetExpertMagicNumber(InpMagic); tr.SetDeviationInPoints(30); tr.SetTypeFillingBySymbol(_Symbol);
   if (InpTilt == 2) { Print("[TILT] SPRING needs the order book (OBI = bestBid vol vs bestAsk vol); the tester has no DOM - not portable"); return INIT_FAILED; }
   if (InpTilt == 1 && V_OnInit() != INIT_SUCCEEDED) return INIT_FAILED;
   if (InpTilt == 3) { hRsi = iRSI(_Symbol, PERIOD_M1, InpRsiLen, PRICE_CLOSE); if (InpLineMode == 1) hEma = iMA(_Symbol, PERIOD_M1, InpLineLen, 0, MODE_EMA, PRICE_CLOSE); }
   if (InpTilt == 4) { hAdx = iADX(_Symbol, PERIOD_M1, InpAdxLen); hAo = iAO(_Symbol, PERIOD_M1); }
   ArrayInitialize(rsSt, 0); ArrayInitialize(rsArm, 0); ArrayInitialize(rsPk, 0);
   PrintFormat("[TILT] lab v1.00 tilt %d TP %.5f SL %.5f cool %ds", InpTilt, InpTP, InpSL, InpCoolSec);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[TILT] fires %d skipped-busy %d reanchor-fail %d", g_fires, g_skipBusy, g_reFail); }

double HaDelta() {   // engine.py ha_delta over the last n M1 bars INCLUDING the forming bar
   int n = InpHaBars; double ho = 0, hc = 0;
   for (int k = n - 1; k >= 0; k--) {
      double o = iOpen(_Symbol, PERIOD_M1, k), h = iHigh(_Symbol, PERIOD_M1, k), l = iLow(_Symbol, PERIOD_M1, k), c = iClose(_Symbol, PERIOD_M1, k);
      if (k == n - 1) { ho = (o + c) / 2; hc = (o + h + l + c) / 4; }
      else { ho = (ho + hc) / 2; hc = (o + h + l + c) / 4; }
   }
   return hc - ho;
}
void TickHa() {
   MqlTick tk; if (!SymbolInfoTick(_Symbol, tk)) return;
   double raw = MathMax(-1.0, MathMin(1.0, HaDelta() / InpHaScale));
   double dt = g_lastMs == 0 ? 0.1 : MathMax(0.0, MathMin(5.0, (tk.time_msc - g_lastMs) / 1000.0));
   g_lastMs = tk.time_msc;
   g_ema += (1.0 - MathExp(-dt / MathMax(0.05, InpHaEmaSec))) * (raw - g_ema);
   double a = MathAbs(g_ema);
   if (g_prevAbs < InpHaThr && a >= InpHaThr) Fire(g_ema > 0 ? 1 : -1, "ha");
   g_prevAbs = a;
}
double Line(int k) {
   if (InpLineMode == 1) return Buf(hEma, 0, k);
   int hi = iHighest(_Symbol, PERIOD_M1, MODE_HIGH, InpLineLen, k), lo = iLowest(_Symbol, PERIOD_M1, MODE_LOW, InpLineLen, k);
   return (iHigh(_Symbol, PERIOD_M1, hi) + iLow(_Symbol, PERIOD_M1, lo)) / 2;
}
void BarRsi() {   // first tick of a new bar; r[0] = RSI of the last closed bar
   int P = InpPivStr; double r[]; ArraySetAsSeries(r, true);
   if (CopyBuffer(hRsi, 0, 1, 2 * P + 2, r) < 2 * P + 2) return;
   double v = r[0];
   bool pivH = true, pivL = true;     // pivot at r[P], confirmed now (RSI has turned for P bars)
   for (int j = 1; j <= P; j++) { if (!(r[P] > r[P - j] && r[P] > r[P + j])) pivH = false; if (!(r[P] < r[P - j] && r[P] < r[P + j])) pivL = false; }
   double o = iOpen(_Symbol, PERIOD_M1, 1), c = iClose(_Symbol, PERIOD_M1, 1), ln = Line(1), body = MathAbs(c - o);
   // s 0 = bear (second lower RSI top -> SELL), s 1 = bull (second higher RSI bottom -> BUY)
   for (int s = 0; s < 2; s++) {
      double sg = s == 0 ? 1 : -1;               // flip so both sides read as "tops"
      double x = sg * v, ext = s == 0 ? InpRsiHi : -InpRsiLo, cool = s == 0 ? InpCoolHi : -InpCoolLo;
      double pv = sg * r[P]; bool piv = s == 0 ? pivH : pivL;
      if (rsSt[s] == 0) { if (x >= ext) { rsSt[s] = 1; rsPk[s] = x; } }
      else if (rsSt[s] == 1) { rsPk[s] = MathMax(rsPk[s], x); if (x < cool) rsSt[s] = 2; }
      else if (rsSt[s] == 2) {
         if (x > rsPk[s]) { rsPk[s] = x; rsSt[s] = 1; }
         else if (piv && pv < rsPk[s] && pv > cool) { rsSt[s] = 3; rsArm[s] = InpArmBars; }
      }
      else if (rsSt[s] == 3) {
         if (x > rsPk[s]) { rsPk[s] = x; rsSt[s] = 1; continue; }
         if (s == 0 && c < o && c < ln) { if (MathMin(o, ln) - c >= InpBodyPct * body) { g_pend = -1; rsSt[s] = 0; continue; } }
         if (s == 1 && c > o && c > ln) { if (c - MathMax(o, ln) >= InpBodyPct * body) { g_pend = 1; rsSt[s] = 0; continue; } }
         if (--rsArm[s] <= 0) rsSt[s] = 0;
      }
   }
}
void OnTick() {
   Reanchor();
   if (InpTilt == 0) { TickHa(); return; }
   datetime bt = iTime(_Symbol, PERIOD_M1, 0);
   if (bt == g_lastBar) return;
   g_lastBar = bt;
   if (InpTilt == 3) { BarRsi(); if (g_pend != 0) { Fire(g_pend, "rsi"); g_pend = 0; } return; }   // confirmation bar just closed -> enter at this bar's open
   if (InpTilt == 4) {
      double dp = Buf(hAdx, 1, 1), dm = Buf(hAdx, 2, 1), ao = Buf(hAo, 0, 1);
      if (dp == EMPTY_VALUE || ao == EMPTY_VALUE) return;
      bool cond = InpDmiSide == 0 ? (dp < InpDmiLvl && ao < 0) : (dm < InpDmiLvl && ao > 0);
      if (cond && !g_prevCond) Fire(InpDmiSide == 0 ? 1 : -1, "dmi");
      g_prevCond = cond; return;
   }
   if (InpTilt == 5) {
      MqlDateTime d; TimeToStruct(bt, d);
      if ((d.hour * 60 + d.min) % InpEveryMin == 0 && Flat()) { Fire(g_randBuy ? 1 : -1, "rnd"); g_randBuy = !g_randBuy; }
      return;
   }
   if (InpTilt == 1) {
      static datetime vb = 0; datetime vt = iTime(_Symbol, V_InpTF, 0);
      if (vt == vb) return; vb = vt;
      double sl; string why;
      if (V_InpBuys && V_Detect(+1, sl, why)) { Fire(1, "vsisa"); return; }
      if (V_InpSells && V_Detect(-1, sl, why)) { Fire(-1, "vsisa"); return; }
      if (V_InpBuys && V_DetectFade(+1, sl, why)) { Fire(1, "vsfade"); return; }
      if (V_InpSells && V_DetectFade(-1, sl, why)) { Fire(-1, "vsfade"); return; }
   }
}
