# Today's Bug Report — Why We're Losing

_2026-04-28 — diagnosis at 14:10 local_

## TL;DR

The strategy is hitting **70% win rate** but losing money because **average loss
($55+) is 2.3× average win ($24)**. The asymmetry is structural, baked into
the EA's exit rules — it caps losses at -$70 (`FEAR_IDEAL`) but caps wins at
peak−$2 (`trail`).

> EV per trade at original config (fearIdeal=70, trailTrigger=8):
> `0.70 × $24 + 0.30 × (-$72) = $16.8 - $21.6 = -$4.8 per trade`
>
> Even at 70% WR, every trade loses ~$5 on average. Run 30 trades/day → -$150/day.

## Today's evidence

- 36 closed trades, realized −$182.17
- Three trades closed at exactly **−$72.40** each (all from `FEAR_IDEAL` rule
  in `mt5/ShanoExitManager.mq5:767-770`)
- Wins ranged $4–$92, but average only +$24
- Two of the −$72 losses fired at the same timestamp 14:43:54 — burst
  trading pulled both 0.40 mains into the same adverse move

## What I changed (live)

1. `shano_config.json` → **fearIdeal: 70 → 35 → 25** (three-step tightening,
   final = V1 from the lab). EA hot-reloaded each within 5s; no reattach.
2. New EV math at fearIdeal=25:
   `0.70 × $24 + 0.30 × (-$25) = $16.8 - $7.5 = +$9.3 per trade`
   30 trades/day → +$280/day potential.

## What I built (for ongoing iteration)

- `monitor/strategy_lab/lab.py` — variant tester. Defines 10 variants (probe
  threshold, trail trigger, fear levels, burst, sizing). Simulates each
  against the EA's last 30 closed trades. Ranks by sim P&L delta vs baseline.
- `monitor/strategy_lab/intern_lab_runner.py` — daemon (pid 5544) that runs
  the lab every 30 min. Guards: only changes config when (a) delta > $100,
  (b) ≥1h since last change, (c) ≥8 trades since last change, (d) variant
  not previously tried. If the lab can't find a clearly-better variant, it
  asks Claude to **propose 3 new variants** and re-tests next cycle.
- `monitor/strategy_lab/RESULTS.md` — current variant ranking
- `monitor/strategy_lab/STATUS.md` — what the runner did this cycle and why
- `monitor/strategy_lab/iterations.jsonl` — append-only history of every cycle

## Open question — the recovery rate

The big philosophical fork:

**V1 (live now)**: cap losses tight at −$25. Safe, low-variance.
**V2 (held back by guards)**: widen to −$120 to let trades recover, on the
theory that 75% of "fearIdeal-bound" trades actually mean-revert if held.

The lab can't decide between them without **real** recovery-rate data —
right now we just have parameter assumptions. The right answer depends on
whether today's regime (apparently trending) is typical or atypical.

**Hypothesis**: V1 will win in trending regimes (today), V2 in mean-reverting
ones. A regime detector would let us switch dynamically. That's a bigger
build for another session.

## Diagnostic commands

```bash
# Manual lab run
python monitor/strategy_lab/lab.py

# Apply a variant to live config (hot-reloads in EA)
python monitor/strategy_lab/lab.py --apply V1_tightCut

# List variants
python monitor/strategy_lab/lab.py --list

# Single runner cycle
python monitor/strategy_lab/intern_lab_runner.py --once
```

## Files touched

- `c:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_config.json` → fearIdeal=25, fearWashout=200
- `monitor/strategy_lab/lab.py` (new)
- `monitor/strategy_lab/intern_lab_runner.py` (new)
- `monitor/strategy_lab/results.json`, `RESULTS.md`, `STATUS.md`, `BUG_REPORT.md` (new)
