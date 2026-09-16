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

## VSISA v1.21-1.23 — SHIPPED: LAW 14, the FADE (2026-09-17)

**Who ordered it.** Zee took a trade the EA refused — 16 Sep 22:33 broker, **+$858 on 1
lot** — and described how he read it: *"i filtered out the red candles: saw that reds are
ultra highs .. then tried to find a green reaction candle.. i saw that the green's had
reduced alot from one green to another green. so it meant that now buyers have to apply
less force to bring the price up.."* Then: **"ok ship it"**.

**Why the EA could not see it.** Two differences, and neither is a threshold:
1. **His background is not adjacent.** He reads the reds of the whole recent leg. At his
   entry there was no red run at all — the bar before was green. Gaps up to 3 contrary bars
   still fire nothing that night.
2. **His comparison is GREEN-TO-GREEN.** The EA asks "is the reaction quieter than the reds
   behind it". He asks "is each green quieter than the LAST GREEN" — the Base Case forwards.

**What shipped.** `InpFadeMode` = 1 — a SECOND entry path, tried only after the ordinary
setup refuses, so it can only ever ADD trades. `InpFadePct` 0.60, `InpFadeLook` 4,
`InpFadeBigPct` 0.80.

**Two things had to be learned first, and both are in the source.**

*His eye did more than his words.* Built exactly as described it fired **1,455 to 5,558
times** at 0.03–1.46 net per $1 of drawdown against the shipped 9.16. He was also looking at
**a low that had just been made** — applying LAW 13's sweep to this path doubled every
variant.

*It had to survive the spike test.* 0.60/look4 first appeared between neighbours of 5.39 and
6.40 — the shape refused all week. The fine grid made it a RIDGE:

| fade ≤ | look3 | look4 | look5 |
|---|---|---|---|
| 0.55 | 5.19 | 6.58 | 5.62 |
| **0.60** | 6.26 | **15.75** | **12.99** |
| 0.65 | 6.00 | 9.58 | 8.36 |

**Ship-verified:** 121 trades · 51% WR · **NET +$10,400.18** · maxDD $661 (6.6%) · streak 4 ·
ratio 15.75 — matching the pre-ship measurement exactly.

| | v1.20 | **v1.23** |
|---|---|---|
| net, Jan–Sep | +$8,019 | **+$10,400** |
| trades | 66 | **121** |
| win rate | 59% | 51% |
| max drawdown | $875 (8.8%) | **$661 (6.6%)** |
| worst streak | 5 | **4** |
| net per $1 DD | 9.16 | **15.75** |
| halves | 2.06 / 11.15 | **4.16 / 12.43** |

**9 of 9 months green.** Jan +$664, Feb +$598, Mar +$84, Apr +$66, May +$2,754, Jun +$1,422,
Jul +$3,496, Aug +$1,163, Sep +$306.

This answers the frequency question I told him on 2026-09-17 I could not solve — and it came
from him watching a chart and taking the trade, not from any parameter search.

**ZEE MUST REATTACH.** Banner must read `v1.23`.

---

## VSISA v1.20 — SHIPPED: the night's four answers (2026-09-17)

**Who ordered it.** Zee, going to bed: *"i want you to through the night experiment
thoroughly with the following: wicks .. finding out if we're taking all possible setups ..
solving the no-supply candle's mystery .. tuning this strategy further .. increasing the
frequency of trading .. keep working in a loop till you find optimal values."*

**Four defaults moved. Every one is better in BOTH walk-forward halves.**

| input | was | now | why |
|---|---|---|---|
| `InpWickMode` | 2 | **0** | the "a LOUD reaction is fine if it has a wick" exception was losing money |
| `InpSwingMin` | 10 | **5** | a shorter yardstick grades the volume better |
| `InpRatchetStep` | 1.0 | **8.0** | NOT a tighter trail — ONE LOCK AT 2R AND HANDS OFF |
| `InpTargetR` | 5.0 | **10.0** | the target is decorative; raising it stops the ratchet colliding with it |

| | v1.19 | **v1.20** |
|---|---|---|
| net, Jan–Sep | +$8,019 | **+$8,979** |
| trades | 66 | 54 |
| win rate | 59% | **65%** |
| max drawdown | $875 (8.8%) | **$558 (5.6%)** |
| worst streak | 5 | **3** |
| net per $1 DD | 9.16 | **16.09** |
| walk-forward halves | 2.06 / 11.15 | **4.79 / 11.72** |

**Ship-verified:** 54 trades · 65% WR · NET **+$8,979.32** · maxDD $558 · streak 3 —
matching the pre-ship measurement exactly. **8 of 9 months green** (only February red, −$135).

### The two discoveries behind it

**1. The target has been decorative since the ratchet shipped.** Over the full window ALL
trades close at the STOP and not one reaches the target — average stop-exit **+$136.68**, so
most stops are now taken in profit. The ratchet locked at 5R exactly where the 5R target sat,
so the stop always arrived first. That is why `InpTargetR` 4/6/7 returned byte-identical
numbers. "65% win rate" means 65% got past 2R and ratcheted into profit, NOT that they
reached a target.

