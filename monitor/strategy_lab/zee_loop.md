# Optimise -> evaluate loop for Saad_strategy_15min (started 2026-10-12)

Rules of the loop (from the advisor review + Zee):
- data gate: "real ticks discarded" must be ~0 before any screening
- control = v1.09 (git 7b0840d) as mt5/_control_Saad15_v109.mq5, on the same clean data
- screen with ExecutionMode=200 (fixed 200 ms, deterministic, ~ PXBT live fill latency)
- tune on IS = 2026.01.01-2026.07.01; promote only if it also beats the control on OOS = 2026.07.01-2026.10.08
- finalists: 2 random-delay runs on the full period
- report per batch: WR, $/trade, $/day, worst day, largest single loss, longest losing streak, $20/$100 feasibility

Results log: zee_loop.jsonl ; ranking: python saad_rank.py zee_loop.jsonl
