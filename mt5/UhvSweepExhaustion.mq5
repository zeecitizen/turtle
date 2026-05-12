//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5  v2.00 — lesson-2 rewrite (2026-05-12)    |
//|                                                                  |
//| Implements Zee's lessons 1+2 ONLY (M1 UHV breakout). No FVG,     |
//| no sweep, no NSC, no DOM, no ATR trail. Validated on Feb 11      |
//| to capture 20/20 of his strict textbook setups.                  |
//|                                                                  |
//| BUY logic (SELL mirrors):                                        |
//|   1. Just-closed M1 bar is GREEN (close > open).                 |
//|   2. Walk back ≤ MAX_LOOKBACK M1 bars; first bar whose high      |
//|      ≥ breakout.close = swing high. Retracement is between       |
//|      swing high and breakout.                                    |
//|   3. UHV = highest-volume RED bar in retracement.                |
//|   4. Confirm breakout.close > UHV.high AND breakout.vol <        |
//|      UHV.vol.                                                    |
//|   5. Fire BUY at market: SL = UHV.low, TP = entry + (entry-SL)   |
//|      (1:1 R:R per lesson 2).                                     |
//|                                                                  |
//| Dedup: don't re-fire on the same UHV time + side until a new     |
//|        UHV emerges.                                              |
//|                                                                  |
//| Magic 88001 (production). Heartbeat to Common\Files matches v1   |
//| schema so the dashboard keeps working unchanged.                 |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — lesson-2 rewrite, Feb 11 validated"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Entry: lesson-2 UHV breakout ──"
input double InpLots               = 0.10;
input int    InpMaxLookback        = 60;   // bars back to find swing high
input int    InpMaxBarsBack        = 60;   // max bars from UHV to breakout
input int    InpMagicNumber        = 88001;

input group "── Exit: 1R per lesson 2 ──"
input double InpMinR_Points        = 0.10; // reject if R < this
input double InpMaxR_Points        = 30.0; // reject if R > this (catastrophic SL)

input group "── Logging ──"
input bool   InpVerbose            = true;
input string InpLogPrefix          = "UhvL2";
input int    InpHeartbeatSec       = 5;
input string InpStateFile          = "uhv_sweep_state.json";

//── State ───────────────────────────────────────────────────────────
ulong    g_open_ticket          = 0;
double   g_open_entry           = 0;
double   g_open_lots            = 0;
int      g_open_side            = 0;       // +1 buy, -1 sell, 0 none
datetime g_last_signal_uhv_time = 0;
int      g_last_signal_side     = 0;
datetime g_last_check_m1        = 0;
datetime g_last_heartbeat       = 0;
int      g_signals_today        = 0;
int      g_entries_today        = 0;
int      g_exits_today          = 0;
double   g_realized_today_usd   = 0;
int      g_today_day            = 0;
double   g_contract_size        = 100.0;

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

//── Detection: returns +1 buy, -1 sell, 0 none ───────────────────────
int DetectSignal(double &out_uhv_high, double &out_uhv_low,
                 datetime &out_uhv_time, long &out_uhv_vol) {
   int bars_needed = InpMaxLookback + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int got = CopyRates(_Symbol, PERIOD_M1, 0, bars_needed, rates);
   if(got < bars_needed) return 0;

   // Breakout candle = just-closed bar (shift 1). Shift 0 is the forming bar.
   MqlRates bo = rates[1];

   // ── BUY ──
   if(IsGreenBar(bo)) {
      int  uhv_idx = -1;
      long uhv_vol = -1;
      bool found_swing = false;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.high >= bo.close) { found_swing = true; break; }
         if(IsRedBar(c) && (long)c.tick_volume > uhv_vol) {
            uhv_idx = j;
            uhv_vol = (long)c.tick_volume;
         }
      }
      if(!found_swing || uhv_idx < 0) return 0;
      MqlRates uhv = rates[uhv_idx];
      int bars_from_uhv = uhv_idx - 1;
      if(bars_from_uhv > InpMaxBarsBack) return 0;
      if(bo.close <= uhv.high) return 0;
      if((long)bo.tick_volume >= uhv_vol) return 0;
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
      bool found_swing = false;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.low <= bo.close) { found_swing = true; break; }
         if(IsGreenBar(c) && (long)c.tick_volume > uhv_vol) {
            uhv_idx = j;
            uhv_vol = (long)c.tick_volume;
         }
      }
      if(!found_swing || uhv_idx < 0) return 0;
      MqlRates uhv = rates[uhv_idx];
      int bars_from_uhv = uhv_idx - 1;
      if(bars_from_uhv > InpMaxBarsBack) return 0;
      if(bo.close >= uhv.low) return 0;
      if((long)bo.tick_volume >= uhv_vol) return 0;
      out_uhv_high = uhv.high;
      out_uhv_low  = uhv.low;
      out_uhv_time = uhv.time;
      out_uhv_vol  = uhv_vol;
      return -1;
   }

   return 0;
}

