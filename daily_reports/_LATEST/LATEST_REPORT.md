# 13 August 2026 — the branch search, and an audit that changes what it means

**Supersedes:** the 21 July post-mortem, which now lives at
[`daily_reports/2026-07/POST_MORTEM_6_MONTHS_2026-07-21.md`](../2026-07/POST_MORTEM_6_MONTHS_2026-07-21.md).
Read that one for *why six months failed*. Read this one for *where the search stands*.

**Nothing has been promoted. `diamond` is untouched. The live EA is untouched.**

---

# 0. Read this first — a measurement fault found today

Four candidates were tested overnight against the shipped configuration. Before writing
them up, every report was re-opened and the `Bars` field compared. **Two problems turned
up, and both change how the results read.**

## 0a. Runs that report ≈ −$4,000 are bankruptcies, not measurements

The tester deposit is **$4,123**. Every run whose net lands near −$4,000 shows an equity
drawdown of 92–98% and a truncated bar count:

```
run                        net        equity DD    bars / expected
ZeeUHV_v13_021847     -4 000.60         97.13%     11,565 / 12,407    baseline, April
ZeeUHV_v14_012937     -4 039.60         98.06%      5,308 / 12,407    v1.4 rank 6, April
ZeeMulti_015952       -4 001.30         97.21%      4,432 / 13,788    all four, May
ZeeUHV_v14_012737     -3 766.10         92.05%      1,591 / 13,788    all gates open, March
```

**The account died and the run stopped.** −$4,000 is the floor of the measuring
instrument — the most it is *possible* to lose — so every one of these numbers is
**censored**. The true loss is worse, by an unknown amount, and two configurations that
both print "−$4,00x" may be nowhere near equally bad.

This matters most for the multi-pattern work. Yesterday's commit reported *"MOMENTUM alone
−$4,023, ALL FOUR −$4,045"* and computed a good-day-to-bad-day ratio from them. Those are
stop-outs. **The ratio cannot be computed from a censored loss, and that conclusion is
withdrawn.**

## 0b. `Ticks / Bars > 50` does not prove the run covered the period

The existing checklist verifies tick *quality*. Nothing verified tick *coverage*. Two
August runs, **byte-identical configuration**, diffed input by input:

```
ZeeUHV_v13_004725    2,758 bars   217 tk/bar    38 trades   100.00%   +$430.00
ZeeUHV_v13_021210    4,137 bars   215 tk/bar    63 trades    93.65%   +$430.80
```

Both pass `Ticks/Bars > 50`. The first covered **two days of a three-day window** — the
rig's tick history had not finished downloading when it ran. The nets agree to within a
dollar by coincidence, which is exactly why it went unnoticed.

### The consequence

> **"Aug 10–13: 38 trades, 100.00%, +$430" — the flagship result, the one quoted as
> proof that the tester agrees with live — was measured on two-thirds of the window.
> On the full window it is 63 trades at 93.65%, with an average loss of $58.30.**

August is still a good period and the tester still broadly agrees with live. But it is
**not** a period in which this strategy does not lose. That claim appears in
`testing/test_tips.md`, `THINGS_TO_REMEMBER.md` and `latest_winrate.md`; all three are
corrected in this commit.

**New rule, added to the checklist:** assert `Bars` against the window's expected bar
count (≈1,380 per trading day on M1 gold) *before* reading any other number. A short run
is not an error — it is a clean-looking report about a different experiment.

---

# 1. The candidates, audited

All runs: `XAUUSD` broker data, real ticks (`--model 4`), M1, 0.10 lots, deposit $4,123.
Every row below is a named report file in `mt5/_tester_runs/headless/`, and every row's
bar count has been checked against its period.

## 1.1 The shipped configuration — SL 20 / TP 1 / hold 60

