//+------------------------------------------------------------------+
//| S1Trader.mq5 — Setup 1 "Ultra-High-Volume Breakout" executor     |
//|                                                                  |
//| v2.0 (2026-05-19) — walk-forward validated config:               |
//|   • BUY+SELL (symmetric), SL=$2.00, TP=$7.5 pts, H1 FVG req      |
//|   • TRAIN (first 6d): 20 trades, 75% WR, +$552 @ 0.10 lots       |
//|   • TEST  (last 6d):  12 trades, 67% WR, +$193 @ 0.10 lots       |
//|   • TEST EV/trade: +$16.12 (positive OOS — passes walk-forward)  |
//|   • Projection @ 0.02 lots: ~$6.40/day                           |
//|                                                                  |
//| Curve-fit warning: 4 of 5 top in-sample configs FAILED OOS.      |
//| Only this one (with wider SL=$2) survived. Wider SL absorbs      |
//| noise that tighter configs get stopped out by — same lesson      |
//| we learned with S3 (0.10 → 2.00).                                |
//|                                                                  |
//| STRATEGY (BUY side; SELL is symmetric):                          |
//|   1. H1: identify unfilled bullish Fair Value Gap (3-bar gap up) |
//|   2. M5: price retraces and TAPS the H1 FVG                      |
//|   3. In retracement, find the RED M5 candle with HIGHEST volume  |
//|      (the UHV / climactic action bar)                            |
//|   4. Wait for a candle to SWEEP the UHV red's low (wick below)   |
//|   5. Wait for a GREEN M5 candle to CLOSE ABOVE the UHV red's high|
//|      and to OPEN at-or-below it (fresh transition, not continuation)|
//|   6. ENTRY: market BUY at the green breakout's close             |
//|   7. SL: UHV red's low − InpSLBufferPts                          |
//|   8. TP: entry + InpTPPoints                                     |
//|   9. PRE-REQ: 2-hour M5 uptrend (close[now] − close[24 bars] > 2)|
//|   SELL: same but mirrored — UHV GREEN, sweep ABOVE, red breakout |
//|         down through UHV.low, downtrend required, bearish H1 FVG |
//|                                                                  |
//| Independent of S3Trader (Magic 88003); A/B comparable.           |
//| Magic 88004.                                                     |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — Setup 1 UHV Breakout v2"
#property version   "2.40"
#property strict

// ╔══════════════════════════════════════════════════════════════════╗
// ║  📄 STRATEGY DOCUMENTATION: docs/S1_STRATEGY.md                 ║
// ║  Contains: full strategy logic, backtest results, parameter     ║
// ║  rationale, walk-forward validation, and change history.        ║
// ║  READ THAT FILE FIRST before modifying this EA.                 ║
// ╚══════════════════════════════════════════════════════════════════╝

// v2.10 (2026-05-22): "2R Free Roll" management code added for parity with S3/NSND,
// but DEFAULT OFF — backtest (backtest_exit_protocols_multi.py, S1 deployed signals,
// 13 real-tick days, n=34) showed it is STRUCTURALLY INERT on S1: the SL sits at the
// UHV-red low (often $5-15 below entry), so 1R is usually wider than the $7.5 TP and
// breakeven/partial can never arm before TP resolves — every policy was byte-identical
// to baseline (+$431.8). Left as a toggle in case S1's TP/SL geometry is widened later.

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.01;     // 2026-05-27: Shano Exness $126 account (was 0.06 FTMO-era — that'd be ~$30-90 risk/trade = account-ending on $126). 0.01 = ~$5-15/trade.
input int    InpMagicNumber   = 88004;
input double InpDailyLossHalt = 50.0;   // 2026-05-27 Shano $126 acct: ~20% daily-loss cap — halt NEW entries if equity is down this much today (incl. floating). Was FTMO-era $200/$50. Tighten to 15 for stricter. 0=off.

