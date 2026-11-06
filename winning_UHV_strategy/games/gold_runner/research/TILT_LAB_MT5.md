# Tilt lab: which direction signal wins at the game geometry? MT5 Strategy Tester (2026-11-04)

**Question.** The game's rounds are EUR/USD, TP 2 pips / SL 2 pips from the fill, ~0.1-pip spread. Which "tilt"
(direction signal) wins most often? **Every number below is an MT5 Strategy Tester result**: custom symbol `EURUSD_ZX`
(Zee's real EUR/USD ticks, Jan 2 - Nov 3 2026, 21,379,397 ticks / 312,024 M1 bars, "100% real ticks"), rig
`C:/mt5_rig_axi4`, model 4, **random execution delay**, 1.00 lot, every input pinned. Python only tabulated the tester's
own deal lists.

## Answer: none beats random, and nothing gets near break-even

Selection rule, fixed before Jul-Nov was read: within each family, pick the variant with the best Jan-Jun WR minus
random. Judge it on Jul-Nov only. Random control (same EA, InpTilt 5, every 15 min, alternating sides) = **46.9%** full,
47.1% Jan-Jun, **46.7% Jul-Nov**. Break-even WR = avg loss / (avg win + avg loss) is ~50.1-50.6% for every row.

**Ranked on Jul-Nov (out-of-sample) WR**

| rank | tilt (variant picked on Jan-Jun) | Jul-Nov trades | Jul-Nov WR | break-even | WR - random | p vs random | Jan-Jun WR | net pips Jul-Nov |
|---|---|---|---|---|---|---|---|---|
| 1= | 4. Teacher BUY: DI+ < 10 and AO < 0 | 2,625 | **47.8%** | 50.7% | +1.1 | 0.26 | 47.2% | -326 |
| 1= | 4m. Mirror SELL: DI- < 10 and AO > 0 (reported separately) | 2,520 | **47.8%** | 50.4% | +1.1 | 0.27 | 48.3% | -274 |
| 3 | 3. RSI top/bottom retest, EMA 9 line | 1,519 | 46.8% | 50.3% | +0.1 | 0.93 | 44.7% | -219 |
| 4 | 5. Random control | 6,337 | 46.7% | 50.4% | 0 | - | 47.1% | -976 |
| 5 | 0. Game HA tilt, threshold 0.8 | 3,531 | 46.5% | 50.3% | -0.2 | 0.84 | 46.1% | -554 |
| 6 | 1. VSISA setup (M5, engine defaults) | 137 | 44.5% | 52.5% | -2.1 | 0.68 | 47.2% | -48 |
| - | 2. SPRING | not testable in MT5 (see below) | | | | | | |

- **The best tilt is the teacher's DMI/AO rule, at 47.8%.** That is +1.1 points over random, p ~0.26, so not
  distinguishable from random. It is still 3 points below break-even and loses ~0.12 pip per trade. Full period: BUY
  47.4% (n 6,731), SELL mirror 48.1% (n 6,476, p 0.06 vs random). Both halves sit at 47-48%, so it is stable, but the
  gap is small.
- **The game's current HA tilt is slightly worse than random in Jan-Jun at every threshold** (-1.0 to -1.3 points, p
  0.05 to <0.001 at 0.4/0.6). Jul-Nov: -0.2 to -1.0. Following the tilt gives no edge. Fading it would add about 1
  point, which still leaves it far below break-even.
- **RSI retest:** all four variants were below random in Jan-Jun (-2.4 to -3.0). The pick, EMA 9, is at random in
  Jul-Nov.
- **VSISA** on EUR M5 fires 370 times in ten months; it does not beat random. This matches the earlier finding that
  VSISA's edge was gold M5 only. M1: 46.5%, at random.
- **At TP 2 / SL 2 with a 0.1-pip spread, every entry starts ~3 points of WR behind break-even.** No signal tested here
  closes that gap. For the game, any tilt is a cosmetic hint, not an edge.

## Every run (Jan 2 - Nov 3 2026)

