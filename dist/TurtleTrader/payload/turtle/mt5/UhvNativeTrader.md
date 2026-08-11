# UhvNativeTrader.mq5 — Design Doc

**Status:** OUTLINE (skeleton compiles, logic stubbed)
**Asset:** XAUUSD (gold)
**Timeframe:** Tick + M1 aggregation in EA
**Goal:** Replicate Zee's manual 98W/1L UHV-breakout alpha by removing webhook latency
**Author:** Claude Code, 2026-05-09

---

## 1. Why this EA exists

The validated alpha is real (manually traded 98:1 record on XAUUSD). The execution model
that kills it is the TradingView → PineConnector → MT5 webhook chain (~262–910ms cumulative,
spike to 5s under load). At XAUUSD's 10–30 pips/sec UHV-breakout velocity, that latency
costs ~$1.39 average slippage per fill — 4.6× the 3-pip target. Mathematically dead.

This EA moves the entire detect → fire → exit loop **inside the MT5 terminal**. Latency
collapses to single-digit milliseconds. The 1.39$ slippage drops to 5–15¢ (broker matching
engine only).

Read the full diagnosis in: [UHV Strategy Automation_ Stop Orders.pdf](../UHV%20Strategy%20Automation_%20Stop%20Orders.pdf)
(Section 5 — the architecture below directly implements §5.2 + §5.3).

---

## 2. Architectural pillars

### 2.1 Tick-level detection (no bar close wait)

`OnTick()` runs on every quote. We maintain a rolling 60-bar M1 buffer in EA memory,
appending the in-progress bar's high/low/close/volume on every tick. UHV detection runs
every tick — the moment current-bar volume crosses the threshold AND price body crosses
the trigger level, we fire. We don't wait for `barstate.isconfirmed`.

### 2.2 Virtual / Stealth TP/SL

`OrderSend()` is called with `sl=0, tp=0` — broker sees a naked position. The actual TP/SL
levels are stored in EA memory only:

```mql5
struct VirtualExit {
   ulong  ticket;
   double entryPrice;
   double virtualSL;     // e.g. entry - 1.50  (15 pips on a buy)
   double virtualTP;     // e.g. entry + 0.30  (3 pips on a buy)
   datetime openedAt;
   ENUM_POSITION_TYPE type;
};
VirtualExit g_active[];   // active positions awaiting virtual exits
```

On every tick, `OnTick()` walks `g_active[]`, computes `PositionGetDouble(POSITION_PROFIT)`,
and closes the position the millisecond profit crosses TP threshold. No hard SL/TP visible
to broker — **immune to stop-hunting**.

### 2.3 Pre-flight spread gate

Before any entry, query `SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)`. If spread > X points,
abort the signal — better to skip than get filled at a punitive level. Strategy depends on
sub-pip slippage; a 4-pip spread spike ALONE kills profitability.

### 2.4 Session filter (already validated)

Memory: `project_sydney_session_filters.md` proves Sydney session (00–06 GMT) is 0% WR on
mechanical UHV. EA hard-blocks all entries in this window regardless of signal strength.

### 2.5 Daily loss kill switch

Track today's realized P&L. If it dips below `-DailyLossLimitUSD`, EA disables itself for
the rest of the day. Resets at broker midnight (server time, not local).

---

## 3. File layout

```
mt5/
├── UhvNativeTrader.mq5        ← main EA (skeleton present)
├── UhvNativeTrader.md         ← this design doc
├── include/
│   ├── UHVDetection.mqh       ← bar buffer + UHV detection logic (stubbed)
│   ├── VirtualExits.mqh       ← VirtualExit struct + tick-loop checker (stubbed)
│   ├── RiskGates.mqh          ← spread filter, session filter, loss limit (stubbed)
│   └── Logging.mqh            ← CSV row writers + chart annotations (stubbed)
└── configs/
    └── uhv_native_defaults.set  ← default input set
```

**Why split into `.mqh` modules:** the existing ShanoExitManager.mq5 is 2000+ lines and
hard to navigate. New EA stays modular from day one.

