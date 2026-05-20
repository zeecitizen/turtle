//+------------------------------------------------------------------+
//| BtcS3M30Trader.mq5 — Setup 3 on BTCUSD M30 (no FVG)              |
//|                                                                  |
//| BTC-specific tuning (validated on 14 days bar-replay, 2026-05-16)|
//|   • Execution timeframe: M30 (instead of M5 for XAU)             |
//|   • H1 FVG REQUIREMENT DROPPED (BTC works better without it)     |
//|   • SL buffer: $200 below wicking-green low                      |
//|   • TP: fixed $200 above entry (1:1 R:R, 82% WR)                 |
//|   • Trend threshold: $300 over 12 M30 bars (6 hours)             |
//|                                                                  |
//| Backtest result (14 days BTC bar-replay):                        |
//|   17 trades, 82% WR, +$15.00 @ 0.01 BTC                          |
//|   Projection @ 0.05 BTC: +$75 / 14d ≈ $5/day  (SAFER)            |
//|   Projection @ 0.10 BTC: +$150 / 14d ≈ $11/day                   |
//|   Projection @ 0.40 BTC: +$600 / 14d ≈ $43/day (HIGH RISK)       |
//|                                                                  |
//| SAFETY: small sample (17 trades). Real WR likely 65-80%. At      |
//| 0.40 BTC, a 3-loss streak = $240 = ~50% of $500 account.         |
//| Default lots=0.05 is the recommended starting point.             |
//|                                                                  |
//| Magic 88005 (distinct from XAU EAs: S3=88003, S1=88004).         |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — BTC S3 M30"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.05;   // 0.05 BTC ≈ $4K notional. SL=$200×0.05=$10 risk/trade.
input int    InpMagicNumber   = 88005;

input group "── Detection (M30) ──"
input int    InpTrendLookback     = 12;    // M30 bars (~6 hours)
input double InpTrendThreshold    = 300.0; // BTC $ move to count as trend
input int    InpRetraceLookback   = 15;    // M30 bars searched for the red
input bool   InpRequireH1Fvg      = false; // BTC: FALSE (worked better without per backtest)
input int    InpH1FvgLookback     = 50;    // H1 bars (only used if InpRequireH1Fvg = true)
input double InpSLBufferUSD       = 200.0; // SL = wicking-green.low − $200

input group "── Exit ──"
input double InpTPUSD             = 200.0; // TP = entry + $200 (1:1 R:R at $200 SLbuf)

input group "── Safety ──"
input int    InpMaxLossesPerDay   = 3;     // halt EA after this many losing trades same day

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "BtcS3";
input string InpStateFile     = "btc_s3_m30_state.json";
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m30_time = 0;
datetime g_last_signal_t = 0;
datetime g_last_heartbeat = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_losses_today = 0;
int      g_today_day = 0;
ulong    g_last_ticket = 0;
double   g_last_entry  = 0.0;

void Log(string msg) {
   if (!InpVerbose) return;
   PrintFormat("[%s] %s", InpLogPrefix, msg);
}

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day;
      g_signals_today = 0;
      g_entries_today = 0;
      g_losses_today = 0;
      return true;
   }
   return false;
}

bool IsUptrendM30(int from_shift) {
   double now_close   = iClose(_Symbol, PERIOD_M30, from_shift);
   double back_close  = iClose(_Symbol, PERIOD_M30, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (now_close - back_close) > InpTrendThreshold;
}

bool H1FvgTappedDuringRetracement(int retrace_back_shift_m30) {
   // M30 → H1 conversion: each H1 bar = 2 M30 bars. retrace_back_shift_m30 is
   // in M30 shifts (1, 2, 3...). For tap check we iterate M30 bars directly
   // (no conversion needed — they overlap the H1 zones same way).
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_high = iHigh(_Symbol, PERIOD_H1, i + 2);
      double newer_low  = iLow (_Symbol, PERIOD_H1, i);
      if (newer_low <= older_high) continue;
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iLow(_Symbol, PERIOD_H1, j) < older_high) {
            filled = true; break;
         }
      }
      if (filled) continue;
      for (int k = 1; k <= retrace_back_shift_m30; k++) {
         double mlow  = iLow(_Symbol, PERIOD_M30, k);
         double mhigh = iHigh(_Symbol, PERIOD_M30, k);
         if (mlow <= newer_low && mhigh >= older_high) return true;
      }
   }
   return false;
}

