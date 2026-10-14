//+------------------------------------------------------------------+
//| SaadEMAs.mq5 v1.00 (2026-10-14) - the two EMAs Saad_strategy_15min |
//| trades on, drawn thick: EMA 9 blue, EMA 50 red. Computed on        |
//| InpTF (default M15, the strategy's candles) and drawn on any chart |
//| timeframe (on a lower timeframe each bar shows the M15 value of    |
//| the M15 candle it belongs to). Embedded in TradeLifecycle.ex5 as a |
//| resource, so it needs no separate install.                         |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2
#property indicator_label1  "EMA 9"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDodgerBlue
#property indicator_style1  STYLE_SOLID
#property indicator_width1  3
#property indicator_label2  "EMA 50"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrRed
#property indicator_style2  STYLE_SOLID
#property indicator_width2  3

input ENUM_TIMEFRAMES InpTF   = PERIOD_M15;  // InpTF — timeframe the EMAs are computed on
input int             InpFast = 9;           // InpFast — fast EMA (blue)
input int             InpSlow = 50;          // InpSlow — slow EMA (red)

double bFast[], bSlow[];
int hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE;

int OnInit()
{
   SetIndexBuffer(0, bFast, INDICATOR_DATA);
   SetIndexBuffer(1, bSlow, INDICATOR_DATA);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   ENUM_TIMEFRAMES tf = InpTF == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)Period() : InpTF;
   hFast = iMA(_Symbol, tf, InpFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, tf, InpSlow, 0, MODE_EMA, PRICE_CLOSE);
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE) return INIT_FAILED;
   IndicatorSetString(INDICATOR_SHORTNAME, "SaadEMAs");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   return INIT_SUCCEEDED;
}

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[], const double &open[],
                const double &high[], const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
{
   ENUM_TIMEFRAMES tf = InpTF == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)Period() : InpTF;
   int ready = MathMin(BarsCalculated(hFast), BarsCalculated(hSlow));
   if (ready <= 0) return prev_calculated;                      // the EMAs are still loading: try on the next tick
   ArraySetAsSeries(time, false);
   int start = prev_calculated > 1 ? prev_calculated - 1 : 0;
   if (tf == Period()) {                                         // same timeframe: copy straight across
      double f[], s[];
      int n = rates_total - start;
      if (CopyBuffer(hFast, 0, 0, n, f) != n || CopyBuffer(hSlow, 0, 0, n, s) != n) return prev_calculated;
      for (int i = 0; i < n; i++) { bFast[start + i] = f[i]; bSlow[start + i] = s[i]; }
      return rates_total;
   }
   for (int i = start; i < rates_total; i++) {                   // another timeframe: the value of the candle this bar belongs to
      int sh = iBarShift(_Symbol, tf, time[i], false);
      double f[1], s[1];
      if (sh < 0 || CopyBuffer(hFast, 0, sh, 1, f) != 1 || CopyBuffer(hSlow, 0, sh, 1, s) != 1) { bFast[i] = EMPTY_VALUE; bSlow[i] = EMPTY_VALUE; continue; }
      bFast[i] = f[0]; bSlow[i] = s[0];
   }
   return rates_total;
}
