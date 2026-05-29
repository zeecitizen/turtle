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
#property version   "1.34"
#property strict

// ╔══════════════════════════════════════════════════════════════════╗
// ║  2026-05-27 RE-VALIDATION (nsnd_native_validation.py): the old     ║
// ║  "backtest≠live" was a DATA bug — the backtest read reverse-       ║
// ║  engineered M1 volume; the live EA reads NATIVE iVolume (differ on ║
// ║  99.9% of bars). Re-run on NATIVE bars (latest_for_claude.csv):    ║
// ║  122 trades, 67.2% WR, +$8079/18d @0.10, walk-forward OOS +$3532.  ║
// ║  The edge is REAL on native volume. Revive at 0.01 lots and        ║
// ║  CONFIRM the live win-rate holds before trusting full size.        ║
// ╚══════════════════════════════════════════════════════════════════╝

// v1.10 (2026-05-22): "2R Free Roll" breakeven added (ManageOpenPositions, tick-
// level, side-aware). Backtest (backtest_exit_protocols_multi.py, NSND deployed
// signals, 13 real-tick days @ 0.03, n=93): baseline +$475 / WR 31% / PF 3.13 →
// breakeven-only +$518 / WR 53% / PF 4.13, and it HOLDS out-of-sample (+$311 →
// +$330). Partial scale-out was tested and DILUTES (caps NSND's big asymmetric
// runners: +$488 < +$518) → default OFF. ATR-trail/drop-TP was WORSE than
// baseline (+$443) → not implemented. So: breakeven ON, partial OFF.

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.01;  // 2026-05-27: Shano Exness $126 account ONLY. Was 0.03 (FTMO 3x) = ~$36 risk/trade = account-ending. 0.01.
input int    InpMagicNumber   = 88006;
input double InpDailyLossHalt = 50.0;  // Daily stop: halt NEW entries if down $this today (incl. floating). ~20% of $126 acct. 0=off.

input group "── Profit protection: 2R Free Roll (backtest-validated 2026-05-22) ──"
input bool   InpEnableBreakeven = true;  // VALIDATED for NSND: +$43/12d (+$518 vs +$475 baseline), WR 31%->53%, PF 3.13->4.13, holds OOS (+$311->+$330), n=93. Moves SL to breakeven at +InpBreakevenR. Applies to already-open trades on reattach.
input double InpBreakevenR      = 1.0;   // R-multiple that arms breakeven. R = entry − ORIGINAL SL.
input double InpBEArmUsd        = 0.0;   // Breakeven: lock SL at entry once trade is +$this profit. SUPERSEDED by the trailing lock below (0=off). Set >0 only to use fixed BE instead of the trail.
input double InpTrailActUsd     = 0.0;   // 2026-05-29 REVERTED to OFF — trail's S1/S3/NSND "win" was measured on misaligned data; original validated NSND uses InpEnableBreakeven=true (2R Free Roll) which stays on.
input double InpTrailGiveUsd    = 0.3;   // Trailing lock: bank & exit if profit falls $this back from its peak ($0.3 keeps it outside gold spread so noise can't shake you out).
input string InpPeakLogFile     = "trade_peaks_NSND.csv";  // closed-trade peak (MFE) log in Common\Files — feeds the live "% of trades reached here" slider markers.
input bool   InpEnablePartial   = false; // OFF for NSND: backtest showed partial scale-out DILUTES the edge (+$488 < +$518 BE-only) by capping NSND's big asymmetric runners. Enable only after re-testing.
input double InpPartialR        = 1.5;   // R-multiple to bank the partial (if enabled).
input double InpPartialFrac     = 0.5;   // fraction of volume to bank (rounded to lot step).
input double InpBEBufferPts     = 0.30;  // SL set this far beyond entry (price units) to cover spread/swap.

input group "── Human profit-pulse + one-tap GRAB ──"
input bool   InpEnableGrab = true;       // honor a GRAB command (close ALL this EA's positions at market) from WhatsApp/dashboard one tap.
input double InpAvgWinUsd  = 14.0;       // reference avg winning trade ($) for the heartbeat 'bigness' read (NSND ~$13.7 avg win @0.03).
input string InpGrabFile   = "grab_command.txt"; // shared command file (epoch id). EA grabs on a NEWER id than last seen.