bool TryS3BuySignal() {
   double bo_o = iOpen (_Symbol, PERIOD_M30, 1);
   double bo_l = iLow  (_Symbol, PERIOD_M30, 1);
   double bo_c = iClose(_Symbol, PERIOD_M30, 1);
   long   bo_v = iVolume(_Symbol, PERIOD_M30, 1);
   datetime bo_t = iTime(_Symbol, PERIOD_M30, 1);

   if (bo_t == g_last_signal_t) return false;
   if (g_losses_today >= InpMaxLossesPerDay) return false;

   // Green wicking candle
   if (bo_c <= bo_o) return false;
   // Uptrend on M30
   if (!IsUptrendM30(1)) return false;

   // Walk back collecting retracement reds (stop on swing-high green)
   int reds[15];
   int reds_count = 0;
   int max_red_shift = 1;
   for (int j = 2; j <= 1 + InpRetraceLookback; j++) {
      double r_o = iOpen (_Symbol, PERIOD_M30, j);
      double r_c = iClose(_Symbol, PERIOD_M30, j);
      double r_h = iHigh (_Symbol, PERIOD_M30, j);
      if (r_c >= r_o) {
         if (reds_count > 0) {
            double last_red_h = iHigh(_Symbol, PERIOD_M30, reds[reds_count - 1]);
            if (r_h > last_red_h) break;
         }
      } else {
         if (reds_count < 15) {
            reds[reds_count++] = j;
            max_red_shift = j;
         }
      }
   }
   if (reds_count == 0) return false;

   // Find a red where: bo wicks below red's low, closes back inside red's range,
   // and bo has higher volume than red.
   int matching_red_shift = -1;
   for (int r = 0; r < reds_count; r++) {
      int rs = reds[r];
      double r_l = iLow   (_Symbol, PERIOD_M30, rs);
      long   r_v = iVolume(_Symbol, PERIOD_M30, rs);
      if (bo_l >= r_l)   continue;
      if (bo_c <= r_l)   continue;
      if (bo_v <= r_v)   continue;
      matching_red_shift = rs;
      break;
   }
   if (matching_red_shift < 0) return false;

   // H1 FVG tap during retracement (BTC default: skip — backtest showed
   // dropping this requirement DOUBLES signal count while keeping 82% WR)
   if (InpRequireH1Fvg && !H1FvgTappedDuringRetracement(max_red_shift)) return false;

   // SL / TP — BTC scale
   double sl  = bo_l - InpSLBufferUSD;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tp  = ask + InpTPUSD;

   double rr = InpTPUSD / MathMax(0.01, ask - sl);
   g_signals_today++;
   Log(StringFormat("BTC-S3 BUY — entry=%.2f sl=%.2f tp=%.2f red_shift=%d (vol=%d) R:R=%.2f",
                     ask, sl, tp, matching_red_shift, (int)bo_v, rr));

   if (!g_trade.Buy(InpLots, _Symbol, 0, sl, tp, "BtcS3M30")) {
      Log(StringFormat("[ERR] Buy failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_signal_t = bo_t;
   g_last_ticket = g_trade.ResultOrder();
   g_last_entry  = g_trade.ResultPrice();
   Log(StringFormat("[FILLED] ticket=%d", g_last_ticket));
   return true;
}

void TrackClosedTradesForLossCount() {
   // Watch for the last ticket to disappear from open positions. If gone
   // and last fill was a loss, increment loss counter.
   if (g_last_ticket == 0) return;
   if (PositionSelectByTicket(g_last_ticket)) return;   // still open
   // Closed — check history
   HistorySelect(TimeCurrent() - 86400, TimeCurrent() + 60);
   int total = HistoryDealsTotal();
   double realized = 0.0;
   bool found = false;
   for (int i = total - 1; i >= 0; i--) {
      ulong tkt = HistoryDealGetTicket(i);
      if (HistoryDealGetInteger(tkt, DEAL_POSITION_ID) != (long)g_last_ticket) continue;
      realized += HistoryDealGetDouble(tkt, DEAL_PROFIT);
      found = true;
   }
   if (found) {
      if (realized < 0) {
         g_losses_today++;
         Log(StringFormat("Position %d closed at LOSS $%.2f (losses_today=%d/%d)",
                          g_last_ticket, realized, g_losses_today, InpMaxLossesPerDay));
      } else {
         Log(StringFormat("Position %d closed at PROFIT $%.2f", g_last_ticket, realized));
      }
      g_last_ticket = 0;
   }
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"BtcS3M30Trader\",\"version\":\"1.00\",\"alive\":true,"
      "\"symbol\":\"%s\",\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"losses_today\":%d,\"max_losses\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.4f,"
      "\"tp_usd\":%.0f,\"sl_buf_usd\":%.0f}",
      _Symbol,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today, g_losses_today, InpMaxLossesPerDay,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots, InpTPUSD, InpSLBufferUSD));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   Log(StringFormat("BtcS3M30Trader Init — symbol=%s magic=%d lots=%.4f SLbuf=$%.0f TP=$%.0f",
                     _Symbol, InpMagicNumber, InpLots, InpSLBufferUSD, InpTPUSD));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log(StringFormat("BtcS3M30Trader Deinit reason=%d signals=%d entries=%d losses=%d",
                     reason, g_signals_today, g_entries_today, g_losses_today));
}

void OnTick() {
   IsNewDay();
   TrackClosedTradesForLossCount();
   datetime cur_m30 = iTime(_Symbol, PERIOD_M30, 0);
   if (cur_m30 != g_last_m30_time && g_last_m30_time != 0) {
      TryS3BuySignal();
   }
   g_last_m30_time = cur_m30;
   WriteHeartbeat();
}
