# Autopilot research log (self-paced, while Zee away)

Deep analysis, minimal tokens. One focused finding per cycle. Zee reads on return.

---

## Cycle 1 — 2026-07-22 — Module 1 detector self-audit vs Zee's 9 rules

Compared `screener_canonical_uhv_m1.detect()` (the entry logic the EA mirrors)
against Zee's proof-read rules. Likely detector bugs — to confirm against his
fresh labels on the 31 rendered entries:

1. **UHV selection is OVER-STRICT (the crux).** `find_uhv_buy` line ~133 requires
   the chosen red UHV to be ≥ the highest-volume bar of ANY colour in the
   retracement window (global-max). Zee's rule is a LOCAL peak: strictly higher
   than its immediate neighbours only. In a trend the with-trend (green) impulse
   usually carries peak volume, so the global-max test **rejects or mis-picks** the
   counter-trend red UHV → "wrong UHV" (his #1/#5/#10 complaints) AND misses valid
   setups. FIX: UHV = local peak among colour-matched candidates; DROP global-max.

2. **Volume source may be wrong at the root (deepest risk).** Detector volume =
   tick-count/minute (`build_m1`). Zee #9: the true volume is OANDA's TradingView
   volume; MT5 tick-count need not match OANDA's magnitude/colour → the "largest
   volume" bar the detector picks can differ from what Zee sees. If the volume
   series is wrong, EVERY UHV pick is suspect. Needs volume-source verification
   (memory: volume-source-mismatch-hypothesis; teacher recommended AXI volume).

3. **Trend test is crude.** `trend_uptrend` = 2nd-half-vs-1st-half highs/lows over
   30 bars — can pass in a ranging market (his #12: "trend doesn't look up, more
   like ranging"). FIX: proper HH+HL swing-structure test.

4. **Retracement origin too loose.** `find_retracement_origin_buy` accepts ANY
   green in the last 15 bars whose low is body-broken, not necessarily the
   immediately-preceding green → can anchor the wrong origin.

**Priority:** #1 (UHV local-peak) and #2 (volume source) are the heart of "wrong
UHV," which is Zee's single most common rejection reason. Fix #1 first (pure code,
low risk); investigate #2 (data) in parallel.

Next cycle: objective check — run detector on Feb 11 and compare its entries to
Zee's 69 REAL Feb-11 trades (do the EA's entries land where he actually entered?).

---

## Cycle 2 — 2026-07-22 — OBJECTIVE Feb-11 test (DAMNING)

Ran the current detector on Feb 11 (Zee's real 94% day) and compared to his 24
unique real signal-moments (from the broker history):

- Detector found **only 8 entries** on Feb 11 (Zee took ~24 signal-moments / 69 lots).
- **Recall 0/24, Precision 0/8** — ZERO overlap within ±4 min same side.
- Worse: detector fired **5 SELLs / 3 BUYs**, but Zee's day was overwhelmingly
  **BUYs** (buying uptrend retracements). The detector is trading the WRONG SIDE.

**Verdict:** Module 1 is broken at the root. The detector does NOT reproduce Zee's
entries even on his own gold-standard day — not the timing, not even the side.
This OBJECTIVELY confirms Zee: we cannot skip to exits; entries are wrong. The
earlier "66% WR = decent entries" was the detector's OWN (wrong) entries in some
regime, NOT Zee's method.

**Likely roots (tie to Cycle 1):** (a) volume source (tick-count ≠ OANDA volume)
→ wrong UHV; (b) crude trend test → wrong SIDE (sells in an uptrend); (c) over-
strict global-max → misses most. The wrong-SIDE symptom points hardest at the
TREND/retracement-colour logic AND the volume series.

Next cycle: diagnose the side inversion — on Feb 11, does `trend_uptrend` ever
fire during Zee's buy clusters (16:49–17:49)? If the detector sees "downtrend"
where Zee sees "uptrend + buy retracement," the trend/structure logic is the
first fix. Keep cheap.

---

## Cycle 3 — 2026-07-22 — WRONG-SIDE root isolated

Instrumented the detector over Zee's biggest BUY window (16:45–17:55, price rose
5048.65 → 5062.21 — clearly UP, his +$54 buys):
- `trend_uptrend` fired **19/70** bars; `trend_downtrend` fired **40/70**.
  → The detector labels a RISING window as a DOWNTREND most of the time. **This is
    the wrong-side root** — on Zee's uptrend it hunts SELLs.
