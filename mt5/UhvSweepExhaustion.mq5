//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5  v3.44 — pyramiding (up to N concurrent)  |
//|                                                                  |
//| Implements Zee's lesson-2 ENTRY: M1 UHV breakout (validated      |
//| 20/20 on Feb 11). Strict-1:1 R:R from lesson 2 was textbook —    |
//| in practice Zee banks small profits aggressively. v3 replaces    |
//| the 1:1 TP with active peak-trail exit + smart-cut.              |
//|                                                                  |
//| v3.43 → v3.44 change: allow MULTIPLE concurrent positions.       |
//|   Sim showed v3.43 detector finds Shano-rate signals (30/hr)     |
//|   but one-position-at-a-time blocked 9 of her 18 fires because   |
//|   the EA was holding an unrelated trade. Pyramiding to N=2 sim-  |
//|   captures 14/18 (78%) vs 9/18 (50%); Feb 11 jumps to 20/20.     |
//|                                                                  |
//| Each position has independent peak/trail/smart-cut state.        |
//|                                                                  |
//| Magic 88001 (production). Heartbeat to Common\Files matches v1   |
//| schema for primary (newest) position; adds positions[] array.    |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — lesson-2 + smart-cut + broker-trail + pyramid"
#property version   "3.44"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Entry: lesson-2 UHV breakout ──"
input double InpLots               = 0.10;
input int    InpMaxLookback        = 60;
input int    InpMaxBarsBack        = 60;
input int    InpMagicNumber        = 88001;
input int    InpMaxConcurrent      = 2;    // v3.44: max concurrent open positions

input group "── Exit: Zee-style active management ──"
input double InpMinR_Points        = 0.10;
input double InpMaxR_Points        = 30.0;
input double InpPeakBankUSD        = 1.0;
input double InpPeakDropUSD        = 0.5;
input double InpTrailUpdateStep    = 0.5;
input double InpEarlyStopUSD       = 2.0;
input double InpEarlyCutPeakGuard  = 1.0;
input int    InpEarlyCutMinBars    = 1;
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

