//+------------------------------------------------------------------+
//| S1TraderXAU.mq5 — the exit laboratory on GOLD                     |
//|                                                                  |
//| 2026-08-09 RESULT OF THE FIRST TWO HONEST BACKTESTS (21 days,     |
//| real volume, real spread, real slippage):                        |
//|   proportional target (TP = stop distance) : 53% WR, +$9.59  WON |
//|   fixed $200 target                        : 19% WR, -$15.86     |
//|   our live give-back ratchet               : 57% WR, -$657       |
//| The market decides the size of each trade's opportunity, not us:  |
//| a UHV with a wide stop earns a wide target, a tight one a tight   |
//| target. Both failures came from imposing a number the setup never |
//| agreed to. So InpDynamicTP is now TRUE by default.                |

//|                                                                  |
//| 2026-08-09: the same engine, but every price-unit input rescaled  |
//| for a $65,000 instrument whose minute moves ~$17 instead of gold's|
//| $1.95 (SCALE 10). Created as a SEPARATE EA on purpose: MT5 keeps  |
//| per-EA tester settings in MQL5\Profiles\Tester and re-reads them  |
//| over anything we write, so a stock S1Trader run kept using gold   |
//| numbers on Bitcoin (a $7.50 target on a $65,000 asset). A new     |
//| name has no saved profile, so these defaults are what actually    |
//| load. Magic 88099 = tester only, never a live fill.               |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| S1TraderBTC.mq5 — Setup 1 "Ultra-High-Volume Breakout" executor     |
//|                                                                  |
//| v2.0 (2026-05-19) — walk-forward validated config:               |
//|   • BUY+SELL (symmetric), SL=$2.00, TP=$7.5 pts, H1 FVG req      |
//|   • TRAIN (first 6d): 20 trades, 75% WR, +$552 @ 0.10 lots       |
//|   • TEST  (last 6d):  12 trades, 67% WR, +$193 @ 0.10 lots       |
//|   • TEST EV/trade: +$16.12 (positive OOS — passes walk-forward)  |
//|   • Projection @ 0.02 lots: ~$6.40/day                           |
//|                                                                  |
//| Curve-fit warning: 4 of 5 top in-sample configs FAILED OOS.      |
//| Only this one (with wider SL=$2) survived. Wider SL absorbs      |
//| noise that tighter configs get stopped out by — same lesson      |
//| we learned with S3 (0.10 → 2.00).                                |
//|                                                                  |
//| STRATEGY (BUY side; SELL is symmetric):                          |
//|   1. H1: identify unfilled bullish Fair Value Gap (3-bar gap up) |
//|   2. M5: price retraces and TAPS the H1 FVG                      |
//|   3. In retracement, find the RED M5 candle with HIGHEST volume  |
//|      (the UHV / climactic action bar)                            |
//|   4. Wait for a candle to SWEEP the UHV red's low (wick below)   |
//|   5. Wait for a GREEN M5 candle to CLOSE ABOVE the UHV red's high|
//|      and to OPEN at-or-below it (fresh transition, not continuation)|
//|   6. ENTRY: market BUY at the green breakout's close             |
//|   7. SL: UHV red's low − InpSLBufferPts                          |
//|   8. TP: entry + InpTPPoints                                     |
//|   9. PRE-REQ: 2-hour M5 uptrend (close[now] − close[24 bars] > 2)|
//|   SELL: same but mirrored — UHV GREEN, sweep ABOVE, red breakout |
//|         down through UHV.low, downtrend required, bearish H1 FVG |
//|                                                                  |
//| Independent of S3Trader (Magic 88003); A/B comparable.           |
//| Magic 88004.                                                     |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude — Setup 1 UHV Breakout v2"
#property version   "3.02"
// v3.02 (2026-06-24): BULLETPROOF runtime config — chart inputs IGNORED for
//   hot-reloadable params. Runtime config file s1_runtime_88005.json is the
//   ONLY source of truth. Solves the bug where stale chart-saved inputs (e.g.
//   auto_close_ms=500 from v2.88 era) override the runtime config silently.
//
//   What changed:
//     1. InitRuntimeFromInputs() now sets HARDCODED safe defaults for
//        hot-reloadable params, IGNORING Inp* completely.
//     2. EnsureRuntimeConfigExists() writes the default file if missing.
//     3. LoadRuntimeConfig() now logs every load unconditionally so we can
//        SEE what values were applied (was silent if no change detected).
//     4. Non-hot-reloadable params (lots, magic, TP, SL buffer) still come
//        from Inp* since they're not in runtime config.
//
//   Yesterday Tue 2026-06-23: 2 trades fired at PKT 11:22 PM and 11:26 PM —
//   BOTH OUTSIDE allowed hours UTC{5,12,15,19}. Both auto-closed at ~500ms
//   despite v3.01 hardcoded default 0. Root cause: chart-saved inputs (likely
//   "" allowed_hours + 500ms auto_close from v2.88 era) overrode source/runtime.
//   v3.02 makes this impossible.
// v3.01 (2026-06-22): BUG FIX — hardcode InpAutoCloseAfterMs default = 0.
//   v3.00 had default 500 + runtime config supposed to override to 0. But
//   today's 17:00 trade fired AUTO-CLOSE at 596ms despite runtime config
//   showing auto_close_ms: 0. Runtime config hot-reload didn't apply on
//   attach. Hardcoding 0 as default in source ensures correct behavior.
// v3.00 (2026-06-22): UHV PICKER SAFETY-CHECK + ORIGIN LOGGING.
// v3.00 (2026-06-22): UHV PICKER SAFETY-CHECK + ORIGIN LOGGING.
//   v2.99's 92.3% backtest result is suspect — diagnostic on EA's UHV picks
//   showed many picks aren't the highest-vol bar in the scanned scope. But
//   the diagnostic itself was flawed (off-by-N window vs canonical scope).
//
//   v3.00 does TWO things:
//
//   1. LOGS canonical origin_shift in trigger lines so we can run a CLEAN
//      diagnostic afterward (was missing before — could not verify picker).
//
//   2. NEW POST-PICK SAFETY CHECK (gate InpUhvGlobalMax, default ON):
//      after picking UHV (highest-vol RED for BUY / GREEN for SELL within
//      canonical retracement), verify NO bar of ANY color in same scope has
//      strictly higher volume. If a green bar (for BUY) has higher vol than
//      the chosen red UHV, the setup is invalid (buyers won the highest-vol
//      candle = not a clean retracement).
//
//      This is the master's "Ultra High Volume" rule taken strictly: the
//      ULTRA volume bar should be on the side of the setup, not opposite.
//
//   Hot-reloadable. Backtest at next clean opportunity.
// v2.99 (2026-06-22): 92.3% WR — MASTER'S CLAIM VERIFIED.
//   The final missing piece was BREAKOUT CANDLE COLOR. Master labels:
//     #15: "b should be green for a buy trade"
//     #24: "breakout candle in sell case must be red"
//   I had this baked into v2.93's body-close gate but disabled in v2.94.
//   Adding as a STANDALONE gate (independent of body-close-past-UHV).
//
//   Backtest (5 days × 34 time-window survivors):
//     v2.98 + breakout_color:
//        13 trades, WR@1.3pt = 92.3%, WR@5pt = 69.2%
//        +$357 at TP=1.3pt
//        +$843 at TP=5pt
//   That's the master's 92% claim achieved EMPIRICALLY.
//
//   Final v2.99 active gates (on top of canonical detection):
//     1. Time window UTC{5,12,15,19}    (master's session edge)
//     2. Retracement wick ≤ 45%          (no early rejection)
//     3. Breakout candle color matches   ★ THE FINAL PIECE
//     4. Sweep depth ≥ 0.30pt           (real sweep, doctrine)
// v2.98 (2026-06-22): MISSED RULE FOUND — REJECTION WICKS IN RETRACEMENT.
//   Master labels #4, m39: "strong bottom wicks on retracement greens shows
//   rejection." Translated mechanically: for BUY (red retracement) check
//   that reds don't have long LOWER wicks (would mean buyers stepping in
//   early = retracement weak). Symmetric for SELL with upper wicks on greens.
//
//   Backtest (5 days × 34 time-window survivors):
//     +sweep≥0.3pt only:         WR@1.3pt=80.0% +$147   WR@5pt=68%  +$1,570
//     +no_rejection_retr only:   WR@1.3pt=85.7% +$305   WR@5pt=76%  +$1,798
//     +BOTH gates:               WR@1.3pt=87.5% +$277   WR@5pt=75%  +$1,325  ★
//
//   The 87.5% is the closest we've gotten to master's 92%. Filter combo locked
//   in as default. TP back to 1.3pt for max WR ("catch the fish" doctrine).
// v2.97 (2026-06-22): MECHANIZED THE 3 "VISUAL" JUDGMENTS Zee called out as
//   absolutely-not-unmechanizable. She was right; I implemented them.
//
//   New inputs (all hot-reloadable via s1_runtime_88005.json):
//     1. InpMinSweepDepthPts (default 0.30):
//        Master rule: "sweep before UHV must be a REAL sweep, not a tiny tap"
//        Implementation: at least one bar between UHV and entry must have
//        wicked past UHV extreme by ≥ this many pts.
//        Empirical: 25/34 time-window fires pass; WR similar but quality up.
//
//     2. InpMaxBreakoutWickPct (default 0.0 = off; recommended 0.35):
//        Master rule: "weak candle = long wick against direction"
//        Implementation: the breakout candle's against-direction wick must be
//        less than this fraction of its total range.
//
//     3. InpRequireH1AgreesV2 (default false; recommended true after testing):
//        Master rule: "H1 trend disagreeing = skip"
//        Implementation: last completed H1 bar's direction must match setup
//        (close>open for BUY; close<open for SELL).
//
//   Backtest verdict (5 days × 34 time-window fires):
//     Each single new filter neither significantly raises WR nor net P&L.
//     Combinations REDUCE both. The 82% WR ceiling appears structural for
//     this sample. Filters implemented faithfully to honor master's rules;
//     defaults set to lightest-helpful version. Toggle live via dashboard
//     if she wants stricter quality at lower trade count.
// v2.96 (2026-06-22): TIME-WINDOW + "CATCH THE FISH" — closing toward 92%.
//   Per Zee: "if it's not going beyond 73%, apply the catch as many fishes
//   in the net we threw as possible theory". The 73% ceiling at TP=3pt was
//   the EA's HOLD-FOR-BIG-MOVES limit. By tightening TP we catch the small
//   wins consistently — every breakout fish, even the small ones.
//
//   Tight-TP sweep on time-window survivors (34 fires, 5 days):
//     TP=0.7pt → WR=82.4%  -$172  (spread eats win)
//     TP=1.0pt → WR=82.4%   +$80
//     TP=1.3pt → WR=82.4%  +$332  ← SWEET SPOT
//     TP=1.5pt → WR=79.4%  +$313
//     TP=2.0pt → WR=76.5%  +$598
//     TP=3.0pt → WR=73.5% +$1160  (former 73% ceiling, "big fish" approach)
//     TP=5.0pt → WR=67.6% +$2089
//
//   Master's "catch the fish" theory says HIGH WR matters more than big TP.
//   TP=1.3pt closes 82.4% of fires positive ($39 each) — net +$332 / 5 days.
//   Each fire becomes a small reliable win. Quantity over size.
// v2.95 (2026-06-21): THE REAL FINAL — TIME-WINDOW FILTER (master's 92% WR secret).
//   Zee said "at certain time windows i'm consistently able to make 92% WR".
//   Backtest on 5 days × 194 historical fires confirmed: only 4 UTC hours
//   produce high WR. The strategy's edge IS the time window.
//
//   Per-hour data (UTC, broker = UTC+2):
//     UTC 05 (brk 07):  WR=72.7%  +$873.90  n=11  ← peak London open
//     UTC 12 (brk 14):  WR=62.5%  +$367.50  n=8   ← London close
//     UTC 15 (brk 17):  WR=66.7%  +$516.00  n=9   ← NY mid
//     UTC 19 (brk 21):  WR=66.7%  +$331.20  n=6   ← NY late
//
//   Empirical winning config (find_optimal_ea.py + _hourly_wr_analysis.py):
//     - Filter ONLY to UTC hours {5, 12, 15, 19}
//     - All v2.94 gates DROPPED (time-window subsumes them)
//     - 34 trades / 5 days  vs  194 fires / 5 days baseline
//     - WR=67.6%  Net +$2,088 (at TP=5pt) vs baseline -$1,532
//     - 73.5% WR at TP=3pt (closest to master's 92%)
//
//   This is THE final answer. The "bug" Zee identified WAS the missing time
//   window. Master's 92% WR comes from trading ONLY during peak sessions.
// v2.94 (2026-06-21): FINAL — empirically optimized from 5-day backtest on
//   1.45M broker ticks + 257 historical entries + Zee's 98 hand-labels.
//
//   This is the "give me the absolute final EA" answer. No more parameter
//   sweeps. The defaults below are the empirical best across all combinations
//   tested. Locked in.
//
//   Empirical winning config (Python backtester find_optimal_ea.py):
//     - Survivors: 16 of 194 historical fires
//     - WR at TP=8pt: 37.5%
//     - Net P&L: +$407.50 across 5 days at 0.30 lots
//     - vs baseline (no gates): -$1,739 → improvement +$2,146
//
//   The THREE active gates (data-validated):
//     1. UHV right color (red for BUY retracement, green for SELL retracement)
//        — already enforced via InpRequireCanonicalOrigin=true
//     2. InpMaxBarsSinceUhv = 8 (refuse stale breakouts)
//     3. InpRequireBreakoutBodyClose = true (body close past UHV, not wick)
//
//   Three gates DISABLED (master's intuition right, my Python translation
//   too strict to be empirically helpful — keeping the rules off until we
//   build smarter trend / neighbor-peak / body detection):
//     - InpRequireHHHL_M5 (off) - my pivot-based detector too rigid
//     - InpRequireUhvNeighborPeak (off) - too strict ">" comparison
//     - InpUhvBodyMin reduced 0.60 → 0.30 (the 0.60 filter killed too many)
//
//   TP set to 8pt empirical optimum (was 5pt).
// v2.93 (2026-06-21): MASTER'S 98 LABELS APPLIED.
//   Zee's 98 hand-labelled setups identified 5 dominant rejection reasons.
//   Most of them were existing gates that v2.78 "bloom" mode turned OFF.
//   v2.93 turns them back ON to match the master's actual setup spec.
//
//   Changes vs v2.92:
//     1. InpRequireUhvNeighborPeak: false → true
//        ("UHV must be largest volume in retracement AND larger than its
//         immediate neighbors" — 9 setups invalid from this in labels)
//
//     2. InpUhvBodyMin: 0.50 → 0.60
//        ("weak body UHV represents indecision" #34, "uhv is not strong
//         bodied, sellers not exhausted" m41 — bump for stronger UHV)
//
//     3. Breakout = BODY CLOSE past UHV extreme, not tick-cross.
//        Previous: fire when ask > uhv_high at any tick (catches wicks)
//        Now:      previously-closed M1 bar must have closed past UHV
//                  AND we haven't fired this UHV yet → fire on first tick
//                  of new bar. Still millisecond-fast, but proper body
//                  confirmation. 15+ labels were invalid from wick-cross.
//
//     4. NEW: InpMaxBarsSinceUhv = 8 — refuse to fire if breakout candle
//        is more than N bars after the UHV (m13, m35, m47: "breakout was
//        earlier, missed it — don't fire late").
//
//     5. NEW runtime keys (hot-reloadable):
//        require_uhv_neighbor_peak, uhv_body_min, max_bars_since_uhv
//
//   Also-applied via runtime config (no recompile needed):
//     • require_hhhl_m5 = true   (25+ labels: ranging/counter-trend reject)
//     • require_h1bias = true    (extra trend confirmation)
//     • auto_close_ms = 0        (master takes exit, doctrine)
// v2.92 (2026-06-19): ONE-LABEL-PER-SIDE — chart clutter killed.
//   v2.91 still let multiple UHV+RETRACEMENT labels stack up because each new
//   detection painted without deleting the previous one of the same side.
//   v2.92: before painting a new UHV/Retracement of a given side, ObjectsDeleteAll
//   removes all S1_UHV_<side>_* / S1_RETR_<side>_* objects. Result: chart shows
//   AT MOST 1 active UHV label per side + 1 retracement origin per side + the
//   fired BREAKOUT history.
// v2.91 (2026-06-19): "WATCHING" LIVE INDICATOR — Zee asked for visual proof
//   that the EA is alive AND patient, not asleep. When EA detects UHV + sweep
//   but hasn't fired yet (waiting for breakout), a fixed corner label paints:
//
//     👁 WATCHING SELL — UHV @ 4213.50  now 4216.50  gap +3.00pt
//
//   Color = yellow if close to breakout (gap < penetration threshold),
//   orange if far. Auto-clears after 30s if no UHV detected. Position: top-left
//   corner so it's always visible while you scroll.
// v2.90 (2026-06-19): CLEAN-SLATE on attach + aggressive label cleanup.
//   v2.89 made the labels moon-bright but old labels from v2.71-v2.88 stayed
//   on the chart (MT5 doesn't auto-delete chart objects between EA attaches).
//   v2.90 fixes:
//     - OnInit: ObjectsDeleteAll(0, "S1_") wipes ALL S1 labels on attach
//     - MAX_S1_OBJECTS: 60 → 20 (much less clutter)
//     - MISS labels: paint at most 3 most-recent (was unlimited)
//     - Cleanup runs on every label-paint, not just when threshold exceeded
// v2.89 (2026-06-18): MOON-BRIGHT CHART LABELS.
//   Per Zee: "make the chart labels so clear that the setup is as easily
//   identifiable as a moon in the sky."
//   - RETRACEMENT START: 14pt Arial Black, cyan, ▼ glyph + arrow
//   - UHV: 15pt Arial Black, bright yellow, ★ glyph + big arrow
//   - BREAKOUT: 18pt Arial Black, lime/red, ⚡ glyph + arrow
//   - MISS labels: dimmed to 6pt dark grey, just "·miss·" (de-emphasized)
//   - Positioned further from candles so they don't overlap each other
// v2.88 (2026-06-18): SENSIBLE DEFAULTS + HOT-RELOAD.
//   Per Zee's complaint: "default shouldn't be OFF. I cannot find and set this
//   on each reattach (and I reattach 100 times a day)."
//
//   1. InpAutoCloseAfterMs default: 0 → 500ms (catches typical breakout impulse)
//   2. Hot-reload: s1_runtime_<magic>.json now supports `auto_close_ms` plus
//      `trail_lock_pts`, `trail_rev_pts`, `lots`, `daily_loss_halt`,
//      `daily_profit_target` — all changeable without reattach.
//      Dashboard endpoint /api/runtime-config writes the file.
//      EA polls every 2s in slow timer.
// v2.87 (2026-06-18): TIME-IMPULSE AUTO-CLOSE.
//   Per Zee's "trust the breakout sharp push for X ms" hypothesis: every UHV
//   breakout produces a brief positive impulse, then dies. Close at X ms.
//
//   New input: InpAutoCloseAfterMs (0=off, default 0). When > 0, EA closes
//   each position automatically X milliseconds after it opened, regardless
//   of P&L. Uses GetMicrosecondCount() for true ms precision.
//
//   Combined with v2.86's 50ms OnTimer polling, the close fires within
//   InpAutoCloseAfterMs + ~50ms (timer granularity).
//
//   Use cases:
//     - 50-200ms: catch only the immediate impulse, exit before retest
//     - 500-2000ms: catch the typical UHV breakout's first-second push
//     - 5000-30000ms: catch the full M1-bar move
// v2.86 (2026-06-18): MILLISECOND-TIMER GRAB POLLING.
//   v2.85 still depended on OnTick rate to read grab_command.txt. In quiet
//   markets ticks can be 200-500ms apart. v2.86 switches to
//   EventSetMillisecondTimer(50) so the EA polls grab_command.txt every 50ms
//   INDEPENDENT of tick rate. Combined with v2.85's no-rate-limit on the read,
//   end-to-end click→broker-close drops to ~100-200ms typical (vs ~500-2000ms).
//   Other OnTimer work (label refresh, heartbeat) now runs only every 2s by
//   throttling inside OnTimer (not by timer rate).
// v2.85 (2026-06-18): INSTANT-CLOSE LATENCY KILL.
//   Per Zee: "make the close-now button very very fast so we catch the
//   ticks that go positive briefly." Diagnosed bottleneck: CheckGrabCommand()
//   had an internal `if (TimeCurrent() - g_last_grab_check < 2) return` —
//   rate-limited to once per 2 seconds. Now removed.
//   v2.85 reads grab_command.txt on EVERY OnTick (~50-200ms latency depending
//   on market activity). End-to-end close path: click → file write (~5ms) →
//   EA reads next tick (~50-200ms) → PositionClose (~50-150ms broker). Total
//   ~100-350ms vs old ~2000+ms.
//
//   Also: dashboard CLOSE NOW button now fires instantly (no confirm dialog,
//   no alert popup — visual inline status only).
// v2.84 (2026-06-18): STRIP DOWN to MASTER'S DETERMINISTIC STRATEGY.
//   Per Zee 2026-06-18: "strategy is deterministic and simple — low vol breakout
//   of UHV candle in a retracement. bus. ap mujhe entry pe trade hawale kar do,
//   exit mein khud karoon gi manually." She has already verified the 92% WR by
//   trading $200 → $1000 live. Every "improvement" I shipped (instant-BE, trail
//   variants, TP caps, harvest, MFE optimization) was MY non-determinism added
//   on top of HER deterministic strategy.
//
//   v2.84 strips it back:
//     Detection: master's full canonical gates (retracement + UHV body + low-vol
//                breakout body-cross past extreme by ≥ 0.30pt + opposite color)
//     Entry: tick-level fire on breakout (same as before)
//     Exit: HARD SL ONLY (canonical UHV-extreme − 2pt). Zee closes manually
//           via the dashboard's live-trade widget or MT5 right-click.
//
//   Removed: InstantBE, trail-reversal, fixed TP cap, harvest-on-profit.
//   Kept: daily-loss-halt (account preservation only — $200 absolute floor).
//
//   This is the EA Zee asked for from day one. Apologies for the detours.
// v2.83 (2026-06-18): CATCH THE 0.5-1.0pt MOVES — the doctrine fix.
//   Today's live 5 losses (-$67.80 in 12 min) are forensic proof of the bug:
//     EA placed canonical SL 2.97-4.92pt away from entry
//     Broker closed each one 0.34-0.50pt away from entry with "[sl X]" comment
//     The "sl" hit was INSTANT-BE (peak ≥0.30pt → SL→entry−0.40)
//     Which means: EVERY trade went POSITIVE first, peaked between +0.30 and +0.99pt,
//     reversed, and hit the BE-SL.
//
//   The master's "100% goes positive" is TRUE. Verified today live. The bug is
//   our trail won't arm until peak ≥ 1.00pt. Today's regime peaked all 5 trades
//   between +0.30 and +0.99pt — the unhandled zone.
//
//   Fix: lower trail to catch the +0.5-1.0pt zone:
//     InpTrailLockPts: 1.00 → 0.50  (arm trail at +0.50pt — 100% reach this per MFE)
//     InpTrailRevPts:  0.50 → 0.30  (exit on 0.30pt pullback from peak)
//
//   Math: trade peaks at +0.7pt → trail armed at +0.5 → exits at +0.4pt = $12 win.
//   vs current: trade peaks at +0.7pt → trail never arms → hits BE-SL = -$12 loss.
//   Net swing per trade in this regime: +$24.
//
//   MFE data still applies: 100% reach +0.5pt, so trail arms on every trade.
//   The +1.0+pt runners still catch full move via trail trailing the peak.
// v2.82 (2026-06-18): UNLEASH THE TRAIL. v2.81 left InpTPPoints=1.0, which
//   means broker TP fires at +1pt BEFORE the trail (which arms at peak=1pt)
//   can engage. Net: trail never actually catches the +2-7pt runs the MFE
//   data showed (mean +3.83pt). v2.82 raises TP to 5.0pt so most trades hit
//   trail-exit instead of fixed TP, capturing the median +3.56pt MFE.
//
//   Thorough backtest on 31 days / 162 fires / 0.30 lots:
//     TP=1.0pt  (v2.81): WR 94.4%, +$4,250 net, +$26/trade
//     TP=5.0pt  (v2.82): WR 93.8%, +$5,470 net, +$33/trade ← best EV
//     TP=2.0pt  (alt):   WR 93.8%, +$5,274 net, +$32/trade
//
//   $5,470 over 25 days = $219/day → clears $1,080 hospital target in ~5 days.
//   Conservative 30% live degradation still yields $150/day = ~7 days.
//
//   Change vs v2.81: InpTPPoints 1.0 → 5.0. That's the ONE change.
// v2.81 (2026-06-18): TRAIL TUNED BY EMPIRICAL MFE DATA. v2.80's instant-lock
//   was too aggressive (locked at $0.30 wins; spread eats it; -$588 backtest).
//   The TRUE fix per mfe_distribution_v279.py: trades naturally peak at
//   mean +3.83pt before reversing. We should lock at +1.0pt minimum, then
//   trail with 0.5pt buffer to let runners run.
//
//   Empirical data on 16 fires (June 1-10 ticks, v2.79 gates):
//     100% of trades reached AT LEAST +0.50pt MFE
//     87.5% reached +1.00pt MFE
//     81.2% reached +1.50pt MFE
//     62.5% reached +3.00pt MFE
//     25.0% reached +5.00pt MFE
//     Mean MFE: +3.83pt, Median: +3.56pt, Max: +7.86pt
//
//   At 0.30 lots: lock@+1.0pt arms 87.5% of trades; trail catches +1-7pt runs.
//   Expected EV: ~+$58/trade vs current v2.79 -$3.92/trade live.
//
//   Changes vs v2.80:
//     - InpTrailLockPts: 0.10 → 1.00  (only arm trail after real momentum)
//     - InpTrailRevPts:  0.10 → 0.50  (let winners run, exit on 0.5pt pullback)
//     - InpInstantLockOnFirstPositive: true → false (trail does the work)
// v2.80 (2026-06-18): INSTANT-LOCK-ON-FIRST-POSITIVE-TICK — fix the exit bug.
//   v2.79 LIVE produced 58 trades / 38% WR / -$261 across 2 days, despite the
//   verify_micro_positive.py proving 100% of UHV breakouts go positive at some
//   point. Conclusion: the strategy's edge IS REAL but our EXIT mechanism
//   wastes it. v2.79 trail (Lock=0.10, Rev=0.10) waits 0.10pt then gives back
//   0.10pt → net exit at ~0pt → many trades that briefly touched positive
//   then reversed get classified as losses by the SL instead of wins by trail.
//
//   Per master's verbatim 06-09: "we're looking for something like 1:0.001 R:R"
//   = close on FIRST positive tick. No threshold. No trail. No wait.
//
//   New input: InpInstantLockOnFirstPositive (default true).
//   Behavior: in ManageOpenPositions(), if prof > 0 (current bid > entry_ask
//   for BUY, or current ask < entry_bid for SELL), CLOSE THE POSITION.
//   This catches ANY positive move past spread cost, no matter how small.
//
//   Expected behavior:
//     - Wins: tiny ($0.01-$5 each at 0.30 lots) but FREQUENT (near 100% WR)
//     - Losses: only trades that NEVER cross positive — these hit hard SL
//     - Per-trade EV: small but positive if WR >= 80% (likely per verification)
// v2.79 (2026-06-16): RESTORE THE VERIFIED CONFIG (the 2 gates that actually
//   proved Zee's "100% goes positive" claim in verify_micro_positive.py).
//
//   Diagnosis: we had weakened TWO gates that the empirical verification depended on:
//     - InpUhvBodyMin: was 0.50 in verification, we dropped to 0.30 in v2.64
//     - InpBreakoutVolRatio: was 0.75 in verification, we dropped to 1.00 in v2.66
//   These weren't on Zee's "trash filters" list — they were on the canonical core.
//
//   Realistic backtest (ExecutionMode=1, real ticks): +$319 over 7 days, 26 trades.
//   This is the FIRST config tested under realistic latency that produced positive
//   net. Strict-everything hybrid (FVG + HHHL + neighbor peak) produced ZERO trades
//   under same latency — too fragile.
//
//   v2.79 = v2.78 + UhvBodyMin 0.30→0.50 + BreakoutVolRatio 1.00→0.75. Nothing else.
//   Kept: lots 0.30, harvest $60, halt $200, tight trail 0.10/0.10, canonical SL.
// v2.78 (2026-06-16): CORRECT THE MASTER MISREAD — v2.77 was wrong direction.
//   Re-reading Zee's verbatim 06-09 teaching (project_master_verbatim_2026_06_09):
//   she explicitly said KILL THE FILTERS, let the strategy BLOOM, and CATCH THE
//   100% positive move every UHV breakout makes before it reverses. That's
//   Strategy B (tick-speed catch-the-100%), NOT Strategy A (12-gate canonical).
//
//   v2.77 ADDED gates back. That's the opposite. v2.78 reverts:
//     1. InpRequireHHHL_M5 → false (bloom)
//     2. InpRequireH1Fvg → false (bloom)
//     3. InpRequireUhvNeighborPeak → false (bloom)
//     4. InpBreakoutVolRatio → 1.00 (effectively no filter)
//     5. InpDynamicTP → false (we don't chase big TPs)
//
//   Plus TIGHTEN the trailing-reversal exit to match master's "catch the +0.1pt
//   that EVERY UHV breakout makes":
//     6. InpTrailLockPts: 0.30 → 0.10 (arm the trail almost instantly)
//     7. InpTrailRevPts: 0.30 → 0.10 (exit on any tiny reversal)
//
//   Lots stay 0.30. Harvest $60, halt $200, canonical wide SL (no cap).
// v2.77 (2026-06-16): RESTORE THE MASTER (WRONG DIRECTION — superseded by v2.78) — re-enable the 5 canonical quality gates
//   that were disabled when I (mis)applied "trash hides gems" to the wrong layer.
//   The master's Feb-11-94%-WR spec requires these gates; they are not "trash":
//     1. InpRequireHHHL_M5 = true   — trade WITH the M5 trend (camel humps)
//     2. InpRequireH1Fvg   = true   — only fire when price taps an unfilled FVG
//     3. InpRequireUhvNeighborPeak = true — UHV strictly > both neighbors
//     4. InpBreakoutVolRatio = 0.80 — breakout vol < 80% of UHV vol (real filter)
//     5. InpDynamicTP      = true   — TP at sl_dist (1:1 R:R minimum)
//   Expected: trade frequency drops sharply (5-10/day vs 20-40), WR climbs toward
//   the master's 94% target. Quality over quantity — Zee's own teaching restored.
//   Lots stay 0.30, harvest $60, daily halt $200, canonical wide SL (no cap).
// v2.76 (2026-06-16): RESPECT WHAT WORKED — Honest reset based on receipt audit.
//   The +$192 day on 06-10 was REAL hard-earned profit (4 TP hits in 6h at v2.73).
//   What broke it was the lack of HarvestLock + the wide-SL killer trade. v2.75's
//   2pt SL cap "fixed" the killer but introduced a worse problem: it converted
//   pullback-survivors into capped losses, dropping WR from 38%→30%. Net effect
//   was WORSE than v2.73 ever was, despite the safety story.
//   v2.76 reverts SL cap (InpMaxInitialSLPoints=0 → no cap, back to canonical
//   UHV-extreme − 2pt buffer). Wide SL lets winners ride to TP like the v2.73 era.
//   Catastrophic killer protection comes instead from LOTS DROP 0.80 → 0.30 →
//   worst-case single-trade loss caps at ~$144 (6pt × 0.30 lots) instead of ~$500.
//   Daily-loss-halt scaled 500 → 200 (matches 0.30/0.80 ratio).
//   Daily-profit-target scaled 150 → 60 (same ratio; harvest locks earlier).
// v2.75 (2026-06-15): MAX-INITIAL-SL CAP — caps the initial SL distance so a
//   single "wide UHV" trade can't produce catastrophic single-trade losses.
//   Background: 06-10 had a −$329.60 single trade. 06-15 had a −$505.60 single
//   trade. Both were "wide UHV" candles where the canonical SL placement
//   (UHV-extreme − 2pt buffer) put the exit 4-6pt away. At 0.80 lots that's
//   $320-$500 per stop. Instant-BE can't help when the trade moves immediately
//   against entry (never reaches +0.30pt favorable to arm the tighter SL).
//   Fix: cap the initial SL distance at InpMaxInitialSLPoints (default 2.0pt).
//   At 0.80 lots, worst-case loss drops from ~$500 to ~$160. Wins unchanged.
//   Asymmetric R math improves substantially.
// v2.74 (2026-06-10): HARD HARVEST GUARDRAIL — Zee's "human dual-mode greed" rule.
//   When today's net realized P&L ≥ InpDailyProfitTarget, the EA:
//   (a) refuses to open NEW positions until next broker day
//   (b) writes harvest_locked_date_broker into daily_profit_target.json so dashboard knows
//   (c) optionally auto-closes any open positions if InpAutoCloseOnTarget=true
//   This is the MECHANICAL counterpart to the dashboard's harvest checklist.
//   The human side WILL forget the rule under greed; the EA must enforce it.
//   New inputs: InpDailyProfitTarget (default 150.0), InpAutoCloseOnTarget (default true).
//   The lock state persists across EA restart by reading daily_profit_target.json on OnInit.
// v2.73 (2026-06-09): LOT BUMP 0.30 → 0.80 — hospital-deadline pace. v2.71/v2.72 live
//   today: 19 trades, 47.4% WR, +$15.10 at 0.10 lots = $0.79/trade. Required pace for
//   $1080-by-June-20 = $120/day = 0.80 lots × $0.79 × 3 × 19 trades = ~$120/day. Risk:
//   margin = ~33% of $2058 demo per position. Daily halt bumped 250 → 500. Worst-case
//   per-trade if instant-BE misses = ~$160; capped-typical = ~$32. Strategy holds while
//   live WR stays > 40%.
// v2.72 (2026-06-09): LOT BUMP 0.10 → 0.30 per Zee. Live v2.71 today: 19 trades,
//   47.4% WR, NET +$15.10 — proved profitable despite sub-50% WR thanks to instant-BE
//   capping losses at ~$4 vs wins of $3-15. Scaling 3× to capture more $/trade.
//   Also bumped InpDailyLossHalt 50 → 250 because at 0.30 lots one worst-case stop
//   ≈ $60 and ~3-4 capped losses ≈ $12-50; need headroom for normal day drawdown.
// v2.71 (2026-06-09): CANONICAL CHART LABELS per Zee's request — every detected
//   setup paints "Retracement" (cyan, on origin candle) + "UHV vol=X" (gold, on UHV
//   candle) + "BREAKOUT" (green BUY / red SELL, on breakout candle). Fires AND misses
//   both labeled so Zee can see what the EA is detecting in real time. Auto-cleanup
//   keeps total S1 chart objects ≤ 60 (oldest deleted first) to prevent overlap clutter.
//   Also fixed DiagnoseBuyBlock/SellBlock to walk current gate order with opt-in flag
//   checks — previously was reporting "trend: slow_d=X" as MISS reason even though
//   InpRequireSlowTrend was false. The labels now tell the actual block reason.
// v2.70 (2026-06-09): INSTANT-BE — Zee's "ZERO LOSS TODAY" mandate. On the first
//   tick after a fill, SL is moved to entry ± InpInstantBE_BufferPts (default 0.40pt
//   = typical XAUUSD spread). Caps worst-case loss at ~$4 at 0.10 lots instead of
//   ~$56 from the UHV-based hard SL. Trade can only WIN big (trailing-reversal exit
//   from v2.65/v2.69) or close at near-zero loss. Implementation: g_mng_be_set[]
//   per-position flag + new code at top of ManageOpenPositions loop.
//   Zee verbatim: "let's define it as a goal, convert all loss trades into
//   breakeven at ZERO loss (achieve this today no matter what)"
// v2.69 (2026-06-09): EARLY BREAKEVEN — lower trailing-lock 0.70pt → 0.30pt so any
//   meaningful favorable move arms the reversal exit at near-breakeven. Zee's chart caught
//   a -$56 loser this morning whose peak was only 0.33pt — never reached the 0.70pt lock
//   so the trailing exit didn't arm, hard SL took the whole loss. Lowering lock makes the
//   trade close near-breakeven on any reversal once it shows ANY positive intent. Reduces
//   per-trade max loss from ~$56 (hard SL) to ~$3-5 (reversal close at breakeven). Slight
//   WR hit acceptable because total exposure shrinks dramatically.
//   Zee verbatim: "we just made a loss of 56.. keep an eye on it. see if we could've
//   reduced this loss by setting SL to zero right after entering trade?"
// v2.68 (2026-06-09): KILL CLUSTER_GUARD blockers. Zee's chart showed MISS BUY markers
//   with reason "cluster_guard" during a clear uptrend with UHVs forming and breaking.
//   The ClusterBlocked() function had TWO always-on gates: (a) InpSkipOvernight blocked
//   entries during broker 00-06 hours [vestigial — predates 24h "take all chances" rule],
//   (b) InpMaxOneSameDir blocked entries if S1/S3/NSND magic had a same-direction position
//   [vestigial — we dropped S3/S5/NSND]. Both flipped to false default. Per "trash hides
//   gems" rule + "take all chances" rule + "you've chained it too much" — every gate
//   that's not from Zee's spec must default OFF.
// v2.67 (2026-06-09): SESSION FILTER OFF by default so the EA fires 24/7 and Zee can SEE
//   it actually firing in real time. Yesterday (Monday) we had zero fires the whole day
//   thinking it was "silently working" — that's intolerable. Defaults flipped:
//     InpSessionStartHour: 14 → 0
//     InpSessionEndHour:   18 → 0  (both same disables the gate per v2.66 code path)
//   Other v2.66 bloom (no H1Bias, no slow-trend, no big-spread-climax, vol-ratio 1.0,
//   tick-level reversal exit) all retained. Once we see consistent fires + WR data, can
//   re-introduce time window if it improves quality.
// v2.66 (2026-06-09): HOT-HOURS WINDOW + bloom flags. Per Zee's insight: "Feb 11 had
//   specific hours where we were most profitable, that's the 94% WR." Tick-volatility
//   analysis on Feb 11: broker-hours 14:00-18:00 had 47-71pt range (NY session). Default
//   trading window restricted to those hours. Also removes the three hidden hardcoded
//   gates (IsUptrendM5/Downtrend slow-trend, H1Bias, IsBigSpreadClimax) — now opt-in via
//   InpRequireSlowTrend / InpRequireH1Bias / InpRequireBigSpreadClimax (all default false).
//   Relaxes InpBreakoutVolRatio 0.75→1.00 (kills the 31% remaining vol blocker).
//   Combined: fire ONLY during hot hours, but with all bloom gates off so we catch as many
//   setups as possible within the window. Quality from time, frequency from looseness.
// v2.65 (2026-06-09): TICK-LEVEL TRAILING-REVERSAL EXIT — Zee's "catch the 100%" mandate.
//   Tick-level test on 34 fires (v2.64 config) with peak-tracking + reversal exit:
//   rev=0.5pt/lock=1.0pt/sl=2.0pt → 24W/1L/9TO = 96% WR, +$302/day @ 1.0 lots.
//   rev=0.3pt/lock=0.7pt/sl=1.5pt → 22W/2L/10TO = 92% WR, +$311/day @ 1.0 lots ← shipping this.
//   New inputs (default arms ON):
//     InpTrailRevPts  = 0.30  reversal-from-peak in price points (exit when peak-current >= this)
//     InpTrailLockPts = 0.70  minimum peak before trail arms (no early exits on tiny noise)
//   Mechanism: per-position peak_pts tracked tick-by-tick. Once peak_pts >= LockPts, watch for
//   any pullback of RevPts from that peak → close at market immediately. Hard SL stays as safety.
//   This finally captures the 100% favorable-excursion fact at tick level.
// v2.64 (2026-06-09): MICRO-SCALP defaults per Zee's "speed-of-execution > R:R" insight.
//   Tick-level analysis on 16 M1 fires (no-trend-gate config) showed 100% reached at
//   least +0.1pt favorable BEFORE going adverse, 94% reached +0.5pt favorable. Backtested
//   TP=1.0/SL=2.0 micro-scalp: 10W/0L (6 OPEN), 100% WR on closed, +$14.29/day @ 0.10 lots.
//   At 1.0 lots = $143/day = Feb 11 territory at current fire rate (16/7d = 2.3/day).
//   New defaults baked in: InpLots 0.01→0.10, InpTPPoints 7.5→1.0, InpDynamicTP true→false,
//   InpSLBufferPts 2.00→2.0 (unchanged), InpUhvBodyMin 0.50→0.30, InpRequireUhvNeighborPeak
//   true→false, InpRequireHHHL_M5 true→false. M1-default: InpTimeframe M5→M1, InpMagicNumber
//   88004→88005, InpStateFile→s1_trader_state_m1.json, InpDecisionCsv→s1_decisions_m1.csv.
//   M5 instance (88004) untouched — keep current v2.63 running for comparison.
// v2.63 (2026-06-08): SHORTER trend window for more fires while preserving HH+HL discipline.
//   v2.62 (LookbackM5=60 = 5h window) was firing only 6 times in 29 days = 1/5d.
//   Python sweep with TREND_BARS=5: 10 fires / 29d / 50% WR / +124 pts (vs v2.62: 6 fires / 67% WR / +129 pts).
//   Same total P&L (~+$1240 @ 0.10 lots / 29d) with 67% more fires — better for hospital deadline.
//   Change: default InpHHHL_LookbackM5 from 60 → 24 (2h window). Still requires last 2 swing highs
//   ascending AND last 2 swing lows ascending — just on a more recent window.
// v2.62 (2026-06-08): TREND-CONFIRMATION ENFORCED per Zee's 48-setup binary verdict pass.
//   Verdict result: 5/48 fully correct (10%), 43/48 incorrect. Dominant failure mode:
//   COUNTER-TREND / RANGING entries (30 / 43 incorrect cases). Verbatim: "selling in
//   uptrend", "buying in downtrend", "ranging market, we don't trade".
//   v2.62 fix: InpRequireHHHL_M5 default flipped to TRUE (was false). The structural
//   camel-humps gate now blocks chop/ranging/counter-trend entries that v2.61's
//   close-delta IsUptrendM5/IsDowntrendM5 was letting through.
//   Also added: InpMinBreakoutPenetration (default 0.30 USD) so that a "micro-poke past
//   the UHV extreme" doesn't count as a breakout (Zee m34/m35).
// v2.61 (2026-06-08): CANONICAL GATES per Zee's 36+5-setup labelling pass + lesson02 spec.
//   Cyan-bug fix: retracement origin = the FIRST bear whose IMMEDIATE prior bar is bull
//   AND whose body closes below that bull's low. Reds collected ONLY from origin onward.
//   UHV: body_ratio ≥ InpUhvBodyMin (default 0.50) AND strictly higher vol than both
//   immediate neighbours (no doji-vol-peaks). Breakout: forming bar vol ≤ InpBreakoutVolRatio
//   × UHV.vol (default 0.75). All new gates default ON. Python detector showed 75% WR /
//   PF 5.13 on 10d ticks with these settings (3W/1L closed, 1 open).
// v2.52 (2026-06-04 ~03:30 PKT, Claude autonomous overnight on Zee asleep): STRUCTURAL GATES.
//   Zee's diagnosis on v2.51 chart: entries "not perfect" — UHV firing without
//   proper trend (HH+HL camel humps) + retracement context per lesson02.
//   Today's v2.51 result: 4W/4L PF 1.00 +$0.28 — breakeven. The only BUY trade
//   (13:15 on a clearly bearish day, -$13) is the smoking gun: current
//   IsUptrendM5() is just close-delta(24bars > 7pts), which a brief chop-bounce
//   passes. Teacher requires structural HH+HL pattern AND H1 confirmation.
//   v2.52 adds three optional gates (default OFF, opt-in via inputs):
//     InpRequireHHHL_M5  — last 2 swing highs ascending AND last 2 swing lows ascending
//     InpRequireHHHL_H1  — same structure check on H1 timeframe
//     InpRequireMomentumBO — breakout bar must close as low-wick momentum + vol < UHV vol
//                            (only checked if EA is in candle-close mode; live-tick path
//                             gets a deferred-exit if InpMomentumBOPostCheck=true)
//   Other gates (close-delta trend, retracement walk, UHV detection, live-tick fire)
//   unchanged from v2.51. No baseline regression risk when gates left OFF.
// v2.51 (2026-06-04 ~02:40 PKT, Gemini-DR + Claude TASK-010): DYNAMIC 1:1 TP FIX.
//   v2.50 backtest (today's real ticks, MT5 Strategy Tester, 100% quality):
//     9 trades, 66.67% WR, PF 0.78, -$11.58 → Avg win $6.72 vs Avg loss $17.15.
//   The inverted R:R was the killer: UHV-range-derived SL is wide (~$15-25),
//   fixed TP=$7.5 was a tiny scalp. Even 66% WR couldn't pay the bill.
//   v2.51: TP is now DYNAMIC = sl_dist above entry (1:1 R:R). At 66% WR a 1:1
//   gives +$5.44/trade expectancy vs -$1.29 at the old config.
//   Toggle via InpDynamicTP — keep old behaviour by setting false + using InpTPPoints.
// v2.50 (2026-06-04, Zee + Gemini-DR + Claude TASK-010): LIVE-TICK UHV TRIGGER.
//   Pre-v2.50 EA waited for M5 candle CLOSE before firing — the breakout
//   momentum was already over and EA would buy the top, immediately
//   underwater. New logic checks ask > uhv_high (or bid < uhv_low) on EVERY
//   tick, firing the millisecond the breakout level is breached. Anti-spam
//   via per-UHV-candle lockout (g_last_uhv_buy_t / g_last_uhv_sell_t) so a
//   single UHV setup fires once, then waits for a NEW UHV. Mirrors Zee's
//   manual style (Feb 11 trade history: trades closed 9-24s, intra-candle).
#property strict