```
period        bars    trades   win%        net     avg loss   eq DD    verdict
Aug 10-13    4,137        63  93.65%    +430.80     -58.30    13.8%    survived
Mar 2-16    13,788       224  85.27%  -2,618.30    -148.81    73.5%    survived
Apr 1-15    11,565       265  84.53%  -4,000.60    -165.84    97.1%    BLEW UP
May 1-15    13,788       250  88.00%    +531.80     -63.99    23.4%    survived
                                       ---------
                                       -5,656.30   (April censored — true loss is worse)
```

**The shipped configuration goes bankrupt in April.** That is the finding of the day and
it was not visible in yesterday's table, because a blown account and a bad fortnight print
the same kind of number.

## 1.2 No stop, TP 1, hold 25 — `InpStopPts=200`

```
Aug 10-13    4,137        63  87.30%    +290.40     -39.10     8.3%    survived
Mar 2-16    13,788       228  82.89%  -1,382.40     -94.44    46.0%    survived
Apr 1-15    12,407       299  81.61%  -2,743.10    -104.45    83.3%    survived
May 1-15    13,788       254  79.13%  -1,027.50     -61.01    34.5%    survived
                                       ---------
                                       -4,862.60
```

Keeps real wins ($10.97 average) and survives April, but 83.3% drawdown is a near miss.

## 1.3 ~~No stop, no target, hold 25 — the survivor~~ **RETRACTED — it was never trading**

```
Aug 10-13    4,137        63 100.00%     +32.10       0.00     7.6%    survived
Mar 2-16    13,788       236  98.31%    -327.10    -157.60    17.8%    survived
Apr 1-15    12,407       311  96.78%    -727.90     -99.26    23.0%    survived
May 1-15    13,788       272  97.06%    -126.80     -43.90     9.1%    survived
                                       ---------
                                       -1,149.70   max equity drawdown 23.0%
```

> ### 🛑 RETRACTED the same day it was published
>
> These runs set `InpTargetPts = 0` to mean "no target". The EA computed
> `tp = px + InpTargetPts`, which put the take-profit **on the entry price itself**, so
> every trade closed as soon as price ticked up by one spread. The 25-minute hold never
> happened. Nothing ran.
>
> **The tell was in the report all along:** across 63 August trades the largest single
> win was **$2.70**, against the TP-1 baseline's $15.20 — while the tape over those same
> entries offered a median favourable excursion of **+4.62 points**. A configuration that
> "lets winners run" cannot have a $2.70 best trade. It also explains the 97–100% win
> rates and the $0.51–$0.88 average wins: that is what closing at breakeven looks like.
> And it explains why 15, 25 and 40-minute holds all returned nearly the same number —
> the hold was irrelevant.
>
> **So −$1,150 was not a strategy surviving four periods. It was a machine that opened
> and immediately closed, collecting a spread-sized crumb and occasionally being caught
> out.** The claim that it "survived where the shipped config went bankrupt" is withdrawn.
>
> Fixed in `mt5/ZeeUHV_v13.mq5`: zero now sends `0.0`, which MT5 reads as "no level".
> Re-measured honestly, **letting winners run is a disaster** — see §1.6.
>
> Untouched by this: **`NOSTOP TP1 h25` used a real target (TP 1.0) and remains valid**,
> as does every row in §1.1 and §1.2. **The live EA is not affected** — it runs
> `InpTargetPts = 1.0`, so all 14 live baskets are genuine.

**One caveat on §1.1 that still stands:** the April baseline run covered 11,565 bars
against §1.2's 12,407. The baseline saw *less* of a losing month.

## 1.6 THE EXIT SWEEP — can we make more money per trade? No. (2026-08-13, evening)

Zee: *"given our current trade history since deploying the EA and its first trade on
11.08 01:51, can you find a way to maximize the profits?"*

The screenshot he sent carries the clue: **every close price overshoots the take-profit**,
sometimes by 0.30–0.56. Price is moving fast *through* our $1 target, which looks like a
move we are clipping short. And his own Feb-11 winners ran to ~6 points where ours take 1.

So the target was swept properly, on real ticks, for the first time.

### August (kind period) · 4,137 bars · 216 ticks/bar · 0.10 lots