**2. The right rule is one lock, not a trail.** Step 8.0 and step 20.0 return identical
results, which proves no second rung is ever reached. Trailing beyond the first rung was
cutting winners; locking 2R once and leaving it alone is worth ratio 14.85 against 14.36.

### Refuted the same night — recorded so they are not re-tested

- **The no-supply test, third geometry.** Every variant far worse (best 1.24 against base
  13.25, several negative). Written three ways including his own diagram-11 sequence.
- **Frequency by loosening the volume gate.** 62 trades can become 170, and the first half
  goes NEGATIVE (−0.50) while drawdown quadruples. The big-volume requirement is load-bearing.

### The funnel, counted

`dir 75,487 | not loud 21,895 of 24,498 (89%) | fake 2,342 | trend 36 | FIRED 62`

**ZEE MUST REATTACH — and note the live chart is still on v1.17**, which he attached before
the camel filter shipped. Banner must read `v1.20`, `trendTF 30`, `wick 0`, `0.28 lots`.

---

## VSISA v1.19 — SHIPPED: camel humps on M30 (2026-09-16)

**Who ordered it.** Zee: *"ok ship M30"*.

**What changed.** `InpTrendTF` 0 -> **30**, `InpTrendMode` 0 -> **1** (camel humps). No
logic touched — both shipped as options in v1.18.

**Ship verification.** Compiled v1.19, Jan 1 → Sep 16, Axi real ticks M5, 0.28 lots:
**66 trades · 39 wins (59%) · NET +$8,018.64 · maxDD $875 (8.8% of $10k) · worst streak 5**
— matching the pre-ship measurement exactly.

**Against what it replaces:**

| | v1.17 (no trend filter) | **v1.19 (camel M30)** |
|---|---|---|
| net, Jan–Sep | +$7,918 | **+$8,019** |
| win rate | 51% | **59%** |
| worst streak | 7 | **5** |
| max drawdown | $1,232 (12.3%) | **$875 (8.8%)** |
| trades | 94 | 66 |

More money, +8 points of win rate, a shorter streak, and **29% less drawdown on 28 fewer
trades**. It is the only change this year to improve all four in BOTH walk-forward halves.

**AND IT PUTS THE ACCOUNT BACK INSIDE A 10% FUNDED RULE.** v1.17 sat at 12.3% and breached;
this is **8.8%**. The 0.28 lot was chosen to match v1.15's drawdown, and the trend filter has
now given 3.5 points of that back for free.

**Month by month at 0.28 lots** — and the four-month opening slump is much shallower than the
filter-less build's −$634:

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|---|---|---|
| +$619 | −$217 | +$226 | +$83 | +$2,284 | +$1,692 | +$2,713 | +$309 | +$392 |

**8 of 9 months green**, and March — 0-for-7 in the filter-less build — is now **2-3 and
positive**. That is the filter doing exactly what it should: standing aside when structure
says the move is against us.

**Why M30 over H1.** Full window they are tied ($8,019 vs $8,096, under 1%). They separate on
the halves and M30 owns the harder one: 2.06 against 1.27 in Jan–mid-May, 50% win rate
against 43%. That half holds March. H1 is better in the kinder half and is the timeframe the
teacher names, so its case was never numeric. Zee took the conservative read.

**Current shipped configuration (v1.19):**
`M5 · InpLots 0.28 · InpMaxOpen 2 · InpTargetR 5.0 · InpStopRef 0 · InpSlBufPts 120 ·
InpMinSlPts 60 · InpMaxSlPts 900 · InpBreakEvenR 0 · InpRatchetStart 2.0 / Step 1.0 ·
InpLowVolPct 1.00 · InpWickMode 2 · InpFakeBreak TRUE / InpSweepLook 30 ·
InpTrendTF 30 / InpTrendMode 1 / InpCamelPivot 2 / InpCamelLook 120`

**ZEE MUST REATTACH.** Banner must read `v1.19` and `trendTF 30`.

---

## VSISA v1.18 — THE CAMEL HUMPS. Zee's own trend reading, and it wins (2026-09-16)

**Who ordered it.** Zee: *"test if we check trend first what happens then? test all
timeframes for the trend and their impact on us ... because i heard the teacher say
something about trading with the trend ... also TEST the trend detector (camel humps) from
our previous UHV strategy onto this strategy VSISA as a trend checker -- maybe it works?"*

**What shipped (as options, default OFF).** `InpTrendMode` — 0 = the slope the EA already
had, 1 = **CAMEL HUMPS**, his own definition from `LAWS.md`: *"we identify trend by drawing
camel humps .. we call it an uptrend if we're breaking above previous highs. and forming new
higher lows."* Fractal pivots, K bars clear each side, then HH+HL for up, LH+LL for down,
anything mixed is a RANGE and gates nothing. Ported from `trend_eyes.py`, the UHV compass.
`InpTrendTF` also widened from {M15, M30, H1, else H4} to the full ladder M1…D1.

**Full window, Jan 1 → Sep 16, v1.17 geometry at 0.28 lots:**