//── Fire entry with SL+TP per lesson 2 (1:1 R:R) ───────────────────
void FireEntry(int side, double uhv_high, double uhv_low, datetime uhv_time, long uhv_vol) {
   // Dedup: don't re-fire on the same (UHV time, side)
   if(uhv_time == g_last_signal_uhv_time && side == g_last_signal_side) return;
   // One position at a time
   if(g_open_ticket != 0) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry, sl, tp, r;
   string side_str;

   if(side > 0) {
      entry = ask;
      sl    = uhv_low;
      r     = entry - sl;
      tp    = entry + r;
      side_str = "BUY";
   } else {
      entry = bid;
      sl    = uhv_high;
      r     = sl - entry;
      tp    = entry - r;
      side_str = "SELL";
   }

   if(r < InpMinR_Points) {
      Log("[REJECT] R too small: " + DoubleToString(r, 2) + " < " + DoubleToString(InpMinR_Points, 2));
      g_last_signal_uhv_time = uhv_time;  // suppress retries on this UHV
      g_last_signal_side     = side;
      return;
   }
   if(r > InpMaxR_Points) {
      Log("[REJECT] R too large: " + DoubleToString(r, 2) + " > " + DoubleToString(InpMaxR_Points, 2));
      g_last_signal_uhv_time = uhv_time;
      g_last_signal_side     = side;
      return;
   }

   RollDailyCountersIfNeeded();
   g_signals_today++;

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   bool ok;
   if(side > 0) ok = g_trade.Buy (InpLots, _Symbol, entry, sl, tp, InpLogPrefix);
   else         ok = g_trade.Sell(InpLots, _Symbol, entry, sl, tp, InpLogPrefix);

   if(ok) {
      g_last_signal_uhv_time = uhv_time;
      g_last_signal_side     = side;
      Log("[SIGNAL] " + side_str + " @ " + DoubleToString(entry, _Digits) +
          " SL=" + DoubleToString(sl, _Digits) +
          " TP=" + DoubleToString(tp, _Digits) +
          " R="  + DoubleToString(r, 2) +
          " UHV=" + TimeToString(uhv_time, TIME_DATE|TIME_MINUTES) +
          " (uhv_vol=" + IntegerToString(uhv_vol) + ")");
   } else {
      Log("[ORDER_FAIL] retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment());
   }
}

//── Heartbeat (5s, OnTimer-driven, tick-independent) ───────────────
void WriteHeartbeat() {
   if((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   RollDailyCountersIfNeeded();

   string json = "{";
   json += "\"ts\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"ea\":\"UhvSweepExhaustion v2.00\",";
   json += "\"alive\":true,";
   json += "\"bid\":" + DoubleToString(bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(ask, _Digits) + ",";
   json += "\"contract_size\":" + DoubleToString(g_contract_size, 2) + ",";
   json += "\"signals_today\":" + IntegerToString(g_signals_today) + ",";
   json += "\"entries_today\":" + IntegerToString(g_entries_today) + ",";
   json += "\"exits_today\":" + IntegerToString(g_exits_today) + ",";
   json += "\"realized_today_usd\":" + DoubleToString(g_realized_today_usd, 2) + ",";
   json += "\"position_open\":" + (g_open_ticket != 0 ? "true" : "false") + ",";
   if(g_open_ticket != 0) {
      json += "\"open_ticket\":" + IntegerToString((long)g_open_ticket) + ",";
      json += "\"open_entry\":"  + DoubleToString(g_open_entry, _Digits) + ",";
      json += "\"open_side\":\"" + (g_open_side > 0 ? "BUY" : "SELL") + "\",";
      json += "\"open_lots\":"   + DoubleToString(g_open_lots, 2) + ",";
      if(PositionSelectByTicket(g_open_ticket)) {
         json += "\"open_pnl\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
         json += "\"open_sl\":"  + DoubleToString(PositionGetDouble(POSITION_SL), _Digits) + ",";
         json += "\"open_tp\":"  + DoubleToString(PositionGetDouble(POSITION_TP), _Digits) + ",";
      }
   }
   json += "\"params\":{";
   json += "\"lots\":"     + DoubleToString(InpLots, 2) + ",";
   json += "\"max_lookback\":" + IntegerToString(InpMaxLookback) + ",";
   json += "\"max_bars_back\":" + IntegerToString(InpMaxBarsBack) + ",";
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

//── OnInit: amnesia recovery + timer setup ──────────────────────────
int OnInit() {
   g_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(g_contract_size <= 0) g_contract_size = 100.0;
   int fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   Log("Init v2.00 (lesson-2). MaxLookback=" + IntegerToString(InpMaxLookback) +
       " MaxBarsBack=" + IntegerToString(InpMaxBarsBack) +
       " Lots=" + DoubleToString(InpLots, 2) +
       " Magic=" + IntegerToString(InpMagicNumber) +
       " Filling: FOK=" + ((fill & SYMBOL_FILLING_FOK)?"Y":"N") +
       " IOC=" + ((fill & SYMBOL_FILLING_IOC)?"Y":"N"));

   // Amnesia recovery: scan for existing position with our magic
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0) continue;
      if(!PositionSelectByTicket(tkt)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      g_open_ticket = tkt;
      g_open_entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      g_open_lots   = PositionGetDouble(POSITION_VOLUME);
      g_open_side   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      Log("[REBIND] Resumed ticket=" + IntegerToString((long)tkt) +
          " entry=" + DoubleToString(g_open_entry, _Digits) +
          " side=" + (g_open_side > 0 ? "BUY" : "SELL") +
          " lots=" + DoubleToString(g_open_lots, 2));
      break;
   }

   EventSetTimer(InpHeartbeatSec > 0 ? InpHeartbeatSec : 5);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   Log("Deinit reason=" + IntegerToString(reason));
}

//── OnTimer: heartbeat (tick-independent) ──────────────────────────
void OnTimer() {
   WriteHeartbeat();
}

//── OnTick: detect on every new M1 bar close ──────────────────────
void OnTick() {
   // Reconcile open position state (handles SL/TP closes which fire silently)
   if(g_open_ticket != 0 && !PositionSelectByTicket(g_open_ticket)) {
      // Position closed (TP/SL hit). Look up last closed deal for P&L.
      Log("[CLOSED] ticket=" + IntegerToString((long)g_open_ticket) + " (position no longer exists)");
      // Pull realized P&L from history
      if(HistorySelectByPosition(g_open_ticket)) {
         double total_profit = 0, total_swap = 0, total_comm = 0;
         for(int i = 0; i < HistoryDealsTotal(); i++) {
            ulong dt = HistoryDealGetTicket(i);
            if(dt == 0) continue;
            total_profit += HistoryDealGetDouble(dt, DEAL_PROFIT);
            total_swap   += HistoryDealGetDouble(dt, DEAL_SWAP);
            total_comm   += HistoryDealGetDouble(dt, DEAL_COMMISSION);
         }
         double net = total_profit + total_swap + total_comm;
         g_realized_today_usd += net;
         g_exits_today++;
         Log("[CLOSED] net P&L: $" + DoubleToString(net, 2));
      }
      g_open_ticket = 0;
      g_open_entry  = 0;
      g_open_lots   = 0;
      g_open_side   = 0;
   }

   // Detect only on new M1 bar close
   MqlRates r0[1];
   ArraySetAsSeries(r0, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, 1, r0) < 1) return;
   if(r0[0].time == g_last_check_m1) return;
   g_last_check_m1 = r0[0].time;

   // Only detect if no position is open (one-at-a-time per lesson 2)
   if(g_open_ticket != 0) return;

   double uhv_high, uhv_low;
   datetime uhv_time;
   long uhv_vol;
   int sig = DetectSignal(uhv_high, uhv_low, uhv_time, uhv_vol);
   if(sig != 0) FireEntry(sig, uhv_high, uhv_low, uhv_time, uhv_vol);
}

//── OnTradeTransaction: track fills for state update ──────────────
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
      g_open_ticket = pos_id;
      g_open_entry  = price;
      g_open_lots   = vol;
      g_open_side   = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(deal_ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? +1 : -1;
      g_entries_today++;
      Log("[FILLED] " + (g_open_side > 0 ? "BUY" : "SELL") +
          " ticket=" + IntegerToString((long)pos_id) +
          " @ " + DoubleToString(price, _Digits) +
          " lots=" + DoubleToString(vol, 2));
   }
}
