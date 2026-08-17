# HOW TO TEST THIS SYSTEM WITHOUT LYING TO YOURSELF

Zee, 2026-08-13: *"since u told me u have a more reliable way to test now, can u record
that way of testing... so that in future we don't make the same testing mistakes."*

Everything on this page was learned by getting it wrong first. Every rule has a number
behind it and the mistake that produced it. **Read this before running a single test.**

---

# PART 1 — THE ONE RULE THAT MATTERS MOST

## Use real ticks. Nothing else can test a 1-point target.

```bash
py monitor/mt5_headless.py --ea ZeeUHV --symbol XAUUSD --from 2026.08.10 --to 2026.08.13 --model 4
```

`--model 4` is **"Every tick based on REAL ticks"**. It reads the broker's stored tick
history. Every other mode INVENTS the path inside each candle:

| mode | name | ticks per bar | usable for a 1-point target? |
|---|---|---|---|
| 0 | Every tick | interpolated from OHLC | **NO** — it is a guess |
| 1 | 1 minute OHLC | 4 | **NO** |
| 2 | Open prices only | 1 | **NO** |
| 4 | **Every tick based on real ticks** | **200-450** | **YES** |

**WHY IT MATTERS.** Gold moves 10-30 points inside a single minute. With a 1-point target
the path inside the candle *is* the trade. OHLC modelling deletes that path and
reconstructs it from four numbers.

**PROOF, and it is unambiguous.** Replaying the exact days the live EA traded:

```
real ticks, Aug 10-13    63 trades   93.65%   +$430.80   (890,868 ticks · 215/bar)
THE LIVE ACCOUNT         14 baskets 100.00%   +$613.80
```

The tester **agrees with live** once it can see the real path. Before this discovery,
every number this project ever produced was measured at **4 ticks per bar**.

> ⚠️ **CORRECTED 2026-08-13.** This block used to read *"38 trades, 100.00%, +$430"*. That
> run covered **2,758 bars of a 4,137-bar window** — two days of three. On the full window
> the same configuration scores 93.65% and takes losses averaging $58.30. August is a good
> period; it is not a period without losses. See **Part 11**.

## How to verify a run actually used real ticks
Never trust the flag — check the report:
```python
ratio = Ticks / Bars
ratio < 2    -> open prices only
ratio ≈ 4    -> OHLC modelling
ratio > 50   -> REAL TICKS
```
A run that silently fell back to OHLC looks identical to a good one.

**This ratio proves tick QUALITY and says nothing about COVERAGE.** Both of the August runs
above score ~216 ticks/bar and one of them is missing a third of the period. Check `Bars`
too — **Part 11**.

## Custom symbols CANNOT do this
`XAUUSD_BIG`, `XAUUSD_R3`, `XAUUSD_F11` were built from CSV **bars**. MT5 logs:
```
OHLC bar states generating. OnTick executed on the bar begin only
```
The EA sees roughly **one price per minute**. Every number those symbols produced —
including the famous **93.28% / +$2,599** — was measured that way and remains suspect.

To test a micro-scalper on custom data you must import **ticks** as well as bars
(`Ctrl+U` → symbol → Ticks tab → Import Ticks). Bars alone are not enough.

## Budget the time
Real ticks are ~50× slower.
```
2 weeks  ≈ 18 minutes
1 month  EXCEEDS the 5,400s limit and returns NO REPORT
```
A timeout writes nothing, which **looks exactly like a failed test**. Four monthly runs
were lost to this before it was understood. **Use two-week windows.**

---

# PART 2 — THE COMPARISON RULES

## 2.1 Match the period before comparing anything

**The most expensive mistake of the week.** Two days were spent inventing explanations —
volume source, tick model, contaminated code, price feed — for this:

```
103-day backtest on broker data   loses
2 days of live trading            wins every setup
```

There was no contradiction. **It was a sampling error.** Point the tester at the *same
days* and it agrees with live. A strategy has good periods and bad ones:

```
real ticks, Mar 2-16    85.27%   -$2,618
real ticks, Aug 10-13   93.65%     +$431
```

> **If a backtest disagrees with live, first check they cover the same dates.**
> **Then check they cover the same NUMBER OF BARS** — matching `--from/--to` is not the
> same as matching coverage (Part 11).

## 2.2 Always run the null hypothesis