input group "── Profit protection: 2R Free Roll (backtest 2026-05-22) ──"
input bool   InpEnableBreakeven = false; // OFF — backtest showed INERT on S1 (SL at UHV-red low is usually wider than the $7.5 TP, so +1R can't arm before TP; identical to baseline +$431.8). Enable only if you widen TP / tighten SL.
input double InpBreakevenR      = 1.0;   // R-multiple that arms breakeven. R = entry − ORIGINAL SL.
input bool   InpEnablePartial   = false; // OFF — inert on S1 for the same geometry reason.
input double InpPartialR        = 1.5;
input double InpPartialFrac     = 0.5;
input double InpBEBufferPts     = 0.30;  // SL set this far beyond entry (price units) to cover spread/swap.

input group "── Human profit-pulse + one-tap GRAB ──"
input bool   InpEnableGrab = true;       // honor a GRAB command (close ALL this EA's positions at market) from WhatsApp/dashboard one tap.
input double InpAvgWinUsd  = 40.0;       // reference avg winning trade ($) for the heartbeat 'bigness' read (S1 ~$44 avg win @0.06).
input string InpGrabFile   = "grab_command.txt"; // shared command file (epoch id). EA grabs on a NEWER id than last seen.

input group "── Sides ──"
input bool   InpDoBuys        = true;     // BUY side enabled (UHV red + bullish FVG)
input bool   InpDoSells       = true;     // 2026-05-19: SELL side enabled — adds +$243/12d in walk-forward train (+/-$0 OOS net)

input group "── Detection ──"
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M1;  // 2026-05-27: DEFAULT M1 — validated far stronger (644 tr/19d, 62% WR, +$3088 NET after cost, 5/5 splits OOS+, EV +$4.79/tr) vs M5 (+$877). Set PERIOD_M5 + InpTrendThreshold=7.0 to revert.
input int    InpTrendLookback     = 24;   // bars (M1 default: ~24min; M5: ~2h)
input double InpTrendThreshold    = 2.0;  // 2026-05-27: 2.0 for the M1 default (min move over 24 M1 bars). On M5 use 7.0 (verify_thorough.py: 7/7 splits, +$629->+$745, WR 69->76%).
input int    InpRetraceLookback   = 15;   // M5 bars searched for UHV red/green
input bool   InpRequireH1Fvg      = false; // 2026-05-27: DISABLED. The +$2166 backtest ran without H1 FVG; stacking it with BigSpread killed all signals. Re-enable after live data proves it helps.
input int    InpH1FvgLookback     = 50;   // H1 bars searched for unfilled FVG (only used if InpRequireH1Fvg)
input bool   InpRequireBigSpread  = false; // 2026-05-27: DISABLED. Was blocking 100% of live trades (0 entries in 5 days). The WF validation was on a model that didn't include this filter. Re-enable only after live calibration.
input double InpBigSpreadMult     = 1.3;  // UHV bar range must be >= this x avg range of prior 10 M5 bars
input int    InpSpreadAvgBars     = 10;   // bars used for the avg-range baseline
input double InpSLBufferPts       = 2.00; // 2026-05-19: walk-forward winner. Was 0.10, but tighter SL configs all BROKE OOS (curve-fit). Wider SL absorbs noise.

input group "── Exit ──"
input double InpTPPoints          = 3.0;  // 2026-05-27: M1 quick-scalp (=$3 @0.01). s1_m1_exits.py: book+$3 beats ride-to-7.5 (+$3431 vs +$3362, OOS +$1094 vs +$1018) and kills give-backs. On M5 use 7.5 (its WF winner).

input group "── Logging ──"
input bool   InpVerbose       = true;
input string InpLogPrefix     = "S1";
input string InpStateFile     = "s1_trader_state.json";
input int    InpHeartbeatSec  = 5;

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
datetime g_last_m5_time = 0;
datetime g_last_signal_t = 0;
datetime g_last_heartbeat = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_today_day = 0;

//── Helpers ─────────────────────────────────────────────────────────
void Log(string msg) {
   if (!InpVerbose) return;
   PrintFormat("[%s] %s", InpLogPrefix, msg);
}

double g_day_start_equity = 0;

//── Per-position management state (2R Free Roll) ───────────────────
ulong  g_mng_ticket[256];
double g_mng_sl0[256];
bool   g_mng_partialed[256];
int    g_mng_count = 0;

