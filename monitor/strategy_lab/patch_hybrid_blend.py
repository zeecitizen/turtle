"""Blend modes for Hybrid_Saad15_VSISA5 (run after build_hybrid.py + patch_hybrid_stats.py).
Zee 2026-10-14: "what if the pyramidding inner trade is saad's EA and the outer one is the 5 minute VSISA? ...
the VSISA can tell hey the market is moving up now.. then Saad's EA takes its trade and that's a doubled
confirmation so the chances of that trade winning should double."

Confirmation definitions (the OTHER engine, same direction):
  1 = it has an OPEN position     2 = it OPENED a trade within InpHybWinMin minutes
  3 = it SAW a setup (raw, before VSISA's ML filters / Saad's skips) within InpHybWinMin minutes
InpHybSaadGate (VSISA confirms Saad) 0 off / 1-3; InpHybSaadAct 0 = skip unconfirmed Saad trades,
1 = take all, confirmed ones at InpHybConfMult x lots.  InpHybVsGate (Saad confirms VSISA) 0 = the old
probe rule (InpHybNeedProbe/InpHybMature) / 2-3 = definitions above.
Every position is TAGGED at open with all definitions, and OnDeinit prints win rate per tag."""
from pathlib import Path

M = Path(r'C:\Users\zeesh\turtle\mt5')

# ---- engine hooks -------------------------------------------------------------------------------------------
e = (M / 'SaadEngine15.mqh').read_text(encoding='utf-8')
a = 'void S_DoEntry(int side, double sl)\n{\n'
assert e.count(a) == 1
e = e.replace(a, a + '   HybRaw(0, side);\n   if (!HybSaadOk(side)) return;\n')
a = '   double lots = S_LotsFor(side, en, sl);\n'
assert e.count(a) == 1
e = e.replace(a, a + '   lots = HybSaadLots(side, lots);\n')
(M / 'SaadEngine15.mqh').write_text(e, encoding='utf-8')

# ---- hybrid EA ----------------------------------------------------------------------------------------------
p = M / 'Hybrid_Saad15_VSISA5.mq5'
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


rep('input bool   InpHybNeedProbe = true;', '''input bool   InpHybNeedProbe = true;
input int    InpHybSaadGate = 0;      // InpHybSaadGate — VSISA confirms Saad: 0 off · 1 VSISA position open · 2 VSISA traded within InpHybWinMin · 3 VSISA setup seen within InpHybWinMin (same direction)
input int    InpHybSaadAct  = 0;      // InpHybSaadAct — 0 skip unconfirmed Saad trades · 1 take all, confirmed ones x InpHybConfMult lots
input double InpHybConfMult = 2.0;    // InpHybConfMult — lot multiplier for confirmed Saad trades (InpHybSaadAct 1)
input int    InpHybVsGate   = 0;      // InpHybVsGate — Saad confirms VSISA: 0 the probe rule above · 2 Saad traded within InpHybWinMin · 3 Saad setup seen within InpHybWinMin
input int    InpHybWinMin   = 240;    // InpHybWinMin — confirmation window, minutes
input int    InpHybSaadMature = 0;    // InpHybSaadMature — gate 1 only: the open VSISA probe must be 0 just open · 1 in profit >= InpHybSaadMatR x its initial risk · 2 stop at/after breakeven
input double InpHybSaadMatR = 0.5;    // InpHybSaadMatR''')

