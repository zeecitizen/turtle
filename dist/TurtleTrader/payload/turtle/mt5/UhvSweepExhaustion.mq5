//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5  v3.50 — Shano probe-to-trade (verified)  |
//|                                                                  |
//| ENTRY: Zee's lesson-2 M1 UHV breakout (validated 20/20 Feb 11),  |
//| fired on EVERY breakout. But size is committed Shano's way:      |
//|                                                                  |
//| v3.48 → v3.49: the probe is a PATIENCE instrument, not a fast    |
//|   filter. Confirmed direct from Shano 2026-05-14:                |
//|                                                                  |
//|   PROBE (InpProbeLots 0.01) — fired on the breakout:             |
//|     • opens, usually goes red — HOLD through the drawdown        |
//|     • only floor: -InpProbeFloorUSD ($40) catastrophe cut        |
//|       (placed as a resting broker SL — no chase slippage)        |
//|     • recovery to +InpProbeConfirmUSD ($1) → fire the MAIN       |
//|                                                                  |
//|   MAIN (InpRealLots 0.40) — fired when the probe recovers:       |
//|     • rides drawdowns like Shano, but with a DEEP-but-BOUNDED    |
//|       catastrophe floor (InpMainFloorUSD) as a resting broker    |
//|       SL — Shano holds "forever" (unbounded); we bound it.       |
//|     • banks on roll-over: once peak >= InpMainBankUSD, a         |
//|       trailing broker SL locks (peak - InpMainDropUSD); when     |
//|       price rolls back off the peak the main closes in profit.   |
//|     • probe + main are one linked UNIT — closing the main also  |
//|       closes the probe.                                          |
//|                                                                  |
//| v3.50: REMOVED the daily-loss circuit breaker — it was halting   |
//| the EA and costing us trade data for analysis. The main-floor    |
//| (-$150) is the only bounded risk; per-trade safety lives there.  |
//|                                                                  |
//| Magic 88001 (production).                                        |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — lesson-2 + Shano probe-to-trade"
#property version   "3.50"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Entry: lesson-2 UHV breakout ──"
input int    InpMaxLookback        = 60;
input int    InpMaxBarsBack        = 60;
input int    InpMagicNumber        = 88001;
input int    InpMaxConcurrent      = 2;     // max concurrent UNITS (each unit = probe + optional main)
// (v3.50: InpMaxDailyLossUSD removed — was halting data collection)

input group "── Probe-to-trade (v3.49 — Shano's verified method) ──"
input double InpProbeLots          = 0.01;  // probe size — fired on every UHV breakout
input double InpProbeFloorUSD      = 40.0;  // probe CATASTROPHE cut — hold the drawdown until this; placed as a resting broker SL
input double InpProbeConfirmUSD    = 1.0;   // probe RECOVERY level — when probe P&L climbs back to +this, fire the main
input double InpRealLots           = 0.40;  // main size — fired when the probe recovers
input double InpMainBankUSD        = 8.0;   // main: once peak P&L hits this, the roll-over trail engages
input double InpMainDropUSD        = 3.0;   // main: roll-over trail locks (peak - this) — "reached a peak and is reversing"
input double InpMainFloorUSD       = 150.0; // main: DEEP but BOUNDED catastrophe floor (resting broker SL). Shano holds the main "forever" = unbounded risk; this caps it. Rides drawdowns down to here, then cuts. Tune empirically.
input double InpTrailUpdateStep    = 1.0;   // main: only re-modify the trailing SL when peak grew at least this much (rate-limit)

input group "── Safety ──"
input int    InpMaxHoldSec         = 0;     // optional hard time-stop on a UNIT (0 = disabled — Shano holds indefinitely)

input group "── Logging ──"
input bool   InpVerbose            = true;
input string InpLogPrefix          = "UhvL2";
input int    InpHeartbeatSec       = 5;
input string InpStateFile          = "uhv_sweep_state.json";

//── State ───────────────────────────────────────────────────────────
#define MAX_UNITS  8
#define ST_PROBING 0
#define ST_TRADING 1

struct TradeUnit {
   int      state;            // ST_PROBING / ST_TRADING
   int      side;             // +1 buy, -1 sell
   datetime uhv_time;
   // probe
   ulong    probe_ticket;     // 0 once the probe has been closed
   double   probe_entry;
   datetime probe_open_time;
   // main
   ulong    main_ticket;      // 0 until the probe confirms and the main fills
   double   main_entry;
   datetime main_open_time;
   double   main_peak_usd;
   double   main_locked_usd;
};