input group "── Detection ──"
input int    InpNsLookback        = 15;    // M1 bars searched for NS/ND
input int    InpVolCompareN       = 4;     // NS vol < at least this many of prev N
input int    InpVolCompareMin     = 3;     // BUGFIX 2026-05-17: was 2; clock-aligned sweep best at 3
input double InpNarrowRangeFrac   = 1.0;   // NS range < this × avg-prev-5
input int    InpUhvLookback       = 20;    // bars before NS that must have a UHV
input double InpUhvVolMult        = 1.30;  // UHV vol > this × avg-20
input int    InpTrendLookback     = 60;    // M1 bars for trend (~1 hour)
input double InpTrendThreshold    = 2.0;   // BUGFIX 2026-05-17: was 1.0; clock-aligned sweep best at 2.0 (filters more noise)
input double InpERMin             = 0.0;   // 2026-05-29 NEW: Kaufman Efficiency Ratio chop filter (same math as S4). 0=OFF. Threshold to be validated on aligned oracle before enabling.
input int    InpERLookback        = 30;    // M1 bars for the ER calc.

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
input bool   InpMaxOneSameDir = true;  // ANTI-CLUSTER: don't open if S1/S3/NSND already hold a position the SAME direction. Validated on real ticks. 0=off.
input bool   InpSkipOvernight = true;  // skip NEW entries during thin 00:00-06:00 broker hours. 0=off.
input int    InpOvernightStart= 0;     // broker hour: block new entries from here ...
input int    InpOvernightEnd  = 6;     // ... until here (exclusive).
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

// Kaufman Efficiency Ratio over InpERLookback M1 bars. 0=chop / 1=trend.
double EfficiencyRatio() {
   double net = MathAbs(iClose(_Symbol,PERIOD_M1,1) - iClose(_Symbol,PERIOD_M1,InpERLookback));
   double path = 0;
   for (int s = 1; s < InpERLookback; s++)
      path += MathAbs(iClose(_Symbol,PERIOD_M1,s) - iClose(_Symbol,PERIOD_M1,s+1));
   return (path > 0) ? net / path : 0.0;
}
double CurrentSpreadPts() {
   return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
}

double g_day_start_equity = 0;

//── Per-position management state (2R Free Roll) ───────────────────
//   Captures each position's ORIGINAL SL on first sighting so R survives the
//   breakeven move; survives reattach (live SL is still original on first sight).
ulong  g_mng_ticket[256];
double g_mng_sl0[256];
bool   g_mng_partialed[256];
double g_mng_peak[256];      // per-position peak floating profit ($) — drives the trailing lock
double g_mng_trough[256];    // per-position worst floating loss ($, <=0) — MAE, for loss-side study
double g_mng_lastprof[256];  // last floating P&L ($) seen before close — outcome proxy (win/loss)
double g_mng_entry[256];     // entry price (for the closed-trade peak log)
int    g_mng_side[256];      // +1 buy / -1 sell (for the log)
bool   g_mng_logged[256];    // has this closed trade's peak been written to the MFE log yet
int    g_mng_count = 0;

//── One-tap GRAB state ──────────────────────────────────────────────
long     g_last_grab_id = 0;
datetime g_last_grab_check = 0;

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day;
      g_signals_today = 0;
      g_entries_today = 0;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);  // FTMO daily-loss baseline
      return true;
   }
   return false;
}

// FTMO circuit breaker (account-wide, equity-based incl. floating). Blocks NEW entries.
bool DailyLossHalted() {
   if (InpDailyLossHalt <= 0 || g_day_start_equity <= 0) return false;
   return (AccountInfoDouble(ACCOUNT_EQUITY) - g_day_start_equity) <= -InpDailyLossHalt;
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
   if (DailyLossHalted()) return false;   // FTMO daily-loss circuit breaker
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return false;   // Chop filter (OFF by default)
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

      if (ClusterBlocked(buy_setup ? +1 : -1)) return false;
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
                    "intended_entry","intended_sl","intended_tp","actual_fill","ticket","magic","lots",
                    "er","spread_pts");
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
      DoubleToString(InpLots, 2),
      DoubleToString(EfficiencyRatio(), 3),
      DoubleToString(CurrentSpreadPts(), 3)
   );
   FileClose(fh);
}

