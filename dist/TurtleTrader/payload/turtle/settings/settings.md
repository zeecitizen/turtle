# Turtle Trader Desk — Settings Reference

**Strategy:** Ultra High Volume Breakout (UHV) + Effort vs Result (EVR) on XAUUSD (Gold), 1-minute chart
**Broker:** Exness Pro — XAUUSDm (mini-lot symbol), 500:1 leverage
**Automation:** PineConnector bridge → MetaTrader 5

This document preserves the full settings configuration as of 2026-03-18, with explanations of what each setting does and why it matters. Written so that anyone unfamiliar with the strategy logic can understand not just the values, but the reasoning behind them.

---

## How the Strategy Works (Overview)

1. **Impulse phase** — Price makes a strong directional move (the "Initial Bar" / IB phase).
2. **Retracement phase** — Price pulls back against the impulse. During this pullback, the script finds the candle with the highest volume — this is the **UHV candle** (Ultra High Volume). That candle represents institutional supply or demand: the biggest player stepped in here.
3. **Breakout** — When price breaks back out of the UHV candle's range (breaking its high for bulls, low for bears), it signals that the institutional order is now being filled in the direction of the original impulse.
4. **Entry** — An alert fires and PineConnector sends a market order to MT5 automatically.

The **EVR (Effort vs Result)** strategy is a complementary VSA (Volume Spread Analysis) approach. It looks for a candle that sweeps through a prior significant candle's low (or high) with high volume but *closes back inside* it — meaning the effort (volume) produced little result (price reversal). This signals absorption and a likely continuation.

---

## My Account

| Setting | Value | Explanation |
|---|---|---|
| My Starting Capital ($) | 692 | Your current account equity in dollars. Used to calculate position sizes when using % risk. If you add/withdraw funds, update this to keep risk sizing accurate. |
| Contract size ($/point/lot) | 100 | Broker's contract specification for XAUUSD. On Exness, 1 lot of gold = $100 per $1 move = $1 per 0.01 move (1 pip). Do not change unless your broker has a different contract size. |
| Position Size Multiplier | 1 | Scales all lot sizes simultaneously. 1.0 = normal. 2.0 = double all lots (doubles risk and profit). 0.5 = half size. Use to quickly scale down during drawdowns or scale up in high-conviction conditions. |
| Spread ($) | 0.3 | Your live broker spread for gold in dollars. Exness Pro gold spread ≈ $0.28–$0.30. This widens the SL minimum so the backtest reflects real spread cost. Critical: if your spread is wider (e.g., during news), SL can be hit by spread alone. |
| Account Leverage | 500 | Leverage ratio (500:1). Used in margin calculations to ensure position sizes don't exceed available margin. |

---

## Points of Interest (POI)

POIs are price levels that add context and confluence to a trade setup. When enabled, the script requires price to interact with these zones before or at signal time.

| Setting | Value | Explanation |
|---|---|---|
| Require POI zone to exist before retracement starts | Off | When ON: a POI (FVG, Higher Low, or S/R flip) must already exist on the chart before the retracement phase begins. Filters setups that have no structural backing. |
| Require POI Touch Before Signal | Off | When ON: price must actually reach and touch the POI zone during the retracement. Stricter than the above — the POI must be tagged. |
| Higher Time Frame FVG (imbalance zone) | Off | Treats an unfilled Fair Value Gap (price gap between candle wicks on HTF) as a POI. Price tends to return to fill these gaps. |
| Previous Higher Low | Off | Treats the previous swing's Higher Low as a POI. In an uptrend, Higher Lows represent buyer-supported levels. |
| Broken High / Low (flipped S/R) | Off | When a resistance is broken it becomes support (and vice versa). Treats these flipped levels as POIs. |
| POI Lookback (bars) | 50 | How many bars back to scan for POI levels. 50 bars = look at the last 50 candles for FVG, HL, S/R zones. |

---

## Strategy: Ultra High Volume Breakout (UHV)

### Core Logic

