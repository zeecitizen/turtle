# VERSION HISTORY — the EA ledger

**Purpose (Zee, 2026-08-19):** *"when i'm on my other computer with claude in another
session they can read and say aha i know today we did this."*

**THE RULE: every shipped version gets an entry here, in the same commit that ships
it.** Entry format: version · date · what changed · the receipts · who ordered it.
Newest first. Pre-EA history (Pine/TradingView era) lives in `CHANGELOG.md`;
deep session narratives live in `daily_reports/`; live-config philosophy in
`EA_SYSTEM_STATE.md` (stale below v1.2x — this file supersedes it for versions).

Test receipts notation: "six-period total" = the standard court — six fortnights of
real ticks (LIVE Aug 11-14 · Mar · Apr · May · Jun · Jul 2026) at 0.02 lots, MT5
Strategy Tester, model 4, delay 163. Promotion rule: better in a kind period AND a
hostile one, or it doesn't ship.

---

## ZeeUHV (main EA, magic 88094, XAUUSD M1)

| ver | date | change | receipts / reason |
|---|---|---|---|
| v1.54-55 | 2026-08-20 | CONVICTION GEOMETRY family (defaults off): `InpDiaTpFrac` (TP scales with diamonds: D0 aims 0.35pt → D5 the full point), `InpDiaScaleSL` (the ratio repair: SL shrinks with TP so every tier fights the same 5:1 wall), `InpDiaInvLots` (Zee's inverse-lots cure: 8× at D0 fading to 1× at D5) | triple exams running: diamond-TP alone, then his literal inverse-lots design, the repaired geometry, and repaired+inverse — the wall arithmetic (0.35tp/5sl needs 93.5% at ANY lot size) predicts only the repaired forms can pass |
| v1.58 | 2026-08-20 | **THE VOLUME SOURCE** (`InpVolSource`, default 0=broker): 1 = read OANDA/TradingView volume from `Common\Files\oanda_vol.csv` (server-time keyed, per-minute fallback to broker). Works in the TESTER too (FILE_COMMON) so it is court-testable | **MEASURED: the two feeds crown a DIFFERENT loudest candle in 46.4% of rolling 8-bar windows** — and Zee's eye, his 146 labels and Feb-11 all read OANDA. The volume-source mismatch hypothesis finally has a number. `monitor/oanda_volume_bridge.py` pulls via tvDatafeed websocket (no CDP — also HEALS oanda_m1.csv, dead since the Aug-14 MSIX break) and archives every minute for future courts. tvdatafeed reach = ~5,110 M1 bars (4 days), so head-to-head starts on Aug 17-20 and grows |
| v1.61 | 2026-08-23 | **THE TEACHER'S EXITS on our entry** (`InpStructStop`, `InpStructBufPts/Min/Max`, `InpTargetR`, `InpBreakEvenR` — all default off): stop under the UHV's own low/high, target a multiple of the risk taken, stop to entry at 1R | ZeeScalp's court proved every rule Ahmad Umair teaches EARNS its place (no-momentum −$1,000 · no-breakeven −$629 · 3R worse than 2R · NY-only the biggest single gain) yet his simple entry reaches only ~28% and dies just under the 33% a 2R design needs. Ours reaches 65-78%. This is the untried pairing: our laws, his economics. Court + virgin running |
| ZeeScalp v1.00 verdict | 2026-08-23 | his method whole: court −462.83 / virgin −588.55 (best arm NY-only: −308.92 / −138.57) | REFUSED as a standalone — but it PRICED each of his rules, and it confirmed the momentum breakout (Zee's 23:53 forensic, Law 13) is worth ~$1,000 **inside his geometry** after failing inside ours. Momentum and a structural 2R stop are a PAIR |
| v1.60 | 2026-08-22 | **LAW 13 — THE MOMENTUM BREAKOUT** (`InpBrkBodyMult`, `InpBrkClosePos`, both default off): the breakout candle must have a body large against the last 20 candles AND close near its own extreme | Zee's forensic of the 23:53 loser: "breakout should be a momentum candle" — a doji-ish nudge crossed the trigger and qualified, because the EA only ever demanded the break be QUIET and FIRST, never DECISIVE. Aimed straight at the standing win-rate goal. Court + virgin trial running |
| v1.58-59 | 2026-08-21 | `InpOandaVolume` (Zainab) · `InpOandaBars` · FileOpen retries · `[DIA]` voice | see the OANDA section |
| v1.57 | 2026-08-20 | `InpStickyGreenOnly` (sticky trend only in green pulse) | **the 18:41 file CLOSES: five cures, five refusals** — pivot-1 −1,068 · sticky 5/10/20 −1,097/−1,338/−1,268 · green-only sticky −535 (better but still taxed by Apr −339/Jul −318). The gate's confirmation lag is load-bearing: its visible single-trade cost funds an invisible four-figure salary |
| v1.56 | 2026-08-20 | STICKY TREND (`InpTrendSticky`, default off) — the 18:41 wound: a confirmed trend persists through paperwork-pending "mixed" until CONTRADICTED | gate-lag trial running (pivot-1 + sticky 5/10/20) |
| v1.54-55 verdicts | 2026-08-20 | conviction-geometry family REFUSED: literal inverse-lots days +129 / court −371 / **virgin −1,832** (the $28-vs-$400 wall realized); repair B court −339 (April's trend-tax); C −560/−1,630. Conviction stays in SIZING, never geometry | the family's five variants all fail the same way |
| v1.53 | 2026-08-20 | PULSE-SWITCHED TARGET (`InpRedTargetPts`, default off): red pulse → TP 0.75 (the chop harvester — near-misses at 0.7-0.9 pts convert to wins), green/diamond → TP 1.0 (feast pays full) | **REFUSED by the triple exam** (court −112 ✗ · virgin +103 ✓ · days −15 ✗): the pulse is the wrong chop-key for a target switch — red pulse also means early-feast recovery, where 0.75 taxes full-dollar winners. TP 0.75 stays benched awaiting a TAPE-based chop detector. Dead input with receipts |
| **v1.52** | 2026-08-20 | **THE HOUR DIMMER (live)** — broker hours 02/03/09/10 quarter-sized (`InpDimHourA-D=2,3,9,10`) | The only candidate positive on ALL THREE datasets: court +127 (total +576.18, April green) · 8 VIRGIN fortnights +260 · live days +165. Sourced from Zee's window theory (Feb-11: 85% of his trades in the NY-morning session; live fills: 38-for-38 there; the bleed hours cost −$1,950 live). TP 0.75 benched with honor (virgin +605 but court +13 / days −12 — first candidate of the next cycle); combined dimmer+TP75 contradicts itself across datasets (court −128 / virgin +709) = noise, refused |
| v1.51 | 2026-08-20 | THE HOUR DIMMER (`InpDimHourA-D`, `InpDimFrac`), default off — Zee's window theory: NY morning = the golden session (Feb-11: 85% of his trades; live: 38-for-38 at PKT 17-19h); the bleed lives in broker 02-03 & 09-10 (−$1,950 live) | court in session |
| v1.50 | 2026-08-20 | LAW 5 switch: `InpWickDia` (wick-breakout diamond toggleable), default true = unchanged | **DECIDED: wick STAYS** — off is worse in ALL SIX periods (−291.28). The 6.7× mask receipt described the old machine; under v1.49 wick baskets are net contributors. Law 5 closed |
| **v1.49** | 2026-08-19 | **THE DIAMOND SEASON MACHINE (live)** — `InpDiamondMode=true`, `InpGreenFastRed=true`, `InpFastRedLook=8`. Green season (pulse-20 green AND last-8-tickets green) trades the locked streak geometry: SL 20 / TP 1 / hold 60, full stack, 10c bypassed. Red season: scout machine (SL 5 / hold 3, quarter size, full guard) | **+449.26** six-period (champion was +276.22). Fast-fear dial a perfect hill: 3/5/8/12 = +377/+416/+449/+283. Worst single loss −19.36 (the −42 crash class extinct). Born from Zee's crash theory: "the diamond only had one defect — the crash." ON PROBATION: first out-of-sample day (Aug 18 replay) lost −217 vs pulse's −38; live-forward must confirm before any lot raise |
| v1.48 | 2026-08-19 | `InpFastRedLook` dial added (quick-to-fear window) | dial receipts above |
| v1.47 | 2026-08-19 | Crash-control organs, default off: `InpLossCoolMin` (stand down after a losing ticket), `InpDayHaltLoss` (day-halt) | both FAILED on the raw diamond (−975/−982); kept as dead inputs with receipts |
| v1.46 | 2026-08-19 | `InpDiamondMode` + `InpGreenStopPts/HoldMin/Keep10c` (fused machine, default off) | fused pure +247.08, guarded +24.74 |
| **v1.45** | 2026-08-19 | **THE SELF-AWARE SWITCH (live)** — `InpRegimeLook=20`: pulse = net of own last 20 closed tickets; red → quarter-size scouts, green → full stack. Never stops (a stopped machine can't feel the season change) | **+276.22** six-period — the FIRST net-positive M1 config in project history. Dial a hill: p10 +265 / p20 +276 / p40 +226 (absolute). Mar −247→−87 · May −384→−91 · Apr flips green |
| v1.44 | 2026-08-19 | `InpScratchRedOnly` (scratch only in red pulse), default off | synthesis +155.10 — positive but $121 under the switch alone; retouch closed |
| v1.43 | 2026-08-19 | FEB-11 EXIT LAB, default off: `InpScratchArm/Ofs/Hold` (retouch scratch), `InpRevExit` (first opposing candle) | 11 arms, ALL fail vs baseline. Losses DO collapse $40→$2-3 (his loss column achieved) but this strategy's winners dip first — scratching the dip scratches the payers. 9th failure of mechanizing the hand |
| v1.42 | 2026-08-19 | `InpRegimeLook/RegimeFrac` (the pulse), default off | court receipts under v1.45 |
| v1.41 | 2026-08-18 | LAW 12 (peak-bounded origin), default off, 2 variants | v1 −14.52 · v2 +171.44 (passes letter; taxes the streak). Aug-18 day replay: 53%→80%, −38→+76. PENDING: measure on top of the pulse |
| v1.40 | 2026-08-18 | Exhaustion TAGS (measure-only): bit 64 DEFENDED-LEVEL, bit 128 LATE-HUMP; mask space →256 | neither separates (2,200 tickets; per-period contradictions). Riding live for evidence |
| v1.39 | 2026-08-18 | LAW 11 (origin integrity: retracement may not contain new leg extremes), default off | REFUSED both courts: −303.86 six-period AND kills 8 golden-streak fires. The V-turn skeleton is shared by winners and losers |
| v1.38 | 2026-08-18 | Mix-and-match organs, default off: `InpHtfMode/HtfSizeFrac` (M3-consult as sizing), `InpBoundaryExit`, `InpEntryBoundary` | marriage campaign: consult dial = minefield (look2 +300 beside look3 −119); transplant refuted 3×; nothing shipped |
| v1.37 | 2026-08-18 | HTF gate learns M3/M5 (`InpHtfMinutes=3` now valid) | consult veto look4 +103 but dial unstable — not shipped |
| v1.36 | 2026-08-18 | PROBE module (`InpProbeSec/MinPts/Lots`), default off — Zee's scout-then-burst | a MAY-shaped tool (+346..+451 there, fails elsewhere); filed under regime |
| v1.35 | 2026-08-18 | Hourly census `[HCEN]` (tester-only) | answered "why is NY session skipped": trend gate reads 60-67% of NY minutes as ranging |
| **v1.34** | 2026-08-18 | **RANK 6 (live)** — `InpUhvRank=6`: every retracement auditions up to 6 volume-ranked UHV candidates; quality laws unchanged | +121.86 six-period; dial saturates (6≈10); census: 1,439/4,137 bars died because only the loudest candidate was ever examined |
| v1.33 | 2026-08-18 | `InpLocalPeak` switch (body+neighbour vetoes toggleable), default on | Zee's funnel ("a UHV in EVERY retracement") priced: −2,430. The vetoes are guardians |
| v1.32 | 2026-08-18 | Rank-N walk (`FindUhvBroken`), default 1 = byte-identical (census-verified) | reproduction exact |
| v1.31 | 2026-08-18 | Pipeline census `[CEN]` (tester-only counters) | the funnel: 50.9% ranging · 34.8% UHV-vetoed · origins near-universal |
| **v1.30** | 2026-08-18 | **HOLD 5→3 MIN (live)**, both EAs | +288.68 six-period; clock bracketed both sides (h2 fails, h8/12/20 fail) |
| **v1.29** | 2026-08-17 | **LAW 10c (live)** — `InpLoudSizeFrac=0.25`: breakout louder than 0.85×UHV → basket opens ¼ tickets, never zero | +538 six-period, zero trades cut (Zee declined the 10b gate: −48% trades) |
| v1.27-28 | 2026-08-17 | Law 10a margin (dead input, failed every depth); Law 10b gate (passed +786 but cut 48% of trades — declined by Zee) | receipts in report §3 |
| **v1.26** | 2026-08-17 | **LAW 9 (live)** — `InpImpulseOrigin=true`: origin's reference must be an IMPULSE bar (label #e014). Zee's forensic find on the 11:08 loser | +437.38 six-period (Mar +202, Jun flips +309) |
| v1.24-25 | 2026-08-17 | LAW 8 tag (mask bit 32, "independent retracement") — failed promotion, rides as tag | kind-only shape |
| ≤v1.23 | 2026-08-10..16 | Diamond era: stop 20→5 (v1.23), laws 6/7 as diamonds, stack ×2, OnTester mask receipts. See `05_AUGUST_DIAMONDS_FINDINGS.md` and branch `05_August_successful_diamonds` (the locked streak code) | the 14-basket +$614 streak (Aug 11-13) ran SL20/TP1 |

## Sibling EAs

| EA | magic | state | story |
|---|---|---|---|
| ZeeUHV_Loud_Breakout v1.2 | 88104 | LIVE | counter-experiment: fires when breakout ≥0.80×UHV (the band 10c shrinks). Has Law 9 + hold 3; NO rank-6/pulse yet (port = separate receipted step) |
| ZeeUHV_M3 "Shop B" **v1.10** | 88134 | LIVE on M3 chart | **2026-08-20: THE PULSE PORTED** (Zee's order, after −258.70 overnight = 2.7× her worst tested fortnight, second out-of-book day in week one). Pulse-20 default ON: red → quarter-size, green → full. Birth story: first-ever positive six-period config (+23.32, worst period −19). MUST run on the M3 chart |
| ZeeFade v1.00 | 88164 | **REFUSED — full dial complete: 2.5×/3.5×/5× = −2,849/−920/−77.** Monotone toward zero, never crossing: even once-a-day monsters converge to zero-sum minus costs. Theory closed | Zee's capitulation-fade theory: a GIANT candle (body ≥ 3× avg-60, ≥1.5 pts) marks exhaustion — fade it (giant red → BUY the panic, giant green → SELL the chase). House exit geometry for comparability. His Feb-11 memory: the 16:49+ buying cluster followed the morning's steep drop. Related: Law 7 reads climax bars as trend-fuel; this EA reads them as reversal |
| ZeeUHV_Diamond **v1.10** | 88154 | BUILT (Aug 20) — awaiting Zee's attach decision | THE UNTOUCHED ancestor: byte-faithful to commit 718b68a (the streak-era machine) except nameplate/magic/tags. No pulse, no laws 9+; court record of this config: −1,640/six fortnights, positive 4 of 6, crash cluster ≈ −$1,700/day possible at 0.10. **2026-08-21: LIVE and it proved the record** — 12W/6L and still −877.70, one 03:55 basket −1,003 at ~−167/ticket. Same day gained `InpOandaVolume` (default 0): 4-day audited test says broker +433.90 vs OANDA **+1,358.10**, better 3 of 4, and the −522.30 crash day came back **+59.40** on his eye. Awaiting Zee's word |
| BasedOnLaws **v1.35** | 88184 | BUILT (Aug 23-24) — NOT attached; validated forward only | **His page, and every version since v1.11 written by his own eye on Friday Aug 21.** v1.11 all three of his marked setups to the minute · v1.15 the whole setup judged on HIS chart (OANDA candles, not the broker's — the feeds differ up to 0.85) · v1.18 body, not wick, in the structure · **v1.19 a breakout is an EVENT, not a state** (first body-close only; killed a stale-break chase worth −83.10) · v1.20 `InpOandaStrict` — a missing OANDA minute is refused, never silently filled from the broker · v1.21 the tester snapshots his chart ONCE per run · v1.22 **"no big wick" measured against HIS LEVEL** (`InpBreakHold`) not the candle's shape · v1.23 every fire stamps how much of its break it held · **v1.24 defaults from the receipts: hold ≥ 45%, my body-vs-average test retired to 0**. Seven days of his chart (Aug 5-6, 18-21; the only days OANDA history reaches), 0.10 lots, frozen ground: **6W/10L · 37.5% · +448.10**, against +224.10 / 26.3% for the shape-test version and +163.60 with no wick test at all. v1.26-27 LAWS.md line 33 finally implemented — a confirmed uptrend LATCHES and stands until its last low breaks, guard moving only when a genuine hump top is taken (my code had re-proved the trend from scratch every minute and demanded the last two lows AND highs both rise, which called 80% of the week a range on days Zee reads as clean uptrends) — 24 trades 33.3% +296.60, better structure but not better money. **v1.28-29 HIS IDEA WINS: the trend is the EMA-5 SLOPE, the camel-hump code is bypassed entirely** ("what if you remove this gate.. use the slope of EMA 5 instead as your trend line") — dial 1/3/5/10 = +403/+323/+597/**+624**, and at 10 it beats my structure on EVERY axis at once: 30 trades vs 24, **40.0% vs 33.3%**, +624.00 vs +296.60. ATTACH-READY at 0.01 (InpTrendMode=1, InpEmaSlopeBars=10). **v1.30 (2026-08-24, after the FIRST LIVE TRADE lost -8.86): never judge a candle the bridge has not finished writing.** At 18:31:00.386 the EA read the 18:30 breakout as `close 4676.37, vol 788` and fired; the finished candle was `close 4675.84, vol 2109`. His law says the breakout must be QUIETER than the UHV (997) — 788 PASSES, 2109 REFUSES. The trade was forbidden by its own law and was taken only because the volume was still accumulating. Now a bar is judged only once the OANDA table holds a LATER minute (the bridge's own proof it moved past it); `InpFreshMaxSec=40` then skips the bar rather than trading blind. The bridge cycle also went 60s -> 15s -> 5s (and a shadowed variable that had been crashing the candle collector every cycle was fixed), so the lag is now ~0. **v1.31-32 — "A MOMENTUM CANDLE", QUANTIFIED.** After the second live loss Zee supplied the VSA definition and ruled out its volume clause himself ("we dont require Above-Average Volume, on the contrary our method uses the three only" — his page wants the breakout QUIETER than the UHV). Court, 7 days, his chart: **body ratio |C-O|/(H-L) >= 0.70 deleted SEVEN losing trades and ZERO winners** — 12W/18L +624.00 -> **12W/11L 52.2% +876.20**. The expansion clause (1.2xATR / 1.5xSMA) was REFUSED: it cuts 23 trades to 17 and kills three winners (+756.80). Close-at-extreme is byte-identical once the body ratio is enforced (kept, his clause, free). And my hold-45 test was NOT redundant as I predicted — without it +805.80/48.0%, with it +876.20/52.2%. Both live trades that lost (-8.86, -10.13) had breakout body ratios of 0.47 and 0.19 and would have been refused. **v1.33-34 — HIS OWN TREND LAW COMES BACK AND WINS.** He asked for a full audit ("can u check if we're following every single thing written in the laws.md?") and it found three real divergences; the biggest was that the live trend gate was my EMA-5 slope, not his line 7. Rebuilt as `CamelTrend` — humps DRAWN from pivots (a high with InpPivot lower highs each side, the rule his eye uses) rather than inferred from a retracement state machine, with his line 45 inside it ("whenever a high is broken, the deepest point is the confirmed higher low"). Seven days: **camel pivot-2 latched 18 tr · 11W/7L · 61.1%% · +1044.30** vs EMA-10 23 tr/52.2%%/+876.20 and the old inferred structure 31.6%%/+298.10. **The latch is worth 15 WR points** (no-latch: 46.2%%, +353.50). Pivot dial is a true hill: 1=+468 · **2=+1044** · 3=+630 · 5=+342. `InpTrendLook` is NOT load-bearing here — 60/90/120 are byte-identical. Expansion clause dialled at 0.6/0.8/1.0/1.25 xSMA and 1.0xATR: every setting within ~$145 of no-floor with single-trade differences = noise, so it stays OFF with receipts (the micro-candle trap the sources warn about lives in dead sessions; we trade New York only). **v1.35 — ALL HOURS (his call).** Session court on the camel trend, 7 days: NY-only 18 tr/61.1%%/+1044.30 ($58/trade) · ALL HOURS 39 tr/43.6%%/+1335.90 ($34/trade) · pre-NY-only 18 tr/33.3%%/+388.20 ($22/trade) · 15-24 21 tr/57.1%%/+1143.60. **Outside New York the edge is ~break-even, not a bleed** — his session law was protecting QUALITY (2.7x per trade), not money. He chose the total: "let's go all hours, since the goal is to make maximum money and all setups are losing anyways under this EA". **This DIVERGES from LAWS.md line 47 by his decision** — the only open item on the audit list. Also fixed: volume and candles came from TWO separate pulls and disagreed for the same minute (1396 vs 1505) — the volume now comes from the SAME ROW as the candle. **SLOPE DIAL COMPLETE (8 settings): 1=+403 · 3=+323 · 5=+597 · **10=+624** · 15=+368 · 20=+328 · 30=+382 · 45=+449.** The crest is 10 and the default STAYS (no reattach needed), but the honest headline is not the number — it is that **EVERY setting beats my camel-hump structure (+296.60)**, by $31 to $327. The instrument is proven; the dial itself is bumpy on ~30 trades and 10-vs-5 is within noise. v1.25 his clause c ("share body with the UHV's high") checked LITERALLY instead of inferred from first-crossing — byte-identical on Friday and on all seven days, so first-crossing was already carrying it. Threshold caveat on record: 40% and 45% are identical, 55% and 60% are identical, and ONE trade separates the two plateaus; 45% was chosen ON this sample, so forward days are the only jury |
| BasedOnLaws v1.00 | 88184 | superseded (Aug 23) | **LAWS.md mechanized whole, and nothing else.** Every provision of Zee's page as a HARD GATE: camel-hump trend · buy-side only ("gold is mostly bullish") · retracement starts when the LAST GREEN CANDLE'S LOW breaks · UHV = loudest RED of that pullback on OANDA volume · breakout CLOSES above its high, quieter than it, momentum body, **no big wick** · EMA-5 as his "extra confirmation" (optional) · **stop 5-7 pips under the retracement's lowest point** · **1:2 target, breakeven at 1:1** · **stop buying once the last low breaks** (the law nothing else implements) · NY session only · M5+M15 must agree. NOTHING from ZeeUHV's own history: no rank-6, no diamonds, no pulse, no dimmer, no Law 9/10c/12 |
| ZeeScalp v1.00 | 88174 | BUILT (Aug 23) — court in session | **Ahmad Umair's base video, mechanized end to end** (base_video/, transcript yt_2mKEfO85D04). NY session · trend-only · retracement counts once the last with-trend candle's LOW breaks · loudest-volume candle of that retracement · entry on a LOW-VOLUME **and MOMENTUM** break of its high · **stop below that candle's low (structural)** · **target 2R** · **breakeven at 1R (his mandatory rule)**. The one exit shape our court never measured: his geometry breaks even at ~33%, ours (fixed 5.0 stop for 1.0 target) at ~83% |
| ZeeUHV_Bull v1.00 | 88144 | **REFUSED by the court — never attach** | Zee's long-bias theory: "gold tends to keep going up" — buys only, NO trend gate (every red pullback after a green = an uptrend retracement), full guard otherwise (Law 9, rank 6, 10c, clock, pulse). Court verdict: loses ALL SIX periods (as-born −1,316; +diamond −1,678) — "gold tends up" is true yearly, false at M1 pullback scale; the gate's silence = losses dodged (~$1,600/twelve weeks), not harvest missed |
| ZeeSimple v1.20 | 88111 | RETIRED (Aug 18) | attempt 7 at Feb-11 tempo; every-retracement ≈ random entry paying spread rent. Live-forward confirmed the tester (−$37/138 closes). Ladder rungs live in its inputs |
| ZeeUHV_R1 v1.00 | 88121 | RETIRED (Aug 18) | rung 1 frozen (real retracement only, 66/day = Feb-11's tempo); kind-tape-only |
| TurtleTradeLogger v1.04 | — | LIVE | self-healing: `BackfillMissedDeals()` at init (the fills file had silently lost 96 positions/−$590 during disconnects) |

## The campaign arc (six-period totals, same court)

```
2026-08-16  shipped config        −1,615
2026-08-17  + Law 9               −1,178
2026-08-17  + Law 10c               −639
2026-08-18  + hold 3                −351
2026-08-18  + rank 6                −229
2026-08-19  + the pulse (v1.45)     +276   ← first positive M1 config ever
2026-08-19  + Diamond Season        +449   ← live now, on probation
```

## Standing cautions (read before trusting any number)

1. Python backtests NEVER promote — MT5 tester or live fills only (CLAUDE.md prime rule).
2. Identical numbers across tester arms = VOID run (`testing/test_tips.md` Part 13).
3. A freshly published day can be cached half-baked in the rig (Part 12).
4. v1.49 carries an overfit caveat (heavy same-day iteration on the six court periods)
   — live-forward receipts required before lots rise; revert path = v1.45 defaults.

## BasedOnLaws v1.43 — 2026-08-28 — HIS PAGE RESTORED, on receipts

Zee: *"let's please test the variants of the LAWS EA. because that's the one written per
our rules. and if some rule is bent by us, test the variants etc."*

Two clauses I had shipped LOOSER than LAWS.md now carry his own values. Court: MT5
Strategy Tester, 100% real ticks, 5–27 Aug, 0.01 lots, his OANDA chart in strict mode.

| clause | I shipped | HIS TEXT | net at mine | net at his |
|---|---|---|---|---|
| a. momentum body | 0.50 | **0.70** | +83.39 (PF 1.19) | **+98.82 (PF 1.25)** |
| b. breakout quieter than the UHV | 1.5x | **1.0** | +83.39 | **+102.16 (PF 1.30)** |

Clause b is monotone on his tape — 1.0 (+102.16) > 1.2 (+77.71) > 1.5 (+83.39) > off
(+66.84). A hill, not a spike, which is the shape three other findings this week failed
to produce.

**Combined, with the two guards I invented kept in place: +158.35 all hours (119 trades,
PF 1.54) or +134.97 New York only (39 trades, 46% WR, PF 2.32, $3.46/trade against the
shipped machine's $0.49).**

ALSO MEASURED, and left ON with receipts rather than as silent defaults:
* `InpBreakHold 0.45` — my invention, not on his page. Removing it costs **−18.29**.
* `InpMaxRiskPts 10.0` — my invention, picked with no evidence. Removing it turns the
  machine NEGATIVE (−40.70, PF 0.93) and nearly doubles the worst trade (−10.18 →
  −19.94). It is load-bearing.

NOT CHANGED, and his to decide: **line 47, New York only.** He chose all-hours on 25 Aug
from v1.30 receipts (+1,335 vs +1,044 over 7 days). With these clauses corrected the
ranking REVERSES — NY-only now wins on quality and nearly matches on money. The evidence
moved; the choice is his.

LIMITS, stated plainly: eight days of OANDA archive is the entire testable world for this
EA, twenty configurations were tried on that one tape, and the live record is four
trades. The DIRECTION is sturdy (his values won on every clause separately and together);
the MAGNITUDES are not. Full report: daily_reports/_LATEST/LAWS_VARIANTS_REPORT.md

Propagated to BasedOnLawsA/B/C so the arms do not drift from the main EA.

## ZeeUHV_Diamond v1.12 — THE SWEEP REQUIRED (2026-09-01)

**magic 88154 · 0.10 lots · stacked x2 · `InpReqLaws = 4`**

Zee, 31 Aug: *"there were some laws of conviction before the OANDA volume was used, can
you test them all now on the OANDA volume? ... be careful while testing to simulate exact
real environments such as random delays etc"*

All eight Laws of Conviction were built and tuned while the EA judged UHVs on **Blueberry
volume** — the feed proved on 30 Aug to invert the sign of a day. The Diamond carried only
three of them, and only as SIZE: they added tickets to trades it took anyway and never
refused one. `InpReqLaws` makes any subset a GATE; the other five were ported from
ZeeUHV.mq5 verbatim in behaviour.

Environment: **his OANDA chart, RANDOM delay** (fixed 163 ms produces ladder spread 0.13
against live's 0.57; random produces 0.99), 0.10 lots stacked — as it trades.

| law required | trades | WR | net | PF |
|---|---|---|---|---|
| none — as it traded | 511 | 91% | +2,184.40 | 1.45 |
| **4 — THE SWEEP** | **488** | **93%** | **+4,332.80** | **2.81** |
| 16 wick + quieter | 433 | 93% | +3,043.90 | 1.95 |
| 8 EMA-5 close | 508 | 91% | +1,800.10 | 1.37 |
| 2 selling climax | 124 | 95% | +427.30 | 1.39 |
| 64 defended level | 440 | 89% | +577.50 | 1.12 |
| 1 UHV is loud *(vol)* | 199 | 93% | +99.50 | 1.05 |
| 32 ref-8 break | 241 | 89% | −654.80 | 0.82 |

**OUT OF SAMPLE — the test that killed three other candidates this week:**

| window | none | sweep |
|---|---|---|
| 05-07 Aug | −1,223 / PF 0.56 | −1,261 / PF 0.56 |
| 17-19 Aug | +692 / PF 1.74 | **+1,297 / PF 5.22** |
| 20-29 Aug *(in-sample)* | +2,184 / PF 1.45 | **+4,333 / PF 2.81** |
| **three windows** | **+1,653** | **+4,369** |

It raises PROFIT FACTOR rather than trade count — 488 against 511, refusing 23 setups
and nearly doubling the money. The 2R target, the volume floor and deliberate spacing all
reversed sign out of sample; this did not.

**What did NOT ship, and why it matters:** law 1 ("the UHV is loud") collapses on his
chart — +99.50 against +2,184.40. Its threshold is a multiple of neighbouring volume,
tuned when those numbers were Blueberry's, which run about a fifth the scale of OANDA's.
It has been worthless since the feed changed.

**Limits.** Three windows. And no law rescues bad tape — 05-07 Aug loses under every one
of the eight.

## ZeeUHV_Diamond v1.14 — his line 42, obeyed at last (2026-09-01)

**magic 88154 · `InpStructStop = 0.50` (five pips) · hold 20m · sweep required**

Zee: *"can you test setting the SL at the last low (retracement's low) 5-7 pips beneath
it maybe"* — then, on the result, *"ok ship the structural stop"*.

LAWS.md line 42 has said this from the beginning. The Diamond never did it: a flat $20
from wherever the first ticket filled, which is why one bad basket cost 8 x 20 x 0.10 x
100 = $1,600 no matter what the chart was doing.

| window | flat $20 | 5 pips structural |
|---|---|---|
| 20-29 Aug *(in-sample)* | +4,337 · PF 2.73 · **DD 18.9%** | +2,579 · PF 1.96 · **DD 9.1%** |
| 17-19 Aug | +3 · PF 1.00 · DD 15.8% | +202 · PF 1.20 · **DD 7.7%** |
| 05-07 Aug | −1,243 · PF 0.59 · DD 37.8% | **−342** · PF 0.84 · **DD 22.2%** |
| **three windows** | **+3,097** | **+2,439** |

**It makes less money — −$658 — and shipped anyway.** It halves the drawdown in every
window (37.8→22.2, 15.8→7.7, 18.9→9.1) and cuts the worst window by 73%. Nothing else
tested this fortnight has touched the bad days at all: the sweep, the hold cap, the 2R
target, the volume floor and deliberate spacing all improved good tape and left the
catastrophes exactly where they were. This account has been to $53.99 once.

Five pips beat his six; both sit inside noise of each other and both inside his stated
5–7.

**A CORRECTION THIS COURT FORCED.** On 28 Aug the D07 variant "tested" this law, went
0-for-4, and I reported *"your structural stop never helps this machine"*. D07 computed
the buffer as `InpLawStructStop * 10 * _Point` — 0.60 became 0.06 in price, six TENTHS
of a pip. It stopped out on almost any tick. That court measured my arithmetic, not his
law. BasedOnLaws has had the units right since it was written (`sl = deep - 0.60`, and
0.60 in price IS six pips) — and BasedOnLaws is the one EA with no catastrophic day.

**The Diamond now, cumulatively:** v1.11 on this window made +2,184 at PF 1.45. v1.14
makes +2,579 at PF 1.96 with half the drawdown — and every change came from a law on
his page that the machine had been ignoring.

## ZeeUHV_Diamond v1.15 — his eye or no trade (2026-09-06)

**magic 88154 · `InpOandaVolume = 1` · `InpOandaStrict = true` · `InpVolFreshSec = 90`**

Zee: *"we donot wish to use broker volume, we want to completely transition to OANDA
volume taken from tradingview. any broker volume trades waste our time"*

**WHAT PROMPTED IT.** He opened Friday's review page, looked at the 04:28 SELL that lost
$123.10, and the chart did not match the trade. The EA logged `UHV 02:23 (vol 87, low
4472.48)` — Blueberry's numbers to the decimal. His own chart shows **150** that minute,
and makes **02:22 (152)** the louder bar. A different candle, a different trigger, a
trade that does not exist on his chart.

**THE SWITCH ALONE WAS NEVER ENOUGH.** `InpOandaVolume` has existed since v1.10 and
defaulted to 0, but flipping it would not have fixed this: `BarVolume()` fell back to
the broker **per bar, silently**, whenever the table lacked a minute. A single decision
could read his chart for the UHV and Blueberry's for the neighbours. Three changes:

* `InpOandaStrict` — a missing OANDA minute returns −1, and `VolWindowWhole()` refuses
  the whole setup. Checked across all `InpTrendLook + InpRetraceBack + 8` bars, because
  checking only the UHV leaves the loudness test, the quieter-than-UHV test and the
  20-bar average reading broker numbers one level down.
* `InpVolFreshSec` — a stalled bridge stands down instead of reverting. The bridge died
  for **61.8 hours** over 5–6 Sep and nothing noticed; without this the EA would have
  run on broker volume the whole time and called the results his.
* Both gates run BEFORE any law, so a feed fault can never be misread as the laws
  refusing a setup.

Levels, stops and fills stay Blueberry's. We trade his broker, we judge his chart.

### The court — same EA, same window, only the feed changes (real ticks, 163 ms)

| window | broker | OANDA + strict | OANDA loose | trades b / s / l |
|---|---|---|---|---|
| 31 Aug – 4 Sep | −555.40 | **−229.40** | −229.40 | 108 / 106 / 106 |
| 17–22 Aug | −1,165.80 | **+377.80** | +483.50 | 256 / 266 / 274 |
| 5–8 Aug *(see caveat)* | −1,245.40 | +869.40 | −270.00 | 198 / 98 / 208 |

**THE CAVEAT, AND IT IS LOAD-BEARING.** The 5–8 Aug row is **not an apples-to-apples
comparison and must not be quoted as one.** `oanda_vol.csv` begins 05 Aug 15:11 and ends
07 Aug 04:26 — 2,108 minutes of a ~4,320-minute window. Strict therefore traded *a
different and smaller slice of time* than broker did; its +869.40 and PF 5.07 are
measured on under half the window and are contaminated by a time-of-day selection
effect. The honest reading of that row is "strict refused the half it could not see",
not "strict earns $1,139".

**The two clean windows carry the finding.** 17–22 Aug has 97% coverage (266 trades
against 274) and still turns **−1,165.80 into +377.80**. 31 Aug – 4 Sep returns
*identical* numbers strict and loose — no holes at all — and still gains **$326**. Both
windows move the same way, and both improve profit factor (0.62→1.20, 0.66→0.82) and
drawdown (3.69→1.38, 3.05→2.21) alongside the money.

This corroborates the four-day live measurement recorded at v1.58: broker +433.90 vs
OANDA +1,358.10, better on 3 of 4.

**REQUIRES A REATTACH.** `InpOandaVolume` already exists on the attached chart with a
stored value of 0; a changed default only applies on a fresh attach. F7 + drag before
the Monday open or it keeps trading on broker volume.

**NEW OPERATIONAL RISK, STATED PLAINLY.** With no fallback, the OANDA bridge is a single
point of failure. It runs ~40 s behind routinely and was dead for 61.8 hours this
weekend. BasedOnLaws, already strict, skipped 6.0% of its bars for this reason and 100%
of Friday's last two hours. A dead bridge is now a dead EA — which is what he asked for,
and it means the bridge's own alerting (GreenAPI, currently 401) is no longer optional.

**RIG TRAP FOUND (worth its own line).** The headless rig silently auto-updated to build
6182 mid-court; every later launch tried to install it, hit a sharing violation and
exited in 2 s with **no report** — which looks exactly like "strict refused everything".
Two windows had to be re-run. Kill the `liveupdate` stubs by PATH (never the Blueberry
terminal) and clear the payload before trusting a court that returns no report.

## LAW 45 as a gate on the Diamond — TESTED, NOT SHIPPED (2026-09-07)

**`InpStopOnLastLow`, default false. Built, measured, left dark.**

Zee: *"the EA keeps performing until there occurs the end of a trend. at the end of the
trend the EA expects the price to go upwards still whereas the price takes a turn
downwards. that last trade is in much loss ... that last losing trade eats up all the
profit"*

His diagnosis is exactly right, and his own LAWS.md line 45 already states the cure:
*"we stop buying, when the last low is broken .. we keep trading until the last low is
safe (unbroken below). Whenever a high is broken, the deepest point (the lowest point)
is the confirmed higher low."* The Diamond has never implemented it. Ported MQL->MQL
from BasedOnLaws' `CamelTrend()`, which has carried the law since 2026-08-23.

**WHY `TrendNow()` CANNOT DO THIS JOB.** It declares an uptrend dead only after TWO new
pivot lows print with the newer below the older, and a pivot needs `InpPivot` bars each
side to confirm. At a top the structure breaks and `TrendNow()` keeps returning +1
through the confirmation lag. That lag is the window the losing trade is taken in.

### THE FINDING THAT COST THE MOST: line 45 is a STATE, not a test

The first implementation asked *"is the close below the last low right now"* at the
moment of the breakout. **0 refusals in 2,763 bars** — 106 trades with the gate off,
106 with it on, identical to the cent. The test was evaluated at the one instant it
cannot fail: a breakout is a candle thrusting UP through a level, while the guard is a
pivot low confirmed at least `InpPivot` bars earlier.

His sentence is a latch. *"We STOP buying, WHEN the last low is broken .. we KEEP
trading UNTIL the last low is safe."* Buying stops at the break and stays stopped until
a high is broken and a new higher low is confirmed under it. At a trend's end the low
breaks, price bounces, and the breakout fires on the bounce — the trade Zee describes,
and the one a snapshot waves through. Rebuilt as `LastLowUpdate()`, run once per closed
bar: break by BODY (his line 13: *"the low must be broken by body not wick"*), resume
only on a body close above the last hump top. Guard only ever rises. Short side mirrored.

### The court — real ticks, 163 ms, OANDA volume, v1.15 strict

| window | off | ON | delta | tickets off/ON | refused | DD off → ON |
|---|---|---|---|---|---|---|
| 31 Aug – 5 Sep | −229.40 | **−12.50** | **+216.90** | 106 / 98 | 8 | 2.21 → 2.14 |
| 17–22 Aug | +377.80 | +215.80 | **−162.00** | 266 / 228 | 38 | 1.38 → **1.70** |
| 5–8 Aug | +869.40 | +869.40 | 0.00 | 98 / 98 | 0 | 0.78 → 0.78 |
| **three windows** | **+1,017.80** | **+1,072.70** | **+54.90** | 470 / 424 | 46 | — |

**VERDICT: NOT SHIPPED.** One window helped, one hurt, one was untouched. The
three-window gain of $54.90 is the residue of +216.90 and −162.00 cancelling — noise,
not signal, on 470 tickets.

The in-sample window is genuinely striking: it refused ONE basket of 8 tickets and that
basket carried −$216.90, turning the week from −229.40 to −12.50. That is exactly the
shape Zee described. But out of sample the same latch refused 38 tickets and gave back
$162, and made drawdown WORSE (1.38 → 1.70). It is not selectively removing the
trend-end trade; it removes good trades at the same rate.

**This is the 2R target's failure repeating** — excellent in-sample, sign-reversed out.
Kept as a dead input with receipts, default false, so the next session does not rebuild
it from his page and read the first window as a result.

**WHAT IS STILL TRUE AND UNADDRESSED.** Law 45 targets the trade that ends the run. It
does nothing about the geometry that makes that trade fatal: last week's live R:R ran
0.05R to 0.63R, median 0.18R, where one full loss erases five and a half wins. Even
with the latch on, the best window is PF 0.99 — break-even, not profitable.

### Rig traps found on the way (all produced a clean exit code and a report file)

1. **Bool sweep syntax.** MT5 needs numeric `0||1||1`; `false||0||true` is rejected with
   *"no optimized parameter selected"*, ends in ~55 s, writes a header-only report.
2. **`sync_experts()` overwrites the rig build.** It copies every `.ex5` from the LIVE
   terminal, including the EA under test. Compile into the rig AFTER the sync or the
   court silently tests yesterday's binary.
3. **Do not verify a build by searching the `.ex5` for an input name.** MQL5 stores them
   encoded — `InpTargetPts` does not appear either. Check the compiled SOURCE, and check
   the optimisation report's COLUMNS afterwards.

A run that tests nothing and a run that finds nothing are indistinguishable except by
the clock: 55 s where 600 s is expected.

## ZeeUHV_Diamond v1.16 — the hump budget (2026-09-09)

**magic 88154 · `InpMaxHumps = 3` · SHIPPED AGAINST THE BACKTEST, ON HIS INSTRUCTION**

Zee, with a drawing of an uptrend labelled *trend begins* / *trend ends*: *"When a trend
starts on 1 minute scale it makes 2..3..X definite camel humps.. after a certain number
of humps the trend expires ... if we stop after the price has made a new trend and the X
number of humps are done, we might be able to avoid the ONE LAST TRADE that is taken at
the end of the trend."*

**WHY THIS MECHANISM IS DIFFERENT FROM EVERY EARLIER ATTEMPT.** `TrendNow` needs two
fresh pivots; law 45 needs the low already broken. Both answer *after* the reversal has
begun — late by construction, which is when the losing trade is taken. Counting FORWARD
from a trend's birth needs no confirmation: the fourth hump is the fourth hump whether
or not the top has printed.

### The measurement that set the number

Instrumented over **113 trends**, 31 Aug – 5 Sep, real ticks:

| humps before the trend flips | trends | cumulative |
|---|---|---|
| 1 | 15 | 13% |
| 2 | 34 | 43% |
| **3** | **25** | **65%** |
| 4 | 11 | 75% |
| 5–9 | 26 | 98% |
| 11, 17 | 2 | 100% |

**median 3 · mean 3.5 · max 17.** His model — *"hump 3 trade, hump 4 hmm maybe it
shifts"* — is what the tape does. He had the number right.

### Why 8 was withdrawn

The sweep's best arm was budget 8: +2,427.30 across three windows, positive in 3/3,
against OFF's +2,287.40 in 2/3. A diff of the deal lists named the single basket it
refused — the 01 Sep 03:28 buy at 4460.34, which is the live −$323.40 trade taken 19
minutes after the 4454.43 buy had just won +$75.30, six dollars higher, at the top of
the same push. Real mechanism, real trade.

**But the trade-by-hump histogram killed it.** Of 28 fires: hump 0 → 14 trades, hump 1
→ 5, hump 2 → 4, hump 3 → 2, humps 5/6/8 → one each. **Budget 8 refuses ONE trade in
28.** Its whole three-window edge rests on a single basket — a placebo that happened to
catch a loser. Zee spotted this before the ledger did: *"i hope u're sure.. because
otherwise this number could be so high that it might result in a loss."*

### What 3 costs, stated plainly

| budget | three windows | windows won | refuses |
|---|---|---|---|
| OFF | **+2,287.40** | 2/3 | — |
| **3 (SHIPPED)** | **+768.10** | 1/3 | ~4-5 of 28 |
| 8 (withdrawn) | +2,427.30 | 3/3 | 1 of 28 |

**This ships knowingly below the backtest.** He read the numbers and chose the rule that
actually implements his law over the one that scores better by doing nothing: *"let's set
it at 3 and activate it on the diamond. this could result in us avoiding trades taken at
the end of a trend where trend starts to shift."* Forward days are the jury.

### The open question this leaves

**68% of fires happen at hump 0 or 1** — right after a direction flip, at the START of a
trend. So the Diamond is not systematically trading late into exhausted trends. But the
counter resets on the ENGINE's direction flip, and `TrendNow` flips when it finally
catches up rather than when a new trend truly begins — so a "hump 0" trade can still sit
at the top of a larger move. If so the theory is right and the instrument is coarse, and
humps counted against the M15 structure (the only other arm to go 3/3 this week) is the
untested version.

Also shipped in this version, all default OFF and each with receipts in the session log:
`InpTrendMode` (0 stale-pivot · 1 CamelTrend · 2 EMA slope), `InpTrendTF` (read the trend
on M5/M15), `InpLastLowMode` (law 45 snapshot or latch), `InpSlMode` (stop at the
defended low), `InpTargetR` / `InpBreakEvenR` (the teacher's 1:2 with breakeven at 1:1 —
REFUSED, 27% win rate against the 33% a 2R design needs), `InpNyOnly` (NY session).

## ZeeUHV_Diamond v1.17 — hump budget 3 -> 2 (2026-09-09)

Zee, hours after v1.16 shipped: *"let's make it 2 instead of 3. what difference would
that make?"*

| budget | aug17 | aug24 | aug31 | three windows | trades | windows won | refuses |
|---|---|---|---|---|---|---|---|
| OFF | +378 | +2,139 | −229 | **+2,287.40** | 762 | 2/3 | — |
| **2 (SHIPPED)** | **+277** | +1,060 | **−507** | **+830.30** | **324** | **2/3** | 9 of 28 |
| 3 (v1.16) | −526 | +1,509 | −215 | +768.10 | 462 | 1/3 | 5 of 28 |

**2 beats 3 on total and on window consistency** — it rescues aug17 (−526 → +277) — but
it is WORSE on aug31 (−506.90 against −215.10), the window that holds the end-of-trend
losses this rule exists to prevent. It blocks hump-2 trades that were paying there.

It is also one tier stricter than his own stated model. He described *"hump 1 trade,
hump 2 trade, hump 3 trade, hump 4 hmm maybe it shifts"*; budget 3 permits humps 0-1-2,
budget 2 permits 0-1. Shipped on his instruction with both tables in front of him.

**Trade count is the thing to watch live:** 324 against the unrestricted 762 over three
windows — roughly a third of setups declined. If the forward days show the trade count
collapsing without the end-of-trend loser disappearing, the budget is cutting the wrong
trades and 3 (or off) is the fallback.

---

## VSISA v1.06 — diagrams 10-12: the NO SUPPLY TEST, made faithful and measured (2026-09-15)

**Who ordered it.** Zee: *"i've added an important concept in the diagram 11,12 read and test"*.

**The concept.** Diagram 11 spells out the full sequence, and d12 repeats it:
increasing red volumes with a very large volume on the last bar -> a bullish bar confirming
the reds were buying -> *"the next bar is again red (after the blue surprisingly) -> this is
testing -> WE CALL IT THE NO SUPPLY TEST -> if on testing volume is SMALL WE MUST WAIT FOR
NEXT BAR BULLISH MEANS SETUP CONFIRMED we take entry -> if in case on no supply test it
were big volume it would mean sustained buying."*

This is `InpConfirmMode = 1`, which already existed and already matched the sequence —
EXCEPT for one gap. The old code only required the test bar not to break the setup extreme,
so a bar closing UP could serve as the "test" of a buy, which is not a test of supply at
all. **`InpTestRed` added** (default false) to require the test bar to close AGAINST the
trade, as he draws it.

**The fidelity fix genuinely helps — and the rule still fails.** Apr 1 -> Sep 15, 5.0R:

| config | trades | WR | net | $/trade |
|---|---|---|---|---|
| **baseline, no test** | **322** | **25%** | **+$8,010** | **+$24.88** |
| test, any direction, vol<=0.90 | 51 | 20% | +$106 | +$2.07 |
| **test, RED bar (faithful), vol<=0.90** | 30 | 23% | +$559 | +$18.63 |
| test, RED bar, vol<=0.70 | 12 | 17% | +$57 | +$4.72 |
| test, RED bar, vol<=1.10 | 40 | 18% | −$66 | −$1.65 |

Requiring the red bar multiplies the net five-fold ($106 -> $559), so the gap was real. But
the test as a MANDATORY gate removes **91% of all trades** (322 -> 30) and returns $559
against $8,010.

**And it is not a quality filter either — that is the decisive test.** A confirmation tier
should earn MORE PER TRADE than the base setup. It earns **$18.63 against the base's
$24.88**, on a lower win rate (23% vs 25%). So the no-supply test does not identify better
setups; it identifies fewer of the same ones, two bars later and with a wider stop — because
entry moves to the confirming bar while the stop stays under the reaction candle.

**Diagram 10 and the rest of 11 were already covered.** d10's *"when going up the market has
lower volumes ... lower than the reds previously"* IS Law 3, the live trigger. d11's *"small
candle with high volume is a very powerful signal"* is the cap bar, tested and negative in
v1.03, and again as effort-per-range in v1.04.

**Default unchanged: `InpConfirmMode = 0`.** The shipped 1:5 config is untouched.

---

## VSISA v1.05 — SHIPPED: the target runs to 1:5 (2026-09-15)

**Who ordered it.** Zee: *"SL should not be tied to TP. SL can be below the first reaction
candle's low (low volume bullish candle after bearish background big volumes).. and TP can
be very high up until 1:7 .. can you test this?"* — then, on the result: **"ship 5.0"**.

**What changed.** `InpTargetR` default **2.0 -> 5.0**. That is the whole change; no logic was
touched, and the stop rule is untouched and still structural (`InpStopRef=0`, 120 points
under the reaction candle's low — which is already exactly what he describes).

**I HAD THIS WRONG and the error is recorded in the source.** I swept the R ladder only as
far as 2.5R, found it worse than 2.0R, and shipped 2.0R as the optimum. 2.0R is a LOCAL
peak — the curve dips at 2.5-3.0R and climbs to a second, higher one:

| InpTargetR | WR | net | maxDD | % of $10k funded |
|---|---|---|---|---|
| **2.0 — the old default** | 43% | +$5,502 | $946 | 9.5% |
| 2.5 | 36% | +$4,503 | — | |
| 3.0 | 32% | +$4,624 | — | the dip that fooled me |
| 4.0 | 27% | +$6,374 | $1,014 | 10.1% ⚠ breach |
| **5.0 — SHIPPED** | **25%** | **+$8,153** | **$950** | **9.5%** |
| 6.0 | 22% | +$8,744 | $1,322 | 13.2% ⚠ breach |
| 7.0 | 19% | +$8,112 | — | |

**+48% profit for identical drawdown**, and the only rung that stays under a 10% funded
limit — 6.0R earns $591 more and would breach the account.

**Walk-forward — the best of the whole session.** Apr–Jun **+$4,022** · Jul–Sep **+$3,988**:
the two halves within 1% of each other on a split it was never fitted to, beating the old
default on BOTH (+$3,621 / +$1,741) and more than doubling the unseen half.

**Nothing about the risk changed.** Same 322 setups, same structural stop, same average loss
(−$57.35 at every rung). Only the winners run: avg win **+$279.62** against 2.0R's +$114.99,
payoff 4.9:1. That is precisely what decoupling the target from the stop buys.

**THE COST, so it is never mistaken for free:** win rate **43% -> 25%**, worst losing streak
**11 -> 15**. The H1 trend filter does not rescue it — at 5.0R it halves the profit and
leaves WR at 24%; that benefit was specific to 2.0R.

**Ship verification.** The compiled v1.05 binary re-run on Apr 1 -> Sep 15 returned
**79W/243L, NET $8,010.00** — identical to the pre-ship measurement, so the default in the
source is the one that was tested. Report `AXI_bt_224426.htm`.

**ZEE MUST REATTACH** — MT5 does not hot-reload inputs. The live chart keeps running 2.0R
until the EA is re-dragged onto it, and the banner line must read `v1.05`.

---

## VSISA v1.04 — diagram 9: effort per unit of result (2026-09-15)

**Who ordered it.** Zee: *"i've added another diagram 9. test it?"*

**What diagram 9 adds, and why it matters.** It is the Base Case stated properly for the
first time. He picks two candles and holds one variable fixed: *"let's take the forth blue
candle, and the seventh blue candle -> both has same spread (height of candle body). 4th ->
volume low -> low supply. 7th -> supply hit so a big volume."*

Comparing volume at EQUAL SPREAD is volume-per-range. That diagnoses the v1.03 cap-bar
failure exactly: `InpAnomaly` demanded a small ABSOLUTE range, which is rare and discards
every large bar that is also working hard. Normalising by range asks only the question he
asks — how much volume did this bar spend for the distance it travelled?

**What shipped.** `InpEffortMin` — the last setup bar's volume/range against the swing
average volume/range. **Default 0.00 = OFF.**

**The receipts — no win-rate gain. Again.** Axi real ticks, Apr 1 -> Sep 15, stop 120 / 2.0R:

| InpEffortMin | trades | WR | net |
|---|---|---|---|
| **0 (off)** | 322 | **43%** | **+$5,362** |
| 1.00 | 196 | 41% | +$2,379 |
| 1.20 | 140 | 42% | +$1,650 |
| 1.40 | 83 | 43% | +$1,094 |
| 1.60 | 45 | 40% | +$460 |
| 1.80 | 28 | 54% | +$871 |
| 2.00 | 10 | 40% | +$72 |

The 54% at 1.80 has 40% on both sides of it and rests on 28 trades — a spike, not a plateau.

**Diagram 9's conjunction also tested.** He describes the ideal as low volume AND a small
top wick AND closing near the low. Run as quiet-only (WickMode 0) x close location x
ceiling, every cell landed between 42% and 45% against the 43% baseline, each one costing
money for the trades it removed.

**THE STANDING RESULT AFTER ~30 FILTER CONFIGURATIONS TODAY.** Win rate has not moved off
39-45% for ANY candle-or-volume-shape filter: reaction volume ratio, a volume floor, cap
bar, close location, engulfing, effort per range, the wick exception. Each one removes
winners and losers in almost the same proportion. The single exception is the H1 TREND
filter — market context, not candle shape — which reaches 48%.

That is now a measured claim about where this strategy's edge is NOT, and it should stop a
future session re-testing the same family of ideas: the entry-shape features are exhausted;
context and exit are where the remaining leverage sits.

---

## VSISA v1.03 — diagrams 3-8 read, encoded, and MEASURED (2026-09-15)

**Who ordered it.** Zee: *"i've added new diagrams and their description (until diagram 8)
in the LAWS_VSISA. can you read them and check the diagrams and use this better
understanding to improve our winrate?"*

**What the new diagrams actually add.** Three testable laws, none previously in the EA:

1. **THE CAP BAR — effort against result.** Stated four times: d4 *"small candle with big
   volume shows that big demand came that caps the market"*; d6 *"next candle is small blue
   with a large volume -> supply was hit"*; d7 *"low height / spread but volume is bigger ->
   end of rising market -> price capped"*. The signature is both halves ON THE SAME BAR.
   `InpAnomaly` had the small-spread half; the loud half was missing.
2. **THE REACTION CLOSES AT ITS EXTREME.** d7 *"closing of reaction candle's body is strong
   bearish"*; d8 *"on the low the closing of candle happened"*. `InpBodyFrac` only sizes the
   body; it cannot tell a close-on-the-low from a mid-range close with wicks both sides.
3. **THE REACTION ENGULFS the previous body** (d8) — `InpEngulf` already existed, untested
   since the geometry corrections.

**What shipped.** `InpCapVol` (last setup bar's volume >= x avg) and `InpCloseLoc`
(reaction close within the top/bottom fraction of its range). **Both default 0 = OFF.**

**The receipts — none of them improved win rate durably.** Axi real ticks, Apr 1 -> Sep 15,
M5, geometry fixed at stop 120 / 2.0R:

| rule | trades | WR | net |
|---|---|---|---|
| **baseline** | 322 | **43%** | **+$5,362** |
| cap bar 0.70 / 1.2 | 15 | 67% | +$786 |
| cap bar 0.80 / 1.0 | 45 | 44% | +$706 |
| cap bar 0.90 / 1.0 | 58 | 43% | +$733 |
| cap bar 1.00 / 1.0 | 84 | 39% | +$534 |
| close loc 0.60 | 293 | 42% | +$4,630 |
| close loc 0.70 | 244 | 42% | +$3,769 |
| close loc 0.80 | 188 | 40% | +$2,599 |
| engulf | 111 | 45% | +$2,698 |

- **Cap bar: NOT PROVEN.** The 67% is 15 trades (4W/3L and 6W/2L across the two halves) and
  it decays monotonically to baseline as the sample grows. `InpCapVol` 1.00 and 1.20 return
  BYTE-IDENTICAL results, so the volume half never binds — bars small enough to pass the
  spread test are already loud. The rule as written adds nothing the spread test did not.
- **Close location: REFUTED.** 42% against 43%, at every threshold, costing money throughout.
- **Engulf:** +2 points of WR for half the profit.

**What the diagrams DID corroborate.** d3 *"reaction candle has high volume, means there is
still alot of supply here... so its not a strong setup"* and d5 *"the pink volume is also
relatively big on the reaction candle... so there's buying on this bar too"*. Both say a
LOUD reaction is a weak setup — and the trade-by-trade data agrees exactly:

| reaction | trades | WR | $/trade |
|---|---|---|---|
| QUIET (the core rule) | 289 | 43% | +$16.55 |
| **LOUD + wick (the InpWickMode=2 exception)** | 16 | **25%** | **−$11.12** |

The wick exception is a losing group, and on sells it is 22% WR / −$21.89 a trade. But it is
only 16 of 322 trades, so removing it moves win rate 43% -> 43.8% and costs $131. Left ON.

**Conclusion: no win-rate lever was found in diagrams 3-8.** The best WR config on the book
remains 2.0R + H1 trend + vol floor (48% full window, 43% out-of-sample). Defaults unchanged.

---

## VSISA v1.02 — the target decoupled from the stop (2026-09-15)

**Who ordered it.** Zee: *"yes try decoupling them to check what's the best config"* —
after the 14 Sep 04:10 loss showed that widening the stop cannot rescue a trade while
the target is a multiple of it, because the target retreats as fast as the stop widens.

**What changed in code.** `InpTargetMode`: 0 = R multiple (the coupled original, still
the DEFAULT), 1 = a fixed distance `InpTargetPts`, 2 = the swing origin — the level the
leg came from, read off the pivot `SwingLen()` already finds. Guards `InpTgtMinR` /
`InpTgtMaxR` refuse a target on the wrong side of entry or too close to pay the spread.
Mode 0 regression-checked: identical 170 trades, +$3,621.05 Apr–Jun, unchanged.

**The receipts.** Axi real ticks, M5, model 4, buffer 120 throughout:

| config | Apr–Jun (tuned) | WR | maxDD | Jul–Sep (unseen) | WR | maxDD | total |
|---|---|---|---|---|---|---|---|
| **mode 0, 2R — shipped** | +$3,621 | 46% | $460 | +$1,741 | 39% | $910 | +$5,362 |
| mode 1, 2400 pts | +$3,949 | 27% | $765 | **+$3,309** | 26% | $906 | +$7,257 |
| mode 1, 3900 pts | +$4,117 | 18% | $1,449 | **+$5,947** | 21% | $862 | +$10,063 |
| mode 1, 4500 pts | +$4,885 | 17% | $1,847 | +$5,784 | 18% | $865 | +$10,669 |

Decoupling is a REAL out-of-sample gain, not a tune: every fixed-target row beats the
shipped config on the half it was never fitted to. Exits were audited — all 152 trades
in the 3900 run closed as tp (32) or sl (120), none marked out at test end.

**Mode 2 (swing origin) LOST**: best +$2,949 Apr–Jun against mode 0's +$3,621, and its
optimum sat on the `InpTgtMaxR=3.0` bound — it only works by being capped back into R
terms, which is the coupling it was meant to escape. Not recommended.

**The far targets turn over** past ~9,000 points and drawdown explodes (6.93% at 12,000,
10.28% at 15,000), so 3900–4500 is a real interior band, not a runaway.

**The stop stays at 120.** Buffer 400 with a near target — the exact pair that would have
saved his 14 Sep trade — makes +$3,978 on the tuned half and **−$1,056** on the unseen
one. Every version of "widen the stop" has now failed out-of-sample three times.

**His named trade is still a loss** under every config above: it was stopped at 04:15
before any target mattered, and only a 361pt+ buffer changes that.

**DEFAULT UNCHANGED at mode 0.** This trades win rate (46% → 27%) for money, which runs
against the standing win-rate goal, so it is Zee's call and not a silent flip.

**Receipts:** grids `tgt_fixed`, `tgt_swing`, `wide` in `monitor/strategy_lab/axi_sweep.py`
· reports `AXI_bt_1940*`–`1943*`.

---

## VSISA v1.01 — the reaction-volume floor, built and left OFF (2026-09-15)

**Who ordered it.** Zee: *"i think the reaction candle's volume as compared to the --
high volume selling background candle's volume .. if the reaction candle volume is too
near the selling volumes then our setup might be failing.. such as the setup at Fri 11
Sep 2026 04:30 broker TESTER -86.30 / can u test the difference X between the reaction
volume vs the high volumes in the background"*

**What changed in code.** One new input, `InpMinVolPct` (default **0.00 = off**): a LOWER
bound on the reaction volume, mirroring the existing `InpLowVolPct` ceiling. No
behavioural change at the shipped default. Version and banner string bumped together.

**The receipts — his hypothesis is not supported.** 322 fires from one Axi real-tick run
(Apr 1 → Sep 15, M5, model 4) were joined 1:1 to their own MT5 outcomes, 305 closed:

| measure of "too near the selling volume" | winners' median | losers' median | gap |
|---|---|---|---|
| reaction / setup average (the live rule) | 0.856 | 0.865 | +0.009 |
| reaction / swing MAX (his literal words) | 0.815 | 0.810 | −0.005 |
| reaction / swing average | 1.385 | 1.335 | −0.050 |

No separation in any form. His named trade, 11 Sep 04:30 (−$86.30), fired at 0.87 — the
**52nd percentile**, inside the best-performing band. It was an ordinary setup that lost.

**What the same data DID show — the shape is a band, not a ceiling.** By quintile of
reaction/setup, and stable in both walk-forward halves independently:

| band | trades | WR | $/trade |
|---|---|---|---|
| 0.39–0.76 (quietest) | 61 | 36% | **6.40** |
| 0.76–0.83 | 61 | 46% | 23.13 |
| 0.83–0.89 | 61 | 48% | **27.38** |
| 0.89–0.94 | 61 | 39% | 12.89 |
| 0.94–2.05 (loudest) | 61 | 39% | 5.68 |

The QUIETEST fifth is the worst group on the book. That contradicts the document's *"the
lower the volume on it, the stronger the signal"* read as a monotonic rule.

**Why the floor still ships OFF.** Swept 0.00→0.84 at the shipped geometry. Apr–Jun picked
0.72 (+$3,600 vs +$3,545 with no floor, +$55 on 13 fewer trades); Jul–Sep gave that same
0.72 **+$1,640 vs +$1,672 with no floor** — worse. The out-of-sample best was 0.56, a
different value. A $55 in-sample gain that inverts out-of-sample is noise, so the
parameter exists and stays off.

**Ceiling re-confirmed at 1.00.** Full sweep 0.50→1.05 × WickMode {0,2}, both halves:
1.00 is an interior optimum, not a bound — 1.05 is worse in Apr–Jun, tightening is
monotonically worse from 0.95 down. Tightening to 0.85 (the value that would have
refused his named trade) costs **$2,473 of the $5,217**.

**Receipts:** `mt5/_tester_runs/axi/AXI_bt_051034.htm` · grids `vratio`, `vfloor` in
`monitor/strategy_lab/axi_sweep.py` · 24-pass sweeps per half, Axi XAUUSD.pro M5 model 4.

---

## VSISA v1.00 — a NEW EA, a new strategy (2026-09-09)

**Zee:** *"Since the diamond EA is not converging to a profitable strategy, we will
tonight write a new EA based on a new strategy... so i've written a new strategy called
LAWS_VSISA. Read and implement this strategy as an EA. then test this EA's performance
on the 5 minute chart."*

Volume Spread Imbalance Shift Analysis — Sajid Ahmed's method, from the 22-part course
Zee downloaded plus his own `LAWS_VSISA.md`. Rules inferred into `LAWS_VSISA_INFER.md`
(13 laws, each carrying the quote it came from). **Magic 88201. XAUUSD M5.** Entirely
separate from the Diamond — different magic, different timeframe, nothing shared.

### The engine, in four lines

1. a **cluster** of 2 same-direction bars carrying big volume — effort;
2. a **reaction** bar closing the other way — that names which side the volume was;
3. the reaction arrives on **LOW volume** — the resting orders are gone. *This is the
   trigger and it is a veto, not a score;*
4. enter on its close, stop past the extreme, target a multiple of the risk.

### Receipts — SEVEN MONTHS of real ticks, not one

M5 XAUUSD, model 4 (real ticks), delay 163 ms, 0.10 lots, deposit 50,000,
2026.02.02 → 2026.09.01. Tuned on August alone, then run on the six months it had
never seen.

| month | SHIP (H1 trend) | no trend filter |
|---|---|---|
| 2026-02 | −49.20 | −277.50 |
| 2026-03 | +207.80 | +355.60 |
| 2026-04 | +658.30 | +424.10 |
| 2026-05 | +156.20 | +366.60 |
| 2026-06 | +685.30 | +525.30 |
| 2026-07 | +638.60 | +432.90 |
| 2026-08 *(tuned)* | +830.60 | +1386.50 |
| **TOTAL** | **+3,127.60** | **+3,213.50** |
| trades | 120 | 244 |
| win rate | **34%** | 27% |
| profit factor | **1.94** | 1.42 |
| max equity DD | 0.95% | 0.99% |
| green months | 6/7 | 6/7 |

**Shipped WITH the H1 trend filter**: same money for HALF the trades and seven more
points of win rate at identical geometry — which is exactly the standing goal
(`project_goal_winrate`), and it is bought with fewer trades rather than wider stops.

August is the best month and August is where it was tuned, so some of that is fit. The
other six months are the honest number: **+$2,297 across months it never saw, five of
six green.**

### Laws that EARNED their place

| law | receipt |
|---|---|
| LAW 3 — reaction must be quiet | leaving it unconstrained (LowVolPct>1.1) scores **+$621** against **+$1,024** constrained, same August window |
| LAW 3 — quiet vs the CLIMAX, not vs normal | `QuietRef=0` swept every top row; `QuietRef=1` appears once, at rank 22, on 2 trades |
| LAW 8 — breakeven at 1R | +$1,386.50 with, +$1,212.70 without, otherwise identical |
| LAW 8 — target 2.5R | interior optimum; 1.5R and 3.0R both worse |
| LAW 9 — trade with the H1 trend | the whole reason the ship config exists — see the table |
| LAW 4 — 2-bar cluster | beats 3-bar on net in every sweep (3-bar wins on PF with a third the trades) |

### Laws that were TESTED and did NOT survive

| law | receipt |
|---|---|
| LAW 13 — the fake break | `FakeBreak=false` in **all 30 top rows** of a 336-pass August sweep. This is Zee's own tier-3 "strongest" case, and it does not hold up on M5 gold |
| LAW 6 — the wick | `WickMode=0` beats both "require" and "override" in every paired comparison |
| the no-supply test (confirmed entry) | **+$233 best, most variants negative**, against +$3,213 for the aggressive entry |

**The no-supply test needed fixing before it could be judged.** The first cut compared
the test bar's volume to the REACTION bar — which LAW 3 has already forced to be quiet —
so it asked the test to be quieter than something already quiet, and fired **zero trades
in 48 passes across seven months**. That was my arithmetic, not his rule. Re-measured
against the climax like every other "small volume" in the course, it fires properly and
then genuinely loses. Only the second number is evidence.

### What "volume" actually is here — MEASURED, not assumed

```
VOLUME SOURCE iRealVolume 0 reads, tick-count fallback 8,006,496 reads
             — EVERY judgement used TICK COUNT
```

The broker publishes no exchange volume for gold CFD, so every VSISA decision is made on
**tick count**. Defensible — it is roughly what the teacher reads on his own retail
terminal — but it is a THIRD number alongside broker real volume and the OANDA feed the
Diamond uses, and the EA prints the split at the end of every run so it can never
quietly change underneath us.

### Also tested, also rejected (seven months each)

| variant | receipt |
|---|---|
| LAW 7 — the anomaly (tiny spread, huge volume) | every `Anomaly=true` pass collapsed to 1-4 trades; best +$305, several at zero |
| engulfing reaction required | +$640 best against +$3,376 |
| rising cluster volume required | +$580 best |
| `QuietRef=1` (quiet vs the market, not vs the climax) | one appearance at rank 22, on 2 trades |

### The lookback is a PLATEAU, which is the reassuring part

Seven months, net by `InpVolLookback`: 30 -> $3,284 · 45 -> $3,385 · **60 -> $3,377** ·
75 -> $3,050 · 90 -> $3,196 · **100 -> $3,128** · 105 -> $2,948.

No spike anywhere — a broad flat region, which is what a real effect looks like and what
a curve fit does not. Adjacent settings swing ~$300, so the $249 by which 60 beats 100
is noise. **Shipped at 100** because with net indistinguishable the standing goal decides:
34% WR / PF 1.94 / 120 trades against 60's 31% / 1.83 / 153, at identical geometry.
Lookback 60 is validated too (+$3,376.50 · 153 trades · 31% · 6/7 green) and is a
one-line change if he wants the trades instead.

### A tester trap worth remembering

An "run it on the compiled defaults" validation returned **0 trades**, and its REACH line
quoted thresholds that had been replaced two hours earlier. **An empty `[TesterInputs]`
section does NOT fall back to the EA's compiled defaults — MT5 reuses the inputs it
cached for that EA from a previous run.** `vsisa_court.run_arm()` now refuses to launch
with an empty input list rather than produce a confident wrong answer.

### Honest cautions

- **February loses** (−$49.20) and it is the earliest month. Not fatal, but the strategy
  is not all-weather.
- **27–34% win rate is by design** (2.5R target), not a defect — but it means long
  losing streaks are normal and must not be read as a broken EA.
- **His 2–3 pip stops did not transfer.** Those are FX-major pips; the ship uses a 30-pt
  buffer with a 60-pt floor because a stop narrower than gold's spread is a guaranteed
  loss on entry. Results were insensitive to this (10/30/50/70 all close), which is
  reassuring.
- **The tester's spread is the broker's recorded spread**, and 120 trades over seven
  months is roughly 17 a month. Live behaviour is the only thing that settles it.

### Files

`mt5/VSISA.mq5` · `LAWS_VSISA_INFER.md` · `monitor/_vsisa_transcripts/` ·
`monitor/strategy_lab/vsisa_court.py` (per-day + funnel) ·
`vsisa_sweep.py` (parallel variant search) · `vsisa_validate.py` (month by month)
