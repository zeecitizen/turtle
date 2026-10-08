//+------------------------------------------------------------------+
//|  ZeeBreakout.mq5 — Zee's UHV breakout, traded live from the      |
//|  TradingView indicator's armed setups (2026-10-09).               |
//|                                                                  |
//|  Signals are NOT re-derived here. turtle.pine (OANDA price and    |
//|  OANDA volume, as LAWS.md requires) arms a setup at each candle   |
//|  close; pine/tv_armed_bridge.py writes it to                      |
//|  Common\Files\tv_armed.csv. During the next candle this EA enters |
//|  when THIS broker's price crosses THIS broker's high (BUY) / low  |
//|  (SELL) of the same UHV candle — the logic of mt5/SignalReplay,   |
//|  which is what the MT5 tests measured.                            |
//|                                                                  |
//|  MT5 receipts (real ticks, random delay, 0.1 lot, 28 Sep-8 Oct,   |
//|  174 trades, IN-SAMPLE): Blueberry XAUUSD.pi, TP 1.50 / SL 3.50 / |
//|  5 min: +$1.48/trade vs random entries -$2.63. Prime XBT similar. |
//|                                                                  |
//|  Funded-account guards (Blueberry Prime: daily loss 4% of initial,|
//|  from max(balance, equity) at day start; static floor 10% below   |
//|  initial; no new trades 2 min around high-impact news). Built for |
//|  Zee's own strategy; Blueberry requires disclosing the EA and     |
//|  getting consent BEFORE it trades.                                |
//+------------------------------------------------------------------+
#property copyright "Zee"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input group "── Trade ──"
input double InpLots          = 0.10;  // lots
input double InpTPPrice       = 1.50;  // take-profit distance in price ($1.50 = $15 on 0.1 lot)
input double InpSLPrice       = 3.50;  // stop-loss distance in price ($3.50 = $35 on 0.1 lot)
input int    InpWindowMin     = 5;     // close at market this many minutes after the signal candle
input double InpMaxSpread     = 0.60;  // skip if the spread is wider than this (price)
input double InpMaxChase      = 0.60;  // skip if price is already this far past the level (price)
input bool   InpDryRun        = false; // true = log what it would do, never trade

input group "── Funded-account guards ──"
input double InpInitialBalance = 25000;  // account's initial balance
input double InpMaxLossPct     = 10;     // static floor: initial balance minus this %
input double InpFloorBuffer    = 300;    // stop everything this far ABOVE the floor
input double InpDailyStop      = 500;    // no new trades after losing this much today
input double InpDailyHardClose = 800;    // close everything after losing this much today (limit: 1000)
input int    InpMaxTradesDay   = 40;     // safety cap
input int    InpNewsMin        = 3;      // no new trades within this many minutes of high-impact news
input string InpNewsCurrency   = "USD";

input group "── Bridge ──"
input string InpFile          = "tv_armed.csv";
input int    InpMaxAgeSec     = 15;      // ignore the bridge if its last write is older
input int    InpMagic         = 88501;

datetime g_firedCandle = 0;     // one entry per candle
datetime g_exitAt = 0;
ulong    g_pos = 0;
bool     g_stopped = false;     // floor reached: done until restarted by hand
datetime g_day = 0;
double   g_dayStart = 0;
int      g_tradesToday = 0;
bool     g_dayHalt = false;
string   g_lastWhy = "";

void Say(string why) { if (why != g_lastWhy) { Print("[ZB] ", why); g_lastWhy = why; } }

int UtcOffset() { return (int)(TimeTradeServer() - TimeGMT()); }   // broker server time minus UTC

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   EventSetMillisecondTimer(250);
   PrintFormat("[ZB] ZeeBreakout v1.00 on %s | lots %.2f TP %.2f SL %.2f window %d min | floor %.0f (+%.0f buffer) | daily stop %.0f / close %.0f | %s",
               _Symbol, InpLots, InpTPPrice, InpSLPrice, InpWindowMin, InpInitialBalance * (1 - InpMaxLossPct / 100.0),
               InpFloorBuffer, InpDailyStop, InpDailyHardClose, InpDryRun ? "DRY RUN" : "LIVE");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); }

ulong MyPosition() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) return t;
   }
   return 0;
}

void CloseAll(string why) {
   ulong t;
   while ((t = MyPosition()) != 0) { if (!trade.PositionClose(t)) break; }
   Say("closed all: " + why);
}

// Blueberry: the day starts from max(balance, equity); remembered across restarts
void DayRoll() {
   MqlDateTime s; TimeToStruct(TimeTradeServer(), s);
   datetime day = StringToTime(StringFormat("%04d.%02d.%02d", s.year, s.mon, s.day));
   if (day == g_day) return;
   g_day = day; g_tradesToday = 0; g_dayHalt = false;
   string gv = StringFormat("ZB_%d_%s_daystart", (int)AccountInfoInteger(ACCOUNT_LOGIN), TimeToString(day, TIME_DATE));
   if (GlobalVariableCheck(gv)) g_dayStart = GlobalVariableGet(gv);
   else {
      g_dayStart = MathMax(AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY));
      GlobalVariableSet(gv, g_dayStart);
   }
   PrintFormat("[ZB] new day %s: start %.2f, no new trades below %.2f, close all below %.2f",
               TimeToString(day, TIME_DATE), g_dayStart, g_dayStart - InpDailyStop, g_dayStart - InpDailyHardClose);
}

