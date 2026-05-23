//+------------------------------------------------------------------+
//| BtcS4bTrader.mq5 — S4b v2.00 for BTCUSD (weekend trading)      |
//|                                                                  |
//| Same logic as S4bTrader.mq5 but with BTCUSD-scaled defaults:    |
//|   UHV range min = 100.0 (BTC M1 candles move $100s not $1s)     |
//|   ATR trailing exit (SL=2x, trail=2x, BE@1x)                   |
//|                                                                  |
//| ⚠️ NOT BACKTESTED on BTC — forward-test only. Parameters may     |
//|   need tuning based on live BTC volatility.                      |
//|                                                                  |
//| Magic 88010 (distinct from S4b=88008 / S4=88007 / S3=88003).    |
//+------------------------------------------------------------------+
#property copyright "Zee + Antigravity — BTC S4b UHV Breakout (ATR trailing exit)"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.02;   // FTMO-safe
input int    InpMagicNumber   = 88010;
input double InpDailyLossHalt = 200.0;  // halt NEW entries if equity down this much today. 0=off.

input group "── Detection (M1) ──"
input int    InpTrendLookback   = 30;   // M1 bars for HH/HL structure
input int    InpRetraceLookback = 12;   // M1 bars to scan for the UHV candle
input double InpMomBodyFrac     = 0.55; // breakout candle body/range >= this
input bool   InpRequireTrend    = true; // require HH/HL structure
input double InpERMin           = 0.15; // Kaufman ER minimum. 0=off.
input double InpUHVRangeMin     = 100.0; // UHV candle range minimum (pts). BTCUSD scale: $100 min. 0=off.
input bool   InpDoBuys          = true;
input bool   InpDoSells         = true;

input group "── Exit (ATR Trailing — walk-forward proven) ──"
input int    InpATRPeriod       = 7;    // ATR lookback period (M1 bars)
input double InpATRSLMult       = 2.0;  // Initial SL = entry ± mult × ATR
input double InpATRTrailMult    = 2.0;  // Trailing SL = peak ± mult × ATR
input double InpATRBEMult       = 1.0;  // Move SL to breakeven when profit >= mult × ATR

input group "── One-tap GRAB ──"
input bool   InpEnableGrab = true;
input double InpAvgWinUsd  = 11.5;      // ~avg win @0.02 for heartbeat 'bigness'
input string InpGrabFile   = "grab_command.txt";

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "BtcS4b";
input string InpStateFile     = "btc_s4b_trader_state.json";
input string InpDecisionCsv   = "btc_s4b_decisions.csv";
input int    InpHeartbeatSec  = 5;

//── Trail tracking per position ─────────────────────────────────────
#define MAX_POSITIONS 20
struct TrailInfo {
   ulong    ticket;
   double   entry_price;
   double   atr_val;        // ATR at time of entry
   double   peak_profit;    // best profit seen (in price pts)
   bool     be_hit;         // breakeven already moved?
   bool     is_buy;
};
TrailInfo g_trail[MAX_POSITIONS];
int       g_trail_count = 0;

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

//── ATR calculation ─────────────────────────────────────────────────
double CalcATR() {
   double sum = 0;
   for (int s = 1; s <= InpATRPeriod; s++) {
      double h  = iHigh (_Symbol, PERIOD_M1, s);
      double l  = iLow  (_Symbol, PERIOD_M1, s);
      double pc = iClose(_Symbol, PERIOD_M1, s + 1);
      double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      sum += tr;
   }
   return sum / InpATRPeriod;
}

//── Trail info management ───────────────────────────────────────────
int FindTrail(ulong ticket) {
   for (int i = 0; i < g_trail_count; i++)
      if (g_trail[i].ticket == ticket) return i;
   return -1;
}