| trend filter | net | trades | WR | maxDD | streak | net per $1 DD |
|---|---|---|---|---|---|---|
| **OFF (shipped)** | +$7,918 | 94 | 51% | $1,232 | 7 | 6.43 |
| slope M15 | +$680 | 23 | 43% | $880 | 5 | 0.77 |
| slope M30 | +$3,212 | 40 | 52% | $975 | 4 | 3.29 |
| slope H1 | +$5,942 | 50 | 58% | $679 | 3 | 8.76 |
| slope H4 | +$6,299 | 50 | 56% | $834 | 3 | 7.55 |
| camel M15 | +$4,875 | 64 | 50% | $879 | 4 | 5.55 |
| **camel M30** | **+$8,019** | 66 | **59%** | $875 | 5 | **9.16** |
| **camel H1** | **+$8,096** | 67 | 57% | **$865** | 5 | **9.36** |
| camel H4 | +$6,842 | 73 | 52% | $819 | 4 | 8.35 |
| camel D1 | +$3,401 | 64 | 45% | $903 | 5 | 3.77 |

**His reading beats mine at every single timeframe.** Swing structure carries information the
20-bar slope does not, and the difference is not small: M30 goes 3.29 → 9.16, M15 0.77 → 5.55.

**CAMEL H1 DOMINATES THE SHIPPED CONFIG ON EVERY AXIS AT ONCE** — more money (+$8,096 vs
+$7,918), higher win rate (57% vs 51%), 30% LESS drawdown ($865 vs $1,232), shorter worst
streak (5 vs 7), on 27 fewer trades. And M30/H1/H4 are all strong, so it is a plateau rather
than a spike.

**Walk-forward — and this is the rare one that holds in BOTH halves:**

| | H1 (Jan–mid-May) | H2 (mid-May–Sep) |
|---|---|---|
| OFF | 42% WR · +$1,223 · DD $1,232 · streak 7 · **0.99** | 56% · +$6,695 · DD $819 · streak 4 · **8.17** |
| **camel H1** | 43% · +$1,101 · DD $865 · streak 5 · **1.27** | **64%** · +$6,995 · DD $558 · streak 3 · **12.53** |
| camel M30 | **50%** · +$1,798 · DD $875 · streak 5 · **2.06** | **65%** · +$6,220 · DD $558 · streak 3 · **11.15** |
| camel H4 | 52% · +$2,195 · DD $612 · streak 3 · 3.59 | 52% · +$4,647 · DD $819 · streak 4 · 5.67 |

Camel H1 and camel M30 improve win rate, drawdown, streak AND risk-adjusted return in BOTH
halves. Nothing else tested this year has done that — every other candidate was strong in
one half and flat or negative in the other.

**The teacher's own words back H1 specifically:** *"That setup comes on H1, and we take entry
on M5... take the trade in trend direction. Do not catch the top."*

**Recommended: `InpTrendTF 60`, `InpTrendMode 1`. Not shipped pending Zee's call.**

---

## VSISA v1.17 — SHIPPED: the ratchet ON at 2.0R, and 0.28 lots (2026-09-16)

**Who ordered it.** Zee: *"ok let's go for: ratchet 2.0/1.0, 0.28 lots +$7,918 51% 7 $1,232"*.

**What changed.** `InpRatchetStart` 0 -> **2.00**, `InpRatchetStep` **1.00**, `InpLots`
0.15 -> **0.28**. No logic touched — the ratchet itself shipped (off) in v1.16.

**Ship verification.** Compiled v1.17, Jan 1 -> Sep 16, Axi real ticks M5:
**94 trades · 48 wins (51%) · NET +$7,918.12 · maxDD $1,232 · worst streak 7** — every
figure matching the pre-ship measurement exactly.

**Against what it replaces:**

| | v1.15 (no ratchet, 0.15) | **v1.17 (ratchet 2.0, 0.28)** |
|---|---|---|
| net, Jan–Sep | +$5,571 | **+$7,918** |
| win rate | 30% | **51%** |
| worst losing streak | 13 | **7** |
| max drawdown | $1,232 | $1,232 |

Same risk, +42% money, +21 points of win rate, half the streak.

**THE TWO CHANGES ARE ONE CHANGE AND MUST NOT BE SEPARATED.** The ratchet cut drawdown from
$1,232 to $660 at 0.15 lots; the lot rise spends exactly that headroom back. Turning the
ratchet OFF while leaving 0.28 lots would roughly DOUBLE drawdown to ~$2,300. This is
written into the source beside both defaults.

**THE FUNDED-ACCOUNT WARNING, unchanged and now inherited.** $1,232 is **12.3% of $10,000**
and would breach a 10% rule. Zee chose it knowing that — it is the drawdown he was already
carrying at v1.15. For a 10% limit the size is **~0.22 lots** (about $968).

**The caveat from v1.16 still stands.** Walk-forward, the win-rate and streak gains hold in
BOTH halves (27%→42% and 31%→56%; streak 13→7 and 9→4), but risk-adjusted return is 0.99
against 1.14 in the first half and 8.17 against 4.73 in the second. Strongly better in one
half, marginally worse in the other.

**Current shipped configuration (v1.17):**
`M5 · InpLots 0.28 · InpMaxOpen 2 · InpTargetR 5.0 · InpStopRef 0 · InpSlBufPts 120 ·
InpMinSlPts 60 · InpMaxSlPts 900 · InpBreakEvenR 0 · InpRatchetStart 2.0 / Step 1.0 ·
InpLowVolPct 1.00 · InpWickMode 2 · InpFakeBreak TRUE / InpSweepLook 30 · InpTrendTF 0`

