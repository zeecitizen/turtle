# KNOWLEDGE_BASE.md: what this repo has proven, refuted and learned

Built 2026-10-14 from a survey of the repo: report.md, EA_SYSTEM_STATE.md, VERSION_HISTORY.md,
LOSS_LEDGER.md, the LAWS*.md files, DIAMOND_WINRATE, VSISA findings, TICK_SPEED / RESUME_HERE, the EA
header notes, daily reports and the memory notes. It feeds the bread_winner EA.

Every claim carries its source. **MT5** = measured in the Strategy Tester or on live fills. **PY** = a
Python hypothesis, never promotion-grade (CLAUDE.md).

---

## A. How to test (rules that cost real money to learn)

1. **Only MT5's Strategy Tester or live fills may promote an idea.** A Python replay of 163 real trades
   said +$876; they really made −$657. Python's win rates run about 16 points high. *(CLAUDE.md, MT5)*
2. **Walk-forward:** tune on Jan–Jun 2026 and judge on Jul 1 – Oct 8. Accept a change only if it also wins
   on the unseen part. *(report §3.3)*
3. **Real ticks only: `XAUUSD_TK`.** Axi's stored history became half-synthetic around Oct 10–11, and
   invented ticks flattered results (+$207k "found" vs +$151k real). `XAUUSD_TK` = 60.4M real Axi ticks,
   plus $4/lot commission added in parsing. *(report §3.1, MT5)*
4. **Quote random-delay results** (exec −1) as well as 200 ms. *(memory: quote_random_delay)*
5. **The tester reuses old inputs.** Pin every input, including inputs inside `.mqh` include files
   (`axi_rig.ea_defaults` does this since 2026-10-14). *(report §35, MT5)*
6. **Volume in the tester:** only real-tick mode (model 4) gives true tick counts. The broker publishes no
   exchange volume for gold CFDs, so every "volume" is a **tick count**. *(VSISA header, MT5)*
7. **Before believing any signal** *(RESUME_HERE §4, TICK_SPEED)*:
   - the mirror test
   - permutation against same-size random draws
   - count episodes, not rows
   - out-of-sample on a different instrument
   - P&L after the real spread

   Four "validated" signals (SPRING, SWEEP, GET READY, the ranging block) all reversed on better data.
8. **Always run a random-entry control with the same exits.** NullEntry (random direction every 30 min,
   same stop/target) won **92.4%** at a $1 target / $20 stop, as often as the real UHV rules. On real ticks
   the UHV entry was **worse than random** in 3 of 4 fortnights. *(memory: win_rate_is_geometry, MT5)*
9. **MFE/MAE medians say nothing about the order of events.** Only walking bar by bar shows which of stop
   or target came first. *(memory: level_not_chase)*

## B. The instrument (XAUUSD on Axi)

- **Money:** $1 of price = $1 per 0.01 lot = $100 per 1 lot. Commission about $4 per lot round trip.
  Typical spread about $0.10–0.20 (Axi), $0.17 (PXBT), $0.07 + commission (Blueberry).
  *(report, RESUME_HERE)*
- **Server time** = UTC+3 during US daylight saving, UTC+2 otherwise, i.e. New York time + 7, so New York
  09:30 = 16:30 server all year. **PKT = UTC+5** with no DST: NY open = PKT 18:30 (Mar–Nov) or 19:30
  (Nov–Mar). London open 08:00 UK = PKT 12:00 all year.
- **The minimum horizon to beat the spread:** mean absolute move after 1 s = 0.32× spread (impossible);
  10 s = 1.36× (needs 87% wins); 60 s = 3.05× (needs 66%). **Nothing under about 10 seconds can pay.**
  *(RESUME_HERE §3, PXBT data)*
- **Gold breathes.** About 92% of UHV breakouts reach +$1, 84% +$2, 77% +$3 and 60% +$5 in the break
  direction (tape fact, not P&L). *(memory: level_not_chase)*
- **Sub-$3 targets are a math trap on gold:** WR 87–92% at a $0.50 target, but you need 93% to beat a $6
  stop, and the spread eats the win. *(EA_SYSTEM_STATE: S4b, PY-era)*

