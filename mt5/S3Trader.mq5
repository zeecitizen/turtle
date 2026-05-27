//+------------------------------------------------------------------+
//| S3Trader.mq5 — Setup 3 "Effort vs Result" live executor          |
//|                                                                  |
//| Empirical edge from 12-day real-tick backtest (2026-05-15):     |
//|   • 11 trades / 12 days @ 0.10 lots                              |
//|   • Win rate 63.6%  |  Avg win $65  |  Avg loss $46              |
//|   • EV +$24.58/trade  |  Total +$270.40 in 12 days               |
//|   • @ 0.40 lots projection: +$1,082 / 12 days ≈ $90/day          |
//|                                                                  |
//| STRATEGY (BUY-only — sell variant lost on backtest):             |
//|   1. H1: identify unfilled bullish Fair Value Gap (3-bar gap up) |
//|   2. M5: price retraces and TAPS the H1 FVG                      |
//|   3. In retracement, look at red M5 candles                      |
//|   4. Find a GREEN M5 candle that:                                |
//|        a. wicks BELOW one of the red's low                       |
//|        b. closes back INSIDE the red's range (close > red.low)   |
//|        c. has HIGHER volume than that red                        |
//|   5. ENTRY: market BUY at the wicking-green's close              |
//|   6. SL: wicking-green's low − 1 pip                             |
//|   7. TP: highest high in the last 30 M5 bars (recent peak)       |
//|   8. PRE-REQ: 2-hour M5 uptrend (close[now] − close[24 bars] > 2)|
//|                                                                  |
//| Fires once per qualifying M5 bar close; deduped by bar timestamp.|
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — Setup 3 Effort vs Result (Teacher Spec v2)"
#property version   "2.40"
#property strict

// ╔══════════════════════════════════════════════════════════════════╗
// ║  📄 STRATEGY DOCUMENTATION: docs/S3_STRATEGY.md                 ║
// ║  Contains: full strategy logic, backtest results, parameter     ║
// ║  rationale, walk-forward validation, and change history.        ║
// ║  READ THAT FILE FIRST before modifying this EA.                 ║
// ╚══════════════════════════════════════════════════════════════════╝

// v2.10 (2026-05-22): "2R Free Roll" profit protection added (ManageOpenPositions,
// tick-level). Backtest (backtest_exit_protocols.py, same S3 signals, 13 real-tick
// days @ 0.09): baseline +$115 / WR .60 / worst -$87.8 → partial+BE (keep TP)
// +$250 / WR .80 / worst -$62.9. The give-back that scared us (a +profit trade
// round-tripping to -$87.8) is caught by breakeven. DELIBERATELY NOT implemented:
// the doc's drop-static-TP + 3×ATR-Chandelier trail — it scored +$187 < +$250,
// i.e. WORSE than keeping our peak-TP. n=5 trades → treat as PROVISIONAL.

// v2 (2026-05-16): faithful teacher-spec upgrade. Retracement defined as
// "reds that broke last green's low" (was swing-high break — fires 10× more
// signals). H1 FVG made optional (default off — backtest showed it cuts too
// many winners on XAU). Trend threshold relaxed to $1.0.
// Backtest 12 days real ticks @ 0.10 lots: +$1,184 (vs v1 +$270),
// projects ~$395/day @ 0.40 lots.

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.01;  // 2026-05-27: Shano Exness $126 account (was 0.09 FTMO-era — that'd be ~$45-135 risk/trade = account-ending on $126). 0.01 = ~$5-15/trade.
input int    InpMagicNumber   = 88003;

input group "── Sides ──"
input bool   InpDoBuys        = true;     // BUY side enabled
input bool   InpDoSells       = true;     // 2026-05-27: SELL side added. Backtest shows SELL WR=81.7% EV=+$10.41 vs BUY WR=72.9% EV=-$6.70. Sells are the stronger direction.

input group "── FTMO daily-loss circuit breaker ──"
input double InpDailyLossHalt = 50.0;   // Daily stop: halt NEW entries if down $this today (incl. floating). ~20% of $126 acct. 0=off.

