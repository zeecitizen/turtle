//+------------------------------------------------------------------+
//| UhvSweepExhaustion.mq5                                            |
//|                                                                   |
//| Institutional-grade order flow exit EA.                           |
//|                                                                   |
//| ENTRY:  UHV-low-sweep-then-break (Zee's high-quality variant)    |
//|   - M5 FVG context (zone within last 30 M5 bars)                  |
//|   - M1 UHV red candle (vol >= 1.5x avg-20, body% >= 0.4)          |
//|   - Within 8 M1 bars, price wicks BELOW UHV low                   |
//|   - Within 5 more M1 bars, candle CLOSES ABOVE UHV high           |
//|   - Entry on close of break candle via OrderSendAsync             |
//|                                                                   |
//| EXIT:   3 microstructure modules                                  |
//|   1. CDepthOfMarket  — 3:1 imbalance = institutional resistance   |
//|   2. CTickVelocity   — circular buffer 20k ticks, velocity decay  |
//|   3. CMicrostructureTrail — ATR-based dynamic stop                |
//|       Tier 1 (+$2, 74%):  SL → break-even                        |
//|       Tier 2 (+$5, 53%):  trail = peak − 1.5×ATR                  |
//|       Exhaustion Choke:   tighten to 0.5×ATR on DOM/velocity exit |
//|                                                                   |
//| EXECUTION: OrderSendAsync + OnTradeTransaction (non-blocking)     |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — Mechanical Capture Deficit fix"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

//── User inputs ────────────────────────────────────────────────────
input group "── Entry: UHV-sweep-break ──"
input double InpLots               = 0.10;
input double InpUhvVolMultMin      = 1.5;     // UHV vol must be >= 1.5× 20-bar avg
input double InpUhvMinBodyPct      = 0.40;    // UHV body % of range
input int    InpFvgMaxAgeM5Bars    = 30;      // FVG must mitigate within 30 M5 bars
input double InpSweepMinPts        = 0.10;    // wick must penetrate prev low by this
input int    InpMaxBarsLookahead   = 8;       // sweep must occur within 8 M1 bars
input int    InpMaxBarsSweepBreak  = 5;       // break must occur within 5 bars after sweep
input int    InpMagicNumber        = 88001;

input group "── Path B: wick-CAB (climactic action bar) ──"
input bool   InpPathBEnabled       = true;    // enable wick-CAB pattern (no separate sweep bar)
input double InpPathBBodyMax       = 0.30;    // UHV body must be ≤ 30% of range (wicky)
input double InpPathBWickMinPts    = 1.50;    // UHV opposing wick ≥ 1.5pt (deep rejection)

input group "── Exit: DOM imbalance ──"
input double InpDomImbRatio        = 3.0;     // 3:1 ratio = exhaustion
input int    InpDomTopLevels       = 5;       // sum top N levels each side

input group "── Exit: tick velocity ──"
input int    InpVelocityWindow     = 100;     // rolling 100 ticks
input int    InpVelocityBaseline   = 500;     // 500-tick baseline
input double InpVelocityDecayStdev = 1.0;     // exit on >=1.0 stdev drop

input group "── Exit: ATR microstructure trail ──"
input int    InpAtrPeriod          = 14;
input ENUM_TIMEFRAMES InpAtrTimeframe = PERIOD_M1;
input double InpTier1USD           = 2.0;     // move SL to BE at +$2
input double InpTier2USD           = 5.0;     // start ATR trail at +$5
input double InpAtrTrailMult       = 1.5;
input double InpAtrChokeMult       = 0.5;     // tighten on exhaustion
input double InpHardSlUSD          = 15.0;    // catastrophic SL (always active)

input group "── Logging ──"
input bool   InpVerbose            = true;
input string InpLogPrefix          = "UhvSweep";
input int    InpHeartbeatSec       = 5;          // write state JSON every N seconds
input string InpStateFile          = "uhv_sweep_state.json"; // Common\Files

//══════════════════════════════════════════════════════════════════
//  CTickVelocity — circular buffer, buy/sell velocity in pts/sec
//══════════════════════════════════════════════════════════════════
#define VEL_BUF_SIZE 20000

class CTickVelocity {
private:
   struct STick {
      ulong  micros;
      double bid;
      double ask;
      int    dir; // +1 up-tick, -1 down-tick, 0 flat
   };
   STick m_buf[VEL_BUF_SIZE];
   int   m_head;
   int   m_count;
   double m_last_bid;

public:
   CTickVelocity() { m_head = 0; m_count = 0; m_last_bid = 0; }

   void Push(double bid, double ask) {
      int dir = 0;
      if(m_last_bid > 0) {
         if(bid > m_last_bid)      dir = 1;
         else if(bid < m_last_bid) dir = -1;
      }
      m_buf[m_head].micros = GetMicrosecondCount();
      m_buf[m_head].bid    = bid;
      m_buf[m_head].ask    = ask;
      m_buf[m_head].dir    = dir;
      m_head = (m_head + 1) % VEL_BUF_SIZE;
      if(m_count < VEL_BUF_SIZE) m_count++;
      m_last_bid = bid;
   }

   // Up-ticks per second over last N ticks
   // FIX #5 (code review): floor span at 1ms to prevent zero-division blindness
   //   when Windows GetMicrosecondCount() returns identical values across fast tick bursts.
   double BuyVelocity(int n) {
      if(m_count < n + 1) return 0;
      int up = 0;
      for(int i = 1; i <= n; i++) {
         int idx = (m_head - i + VEL_BUF_SIZE) % VEL_BUF_SIZE;
         if(m_buf[idx].dir > 0) up++;
      }
      int newest = (m_head - 1 + VEL_BUF_SIZE) % VEL_BUF_SIZE;
      int oldest = (m_head - n + VEL_BUF_SIZE) % VEL_BUF_SIZE;
      ulong span = m_buf[newest].micros - m_buf[oldest].micros;
      if(span < 15000) return 0; // FIX R2#3: Windows timer chunks at ~15.6ms — anything below = unreliable
      return (double)up / (span / 1000000.0);
   }

