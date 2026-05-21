//+------------------------------------------------------------------+
//| NsndTrader.mq5 — VSA No Supply / No Demand executor              |
//|                                                                  |
//| Backtest 12 days real ticks XAU @ 0.10 lots:                     |
//|   95 trades, 51% WR, avg win $26.8 / avg loss $7.5 (R:R 3.5:1)  |
//|   Total +$935 / 12 days  (~$78/day @ 0.10 lots)                  |
//|   Projection @ 0.40 lots: +$3,741 / 12 days ≈ $312/day           |
//|   Designed for COMBINED use with S3Trader (different magics).    |
//|                                                                  |
//| STRATEGY (BUY-only when NS, SELL-only when ND):                  |
//|   1. M1 intraday trend filter (close[1] - close[60] vs threshold)|
//|        uptrend  → BUY setups only                                |
//|        downtrend→ SELL setups only                               |
//|   2. NS candidate (BUY): red M1 candle with                      |
//|        • dead volume (lower than at least 2 of prev 4 bars)      |
//|        • small range (< avg range of prev 5 bars)                |
//|        • Some unfilled bullish FVG (M15 or H1) overlaps the      |
//|          NS bar's range                                          |
//|   3. ND candidate (SELL): symmetric — green candle, bearish FVG  |
//|   4. Prior UHV (big opposite-color volume bar) within 20 bars    |
//|      before the NS/ND                                            |
//|   5. Entry trigger: current bar SWEEPS the NS/ND's low (buy)     |
//|      or high (sell)                                              |
//|   6. SL: sweep-bar's extreme + 1 pip buffer                      |
//|   7. TP: fixed $12 distance at 0.10 lots (1.2 price units);      |
//|      scales with lots — actual TP_distance = InpTPUsd / (lots×100)|
//|                                                                  |
//| Magic 88006 (distinct from S3=88003 / BTC=88005).                |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — NS/ND VSA"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.03;  // 2026-05-21: FTMO $10k challenge, 3x EV-weighted (S3 0.09/S1 0.06/NSND 0.03). NSND underweighted (most volatile). Was 0.01 on the $500 Blueberry acct.
input int    InpMagicNumber   = 88006;

input group "── Detection ──"
input int    InpNsLookback        = 15;    // M1 bars searched for NS/ND
input int    InpVolCompareN       = 4;     // NS vol < at least this many of prev N
input int    InpVolCompareMin     = 3;     // BUGFIX 2026-05-17: was 2; clock-aligned sweep best at 3
input double InpNarrowRangeFrac   = 1.0;   // NS range < this × avg-prev-5
input int    InpUhvLookback       = 20;    // bars before NS that must have a UHV
input double InpUhvVolMult        = 1.30;  // UHV vol > this × avg-20
input int    InpTrendLookback     = 60;    // M1 bars for trend (~1 hour)
input double InpTrendThreshold    = 2.0;   // BUGFIX 2026-05-17: was 1.0; clock-aligned sweep best at 2.0 (filters more noise)

input group "── FVG context ──"
input int    InpFvgLookbackM15    = 30;    // M15 bars searched for FVG
input int    InpFvgLookbackH1     = 30;    // H1 bars searched for FVG (only if InpUseH1Fvg)
input bool   InpUseH1Fvg          = false; // 2026-05-20 walk-forward: M15-only beats M15+H1 (H1 adds low-quality trades). Set true to restore old M15-or-H1 behaviour.

input group "── HH/HL trend confirmation (Dow Theory) ──"
// BUGFIX 2026-05-17: defaulted to OFF. HH/HL filter worked with stride-based
// FVG aggregation but HURTS with MT5's native clock-aligned bars (which the EA
// actually uses). Clock-aligned sweep: HH/HL=False → +$416/12d (best);
// HH/HL=True → -$15/12d.
input bool   InpUseHHHL           = false; // was true; toggle ON only if backtested for your setup
input int    InpHHHLSwingN        = 3;     // bars on each side for swing detection
input int    InpHHHLLookback      = 180;   // M1 bars to search for swings
input int    InpHHHLNeed          = 2;     // need this many consecutive HH or HL

input group "── Exit ──"
input double InpTPUsd             = 12.0;  // TP in USD P&L (scales with lots)
input double InpSLBufferPts       = 0.10;  // SL = sweep_extreme ± this (XAU pip)

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "NSND";
input string InpStateFile     = "nsnd_trader_state.json";
input string InpDecisionCsv   = "nsnd_decisions.csv";  // per-trade log for reconciler
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m1_time = 0;
datetime g_last_signal_t = 0;
datetime g_last_heartbeat = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_today_day = 0;

const double CONTRACT_SIZE = 100.0;  // XAU $1/oz/lot

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
      return true;
   }
   return false;
}

