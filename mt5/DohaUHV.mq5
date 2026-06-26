//+------------------------------------------------------------------+
//| DohaUHV.mq5 — Zee's ACTUAL Doha-airport / Feb 11 UHV strategy     |
//|                                                                  |
//| The strategy that earned $70k on $200k at Doha + $835 on Feb 11. |
//| Built fresh 2026-06-03 after realizing Feb11TickMedium drifted   |
//| into rng60+M5-trend, which is NOT what Zee actually traded.      |
//|                                                                  |
//| Pattern (Zee's words):                                            |
//|   1. Find an UHV (Ultra High Volume) M1 candle                   |
//|   2. Wait for the next candle to break the UHV's high (or low)   |
//|      WITH lower volume than the UHV bar (volume divergence)     |
//|   3. Enter on the breakout candle's close                        |
//|   4. Close after 1-2 min (median hold = 65s on Feb 11)           |
//|                                                                  |
//| Magic: 88012 (separate from Feb11TickMedium 88011)               |
//| Default lots: 0.10 (matches Zee's Feb 11 broker statement)       |
//| Runtime config: Common\\Files\\doha_runtime_88012.json (2-sec)    |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "Doha UHV strategy: UHV + volume-divergence breakout + short hold. Magic 88012. Lots 0.10."

#include <Trade\Trade.mqh>

input string  Inp_Symbol         = "XAUUSD";
input double  InpLots             = 0.10;      // Zee's Feb 11 size
input ulong   InpMagic            = 88012;     // DohaUHV
input int     InpSlippagePts      = 10;

// === UHV detector ===
input double  InpUhvVolMult       = 2.0;    // UHV = bar volume >= 2× median of lookback bars
input int     InpUhvLookback      = 30;     // median over last 30 M1 bars (~30 min context)
input double  InpUhvMinBodyPts    = 0.30;   // UHV must have meaningful body ($0.30+)
input int     InpUhvValidSec      = 600;    // UHV level valid for breakout up to 10 min
input double  InpBreakoutBuffer   = 0.05;   // need price to clear UHV high/low by $0.05 (avoid wick noise)
input double  InpSpreadMax        = 0.50;
input int     InpCooldownSec      = 20;

// === Universal rng60_norm gate (from Feb 11 forensics) ===
// EVERY Feb 11 entry happened during 60-sec volatility expansion. Zee's words:
// "you unconsciously gated by 'the tape is moving NOW.'" Without this, EA fires
// in dead-tape moments where Zee would never have. ALL strategies use this gate.
input double  InpRng60NormMin     = 1.20;   // Feb 11 forensic minimum

// === Exit (short-hold, Feb 11 style) ===
input int     InpTargetHoldSec    = 90;     // close around 90s if not already exited
input int     InpMaxHoldSec       = 600;    // hard cap 10 min
input double  InpQuickProfitUSD   = 5.0;    // close at +$5 USD anytime
input double  InpTrailArm         = 5.0;    // trail arms at +$5 price ($50 USD at 0.10 lot)
input double  InpTrailGiveback    = 5.0;    // tight trail for short-hold
input double  InpSkimCap          = 15.0;   // SKIM at $15 price ($150 USD at 0.10 lot)
input double  InpMaxLoss          = 10.0;   // CB at $10 price ($100 USD at 0.10 lot)

// === Broker parachutes ===
input double  InpBrokerSL_USD     = 50.0;
input double  InpBrokerTP_USD     = 100.0;

// === Daily DD ===
// At 0.10 lots: 30 price = $300 USD, $100 buffer under Atmos $400 daily limit
input double  InpDailySessionDD   = 30.0;

// === Loss-streak ===
input int     InpLossStreakN      = 1;
input int     InpLossStreakPause  = 300;

// ── Trade state ──
CTrade   trade;
double   g_sessionPnl    = 0.0;
datetime g_sessionDate   = 0;
ulong    g_openTicket    = 0;
int      g_openSide      = 0;
double   g_openEntry     = 0;
datetime g_openTime      = 0;
double   g_openPeak      = 0;
bool     g_openArmed     = false;
int      g_consecLosses  = 0;
datetime g_pauseUntil    = 0;
datetime g_lastFireBuy   = 0;
datetime g_lastFireSell  = 0;

// ── UHV state machine ──
enum UhvState { UHV_WATCHING, UHV_FOUND };
UhvState g_uhvState        = UHV_WATCHING;
datetime g_uhvBarTime      = 0;     // open-time of the UHV bar
double   g_uhvHigh         = 0;
double   g_uhvLow          = 0;
long     g_uhvVolume       = 0;
int      g_uhvSide         = 0;     // +1 (UHV was bullish, watch high break) or -1 (bearish, watch low break)
datetime g_lastM1BarTime   = 0;     // for new-bar detection