   double SellVelocity(int n) {
      if(m_count < n + 1) return 0;
      int down = 0;
      for(int i = 1; i <= n; i++) {
         int idx = (m_head - i + VEL_BUF_SIZE) % VEL_BUF_SIZE;
         if(m_buf[idx].dir < 0) down++;
      }
      int newest = (m_head - 1 + VEL_BUF_SIZE) % VEL_BUF_SIZE;
      int oldest = (m_head - n + VEL_BUF_SIZE) % VEL_BUF_SIZE;
      ulong span = m_buf[newest].micros - m_buf[oldest].micros;
      if(span < 15000) return 0; // FIX R2#3: Windows timer chunks at ~15.6ms
      return (double)down / (span / 1000000.0);
   }

   // Mean + std-dev of buy velocity over a longer baseline window (sampled)
   void BaselineStats(int n_baseline, int n_window, double &mean, double &stdev) {
      mean = 0; stdev = 0;
      if(m_count < n_baseline + n_window) return;
      // Sample 10 windows across the baseline
      double samples[10];
      for(int s = 0; s < 10; s++) {
         int start_offset = n_window + (s * (n_baseline - n_window) / 9);
         int up = 0;
         for(int i = 0; i < n_window; i++) {
            int idx = (m_head - start_offset - i + VEL_BUF_SIZE) % VEL_BUF_SIZE;
            if(m_buf[idx].dir > 0) up++;
         }
         int newest = (m_head - start_offset + VEL_BUF_SIZE) % VEL_BUF_SIZE;
         int oldest = (m_head - start_offset - n_window + 1 + VEL_BUF_SIZE) % VEL_BUF_SIZE;
         ulong span = m_buf[newest].micros - m_buf[oldest].micros;
         if(span < 15000) { samples[s] = 0; continue; } // FIX R2#3: skip unreliable
         samples[s] = (double)up / (span / 1000000.0);
      }
      double sum = 0;
      for(int i = 0; i < 10; i++) sum += samples[i];
      mean = sum / 10.0;
      double sq = 0;
      for(int i = 0; i < 10; i++) sq += MathPow(samples[i] - mean, 2);
      stdev = MathSqrt(sq / 10.0);
   }
};

//══════════════════════════════════════════════════════════════════
//  CDepthOfMarket — top-N imbalance ratio
//══════════════════════════════════════════════════════════════════
class CDepthOfMarket {
private:
   double m_bid_vol;
   double m_ask_vol;
   datetime m_last_update;

public:
   CDepthOfMarket() { m_bid_vol = 0; m_ask_vol = 0; m_last_update = 0; }

   // FIX #2 (code review): MarketBookGet returns array sorted HIGH→LOW price.
   //   Sells are at TOP (highest/worst asks), Bids at BOTTOM (lowest/best on top of buys).
   //   The institutional limits at the spread are AT THE TRANSITION POINT.
   //   Original code summed worst-OTM asks → blind to actual resistance.
   bool Refresh(int top_levels) {
      MqlBookInfo book[];
      if(!MarketBookGet(_Symbol, book)) return false;
      m_bid_vol = 0; m_ask_vol = 0;
      int sz = ArraySize(book);
      if(sz == 0) return false;
      // 1. Find the transition point (where sells end / buys begin)
      int best_bid_index = -1;
      for(int i = 0; i < sz; i++) {
         if(book[i].type == BOOK_TYPE_BUY) { best_bid_index = i; break; }
      }
      if(best_bid_index == -1) return false; // book malformed
      // 2. Sum top BIDS (best_bid downwards in array)
      int bid_end = MathMin(sz, best_bid_index + top_levels);
      for(int i = best_bid_index; i < bid_end; i++) {
         if(book[i].type == BOOK_TYPE_BUY) m_bid_vol += book[i].volume_real;
      }
      // 3. Sum top ASKS (best_ask upwards in array, i.e. best_bid_index - 1 walking UP toward 0)
      int ask_start = MathMax(0, best_bid_index - top_levels);
      for(int i = best_bid_index - 1; i >= ask_start; i--) {
         if(book[i].type == BOOK_TYPE_SELL) m_ask_vol += book[i].volume_real;
      }
      m_last_update = TimeCurrent();
      return true;
   }

   double BidVol() { return m_bid_vol; }
   double AskVol() { return m_ask_vol; }

   // For BUY position: heavy ASK volume = sellers stacked = exhaustion
   bool IsExhaustedForBuy(double threshold_ratio) {
      if(m_bid_vol <= 0) return false;
      return (m_ask_vol / m_bid_vol) >= threshold_ratio;
   }

   bool IsExhaustedForSell(double threshold_ratio) {
      if(m_ask_vol <= 0) return false;
      return (m_bid_vol / m_ask_vol) >= threshold_ratio;
   }
};

//══════════════════════════════════════════════════════════════════
//  CEntryDetector — UHV-low-sweep-then-break
//══════════════════════════════════════════════════════════════════
struct SFvgZone {
   datetime formed_time;
   double   hi;
   double   lo;
   int      side; // +1 buy, -1 sell
};

#define FVG_BUF_SIZE 200