The UHV candle is the candle with the most volume during the retracement. It represents institutional activity. The breakout is when price closes back above (bull) or below (bear) that candle's range, confirming the institutional order is being filled.

### Enable & Direction

| Setting | Value | Explanation |
|---|---|---|
| Use this strategy? | On | Master switch for UHV. If off, no UHV signals fire at all. |
| Trade direction? | Both | Take both bull (buy) and bear (sell) signals. "Bull only" / "Bear only" when you have a strong directional bias (e.g., only sell during a clear downtrend session). |

### UHV Detection Filters

| Setting | Value | Explanation |
|---|---|---|
| Must candle wick through UHV low before entry? | Off | When ON: a candle must sweep (wick through) the UHV candle's low (for bull) before the entry breakout. This is a "false break" filter — the market hunts stops below the UHV, then reverses. Reduces signal count but increases quality. |
| Must breakout candle have lower volume? | Off | When ON: the breakout candle must have less volume than the UHV candle. A quiet breakout on lower volume after a high-volume setup often indicates institutional absorption is complete. |
| Align direction to HTF? | Off | When set to a timeframe (1, 5, 15, 60, 240 min): only take bull signals if that HTF is bullish, only take bear signals if that HTF is bearish. Filters counter-trend setups. |
| UHV Detection: require volume percentile? | Off | When ON: the UHV candle must rank in the top N% of volume over the last X bars. OFF = simply pick whichever candle has the highest volume during this retracement (no percentile requirement). |
| Min volume percentile threshold | 91 | Only used when the above is ON. 91 = UHV candle must be in the top 9% of volume over the lookback window. Very strict filter. |
| Lookback bars for percentile | 4 | Only used when percentile mode is ON. Compare the UHV candle's volume against the last 4 bars. |
| Bars after UHV before entry? | 0 | Minimum number of candles that must pass after the UHV candle before the breakout entry is valid. 0 = entry can happen on the very next bar. Increase to require a deeper retracement. |

### Entry Timing

| Setting | Value | Explanation |
|---|---|---|
| Open trade at | Instant at Breakout (IOE) | **IOE mode**: fires the alert the moment price crosses the UHV candle's high/low intra-bar, without waiting for the candle to close. Gets earlier fills at the level. **Candle Close**: waits for the full 1-minute bar to close above/below the level. More conservative, fewer false entries, but worse fill price. |
| Pre-breakout offset ($) | 4 | Fire the alert $4 BEFORE price reaches the UHV breakout level. Because PineConnector has ~150-200ms latency (Pine → webhook → PineConnector → MT5), by the time MT5 gets the order, price has moved. Firing early compensates: if price is moving at $5/minute and latency is 150ms, the price moves ~$0.012 during transit — but the offset of $4 accounts for the typical pre-level entry for a better average fill. |
| Post-breakout offset ($) | 0 | Wait for price to move $X past the breakout level before entering. Combines with pre-offset. 0 = disabled. Use to confirm the level breaks convincingly before entering. |
| Also allow signal at actual breakout level | On | If the pre-offset is set ($4) but price blows through the level without pausing at the pre-offset trigger, fire at the actual breakout price instead of missing the trade entirely. This is the "co-exist" fallback. |

### Risk & Position Sizing

| Setting | Value | Explanation |
|---|---|---|
| Dollar risk per trade ($) | 0 | Fixed dollar amount to risk. When 0, the script uses % risk (below). |
| % of capital per trade | 4.1 | Risk 4.1% of starting capital ($692) per trade = ~$28.37 at risk. Lots are auto-calculated: Lots = RiskAmount ÷ (SLDistance × ContractSize). If SL is $5 away: Lots = $28.37 ÷ ($5 × 100) = 0.057 lots. |
| Fixed lot size | 0.37 | Fallback lot size used only when both Dollar risk and % risk are 0. |

### Take Profit