bool AddPos(ulong tkt, double entry, double lots, int side, datetime open_time, datetime uhv_time, double init_peak = 0, int init_bar_count = 0) {
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

//── Fire entry with SL+TP. v3.44: gated by InpMaxConcurrent ─────────
//   Race-safe: g_last_fire_time + g_pending_fires are bumped BEFORE
//   the synchronous Buy/Sell call so consecutive ticks block immediately,
//   and the pending counter caps total positions including in-flight orders
//   (OnTradeTransaction decrements + adds to g_pos[]).
void FireEntry(int side, double uhv_high, double uhv_low, datetime uhv_time, long uhv_vol) {
   if((g_pos_count + g_pending_fires) >= InpMaxConcurrent) return;
   datetime now_t = TimeCurrent();
   if(g_last_fire_time != 0 && (now_t - g_last_fire_time) < 2) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry, sl, tp, r;
   string side_str;

   if(side > 0) {
      entry = ask;
      sl    = uhv_low;
      r     = entry - sl;
      tp    = entry + r * InpTpMultR;
      side_str = "BUY";
   } else {
      entry = bid;
      sl    = uhv_high;
      r     = sl - entry;
      tp    = entry - r * InpTpMultR;
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

   RollDailyCountersIfNeeded();
   g_signals_today++;

   // RESERVE the slot BEFORE the Buy/Sell call so concurrent ticks see the
   // cap and rate-limit immediately. OnTradeTransaction will decrement on fill.
   g_last_fire_time = now_t;
   g_pending_fires++;

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   bool ok;
   if(side > 0) ok = g_trade.Buy (InpLots, _Symbol, entry, sl, tp, InpLogPrefix);
   else         ok = g_trade.Sell(InpLots, _Symbol, entry, sl, tp, InpLogPrefix);

   if(ok) {
      Log("[SIGNAL] " + side_str + " @ " + DoubleToString(entry, _Digits) +
          " SL=" + DoubleToString(sl, _Digits) +
          " TP=" + DoubleToString(tp, _Digits) +
          " R="  + DoubleToString(r, 2) +
          " UHV=" + TimeToString(uhv_time, TIME_DATE|TIME_MINUTES) +
          " (uhv_vol=" + IntegerToString(uhv_vol) + ", concurrent=" + IntegerToString(g_pos_count) +
          ", pending=" + IntegerToString(g_pending_fires) + ")");
      // The actual PosState row is added in OnTradeTransaction when the deal fills.
   } else {
      // Order rejected — release the reserved slot
      g_pending_fires--;
      if(g_pending_fires < 0) g_pending_fires = 0;
      Log("[ORDER_FAIL] retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment() + " (pending released)");
   }
}

//── Heartbeat ───────────────────────────────────────────────────────
void WriteHeartbeat() {
   if((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   RollDailyCountersIfNeeded();

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
   json += "\"ea\":\"UhvSweepExhaustion v3.44\",";
   json += "\"alive\":true,";
   json += "\"bid\":" + DoubleToString(bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(ask, _Digits) + ",";
   json += "\"contract_size\":" + DoubleToString(g_contract_size, 2) + ",";
   json += "\"signals_today\":" + IntegerToString(g_signals_today) + ",";
   json += "\"entries_today\":" + IntegerToString(g_entries_today) + ",";
   json += "\"exits_today\":" + IntegerToString(g_exits_today) + ",";
   json += "\"realized_today_usd\":" + DoubleToString(g_realized_today_usd, 2) + ",";
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
   Log("Init v3.44 (pyramid, max_concurrent=" + IntegerToString(InpMaxConcurrent) + "). " +
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
      AddPos(tkt, entry, lots, side, ot, 0, peak, /*init_bar_count=*/10);
      Log("[REBIND] Resumed ticket=" + IntegerToString((long)tkt) +
          " entry=" + DoubleToString(entry, _Digits) +
          " side=" + (side > 0 ? "BUY" : "SELL") +
          " lots=" + DoubleToString(lots, 2));
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

//── Manage ONE position: peak/trail/smart-cut/time-stop ─────────────
//   Returns true if position was closed (caller should prune array).
//   MQL5 doesn't allow `PosState &p = g_pos[pi]`, so we index directly.
bool ManageOne(int pi) {
   if(!PositionSelectByTicket(g_pos[pi].ticket)) return true;

   double pnl = PositionGetDouble(POSITION_PROFIT);
   if(pnl > g_pos[pi].peak_pnl_usd) g_pos[pi].peak_pnl_usd = pnl;

   // 1. SMART CUT
   if(InpEarlyStopUSD > 0 &&
      g_pos[pi].peak_pnl_usd < InpEarlyCutPeakGuard &&
      g_pos[pi].bar_count >= InpEarlyCutMinBars &&
      pnl <= -InpEarlyStopUSD) {
      Log("[EXIT smart_cut] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
          " pnl=$" + DoubleToString(pnl, 2) +
          " peak=$" + DoubleToString(g_pos[pi].peak_pnl_usd, 2) +
          " bars=" + IntegerToString(g_pos[pi].bar_count));
      g_trade.PositionClose(g_pos[pi].ticket);
      return true;
   }

   // 2. Time stop
   datetime now = TimeCurrent();
   if(InpMaxHoldSec > 0 && (now - g_pos[pi].open_time) >= InpMaxHoldSec) {
      Log("[EXIT time_stop] tkt=" + IntegerToString((long)g_pos[pi].ticket) +
          " pnl=$" + DoubleToString(pnl, 2));
      g_trade.PositionClose(g_pos[pi].ticket);
      return true;
   }

   // 3. Broker-side trailing SL
   if(g_pos[pi].peak_pnl_usd >= InpPeakBankUSD) {
      double target_lock = g_pos[pi].peak_pnl_usd - InpPeakDropUSD;
      if(target_lock > g_pos[pi].locked_pnl_usd + InpTrailUpdateStep - 1e-9) {
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
                  if(pnl <= (g_pos[pi].peak_pnl_usd - InpPeakDropUSD * 4)) {
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
            g_realized_today_usd += net;
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
      AddPos(pos_id, price, vol, side, TimeCurrent(), 0, 0, 0);
      g_entries_today++;
      Log("[FILLED] " + (side > 0 ? "BUY" : "SELL") +
          " ticket=" + IntegerToString((long)pos_id) +
          " @ " + DoubleToString(price, _Digits) +
          " lots=" + DoubleToString(vol, 2) +
          " (open_count=" + IntegerToString(g_pos_count) + ", pending=" + IntegerToString(g_pending_fires) + ")");
   }
}
