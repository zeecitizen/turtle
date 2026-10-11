# Optimal settings — Saad Strategy indicator (TradingView)

*Saved 2026-10-11 from Zee's chart (TradingView "Save settings" list), indicator
`pine/saad_strategy.pine` (title "Saad Strategy v3.20 — EMA 9/50 pin & marubozu"),
OANDA:XAUUSD, 5-minute chart.*

> **Status: chosen by eye on the TradingView chart (about two weeks of bars, judged on
> closed candles). NOT tested in the MT5 Strategy Tester.** The EA (`mt5/Saad_strategy.mq5`
> v3.20) does not yet have several of these options (trailing stop, "either EMA",
> long-exit-on-close, hammers). Until the EA carries them and MT5 tests them on Axi,
> treat this as a hypothesis — CLAUDE.md: only MT5 or live fills promote a setting.

## The settings

Values in **bold** differ from the indicator's defaults (= the EA's MT5-tested v3.20).

| # | Section | Setting | Value | Default |
|---|---|---|---|---|
| 1 | ① Setup candle | Pin: long wick at least this share of the candle | **0.35** | 0.60 |
| 2 | | Pin: body at most this share of the candle | **0.6** | 0.30 |
| 3 | | Pin: short wick at most this share | **0.2** | 0.25 |
| 4 | | Pin must point the trade way (thumb pin) | **OFF** — any pin, the EMA decides | ON |
| 5 | | Accept a marubozu too | ON | ON |
| 6 | | Marubozu: body at least this share | **0.7** | 0.80 |
| 7 | | Candle at least × ATR(14) | 0.5 | 0.5 |
| 8 | ① …made on the EMA | Fast EMA length | 9 | 9 |
| 9 | | Slow EMA length | 50 | 50 |
| 10 | | LONG setups must be on | **Either EMA** | 9 EMA |
| 11 | | SHORT setups must be on | **Either EMA** | 50 EMA |
| 12 | | "On the EMA" means | Candle touches the EMA | same |
| 13 | | Touch tolerance (pips) | 0 | 0 |
| 14 | | LONG only when the exit EMA is above the candle | **OFF** | ON |
| 15 | ② Wait for the break | Candles allowed to break the high / low | 2 | 2 |
| 16 | | Break must clear it by (pips) | 0 | 0 |
| 17 | | Break must be a candle CLOSE | OFF | OFF |
| 18 | ③ Entry | Allow LONG trades | ON | ON |
| 19 | | Allow SHORT trades | ON | ON |
| 20 | ④ Stop loss | Pips beyond the pin / marubozu | **34** | 25 |
| 21 | ⑤ Take profit | LONG exit | **Candle CLOSES at / beyond the 50 EMA** | Candle touches the 50 EMA |
| 22 | | LONG: take profit X pips before the EMA | 0 | 0 |
| 23 | | SHORT "last support" swing size (candles each side) | 3 | 3 |
| 24 | | SHORT: take profit X pips before the support | 0 | 0 |
| 25 | ⑥ Breakeven | Move stop to entry after $ | 0 (off) | 0 |
| — | | *(an extra "0" appears here in the list — see note 1)* | 0 | — |
| 26 | | Measure the $ as | Price moved $X | same |
| 27 | ✖ Skip filters | Skip choppy: efficiency ratio below | **0.1** | 0.20 |
| 28 | | Efficiency ratio length | **16** | 14 |
| 29 | | Only trade between these hours | **OFF** | ON |
| 30 | | From hour (server) | **5** (not used while hours are OFF) | 8 |
| 31 | | To hour (server) | **18** (not used while hours are OFF) | 17 |
| 32 | | Server timezone | GMT+3 | same |
| 33 | 🎨 Display | Lots for the $ figures | 0.1 | 0.1 |
| 34 | | Contract size | 100 | 100 |
| 35 | | Show skipped setups | ON | ON |
| 36 | | Show stats panel | ON | ON |
| 37 | | Show the numbered rules box | ON | ON |
| 38 | ⑦ Trailing stop | Use a trailing stop | **ON** | OFF |
| 39 | | Apply it to | **Both** | LONG only |
| 40 | | Let winners run (trail from the TP instead of exiting) | ON | ON |
| 41 | | Trail the stop by | Low / high of the last N candles | same |
| 42 | | N candles | **6** | 3 |
| 43 | | X pips | 30 | 30 |
| 44 | | ATR multiple (not used in "last N candles" mode) | **1.3** | 1.5 |
| 45 | | Start trailing after X pips | 0 | 0 |
| 46 | ⑧ LONG rule | Which EMA is the setup / the exit | **Both** (9 → exit 50, and 50 → exit 9) | 9 EMA setup → exit at 50 EMA |
| 47 | ⑨ Hammers | Also accept hammers / shooting stars | *not in the list — see note 2* | OFF |
| 48 | | Hammer: long wick at least × the body | **3** | 2 |
| 49 | | Hammer: opposite wick at most this share | **0.5** | 0.10 |

## Notes

1. **One value doesn't line up.** The list has 49 values and the indicator has 49 settings,
   but between "breakeven $ = 0" and "Price moved $X" there is one more "0" than there are
   settings, and the hammer ON/OFF switch (a yes/no setting) has no ON/OFF in the list.
   Everything before and after lines up exactly by type, so the most likely reading is that
   the hammer switch was exported out of place. **Check the ⑨ Hammers switch on the chart**
   and correct row 47.
2. **Hammer settings 3 and 0.5:** a wick of 3 × the body is stricter than the classic 2, but
   allowing the opposite wick to be half the candle is very loose — such a candle is closer to
   a spinning top than a hammer. Worth a second look if hammers are switched on.
3. **Hours 5–18 are switched off** (row 29), so the bot trades around the clock; the MT5 tests
   found the 08–17 window was the single biggest improvement (+$2,112 → +$6,056).
4. **Choppy filter at 0.1** is looser than the tested 0.20 (0.20 lifted PF 1.27 → 1.57 in MT5).
5. **Stop 34 pips** is beyond the 25–30 plateau MT5 found (35 pips was already worse than 30).

## How to restore them

TradingView: double-click the indicator → **Inputs** → set the bold values above (or use
**Defaults → Save as default** once they are entered). Then **save the chart layout** (Save
button on the top bar) — unsaved layouts revert to the last save when TradingView restarts.

## What it would take to trust them

Port the missing options into the EA (trailing stop with "let winners run", either-EMA setups,
long exit on close, the inverse long rule, hammers) and run this exact set against the v3.20
baseline in the Axi Strategy Tester (real ticks, Jan 1 → Oct 8).