input group "── Profit protection: 2R Free Roll (backtest-validated 2026-05-22) ──"
input bool   InpEnableBreakeven = true;  // move SL to breakeven once +InpBreakevenR reached (caps the 'give back to zero' risk). On reattach, applies to ALREADY-OPEN trades too.
input double InpBreakevenR      = 1.0;   // R-multiple that arms breakeven. R = entry − ORIGINAL SL.
input double InpBEArmUsd        = 0.0;   // Breakeven: lock SL at entry once trade is +$this profit. SUPERSEDED by the trailing lock below (0=off). Set >0 only to use fixed BE instead of the trail.
input double InpTrailActUsd     = 0.3;   // Trailing lock: arm once trade is +$this profit, then trail its peak. Validated best-or-tied on S1/S3/NSND. 0=off.
input double InpTrailGiveUsd    = 0.3;   // Trailing lock: bank & exit if profit falls $this back from its peak ($0.3 keeps it outside gold spread so noise can't shake you out).
input bool   InpEnablePartial   = true;  // bank InpPartialFrac of the position at +InpPartialR, then BE the rest (Income tranche). NOTE: on reattach, any open trade already past +1.5R is partialed+BE'd immediately.
input double InpPartialR        = 1.5;   // R-multiple to bank the partial.
input double InpPartialFrac     = 0.5;   // fraction of position volume to bank (rounded to lot step).
input double InpBEBufferPts     = 0.30;  // SL set this far ABOVE entry (price units) to cover spread/swap. Matches backtest BE buffer.
// REJECTED by backtest (kept here as a note, NOT implemented): dropping the static
// TP to trail the runner on 3×H1-ATR (Chandelier) scored +$187 vs +$250 for
// partial+BE-with-TP. Our peak-TP scalp beats the trend-runner trail. Do not add.

input group "── Human profit-pulse + one-tap GRAB ──"
input bool   InpEnableGrab = true;       // honor a GRAB command (close ALL this EA's positions at market). Fired from WhatsApp/dashboard one tap. The system 'feels' a big profit and lets YOU grab it.
input double InpAvgWinUsd  = 60.0;       // reference avg winning trade ($) for the 'bigness' read written to the heartbeat. bigness = floating / this = how-big-it-feels-like.
input string InpGrabFile   = "grab_command.txt"; // shared command file (epoch id). EA grabs on a NEWER id than last seen.

input group "── Detection ──"
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M1;  // 2026-05-27: DEFAULT M1 — full-logic validated +$3677/558tr 5/5 OOS+ vs M5 +$1068. Set PERIOD_M5 to revert.
input int    InpTrendLookback     = 24;   // M5 bars: ~2 hours for trend
input double InpTrendThreshold    = 1.0;  // min price units of move (v2: was 2.0)
input double InpTrend60Threshold  = 5.0;  // 2026-05-27: NEW 60-bar trend filter. VERIFIED robust (prove_all_improvements.py, reproduced): 6/7 walk-forward splits; +$504->+$571, DD $67->$55. Min |close[1]-close[61]| in trade direction. 0=off.
input int    InpRetraceLookback   = 30;   // M5 bars to look back for retracement
input int    InpTPPeakLookback    = 10;   // M5 bars for "recent peak" TP (v2: was 30)
input bool   InpRequireH1Fvg      = false;// v2: default OFF — backtest improved without
input int    InpH1FvgLookback     = 50;   // H1 bars (only used if InpRequireH1Fvg)
input bool   InpRequireM5Fvg      = false; // 2026-05-27: DISABLED. 18-day backtest shows FVG makes OOS 5x worse (-$321 vs -$60). Was validated on 12d but failed on 18d. Re-enable after further validation.
input int    InpM5FvgLookback     = 60;   // M5 bars to scan back for an unfilled bullish FVG (only used if InpRequireM5Fvg)
input double InpMinTPDistPts      = 0.2;  // min TP distance in price-pts (2 pips). BUGFIX 2026-05-17: was 0.5, but backtest uses sl_buf*2=0.20. The stricter 0.5 was rejecting valid trades and cutting backtest P&L by ~50%.
input double InpSLBufferPts       = 5.00; // 2026-05-27: raised from 2.00 → 5.00 after deep sweep (s3_deep_sweep.py, 150+ configs, 18 tick days). OOS improved +$115 → +$199, DD $80→$67. Wider SL absorbs noise, lets more trades survive to peak TP.
input double InpMaxUpperWickFrac  = 0.35; // 2026-05-19 teacher-faithful (lesson 10): reject wicking green if upper_wick/range > this (=rejection). Backtest: WR 63%->69%, EV +$13.78->+$16.46. Set 0 to disable.

input group "── Time-of-day filter (broker time) ──"
input bool   InpUseHourFilter     = false;      // 2026-05-18 19:00: DISABLED after live A/B. Filter blocked 3 wins (+$74) on launch day. 12d walk-forward was +$333 OOS but live variance is brutal — running un-filtered until we have more days.
input string InpSkipHours         = "13,15,16"; // skip-list (broker hrs) — only used if InpUseHourFilter=true.

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "S3";
input string InpStateFile     = "s3_trader_state.json";
input string InpDecisionCsv   = "s3_decisions.csv";  // per-trade decision log for reconciler
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m5_time = 0;        // last M5 bar timestamp we evaluated
datetime g_last_signal_t = 0;       // dedup: last M5 bar that fired
datetime g_last_heartbeat = 0;
// BUGFIX 2026-05-17: dedup by RED ref-time (matches backtest per-red set).
// Stores up to 200 matched red times TODAY; cleared on new day. Without this,
// the EA could refire on the same retracement red as bo advances.
datetime g_fired_reds[200];
int      g_fired_reds_count = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_today_day = 0;

