"""Diamond filter + feature log for Trinity_1min (Zee 2026-10-14: "we're looking for the UHV diamond EA to filter
out all bad trades by using trend / volume confirmations from saad and vsisa .. so that the UHV diamond winrate
increases to a very high winrate like 94%"). Run after build_trinity.py.

Filters (all default OFF), checked at the moment Diamond would fire, `side` = its direction:
  InpDiaTrend    1 price on the trade side of the M15 EMA50 · 2 + EMA9 beyond EMA50 · 3 + EMA50 sloping that way
  InpDiaMinER    M15 efficiency ratio over 16 candles >= this (Saad's chop filter)
  InpDiaVsNoOpp  skip when VSISA's last setup (<= 240 min) pointed the OTHER way
  InpDiaVsSame   require a same-direction VSISA setup within this many minutes (0 = off)
  InpDiaSaadSame require an open same-direction Saad position
  InpDiaRegSkip  skip when VSISA's volatility regime is in this bit mask (4 = the high-vol cluster)
  InpDiaHourFrom/To  server-hour window (To <= From = off)
InpDiaLog writes one row per Diamond position to Common\\Files\\trinity_dia_feat.csv with every reading + net."""
from pathlib import Path

M = Path(r'C:\Users\zeesh\turtle\mt5')


def rep(p, a, b):
    s = (M / p).read_text(encoding='utf-8')
    assert s.count(a) == 1, (p, s.count(a), a[:70])
    (M / p).write_text(s.replace(a, b), encoding='utf-8')


rep('TriVsisa.mqh', 'void V_Fire(int side, double sl_level, string why) {\n',
    'void V_Fire(int side, double sl_level, string why) {\n   TriVsRaw(side);\n')
rep('TriDia.mqh', '   int tickets = D_InpStackLots ?', '   if (!TriDiaOk(t, dia)) return;\n   int tickets = D_InpStackLots ?')

