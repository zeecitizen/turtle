"""Build mt5/Saad_guard.mq5 = Saad_mini (v1.15) + three loss-cutting exits/filters (all off by default):
- InpMinRR: skip a trade whose TP1 is closer than this x the risk
- InpFailBars / InpFailLossPct: close a trade still losing after N closed candles, before CTC/TP1
- InpInvalid: close when a candle closes back through the setup candle (1 = far side, 2 = middle) before CTC/TP1"""
src = r'C:\Users\zeesh\turtle\mt5\Saad_mini.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\Saad_guard.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("input int    InpHtfMin      = 0;",
    "input double InpMinRR       = 0;      // InpMinRR — skip a trade whose TP1 is closer than this x its risk (0 = off)\n"
    "input int    InpFailBars    = 0;      // InpFailBars — close a trade still in loss after this many closed candles, if CTC/TP1 not reached (0 = off)\n"
    "input int    InpInvalid     = 0;      // InpInvalid — before CTC/TP1, close when a candle closes back through the setup candle: 0 off · 1 its far side · 2 its middle\n"
    "input int    InpHtfMin      = 0;")
rep("int num; double slNow; datetime slFrom; string why; };",
    "int num; double slNow; datetime slFrom; string why; double setHi; double setLo; };")
# remember the setup candle on every new position (both creation paths)
rep("p.tpNext = 0; p.tpStage = 1; p.setup = \"\";", "p.tpNext = 0; p.tpStage = 1; p.setHi = g_pHigh; p.setLo = g_pLow; p.setup = \"\";")
s = s.replace("p.tpNext = 0; p.tpStage = 1; p.resTp1 = false;", "p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.setHi = 0; p.setLo = 0;")

# min reward:risk at entry
rep("   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;",
    """   if (InpMinRR > 0) {
      double riskD = MathAbs(en - sl);
      double tpD = side < 0 ? en - tp : (noTp ? 0 : (resTp1 ? tp - en : Ema(g_pExit, 0) - InpLongTpPips * pip - en));
      if (riskD <= 0 || tpD < InpMinRR * riskD) { g_filtered++; DSkip(side, StringFormat("TP1 only %.2f for %.2f risk (R:R %.2f < %.2f)", tpD, riskD, riskD > 0 ? tpD / riskD : 0, InpMinRR)); return; }
   }
   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;""")

# failure / invalidation exits at candle close (before CTC / TP1)
rep("      if (g_pos[i].usdTrail) continue;              // LONG after the touch: trailed tick by tick",
    """      if (!g_pos[i].ride && !g_pos[i].usdTrail && (InpFailBars > 0 || InpInvalid > 0)) {
         bool atEntry = g_pos[i].side > 0 ? sl >= g_pos[i].entry : (sl > 0 && sl <= g_pos[i].entry);
         if (!atEntry) {
            int bars = (int)((iTime(_Symbol, PERIOD_CURRENT, 0) - g_pos[i].entryTime) / PeriodSeconds());
            bool losing = g_pos[i].side > 0 ? c1 < g_pos[i].entry : c1 > g_pos[i].entry;
            double mid = (g_pos[i].setHi + g_pos[i].setLo) / 2;
            bool broke = InpInvalid > 0 && g_pos[i].setHi > 0 &&
                         (g_pos[i].side > 0 ? c1 < (InpInvalid == 1 ? g_pos[i].setLo : mid) : c1 > (InpInvalid == 1 ? g_pos[i].setHi : mid));
            if ((InpFailBars > 0 && bars >= InpFailBars && losing) || broke) {
               g_pos[i].why = broke ? "setup candle broken" : StringFormat("still losing after %d candles", bars);
               trade.PositionClose(t);
               continue;
            }
         }
      }
      if (g_pos[i].usdTrail) continue;              // LONG after the touch: trailed tick by tick""")
s = s.replace('#property version   "1.15"', '#property version   "1.16"').replace('"[SAAD-15min] v1.15 ', '"[SAAD-15min] v1.16 ')
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)
