# Turtle TV

Zee, 2026-10-20: *"i want to build a tradingview's copy web app which can show the entire year's candles and my MT5 EA's code applied to
the candles"* · *"i make a settings change on tradingview -> our tradingview call it "turtle tv" picks up the new settings and reflects them
on its own chart's candles -> then there's an export to MT5 button which puts all the optimized settings to an MT5 EA and runs the tests and
brings the result and publishes the result below the chart on turtle tv"* · *"maybe we can make TV generate a json turtle can read, and turtle
export a json the mt5 EA maker can read"*

**Start:** double-click `start_turtle_tv.bat` (or `py monitor/saad_view/server.py`), then open **http://127.0.0.1:8773**.

## What it is

A TradingView-style chart of the **whole year** of XAUUSD 15-min candles (Blueberry real ticks, `XAUUSD_BB`, Jan 1 – Oct 17 2026). Every
trade, number and table on it comes from the **MT5 Strategy Tester running the real EA**. The page only displays what the EA exported.
There is no strategy logic in Python or JavaScript (CLAUDE.md: a Python port is never a backtest).

- **Chart:** candles, the EA's own fast / slow EMAs, ADX in its own pane with the minimum line, every trade as an arrow at its fill
  price with a dotted line to its exit, stand-aside trades in grey, and optionally every setup and skip. Hovering a candle shows what the
  EA decided on it.
- **Below the chart:**
  - Overview: net, PF, win rate, drawdown, equity curve, the settings that differ from the EA's defaults, and chart-only settings.
  - Months, Weekdays.
  - Range boxes: BUY / SELL, ticked or not, plus what the stand-aside trades would have made.
  - List of trades: click one to see it on the chart.
  - Why no trade: setups by skip reason.
- **Runs:** every MT5 run is kept (`runs/`, git-ignored) and can be picked from the header to compare.
- **Speed:** a year takes about 45–60 s in MT5 (rig `axi7`).

The four-year `m15.npz` candles use both the raw quotes and per-second paths from the downloaded XAUUSD tick CSV for the tester's intraminute execution and fills. Build them once on this PC with `py monitor/saad_view/build_m15_tick_points.py`; the default input is `data_15min_2015_onwards_xauusd/XAUUSD_202201030100_202610232021.csv`. The builder streams the CSV and writes disk-backed arrays under `simdata/`, so no full tick history is loaded into RAM. Minutes with no source ticks remain gaps; the tester does not fabricate quotes for them.

The Exit Research Lab keeps the full tick path while a position, pending entry or stand-aside trade is active. After the first point of an otherwise idle minute, it skips the remaining seconds because setup changes are processed at that first point; the scan still tests every setting with the same execution rules.

When a scan is repeated after a suggestion is picked, it re-tests up to nine of the other previously ranked settings first. Turtle TV publishes those results as soon as that batch finishes, then refreshes the ranking as the rest of the settings complete. A fresh scan without previous suggestions starts with one move per setting; intermediate updates are sent only when new results are ready.

## The flow

1. **TradingView → Turtle TV.**
   - "take settings" reads the Saad indicator's settings from the open TradingView chart. It uses the compare page's reader in
     `monitor/saad_compare/server.py` and maps them to the EA's inputs.
   - With **follow TradingView** ticked, every change on the chart is picked up after it has stayed the same for 5 s. A newer change drops
     a run that is still going.
   - The page lists chart settings the EA doesn't have ("On the chart but not in the EA").
   - If the same settings were already run, the existing run is shown and MT5 isn't run again.
2. **MT5:** the run uses `mt5/Saad_strategy_15min_view.mq5`, v1.27 verbatim plus the export. Trading is identical: no delay
   +$242,911 / 198 trades, exactly as v1.27.
3. **Export to MT5:**
   - if there is no completed MT5 run matching the current chart settings and timeframe, the button first starts that run and continues the export automatically when it finishes (it cancels the handoff if the chart settings change while testing);
   - writes `settings/Saad_strategy_15min_TurtleTV_<run>.json` with every production EA input (current run values where shared, production defaults for the rest);
   - writes the preset `Saad_strategy_15min_TurtleTV.set` into terminals that already have the production EA;
   - generates a separate `Saad_strategy_15min_TurtleTV_<run>.mq5` candidate without overwriting the release EA, compiles it in the isolated MT5 rig, and runs that compiled candidate in MT5 Strategy Tester using the selected run's symbol, timeframe, dates, deposit, delay and settings;
   - after compilation, tester report creation and a successful test, copies the candidate `.mq5`, `.ex5` and candidate-specific `.set` into MT5 terminals that have the production EA. The top-menu button reports failure instead of claiming the EA is ready if any required stage fails or no attachable terminal is updated;
   - saves the candidate tester report as `runs/<run>_candidate.htm`, available from the completion notice;
   - the matching saved-settings row enables **Download MT5 Compiled EA**. It downloads a ZIP containing the `.mq5` source and `.ex5` binary, and opens Explorer at the installed binary's MT5 Experts folder;
   - the saved row permanently records each successful export's EA name/version, compile date, source/binary/preset paths, and final MT5 tester metrics/report. During generation, that row shows the current export stage and progress;
   - starts the existing random-delay run on the same timeframe if the run on screen had none; matching still requires the same settings and timeframe.
   - **Download MT5 Report** saves the actual HTML Strategy Tester report for the matching run.