HOST = r'''
input group "=== Diamond filters (trend from Saad's core, volume from VSISA's core) ==="
input int    InpDiaTrend    = 0;      // InpDiaTrend — 0 off · 1 price beyond the M15 EMA50 on the trade side · 2 + EMA9 beyond EMA50 · 3 + EMA50 sloping that way
input double InpDiaMinER    = 0.45;   // InpDiaMinER — M15 efficiency ratio (16 candles) at least this (0 = off) [v1.00: 0.45 = 94% WR, report §34]
input bool   InpDiaVsNoOpp  = false;  // InpDiaVsNoOpp — skip when VSISA's last setup within 240 min pointed the other way
input int    InpDiaVsSame   = 0;      // InpDiaVsSame — require a same-direction VSISA setup within this many minutes (0 = off)
input bool   InpDiaSaadSame = false;  // InpDiaSaadSame — require an open same-direction Saad position
input int    InpDiaRegSkip  = 0;      // InpDiaRegSkip — skip in these VSISA regimes (bit mask, 4 = high-vol cluster)
input int    InpDiaHourFrom = 0;      // InpDiaHourFrom — server hour window start
input int    InpDiaHourTo   = 0;      // InpDiaHourTo — window end (<= start = off)
input bool   InpDiaLog      = false;  // InpDiaLog — one CSV row per Diamond position (Common\Files\trinity_dia_feat.csv)

datetime g_tvRawT = 0; int g_tvRawS = 0, g_tvRawSPrev = 0; datetime g_tvRawTPrev = 0;
void TriVsRaw(int side) { g_tvRawTPrev = g_tvRawT; g_tvRawSPrev = g_tvRawS; g_tvRawT = TimeCurrent(); g_tvRawS = side; }
int g_hE9 = INVALID_HANDLE, g_hE50 = INVALID_HANDLE, g_hAtr15 = INVALID_HANDLE, g_hAtr1 = INVALID_HANDLE, g_hE20m5 = INVALID_HANDLE;
int g_dfPass = 0, g_dfBlock = 0;
string g_dfRow = ""; ulong g_dfMaxId = 0; ulong g_dfId[]; string g_dfFeat[]; int g_dfN = 0;
double TriBuf(int h, int k) { double b[1]; return CopyBuffer(h, 0, k, 1, b) == 1 ? b[0] : 0; }
double TriER(int n)
{
   double c0 = iClose(_Symbol, PERIOD_M15, 1), cn = iClose(_Symbol, PERIOD_M15, 1 + n), path = 0;
   for (int k = 1; k <= n; k++) path += MathAbs(iClose(_Symbol, PERIOD_M15, k) - iClose(_Symbol, PERIOD_M15, k + 1));
   return path > 0 ? MathAbs(c0 - cn) / path : 0;
}
bool TriPosSide(long mg, int side)
{
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetInteger(POSITION_MAGIC) != mg || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if ((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1) == side) return true;
   }
   return false;
}
bool TriDiaOk(int side, int dia)
{
   if (g_hE9 == INVALID_HANDLE) {
      g_hE9 = iMA(_Symbol, PERIOD_M15, 9, 0, MODE_EMA, PRICE_CLOSE); g_hE50 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
      g_hAtr15 = iATR(_Symbol, PERIOD_M15, 14); g_hAtr1 = iATR(_Symbol, PERIOD_M1, 14); g_hE20m5 = iMA(_Symbol, PERIOD_M5, 20, 0, MODE_EMA, PRICE_CLOSE);
   }
   double px = side > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double e9 = TriBuf(g_hE9, 1), e50 = TriBuf(g_hE50, 1), e50o = TriBuf(g_hE50, 5), a15 = MathMax(TriBuf(g_hAtr15, 1), _Point);
   double a1 = TriBuf(g_hAtr1, 1), m5e = TriBuf(g_hE20m5, 1), m5eo = TriBuf(g_hE20m5, 4);
   double er = TriER(16);
   datetime now = TimeCurrent();
   int vsAge = g_tvRawT > 0 ? (int)((now - g_tvRawT) / 60) : 99999;
   int vsDir = g_tvRawS * side;                       // +1 VSISA's last setup agrees, -1 opposite
   bool saadSame = TriPosSide(S_InpMagicNumber, side), saadOpp = TriPosSide(S_InpMagicNumber, -side);
   bool vsSame = TriPosSide(V_InpMagicNumber, side), vsOpp = TriPosSide(V_InpMagicNumber, -side);
   MqlDateTime dt; TimeToStruct(now, dt);
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   g_dfRow = StringFormat("%s,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%d,%d,%d,%d,%.2f",
                          TimeToString(now, TIME_DATE | TIME_MINUTES), side, dia,
                          side * (px - e50) / a15, side * (px - e9) / a15, side * (e9 - e50) / a15, side * (e50 - e50o) / a15,
                          er, a1 / a15, side * (px - m5e) / a15, side * (m5e - m5eo) / a15,
                          vsAge, vsDir, (int)saadSame, (int)saadOpp, (int)vsSame, (int)vsOpp, V_g_mlRegime, dt.hour, spread);
   bool ok = true;
   if (InpDiaTrend >= 1 && side * (px - e50) <= 0) ok = false;
   if (InpDiaTrend >= 2 && side * (e9 - e50) <= 0) ok = false;
   if (InpDiaTrend >= 3 && side * (e50 - e50o) <= 0) ok = false;
   if (InpDiaMinER > 0 && er < InpDiaMinER) ok = false;
   if (InpDiaVsNoOpp && vsDir < 0 && vsAge <= 240) ok = false;
   if (InpDiaVsSame > 0 && !(vsDir > 0 && vsAge <= InpDiaVsSame)) ok = false;
   if (InpDiaSaadSame && !saadSame) ok = false;
   if (InpDiaRegSkip > 0 && V_g_mlRegime >= 0 && ((InpDiaRegSkip >> V_g_mlRegime) & 1) == 1) ok = false;
   if (InpDiaHourTo > InpDiaHourFrom && (dt.hour < InpDiaHourFrom || dt.hour >= InpDiaHourTo)) ok = false;
   if (ok) g_dfPass++; else g_dfBlock++;
   return ok;
}
void TriDiaTrack()
{
   for (int i = 0; i < PositionsTotal(); i++) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetInteger(POSITION_MAGIC) != D_InpMagicNumber) continue;
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if (id <= g_dfMaxId) continue;
      g_dfN++; ArrayResize(g_dfId, g_dfN, 1024); ArrayResize(g_dfFeat, g_dfN, 1024);
      g_dfId[g_dfN - 1] = id; g_dfFeat[g_dfN - 1] = g_dfRow + "," + IntegerToString((long)PositionGetInteger(POSITION_TIME));
   }
   for (int i = 0; i < PositionsTotal(); i++) {
      ulong t = PositionGetTicket(i);
      if (t > 0 && PositionGetInteger(POSITION_MAGIC) == D_InpMagicNumber) { ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER); if (id > g_dfMaxId) g_dfMaxId = id; }
   }
}
void TriDiaLog()
{
   PrintFormat("[TRINITY-DIA] filter passed %d blocked %d", g_dfPass, g_dfBlock);
   if (!InpDiaLog || g_dfN == 0 || !HistorySelect(0, TimeCurrent() + 86400)) return;
   int h = FileOpen("trinity_dia_feat.csv", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   FileWrite(h, "time,side,dia,px_e50,px_e9,e9_e50,e50_slope,er,atr1_atr15,px_m5e20,m5e20_slope,vs_age,vs_dir,saad_same,saad_opp,vs_same,vs_opp,regime,hour,spread,open_unix,net");
   for (int j = 0; j < g_dfN; j++) {
      double net = 0, vin = 0, com = 0;
      if (HistorySelectByPosition(g_dfId[j]))
         for (int i = 0; i < HistoryDealsTotal(); i++) {
            ulong d = HistoryDealGetTicket(i);
            if (HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) vin += HistoryDealGetDouble(d, DEAL_VOLUME);
            com += HistoryDealGetDouble(d, DEAL_COMMISSION);
            net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
         }
      if (com == 0) net -= 4.0 * vin;
      FileWrite(h, g_dfFeat[j] + "," + DoubleToString(net, 2));
   }
   FileClose(h);
}
'''
rep('Trinity_1min.mq5', 'int OnInit()\n{{'.replace('{{', '{'), HOST + '\nint OnInit()\n{')
rep('Trinity_1min.mq5', '   if (InpUseDia)   D_OnTick();\n', '   if (InpUseDia)   D_OnTick();\n   TriDiaTrack();\n')
rep('Trinity_1min.mq5', '   TriStats();\n', '   TriStats();\n   TriDiaLog();\n')
print('trinity diamond filter added')