void AddTrail(ulong ticket, double entry, double atr_val, bool isBuy) {
   if (g_trail_count >= MAX_POSITIONS) {
      Log("[WARN] Trail array full, cannot track new position");
      return;
   }
   g_trail[g_trail_count].ticket       = ticket;
   g_trail[g_trail_count].entry_price  = entry;
   g_trail[g_trail_count].atr_val      = atr_val;
   g_trail[g_trail_count].peak_profit  = 0;
   g_trail[g_trail_count].be_hit       = false;
   g_trail[g_trail_count].is_buy       = isBuy;
   g_trail_count++;
}

void RemoveTrail(int idx) {
   if (idx < 0 || idx >= g_trail_count) return;
   for (int i = idx; i < g_trail_count - 1; i++)
      g_trail[i] = g_trail[i + 1];
   g_trail_count--;
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
   if (body / rng < InpMomBodyFrac) return;

   double sb = 0; int nb = 0;
   for (int s = 1; s <= 1 + InpRetraceLookback; s++) { sb += MathAbs(iClose(_Symbol,PERIOD_M1,s)-iOpen(_Symbol,PERIOD_M1,s)); nb++; }
   double avgbody = (nb > 0) ? sb / nb : 0;
   if (body < avgbody) return;
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return;

   int td = TrendDir();
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // BUY: green momentum breaks above the UHV RED candle's high, low vol
   if (InpDoBuys && bo_c > bo_o && (!InpRequireTrend || td == 1)) {
      double uhv_h = 0; long uhv_v = -1;
      for (int s = 2; s <= 1 + InpRetraceLookback; s++) {
         if (iClose(_Symbol,PERIOD_M1,s) < iOpen(_Symbol,PERIOD_M1,s)) {
            double c_rng = iHigh(_Symbol,PERIOD_M1,s) - iLow(_Symbol,PERIOD_M1,s);
            if (InpUHVRangeMin > 0 && c_rng < InpUHVRangeMin) continue;
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
         if (iClose(_Symbol,PERIOD_M1,s) > iOpen(_Symbol,PERIOD_M1,s)) {
            double c_rng = iHigh(_Symbol,PERIOD_M1,s) - iLow(_Symbol,PERIOD_M1,s);
            if (InpUHVRangeMin > 0 && c_rng < InpUHVRangeMin) continue;
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
   double cur_atr = CalcATR();
   if (cur_atr <= 0) { Log("[WARN] ATR=0, skipping trade"); return; }

   double sl_dist = InpATRSLMult * cur_atr;
   double sl = isBuy ? px - sl_dist : px + sl_dist;
   // No fixed TP — trailing handles exit. Set TP=0 (disabled).
   double tp = 0;

   g_signals_today++;
   bool ok = isBuy ? g_trade.Buy (InpLots, _Symbol, 0, sl, tp, StringFormat("S4b_atr%.1f", cur_atr))
                   : g_trade.Sell(InpLots, _Symbol, 0, sl, tp, StringFormat("S4b_atr%.1f", cur_atr));
   if (!ok) { Log(StringFormat("[ERR] %s failed ret=%d", isBuy?"Buy":"Sell", g_trade.ResultRetcode())); return; }
   g_entries_today++;
   g_last_signal_t = bo_t;
   ulong ticket = g_trade.ResultOrder();

   // Track this position for trailing
   AddTrail(ticket, px, cur_atr, isBuy);

   Log(StringFormat("S4b %s @%.2f sl=%.2f (ATR=%.2f, SL=%.1fx) ticket=%I64u",
                    isBuy?"BUY":"SELL", px, sl, cur_atr, InpATRSLMult, ticket));
   LogDecision(isBuy, bo_t, px, sl, tp, ticket);
}

//── ATR Trailing Stop Manager — called every tick ───────────────────
void ManageTrailingStops() {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Clean up closed positions first
   for (int i = g_trail_count - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_trail[i].ticket)) {
         RemoveTrail(i);  // position no longer exists
      }
   }

   // Manage active positions
   for (int i = 0; i < g_trail_count; i++) {
      if (!PositionSelectByTicket(g_trail[i].ticket)) continue;

      double entry = g_trail[i].entry_price;
      double atr_v = g_trail[i].atr_val;
      bool   isBuy = g_trail[i].is_buy;
      double cur_sl = PositionGetDouble(POSITION_SL);

      // Calculate current profit in price points
      double cur_profit;
      if (isBuy)
         cur_profit = bid - entry;
      else
         cur_profit = entry - ask;

      // Update peak profit
      if (cur_profit > g_trail[i].peak_profit)
         g_trail[i].peak_profit = cur_profit;

      double new_sl = cur_sl;
      double be_threshold = InpATRBEMult * atr_v;

      // --- Breakeven: once profit reaches BE threshold, lock entry ---
      if (!g_trail[i].be_hit && cur_profit >= be_threshold) {
         g_trail[i].be_hit = true;
         if (isBuy) {
            new_sl = MathMax(cur_sl, entry);  // move SL up to entry
         } else {
            new_sl = MathMin(cur_sl, entry);  // move SL down to entry
         }
         if (MathAbs(new_sl - cur_sl) > 0.01) {
            Log(StringFormat("[BE] ticket=%I64u → SL=%.2f (profit=%.2f >= %.2f×ATR)",
                            g_trail[i].ticket, new_sl, cur_profit, InpATRBEMult));
         }
      }

      // --- Trailing: trail SL at peak - trail_mult*ATR ---
      double trail_dist = InpATRTrailMult * atr_v;
      if (isBuy) {
         double peak_price = entry + g_trail[i].peak_profit;
         double trail_sl = peak_price - trail_dist;
         if (trail_sl > new_sl) {
            new_sl = trail_sl;
         }
      } else {
         double peak_price = entry - g_trail[i].peak_profit;
         double trail_sl = peak_price + trail_dist;
         if (trail_sl < new_sl) {
            new_sl = trail_sl;
         }
      }

      // --- Apply new SL if it improved ---
      bool should_modify = false;
      if (isBuy && new_sl > cur_sl + 0.01)
         should_modify = true;
      if (!isBuy && new_sl < cur_sl - 0.01)
         should_modify = true;

      if (should_modify) {
         double tp = PositionGetDouble(POSITION_TP);  // preserve existing TP (0)
         if (g_trade.PositionModify(g_trail[i].ticket, new_sl, tp)) {
            Log(StringFormat("[TRAIL] ticket=%I64u SL: %.2f → %.2f (peak=%.2f, ATR=%.2f)",
                            g_trail[i].ticket, cur_sl, new_sl, g_trail[i].peak_profit, atr_v));
         }
      }
   }
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
      "{\"ea\":\"S4bTrader\",\"version\":\"2.00\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,"
      "\"exit_mode\":\"ATR_TRAIL\",\"atr_period\":%d,\"atr_sl_mult\":%.1f,"
      "\"atr_trail_mult\":%.1f,\"atr_be_mult\":%.1f,\"open\":%s}",
      TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t,TIME_DATE|TIME_SECONDS), InpMagicNumber, InpLots,
      floating, n_open, bigness, InpAvgWinUsd,
      InpATRPeriod, InpATRSLMult, InpATRTrailMult, InpATRBEMult, BuildOpenJson()));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trail_count = 0;
   IsNewDay();
   g_last_grab_id = ReadGrabId();
   Log(StringFormat("S4bTrader v2.00 Init — magic=%d lots=%.2f ATR(%d) SL=%.1fx Trail=%.1fx BE=%.1fx UHVrng>=%.1f",
                    InpMagicNumber, InpLots, InpATRPeriod, InpATRSLMult, InpATRTrailMult, InpATRBEMult, InpUHVRangeMin));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { Log(StringFormat("S4b Deinit reason=%d", reason)); }

void OnTick() {
   IsNewDay();
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if (cur != g_last_m1_time && g_last_m1_time != 0) TrySignal();
   g_last_m1_time = cur;

   // ATR trailing stop management — every tick
   ManageTrailingStops();

   CheckGrabCommand();
   WriteHeartbeat();
}
