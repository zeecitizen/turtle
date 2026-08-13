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

## 1.3 No stop, no target, hold 25 — the survivor

```
Aug 10-13    4,137        63 100.00%     +32.10       0.00     7.6%    survived
Mar 2-16    13,788       236  98.31%    -327.10    -157.60    17.8%    survived
Apr 1-15    12,407       311  96.78%    -727.90     -99.26    23.0%    survived
May 1-15    13,788       272  97.06%    -126.80     -43.90     9.1%    survived
                                       ---------
                                       -1,149.70   max equity drawdown 23.0%
```

**This is the real result, and the audit strengthens it rather than weakening it.** The
comparison is not "−$1,150 versus −$5,656". It is:

```
                    four-period net    worst drawdown    survived all four?
shipped                 -$5,656*            97.1%              NO
no stop, flat 25min     -$1,150             23.0%             YES
```

*\*censored; the true figure is worse.*

**It still loses money.** Wins average $0.85. A machine that survives is not a machine
that earns, and −$1,150 over 47 trading days is not a business. But it is the first
configuration this week that did not put the account on the floor in any period tested.

**One caveat, stated because it cuts our way and should not be quietly enjoyed:** the
April baseline run covered 11,565 bars against the candidates' 12,407. The baseline saw
*less* of a losing month, so correcting it would widen the gap, not close it.

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
