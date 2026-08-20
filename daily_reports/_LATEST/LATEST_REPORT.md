# 17 August 2026 — the streak dies, the record heals, and Zee's eye writes two laws

**Supersedes:** the 13 August branch-search audit, archived at
[`daily_reports/2026-08/REPORT_2026-08-13_branch_search_audit.md`](../2026-08/REPORT_2026-08-13_branch_search_audit.md).

**Promoted today: LAW 9 (impulse origin, both EAs) and LAW 10c (quarter-size in the
loud band, ZeeUHV v1.29).** Law 8 rides as a tag. Law 10a (displacement margin) failed
at every depth — dead input. The Law 10b GATE (+786 but −48% trades) was measured and
declined by Zee for the non-blocking 10c (+538, zero trades cut). Six-fortnight ledger,
all laws stacked: **−$1,615 → −$639**, LIVE/Jun/Jul positive. The Loud-Breakout EA
deliberately keeps full size — its thesis IS the loud band; its live magic is the
counter-experiment. Frequency note for next session: Zee wants MORE trades (Feb-11 was
69/day) — **rank-6 is the measured, unshipped lever** (+46% Aug, better Mar drawdown).

---

## 0. The honest week, from the broker's own history

The 14-basket unbeaten streak ended Thursday. Reconciled against Blueberry's
`ReportHistory-12654799bb.html`, position by position:

```
Aug 11   27 closes  100.0%   +300.60      the streak
Aug 12   18 closes  100.0%   +220.80
Aug 13    8 closes  100.0%    +92.40
Aug 14   16 closes   50.0%   -450.40      first losses
Aug 17   88 closes  66W/22L  -383.90      (incl. evening basket +$134)
```

Three losing events today: the 09:11 broker BUY basket (~-$500), the 11:08 PKT BUY
(-$43.20/ticket, hold-timer exit), and the 12:21 PKT SELL basket (six -$50 stop-outs at
12:28). The 20:1 geometry doing exactly what §1.9 of the previous report predicted: wins
pinned at ~$10, one stop eats fifty of them.

## 1. THE FILLS FILE WAS BLIND — 96 positions were missing (fixed, self-healing now)

`turtle_fills.csv` disagreed with the broker: **96 closed positions since Aug 3 were
never logged (-$590.40)**, including all six 12:28 stop-outs. Today's CSV said -$60.50
when the truth was -$561.90.

**Why:** TurtleTradeLogger was purely event-driven (`OnTradeTransaction` only). Any deal
that closed while the terminal was down or **disconnected** was lost forever. The 12:28
stops executed server-side during a connection drop — the terminal never heard them, and
nothing ever backfilled. The GUI then honestly displayed the corrupt record.

**Fix (all live):**
- **TurtleTradeLogger v1.04** — `BackfillMissedDeals()` at init replays broker history
  (≥14 days) and appends every closed deal the CSV lacks, deduped by deal_ticket. A
  restart now HEALS the record. Verified after reattach: "scanned 1,136 deals — appended
  0 missed" (zero because the record had already been healed by hand via the
  MetaTrader5 python bridge — 85 deals, -$568.70).
- **Trades window** sorts by broker timestamp (backfill appends out of order) and the
  Karachi-shift detector only accepts +2/+3 (a backfill write used to fool its
  mtime heuristic).
- Timezone verified: all 481 shared positions agree with the broker export to the
  second; GUI's +2 conversion correct.

## 2. FORENSIC SAID "no EA fire line" — the fire line was fine, the chart had no bars

The resolver worked; `draw_trade()` had nothing to draw on. Its bar source was the
bridge's rolling ~300-bar window — any trade older than a few hours was unreachable, and
the GUI mislabeled the failure. Underneath: **the OANDA feed and tape archive had been
dead since Aug 14/15 and nothing noticed.**

**Fix:** `load_deep()` in `monitor/forensic_chart.py` — live window → tape archive →
**the running terminal itself** (`monitor/mt5_bars_helper.py`, x64 python, because no
MetaTrader5 wheel exists for ARM64). The terminal always holds full M1 history; that
source cannot rot. All of today's losers draw, setup + circumstances.