//── Helpers ─────────────────────────────────────────────────────────
void Log(string msg) {
   if (!InpVerbose) return;
   PrintFormat("[%s] %s", InpLogPrefix, msg);
}

double g_day_start_equity = 0;   // account equity at the start of the broker day

//── Per-position management state (2R Free Roll) ───────────────────
//   Captures each position's ORIGINAL SL on first sighting (so R survives the
//   breakeven move) and remembers whether we've already banked the partial.
//   On reattach this table is empty, but the volume/SL on the live position is
//   still original, so the first sighting captures true R correctly.
ulong  g_mng_ticket[256];
double g_mng_sl0[256];
bool   g_mng_partialed[256];
double g_mng_peak[256];      // per-position peak floating profit ($) — drives the trailing lock
int    g_mng_count = 0;

//── One-tap GRAB state ──────────────────────────────────────────────
long     g_last_grab_id = 0;       // highest grab-command id we've already acted on
datetime g_last_grab_check = 0;    // throttle the file read

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day;
      g_signals_today = 0;
      g_entries_today = 0;
      g_fired_reds_count = 0;   // BUGFIX: clear fired-red dedup set daily
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);  // FTMO daily-loss baseline
      return true;
   }
   return false;
}

// FTMO circuit breaker: true if the account is down >= InpDailyLossHalt today
// (equity-based, so it counts floating losses too). Blocks NEW entries only;
// open positions keep their SL/TP. Account-wide because equity is account-wide.
bool DailyLossHalted() {
   if (InpDailyLossHalt <= 0 || g_day_start_equity <= 0) return false;
   double day_pl = AccountInfoDouble(ACCOUNT_EQUITY) - g_day_start_equity;
   return day_pl <= -InpDailyLossHalt;
}

bool IsRedAlreadyFired(datetime red_t) {
   for (int i = 0; i < g_fired_reds_count; i++) {
      if (g_fired_reds[i] == red_t) return true;
   }
   return false;
}

void RememberFiredRed(datetime red_t) {
   if (g_fired_reds_count < 200) {
      g_fired_reds[g_fired_reds_count++] = red_t;
   } else {
      // Shift left, drop oldest
      for (int i = 0; i < 199; i++) g_fired_reds[i] = g_fired_reds[i + 1];
      g_fired_reds[199] = red_t;
   }
}

//── Time-of-day filter: is the given broker hour in the skip list? ──
//   Walk-forward validated 2026-05-18: skipping broker hours 13,15,16
//   adds +$333 out-of-sample over 6 days (skipping pre-London / London
//   open / NY open killzones; gold is choppiest in those windows).
bool IsHourInSkipList(int hour) {
   if (!InpUseHourFilter) return false;
   string parts[];
   int n = StringSplit(InpSkipHours, ',', parts);
   for (int i = 0; i < n; i++) {
      string p = parts[i];
      StringTrimLeft(p);
      StringTrimRight(p);
      if (StringLen(p) == 0) continue;
      if ((int)StringToInteger(p) == hour) return true;
   }
   return false;
}

//── Trend check on M5 ───────────────────────────────────────────────
bool IsUptrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (now_close - back_close) > InpTrendThreshold;
}

bool IsDowntrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (back_close - now_close) > InpTrendThreshold;
}

// 60-bar trend-strength filter (verified robust 6/7 splits, 2026-05-27)
bool Trend60OK(bool isBuy) {
   if (InpTrend60Threshold <= 0) return true;
   double now  = iClose(_Symbol, InpTimeframe, 1);
   double back = iClose(_Symbol, InpTimeframe, 61);
   if (back == 0) return false;
   return isBuy ? (now - back >= InpTrend60Threshold) : (back - now >= InpTrend60Threshold);
}

//── H1 unfilled bullish FVG tapped during the retracement ──────────
//   retrace_back_shift = how many M5 bars back the retracement extends
bool H1FvgTappedDuringRetracement(int retrace_back_shift) {
   // Walk H1 bars searching for an unfilled bullish FVG.
   // For each candidate center shift i: FVG between bar at shift (i+2) and bar at shift i.
   // (Older bar's high < newer bar's low → bullish gap.)
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_high = iHigh(_Symbol, PERIOD_H1, i + 2);
      double newer_low  = iLow (_Symbol, PERIOD_H1, i);
      if (newer_low <= older_high) continue;     // no gap
      // Unfilled: no H1 bar between i-1 and now (shift 0) has low < older_high
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iLow(_Symbol, PERIOD_H1, j) < older_high) {
            filled = true; break;
         }
      }
      if (filled) continue;
      // Tap check: any M5 bar in [1, retrace_back_shift] has range overlap
      // with the FVG zone [older_high, newer_low].
      for (int k = 1; k <= retrace_back_shift; k++) {
         double mlow  = iLow(_Symbol, InpTimeframe, k);
         double mhigh = iHigh(_Symbol, InpTimeframe, k);
         if (mlow <= newer_low && mhigh >= older_high) return true;
      }
   }
   return false;
}