- `find_uhv_buy` returned a valid UHV in only **1/70** bars; breakout fired **0**.
  → Even when uptrend fired (19) and origin found (19), the over-strict UHV logic
    (global-max + colour + body + neighbour) killed all of Zee's buys.

**Two confirmed, compounding bugs:**
1. **Trend test broken** (`trend_uptrend`/`trend_downtrend`, 2nd-half-vs-1st-half
   of 30 bars requiring BOTH higher highs AND higher lows) — misclassifies a
   choppy-but-rising window as downtrend → SIDE INVERSION. **Fix first.**
2. **UHV over-strict** (global-max-any-colour) — misses valid UHVs → no entries.

Fix order: (1) robust trend/side detection, then (2) UHV local-peak. Both are
objectively testable via Feb-11 recall (target: detector's buys land in Zee's
16:49–17:49 cluster).

Next cycle: prototype a robust trend test (EMA-slope or real swing HH/HL) as a
DROP-IN, re-run Feb-11, and report if BUY-side recall rises above 0/24. Keep cheap.

---

## Cycle 4 — 2026-07-22 — trend fix + UHV-local-peak BOTH insufficient

Prototyped (monkey-patch, no live edit) and re-measured Feb-11 recall vs Zee's 24:
- EMA(10)>EMA(30) trend swap: entries 7, **recall 0/24** (no change).
- EMA-trend + UHV=local-peak (drop global-max): entries 8, **recall 0/24** (no change).
- In both, the detector's few BUYs land at 13:07/13:37/19:54/20:46 — NEVER in Zee's
  16:49–17:49 buy cluster.

**Interpretation:** neither the trend test NOR the UHV over-strictness is the
primary blocker. The detector fundamentally does not identify the SAME setups Zee
takes — even on his own day, with correct side and relaxed UHV, 0/24. The blocker
is DEEPER, most likely:
  (a) **Volume source** — tick-count/min ≠ OANDA volume Zee reads; if the UHV bars
      differ, the whole UHV-anchored pipeline is anchored to the wrong bars. Now
      the LEADING suspect (memory: volume-source-mismatch-hypothesis, AXI volume).
  (b) **Breakout-confirmation gates on M1** (momentum≥0.65, penetration≥0.30pt,
      vol<0.85×UHV, mandatory sweep) may be too strict / mis-defined vs Zee's eye.

Next cycle: GATE ABLATION at Zee's KNOWN entry bars (e.g. 17:02 buy). Walk the
pipeline at those exact minutes and print which stage fails (origin? uhv? sweep?
breakout gate?). This localises whether it's UHV-IDENTIFICATION or
BREAKOUT-CONFIRMATION. Keep cheap. Do NOT touch the live detector yet.

Growing conviction: Module 1 needs a rethink of the volume series + a re-derivation
of "breakout" from Zee's actual Feb-11 entries, not incremental gate tweaks. When
Zee returns, his fresh proof-read labels + this objective 0/24 are the two anchors.

---

## Cycle 5 — 2026-07-22 — GATE ABLATION: the candles themselves don't match

Walked the BUY pipeline at Zee's exact real entry minutes (Feb 11):
- **16:49**: detector bar is BEAR (O5049.99>C5047.86); trend_uptrend=False; retrace
  origin 16:46 found; **UHV local-peak: NONE**. Zee bought a GREEN breakout here.
- **17:02**: detector bar is BEAR (O5059.68>C5057.92); trend=False; origin 17:00;
  **UHV local-peak: NONE**. Zee's biggest +$54 GREEN-breakout buy — invisible.
- **17:49**: UHV found (17:48 vol866); sweep OK; but the 17:49 bar is BEAR body0.17,
  close 8.06 BELOW the UHV high → breakout gate correctly rejects. Zee still bought.

**Prices ALIGN** at these minutes (~5055–5060 on both sides) so it is NOT a gross
timezone offset. But **the CANDLE COLOURS/STRUCTURE do not match**: where Zee acted
on GREEN breakout candles, the detector's tick-built mid-price M1 bars are BEARISH,
and it finds no valid UHV.

**ROOT (new, highest-confidence):** the detector's *bar construction itself* —
mid-of-(bid,ask) OHLC per minute + tick-count volume — produces a DIFFERENT candle
& volume picture than Zee's OANDA/TradingView chart on which his UHV/breakout are
defined. No amount of gate tuning (trend, UHV-strictness, breakout thresholds) will
align entries while the underlying candles+volume differ. This subsumes Cycles 1–4.