4. **EA maker:**
   - `py monitor/saad_view/make_ea_from_settings.py <json> --out <name>` writes an EA whose **defaults** are those settings; it rejects missing/unknown inputs and keeps the trade-comment version aligned with `#property version`.
   - MetaEditor compilation starts from a clean `.ex5` and log; an export proceeds only with a fresh zero-error, zero-warning compile and a non-empty binary. The Strategy Tester tests that compiled candidate before installation, and installed binaries are hash-checked against the tested build.
   - Shipping a version still needs `--in-place --version X.YY` plus the VERSION.md / VERSION_HISTORY.md rows.

## The settings file (`"format": "turtle-settings/1"`)

| Key | What |
|---|---|
| `ea`, `ea_version` | the EA the settings are for (Saad_strategy_15min, 1.27) |
| `ea_inputs` | every input of that EA, defaults filled in |
| `changed_from_defaults` | only the ones that differ from the EA's defaults |
| `chart_only` | settings switched on in the chart that the EA doesn't have |
| `chart`, `tradingview` | the chart (symbol, timeframe, when it was read) and its own 160 settings by Pine variable |
| `mt5_result` | run, dates, delay, net, PF, trades, win rate, max drawdown, months (exports only) |

`settings/tradingview_latest.json` is rewritten whenever Turtle TV reads a changed chart. `settings/turtletv_export_latest.json` is the last export.

## Files

- `server.py`: the page server and runner (port 8773).
- `static/`: the page. Lightweight Charts 5.0.9 by TradingView is kept here under its Apache 2.0 licence; its logo on the chart is the
  required attribution.
- `make_view_ea.py`: rebuilds the viewer EA from `mt5/Saad_strategy_15min.mq5`. **Run it after any change to that EA.**
- `make_ea_from_settings.py`: the EA maker.

**Rig:** Turtle TV uses `C:\mt5_rig_axi7`. The compare page's 10-month view (127.0.0.1:8772) also uses axi2–7 when it's switched on, so
don't run both at once.

## The Turtle TV Tester, the optimizer and Ask Claude (2026-10-20, later the same day)

Zee: *"we want a faster few seconds running optimizer"* · *"its ok since we have our own chart we can rely on python to build an optimizer"* ·
*"we toggle a setting in plus and minus 1 step. if it results in an improvement we further take steps until there's no effect of that setting"* ·
*"in turtle tv i want to be able to tune the settings same way as in tradingview"* · *"connect claude to this web page"*

- **Turtle TV Tester** (`sim.py`): v1.27's rules as a numba-compiled loop over every 1-minute candle of the year. It needs `NUMBA_CPU_NAME=generic`
  on this ARM laptop, which sim.py sets itself.
  - **Speed:** 7–14 ms a year.
  - **Data:** the viewer EA's export with `InpExportM1` (278,805 one-minute candles with spreads) in `simdata/year.npz` (git-ignored).
    Rebuild with `py sim.py --build` after a new MT5 export.
  - **Checked against MT5** (`validate.py`, Blueberry Jan 1 – Oct 17, no delay):
    - v1.27 takes **194 of MT5's 198 trades**, 190 with the same result; median gap 8 cents on the entry, $16 on the result;
    - setups 5,000 vs 4,990; skip counts within 1%;
    - **11 different settings ranked the same way as MT5 (Spearman 0.95)**;
    - **optimistic for tight stops** (SL × 1.2: +$236k vs MT5 +$191k), because it can't see the order inside a 1-minute candle.
- **Tuning like TradingView:** the settings panel next to the chart re-runs the Turtle TV Tester on every change. The MT5 Strategy Tester section
  underneath shows MT5's result for the same settings ("Check in MT5", about a minute).
- **Optimizer** (`optimizer.py`, the Turtle TV Tester's "Optimizer" tab), Zee's method:
  - each setting ± one step; keep stepping while it helps (by at least 1%); passes until nothing changes;
  - scored on **Jan – Jun only**; Jul – Oct is shown but never chooses;
  - **Cut down Avg Loss** and **Cut down Worst Loss** score the average and single largest losing trade respectively (closer to zero is better); Python results are hypotheses, and MT5 is the promotion check;
  - about 200 tries in 1.6 s; optional restarts; the range boxes only when ticked.
  - **First run from v1.27:** Jan – Jun +$159k → +$205k, but Jul – Oct +$91k → +$76k. It fitted the past, and the page says so.
- **Risk Manager:** uses the actual MT5 run `r20261024_235213` as its diagnosis reference. In that report `InpSlMode=2`, so `InpSlUsd=25` is the active stop distance; `InpSlPips` and `InpSlAtrMult` do not set that stop. `InpMaxRiskUsd` filters entries by stop distance rather than capping an open trade. Numeric risk controls have chart-linked sliders. Its optional scan tests every configured grid value for each selected control, one setting at a time, and preserves at least 70% of baseline training trades. Ranked suggestion cards show full-period net, WR, PF, trades and loss metrics, plus train/held-out results and the trade-offs against the baseline; each can be applied individually. An optional “scan again after every pick” setting repeats the search from the updated chart. Held-out results are reported but never used to select; the scan does not apply settings automatically or start an MT5 run. Simulator output is a hypothesis only—verify any candidate with the MT5 Strategy Tester.
- **Ask Claude:** sends the chart picture (`chart.takeScreenshot()`) and the data behind it (settings, both testers' results, the trades and candles in
  view) from the server to the Claude API (`claude-opus-5-5`; key `monitor/.claude_api_key`, never sent to the page).
  - 2026-10-20: the call reached the API, but the account had no credits ("credit balance is too low").