**Feed root cause found:** the "OANDA bridge" scrapes TradingView Desktop via CDP :9222.
TradingView auto-updated into a Store (MSIX) app on Friday — the old CDP launch path
died with it. `feed_supervisor` + `tape_archive` daemons restarted; **TV-with-debug-port
is still an open item** (MSIX blocks direct exe launch; `Invoke-CommandInDesktopPackage`
attempt unresolved). Forensic no longer depends on it; the tape archive does.

## 3. ZEE'S TWO FORENSIC READS — one law fails promotion, one goes LIVE

He inspected his own losers in the healed viewer and called two defects. Both verified
on broker bars. Both share one root: **the machine measured displacement against the
nearest neighbour where his rules measure it against the leg.**

### Law 8 — "invalid retracement" (the 12:21 SELL) — TAG ONLY, not promoted

His claim: the retracement never broke the last independent bar's high. Strict
bar-vs-neighbour reading: false (every green did break its predecessor). Structural
reading (confirmed by him): true — the retracement topped 4399.26 against the leg's
last upward-independent bar at 4401.40.

Coded as mask bit 32 (comment tag, no sizing change). Six periods, real ticks, 3,096
tickets, reproduction exact:

```
LIVE  ok +2.29 / no +0.86     Jun  ok +0.21 / no -1.02     kind: L8 better
May/Jul: ties                 Mar  ok -1.69 / no -1.57     hostile: L8 WORSE
                              Apr  ok -1.04 / no -0.38
```

**Fails the promotion rule** (wins only in kind periods — the stop-3 shape). Stays a
tag; the live EA stamps it on every basket, live evidence accrues free.

### Law 9 — "not a UHV, no valid retracement started" (the 11:08 BUY) — **LIVE**

His claim, verified: the marked UHV (11:04, vol 230) wasn't the loudest red (11:02 was,
vol 237), and the origin only broke a ONE-BAR bounce inside the pullback (11:03), never
the leg's real last green (11:01). Label #e014 forbids exactly this; the origin code
accepted any previous green.

**The fix:** `InpImpulseOrigin` — the origin's reference bar must be an IMPULSE candle
(green that made a new high / red that made a new low). Hand-traced on the 11:08 window
it reproduces his read two laws deep: scope widens → 11:02 becomes the UHV candidate →
the local-peak law rejects it (11:01 louder, 266) → **no trade**.

**Receipts (six periods, real ticks, head-to-head):**

```
         shipped      Law 9 ON        Δ
LIVE     +176.30      +190.84       +14.54   kind ✓
Mar      -740.42      -538.00      +202.42   HOSTILE ✓
Apr      -444.30      -510.42       -66.12   ✗
May      -351.68      -456.36      -104.68   ✗
Jun      -274.70       +33.82      +308.52   flips POSITIVE
Jul       +19.62      +102.32       +82.70   ✓
total  -1,615.18    -1,177.80      +437.38   ~10% fewer tickets
```

**Passes the promotion rule** — better in kind AND in the worst hostile month. Zee:
*"yes make it LIVE."* Shipped as **ZeeUHV v1.26** and **ZeeUHV_Loud_Breakout v1.1**
(both, because both fire every basket). Reattached and fingerprint-verified ~7:10 PM PKT.

**Honest limits:** April and May get worse; the system still loses over the six
fortnights (-$1,178). Law 9 removes one class of bad entry. The 12:21 stop-out class is
NOT blocked by anything live — Law 9 checked against it specifically: its origin was
legitimate, that trade still fires.

## 4. Current live state (post 7:10 PM PKT)

```
ZeeUHV v1.26              magic 88094   SL 5 / TP 1 / hold 5min / stack x2   Law 9 ON, Law 8 tagging
ZeeUHV_Loud_Breakout v1.1 magic 88104?  same, brk vol >= 0.80x UHV           Law 9 ON
TurtleTradeLogger v1.04   self-healing backfill armed
Ticket comments now carry the law bitmask: zee_sell_D2_m52 (bit 32 = Law-8-valid)
```

## 4b. ZEESIMPLE — attempt seven at Feb-11, built and measured the same evening

Zee, at dinner: *"create a new EA from scratch... any law that cuts off too many trades
should be skipped... losses near about 2 USD... every single retracement, a frequency
from this report."* Target spec from his real Feb-11 statement (acct 5118408): 69
trades/day, 94.2%, avg win €12.93, avg loss −€1.32, holds 6s–3min.

