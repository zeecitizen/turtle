//+------------------------------------------------------------------+
//|  UhvNativeTrader.mq5                                             |
//|  Native MT5 EA for UHV breakout strategy on XAUUSD              |
//|                                                                  |
//|  WHY:  Webhook latency (TV->PineConnector->MT5 = ~$1.39 avg     |
//|        slippage) destroys 3-5pip target profitability. Manual    |
//|        execution is 98W/1L; webhook automation is -$515.         |
//|                                                                  |
//|  HOW:  Move detection + entry + exit ENTIRELY inside MT5.        |
//|        Tick-level OnTick() loop. Virtual TP/SL stored in EA RAM. |
//|        Stealth exits invisible to broker (anti-stop-hunt).       |
//|                                                                  |
//|  STATUS:  SKELETON — compiles and runs in DRY_RUN mode only.     |
//|           Detection logic, virtual exits, risk gates all stubbed.|
//|           Fill in incrementally. See UhvNativeTrader.md for plan.|
//|                                                                  |
//|  Magic:  84099  (distinct from 84001/2/3 used by Python sniper)  |
//|                                                                  |
//|  Refer: UhvNativeTrader.md (design doc — read before editing)    |
//|         ../UHV Strategy Automation_ Stop Orders.pdf (latency rpt)|
//+------------------------------------------------------------------+
#property copyright "Turtle Trader by M. Zeeshan / Claude Code 2026-05-09"
#property version   "1.00"
#property description "Native MT5 UHV breakout EA — tick-level + virtual TP/SL"
#property strict

#include <Trade\Trade.mqh>

CTrade g_trade;

//+------------------------------------------------------------------+
//| Inputs (see UhvNativeTrader.md §4)                               |
//+------------------------------------------------------------------+
input group "=== Master Control ==="
input bool   InpEnabled        = true;        // Enable EA
input bool   InpDryRun         = true;        // DRY-RUN: log signals, do NOT actually OrderSend
input string InpSymbol         = "XAUUSD";    // Symbol filter (must match attached chart)
input int    InpMagicNumber    = 84099;       // Distinct magic vs Python sniper (84001/2/3)

input group "=== UHV Detection ==="
input int    InpUhvLookback    = 20;          // Find highest-vol bar in last N closed M1 bars
input int    InpUhvMaxAgeBars  = 10;          // Discard UHV anchors older than this many bars
input double InpMinBodyPct     = 0.50;        // Body must be ≥ X% of candle range (0 = disabled)
input bool   InpRequireBgContext = false;     // Background red bars (long) / green (short) before UHV — NOT IMPLEMENTED in v0.10

input group "=== Entry ==="
input double InpLots           = 0.10;        // Fixed lot size (0.01 for real-$500 cap, 0.10 demo)
input double InpPreOffsetPts   = 1.0;         // Fire X points BEFORE the breakout level
input bool   InpRequireBodyClose = true;      // Confirm with body close past level (vs wick only)
input int    InpMinSpacingSec  = 60;          // Minimum seconds between entries

input group "=== Exit (Virtual / Stealth) ==="
input double InpVirtualTpUsd   = 3.0;         // Close at first +$X profit (fixed-TP mode)
input double InpVirtualSlUsd   = 15.0;        // Hard kill at -$X loss (catastrophic stop, both modes)
input int    InpKillTimerSec   = 5;           // Max hold time (sec) — fixed-TP mode only; trailing uses InpTrailMaxHoldSec
input bool   InpUseTrailing    = false;       // Trail-after-peak: ignore InpVirtualTpUsd, use trigger+drop+max-hold instead
input double InpTrailTriggerUsd = 8.0;        // Trailing only: arm trail after profit reaches +$X (trail mode)
input double InpTrailDropUsd    = 2.0;        // Trailing only: exit when peak drops by $X from peak (trail mode)
input int    InpTrailMaxHoldSec = 60;         // Trailing only: max hold time before time-out (longer than fixed-TP)
input int    InpTrailScratchSec = 30;         // Trailing only: scratch-exit if not yet positive after N sec

input group "=== Risk Gates ==="
input double InpMaxSpreadPts   = 30.0;        // Reject entry if spread > X points (XAUUSD: 1pt = $0.01)
input bool   InpSkipSydney     = true;        // Block 00:00-06:00 GMT (memory: 0% WR Sydney session)
input double InpDailyLossUsd   = 100.0;       // Halt for the day at -$X realized
input bool   InpRespectSniperLock = true;     // Honour 5-min lockout file written by auto_uhv_trader.py (prevent double-fire)
input string InpSniperLockFile = "C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\.uhv_native_last_fire.json";

