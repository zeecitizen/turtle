//+------------------------------------------------------------------+
//| S4bTrader.mq5 — S4 variant: TP$5/SL$6 (closer take, higher WR)  |
//|                                                                  |
//| Same entry as S4 (Lesson-2 UHV breakout + HH/HL structure +      |
//| Kaufman ER≥0.15 regime filter), but CLOSER TP for higher WR.     |
//|                                                                  |
//| VALIDATION (backtest_s4_tp_sweep_and_trend.py, 13 real-tick days,|
//|   broker feed, bar-close detect + next-tick fill, spread modeled):|
//|   TP5/SL6 @0.10: ALL +$564 / OOS +$1,257 (beats TP12/SL6 OOS)   |
//|   WR: 56% all / 65% OOS (vs 40%/38% at TP12).                   |
//|   Higher WR = psychologically easier, fewer losing streaks.      |
//|   ~17/day, same entry count as S4, just exits faster.            |
//|                                                                  |
//| ⚠️ CANDIDATE — forward-test alongside S4 before trusting.        |
//| Magic 88008 (distinct from S4=88007 / S3=88003 / S1=88004 /      |
//| NSND=88006).                                                     |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — S4b UHV Breakout (TP5/SL6 closer-take variant)"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.02;   // FTMO-safe
input int    InpMagicNumber   = 88008;
input double InpDailyLossHalt = 200.0;  // halt NEW entries if account EQUITY down this much today. 0=off.

input group "── Detection (M1) ──"
input int    InpTrendLookback   = 30;   // M1 bars for HH/HL structure (recent 15 vs prior 15)
input int    InpRetraceLookback = 12;   // M1 bars to scan for the UHV candle
input double InpMomBodyFrac     = 0.55; // breakout candle body/range >= this (momentum, small wicks)
input bool   InpRequireTrend    = true; // require HH/HL structure in the trade direction
input double InpERMin           = 0.15; // REGIME FILTER: Kaufman efficiency ratio minimum. 0=off.
input bool   InpDoBuys          = true;
input bool   InpDoSells         = true;

input group "── Exit (TP5/SL6 — closer take, higher WR) ──"
input double InpTPPts           = 5.0;  // take-profit distance (price units). OOS: 65% WR, +$1257@0.10.
input double InpSLPts           = 6.0;  // stop-loss distance (price units).

input group "── One-tap GRAB ──"
input bool   InpEnableGrab = true;
input double InpAvgWinUsd  = 10.0;      // ~avg win @0.02 (TP5 = $10); for heartbeat 'bigness'
input string InpGrabFile   = "grab_command.txt";

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "S4b";
input string InpStateFile     = "s4b_trader_state.json";
input string InpDecisionCsv   = "s4b_decisions.csv";
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m1_time = 0;
datetime g_last_signal_t = 0;
datetime g_last_heartbeat = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_today_day = 0;
double   g_day_start_equity = 0;
long     g_last_grab_id = 0;
datetime g_last_grab_check = 0;

void Log(string m) { if (InpVerbose) PrintFormat("[%s] %s", InpLogPrefix, m); }

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day; g_signals_today = 0; g_entries_today = 0;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      return true;
   }
   return false;
}
bool DailyLossHalted() {
   if (InpDailyLossHalt <= 0 || g_day_start_equity <= 0) return false;
   return (AccountInfoDouble(ACCOUNT_EQUITY) - g_day_start_equity) <= -InpDailyLossHalt;
}

//── Same-TF market structure: HH+HL = +1, LH+LL = -1, else 0 ──
int TrendDir() {
   int half = InpTrendLookback / 2;
   double rHi = -1e18, rLo = 1e18, oHi = -1e18, oLo = 1e18;
   for (int s = 1; s <= half; s++) {
      rHi = MathMax(rHi, iHigh(_Symbol, PERIOD_M1, s));
      rLo = MathMin(rLo, iLow (_Symbol, PERIOD_M1, s));
   }
   for (int s = half + 1; s <= InpTrendLookback; s++) {
      oHi = MathMax(oHi, iHigh(_Symbol, PERIOD_M1, s));
      oLo = MathMin(oLo, iLow (_Symbol, PERIOD_M1, s));
   }
   if (rHi > oHi && rLo > oLo) return 1;
   if (rHi < oHi && rLo < oLo) return -1;
   return 0;
}

