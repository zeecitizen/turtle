//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5  v3.43 — Shano-rate detector relaxation   |
//|                                                                  |
//| Implements Zee's lesson-2 ENTRY: M1 UHV breakout (validated      |
//| 20/20 on Feb 11). Strict-1:1 R:R from lesson 2 was textbook —    |
//| in practice Zee banks small profits aggressively. v3 replaces    |
//| the 1:1 TP with active peak-trail exit (proven $3/$1) + a 30-min |
//| time stop. SL stays at UHV.low as catastrophic backstop.         |
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
#property copyright "Zee + Claude — lesson-2 + smart-cut + broker-trail SL"
#property version   "3.43"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Entry: lesson-2 UHV breakout ──"
input double InpLots               = 0.10;
input int    InpMaxLookback        = 60;   // bars back to find swing high
input int    InpMaxBarsBack        = 60;   // max bars from UHV to breakout
input int    InpMagicNumber        = 88001;

input group "── Exit: Zee-style active management (NOT lesson-2 1:1) ──"
input double InpMinR_Points        = 0.10; // reject if R < this
input double InpMaxR_Points        = 30.0; // reject if R > this (catastrophic SL)
input double InpPeakBankUSD        = 1.0;  // engage broker-side trail as soon as P&L peaks at this
input double InpPeakDropUSD        = 0.5;  // SL locks profit at (peak - this); broker fills exactly here
input double InpTrailUpdateStep    = 0.5;  // v3.42: only modify SL when peak grew this much from last lock (rate-limit)
input double InpEarlyStopUSD       = 2.0;  // v3.42: SMART CUT — close if pnl ≤ -this AND peak < InpEarlyCutPeakGuard AND bars ≥ InpEarlyCutMinBars. Targets "trade went straight against entry, no recovery" pattern.
input double InpEarlyCutPeakGuard  = 1.0;  // v3.42: must match InpPeakBankUSD — once peak-trail engages (peak >= bank), smart cut backs off and lets the trail handle.
input int    InpEarlyCutMinBars    = 1;    // v3.42: minimum M1 bars in position before smart cut can fire (avoids firing on entry-bar spread noise).
input int    InpMaxHoldSec         = 1800; // 30-min time stop
input double InpTpMultR            = 10.0; // TP placed wide; peak-trail handles real exits

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
datetime g_open_time            = 0;
double   g_peak_pnl_usd         = 0;       // for active peak-trail exit
double   g_locked_pnl_usd       = 0;       // v3.42: profit currently locked by broker-side trailing SL
int      g_open_bar_count       = 0;       // v3.42: # of M1 bar transitions since entry (smart-cut gate)
datetime g_last_signal_uhv_time = 0;   // (v3.42 informational only — no longer used to block fires)
int      g_last_signal_side     = 0;   // (v3.42 informational only)
datetime g_last_fire_time       = 0;   // v3.42: rate-limit min 2s between fires
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
   // v3.43 RELAX: drop bo.vol < uhv.vol (Shano fires on high-vol breakouts too)
   //              and treat overlap bars as non-fatal (continue instead of break)
   if(IsGreenBar(bo)) {
      int  uhv_idx = -1;
      long uhv_vol = -1;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.high >= bo.close) continue;   // skip overlap candidates, keep walking
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
   // v3.43 RELAX: same two relaxations as buy side.
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