class CEntryDetector {
private:
   SFvgZone m_fvgs[FVG_BUF_SIZE];
   int      m_fvg_head;   // FIX R2#6: circular buffer head
   int      m_fvg_count;  // total written (capped at FVG_BUF_SIZE)
   datetime m_last_check_m5;

   // FIX R2#6: O(1) circular insert instead of O(n) array shift.
   void AddFvg(datetime t, double hi, double lo, int side) {
      m_fvgs[m_fvg_head].formed_time = t;
      m_fvgs[m_fvg_head].hi          = hi;
      m_fvgs[m_fvg_head].lo          = lo;
      m_fvgs[m_fvg_head].side        = side;
      m_fvg_head = (m_fvg_head + 1) % FVG_BUF_SIZE;
      if(m_fvg_count < FVG_BUF_SIZE) m_fvg_count++;
   }

   double AvgVolM1FromRates(MqlRates &rates[], int from_shift, int lookback) {
      double sum = 0;
      int rates_n = ArraySize(rates);
      for(int i = from_shift + 1; i <= from_shift + lookback && i < rates_n; i++) {
         sum += (double)rates[i].tick_volume;
      }
      return sum / lookback;
   }

public:
   CEntryDetector() { m_fvg_head = 0; m_fvg_count = 0; m_last_check_m5 = 0; }

   // Call from OnTick — detects new M5 FVGs (CopyRates bulk fetch)
   void RefreshFvgs() {
      MqlRates m5r[];
      ArraySetAsSeries(m5r, true);
      if(CopyRates(_Symbol, PERIOD_M5, 0, 4, m5r) < 4) return;
      datetime cur_m5 = m5r[0].time;
      if(cur_m5 == m_last_check_m5) return;
      m_last_check_m5 = cur_m5;
      // 3-bar pattern at shifts (3, 2, 1): check bar 3 vs bar 1
      if(m5r[3].high < m5r[1].low)
         AddFvg(m5r[1].time, m5r[1].low, m5r[3].high, +1);  // buy FVG
      else if(m5r[3].low > m5r[1].high)
         AddFvg(m5r[1].time, m5r[3].low, m5r[1].high, -1); // sell FVG
   }

   // FIX R2#6: scan circular buffer from newest to oldest.
   bool InsideFvg(int side, double bar_low, double bar_high, int max_age_m5_bars) {
      datetime cutoff = TimeCurrent() - max_age_m5_bars * 5 * 60;
      for(int i = 0; i < m_fvg_count; i++) {
         int idx = (m_fvg_head - 1 - i + FVG_BUF_SIZE) % FVG_BUF_SIZE;
         if(m_fvgs[idx].formed_time < cutoff) continue; // skip stale (don't break — non-contiguous in ring)
         if(m_fvgs[idx].side != side) continue;
         if(bar_low <= m_fvgs[idx].hi && bar_high >= m_fvgs[idx].lo) return true;
      }
      return false;
   }

   // Detect UHV-low-sweep-then-break on JUST-CLOSED M1 bar (shift 1).
   // Uses CopyRates for bulk timeseries access (per code-review feedback).
   //
   // Two valid pattern paths:
   //   PATH A: separate sweep bar → UHV body% ≥ min_body_pct,
   //           separate sweep bar between UHV and break
   //   PATH B (NEW): wick-CAB / climactic bar → UHV body% ≤ pathB_body_max,
   //           UHV's OWN long opposing wick IS the sweep (no separate bar),
   //           break is the immediately-next bar
   int Detect(double &uhv_low, double &uhv_high, double vol_mult_min,
              double min_body_pct, int max_lookahead, int max_sweep_break,
              double sweep_min_pts, int max_age_m5_bars,
              bool pathB_enabled, double pathB_body_max, double pathB_wick_min_pts,
              int &out_path) {
      out_path = 0;
      int bars_needed = max_lookahead + max_sweep_break + 22;
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      int got = CopyRates(_Symbol, PERIOD_M1, 0, bars_needed, rates);
      if(got < bars_needed) return 0;

      double break_close = rates[1].close;

      // ── PATH B (wick-CAB): UHV is shift 2, break is shift 1 ──
      // Check FIRST because Path A could match a different UHV further back.
      if(pathB_enabled) {
         double uhv_h = rates[2].high;
         double uhv_l = rates[2].low;
         double uhv_o = rates[2].open;
         double uhv_c = rates[2].close;
         long   uhv_v = rates[2].tick_volume;
         double rng = uhv_h - uhv_l;
         if(rng > 0) {
            double body_pct = MathAbs(uhv_c - uhv_o) / rng;
            double avg_v = AvgVolM1FromRates(rates, 2, 20);
            if(body_pct <= pathB_body_max && avg_v > 0 && (double)uhv_v >= vol_mult_min * avg_v) {
               double body_lo = MathMin(uhv_o, uhv_c);
               double body_hi = MathMax(uhv_o, uhv_c);
               double lower_wick = body_lo - uhv_l;
               double upper_wick = uhv_h - body_hi;
               // BUY Path B: long lower wick on UHV + next-bar break above UHV high + inside buy FVG
               if(lower_wick >= pathB_wick_min_pts &&
                  InsideFvg(+1, uhv_l, uhv_h, max_age_m5_bars) &&
                  break_close > uhv_h) {
                  uhv_low = uhv_l; uhv_high = uhv_h; out_path = 2;
                  return +1;
               }
               // SELL Path B: long upper wick on UHV + next-bar break below UHV low + inside sell FVG
               if(upper_wick >= pathB_wick_min_pts &&
                  InsideFvg(-1, uhv_l, uhv_h, max_age_m5_bars) &&
                  break_close < uhv_l) {
                  uhv_low = uhv_l; uhv_high = uhv_h; out_path = 2;
                  return -1;
               }
            }
         }
      }

      // ── PATH A (separate sweep bar) ──
      for(int k = 2; k <= max_lookahead + max_sweep_break + 1; k++) {
         double uhv_h = rates[k].high;
         double uhv_l = rates[k].low;
         double uhv_o = rates[k].open;
         double uhv_c = rates[k].close;
         long   uhv_v = rates[k].tick_volume;
         double rng = uhv_h - uhv_l;
         if(rng <= 0) continue;
         double body_pct = MathAbs(uhv_c - uhv_o) / rng;
         if(body_pct < min_body_pct) continue;
         double avg_v = AvgVolM1FromRates(rates, k, 20);
         if(avg_v <= 0 || (double)uhv_v < vol_mult_min * avg_v) continue;

         if(uhv_c < uhv_o && InsideFvg(+1, uhv_l, uhv_h, max_age_m5_bars)) {
            bool sweep_found = false;
            for(int j = k-1; j >= 2; j--) {
               if(rates[j].low < uhv_l - sweep_min_pts) { sweep_found = true; break; }
            }
            if(!sweep_found) continue;
            if(break_close > uhv_h) {
               uhv_low = uhv_l; uhv_high = uhv_h; out_path = 1;
               return +1;
            }
         }
         if(uhv_c > uhv_o && InsideFvg(-1, uhv_l, uhv_h, max_age_m5_bars)) {
            bool sweep_found = false;
            for(int j = k-1; j >= 2; j--) {
               if(rates[j].high > uhv_h + sweep_min_pts) { sweep_found = true; break; }
            }
            if(!sweep_found) continue;
            if(break_close < uhv_l) {
               uhv_low = uhv_l; uhv_high = uhv_h; out_path = 1;
               return -1;
            }
         }
      }
      return 0;
   }
};