//── M5 unfilled bullish FVG tapped during the retracement ──────────
//   2026-05-19: walk-forward validated (train+test both ~2x EV vs no-FVG).
//   Uses the SAME-timeframe FVG (M5) instead of H1 — H1 was too coarse
//   (killed trade count to 7/12d); M5 keeps ~57 trades/12d at +$26 EV.
//   Mirrors Python find_h1_fvgs(M5) + fvg_tapped_at: for each retracement
//   red bar k, look for an unfilled bullish M5 FVG (formed before bar k)
//   whose zone bar k's range overlaps.
bool M5FvgTappedDuringRetracement(int retrace_back_shift) {
   for (int k = 1; k <= retrace_back_shift; k++) {
      double mlow  = iLow (_Symbol, InpTimeframe, k);
      double mhigh = iHigh(_Symbol, InpTimeframe, k);
      // candidate FVG: newer bar at shift i (older than tap bar k), gap between i+2 and i
      for (int i = k + 1; i <= k + InpM5FvgLookback; i++) {
         double older_high = iHigh(_Symbol, InpTimeframe, i + 2);
         double newer_low  = iLow (_Symbol, InpTimeframe, i);
         if (newer_low <= older_high) continue;       // no bullish gap
         // unfilled up to the tap bar: no bar between (i-1) and (k+1) has low < older_high
         bool filled = false;
         for (int j = i - 1; j > k; j--) {
            if (iLow(_Symbol, InpTimeframe, j) < older_high) { filled = true; break; }
         }
         if (filled) continue;
         // tap: bar k's range overlaps the FVG zone [older_high, newer_low]
         if (mlow <= newer_low && mhigh >= older_high) return true;
      }
   }
   return false;
}