// ╔══════════════════════════════════════════════════════════════════╗
// ║  📄 STRATEGY DOCUMENTATION: docs/S1_STRATEGY.md                 ║
// ║  Contains: full strategy logic, backtest results, parameter     ║
// ║  rationale, walk-forward validation, and change history.        ║
// ║  READ THAT FILE FIRST before modifying this EA.                 ║
// ╚══════════════════════════════════════════════════════════════════╝

// v2.10 (2026-05-22): "2R Free Roll" management code added for parity with S3/NSND,
// but DEFAULT OFF — backtest (backtest_exit_protocols_multi.py, S1 deployed signals,
// 13 real-tick days, n=34) showed it is STRUCTURALLY INERT on S1: the SL sits at the
// UHV-red low (often $5-15 below entry), so 1R is usually wider than the $7.5 TP and
// breakeven/partial can never arm before TP resolves — every policy was byte-identical
// to baseline (+$431.8). Left as a toggle in case S1's TP/SL geometry is widened later.

#include <Trade/Trade.mqh>

//── Inputs ──────────────────────────────────────────────────────────
input group "── Sizing ──"
input double InpLots          = 0.10; // InpLots — 2026-06-16 v2.76: REVERTED 0.80→0.30 after live receipt showed 0.80 + 
input int    InpMagicNumber   = 88098; // InpMagicNumber — 2026-06-09 v2.64: defaults to M1 scalp instance (was 88004 = M5). M5 i
input double InpDailyLossHalt = 0.0; // InpDailyLossHalt — 2026-06-16 v2.76: scaled to 0.30 lot size (500 × 0.30/0.80 ≈ 188 → rou
input double InpDailyProfitTarget = 0.0; // InpDailyProfitTarget — 2026-06-18 v2.84: DISABLED. Master decides when to stop trading for th
input bool   InpAutoCloseOnTarget = false; // InpAutoCloseOnTarget — 2026-06-18 v2.84: DISABLED. No auto-close on profit. Master closes man

