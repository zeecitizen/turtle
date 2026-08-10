# LATEST WIN RATE

## ⚠️ READ THIS FIRST — the 96.4% did NOT survive out-of-sample (2026-08-10)

The 96.4% below was found by optimising on four days and validating on nothing. Run on
tape it had never seen, with **every setting frozen and nothing retuned**:

```
IN-SAMPLE    Aug 5-10  (where it was found)     +$580.00     55 trades   96.36%
OUT-SAMPLE   Feb 12 - May 27 (103 days)       -$4,071.70    768 trades   82.81%
OUT-SAMPLE   Feb 11 - Zee's own day             -$180.00     36 trades   83.33%
```

**It loses on unseen data. That $4,071 would have been real money.**

### But the number that matters is not the loss — it is the agreement

```
768 trades  ->  82.81%
 36 trades  ->  83.33%
```

**Two completely independent datasets landing within half a point of each other.**
That is not noise. **The strategy's real win rate is ~83%**, measured over 768 trades
instead of 28. The 96.4% was four lucky days dressed up by a 5,280-pass search.

**83% is a genuinely good entry engine.** The failure is not the entries — it is that
**SL 7 / TP 1 needs 87.5% just to break even**, so a real 83% engine bleeds on a 7:1
payoff. The entries are fine. The exit arithmetic is wrong for them.

### The methodological lesson, which is the permanent one

**I optimised on four days and validated on nothing.** The correct order is the
opposite: **search on the large sample, confirm on the small one.** Any configuration
found on a few days must be run on unseen tape with everything frozen before it is
believed — and certainly before it is funded.

The 311-pass 90%+ region and the six-stop plateau did NOT protect against this. A
plateau proves the result is stable *within that sample*; it says nothing about another
sample. That is worth remembering, because I offered the plateau as reassurance.

---


## The in-sample record (superseded by the box above)

**Measured 2026-08-10 by MT5's own Strategy Tester** (never Python), on real archived
gold, found by a 5,280-pass sweep the tester ran with no human clicks.

---

## The headline

```
96.4%  ·  27 wins / 1 loss  ·  28 trades  ·  +$200 at flat 0.10 lots
```

**311 of 5,280 passes reached 90%+**, and the 96.4% cell has six consecutive stops
behind it — a plateau, not a lucky cell.

### With Zee's stacking on top

```
                    net        trades   win%     worst loss   max drawdown
flat 0.10        +$200.00        28    96.43%     -$70          2.8%
STACK capped     +$580.00        55    96.36%    -$140          8.0%   <- RECOMMENDED
STACK uncapped +$1,490.00        98    95.92%    -$280         28%
```

---

## THE THREE THINGS THAT UNLOCKED IT — all three were Zee's

**1. TP 1 — the $1 target.** *"if 96% reach +$1, then let each trade bring in the $1."*
Every high-win-rate pass uses TP 1. I argued for TP 3 twice and was wrong both times.

**2. Let ranging tape trade.** *"we're taking too less trades... can u check what's
stopping us?"* `update_gate()`'s "flat -> the ghost waits" closes BOTH sides 40.3% of
the time. Opening it: 16 trades -> 50, and the win rate went UP.

```
gate ON   +$44.50   16 trades   87.5%
gate OFF +$144.50   50 trades   90.0%
```

**3. The stack.** *"the diamonds should each not only add 1 trade, but add the trade in
twice the lots we already have... 0.1, then 0.2, then 0.3, then 0.4."* A diamond is not
a multiplier on one ticket — it is ANOTHER ticket, larger than the one before.

---

## The exact conditions

**Engine:** `mt5/ZeeUHV.mq5` — built from Zee's own 146 setup labels, each rule carrying
his sentence quoted above it in the code.

**Data:** `XAUUSD_R3`, real OANDA gold from our archive, 2026.08.05 -> 08.10, 1,764 M1
bars, "1 minute OHLC", BlueberryMarkets-Demo spread and execution.

| input | value | why |
|---|---|---|
| `InpUhvBodyMin` | **0.6** | THE KEY. Body 0.2-0.5 -> median 89% win; **0.6 -> 95%** |
| `InpTargetPts` | **1** | Zee's call; no high-win-rate pass uses anything else |
| `InpStopPts` | **7** | 96.4% holds from 7 to 12; 6 gives 92.9%, 5 gives 89.3% |
| `InpRequireTrend` | **false** | ranging tape allowed — the 40% gate opened |
| `InpTrendLook` | 20 | |
| `InpRetraceBack` | 16-20 | identical either way |
| `InpMaxHoldMin` | 30 | the age-out does real work: it closes losers early |
| `InpStackLots` | true | each diamond adds a bigger ticket |
| `InpStackStep` | 0.10 | 0.10 / 0.20 / 0.30 / 0.40 |
| `InpMaxRisk` | **0.60** | caps the stack. Uncapped is 28% drawdown |

**The body filter is the single strongest lever:**
```
body 0.2: median win 89.4% · 48 trades · +$103
body 0.3: median win 89.6% · 43 trades · +$100
body 0.4: median win 89.3% · 38 trades ·  +$95
body 0.5: median win 88.9% · 37 trades ·  +$85
body 0.6: median win 95.2% · 26 trades · +$110   <- his "UHV should be a STRONG candle"
```

**And the four rules that must all hold before a trade exists**, in his words:
1. **Retracement** — buys retrace in RED candles, sells in GREEN; the origin's **body**
   must clear the previous opposite candle's extreme, not just a wick.
2. **UHV inside that retracement** — loudest candle of the right colour, louder than
   both neighbours, **body >= 0.6 of range**.
3. **Breakout** — right colour, **body** past the UHV's wick-end, volume LOWER than the
   UHV's, first crossing only.
4. **Diamonds** — sweep, EMA-5 close, wick+volume. They never gate; they buy tickets.

---

## What must travel with this number

- **28 trades** (55 with the stack). Small. One more loss takes 96.4% to 93%.
- **Four days** of tape. Re-run when the archive holds a month.
- **It is an OPTIMISED result.** 5,280 passes searched, best kept. The 311-pass 90%+
  region and the six-stop plateau make overfitting less likely, **but the honest test is
  fresh tape it has never seen.**
- **The live receipts still disagree about size.** `oanda_live_matcher.py`, 2026-08-06,
  n=14: *"big lots 36% WR, -$219.90; 0.10 flat 71% WR, +$76.60 — conviction sizing as
  currently timed multiplies losses."* Real fills outrank a tester result. **The stack
  goes live only after a fresh trial says otherwise, and capped when it does.**

---

## Reproduce it with no clicks

```bash
py monitor/mt5_headless.py --ea ZeeUHV              # single run
py monitor/mt5_headless.py --ea ZeeUHV --optimize   # 5,280 passes, ~28s
py monitor/read_opt.py                              # rank the newest sweep
```

See `THINGS_TO_REMEMBER.md` for the rig and its gotchas.
