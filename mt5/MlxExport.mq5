//+------------------------------------------------------------------+
//| MlxExport.mq5 - dataset exporter for the triple-barrier ML blueprint (monitor/saad_view/mlx), 2026-11-01            |
//|                                                                                                                    |
//| An EXPERT (the Strategy Tester cannot run scripts); it trades nothing. The features are MlxFeatures.mqh (the same  |
//| code the EA's v1.39 InpMlFilter gate runs), the files go to the terminal's MQL5\Files (in the tester: the agent's  |
//| MQL5\Files, Tester\Agent-...\MQL5\Files) as mlx_features_<symbol><tag>.csv / mlx_bars_<symbol><tag>.csv.          |
//|  InpMode 0: at start, every history bar from InpWarm to the last one followed by InpFwd CLOSED bars: time (unix    |
//|     seconds, server time of the bar's open), the MLX_N features, then H/L/C of the next InpFwd bars                |
//|     (h1,l1,c1 .. h48,l48,c48). For a chart with history; the indicators may still be calculating right after the   |
//|     attach, so it retries every second until they answer.                                                          |
//|  InpMode 1: streaming - at each new M15 bar the just-closed bar's row (time + features) and, in the bars file, the |
//|     bar's own time,O,H,L,C so Python builds the forward matrix itself. Rows are appended; a restart continues.      |
//|  InpMode 2: the mode-0 dump at the END of the run (OnTester / OnDeinit): the tester's way to dump a whole period   |
//|     in one pass (its history before the start date is short). The run itself does nothing else.                    |
//| spread_pts is written as 0 (the spec: the model is trained without it). CSV written in big chunks for speed.       |
//| InpCommon = true writes to Common Files instead: in the tester the agent's MQL5\Files is wiped when the next pass    |
//| starts, so collect the files right after the run or use Common Files.                                              |
//| Tester (rig axi4): Expert=MlxExport Symbol=XAUUSD_BB Period=M15 InpMode=1 (or 2) InpCommon=true FromDate=2023.01.01. |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict

#include "MlxFeatures.mqh"

input int    InpMode = 0;       // InpMode - 0 dump the chart's history at start · 1 stream every closed bar · 2 dump at the end (tester)
input int    InpWarm = 600;     // InpWarm - first bar exported (bars of warm-up before it; never below 480)
input int    InpFwd  = 48;      // InpFwd - forward bars of H/L/C per row (modes 0 / 2)
input string InpTag  = "";      // InpTag - suffix for the file names (mlx_features_<symbol><tag>.csv)
input bool   InpCommon = false; // InpCommon - write to Common Files instead of MQL5\Files (the tester wipes its agent's MQL5\Files at the next pass)

bool     g_done = false;
int      g_hF = INVALID_HANDLE, g_hB = INVALID_HANDLE;
datetime g_last = 0;
int      g_rows = 0, g_digits = 2;

string FnFeatures() { return "mlx_features_" + _Symbol + InpTag + ".csv"; }
string FnBars()     { return "mlx_bars_" + _Symbol + InpTag + ".csv"; }
string Fmt(double v) { return StringFormat("%.8g", v); }
int    Common()      { return InpCommon ? FILE_COMMON : 0; }
string Px(double v)  { return DoubleToString(v, g_digits); }

// one row: time + the features
string Row(datetime t, const double &f[])
{
   string line = IntegerToString((long)t);
   for (int k = 0; k < MLX_N; k++) line += "," + Fmt(f[k]);
   return line;
}