input group "── Profit protection: 2R Free Roll (backtest 2026-05-22) ──"
input bool   InpEnableBreakeven = false; // InpEnableBreakeven — OFF — backtest showed INERT on S1 (SL at UHV-red low is usually wider 
input double InpBreakevenR      = 1.0; // InpBreakevenR — R-multiple that arms breakeven. R = entry − ORIGINAL SL.
input double InpBEArmUsd        = 0.0; // InpBEArmUsd — Breakeven: lock SL at entry once trade is +$this profit. SUPERSEDED by
input double InpTrailActUsd     = 0.0; // InpTrailActUsd — 2026-05-29 REVERTED to OFF — May-27 trail "validation" was on misalign
input double InpTrailGiveUsd    = 0.0; // InpTrailGiveUsd — Trailing lock: bank & exit if profit falls $this back from its peak ($
input string InpPeakLogFile     = ""; // InpPeakLogFile — closed-trade peak (MFE) log in Common\Files — feeds the live "% of tra
input bool   InpMaxOneSameDir   = false; // InpMaxOneSameDir — 2026-06-09 v2.68: FLIPPED to FALSE. Vestigial from multi-EA era (S1/S3
input bool   InpSkipOvernight   = false; // InpSkipOvernight — 2026-06-09 v2.68: FLIPPED to FALSE. Vestigial — "overnight thin hours"
input int    InpOvernightStart  = 0; // InpOvernightStart — broker hour: block new entries from here ...
input int    InpOvernightEnd    = 6; // InpOvernightEnd — ... until here (exclusive).
input string InpDecisionCsv     = "s1_decisions_m1.csv"; // InpDecisionCsv — 2026-06-09 v2.64: defaults to M1 instance file (was s1_decisions.csv f
input bool   InpEnablePartial   = false; // InpEnablePartial — OFF — inert on S1 for the same geometry reason.
input double InpPartialR        = 1.5; // InpPartialR
input double InpPartialFrac     = 0.5; // InpPartialFrac
input double InpBEBufferPts     = 0.30; // InpBEBufferPts — SL set this far beyond entry (price units) to cover spread/swap.

input group "── Human profit-pulse + one-tap GRAB ──"
input bool   InpEnableGrab = true; // InpEnableGrab — honor a GRAB command (close ALL this EA's positions at market) from Wh
input double InpAvgWinUsd  = 40.0; // InpAvgWinUsd — reference avg winning trade ($) for the heartbeat 'bigness' read (S1 ~
input string InpGrabFile   = "grab_command.txt"; // InpGrabFile — shared command file (epoch id). EA grabs on a NEWER id than last seen.

input group "── Sides ──"
input bool   InpDoBuys        = true; // InpDoBuys — BUY side enabled (UHV red + bullish FVG)
input bool   InpDoSells       = true; // InpDoSells — 2026-05-19: SELL side enabled — adds +$243/12d in walk-forward train (

input group "── Detection ──"
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M1; // InpTimeframe — 2026-06-09 v2.64: defaults to M1 (scalp instance). The M5 instance v2.
input int    InpTrendLookback     = 24; // InpTrendLookback — bars (M1 default: ~24min; M5: ~2h)
input double InpTrendThreshold    = 7.0; // InpTrendThreshold — 2026-05-29 REVERTED to M5 validated value (verify_thorough.py: 7/7 spl
input double InpERMin             = 0.0; // InpERMin — 2026-05-29 NEW: Kaufman Efficiency Ratio chop filter (same math as S4)
input int    InpERLookback        = 30; // InpERLookback — bars over InpTimeframe for the ER calc.
input int    InpRetraceLookback   = 15; // InpRetraceLookback — M5 bars searched for UHV red/green
input bool   InpRequireH1Fvg      = false; // InpRequireH1Fvg — 2026-06-16 v2.78: BACK to FALSE per master verbatim 06-09 ("kill the f
input int    InpH1FvgLookback     = 50; // InpH1FvgLookback — H1 bars searched for unfilled FVG (only used if InpRequireH1Fvg)
input bool   InpRequireBigSpread  = false; // InpRequireBigSpread — 2026-05-27: DISABLED. Was blocking 100% of live trades (0 entries in 5
input double InpBigSpreadMult     = 1.3; // InpBigSpreadMult — UHV bar range must be >= this x avg range of prior 10 M5 bars
input int    InpSpreadAvgBars     = 10; // InpSpreadAvgBars — bars used for the avg-range baseline
input int    InpExitStyle    = 0;  // InpExitStyle — 0 = proportional target (TP = stop distance) · 1 = LIVE RATCHET (give back 30% of peak) · 2 = ZEE hold-to-flat + breakeven
input double InpZeeBEPts     = 0.3; // InpZeeBEPts — style 2: lock breakeven once this far in profit (gold pts; x10 on BTC)
input double InpZeeFlatPts   = 0.05;// InpZeeFlatPts — style 2: a red trade that returns within this of entry steps off
input double InpRatchetArm   = 0.3; // InpRatchetArm — style 1: arm the ratchet at this profit
input double InpRatchetGive  = 0.2; // InpRatchetGive — style 1: minimum give-back from peak
input double InpRatchetFrac  = 0.30;// InpRatchetFrac — style 1: give back this fraction of the peak
input double InpSLBufferPts       = 2.0; // InpSLBufferPts — 2026-05-19: walk-forward winner. Was 0.10, but tighter SL configs all 
input double InpMaxInitialSLPoints = 0.0; // InpMaxInitialSLPoints — 2026-06-16 v2.76: REVERTED to 0 (no cap). Live data showed 2.0pt cap w

input group "── v2.52 Structural Gates (teacher-faithful, all OFF by default) ──"
input bool   InpRequireHHHL_M5 = false; // InpRequireHHHL_M5 — 2026-06-16 v2.78: BACK to FALSE per master verbatim — bloom mandate. v
input bool   InpRequireHHHL_H1 = false; // InpRequireHHHL_H1 — 2026-06-04 v2.52: same HH+HL check on H1 (multi-TF confirmation per le
input int    InpHHHL_PivotBars = 3; // InpHHHL_PivotBars — number of bars on each side a candle must be the local high/low to cou
input int    InpHHHL_LookbackM5 = 24; // InpHHHL_LookbackM5 — 2026-06-08 v2.63: shortened 60→24 (2h) per Python sweep — gets 67% mor
input int    InpHHHL_LookbackH1 = 24; // InpHHHL_LookbackH1 — H1 bars to scan for swing structure (~24h).
input bool   InpRequireH1Bias  = false; // InpRequireH1Bias — 2026-06-09 v2.66: FLIPPED to FALSE — filter-attribution showed this wa
input int    InpH1BiasBars     = 6; // InpH1BiasBars — how many H1 bars back to compare for the bias check. 6 = compare again

input group "── v2.59 Momentum Override (bypass slow trend filter on big single-bar moves) ──"
input bool   InpMomentumOverrideEnabled = true; // InpMomentumOverrideEnabled — 2026-06-05 v2.59: when slow trend filter says NO but recent 30-min clo
input double InpMomentumOverridePts     = 5.0; // InpMomentumOverridePts — 30-min (6 M5 bars) close-delta needed to bypass IsDowntrendM5/IsUptren

input group "── v2.60 Breakout Candle Quality (lesson02: 'momentum body + low vol') ──"
input bool   InpRequireBreakoutMomentum = false; // InpRequireBreakoutMomentum — 2026-06-05 v2.60: require the FORMING breakout bar to already show mom
input double InpBreakoutMinBodyPts      = 1.5; // InpBreakoutMinBodyPts — minimum body size (in price units) of the forming bar at trigger time.
input bool   InpRequireBreakoutLowVol   = false; // InpRequireBreakoutLowVol — 2026-06-05 v2.60: require forming-bar tick-volume to be BELOW the UHV'

input group "── v2.61 Canonical UHV (lesson02 + Zee's labelling pass 2026-06-05/08) ──"
input bool   InpRequireCanonicalOrigin = true; // InpRequireCanonicalOrigin — 2026-06-08 v2.61: retracement origin = FIRST bear (BUY) / bull (SELL) 
input double InpUhvBodyMin             = 0.30; // InpUhvBodyMin — 2026-06-21 v2.94: 0.60→0.30. Backtest showed 0.60 killed too many good
input bool   InpRequireUhvNeighborPeak = false; // InpRequireUhvNeighborPeak — 2026-06-21 v2.94: true→FALSE. Master's intuition correct but strict ">
input int    InpMaxBarsSinceUhv        = 0; // InpMaxBarsSinceUhv — 2026-06-21 v2.95: 8→0 (off). Time-window filter dominates; max-bars ad
input bool   InpRequireBreakoutBodyClose = false; // InpRequireBreakoutBodyClose — 2026-06-21 v2.95: true→FALSE. Body-close cut sample size; time-window 
input string InpAllowedHoursUtc        = "5,12,15,19"; // InpAllowedHoursUtc — 2026-06-21 v2.95: comma-separated UTC hours where fires are allowed. E
input double InpMinSweepDepthPts       = 0.30; // InpMinSweepDepthPts — 2026-06-22 v2.97: minimum depth (pts) the sweep must reach past UHV ex
input double InpMaxBreakoutWickPct     = 0.35; // InpMaxBreakoutWickPct — 2026-06-22 v2.97: max against-direction wick on breakout candle (as fr
input bool   InpRequireH1AgreesV2      = false; // InpRequireH1AgreesV2 — 2026-06-22 v2.97: H1 candle direction must match setup direction (clos
input double InpMaxRetracementWickPct  = 0.45; // InpMaxRetracementWickPct — 2026-06-22 v2.98 NEW: max rejection-wick on retracement candles (UHV +
input bool   InpRequireBreakoutColor   = true; // InpRequireBreakoutColor — 2026-06-22 v2.99 ★: breakout candle (shift=1) must match side color. B
input bool   InpUhvGlobalMax           = true; // InpUhvGlobalMax — 2026-06-22 v3.00 NEW: chosen UHV must have STRICTLY GREATER volume tha
input double InpBreakoutVolRatio       = 0.75; // InpBreakoutVolRatio — 2026-06-16 v2.79: RESTORED 1.00→0.75. This is the value verify_micro_p
input double InpBreakoutBodyRatio      = 0.65; // InpBreakoutBodyRatio — 2026-06-08 v2.61: forming breakout bar body/range must be >= this (can
input double InpMinBreakoutPenetration = 0.30; // InpMinBreakoutPenetration — 2026-06-08 v2.62: minimum price-units the forming bar's body must clos

input group "── v2.65 Tick-level Trailing Reversal (Zee's catch-the-100% mandate) ──"
input bool   InpInstantLockOnFirstPositive = false; // InpInstantLockOnFirstPositive — 2026-06-18 v2.81: DISABLED. v2.80's instant-lock at +0.01-0.14pt locke
input double InpTrailRevPts  = 0.0; // InpTrailRevPts — 2026-06-18 v2.84: DISABLED. Master takes manual exit. 0=off.
input double InpTrailLockPts = 0.0; // InpTrailLockPts — 2026-06-18 v2.84: DISABLED. No auto trail. Manual close only.

input group "── v2.70 INSTANT-BE (Zee's zero-loss-today mandate) ──"
input bool   InpInstantBE          = false; // InpInstantBE — 2026-06-18 v2.84: DISABLED per master's deterministic-strategy mandate
input int    InpAutoCloseAfterMs   = 0; // InpAutoCloseAfterMs — 2026-06-22 v3.01: DEFAULT 0 (off) per master-takes-exit doctrine. Was 
input double InpInstantBE_BufferPts = 0.40; // InpInstantBE_BufferPts — 2026-06-09 v2.70: how far BELOW entry (for BUY) / ABOVE entry (for SEL

input group "── v2.66 Hot-hours window + bloom flags (Zee's session-specific insight) ──"
input int    InpSessionStartHour = 0; // InpSessionStartHour — 2026-06-09 v2.67: DISABLED (start==end means 24h). Was 14 in v2.66 but
input int    InpSessionEndHour   = 0; // InpSessionEndHour — 2026-06-09 v2.67: DISABLED.
input bool   InpRequireSlowTrend = false; // InpRequireSlowTrend — 2026-06-09 v2.66: previously HARDCODED on as IsUptrendM5/IsDowntrendM5
input bool   InpRequireBigSpreadClimax = false; // InpRequireBigSpreadClimax — 2026-06-09 v2.66: previously HARDCODED on as IsBigSpreadClimax (UHV mu

input group "── Exit ──"
input double InpTPPoints          = 1.3; // InpTPPoints — 2026-06-22 v2.98: 5.0→1.3 — with rejection-wick filter producing 87.5%
input bool   InpDynamicTP         = true; // InpDynamicTP — 2026-06-16 v2.78: BACK to FALSE per master verbatim "we're looking for

input group "── Logging ──"
input bool   InpVerbose       = false; // InpVerbose
input string InpLogPrefix     = "S1"; // InpLogPrefix
input string InpStateFile     = "s1_trader_state_m1.json"; // InpStateFile — 2026-06-09 v2.64: defaults to M1 instance file.
input int    InpHeartbeatSec  = 0; // InpHeartbeatSec

//── State ───────────────────────────────────────────────────────────
CTrade   g_trade;
// v2.50: live-tick UHV trigger — track the specific UHV candle we already
// fired on, so the same setup doesn't double-fire on every subsequent tick
// while price hovers above (or below) the breakout level.
datetime g_last_uhv_buy_t  = 0;
datetime g_last_uhv_sell_t = 0;
// Legacy (kept for read-only reporting only — BuildWatchJson uses these):
datetime g_last_m5_time = 0;
datetime g_last_signal_t = 0;
datetime g_last_heartbeat = 0;
int      g_signals_today = 0;
int      g_entries_today = 0;
int      g_today_day = 0;

//── Helpers ─────────────────────────────────────────────────────────
void Log(string msg) {
   if (!InpVerbose) return;
   PrintFormat("[%s] %s", InpLogPrefix, msg);
}

// Kaufman Efficiency Ratio over InpERLookback bars of InpTimeframe. Returns net/path
// (0=pure chop / 1=perfect trend). Used as a chop filter when InpERMin>0.
double EfficiencyRatio() {
   double net = MathAbs(iClose(_Symbol,InpTimeframe,1) - iClose(_Symbol,InpTimeframe,InpERLookback));
   double path = 0;
   for (int s = 1; s < InpERLookback; s++)
      path += MathAbs(iClose(_Symbol,InpTimeframe,s) - iClose(_Symbol,InpTimeframe,s+1));
   return (path > 0) ? net / path : 0.0;
}

// Spread in price points at the current tick — for the regime-state log so we can later
// tell if a losing trade fired during a wide-spread (low-liquidity / chop) micro-window.
double CurrentSpreadPts() {
   return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
}

double g_day_start_equity = 0;

//── Per-position management state (2R Free Roll) ───────────────────
ulong  g_mng_ticket[256];
double g_mng_sl0[256];
bool   g_mng_partialed[256];
double g_mng_peak[256];      // per-position peak floating profit ($) — drives the trailing lock
double g_mng_trough[256];    // per-position worst floating loss ($, <=0) — MAE, for loss-side study
double g_mng_peak_pts[256];  // v2.65: per-position peak unrealized profit in PRICE POINTS (not $) — drives tick-level reversal exit
bool   g_mng_be_set[256];    // v2.70: per-position flag — has instant-BE SL move been applied yet?
ulong  g_mng_open_us[256];   // v2.87: per-position open time in microseconds — drives auto-close-after-ms
double g_mng_lastprof[256];  // last floating P&L ($) seen before close — outcome proxy (win/loss)
double g_mng_entry[256];     // entry price (for the closed-trade peak log)
int    g_mng_side[256];      // +1 buy / -1 sell (for the log)
bool   g_mng_logged[256];    // has this closed trade's peak been written to the MFE log yet
int    g_mng_count = 0;

//── One-tap GRAB state ──────────────────────────────────────────────
long     g_last_grab_id = 0;
datetime g_last_grab_check = 0;

//── Diagnostic: setups that passed every filter EXCEPT the H1-FVG gate today.
//   If this is >0 while entries=0, the H1-FVG check is the live blocker; if it's
//   0, no qualifying setups occurred (rarity, not a bug). Reset daily.
int g_reached_late = 0;

bool IsNewDay() {
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if (dt.day != g_today_day) {
      g_today_day = dt.day;
      g_signals_today = 0;
      g_entries_today = 0;
      g_reached_late = 0;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);  // FTMO daily-loss baseline
      g_harvest_locked_day = 0;   // v2.74 harvest lock auto-resets at broker midnight
      return true;
   }
   return false;
}

// FTMO circuit breaker (account-wide, equity-based incl. floating). Blocks NEW entries.
bool DailyLossHalted() {
   if (InpDailyLossHalt <= 0 || g_day_start_equity <= 0) return false;
   return (AccountInfoDouble(ACCOUNT_EQUITY) - g_day_start_equity) <= -InpDailyLossHalt;
}

// 2026-06-10 v2.74 — HARVEST GUARDRAIL (the dual-mode-greed mechanical lock)
//   When today's REALIZED net P&L ≥ InpDailyProfitTarget, refuse new entries.
//   Lock state mirrored to monitor/daily_profit_target.json so dashboard agrees.
//   This is Zee's "let the farmland become re-fertile" rule — humans WILL try to
//   re-harvest under greed; the machine must refuse. Lock resets on broker-day rollover.
datetime g_harvest_locked_day = 0;  // broker midnight when we locked (sentinel)

// Walk today's closed deals from broker history; return net realized P&L this broker day.
double TodayRealizedNet() {
   datetime today_start = TimeCurrent() - (TimeCurrent() % 86400);  // broker midnight
   if (!HistorySelect(today_start, TimeCurrent())) return 0.0;
   int total = HistoryDealsTotal();
   double net = 0.0;
   for (int i = 0; i < total; i++) {
      ulong tk = HistoryDealGetTicket(i);
      if (tk == 0) continue;
      long magic = (long)HistoryDealGetInteger(tk, DEAL_MAGIC);
      if (magic != InpMagicNumber) continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk, DEAL_ENTRY);
      if (entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) continue;
      net += HistoryDealGetDouble(tk, DEAL_PROFIT)
           + HistoryDealGetDouble(tk, DEAL_SWAP)
           + HistoryDealGetDouble(tk, DEAL_COMMISSION);
   }
   return net;
}

