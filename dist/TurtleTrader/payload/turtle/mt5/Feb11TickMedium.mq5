//+------------------------------------------------------------------+
//| Feb11TickMedium.mq5 — CONSERVATIVE variant of Feb11TickTrader    |
//|                                                                  |
//| Same engine, less aggressive params for SAFER initial live      |
//| deployment. Trades 96 fills/day (vs 286 in aggressive).         |
//|                                                                  |
//| Backtest @COST=$0.50 / 0.10 lots / 23 days:                    |
//|   AGGRESSIVE: +$477k / 286/day / 94% WR / 20W/2L              |
//|   MEDIUM:     +$128k / 96/day  / 85% WR / 17W/5L              |
//|                                                                  |
//| Recommended for FIRST live week to validate execution matches  |
//| backtest. Once confirmed, switch to Feb11TickTrader.mq5.        |
//|                                                                  |
//| Magic: 88011 (was 88010 — moved 2026-06-01 to avoid collision     |
//| with BtcS4bTrader which already owns 88010)                       |
//+------------------------------------------------------------------+
#property strict
#property version   "1.18"
#property description "Feb 11 tick momentum MEDIUM variant. Magic 88011. v1.18: SESSION TIMEZONE FIX for Atmos broker. v1.17's Inp Session defaults were calibrated for FTMO GMT+3 (270/330/1185/1365); on Atmos (GMT+0) they fired 3 hours OFF the validated UTC windows. Verified by state file: session_date resets at 00:00 UTC = broker is GMT+0. Defaults now 90/150/1005/1185 = validated UTC 01:30-02:30 + 16:45-19:45. v1.17 broker-SL tracking fix preserved."

#include <Trade\Trade.mqh>

input string  Inp_Symbol         = "XAUUSD";
input double  InpLots             = 0.05;      // 2026-06-02 v1.13: tuned for Atmos $10k account (was 0.01 for Exness micro)
input ulong   InpMagic            = 88011;     // medium variant (was 88010 — collided with BtcS4b)
input int     InpSlippagePts      = 7;     // 2026-06-01: 30→7 (real-world slippage measured $0.16 avg from shano_open_log.csv)

// === Broker-side parachute SL/TP (slack vs EA-managed exits) ===
// EA still drives normal CB/SKIM/TRAIL exits; these are last-resort safety nets
// in case connection dies / EA crashes mid-trade.
input double  InpBrokerSL_USD     = 25.0;   // wider than InpMaxLoss=10 so EA's CB fires first
input double  InpBrokerTP_USD     = 50.0;   // wider than InpSkimCap=10 so EA's SKIM fires first

// === Session windows (BROKER time, in minutes-of-day) ===
// CALIBRATION: backtest validated UTC hours 01:30-02:30 (S1) and 16:45-19:45 (S2).
// v1.18 (2026-06-03): defaults RECALIBRATED for Atmos broker (GMT+0 / UTC).
// Earlier FTMO GMT+3 defaults (270/330/1185/1365) were firing 3 HOURS OFF on Atmos —
// caused 17 of 23 trades on 2026-06-03 to fire outside the validated UTC windows,
// contributing to $-225 daily loss. State file confirmed Atmos session_date resets
// at 00:00 UTC = broker is GMT+0.
// For broker timezone reference:
//   GMT+0 (Atmos / Exness standard): S1=90/150,  S2=1005/1185   (current defaults)
//   GMT+3 (FTMO summer-time):        S1=270/330, S2=1185/1365   (old defaults)
//   PKT in either case: S1 06:30-07:30, S2 21:45-00:45.
input int     InpSession1StartMin = 90;     // 01:30 broker (GMT+0) = 01:30 UTC
input int     InpSession1EndMin   = 150;    // 02:30 broker (GMT+0) = 02:30 UTC
input int     InpSession2StartMin = 1005;   // 16:45 broker (GMT+0) = 16:45 UTC
input int     InpSession2EndMin   = 1185;   // 19:45 broker (GMT+0) = 19:45 UTC