**ZEE MUST REATTACH.** Banner must read `v1.17` and `0.28 lots x1`.

---

## VSISA v1.16 — THE RATCHET. Zee's ladder, and it beats the shipped build (2026-09-16)

**Who ordered it.** Zee, after seeing the 11 Sep trade peak at 4.77R and still lose:
*"if 0.75R is reached we breakeven to 0.75R / if 1R is reached we breakeven to 1R / if 2R
is reached we breakeven to 2R / if XR is reached we breakeven to XR"*.

**What it is, and why it is NOT InpBreakEvenR.** The old breakeven moves the stop to ENTRY
and then stops caring, so a trade that reaches 4R and reverses still closes at zero. This
CLIMBS: reach 2R and 2R is banked whatever happens next. `InpRatchetStart` (first rung),
`InpRatchetStep` (spacing). **Default OFF.**

**What prompted it.** Of the 65 losing trades Jan–Sep, four ran past 4R before being stopped
for a full loss (20 May 4.80R, 11 Sep 4.77R, 3 Jun 4.61R, 17 Mar 4.02R) and three more
passed 3R. Nothing protected any of it.

**The ladder matters enormously — and his literal 0.75R start is the wrong rung:**

| ratchet | net | WR | avg win | maxDD | streak | net per $1 DD |
|---|---|---|---|---|---|---|
| **OFF (shipped)** | +$5,571 | 30% | +$420 | $1,232 | 13 | 4.52 |
| start 0.75 step 0.25 | +$1,356 | **67%** | +$69 | $558 | 4 | 2.43 |
| start 1.00 step 1.00 | +$1,819 | 61% | +$93 | $403 | 4 | 4.51 |
| **start 2.00 step 1.00** | **+$4,241** | **51%** | +$178 | **$660** | **7** | **6.42** |
| start 3.00 step 1.00 | +$3,598 | 38% | +$252 | $759 | 8 | 4.74 |

Locking from 0.75R reaches 67% win rate and earns a quarter of the money — it banks 0.75R
on trades that were going to 5R. Starting at 2.0R is the peak on every risk-adjusted measure.

**AT MATCHED DRAWDOWN IT DOMINATES THE SHIPPED BUILD.** Sized to the same $1,232:

| | net | WR | worst streak | maxDD |
|---|---|---|---|---|
| shipped, no ratchet, 0.15 lots | +$5,571 | 30% | 13 | $1,232 |
| **ratchet 2.0/1.0, 0.28 lots** | **+$7,918** | **51%** | **7** | $1,232 |

**+42% more money, 21 more points of win rate, and half the losing streak, for identical
risk.** Nothing else tested this year has improved all three at once.

**Walk-forward, 0.15 lots, Jan–mid-May vs mid-May–Sep:**

| | H1 | H2 |
|---|---|---|
| OFF | 27% WR · +$1,407 · streak 13 · ratio 1.14 | 31% WR · +$4,164 · streak 9 · ratio 4.73 |
| ratchet 2.0 | 42% WR · +$655 · streak 7 · ratio 0.99 | 56% WR · +$3,586 · streak 4 · ratio 8.17 |

The win-rate and streak gains hold in BOTH halves (27→42 and 31→56; 13→7 and 9→4). The
risk-adjusted return is a slight loss in H1 (0.99 vs 1.14) and a large gain in H2. So it is
not universally dominant — but the two things Zee actually asked for are consistent.

**Not shipped pending his call.** Recommended: `InpRatchetStart 2.0`, `InpRatchetStep 1.0`.

---

## VSISA v1.15 — SHIPPED: 0.15 lots (2026-09-16)

**Who ordered it.** Zee: *"ok 0.15 lot adjustment"*.

**What changed.** `InpLots` **0.10 -> 0.15**. Nothing else.

**This spends headroom v1.14 created; it does not add new risk.** Turning on the fake break
cut drawdown from $905 to $586 while halving the income. Raising the lot takes some of that
income back inside the same 10% breach line. MEASURED, not extrapolated:

| lots | net | trades | WR | maxDD | % of $10k | worst streak | worst trade |
|---|---|---|---|---|---|---|---|
| 0.10 | +$3,991 | 78 | 33% | $586 | 5.9% | 9 | −$93 |
| **0.15 — SHIPPED** | **+$5,986** | 78 | 33% | **$879** | **8.8%** | 9 | −$139 |
| 0.17 | +$6,784 | 78 | 33% | $997 | 10.0% | 9 | −$158 |

**0.17 is the hard ceiling on $10k** — exactly 10.0%, no margin at all. 0.15 leaves 1.2
points of room, which is the whole reason to stop there rather than squeeze.

Drawdown scales linearly with size and nothing in the risk machinery changes that: v1.12
tested a tighter stop, a concurrency cap, a risk cap and a daily loss limit, and none of
them moved it. The 9-loss worst streak is unchanged by lot size; at 0.15 it costs about
$780 to sit through.

**Where the account stands now.** Against the shipped v1.13 (no fake break, 0.10 lots,
+$8,196 at 9.0% DD), this configuration earns **$2,210 less** for **33% win rate instead of
25%** and a **9-loss streak instead of 15**. That is the trade Zee chose, made twice — once
with the filter and once with the lot — and it is recorded here so it is never mistaken for
an optimisation.

