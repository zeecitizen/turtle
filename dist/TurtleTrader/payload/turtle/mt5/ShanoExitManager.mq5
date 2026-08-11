//+------------------------------------------------------------------+
//|  ShanoExitManager.mq5                                            |
//|  Complete Shano Momentum Scalping EA for XAUUSD                  |
//|                                                                  |
//|  ARCHITECTURE:                                                   |
//|  - PineConnector opens 0.01 SELL probe via TradingView webhook   |
//|  - This EA detects the probe, monitors P&L every tick            |
//|  - If probe confirms (+$0.58) → opens main trade (calculated)    |
//|  - Manages trailing exit, machine gun bursts, daily limits       |
//|                                                                  |
//|  LIFECYCLE:                                                      |
//|  1. Probe appears (0.01 SELL) → EA starts monitoring             |
//|  2. Probe profit >= ProbeConfirmUSD → open main SELL             |
//|  3. Main trade trails: peak >= TrailTrigger, drop >= TrailDrop   |
//|  4. Close main FIRST, then probe                                 |
//|  5. Machine gun: if momentum continues, reopen immediately       |
//|  6. Up to MaxBurst trades per burst cycle                        |
//|                                                                  |
//|  INSTALL: Drag onto XAUUSD chart (any timeframe). AutoTrading ON |
//|  NOTE: Does NOT conflict with TurtleTradeLogger (separate EA)    |
//+------------------------------------------------------------------+
#property copyright "Turtle Trader by M. Zeeshan"
#property version   "2.00"
#property description "Shano momentum scalp: probe→confirm→main→trail→machine gun"
#property strict

#include <Generic\HashMap.mqh>
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+
input group "=== Master Control ==="
input bool   InpEnabled       = true;          // Enable EA
input string InpSymbolFilter  = "XAUUSD";     // Symbol filter (blank = all)
input bool   InpSellOnly      = true;          // SELL only (ignore BUY signals)

input group "=== Probe Management ==="
input double InpProbeConfirm  = 0.58;          // Probe confirm threshold ($)
input double InpProbeFail     = 3.00;          // Probe fail cut ($)
input double InpProbeLots     = 0.01;          // Probe lot size (detect threshold)
input int    InpProbeTimeout  = 50;            // Probe timeout (sec) — close if still in loss after this (Shano S3)

input group "=== Main Trade Trailing ==="
input double InpTrailTrigger  = 8.0;           // Start trailing after this $ profit
input double InpTrailDrop     = 2.0;           // Close when drops this $ from peak
input double InpCatastrophic  = 0.50;          // Catastrophic loss = X * account equity (last-resort)

input group "=== Fear-Based Stops (Shano S3: lot > 0.10 only) ==="
input double InpHoldLotMax    = 0.10;          // Lots <= this: HOLD forever (Shano: 0.01/0.08/0.10 chalti rahay)
input double InpFearIdeal     = 70.0;          // Ideal close at -$X for lots > InpHoldLotMax (Shano: -70 ideal)
input double InpFearWashout   = 180.0;         // Hard close at -$X (washout-prevention) for lots > InpHoldLotMax

input group "=== Big-Loss Filters (added 2026-04-30) ==="
input int    InpPostBigLossCooldown = 0;       // Skip next N main trades after a fearIdeal hit (0 = off)
input int    InpDailyBigLossHalt    = 99;      // Halt all main-trades for the day after N fearIdeal hits (99 = off)
input bool   InpSkipBadHours        = false;   // Skip main-trades in narrow bad hours (04-06 + 21-23 broker)

input group "=== Trend Filter (added 2026-04-30 evening) ==="
input bool   InpTrendFilter         = false;   // Skip mains AGAINST trend or in NEUTRAL chop zone
input int    InpEmaFast             = 34;      // Fast EMA period
input int    InpEmaSlow             = 89;      // Slow EMA period
input int    InpTrendTfMinutes      = 1;       // Trend timeframe in minutes (1, 2, 3, 5, 10, 15)
input bool   InpSkipFastConfirm     = false;   // Skip mains where probe confirmed in 3-8s (fakeout zone)

input group "=== Shano-Zee UHV Breakout Filter (added 2026-04-30) ==="
input bool   InpUhvFilter           = false;   // Require trigger bar to break out of recent UHV candle high/low
input int    InpUhvLookback         = 20;      // Lookback (1-min bars) to find the UHV candle

input group "=== Lot Ladder (Shano-Zee burst pyramid, added 2026-04-30 evening) ==="
input bool   InpLotLadder           = false;   // Use progressive lot sizing per burst (overrides override/auto)
input double InpLotLadderStart      = 0.10;    // First main (burst 1) lot size
input double InpLotLadderStep       = 0.10;    // Increment per burst
input double InpLotLadderMax        = 0.70;    // Cap (do not exceed)

input group "=== BIG STACK Filters (PDF #2 — added 2026-04-30 evening) ==="
input int    InpTickSpeedMaxSec     = 0;       // Max seconds-into-trigger-bar UHV cross can occur (0 = off)
input double InpSpreadMaxMult       = 0.0;     // Max spread vs 5-min median baseline (0 = off, 1.3 = strict)
input bool   InpM15TrendFilter      = false;   // Require price above M15 21-EMA (buys) / below (sells)
input int    InpM15EmaPeriod        = 21;      // M15 EMA period
input int    InpChainStopAfterLoss  = 0;       // Halt after N consecutive losing chains (0 = off)

input group "=== Setup 1 HARD GATE (M1 UHV breakout pattern, added 2026-04-30 night) ==="
input bool   InpSetup1Filter        = false;   // Require Setup 1 pattern in last N M1 bars
input int    InpSetup1LookbackBars  = 3;       // Look back N M1 bars for the Setup 1 trigger
input int    InpSetup1PatternLookback = 10;    // Pattern: search this many bars for UHV red before trigger

input group "=== Burst-Delta Filter (PDF #3 microstructure, added 2026-05-01) ==="
input bool   InpBurstDeltaFilter    = false;   // Require positive pseudo-delta (flow agrees with chain dir) before each burst-fire
input int    InpBurstDeltaLookbackSec = 15;    // Rolling window (seconds) to count up-ticks vs down-ticks

input group "=== Trigger Margin (PDF #3 deep-mine, added 2026-05-01 night) ==="
input double InpTriggerPastUhvPts   = 0.0;     // Trigger close must clear UHV extreme by ≥ this many points (0 = off; backtest 0.3 best)

input group "=== CDD Divergence Exit (PDF #3 deep-mine, added 2026-05-01 night) ==="
input bool   InpCddDivExit          = false;   // Exit early on cumulative-delta divergence (price new HWM but cumDelta lower-HWM)
input int    InpCddCheckSec         = 10;      // Check interval (seconds) — every N sec while in profit
input int    InpCddWindowSec        = 60;      // Cumulative-delta sliding window (seconds)
input double InpCddMinProfit        = 5.0;     // Only check divergence when unrealized profit > this $ (avoid noise on near-zero positions)

input group "=== Effort-vs-Result on Setup 1 UHV (PDF Phase 2, added 2026-05-01 evening) ==="
input bool   InpSetup1EffortResult  = false;  // Require Setup 1 UHV body ≥ X% of range AND wicks ≤ Y% of range
input double InpEffortBodyMin       = 0.50;   // Body must be ≥ this fraction of range (0.50 = 50%)
input double InpEffortWickMax       = 0.40;   // Each wick must be ≤ this fraction of range (0.40 = 40%)

input group "=== Burst-Specific Stop-Loss (forensic 2026-05-01: prevents catastrophic burst losses) ==="
input double InpBurstSlUsd          = 0.0;    // Tighter SL ($) for BURST trades (0 = disabled, fall back to fearIdeal). Backtest: $15 → 100% chainWR, 0 losing chains.

input group "=== Probe Auto-Trail (2026-05-04: bank profit when filter blocks main fire) ==="
input bool   InpProbeTrailEnabled   = true;   // Auto-trail probes that confirmed but main never fired (filter blocked)
input double InpProbeTrailTrigger   = 3.0;    // Probe peak profit ($) needed before trail arms — must be > probeConfirm so probes that ALREADY fired main don't trail-exit
input double InpProbeTrailDrop      = 1.0;    // $ drop from peak triggers exit — closes orphaned probes at locked profit

input group "=== Mid-Trade Probe-Velocity Monitor (rocket-ship deceleration, 2026-05-02) ==="
input bool   InpMidtradeMonitor      = false; // Enable: while a burst is open, sample probe PnL every N sec; exit burst if velocity drops below threshold
input double InpMidtradeSampleSec    = 1.0;   // Sample probe PnL every N seconds while burst is open
input double InpMidtradeVelThreshold = 0.0;   // Exit burst if probe velocity ($/sec) falls below this (0 = exit on any deceleration)

input group "=== Main No-Green Timeout (2026-05-05: exit mains that never went +profit; prevents fearIdeal trips on faded entries) ==="
input bool   InpMainNoGreenEnabled  = true;   // Exit main early if open >N sec and peak < $X (would have caught -$101 trip on 2026-05-04)
input int    InpMainNoGreenSec      = 60;     // Seconds main can be open without going meaningfully green before forced exit
input double InpMainNoGreenPeakMin  = 3.0;    // Peak ($) required to consider the main as having gone green

input group "=== Machine Gun ==="
input int    InpMaxBurst      = 5;             // Max trades per burst cycle (Shano: up to 5 on strong moves)
input int    InpBurstCooldown = 0;             // Cooldown between bursts (0 = wait for natural new probe)

input group "=== Position Limits ==="
input int    InpMaxPositions  = 3;             // Max simultaneous positions
input double InpDailyCap      = 500.0;         // Stop after this daily profit ($)

input group "=== Lot Sizing ==="
input double InpOverrideLots  = 0.0;           // Override main lot size (0 = auto-calculate)

input group "=== Logging ==="
input string InpLogFile       = "turtle_fills.csv";  // CSV log file (Common\Files)
input string InpOpenLog       = "shano_open_log.csv"; // Richer open-event log with send_ts/intended/actual/latency for slippage calibration
input bool   InpVerbose       = true;          // Verbose journal logging

input group "=== Safety ==="
input int    InpSlippage      = 50;            // Max slippage (points)
input long   InpMagicNumber   = 77777;         // Magic number for EA-opened trades

//+------------------------------------------------------------------+
//| Global State                                                      |
//+------------------------------------------------------------------+
CHashMap<ulong, double>  g_peakMap;           // ticket → peak profit
CHashMap<ulong, bool>    g_probeMap;          // ticket → true (known probes)
CHashMap<ulong, bool>    g_mainMap;           // ticket → true (EA-opened mains)
CHashMap<ulong, ulong>   g_probeToMain;      // probe ticket → main ticket
CHashMap<ulong, datetime> g_probeOpenTime;    // probe ticket → open timestamp (for 50s timeout)

// ── Runtime-tunable config (read from Common\Files\shano_config.json on init + every 5s)
// Allows tuning without reattaching the EA. Falls back to Inp* defaults if JSON missing.
double   g_probeConfirm  = 0.0;
double   g_probeFail     = 0.0;
double   g_probeLots     = 0.0;
int      g_probeTimeout  = 0;
double   g_trailTrigger  = 0.0;
double   g_trailDrop     = 0.0;
double   g_holdLotMax    = 0.0;
double   g_fearIdeal     = 0.0;
double   g_fearWashout   = 0.0;
int      g_maxBurst      = 0;
int      g_burstCooldown = 0;
int      g_maxPositions  = 0;
double   g_dailyCap      = 0.0;
bool     g_sellOnly      = false;
int      g_postBigLossCooldown = 0;             // skip N mains after fearIdeal hit (config)
int      g_dailyBigLossHalt    = 99;            // halt for day after N fearIdeals (99 = off)
bool     g_skipBadHours        = false;         // skip 04-06 + 21-23 broker time (narrowed; NY peak preserved)
bool     g_trendFilter         = false;         // skip AGAINST-trend or NEUTRAL probes
int      g_trendTfMinutes      = 1;             // EMA trend timeframe in minutes (2-min = 95.5% WR backtest)
bool     g_skipFastConfirm     = false;         // skip mains where probe confirmed in 3-8s (fakeout zone)
double   g_overrideLots        = 0.0;           // override main lot size (0 = use balance-tier auto)
bool     g_uhvFilter           = false;         // Shano-Zee: require UHV breakout context for main fire
int      g_uhvLookback         = 20;            // 1-min bars to search for the UHV candle
bool     g_lotLadder           = false;         // Shano-Zee burst pyramid: lot grows per burst
double   g_lotLadderStart      = 0.10;          // First-main lot size in ladder mode
double   g_lotLadderStep       = 0.10;          // Increment per burst
double   g_lotLadderMax        = 0.70;          // Hard cap on ladder lot size
int      g_tickSpeedMaxSec     = 0;             // 0=off; require trigger cross UHV within N sec
double   g_spreadMaxMult       = 0.0;           // 0=off; require spread <= median × X
bool     g_m15TrendFilter      = false;         // Require price above M15 21-EMA (buys) / below (sells)
int      g_chainStopAfterLoss  = 0;             // 0=off; halt after N consecutive losing chains
bool     g_setup1Filter        = false;         // Require Setup 1 M1 pattern recently
int      g_setup1LookbackBars  = 3;             // M1 trigger bars to search
int      g_setup1PatternLookback = 10;          // M1 bars to search for UHV before trigger
bool     g_setup1EffortResult  = false;         // Require UHV body% / wick% on Setup 1 (PDF Phase 2)
double   g_effortBodyMin       = 0.50;          // UHV body must be >= this fraction of range
double   g_effortWickMax       = 0.40;          // Each UHV wick must be <= this fraction of range
double   g_burstSlUsd          = 0.0;           // Tighter SL for burst trades (0 = use fearIdeal)
CHashMap<ulong, bool>     g_isBurstMap;          // ticket → true if this main was opened as a burst (not the first main of chain)
bool     g_probeTrailEnabled   = true;           // Auto-trail probes that confirmed but main never fired
double   g_probeTrailTrigger   = 3.0;            // Probe peak ≥ this → trail arms
double   g_probeTrailDrop      = 1.0;            // Probe drops this much from peak → exit
CHashMap<ulong, double>   g_probePeakMap;        // probe_ticket → peak P&L observed (separate from g_peakMap which is for mains)

// Mid-trade probe-velocity monitor state
bool     g_midtradeMonitor     = false;
double   g_midtradeSampleSec   = 1.0;
double   g_midtradeVelThreshold = 0.0;
ulong    g_chainProbeTicket    = 0;             // Active probe ticket for the current chain (for velocity sampling)
CHashMap<ulong, datetime> g_midtradeLastCheck;   // burst_ticket → last sample time
CHashMap<ulong, double>   g_midtradeLastPnl;     // burst_ticket → probe PnL at last sample

// Main no-green timeout (2026-05-05: prevents fearIdeal trips on instantly-faded entries)
bool     g_mainNoGreenEnabled = true;
int      g_mainNoGreenSec     = 60;
double   g_mainNoGreenPeakMin = 3.0;
CHashMap<ulong, datetime> g_mainOpenTimeMap;     // main_ticket → open time (for never-green age check)
bool     g_burstDeltaFilter    = false;         // Require positive pseudo-delta before each burst-fire
int      g_burstDeltaLookbackSec = 15;          // Rolling window (seconds) for up/down tick count
double   g_triggerPastUhvPts   = 0.0;           // Trigger margin past UHV extreme (PDF#3 deep-mine winner: 0.3pt)
bool     g_cddDivExit          = false;         // Cumulative-delta divergence early-exit
int      g_cddCheckSec         = 10;            // CDD divergence check interval
int      g_cddWindowSec        = 60;            // CDD sliding window (seconds)
double   g_cddMinProfit        = 5.0;           // Only check CDD divergence when in profit > $X

// Per-position state for CDD-div exit (key: position ticket)
CHashMap<ulong, double>   g_cddPriceHwm;        // ticket → highest favorable price
CHashMap<ulong, int>      g_cddDeltaHwm;        // ticket → highest cumulative delta seen at price-HWM
CHashMap<ulong, datetime> g_cddLastCheck;       // ticket → last divergence check time

// Tick-flow ring buffer for pseudo-delta (PDF #3 microstructure, 2026-05-01)
// Stores recent bid samples + timestamps so we can count up-ticks vs down-ticks
// over an arbitrary rolling lookback. Sized for ~120s of dense flow (XAUUSD ~10tps peak)
// to also support CDD-div exit which uses 60s windows.
#define DELTA_BUFFER_SIZE 1200
double   g_deltaBidBuf[DELTA_BUFFER_SIZE];
datetime g_deltaTimeBuf[DELTA_BUFFER_SIZE];
int      g_deltaBufCount = 0;
int      g_deltaBufIdx   = 0;
double   g_deltaLastBid  = 0.0;
int      g_emaM15H             = INVALID_HANDLE;
// Spread baseline tracking (rolling median over last 60 samples, 1 per sec)
#define SPREAD_BUFFER_SIZE 60
double   g_spreadBuffer[SPREAD_BUFFER_SIZE];
int      g_spreadBufferCount   = 0;
int      g_spreadBufferIdx     = 0;
datetime g_lastSpreadSample    = 0;
// Chain-stop tracking
int      g_consecutiveLosingChains = 0;
double   g_currentChainPnl     = 0.0;