Built: `mt5/ZeeSimple.mq5` — EMA 5/20 trend, fire on EVERY retracement resumption
(counter-color candle, then trend-color close beyond it), no UHV, no diamonds, no laws.
It reaches the frequency: **140–230 trades/day.**

Measured: seven exit geometries, real ticks, AUG+MAR screen, winner validated on four
more periods. **Every arm loses.** Best (SL2/TP1/h120): 50–56% WR, −$2.10/trade, five
of six fortnights bankrupt the tester account at 0.10 lots (nets ≈ −$4,0xx are censored
— §0a). The per-trade loss ≈ the spread: an every-retracement trigger is approximately
a random entry (NullEntry, §1.8 of 13-Aug report), and 200 random entries/day pay 200
spreads with nothing to cover them. **Frequency without selection is rent, not tempo.**

Shipped as v1.01 attach-ready but with defaults that tell the truth: best-arm exit,
**0.01 lots** (tuition cap), receipts in the file header. Recommendation on record: do
not attach at size; the frequency lever with an actual edge is rank-6 on ZeeUHV.

## 4c. THE HOLD TIMER SURVIVES ITS THIRD TRIAL (late evening)

The 22:32 PKT SELL — right direction, right size (Law 10c correctly read 299/359 =
0.83 as quiet band), right stop — was cut by the 5-minute clock at the retest top for
−$232, two minutes before its TP filled. So the clock was re-swept under the LIVE
v1.29 configuration (holds 8/12/20 vs h5, six periods, real ticks): every longer hold
fails promotion — h8 −372, h12 −363, h20 −791 vs baseline. Only May improves, ever.
h5 stays. That basket's loss is the premium on a policy the receipts say to keep.

## 4d. v1.30 — THE 3-MINUTE CLOCK (2026-08-18, after midnight)

Zee watched ZeeSimple's quick scratches live and asked to port its exit to ZeeUHV. The
grid (6 exit ports x 6 periods vs v1.29): the FULL port fails (SL2 whipsaws, h2 starves
June/July), but **SL5 h3 passes: +288.68, better in 5 of 6 incl. both hostile months,
April flips positive**. With last night's h8/12/20 sweep the clock is now bracketed
from BOTH sides — these entries pay by minute 3 or not at all. Shipped as ZeeUHV v1.30
+ Loud v1.2 (clocks kept identical so the loud experiment measures the entry).
Campaign ledger: -1,615 -> -639 (v1.29) -> **-351** (v1.30), four of six periods green.
ZeeSimple live forward: 14 closes, 10W/4L, +$6.29 at 0.01 lots — collecting.

## 4e. THE LADDER (2026-08-18 ~3 AM) — the frequency-vs-edge curve, drawn

Zee: "add the laws back one rung at a time and measure where each rung puts us."
ZeeSimple v1.10 grew three faithful law-rungs (default OFF); four configs x six
periods at 0.01 lots (uncensorable):

```
R0 bare            182.6/day  53.4%  -2,516.80  -0.201/trade
R1 +retracement     66.0/day  54.7%    -815.84  -0.181   <- Feb-11's 69/day lives HERE
R2 +structure       32.5/day  55.8%    -343.98  -0.155      (AUG positive from R1 up)
R3 +quiet-break     17.9/day  56.4%    -161.33  -0.133      (JUL positive at R2/R3)
```

Monotonic — every law buys expectancy; the laws are real. R1 = "every REAL
retracement" lands at Zee's exact Feb-11 tempo and is PROFITABLE in August tape.
No rung crosses zero over mixed regimes: hostile months get cheaper, never green.
**The residual is not a missing law — it is the REGIME.** Open question #1 (what
distinguishes Aug/May from Mar/Apr, in advance) is now formally the last unsolved
piece: R1's tempo gated by a kind-regime detector is the closest mechanical Feb-11
that can exist. Nothing shipped; all rungs default off.

## 4f. BACKTEST-vs-LIVE VERIFICATION (Zee's protocol: replay the live day, demand
the same trades at the same times)

**Friday Aug 14: both live fires reproduced TO THE SECOND** with identical side,
diamonds, tickets and the unforgeable volume fingerprint (uhv 173/brk 162 · uhv
206/brk 145). Price prints differed because Friday's LIVE quote feed was frozen near
4366 (the documented "2026-08-14 fault" that birthed the stale-quote guard) — live
printed the frozen quote; the tester replays the true tape. Tester's 5 extra fires =
windows the tick-starved live EA never evaluated. Verdict: **the tester is faithful;
that era's live side was the defective one, and it has since been guarded.**
Aug-17's 7-fire replay is queued — the broker had not yet published the day's ticks
(Bars: 0 at 3 AM; retry in the morning).