**Current shipped configuration (v1.15):**
`M5 · InpLots 0.15 · InpMaxOpen 2 · InpTargetR 5.0 · InpStopRef 0 · InpSlBufPts 120 ·
InpMinSlPts 60 · InpMaxSlPts 900 · InpBreakEvenR 0 · InpLowVolPct 1.00 · InpWickMode 2 ·
InpFakeBreak TRUE / InpSweepLook 30 · InpTrendTF 0`

**ZEE MUST REATTACH.** Banner must read `v1.15`, `fake 1`, `0.15 lots x1`.

---

## VSISA v1.14 — SHIPPED: the fake break is ON (2026-09-16)

**Who ordered it.** Zee: *"activate turn on InpFakeBreak with InpSweepLook=30."*

**What changed.** `InpFakeBreak` **false -> true**, `InpSweepLook` stays 30. No logic touched.

**What it is.** His own tier-3 case, written in `LAWS_VSISA.md` from the start: *"case 3.
2 bar setup + fake break of this support + forms a wick + closing again inside support ..
(strongest)"*. The setup must SWEEP a recent extreme and the reaction must close back inside
it. Built early, tested OFF on the OLD build, and never re-examined after the stop and swing
corrections — it took an external analysis naming `InpFakeBreak` to send me back to it.

**It is the best filter found on this project.** Walk-forward, per trade:

| sweep | Apr–Jun | Jul–Sep |
|---|---|---|
| off | 25% WR · $23.66 | 24% WR · $28.21 |
| 20 bars | 33% · $45.40 | 31% · $51.46 |
| **30 bars — SHIPPED** | **34% · $48.76** | **32% · $54.50** |
| 50 bars | 38% · $57.65 | 31% · $59.39 |

Win rate and per-trade value both roughly double, in BOTH halves, at EVERY sweep length.
That plateau is the signature that separates it from everything rejected this year — the cap
bar, the volume floor, close location, effort-per-range and the quiet retracement were each
good at ONE setting and worthless at its neighbours.

**What it buys:** win rate **25% -> 33%**, worst losing streak **15 -> 9**, drawdown
**$905 -> $586** (5.9% of a $10k funded account). Zee turned it on for the streak.

**What it costs, and it is NOT free:** it refuses 75% of setups (318 -> 78), so net falls
**$8,196 -> $3,998** at 0.10 lots. Per unit of drawdown it is WORSE than off — 6.81 against
9.06 — meaning a bigger lot with the filter off earns more for the same risk. This is a
deliberate trade of income for bearability, recorded in the source so no future session
reads it as an upgrade.

**Ship verification.** Compiled v1.14, Apr 1 → Sep 15, Axi real ticks M5:
**26W/52L, NET $3,998.63** — matching the pre-ship measurement exactly. Report
`AXI_bt_032102.htm`.

**Current shipped configuration (v1.14):**
`M5 · InpLots 0.10 · InpMaxOpen 2 · InpTargetR 5.0 · InpStopRef 0 · InpSlBufPts 120 ·
InpMinSlPts 60 · InpMaxSlPts 900 · InpBreakEvenR 0 · InpLowVolPct 1.00 · InpWickMode 2 ·
InpFakeBreak TRUE / InpSweepLook 30 · InpTrendTF 0` — all other experimental inputs OFF.

**ZEE MUST REATTACH.** The banner must read `v1.14` and `fake 1`.

---

## VSISA v1.13 — SHIPPED: InpMaxOpen 10 -> 2 (2026-09-16)

**Who ordered it.** Zee: *"ok ship InpMaxOpen=2"*.

**What changed.** `InpMaxOpen` default **10 -> 2**. Nothing else; no logic touched.

**Shipped on RISK, not on return — and the distinction is the point.** Walk-forward:

| | Apr–Jun | Jul–Sep |
|---|---|---|
| maxOpen=10 | +$4,004 · DD $898 | +$4,004 · DD $950 |
| **maxOpen=2** | +$4,004 · DD $898 — **identical, the cap never binds** | +$4,192 · DD $905 |

One half is untouched and the other moves on FOUR trades. +$188 is not a result worth
defending and is not why this shipped. What is solid: the cap costs nothing measurable in
either half while cutting worst-case concurrent exposure from ~$450 to ~$90 — and on a
funded account with a hard breach line, a free reduction in tail exposure is worth taking.

Measured, the EA rarely holds more than three positions anyway — maxOpen 10, 5 and 3 return
BYTE-IDENTICAL results over Apr–Sep. This binds only in the crowded moments, which are
exactly the moments a breach line cares about.

**Ship verification.** The compiled v1.13 binary, Apr 1 → Sep 15, Axi real ticks M5:
**79W/239L, NET $8,197.60** — four fewer trades than v1.05's 79W/243L and $189 more, exactly
the Jul–Sep difference measured before shipping.

**Current shipped configuration (v1.13):**
`InpLots 0.10 · InpMaxOpen 2 · M5 · InpTargetMode 0 · InpTargetR 5.0 · InpStopRef 0 ·
InpSlBufPts 120 · InpMinSlPts 60 · InpMaxSlPts 900 · InpBreakEvenR 0 · InpLowVolPct 1.00 ·
InpWickMode 2 · InpTrendTF 0` — every experimental input from v1.01–v1.12 defaults OFF.