## C. Strategy cores

| Core | Timeframe | The edge in one line | Best MT5 evidence |
|---|---|---|---|
| **Saad** (`Saad_strategy_15min` v1.18) | M15 | Rejection candle (pin bar, hammer/star, marubozu ≥ 0.53 body) touching EMA9 (or EMA50 for buys), entered on the break of that candle by 2 pips. Stop 35 pips beyond the candle; target the last swing or the exit EMA; breakeven at 75%; half off at TP1; $2 trail. Filters: candle ≥ 0.55× ATR, efficiency ratio(16) ≥ 0.11 | +$202–207k at 1 lot over Jan–Oct, PF 1.6, about 47% WR per trade, 0 losing months *(report §0, MT5)* |
| **VSISA** (v1.30) | M5 | 2–3 loud same-direction bars (the campaign), then a **quiet** bar closing the other way (the reaction); enter on its close, stop past its extreme, one lock at 2R. ML: meta-label ≥ 0.40, skip the high-vol GMM regime, exhaustion exit ≥ 0.75 | Jul–Oct (unseen by the ML) +$10,019 at 0.28 lots, 60% WR, PF 3.37 *(report §28, MT5)* |
| **UHV / Diamond** (LAWS.md, ZeeUHV_Diamond v1.27) | M1 | In a trend (higher highs / higher lows), the loudest red candle inside a valid pullback = the UHV; a **quiet** momentum candle (body ≥ 70%, close in the top 20%) closes beyond the UHV's high. Stop under the pullback low. LAWS: 1:2 target, breakeven at 1:1, NY session | Unfiltered it loses (−$463 a year at 0.01). With 15-min chop ≥ 0.45: **94.1% WR** (Jul–Oct 100%) but only +$19 a year, because the geometry needs 84% to break even *(report §34, MT5)* |
| **Trinity_1min** v1.00 | M1 chart (M15 / M5 / M1 engines) | All three in one EA at 0.01 lots | $15.23–15.99 per trading day, every month green, 4 in 10 days red *(report §35, MT5)* |
| **saad_vsisa_hybrid** v1.00 | M5 | Saad at 2× lots when VSISA traded the same way within 60 min | Best net ÷ DD of about 50 blends *(report §30–31, MT5)* |

## D. What works (MT5-proven)

1. **The chop filter is the most reliable lever in the project.** The efficiency ratio:
   - Saad's v1.14 gain came from ER 0.11 + candle ≥ 0.55 ATR + marubozu 0.53. *(report §0)*
   - It lifted Diamond from 76% to 94% WR (ER(16, M15) ≥ 0.45). *(report §34)*
   - S4 kept its profit with ER ≥ 0.15 (plateau 0.15–0.20). *(EA_SYSTEM_STATE, PY-era)*
2. **Structural stop + structural target, nothing in between.** Every exit rule that closes a trade between
   the stop and the target (breakeven locks, give-back ratchets) cost money. *(memory:
   exit_interference_costs, MT5)* Exceptions with receipts: Saad's 75% breakeven and $2 trail after TP1,
   and VSISA's single lock at 2R.
3. **Take the break, don't wait for the dip.** Retest, limit-at-level and liquidity-sweep entries all lost.
   A limit fills only on the trades that come back, which are the worse half. *(report §3.2, memory:
   level_not_chase, MT5)*
4. **Selectivity beats frequency:** 5 trades in 2 days profited where 148 a day bled. *(memory:
   exit_interference_costs)*
5. **ML layers that held on unseen data** (VSISA, trained Jan–Jun, judged Jul–Oct): the meta-label
   classifier (skip P < 0.40), skipping the high-vol GMM regime, and the exhaustion exit (P ≥ 0.75).
   Together: Jul–Oct PF 1.77 → 3.37, DD halved. *(report §28, MT5)*
6. **Lot size is the risk.** The −$1,475 day and the liquidated $200 account were size, not direction.
   *(report §2, memory: tickspeed_and_riskguard)*

## E. What failed (do not re-try without new evidence)