## 4g. ZEE'S FUNNEL PRICED · A NEW TESTER TRAP FOUND (morning, 2026-08-18)

Zee's correction: he never meant rank-6 — he meant "a UHV in EVERY retracement" (his
funnel: 100 trends -> 100 retracements -> 100 UHVs -> ~50 broken). Measured with the
body and local-peak vetoes OFF (ZeeUHV v1.33 InpLocalPeak): the FREQUENCY arrives
(87->374 LIVE trades, ~90-125/day) but the money leaves: -2,430.64 over six periods,
worse in 5 of 6. The two vetoes are guardians worth $2,430 — the mechanical shadow of
the glance his Feb-11 hand applied without noticing. April alone improves under every
loosening ever tested (trend-off +75, body-.3 +31, no-veto +115): the regime whisper.
Rank-6 (+121.86, passes promotion) stays shelved as an alternative — it answered a
question he wasn't asking. Nothing shipped; v1.30 remains live.

Also: the Aug-17 replay's "0 trades" was VOID — the rig cached a HALF-BAKED copy of
the freshly published day (bars with ranges, no candle colors; live terminal's record
is 99.1%% colored; Friday reproduces perfectly on the same binary). Cache deleted,
re-downloading, watcher re-armed WITH a census-based half-baked-data guard.
test_tips.md Part 12 records the trap.

## 4h. THE CERTIFICATE, THE DIAL, AND v1.34 (2026-08-18, midday)

**Backtest-vs-live verification COMPLETE.** Aug-17 replay on clean data (after the
half-baked cache was caught and purged): **7/7 live fires reproduced exactly** — minute,
side, volume fingerprint. Extras all named: one in the live disconnect window, one a
setup live v1.29 correctly refused under Law 9, one borderline feed-vs-tape flip.
With Friday's 2/2: the tester provably measures OUR strategy. (ZeeUHV_R1 on Aug 17:
16 trades, 4W/12L, -7.49 at 0.01 — hostile tape, as the ladder predicts.)

**The rank dial** {2,3,6,10}: +79.86 / +42.72 / +121.86 / +126.20 — every position
positive, 6 == 10 in five of six periods = SATURATION (most retracements hold few
serious candidates). Reproduction exact. Zee: "ship rank 6" -> **ZeeUHV v1.34 LIVE**:
every retracement auditions up to six volume-ranked candidates; body and local-peak
laws stay exactly as strict. Zee's two sentences reconciled in code.

NOTE: ZeeUHV_Loud_Breakout still runs rank-1 (the rank refactor is not ported there
yet) — its fires are now a strict SUBSET of ZeeUHV's; port + verify next session if
the pairing is to stay exact.

## 4i. NIGHT 2 (2026-08-17 -> 18) — Zee's goodnight ideas, measured

**The PROBE-BURST (his design: 0.01 scout first, basket only into pre-tested ground),
three temperaments:** 60s/0.10 -> -326.85 · 120s/0.20 -> +127.67 · 60s/any+ -> -318.13.
Not promotable — the +127.67 is May wearing a disguise (+450.97 there, negative in
LIVE/Jul/Apr). BUT a real discovery inside: **ALL three probe arms transform May**
(+346..+451) — the scout is a MAY-shaped tool; whippy tape is where pre-testing the
region pays. Filed under the regime question, not shipped.

**THE CALMER CHART — the night's headline. ZeeUHV v1.34 config on an M3 chart:**

```
              LIVE     Mar     Apr     May     Jun     Jul    TOTAL   worst
M1 (live)   +99.68 -246.70  +29.76 -383.86 +117.24 +155.00  -228.88  -383.86
M3           +0.96  -16.32   -7.28  -15.24  +80.12  -18.92   +23.32   -18.92
M5          -25.40  -11.52  -92.40  -55.74  -54.22   +4.40  -234.88   -92.40
```

