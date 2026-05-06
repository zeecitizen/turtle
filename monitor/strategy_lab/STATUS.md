# Strategy Lab — Live Status

_Updated: 2026-04-28T18:17:59_

## Live performance
- Today realized: **$-389.65**
- Week realized: **$-318.80**
- Today main wins/losses: 20W / 21L
- Active config: fearIdeal=$25.0, trailTrigger=$8.0, trailDrop=$2.0, probeConfirm=$0.58

## Last lab cycle
- Variants tested: 10
- Top variant: **Hold longer: fearIdeal=120, washout=200**
- Top sim total: $-88.84
- vs baseline: $+14.43

## This iteration
- Action: **hold**
- Reasoning: best variant within tolerance — staying with current config

## How to inspect
- Variant ranking: `monitor/strategy_lab/RESULTS.md`
- Per-iteration log: `monitor/strategy_lab/iterations.jsonl`
- Runner log: `monitor/strategy_lab/lab_runner.log`