---

## 4. Core inputs (matching house style)

```mql5
input group "=== Master Control ==="
input bool   InpEnabled        = true;        // Enable EA
input bool   InpDryRun         = true;        // DEFAULT TRUE — log signals but don't actually OrderSend()
input string InpSymbol         = "XAUUSD";
input int    InpMagicNumber    = 84099;       // Distinct from 84001/2/3 used by Python sniper

input group "=== UHV Detection ==="
input int    InpBarsBuffer     = 60;          // M1 bars kept in rolling buffer
input int    InpUhvLookback    = 20;          // Find highest-vol bar in last N bars
input int    InpUhvMaxAgeBars  = 10;          // Discard UHV signals older than this
input double InpMinBodyPct     = 0.50;        // Body must be ≥ X% of candle range
input bool   InpRequireBgContext = false;     // Background red-bars (long) / green (short) before UHV

input group "=== Entry ==="
input double InpLots           = 0.10;        // Fixed lot size (10x scale = 0.01 for $500 real)
input double InpPreOffsetPts   = 1.0;         // Fire when price is X points BEFORE breakout level
input bool   InpRequireBodyClose = true;      // Confirm with body close past level (vs wick)

input group "=== Exit (Virtual) ==="
input double InpVirtualTpUsd   = 3.0;         // Close at first +$X profit
input double InpVirtualSlUsd   = 15.0;        // Hard kill at -$X loss
input int    InpKillTimerSec   = 5;           // Max hold time (sec)
input bool   InpUseTrailing    = false;       // Trail-after-peak instead of fixed TP

input group "=== Risk Gates ==="
input double InpMaxSpreadPts   = 30.0;        // Reject entry if spread > X points
input bool   InpSkipSydney     = true;        // Block 00:00–06:00 GMT (memory: 0% WR)
input double InpDailyLossUsd   = 100.0;       // Halt for the day at -$X realized
input int    InpMinSpacingSec  = 60;          // Minimum seconds between entries

input group "=== Diagnostics ==="
input bool   InpLogToCsv       = true;        // Write each fill + exit to logs/uhv_native_trader.csv
input bool   InpAnnotateChart  = true;        // Draw entry/exit arrows on chart
input bool   InpVerbose        = false;       // Print() every tick decision (DEBUG ONLY)
```

---

## 5. Tick-loop pseudocode

```
OnTick():
  1. risk_gates_check()          ← spread, session, daily loss, master enable
     → if any gate is closed: return early
  2. update_bar_buffer()         ← append current tick to in-progress M1 bar
  3. if g_active.size() > 0:
       walk_virtual_exits()      ← check every open position for TP / SL / kill timer
  4. if entry_cooldown_passed():
       sig = detect_uhv_breakout()
       if sig:
         if InpDryRun: log_dryrun_signal(sig); else fire_market_order(sig)

OnNewMinuteBar():       ← detect via SymbolInfoInteger time-of-last-tick rollover
  5. finalize_pending_bar()      ← move in-progress bar to closed-bar list
  6. recompute_uhv_anchor()      ← find highest-volume bar in last InpUhvLookback closed bars
```

---

## 6. UHV detection (UHVDetection.mqh)