//── One-tap GRAB state ──────────────────────────────────────────────
long     g_last_grab_id = 0;
datetime g_last_grab_check = 0;

//── Diagnostic: setups that passed every filter EXCEPT the H1-FVG gate today.
//   If this is >0 while entries=0, the H1-FVG check is the live blocker; if it's
//   0, no qualifying setups occurred (rarity, not a bug). Reset daily.
int g_reached_late = 0;

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day;
      g_signals_today = 0;
      g_entries_today = 0;
      g_reached_late = 0;
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

bool IsUptrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (now_close - back_close) > InpTrendThreshold;
}

// Average M5 candle range over the N bars BEFORE the given shift (older bars).
double AvgRangeM5(int from_shift, int n) {
   double sum = 0; int cnt = 0;
   for (int j = from_shift + 1; j <= from_shift + n; j++) {
      sum += iHigh(_Symbol, InpTimeframe, j) - iLow(_Symbol, InpTimeframe, j);
      cnt++;
   }
   return (cnt > 0) ? sum / cnt : 0.0;
}

// Teacher's "big-spread climax bar" filter: the UHV bar's range must be a
// large candle vs the recent average. Walk-forward validated 2026-05-19.
bool IsBigSpreadClimax(int uhv_shift) {
   if (!InpRequireBigSpread) return true;
   double rng = iHigh(_Symbol, InpTimeframe, uhv_shift) - iLow(_Symbol, InpTimeframe, uhv_shift);
   double avg = AvgRangeM5(uhv_shift, InpSpreadAvgBars);
   if (avg <= 0) return false;
   return rng >= InpBigSpreadMult * avg;
}

bool IsDowntrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (back_close - now_close) > InpTrendThreshold;
}

// Bullish H1 FVG = older_high < newer_low (a gap up). Tapped if any M5 bar in
// the retracement has range overlapping the gap zone.
bool H1FvgTappedDuringRetracement(int retrace_back_shift) {
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_high = iHigh(_Symbol, PERIOD_H1, i + 2);
      double newer_low  = iLow (_Symbol, PERIOD_H1, i);
      if (newer_low <= older_high) continue;
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iLow(_Symbol, PERIOD_H1, j) < older_high) {
            filled = true; break;
         }
      }
      if (filled) continue;
      for (int k = 1; k <= retrace_back_shift; k++) {
         double mlow  = iLow(_Symbol, InpTimeframe, k);
         double mhigh = iHigh(_Symbol, InpTimeframe, k);
         if (mlow <= newer_low && mhigh >= older_high) return true;
      }
   }
   return false;
}

// Bearish H1 FVG = older_low > newer_high (a gap down). Tapped if any M5 bar
// in the retracement has range overlapping the gap zone. "Filled" = a later
// H1 bar's high traded back above older_low.
bool H1BearFvgTappedDuringRetracement(int retrace_back_shift) {
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_low  = iLow (_Symbol, PERIOD_H1, i + 2);
      double newer_high = iHigh(_Symbol, PERIOD_H1, i);
      if (older_low <= newer_high) continue;
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iHigh(_Symbol, PERIOD_H1, j) > older_low) {
            filled = true; break;
         }
      }
      if (filled) continue;
      for (int k = 1; k <= retrace_back_shift; k++) {
         double mlow  = iLow (_Symbol, InpTimeframe, k);
         double mhigh = iHigh(_Symbol, InpTimeframe, k);
         // Bear FVG zone is [newer_high, older_low]. Overlap: m5.low<=older_low && m5.high>=newer_high
         if (mlow <= older_low && mhigh >= newer_high) return true;
      }
   }
   return false;
}