input group "=== Sizing (advanced) ==="
input double InpRiskPctPerTrade = 0.0;        // 0 = use fixed InpLots; >0 = risk this % of equity per trade (e.g. 0.5 = 0.5%). Validate first.
input double InpMaxLots         = 1.0;        // Cap on any computed lot size (safety)

input group "=== Diagnostics ==="
input bool   InpLogToCsv       = true;        // Write fills + exits to MQL5/Files/uhv_native_trader.csv
input bool   InpAnnotateChart  = true;        // Draw entry/exit arrows on chart
input bool   InpVerbose        = false;       // Print() on every tick decision (DEBUG ONLY — noisy)

//+------------------------------------------------------------------+
//| Data structures                                                  |
//+------------------------------------------------------------------+
struct VirtualExit {
   ulong              ticket;        // position ticket from OrderSend result
   double             entryPrice;
   double             virtualSL;     // hard catastrophic stop ($-side)
   double             virtualTP;     // fixed-TP target (used when InpUseTrailing=false)
   double             peakPnlUsd;    // running peak P&L since open (for trailing mode)
   bool               trailArmed;    // trailing only: true once peakPnlUsd >= InpTrailTriggerUsd
   bool               hasBeenPositive; // any tick where cur P&L > 0 (for trailing scratch logic)
   datetime           openedAt;
   ENUM_POSITION_TYPE type;
   double             lots;          // captured at entry (for accurate $-to-points conversion later)
};

struct UhvSignal {
   bool   valid;
   bool   isLong;
   double triggerLevel;
   double currentPrice;
   double uhvHigh;
   double uhvLow;
};

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
VirtualExit   g_active[];           // currently-active positions awaiting virtual exits
datetime      g_last_entry_ts = 0;  // last entry timestamp (for InpMinSpacingSec)
double        g_today_pl      = 0.0;
int           g_today_dom     = -1; // dayofmonth for daily P&L reset
int           g_csv_handle    = INVALID_HANDLE;
int           g_signals_today = 0;
int           g_fills_today   = 0;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit() {
   Print("[UhvNative] init  symbol=", _Symbol, "  dryrun=", InpDryRun, "  magic=", InpMagicNumber);

   if (_Symbol != InpSymbol) {
      Print("[UhvNative] WARN: chart symbol (", _Symbol, ") != InpSymbol (", InpSymbol, ")");
   }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(30);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   ArrayResize(g_active, 0);

   // Verify enough M1 history is loaded for UHV detection
   int bars_avail = Bars(_Symbol, PERIOD_M1);
   if (bars_avail < InpUhvLookback + 5) {
      Print("[UhvNative] WARN: only ", bars_avail, " M1 bars loaded — need ", InpUhvLookback + 5, ". Wait for history sync.");
   }

   if (InpLogToCsv) OpenCsvLog();
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   if (g_csv_handle != INVALID_HANDLE) FileClose(g_csv_handle);
   Print("[UhvNative] deinit reason=", reason);
}

//+------------------------------------------------------------------+
//| OnTick — main entry point, runs on every quote                  |
//+------------------------------------------------------------------+
void OnTick() {
   // 1. Daily P&L reset check
   ResetDailyStateIfNewDay();

   // 2. Diagnostic heartbeat (1/min) — visibility into why signals fire or don't
   DiagnosticHeartbeat();

   // 3. Walk virtual exits FIRST (existing positions take priority over new entries)
   if (ArraySize(g_active) > 0) WalkVirtualExits();

   // 4. Risk gates — abort if any closed
   if (!RiskGatesOpen()) return;

   // 4. Detection (uses iHigh/iLow/iVolume series — no manual buffer needed)
   UhvSignal sig = DetectBreakout();
   if (!sig.valid) return;

   // 5. Min-spacing gate
   if (TimeCurrent() - g_last_entry_ts < InpMinSpacingSec) return;

   // 6. Fire (or dry-run log)
   g_signals_today++;
   if (InpDryRun) {
      LogDryRunSignal(sig);
      g_last_entry_ts = TimeCurrent();   // dry-run still respects spacing for honest sim
   } else {
      if (FireEntry(sig)) g_fills_today++;
   }
}

//+------------------------------------------------------------------+
//| Bar access — uses MT5 series functions directly (no buffer)      |
//| Shift 0 = in-progress bar, shift 1..N = closed bars              |
//+------------------------------------------------------------------+
// (No BootstrapBarBuffer / UpdateInProgressBar / FinalizePendingBar needed —
//  iHigh/iLow/iOpen/iClose/iVolume/iTime are constant-time series accessors)

