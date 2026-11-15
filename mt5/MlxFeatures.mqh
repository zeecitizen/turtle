//+------------------------------------------------------------------+
//| MlxFeatures.mqh - the per-bar feature state of monitor/saad_view/mlx/FEATURE_SPEC.md (v1, 2026-11-01)             |
//|                                                                                                                    |
//| Computed from the chart's M15 candles exactly as mlx/features.py computes them from sim.data("m15"): every value    |
//| uses bars <= i only. ATR = iATR(14) (MT5's ATR is an SMA of the true range - the tester's D["atr"]), ADX / +DI / -DI|
//| = iADX(14) (MT5's EMA form - D["adx"]), EMA = iMA(MODE_EMA) (alpha 2/(n+1) seeded on the first close). The first  |
//| 600 bars of history are warm-up and are never exported.                                                            |
//| Column order and names are the contract: the ONNX tensor follows them after the SHAP pruning, and meta.json's      |
//| "kept" names are mapped to columns BY NAME (MlxIndex) so a renumbering can never shift a column in silence.         |
//| Shared by Saad_strategy_15min (the v1.39 InpMlFilter gate) and MlxExport (the dataset exporter): one code path,    |
//| one set of numbers. The spec's table numbers its columns 1-85 while its text says 86: this file has the 85 named   |
//| ones; MLX_N is the truth and both sides align by name.                                                             |
//| Conventions where the spec leaves room - the same as mlx/features.py (its docstring lists them):                   |
//|   * since_hi20 / since_lo20: on equal highs / lows the MOST RECENT bar wins (scan from the newest bar, strict '>') |
//|   * pivots: bar p is a pivot when its high (low) is >= (<=) every neighbour in p-3..p+3; the most recent one, age  |
//|     at most 100 bars                                                                                               |
//|   * vs_pclose / prng: "previous date" = the date of the bar before today's first bar (the last trading day)        |
//|   * ib_u: IB1 = the first 4 bars of today with hour 10..14, IB2 = the first 4 with hour >= 15; completed = 4 bars  |
//|     closed, NY over London, 0.5 before                                                                             |
//|   * asia_u: 0.5 until the first bar of today with hour 0-7 exists; after that the range so far                     |
//|   * degenerate ranges are floored at 1e-6 everywhere a division happens                                             |
//+------------------------------------------------------------------+

#define MLX_N       85       // columns (the names below)
#define MLX_WARM    600      // bars of warm-up before the first exported bar
#define MLX_MINBACK 480      // bars needed behind bar i (the 480-bar ATR window)
#define MLX_WIN     520      // bars a single-bar call copies

string MlxNames[MLX_N] =
{
   "ret_1", "ret_2", "ret_4", "ret_8", "ret_16", "ret_32", "ret_64", "ret_96",
   "c0_range", "c0_body", "c0_uwick", "c0_lwick", "c0_clpos", "c0_dir",
   "c1_range", "c1_body", "c1_uwick", "c1_lwick", "c1_clpos", "c1_dir",
   "c2_range", "c2_body", "c2_uwick", "c2_lwick", "c2_clpos", "c2_dir",
   "gap_0", "atr_r96", "atr_r480", "atr_pct480", "rng_m4", "rng_m16", "rv_16", "rv_64",
   "ema_8", "ema_16", "ema_32", "ema_64", "ema_128", "ema_256",
   "slope16_4", "slope16_16", "slope64_4", "slope64_16", "disp_16_64", "disp_64_256",
   "adx", "di_diff", "adx_d4",
   "pos_7", "pos_20", "pos_50", "pos_100", "dhi_20", "dhi_50", "dhi_100", "dlo_20", "dlo_50", "dlo_100", "since_hi20", "since_lo20",
   "hour", "minute", "dow", "bar_of_day", "day_rng", "day_pos", "vs_dopen", "vs_pclose", "prng",
   "kelt_u", "expn", "h1_pos", "asia_u", "ib_u",
   "piv_hi_d", "piv_lo_d", "piv_hi_age", "piv_lo_age",
   "hh_10", "ll_10", "inside_3", "up_streak", "dn_streak", "spread_pts"
};