// READ-ONLY: the NS/ND setup NSND is currently watching, for the dashboard chart.
// Mirrors the entry scan (trend → NS/ND candidate + prior UHV + M15 FVG); the
// "level" is the candidate's low (buy) / high (sell) that price must SWEEP to fire.
string BuildWatchJson() {
   int dir = IntradayTrend();
   if (dir == 0) return "null";
   bool buy = (dir > 0);
   double avg20 = AvgVol20();
   if (avg20 <= 0) return "null";
   for (int k = 2; k <= 1 + InpNsLookback; k++) {
      if (!IsNsCandidate(k, buy)) continue;
      if (!HasPriorUhv(k, buy, avg20)) continue;
      double ns_low = iLow(_Symbol, PERIOD_M1, k), ns_high = iHigh(_Symbol, PERIOD_M1, k);
      bool fvg_ok = FvgOverlap(PERIOD_M15, InpFvgLookbackM15, buy, ns_low, ns_high)
                 || (InpUseH1Fvg && FvgOverlap(PERIOD_H1, InpFvgLookbackH1, buy, ns_low, ns_high));
      if (!fvg_ok) continue;
      return StringFormat(
         "{\"dir\":\"%s\",\"ref_bar_t\":\"%s\",\"ref_high\":%.3f,\"ref_low\":%.3f,"
         "\"level\":%.3f,\"setup_bar_t\":\"%s\"}",
         buy ? "buy" : "sell",
         TimeToString(iTime(_Symbol, PERIOD_M1, k), TIME_DATE|TIME_SECONDS),
         ns_high, ns_low, (buy ? ns_low : ns_high),
         TimeToString(iTime(_Symbol, PERIOD_M1, 1), TIME_DATE|TIME_SECONDS));
   }
   return "null";
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   int n_open = 0;
   double floating = FloatingPnL(n_open);
   double bigness = (InpAvgWinUsd > 0 && floating > 0) ? floating / InpAvgWinUsd : 0.0;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"NsndTrader\",\"version\":\"1.34\",\"alive\":true,"
      "\"symbol\":\"%s\",\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.4f,\"tp_usd\":%.0f,"
      "\"watch\":%s,\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,\"open\":%s}",
      _Symbol,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots, InpTPUsd,
      BuildWatchJson(), floating, n_open, bigness, InpAvgWinUsd, BuildOpenJson()));
   FileClose(fh);
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();   // ignore any pre-existing grab command on attach
   Log(StringFormat("NsndTrader Init — symbol=%s magic=%d lots=%.4f TP=$%.0f grab_base=%I64d",
                    _Symbol, InpMagicNumber, InpLots, InpTPUsd, g_last_grab_id));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log(StringFormat("NsndTrader Deinit reason=%d signals=%d entries=%d",
                    reason, g_signals_today, g_entries_today));
}

//── 2R Free Roll: side-aware per-position management ───────────────
int MngIndex(ulong ticket) {
   for (int i = 0; i < g_mng_count; i++)
      if (g_mng_ticket[i] == ticket) return i;
   int idx = (g_mng_count < 256) ? g_mng_count++ : 0;
   g_mng_ticket[idx]    = ticket;
   g_mng_sl0[idx]       = PositionGetDouble(POSITION_SL);
   g_mng_partialed[idx] = false;
   g_mng_peak[idx]      = 0.0;
   g_mng_trough[idx]    = 0.0;
   g_mng_lastprof[idx]  = 0.0;
   g_mng_entry[idx]     = PositionGetDouble(POSITION_PRICE_OPEN);
   g_mng_side[idx]      = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   g_mng_logged[idx]    = false;
   return idx;
}

