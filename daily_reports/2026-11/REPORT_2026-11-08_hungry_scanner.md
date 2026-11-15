# 5–8 November 2026 — Turtle TV UHV: Detector Lab, 🔭 one-value scanner, 🍖 "Scan for maximizing trades"; Golden Gravity frontend repo

Zee (8 Nov): *"a greedy, hungry for trade scanner which tries to include more and more trades with minimal loss of winrate ...
i want you to put all the intelligence you have into building this one scanner which trades more per day at same winrate"*

**Every number below is a tester estimate** (Python engine on PrimeXBT EUR/USD ticks, `sim.data("year1")`, 209 days with data).
Python generates the hypothesis; MT5 / live fills promote it. Nothing here is promoted. Nothing was committed (`monitor/TurtleTVUHV/`
is still untracked).

## 1. 🔧 Detector Lab (7 Nov) — `monitor/TurtleTVUHV/detlab.py`, `static/detlab.js`, `/api/detlab*`
Built from Zee's 19 labelled losses on setting `2026-11-07 12-09-37` (3,076 trades / 19 losses / 99.38%): one page per detector —
📦 Ranging (7 rules), 🧱 Support/resistance (5), 🔀 Trend shift / against the trend (11), 🌊 Choppy (6). Each page says how the engine
detects it today, draws every labelled loss with the detector's diagram, lets Zee label YES/NO, and exposes the rules' engine inputs as
sliders — a tuned detector IS a setting (💾 Save → `settings/saved/`). Labels in `settings/detector_labels.json`.
- At the setting's own values every detector is silent on its losses by construction; the lab finds the stricter values that would
  have caught them. The fit searches STRICTER values only (a looser rule lets in trades the estimate never sees; "quiet box OFF"
  looked good in the estimate and lost $2,926 in the full engine) and runs the top rows through the full engine.
- Reviewers caught two gating bugs before shipping: the zone-box rule silently flipped the risk manager to mode 4 (−$16k on the
  setting), and secure-zone trades were being judged by skip-type rules; both fixed through one `final_inputs` path.
- First fits (full engine): Ranging BoxAtr 1 → 3,022 / 18 / 99.40%; S/R → 2,835 / 13 / 99.54%; Trend V2Against 1 + V2Back 3 →
  2,887 / 17 / 99.41%; Choppy MaxFlips 0.56/30 + MinVolRel 0.6 → 2,642 / 13 / 99.51%.

## 2. 🔭 Scan for tuned settings (7–8 Nov)
One input at a time, every grid value, a FULL engine run each on the 4-worker pool; ranked win rate → fewer losses → more trades; green
rows raise the win rate and carry Apply. Per detector (ranging 52 moves, S/R 49, trend 62, choppy 36) or **all four** (189). Choppy: 36
runs in 21.6 s. **Load** on a saved setting makes the lab and its scans follow that setting. Zee then saved
**`2026-11-07 12-09-37 + New Detector 100 percent at 976`**: 976 trades, 0 losses, 100.00% (ranging scan on 12-09-37; BUY box 55–60%
stands aside). Over the 209 days with data that is **4.67 trades/day** (the earlier "5.3/day" used 185 trading days).

## 3. 🍖 Scan for maximizing trades (8 Nov) — `monitor/TurtleTVUHV/hungry.py`
**Design.** Every lever that gates trade COUNT, each with its "let more in" direction: sessions (NoClose, Friday cut, hours, news,
holidays), spread caps, Mode/Laws/ER, the risk manager, every loss filter loosened step by step along its grid or off, Saad switches,
stood-aside range boxes, pre-break depth, and (checkbox, slow) the UHV detection settings themselves. Geometry and fill inputs are frozen.
Greedy loop, full engine, no estimates: each round runs every candidate (74 on the 976 setting), accepts only rows within `tol`
win-rate points of the START (or loss-free gains), picks one (`most` trades / `free` = fewest new losses first / `cheapest` = trades per
win-rate point spent / `auto` = most at tol 0, cheapest above), applies it, repeats. Output: the ceiling (setups that exist and what blocks
them), the path with both halves and the win rate of the trades each step ADDED (true marginal, by entry-time diff), every evaluated
point, the Pareto frontier, per-round tables; Apply / 💾 Save on any step, row or dot; ⏹ Stop keeps what was found; a reload re-attaches
to the running job. Endpoints `POST /api/detlab/hungry`, `/hungry_stop`, `GET /api/detlab/hungry?job=`; `cnt["busy"]` added to the engine.