| Setting | Value | Explanation |
|---|---|---|
| TP method | Dollar Amount | Which method calculates the TP price. "Dollar Amount" = fixed $ profit target. "R:R Ratio" = TP at entry ± (SLdistance × R:R). "Structural High/Low" = TP at the next structural floor (bear) or ceiling (bull). |
| R:R Ratio | 0.1 | Only used when method = R:R Ratio. 0.1 = very tight scalp — TP is only 10% of the SL distance from entry. With a $5 SL, TP = $0.50 profit target. |
| Fixed $ target (Dollar method) | 0.5 | Only used when method = Dollar Amount. TP is placed $0.50 profit from entry. For 0.057 lots × $100 × $0.50 = $2.85 profit per trade. |
| Override with fixed pips (SL) | 0 | Override the SL method entirely with a fixed pip count. 0 = use the SL method above. Setting to e.g., 30 would always place SL 30 pips ($0.30) from entry regardless of UHV position. |
| Override with fixed pips (TP) | 50 | Override the TP method with 50 pips = $0.50 from entry. This overrides the Dollar Amount method. With 1 pip = $0.01 for XAUUSD, 50 pips = $0.50 TP. This ensures TP is always a fixed distance from entry, immune to structural level proximity issues that cause Error 4756. |

### Stop Loss

| Setting | Value | Explanation |
|---|---|---|
| Where to place SL? | Breakout Wick | **Breakout Wick**: SL is placed beyond the entry candle's wick (the candle that broke out). For a bear breakout, the entry candle's high becomes the SL reference. This is tight and closely tied to the actual entry. Other options: "UHV" = SL at the UHV candle's extreme (wider, more room), "ATR" = volatility-based width, "SwingLow" = recent swing extreme, "Dollar" = fixed $ away, "Retracement's Min/Max" = widest point of the retracement. |
| SL Offset from SL level ($) | 2 | Buffer added beyond the SL reference level. For Breakout Wick: SL = entry candle wick + $2 beyond it. Positive = further from entry (looser stop, more room). This gives the trade room to breathe without being stopped out by noise. |
| Closest SL can ever be to entry ($) | 0.1 | Hard floor: SL can never be closer than $0.10 to entry. Prevents degenerate micro-stops (e.g., if wick is very close to entry in IOE mode). Note: with gold spread of $0.30, a $0.10 min is still inside the spread — consider raising to $1.50+ for safety. |
| Volatility width (ATR method) | 1.92 | Only used when SL method = ATR. SL = entry ± (14-period ATR × 1.92). |
| Fixed $ distance (Dollar method) | 0.3 | Only used when SL method = Dollar. SL placed $0.30 from entry. |
| Bars back to find swing (SwingLow) | 11 | Only used when SL method = SwingLow. Looks back 11 bars to find the lowest low (bull) or highest high (bear) as SL reference. |

### Breakout Quality Filters

| Setting | Value | Explanation |
|---|---|---|
| Cancel on early bounce-back? | Off | When ON: if price returns to the Initial Bar level before touching any POI during retracement, the setup is cancelled. Guards against setups where structure has already been invalidated. |
| Require min body size (momentum)? | Off | When ON: the breakout candle must have a strong body (close far from open). Filters indecision doji-style candles. |
| Min body size % of range | 60 | Only used when above is ON. Body must be ≥60% of (high-low). |
| Require max wick size? | Off | When ON: the breakout candle must have small wicks (clean directional move). |
| Max wick size % of range | 15 | Only used when above is ON. Each wick (upper and lower) must be ≤15% of the candle's total range. |
| Require volume drop vs UHV? | Off | When ON: the breakout candle must have less volume than the UHV candle (quiet breakout = institutional absorption complete). |
| Volume drop % | 5 | Only used when above is ON. Breakout volume must be ≥5% lower than UHV volume. |
| Require body breakout (IOE mode) | On | IOE-only: the candle BODY (its close) must cross the breakout level, not just a wick spike. Prevents false entries from wick-only punctures that don't represent conviction. Bar-close mode already uses close, so this only matters in IOE. |

### Timing & Gating

