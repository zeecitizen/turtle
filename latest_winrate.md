# LATEST WIN RATE — 87.5%, and exactly what it took

**Measured 2026-08-10 by MT5's own Strategy Tester** (not Python), on real archived
gold, over a 5,280-pass sweep the tester ran by itself.

---

## The headline

```
87.5%  ·  14 wins / 2 losses  ·  16 trades  ·  +$44.50 at flat 0.10 lots
```

**Nothing in 5,280 passes reached 90%.** 87.5% is the ceiling we have actually
demonstrated, and **24 separate parameter settings share it** — a plateau, not a lucky
cell, which is the shape that means it is real rather than fitted.

---

## The exact conditions under which 87.5% happens

**Engine:** `mt5/ZeeUHV.mq5` — the detector rebuilt from Zee's own 146 setup labels,
where each rule carries his sentence quoted above it in the code.

**Data:** `XAUUSD_R3` — real OANDA gold bars from our own archive, 2026.08.05 → 2026.08.10,
1,764 M1 bars, "1 minute OHLC" modelling, BlueberryMarkets-Demo spread and execution.

**Settings:**

| input | value | note |
|---|---|---|
| `InpStopPts` | **7** | the plateau runs 6–11; 12 falls off a cliff to 0% |
| `InpTargetPts` | **1** | Zee's call. Every one of the 24 best passes uses TP 1 |
| `InpUhvBodyMin` | **0.2** | "UHV should also be a strong candle" |
| `InpTrendLook` | 40–60 | both work identically |
| `InpRetraceBack` | 16–20 | both work identically |
| `InpMaxHoldMin` | 30 | age-out; it is doing real work (see below) |
| `InpPivot` | 2 | swing strength for the HH/HL trend read |

**And the rules that must all be true before a trade exists at all** — his words:

1. **Trend, by structure.** HH+HL to buy, LH+LL to sell. *"we cannot sell in an uptrend,
   we only buy in an uptrend."* Ranging tape disqualifies the setup entirely.
2. **A valid retracement, and its origin.** Buy setups retrace in RED candles, sells in
   GREEN. The origin candle's **body** must clear the previous opposite candle's extreme
   — *"the body of green candle doesnot break above the last red."* A wick does not count.
3. **The UHV inside that retracement.** Loudest candle of the right colour, louder than
   both neighbours, body ≥ 0.2 of range. Searching only INSIDE the retracement is what
   most of his 146 corrections were about.
4. **The breakout.** Right colour, **body** past the UHV's wick-end, volume LOWER than the
   UHV's, and only the FIRST crossing counts.

---

## The shape of the plateau

```
   SL   TP   win%   profit
    6    1   87.5   +$13
    7    1   87.5   +$44   <- best
    8    1   87.5   +$34
    9    1   87.5   +$24
   10    1   87.5   +$14
   11    1   87.5    +$4
   12    1    0      -$16   <- the cliff
```

The win rate is flat across stops 6–11 and across both trend/retrace settings; only the
profit changes, because a wider stop costs more on the two losers. **The stop must sit
between 6 and 11 points.** Tighter loses winners, wider falls off the cliff.

**Note SL 7 / TP 1 is a 7:1 risk ratio, which "should" need 88% to break even — and it
profits at 87.5%.** That is the 30-minute age-out doing real work: some losers close
early rather than paying the full stop.

---

## What must travel with this number

- **16 trades.** One more loss makes it 81%. The plateau is reassuring; the sample is not.
- **Four days** of tape. The archive grows every minute now; re-run this when there is a
  month.
- **$11/day at 0.10 lots.** Real, but not yet bread.
- **This is an OPTIMISED result.** 5,280 passes were searched and the best was kept. The
  plateau makes overfitting less likely but does not eliminate it. **The honest test is
  fresh tape it has never seen.**

---

## Diamonds (conviction sizing) — CONFLICTING EVIDENCE, do not ship yet

Same 16 setups, sized by the laws of conviction (1/2/3 clicks) instead of flat 0.10:

```
flat 0.10     +$44.50   87.5%   largest loss  -$70
diamonds ON   +$73.50   87.5%   largest loss -$229.80
```

The tester says diamonds add **+65% profit at the same win rate.**

**But the live receipts say the opposite.** From `oanda_live_matcher.py`, recorded
2026-08-06 after a real trial (n=14): *"big lots 36% WR, -$219.90; 0.10 flat 71% WR,
+$76.60 — conviction sizing as currently timed multiplies losses (diamonds align late,
when trends are old). Cap returns to 0.10."*

**Live evidence outranks a tester result.** Diamonds stay OFF for live until a fresh
trial with real fills says otherwise. The tester number is a hypothesis, not a promotion.

---

## How to reproduce this, with no clicks

```bash
py monitor/mt5_headless.py --ea ZeeUHV              # single run
py monitor/mt5_headless.py --ea ZeeUHV --optimize   # the whole 5,280-pass sweep, ~18s
```

See `THINGS_TO_REMEMBER.md` for the rig and its four gotchas.
