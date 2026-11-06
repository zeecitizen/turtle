"""Build mt5/VSISA_ml.mq5 = VSISA (unchanged behaviour with every switch off) + the machine-learning hooks of
report.md sections 13-19 (Zee 2026-10-14: "apply all the machine learning methods described in report.md to the
VSISA EA on 5 min timeframe"). Everything is computed by the EA itself, logged to Common\\Files, and judged in
the MT5 Strategy Tester:
  InpMlLog       entry features (+ position id) -> vml_<tag>_feat.csv, final net of each position -> vml_<tag>_out.csv,
                 every open position at each candle close -> vml_<tag>_exh.csv, regime features per candle -> vml_<tag>_reg.csv
  InpMetaMode    1 = meta-label model compiled in (VsisaMetaModel.mqh): skip when its score < InpMetaThr
                 (classifier: probability; regression: predicted $)
  InpRegimeMode  1 = GMM compiled in (VsisaRegimeModel.mqh): skip entries in the regimes set in InpRegSkipMask (bit k = cluster k)
  InpExhMode     1 = exhaustion model (VsisaExhaustModel.mqh): close a profitable position when P >= InpExhThr
  InpDrlMode     1 = PPO policy (VsisaDrlPolicy.mqh) sets a lot multiplier 0..2 · 2 = constant InpDrlConst (benchmark)"""
src = r'C:\Users\zeesh\turtle\mt5\VSISA.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\VSISA_ml.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


rep('#include <Trade/Trade.mqh>', '#include <Trade/Trade.mqh>\n#include "VsisaMetaModel.mqh"\n#include "VsisaRegimeModel.mqh"\n#include "VsisaExhaustModel.mqh"\n#include "VsisaDrlPolicy.mqh"')
rep('input bool   InpVerbose     = true;', '''input group "=== Machine learning (report.md 13-19) - all OFF = plain VSISA ==="
input bool   InpMlLog       = false;  // InpMlLog — log features / outcomes / open positions / regime features (training data)
input int    InpMlTag       = 1;      // InpMlTag — log file number vml_<n>_*.csv (one per rig/run)
input int    InpMetaMode    = 0;      // InpMetaMode — 1 = skip when the compiled meta-label model's score < InpMetaThr
input double InpMetaThr     = 0.5;    // InpMetaThr — classifier: probability · regression: predicted $
input int    InpRegimeMode  = 0;      // InpRegimeMode — 1 = compiled GMM regime filter
input int    InpRegSkipMask = 0;      // InpRegSkipMask — skip entries in these regimes (bit 0 = cluster 0, bit 1 = cluster 1, bit 2 = cluster 2)
input int    InpExhMode     = 0;      // InpExhMode — 1 = close a profitable position when the exhaustion model says P >= InpExhThr
input double InpExhThr      = 0.85;   // InpExhThr
input int    InpDrlMode     = 0;      // InpDrlMode — 1 = PPO lot multiplier (0..2) · 2 = constant InpDrlConst
input double InpDrlConst    = 1.0;    // InpDrlConst
input bool   InpVerbose     = true;''')