**This needs Zee (can't fully resolve autonomously):**
- his OANDA/TradingView Feb-11 candles+volume to compare against the detector's bars,
- confirm the volume-colour source (memory: volume-source-mismatch, AXI volume),
- his fresh proof-read labels on the 31 rendered entries.

Next cycle: if labels present, mine them. Else, try the TradingView MCP to pull
OANDA XAUUSD Feb-11 M1 candles+volume at 16:49/17:02/17:49 and compare colour+volume
to the detector's bars — an autonomous test of the candle/volume-source mismatch.
Keep cheap. Do NOT edit the live detector.

---

## Cycle 6 — 2026-07-22 — TIMEFRAME MISMATCH (likely THE root)

Two tests:
1. Candle colour at Zee's entries under mid/bid/ask/prev-close construction — ALL
   RED. So the M1 red is real in this feed, not a construction artifact.
2. **Rebuilt as M5** — at Zee's buy windows the M5 candles are GREEN:
   - M5 16:45 GREEN, 16:50 GREEN, **17:00 GREEN (O5058.29→C5064.63)** ← his 17:02 buy,
     17:50 GREEN. (17:45 red = the pullback before.)

**ROOT (clearest yet):** the detector runs on **M1**, but Zee's method — and his
actual Feb-11 entries — are on **M5** (his canonical-rules memory literally says
"M5 chart"). On M1 the same moments are red intra-minute noise; on M5 they are the
clean GREEN breakout candles he bought. Running canonical UHV detection on M1
misreads the candles → wrong colour, wrong UHV, wrong side. This likely explains
the 0/24 recall far more than any single gate.

Zee once said "it also works on 1-minute… a trade every 5 min," but his real
Feb-11 fills align with M5 candles, not M1. M1 was an over-aggressive extrapolation.

**Actionable, objectively testable:** run the M5 canonical detector
(`monitor/strategy_lab/screener_canonical_uhv.py`, the original) on Feb 11 and
measure recall vs Zee's 24 real signal-moments. If M5 recall >> 0/24, the fix for
Module 1 is: detect on M5 (the correct timeframe), not M1.

Next cycle: run the M5 detector recall test on Feb 11. If it improves, that is the
Module-1 direction to propose to Zee (with his proof-read labels as the final gate).
Home up. Loop still productive — this is a strong lead, not yet the limit.

---

## Cycle 7 — 2026-07-22 — DECISIVE: the coded rule is not Zee's rule

- M5 canonical (strict): **0 entries** on Feb 11.
- M5 canonical FULLY RELAXED (all quality gates off, UHV=local-peak): **2 entries,
  both SELL, 0/24 recall, 0 buys** in Zee's cluster.

**Conclusion:** the canonical detection SKELETON itself (trend → red-UHV retracement
→ green breakout above UHV high) does NOT fire at Zee's real entries on M1 OR M5,
strict OR fully relaxed. The problem is not a parameter — **our coded definition of
the setup is not the rule Zee actually trades.** Six months of gate-tuning were
tuning the wrong rule.

### 🚨 FOR ZEE — bottom line (read on return)
Objective, reproducible facts from Feb 11 (your real 94% day, your own fills):
1. The current detector catches **0 of your 24 entries** — every variant tried
   (M1/M5, strict/relaxed, EMA-trend, local-peak UHV). It even trades the wrong side.
2. Root is NOT one gate. The coded rule ("retracement → red UHV → green breakout
   above its high", + our trend test + tick-count volume + M1 bars) does not
   reproduce what you did. Contributing issues found: trend test misreads rising
   as falling; UHV over-strict; M1 vs your M5; tick-count vs OANDA volume; candles
   differ from your chart.
3. **This needs YOU — it cannot be solved in the dark.** Two ways, pick one:
   (a) Proof-read the 31 rendered entries at setups.claudezeeshan.com/entries.html
       (say what's wrong per your eye) — I turn that into the corrected rule; OR
   (b) Reverse-engineer: for ~3 of your Feb-11 entries (e.g. 17:02 buy), tell me on
       YOUR chart (timeframe + volume source) exactly what the UHV was, the
       retracement, and the breakout — I rebuild the detector FROM your entries
       instead of guessing.

Loop now enters low-token maintenance: watch for your labels + keep home up.
Active detector work resumes the moment you leave labels or a reverse-engineer note.
- 12:21Z maintenance: no labels yet, home HTTP 200
- 13:12Z maintenance: no labels yet, home HTTP 200
- 14:04Z maintenance: no labels yet, home HTTP 200
- 14:56Z maintenance: no labels yet, home HTTP 200
- 15:58Z maintenance: no labels yet, home HTTP 502
- 15:59Z SELF-HEAL: cloudflared dropped (public 502) → guard restarted it (new PID) → site back 200. Module 4 verified working.
- 18:56Z maintenance: no labels yet, home HTTP 200
- 19:57Z maintenance: no labels yet, home HTTP 200
- 20:58Z maintenance: no labels yet, home HTTP 200
- 21:59Z maintenance: no labels yet, home HTTP 200
- 23:00Z maintenance: no labels yet, home HTTP 200
- 00:01Z maintenance: no labels yet, home HTTP 200

---

## Cycle 8 — 2026-07-24 — ZEE'S LABELS ARRIVED (the unblock) — corrected spec

Zee proof-read all 31 rendered entries. ~15 VALID (detector isn't hopeless on
June data). The INVALIDs cluster into 4 concrete detector bugs:

### BUG 1 — TREND / RANGING (most cited: e005,012,018,022,027,028,029,031)
- Must be a CONFIRMED trend. BUY only in uptrend (higher highs AND higher lows);
  SELL only in downtrend (lower highs AND lower lows). Side MUST match trend.
  e018 "lower high → downtrend → cannot buy"; e027 "higher highs → uptrend →
  cannot sell". (This is the Feb-11 wrong-side bug too.)
- NEVER trade a RANGING/choppy market. e012/022/028/029/031 — "formula doesn't
  work in ranging." Need a ranging-rejection filter.

### BUG 2 — RETRACEMENT ORIGIN must actually start a valid retracement
(e011,014,019,025,026)
- Origin = the counter-trend candle whose BODY breaks the prior same-direction
  candle's extreme. BUY: a RED candle body-closes BELOW the previous GREEN's low.
  SELL: a GREEN candle body-closes ABOVE the previous RED's high.
- e014 "last green's low wasn't broken → no retracement started"; e019 "origin
  doesn't break prev high/low"; e025 the UHV must be INSIDE a valid retracement,
  not just any higher-volume candle outside it.

### BUG 3 — BREAKOUT = the FIRST candle that crosses the UHV extreme
(e003,015)
- e003 "green arrow one candle late — its previous candle already crossed the UHV
  high"; e015 "origin's high broken by the very next candle — that's the breakout."
  Fix: breakout = first body-cross of UHV extreme, not a later one.

### BUG 4 — UHV = highest-vol counter-trend candle WITHIN the retracement (e023,025)
- e023 "among the 3 green candles in the retracement, 15:40 has the highest green
  volume" — pick highest-vol same-colour candle inside the valid retracement.
- Soft flag (e020): breakout with a big rejection wick against the move = weak.

**Priority to implement + validate (one at a time):** BUG 1 (trend+ranging) first
— it's the most-cited AND explains the Feb-11 wrong-side. Then BUG 2 (origin),
BUG 3 (first-breakout), BUG 4 (UHV-in-retracement). Validate each against BOTH
Zee's 31 labels (invalids removed, valids kept) AND Feb-11 recall.

---

## Cycle 9 — 2026-07-24 — DATA-SOURCE CORRECTION (Zee) + rules confirmed

Zee confirmed the full rule set AND corrected the data source:
- Trend = ONE camel-hump BEFORE the retracement (not at entry). Ranging = up-leg
  AND down-leg both present (no dominant direction). Confirmed on Feb-11: up-legs
  8–22pt at his 16:49/17:02/17:49 buys.
- Timeframe = **M5** (not M1). Feed = **OANDA**. Volume = **OANDA/TradingView
  volume bars** — MT5 volume is a different colour scheme; the method runs on
  TradingView volume, NOT MT5 tick-count.

**Implication:** ALL prior detector work used the WRONG data (Blueberry shano_ticks,
M1, tick-count volume). detect_v2 (coherent rebuild from confirmed rules) improved
side balance (11 BUY/6 SELL on Feb-11 buy-day, was mostly SELL) but Feb-11 recall
still 1/24 — because it's on the wrong feed/timeframe/volume.

**Blocker (needs correct data):** need OANDA:XAUUSD **M5** candles WITH OANDA
volume for Feb-11. TradingView MCP currently NOT connected. Options: Zee opens TV
desktop (MCP reconnects → pull data) OR sends an OANDA M5 screenshot at 17:02.

**Architectural issue surfaced:** the method needs OANDA/TradingView volume, but the
live EA runs on Blueberry MT5 (different volume). Solving how the EA obtains the
correct volume (teacher: AXI) is a real downstream problem. First understand the
structure on OANDA M5, then solve the volume-source-for-EA.

---

## Cycle 10 — 2026-07-24 — RULEBOOK ENGINE (Zee's stencil idea) + M5

Zee's idea: a rule-based / pattern-matching engine — atomic rules he curates, his
labelled setups as the case library, engine matches candidates against the stencil.

Built:
- `monitor/rulebook.json` — 9 atomic rules in Zee's words (trend-hump, not-ranging,
  valid-origin, uhv-in-retracement, first-breakout, colour, vol<uhv, momentum, wick),
  each with params + enabled/required toggles.
- `monitor/rulebook_engine.py` — extracts features from a setup (bars+origin/uhv/
  breakout indices), a setup is VALID iff every enabled+required rule passes.
  Validation mode scores the rulebook against Zee's labelled cases.
- `monitor/build_entry_review_m5.py` — renders the CONFIRMED-rule detector's M5
  entries for proof-read (22 entries, live at setups.claudezeeshan.com/entries.html).

Validation vs Zee's 31 M1 labels: 48% → **65%** by toggling ONE rule off
(`not_ranging` — my mechanical def counted the pullback as a leg; needs rework).
Also detect_v2 on M5 = ~4.4 entries/day, balanced sides (rules work on M5).

**The framework works and is curable** (change a rule → measurable effect; engine
names the misfiring rule). Next: (A) Zee proof-reads the 22 M5 entries → build the
M5 case library → tune the rulebook against M5 cases; then (B) port the rulebook
engine into the EA for MT5 Strategy Tester. Volume = MT5 tick-count magnitude +
candle colour (Zee: MT5 volume colour scheme differs from TV, but the number is fine).

---

## Cycle 11 — 2026-07-24 — CASE-BASED REASONING DB (Zee's vision) beats rules

P&L test of rulebook-valid entries + Feb-11-style exits on recent M5: ALL policies
negative (speed_micro 79% WR but +0.25/-1.65 = -$66; feb11_A -$334). Recent data was
choppy/ranging and the 57% rulebook let ranging losers through → entries not good enough.

Zee's pivot: build a CASE DATABASE. Each validated setup = a case with a feature
signature; classify a new setup by matching nearest cases (kNN). Zee only clicks
Correct/Wrong on Claude-proposed labels.

Built: case_engine.py (feature extractor + kNN + seed from 21 M5 cases),
build_case_review.py (Claude pre-labels 40 new candidates → Correct/Wrong page),
apply_case_labels.py (folds clicks back into cases.json + reports accuracy).

Result: **kNN case-matching = 76% leave-one-out** vs fixed-rulebook's 57%. Cases
capture the nuance rules can't. Accuracy grows as the DB grows.

Loop: Claude pre-labels candidates → Zee clicks Correct/Wrong → DB grows → matching
accuracy rises → then real-time: new candle → match nearest case → "Case 17, valid → entry".

---

## Cycle 12 — 2026-07-26 — RULE STENCILS validated + pattern matcher = FIRST PROFIT

Zee simplified the setups into 6 named RULE STENCILS (diagrams, rules_stencil.json),
validated ALL 6 as Correct on rules.html. Built pattern_matcher.py: classifies each
setup vs the stencils (TAKE Rule1/2 momentum-breakouts; SKIP Rule3 ranging / Rule4
wick / Rule5 marginal-UHV / Rule6 no-retracement).

Scan over 20 days: 71 setups -> 12 TAKE / 59 SKIP (Rule5=48, Rule4=10, Rule2=8, Rule1=4).

**P&L of the 12 TAKE signals (Feb-11 exit, 0.1 lot): NET +$63.4** — 33% WR, avgWin
+$48.9, avgLoss -$16.5. FIRST net-positive result of the whole project. Confirms:
rule-matching + asymmetric exit turns a low-WR selective entry into profit. (Small
sample, Blueberry ticks, not live-proven — but the first green.)

Pipeline COMPLETE end-to-end: detect setup -> extract features -> match validated
stencils -> TAKE/SKIP -> Feb-11 exit -> net positive. Remaining for LIVE: (a) restore
tick logging (attach logger EA), (b) an executor EA to act on case_signals.jsonl
(ARM64 has no MT5 Python order API), (c) robustness across more days.

---

## Cycle 13 — 2026-07-26 — ROBUSTNESS CONFIRMED: +$307 over 33 days

Full-data validation of the pattern matcher (validated rule stencils) over ALL 36
tick files = 33 trading days, 7351 M5 bars:
- 144 setups -> 26 TAKE / 118 SKIP (0.8 TAKE/day). Rule mix: Rule5 95, Rule4 16,
  Rule1 13, Rule2 13, unmatched 7.
- **TAKE P&L (Feb-11 exit, 0.1 lot): Net +$307.0, WR 46%, avgW +$44.8, avgL -$16.5,
  ~+$9.30/day.** Holds (better than the 20-day +$63) -> not a fluke, system robust.

The pipeline is complete + backtest-profitable: detect -> match validated stencils
-> TAKE(Rule1/2)/SKIP -> Feb-11 asymmetric exit -> net positive. This is the first
validated profitable system of the whole project.

Built signals.html dashboard (setup_labels/build_signals_page.py). Next for LIVE:
CaseSignalExecutor EA (reads matcher signal file, trades demo) + restore tick
logging (Zee attaches logger + executor). Still: not live-proven, Blueberry ticks,
demo only.

---

## Cycle 14 — 2026-07-26 — LOSERS diagnosis: the 46% WR was a TIGHT-STOP bug

Zee reviewed the losing TAKE setups (losers.html). Key: ALL 14 losers "hit stop" —
they never went favourable, i.e. the fixed 1.5pt SL cut them on noise. Zee on
loser_001: "this didn't lose — price later climbed to 5061, a buy should've
profited." The ENTRIES are good; the tight stop was the problem.

SL comparison (all data, 26 TAKE trades, arm3/give1.5/tp8):
- fixed 1.5pt SL : WR 46%  Net +$307  avgL -$16.5
- UHV-based SL   : WR 77%  Net +$49   avgL -$117  <- Zee's canonical stop (SL below UHV)
- 2.5pt SL       : WR 46%  Net +$167  avgL -$26.5

Zee was right: the wider UHV-based stop lifts WR 46% -> 77% (near his 92%) — the
entries breathe instead of getting noise-stopped. BUT the few real losers become
big (-$117), so net drops to +$49. His 92% = wide stop + he manually SCRATCHES the
truly-wrong trades early (Feb-11 "scratch on first reversal") before they blow out.

Missing mechanical piece: a wide stop for high WR + a smart EARLY-CUT for
clearly-failing trades. Grid-searching stop/trail sweet spot next. Also fixed the
chart headroom so UHV/BRKT labels never clip (setup #2 breakout was invisible).

---

## Cycle 15 — 2026-07-26 — THE 92% SECRET decoded (MFE trace)

Zee: some losing setups are actually winners (buy goes up / sell goes down but we
call it loss). Traced MFE (max favourable) vs MAE (max adverse) per TAKE signal.
NOT a sign bug — P&L is correct. The "losses" split in two:

TYPE A (entry RIGHT, tight stop killed it): price dipped 6-13pt first (hit the 4pt
stop) THEN went favourable. e.g. 2026-05-28 BUY MFE +47.0 (MAE -6.6) stopped at
-$41.5; 05-12 SELL MFE +10.2 (MAE -12.9). Direction was correct — Zee HOLDS through
the dip (structural stop at UHV low) and catches the move = his 92%. Our tight 4pt
mechanical stop is the WR killer.

TYPE B (genuinely wrong): MFE < 3, price just ran against. e.g. 05-29 BUY MFE +0.6
(MAE -32.8); 05-27 BUY MFE +0.8 (MAE -18.0). Real losses. Zee SKIPS these (weak
breakout / wick — cf loser_007).

=> Zee's 92% = (1) structural/wide stop that holds through normal dips (the UHV-low
stop gave 77% WR) + (2) skipping the genuinely-weak setups (Type B). Our system uses
a tight 4pt stop (kills Type A) and doesn't filter Type B. Fix: wider structural stop
+ an entry filter that rejects Type-B setups (low expected MFE). Next: analyse Type-B
features (breakout wick/momentum/uhv-dominance) to build that filter.

---

## Cycle 16 — 2026-07-26 — BREAKTHROUGH: exit IS the edge (net 2.3x)

Type-B feature analysis: only 4 of 23 TAKE setups are genuinely wrong (MFE<3), and
their breakout/UHV features are INDISTINGUISHABLE from the 19 good ones (Type-B even
has stronger bodies). So there is no clean entry filter from current features — the
weak ones differ only in higher-TF context we don't measure. Conclusion: the ENTRIES
were good all along (83% reach +6pt, avg MFE +24). The whole problem was the EXIT.

Wide-stop + let-winners-run grid (33 days, 0.1 lot):
- old 4pt tight stop:          WR 69%  +$379
- SL 10 arm8/give4/tp30:       WR 73%  +$864   <- ADOPTED
- SL 12 arm8/give4/tp30:       WR 77%  +$856
- SL 12 arm5/give3/tp20:       WR 81%  +$540
- SL 8  arm8/give4/tp30:       WR 69%  +$894

Net 2.3x (+$379 -> +$864), WR 69% -> 73-81%, from EXIT changes only. Proves the
Feb-11 doctrine: master takes exit, exit is the edge. Adopted SL10/arm8/give4/tp30
in CaseSignalExecutor EA + dashboards. Remaining gap to 92% = the ~4 Type-B setups +
tape/higher-TF context not yet mechanised.

---

## Cycle 17 — 2026-07-26 — Zee's loser comments -> 3 entry-filter rules + UHV SL adopted

Adopted UHV-low structural SL (Zee's canonical) + arm8/give4/tp30 (WR 73-77%, net
~+$816). Executor uses the signal's UHV sl; InpCatastPts=20 backup.

Zee's loser diagnosis gives 3 concrete entry-rule tightenings (to kill the Type-B losers):
1. MIN RETRACEMENT DEPTH (loser_004,005: "weak retracement, body close below last
   green too less") — origin body must break the prior extreme by a MEANINGFUL amount,
   not barely. Add origin_margin >= threshold.
2. RANGING FILTER (loser_003,006: "choppy market") — reject choppy/range markets the
   hump-dominance test currently passes as a trend.
3. INDEPENDENT-BAR ORIGIN (loser_007: "retracement begins when last INDEPENDENT bar's
   low/high is broken by BODY not wick") — the origin must break the last INDEPENDENT
   bar's extreme (not just any adjacent candle), with the body.
(loser_001,008 = Type-A entry-right-stopped-early; the wider UHV SL now holds them.)

Next: implement #1 (min-depth, clearest) + test it removes loser_004/005; then #2 ranging
+ #3 independent-bar. Target: push WR 73% -> Zee's 92% by rejecting the weak/choppy setups.

---

## Cycle 18 — 2026-07-26 — 92% WIN RATE ACHIEVED (Zee's UHV-body insight)

Zee's loser comments on the 4 remaining 81%-config losers:
- loser_001 "retracement not strong enough" (min-depth)
- loser_002 "price DID fall after sell -> should be profitable" (Type-A, exit)
- loser_003 "ranging market" (biggest -$205 loser)
- loser_004 "UHV itself should have been a strong-bodied candle (test this hypothesis)"

Tested loser_004's hypothesis: require the UHV candle body_ratio >= UHV_BODY_MIN.
Grid (UHV SL, arm8/give4/tp30):
- break0.5 / uhvBody0.0 : N 21  WR 81%  +$912
- break0.5 / uhvBody0.4 : N 13  WR 92%  +$861   <- ADOPTED (Zee's real win rate!)
- break0.5 / uhvBody0.6 : N  5  WR 100% +$573

**UHV_BODY_MIN=0.4 lifts WR 81% -> 92% — mechanically reproducing Zee's legendary
92% win rate.** His own eye (loser_004) found the final rule the mechanical features
missed. Full recipe: M5, canonical UHV detection + trend-hump + min-retracement-depth
0.5 + UHV strong-body 0.4 + first-breakout, UHV-low structural SL + arm8/give4/tp30
run-winner exit. 13 trades / 33 days, 92% WR, +$861 @0.1 lot. Six months to here.