```mql5
struct M1Bar {
   datetime ts;
   double   o, h, l, c;
   long     vol;       // tick volume
};
M1Bar g_buffer[];      // rolling InpBarsBuffer-sized

int UhvDetectIdx() {
   // Find highest-volume bar in last InpUhvLookback CLOSED bars
   int n = ArraySize(g_buffer);
   int look_start = MathMax(0, n - InpUhvLookback - 1);
   int look_end   = n - 2;        // -2 to exclude the in-progress bar
   int idx = -1;
   long max_vol = 0;
   for (int i = look_start; i <= look_end; i++) {
      if (g_buffer[i].vol > max_vol) { max_vol = g_buffer[i].vol; idx = i; }
   }
   if (idx < 0) return -1;
   if ((n - 1 - idx) > InpUhvMaxAgeBars) return -1;   // too old
   return idx;
}

struct UhvSignal {
   bool   valid;
   bool   isLong;
   double triggerLevel;        // UHV high (long) or low (short)
   double currentPrice;
};

UhvSignal DetectBreakout() {
   UhvSignal s; s.valid = false;
   int uhv_idx = UhvDetectIdx();
   if (uhv_idx < 0) return s;
   M1Bar uhv = g_buffer[uhv_idx];
   bool uhv_red   = uhv.c < uhv.o;
   bool uhv_green = uhv.c > uhv.o;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pre = InpPreOffsetPts * _Point;

   // Long setup: red UHV + price approaching/breaking high
   if (uhv_red && ask >= uhv.h - pre) {
      s.valid = true; s.isLong = true;
      s.triggerLevel = uhv.h; s.currentPrice = ask;
   }
   // Short setup: green UHV + price approaching/breaking low
   else if (uhv_green && bid <= uhv.l + pre) {
      s.valid = true; s.isLong = false;
      s.triggerLevel = uhv.l; s.currentPrice = bid;
   }
   return s;
}
```

---

## 7. Entry firing

```mql5
bool FireEntry(UhvSignal &sig) {
   MqlTradeRequest req = {};
   MqlTradeResult res = {};
   req.action       = TRADE_ACTION_DEAL;             // immediate market fill
   req.symbol       = _Symbol;
   req.volume       = InpLots;
   req.type         = sig.isLong ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price        = sig.isLong
                      ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                      : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   req.deviation    = 30;                            // accept up to 30 points slippage
   req.magic        = InpMagicNumber;
   req.sl           = 0;                             // VIRTUAL — set in EA memory only
   req.tp           = 0;                             // VIRTUAL
   req.type_filling = ORDER_FILLING_IOC;             // immediate-or-cancel
   req.comment      = StringFormat("UHV-N %s", sig.isLong ? "L" : "S");

   if (!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE) {
      LogError(StringFormat("OrderSend failed retcode=%d %s", res.retcode, res.comment));
      return false;
   }

   // Register virtual exit for this position
   VirtualExit ve;
   ve.ticket     = res.deal;          // or res.order — verify in MT5 docs
   ve.entryPrice = res.price;
   ve.openedAt   = TimeCurrent();
   ve.type       = sig.isLong ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   double tp_dist = InpVirtualTpUsd / (InpLots * 100.0);  // dollars → price points (XAUUSD: $1 = 1pt at 1.0 lots)
   double sl_dist = InpVirtualSlUsd / (InpLots * 100.0);
   ve.virtualTP = sig.isLong ? ve.entryPrice + tp_dist : ve.entryPrice - tp_dist;
   ve.virtualSL = sig.isLong ? ve.entryPrice - sl_dist : ve.entryPrice + sl_dist;
   ArrayResize(g_active, ArraySize(g_active) + 1);
   g_active[ArraySize(g_active) - 1] = ve;
   return true;
}
```

---

## 8. Virtual exit walker (VirtualExits.mqh)

Runs every `OnTick()`:

```mql5
void WalkVirtualExits() {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   datetime now = TimeCurrent();

   for (int i = ArraySize(g_active) - 1; i >= 0; i--) {
      VirtualExit ve = g_active[i];
      if (!PositionSelectByTicket(ve.ticket)) {
         // Position no longer exists (closed externally — e.g., manual close)
         RemoveFromActive(i);
         continue;
      }

      double cur_price = (ve.type == POSITION_TYPE_BUY) ? bid : ask;
      bool tp_hit = (ve.type == POSITION_TYPE_BUY) ? (cur_price >= ve.virtualTP) : (cur_price <= ve.virtualTP);
      bool sl_hit = (ve.type == POSITION_TYPE_BUY) ? (cur_price <= ve.virtualSL) : (cur_price >= ve.virtualSL);
      bool timer_hit = (now - ve.openedAt) >= InpKillTimerSec;

      if (tp_hit || sl_hit || timer_hit) {
         string reason = tp_hit ? "TP" : sl_hit ? "SL" : "KILL";
         CloseVirtualPosition(ve, reason);
         RemoveFromActive(i);
      }
   }
}
```

