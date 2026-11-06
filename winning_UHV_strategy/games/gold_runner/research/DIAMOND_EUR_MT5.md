# UHV Diamond on EUR/USD: MT5 Strategy Tester results (2026-11-04)

**Question.** Does Zee's 1-minute "UHV Diamond" setup have an edge on EUR/USD, and does the 15-minute chop filter
(efficiency ratio, the filter that gave **94.1%** on gold, report section 34) carry over? The answer decides whether a
"Diamond" hint in the game (EUR/USD, TP 2 pips / SL 2 pips, ~0.1-pip spread) means anything.

**Every number in this file is an MT5 Strategy Tester result** on real ticks with random execution delay. No Python
simulated a fill. Python was used only to convert Zee's tick export into the tester's input format, to measure median bar
ranges, and to tabulate the tester's own deal lists.

## Answer first

"Break-even WR" below is avg loss / (avg win + avg loss), the "coin-flip" WR the brief asked for. It is **not** what
a random entry wins. At the game geometry a random entry starts each trade one spread behind, so it wins less than
break-even. That is why the table also carries a measured **random entry** row.

| | trades | WR | break-even WR | net (1.00 lot) | verdict |
|---|---|---|---|---|---|
| **Random entry (NullEntry), game geometry** | **16,561** | **46.5%** | 50.9% | -0.17 pip/trade | the baseline: what any entry wins at TP 2 / SL 2 here |
| **Diamond, game geometry, no filter** | 119 | **41.2%** | 49.9% | -43.1 pips (-0.36/trade) | below break-even and below random; vs random p = 0.27, so **not distinguishable from random** |
| Diamond, game, ER >= 0.45 | 17 | 58.8% | 49.6% | +6.4 pips | noise: CI 36-78%, vs random p = 0.34; Jan-Jun 8/10, Jul-Nov 2/7 |
| Diamond, game, ER >= 0.38 + trend 2 | 13 | 53.8% | 49.4% | +2.4 pips | noise: CI 29-77%, vs random p = 0.78 |
| Diamond, native geometry, no filter | 117 | **77.8%** | 81.5% | -18.6 pips | below break-even, same shape of failure as gold unfiltered (75.9% vs ~84%) |
| Diamond, native, ER >= 0.45 | 14 | 78.6% | 76.3% | +1.1 pips | no 94%; noise (CI 52-92%) |
| Diamond, native, ER >= 0.38 + trend 2 | 11 | 81.8% | 83.0% | -0.6 pips | no 94%; noise (CI 52-95%) |

**There is no measurable Diamond edge on EUR/USD in 2026.**
- At the game's geometry the unfiltered Diamond wins 41.2%, against a 49.9% break-even and a measured 46.5% for random
  entry. It is below break-even, borderline (p = 0.07). It is not distinguishable from random entry (p = 0.27). Jul-Nov
  alone reads 32.6%, but that is one of about 60 p-values in these tables, so one at the 0.03-0.08 level is expected
  by chance.
- The chop filter that made gold 94% leaves only **13-17 setups in ten months** on EUR/USD. Their win rates (54-59% at
  the game geometry, 79-82% at the native one) sit near break-even. Every confidence interval spans both break-even
  and random. The filtered rows also flip sign between halves: Jan-Jun positive, Jul-Nov negative in every filtered
  configuration at both geometries.
- Turning off the hump budget for more samples (sensitivity table) doubles the counts and changes nothing: 47.3%
  unfiltered (random: 46.5%), 53-56% filtered.
- A native-geometry random control is not possible: its stop sits under a retracement, which a random entry does not
  have.

**For the game:** a "Diamond" hint at TP 2 / SL 2 is not a usable signal either way. Unfiltered it does no better than
random entry, which itself loses one spread per trade. Filtered, it appears about 1.5 times a month and cannot be told
apart from random. If the hint stays, it should be presented as entertainment, not as an edge. Fading it is not
supported either: 41% vs 46.5% random is p = 0.27.

## What was run