| Idea | Result | Source |
|---|---|---|
| Tighter stops (5–25 pips, 0.5–1.5 ATR, fixed $2–10) | all worse: noise knocks them out | report §3.2 |
| Wait for the dip / retest after the break | all worse | report §3.2 |
| Liquidity-sweep entry before the break | all lost | report §3.2 |
| HTF trend filter (1H/4H), 200 EMA side filter | WR 47.8 → 43.7%, profit −75%: Saad earns on the first trades of a new trend | report §10 |
| FVG "safe zone" | blocks 40–85% of trades, no WR gain | report §9 |
| Saad on M5 / M1 | spread + commission eat the edge; results flip between periods | report §5, §11, §35 |
| True 1-minute versions of Saad/VSISA, tuned (242 Optuna trials) | best Jan–Jun +$5.12/day → Jul–Oct −$0.72 to +$1.00/day: fits noise | report §35 |
| Gating one strategy on another (Saad ↔ VSISA ↔ Diamond) | cuts trades, never raises the gated strategy's own WR; they mostly disagree (VSISA fades, Saad breaks out) | report §29–31 |
| Larger lots via Optuna | 2.6× profit for 3.6× drawdown; net ÷ DD always worse | report §33 |
| Diamond target 1R / 2R / 3R (24 combinations) | all lose over 3 windows; 2R sign-reverses | EA_SYSTEM_STATE (MT5) |
| Ichimoku confluence scalping | high WR, PF < 1; R:R 2 failed walk-forward | EA_SYSTEM_STATE |
| Shano probe (momentum confirmation) | in-sample WR mirage, no out-of-sample edge | EA_SYSTEM_STATE |
| Order-flow signals (SPRING, SWEEP, GET READY) | reversed on gold | RESUME_HERE §4 |
| PPO lot sizing, mature-runner exits, regression meta-label | no gain over a constant lot / simpler rules | report §14, §19, §20 |

## F. Geometry, win rate and expectancy

- **Win rate is mostly geometry.** A random entry wins about `SL / (SL + TP)` of the time: 92% at 1:20,
  50% at 1:1, 18% at 6:1. *(memory: win_rate_is_geometry; RESUME_HERE §3)*
- **Never optimise for win rate; never buy win rate with wider stops.** *(memory: goal_winrate)* Report it
  beside net, and judge selection by **WR above the random control at the same geometry**.
- **Break-even WR = SL / (SL + TP)**, plus spread and commission. Diamond's $1.12 average win vs $5.85
  average loss needs 84%. *(report §34)*
- Zee's discretionary Feb-11 shape: average win +$12.93, average loss −$1.32. That edge is the
  **exit**, and it doesn't automate. *(memory: exit_is_the_edge)*

## G. Zee's doctrines (constraints on any EA)

- `LAWS.md` is Zee's; read it, never edit it.
- Volume should be OANDA's (TradingView) live; Axi tick volume is allowed in tests when OANDA isn't
  available (Zee, 2026-10-14).
- Guardrails must live in code, not in a human's discipline. *(memory: greed_has_no_measurement)*
- Harvest, then withdraw: at the daily target, stop. *(memory: harvest_then_withdraw)* **bread_winner is
  exactly this.**
- Report PKT times, 12-hour clock.

## H. Sessions and timing

- **VSISA by session (MT5, VSISA_AXI_OPTIMISATION):**

  | Window | Net | WR |
  |---|---|---|
  | all hours | $13,689 | 51% |
  | London 8–17 server | $7,742 | 55% |
  | NY 13–24 server | $5,564 | 47% |

  A session window **raises WR a little but cuts profit**. The Asian session was profitable for VSISA.
  - "A split found on one population is not evidence about another": the pullback scan's 21% Asian
    figure didn't transfer.
- **Sydney / maintenance hours:** 0% WR in the old UHV indicator era. Filters `mTS = 25`, `sFilt` are
  mandatory there. *(CLAUDE.md, legacy)*
- **LAWS.md:** trade the UHV only in the New York session, "5:00 PM or maybe 6:00 PM" PKT. The NY cash
  open is PKT 18:30 in summer and 19:30 in winter.