// === Detector (MEDIUM variant — more selective) ===
input double  InpRng60NormMin     = 0.8;    // medium: 0.5→0.8 stricter
input double  InpRng60Min         = 0.8;    // medium: 0.5→0.8 stricter
input double  InpSpreadMax        = 0.50;
input int     InpCooldownSec      = 30;     // medium: 10→30 (less frequent)
input int     InpM5Lookback       = 14;
input int     InpCheckEveryTicks  = 10;     // medium: 3→10 (less aggressive)

// === Exit (peak-trail) ===
input double  InpTrailArm         = 5.0;    // cycle 23: 2.0→5.0 (+$2718)
input double  InpTrailGiveback    = 15.0;   // cycle 27: 10→15 (+$60212)
input double  InpSkimCap          = 10.0;   // cycle 16: 50→10 (Feb 11 +$4931 = 5.9× goal!)
input double  InpMaxLoss          = 10.0;   // cycle 14: 5→10 (+$5902)
input int     InpMaxHoldSec       = 2400;   // cycle 20: 1800→2400s (40 min, +$21780)

// === Daily session DD ===
// v1.13: 75→70 for Atmos NOVA. At 0.05 lots, 70 price-units = $350 USD, leaves $50 buffer
// under prop firm's $400 daily loss limit.
input double  InpDailySessionDD   = 70.0;

// === Loss-streak adaptive cooldown (OOS-validated: +$6575/23d @0.10L) ===
input int     InpLossStreakN      = 1;      // cycle 24: 2→1 (pause after every loss)
input int     InpLossStreakPause  = 300;    // cycle 24: 600→300 (+$12872)

// ── State ──
CTrade   trade;
datetime g_lastFireBuy   = 0;
datetime g_lastFireSell  = 0;
double   g_sessionPnl    = 0.0;
datetime g_sessionDate   = 0;
int      g_tickCounter   = 0;
ulong    g_openTicket    = 0;
int      g_openSide      = 0;     // +1 buy, -1 sell
double   g_openEntry     = 0;
datetime g_openTime      = 0;
double   g_openPeak      = 0;
bool     g_openArmed     = false;
int      g_consecLosses  = 0;
datetime g_pauseUntil    = 0;

// ── Runtime-tunable params (v1.15) ──
// These mirror the Inp* values at init, then can be live-updated by writing to
// Common\Files\feb11_runtime_<magic>.json. Lets Claude adjust params without
// needing user to detach+reattach the EA.
double   g_lots           = 0;
double   g_trailArm       = 0;
double   g_trailGiveback  = 0;
double   g_skimCap        = 0;
double   g_maxLoss        = 0;
double   g_brokerSL_USD   = 0;
double   g_brokerTP_USD   = 0;
double   g_dailySessionDD = 0;
double   g_rng60Min       = 0;
double   g_rng60NormMin   = 0;
double   g_spreadMax      = 0;
int      g_cooldownSec    = 0;
int      g_maxHoldSec     = 0;
int      g_lossStreakN    = 0;
int      g_lossStreakPause = 0;
datetime g_lastRuntimeMtime = 0;

// Rolling tick buffer (last 5 min for rng60 + range_300)
struct TickRec { datetime t; double mid; double bid; double ask; };
TickRec  g_buf[100000];
int      g_bufHead = 0;
int      g_bufCount = 0;

// === Fix #6: persistent state across EA restarts ===
string StatePath() {
   return StringFormat("feb11_state_%I64u.json", InpMagic);
}

