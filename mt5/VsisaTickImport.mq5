//+------------------------------------------------------------------+
//|  VsisaTickImport.mq5 — load OUR REAL recorded ticks into a custom  |
//|  symbol so the Strategy Tester can replay a month MT5 never kept.  |
//|                                                                    |
//|  Zee 2026-09-09: "but blueberry MT5 already exports tick data.."    |
//|  He was right. MT5's own 202609.tkc is a 1,784-byte empty stub, but |
//|  ShanoTickLogger has been writing real bid/ask to Common\Files all  |
//|  along at ~285,000 rows a day.                                      |
//|                                                                    |
//|  DIFFERENT FROM CustomSymbolImport ON PURPOSE. That one loads BARS  |
//|  and then invents four ticks per bar — which cannot answer "did the |
//|  stop or the target get touched first", the only question that      |
//|  decides a 2.5R trade. This loads the ACTUAL tick stream, so the    |
//|  intrabar path and the real spread both survive into the test.      |
//|                                                                    |
//|  Reads Common\Files CSV with header:  time_msc,bid,ask              |
//|  (built by monitor/strategy_lab/vsisa_sep_ticks.py)                 |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

input string InpCsv       = "vsisa_ticks.csv";  // tick source in Common\Files
input string InpNewSymbol = "XAUUSD_TK";        // custom symbol to build
input string InpCopyFrom  = "XAUUSD";           // broker symbol to copy specs from
input int    InpChunk     = 200000;             // ticks per CustomTicksReplace call

//+------------------------------------------------------------------+
void OnStart() {
   int h = FileOpen(InpCsv, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) {
      PrintFormat("[tickimport] cannot open %s (err %d)", InpCsv, GetLastError());
      return;
   }

   if (!SymbolSelect(InpCopyFrom, true))
      PrintFormat("[tickimport] warning: cannot select %s", InpCopyFrom);

   // MQL5 has no CustomSymbolExists(); creating an existing one just fails, which we
   // read as "already there".
   bool existed = SymbolInfoInteger(InpNewSymbol, SYMBOL_CUSTOM) > 0;
   if (!existed) {
      if (!CustomSymbolCreate(InpNewSymbol, "Custom\\Ghost", InpCopyFrom)) {
         PrintFormat("[tickimport] CustomSymbolCreate failed: %d", GetLastError());
         FileClose(h);
         return;
      }
      PrintFormat("[tickimport] created %s from %s", InpNewSymbol, InpCopyFrom);
   } else {
      PrintFormat("[tickimport] %s exists — replacing its ticks", InpNewSymbol);
   }

   // keep the money maths identical to the live symbol
   CustomSymbolSetInteger(InpNewSymbol, SYMBOL_DIGITS,
                          (int)SymbolInfoInteger(InpCopyFrom, SYMBOL_DIGITS));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_POINT,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_POINT));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_TRADE_TICK_SIZE,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_TRADE_TICK_SIZE));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_TRADE_TICK_VALUE,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_TRADE_TICK_VALUE));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_TRADE_CONTRACT_SIZE,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_TRADE_CONTRACT_SIZE));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_VOLUME_MIN,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_VOLUME_MIN));
   CustomSymbolSetDouble(InpNewSymbol, SYMBOL_VOLUME_STEP,
                         SymbolInfoDouble(InpCopyFrom, SYMBOL_VOLUME_STEP));
   CustomSymbolSetInteger(InpNewSymbol, SYMBOL_TRADE_MODE, SYMBOL_TRADE_MODE_FULL);

   // SELECT IT BEFORE WRITING. Without this CustomTicksReplace returns 0 and sets no
   // error — the import "succeeds", writes a bars file, and leaves NO .tkc at all. That
   // is a silent no-op that looks exactly like success, so it is worth a line of its own.
   if (!SymbolSelect(InpNewSymbol, true))
      PrintFormat("[tickimport] WARNING: cannot select %s (err %d) — ticks will not save",
                  InpNewSymbol, GetLastError());

   // SESSIONS. Inheriting XAUUSD's hours once made the tester reject 188 orders with
   // "[Market closed]" on bars we actually had. Our tick file only holds minutes the
   // market was open, so telling the symbol it is open 24/7 cannot invent trades — it
   // only stops MT5 discarding real ones.
   for (int d = 0; d < 7; d++) {
      CustomSymbolSetSessionQuote(InpNewSymbol, (ENUM_DAY_OF_WEEK)d, 0, 0, 86400);
      CustomSymbolSetSessionTrade(InpNewSymbol, (ENUM_DAY_OF_WEEK)d, 0, 0, 86400);
   }

   MqlTick buf[];
   ArrayResize(buf, InpChunk);
   int m = 0;
   long total = 0, bad = 0;
   bool first = true;
   long firstMsc = 0, lastMsc = 0;

   while (!FileIsEnding(h)) {
      string line = FileReadString(h);
      if (line == "") continue;
      if (first) { first = false; if (StringFind(line, "time_msc") >= 0) continue; }
      string f[];
      if (StringSplit(line, ',', f) < 3) { bad++; continue; }
      long   msc = (long)StringToInteger(f[0]);
      double bid = StringToDouble(f[1]);
      double ask = StringToDouble(f[2]);
      if (msc <= 0 || bid <= 0 || ask <= 0) { bad++; continue; }

      buf[m].time       = (datetime)(msc / 1000);
      buf[m].time_msc   = msc;
      buf[m].bid        = bid;
      buf[m].ask        = ask;
      buf[m].last       = 0;
      buf[m].volume     = 0;
      buf[m].volume_real= 0;
      // BOTH FLAGS, ALWAYS. A tick carrying only TICK_FLAG_BID leaves ask unset for
      // the tester, and every trade would then fill at a spread of zero — which is
      // precisely the fantasy real-tick testing exists to avoid.
      buf[m].flags      = TICK_FLAG_BID | TICK_FLAG_ASK;
      if (firstMsc == 0) firstMsc = msc;
      lastMsc = msc;
      m++;
      total++;

      if (m >= InpChunk) {
         if (!PushChunk(buf, m)) { FileClose(h); return; }
         m = 0;
      }
   }
   FileClose(h);
   if (m > 0 && !PushChunk(buf, m)) return;

   PrintFormat("[tickimport] %s: %I64d ticks loaded, %I64d bad rows", InpNewSymbol,
               total, bad);
   PrintFormat("[tickimport] span %s -> %s (server time)",
               TimeToString((datetime)(firstMsc / 1000), TIME_DATE | TIME_SECONDS),
               TimeToString((datetime)(lastMsc / 1000), TIME_DATE | TIME_SECONDS));
   PrintFormat("[tickimport] now run the tester on %s — bars and their tick_volume are "
               "built by MT5 from these ticks", InpNewSymbol);
}