- **EA:** `mt5/DiamondEUR_lab.mq5` (new, lab only). It is the Trinity_1min v1.00 host with Saad and VSISA switched off.
  Its Diamond engine `mt5/DiaEUR_lab.mqh` is a copy of `mt5/TriDia.mqh`, the engine Trinity actually includes. The
  copy is the same code as `DiamondEngineM1.mqh`, apart from magic, lots, stack multiplier and the timeframe input.
  **The Diamond rules are untouched.** The copy adds only:
  - a `[DIAFIRE]` log line: full date-time, 5-decimal prices, UHV high/low, retracement extreme, tick volumes;
  - a `[DIAFAIL]` line for refused orders. The shipped engine `break`s silently.
  - `D_InpLabFromFill` (default **false**): re-anchors the *same* SL/TP distances to the actual fill price after the
    order fills. It is used only for the game geometry, because the brief says "from the fill".

  Shipped EAs, their defaults and LAWS.md were not touched. Nothing was committed.
- **Data:** custom symbol **`EURUSD_ZX`** built from Zee's own MT5 tick export
  `EURUSD_tick_data/EURUSD.i_202601020000_202611040757.csv`:
  - 21,504,908 ticks; blank BID/ASK cells were forward-filled.
  - Specs and sessions are copied from Axi `EURUSD.pro`: 5 digits, contract 100,000.
  - Loaded with the new script `mt5/EurTickLoad_lab.mq5` (`CustomTicksReplace`, the BbTickLoad pattern). It reads the
    rig's own `MQL5/Files`, never Common/Files.
  - Lives on rig **`C:/mt5_rig_axi4`** only.
  - No Axi rig had EUR tick history (each `EURUSD.pro` tick folder held one 123 KB `ticks.dat`), so the broker symbol
    was not used.
- **Tick quality receipt:** 21,379,397 ticks over 312,024 M1 bars = **68.5 ticks per bar**: real ticks, not the 4-per-bar
  OHLC trap. The tester reports "100% real ticks". 312,024 bars = the export's 313,464 bars minus 1,440 (Jan 2, which
  MT5 used as warm-up history and did not trade).
- **Spread** in the export: median **0.10 pip**, p90 0.20 pip, the same median 09-21 server time. That is the game's
  spread. **The custom symbol books no commission**, which also matches the game's cost model. (A commission-charging
  account would subtract its round-trip cost from every trade. Axi `.pro`'s actual EURUSD commission was not measured
  in this session.)
- **Tester:** headless `monitor/strategy_lab/axi_rig.py` with every input pinned (the EA's own and all three engines'
  `.mqh` defaults, then the overrides below).
  - Model 4 (every tick based on real ticks), **ExecutionMode -1 (random delay)**, M1, deposit $100,000, 1:400. Margin
    never binds.
  - **1.00 lot**, so $10 = 1 pip. **One ticket per setup** (`D_InpUseDiamonds=false`, `D_InpStackLots=false`,
    `D_InpMaxOpen=1`).
  - Period: From 2026.01.02, To 2026.11.04. MT5 treats To as exclusive, so the last bar traded is Nov 3 23:59.
  - Halves are split by entry date from each full run's deal list. Their drawdown is closed-balance drawdown.
- **Pinned in every run:**
  - `InpUseSaad=false`, `InpUseVsisa=false`, `InpUseDia=true`;
  - `D_InpOandaVolume=0`: volume = the tester's tick count. It varies bar to bar (UHV volumes 21-138 in the parity files).
  - `D_InpOandaColour/OandaPrice=false`, `D_InpTargetR=0`, `D_InpBreakEvenR=0`, `D_InpBailSec=0`, `D_InpFailCandles=0`,
    `D_InpJuryMode=0`, `D_InpReqLaws=0`, `D_InpNyOnly=false`, `D_InpCooldownBar=3`;
  - every rule input at its engine default: TrendLook 20, Pivot 3, RetraceBack 20, UhvBodyMin 0.5, BreakWindow 12,
    CamelTrend mode 1, RetraceFix on, **MaxHumps 3**.
- **Geometry 1, native scaled.** Ratio r = EUR median M1 range / gold median M1 range = 0.00011 / $1.93 = **5.7e-5**:
  - EUR: Zee's export, bars with >= 5 ticks; 0.00010 over all bars.
  - Gold: Turtle TV M1 bars, `monitor/saad_view/simdata/m1x.npz`, Jan 2 - Oct 21 2026.

  Scaled and rounded to whole points:

  | input | gold | EUR |
  |---|---|---|
  | `D_InpStructStop` | 0.50 | 0.00003 |
  | `D_InpTargetPts` | 1.0 | 0.00006 (0.6 pip) |
  | `D_InpStopPts` | 20 | 0.00114 (inactive, because the structural stop is on) |
  | `D_InpMaxHoldMin` | 20 | 20 (time, unscaled) |

  Pivot counts, body ratios and ER thresholds are unchanged. The realised shape is about 1 : 4.4 (avg win 0.79 pip,
  avg loss 3.48 pips), close to gold's 1 : 5.2 ($1.12 / $5.85 per 0.01).
