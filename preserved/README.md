# preserved/ — the evidence, copied in so the result can be reproduced from this repo alone

Everything here normally lives OUTSIDE the repository, in MetaQuotes' folders. Without
these files the numbers in the top-level `README.md` cannot be checked by anyone.

## datasets/
The three symbols every test ran on. Import with `mt5/CustomSymbolImport.mq5`.

| file | symbol | bars | period | median volume |
|---|---|---|---|---|
| `tester_xau_real.csv` | XAUUSD_R3 | 2,409 | 2026-08-05 -> 08-09 | 518 (real OANDA traded volume) |
| `tester_xau_big.csv` | XAUUSD_BIG | 100,000 | 2026-02-12 -> 05-27 | 176 (broker tick counts) |
| `tester_xau_feb11_warm.csv` | XAUUSD_F11 | 2,879 | 2026-02-10 -> 02-11 | rebuilt from 448,294 real ticks |

**The volume columns are NOT the same measurement.** Every UHV rule is relative
(loudest bar in the window, breakout quieter than the UHV), which is why results
transfer between them — but no absolute volume threshold may be taken from one and
used on another.

## tester_settings/
MT5 reads its inputs from `MQL5/Profiles/Tester/<Expert>.set`, **not** from the `.mq5`
defaults. `ZeeUHV.set` is the exact configuration that produced 93.28%.

## live_evidence/
- `turtle_fills.csv` — every real fill the account has taken, including ZeeUHV's first
  live trades from 2026-08-11.
- `ZEE_FEB11_broker_statement.html` — **the origin of everything.** Zee's own hand-traded
  day on a live account: 69 trades, 65W/4L, 94.2%, +EUR 835.16, worst trade -EUR 1.60.
  This is the target the machine was built to reach.

## What is deliberately NOT here
- **Credentials of any kind** — API keys, the dashboard password, WhatsApp config, VAPID
  keys. Anything written into this repo is in its history forever, so secrets never
  enter it.
- Generated artefacts: `__pycache__`, `node_modules`, rotating logs.
- Very large media (the lesson audio, the brain database, the tick parquet). They exceed
  GitHub's per-file limit and none of them is needed to reproduce a single number here.