```
config                trades   win%       net    avgW    maxW     avgL    eqDD
CONTROL SL20/TP1/60       63  93.65%   +440.30   11.42   15.20   -58.30   13.1%   <- shipped
TP 2.0                    60  66.67%   -489.60   21.75           -67.98   33.0%
TP 3.0                    60  66.67%   -106.40   31.33           -67.98   30.0%
TP 5.0                    60  46.67%  -1510.70   40.85           -82.95   54.6%
SL20 TRAIL 1.0/0.3        63  88.89%   +348.30   10.45   27.60   -33.87   13.3%
SL20 TRAIL 1.0/0.5        63  88.89%   +361.50   10.69   27.60   -33.87   13.3%
SL20 TRAIL 2.0/1.0        60  66.67%   -668.70   17.27   27.60   -67.98   34.5%
SL20 TRAIL 3.0/1.5        60  66.67%   -235.30   28.11   63.00   -67.98   31.2%
NOSL NOTP h25             60  11.67%  -2165.60   30.94   50.70   -44.95   58.2%
NOSL NOTP h60             60  40.00%  -1998.10   65.93  131.50   -99.46   81.2%
NOSL TP1 h25              63  87.30%   +299.90   11.14   13.50   -39.10    8.0%
```

**Nothing beats TP 1.** Every larger target loses money, and the win rate collapses with
it — 93.65% → 66.67% → 46.67%. This is now the fourth independent confirmation of Zee's
$1 call, and the first on real ticks.

### The Feb-11 shape, mechanised — and why six months of it failed

`NOSL NOTP h60` is his actual Feb-11 configuration: **no stop, no target, exit on the
clock.** Run honestly for the first time (§1.3 explains why every previous attempt was
fake), it reproduces the good half of his day exactly:

```
                     average WIN    largest WIN
Zee, 11 Feb 2026        €12.93         €54.93      ≈ 5.5 points
NOSL NOTP h60            $65.93        $131.50     ≈ 6.6 points at 0.10 lots
```

**The winners really do run to six points.** The machine found them. What it could not do
was the other half:

```
                     win rate    average LOSS    worst
Zee's hand              94.2%         -€1.32     -€1.60
the machine             40.0%        -$99.46    -$400+     net -$1,998
```

> **This is the six-month post-mortem, measured.** His 94% and his €1.32 average loss were
> one thing, not two: a discretionary cut. Remove the cut and the same entries produce
> 60% losers at $99 each. **The runs were never the edge. The cut was.** And no clock,
> stop, trail or volume rule tested so far reproduces it — this is the sixth to fail.

### The one honest improvement, and it is not in August

The trail at 1.0/0.5 cuts the average loss almost in half — **−$58.30 → −$33.87** — while
capturing bigger winners ($27.60 vs $15.20). It nets less in August because it gives up
win rate. But losses are what destroy the hostile months, so it was tested there.

### All four periods at 0.02 lots — nothing censored, every window complete

Small lots deliberately: at 0.10 the shipped config bankrupts in April and its net is
censored at the deposit (§0a), which makes every comparison against it meaningless.

```
exit configuration          AUG       MAR        APR       MAY    4-PERIOD   E/trade
NOSL TP1 h25              59.98   -276.48    -548.62   -205.50    -970.62    -1.150
NOSL TRAIL1.0/0.5 h60     72.30    -44.76  -1,193.56   +108.42  -1,057.60    -1.288
SL20 TRAIL 1.0/0.3        69.66   -392.74    -896.00   +130.98  -1,088.10    -1.302
SL20 TRAIL 1.0/0.5        72.30   -397.02    -873.48   +108.42  -1,089.78    -1.310
CONTROL SL20/TP1/60       88.06   -523.66    -896.34   +106.36  -1,225.58    -1.466   <- shipped
SL20 TRAIL 2.0/1.0      -133.74   -575.76    -873.20    -78.10  -1,660.80    -2.061
```

