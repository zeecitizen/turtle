//+------------------------------------------------------------------+
//| SwapProbe.mq5 - script: print the broker's gold swap terms and,   |
//| with InpApply, copy them onto the real-tick custom symbol so the  |
//| Strategy Tester charges overnight swap (2026-10-13: AxiTickClone  |
//| did not copy swap, so XAUUSD_TK tests held positions for free).    |
//+------------------------------------------------------------------+
#property script_show_inputs
input string InpSrc   = "XAUUSD.pro";
input string InpDst   = "XAUUSD_TK";
input bool   InpApply = true;

void OnStart()
{
   SymbolSelect(InpSrc, true);
   long mode = SymbolInfoInteger(InpSrc, SYMBOL_SWAP_MODE);
   double sl = SymbolInfoDouble(InpSrc, SYMBOL_SWAP_LONG), ss = SymbolInfoDouble(InpSrc, SYMBOL_SWAP_SHORT);
   long tri = SymbolInfoInteger(InpSrc, SYMBOL_SWAP_ROLLOVER3DAYS);
   PrintFormat("[swap] %s mode %d long %.4f short %.4f triple-swap day %d | %s mode %d long %.4f short %.4f",
               InpSrc, mode, sl, ss, tri, InpDst, SymbolInfoInteger(InpDst, SYMBOL_SWAP_MODE),
               SymbolInfoDouble(InpDst, SYMBOL_SWAP_LONG), SymbolInfoDouble(InpDst, SYMBOL_SWAP_SHORT));
   if (InpApply && SymbolInfoInteger(InpDst, SYMBOL_CUSTOM) > 0) {
      bool ok = CustomSymbolSetInteger(InpDst, SYMBOL_SWAP_MODE, mode)
             && CustomSymbolSetDouble(InpDst, SYMBOL_SWAP_LONG, sl)
             && CustomSymbolSetDouble(InpDst, SYMBOL_SWAP_SHORT, ss)
             && CustomSymbolSetInteger(InpDst, SYMBOL_SWAP_ROLLOVER3DAYS, tri);
      PrintFormat("[swap] applied to %s: %s (err %d)", InpDst, ok ? "OK" : "FAILED", GetLastError());
   }
   Print("[swap] DONE");
   TerminalClose(0);
}