//── S3 BUY signal check on M5 bar at shift 1 (just-closed) ─────────
//   Returns true if signal fired (and order sent).
bool TryS3BuySignal() {
   if (!InpDoBuys) return false;
   if (DailyLossHalted()) return false;   // FTMO daily-loss circuit breaker
   double bo_o = iOpen (_Symbol, InpTimeframe, 1);
   double bo_h = iHigh (_Symbol, InpTimeframe, 1);
   double bo_l = iLow  (_Symbol, InpTimeframe, 1);
   double bo_c = iClose(_Symbol, InpTimeframe, 1);
   long   bo_v = iVolume(_Symbol, InpTimeframe, 1);
   datetime bo_t = iTime(_Symbol, InpTimeframe, 1);

   // Dedup
   if (bo_t == g_last_signal_t) return false;

   // 0. Time-of-day filter (broker time). Validated 2026-05-18 walk-forward:
   //    skip broker hours 13,15,16 → +$333 out-of-sample / 6d, 8 days
   //    improved / 0 degraded vs no filter.
   if (InpUseHourFilter) {
      MqlDateTime bdt; TimeToStruct(bo_t, bdt);
      if (IsHourInSkipList(bdt.hour)) {
         g_last_signal_t = bo_t;   // mark as evaluated so we don't recheck every tick
         return false;
      }
   }

   // 1. Green wicking candle?
   if (bo_c <= bo_o) return false;

   // 2. Uptrend on M5
   if (!IsUptrendM5(1)) return false;
   if (!Trend60OK(true)) return false;   // 60-bar trend-strength filter (verified)

   // 3. v2: find retracement = "reds that broke the last green candle's low"
   //   Walk back looking for a green whose low got broken by subsequent reds.
   //   The reds AFTER that green (and before bo) are the retracement reds.
   int reds[30];
   int reds_count = 0;
   int max_red_shift = 1;
   for (int back_g = 2; back_g <= 1 + InpRetraceLookback; back_g++) {
      double g_o = iOpen (_Symbol, InpTimeframe, back_g);
      double g_c = iClose(_Symbol, InpTimeframe, back_g);
      double g_l = iLow  (_Symbol, InpTimeframe, back_g);
      if (g_c <= g_o) continue;          // not green — keep looking
      // Found a candidate green. Check subsequent reds (shifts back_g-1 down to 2)
      // for any whose low/close went BELOW g_l.
      bool any_broke = false;
      int  found_reds = 0;
      int  tmp_reds[30];
      int  tmp_max_shift = 1;
      for (int j = back_g - 1; j >= 2; j--) {
         double r_o = iOpen (_Symbol, InpTimeframe, j);
         double r_c = iClose(_Symbol, InpTimeframe, j);
         double r_l = iLow  (_Symbol, InpTimeframe, j);
         if (r_c < r_o) {
            if (r_c < g_l || r_l < g_l) any_broke = true;
            if (found_reds < 30) {
               tmp_reds[found_reds++] = j;
               if (j > tmp_max_shift) tmp_max_shift = j;
            }
         }
      }
      if (any_broke && found_reds > 0) {
         for (int k = 0; k < found_reds; k++) reds[k] = tmp_reds[k];
         reds_count = found_reds;
         max_red_shift = tmp_max_shift;
         break;
      }
   }
   if (reds_count == 0) return false;

   // 4. For each red, check wicking pattern: bo wicks below red.low,
   //    closes back inside red's range, and has higher volume than red.
   int matching_red_shift = -1;
   datetime matching_red_t = 0;
   for (int r = 0; r < reds_count; r++) {
      int rs = reds[r];
      double r_l = iLow   (_Symbol, InpTimeframe, rs);
      long   r_v = iVolume(_Symbol, InpTimeframe, rs);
      if (bo_l >= r_l)   continue;      // didn't wick below
      if (bo_c <= r_l)   continue;      // didn't close back inside
      if (bo_v <= r_v)   continue;      // need higher green vol
      matching_red_shift = rs;
      matching_red_t = iTime(_Symbol, InpTimeframe, rs);
      break;
   }
   if (matching_red_shift < 0) return false;

   // 4b. TEACHER FILTER (lesson 10): the wicking green must NOT have a big
   //     upper wick — a large upper wick means the up-move got rejected.
   //     Backtest 2026-05-19: upper_wick/range <= 0.35 lifts WR 63%->69%,
   //     EV +$13.78 -> +$16.46 over 12 days. Validated, teacher-faithful.
   if (InpMaxUpperWickFrac > 0.0) {
      double bo_range = bo_h - bo_l;
      if (bo_range > 0.0) {
         double upper_wick = bo_h - MathMax(bo_o, bo_c);
         if (upper_wick / bo_range > InpMaxUpperWickFrac) return false;
      }
   }

   // BUGFIX: dedup by RED's time (matches Python backtest per-ref-red dedup).
   // Without this, multiple consecutive bos could fire on the same retracement red.
   if (IsRedAlreadyFired(matching_red_t)) return false;

   // 5. H1 FVG tap during the retracement (v2: OPTIONAL — default off)
   if (InpRequireH1Fvg && !H1FvgTappedDuringRetracement(max_red_shift)) return false;

   // 5b. M5 (same-TF) FVG tap during the retracement — 2026-05-19 walk-forward
   //     validated as a quality gate (~2x EV/trade). Default ON.
   if (InpRequireM5Fvg && !M5FvgTappedDuringRetracement(max_red_shift)) return false;

   // 6. Compute SL / TP / entry
   //    BUGFIX 2026-05-17: TP must use the PEAK of bars BEFORE bo (shifts 2..N+1),
   //    NOT include bo itself (shift 1). The backtest excludes bo.high.
   //    Including bo would set TP ≈ bo.high (= entry + spread) → tiny instant
   //    "wins" that don't match the strategy's intent.
   double sl = bo_l - InpSLBufferPts;
   double tp = 0.0;
   for (int j = 2; j <= 1 + InpTPPeakLookback; j++) {
      double h = iHigh(_Symbol, InpTimeframe, j);
      if (h > tp) tp = h;
   }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // BUGFIX: backtest uses (entry + sl_buf*2) as min TP gating.
   // Take whichever is LESS strict so we don't filter trades the backtest accepted.
   double min_tp_dist = MathMin(InpMinTPDistPts, InpSLBufferPts * 2.0);
   if (tp <= ask + min_tp_dist) return false;

   g_signals_today++;
   Log(StringFormat("S3 BUY signal — entry=%.2f sl=%.2f tp=%.2f red_at_shift=%d (R:R=%.2f)",
                     ask, sl, tp, matching_red_shift, (tp - ask) / MathMax(0.0001, ask - sl)));

   // 7. Fire
   if (!g_trade.Buy(InpLots, _Symbol, 0, sl, tp, "S3_buy")) {
      Log(StringFormat("[ERR] Buy failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_signal_t = bo_t;
   RememberFiredRed(matching_red_t);   // BUGFIX: add to set so we don't refire on it
   ulong ticket = g_trade.ResultOrder();
   double actual_fill = g_trade.ResultPrice();
   Log(StringFormat("[FILLED] ticket=%d fill=%.2f (intended=%.2f Δ=%.2f)",
                    ticket, actual_fill, ask, actual_fill - ask));
   // Log the decision for the live-vs-backtest reconciler
   double red_l_log = iLow(_Symbol, InpTimeframe, matching_red_shift);
   long   red_v_log = iVolume(_Symbol, InpTimeframe, matching_red_shift);
   LogDecisionCsv(bo_t, bo_c, bo_l, bo_v, matching_red_t, red_l_log, red_v_log,
                  ask, sl, tp, actual_fill, ticket, "buy");
   return true;
}

//── S3 SELL signal check (mirror of Buy) ──────────────────────────
bool TryS3SellSignal() {
   if (!InpDoSells) return false;
   if (DailyLossHalted()) return false;
   double bo_o = iOpen (_Symbol, InpTimeframe, 1);
   double bo_h = iHigh (_Symbol, InpTimeframe, 1);
   double bo_l = iLow  (_Symbol, InpTimeframe, 1);
   double bo_c = iClose(_Symbol, InpTimeframe, 1);
   long   bo_v = iVolume(_Symbol, InpTimeframe, 1);
   datetime bo_t = iTime(_Symbol, InpTimeframe, 1);

   if (bo_t == g_last_signal_t) return false;
   if (InpUseHourFilter) {
      MqlDateTime bdt; TimeToStruct(bo_t, bdt);
      if (IsHourInSkipList(bdt.hour)) { g_last_signal_t = bo_t; return false; }
   }

   if (bo_c >= bo_o) return false;
   if (!IsDowntrendM5(1)) return false;
   if (!Trend60OK(false)) return false;   // 60-bar trend-strength filter (verified)

   int reds[30]; int reds_count = 0; int max_red_shift = 1;
   for (int back_g = 2; back_g <= 1 + InpRetraceLookback; back_g++) {
      double g_o = iOpen (_Symbol, InpTimeframe, back_g);
      double g_c = iClose(_Symbol, InpTimeframe, back_g);
      double g_h = iHigh (_Symbol, InpTimeframe, back_g);
      if (g_c >= g_o) continue; 
      bool any_broke = false; int found_reds = 0; int tmp_reds[30]; int tmp_max_shift = 1;
      for (int j = back_g - 1; j >= 2; j--) {
         double r_o = iOpen (_Symbol, InpTimeframe, j);
         double r_c = iClose(_Symbol, InpTimeframe, j);
         double r_h = iHigh (_Symbol, InpTimeframe, j);
         if (r_c > r_o) {
            if (r_c > g_h || r_h > g_h) any_broke = true;
            if (found_reds < 30) { tmp_reds[found_reds++] = j; if (j > tmp_max_shift) tmp_max_shift = j; }
         }
      }
      if (any_broke && found_reds > 0) {
         for (int k = 0; k < found_reds; k++) reds[k] = tmp_reds[k];
         reds_count = found_reds; max_red_shift = tmp_max_shift; break;
      }
   }
   if (reds_count == 0) return false;

   int matching_red_shift = -1; datetime matching_red_t = 0;
   for (int r = 0; r < reds_count; r++) {
      int rs = reds[r]; double r_h = iHigh(_Symbol, InpTimeframe, rs); long r_v = iVolume(_Symbol, InpTimeframe, rs);
      if (bo_h <= r_h) continue; if (bo_c >= r_h) continue; if (bo_v <= r_v) continue;
      matching_red_shift = rs; matching_red_t = iTime(_Symbol, InpTimeframe, rs); break;
   }
   if (matching_red_shift < 0) return false;
   if (IsRedAlreadyFired(matching_red_t)) return false;

   double sl = bo_h + InpSLBufferPts; double tp = 99999999.0;
   for (int j = 2; j <= 1 + InpTPPeakLookback; j++) { double l = iLow(_Symbol, InpTimeframe, j); if (l < tp) tp = l; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (tp >= bid - MathMin(InpMinTPDistPts, InpSLBufferPts * 2.0)) return false;

   g_signals_today++;
   if (!g_trade.Sell(InpLots, _Symbol, 0, sl, tp, "S3_sell")) return false;
   g_entries_today++; g_last_signal_t = bo_t; RememberFiredRed(matching_red_t);
   ulong ticket = g_trade.ResultOrder(); double actual_fill = g_trade.ResultPrice();
   LogDecisionCsv(bo_t, bo_c, bo_h, bo_v, matching_red_t, iHigh(_Symbol, InpTimeframe, matching_red_shift), 0, bid, sl, tp, actual_fill, ticket, "sell");
   return true;
}

//── CSV decision logger (one row per fired signal) ─────────────────
//   Joined with turtle_fills.csv by ticket → live vs backtest reconciler.
void LogDecisionCsv(datetime bo_t, double bo_c, double bo_l, long bo_v,
                    datetime red_t, double red_l, double red_v,
                    double intended_entry, double sl, double tp,
                    double actual_fill, ulong ticket, string side="buy") {
   int fh = FileOpen(InpDecisionCsv, FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (fh == INVALID_HANDLE) {
      // Create with header
      fh = FileOpen(InpDecisionCsv, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
      if (fh == INVALID_HANDLE) return;
      FileWrite(fh, "fire_iso","ea","side","bo_time_iso","bo_close","bo_low","bo_volume",
                    "red_time_iso","red_low","red_volume",
                    "intended_entry","intended_sl","intended_tp","actual_fill","ticket","magic","lots");
   } else {
      FileSeek(fh, 0, SEEK_END);
   }
   FileWrite(fh,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      "S3",
      side,
      TimeToString(bo_t,  TIME_DATE | TIME_SECONDS),
      DoubleToString(bo_c, 2),
      DoubleToString(bo_l, 2),
      IntegerToString((long)bo_v),
      TimeToString(red_t, TIME_DATE | TIME_SECONDS),
      DoubleToString(red_l, 2),
      IntegerToString((long)red_v),
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

//── State JSON heartbeat for dashboards / watchdog ─────────────────
// READ-ONLY: the liquidity-sweep setup S3 is currently watching, for the live chart.
// Mirrors the detection: trend → retracement (green-low broken by reds for buy / red-high
// broken by greens for sell) → the extreme level S3 wants swept & reclaimed. No trade logic.
string BuildWatchJson() {
   int dir = 0;
   if (InpDoBuys && IsUptrendM5(1) && Trend60OK(true)) dir = 1;
   else if (InpDoSells && IsDowntrendM5(1) && Trend60OK(false)) dir = -1;
   if (dir == 0) return "null";

   int reds[30]; int reds_count = 0;
   for (int back_g = 2; back_g <= 1 + InpRetraceLookback; back_g++) {
      double g_o = iOpen(_Symbol, InpTimeframe, back_g), g_c = iClose(_Symbol, InpTimeframe, back_g);
      double g_l = iLow(_Symbol, InpTimeframe, back_g),  g_h = iHigh(_Symbol, InpTimeframe, back_g);
      bool green = (g_c > g_o);
      if (dir == 1 ? !green : green) continue;     // buy seeks a prior green; sell a prior red
      bool any_broke = false; int tmp[30]; int found = 0;
      for (int j = back_g - 1; j >= 2; j--) {
         double r_o = iOpen(_Symbol, InpTimeframe, j), r_c = iClose(_Symbol, InpTimeframe, j);
         double r_l = iLow(_Symbol, InpTimeframe, j),  r_h = iHigh(_Symbol, InpTimeframe, j);
         bool isRed = (r_c < r_o);
         if (dir == 1 ? isRed : !isRed) {
            if (dir == 1) { if (r_c < g_l || r_l < g_l) any_broke = true; }
            else          { if (r_c > g_h || r_h > g_h) any_broke = true; }
            if (found < 30) tmp[found++] = j;
         }
      }
      if (any_broke && found > 0) { for (int k = 0; k < found; k++) reds[k] = tmp[k]; reds_count = found; break; }
   }
   if (reds_count == 0) return "null";

   int ref_shift = reds[0];
   double level = (dir == 1) ? iLow(_Symbol, InpTimeframe, reds[0]) : iHigh(_Symbol, InpTimeframe, reds[0]);
   for (int r = 1; r < reds_count; r++) {
      double v = (dir == 1) ? iLow(_Symbol, InpTimeframe, reds[r]) : iHigh(_Symbol, InpTimeframe, reds[r]);
      if (dir == 1 ? (v < level) : (v > level)) { level = v; ref_shift = reds[r]; }
   }
   return StringFormat(
      "{\"dir\":\"%s\",\"ref_bar_t\":\"%s\",\"ref_high\":%.3f,\"ref_low\":%.3f,\"level\":%.3f,\"setup_bar_t\":\"%s\"}",
      dir == 1 ? "buy" : "sell",
      TimeToString(iTime(_Symbol, InpTimeframe, ref_shift), TIME_DATE|TIME_SECONDS),
      iHigh(_Symbol, InpTimeframe, ref_shift), iLow(_Symbol, InpTimeframe, ref_shift), level,
      TimeToString(iTime(_Symbol, InpTimeframe, 1), TIME_DATE|TIME_SECONDS));
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   string path = InpStateFile;
   int fh = FileOpen(path, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   int n_open = 0;
   double floating = FloatingPnL(n_open);
   double bigness = (InpAvgWinUsd > 0 && floating > 0) ? floating / InpAvgWinUsd : 0.0;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"S3Trader\",\"version\":\"2.40\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,\"watch\":%s,\"open\":%s}",
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots,
      floating, n_open, bigness, InpAvgWinUsd, BuildWatchJson(), BuildOpenJson()));
   FileClose(fh);
}

//── 2R Free Roll: per-position management ──────────────────────────
//   Find this ticket's slot, or create one — capturing the position's CURRENT
//   SL as the original (valid because first sighting precedes any BE move).
//   Assumes the position is already selected via PositionSelectByTicket.
int MngIndex(ulong ticket) {
   for (int i = 0; i < g_mng_count; i++)
      if (g_mng_ticket[i] == ticket) return i;
   int idx = (g_mng_count < 256) ? g_mng_count++ : 0;  // overwrite slot 0 if full (rare)
   g_mng_ticket[idx]    = ticket;
   g_mng_sl0[idx]       = PositionGetDouble(POSITION_SL);
   g_mng_partialed[idx] = false;
   g_mng_peak[idx]      = 0.0;
   return idx;
}

//   Walk this EA's open positions (BUY or SELL) every tick. At +BreakevenR move SL to
//   entry+buffer (firewall). At +PartialR bank a fraction (Income tranche) and
//   ensure the runner is at breakeven. Static TP is left untouched (validated).
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

      int mi = MngIndex(ticket);          // captures original SL on first sight
      double R = MathAbs(entry - g_mng_sl0[mi]);
      if (R <= 0) continue;               // no measurable risk → leave alone

      double prof  = is_buy ? (bid - entry) : (entry - ask);
      double be_sl = NormalizeDouble(is_buy ? entry + InpBEBufferPts
                                            : entry - InpBEBufferPts, _Digits);
      bool can_raise = is_buy ? (cur_sl < be_sl) : (cur_sl == 0.0 || cur_sl > be_sl);

      // TRAILING PROFIT-LOCK (Zee's idea, validated trail_all.py: best-or-tied on all 3 EAs).
      // Once +$Act, ratchet a floor under the peak and bank the instant profit gives back
      // $Give from peak — catches green trades that peak BELOW the old +$1 breakeven and
      // reverse. Keeps the TP (a runner still reaches it). Slides hard SL to entry as a
      // backstop, which also lights the dashboard "profit secured" banner.
      double prof_usd = prof * vol * 100.0;
      if (prof_usd > g_mng_peak[mi]) g_mng_peak[mi] = prof_usd;
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


      // 1. Partial bank at +PartialR (once), then breakeven the remainder.
      if (InpEnablePartial && !g_mng_partialed[mi] && prof >= InpPartialR * R) {
         double close_vol = NormalizeDouble(MathFloor((vol * InpPartialFrac) / step) * step, 2);
         if (close_vol >= vmin && (vol - close_vol) >= vmin) {
            if (g_trade.PositionClosePartial(ticket, close_vol)) {
               g_mng_partialed[mi] = true;
               Log(StringFormat("[2R] Banked %.2f of #%I64u (+%.2fR) — runner=%.2f",
                                close_vol, ticket, prof / R, vol - close_vol));
            }
         } else {
            g_mng_partialed[mi] = true;   // too small to split — don't retry, just BE below
         }
         if (InpEnableBreakeven && can_raise &&
             g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[2R] Breakeven firewall #%I64u SL→%.2f (TP kept %.2f)",
                             ticket, be_sl, cur_tp));
         continue;
      }

      // 2. Plain breakeven at +BreakevenR (fires before PartialR, or if partial off).
      if (InpEnableBreakeven && can_raise && prof >= InpBreakevenR * R) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE] #%I64u SL→%.2f (+%.2fR, TP kept %.2f)",
                             ticket, be_sl, prof / R, cur_tp));
      }
   }
}