TradeUnit g_units[MAX_UNITS];
int       g_unit_count        = 0;

datetime g_last_fire_time     = 0;
datetime g_last_check_m1      = 0;
datetime g_last_heartbeat     = 0;
int      g_signals_today      = 0;
int      g_entries_today      = 0;
int      g_exits_today        = 0;
double   g_realized_today_usd = 0;
int      g_today_day          = 0;
double   g_contract_size      = 100.0;

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

void RemoveUnitAt(int idx) {
   if(idx < 0 || idx >= g_unit_count) return;
   for(int j = idx; j < g_unit_count - 1; j++) g_units[j] = g_units[j + 1];
   g_unit_count--;
}

// Resolve a CTrade market-order result into the opened POSITION id.
ulong LastOpenedPositionId() {
   ulong deal = g_trade.ResultDeal();
   if(deal != 0 && HistoryDealSelect(deal))
      return (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   // fallback: in hedge mode the opening order ticket == position ticket
   return g_trade.ResultOrder();
}

double PositionPnL(ulong tkt) {
   if(tkt == 0) return 0.0;
   if(!PositionSelectByTicket(tkt)) return 0.0;
   return PositionGetDouble(POSITION_PROFIT);
}

bool PositionAlive(ulong tkt) {
   return (tkt != 0 && PositionSelectByTicket(tkt));
}

//── Detection: returns +1 buy, -1 sell, 0 none (v3.43 relaxed) ──────
int DetectSignal(double &out_uhv_high, double &out_uhv_low,
                 datetime &out_uhv_time, long &out_uhv_vol) {
   int bars_needed = InpMaxLookback + 5;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int got = CopyRates(_Symbol, PERIOD_M1, 0, bars_needed, rates);
   if(got < bars_needed) return 0;

   MqlRates bo = rates[1];   // just-closed bar = breakout candle

   // ── BUY ──
   if(IsGreenBar(bo)) {
      int  uhv_idx = -1;
      long uhv_vol = -1;
      for(int j = 2; j <= InpMaxLookback + 1 && j < got; j++) {
         MqlRates c = rates[j];
         if(c.high >= bo.close) continue;          // skip overlap, keep walking (v3.43)
         if(IsRedBar(c) && (long)c.tick_volume > uhv_vol) {
            uhv_idx = j;
            uhv_vol = (long)c.tick_volume;
         }
      }
      if(uhv_idx < 0) return 0;
      MqlRates uhv = rates[uhv_idx];
      if((uhv_idx - 1) > InpMaxBarsBack) return 0;
      if(bo.close <= uhv.high) return 0;
      out_uhv_high = uhv.high; out_uhv_low = uhv.low;
      out_uhv_time = uhv.time; out_uhv_vol = uhv_vol;
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
      if((uhv_idx - 1) > InpMaxBarsBack) return 0;
      if(bo.close >= uhv.low) return 0;
      out_uhv_high = uhv.high; out_uhv_low = uhv.low;
      out_uhv_time = uhv.time; out_uhv_vol = uhv_vol;
      return -1;
   }

   return 0;
}

//── Open a PROBE on a UHV breakout → new PROBING unit ──────────────
void OpenProbe(int side, double uhv_high, double uhv_low, datetime uhv_time, long uhv_vol) {
   if(g_unit_count >= InpMaxConcurrent) return;
   datetime now_t = TimeCurrent();
   if(g_last_fire_time != 0 && (now_t - g_last_fire_time) < 2) return;   // rate-limit
   // v3.50: circuit breaker removed — keep collecting data.

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = (side > 0) ? ask : bid;

   // probe catastrophe floor as a RESTING broker SL — InpProbeFloorUSD worth of points
   double probe_ppp = InpProbeLots * g_contract_size;          // $/point for the probe
   double floor_pts = (probe_ppp > 0) ? (InpProbeFloorUSD / probe_ppp) : 40.0;
   double sl = (side > 0) ? entry - floor_pts : entry + floor_pts;
   sl = NormalizeDouble(sl, _Digits);

   RollDailyCountersIfNeeded();
   g_last_fire_time = now_t;   // reserve before the order so concurrent ticks rate-limit

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = (side > 0)
      ? g_trade.Buy (InpProbeLots, _Symbol, entry, sl, 0.0, InpLogPrefix + "_probe")
      : g_trade.Sell(InpProbeLots, _Symbol, entry, sl, 0.0, InpLogPrefix + "_probe");

   if(!ok) {
      Log("[ORDER_FAIL] probe retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment());
      return;
   }

   ulong pos_id = LastOpenedPositionId();
   g_signals_today++;
   g_entries_today++;

   g_units[g_unit_count].state           = ST_PROBING;
   g_units[g_unit_count].side            = side;
   g_units[g_unit_count].uhv_time        = uhv_time;
   g_units[g_unit_count].probe_ticket    = pos_id;
   g_units[g_unit_count].probe_entry     = g_trade.ResultPrice();
   g_units[g_unit_count].probe_open_time = now_t;
   g_units[g_unit_count].main_ticket     = 0;
   g_units[g_unit_count].main_entry      = 0;
   g_units[g_unit_count].main_open_time  = 0;
   g_units[g_unit_count].main_peak_usd   = 0;
   g_units[g_unit_count].main_locked_usd = 0;
   g_unit_count++;

   Log("[PROBE] " + (side > 0 ? "BUY" : "SELL") + " " + DoubleToString(InpProbeLots, 2) +
       " @ " + DoubleToString(g_trade.ResultPrice(), _Digits) +
       " tkt=" + IntegerToString((long)pos_id) +
       " floorSL=" + DoubleToString(sl, _Digits) + " (-$" + DoubleToString(InpProbeFloorUSD, 2) + ")" +
       " confirm@+$" + DoubleToString(InpProbeConfirmUSD, 2) +
       " UHV=" + TimeToString(uhv_time, TIME_DATE|TIME_MINUTES) +
       " vol=" + IntegerToString(uhv_vol) + " units=" + IntegerToString(g_unit_count));
}

//── Probe recovered → open the MAIN for this unit ──────────────────
void OpenMainForUnit(int ui) {
   int side = g_units[ui].side;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = (side > 0) ? ask : bid;

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   // Main opens with a DEEP catastrophe floor as a resting broker SL — it
   // rides drawdowns like Shano (lots of room) but the worst case is BOUNDED,
   // not infinite. The roll-over trail moves this SL UP once peak >= bank.
   double main_ppp  = InpRealLots * g_contract_size;
   double floor_pts = (main_ppp > 0) ? (InpMainFloorUSD / main_ppp) : 0.0;
   double main_sl   = (side > 0) ? entry - floor_pts : entry + floor_pts;
   main_sl = NormalizeDouble(main_sl, _Digits);

   bool ok = (side > 0)
      ? g_trade.Buy (InpRealLots, _Symbol, entry, main_sl, 0.0, InpLogPrefix + "_main")
      : g_trade.Sell(InpRealLots, _Symbol, entry, main_sl, 0.0, InpLogPrefix + "_main");

   if(!ok) {
      Log("[ORDER_FAIL] main retcode=" + IntegerToString(g_trade.ResultRetcode()) +
          " " + g_trade.ResultComment() + " — probe stays PROBING, will retry");
      return;   // unit stays PROBING; next tick (still >= confirm) retries
   }

   ulong pos_id = LastOpenedPositionId();
   g_entries_today++;
   g_units[ui].state          = ST_TRADING;
   g_units[ui].main_ticket    = pos_id;
   g_units[ui].main_entry     = g_trade.ResultPrice();
   g_units[ui].main_open_time = TimeCurrent();
   g_units[ui].main_peak_usd  = 0;
   g_units[ui].main_locked_usd = 0;

   Log("[PROBE_RECOVERED→MAIN] " + (side > 0 ? "BUY" : "SELL") + " " +
       DoubleToString(InpRealLots, 2) + " @ " + DoubleToString(g_trade.ResultPrice(), _Digits) +
       " tkt=" + IntegerToString((long)pos_id) +
       " floorSL=" + DoubleToString(main_sl, _Digits) + " (-$" + DoubleToString(InpMainFloorUSD, 2) + " bounded)" +
       " (probe tkt=" + IntegerToString((long)g_units[ui].probe_ticket) + " stays open, linked)");
}

//── Close a whole unit (probe + main if present) ───────────────────
void CloseUnit(int ui, string reason) {
   double probe_pnl = 0, main_pnl = 0;
   if(PositionAlive(g_units[ui].probe_ticket)) {
      probe_pnl = PositionGetDouble(POSITION_PROFIT);
      g_trade.PositionClose(g_units[ui].probe_ticket);
   }
   if(PositionAlive(g_units[ui].main_ticket)) {
      main_pnl = PositionGetDouble(POSITION_PROFIT);
      g_trade.PositionClose(g_units[ui].main_ticket);
   }
   g_exits_today++;
   Log("[UNIT_CLOSE " + reason + "] probe tkt=" + IntegerToString((long)g_units[ui].probe_ticket) +
       " ($" + DoubleToString(probe_pnl, 2) + ") main tkt=" +
       IntegerToString((long)g_units[ui].main_ticket) + " ($" + DoubleToString(main_pnl, 2) +
       ") total=$" + DoubleToString(probe_pnl + main_pnl, 2));
}

//── Manage ONE unit. Returns true if the unit is finished (prune it). ─
bool ManageUnit(int ui) {
   int side = g_units[ui].side;
   datetime now = TimeCurrent();

   // optional hard time-stop on the whole unit
   if(InpMaxHoldSec > 0 && (now - g_units[ui].probe_open_time) >= InpMaxHoldSec) {
      CloseUnit(ui, "time_stop");
      return true;
   }

   // ───────── PROBING ─────────
   if(g_units[ui].state == ST_PROBING) {
      if(!PositionAlive(g_units[ui].probe_ticket)) {
         // probe gone (its resting -$40 floor SL fired, or manual close)
         Log("[PROBE_FLOOR/closed] probe tkt=" + IntegerToString((long)g_units[ui].probe_ticket) +
             " — unit done");
         g_exits_today++;
         return true;
      }
      double probe_pnl = PositionGetDouble(POSITION_PROFIT);
      // RECOVERY → fire the main
      if(probe_pnl >= InpProbeConfirmUSD) {
         Log("[PROBE_CONFIRM] probe tkt=" + IntegerToString((long)g_units[ui].probe_ticket) +
             " recovered to $" + DoubleToString(probe_pnl, 2) +
             " (>= $" + DoubleToString(InpProbeConfirmUSD, 2) + ") — firing main");
         OpenMainForUnit(ui);
         return false;   // unit continues (now TRADING, or still PROBING if order failed)
      }
      // else: HOLD. The -$40 floor is the resting broker SL — no software cut.
      return false;
   }

   // ───────── TRADING ─────────
   // main gone? → close the probe too, unit done
   if(!PositionAlive(g_units[ui].main_ticket)) {
      Log("[MAIN_CLOSED] main tkt=" + IntegerToString((long)g_units[ui].main_ticket) +
          " gone (roll-over SL or manual) — closing linked probe");
      if(PositionAlive(g_units[ui].probe_ticket))
         g_trade.PositionClose(g_units[ui].probe_ticket);
      g_exits_today++;
      return true;
   }

   double main_pnl = PositionGetDouble(POSITION_PROFIT);
   if(main_pnl > g_units[ui].main_peak_usd) g_units[ui].main_peak_usd = main_pnl;

   // ROLL-OVER trail: once the main has peaked >= bank, lock (peak - drop) as a
   // resting broker SL. Price rolling back to it closes the main cleanly (no
   // chase slippage). Below the bank threshold the main rides on its DEEP
   // catastrophe floor SL (set at open) — bounded risk, not infinite.
   if(g_units[ui].main_peak_usd >= InpMainBankUSD) {
      double target_lock = g_units[ui].main_peak_usd - InpMainDropUSD;
      if(target_lock > g_units[ui].main_locked_usd + InpTrailUpdateStep - 1e-9) {
         double ppp = InpRealLots * g_contract_size;
         if(ppp > 0) {
            double lock_pts = target_lock / ppp;
            double new_sl = (side > 0) ? g_units[ui].main_entry + lock_pts
                                       : g_units[ui].main_entry - lock_pts;
            new_sl = NormalizeDouble(new_sl, _Digits);
            double cur_sl = PositionGetDouble(POSITION_SL);
            bool better = (side > 0 && (cur_sl == 0 || new_sl > cur_sl)) ||
                          (side < 0 && (cur_sl == 0 || new_sl < cur_sl));
            if(better) {
               if(g_trade.PositionModify(g_units[ui].main_ticket, new_sl, 0.0)) {
                  g_units[ui].main_locked_usd = target_lock;
                  Log("[ROLL_OVER_LOCK] main tkt=" + IntegerToString((long)g_units[ui].main_ticket) +
                      " peak=$" + DoubleToString(g_units[ui].main_peak_usd, 2) +
                      " locked=$" + DoubleToString(target_lock, 2) +
                      " sl=" + DoubleToString(new_sl, _Digits));
               } else {
                  // modify failed — if we've already rolled well past the lock, close now
                  if(main_pnl <= (g_units[ui].main_peak_usd - InpMainDropUSD * 3)) {
                     Log("[MAIN_EXIT fallback] modify failed, rolled over — closing unit");
                     CloseUnit(ui, "rollover_fallback");
                     return true;
                  }
               }
            }
         }
      }
   }
   return false;
}

//── Reconcile: a probe/main may close behind our back (SL fill). The
//   ManageUnit checks PositionAlive each tick, so this is just a safety
//   sweep for fully-orphaned units.
void ReconcileUnits() {
   for(int i = g_unit_count - 1; i >= 0; i--) {
      bool probe_alive = PositionAlive(g_units[i].probe_ticket);
      bool main_alive  = (g_units[i].main_ticket != 0) && PositionAlive(g_units[i].main_ticket);
      if(g_units[i].state == ST_PROBING && !probe_alive) {
         Log("[RECONCILE] PROBING unit orphaned (probe gone) — pruning");
         g_exits_today++;
         RemoveUnitAt(i);
      } else if(g_units[i].state == ST_TRADING && !main_alive) {
         if(probe_alive) {
            Log("[RECONCILE] TRADING unit — main gone, closing linked probe");
            g_trade.PositionClose(g_units[i].probe_ticket);
         }
         g_exits_today++;
         RemoveUnitAt(i);
      }
   }
}

//── Heartbeat ───────────────────────────────────────────────────────
void RefreshRealizedFromHistory() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime day_start = StructToTime(dt);
   if(!HistorySelect(day_start, TimeCurrent())) return;
   double total = 0;
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++) {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      total += HistoryDealGetDouble(d, DEAL_PROFIT);
      total += HistoryDealGetDouble(d, DEAL_SWAP);
      total += HistoryDealGetDouble(d, DEAL_COMMISSION);
   }
   g_realized_today_usd = total;
}

