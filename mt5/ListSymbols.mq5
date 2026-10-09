// ListSymbols.mq5 - prints every symbol the broker offers, then stops. Tester helper.
#property strict
int OnInit()
{
   int n = SymbolsTotal(false);
   for(int i = 0; i < n; i++)
   {
      string s = SymbolName(i, false);
      PrintFormat("SYM %s | %s | %s", s, SymbolInfoString(s, SYMBOL_PATH),
                  SymbolInfoString(s, SYMBOL_DESCRIPTION));
   }
   return(INIT_FAILED);
}
void OnTick() {}