| Setting | Value | Explanation |
|---|---|---|
| Cooldown (bars after signal) | 0 | Minimum bars that must pass after a UHV signal before another UHV signal can fire from the same setup. 0 = no cooldown. Increase to prevent rapid re-entries in choppy conditions. |
| Alert Gate ($) | -0.05 | Controls late-signal suppression. **-1** = always fire regardless. **0** = suppress if price has already passed the TP. **-0.05** = allow firing even if price is up to $0.05 past TP (small tolerance for fast candles). **Positive value** (e.g., 0.5) = require $0.50 gap between current price and TP before firing — protects against entries where price is already near TP and would be an instant-win or Error 4756. Current value of -0.05 means: fire unless price is more than $0.05 past TP. |

---

## Strategy: Effort vs Result (EVR)

### Core Logic

The EVR candle "sweeps" through a prior significant candle's extreme (wick extends beyond the low/high) with high volume but closes back inside the prior candle's range. This is VSA's "effort vs result" principle: huge effort (volume) produced little result (no follow-through). Signals institutional absorption and likely reversal/continuation in the original direction.

| Setting | Value | Explanation |
|---|---|---|
| Use this strategy? | Off | Master switch for EVR. Currently disabled — UHV is the primary strategy. |
| Trade direction? | Both | Same as UHV direction filter. |
| Show signals on chart? | Off | Show EVR sweep candle markers visually, independent of whether actual signals fire. Useful for studying the setup without live trading it. |
| Must sweep candle have higher volume? | Off | When ON: the sweep candle must have more volume than the candle it sweeps (the "absorbed" candle). Confirms institutional footprint. |
| Minimum volume excess % | 0 | When above is ON: sweep candle must have ≥X% more volume than the swept candle. 0 = any higher volume qualifies. 20 = must be 20% more. |
| Wait for wick rejection confirmation? | Off | When ON and the sweep candle has a large rejection wick (wick > body, showing reversal in progress), wait for the NEXT candle to close in the signal direction before entering. Extra confirmation at cost of slightly worse fill. |
| Dollar risk per trade ($) | 0 | Same as UHV — use % risk instead. |
| % of capital per trade | 7 | Risk 7% of $692 ≈ $48.44 per EVR trade. EVR signals are rarer but higher conviction — justified slightly higher risk. |
| Fixed lot size | 0.011 | Fallback lot size for EVR when both risk methods = 0. |
| TP method | R:R Ratio | EVR uses R:R ratio for TP (vs UHV which uses Dollar Amount). |
| R:R Ratio | 0.2 | TP = 0.2× the SL distance from entry. |
| Fixed $ target (Dollar method) | 28 | Dollar TP fallback for EVR if method switched to Dollar Amount. |
| SL placement | UHV | For EVR, SL is placed beyond the swept candle's extreme. "UHV" here means "the high-volume candle that was swept" — SL goes beyond that candle's low (bull) or high (bear), where the institutional absorption was identified. |
| SL offset ($) | 16.27 | Buffer beyond the swept candle's wick. Large because EVR candles on gold can have wide swings. |
| Closest SL to entry ($) | 0.2 | EVR SL minimum floor — $0.20 from entry. |
| ATR volatility width | 4 | ATR multiplier if SL method = ATR. |
| Fixed $ SL distance | 2 | Fixed $ SL if method = Dollar. |
| Swing lookback bars | 11 | Swing SL lookback. |
| Cancel on early bounce-back? | Off | Same as UHV's bounce-back filter. |
| Sweep candle immediately follow HV candle? | Off | When ON: the sweep must happen on the very next bar after the high-volume candle. Consecutive bars only — no delay allowed. |
| Min close level within swept candle % | 0 | How deep the sweep candle must close inside the swept candle. 0 = anywhere inside. 50 = must close above midpoint. 100 = must reach the swept candle's far extreme (full reversal). |
| Max bars since high-vol candle | 0 | How long after the HV candle the sweep can occur. 0 = unlimited. 3 = sweep must happen within 3 bars. |
| Min wick penetration ($) | 0 | The sweep candle's wick must extend at least $X beyond the swept candle's low/high. 0 = any penetration. |
| Min volume percentile | 0 | Sweep candle must be in the top N% of volume. 0 = disabled. 50 = above average. |
| Open trade at | Candle Close | EVR uses bar-close entries (not IOE). The VSA setup requires waiting for candle confirmation. |
| Cooldown (bars) | 22 | EVR cooldown — must wait 22 bars after a signal before another EVR fires from the same setup. EVR signals are less frequent and the cooldown prevents over-trading. |