`mt5/NullEntry.mq5` has **no strategy at all** — it opens a position every 30 minutes,
alternating direction, with the identical stop, target and hold.

```
                     trades    win%   avg WIN   avg LOSS    worst      net
NullEntry (no rules)  1,716  92.42%     $9.99  -$154.80    -$723   -$4,277
ZeeUHV (the rules)    1,608  93.28%     $9.98  -$114.58    -$200   +$2,599
```

**Firing at nothing wins 92.42%.** The whole win rate is the GEOMETRY — a 1-point target
against a 20-point stop over 60 minutes wins from any entry, because gold touches a dollar
constantly. Brownian approximation: `20 / (20 + 1) = 95%`.

> **Before believing any win rate, ask what a random entry scores with the same exits.**
> If they match, the strategy is not doing the work.

> ⚠️ **The +$2,599 column above is 4-ticks-per-bar and is now known to be wrong.** Re-run on
> REAL TICKS over four fortnights at matched exits, the control **beats** the strategy:
> NullEntry −$0.237/trade against ZeeUHV −$1.466/trade, with a HIGHER win rate in three of
> four periods. The rule in the box still stands — it is just that when we finally obeyed
> it properly, the answer was worse than "they match". See Part 8.

### ⚠️ How to QUOTE a control result without misleading anyone (Zee, 2026-08-13)

He objected: *"i can't accept the fact that 87% of randomly taken trades go into positive …
its even hard to get 50% if i click randomly … and by saying this u discard the advantage
the UHV strategy gives us."* **He was right on both counts.**

"Random entries score 87%" is not a statement about entries. It is a statement about
**risking 20 points to make 1**. Widen the target and it collapses to the coin flip he
described — same EA, same random entries, only the target moved:

```
target      AUG win%    MAR win%    random-walk prediction 20/(20+t)
  1.0        87.39%      92.22%             95.2%
  5.0        61.54%      72.93%             80.0%
 20.0        54.29%      51.47%             50.0%     <- 272 March trades
```

**Two rules follow, and they are about honesty rather than method:**

1. **Never quote a control's win rate without its risk/reward.** "NullEntry wins 92%" is
   meaningless alone; "NullEntry wins 92% risking 20 to make 1, and still loses money"
   is the finding.
2. **Lead a control comparison with EXPECTANCY, not win rate.** The win rate is mostly the
   exit and comparing it invites the reading that the strategy is worse than noise. On the
   identical August days: random **−$0.39/trade**, his rules **+$1.40/trade**. That gap is
   the edge, and it was buried under a win-rate table that implied the opposite.

## 2.3 Out-of-sample or it did not happen

Freeze every parameter, then run on data the search never saw. This has caught four
would-be shipments:

```
96.4% found on 4 days          -> -$4,071 over 103 unseen days
TP 3, best by expectancy       -> 57.14% and -$491 on Feb 11
TP 3, best by TCER             -> the same config, the same failure
the volume-fade exit           -> 1 winning cell of 45, all neighbours negative
```

**A plateau is not protection.** The 96.4% had 311 passes above 90% and a six-stop
plateau. It still failed. A plateau proves stability *within a sample* and says nothing
about another sample.

## 2.4 Python may generate a hypothesis. Only MT5 or live fills may promote one.

**Measured haircut: Python overstates the win rate by ~16 points** (96→83, 88→67, 83→67
across three configs on identical setups). A configuration needs **more than 16 points of
Python margin** to survive real execution. `monitor/doctrine.py` enforces this in code.

---

# PART 3 — WHAT TO OPTIMISE FOR

## Never win rate. It is noise the geometry produces.

### Expectancy
```
E = Net Profit / Total Trades
```
```
NullEntry  (0.9242 × 9.99) - (0.0758 × 154.80) = -$2.50 / trade
ZeeUHV     (0.9328 × 9.98) - (0.0672 × 114.58) = +$1.61 / trade
```
`1,608 × $1.61 = $2,589` — reconciles with the reported +$2,599. **The edge is not
picking winners; it is picking trades that are cheap to be wrong about.**

### TCER — Tail-Compressed Expectancy Ratio
```
TCER = E × (avgLoss / CVaR95) × √N
```
- **E** — expectancy per trade; also rejects any net-negative pass
- **avgLoss / CVaR95** — how closely the worst losses resemble the average one. Bounded in
  (0,1] and equals 1 only when EVERY loss is the same size
