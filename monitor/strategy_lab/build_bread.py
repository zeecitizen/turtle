"""bread_winner (Zee 2026-10-14: "I attach an EA. It makes $15. I close it. That's all i want from a day ... I just
want to eat bread per day. which costs around $10 per day in my city. As long as i make $10 with a 100% winrate. I
am happy. You can change to as many settings as you want . Tune to any time frame any candle any EA .. call this 1
EA the bread_winner EA.")

Trinity's three engines (Saad / VSISA / UHV Diamond, timeframes as inputs) + a DAY MANAGER:
  * today's P&L = closed deals since the server day began + open positions (all three magics; $4/lot when the
    broker books no commission)
  * >= InpBwTarget  -> close everything, no new trades until tomorrow ("bread bought")
  * <= -InpBwMaxLoss (0 = off) -> close everything, stop for the day
  * InpBwFlatHour (server hour, 24 = off) -> close everything and stop; every day starts flat
  * InpBwFromHour / InpBwToHour -> new entries only inside this server-hour window
Run after build_trinity.py + patch_trinity_filter.py (it copies their output)."""
import re
from pathlib import Path

M = Path(r'C:\Users\zeesh\turtle\mt5')
VER = "1.00"
C = f"Bread v{VER}"


def rep(s, a, b):
    assert s.count(a) == 1, (s.count(a), a[:80])
    return s.replace(a, b)


def setdef(txt, name, val):
    pat = re.compile(rf'^(input\s+\w+\s+{name}\s*=\s*)([^;]+);', re.M)
    assert len(pat.findall(txt)) == 1, name
    return pat.sub(lambda m: m.group(1) + val + ';', txt)


sa = (M / 'TriSaad.mqh').read_text(encoding='utf-8')
sa = setdef(sa, 'S_InpMagicNumber', '88380')
sa = re.sub(r'#define S_EA_COMMENT "[^"]*"', f'#define S_EA_COMMENT "{C} SAAD"', sa)
sa = rep(sa, 'void S_DoEntry(int side, double sl)\n{\n', 'void S_DoEntry(int side, double sl)\n{\n   if (!BwOk()) return;\n')
vs = (M / 'TriVsisa.mqh').read_text(encoding='utf-8')
vs = setdef(vs, 'V_InpMagicNumber', '88381')
vs = vs.replace('"Tri1m v1.00 VSISA %d_%d"', f'"{C} VSISA %d_%d"')
vs = rep(vs, '   TriVsRaw(side);\n', '   TriVsRaw(side);\n   if (!BwOk()) return;\n')
di = (M / 'TriDia.mqh').read_text(encoding='utf-8')
di = setdef(di, 'D_InpMagicNumber', '88382')
di = di.replace('"Tri1m v1.00 DIA %s D%d"', f'"{C} DIA %s D%d"')
for f, t in (('bw_saad.mqh', sa), ('bw_vsisa.mqh', vs), ('bw_dia.mqh', di)):
    (M / f).write_text(t.replace('as an engine for Trinity_1min', 'as an engine for bread_winner'), encoding='utf-8')

h = (M / 'Trinity_1min.mq5').read_text(encoding='utf-8')
h = rep(h, '#include "TriSaad.mqh"\n#include "TriVsisa.mqh"\n#include "TriDia.mqh"',
        '#include "bw_saad.mqh"\n#include "bw_vsisa.mqh"\n#include "bw_dia.mqh"')
