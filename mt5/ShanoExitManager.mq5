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
datetime g_lastConfigMtime = 0;

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
}

datetime g_lastConfigCheck = 0;

void CheckConfigReload()
{
   // Re-read JSON every 5 seconds (or on first call). LoadRuntimeConfig logs only on change.
   datetime now = TimeCurrent();
   if(g_lastConfigCheck > 0 && now - g_lastConfigCheck < 5) return;
   g_lastConfigCheck = now;
   LoadRuntimeConfig(false);
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
   config_json += ",\"overrideLots\":" + DoubleToString(InpOverrideLots, 2);
   config_json += ",\"magicNumber\":"  + IntegerToString(InpMagicNumber);
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
      // Ideal close (Shano: "-70 pe ideal hota agar hum close kar detay")
      if(g_fearIdeal > 0 && profit <= -g_fearIdeal)
      {
         return StringFormat("FEAR_IDEAL lot=%.2f loss=$%.2f <= -$%.0f", lots, profit, g_fearIdeal);
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
//| Open main trade (SELL)                                           |
//+------------------------------------------------------------------+
bool OpenMainTrade(ulong probeTicket)
{
   string sym = InpSymbolFilter != "" ? InpSymbolFilter : _Symbol;

   // Calculate lot size
   double mainLots = CalculateLotSize();

   // Get current BID price for SELL
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   if(bid <= 0)
   {
      PrintFormat("ShanoEA: ERROR — cannot get BID for %s", sym);
      return false;
   }

   // Validate lot size
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(mainLots < minLot) mainLots = minLot;
   if(mainLots > maxLot) mainLots = maxLot;
   mainLots = MathFloor(mainLots / lotStep) * lotStep;
   mainLots = NormalizeDouble(mainLots, 2);

   // Send SELL order
   string comment = StringFormat("Shano_Main_Burst%d", g_burstCount + 1);

   PrintFormat("ShanoEA: OPENING MAIN SELL %.2f lots %s @ %.5f (probe=%I64u)",
              mainLots, sym, bid, probeTicket);

   bool ok = g_trade.Sell(mainLots, sym, bid, 0, 0, comment);

   if(ok && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
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

      // Update burst
      g_burstCount++;
      g_burstActive = true;
      g_totalMains++;

      PrintFormat("ShanoEA: MAIN OPENED ticket=%I64u deal=%I64u | %.2f lots | burst=%d/%d",
                 mainTicket, dealTicket, mainLots, g_burstCount, g_maxBurst);

      // Log to CSV
      LogToCSV(mainTicket, sym, "SELL_open", mainLots, bid, 0, 0, 0, comment);

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
bool ClosePosition(ulong ticket, string reason)
{
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
void MachineGunCheck(string sym, long closedType)
{
   // Only machine gun SELL positions
   if(g_sellOnly && closedType != POSITION_TYPE_SELL) return;

   // Check if momentum still going (price still falling for sell)
   // Machine gun fires immediately — Shano doesn't wait, she fires within seconds

   // For SELL: momentum continues if price is BELOW where we closed
   // (we closed by buying at ASK, price should be lower now)
   if(closedType == POSITION_TYPE_SELL)
   {
      // Price continuing to fall = momentum alive
      // We just closed — give it a tick to confirm direction
      // The next OnTick will handle the actual reopening via burst logic

      if(CountOurPositions() < g_maxPositions)
      {
         PrintFormat("ShanoEA: MACHINE GUN — reopening SELL (burst %d/%d)",
                    g_burstCount + 1, g_maxBurst);
         OpenMachineGunTrade(sym);
      }
   }
}

//+------------------------------------------------------------------+
//| Open machine gun trade (direct, no probe needed)                 |
//+------------------------------------------------------------------+
bool OpenMachineGunTrade(string sym)
{
   double mainLots = CalculateLotSize();
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);

   if(bid <= 0) return false;

   // Validate lots
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(mainLots < minLot) mainLots = minLot;
   if(mainLots > maxLot) mainLots = maxLot;
   mainLots = MathFloor(mainLots / lotStep) * lotStep;
   mainLots = NormalizeDouble(mainLots, 2);

   string comment = StringFormat("Shano_MG_Burst%d", g_burstCount + 1);

   bool ok = g_trade.Sell(mainLots, sym, bid, 0, 0, comment);

   if(ok && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
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

      g_burstCount++;
      g_totalMains++;

      PrintFormat("ShanoEA: MACHINE GUN OPENED ticket=%I64u | %.2f lots | burst=%d/%d",
                 mgTicket, mainLots, g_burstCount, g_maxBurst);

      LogToCSV(mgTicket, sym, "SELL_open", mainLots, bid, 0, 0, 0, comment);
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
   int probes = 0, mains = 0;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string sym = PositionGetString(POSITION_SYMBOL);
      if(InpSymbolFilter != "" && sym != InpSymbolFilter) continue;

      long posType = PositionGetInteger(POSITION_TYPE);
      if(g_sellOnly && posType != POSITION_TYPE_SELL) continue;

      double lots   = PositionGetDouble(POSITION_VOLUME);
      double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      long   magic  = PositionGetInteger(POSITION_MAGIC);

      if(lots <= g_probeLots + 0.001 && magic != InpMagicNumber)
      {
         // Existing probe
         bool exists = false;
         if(!g_probeMap.TryGetValue(ticket, exists))
         {
            g_probeMap.Add(ticket, true);
            g_peakMap.Add(ticket, profit > 0 ? profit : 0.0);
            probes++;
         }

         // If probe is already profitable beyond confirm, mark confirmed
         if(profit >= g_probeConfirm)
         {
            MarkProbeConfirmed(ticket);
         }
      }
      else if(lots >= 0.02)
      {
         // Existing main trade
         bool exists = false;
         if(!g_mainMap.TryGetValue(ticket, exists))
         {
            g_mainMap.Add(ticket, true);
            g_peakMap.Add(ticket, profit > 0 ? profit : 0.0);
            mains++;
         }
      }
   }

   if(probes > 0 || mains > 0)
      PrintFormat("ShanoEA: Recovered %d probes + %d mains from existing positions", probes, mains);
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
         g_burstActive = false;
         g_burstCount  = 0;
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
   int h = FileOpen(InpLogFile, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
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
//| Log trade to CSV (same format as TurtleTradeLogger)              |
//+------------------------------------------------------------------+
void LogToCSV(ulong ticket, string sym, string direction, double volume,
              double price, double profit, double commission, double swap,
              string comment)
{
   int h = FileOpen(InpLogFile, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("ShanoEA: ERROR opening CSV file err=%d", GetLastError());
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