- **√N** — sample weight, so a lucky 40-trade run cannot outrank 1,600

**CVaR95** is the mean of the worst 5% of losing trades. MT5 has no statistic for it, so
compute it from the deal history inside `OnTester()`:

```cpp
double GetCVaR95() {
   if (!HistorySelect(0, TimeCurrent())) return 0.0;
   double losses[]; int n = 0;
   for (int i = 0; i < HistoryDealsTotal(); i++) {
      ulong t = HistoryDealGetTicket(i);
      if (t <= 0) continue;
      long entry = HistoryDealGetInteger(t, DEAL_ENTRY);
      if (entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;
      double pnl = HistoryDealGetDouble(t, DEAL_PROFIT)
                 + HistoryDealGetDouble(t, DEAL_SWAP)
                 + HistoryDealGetDouble(t, DEAL_COMMISSION);
      if (pnl < 0) { n++; ArrayResize(losses, n); losses[n-1] = MathAbs(pnl); }
   }
   if (n == 0) return 0.0;
   ArraySort(losses);                                // ascending
   int k = (int)MathMax(1, MathCeil(n * 0.05));
   double sum = 0; for (int i = n-k; i < n; i++) sum += losses[i];
   return sum / k;
}
```

**MQL5 constant names** (most examples online use the MQL4 spellings and will not
compile): `STAT_PROFIT`, `STAT_GROSS_LOSS`, `STAT_LOSS_TRADES`, `STAT_MAX_LOSSTRADE`,
`STAT_TRADES`.

### TCER's weakness — know it before trusting a winner
The tail term rises either by **shrinking the worst loss** (wanted) or by **inflating the
average loss** (not wanted). Worked example:
```
scenario                        E      avgL    worst      N     TCER
shipped, as measured          1.62   114.58   200.00   1608     37.2
SAME tail, WORSE avg loss     1.62   180.00   200.00   1608     58.5  <- scores HIGHER
```
`E` partly cancels this. Not completely. **Every TCER winner still needs out-of-sample
validation** — in practice TCER picked exactly the same over-fitted config that expectancy
did.

---

# PART 4 — THE FIVE SILENT FAILURES

**Every one produced a confident, clean-looking result while doing nothing.** This is the
dominant failure mode of this project — not wrong answers, but convincing ones.

| # | what happened | how it looked | the tell |
|---|---|---|---|
| 1 | `iVolume()` returned a constant **4** in the tester | every volume rule "working" | `NsndF11` reported `signals=0` on a day full of setups |
| 2 | A file-open error hidden behind `InpVerbose` | 0 trades, clean report | the filename was `oanda_archive.csv\|\|\|\|\|\|N` |
| 3 | `hasattr(Z, "diamonds_for")` on a function that never existed | printed `0 diamonds` on every setup | the stack was worth 6× and never fired |
| 4 | `tickets = 1 + MathMin(dia, 3)` capped away a 4th diamond | Law 2 on/off identical **to the cent** | identical results are never a real result |
| 5 | The brain judged the **still-forming** candle | 9 hours, zero setups, heartbeat healthy | replay found 3 setups the live process missed |

### The rules that follow
1. **Never hide a failure behind a verbosity flag.** A load error, a missing file, a
   fallback — all must print unconditionally.
2. **Never write a silent fallback.** `hasattr(...) else 0` reported a measured zero for
   something that did not exist. If a thing is missing, say so.
3. **Identical results are a bug, not a confirmation.** If a rule changes nothing to the
   cent, it is not working.
4. **A heartbeat proves the process is alive, not that it is working.** Log what it
   *found*, not merely that it ran.
5. **`bars[-1]` is the candle still being built.** Step back until the minute has ended.

---

# PART 5 — MT5 TESTER GOTCHAS

Each of these cost at least an hour.

1. **MT5 reads inputs from `MQL5/Profiles/Tester/<Expert>.set`, NOT from the `.mq5`
   defaults.** Changing a default in source does not change what the tester runs — and it
   leaves the EA wrong the moment it is dragged onto a chart. After editing defaults,
   **read the source back and verify.**