void SaveState() {
   int h = FileOpen(StatePath(), FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = StringFormat(
      "{\"session_date\":%I64d,\"session_pnl\":%.4f,\"consec_losses\":%d,\"pause_until\":%I64d,\"last_buy\":%I64d,\"last_sell\":%I64d}",
      (long)g_sessionDate, g_sessionPnl, g_consecLosses,
      (long)g_pauseUntil, (long)g_lastFireBuy, (long)g_lastFireSell);
   FileWriteString(h, j);
   FileClose(h);
}

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
   if(q == p) return 0;
   return StringToInteger(StringSubstr(j, p, q - p));
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
   if(q == p) return 0.0;
   return StringToDouble(StringSubstr(j, p, q - p));
}

void LoadState() {
   if(!FileIsExist(StatePath(), FILE_COMMON)) return;
   int h = FileOpen(StatePath(), FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = "";
   while(!FileIsEnding(h)) j += FileReadString(h);
   FileClose(h);
   g_sessionDate   = (datetime)ExtractLong(j, "session_date");
   g_sessionPnl    = ExtractDouble(j, "session_pnl");
   g_consecLosses  = (int)ExtractLong(j, "consec_losses");
   g_pauseUntil    = (datetime)ExtractLong(j, "pause_until");
   g_lastFireBuy   = (datetime)ExtractLong(j, "last_buy");
   g_lastFireSell  = (datetime)ExtractLong(j, "last_sell");
   PrintFormat("[Feb11TickMedium] state restored: date=%s sessionPnl=%.2f consecLosses=%d pauseUntil=%s",
               TimeToString(g_sessionDate, TIME_DATE), g_sessionPnl, g_consecLosses,
               g_pauseUntil > 0 ? TimeToString(g_pauseUntil) : "—");
}

bool HasOpenForMagic();

// ── Runtime config (v1.15) ──
string RuntimePath() {
   return StringFormat("feb11_runtime_%I64u.json", InpMagic);
}

// Initialize all g_* runtime params from their Inp* startup values. Called once at OnInit.
void InitRuntimeFromInputs() {
   g_lots            = InpLots;
   g_trailArm        = InpTrailArm;
   g_trailGiveback   = InpTrailGiveback;
   g_skimCap         = InpSkimCap;
   g_maxLoss         = InpMaxLoss;
   g_brokerSL_USD    = InpBrokerSL_USD;
   g_brokerTP_USD    = InpBrokerTP_USD;
   g_dailySessionDD  = InpDailySessionDD;
   g_rng60Min        = InpRng60Min;
   g_rng60NormMin    = InpRng60NormMin;
   g_spreadMax       = InpSpreadMax;
   g_cooldownSec     = InpCooldownSec;
   g_maxHoldSec      = InpMaxHoldSec;
   g_lossStreakN     = InpLossStreakN;
   g_lossStreakPause = InpLossStreakPause;
}

// Read Common\Files\feb11_runtime_<magic>.json. For each known key, override the
// corresponding g_* var. Missing keys keep current value. Logs what changed.
// Called from OnTimer every 2s.
void LoadRuntimeConfig() {
   if(!FileIsExist(RuntimePath(), FILE_COMMON)) return;
   int h = FileOpen(RuntimePath(), FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   // Only read+log if file is newer than last read (avoid log spam every 2s)
   datetime mtime = (datetime)FileGetInteger(h, FILE_MODIFY_DATE);
   if(mtime <= g_lastRuntimeMtime) { FileClose(h); return; }
   g_lastRuntimeMtime = mtime;
   string j = "";
   while(!FileIsEnding(h)) j += FileReadString(h);
   FileClose(h);
   string changes = "";
   double v; int iv;
   v = ExtractDouble(j, "lots");            if(v > 0 && v != g_lots)           { g_lots = v; changes += StringFormat(" lots=%.2f", v); }
   v = ExtractDouble(j, "trail_arm");       if(v > 0 && v != g_trailArm)       { g_trailArm = v; changes += StringFormat(" trailArm=%.2f", v); }
   v = ExtractDouble(j, "trail_giveback");  if(v > 0 && v != g_trailGiveback)  { g_trailGiveback = v; changes += StringFormat(" trailGB=%.2f", v); }
   v = ExtractDouble(j, "skim_cap");        if(v > 0 && v != g_skimCap)        { g_skimCap = v; changes += StringFormat(" skim=%.2f", v); }
   v = ExtractDouble(j, "max_loss");        if(v > 0 && v != g_maxLoss)        { g_maxLoss = v; changes += StringFormat(" maxLoss=%.2f", v); }
   v = ExtractDouble(j, "broker_sl_usd");   if(v > 0 && v != g_brokerSL_USD)   { g_brokerSL_USD = v; changes += StringFormat(" brokerSL=%.2f", v); }
   v = ExtractDouble(j, "broker_tp_usd");   if(v > 0 && v != g_brokerTP_USD)   { g_brokerTP_USD = v; changes += StringFormat(" brokerTP=%.2f", v); }
   v = ExtractDouble(j, "daily_dd");        if(v > 0 && v != g_dailySessionDD) { g_dailySessionDD = v; changes += StringFormat(" dailyDD=%.2f", v); }
   v = ExtractDouble(j, "rng60_min");       if(v > 0 && v != g_rng60Min)       { g_rng60Min = v; changes += StringFormat(" rng60Min=%.2f", v); }
   v = ExtractDouble(j, "rng60_norm_min");  if(v > 0 && v != g_rng60NormMin)   { g_rng60NormMin = v; changes += StringFormat(" rng60NormMin=%.2f", v); }
   v = ExtractDouble(j, "spread_max");      if(v > 0 && v != g_spreadMax)      { g_spreadMax = v; changes += StringFormat(" spreadMax=%.2f", v); }
   iv = (int)ExtractLong(j, "cooldown_sec");      if(iv > 0 && iv != g_cooldownSec)     { g_cooldownSec = iv; changes += StringFormat(" cooldown=%ds", iv); }
   iv = (int)ExtractLong(j, "max_hold_sec");      if(iv > 0 && iv != g_maxHoldSec)      { g_maxHoldSec = iv; changes += StringFormat(" maxHold=%ds", iv); }
   iv = (int)ExtractLong(j, "loss_streak_n");     if(iv > 0 && iv != g_lossStreakN)     { g_lossStreakN = iv; changes += StringFormat(" lossStreakN=%d", iv); }
   iv = (int)ExtractLong(j, "loss_streak_pause"); if(iv > 0 && iv != g_lossStreakPause) { g_lossStreakPause = iv; changes += StringFormat(" lossStreakPause=%ds", iv); }
   if(changes != "") {
      PrintFormat("[Feb11TickMedium] runtime config updated:%s", changes);
   }
}

int OnInit() {
   // Fix #5: input validation
   if(InpCheckEveryTicks < 1) {
      Print("[Feb11TickMedium] FATAL: InpCheckEveryTicks must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpLots <= 0) {
      Print("[Feb11TickMedium] FATAL: InpLots must be > 0");
      return(INIT_PARAMETERS_INCORRECT);
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   // Fix #1: auto-detect broker's filling mode
   long fillMask = (long)SymbolInfoInteger(Inp_Symbol, SYMBOL_FILLING_MODE);
   ENUM_ORDER_TYPE_FILLING fillMode;
   if((fillMask & SYMBOL_FILLING_IOC) != 0)      fillMode = ORDER_FILLING_IOC;
   else if((fillMask & SYMBOL_FILLING_FOK) != 0) fillMode = ORDER_FILLING_FOK;
   else                                           fillMode = ORDER_FILLING_RETURN;
   trade.SetTypeFilling(fillMode);
   PrintFormat("[Feb11TickMedium] init magic=%I64u lots=%.2f sym=%s slippage=%d fill=%s",
               InpMagic, InpLots, Inp_Symbol, InpSlippagePts,
               fillMode == ORDER_FILLING_IOC ? "IOC" :
               fillMode == ORDER_FILLING_FOK ? "FOK" : "RETURN");
   LoadState();
   if(HasOpenForMagic()) {
      PrintFormat("[Feb11TickMedium] re-bound open position ticket=%I64u side=%d entry=%.5f",
                  g_openTicket, g_openSide, g_openEntry);
   }
   // v1.15: initialize runtime params from inputs, then check for any file overrides
   InitRuntimeFromInputs();
   LoadRuntimeConfig();
   EventSetTimer(2);   // poll runtime config every 2 seconds
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
   PrintFormat("[Feb11TickMedium] deinit reason=%d", reason);
}

void OnTimer() {
   LoadRuntimeConfig();
}

// v1.17 BUG FIX: OnTradeTransaction catches broker-side closes (SL/TP that fire
// at broker level without going through trade.PositionClose()). Previously these
// closes left g_consecLosses unchanged, so the loss-streak pause NEVER triggered
// during a streak of broker SL hits. Empirical disaster on 2026-06-03: 10 SLs
// in a row = -$260 in 1h, no pause.
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result) {
   // We only care about DEAL_ADD events that REPRESENT A CLOSE (DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT).
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(trans.symbol != Inp_Symbol) return;

   // Pull the deal details from history
   if(!HistoryDealSelect(trans.deal)) return;
   long deal_magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   if(deal_magic != (long)InpMagic) return;
   long entry_type = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   // Only count CLOSE-side deals (OUT) or all-in-one (INOUT)
   if(entry_type != DEAL_ENTRY_OUT && entry_type != DEAL_ENTRY_INOUT) return;

   long deal_reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   double profit  = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
   double swap    = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
   double commish = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   double net_usd = profit + swap + commish;

   // CRITICAL: only count this if it was NOT initiated by the EA's own ClosePosition()
   // (those already update g_consecLosses inside ClosePosition()).
   // DEAL_REASON values: DEAL_REASON_CLIENT=0, EXPERT=4, SL=5, TP=6, SO=7 (stop out)
   // EA-initiated closes show as EXPERT. Broker-side closes show as SL/TP/SO.
   if(deal_reason == DEAL_REASON_EXPERT) {
      // ClosePosition() already handled this — don't double-count
      return;
   }

   // It's a broker-side close. Convert net USD back to price units for sessionPnl,
   // update consec_losses, maybe trigger pause.
   double tv = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double lots = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double pnl_price = 0;
   if(tv > 0 && ts > 0 && lots > 0) {
      // USD per price unit = tv * lots / ts → price units = net_usd / (tv*lots/ts)
      pnl_price = net_usd * ts / (tv * lots);
   } else {
      pnl_price = net_usd / 5.0;  // fallback approximate at 0.05 lots
   }
   g_sessionPnl += pnl_price;

   string reason_str = (deal_reason == DEAL_REASON_SL) ? "BROKER_SL" :
                      (deal_reason == DEAL_REASON_TP) ? "BROKER_TP" :
                      (deal_reason == DEAL_REASON_SO) ? "STOP_OUT" : "OTHER";

   if(net_usd > 0) {
      g_consecLosses = 0;
   } else {
      g_consecLosses++;
      if(g_consecLosses >= g_lossStreakN) {
         g_pauseUntil = TimeCurrent() + g_lossStreakPause;
         g_consecLosses = 0;
         PrintFormat("[Feb11TickMedium] LOSS STREAK (broker-side): paused until %s",
                     TimeToString(g_pauseUntil));
      }
   }
   PrintFormat("[Feb11TickMedium] %s ticket=%I64u net=$%.2f pnl_price=%.2f sessionPnl=%.2f consec=%d",
               reason_str, trans.position, net_usd, pnl_price, g_sessionPnl, g_consecLosses);
   // Reset our local position tracking — EA will re-bind via HasOpenForMagic next tick
   if(g_openTicket == trans.position) {
      g_openTicket = 0; g_openSide = 0; g_openPeak = 0; g_openArmed = false;
   }
   SaveState();
}

int MinutesInDay(datetime t) {
   MqlDateTime dt; TimeToStruct(t, dt);
   return dt.hour * 60 + dt.min;
}

bool InSessionWindow(datetime t) {
   // v1.16: SESSION WINDOWS RE-ENABLED. v1.14's 24h "+$250k" backtest was
   // inflated by a parallel-position bug. Live data 2026-06-02 showed:
   //   24h aggressive = 47% WR (alternating W/L), much worse than expected
   //   Original session-windowed Medium = matched Zee's Feb 11 trading hours
   // Reverting to honor the actual validated config + Zee's instinct that
   // "pausing for some hours was key to win rate."
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
      PrintFormat("[Feb11TickMedium] new session day %s", TimeToString(day0, TIME_DATE));
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

// Compute rng60_norm using rolling buffer (looking back N seconds)
bool ComputeRanges(double &rng60, double &rng60_norm) {
   double hi60 = -DBL_MAX, lo60 = DBL_MAX;
   double hi300 = -DBL_MAX, lo300 = DBL_MAX;
   datetime now = TimeCurrent();
   int n = g_bufCount;
   datetime last_t = now + 1;   // Fix #7: wrap-detect guard
   for(int i = 0; i < n; i++) {
      int idx = (g_bufHead - 1 - i + 100000) % 100000;
      datetime t = g_buf[idx].t;
      double m = g_buf[idx].mid;
      // Fix #7: stop on monotonicity break (ring wrap into overwritten slots)
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

// HH/HL on last InpM5Lookback M5 bars. Skips current incomplete bar.
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

bool HasOpenForMagic() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      // Defense-in-depth: even if another EA shares our magic, the symbol filter
      // ensures we only manage positions on OUR symbol (e.g. XAUUSDm). Prevents
      // a magic-collision EA from cross-managing positions on other instruments.
      if(PositionGetString(POSITION_SYMBOL) != Inp_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      g_openTicket = tk;
      g_openSide   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? +1 : -1;
      g_openEntry  = PositionGetDouble(POSITION_PRICE_OPEN);
      g_openTime   = (datetime)PositionGetInteger(POSITION_TIME);
      return true;
   }
   g_openTicket = 0; g_openSide = 0;
   return false;
}

// Convert USD distance to price points for current lot size (uses runtime g_lots)
double UsdToPriceDist(double usd_amount) {
   double tick_value = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0 || tick_size <= 0) return 0;
   double ticks = usd_amount / (tick_value * g_lots);
   return ticks * tick_size;
}

void TryEnter(int side, double bid, double ask) {
   double sl_dist = UsdToPriceDist(g_brokerSL_USD);
   double tp_dist = UsdToPriceDist(g_brokerTP_USD);
   double sl = 0, tp = 0;
   int digits = (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS);
   if(side == +1) {
      if(sl_dist > 0) sl = NormalizeDouble(ask - sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(ask + tp_dist, digits);
      if(!trade.Buy(g_lots, Inp_Symbol, ask, sl, tp, "Feb11TickMedium buy")) {
         PrintFormat("[Feb11TickMedium] Buy FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = +1; g_openEntry = ask; g_openTime = TimeCurrent();
   } else {
      if(sl_dist > 0) sl = NormalizeDouble(bid + sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(bid - tp_dist, digits);
      if(!trade.Sell(g_lots, Inp_Symbol, bid, sl, tp, "Feb11TickMedium sell")) {
         PrintFormat("[Feb11TickMedium] Sell FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = -1; g_openEntry = bid; g_openTime = TimeCurrent();
   }
   // Fix #8: ticket re-bind fallback if ResultOrder returns 0
   g_openTicket = trade.ResultOrder();
   if(g_openTicket == 0) HasOpenForMagic();
   g_openPeak = 0.0; g_openArmed = false;
   if(side == +1) g_lastFireBuy = TimeCurrent();
   else           g_lastFireSell = TimeCurrent();
   PrintFormat("[Feb11TickMedium] OPEN %s @ %.5f sl=%.5f tp=%.5f ticket=%I64u lots=%.2f",
               side > 0 ? "BUY" : "SELL", g_openEntry, sl, tp, g_openTicket, g_lots);
}

void ManageOpen(double bid, double ask) {
   if(g_openTicket == 0) return;
   double cur = (g_openSide > 0) ? (bid - g_openEntry) : (g_openEntry - ask);
   if(cur >= g_skimCap) {
      ClosePosition("SKIM"); return;
   }
   if(cur > g_openPeak) g_openPeak = cur;
   if(g_openPeak >= g_trailArm) g_openArmed = true;
   if(g_openArmed && cur <= g_openPeak - g_trailGiveback) {
      ClosePosition("TRAIL"); return;
   }
   if(cur <= -g_maxLoss) {
      ClosePosition("CB"); return;
   }
   if(TimeCurrent() - g_openTime > g_maxHoldSec) {
      ClosePosition("EOH"); return;
   }
}

void ClosePosition(string reason) {
   if(g_openTicket == 0) return;
   if(trade.PositionClose(g_openTicket)) {
      double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
      double cur = (g_openSide > 0) ? (bid - g_openEntry) : (g_openEntry - ask);
      g_sessionPnl += cur;
      if(cur > 0) {
         g_consecLosses = 0;
      } else {
         g_consecLosses++;
         if(g_consecLosses >= g_lossStreakN) {
            g_pauseUntil   = TimeCurrent() + g_lossStreakPause;
            g_consecLosses = 0;
            PrintFormat("[Feb11TickMedium] LOSS STREAK: paused until %s", TimeToString(g_pauseUntil));
         }
      }
      PrintFormat("[Feb11TickMedium] CLOSE %s side=%d entry=%.5f bid=%.5f ask=%.5f pnl=%.2f sessionPnl=%.2f consecLosses=%d",
                  reason, g_openSide, g_openEntry, bid, ask, cur, g_sessionPnl, g_consecLosses);
      // Fix #2: state reset only on success
      g_openTicket = 0; g_openSide = 0;
      g_openPeak = 0; g_openArmed = false;
      SaveState();
   } else {
      PrintFormat("[Feb11TickMedium] CLOSE FAIL ticket=%I64u rc=%d err=%d retry next tick",
                  g_openTicket, trade.ResultRetcode(), GetLastError());
      // DO NOT clear state — next OnTick re-attempts via ManageOpen.
   }
}

void OnTick() {
   datetime t = TimeCurrent();
   ResetIfNewDay(t);

   double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0) return;
   AddTick(t, bid, ask);

   bool hasOpen = HasOpenForMagic();
   if(hasOpen) {
      ManageOpen(bid, ask);
      return;
   }

   g_tickCounter++;
   if(g_tickCounter % InpCheckEveryTicks != 0) return;

   if(!InSessionWindow(t)) return;
   if((ask - bid) > g_spreadMax) return;
   if(g_sessionPnl <= -g_dailySessionDD) return;
   if(t < g_pauseUntil) return;

   double rng60 = 0, rng60_norm = 0;
   if(!ComputeRanges(rng60, rng60_norm)) return;
   if(rng60 < g_rng60Min) return;
   if(rng60_norm < g_rng60NormMin) return;

   int td = M5TrendDir();
   if(td == 0) return;

   int side = (td > 0) ? +1 : -1;
   if(side > 0 && TimeCurrent() - g_lastFireBuy  < g_cooldownSec) return;
   if(side < 0 && TimeCurrent() - g_lastFireSell < g_cooldownSec) return;

   TryEnter(side, bid, ask);
}
//+------------------------------------------------------------------+
