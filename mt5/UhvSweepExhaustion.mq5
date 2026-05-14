//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5  v3.48 — PROBE-to-trade (Shano's method)  |
//|                                                                  |
//| Implements Zee's lesson-2 ENTRY: M1 UHV breakout (validated      |
//| 20/20 on Feb 11), fired on EVERY breakout (every few minutes).   |
//|                                                                  |
//| v3.47 → v3.48: add the PROBE. Live trading showed the relaxed    |
//|   detector fires Shano-rate but at 32% WR — trades come in       |
//|   regime streaks (win-run in trend, loss-run in chop). Shano     |
//|   handles this with a 0.01 PROBE: fire on every breakout tiny,   |
//|   scale to full 0.40 ONLY when the probe confirms momentum is    |
//|   real. Chop → probe fails for ~$1, never commits. Trend → probe |
//|   confirms in seconds, commits big.                              |
//|                                                                  |
//|   PROBE  : InpProbeLots (0.01), broker SL at -InpProbeFailUSD.   |
//|     confirm: price moves +InpProbeConfirmPts in favor → close    |
//|              probe, open InpRealLots real trade.                 |
//|     fail  : pnl <= -InpProbeFailUSD OR InpProbeTimeoutSec elapsed |
//|             → close probe, done.                                 |
//|   REAL   : InpRealLots (0.40), resting smart-cut SL + trail-lock |
//|            (all $ thresholds scale by lots/0.10 → constant pts). |
//|                                                                  |
//| Magic 88001 (production). Heartbeat positions[] now tags probe.  |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — lesson-2 + probe-to-trade + smart-cut + trail"
#property version   "3.48"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Entry: lesson-2 UHV breakout ──"
input double InpLots               = 0.10;  // (legacy — probe/real lots below override actual sizing)
input int    InpMaxLookback        = 60;
input int    InpMaxBarsBack        = 60;
input int    InpMagicNumber        = 88001;
input int    InpMaxConcurrent      = 2;    // v3.44: max concurrent open positions (probes + reals combined)
input double InpMaxDailyLossUSD    = 300.0; // v3.46: CIRCUIT BREAKER — stop firing for the rest of the broker day when realized loss exceeds this. 0 = disabled.

input group "── Probe-to-trade (v3.48 — Shano's method) ──"
input double InpProbeLots          = 0.01;  // probe size — fired on every UHV breakout
input double InpRealLots           = 0.40;  // real-trade size after a probe confirms
input double InpProbeConfirmPts    = 0.45;  // probe CONFIRMS (→ scale to real) when price moves this many points in favor
input double InpProbeFailUSD       = 3.0;   // probe FAILS (closes) at this loss — also placed as a resting broker SL
input int    InpProbeTimeoutSec    = 50;    // probe FAILS (closes) after this many seconds if not yet confirmed

input group "── Exit: Zee-style active management ──"
input double InpMinR_Points        = 0.10;
input double InpMaxR_Points        = 30.0;
input double InpPeakBankUSD        = 1.0;
input double InpPeakDropUSD        = 0.5;
input double InpTrailUpdateStep    = 0.5;
input double InpEarlyStopUSD       = 4.0;  // v3.45: was 2.0; bumped to clear spread noise (~$1.40-$2)
input double InpEarlyCutPeakGuard  = 1.0;
input int    InpEarlyCutMinBars    = 0;    // v3.45: deprecated (left for compat); seconds gate replaces it
input int    InpEarlyCutMinSec     = 3;    // v3.45: smart-cut waits this many seconds after entry (lets spread settle, fires fast)
input int    InpMaxHoldSec         = 1800;
input double InpTpMultR            = 10.0;

input group "── Logging ──"
input bool   InpVerbose            = true;
input string InpLogPrefix          = "UhvL2";
input int    InpHeartbeatSec       = 5;
input string InpStateFile          = "uhv_sweep_state.json";

//── State ───────────────────────────────────────────────────────────
#define MAX_POS_SLOTS 10

struct PosState {
   ulong    ticket;
   double   entry;
   double   lots;
   int      side;            // +1 buy, -1 sell
   datetime open_time;
   double   peak_pnl_usd;
   double   locked_pnl_usd;
   int      bar_count;
   datetime uhv_time;
   bool     is_probe;        // v3.48: true while this is a 0.01 probe awaiting confirm/fail
};