**Run on the live 8774 instance, tol 0, detection off** — 179 engine runs, 67 s, 5 rounds:
| step | change | trades | /day | losses | WR | Mar–Jun / Jul–Nov | added trades' WR | net |
|---|---|---|---|---|---|---|---|---|
| 0 | the setting | 976 | 4.67 | 0 | 100.00 | 100 / 100 | – | +$1,534 |
| 1 | Friday cut-off (NY hour) 10 → 11 | 989 | 4.73 | 0 | 100.00 | 100 / 100 | 100 | +$1,563 |
| 2 | harvest wins per trend 2 → 3 | 995 | 4.76 | 0 | 100.00 | 100 / 100 | 100 | +$1,571 |
| 3 | max spread at the breakout tick 0.7 → 1.5 | 1,000 | 4.78 | 0 | 100.00 | 100 / 100 | 100 | +$1,578 |
| 4 | New York rollover block → off | 1,002 | 4.79 | 0 | 100.00 | 100 / 100 | 100 | +$1,580 |
Stopped: no lever adds trades within the tolerance. +26 trades (+0.12/day) at 100%, 0 losses.

**Run with tol 0.25, pick auto (= cheapest)** — 141 runs, 52 s: 976 → 1,181 (wick fake-break candles 3 → 1; 1 loss, 99.92%,
halves 99.79 / 100) → 1,373 (wide-swing ATR span 6.565 → 8; 2 losses, 99.85%) → 1,408 (BUY box 55–60% trade; 3 losses, 99.79%,
added trades' WR 97.2%, net falls $1,651 → $1,470). Stopped at the tolerance floor.

**Frontier (what more tolerance buys):** 1,500 @ 99.73% (4 losses) · 1,889 @ 99.52% (9) · 2,242 @ 99.24% (17, net −$553) ·
2,585 @ 99.07% (24, −$1,630) · 3,373 @ 98.67% (risk manager 0 → 1, 45 losses, −$5,253) · 8,184 @ 98.44% (risk manager 0 → 3, 128
losses, −$18,089). **Net turns negative past ~2,000 trades even above 99% win rate** — the geometry's loss:win ratio makes those trades
expensive; win rate alone hides it.

**Ceiling:** 25,694 setups / 209 days; the setting takes 976. Blocked: loss filters 22,218 · sessions/setup rules/range boxes 1,976 ·
spread 409 · busy (one trade at a time) 92 · 23 stood-aside ghosts · unexplained 0.

**Review (6 agents, 26 findings, 25 fixed):** 21-char range-box strings were compared as floats, so flipping boxes 17–20 was invisible
(moves dropped, saved files wrong) — strings over 15 chars now compare as text in detlab/server/app.js/hungry; `save_setting`'s
`changed` now diffs against the EA defaults like `/api/save` (an MT5 run no longer attaches to the wrong hungry save); skip-type levers
suppressed under risk manager 4 as well as 2; Saad master-switch lever labelled when it also drops break-even/lock/cool-down; spread
levers offered whenever entry mode 1 (TTD on or off); band values validated (400); page: setting picker locked during a run, error rows
shown, one shared result across detector cards, zoom inset on the frontier chart, rounds + pick selectors, detection OFF by default,
stats card shows the applied step's full-engine numbers. **Open (cosmetic):** a save from the 🍖 table records `source.det` = the
current detector card. **Contract deviations the engine forced:** risk manager 1 → 0 and 3 → 0 are TIGHTER (levers run 0 → 1, 3);
Struct 1 → 2 → 0; CamStrong 0 is the strict value; trades/day uses the 209 days with data.

**Live fix 11:40 AM PKT:** Zee's first 🍖 save, `2026-11-07 12-09-37 + 1221at 99.84` (1,222 trades / 2 losses / 99.84% /
5.85 per day, tester), hit "server error" on the Detector Lab: `detlab._setting` used `with_suffix(".json")`, which replaced the
name's own ".84" and looked for `… 99.json`. Now the extension is appended, never replaced; all four detector pages answer 200 for it.

**Caveats:** in-sample — the 976 setting was carved on the same 209 days the scanner now loosens; the Jul–Nov half is the only
near-out-of-sample column and the detector itself was fitted on all of it. Promotion = MT5 Strategy Tester / live fills only.

## 4. Exit Lab scanner (6 Nov)
Suggestion group "loss fixes (12-09-37)": BuyRes 2, WickFake 1, MaxFlips60 0.5 and their combinations (labels "fix: …").

## 5. Golden Gravity frontend (8 Nov)
All game graphics (code/assets) moved to `games/gold_runner/frontend/`, served as-is by the game server (only `static/admin.html` stays
in static/). Pushed to the **private** repo `zeecitizen/golden-gravity-frontend` (nested clone; `pull_frontend.bat` = `git pull --ff-only`).
Designer README in the repo (`serve.bat` → `http://127.0.0.1:8800/?fixture=open_profit`; `net.js` and `fixtures/` off limits).
**Zee must invite the designer as a collaborator.** 105 game tests pass.

## Open items
1. MT5 promotion of any detector / hungry setting before it touches money.
2. Designer invite on the private repo.
3. Memory `current_context.md` is from Aug 2026 (BasedOnLaws era) — stale; the MEMORY.md "Read-first" rows are the current state.