//── Fire entry with SL+TP per lesson 2 (1:1 R:R) ───────────────────
void FireEntry(int side, double uhv_high, double uhv_low, datetime uhv_time, long uhv_vol) {
   // v3.42: REMOVED forever-dedup on (UHV time, side). Shano scales in on the
   //   same UHV setup multiple times per minute. The only constraints now are:
   //     (a) no concurrent positions (one-at-a-time)
   //     (b) min 2-second gap between fires (rate-limit, not signal-block)
   // The peak-trail / smart-cut exits handle the per-trade lifecycle.
   if(g_open_ticket != 0) return;
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
      tp    = entry + r * InpTpMultR;  // wide TP — peak-trail handles real exit
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
      g_last_fire_time       = TimeCurrent();   // v3.42
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
   json += "\"ea\":\"UhvSweepExhaustion v3.43\",";
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
   Log("Init v3.43 (detector relax: drop vol-check + non-fatal lookback). MaxLookback=" + IntegerToString(InpMaxLookback) +
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
      g_open_ticket  = tkt;
      g_open_entry   = PositionGetDouble(POSITION_PRICE_OPEN);
      g_open_lots    = PositionGetDouble(POSITION_VOLUME);
      g_open_side    = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      g_open_time      = (datetime)PositionGetInteger(POSITION_TIME);
      g_peak_pnl_usd   = MathMax(0.0, PositionGetDouble(POSITION_PROFIT));
      g_locked_pnl_usd = 0;   // v3.42 — let trail re-lock from scratch
      // v3.42: rebound position has unknown bar count. Set high enough that
      // smart cut can fire immediately if pnl is already deeply negative.
      g_open_bar_count = 10;
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

//── Active exit: peak-trail + time stop. Per-tick when position open.
//   Models Zee's actual exit behavior: bank small profits aggressively,
//   let runners run with $1 drawdown trail, cap holds at 30 min.
void ManageOpenPosition() {
   if(g_open_ticket == 0) return;
   if(!PositionSelectByTicket(g_open_ticket)) return;

   double pnl = PositionGetDouble(POSITION_PROFIT);
   if(pnl > g_peak_pnl_usd) g_peak_pnl_usd = pnl;

   // 1. v3.42 SMART CUT — close trades that went straight against entry without
   //    ever showing protective profit. Three guards keep this from killing winners:
   //      (a) peak_pnl < InpEarlyCutPeakGuard ($1.00) — once peak-trail can engage,
   //          let the trail handle the exit instead (don't double-cut recoveries)
   //      (b) g_open_bar_count >= InpEarlyCutMinBars (≥1) — avoid firing on entry-bar
   //          spread noise (-$2 is normal at entry for XAU at 0.10 lots)
   //      (c) pnl <= -InpEarlyStopUSD ($2) — only fires once loss exceeds threshold
   //    Validated overnight: saves ~$22 per "no-peak" loss across 64 days,
   //    doesn't kill any of Zee's 20 textbook Feb 11 trades.
   if(InpEarlyStopUSD > 0 &&
      g_peak_pnl_usd < InpEarlyCutPeakGuard &&
      g_open_bar_count >= InpEarlyCutMinBars &&
      pnl <= -InpEarlyStopUSD) {
      Log("[EXIT smart_cut] pnl=$" + DoubleToString(pnl, 2) +
          " peak=$" + DoubleToString(g_peak_pnl_usd, 2) +
          " bars=" + IntegerToString(g_open_bar_count) +
          " (never reached $" + DoubleToString(InpEarlyCutPeakGuard, 2) + " peak)");
      g_trade.PositionClose(g_open_ticket);
      return;
   }

   // 2. Time stop
   datetime now = TimeCurrent();
   if(InpMaxHoldSec > 0 && (now - g_open_time) >= InpMaxHoldSec) {
      Log("[EXIT time_stop] pnl=$" + DoubleToString(pnl, 2) +
          " peak=$" + DoubleToString(g_peak_pnl_usd, 2) +
          " held=" + IntegerToString((int)(now - g_open_time)) + "s");
      g_trade.PositionClose(g_open_ticket);
      return;
   }

   // 3. v3.42 BROKER-SIDE TRAILING SL — once peak hits bank threshold, lock
   //    (peak - drop) USD profit as a broker-side stop loss. Broker fills
   //    exactly at the locked price regardless of tick gaps that previously
   //    caused 1-2 USD slippage on fast reversals (the Shano-vs-EA gap).
   if(g_peak_pnl_usd >= InpPeakBankUSD) {
      double target_lock = g_peak_pnl_usd - InpPeakDropUSD;
      if(target_lock > g_locked_pnl_usd + InpTrailUpdateStep - 1e-9) {
         double pnl_per_point = g_open_lots * g_contract_size;  // e.g. 0.10 * 100 = $10/pt for XAUUSD
         if(pnl_per_point > 0) {
            double sl_distance_pts = target_lock / pnl_per_point;
            double new_sl;
            if(g_open_side > 0) {
               new_sl = g_open_entry + sl_distance_pts;
            } else {
               new_sl = g_open_entry - sl_distance_pts;
            }
            new_sl = NormalizeDouble(new_sl, _Digits);
            double cur_tp = PositionGetDouble(POSITION_TP);
            double cur_sl = PositionGetDouble(POSITION_SL);
            // Only modify if the new SL improves (locks more profit)
            bool better = (g_open_side > 0 && new_sl > cur_sl) || (g_open_side < 0 && new_sl < cur_sl);
            if(better) {
               if(g_trade.PositionModify(g_open_ticket, new_sl, cur_tp)) {
                  g_locked_pnl_usd = target_lock;
                  Log("[TRAIL_LOCK] peak=$" + DoubleToString(g_peak_pnl_usd, 2) +
                      " locked=$" + DoubleToString(target_lock, 2) +
                      " sl=" + DoubleToString(new_sl, _Digits));
               } else {
                  // Failed modify: fall back to immediate close on big drawdown
                  if(pnl <= (g_peak_pnl_usd - InpPeakDropUSD * 4)) {
                     Log("[EXIT fallback] PositionModify failed, pnl=$" + DoubleToString(pnl, 2));
                     g_trade.PositionClose(g_open_ticket);
                     return;
                  }
               }
            }
         }
      }
   }
}

//── OnTick: detect on every new M1 bar close ──────────────────────
void OnTick() {
   // Reconcile open position state (handles SL/TP closes which fire silently)
   if(g_open_ticket != 0 && !PositionSelectByTicket(g_open_ticket)) {
      // Position closed (TP/SL hit or active exit). Look up last closed deal for P&L.
      Log("[CLOSED] ticket=" + IntegerToString((long)g_open_ticket) +
          " peak_was=$" + DoubleToString(g_peak_pnl_usd, 2));
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
      g_open_ticket    = 0;
      g_open_entry     = 0;
      g_open_lots      = 0;
      g_open_side      = 0;
      g_open_time      = 0;
      g_peak_pnl_usd   = 0;
      g_locked_pnl_usd = 0;   // v3.42
      g_open_bar_count = 0;   // v3.42
   }

   // Check for new M1 bar — needed by both bar-count tracking (smart cut)
   //   AND signal detection. Do this BEFORE returning to ManageOpenPosition.
   MqlRates r0[1];
   ArraySetAsSeries(r0, true);
   if(CopyRates(_Symbol, PERIOD_M1, 0, 1, r0) < 1) return;
   bool new_m1_bar = (r0[0].time != g_last_check_m1);
   if(new_m1_bar) {
      g_last_check_m1 = r0[0].time;
      // v3.42: bump bar count if we have an open position
      if(g_open_ticket != 0) g_open_bar_count++;
   }

   // Active exit management when position is open
   if(g_open_ticket != 0) {
      ManageOpenPosition();
      return;
   }

   // v3.42: detect on EVERY tick when no position open (was: only new M1 bar).
   //   The detector still reads bar shift 1 (the just-closed bar), so the
   //   *signal* only changes on new bars — but checking every tick means we
   //   fire immediately after exit instead of waiting up to 60s for the
   //   next bar close. Combined with removed UHV-dedup, this lets the EA
   //   rapid-fire on the same setup like Shano does.

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
      g_open_ticket  = pos_id;
      g_open_entry   = price;
      g_open_lots    = vol;
      g_open_side    = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(deal_ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? +1 : -1;
      g_open_time       = TimeCurrent();
      g_peak_pnl_usd    = 0;
      g_locked_pnl_usd  = 0;   // v3.42
      g_open_bar_count  = 0;   // v3.42
      g_entries_today++;
      Log("[FILLED] " + (g_open_side > 0 ? "BUY" : "SELL") +
          " ticket=" + IntegerToString((long)pos_id) +
          " @ " + DoubleToString(price, _Digits) +
          " lots=" + DoubleToString(vol, 2));
   }
}