- **Geometry 2, game:** `D_InpStructStop=0`, `D_InpStopPts=0.00020`, `D_InpTargetPts=0.00020`, `D_InpMaxHoldMin=0` (no
  clock), no breakeven, `D_InpLabFromFill=true`. Geometry 2b repeats it anchored to the quote (the engine's own
  behaviour) and gives the same conclusion.
- **Filters** (Trinity's `InpDiaMinER` / `InpDiaTrend`, M15, unit-free):
  - off = 0 / 0;
  - `0.45 / 0`;
  - `0.38 / 2`.

  `0.38 / 3` was added because report section 34's 94.8% row ("chop >= 0.38 + full M15 EMA trend") is trend level
  **3**, not 2.
- **Coin-flip WR** = avg loss / (avg win + avg loss), from the realised dollars of each row: the break-even win rate. A
  setup has an edge only if WR is above it. "p vs coin" is the two-sided exact binomial p-value of the observed wins
  against that break-even rate. In the tables below the column is still headed "coin-flip WR"; it means break-even.
- **Random-entry control** (`testing/test_tips.md` Part 2.2): the existing `mt5/NullEntry.mq5`, unmodified.
  - Setup: same symbol, period and random delay; 1.00 lot; SL/TP 0.00020 anchored to the quote (like geometry 2b);
    `InpMaxHoldMin=100000` (no clock); one position at a time; it fires on every 15-minute boundary when flat and
    alternates sides.
  - Result: **16,561 trades, 46.5% WR**, avg win 1.97 pips, avg loss 2.04 pips, net -2,856 pips (-0.17 pip/trade).
    Jan-Jun 46.3%, Jul-Nov 46.9%.
  - Report: `diaeur_null15`. Receipt: `diamond_eur_mt5/runs/null15.json`.
  - Diamond vs random at the game geometry (exact binomial against 46.5%): unfiltered p = 0.27, ER 0.45 p = 0.34,
    ER 0.38 + T2 p = 0.78, hump budget off p = 0.85.

## Results

### Geometry 1 - native Diamond scaled to EUR/USD


**Jan 2 - Nov 3 2026**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 117 | **77.8%** | 81.5% | -3.7 | -186 (-18.6 p) | +7.89 (0.79 p) | -34.77 (3.48 p) | 274 | 0.29 |
| ER >= 0.45 | 14 | **78.6%** | 76.3% | +2.3 | +11 (+1.1 p) | +8.09 (0.81 p) | -26.00 (2.60 p) | 59 | 1.00 |
| ER >= 0.38 + trend 2 | 11 | **81.8%** | 83.0% | -1.2 | -6 (-0.6 p) | +7.89 (0.79 p) | -38.50 (3.85 p) | 55 | 1.00 |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 12 | **83.3%** | 86.2% | -2.8 | -16 (-1.6 p) | +6.50 (0.65 p) | -40.50 (4.05 p) | 56 | 0.68 |

**Jan - Jun**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 71 | **77.5%** | 82.2% | -4.7 | -157 (-15.7 p) | +8.29 (0.83 p) | -38.31 (3.83 p) | 241 | 0.28 |
| ER >= 0.45 | 8 | **87.5%** | 72.6% | +14.9 | +41 (+4.1 p) | +9.43 (0.94 p) | -25.00 (2.50 p) | 25 | 0.69 |
| ER >= 0.38 + trend 2 | 4 | **100.0%** | 0.0% | +100.0 | +42 (+4.2 p) | +10.50 (1.05 p) | -0.00 (0.00 p) | 0 | nan |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 4 | **100.0%** | 0.0% | +100.0 | +28 (+2.8 p) | +7.00 (0.70 p) | -0.00 (0.00 p) | 0 | nan |

**Jul - Nov 3**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 46 | **78.3%** | 80.0% | -1.7 | -29 (-2.9 p) | +7.28 (0.73 p) | -29.10 (2.91 p) | 119 | 0.71 |
| ER >= 0.45 | 6 | **66.7%** | 82.2% | -15.5 | -30 (-3.0 p) | +5.75 (0.57 p) | -26.50 (2.65 p) | 53 | 0.29 |
| ER >= 0.38 + trend 2 | 7 | **71.4%** | 86.9% | -15.5 | -48 (-4.8 p) | +5.80 (0.58 p) | -38.50 (3.85 p) | 55 | 0.23 |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 8 | **75.0%** | 86.8% | -11.8 | -44 (-4.4 p) | +6.17 (0.62 p) | -40.50 (4.05 p) | 56 | 0.29 |

### Geometry 2 - game: TP 2 pips / SL 2 pips from the fill, no clock


**Jan 2 - Nov 3 2026**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 119 | **41.2%** | 49.9% | -8.8 | -431 (-43.1 p) | +20.71 (2.07 p) | -20.66 (2.07 p) | 493 | 0.07 |
| ER >= 0.45 | 17 | **58.8%** | 49.6% | +9.3 | +64 (+6.4 p) | +20.50 (2.05 p) | -20.14 (2.01 p) | 99 | 0.48 |
| ER >= 0.38 + trend 2 | 13 | **53.8%** | 49.4% | +4.4 | +24 (+2.4 p) | +21.00 (2.10 p) | -20.50 (2.05 p) | 63 | 0.79 |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 13 | **46.2%** | 49.7% | -3.6 | -19 (-1.9 p) | +20.67 (2.07 p) | -20.43 (2.04 p) | 79 | 1.00 |

**Jan - Jun**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 73 | **46.6%** | 50.2% | -3.6 | -109 (-10.9 p) | +20.62 (2.06 p) | -20.77 (2.08 p) | 171 | 0.56 |
| ER >= 0.45 | 10 | **80.0%** | 49.8% | +30.2 | +124 (+12.4 p) | +20.62 (2.06 p) | -20.50 (2.05 p) | 41 | 0.06 |
| ER >= 0.38 + trend 2 | 5 | **80.0%** | 50.3% | +29.7 | +62 (+6.2 p) | +20.75 (2.08 p) | -21.00 (2.10 p) | 21 | 0.38 |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 5 | **80.0%** | 50.0% | +30.0 | +60 (+6.0 p) | +20.00 (2.00 p) | -20.00 (2.00 p) | 20 | 0.38 |

**Jul - Nov 3**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 46 | **32.6%** | 49.5% | -16.9 | -322 (-32.2 p) | +20.93 (2.09 p) | -20.52 (2.05 p) | 344 | 0.03 |
| ER >= 0.45 | 7 | **28.6%** | 50.0% | -21.4 | -60 (-6.0 p) | +20.00 (2.00 p) | -20.00 (2.00 p) | 80 | 0.45 |
| ER >= 0.38 + trend 2 | 8 | **37.5%** | 48.9% | -11.4 | -38 (-3.8 p) | +21.33 (2.13 p) | -20.40 (2.04 p) | 62 | 0.73 |
| ER >= 0.38 + trend 3 (gold 94.8% row) | 8 | **25.0%** | 48.2% | -23.2 | -79 (-7.9 p) | +22.00 (2.20 p) | -20.50 (2.05 p) | 79 | 0.29 |

### Geometry 2b - game distances anchored to the QUOTE (engine default), for comparison


**Jan 2 - Nov 3 2026**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 119 | **41.2%** | 48.8% | -7.6 | -367 (-36.7 p) | +20.86 (2.09 p) | -19.84 (1.98 p) | 452 | 0.10 |
| ER >= 0.45 | 17 | **52.9%** | 47.8% | +5.1 | +32 (+3.2 p) | +19.11 (1.91 p) | -17.50 (1.75 p) | 99 | 0.81 |
| ER >= 0.38 + trend 2 | 13 | **53.8%** | 49.3% | +4.6 | +24 (+2.4 p) | +20.57 (2.06 p) | -20.00 (2.00 p) | 68 | 0.79 |

**Jan - Jun**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 73 | **46.6%** | 48.6% | -2.0 | -58 (-5.8 p) | +20.32 (2.03 p) | -19.21 (1.92 p) | 143 | 0.82 |
| ER >= 0.45 | 10 | **70.0%** | 39.4% | +30.6 | +93 (+9.3 p) | +18.43 (1.84 p) | -12.00 (1.20 p) | 36 | 0.06 |
| ER >= 0.38 + trend 2 | 5 | **80.0%** | 52.2% | +27.8 | +56 (+5.6 p) | +19.25 (1.93 p) | -21.00 (2.10 p) | 21 | 0.38 |

**Jul - Nov 3**

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| filter off | 46 | **32.6%** | 48.3% | -15.7 | -309 (-30.9 p) | +22.07 (2.21 p) | -20.65 (2.06 p) | 328 | 0.04 |
| ER >= 0.45 | 7 | **28.6%** | 49.2% | -20.6 | -61 (-6.1 p) | +21.50 (2.15 p) | -20.80 (2.08 p) | 81 | 0.45 |
| ER >= 0.38 + trend 2 | 8 | **37.5%** | 47.0% | -9.5 | -32 (-3.2 p) | +22.33 (2.23 p) | -19.80 (1.98 p) | 68 | 0.73 |

### Sensitivity (NOT the Diamond as shipped or not the main setting)

| run | trades | WR | coin-flip WR | WR - coin | net $ (pips) | avg win | avg loss | max DD $ (closed) | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| native, filter off, ZERO delay | 121 | **78.5%** | 84.6% | -6.0 | -320 (-32.0 p) | +6.76 (0.68 p) | -37.00 (3.70 p) | 368 | 0.08 |
| game, filter off, ZERO delay | 119 | **41.2%** | 49.4% | -8.2 | -406 (-40.6 p) | +20.98 (2.10 p) | -20.49 (2.05 p) | 481 | 0.08 |
| game, ER 0.45, ZERO delay | 17 | **52.9%** | 49.3% | +3.6 | +25 (+2.5 p) | +20.67 (2.07 p) | -20.12 (2.01 p) | 119 | 0.81 |
| game, ER 0.38+T2, ZERO delay | 13 | **53.8%** | 49.5% | +4.3 | +23 (+2.3 p) | +20.71 (2.07 p) | -20.33 (2.03 p) | 62 | 0.79 |
| native, filter off, hump budget OFF | 237 | **78.9%** | 81.0% | -2.1 | -137 (-13.7 p) | +7.77 (0.78 p) | -33.12 (3.31 p) | 330 | 0.41 |
| native, ER 0.45, hump budget OFF | 31 | **87.1%** | 79.7% | +7.4 | +83 (+8.3 p) | +7.33 (0.73 p) | -28.75 (2.88 p) | 79 | 0.38 |
| native, ER 0.38+T2, hump budget OFF | 24 | **79.2%** | 80.5% | -1.4 | -13 (-1.3 p) | +7.63 (0.76 p) | -31.60 (3.16 p) | 103 | 0.80 |
| game, filter off, hump budget OFF | 243 | **47.3%** | 49.9% | -2.6 | -256 (-25.6 p) | +20.74 (2.07 p) | -20.63 (2.06 p) | 540 | 0.44 |
| game, ER 0.45, hump budget OFF | 32 | **53.1%** | 49.4% | +3.7 | +50 (+5.0 p) | +21.18 (2.12 p) | -20.67 (2.07 p) | 121 | 0.73 |
| game, ER 0.38+T2, hump budget OFF | 25 | **56.0%** | 48.9% | +7.1 | +73 (+7.3 p) | +21.14 (2.11 p) | -20.27 (2.03 p) | 142 | 0.55 |

### Receipts per run

| run | ticks | bars | ticks/bar | report trades | report WR | report net | report equity DD | fires | refused orders | exits tp/sl/clock |
|---|---|---|---|---|---|---|---|---|---|---|
| game_er38t2-d0 | 21,379,397 | 312,024 | 68.5 | 13 | 53.85% | 23.0 | 77.00 (0.08%) | 13 | 0 | 7/6/0 |
| game_er38t2-h0 | 21,379,397 | 312,024 | 68.5 | 25 | 56.00% | 73.0 | 148.00 (0.15%) | 25 | 1 | 14/11/0 |
| game_er38t2 | 21,379,397 | 312,024 | 68.5 | 13 | 53.85% | 24.0 | 77.00 (0.08%) | 13 | 0 | 7/6/0 |
| game_er38t3 | 21,379,397 | 312,024 | 68.5 | 13 | 46.15% | -19.0 | 88.00 (0.09%) | 13 | 0 | 6/7/0 |
| game_er45-d0 | 21,379,397 | 312,024 | 68.5 | 17 | 52.94% | 25.0 | 127.00 (0.13%) | 17 | 0 | 9/8/0 |
| game_er45-h0 | 21,379,397 | 312,024 | 68.5 | 32 | 53.12% | 50.0 | 132.00 (0.13%) | 32 | 1 | 17/15/0 |
| game_er45 | 21,379,397 | 312,024 | 68.5 | 17 | 58.82% | 64.0 | 107.00 (0.11%) | 17 | 0 | 10/7/0 |
| game_off-d0 | 21,379,397 | 312,024 | 68.5 | 119 | 41.18% | -406.0 | 481.00 (0.48%) | 119 | 2 | 49/70/0 |
| game_off-h0 | 21,379,397 | 312,024 | 68.5 | 243 | 47.33% | -256.38 | 540.38 (0.54%) | 243 | 4 | 115/128/0 |
| game_off | 21,379,397 | 312,024 | 68.5 | 119 | 41.18% | -431.0 | 504.00 (0.50%) | 119 | 2 | 49/70/0 |
| gameq_er38t2 | 21,379,397 | 312,024 | 68.5 | 13 | 53.85% | 24.0 | 81.00 (0.08%) | 13 | 0 | 7/6/0 |
| gameq_er45 | 21,379,397 | 312,024 | 68.5 | 17 | 52.94% | 32.0 | 107.00 (0.11%) | 17 | 0 | 9/8/0 |
| gameq_off | 21,379,397 | 312,024 | 68.5 | 119 | 41.18% | -367.0 | 452.00 (0.45%) | 119 | 2 | 49/70/0 |
| nat_er38t2-h0 | 21,379,397 | 312,024 | 68.5 | 24 | 79.17% | -13.0 | 107.00 (0.11%) | 24 | 2 | 19/4/1 |
| nat_er38t2 | 21,379,397 | 312,024 | 68.5 | 11 | 81.82% | -6.0 | 55.00 (0.05%) | 11 | 2 | 9/2/0 |
| nat_er38t3 | 21,379,397 | 312,024 | 68.5 | 12 | 83.33% | -16.0 | 56.00 (0.06%) | 12 | 1 | 10/2/0 |
| nat_er45-h0 | 21,379,397 | 312,024 | 68.5 | 31 | 87.10% | 83.0 | 93.00 (0.09%) | 31 | 2 | 27/3/1 |
| nat_er45 | 21,379,397 | 312,024 | 68.5 | 14 | 78.57% | 11.0 | 79.00 (0.08%) | 14 | 3 | 11/2/1 |
| nat_off-d0 | 21,379,397 | 312,024 | 68.5 | 121 | 78.51% | -320.0 | 384.00 (0.38%) | 121 | 0 | 95/21/5 |
| nat_off-h0 | 21,379,397 | 312,024 | 68.5 | 237 | 79.75% | -137.38 | 330.38 (0.33%) | 237 | 10 | 189/42/6 |
| nat_off | 21,379,397 | 312,024 | 68.5 | 117 | 77.78% | -186.0 | 291.00 (0.29%) | 117 | 4 | 91/21/5 |
| parity | 380,719 | 7,192 | 52.9 | 5 | 20.00% | -62.0 | 72.00 (0.07%) | 5 | 1 | 1/4/0 |
| parity_oct | 1,807,473 | 31,648 | 57.1 | 9 | 44.44% | -20.0 | 70.00 (0.07%) | 9 | 1 | 4/5/0 |
| parity_traded | 380,719 | 7,192 | 52.9 | 5 | 20.00% | -60.0 | 70.00 (0.07%) | 5 | 1 | 1/4/0 |

Notes on the tables:
- WR counts a trade as a win when its net is above $0. The report's own WR agrees except for one $0 trade in nat_er45.
- "nan" p-values are rows with no losses, where the break-even rate is undefined.
- Swap is included (custom symbol swaps copied from EURUSD.pro). It matters only in a few overnight holds.
- The receipts table's "refused orders" counts every `[DIAFAIL]` refusal. Each one is a detected setup that became no
  trade.

## Fire list for the game port (parity check)

- `games/gold_runner/research/diamond_eur_fires_mt5.csv`: week **Mon 26 - Fri 30 Oct 2026**, 5 fires.
- `games/gold_runner/research/diamond_eur_fires_mt5_oct2026.csv`: the whole of **October 2026**, 9 fires.

Columns: the requested `time_server,side,uhv_time,uhv_high,uhv_low,retrace_extreme`, followed by `entry_quote`,
`uhv_tickvol`, `breakout_tickvol` and `origin_time`.

- **Config:** game geometry, filter off, but `D_InpMaxOpen=99` and `D_InpCooldownBar=0`, so the list is the detector,
  not gated by open positions. The traded config (`MaxOpen 1`, cooldown 3) gave the identical 5 fires that week.
- `time_server` is the decision minute: the open of the bar after the breakout candle, i.e. the breakout candle's close.
  `uhv_time` and `origin_time` are bar-open times. All times are **server time of Zee's `EURUSD.i` export**.
- **Volume is the tick count per M1 bar** (number of quote changes in Zee's export), and so is the UHV comparison. The
  port must use the same feed's tick counts, not PXTrader quote counts, or the UHV choice will differ.
- **One fire is missing from both CSVs:** **2026-10-30 10:45 sell** was detected but its order was refused
  ("invalid stops", quote 1.11838). Its UHV fields were never printed, so the port should expect a sell signal there.
- **Watch out:** in all 5 fires of that week `origin_time == uhv_time`, meaning the retracement's first breaking candle
  was also the loudest. The October file shows other cases (10-05 10:21, 10-07 19:31, 10-21 12:27), and those test
  the UHV search.
- `retrace_extreme` is computed exactly as the engine's structural stop does: the lowest low (buy) or highest high
  (sell) from the origin bar to the breakout bar.
- The detector is stateful. Hump budget, CamelTrend pivots and cooldown all look back 20+ bars, so a port starting
  cold on Oct 26 needs at least the prior trading day of bars. The MT5 run had all history from Jan 2 available.

## Caveats that travel with these numbers

1. **Small samples.** The engine's own hump budget (`D_InpMaxHumps=3`, shipped) refuses about 90% of bars on EUR/USD
   (281,648 of 312,024), so the filtered rows hold 11-17 trades. No row is statistically distinguishable from random
   entry. The unfiltered game row is below break-even only borderline (p = 0.07).
2. **One instrument-year.** 2026 on one feed (Zee's `EURUSD.i` export, broker not named in the file). The ER thresholds
   were chosen on gold in report section 34, so this *is* an out-of-sample test of them, and they did not transfer.
3. **Per setup, not per ticket.** Gold's 94% was counted per ticket with 1-4 stacked tickets per setup. EUR numbers here
   are one ticket per setup, which is the honest unit for a game hint.
4. **Hard-coded gold literals** in `D_DiamondsFor` (0.10, 0.30 price) are inert here. They only size the stack and feed
   the law gate, and both are off.
5. **Delay.** Random delay was used for every main row. The zero-delay rows in the sensitivity table give the same
   verdict. Refused orders ("invalid stops", mostly around rollover or thin quotes) were 0-4 per main run, each one a
   detected setup that became no trade. A few fill re-anchors failed (MT5 retcode 3, at most 4 in a run); those trades
   kept their quote-anchored stops.
6. **Costs.** No commission was booked, matching the game. Any per-trade commission (not measured here) hits the
   native geometry hardest, because its average win is under 1 pip.
7. **Sessions** come from Axi EURUSD.pro while tick times are the export's server time. If that server's timezone
   differs, a few Friday/Sunday-edge ticks could fall outside trade sessions, which shows up as refused orders.

## Reproduce

Scripts and per-run receipts (deals and tester log extracts) are in `games/gold_runner/research/diamond_eur_mt5/`:

| script | what it does |
|---|---|
| `conv.py` | export -> binary ticks in the rig's `MQL5/Files` |
| `runload.py axi4` | `EurTickLoad_lab` -> `EURUSD_ZX` |
| `batch.py axi4 <names>` | runs a list of passes, e.g. `nat_off game_er45 game_off-d0 game_off-h0 parity` |
| `tables.py` | builds the tables above and the parity CSVs |
| `null_run.py` | the NullEntry random-entry control |

The converted ticks (`eur_t.bin`, `eur_bid.bin`, `eur_ask.bin`, about 500 MB) remain in `C:/mt5_rig_axi4/MQL5/Files`.
They can be deleted once the symbol is loaded.

To use another rig, first run `runload.py <rig>`: the custom symbol exists on axi4 only.
