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
   - writes `settings/Saad_strategy_15min_TurtleTV_<run>.json` (the settings + MT5's result);
   - writes the preset `Saad_strategy_15min_TurtleTV.set` into every MT5 terminal that has the EA (EA inputs → Load);
   - starts a random-delay run if the run on screen had none.
4. **EA maker:**
   - `py monitor/saad_view/make_ea_from_settings.py <json> --out <name>` writes an EA whose **defaults** are those settings.
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