//+------------------------------------------------------------------+
//| UHV signal detection (ported from monitor/auto_uhv_trader.py)    |
//|                                                                  |
//| Algorithm (matches Pine + Python):                               |
//|  1. Find highest-volume CLOSED M1 bar in last InpUhvLookback     |
//|     bars (i.e. shifts 1..InpUhvLookback, excluding in-progress)  |
//|  2. UHV color: Red (close<open) → BUY setup, Green → SELL setup  |
//|  3. Trigger level = UHV high (BUY) or UHV low (SELL)             |
//|  4. Fire when bid/ask reaches level - InpPreOffsetPts (BUY)      |
//|     or level + InpPreOffsetPts (SELL)                            |
//|  5. UHV must be within InpUhvMaxAgeBars or it's stale            |
//|  6. Optional body% gate — body >= InpMinBodyPct * range          |
//+------------------------------------------------------------------+
UhvSignal DetectBreakout() {
   UhvSignal s;
   s.valid = false;

   // Need at least InpUhvLookback closed bars + 1 in-progress
   int avail_bars = Bars(_Symbol, PERIOD_M1);
   if (avail_bars < InpUhvLookback + 2) return s;

   // Find highest-volume CLOSED bar in shifts 1..InpUhvLookback
   int  uhv_shift = -1;
   long uhv_vol   = 0;
   for (int sh = 1; sh <= InpUhvLookback; sh++) {
      long v = iVolume(_Symbol, PERIOD_M1, sh);
      if (v > uhv_vol) { uhv_vol = v; uhv_shift = sh; }
   }
   if (uhv_shift < 0 || uhv_vol <= 0) return s;

   // Stale-anchor check
   if (uhv_shift > InpUhvMaxAgeBars) return s;

   double uhv_o = iOpen (_Symbol, PERIOD_M1, uhv_shift);
   double uhv_h = iHigh (_Symbol, PERIOD_M1, uhv_shift);
   double uhv_l = iLow  (_Symbol, PERIOD_M1, uhv_shift);
   double uhv_c = iClose(_Symbol, PERIOD_M1, uhv_shift);

   // Body% gate (optional — InpMinBodyPct=0 disables)
   if (InpMinBodyPct > 0.0) {
      double range = uhv_h - uhv_l;
      double body  = MathAbs(uhv_c - uhv_o);
      if (range > 0.0 && (body / range) < InpMinBodyPct) return s;
   }

   bool uhv_red   = uhv_c < uhv_o;
   bool uhv_green = uhv_c > uhv_o;
   if (!uhv_red && !uhv_green) return s;   // doji — skip

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pre = InpPreOffsetPts * _Point;

   // Red UHV → BUY when ASK reaches uhv_h - pre
   if (uhv_red) {
      double trigger = uhv_h - pre;
      if (ask >= trigger) {
         s.valid        = true;
         s.isLong       = true;
         s.triggerLevel = uhv_h;
         s.currentPrice = ask;
         s.uhvHigh      = uhv_h;
         s.uhvLow       = uhv_l;
      }
   }
   // Green UHV → SELL when BID reaches uhv_l + pre
   else if (uhv_green) {
      double trigger = uhv_l + pre;
      if (bid <= trigger) {
         s.valid        = true;
         s.isLong       = false;
         s.triggerLevel = uhv_l;
         s.currentPrice = bid;
         s.uhvHigh      = uhv_h;
         s.uhvLow       = uhv_l;
      }
   }

   // Body breakout confirmation (skip if disabled)
   if (s.valid && InpRequireBodyClose) {
      // For LONG: require either current bar close > uhv_h, OR previous closed bar close > uhv_h
      double cur_c = iClose(_Symbol, PERIOD_M1, 0);
      double pr1_c = iClose(_Symbol, PERIOD_M1, 1);
      bool breakout_confirmed;
      if (s.isLong) breakout_confirmed = (cur_c > uhv_h) || (pr1_c > uhv_h);
      else          breakout_confirmed = (cur_c < uhv_l) || (pr1_c < uhv_l);
      if (!breakout_confirmed) s.valid = false;
   }

   // Background context filter — UHV is more reliable as a climax when prior bars
   // were predominantly opposite color (selling-climax-in-downtrend pattern, etc.)
   if (s.valid && InpRequireBgContext) {
      if (!BgContextOK(uhv_shift, s.isLong, 5)) s.valid = false;
   }

   return s;
}