2. **STRING inputs in a `.set` take a BARE value.** Numbers and bools use
   `name=value||start||step||stop||optimise`. A string does not — MT5 took
   `oanda_archive.csv||||||N` as the literal filename.

3. **`Optimization=1` is slow-complete. `Optimization=2` is GENETIC** and stops early — it
   ran 176 of 5,280 passes and looked finished.

4. **Reports: bare filename only.** Given an absolute path MT5 silently writes **nothing**.
   Pass a bare name and fetch the file afterwards.

5. **Reports are sometimes UTF-16 and sometimes UTF-8**, in the same folder. Sniff the BOM:
   ```python
   raw = path.read_bytes()
   text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")
   ```

6. **MT5 uses spaces as thousand separators** — `"1 490.00"`. A naive token split reads
   `1`. Strip spaces before `float()`.

7. **A swept BOOL arrives as `"true"`/`"false"`** in the optimisation XML and `float()`
   throws — which silently discarded every row of a 3,600-pass sweep.

8. **`ExecutionMode` is ABSENT unless you write it, and its default is IDEAL.** Zee,
   2026-08-13: *"u selected ideal zero latency during testing, while in real, we have a
   spread / latency etc."* He was right — no ini this project ever wrote contained the key,
   so every result before that used instant fills.
   ```
   ExecutionMode=0     ideal, no delay      <- the silent default
   ExecutionMode=163   163 ms send-to-fill  <- our measured live median
   ExecutionMode=-1    random delay
   ```
   **Real-tick mode already models SPREAD** (it replays the broker's own recorded bid/ask);
   it is only the send-to-fill delay that is missing. Use `--delay` in `mt5_headless.py`.
   Our own `Common/Files/shano_open_log.csv` measures the real number on live fills:
   **median 162.6 ms, p90 197 ms, p99 566 ms**, so do not invent one.

   **Measured effect, both EAs, Aug and Mar (real ticks, 0.02 lots):** at 0 / 163 / 200 /
   500 ms, ZeeUHV goes +1.40 → +1.48 per trade in August and −2.34 → −2.50 in March;
   NullEntry stays flat at −0.39 → −0.41. **The ranking is identical at every delay.**
   500 ms of gold is roughly 0.02–0.05 points against a 1-point target — noise, not drag.

   **What it still does NOT model:** requotes, rejections and partial fills. Delay only
   moves the price under your order.

9. **The tester needs a logged-in trade server**, even for a custom symbol.

9. **A custom symbol needs `bases/symbols.custom.dat`**, not just `bases/Custom/history`.
   That 4 KB registry file is the whole difference between working and `symbol not exist`.

10. **Adding code changes results even when the code is switched OFF.** The Watcher
    defaulted to `false`, its guard returned on the first line, and the result still moved
    from **1,608 trades / 93.28% / +$2,599.10** to **1,665 / 69.43% / −$779.90**. Removing
    it restored the number to the cent. **The mechanism is still not understood.**
    > **After adding ANY code, re-run the baseline and confirm it reproduces exactly,
    > before testing anything new.**

---

# PART 6 — THE CHECKLIST

Before believing any test result:

- [ ] **`Bars` ≈ the window's expected bar count?** (~1,380/trading day on M1 gold) — a short
      run is a clean-looking report about a different experiment (Part 11)
- [ ] **`Equity Drawdown Relative` < 90%?** Above that the account died, the run stopped
      early, and the net is CENSORED at the deposit — not a measurement (Part 11)
- [ ] `Ticks / Bars > 50`? (real ticks, not a guess)
- [ ] Does the baseline still reproduce to the cent after my code change?
- [ ] Same date range as whatever I am comparing it to — **and the same `Bars`?**
- [ ] What does `NullEntry` score with the same exits?
- [ ] Has the winner been frozen and run on data the search never saw?
- [ ] Am I ranking by expectancy, not win rate?
- [ ] Did any config produce results *identical* to another? (that is a bug)
- [ ] Did the run actually write a report, or did it time out?
- [ ] Do the numbers reconcile? (`E × N` should equal net profit)

---

# PART 7 — REPRODUCING THE KEY RESULTS

```bash
# the honest test — real ticks, live days
py monitor/mt5_headless.py --ea ZeeUHV --symbol XAUUSD --from 2026.08.10 --to 2026.08.13 --model 4

# the control — does a no-rules EA score the same?
py monitor/mt5_headless.py --ea NullEntry --symbol XAUUSD_BIG --from 2026.02.12 --to 2026.05.27

# a parameter sweep (edit Profiles/Tester/ZeeUHV.set first)
py monitor/mt5_headless.py --ea ZeeUHV --optimize --symbol XAUUSD_BIG --from 2026.02.12 --to 2026.05.27
py monitor/read_opt.py --top 12

# what the EA actually sees (volume, ranges) — trades nothing
py monitor/mt5_headless.py --ea TapeProbe --symbol XAUUSD --from 2026.08.06 --to 2026.08.12
```

The rig is a portable clone of the Blueberry terminal at `C:\mt5_rig`, run with
`/portable`. It never touches the live terminal. See `THINGS_TO_REMEMBER.md`.

---

# PART 8 — WHAT IS STILL UNKNOWN

Recorded so nobody mistakes an open question for a settled one.

- **How unusual is August?** Only two real-tick periods have been measured: March
  (85.27%, −$2,618) and August (100%, +$430). Two samples is not a distribution. **This is
  the most valuable outstanding measurement** — it decides whether this is a strategy or a
  season.
- **Why did the Watcher change results while disabled?** Reproducible in both directions,
  mechanism unexplained.
- ~~**Does the loss-cheapness edge survive real ticks?**~~ **ANSWERED 2026-08-13 — and the
  answer is no.** The real-tick `NullEntry` control was finally run over four fortnights at
  matched exits and lot size:

  ```
                          trades    win%        net    E/trade
  ZeeUHV (his rules)         836              -1,225.58   -1.466
  NullEntry (NO rules)     1,329                -314.44   -0.237
  ```

  **The entry is worse than random.** The loss-cheapness half is still true — ZeeUHV's
  average loss is smaller in every period — but its **win rate is LOWER than random in
  three of the four** (85.27 vs 92.22, 81.61 vs 90.55, 88.00 vs 93.58). It beats random
  only in August. Full table and caveats in
  [`daily_reports/_LATEST/LATEST_REPORT.md`](../daily_reports/_LATEST/LATEST_REPORT.md) §1.8.

  **The lesson for this page:** the 2026-08-12 conclusion "the edge is picking trades that
  are cheap to be wrong about" was drawn at 4 ticks per bar and did not survive real ticks.
  A control experiment is only as good as its tick model, exactly like everything else here.


---

# PART 9 — VOLUME: WHAT IT ACTUALLY IS (corrected 2026-08-13)

**XAUUSD is OTC. There is no central exchange, so NO retail broker publishes traded
volume.** Every "volume" number in this project — OANDA's and Blueberry's alike — is a
**TICK COUNT**: how many price updates arrived in that minute.

```
OANDA     median ~500   aggregates 20+ interbank feeds, so ticks arrive densely
Blueberry median ~200   only the updates crossing their own servers
```

**They are the same KIND of measurement at different densities.** For months this project
described OANDA's as "the real volume" — in the bridge docstring, in code comments, in
commit messages and in this file. That was wrong and is now corrected.

### Which to use, and why it is not a threshold problem

The usual warning is that a bot calibrated on one feed's thresholds will misfire on
another. **That does not apply here: this strategy uses no absolute volume threshold
anywhere.** Every rule is relative —
```
the UHV = the loudest bar in the retracement
the breakout must be QUIETER than the UHV
```
Ratios survive a change of scale. A denser feed simply resolves those comparisons more
finely.

### The real hazard, measured

Two feeds can disagree about **WHICH bar was loudest**.

```
of 10 live entries the EA made from Blueberry bars,
our OANDA archive agrees with exactly ONE.
```

Same minute, same rules, different answer about where the UHV sat. **That is the live
consequence of the feed difference, and it is not fixable by rescaling anything.**

### The decision on record
**Zee, 2026-08-13: use OANDA volume — his teacher specified it.** The denser feed is the
better estimate of where activity concentrated, which is what a UHV is meant to identify.
`zeeuhv_brain.py` (v3) reads OANDA and is the engine that honours this. `ZeeUHV.mq5` on a
broker chart reads that broker's ticks and does not.

*(For genuinely traded volume, VSA traders use COMEX Gold futures (GC), which is
exchange-traded and publishes real contract volume. We do not have that feed.)*


---

# PART 10 — THE BRANCHING DISCIPLINE

Zee, 2026-08-13: *"the diamond branch stays untouched with all rules preserved as is on
the last 10 trade setups. what we're doing is branching (like searching in a tree a new
version that is better) and we revert to the diamond's own rules if these don't hold."*