h = rep(h, 'bool TriDiaOk(int side, int dia)\n{\n', 'bool TriDiaOk(int side, int dia)\n{\n   if (!BwOk()) return false;\n')
DAY = r'''
input group "=== bread_winner: the day manager ==="
input double InpBwTarget   = 15.0;   // InpBwTarget — today's P&L reaches this $ -> close everything, stop until tomorrow
input double InpBwMaxLoss  = 0.0;    // InpBwMaxLoss — today's P&L falls to -this $ -> close everything, stop (0 = off)
input int    InpBwFlatHour = 24;     // InpBwFlatHour — server hour: close everything and stop for the day (24 = off)
input int    InpBwFromHour = 0;      // InpBwFromHour — new entries only from this server hour...
input int    InpBwToHour   = 24;     // InpBwToHour — ...until this one (exclusive)
input bool   InpBwCarry    = false;  // InpBwCarry — true: a day that ends below target CARRIES OVER; the EA keeps going until everything since the cycle began reaches InpBwTarget ("attach, it makes $15, close")

datetime g_bwDay = 0, g_bwCal = 0; bool g_bwDone = false, g_bwCycDone = false; datetime g_bwLastCalc = 0; double g_bwPnl = 0;
int g_bwHit = 0, g_bwStop = 0, g_bwFlat = 0;
double g_bwClosed = 0; int g_bwPosN = -1; double g_bwPosV = -1; ulong g_bwPosSig = 0; datetime g_bwClosedFrom = -1;
datetime g_bwCycStart = 0; double g_bwCycMin = 0, g_bwWorstDip = 0; int g_bwLongest = 0;   // cycle stats (carry mode)
bool BwMine(long mg) { return mg == S_InpMagicNumber || mg == V_InpMagicNumber || mg == D_InpMagicNumber; }
// P&L since the accounting window began: closed deals (re-read only when our positions change) + open positions
double BwDayPnl()
{
   int n = 0; double v = 0, flo = 0; ulong sig = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !BwMine(PositionGetInteger(POSITION_MAGIC))) continue;
      n++; sig += t; v += PositionGetDouble(POSITION_VOLUME);
      flo += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) - 4.0 * PositionGetDouble(POSITION_VOLUME);
   }
   if (n != g_bwPosN || sig != g_bwPosSig || MathAbs(v - g_bwPosV) > 1e-9 || g_bwClosedFrom != g_bwDay) {
      g_bwPosN = n; g_bwPosSig = sig; g_bwPosV = v; g_bwClosedFrom = g_bwDay; g_bwClosed = 0;
      if (HistorySelect(g_bwDay, TimeCurrent() + 60))
         for (int i = 0; i < HistoryDealsTotal(); i++) {
            ulong d = HistoryDealGetTicket(i);
            if (!BwMine(HistoryDealGetInteger(d, DEAL_MAGIC))) continue;
            long e = HistoryDealGetInteger(d, DEAL_ENTRY);
            double c = HistoryDealGetDouble(d, DEAL_COMMISSION);
            g_bwClosed += HistoryDealGetDouble(d, DEAL_PROFIT) + c + HistoryDealGetDouble(d, DEAL_SWAP);
            if (c == 0 && e != DEAL_ENTRY_IN) g_bwClosed -= 4.0 * HistoryDealGetDouble(d, DEAL_VOLUME);   // tester books no commission
         }
   }
   return g_bwClosed + flo;
}
void BwCloseAll()
{
   CTrade tr;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t > 0 && BwMine(PositionGetInteger(POSITION_MAGIC))) tr.PositionClose(t);
   }
}
void BwTick()
{
   datetime now = TimeCurrent();
   datetime day = now - now % 86400;
   if (day != g_bwCal) {                            // a new server day
      g_bwCal = day;
      if (!InpBwCarry || g_bwCycDone || g_bwDay == 0) { g_bwDay = day; g_bwCycStart = day; g_bwCycMin = 0; }   // carry: keep the old window until its target is met
      g_bwDone = false; g_bwCycDone = false;
   }
   if (g_bwDone) { BwCloseAll(); return; }          // a position opened between checks: close it too
   MqlDateTime dt; TimeToStruct(now, dt);
   if (InpBwFlatHour < 24 && dt.hour >= InpBwFlatHour) { BwCloseAll(); g_bwDone = true; g_bwFlat++; return; }
   if (now - g_bwLastCalc < 1) return;              // once a second is enough
   g_bwLastCalc = now;
   g_bwPnl = BwDayPnl();
   if (g_bwPnl < g_bwCycMin) { g_bwCycMin = g_bwPnl; if (g_bwCycMin < g_bwWorstDip) g_bwWorstDip = g_bwCycMin; }
   if (g_bwPnl >= InpBwTarget) {
      BwCloseAll(); g_bwDone = true; g_bwCycDone = true; g_bwHit++;
      int len = (int)((day - g_bwCycStart) / 86400) + 1;
      if (len > g_bwLongest) g_bwLongest = len;
      return;
   }
   if (InpBwMaxLoss > 0 && g_bwPnl <= -InpBwMaxLoss) { BwCloseAll(); g_bwDone = true; g_bwStop++; }
}
bool BwOk()
{
   if (g_bwDone) return false;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (InpBwToHour > InpBwFromHour && (dt.hour < InpBwFromHour || dt.hour >= InpBwToHour)) return false;
   return true;
}
'''
h = rep(h, '\ninput group "=== Diamond filters', DAY + '\ninput group "=== Diamond filters')
h = rep(h, 'void OnTick()\n{\n', 'void OnTick()\n{\n   BwTick();\n')
h = rep(h, '   TriStats();\n', '   TriStats();\n   PrintFormat("[BREAD] target days %d, loss-limit days %d, flat-hour days %d | carry %s: longest cycle %d days, deepest dip inside a cycle %.2f",'
                                ' g_bwHit, g_bwStop, g_bwFlat, InpBwCarry ? "on" : "off", g_bwLongest, g_bwWorstDip);\n')
h = h.replace('[TRINITY] v1.00', f'[BREAD] bread_winner v{VER}').replace('"[TRINITY-STATS]', '"[TRINITY-STATS]')
h = re.sub(r'^//\+-+\+\n(//\|.*\n)+//\+-+\+\n', '', h, count=1)
h = (f'//+------------------------------------------------------------------+\n'
     f'//| bread_winner.mq5 v{VER} (2026-10-14). Attach on XAUUSD (any chart).   |\n'
     '//| Saad + VSISA + UHV Diamond engines; a day manager closes everything |\n'
     '//| and stops for the day once today\'s P&L reaches InpBwTarget.        |\n'
     '//| Needs bw_saad.mqh, bw_vsisa.mqh, bw_dia.mqh + 4 Vsisa*.mqh.         |\n'
     '//| GENERATED by monitor/strategy_lab/build_bread.py.                    |\n'
     '//+------------------------------------------------------------------+\n') + h
import sys
NAME = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'bread_winner'
(M / f'{NAME}.mq5').write_text(h, encoding='utf-8')
print(f'{NAME} built')