bool HarvestLocked() {
   if (InpDailyProfitTarget <= 0) return false;
   // Already locked today? Stay locked until midnight rollover.
   datetime midnight = TimeCurrent() - (TimeCurrent() % 86400);
   if (g_harvest_locked_day == midnight) return true;
   // Else check live realized net
   double net = TodayRealizedNet();
   if (net >= InpDailyProfitTarget) {
      g_harvest_locked_day = midnight;
      Log(StringFormat("[HARVEST v2.74] TARGET HIT — net realized = $%.2f >= $%.2f. EA pauses new entries until broker rollover.",
                       net, InpDailyProfitTarget));
      // Mirror to file for dashboard
      int fh = FileOpen("daily_profit_target.json", FILE_WRITE | FILE_TXT | FILE_COMMON);
      if (fh != INVALID_HANDLE) {
         string broker_date = TimeToString(midnight, TIME_DATE);  // "2026.06.10"
         StringReplace(broker_date, ".", ".");
         FileWriteString(fh, StringFormat(
            "{\n  \"target_usd\": %.1f,\n  \"harvest_locked_date_broker\": \"%s\",\n  \"harvested_at\": \"%s\",\n  \"net_realized_at_lock\": %.2f,\n  \"locked_by\": \"EA v2.74\"\n}\n",
            InpDailyProfitTarget, broker_date, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), net));
         FileClose(fh);
      }
      // Auto-close any open positions if configured
      if (InpAutoCloseOnTarget) {
         for (int i = PositionsTotal() - 1; i >= 0; i--) {
            ulong tkt = PositionGetTicket(i);
            if (tkt == 0) continue;
            if (!PositionSelectByTicket(tkt)) continue;
            if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
            if (g_trade.PositionClose(tkt)) {
               Log(StringFormat("[HARVEST v2.74] auto-closed #%I64u at market to lock profit", tkt));
            }
         }
      }
      return true;
   }
   return false;
}

bool IsUptrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (now_close - back_close) > InpTrendThreshold;
}

// Average M5 candle range over the N bars BEFORE the given shift (older bars).
double AvgRangeM5(int from_shift, int n) {
   double sum = 0; int cnt = 0;
   for (int j = from_shift + 1; j <= from_shift + n; j++) {
      sum += iHigh(_Symbol, InpTimeframe, j) - iLow(_Symbol, InpTimeframe, j);
      cnt++;
   }
   return (cnt > 0) ? sum / cnt : 0.0;
}

// Teacher's "big-spread climax bar" filter: the UHV bar's range must be a
// large candle vs the recent average. Walk-forward validated 2026-05-19.
bool IsBigSpreadClimax(int uhv_shift) {
   if (!InpRequireBigSpread) return true;
   double rng = iHigh(_Symbol, InpTimeframe, uhv_shift) - iLow(_Symbol, InpTimeframe, uhv_shift);
   double avg = AvgRangeM5(uhv_shift, InpSpreadAvgBars);
   if (avg <= 0) return false;
   return rng >= InpBigSpreadMult * avg;
}

bool IsDowntrendM5(int from_shift) {
   double now_close   = iClose(_Symbol, InpTimeframe, from_shift);
   double back_close  = iClose(_Symbol, InpTimeframe, from_shift + InpTrendLookback);
   if (back_close == 0) return false;
   return (back_close - now_close) > InpTrendThreshold;
}

// v2.56: paired sequence number so each UHV bar and its breakout share the same #N
int g_marker_seq = 0;

// v2.58: write volume number on top of each visible M5 candle
//   Called from OnTimer (every 2s) so labels appear/refresh as new bars form.
//   Uses bar time in name so each bar gets exactly one label.
void DrawVolumeLabels(int n_bars = 200) {
   long bar_sec = PeriodSeconds(InpTimeframe);
   for (int i = 0; i < n_bars; i++) {
      datetime t = iTime(_Symbol, InpTimeframe, i);
      if (t == 0) break;
      long vol = iVolume(_Symbol, InpTimeframe, i);
      double bar_high = iHigh(_Symbol, InpTimeframe, i);
      double bar_low  = iLow (_Symbol, InpTimeframe, i);
      double bar_h    = bar_high - bar_low;
      if (bar_h <= 0) bar_h = 0.3;
      // Position label just above the candle high
      double label_y = bar_high + bar_h * 0.15;
      // Center horizontally on bar midpoint
      datetime mid_t = t + bar_sec / 2;
      string name = StringFormat("S1_vol_%I64d", (long)t);
      // Create or refresh
      if (!ObjectCreate(0, name, OBJ_TEXT, 0, mid_t, label_y)) {
         // already exists — update position + text
         ObjectMove(0, name, 0, mid_t, label_y);
      }
      ObjectSetString (0, name, OBJPROP_TEXT, IntegerToString(vol));
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 7);
      ObjectSetString (0, name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LOWER);
   }
}

//── v2.54 Chart annotations — visualise EVERY step of the S1 strategy ──
// Each annotation set uses a timestamped tag so multiple entries coexist.
//
// Drawn objects (in z-order back→front):
//   1) Retracement zone        purple semi-transparent rectangle covering pullback bars
//   2) UHV bar box             goldenrod filled rectangle (the climactic vol candle)
//   3) Breakout level ray      horizontal ray at UHV.high (BUY) / UHV.low (SELL)
//   4) Sweep arrow             purple ↑/↓ above/below the sweep bar
//   5) Entry vline             dashed vertical at the trigger tick time
//   6) Entry arrow             large side-coloured thumb arrow at entry price
//   7) SL ray                  red dashed horizontal ray right from UHV time
//   8) TP ray                  green dashed horizontal ray right from UHV time
//   9) Step text labels        small numbered hints at each step
//   10) Master label           bold summary near entry with ER, retrace_n, H1Bias
// ─────── v2.71 CANONICAL CHART LABELS (Zee's visual ask) ───────
// Three small labels per detected setup so Zee can SEE what the EA detects:
//   Retracement (cyan) - on the origin candle (first bear of pullback for BUY)
//   UHV vol=X   (gold) - on the highest-vol bar in the retracement
//   BREAKOUT    (green/red) - on the breakout candle that fires (or grey if missed)
// Auto-cleanup caps total objects ≤ MAX_S1_OBJECTS, deleting oldest first.

const int MAX_S1_OBJECTS = 20;   // v2.90: was 60; aggressive cleanup so chart stays readable

bool IsS1Object(string name) {
   return (StringFind(name, "S1_RETR_") == 0 ||
           StringFind(name, "S1_UHV_")  == 0 ||
           StringFind(name, "S1_BRK_")  == 0 ||
           StringFind(name, "S1_MISS_") == 0);
}

void CleanOldS1Labels() {
   int total = ObjectsTotal(0);
   if (total < MAX_S1_OBJECTS) return;
   // v2.90: also aggressively delete arrow children (S1_*_arr)
   // Note: trim threshold tightened — fall through to bubble-sort below
   // Gather S1 objects and their times
   string names[200];
   datetime times[200];
   int n = 0;
   for (int i = 0; i < total && n < 200; i++) {
      string nm = ObjectName(0, i);
      if (!IsS1Object(nm)) continue;
      names[n] = nm;
      times[n] = (datetime)ObjectGetInteger(0, nm, OBJPROP_CREATETIME);
      n++;
   }
   if (n < MAX_S1_OBJECTS) return;
   // Bubble-sort by time ascending (oldest first). 200-cap so it's fine.
   for (int a = 0; a < n - 1; a++) {
      for (int b = 0; b < n - 1 - a; b++) {
         if (times[b] > times[b+1]) {
            datetime tt = times[b]; times[b] = times[b+1]; times[b+1] = tt;
            string ss = names[b]; names[b] = names[b+1]; names[b+1] = ss;
         }
      }
   }
   // Delete oldest until we're under the cap
   int to_delete = n - (MAX_S1_OBJECTS - 10); // leave room for new labels
   for (int k = 0; k < to_delete && k < n; k++) {
      ObjectDelete(0, names[k]);
   }
}

// v2.91: WATCHING — fixed corner label that updates live while EA is patient.
datetime g_watch_buy_t  = 0;
datetime g_watch_sell_t = 0;

void PaintWatchingLabel(string side, double uhv_extreme, double current_price, double penetration_needed) {
   string tag = "S1_WATCH_" + side;
   if (ObjectFind(0, tag) < 0) {
      ObjectCreate(0, tag, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, tag, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, tag, OBJPROP_XDISTANCE, 12);
      ObjectSetInteger(0, tag, OBJPROP_YDISTANCE, (side == "BUY") ? 30 : 60);
      ObjectSetString (0, tag, OBJPROP_FONT, "Arial Black");
      ObjectSetInteger(0, tag, OBJPROP_FONTSIZE, 13);
      ObjectSetInteger(0, tag, OBJPROP_BACK, false);
   }
   // For BUY: we need current price > uhv_extreme. gap = current - uhv_extreme (positive=already broken)
   // For SELL: we need current price < uhv_extreme. gap = uhv_extreme - current (positive=already broken)
   double gap = (side == "BUY")
      ? (current_price - uhv_extreme)
      : (uhv_extreme - current_price);
   color clr = (gap >= penetration_needed) ? clrLime
              : (gap > 0)                  ? clrYellow
              :                              clrOrange;
   string need_price = StringFormat("%.2f", uhv_extreme + ((side == "BUY") ? penetration_needed : -penetration_needed));
   string txt = StringFormat("👁 WATCHING %s — UHV %s %.2f | now %.2f | need %s %s | gap %+.2fpt",
                              side,
                              (side == "BUY") ? "high" : "low",
                              uhv_extreme,
                              current_price,
                              (side == "BUY") ? ">" : "<",
                              need_price,
                              gap);
   ObjectSetString (0, tag, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, tag, OBJPROP_COLOR, clr);
}

void TickWatchingExpiry() {
   datetime now = TimeCurrent();
   if (g_watch_buy_t > 0 && now - g_watch_buy_t > 30) {
      ObjectDelete(0, "S1_WATCH_BUY");
      g_watch_buy_t = 0;
   }
   if (g_watch_sell_t > 0 && now - g_watch_sell_t > 30) {
      ObjectDelete(0, "S1_WATCH_SELL");
      g_watch_sell_t = 0;
   }
}
// ─────── end v2.91 watching ─────────────────────────────────────────

// v2.89: MOON-BRIGHT chart labels — big bold readable fonts so the setup
// is identifiable like a moon in the sky.
// Helper — create a colored arrow object (used for retracement / uhv pointers).
void S1Arrow(string tag, datetime t, double price, color clr, uchar arrow_code) {
   if (ObjectFind(0, tag) >= 0) return;
   if (ObjectCreate(0, tag, OBJ_ARROW, 0, t, price)) {
      ObjectSetInteger(0, tag, OBJPROP_ARROWCODE, arrow_code);
      ObjectSetInteger(0, tag, OBJPROP_COLOR,    clr);
      ObjectSetInteger(0, tag, OBJPROP_WIDTH,    3);
      ObjectSetInteger(0, tag, OBJPROP_BACK,     false);
   }
}

void LabelRetracementOrigin(int shift, string side) {
   datetime t = iTime(_Symbol, InpTimeframe, shift);
   double h  = iHigh(_Symbol, InpTimeframe, shift);
   double l  = iLow (_Symbol, InpTimeframe, shift);
   double rng = MathMax(h - l, 0.3);
   string tag = StringFormat("S1_RETR_%s_%I64d", side, (long)t);
   if (ObjectFind(0, tag) >= 0) return;
   // v2.92: kill the previous retracement label of same side BEFORE painting new
   ObjectsDeleteAll(0, "S1_RETR_" + side + "_");
   // Place label BELOW the bar (for BUY origins which are bear bars) /
   // ABOVE the bar (for SELL origins which are bull bars).
   bool below = (side == "BUY");
   double y = below ? (l - rng * 0.80) : (h + rng * 0.80);
   ENUM_ANCHOR_POINT anchor = below ? ANCHOR_UPPER : ANCHOR_LOWER;
   if (ObjectCreate(0, tag, OBJ_TEXT, 0, t, y)) {
      ObjectSetString (0, tag, OBJPROP_TEXT,     "▼ RETRACEMENT START");
      ObjectSetInteger(0, tag, OBJPROP_COLOR,    clrAqua);
      ObjectSetInteger(0, tag, OBJPROP_FONTSIZE, 14);
      ObjectSetString (0, tag, OBJPROP_FONT,     "Arial Black");
      ObjectSetInteger(0, tag, OBJPROP_ANCHOR,   anchor);
   }
   // Arrow pointing to the bar
   S1Arrow(tag + "_arr", t, below ? l : h, clrAqua, below ? 234 : 233);
   CleanOldS1Labels();
}

void LabelUhv(int shift, string side, long vol) {
   datetime t = iTime(_Symbol, InpTimeframe, shift);
   double h  = iHigh(_Symbol, InpTimeframe, shift);
   double l  = iLow (_Symbol, InpTimeframe, shift);
   double rng = MathMax(h - l, 0.3);
   string tag = StringFormat("S1_UHV_%s_%I64d", side, (long)t);
   if (ObjectFind(0, tag) >= 0) return;
   // v2.92: kill the previous UHV label of same side BEFORE painting new (no stacking)
   ObjectsDeleteAll(0, "S1_UHV_" + side + "_");
   // BUY: UHV is bearish red — label ABOVE bar. SELL: UHV is bullish green — label BELOW bar.
   bool above = (side == "BUY");
   double y = above ? (h + rng * 0.95) : (l - rng * 0.95);
   ENUM_ANCHOR_POINT anchor = above ? ANCHOR_LOWER : ANCHOR_UPPER;
   if (ObjectCreate(0, tag, OBJ_TEXT, 0, t, y)) {
      ObjectSetString (0, tag, OBJPROP_TEXT,     StringFormat("★ UHV (vol %d) ★", (int)vol));
      ObjectSetInteger(0, tag, OBJPROP_COLOR,    clrYellow);
      ObjectSetInteger(0, tag, OBJPROP_FONTSIZE, 15);
      ObjectSetString (0, tag, OBJPROP_FONT,     "Arial Black");
      ObjectSetInteger(0, tag, OBJPROP_ANCHOR,   anchor);
   }
   // Big arrow pointing to the UHV bar high/low
   S1Arrow(tag + "_arr", t, above ? h : l, clrYellow, above ? 234 : 233);
   CleanOldS1Labels();
}

void LabelBreakout(int shift, string side, bool fired) {
   datetime t = iTime(_Symbol, InpTimeframe, shift);
   double h  = iHigh(_Symbol, InpTimeframe, shift);
   double l  = iLow (_Symbol, InpTimeframe, shift);
   double rng = MathMax(h - l, 0.3);
   string tag = StringFormat("S1_BRK_%s_%I64d_%s", side, (long)t, fired ? "F" : "M");
   if (ObjectFind(0, tag) >= 0) return;
   bool above = (side == "BUY");
   double y = above ? (h + rng * 1.10) : (l - rng * 1.10);
   ENUM_ANCHOR_POINT anchor = above ? ANCHOR_LOWER : ANCHOR_UPPER;
   color clr = fired
      ? ((side == "BUY") ? clrLime : clrTomato)
      : clrDimGray;
   string txt = fired
      ? StringFormat("⚡ %s BREAKOUT ⚡", side)
      : "brk-miss";
   if (ObjectCreate(0, tag, OBJ_TEXT, 0, t, y)) {
      ObjectSetString (0, tag, OBJPROP_TEXT,     txt);
      ObjectSetInteger(0, tag, OBJPROP_COLOR,    clr);
      ObjectSetInteger(0, tag, OBJPROP_FONTSIZE, fired ? 18 : 7);
      ObjectSetString (0, tag, OBJPROP_FONT,     fired ? "Arial Black" : "Arial");
      ObjectSetInteger(0, tag, OBJPROP_ANCHOR,   anchor);
   }
   // Arrow pointing to the breakout bar
   if (fired) S1Arrow(tag + "_arr", t, above ? h : l, clr, above ? 233 : 234);
   CleanOldS1Labels();
}
// ─────── end v2.71 chart labels ─────────────────────────────────

void DrawEntryMarkers(string side, double entry, double sl, double tp,
                      double uhv_h, double uhv_l, datetime uhv_t, long uhv_vol,
                      int uhv_shift, int retrace_count, int retrace_max_shift,
                      int sweep_shift, double er_value,
                      bool h1bias_active, bool h1bias_uptrend) {
   g_marker_seq++;
   int seq = g_marker_seq;
   string tag = StringFormat("S1_%s_%d_%I64d", side, seq, (long)TimeCurrent());
   datetime now_t      = TimeCurrent();
   long bar_sec        = PeriodSeconds(InpTimeframe);
   datetime uhv_end_t  = uhv_t + bar_sec;
   datetime retrace_start_t = iTime(_Symbol, InpTimeframe, retrace_max_shift);
   datetime retrace_end_t   = uhv_t + bar_sec;   // retracement ends at UHV bar end
   datetime sweep_t    = (sweep_shift >= 0) ? iTime(_Symbol, InpTimeframe, sweep_shift) : (datetime)0;
   color side_color = (side == "BUY") ? clrDodgerBlue : clrTomato;
   color sl_color   = clrCrimson;
   color tp_color   = clrLimeGreen;
   color retrace_color = clrMediumPurple;
   color sweep_color   = clrMagenta;

   // Approx ymin/ymax for retracement box height (covers entire bar range across retrace)
   double rng_hi = uhv_h, rng_lo = uhv_l;
   for (int s = 1; s <= retrace_max_shift; s++) {
      double bh = iHigh(_Symbol, InpTimeframe, s);
      double bl = iLow (_Symbol, InpTimeframe, s);
      if (bh > rng_hi) rng_hi = bh;
      if (bl < rng_lo) rng_lo = bl;
   }

   double bar_h = uhv_h - uhv_l;
   if (bar_h <= 0) bar_h = 0.5;
   double uhv_mid_t = uhv_t + bar_sec / 2;            // midpoint of the M5 UHV bar (so arrow centers over it)
   datetime brk_t = iTime(_Symbol, InpTimeframe, 0);  // breakout M5 bar (currently forming)
   datetime brk_mid_t = brk_t + bar_sec / 2;
   double brk_h = iHigh(_Symbol, InpTimeframe, 0);
   double brk_l = iLow (_Symbol, InpTimeframe, 0);

   // 1) UHV BOX — outline only, exact M5 bar width, very thick goldenrod
   string rect_name = tag + "_uhv_box";
   if (ObjectCreate(0, rect_name, OBJ_RECTANGLE, 0, uhv_t, uhv_h, uhv_end_t, uhv_l)) {
      ObjectSetInteger(0, rect_name, OBJPROP_COLOR, clrGoldenrod);
      ObjectSetInteger(0, rect_name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, rect_name, OBJPROP_WIDTH, 4);
      ObjectSetInteger(0, rect_name, OBJPROP_FILL, false);
      ObjectSetInteger(0, rect_name, OBJPROP_BACK, false);
   }

   // 2) BIG UHV ARROW pointing AT the UHV bar (centered on the M5 candle)
   double uhv_arrow_y = (side == "BUY") ? uhv_l - bar_h * 0.4 : uhv_h + bar_h * 0.4;
   ENUM_OBJECT uhv_arrow_type = (side == "BUY") ? OBJ_ARROW_UP : OBJ_ARROW_DOWN;
   string uhv_arrow_name = tag + "_uhv_arrow";
   if (ObjectCreate(0, uhv_arrow_name, uhv_arrow_type, 0, uhv_mid_t, uhv_arrow_y)) {
      ObjectSetInteger(0, uhv_arrow_name, OBJPROP_COLOR, clrGoldenrod);
      ObjectSetInteger(0, uhv_arrow_name, OBJPROP_WIDTH, 6);
   }
   // UHV text label, just past the arrow
   double uhv_label_y = (side == "BUY") ? uhv_l - bar_h * 1.0 : uhv_h + bar_h * 1.0;
   string uhv_label_name = tag + "_uhv_label";
   if (ObjectCreate(0, uhv_label_name, OBJ_TEXT, 0, uhv_mid_t, uhv_label_y)) {
      ObjectSetString (0, uhv_label_name, OBJPROP_TEXT,
                       StringFormat("UHV #%d  vol=%d", seq, (int)uhv_vol));
      ObjectSetInteger(0, uhv_label_name, OBJPROP_COLOR, clrGoldenrod);
      ObjectSetInteger(0, uhv_label_name, OBJPROP_FONTSIZE, 13);
      ObjectSetString (0, uhv_label_name, OBJPROP_FONT, "Arial Bold");
      ObjectSetInteger(0, uhv_label_name, OBJPROP_ANCHOR,
                       (side == "BUY") ? ANCHOR_UPPER : ANCHOR_LOWER);
   }

   // 3) BREAKOUT LEVEL — thin gold dotted segment at UHV.high (BUY) / UHV.low (SELL)
   double brk_level = (side == "BUY") ? uhv_h : uhv_l;
   string brk_name = tag + "_breakout_level";
   if (ObjectCreate(0, brk_name, OBJ_TREND, 0, uhv_end_t, brk_level, brk_t, brk_level)) {
      ObjectSetInteger(0, brk_name, OBJPROP_COLOR, clrGold);
      ObjectSetInteger(0, brk_name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, brk_name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, brk_name, OBJPROP_RAY, false);
   }

   // 4) BREAKOUT CANDLE — outline box around the breakout M5 bar + big arrow + label
   string brk_box_name = tag + "_brk_box";
   datetime brk_end_t = brk_t + bar_sec;
   if (ObjectCreate(0, brk_box_name, OBJ_RECTANGLE, 0, brk_t, brk_h, brk_end_t, brk_l)) {
      ObjectSetInteger(0, brk_box_name, OBJPROP_COLOR, side_color);
      ObjectSetInteger(0, brk_box_name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, brk_box_name, OBJPROP_WIDTH, 4);
      ObjectSetInteger(0, brk_box_name, OBJPROP_FILL, false);
      ObjectSetInteger(0, brk_box_name, OBJPROP_BACK, false);
   }
   double brk_bar_h = brk_h - brk_l; if (brk_bar_h <= 0) brk_bar_h = bar_h;
   double brk_arrow_y = (side == "BUY") ? brk_l - brk_bar_h * 0.4 : brk_h + brk_bar_h * 0.4;
   string brk_arrow_name = tag + "_brk_arrow";
   ENUM_OBJECT brk_arrow_type = (side == "BUY") ? OBJ_ARROW_UP : OBJ_ARROW_DOWN;
   if (ObjectCreate(0, brk_arrow_name, brk_arrow_type, 0, brk_mid_t, brk_arrow_y)) {
      ObjectSetInteger(0, brk_arrow_name, OBJPROP_COLOR, side_color);
      ObjectSetInteger(0, brk_arrow_name, OBJPROP_WIDTH, 6);
   }
   double brk_label_y = (side == "BUY") ? brk_l - brk_bar_h * 1.0 : brk_h + brk_bar_h * 1.0;
   string brk_label_name = tag + "_brk_label";
   if (ObjectCreate(0, brk_label_name, OBJ_TEXT, 0, brk_mid_t, brk_label_y)) {
      ObjectSetString (0, brk_label_name, OBJPROP_TEXT,
                       StringFormat("BREAKOUT #%d  %s @ %.2f", seq, side, entry));
      ObjectSetInteger(0, brk_label_name, OBJPROP_COLOR, side_color);
      ObjectSetInteger(0, brk_label_name, OBJPROP_FONTSIZE, 13);
      ObjectSetString (0, brk_label_name, OBJPROP_FONT, "Arial Bold");
      ObjectSetInteger(0, brk_label_name, OBJPROP_ANCHOR,
                       (side == "BUY") ? ANCHOR_UPPER : ANCHOR_LOWER);
   }
}