// Per-filter contribution telemetry (added 2026-04-30 evening)
// Tracks how many probes hit each filter check, and how many were blocked.
// Reset on midnight (with daily counters) so each day shows fresh stats.
#define FILT_COUNT 12
const string g_filterNames[FILT_COUNT] = {
   "daily_halt",       // 0
   "chain_stop",       // 1
   "big_loss_cooldown",// 2
   "fast_confirm",     // 3
   "bad_hours",        // 4
   "trend_2min",       // 5
   "uhv_breakout",     // 6
   "tick_speed",       // 7
   "spread",           // 8
   "m15_trend",        // 9
   "sell_only",        // 10
   "setup1_hardgate"   // 11
};
int g_filterReached[FILT_COUNT];   // # of times this filter was REACHED (probe got here)
int g_filterBlocked[FILT_COUNT];   // # of times this filter BLOCKED the main
CHashMap<ulong, bool> g_probeMainAttempted;  // probe tickets we've already evaluated
int      g_emaFastH            = INVALID_HANDLE;
int      g_emaSlowH            = INVALID_HANDLE;
int      g_emaTfApplied        = 0;             // currently-applied trend timeframe (re-init handles when changed)
datetime g_lastConfigMtime = 0;

// Big-loss filter STATE (resets at broker midnight)
int      g_postBigLossSkipRemaining = 0;        // skip-counter (decremented per fired main)
int      g_bigLossesToday  = 0;                 // # of fearIdeal hits today
bool     g_haltedToday     = false;             // hard halt flag for today
int      g_lastResetDay    = 0;                 // day-of-year for midnight reset

CTrade g_trade;                                // Trade execution object

// Burst tracking
int      g_burstCount     = 0;                 // Trades fired this burst
datetime g_lastCloseTime  = 0;                 // Last profitable close time
bool     g_burstActive    = false;             // Currently in burst mode
double   g_lastClosePrice = 0;                 // Price at last close (for momentum check)

// Daily tracking
double   g_dailyPnL       = 0.0;              // Realized P&L today
datetime g_dailyReset     = 0;                 // Last reset date

// Stats
int      g_totalExits     = 0;
double   g_totalPnL       = 0.0;
int      g_totalProbes    = 0;
int      g_totalMains     = 0;

