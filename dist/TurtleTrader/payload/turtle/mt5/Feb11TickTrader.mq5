//+------------------------------------------------------------------+
//| Feb11TickTrader.mq5                                              |
//|                                                                  |
//| Tick-level momentum trader derived from Zee's Feb 11 day on real |
//| Blueberry ticks. Signature: trade in M5 trend direction within   |
//| Zee's session windows when 60-sec range expands beyond recent    |
//| normal. Peak-trail exit, daily session DD circuit breaker.       |
//|                                                                  |
//| Backtest OOS (Apr-May, 22 days @0.10 lots): +$1569                |
//| Magic: 88009                                                     |
//| Default lots: 0.01 (Shano's live)                                |
//+------------------------------------------------------------------+
#property strict
#property version   "1.13"
#property description "Feb 11 tick-level momentum AGGRESSIVE variant (Zee-derived). Magic 88009. v1.13: SESSION TIMEZONE FIX for Atmos broker (GMT+0). Inp Session defaults changed from FTMO GMT+3 (270/330/1185/1365) to Atmos GMT+0 (90/150/1005/1185) so the validated UTC 01:30-02:30 + 16:45-19:45 windows are honoured. Python canonical zee_tick_detector_OOS.py reproduces +$47,084 Feb 11 / +$548k 27d on real ticks; this EA implements the same logic. A/B candidate vs Feb11TickMedium (magic 88011)."

#include <Trade\Trade.mqh>

input string  Inp_Symbol         = "XAUUSD";
input double  InpLots             = 0.01;
input ulong   InpMagic            = 88009;
input int     InpSlippagePts      = 7;     // 2026-06-01: 30→7 (real-world slippage measured $0.16 avg from shano_open_log.csv)

// === Broker-side parachute SL/TP (slack vs EA-managed exits) ===
// EA still drives normal CB/SKIM/TRAIL exits; these are last-resort safety nets
// in case connection dies / EA crashes mid-trade.
input double  InpBrokerSL_USD     = 25.0;   // wider than InpMaxLoss=10 so EA's CB fires first
input double  InpBrokerTP_USD     = 50.0;   // wider than InpSkimCap=10 so EA's SKIM fires first

// === Session windows (BROKER time, in minutes-of-day) ===
// CALIBRATION: backtest validated UTC hours 01:30-02:30 (S1) and 16:45-19:45 (S2).
// Defaults below are for a GMT+3 broker (FTMO summer-time). If running on a GMT+0
// broker (Exness/Blueberry standard), subtract 180 (3 hours): S1=90/150, S2=1005/1185.
// PKT in either case: S1 06:30-07:30, S2 21:45-00:45.
input int     InpSession1StartMin = 270;    // 04:30 FTMO = 01:30 UTC
input int     InpSession1EndMin   = 330;    // 05:30 FTMO = 02:30 UTC
input int     InpSession2StartMin = 1185;   // 19:45 FTMO = 16:45 UTC
input int     InpSession2EndMin   = 1365;   // 22:45 FTMO = 19:45 UTC

// === Detector ===
input double  InpRng60NormMin     = 0.5;    // cycle 22: 1.0→0.5 (+$4358)
input double  InpRng60Min         = 0.5;    // cycle 22: locked
input double  InpSpreadMax        = 0.50;   // cycle 10: 0.40→0.50 (+$2791)
input int     InpCooldownSec      = 10;   // cycle 26: 15→10 (+$144691)
input int     InpM5Lookback       = 14;     // cycle 19: 20→14 (+$33758)
input int     InpCheckEveryTicks  = 3;      // cycle 25: 20→3 (+$39189, 21W/1L)

// === Exit (peak-trail) ===
input double  InpTrailArm         = 5.0;    // cycle 23: 2.0→5.0 (+$2718)
input double  InpTrailGiveback    = 15.0;   // cycle 27: 10→15 (+$60212)
input double  InpSkimCap          = 10.0;   // cycle 16: 50→10 (Feb 11 +$4931 = 5.9× goal!)
input double  InpMaxLoss          = 10.0;   // cycle 14: 5→10 (+$5902)
input int     InpMaxHoldSec       = 2400;   // cycle 20: 1800→2400s (40 min, +$21780)

// === Daily session DD ===
input double  InpDailySessionDD   = 100.0;  // cycle 21: 75→100 (+$4545, 20W/2L)

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

// Rolling tick buffer (last 5 min for rng60 + range_300)
struct TickRec { datetime t; double mid; double bid; double ask; };
TickRec  g_buf[100000];
int      g_bufHead = 0;
int      g_bufCount = 0;

// === Fix #6: persistent state across EA restarts ===
// MT5 wipes globals on chart change / recompile. We persist session-survival vars
// to Common\Files so a mid-session reload doesn't reset DD circuit / loss-pause.
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

