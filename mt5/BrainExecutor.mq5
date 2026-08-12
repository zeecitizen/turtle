//+------------------------------------------------------------------+
//| BrainExecutor.mq5 — the hand for zeeuhv_brain's eyes.             |
//|                                                                  |
//| Zee, 2026-08-12: "why is it still on paper? why not implement it? |
//| what's stopping you"                                              |
//|                                                                  |
//| Nothing structural — and he removed the one real obstacle. The    |
//| brain was on paper because firing it on Blueberry would put two   |
//| engines on one account, which is the double-firing hazard we      |
//| removed from the matcher four days ago. Atmos is a different      |
//| terminal and a different account, so that objection is gone.      |
//|                                                                  |
//| WHAT WAS ACTUALLY MISSING was this file. monitor/zeeuhv_brain.py  |
//| judges OANDA bars — real OANDA prices AND real OANDA volume, the  |
//| combination that tested at 93.28% — and writes a signal. Until    |
//| now nothing read it.                                              |
//|                                                                  |
//|     brain (OANDA prices)  ->  signal file  ->  THIS  ->  broker    |
//|                                                                    |
//| THE HONEST RISK, stated here because it belongs in the code and    |
//| not only in a chat message: the 93.28% assumed fills at OANDA's    |
//| prices. This executes at Atmos's. The gap between two brokers'     |
//| gold quotes is wider than our 1-point target, so the edge may not  |
//| survive the crossing. That is the experiment. It is not a          |
//| prediction that it will work.                                      |
//|                                                                    |
//| SAFETY, because this trades a funded challenge:                    |
//|   * a signal older than InpMaxAgeSec is IGNORED. A stale file must  |
//|     never open a position at a price that has moved on.            |
//|   * every signal id is fired at most once, remembered across       |
//|     restarts, so a restart cannot replay yesterday's trades.       |
//|   * InpMaxOpen caps concurrent positions.                          |
//|   * InpLots defaults to 0.01, NOT 0.10. On a $10,000 challenge     |
//|     with an 8% cap, a 4-ticket stack at 0.10 costs $800 and ends   |
//|     the account on ONE losing setup. 0.01 costs $80.               |
//|                                                                    |
//| magic 88096 — its own, so it can never manage ZeeUHV's positions.  |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots       = 0.01;   // InpLots — 0.01 on a challenge. 0.10 risks the account on one stack.
input int    InpMagicNumber= 88096;  // InpMagicNumber — 88096 = BrainExecutor. Never 88094/88095.
input string InpSignalFile = "zeeuhv_brain_signal.json";  // InpSignalFile — in Common\Files
input int    InpMaxAgeSec  = 90;     // InpMaxAgeSec — ignore a signal older than this
input int    InpMaxOpen    = 4;      // InpMaxOpen — concurrent positions from this EA
input int    InpPollMs     = 1000;   // InpPollMs — how often to look at the file
input bool   InpVerbose    = true;   // InpVerbose — say what it sees

long   g_last_id = 0;
string g_state   = "brain_exec_last.txt";

int CountMine() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//| Remember the last signal across restarts. Without this, a terminal
//| restart re-reads the same file and fires a trade the brain already
//| judged hours ago — the restart_refire mistake, in a new costume.
void LoadLast() {
   int h = FileOpen(g_state, FILE_READ|FILE_TXT|FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   g_last_id = (long)StringToInteger(FileReadString(h));
   FileClose(h);
}

void SaveLast(long id) {
   int h = FileOpen(g_state, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   FileWriteString(h, IntegerToString(id));
   FileClose(h);
}

string Grab(string src, string key) {
   int i = StringFind(src, "\"" + key + "\"");
   if (i < 0) return "";
   int c = StringFind(src, ":", i);
   if (c < 0) return "";
   int s = c + 1, n = StringLen(src);
   while (s < n) {
      ushort ch = StringGetCharacter(src, s);
      if (ch != ' ' && ch != '"') break;
      s++;
   }
   int e = s;
   while (e < n) {
      ushort ch = StringGetCharacter(src, e);
      if (ch == ',' || ch == '}' || ch == '"') break;
      e++;
   }
   return StringSubstr(src, s, e - s);
}

void CheckSignal() {
   int h = FileOpen(InpSignalFile, FILE_READ|FILE_TXT|FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   string body = "";
   while (!FileIsEnding(h)) body += FileReadString(h);
   FileClose(h);
   if (StringLen(body) < 10) return;

   long id = (long)StringToInteger(Grab(body, "ts"));
   if (id <= 0 || id == g_last_id) return;

   // A stale signal must never open a position. The price it was judged at is gone.
   long age = (long)TimeCurrent() - id;
   if (age > InpMaxAgeSec) {
      if (InpVerbose)
         PrintFormat("[BRAIN] signal %d is %d s old (limit %d) — IGNORED",
                     id, (int)age, InpMaxAgeSec);
      g_last_id = id; SaveLast(id);          // consume it so it is not re-reported
      return;
   }
   if (CountMine() >= InpMaxOpen) {
      if (InpVerbose) PrintFormat("[BRAIN] %d already open — signal %d skipped",
                                  CountMine(), id);
      g_last_id = id; SaveLast(id);
      return;
   }

   string side = Grab(body, "side");
   double sl = StringToDouble(Grab(body, "sl"));
   double tp = StringToDouble(Grab(body, "tp"));
   if (side != "buy" && side != "sell") return;

   g_last_id = id; SaveLast(id);             // BEFORE trading: a failed order must not retry forever
   bool ok = (side == "buy")
             ? trade.Buy (InpLots, _Symbol, 0, sl, tp, "brain_buy")
             : trade.Sell(InpLots, _Symbol, 0, sl, tp, "brain_sell");
   PrintFormat("[BRAIN] %s %.2f lots  SL %.2f  TP %.2f  -> %s (%d)",
               side, InpLots, sl, tp, ok ? "FILLED" : "REJECTED", trade.ResultRetcode());
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(20);
   LoadLast();
   EventSetMillisecondTimer(InpPollMs);
   PrintFormat("[BRAIN] BrainExecutor v1.00 · magic %d · %.2f lots · reads %s · last id %d",
               InpMagicNumber, InpLots, InpSignalFile, g_last_id);
   if (InpLots > 0.02)
      Print("[BRAIN] *** WARNING: on a $10,000 challenge a 4-ticket stack at these lots "
            "can breach the 8% cap in ONE losing setup. ***");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int r) { EventKillTimer(); PrintFormat("[BRAIN] stopped, reason=%d", r); }
void OnTimer() { CheckSignal(); }
void OnTick()  { }