// State
bool     g_dailyCapHit    = false;             // Daily cap reached
datetime g_lastLogTime    = 0;                 // Throttle status prints

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
// ── Helpers for parsing flat JSON config ─────────────────────────────────
double JsonGetNumber(string json, string key, double fallback)
{
   string pat = "\"" + key + "\"";
   int pos = StringFind(json, pat);
   if(pos < 0) return fallback;
   pos = StringFind(json, ":", pos);
   if(pos < 0) return fallback;
   pos++;
   int n = StringLen(json);
   while(pos < n) {
      ushort ch = StringGetCharacter(json, pos);
      if(ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r') { pos++; continue; }
      break;
   }
   string num = "";
   while(pos < n) {
      ushort ch = StringGetCharacter(json, pos);
      if((ch >= '0' && ch <= '9') || ch == '.' || ch == '-' || ch == '+' || ch == 'e' || ch == 'E') {
         num += ShortToString(ch);
         pos++;
      } else break;
   }
   if(StringLen(num) == 0) return fallback;
   return StringToDouble(num);
}

bool JsonGetBool(string json, string key, bool fallback)
{
   string pat = "\"" + key + "\"";
   int pos = StringFind(json, pat);
   if(pos < 0) return fallback;
   pos = StringFind(json, ":", pos);
   if(pos < 0) return fallback;
   string rest = StringSubstr(json, pos + 1, 12);
   if(StringFind(rest, "true") >= 0) return true;
   if(StringFind(rest, "false") >= 0) return false;
   return fallback;
}

// Loads tunable config from Common\Files\shano_config.json. Falls back to Inp* defaults.
// initial=true: first load (silent). initial=false: reload (logs changes).
void LoadRuntimeConfig(bool initial)
{
   // Start with Inp* defaults
   double n_probeConfirm  = InpProbeConfirm;
   double n_probeFail     = InpProbeFail;
   double n_probeLots     = InpProbeLots;
   int    n_probeTimeout  = InpProbeTimeout;
   double n_trailTrigger  = InpTrailTrigger;
   double n_trailDrop     = InpTrailDrop;
   double n_holdLotMax    = InpHoldLotMax;
   double n_fearIdeal     = InpFearIdeal;
   double n_fearWashout   = InpFearWashout;
   int    n_maxBurst      = InpMaxBurst;
   int    n_burstCooldown = InpBurstCooldown;
   int    n_maxPositions  = InpMaxPositions;
   double n_dailyCap      = InpDailyCap;
   bool   n_sellOnly      = InpSellOnly;
   int    n_postBigLossCooldown = InpPostBigLossCooldown;
   int    n_dailyBigLossHalt    = InpDailyBigLossHalt;
   bool   n_skipBadHours        = InpSkipBadHours;
   bool   n_trendFilter         = InpTrendFilter;
   int    n_trendTfMinutes      = InpTrendTfMinutes;
   bool   n_skipFastConfirm     = InpSkipFastConfirm;
   double n_overrideLots        = InpOverrideLots;
   bool   n_uhvFilter           = InpUhvFilter;
   int    n_uhvLookback         = InpUhvLookback;
   bool   n_lotLadder           = InpLotLadder;
   double n_lotLadderStart      = InpLotLadderStart;
   double n_lotLadderStep       = InpLotLadderStep;
   double n_lotLadderMax        = InpLotLadderMax;
   int    n_tickSpeedMaxSec     = InpTickSpeedMaxSec;
   double n_spreadMaxMult       = InpSpreadMaxMult;
   bool   n_m15TrendFilter      = InpM15TrendFilter;
   int    n_chainStopAfterLoss  = InpChainStopAfterLoss;
   bool   n_setup1Filter        = InpSetup1Filter;
   int    n_setup1LookbackBars  = InpSetup1LookbackBars;
   int    n_setup1PatternLookback = InpSetup1PatternLookback;
   bool   n_setup1EffortResult  = InpSetup1EffortResult;
   double n_effortBodyMin       = InpEffortBodyMin;
   double n_effortWickMax       = InpEffortWickMax;
   double n_burstSlUsd          = InpBurstSlUsd;
   bool   n_probeTrailEnabled   = InpProbeTrailEnabled;
   double n_probeTrailTrigger   = InpProbeTrailTrigger;
   double n_probeTrailDrop      = InpProbeTrailDrop;
   bool   n_midtradeMonitor     = InpMidtradeMonitor;
   double n_midtradeSampleSec   = InpMidtradeSampleSec;
   double n_midtradeVelThreshold = InpMidtradeVelThreshold;
   bool   n_burstDeltaFilter    = InpBurstDeltaFilter;
   int    n_burstDeltaLookbackSec = InpBurstDeltaLookbackSec;
   double n_triggerPastUhvPts   = InpTriggerPastUhvPts;
   bool   n_cddDivExit          = InpCddDivExit;
   int    n_cddCheckSec         = InpCddCheckSec;
   int    n_cddWindowSec        = InpCddWindowSec;
   double n_cddMinProfit        = InpCddMinProfit;
   bool   n_mainNoGreenEnabled  = InpMainNoGreenEnabled;
   int    n_mainNoGreenSec      = InpMainNoGreenSec;
   double n_mainNoGreenPeakMin  = InpMainNoGreenPeakMin;

   if(FileIsExist("shano_config.json", FILE_COMMON))
   {
      int h = FileOpen("shano_config.json", FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
      if(h != INVALID_HANDLE)
      {
         string content = "";
         while(!FileIsEnding(h)) content += FileReadString(h);
         FileClose(h);

         if(StringLen(content) > 0)
         {
            n_probeConfirm  = JsonGetNumber(content, "probeConfirm",  n_probeConfirm);
            n_probeFail     = JsonGetNumber(content, "probeFail",     n_probeFail);
            n_probeLots     = JsonGetNumber(content, "probeLots",     n_probeLots);
            n_probeTimeout  = (int)JsonGetNumber(content, "probeTimeout", n_probeTimeout);
            n_trailTrigger  = JsonGetNumber(content, "trailTrigger",  n_trailTrigger);
            n_trailDrop     = JsonGetNumber(content, "trailDrop",     n_trailDrop);
            n_holdLotMax    = JsonGetNumber(content, "holdLotMax",    n_holdLotMax);
            n_fearIdeal     = JsonGetNumber(content, "fearIdeal",     n_fearIdeal);
            n_fearWashout   = JsonGetNumber(content, "fearWashout",   n_fearWashout);
            n_maxBurst      = (int)JsonGetNumber(content, "maxBurst",      n_maxBurst);
            n_burstCooldown = (int)JsonGetNumber(content, "burstCooldown", n_burstCooldown);
            n_maxPositions  = (int)JsonGetNumber(content, "maxPositions",  n_maxPositions);
            n_dailyCap      = JsonGetNumber(content, "dailyCap",      n_dailyCap);
            n_sellOnly      = JsonGetBool(content, "sellOnly", n_sellOnly);
            n_postBigLossCooldown = (int)JsonGetNumber(content, "postBigLossCooldown", n_postBigLossCooldown);
            n_dailyBigLossHalt    = (int)JsonGetNumber(content, "dailyBigLossHalt",    n_dailyBigLossHalt);
            n_skipBadHours        = JsonGetBool(content, "skipBadHours", n_skipBadHours);
            n_trendFilter         = JsonGetBool(content, "trendFilter",  n_trendFilter);
            n_trendTfMinutes      = (int)JsonGetNumber(content, "trendTfMinutes", n_trendTfMinutes);
            n_skipFastConfirm     = JsonGetBool(content, "skipFastConfirm", n_skipFastConfirm);
            n_overrideLots        = JsonGetNumber(content, "overrideLots",  n_overrideLots);
            n_uhvFilter           = JsonGetBool(content, "uhvFilter", n_uhvFilter);
            n_uhvLookback         = (int)JsonGetNumber(content, "uhvLookback", n_uhvLookback);
            n_lotLadder           = JsonGetBool(content, "lotLadder", n_lotLadder);
            n_lotLadderStart      = JsonGetNumber(content, "lotLadderStart", n_lotLadderStart);
            n_lotLadderStep       = JsonGetNumber(content, "lotLadderStep", n_lotLadderStep);
            n_lotLadderMax        = JsonGetNumber(content, "lotLadderMax", n_lotLadderMax);
            n_tickSpeedMaxSec     = (int)JsonGetNumber(content, "tickSpeedMaxSec", n_tickSpeedMaxSec);
            n_spreadMaxMult       = JsonGetNumber(content, "spreadMaxMult", n_spreadMaxMult);
            n_m15TrendFilter      = JsonGetBool(content, "m15TrendFilter", n_m15TrendFilter);
            n_chainStopAfterLoss  = (int)JsonGetNumber(content, "chainStopAfterLoss", n_chainStopAfterLoss);
            n_setup1Filter        = JsonGetBool(content, "setup1Filter", n_setup1Filter);
            n_setup1LookbackBars  = (int)JsonGetNumber(content, "setup1LookbackBars", n_setup1LookbackBars);
            n_setup1PatternLookback = (int)JsonGetNumber(content, "setup1PatternLookback", n_setup1PatternLookback);
            n_setup1EffortResult  = JsonGetBool(content, "setup1EffortResult", n_setup1EffortResult);
            n_effortBodyMin       = JsonGetNumber(content, "effortBodyMin", n_effortBodyMin);
            n_effortWickMax       = JsonGetNumber(content, "effortWickMax", n_effortWickMax);
            n_burstSlUsd          = JsonGetNumber(content, "burstSlUsd", n_burstSlUsd);
            n_probeTrailEnabled   = JsonGetBool(content, "probeTrailEnabled", n_probeTrailEnabled);
            n_probeTrailTrigger   = JsonGetNumber(content, "probeTrailTrigger", n_probeTrailTrigger);
            n_probeTrailDrop      = JsonGetNumber(content, "probeTrailDrop", n_probeTrailDrop);
            n_midtradeMonitor     = JsonGetBool(content, "midtradeMonitor", n_midtradeMonitor);
            n_midtradeSampleSec   = JsonGetNumber(content, "midtradeSampleSec", n_midtradeSampleSec);
            n_midtradeVelThreshold = JsonGetNumber(content, "midtradeVelThreshold", n_midtradeVelThreshold);
            n_burstDeltaFilter    = JsonGetBool(content, "burstDeltaFilter", n_burstDeltaFilter);
            n_burstDeltaLookbackSec = (int)JsonGetNumber(content, "burstDeltaLookbackSec", n_burstDeltaLookbackSec);
            n_triggerPastUhvPts   = JsonGetNumber(content, "triggerPastUhvPts", n_triggerPastUhvPts);
            n_cddDivExit          = JsonGetBool(content, "cddDivExit", n_cddDivExit);
            n_cddCheckSec         = (int)JsonGetNumber(content, "cddCheckSec", n_cddCheckSec);
            n_cddWindowSec        = (int)JsonGetNumber(content, "cddWindowSec", n_cddWindowSec);
            n_cddMinProfit        = JsonGetNumber(content, "cddMinProfit", n_cddMinProfit);
            n_mainNoGreenEnabled  = JsonGetBool(content, "mainNoGreenEnabled", n_mainNoGreenEnabled);
            n_mainNoGreenSec      = (int)JsonGetNumber(content, "mainNoGreenSec", n_mainNoGreenSec);
            n_mainNoGreenPeakMin  = JsonGetNumber(content, "mainNoGreenPeakMin", n_mainNoGreenPeakMin);
         }
      }
   }

   // Detect changes (reload only)
   if(!initial)
   {
      bool changed = false;
      if(g_probeFail    != n_probeFail)    { PrintFormat("ShanoEA: config probeFail %.2f -> %.2f",       g_probeFail,    n_probeFail);    changed = true; }
      if(g_fearIdeal    != n_fearIdeal)    { PrintFormat("ShanoEA: config fearIdeal %.0f -> %.0f",       g_fearIdeal,    n_fearIdeal);    changed = true; }
      if(g_fearWashout  != n_fearWashout)  { PrintFormat("ShanoEA: config fearWashout %.0f -> %.0f",     g_fearWashout,  n_fearWashout);  changed = true; }
      if(g_trailTrigger != n_trailTrigger) { PrintFormat("ShanoEA: config trailTrigger %.1f -> %.1f",    g_trailTrigger, n_trailTrigger); changed = true; }
      if(g_trailDrop    != n_trailDrop)    { PrintFormat("ShanoEA: config trailDrop %.1f -> %.1f",       g_trailDrop,    n_trailDrop);    changed = true; }
      if(g_maxBurst     != n_maxBurst)     { PrintFormat("ShanoEA: config maxBurst %d -> %d",            g_maxBurst,     n_maxBurst);     changed = true; }
      if(g_holdLotMax   != n_holdLotMax)   { PrintFormat("ShanoEA: config holdLotMax %.2f -> %.2f",      g_holdLotMax,   n_holdLotMax);   changed = true; }
      if(g_sellOnly     != n_sellOnly)     { PrintFormat("ShanoEA: config sellOnly %s -> %s",
                                                          g_sellOnly?"YES":"NO", n_sellOnly?"YES":"NO"); changed = true; }
      if(g_postBigLossCooldown != n_postBigLossCooldown) { PrintFormat("ShanoEA: config postBigLossCooldown %d -> %d", g_postBigLossCooldown, n_postBigLossCooldown); changed = true; }
      if(g_dailyBigLossHalt    != n_dailyBigLossHalt)    { PrintFormat("ShanoEA: config dailyBigLossHalt %d -> %d",    g_dailyBigLossHalt,    n_dailyBigLossHalt);    changed = true; }
      if(g_skipBadHours        != n_skipBadHours)        { PrintFormat("ShanoEA: config skipBadHours %s -> %s", g_skipBadHours?"YES":"NO", n_skipBadHours?"YES":"NO"); changed = true; }
      if(g_trendFilter         != n_trendFilter)         { PrintFormat("ShanoEA: config trendFilter %s -> %s",  g_trendFilter?"YES":"NO",  n_trendFilter?"YES":"NO");  changed = true; }
      if(g_trendTfMinutes      != n_trendTfMinutes)      { PrintFormat("ShanoEA: config trendTfMinutes %d -> %d", g_trendTfMinutes, n_trendTfMinutes); changed = true; }
      if(g_skipFastConfirm     != n_skipFastConfirm)     { PrintFormat("ShanoEA: config skipFastConfirm %s -> %s", g_skipFastConfirm?"YES":"NO", n_skipFastConfirm?"YES":"NO"); changed = true; }
      if(g_overrideLots        != n_overrideLots)        { PrintFormat("ShanoEA: config overrideLots %.2f -> %.2f", g_overrideLots, n_overrideLots); changed = true; }
      if(g_uhvFilter           != n_uhvFilter)           { PrintFormat("ShanoEA: config uhvFilter %s -> %s", g_uhvFilter?"YES":"NO", n_uhvFilter?"YES":"NO"); changed = true; }
      if(g_uhvLookback         != n_uhvLookback)         { PrintFormat("ShanoEA: config uhvLookback %d -> %d", g_uhvLookback, n_uhvLookback); changed = true; }
      if(g_lotLadder           != n_lotLadder)           { PrintFormat("ShanoEA: config lotLadder %s -> %s", g_lotLadder?"YES":"NO", n_lotLadder?"YES":"NO"); changed = true; }
      if(g_lotLadderStart      != n_lotLadderStart)      { PrintFormat("ShanoEA: config lotLadderStart %.2f -> %.2f", g_lotLadderStart, n_lotLadderStart); changed = true; }
      if(g_lotLadderStep       != n_lotLadderStep)       { PrintFormat("ShanoEA: config lotLadderStep %.2f -> %.2f", g_lotLadderStep, n_lotLadderStep); changed = true; }
      if(g_lotLadderMax        != n_lotLadderMax)        { PrintFormat("ShanoEA: config lotLadderMax %.2f -> %.2f", g_lotLadderMax, n_lotLadderMax); changed = true; }
      if(g_tickSpeedMaxSec     != n_tickSpeedMaxSec)     { PrintFormat("ShanoEA: config tickSpeedMaxSec %d -> %d", g_tickSpeedMaxSec, n_tickSpeedMaxSec); changed = true; }
      if(g_spreadMaxMult       != n_spreadMaxMult)       { PrintFormat("ShanoEA: config spreadMaxMult %.2f -> %.2f", g_spreadMaxMult, n_spreadMaxMult); changed = true; }
      if(g_m15TrendFilter      != n_m15TrendFilter)      { PrintFormat("ShanoEA: config m15TrendFilter %s -> %s", g_m15TrendFilter?"YES":"NO", n_m15TrendFilter?"YES":"NO"); changed = true; }
      if(g_chainStopAfterLoss  != n_chainStopAfterLoss)  { PrintFormat("ShanoEA: config chainStopAfterLoss %d -> %d", g_chainStopAfterLoss, n_chainStopAfterLoss); changed = true; }
      if(g_setup1Filter        != n_setup1Filter)        { PrintFormat("ShanoEA: config setup1Filter %s -> %s", g_setup1Filter?"YES":"NO", n_setup1Filter?"YES":"NO"); changed = true; }
      if(g_setup1LookbackBars  != n_setup1LookbackBars)  { PrintFormat("ShanoEA: config setup1LookbackBars %d -> %d", g_setup1LookbackBars, n_setup1LookbackBars); changed = true; }
      if(g_setup1PatternLookback != n_setup1PatternLookback) { PrintFormat("ShanoEA: config setup1PatternLookback %d -> %d", g_setup1PatternLookback, n_setup1PatternLookback); changed = true; }
      if(g_setup1EffortResult  != n_setup1EffortResult)  { PrintFormat("ShanoEA: config setup1EffortResult %s -> %s", g_setup1EffortResult?"YES":"NO", n_setup1EffortResult?"YES":"NO"); changed = true; }
      if(g_effortBodyMin       != n_effortBodyMin)       { PrintFormat("ShanoEA: config effortBodyMin %.2f -> %.2f", g_effortBodyMin, n_effortBodyMin); changed = true; }
      if(g_effortWickMax       != n_effortWickMax)       { PrintFormat("ShanoEA: config effortWickMax %.2f -> %.2f", g_effortWickMax, n_effortWickMax); changed = true; }
      if(g_burstSlUsd          != n_burstSlUsd)          { PrintFormat("ShanoEA: config burstSlUsd $%.2f -> $%.2f", g_burstSlUsd, n_burstSlUsd); changed = true; }
      if(g_probeTrailEnabled   != n_probeTrailEnabled)   { PrintFormat("ShanoEA: config probeTrailEnabled %s -> %s", g_probeTrailEnabled?"YES":"NO", n_probeTrailEnabled?"YES":"NO"); changed = true; }
      if(g_probeTrailTrigger   != n_probeTrailTrigger)   { PrintFormat("ShanoEA: config probeTrailTrigger $%.2f -> $%.2f", g_probeTrailTrigger, n_probeTrailTrigger); changed = true; }
      if(g_probeTrailDrop      != n_probeTrailDrop)      { PrintFormat("ShanoEA: config probeTrailDrop $%.2f -> $%.2f", g_probeTrailDrop, n_probeTrailDrop); changed = true; }
      if(g_midtradeMonitor     != n_midtradeMonitor)     { PrintFormat("ShanoEA: config midtradeMonitor %s -> %s", g_midtradeMonitor?"YES":"NO", n_midtradeMonitor?"YES":"NO"); changed = true; }
      if(g_midtradeSampleSec   != n_midtradeSampleSec)   { PrintFormat("ShanoEA: config midtradeSampleSec %.2f -> %.2f", g_midtradeSampleSec, n_midtradeSampleSec); changed = true; }
      if(g_midtradeVelThreshold != n_midtradeVelThreshold){ PrintFormat("ShanoEA: config midtradeVelThreshold %.4f -> %.4f", g_midtradeVelThreshold, n_midtradeVelThreshold); changed = true; }
      if(g_burstDeltaFilter      != n_burstDeltaFilter)      { PrintFormat("ShanoEA: config burstDeltaFilter %s -> %s", g_burstDeltaFilter?"YES":"NO", n_burstDeltaFilter?"YES":"NO"); changed = true; }
      if(g_burstDeltaLookbackSec != n_burstDeltaLookbackSec) { PrintFormat("ShanoEA: config burstDeltaLookbackSec %d -> %d", g_burstDeltaLookbackSec, n_burstDeltaLookbackSec); changed = true; }
      if(g_triggerPastUhvPts     != n_triggerPastUhvPts)     { PrintFormat("ShanoEA: config triggerPastUhvPts %.2f -> %.2f", g_triggerPastUhvPts, n_triggerPastUhvPts); changed = true; }
      if(g_cddDivExit            != n_cddDivExit)            { PrintFormat("ShanoEA: config cddDivExit %s -> %s", g_cddDivExit?"YES":"NO", n_cddDivExit?"YES":"NO"); changed = true; }
      if(g_cddCheckSec           != n_cddCheckSec)           { PrintFormat("ShanoEA: config cddCheckSec %d -> %d", g_cddCheckSec, n_cddCheckSec); changed = true; }
      if(g_cddWindowSec          != n_cddWindowSec)          { PrintFormat("ShanoEA: config cddWindowSec %d -> %d", g_cddWindowSec, n_cddWindowSec); changed = true; }
      if(g_cddMinProfit          != n_cddMinProfit)          { PrintFormat("ShanoEA: config cddMinProfit %.2f -> %.2f", g_cddMinProfit, n_cddMinProfit); changed = true; }
      if(g_mainNoGreenEnabled    != n_mainNoGreenEnabled)    { PrintFormat("ShanoEA: config mainNoGreenEnabled %s -> %s", g_mainNoGreenEnabled?"YES":"NO", n_mainNoGreenEnabled?"YES":"NO"); changed = true; }
      if(g_mainNoGreenSec        != n_mainNoGreenSec)        { PrintFormat("ShanoEA: config mainNoGreenSec %d -> %d", g_mainNoGreenSec, n_mainNoGreenSec); changed = true; }
      if(g_mainNoGreenPeakMin    != n_mainNoGreenPeakMin)    { PrintFormat("ShanoEA: config mainNoGreenPeakMin $%.2f -> $%.2f", g_mainNoGreenPeakMin, n_mainNoGreenPeakMin); changed = true; }
   }

   g_probeConfirm  = n_probeConfirm;
   g_probeFail     = n_probeFail;
   g_probeLots     = n_probeLots;
   g_probeTimeout  = n_probeTimeout;
   g_trailTrigger  = n_trailTrigger;
   g_trailDrop     = n_trailDrop;
   g_holdLotMax    = n_holdLotMax;
   g_fearIdeal     = n_fearIdeal;
   g_fearWashout   = n_fearWashout;
   g_maxBurst      = n_maxBurst;
   g_burstCooldown = n_burstCooldown;
   g_maxPositions  = n_maxPositions;
   g_dailyCap      = n_dailyCap;
   g_sellOnly      = n_sellOnly;
   g_postBigLossCooldown = n_postBigLossCooldown;
   g_dailyBigLossHalt    = n_dailyBigLossHalt;
   g_skipBadHours        = n_skipBadHours;
   g_trendFilter         = n_trendFilter;
   g_trendTfMinutes      = n_trendTfMinutes;
   g_skipFastConfirm     = n_skipFastConfirm;
   g_overrideLots        = n_overrideLots;
   g_uhvFilter           = n_uhvFilter;
   g_uhvLookback         = n_uhvLookback;
   g_lotLadder           = n_lotLadder;
   g_lotLadderStart      = n_lotLadderStart;
   g_lotLadderStep       = n_lotLadderStep;
   g_lotLadderMax        = n_lotLadderMax;
   g_tickSpeedMaxSec     = n_tickSpeedMaxSec;
   g_spreadMaxMult       = n_spreadMaxMult;
   g_m15TrendFilter      = n_m15TrendFilter;
   g_chainStopAfterLoss  = n_chainStopAfterLoss;
   g_setup1Filter        = n_setup1Filter;
   g_setup1LookbackBars  = n_setup1LookbackBars;
   g_setup1PatternLookback = n_setup1PatternLookback;
   g_setup1EffortResult  = n_setup1EffortResult;
   g_effortBodyMin       = n_effortBodyMin;
   g_effortWickMax       = n_effortWickMax;
   g_burstSlUsd          = n_burstSlUsd;
   g_probeTrailEnabled   = n_probeTrailEnabled;
   g_probeTrailTrigger   = n_probeTrailTrigger;
   g_probeTrailDrop      = n_probeTrailDrop;
   g_midtradeMonitor     = n_midtradeMonitor;
   g_midtradeSampleSec   = n_midtradeSampleSec;
   g_midtradeVelThreshold = n_midtradeVelThreshold;
   g_burstDeltaFilter    = n_burstDeltaFilter;
   g_burstDeltaLookbackSec = n_burstDeltaLookbackSec;
   g_triggerPastUhvPts   = n_triggerPastUhvPts;
   g_cddDivExit          = n_cddDivExit;
   g_cddCheckSec         = n_cddCheckSec;
   g_cddWindowSec        = n_cddWindowSec;
   g_cddMinProfit        = n_cddMinProfit;
   g_mainNoGreenEnabled  = n_mainNoGreenEnabled;
   g_mainNoGreenSec      = n_mainNoGreenSec;
   g_mainNoGreenPeakMin  = n_mainNoGreenPeakMin;
}

datetime g_lastConfigCheck = 0;

ENUM_TIMEFRAMES TfFromMinutes(int m)
{
   switch(m) {
      case 1:  return PERIOD_M1;
      case 2:  return PERIOD_M2;
      case 3:  return PERIOD_M3;
      case 4:  return PERIOD_M4;
      case 5:  return PERIOD_M5;
      case 6:  return PERIOD_M6;
      case 10: return PERIOD_M10;
      case 12: return PERIOD_M12;
      case 15: return PERIOD_M15;
      case 30: return PERIOD_M30;
      default: return PERIOD_M1;
   }
}

void RebuildEmaHandlesIfNeeded()
{
   if(g_trendTfMinutes == g_emaTfApplied && g_emaFastH != INVALID_HANDLE) return;
   if(g_emaFastH != INVALID_HANDLE) IndicatorRelease(g_emaFastH);
   if(g_emaSlowH != INVALID_HANDLE) IndicatorRelease(g_emaSlowH);
   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
   ENUM_TIMEFRAMES tf = TfFromMinutes(g_trendTfMinutes);
   g_emaFastH = iMA(sym, tf, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   g_emaSlowH = iMA(sym, tf, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   g_emaTfApplied = g_trendTfMinutes;
   PrintFormat("ShanoEA: EMA handles REBUILT for M%d (fast=%d slow=%d)",
              g_trendTfMinutes, InpEmaFast, InpEmaSlow);
}

void CheckConfigReload()
{
   // Re-read JSON every 5 seconds (or on first call). LoadRuntimeConfig logs only on change.
   datetime now = TimeCurrent();
   if(g_lastConfigCheck > 0 && now - g_lastConfigCheck < 5) return;
   g_lastConfigCheck = now;
   LoadRuntimeConfig(false);
   RebuildEmaHandlesIfNeeded();
}

int OnInit()
{
   if(!InpEnabled)
   {
      Print("ShanoEA: DISABLED by input");
      return INIT_SUCCEEDED;
   }

   // Load runtime config (overrides Inp* defaults if shano_config.json exists)
   LoadRuntimeConfig(true);
   if(FileIsExist("shano_config.json", FILE_COMMON)) {
      int h = FileOpen("shano_config.json", FILE_READ|FILE_TXT|FILE_COMMON);
      if(h != INVALID_HANDLE) {
         g_lastConfigMtime = (datetime)FileGetInteger(h, FILE_MODIFY_DATE);
         FileClose(h);
      }
   }

   // Initialize EMA handles for trend filter (released in OnDeinit)
   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
   ENUM_TIMEFRAMES tf = TfFromMinutes(g_trendTfMinutes);
   g_emaFastH = iMA(sym, tf, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   g_emaSlowH = iMA(sym, tf, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   g_emaTfApplied = g_trendTfMinutes;
   if(g_emaFastH == INVALID_HANDLE || g_emaSlowH == INVALID_HANDLE)
      Print("ShanoEA: WARNING — EMA handles failed to init; trend filter will be inert");
   else
      PrintFormat("ShanoEA: EMA handles ready (fast=%d slow=%d on %s M%d)", InpEmaFast, InpEmaSlow, sym, g_trendTfMinutes);

   // M15 21-EMA handle for HTF trend alignment filter
   g_emaM15H = iMA(sym, PERIOD_M15, InpM15EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_emaM15H == INVALID_HANDLE)
      Print("ShanoEA: WARNING — M15 EMA handle failed to init; m15TrendFilter will be inert");
   else
      PrintFormat("ShanoEA: M15 EMA-%d handle ready", InpM15EmaPeriod);

   // Configure trade object
   g_trade.SetDeviationInPoints(InpSlippage);
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   g_trade.SetAsyncMode(false);

   // Initialize CSV file
   InitCSV();

   // Reset daily P&L
   ResetDailyIfNeeded();

   // Scan for any existing positions (in case EA restarted)
   ScanExistingPositions();

   // Heartbeat timer — keeps shano_live.json fresh during quiet markets
   // (maintenance breaks, weekends, low-volume periods where OnTick rarely fires).
   EventSetTimer(1);

   PrintFormat("=== ShanoExitManager v2.00 ACTIVE ===");
   PrintFormat("  Symbol: %s | SellOnly: %s", InpSymbolFilter, InpSellOnly ? "YES" : "NO");
   PrintFormat("  Probe: confirm=$%.2f, fail=$%.2f", InpProbeConfirm, InpProbeFail);
   PrintFormat("  Trail: trigger=$%.1f, drop=$%.1f", InpTrailTrigger, InpTrailDrop);
   PrintFormat("  Burst: max=%d, cooldown=%ds", InpMaxBurst, InpBurstCooldown);
   PrintFormat("  MaxPos: %d | DailyCap: $%.0f", InpMaxPositions, InpDailyCap);
   PrintFormat("  MainLots: %s", InpOverrideLots > 0 ?
              StringFormat("%.2f (override)", InpOverrideLots) : "AUTO");
   PrintFormat("================================");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("ShanoEA: STOPPED | Probes: %d | Mains: %d | Exits: %d | P&L: $%.2f",
              g_totalProbes, g_totalMains, g_totalExits, g_totalPnL);
}

//+------------------------------------------------------------------+
//| TICK HANDLER — Main processing loop                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!InpEnabled) return;

   // Reset daily counters at midnight
   ResetDailyIfNeeded();

   // Spread baseline sampler: 1 sample/sec rolling buffer of 60 samples (=1 min median)
   {
      datetime now = TimeCurrent();
      if(now - g_lastSpreadSample >= 1)
      {
         string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
         double sp = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
         if(sp > 0)
         {
            g_spreadBuffer[g_spreadBufferIdx] = sp;
            g_spreadBufferIdx = (g_spreadBufferIdx + 1) % SPREAD_BUFFER_SIZE;
            if(g_spreadBufferCount < SPREAD_BUFFER_SIZE) g_spreadBufferCount++;
            g_lastSpreadSample = now;
         }
      }
   }

   // Tick-flow ring buffer: store every tick where bid changed (pseudo-delta input)
   {
      string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
      double bid = SymbolInfoDouble(sym, SYMBOL_BID);
      if(bid > 0 && bid != g_deltaLastBid)
      {
         g_deltaBidBuf[g_deltaBufIdx]  = bid;
         g_deltaTimeBuf[g_deltaBufIdx] = TimeCurrent();
         g_deltaBufIdx = (g_deltaBufIdx + 1) % DELTA_BUFFER_SIZE;
         if(g_deltaBufCount < DELTA_BUFFER_SIZE) g_deltaBufCount++;
         g_deltaLastBid = bid;
      }
   }

   // Check if daily cap hit
   if(g_dailyCapHit)
   {
      // Print reminder once per minute
      if(TimeCurrent() - g_lastLogTime > 60)
      {
         PrintFormat("ShanoEA: DAILY CAP HIT ($%.2f >= $%.0f) — paused until midnight",
                    g_dailyPnL, g_dailyCap);
         g_lastLogTime = TimeCurrent();
      }
      return;
   }

   // Check burst cooldown
   CheckBurstCooldown();

   // Process all open positions
   int total = PositionsTotal();
   if(total == 0)
   {
      // No positions — clear maps if stale
      return;
   }

   // Arrays for deferred closes (close big lots first)
   ulong  closeTickets[];
   double closeLots[];
   string closeReasons[];
   int    closeCount = 0;

   for(int i = total - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      // Select position
      if(!PositionSelectByTicket(ticket)) continue;

      // Symbol filter
      string sym = PositionGetString(POSITION_SYMBOL);
      if(InpSymbolFilter != "" && sym != InpSymbolFilter) continue;

      // Direction filter (SELL only)
      long posType = PositionGetInteger(POSITION_TYPE);
      if(g_sellOnly && posType != POSITION_TYPE_SELL) continue;

      double lots   = PositionGetDouble(POSITION_VOLUME);
      double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);

      bool isProbe = false;
      bool isMain  = false;
      g_probeMap.TryGetValue(ticket, isProbe);
      g_mainMap.TryGetValue(ticket, isMain);

      // --- PROBE LOGIC ---
      if(isProbe && !IsProbeConfirmed(ticket))
      {
         // Monitor probe for confirmation or failure
         string probeAction = ProcessProbe(ticket, profit, lots);
         if(probeAction != "")
         {
            // Queue probe for close (failure)
            int idx = closeCount++;
            ArrayResize(closeTickets, closeCount);
            ArrayResize(closeLots, closeCount);
            ArrayResize(closeReasons, closeCount);
            closeTickets[idx] = ticket;
            closeLots[idx]    = lots;
            closeReasons[idx] = probeAction;
         }
         continue;
      }

      // --- MAIN TRADE LOGIC ---
      if(isMain || lots >= 0.02)
      {
         string mainAction = ProcessMainTrade(ticket, profit, lots, sym);
         if(mainAction != "")
         {
            int idx = closeCount++;
            ArrayResize(closeTickets, closeCount);
            ArrayResize(closeLots, closeCount);
            ArrayResize(closeReasons, closeCount);
            closeTickets[idx] = ticket;
            closeLots[idx]    = lots;
            closeReasons[idx] = mainAction;
         }
      }
   }

   // Sort by lot size descending (close biggest FIRST — Shano rule)
   SortCloseQueue(closeTickets, closeLots, closeReasons, closeCount);

   // Execute closes
   for(int i = 0; i < closeCount; i++)
   {
      ClosePosition(closeTickets[i], closeReasons[i]);
   }

   // Dump live state for dashboard (throttled to once per second to avoid I/O storm)
   DumpLiveState();
}

//+------------------------------------------------------------------+
//| OnTimer — heartbeat for the dashboard during quiet markets       |
//| Fires every 1 second regardless of ticks. Keeps shano_live.json  |
//| fresh during maintenance breaks and weekends.                    |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(!InpEnabled) return;
   CheckConfigReload();   // re-reads shano_config.json if mtime changed
   DumpLiveState();
}

//+------------------------------------------------------------------+
//| Dump live state JSON for dashboard consumption                   |
//| Throttled: writes at most once per second.                       |
//+------------------------------------------------------------------+
datetime g_lastDumpTime = 0;

void DumpLiveState()
{
   datetime now = TimeCurrent();
   if(now - g_lastDumpTime < 1) return;
   g_lastDumpTime = now;

   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double free    = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double bid     = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask     = SymbolInfoDouble(sym, SYMBOL_ASK);

   string positions_json = "[";
   bool first = true;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      string psym = PositionGetString(POSITION_SYMBOL);
      if(InpSymbolFilter != "" && psym != InpSymbolFilter) continue;

      long ptype  = PositionGetInteger(POSITION_TYPE);
      double lots = PositionGetDouble(POSITION_VOLUME);
      double opn  = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur  = PositionGetDouble(POSITION_PRICE_CURRENT);
      double prft = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      datetime opt = (datetime)PositionGetInteger(POSITION_TIME);
      string dir  = (ptype == POSITION_TYPE_SELL) ? "sell" : "buy";

      bool isProbe = false;
      bool isMain  = false;
      g_probeMap.TryGetValue(ticket, isProbe);
      g_mainMap.TryGetValue(ticket, isMain);
      string role = isProbe ? "probe" : (isMain ? "main" : "external");

      if(!first) positions_json += ",";
      positions_json += "{";
      positions_json += "\"ticket\":" + IntegerToString(ticket);
      positions_json += ",\"dir\":\"" + dir + "\"";
      positions_json += ",\"lots\":" + DoubleToString(lots, 2);
      positions_json += ",\"entry\":" + DoubleToString(opn, 5);
      positions_json += ",\"current\":" + DoubleToString(cur, 5);
      positions_json += ",\"floating\":" + DoubleToString(prft, 2);
      positions_json += ",\"role\":\"" + role + "\"";
      positions_json += ",\"opened\":\"" + TimeToString(opt, TIME_DATE|TIME_SECONDS) + "\"";
      positions_json += "}";
      first = false;
   }
   positions_json += "]";

   // Build today's closed-deal history. Ground truth — captures every close
   // including manual ones, regardless of whether TurtleTradeLogger logged to CSV.
   // First pass: sum ALL OUT deals for total realized P&L.
   // Second pass: emit latest 30 to JSON for the dashboard recent-trades roller.
   MqlDateTime dt;
   TimeToStruct(now, dt);
   datetime today_start = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00", dt.year, dt.mon, dt.day));
   HistorySelect(today_start, now);
   int deal_count = HistoryDealsTotal();

   double total_realized = 0.0;
   int total_closes = 0;
   // TODAY win/loss counters (mains only, lots > probeLots)
   int today_main_wins = 0, today_main_losses = 0;
   for(int di = 0; di < deal_count; di++)
   {
      ulong dticket = HistoryDealGetTicket(di);
      if(dticket == 0) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      string dsym = HistoryDealGetString(dticket, DEAL_SYMBOL);
      if(InpSymbolFilter != "" && dsym != InpSymbolFilter) continue;
      double dvol = HistoryDealGetDouble(dticket, DEAL_VOLUME);
      double dprft = HistoryDealGetDouble(dticket, DEAL_PROFIT)
                   + HistoryDealGetDouble(dticket, DEAL_SWAP)
                   + HistoryDealGetDouble(dticket, DEAL_COMMISSION);
      total_realized += dprft;
      total_closes++;
      // Mains only (exclude probe-sized 0.01 lots) for win-rate
      if(dvol > 0.011) {
         if(dprft > 0.001) today_main_wins++;
         else if(dprft < -0.001) today_main_losses++;
      }
   }

   // SHANO-ERA stats (last 7 days = covers since Shano EA went live + buffer).
   // Used by dashboard for "all-time WR" — superior to CSV because err=5004 file
   // locks corrupted CSV writes for many trades.
   datetime week_start = now - (7 * 24 * 60 * 60);
   HistorySelect(week_start, now);
   int week_deal_count = HistoryDealsTotal();
   int week_main_wins = 0, week_main_losses = 0;
   double week_realized = 0.0;
   int week_main_closes = 0, week_probe_closes = 0;
   for(int di = 0; di < week_deal_count; di++)
   {
      ulong dticket = HistoryDealGetTicket(di);
      if(dticket == 0) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      string dsym = HistoryDealGetString(dticket, DEAL_SYMBOL);
      if(InpSymbolFilter != "" && dsym != InpSymbolFilter) continue;
      double dvol = HistoryDealGetDouble(dticket, DEAL_VOLUME);
      double dprft = HistoryDealGetDouble(dticket, DEAL_PROFIT)
                   + HistoryDealGetDouble(dticket, DEAL_SWAP)
                   + HistoryDealGetDouble(dticket, DEAL_COMMISSION);
      week_realized += dprft;
      if(dvol > 0.011) {
         week_main_closes++;
         if(dprft > 0.001) week_main_wins++;
         else if(dprft < -0.001) week_main_losses++;
      } else {
         week_probe_closes++;
      }
   }
   // Restore today's HistorySelect for the recent-fills-roller pass below
   HistorySelect(today_start, now);

   string fills_json = "[";
   bool first_fill = true;
   int emitted = 0;
   for(int di = deal_count - 1; di >= 0 && emitted < 30; di--)
   {
      ulong dticket = HistoryDealGetTicket(di);
      if(dticket == 0) continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT) continue;
      string dsym = HistoryDealGetString(dticket, DEAL_SYMBOL);
      if(InpSymbolFilter != "" && dsym != InpSymbolFilter) continue;

      double dvol   = HistoryDealGetDouble(dticket, DEAL_VOLUME);
      double dprice = HistoryDealGetDouble(dticket, DEAL_PRICE);
      double dprft  = HistoryDealGetDouble(dticket, DEAL_PROFIT)
                    + HistoryDealGetDouble(dticket, DEAL_SWAP)
                    + HistoryDealGetDouble(dticket, DEAL_COMMISSION);
      datetime dtime = (datetime)HistoryDealGetInteger(dticket, DEAL_TIME);
      ulong dpos   = HistoryDealGetInteger(dticket, DEAL_POSITION_ID);
      long dtype   = HistoryDealGetInteger(dticket, DEAL_TYPE);
      string posdir = (dtype == DEAL_TYPE_BUY) ? "sell" : "buy";
      string dcomment = HistoryDealGetString(dticket, DEAL_COMMENT);

      if(!first_fill) fills_json += ",";
      fills_json += "{";
      fills_json += "\"time\":\"" + TimeToString(dtime, TIME_DATE|TIME_SECONDS) + "\"";
      fills_json += ",\"ticket\":" + IntegerToString(dpos);
      fills_json += ",\"deal_id\":" + IntegerToString(dticket);
      fills_json += ",\"dir\":\"" + posdir + "\"";
      fills_json += ",\"lots\":" + DoubleToString(dvol, 2);
      fills_json += ",\"price\":" + DoubleToString(dprice, 5);
      fills_json += ",\"pnl\":" + DoubleToString(dprft, 2);
      fills_json += ",\"comment\":\"" + dcomment + "\"";
      fills_json += "}";
      first_fill = false;
      emitted++;
   }
   fills_json += "]";

   string json = "{";
   json += "\"ts\":\""    + TimeToString(now, TIME_DATE|TIME_SECONDS) + "\"";
   json += ",\"symbol\":\"" + sym + "\"";
   json += ",\"balance\":" + DoubleToString(balance, 2);
   json += ",\"equity\":"  + DoubleToString(equity, 2);
   json += ",\"floating\":" + DoubleToString(equity - balance, 2);
   json += ",\"free_margin\":" + DoubleToString(free, 2);
   json += ",\"bid\":"     + DoubleToString(bid, 5);
   json += ",\"ask\":"     + DoubleToString(ask, 5);
   json += ",\"burst_count\":" + IntegerToString(g_burstCount);
   json += ",\"burst_max\":"   + IntegerToString(g_maxBurst);
   json += ",\"burst_active\":" + (g_burstActive ? "true" : "false");
   json += ",\"daily_pnl\":" + DoubleToString(g_dailyPnL, 2);
   json += ",\"realized_today\":" + DoubleToString(total_realized, 2);
   json += ",\"closes_today\":" + IntegerToString(total_closes);
   json += ",\"today_main_wins\":"   + IntegerToString(today_main_wins);
   json += ",\"today_main_losses\":" + IntegerToString(today_main_losses);
   json += ",\"week_main_wins\":"    + IntegerToString(week_main_wins);
   json += ",\"week_main_losses\":"  + IntegerToString(week_main_losses);
   json += ",\"week_main_closes\":"  + IntegerToString(week_main_closes);
   json += ",\"week_probe_closes\":" + IntegerToString(week_probe_closes);
   json += ",\"week_realized\":"     + DoubleToString(week_realized, 2);
   json += ",\"positions\":" + positions_json;

   // Runtime config snapshot — uses LIVE g_* values (overrideable via shano_config.json),
   // NOT Inp* source-defaults. This is what the rule check needs to verify runtime drift.
   string config_json = "{";
   config_json += "\"enabled\":"      + (InpEnabled ? "true" : "false");
   config_json += ",\"symbolFilter\":\"" + InpSymbolFilter + "\"";
   config_json += ",\"sellOnly\":"    + (g_sellOnly ? "true" : "false");
   config_json += ",\"probeConfirm\":" + DoubleToString(g_probeConfirm, 2);
   config_json += ",\"probeFail\":"    + DoubleToString(g_probeFail, 2);
   config_json += ",\"probeLots\":"    + DoubleToString(g_probeLots, 2);
   config_json += ",\"probeTimeout\":" + IntegerToString(g_probeTimeout);
   config_json += ",\"trailTrigger\":" + DoubleToString(g_trailTrigger, 2);
   config_json += ",\"trailDrop\":"    + DoubleToString(g_trailDrop, 2);
   config_json += ",\"catastrophic\":" + DoubleToString(InpCatastrophic, 2);
   config_json += ",\"holdLotMax\":"   + DoubleToString(g_holdLotMax, 2);
   config_json += ",\"fearIdeal\":"    + DoubleToString(g_fearIdeal, 2);
   config_json += ",\"fearWashout\":"  + DoubleToString(g_fearWashout, 2);
   config_json += ",\"maxBurst\":"     + IntegerToString(g_maxBurst);
   config_json += ",\"burstCooldown\":" + IntegerToString(g_burstCooldown);
   config_json += ",\"maxPositions\":" + IntegerToString(g_maxPositions);
   config_json += ",\"dailyCap\":"     + DoubleToString(g_dailyCap, 2);
   config_json += ",\"overrideLots\":" + DoubleToString(g_overrideLots, 2);
   config_json += ",\"postBigLossCooldown\":" + IntegerToString(g_postBigLossCooldown);
   config_json += ",\"dailyBigLossHalt\":"    + IntegerToString(g_dailyBigLossHalt);
   config_json += ",\"bigLossesToday\":"      + IntegerToString(g_bigLossesToday);
   config_json += ",\"haltedToday\":"         + (g_haltedToday ? "true" : "false");
   config_json += ",\"postBigLossSkipRemaining\":" + IntegerToString(g_postBigLossSkipRemaining);
   config_json += ",\"skipBadHours\":"    + (g_skipBadHours ? "true" : "false");
   config_json += ",\"trendFilter\":"     + (g_trendFilter ? "true" : "false");
   config_json += ",\"trendTfMinutes\":"  + IntegerToString(g_trendTfMinutes);
   config_json += ",\"skipFastConfirm\":" + (g_skipFastConfirm ? "true" : "false");
   config_json += ",\"uhvFilter\":"       + (g_uhvFilter ? "true" : "false");
   config_json += ",\"uhvLookback\":"     + IntegerToString(g_uhvLookback);
   config_json += ",\"lotLadder\":"       + (g_lotLadder ? "true" : "false");
   config_json += ",\"lotLadderStart\":"  + DoubleToString(g_lotLadderStart, 2);
   config_json += ",\"lotLadderStep\":"   + DoubleToString(g_lotLadderStep, 2);
   config_json += ",\"lotLadderMax\":"    + DoubleToString(g_lotLadderMax, 2);
   config_json += ",\"tickSpeedMaxSec\":" + IntegerToString(g_tickSpeedMaxSec);
   config_json += ",\"spreadMaxMult\":"   + DoubleToString(g_spreadMaxMult, 2);
   config_json += ",\"m15TrendFilter\":"  + (g_m15TrendFilter ? "true" : "false");
   config_json += ",\"chainStopAfterLoss\":" + IntegerToString(g_chainStopAfterLoss);
   config_json += ",\"consecutiveLosingChains\":" + IntegerToString(g_consecutiveLosingChains);
   config_json += ",\"currentChainPnl\":" + DoubleToString(g_currentChainPnl, 2);
   config_json += ",\"setup1Filter\":"     + (g_setup1Filter ? "true" : "false");
   config_json += ",\"setup1LookbackBars\":" + IntegerToString(g_setup1LookbackBars);
   config_json += ",\"setup1PatternLookback\":" + IntegerToString(g_setup1PatternLookback);
   config_json += ",\"setup1EffortResult\":" + (g_setup1EffortResult ? "true" : "false");
   config_json += ",\"effortBodyMin\":" + DoubleToString(g_effortBodyMin, 2);
   config_json += ",\"effortWickMax\":" + DoubleToString(g_effortWickMax, 2);
   config_json += ",\"burstSlUsd\":" + DoubleToString(g_burstSlUsd, 2);
   config_json += ",\"probeTrailEnabled\":" + (g_probeTrailEnabled ? "true" : "false");
   config_json += ",\"probeTrailTrigger\":" + DoubleToString(g_probeTrailTrigger, 2);
   config_json += ",\"probeTrailDrop\":" + DoubleToString(g_probeTrailDrop, 2);
   config_json += ",\"midtradeMonitor\":" + (g_midtradeMonitor ? "true" : "false");
   config_json += ",\"midtradeSampleSec\":" + DoubleToString(g_midtradeSampleSec, 2);
   config_json += ",\"midtradeVelThreshold\":" + DoubleToString(g_midtradeVelThreshold, 4);
   config_json += ",\"burstDeltaFilter\":" + (g_burstDeltaFilter ? "true" : "false");
   config_json += ",\"burstDeltaLookbackSec\":" + IntegerToString(g_burstDeltaLookbackSec);
   config_json += ",\"triggerPastUhvPts\":" + DoubleToString(g_triggerPastUhvPts, 2);
   config_json += ",\"cddDivExit\":" + (g_cddDivExit ? "true" : "false");
   config_json += ",\"cddCheckSec\":" + IntegerToString(g_cddCheckSec);
   config_json += ",\"cddWindowSec\":" + IntegerToString(g_cddWindowSec);
   config_json += ",\"cddMinProfit\":" + DoubleToString(g_cddMinProfit, 2);
   config_json += ",\"mainNoGreenEnabled\":" + (g_mainNoGreenEnabled ? "true" : "false");
   config_json += ",\"mainNoGreenSec\":" + IntegerToString(g_mainNoGreenSec);
   config_json += ",\"mainNoGreenPeakMin\":" + DoubleToString(g_mainNoGreenPeakMin, 2);
   config_json += ",\"magicNumber\":"  + IntegerToString(InpMagicNumber);
   // Per-filter contribution telemetry
   string filter_stats = "{";
   for(int fi = 0; fi < FILT_COUNT; fi++)
   {
      if(fi > 0) filter_stats += ",";
      filter_stats += "\"" + g_filterNames[fi] + "\":{\"reached\":" + IntegerToString(g_filterReached[fi]) + ",\"blocked\":" + IntegerToString(g_filterBlocked[fi]) + "}";
   }
   filter_stats += "}";
   config_json += ",\"filter_stats\":" + filter_stats;
   config_json += "}";
   json += ",\"config\":" + config_json;
   json += ",\"history\":" + fills_json;
   json += "}";

   int h = FileOpen("shano_live.json", FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h != INVALID_HANDLE)
   {
      FileWriteString(h, json);
      FileClose(h);
   }
}

//+------------------------------------------------------------------+
//| Process probe position                                           |
//+------------------------------------------------------------------+
string ProcessProbe(ulong ticket, double profit, double lots)
{
   // ── PROBE AUTO-TRAIL (added 2026-05-04) ──
   // Track peak P&L for every probe. When peak >= probeTrailTrigger AND main hasn't fired
   // for this probe (filter blocked the escalation), close on probeTrailDrop give-back.
   // This banks profit when a probe orphans because the LIVE filter stack rejected the main fire.
   if(g_probeTrailEnabled && g_probeTrailTrigger > 0)
   {
      double peak = 0;
      if(!g_probePeakMap.TryGetValue(ticket, peak))
         g_probePeakMap.Add(ticket, profit > 0 ? profit : 0);
      if(profit > peak)
      {
         peak = profit;
         g_probePeakMap.TrySetValue(ticket, peak);
      }
      // Only trail-exit if peak armed AND we haven't fired a main for this probe yet
      // (if a main already fired and is open, the probe stays alongside it per Shano's design)
      ulong linkedMain = 0;
      bool hasMain = g_probeToMain.TryGetValue(ticket, linkedMain) && linkedMain > 0;
      if(!hasMain && peak >= g_probeTrailTrigger && (peak - profit) >= g_probeTrailDrop)
      {
         return StringFormat("PROBE_TRAIL pnl=$%.2f peak=$%.2f drop=$%.2f (filter likely blocked main)",
                              profit, peak, peak - profit);
      }
   }

   // Probe CONFIRMED — open main trade
   if(profit >= g_probeConfirm)
   {
      PrintFormat("ShanoEA: PROBE CONFIRMED ticket=%I64u profit=$%.2f >= $%.2f",
                 ticket, profit, g_probeConfirm);

      // Check if we can open more positions
      int currentPos = CountOurPositions();
      if(currentPos >= g_maxPositions)
      {
         PrintFormat("ShanoEA: Cannot open main — max positions reached (%d/%d)",
                    currentPos, g_maxPositions);
         return "";
      }

      // Check burst limit
      if(g_burstActive && g_burstCount >= g_maxBurst)
      {
         PrintFormat("ShanoEA: Cannot open main — burst limit reached (%d/%d)",
                    g_burstCount, g_maxBurst);
         return "";
      }

      // Open main trade
      OpenMainTrade(ticket);
      return ""; // Don't close probe — it stays open alongside main
   }

   // Probe FAILED — cut loss
   if(profit <= -g_probeFail)
   {
      PrintFormat("ShanoEA: PROBE FAILED ticket=%I64u loss=$%.2f <= -$%.2f",
                 ticket, profit, g_probeFail);
      return StringFormat("PROBE_FAIL loss=$%.2f", profit);
   }

   // Probe TIMEOUT — Shano S3: "i wait 50 seconds, still if its in loss, close it"
   if(g_probeTimeout > 0 && profit < 0)
   {
      datetime openTime = 0;
      if(g_probeOpenTime.TryGetValue(ticket, openTime))
      {
         int elapsed = (int)(TimeCurrent() - openTime);
         if(elapsed >= g_probeTimeout)
         {
            PrintFormat("ShanoEA: PROBE TIMEOUT ticket=%I64u elapsed=%ds >= %ds, profit=$%.2f",
                       ticket, elapsed, g_probeTimeout, profit);
            return StringFormat("PROBE_TIMEOUT %ds loss=$%.2f", elapsed, profit);
         }
      }
   }

   return ""; // Still monitoring
}

//+------------------------------------------------------------------+
//| Process main trade position                                      |
//+------------------------------------------------------------------+
string ProcessMainTrade(ulong ticket, double profit, double lots, string sym)
{
   // Get or initialize peak
   double peak = 0;
   if(!g_peakMap.TryGetValue(ticket, peak))
   {
      peak = profit;
      g_peakMap.Add(ticket, peak);
   }

   // Update peak
   if(profit > peak)
   {
      peak = profit;
      g_peakMap.TrySetValue(ticket, peak);
   }

   // --- TRAILING EXIT (always wins if active) ---
   if(peak >= g_trailTrigger)
   {
      double drop = peak - profit;
      if(drop >= g_trailDrop)
      {
         return StringFormat("TRAIL peak=$%.2f now=$%.2f drop=$%.2f", peak, profit, drop);
      }
   }

   // --- CDD-DIVERGENCE EARLY EXIT (PDF#3 deep-mine 2026-05-01) ---
   if(g_cddDivExit && PositionSelectByTicket(ticket))
   {
      long posType = PositionGetInteger(POSITION_TYPE);
      double curPrice = (posType == POSITION_TYPE_BUY)
                        ? SymbolInfoDouble(sym, SYMBOL_BID)
                        : SymbolInfoDouble(sym, SYMBOL_ASK);
      if(CddDivergenceExit(ticket, posType, curPrice, profit))
      {
         return StringFormat("CDD_DIV peak=$%.2f now=$%.2f window=%ds", peak, profit, g_cddWindowSec);
      }
   }

   // --- LOT-SIZE-CONDITIONAL FEAR STOPS (Shano S3 2026-04-27) ---
   // Rule: lots <= 0.10 hold forever, lots > 0.10 apply fear thresholds.
   // Quote: "0.08 wali chalti rahay, 0.01 wali chalti rahay, 0.1 wali bhi chalti rahay,
   //         0.1 se upar wali ko close kar dena behtar hai"
   if(lots > g_holdLotMax)
   {
      // Hard washout-prevention close (Shano: "0.4 wali -180 pe close kar deti hun
      // kyunk else wo pura account wash kar degi")
      if(g_fearWashout > 0 && profit <= -g_fearWashout)
      {
         return StringFormat("WASHOUT lot=%.2f loss=$%.2f <= -$%.0f", lots, profit, g_fearWashout);
      }
      // Burst-specific tighter SL (forensic 2026-05-01: prevents catastrophic burst losses)
      // If this position was opened as a burst AND burstSlUsd > 0, use it instead of fearIdeal.
      bool isBurstPos = false;
      g_isBurstMap.TryGetValue(ticket, isBurstPos);
      if(isBurstPos && g_burstSlUsd > 0 && profit <= -g_burstSlUsd)
      {
         return StringFormat("BURST_SL lot=%.2f loss=$%.2f <= -$%.2f", lots, profit, g_burstSlUsd);
      }

      // Mid-trade probe-velocity monitor (rocket-ship deceleration, 2026-05-02)
      // While a burst is open, sample probe PnL every N sec; exit if velocity drops below threshold.
      if(isBurstPos && g_midtradeMonitor && g_chainProbeTicket > 0)
      {
         datetime now = TimeCurrent();
         datetime lastCheck = 0;
         double lastPnl = 0.0;
         bool hasLast = g_midtradeLastCheck.TryGetValue(ticket, lastCheck);
         double elapsedSec = hasLast ? (double)(now - lastCheck) : 0.0;

         if(!hasLast || elapsedSec >= g_midtradeSampleSec)
         {
            // Sample current probe PnL
            if(PositionSelectByTicket(g_chainProbeTicket))
            {
               double curProbePnl = PositionGetDouble(POSITION_PROFIT);

               if(hasLast && elapsedSec > 0)
               {
                  g_midtradeLastPnl.TryGetValue(ticket, lastPnl);
                  double velocity = (curProbePnl - lastPnl) / elapsedSec;
                  if(velocity < g_midtradeVelThreshold)
                  {
                     return StringFormat("MIDTRADE_DECEL lot=%.2f vel=%.4f$/s < %.4f$/s probePnL=%.2f",
                                          lots, velocity, g_midtradeVelThreshold, curProbePnl);
                  }
               }

               // Update sample
               if(g_midtradeLastCheck.ContainsKey(ticket)) g_midtradeLastCheck.TrySetValue(ticket, now);
               else                                        g_midtradeLastCheck.Add(ticket, now);
               if(g_midtradeLastPnl.ContainsKey(ticket))   g_midtradeLastPnl.TrySetValue(ticket, curProbePnl);
               else                                        g_midtradeLastPnl.Add(ticket, curProbePnl);
            }
         }
      }
      // Main never-green timeout (2026-05-05: prevents fearIdeal trips on faded entries)
      // If main has been open >N sec and peak never reached $X, exit at current loss.
      // Forensic root cause: 2026-05-04 -$101 trip — main entered at 4582.34, never went green,
      // hit fearIdeal in 113s. Catching at age=60 with peak<$3 would have exited near -$50.
      if(g_mainNoGreenEnabled && profit < 0 && peak < g_mainNoGreenPeakMin)
      {
         datetime openTime = 0;
         if(g_mainOpenTimeMap.TryGetValue(ticket, openTime))
         {
            int ageSec = (int)(TimeCurrent() - openTime);
            if(ageSec >= g_mainNoGreenSec)
            {
               return StringFormat("MAIN_NO_GREEN lot=%.2f age=%ds peak=$%.2f profit=$%.2f (never reached $%.2f)",
                                    lots, ageSec, peak, profit, g_mainNoGreenPeakMin);
            }
         }
      }

      // Ideal close (Shano: "-70 pe ideal hota agar hum close kar detay")
      if(g_fearIdeal > 0 && profit <= -g_fearIdeal)
      {
         // Big-loss filter bookkeeping: increment counter, set cooldown, halt if needed.
         // The actual gating happens in OpenMainTrade() before opening the next main.
         g_bigLossesToday += 1;
         if(g_postBigLossCooldown > 0)
            g_postBigLossSkipRemaining = g_postBigLossCooldown;
         if(g_dailyBigLossHalt > 0 && g_dailyBigLossHalt < 99 && g_bigLossesToday >= g_dailyBigLossHalt)
         {
            g_haltedToday = true;
            PrintFormat("ShanoEA: HALTED for the day — %d big losses (>= dailyBigLossHalt=%d). No more main trades until midnight.",
                        g_bigLossesToday, g_dailyBigLossHalt);
         }
         else if(g_postBigLossCooldown > 0)
         {
            PrintFormat("ShanoEA: post-big-loss cooldown set: skip next %d main trades", g_postBigLossSkipRemaining);
         }
         return StringFormat("FEAR_IDEAL lot=%.2f loss=$%.2f <= -$%.0f (today_bigL=%d)",
                              lots, profit, g_fearIdeal, g_bigLossesToday);
      }
   }
   // else: lots <= g_holdLotMax → Shano rule "chalti rahay" — hold until reverse

   // --- CATASTROPHIC LOSS CUT (last-resort safety, applies to ALL lots) ---
   if(InpCatastrophic > 0)
   {
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      double maxLoss = equity * InpCatastrophic;
      if(profit <= -maxLoss)
      {
         return StringFormat("CATASTROPHIC loss=$%.2f (%.0f%% equity)", profit, InpCatastrophic * 100);
      }
   }

   return ""; // Continue holding
}

//+------------------------------------------------------------------+
//| Setup 1 HARD GATE: was Setup 1 (UHV breakout) matching on M1     |
//| within last g_setup1LookbackBars bars?                            |
//| Setup 1 pattern at trigger bar: there's a UHV red bar in prior   |
//| g_setup1PatternLookback bars whose low got swept by an interim   |
//| bar, and the trigger bar is green closing above UHV high (mirror |
//| for sells).                                                       |
//+------------------------------------------------------------------+
bool IsSetup1RecentlyActive(int dirSign)
{
   if(g_setup1LookbackBars <= 0 || g_setup1PatternLookback <= 0) return false;
   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
   int needed = g_setup1LookbackBars + g_setup1PatternLookback + 2;
   double opens[], highs[], lows[], closes[];
   long volumes[];
   ArraySetAsSeries(opens, true);
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);
   ArraySetAsSeries(closes, true);
   ArraySetAsSeries(volumes, true);
   int n_o = CopyOpen(sym, PERIOD_M1, 1, needed, opens);
   int n_h = CopyHigh(sym, PERIOD_M1, 1, needed, highs);
   int n_l = CopyLow(sym, PERIOD_M1, 1, needed, lows);
   int n_c = CopyClose(sym, PERIOD_M1, 1, needed, closes);
   int n_v = CopyTickVolume(sym, PERIOD_M1, 1, needed, volumes);
   if(n_o < needed || n_h < needed || n_l < needed || n_c < needed || n_v < needed) return false;

   // For each potential trigger bar (newest = shift 0):
   for(int trig = 0; trig < g_setup1LookbackBars; trig++)
   {
      // Find UHV (highest-vol matching color) in [trig+1, trig+1+pattern_lookback)
      int uhv_shift = -1; long uhv_vol = -1;
      int s_end = MathMin(needed, trig + 1 + g_setup1PatternLookback);
      for(int s = trig + 1; s < s_end; s++)
      {
         bool isRed = closes[s] < opens[s];
         bool isGreen = closes[s] > opens[s];
         bool match = (dirSign == 1) ? isRed : isGreen;
         if(match && volumes[s] > uhv_vol) { uhv_vol = volumes[s]; uhv_shift = s; }
      }
      if(uhv_shift < 0) continue;

      // Sweep: any bar between uhv_shift-1 (closer to now) and trig+1 broke UHV extreme
      bool swept = false;
      for(int s = uhv_shift - 1; s > trig; s--)
      {
         if(dirSign == 1 && lows[s] < lows[uhv_shift]) { swept = true; break; }
         if(dirSign == -1 && highs[s] > highs[uhv_shift]) { swept = true; break; }
      }
      if(!swept) continue;

      // Effort-vs-Result filter: UHV bar must have body >= 50% of range AND wicks <= 40% of range
      // (Tested 2026-05-01: backtest shows +6.7% WR (84.2% → 90.9%) when this filter is enabled)
      if(g_setup1EffortResult)
      {
         double uhv_o = opens[uhv_shift];
         double uhv_h = highs[uhv_shift];
         double uhv_l = lows[uhv_shift];
         double uhv_c = closes[uhv_shift];
         double uhv_rng = uhv_h - uhv_l;
         if(uhv_rng <= 0) continue;
         double body = MathAbs(uhv_c - uhv_o);
         double upper_wick = uhv_h - MathMax(uhv_o, uhv_c);
         double lower_wick = MathMin(uhv_o, uhv_c) - uhv_l;
         if(body / uhv_rng < g_effortBodyMin) continue;
         if(upper_wick / uhv_rng > g_effortWickMax) continue;
         if(lower_wick / uhv_rng > g_effortWickMax) continue;
      }

      // Trigger candle
      bool isGreenT = closes[trig] > opens[trig];
      bool isRedT = closes[trig] < opens[trig];
      if(dirSign == 1 && isGreenT && closes[trig] > highs[uhv_shift]) return true;
      if(dirSign == -1 && isRedT && closes[trig] < lows[uhv_shift]) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Open main trade (SELL)                                           |
//+------------------------------------------------------------------+
bool OpenMainTrade(ulong probeTicket)
{
   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;

   // De-dup: if we already evaluated this probe and rejected it, skip telemetry +
   // filter checks on subsequent ticks. The probe stays open, riding orphan-style.
   bool alreadyTried = false;
   if(g_probeMainAttempted.TryGetValue(probeTicket, alreadyTried) && alreadyTried)
      return false;
   g_probeMainAttempted.Add(probeTicket, true);  // mark — every subsequent tick skips above

   // ── BIG-LOSS FILTERS (added 2026-04-30) ──
   // Daily halt: after N fearIdeal hits today, no more main trades until midnight.
   g_filterReached[0]++;
   if(g_haltedToday)
   {
      g_filterBlocked[0]++;
      PrintFormat("ShanoEA: SKIP MAIN — halted for day (big losses today: %d >= halt threshold)", g_bigLossesToday);
      return false;
   }
   // Chain-stop: halt new mains after N consecutive losing chains
   g_filterReached[1]++;
   if(g_chainStopAfterLoss > 0 && g_consecutiveLosingChains >= g_chainStopAfterLoss)
   {
      g_filterBlocked[1]++;
      PrintFormat("ShanoEA: SKIP MAIN — chain-stop active (%d consecutive losing chains >= %d threshold)",
                 g_consecutiveLosingChains, g_chainStopAfterLoss);
      return false;
   }
   // Post-big-loss cooldown: skip the next N mains after a fearIdeal hit.
   g_filterReached[2]++;
   if(g_postBigLossSkipRemaining > 0)
   {
      g_filterBlocked[2]++;
      PrintFormat("ShanoEA: SKIP MAIN — post-bigloss cooldown active (%d main(s) remaining to skip)", g_postBigLossSkipRemaining);
      g_postBigLossSkipRemaining -= 1;
      return false;
   }
   // Fast-confirm filter (added 2026-04-30 evening): probes that confirm in 3-8s are
   // typically fakeouts (price spike that reverses). 22-fire backtest: this filter
   // contributed to 90.9% WR vs 87.9% baseline.
   if(g_skipFastConfirm)
   {
      g_filterReached[3]++;
      datetime probeOpen = 0;
      if(g_probeOpenTime.TryGetValue(probeTicket, probeOpen) && probeOpen > 0)
      {
         long delaySec = (long)TimeCurrent() - (long)probeOpen;
         if(delaySec >= 3 && delaySec <= 8)
         {
            g_filterBlocked[3]++;
            PrintFormat("ShanoEA: SKIP MAIN — fast-confirm filter (probe confirmed in %lds, fakeout zone)", delaySec);
            return false;
         }
      }
   }

   // Bad-hours filter (NARROWED 2026-04-30 evening): skip ONLY 04-06 + 21-23 broker.
   // Originally 19-23 but 19-20 broker IS NY peak (75% WR per per-hour analysis).
   // 21-23 are post-NY chop hours (33-40% WR). 04-06 are pre-Tokyo thin Asia (0-20% WR).
   if(g_skipBadHours)
   {
      g_filterReached[4]++;
      MqlDateTime dt; TimeCurrent(dt);
      int h = dt.hour;
      if((h >= 4 && h <= 6) || (h >= 21 && h <= 23))
      {
         g_filterBlocked[4]++;
         PrintFormat("ShanoEA: SKIP MAIN — bad hour filter (broker hour %d in low-liquidity window)", h);
         return false;
      }
   }

   // Trend filter (added 2026-04-30 evening): skip if probe direction is AGAINST the
   // EMA-34/89 trend on 1-min XAUUSD, OR if trend is NEUTRAL (chop zone). Backtest
   // 68 confirmed probes: hour-narrow + trend filter -> +$401 / 88.5% WR / both days+.
   if(g_trendFilter && g_emaFastH != INVALID_HANDLE && g_emaSlowH != INVALID_HANDLE)
   {
      double bufF[], bufS[];
      ArraySetAsSeries(bufF, true);
      ArraySetAsSeries(bufS, true);
      if(CopyBuffer(g_emaFastH, 0, 0, 2, bufF) >= 2 && CopyBuffer(g_emaSlowH, 0, 0, 1, bufS) >= 1)
      {
         g_filterReached[5]++;
         double fast_now  = bufF[0];
         double fast_prev = bufF[1];
         double slow_now  = bufS[0];
         double price     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         bool above = price > fast_now && fast_now > slow_now;
         bool below = price < fast_now && fast_now < slow_now;
         bool rising  = fast_now > fast_prev;
         bool falling = fast_now < fast_prev;
         int trend = (above && rising) ? 1 : (below && falling) ? -1 : 0;  // 1=up, -1=down, 0=neutral
         // Determine probe direction sign (1=buy, -1=sell)
         long probeType = -1;
         if(PositionSelectByTicket(probeTicket))
            probeType = PositionGetInteger(POSITION_TYPE);
         int probeDir = (probeType == POSITION_TYPE_BUY) ? 1 : (probeType == POSITION_TYPE_SELL) ? -1 : 0;
         if(trend == 0)
         {
            g_filterBlocked[5]++;
            PrintFormat("ShanoEA: SKIP MAIN — trend filter (NEUTRAL chop zone, EMA-34=%.2f EMA-89=%.2f)",
                        fast_now, slow_now);
            return false;
         }
         if(trend != probeDir)
         {
            g_filterBlocked[5]++;
            string trStr = (trend == 1) ? "UP" : "DOWN";
            string pdStr = (probeDir == 1) ? "BUY" : "SELL";
            PrintFormat("ShanoEA: SKIP MAIN — trend filter (probe %s AGAINST trend %s)", pdStr, trStr);
            return false;
         }
      }
   }

   // Look up the probe's direction so the main matches it.
   // Shano's rule (2026-04-28, in person): "probe must be in the direction of the main".
   // Without this lookup the EA used to hardcode SELL, which silently broke when sellOnly
   // was disabled and BUY probes started firing.
   long probeType = -1;
   if(PositionSelectByTicket(probeTicket))
      probeType = PositionGetInteger(POSITION_TYPE);

   if(probeType != POSITION_TYPE_SELL && probeType != POSITION_TYPE_BUY)
   {
      PrintFormat("ShanoEA: ABORT MAIN — cannot read probe direction (ticket=%I64u). Skipping rather than opening wrong-direction main.", probeTicket);
      return false;
   }

   // Shano-Zee UHV breakout filter (added 2026-04-30): the trigger candle (last
   // closed 1-min bar) must close BEYOND the high/low of the highest-tick-volume
   // candle in the last N minutes. Backtest 2-day: 15/15 100% WR, $0 max loss.
   if(g_uhvFilter)
   {
      string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;
      int lb = MathMax(5, MathMin(g_uhvLookback, 60));
      long volumes[]; double highs[], lows[], closes[];
      ArraySetAsSeries(volumes, true);
      ArraySetAsSeries(highs, true);
      ArraySetAsSeries(lows, true);
      ArraySetAsSeries(closes, true);
      // We need lb+1 bars: bar 1 = trigger, bars 2..lb+1 = lookback for UHV
      int needed = lb + 1;
      int nv = CopyTickVolume(sym, PERIOD_M1, 1, needed, volumes);
      int nh = CopyHigh(sym, PERIOD_M1, 1, needed, highs);
      int nl = CopyLow(sym, PERIOD_M1, 1, needed, lows);
      int nc = CopyClose(sym, PERIOD_M1, 1, 1, closes);
      if(nv < needed || nh < needed || nl < needed || nc < 1)
      {
         PrintFormat("ShanoEA: SKIP MAIN — UHV filter could not load %d M1 bars (got v=%d h=%d l=%d c=%d)",
                    needed, nv, nh, nl, nc);
         return false;
      }
      double trigger_close = closes[0];
      // Search bars index 1..lb (= bars 2..lb+1 ago) for max volume
      int uhv_idx = 1;
      for(int i = 2; i <= lb; i++)
         if(volumes[i] > volumes[uhv_idx]) uhv_idx = i;
      double uhv_high = highs[uhv_idx];
      double uhv_low  = lows[uhv_idx];
      bool isBuy = (probeType == POSITION_TYPE_BUY);
      g_filterReached[6]++;
      // Trigger margin (PDF#3 deep-mine 2026-05-01: 0.3pt eliminates losing chains)
      double margin = MathMax(0.0, g_triggerPastUhvPts);
      bool brokeOut = isBuy ? (trigger_close >= uhv_high + margin) : (trigger_close <= uhv_low - margin);
      if(!brokeOut)
      {
         g_filterBlocked[6]++;
         PrintFormat("ShanoEA: SKIP MAIN — UHV filter (trigger close %.2f did NOT break %s of UHV bar %d ago by margin %.2fpt [H=%.2f L=%.2f vol=%I64d])",
                    trigger_close, (isBuy ? "above high" : "below low"),
                    uhv_idx + 1, margin, uhv_high, uhv_low, volumes[uhv_idx]);
         return false;
      }
      PrintFormat("ShanoEA: UHV breakout OK — trigger close %.2f %s UHV bar %d ago by margin %.2fpt [H=%.2f L=%.2f vol=%I64d]",
                 trigger_close, (isBuy ? "ABOVE" : "BELOW"),
                 uhv_idx + 1, margin, uhv_high, uhv_low, volumes[uhv_idx]);

      // ===== BIG STACK FILTER 1: TICK-SPEED =====
      // The trigger candle's close-beyond-UHV must have happened within N seconds of
      // bar open. Slow break = liquidity grab; fast break = real momentum.
      if(g_tickSpeedMaxSec > 0)
      {
         g_filterReached[7]++;
         // Find the trigger bar's open time. Trigger = bar at idx_offset 1 ago.
         datetime now = TimeCurrent();
         datetime currentBarOpen = (now / 60) * 60;  // floor to minute
         datetime triggerBarOpen = currentBarOpen - 60;  // bar before current
         double uhv_extreme = isBuy ? uhv_high : uhv_low;
         MqlTick ticks[];
         int n = CopyTicksRange(sym, ticks, COPY_TICKS_ALL,
                                (long)triggerBarOpen * 1000,
                                (long)(triggerBarOpen + 60) * 1000);
         long crossSec = -1;
         if(n > 0)
         {
            for(int i = 0; i < n; i++)
            {
               double price = isBuy ? ticks[i].ask : ticks[i].bid;
               bool crossed = isBuy ? (price > uhv_extreme) : (price < uhv_extreme);
               if(crossed)
               {
                  crossSec = (long)((ticks[i].time_msc - (long)triggerBarOpen * 1000) / 1000);
                  break;
               }
            }
         }
         if(crossSec < 0)
         {
            g_filterBlocked[7]++;
            PrintFormat("ShanoEA: SKIP MAIN — tick-speed filter (no UHV cross found in trigger bar ticks; n=%d)", n);
            return false;
         }
         if(crossSec > g_tickSpeedMaxSec)
         {
            g_filterBlocked[7]++;
            PrintFormat("ShanoEA: SKIP MAIN — tick-speed filter (UHV cross at %ds > max %ds; slow break)",
                       crossSec, g_tickSpeedMaxSec);
            return false;
         }
         PrintFormat("ShanoEA: tick-speed OK — UHV cross at %ds (max %ds)", crossSec, g_tickSpeedMaxSec);
      }

      // ===== BIG STACK FILTER 2: SPREAD <= baseline × X =====
      if(g_spreadMaxMult > 0 && g_spreadBufferCount >= 10)
      {
         g_filterReached[8]++;
         double currentSpread = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
         // Compute median of buffer
         double sorted[];
         ArrayResize(sorted, g_spreadBufferCount);
         for(int i = 0; i < g_spreadBufferCount; i++) sorted[i] = g_spreadBuffer[i];
         ArraySort(sorted);
         double median = sorted[g_spreadBufferCount / 2];
         if(median > 0 && currentSpread > g_spreadMaxMult * median)
         {
            g_filterBlocked[8]++;
            PrintFormat("ShanoEA: SKIP MAIN — spread filter (current %.5f > %.1fx baseline %.5f)",
                       currentSpread, g_spreadMaxMult, median);
            return false;
         }
      }

      // ===== BIG STACK FILTER 4: SETUP 1 HARD GATE (M1 UHV breakout pattern) =====
      if(g_setup1Filter)
      {
         g_filterReached[11]++;
         int dirSign = (probeType == POSITION_TYPE_BUY) ? 1 : -1;
         if(!IsSetup1RecentlyActive(dirSign))
         {
            g_filterBlocked[11]++;
            PrintFormat("ShanoEA: SKIP MAIN — Setup 1 HARD GATE (no UHV breakout pattern in last %d M1 bars for %s)",
                       g_setup1LookbackBars, dirSign == 1 ? "BUY" : "SELL");
            return false;
         }
         PrintFormat("ShanoEA: Setup 1 confirmed — UHV breakout in last %d M1 bars", g_setup1LookbackBars);
      }

      // ===== BIG STACK FILTER 3: M15 21-EMA TREND ALIGNMENT =====
      if(g_m15TrendFilter && g_emaM15H != INVALID_HANDLE)
      {
         g_filterReached[9]++;
         double bufM15[];
         ArraySetAsSeries(bufM15, true);
         if(CopyBuffer(g_emaM15H, 0, 0, 1, bufM15) >= 1)
         {
            double m15_ema = bufM15[0];
            double price = SymbolInfoDouble(sym, SYMBOL_BID);
            bool aligned = isBuy ? (price > m15_ema) : (price < m15_ema);
            if(!aligned)
            {
               g_filterBlocked[9]++;
               PrintFormat("ShanoEA: SKIP MAIN — M15 trend filter (price %.2f %s M15-21EMA %.2f for %s)",
                          price, (isBuy ? "<=" : ">="), m15_ema, (isBuy ? "BUY" : "SELL"));
               return false;
            }
            PrintFormat("ShanoEA: M15 trend OK — price %.2f %s M15-21EMA %.2f",
                       price, (isBuy ? ">" : "<"), m15_ema);
         }
      }
   }

   bool isSell = (probeType == POSITION_TYPE_SELL);

   g_filterReached[10]++;
   if(g_sellOnly && !isSell)
   {
      g_filterBlocked[10]++;
      PrintFormat("ShanoEA: ABORT MAIN — probe was BUY but sellOnly is true. Skipping.");
      return false;
   }

   // Calculate lot size
   double mainLots = CalculateLotSize();

   // Get bid/ask. SELL fills at bid, BUY fills at ask.
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
   {
      PrintFormat("ShanoEA: ERROR — cannot get bid/ask for %s", sym);
      return false;
   }
   double price = isSell ? bid : ask;

   // Validate lot size
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(mainLots < minLot) mainLots = minLot;
   if(mainLots > maxLot) mainLots = maxLot;
   mainLots = MathFloor(mainLots / lotStep) * lotStep;
   mainLots = NormalizeDouble(mainLots, 2);

   string dirStr = isSell ? "SELL" : "BUY";
   string comment = StringFormat("Shano_Main_Burst%d", g_burstCount + 1);

   PrintFormat("ShanoEA: OPENING MAIN %s %.2f lots %s @ %.5f (probe=%I64u)",
              dirStr, mainLots, sym, price, probeTicket);

   // ── CALIBRATION LOGGING (added 2026-05-02) ──
   // Capture intended price and send timestamp for slippage/latency measurement
   double intended_bid = bid;
   double intended_ask = ask;
   double intended_price_log = price;
   ulong send_us = GetMicrosecondCount();
   datetime send_ts = TimeCurrent();

   bool ok = isSell ? g_trade.Sell(mainLots, sym, price, 0, 0, comment)
                    : g_trade.Buy(mainLots, sym, price, 0, 0, comment);

   if(ok && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      ulong fill_us = GetMicrosecondCount();
      datetime fill_ts = TimeCurrent();
      ulong latency_us = fill_us - send_us;
      double actual_fill = g_trade.ResultPrice();
      double slip_pts = MathAbs(actual_fill - intended_price_log);

      // Get position ticket from the deal
      ulong mainTicket = 0;
      ulong dealTicket = g_trade.ResultDeal();
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
         mainTicket = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);

      // Fallback: use order ticket (works on most netting accounts)
      if(mainTicket == 0)
         mainTicket = g_trade.ResultOrder();

      // Track this as a main trade
      bool exists = false;
      if(!g_mainMap.TryGetValue(mainTicket, exists))
         g_mainMap.Add(mainTicket, true);
      double existPeak = 0;
      if(!g_peakMap.TryGetValue(mainTicket, existPeak))
         g_peakMap.Add(mainTicket, 0.0);

      // Link probe to main trade
      ulong existingMain = 0;
      if(g_probeToMain.TryGetValue(probeTicket, existingMain))
         g_probeToMain.TrySetValue(probeTicket, mainTicket);
      else
         g_probeToMain.Add(probeTicket, mainTicket);

      // Mark this position as first-main (burst_count==0 before increment) or burst
      bool isBurstPos = (g_burstCount > 0);
      bool existsBurst = false;
      if(!g_isBurstMap.TryGetValue(mainTicket, existsBurst))
         g_isBurstMap.Add(mainTicket, isBurstPos);

      // First main of chain: record probe ticket as the chain's "rocket-ship" reference
      if(!isBurstPos)
         g_chainProbeTicket = probeTicket;

      // Update burst
      g_burstCount++;
      g_burstActive = true;
      g_totalMains++;

      PrintFormat("ShanoEA: MAIN OPENED ticket=%I64u deal=%I64u | %.2f lots | burst=%d/%d | %s",
                 mainTicket, dealTicket, mainLots, g_burstCount, g_maxBurst,
                 isBurstPos ? "BURST" : "FIRST_MAIN");

      // Track open time for never-green timeout (2026-05-05)
      if(!g_mainOpenTimeMap.ContainsKey(mainTicket))
         g_mainOpenTimeMap.Add(mainTicket, TimeCurrent());

      // Log to CSV
      LogToCSV(mainTicket, sym, isSell ? "SELL_open" : "BUY_open", mainLots, price, 0, 0, 0, comment);

      // Calibration log: rich open event
      LogOpenWithLatency(mainTicket, sym, isSell ? "SELL" : "BUY", mainLots,
                          send_ts, fill_ts, latency_us,
                          intended_bid, intended_ask, intended_price_log, actual_fill, slip_pts,
                          isBurstPos, comment);

      return true;
   }
   else
   {
      PrintFormat("ShanoEA: MAIN OPEN FAILED retcode=%u err=%s",
                 g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      return false;
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on account balance                       |
//+------------------------------------------------------------------+
double CalculateLotSize()
{
   // Lot ladder takes priority — burst pyramid
   if(g_lotLadder)
   {
      double lots = g_lotLadderStart + g_burstCount * g_lotLadderStep;
      if(lots > g_lotLadderMax) lots = g_lotLadderMax;
      if(lots < 0.01) lots = 0.01;
      return lots;
   }
   if(g_overrideLots > 0)
      return g_overrideLots;
   if(InpOverrideLots > 0)
      return InpOverrideLots;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   if(balance >= 800)  return 0.40;
   if(balance >= 500)  return 0.40;
   if(balance >= 300)  return 0.08;
   if(balance >= 200)  return 0.06;
   if(balance >= 100)  return 0.04;
   return 0.01;
}

//+------------------------------------------------------------------+
//| Close position by ticket                                         |
//+------------------------------------------------------------------+
// Backoff during broker session-change (retcode=10018 MARKET_CLOSED).
// Set when a CLOSE returns 10018; suppresses further close attempts until expiry.
datetime g_marketClosedUntil = 0;

bool ClosePosition(ulong ticket, string reason)
{
   // If broker recently said "market closed", don't spam close attempts (and log lines).
   if(g_marketClosedUntil > 0 && TimeCurrent() < g_marketClosedUntil)
      return false;

   if(!PositionSelectByTicket(ticket))
   {
      if(InpVerbose)
         PrintFormat("ShanoEA: ticket %I64u no longer exists (closed externally?)", ticket);
      CleanupTicket(ticket);
      return false;
   }

   string sym    = PositionGetString(POSITION_SYMBOL);
   double lots   = PositionGetDouble(POSITION_VOLUME);
   long   type   = PositionGetInteger(POSITION_TYPE);
   double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   double commission = 0; // Will be in deal history

   // Determine close price
   double closePrice = 0;
   if(type == POSITION_TYPE_SELL)
      closePrice = SymbolInfoDouble(sym, SYMBOL_ASK);  // Buy back to close short
   else
      closePrice = SymbolInfoDouble(sym, SYMBOL_BID);  // Sell to close long

   PrintFormat("ShanoEA: CLOSING %s %.2f lots %s | %s | profit=$%.2f @ %.5f",
              sym, lots, (type == POSITION_TYPE_SELL ? "SELL" : "BUY"),
              reason, profit, closePrice);

   // Build close request manually for maximum control
   MqlTradeRequest request = {};
   MqlTradeResult  result  = {};

   request.action    = TRADE_ACTION_DEAL;
   request.position  = ticket;
   request.symbol    = sym;
   request.volume    = lots;
   request.deviation = InpSlippage;
   request.comment   = "ShanoExit:" + reason;

   if(type == POSITION_TYPE_SELL)
   {
      request.type  = ORDER_TYPE_BUY;
      request.price = closePrice;
   }
   else
   {
      request.type  = ORDER_TYPE_SELL;
      request.price = closePrice;
   }

   // Try IOC filling first
   request.type_filling = ORDER_FILLING_IOC;

   bool ok = OrderSend(request, result);

   if(!ok || result.retcode != TRADE_RETCODE_DONE)
   {
      // Try FOK filling as fallback
      request.type_filling = ORDER_FILLING_FOK;
      ok = OrderSend(request, result);
   }

   if(ok && result.retcode == TRADE_RETCODE_DONE)
   {
      PrintFormat("ShanoEA: CLOSED ticket=%I64u | %s | $%.2f", ticket, reason, profit);

      // Update stats
      g_totalExits++;
      g_totalPnL += profit;
      g_dailyPnL += profit;

      // Chain-stop tracking: accumulate PnL of all mains in current chain
      if(lots >= 0.02) g_currentChainPnl += profit;

      // Check daily cap
      if(g_dailyPnL >= g_dailyCap)
      {
         g_dailyCapHit = true;
         PrintFormat("ShanoEA: *** DAILY CAP REACHED *** P&L=$%.2f >= $%.0f — STOPPING",
                    g_dailyPnL, g_dailyCap);
      }

      // Record for machine gun logic
      if(profit > 0 && lots >= 0.02)
      {
         g_lastCloseTime  = TimeCurrent();
         g_lastClosePrice = closePrice;

         // Check if we should machine gun
         if(g_burstActive && g_burstCount < g_maxBurst && !g_dailyCapHit)
         {
            MachineGunCheck(sym, type);
         }
      }

      // Log to CSV
      string direction = (type == POSITION_TYPE_SELL) ? "SELL_closed" : "BUY_closed";
      LogToCSV(ticket, sym, direction, lots, closePrice, profit, commission, 0, reason);

      // Close associated probe if this was a main trade
      bool isMain = false;
      if(g_mainMap.TryGetValue(ticket, isMain) && isMain)
      {
         CloseAssociatedProbe(ticket);
      }

      // Cleanup tracking
      CleanupTicket(ticket);

      return true;
   }
   else
   {
      // 10018 = MARKET_CLOSED (broker daily session rollover). Set 90s backoff
      // and log the event ONCE per session-change (subsequent closes are silently skipped).
      if(result.retcode == 10018)
      {
         if(g_marketClosedUntil <= TimeCurrent())
         {
            g_marketClosedUntil = TimeCurrent() + 90;
            PrintFormat("ShanoEA: MARKET CLOSED (retcode=10018) — suppressing close attempts for 90s on all tickets (first hit ticket=%I64u)", ticket);
         }
         return false;
      }
      PrintFormat("ShanoEA: CLOSE FAILED ticket=%I64u retcode=%u (%s)",
                 ticket, result.retcode,
                 result.retcode == 10004 ? "REQUOTE" :
                 result.retcode == 10006 ? "REJECTED" :
                 result.retcode == 10014 ? "INVALID_VOLUME" :
                 result.retcode == 10015 ? "INVALID_PRICE" :
                 "OTHER");
      return false;
   }
}

//+------------------------------------------------------------------+
//| Machine gun check — should we reopen immediately?                |
//+------------------------------------------------------------------+
// Burst-time filter check — same gates as ShouldOpenMain, adapted for "continuation"
// (no probe trigger candle, so UHV check is "is current price still beyond UHV extreme")
// Cumulative delta in direction over last lookbackSec (PDF#3 deep-mine helper).
// Returns up_ticks - down_ticks for BUY, down_ticks - up_ticks for SELL.
// Returns 0 if buffer empty / too sparse.
int CumDeltaInWindow(long dirType, int lookbackSec)
{
   if(g_deltaBufCount < 2) return 0;
   datetime now = TimeCurrent();
   datetime cutoff = now - lookbackSec;
   int up = 0, down = 0;
   int newest = (g_deltaBufIdx - 1 + DELTA_BUFFER_SIZE) % DELTA_BUFFER_SIZE;
   if(g_deltaTimeBuf[newest] < cutoff) return 0;
   double prev = g_deltaBidBuf[newest];
   int steps = MathMin(g_deltaBufCount - 1, DELTA_BUFFER_SIZE - 1);
   for(int i = 1; i <= steps; i++)
   {
      int idx = (newest - i + DELTA_BUFFER_SIZE) % DELTA_BUFFER_SIZE;
      if(g_deltaTimeBuf[idx] < cutoff) break;
      double b = g_deltaBidBuf[idx];
      if(prev > b)      up++;
      else if(prev < b) down++;
      prev = b;
   }
   if(up + down < 2) return 0;
   return (dirType == POSITION_TYPE_BUY) ? (up - down) : (down - up);
}

// CDD divergence exit (PDF#3 deep-mine winner: 10s check, 60s window adds +$50/0.3% WR).
// During open trade, when in profit > minProfit, every checkSec, compare price-HWM and cumDelta-HWM.
// If price made a new HWM but cumDelta didn't → divergence → caller exits.
// Returns true if divergence detected.
bool CddDivergenceExit(ulong ticket, long dirType, double currentPrice, double profit)
{
   if(!g_cddDivExit) return false;
   if(profit < g_cddMinProfit) return false;
   datetime now = TimeCurrent();
   datetime lastCheck;
   if(!g_cddLastCheck.TryGetValue(ticket, lastCheck))
   {
      g_cddLastCheck.Add(ticket, now);
      g_cddPriceHwm.Add(ticket, currentPrice);
      g_cddDeltaHwm.Add(ticket, 0);
      return false;
   }
   if(now - lastCheck < g_cddCheckSec) return false;
   g_cddLastCheck.TrySetValue(ticket, now);
   int curCumDelta = CumDeltaInWindow(dirType, g_cddWindowSec);
   double priceHwm = currentPrice;
   int deltaHwm = 0;
   g_cddPriceHwm.TryGetValue(ticket, priceHwm);
   g_cddDeltaHwm.TryGetValue(ticket, deltaHwm);
   bool isBuy = (dirType == POSITION_TYPE_BUY);
   bool newPriceHwm = isBuy ? (currentPrice > priceHwm) : (currentPrice < priceHwm);
   if(newPriceHwm)
   {
      if(curCumDelta < deltaHwm)
      {
         PrintFormat("ShanoEA: CDD-DIV exit ticket=%I64u price-HWM=%.2f→%.2f but cumDelta(%ds)=%d < HWM=%d",
                    ticket, priceHwm, currentPrice, g_cddWindowSec, curCumDelta, deltaHwm);
         return true;
      }
      g_cddPriceHwm.TrySetValue(ticket, currentPrice);
      g_cddDeltaHwm.TrySetValue(ticket, curCumDelta);
   }
   else if(curCumDelta > deltaHwm)
   {
      g_cddDeltaHwm.TrySetValue(ticket, curCumDelta);
   }
   return false;
}

// Pseudo-delta: count up-ticks vs down-ticks in last lookbackSec, return true if
// flow agrees with direction (BUY: up>down. SELL: down>up). Returns true if buffer
// too small to evaluate (fail-open during warm-up).
bool BurstDeltaPositive(long dirType, int lookbackSec)
{
   if(g_deltaBufCount < 4) return true;  // warm-up: not enough samples yet
   datetime now = TimeCurrent();
   datetime cutoff = now - lookbackSec;
   int up = 0, down = 0;
   // Walk newest → oldest. Buffer is circular; idx is next-write slot.
   int newest = (g_deltaBufIdx - 1 + DELTA_BUFFER_SIZE) % DELTA_BUFFER_SIZE;
   double prev = g_deltaBidBuf[newest];
   datetime prevT = g_deltaTimeBuf[newest];
   if(prevT < cutoff) return true;  // newest sample older than lookback (stale)
   int steps = MathMin(g_deltaBufCount - 1, DELTA_BUFFER_SIZE - 1);
   for(int i = 1; i <= steps; i++)
   {
      int idx = (newest - i + DELTA_BUFFER_SIZE) % DELTA_BUFFER_SIZE;
      datetime t = g_deltaTimeBuf[idx];
      if(t < cutoff) break;
      double b = g_deltaBidBuf[idx];
      if(prev > b)      up++;
      else if(prev < b) down++;
      prev = b;
   }
   if(up + down < 3) return true;  // too sparse to judge
   int dirSign = (dirType == POSITION_TYPE_BUY) ? 1 : -1;
   int delta = (dirSign == 1) ? (up - down) : (down - up);
   return delta > 0;
}

bool BurstFiltersAllow(string sym, long dirType)
{
   // Hour filter
   if(g_skipBadHours)
   {
      MqlDateTime dt; TimeCurrent(dt);
      int h = dt.hour;
      if((h >= 4 && h <= 6) || (h >= 21 && h <= 23))
      {
         PrintFormat("ShanoEA: BURST SKIP — bad hour (%d)", h);
         return false;
      }
   }

   // Trend filter (2-min EMA-34/89 still aligned with direction)
   if(g_trendFilter && g_emaFastH != INVALID_HANDLE && g_emaSlowH != INVALID_HANDLE)
   {
      double bufF[], bufS[];
      ArraySetAsSeries(bufF, true);
      ArraySetAsSeries(bufS, true);
      if(CopyBuffer(g_emaFastH, 0, 0, 2, bufF) >= 2 && CopyBuffer(g_emaSlowH, 0, 0, 1, bufS) >= 1)
      {
         double f = bufF[0], fp = bufF[1], s = bufS[0];
         double price = SymbolInfoDouble(sym, SYMBOL_BID);
         bool above = price > f && f > s;
         bool below = price < f && f < s;
         int trend = (above && f > fp) ? 1 : (below && f < fp) ? -1 : 0;
         int dirSign = (dirType == POSITION_TYPE_BUY) ? 1 : -1;
         if(trend == 0 || trend != dirSign)
         {
            PrintFormat("ShanoEA: BURST SKIP — trend (trend=%d dir=%d)", trend, dirSign);
            return false;
         }
      }
   }

   // UHV continuation: current price must still be BEYOND the UHV bar's extreme.
   // For buy continuation: price > UHV high (still extending). For sell: price < UHV low.
   if(g_uhvFilter)
   {
      int lb = MathMax(5, MathMin(g_uhvLookback, 60));
      long volumes[]; double highs[], lows[];
      ArraySetAsSeries(volumes, true);
      ArraySetAsSeries(highs, true);
      ArraySetAsSeries(lows, true);
      int needed = lb + 1;
      int nv = CopyTickVolume(sym, PERIOD_M1, 1, needed, volumes);
      int nh = CopyHigh(sym, PERIOD_M1, 1, needed, highs);
      int nl = CopyLow(sym, PERIOD_M1, 1, needed, lows);
      if(nv < needed || nh < needed || nl < needed)
      {
         PrintFormat("ShanoEA: BURST SKIP — UHV no history");
         return false;
      }
      // Find UHV (max volume in bars 1..lb, ie the recent activity zone)
      int uhv_idx = 1;
      for(int i = 2; i <= lb; i++)
         if(volumes[i] > volumes[uhv_idx]) uhv_idx = i;
      double uhv_high = highs[uhv_idx];
      double uhv_low  = lows[uhv_idx];
      double price = SymbolInfoDouble(sym, (dirType == POSITION_TYPE_BUY) ? SYMBOL_ASK : SYMBOL_BID);
      bool stillExtending = (dirType == POSITION_TYPE_BUY) ? (price > uhv_high) : (price < uhv_low);
      if(!stillExtending)
      {
         PrintFormat("ShanoEA: BURST SKIP — UHV no longer extending (price=%.2f UHV[H=%.2f L=%.2f])",
                    price, uhv_high, uhv_low);
         return false;
      }
   }

   // Burst-delta filter: require positive pseudo-delta (flow agrees with chain dir)
   // Backtest 2026-05-01: lb=15s gives +$246 over baseline, drops losing chains 4→1
   if(g_burstDeltaFilter)
   {
      int lb = MathMax(5, MathMin(g_burstDeltaLookbackSec, 60));
      if(!BurstDeltaPositive(dirType, lb))
      {
         PrintFormat("ShanoEA: BURST SKIP — pseudo-delta against direction (lb=%ds)", lb);
         return false;
      }
   }
   return true;
}

void MachineGunCheck(string sym, long closedType)
{
   // Direction guard: respect sellOnly setting
   if(g_sellOnly && closedType != POSITION_TYPE_SELL) return;

   // Position-count guard
   if(CountOurPositions() >= g_maxPositions) return;

   // Apply Shano-Zee filters before bursting
   if(!BurstFiltersAllow(sym, closedType)) return;

   PrintFormat("ShanoEA: BURST OK — re-firing %s (burst %d/%d)",
              (closedType == POSITION_TYPE_BUY) ? "BUY" : "SELL",
              g_burstCount + 1, g_maxBurst);
   OpenMachineGunTrade(sym, closedType);
}

//+------------------------------------------------------------------+
//| Open machine gun trade (direct, no probe needed)                 |
//+------------------------------------------------------------------+
bool OpenMachineGunTrade(string sym, long dirType = POSITION_TYPE_SELL)
{
   double mainLots = CalculateLotSize();
   bool isBuy = (dirType == POSITION_TYPE_BUY);
   double price = SymbolInfoDouble(sym, isBuy ? SYMBOL_ASK : SYMBOL_BID);

   if(price <= 0) return false;

   // Validate lots
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(mainLots < minLot) mainLots = minLot;
   if(mainLots > maxLot) mainLots = maxLot;
   mainLots = MathFloor(mainLots / lotStep) * lotStep;
   mainLots = NormalizeDouble(mainLots, 2);

   string comment = StringFormat("Shano_MG_Burst%d", g_burstCount + 1);

   // ── CALIBRATION LOGGING ──
   double mg_intended_bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double mg_intended_ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   ulong mg_send_us = GetMicrosecondCount();
   datetime mg_send_ts = TimeCurrent();

   bool ok = isBuy ? g_trade.Buy(mainLots, sym, price, 0, 0, comment)
                   : g_trade.Sell(mainLots, sym, price, 0, 0, comment);

   if(ok && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      ulong mg_fill_us = GetMicrosecondCount();
      datetime mg_fill_ts = TimeCurrent();
      ulong mg_latency_us = mg_fill_us - mg_send_us;
      double mg_actual_fill = g_trade.ResultPrice();
      double mg_slip_pts = MathAbs(mg_actual_fill - price);

      // Get position ticket from deal
      ulong mgTicket = 0;
      ulong dealTicket = g_trade.ResultDeal();
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
         mgTicket = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      if(mgTicket == 0)
         mgTicket = g_trade.ResultOrder();

      bool exists = false;
      if(!g_mainMap.TryGetValue(mgTicket, exists))
         g_mainMap.Add(mgTicket, true);
      double existPeak = 0;
      if(!g_peakMap.TryGetValue(mgTicket, existPeak))
         g_peakMap.Add(mgTicket, 0.0);

      // Mark as burst (machine-gun mains are always bursts — first-main path is OpenMainTrade)
      bool existsBurstMg = false;
      if(!g_isBurstMap.TryGetValue(mgTicket, existsBurstMg))
         g_isBurstMap.Add(mgTicket, true);

      g_burstCount++;
      g_totalMains++;

      PrintFormat("ShanoEA: MACHINE GUN OPENED ticket=%I64u | %s %.2f lots | burst=%d/%d",
                 mgTicket, isBuy ? "BUY" : "SELL", mainLots, g_burstCount, g_maxBurst);

      // Track open time for never-green timeout (2026-05-05)
      if(!g_mainOpenTimeMap.ContainsKey(mgTicket))
         g_mainOpenTimeMap.Add(mgTicket, TimeCurrent());

      LogToCSV(mgTicket, sym, isBuy ? "BUY_open" : "SELL_open", mainLots, price, 0, 0, 0, comment);
      LogOpenWithLatency(mgTicket, sym, isBuy ? "BUY" : "SELL", mainLots,
                          mg_send_ts, mg_fill_ts, mg_latency_us,
                          mg_intended_bid, mg_intended_ask, price, mg_actual_fill, mg_slip_pts,
                          true, comment);   // MG always bursts
      return true;
   }
   else
   {
      PrintFormat("ShanoEA: MACHINE GUN FAILED retcode=%u", g_trade.ResultRetcode());
      return false;
   }
}

//+------------------------------------------------------------------+
//| Close the probe associated with a main trade                     |
//+------------------------------------------------------------------+
void CloseAssociatedProbe(ulong mainTicket)
{
   // Scan all open positions for the probe linked to this main
   int total = PositionsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      // Check if this is a known probe
      bool isProbe = false;
      if(!g_probeMap.TryGetValue(ticket, isProbe)) continue;
      if(!isProbe) continue;

      // Check if this probe is linked to the closed main
      ulong linkedMain = 0;
      if(g_probeToMain.TryGetValue(ticket, linkedMain))
      {
         if(linkedMain == mainTicket)
         {
            PrintFormat("ShanoEA: Closing associated probe ticket=%I64u", ticket);
            ClosePosition(ticket, "PROBE_CLOSE_WITH_MAIN");
            break;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Trade transaction handler — detect new PineConnector probes      |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result)
{
   if(!InpEnabled) return;

   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      if(!HistoryDealSelect(trans.deal)) return;

      long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

      // New position opened
      if(entry == DEAL_ENTRY_IN)
      {
         ulong  posTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
         string symbol    = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
         double volume    = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
         long   dealType  = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
         long   magic     = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
         string comment   = HistoryDealGetString(trans.deal, DEAL_COMMENT);

         // Symbol filter
         if(InpSymbolFilter != "" && symbol != InpSymbolFilter) return;

         // Direction filter
         if(g_sellOnly && dealType != DEAL_TYPE_SELL) return;

         // Skip our own trades (magic number match)
         if(magic == InpMagicNumber) return;

         // Detect probe: small lot size opened by PineConnector or external
         if(volume <= g_probeLots + 0.001)
         {
            // This is a probe from PineConnector!
            bool exists = false;
            if(!g_probeMap.TryGetValue(posTicket, exists))
            {
               g_probeMap.Add(posTicket, true);
               g_peakMap.Add(posTicket, 0.0);
               g_probeOpenTime.Add(posTicket, TimeCurrent());
               g_totalProbes++;

               PrintFormat("ShanoEA: *** NEW PROBE DETECTED *** ticket=%I64u | %s | %.2f lots | comment=%s",
                          posTicket, symbol, volume, comment);
            }
         }
         else
         {
            // Larger position opened externally — track as main for exit management
            bool exists = false;
            if(!g_mainMap.TryGetValue(posTicket, exists))
            {
               g_mainMap.Add(posTicket, true);
               g_peakMap.Add(posTicket, 0.0);

               PrintFormat("ShanoEA: External main detected ticket=%I64u | %.2f lots", posTicket, volume);
            }
         }
      }
      // Position closed (externally)
      else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
      {
         ulong posTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
         CleanupTicket(posTicket);
      }
   }
}

//+------------------------------------------------------------------+
//| Scan existing positions on startup (EA restart recovery)         |
//+------------------------------------------------------------------+
void ScanExistingPositions()
{
   int total = PositionsTotal();

   // First pass — collect probe and main metadata so we can re-link them.
   ulong    probeTickets[];   string  probeSyms[];   long     probeDirs[];
   datetime probeTimes[];     double  probeProfits[];
   ulong    mainTickets[];    string  mainSyms[];    long     mainDirs[];
   datetime mainTimes[];      double  mainProfits[];

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string sym = PositionGetString(POSITION_SYMBOL);
      if(InpSymbolFilter != "" && sym != InpSymbolFilter) continue;

      long     posType = PositionGetInteger(POSITION_TYPE);
      double   lots    = PositionGetDouble(POSITION_VOLUME);
      double   profit  = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      long     magic   = PositionGetInteger(POSITION_MAGIC);
      datetime opened  = (datetime)PositionGetInteger(POSITION_TIME);

      if(g_sellOnly && posType != POSITION_TYPE_SELL) continue;

      if(lots <= g_probeLots + 0.001 && magic != InpMagicNumber)
      {
         int n = ArraySize(probeTickets);
         ArrayResize(probeTickets, n+1); ArrayResize(probeSyms, n+1); ArrayResize(probeDirs, n+1);
         ArrayResize(probeTimes, n+1);   ArrayResize(probeProfits, n+1);
         probeTickets[n] = ticket; probeSyms[n] = sym; probeDirs[n] = posType;
         probeTimes[n] = opened;   probeProfits[n] = profit;
      }
      else if(lots >= 0.02)
      {
         int n = ArraySize(mainTickets);
         ArrayResize(mainTickets, n+1); ArrayResize(mainSyms, n+1); ArrayResize(mainDirs, n+1);
         ArrayResize(mainTimes, n+1);   ArrayResize(mainProfits, n+1);
         mainTickets[n] = ticket; mainSyms[n] = sym; mainDirs[n] = posType;
         mainTimes[n] = opened;   mainProfits[n] = profit;
      }
   }

   // Register mains
   int mainsRegistered = 0;
   for(int i = 0; i < ArraySize(mainTickets); i++)
   {
      ulong t = mainTickets[i]; bool exists = false;
      if(!g_mainMap.TryGetValue(t, exists))
      {
         g_mainMap.Add(t, true);
         g_peakMap.Add(t, mainProfits[i] > 0 ? mainProfits[i] : 0.0);
         mainsRegistered++;
      }
   }

   // Register probes + re-link to matching open main (same sym+dir, opened within 5min after probe)
   int probesRegistered = 0, relinked = 0, orphansClosed = 0;
   for(int i = 0; i < ArraySize(probeTickets); i++)
   {
      ulong probeTicket = probeTickets[i];
      bool exists = false;
      if(!g_probeMap.TryGetValue(probeTicket, exists))
      {
         g_probeMap.Add(probeTicket, true);
         g_peakMap.Add(probeTicket, probeProfits[i] > 0 ? probeProfits[i] : 0.0);
         probesRegistered++;
      }

      bool confirmed = (probeProfits[i] >= g_probeConfirm);

      // Look for the matching main: same sym, same direction, opened <=300s after probe
      ulong matchedMain = 0; long bestDelta = 999999;
      for(int j = 0; j < ArraySize(mainTickets); j++)
      {
         if(mainSyms[j] != probeSyms[i]) continue;
         if(mainDirs[j] != probeDirs[i]) continue;
         long delta = (long)mainTimes[j] - (long)probeTimes[i];
         if(delta < 0 || delta > 300) continue;
         if(delta < bestDelta) { bestDelta = delta; matchedMain = mainTickets[j]; }
      }

      if(matchedMain > 0)
      {
         ulong existing = 0;
         if(g_probeToMain.TryGetValue(probeTicket, existing))
            g_probeToMain.TrySetValue(probeTicket, matchedMain);
         else
            g_probeToMain.Add(probeTicket, matchedMain);
         relinked++;
      }
      else if(confirmed)
      {
         // Confirmed probe with no matching open main. Two cases:
         //  - Old probe whose main already closed → orphan, close to realize PnL.
         //  - Probe that just confirmed during startup → main about to fire on next OnTick.
         // Distinguish by age: probes older than 5min are definitely orphans.
         long age = (long)TimeCurrent() - (long)probeTimes[i];
         if(age >= 300)
         {
            PrintFormat("ShanoEA: ORPHAN PROBE ticket=%I64u age=%lds profit=$%.2f — closing",
                       probeTicket, age, probeProfits[i]);
            ClosePosition(probeTicket, "PROBE_ORPHAN_RECOVERY");
            orphansClosed++;
         }
         else
         {
            // Young confirmed probe — let normal lifecycle handle it.
            MarkProbeConfirmed(probeTicket);
         }
      }
   }

   if(probesRegistered + mainsRegistered + relinked + orphansClosed > 0)
      PrintFormat("ShanoEA: Recovered %d probes + %d mains | re-linked %d | closed %d orphans",
                 probesRegistered, mainsRegistered, relinked, orphansClosed);
}

//+------------------------------------------------------------------+
//| Helper: Is probe already confirmed (main trade opened for it)?   |
//+------------------------------------------------------------------+
bool IsProbeConfirmed(ulong probeTicket)
{
   ulong mainTicket = 0;
   return g_probeToMain.TryGetValue(probeTicket, mainTicket);
}

//+------------------------------------------------------------------+
//| Helper: Mark probe as confirmed                                  |
//+------------------------------------------------------------------+
void MarkProbeConfirmed(ulong probeTicket)
{
   ulong existing = 0;
   if(!g_probeToMain.TryGetValue(probeTicket, existing))
   {
      g_probeToMain.Add(probeTicket, 0); // Will be updated when main opens
   }
}

//+------------------------------------------------------------------+
//| Helper: Count our active positions                               |
//+------------------------------------------------------------------+
int CountOurPositions()
{
   int count = 0;
   int total = PositionsTotal();

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string sym = PositionGetString(POSITION_SYMBOL);
      if(InpSymbolFilter != "" && sym != InpSymbolFilter) continue;

      long posType = PositionGetInteger(POSITION_TYPE);
      if(g_sellOnly && posType != POSITION_TYPE_SELL) continue;

      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Helper: Check and reset burst cooldown                           |
//+------------------------------------------------------------------+
void CheckBurstCooldown()
{
   if(!g_burstActive) return;

   // If no positions open and cooldown elapsed, reset burst
   if(g_lastCloseTime > 0)
   {
      int elapsed = (int)(TimeCurrent() - g_lastCloseTime);
      if(elapsed >= g_burstCooldown && CountOurPositions() == 0)
      {
         // Chain ended — evaluate for chain-stop
         if(g_currentChainPnl < 0)
         {
            g_consecutiveLosingChains++;
            PrintFormat("ShanoEA: Chain ended LOSING ($%.2f) — consecutive losing chains: %d",
                       g_currentChainPnl, g_consecutiveLosingChains);
         }
         else if(g_currentChainPnl > 0)
         {
            if(g_consecutiveLosingChains > 0)
               PrintFormat("ShanoEA: Chain ended WINNING ($%.2f) — resetting consecutive losing chains (was %d)",
                          g_currentChainPnl, g_consecutiveLosingChains);
            g_consecutiveLosingChains = 0;
         }
         g_currentChainPnl = 0.0;
         g_burstActive = false;
         g_burstCount  = 0;
         g_chainProbeTicket = 0;   // clear rocket-ship reference for next chain
         if(InpVerbose)
            PrintFormat("ShanoEA: Burst cooldown elapsed (%ds) — reset for next setup",
                       elapsed);
      }
   }
}

//+------------------------------------------------------------------+
//| Helper: Reset daily P&L at midnight (broker time)                |
//+------------------------------------------------------------------+
void ResetDailyIfNeeded()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00",
                                              dt.year, dt.mon, dt.day));

   if(today > g_dailyReset)
   {
      if(g_dailyPnL != 0 && g_dailyReset > 0)
         PrintFormat("ShanoEA: NEW DAY — yesterday P&L: $%.2f | Resetting", g_dailyPnL);

      g_dailyPnL    = 0.0;
      g_dailyCapHit = false;
      g_dailyReset  = today;
      g_burstCount  = 0;
      g_burstActive = false;

      // Reset filter telemetry on new day
      for(int fi = 0; fi < FILT_COUNT; fi++)
      {
         g_filterReached[fi] = 0;
         g_filterBlocked[fi] = 0;
      }

      // Big-loss filter reset (added 2026-04-30)
      if(g_bigLossesToday > 0 || g_haltedToday)
         PrintFormat("ShanoEA: NEW DAY — resetting big-loss filter state (was: %d big losses, halted=%s)",
                     g_bigLossesToday, g_haltedToday ? "YES" : "no");
      g_bigLossesToday = 0;
      g_haltedToday = false;
      g_postBigLossSkipRemaining = 0;
   }
}

//+------------------------------------------------------------------+
//| Helper: Cleanup all tracking for a ticket                        |
//+------------------------------------------------------------------+
void CleanupTicket(ulong ticket)
{
   g_peakMap.Remove(ticket);
   g_probeMap.Remove(ticket);
   g_probeOpenTime.Remove(ticket);
   g_mainMap.Remove(ticket);
   g_probeToMain.Remove(ticket);
   g_probeMainAttempted.Remove(ticket);
   g_cddPriceHwm.Remove(ticket);
   g_cddDeltaHwm.Remove(ticket);
   g_cddLastCheck.Remove(ticket);
   g_mainOpenTimeMap.Remove(ticket);
}

//+------------------------------------------------------------------+
//| Helper: Sort close queue by lot size descending                  |
//+------------------------------------------------------------------+
void SortCloseQueue(ulong &tickets[], double &lots[], string &reasons[], int count)
{
   for(int i = 0; i < count - 1; i++)
   {
      for(int j = i + 1; j < count; j++)
      {
         if(lots[j] > lots[i])
         {
            // Swap tickets
            ulong tmpT = tickets[i];
            tickets[i] = tickets[j];
            tickets[j] = tmpT;
            // Swap lots
            double tmpL = lots[i];
            lots[i] = lots[j];
            lots[j] = tmpL;
            // Swap reasons
            string tmpR = reasons[i];
            reasons[i] = reasons[j];
            reasons[j] = tmpR;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Initialize CSV file with header                                  |
//+------------------------------------------------------------------+
void InitCSV()
{
   int h = FileOpen(InpLogFile, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h != INVALID_HANDLE)
   {
      if(FileSize(h) == 0)
      {
         FileWriteString(h, "broker_time,deal_ticket,position_ticket,symbol,direction,volume,close_price,profit,commission,swap,net_pnl,comment\n");
         Print("ShanoEA: Created new CSV log with header");
      }
      FileClose(h);
   }
   else
   {
      PrintFormat("ShanoEA: WARNING — could not open %s (err=%d)", InpLogFile, GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Helper: open CSV with retry + backoff (handles transient locks)  |
//| FILE_SHARE flags allow concurrent access, but Windows can still  |
//| briefly refuse if another process is mid-write. Retry 3x at 50ms.|
//+------------------------------------------------------------------+
int OpenCsvWithRetry(const string filename)
{
   const int flags = FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE;
   for(int attempt = 0; attempt < 3; attempt++)
   {
      int h = FileOpen(filename, flags);
      if(h != INVALID_HANDLE)
         return h;
      if(attempt < 2)
         Sleep(50);
   }
   return INVALID_HANDLE;
}

//+------------------------------------------------------------------+
//| Log open event with latency + slippage data (calibration source) |
//| Writes shano_open_log.csv: send_ts, fill_ts, latency_us,         |
//| intended_bid/ask/price, actual fill, slippage in points          |
//+------------------------------------------------------------------+
void LogOpenWithLatency(ulong ticket, string sym, string direction, double lots,
                         datetime send_ts, datetime fill_ts, ulong latency_us,
                         double intended_bid, double intended_ask,
                         double intended_price, double actual_fill, double slip_pts,
                         bool is_burst, string comment)
{
   int h = OpenCsvWithRetry(InpOpenLog);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("ShanoEA: ERROR opening %s err=%d (after 3 retries)", InpOpenLog, GetLastError());
      return;
   }

   // Write header on first use (file is empty)
   if(FileSize(h) == 0)
   {
      FileWriteString(h, "send_ts,fill_ts,latency_us,ticket,symbol,direction,lots,intended_bid,intended_ask,intended_price,actual_fill,slip_pts,is_burst,comment\n");
   }

   FileSeek(h, 0, SEEK_END);

   StringReplace(comment, ",", ";");
   StringReplace(comment, "\n", " ");
   StringReplace(comment, "\r", "");

   string line = StringFormat("%s,%s,%I64u,%I64u,%s,%s,%.2f,%.5f,%.5f,%.5f,%.5f,%.5f,%s,%s\n",
                              TimeToString(send_ts, TIME_DATE|TIME_SECONDS),
                              TimeToString(fill_ts, TIME_DATE|TIME_SECONDS),
                              latency_us, ticket, sym, direction, lots,
                              intended_bid, intended_ask, intended_price, actual_fill, slip_pts,
                              is_burst ? "BURST" : "FIRST", comment);
   FileWriteString(h, line);
   FileClose(h);
}


//+------------------------------------------------------------------+
//| Log trade to CSV (same format as TurtleTradeLogger)              |
//+------------------------------------------------------------------+
void LogToCSV(ulong ticket, string sym, string direction, double volume,
              double price, double profit, double commission, double swap,
              string comment)
{
   int h = OpenCsvWithRetry(InpLogFile);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("ShanoEA: ERROR opening CSV file err=%d (after 3 retries)", GetLastError());
      return;
   }

   FileSeek(h, 0, SEEK_END);

   // Sanitize comment
   StringReplace(comment, ",", ";");
   StringReplace(comment, "\n", " ");
   StringReplace(comment, "\r", "");

   double netPnl = profit + commission + swap;
   string timeStr = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);

   string line = StringFormat("%s,%I64u,%I64u,%s,%s,%.2f,%.5f,%.2f,%.2f,%.2f,%.2f,%s\n",
                              timeStr,
                              (ulong)0, // deal ticket (not available here, filled by logger)
                              ticket,
                              sym,
                              direction,
                              volume,
                              price,
                              profit,
                              commission,
                              swap,
                              netPnl,
                              comment);

   FileWriteString(h, line);
   FileClose(h);
}

//+------------------------------------------------------------------+
//| Chart event handler (for visual feedback)                        |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   // Could add chart button controls here in future
}
//+------------------------------------------------------------------+