- **The Diamond trend gate read 60–67% of NY minutes as ranging.** *(VERSION_HISTORY v1.35)*
- **The daily-loss rule matters more than total drawdown for funded accounts.** VSISA v1.24 at 0.28 lots:
  worst day $449, 0 of 92 days breaching a 5% daily limit. *(VSISA_AXI_OPTIMISATION)*

## I. Daily-target experiments (2026-10-14, MT5)

- **Trinity_1min v1.00** (0.01 lots, no daily stop): **93 of 187 days ≥ $10**, 73 red days, average
  $15.23/day. *(report §35)*
- **bread_winner day manager** (close all and stop at +$15) on Trinity's defaults, Jul–Oct: **55 of 71
  weekdays ≥ $10 (77.5%)**, 14 red (worst −$39), $8.69/day. The target caps the good days, so the average
  falls while the hit rate rises.
- **The trade-off:** bigger lots plus a loss limit cut red days to about 9%, but single days lost
  $125–274.

## J. bread_winner research (2026-10-14): one $1 shot a day

Geometry: TP $1, SL $6, 0.11 lots (a win ≈ +$10.56). Random entry wins about 83%; break-even is about 86%.
Every number below is MT5, real ticks (`XAUUSD_TK`), Jan 6 – Oct 8.

**Census** (every setup fired, all day; per-setup WR, net at 0.11 lots):

| Scout | Setups | WR | Net | Verdict |
|---|---|---|---|---|
| **VSISA M5, loose** (campaign ≥ 0.60× max, ≥ 1.0× avg, reaction body ≥ 0.25), raw signal | 407 | **87.2%** | **+$1,019** | **the robust core** |
| VSISA M5, shipped settings, raw signal | 320 | 86.3% | +$557 | good |
| VSISA M5, after its ML filter | 163 | 88.3% | +$372 | good, fewer |
| Diamond (all hours) | 225 | 76.4% | −$1,235 | needs a filter |
| Diamond, only when the 4h (16×M15) net move ≥ $11.5 its way | 56 | 92.9% (94.6 / 89.5) | +$397 | strong but rare |
| Saad (M15 chop + trend context) | 182 | 83.5% | −$536 | weak, except NY hours (89%) |
| VSISA M1 / M15, Saad M5, PULSE, VSISA_Pullbacks | 113–3,466 | 77–83% | all negative | **no edge at this geometry** |

**What failed:**

| Idea | Result |
|---|---|
| ML on 94k random moments (MT5-labelled) | test AUC 0.518: moments are unpredictable |
| ML on the structural shots | train AUC 0.92 → test 0.505: overfit |
| Time stops (10 / 20 / 30 / 60 min) | all lose money vs none: winners get cut |
| Rollover-hour block (server 22–01) | 150 → 134 bread days: the losing days lose anyway |
| Spread caps ($0.15 / $0.20) | fewer bread days, more red days |
| Friday-close block | −$276, no fewer red days |
| VSISA's own structural stop (clamped 3–10 / 4–8 / 5–12) | worse than a fixed $6 |
| Wider ($10) / tighter ($4) fixed stops | less money |

**What worked:** taking the first good setup of the PKT day (it beats the average setup), the per-scout
filters above, and the looser VSISA.

**Best policy, `bread_winner` v1.00:** Diamond (after PKT 17:00) + loose VSISA, one shot per PKT day.
- **Full year:** 150 of 196 weekdays ≥ $10 (76.5%), 16 red, 22 without a shot, +$1,173 (+$6/day).
- **Both halves agree:** Jan–Jun 77.6%, Jul–Oct 74.6%.
- **Adding VSISA_Pullbacks as a scout:** 161 bread days (82.1%), 0 empty days, but 23 red days and +$610.

**v1.01 (same evening):** a $8 stop + 0.12 lots: 164 / 196 bread days (83.7%), 9 red, +$1,615. In the
first-of-day policy the stop plateau $8–10 beat $6 on bread days AND money, in both halves. This is the opposite
of the all-setups census, where wider stops lost money: the first-of-day selection changes the answer.
**VSISA on M3 / M4 / M6 / M10: 82–85%, all negative.** Only M5 works.
