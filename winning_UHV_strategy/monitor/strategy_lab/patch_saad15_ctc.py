"""One-off patch: Saad_strategy_15min v1.02 - CTC breakeven at 75% of the way to the TP."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:90])
    s = s.replace(a, b)


rep("input double InpBeUsd       = 0.0;    // InpBeUsd — stop to entry once price moved this $ (0 = off)\n",
    "input double InpBeUsd       = 0.0;    // InpBeUsd — stop to entry once price moved this $ (0 = off)\n"
    "input double InpBeTpPct     = 0.75;   // InpBeTpPct — CTC: stop to entry once price covered this share of the way to the TP (0 = off) [v1.02, Zee]\n")

# tick by tick, before the TP: CTC breakeven
rep("      if (InpFixTpPips > 0) continue;\n      if (g_pos[i].ride) continue;",
    '''      if (InpBeTpPct > 0 && !g_pos[i].ride && PositionSelectByTicket(g_pos[i].ticket)) {
         // the TP this trade is heading for: the support (SHORT), the exit EMA now (LONG), or a fixed TP
         double tpRef = g_pos[i].side < 0 || InpFixTpPips > 0 ? g_pos[i].tp
                      : (g_pos[i].noTp ? 0 : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip());
         double dist = g_pos[i].side > 0 ? tpRef - g_pos[i].entry : g_pos[i].entry - tpRef;
         double cur = PositionGetDouble(POSITION_SL);
         bool atEntry = g_pos[i].side > 0 ? cur >= g_pos[i].entry : (cur > 0 && cur <= g_pos[i].entry);
         if (tpRef > 0 && dist > 0 && !atEntry) {
            double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
            if (moved >= InpBeTpPct * dist && ModifySl(g_pos[i].ticket, g_pos[i].entry)) {
               g_ctc++;
               SlMoved(i, g_pos[i].entry, StringFormat("CTC: %d%% of TP -> SL to entry", (int)MathRound(InpBeTpPct * 100)));
            }
         }
      }
      if (InpFixTpPips > 0) continue;
      if (g_pos[i].ride) continue;''')

# counter
rep("int g_setups = 0,", "int g_ctc = 0;\nint g_setups = 0,")
rep('PrintFormat("[SAAD] setups %d,', 'PrintFormat("[SAAD] CTC breakevens %d", g_ctc);\n   PrintFormat("[SAAD] setups %d,')

# exit label: a stop at the entry is a breakeven
rep('''   if (reason == DEAL_REASON_SL) why = (p.ride || (p.side > 0 ? p.slNow > p.entry : p.slNow < p.entry)) ? "trailing stop" : "stop loss";''',
    '''   if (reason == DEAL_REASON_SL)
      why = MathAbs(p.slNow - p.entry) < _Point ? "breakeven (CTC)"
          : (p.ride || (p.side > 0 ? p.slNow > p.entry : p.slNow < p.entry)) ? "trailing stop" : "stop loss";''')

s = s.replace('#property version   "1.01"', '#property version   "1.02"').replace('"[SAAD-15min] v1.01 ', '"[SAAD-15min] v1.02 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