**M3 is the FIRST net-positive six-period configuration in the project's history**,
with the worst period collapsing -384 -> -19 (20x variance reduction). It does not
earn more — it stops bleeding: hostile months flatten to near zero at the cost of the
kind months' cream. M5 failing both sides says M3 is a KNEE, not "slower is better".
**DIAL VERDICT (pre-dawn): M3 is a LONE SPIKE, not a plateau** — M2 −314.48,
M3 +23.32 (reproduced to the cent), M4 −274.44. Neighbours as bad as M1 or worse =
the stop-3 disguise. **M3 does NOT ship on this evidence.** One mechanical hypothesis
survives before burial: on M3 the 3-min hold is EXACTLY ONE CANDLE (enter at open,
judged at next open) — M2/M4 break that resonance. **THE RESONANCE IS REAL — "the trade lives ONE CANDLE" is the actual law.** Matching
hold to one candle improved EVERY timeframe: M2 −314→−170, M4 −274→−140, M5 −235→−51
(M3 +23 was already one-candle). March goes POSITIVE on M2 and M5, near-flat on M4 —
the bankruptcy month flattens on every chart where the trade is judged exactly at the
next candle's open. M3 was never magic; it was where the live 3-min hold accidentally
obeyed the law. **The completing cell broke the pure law — and completed the true one.** M1/h1:
−1,124.60 — catastrophic. One minute is not enough life for a 1-point target; the
scratch kills winners before they arrive. The full matrix:

```
        hold=3min (wall-clock)     hold=ONE CANDLE
M1           −228.88                 −1,124.60  (h1: candle too short for TP 1)
M2           −314.48                   −170.44
M3              =                       +23.32  (h3 IS one candle — the intersection)
M4           −274.44                   −139.76
M5           −234.88                    −50.58
```

SYNTHESIS — two separately-evidenced effects, and M3 is their unique intersection:
(1) ~3 minutes of LIFE is the wall-clock optimum (proven twice on M1: h2 fails, h3
beats h5/h8/h12/h20); (2) being JUDGED AT A CANDLE BOUNDARY stabilizes hostile months
(improves M2/M4/M5 uniformly, March flattens or flips positive everywhere it holds).
M3/h3 is the only cell where the optimal life equals exactly one candle. Not luck,
not a magic timeframe — a mechanism with neighbourhood support on both axes.

THE MORNING DECISION (Zee's, not mine): stay on M1 (earns the kind months: LIVE
+99.68, Jul +155; bleeds hostile: −384 worst) or move ZeeUHV to the M3 chart (first
positive six-period total +23.32, worst period −19, near-flat everywhere — at the
price of the kind months' cream). Passes the promotion letter (Jun kind ✓, Mar
hostile ✓). Nothing shipped overnight; v1.34 on M1 remains exactly as he left it. (Accidental find, confounded, logged as curiosity: ZeeSimple-canonical
on M5 went 78.6%% WR +26.64 in April.)

## 4j. THE MARRIAGE CAMPAIGN (2026-08-18 afternoon) — 54 runs, nothing ships, much learned

Zee: "run as many experiments as you want to mix n match the two M1/M3." Verdicts:
- **Consult dial = minefield**: look2 +300 / look3 −119 / look4 +103 / look5 +27 /
  look6 +10 / look8 −58 / look12 +44. Best cell adjacent to worst = luck's signature.
  No veto value ships. As SIZING (C2): coherent, too weak (+43 at 0.25).