BLEND = r'''// --- blend: who confirmed whom (engine 0 = Saad, 1 = VSISA) ---
datetime g_hRawT[2] = {0, 0}; int g_hRawS[2] = {0, 0};   // last raw setup seen
datetime g_hOpnT[2] = {0, 0}; int g_hOpnS[2] = {0, 0};   // last trade opened
ulong g_hMaxId = 0; ulong g_hTagId[]; int g_hTagF[], g_hTagE[]; double g_hTagSl0[]; int g_hTagN = 0;
int g_hSaadBlocked = 0, g_hSaadAllowed = 0, g_hSaadBoosted = 0;
void HybRaw(int eng, int side) { g_hRawT[eng] = TimeCurrent(); g_hRawS[eng] = side; }
bool HybOpenSide(int eng, int side)
{
   long mg = eng == 0 ? S_InpMagicNumber : InpMagicNumber;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetInteger(POSITION_MAGIC) != mg || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if ((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1) == side) return true;
   }
   return false;
}
bool HybConf(int eng, int side, int def, int winMin)
{
   datetime now = TimeCurrent();
   if (def == 1) return HybOpenSide(eng, side);
   if (def == 2) return g_hOpnS[eng] == side && now - g_hOpnT[eng] <= winMin * 60;
   if (def == 3) return g_hRawS[eng] == side && now - g_hRawT[eng] <= winMin * 60;
   return false;
}
// the mirror of the original hybrid: a same-direction VSISA probe that is mature
bool HybVsMature(int side)
{
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      int sd = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      if (sd != side) continue;
      double en = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), sl0 = 0;
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      for (int k = g_hTagN - 1; k >= 0; k--) if (g_hTagId[k] == id) { sl0 = g_hTagSl0[k]; break; }
      double risk = sl0 > 0 ? MathAbs(en - sl0) : (sl > 0 ? MathAbs(en - sl) : 0);
      double px = sd > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if (InpHybSaadMature == 1 && risk > 0 && sd * (px - en) >= InpHybSaadMatR * risk) return true;
      if (InpHybSaadMature == 2 && sl > 0 && (sd > 0 ? sl >= en : sl <= en)) return true;
   }
   return false;
}
bool HybSaadOk(int side)
{
   if (InpHybSaadGate <= 0 || InpHybSaadAct == 1) return true;
   if (InpHybSaadGate == 1 && InpHybSaadMature > 0) { if (HybVsMature(side)) { g_hSaadAllowed++; return true; } g_hSaadBlocked++; return false; }
   if (HybConf(1, side, InpHybSaadGate, InpHybWinMin)) { g_hSaadAllowed++; return true; }
   g_hSaadBlocked++; return false;
}
double HybSaadLots(int side, double lots)
{
   if (InpHybSaadGate <= 0 || InpHybSaadAct != 1 || !HybConf(1, side, InpHybSaadGate, InpHybWinMin)) return lots;
   g_hSaadBoosted++;
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), x = lots * InpHybConfMult;
   return st > 0 ? MathFloor(x / st + 1e-9) * st : x;
}
// tag every new position at open: bit0 other open same dir · bit1/2 other traded same dir 60/240 min ·
// bit3/4 other saw a setup same dir 60/240 min · bit5 other open OPPOSITE dir · bit6 other's last setup (240 min) was OPPOSITE
void HybTrack()
{
   for (int i = 0; i < PositionsTotal(); i++) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if (id <= g_hMaxId) continue;
      long mg = PositionGetInteger(POSITION_MAGIC);
      int eng = mg == S_InpMagicNumber ? 0 : (mg == InpMagicNumber ? 1 : -1);
      if (eng < 0) continue;
      int side = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1, o = 1 - eng, f = 0;
      if (HybOpenSide(o, side)) f |= 1;
      if (HybConf(o, side, 2, 60)) f |= 2;
      if (HybConf(o, side, 2, 240)) f |= 4;
      if (HybConf(o, side, 3, 60)) f |= 8;
      if (HybConf(o, side, 3, 240)) f |= 16;
      if (HybOpenSide(o, -side)) f |= 32;
      if (HybConf(o, -side, 3, 240)) f |= 64;
      g_hTagN++; ArrayResize(g_hTagId, g_hTagN, 512); ArrayResize(g_hTagF, g_hTagN, 512); ArrayResize(g_hTagE, g_hTagN, 512); ArrayResize(g_hTagSl0, g_hTagN, 512); g_hTagSl0[g_hTagN - 1] = PositionGetDouble(POSITION_SL);
      g_hTagId[g_hTagN - 1] = id; g_hTagF[g_hTagN - 1] = f; g_hTagE[g_hTagN - 1] = eng;
      g_hOpnT[eng] = TimeCurrent(); g_hOpnS[eng] = side;
   }
   for (int i = 0; i < PositionsTotal(); i++) {
      ulong t = PositionGetTicket(i);
      if (t > 0) { ulong id = (ulong)PositionGetInteger(POSITION_IDENTIFIER); if (id > g_hMaxId) g_hMaxId = id; }
   }
}
void HybTagStats()
{
   if (!HistorySelect(0, TimeCurrent() + 86400)) return;
   double net[]; ArrayResize(net, g_hTagN); ArrayInitialize(net, 0);
   double vin[]; ArrayResize(vin, g_hTagN); ArrayInitialize(vin, 0);
   double com[]; ArrayResize(com, g_hTagN); ArrayInitialize(com, 0);
   for (int i = 0; i < HistoryDealsTotal(); i++) {
      ulong d = HistoryDealGetTicket(i); long tp = HistoryDealGetInteger(d, DEAL_TYPE);
      if (tp != DEAL_TYPE_BUY && tp != DEAL_TYPE_SELL) continue;
      ulong ps = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID); int k = -1;
      for (int j = g_hTagN - 1; j >= 0; j--) if (g_hTagId[j] == ps) { k = j; break; }
      if (k < 0) continue;
      if (HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) vin[k] += HistoryDealGetDouble(d, DEAL_VOLUME);
      com[k] += HistoryDealGetDouble(d, DEAL_COMMISSION);
      net[k] += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
   }
   string en[2] = {"SAAD", "VSISA"};
   string bn[9] = {"all", "other OPEN same dir", "other TRADED same dir 60m", "other TRADED same dir 240m",
                   "other SETUP same dir 60m", "other SETUP same dir 240m", "other OPEN opposite dir",
                   "other last SETUP opposite 240m", "no same-dir confirmation (bits0-4 none)"};
   for (int g = 0; g < 2; g++)
      for (int b = 0; b < 9; b++) {
         int c = 0, w = 0; double tot = 0;
         for (int j = 0; j < g_hTagN; j++) {
            if (g_hTagE[j] != g) continue;
            bool in = b == 0 ? true : (b == 8 ? (g_hTagF[j] & 31) == 0 : ((g_hTagF[j] >> (b - 1)) & 1) == 1);
            if (!in) continue;
            double x = net[j] - (com[j] == 0 ? 4.0 * vin[j] : 0); c++; tot += x; if (x > 0) w++;
         }
         PrintFormat("[HYBRID-TAG] %s | %s | trades %d wins %d WR %.1f%% net %.2f", en[g], bn[b], c, w, c > 0 ? 100.0 * w / c : 0, tot);
      }
   PrintFormat("[HYBRID-TAG] Saad gate: allowed %d blocked %d boosted %d", g_hSaadAllowed, g_hSaadBlocked, g_hSaadBoosted);
}
'''
rep('void HybStats()', BLEND + 'void HybStats()')
# VSISA gate on Saad's direction
rep('bool HybProbeOk(int side)\n{\n', 'bool HybProbeOk(int side)\n{\n   if (InpHybVsGate >= 2) return HybConf(0, side, InpHybVsGate, InpHybWinMin);\n')
# raw VSISA setup = every call of Fire, before any gate or filter
rep('void Fire(int side, double sl_level, string why) {\n', 'void Fire(int side, double sl_level, string why) {\n   HybRaw(1, side);\n')
rep('   if (InpHybSaad) S_OnTick();\n', '   HybTrack();\n   if (InpHybSaad) S_OnTick();\n   HybTrack();\n')
rep('   HybStats();\n', '   HybStats();\n   HybTagStats();\n')
p.write_text(s, encoding='utf-8')
print('blend added')