rep('void Fire(int side, double sl_level, string why) {', r'''//--- machine-learning hooks -----------------------------------------------------
int g_mlAtr = INVALID_HANDLE, g_mlAtr200 = INVALID_HANDLE, g_mlE9 = INVALID_HANDLE, g_mlE50 = INVALID_HANDLE;
int g_mlRegime = -1, g_mlMetaVeto = 0, g_mlRegVeto = 0, g_mlExh = 0, g_mlDrlVeto = 0; double g_mlDrlSum = 0; int g_mlDrlN = 0;
ulong g_mlOpen[];          // positions seen open last tick (to log their outcome when they close)
double MlBuf(int h, int s) { double v[1]; return (h != INVALID_HANDLE && CopyBuffer(h, 0, s, 1, v) == 1) ? v[0] : 0.0; }
string MlFile(string kind) { return StringFormat("vml_%d_%s.csv", InpMlTag, kind); }
void MlAppend(string kind, string header, string row)
{
   int h = FileOpen(MlFile(kind), FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   if (FileSize(h) == 0) FileWriteString(h, header + "\r\n");
   FileSeek(h, 0, SEEK_END); FileWriteString(h, row + "\r\n"); FileClose(h);
}
double MlEr(int n) { double net = MathAbs(bClose(1) - bClose(n + 1)), path = 0; for (int i = 1; i <= n; i++) path += MathAbs(bClose(i) - bClose(i + 1)); return path > 0 ? net / path : 0; }
double MlRvol(int n) { double r[], m = 0; ArrayResize(r, n); for (int i = 0; i < n; i++) { double a = bClose(i + 1), b = bClose(i + 2); r[i] = (a > 0 && b > 0) ? MathLog(a / b) : 0; m += r[i]; } m /= n; double v = 0; for (int i = 0; i < n; i++) v += (r[i] - m) * (r[i] - m); return MathSqrt(v / (n - 1)); }
// entry features: order MUST match V_META_NAMES in the trainers
void MlFeatures(int side, double entry, double sl, double tp, string why, double &f[])
{
   ArrayResize(f, V_META_NF);
   double atr = MathMax(MlBuf(g_mlAtr, 1), _Point), atr200 = MlBuf(g_mlAtr200, 1), risk = MathAbs(entry - sl);
   double c1 = bClose(1), e9 = MlBuf(g_mlE9, 1), e50 = MlBuf(g_mlE50, 1), e50b = MlBuf(g_mlE50, 6);
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   f[0] = side; f[1] = risk / atr; f[2] = (tp > 0 && risk > 0) ? MathMin(MathAbs(tp - entry) / risk, 20) : 0;
   f[3] = MlEr(14); f[4] = atr200 > 0 ? atr / atr200 : 1; f[5] = side * (c1 - e50) / atr; f[6] = side * (c1 - e9) / atr;
   f[7] = side * (e50 - e50b) / atr; f[8] = dt.hour; f[9] = dt.day_of_week;
   f[10] = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   f[11] = g_react_ratio; f[12] = StringFind(why, "FADE") == 0 ? 1 : 0; f[13] = TrendDir() * side; f[14] = bRange(1) / atr;
}
string MlRow(ulong pos, const double &f[], double score, int veto)
{
   string r = StringFormat("%I64u,%s", pos, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
   for (int i = 0; i < V_META_NF; i++) r += StringFormat(",%.8f", f[i]);
   return r + StringFormat(",%.8f,%d", score, veto);
}
string MlHeader() { string h = "pos_id,time"; for (int i = 0; i < V_META_NF; i++) h += "," + V_META_NAMES[i]; return h + ",score,veto"; }
// regime features of the candle that just closed: [ER14, ATR14/ATR200, realized vol 14]
bool MlRegFeat(double &x[]) { ArrayResize(x, 3); double atr = MlBuf(g_mlAtr, 1), a2 = MlBuf(g_mlAtr200, 1); if (atr <= 0 || a2 <= 0) return false; x[0] = MlEr(14); x[1] = atr / a2; x[2] = MlRvol(14); return true; }
// once per tick: positions that disappeared -> their final net
void MlTick()
{
   if (!InpMlLog) return;
   ulong now[]; int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if (t > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) { ArrayResize(now, n + 1); now[n++] = (ulong)PositionGetInteger(POSITION_IDENTIFIER); } }
   for (int k = 0; k < ArraySize(g_mlOpen); k++) {
      bool still = false; for (int j = 0; j < n; j++) if (now[j] == g_mlOpen[k]) { still = true; break; }
      if (still || !HistorySelectByPosition(g_mlOpen[k])) continue;
      double prof = 0, comm = 0, swp = 0, vin = 0;
      for (int d = 0; d < HistoryDealsTotal(); d++) { ulong dl = HistoryDealGetTicket(d); comm += HistoryDealGetDouble(dl, DEAL_COMMISSION);
         if (HistoryDealGetInteger(dl, DEAL_ENTRY) == DEAL_ENTRY_IN) { vin += HistoryDealGetDouble(dl, DEAL_VOLUME); continue; }
         prof += HistoryDealGetDouble(dl, DEAL_PROFIT); swp += HistoryDealGetDouble(dl, DEAL_SWAP); }
      if (comm == 0) comm = -4.0 * vin;
      MlAppend("out", "pos_id,profit,commission,swap,net,lots", StringFormat("%I64u,%.2f,%.2f,%.2f,%.2f,%.2f", g_mlOpen[k], prof, comm, swp, prof + comm + swp, vin));
   }
   ArrayResize(g_mlOpen, n); for (int j = 0; j < n; j++) g_mlOpen[j] = now[j];
}
// once per new candle: regime, logs of open positions, exhaustion exit
void MlBar()
{
   double x[];
   if ((InpRegimeMode > 0 || InpMlLog) && MlRegFeat(x)) {
      g_mlRegime = InpRegimeMode > 0 ? V_RegimeOf(x) : -1;
      if (InpMlLog) MlAppend("reg", "time,kaufman_er,atr_ratio,realized_vol", StringFormat("%s,%.8f,%.8f,%.10f", TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_DATE | TIME_MINUTES), x[0], x[1], x[2]));
   }
   if (InpExhMode <= 0 && !InpMlLog) return;
   double atr = MathMax(MlBuf(g_mlAtr, 1), _Point), a2 = MlBuf(g_mlAtr200, 1);
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if (ot >= iTime(_Symbol, PERIOD_CURRENT, 0)) continue;
      int side = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double en = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL);
      double px = side > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double risk = sl > 0 ? MathAbs(en - sl) : atr; if (risk <= 0) risk = atr;
      int bars = iBarShift(_Symbol, PERIOD_CURRENT, ot);
      double best = side > 0 ? iHigh(_Symbol, PERIOD_CURRENT, iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, MathMax(1, bars), 1)) : iLow(_Symbol, PERIOD_CURRENT, iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW, MathMax(1, bars), 1));
      double e[]; ArrayResize(e, V_EXH_NF);
      double fr = side * (px - en) / risk, mr = MathMax(fr, side * (best - en) / risk);
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      e[0] = side; e[1] = bars; e[2] = fr; e[3] = mr; e[4] = mr - fr; e[5] = MlEr(14); e[6] = side * (bClose(1) - MlBuf(g_mlE50, 1)) / atr;
      e[7] = side * (bClose(1) - MlBuf(g_mlE9, 1)) / atr; e[8] = a2 > 0 ? atr / a2 : 1; e[9] = sl > 0 ? side * (px - sl) / risk : 0;
      e[10] = side * (bClose(1) - bOpen(1)) / atr; e[11] = dt.hour; e[12] = PositionGetDouble(POSITION_TP) > 0 ? side * (PositionGetDouble(POSITION_TP) - px) / risk : 0;
      double flt = PositionGetDouble(POSITION_PROFIT), p = -1; int closed = 0;
      if (InpExhMode == 1 && flt > 0) { p = V_ExhModelProb(e); if (p >= InpExhThr && trade.PositionClose(t)) { g_mlExh++; closed = 1; } }
      if (InpMlLog) {
         string r = StringFormat("%I64u,%s", (ulong)PositionGetInteger(POSITION_IDENTIFIER), TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
         for (int k = 0; k < V_EXH_NF; k++) r += StringFormat(",%.8f", e[k]);
         string h = "pos_id,time"; for (int k = 0; k < V_EXH_NF; k++) h += "," + V_EXH_NAMES[k];
         MlAppend("exh", h + ",float_usd,realized_usd,prob,closed", r + StringFormat(",%.2f,0,%.8f,%d", flt, p, closed));
      }
   }
}

void Fire(int side, double sl_level, string why) {
   if (InpRegimeMode > 0 && g_mlRegime >= 0 && ((InpRegSkipMask >> g_mlRegime) & 1) == 1) { g_mlRegVeto++; return; }''')

