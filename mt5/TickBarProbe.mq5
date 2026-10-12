//+------------------------------------------------------------------+
//| TickBarProbe.mq5 - script: do the broker's M1 bars agree with its |
//| ticks? (2026-10-12: the tester discards 50-68% of Jan-Jul minutes |
//| on Axi XAUUSD.pro because tick prices fall outside the bars.)      |
//| For sample days it compares each M1 bar's high/low with the bid    |
//| max/min of the ticks inside that minute, and also tries shifted    |
//| alignments (+-1h, +-2h) to detect a time-zone shift.               |
//| Output: Print lines "[probe] ..." in the terminal's MQL5\Logs.     |
//+------------------------------------------------------------------+
#property script_show_inputs
input string InpSymbol = "XAUUSD.pro";
input string InpDays   = "2026.01.05,2026.01.15,2026.02.10,2026.03.10,2026.04.14,2026.05.12,2026.06.16,2026.07.14,2026.08.18,2026.09.15,2026.10.06";

void ProbeDay(datetime day)
{
   MqlRates r[];
   int nb = -1;
   for (int tries = 0; tries < 20 && nb <= 0; tries++) {      // the terminal downloads missing history on demand
      nb = CopyRates(InpSymbol, PERIOD_M1, day, day + 86400 - 1, r);
      if (nb <= 0) Sleep(1000);
   }
   MqlTick tk[];
   int nt = CopyTicksRange(InpSymbol, tk, COPY_TICKS_ALL, (ulong)day * 1000, (ulong)(day + 86400) * 1000);
   if (nb <= 0 || nt <= 0) { PrintFormat("[probe] %s bars %d ticks %d (err %d)", TimeToString(day, TIME_DATE), nb, nt, GetLastError()); return; }
   int shifts[] = {0, 3600, -3600, 7200, -7200};
   for (int s = 0; s < ArraySize(shifts); s++) {
      int sh = shifts[s];
      int checked = 0, bad = 0, hiAbove = 0, loBelow = 0, empty = 0;
      double sumHi = 0, sumLo = 0, sumAskHi = 0;
      int j = 0;
      for (int i = 0; i < nb; i++) {
         datetime t0 = r[i].time + sh, t1 = t0 + 60;
         while (j < nt && tk[j].time < t0) j++;
         int k = j; double bmax = -1, bmin = 1e18, amax = -1;
         while (k < nt && tk[k].time < t1) { if (tk[k].bid > 0) { bmax = MathMax(bmax, tk[k].bid); bmin = MathMin(bmin, tk[k].bid); } amax = MathMax(amax, tk[k].ask); k++; }
         if (bmax < 0) { empty++; continue; }
         checked++;
         double eps = _Point * 0.5;
         bool b = bmax > r[i].high + eps || bmin < r[i].low - eps;
         if (b) bad++;
         if (bmax > r[i].high + eps) hiAbove++;
         if (bmin < r[i].low - eps) loBelow++;
         sumHi += bmax - r[i].high; sumLo += bmin - r[i].low; sumAskHi += amax - r[i].high;
      }
      if (checked == 0) continue;
      PrintFormat("[probe] %s shift %+5ds: bars %d ticks %d | minutes checked %d, outside bar %d (%.0f%%) [tick max > bar high %d, tick min < bar low %d] | avg(tickBidMax-barHigh) %.3f avg(tickBidMin-barLow) %.3f avg(tickAskMax-barHigh) %.3f | empty %d",
                  TimeToString(day, TIME_DATE), sh, nb, nt, checked, bad, 100.0 * bad / checked, hiAbove, loBelow,
                  sumHi / checked, sumLo / checked, sumAskHi / checked, empty);
   }
   // three example minutes that disagree at shift 0
   int shown = 0, j2 = 0;
   for (int i = 0; i < nb && shown < 3; i++) {
      datetime t0 = r[i].time, t1 = t0 + 60;
      while (j2 < nt && tk[j2].time < t0) j2++;
      int k = j2; double bmax = -1, bmin = 1e18; int cnt = 0;
      while (k < nt && tk[k].time < t1) { bmax = MathMax(bmax, tk[k].bid); bmin = MathMin(bmin, tk[k].bid); cnt++; k++; }
      if (cnt > 0 && (bmax > r[i].high + _Point * 0.5 || bmin < r[i].low - _Point * 0.5)) {
         PrintFormat("[probe]   e.g. %s bar O %.2f H %.2f L %.2f C %.2f vol %d | %d ticks bid %.2f..%.2f first %.2f last %.2f",
                     TimeToString(t0, TIME_DATE | TIME_MINUTES), r[i].open, r[i].high, r[i].low, r[i].close, (int)r[i].tick_volume,
                     cnt, bmin, bmax, tk[j2].bid, tk[k - 1].bid);
         shown++;
      }
   }
}

void OnStart()
{
   SymbolSelect(InpSymbol, true);
   string d[]; int n = StringSplit(InpDays, ',', d);
   for (int i = 0; i < n; i++) ProbeDay(StringToTime(d[i]));
   Print("[probe] DONE");
}
