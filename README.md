# Turtle Trader Desk — User Manual

**Pine Script v5 | TradingView Indicator | PineConnector → MT5 Automation**

---

## Table of Contents

1. [What Is the UHV Strategy?](#1-what-is-the-uhv-strategy)
2. [Visual Elements on the Chart](#2-visual-elements-on-the-chart)
3. [The Stats Panel Explained](#3-the-stats-panel-explained)
4. [The Optimizer Panel (Smiley)](#4-the-optimizer-panel-smiley)
5. [UHV Strategy Settings — Step-by-Step Setup](#5-uhv-strategy-settings--step-by-step-setup)
6. [Alert Condition Bitmask — Decoding a Trade](#6-alert-condition-bitmask--decoding-a-trade)
7. [Settings Export String — Saving and Restoring Your Config](#7-settings-export-string--saving-and-restoring-your-config)
8. [PineConnector Automation](#8-pineconnector-automation)
9. [Recommended Settings for XAUUSD (Gold)](#9-recommended-settings-for-xauusd-gold)

---

## 1. What Is the UHV Strategy?

**UHV stands for Ultra High Volume Breakout.**

The idea is simple: when institutions (banks, hedge funds) are building a large position, they leave a footprint — a candle with unusually high volume that usually ends in a retracement. They buy in size, which pushes the price up aggressively, but the market then pulls back as retail traders take profit. That pullback is your entry opportunity.

### The logic, step by step:

```
1. A candle appears with ULTRA HIGH VOLUME → this is the "UHV candle"
   (much more volume than the surrounding candles)

2. After the UHV candle, price RETRACES back down
   (the IB phase — Institutional Buildup phase)

3. Price touches a POINT OF INTEREST (POI) during the retracement
   (a Fair Value Gap, a previous High/Low, or a Support/Resistance level)

4. Price then BREAKS OUT above the high of the UHV candle (bull)
   or below the low of the UHV candle (bear)

5. → SIGNAL FIRES. Enter the trade.
```

### Why it works:

- The UHV candle shows WHERE institutions were active
- The retracement shows WHERE they wanted to add to their position
- The breakout shows CONFIRMATION that the institutional order flow is resuming
- The POI touch confirms the market found buyers/sellers at a meaningful price level

### What UHV is NOT:

- It is not a momentum strategy (chasing strong candles)
- It is not a reversal strategy (fading moves)
- It is a **continuation** strategy — you join the institutional order flow after it has paused and confirmed

---

## 2. Visual Elements on the Chart

### Signal Labels

| Label Color | Meaning |
|---|---|
| **Green label** | Bull (BUY) signal — price broke above UHV candle high |
| **Red label** | Bear (SELL) signal — price broke below UHV candle low |
| **Gray/dim label** | Signal was blocked by a filter (e.g. sweep not confirmed, wrong trend) |

### Label Text Format

Each signal label shows:
```
UHV #42
SL: $4998.50  (ATR method)
TP: $5008.20  (0.34R)
Lots: 0.033
```

- `#42` — trade number, increments with every signal fired
- `SL` — where the stop loss was placed
- `TP` — where the take profit was placed
- `Lots` — the lot size calculated for this trade

### After a Trade Closes

The label updates with the result:
```
✅ #42 TP Hit — +$8.40 Profit
```
or
```
❌ #42 SL Hit — -$4.20 Loss
```

### Candle Highlights

When **"Highlight signal candles"** is ON, a thin colored outline draws on candles that were studied by the engine. This lets you see exactly which candles triggered the setup detection logic.

### Fair Value Gap (FVG) Zones

Colored horizontal zones on the chart show where Higher Time Frame FVGs exist:
- **Green zone** — bullish FVG (gap in sell-side candles, demand area)
- **Red zone** — bearish FVG (gap in buy-side candles, supply area)
- **Gray zone** — FVG that has been filled or neutralized

These are the **Points of Interest** the strategy uses to qualify entries.

### Trend MA Line

A colored line (EMA 34) shows the current trend:
- **Thick green line** — strong uptrend
- **Thin green line** — weak uptrend
- **Thick red line** — strong downtrend
- **Thin red line** — weak downtrend

The line color fades as trend strength decreases.

### Min Spread Value

At the bottom of some labels you may see a value like `min spread: $0.28`. This is the live Exness gold spread. The script uses this to ensure no SL is placed so tight that it would be instantly hit by the spread cost on entry.

---

## 3. The Stats Panel Explained

The panel appears in the **bottom-right corner** of the chart. It updates on every bar close.

### Row by Row

| Row | What It Shows |
|---|---|
| **Header** | Ticker, timeframe, current trading session |
| **Signal Status** | `STANDING BY` / `SETUP IN PROGRESS` / `POI REACHED` / `SIGNAL FIRED` |
| **Trend** | Direction (BULLISH/BEARISH), strength bar, and estimated time to next signal |
| **TODAY divider** | — |
| **Today P&L** | Dollar gain/loss today, and current account balance |
| **Strategy subtotals** | UHV / 2BR / EVR individual P&L for today, plus avg trade duration |
| **Trade count + streak** | Signals fired, trades closed, wins, win%, and current win/loss streak |
| **Last hour + Next hour EV** | P&L from last hour, projected next-hour earnings based on EV |
| **STRATEGIES divider** | — |
| **UHV row** | All-time W/L, %, P&L, today's P&L, avg win/loss, lot size used |
| **2BR row** | Same for Two Bar Reversal strategy |
| **EVR row** | Same for Effort vs Result strategy |
| **ALL-TIME divider** | — |
| **All-time P&L** | Total P&L, win rate, EV per trade, avg win and avg loss dollar amounts |
| **Milestones** | Trades needed to double account, hours to double, washout (how many losses wipe account), yesterday P&L |
| **OPTIMIZER divider** | — |
| **Recommendations** | Smart suggestions based on your trade history (see below) |
| **Last Signal Sent** | The exact PineConnector alert string from your most recent signal |
| **Settings Export** | Full encoded settings string — copy and save externally |

### Recommendation Icons

| Icon | Priority | Meaning |
|---|---|---|
| 🚨 | Critical | Negative EV detected or large daily drawdown — stop trading until resolved |
| ⚠️ | Warning | Win rate below break-even — strategy may need adjustment |
| 💡 | Optimize | A data-driven suggestion to improve R:R or trend filtering |
| 🔓 | Unlock | A filter is blocking signals — estimate of extra P&L if you relax it |

---

## 4. The Optimizer Panel (Smiley)

In the **bottom-left corner** a smaller panel shows:

```
OPTIMIZER
😄 Loving it!  ($4.22/trade avg)
```

The smiley is based on your **average P&L per trade** compared to your target dollar-per-trade (average of uTD/tTD/eTD settings):

| Smiley | Meaning |
|---|---|
| ⌛ | No trades yet — waiting for results |
| 😄 | Average P&L per trade > 35% of target — excellent |
| 🙂 | Profitable but below target — good |
| 😐 | Near breakeven |
| 😟 | Losing on average — try different settings |

---

## 5. UHV Strategy Settings — Step-by-Step Setup

Work through these settings **in order**. Each step builds on the previous one.

---

### Step 1 — Enable the Strategy

**Setting:** `Use this strategy?` → `ON`

**What it does:** Activates the UHV Breakout engine. When OFF, no UHV signals fire and no UHV trades are tracked.

**How to set it:** Turn ON before doing anything else.

---

### Step 2 — Choose Trade Direction

**Setting:** `Trade direction?` → `Both` / `Bull only` / `Bear only`

**What it does:**
- `Both` — takes buy and sell signals
- `Bull only` — takes only buy (upside breakout) signals
- `Bear only` — takes only sell (downside breakout) signals

**How to set it:** Start with `Both`. After 20+ trades, check your stats panel to see if buys or sells are losing. If one direction has consistently negative P&L, switch to the other direction only.

**Impact:** Restricting direction reduces signal frequency but can improve win rate in trending markets.

---

### Step 3 — Set Your Risk Per Trade

Choose **one** of the three risk modes (the others are ignored):

#### Option A — Dollar Risk (recommended for beginners)

**Setting:** `Risk: Dollar risk per trade? ($)` → e.g. `5.00`

**What it does:** Automatically calculates the lot size so that if the SL is hit, you lose exactly $5 (before spread). Lot size adjusts dynamically based on how far away the SL is.

**How to set it:** Set this to an amount you are comfortable losing on a single trade. A good starting point is 1–2% of your account. For a $200 account: `$2.00` to `$4.00`.

**Impact:** This is the safest mode. Your risk is capped regardless of how wide the SL is.

---

#### Option B — % of Capital

**Setting:** `Risk: % of capital per trade (when $Risk = 0)` → e.g. `2.0`

**What it does:** Sizes lots so each trade risks this percentage of your starting capital (the `My Starting Capital` setting). If capital = $200 and % = 2, risk = $4 per trade.

**How to set it:** Set `Dollar risk per trade` to `0`, then set this %. Useful if you want risk to scale as your account grows.

---

#### Option C — Fixed Lots

**Setting:** `Risk: Fixed lot size?` → e.g. `0.033`

**What it does:** Uses the same lot size every trade, regardless of SL distance. Simple but can result in variable dollar risk.

**How to set it:** Set both `Dollar risk` and `%` to `0`, then enter your lot size.

---

### Step 4 — Set Stop Loss Placement

**Setting:** `Stop Loss: Where to place it?`

Options and when to use each:

| Option | Description | Best for |
|---|---|---|
| `ATR` | SL = entry ± (ATR × multiplier). Adapts to current volatility. | Gold — most recommended |
| `UHV` | SL below/above the UHV candle low/high + buffer. | When you want SL anchored to the institutional candle |
| `Breakout Wick` | SL below/above the breakout candle's wick. | Tight SL, higher risk of getting stopped |
| `SwingLow` | SL below/above recent swing low/high. | When trend structure is clear |
| `Dollar` | SL exactly $X from entry. | Simple fixed risk, ignores market structure |
| `Retracement's Min/Max` | SL at the lowest/highest point touched during the retracement. | Captures full range of the retracement |
| `Prev Candle` | SL below/above the previous candle's low/high + buffer. | Very tight, use with caution |

**How to set it for gold (XAUUSD):** Start with `ATR`. Set `Volatility width` to `1.9` to `2.5` — this means SL = 1.9× to 2.5× the Average True Range. On gold with ATR ≈ $1.50, that places SL about $2.85–$3.75 from entry.

---

### Step 5 — Set SL Buffer and Minimum

**Setting:** `Stop Loss: Distance $ below SL level?` (used by UHV, Breakout Wick, SwingLow, Retracement, Prev Candle modes)

**What it does:** Adds extra distance below the calculated SL reference point. For example, if SL mode is `UHV` and buffer = `$0.70`, the SL is placed $0.70 below the UHV candle's low.

**How to set it:** For gold, use `$0.50` to `$2.00`. More buffer = harder to get stopped by normal volatility, but larger loss if SL is hit.

---

**Setting:** `Stop Loss: Closest it can ever be to entry? ($)`

**What it does:** Hard floor. No SL can ever be placed closer to entry than this value, regardless of what the SL method calculates. Prevents degenerate $0.10 SL scenarios.

**How to set it for gold:** Set to at least `$1.50`. The gold spread is ~$0.28, so anything below $1.00 will be eaten by spread and slippage on entry. A value of `$1.50` to `$3.00` is safe.

**Impact:** Too low = SL gets hit by spread noise. Too high = every trade risks more than intended.

---

### Step 6 — Set Take Profit

**Setting:** `Take Profit: Which method?`

| Option | Description |
|---|---|
| `R:R Ratio` | TP = entry + (SL distance × R multiplier). E.g. 0.34R means TP is 34% of the SL distance from entry. |
| `Structural High/Low` | TP at the next swing high (bull) or swing low (bear). |
| `Dollar Amount` | TP exactly $X from entry. |

**Setting:** `Take Profit: R:R Ratio` → e.g. `0.34`

**How to set it:** For gold on a 5-minute chart with tight SLs, a ratio of `0.3` to `0.5` works well. Higher R:R means bigger wins but lower win rate. The stats panel shows your break-even win rate — match your R:R to what your actual win rate supports.

**Impact:**
- Low R:R (0.2–0.4) = more wins, smaller profit per win, win rate matters less
- High R:R (2.0+) = fewer wins, big profit per win, requires high accuracy

---

### Step 7 — Set the UHV Volume Filter (Optional but recommended)

**Setting:** `UHV Detection: Require candle to rank in top percentile?` → `ON`

**What it does:** Instead of picking any candle that is the highest volume in the retracement, this requires the UHV candle to rank in the top N% of all recent candles. Filters out weak setups where "high volume" was actually just average.

**Setting:** `Min volume percentile threshold` → e.g. `71`

**What it does:** The UHV candle must be in the top 29% of volume over the last N bars (lookback). 71 means top 29%, 90 means top 10%.

**How to set it:** Start with `71`. If you see too many weak signals, raise to `80`. If signals are too rare, lower to `60`.

---

### Step 8 — Set the Sweep Requirement

**Setting:** `Must any candle wick through or break the UHV low before the entry candle breaks its high?` → `ON` (recommended)

**What it does:** Requires that before the breakout happens, at least one candle's wick (or close) must dip below the UHV candle's low. This is the "sweep" — institutions shake out weak longs before the real move up. Without this, you can get stopped out by the sweep after you enter.

**Impact:**
- ON → fewer signals, but higher quality. You miss some trades but avoid entering before the shake-out.
- OFF → more signals, but you may enter before the sweep and get stopped.

**How to set it:** Turn ON as your default. If the stats panel shows `Sweep filter blocked N signals/day` in the recommendations section and your win rate is already high, you can consider turning it OFF.

---

### Step 9 — Set Entry Mode

**Setting:** `Open trade at` → `Candle Close` or `Instant at Breakout`

| Mode | Description |
|---|---|
| `Candle Close` | Signal fires when the breakout candle closes above the UHV high. Standard. Prevents false breakouts. |
| `Instant at Breakout` (IOE) | Signal fires the moment price ticks above the UHV high, mid-bar. Earlier fill, but candle may not confirm. |

**How to set it:** Use `Candle Close` for backtesting accuracy. Use `Instant at Breakout` for better live fills on fast markets like gold.

---

### Step 10 — Set Pre-Breakout Offset (Advanced)

**Setting:** `Pre-breakout offset ($)` → e.g. `0.05`

**What it does:** In IOE mode, this fires the signal slightly BEFORE the breakout level. If gold's UHV high is $5000.00 and offset = $0.05, the signal fires when price reaches $4999.95. This gives a better fill price.

**How to set it:** Start with `0` (disabled). If you are in IOE mode and consistently getting filled $0.10–$0.20 worse than the breakout level, try `0.05` to `0.15`.

**Setting:** `Also allow signal at actual breakout level` → `ON`

**What it does:** If you have a pre-breakout offset set but price never dips to the offset level before breaking out, this fires the signal at the actual breakout level instead of missing the trade entirely.

**How to set it:** Keep ON when using pre-breakout offset.

---

### Step 11 — Set Cooldown

**Setting:** `Cooldown: Bars after a signal before another can fire?` → e.g. `14`

**What it does:** After a UHV signal fires, the engine waits this many bars before it can fire again. Prevents signal spamming during choppy markets.

**How to set it:** On a 5-minute chart, `14` bars = 70 minutes cooldown. For gold where setups can repeat in the same session, try `10`–`20`. Longer cooldown = fewer trades but possibly better quality.

---

### Step 12 — Set Momentum Candle Filters (Optional)

**Setting:** `Momentum Candle: Require min body size?` → `ON` / `OFF`

**What it does:** Requires the breakout candle to have a strong body (the filled portion of the candle). Filters out candles that moved mostly on wicks.

**Setting:** `Min body size as % of candle range` → e.g. `60`

**What it does:** The candle body must be at least 60% of the full high-to-low range. A candle with lots of wicks and a small body scores low — these are indecision candles, not strong breakouts.

---

**Setting:** `Momentum Candle: Require max wick size?` → `ON` / `OFF`

**What it does:** Rejects breakout candles that have large wicks, since large wicks indicate the breakout was rejected at the extremes.

**Setting:** `Max wick size as % of candle range` → e.g. `15`

**What it does:** Neither the upper nor lower wick can be more than 15% of the full candle range.

---

### Step 13 — Cancel on Early Bounce (Optional)

**Setting:** `Cancel this strategy on early bounce-back?` → `ON` / `OFF`

**What it does:** If price returns to the Institutional Buildup (IB) level before touching the POI, the entire setup is cancelled. This prevents entering setups that have "failed" the retracement structure.

**How to set it:** `ON` for cleaner setups, fewer but higher-quality signals. `OFF` for more signals.

---

## 6. Alert Condition Bitmask — Decoding a Trade

Every alert sent to PineConnector includes a 16-character binary string at the end of the `comment=` field. This lets you paste any alert string to Claude and instantly decode exactly which conditions triggered (or didn't trigger) for that specific trade.

### Alert String Format

```
87782869895251,sell,XAUUSD,vol_lots=1.04,sl_price=5000.055,tp_pips=80,comment=UHV@4996.66_1:03_#1231#0110100001100000
```

Breaking down `comment=UHV@4996.66_1:03_#1231#0110100001100000`:

| Part | Value | Meaning |
|---|---|---|
| `UHV` | strategy name | Which strategy fired (UHV / 2BR / EVR / EVR-W) |
| `@4996.66` | price | Chart close price when signal fired |
| `1:03` | UTC time | Hour:minute in UTC when signal fired |
| `#1231` | trade number | Sequential trade counter |
| `#0110100001100000` | bitmask | 16-bit condition code — see table below |

### Bitmask Bit Reference

Each character is a bit (0=OFF, 1=ON), read left to right:

| Bit | Position | Meaning when 1 |
|---|---|---|
| 0 | 1st char | Direction: **1=SELL**, 0=BUY |
| 1 | 2nd char | Entry mode: **1=IOE** (Instant at Breakout), 0=Candle Close |
| 2 | 3rd char | Strategy bit (low): combined with bit 3 — see strategy table |
| 3 | 4th char | Strategy bit (high): combined with bit 2 — see strategy table |
| 4 | 5th char | Strict trend mode is **ON** for this strategy |
| 5 | 6th char | Strict trend condition was **MET** (higher-high + TP cross) |
| 6 | 7th char | Sweep requirement is **ON** |
| 7 | 8th char | Sweep was **confirmed** (wick swept UHV low before breakout) |
| 8 | 9th char | Pre-breakout offset is **ON** (uPBD > 0) |
| 9 | 10th char | Co-exist path used — fired at breakout level (pre-offset fallback) |
| 10 | 11th char | Trend direction: **1=uptrend**, 0=downtrend |
| 11 | 12th char | In session: **1=within allowed session window** |
| 12 | 13th char | Volume filter is **ON** for this strategy |
| 13 | 14th char | Volume filter condition was **MET** |
| 14 | 15th char | Opposing candle filter is **ON** (2BR only) |
| 15 | 16th char | Opposing candle condition was **MET** (2BR only) |

**Strategy encoding (bits 2–3):**

| Bit 3 | Bit 2 | Strategy |
|---|---|---|
| 0 | 0 | UHV Breakout |
| 0 | 1 | Two Bar Reversal (2BR) |
| 1 | 0 | Effort vs Result (EVR) |
| 1 | 1 | EVR Weak (EVR-W) |

### Example Decode

Bitmask: `0110100001100000`

```
Bit  0: 0 → BUY
Bit  1: 1 → IOE mode
Bit  2: 1 ╮
Bit  3: 0 ╯ → 2BR strategy
Bit  4: 1 → strict trend ON
Bit  5: 0 → strict trend NOT met (but trade fired anyway — strict trend not required for 2BR by default)
Bit  6: 0 → sweep not required
Bit  7: 0 → sweep not confirmed
Bit  8: 0 → no pre-offset
Bit  9: 0 → co-exist path not used
Bit 10: 1 → uptrend at entry
Bit 11: 1 → in session
Bit 12: 0 → volume filter OFF
Bit 13: 0 → volume filter not checked
Bit 14: 0 → opposing candle filter OFF
Bit 15: 0 → opposing candle not checked
```

**To decode any trade:** paste the full alert string to Claude and say "decode the bitmask".

---

## 7. Settings Export String — Saving and Restoring Your Config

TradingView does not allow you to export or download your indicator settings. The **Settings Export** row in the stats panel solves this.

### How to Save Your Settings

1. Open TradingView → click on your chart → open the **Data Window** (right-click → Data Window, or press `D`)
2. Find the **SETTINGS EXPORT** row in the data window
3. Copy the full string — it starts with `T1|` and contains all your settings

Example (abbreviated):
```
T1|262|100|1|0|1|1|1|1|1|50|1|0|1|0|0|71|20|0|0|0|0|0|...
```

4. Save this string in a text file, notes app, or any external storage

### How to Restore Settings

Paste the string to Claude and say: **"restore my settings from this export string"**

Claude will decode every field and tell you exactly what value each setting should be set to.

### String Format Reference

The string is pipe-delimited (`|`) in this fixed order:

```
T1 | Account | POI | UHV | 2BR | EVR | Trend | HTF | PC
```

Where each section contains:

| Section | Fields |
|---|---|
| Account | Starting Capital, Contract Size, Lot Multiplier, Spread |
| POI | Require POI, Require Touch, FVG, Prev High/Low, Sup/Res, Lookback |
| UHV | 35 fields — all UHV settings in input declaration order |
| 2BR | 19 fields — all Two Bar Reversal settings |
| EVR | 26 fields — all Effort vs Result settings |
| Trend | 19 fields — all Trend & Filter settings |
| HTF | 6 fields — Higher Time Frame settings |
| PC | 8 fields — PineConnector automation settings |

**Enum encoding** (integers represent dropdown selections):
- Direction: `0=Both`, `1=Bull only`, `2=Bear only`
- Entry mode: `0=Candle Close`, `1=Instant at Breakout`
- Take profit method: `0=R:R Ratio`, `1=Structural High/Low`, `2=Dollar Amount`
- Stop loss method (UHV): `0=UHV`, `1=ATR`, `2=Breakout Wick`, `3=SwingLow`, `4=Dollar`, `5=Retracement's Min/Max`, `6=Prev Candle`
- SL/TP format to MT5: `0=Pips`, `1=Price`
- Order type: `0=Market`, `1=Limit`
- Booleans: `0=OFF`, `1=ON`

---

## 8. PineConnector Automation

The script sends trade signals directly to **PineConnector**, which forwards them to **MetaTrader 5 (MT5)**.

### Alert String Format

```
{license_id},{direction},{symbol},vol_lots={lots},sl_price={sl},tp_price={tp},comment={tag}
```

or with pip format:

```
{license_id},{direction},{symbol},vol_lots={lots},sl_pips={sl},tp_pips={tp},comment={tag}
```

### Critical: Price vs Pips Format

PineConnector interprets `sl=` and `tp=` parameters differently depending on their name:

| Parameter name | Interpretation |
|---|---|
| `sl_pips=50` | Stop Loss is 50 pips away from entry (relative distance) |
| `sl_price=5000.05` | Stop Loss is at the absolute price 5000.05 |

**This script uses `sl_price=` when Price mode is selected.** Never confuse the two — using `sl=` for a price value sends a pips value to MT5 and can result in catastrophically wide stops.

### Setup Steps

1. In indicator settings → `PineConnector Automation` group:
   - Enter your `PineConnector License ID`
   - Set `MT5 Symbol Name` to match exactly what your MT5 broker uses (e.g. `XAUUSD`)
   - Set `MT5 pip size` → Gold = `0.01`, ETH = `0.1`, BTC = `1.0`
   - Set `Stop Loss format` → `Price` recommended (avoids pip rounding errors)
   - Set `Take Profit format` → `Price` or `Pips`
   - Set `Order type` → `Market` (standard) or `Limit` (uses limit order at entry level)

2. In TradingView, create an alert:
   - Condition: `UHV Bull Signal` or `UHV Bear Signal`
   - Message: leave blank or use `{{strategy.order.alert_message}}`
   - Use webhook to your PineConnector endpoint

---

## 9. Recommended Settings for XAUUSD (Gold)

These settings have been tuned for gold on a 5-minute chart. Use as a starting point and adjust based on your backtest results.

| Setting | Recommended Value | Reason |
|---|---|---|
| Spread ($) | `0.28` | Exness standard gold spread |
| Min SL distance | `1.50` | Below 1.50 gets eaten by spread + slippage |
| SL method | `ATR` | Adapts to gold volatility sessions |
| ATR multiplier | `1.92` | ~$2.88 SL on avg ATR of $1.50 |
| SL buffer | `0.70` | Extra margin below structure |
| TP method | `R:R Ratio` | Simple, predictable |
| TP ratio | `0.34` | Quick TP, high win rate |
| Entry mode | `Instant at Breakout` | Better fills on gold |
| Require sweep | `ON` | Filters out most false breakouts |
| UHV percentile | `ON`, threshold `71` | Top 29% volume only |
| Risk mode | Dollar risk `$2–5` | Fixed dollar risk per account size |
| Cooldown | `14 bars` | 70 min on 5m chart |
| SL format to MT5 | `Price` | Use `sl_price=` not `sl_pips=` — critical for gold |

### Gold-Specific Warning

Gold moves approximately `$0.28` per pip, and typical spread is `$0.28` (28 pips). Any SL closer than `$1.00` to entry will be hit by normal spread noise or slippage on entry. The `uSMn` (SL minimum) setting enforces this floor.

---

*Documentation version: 2026-03-17*
