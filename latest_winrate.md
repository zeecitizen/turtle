
# 🚨 THE WIN RATE WAS NEVER THE EDGE (2026-08-12)

Zee: *"but isnt it the fact: that your tests don't even apply to our trades, that you're
unaware on why the trades win in the first place?"*

He was right, and the control experiment settles it.

## The control: NullEntry — no strategy at all

`mt5/NullEntry.mq5` has no rules. It opens a position every 30 minutes, alternating
direction, with the IDENTICAL stop, target and hold as ZeeUHV. Same 103 days:

```
                     trades    win%    avg WIN   avg LOSS   worst    net
NullEntry (no rules)  1,716   92.42%    $9.99    -$154.80   -$723   -$4,277
ZeeUHV (his rules)    1,608   93.28%    $9.98    -$114.58   -$200   +$2,599
```

**Firing at nothing wins 92.42%.** The entire UHV detection adds **0.86 points** of win
rate. The 93% is not the strategy — it is the GEOMETRY. A 1-point target against a
20-point stop over 60 minutes wins ~92% from any entry, because gold touches a dollar
constantly. (Brownian approximation: 20/(20+1) = 95%.)

**So the 11-setup live streak proves nothing about the strategy. Random entries would
have produced it too.**

## Where the $6,876 actually is

Both engines average **$9.98 a win**. The difference is entirely in the losses:

```
average loss   null -$154.80   ZeeUHV -$114.58    ($40 cheaper)
worst trade    null -$723.10   ZeeUHV -$200.00    (3.6x smaller)
```

Expectancy per trade:
```
null    (0.9242 x 9.99) - (0.0758 x 154.80) = -$2.50
ZeeUHV  (0.9328 x 9.98) - (0.0672 x 114.58) = +$1.61      x 1,608 trades = +$2,589
```

**THE EDGE IS NOT PICKING WINNERS. IT IS PICKING TRADES THAT ARE CHEAP TO BE WRONG
ABOUT.** A genuine UHV sits at a level price respects — heavy institutional volume at
that price acts as friction — so a failed breakout chops in the absorption zone instead
of free-falling through empty air.

## What this invalidates

- **Every sweep ranked by win rate was ranking noise.** The geometry produces ~92%
  whatever the rules say.
- **"93.3%" was never evidence the strategy works.**
- **The live streak is not confirmation.** It is what the geometry does.
- **It also explains the two-day contradiction.** Broker data and OANDA data give
  similar WIN RATES and opposite MONEY, which is impossible if the win rate were the
  edge — and obvious once the edge is the loss distribution.

## What replaces it

`OnTester()` now returns **expectancy per trade, penalised by the worst single loss**,
so a configuration that earns by risking one catastrophic trade cannot outrank one that
never has a big loser. Win rate is no longer an optimisation target and should never be
one again.

---

# LATEST WIN RATE — 93.3%, MEASURED BY MT5, NOT PYTHON

**Date:** 2026-08-10 · **Branch:** `profitable_2026_08_10_tested` · **Frozen at commit:** `6e2a82d`
**EA:** `mt5/ZeeUHV.mq5` (450 lines) · **compiled .ex5 sha256 begins** `560be3c800ac0fb3`

Zee: *"i hope you can cementize in concrete these results and their code... so that in
future when we both are losing track or repeating the same investigation we know that
MT5 strategy tester's testing (not python) gave us a worthwhile result."*

**This page is that record. Every number below came from MT5's own Strategy Tester with
real spread and real execution. No Python figure appears anywhere on this page.**

---

# 1. THE RESULT

```
                        trades     win%         net        max drawdown
103 days (in-sample)     1,608    93.28%   +$2,599.10        45.7%
Aug 5-10   (UNSEEN)         26   100.00%     +$260.00         6.5%
Feb 11     (UNSEEN)         26   100.00%     +$260.00         5.5%
```

**1,608 trades is the largest sample this project has ever measured.** The two UNSEEN
rows are datasets the optimiser never touched: the configuration was frozen first and
nothing was retuned afterwards.

```
base 0.10  ->  +$2,599 per 103 days  =  about $25/day   (demo, $4,123)
base 0.02  ->    +$520 per 103 days  =  about  $5/day, drawdown ~9%   ($500 real)
```

---

