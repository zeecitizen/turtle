
on 5 minute, or max 15 minute timeframe: 

LONG: 

Entry: 

If a PINBAR (like a thumb pin) or MARIBUZU is made on 9 EMA .. we wait for next candle or next to next to candle to break the high point of pinbar / maribuzu ..


Exit / Take Profit:  If a candle forms that touches the 50 EMA .. 

In case of TP touched 50 EMA -> 
1. Activate Trailing SL at 3 USD less than current price of the market
2. Set TP to next liquidity (last resistance), call this the TP2
3. If we reach the TP2, in this case set the TP further to TP3 where we define TP3 as: last to last resistance <= In essence we'll exit at the Trailing SL


Update the long rule to the following: 

in case of long entry at time of entry if the 50 EMA is below our entry, then instead of having 0 tp (what we have currently), we should have the first target as the TP which is the next resistance level .. because in the trade shown the tp was 0

Stop Loss Management: the SL is set to 20 pips below the pinbar / maribuzu 

Trailing Stop: when we reach TP 1 .. it should activate a trailing stop to 30 pips of the current price. 

Conditions: skip the move if within 2 candles teh pinbar / maribuzu high is not broken



SHORT: 

Entry: If a PINBAR (like a thumb pin) or MARIBUZU is made on 50 EMA .. we wait for next candle or next to next to candle to break the low point of pinbar / maribuzu ..

Exit / Take Profit: Till next liquidity (last support)

Stop Loss Management: the SL is set to 20 pips above the pinbar / maribuzu 

Conditions: skip the move if within 2 candles teh pinbar / maribuzu low is not broken


Also test if its favorable to: 

if our profit is above 3 USD, then we breakeven the trade, setting SL to Entry till we take our profit 

we don't want to trade in choppy / range conditions.. 



---

## Fix log — TradingView indicator (pine/saad_strategy.pine)

Appended by Claude at Zee's request. Newest at the bottom. Chart numbers are a bar-close sketch on
OANDA XAUUSD; only the MT5 Strategy Tester can confirm a change.

**2026-10-11 — clearer labels**
- Entries show as a solid **▲ BUY #n / ▼ SELL #n** tag (blue / magenta, never a candle colour); exits as a dark
  **EXIT #n ±$** tag (green win / red loss). Explanations moved into the hover tooltip.
- MT5-style **dotted line from each entry to its exit**, with a ✕ at the exit price.
- Setup and skip tags made small; old SL/TP notes removed once a trade closes.
- New input "Draw labels only up to this time" (for screenshots of old trades; TradingView keeps only 500 labels).
- Colour inputs removed again (constants): they broke every settings change made through the API ("Can't parse pine").

**2026-10-11 — lots set to 1** (default and on the chart). Results are now shown at 1 lot.