// modes 0 / 2: the whole history in one file. true = done (or given up), false = not ready yet
bool Dump()
{
   if (g_done) return true;
   int warm = MathMax(InpWarm, MLX_MINBACK), fwd = MathMax(InpFwd, 0);
   int bars = Bars(_Symbol, PERIOD_M15), need = warm + fwd + 2;
   if (bars < need) { PrintFormat("[MLX] %d M15 bars, %d needed - waiting", bars, need); return false; }
   MlxSeries S;
   if (!MlxLoad(_Symbol, 0, bars, S)) { PrintFormat("[MLX] indicators still calculating (%d bars) - retrying", bars); return false; }
   int last = S.n - 2 - fwd;                    // the newest bar with fwd CLOSED bars after it (S.n - 1 is the forming bar)
   string fn = FnFeatures();
   int h = FileOpen(fn, FILE_WRITE | FILE_TXT | FILE_ANSI | Common());
   if (h == INVALID_HANDLE) { PrintFormat("[MLX] cannot write %s (error %d)", fn, GetLastError()); g_done = true; return true; }
   string head = "time," + MlxHeader(",");
   for (int q = 1; q <= fwd; q++) head += StringFormat(",h%d,l%d,c%d", q, q, q);
   FileWriteString(h, head + "\r\n");
   string buf = ""; int rows = 0; double f[];
   for (int i = warm; i <= last; i++) {
      if (MlxCompute(S, i, 0, f) != MLX_N) continue;
      string line = Row(S.r[i].time, f);
      for (int q = 1; q <= fwd; q++) line += "," + Px(S.r[i + q].high) + "," + Px(S.r[i + q].low) + "," + Px(S.r[i + q].close);
      buf += line + "\r\n"; rows++;
      if (StringLen(buf) > 262144) { FileWriteString(h, buf); buf = ""; }
   }
   if (buf != "") FileWriteString(h, buf);
   FileClose(h);
   PrintFormat("[MLX] %s: %d rows (bars %d..%d of %d, %s .. %s), %d features + %d forward bars", fn, rows, warm, last, S.n,
               rows > 0 ? TimeToString(S.r[warm].time) : "", rows > 0 ? TimeToString(S.r[last].time) : "", MLX_N, fwd);
   g_done = true;
   return true;
}

// mode 1: the two files, appended
bool OpenStream()
{
   if (g_hF != INVALID_HANDLE) return true;
   g_hF = FileOpen(FnFeatures(), FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | Common());
   g_hB = FileOpen(FnBars(), FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | Common());
   if (g_hF == INVALID_HANDLE || g_hB == INVALID_HANDLE) { PrintFormat("[MLX] cannot open the stream files (error %d)", GetLastError()); return false; }
   if (FileSize(g_hF) == 0) FileWriteString(g_hF, "time," + MlxHeader(",") + "\r\n");
   if (FileSize(g_hB) == 0) FileWriteString(g_hB, "time,open,high,low,close\r\n");
   FileSeek(g_hF, 0, SEEK_END); FileSeek(g_hB, 0, SEEK_END);
   return true;
}

void CloseStream()
{
   if (g_hF != INVALID_HANDLE) { FileClose(g_hF); g_hF = INVALID_HANDLE; }
   if (g_hB != INVALID_HANDLE) { FileClose(g_hB); g_hB = INVALID_HANDLE; }
}

// mode 1: a new M15 bar -> the just-closed bar's features and candle
void Stream()
{
   datetime t0 = iTime(_Symbol, PERIOD_M15, 0);
   if (t0 == 0 || t0 == g_last) return;
   double f[];
   if (MlxFeatures(_Symbol, 1, f, 0) != MLX_N) return;           // not enough bars yet / indicators calculating: again on the next tick
   if (!OpenStream()) { g_last = t0; return; }
   datetime t1 = iTime(_Symbol, PERIOD_M15, 1);
   FileWriteString(g_hF, Row(t1, f) + "\r\n");
   FileWriteString(g_hB, IntegerToString((long)t1) + "," + Px(iOpen(_Symbol, PERIOD_M15, 1)) + "," + Px(iHigh(_Symbol, PERIOD_M15, 1)) + ","
                         + Px(iLow(_Symbol, PERIOD_M15, 1)) + "," + Px(iClose(_Symbol, PERIOD_M15, 1)) + "\r\n");
   FileFlush(g_hF); FileFlush(g_hB);
   g_last = t0; g_rows++;
}

int OnInit()
{
   g_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if (!MlxHandles(_Symbol)) { Print("[MLX] the indicator handles could not be created"); return INIT_FAILED; }
   PrintFormat("[MLX] exporter v1.00 on %s M15: mode %d, warm-up %d, forward %d, %d features -> %s\\%s", _Symbol, InpMode, InpWarm, InpFwd, MLX_N, InpCommon ? "Common Files" : "MQL5\\Files", FnFeatures());
   if (InpMode == 0 && !Dump()) EventSetTimer(1);
   return INIT_SUCCEEDED;
}

void OnTimer() { if (InpMode == 0 && Dump()) EventKillTimer(); }

void OnTick()
{
   if (InpMode == 0) { if (!g_done && Dump()) EventKillTimer(); }
   else if (InpMode == 1) Stream();
}

double OnTester()
{
   if (InpMode == 2) Dump();
   return 0;
}

void OnDeinit(const int reason)
{
   if (InpMode == 2) Dump();
   if (InpMode == 1) PrintFormat("[MLX] streamed %d rows to %s / %s", g_rows, FnFeatures(), FnBars());
   CloseStream();
   MlxRelease();
}
