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

## 4i. NIGHT 2 (2026-08-18 -> 19) — Zee's goodnight ideas, measured

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
judged at next open) — M2/M4 break that resonance. The one-candle-hold arm (M2/h2,
M4/h4, M5/h5) is running: if hostile months flatten across TFs, the law is "the trade
lives one candle" and M3 was merely where the live hold already obeyed it. (Accidental find, confounded, logged as curiosity: ZeeSimple-canonical
on M5 went 78.6%% WR +26.64 in April.)

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