//── M1 intraday trend ──────────────────────────────────────────────
int IntradayTrend() {
   double now_c   = iClose(_Symbol, PERIOD_M1, 1);
   double back_c  = iClose(_Symbol, PERIOD_M1, 1 + InpTrendLookback);
   if (back_c == 0) return 0;
   double delta = now_c - back_c;
   if (delta >  InpTrendThreshold) return +1;
   if (delta < -InpTrendThreshold) return -1;
   return 0;
}

//── Is bar at M1 shift k a valid NS (buy) or ND (sell) candle? ─────
bool IsNsCandidate(int k, bool buy_setup) {
   double o = iOpen (_Symbol, PERIOD_M1, k);
   double c = iClose(_Symbol, PERIOD_M1, k);
   double h = iHigh (_Symbol, PERIOD_M1, k);
   double l = iLow  (_Symbol, PERIOD_M1, k);
   long   v = iVolume(_Symbol, PERIOD_M1, k);
   if (buy_setup) { if (c >= o) return false; }    // NS = red
   else           { if (c <= o) return false; }    // ND = green
   // Volume: lower than at least vol_compare_min of prev vol_compare_n
   int lower_count = 0;
   for (int j = k + 1; j <= k + InpVolCompareN; j++) {
      long jv = iVolume(_Symbol, PERIOD_M1, j);
      if (jv > v) lower_count++;
   }
   if (lower_count < InpVolCompareMin) return false;
   // Narrow range
   double sum_rng = 0; int cnt = 0;
   for (int j = k + 1; j <= k + 5; j++) {
      sum_rng += iHigh(_Symbol, PERIOD_M1, j) - iLow(_Symbol, PERIOD_M1, j);
      cnt++;
   }
   if (cnt == 0) return false;
   double avg_rng = sum_rng / cnt;
   double rng = h - l;
   if (rng > InpNarrowRangeFrac * avg_rng) return false;
   return true;
}

//── Prior UHV: big opposite-color vol bar in window before NS ──────
bool HasPriorUhv(int ns_k, bool buy_setup, double avg20_vol) {
   for (int j = ns_k + 1; j <= ns_k + InpUhvLookback; j++) {
      double o = iOpen (_Symbol, PERIOD_M1, j);
      double c = iClose(_Symbol, PERIOD_M1, j);
      long   v = iVolume(_Symbol, PERIOD_M1, j);
      if (buy_setup)  { if (c >= o) continue; }  // need red (supply)
      else            { if (c <= o) continue; }  // need green (demand)
      if (v >= InpUhvVolMult * avg20_vol) return true;
   }
   return false;
}

double AvgVol20() {
   // BUGFIX 2026-05-17: Python backtest uses 20 bars BEFORE bo (excludes bo itself).
   // Was: shifts 1..20 (included bo at shift 1). Now: shifts 2..21 (excludes bo).
   double sum = 0;
   for (int j = 2; j <= 21; j++) sum += iVolume(_Symbol, PERIOD_M1, j);
   return sum / 20.0;
}

//── HH/HL Dow Theory trend confirmation ────────────────────────────
//   Returns +1 for confirmed uptrend (HH + HL), -1 for downtrend (LH + LL), 0 otherwise.
int HhHlTrend() {
   // Collect last `need` swing highs and lows in the lookback window.
   // Swing high = bar.high > N bars on each side (we iterate M1 shifts 1+N up to lookback).
   int N    = InpHHHLSwingN;
   int LB   = InpHHHLLookback;
   int need = InpHHHLNeed;
   // BUGFIX 2026-05-17: was cap 10 — if window had >10 swings, NEWER swings were
   // dropped (we append older first), which is exactly what we DON'T want for
   // recency-based trend check. Raised to 50 and added overflow protection.
   double sh_vals[50]; int sh_count = 0;
   double sl_vals[50]; int sl_count = 0;
   for (int s = LB; s >= 1 + N; s--) {
      double bh = iHigh(_Symbol, PERIOD_M1, s);
      double bl = iLow (_Symbol, PERIOD_M1, s);
      bool is_h = true, is_l = true;
      for (int k = 1; k <= N; k++) {
         if (iHigh(_Symbol, PERIOD_M1, s + k) >= bh) is_h = false;
         if (iHigh(_Symbol, PERIOD_M1, s - k) >= bh) is_h = false;
         if (iLow(_Symbol, PERIOD_M1, s + k)  <= bl) is_l = false;
         if (iLow(_Symbol, PERIOD_M1, s - k)  <= bl) is_l = false;
      }
      if (is_h) {
         // Shift older entries left if full — keep the most recent N
         if (sh_count >= 50) { for (int x=0; x<49; x++) sh_vals[x] = sh_vals[x+1]; sh_count = 49; }
         sh_vals[sh_count++] = bh;
      }
      if (is_l) {
         if (sl_count >= 50) { for (int x=0; x<49; x++) sl_vals[x] = sl_vals[x+1]; sl_count = 49; }
         sl_vals[sl_count++] = bl;
      }
   }
   if (sh_count < need || sl_count < need) return 0;
   // sh_vals is in iter-order: older shifts first. We want the LAST `need` (most recent).
   bool up_ok = true, down_ok = true;
   for (int k = sh_count - need + 1; k < sh_count; k++) {
      if (sh_vals[k] <= sh_vals[k-1]) up_ok = false;       // not ascending
      if (sh_vals[k] >= sh_vals[k-1]) down_ok = false;     // not descending
   }
   for (int k = sl_count - need + 1; k < sl_count; k++) {
      if (sl_vals[k] <= sl_vals[k-1]) up_ok = false;
      if (sl_vals[k] >= sl_vals[k-1]) down_ok = false;
   }
   if (up_ok)   return +1;
   if (down_ok) return -1;
   return 0;
}

