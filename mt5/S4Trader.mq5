//+------------------------------------------------------------------+
//| S4Trader.mq5 — "Zee's Feb-11 entry, mechanized" (UHV breakout)    |
//|                                                                  |
//| v2.00 (2026-05-27): REBUILT based on deep parameter sweep         |
//| (s4_deep_sweep.py, 150+ configs, 18 real-tick days from Exness).  |
//|                                                                  |
//| KEY FINDING: The strategy works on M5, NOT M1. M1 was too noisy  |
//| and all M1 scalp configs failed walk-forward. On M5 with a wide  |
//| SL ($7.5) and small TP ($2), the strategy achieves 85.6% WR —    |
//| the closest mechanical match to Zee's Feb-11 trading (94% WR).   |
//|                                                                  |
//| ENTRY (M5, BUY+SELL — teacher's Lesson 02 "Our Strategy"):       |
//|   1. Trend = same-TF market structure (HH+HL = up / LH+LL = dn) |
//|   2. In the retracement (last 12 M5 bars) find the UHV candle    |
//|      (highest volume: red for buy / green for sell)               |
//|   3. A LOW-VOLUME MOMENTUM candle (body>avg, body/range>0.55,    |
//|      vol < UHV) breaks through the UHV line                      |
//|   4. ENTER at the breakout candle's close                        |
//|   NO sweep, NO big-spread, NO FVG, NO ER filter                  |
//| EXIT: TP $2.0 / SL $7.5 (wide SL absorbs noise → 85.6% WR)      |
//|                                                                  |
//| VALIDATION (s4_deep_sweep.py, 18 real-tick days, 0.01 lots):     |
//|   n=111, WR=85.6%, Total=+$69, Train=+$42, OOS=+$27 (WF+ ✅)    |
//|   MaxDD=$25, BUY=+$19, SELL=+$51, both sides positive            |
//|   ~6 trades/day, high WR, low drawdown, $126 account safe        |
//|                                                                  |
//| Magic 88007 (distinct from S3=88003 / S1=88004 / NSND=88006).    |
//+------------------------------------------------------------------+
#property copyright "Zee + Antigravity — S4 UHV Breakout v2 (M5, 85% WR)"
#property version   "2.10"
#property strict

// ╔══════════════════════════════════════════════════════════════════╗
// ║  📄 STRATEGY DOCUMENTATION: docs/S4_STRATEGY.md                 ║
// ║  Contains: Feb-11 investigation, deep parameter sweep results,  ║
// ║  walk-forward validation, and teacher's Lesson 02 comparison.   ║
// ║  READ THAT FILE FIRST before modifying this EA.                 ║
// ╚══════════════════════════════════════════════════════════════════╝

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.01;   // Exness $126 account: conservative. MaxDD $25 = 20% of account.
input int    InpMagicNumber   = 88007;
input double InpDailyLossHalt = 50.0;   // 2026-05-27 Shano $126 acct: ~20% daily-loss cap — halt NEW entries if equity is down this much today (incl. floating). Was FTMO-era $200/$50. Tighten to 15 for stricter. 0=off.

input group "── Detection (M5) ──"
input int    InpTrendLookback   = 30;   // M5 bars for HH/HL structure (recent 15 vs prior 15)
input int    InpRetraceLookback = 12;   // M5 bars to scan for the UHV candle
input double InpMomBodyFrac     = 0.55; // breakout candle body/range >= this (momentum, small wicks)
input bool   InpRequireTrend    = true; // require HH/HL structure in the trade direction
input double InpTrend24Min       = 7.0;  // 2026-05-27: min 24-bar M5 price move in trade direction. VERIFIED (verify_s4_hours.py): +$69->+$87, DD $24.5->$20.5, 5/7 WF splits. (Hour-filter 'skip 12-13' tested too — only 4/7 marginal, NOT added.) 0=off.
input double InpERMin           = 0.15; // 2026-05-29 REVERTED to validated 0.15 (regime filter, skips chop). EA_SYSTEM_STATE: lifted OOS +$473→+$629, 8/13 green days. May-27 disable rode on misaligned harness.
input bool   InpDoBuys          = true;
input bool   InpDoSells         = true;

input group "── Exit (wide SL, small TP → 85% WR) ──"
input double InpTPPts           = 12.0; // 2026-05-29 REVERTED to validated 2:1 (TP12/SL6). May-27 TP2/SL7.5 inverted R:R (breakeven WR went 33%→79%, math broken). At entry's real 63% WR: TP12/SL6 = +$5.34/tr; TP2/SL7.5 = −$1.52/tr.
input double InpSLPts           = 6.0;  // 2026-05-29 REVERTED to validated 6.0 (paired with TP=12 for 2:1 R:R, breakeven WR = 33%).