---

## Trend & Filters

These settings apply globally across both strategies.

| Setting | Value | Explanation |
|---|---|---|
| Min Trend Strength at Signal | 15 | The script calculates a trend score (0–100) based on directional momentum. A UHV/EVR signal only fires if this score ≥ 15. Score of 15 is quite permissive (low bar) — mainly filters out sideways/no-trend conditions. Raise to 30–50 to only trade in clear trending conditions. |
| Trend Persistence Lookback (bars) | 8 | How many bars to evaluate for trend consistency. Higher = requires the trend to have persisted longer before qualifying. |
| Only trade London + NY sessions? | Off | When ON: only trade during London (8–12 GMT) and New York (13–17 GMT) overlap sessions. These are highest-liquidity periods for gold. Off = trade 24/7 including low-liquidity Asian sessions (wider spreads, erratic moves). |
| Cut Low Probability Trades | Off | When ON: if a trade direction (bull or bear) has ≥10 historical trades and is negative overall P&L, suppress future trades in that direction. Self-learning filter based on real performance. |
| Avoid trading when trend is shifting? | Off | When ON: if the trend strength drops sharply (by more than the shift threshold), suppress new entries until trend stabilises. |
| — Apply to UHV? | Off | Whether the trend-shift avoidance applies to UHV signals. |
| — Apply to EVR? | Off | Whether the trend-shift avoidance applies to EVR signals. |
| Shift Threshold | 53 | The trend strength must drop by 53 points to trigger "trend shifting" status. High threshold = only truly dramatic reversals trigger it. |
| Require Full Trend Confirmation? | Off | When ON: requires a full structural trend (HH+HL for bull, LH+LL for bear) plus the trend MA must align with the trade direction. More restrictive than the basic trend strength filter. |
| — Apply to UHV? | On | Pre-positioned ON for UHV — takes effect when the main switch (above) is enabled. |
| — Apply to EVR? | Off | EVR does not require full trend confirmation even if the main switch is on. |
| Show Trend MA Line on Chart | On | Display the trend moving average line that the strategy uses for trend direction. Useful for visually verifying the trend filter. |
| Require structural trend? | Off | When ON: buy only during confirmed HH+HL sequences; sell only during LH+LL sequences. Very strict — prevents all counter-trend trades. |
| Avoid ranging market signals? (ADX) | Off | When ON: suppress all signals when the ADX indicator is below the ranging threshold. ADX < threshold = market is ranging (choppy, breakouts likely to fail). |
| Ranging threshold (ADX) | 14 | ADX below this = ranging. 14 = very strict (only suppresses the most sideways conditions). 18 = balanced. 25 = aggressive suppression. |
| Bypass retracement rules | On | **This is a key setting.** When ON: the retracement phase starts whenever a red candle closes below the prior green candle's low (for bear) or vice versa — regardless of whether the proper Initial Bar phase was established. Makes the system more reactive and fires more signals. When OFF: strict IB → retracement → breakout sequence is enforced. |

---

## Higher Time Frame Fair Value Gap (HTF FVG)

FVGs are price imbalances — gaps between candle wicks where price moved so fast that no trading occurred. These zones often act as magnets for price.

| Setting | Value | Explanation |
|---|---|---|
| Use HTF FVG for Signals | Off | When ON: signals only fire when price is inside a valid HTF FVG zone. Uses the FVG as a confluence filter. |
| Higher Time Frame | 1 | Which timeframe's FVGs to use. "1" = 1-minute HTF (same as chart, so all FVGs qualify). Higher values (5, 15, 60, 240) give fewer but more significant zones. |
| FVG Width Filter (ATR multiple) | 0.3 | FVGs smaller than 0.3× the 14-period ATR are ignored (too narrow to be meaningful). |
| UHV FVG Width Filter | 0.3 | UHV-specific FVG width threshold. |
| EVR FVG Width Filter | 0.3 | EVR-specific FVG width threshold. |
| Show Historical FVGs | On | Display all identified FVG zones on the chart as colored boxes. Useful for visualising where price imbalances exist. |