rep('   int n = MathMax(1, InpTickets);\n',
    r'''   // ML: features, meta-label gate, DRL sizing (the EA's own entry/stop/target, computed above)
   double mlf[]; double mlscore = -1;
   bool mlOn = InpMlLog || InpMetaMode > 0 || InpDrlMode > 0;
   if (mlOn) MlFeatures(side, entry, sl_level, tp, why, mlf);
   if (InpMetaMode > 0) {
      mlscore = V_MetaModelScore(mlf);
      if (mlscore < InpMetaThr) { g_mlMetaVeto++; if (InpMlLog) MlAppend("feat", MlHeader(), MlRow(0, mlf, mlscore, 1)); return; }
   }
   if (InpDrlMode > 0) {
      double rx[]; double mult = InpDrlConst;
      if (InpDrlMode == 1 && MlRegFeat(rx)) { double o[5]; o[0] = rx[0]; o[1] = rx[1]; o[2] = rx[2]; o[3] = mlf[5]; o[4] = side; mult = MathMax(0.0, MathMin(2.0, V_DrlPolicy(o))); }
      if (mult < 0.1) { g_mlDrlVeto++; return; }
      double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), lo = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      lots = NormalizeDouble(MathMax(lo, MathRound(lots * mult / st) * st), 2);
      g_mlDrlSum += mult; g_mlDrlN++;
   }
   int n = MathMax(1, InpTickets);
''')
rep('      if (ok) placed++;\n',
    '      if (ok) placed++;\n'
    '      if (ok && InpMlLog) { ulong pid = trade.ResultOrder(); if (HistoryDealSelect(trade.ResultDeal())) pid = (ulong)HistoryDealGetInteger(trade.ResultDeal(), DEAL_POSITION_ID); MlAppend("feat", MlHeader(), MlRow(pid, mlf, mlscore, 0)); }\n')