---

## 9. Risk gates (RiskGates.mqh)

```mql5
bool RiskGatesOpen() {
   if (!InpEnabled) return false;
   if (Symbol() != InpSymbol) return false;

   // 1. Spread gate
   double spread_pts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if (spread_pts > InpMaxSpreadPts) {
      if (InpVerbose) Print("Gate: spread ", spread_pts, " > ", InpMaxSpreadPts);
      return false;
   }

   // 2. Sydney session gate
   if (InpSkipSydney) {
      MqlDateTime gmt; TimeGMT(gmt);
      if (gmt.hour >= 0 && gmt.hour < 6) {
         if (InpVerbose) Print("Gate: Sydney session block ", gmt.hour, ":", gmt.min);
         return false;
      }
   }

   // 3. Daily loss limit
   double today_pl = ComputeTodayRealizedPL();
   if (today_pl <= -InpDailyLossUsd) {
      Print("Gate: DAILY LOSS LIMIT hit (", today_pl, " <= -", InpDailyLossUsd, ") — EA halted for day");
      return false;
   }

   // 4. Min spacing between entries
   if (TimeCurrent() - g_last_entry_ts < InpMinSpacingSec) return false;

   return true;
}
```

---

## 10. Coexistence

This EA must NOT conflict with what's already running:

| Component | Magic | Role | Conflict? |
|-----------|-------|------|-----------|
| ShanoExitManager.mq5 | (managed) | Probe→main scalper for Shano strategy | ❌ Different strategy entirely; reads from PineConnector probes |
| auto_uhv_trader.py | 84001/2/3 | Python sniper, fires UHV via PineConnector | ⚠️ Same UHV pattern — must coordinate |
| TurtleTradeLogger.mq5 | (logger) | Writes turtle_fills.csv | ✅ Read-only, no conflict |
| **UhvNativeTrader.mq5** | **84099** | **NEW: native tick-level UHV** | — |

**Coordination with auto_uhv_trader.py:** when this EA fires, it writes to `monitor/.uhv_native_last_fire.json`
with a 5-minute lockout. The Python sniper reads this and skips its own fire if the native EA
just fired. This prevents double-execution while we're A/B testing native vs Python paths.

---

## 11. Backtesting plan

### 11.1 Strategy Tester (built-in MT5)

- Symbol: XAUUSD
- Timeframe: Every Tick Based on Real Ticks
- Period: Last 30 days (matches our parquet tick data range)
- Initial deposit: $5,000 (demo equivalent)
- Lots: 0.40 (demo size); for live $500 cap: scale to 0.04

Compare against the Python tick-replay results we already have:
- `_uhv_zee_style_results.json` — 100% WR with Sydney filter, +$45 net on 2026-05-07 (3 trades)
- `_turtle_optimized_results.json` — 30% WR, -$515 net (52 trades) under realistic webhook fills

Goal: native EA should match or exceed the Sydney-filtered Zee-loose result, but on more days.

### 11.2 Live A/B test

After backtest validates:
1. Run on demo for 5 trading days alongside auto_uhv_trader.py
2. Compare fill quality: log entry slippage, exit slippage, full-trade P&L
3. If native EA's avg slippage < $0.30 (10× improvement over current), promote to live

---

## 12. Deployment steps (when ready to ship)

1. Compile via MetaEditor: open `UhvNativeTrader.mq5` → F7 (compile) → check for warnings
2. Copy `.ex5` to MT5 Experts folder (the existing `mt5\install_eas.ps1` already automates this — extend it)
3. Drag onto XAUUSD chart, M1 timeframe
4. **Set `InpDryRun = true`** initially — EA will log signals but not actually trade
5. Watch the log file `MQL5/Files/uhv_native_trader.csv` for 1 day
6. Compare logged signals against actual market behavior — does the EA fire on the right setups?
7. If matching expectations: flip `InpDryRun = false`, lots stay at 0.04 (real-money safe)
8. Monitor for 5 days. Promote to 0.10 lots if WR > 60% over 30+ trades.

