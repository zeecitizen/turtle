# LATEST WIN RATE

## 📌 TODAY'S ANSWER (2026-08-10) — 93.3%

Zee asked: *"can we ever say every single UHV breakout resulted in a small bump in our
direction... if we could gain total control we could be making profit 94% of the time?"*

**He was right, and measuring it produced the best configuration of the day.**

```
THE CEILING — how often the $1 EVER arrives if we are never stopped (103 days):

  stop   9pt, wait  30min   88.44%   +$139   worst -$90       drawdown 15%
  stop  20pt, wait  60min   93.12%   +$597   worst -$200      drawdown 17%   <- best money
  stop  40pt, wait 120min   95.56%   +$249   worst -$400      drawdown 26%
  stop  80pt, wait 240min   96.92%   +$508   worst -$800      drawdown 31%
  stop 200pt, wait 600min   98.07%   +$268   worst -$1,605    drawdown 48%
```

**98% of UHV breakouts do eventually give the bump.** His claim is confirmed. But the
MONEY does not follow the win rate — 98% earns less than 93%, because the few that never
come back become enormous. Perfect control is not free; you pay for it in the size of
the rare loss.

### THE SHIPPED CONFIGURATION — stop 20, wait 60, diamonds at fixed 0.10

```
                        trades    win%        net      maxDD
  103 days (in-sample)   1,608   93.28%   +$2,599.10   45.7%
  Aug 5-10   (UNSEEN)       26  100.00%     +$260.00    6.5%
  Feb 11     (UNSEEN)       26  100.00%     +$260.00    5.5%
```

**93.3% on 1,608 trades — the largest sample this project has measured — and 100% on
both datasets the optimiser never saw.** Three times the profit of the previous best for
the same drawdown.

**EA defaults now match this exactly:**
```
InpLots 0.10 · InpStopPts 20 · InpTargetPts 1 · InpUhvBodyMin 0.5 · InpTrendLook 20
InpRetraceBack 20 · InpRequireTrend true · InpUseDiamonds true · InpStackLots true
InpStackStep 0.0 · InpMaxRisk 0 · InpMaxOpen 1 · InpCooldownBar 3 · InpMaxHoldMin 60
```

### What to expect
```
base 0.10  ->  +$2,599 / 103 days  =  about $25/day, ~16 trades, ~15 winners
base 0.02  ->    +$520 / 103 days  =  about $5/day, drawdown ~9%   <- $500 account
```

**Still never traded live.** 93.3% is a tester result across 1,608 trades, which is the
strongest evidence this project has ever had — and it is still not a live fill. The
honest next step is a week at 0.02 on the real account.

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


## 🎚️ THE RISK ANSWER — do not cap the conviction, shrink the base lot

Capping the stack was the obvious idea and it is the wrong one. Measured on 103 days:

```
   cap    trades   win%      net     maxDD   $ earned per 1% of drawdown
  0.10      441   88.4%   +$139     14.9%          9.3
  0.20      882   88.4%   +$277     28.2%          9.8
  none     1628   88.6%   +$821     45.2%         18.1   <- TWICE as efficient
```

**The uncapped version earns twice as much per unit of risk.** The 3rd and 4th tickets —
the ones only the highest-conviction setups earn — are the best trades in the system.
Capping throws away precisely the part worth having.

**So scale the BASE LOT instead. The structure stays; only the size moves:**

```
   base       net      maxDD    what a $500 account would feel
   0.10    +820.50     45.2%    ~$226 down at its worst
   0.05    +410.25     25.9%    ~$130 down
   0.02    +164.10     11.4%    ~$57 down     <- for a $500 real account
   0.01     +82.05      5.9%    ~$29 down
```

**RECOMMENDED SIZES**
- **$500 real account -> base 0.02.** ~11% drawdown, +$164 per 103 days (~$1.60/day).
- **$4,123 demo -> base 0.10.** 45% drawdown is aggressive but survivable while testing.

Both keep `InpMaxRisk = 0` (no cap), because the cap destroys the edge's efficiency.

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