rep('   g_last_bar = t;\n', '   g_last_bar = t;\n   MlBar();\n')
rep('void OnTick() {\n', 'void OnTick() {\n   MlTick();\n')
rep('int OnInit() {\n', '''int OnInit() {
   g_mlAtr = iATR(_Symbol, PERIOD_CURRENT, 14); g_mlAtr200 = iATR(_Symbol, PERIOD_CURRENT, 200);
   g_mlE9 = iMA(_Symbol, PERIOD_CURRENT, 9, 0, MODE_EMA, PRICE_CLOSE); g_mlE50 = iMA(_Symbol, PERIOD_CURRENT, 50, 0, MODE_EMA, PRICE_CLOSE);
   if (InpMlLog && MQLInfoInteger(MQL_TESTER)) { string k[] = {"feat", "out", "exh", "reg"}; for (int i = 0; i < 4; i++) FileDelete(MlFile(k[i]), FILE_COMMON); }
''')
rep('void OnDeinit(const int reason) {\n', 'void OnDeinit(const int reason) {\n   PrintFormat("[VSISA-ML] meta vetoed %d | regime vetoed %d | exhaustion closes %d | DRL avg x%.3f over %d, skipped %d", g_mlMetaVeto, g_mlRegVeto, g_mlExh, g_mlDrlN > 0 ? g_mlDrlSum / g_mlDrlN : 0, g_mlDrlN, g_mlDrlVeto);\n')
open(dst, 'w', encoding='utf-8').write(s)

stubs = {
    "VsisaMetaModel.mqh": '// VsisaMetaModel.mqh - PLACEHOLDER (untrained): approves everything. Regenerated by meta_labeling_system/src/vsisa_train.py\n#define V_META_NF 15\nstring V_META_NAMES[V_META_NF] = {"f_side","f_risk_atr","f_tp_r","f_er","f_atr_ratio","f_ema50_dist","f_ema9_dist","f_slope50","f_hour","f_dow","f_spread","f_react_ratio","f_fade","f_trend","f_range_atr"};\ndouble V_MetaModelScore(const double &f[]) { return 1e9; }\n',
    "VsisaRegimeModel.mqh": '// VsisaRegimeModel.mqh - PLACEHOLDER (untrained)\nint V_RegimeOf(const double &x[]) { return -1; }\n',
    "VsisaExhaustModel.mqh": '// VsisaExhaustModel.mqh - PLACEHOLDER (untrained)\n#define V_EXH_NF 13\nstring V_EXH_NAMES[V_EXH_NF] = {"x_side","x_bars","x_float_r","x_mfe_r","x_giveback_r","x_er","x_ema50_dist","x_ema9_dist","x_atr_ratio","x_room_r","x_body","x_hour","x_tp_left_r"};\ndouble V_ExhModelProb(const double &x[]) { return 0.0; }\n',
    "VsisaDrlPolicy.mqh": '// VsisaDrlPolicy.mqh - PLACEHOLDER (untrained): multiplier 1\ndouble V_DrlPolicy(const double &o[]) { return 1.0; }\n'}
for n, t in stubs.items():
    open(r'C:\Users\zeesh\turtle\mt5\\' + n, 'w', encoding='utf-8').write(t)
print('wrote', dst, '+ stubs')