**Every row is negative.** The best (`NOSL TP1 h25`) beats the shipped config by $254.96 at
0.02 lots — about **+$1,275 at 0.10 over 47 trading days** — and it does it by having the
cheapest losses of anything tested, not by winning more. It buys March and April protection
by giving up May.

**The conclusion is uncomfortable and worth stating plainly: the exit is already at its
maximum. Every one of the eleven alternatives tested today earns less, or earns a little
more only by trading one period's profit for another's.** The shipped exit loses $1.47 per
trade; the best alternative loses $1.15. Breaking even needs $1.47 of improvement per
trade and the entire exit search delivers $0.32. **If more money exists, it is not here.**

**The conclusion is uncomfortable and worth stating plainly: the exit is already at its
maximum. Every one of the eleven alternatives tested today earns less.** If more money is
to be found it is not here.

## 1.7 THE LEVERS THAT ARE NOT THE EXIT — frequency works, size does not

Since the exit is maximal, the remaining levers all multiply the *good* setups. All at
0.02 lots, all four periods, every window complete.

```
arm                    AUG       MAR        APR       MAY    4-PERIOD
rank6 + Law2        +128.62   -353.98  -998.48   +204.12   -1,019.72
rank6               +128.62   -356.74  -1,003.36 +204.12   -1,027.36
Law2 (5th ticket)    +88.06   -520.90   -894.00  +106.36   -1,220.48
shipped              +88.06   -523.66   -896.34  +106.36   -1,225.58
StackStep 0.1       +668.56 -3,795.84 -4,249.28  +572.86   -6,803.70   BLEW UP ×2
```

**`rank 6` is the one genuine improvement found all day — and it is Zee's own rule.**

```
             AUG                       MAR                       MAY
shipped   63 tr 93.65% +88.06     224 tr 85.27% -523.66     250 tr 88.00% +106.36
rank 6    82 tr 95.12% +128.62    296 tr 88.85% -356.74     357 tr 88.52% +204.12
                                  drawdown 15.7% -> 12.1%
```

August: **+46% more money and not one new loss** — four losing tickets in both arms, which
is why the average loss is identical to the cent. March: better by $167 *at lower
drawdown*. May: nearly double. April is the only period it costs anything (−$107). It
satisfies the promotion rule — it wins in a kind period and a hostile one — and it is
worth about **+$1,000 per 47 trading days at 0.10 lots**.

**`Law 2` is inert**, not broken: it added 1 ticket in 225 in March, exactly what its
measured 1.1% fire rate predicts. It costs nothing and earns nothing.

**`StackStep` is leverage, not edge, and it is dangerous.** In August it looks like a 7.6×
profit multiplier — but drawdown scales 7.2× with it, and in March and April it **blew the
account** (93.0% and 102.9% equity drawdown). Third confirmation that the account, not the
strategy, is the limit on size.

## 1.8 🚨 THE CONTROL EXPERIMENT — the entry is WORSE THAN RANDOM on real ticks

Open since 2026-08-12, listed in `test_tips.md` Part 8 as "the most valuable outstanding
measurement", never run. It is now run.

`NullEntry` has **no rules**: it opens every 30 minutes, alternating direction, with the
identical stop 20 / target 1 / hold 60. Both arms at 0.02 lots, real ticks, every window
complete, nothing censored.

```
period       ZeeUHV (his rules)                NullEntry (NO rules)
             trades   win%      net   E/tr     trades   win%      net   E/tr
Aug 10-13        63  93.65%   +88.06  +1.40       119  87.39%   -46.28  -0.39
Mar 02-16       224  85.27%  -523.66  -2.34       424  92.22%  -185.52  -0.44
Apr 01-15       299  81.61%  -896.34  -3.00       381  90.55%  -257.22  -0.68
May 01-15       250  88.00%  +106.36  +0.43       405  93.58%  +174.58  +0.43
──────────────────────────────────────────────────────────────────────────────
TOTAL           836          -1,225.58 -1.466    1,329          -314.44 -0.237
```

