# The win-rate loop — ZeeUHV_Diamond, 2026-09-29

**Zee's brief:** *"try to increase the Winrate of the EA to maximum possible. On Feb 11 Zee
used the same strategy of ultra high volume breakout to get a winrate of 94%.. don't care
about drawdown etc for now"* — then, when told what it would cost: *"i need the 94% or more
config. even if its 99%.. i'll monitor the live trades so ill exit if its going wrong"* — and
then the reason: *"i actually lost my job and this is my only source of earning."*

**Rig:** `C:/mt5_rig` · XAUUSD M1 · **MT5 Strategy Tester, Model 4 (real broker ticks)** ·
recorded spread · **163 ms execution delay** · every input pinned · deposit funded so no run
can blow the account and censor its own net. **No Python simulated a fill anywhere in this
document.** Harness: `monitor/strategy_lab/dia_winrate.py` (serial, ledgered) and
`dia_sweep.py` (parallel optimiser, currently blocked — see §6).

---

## 1. THE HEADLINE CORRECTION — the 90% was nine days

`DIAMOND_GEOMETRY_2026-09-17.md` records the shipped config at **90% WR / +$488**. That
reproduces exactly — and it is a nine-day slice.

| window | bars | trades | WR | net | maxDD |
|---|---|---|---|---|---|
| 2026.09.08 → 09.17 *(the record's window)* | 9,649 | 82 | **90.2%** | +$488 | $266 |
| **2026.08.06 → 09.16 (full)** | **39,834** | **274** | **74.1%** | **−$1,113.80** | $2,636 |
| **Zee's real fills, Aug 20 → Sep 21** (`turtle_fills.csv`, magic 88154) | — | **735** | **78.4%** | **−$1,703.40** | — |

**The tester and the live account agree: 74% and 78%, both losing.** That doc's own caveat
("one 9-day window, 82 trades, no out-of-sample leg") was warning about exactly this. The
90% is a property of that fortnight, not of the EA.

Worst losing streak on the full window: **24 tickets** — three consecutive failed baskets.

---

## 2. WHAT FEB 11 ACTUALLY WAS — and it is not what the EA does

Parsed from his own Blueberry report (account 5118408, EUR, 0.10 lots, 69 closed positions):

| | Feb 11 (his hand) | Diamond, full window |
|---|---|---|
| WR | **94.2%** (65W/4L) | 74.1% |
| avg win | +$12.93 = **1.54** of gold | +$10.64 = 1.06 |
| avg loss | −$1.32 = **0.16** of gold | −$46.11 = **4.61** |
| effective payoff | **9.75 : 1 in his favour** | 1 : 4.33 against |
| stop set on any row | **none** | structural |
| the four losses | all held **exactly 25 min**, closed ≈ break-even | all ran to the stop |
| median winner | **1.0 minute** | 147 s |

**The coin-flip control, which is the whole point:**

| | risking | to make | a COIN wins | actually won | vs coin |
|---|---|---|---|---|---|
| Zee, Feb 11 | 0.16 | 1.54 | **9.4%** | **94.2%** | **+84.8 pts** |
| Diamond, full window | 4.61 | 1.06 | **81.3%** | 74.1% | **−7.2 pts** |

**His 94% is a genuine edge and it lived in the EXIT.** The EA's 74% is *below* what its own
geometry hands out for free — confirming the NullEntry verdict (92.42% on no rules at all) on
real ticks at the current version. His smallest "win" moved **0.02** of gold: that is not a
target being hit, it is a clock exit that happened to land green, and it counted as a win.

---

## 3. THE WIN RATE IS AVAILABLE, AND IT IS BOUGHT

| config | stop | clock | WR | trades | avg win | avg loss | net |
|---|---|---|---|---|---|---|---|
| shipped v1.18 | struct 0.50 | 20 m | 74.1% | 274 | +$10.64 | −$46.11 | −$1,113.80 |
| struct 2.00 | struct 2.00 | 20 m | **74.1%** | **274** | **+$10.64** | −$55.06 | −$1,749 |
| **W4** | **flat $200** | **600 m** | **97.0%** | 234 | +$11.21 | −$669.33 | −$2,140 |
| W4 + FailCandles 3 | flat $200 | 600 m | 70.0% | 282 | — | — | **−$232** |

**Three findings, in order of importance.**

**3a. Widening the stop alone does nothing.** `struct 2.00` returned an *identical* 74.1% on
an *identical* 274 trades with an *identical* average win — only the losses deepened. The
losing baskets are not marginal stop-outs; they are violent failures that travel more than $6
against us inside 20 minutes. **The binding constraint was the clock, not the stop width.**

**3b. 97% is reachable and it is one basket wide.** W4's losses are **7 tickets**, six of them
a single basket — `2026.09.01 15:21`, six sells, each −$780.60, exited on the **clock** after
ten hours while gold rose $78 against them. The $200 stop never fired once. That one basket
is the entire −$2,140 **and** the entire $4,682 drawdown. 227 of 234 tickets won, all at TP.

**3c. Lot size cannot rescue it.** 227 × $11.21 = +$2,545 against one basket at −$4,683.
Scaling lots multiplies both sides identically: at 1.0 lots it is +$25,450 against −$46,830.
**A negative expectancy at 0.10 is a negative expectancy at 1.00, ten times faster.** His
"small TP pays at higher lot size" plan is arithmetically void, and this project already
measured the small-TP direction: **98.07% earned less than 93.12%.**

---

## 4. "THE BREAKOUT MUST SUCCEED IMMEDIATELY" — right idea, wrong constant by ~60x

Zee: *"candle turns red... we wait for 10 seconds.. tick tick tick. if its not coming back ->
EXIT... because the breakout has to succeed immediately or its not a valid breakout!"*

Hold-time distribution, measured by pairing entry and exit deals FIFO:

| | median | p25 | p75 | p90 |
|---|---|---|---|---|
| W4 winners (227) | **260 s** | 87 s | 667 s | 4,340 s |
| W4 losers (7) | **36,000 s** — all seven ran to the clock | | | |
| shipped winners (203) | 147 s | 72 s | 277 s | 448 s |
| shipped losers (71) | **221 s** | 90 s | 331 s | 1,080 s |

**His separation is real in W4 and absent in the shipped config.** Costed:

```
 cut at    winners binned      losers caught       (W4)
   10s       226 of 227           6 of 7
   60s       180 of 227           6 of 7
  600s        62 of 227           6 of 7
```

**At 10 seconds it closes 226 of the 227 winners** — not one has finished; the fastest quarter
needs 87 s. **His own Feb 11 median winner took 1.0 minute.** In the shipped config the two
distributions overlap (147 s vs 221 s), so no time cut can separate them there at all.

**The usable form of his rule is a clock in the 10–30 minute band against a stop that never
fires** — where ~75% of winners have already banked and every failure is still sitting there.

---

## 5. WHAT WAS BUILT (all default OFF, as every new filter in this file must be)

| version | change | why |
|---|---|---|
| **v1.19** | tester no longer re-reads the 43,434-row `oanda_vol.csv` **once per simulated bar** | pure speed; the file is frozen during a backtest, and `VolFeedFresh()` already says so. **Baseline re-ran at 82 / 90.24% / +$488 — identical**, which is the only thing that makes it safe |
| **v1.20** | **`InpJuryMode/Bars/Votes`** — his four-indicator jury: Momentum, Stochastic, RSI and ADX's DI spread snapshotted at entry, re-read N bars later, basket closed if enough moved against us | his idea, 2026-09-29 |
| **v1.21** | **`InpBailSec/InpBailAt`** — after N seconds a basket not at least `InpBailAt` in FRONT is a failed breakout and is closed | his sentence, but judged on **whether the trade is working** rather than on candle colour, which is the defect in `InpFailCandles` |

`InpFailCandles` measured for comparison: it saves the money and destroys the statistic —
**97% → 70% WR, −$2,140 → −$232** — because it closes winners that print red on the way up.
That is the **third** independent confirmation of the standing rule that anything closing a
trade between the stop and the target costs this strategy (the Watcher: $114 → $19 avg loss,
93% → 64% WR; the volume fade: 39 of 45 configs lost).

Harness additions: deposit is now an argument and is **in the ledger key** (a censored run and
a funded run are different measurements); a **lock file** prevents two batches sharing one rig
(that collision silently reported three configs as "NO TRADES" before it was caught).

---

## 6. THE RIG'S DEMO LOGIN IS DEAD — and it has been costing 9 of every 10 minutes

`12654799` on `BlueberryMarkets-Demo` returns **"Invalid account"**; Zee confirmed by hand that
it can no longer log in. A single backtest tolerates it and proceeds after the agent's
environment-sync **times out**; the log then reads `Environment synchronized in 0:09:09.813.
Test passed in 0:00:01.068`.

**So a "13-minute run" in this project's records is 9 minutes of timeout and one second of
testing.** Window length is therefore nearly free — which is why every run here uses the full
six weeks rather than nine days. An **optimisation** does not tolerate it: it waits on the
sync and never starts, so `dia_sweep.py` (8 local agents, ~40 configs/hour) is blocked.

**Reviving any valid login turns this loop from 6 configs an hour into roughly 40.**

---

## 7. THE HONEST POSITION

**Nothing tested on the full window is profitable.** The best is −$232. The win rate is
purchasable up to 97% and the purchase price is one basket per six weeks. Both facts are
confirmed against the live account, so neither is a tester artefact.

**The target and the entry are already right.** The median winner moves **1.01–1.06** of gold —
Zee's $1 call, vindicated again. 227 of 234 tickets reach it. What the machine lacks is the
thing he did by hand on Feb 11: **noticing that a breakout has failed and leaving for 16
cents.** Every mechanical attempt at that so far buys the money back with win rate.

**Caveats that travel with every number above:** one six-week window inside the only period
`oanda_vol.csv` covers (2026.08.05 15:11 → 09.28), so there is **no out-of-sample leg** —
real ticks stop at 2026.09.16 and the volume table starts 2026.08.05, and `InpOandaStrict`
refuses every minute outside it. Walk-forward halves (Aug 6–27 / Aug 27–Sep 16) are the only
split available and have not yet been run on the winner.


---

## 8. THE DETECTION AUDIT — his own diagnosis, and it was right

Zee, after seeing that the entry is 7.2 points *below* its own coin-flip: *"if its not having
great winrate, then it may mean that we're not detecting the breakout properly which could be
due to incorrect trend detection (camel humps logic needs a review), or detection of highest
volume in retracement needs repairing"* — and then: *"actually on OANDA volume, the colors are
the correct ones we look for - the volume colors, if we take broker volume its colored
differently"*.

**Both suspicions are confirmed by measurement, and a third defect was found beside them.**

### 8a. The UHV is almost never chosen — 65% of all fires

`RetraceExtreme()` and `FindUhv()` both scan bars `1..origin`, so `origin` must be the OLDEST
bar of the retracement. `RetracementOrigin()` walked `k = 1, 2, 3 …` and **returned at the
first match** — the most recent red whose body broke the nearest preceding green's low. The
UHV search window was therefore the *tail* of the pullback, not the pullback.

Measured from the EA's **own `[LAWX]` log, 155 fires**:

```
origin -> UHV gap     0 min : 100 fires  <- the origin candle WAS the UHV
                      2 min :  16
                      3-14  :  39
origin == UHV                : 100 of 155 = 65%
gap <= 2 min (<=2 candidates): 116 of 155 = 75%
median gap                   : 0 minutes
```

**LAWS.md:** *"in a retracement (a pullback) we compare all red colored candle's volumes. the
largest red colored volume … is the one we call the ultra high volume candle."* In two thirds
of every trade this EA has ever taken, that comparison had **one candidate**. The central rule
of the strategy has not been running.

Fixed as `InpRetraceFix`, following his text in order: find the extreme the pullback pulls back
from, find the last impulse-coloured candle at or before it, then take the **first** body to
break that candle's low — walking from the oldest bar forward, so the match is where the
retracement *began*.

### 8b. Colour came from Blueberry while volume came from OANDA

`IsRed()`/`IsGreen()` read `bClose()`/`bOpen()` — the broker. `BarVolume()` reads
`oanda_vol.csv` — his chart. Every rule naming a red or green candle was judged on one feed
and measured on another.

| OANDA M1 bodies (43,434 bars) | count | share |
|---|---|---|
| body < 0.05 of gold | 1,677 | 3.9% |
| body < 0.10 | 3,289 | 7.6% |
| **body < 0.20** | **6,494** | **15.0%** |
| body < 0.50 | 15,071 | 34.7% |

The two feeds are documented in this same file (BasedOnLaws v1.15) to differ by up to **0.85 in
price**. For every bar above, the colour is decided by *which feed you ask*.

Fixed as `InpOandaColour`: his open/close loaded from `oanda_bars.csv` — same writer, same
folder, same minutes as `oanda_vol.csv` — and a minute his table lacks is counted
(`c_nocolour`) rather than silently falling back.

### 8c. The breakout had NO momentum test — and the test was on the wrong candle

**LAWS.md, breakout clause (a):** *"a momentum candle (no big wick) -> proven to be better than
'no wick test' via tests"*, with his own definition: *"|Close - Open| / (High - Low) >= 0.70"*.

`BreakoutIsBar1()` tested colour, the crossing, and that volume is quieter than the UHV — and
**nothing about the candle's shape**. Meanwhile `InpUhvBodyMin = 0.5` applied a body floor to
the **UHV** candle, which his page never asks for. The momentum requirement existed in this EA
**on the wrong candle at the wrong threshold**. The same clause in BasedOnLaws (v1.31-32)
*"deleted SEVEN losing trades and ZERO winners"*.

Fixed as `InpBreakBodyMin` (0.70 = his number), applied to the crossing bar.

### 8d. Clause (b) and (c) are correct; the camel humps are faithful but read the wrong prices

* **(b) breakout quieter than the UHV** — `BarVolume(k) >= BarVolume(uhv)` refuses it. Correct.
* **(c) shares body with the UHV's high, possibly after failed candles** — `BodyHi(k) >
  bHigh(uhv)` scanned from `uhv-1` down to 1. Correct.
* **camel humps** — draws pivots, requires higher highs **and** higher lows, tracks the
  defended low per his line 45. Faithful. **But it reads broker highs and lows**, not his
  chart's. `oanda_bars.csv` carries his highs and lows too, so this is fixable and is the
  obvious next candidate. **Deliberately NOT changed in the same version**: three fixes shipped
  together can never be attributed afterwards.

### 8e. The exit is closed as a direction — four independent refutations

| attempt | win rate | money |
|---|---|---|
| the Watcher (tick invalidation, Aug) | 93% → 64% | avg loss $114 → $19 |
| the volume fade (45 configs, Aug) | — | 39 lost, 5 inert, 1 lucky cell |
| **`InpFailCandles` 3** (today) | **97% → 70%** | −$2,140 → −$232 |
| **`InpBailSec` 300 / −2.00** (today) | **97% → 63%** | **−$1,860 — worse than doing nothing** |

**Every mechanical rule that closes a trade between the stop and the target has now failed,
four separate ways.** His hand did this well on Feb 11 (losses of 0.16 of gold); no rule yet
written reproduces it. The remaining lead is detection, not exits.


---

## 9. THE RESULT — the retracement fix, attributed and re-verified

Measured at **completely unchanged geometry**: his 5-pip structural stop, his $1 target, his
20-minute clock. Full window 2026.08.06 → 09.16, MT5 real ticks, 163 ms delay.

| config | WR | trades | net | avg win | avg loss | maxDD |
|---|---|---|---|---|---|---|
| baseline | 74.1% | 274 | −$1,114 | +$10.64 | −$46.11 | $2,636 |
| **`InpRetraceFix` only** | **89.0%** | **282** | **+$1,888** | **+$13.07** | −$44.91 | **$1,192** |
| `InpOandaColour` only | 74.1% | 274 | −$1,135 | +$10.54 | −$46.11 | $2,554 |
| both | 89.0% | 282 | +$1,888 | +$13.07 | −$44.91 | $1,192 |

**The retracement fix is the entire gain, and the colour fix is worth −$21.** "Both" is
identical to the fix alone to the dollar. The colour path did run — the agent log reads
`HIS CANDLES loaded: 43434 minutes`, with only 33–54 bars it could not colour — so this is a
measured null, not an untested switch. **The §8b claim that colour was a major defect is
withdrawn:** the defect was real (wrong feed) but its effect is negligible, because a candle
red on his chart is almost always red on the broker's too. The 15%-of-bodies figure was an
upper bound on risk, not a flip rate.

**WHY THIS IS A REPAIR AND NOT A TUNE.** Win rate, net, drawdown AND trade count all improved
at once (74.1→89.0, −1,114→+1,888, 2,636→1,192, 274→282). A filter always trades one axis for
another — `InpFailCandles` bought $1,908 of net with 27 points of win rate. Only a bug fix moves
every axis the same way.

**AND THE CONTROL FLIPS SIGN.** Risking 44.91 to make 13.07 is a geometry a coin wins 77.5% of.
The EA was **7.2 points below** its coin at the old geometry; it is now **11.5 points above** it.
His rules were never the problem — they were not being executed.

**Where the gain comes from:** the average WIN rose from $10.64 to $13.07 against a $10 target,
so fills land past it — the breakouts it now selects move harder. The average LOSS barely moved
(−46.11 → −44.91). So this is **better setup selection**, not cheaper losses. That is what a
repaired detector should look like.

### Re-verified on a different tick archive

The rig's September tick archive was replaced with the live terminal's fuller copy (3.8 MB →
68 MB, via `monitor/strategy_lab/extend_rig_ticks.py`). Both rows were then re-run:

| | old archive | new archive |
|---|---|---|
| retracement fix | 89% · +$1,888 | **89% · +$1,890** |
| control | 74% · −$1,114 | **74% · −$1,122** |

$2 and $8 apart, same trade counts, same 39,834 bars. The result is not an artefact of one tick
file, and every number in this document stays comparable.

### STILL NOT VALIDATED OUT OF SAMPLE — and it cannot be, from the rig

Extending the tick archive was not enough: MT5 also needs the **bar** archive to cover the
range, and the Sept 17–28 run saw **32 bars**. Replacing the rig's `2026.hcc` (34.7 MB, Feb–Sep)
with the live symbol's (16.1 MB, Aug–Sep) would permanently destroy Feb–July, and was refused as
irreversible. Correctly.

**So the out-of-sample leg has to be run in the live terminal, which already holds both
archives for XAUUSD.pi.** `monitor/strategy_lab/make_oos_setfiles.py` writes the two input files
— `ZeeUHV_Diamond_OOS_FIXED.set` and `..._CONTROL.set`, identical in ~50 inputs except
`InpRetraceFix` — into his Tester profile. **Both must be run.** If Sept 17–28 is simply easy
tape the control wins there too, and the candidate alone would prove nothing. This is the check
that caught the $4,071 overfit on 2026-08-12.

**Until that comes back, the 89% is a strong hypothesis and nothing more, and it must not go on
a live chart at 0.10 lots.**


---

## 10. THE OUT-OF-SAMPLE VERDICT — the retracement fix ALONE did not survive

Run by Zee in his own terminal (`XAUUSD.pi`, BlueberryMarketsSVG-Live, 100% real ticks,
2026.09.17 → 09.28 — tape the search never saw). Reports in
`mt5/_tester_runs/reports/29 sept/`.

| | setups | tickets | WR | net |
|---|---|---|---|---|
| CONTROL (no fix, pivot 2) `_d` | 22 | 88 | 63.6% | **−$534.10** |
| fix, pivot 2 `_c`/`_e` | 12 | 48 | 66.7% | **−$350.60** |
| **fix + pivot 3** `_f` | **6** | **24** | **100.0%** | **+$249.10** |

**In-sample the retracement fix gave 89% / +$1,888; out-of-sample it gives 66.7% / −$350.60.**
It does not reproduce on its own and is no longer claimed as a standalone result. Only the
pivot-3 configuration was profitable on unseen tape — and its honest sample is **6 setups**,
because pivot 3 was *selected* on the earlier window.

**A margin fact worth more than the test.** `_a`/`_b` ran at a $5,000 deposit and opened
**one ticket per setup** with Margin Level at 113.70%. Working back, one 0.1-lot gold position
consumes **~$4,330** — the broker gives metals **1:10**, not the account's 1:500. The 8-ticket
stack needs ~$34,600. **A $5,000 account can fund ONE ticket**, and at $5,000 the margin also
blocked whole setups (6 taken instead of 12). Every in-sample figure in this document assumes
the stack.

---

## 11. THE FUNNEL — 93.8% of the chart was never looked at

Zee: *"these UHV setups.. they appear almost a 100 times a day on 1 minute scale ... whether
something is cutting too many setups? ... usually i take a 50+ trades in a day."*

`TryFire()` runs **once per bar** — 39,834 times over the window — and fired **23** times. v1.26
adds a counter to every gate (telemetry only; the winning config re-ran identically at 96% /
+$1,146 / 178 trades, which is what makes the instrumentation trustworthy). The counters sum to
exactly 39,834.

```
[FUNNEL] bars=39834 | session=0 maxopen=23 cooldown=42 gap=63 stale=0 volhole=531
         humps=37369 law45=0 ranging=799 | noorigin=527 nouhv=271 nobreak=180 laws=6 | FIRED=23
```

| gate | bars killed | share |
|---|---|---|
| **`InpMaxHumps = 2`** | **37,369** | **93.8%** |
| ranging (`InpRequireTrend`) | 799 | 2.0% |
| OANDA volume hole | 531 | 1.3% |
| no retracement | 527 | 1.3% |
| no UHV | 271 | 0.7% |
| no breakout | 180 | 0.5% |
| gap + cooldown + maxopen | 128 | 0.3% |
| the SWEEP law | 6 | 0.02% |

**The hump budget answers first on 93.8% of bars, so the UHV and breakout tests are never
reached.** The machine is not judging his setups and rejecting them — it never looks.
`InpMaxOpen` was the predicted culprit and killed **23 bars**; `MaxOpen 10` and `Cooldown 0` both
returned byte-identical results.

### What the two miscalibrated gates cost (pivot 3 + fix, in-sample)

| config | WR | net | trades |
|---|---|---|---|
| shipped `MaxHumps 2`, `ReqLaws 4` | **96%** | +$1,146 | 178 |
| **`MaxHumps 0`** | 93% | **+$1,775** | **310** |
| **`ReqLaws 0`** (no sweep) | **96%** | **+$1,566** | 212 |
| ALL GATES LOOSE (the ceiling) | 76% | **−$13,178** | 5,648 |

The budget costs **$629 and 132 trades**; the sweep costs **$420 and 34 trades and buys no win
rate**. The sweep is **not from LAWS.md** — it was added in v1.12, measured at pivot 2 with the
broken detector.

**And the ceiling run is the control that stops this becoming "delete the rules".** Fully open,
the EA finds **820 setups (about 19.5/day — close to his lived experience)** and loses **$13,178**
at 76%. With everything open, `nouhv` rejects 24,052 bars and `nobreak` 20,838: **his tests do
real work once they are actually asked.** The trend filter is carrying the system.

**v1.17 predicted this exactly, on 2026-09-09:** *"If the forward days show the trade count
collapsing without the end-of-trend loser disappearing, the budget is cutting the wrong trades
and 3 (or off) is the fallback."* That table already showed budget OFF at **+$2,287 / 762 trades**
against budget 2's **+$830 / 324**. Budget 2 is also stricter than his own stated model —
*"hump 1 trade, hump 2 trade, hump 3 trade, hump 4 hmm maybe it shifts"* is budget **3**.

---

## 12. ATTRIBUTION — the win rate is HIS rule, not my repair

| config (in-sample, geometry untouched) | WR | net | trades |
|---|---|---|---|
| baseline: pivot 2, no fix | 74% | −$1,122 | 274 |
| **pivot 3 alone, NO retracement fix** | **94%** | +$614 | 134 |
| pivot 3 + retracement fix | **96%** | +$1,146 | 178 |
| pivot 2 + retracement fix | 89% | +$1,890 | 282 |

**`InpPivot` 2 → 3 — his camel hump read strictly — is worth 20 points of win rate on its own.**
The retracement fix adds 2 more and $532. Both help; the discovery is his.

**The pivot dial is a slope, not a peak:** pivot 3 → 178 trades, pivot 4 → 40 (100%), pivot 5 →
**zero**. Win rate rises only because trade count collapses, so pivot 3 is kept as the **money**
optimum (+$1,146 vs +$445), never for its win rate. Walk-forward: **H1 89% / +$108**, **H2 100%
/ +$1,037** — both green, but pivot 3 does lose, and the 100% leans on one favourable stretch.

---

## 13. WHAT IS AND IS NOT ESTABLISHED, 2026-09-29

**Established on MT5 real ticks:**
* the shipped Diamond is **74.1% / −$1,114** over six weeks, matching his live fills (78.4% / −$1,703)
* the UHV was chosen from **one candle in 65%** of all 155 logged fires — repaired
* **93.8% of bars die at the hump budget** before any setup rule is consulted
* `InpPivot 3` is worth **+20 points** of win rate at unchanged geometry
* every mechanical exit rule fails — **four** refutations (Watcher, volume fade, FailCandles, bail)
* win rate is purchasable to 97% and worthless (one basket, −$2,140)
* **his account funds ONE ticket** at 1:10 gold margin

**NOT established:**
* any configuration out-of-sample beyond **6 setups** (Sept 17–28)
* `MaxHumps 0` and `ReqLaws 0` have **no out-of-sample leg at all**
* the whole testable world is **2026.08.05 → 09.28**, because `oanda_vol.csv` starts there and
  `InpOandaStrict` refuses every minute outside it

**Nothing has been shipped as a default. Every new input added today is OFF.**