- **Transplant refuted 3×**: Shop B's boundary exit on M1 entries = −247…−602. B is an
  ecosystem, not parts. (Matches M1/h1's earlier failure.)
- **Portfolio arithmetic**: B alone dominates every A/B blend on the test set — but the
  set underweights A's feast regimes (live receipts: +300/day in its season).
- **Leaderboard**: look2 +70.76 (spike, untrusted) · B +23.32 (worst −19) · everything
  else negative.
FIFTH independent pointer to the REGIME SWITCH as the real prize. Proposed next: the
self-aware switch (A stands down / quarter-sizes when her own rolling P&L is red; B
carries) — no forecasting needed, rig-testable. Both shops live meanwhile: the week
itself is the A/B experiment.

## 4k. 🫀 THE SELF-AWARE SWITCH — the week's crown (night of Aug 19-20)

Zee: "ok test it." The machine reads its own pulse (net of its last N closed
tickets); red pulse -> quarter-size scouts (never stops — a stopped machine cannot
feel the season change); green -> full stack. THE COURT'S VERDICT, pulse=20:

```
         v1.34      switch20       Δ
LIVE     +99.68      +87.30      -12.38   ~tie
Mar     -246.70      -87.40     +159.30   ✓✓
Apr      +29.76      +98.46      +68.70   ✓ green
May     -383.86      -90.64     +293.22   ✓✓✓
Jun     +117.24     +130.30      +13.06   ✓ kind improves
Jul     +155.00     +138.20      -16.80   small
TOTAL   -228.88    **+276.22**  +505.10
```

**THE FIRST NET-POSITIVE M1 CONFIGURATION IN PROJECT HISTORY** — and the mechanism
performed exactly as predicted: hostile months collapse, kind months untouched.
Better/tied in 5 of 6. The dial is a HILL (pulse-10: +264.78; pulse-40 partial
pre-crash: Mar +136.90). Season theory mechanically validated. SHIP DECISION
(pulse-20 -> v1.44) awaits Zee's word in the morning.

Caveats for the record: the pulse-40 completion run was VOID (six identical rows =
stale-report re-reads; something from a crashed parent task held the rig — rerun in
the morning). The original court task died at exit 127 mid-pulse-40; results above
are from its valid completed arms. The Aug-18 Law-12 replay is still owed.

**THE FEB-11 EXIT LAB — VERDICT (pre-dawn).** The retouch hypothesis (his 18:41
cluster waited 25 min and scratched — patience, not reflexes) was built (v1.43),
swept 11 arms, then synthesized with the switch (v1.44 InpScratchRedOnly):

```
switch p20 ALONE            +276.22   ← the crown HOLDS
full synthesis (p20+RS)     +155.10   positive; the scratch drags -$121
best always-on scratch      -547.20   (and it DID build his loss column: avgL
red-only scratch alone      -299.62    collapses $40 -> $2-3 — mission failed anyway)
```

CLOSED HONESTLY: the retouch mechanically achieves Feb-11's tiny losses, but this
strategy's winners DIP FIRST — scratching the dip scratches the $1 payers, in every
variant, even season-gated. His hand's selectivity remains unmechanized (count: 9).
**The machine's Feb-11 is the switch, alone.** (Lab data note: a few round-1 rows
were stale-polluted from the earlier rig crash — identical-row tripwire visible in
the raw table; clean arms carry the verdict.)

## 4l. MORNING OF AUG 19 — the dial completed, v1.45 LIVE, the Aug-18 answer

**v1.45 SHIPPED AND ATTACHED (05:30):** the self-aware switch live at pulse-20.
**The dial completed clean:** p10 +264.78 · p20 +505.10 · p40 +455.16 (deltas) —
all three ABSOLUTE-POSITIVE configs; a plateau, v1.45 on its crest. The mechanism
is robust, not lucky.

**The Aug-18 Law-12 answer (his two-day-old question), at live size:**
OFF 30 tickets 53.3%% −37.70 · ON 10 tickets 80.0%% +75.60 — his peak-bound law
turned that red day green and removed exactly the fires his autopsy convicted
(12:46 + the evening ghost family). Six-fortnight receipts still carry the
streak-tax; and with the switch now live, Law 12's marginal value must be
re-measured ON TOP of v1.45 before any ship (they may overlap or compound).

**Harness lesson (cost 8 wasted watcher-hours):** the half-baked guard vetoed valid
Aug-18 data 24 times because it read the census from an unrelated log. Rule: the
census check must come from the SAME run's output, and when it cannot be found at
all, downgrade to a warning if bars+trades are sane. (test_tips candidate P14.)

## 4m. THE DIAMOND CRASH COURT (Aug 19 midday) — his theory, tried in 54 runs

Zee: "the diamond had only one defect — it kept winning until the trend shifted and
it gave a drop. control the crash and even without the additional laws it's a
consecutive winner. test this as thoroughly as you can."

```
FUSED pure (diamond in green season)   +247.08   Jul +410! · worst single -42
FUSED guarded (10c kept in green)       +24.74
RAW + pulse slow (20)                  -233.19   best pure-theory arm
RAW + near-stop / cool60 / day-halt    -713 .. -982
RAW + pulse fast (5)                 -1,373.27
RAW diamond, faithfully resurrected  -1,640.61   (but POSITIVE in 4 of 6 periods!)
(sitting champion: v1.45 pulse         +276.22)
```

