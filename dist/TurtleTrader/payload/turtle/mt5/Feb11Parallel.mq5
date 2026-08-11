//+------------------------------------------------------------------+
//| Feb11Parallel.mq5 — Feb 11 strategy in UNLIMITED PARALLEL mode    |
//|                                                                  |
//| Uses Feb11TickMedium's exact entry logic (rng60_norm expansion +  |
//| M5 HH/HL trend), but opens positions in PARALLEL without blocking |
//| on existing positions. This replicates the parallel-position      |
//| behavior the backtest assumed (+$1.25M / 26 days projected).      |
//|                                                                  |
//| Built 2026-06-03 for Zee's own $5k risk capital account (NOT     |
//| Atmos NOVA — Atmos has 1% per-symbol floating cap that prevents  |
//| true unlimited parallel).                                         |
//|                                                                  |
//| Safety rails (NON-NEGOTIABLE):                                    |
//|   - Equity floor: stop new fires if equity drops below 60% start  |
//|   - 1-hour DD trip: stop if equity drops >20% in any rolling hour |
//|   - Margin level check: skip new fire if margin level < 200%      |
//|   - Max concurrent cap (default 100, runtime-tunable)             |
//|                                                                  |
//| Magic: 88013 (separate from Medium 88011 and DohaUHV 88012)       |
//| Default lots: 0.10                                                |
//| Runtime config: Common\\Files\\feb11parallel_runtime_88013.json   |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "Feb 11 entry logic + UNLIMITED PARALLEL positions + safety rails. Magic 88013."

#include <Trade\Trade.mqh>

input string  Inp_Symbol         = "XAUUSD";
input double  InpLots             = 0.10;
input ulong   InpMagic            = 88013;
input int     InpSlippagePts      = 10;

// === Entry logic (same as Feb11TickMedium aggressive) ===
input double  InpRng60Min         = 0.5;
input double  InpRng60NormMin     = 0.5;
input double  InpSpreadMax        = 0.50;
input int     InpCooldownSec      = 10;
input int     InpM5Lookback       = 14;
input int     InpCheckEveryTicks  = 3;

// === Exits (per position) ===
input double  InpSkimCap          = 10.0;
input double  InpMaxLoss          = 10.0;
input double  InpTrailArm         = 5.0;
input double  InpTrailGiveback    = 15.0;
input int     InpMaxHoldSec       = 2400;

// === Broker parachutes (per position) ===
input double  InpBrokerSL_USD     = 25.0;
input double  InpBrokerTP_USD     = 50.0;

// === PARALLEL-SPECIFIC SAFETY RAILS ===
// Equity floor: stop opening new positions if equity drops below this fraction of start
input double  InpEquityFloorPct   = 0.60;   // 60% of starting balance
// 1-hour drawdown trip: stop if equity drops >20% in rolling 1-hour window
input double  InpHourDDTripPct    = 0.20;   // 20%
// Max concurrent positions cap (high default, runtime-tunable to "unlimited" if needed)
input int     InpMaxConcurrent    = 100;
// Margin level minimum to allow new fires
input double  InpMinMarginLevel   = 200.0;  // 200% = healthy

// === Session windows (same as Feb11TickMedium) ===
// Disabled by default for parallel (we want the full 24h fire rate per backtest)
input int     InpSession1StartMin = 0;
input int     InpSession1EndMin   = 1440;
input int     InpSession2StartMin = 0;
input int     InpSession2EndMin   = 1440;

// === Daily session DD ===
input double  InpDailySessionDD   = 500.0;  // In USD (parallel uses USD, not price units)

// === Loss-streak (per the system, counted across all parallel positions) ===
input int     InpLossStreakN      = 5;      // 5 consecutive losses → pause
input int     InpLossStreakPause  = 300;

// ── Trade state ──
CTrade   trade;
double   g_sessionPnl    = 0.0;  // USD-denominated for parallel
datetime g_sessionDate   = 0;
double   g_startingBalance = 0;
int      g_consecLosses  = 0;
datetime g_pauseUntil    = 0;
datetime g_lastFireBuy   = 0;
datetime g_lastFireSell  = 0;
int      g_tickCounter   = 0;