```
diamond            THE BASELINE. The exact rules behind 12 live setups, 12 wins,
                   +$570.40. Never edited. Everything reverts here.
goal_achieved      SEALED — git hooks refuse commits
feature/*          experiments. They must EARN their way in.
```

## The rules of the search

1. **Never edit the live EA to run an experiment.** A new rule gets its own file and its
   own magic number — `ZeeUHV_v12.mq5` is 88098, `ZeeUHV_v2.mq5` is 88095, the baseline is
   88094. Two EAs must never be able to manage each other's positions.

2. **After ANY edit to the baseline's source, restore it and confirm it is byte-identical
   to `diamond`.** This is not paranoia. On 2026-08-12 the Watcher was added to
   `ZeeUHV.mq5`, defaulted to `false`, guarded on its first line — and moved the result
   from 1,608 trades / 93.28% / +$2,599.10 to 1,665 / 69.43% / -$779.90. Dead code that
   moves live results is not dead.
   ```bash
   git show diamond:mt5/ZeeUHV.mq5 > mt5/ZeeUHV.mq5
   py monitor/deploy_ea.py ZeeUHV
   git diff diamond -- mt5/ZeeUHV.mq5     # must print nothing
   ```

3. **The compiled .ex5 matters as much as the source.** An attached EA keeps running the
   binary it was loaded with, so recompiling looks harmless — until MT5 restarts and
   silently picks up the new one. Recompile the BASELINE back into the live terminal after
   any experiment.

