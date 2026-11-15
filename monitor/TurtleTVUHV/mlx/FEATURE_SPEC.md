# MLX feature specification (v1, 2026-11-01)

Per-bar state of the XAUUSD M15 chart at the CLOSE of bar `i`, computed identically in Python (`mlx/features.py`, from `sim.data("m15")`)
and MQL5 (`mt5/MlxFeatures.mqh`, from the chart's M15 bars). Every value uses only bars `<= i`. "ATR" = ATR(14) of bar i (Wilder, as `iATR`
and the tester's `D["atr"]`); divide by `max(ATR, 1e-6)`. EMA(n) = standard exponential average with alpha = 2/(n+1) seeded on the first close
(as `iMA(..., MODE_EMA)`); the first 600 bars of history are warm-up and are not exported. `range = h - l` of a bar (floor 1e-6).
Server time = the chart's time (Blueberry, UTC+2/+3); hour = `hr15` in the tester.

Column order and names are FIXED (the ONNX tensor follows this order after SHAP pruning; the kept list is written to `simdata/mlx_features.json`).

| # | name | definition |
|---|------|------------|
| 1-8 | `ret_1 ret_2 ret_4 ret_8 ret_16 ret_32 ret_64 ret_96` | `(c[i] - c[i-n]) / ATR` |
| 9-14 | `c0_range c0_body c0_uwick c0_lwick c0_clpos c0_dir` | bar i: `range/ATR`, `|c-o|/range`, `(h-max(o,c))/range`, `(min(o,c)-l)/range`, `(c-l)/range`, `sign(c-o)` (0 if equal) |
| 15-20 | `c1_*` (same six) | bar i-1 |
| 21-26 | `c2_*` (same six) | bar i-2 |
| 27 | `gap_0` | `(o[i] - c[i-1]) / ATR` |
| 28 | `atr_r96` | `ATR / mean(ATR[i-95..i])` |
| 29 | `atr_r480` | `ATR / mean(ATR[i-479..i])` |
| 30 | `atr_pct480` | share of `ATR[i-479..i-1]` strictly below `ATR[i]` (0..1) |
| 31-32 | `rng_m4 rng_m16` | `mean(range[i-n+1..i]) / ATR` |
| 33-34 | `rv_16 rv_64` | std of the n one-bar changes `c[j]-c[j-1]`, j in (i-n+1..i), population std, `/ ATR` |
| 35-40 | `ema_8 ema_16 ema_32 ema_64 ema_128 ema_256` | `(c[i] - EMA_n[i]) / ATR` |
| 41-42 | `slope16_4 slope16_16` | `(EMA_16[i] - EMA_16[i-n]) / ATR` for n = 4, 16 |
| 43-44 | `slope64_4 slope64_16` | same with EMA_64 |
| 45 | `disp_16_64` | `(EMA_16 - EMA_64) / ATR` |
| 46 | `disp_64_256` | `(EMA_64 - EMA_256) / ATR` |
| 47 | `adx` | ADX(14) of bar i (Wilder, as `iADX` main line) |
| 48 | `di_diff` | `(+DI - -DI)` of ADX(14) at bar i |
| 49 | `adx_d4` | `ADX[i] - ADX[i-4]` |
| 50-53 | `pos_7 pos_20 pos_50 pos_100` | `(c[i] - min(l[i-n+1..i])) / (max(h[i-n+1..i]) - min(l[i-n+1..i]))`, floor 1e-6 |
| 54-56 | `dhi_20 dhi_50 dhi_100` | `(max(h[i-n+1..i]) - c[i]) / ATR` |
| 57-59 | `dlo_20 dlo_50 dlo_100` | `(c[i] - min(l[i-n+1..i])) / ATR` |
| 60-61 | `since_hi20 since_lo20` | bars since the highest high / lowest low of the last 20 bars (0 = this bar) |
| 62 | `hour` | server hour of bar i's OPEN time (0-23) |
| 63 | `minute` | minute of bar i's open (0, 15, 30, 45) |
| 64 | `dow` | day of week of the open, Monday = 1 .. Friday = 5 (Sunday = 0) |
| 65 | `bar_of_day` | bars since the first bar whose open date = bar i's date (0-based) |
| 66 | `day_rng` | (today's highest high - lowest low, bars of this date up to i) / ATR |
| 67 | `day_pos` | `(c[i] - today's low) / (today's high - today's low)`, floor 1e-6 |
| 68 | `vs_dopen` | `(c[i] - open of today's first bar) / ATR` |
| 69 | `vs_pclose` | `(c[i] - close of the last bar of the previous date) / ATR` (0 when there is none) |
| 70 | `prng` | previous date's (high - low) / ATR (0 when none) |
| 71 | `kelt_u` | `(c[i] - EMA_20[i]) / (2 * ATR)` (the EA's Keltner family: EMA 20 +- 2 ATR; -1..1 inside the channel) |
| 72 | `expn` | `(max h - min l over bars i-9..i) / (max h - min l over bars i-19..i-10)`, floor 1e-6, cap 10 |
| 73 | `h1_pos` | position of `c[i]` in the developing H1 candle's range so far (bars with the same server hour and date, up to i), floor 1e-6 |
| 74 | `asia_u` | `(c[i] - asia_low) / (asia_high - asia_low)` where asia = bars of today with hour 0..7 (complete or so far); 0.5 if none yet |
| 75 | `ib_u` | `(c[i] - ib_low) / (ib_high - ib_low)` for the most recent completed Initial Balance of today (first 4 bars from 10:00, then from 15:00); 0.5 if none yet |
| 76 | `piv_hi_d` | `(last confirmed pivot high - c[i]) / ATR`; pivot = bar `p <= i-3` with the highest high of `p-3..p+3`, searched back up to 100 bars; 0 if none |
| 77 | `piv_lo_d` | `(c[i] - last confirmed pivot low) / ATR`, same rule on lows |
| 78 | `piv_hi_age` | bars since that pivot high (0 if none) |
| 79 | `piv_lo_age` | bars since that pivot low (0 if none) |
| 80 | `hh_10` | count of bars j in (i-9..i) with `h[j] > h[j-1]` |
| 81 | `ll_10` | count of bars j in (i-9..i) with `l[j] < l[j-1]` |
| 82 | `inside_3` | count of inside bars among i-2..i (`h[j] <= h[j-1] and l[j] >= l[j-1]`) |
| 83 | `up_streak` | consecutive bars up to i with `c > o` (0 if bar i is not up) |
| 84 | `dn_streak` | consecutive bars up to i with `c < o` |
| 85 | `spread_pts` | spread at the bar's close in points (tester: `sp1` of the last minute of the bar; MQL5: `SymbolInfoInteger(SYMBOL_SPREAD)` at that moment - live only; the exporter writes 0 and the model is trained WITHOUT this column unless both sides have it) |

85 columns (numbered 1-85 above); `spread_pts` is excluded from training by default (set `use_spread=false`). Volume is excluded on purpose: MT5's Strategy
Tester overwrites tick volume (4 ticks per bar), so a volume feature can never be reproduced in the tester.

## Labels (Python only, `mlx/labels.py`) - Triple Barrier, de Prado
At bar i (close `c[i]`), barriers on the forward path of bars i+1 .. i+24: upper = `c[i] + 1.5 * ATR[i]`, lower = `c[i] - 1.5 * ATR[i]`,
time = 24 bars. Walk forward bar by bar: `h[j] >= upper` touches the upper barrier, `l[j] <= lower` the lower one. Label **1** if the upper is
touched first, **-1** if the lower is touched first, **0** if neither within 24 bars. If BOTH are touched in the same bar j, use the 1-minute
candles inside bar j (`t1/h1/l1`) to find which came first; if still tied, the label is 0 (undecided). Bars without 24 forward bars are dropped.
Also recorded per bar: the touch bar index (for purging), and `ret_fwd_24 = (c[i+24] - c[i]) / ATR`.

## Dataset files
- `simdata/mlx_dataset.npz`: `X` float32 (n x 85), `names` (85 str), `t15` int64 (bar open time), `k15` int64 (bar index in `D["t15"]`),
  `label` int8 (1 / -1 / 0), `touch_k` int64 (bar index where the label was decided), `atr` float32, `close` float32.
- `simdata/mlx_entries.npz`: the EA's trades to translate the model into trading: for setting B (`settings/saved/2026-10-30 23-08-23.json`) and
  for the setup UNIVERSE (B with its entry filters off and `InpMaxPos 8`): arrays `k15` (entry bar), `side` (+1/-1), `entry_t`, `pnl`, `reason`,
  `src` (0 = B, 1 = universe). The model's features for a trade entered during bar k are those of bar `k-1` (the last closed bar).
- `simdata/mlx_features.json`: the spec as data: `{"all": [85 names], "kept": [...after SHAP...], "scaler": {"mean": [...], "scale": [...]}}`.