//── S1 BUY signal check on M5 bar at shift 1 (just-closed) ─────────
bool TryS1BuySignal() {
   if (!InpDoBuys) return false;
   if (DailyLossHalted()) return false;   // FTMO daily-loss circuit breaker
   double bo_o = iOpen (_Symbol, InpTimeframe, 1);
   double bo_h = iHigh (_Symbol, InpTimeframe, 1);
   double bo_l = iLow  (_Symbol, InpTimeframe, 1);
   double bo_c = iClose(_Symbol, InpTimeframe, 1);
   datetime bo_t = iTime(_Symbol, InpTimeframe, 1);

   if (bo_t == g_last_signal_t) return false;

   // 1. Must be green
   if (bo_c <= bo_o) return false;
   // 2. Uptrend
   if (!IsUptrendM5(1)) return false;

   // 3. Walk back collecting retracement reds in last InpRetraceLookback bars
   //    BUGFIX 2026-05-19: was stopping early on swing-high greens, which
   //    diverged from Python mirror. Now matches mirror exactly: just
   //    collect all reds in the lookback window.
   int reds[15];
   int reds_count = 0;
   int max_red_shift = 1;
   for (int j = 2; j <= 1 + InpRetraceLookback; j++) {
      double r_o = iOpen (_Symbol, InpTimeframe, j);
      double r_c = iClose(_Symbol, InpTimeframe, j);
      if (r_c < r_o) {
         if (reds_count < 15) {
            reds[reds_count++] = j;
            max_red_shift = j;
         }
      }
   }
   if (reds_count == 0) return false;

   // 4. UHV red = highest-volume red in the retracement
   int uhv_shift = reds[0];
   long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
   for (int r = 1; r < reds_count; r++) {
      long v = iVolume(_Symbol, InpTimeframe, reds[r]);
      if (v > uhv_vol) {
         uhv_vol = v;
         uhv_shift = reds[r];
      }
   }
   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);

   // 4b. TEACHER (VSA Selling-Climax): climax bar must be a BIG-SPREAD candle.
   if (!IsBigSpreadClimax(uhv_shift)) return false;

   // 5. Breakout: bo.close > UHV.high, bo.open <= UHV.high (fresh transition)
   if (bo_c <= uhv_h) return false;
   if (bo_o >  uhv_h) return false;

   // 6. Sweep: some M5 bar between (uhv_shift) and 1 has low < uhv_l
   //    (uhv_shift is a higher shift = older bar. shift goes 1..uhv_shift-1)
   bool swept = false;
   for (int k = uhv_shift - 1; k >= 1; k--) {
      if (iLow(_Symbol, InpTimeframe, k) < uhv_l) {
         swept = true; break;
      }
   }
   if (!swept) return false;

   g_reached_late++;   // diagnostic: passed all filters except the H1-FVG gate
   // 7. H1 FVG tap during retracement (optional — default OFF since 2026-05-27)
   if (InpRequireH1Fvg && !H1FvgTappedDuringRetracement(max_red_shift)) return false;

   // 8. Compute SL/TP/entry
   double sl  = uhv_l - InpSLBufferPts;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tp  = ask + InpTPPoints;

   g_signals_today++;
   Log(StringFormat("S1 BUY signal — entry=%.2f sl=%.2f tp=%.2f uhv_shift=%d (vol=%d) R:R=%.2f",
                     ask, sl, tp, uhv_shift, (int)uhv_vol,
                     InpTPPoints / MathMax(0.0001, ask - sl)));

   // 9. Fire
   if (!g_trade.Buy(InpLots, _Symbol, 0, sl, tp, "S1_buy")) {
      Log(StringFormat("[ERR] Buy failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_signal_t = bo_t;
   Log(StringFormat("[FILLED] ticket=%d", g_trade.ResultOrder()));
   return true;
}

//── S1 SELL signal check on M5 bar at shift 1 (just-closed) ─────────
//   Symmetric mirror of TryS1BuySignal: UHV GREEN in retracement,
//   sweep ABOVE UHV.high, red breakout closes BELOW UHV.low (open at
//   or above UHV.low — fresh transition). Bearish H1 FVG required.
bool TryS1SellSignal() {
   if (!InpDoSells) return false;
   if (DailyLossHalted()) return false;   // FTMO daily-loss circuit breaker
   double bo_o = iOpen (_Symbol, InpTimeframe, 1);
   double bo_h = iHigh (_Symbol, InpTimeframe, 1);
   double bo_l = iLow  (_Symbol, InpTimeframe, 1);
   double bo_c = iClose(_Symbol, InpTimeframe, 1);
   datetime bo_t = iTime(_Symbol, InpTimeframe, 1);

   if (bo_t == g_last_signal_t) return false;

   // 1. Must be red
   if (bo_c >= bo_o) return false;
   // 2. Downtrend
   if (!IsDowntrendM5(1)) return false;

   // 3. Walk back collecting retracement greens in last InpRetraceLookback bars
   //    BUGFIX 2026-05-19: was stopping early on swing-low reds, which
   //    diverged from Python mirror. Now matches mirror exactly.
   int greens[15];
   int greens_count = 0;
   int max_green_shift = 1;
   for (int j = 2; j <= 1 + InpRetraceLookback; j++) {
      double g_o = iOpen (_Symbol, InpTimeframe, j);
      double g_c = iClose(_Symbol, InpTimeframe, j);
      if (g_c > g_o) {
         if (greens_count < 15) {
            greens[greens_count++] = j;
            max_green_shift = j;
         }
      }
   }
   if (greens_count == 0) return false;

   // 4. UHV green = highest-volume green in the retracement
   int uhv_shift = greens[0];
   long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
   for (int r = 1; r < greens_count; r++) {
      long v = iVolume(_Symbol, InpTimeframe, greens[r]);
      if (v > uhv_vol) {
         uhv_vol = v;
         uhv_shift = greens[r];
      }
   }
   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);

   // 4b. TEACHER (VSA Buying-Climax): climax bar must be a BIG-SPREAD candle.
   if (!IsBigSpreadClimax(uhv_shift)) return false;

   // 5. Breakdown: bo.close < UHV.low, bo.open >= UHV.low (fresh transition)
   if (bo_c >= uhv_l) return false;
   if (bo_o <  uhv_l) return false;

   // 6. Sweep: some M5 bar between (uhv_shift) and 1 has high > uhv_h
   bool swept = false;
   for (int k = uhv_shift - 1; k >= 1; k--) {
      if (iHigh(_Symbol, InpTimeframe, k) > uhv_h) {
         swept = true; break;
      }
   }
   if (!swept) return false;

   g_reached_late++;   // diagnostic: passed all filters except the H1-FVG gate
   // 7. Bearish H1 FVG tap during retracement (optional — default OFF since 2026-05-27)
   if (InpRequireH1Fvg && !H1BearFvgTappedDuringRetracement(max_green_shift)) return false;

   // 8. Compute SL/TP/entry
   double sl  = uhv_h + InpSLBufferPts;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double tp  = bid - InpTPPoints;
   if (tp <= 0) return false;

   g_signals_today++;
   Log(StringFormat("S1 SELL signal — entry=%.2f sl=%.2f tp=%.2f uhv_shift=%d (vol=%d) R:R=%.2f",
                     bid, sl, tp, uhv_shift, (int)uhv_vol,
                     InpTPPoints / MathMax(0.0001, sl - bid)));

   if (!g_trade.Sell(InpLots, _Symbol, 0, sl, tp, "S1_sell")) {
      Log(StringFormat("[ERR] Sell failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_signal_t = bo_t;
   Log(StringFormat("[FILLED] ticket=%d", g_trade.ResultOrder()));
   return true;
}

//── State JSON heartbeat ─────────────────────────────────────────
// READ-ONLY: the setup S1 is currently watching, for the dashboard live chart.
// Mirrors the buy/sell detection (trend → highest-volume retracement UHV bar →
// the price level a breakout must clear). Touches NO trade logic; pure read+report.
string BuildWatchJson() {
   int dir = 0;
   if (InpDoBuys && IsUptrendM5(1)) dir = 1;          // watching for a BUY (UHV red)
   else if (InpDoSells && IsDowntrendM5(1)) dir = -1; // watching for a SELL (UHV green)
   if (dir == 0) return "null";

   int uhv_shift = -1; long uhv_vol = -1;
   for (int j = 2; j <= 1 + InpRetraceLookback; j++) {
      double o = iOpen(_Symbol, InpTimeframe, j), c = iClose(_Symbol, InpTimeframe, j);
      bool match = (dir == 1) ? (c < o) : (c > o);     // red for buy, green for sell
      if (!match) continue;
      long v = iVolume(_Symbol, InpTimeframe, j);
      if (v > uhv_vol) { uhv_vol = v; uhv_shift = j; }
   }
   if (uhv_shift < 0) return "null";

   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
   return StringFormat(
      "{\"dir\":\"%s\",\"ref_bar_t\":\"%s\",\"ref_high\":%.3f,\"ref_low\":%.3f,"
      "\"level\":%.3f,\"setup_bar_t\":\"%s\"}",
      dir == 1 ? "buy" : "sell",
      TimeToString(iTime(_Symbol, InpTimeframe, uhv_shift), TIME_DATE|TIME_SECONDS),
      uhv_h, uhv_l, (dir == 1 ? uhv_h : uhv_l),
      TimeToString(iTime(_Symbol, InpTimeframe, 1), TIME_DATE|TIME_SECONDS));
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
      "{\"ea\":\"S1Trader\",\"version\":\"2.40\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,\"late_setups\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"tp_points\":%.2f,\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,"
      "\"watch\":%s,\"open\":%s}",
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today, g_reached_late,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots, InpTPPoints,
      floating, n_open, bigness, InpAvgWinUsd, BuildWatchJson(), BuildOpenJson()));
   FileClose(fh);
}

//── EA hooks ────────────────────────────────────────────────────────
int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();   // ignore any pre-existing grab command on attach
   Log(StringFormat("S1Trader Init — magic=%d lots=%.2f TP=%.2fpts trendLB=%d retraceLB=%d grab_base=%I64d",
                     InpMagicNumber, InpLots, InpTPPoints,
                     InpTrendLookback, InpRetraceLookback, g_last_grab_id));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   Log(StringFormat("S1Trader Deinit reason=%d signals=%d entries=%d",
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
   return idx;
}

//   Walk this EA's open positions (BUY or SELL) each tick. At +BreakevenR move SL
//   to breakeven. Optional partial at +PartialR. Static TP untouched. (Default OFF
//   on S1 — see header note; inert because 1R is usually wider than the $7.5 TP.)
void ManageOpenPositions() {
   if (!InpEnableBreakeven && !InpEnablePartial) return;
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

      double prof  = is_buy ? (bid - entry) : (entry - ask);
      double be_sl = NormalizeDouble(is_buy ? entry + InpBEBufferPts
                                            : entry - InpBEBufferPts, _Digits);
      bool can_raise = is_buy ? (cur_sl < be_sl) : (cur_sl == 0.0 || cur_sl > be_sl);

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

      if (InpEnableBreakeven && can_raise && prof >= InpBreakevenR * R) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE] #%I64u SL→%.2f (+%.2fR, TP kept %.2f)",
                             ticket, be_sl, prof / R, cur_tp));
      }
   }
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
      if (n > 0) arr += ",";
      arr += StringFormat("{\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.2f,\"cur\":%.2f,\"pnl\":%.2f,\"sl\":%.2f,\"tp\":%.2f}",
                          buy ? "BUY" : "SELL", PositionGetDouble(POSITION_VOLUME),
                          PositionGetDouble(POSITION_PRICE_OPEN), PositionGetDouble(POSITION_PRICE_CURRENT),
                          PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP),
                          PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP));
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
   datetime cur_m5 = iTime(_Symbol, InpTimeframe, 0);
   if (cur_m5 != g_last_m5_time && g_last_m5_time != 0) {
      // BUY first; if it fires, SELL on same bar is blocked by dedup (g_last_signal_t).
      if (!TryS1BuySignal()) TryS1SellSignal();
   }
   g_last_m5_time = cur_m5;
   ManageOpenPositions();   // 2R Free Roll (default off on S1 — see header)
   CheckGrabCommand();      // one-tap GRAB (close all) from WhatsApp/dashboard
   WriteHeartbeat();
}