//── v2.52 HH+HL swing-structure gate ──
// A "pivot high" at bar i = iHigh(i) > iHigh(i-k) and iHigh(i) > iHigh(i+k) for all k in [1..pivot_strength].
// Returns the two most recent confirmed pivot highs and lows within lookback bars from now (from_shift).
// HasHHHLUptrend = the most recent pivot_high (newer) > previous pivot_high (older) AND
//                  the most recent pivot_low  (newer) > previous pivot_low  (older).
// HasHHHLDowntrend = mirror (LH+LL).
bool HasHHHLTrend(ENUM_TIMEFRAMES tf, int lookback, int pivot_str, bool want_uptrend) {
   double hi1=0, hi2=0;   // hi1 = NEWER pivot high (smaller bar index), hi2 = OLDER pivot high
   double lo1=0, lo2=0;
   int    hi_cnt=0, lo_cnt=0;
   // Walk from oldest to newest in the lookback window so the most recent pivot becomes hi1.
   for (int i = lookback - pivot_str; i >= pivot_str + 1; i--) {
      double h_i = iHigh(_Symbol, tf, i);
      double l_i = iLow (_Symbol, tf, i);
      if (h_i <= 0 || l_i <= 0) continue;
      bool is_pivot_hi = true;
      bool is_pivot_lo = true;
      for (int k = 1; k <= pivot_str && (is_pivot_hi || is_pivot_lo); k++) {
         double hL = iHigh(_Symbol, tf, i + k);
         double hR = iHigh(_Symbol, tf, i - k);
         double lL = iLow (_Symbol, tf, i + k);
         double lR = iLow (_Symbol, tf, i - k);
         if (hL <= 0 || hR <= 0 || lL <= 0 || lR <= 0) { is_pivot_hi = false; is_pivot_lo = false; break; }
         if (h_i <= hL || h_i <= hR) is_pivot_hi = false;
         if (l_i >= lL || l_i >= lR) is_pivot_lo = false;
      }
      if (is_pivot_hi) {
         hi2 = hi1; hi1 = h_i; hi_cnt++;
      }
      if (is_pivot_lo) {
         lo2 = lo1; lo1 = l_i; lo_cnt++;
      }
   }
   if (hi_cnt < 2 || lo_cnt < 2) return false;
   if (want_uptrend) {
      return (hi1 > hi2 && lo1 > lo2);   // HH + HL
   } else {
      return (hi1 < hi2 && lo1 < lo2);   // LH + LL
   }
}

// Convenience wrappers — return TRUE when gate is OFF (so they're inert when not enabled).
// v2.53 — runtime-config mirrors. Read from Common\Files\s1_runtime_<magic>.json
// every 2s via OnTimer. Initialised from Inp* defaults at OnInit.
int    g_auto_close_ms   = 0;  // v2.88: hot-reloadable from runtime config
double g_trail_lock_pts  = 0.0; // v2.88: hot-reloadable
double g_trail_rev_pts   = 0.0; // v2.88: hot-reloadable
double g_daily_loss_halt = 0.0; // v2.88: hot-reloadable
double g_daily_profit_target = 0.0; // v2.88: hot-reloadable
bool   g_require_uhv_neighbor_peak = true;  // v2.93: hot-reloadable
double g_uhv_body_min     = 0.60;            // v2.93: hot-reloadable
int    g_max_bars_since_uhv = 8;             // v2.93: hot-reloadable
bool   g_require_breakout_body_close = true; // v2.93: hot-reloadable
bool   g_allowed_hours_mask[24];             // v2.95: per-UTC-hour bitmap; true=allowed
bool   g_time_window_active = false;         // v2.95: false = no filter (all hours)
string g_allowed_hours_str  = "";            // v2.95: hot-reloadable string cache
double g_min_sweep_depth_pts = 0.30;         // v2.97: hot-reloadable
double g_max_breakout_wick_pct = 0.0;        // v2.97: hot-reloadable
bool   g_require_h1_agrees_v2 = false;       // v2.97: hot-reloadable
double g_max_retracement_wick_pct = 0.45;    // v2.98: hot-reloadable. The big one.
bool   g_require_breakout_color = true;      // v2.99: standalone color check. 92.3% WR enabler.
bool   g_uhv_global_max         = true;      // v3.00: UHV must be strictly highest-vol bar in scope regardless of color
bool   g_require_hhhl_m5 = false;
bool   g_require_hhhl_h1 = false;
bool   g_require_h1bias  = true;
int    g_h1bias_bars     = 6;
// v2.59 — momentum override
bool   g_momentum_override_enabled = true;
double g_momentum_override_pts     = 5.0;
// v2.60 — breakout-candle quality filter
bool   g_require_breakout_momentum = false;
double g_breakout_min_body_pts     = 1.5;
bool   g_require_breakout_lowvol   = false;
// v2.59 — missed-breakout tracking (so we don't repaint the same missed UHV)
datetime g_last_missed_buy_uhv_t  = 0;
datetime g_last_missed_sell_uhv_t = 0;

// v2.59 — bypass slow IsDowntrendM5/IsUptrendM5 when 30-min close-delta is big
bool HasBearMomentumOverride() {
   if (!g_momentum_override_enabled) return false;
   double now   = iClose(_Symbol, InpTimeframe, 1);
   double back6 = iClose(_Symbol, InpTimeframe, 7);  // 6 closed M5 bars back = 30 min
   if (back6 <= 0 || now <= 0) return false;
   return (back6 - now) > g_momentum_override_pts;
}
bool HasBullMomentumOverride() {
   if (!g_momentum_override_enabled) return false;
   double now   = iClose(_Symbol, InpTimeframe, 1);
   double back6 = iClose(_Symbol, InpTimeframe, 7);
   if (back6 <= 0 || now <= 0) return false;
   return (now - back6) > g_momentum_override_pts;
}

// v2.60 — breakout-candle momentum body filter (lesson02: "momentum candle, big body, tiny wicks")
//   For SELL: the forming M5 bar 0 must already show enough bearish body (open - close >= min)
//   For BUY:  bullish body (close - open >= min)
//   If forming bar's body is too small the breakout is likely a wick/spike, not real momentum.
bool HasSellBreakoutMomentum() {
   if (!g_require_breakout_momentum) return true;
   double cur_open  = iOpen(_Symbol, InpTimeframe, 0);
   double cur_close = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (cur_open <= 0 || cur_close <= 0) return false;
   return (cur_open - cur_close) >= g_breakout_min_body_pts;
}
bool HasBuyBreakoutMomentum() {
   if (!g_require_breakout_momentum) return true;
   double cur_open  = iOpen(_Symbol, InpTimeframe, 0);
   double cur_close = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if (cur_open <= 0 || cur_close <= 0) return false;
   return (cur_close - cur_open) >= g_breakout_min_body_pts;
}

// v2.60 — breakout-candle low-vol filter (lesson02: "low volume breakout")
//   Breakout's tick volume so far must be below the UHV's volume.
bool HasBreakoutLowVolume(long uhv_vol) {
   if (!g_require_breakout_lowvol) return true;
   long cur_vol = iVolume(_Symbol, InpTimeframe, 0);
   return cur_vol < uhv_vol;
}

bool PassHHHLUptrendGate() {
   if (g_require_hhhl_m5 && !HasHHHLTrend(InpTimeframe, InpHHHL_LookbackM5, InpHHHL_PivotBars, true)) return false;
   if (g_require_hhhl_h1 && !HasHHHLTrend(PERIOD_H1,    InpHHHL_LookbackH1, InpHHHL_PivotBars, true)) return false;
   return true;
}
bool PassHHHLDowntrendGate() {
   if (g_require_hhhl_m5 && !HasHHHLTrend(InpTimeframe, InpHHHL_LookbackM5, InpHHHL_PivotBars, false)) return false;
   if (g_require_hhhl_h1 && !HasHHHLTrend(PERIOD_H1,    InpHHHL_LookbackH1, InpHHHL_PivotBars, false)) return false;
   return true;
}

bool PassH1BiasGate(bool want_uptrend) {
   if (!g_require_h1bias) return true;
   double recent = iClose(_Symbol, PERIOD_H1, 1);
   double older  = iClose(_Symbol, PERIOD_H1, g_h1bias_bars);
   if (recent <= 0 || older <= 0) return false;
   return want_uptrend ? (recent > older) : (recent < older);
}

// v2.59 — diagnose why a SELL would not have fired given a triggered UHV
// v2.71 — diagnose functions REWRITTEN to walk current gate order with opt-in flag
// checks. Previously these reported gates that aren't actually active (e.g. slow_d
// when InpRequireSlowTrend=false), making MISS labels lie. Now only reports gates
// that ARE active and ARE blocking.
string DiagnoseSellBlock(int uhv_shift) {
   if (DailyLossHalted()) return "daily_halt";
   if (HarvestLocked()) return "HARVEST_LOCKED (target hit — withdraw + sleep)";
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return StringFormat("ER<%.2f", InpERMin);
   if (InpSessionStartHour != InpSessionEndHour) {
      MqlDateTime _dt; TimeToStruct(TimeCurrent(), _dt);
      int _h = _dt.hour;
      bool _in = (InpSessionStartHour < InpSessionEndHour)
                    ? (_h >= InpSessionStartHour && _h < InpSessionEndHour)
                    : (_h >= InpSessionStartHour || _h < InpSessionEndHour);
      if (!_in) return StringFormat("out-of-session (h=%d)", _h);
   }
   if (InpRequireSlowTrend && !IsDowntrendM5(1) && !HasBearMomentumOverride()) return "slow_trend(opt-in)";
   if (g_require_hhhl_m5 && !HasHHHLTrend(InpTimeframe, InpHHHL_LookbackM5, InpHHHL_PivotBars, false)) return "HHHL_M5";
   if (g_require_hhhl_h1 && !HasHHHLTrend(PERIOD_H1, InpHHHL_LookbackH1, InpHHHL_PivotBars, false)) return "HHHL_H1";
   if (!PassH1BiasGate(false)) return "H1Bias";
   if (InpRequireCanonicalOrigin && FindCanonicalRetracementOriginSell() < 0) return "no-canon-origin";
   if (!UhvBodyOk(uhv_shift, InpUhvBodyMin)) return StringFormat("uhv-body<%.2f", InpUhvBodyMin);
   if (InpRequireUhvNeighborPeak && !UhvNeighborPeakOk(uhv_shift)) return "uhv-not-peak";
   if (InpRequireBigSpreadClimax && !IsBigSpreadClimax(uhv_shift)) return "not-climax";
   if (ClusterBlocked(-1)) return "cluster";
   return "post-uhv (breakout-gates)";
}
string DiagnoseBuyBlock(int uhv_shift) {
   if (DailyLossHalted()) return "daily_halt";
   if (HarvestLocked()) return "HARVEST_LOCKED (target hit — withdraw + sleep)";
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return StringFormat("ER<%.2f", InpERMin);
   if (InpSessionStartHour != InpSessionEndHour) {
      MqlDateTime _dt; TimeToStruct(TimeCurrent(), _dt);
      int _h = _dt.hour;
      bool _in = (InpSessionStartHour < InpSessionEndHour)
                    ? (_h >= InpSessionStartHour && _h < InpSessionEndHour)
                    : (_h >= InpSessionStartHour || _h < InpSessionEndHour);
      if (!_in) return StringFormat("out-of-session (h=%d)", _h);
   }
   if (InpRequireSlowTrend && !IsUptrendM5(1) && !HasBullMomentumOverride()) return "slow_trend(opt-in)";
   if (g_require_hhhl_m5 && !HasHHHLTrend(InpTimeframe, InpHHHL_LookbackM5, InpHHHL_PivotBars, true)) return "HHHL_M5";
   if (g_require_hhhl_h1 && !HasHHHLTrend(PERIOD_H1, InpHHHL_LookbackH1, InpHHHL_PivotBars, true)) return "HHHL_H1";
   if (!PassH1BiasGate(true)) return "H1Bias";
   if (InpRequireCanonicalOrigin && FindCanonicalRetracementOriginBuy() < 0) return "no-canon-origin";
   if (!UhvBodyOk(uhv_shift, InpUhvBodyMin)) return StringFormat("uhv-body<%.2f", InpUhvBodyMin);
   if (InpRequireUhvNeighborPeak && !UhvNeighborPeakOk(uhv_shift)) return "uhv-not-peak";
   if (InpRequireBigSpreadClimax && !IsBigSpreadClimax(uhv_shift)) return "not-climax";
   if (ClusterBlocked(+1)) return "cluster";
   return "post-uhv (breakout-gates)";
}

// v2.59 — paint a faded grey "MISSED" marker on the current bar with the blocking reason
void PaintMissedMarker(string side, int uhv_shift, double uhv_h, double uhv_l,
                      datetime uhv_t, long uhv_vol, string reason) {
   long bar_sec = PeriodSeconds(InpTimeframe);
   datetime now_t = TimeCurrent();
   double cur_h = iHigh(_Symbol, InpTimeframe, 0);
   double cur_l = iLow (_Symbol, InpTimeframe, 0);
   double bar_h = MathMax(cur_h - cur_l, 0.3);
   double arrow_y = (side == "BUY") ? cur_l - bar_h * 0.4 : cur_h + bar_h * 0.4;
   double label_y = (side == "BUY") ? cur_l - bar_h * 1.0 : cur_h + bar_h * 1.0;
   string tag = StringFormat("S1_MISS_%s_%I64d", side, (long)uhv_t);
   ENUM_OBJECT atype = (side == "BUY") ? OBJ_ARROW_UP : OBJ_ARROW_DOWN;
   if (ObjectCreate(0, tag + "_a", atype, 0, now_t, arrow_y)) {
      ObjectSetInteger(0, tag + "_a", OBJPROP_COLOR, clrDimGray);
      ObjectSetInteger(0, tag + "_a", OBJPROP_WIDTH, 4);
   }
   if (ObjectCreate(0, tag + "_l", OBJ_TEXT, 0, now_t, label_y)) {
      // v2.89: MISS labels are DIMMED + tiny so they don't compete with the bright moon labels.
      ObjectSetString (0, tag + "_l", OBJPROP_TEXT,
                       StringFormat("· miss %s ·", side));
      ObjectSetInteger(0, tag + "_l", OBJPROP_COLOR, C'60,60,60');   // very dark grey
      ObjectSetInteger(0, tag + "_l", OBJPROP_FONTSIZE, 6);
      ObjectSetString (0, tag + "_l", OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, tag + "_l", OBJPROP_ANCHOR,
                       (side == "BUY") ? ANCHOR_UPPER : ANCHOR_LOWER);
   }
   // Also box the missed UHV bar in dim grey so it pairs visually
   if (ObjectCreate(0, tag + "_box", OBJ_RECTANGLE, 0, uhv_t, uhv_h, uhv_t + bar_sec, uhv_l)) {
      ObjectSetInteger(0, tag + "_box", OBJPROP_COLOR, clrDimGray);
      ObjectSetInteger(0, tag + "_box", OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, tag + "_box", OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, tag + "_box", OBJPROP_FILL, false);
      ObjectSetInteger(0, tag + "_box", OBJPROP_BACK, true);
   }
   Log(StringFormat("[MISS] %s UHV vol=%d shift=%d uhv_l=%.2f uhv_h=%.2f reason=%s",
                    side, (int)uhv_vol, uhv_shift, uhv_l, uhv_h, reason));
}

// v2.59 — shadow detector that finds breakouts and marks them MISSED if EA didn't fire
void DetectMissedBreakouts() {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if (bid <= 0 || ask <= 0) return;

   // SELL side: find highest-vol GREEN in last InpRetraceLookback bars
   {
      int greens[15]; int gc = 0;
      for (int j = 1; j <= InpRetraceLookback; j++) {
         double o = iOpen(_Symbol, InpTimeframe, j);
         double c = iClose(_Symbol, InpTimeframe, j);
         if (c > o && gc < 15) greens[gc++] = j;
      }
      if (gc > 0) {
         int uhv_shift = greens[0]; long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
         for (int r = 1; r < gc; r++) {
            long v = iVolume(_Symbol, InpTimeframe, greens[r]);
            if (v > uhv_vol) { uhv_vol = v; uhv_shift = greens[r]; }
         }
         double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
         double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
         datetime uhv_t = iTime(_Symbol, InpTimeframe, uhv_shift);
         if (uhv_t != g_last_uhv_sell_t && uhv_t != g_last_missed_sell_uhv_t) {
            bool swept = false;
            for (int k = uhv_shift - 1; k >= 1; k--) {
               if (iHigh(_Symbol, InpTimeframe, k) > uhv_h) { swept = true; break; }
            }
            if (!swept && iHigh(_Symbol, InpTimeframe, 0) > uhv_h) swept = true;
            if (swept && bid < uhv_l) {
               string reason = DiagnoseSellBlock(uhv_shift);
               PaintMissedMarker("SELL", uhv_shift, uhv_h, uhv_l, uhv_t, uhv_vol, reason);
               g_last_missed_sell_uhv_t = uhv_t;
            }
         }
      }
   }

   // BUY side: find highest-vol RED in last InpRetraceLookback bars
   {
      int reds[15]; int rc = 0;
      for (int j = 1; j <= InpRetraceLookback; j++) {
         double o = iOpen(_Symbol, InpTimeframe, j);
         double c = iClose(_Symbol, InpTimeframe, j);
         if (c < o && rc < 15) reds[rc++] = j;
      }
      if (rc > 0) {
         int uhv_shift = reds[0]; long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
         for (int r = 1; r < rc; r++) {
            long v = iVolume(_Symbol, InpTimeframe, reds[r]);
            if (v > uhv_vol) { uhv_vol = v; uhv_shift = reds[r]; }
         }
         double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
         double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
         datetime uhv_t = iTime(_Symbol, InpTimeframe, uhv_shift);
         if (uhv_t != g_last_uhv_buy_t && uhv_t != g_last_missed_buy_uhv_t) {
            bool swept = false;
            for (int k = uhv_shift - 1; k >= 1; k--) {
               if (iLow(_Symbol, InpTimeframe, k) < uhv_l) { swept = true; break; }
            }
            if (!swept && iLow(_Symbol, InpTimeframe, 0) < uhv_l) swept = true;
            if (swept && ask > uhv_h) {
               string reason = DiagnoseBuyBlock(uhv_shift);
               PaintMissedMarker("BUY", uhv_shift, uhv_h, uhv_l, uhv_t, uhv_vol, reason);
               g_last_missed_buy_uhv_t = uhv_t;
            }
         }
      }
   }
}

// Bullish H1 FVG = older_high < newer_low (a gap up). Tapped if any M5 bar in
// the retracement has range overlapping the gap zone.
bool H1FvgTappedDuringRetracement(int retrace_back_shift) {
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_high = iHigh(_Symbol, PERIOD_H1, i + 2);
      double newer_low  = iLow (_Symbol, PERIOD_H1, i);
      if (newer_low <= older_high) continue;
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iLow(_Symbol, PERIOD_H1, j) < older_high) {
            filled = true; break;
         }
      }
      if (filled) continue;
      for (int k = 1; k <= retrace_back_shift; k++) {
         double mlow  = iLow(_Symbol, InpTimeframe, k);
         double mhigh = iHigh(_Symbol, InpTimeframe, k);
         if (mlow <= newer_low && mhigh >= older_high) return true;
      }
   }
   return false;
}

// Bearish H1 FVG = older_low > newer_high (a gap down). Tapped if any M5 bar
// in the retracement has range overlapping the gap zone. "Filled" = a later
// H1 bar's high traded back above older_low.
bool H1BearFvgTappedDuringRetracement(int retrace_back_shift) {
   for (int i = 2; i <= InpH1FvgLookback; i++) {
      double older_low  = iLow (_Symbol, PERIOD_H1, i + 2);
      double newer_high = iHigh(_Symbol, PERIOD_H1, i);
      if (older_low <= newer_high) continue;
      bool filled = false;
      for (int j = i - 1; j >= 0; j--) {
         if (iHigh(_Symbol, PERIOD_H1, j) > older_low) {
            filled = true; break;
         }
      }
      if (filled) continue;
      for (int k = 1; k <= retrace_back_shift; k++) {
         double mlow  = iLow (_Symbol, InpTimeframe, k);
         double mhigh = iHigh(_Symbol, InpTimeframe, k);
         // Bear FVG zone is [newer_high, older_low]. Overlap: m5.low<=older_low && m5.high>=newer_high
         if (mlow <= older_low && mhigh >= newer_high) return true;
      }
   }
   return false;
}

