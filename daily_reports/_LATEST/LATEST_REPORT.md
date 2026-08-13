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

```
config                   MAR       APR       MAY     3-period    worst eqDD
CONTROL SL20/TP1/60   -523.66   -896.34   +106.36   -1,313.64      24.9%
SL20 TRAIL 1.0/0.3    -392.74   -896.00   +130.98   -1,157.76      24.9%
SL20 TRAIL 1.0/0.5    -397.02   -873.48   +108.42   -1,162.08      24.4%
SL20 TRAIL 2.0/1.0    -575.76   -873.20    -78.10   -1,527.06      25.1%
NOSL TRAIL1.0/0.5 h60  -44.76  -1,193.56  +108.42   -1,129.90      32.2%
NOSL TP1 h25          -276.48   -548.62   -205.50   -1,030.60      17.1%
```

**No exit configuration is profitable across four periods.** The best (`NOSL TP1 h25`,
−$1,030.60) beats the shipped config by $283 at 0.02 lots — about $1,400 at 0.10 — and it
does it by having the cheapest losses of anything tested, not by winning more.

**The conclusion is uncomfortable and worth stating plainly: the exit is already at its
maximum. Every one of the eleven alternatives tested today earns less.** If more money is
to be found it is not here.

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

**The unanswered question underneath all of it** ([`test_tips.md`](../../testing/test_tips.md) Part 8):
under OHLC modelling the strategy's average loss was $114.58 against random's $154.80 — that
gap *is* the entire claimed edge. Under real ticks the strategy's average loss is $148.81,
essentially random. **A real-tick `NullEntry` run has never been done.** Until it is, we do
not know whether the entry contributes anything at all, and every exit we tune is being
tuned on top of an unmeasured foundation.

That is one ~18-minute run per fortnight window. It is the cheapest decisive measurement
available and it should come before any further exit search.

---

# 4. Reproducing anything above

```bash
py monitor/mt5_headless.py --ea ZeeUHV_v13 --symbol XAUUSD --from 2026.04.01 --to 2026.04.15 --model 4
py monitor/read_opt.py --top 12
```

Check `Bars` first, then `Ticks/Bars`, then `Equity Drawdown Relative` — a figure above 90%
means the account died and the net is censored. Reports are in `mt5/_tester_runs/headless/`
and every number in this document names the file it came from.