# 2. THE EXACT CONFIGURATION

Every value is a default inside `mt5/ZeeUHV.mq5`, verified by reading the source back
after compiling:

```
InpLots          0.10     base lot; each diamond ticket is this same size
InpMagicNumber   88094
InpStopPts       20       <- 20, not 9. Section 4.
InpTargetPts     1        <- Zee's call. Every high-win-rate config uses TP 1.
InpUhvBodyMin    0.5      <- the strongest single filter. Section 5.
InpTrendLook     20
InpPivot         2
InpRetraceBack   20
InpRequireTrend  true     <- the trend gate STAYS ON. Section 6.
InpMaxHoldMin    60       <- 60, not 30. Section 4.
InpMaxOpen       1
InpCooldownBar   3
InpMaxGapSec     300
InpUseDiamonds   true
InpStackLots     true
InpStackStep     0.0      <- every ticket 0.10; diamonds buy TICKETS, not bigger ones
InpMaxRisk       0.0      <- NO CAP. Capping halves efficiency. Section 6.
InpMinTrades     15       (OnTester guard only; does not affect trading)
```

**For the $500 real account set `InpLots = 0.02` and change nothing else.**

---

# 3. THE EXACT DATA

| symbol | source file | bars | period | median volume |
|---|---|---|---|---|
| `XAUUSD_R3` | `tester_xau_real.csv` | 2,409 | 2026-08-05 -> 08-09 | 518 |
| `XAUUSD_BIG` | `tester_xau_big.csv` | 100,000 | 2026-02-12 -> 05-27 | 176 |
| `XAUUSD_F11` | `tester_xau_feb11_warm.csv` | 2,879 | 2026-02-10 -> 02-11 | 1 (warm-up bars included) |

All three sit in `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files`.
Tester: **M1, "1 minute OHLC" modelling, deposit $4,123, leverage 1:500,
BlueberryMarkets-Demo spread and execution.**

**The volume columns are NOT the same measurement.** `XAUUSD_R3` carries real OANDA
traded volume (median 518); `XAUUSD_BIG` carries broker tick counts (median 176). Every
UHV rule is RELATIVE — loudest bar in the window, breakout quieter than the UHV — which
is why the result transfers. **No absolute volume threshold may ever be taken from one
and used on the other.**

---

# 4. HOW IT WAS ACHIEVED — the actual sequence

**Step 1 — the detector was rebuilt from Zee's own 146 labels.**
`monitor/setup_labels/zee_labels.json` holds 146 setups he annotated in his own words.
67 distinct rule-statements were mined from them, and every check in `ZeeUHV.mq5` carries
his sentence quoted above it. Two things every earlier detector missed, and which he had
already complained about repeatedly: **the BODY must clear the previous extreme (a wick
does not count)**, and **the UHV search is scoped INSIDE the retracement**, so a louder
candle outside it can never be chosen.

**Step 2 — the tester was found to be lying about volume.**
`mt5/TapeProbe.mq5` showed `iVolume` returning a constant 4 while `iRealVolume` returned
572, 454, 270, 174. MT5 overwrites `tick_volume` with its own synthesised tick count and
preserves `real_volume`. **Every EA we owned had been comparing 4 against 4.** Fixed with
a `BarVolume()` helper across 43 call sites. **Nothing measured before this fix is valid.**

**Step 3 — searched on the LARGE sample, validated on the small.**
3,600 configurations swept on the 103-day set (440+ trades per pass); the winner was
then frozen and run on two datasets the search had never seen. **This order is the whole
lesson — section 8 shows what happened when it was done the other way round.**

**Step 4 — Zee's "total control" question found the stop and the hold.**
He asked whether every UHV breakout gives a small bump, so that with total control we
would profit ~94% of the time. Measuring that ceiling directly:

```
  stop   9pt, wait  30min   88.44%   +$139   worst -$90       drawdown 15%
  stop  20pt, wait  60min   93.12%   +$597   worst -$200      drawdown 17%  <- best money
  stop  40pt, wait 120min   95.56%   +$249   worst -$400      drawdown 26%
  stop  80pt, wait 240min   96.92%   +$508   worst -$800      drawdown 31%
  stop 200pt, wait 600min   98.07%   +$268   worst -$1,605    drawdown 48%
```