> **Firing at nothing loses $0.24 a trade. Firing on Zee's UHV rules loses $1.47 a trade.
> Over 47 trading days the random entry is six times cheaper to be wrong with.**

**The old belief is exactly inverted.** Under OHLC modelling ZeeUHV's average loss was
$114.58 against NullEntry's $154.80, and that gap was declared the whole edge —
"the edge is not picking winners, it is picking trades that are cheap to be wrong about."

On real ticks the loss-cheapness half is **still true**: ZeeUHV's average loss is smaller
in *every* period (−29.76 vs −33.54, −27.33 vs −31.92, −12.80 vs −26.08, −11.66 vs −18.41).
But it is swamped, because the entry's **win rate is LOWER than random in three of the four
periods** — 85.27 vs 92.22, 81.61 vs 90.55, 88.00 vs 93.58. Cheaper losses, far more of them.

**A coherent mechanism, offered as a hypothesis rather than a conclusion:** a UHV is by
definition a moment of unusual volume, therefore unusual volatility. A 20-point stop is hit
far more often from there than from a random quiet minute, where price simply wanders back
to +1 within the hour. **We may have spent six months selecting precisely the moments where
our own exit geometry is most likely to fail.**

### What this does NOT say

- **It does not say August is fake.** August is the one period where the entry clearly beats
  random — **+$1.40 a trade against −$0.39** — and it is the regime the live account is
  trading right now, 14 baskets unbeaten.

  **But "regime-dependent" is a hypothesis, not a measurement.** The entry beat random in
  **one fortnight out of four**. May was a dead heat (+$0.43 both). One win in four is not
  distinguishable from luck at this sample size, and calling it a regime effect is exactly
  the kind of overclaim this project keeps paying for. What is measured is the *shape*:

  ```
  period   ZeeUHV avgW    avgL    our win rate vs random
  Aug            2.28  -11.66            +6.26 pts
  May            2.23  -12.80            -5.58
  Mar            2.40  -29.76            -6.95
  Apr            2.49  -27.33            -8.94
  ```

  **The average WIN barely moves (2.23–2.49). The average LOSS more than doubles.** The
  regime variable is how far a failed trade runs against you, not what a winner pays — and
  our deficit against random widens as losses get more expensive. That is a coherent,
  testable story. It is not yet evidence.
- **It does not say NullEntry is a strategy.** It loses money too. Nothing here is a
  business.
- **Sample caveat, stated because it cuts against the finding:** ZeeUHV's 836 tickets are
  only ~220 independent setups (a diamond stack wins or loses together), so its effective
  sample is ~55 setups per period and noisier than the trade count suggests. NullEntry's
  1,329 are independent. The direction is consistent across three periods and the totals
  differ 4×, which is more than noise — but the per-period figures deserve less confidence
  than they look.

## 1.9 WHERE THE LOSS LIVES — 13 windows, and the quantity that decides everything

If a hostile fortnight is a few bad days, a regime filter has something to bite on. If it
bleeds throughout, it does not. So the shipped configuration was run over 13 consecutive
~3-day windows at 0.02 lots.

**Reconciliation check first:** the four March windows sum to **−$523.66**, matching the
single full-period run to the cent; April's four sum to **−$896.34**, likewise. All 13 sum
to −$1,226.54 against the four full runs' −$1,225.58. The windowing is sound.

```
window        win%    avgW     avgL    break-even needed        net
May 09-13   88.89%    2.24    -0.49         17.9%           +104.48
Aug 10-13   93.65%    2.28   -11.66         83.6%            +88.06
Apr 09-13   94.74%    2.28   -16.20         87.7%            +74.30
May 13-15   85.19%    2.20    -9.85         81.7%            +22.48
May 06-09   84.31%    2.14   -12.28         85.2%             -6.38
May 01-06   91.21%    2.29   -25.62         91.8%            -15.18
Mar 02-05   89.02%    2.64   -30.95         92.1%            -86.20
Mar 05-10   88.06%    2.40   -30.99         92.8%           -106.50
Mar 13-16   86.67%    2.15   -40.82         95.0%           -107.46
Mar 10-13   73.33%    2.09   -24.37         92.1%           -223.50
Apr 01-06   84.62%    2.20   -40.12         94.8%           -224.26
Apr 13-15   75.63%    2.81   -18.12         86.6%           -272.92
Apr 06-09   78.87%    2.40   -40.54         94.4%           -473.46
```