//── FVG overlap check at given timeframe ───────────────────────────
//   period: PERIOD_M15 or PERIOD_H1
//   bullish: looking for bullish FVG (for NS/buy)
//   ns_low/ns_high: the NS bar's price range
bool FvgOverlap(ENUM_TIMEFRAMES period, int lookback, bool bullish,
                double ns_low, double ns_high) {
   for (int i = 2; i <= lookback; i++) {
      double gap_lo, gap_hi;
      if (bullish) {
         gap_lo = iHigh(_Symbol, period, i + 2);
         gap_hi = iLow (_Symbol, period, i);
         if (gap_hi <= gap_lo) continue;
         // Unfilled: no bar between i-1 and 0 has low < gap_lo
         bool filled = false;
         for (int j = i - 1; j >= 0; j--) {
            if (iLow(_Symbol, period, j) < gap_lo) { filled = true; break; }
         }
         if (filled) continue;
      } else {
         gap_lo = iHigh(_Symbol, period, i);
         gap_hi = iLow (_Symbol, period, i + 2);
         if (gap_hi <= gap_lo) continue;
         bool filled = false;
         for (int j = i - 1; j >= 0; j--) {
            if (iHigh(_Symbol, period, j) > gap_hi) { filled = true; break; }
         }
         if (filled) continue;
      }
      // Overlap with NS/ND range?
      if (ns_low <= gap_hi && ns_high >= gap_lo) return true;
   }
   return false;
}