**His claim is CONFIRMED — 98% of UHV breakouts eventually give the $1 bump.** But the
money does not follow the win rate: 98% earns less than 93%, because the few that never
come back grow enormous. **Perfect control is paid for in the size of the rare loss.**
Stop 20 / hold 60 is the peak of the money curve, not the peak of the win rate.

---

# 5. THE FIVE THINGS THAT MOVED THE NUMBER — four of them were Zee's

**1. The volume fix (mine).** Without it nothing worked at all: every detector was blind,
and `NsndF11` reported `signals=0` on a day full of setups.

**2. `InpUhvBodyMin` — "UHV should also be a strong candle" (his).** The strongest single
filter measured:
```
body 0.2: median win 89.4% · 48 trades · +$103
body 0.3: median win 89.6% · 43 trades · +$100
body 0.4: median win 89.3% · 38 trades ·  +$95
body 0.5: median win 88.9% · 37 trades ·  +$85
body 0.6: median win 95.2% · 26 trades · +$110
```

**3. `InpTargetPts` 1 — "if 96% reach +$1, let each trade bring in the $1" (his).**
Every high-win-rate configuration in every sweep uses TP 1. I argued for TP 3 twice and
was wrong both times.

**4. Diamonds as extra TICKETS at fixed size (his).** Six times the profit at an
unchanged win rate — and provably selection, not leverage:
```
flat 0.30 lots   +$416   drawdown 40%
diamonds @0.10   +$821   drawdown 45%
```
If diamonds were only size, those two lines would match. They do not.

**5. Stop 20 / hold 60, from his "total control" question (his).** Three times the profit
of the previous best, at the same drawdown.

---

# 6. THINGS WE PROVED DO **NOT** WORK — do not re-investigate these

| idea | verdict |
|---|---|
| **Resting a LIMIT at the UHV level** instead of chasing | **-$593.10.** A limit only fills on trades that come BACK, and those are the worse half. 65 of 193 setups never filled and they were disproportionately the good ones. |
| **Opening the trend gate** (allowing ranging tape) | Looked like a huge win on 4 days (+$44 -> +$144). On 103 days **every** top config has the gate ON. Small-sample artefact. **Gate stays ON.** |
| **Escalating stack** 0.1/0.2/0.3/0.4 | Works, but 28% drawdown uncapped. Fixed 0.10 per ticket is better risk-adjusted. |
| **Capping the stack** (`InpMaxRisk` 0.10-0.30) | **Halves efficiency**: $9.30 earned per 1% of drawdown capped, $18.10 uncapped. The 3rd and 4th tickets are the BEST trades. Scale the base lot instead. |
| **Loosening rules to trade more** | Every loosening cost money: body 0.3 -> 7.1 trades/day, -$1,018; body 0.1 -> 9.7/day, -$2,256; ranging too -> 11.1/day, -$4,090. |
| **Removing MaxOpen / cooldown** | 441 -> 453 trades and +$139 -> -$29. Those twelve extra trades were poison. **The caps earn their keep.** |
| **Bigger lots to magnify the small win** | A pure multiplier on profit AND drawdown: 0.10/0.20/0.30/0.50 give +$139/+$277/+$416/+$693 at 15/28/40/60% drawdown. **The account is the limit, not the strategy.** |
| **Chasing 69 trades/day like Feb 11** | Only 26 lawful setups exist that day, and removing every limit changes the count not at all. His other 43 were OTHER strategies. **More engines, not looser rules.** |

---

# 7. HOW TO REPRODUCE IT — no human clicks

```bash
py monitor/mt5_headless.py --ea ZeeUHV --symbol XAUUSD_BIG --from 2026.02.12 --to 2026.05.27
py monitor/mt5_headless.py --ea ZeeUHV --symbol XAUUSD_R3  --from 2026.08.05 --to 2026.08.10
py monitor/mt5_headless.py --ea ZeeUHV --symbol XAUUSD_F11 --from 2026.02.10 --to 2026.02.12
py monitor/mt5_headless.py --ea ZeeUHV --optimize          # 5,280-pass sweep, ~30s
py monitor/read_opt.py                                     # rank the newest sweep
```

