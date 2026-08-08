//+------------------------------------------------------------------+
//| CustomSymbolImport.mq5 — put OUR volume into MT5's own tester     |
//|                                                                  |
//| Zee 2026-08-08: "maybe if we can test the EA on MT5 own strategy  |
//| tester... that would be more accurate as it simulates non-ideal   |
//| conditions as well."  He is right, and there was one wall in the  |
//| way: the Strategy Tester can only replay the BROKER's data, whose |
//| tick-count volume is a different metric from the OANDA/Pepperstone|
//| volume this whole method is built on (same candle: MT5 451 vs     |
//| OANDA 2132). Backtesting on broker volume tests a strategy we do  |
//| not trade.                                                        |
//|                                                                   |
//| So: create a CUSTOM SYMBOL and load our real bars into it. The    |
//| tester then replays OUR volume with MT5's real spread, slippage   |
//| and execution model — accurate evidence at last.                  |
//|                                                                   |
//| Run as a SCRIPT on any chart. Reads a CSV from Common\Files with  |
//| header: time_unix,open,high,low,close,volume                      |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

input string InpCsv        = "oanda_m1_history.csv";  // source bars (Common\Files)
input string InpNewSymbol  = "XAUUSD_OANDA";          // custom symbol to create
input string InpCopyFrom   = "XAUUSD";                // broker symbol to copy specs from
input double InpPriceMin   = 0;                       // ignore rows below this price (0 = off)
input double InpPriceMax   = 0;                       // ignore rows above this price (0 = off)

//+------------------------------------------------------------------+
int ReadBars(MqlRates &out[]) {
   int h = FileOpen(InpCsv, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) { PrintFormat("[import] cannot open %s", InpCsv); return 0; }
   int n = 0;
   ArrayResize(out, 200000);
   bool first = true;
   while (!FileIsEnding(h)) {
      string line = FileReadString(h);
      if (line == "") continue;
      if (first) { first = false; if (StringFind(line, "time_unix") >= 0) continue; }
      string f[];
      if (StringSplit(line, ',', f) < 6) continue;
      double o = StringToDouble(f[1]), hi = StringToDouble(f[2]);
      double lo = StringToDouble(f[3]), c = StringToDouble(f[4]);
      if (o <= 0 || hi <= 0 || lo <= 0 || c <= 0) continue;
      // PRICE BAND: our archives ended up holding two instruments after a feed
      // swap (gold rows and BTC rows in one file). The band keeps them apart.
      if (InpPriceMin > 0 && c < InpPriceMin) continue;
      if (InpPriceMax > 0 && c > InpPriceMax) continue;
      out[n].time        = (datetime)StringToInteger(f[0]);
      out[n].open        = o;
      out[n].high        = hi;
      out[n].low         = lo;
      out[n].close       = c;
      out[n].tick_volume = (long)StringToInteger(f[5]);   // OUR volume, the whole point
      out[n].real_volume = (long)StringToInteger(f[5]);
      out[n].spread      = 0;
      n++;
      if (n >= 199990) break;
   }
   FileClose(h);
   ArrayResize(out, n);
   return n;
}

//+------------------------------------------------------------------+
void OnStart() {
   MqlRates rates[];
   int n = ReadBars(rates);
   if (n < 50) { PrintFormat("[import] only %d usable bars — aborting", n); return; }
   ArraySort(rates);           // MqlRates sorts by time

   if (!SymbolSelect(InpCopyFrom, true))
      PrintFormat("[import] warning: cannot select %s to copy specs from", InpCopyFrom);

   // MQL5 has no CustomSymbolExists(): a custom symbol already present simply makes
   // CustomSymbolCreate fail with ERR_MARKET_SELECT_ERROR, which we treat as "exists".
   bool existed = SymbolInfoInteger(InpNewSymbol, SYMBOL_CUSTOM) > 0;
   if (!existed) {
      if (!CustomSymbolCreate(InpNewSymbol, "Custom\\Ghost", InpCopyFrom)) {
         PrintFormat("[import] CustomSymbolCreate failed: %d", GetLastError());
         return;
      }
      PrintFormat("[import] created custom symbol %s (specs copied from %s)",
                  InpNewSymbol, InpCopyFrom);
   } else {
      PrintFormat("[import] custom symbol %s already exists — replacing its bars",
                  InpNewSymbol);
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

   int put = CustomRatesReplace(InpNewSymbol, 0, D'2100.01.01', rates);
   if (put < 0) { PrintFormat("[import] CustomRatesReplace failed: %d", GetLastError()); return; }
   SymbolSelect(InpNewSymbol, true);
   PrintFormat("[import] %s: %d M1 bars loaded (%s .. %s) — open the Strategy Tester "
               "and choose this symbol, period M1, 'Every tick based on real ticks' is "
               "NOT available for custom bars, use 'OHLC M1' or '1 minute OHLC'",
               InpNewSymbol, n,
               TimeToString(rates[0].time, TIME_DATE|TIME_MINUTES),
               TimeToString(rates[n-1].time, TIME_DATE|TIME_MINUTES));
}
//+------------------------------------------------------------------+