// ── Runtime-tunable params ──
double   g_lots = 0, g_skimCap = 0, g_maxLoss = 0, g_brokerSL_USD = 0, g_brokerTP_USD = 0;
double   g_dailySessionDD = 0, g_trailArm = 0, g_trailGiveback = 0;
double   g_uhvVolMult = 0, g_uhvMinBodyPts = 0, g_breakoutBuffer = 0, g_spreadMax = 0, g_quickProfitUSD = 0;
int      g_uhvLookback = 0, g_uhvValidSec = 0, g_targetHoldSec = 0, g_maxHoldSec = 0;
int      g_cooldownSec = 0, g_lossStreakN = 0, g_lossStreakPause = 0;
datetime g_lastRuntimeMtime = 0;

string StatePath()   { return StringFormat("doha_state_%I64u.json", InpMagic); }
string RuntimePath() { return StringFormat("doha_runtime_%I64u.json", InpMagic); }

void SaveState() {
   int h = FileOpen(StatePath(), FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = StringFormat(
      "{\"session_date\":%I64d,\"session_pnl\":%.4f,\"consec_losses\":%d,\"pause_until\":%I64d}",
      (long)g_sessionDate, g_sessionPnl, g_consecLosses, (long)g_pauseUntil);
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

void LoadState() {
   if(!FileIsExist(StatePath(), FILE_COMMON)) return;
   int h = FileOpen(StatePath(), FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string j = "";
   while(!FileIsEnding(h)) j += FileReadString(h);
   FileClose(h);
   g_sessionDate  = (datetime)ExtractLong(j, "session_date");
   g_sessionPnl   = ExtractDouble(j, "session_pnl");
   g_consecLosses = (int)ExtractLong(j, "consec_losses");
   g_pauseUntil   = (datetime)ExtractLong(j, "pause_until");
   PrintFormat("[DohaUHV] state restored: sessionPnl=%.2f consecLosses=%d", g_sessionPnl, g_consecLosses);
}

void InitRuntimeFromInputs() {
   g_lots = InpLots; g_skimCap = InpSkimCap; g_maxLoss = InpMaxLoss;
   g_brokerSL_USD = InpBrokerSL_USD; g_brokerTP_USD = InpBrokerTP_USD;
   g_dailySessionDD = InpDailySessionDD; g_trailArm = InpTrailArm; g_trailGiveback = InpTrailGiveback;
   g_uhvVolMult = InpUhvVolMult; g_uhvMinBodyPts = InpUhvMinBodyPts;
   g_breakoutBuffer = InpBreakoutBuffer; g_spreadMax = InpSpreadMax;
   g_quickProfitUSD = InpQuickProfitUSD;
   g_uhvLookback = InpUhvLookback; g_uhvValidSec = InpUhvValidSec;
   g_targetHoldSec = InpTargetHoldSec; g_maxHoldSec = InpMaxHoldSec;
   g_cooldownSec = InpCooldownSec; g_lossStreakN = InpLossStreakN; g_lossStreakPause = InpLossStreakPause;
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
   v = ExtractDouble(j, "lots");            if(v > 0 && v != g_lots)           { g_lots = v; changes += StringFormat(" lots=%.2f", v); }
   v = ExtractDouble(j, "uhv_vol_mult");    if(v > 0 && v != g_uhvVolMult)     { g_uhvVolMult = v; changes += StringFormat(" uhvVolMult=%.2f", v); }
   v = ExtractDouble(j, "uhv_min_body");    if(v > 0 && v != g_uhvMinBodyPts)  { g_uhvMinBodyPts = v; changes += StringFormat(" uhvMinBody=%.2f", v); }
   v = ExtractDouble(j, "breakout_buffer"); if(v > 0 && v != g_breakoutBuffer) { g_breakoutBuffer = v; changes += StringFormat(" breakoutBuf=%.2f", v); }
   v = ExtractDouble(j, "quick_profit_usd");if(v > 0 && v != g_quickProfitUSD) { g_quickProfitUSD = v; changes += StringFormat(" quickProfit=%.2f", v); }
   v = ExtractDouble(j, "trail_arm");       if(v > 0 && v != g_trailArm)       { g_trailArm = v; changes += StringFormat(" trailArm=%.2f", v); }
   v = ExtractDouble(j, "trail_giveback");  if(v > 0 && v != g_trailGiveback)  { g_trailGiveback = v; changes += StringFormat(" trailGB=%.2f", v); }
   v = ExtractDouble(j, "skim_cap");        if(v > 0 && v != g_skimCap)        { g_skimCap = v; changes += StringFormat(" skim=%.2f", v); }
   v = ExtractDouble(j, "max_loss");        if(v > 0 && v != g_maxLoss)        { g_maxLoss = v; changes += StringFormat(" maxLoss=%.2f", v); }
   v = ExtractDouble(j, "broker_sl_usd");   if(v > 0 && v != g_brokerSL_USD)   { g_brokerSL_USD = v; changes += StringFormat(" brokerSL=%.2f", v); }
   v = ExtractDouble(j, "broker_tp_usd");   if(v > 0 && v != g_brokerTP_USD)   { g_brokerTP_USD = v; changes += StringFormat(" brokerTP=%.2f", v); }
   v = ExtractDouble(j, "daily_dd");        if(v > 0 && v != g_dailySessionDD) { g_dailySessionDD = v; changes += StringFormat(" dailyDD=%.2f", v); }
   v = ExtractDouble(j, "spread_max");      if(v > 0 && v != g_spreadMax)      { g_spreadMax = v; changes += StringFormat(" spreadMax=%.2f", v); }
   iv = (int)ExtractLong(j, "uhv_lookback");   if(iv > 0 && iv != g_uhvLookback)   { g_uhvLookback = iv; changes += StringFormat(" uhvLB=%d", iv); }
   iv = (int)ExtractLong(j, "uhv_valid_sec");  if(iv > 0 && iv != g_uhvValidSec)   { g_uhvValidSec = iv; changes += StringFormat(" uhvValid=%ds", iv); }
   iv = (int)ExtractLong(j, "target_hold");    if(iv > 0 && iv != g_targetHoldSec) { g_targetHoldSec = iv; changes += StringFormat(" target=%ds", iv); }
   iv = (int)ExtractLong(j, "max_hold");       if(iv > 0 && iv != g_maxHoldSec)    { g_maxHoldSec = iv; changes += StringFormat(" maxHold=%ds", iv); }
   iv = (int)ExtractLong(j, "cooldown");       if(iv > 0 && iv != g_cooldownSec)   { g_cooldownSec = iv; changes += StringFormat(" cooldown=%ds", iv); }
   if(changes != "") PrintFormat("[DohaUHV] runtime config updated:%s", changes);
}

int OnInit() {
   if(InpLots <= 0) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   long fillMask = (long)SymbolInfoInteger(Inp_Symbol, SYMBOL_FILLING_MODE);
   ENUM_ORDER_TYPE_FILLING fillMode;
   if((fillMask & SYMBOL_FILLING_IOC) != 0)      fillMode = ORDER_FILLING_IOC;
   else if((fillMask & SYMBOL_FILLING_FOK) != 0) fillMode = ORDER_FILLING_FOK;
   else                                           fillMode = ORDER_FILLING_RETURN;
   trade.SetTypeFilling(fillMode);
   PrintFormat("[DohaUHV] init magic=%I64u lots=%.2f sym=%s fill=%s",
               InpMagic, InpLots, Inp_Symbol,
               fillMode == ORDER_FILLING_IOC ? "IOC" : fillMode == ORDER_FILLING_FOK ? "FOK" : "RETURN");
   LoadState();
   InitRuntimeFromInputs();
   LoadRuntimeConfig();
   if(HasOpenForMagic()) {
      PrintFormat("[DohaUHV] re-bound open position ticket=%I64u side=%d", g_openTicket, g_openSide);
   }
   EventSetTimer(2);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   PrintFormat("[DohaUHV] deinit reason=%d", reason);
}

void OnTimer() { LoadRuntimeConfig(); }

void ResetIfNewDay(datetime t) {
   MqlDateTime dt; TimeToStruct(t, dt);
   datetime day0 = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   if(day0 != g_sessionDate) {
      g_sessionDate    = day0;
      g_sessionPnl     = 0.0;
      g_consecLosses   = 0;
      g_pauseUntil     = 0;
      g_uhvState       = UHV_WATCHING;
      PrintFormat("[DohaUHV] new session day %s", TimeToString(day0, TIME_DATE));
      SaveState();
   }
}

bool HasOpenForMagic() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
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

// USD distance → price distance (uses current runtime g_lots)
double UsdToPriceDist(double usd_amount) {
   double tv = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0) return 0;
   return (usd_amount / (tv * g_lots)) * ts;
}

void TryEnter(int side, double bid, double ask) {
   double sl_dist = UsdToPriceDist(g_brokerSL_USD);
   double tp_dist = UsdToPriceDist(g_brokerTP_USD);
   double sl = 0, tp = 0;
   int digits = (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS);
   if(side == +1) {
      if(sl_dist > 0) sl = NormalizeDouble(ask - sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(ask + tp_dist, digits);
      if(!trade.Buy(g_lots, Inp_Symbol, ask, sl, tp, "DohaUHV buy")) {
         PrintFormat("[DohaUHV] Buy FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = +1; g_openEntry = ask; g_openTime = TimeCurrent();
      g_lastFireBuy = TimeCurrent();
   } else {
      if(sl_dist > 0) sl = NormalizeDouble(bid + sl_dist, digits);
      if(tp_dist > 0) tp = NormalizeDouble(bid - tp_dist, digits);
      if(!trade.Sell(g_lots, Inp_Symbol, bid, sl, tp, "DohaUHV sell")) {
         PrintFormat("[DohaUHV] Sell FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = -1; g_openEntry = bid; g_openTime = TimeCurrent();
      g_lastFireSell = TimeCurrent();
   }
   g_openTicket = trade.ResultOrder();
   if(g_openTicket == 0) HasOpenForMagic();
   g_openPeak = 0; g_openArmed = false;
   PrintFormat("[DohaUHV] OPEN %s @ %.5f sl=%.5f tp=%.5f ticket=%I64u lots=%.2f (UHV bar @ %s)",
               side > 0 ? "BUY" : "SELL", g_openEntry, sl, tp, g_openTicket, g_lots,
               TimeToString(g_uhvBarTime, TIME_DATE|TIME_MINUTES));
   g_uhvState = UHV_WATCHING;   // reset state machine after entry
}

void ClosePosition(string reason) {
   if(g_openTicket == 0) return;
   if(trade.PositionClose(g_openTicket)) {
      double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
      double cur = (g_openSide > 0) ? (bid - g_openEntry) : (g_openEntry - ask);
      g_sessionPnl += cur;
      if(cur > 0) g_consecLosses = 0;
      else {
         g_consecLosses++;
         if(g_consecLosses >= g_lossStreakN) {
            g_pauseUntil = TimeCurrent() + g_lossStreakPause;
            g_consecLosses = 0;
            PrintFormat("[DohaUHV] LOSS STREAK: paused until %s", TimeToString(g_pauseUntil));
         }
      }
      PrintFormat("[DohaUHV] CLOSE %s side=%d pnl=%.2f sessionPnl=%.2f",
                  reason, g_openSide, cur, g_sessionPnl);
      g_openTicket = 0; g_openSide = 0; g_openPeak = 0; g_openArmed = false;
      SaveState();
   } else {
      PrintFormat("[DohaUHV] CLOSE FAIL ticket=%I64u rc=%d err=%d",
                  g_openTicket, trade.ResultRetcode(), GetLastError());
   }
}

void ManageOpen(double bid, double ask) {
   if(g_openTicket == 0) return;
   double cur = (g_openSide > 0) ? (bid - g_openEntry) : (g_openEntry - ask);
   int holdSec = (int)(TimeCurrent() - g_openTime);

   // Quick profit close: if we've earned $5+ USD by ~target hold, scalp out
   double curUsd = cur * g_lots * 100.0;   // USD = price * lots * 100 (XAU)
   if(holdSec >= g_targetHoldSec && curUsd >= g_quickProfitUSD) {
      ClosePosition("QUICK"); return;
   }

   // SKIM (big winner cap)
   if(cur >= g_skimCap) { ClosePosition("SKIM"); return; }

   // Peak + trail
   if(cur > g_openPeak) g_openPeak = cur;
   if(g_openPeak >= g_trailArm) g_openArmed = true;
   if(g_openArmed && cur <= g_openPeak - g_trailGiveback) {
      ClosePosition("TRAIL"); return;
   }
   // CB
   if(cur <= -g_maxLoss) { ClosePosition("CB"); return; }
   // EOH max hold
   if(holdSec > g_maxHoldSec) { ClosePosition("EOH"); return; }
}

// Detect UHV on the just-closed M1 bar (shift=1 in iVolume/iHigh/iLow/iOpen/iClose).
// Returns +1 if UHV bullish, -1 if UHV bearish, 0 if not a UHV.
int DetectUhv() {
   long vol_now = iVolume(Inp_Symbol, PERIOD_M1, 1);  // just-closed bar
   if(vol_now <= 0) return 0;

   // Compute median volume of the lookback window (shifted by 1 to skip current bar)
   long vols[];
   ArrayResize(vols, g_uhvLookback);
   for(int i = 0; i < g_uhvLookback; i++) {
      vols[i] = iVolume(Inp_Symbol, PERIOD_M1, 2 + i);   // bars 2..2+lookback
   }
   ArraySort(vols);
   long median = vols[g_uhvLookback / 2];
   if(median <= 0) return 0;

   double ratio = (double)vol_now / (double)median;
   if(ratio < g_uhvVolMult) return 0;   // not enough volume relative to context

   double open  = iOpen(Inp_Symbol, PERIOD_M1, 1);
   double close = iClose(Inp_Symbol, PERIOD_M1, 1);
   double body  = MathAbs(close - open);
   if(body < g_uhvMinBodyPts) return 0;   // doji-like, not directional

   return (close > open) ? +1 : -1;
}

// Check if just-closed bar broke the UHV's high (for bullish UHV) or low (for bearish UHV)
// with LOWER volume than UHV bar. Returns +1/-1 if breakout confirmed, 0 if not.
int DetectBreakout() {
   if(g_uhvState != UHV_FOUND) return 0;
   // Has UHV expired?
   if(TimeCurrent() - g_uhvBarTime > g_uhvValidSec) {
      PrintFormat("[DohaUHV] UHV expired (no breakout within %ds), back to WATCHING", g_uhvValidSec);
      g_uhvState = UHV_WATCHING;
      return 0;
   }

   long brk_vol  = iVolume(Inp_Symbol, PERIOD_M1, 1);
   double brk_high = iHigh(Inp_Symbol, PERIOD_M1, 1);
   double brk_low  = iLow(Inp_Symbol, PERIOD_M1, 1);
   double brk_close= iClose(Inp_Symbol, PERIOD_M1, 1);

   if(brk_vol >= g_uhvVolume) return 0;   // breakout candle must have LOWER volume (divergence)

   if(g_uhvSide > 0) {
      // Bullish UHV: need breakout close above UHV high + buffer
      if(brk_close > g_uhvHigh + g_breakoutBuffer) return +1;
   } else {
      // Bearish UHV: need breakout close below UHV low - buffer
      if(brk_close < g_uhvLow - g_breakoutBuffer) return -1;
   }
   return 0;
}

void OnTick() {
   datetime t = TimeCurrent();
   ResetIfNewDay(t);

   double bid = SymbolInfoDouble(Inp_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(Inp_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0) return;

   // Manage open position
   if(HasOpenForMagic()) {
      ManageOpen(bid, ask);
      return;
   }

   // Global filters
   if((ask - bid) > g_spreadMax) return;
   if(g_sessionPnl <= -g_dailySessionDD) return;
   if(t < g_pauseUntil) return;

   // Detect new M1 bar close (run UHV/breakout logic ONCE per bar close, not every tick)
   datetime barTime = iTime(Inp_Symbol, PERIOD_M1, 1);  // open-time of just-closed bar
   if(barTime == g_lastM1BarTime) return;
   g_lastM1BarTime = barTime;

   // STATE MACHINE
   if(g_uhvState == UHV_WATCHING) {
      int uhv = DetectUhv();
      if(uhv != 0) {
         g_uhvState   = UHV_FOUND;
         g_uhvBarTime = barTime;
         g_uhvHigh    = iHigh(Inp_Symbol, PERIOD_M1, 1);
         g_uhvLow     = iLow(Inp_Symbol, PERIOD_M1, 1);
         g_uhvVolume  = iVolume(Inp_Symbol, PERIOD_M1, 1);
         g_uhvSide    = uhv;
         PrintFormat("[DohaUHV] UHV detected: %s bar @ %s vol=%I64d hi=%.5f lo=%.5f",
                     uhv > 0 ? "BULL" : "BEAR", TimeToString(barTime, TIME_DATE|TIME_MINUTES),
                     g_uhvVolume, g_uhvHigh, g_uhvLow);
      }
      return;
   }

   if(g_uhvState == UHV_FOUND) {
      int brk = DetectBreakout();
      if(brk == 0) return;
      // Cooldown
      datetime lastFire = (brk > 0) ? g_lastFireBuy : g_lastFireSell;
      if(TimeCurrent() - lastFire < g_cooldownSec) return;
      TryEnter(brk, bid, ask);
   }
}
//+------------------------------------------------------------------+