// the M15 series the features are computed from: chronological, index 0 = the oldest bar
struct MlxSeries
{
   int      n;
   MqlRates r[];
   double   atr[], adx[], pdi[], ndi[], e8[], e16[], e20[], e32[], e64[], e128[], e256[];
};

int    g_mlxH[9];            // 0 ATR(14), 1 ADX(14), 2.. EMA 8 16 20 32 64 128 256
string g_mlxSym = "";

// the column of a feature name, -1 when unknown
int MlxIndex(const string name)
{
   for (int k = 0; k < MLX_N; k++) if (MlxNames[k] == name) return k;
   return -1;
}

// the names joined with sep (CSV headers)
string MlxHeader(const string sep = ",")
{
   string s = MlxNames[0];
   for (int k = 1; k < MLX_N; k++) s += sep + MlxNames[k];
   return s;
}

void MlxRelease()
{
   if (g_mlxSym == "") return;
   for (int k = 0; k < 9; k++) if (g_mlxH[k] != INVALID_HANDLE) IndicatorRelease(g_mlxH[k]);
   g_mlxSym = "";
}

// the indicator handles for sym (M15), created once; false = a handle failed
bool MlxHandles(const string sym)
{
   if (g_mlxSym == sym) return true;
   int per[7] = {8, 16, 20, 32, 64, 128, 256};
   int h[9];
   h[0] = iATR(sym, PERIOD_M15, 14);
   h[1] = iADX(sym, PERIOD_M15, 14);
   for (int k = 0; k < 7; k++) h[2 + k] = iMA(sym, PERIOD_M15, per[k], 0, MODE_EMA, PRICE_CLOSE);
   for (int k = 0; k < 9; k++)
      if (h[k] == INVALID_HANDLE) {
         for (int q = 0; q < 9; q++) if (h[q] != INVALID_HANDLE) IndicatorRelease(h[q]);
         return false;
      }
   MlxRelease();
   for (int k = 0; k < 9; k++) g_mlxH[k] = h[k];
   g_mlxSym = sym;
   return true;
}

// count bars ending at shift (0 = the forming bar) into S. false = not that many bars yet, or the indicators are still calculating
bool MlxLoad(const string sym, int shift, int count, MlxSeries &S)
{
   S.n = 0;
   if (count <= 0 || !MlxHandles(sym)) return false;
   if (CopyRates(sym, PERIOD_M15, shift, count, S.r) != count) return false;
   if (CopyBuffer(g_mlxH[0], 0, shift, count, S.atr) != count) return false;
   if (CopyBuffer(g_mlxH[1], 0, shift, count, S.adx) != count) return false;
   if (CopyBuffer(g_mlxH[1], 1, shift, count, S.pdi) != count) return false;
   if (CopyBuffer(g_mlxH[1], 2, shift, count, S.ndi) != count) return false;
   if (CopyBuffer(g_mlxH[2], 0, shift, count, S.e8) != count) return false;
   if (CopyBuffer(g_mlxH[3], 0, shift, count, S.e16) != count) return false;
   if (CopyBuffer(g_mlxH[4], 0, shift, count, S.e20) != count) return false;
   if (CopyBuffer(g_mlxH[5], 0, shift, count, S.e32) != count) return false;
   if (CopyBuffer(g_mlxH[6], 0, shift, count, S.e64) != count) return false;
   if (CopyBuffer(g_mlxH[7], 0, shift, count, S.e128) != count) return false;
   if (CopyBuffer(g_mlxH[8], 0, shift, count, S.e256) != count) return false;
   S.n = count;
   return true;
}

