"""make_view_ea.py - Zee 2026-10-20: "i want to build a tradingview's copy web app which can show the entire year's candles and my MT5 EA's code
applied to the candles" -> "yes, do your best".

Builds mt5/Saad_strategy_15min_view.mq5 = Saad_strategy_15min (v1.27) VERBATIM + an export of every closed candle (the EA's own EMAs, ADX, ATR)
and every decision (setup, skip + reason, entry, exit + reason, stand-aside ghost start / end) to Common\\Files\\saadview_<tag>_bars.csv /
_events.csv. Nothing that trades is changed: the web chart (monitor/saad_view) shows MT5's real trades, never a re-implementation.
Re-run after any change to Saad_strategy_15min.mq5:   py monitor/saad_view/make_view_ea.py"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = ROOT / "mt5" / "Saad_strategy_15min.mq5"
dst = ROOT / "mt5" / "Saad_strategy_15min_view.mq5"
t = src.read_text(encoding="utf-8")
ver = re.search(r'#property version\s+"([^"]+)"', t).group(1)


def rep(o, n):
    global t
    assert t.count(o) == 1, (o[:90], t.count(o))
    t = t.replace(o, n)


rep('#define EA_COMMENT "Saad15 v', '''// VIEWER copy (Zee 2026-10-20: "a tradingview's copy web app which can show the entire year's candles and my MT5 EA's code applied to the
//   candles"): Saad_strategy_15min VERBATIM + an export of every candle and decision for the web chart (monitor/saad_view). Built by
//   monitor/saad_view/make_view_ea.py - do not edit by hand. TEST - run it in the Strategy Tester, never attach to an account.
#define EA_COMMENT "Saad15 view v''')
rep("input int    InpMagicNumber = 88302;", "input int    InpMagicNumber = 88316;")
i = t.index("input int    InpExitMode    = 1;")
j = t.index("\n", i) + 1
t = t[:j] + '''//--- VIEWER: the export for the web chart (trading is untouched)
input bool   InpExport      = true;    // InpExport - write every closed candle and every decision to Common\\Files\\saadview_<InpExportTag>_bars.csv / _events.csv
input string InpExportTag   = "view";  // InpExportTag - the run's name in those file names
input bool   InpExportM1    = false;   // InpExportM1 - also every closed 1-minute candle with its spread (the fast optimizer's data, ~350k lines a year)
''' + t[j:]
rep("int      hFast = INVALID_HANDLE,", "int      hAdxX = INVALID_HANDLE;   // VIEWER: ADX for the export (the EA's own formula: MT5's iADX on its candles)\nint      hFast = INVALID_HANDLE,")
rep("   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);", "   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);\n   if (InpExport) hAdxX = iADX(_Symbol, PERIOD_CURRENT, InpAdxPeriod);")
rep("string Px(double v) { return v == 0 ? \"\" : DoubleToString(v, _Digits); }", r'''string Px(double v) { return v == 0 ? "" : DoubleToString(v, _Digits); }
//--- VIEWER: the export (one line per closed candle; one line per decision). Tab-separated, server time.
int g_exB = INVALID_HANDLE, g_exE = INVALID_HANDLE;
void ExOpen()
{
   if (!InpExport || g_exB != INVALID_HANDLE) return;
   g_exB = FileOpen(StringFormat("saadview_%s_bars.csv", InpExportTag), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   g_exE = FileOpen(StringFormat("saadview_%s_events.csv", InpExportTag), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if (g_exB != INVALID_HANDLE) FileWriteString(g_exB, "time\topen\thigh\tlow\tclose\tema_fast\tema_slow\tadx\tatr\r\n");
   if (g_exE != INVALID_HANDLE) FileWriteString(g_exE, "type\ttime\tside\tprice\tsl\tv1\tv2\tref\tnum\ttext\r\n");
}
void ExBar()
{
   if (!InpExport) return;
   ExOpen();
   if (g_exB == INVALID_HANDLE) return;
   double a[1]; double adx = hAdxX != INVALID_HANDLE && CopyBuffer(hAdxX, 0, 1, 1, a) == 1 ? a[0] : 0;
   FileWriteString(g_exB, StringFormat("%s\t%s\t%s\t%s\t%s\t%.3f\t%.3f\t%.2f\t%.3f\r\n", TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_DATE | TIME_MINUTES),
                   Px(iOpen(_Symbol, PERIOD_CURRENT, 1)), Px(iHigh(_Symbol, PERIOD_CURRENT, 1)), Px(iLow(_Symbol, PERIOD_CURRENT, 1)), Px(iClose(_Symbol, PERIOD_CURRENT, 1)),
                   Buf(hFast, 1), Buf(hSlow, 1), adx, Buf(hAtr, 1)));
}
void EV(string type, datetime tm, int side, double price, double sl, double v1, double v2, datetime ref, int num, string txt)
{
   if (!InpExport) return;
   ExOpen();
   if (g_exE == INVALID_HANDLE) return;
   StringReplace(txt, "\t", " "); StringReplace(txt, "\r", " "); StringReplace(txt, "\n", " ");
   FileWriteString(g_exE, StringFormat("%s\t%s\t%d\t%s\t%s\t%.4f\t%.4f\t%s\t%d\t%s\r\n", type, TimeToString(tm, TIME_DATE | TIME_SECONDS), side, Px(price), Px(sl),
                   v1, v2, ref > 0 ? TimeToString(ref, TIME_DATE | TIME_MINUTES) : "", num, txt));
}
int g_exM = INVALID_HANDLE;
datetime g_exMLast = 0;
int g_exMSpr = 0;
// every closed 1-minute candle (bid OHLC) + the spread at its first tick and the bar's own spread (points)
void ExM1()
{
   if (!InpExport || !InpExportM1) return;
   datetime m = iTime(_Symbol, PERIOD_M1, 0);
   if (m == g_exMLast) return;
   if (g_exM == INVALID_HANDLE) {
      g_exM = FileOpen(StringFormat("saadview_%s_m1.csv", InpExportTag), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if (g_exM != INVALID_HANDLE) FileWriteString(g_exM, "time\topen\thigh\tlow\tclose\tspread_open\tspread_bar\r\n");
   }
   if (g_exMLast > 0 && g_exM != INVALID_HANDLE)
      FileWriteString(g_exM, StringFormat("%s\t%s\t%s\t%s\t%s\t%d\t%d\r\n", TimeToString(iTime(_Symbol, PERIOD_M1, 1), TIME_DATE | TIME_MINUTES),
                      Px(iOpen(_Symbol, PERIOD_M1, 1)), Px(iHigh(_Symbol, PERIOD_M1, 1)), Px(iLow(_Symbol, PERIOD_M1, 1)), Px(iClose(_Symbol, PERIOD_M1, 1)),
                      g_exMSpr, (int)iSpread(_Symbol, PERIOD_M1, 1)));
   g_exMLast = m;
   g_exMSpr = (int)MathRound((SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point);
}
void ExClose()
{
   if (g_exB != INVALID_HANDLE) { FileClose(g_exB); g_exB = INVALID_HANDLE; }
   if (g_exE != INVALID_HANDLE) { FileClose(g_exE); g_exE = INVALID_HANDLE; }
   if (g_exM != INVALID_HANDLE) { FileClose(g_exM); g_exM = INVALID_HANDLE; }
}''')
rep("void OnTick()\n{\n", "void OnTick()\n{\n   ExM1();\n")
# hooks
rep("void OnDeinit(const int reason)\n{\n", "void OnDeinit(const int reason)\n{\n   ExClose();\n")
rep("      g_lastBar = bar;\n", "      g_lastBar = bar;\n      ExBar();\n")
rep('   Log("SKIP: " + why + " | " + g_pDesc);', '   Log("SKIP: " + why + " | " + g_pDesc);\n   EV("skip", TimeCurrent(), side, g_pHigh, g_pLow, 0, 0, g_pTime, 0, why);')
rep('   Log(StringFormat("SETUP %s | candle %s H %s L %s', '''   EV("setup", g_pTime, side, h, l, side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip(), g_kind, g_pTime, 0, g_pDesc);
   Log(StringFormat("SETUP %s | candle %s H %s L %s''')
rep("g_gTime = TimeCurrent(); g_ghosts++;", 'g_gTime = TimeCurrent(); g_ghosts++;\n      EV("ghost", TimeCurrent(), side, en, sl, nxE, g_ck, g_pTime, 0, g_pDesc);')
rep("   g_entries++;\n", '   g_entries++;\n   EV("entry", p.entryTime, side, p.entry, p.sl0, nxE, g_ck, g_pTime, p.num, p.tp1 + " | " + p.setup);\n')
rep("   if (!(Drawing() || LogOn() || InpLogCsv) || !HistorySelectByPosition(p.ticket)) return;",
    "   if (!(Drawing() || LogOn() || InpLogCsv || InpExport) || !HistorySelectByPosition(p.ticket)) return;")
rep('   Log(StringFormat("EXIT #%d %s %s @ %s | entry %s', '   EV("exit", t, p.side, px, p.sl0, pnl, swp, p.entryTime, p.num, why);\n   Log(StringFormat("EXIT #%d %s %s @ %s | entry %s')
# the ghost's end, with the reason and the price a real trade would have closed at
rep('''   bool end = s > 0 ? bid <= g_gSl : ask >= g_gSl;
   if (!end && g_gNxE > 0) end = s > 0 ? bid >= Ema(g_gNxE, 0) : ask <= Ema(g_gNxE, 0);''', '''   bool end = s > 0 ? bid <= g_gSl : ask >= g_gSl;
   string gwhy = "stop loss";
   if (!end && g_gNxE > 0) { end = s > 0 ? bid >= Ema(g_gNxE, 0) : ask <= Ema(g_gNxE, 0); gwhy = "next EMA touched"; }''')
rep('''   if (!end && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) end = s > 0 ? bid < g_gEntry : ask > g_gEntry;
   if (end) g_gSide = 0;''', '''   if (!end && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) { end = s > 0 ? bid < g_gEntry : ask > g_gEntry; gwhy = "day close, in loss"; }
   if (end) { EV("ghost_end", TimeCurrent(), s, s > 0 ? bid : ask, g_gEntry, 0, 0, g_gTime, 0, gwhy); g_gSide = 0; }''')
rep("   if (ce > 0 && (g_gSide > 0 ? c1 < Ema(ce, 1) : c1 > Ema(ce, 1))) g_gSide = 0;",
    '''   if (ce > 0 && (g_gSide > 0 ? c1 < Ema(ce, 1) : c1 > Ema(ce, 1))) {
      EV("ghost_end", TimeCurrent(), g_gSide, g_gSide > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK), g_gEntry, 0, 0, g_gTime, 0,
         StringFormat("closed back across the %d EMA", ce == 9 ? InpEmaFast : InpEmaSlow));
      g_gSide = 0;
   }''')
dst.write_text(t, encoding="utf-8")
print(f"written {dst} (from Saad_strategy_15min v{ver}), {len(t.splitlines())} lines")