The rig is a **portable clone of the Blueberry terminal at `C:\mt5_rig`**, launched with
`/portable`. It owns its data folder and never touches the live terminal. Full details
and its four gotchas are in `THINGS_TO_REMEMBER.md`.

**MT5 reads its inputs from `MQL5/Profiles/Tester/ZeeUHV.set`, NOT from the `.mq5`
defaults.** Changing a default in source does not change what the tester runs. This cost
three runs before it was understood, and it left the EA's own defaults stale for hours
while every test passed — they would have been wrong the instant the EA was dragged onto
a chart. **After changing defaults, always read the source back and verify.**

---

# 8. THE METHODOLOGICAL LESSON — the one that must never be forgotten

Earlier the same day, an optimisation on **four days** produced **96.4% and +$580**. It
had a 311-pass region above 90% and a six-stop plateau, and I offered both to Zee as
proof it was not overfitting.

Run on unseen tape, everything frozen:

```
IN-SAMPLE    Aug 5-10  (where it was found)     +$580.00     55 trades   96.36%
OUT-SAMPLE   Feb 12 - May 27 (103 days)       -$4,071.70    768 trades   82.81%
OUT-SAMPLE   Feb 11                             -$180.00     36 trades   83.33%
```

**A plateau proves stability WITHIN a sample and says nothing whatever about another
sample.** That $4,071 would have been real money, and it was caught only because Zee
asked for the out-of-sample run.

> **THE RULE: search on the largest dataset available, then freeze everything and
> validate on data the search never saw. A configuration that has not survived unseen
> tape is not a result.**

---

# 9. WHAT IS STILL NOT PROVEN

- **It has never traded live.** 1,608 tester trades is the strongest evidence this
  project has ever had, and a live fill remains a different animal — slippage, requotes,
  latency, and a broker that is not a simulation.
- **The honest next step is one week at `InpLots = 0.02` on the real account.** If about
  15 of every 16 come back green, it is confirmed where it counts, for roughly $30 of risk.
- **The live receipts still disagree about conviction sizing.** `oanda_live_matcher.py`
  carries a verdict from 2026-08-06 (n=14): *"big lots 36% WR, -$219.90; 0.10 flat 71%
  WR, +$76.60."* Fixed-0.10 tickets are not the same thing as the big lots that failed
  then — but the warning stands until fresh fills settle it.
- **45.7% drawdown at base 0.10 is aggressive.** At 0.02 it is about 9%.

---

# 10. THE FILES THAT MATTER

```
mt5/ZeeUHV.mq5                        the EA — his rules, his words quoted above each check
monitor/zee_uhv.py                    the same rules in Python, for analysis only
monitor/mt5_headless.py               runs MT5's tester with zero clicks
monitor/read_opt.py                   reads and ranks an optimisation report
monitor/doctrine.py                   stops a Python number being quoted as evidence
monitor/setup_labels/zee_labels.json  his 146 labels — the source of every rule
THINGS_TO_REMEMBER.md                 the rig, and the things we keep forgetting
```

## 🚫 EXIT INTERFERENCE, TESTED A THIRD TIME AND REFUTED AGAIN (2026-08-12)

Zee noticed a live trade that took **56 minutes** to reach its target where the median is
1.8 minutes, and asked whether that was normal. Two VSA reports then proposed cutting the
hold time and adding staged exits. Both were tested. Both are wrong for this strategy.

### The hold-time sweep, 2 to 60 minutes, everything else frozen
```
   5 min   -$1,742          25 min     +$198
   8 min     -$918  <- report 1        45 min   +$1,450
  10 min      -$24  <- report 2        60 min   +$2,599   93.28%   <- shipped
  15 min     +$935
```
**The curve rises almost monotonically with time.** Cutting to 8 minutes turns +$2,599
into -$918 — a **$3,517 swing** — and the win rate falls from 93.28% to 87% or worse.

**Why the reasoning fails even though the VSA theory is sound:** both reports argued that
90% of winners arrive within 3.4 minutes, so 8 minutes is generous. True, and it is the
trap. The fast winners are already banked; a short clock does not touch them. What it
cuts is the SLOW winners. In this market a drifting trade usually still reaches the
target — just later.

### The volume-fade exit, the one proposal that deserved a test
It uses no clock: it closes when institutional effort dies, measured against the UHV's
own volume. Built as `InpFadeExit`, swept across 45 configurations (threshold 0.20-0.60,
2-6 consecutive dead bars). Profit relative to the baseline:

```
   frac \ bars      2      3      4      5      6
        0.20      -242   -213     +0     +0     +0
        0.30      -691   -944   -960   -933   -834
        0.35      -718   -765  -1192   -916   -610     <- the reports' recommended band
        0.50     -1164   -256   -632   -700   -781
        0.60     -2235  -1373  -1052   +105   -103
```

**One cell of 45 beats doing nothing, by $105 — and every neighbour it has is negative**
(-427, -1052, -103). That is a lone lucky cell, not a plateau, and it is exactly the
shape of the 96.4% that lost $4,071 out of sample. It also costs 2.7 points of win rate
(93.28% -> 90.56%) to earn 4% more money.

**5 configurations never fired at all. 39 lost money against doing nothing.**

### THE RULE, now established three independent ways
```
the Watcher (tick-by-tick invalidation)   avg loss $114 -> $19, win rate 93% -> 64%
v1.81 (the breakeven lock)                removed; the sweep said so
the volume fade (45 configs)              39 lose, 5 inert, 1 lucky cell
```
**Anything that closes a trade between the structural stop and the target costs money in
this strategy.** The 56-minute trade is not a defect to be engineered away — it is the
strategy working slowly, and it paid $82.90.

`InpFadeExit` stays in the code, default FALSE, with this measurement beside it.

**Method note:** after adding the fade code the baseline was RE-RUN before testing
anything, and reproduced 1,608 trades / 93.28% / +$2,599.10 exactly. That check exists
because the Watcher was also default-off and still changed the result.

---

## 🔴 OPEN CONTRADICTION — live says 100%, the tester says it loses (2026-08-12)

**Live, on the real Blueberry demo account:**
```
9 setups · 40 fills · 9W / 0L · +$437.70   over 24 hours, no loss yet
```

**The same EA, same symbol, same days, in MT5's Strategy Tester:**
```
XAUUSD, 1 minute OHLC   Aug 6-12    49.4%   -$566
XAUUSD, EVERY REAL TICK Aug 6-12    38.8%   -$356      (1,236,009 ticks, quality 100%)
XAUUSD, 1 minute OHLC   103 days    64.4%   -$4,030    drawdown 97.8%
```

**On the identical calendar days the two disagree completely** — the tester records
losing trades at 07:32 and 13:07 on Aug 11 where the live account took wins.

### What was ruled OUT
- **Not the volume feed.** TapeProbe on broker XAUUSD: `iVolume` varies (132, 88, 75,
  135…), `iRealVolume` is 0. The tester was NOT blind, and the live EA reads the same
  tick counts.
- **Not tick modelling.** Every-tick with real broker history was WORSE (38.8%), not
  better, so the four-ticks-per-bar theory is dead.
- **Not the configuration.** The tester's own order rows show SL 20 below entry and TP 1
  above — exactly as shipped.
- **Not a lucky-streak illusion of size.** 40 fills are only 9 setups, because a stack
  wins or loses together. At the tester's 64% a 9-setup run has a 1.9% chance; at 93%
  it has 53.6%.

### What is UNRESOLVED
The prices do not reconcile. The rig, the live fills and our OANDA archive give three
different levels for what should be the same moment. Either the timezone arithmetic is
wrong or **the rig's freshly-downloaded XAUUSD history is not the market the live
account traded** — and that rig produced a 0.247-second "test" and a mis-parsed report
in the same session, so it is not above suspicion.

### THE DECISION (Zee, 2026-08-12)
> *"i think the setup we already have, maybe running on diff data etc, but is highly
> successful at 100% winrate since 24 hours+. Thus we keep this setup as is for now."*

**Left running, unchanged.** It is a demo account, so nothing is at risk, and the live
sample is the only evidence gathered from reality rather than from a model. The concern
was raised twice and answered twice; this is his call and it stands.

**What decides it:** the next several setups. Losses arriving at roughly one in three
would vindicate the tester. Reaching 15+ setups still unbeaten makes 64% very hard to
believe and means the backtest is measuring the wrong market.

`monitor/zeeuhv_live.py` prints both predictions beside the live number on every run, so
whichever way it turns, we see it turn.

---