4. **A change is only promoted when it wins in a kind period AND a hostile one, on real
   ticks.** Two periods, one of each. Improving only in the good one is what a favourable
   fortnight looks like.

5. **A rule from Zee's own labels is not overridden by a measurement alone.** Doctrine and
   data disagreeing is HIS call to make, and the disagreement gets recorded either way.

## Worked example — the body filter, 2026-08-13

```
                    AUGUST (kind)              MARCH (hard)
peak  body    trades  win%      net      trades  win%       net
 on   0.5        38  100.00%   +$430      224  85.27%   -$2,618   <- baseline
 on   0.0       123   97.56% +$1,257      585  91.28%     -$571   <- better in BOTH
OFF   0.5        90   91.11%    -$63      380  86.58%   -$3,918
OFF   0.0       207   87.44%   +$199      706  89.94%   -$3,967
```

> ⚠️ **This table has NOT been re-audited (2026-08-13).** Its August baseline is the
> 2,758-bar run (Part 11), and its two −$3,9xx March cells are close enough to the $4,123
> deposit to be suspected stop-outs rather than measurements. The *direction* of the body
> result has survived three separate framings and is probably right; the **numbers need
> re-running with `Bars` and `Equity Drawdown Relative` checked** before they are quoted.

Removing the body filter improves the net, the win rate and the average loss, in both a
kind period and a hostile one. It passes rule 4. **It has still not been promoted**,
because the body filter is Zee's own rule and rule 5 applies.

The fine sweep shows there is **no compromise value** — the relationship is monotonic in
both periods, so no setting keeps "strong candle" while capturing the benefit (same
re-audit caveat as above applies to these figures):

```
body    AUGUST  trades  win%       net       MARCH  trades  win%       net
0.0             123   97.56%   +$1,257              585   91.28%     -$571
0.1             119   97.48%   +$1,213              520   90.19%   -$1,432
0.2             100   97.00%     +$953              454   88.77%   -$2,162
0.3              77   96.10%     +$690              389   86.89%   -$2,861
0.4              59   96.61%     +$555              293   85.32%   -$2,820
0.5              38  100.00%     +$430              224   85.27%   -$2,618   <- shipped
```

Note the trap in that table: **0.5 has the highest August win rate (100%) and the worst
August profit.** Ranking by win rate would pick exactly the wrong row — the same lesson
NullEntry taught, appearing again in live data.

Meanwhile the peak rule — which he correctly identified as absent from his labels — turns
out to be load-bearing: removing it is worse in both periods. **Kept.**


---