//+------------------------------------------------------------------+
//| Entry firing — naked OrderSend with sl=0, tp=0 (virtual)         |
//|                                                                  |
//| For XAUUSD with contract size 100:                               |
//|   $1 PnL per 0.01 price-move at 1.0 lots                         |
//|   $1 PnL per 0.10 price-move at 0.10 lots                        |
//|   formula: price_distance = $X / (lots * 100)                    |
//+------------------------------------------------------------------+
bool FireEntry(UhvSignal &sig) {
   // Compute lots — fixed or equity-based (InpRiskPctPerTrade > 0 enables dynamic)
   double lots = ComputeLots();
   if (lots < 0.01) {
      LogError(StringFormat("ComputeLots returned %.4f, abort fire", lots));
      return false;
   }

   double price = sig.isLong
                  ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string comment = StringFormat("UHV-N %s", sig.isLong ? "L" : "S");

   bool ok;
   if (sig.isLong) {
      ok = g_trade.Buy(lots, _Symbol, 0.0, 0.0, 0.0, comment);   // price=0 → market
   } else {
      ok = g_trade.Sell(lots, _Symbol, 0.0, 0.0, 0.0, comment);
   }

   if (!ok) {
      LogError(StringFormat("OrderSend failed rc=%d %s",
                            g_trade.ResultRetcode(),
                            g_trade.ResultRetcodeDescription()));
      return false;
   }

   ulong  ticket    = g_trade.ResultDeal();
   double fill_px   = g_trade.ResultPrice();
   double slippage  = sig.isLong ? (fill_px - price) : (price - fill_px);

   // Register virtual exit
   VirtualExit ve;
   ve.ticket          = ticket;
   ve.entryPrice      = fill_px;
   ve.lots            = lots;
   ve.openedAt        = TimeCurrent();
   ve.type            = sig.isLong ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   ve.peakPnlUsd      = -1e9;
   ve.trailArmed      = false;
   ve.hasBeenPositive = false;

   double tp_dist = InpVirtualTpUsd / (lots * 100.0);     // dollars → price-distance
   double sl_dist = InpVirtualSlUsd / (lots * 100.0);
   ve.virtualTP   = sig.isLong ? fill_px + tp_dist : fill_px - tp_dist;
   ve.virtualSL   = sig.isLong ? fill_px - sl_dist : fill_px + sl_dist;
   int n = ArraySize(g_active);
   ArrayResize(g_active, n + 1);
   g_active[n] = ve;

   g_last_entry_ts = TimeCurrent();
   WriteSniperLockFile(sig);   // tell auto_uhv_trader.py we just fired — 5min cooldown on its side
   LogFill(sig, ve, fill_px, slippage);
   if (InpAnnotateChart) AnnotateEntry(ve);
   return true;
}

//+------------------------------------------------------------------+
//| Compute lot size — fixed or equity-based (per design doc §15.2) |
//+------------------------------------------------------------------+
double ComputeLots() {
   if (InpRiskPctPerTrade <= 0.0) return InpLots;
   double equity      = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_usd    = equity * InpRiskPctPerTrade / 100.0;
   double sl_dist_pts = InpVirtualSlUsd;                       // already in $ on 1.0-lot equivalent
   if (sl_dist_pts <= 0) return InpLots;
   double lots = risk_usd / sl_dist_pts;                       // $risk / $-per-lot-at-SL = lots
   return NormalizeDouble(MathMax(0.01, MathMin(InpMaxLots, lots)), 2);
}