bool Guards(double &room) {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double floorStop = InpInitialBalance * (1 - InpMaxLossPct / 100.0) + InpFloorBuffer;
   if (eq <= floorStop) { if (!g_stopped) { CloseAll("account floor buffer reached"); g_stopped = true; } return false; }
   if (eq <= g_dayStart - InpDailyHardClose) { if (!g_dayHalt) { CloseAll("daily hard close reached"); g_dayHalt = true; } return false; }
   if (g_stopped || g_dayHalt) return false;
   room = MathMin(eq - floorStop, eq - (g_dayStart - InpDailyStop));
   return room > 0;
}

bool NewsNear() {
   MqlCalendarValue v[];
   datetime now = TimeTradeServer();
   ResetLastError();
   if (CalendarValueHistory(v, now - InpNewsMin * 60, now + InpNewsMin * 60, NULL, InpNewsCurrency) < 0) {
      Say("news calendar unavailable - not opening trades (fail-safe)");
      return true;
   }
   for (int i = 0; i < ArraySize(v); i++) {
      MqlCalendarEvent e;
      if (CalendarEventById(v[i].event_id, e) && e.importance == CALENDAR_IMPORTANCE_HIGH) {
         Say("high-impact news near: " + e.name);
         return true;
      }
   }
   return false;
}

bool ReadArmed(long &t, int &side, long &uhv, string &status) {
   int h = FileOpen(InpFile, FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (h == INVALID_HANDLE) { status = "bridge file missing"; return false; }
   t = StringToInteger(FileReadString(h)); side = (int)StringToInteger(FileReadString(h));
   uhv = StringToInteger(FileReadString(h)); FileReadString(h);
   long written = StringToInteger(FileReadString(h)); status = FileReadString(h);
   FileClose(h);
   if (status != "OK") return false;
   if ((long)TimeGMT() - written > InpMaxAgeSec) { status = "bridge is stale"; return false; }
   return true;
}

void Manage() {
   if (g_pos != 0 && !PositionSelectByTicket(g_pos)) g_pos = 0;          // closed by TP/SL
   if (g_pos != 0 && TimeTradeServer() >= g_exitAt) { trade.PositionClose(g_pos); Say("time exit"); g_pos = 0; }
}

void Step() {
   DayRoll();
   Manage();
   double room;
   if (!Guards(room)) return;
   if (g_pos != 0 || MyPosition() != 0) return;
   datetime candle = iTime(_Symbol, PERIOD_M1, 0);
   if (candle == g_firedCandle) return;
   long t, uhv; int side; string status;
   if (!ReadArmed(t, side, uhv, status)) { Say(status); return; }
   int off = UtcOffset();
   if (side == 0 || (datetime)(t + 60 + off) != candle) return;          // nothing armed for THIS candle
   int sh = iBarShift(_Symbol, PERIOD_M1, (datetime)(uhv + off), true);
   if (sh < 1) { Say("UHV candle not on this broker's chart"); return; }
   bool buy = side > 0;
   double lvl = buy ? iHigh(_Symbol, PERIOD_M1, sh) : iLow(_Symbol, PERIOD_M1, sh);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if (buy ? bid <= lvl : bid >= lvl) return;                            // not crossed yet
   g_firedCandle = candle;                                               // one decision per candle
   if (MathAbs(bid - lvl) > InpMaxChase) { Say(StringFormat("skip: price already %.2f past the level", MathAbs(bid - lvl))); return; }
   if (ask - bid > InpMaxSpread) { Say(StringFormat("skip: spread %.2f", ask - bid)); return; }
   if (g_tradesToday >= InpMaxTradesDay) { Say("skip: daily trade cap"); return; }
   double risk = InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE) * (InpSLPrice + (ask - bid));
   if (risk >= room) { Say(StringFormat("skip: a full stop (%.0f) would break the daily/floor limit (room %.0f)", risk, room)); return; }
   if (NewsNear()) return;
   double px = buy ? ask : bid;
   double sl = NormalizeDouble(buy ? px - InpSLPrice : px + InpSLPrice, _Digits);
   double tp = NormalizeDouble(buy ? px + InpTPPrice : px - InpTPPrice, _Digits);
   string why = StringFormat("%s at %.2f: crossed %s %.2f of UHV %s | SL %.2f TP %.2f | exit by %s",
                             buy ? "BUY" : "SELL", px, buy ? "high" : "low", lvl, TimeToString((datetime)(uhv + off), TIME_MINUTES),
                             sl, tp, TimeToString(candle + (InpWindowMin + 1) * 60, TIME_MINUTES));
   if (InpDryRun) { Say("DRY RUN " + why); return; }
   bool ok = buy ? trade.Buy(InpLots, _Symbol, 0, sl, tp, "ZB") : trade.Sell(InpLots, _Symbol, 0, sl, tp, "ZB");
   if (!ok) { Say("order failed: " + trade.ResultRetcodeDescription()); return; }
   g_pos = MyPosition(); g_tradesToday++;
   g_exitAt = candle + (InpWindowMin + 1) * 60;
   Say(why);
}

void OnTick()  { Step(); }
void OnTimer() { Step(); }