PosState g_pos[MAX_POS_SLOTS];
int      g_pos_count           = 0;

datetime g_last_fire_time      = 0;
int      g_pending_fires       = 0;   // orders sent, not yet acknowledged via OnTradeTransaction
datetime g_last_check_m1       = 0;
datetime g_last_heartbeat      = 0;
int      g_signals_today       = 0;
int      g_entries_today       = 0;
int      g_exits_today         = 0;
double   g_realized_today_usd  = 0;
int      g_today_day           = 0;
double   g_contract_size       = 100.0;

CTrade g_trade;

//── Helpers ─────────────────────────────────────────────────────────
void Log(string s) { if(InpVerbose) Print(InpLogPrefix + " " + s); }

bool IsGreenBar(const MqlRates &r) { return r.close > r.open; }
bool IsRedBar  (const MqlRates &r) { return r.close < r.open; }

void RollDailyCountersIfNeeded() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int today_key = dt.year * 10000 + dt.mon * 100 + dt.day;
   if(today_key != g_today_day) {
      g_today_day = today_key;
      g_signals_today = 0;
      g_entries_today = 0;
      g_exits_today   = 0;
      g_realized_today_usd = 0;
   }
}

int FindPosByTicket(ulong tkt) {
   for(int i = 0; i < g_pos_count; i++) if(g_pos[i].ticket == tkt) return i;
   return -1;
}

void RemovePosAt(int idx) {
   if(idx < 0 || idx >= g_pos_count) return;
   for(int j = idx; j < g_pos_count - 1; j++) g_pos[j] = g_pos[j + 1];
   g_pos_count--;
}

bool AddPos(ulong tkt, double entry, double lots, int side, datetime open_time, datetime uhv_time, bool is_probe, double init_peak = 0, int init_bar_count = 0) {
   if(g_pos_count >= MAX_POS_SLOTS) return false;
   g_pos[g_pos_count].ticket         = tkt;
   g_pos[g_pos_count].entry          = entry;
   g_pos[g_pos_count].lots           = lots;
   g_pos[g_pos_count].side           = side;
   g_pos[g_pos_count].open_time      = open_time;
   g_pos[g_pos_count].peak_pnl_usd   = init_peak;
   g_pos[g_pos_count].locked_pnl_usd = 0;
   g_pos[g_pos_count].bar_count      = init_bar_count;
   g_pos[g_pos_count].uhv_time       = uhv_time;
   g_pos[g_pos_count].is_probe       = is_probe;
   g_pos_count++;
   return true;
}

//── Detection: returns +1 buy, -1 sell, 0 none (v3.43 relaxed) ──────
int DetectSignal(double &out_uhv_high, double &out_uhv_low,
                 datetime &out_uhv_time, long &out_uhv_vol) {
   int bars_needed = InpMaxLookback + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int got = CopyRates(_Symbol, PERIOD_M1, 0, bars_needed, rates);
   if(got < bars_needed) return 0;

   MqlRates bo = rates[1];

   // ── BUY ──
   if(IsGreenBar(bo)) {
      int  uhv_idx = -1;
      long uhv_vol = -1;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.high >= bo.close) continue;
         if(IsRedBar(c) && (long)c.tick_volume > uhv_vol) {
            uhv_idx = j;
            uhv_vol = (long)c.tick_volume;
         }
      }
      if(uhv_idx < 0) return 0;
      MqlRates uhv = rates[uhv_idx];
      int bars_from_uhv = uhv_idx - 1;
      if(bars_from_uhv > InpMaxBarsBack) return 0;
      if(bo.close <= uhv.high) return 0;
      out_uhv_high = uhv.high;
      out_uhv_low  = uhv.low;
      out_uhv_time = uhv.time;
      out_uhv_vol  = uhv_vol;
      return +1;
   }

   // ── SELL (mirror) ──
   if(IsRedBar(bo)) {
      int  uhv_idx = -1;
      long uhv_vol = -1;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.low <= bo.close) continue;
         if(IsGreenBar(c) && (long)c.tick_volume > uhv_vol) {
            uhv_idx = j;
            uhv_vol = (long)c.tick_volume;
         }
      }
      if(uhv_idx < 0) return 0;
      MqlRates uhv = rates[uhv_idx];
      int bars_from_uhv = uhv_idx - 1;
      if(bars_from_uhv > InpMaxBarsBack) return 0;
      if(bo.close >= uhv.low) return 0;
      out_uhv_high = uhv.high;
      out_uhv_low  = uhv.low;
      out_uhv_time = uhv.time;
      out_uhv_vol  = uhv_vol;
      return -1;
   }

   return 0;
}