//── Kaufman Efficiency Ratio over the trend window ──
double EfficiencyRatio() {
   double net = MathAbs(iClose(_Symbol,PERIOD_M1,1) - iClose(_Symbol,PERIOD_M1,InpTrendLookback));
   double path = 0;
   for (int s = 1; s < InpTrendLookback; s++)
      path += MathAbs(iClose(_Symbol,PERIOD_M1,s) - iClose(_Symbol,PERIOD_M1,s+1));
   return (path > 0) ? net / path : 0.0;
}

//── Evaluate the just-closed M1 bar (shift 1) for a signal ──
void TrySignal() {
   if (DailyLossHalted()) return;
   datetime bo_t = iTime(_Symbol, PERIOD_M1, 1);
   if (bo_t == g_last_signal_t) return;

   double bo_o = iOpen (_Symbol, PERIOD_M1, 1);
   double bo_h = iHigh (_Symbol, PERIOD_M1, 1);
   double bo_l = iLow  (_Symbol, PERIOD_M1, 1);
   double bo_c = iClose(_Symbol, PERIOD_M1, 1);
   long   bo_v = iVolume(_Symbol, PERIOD_M1, 1);
   double rng = bo_h - bo_l;
   if (rng <= 0) return;
   double body = MathAbs(bo_c - bo_o);
   if (body / rng < InpMomBodyFrac) return;            // momentum candle (small wicks)

   // avg body over the retracement window (shifts 1..1+RetraceLB)
   double sb = 0; int nb = 0;
   for (int s = 1; s <= 1 + InpRetraceLookback; s++) { sb += MathAbs(iClose(_Symbol,PERIOD_M1,s)-iOpen(_Symbol,PERIOD_M1,s)); nb++; }
   double avgbody = (nb > 0) ? sb / nb : 0;
   if (body < avgbody) return;                          // strong candle
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return;  // regime filter: skip ranging

   int td = TrendDir();
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // BUY: green momentum breaks above the UHV RED candle's high, low vol
   if (InpDoBuys && bo_c > bo_o && (!InpRequireTrend || td == 1)) {
      double uhv_h = 0; long uhv_v = -1;
      for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
         if (iClose(_Symbol,PERIOD_M1,s) < iOpen(_Symbol,PERIOD_M1,s)) {   // red
            long v = iVolume(_Symbol, PERIOD_M1, s);
            if (v > uhv_v) { uhv_v = v; uhv_h = iHigh(_Symbol, PERIOD_M1, s); }
         }
      }
      if (uhv_v > 0 && bo_v < uhv_v && bo_c > uhv_h && bo_o <= uhv_h) {
         FireTrade(true, ask, bo_t);
         return;
      }
   }
   // SELL: red momentum breaks below the UHV GREEN candle's low, low vol
   if (InpDoSells && bo_c < bo_o && (!InpRequireTrend || td == -1)) {
      double uhv_l = 0; long uhv_v = -1;
      for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
         if (iClose(_Symbol,PERIOD_M1,s) > iOpen(_Symbol,PERIOD_M1,s)) {   // green
            long v = iVolume(_Symbol, PERIOD_M1, s);
            if (v > uhv_v) { uhv_v = v; uhv_l = iLow(_Symbol, PERIOD_M1, s); }
         }
      }
      if (uhv_v > 0 && bo_v < uhv_v && bo_c < uhv_l && bo_o >= uhv_l) {
         FireTrade(false, bid, bo_t);
         return;
      }
   }
}

void FireTrade(bool isBuy, double px, datetime bo_t) {
   double sl = isBuy ? px - InpSLPts : px + InpSLPts;
   double tp = isBuy ? px + InpTPPts : px - InpTPPts;
   g_signals_today++;
   bool ok = isBuy ? g_trade.Buy (InpLots, _Symbol, 0, sl, tp, "S4b_buy")
                   : g_trade.Sell(InpLots, _Symbol, 0, sl, tp, "S4b_sell");
   if (!ok) { Log(StringFormat("[ERR] %s failed ret=%d", isBuy?"Buy":"Sell", g_trade.ResultRetcode())); return; }
   g_entries_today++;
   g_last_signal_t = bo_t;
   ulong ticket = g_trade.ResultOrder();
   Log(StringFormat("S4b %s @%.2f sl=%.2f tp=%.2f ticket=%I64u", isBuy?"BUY":"SELL", px, sl, tp, ticket));
   LogDecision(isBuy, bo_t, px, sl, tp, ticket);
}