**4 of 13 windows are profitable, and they are not grouped by month.** April — the worst
fortnight — contains both a +$74.30 window and the −$473.46 one. March bleeds in all four.
So the damage is neither uniform nor conveniently concentrated.

### The quantity that decides it

`break-even needed = |avgL| / (avgW + |avgL|)`. Every profitable window clears its own
threshold and every losing one misses — but that is an **accounting identity, not a
prediction**, and it should not be dressed up as a discovery. Its value is the
decomposition:

```
avgW  spans  2.09 -> 2.81     a factor of 1.3
avgL  spans -0.49 -> -40.82   a factor of 83
```

**The average win is pinned by the $1 target and barely moves. The outcome is decided
almost entirely by the average loss.** At a realistic 88% win rate the system needs
`|avgL| <= 2.3 × 0.88/0.12 ≈ $17` to survive. It sits between $12 and $41.

That is what §1.10 goes after — and it is also why the 1:20 geometry is a trap: **a
volatile period raises the win rate you need at the same moment it lowers the win rate you
get.**

### A caveat this section made visible

All four of August's losing tickets are **−$11.66 exactly** — one losing setup with four
stacked tickets, exiting together. **August's 93.65% over 63 tickets is 15 setups with one
loser.** Every per-period win rate in this document should be read with the same division:
the ticket counts are roughly 3.8× the number of independent events.

## 1.10 THE STOP SWEEP — a $500 improvement that must be REJECTED

§1.9 showed the average loss decides everything, so the stop was swept on real ticks across
all four periods, target and hold unchanged, 0.02 lots. The headline looks like the best
result of the day:

```
stop   four-period total    vs shipped
   3        -724.76          +500.82   <- "best"
   8        -955.78          +269.80
   5      -1,040.58          +185.00
  12      -1,065.90          +159.68
  20      -1,225.58             ----   <- shipped
```

**Do not ship it.** Broken out by period, the total is one month wearing a disguise:

```
stop       AUG        MAR        APR        MAY   |  change vs shipped, per period
  20     88.06    -523.66    -896.34    +106.36   |    ----      ----      ----      ----
  12     88.06    -378.08    -634.60    -141.28   |   +0.00   +145.58   +261.74   -247.64
   8    -62.50    -372.92    -318.12    -202.24   | -150.56   +150.74   +578.22   -308.60
   5     -9.22    -359.14    -296.54    -375.68   |  -97.28   +164.52   +599.80   -482.04
   3    +30.46    -400.74     -83.18    -271.30   |  -57.60   +122.92   +813.16   -377.66
```

- **Only 2 of 4 periods improve at any stop.** It helps March and April, hurts August and May.
- **April alone contributes +$813 of the +$501.** Remove April and stop 3 is **worse** by $312.
- **The win rate collapses**: March 85.27% → 55.08%, May 88.00% → 61.51%. That is a
  different strategy — high-frequency, low-win-rate — not a tuned version of this one.
- **It is non-monotonic**: in August, stop 8 is worse than both stop 12 and stop 3. No
  plateau, so no stable optimum. Part 2.3 of `test_tips.md`: *a plateau is not protection* —
  and here there is not even a plateau.

**It fails the promotion rule outright: a change must win in a kind period AND a hostile
one. This wins only in the hostile ones.** It is the same shape as the 96.4% configuration
that lost $4,071 out of sample — a single period carrying a total.

### What it does establish

The direction is consistent and it is the regime story again, from the other side:

> **A tighter stop helps where losses run (March, April) and hurts where noise ejects
> trades (August, May).** The right stop is not a constant — it is a function of how far
> price is currently travelling.

A volatility-scaled stop is therefore the natural next experiment. It is also exactly the
kind of feature that overfits, so it gets built only with its own out-of-sample receipts,
and not tonight.

## 1.11 THE DIAMOND MULTIPLIER — 4 tickets to 8

Zee, 2026-08-13: *"since our winrate since past two days is 100%, let's increase the
multiplier of each diamond. so that instead of opening 4 trades, it opens 8 trades."*

That sentence has two readings and they are not the same trade, so both were built
(`InpDiaMult`, `InpStackMult` in `ZeeUHV_v13`, both defaulting to 1 = shipped behaviour):

```
InpDiaMult   2   1 + dia*2   = 7 at 3 diamonds   conviction-weighted: a 0-diamond setup still opens 1
InpStackMult 2   (1 + dia)*2 = 8 at 3 diamonds   doubles everything
```

Baseline re-ran to the cent after the edit (63 trades / 93.65% / +$88.06), as required.

### At 0.02 lots — uncensored, so expectancy is comparable

```
              AUG       MAR       APR      MAY    4-period
baseline 4  +88.06   -523.66   -896.34  +106.36   -1,225.58
DiaMult2 7 +151.44   -896.90 -1,560.14  +175.22   -2,130.38
StackMul2 8 +176.12 -1,047.32 -1,792.68 +212.72   -2,451.16
```

**−2451.16 / −1225.58 = exactly 2.000.** Per-ticket expectancy is unchanged in every arm
($1.40 / $1.39 / $1.40) and the average loss never moves ($−11.66 in all three August
arms). **It is a pure multiplier: it does not make the system better, it makes it bigger,
in both directions.** `StackMult` is arithmetically identical to doubling `InpLots`.

### At 0.10 lots — the size actually traded, and the reason this matters

```
             MAR                                APR
baseline 4   -2,618.30   73.5% DD   survived    -4,000.60    97.1%  blew up
DiaMult2 7   -3,783.80   92.9% DD   BLEW UP     -4,295.40   104.0%  blew up
StackMul2 8  -3,781.80   93.0% DD   BLEW UP     -3,990.60    97.0%  blew up at 25% of the window
```

**March is the line.** At 4 tickets the account survives it — badly hurt at 73.5% drawdown,
but alive. At 7 or 8 it is gone. Doubling converts one bad month into no account. (The
0.10 four-period totals are omitted deliberately: three of them are censored at the
deposit and cannot be summed — §0a.)

Risk per failed setup on the $4,123 demo, since all tickets share one stop and die together:

```
stack        lots/setup   risk if the setup fails   % of account   losing setups to ruin
4 tickets        0.40              $800                 19.4%              5.2
7 tickets        0.70            $1,400                 34.0%              2.9
8 tickets        0.80            $1,600                 38.8%              2.6
```

**Not promoted. Nothing is live.** Both inputs default to 1. The decision is Zee's, and the
options put to him were: ship it as asked; double the tickets and halve the lot (identical
exposure, finer granularity); or ship it paired with a **code-enforced equity halt**, on the
grounds that a safety rule a human has to remember is not a safety rule.

## 1.4 v1.4 — "every UHV in the retracement" (`InpUhvRank`, `InpMaxOpen=8`)

Your rule: fire on every UHV in the retracement, not only the loudest. Mechanically sound
— `FindUhvRanked()` walks candidates from loudest down and takes the first one actually
broken.

```
period       rank 1 (baseline)          rank 6
Aug 10-13    +430.00  (2,758 bars)    +592.40  (2,758 bars)   both short — see 0b
Mar 2-16   -2,618.30 (13,788)       -1,783.70 (13,788)        clean, better
Apr 1-15   -4,000.60 (11,565)       -4,039.60 ( 5,308)        BOTH BLEW UP — void
May 1-15     +531.80 (13,788)       +1,020.60 (13,788)        clean, better
```