| run | full n | full WR | BE | net pips | Jan-Jun n / WR / dWR | Jul-Nov n / WR / dWR | fires | skipped (busy/cool) | re-anchor fail |
|---|---|---|---|---|---|---|---|---|---|
| rnd (InpTilt 5) | 16,283 | 46.9% | 50.2% | -2,191 | 9,946 / 47.1 / 0 | 6,337 / 46.7 / 0 | 16,283 | 0 | 247 (1.5%) |
| ha04 | 28,531 | 45.8% | 50.1% | -5,130 | 19,025 / 45.8 / -1.3 | 9,506 / 45.7 / -1.0 | 28,531 | 32,251 | 566 |
| ha06 | 20,398 | 46.0% | 50.1% | -3,423 | 14,234 / 46.0 / -1.1 | 6,164 / 46.1 / -0.5 | 20,398 | 13,614 | 575 |
| **ha08** | 13,134 | 46.2% | 50.1% | -2,105 | 9,603 / 46.1 / **-1.0** | 3,531 / 46.5 / -0.2 | 13,134 | 6,240 | 541 |
| **vs5** (VSISA M5) | 370 | 46.2% | 51.5% | -83 | 233 / 47.2 / **+0.1** | 137 / 44.5 / -2.1 | 370 | 8 | 8 |
| vs1 (VSISA M1) | 2,920 | 46.5% | 50.5% | -483 | 1,726 / 46.4 / -0.7 | 1,194 / 46.6 / -0.1 | 2,920 | 348 | 18 |
| rsik34 (Kijun 34, body 50%) | 2,787 | 44.6% | 50.2% | -650 | 1,627 / 44.1 / -3.0 | 1,160 / 45.3 / -1.4 | 2,787 | 83 | 23 |
| rsik34b30 (body 30%) | 2,844 | 45.0% | 50.3% | -628 | 1,668 / 44.4 / -2.7 | 1,176 / 45.8 / -0.8 | 2,844 | 97 | 30 |
| rsie21 (EMA 21 line) | 3,210 | 44.5% | 50.0% | -742 | 1,885 / 44.0 / -3.0 | 1,325 / 45.1 / -1.5 | 3,210 | 97 | 27 |
| **rsie9** (EMA 9 line) | 3,685 | 45.6% | 50.3% | -718 | 2,166 / 44.7 / **-2.4** | 1,519 / 46.8 / +0.1 | 3,685 | 91 | 34 |
| **dmibuy** | 6,731 | 47.4% | 50.5% | -875 | 4,106 / 47.2 / +0.1 | 2,625 / 47.8 / +1.1 | 6,731 | 2,256 | 60 |
| **dmisell** | 6,476 | 48.1% | 50.4% | -616 | 3,956 / 48.3 / +1.2 | 2,520 / 47.8 / +1.1 | 6,476 | 2,173 | 79 |

Bold = the family's Jan-Jun pick. dWR = WR minus random for the same half. p = two-sided binomial (normal approx)
against random's WR for that half. About 36 cells were tested, so a single p ~0.03 is expected by chance. Fires =
trades opened. Skipped = signals that arrived while a position was open or inside the 60 s cooldown.

## How each tilt was built (`mt5/TiltLab_EUR.mq5`, new, lab only)

Common to all signals:
- market order, TP/SL 0.00020 from the quote, re-anchored to the actual fill price right after the fill;
- one position at a time, 60 s cooldown after each close, magic 88990;
- no commission (the custom symbol books none, the same as the game).

1-2% of re-anchors failed (price had already moved past the new level). Those trades kept quote-anchored stops.

- **0 HA tilt.** A port of `games/gold_runner/engine.py` `ha_delta` (lines 156-167: 20 M1 bars including the forming
  one) and `_update_market` (lines 1449-1458):
  - raw = clamp(HA delta / 0.00024, -1, 1); EMA with tau 3 s on tick time (dt capped at 5 s);
  - fires when |EMA| crosses up through the threshold (0.4 / 0.6 / 0.8), in the tilt's direction.