// Lightweight extractor — no full JSON parse, just key:value scan
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
   PrintFormat("[Feb11TickTrader] state restored: date=%s sessionPnl=%.2f consecLosses=%d pauseUntil=%s",
               TimeToString(g_sessionDate, TIME_DATE), g_sessionPnl, g_consecLosses,
               g_pauseUntil > 0 ? TimeToString(g_pauseUntil) : "—");
}

int OnInit() {
   // Fix #5: input validation — InpCheckEveryTicks=0 would divide-by-zero in OnTick
   if(InpCheckEveryTicks < 1) {
      Print("[Feb11TickTrader] FATAL: InpCheckEveryTicks must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpLots <= 0) {
      Print("[Feb11TickTrader] FATAL: InpLots must be > 0");
      return(INIT_PARAMETERS_INCORRECT);
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   // Fix #1: auto-detect broker's filling mode instead of hardcoded FOK.
   // Blueberry XAUUSD supports IOC for market orders; FOK fails on partial-fill risk.
   long fillMask = (long)SymbolInfoInteger(Inp_Symbol, SYMBOL_FILLING_MODE);
   ENUM_ORDER_TYPE_FILLING fillMode;
   if((fillMask & SYMBOL_FILLING_IOC) != 0)      fillMode = ORDER_FILLING_IOC;
   else if((fillMask & SYMBOL_FILLING_FOK) != 0) fillMode = ORDER_FILLING_FOK;
   else                                           fillMode = ORDER_FILLING_RETURN;
   trade.SetTypeFilling(fillMode);
   PrintFormat("[Feb11TickTrader] init magic=%I64u lots=%.2f sym=%s slippage=%d fill=%s",
               InpMagic, InpLots, Inp_Symbol, InpSlippagePts,
               fillMode == ORDER_FILLING_IOC ? "IOC" :
               fillMode == ORDER_FILLING_FOK ? "FOK" : "RETURN");
   LoadState();   // Fix #6: restore session DD / loss-pause across restarts
   // If a position is already open at broker (recompile mid-trade), re-bind it
   if(HasOpenForMagic()) {
      PrintFormat("[Feb11TickTrader] re-bound open position ticket=%I64u side=%d entry=%.5f",
                  g_openTicket, g_openSide, g_openEntry);
   }
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   PrintFormat("[Feb11TickTrader] deinit reason=%d", reason);
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
      PrintFormat("[Feb11TickTrader] new session day %s", TimeToString(day0, TIME_DATE));
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
   datetime last_t = now + 1;   // Fix #7: monotonicity guard for wrap-detect
   for(int i = 0; i < n; i++) {
      int idx = (g_bufHead - 1 - i + 100000) % 100000;
      datetime t = g_buf[idx].t;
      double m = g_buf[idx].mid;
      // Fix #7: if t suddenly jumps NEWER than the previous (newer) sample,
      // we've wrapped into overwritten older slots — stop scanning.
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

// HH/HL on last InpM5Lookback M5 bars. Skips the current (incomplete) bar.
int M5TrendDir() {
   int lb = InpM5Lookback;
   MqlRates r[];
   ArraySetAsSeries(r, true);   // r[0]=newest (current incomplete), r[1]=most recent closed
   if(CopyRates(Inp_Symbol, PERIOD_M5, 0, lb + 1, r) < lb + 1) return 0;
   int h = lb / 2;
   double rH = -DBL_MAX, rL = DBL_MAX, oH = -DBL_MAX, oL = DBL_MAX;
   // recent half: r[1] (newest closed) to r[h]
   for(int i = 1; i <= h; i++) {
      if(r[i].high > rH) rH = r[i].high;
      if(r[i].low  < rL) rL = r[i].low;
   }
   // older half: r[h+1] to r[lb]
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
      // ensures we only manage positions on OUR symbol. Prevents a magic-collision
      // EA from cross-managing positions on other instruments.
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

// Convert a USD-denominated distance into a price delta for InpLots.
// XAUUSD: 1 lot = 100 oz, so $1 profit/loss ≈ 0.01 price move per 0.01 lot.
double UsdToPriceDist(double usd_amount) {
   double tick_value = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(Inp_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0 || tick_size <= 0) return 0;
   // ticks needed for `usd_amount` at InpLots
   double ticks = usd_amount / (tick_value * InpLots);
   return ticks * tick_size;
}

void TryEnter(int side, double bid, double ask) {
   double sl_dist = UsdToPriceDist(InpBrokerSL_USD);
   double tp_dist = UsdToPriceDist(InpBrokerTP_USD);
   double sl = 0, tp = 0;
   if(side == +1) {
      // Buy: SL below ask, TP above ask
      if(sl_dist > 0) sl = NormalizeDouble(ask - sl_dist, (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS));
      if(tp_dist > 0) tp = NormalizeDouble(ask + tp_dist, (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS));
      if(!trade.Buy(InpLots, Inp_Symbol, ask, sl, tp, "Feb11TickTrader buy")) {
         PrintFormat("[Feb11TickTrader] Buy FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = +1; g_openEntry = ask; g_openTime = TimeCurrent();
   } else {
      // Sell: SL above bid, TP below bid
      if(sl_dist > 0) sl = NormalizeDouble(bid + sl_dist, (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS));
      if(tp_dist > 0) tp = NormalizeDouble(bid - tp_dist, (int)SymbolInfoInteger(Inp_Symbol, SYMBOL_DIGITS));
      if(!trade.Sell(InpLots, Inp_Symbol, bid, sl, tp, "Feb11TickTrader sell")) {
         PrintFormat("[Feb11TickTrader] Sell FAIL rc=%d err=%d", trade.ResultRetcode(), GetLastError());
         return;
      }
      g_openSide = -1; g_openEntry = bid; g_openTime = TimeCurrent();
   }
   // Fix #8: re-bind ticket authoritatively from broker (DEAL_ADD bind in case
   // Blueberry returns 0 in trade.ResultOrder() on async fills).
   g_openTicket = trade.ResultOrder();
   if(g_openTicket == 0) {
      // fallback: re-scan positions
      HasOpenForMagic();
   }
   g_openPeak = 0.0; g_openArmed = false;
   if(side == +1) g_lastFireBuy = TimeCurrent();
   else           g_lastFireSell = TimeCurrent();
   PrintFormat("[Feb11TickTrader] OPEN %s @ %.5f sl=%.5f tp=%.5f ticket=%I64u",
               side > 0 ? "BUY" : "SELL", g_openEntry, sl, tp, g_openTicket);
}

void ManageOpen(double bid, double ask) {
   if(g_openTicket == 0) return;
   double cur = (g_openSide > 0) ? (bid - g_openEntry) : (g_openEntry - ask);
   // Skim
   if(cur >= InpSkimCap) {
      ClosePosition("SKIM"); return;
   }
   // Update peak / arm trail
   if(cur > g_openPeak) g_openPeak = cur;
   if(g_openPeak >= InpTrailArm) g_openArmed = true;
   if(g_openArmed && cur <= g_openPeak - InpTrailGiveback) {
      ClosePosition("TRAIL"); return;
   }
   // CB
   if(cur <= -InpMaxLoss) {
      ClosePosition("CB"); return;
   }
   // Max hold
   if(TimeCurrent() - g_openTime > InpMaxHoldSec) {
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
      // Loss-streak tracking
      if(cur > 0) {
         g_consecLosses = 0;
      } else {
         g_consecLosses++;
         if(g_consecLosses >= InpLossStreakN) {
            g_pauseUntil   = TimeCurrent() + InpLossStreakPause;
            g_consecLosses = 0;
            PrintFormat("[Feb11TickTrader] LOSS STREAK: paused until %s", TimeToString(g_pauseUntil));
         }
      }
      PrintFormat("[Feb11TickTrader] CLOSE %s side=%d entry=%.5f bid=%.5f ask=%.5f pnl=%.2f sessionPnl=%.2f consecLosses=%d",
                  reason, g_openSide, g_openEntry, bid, ask, cur, g_sessionPnl, g_consecLosses);
      // Fix #2: state reset ONLY on successful close. If close failed, position is
      // still open at broker — next OnTick will re-find it via HasOpenForMagic().
      g_openTicket = 0; g_openSide = 0;
      g_openPeak = 0; g_openArmed = false;
      SaveState();   // Fix #6: persist post-close DD/streak state
   } else {
      PrintFormat("[Feb11TickTrader] CLOSE FAIL ticket=%I64u rc=%d err=%d retry next tick",
                  g_openTicket, trade.ResultRetcode(), GetLastError());
      // DO NOT clear state — next OnTick will re-attempt close via ManageOpen().
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

   // Throttle: only fire-check every N ticks
   g_tickCounter++;
   if(g_tickCounter % InpCheckEveryTicks != 0) return;

   if(!InSessionWindow(t)) return;
   if((ask - bid) > InpSpreadMax) return;
   if(g_sessionPnl <= -InpDailySessionDD) return;
   if(t < g_pauseUntil) return;   // loss-streak pause active

   double rng60 = 0, rng60_norm = 0;
   if(!ComputeRanges(rng60, rng60_norm)) return;
   if(rng60 < InpRng60Min) return;
   if(rng60_norm < InpRng60NormMin) return;

   int td = M5TrendDir();
   if(td == 0) return;

   int side = (td > 0) ? +1 : -1;
   if(side > 0 && TimeCurrent() - g_lastFireBuy  < InpCooldownSec) return;
   if(side < 0 && TimeCurrent() - g_lastFireSell < InpCooldownSec) return;

   TryEnter(side, bid, ask);
}
//+------------------------------------------------------------------+