**Verdict: promising, not proven.** March and May are clean and both improve. August was
measured on the short window for both arms — the comparison is internally fair but the
absolute numbers are wrong. **April is void**: rank 6 blew up after 5,308 bars, so
"−$4,039.60" is not a result at all. Needs re-running on the full April window before it
can be judged.

## 1.5 ZeeMulti — the other Feb-11 patterns

The August column is sound (all arms on the same 2,758 bars, so the *relative* reading
holds). MOMENTUM is genuinely the frequency answer: 27 setups/day against UHV's 3.3, and
profitable in the kind period.

**The March, April and May columns are not usable.** The high-frequency arms are exactly
the ones that blew up — MOMENTUM alone at 11,335 bars, ALL FOUR at 9,305 (March), 9,276
(April), 4,432 (May). More trades meant a faster death, which the bar counts record and
the nets conceal.

**Verdict: the frequency claim survives, the profitability claim is withdrawn** pending
re-runs that either survive the window or are honestly reported as bankruptcies.

---

# 2. Live — 14 setups, still unbeaten

Straight from `turtle_fills.csv`, deduplicated by `(deal_ticket, position_ticket)`:

```
14 baskets · 53 fills · 0 losing fills · +$613.80
first 2026.08.11 01:51 broker · latest 2026.08.13 17:30 broker (19:30 PKT)
```

Two landed today: 09:04 (+$38.40) and 17:30 (+$54.00).

**What this is not.** `NullEntry` — an EA with no rules that fires every 30 minutes —
scores 92.42% on the same exits. At that rate an unbeaten run of 14 baskets is unremarkable.
The streak is recorded because it is real, not because it is evidence.

**A discrepancy worth logging:** `README.md` reports the first three setups as *"15 fills,
+$161.90"*. The fills file gives 12 fills and +$130.00 for the same three, and README's own
per-setup rows sum to $162.90 rather than the $161.90 it states. Unresolved; the fills file
is the receipts truth per [`reference_mt5_trade_logger`](../../THINGS_TO_REMEMBER.md).

---

# 3. What this changes about the plan

The four-period search has now cost a week and produced one configuration that survives and
none that earns. The audit says part of that week measured bankruptcies and reported them as
fortnight-quality differences.

**The gap that actually matters is unchanged and getting louder:**

```
your 14 live baskets      average  ~$44 per basket
the mechanical version    average   $0.85 per win
```

Same nominal strategy. Two orders of magnitude apart. Every candidate this week has been an
*exit* variation, and the best of them survives by refusing to lose rather than by winning.

**That question is now answered — see §1.8.** The real-tick `NullEntry` control was run this
evening. **The entry is worse than random over 47 trading days** (−$1.47 a trade against
−$0.24), because its win rate is *lower* than random in three of the four periods. It beats
random only in August — the regime the live account is trading right now.

So the order of business inverts. There is no point tuning an exit on top of an entry that
subtracts value in three regimes out of four. The two questions that matter now:

1. **What distinguishes August and May from March and April?** The entry earns in one pair
   and bleeds in the other. If that is detectable in advance, it is the whole ballgame —
   sitting out the hostile periods turns −$1,225 into +$194 on this data. If it is not
   detectable, the strategy is a bet on regime and must be sized as one.
2. **Does the diamond count carry the signal?** The stack is the one part of the entry never
   tested against random. If 3-diamond setups beat NullEntry and 0-diamond ones do not, the
   conviction laws are the edge and the UHV trigger is just their carrier.

---

# 4. Reproducing anything above

```bash
py monitor/mt5_headless.py --ea ZeeUHV_v13 --symbol XAUUSD --from 2026.04.01 --to 2026.04.15 --model 4
py monitor/read_opt.py --top 12
```

Check `Bars` first, then `Ticks/Bars`, then `Equity Drawdown Relative` — a figure above 90%
means the account died and the net is censored. Reports are in `mt5/_tester_runs/headless/`
and every number in this document names the file it came from.