- **1 VSISA.** `mt5/TriVsisa.mqh` (the Trinity copy of VSISA v1.30), **included unchanged**:
  - the host calls the engine's own law functions once per closed `V_InpTF` bar, in `V_OnTick`'s order:
    `V_Detect(+1)`, `V_Detect(-1)`, `V_DetectFade(+1)`, `V_DetectFade(-1)` (TriVsisa.mqh lines 887-1180, 1183-1265;
    order from lines 1954-1960);
  - detection defaults are identical to `mt5/VSISA.mq5`, checked input by input: BigPct 0.70, BigAvg 1.10, LowVolPct
    1.00, BodyFrac 0.35, FakeBreak on / SweepLook 30, FadeMode 1 / FadeLook 5 / FadePct 0.65 / FadeBigPct 0.80, TrendTF
    30 camel (pivot 2), SwingPivot 3, SetupMin/Max 2/10, ConfirmMode 0;
  - law statement: `WINNING_STRATEGY_VSISA.md`.

  **Not included:**
  - `V_Fire`'s geometry refusals (max SL, target too near), because the geometry is the game's;
  - the ML meta / regime / exhaustion vetoes (trained on gold; pinned off);
  - VSISA's own session, cooldown and MaxOpen gating (replaced by the lab's one position plus 60 s);
  - volume falls back to the tester's per-bar tick count (no OANDA file; `V_InpOandaVolume` 0).
- **2 SPRING: not testable, and not substituted.**
  - It is in `mt5/TickSpeedGauge.mq5`; `TICK_SPEED.md` documents it.
  - Its input is **order-book imbalance**: OBI = (best-bid volume - best-ask volume) / sum (line 615).
  - It loads while OBI sits beyond ±0.25 and fires on the cross back (lines 811-830).
  - The EA itself says SPRING needs the book (lines 452, 635). The Strategy Tester has no market depth, and Zee's tick
    export carries no book volumes, so the trigger cannot be replayed.
  - The lab EA refuses to start with InpTilt 2 rather than fake it.
  - (`engine.py vsa_read` has a different, bar-based "spring". It is not the gauge's, and it was not tested.)
- **3 RSI top/bottom retest.** RSI 14 on M1 closes:
  - an extreme at >= 70 (bear) or <= 30 (bull), tracking the first peak;
  - then a cool-back past 60 / 40;
  - then a second RSI pivot (strength 2 = higher/lower than 2 bars on each side, so it is confirmed only once RSI has
    turned), below the first peak (bear) / above the first bottom (bull) and still beyond the cooling level; this arms
    the setup for 30 bars, and a new extreme beyond peak 1 resets it;
  - then a candle closing against the line with >= 50% (or 30%) of its body beyond the confirmation line: Kijun 34 =
    (34-bar HH + LL)/2, or EMA 21 / EMA 9;
  - entry at the NEXT candle's open (the first tick of the new bar).

  This is my port from the brief's description; the original Pine source was not in the repo.
- **4 Teacher.** `iADX(14)` +DI / -DI and `iAO` on the last closed M1 bar:
  - BUY when DI+ < 10 and AO < 0;
  - mirror SELL when DI- < 10 and AO > 0, run separately.

  It fires on the bar where the condition becomes true (rising edge), not on every bar while it holds. About 25% of
  edges arrived while a position was open and were skipped.
- **5 Random.** Every 15 minutes when flat, alternating sides. It reproduces the earlier NullEntry control (46.5% there,
  46.9% here; the small difference comes from re-anchoring to the fill and the cooldown).

## Caveats

- One symbol, one broker feed, ten months. No commission. A real account's round trip would push break-even higher.
- Thresholds were swept on Jan-Jun only. Jul-Nov is the verdict, but it is a single out-of-sample period.
- The RSI script is a reconstruction from the brief, not the author's Pine code. The DMI rule uses an edge trigger (my
  choice; "when" is ambiguous).
- Receipts: `games/gold_runner/research/tilt_lab_mt5/runs/*.json` (the tester's deal lists plus log lines),
  `tilt_lab_mt5/summary.json`, runner `tilt_lab_mt5/run.py`, tabulator `tilt_lab_mt5/tab.py`. The HTML reports were
  deleted after parsing, to save disk space.
