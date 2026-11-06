"""Build mt5/Saad_cut.mq5 = Saad_guard (v1.16 test EA) + two loss-cutters from Zee's 2026-10-13 list (off by default):
- InpHardCutUsd: close a position as soon as its open P&L (incl. swap) reaches -X account $ (tick by tick)
- InpEmaExit: before CTC/TP1, close at the candle close when the candle closes against the trade beyond the 9 EMA
  (LONG: red candle closing below EMA9; SHORT: green candle closing above it)"""
src = r'C:\Users\zeesh\turtle\mt5\Saad_guard.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\Saad_cut.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("input int    InpFailBars    = 0;",
    "input double InpHardCutUsd  = 0;      // InpHardCutUsd — close a position once its open loss reaches this many account $ (0 = off)\n"
    "input bool   InpEmaExit     = false;  // InpEmaExit — before CTC/TP1: close when a candle closes against the trade beyond the 9 EMA\n"
    "input int    InpFailBars    = 0;")
rep("      if (InpMaxBars > 0 && TimeCurrent()",
    """      if (InpHardCutUsd > 0 && PositionSelectByTicket(g_pos[i].ticket) &&
          PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) <= -InpHardCutUsd) {
         g_pos[i].why = StringFormat("hard $ cut %.0f", InpHardCutUsd); trade.PositionClose(g_pos[i].ticket); continue;
      }
      if (InpMaxBars > 0 && TimeCurrent()""")
rep("      if (!g_pos[i].ride && !g_pos[i].usdTrail && (InpFailBars > 0 || InpInvalid > 0)) {",
    """      if (InpEmaExit && !g_pos[i].ride && !g_pos[i].usdTrail && g_pos[i].entryTime < t1) {
         bool atE = side > 0 ? sl >= g_pos[i].entry : (sl > 0 && sl <= g_pos[i].entry);
         double o1 = iOpen(_Symbol, PERIOD_CURRENT, 1), e9 = Ema(9, 1);
         if (!atE && (side > 0 ? (c1 < e9 && c1 < o1) : (c1 > e9 && c1 > o1))) {
            g_pos[i].why = "closed against the trade beyond the 9 EMA"; trade.PositionClose(t); continue;
         }
      }
      if (!g_pos[i].ride && !g_pos[i].usdTrail && (InpFailBars > 0 || InpInvalid > 0)) {""")
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)

# v2 (2026-10-13): weekend gap guard — the year's biggest loss (-$2,612) was a breakeven short gapped over the weekend
s = open(dst, encoding='utf-8').read()
rep("input double InpHardCutUsd  = 0;",
    "input int    InpFlatMode    = 0;      // InpFlatMode — InpCloseLossMins before the close also shut WINNERS: 0 off · 1 Fridays only (weekend gap) · 2 every day\n"
    "input double InpHardCutUsd  = 0;")
rep("      if (pl < 0) {\n         g_pos[i].why = \"day close, in loss\";",
    """      MqlDateTime dw; TimeToStruct(TimeCurrent(), dw);
      bool flat = InpFlatMode == 2 || (InpFlatMode == 1 && dw.day_of_week == 5);
      if (pl < 0 || flat) {
         g_pos[i].why = pl < 0 ? "day close, in loss" : "day close, flat";""")
open(dst, 'w', encoding='utf-8').write(s)
print('patched v2', dst)
