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




## 💎 DIAMONDS AT FIXED 0.10 — 6x the profit, win rate unchanged, green on ALL THREE

Zee, 2026-08-10: *"keep the lotsize fixed at 0.1 for all diamonds etc.. and then check
for me if we can make profit?"*

**Yes.** Diamonds buy MORE TICKETS, never bigger ones — every ticket stays 0.10.

```
                     103 days              Aug 5-10 (UNSEEN)     Feb 11 (UNSEEN)
no diamonds     441 tr  88.44%  +$139       8 tr  87.5%  +$51     7 tr 100%  +$70
diamonds @0.10 1628 tr  88.64%  +$821      30 tr  86.7% +$184    26 tr 100% +$260
```

**Six times the profit. The win rate does not move (88.44% -> 88.64%). Profitable on
every dataset including both the optimiser never saw.**

### And it is NOT just leverage — the conviction laws genuinely pick better trades

```
flat 0.30 lots   +$416   drawdown 40%
diamonds @0.10   +$821   drawdown 45%
```

Nearly double the money for barely more risk. If diamonds were only size, those two
lines would match. They do not, so Law 1 (the sweep), Law 3 (the EMA-5 close) and Law 5
(wick and volume) are selecting, not merely amplifying.

**The open problem: 45% drawdown over 103 days is not survivable on a $500 account.**
`InpMaxRisk` caps total lots per setup and the right cap is not yet measured.

### Lot size is a pure multiplier — it cannot manufacture an edge

Zee asked whether a bigger lot magnifies the small $1 win against the high win rate.
Arithmetically yes, and the win rate is unchanged by size — but the losses scale in
exactly the same step:

```
  lots     trades   win%      profit     max drawdown
  0.10      441    88.44%    +$138.60    15% of account
  0.20      441    88.44%    +$277.20    28%
  0.30      441    88.44%    +$415.80    40%
  0.50      441    88.44%    +$693.00    60%
```

**The strategy is not the limit. The account size is.** At $500 the safe size is about
0.01-0.02 lots. Surviving a 15% dip at 0.10 lots needs roughly $4,400.

---

## 🔍 WHY WE TAKE 26 TRADES ON FEB 11 AND HE TOOK 69

Measured on Feb 11 itself. **The position limits are NOT the constraint** — removing all
of them changes nothing at all:

```
as validated (MaxOpen 1, cooldown 3)   26 trades · 100.00% · +$260
MaxOpen 4, cooldown 1                  26 trades · 100.00% · +$260
MaxOpen 10, no cooldown                26 trades · 100.00% · +$260
+ hold 10 minutes instead of 30        26 trades · 100.00% · +$260
+ body rule 0.5 -> 0.3                 41 trades ·  90.24% ·  +$10   <- profit collapses
```

**26 is simply how many lawful UHV setups exist on that day.** Loosening the body rule
finds 41, and the extra 15 destroy the profit — $260 down to $10.

**So his other 43 trades were not this pattern.** They were the other strategies the
June taxonomy identified in that day — sweep, NS/ND, momentum, and un-mechanizable tape
reading. See [[project_feb11_strategy_taxonomy]]. Chasing 69 with THIS engine means
taking rubbish; the way to 69 is more ENGINES, not looser rules.

**And 26 trades at 100% with +$260 on his own day is the best single-day result this
project has ever produced.**

---

## ✅ THE CONFIRMED RESULT — 88.4%, and it survives unseen tape

Found the honest way round: **searched on 103 days (3,600 configs, 440+ trades per
pass), then validated on tape the search never saw.**

```
SL 9  ·  TP 1  ·  UhvBodyMin 0.5  ·  TrendLook 20  ·  gate ON (trend required)  ·  flat 0.10

                        net      trades   win%     maxDD
103 days (in-sample)  +138.60      441    88.44%   14.95%
Aug 5-10   (UNSEEN)    +51.10        8    87.50%    1.64%
Feb 11     (UNSEEN)    +70.00        7   100.00%    1.40%
```

**Profitable on all three. The win rate holds at 87-88% across every dataset**, and
88.44% of it rests on 441 trades — the largest sample this project has ever measured.

### What FAILED the same test, and why it matters
```
                                103 days    Aug 5-10    Feb 11
B  SL4/TP5 body0.7 gate OFF     +$1074      -$171       -$120
C  SL6/TP5 body0.7 gate OFF      +$878       -$21       -$146
```
Both looked far richer in-sample and collapsed on contact with new tape — exactly as the
96.4% did. **In-sample profit is not evidence. Surviving unseen tape is.**

### With Zee's capped stack
```
103 days + stack   +415.80    882 trades   88.44%   maxDD 40%   <- drawdown too high
Aug 5-10  + stack  +153.30     16 trades   87.50%   maxDD 4.9%
```
The stack triples the profit and the win rate does not move — but **40% drawdown over
103 days is not survivable on a $500 account.** If the stack is used it needs a tighter
cap than 0.60, and that cap must itself be tested.

### The honest economics
**+$138.60 over 103 days at 0.10 lots is about $1.35/day.** It is a real, validated edge
and it is small. The reason is arithmetic: at SL 9 / TP 1 each win pays $10 and each
full-stop loss costs $90, so 88% barely clears. The 30-minute age-out is what makes it
positive at all, by closing some losers before they reach the stop.

**To earn more we need more trades or a better payoff — not better entries.** 441 trades
in 103 days is 4.3/day; the entry engine is sound and under-used.

### The trend gate — the answer flipped
On four days of August, opening the gate looked like a huge win (+$44 -> +$144). On 103
days, **every one of the top win-rate configs has the gate ON.** The August result was
a small-sample artefact. **Gate stays ON.**

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