//   Walk this EA's open positions (BUY or SELL) each tick. At +BreakevenR move
//   SL to breakeven (entry ∓ buffer). Optional partial bank at +PartialR. Static
//   TP is left untouched (validated: keeping TP beats trailing on NSND).
void ManageOpenPositions() {
   if (!InpEnableBreakeven && !InpEnablePartial && InpBEArmUsd <= 0 && InpTrailActUsd <= 0) return;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (step <= 0) step = 0.01;

   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool is_buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);

      double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur_sl = PositionGetDouble(POSITION_SL);
      double cur_tp = PositionGetDouble(POSITION_TP);
      double vol    = PositionGetDouble(POSITION_VOLUME);

      int mi = MngIndex(ticket);
      double R = MathAbs(entry - g_mng_sl0[mi]);
      if (R <= 0) continue;

      double prof  = is_buy ? (bid - entry) : (entry - ask);   // profit distance (price)
      double be_sl = NormalizeDouble(is_buy ? entry + InpBEBufferPts
                                            : entry - InpBEBufferPts, _Digits);
      // a move is protective if it pulls the stop toward/through breakeven
      bool can_raise = is_buy ? (cur_sl < be_sl) : (cur_sl == 0.0 || cur_sl > be_sl);

      // TRAILING PROFIT-LOCK (Zee's idea, validated trail_all.py: best-or-tied on all 3 EAs).
      // Once +$Act, ratchet a floor under the peak and bank the instant profit gives back
      // $Give from peak — catches green trades that peak BELOW the old +$1 breakeven and
      // reverse. Keeps the TP (a runner still reaches it). Slides hard SL to entry as a
      // backstop, which also lights the dashboard "profit secured" banner.
      double prof_usd = prof * vol * 100.0;
      if (prof_usd > g_mng_peak[mi])   g_mng_peak[mi]   = prof_usd;
      if (prof_usd < g_mng_trough[mi]) g_mng_trough[mi] = prof_usd;   // MAE (worst dip)
      g_mng_lastprof[mi] = prof_usd;                                  // outcome proxy
      if (InpTrailActUsd > 0 && g_mng_peak[mi] >= InpTrailActUsd) {
         bool need_be = is_buy ? (cur_sl < entry) : (cur_sl == 0.0 || cur_sl > entry);
         if (need_be) g_trade.PositionModify(ticket, NormalizeDouble(entry, _Digits), cur_tp);
         double floor_usd = MathMax(0.0, g_mng_peak[mi] - InpTrailGiveUsd);
         if (prof_usd <= floor_usd) {
            if (g_trade.PositionClose(ticket))
               Log(StringFormat("[TRAIL] #%I64u banked +$%.2f (peak +$%.2f, gave back $%.2f)",
                   ticket, prof_usd, g_mng_peak[mi], g_mng_peak[mi] - prof_usd));
            continue;
         }
      }

      // GIVE-BACK KILLER ($-based breakeven): once +$InpBEArmUsd floating, lock breakeven.
      // (Superseded by the trailing lock above; only runs if InpBEArmUsd>0 & trail off.)
      if (InpBEArmUsd > 0 && can_raise && (prof * vol * 100.0) >= InpBEArmUsd) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE$] #%I64u SL->%.2f (+$%.2f locked)", ticket, be_sl, prof*vol*100.0));
         continue;
      }


      // 1. partial bank + breakeven at +PartialR (once)
      if (InpEnablePartial && !g_mng_partialed[mi] && prof >= InpPartialR * R) {
         double close_vol = NormalizeDouble(MathFloor((vol * InpPartialFrac) / step) * step, 2);
         if (close_vol >= vmin && (vol - close_vol) >= vmin) {
            if (g_trade.PositionClosePartial(ticket, close_vol)) {
               g_mng_partialed[mi] = true;
               Log(StringFormat("[2R] Banked %.2f of #%I64u (+%.2fR) runner=%.2f",
                                close_vol, ticket, prof / R, vol - close_vol));
            }
         } else {
            g_mng_partialed[mi] = true;
         }
         if (InpEnableBreakeven && can_raise &&
             g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[2R] Breakeven #%I64u SL→%.2f (TP kept %.2f)", ticket, be_sl, cur_tp));
         continue;
      }

      // 2. plain breakeven at +BreakevenR
      if (InpEnableBreakeven && can_raise && prof >= InpBreakevenR * R) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE] #%I64u SL→%.2f (+%.2fR, TP kept %.2f)",
                             ticket, be_sl, prof / R, cur_tp));
      }
   }

   // ── Closed-trade peak (MFE) logging ───────────────────────────────
   // Any ticket we were tracking that is no longer open has closed — write its
   // peak floating profit once. The dashboard turns these into the live
   // "X% of trades reached here" markers on the trade slider (real data, not backtest).
   for (int j = 0; j < g_mng_count; j++) {
      if (g_mng_logged[j] || g_mng_ticket[j] == 0) continue;
      if (PositionSelectByTicket(g_mng_ticket[j])) continue;   // still open → skip
      AppendPeakLog(g_mng_side[j], g_mng_entry[j], g_mng_peak[j], g_mng_trough[j], g_mng_lastprof[j]);
      g_mng_logged[j] = true;
   }
}