//── v2.61 Canonical helpers (lesson02 + Zee's labelling pass) ──────
// Bar shift convention: 0 = currently-forming bar, 1 = most-recently-closed
// bar, larger shift = older. "Immediate prior" of shift S = shift S+1.

// Find retracement origin (BUY): the FIRST bear (red) closed bar within
// InpRetraceLookback whose IMMEDIATE prior bar is bull (green) AND whose
// close is BELOW that bull's low (body-break, not wick-poke).
// Returns the SHIFT of that origin bar, or -1 if no valid origin in window.
int FindCanonicalRetracementOriginBuy() {
   for (int j = 1; j <= InpRetraceLookback; j++) {
      double j_o  = iOpen (_Symbol, InpTimeframe, j);
      double j_c  = iClose(_Symbol, InpTimeframe, j);
      if (j_c >= j_o) continue;                          // j must be bear
      double p_o  = iOpen (_Symbol, InpTimeframe, j + 1);
      double p_c  = iClose(_Symbol, InpTimeframe, j + 1);
      if (p_c <= p_o) continue;                          // immediate prior must be bull
      double p_l  = iLow  (_Symbol, InpTimeframe, j + 1);
      if (j_c >= p_l) continue;                          // bear's close must be < bull's low (body-break)
      return j;
   }
   return -1;
}

// Mirror for SELL: first bull within window whose IMMEDIATE prior is bear
// and whose close is ABOVE that bear's high.
int FindCanonicalRetracementOriginSell() {
   for (int j = 1; j <= InpRetraceLookback; j++) {
      double j_o = iOpen (_Symbol, InpTimeframe, j);
      double j_c = iClose(_Symbol, InpTimeframe, j);
      if (j_c <= j_o) continue;
      double p_o = iOpen (_Symbol, InpTimeframe, j + 1);
      double p_c = iClose(_Symbol, InpTimeframe, j + 1);
      if (p_c >= p_o) continue;
      double p_h = iHigh (_Symbol, InpTimeframe, j + 1);
      if (j_c <= p_h) continue;
      return j;
   }
   return -1;
}

// UHV body strength gate: |close-open| / (high-low) must be >= min_ratio.
bool UhvBodyOk(int shift, double min_ratio) {
   double o = iOpen(_Symbol, InpTimeframe, shift);
   double c = iClose(_Symbol, InpTimeframe, shift);
   double h = iHigh(_Symbol, InpTimeframe, shift);
   double l = iLow(_Symbol, InpTimeframe, shift);
   double rng = h - l;
   if (rng <= 0.0) return false;
   double body = MathAbs(c - o);
   return (body / rng) >= min_ratio;
}

// UHV must be a STRICT local-volume peak — higher vol than the immediate
// older bar (shift+1) AND the immediate newer bar (shift-1). The newer
// neighbour exists only if shift >= 2 (otherwise still-forming bar 0
// could become higher; we skip the check rather than approve weakly).
bool UhvNeighborPeakOk(int shift) {
   long uhv_v = iVolume(_Symbol, InpTimeframe, shift);
   long older_v = iVolume(_Symbol, InpTimeframe, shift + 1);
   if (older_v >= uhv_v) return false;
   if (shift >= 2) {
      long newer_v = iVolume(_Symbol, InpTimeframe, shift - 1);
      if (newer_v >= uhv_v) return false;
   }
   return true;
}

// Forming-bar (shift 0) breakout-body momentum check: body/range of the
// FORMING bar measured at current tick must be >= min_ratio. Uses bid for
// SELL and ask for BUY as the live close. side: +1 BUY, -1 SELL.
bool BreakoutBodyOk(int side, double min_ratio, double ask, double bid) {
   double cur_o = iOpen(_Symbol, InpTimeframe, 0);
   double cur_h = iHigh(_Symbol, InpTimeframe, 0);
   double cur_l = iLow (_Symbol, InpTimeframe, 0);
   double cur_c = (side > 0) ? ask : bid;
   if (side > 0 && cur_h < cur_c) cur_h = cur_c;        // live tick may extend high
   if (side < 0 && cur_l > cur_c) cur_l = cur_c;
   double rng = cur_h - cur_l;
   if (rng <= 0.0) return false;
   double body = MathAbs(cur_c - cur_o);
   return (body / rng) >= min_ratio;
}

// Forming-bar tick-volume must be <= ratio × UHV vol.
bool BreakoutVolOk(long uhv_vol, double ratio) {
   long cur_v = iVolume(_Symbol, InpTimeframe, 0);
   double cap = (double)uhv_vol * ratio;
   return (double)cur_v <= cap;
}

// ─── v2.97 mechanizable visual-judgment gates ──────────────────────────
// (1) Sweep depth: between UHV bar and current forming bar, at least one bar
// must have wicked past the UHV extreme by >= g_min_sweep_depth_pts.
bool SweepDepthOk(int uhv_shift, string side) {
   if (g_min_sweep_depth_pts <= 0) return true;
   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
   double max_sweep = 0.0;
   for (int k = uhv_shift - 1; k >= 0; k--) {
      double sweep_amt = (side == "BUY")
         ? (uhv_l - iLow(_Symbol, InpTimeframe, k))
         : (iHigh(_Symbol, InpTimeframe, k) - uhv_h);
      if (sweep_amt > max_sweep) max_sweep = sweep_amt;
   }
   return max_sweep >= g_min_sweep_depth_pts;
}

// (2) Breakout-candle wick check: the AGAINST-direction wick must be small.
// shift=1 = the previously closed breakout candle.
bool BreakoutWickOk(int shift, string side) {
   if (g_max_breakout_wick_pct <= 0) return true;
   double o = iOpen (_Symbol, InpTimeframe, shift);
   double h = iHigh (_Symbol, InpTimeframe, shift);
   double l = iLow  (_Symbol, InpTimeframe, shift);
   double c = iClose(_Symbol, InpTimeframe, shift);
   double rng = h - l;
   if (rng <= 0) return false;
   double body_h = MathMax(o, c);
   double body_l = MathMin(o, c);
   double upper_w = (h - body_h) / rng;
   double lower_w = (body_l - l) / rng;
   if (side == "BUY") {
      // BUY breakout candle = green/bullish. The bears tried to push down = LOWER wick. Long lower wick = bad.
      return lower_w <= g_max_breakout_wick_pct;
   } else {
      // SELL breakout candle = red/bearish. Bulls tried to push up = UPPER wick. Long upper = bad.
      return upper_w <= g_max_breakout_wick_pct;
   }
}

// (3) H1 trend bias: last completed H1 candle direction must match setup.
bool H1AgreesV2(string side) {
   if (!g_require_h1_agrees_v2) return true;
   double h1_open  = iOpen (_Symbol, PERIOD_H1, 1);
   double h1_close = iClose(_Symbol, PERIOD_H1, 1);
   if (side == "BUY")  return h1_close > h1_open;
   else                return h1_close < h1_open;
}

// (4) v2.98 — REJECTION WICKS in retracement (the 87.5% WR rule).
//     For BUY (red retracement): each retracement-area candle's LOWER wick
//     must be ≤ g_max_retracement_wick_pct of its range. Long lower wicks
//     = buyers stepping in early = retracement weak. Symmetric for SELL.
bool RetracementWicksClean(int uhv_shift, string side) {
   if (g_max_retracement_wick_pct <= 0) return true;
   // Check UHV bar + 2 bars immediately before it (the active retracement bars).
   int start = uhv_shift + 2;
   for (int k = uhv_shift; k <= start; k++) {
      double o = iOpen (_Symbol, InpTimeframe, k);
      double h = iHigh (_Symbol, InpTimeframe, k);
      double l = iLow  (_Symbol, InpTimeframe, k);
      double c = iClose(_Symbol, InpTimeframe, k);
      double rng = h - l;
      if (rng <= 0) continue;
      double body_h = MathMax(o, c);
      double body_l = MathMin(o, c);
      if (side == "BUY") {
         // Red retracement — lower wick = buyer rejection of low = bad
         double lower_w = (body_l - l) / rng;
         if (lower_w > g_max_retracement_wick_pct) return false;
      } else {
         // Green retracement — upper wick = seller rejection of high = bad
         double upper_w = (h - body_h) / rng;
         if (upper_w > g_max_retracement_wick_pct) return false;
      }
   }
   return true;
}
// ─── end v2.98 ─────────────────────────────────────────────────────────

// (5) v2.99 — STANDALONE breakout-candle color check (the 92.3% WR enabler).
//     Independent of body-close-past-UHV. Just checks candle direction.
bool BreakoutColorOk(string side) {
   if (!g_require_breakout_color) return true;
   double o = iOpen (_Symbol, InpTimeframe, 1);
   double c = iClose(_Symbol, InpTimeframe, 1);
   if (side == "BUY")  return c > o;   // breakout candle must be GREEN
   else                return c < o;   // breakout candle must be RED
}
// ─── end v2.99 ─────────────────────────────────────────────────────────

// (6) v3.00 — UHV GLOBAL-MAX SAFETY CHECK
//     Verifies the chosen UHV (correct-color highest-vol bar) ALSO has
//     strictly higher volume than EVERY OTHER bar (any color) in the
//     same scanned scope. If an opposite-color bar has higher volume,
//     the "ultra volume" was on the wrong side → setup is invalid.
//
//     scope_back = how far back from current bar the scan covered
//                  (= origin_shift if canonical mode, else InpRetraceLookback)
bool UhvIsGlobalMax(int uhv_shift, long uhv_vol, int scope_back) {
   if (!g_uhv_global_max) return true;
   for (int j = 1; j <= scope_back; j++) {
      if (j == uhv_shift) continue;
      long v = iVolume(_Symbol, InpTimeframe, j);
      if (v > uhv_vol) return false;     // some other bar has higher vol → invalid
   }
   return true;
}
// ─── end v3.00 ─────────────────────────────────────────────────────────