VERDICT — three truths:
1. HIS PREMISE IS TRUE: the raw diamond wins 4 of 6 fortnights (May +220, Jun +161,
   Jul +180, LIVE +38). Only Mar (-803) and Apr (-1,437) kill it.
2. THE CRASH CANNOT BE CONTROLLED FROM INSIDE THE RAW MACHINE: five designs, zero
   pass. The worst-single-loss column (-42.50) never moved — crash-fixes cut crash
   COUNT, never crash SIZE, and with SL 20 the damage-before-detection is fatal.
3. THE CRASH CAN BE PRE-EMPTED: the fused machine (diamond geometry only in green
   pulse seasons) is the only diamond-bearing config in profit (+247) — $29 short
   of the plain champion. **THE REFINEMENT TOOK THE THRONE — FUSED + fast-red: +415.96** (+140 over the
   champion). Quick to fear (5-ticket red ends the diamond season instantly), slow
   to greed (20-ticket green opens it). LIVE +114 · Mar −62 · Apr −88 · May −148 ·
   Jun +202 · Jul +398. Better in 4 of 6 vs the champion, kind AND hostile.
   **Worst single loss: −19.36 — the −42 crash class is GONE** from a machine
   carrying the 20-point diamond stop. Zee's theory vindicated in refined form:
   the crash was never controllable, only pre-emptable, and the asymmetric pulse
   pre-empts it. **THE DIAL IS A RISING RIDGE, not a spike:** fast-red 3 = +376.60 · 5 = +415.96 ·
   8 = +449.26 — every position beats the champion by $100-173, worst single loss
   -19..-22 at every setting. **CREST FOUND AT 8 — a perfect hill: 3=+377 · 5=+416 · 8=+449 · 12=+283** (rises,
   peaks, falls; all four beat the champion). SHIPPED as v1.49 (Zee: "go ahead"), awaiting reattach:
   **THE DIAMOND SEASON MACHINE** = DiamondMode on · slow-greed pulse 20 ·
   fast-fear window 8 · diamond geometry SL20/TP1/h60 in green · scout machine in
   red. Receipts: +449.26 (champion +276.22, 3 days ago -228.88), better in 4 of 6
   vs champion incl. kind AND hostile, worst avgL -5.49, worst single -19.36.
   (Honest overfit note: fourth refinement round on the same six periods today —
   mitigated by mechanism-first design and whole-dial positivity, and the final
   config gets live-forward validation like everything else.)

## 4n. THE LOUD THESIS ON TRIAL (Aug 20) — Zee: "loud EA's winrate and totals beat the queen"

True this week (era: LOUD 59%% +172.90 vs QUEEN 45%% -227.40) — so the wild twin got
its first six-fortnight court appearance. VERDICT: **-658.44**, losing 4 of 6 periods
(Apr -383, even Jun -185); spectacular ONLY in feast windows (LIVE +162.56 — best
single feast harvest of any config — and Jul +248). A pure feast-weather specialist:
this week's outperformance is regime luck; its Monday -366 was its March in preview.
The queen's guard is worth ~$1,100/twelve-weeks vs the loud style. No changes — the
live A/B continues with priors now set. Also today: Shop B v1.10 (pulse ported,
AWAITING REATTACH on M3); her -258.70 autopsy: lawful setup, thrice-defended ceiling
at rally exhaustion, damage = SIZE (8 unguarded tickets).

## 4o. THE RANK-6 AUDIT (Aug 20, Zee: "do it") — exonerated and decorated

Under v1.49: rank-1 = +198.24 vs shipped rank-6 = +449.26 → **rank-6 is worth
+251.02 under the new machine** (2x its original receipts; better in 5 of 6, only
April prefers rank-1). Live era: 15 rank-6-only fires; exactly ONE on Wednesday —
the evening WINNER. The 0W/14L Wednesday morning was all rank-1-visible setups:
the "extra frequency skewed the week" hypothesis is REFUTED. The queen-vs-Loud gap
is now fully explained: feast weather + deliberate loud-quartering + winter sizing.

## 4p. THE WIN-RATE GOAL — day one: three trials, three refusals, one conclusion

Zee's standing goal (memorized): fewer losing trades at FIXED geometry. Campaign day:
- LAW 12 on v1.49: WR 69-81%% but −275.56 net (the pulse already owns its value) — refused
- THE BULL (buys-only, no gate): loses ALL SIX incl. July — "gold tends up" is false
  at M1 pullback scale; the trend gate's silence = ~$1,600/12wk of dodged losses