//── Append one closed trade's peak (MFE) + trough (MAE) + outcome to the per-EA log ──
// Columns: time, side, entry, peak$, trough$, last$ (last floating ≈ realized outcome).
void AppendPeakLog(int side, double entry, double peak, double trough, double last) {
   int fh = FileOpen(InpPeakLogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWriteString(fh, StringFormat("%s,%s,%.2f,%.2f,%.2f,%.2f\n",
       TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
       side > 0 ? "BUY" : "SELL", entry, peak, trough, last));
   FileClose(fh);
}

//── ANTI-CLUSTER GUARD (shared logic with S1/S3): block a new entry during the thin
//   overnight window, or if S1/S3/NSND already hold a SAME-DIRECTION position. All three
//   run in one terminal so PositionsTotal() sees every magic. Reversible inputs.
bool ClusterBlocked(int side) {
   if (InpSkipOvernight) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      if (dt.hour >= InpOvernightStart && dt.hour < InpOvernightEnd) {
         Log(StringFormat("[GUARD] skip entry — overnight window (broker hour %d)", dt.hour));
         return true;
      }
   }
   if (InpMaxOneSameDir) {
      for (int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong tk = PositionGetTicket(i);
         if (tk == 0 || !PositionSelectByTicket(tk)) continue;
         if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         long mg = PositionGetInteger(POSITION_MAGIC);
         if (mg != 88003 && mg != 88004 && mg != 88006) continue;
         bool is_buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         if ((side > 0 && is_buy) || (side < 0 && !is_buy)) {
            Log("[GUARD] skip entry — cluster group already holds a same-direction position");
            return true;
         }
      }
   }
   return false;
}

//── Floating P&L + one-tap GRAB (close all this EA's positions on a newer id) ──
double FloatingPnL(int &n_open) {
   double sum = 0; n_open = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      n_open++;
   }
   return sum;
}
//── Open positions as a JSON array (for the dashboard's live Open Positions view) ──
string BuildOpenJson() {
   string arr = "["; int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      int  mi  = MngIndex(tk);
      bool secured = (InpTrailActUsd > 0 && g_mng_peak[mi] >= InpTrailActUsd);
      if (n > 0) arr += ",";
      arr += StringFormat("{\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.2f,\"cur\":%.2f,\"pnl\":%.2f,\"sl\":%.2f,\"tp\":%.2f,\"peak\":%.2f,\"secured\":%s}",
                          buy ? "BUY" : "SELL", PositionGetDouble(POSITION_VOLUME),
                          PositionGetDouble(POSITION_PRICE_OPEN), PositionGetDouble(POSITION_PRICE_CURRENT),
                          PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP),
                          PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP),
                          g_mng_peak[mi], secured ? "true" : "false");
      n++;
   }
   return arr + "]";
}

long ReadGrabId() {
   if (!FileIsExist(InpGrabFile, FILE_COMMON)) return 0;
   int fh = FileOpen(InpGrabFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
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
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (g_trade.PositionClose(tk)) closed++;
   }
   if (closed > 0)
      Log(StringFormat("[GRAB] one-tap grab id=%I64d — closed %d position(s) at market", id, closed));
}

void OnTick() {
   IsNewDay();
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if (cur != g_last_m1_time && g_last_m1_time != 0) {
      TryNsndSignal();
   }
   g_last_m1_time = cur;
   ManageOpenPositions();   // 2R Free Roll: breakeven on open trades (every tick)
   CheckGrabCommand();      // one-tap GRAB (close all) from WhatsApp/dashboard
   WriteHeartbeat();
}