//══════════════════════════════════════════════════════════════════
//  CMicrostructureTrail — Tier1 BE + Tier2 ATR + Choke
//══════════════════════════════════════════════════════════════════
class CMicrostructureTrail {
private:
   double m_entry_price;
   int    m_side; // +1 buy, -1 sell
   double m_peak_price; // FIX R2#5: track absolute price level, not derived USD
   double m_lots;
   int    m_tier;  // 0=initial, 1=BE moved, 2=ATR trail active
   ulong  m_ticket;

public:
   CMicrostructureTrail() { Reset(); }

   void Reset() {
      m_entry_price = 0; m_side = 0; m_peak_price = 0;
      m_lots = 0; m_tier = 0; m_ticket = 0;
   }

   void OnEntry(ulong ticket, double entry_price, int side, double lots) {
      m_ticket = ticket; m_entry_price = entry_price;
      m_side = side; m_lots = lots;
      m_peak_price = entry_price; m_tier = 0;
   }

   bool IsActive() { return m_ticket != 0; }
   ulong Ticket() { return m_ticket; }
   int Tier() { return m_tier; }

   // FIX R2#2: Use the broker's native position-profit (handles cross-rate, swaps, commission).
   //   Fallback to manual calc only if PositionSelectByTicket fails.
   double CurrentPnlUsd(double bid, double ask) {
      if(m_ticket == 0) return 0;
      if(PositionSelectByTicket(m_ticket)) {
         return PositionGetDouble(POSITION_PROFIT);
      }
      double px = (m_side > 0) ? bid : ask;
      double pts = (m_side > 0) ? (px - m_entry_price) : (m_entry_price - px);
      return pts * g_contract_size * m_lots;
   }

   double PeakUsd() {
      // Derived from m_peak_price for dashboard reporting
      double pts = (m_side > 0) ? (m_peak_price - m_entry_price) : (m_entry_price - m_peak_price);
      return pts * g_contract_size * m_lots;
   }

   // FIX R2#5: Track absolute price level — no reverse-engineering from USD.
   void UpdatePeak(double bid, double ask) {
      if(m_side > 0 && bid > m_peak_price) m_peak_price = bid;
      else if(m_side < 0 && ask < m_peak_price) m_peak_price = ask;
   }

   // Returns desired SL price based on tier; 0 = no change
   double DesiredSl(double atr, double tier1_usd, double tier2_usd,
                    double atr_mult, bool choke_active, double choke_mult) {
      if(m_ticket == 0) return 0;
      double mult = choke_active ? choke_mult : atr_mult;
      double peak_pnl = PeakUsd();
      // Tier 1: at +tier1_usd, move to break-even
      if(m_tier == 0 && peak_pnl >= tier1_usd) {
         m_tier = 1;
         return m_entry_price;
      }
      // Tier 2: at +tier2_usd, activate ATR trail (clean: peak_price directly)
      if(peak_pnl >= tier2_usd) {
         m_tier = 2;
         if(m_side > 0) return m_peak_price - mult * atr;
         else            return m_peak_price + mult * atr;
      }
      return 0;
   }
};

//══════════════════════════════════════════════════════════════════
//  CAsyncExecution — OrderSendAsync + OnTradeTransaction
//══════════════════════════════════════════════════════════════════
class CAsyncExecution {
private:
   ulong m_pending_request_id;
   ulong m_pending_modify_id;     // separate channel for SL modifies
   ulong m_open_ticket;
   double m_open_price;
   double m_last_modified_sl;     // dedupe: don't resend identical SL
   int    m_pending_side; // +1 buy entry, -1 sell entry, +2 close

public:
   CAsyncExecution() { m_magic_filter = 0; Reset(); }

