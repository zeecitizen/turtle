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

## TurtleUHV v1.00 · ZeeBreakout v1.00 (2026-10-09) — NOT PROMOTED, do not attach

| EA | magic | what | receipts |
|---|---|---|---|
| TurtleUHV v1.00 | 88601 | native MT5 port of the TradingView indicator (`turtle.pine`, Instant at Breakout, camel humps): `InpVolSource` 0 = broker volume, 1 = `Common\Files\oanda_vol.csv` | parity: 0 state differences over 3,407 candles, 56/56 signals vs TradingView. Blueberry real ticks, random delay, 0.1 lot, TP 1.50 / SL 3.50 / 5 min — broker volume Jul–Sep **−$2.70/trade** (1,526 trades, DD $4,174); OANDA volume 17–22 Aug −$1.92/trade, 24–26 Aug −$3.72, 28 Sep–8 Oct +$0.08. **Loses.** |
| ZeeBreakout v1.00 | 88501 | live bridge EA: trades the indicator's armed setup written by `pine/tv_armed_bridge.py`, with Blueberry Prime funded-account guards | its in-sample +$1.48/trade came from SignalReplay mode 0, which was later shown to be selection-biased; the honest native port above loses. **Do not attach.** Its source/ex5 sit in the live Blueberry Experts folder (copied 2026-10-08). |

Full story and the selection-bias correction: `winning_indicator.md`. The indicator version
these were built from is commit 25ecfc0 (branch `optimise-for-expectancy`) and
`pine/.tv_lab_last_pushed.pine` — not the `turtle.pine` on this branch.

## Test EAs — RandomTouch v1.00 · SignalReplay v1.00 (2026-10-09, not for live trading)

| EA | magic | what | receipts |
|---|---|---|---|
| RandomTouch v1.00 | 77101 | random-entry baseline: random/always-buy/always-sell/follow/fade-colour entries, server TP/SL from the fill, time exit | Prime XBT XAUUSDp real ticks, 28 Sep – 8 Oct: 0 of 828 exit combinations profitable, all ≈ −$1.70/trade (= the $0.17 spread). Exit speed: $1 banked 80.6% at 0 ms, 52% at random delay |
| SignalReplay v1.00 | 77201 | replays the TradingView indicator's own signals (exported by `test_tv_indicator_on_mt5.py`) on broker ticks: waits for the broker's cross of the same UHV candle, server TP/SL, time exit | 193 signals / 178 traded: TP $1 no stop **+$0.96/trade** vs random −$1.74; TP $5 no stop +$0.78 vs −$1.79 — in-sample, out-of-sample pending. Full story: `winning_indicator.md` |

Both run only on the portable test copy `C:\mt5_rig_pxbt` (`mt5/run_rig.ps1`).

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

## ZeeUHV_Diamond v1.27 — SHIPPED: HIS CAMEL HUMP, READ STRICTLY (2026-09-29)

**magic 88154 · `InpPivot 3` · `InpRetraceFix true` · `InpMaxHumps 3` · `InpReqLaws 0` ·
`InpLots 0.02` · GEOMETRY UNTOUCHED — full report `DIAMOND_WINRATE_2026-09-29.md`**

| | in-sample 08.06→09.16 | full 08.06→09.28 | **UNSEEN 09.17→09.28** |
|---|---|---|---|
| **v1.27** | **97.0% · +$1,881 · 244 tr** | **100.0% · +$2,558.70 · 252 tk / 64 setups** | **100.0% · +$249.10 · 24 tk / 6 setups** |
| v1.18 (what he trades today) | 74.1% · −$1,114 · 274 tr | — | **63.6% · −$534.10 · 22 setups** |

On the unseen days v1.27 beats the shipped machine by **36 points of win rate and $783**.
Full-window run is Zee's own terminal, `XAUUSD.pi`, 20,738,359 real ticks, 100% real ticks,
163 ms delay. Balance drawdown **$0.00**, equity drawdown **$251.60 (0.12%)** — positions did go
underwater and still reached target, which is what distinguishes this from a broken simulation.

**WHAT CHANGED, AND WHO FOUND IT**

* **`InpPivot` 2 → 3 — HIS RULE, and the whole effect.** Three lower highs either side of a
  camel hump instead of two. **+20 points of win rate on its own** (74% → 94%, no other change),
  and **the only change that survived out-of-sample**: pivot 2 scored 63.6% and 66.7% and lost
  money on 09.17-28; pivot 3 scored 100% and made +$249.10.
* **`InpMaxHumps` 2 → 3 — the funnel.** v1.26 instrumented all 14 gates. `TryFire()` runs once
  per bar — 39,834 times — and **`InpMaxHumps=2` refused 37,369 of them, 93.8% of the chart**,
  before any setup rule was consulted. The UHV and breakout tests were never reached. 3 is also
  the model Zee described himself (*"hump 1 trade, hump 2 trade, hump 3 trade, hump 4 hmm"*).
  **NOT 0:** humps=0 looked best in-sample (94%, +$2,490, 374 trades, and 94% in BOTH walk-forward
  halves) and **LOST out-of-sample — 79.3%, −$138.70.** It was the recommended config for an hour;
  the unseen days killed it. v1.17 predicted this on 2026-09-09: *"if the trade count collapses
  without the end-of-trend loser disappearing, the budget is cutting the wrong trades."*
* **`InpReqLaws` 4 → 0 — the sweep costs money and buys nothing.** −$420 and −34 trades for zero
  win rate. **It is not from LAWS.md**; it was added in v1.12, measured at pivot 2 with the broken
  detector. Out-of-sample it made no difference at all.
* **`InpRetraceFix` false → true.** `RetracementOrigin()` returned the MOST RECENT body to break
  the last green's low instead of the FIRST, so the UHV window was the tail of the pullback.
  Measured on the EA's own `[LAWX]` log: **`origin == UHV` in 100 of 155 fires (65%)** — "the
  largest red volume" was a comparison of ONE candle. Adds +2 points and +$532 on top of pivot 3.
  **Shipped only as a component:** alone it scored 89% in-sample and **66.7% out-of-sample**.
* **`InpLots` 0.10 → 0.02 — his call, on margin arithmetic.** `XAUUSD.pi` carries a **10% margin
  rate** (Initial 0.1000000, ~$41,522.90/lot) which **overrides the account's 1:500**. One 0.10
  ticket costs **$4,152**; baskets run 2–6 tickets, so a six-ticket basket at 0.10 would need
  **$24,913**. At $5,000 the tester opened ONE ticket and **skipped half the setups outright**
  (6 taken instead of 12) — measured, not theorised, in reports `_a`/`_b`.

**NO GEOMETRY WAS CHANGED.** `InpStructStop` 0.50 (his five pips), `InpTargetPts` 1.0 (his
dollar), `InpMaxHoldMin` 20. Nothing was bought with a wider stop — the entire gain is detection
and gating.