- LAW 5 (wick off): worse in ALL SIX (−291.28) — DECIDED, wick stays; oldest item closed

CONCLUSION: v1.49 is a genuine local optimum — every single-knob deviation loses.
Remaining trail: hour-census filter + live-forward (the pulse's first green season IS
the win-rate event). Law 5 removed from open items.

## 4q. v1.52 SHIPPED — THE HOUR DIMMER (Zee: "ok ship the dimmer alone as v1.52")

The week's most-vetted candidate: 22 periods, 3 independent datasets, positive on
all three (court +127 · virgin +260 · live days +165); surgical (byte-identical on
days with no dim-hour trades). New court total +576.18. TP 0.75 benched with honor
(virgin +605 — first candidate of the next promotion cycle after live-forward).
Combined arm refused (contradicts itself across datasets = noise). NEEDS REATTACH
(banner must say v1.52).

## 4r. THE PRUNED-SETUPS THEORY (Zee: "if we took all those setups we'd be in much
greater profit! test this") — the week's most dramatic refusal

All togglable prunes off at once under v1.52: 13,674 tickets, WR 53-70%% (the trap:
they LOOK like winners), **TOTAL −6,505.71 vs +576.18 shipped — a $7,082 swing.**
The prune-pile's one real vein was already mined (rank-6, +251, shipped). The
"possible setups" button shows the guard's salary being earned, not missed gold.
Theory closed with the strongest receipt of the week.

## 4s. THE +605 INVESTIGATION (Zee) — explained, attempted, honestly refused

TP 0.75's virgin +605 = a CHOP HARVESTER: near-misses at 0.7-0.9 pts convert to wins
(Feb2 WR 69→82; live chop day Aug 12 +303) while feasts get taxed (Aug 11: WR 86→91
but −66 — the first 90%+ live day on our setups, and the honest anatomy of paid-vs-
free win rate). The shippable form (v1.53 pulse-switched target: red→0.75) FAILED
the triple bar (court −112 · virgin +103 · days −15): red pulse ≠ chop — it also
means early-feast recovery. TP 0.75 benched awaiting a tape-based chop detector.
Also today: the LIVE ANATOMY shipped (cockpit panel + humps overlay + forming view
in his exact reading format, all from rot-proof terminal bars).

## 4t. THE VOLUME SOURCE — his eye's feed, finally measurable (Aug 20 night)

Zee: "we want to use concretely the volume from OANDA inside Tradingview."
tvDatafeed (websocket, no CDP) restores OANDA data AND heals oanda_m1.csv (dead
since Aug 14). **Disagreement measured: 46.4%% of rolling 8-bar windows crown a
DIFFERENT loudest candle** (broker ~450/min vs OANDA ~1,550/min — different
counters entirely; only rank matters). v1.58 InpVolSource=1 reads the bridge's CSV
in live AND tester. Reach limit: ~4 days of M1 history, so the head-to-head runs
Aug 17-20 and the archive grows from tonight for future courts.

## 5. Open items

1. **TradingView CDP** — MSIX app can't be launched with `--remote-debugging-port` by
   normal means; until solved, tape archive and brain panels are frozen (forensic is
   independent now). Options: `Invoke-CommandInDesktopPackage` (attempted, unverified),
   or reinstall TV from the normal installer instead of the Store.
2. **Law 8 live evidence** — accumulate; revisit when the tag has a few hundred live tickets.
3. **D3 drag / Law 5 wick question** — from last session, still open: drop, invert, or
   keep Law 5 as a diamond. Zee hasn't decided.
4. **11 oldest missing fills (Aug 3-4, ≈-$22)** — beyond the terminal's local history;
   v1.04's server-side backfill may collect them eventually. Cosmetic.

## 6. Reproducing today's measurements

```bash
# Law 8/9 harness (writes .set, runs six periods, aggregates mask buckets):
py <scratchpad>/law8_run.py    # tag split
py <scratchpad>/law9_run.py    # arm ON vs the §3 baseline table
# Baselines live in this report; mask parse: C:\mt5_rig\Tester\logs, [DIA] lines.
# Check Bars against the window FIRST (13,788 = full two-week M1 window; 4,137 = 3 days).
```