//+------------------------------------------------------------------+
//| One CustomTicksReplace call. Split out so a failure names the      |
//| chunk instead of failing the whole import silently.                |
//+------------------------------------------------------------------+
bool PushChunk(MqlTick &buf[], int m) {
   MqlTick part[];
   ArrayResize(part, m);
   for (int i = 0; i < m; i++) part[i] = buf[i];
   datetime from = (datetime)(part[0].time_msc / 1000);
   datetime to   = (datetime)(part[m - 1].time_msc / 1000) + 1;
   // TWO APIs, BECAUSE ONE OF THEM SILENTLY DOES NOTHING HERE.
   // CustomTicksReplace returned 0 for every chunk with GetLastError()==0 — no error,
   // no ticks, and a .tkc that never appeared. CustomTicksAdd is the append path and is
   // tried second. Whichever works is named in the log so the next session does not
   // repeat the experiment.
   ResetLastError();
   int put = CustomTicksReplace(InpNewSymbol, from, to, part);
   int errRep = GetLastError();
   if (put <= 0) {
      ResetLastError();
      put = CustomTicksAdd(InpNewSymbol, part);
      if (put <= 0) {
         PrintFormat("[tickimport] BOTH failed at %s — Replace %d (err %d), Add %d (err %d)",
                     TimeToString(from, TIME_DATE | TIME_SECONDS), 0, errRep, put,
                     GetLastError());
         return false;
      }
      PrintFormat("[tickimport]   +%d via CustomTicksAdd  %s", put,
                  TimeToString(from, TIME_DATE | TIME_SECONDS));
      return true;
   }
   PrintFormat("[tickimport]   +%d ticks  %s", put,
               TimeToString(from, TIME_DATE | TIME_SECONDS));
   return true;
}
//+------------------------------------------------------------------+
