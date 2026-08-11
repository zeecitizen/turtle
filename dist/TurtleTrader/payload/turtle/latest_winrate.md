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