---

## Display

| Setting | Value | Explanation |
|---|---|---|
| Show Signal Labels | On | Shows a label at each signal bar with full trade details: entry price, SL, TP, lot size, risk %, win rate stats, and alert status. IMPORTANT: when OFF, labels are not created at all (not just hidden). If you turn this off and back on, labels for missed bars don't appear retroactively. Pine Script's label limit is 500 — with 700+ trades, only the most recent ~250 signals have both their labels visible. |
| Show Debug Labels | Off | Shows diagnostic labels: Initial Bar markers, POI touch events, setup resets. Helpful when troubleshooting why signals aren't firing or why a setup cancelled. Each debug label consumes from the 500-label budget — keep OFF in live trading to preserve budget for signal labels. |
| Show Stats Panel | On | Shows the performance dashboard in the chart corner: total trades, win rate, P&L, streak, today's stats, and the T1 settings export string. |
| Highlight signal candles | On | Draws colored boxes around the UHV candle (yellow), breakout candle (green/red), and EVR candle (orange) for each signal. Useful for visually reviewing which candles triggered the signal. |

---

## PineConnector Automation

PineConnector is a bridge service that receives TradingView webhook alerts and forwards them as MT5 trading commands.

| Setting | Value | Explanation |
|---|---|---|
| Send signals to PineConnector? | On | Master switch for live automation. When ON: alert strings are formatted as PineConnector commands. When OFF: alerts fire as plain text (for visual-only use or strategy testing). |
| PineConnector License ID | 87782869895254 | Your unique PineConnector account identifier. This must match your PineConnector dashboard exactly. Every alert string begins with this ID — PineConnector rejects alerts without it. Never share this publicly. |
| MT5 Symbol Name | XAUUSDm | The symbol name EXACTLY as it appears in MetaTrader 5's Market Watch. Exness uses "XAUUSDm" for gold mini-lots. Standard accounts use "XAUUSD". A mismatch causes MT5 to reject the order silently (no error in PineConnector, but no order in MT5). |
| Minimum lot size | 0.01 | Your broker's minimum lot size. Orders calculated below this floor are rounded up. Exness minimum = 0.01 lots. |
| MT5 pip size | 0.01 | The pip value in price terms for this symbol. XAUUSD: 1 pip = $0.01 (gold is quoted to 2 decimal places, e.g., 4840.55 — the last digit is 0.01). ETHUSD: 0.1. BTCUSD: 1.0. Used to convert pip counts to/from price. Wrong value here breaks all pip-based SL/TP calculations. |
| Signal→MT5 latency (ms) | 151,135,155,142,144 | Observed latencies from when TradingView fires the alert to when MT5 receives it (copied from PineConnector Bridge logs). Used to calculate the latency-window TP guard: if TP could be hit during transit time, the alert is suppressed or rebased. Update these values periodically from your PineConnector logs. |
| Stop Loss format | Price | How SL is sent in the alert. **"Price"** = `sl_price=4846.43` (absolute price level). **"Pips"** = `sl_pips=50` (distance from fill in pips). CRITICAL: always use `sl_price=` for absolute price, never bare `sl=` — PineConnector interprets `sl=VALUE` as pips, causing catastrophically wrong SL placement (previously caused a ~$895 loss). |
| Take Profit format | Price | How TP is sent in the alert. **"Price"** = `tp_price=4840.99`. **"Pips"** = `tp_pips=50` (MT5 places TP at fill_price ± N pips). "Pips" mode is immune to Error 4756 because MT5 calculates TP from the actual fill price. "Price" mode can cause Error 4756 if price moves between signal and fill. |
| Order type | Market | **"Market"** = instant fill at current price (IOE mode). **"Limit"** = pending order at the entry price. Limit orders never cause Error 4756 but may not fill if price blows through the level. |