**ZEE MUST REATTACH** — MT5 does not hot-reload inputs. The banner must read `v1.13`.

---

## VSISA v1.12 — can the drawdown at 0.20 lots be cut? No. (2026-09-16)

**Who ordered it.** Zee: *"if we use flat 0.2 .. can't we reduce the drawdown from 19% by
setting a tighter stop? or something else.. check?"*

**What shipped.** `InpDayLossStop` — stop opening new trades once the day's realised loss on
this magic passes a line, the standard funded-account tool. **Default OFF.**

**Every lever tested at 0.20 lots. Baseline +$16,017, DD $1,901 = 19.0%, ratio 8.43.**

| lever | net | maxDD | % of $10k | net per $1 DD |
|---|---|---|---|---|
| **baseline** | +$16,017 | $1,901 | 19.0% | **8.43** |
| maxOpen 5 | +$16,017 | $1,901 | 19.0% | 8.43 |
| maxOpen 3 | +$16,017 | $1,901 | 19.0% | 8.43 |
| maxOpen 2 | +$16,392 | $1,810 | 18.1% | 9.06 |
| maxOpen 1 | +$13,532 | $1,673 | 16.7% | 8.09 |
| maxSlPts 600 | +$5,974 | $2,125 | 21.3% | 2.81 |
| **maxSlPts 450** | +$3,830 | **$721** | **7.2%** | **5.31** |
| daily stop −$500 | +$16,017 | $1,901 | 19.0% | 8.43 |
| daily stop −$400 | +$13,980 | $1,856 | 18.6% | 7.53 |
| daily stop −$250 | +$13,941 | $1,685 | 16.8% | 8.28 |

**Why each one fails:**

- **A tighter stop is not a lever at all.** At a fixed 5R the target moves in with the stop,
  so everything scales together — arithmetically identical to trading smaller lots, minus the
  extra stop-outs.
- **Concurrency is not the cause.** maxOpen 10, 5 and 3 return IDENTICAL numbers: the EA
  rarely holds more than three positions. maxOpen 2 is the one mild win (ratio 9.06).
- **The risk cap reaches the target and destroys the edge.** maxSlPts 450 gets to 7.2% but
  at ratio 5.31 — far worse than simply trading 0.10 lots, which gives 9.5% at ratio 8.43.
- **The daily stop CANNOT WORK HERE, and the reason is structural.** A −$500 limit returns
  results byte-identical to OFF even though the worst day is −$635. At a 5R target positions
  live for days, so most of a day's damage comes from trades opened on PREVIOUS days, and a
  rule that only blocks new entries cannot touch them.

**THE FINDING: the drawdown is the losing streak, and the streak is the 25% win rate.**
The worst drawdown is $1,587 over five sessions (22–29 July). 15 consecutive losses at
~$113 each IS $1,695. Nothing in the trade-selection or risk machinery moves it, because it
is not a defect — it is what a 25%-win-rate, 4.9:1-payoff system looks like.

Net per $1 of drawdown sits at **8.43 across every lot size and nearly every variant**. That
constant is the strategy; drawdown is simply lot size times it.

**So the practical answer is capital, not settings.** 0.20 lots needs a **$20k** funded
account to sit inside a 10% rule (DD $1,901 = 9.5% of $20k). On $10k the ceiling is
**0.10-0.11 lots**. Defaults unchanged.

---

## VSISA v1.11 — sizing by reaction spread, and why the "quality signal" was not one (2026-09-16)

**Who ordered it.** Zee: *"yes let's let it do position sizing. test"* — after v1.10 found
that wide-reaction setups were worth more per trade in both walk-forward halves.

**What shipped.** `InpSizeBySpread` with two thresholds and three multipliers
(`InpSizeT1/T2`, `InpSizeM0/M1/M2`), so risk can be added to the graded setups OR taken off
the ordinary ones. **Default OFF.**

**Raw profit rises a lot.** Apr 1 -> Sep 15, 1:5 geometry, commission taken from the report
itself (it scales with lots — $193.96 against the flat $144.90, so a flat $0.45/trade
assumption would have flattered these):

| config | net | maxDD | % of $10k |
|---|---|---|---|
| flat 0.10 (shipped) | +$8,008 | $950 | 9.5% |
| sized up 1 / 1.5 / 2.0 | +$11,350 | $1,377 | 13.8% |
| sized up 1 / 2.0 / 3.0 | +$14,693 | $1,804 | 18.0% |
| sized down 0.6 / 1 / 1.5 | +$7,710 | $932 | 9.3% |

**But it is pure leverage, and it is DOMINATED by simply trading a bigger flat lot:**

| config | net | maxDD | **net per $1 of drawdown** |
|---|---|---|---|
| **flat 0.10** | +$8,008 | $950 | **8.43** |
| sized up 1/1.5/2.0 | +$11,350 | $1,377 | 8.24 |
| **flat 0.15** | +$12,011 | $1,426 | **8.42** |
| sized up 1/2.0/3.0 | +$14,693 | $1,804 | 8.14 |
| **flat 0.20** | +$16,017 | $1,901 | **8.43** |
| sized down 0.6/1/1.5 | +$7,710 | $932 | 8.27 |