// highest high / lowest low of bars a..b
void MlxHiLo(const MlxSeries &S, int a, int b, double &hi, double &lo)
{
   hi = -DBL_MAX; lo = DBL_MAX;
   for (int j = MathMax(a, 0); j <= b; j++) { hi = MathMax(hi, S.r[j].high); lo = MathMin(lo, S.r[j].low); }
}

// population std of the n one-bar close changes ending at bar i
double MlxStdDiff(const MlxSeries &S, int i, int n)
{
   double s = 0, s2 = 0;
   for (int j = i - n + 1; j <= i; j++) { double d = S.r[j].close - S.r[j - 1].close; s += d; s2 += d * d; }
   double m = s / n;
   return MathSqrt(MathMax(s2 / n - m * m, 0.0));
}

// bar p is a pivot high (low): its high (low) is the extreme of p-3..p+3 (ties count)
bool MlxIsPivot(const MlxSeries &S, int p, bool high)
{
   for (int q = p - 3; q <= p + 3; q++) {
      if (q == p) continue;
      if (high ? S.r[q].high > S.r[p].high : S.r[q].low < S.r[p].low) return false;
   }
   return true;
}

// the MLX_N features of bar i of S (needs MLX_MINBACK bars behind it). spread = spread_pts (0 in the exporter). Returns MLX_N, or -1
int MlxCompute(const MlxSeries &S, int i, int spread, double &f[])
{
   if (i < MLX_MINBACK || i >= S.n) return -1;
   ArrayResize(f, MLX_N);
   double A = MathMax(S.atr[i], 1e-6);
   double c = S.r[i].close, o = S.r[i].open;
   int k = 0;
   // 1-8 returns
   int rn[8] = {1, 2, 4, 8, 16, 32, 64, 96};
   for (int q = 0; q < 8; q++) f[k++] = (c - S.r[i - rn[q]].close) / A;
   // 9-26 the last three candles
   for (int q = 0; q < 3; q++) {
      double o_ = S.r[i - q].open, c_ = S.r[i - q].close, h_ = S.r[i - q].high, l_ = S.r[i - q].low, rg = MathMax(h_ - l_, 1e-6);
      f[k++] = rg / A;
      f[k++] = MathAbs(c_ - o_) / rg;
      f[k++] = (h_ - MathMax(o_, c_)) / rg;
      f[k++] = (MathMin(o_, c_) - l_) / rg;
      f[k++] = (c_ - l_) / rg;
      f[k++] = c_ > o_ ? 1 : c_ < o_ ? -1 : 0;
   }
   // 27 gap
   f[k++] = (o - S.r[i - 1].close) / A;
   // 28-30 ATR regime
   double m96 = 0, m480 = 0; int below = 0;
   for (int j = i - 479; j <= i; j++) {
      m480 += S.atr[j];
      if (j >= i - 95) m96 += S.atr[j];
      if (j < i && S.atr[j] < S.atr[i]) below++;
   }
   f[k++] = S.atr[i] / MathMax(m96 / 96.0, 1e-6);
   f[k++] = S.atr[i] / MathMax(m480 / 480.0, 1e-6);
   f[k++] = below / 479.0;
   // 31-32 mean ranges
   double s4 = 0, s16 = 0;
   for (int j = i - 15; j <= i; j++) { double rg = MathMax(S.r[j].high - S.r[j].low, 1e-6); s16 += rg; if (j >= i - 3) s4 += rg; }
   f[k++] = s4 / 4.0 / A;
   f[k++] = s16 / 16.0 / A;
   // 33-34 realised volatility
   f[k++] = MlxStdDiff(S, i, 16) / A;
   f[k++] = MlxStdDiff(S, i, 64) / A;
   // 35-46 EMAs, slopes, dispersion
   f[k++] = (c - S.e8[i]) / A;
   f[k++] = (c - S.e16[i]) / A;
   f[k++] = (c - S.e32[i]) / A;
   f[k++] = (c - S.e64[i]) / A;
   f[k++] = (c - S.e128[i]) / A;
   f[k++] = (c - S.e256[i]) / A;
   f[k++] = (S.e16[i] - S.e16[i - 4]) / A;
   f[k++] = (S.e16[i] - S.e16[i - 16]) / A;
   f[k++] = (S.e64[i] - S.e64[i - 4]) / A;
   f[k++] = (S.e64[i] - S.e64[i - 16]) / A;
   f[k++] = (S.e16[i] - S.e64[i]) / A;
   f[k++] = (S.e64[i] - S.e256[i]) / A;
   // 47-49 ADX
   f[k++] = S.adx[i];
   f[k++] = S.pdi[i] - S.ndi[i];
   f[k++] = S.adx[i] - S.adx[i - 4];
   // 50-61 position in the last n bars, distances, bars since the extremes
   int pn[4] = {7, 20, 50, 100}; double hiN[4], loN[4];
   for (int q = 0; q < 4; q++) { MlxHiLo(S, i - pn[q] + 1, i, hiN[q], loN[q]); f[k++] = (c - loN[q]) / MathMax(hiN[q] - loN[q], 1e-6); }
   for (int q = 1; q < 4; q++) f[k++] = (hiN[q] - c) / A;
   for (int q = 1; q < 4; q++) f[k++] = (c - loN[q]) / A;
   int jh = i, jl = i;                           // ties: the most recent bar (features.py scans from the newest bar with a strict '>')
   for (int j = i - 1; j >= i - 19; j--) { if (S.r[j].high > S.r[jh].high) jh = j; if (S.r[j].low < S.r[jl].low) jl = j; }
   f[k++] = i - jh;
   f[k++] = i - jl;
   // 62-65 the clock (server time)
   MqlDateTime d; TimeToStruct(S.r[i].time, d);
   f[k++] = d.hour;
   f[k++] = d.min;
   f[k++] = d.day_of_week;
   long day = (long)S.r[i].time / 86400;
   int j0 = i;
   while (j0 > 0 && (long)S.r[j0 - 1].time / 86400 == day) j0--;
   f[k++] = i - j0;
   // 66-70 today and the previous date
   double dh, dl; MlxHiLo(S, j0, i, dh, dl);
   f[k++] = (dh - dl) / A;
   f[k++] = (c - dl) / MathMax(dh - dl, 1e-6);
   f[k++] = (c - S.r[j0].open) / A;
   if (j0 > 0) {
      int j1 = j0 - 1, jj = j1; long pday = (long)S.r[j1].time / 86400;
      while (jj > 0 && (long)S.r[jj - 1].time / 86400 == pday) jj--;
      double ph, pl; MlxHiLo(S, jj, j1, ph, pl);
      f[k++] = (c - S.r[j1].close) / A;
      f[k++] = (ph - pl) / A;
   } else { f[k++] = 0; f[k++] = 0; }
   // 71-72 Keltner position, range expansion
   f[k++] = (c - S.e20[i]) / (2 * A);
   double h10, l10, h20, l20; MlxHiLo(S, i - 9, i, h10, l10); MlxHiLo(S, i - 19, i - 10, h20, l20);
   f[k++] = MathMin((h10 - l10) / MathMax(h20 - l20, 1e-6), 10.0);
   // 73 the developing H1 candle (same date and hour)
   long hr0 = (long)S.r[i].time / 3600;
   int jh1 = i;
   while (jh1 > 0 && (long)S.r[jh1 - 1].time / 3600 == hr0) jh1--;
   double hh1, ll1; MlxHiLo(S, jh1, i, hh1, ll1);
   f[k++] = (c - ll1) / MathMax(hh1 - ll1, 1e-6);
   // 74 the Asian range (today, hours 0-7, so far)
   double ah = -DBL_MAX, al = DBL_MAX; bool any = false;
   for (int j = j0; j <= i; j++) {
      long sec = (long)S.r[j].time % 86400;
      if (sec < 8 * 3600) { ah = MathMax(ah, S.r[j].high); al = MathMin(al, S.r[j].low); any = true; }
   }
   f[k++] = any ? (c - al) / MathMax(ah - al, 1e-6) : 0.5;
   // 75 the Initial Balance (features.py _sessions): IB1 = the first 4 bars of today with hour 10..14, IB2 = the first 4 with hour >= 15;
   //    the completed one (NY over London), 0.5 before 4 bars have closed
   int i1n = 0, i2n = 0; double i1h = 0, i1l = 0, i2h = 0, i2l = 0;
   for (int j = j0; j <= i; j++) {
      int hr = (int)(((long)S.r[j].time % 86400) / 3600);
      if (hr >= 15) {
         if (i2n < 4) { if (i2n == 0) { i2h = S.r[j].high; i2l = S.r[j].low; } else { i2h = MathMax(i2h, S.r[j].high); i2l = MathMin(i2l, S.r[j].low); } i2n++; }
      } else if (hr >= 10) {
         if (i1n < 4) { if (i1n == 0) { i1h = S.r[j].high; i1l = S.r[j].low; } else { i1h = MathMax(i1h, S.r[j].high); i1l = MathMin(i1l, S.r[j].low); } i1n++; }
      }
   }
   if (i2n == 4) f[k++] = (c - i2l) / MathMax(i2h - i2l, 1e-6);
   else if (i1n == 4) f[k++] = (c - i1l) / MathMax(i1h - i1l, 1e-6);
   else f[k++] = 0.5;
   // 76-79 the last confirmed pivots (3 bars each side, up to 100 bars back)
   int ph_ = -1, pl_ = -1;
   for (int p = i - 3; p >= i - 100 && p >= 3; p--) {
      if (ph_ < 0 && MlxIsPivot(S, p, true)) ph_ = p;
      if (pl_ < 0 && MlxIsPivot(S, p, false)) pl_ = p;
      if (ph_ >= 0 && pl_ >= 0) break;
   }
   f[k++] = ph_ >= 0 ? (S.r[ph_].high - c) / A : 0;
   f[k++] = pl_ >= 0 ? (c - S.r[pl_].low) / A : 0;
   f[k++] = ph_ >= 0 ? i - ph_ : 0;
   f[k++] = pl_ >= 0 ? i - pl_ : 0;
   // 80-84 bar patterns
   int hh = 0, ll = 0, ins = 0;
   for (int j = i - 9; j <= i; j++) {
      if (S.r[j].high > S.r[j - 1].high) hh++;
      if (S.r[j].low < S.r[j - 1].low) ll++;
      if (j >= i - 2 && S.r[j].high <= S.r[j - 1].high && S.r[j].low >= S.r[j - 1].low) ins++;
   }
   f[k++] = hh;
   f[k++] = ll;
   f[k++] = ins;
   int up = 0, dn = 0;
   for (int j = i; j >= 0 && S.r[j].close > S.r[j].open; j--) up++;
   for (int j = i; j >= 0 && S.r[j].close < S.r[j].open; j--) dn++;
   f[k++] = up;
   f[k++] = dn;
   // 85 the spread
   f[k++] = spread;
   return k;
}

// the features of the M15 bar at shift (1 = the last closed bar) of sym. spread = spread_pts for that bar (live: SymbolInfoInteger(SYMBOL_SPREAD);
// the exporter: 0). Returns MLX_N, or -1 when the bars / indicators are not there yet (call again on the next tick)
int MlxFeatures(const string sym, int shift, double &f[], int spread = 0)
{
   MlxSeries S;
   if (!MlxLoad(sym, shift, MLX_WIN, S)) return -1;
   return MlxCompute(S, MLX_WIN - 1, spread, f);
}
