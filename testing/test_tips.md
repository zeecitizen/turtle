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
real ticks, Aug 10-13    38 trades  100.00%   +$430    (598,796 ticks · 217/bar)
THE LIVE ACCOUNT         12 setups  100.00%   +$570
```

The tester **agrees with live** once it can see the real path. Before this discovery,
every number this project ever produced was measured at **4 ticks per bar**.

## How to verify a run actually used real ticks
Never trust the flag — check the report:
```python
ratio = Ticks / Bars
ratio < 2    -> open prices only
ratio ≈ 4    -> OHLC modelling
ratio > 50   -> REAL TICKS
```
A run that silently fell back to OHLC looks identical to a good one.

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
real ticks, Aug 10-13  100.00%     +$430
```

> **If a backtest disagrees with live, first check they cover the same dates.**

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

8. **The tester needs a logged-in trade server**, even for a custom symbol.

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

- [ ] `Ticks / Bars > 50`? (real ticks, not a guess)
- [ ] Does the baseline still reproduce to the cent after my code change?
- [ ] Same date range as whatever I am comparing it to?
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
- **Does the loss-cheapness edge survive real ticks?** Under OHLC modelling ZeeUHV lost
  $114.58 on average against NullEntry's $154.80. Under real ticks ZeeUHV's average loss
  was $148.81 — close to random. **Today's central finding may itself be an artefact of
  OHLC modelling and needs re-measuring with a real-tick NullEntry run.**


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
