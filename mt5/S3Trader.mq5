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
#property version   "2.10"
#property strict

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
input double InpLots          = 0.09;  // 2026-05-21: FTMO $10k challenge, 3x EV-weighted (S3 0.09/S1 0.06/NSND 0.03). Targets +$500 in ~3 days; realistic worst day ~-$150-200 vs FTMO -$300 daily limit (~50% buffer). Was 0.03 on the $500 Blueberry acct.
input int    InpMagicNumber   = 88003;

input group "── FTMO daily-loss circuit breaker ──"
input double InpDailyLossHalt = 200.0; // halt NEW entries if account EQUITY is down this much today (incl. floating). Account-wide FTMO -$300 daily-limit protection. 0 = off.

input group "── Profit protection: 2R Free Roll (backtest-validated 2026-05-22) ──"
input bool   InpEnableBreakeven = true;  // move SL to breakeven once +InpBreakevenR reached (caps the 'give back to zero' risk). On reattach, applies to ALREADY-OPEN trades too.
input double InpBreakevenR      = 1.0;   // R-multiple that arms breakeven. R = entry − ORIGINAL SL.
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
input int    InpTrendLookback     = 24;   // M5 bars: ~2 hours for trend
input double InpTrendThreshold    = 1.0;  // min price units of move (v2: was 2.0)
input int    InpRetraceLookback   = 30;   // M5 bars to look back for retracement
input int    InpTPPeakLookback    = 10;   // M5 bars for "recent peak" TP (v2: was 30)
input bool   InpRequireH1Fvg      = false;// v2: default OFF — backtest improved without
input int    InpH1FvgLookback     = 50;   // H1 bars (only used if InpRequireH1Fvg)
input bool   InpRequireM5Fvg      = true; // 2026-05-19 walk-forward validated: require a same-TF (M5) bullish FVG tap during retracement. WR 63%->68%, EV/tr $13.78->$26.24 over 12d, holds OOS (~2x EV both halves). H1 was too coarse (7 trades/12d); M5 keeps ~57.
input int    InpM5FvgLookback     = 60;   // M5 bars to scan back for an unfilled bullish FVG (only used if InpRequireM5Fvg)
input double InpMinTPDistPts      = 0.2;  // min TP distance in price-pts (2 pips). BUGFIX 2026-05-17: was 0.5, but backtest uses sl_buf*2=0.20. The stricter 0.5 was rejecting valid trades and cutting backtest P&L by ~50%.
input double InpSLBufferPts       = 2.00; // SL = wicking-green.low − this. 2026-05-18: raised from 0.10 → 2.00 after sweep showed +17% improvement on 12-day backtest (104→100 trades, 56%→63% WR, +$1,184 → +$1,386). Saves single-wick stop-outs like Trade 3 on 2026-05-18.
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
   double now_close   = iClose(_Symbol, PERIOD_M5, from_shift);
   double back_close  = iClose(_Symbol, PERIOD_M5, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (now_close - back_close) > InpTrendThreshold;
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
         double mlow  = iLow(_Symbol, PERIOD_M5, k);
         double mhigh = iHigh(_Symbol, PERIOD_M5, k);
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
      double mlow  = iLow (_Symbol, PERIOD_M5, k);
      double mhigh = iHigh(_Symbol, PERIOD_M5, k);
      // candidate FVG: newer bar at shift i (older than tap bar k), gap between i+2 and i
      for (int i = k + 1; i <= k + InpM5FvgLookback; i++) {
         double older_high = iHigh(_Symbol, PERIOD_M5, i + 2);
         double newer_low  = iLow (_Symbol, PERIOD_M5, i);
         if (newer_low <= older_high) continue;       // no bullish gap
         // unfilled up to the tap bar: no bar between (i-1) and (k+1) has low < older_high
         bool filled = false;
         for (int j = i - 1; j > k; j--) {
            if (iLow(_Symbol, PERIOD_M5, j) < older_high) { filled = true; break; }
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
   if (DailyLossHalted()) return false;   // FTMO daily-loss circuit breaker
   double bo_o = iOpen (_Symbol, PERIOD_M5, 1);
   double bo_h = iHigh (_Symbol, PERIOD_M5, 1);
   double bo_l = iLow  (_Symbol, PERIOD_M5, 1);
   double bo_c = iClose(_Symbol, PERIOD_M5, 1);
   long   bo_v = iVolume(_Symbol, PERIOD_M5, 1);
   datetime bo_t = iTime(_Symbol, PERIOD_M5, 1);

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

   // 3. v2: find retracement = "reds that broke the last green candle's low"
   //   Walk back looking for a green whose low got broken by subsequent reds.
   //   The reds AFTER that green (and before bo) are the retracement reds.
   int reds[30];
   int reds_count = 0;
   int max_red_shift = 1;
   for (int back_g = 2; back_g <= 1 + InpRetraceLookback; back_g++) {
      double g_o = iOpen (_Symbol, PERIOD_M5, back_g);
      double g_c = iClose(_Symbol, PERIOD_M5, back_g);
      double g_l = iLow  (_Symbol, PERIOD_M5, back_g);
      if (g_c <= g_o) continue;          // not green — keep looking
      // Found a candidate green. Check subsequent reds (shifts back_g-1 down to 2)
      // for any whose low/close went BELOW g_l.
      bool any_broke = false;
      int  found_reds = 0;
      int  tmp_reds[30];
      int  tmp_max_shift = 1;
      for (int j = back_g - 1; j >= 2; j--) {
         double r_o = iOpen (_Symbol, PERIOD_M5, j);
         double r_c = iClose(_Symbol, PERIOD_M5, j);
         double r_l = iLow  (_Symbol, PERIOD_M5, j);
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
      double r_l = iLow   (_Symbol, PERIOD_M5, rs);
      long   r_v = iVolume(_Symbol, PERIOD_M5, rs);
      if (bo_l >= r_l)   continue;      // didn't wick below
      if (bo_c <= r_l)   continue;      // didn't close back inside
      if (bo_v <= r_v)   continue;      // need higher green vol
      matching_red_shift = rs;
      matching_red_t = iTime(_Symbol, PERIOD_M5, rs);
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
      double h = iHigh(_Symbol, PERIOD_M5, j);
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
   double red_l_log = iLow(_Symbol, PERIOD_M5, matching_red_shift);
   long   red_v_log = iVolume(_Symbol, PERIOD_M5, matching_red_shift);
   LogDecisionCsv(bo_t, bo_c, bo_l, bo_v, matching_red_t, red_l_log, red_v_log,
                  ask, sl, tp, actual_fill, ticket);
   return true;
}

//── CSV decision logger (one row per fired signal) ─────────────────
//   Joined with turtle_fills.csv by ticket → live vs backtest reconciler.
void LogDecisionCsv(datetime bo_t, double bo_c, double bo_l, long bo_v,
                    datetime red_t, double red_l, double red_v,
                    double intended_entry, double sl, double tp,
                    double actual_fill, ulong ticket) {
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
      "buy",
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
      "{\"ea\":\"S3Trader\",\"version\":\"2.20\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f}",
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots,
      floating, n_open, bigness, InpAvgWinUsd));
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
   return idx;
}

//   Walk this EA's open BUY positions every tick. At +BreakevenR move SL to
//   entry+buffer (firewall). At +PartialR bank a fraction (Income tranche) and
//   ensure the runner is at breakeven. Static TP is left untouched (validated).
void ManageOpenPositions() {
   if (!InpEnableBreakeven && !InpEnablePartial) return;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (step <= 0) step = 0.01;

   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue; // S3 buy-only

      double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur_sl = PositionGetDouble(POSITION_SL);
      double cur_tp = PositionGetDouble(POSITION_TP);
      double vol    = PositionGetDouble(POSITION_VOLUME);

      int mi = MngIndex(ticket);          // captures original SL on first sight
      double R = entry - g_mng_sl0[mi];
      if (R <= 0) continue;               // no measurable risk → leave alone

      double be_sl = NormalizeDouble(entry + InpBEBufferPts, _Digits);

      // 1. Partial bank at +PartialR (once), then breakeven the remainder.
      if (InpEnablePartial && !g_mng_partialed[mi] && bid >= entry + InpPartialR * R) {
         double close_vol = NormalizeDouble(MathFloor((vol * InpPartialFrac) / step) * step, 2);
         if (close_vol >= vmin && (vol - close_vol) >= vmin) {
            if (g_trade.PositionClosePartial(ticket, close_vol)) {
               g_mng_partialed[mi] = true;
               Log(StringFormat("[2R] Banked %.2f of #%I64u @ bid=%.2f (+%.2fR) — runner=%.2f",
                                close_vol, ticket, bid, (bid - entry) / R, vol - close_vol));
            }
         } else {
            g_mng_partialed[mi] = true;   // too small to split — don't retry, just BE below
         }
         if (InpEnableBreakeven && cur_sl < be_sl &&
             g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[2R] Breakeven firewall #%I64u SL→%.2f (TP kept %.2f)",
                             ticket, be_sl, cur_tp));
         continue;
      }

      // 2. Plain breakeven at +BreakevenR (fires before PartialR, or if partial off).
      if (InpEnableBreakeven && cur_sl < be_sl && bid >= entry + InpBreakevenR * R) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE] #%I64u SL→%.2f (+%.2fR, TP kept %.2f)",
                             ticket, be_sl, (bid - entry) / R, cur_tp));
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
   datetime cur_m5 = iTime(_Symbol, PERIOD_M5, 0);
   if (cur_m5 != g_last_m5_time && g_last_m5_time != 0) {
      // A new M5 bar opened — the previous one just closed. Evaluate.
      TryS3BuySignal();
   }
   g_last_m5_time = cur_m5;
   ManageOpenPositions();   // 2R Free Roll: breakeven + partial on open trades (every tick)
   CheckGrabCommand();      // honor a one-tap GRAB (close all) from WhatsApp/dashboard
   WriteHeartbeat();
}