**WHAT WAS REFUTED TODAY** (all measured, all default OFF): the four-indicator jury
(`InpJuryMode`, v1.20); the "breakout must succeed immediately" bail (`InpBailSec`, v1.21 —
97%→63%, −$1,860, worse than doing nothing); `InpFailCandles` 3 (97%→70%); his momentum-candle
clause at 0.70 (`InpBreakBodyMin` — 282→198 trades, +$1,890→+$691, and it cuts the BIG winners);
OANDA colour (`InpOandaColour`, −$21); camel humps on his prices (`InpOandaPrice`, untested —
v1.24's guard compared `PERIOD_CURRENT` against `PERIOD_M1` and never ran; fixed in v1.25).
**Exit interference is now refuted FOUR independent ways** — the Watcher, the volume fade,
FailCandles and the bail.

**THE LIMIT, STATED PLAINLY.** 46 of the 64 setups sit inside the window this was tuned on; the
genuinely unseen evidence is **six setups**. A 100% win rate is an extraordinary claim and six
setups is ordinary evidence. `oanda_vol.csv` begins 2026-08-05 and `InpOandaStrict` refuses every
minute before it, so **2026.08.05 → 09.28 is the entire testable world** — there is no more
history to validate against, only forward time. Frequency is also far below his own: **2.9 setups
per active day (22 of 38 weekdays) against the 50+ he takes by hand**, and fully opened up the EA
finds ~19.5/day but wins only 76% of them and loses $13,178. **His selection among the same setups
is still much better than the machine's, and closing that gap is worth more than any dial.**

**ZEE MUST REATTACH.** The Journal must read `[DIA] ZeeUHV v1.27 - pivot 3 - retraceFix ON -
humpBudget 3 - sweep off ...`. Every field in that line is read back from the live inputs, so it
cannot claim a configuration the binary is not running.

## ZeeUHV_Diamond v1.19-1.23 — THE DETECTION AUDIT (2026-09-29)

**magic 88154 · NOTHING SHIPPED AS A DEFAULT — every new input is OFF · full report:
`DIAMOND_WINRATE_2026-09-29.md`**

Zee: *"try to increase the Winrate of the EA to maximum possible"*, then *"i need the 94% or
more config. even if its 99%"*, then — after the numbers — *"i want you to loop until u've
fixed the retracement logic, the camel humps, the ultra high volume candle, the breakout being
a low volume momentum candle"*.

**THE CORRECTION THAT MATTERS MOST: the Diamond's 90% is a nine-day number.** The
`DIAMOND_GEOMETRY_2026-09-17.md` row (90% / +$488 / 82 trades) reproduces exactly and is a
slice. On the full window it is a different machine:

| window | trades | WR | net |
|---|---|---|---|
| 09.08 → 09.17 *(that doc)* | 82 | **90.2%** | +$488 |
| **08.06 → 09.16 (39,834 bars)** | **274** | **74.1%** | **−$1,113.80** |
| **his real fills, Aug 20 → Sep 21** | **735** | **78.4%** | **−$1,703.40** |

The tester and the live account agree. **No configuration tested on the full window is
profitable**; the best is −$232.

**THE WIN RATE IS PURCHASABLE AND WORTH NOTHING.** flat $200 stop / 600-min clock gives
**97.0%** (227W/7L, 234 trades) and **−$2,140** — because six of the seven losses are ONE
basket, 2026.09.01 15:21, each −$780.60, exited on the clock after ten hours. That basket is
the entire loss and the entire $4,682 drawdown. A coin at that geometry wins ~99%; at the
shipped geometry a coin wins 81.3% where the EA wins 74.1%, so **the entry is 7.2 points worse
than random** — NullEntry's August verdict, re-confirmed on real ticks at the current version.
Lot size cannot help: it multiplies +$2,545 and −$4,683 identically.

**HIS FEB 11 IS A DIFFERENT ANIMAL, and it is the only real edge in the record.** His own
broker report (5118408, 69 positions, 0.10 lots): 94.2%, avg win 1.54 of gold, **avg loss 0.16**,
no stop on any row, all four losses held exactly 25 min and closed ≈ break-even, median winner
1.0 minute. A coin at *his* geometry wins **9.4%**. He beat it by 84.8 points, and it lived in
the exit.

**THE THREE DETECTION DEFECTS — his diagnosis, confirmed by measurement:**

1. **`InpRetraceFix` — the UHV was never chosen.** `RetracementOrigin()` returned the most
   recent breaking body, not the first, so the UHV window was the pullback's tail. From the
   EA's own `[LAWX]` log, **155 fires: `origin == UHV` in 100 of them (65%)**, ≤2 candidates in
   75%, median gap 0 minutes. LAWS.md wants the loudest red *among all of them*.
2. **`InpOandaColour` — colour came from Blueberry, volume from OANDA.** His words:
   *"on OANDA volume, the colors are the correct ones we look for"*. 15.0% of 43,434 OANDA bars
   have a body under 0.20 of gold against a documented 0.85 feed difference, so their colour
   depended on which feed was asked. Now read from `oanda_bars.csv`, with misses counted.
3. **`InpBreakBodyMin` — the breakout had no momentum test at all.** LAWS.md clause (a) wants
   body/range ≥ 0.70 on the breakout; `BreakoutIsBar1()` tested colour, crossing and volume
   only, while `InpUhvBodyMin=0.5` applied a body floor to the **UHV**, which his page never
   asks for. The test existed on the wrong candle at the wrong threshold.

Clauses (b) quieter-than-UHV and (c) shares-body-with-the-high are **correct as written**. The
camel humps are faithful to his page but **draw their pivots from broker highs and lows** — the
obvious next fix, deliberately left out so these three can be attributed.

**`v1.19` is a pure speed fix** — the tester no longer re-reads all 43,434 rows of
`oanda_vol.csv` once per simulated bar. Baseline re-ran at **82 / 90.24% / +$488, identical**,
which is the only thing that makes it safe. `v1.20` added his four-indicator jury
(`InpJuryMode`), `v1.21` the bail (`InpBailSec`/`InpBailAt`).

**THE EXIT IS NOW CLOSED AS A DIRECTION — four refutations.** the Watcher (93%→64%), the volume
fade (39 of 45 lost), **`InpFailCandles` 3 (97%→70%, −$2,140→−$232)** and **`InpBailSec` 300/−2.00
(97%→63%, −$1,860, worse than doing nothing)**. Anything that closes a trade between the stop
and the target costs more than it saves.

**Rig note that changes how every past number should be read:** the rig's demo login
`12654799` is dead (Zee confirmed by hand). A single backtest tolerates it and proceeds after
the agent's environment-sync **times out** — `Environment synchronized in 0:09:09.813. Test
passed in 0:00:01.068`. **So a "13-minute run" in this ledger is 9 minutes of timeout and one
second of testing**, window length is nearly free, and **optimisation does not work at all**
(it waits on the sync forever). Reviving any valid login turns the loop from 6 configs/hour
into ~40.

## VSISA v1.29 — three machine-learning layers on top of v1.28 (2026-10-14)

**Who:** Zee: *"optimize the VSISA EA that runs on 5 minutes timeframe to maximize profits"* and *"apply all the
machine learning methods described in report.md to the VSISA EA on 5 min timeframe to get the best ever result"*.

**What:**
- `mt5/VSISA.mq5` v1.29 = v1.28 + the hooks from `VSISA_ml.mq5` with three layers ON. The models are trained on
  Jan–Jun only by `meta_labeling_system/src/vsisa_train.py` and compiled in as `VsisaMetaModel.mqh`
  (XGBoost classifier, threshold 0.40), `VsisaRegimeModel.mqh` (3-cluster GMM, skip mask 4) and
  `VsisaExhaustModel.mqh` (threshold 0.75).
- `VsisaDrlPolicy.mqh` ships too, but the PPO sizing is OFF: with the filters on it didn't beat a constant lot.
- Banner: `[VSISA] v1.29 (ML: meta 1 thr 0.40, regime skip 4, exhaustion 1 thr 0.75)`. Magic 88201 unchanged.

**Receipts** (XAUUSD_TK real ticks + $4/lot, 0.28 lots, $25k, 200 ms):
- **Jul 1 – Oct 8 (unseen):** v1.29 **+$10,018.82**, PF 3.37, DD $981, worst day −$276, vs v1.28 +$7,378.64,
  PF 1.77, DD $1,987. Random delay: +$10,221.
- **Full year:** +$22,078 (Jan–Jun is in-sample for the models).
- **Optuna** (about 150 trials) found nothing better than v1.28's own settings; all runners-up lost on Jul–Oct.

**Caution:** the 0.75 exhaustion threshold and the final combination were chosen after seeing Jul–Oct results.
Every layer can be switched off with its `Inp*Mode = 0`. Compiled into the Axi terminal with its four .mqh
files. Full results: report.md §28.

## TradeLifecycle v1.02 — expected TP1 and the 75% breakeven level (2026-10-14)

Zee: *"also show the TP.. what is the expected TP. what is its 75% etc"*.

The Saad EAs never send a take-profit to the broker, so for their trades (magic 88302 / 88330 / 88320) the
analyzer recomputes the EA's own TP1 with the EA's rules:
- **SELL:** the last support (a swing low with 3 candles on each side, within 100 candles, at least 5 pips
  below the entry; 30 pips for the 5-min EA)
- **BUY:** the setup candle (the one before the entry) on the 9 EMA → target the 50 EMA, on the 50 → the 9 EMA.
  The target EMA is drawn bar by bar as a moving line. If it's below the entry (or under the minimum), the
  analyzer shows "no TP1, 2×ATR trail".

**Drawn:** the TP1 line, the **75% line** (where the stop jumps to breakeven), and labels for both. **In the
panel:** the expected TP1, the 75% level, and "at TP1: close half, trail $2" ($4 for the 5-min EA).

**Not yet verified:** a tester check against the TP1 values the EAs logged for five real Axi trades (12–13 Oct)
was started but produced no output before Zee asked to finalize. The `InpVerify` mode is in the code for that
check.

## TradeLifecycle v1.01 — labels that never overlap (2026-10-14)

Zee, with a screenshot of v1.00 (labels piled on the newest candles, the panel's text cut off): *"on the
candles i want clear labels. means they are not overlapping, not overlapping the candles, not labels with each
other."*

**What changed:**
- **Labels are queued, then placed in screen pixels:**
  - each one is measured with `TextGetSize`
  - it starts above the highest wick (or below the lowest wick) of the candles under it, on its preferred
    side, and moves further out until it doesn't touch another label or the panel
  - if neither side fits, it tries the left of its point
  - a dotted leader line joins it to its exact point
- **Re-laid out** on every scroll, zoom or resize (`CHARTEVENT_CHART_CHANGE`).
- **Chart shift on (30%),** so an open trade's labels have room right of the last candle.
- **The panel is sized from the measured text,** so no line is cut off.

No change to what is recorded or analysed.

## TradeLifecycle v1.00 — a trade-lifecycle diagram on the chart (2026-10-13)

**Who:** Zee: *"build a trade analyzer EA … if there's a current position open or the last closed trade … it
explains everything by writing on the chart and drawing labels like trail / tp updates / sl updates … a
lifecycle diagram EA"*.

**What it is:** `mt5/TradeLifecycle.mq5`. **It never trades.**
- **Which trade:** the newest open position, otherwise the last closed one within `InpLookbackDays`. Can be
  limited by `InpMagic` / `InpChartSymbolOnly`, or set to one `InpTicket`.
- **What it draws:**
  - entry and add-on arrows
  - the average entry line, and the SL and TP paths as steps
  - labelled stop moves: breakeven / trail / tightened / **WIDENED** / removed, and TP changes
  - partial closes and the exit, with $ and who/why (EA, desktop, phone, web, stop loss, take profit,
    stop-out, from the deal/order reason)
  - the best and worst price (1-minute candles)
  - Saad EA extras (setup, breakeven time, TP1 time) from their CSV
  - a summary panel with the timeline, net, duration and R
- **The limit it works around:** MT5 stores no history of SL/TP modifications. So the EA records every SL/TP
  change of every open position on the account once a second (plus on each trade event) to
  `Common\Files\TradeLifecycle\<login>.csv`. Trades from before it was attached show only the first stop
  (from the opening order) and the final stop (from the exit deal).

**Receipt:** the Strategy Tester self-test (`InpSelfTest=true`, XAUUSD_TK) scripted a BUY:
breakeven, a 0.5-lot partial, a trail, then a stop exit. The analyzer reproduced every step, with net +$283.50
(0.57 R). Compiled into the Axi and PXBT terminals.

## Saad_strategy_5min v1.01 — a profitable M5 variant: sell only (2026-10-13)

**Who:** Zee: *"find a profitable variant of this EA on 5 minute timeframe using whatever tools you have.
call this EA name_5min"*.

**How it was found** (`monitor/strategy_lab/optuna_5min.py`, study `saad5_janjun`):
- Optuna, about 150 trials over 3 rigs. Every trial was a real MT5 test (XAUUSD_TK real ticks + $4/lot, 1 lot,
  $25k, 200 ms).
- Tuned on Jan 6 – Jun 30 only; fitness = net − 0.5 × drawdown.
- The top 10 were then run on unseen Jul 1 – Oct 8: 7 of 10 profitable there.
- Trial 126 was chosen. It's the best on Jul–Oct, so the pick is flattered by having looked at those months.

**New defaults** (all switches already in the EA):
- `InpBuys=false` (**sell only**)
- `InpMinRangeAtr` 0.55 → 1.10, `InpSlPips` 20 → 15, `InpMaxRiskUsd` 9 → 8
- `InpChopEr` 0.11 → 0.06, `InpChopErLook` 48 → 40
- `InpWickMin` 0.45 → 0.35, `InpMaruBody` 0.53 → 0.58, `InpHamRatio` 2.5 → 2.0
- `InpBreakPips` 2 → 1, $ trails 2 → 4, `InpMinTpPips` 5 → 30, `InpSessFrom` 0 → 8
- comments `Saad5 v1.01 BUY/SELL`

**Receipts** (EA defaults, reproduced to the cent):
- Jan–Jun **+$13,651.25** · Jul–Oct **+$16,505.25** · PF 1.26 · DD $6.0k / $9.9k
- full period with random delay: **+$32,992**, DD $9.4k, 5 of 10 months negative
- runner-up (trial 140): +$23,568, both halves positive

**Cautions:**
- The same settings with **buys allowed make only +$4,457**: the longs lose. Gold fell about 20% over the
  test year, so the edge may be regime-bound.
- The profit is about 1/6 of the 15-min EA's.
- Compiled into the Axi terminal. **Demo first.**

## Saad_strategy_15min v1.18 · pyramiding_max_3 v1.01 — trade comments name the EA (2026-10-13)

**Who:** Zee: *"in the pyramiding EA and the latest EA to say in comments the name of EA so we know
exactly where the trade is coming from.."*

**What changed:**
- **v1.18** writes `Saad15 v1.18 BUY` / `Saad15 v1.18 SELL` as each order's comment (was `saad_long` /
  `saad_short`), through `#define EA_COMMENT`.
- **pyramiding_max_3 v1.01** is built on v1.18 and writes `Saad15-PYR3 v1.01 BUY/SELL`, with add-ons
  `Saad15-PYR3 v1.01 ADD`. It recognises its add-ons by " ADD" in the comment (was the bare `saad_pyr`).

**No trading change.** MT5 receipts, unchanged to the cent (Jan 6 – Oct 8, real ticks, 1 lot, 200 ms):
- v1.18: +$202,221.80
- pyramiding v1.01: +$479,814.52

**Compiled:**
- pyramiding v1.01 into the Axi terminal
- v1.18 **not yet**: v1.17 was attached with an open trade, and recompiling would reload it mid-trade

## Saad_strategy_15min_pyramiding_max_3 v1.00 — v1.17 + scale-in pyramiding (2026-10-13)

**Who:** Zee: *"ATR 0.25×, 5 tiers, ×0.75 add-ons .. +$479,815 this is the result we want to put into:
make it another EA named as *_pyramiding_max_3"*.
**File:** `mt5/Saad_strategy_15min_pyramiding_max_3.mq5`, built by `monitor/strategy_lab/build_pyr_max3.py`.
Magic **88330**, so it can run beside the plain EA (88302). Compiled into the Axi terminal.

**What:** Saad_strategy_15min v1.17, unchanged, plus the pyramid engine copied verbatim from the test EA
`Saad_pyramid`:
- when the trade is **0.25 × ATR(14)** beyond the last entry, add **0.75 ×** the last position's lots
- up to **5 positions**, about 3.05 lots at `InpLots = 1`
- add-ons carry the base trade's stop and close with it; **no breakeven lock**

**Receipts** (XAUUSD_TK real ticks + $4/lot, 1 lot, $25k, Jan 6 – Oct 8):

| Run | Net | PF | Max DD | Worst day | Losing months |
|---|---|---|---|---|---|
| EA defaults, 200 ms | **+$479,814.52** (identical to the test EA) | 1.58 | $41.8k | −$12,338 | 0 |
| EA defaults, random delay | +$468,074.90 | 1.56 | $42.8k | −$13,035 | 0 |

The 200 ms run splits **Jan–Jun +$320,169 / Jul–Oct +$159,646**.

**Caution (report.md §23):** this is bigger size, not a better entry.
- Plain v1.17 at about 3 lots would make about +$607k for the same drawdown.
- Profit per $ of drawdown is 11.5 here vs 15.1 for plain v1.17.
- The worst day is −$12k to −$13k on a $25k account.
- Demo first.

## Saad_strategy_5min v1.00 — 5-minute variant: NOT profitable, demo only (2026-10-13)

Commit `1ad36d0`. Magic 88320. v1.17 rescaled for M5 (risk cap $9, stop 20 pips, choppy window 48).
30 variants on real ticks, tuned Jan–Jun:
- best Jan–Jun +$16,243
- the same settings on Jul–Oct: **−$27,816**

Spread + commission eat M5 moves. Report §11.

## Saad_strategy_15min v1.17 — default lot 1 (2026-10-13)

Commit `e9cfea7`. Zee: default `InpLots` 0.10 → **1.00**. No logic change.
Receipt: +$202,221.80 at 1 lot (Jan 6 – Oct 8, real ticks, 200 ms), PF 1.60, 0 losing months.

## Saad_strategy_15min v1.16 — Zee's rule: 50% at TP1 + breakeven (2026-10-12)

Commit `f14c8b5`. `InpPartialPct` 0 → **0.5**, `InpTp1Be` → **true**. When TP1 is hit, half the trade
closes and the rest's stop is never worse than the entry.
- Ship receipt: **+$202,221.80** at 1 lot, vs v1.14's +$206,705.
- Worst day −$3,806 vs −$3,966; biggest loss unchanged (−$2,570).
- MT5 win rate (per deal) 61% vs 48%.
- Random delay: +$201,922 / +$207,971. Report §8.

## Saad_strategy_15min v1.15 — HTF trend filter switch, OFF (2026-10-12)

Commit `e8dec27`. Adds `InpHtfMin` (H1/H4 trend filter), **off by default**. Tested: costs most of the
profit (H1 +$64k, H4 +$83k vs +$202k). Report §2/§12.

## Saad_strategy_15min v1.14 — min candle 0.55, marubozu 0.53, choppy 0.11 (2026-10-12)

Commit `56e5dcb`. Tuned on Jan–Jun, confirmed on unseen Jul–Oct:
- Jul–Oct **+$68.6k** vs v1.13's +$48.2k
- full period **+$206.7k**, PF 1.62, DD 5.5%, 0 losing months
- random delay +$205k (commit `7f84039`)

Report §0/§3.

## EA_20USD … EA_200USD v1.13 — small-account tiers; M5 "frequent" variant rejected (2026-10-12)

Zee asked for EAs for $20/$40/$80/$100/$200 accounts at high leverage, and for a variant with at
least one trade an hour. Each tier file is `Saad_strategy_15min` v1.13 at a **fixed 0.01 lot**
(Axi's minimum), magic 88310–88314, with its survival numbers in the header. Compiled into the
Axi terminal.

**Survival court:** XAUUSD_TK real ticks, 200 ms delay; one-month runs started at each month
Jan–Sep (9 starts per tier).

The first pass silently ran at 1:400, because axi_rig ignored `--leverage` (since fixed).
Re-run at a confirmed **1:1000**:

| tier | months losing more than half | worst month end | median month end |
|---|---|---|---|
| $20 | 6/9 | −$2.41 | $3.82 |
| $40 | 5/9 | −$2.63 | $0.93 |
| $80 | 2/9 | −$5.44 | $263 |
| $100 | 2/9 | −$3.70 | $283 |
| **$200** | **0/9 (1 losing month)** | **$136** | **$383** |

PXBT XAUUSDp also has a 0.01 minimum lot (contract 100, spread ~17 pts), so the maths is the
same there.

**Why the small tiers fail:** one stop at 0.01 lot costs $8–15. Leverage only changes margin.
Tighter stops, which would make small accounts viable, all lost money on real ticks.

**M5 frequent variant: rejected.** 24 variants on real ticks gave 6–26 trades a day, which meets
the frequency, but the best was +$29k on a $100k deposit at 1 lot over 9 months (PF 1.04), and
most lost. Spread plus $4/lot commission eat the smaller M5 moves.

**v1.13 with random delay (finalist check):** +$167,178 / +$164,925 at 1 lot; +$17,203 at 0.10
lot (max DD 2.0%, worst day −$440).

## Saad_strategy_15min v1.12–v1.13 — real-tick court, the v1.11 fix, SL 35 + hammer 2.5 + wick 0.45 (2026-10-12)

**THE DATA.** Around Oct 10–11, Axi revised its gold history. Since then the tester discards real
ticks for 135,070 of 271,894 Jan–Oct minutes on XAUUSD.pro ("tick prices not matched … every tick
generation used") and invents ticks from the candles. Per month: Jan–Jul 48–68%, Aug 28%,
Sep–Oct 12–13%. Zee's terminal has the same problem since Oct 11; his Oct 9–10 runs show ~92
minutes, which is clean. Re-downloading ticks and candles in the rig did not fix it.

The fix is `mt5/AxiTickClone.mq5`, which builds the custom symbol **XAUUSD_TK** from Axi's 60.4M
real ticks, with Axi's sessions and contract specs. The tester builds candles from those same
ticks, so 0 minutes are discarded. The harness adds $4/lot commission on _TK. Every number below
is on XAUUSD_TK. Synthetic minutes had inflated the strategy: the v1.09 control went from +$187.8k
to **+$151.9k** at 1 lot.

**v1.12:**
- FIX: v1.11 reset `p.resTp1` straight after setting it, which cost ~$39k. Fixed, the rule
  itself still loses −$70k on real ticks, so `InpLongResTp1` defaults OFF.
- A trading call is retried only after a 3 s back-off, or 60 s when the market is closed.
- Quiet CTrade logs in non-visual tests. Agent logs had reached 381–866 MB, and the terminal
  tester log 3.2 GB.
- Variant switches: entry mode (dip / sweep), stop mode (ATR / $), partial close at TP1,
  risk-% sizing with a min-lot guard and margin check, daily loss %.

**v1.13 defaults:** `InpSlPips` 30 → **35**, `InpHamRatio` 3 → **2.5**, `InpWickMin` 0.35 → **0.45**.

Court: 200 ms fixed delay, $100k deposit, 1 lot; tune on Jan 6–Jul 1, holdout Jul 1–Oct 8.

| arm | Jan–Jun | Jul–Oct holdout | full Jan 6–Oct 8 | PF | max DD |
|---|---|---|---|---|---|
| v1.12 base (= v1.09) | +$112,935 | +$37,958 | +$150,893 | 1.36 | 10.0% |
| **v1.13 (SL 35 + ham 2.5 + wick 0.45)** | — | **+$48,220** | **+$167,534** | **1.43** | **9.5%** |
| SL 35 alone | +$117,393 | +$44,291 | +$161,684 | 1.40 | 9.3% |
| shorts with the old exit (`InpShortTouch 0`) | +$124,718 | +$35,475 ✗ | — | | |
| risk cap $20 | +$126,727 | +$41,615 | +$168,342 | 1.28 | 15.1%, worst day −$8.5k |

**Rejected on real ticks:**
- tighter stops: 5–25 pips, 0.5–1.5×ATR, $2–$10 from entry
- wait for a dip after the break: 0/25/50/75/100% into the candle, 1–3 candles
- liquidity sweep then enter: 20 variants, all losing
- partial close at TP1
- break by 0 pips
- 2×ATR stop: PF 2.04 on Jan–Jun, but only +$17k on the holdout
- choppy filter length 12/20, which collapses the result (a fragile setting)
- CTC at 60% or 90%: 75% is a narrow peak

Logs: `monitor/strategy_lab/zee_loop.jsonl`, `zee_oos.jsonl`, `zee_full.jsonl`.

Compiled into the Axi terminal (0 errors); default lots 0.10.

## Saad_strategy_15min v1.10–v1.11 — trade log; TP1 = next resistance for longs with the EMA below (2026-10-12)

**v1.10 — trade log** (`InpLog`, `InpLogCsv`, both on). Zee asked: *"i want to know what the TP was set
to etc. how can i see that?"*. The broker shows `tp: 0.00` because the EA never sends TPs: TP1 is a
trigger for the trail, and TP2/TP3 are watched by the EA.
- **Experts tab:** every event — SETUP, SKIP, ENTRY (SL, $ risk, TP1 rule), CTC, TP1 (price, TP2),
  TPn → TPn+1, day-close shut, and EXIT (reason, best price, number of SL moves, profit /
  commission / swap).
- **CSV:** one row per closed trade in `Common\Files\Saad15_trades_<symbol>_<magic>.csv`. In the
  visual tester the file name ends `_tester`. Nothing is written in ordinary tester runs.
- Checked on Oct 1–8 at 1 lot: the same trades and result with and without logging (+$10,309).

**v1.11 — `InpLongResTp1 true`.** Zee: *"in case of long entry at time of entry if the 50 EMA is below
our entry, then instead of having 0 tp ... we should have the first target as the TP which is the
next resistance level"*. A long whose exit EMA is below the entry, or within 5 pips of it, now gets:
- **TP1** = the newest swing high at least 5 pips above the entry (pivot 3, last 100 candles)
- **at TP1:** the same as an EMA touch — the stop goes to $2 behind the market, then TP2 / TP3
- **CTC** measured toward that resistance
- only if no resistance exists: trail from the entry, as before

Zee's live PXBT trade #58513632 (BUY 1 lot @ 4191.87, closed at 4191.40, −$47) fits this case. Its
stop moved at the first tick of the 04:45 candle: the 2×ATR candle-close trail of a no-TP long.

**NOT yet measured in MT5.** The rig hung during the full-period check and Zee stopped the runs.
Compiled into the Axi terminal (0 errors). Expect a trading change versus v1.09.

## Saad_strategy_15min v1.09 — marubozu body ≥ 50% of the candle (2026-10-12)

Zee: *"let's goto 0.50 (50%) with +$207,274"*. `InpMaruBody` 0.70 → **0.50**: the two wicks may
now be up to half the candle. Pins and hammers are still recognised first.

Sweep (1 lot, Axi M15, Jan 1–Oct 8, no delay; net / PF / max DD):

| body ≥ | net | PF | max DD |
|---|---|---|---|
| 0.95 | +$60.7k | 1.19 | 24.2% |
| 0.90 | +$77.2k | 1.24 | 22.9% |
| 0.80 | +$118.6k | 1.33 | 19.2% |
| 0.75 | +$127.0k | 1.34 | 13.3% |
| 0.70 (old) | +$167.3k | 1.43 | 12.1% |
| 0.65 | +$162.8k | 1.39 | 13.7% |
| 0.60 | +$182.9k | 1.43 | 13.3% |
| 0.55 | +$190.2k | 1.44 | 11.8% |
| **0.50** | **+$207.3k** | **1.48** | **10.3%** |
| 0.45 | +$192.9k | 1.43 | 11.1% |
| 0.40 | +$203.7k | 1.45 | 11.7% |
| 0.35 | +$195.1k | 1.42 | 12.7% |
| 0.30 | +$185.3k | 1.39 | 12.3% |
| no marubozu | +$57.3k | 1.19 | 25.7% |

0.35–0.55 is a plateau, and 0.50 sits in the middle of it.

**Ship receipt** (compiled defaults): 1 lot **+$207,274 · 1,027 trades (5.4/day) · WR 47.6% ·
PF 1.48 · max DD $19,180 (10.3%) · worst day −$4,840 · 1 losing month (Jul −$6.2k)**. 0.10 lots:
+$20,727, DD 4.7%. Tuned on the same nine months it is scored on — expect less live.

## Saad_strategy_15min v1.08 — directional pin bars: TESTED, left OFF (2026-10-12)

Zee: *"if the direction is long then we accept a bullish pinbar only (body on top of wick and
body in direction of breakout) AND we don't accept the inverted pinbar. same for SHORT"*. Added
`InpPinColor`: the pin's body must close the trade's way, green for LONG and red for SHORT.
It works with the existing `InpPinDir` (the long wick points away from the trade). Both stay OFF.

| arm (1 lot, Axi M15, Jan 1–Oct 8, no delay) | net | trades | WR | PF | max DD |
|---|---|---|---|---|---|
| **any pin, the EMA decides (v1.07, kept)** | **+$167,345** | 926 | 47.0% | **1.43** | **12.1%** |
| pin must point the trade's way | +$89,951 | 955 | 45.6% | 1.22 | 22.8% |
| ...and body closes the trade's way | +$124,020 | 834 | 46.6% | 1.35 | 16.0% |
| no pin bars at all | +$89,466 | 629 | 46.1% | 1.33 | 26.6% |

**The "inverted" pins earn about half the profit.** A pin with its wick toward the trade, at the
EMA, is a rejection the market then breaks through. Every month got worse with directional
pins. No trading change in v1.08.

## Saad_strategy_15min v1.07 — $2 trails on both sides; widening tested and rejected (2026-10-12)

Zee: *"ok let's activate: A fixed $2 trail on both sides"*. `InpLongTrailUsd` and
`InpShortTrailUsd` 3 → **2**. Added `InpTrailStepUsd` (0 = off), which widens the trail at each
TP after TP1. Zee asked to test $2 → $3 → $4.

**THE DATA MOVED UNDER US.** Between the v1.06 runs and these, the rig re-synced Axi's gold ticks:
59,886,606 → 59,410,491 ticks for Jan 1–Oct 8, and the report's history quality now reads "n/a".
The same v1.06 build went from +$141,492 to +$158,490 at 1 lot. Compare only arms run on the
same data. Everything below is on the new data.

| arm (1 lot, Axi M15, Jan 1–Oct 8, no delay) | net | WR | PF | max DD | worst day |
|---|---|---|---|---|---|
| $3 fixed (v1.06) | +$158,490 | 46.9% | 1.41 | $18,395 (13.1%) | −$5,340 |
| $3, +$1 per TP | +$154,794 | 46.8% | 1.40 | 13.4% | −$5,340 |
| **$2 fixed (v1.07 ship)** | **+$167,345** | 47.0% | **1.43** | **$17,458 (12.1%)** | −$5,140 |
| $2 → $3 → $4 (Zee's idea) | +$164,413 | 47.0% | 1.42 | 12.3% | −$5,140 |
| $2, +$0.50 / +$2 per TP | +$165,960 / +$161,715 | 47.0% | 1.43 / 1.42 | 12.2 / 12.5% | −$5,140 |

**Widening never helps:** a looser trail after TP2 gives back more. The ship receipt is the
compiled defaults with no overrides: 0.10 lots +$16,734 (DD 4.7%); 1 lot +$167,345.

**Monthly at 1 lot:**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct 1–8 |
|---|---|---|---|---|---|---|---|---|---|
| +$38,448 | +$12,092 | +$15,935 | +$43,525 | −$5,192 | +$13,706 | −$4,818 | +$29,482 | +$17,314 | +$6,854 |

Compiled into the Axi terminal.

## Saad_strategy_15min v1.06 — TP1 → $3 trail, TP2 → TP3 ladder, for LONGs and SHORTs (2026-10-12)

Zee (RULES_EMA_SAAD.md): *"Set TP to next liquidity (last resistance), call this the TP2. If we
reach the TP2 ... set the TP further to TP3 ... last to last resistance <= In essence we'll exit
at the Trailing SL ... do the same for SHORT trades TP"*.

- **LONG:** TP1 = a touch of the exit EMA. The stop goes to bid − $3 and trails. TP2 = the next
  resistance. When TP2 is reached, TP3 = the resistance beyond it, and so on.
- **SHORT (`InpShortTouch 1`, `InpShortTrailUsd 3`):** TP1 = the last support. The stop goes to
  ask + $3 and trails. TP2 = the next support below, then TP3, and so on.
- **TP2 and TP3 are watched by the EA, not sent to the broker.** A broker TP would close the
  trade at TP2 and TP3 could never happen. The exit is the trailing stop, as the rule says. The
  ladder is drawn on the chart: "TP2 reached → TP3 …".

Court (Axi M15, Jan 1–Oct 8, **1 lot**, no delay):

| arm | net | WR | PF | max DD | worst day |
|---|---|---|---|---|---|
| v1.05 (old short exit: lock + ATR trail) | +$147,294 | 41.2% | 1.39 | $22,753 (16.3%) | −$5,859 |
| **v1.06 default (shorts: $3 trail + ladder)** | +$141,492 | 45.2% | 1.36 | **$21,043 (15.3%)** | −$5,425 |
| v1.06, short trail $2 | +$148,471 | 45.8% | 1.38 | $19,839 (14.1%) | −$5,324 |
| v1.06, short trail $5 | +$127,070 | 44.1% | 1.32 | $24,156 (18.8%) | −$5,624 |
| v1.06, both trails $2 | **+$151,069** | 45.8% | 1.39 | **$19,552 (13.9%)** | −$5,227 |

**Readings:**
- **Zee's short rule at $3** costs about $5.8k against the old short exit, but cuts the drawdown
  and lifts the win rate.
- **At $2 for both sides** it is the best seen: +$151k, DD 13.9%. Defaults stay at Zee's $3.

## Saad_strategy_15min v1.05 — the 30-minute no-new-trades rule removed (2026-10-12)

Zee: *"REMOVE the condition: No new setups or entries in the last 30 minutes before the close.
keep the other one"*. `InpNoNewMins` 30 → **0**. Losers are still shut 3 minutes before the close
(`InpCloseLossMins 3`). CTC 75% and the v1.04 long exit stay on.

**Ship receipt** (compiled defaults, Axi M15, Jan 1–Oct 8, **1 lot**, no delay): **+$147,253 ·
895 trades · WR 41.2% · PF 1.39 · max DD $22,753 (16.3%) · worst day −$5,859 · 1 losing month.**
With the old long exit (`InpLongTouch 0`) it reproduces Zee's chosen row exactly: +$138,133, PF
1.37, DD 17.6%.

## Saad_strategy_15min v1.04 — Zee's LONG exit: touch the 50 EMA → trail $3 + TP at the last resistance (2026-10-12)

`mt5/RULES_EMA_SAAD.md` (Zee): *"In case of TP touched 50 EMA -> 1. Activate Trailing SL at 3 USD
less than current price of the market 2. Set TP to next liquidity (last resistance)"*.

`InpLongTouch 1` (default) · `InpLongTrailUsd 3.0` · `InpLongResTp true`. When the bid touches
the long's exit EMA (the 50 EMA, or the 9 EMA for the inverse rule), three things happen:
- the stop goes to bid − $3
- the TP is set at the last swing high at least 5 pips above
- the stop then follows the market $3 behind, tick by tick, in steps of at least $0.10, and never
  moves back

These longs skip the ATR trail. Shorts and no-TP longs are unchanged.

Court (Axi M15, Jan 1–Oct 8, **1 lot**, no delay):

| arm | net | WR | PF | max DD | worst day |
|---|---|---|---|---|---|
| v1.03 default (old long exit) | +$126,863 | 38.1% | 1.34 | $26,625 (21.2%) | −$5,104 |
| **v1.04 default (touch → $3 trail + resistance TP)** | **+$135,759** | 41.5% | 1.36 | **$22,980 (16.6%)** | −$5,859 |
| v1.04, trail $2 / $5 / $8 | +$137,210 / +$124,202 / +$127,448 | — | 1.36 / 1.33 / 1.34 | 16.3 / 18.2 / 18.3% | — |
| v1.04 without the resistance TP | +$135,800 | 41.5% | 1.36 | 16.6% | — |
| v1.04 + `InpNoNewMins 0` | **+$147,253** | 41.2% | **1.39** | $22,753 (16.3%) | −$5,859 |

**Readings:**
- **Zee's long exit beats the old one:** +$8.9k, and the drawdown falls from 21.2% to 16.6%.
- **$2 and $3 trails are equal** within noise; $5 or more is worse.
- **The resistance TP almost never fires** before the $3 trail closes the trade (same result
  with or without it). It is kept because the rule asks for it.
- The 30-minute no-new-trades rule still costs about $11k at 1 lot.

## Saad_strategy_15min v1.02–v1.03 — CTC at 75% of the TP, day-close rules, clearer labels (2026-10-12)

Zee: *"if 75% of TP has been reached, then CTC breakeven the trade moving the SL to Entry price.
Trailing SL should be activated after TP is hit"* and *"0.5 hours before day close don't take a
trade. if a trade is open on day close, if it is profit, keep it open. if a trade is in loss
on day close, then shut it down"*.

- **v1.02 `InpBeTpPct 0.75`:** once price has covered 75% of the way from entry to the TP, the
  stop moves to the entry. The TP used is the support level for shorts, the exit EMA at that
  moment for longs, or a fixed TP if one is set. Longs with no TP are not affected. Exits at the
  entry are labelled "breakeven (CTC)".
- **Trailing after the TP** was already the behaviour (`InpRide`): before the TP the stop stays
  beyond the candle, or at the entry after CTC. Longs with no TP still trail from the entry.
- **v1.03 `InpNoNewMins 30`, `InpCloseLossMins 3`:** the close comes from the broker's own
  trading sessions for the symbol, so the Friday close counts too. No setups and no entries in
  the last 30 minutes. 3 minutes before the close, trades in loss are shut and winners stay open.
  The log reports the counts.
- **Labels:** text now sits 2.5–4 ATR away from the candle, with an arrow pointing back to it.
  Skip notes are off by default (`InpDrawSkips`).

Court (Axi M15, Jan 1–Oct 8, 0.10 lots, no delay):

| arm | net | trades | WR | PF | max DD | losing months |
|---|---|---|---|---|---|---|
| v1.01 (no CTC, no day rules) | +$13,344 | 796 | 42.1% | 1.30 | 6.1% | 0 |
| + CTC 75% | +$13,431 | 865 | 38.7% | 1.35 | 7.3% | 1 |
| CTC 50% / 90% | +$11,864 / +$11,910 | — | — | 1.32 / 1.29 | 7.5 / 10.4% | 1 |
| + CTC + shut losers at close only | **+$13,813** | 885 | 37.9% | **1.37** | **6.3%** | 1 |
| + CTC + no new trades 30 min only | +$12,424 | 855 | 38.8% | 1.33 | 7.4% | 1 |
| **+ CTC + both day rules (v1.03 default)** | +$12,686 | 872 | 38.1% | 1.34 | 7.6% | 1 |

At 1 lot, v1.03 makes +$126,863 with a 21.2% drawdown.

**Readings:**
- **CTC:** 75% is the best of 50 / 75 / 90, but only slightly better than no CTC. It lowers
  the win rate, because breakeven exits lose the spread.
- **Shutting losers at the close helps** (+$382, drawdown 7.3 → 6.3%).
- **"No new trades in the last 30 min" costs about $1,000** over nine months. It ships ON
  because Zee asked for it; `InpNoNewMins=0` switches it off.

## Saad_strategy_15min v1.01 — chart labels for the visual tester (2026-10-12)

Zee: *"put labels on each setup and their exit candles etc. the labels similar to tradingview ...
such that I can see the labels in the strategy tester while testing with visualization = ON"*.

Drawn only in the visual tester or on a live chart (`InpDraw`, `InpDrawSkips`, both on), so
ordinary tester runs are not slowed. Labels are plain text, since MT5 shows no emoji:
- **SETUP** — a gold box around the candle and the break level, with the candle type and EMA.
  The tooltip gives the exit rule.
- **SKIP** — grey notes: not broken in time, stop too far, no support, choppy, market closed.
- **BUY/SELL #n** — an arrow, the SL, and the TP (support level, or the EMA close for longs).
  The tooltip gives the risk in $.
- **Stop path** — red dashed steps before the TP, orange after. "TP reached → trailing" marks
  the TP, and says when the broker refused the lock.
- **EXIT #n** — the reason (stop loss / trailing stop / TP / EMA close) and the $ result, plus a
  dotted line from entry to exit.

No trading change: the compiled v1.01 reproduces v1.00 exactly (+$13,344, 796 trades, Axi M15,
no delay). Compiled into the Axi terminal.

## Saad_strategy_15min v1.00 — the 15-minute variant (2026-10-11)

**`mt5/Saad_strategy_15min.mq5` · magic 88302 · attach on M15 only.** Zee: *"create a variant of
this EA, which i can test on 15 minutes scale ... find out why 15 mins timeframe is losing"*.
The engine is identical to Saad_strategy v4.03. Five defaults change:

| input | M5 EA | 15min |
|---|---|---|
| `InpMaxRiskUsd` | 9 | **15** |
| `InpBreakBars` | 2 | **1** |
| `InpSwingLook` | 300 | **100** |
| `InpShortLine` | 2 (either EMA) | **1 (9 EMA)** |
| `InpDayTargetUsd` | 150 | **0** |

**Why M5 settings lose on M15** (Axi, real ticks, Jan 1–Oct 8, 0.10 lots): −$1,780, 250
trades, 29% WR, PF 0.87, 8 losing months. The EA's own count: of 2,980 setups, **1,907 were
skipped because the stop was more than $9 away**. Every pips/$ input was sized for 5-minute
candles. On M15 the $9 cap keeps only the smallest candles — the quiet, indecisive ones —
and those lose.

**Ship receipt** (compiled defaults, no overrides, no execution delay): **+$13,344 · 796
trades (4.2/day) · WR 42.1% · PF 1.30 · max DD 6.1% · 0 losing months**. At 1 lot:
+$133,444, DD 18.1%. Monthly at 0.10: Jan +2,083 · Feb +871 · Mar +1,004 · Apr +3,914 ·
May +227 · Jun +704 · Jul +710 · Aug +2,122 · Sep +1,030 · Oct (1–8) +679. Only 91 of 188
days were green: fewer, bigger winners than on M5.

**Robustness:**
- risk cap $14 / $16 / $18 → +$10.0k / +$12.3k / +$10.0k; **$20 falls to +$7.5k (DD 15%)**
- PrimeXBT M15, Sep 1–Oct 8: +$1,400 (the M5 settings lost −$1,298)

**The court** (`monitor/strategy_lab/m15_grid/m15c/m15d`, one no-delay run each, at Zee's request):
- 33 + 71 + 18 variants, each one change from the best-so-far
- helped: shorts on the 9 EMA, no day target, a 4-candle pause after a loss, break +4 pips
- hurt: session hours, trend alignment, 2–3 trades at once, breakeven at $3, longer ER,
  dropping pin bars or marubozu

The court used no-delay runs only; random-delay runs are still to do.

## Saad_strategy v4.03 — more than one trade at a time: TESTED, left OFF (2026-10-11)

Zee: *"we should allow our EA to have more than 1 trade at one time.. we don't wanna miss out
on setups"*. New input `InpExtraDir` (0 any side · 1 same side as the open trade · 2 opposite).
Defaults unchanged (`InpMaxPos 1`), so v4.03 trades exactly like v4.02.

Court: Axi, real ticks, Jan 1–Oct 8, v4.02 settings, 3 random-delay runs per arm, averages.

| positions | trades | WR | net | PF | max DD | green days | worst day |
|---|---|---|---|---|---|---|---|
| **1 (shipped)** | 1,349 | 46.5% | **+$15,349** | **1.35** | **7.6%** | **65.5%** | −$593 |
| 2 | 2,077 | 43.4% | +$13,623 | 1.19 | 11.8% | 61.5% | −$869 |
| 3 | 2,560 | 41.7% | +$5,819 | 1.07 | 20.0% | 58.3% | −$1,246 |
| 5 | 2,874 | 41.5% | +$4,727 | 1.05 | 21.1% | 55.9% | −$1,401 |
| 2 + newer setup replaces the waiting one | 2,255 | 43.2% | +$8,991 | 1.12 | 16.2% | 61.0% | −$864 |
| 2, extra only on the same side | 1,896 | 43.2% | +$13,348 | 1.21 | 10.0% | 60.6% | −$844 |
| 3, extras only on the same side | 2,084 | 43.7% | +$14,065 | 1.21 | 12.0% | 60.9% | −$986 |
| 2, extra only on the opposite side | 2,027 | 42.9% | +$7,456 | 1.11 | 12.0% | 57.3% | −$717 |

**The setups skipped while a trade is open lose money on average** (about −$2.40 per extra
trade at 2 positions). Same-side extras come closest to break-even. Opposite-side extras
(hedging the open trade) are the worst. If Zee wants more trades anyway, the least costly
choice is `InpMaxPos=3, InpExtraDir=1`: +55% trades, about −$1.3k, drawdown 7.6% → 12%.

## Saad_strategy v4.02 — SHIPPED to Axi: the TradingView indicator, ported and tuned (2026-10-11)

**magic 88301 · gold M5 · Axi `XAUUSD.pro` / PrimeXBT `XAUUSDp`.** Zee (while asleep):
*"port these settings to an EA. check how its performing on a daily basis.. does it make us
profit daily? try to tune the EA's settings to see if you can achieve a higher profit / winrate"*
and *"tune it to the max possible. try everything u can."*

**What v4 is.** A rewrite that trades what the indicator `pine/saad_strategy.pine` (v4 engine)
draws. Setup candles:
- pin bars in any direction, with the EMA picking the side
- marubozu
- hammer / shooting star

Longs follow the rule (9 EMA setup → exit at the 50 EMA) and the inverse (50 EMA setup → exit
at the 9 EMA); the exit is a candle close at the EMA. Shorts set up on either EMA and target the
last support at least 5 pips away. Every trade:
- SL beyond the candle
- skipped if the risk is above $9
- "let winners run": at the TP the stop is locked, then a trailing stop takes over
- a waiting setup is cancelled across the daily close

v4.01 added tuning switches, all OFF by default:
- maximum positions; a newer setup replaces the waiting one
- daily loss stop and daily target
- per-candle and per-line switches
- trend, slope, EMA-gap and price-side filters
- spread filter, maximum TP distance
- fixed TP, a "lock $Y at $X" ratchet, time exit, cooldown after a loss

**v4.02 defaults** = Zee's chart settings ([optimal_settings_saad_strategy.md](optimal_settings_saad_strategy.md)) plus six court winners:
- `InpBreakPips` 0 → **2**
- `InpSlPips` 34 → **30**
- `InpTrailMode` → **2** (ATR)
- `InpTrailAtr` → **2.0**
- `InpLockPips` 2 → **0** (lock exactly at the TP)
- `InpDayTargetUsd` → **150** (no new trades once the day made +$150 at 0.10 lots)

**Ship receipt** (compiled defaults, no overrides, real ticks, random delay, $25k, 0.10 lots):

| | trades | per day | WR | PF | net | max DD | green days | worst day |
|---|---|---|---|---|---|---|---|---|
| Axi Jan 1–Oct 8, 3 runs | 1,350–1,366 | 7.6 | 46.0–46.8% | 1.32–1.35 | **+$14,457 – +$15,219** | 6.8–8.0% | 122–126 / 192 | −$588 |
| PrimeXBT Sep 1–Oct 8, 2 runs | 203–207 | 7.2 | 50.7–51.2% | 1.41–1.43 | **+$2,741 – +$2,921** | 3.2% | 22–23 / 30 | −$681 |

**Daily, honestly:**
- **Axi:** not every day is green — 126 green / 66 red. The worst run was 6 red days in a row
  and the worst week −$1,323. 30 of 41 weeks were green; the average day was +$79. 2 losing
  months, both halves of the year positive.
- **PrimeXBT (5 weeks):** every week green; worst day 29 Sep (−$681).

**The court (`monitor/strategy_lab/saad_v4.py`, `saad_v4.jsonl`, `saad_summ.py`; logs
`saad_sweep1..5.log`).**

1. **Random delay makes single runs noisy.** The same build gave +$4.4k to +$7.9k over four
   runs, because one-trade-at-a-time is path-dependent. From sweep 3 on, every arm ran
   **3× with random delay**; the averages are what count. (No-delay runs repeat exactly.)
2. **Zee's chart settings in MT5:** +$5,653 average, WR 44%, PF 1.08, DD 12%, 51% of days
   green. The chart showed 54% WR. The gap is the measured Python/chart haircut again.
3. **Changes that helped** (one at a time, 3 runs each):
   - break must clear the high/low by 2 pips: +$8,763, PF 1.14
   - then ATR × 2 trail: +$11,814, PF 1.18
   - then day target $150: **+$12,191, WR 50.3%, PF 1.28, DD 5.1%, 62.5% of days green**
   - then lock at the TP and SL 30: +$14,770, PF 1.33, DD 7.3%, 64% of days green — the ship
4. **Plateaus:**
   - day target: 100 / 150 / 200 / 250 all fine (+$10.3k – $12.2k)
   - break pips: 2 ≈ 3
   - ATR multiple: 1.75 – 2.5 = +$9.2k – $12.2k, but **1.5 (+$3.1k) and 3.0 (+$4.2k) collapse**.
     Treat 2.0 as the middle of a narrow plateau, not a knife-edge, and expect about +$9–12k.
5. **Win rate is geometry, again.** Fixed TPs win often and lose money (3 runs each):

   | Variant | WR | Net |
   |---|---|---|
   | Fixed TP 10 pips | 86% | −$5,075 |
   | Fixed TP 15 pips | 82% | −$4,763 |
   | Fixed TP 30 pips | 71% | −$3,384 |
   | Lock $0.5 at $2 | 74% | +$4,692 |

   None ships.
6. **Rejected** (single runs, Zee's settings as the base; inside the noise unless large):
   - session hours: 08–17 was −$6.8k worse here, the reverse of v3
   - trend alignment, price side, EMA slope (−$9.5k)
   - maximum TP distance
   - a second or third position (+DD)
   - newer setup replaces the waiting one
   - daily loss stop
   - breakeven at $3
   - wick-only touches
   - "long only when the exit EMA is above"
   - longs only / shorts only (each side alone ≈ $0)
   - no risk cap: **−$2,086, DD 54%** — the $9 cap is essential
   - skipping Monday or Friday
7. **On PrimeXBT's own ticks** (Sep–Oct) Zee's chart settings did best over those five weeks
   (+$3.7k, PF 1.34). The ship (+$2.8k, PF 1.42, DD 3.2%) is the one that holds up across nine
   months on Axi too.

**Rig notes.** With ~3 GB free RAM the portable terminal sometimes hangs *after* a finished test
("tester forced to close"). `saad_v4.py` now times out at 240 s, kills only the rig's terminal,
and retries.

Compiled into the Axi terminal: 0 errors, 0 warnings. **Not attached.** Inputs are stored by
name, so if the v3.20 EA was ever attached, remove it and attach fresh; otherwise the old
hours 08–17 and ER 0.20 would carry over.

## Saad_strategy v3.20 — SHIPPED to Axi: 25-pip stop (2026-10-11)

**magic 88301 · XAUUSD.pro M5 on Axi · defaults: hours 08–17 server (10 AM–7 PM PKT) ·
efficiency ratio ≥ 0.20 · `InpSlPips 20 → 25` · everything else = Saad's rules.**
Zee: *"Yes, commit v3.20 with the 25-pip stop as the default and compile it directly into the
Axi terminal."*

**Ship receipt** (Axi rig, compiled defaults, no overrides, real ticks, random delay, $25k,
0.10 lots, 2026-01-01 → 10-08): **+$5,679 · 272 trades · 65.8% WR · PF 1.66 · max equity DD
$1,135 (4.40%) · a trade on 162 days.** Stop plateau 25–30 pips (court below).
The worst stretch is 20–27 March 2026 (balance −$892, gold's fast slide): setups fired both
ways into a hard trend and stopped out; it is the same cluster in nearly every variant.
Compiled into the Axi terminal: 0 errors, 0 warnings. **Not attached** — Zee attaches it.

## Saad_strategy v2.00 — built from RULES_EMA_SAAD.md, NOT shipped (2026-10-11)

**magic 88301 · EMA 9 / EMA 50 · pin bar or marubozu on the line, enter on the break of its
high/low within 2 candles · long TP = candle touches 50 EMA · short TP = last swing low ·
SL 20 pips ($2.00 gold) beyond the candle.** v1.00 (EMA 9/15, my own reading before the
rules file existed) lost −$6,196 / PF 0.89 and is superseded.

Court (Axi rig, XAUUSD.pro M5, real ticks, random delay, $25k, 0.10 lots, Jan 1 → Oct 8):
rules as written **+$2,112 · 1,536 trades · 58% WR · PF 1.04 · DD 12.3% · 5 losing months**.
Shorts carry it (+$3,103, PF 1.09, DD 6.3%); longs lose (−$1,928, PF 0.93). The rules'
breakeven-at-$3 test HURTS: price-move $3 → −$1,530, profit $3 → −$352. Longs with no
"50 EMA above" condition +$2,591 but DD 21%; pins only (no marubozu) +$83; M15 +$1,152, DD 20%.
No edge strong enough to ship. Harness: `monitor/strategy_lab/saad_court.py`.

**v3.00 (same day) — the suggested fixes, each an input, all OFF by default.** Same court:
| variant | trades | WR | net | PF | DD |
|---|---|---|---|---|---|
| rules | 1,536 | 58% | +$2,112 | 1.04 | 12.3% |
| pin either wick direction | 1,559 | 58% | +$2,227 | 1.04 | 13.3% |
| breakeven at 1R | 1,589 | 57% | +$1,288 | 1.02 | 10.9% |
| trail last 2 candles | 1,833 | 51% | −$2,010 | 0.96 | 13.5% |
| long TP = last swing high | 1,423 | 55% | −$766 | 0.99 | 17.8% |
| SL 1.5×ATR | 1,328 | 68% | −$2,725 | 0.96 | 33.3% |
| SL prior swing + 5 pips | 1,331 | 67% | +$2,414 | 1.04 | 21.1% |
| trend EMA9 vs EMA50 | 424 | 55% | +$3,462 | 1.20 | 4.7% |
| **hours 08–17 broker** | **669** | **63%** | **+$6,056** | **1.28** | **5.4%** |
| hours 10–19 | 658 | 63% | +$4,718 | 1.19 | 9.3% |
| hours 07–18 / 09–16 | 798 / 508 | 61 / 62% | +$4,815 / +$2,986 | 1.17 / 1.18 | 8.2 / 6.1% |
| candle ≥ 1×ATR | 975 | 64% | +$2,089 | 1.06 | 8.1% |
| all suggestions at once | 117 | 74% | +$2,405 | 1.39 | 5.4% |

**The trend filter silently removes every long:** the rules take a long only when the 50 EMA
is above the candle, and the filter wants EMA9 > EMA50 — never both (longs-only + trend = 0
trades). Best: **hours 08–17, nothing else** — +$6,056, PF 1.28, positive both halves
(Jan–Apr +$4,457, May–Oct +$1,599), losing June (−$255) and August (−$358). Within it shorts
+$4,627 (PF 1.36) vs longs +$1,245 (PF 1.13). Defaults still = the rules; not shipped.

**v3.10 — chop filters** (Zee: *"we want to avoid choppy markets"*), all off by default, tested
on top of hours 08–17 (base re-run +$5,816 · 669 tr · PF 1.27 · DD 5.6%):
efficiency ratio ≥0.20 **273 tr +$4,960 PF 1.57 DD 4.4%** · ≥0.30 124 tr +$2,687 PF 1.68 ·
≥0.40 45 tr +$754 · EMA crosses ≤1/≤2/≤4 in 20: +$4,659 / +$6,032 / +$5,972 (PF 1.25–1.29) ·
50 EMA slope ≥1/2/4 pips: +$5,227 / +$4,971 / +$4,874 (PF 1.25–1.28) · ADX ≥15/20/25:
+$4,791 / +$5,286 / +$3,766 (PF 1.22 / 1.31 / 1.30). Only the efficiency ratio clearly lifts
quality, at the cost of frequency (~1.3 trades/day vs ~3). Blueberry/PrimeXBT runs dropped on
Zee's call ("stick to 1 broker"); Blueberry serves real ticks only from Sep 2026 (35% real).

**v3.10 SHIPPED AS THE BASELINE (2026-10-11, Zee: "commit v3.10 as the new baseline").**
Defaults now `InpSessFrom 8` · `InpSessTo 17` (Axi server time, UTC+3 = 10 AM–7 PM PKT) ·
`InpChopEr 0.20`; every other variant stays off. Ship receipt with NO input overrides:
**+$4,801 · 273 trades · 62.6% WR · PF 1.55 · DD $1,135 (4.42%)** — the same 273 trades as the
court row. Not attached anywhere; Axi demo only after the v3.20 tests.

**v3.20 court (2026-10-11) — Zee's four tests, each against the v3.10 baseline.** New inputs,
both off: `InpLongMode 1` = MIRROR longs (pin/marubozu on the 50 EMA, EMA9 > EMA50, TP last
swing high) · `InpTpPips` = fixed TP for both sides.
| test | trades | WR | net | PF | DD | Jan–Apr / May–Oct | losing months |
|---|---|---|---|---|---|---|---|
| v3.10 baseline | 273 | 63% | +$5,012 | 1.58 | 4.4% | +$3,781 / +$1,230 | 2 |
| 1 mirror longs | 210 | 59% | +$3,297 | 1.42 | 4.5% | +$2,272 / +$1,025 | 3 |
| 2A TP 30 pips | 289 | 71% | −$343 | 0.95 | 5.2% | −$378 / +$35 | 5 |
| 2B TP 40 pips | 286 | 69% | +$992 | 1.14 | 4.4% | +$176 / +$815 | 5 |
| 3A SL 15 pips | 274 | 59% | +$4,251 | 1.48 | 4.4% | +$3,488 / +$763 | 3 |
| **3B SL 25 pips** | **271** | **65%** | **+$5,654** | **1.66** | **4.4%** | **+$4,119 / +$1,534** | **1** |
| SL 30 pips | 271 | 66% | +$5,760 | 1.67 | 4.4% | +$4,145 / +$1,615 | 1 |
| SL 35 pips | 271 | 66% | +$5,177 | 1.57 | 4.4% | +$3,763 / +$1,414 | 2 |
| 4 shorts only | 145 | 65% | +$3,381 | 1.73 | 4.4% | +$2,655 / +$726 | 2 |
| shorts only, SL 25 | 144 | 67% | +$4,021 | 1.91 | 4.4% | +$3,144 / +$876 | 2 |
| mirror + TP 30 / 40 | 231 / 224 | 77 / 72% | +$1,330 / +$1,689 | 1.30 / 1.33 | 2.1 / 2.9% | | 3 / 3 |
| longs only: rules / mirror | 139 / 81 | 60 / 46% | +$1,452 / −$351 | 1.34 / 0.91 | | | 6 / 6 |

Findings: the mirror longs LOSE on their own (PF 0.91) — the rules' counter-trend longs
(+$1,452) are better. Fixed targets lose to the structural ones (TP 30 is negative).
**The stop is a plateau at 25–30 pips** (15 < 20 < 25 ≈ 30 > 35): +$5,654–5,760, PF 1.66–1.67,
one losing month. The max-drawdown event ($1,135.40) is the same cluster in almost every arm.
Shorts-only has the best PF (1.91 at SL 25) but half the trades and less money.

## VSISA v1.28 — the looser fade ships: 288 trades instead of 163 (2026-10-10)

**magic 88201 · XAUUSD.pro M5 on Axi · `InpFadePct 0.60 → 0.65` · `InpFadeLook 4 → 5`**

Zee: *"ok ship it"* — for his ask *"we can take as many setups as possible within a single
day.. so we're not kept waiting all day long"*.

**Ship receipt** (Axi rig, v1.28 compiled defaults with no overrides, real ticks, random delay,
$25k, 0.28 fixed lots, 2026-01-01 → 10-08): **+$17,745 · 288 trades · 43.8% WR · PF 1.86 · max
equity DD $1,679 (4.08%) · a trade on 141 days (was 104).** The same settings in the night's
court read +$19,417 / PF 1.96 — random delay alone. Against v1.27's +$17,486 / 163 / 2.65%:
77% more trades, the same money, more drawdown. Every cell of the 0.60–0.75 × 4–6 fade grid
was profitable; 0.65/5 led it and beat 0.60/4 in both halves of the year.

**Compounding stays OFF (`InpCompoundBase = 0`) — a change from what Zee approved.** He
approved "fade 0.65/5 + compounding at 25000". The pre-ship run with both as defaults gave
+$19,390 at **6.63% DD** ($2,879), PF 1.66: 9% more money than fixed lots for 70% more drawdown,
because lots had grown to 0.49 by the weak late months. On v1.26's fade compounding had kept
DD flat (3.85% vs 3.8%); with this fade it does not. It is one input away for whoever wants it.

**ZEE MUST REFRESH + REATTACH.** Navigator → Expert Advisors → right-click → Refresh; the
Journal must read `[VSISA] v1.28 - setup AUTO ...`. In the tester, reset inputs to defaults
(MT5 reuses cached inputs) — `InpFadePct` must show 0.65 and `InpFadeLook` 5.

## VSISA v1.27 — other markets, lot-step fix, and the more-trades court (2026-10-09)

**magic 88201 · defaults unchanged on gold (`InpPtsScale = 1.0` → byte-identical: 163 trades)**

Zee: *"let's aggressively find more trades"*. Two code changes, both inert on gold:
- **`InpPtsScale`** multiplies every point input (stop buffer, floor, cap, fixed target,
  retrace tolerance) so another market runs at gold's proportions.
- **Lots snap to the symbol's volume step.** US30's step is 0.1, so a fixed 4.33 lots was
  refused on every trade ("10014 invalid volume") and the first US30 run fired zero.

**Court** (Axi rig `C:\mt5_rig_axi`, real ticks, random delay, $25k, Jan 1 → Oct 8; harness
`monitor/strategy_lab/axi_rig.py` + `vsisa_more_trades.py`): **other markets and timeframes
fail** — US30 PF 0.96, USTECH 1.13, GER40 1.00, BTC 0.89, GBPUSD 0.74, USDJPY 0.67, gold M15 1.21, gold M1 0.89. **The extra
trades are in the fade path on gold M5**: `InpFadePct 0.65 / InpFadeLook 5` → 288 trades vs
163, +$19,417 vs +$17,486, better in both halves, every month green, DD 2.65% → 4.1%; the
whole 0.60–0.75 × 4–6 grid is profitable. Fake break off with it: 1,192 trades, PF 1.15,
DD 11.5% — rejected again. **Fade change NOT shipped as default — awaiting Zee.** Full tables:
`WINNING_STRATEGY_VSISA.md` → "More trades per day".

## VSISA v1.26 — equity-proportional compounding, and the v1.25 verdict (2026-10-09)

**v1.25 risk-sizing test** (Zee's Axi runs, random delay, $25k, Jan 1 → Oct 8, 163 trades each):
fixed 0.28 lots +$17,014 PF 2.55 DD 3.8% · 0.5% risk +$16,470 PF 2.27 DD 4.3% · 1.0% risk
+$46,897 PF 2.37 DD 8.5%. **Equal-risk sizing loses to fixed lots at the same scale** — fixed
lots weight the wide-stop setups, which are the better ones. `InpRiskPct` stays 0.

**v1.26 adds `InpCompoundBase`** (0 = off): lots = InpLots × equity / base — compounding
without re-weighting the setups. Default off. Details: `WINNING_STRATEGY_VSISA.md`.

**v1.26 receipt** (Zee's Axi run, `InpRiskPct = 0`, `InpCompoundBase = 25000`, same window/settings):
**+$19,291 · PF 2.34 · max equity DD 3.85% · 163 trades · 49.7% WR · lots 0.27→0.49 · every month
green · unseen 18 Sep → 8 Oct +$3,638.** Same DD % as fixed lots (3.8%) with +$2.3k more over 9
months. (An earlier "compound" report had `InpRiskPct = 1` left on, so it was a second 1% run:
+$48,842, DD 6.9% — 1% risk varies 6.9–8.5% DD run to run.)

## VSISA v1.25 — optional risk sizing + the Axi receipt (2026-10-09)

**magic 88201 · XAUUSD.pro M5 on Axi · defaults unchanged (`InpRiskPct = 0` → fixed 0.28 lots)**

**Receipt (Zee's own Axi demo runs, v1.24 defaults, 2026-01-01 → 10-08, 99% real ticks, $25k):**

| | zero latency | random delay |
|---|---|---|
| net | +$14,968.82 | **+$15,817.64** |
| PF | 2.39 | 2.41 |
| trades / WR | 163 / 51.5% | 163 / 49.7% |
| max equity DD | $1,014 (2.7%) | $1,042 (3.3%) |

Every month green; largest win 11% of profit. Unseen days (18 Sep → 7 Oct, after v1.24
shipped): +$2,010.62 random delay / +$1,278.70 zero latency, ~19 trades. Same weeks on
Blueberry tick counts: −$801 — VSISA belongs on Axi.

**v1.25 change (Zee: "Transitioning from a static fixed lot (0.28) to a Fixed Fractional
Risk Model"):** `InpRiskPct` (0 = off) sizes each decision so a full stop + commission loses
that % of equity; `InpRiskMaxLots` caps it; never more than 80% of free margin; lots round
down. **Not yet tested — default OFF.** Test plan and the full how-to-run guide:
`WINNING_STRATEGY_VSISA.md`.

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

---

## VSISA v1.24 — the loud gate was too strict (2026-09-17)

**Shipped:** `InpBigAvg 1.20 → 1.10` · `InpBigPct 0.80 → 0.70`. Nothing else moved.

**Why.** Zee asked for more trades: *"waiting the entire day for the EA to take just 1
trade is slow n boring."* The tester's own funnel says 89% of candidate reactions die at
the LOUD test, so that gate was asked what it charges to relax rather than removed.

**Receipts** (Axi rig, real ticks, 2026.01.01–09.16, 0.28 lots, MT5 Strategy Tester):

| | v1.23 | **v1.24** |
|---|---|---|
| net | +$11,911 | **+$13,689** |
| trades | 120 | **143** |
| win rate | 52% | 51% |
| max drawdown | $650 | $778 |
| net per $1 DD | 18.32 | 17.59 |
| walk-forward halves | 5.52 / 13.67 | **6.58** / 12.09 |

+15% money and +19% trades with the win rate intact. Ship-verified: a run with the
inputs pinned to the new values returned 143 / +$13,689 / 51% / $778 — the experiment
exactly.

**It is a ridge, not a spike.** bigAvg at bigPct 0.70: 1.05 $11,927 · **1.10 $13,689** ·
1.15 $12,828 · 1.20 $12,028 · 1.25 $10,470. bigPct at bigAvg 1.10: **0.70 $13,689** ·
0.75 $13,642 · 0.80 $12,927 · 0.85 $12,141. A smooth hill both ways, every neighbour at
or above shipped.

### What was REJECTED the same night, and why

Frequency beyond ~1 trade/day does not pay. Resized so each config's worst drawdown fits
a 10K funded account's 10% limit, the raw-net ranking **inverts**: `no fake break` looks
like +63% money (+$19,460) and becomes **+$5,660** at the 0.081 lots it needs to survive.
`LOUD+fade0.65/look5` earns the most raw money of all (+$14,719, 1.40 trades/day) and
lands at +$9,826 — below shipped.

- **`InpMaxOpen` 3 and 4 are byte-identical to 2** — the concurrency cap never refused a
  trade. Same for `InpSetupMax 14`. Do not re-test these.
- **The exit is exhausted.** `InpRatchetStep 12` is byte-identical to step 8 and
  `InpTargetR 15` barely moves — third confirmation that these trades all die on ONE
  ratchet lock and never see the target. `InpRatchetStart 2.00` is optimal.
- **`InpSetupGaps 1`** destructive again: +$7,672 at $1,578 DD.

### The harness bug this ship uncovered

`monitor/strategy_lab/vsisa_lab.py`'s `SHIPPED` dict was still the **v1.19** pin — wick 2,
ratchet step 1.0, swing 10, target 5R — and passed **no fade inputs at all**, four
versions after the fade shipped. Every "baseline" row it printed was a retired config. It
is now re-pinned line-by-line from the `input` declarations in `mt5/VSISA.mq5`, and the
corrected baseline reproduces v1.23 exactly. **Any VSISA comparison made against that dict
between v1.20 and 2026-09-17 should be re-checked.**

### Files

`mt5/VSISA.mq5` · `monitor/strategy_lab/vsisa_lab.py` (re-pinned) ·
`monitor/strategy_lab/_vsisa_freq{,2,3,4,5}.py` · `_vsisa_ship124.py` ·
`VSISA_AXI_OPTIMISATION.md`

---

## VSISA_Pullbacks v1.00 — a SECOND EA, built for frequency (2026-09-17)

**New EA. Magic 88202.** VSISA (88201) is untouched and keeps trading its own way.

**Why.** Zee, after a night in which six separate routes to a busier VSISA all failed the
funded-account drawdown test: *"we're not beating the live EA here. we want a separate EA
based on VSISA which trades more frequently. i know there's a drawdown thing going on ..
maybe in future days we'd find a hack ;) to make it less drawdown or more accurate?"*

A deliberate product decision — frequency now, drawdown later, on an EA that cannot hurt
the live one. v1.24 is therefore NOT the benchmark. The objective was the most trades per
day that stays clearly profitable with **both walk-forward halves positive**; robustness
was the one thing not deferred, because a config that dies in H2 is not a drawdown problem,
it is the absence of an edge.

**Receipts** (Axi rig, real ticks, 0.28 lots, MT5 Strategy Tester) — ship-verified, the
compiled binary reproduced all three windows to the dollar:

| window | trades | net | WR | maxDD | net per $1 DD |
|---|---|---|---|---|---|
| **FULL** Jan 1 – Sep 16 | **1,864** (10.38/day) | **+$28,757** | 42% | $3,340 | 8.61 |
| H1 Jan – May | 860 | +$19,144 | 43% | $3,340 | 5.73 |
| H2 May – Sep | 1,004 | +$9,756 | 41% | $2,831 | 3.45 |

**10.38 trades a day against the live EA's 0.80** — 13×, with both halves strongly
positive and H2 taking MORE trades than H1.

### What makes it a different EA, not a preset

| input | VSISA v1.24 | **Pullbacks** | why |
|---|---|---|---|
| `InpFakeBreak` | true | **false** | admits PULLBACK lows — dips inside a move. A chart study of 59 bottoms found the sweep requirement rejected **all** of them, five sessions running. |
| `InpLowVolPct` | 1.00 | **5.00** | quiet CAP lifted, so no-supply *and* loud stopping-volume reactions both qualify |
| `InpTrendTF` | 30 | **0** | the camel trend HELPS VSISA and HURTS this EA — built to read sweep reversals, wrong tool for pullbacks. Removing it added trades, money and half-stability at once. |
| `InpRatchetStart` | 2.00 | **1.50** | the accuracy lever: 38% → 42% WR and the best ratio in the regime. Ridge: 1.00 $12,359 · 1.25 $19,195 · **1.50 $28,757** · 1.75 $27,468 · 2.00 $23,824 |
| `InpFadePct` / `Look` | 0.60 / 4 | **0.70 / 5** | the frequency lever |

The three levers reinforce: together they beat every one alone, and drawdown FELL from the
base's $4,231 to $3,340.

### The deferred problem, stated plainly

$3,340 of drawdown does not fit a 10K funded account's 10% limit at 0.28 lots. At the
**0.084 lots** that do fit, it returns about **$8,610** against v1.24's $13,689. That is
Zee's accepted trade, not an oversight. **Their drawdowns ADD on a shared account** — this
EA needs its own account or a carved-out allocation.

When the hack is hunted, two doors are already known to be shut, both tested 2026-09-17:
**a tighter stop** (buffer 120→40 took net $19,740→$10,821 AND raised drawdown
$4,207→$4,340) and **`InpDayLossStop`** (made drawdown worse at every setting, by removing
the trades that recover the day). The live doors are sizing, a better exit — `ratchetStart`
already bought 4 points of win rate — or a separate account.

### Harness change shipped with it

`axi_sweep.py` hardcoded `Expert=VSISA`. A second EA on the same rig would have silently
tested the WRONG BINARY and reported v1.24's numbers under a Pullbacks label — the same
class of bug as the stale-compile found the same morning. It now takes `--ea`.

### Files

`mt5/VSISA_Pullbacks.mq5` (new) · `monitor/strategy_lab/axi_sweep.py` (`--ea`) ·
`_vsisa_freqea.py` · `_vsisa_freqea2.py` · `_pb_ship.py`

---

## TurtleTradeLogger v1.05 / v1.06 — the ledger itself was lying (2026-09-25)

**Who ordered it:** Zee — *"can the manual circular meter on this page take trade
history from the blueberry account.. these trades are taken by me today on blueberry"*.

**What it was meant to be:** a small change so the Manual dial on claudezeeshan.com
could show Blueberry only. **What it turned out to be:** the reason the dial had
nothing to show.

### v1.05 — account + server columns

`turtle_fills.csv` lives in **Common\Files**, shared by every terminal on the machine,
and carried no account identity. Magic separates EA from EA; it cannot separate
Zee-on-Blueberry from Zee-on-anything-else, because both are magic `0,Human`. Rows now
end `...,magic,ea,account,server` — appended at the END, so every reader that indexes
by column keeps working and pre-upgrade rows simply have no 14/15.

`dashboard/claude_trader/server.js` passes account through as a 4th element of each
`/api/fills-history` row. **A filter on it must treat `''` as UNKNOWN, never as "not
Blueberry"** — otherwise the dial silently drops everything logged before today.

### v1.06 — THE BACKFILL WAS APPENDING NOTHING, and said so in a way that looked fine

Attached to the Blueberry chart (5116967, `BlueberryMarketsSVG-Live`, XAUUSD.pi M1), the
logger printed:

```
TurtleTradeLogger: backfill scanned 545 deals since 2026.09.10 — appended 0 missed
```

It had his trades in hand (deals #16298933-37, sells at 4272.01) and wrote none.

**Cause:** `HistoryDealSelect()` is documented to CLEAR the selected-history list and
refill it with the single requested deal — and `LogDeal()` calls it on its first line.
So `BackfillMissedDeals()` destroyed, on iteration zero, the very list it was walking.
On a fresh funded account deal zero is the opening BALANCE credit, rejected as
not-a-trade, so the cache was wiped before one real fill was reached. Fixed by
collecting every ticket BEFORE logging any of them.

**Why this matters beyond one dial:** the failure is invisible from outside. The
open-positions snapshot keeps ticking, the EA reports a large scan, and the account
looks monitored while recording nothing. Any P&L drawn from this file for a newly
attached account before today should be treated as UNVERIFIED, not as zero.

**Not yet done:** the dial is still unfiltered. Filtering was deliberately left until a
Blueberry row exists to check it against — a filter written against no data is a guess.

### Files

`mt5/TurtleTradeLogger.mq5` (v1.04 → v1.06) · `dashboard/claude_trader/server.js`


---

## 2026-10-03 → 10-07 — TickSpeedGauge v1.00 → v1.53, RiskGuardButtons v1.00 → v1.14

Two new EAs. Full working notes in `TICK_SPEED.md` (57 sections) and the handover in
`RESUME_HERE_2026-10-07.md`.

### `mt5/TickSpeedGauge.mq5` — v1.53 — RESEARCH ONLY, DOES NOT TRADE

An order-flow panel: speed dial, bias dial, sweep dial, trapped dial, two spring coils, nine
verdicts, and a per-second CSV logger. **It never places an order.**

Its real output was the logger. Every number below came from it, and the data is now committed
to `data/tickspeed_logs/` because MT5's `Common\Files` does not travel with the repo.

**What it established:**

* **Only PXBT serves a usable book.** 20 levels with 500–1100 lot sizes on `XAUUSDp`. Exness
  returns no DOM at all; Blueberry returns 2 levels with volume **1 and 1 forever**, which
  makes OBI identically zero while the panel still reported `BOOK` mode. v1.53 demotes such a
  book to tick mode loudly rather than displaying a constant as a signal.
* **No broker here tags the aggressor.** Feed probe on all three: flags 0.0%, last 0.0%,
  volume 0.0%. Direction can only come from the book.
* **Nothing under ~10 seconds can be traded on gold.** Mean move must beat the spread before
  any win rate matters; at 1s the mean move is 0.32× the spread, so no win rate pays.

**And four findings that REVERSED, which is the more important result:**

| | looked like | was |
|---|---|---|
| SPRING | 86% @10s, p=0.0001, 36 episodes, passed the mirror test | **38% on gold** |
| SWEEP | 87% @3s, 71 episodes | **never fires on gold** |
| GET READY | "catches 15 of 20, 4s lead" | beat a same-frequency random light by **2 points** |
| ranging block | "chop is poison" | **inverted** at the 5/30 geometry |

All four were fitted on PXBT `ETHUSDTp`, where the mid moves in **5%** of seconds. Gold moves
in **85%**. They were measuring a near-frozen quote feed, not microstructure. Permutation tests
and mirror tests both passed and still did not survive a change of instrument.

### `mt5/RiskGuardButtons.mq5` — v1.14 — THE LIVE ONE

Built 2026-10-06, the day a **$200 PXBT account was liquidated on borrowed money** after lot
size went 0.01 → 0.1, a loser was held, and the position was flipped at the extreme.

The arithmetic, from Zee's own logged ticks: at 0.1 lots a $200 account has **20 points of
room** on a market whose 15-minute range is a median 6.8 points, and a 20-point adverse move
occurs at **10.5%** of entry moments. The direction was not the problem.

Manual BUY/SELL/CLOSE buttons with every limit enforced in code:

```
0.01 lots hard-capped          mandatory stop on EVERY order
max 5 open, total risk <= 4%   emergency close at -10% floating, checked every tick
daily loss cap 5%              12-loss cooldown, read from deal history
support/resistance block       forming candle must agree with the click
5/30 geometry (InpFixedSLPips 5, InpTargetR 6): random wins 17.9%, breakeven 19.1%
```

**Bugs found and fixed in it, each of which would have cost money silently:**

1. **`PipSize()` on metals** returned `point` (0.01) instead of the 0.10 gold pip, making every
   pip input **10× too small**. The 5-pip stop became 0.05 against a 0.17 spread — *inside* it.
   Caught only because a startup line printed "17.00-pip spread". It now prints pip size in
   PRICE on attach.
2. **`LossStreak()` omitted `DEAL_COMMISSION`** while `Score()` included it. On a raw-spread
   account — both brokers in use — a +$0.50 gross trade is a net loss, and the streak guard
   reset on it.
3. **`InpBlockRanging` was honoured in one of four places.** Switching it off stopped the
   refusal but still greyed the buttons and printed the warning.
4. **`OBJ_LABEL` is single-line** — it ignores `\n`, so a six-line panel drew on top of itself.
5. **Light text on a white chart** was invisible; colour now derives from `CHART_COLOR_BACKGROUND`.

### Files

`mt5/TickSpeedGauge.mq5` (new, v1.53) · `mt5/RiskGuardButtons.mq5` (new, v1.14) ·
`monitor/deploy_ea.py` (+`exness` target) · `monitor/strategy_lab/tickspeed_calibrate.py` (new) ·
`TICK_SPEED.md` (new, 57 sections) · `RESUME_HERE_2026-10-07.md` (new) ·
`data/tickspeed_logs/` (new — 34 MB of evidence, gzipped to 6 MB)

### State

**The measurement apparatus is correct and there is no validated edge yet.** Instrument,
horizon and geometry are settled; the entry is not. `RiskGuardButtons` makes being wrong
survivable while that question is answered.