Flat lots return 8.42-8.43 per $1 of drawdown at EVERY size. Every sized variant returns
LESS (8.14-8.27). Whatever drawdown budget is chosen, a flat lot at that budget earns more.

**THE MECHANISM — and it retracts v1.10's conclusion.** I called the wide reaction "the first
real quality signal of the session". It was not. Measured from the fire log:

| reaction | trades | median risk | WR |
|---|---|---|---|
| narrow (<1.20x) | 167 | **452 pts** | 25% |
| wide (>=1.20x) | 155 | **612 pts** | 25% |

**The wide-reaction trades risk 35% more per trade** — the stop hangs under the reaction
candle's low, so a wider candle mechanically puts the stop further away. Their win rate is
IDENTICAL (25% vs 25%). The higher $/trade was never better setup selection; it was a bigger
bet measured in dollars. Sizing up on them doubles down on the trades that already carry the
most risk, which is why drawdown outruns profit.

**This is the test that separates an edge from leverage**, and the spread grading failed it.
Default OFF; the shipped 1:5 config is untouched.

---

## VSISA v1.10 — the gapped campaign, the wide reaction, and entering ON the test (2026-09-16)

**Who ordered it.** Two ideas from Zee, 2026-09-16.

**(1) "what if the no-supply is itself a reaction candle?"** — a fair answer to my objection
that the test cannot filter the entry. `InpConfirmMode = 2` added: the quiet test bar IS the
reaction, so the trade is taken at ITS close, no confirming bar, no two bars of drift.

**(2) "the initial bullish/bearish candles need not be all consecutive to form the background
campaign (yes we call it that).. several bullish candles with a single red candle in between
them .. again followed by a larger spread low volume engulfing reaction candle"** —
`InpSetupGaps` (contrary bars tolerated inside the campaign; the bar touching the reaction
must still be ours and the run may not END on one) and `InpReactSpread` (reaction range >= x
the average). **All default OFF; regression at gaps=0/mode 0 reproduces 79W/243L, $8,010.00
exactly.**

**Results, 1:5 geometry, Apr 1 -> Sep 15. Shipped = 322 trades, 25% WR, +$8,010, $24.88/trade.**

| idea | trades | WR | net | $/trade |
|---|---|---|---|---|
| **(1) mode 2, test vol <=0.70** | 20 | 30% | +$491 | $24.53 |
| (1) mode 2, test vol <=1.10 | 97 | 20% | +$1,041 | $10.73 |
| **(2a) gaps=1** | 406 | 21% | +$6,304 | $15.53 |
| (2a) gaps=2 | 407 | 21% | +$5,270 | $12.95 |
| (2a) gaps=3 | 411 | 23% | +$7,204 | $17.53 |
| gaps=1 + spread 1.20x | 191 | 21% | +$3,526 | $18.46 |
| gaps=1 + spread 1.20x + engulf | 95 | 20% | +$1,236 | $13.01 |

**(1) and (2a) both fail.** Mode 2 is at best neutral per trade (and on 20 trades); the gapped
campaign is negative at every setting, with or without the wide reaction and the engulfing
requirement. Letting contrary bars into the campaign admits setups that are worth LESS per
trade than the consecutive ones, which is the opposite of the intent.

**(2b) THE WIDE REACTION IS THE FIRST REAL QUALITY SIGNAL OF THE SESSION.** Alone, with no
gaps, $/trade rises MONOTONICALLY with the reaction's spread — no spike anywhere:

| spread >= | trades | WR | $/trade |
|---|---|---|---|
| off | 322 | 25% | $24.88 |
| 1.00x | 214 | 24% | $24.77 |
| 1.20x | 154 | 25% | $28.33 |
| 1.40x | 103 | 25% | $36.23 |
| 1.60x | 62 | 26% | $37.50 |
| 1.80x | 39 | 28% | $45.83 |