input group "── One-tap GRAB ──"
input bool   InpEnableGrab = true;
input double InpAvgWinUsd  = 2.0;       // ~avg win @0.01 (TP2 = $2); for heartbeat 'bigness'
input string InpGrabFile   = "grab_command.txt";

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "S4";
input string InpStateFile     = "s4_trader_state.json";
input string InpDecisionCsv   = "s4_decisions.csv";
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m5_time = 0;
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
      rHi = MathMax(rHi, iHigh(_Symbol, PERIOD_M5, s));
      rLo = MathMin(rLo, iLow (_Symbol, PERIOD_M5, s));
   }
   for (int s = half + 1; s <= InpTrendLookback; s++) {
      oHi = MathMax(oHi, iHigh(_Symbol, PERIOD_M5, s));
      oLo = MathMin(oLo, iLow (_Symbol, PERIOD_M5, s));
   }
   if (rHi > oHi && rLo > oLo) return 1;
   if (rHi < oHi && rLo < oLo) return -1;
   return 0;
}

//── Kaufman Efficiency Ratio over the trend window (regime: trend vs range) ──
//   |net change| / sum(|bar-to-bar change|). ~1 = clean trend, ~0 = choppy.
double EfficiencyRatio() {
   double net = MathAbs(iClose(_Symbol,PERIOD_M5,1) - iClose(_Symbol,PERIOD_M5,InpTrendLookback));
   double path = 0;
   for (int s = 1; s < InpTrendLookback; s++)
      path += MathAbs(iClose(_Symbol,PERIOD_M5,s) - iClose(_Symbol,PERIOD_M5,s+1));
   return (path > 0) ? net / path : 0.0;
}

