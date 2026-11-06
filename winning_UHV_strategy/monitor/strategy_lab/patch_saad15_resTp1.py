"""One-off patch: Saad_strategy_15min v1.11 - a LONG whose exit EMA is below / too close to the entry gets
TP1 = the next resistance above the entry (Zee 2026-10-12), instead of no TP + trailing from the entry."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


rep("input int    InpShortTouch  = 1;",
    "input bool   InpLongResTp1  = true;   // InpLongResTp1 — LONG whose exit EMA is below / too close to the entry: TP1 = the next resistance above the entry (false = no TP, trail from entry) [v1.11, Zee]\n"
    "input int    InpShortTouch  = 1;")

rep("datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage;\n",
    "datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage; bool resTp1;\n")
rep('p.tpNext = 0; p.tpStage = 1;', 'p.tpNext = 0; p.tpStage = 1; p.resTp1 = false;', 2)

# entry: no EMA target -> look for the next resistance above the entry
rep('''   } else {
      noTp = Ema(g_pExit, 0) - InpLongTpPips * pip < en + InpMinTpPips * pip;
   }''', '''   } else {
      noTp = Ema(g_pExit, 0) - InpLongTpPips * pip < en + InpMinTpPips * pip;
      if (noTp && InpLongResTp1 && InpLongTouch == 1) {
         double res = LastResistance(en + InpMinTpPips * pip);
         if (res > 0) { tp = res; noTp = false; resTp1 = true; }
      }
   }''')
rep("   double tp = 0;\n   bool noTp = false;\n", "   double tp = 0;\n   bool noTp = false, resTp1 = false;\n")
rep("p.exitE = g_pExit; p.noTp = noTp;", "p.exitE = g_pExit; p.noTp = noTp; p.resTp1 = resTp1;")
# record what TP1 is
rep('''   p.tp1 = side > 0 ? (noTp ? "none (exit EMA below entry) - trailing from entry" : StringFormat("touch of the %d EMA (now %.2f)", g_pExit, Ema(g_pExit, 0)))''',
    '''   p.tp1 = side > 0 ? (noTp ? "none (exit EMA below entry, no resistance above) - trailing from entry"
                            : resTp1 ? StringFormat("next resistance %.2f (the %d EMA is below the entry)", tp, g_pExit)
                            : StringFormat("touch of the %d EMA (now %.2f)", g_pExit, Ema(g_pExit, 0)))''')
# entry label text
rep('''      string tpTxt = side > 0 ? (noTp ? "none - trailing from entry" : StringFormat("candle closes at the %d EMA", g_pExit))''',
    '''      string tpTxt = side > 0 ? (noTp ? "none - trailing from entry" : resTp1 ? StringFormat("%.2f (next resistance)", tp)
                                                                               : StringFormat("touch of the %d EMA", g_pExit))''')
rep('''      } else if (!noTp)
         DText(p.entryTime + PeriodSeconds(), Ema(g_pExit, 0), StringFormat("TP: close at %d EMA", g_pExit), clrLime, 7, ANCHOR_LEFT_LOWER);''',
    '''      } else if (resTp1) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP1: next resistance");
         DText(p.entryTime, tp, StringFormat("TP1 %.2f (next resistance)", tp), clrLime, 7, ANCHOR_LEFT_LOWER);
      } else if (!noTp)
         DText(p.entryTime + PeriodSeconds(), Ema(g_pExit, 0), StringFormat("TP1: touch of the %d EMA", g_pExit), clrLime, 7, ANCHOR_LEFT_LOWER);''')

# tick by tick: TP1 for these longs is the resistance, not the EMA
rep('''         double tgt = Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip();
         if (tgt > g_pos[i].entry && bid >= tgt) { LongTouched(i, bid); continue; }''',
    '''         double tgt = g_pos[i].resTp1 ? g_pos[i].tp : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip();
         if (tgt > g_pos[i].entry && bid >= tgt) { LongTouched(i, bid); continue; }''')
# CTC: measure the way to that resistance
rep('''                      : (g_pos[i].noTp ? 0 : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip());''',
    '''                      : (g_pos[i].noTp ? 0 : g_pos[i].resTp1 ? g_pos[i].tp : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip());''')
# TP1 log/label wording
rep('''   string note = StringFormat("TP1: %d EMA touched -> trail $%.2f below%s", g_pos[i].exitE, InpLongTrailUsd,''',
    '''   string note = StringFormat("TP1: %s -> trail $%.2f below%s", g_pos[i].resTp1 ? "resistance reached" : StringFormat("%d EMA touched", g_pos[i].exitE), InpLongTrailUsd,''')
rep('''   Log(StringFormat("#%d TP1: %d EMA touched @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, g_pos[i].exitE, Px(bid),''',
    '''   Log(StringFormat("#%d TP1: %s @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, g_pos[i].resTp1 ? "resistance " + Px(g_pos[i].tp) + " reached" : StringFormat("%d EMA touched", g_pos[i].exitE), Px(bid),''')

s = s.replace('#property version   "1.10"', '#property version   "1.11"').replace('"[SAAD-15min] v1.10 ', '"[SAAD-15min] v1.11 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