### Error 4756 — "Invalid Stops" Explained

Error 4756 occurs when MT5 receives an order where SL or TP is invalid:
- **SELL trade**: TP must be BELOW the fill price. If TP ≥ fill price → Error 4756.
- **BUY trade**: TP must be ABOVE the fill price. If TP ≤ fill price → Error 4756.

This happens in IOE mode because: Pine calculates TP at the IOE trigger price, but by the time MT5 fills the order (150–250ms later), price has moved. If TP was already close to entry (e.g., a structural floor only $0.02 below entry), any downward slippage puts the fill price below the TP → invalid.

**Fixes implemented:**
1. Direction guard: if TP is on the wrong side of entry (e.g., structural floor above entry for sell), immediately fall back to dollar TP.
2. IOE spread guard: if TP is within spread distance ($0.30) of the close at signal time, rebase TP from the current close. This catches "TP too close" cases where slippage can push fill past TP.
3. Using `tp_pips=50` (Pips mode) eliminates this entirely — MT5 places TP relative to actual fill price.

---

## Optimize

| Setting | Value | Explanation |
|---|---|---|
| Maximize Trades | Off | Removes all cooldowns and optional filters. Fires on every technically valid setup to generate maximum signal history for analysis. Use for backtesting to see what was possible — not for live trading (over-trades). |
| Developer mode | On | Each signal label shows two extra lines: (1) the 16-bit condition bitmask showing which filters were active and passed at signal time; (2) the full PineConnector alert string that was sent. Essential for debugging Error 4756, verifying SL/TP values, and understanding exactly which conditions fired the signal. The bitmask format is documented separately. |

---

## Bitmask Reference (Developer Mode)

When Developer mode is ON, each signal label shows a 16-character binary string appended to the comment, e.g., `#790#1100000011010000`.

| Bit | Meaning | 0 = | 1 = |
|---|---|---|---|
| 0 | Direction | Buy | Sell |
| 1 | Entry mode | Bar close | IOE (instant) |
| 2 | Strategy (low bit) | — | — |
| 3 | Strategy (high bit) | 00=UHV, 01=2BR, 10=EVR | 11=EVR-Wick |
| 4 | Strict trend required | Off | On |
| 5 | Strict trend passed | No | Yes |
| 6 | Sweep required | Off | On |
| 7 | Sweep confirmed | No | Yes |
| 8 | Pre-offset active | No | Yes (uPBD > 0) |
| 9 | Co-exist path | No (pre-offset hit) | Yes (fired at breakout level) |
| 10 | Trend direction | Downtrend | Uptrend |
| 11 | In session | No | Yes |
| 12 | Volume filter active | Off | On |
| 13 | Volume filter passed | No | Yes |
| 14 | OC (opposite candle) filter | Off | On |
| 15 | OC filter passed | No | Yes |

Example: `1100000011010000` = Sell, IOE, UHV strategy, no strict trend, no sweep, pre-offset active, co-exist path taken, downtrend, in-session, no vol/OC filters.

---

## Alert String Format

Every PineConnector alert follows this format:
```
{LicenseID},sell,XAUUSD,vol_lots=0.05,sl_price=4846.43,tp_price=4840.565,comment=UHV@4840.59_20:09_#{TradeNum}#{Bitmask}
```

- `sl_price=` and `tp_price=` = absolute price levels (NOT `sl=` or `tp=` which mean pips)
- Comment encodes: strategy name, entry price, signal time, trade number, 16-bit bitmask
- `vol_lots=` = position size in lots (calculated from % risk / dollar risk)

---

## T1 Settings Export String

The stats panel (row 18) shows a pipe-delimited string of all ~120 input values. Copy this string and paste it to Claude to restore settings after a TradingView reset. Format: `T1|Account|POI|UHV|2BR|EVR|Trend|HTF|PC`