void WriteHeartbeat() {
   if((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   RollDailyCountersIfNeeded();
   RefreshRealizedFromHistory();

   int probing = 0, trading = 0;
   double open_pnl_total = 0;
   for(int i = 0; i < g_unit_count; i++) {
      if(g_units[i].state == ST_PROBING) probing++; else trading++;
      open_pnl_total += PositionPnL(g_units[i].probe_ticket);
      open_pnl_total += PositionPnL(g_units[i].main_ticket);
   }

   string json = "{";
   json += "\"ts\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"ea\":\"UhvSweepExhaustion v3.50\",";
   json += "\"alive\":true,";
   json += "\"bid\":" + DoubleToString(bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(ask, _Digits) + ",";
   json += "\"contract_size\":" + DoubleToString(g_contract_size, 2) + ",";
   json += "\"signals_today\":" + IntegerToString(g_signals_today) + ",";
   json += "\"entries_today\":" + IntegerToString(g_entries_today) + ",";
   json += "\"exits_today\":" + IntegerToString(g_exits_today) + ",";
   json += "\"realized_today_usd\":" + DoubleToString(g_realized_today_usd, 2) + ",";
   json += "\"max_daily_loss_usd\":0.00,";              // v3.50: breaker removed
   json += "\"circuit_breaker_tripped\":false,";
   json += "\"position_open\":" + (g_unit_count > 0 ? "true" : "false") + ",";
   json += "\"unit_count\":" + IntegerToString(g_unit_count) + ",";
   json += "\"probing\":" + IntegerToString(probing) + ",";
   json += "\"trading\":" + IntegerToString(trading) + ",";
   json += "\"open_pnl_total\":" + DoubleToString(open_pnl_total, 2) + ",";
   // legacy fields for dashboard compat — point at the newest unit's main, else probe
   if(g_unit_count > 0) {
      int idx = g_unit_count - 1;
      ulong show = (g_units[idx].main_ticket != 0) ? g_units[idx].main_ticket : g_units[idx].probe_ticket;
      json += "\"open_ticket\":" + IntegerToString((long)show) + ",";
      json += "\"open_side\":\"" + (g_units[idx].side > 0 ? "BUY" : "SELL") + "\",";
      json += "\"open_pnl\":" + DoubleToString(PositionPnL(show), 2) + ",";
   }
   json += "\"units\":[";
   for(int i = 0; i < g_unit_count; i++) {
      if(i > 0) json += ",";
      json += "{\"state\":\"" + (g_units[i].state == ST_PROBING ? "PROBING" : "TRADING") + "\"" +
              ",\"side\":\"" + (g_units[i].side > 0 ? "BUY" : "SELL") + "\"" +
              ",\"probe_ticket\":" + IntegerToString((long)g_units[i].probe_ticket) +
              ",\"probe_pnl\":" + DoubleToString(PositionPnL(g_units[i].probe_ticket), 2) +
              ",\"main_ticket\":" + IntegerToString((long)g_units[i].main_ticket) +
              ",\"main_pnl\":" + DoubleToString(PositionPnL(g_units[i].main_ticket), 2) +
              ",\"main_peak\":" + DoubleToString(g_units[i].main_peak_usd, 2) +
              ",\"main_locked\":" + DoubleToString(g_units[i].main_locked_usd, 2) + "}";
   }
   json += "],";
   json += "\"params\":{";
   json += "\"probe_lots\":" + DoubleToString(InpProbeLots, 2) + ",";
   json += "\"real_lots\":" + DoubleToString(InpRealLots, 2) + ",";
   json += "\"probe_floor_usd\":" + DoubleToString(InpProbeFloorUSD, 2) + ",";
   json += "\"probe_confirm_usd\":" + DoubleToString(InpProbeConfirmUSD, 2) + ",";
   json += "\"main_bank_usd\":" + DoubleToString(InpMainBankUSD, 2) + ",";
   json += "\"main_drop_usd\":" + DoubleToString(InpMainDropUSD, 2) + ",";
   json += "\"max_concurrent\":" + IntegerToString(InpMaxConcurrent);
   json += "}}";

   int h = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
   }
}

//── OnInit: rebind existing positions into units ───────────────────
int OnInit() {
   g_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(g_contract_size <= 0) g_contract_size = 100.0;
   int fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   Log("Init v3.50 (Shano probe-to-trade, breaker REMOVED: probe " + DoubleToString(InpProbeLots, 2) +
       " floor -$" + DoubleToString(InpProbeFloorUSD, 0) + " confirm +$" + DoubleToString(InpProbeConfirmUSD, 0) +
       " → main " + DoubleToString(InpRealLots, 2) + " rollover " + DoubleToString(InpMainBankUSD, 0) +
       "/" + DoubleToString(InpMainDropUSD, 0) +
       "; max " + IntegerToString(InpMaxConcurrent) + " units). Magic=" + IntegerToString(InpMagicNumber) +
       " Fill: FOK=" + (((fill & SYMBOL_FILLING_FOK) != 0)?"Y":"N") +
       " IOC=" + (((fill & SYMBOL_FILLING_IOC) != 0)?"Y":"N"));

   g_unit_count = 0;
   // collect our open positions
   ulong  probe_tkts[]; int  probe_side[]; double probe_ent[]; datetime probe_t[];
   ulong  main_tkts[];  int  main_side[];  double main_ent[];  datetime main_t[];  double main_pk[];
   double split = (InpProbeLots + InpRealLots) / 2.0;
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0 || !PositionSelectByTicket(tkt)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      double lots = PositionGetDouble(POSITION_VOLUME);
      int    side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      double ent  = PositionGetDouble(POSITION_PRICE_OPEN);
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(lots < split) {
         int n = ArraySize(probe_tkts);
         ArrayResize(probe_tkts, n+1); ArrayResize(probe_side, n+1);
         ArrayResize(probe_ent, n+1);  ArrayResize(probe_t, n+1);
         probe_tkts[n] = tkt; probe_side[n] = side; probe_ent[n] = ent; probe_t[n] = ot;
      } else {
         int n = ArraySize(main_tkts);
         ArrayResize(main_tkts, n+1); ArrayResize(main_side, n+1);
         ArrayResize(main_ent, n+1);  ArrayResize(main_t, n+1); ArrayResize(main_pk, n+1);
         main_tkts[n] = tkt; main_side[n] = side; main_ent[n] = ent; main_t[n] = ot;
         main_pk[n] = MathMax(0.0, PositionGetDouble(POSITION_PROFIT));
      }
   }
   // pair each main with a same-side probe → TRADING unit
   bool probe_used[]; ArrayResize(probe_used, ArraySize(probe_tkts));
   ArrayInitialize(probe_used, false);
   for(int m = 0; m < ArraySize(main_tkts) && g_unit_count < MAX_UNITS; m++) {
      int paired = -1;
      for(int p = 0; p < ArraySize(probe_tkts); p++) {
         if(!probe_used[p] && probe_side[p] == main_side[m]) { paired = p; break; }
      }
      g_units[g_unit_count].state          = ST_TRADING;
      g_units[g_unit_count].side           = main_side[m];
      g_units[g_unit_count].uhv_time       = 0;
      g_units[g_unit_count].main_ticket    = main_tkts[m];
      g_units[g_unit_count].main_entry     = main_ent[m];
      g_units[g_unit_count].main_open_time = main_t[m];
      g_units[g_unit_count].main_peak_usd  = main_pk[m];
      g_units[g_unit_count].main_locked_usd = 0;
      if(paired >= 0) {
         probe_used[paired] = true;
         g_units[g_unit_count].probe_ticket    = probe_tkts[paired];
         g_units[g_unit_count].probe_entry     = probe_ent[paired];
         g_units[g_unit_count].probe_open_time = probe_t[paired];
      } else {
         g_units[g_unit_count].probe_ticket    = 0;
         g_units[g_unit_count].probe_entry     = 0;
         g_units[g_unit_count].probe_open_time = 0;
      }
      Log("[REBIND] TRADING unit main=" + IntegerToString((long)main_tkts[m]) +
          " probe=" + IntegerToString((long)g_units[g_unit_count].probe_ticket));
      g_unit_count++;
   }
   // leftover probes → PROBING units
   for(int p = 0; p < ArraySize(probe_tkts) && g_unit_count < MAX_UNITS; p++) {
      if(probe_used[p]) continue;
      g_units[g_unit_count].state           = ST_PROBING;
      g_units[g_unit_count].side            = probe_side[p];
      g_units[g_unit_count].uhv_time        = 0;
      g_units[g_unit_count].probe_ticket    = probe_tkts[p];
      g_units[g_unit_count].probe_entry     = probe_ent[p];
      g_units[g_unit_count].probe_open_time = probe_t[p];
      g_units[g_unit_count].main_ticket     = 0;
      g_units[g_unit_count].main_entry      = 0;
      g_units[g_unit_count].main_open_time  = 0;
      g_units[g_unit_count].main_peak_usd   = 0;
      g_units[g_unit_count].main_locked_usd = 0;
      Log("[REBIND] PROBING unit probe=" + IntegerToString((long)probe_tkts[p]));
      g_unit_count++;
   }

   EventSetTimer(InpHeartbeatSec > 0 ? InpHeartbeatSec : 5);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   Log("Deinit reason=" + IntegerToString(reason));
}

void OnTimer() { WriteHeartbeat(); }

void OnTick() {
   ReconcileUnits();

   // manage every unit (back-to-front so pruning is safe)
   for(int i = g_unit_count - 1; i >= 0; i--) {
      if(ManageUnit(i)) RemoveUnitAt(i);
   }

   // detect + open a probe if a unit slot is free
   if(g_unit_count >= InpMaxConcurrent) return;
   double uhv_high, uhv_low; datetime uhv_time; long uhv_vol;
   int sig = DetectSignal(uhv_high, uhv_low, uhv_time, uhv_vol);
   if(sig != 0) OpenProbe(sig, uhv_high, uhv_low, uhv_time, uhv_vol);
}

//── OnTradeTransaction: realized-P&L is read from history each
//   heartbeat, so this is just a light log hook for closed deals.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req,
                        const MqlTradeResult &res) {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(trans.symbol != _Symbol) return;
   ulong d = trans.deal;
   if(d == 0 || !HistoryDealSelect(d)) return;
   if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicNumber) return;
   if((int)HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
      double net = HistoryDealGetDouble(d, DEAL_PROFIT) +
                   HistoryDealGetDouble(d, DEAL_SWAP) +
                   HistoryDealGetDouble(d, DEAL_COMMISSION);
      Log("[DEAL_OUT] pos=" + IntegerToString((long)HistoryDealGetInteger(d, DEAL_POSITION_ID)) +
          " net=$" + DoubleToString(net, 2));
   }
}