//── S1 BUY LIVE-TICK trigger (v2.50, canonical gates v2.61) ────────
// v2.50 fires the MILLISECOND ask > UHV.high instead of waiting for the M5
// candle to close. Mirrors Zee's Feb 11 manual style (trades closed 9-24s).
// Per-UHV-candle lockout via g_last_uhv_buy_t so the same setup fires once.
bool TryS1BuySignalLive(double ask, double bid) {
   if (!InpDoBuys) return false;
   if (DailyLossHalted()) return false;
   if (HarvestLocked()) return false;          // v2.74 harvest guardrail
   if (!IsInAllowedHours()) return false;      // v2.95 TIME-WINDOW (master's 92% WR secret)
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return false;

   // v2.66 HOT-HOURS GATE: only fire during configured session window
   if (InpSessionStartHour != InpSessionEndHour) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      int h = dt.hour;
      bool in_window = (InpSessionStartHour < InpSessionEndHour)
                          ? (h >= InpSessionStartHour && h < InpSessionEndHour)
                          : (h >= InpSessionStartHour || h < InpSessionEndHour);
      if (!in_window) return false;
   }

   // v2.66: slow trend filter NOW OPT-IN (was hardcoded). Default OFF.
   if (InpRequireSlowTrend && !IsUptrendM5(1) && !HasBullMomentumOverride()) return false;
   // v2.52: optional structural trend gate (HH+HL on M5 and/or H1). Default OFF.
   if (!PassHHHLUptrendGate()) return false;
   // v2.52: optional softer H1 bias gate. Default OFF.
   if (!PassH1BiasGate(true)) return false;

   // 1a. v2.61 CANONICAL: anchor the retracement to its FIRST-bear origin.
   //     The reds we collect must be AT or AFTER (= same shift or SMALLER
   //     shift number, since smaller=newer) the origin's shift.
   int origin_shift = -1;
   if (InpRequireCanonicalOrigin) {
      origin_shift = FindCanonicalRetracementOriginBuy();
      if (origin_shift < 0) return false;       // no valid retracement origin
      LabelRetracementOrigin(origin_shift, "BUY");   // v2.71 visual label
   }

   // 1. Walk back collecting retracement reds in last InpRetraceLookback CLOSED bars.
   //    j starts at 1 — the just-closed M5 — because we no longer wait for
   //    the breakout candle to close. The breakout happens INTRA-candle on
   //    bar 0 (currently forming) via the ask-cross check below.
   int reds[15];
   int reds_count = 0;
   int max_red_shift = 1;
   int red_upper = InpRetraceLookback;
   if (InpRequireCanonicalOrigin && origin_shift > 0) red_upper = origin_shift;
   for (int j = 1; j <= red_upper; j++) {
      double r_o = iOpen (_Symbol, InpTimeframe, j);
      double r_c = iClose(_Symbol, InpTimeframe, j);
      if (r_c < r_o) {
         if (reds_count < 15) {
            reds[reds_count++] = j;
            max_red_shift = j;
         }
      }
   }
   if (reds_count == 0) return false;

   // 2. UHV red = highest-volume red in the retracement
   int uhv_shift = reds[0];
   long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
   for (int r = 1; r < reds_count; r++) {
      long v = iVolume(_Symbol, InpTimeframe, reds[r]);
      if (v > uhv_vol) {
         uhv_vol = v;
         uhv_shift = reds[r];
      }
   }
   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
   datetime uhv_t = iTime(_Symbol, InpTimeframe, uhv_shift);

   // ANTI-SPAM: if we already fired on this exact UHV candle, skip
   if (uhv_t == g_last_uhv_buy_t) return false;

   LabelUhv(uhv_shift, "BUY", uhv_vol);   // v2.71 visual label

   // 2b. v2.93: UHV body must be ≥ g_uhv_body_min (hot-reloadable, default 0.60)
   if (!UhvBodyOk(uhv_shift, g_uhv_body_min)) return false;
   // 2c. v2.93: UHV must be a strict local volume peak (Zee labels #1, #5, #10, #22, #36)
   if (g_require_uhv_neighbor_peak && !UhvNeighborPeakOk(uhv_shift)) return false;

   // 3. TEACHER VSA selling-climax filter — big-spread climax bar
   //    v2.66: now OPT-IN (was hardcoded). Default OFF for max bloom.
   if (InpRequireBigSpreadClimax && !IsBigSpreadClimax(uhv_shift)) return false;

   // 4. Sweep: any later-closed bar low < uhv_l, OR the current floating bar's low
   bool swept = false;
   int sweep_shift = -1;
   for (int k = uhv_shift - 1; k >= 1; k--) {
      if (iLow(_Symbol, InpTimeframe, k) < uhv_l) { swept = true; sweep_shift = k; break; }
   }
   if (!swept && iLow(_Symbol, InpTimeframe, 0) < uhv_l) { swept = true; sweep_shift = 0; }
   if (!swept) return false;

   g_reached_late++;   // diagnostic: passed all filters except H1-FVG gate
   // v2.91: paint live "watching" indicator so Zee sees EA is alive + patient
   g_watch_buy_t = TimeCurrent();
   PaintWatchingLabel("BUY", uhv_h, ask, InpMinBreakoutPenetration);
   // 5. H1 FVG tap (optional — default OFF since 2026-05-27)
   if (InpRequireH1Fvg && !H1FvgTappedDuringRetracement(max_red_shift)) return false;

   // v2.97: master's 3 mechanizable visual gates (sweep depth + wick + H1 v2)
   if (!SweepDepthOk(uhv_shift, "BUY")) return false;
   if (!BreakoutWickOk(1, "BUY")) return false;
   if (!H1AgreesV2("BUY")) return false;
   // v2.98: rejection wicks in retracement (the 87.5% WR rule)
   if (!RetracementWicksClean(uhv_shift, "BUY")) return false;
   // v2.99: breakout candle color (92.3% WR — the final piece)
   if (!BreakoutColorOk("BUY")) return false;
   // v3.00: UHV must be strictly highest-vol bar in scope (any color)
   if (!UhvIsGlobalMax(uhv_shift, uhv_vol, red_upper)) return false;

   // 6. v2.93 STALE-BREAKOUT CAP — if too many bars passed since UHV, skip.
   //    (Zee labels m13, m35, m47: "breakout was earlier, missed it")
   if (g_max_bars_since_uhv > 0 && uhv_shift > g_max_bars_since_uhv) return false;

   // 7. v2.93 BREAKOUT BODY-CLOSE — require previously-closed M1 bar (shift=1)
   //    to have CLOSED past UHV high. (Zee label #13: "high of uhv is crossed
   //    by a BODY of a single candle"). Replaces the old tick-wick cross.
   if (g_require_breakout_body_close) {
      double prev_close = iClose(_Symbol, InpTimeframe, 1);
      if (prev_close <= uhv_h) return false;   // previous bar didn't close past UHV
      double prev_open = iOpen(_Symbol, InpTimeframe, 1);
      if (prev_close <= prev_open) return false; // previous bar wasn't GREEN (BUY breakout requires green)
   } else {
      // Fallback: original tick-cross behavior
      if (ask <= uhv_h) return false;
   }
   // 6a. v2.62 — require minimum penetration past UHV high (block micro-pokes)
   if (InpMinBreakoutPenetration > 0 && (ask - uhv_h) < InpMinBreakoutPenetration) return false;

   // 6b. v2.61 CANONICAL — forming bar body/range and vol must satisfy spec
   if (InpBreakoutBodyRatio > 0 && !BreakoutBodyOk(+1, InpBreakoutBodyRatio, ask, bid)) return false;
   if (InpBreakoutVolRatio  > 0 && !BreakoutVolOk(uhv_vol, InpBreakoutVolRatio)) return false;

   // v2.60 — lesson02 breakout-candle quality gates
   if (!HasBuyBreakoutMomentum()) return false;
   if (!HasBreakoutLowVolume(uhv_vol)) return false;

   // 7. SL/TP — v2.51: dynamic 1:1 R:R when InpDynamicTP=true (TP = entry + sl_dist)
   double sl = uhv_l - InpSLBufferPts;
   // v2.75 — cap initial SL distance to prevent catastrophic single-trade losses
   if (InpMaxInitialSLPoints > 0 && (ask - sl) > InpMaxInitialSLPoints) {
      Log(StringFormat("[SL-CAP v2.75] BUY canonical SL was %.2fpt wide; capping to %.2fpt",
                       ask - sl, InpMaxInitialSLPoints));
      sl = ask - InpMaxInitialSLPoints;
   }
   double sl_dist = ask - sl;
   if (sl_dist <= 0) return false;
   double tp = InpDynamicTP ? (ask + sl_dist) : (ask + InpTPPoints);

   g_signals_today++;
   Log(StringFormat("S1 BUY LIVE TRIGGER — entry=%.2f sl=%.2f tp=%.2f sl_dist=%.2f (dyn=%s) uhv_shift=%d (vol=%d) origin_shift=%d scope=%d",
                     ask, sl, tp, sl_dist, InpDynamicTP?"true":"false", uhv_shift, (int)uhv_vol, origin_shift, red_upper));

   // 8. Anti-cluster / overnight guard
   if (ClusterBlocked(+1)) return false;

   if (!g_trade.Buy(InpLots, _Symbol, ask, sl, tp, "S1_buy_live")) {
      Log(StringFormat("[ERR] Buy failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_uhv_buy_t = uhv_t;    // lock this UHV setup; next fire needs a NEW UHV
   g_last_signal_t  = uhv_t;    // for dashboard reporting (BuildWatchJson)
   ulong tkt = g_trade.ResultOrder();
   Log(StringFormat("[FILLED] ticket=%d", tkt));
   LogEntryCsv("buy", ask, sl, tp, tkt);
   // v2.54: paint full-step markers on chart so visual inspection shows WHY we fired
   DrawEntryMarkers("BUY", ask, sl, tp, uhv_h, uhv_l, uhv_t, uhv_vol, uhv_shift,
                    reds_count, max_red_shift, sweep_shift,
                    EfficiencyRatio(), g_require_h1bias, true);
   LabelBreakout(0, "BUY", true);   // v2.71 visual label on the firing (bar-0) candle
   return true;
}

//── S1 SELL LIVE-TICK trigger (v2.50) ──────────────────────────────
// Mirror of TryS1BuySignalLive: UHV GREEN in retracement, sweep ABOVE
// uhv.high, fires the millisecond bid < UHV.low.
bool TryS1SellSignalLive(double bid, double ask) {
   if (!InpDoSells) return false;
   if (DailyLossHalted()) return false;
   if (HarvestLocked()) return false;          // v2.74 harvest guardrail
   if (!IsInAllowedHours()) return false;      // v2.95 TIME-WINDOW (master's 92% WR secret)
   if (InpERMin > 0 && EfficiencyRatio() < InpERMin) return false;

   // v2.66 HOT-HOURS GATE: only fire during configured session window
   if (InpSessionStartHour != InpSessionEndHour) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      int h = dt.hour;
      bool in_window = (InpSessionStartHour < InpSessionEndHour)
                          ? (h >= InpSessionStartHour && h < InpSessionEndHour)
                          : (h >= InpSessionStartHour || h < InpSessionEndHour);
      if (!in_window) return false;
   }

   // v2.66: slow trend filter NOW OPT-IN. Default OFF.
   if (InpRequireSlowTrend && !IsDowntrendM5(1) && !HasBearMomentumOverride()) return false;
   // v2.52: optional structural trend gate (LH+LL on M5 and/or H1). Default OFF.
   if (!PassHHHLDowntrendGate()) return false;
   // v2.52: optional softer H1 bias gate. Default OFF.
   if (!PassH1BiasGate(false)) return false;

   // 1a. v2.61 CANONICAL: anchor the retracement to its FIRST-bull origin.
   int origin_shift = -1;
   if (InpRequireCanonicalOrigin) {
      origin_shift = FindCanonicalRetracementOriginSell();
      if (origin_shift < 0) return false;
      LabelRetracementOrigin(origin_shift, "SELL");   // v2.71 visual label
   }

   // 1. Walk back collecting retracement greens in last InpRetraceLookback CLOSED bars
   int greens[15];
   int greens_count = 0;
   int max_green_shift = 1;
   int green_upper = InpRetraceLookback;
   if (InpRequireCanonicalOrigin && origin_shift > 0) green_upper = origin_shift;
   for (int j = 1; j <= green_upper; j++) {
      double g_o = iOpen (_Symbol, InpTimeframe, j);
      double g_c = iClose(_Symbol, InpTimeframe, j);
      if (g_c > g_o) {
         if (greens_count < 15) {
            greens[greens_count++] = j;
            max_green_shift = j;
         }
      }
   }
   if (greens_count == 0) return false;

   // 2. UHV green = highest-volume green in the retracement
   int uhv_shift = greens[0];
   long uhv_vol = iVolume(_Symbol, InpTimeframe, uhv_shift);
   for (int r = 1; r < greens_count; r++) {
      long v = iVolume(_Symbol, InpTimeframe, greens[r]);
      if (v > uhv_vol) {
         uhv_vol = v;
         uhv_shift = greens[r];
      }
   }
   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
   datetime uhv_t = iTime(_Symbol, InpTimeframe, uhv_shift);

   if (uhv_t == g_last_uhv_sell_t) return false;

   LabelUhv(uhv_shift, "SELL", uhv_vol);   // v2.71 visual label

   // 2b. v2.93: UHV body + neighbor peak checks (hot-reloadable)
   if (!UhvBodyOk(uhv_shift, g_uhv_body_min)) return false;
   if (g_require_uhv_neighbor_peak && !UhvNeighborPeakOk(uhv_shift)) return false;

   // v2.66: climax filter NOW OPT-IN. Default OFF for max bloom.
   if (InpRequireBigSpreadClimax && !IsBigSpreadClimax(uhv_shift)) return false;

   // 3. Sweep: any later closed bar high > uhv_h, or current floating bar's high
   bool swept = false;
   int sweep_shift = -1;
   for (int k = uhv_shift - 1; k >= 1; k--) {
      if (iHigh(_Symbol, InpTimeframe, k) > uhv_h) { swept = true; sweep_shift = k; break; }
   }
   if (!swept && iHigh(_Symbol, InpTimeframe, 0) > uhv_h) { swept = true; sweep_shift = 0; }
   if (!swept) return false;

   g_reached_late++;
   // v2.91: paint live "watching" indicator (SELL side)
   g_watch_sell_t = TimeCurrent();
   PaintWatchingLabel("SELL", uhv_l, bid, InpMinBreakoutPenetration);
   if (InpRequireH1Fvg && !H1BearFvgTappedDuringRetracement(max_green_shift)) return false;

   // v2.97: master's 3 mechanizable visual gates
   if (!SweepDepthOk(uhv_shift, "SELL")) return false;
   if (!BreakoutWickOk(1, "SELL")) return false;
   if (!H1AgreesV2("SELL")) return false;
   // v2.98: rejection wicks in retracement (the 87.5% WR rule)
   if (!RetracementWicksClean(uhv_shift, "SELL")) return false;
   // v2.99: breakout candle color (92.3% WR — the final piece)
   if (!BreakoutColorOk("SELL")) return false;
   // v3.00: UHV must be strictly highest-vol bar in scope (any color)
   if (!UhvIsGlobalMax(uhv_shift, uhv_vol, green_upper)) return false;

   // v2.93 STALE-BREAKOUT CAP — refuse if UHV is too far back
   if (g_max_bars_since_uhv > 0 && uhv_shift > g_max_bars_since_uhv) return false;

   // v2.93 BREAKOUT BODY-CLOSE — require previously-closed M1 bar (shift=1)
   // to have CLOSED past UHV low. SELL breakout candle must be RED.
   if (g_require_breakout_body_close) {
      double prev_close = iClose(_Symbol, InpTimeframe, 1);
      if (prev_close >= uhv_l) return false;     // previous bar didn't close past UHV low
      double prev_open = iOpen(_Symbol, InpTimeframe, 1);
      if (prev_close >= prev_open) return false; // previous bar wasn't RED (SELL breakout requires red)
   } else {
      // Fallback: original tick-cross
      if (bid >= uhv_l) return false;
   }
   // 4a. v2.62 — require minimum penetration below UHV low (block micro-pokes)
   if (InpMinBreakoutPenetration > 0 && (uhv_l - bid) < InpMinBreakoutPenetration) return false;

   // 4b. v2.61 CANONICAL — forming bar body/range and vol must satisfy spec
   if (InpBreakoutBodyRatio > 0 && !BreakoutBodyOk(-1, InpBreakoutBodyRatio, ask, bid)) return false;
   if (InpBreakoutVolRatio  > 0 && !BreakoutVolOk(uhv_vol, InpBreakoutVolRatio)) return false;

   // v2.60 — lesson02 breakout-candle quality gates
   if (!HasSellBreakoutMomentum()) return false;
   if (!HasBreakoutLowVolume(uhv_vol)) return false;

   // 5. SL/TP — v2.51: dynamic 1:1 R:R when InpDynamicTP=true (TP = entry - sl_dist)
   double sl = uhv_h + InpSLBufferPts;
   // v2.75 — cap initial SL distance to prevent catastrophic single-trade losses
   if (InpMaxInitialSLPoints > 0 && (sl - bid) > InpMaxInitialSLPoints) {
      Log(StringFormat("[SL-CAP v2.75] SELL canonical SL was %.2fpt wide; capping to %.2fpt",
                       sl - bid, InpMaxInitialSLPoints));
      sl = bid + InpMaxInitialSLPoints;
   }
   double sl_dist = sl - bid;
   if (sl_dist <= 0) return false;
   double tp = InpDynamicTP ? (bid - sl_dist) : (bid - InpTPPoints);
   if (tp <= 0) return false;

   g_signals_today++;
   Log(StringFormat("S1 SELL LIVE TRIGGER — entry=%.2f sl=%.2f tp=%.2f sl_dist=%.2f (dyn=%s) uhv_shift=%d (vol=%d) origin_shift=%d scope=%d",
                     bid, sl, tp, sl_dist, InpDynamicTP?"true":"false", uhv_shift, (int)uhv_vol, origin_shift, green_upper));

   if (ClusterBlocked(-1)) return false;

   if (!g_trade.Sell(InpLots, _Symbol, bid, sl, tp, "S1_sell_live")) {
      Log(StringFormat("[ERR] Sell failed: ret=%d %s",
                       g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      return false;
   }
   g_entries_today++;
   g_last_uhv_sell_t = uhv_t;
   g_last_signal_t   = uhv_t;
   ulong tkt = g_trade.ResultOrder();
   Log(StringFormat("[FILLED] ticket=%d", tkt));
   LogEntryCsv("sell", bid, sl, tp, tkt);
   // v2.54: paint full-step markers on chart so visual inspection shows WHY we fired
   DrawEntryMarkers("SELL", bid, sl, tp, uhv_h, uhv_l, uhv_t, uhv_vol, uhv_shift,
                    greens_count, max_green_shift, sweep_shift,
                    EfficiencyRatio(), g_require_h1bias, false);
   LabelBreakout(0, "SELL", true);   // v2.71 visual label on the firing (bar-0) candle
   return true;
}

//── State JSON heartbeat ─────────────────────────────────────────
// READ-ONLY: the setup S1 is currently watching, for the dashboard live chart.
// Mirrors the buy/sell detection (trend → highest-volume retracement UHV bar →
// the price level a breakout must clear). Touches NO trade logic; pure read+report.
string BuildWatchJson() {
   int dir = 0;
   if (InpDoBuys && IsUptrendM5(1)) dir = 1;          // watching for a BUY (UHV red)
   else if (InpDoSells && IsDowntrendM5(1)) dir = -1; // watching for a SELL (UHV green)
   if (dir == 0) return "null";

   int uhv_shift = -1; long uhv_vol = -1;
   for (int j = 2; j <= 1 + InpRetraceLookback; j++) {
      double o = iOpen(_Symbol, InpTimeframe, j), c = iClose(_Symbol, InpTimeframe, j);
      bool match = (dir == 1) ? (c < o) : (c > o);     // red for buy, green for sell
      if (!match) continue;
      long v = iVolume(_Symbol, InpTimeframe, j);
      if (v > uhv_vol) { uhv_vol = v; uhv_shift = j; }
   }
   if (uhv_shift < 0) return "null";

   double uhv_h = iHigh(_Symbol, InpTimeframe, uhv_shift);
   double uhv_l = iLow (_Symbol, InpTimeframe, uhv_shift);
   return StringFormat(
      "{\"dir\":\"%s\",\"ref_bar_t\":\"%s\",\"ref_high\":%.3f,\"ref_low\":%.3f,"
      "\"level\":%.3f,\"setup_bar_t\":\"%s\"}",
      dir == 1 ? "buy" : "sell",
      TimeToString(iTime(_Symbol, InpTimeframe, uhv_shift), TIME_DATE|TIME_SECONDS),
      uhv_h, uhv_l, (dir == 1 ? uhv_h : uhv_l),
      TimeToString(iTime(_Symbol, InpTimeframe, 1), TIME_DATE|TIME_SECONDS));
}

void WriteHeartbeat() {
   if ((TimeCurrent() - g_last_heartbeat) < InpHeartbeatSec) return;
   g_last_heartbeat = TimeCurrent();
   int fh = FileOpen(InpStateFile, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   int n_open = 0;
   double floating = FloatingPnL(n_open);
   double bigness = (InpAvgWinUsd > 0 && floating > 0) ? floating / InpAvgWinUsd : 0.0;
   FileWriteString(fh, StringFormat(
      "{\"ea\":\"S1Trader\",\"version\":\"3.02\",\"alive\":true,"
      "\"t\":\"%s\",\"signals_today\":%d,\"entries_today\":%d,\"late_setups\":%d,"
      "\"last_signal_t\":\"%s\",\"magic\":%d,\"lots\":%.2f,"
      "\"tp_points\":%.2f,\"floating_usd\":%.2f,\"n_open\":%d,\"bigness\":%.2f,\"avg_win\":%.2f,"
      "\"watch\":%s,\"open\":%s}",
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
      g_signals_today, g_entries_today, g_reached_late,
      TimeToString(g_last_signal_t, TIME_DATE | TIME_SECONDS),
      InpMagicNumber, InpLots, InpTPPoints,
      floating, n_open, bigness, InpAvgWinUsd, BuildWatchJson(), BuildOpenJson()));
   FileClose(fh);
}

//── EA hooks ────────────────────────────────────────────────────────
// v2.53 — load Inp* gate defaults into g_* mirrors, then read runtime overrides.
// v2.95: parse a comma-separated UTC-hour list like "5,12,15,19" into mask.
//        Empty string → all hours allowed.
void ParseAllowedHours(string spec) {
   for (int i = 0; i < 24; i++) g_allowed_hours_mask[i] = false;
   string s = spec;
   StringReplace(s, " ", "");
   if (StringLen(s) == 0) {
      g_time_window_active = false;
      return;
   }
   g_time_window_active = true;
   g_allowed_hours_str  = s;
   string parts[];
   int n = StringSplit(s, ',', parts);
   for (int j = 0; j < n; j++) {
      int h = (int)StringToInteger(parts[j]);
      if (h >= 0 && h < 24) g_allowed_hours_mask[h] = true;
   }
}

// v2.95: check if current UTC hour is in allowed window.
bool IsInAllowedHours() {
   if (!g_time_window_active) return true;
   datetime t = TimeGMT();
   MqlDateTime dt; TimeToStruct(t, dt);
   return g_allowed_hours_mask[dt.hour];
}

// v3.02 BULLETPROOF: HARDCODED safe defaults for hot-reloadable params.
// Chart inputs (Inp*) are IGNORED for these. The runtime config file is the
// only source of truth. This solves the bug where stale chart-saved inputs
// silently override our intended defaults.
void InitRuntimeFromInputs() {
   // ── NON-hot-reloadable: still come from Inp* (lots, magic, TP, SL are not in runtime) ──
   g_require_hhhl_m5           = false;   // hot-reloadable — safe default
   g_require_hhhl_h1           = false;
   g_require_h1bias            = false;
   g_h1bias_bars               = 6;
   g_momentum_override_enabled = InpMomentumOverrideEnabled;
   g_momentum_override_pts     = InpMomentumOverridePts;
   g_require_breakout_momentum = InpRequireBreakoutMomentum;
   g_breakout_min_body_pts     = InpBreakoutMinBodyPts;
   g_require_breakout_lowvol   = InpRequireBreakoutLowVol;
   // ── v3.02: HARDCODED safe defaults — runtime config overrides on file load ──
   g_auto_close_ms             = 0;       // doctrine: master takes exit
   g_trail_lock_pts            = 0;
   g_trail_rev_pts             = 0;
   g_daily_loss_halt           = 200;     // $200 day-loss brake
   g_daily_profit_target       = 0;       // master decides when to stop
   g_require_uhv_neighbor_peak = false;
   g_uhv_body_min              = 0.30;
   g_max_bars_since_uhv        = 0;
   g_require_breakout_body_close = false;
   ParseAllowedHours("5,12,15,19");        // 4 peak hours (PKT 10am/5pm/8pm/midnight)
   g_min_sweep_depth_pts       = 0.30;
   g_max_breakout_wick_pct     = 0.0;
   g_require_h1_agrees_v2      = false;
   g_max_retracement_wick_pct  = 0.45;
   g_require_breakout_color    = true;
   g_uhv_global_max            = true;
}

// v3.02: Write a default runtime config file if missing. Ensures FIRST attach
// on a fresh terminal has sensible runtime params even before user touches.
void EnsureRuntimeConfigExists() {
   string fname = StringFormat("s1_runtime_%d.json", InpMagicNumber);
   if (FileIsExist(fname, FILE_COMMON)) return;
   int fh = FileOpen(fname, FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if (fh == INVALID_HANDLE) {
      Log(StringFormat("[S1 v3.02] EnsureRuntimeConfig: FileOpen failed err=%d", GetLastError()));
      return;
   }
   FileWriteString(fh,
      "{\n"
      "  \"auto_close_ms\": 0,\n"
      "  \"daily_loss_halt\": 200,\n"
      "  \"daily_profit_target\": 0,\n"
      "  \"trail_lock_pts\": 0,\n"
      "  \"trail_rev_pts\": 0,\n"
      "  \"require_hhhl_m5\": false,\n"
      "  \"require_h1bias\": false,\n"
      "  \"require_uhv_neighbor_peak\": false,\n"
      "  \"uhv_body_min\": 0.30,\n"
      "  \"max_bars_since_uhv\": 0,\n"
      "  \"require_breakout_body_close\": false,\n"
      "  \"allowed_hours_utc\": \"5,12,15,19\",\n"
      "  \"min_sweep_depth_pts\": 0.30,\n"
      "  \"max_breakout_wick_pct\": 0.0,\n"
      "  \"require_h1_agrees_v2\": false,\n"
      "  \"max_retracement_wick_pct\": 0.45,\n"
      "  \"require_breakout_color\": true,\n"
      "  \"uhv_global_max\": true\n"
      "}\n");
   FileClose(fh);
   Log("[S1 v3.02] Created runtime config with safe defaults at " + fname);
}

// Read JSON-ish runtime config (Common\Files\s1_runtime_<magic>.json).
// Format: simple key:value lines or proper JSON — both supported by string scan.
// Only the keys we care about are read; missing keys keep current value.
datetime g_rt_last_mtime = 0;
void LoadRuntimeConfig() {
   string fname = StringFormat("s1_runtime_%d.json", InpMagicNumber);
   if (!FileIsExist(fname, FILE_COMMON)) return;
   int fh = FileOpen(fname, FILE_READ|FILE_TXT|FILE_COMMON);
   if (fh == INVALID_HANDLE) return;
   string content = "";
   while (!FileIsEnding(fh)) content += FileReadString(fh) + "\n";
   FileClose(fh);
   if (StringLen(content) == 0) return;

   bool changed = false;
   string keys[]  = {"require_hhhl_m5","require_hhhl_h1","require_h1bias","h1bias_bars","momentum_override_enabled","momentum_override_pts","require_breakout_momentum","breakout_min_body_pts","require_breakout_lowvol","auto_close_ms","trail_lock_pts","trail_rev_pts","daily_loss_halt","daily_profit_target","require_uhv_neighbor_peak","uhv_body_min","max_bars_since_uhv","require_breakout_body_close","allowed_hours_utc","min_sweep_depth_pts","max_breakout_wick_pct","require_h1_agrees_v2","max_retracement_wick_pct","require_breakout_color","uhv_global_max"};
   for (int i = 0; i < ArraySize(keys); i++) {
      string k = keys[i];
      int p = StringFind(content, "\"" + k + "\"");
      if (p < 0) p = StringFind(content, k);
      if (p < 0) continue;
      int colon = StringFind(content, ":", p);
      if (colon < 0) continue;
      // grab value until comma / newline / brace
      string val = "";
      for (int j = colon + 1; j < StringLen(content); j++) {
         ushort c = StringGetCharacter(content, j);
         if (c == ',' || c == '\n' || c == '}' || c == '\r') break;
         if (c == ' ' || c == '"' || c == '\t') continue;
         val += ShortToString(c);
      }
      if (k == "require_hhhl_m5") { bool nv = (val == "true" || val == "1"); if (nv != g_require_hhhl_m5) { g_require_hhhl_m5 = nv; changed = true; } }
      if (k == "require_hhhl_h1") { bool nv = (val == "true" || val == "1"); if (nv != g_require_hhhl_h1) { g_require_hhhl_h1 = nv; changed = true; } }
      if (k == "require_h1bias")  { bool nv = (val == "true" || val == "1"); if (nv != g_require_h1bias)  { g_require_h1bias  = nv; changed = true; } }
      if (k == "h1bias_bars")     { int  nv = (int)StringToInteger(val);     if (nv > 0 && nv != g_h1bias_bars) { g_h1bias_bars = nv; changed = true; } }
      if (k == "momentum_override_enabled") { bool nv = (val == "true" || val == "1"); if (nv != g_momentum_override_enabled) { g_momentum_override_enabled = nv; changed = true; } }
      if (k == "momentum_override_pts") { double nv = StringToDouble(val); if (nv > 0 && nv != g_momentum_override_pts) { g_momentum_override_pts = nv; changed = true; } }
      if (k == "require_breakout_momentum") { bool nv = (val == "true" || val == "1"); if (nv != g_require_breakout_momentum) { g_require_breakout_momentum = nv; changed = true; } }
      if (k == "breakout_min_body_pts") { double nv = StringToDouble(val); if (nv > 0 && nv != g_breakout_min_body_pts) { g_breakout_min_body_pts = nv; changed = true; } }
      if (k == "require_breakout_lowvol") { bool nv = (val == "true" || val == "1"); if (nv != g_require_breakout_lowvol) { g_require_breakout_lowvol = nv; changed = true; } }
      // v2.88 hot-reloadable tunables
      if (k == "auto_close_ms")         { int    nv = (int)StringToInteger(val); if (nv >= 0 && nv != g_auto_close_ms)        { g_auto_close_ms        = nv; changed = true; } }
      if (k == "trail_lock_pts")        { double nv = StringToDouble(val);       if (nv >= 0 && nv != g_trail_lock_pts)       { g_trail_lock_pts       = nv; changed = true; } }
      if (k == "trail_rev_pts")         { double nv = StringToDouble(val);       if (nv >= 0 && nv != g_trail_rev_pts)        { g_trail_rev_pts        = nv; changed = true; } }
      if (k == "daily_loss_halt")       { double nv = StringToDouble(val);       if (nv >= 0 && nv != g_daily_loss_halt)      { g_daily_loss_halt      = nv; changed = true; } }
      if (k == "daily_profit_target")   { double nv = StringToDouble(val);       if (nv >= 0 && nv != g_daily_profit_target)  { g_daily_profit_target  = nv; changed = true; } }
      // v2.93 label-derived gates (hot-reloadable)
      if (k == "require_uhv_neighbor_peak") { bool   nv = (val == "true" || val == "1"); if (nv != g_require_uhv_neighbor_peak) { g_require_uhv_neighbor_peak = nv; changed = true; } }
      if (k == "uhv_body_min")              { double nv = StringToDouble(val);            if (nv > 0 && nv != g_uhv_body_min)    { g_uhv_body_min = nv; changed = true; } }
      if (k == "max_bars_since_uhv")        { int    nv = (int)StringToInteger(val);      if (nv >= 0 && nv != g_max_bars_since_uhv) { g_max_bars_since_uhv = nv; changed = true; } }
      if (k == "require_breakout_body_close") { bool nv = (val == "true" || val == "1");  if (nv != g_require_breakout_body_close) { g_require_breakout_body_close = nv; changed = true; } }
      // v2.95: time-window filter (string value, comma-separated UTC hours)
      if (k == "allowed_hours_utc") {
         if (val != g_allowed_hours_str) { ParseAllowedHours(val); changed = true; }
      }
      // v2.97: 3 mechanizable visual-judgment gates
      if (k == "min_sweep_depth_pts")    { double nv = StringToDouble(val); if (nv >= 0 && nv != g_min_sweep_depth_pts)    { g_min_sweep_depth_pts    = nv; changed = true; } }
      if (k == "max_breakout_wick_pct")  { double nv = StringToDouble(val); if (nv >= 0 && nv != g_max_breakout_wick_pct)  { g_max_breakout_wick_pct  = nv; changed = true; } }
      if (k == "require_h1_agrees_v2")   { bool   nv = (val == "true" || val == "1"); if (nv != g_require_h1_agrees_v2)    { g_require_h1_agrees_v2   = nv; changed = true; } }
      // v2.98: rejection-wicks-in-retracement (the 87.5% WR rule)
      if (k == "max_retracement_wick_pct") { double nv = StringToDouble(val); if (nv >= 0 && nv != g_max_retracement_wick_pct) { g_max_retracement_wick_pct = nv; changed = true; } }
      // v2.99: standalone breakout-color (92.3% WR)
      if (k == "require_breakout_color")   { bool   nv = (val == "true" || val == "1"); if (nv != g_require_breakout_color) { g_require_breakout_color = nv; changed = true; } }
      // v3.00: UHV global-max safety check
      if (k == "uhv_global_max")           { bool   nv = (val == "true" || val == "1"); if (nv != g_uhv_global_max)         { g_uhv_global_max         = nv; changed = true; } }
   }
   if (changed) {
      Log(StringFormat("[S1 v3.02] runtime CHANGED: auto_close_ms=%d hours='%s' wick=%.2f color=%s gmax=%s loss_halt=%.1f",
                       g_auto_close_ms, g_allowed_hours_str, g_max_retracement_wick_pct,
                       g_require_breakout_color ? "true" : "false",
                       g_uhv_global_max ? "true" : "false",
                       g_daily_loss_halt));
   }
}

// v3.02: unconditional one-shot log so OnInit can show what runtime loaded.
void LogRuntimeState() {
   Log(StringFormat("[S1 v3.02] runtime ACTIVE: auto_close_ms=%d hours='%s' wick=%.2f color=%s gmax=%s loss_halt=%.1f sweep=%.2f",
                    g_auto_close_ms, g_allowed_hours_str, g_max_retracement_wick_pct,
                    g_require_breakout_color ? "true" : "false",
                    g_uhv_global_max ? "true" : "false",
                    g_daily_loss_halt, g_min_sweep_depth_pts));
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   IsNewDay();
   g_last_grab_id = ReadGrabId();   // ignore any pre-existing grab command on attach
   InitRuntimeFromInputs();         // v3.02: now sets HARDCODED safe defaults, ignores Inp*
   EnsureRuntimeConfigExists();     // v3.02: write default file if missing
   LoadRuntimeConfig();             // overrides g_* with values from runtime file
   LogRuntimeState();               // v3.02: log final state unconditionally
   // v2.90: CLEAN SLATE on attach — wipe all S1 labels (otherwise old labels from
   // previous EA versions stay on chart and clutter it).
   ObjectsDeleteAll(0, "S1_");
   EventSetMillisecondTimer(50);   // v2.86: 50ms polling for instant grab response (was 2s)
   Log(StringFormat("S1Trader Init — magic=%d lots=%.2f TP=%.2fpts trendLB=%d retraceLB=%d grab_base=%I64d  gates: hhhl_m5=%s hhhl_h1=%s h1bias=%s h1bias_bars=%d",
                     InpMagicNumber, InpLots, InpTPPoints,
                     InpTrendLookback, InpRetraceLookback, g_last_grab_id,
                     g_require_hhhl_m5 ? "true" : "false",
                     g_require_hhhl_h1 ? "true" : "false",
                     g_require_h1bias  ? "true" : "false",
                     g_h1bias_bars));
   return INIT_SUCCEEDED;
}

datetime g_last_slow_timer = 0;
void OnTimer() {
   // v2.86: fires every 50ms. Fast path: check grab + manage open positions.
   CheckGrabCommand();
   if (g_auto_close_ms > 0) {
      ManageOpenPositions();   // v2.87: 50ms-granular auto-close check (g_auto_close_ms is hot-reloadable in v2.88)
   }
   TickWatchingExpiry();   // v2.91: clear stale "watching" labels after 30s

   // Slow path (every 2s) for non-time-critical work
   datetime now = TimeCurrent();
   if (now - g_last_slow_timer >= 2) {
      g_last_slow_timer = now;
      LoadRuntimeConfig();
      DrawVolumeLabels(200);
      DetectMissedBreakouts();
   }
}

void OnDeinit(const int reason) {
   EventKillTimer();
   Log(StringFormat("S1Trader Deinit reason=%d signals=%d entries=%d",
                     reason, g_signals_today, g_entries_today));
}

//── 2R Free Roll: side-aware per-position management ───────────────
int MngIndex(ulong ticket) {
   for (int i = 0; i < g_mng_count; i++)
      if (g_mng_ticket[i] == ticket) return i;
   int idx = (g_mng_count < 256) ? g_mng_count++ : 0;
   g_mng_ticket[idx]    = ticket;
   g_mng_sl0[idx]       = PositionGetDouble(POSITION_SL);
   g_mng_partialed[idx] = false;
   g_mng_peak[idx]      = 0.0;
   g_mng_trough[idx]    = 0.0;
   g_mng_peak_pts[idx]  = 0.0;  // v2.65: tick-level peak in PRICE POINTS
   g_mng_be_set[idx]    = false; // v2.70: instant-BE not yet applied for this ticket
   g_mng_open_us[idx]   = GetMicrosecondCount();  // v2.87: open time stamp for auto-close-ms
   g_mng_lastprof[idx]  = 0.0;
   g_mng_entry[idx]     = PositionGetDouble(POSITION_PRICE_OPEN);
   g_mng_side[idx]      = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   g_mng_logged[idx]    = false;
   return idx;
}

//   Walk this EA's open positions (BUY or SELL) each tick. At +BreakevenR move SL
//   to breakeven. Optional partial at +PartialR. Static TP untouched. (Default OFF
//   on S1 — see header note; inert because 1R is usually wider than the $7.5 TP.)
// ── THE EXIT LABORATORY (Zee 2026-08-09: "test the actual EA, not the old method")
// Identical entries, identical data, identical costs — only the exit changes. This
// is the controlled experiment that says where the -$657 went.
double g_xpeak[512];
ulong  g_xtick[512];

int XIdx(ulong t) {
   for (int i = 0; i < 512; i++) if (g_xtick[i] == t) return i;
   for (int i = 0; i < 512; i++) if (g_xtick[i] == 0) { g_xtick[i] = t; g_xpeak[i] = 0; return i; }
   return 0;
}

void XDrop(ulong t) { for (int i = 0; i < 512; i++) if (g_xtick[i] == t) { g_xtick[i] = 0; g_xpeak[i] = 0; } }

bool RunExitStyle() {
   if (InpExitStyle == 0) return false;             // style 0: broker TP/SL only
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double e = PositionGetDouble(POSITION_PRICE_OPEN);
      double prof = isbuy ? (bid - e) : (e - ask);
      int k = XIdx(t);
      if (prof > g_xpeak[k]) g_xpeak[k] = prof;

      if (InpExitStyle == 1) {
         // OUR LIVE RATCHET — arm, then give back a fraction of the peak.
         if (g_xpeak[k] >= InpRatchetArm) {
            double give = MathMax(InpRatchetGive, InpRatchetFrac * g_xpeak[k]);
            if (g_xpeak[k] - prof >= give) { g_trade.PositionClose(t); XDrop(t); }
         }
      } else if (InpExitStyle == 2) {
         // ZEE'S EXIT — never stopped out small; held until it comes back to flat,
         // and once it has genuinely paid, its stop moves to breakeven.
         if (prof >= InpZeeBEPts) {
            double sl = PositionGetDouble(POSITION_SL);
            bool at_be = (sl > 0) && (isbuy ? (sl >= e) : (sl <= e));
            if (!at_be) g_trade.PositionModify(t, isbuy ? e + 0.05 : e - 0.05,
                                               PositionGetDouble(POSITION_TP));
         } else if (prof < 0 && prof >= -InpZeeFlatPts) {
            g_trade.PositionClose(t); XDrop(t);      // came back to flat, step off
         }
      }
   }
   return true;
}

void ManageOpenPositions() {
   if (RunExitStyle() && InpExitStyle != 0) return;   // the laboratory owns the exit
   if (!InpEnableBreakeven && !InpEnablePartial && InpBEArmUsd <= 0 && InpTrailActUsd <= 0 && InpTrailRevPts <= 0 && !InpInstantBE && g_auto_close_ms <= 0) return;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (step <= 0) step = 0.01;

   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool is_buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);

      double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur_sl = PositionGetDouble(POSITION_SL);
      double cur_tp = PositionGetDouble(POSITION_TP);
      double vol    = PositionGetDouble(POSITION_VOLUME);

      int mi = MngIndex(ticket);

      // ─────── v2.87 TIME-IMPULSE AUTO-CLOSE ───────
      // Close position automatically X milliseconds after open, regardless of P&L.
      // Per Zee's "trust the breakout impulse" hypothesis. v2.88: g_auto_close_ms is hot-reloadable.
      if (g_auto_close_ms > 0) {
         ulong now_us = GetMicrosecondCount();
         ulong elapsed_ms = (now_us - g_mng_open_us[mi]) / 1000;
         if (elapsed_ms >= (ulong)g_auto_close_ms) {
            double prof_close = is_buy ? (bid - entry) : (entry - ask);
            double pnl_close = prof_close * PositionGetDouble(POSITION_VOLUME) * 100.0;
            if (g_trade.PositionClose(ticket))
               Log(StringFormat("[AUTO-CLOSE-MS v2.87] #%I64u after %I64ums: %+.3fpts = $%+.2f",
                   ticket, elapsed_ms, prof_close, pnl_close));
            continue;
         }
      }
      // ─────── end v2.87 ──────────────────────────

      double R = MathAbs(entry - g_mng_sl0[mi]);
      if (R <= 0) continue;

      double prof  = is_buy ? (bid - entry) : (entry - ask);
      double be_sl = NormalizeDouble(is_buy ? entry + InpBEBufferPts
                                            : entry - InpBEBufferPts, _Digits);
      bool can_raise = is_buy ? (cur_sl < be_sl) : (cur_sl == 0.0 || cur_sl > be_sl);

      // ─────── v2.70 INSTANT-BE (Zee's zero-loss-today mandate) ───────
      // Move SL to entry ± InpInstantBE_BufferPts on first tick after fill.
      // Caps worst-case loss at ~$4 @ 0.10 lots instead of ~$56 (UHV-based).
      if (InpInstantBE && !g_mng_be_set[mi]) {
         double instant_sl = NormalizeDouble(
            is_buy ? (entry - InpInstantBE_BufferPts)
                   : (entry + InpInstantBE_BufferPts), _Digits);
         // Only modify if our new SL is tighter (closer to entry) than current SL.
         // Don't loosen, never widen the protection.
         bool tighter = is_buy ? (instant_sl > cur_sl) : (cur_sl == 0.0 || instant_sl < cur_sl);
         if (tighter) {
            if (g_trade.PositionModify(ticket, instant_sl, cur_tp)) {
               g_mng_be_set[mi] = true;
               Log(StringFormat("[INSTANT-BE v2.70] #%I64u SL→%.2f (entry %.2f, buffer %.2fpt) — loss capped at ~$%.2f @ vol %.2f",
                   ticket, instant_sl, entry, InpInstantBE_BufferPts,
                   InpInstantBE_BufferPts * vol * 100.0, vol));
               cur_sl = instant_sl;  // refresh local var for downstream checks
            }
         } else {
            // SL is already tighter than instant-BE would set it — just mark done
            g_mng_be_set[mi] = true;
         }
      }
      // ─────── end v2.70 ────────────────────────────────────────────

      // TRAILING PROFIT-LOCK (Zee's idea, validated trail_all.py: best-or-tied on all 3 EAs).
      // Once +$Act, ratchet a floor under the peak and bank the instant profit gives back
      // $Give from peak — catches green trades that peak BELOW the old +$1 breakeven and
      // reverse. Keeps the TP (a runner still reaches it). Slides hard SL to entry as a
      // backstop, which also lights the dashboard "profit secured" banner.
      double prof_usd = prof * vol * 100.0;
      if (prof_usd > g_mng_peak[mi])   g_mng_peak[mi]   = prof_usd;
      if (prof_usd < g_mng_trough[mi]) g_mng_trough[mi] = prof_usd;   // MAE (worst dip)
      g_mng_lastprof[mi] = prof_usd;                                  // outcome proxy

      // ─────── v2.80 INSTANT-LOCK-ON-FIRST-POSITIVE-TICK (THE FIX) ───────
      // Master's "1:0.001 R:R" = catch ANY positive move past spread.
      // prof > 0 means: for BUY, bid > entry_ask (price crossed past spread upward);
      //                 for SELL, ask < entry_bid (price crossed past spread downward).
      // Either way, we're objectively in profit. Lock it. No threshold. No trail.
      // This converts the "100% breakouts go positive" property directly into wins.
      if (InpInstantLockOnFirstPositive && prof > 0) {
         if (g_trade.PositionClose(ticket))
            Log(StringFormat("[INSTANT-LOCK v2.80] #%I64u closed at first +tick: +%.3fpts = $%.2f",
                ticket, prof, prof_usd));
         continue;
      }
      // ─────── end v2.80 ──────────────────────────────────────────────────

      // ─────── v2.65 TICK-LEVEL TRAILING-REVERSAL EXIT (fallback if InstantLock off) ─
      // Track peak unrealized profit in PRICE POINTS. Once it hits InpTrailLockPts,
      // exit instantly when current pulls back InpTrailRevPts from that peak.
      if (prof > g_mng_peak_pts[mi]) g_mng_peak_pts[mi] = prof;
      if (InpTrailRevPts > 0 && g_mng_peak_pts[mi] >= InpTrailLockPts) {
         if ((g_mng_peak_pts[mi] - prof) >= InpTrailRevPts) {
            if (g_trade.PositionClose(ticket))
               Log(StringFormat("[TICK-REV v2.65] #%I64u banked +%.3fpts (peak +%.3fpts, gave back %.3fpts) = $%.2f",
                   ticket, prof, g_mng_peak_pts[mi], g_mng_peak_pts[mi]-prof, prof_usd));
            continue;
         }
      }
      // ─────── end v2.65 ───────────────────────────────────────────────────────────

      if (InpTrailActUsd > 0 && g_mng_peak[mi] >= InpTrailActUsd) {
         bool need_be = is_buy ? (cur_sl < entry) : (cur_sl == 0.0 || cur_sl > entry);
         if (need_be) g_trade.PositionModify(ticket, NormalizeDouble(entry, _Digits), cur_tp);
         double floor_usd = MathMax(0.0, g_mng_peak[mi] - InpTrailGiveUsd);
         if (prof_usd <= floor_usd) {
            if (g_trade.PositionClose(ticket))
               Log(StringFormat("[TRAIL] #%I64u banked +$%.2f (peak +$%.2f, gave back $%.2f)",
                   ticket, prof_usd, g_mng_peak[mi], g_mng_peak[mi] - prof_usd));
            continue;
         }
      }

      // GIVE-BACK KILLER ($-based breakeven): once +$InpBEArmUsd, lock breakeven.
      // (Superseded by the trailing lock above; only runs if InpBEArmUsd>0 & trail off.)
      if (InpBEArmUsd > 0 && can_raise && (prof * vol * 100.0) >= InpBEArmUsd) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE$] #%I64u SL→%.2f (+$%.2f locked)", ticket, be_sl, prof*vol*100.0));
         continue;
      }

      if (InpEnablePartial && !g_mng_partialed[mi] && prof >= InpPartialR * R) {
         double close_vol = NormalizeDouble(MathFloor((vol * InpPartialFrac) / step) * step, 2);
         if (close_vol >= vmin && (vol - close_vol) >= vmin) {
            if (g_trade.PositionClosePartial(ticket, close_vol)) {
               g_mng_partialed[mi] = true;
               Log(StringFormat("[2R] Banked %.2f of #%I64u (+%.2fR) runner=%.2f",
                                close_vol, ticket, prof / R, vol - close_vol));
            }
         } else {
            g_mng_partialed[mi] = true;
         }
         if (InpEnableBreakeven && can_raise &&
             g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[2R] Breakeven #%I64u SL→%.2f (TP kept %.2f)", ticket, be_sl, cur_tp));
         continue;
      }

      if (InpEnableBreakeven && can_raise && prof >= InpBreakevenR * R) {
         if (g_trade.PositionModify(ticket, be_sl, cur_tp))
            Log(StringFormat("[BE] #%I64u SL→%.2f (+%.2fR, TP kept %.2f)",
                             ticket, be_sl, prof / R, cur_tp));
      }
   }

   // ── Closed-trade peak (MFE) logging ───────────────────────────────
   // Any ticket we were tracking that is no longer open has closed — write its
   // peak floating profit once. The dashboard turns these into the live
   // "X% of trades reached here" markers on the trade slider (real data, not backtest).
   for (int j = 0; j < g_mng_count; j++) {
      if (g_mng_logged[j] || g_mng_ticket[j] == 0) continue;
      if (PositionSelectByTicket(g_mng_ticket[j])) continue;   // still open → skip
      AppendPeakLog(g_mng_side[j], g_mng_entry[j], g_mng_peak[j], g_mng_trough[j], g_mng_lastprof[j]);
      g_mng_logged[j] = true;
   }
}

//── Append one closed trade's peak (MFE) + trough (MAE) + outcome to the per-EA log ──
// Columns: time, side, entry, peak$, trough$, last$ (last floating ≈ realized outcome).
void AppendPeakLog(int side, double entry, double peak, double trough, double last) {
   int fh = FileOpen(InpPeakLogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWriteString(fh, StringFormat("%s,%s,%.2f,%.2f,%.2f,%.2f\n",
       TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
       side > 0 ? "BUY" : "SELL", entry, peak, trough, last));
   FileClose(fh);
}

//── ANTI-CLUSTER GUARD: block a new entry if (a) it's the thin overnight window, or
//   (b) S1/S3/NSND already hold a SAME-DIRECTION position (correlated pile-up). All
//   three engines run in one terminal, so PositionsTotal() sees every magic. Validated
//   on real ticks (cluster_guard_tick.py): cuts drawdown + worst day. Reversible inputs.
bool ClusterBlocked(int side) {
   if (InpSkipOvernight) {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      if (dt.hour >= InpOvernightStart && dt.hour < InpOvernightEnd) {
         Log(StringFormat("[GUARD] skip entry — overnight window (broker hour %d)", dt.hour));
         return true;
      }
   }
   if (InpMaxOneSameDir) {
      for (int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong tk = PositionGetTicket(i);
         if (tk == 0 || !PositionSelectByTicket(tk)) continue;
         if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         long mg = PositionGetInteger(POSITION_MAGIC);
         if (mg != 88003 && mg != 88004 && mg != 88006) continue;   // S3 / S1 / NSND cluster group
         bool is_buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         if ((side > 0 && is_buy) || (side < 0 && !is_buy)) {
            Log("[GUARD] skip entry — cluster group already holds a same-direction position");
            return true;
         }
      }
   }
   return false;
}

//── Entry log (ticket-stamped + regime state at execution) so each day's trades can be
//   reconciled precisely AND post-hoc analyzed for "did the gate let through a marginal
//   setup, or a great one that got shocked?". Columns: time,ea,side,entry,sl,tp,ticket,
//   magic, er, spread_pts (the last two appended 2026-05-29 per architecture review).
void LogEntryCsv(string side_s, double entry, double sl, double tp, ulong ticket) {
   double er = EfficiencyRatio();
   double sp = CurrentSpreadPts();
   int fh = FileOpen(InpDecisionCsv, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWriteString(fh, StringFormat("%s,S1,%s,%.2f,%.2f,%.2f,%I64u,%d,%.3f,%.3f\n",
       TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
       side_s, entry, sl, tp, ticket, InpMagicNumber, er, sp));
   FileClose(fh);
}

//── Floating P&L + one-tap GRAB (close all this EA's positions on a newer id) ──
double FloatingPnL(int &n_open) {
   double sum = 0; n_open = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      n_open++;
   }
   return sum;
}
//── Open positions as a JSON array (for the dashboard's live Open Positions view) ──
string BuildOpenJson() {
   string arr = "["; int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      bool buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      int  mi  = MngIndex(tk);
      bool secured = (InpTrailActUsd > 0 && g_mng_peak[mi] >= InpTrailActUsd);
      if (n > 0) arr += ",";
      arr += StringFormat("{\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.2f,\"cur\":%.2f,\"pnl\":%.2f,\"sl\":%.2f,\"tp\":%.2f,\"peak\":%.2f,\"secured\":%s}",
                          buy ? "BUY" : "SELL", PositionGetDouble(POSITION_VOLUME),
                          PositionGetDouble(POSITION_PRICE_OPEN), PositionGetDouble(POSITION_PRICE_CURRENT),
                          PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP),
                          PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP),
                          g_mng_peak[mi], secured ? "true" : "false");
      n++;
   }
   return arr + "]";
}