   void Reset() {
      m_pending_request_id = 0;
      m_pending_modify_id  = 0;
      m_open_ticket = 0;
      m_open_price = 0;
      m_last_modified_sl = 0;
      m_pending_side = 0;
      // m_magic_filter is configuration (set once in OnInit), not reset on close
   }

   bool HasPendingModify() { return m_pending_modify_id != 0; }

   bool HasOpenPosition() { return m_open_ticket != 0; }
   ulong OpenTicket() { return m_open_ticket; }
   double OpenPrice() { return m_open_price; }

   // FIX R2#1 (Amnesia): rebind state from existing position on restart
   void RebindOpen(ulong ticket, double entry_price) {
      m_open_ticket = ticket;
      m_open_price  = entry_price;
   }

   // FIX #3 (code review): Blueberry/many CFD brokers disable FOK on XAUUSD.
   //   Hardcoded FOK = instant Error 10030 ("Unsupported filling mode") rejection.
   //   Detect what broker allows and pick the best one available.
   ENUM_ORDER_TYPE_FILLING GetAllowedFillingMode() {
      int filling = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
      if((filling & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
      if((filling & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
      return ORDER_FILLING_RETURN;
   }

   // FIX R2#7: magic comes from stored m_magic_filter (no caller-passing).
   bool FireEntry(int side, double lots, double sl_price, string comment) {
      if(m_open_ticket != 0 || m_pending_request_id != 0) return false;
      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action       = TRADE_ACTION_DEAL;
      req.symbol       = _Symbol;
      req.volume       = lots;
      req.type         = (side > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      req.price        = (side > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                    : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      req.sl           = sl_price;
      req.deviation    = 20;
      req.magic        = m_magic_filter;
      req.type_filling = GetAllowedFillingMode();
      req.comment      = comment;
      if(!OrderSendAsync(req, res)) {
         Print("[ASYNC ENTRY FAIL] retcode=", res.retcode);
         return false;
      }
      m_pending_request_id = res.request_id;
      m_pending_side = side;
      return true;
   }

   bool FireClose(ulong ticket, int side) {
      if(ticket == 0) return false;
      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action       = TRADE_ACTION_DEAL;
      req.position     = ticket;
      req.symbol       = _Symbol;
      req.volume       = PositionGetDouble(POSITION_VOLUME);
      req.type         = (side > 0) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY; // opposite to close
      req.price        = (side > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                    : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      req.deviation    = 50;
      req.magic        = m_magic_filter;  // BUG FIX: close DEAL_ADD must carry magic
      req.type_filling = GetAllowedFillingMode();
      req.comment      = "exhaust_close";
      if(!OrderSendAsync(req, res)) {
         Print("[ASYNC CLOSE FAIL] retcode=", res.retcode);
         return false;
      }
      m_pending_request_id = res.request_id;
      m_pending_side = +2; // close marker
      return true;
   }

   bool ModifySl(ulong ticket, double new_sl) {
      // Guard against duplicate modifies — state machine lock
      if(m_pending_modify_id != 0) return false;  // wait for prior to confirm
      if(MathAbs(new_sl - m_last_modified_sl) < _Point) return false;  // no-op
      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action   = TRADE_ACTION_SLTP;
      req.position = ticket;
      req.symbol   = _Symbol;
      req.sl       = new_sl;
      req.tp       = PositionGetDouble(POSITION_TP);
      if(!OrderSendAsync(req, res)) return false;
      m_pending_modify_id = res.request_id;
      return true;
   }

   // FIX #1 (code review — FATAL): Decouple request ack from deal fill.
   //   In MQL5, result.request_id is ONLY populated for TRADE_TRANSACTION_REQUEST.
   //   On TRADE_TRANSACTION_DEAL_ADD, result.request_id == 0, so original code
   //   would NEVER match the fill → m_open_ticket stayed 0 → trail/exit dead.
   void OnTransaction(const MqlTradeTransaction &trans,
                      const MqlTradeRequest &request,
                      const MqlTradeResult &result) {
      // 1. REQUEST event: server acknowledged our async send. Clear pending IDs.
      if(trans.type == TRADE_TRANSACTION_REQUEST) {
         if(result.request_id != 0 && result.request_id == m_pending_request_id) {
            m_pending_request_id = 0; // entry/close request acknowledged
         }
         if(result.request_id != 0 && result.request_id == m_pending_modify_id) {
            m_last_modified_sl = request.sl;
            m_pending_modify_id = 0;
            Print("[MODIFY ACK] new_sl=", request.sl);
         }
         return;
      }
      // 2. DEAL_ADD: deal landed in history. Capture ticket but DO NOT select position yet.
      //    FIX R2#4: PositionSelectByTicket can race ahead of position registration.
      //    We only stash IDs here; the actual bind happens in TRADE_TRANSACTION_POSITION below.
      if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
         if(!HistoryDealSelect(trans.deal)) return;
         long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
         bool is_ours = (magic == m_magic_filter) ||
                        (m_open_ticket != 0 && trans.position == m_open_ticket);
         if(!is_ours) return;
         long deal_entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
         if(deal_entry == DEAL_ENTRY_IN) {
            m_open_ticket = trans.position;
            m_open_price  = trans.price;
            Print("[ENTRY DEAL] ticket=", m_open_ticket, " px=", m_open_price,
                  " — awaiting TRADE_TRANSACTION_POSITION for bind");
         } else if(deal_entry == DEAL_ENTRY_OUT) {
            Print("[CLOSE FILLED] ticket=", trans.position, " exit_px=", trans.price);
            Reset();
         }
         return;
      }
      // 3. POSITION event: position is now confirmed registered. Safe to bind.
      if(trans.type == TRADE_TRANSACTION_POSITION) {
         if(m_open_ticket != 0 && trans.position == m_open_ticket) {
            Print("[POSITION CONFIRMED] ticket=", m_open_ticket);
         }
      }
   }

   void SetMagicFilter(long m) { m_magic_filter = m; }
private:
   long m_magic_filter;  // initialized via SetMagicFilter() in OnInit
};

//══════════════════════════════════════════════════════════════════
//  GLOBALS + EVENT HANDLERS
//══════════════════════════════════════════════════════════════════
CTickVelocity        g_velocity;
CDepthOfMarket       g_dom;
CEntryDetector       g_entry;
CMicrostructureTrail g_trail;
CAsyncExecution      g_exec;
int                  g_atr_handle = INVALID_HANDLE;
double               g_contract_size = 100.0;  // cached at OnInit from broker
datetime             g_last_heartbeat = 0;
int                  g_signals_today = 0;
int                  g_entries_today = 0;
int                  g_exits_today = 0;
double               g_realized_today_usd = 0;
datetime             g_today_date = 0;

void Log(string msg) {
   if(InpVerbose) Print(InpLogPrefix, " ", msg);
}

//──────────────────────────────────────────────────────────────────
//  WriteHeartbeat — dashboard integration
//  Writes uhv_sweep_state.json to MT5 Common\Files\
//──────────────────────────────────────────────────────────────────
void WriteHeartbeat() {
   if((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   // Reset daily counters on date change
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));
   if(today != g_today_date) {
      g_today_date = today;
      g_signals_today = 0;
      g_entries_today = 0;
      g_exits_today = 0;
      g_realized_today_usd = 0;
   }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double cur_pnl = g_trail.CurrentPnlUsd(bid, ask);
   string json = "{";
   json += "\"ts\":" + IntegerToString((long)TimeCurrent()) + ",";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"ea\":\"UhvSweepExhaustion v1.00\",";
   json += "\"alive\":true,";
   json += "\"bid\":" + DoubleToString(bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(ask, _Digits) + ",";
   json += "\"contract_size\":" + DoubleToString(g_contract_size, 2) + ",";
   json += "\"signals_today\":" + IntegerToString(g_signals_today) + ",";
   json += "\"entries_today\":" + IntegerToString(g_entries_today) + ",";
   json += "\"exits_today\":" + IntegerToString(g_exits_today) + ",";
   json += "\"realized_today_usd\":" + DoubleToString(g_realized_today_usd, 2) + ",";
   json += "\"position_open\":" + (g_exec.HasOpenPosition() ? "true" : "false") + ",";
   if(g_exec.HasOpenPosition()) {
      json += "\"ticket\":" + IntegerToString((long)g_exec.OpenTicket()) + ",";
      json += "\"entry_price\":" + DoubleToString(g_exec.OpenPrice(), _Digits) + ",";
      json += "\"cur_pnl_usd\":" + DoubleToString(cur_pnl, 2) + ",";
      json += "\"peak_pnl_usd\":" + DoubleToString(g_trail.PeakUsd(), 2) + ",";
      json += "\"tier\":" + IntegerToString(g_trail.Tier()) + ",";
   }
   json += "\"params\":{";
   json += "\"lots\":" + DoubleToString(InpLots, 2) + ",";
   json += "\"tier1_usd\":" + DoubleToString(InpTier1USD, 2) + ",";
   json += "\"tier2_usd\":" + DoubleToString(InpTier2USD, 2) + ",";
   json += "\"hard_sl_usd\":" + DoubleToString(InpHardSlUSD, 2) + ",";
   json += "\"dom_ratio\":" + DoubleToString(InpDomImbRatio, 2);
   json += "}";
   json += "}";
   int h = FileOpen(InpStateFile, FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
   }
}

//+------------------------------------------------------------------+
int OnInit() {
   bool dom_ok = MarketBookAdd(_Symbol);
   if(!dom_ok) {
      Print("[WARN] MarketBookAdd failed — broker may not provide L2 data. Falling back to velocity-only exit logic.");
   } else {
      // L2 verification: try to retrieve book once and check we got real levels
      Sleep(500); // give broker a moment to push first snapshot
      MqlBookInfo book[];
      if(MarketBookGet(_Symbol, book) && ArraySize(book) > 0) {
         int bid_lvls = 0, ask_lvls = 0; double sample_vol = 0;
         for(int i = 0; i < ArraySize(book); i++) {
            if(book[i].type == BOOK_TYPE_BUY)  bid_lvls++;
            if(book[i].type == BOOK_TYPE_SELL) ask_lvls++;
            sample_vol += book[i].volume_real;
         }
         Log("L2 VERIFY: " + IntegerToString(bid_lvls) + " bid lvls, " +
             IntegerToString(ask_lvls) + " ask lvls, sample_vol=" +
             DoubleToString(sample_vol, 2));
         if(bid_lvls < 2 || ask_lvls < 2) {
            Print("[WARN] L2 data thin (<2 levels each side). Broker may be synthesizing DOM. Order flow exhaustion path will be unreliable — consider true ECN broker.");
         }
      } else {
         Print("[WARN] MarketBookGet returned no data after subscribe. DOM analytics will be unavailable.");
      }
   }
   g_atr_handle = iATR(_Symbol, InpAtrTimeframe, InpAtrPeriod);
   if(g_atr_handle == INVALID_HANDLE) {
      Print("[FATAL] iATR handle creation failed");
      return INIT_FAILED;
   }
   // Cache contract size from broker (fixes hardcoded 100.0 assumption)
   g_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(g_contract_size <= 0) {
      Print("[WARN] SymbolInfoDouble returned ", g_contract_size, " for contract size — defaulting to 100");
      g_contract_size = 100.0;
   }
   // Set magic-number filter for OnTradeTransaction deal identification (Fix #1)
   g_exec.SetMagicFilter(InpMagicNumber);
   // Log allowed filling mode for diagnostic
   int fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   Log("Filling mode bits: " + IntegerToString(fill) +
       " (FOK=" + ((fill & SYMBOL_FILLING_FOK)?"Y":"N") +
       " IOC=" + ((fill & SYMBOL_FILLING_IOC)?"Y":"N") + ")");
   Log("Init done. RING_SIZE=" + IntegerToString(VEL_BUF_SIZE) +
       " ATR=" + IntegerToString(InpAtrPeriod) +
       " ContractSize=" + DoubleToString(g_contract_size, 2) +
       " DOM=" + (dom_ok ? "ON" : "FALLBACK"));

   // FIX R2#1 (Amnesia): scan PositionsTotal for existing position we own.
   //   On restart/recompile/input-change, recover ticket + entry + lots + side.
   //   Reconstructs trail state so the position keeps being managed.
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0) continue;
      if(!PositionSelectByTicket(tkt)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      // Found our position — rebind
      double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      double lots   = PositionGetDouble(POSITION_VOLUME);
      int    side   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      // Reconstruct internal state by forcing the exec's open_ticket
      // (FireEntry won't fire because we're populating directly)
      g_exec.RebindOpen(tkt, entry);
      g_trail.OnEntry(tkt, entry, side, lots);
      // Restore peak: bias toward current price so trail doesn't reset to 0
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_trail.UpdatePeak(bid, ask);
      Log("[REBIND] Resumed existing position: ticket=" + IntegerToString((long)tkt) +
          " entry=" + DoubleToString(entry, _Digits) +
          " side=" + (side > 0 ? "BUY" : "SELL") +
          " lots=" + DoubleToString(lots, 2));
      break;
   }

   // FIX (2026-05-12): heartbeat was tick-driven from OnTick, so XAUUSD's daily
   // settlement break (~22:00-23:00 broker time) froze heartbeats and tripped the
   // watchdog with a false positive. Drive heartbeat from OnTimer so it fires
   // every InpHeartbeatSec regardless of tick flow.
   EventSetTimer(InpHeartbeatSec > 0 ? InpHeartbeatSec : 5);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   EventKillTimer();
   MarketBookRelease(_Symbol);
   if(g_atr_handle != INVALID_HANDLE) IndicatorRelease(g_atr_handle);
   Log("Deinit reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//  OnTimer — tick-independent heartbeat so the watchdog doesn't false-alarm
//  during XAUUSD daily breaks or any quiet market period.
//+------------------------------------------------------------------+
void OnTimer() {
   WriteHeartbeat();
}

//+------------------------------------------------------------------+
// FIX #4 (code review): Extract exit evaluation so DOM-only events
//   (which don't generate ticks) can also fire exhaustion exits immediately.
//   Without this, a massive Ask wall appearing without a price move = silent miss.
void EvaluateExits(double bid, double ask) {
   if(!g_exec.HasOpenPosition() || !g_trail.IsActive()) return;
   if(!PositionSelectByTicket(g_trail.Ticket())) {
      g_trail.Reset();
      g_exec.Reset();
      return;
   }
   g_trail.UpdatePeak(bid, ask);
   double pnl = g_trail.CurrentPnlUsd(bid, ask);

   // Catastrophic SL
   if(pnl <= -InpHardSlUSD) {
      g_exec.FireClose(g_trail.Ticket(),
         (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1);
      Log("[HARD SL] pnl=" + DoubleToString(pnl, 2));
      return;
   }

   // ATR for trail
   double atr_buf[1];
   if(CopyBuffer(g_atr_handle, 0, 0, 1, atr_buf) <= 0) return;
   double atr = atr_buf[0];

   bool is_buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   bool dom_exhaust = is_buy ? g_dom.IsExhaustedForBuy(InpDomImbRatio)
                              : g_dom.IsExhaustedForSell(InpDomImbRatio);
   double cur_vel = is_buy ? g_velocity.BuyVelocity(InpVelocityWindow)
                            : g_velocity.SellVelocity(InpVelocityWindow);
   double vel_mean, vel_stdev;
   g_velocity.BaselineStats(InpVelocityBaseline, InpVelocityWindow, vel_mean, vel_stdev);
   bool vel_decay = (vel_stdev > 0 && (vel_mean - cur_vel) >= InpVelocityDecayStdev * vel_stdev);

   bool choke = (dom_exhaust || vel_decay) && pnl > 0;

   // Tier rules
   double new_sl = g_trail.DesiredSl(atr, InpTier1USD, InpTier2USD,
                                      InpAtrTrailMult, choke, InpAtrChokeMult);
   if(new_sl > 0) {
      double cur_sl = PositionGetDouble(POSITION_SL);
      bool needs_update = false;
      if(is_buy && new_sl > cur_sl) needs_update = true;
      if(!is_buy && (cur_sl == 0 || new_sl < cur_sl)) needs_update = true;
      if(needs_update && !g_exec.HasPendingModify()) {
         if(g_exec.ModifySl(g_trail.Ticket(), new_sl)) {
            Log("[TRAIL] tier=" + IntegerToString(g_trail.Tier()) + " sl=" +
                DoubleToString(new_sl, _Digits) + " pnl=" + DoubleToString(pnl, 2) +
                (choke ? " CHOKE" : ""));
         }
      }
   }

   // Exhaustion exit at market
   if(choke && pnl < g_trail.PeakUsd() - 1.0 && g_trail.Tier() >= 1) {
      g_exec.FireClose(g_trail.Ticket(), is_buy ? +1 : -1);
      Log("[EXHAUST EXIT] peak=" + DoubleToString(g_trail.PeakUsd(), 2) +
          " cur=" + DoubleToString(pnl, 2));
   }
}

//+------------------------------------------------------------------+
void OnBookEvent(const string &symbol) {
   if(symbol != _Symbol) return;
   g_dom.Refresh(InpDomTopLevels);
   // FIX #4: Evaluate exits IMMEDIATELY on DOM shift — don't wait for next tick.
   //   This is the microsecond-edge moment for catching institutional resistance.
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   EvaluateExits(bid, ask);
}

//+------------------------------------------------------------------+
void OnTick() {
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   g_velocity.Push(t.bid, t.ask);
   g_entry.RefreshFvgs();
   WriteHeartbeat();

   // Tick fallback bind: if DEAL_ADD set the open_ticket but PositionSelectByTicket
   // failed there (rare race), retry every tick until the position is selectable.
   if(g_exec.HasOpenPosition() && g_trail.Ticket() == 0) {
      if(PositionSelectByTicket(g_exec.OpenTicket())) {
         int side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
         double lots = PositionGetDouble(POSITION_VOLUME);
         g_trail.OnEntry(g_exec.OpenTicket(), g_exec.OpenPrice(), side, lots);
         Log("[TRAIL BIND] (OnTick fallback) ticket=" + IntegerToString(g_exec.OpenTicket()) +
             " entry=" + DoubleToString(g_exec.OpenPrice(), _Digits) +
             " lots=" + DoubleToString(lots, 2));
      }
   }

   // Evaluate exits on every tick (DOM path handles between-tick events)
   EvaluateExits(t.bid, t.ask);

   // ── ENTRY logic (only if no position) ──
   if(!g_exec.HasOpenPosition()) {
      // Only detect on M1 bar close
      static datetime last_m1 = 0;
      datetime cur_m1 = iTime(_Symbol, PERIOD_M1, 0);
      if(cur_m1 == last_m1) return;
      last_m1 = cur_m1;

      double uhv_low = 0, uhv_high = 0;
      int path_used = 0;
      int signal = g_entry.Detect(uhv_low, uhv_high,
                                   InpUhvVolMultMin, InpUhvMinBodyPct,
                                   InpMaxBarsLookahead, InpMaxBarsSweepBreak,
                                   InpSweepMinPts, InpFvgMaxAgeM5Bars,
                                   InpPathBEnabled, InpPathBBodyMax, InpPathBWickMinPts,
                                   path_used);
      if(signal == 0) return;

      // SL = UHV low (for buy) / UHV high (for sell), with hard cap
      double sl_price;
      double max_sl_dist = InpHardSlUSD / (g_contract_size * InpLots);
      if(signal > 0) {
         sl_price = uhv_low - 0.20; // small buffer
         double cur_ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(cur_ask - sl_price > max_sl_dist) sl_price = cur_ask - max_sl_dist;
      } else {
         sl_price = uhv_high + 0.20;
         double cur_bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(sl_price - cur_bid > max_sl_dist) sl_price = cur_bid + max_sl_dist;
      }

      Log("[SIGNAL] side=" + (signal > 0 ? "BUY" : "SELL") +
          " path=" + (path_used == 2 ? "B(wick-CAB)" : "A(sweep-bar)") +
          " uhv_lo=" + DoubleToString(uhv_low, _Digits) +
          " uhv_hi=" + DoubleToString(uhv_high, _Digits) +
          " sl=" + DoubleToString(sl_price, _Digits));
      g_signals_today++;

      if(g_exec.FireEntry(signal, InpLots, sl_price, "UhvSweep")) {
         g_entries_today++;
         // Optimistic: assume fill at current ask/bid, refined in OnTradeTransaction
         double entry_estimate = (signal > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                              : SymbolInfoDouble(_Symbol, SYMBOL_BID);
         // We'll bind ticket in OnTradeTransaction; for now seed trail with estimate
         g_trail.OnEntry(0, entry_estimate, signal, InpLots);
      }
   }
}

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result) {
   g_exec.OnTransaction(trans, request, result);
   // EMPIRICAL FIX (2026-05-12, smoke-tested on Blueberry):
   //   Blueberry MT5 does NOT fire TRADE_TRANSACTION_POSITION on position open
   //   — only DEAL_ADD with the position field set. So binding at DEAL_ADD
   //   is required. PositionSelectByTicket is reliable at that point on this broker.
   //   The OnTick safety net catches any race-condition case where the position
   //   isn't yet selectable on DEAL_ADD.
   if((trans.type == TRADE_TRANSACTION_DEAL_ADD || trans.type == TRADE_TRANSACTION_POSITION) &&
      g_exec.HasOpenPosition() && g_trail.Ticket() == 0) {
      if(PositionSelectByTicket(g_exec.OpenTicket())) {
         int side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
         double lots = PositionGetDouble(POSITION_VOLUME);
         double actual_entry = g_exec.OpenPrice();
         g_trail.OnEntry(g_exec.OpenTicket(), actual_entry, side, lots);
         Log("[TRAIL BIND] ticket=" + IntegerToString(g_exec.OpenTicket()) +
             " entry=" + DoubleToString(actual_entry, _Digits) +
             " lots=" + DoubleToString(lots, 2) +
             " via=" + (trans.type == TRADE_TRANSACTION_DEAL_ADD ? "DEAL_ADD" : "POSITION"));
      }
   }
}
//+------------------------------------------------------------------+