void LogDecision(bool isBuy, datetime bo_t, double px, double sl, double tp, ulong ticket) {
   int fh = FileOpen(InpDecisionCsv, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ',');
   if (fh == INVALID_HANDLE) {
      fh = FileOpen(InpDecisionCsv, FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ',');
      if (fh == INVALID_HANDLE) return;
      FileWrite(fh, "fire_iso","ea","side","bo_time_iso","entry","sl","tp","ticket","magic","lots");
   } else FileSeek(fh, 0, SEEK_END);
   FileWrite(fh, TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), "S4b", isBuy?"buy":"sell",
             TimeToString(bo_t,TIME_DATE|TIME_SECONDS), DoubleToString(px,2),
             DoubleToString(sl,2), DoubleToString(tp,2), IntegerToString((long)ticket),
             IntegerToString((long)InpMagicNumber), DoubleToString(InpLots,2));
   FileClose(fh);
}

//── Floating P&L + open positions JSON (dashboard) ──
double FloatingPnL(int &n_open) {
   double sum = 0; n_open = 0;
   for (int i = PositionsTotal()-1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk==0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP); n_open++;
   }
   return sum;
}
string BuildOpenJson() {
   string arr = "["; int n = 0;
   for (int i = PositionsTotal()-1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk==0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool buy = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      if (n>0) arr += ",";
      arr += StringFormat("{\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.2f,\"cur\":%.2f,\"pnl\":%.2f,\"sl\":%.2f,\"tp\":%.2f}",
                          buy?"BUY":"SELL", PositionGetDouble(POSITION_VOLUME),
                          PositionGetDouble(POSITION_PRICE_OPEN), PositionGetDouble(POSITION_PRICE_CURRENT),
                          PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP),
                          PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP));
      n++;
   }
   return arr + "]";
}

//── One-tap GRAB ──
long ReadGrabId() {
   if (!FileIsExist(InpGrabFile, FILE_COMMON)) return 0;
   int fh = FileOpen(InpGrabFile, FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if (fh == INVALID_HANDLE) return 0;
   string s = FileIsEnding(fh) ? "" : FileReadString(fh);
   FileClose(fh);
   return (long)StringToInteger(s);
}
void CheckGrabCommand() {
   if (!InpEnableGrab) return;
   if ((TimeCurrent() - g_last_grab_check) < 2) return;
   g_last_grab_check = TimeCurrent();
   long id = ReadGrabId();
   if (id <= g_last_grab_id) return;
   g_last_grab_id = id;
   int closed = 0;
   for (int i = PositionsTotal()-1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk==0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (g_trade.PositionClose(tk)) closed++;
   }
   if (closed > 0) Log(StringFormat("[GRAB] id=%I64d closed %d", id, closed));
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   int n_open = 0; double floating = FloatingPnL(n_open);
   double bigness = (InpAvgWinUsd > 0 && floating > 0) ? floating / InpAvgWinUsd : 0.0;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"S4bTrader\",\"version\":\"1.00\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,\"open\":%s}",
      TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t,TIME_DATE|TIME_SECONDS), InpMagicNumber, InpLots,
      floating, n_open, bigness, InpAvgWinUsd, BuildOpenJson()));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();
   Log(StringFormat("S4bTrader Init — magic=%d lots=%.2f TP=%.1f SL=%.1f (UHV breakout, closer-take variant)",
                    InpMagicNumber, InpLots, InpTPPts, InpSLPts));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { Log(StringFormat("S4b Deinit reason=%d", reason)); }

void OnTick() {
   IsNewDay();
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if (cur != g_last_m1_time && g_last_m1_time != 0) TrySignal();
   g_last_m1_time = cur;
   CheckGrabCommand();
   WriteHeartbeat();
}