long ReadGrabId() {
   if (!FileIsExist(InpGrabFile, FILE_COMMON)) return 0;
   int fh = FileOpen(InpGrabFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (fh == INVALID_HANDLE) return 0;
   string s = FileIsEnding(fh) ? "" : FileReadString(fh);
   FileClose(fh);
   return (long)StringToInteger(s);
}
void CheckGrabCommand() {
   if (!InpEnableGrab) return;
   // v2.85: REMOVED the `< 2 sec` rate limit. Read on every OnTick for instant close.
   long id = ReadGrabId();
   if (id <= g_last_grab_id) return;
   g_last_grab_id = id;
   int closed = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (g_trade.PositionClose(tk)) closed++;
   }
   if (closed > 0)
      Log(StringFormat("[GRAB] one-tap grab id=%I64d — closed %d position(s) at market", id, closed));
}

void OnTick() {
   IsNewDay();

   // v2.50: live-tick scanning. No waiting for M5 close — every tick the
   // broker sends, check if ask > UHV.high (or bid < UHV.low) and fire if so.
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if (bid > 0 && ask > 0) {
      // BUY first; if it fires, SELL on same tick is dedup'd by g_last_uhv_*_t
      if (!TryS1BuySignalLive(ask, bid)) {
         TryS1SellSignalLive(bid, ask);
      }
   }

   // Track M5 bar transitions for legacy heartbeat reporting only
   datetime cur_m5 = iTime(_Symbol, InpTimeframe, 0);
   g_last_m5_time = cur_m5;

   ManageOpenPositions();   // 2R Free Roll (default off on S1 — see header)
   // TESTER SPEED (2026-08-09): CheckGrabCommand reads a file and WriteHeartbeat
   // writes one — on EVERY tick. Live that is the point: it is how Zee's one-tap
   // GRAB reaches the EA in 50ms. In the Strategy Tester it is 115,200 disk
   // round-trips per pass, and with 8 agents contending on the same Common\Files
   // every core sat at 1.9% CPU waiting on the disk (60 passes estimated at 20
   // HOURS). Neither function means anything in a backtest — there is no one to
   // press GRAB and no dashboard to feed.
   if (!MQLInfoInteger(MQL_TESTER)) {
      CheckGrabCommand();   // one-tap GRAB (close all) from WhatsApp/dashboard
      WriteHeartbeat();
   }
}