//── Try NS/ND signal on M1 bar at shift 1 ──────────────────────────
bool TryNsndSignal() {
   datetime bo_t = iTime(_Symbol, PERIOD_M1, 1);
   if (bo_t == g_last_signal_t) return false;

   int trend = IntradayTrend();
   if (trend == 0) return false;
   bool buy_setup = (trend > 0);

   // HH/HL Dow-theory confirmation (default ON for NSND — backtest improved R:R 3.5→9.8)
   if (InpUseHHHL) {
      int hh = HhHlTrend();
      if (hh == 0) return false;                            // ranging — skip
      if (buy_setup && hh < 0) return false;                // intraday up but no HH+HL
      if (!buy_setup && hh > 0) return false;
   }

   double bo_high = iHigh(_Symbol, PERIOD_M1, 1);
   double bo_low  = iLow (_Symbol, PERIOD_M1, 1);
   double avg20 = AvgVol20();
   if (avg20 <= 0) return false;

   // Find NS/ND in the lookback window
   for (int k = 2; k <= 1 + InpNsLookback; k++) {
      if (!IsNsCandidate(k, buy_setup)) continue;
      if (!HasPriorUhv(k, buy_setup, avg20)) continue;
      // FVG overlap. 2026-05-20 walk-forward: M15-ONLY beats M15-or-H1
      // (drops H1-only junk trades, WR 54%->62% on train, identical on test).
      // H1 is the same coarse-TF mistake we fixed on S3/S1. Default M15-only.
      double ns_low  = iLow(_Symbol, PERIOD_M1, k);
      double ns_high = iHigh(_Symbol, PERIOD_M1, k);
      bool fvg_ok = FvgOverlap(PERIOD_M15, InpFvgLookbackM15, buy_setup, ns_low, ns_high)
                 || (InpUseH1Fvg && FvgOverlap(PERIOD_H1, InpFvgLookbackH1, buy_setup, ns_low, ns_high));
      if (!fvg_ok) continue;
      // Sweep check
      if (buy_setup) {
         if (bo_low >= ns_low) continue;
      } else {
         if (bo_high <= ns_high) continue;
      }
      // Already swept by an earlier bar (between k-1 and 2)?
      bool already = false;
      for (int m = k - 1; m >= 2; m--) {
         if (buy_setup) {
            if (iLow(_Symbol, PERIOD_M1, m) < ns_low) { already = true; break; }
         } else {
            if (iHigh(_Symbol, PERIOD_M1, m) > ns_high) { already = true; break; }
         }
      }
      if (already) continue;

      // FIRE
      double ppp = InpLots * CONTRACT_SIZE;
      double tp_dist = InpTPUsd / ppp;
      double entry, sl, tp;
      if (buy_setup) {
         entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         sl    = bo_low - InpSLBufferPts;
         tp    = entry + tp_dist;
      } else {
         entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         sl    = bo_high + InpSLBufferPts;
         tp    = entry - tp_dist;
      }

      g_signals_today++;
      Log(StringFormat("%s — entry=%.2f sl=%.2f tp=%.2f ns_shift=%d",
                       buy_setup ? "NS BUY" : "ND SELL", entry, sl, tp, k));

      bool ok;
      if (buy_setup) ok = g_trade.Buy(InpLots, _Symbol, 0, sl, tp, "NS_buy");
      else           ok = g_trade.Sell(InpLots, _Symbol, 0, sl, tp, "ND_sell");
      if (!ok) {
         Log(StringFormat("[ERR] order failed: ret=%d %s",
                          g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         return false;
      }
      g_entries_today++;
      g_last_signal_t = bo_t;
      ulong ticket = g_trade.ResultOrder();
      double actual_fill = g_trade.ResultPrice();
      Log(StringFormat("[FILLED] ticket=%d fill=%.2f (intended=%.2f Δ=%.2f)",
                       ticket, actual_fill, entry, actual_fill - entry));
      // Log decision for reconciler
      datetime ns_t = iTime(_Symbol, PERIOD_M1, k);
      long ns_vol_log = iVolume(_Symbol, PERIOD_M1, k);
      LogDecisionCsv(bo_t, bo_high, bo_low, iVolume(_Symbol, PERIOD_M1, 1),
                     ns_t, ns_low, ns_high, ns_vol_log,
                     buy_setup, entry, sl, tp, actual_fill, ticket);
      return true;
   }
   return false;
}

//── CSV decision logger (joined with turtle_fills.csv by ticket) ───
void LogDecisionCsv(datetime bo_t, double bo_h, double bo_l, long bo_v,
                    datetime ns_t, double ns_low, double ns_high, long ns_v,
                    bool buy_setup,
                    double intended_entry, double sl, double tp,
                    double actual_fill, ulong ticket) {
   int fh = FileOpen(InpDecisionCsv, FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (fh == INVALID_HANDLE) {
      fh = FileOpen(InpDecisionCsv, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
      if (fh == INVALID_HANDLE) return;
      FileWrite(fh, "fire_iso","ea","side","bo_time_iso","bo_high","bo_low","bo_volume",
                    "ns_time_iso","ns_low","ns_high","ns_volume",
                    "intended_entry","intended_sl","intended_tp","actual_fill","ticket","magic","lots");
   } else {
      FileSeek(fh, 0, SEEK_END);
   }
   FileWrite(fh,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      "NSND",
      buy_setup ? "buy" : "sell",
      TimeToString(bo_t, TIME_DATE | TIME_SECONDS),
      DoubleToString(bo_h, 2),
      DoubleToString(bo_l, 2),
      IntegerToString((long)bo_v),
      TimeToString(ns_t, TIME_DATE | TIME_SECONDS),
      DoubleToString(ns_low, 2),
      DoubleToString(ns_high, 2),
      IntegerToString((long)ns_v),
      DoubleToString(intended_entry, 2),
      DoubleToString(sl, 2),
      DoubleToString(tp, 2),
      DoubleToString(actual_fill, 2),
      IntegerToString((long)ticket),
      IntegerToString((long)InpMagicNumber),
      DoubleToString(InpLots, 2)
   );
   FileClose(fh);
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"NsndTrader\",\"version\":\"1.00\",\"alive\":true,"
      "\"symbol\":\"%s\",\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.4f,\"tp_usd\":%.0f}",
      _Symbol,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots, InpTPUsd));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   Log(StringFormat("NsndTrader Init — symbol=%s magic=%d lots=%.4f TP=$%.0f",
                    _Symbol, InpMagicNumber, InpLots, InpTPUsd));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log(StringFormat("NsndTrader Deinit reason=%d signals=%d entries=%d",
                    reason, g_signals_today, g_entries_today));
}

void OnTick() {
   IsNewDay();
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if (cur != g_last_m1_time && g_last_m1_time != 0) {
      TryNsndSignal();
   }
   g_last_m1_time = cur;
   WriteHeartbeat();
}