# PART 11 — THE RUN ITSELF CAN BE A LIE (2026-08-13)

Parts 1–10 assume that once a report exists, it describes the experiment you asked for.
**Twice today it did not.** Both faults produce a clean report, a plausible number, and no
error anywhere.

## 11.1 A run can cover less of the period than you asked for

Two August runs. Diffed input by input — **the configurations are identical**:

```
ZeeUHV_v13_004725    2,758 bars   217 tk/bar    38 trades   100.00%   +$430.00
ZeeUHV_v13_021210    4,137 bars   215 tk/bar    63 trades    93.65%   +$430.80
```

Same `--from`, same `--to`, same EA, same `.set`. The first ran while the rig was still
downloading tick history and silently tested **two days of a three-day window**.

Both pass every check in Part 6 as it stood. Both pass `Ticks/Bars > 50`. The nets even
agree to within a dollar — pure coincidence, and the reason it survived a week of being
quoted as the project's flagship result.

**The check:** M1 gold produces roughly **1,380 bars per trading day** (23h). Multiply by
the trading days in the window and compare to `Bars` before reading anything else.

```
Aug 10-13  ->  3 days  -> ~4,140    (4,137 = complete;  2,758 = two days)
Mar 2-16   -> 10 days  -> ~13,800   (13,788 = complete)
Apr 1-15   ->  9 days  -> ~12,420   (Good Friday Apr 3 closed; 12,407 = complete)
May 1-15   -> 10 days  -> ~13,800   (13,788 = complete)
```

**A run's bar count also grows as the rig downloads more history, so two runs done hours
apart are not automatically comparable.** Record `Bars` beside every number.

## 11.2 A run can end because the account died — and the net is then censored

The tester deposit is **$4,123**. A cluster of results landed at −$3,766 … −$4,057, all
with equity drawdown 92–98% and truncated bar counts:

```
run                    net        eq DD     bars / expected   what it really is
v13_021847        -4 000.60      97.13%     11,565 / 12,407   bankrupt, April
v14_012937        -4 039.60      98.06%      5,308 / 12,407   bankrupt at 43%
ZeeMulti_015952   -4 001.30      97.21%      4,432 / 13,788   bankrupt at 32%
v14_012737        -3 766.10      92.05%      1,591 / 13,788   bankrupt at 12%
```

**−$4,000 is not a loss, it is the floor of the instrument** — the most the account can
possibly lose. Two configurations that both print "−$4,00x" may be nowhere near equally
bad, and neither number can be averaged, ranked, or put in a ratio.

**It is systematically biased toward the configurations you are most interested in.** The
higher the trade frequency, the sooner the account dies, the shorter the run — so every
"more trades loses money" conclusion drawn from these is confounded. That is precisely the
family of change worth testing.

**The check:** `Equity Drawdown Relative > 90%` → discard the net, report it as a
bankruptcy, and if the configuration still deserves a fair trial, re-run it at a lot size
small enough to survive.

## 11.3 The rule

> **Before reading `Total Net Profit`, read `Bars` and `Equity Drawdown Relative`.**
> The first tells you whether the experiment happened. The second tells you whether the
> number means anything. Only then does the strategy result exist.

Both faults belong in Part 4's family — **a confident, clean-looking result produced by
something that did not do what it was asked.** That remains the dominant failure mode of
this project, and it is now six for six.


## Part 12 — A FRESHLY PUBLISHED DAY CAN BE CACHED HALF-BAKED (2026-08-18)

Polling the tester for the just-closed day (Aug 17) every 20 minutes caught the broker
MID-PUBLICATION: the rig cached bars that had highs/lows but NO CANDLE COLORS
(open == close), and both EAs replayed the day with ZERO trades — while the live
terminal's own record of the same day is 99.1%% colored. Bars and Ticks/Bars BOTH
looked healthy (1,379 bars, 197 t/b), so the existing coverage checks passed.

The cache never heals itself. Fix: delete bases/<server>/ticks/SYMBOL/YYYYMM.tkc and
history/SYMBOL/YYYY.hcc, let the rig re-download.

RULE: before trusting a same-day or next-morning replay, check the pipeline census —
if "no valid retracement origin" swallows the day (origins are near-universal on real
data: ~1%%), the data is half-baked and the run is VOID, whatever Bars says.