// Tick buffer for rng60 / range_300
struct TickRec { datetime t; double mid; double bid; double ask; };
TickRec  g_buf[100000];
int      g_bufHead = 0;
int      g_bufCount = 0;

// Equity history for 1-hour DD trip (sampled per minute)
double   g_equityHist[60];
int      g_equityHistHead = 0;
int      g_equityHistCount = 0;
datetime g_lastEquitySample = 0;

// ── PARALLEL position tracking ──
// Per-ticket state arrays. Aligned by index.
ulong    g_pTickets[];      // ticket IDs
int      g_pSides[];        // +1 buy / -1 sell
double   g_pEntries[];      // entry price
datetime g_pOpenTimes[];    // open time
double   g_pPeaks[];        // peak favorable cur
bool     g_pArmed[];        // trail armed

// ── Runtime-tunable params ──
double   g_lots = 0, g_skimCap = 0, g_maxLoss = 0, g_brokerSL_USD = 0, g_brokerTP_USD = 0;
double   g_dailySessionDD = 0, g_trailArm = 0, g_trailGiveback = 0;
double   g_rng60Min = 0, g_rng60NormMin = 0, g_spreadMax = 0;
int      g_cooldownSec = 0, g_maxHoldSec = 0, g_lossStreakN = 0, g_lossStreakPause = 0;
int      g_maxConcurrent = 0;
double   g_equityFloorPct = 0, g_hourDDTripPct = 0, g_minMarginLevel = 0;
datetime g_lastRuntimeMtime = 0;

string StatePath()   { return StringFormat("feb11parallel_state_%I64u.json", InpMagic); }
string RuntimePath() { return StringFormat("feb11parallel_runtime_%I64u.json", InpMagic); }

// ── JSON helpers (same pattern as Feb11TickMedium) ──
long ExtractLong(string j, string key) {
   string needle = "\"" + key + "\":";
   int p = StringFind(j, needle);
   if(p < 0) return 0;
   p += StringLen(needle);
   int q = p;
   while(q < StringLen(j)) {
      ushort c = StringGetCharacter(j, q);
      if((c < '0' || c > '9') && c != '-') break;
      q++;
   }
   return (q == p) ? 0 : StringToInteger(StringSubstr(j, p, q - p));
}
double ExtractDouble(string j, string key) {
   string needle = "\"" + key + "\":";
   int p = StringFind(j, needle);
   if(p < 0) return 0.0;
   p += StringLen(needle);
   int q = p;
   while(q < StringLen(j)) {
      ushort c = StringGetCharacter(j, q);
      if((c < '0' || c > '9') && c != '.' && c != '-') break;
      q++;
   }
   return (q == p) ? 0.0 : StringToDouble(StringSubstr(j, p, q - p));
}

