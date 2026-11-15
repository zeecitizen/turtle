//+------------------------------------------------------------------+
//| SimpleRule.mq5 - the accuracy test (Zee 2026-10-22): one rule, no Saad logic.
//| Every day at InpHour:InpMinute (server time) buy at market if flat, stop InpSlUsd below, target InpTpUsd above,
//| closed after InpMaxMin minutes if neither is hit. Used to compare MT5 with PyEventBT trade by trade.
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input int    InpHour    = 10;     // InpHour - entry hour (server time)
input int    InpMinute  = 0;      // InpMinute - entry minute
input double InpLots    = 1.0;    // InpLots
input double InpSlUsd   = 3.0;    // InpSlUsd - stop distance ($ of price)
input double InpTpUsd   = 6.0;    // InpTpUsd - target distance ($ of price)
input int    InpMaxMin  = 100000000;     // InpMaxMin - time exit, minutes after entry
input int    InpMagic   = 88500;  // InpMagic

CTrade trade;
datetime g_entryTime = 0;
int g_lastDay = -1;

int OnInit() { trade.SetExpertMagicNumber(InpMagic); return INIT_SUCCEEDED; }

void OnTick()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   bool open = PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC) == InpMagic;
   if (open) {
      if (TimeCurrent() - g_entryTime >= InpMaxMin * 60) trade.PositionClose(_Symbol);
      return;
   }
   if (dt.hour == InpHour && dt.min == InpMinute && dt.day_of_year != g_lastDay) {
      g_lastDay = dt.day_of_year;
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if (trade.Buy(InpLots, _Symbol, ask, ask - InpSlUsd, ask + InpTpUsd, "simple")) g_entryTime = TimeCurrent();
   }
}