//── Floating P&L (this EA's open positions) ────────────────────────
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

//── One-tap GRAB: read shared command id; if newer, close everything ─
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
   if ((TimeCurrent() - g_last_grab_check) < 2) return;   // throttle file IO
   g_last_grab_check = TimeCurrent();
   long id = ReadGrabId();
   if (id <= g_last_grab_id) return;
   g_last_grab_id = id;                                   // mark seen (even if 0 closed)
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

//── EA hooks ────────────────────────────────────────────────────────
int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();   // ignore any pre-existing grab command on attach (no restart-refire)
   Log(StringFormat("S3Trader Init — magic=%d lots=%.2f trendLB=%d retraceLB=%d tpLB=%d grab_base_id=%I64d",
                     InpMagicNumber, InpLots, InpTrendLookback,
                     InpRetraceLookback, InpTPPeakLookback, g_last_grab_id));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log(StringFormat("S3Trader Deinit reason=%d signals=%d entries=%d",
                     reason, g_signals_today, g_entries_today));
}

void OnTick() {
   IsNewDay();
   datetime cur_m5 = iTime(_Symbol, InpTimeframe, 0);
   if (cur_m5 != g_last_m5_time && g_last_m5_time != 0) {
      // A new M5 bar opened — the previous one just closed. Evaluate.
      if (!TryS3BuySignal()) TryS3SellSignal();
   }
   g_last_m5_time = cur_m5;
   ManageOpenPositions();   // 2R Free Roll: breakeven + partial on open trades (every tick)
   CheckGrabCommand();      // honor a one-tap GRAB (close all) from WhatsApp/dashboard
   WriteHeartbeat();
}