void SaveState() {
   int h = FileOpen(StatePath(), FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = StringFormat(
      "{\"session_date\":%I64d,\"session_pnl_usd\":%.4f,\"consec_losses\":%d,\"pause_until\":%I64d,\"starting_balance\":%.2f}",
      (long)g_sessionDate, g_sessionPnl, g_consecLosses, (long)g_pauseUntil, g_startingBalance);
   FileWriteString(h, j);
   FileClose(h);
}
void LoadState() {
   if(!FileIsExist(StatePath(), FILE_COMMON)) return;
   int h = FileOpen(StatePath(), FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = "";
   while(!FileIsEnding(h)) j += FileReadString(h);
   FileClose(h);
   g_sessionDate     = (datetime)ExtractLong(j, "session_date");
   g_sessionPnl      = ExtractDouble(j, "session_pnl_usd");
   g_consecLosses    = (int)ExtractLong(j, "consec_losses");
   g_pauseUntil      = (datetime)ExtractLong(j, "pause_until");
   g_startingBalance = ExtractDouble(j, "starting_balance");
}

void InitRuntimeFromInputs() {
   g_lots = InpLots; g_skimCap = InpSkimCap; g_maxLoss = InpMaxLoss;
   g_brokerSL_USD = InpBrokerSL_USD; g_brokerTP_USD = InpBrokerTP_USD;
   g_dailySessionDD = InpDailySessionDD;
   g_trailArm = InpTrailArm; g_trailGiveback = InpTrailGiveback;
   g_rng60Min = InpRng60Min; g_rng60NormMin = InpRng60NormMin; g_spreadMax = InpSpreadMax;
   g_cooldownSec = InpCooldownSec; g_maxHoldSec = InpMaxHoldSec;
   g_lossStreakN = InpLossStreakN; g_lossStreakPause = InpLossStreakPause;
   g_maxConcurrent = InpMaxConcurrent;
   g_equityFloorPct = InpEquityFloorPct;
   g_hourDDTripPct = InpHourDDTripPct;
   g_minMarginLevel = InpMinMarginLevel;
}

void LoadRuntimeConfig() {
   if(!FileIsExist(RuntimePath(), FILE_COMMON)) return;
   int h = FileOpen(RuntimePath(), FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   datetime mtime = (datetime)FileGetInteger(h, FILE_MODIFY_DATE);
   if(mtime <= g_lastRuntimeMtime) { FileClose(h); return; }
   g_lastRuntimeMtime = mtime;
   string j = "";
   while(!FileIsEnding(h)) j += FileReadString(h);
   FileClose(h);
   string changes = "";
   double v; int iv;
   v = ExtractDouble(j, "lots");           if(v > 0 && v != g_lots)           { g_lots = v; changes += StringFormat(" lots=%.2f", v); }
   v = ExtractDouble(j, "broker_sl_usd");  if(v > 0 && v != g_brokerSL_USD)   { g_brokerSL_USD = v; changes += StringFormat(" brokerSL=%.2f", v); }
   v = ExtractDouble(j, "broker_tp_usd");  if(v > 0 && v != g_brokerTP_USD)   { g_brokerTP_USD = v; changes += StringFormat(" brokerTP=%.2f", v); }
   v = ExtractDouble(j, "trail_arm");      if(v > 0 && v != g_trailArm)       { g_trailArm = v; changes += StringFormat(" trailArm=%.2f", v); }
   v = ExtractDouble(j, "trail_giveback"); if(v > 0 && v != g_trailGiveback)  { g_trailGiveback = v; changes += StringFormat(" trailGB=%.2f", v); }
   v = ExtractDouble(j, "skim_cap");       if(v > 0 && v != g_skimCap)        { g_skimCap = v; changes += StringFormat(" skim=%.2f", v); }
   v = ExtractDouble(j, "max_loss");       if(v > 0 && v != g_maxLoss)        { g_maxLoss = v; changes += StringFormat(" maxLoss=%.2f", v); }
   v = ExtractDouble(j, "rng60_min");      if(v > 0 && v != g_rng60Min)       { g_rng60Min = v; changes += StringFormat(" rng60Min=%.2f", v); }
   v = ExtractDouble(j, "rng60_norm_min"); if(v > 0 && v != g_rng60NormMin)   { g_rng60NormMin = v; changes += StringFormat(" rng60NormMin=%.2f", v); }
   v = ExtractDouble(j, "spread_max");     if(v > 0 && v != g_spreadMax)      { g_spreadMax = v; changes += StringFormat(" spreadMax=%.2f", v); }
   v = ExtractDouble(j, "daily_dd_usd");   if(v > 0 && v != g_dailySessionDD) { g_dailySessionDD = v; changes += StringFormat(" dailyDDUSD=%.2f", v); }
   v = ExtractDouble(j, "equity_floor_pct"); if(v > 0 && v != g_equityFloorPct) { g_equityFloorPct = v; changes += StringFormat(" equityFloor=%.2f", v); }
   v = ExtractDouble(j, "hour_dd_trip_pct"); if(v > 0 && v != g_hourDDTripPct) { g_hourDDTripPct = v; changes += StringFormat(" hourDD=%.2f", v); }
   v = ExtractDouble(j, "min_margin_level"); if(v > 0 && v != g_minMarginLevel) { g_minMarginLevel = v; changes += StringFormat(" minMargin=%.0f%%", v); }
   iv = (int)ExtractLong(j, "cooldown_sec");      if(iv > 0 && iv != g_cooldownSec)     { g_cooldownSec = iv; changes += StringFormat(" cooldown=%ds", iv); }
   iv = (int)ExtractLong(j, "max_concurrent");    if(iv > 0 && iv != g_maxConcurrent)   { g_maxConcurrent = iv; changes += StringFormat(" maxConcurrent=%d", iv); }
   iv = (int)ExtractLong(j, "max_hold_sec");      if(iv > 0 && iv != g_maxHoldSec)      { g_maxHoldSec = iv; changes += StringFormat(" maxHold=%ds", iv); }
   if(changes != "") PrintFormat("[Feb11Parallel] runtime config updated:%s", changes);
}

int OnInit() {
   if(InpLots <= 0) return INIT_PARAMETERS_INCORRECT;
   if(InpCheckEveryTicks < 1) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   long fillMask = (long)SymbolInfoInteger(Inp_Symbol, SYMBOL_FILLING_MODE);
   ENUM_ORDER_TYPE_FILLING fillMode;
   if((fillMask & SYMBOL_FILLING_IOC) != 0)      fillMode = ORDER_FILLING_IOC;
   else if((fillMask & SYMBOL_FILLING_FOK) != 0) fillMode = ORDER_FILLING_FOK;
   else                                           fillMode = ORDER_FILLING_RETURN;
   trade.SetTypeFilling(fillMode);
   LoadState();
   InitRuntimeFromInputs();
   LoadRuntimeConfig();
   if(g_startingBalance <= 0) {
      g_startingBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      SaveState();
   }
   PrintFormat("[Feb11Parallel] init magic=%I64u lots=%.2f sym=%s fill=%s startBal=%.2f equityFloor=%.0f%% maxConcurrent=%d",
               InpMagic, g_lots, Inp_Symbol,
               fillMode == ORDER_FILLING_IOC ? "IOC" : fillMode == ORDER_FILLING_FOK ? "FOK" : "RETURN",
               g_startingBalance, g_equityFloorPct*100, g_maxConcurrent);
   ReconcilePositions();
   EventSetTimer(2);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   PrintFormat("[Feb11Parallel] deinit reason=%d", reason);
}

void OnTimer() {
   LoadRuntimeConfig();
   SampleEquity();
}

// ── Position array management ──
int FindTicketIndex(ulong ticket) {
   int n = ArraySize(g_pTickets);
   for(int i = 0; i < n; i++) if(g_pTickets[i] == ticket) return i;
   return -1;
}

void AddPosition(ulong ticket, int side, double entry, datetime open_time) {
   int n = ArraySize(g_pTickets);
   ArrayResize(g_pTickets,   n + 1);
   ArrayResize(g_pSides,     n + 1);
   ArrayResize(g_pEntries,   n + 1);
   ArrayResize(g_pOpenTimes, n + 1);
   ArrayResize(g_pPeaks,     n + 1);
   ArrayResize(g_pArmed,     n + 1);
   g_pTickets[n]   = ticket;
   g_pSides[n]     = side;
   g_pEntries[n]   = entry;
   g_pOpenTimes[n] = open_time;
   g_pPeaks[n]     = 0;
   g_pArmed[n]     = false;
}

void RemovePosition(int idx) {
   int n = ArraySize(g_pTickets);
   if(idx < 0 || idx >= n) return;
   // Shift remaining elements down
   for(int i = idx; i < n - 1; i++) {
      g_pTickets[i]   = g_pTickets[i+1];
      g_pSides[i]     = g_pSides[i+1];
      g_pEntries[i]   = g_pEntries[i+1];
      g_pOpenTimes[i] = g_pOpenTimes[i+1];
      g_pPeaks[i]     = g_pPeaks[i+1];
      g_pArmed[i]     = g_pArmed[i+1];
   }
   ArrayResize(g_pTickets,   n - 1);
   ArrayResize(g_pSides,     n - 1);
   ArrayResize(g_pEntries,   n - 1);
   ArrayResize(g_pOpenTimes, n - 1);
   ArrayResize(g_pPeaks,     n - 1);
   ArrayResize(g_pArmed,     n - 1);
}

// Reconcile g_p* arrays with actual MT5 positions. Add discovered tickets,
// remove closed tickets. PRESERVES peak/armed state across ticks.
void ReconcilePositions() {
   // Collect current MT5 tickets matching our magic+symbol
   ulong currentTickets[];
   int matchCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != Inp_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      ArrayResize(currentTickets, matchCount + 1);
      currentTickets[matchCount] = tk;
      matchCount++;
      // Add to local array if new
      if(FindTicketIndex(tk) == -1) {
         int side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
         double entry = PositionGetDouble(POSITION_PRICE_OPEN);
         datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
         AddPosition(tk, side, entry, open_time);
      }
   }
   // Remove tickets that are no longer in MT5 (closed via broker SL/TP/manually)
   for(int i = ArraySize(g_pTickets) - 1; i >= 0; i--) {
      bool found = false;
      for(int j = 0; j < matchCount; j++) {
         if(currentTickets[j] == g_pTickets[i]) { found = true; break; }
      }
      if(!found) {
         PrintFormat("[Feb11Parallel] position closed externally (broker SL/TP/manual): ticket=%I64u", g_pTickets[i]);
         RemovePosition(i);
      }
   }
}

// ── Equity history (for 1-hour DD trip) ──
void SampleEquity() {
   datetime now = TimeCurrent();
   if(now - g_lastEquitySample < 60) return;   // sample max 1/min
   g_lastEquitySample = now;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_equityHist[g_equityHistHead] = eq;
   g_equityHistHead = (g_equityHistHead + 1) % 60;
   if(g_equityHistCount < 60) g_equityHistCount++;
}

bool HourDDTripped() {
   if(g_equityHistCount < 5) return false;   // need some history
   double eq_now = AccountInfoDouble(ACCOUNT_EQUITY);
   double eq_max = eq_now;
   for(int i = 0; i < g_equityHistCount; i++) {
      if(g_equityHist[i] > eq_max) eq_max = g_equityHist[i];
   }
   if(eq_max <= 0) return false;
   double dd = (eq_max - eq_now) / eq_max;
   return dd >= g_hourDDTripPct;
}

bool EquityFloorOK() {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_startingBalance <= 0) return true;
   return eq >= g_startingBalance * g_equityFloorPct;
}

bool MarginLevelOK() {
   double ml = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(ml <= 0) return true;   // no positions yet, infinite margin level
   return ml >= g_minMarginLevel;
}

int MinutesInDay(datetime t) {
   MqlDateTime dt; TimeToStruct(t, dt);
   return dt.hour * 60 + dt.min;
}

bool InSessionWindow(datetime t) {
   int m = MinutesInDay(t);
   if(m >= InpSession1StartMin && m <= InpSession1EndMin) return true;
   if(m >= InpSession2StartMin && m <= InpSession2EndMin) return true;
   return false;
}

void ResetIfNewDay(datetime t) {
   MqlDateTime dt; TimeToStruct(t, dt);
   datetime day0 = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   if(day0 != g_sessionDate) {
      g_sessionDate    = day0;
      g_sessionPnl     = 0.0;
      g_consecLosses   = 0;
      g_pauseUntil     = 0;
      PrintFormat("[Feb11Parallel] new session day %s", TimeToString(day0, TIME_DATE));
      SaveState();
   }
}

void AddTick(datetime t, double bid, double ask) {
   double mid = (bid + ask) / 2.0;
   g_buf[g_bufHead].t = t;
   g_buf[g_bufHead].mid = mid;
   g_buf[g_bufHead].bid = bid;
   g_buf[g_bufHead].ask = ask;
   g_bufHead = (g_bufHead + 1) % 100000;
   if(g_bufCount < 100000) g_bufCount++;
}

bool ComputeRanges(double &rng60, double &rng60_norm) {
   double hi60 = -DBL_MAX, lo60 = DBL_MAX;
   double hi300 = -DBL_MAX, lo300 = DBL_MAX;
   datetime now = TimeCurrent();
   int n = g_bufCount;
   datetime last_t = now + 1;
   for(int i = 0; i < n; i++) {
      int idx = (g_bufHead - 1 - i + 100000) % 100000;
      datetime t = g_buf[idx].t;
      double m = g_buf[idx].mid;
      if(t > last_t) break;
      last_t = t;
      int dt_sec = (int)(now - t);
      if(dt_sec > 300) break;
      if(m > hi300) hi300 = m;
      if(m < lo300) lo300 = m;
      if(dt_sec <= 60) {
         if(m > hi60) hi60 = m;
         if(m < lo60) lo60 = m;
      }
   }
   if(hi60 == -DBL_MAX) return false;
   rng60 = hi60 - lo60;
   double range_300 = (hi300 - lo300);
   double denom = MathMax(0.10, range_300 / 5.0);
   rng60_norm = rng60 / denom;
   return true;
}

int M5TrendDir() {
   int lb = InpM5Lookback;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(Inp_Symbol, PERIOD_M5, 0, lb + 1, r) < lb + 1) return 0;
   int h = lb / 2;
   double rH = -DBL_MAX, rL = DBL_MAX, oH = -DBL_MAX, oL = DBL_MAX;
   for(int i = 1; i <= h; i++) {
      if(r[i].high > rH) rH = r[i].high;
      if(r[i].low  < rL) rL = r[i].low;
   }
   for(int i = h + 1; i <= lb; i++) {
      if(r[i].high > oH) oH = r[i].high;
      if(r[i].low  < oL) oL = r[i].low;
   }
   if(rH > oH && rL > oL) return +1;
   if(rH < oH && rL < oL) return -1;
   return 0;
}

