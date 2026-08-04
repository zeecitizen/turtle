# NS/ND overnight — what the data says

**For Zee, 2026-08-04 morning.** You went to sleep saying you'd lost hope. Here are numbers
instead of reassurance. Read the caveats at the bottom before you feel anything about the top.

---

## 1. Your rules, exactly as you stated them, do not fire often enough to matter

| | trades | over | WR | net |
|---|---|---|---|---|
| every gate literal | **6** | 37 tick-days | 17% | **−$67.70** |

Six trades in thirty-seven days. Even at a perfect win rate that is not an income, and it is far
too few to ever prove anything. **That is not your method failing — that is my implementation of
your words being stricter than your eyes are.**

## 2. One number of mine was the strangler: the dead-volume threshold

You said *"pichli do candle se chhoti — half se bhi kam"*, so I coded `< 0.50 ×` each of the
previous two. Loosening it — still "clearly smaller than the last two", just not literally half:

| threshold | trades | WR | net | out-of-sample |
|---|---|---|---|---|
| 0.50 (literal) | 6 | 17% | −$67.70 | 1 trade, −$62.60 |
| 0.60 | 17 | 24% | +$1,245.90 | 4 trades, +$143.80 |
| **0.75** | **36** | **28%** | **+$1,173.95** | **11 trades, 45% WR, +$801.75** |

## 3. The best configuration found

`dead-volume 0.75` + `20 bars allowed between the candle and its breakout` + `no FVG gate`

| | trades | WR | net | $/day |
|---|---|---|---|---|
| all 37 days | 61 | 28% | +$1,699.16 | +$46 |
| **held-out 15 days** | **20** | **45%** | **+$1,255.95** | **+$84** |

One position at a time, stop always resolved before target, 0.2pt spread charged per trade,
0.10 lots. The out-of-sample half is the half no parameter was chosen on.

---

## The thing I will not decide for you

**Dropping the FVG gate improves every measure — and it is one of your own four failure modes.**

You told me a no-supply fails when *"there's no FVG tap"*. The data over 37 days disagrees: the
FVG requirement costs trades without improving the ones that remain. Two possible readings:

* my FVG test is wrong — it demands an exact 3-candle tap on M1, where you draw a grey box by
  eye on M15/H1 and accept "close enough". Then the gate is fine and my code is not.
* or the tap matters for the setups you take by hand, and is not mechanisable.

**I am not overriding your rule on the strength of 61 backtested trades.** The best config above
has it off; the runner-up (`0.60 + window 20`, FVG ON) still makes **+$444.90 out-of-sample on 6
trades**. Your call which we test live.

## What is still wrong with these numbers

1. **n is small.** 20 out-of-sample trades. Not 200.
2. **Bar-resolution fills.** Entry at the close, exits checked against bar highs and lows. Real
   fills are worse; slippage is not modelled, only spread.
3. **28% win rate.** This edge lives entirely on the 4:1 payoff. A few percent of slippage on
   the winners takes it apart — which is exactly what killed the exit in every previous version
   ([[exit-is-the-edge]]).
4. **I chose the values I then tested.** The walk-forward split protects against the worst of
   that, not all of it ([[v299-92pct-backtest-caveats]]).

## What I would do next, if you agree

Run it live on the new $5,000 demo at **0.10 lots** — about **$5–15 risk per trade**, a third of
one percent. Not because the backtest is convincing, but because thirty live fires will settle
in a fortnight what another thousand backtests never will.

**Live receipts, not another table. That is the only thing that has ever been true here.**

---

*Files: `nsnd_detector.py`, `nsnd_overnight_study.py`, `nsnd_walkforward.py`,
`_nsnd_overnight.md`, `_nsnd_walkforward.md`.*