**2026-10-11 — purification page** (`monitor/purification/`, http://127.0.0.1:8766/): one screenshot per setup with
OK / NOT OKAY + comment + Save, an orange box and "THIS SETUP #n" arrow on each. Currently the last 50 M15 setups.

**2026-10-12 — stop loss in $ instead of pips.** "Stop this many $ beyond the pin / marubozu" ($1 = 10 pips).
The chart was set to $3.00 = the old 30 pips; results unchanged (348 trades, 48%, +$52,666).

**2026-10-12 — trailing stop made to follow the rule above** ("when we reach TP 1 .. trailing stop to 30 pips of
the current price"):
1. Bug: a LONG with no TP (its exit EMA already below the entry) started trailing at the entry, pulling the stop
   off the candle at once. Now it keeps the stop below the pin / marubozu and exits on that stop or a close below
   the EMA — it never trails, because there is no TP to reach.
2. New option "When the TP is reached … lock the stop at: **Trail from the TP price**" — at TP the stop jumps to
   30 pips behind price, then trails. (Started by another Claude session; it did not compile until fixed here.)
3. Chart set to: trail by "X pips behind the best price", X = 30, lock = "Trail from the TP price".

| M15, 1 lot | Trades | Win rate | Net |
|---|---|---|---|
| Before | 330 | 48.5% | +$50,315 |
| Bug fix only (stop locked at the TP) | 301 | 45.5% | +$42,498 |
| Bug fix + the rule (30 pips behind price) | 300 | 38.7% | +$36,216 |

The rule as written lowers the win rate: a trade that reached its TP can give back 30 pips.

**2026-10-12 — several trades at once.** New inputs "⑪ Max open trades" (default 1 = as before) and "Allow two
trades in the same direction". Each open trade keeps its own stop, target and trailing stop. PineConnector alerts
are switched off above 1 (its close / move-stop messages act on all longs or all shorts at once).

| M15, 1 lot, current settings | Trades | Win rate | Net | PF |
|---|---|---|---|---|
| Max 1 (as before) | 300 | 38.7% | +$36,216 | 1.23 |
| Max 2 | 467 | 37.9% | +$51,189 | 1.20 |
| Max 3 | 554 | 38.8% | +$57,601 | 1.19 |
| Max 2, at most one LONG + one SHORT | 396 | 38.9% | +$48,691 | 1.23 |

More trades add net dollars at a similar win rate but a lower profit factor, with 2–3× the money at risk at once.
The chart is left on Max 1. The MT5 EA has neither "trail from the TP price" nor several trades yet.

**2026-10-12 — review of the several-trades code** (tested at Max 2 on M15, Sep 24–25 overlaps)
- Works: each open trade keeps its own stop / target / trail and exits on its own; the NOW panel lists every open
  trade; Max 1 gives exactly the old results.
- Fixed: once a stop moved (locked / trailing / breakeven) its note lost the trade number, so with two trades the
  notes could not be told apart → now "#447 TRAIL SL …".
- Fixed: the "busy" count also counted choppy candles that a same-direction block skipped (count only).
- Not a code bug, a design question: **opposite trades can be open together** (a LONG inside a SHORT: #444/#445,
  #454/#455/#456, #470/#471, #473/#474 — several lost on both sides). "Same direction OFF" does not stop this.
- Not a code bug, a design question: **two setups at the same level stack into a double-size trade** — #447 and #448
  (setup lows 4282.305 / 4282.31) both entered at 4282.11 and exited together, +$2,255 each.
- Note: the panel totals cover the candles TradingView has loaded; scrolling back loads older ones and changes the
  totals. Compare settings without scrolling in between.

**2026-10-14 — new indicator `pine/saad_15min.pine` = mirror of Saad_strategy_15min v1.22** (Zee: *"ensure that our
indicator on tradingview has everything exactly ditto as it is in terms of its numerical settings and setup lifecycle
as our Saad_15_min EA strategy"*)
- A NEW script, not an edit of `saad_strategy.pine` (that one mirrors the old M5 EA, and TradingView keeps each chart's
  saved inputs by position, so new defaults in the old script would never reach the chart).
- Every EA default copied, with a table in the file header: pin 0.45 / 0.60 / 0.20, marubozu 0.53, hammer 2.5 / 0.50,
  range 0.55x ATR, longs on the 9 (exit 50) or the 50 (exit 9), shorts on the 9 EMA, break 1 candle by 2 pips, stop 35
  pips, max risk $15, chop ER(16) 0.11, CTC at 75%, half closed at TP1, $2 trail after TP1, TP2 / TP3 = next swing,
  no-TP1 longs trail 2x ATR from the entry, losers shut 3 min before the 4:59 PM New York close, 1 lot.
- Exactness: ATR is MT5's simple average of true range (Pine's ta.atr is Wilder's: PXBT 04:15 = 8.556 vs 6.482); ER,
  last support / resistance use the EA's own formulas (not ta.pivotlow); the LONG EMA target is the live EMA of the
  forming candle like the EA's Ema(x, 0); BUYs fill at the ask (bid + spread input, PXBT 0.17); the 1-candle break
  keeps the EA's gap hole (report §37), as the EA does.
- Dropped: PineConnector alerts and several-trades-at-once (the EA runs one position).