double UsdToPriceDist(double usd_amount) {
   double tv = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0) return 0;
   return (usd_amount / (tv * g_lots)) * ts;
}

// USD PnL for a price-delta at current lot size
double PriceToUsd(double price_delta) {
   double tv = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0) return 0;
   return (price_delta / ts) * tv * g_lots;
}

void TryEnter(int side, double bid, double ask) {
   double sl_dist = UsdToPriceDist(g_brokerSL_USD);
   double tp_dist = UsdToPriceDist(g_brokerTP_USD);
   double sl = 0, tp = 0;
   int digits = (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS);
   double entry_px;
   if(side == +1) {
      if(sl_dist > 0) sl = NormalizeDouble(ask - sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(ask + tp_dist, digits);
      if(!trade.Buy(g_lots, Inp_Symbol, ask, sl, tp, "Feb11Parallel buy")) {
         PrintFormat("[Feb11Parallel] Buy FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      entry_px = ask;
      g_lastFireBuy = TimeCurrent();
   } else {
      if(sl_dist > 0) sl = NormalizeDouble(bid + sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(bid - tp_dist, digits);
      if(!trade.Sell(g_lots, Inp_Symbol, bid, sl, tp, "Feb11Parallel sell")) {
         PrintFormat("[Feb11Parallel] Sell FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      entry_px = bid;
      g_lastFireSell = TimeCurrent();
   }
   ulong tk = trade.ResultOrder();
   if(tk > 0) AddPosition(tk, side, entry_px, TimeCurrent());
   else ReconcilePositions();   // fallback: scan for the new position
   PrintFormat("[Feb11Parallel] OPEN %s @ %.5f sl=%.5f tp=%.5f ticket=%I64u lots=%.2f total_open=%d",
               side > 0 ? "BUY" : "SELL", entry_px, sl, tp, tk, g_lots, ArraySize(g_pTickets));
}

void ClosePositionByIndex(int idx, string reason) {
   if(idx < 0 || idx >= ArraySize(g_pTickets)) return;
   ulong tk = g_pTickets[idx];
   if(trade.PositionClose(tk)) {
      double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
      double cur = (g_pSides[idx] > 0) ? (bid - g_pEntries[idx]) : (g_pEntries[idx] - ask);
      double pnl_usd = PriceToUsd(cur);
      g_sessionPnl += pnl_usd;
      if(pnl_usd > 0) g_consecLosses = 0;
      else {
         g_consecLosses++;
         if(g_consecLosses >= g_lossStreakN) {
            g_pauseUntil = TimeCurrent() + g_lossStreakPause;
            g_consecLosses = 0;
            PrintFormat("[Feb11Parallel] LOSS STREAK: paused until %s", TimeToString(g_pauseUntil));
         }
      }
      PrintFormat("[Feb11Parallel] CLOSE %s ticket=%I64u pnl=%.2fUSD sessionPnl=%.2fUSD open_remaining=%d",
                  reason, tk, pnl_usd, g_sessionPnl, ArraySize(g_pTickets) - 1);
      RemovePosition(idx);
      SaveState();
   } else {
      PrintFormat("[Feb11Parallel] CLOSE FAIL ticket=%I64u rc=%d err=%d",
                  tk, trade.ResultRetcode(), GetLastError());
   }
}

void ManageAllPositions(double bid, double ask) {
   // Iterate backwards so RemovePosition doesn't shift indices we still need
   for(int i = ArraySize(g_pTickets) - 1; i >= 0; i--) {
      double cur = (g_pSides[i] > 0) ? (bid - g_pEntries[i]) : (g_pEntries[i] - ask);
      // SKIM
      if(cur >= g_skimCap) { ClosePositionByIndex(i, "SKIM"); continue; }
      // Update peak
      if(cur > g_pPeaks[i]) g_pPeaks[i] = cur;
      if(g_pPeaks[i] >= g_trailArm) g_pArmed[i] = true;
      // Trail
      if(g_pArmed[i] && cur <= g_pPeaks[i] - g_trailGiveback) {
         ClosePositionByIndex(i, "TRAIL"); continue;
      }
      // CB
      if(cur <= -g_maxLoss) { ClosePositionByIndex(i, "CB"); continue; }
      // EOH
      if(TimeCurrent() - g_pOpenTimes[i] > g_maxHoldSec) {
         ClosePositionByIndex(i, "EOH"); continue;
      }
   }
}

void OnTick() {
   datetime t = TimeCurrent();
   ResetIfNewDay(t);

   double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0) return;
   AddTick(t, bid, ask);

   // Reconcile + manage all open positions (every tick)
   ReconcilePositions();
   ManageAllPositions(bid, ask);

   // ─── New-fire check (parallel: NEVER blocked by existing positions) ───
   g_tickCounter++;
   if(g_tickCounter % InpCheckEveryTicks != 0) return;

   // Global filters
   if(!InSessionWindow(t)) return;
   if((ask - bid) > g_spreadMax) return;
   if(g_sessionPnl <= -g_dailySessionDD) return;
   if(t < g_pauseUntil) return;

   // ─── SAFETY RAILS (these are what make parallel survivable) ───
   if(!EquityFloorOK()) {
      static datetime lastWarn = 0;
      if(t - lastWarn > 60) {
         PrintFormat("[Feb11Parallel] EQUITY FLOOR breached: equity=%.2f < %.2f*%.2f. NO NEW FIRES.",
                     AccountInfoDouble(ACCOUNT_EQUITY), g_startingBalance, g_equityFloorPct);
         lastWarn = t;
      }
      return;
   }
   if(HourDDTripped()) {
      static datetime lastWarn2 = 0;
      if(t - lastWarn2 > 60) {
         PrintFormat("[Feb11Parallel] 1-HOUR DD TRIP: equity dropped >%.0f%% in last 60min. NO NEW FIRES.",
                     g_hourDDTripPct*100);
         lastWarn2 = t;
      }
      return;
   }
   if(!MarginLevelOK()) {
      static datetime lastWarn3 = 0;
      if(t - lastWarn3 > 60) {
         PrintFormat("[Feb11Parallel] MARGIN LEVEL too low: %.1f%% < %.1f%%. NO NEW FIRES.",
                     AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), g_minMarginLevel);
         lastWarn3 = t;
      }
      return;
   }
   if(ArraySize(g_pTickets) >= g_maxConcurrent) return;   // hard cap

   // ─── Entry detection (same as Feb11TickMedium) ───
   double rng60 = 0, rng60_norm = 0;
   if(!ComputeRanges(rng60, rng60_norm)) return;
   if(rng60 < g_rng60Min) return;
   if(rng60_norm < g_rng60NormMin) return;
   int td = M5TrendDir();
   if(td == 0) return;
   int side = (td > 0) ? +1 : -1;
   // Cooldown (global, prevents rapid-fire same side)
   if(side > 0 && TimeCurrent() - g_lastFireBuy  < g_cooldownSec) return;
   if(side < 0 && TimeCurrent() - g_lastFireSell < g_cooldownSec) return;

   TryEnter(side, bid, ask);
}
//+------------------------------------------------------------------+