---

## 13. What's NOT in scope (yet)

These are intentionally deferred to keep the first version shippable:

- **Pending stop orders.** First version uses tick-level market orders only. Stop orders can be
  added later if we want to replace the orphan-prone Pine Stop mode.
- **Multi-symbol support.** XAUUSD only. Generalizing later when Setup 1 is proven on gold.
- **Trailing exits.** Skip the trailing variant in v1; just fixed TP. Add `InpUseTrailing`
  scaffold but route to fixed TP for now.
- **VPS migration.** Run on local laptop initially. Equinix LD5 / NY4 co-location is a
  follow-up infrastructure project.
- **MT5 strategy tester native compile.** First we get it running live; tester optimization later.

---

## 14. Open questions

- **TP/SL distance math:** for XAUUSD, $1 PnL on 1.0 lots = 1 point of price movement (gold contract = 100). On 0.10 lots, $1 = 10 points. Need to verify the formula matches real fills before going live.
- **OrderSend retcode handling:** which `TRADE_RETCODE_*` values are retryable vs fatal? Need a simple retry-with-backoff for transient errors, abort for fatal.
- **`OnTick()` performance under news:** during NFP, gold can produce 100+ ticks/sec. The OnTick handler needs to be < 1ms even under load. Profile and optimize if needed.

These get answered during the dry-run phase, not before.

## 15. Phase 3 implementation notes (captured during design review 2026-05-09)

### 15.1 PositionClose requote/slippage handling

When the virtual TP triggers at +$3.00 but `PositionClose()` fills at +$2.40, our stealth-exit
math is off by 60¢ — small per-trade but compounds over hundreds of trades. Required handling
in `CloseVirtualPosition()`:

```mql5
bool CloseVirtualPosition(VirtualExit &ve, string reason) {
   for (int attempt = 0; attempt < 3; attempt++) {
      if (g_trade.PositionClose(ve.ticket, 30)) {       // 30-pt deviation tolerance
         double realized = g_trade.ResultPrice() ...;
         g_today_pl += realized;
         LogClose(ve, reason, realized, attempt);
         return true;
      }
      uint rc = g_trade.ResultRetcode();
      if (rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_OFF) {
         continue;                                       // retry — broker requoted
      }
      LogError(StringFormat("PositionClose failed rc=%d %s ticket=%d",
                             rc, g_trade.ResultRetcodeDescription(), ve.ticket));
      return false;                                      // fatal — give up
   }
   LogError(StringFormat("PositionClose: 3 retries exhausted ticket=%d", ve.ticket));
   return false;
}
```

Track close-slippage in CSV: log `intended_close_price` vs `actual_close_price` per trade.
After 100+ trades we'll know typical close slippage and can decide whether limit-on-close
is worth the rejection risk.

### 15.2 Equity-based dynamic lot sizing (future enhancement)

Current v0.10 uses fixed `InpLots`. Once the EA is profitable on demo for 5+ days, replace with:

```mql5
input double InpRiskPctPerTrade = 0.5;     // % of equity to risk per trade

double CalcLots() {
   if (InpRiskPctPerTrade <= 0.0) return InpLots;     // fall back to fixed
   double equity      = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_usd    = equity * InpRiskPctPerTrade / 100.0;
   double sl_dist_pts = InpVirtualSlUsd / 100.0;       // dollars → points (XAUUSD $1=$0.01)
   double lots        = risk_usd / (sl_dist_pts * 100.0);
   return NormalizeDouble(MathMax(0.01, MathMin(2.0, lots)), 2);
}
```

Where `0.5%` risk / trade with $500 equity + $1.50 SL distance gives 0.16 lots — modest
compounding without blowing through the 50% account-equity safety cap.

Gate this behind a flag (`InpDynamicLots = false` by default) and validate against fixed-lot
performance for 30+ trades before flipping on. Memory: real capital is $500 (not demo $5k),
so 0.5% risk = $2.50 — a single SL hit costs less than 1% of capital. Conservative by design.
