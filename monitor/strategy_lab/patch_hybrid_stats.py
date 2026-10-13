"""Add per-engine, per-position results to Hybrid_Saad15_VSISA5.mq5 (run after build_hybrid.py)."""
p = r'C:\Users\zeesh\turtle\mt5\Hybrid_Saad15_VSISA5.mq5'
s = open(p, encoding='utf-8').read()
STATS = r'''// per-engine, per-POSITION results (one position = one trade, partial closes included; $4/lot when no commission is booked)
void HybStats()
{
   if (!HistorySelect(0, TimeCurrent() + 86400)) return;
   ulong pid[]; long mg[]; double net[], vin[], com[]; int n = 0;
   for (int i = 0; i < HistoryDealsTotal(); i++) {
      ulong d = HistoryDealGetTicket(i); long tp = HistoryDealGetInteger(d, DEAL_TYPE);
      if (tp != DEAL_TYPE_BUY && tp != DEAL_TYPE_SELL) continue;
      ulong ps = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID); int k = -1;
      for (int j = 0; j < n; j++) if (pid[j] == ps) { k = j; break; }
      if (k < 0) { k = n++; ArrayResize(pid, n); ArrayResize(mg, n); ArrayResize(net, n); ArrayResize(vin, n); ArrayResize(com, n); pid[k] = ps; mg[k] = 0; net[k] = 0; vin[k] = 0; com[k] = 0; }
      if (HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) { mg[k] = HistoryDealGetInteger(d, DEAL_MAGIC); vin[k] += HistoryDealGetDouble(d, DEAL_VOLUME); }
      com[k] += HistoryDealGetDouble(d, DEAL_COMMISSION);
      net[k] += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
   }
   long mags[2]; mags[0] = S_InpMagicNumber; mags[1] = InpMagicNumber;
   string nm[2] = {"PROBE (Saad 15m)", "ADDS (VSISA 5m)"};
   for (int m = 0; m < 2; m++) {
      int c = 0, w = 0; double tot = 0;
      for (int j = 0; j < n; j++) if (mg[j] == mags[m]) { double x = net[j] - (com[j] == 0 ? 4.0 * vin[j] : 0); c++; tot += x; if (x > 0) w++; }
      PrintFormat("[HYBRID-STATS] %s trades %d wins %d WR %.1f%% net %.2f", nm[m], c, w, c > 0 ? 100.0 * w / c : 0, tot);
   }
}
'''
a = 'void HybCloseAdds()'
assert s.count(a) == 1
s = s.replace(a, STATS + a)
b = 'void OnDeinit(const int reason) {\n   if (InpHybSaad) S_OnDeinit(reason);'
assert s.count(b) == 1
s = s.replace(b, 'void OnDeinit(const int reason) {\n   HybStats();\n   if (InpHybSaad) S_OnDeinit(reason);')
open(p, 'w', encoding='utf-8').write(s)
print('stats added')