**Walk-forward tempers it but does not kill it.** Per trade, Apr–Jun / Jul–Sep:
off $23.66 / $26.24 · **1.20x $26.12 / $30.61 (better in BOTH)** · 1.40x $50.92 / $22.90
(the monotonic slope above is partly Apr–Jun's 1.40x spike, which does NOT replicate) ·
1.60x $43.16 / $33.41 (better in both, on 26 and 36 trades).

So **spread >= 1.20x is a small, consistent grading: +10% and +17% per trade in the two
halves.** It is NOT shippable as a gate — it halves the trade count and takes net from
$8,010 to $4,363. Its honest use is POSITION SIZING, not filtering: the wide-reaction setups
are worth more per trade, consistently, in both halves. That is the first thing found all
session that grades setups rather than just thinning them, and it came from a clause Zee
wrote in passing.

**Defaults unchanged. The shipped 1:5 config is untouched.**

---

## VSISA v1.08/1.09 — LAW 10, the retracement re-entry, finally built (2026-09-16)

**Who ordered it.** Zee: *"if we miss such a breakout on low volume, then we wait for a
retracement to the same low where we initially got to when the red candle's happened giving
way to bullish move. that retracement low when it touches the low line of the missed setup
is also a valid setup .. infact sometimes it can touch several times (increasing the
strength of the upcoming move)"*

His document has said this from the beginning — *"Never chase the market. Always catch the
market on a retracement"* — and `VSISA_IMPLEMENTATION_AUDIT.md` has carried LAW 10 as **NOT
IMPLEMENTED** since day one. This is it.

**What shipped.** Every detected setup now leaves a LEVEL behind at the low the move turned
from (`MathMin(setup extreme, reaction low)`), and a later touch that CLOSES BACK above it is
its own entry, stop hung off the level. Touches accumulate, so `InpRetraceMin` can demand the
"several times" he describes. `InpRetrace` (off), `InpRetraceBars` 60, `InpRetraceTol` 30,
`InpRetraceMin` 1, `InpRetraceMax` 2, `InpRetraceQuiet` 0. **All default OFF.**

**v1.08, price-only — clearly NEGATIVE, and it taught the lesson.** Entering on the touch
alone, attributed trade-by-trade from the tester log over the same run:

| | trades | WR | $/trade |
|---|---|---|---|
| BASE setups | 222 | 22% | **+$13.35** |
| RETRACE entries | 409 | 14% | **−$9.46** |

409 trades is a real sample and the verdict is unambiguous. The fault was mine, not his:
every other entry in this EA is a VOLUME judgement, and I had built a price-only re-entry,
which discards the one thing the method reads.

**v1.09 adds `InpRetraceQuiet` — the retest must arrive on no supply.** Same question Law 3
asks of the reaction: if supply had really gone, the retest is cheap. That flips the sign:

| retest quiet <= | trades | net | vs shipped |
|---|---|---|---|
| **off (shipped)** | 322 | **+$8,010** | — |
| 0.90x | 650 | +$7,596 | −$414 |
| 0.65x | 412 | +$7,838 | −$172 |
| **0.55x** | 354 | **+$8,554** | **+$544** |
| 0.45x | 332 | +$7,932 | −$78 |
| 0.35x | 324 | +$7,969 | −$41 |

**NOT PROVEN, and it should not ship.** 0.55x is a single point with WORSE values on both
sides of it — 0.65x and 0.45x both lose to shipped. And the walk-forward is one-sided:
Apr–Jun **+$27** (flat) against Jul–Sep **+$517**. A rule that does nothing in half the data
and sits on an isolated spike in the other is the same shape as the cap bar and the volume
floor before it.

**What it is worth keeping.** The price-only version is REFUTED with a clean 409-trade
sample — that is a genuine negative result about the idea, not a shrug. The quiet version is
undecided on 32 extra trades, and would need more history to settle. LAW 10 is now built, so
the audit line changes from "not implemented" to "implemented, default off, unproven".

---

## VSISA v1.07 — the no-supply test as an ADDITION, not a gate (2026-09-15)

**Who ordered it.** Zee: *"maybe the no-supply test is not working as a gate, but its
something that acts as a strong confirmation right? so can we test it as an addition?
means test / check its variants etc as an added confirmation? does it help someway"*

**He was right about the diagnosis.** `InpConfirmMode` DELAYS the entry two bars, so it
replaces the trade rather than confirming it. But the test cannot filter the entry either —
at entry time the test bar does not exist yet. The only honest place for it is on a trade
ALREADY OPEN, which is his own law read forwards: *"if in case on no supply test it were big
volume it would mean sustained buying"* — for a buy, a loud bar closing back down says the
supply never left, so the setup has failed and there is no reason to wait for the stop.

**What shipped.** `InpTestExit` (0 = off) — close the position when a bar closing AGAINST it
arrives louder than this multiple of the recent average volume; `InpTestWindow` (bars after
entry to watch) and `InpTestAvgBars` (the average it is judged against). **Default OFF.**

**The receipts — no durable gain.** Shipped 1:5 geometry, Axi real ticks:

| variant | Apr–Jun | Jul–Sep | full-window net | WR |
|---|---|---|---|---|
| **OFF (shipped)** | +$4,022 | +$3,988 | **+$8,010** | 25% |
| 2.20x / 3 bars | +$4,022 | +$4,162 | +$8,184 | 25% |
| 1.50x / 1 bar | +$3,974 | +$4,151 | +$8,125 | 24% |
| 1.20x / 3 bars | +$2,225 | +$3,418 | +$5,643 | **32%** |

- **The best-net variant is a no-op.** 2.20x/3bars returns numbers IDENTICAL to OFF across
  Apr–Jun — it never fired once in that half. Its whole +$174 comes from a handful of
  instances in the other half. A rule that does nothing in half the sample is not evidence.
- **1.50x/1bar** is −$48 in one half and +$163 in the other. Noise.
- **1.20x/3bars DOES raise win rate consistently** — 33% and 31%, the most stable
  high-WR behaviour found all session (the earlier 1.25R+trend+floor collapsed 64% -> 49%).
  It costs $2,367 to do it.

**But that purchase is DOMINATED, which settles it.** Simply running 2.0R instead buys a
**43% win rate for +$5,502** — more money AND eleven more points of win rate than the
test-exit's 32% for +$5,643. If win rate is what is wanted, the target is the cheaper lever
and the no-supply test adds nothing on top of it.

**Default stays OFF.** The shipped 1:5 config is untouched.

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