//── Evaluate the just-closed M5 bar (shift 1) for a signal ──
void TrySignal() {
   if (DailyLossHalted()) return;
   datetime bo_t = iTime(_Symbol, PERIOD_M5, 1);
   if (bo_t == g_last_signal_t) return;

   double bo_o = iOpen (_Symbol, PERIOD_M5, 1);
   double bo_h = iHigh (_Symbol, PERIOD_M5, 1);
   double bo_l = iLow  (_Symbol, PERIOD_M5, 1);
   double bo_c = iClose(_Symbol, PERIOD_M5, 1);
   long   bo_v = iVolume(_Symbol, PERIOD_M5, 1);
   double rng = bo_h - bo_l;
   if (rng <= 0) return;
   double body = MathAbs(bo_c - bo_o);
   if (body / rng < InpMomBodyFrac) return;            // momentum candle (small wicks)

   // avg body over the retracement window (shifts 1..1+RetraceLB)
   double sb = 0; int nb = 0;
   for (int s = 1; s <= 1 + InpRetraceLookback; s++) { sb += MathAbs(iClose(_Symbol,PERIOD_M5,s)-iOpen(_Symbol,PERIOD_M5,s)); nb++; }
   double avgbody = (nb > 0) ? sb / nb : 0;
   if (body < avgbody) return;                          // strong candle
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return;  // regime filter (OFF by default)

   int td = TrendDir();
   double td24 = iClose(_Symbol, PERIOD_M5, 1) - iClose(_Symbol, PERIOD_M5, 25);  // 24-bar M5 trend delta
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // BUY: green momentum breaks above the UHV RED candle's high, low vol
   if (InpDoBuys && bo_c > bo_o && (!InpRequireTrend || td == 1) && td24 >= InpTrend24Min) {
      double uhv_h = 0; long uhv_v = -1;
      for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
         if (iClose(_Symbol,PERIOD_M5,s) < iOpen(_Symbol,PERIOD_M5,s)) {   // red
            long v = iVolume(_Symbol, PERIOD_M5, s);
            if (v > uhv_v) { uhv_v = v; uhv_h = iHigh(_Symbol, PERIOD_M5, s); }
         }
      }
      if (uhv_v > 0 && bo_v < uhv_v && bo_c > uhv_h && bo_o <= uhv_h) {
         FireTrade(true, ask, bo_t);
         return;
      }
   }
   // SELL: red momentum breaks below the UHV GREEN candle's low, low vol
   if (InpDoSells && bo_c < bo_o && (!InpRequireTrend || td == -1) && td24 <= -InpTrend24Min) {
      double uhv_l = 0; long uhv_v = -1;
      for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
         if (iClose(_Symbol,PERIOD_M5,s) > iOpen(_Symbol,PERIOD_M5,s)) {   // green
            long v = iVolume(_Symbol, PERIOD_M5, s);
            if (v > uhv_v) { uhv_v = v; uhv_l = iLow(_Symbol, PERIOD_M5, s); }
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
   bool ok = isBuy ? g_trade.Buy (InpLots, _Symbol, 0, sl, tp, "S4_buy")
                   : g_trade.Sell(InpLots, _Symbol, 0, sl, tp, "S4_sell");
   if (!ok) { Log(StringFormat("[ERR] %s failed ret=%d", isBuy?"Buy":"Sell", g_trade.ResultRetcode())); return; }
   g_entries_today++;
   g_last_signal_t = bo_t;
   ulong ticket = g_trade.ResultOrder();
   Log(StringFormat("S4 %s @%.2f sl=%.2f tp=%.2f ticket=%I64u", isBuy?"BUY":"SELL", px, sl, tp, ticket));
   LogDecision(isBuy, bo_t, px, sl, tp, ticket);
}

void LogDecision(bool isBuy, datetime bo_t, double px, double sl, double tp, ulong ticket) {
   int fh = FileOpen(InpDecisionCsv, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ',');
   if (fh == INVALID_HANDLE) {
      fh = FileOpen(InpDecisionCsv, FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ',');
      if (fh == INVALID_HANDLE) return;
      FileWrite(fh, "fire_iso","ea","side","bo_time_iso","entry","sl","tp","ticket","magic","lots");
   } else FileSeek(fh, 0, SEEK_END);
   FileWrite(fh, TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), "S4", isBuy?"buy":"sell",
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

// READ-ONLY: the momentum-UHV setup S4 is currently watching, for the live chart.
// Mirrors TrySignal: td24 momentum direction → highest-volume opposite-colour UHV bar
// in the retracement → its breakout level. No trade logic touched.
string BuildWatchJson() {
   double td24 = iClose(_Symbol,PERIOD_M5,1) - iClose(_Symbol,PERIOD_M5,25);
   int td = TrendDir(), dir = 0;
   if (InpDoBuys && td24 >= InpTrend24Min && (!InpRequireTrend || td == 1)) dir = 1;
   else if (InpDoSells && td24 <= -InpTrend24Min && (!InpRequireTrend || td == -1)) dir = -1;
   if (dir == 0) return "null";
   int uhv_shift = -1; long uhv_v = -1;
   for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
      double o = iOpen(_Symbol,PERIOD_M5,s), c = iClose(_Symbol,PERIOD_M5,s);
      bool match = (dir == 1) ? (c < o) : (c > o);   // buy→UHV red; sell→UHV green
      if (!match) continue;
      long v = iVolume(_Symbol,PERIOD_M5,s);
      if (v > uhv_v) { uhv_v = v; uhv_shift = s; }
   }
   if (uhv_shift < 0) return "null";
   double uhv_h = iHigh(_Symbol,PERIOD_M5,uhv_shift), uhv_l = iLow(_Symbol,PERIOD_M5,uhv_shift);
   return StringFormat(
      "{\"dir\":\"%s\",\"ref_bar_t\":\"%s\",\"ref_high\":%.3f,\"ref_low\":%.3f,\"level\":%.3f,\"setup_bar_t\":\"%s\"}",
      dir == 1 ? "buy" : "sell",
      TimeToString(iTime(_Symbol,PERIOD_M5,uhv_shift),TIME_DATE|TIME_SECONDS),
      uhv_h, uhv_l, (dir == 1 ? uhv_h : uhv_l),
      TimeToString(iTime(_Symbol,PERIOD_M5,1),TIME_DATE|TIME_SECONDS));
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   int n_open = 0; double floating = FloatingPnL(n_open);
   double bigness = (InpAvgWinUsd > 0 && floating > 0) ? floating / InpAvgWinUsd : 0.0;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"S4Trader\",\"version\":\"2.10\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,\"watch\":%s,\"open\":%s}",
      TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t,TIME_DATE|TIME_SECONDS), InpMagicNumber, InpLots,
      floating, n_open, bigness, InpAvgWinUsd, BuildWatchJson(), BuildOpenJson()));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();
   Log(StringFormat("S4Trader Init — magic=%d lots=%.2f TP=%.1f SL=%.1f (2:1 UHV breakout)",
                    InpMagicNumber, InpLots, InpTPPts, InpSLPts));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { Log(StringFormat("S4 Deinit reason=%d", reason)); }

void OnTick() {
   IsNewDay();
   datetime cur = iTime(_Symbol, PERIOD_M5, 0);
   if (cur != g_last_m5_time && g_last_m5_time != 0) TrySignal();
   g_last_m5_time = cur;
   CheckGrabCommand();
   WriteHeartbeat();
}