//── Fire a PROBE on a UHV breakout. v3.48 — every breakout fires a
//   0.01 probe; it only scales to a real trade if it confirms momentum.
//   Race-safe: g_last_fire_time + g_pending_fires bumped BEFORE the
//   synchronous order so concurrent ticks block immediately.
void FireEntry(int side, double uhv_high, double uhv_low, datetime uhv_time, long uhv_vol) {
   if((g_pos_count + g_pending_fires) >= InpMaxConcurrent) return;
   datetime now_t = TimeCurrent();
   if(g_last_fire_time != 0 && (now_t - g_last_fire_time) < 2) return;
   // v3.46: CIRCUIT BREAKER — stop firing once daily realized loss hits the cap.
   if(InpMaxDailyLossUSD > 0 && g_realized_today_usd <= -InpMaxDailyLossUSD) {
      if(g_last_fire_time != 0 && (now_t - g_last_fire_time) >= 60) {
         Log("[CIRCUIT_BREAKER] realized=$" + DoubleToString(g_realized_today_usd, 2) +
             " <= -$" + DoubleToString(InpMaxDailyLossUSD, 2) + " — firing disabled for today");
         g_last_fire_time = now_t;  // throttle log to once/min
      }
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry, sl, r, cat_sl;
   string side_str;

   // R measured against the catastrophic UHV level — that's what the
   // min/max-R reject filter validates (setup quality).
   if(side > 0) {
      entry  = ask;
      cat_sl = uhv_low;
      r      = entry - cat_sl;
      side_str = "BUY";
   } else {
      entry  = bid;
      cat_sl = uhv_high;
      r      = cat_sl - entry;
      side_str = "SELL";
   }

   if(r < InpMinR_Points) {
      Log("[REJECT] R too small: " + DoubleToString(r, 2) + " < " + DoubleToString(InpMinR_Points, 2));
      return;
   }
   if(r > InpMaxR_Points) {
      Log("[REJECT] R too large: " + DoubleToString(r, 2) + " > " + DoubleToString(InpMaxR_Points, 2));
      return;
   }

   // v3.48: PROBE — tiny 0.01 position. Resting broker SL at -InpProbeFailUSD
   //   (no chase slippage). No TP — the probe is closed by confirm/fail logic
   //   in ManageOne, not by a take-profit.
   double probe_ppp = InpProbeLots * g_contract_size;   // $/point for the probe
   double fail_pts  = (probe_ppp > 0) ? (InpProbeFailUSD / probe_ppp) : r;
   if(side > 0) sl = entry - fail_pts;
   else         sl = entry + fail_pts;
   sl = NormalizeDouble(sl, _Digits);

   RollDailyCountersIfNeeded();
   g_signals_today++;

   // RESERVE the slot BEFORE the order so concurrent ticks see the cap.
   g_last_fire_time = now_t;
   g_pending_fires++;

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   bool ok;
   if(side > 0) ok = g_trade.Buy (InpProbeLots, _Symbol, entry, sl, 0.0, InpLogPrefix + "_probe");
   else         ok = g_trade.Sell(InpProbeLots, _Symbol, entry, sl, 0.0, InpLogPrefix + "_probe");

   if(ok) {
      Log("[PROBE] " + side_str + " " + DoubleToString(InpProbeLots, 2) + " @ " + DoubleToString(entry, _Digits) +
          " SL=" + DoubleToString(sl, _Digits) + " (-$" + DoubleToString(InpProbeFailUSD, 2) + ")" +
          " confirm@+" + DoubleToString(InpProbeConfirmPts, 2) + "pt" +
          " R=" + DoubleToString(r, 2) + " catSL=" + DoubleToString(cat_sl, _Digits) +
          " UHV=" + TimeToString(uhv_time, TIME_DATE|TIME_MINUTES) +
          " (uhv_vol=" + IntegerToString(uhv_vol) + ", concurrent=" + IntegerToString(g_pos_count) +
          ", pending=" + IntegerToString(g_pending_fires) + ")");
   } else {
      g_pending_fires--;
      if(g_pending_fires < 0) g_pending_fires = 0;
      Log("[ORDER_FAIL] probe retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment() + " (pending released)");
   }
}

//── Scale a confirmed probe up to a REAL trade. v3.48 — called from
//   ManageOne when a probe hits the confirm threshold. Opens InpRealLots
//   with a RESTING smart-cut SL at the constant point-distance the 0.10-lot
//   tuning implies (InpEarlyStopUSD scaled by lots/0.10 → same pts).
void OpenRealTrade(int side, datetime uhv_time) {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = (side > 0) ? ask : bid;

   // smart-cut SL distance in POINTS — constant regardless of lot size:
   //   (InpEarlyStopUSD * lots/0.10) / (lots * contract) = InpEarlyStopUSD / (0.10*contract)
   double sc_points = InpEarlyStopUSD / (0.10 * g_contract_size);
   double sl = (side > 0) ? entry - sc_points : entry + sc_points;
   double tp = (side > 0) ? entry + sc_points * InpTpMultR * 10.0
                          : entry - sc_points * InpTpMultR * 10.0;
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   g_pending_fires++;
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   bool ok;
   if(side > 0) ok = g_trade.Buy (InpRealLots, _Symbol, entry, sl, tp, InpLogPrefix + "_real");
   else         ok = g_trade.Sell(InpRealLots, _Symbol, entry, sl, tp, InpLogPrefix + "_real");

   if(ok) {
      Log("[PROBE_CONFIRM→REAL] " + (side > 0 ? "BUY" : "SELL") + " " +
          DoubleToString(InpRealLots, 2) + " @ " + DoubleToString(entry, _Digits) +
          " SL=" + DoubleToString(sl, _Digits) + " (resting smart-cut)");
   } else {
      g_pending_fires--;
      if(g_pending_fires < 0) g_pending_fires = 0;
      Log("[ORDER_FAIL] real retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment() + " (probe confirmed but real-trade order rejected)");
   }
}

//── Heartbeat ───────────────────────────────────────────────────────
// v3.46: Recompute today's realized P&L from MT5 history. Authoritative — survives
//        reattach (which used to bias the accumulator toward post-reattach trades).
//        Sums profit + swap + commission for all closed deals with our magic, from
//        broker-day-start to now.
void RefreshRealizedFromHistory() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime day_start = StructToTime(dt);
   if(!HistorySelect(day_start, TimeCurrent())) return;
   double total = 0;
   int deals_n = HistoryDealsTotal();
   for(int i = 0; i < deals_n; i++) {
      ulong dt_ticket = HistoryDealGetTicket(i);
      if(dt_ticket == 0) continue;
      if(HistoryDealGetInteger(dt_ticket, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetString(dt_ticket, DEAL_SYMBOL) != _Symbol) continue;
      // Only "out" deals carry realized P&L (in deals always have profit=0)
      total += HistoryDealGetDouble(dt_ticket, DEAL_PROFIT);
      total += HistoryDealGetDouble(dt_ticket, DEAL_SWAP);
      total += HistoryDealGetDouble(dt_ticket, DEAL_COMMISSION);
   }
   g_realized_today_usd = total;
}

void WriteHeartbeat() {
   if((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   RollDailyCountersIfNeeded();
   RefreshRealizedFromHistory();   // v3.46: always read from authoritative source

   // Aggregate PnL of all open positions
   double total_open_pnl = 0;
   for(int i = 0; i < g_pos_count; i++) {
      if(PositionSelectByTicket(g_pos[i].ticket)) {
         total_open_pnl += PositionGetDouble(POSITION_PROFIT);
      }
   }

   string json = "{";
   json += "\"ts\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"ea\":\"UhvSweepExhaustion v3.48\",";
   json += "\"alive\":true,";
   json += "\"bid\":" + DoubleToString(bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(ask, _Digits) + ",";
   json += "\"contract_size\":" + DoubleToString(g_contract_size, 2) + ",";
   json += "\"signals_today\":" + IntegerToString(g_signals_today) + ",";
   json += "\"entries_today\":" + IntegerToString(g_entries_today) + ",";
   json += "\"exits_today\":" + IntegerToString(g_exits_today) + ",";
   json += "\"realized_today_usd\":" + DoubleToString(g_realized_today_usd, 2) + ",";
   json += "\"max_daily_loss_usd\":" + DoubleToString(InpMaxDailyLossUSD, 2) + ",";
   json += "\"circuit_breaker_tripped\":" +
           ((InpMaxDailyLossUSD > 0 && g_realized_today_usd <= -InpMaxDailyLossUSD) ? "true" : "false") + ",";
   json += "\"position_open\":" + (g_pos_count > 0 ? "true" : "false") + ",";
   json += "\"open_count\":" + IntegerToString(g_pos_count) + ",";
   json += "\"open_pnl_total\":" + DoubleToString(total_open_pnl, 2) + ",";

   // Primary (newest) position for legacy dashboard compat
   if(g_pos_count > 0) {
      int idx = g_pos_count - 1;
      json += "\"open_ticket\":" + IntegerToString((long)g_pos[idx].ticket) + ",";
      json += "\"open_entry\":"  + DoubleToString(g_pos[idx].entry, _Digits) + ",";
      json += "\"open_side\":\"" + (g_pos[idx].side > 0 ? "BUY" : "SELL") + "\",";
      json += "\"open_lots\":"   + DoubleToString(g_pos[idx].lots, 2) + ",";
      if(PositionSelectByTicket(g_pos[idx].ticket)) {
         json += "\"open_pnl\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
         json += "\"open_sl\":"  + DoubleToString(PositionGetDouble(POSITION_SL), _Digits) + ",";
         json += "\"open_tp\":"  + DoubleToString(PositionGetDouble(POSITION_TP), _Digits) + ",";
      }
   }

   // Per-position array (v3.44)
   json += "\"positions\":[";
   for(int i = 0; i < g_pos_count; i++) {
      if(i > 0) json += ",";
      double p_pnl = 0;
      if(PositionSelectByTicket(g_pos[i].ticket)) p_pnl = PositionGetDouble(POSITION_PROFIT);
      json += "{\"ticket\":" + IntegerToString((long)g_pos[i].ticket) +
              ",\"side\":\"" + (g_pos[i].side > 0 ? "BUY" : "SELL") + "\"" +
              ",\"is_probe\":" + (g_pos[i].is_probe ? "true" : "false") +
              ",\"lots\":" + DoubleToString(g_pos[i].lots, 2) +
              ",\"entry\":" + DoubleToString(g_pos[i].entry, _Digits) +
              ",\"pnl\":" + DoubleToString(p_pnl, 2) +
              ",\"peak\":" + DoubleToString(g_pos[i].peak_pnl_usd, 2) +
              ",\"locked\":" + DoubleToString(g_pos[i].locked_pnl_usd, 2) +
              ",\"bars\":" + IntegerToString(g_pos[i].bar_count) + "}";
   }
   json += "],";

   json += "\"params\":{";
   json += "\"lots\":"     + DoubleToString(InpLots, 2) + ",";
   json += "\"max_lookback\":" + IntegerToString(InpMaxLookback) + ",";
   json += "\"max_bars_back\":" + IntegerToString(InpMaxBarsBack) + ",";
   json += "\"max_concurrent\":" + IntegerToString(InpMaxConcurrent) + ",";
   json += "\"min_r_pts\":" + DoubleToString(InpMinR_Points, 2) + ",";
   json += "\"max_r_pts\":" + DoubleToString(InpMaxR_Points, 2);
   json += "}";
   json += "}";

   int h = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
   }
}

//── OnInit: amnesia recovery ────────────────────────────────────────
int OnInit() {
   g_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(g_contract_size <= 0) g_contract_size = 100.0;
   int fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   Log("Init v3.48 (PROBE-to-trade, circuit_breaker=$" + DoubleToString(InpMaxDailyLossUSD, 2) +
       ", smart-cut " + IntegerToString(InpEarlyCutMinSec) + "s/$" + DoubleToString(InpEarlyStopUSD, 2) +
       ", pyramid max=" + IntegerToString(InpMaxConcurrent) + "). " +
       "Lots=" + DoubleToString(InpLots, 2) +
       " Magic=" + IntegerToString(InpMagicNumber) +
       " Filling: FOK=" + (((fill & SYMBOL_FILLING_FOK) != 0)?"Y":"N") +
       " IOC=" + (((fill & SYMBOL_FILLING_IOC) != 0)?"Y":"N"));

   g_pos_count = 0;
   // Rebind ALL existing positions with our magic
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0) continue;
      if(!PositionSelectByTicket(tkt)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double lots  = PositionGetDouble(POSITION_VOLUME);
      int    side  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      datetime ot  = (datetime)PositionGetInteger(POSITION_TIME);
      double peak  = MathMax(0.0, PositionGetDouble(POSITION_PROFIT));
      bool is_probe = (lots < (InpProbeLots + InpRealLots) / 2.0);
      AddPos(tkt, entry, lots, side, ot, 0, is_probe, peak, /*init_bar_count=*/10);
      Log("[REBIND] Resumed ticket=" + IntegerToString((long)tkt) +
          " entry=" + DoubleToString(entry, _Digits) +
          " side=" + (side > 0 ? "BUY" : "SELL") +
          " lots=" + DoubleToString(lots, 2) +
          " (" + (is_probe ? "probe" : "real") + ")");
   }

   EventSetTimer(InpHeartbeatSec > 0 ? InpHeartbeatSec : 5);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   Log("Deinit reason=" + IntegerToString(reason));
}

void OnTimer() {
   WriteHeartbeat();
}

//── Manage ONE position. Returns true if the position was closed
//   (caller prunes the array). v3.48: branches on is_probe.
//   MQL5 doesn't allow `PosState &p = g_pos[pi]`, so we index directly.
bool ManageOne(int pi) {
   if(!PositionSelectByTicket(g_pos[pi].ticket)) return true;

   double pnl = PositionGetDouble(POSITION_PROFIT);
   if(pnl > g_pos[pi].peak_pnl_usd) g_pos[pi].peak_pnl_usd = pnl;
   int elapsed_sec = (int)(TimeCurrent() - g_pos[pi].open_time);

   // ════════════════ PROBE LIFECYCLE (v3.48) ════════════════
   if(g_pos[pi].is_probe) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      // favorable move in POINTS (sell measured on ask, buy on bid — the side
      // we'd close against; conservative)
      double fav_pts = (g_pos[pi].side > 0) ? (bid - g_pos[pi].entry)
                                            : (g_pos[pi].entry - ask);

      // CONFIRM → close probe, open real trade
      if(fav_pts >= InpProbeConfirmPts) {
         int side = g_pos[pi].side;
         datetime uhv_t = g_pos[pi].uhv_time;
         Log("[PROBE_CONFIRM] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
             " fav=" + DoubleToString(fav_pts, 2) + "pt (>= " + DoubleToString(InpProbeConfirmPts, 2) +
             ") elapsed=" + IntegerToString(elapsed_sec) + "s pnl=$" + DoubleToString(pnl, 2));
         g_trade.PositionClose(g_pos[pi].ticket);
         OpenRealTrade(side, uhv_t);
         return true;
      }
      // FAIL → timeout or loss (the -$ loss is also a resting broker SL backstop)
      if(elapsed_sec >= InpProbeTimeoutSec || pnl <= -InpProbeFailUSD) {
         string why = (pnl <= -InpProbeFailUSD) ? "loss" : "timeout";
         Log("[PROBE_FAIL " + why + "] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
             " pnl=$" + DoubleToString(pnl, 2) + " fav=" + DoubleToString(fav_pts, 2) +
             "pt elapsed=" + IntegerToString(elapsed_sec) + "s");
         g_trade.PositionClose(g_pos[pi].ticket);
         return true;
      }
      return false;   // probe still pending
   }

   // ════════════════ REAL-TRADE LIFECYCLE ════════════════
   // $ thresholds scale by lots/0.10 so the POINT distances stay constant
   // regardless of whether the real trade is 0.10, 0.20 or 0.40 lots.
   double lot_scale  = g_pos[pi].lots / 0.10;
   double early_stop = InpEarlyStopUSD      * lot_scale;
   double peak_guard = InpEarlyCutPeakGuard * lot_scale;
   double peak_bank  = InpPeakBankUSD       * lot_scale;
   double peak_drop  = InpPeakDropUSD       * lot_scale;
   double trail_step = InpTrailUpdateStep   * lot_scale;

   // 1. SMART CUT — v3.48: DEEP BACKSTOP ONLY. The real-trade's resting broker SL
   //    already sits at -early_stop and fills cleanly without chase slippage.
   //    A software market-close at the SAME level races the broker SL and (we saw
   //    live 2026-05-14) chases to -$19 instead of -$14. So the software check now
   //    fires only at 2x the SL distance — i.e. "the broker SL didn't fire, emergency."
   double smartcut_backstop = early_stop * 2.0;
   if(smartcut_backstop > 0 &&
      g_pos[pi].peak_pnl_usd < peak_guard &&
      elapsed_sec >= InpEarlyCutMinSec &&
      pnl <= -smartcut_backstop) {
      Log("[EXIT smart_cut BACKSTOP] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
          " pnl=$" + DoubleToString(pnl, 2) + " (broker SL failed to fire?)" +
          " peak=$" + DoubleToString(g_pos[pi].peak_pnl_usd, 2) +
          " elapsed=" + IntegerToString(elapsed_sec) + "s");
      g_trade.PositionClose(g_pos[pi].ticket);
      return true;
   }

   // 2. Time stop
   if(InpMaxHoldSec > 0 && elapsed_sec >= InpMaxHoldSec) {
      Log("[EXIT time_stop] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
          " pnl=$" + DoubleToString(pnl, 2));
      g_trade.PositionClose(g_pos[pi].ticket);
      return true;
   }

   // 3. Broker-side trailing SL
   if(g_pos[pi].peak_pnl_usd >= peak_bank) {
      double target_lock = g_pos[pi].peak_pnl_usd - peak_drop;
      if(target_lock > g_pos[pi].locked_pnl_usd + trail_step - 1e-9) {
         double pnl_per_point = g_pos[pi].lots * g_contract_size;
         if(pnl_per_point > 0) {
            double sl_distance_pts = target_lock / pnl_per_point;
            double new_sl;
            if(g_pos[pi].side > 0) new_sl = g_pos[pi].entry + sl_distance_pts;
            else                   new_sl = g_pos[pi].entry - sl_distance_pts;
            new_sl = NormalizeDouble(new_sl, _Digits);
            double cur_tp = PositionGetDouble(POSITION_TP);
            double cur_sl = PositionGetDouble(POSITION_SL);
            bool better = (g_pos[pi].side > 0 && new_sl > cur_sl) || (g_pos[pi].side < 0 && new_sl < cur_sl);
            if(better) {
               if(g_trade.PositionModify(g_pos[pi].ticket, new_sl, cur_tp)) {
                  g_pos[pi].locked_pnl_usd = target_lock;
                  Log("[TRAIL_LOCK] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
                      " peak=$" + DoubleToString(g_pos[pi].peak_pnl_usd, 2) +
                      " locked=$" + DoubleToString(target_lock, 2) +
                      " sl=" + DoubleToString(new_sl, _Digits));
               } else {
                  if(pnl <= (g_pos[pi].peak_pnl_usd - peak_drop * 4)) {
                     Log("[EXIT fallback] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
                         " modify failed, pnl=$" + DoubleToString(pnl, 2));
                     g_trade.PositionClose(g_pos[pi].ticket);
                     return true;
                  }
               }
            }
         }
      }
   }
   return false;
}

//── Reconcile closed positions: scan g_pos[], log & prune any whose
//   ticket no longer exists in MT5.
void ReconcileClosed() {
   for(int i = g_pos_count - 1; i >= 0; i--) {
      if(!PositionSelectByTicket(g_pos[i].ticket)) {
         // Position closed (SL/TP/manual). Pull realized P&L from history.
         Log("[CLOSED] tkt=" + IntegerToString((long)g_pos[i].ticket) +
             " peak_was=$" + DoubleToString(g_pos[i].peak_pnl_usd, 2));
         // v3.46: per-position P&L log only — running total is now refreshed
         //   from MT5 history every heartbeat (RefreshRealizedFromHistory),
         //   so we no longer accumulate here (which caused double-count / drift).
         if(HistorySelectByPosition(g_pos[i].ticket)) {
            double total_profit = 0, total_swap = 0, total_comm = 0;
            for(int k = 0; k < HistoryDealsTotal(); k++) {
               ulong dt = HistoryDealGetTicket(k);
               if(dt == 0) continue;
               total_profit += HistoryDealGetDouble(dt, DEAL_PROFIT);
               total_swap   += HistoryDealGetDouble(dt, DEAL_SWAP);
               total_comm   += HistoryDealGetDouble(dt, DEAL_COMMISSION);
            }
            double net = total_profit + total_swap + total_comm;
            g_exits_today++;
            Log("[CLOSED] tkt=" + IntegerToString((long)g_pos[i].ticket) +
                " net P&L: $" + DoubleToString(net, 2));
         }
         RemovePosAt(i);
      }
   }
}

void OnTick() {
   ReconcileClosed();

   // Check for new M1 bar — needed for bar-count tracking (smart-cut gate)
   MqlRates r0[];
   ArraySetAsSeries(r0, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, 1, r0) < 1) return;
   bool new_m1_bar = (r0[0].time != g_last_check_m1);
   if(new_m1_bar) {
      g_last_check_m1 = r0[0].time;
      for(int i = 0; i < g_pos_count; i++) g_pos[i].bar_count++;
   }

   // Manage every open position
   for(int i = g_pos_count - 1; i >= 0; i--) {
      if(ManageOne(i)) RemovePosAt(i);
   }

   // Detect + fire new entry if capacity remaining
   if(g_pos_count >= InpMaxConcurrent) return;
   double uhv_high, uhv_low;
   datetime uhv_time;
   long uhv_vol;
   int sig = DetectSignal(uhv_high, uhv_low, uhv_time, uhv_vol);
   if(sig != 0) FireEntry(sig, uhv_high, uhv_low, uhv_time, uhv_vol);
}

//── OnTradeTransaction: track fills to add new PosState rows ──────
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req,
                        const MqlTradeResult &res) {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(trans.symbol != _Symbol) return;
   ulong deal_ticket = trans.deal;
   if(deal_ticket == 0) return;
   if(!HistoryDealSelect(deal_ticket)) return;
   long magic = (long)HistoryDealGetInteger(deal_ticket, DEAL_MAGIC);
   if(magic != InpMagicNumber) return;
   int entry_type = (int)HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
   ulong pos_id = (ulong)HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);
   double price = HistoryDealGetDouble(deal_ticket, DEAL_PRICE);
   double vol   = HistoryDealGetDouble(deal_ticket, DEAL_VOLUME);

   if(entry_type == DEAL_ENTRY_IN) {
      // Release the pending-fires slot now that the order is acknowledged
      if(g_pending_fires > 0) g_pending_fires--;
      // Skip if already tracked (defensive — should not happen)
      if(FindPosByTicket(pos_id) >= 0) return;
      int side = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(deal_ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? +1 : -1;
      // v3.48: classify probe vs real by lot size (probe 0.01, real 0.40 — midpoint split)
      bool is_probe = (vol < (InpProbeLots + InpRealLots) / 2.0);
      AddPos(pos_id, price, vol, side, TimeCurrent(), 0, is_probe, 0, 0);
      g_entries_today++;
      Log("[FILLED] " + (is_probe ? "PROBE " : "REAL ") + (side > 0 ? "BUY" : "SELL") +
          " ticket=" + IntegerToString((long)pos_id) +
          " @ " + DoubleToString(price, _Digits) +
          " lots=" + DoubleToString(vol, 2) +
          " (open_count=" + IntegerToString(g_pos_count) + ", pending=" + IntegerToString(g_pending_fires) + ")");
   }
}
