// HourProbe.mq5 - tester helper: M5 bars per server hour since InpFrom. Gold's daily maintenance
// break (21:00-22:00 UTC in summer, 22:00-23:00 in winter) shows up as the empty hour, which
// gives each broker's server clock offset from UTC.
#property strict
input datetime InpFrom = D'2026.06.01';
int OnInit() { return(INIT_SUCCEEDED); }
void OnTick() {}
void OnDeinit(const int reason)
{
   int cnt[24]; ArrayInitialize(cnt, 0);
   int n = Bars(_Symbol, PERIOD_M5);
   for (int i = 1; i < n; i++) {
      datetime t = iTime(_Symbol, PERIOD_M5, i);
      if (t < InpFrom) break;
      MqlDateTime d; TimeToStruct(t, d);
      cnt[d.hour]++;
   }
   string s = "";
   for (int h = 0; h < 24; h++) s += StringFormat("%02d:%d ", h, cnt[h]);
   PrintFormat("HOURPROBE %s %s", _Symbol, s);
}