//+------------------------------------------------------------------+
//| Virtual exit walker — runs every OnTick                          |
//| Priority: catastrophic SL > scratch/kill timer > TP-or-trail     |
//| Two modes:                                                       |
//|   Fixed-TP (InpUseTrailing=false): close at first +InpVirtualTp  |
//|   Trailing (InpUseTrailing=true):  arm at +InpTrailTrigger,      |
//|                                    exit on InpTrailDrop drop     |
//+------------------------------------------------------------------+
void WalkVirtualExits() {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   datetime now = TimeCurrent();

   for (int i = ArraySize(g_active) - 1; i >= 0; i--) {
      VirtualExit ve = g_active[i];

      // Verify position still exists (it might have been closed externally)
      if (!PositionSelectByTicket(ve.ticket)) {
         if (InpVerbose) Print("[UhvNative] virtual: ticket ", ve.ticket, " no longer open — removing from active");
         RemoveFromActive(i);
         continue;
      }

      // Safety: only manage positions with our magic
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) {
         if (InpVerbose) Print("[UhvNative] virtual: ticket ", ve.ticket, " magic mismatch — skipping");
         RemoveFromActive(i);
         continue;
      }

      double cur_price = (ve.type == POSITION_TYPE_BUY) ? bid : ask;
      // Compute current $ P&L using captured lots (handles dynamic-lot case)
      double cur_pnl_usd;
      if (ve.type == POSITION_TYPE_BUY) cur_pnl_usd = (cur_price - ve.entryPrice) * ve.lots * 100.0;
      else                              cur_pnl_usd = (ve.entryPrice - cur_price) * ve.lots * 100.0;

      // Track peak + positive flag
      if (cur_pnl_usd > ve.peakPnlUsd) ve.peakPnlUsd = cur_pnl_usd;
      if (cur_pnl_usd > 0) ve.hasBeenPositive = true;
      g_active[i] = ve;   // write back struct (peak/flags persist across ticks)

      // Catastrophic stop — checked in BOTH modes (always-on safety)
      bool sl_hit = cur_pnl_usd <= -InpVirtualSlUsd;
      if (sl_hit) {
         CloseVirtualPosition(ve, "SL");
         RemoveFromActive(i);
         continue;
      }

      double age_sec = (double)(now - ve.openedAt);

      if (InpUseTrailing) {
         // ── TRAILING MODE ──
         // Arm trail when peak ≥ trigger
         if (!ve.trailArmed && ve.peakPnlUsd >= InpTrailTriggerUsd) {
            ve.trailArmed = true;
            g_active[i] = ve;
            if (InpVerbose) Print("[UhvNative] trail armed ticket=", ve.ticket, " peak=$", ve.peakPnlUsd);
         }
         // Trail exit: peak armed AND drop from peak ≥ InpTrailDropUsd
         if (ve.trailArmed && (ve.peakPnlUsd - cur_pnl_usd) >= InpTrailDropUsd) {
            CloseVirtualPosition(ve, "TRAIL");
            RemoveFromActive(i);
            continue;
         }
         // Scratch exit: still not positive after InpTrailScratchSec
         if (!ve.hasBeenPositive && age_sec > InpTrailScratchSec) {
            CloseVirtualPosition(ve, "SCRATCH");
            RemoveFromActive(i);
            continue;
         }
         // Max-hold timeout
         if (age_sec >= InpTrailMaxHoldSec) {
            CloseVirtualPosition(ve, "TIMEOUT");
            RemoveFromActive(i);
            continue;
         }
      } else {
         // ── FIXED-TP MODE (original) ──
         bool tp_hit = (ve.type == POSITION_TYPE_BUY) ? (cur_price >= ve.virtualTP) : (cur_price <= ve.virtualTP);
         bool timer_hit = age_sec >= InpKillTimerSec;
         if (timer_hit) {
            CloseVirtualPosition(ve, "KILL");
            RemoveFromActive(i);
         } else if (tp_hit) {
            CloseVirtualPosition(ve, "TP");
            RemoveFromActive(i);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Close a virtual position — handles broker requotes (3 retries)   |
//|                                                                  |
//| Per design-doc §15.1: small close-slippage compounds, so we      |
//| log intended vs actual fill price for post-mortem analysis.      |
//+------------------------------------------------------------------+
bool CloseVirtualPosition(VirtualExit &ve, string reason) {
   double intended_px = (ve.type == POSITION_TYPE_BUY)
                        ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                        : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   bool closed = false;
   uint last_rc = 0;
   string last_rc_desc = "";
   for (int attempt = 0; attempt < 3 && !closed; attempt++) {
      if (g_trade.PositionClose(ve.ticket, 30)) {
         closed = true;
         break;
      }
      last_rc      = g_trade.ResultRetcode();
      last_rc_desc = g_trade.ResultRetcodeDescription();
      // Retry only on transient codes
      if (last_rc != TRADE_RETCODE_REQUOTE && last_rc != TRADE_RETCODE_PRICE_OFF
          && last_rc != TRADE_RETCODE_PRICE_CHANGED) {
         break;
      }
   }

   if (!closed) {
      LogError(StringFormat("PositionClose ticket=%I64u rc=%d %s after retries",
                            ve.ticket, last_rc, last_rc_desc));
      return false;
   }

   double actual_px = g_trade.ResultPrice();
   double slip      = (ve.type == POSITION_TYPE_BUY)
                      ? (intended_px - actual_px)
                      : (actual_px - intended_px);
   double pnl_price = (ve.type == POSITION_TYPE_BUY)
                      ? (actual_px - ve.entryPrice)
                      : (ve.entryPrice - actual_px);
   double pnl_usd   = pnl_price * InpLots * 100.0;

   g_today_pl += pnl_usd;
   LogClose(ve, reason, intended_px, actual_px, slip, pnl_usd);
   if (InpAnnotateChart) AnnotateExit(ve, actual_px, reason, pnl_usd);
   return true;
}

void RemoveFromActive(int idx) {
   int n = ArraySize(g_active);
   if (idx < 0 || idx >= n) return;
   for (int j = idx; j < n - 1; j++) g_active[j] = g_active[j + 1];
   ArrayResize(g_active, n - 1);
}

//+------------------------------------------------------------------+
//| Sniper coordination — write JSON file when WE fire, and check    |
//| for a "they just fired" file from auto_uhv_trader.py to lock out |
//| 5 minutes. Same file path documented in UhvNativeTrader.md §10.  |
//|                                                                  |
//| Format: {"ts_unix": <int>, "side": "buy|sell", "price": <float>} |
//+------------------------------------------------------------------+
const int SNIPER_LOCKOUT_SEC = 300;   // 5 minutes

bool SniperLockedOut() {
   // We read THE SAME file that we write to — so this also dedupes our own
   // back-to-back fires within 5 min, which is desirable safety.
   if (!FileIsExist(InpSniperLockFile, FILE_COMMON)) {
      // Try as absolute path (FileIsExist looks in MQL5/Files by default)
      // We use raw fileio for absolute paths since the lockfile is outside MT5 sandbox.
   }
   // Fall back to absolute-path read via low-level approach — kernel32.dll handle
   // is overkill for this; instead we read via standard file API if path is reachable.
   // MT5 sandboxes file access; we work around by writing to a path inside Common
   // and reading via FileOpen with FILE_COMMON flag. So actually rewrite path semantics:
   // our lockfile lives in Common\Files\.uhv_native_last_fire.json (cross-EA visible).
   // For now, simple Python-side stat: read the file's last-modified epoch.
   long age_sec = -1;
   int h = FileOpen(".uhv_native_last_fire.json", FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if (h != INVALID_HANDLE) {
      string line = FileReadString(h);
      FileClose(h);
      // line is JSON; extract ts_unix via simple substring search
      int idx = StringFind(line, "\"ts_unix\":");
      if (idx >= 0) {
         long ts = StringToInteger(StringSubstr(line, idx + 10, 12));
         if (ts > 0) age_sec = (long)TimeCurrent() - ts;
      }
   }
   return (age_sec >= 0 && age_sec < SNIPER_LOCKOUT_SEC);
}

void WriteSniperLockFile(UhvSignal &sig) {
   int h = FileOpen(".uhv_native_last_fire.json", FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if (h == INVALID_HANDLE) {
      LogError(StringFormat("WriteSniperLockFile failed err=%d", GetLastError()));
      return;
   }
   string body = StringFormat("{\"ts_unix\":%d,\"side\":\"%s\",\"price\":%.4f,\"source\":\"UhvNativeTrader\"}",
                              (int)TimeCurrent(),
                              sig.isLong ? "buy" : "sell",
                              sig.currentPrice);
   FileWriteString(h, body);
   FileClose(h);
}

//+------------------------------------------------------------------+
//| Background context check — for a long signal (red UHV), majority |
//| of N closed bars before the UHV should be RED. Mirrored for SELL.|
//| Optional refinement, off by default. Captures Wyckoff "selling   |
//| climax in a downtrend" (or buying climax in uptrend) intuition.  |
//+------------------------------------------------------------------+
bool BgContextOK(int uhv_shift, bool isLongSetup, int lookback = 5) {
   int red = 0, green = 0;
   // Bars BEFORE the UHV are at shifts (uhv_shift+1)..(uhv_shift+lookback)
   for (int i = 1; i <= lookback; i++) {
      int sh = uhv_shift + i;
      double o = iOpen(_Symbol, PERIOD_M1, sh);
      double c = iClose(_Symbol, PERIOD_M1, sh);
      if (c < o) red++;
      else if (c > o) green++;
   }
   int needed = (lookback / 2) + 1;   // strict majority
   return isLongSetup ? (red >= needed) : (green >= needed);
}

//+------------------------------------------------------------------+
//| Diagnostic heartbeat — once per minute, print + log current      |
//| detection state so we can see WHY signals aren't firing.         |
//+------------------------------------------------------------------+
datetime g_last_heartbeat_ts = 0;
void DiagnosticHeartbeat() {
   datetime now = TimeCurrent();
   if (now - g_last_heartbeat_ts < 60) return;
   g_last_heartbeat_ts = now;

   int avail = Bars(_Symbol, PERIOD_M1);
   if (avail < InpUhvLookback + 2) return;

   int uhv_shift = -1;
   long uhv_vol = 0;
   for (int sh = 1; sh <= InpUhvLookback; sh++) {
      long v = iVolume(_Symbol, PERIOD_M1, sh);
      if (v > uhv_vol) { uhv_vol = v; uhv_shift = sh; }
   }
   if (uhv_shift < 0) return;

   double uhv_h = iHigh(_Symbol, PERIOD_M1, uhv_shift);
   double uhv_l = iLow (_Symbol, PERIOD_M1, uhv_shift);
   double uhv_o = iOpen(_Symbol, PERIOD_M1, uhv_shift);
   double uhv_c = iClose(_Symbol, PERIOD_M1, uhv_shift);
   bool   red    = uhv_c < uhv_o;
   string barCol = red ? "RED" : (uhv_c > uhv_o ? "GREEN" : "DOJI");
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double level = red ? uhv_h : uhv_l;
   double dist  = red ? (level - ask) : (bid - level);

   Print(StringFormat("[UhvNative] heartbeat — uhvShift=%d %s vol=%d level=%.3f dist=%.2f price=(bid %.3f ask %.3f) age=%ds active=%d signals_today=%d",
                      uhv_shift, barCol, (int)uhv_vol, level, dist, bid, ask,
                      uhv_shift * 60, ArraySize(g_active), g_signals_today));
}

//+------------------------------------------------------------------+
//| === Risk gates (basic implementation) ========================= |
//+------------------------------------------------------------------+
bool RiskGatesOpen() {
   if (!InpEnabled) return false;
   if (StringFind(_Symbol, InpSymbol) < 0) return false;

   // Spread gate
   long spread_pts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if (spread_pts > (long)InpMaxSpreadPts) {
      if (InpVerbose) Print("[UhvNative] gate-block: spread=", spread_pts, " > ", InpMaxSpreadPts);
      return false;
   }

   // Python-sniper lockout — both EAs share UHV detection; if Python sniper just fired,
   // we sit out the next 5 minutes to avoid double-firing on the same setup.
   if (InpRespectSniperLock && SniperLockedOut()) {
      if (InpVerbose) Print("[UhvNative] gate-block: python sniper recently fired");
      return false;
   }

   // Sydney session gate
   if (InpSkipSydney) {
      MqlDateTime gmt;
      TimeGMT(gmt);
      if (gmt.hour < 6) {
         if (InpVerbose) Print("[UhvNative] gate-block: Sydney session ", gmt.hour, ":", gmt.min);
         return false;
      }
   }

   // Daily loss gate
   if (g_today_pl <= -InpDailyLossUsd) {
      if (InpVerbose) Print("[UhvNative] gate-block: daily loss limit hit ", g_today_pl);
      return false;
   }

   return true;
}

void ResetDailyStateIfNewDay() {
   MqlDateTime now;
   TimeCurrent(now);
   if (now.day != g_today_dom) {
      g_today_dom     = now.day;
      g_today_pl      = 0.0;
      g_signals_today = 0;
      g_fills_today   = 0;
      Print("[UhvNative] new day reset — ", now.year, "-", now.mon, "-", now.day);
   }
}

//+------------------------------------------------------------------+
//| === Logging =================================================== |
//+------------------------------------------------------------------+
void OpenCsvLog() {
   string path = "uhv_native_trader.csv";
   bool exists = FileIsExist(path);
   g_csv_handle = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if (g_csv_handle == INVALID_HANDLE) {
      Print("[UhvNative] CSV open failed err=", GetLastError());
      return;
   }
   FileSeek(g_csv_handle, 0, SEEK_END);
   if (!exists) {
      FileWrite(g_csv_handle, "ts_iso", "event", "side", "price", "lots", "magic", "tp", "sl", "reason", "pnl_usd");
   }
}

void LogDryRunSignal(UhvSignal &sig) {
   string ts = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   Print("[UhvNative] DRYRUN ", sig.isLong ? "LONG" : "SHORT", " @ ", sig.currentPrice, "  (trigger=", sig.triggerLevel, ")");
   if (g_csv_handle != INVALID_HANDLE) {
      FileWrite(g_csv_handle, ts, "DRYRUN_SIGNAL",
                sig.isLong ? "LONG" : "SHORT",
                DoubleToString(sig.currentPrice, _Digits),
                DoubleToString(InpLots, 2),
                IntegerToString(InpMagicNumber),
                "", "", "would-fire", "0.00");
      FileFlush(g_csv_handle);
   }
}

void LogError(string msg) {
   Print("[UhvNative] ERROR: ", msg);
   if (g_csv_handle != INVALID_HANDLE) {
      string ts = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
      FileWrite(g_csv_handle, ts, "ERROR", "", "", "", IntegerToString(InpMagicNumber), "", "", msg, "");
      FileFlush(g_csv_handle);
   }
}

void LogFill(UhvSignal &sig, VirtualExit &ve, double fill_px, double slip) {
   string ts = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   Print("[UhvNative] FILL ", sig.isLong ? "LONG" : "SHORT",
         " ticket=", ve.ticket, " entry=", DoubleToString(fill_px, _Digits),
         " vTP=", DoubleToString(ve.virtualTP, _Digits),
         " vSL=", DoubleToString(ve.virtualSL, _Digits),
         " entrySlip=", DoubleToString(slip * 100.0 * InpLots, 2));
   if (g_csv_handle != INVALID_HANDLE) {
      FileWrite(g_csv_handle, ts, "FILL",
                sig.isLong ? "LONG" : "SHORT",
                DoubleToString(fill_px, _Digits),
                DoubleToString(InpLots, 2),
                IntegerToString(InpMagicNumber),
                DoubleToString(ve.virtualTP, _Digits),
                DoubleToString(ve.virtualSL, _Digits),
                StringFormat("entrySlip=%.4f", slip),
                "0.00");
      FileFlush(g_csv_handle);
   }
}

void LogClose(VirtualExit &ve, string reason, double intended_px, double actual_px, double slip, double pnl_usd) {
   string ts = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   Print("[UhvNative] CLOSE ", reason,
         " ticket=", ve.ticket,
         " entry=", DoubleToString(ve.entryPrice, _Digits),
         " intended=", DoubleToString(intended_px, _Digits),
         " actual=", DoubleToString(actual_px, _Digits),
         " closeSlip=$", DoubleToString(slip * 100.0 * InpLots, 2),
         " pnl=$", DoubleToString(pnl_usd, 2),
         " today=$", DoubleToString(g_today_pl, 2));
   if (g_csv_handle != INVALID_HANDLE) {
      FileWrite(g_csv_handle, ts, "CLOSE",
                ve.type == POSITION_TYPE_BUY ? "LONG" : "SHORT",
                DoubleToString(actual_px, _Digits),
                DoubleToString(InpLots, 2),
                IntegerToString(InpMagicNumber),
                "", "",
                StringFormat("%s closeSlip=%.4f", reason, slip),
                DoubleToString(pnl_usd, 2));
      FileFlush(g_csv_handle);
   }
}

void AnnotateEntry(VirtualExit &ve) {
   string name = StringFormat("uhvN_in_%I64u", ve.ticket);
   bool isLong = (ve.type == POSITION_TYPE_BUY);
   if (ObjectCreate(0, name, OBJ_ARROW, 0, ve.openedAt, ve.entryPrice)) {
      ObjectSetInteger(0, name, OBJPROP_ARROWCODE, isLong ? 233 : 234);
      ObjectSetInteger(0, name, OBJPROP_COLOR, isLong ? clrLime : clrTomato);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   }
}

void AnnotateExit(VirtualExit &ve, double exit_px, string reason, double pnl_usd) {
   string name = StringFormat("uhvN_out_%I64u", ve.ticket);
   if (ObjectCreate(0, name, OBJ_ARROW, 0, TimeCurrent(), exit_px)) {
      ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 251);   // X mark
      color c = pnl_usd > 0 ? clrLime : pnl_usd < 0 ? clrRed : clrYellow;
      ObjectSetInteger(0, name, OBJPROP_COLOR, c);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      string text = StringFormat("uhvN_out_%I64u_t", ve.ticket);
      if (ObjectCreate(0, text, OBJ_TEXT, 0, TimeCurrent(), exit_px)) {
         ObjectSetString(0, text, OBJPROP_TEXT, StringFormat("%s $%.2f", reason, pnl_usd));
         ObjectSetInteger(0, text, OBJPROP_COLOR, c);
         ObjectSetInteger(0, text, OBJPROP_FONTSIZE, 8);
      }
   }
}
//+------------------------------------------------------------------+
