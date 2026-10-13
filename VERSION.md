# VERSION.md — every EA and every version, one line each

The quick index. Newest first inside each EA. The full story, receipts and reasons for each version
are in `VERSION_HISTORY.md`; the test results are in `report.md`.

**Rule:** every time an EA version ships, add its row here **and** its entry in `VERSION_HISTORY.md`,
in the same commit.

Status words: **LIVE** = attached on a real or demo account · **READY** = compiled in the terminal,
safe to attach · **BUILT** = exists, not attached · **TEST** = test copy, never attach ·
**REFUSED** = failed testing, do not attach · **RETIRED** = replaced.

---

## Which EA is which (latest version of each)

| EA | File (`mt5/`) | Magic | Latest | Chart | Status |
|---|---|---|---|---|---|
| **Saad 15-min** | `Saad_strategy_15min.mq5` | 88302 | **v1.18** (2026-10-13) | XAUUSD M15 | **LIVE** on Axi (v1.17 attached; v1.18 = same trades + named comments) |
| Saad 15-min + pyramiding | `Saad_strategy_15min_pyramiding_max_3.mq5` | 88330 | v1.01 (2026-10-13) | XAUUSD M15 | READY, demo first (bigger risk) |
| Saad 5-min | `Saad_strategy_5min.mq5` | 88320 | v1.00 (2026-10-13) | XAUUSD M5 | BUILT, not profitable, demo only |
| Small-account tiers | `EA_20USD … EA_200USD.mq5` | 88310–88314 | v1.14 base (2026-10-12) | XAUUSD M15 | READY ($80+ only) |
| Saad (M5 original) | `Saad_strategy.mq5` | 88301 | v4.03 (2026-10-11) | XAUUSD M5 | RETIRED by the 15-min |
| VSISA | `VSISA.mq5` | 88201 | v1.28 (2026-10-10) | XAUUSD M5 | BUILT |
| VSISA_Pullbacks | `VSISA_Pullbacks.mq5` | 88202 | v1.00 (2026-09-17) | XAUUSD | BUILT |
| ZeeUHV_Diamond | `ZeeUHV_Diamond.mq5` | 88154 | v1.27 (2026-09-29) | XAUUSD M1 | BUILT |
| BasedOnLaws | `BasedOnLaws.mq5` | 88184 | v1.44 (file) / v1.43 ledger (2026-08-28) | XAUUSD M1 | BUILT |
| ZeeUHV (main, old) | `ZeeUHV.mq5` | 88094 | v1.62 (2026-08-23) | XAUUSD M1 | RETIRED |
| ZeeUHV_Loud_Breakout | `ZeeUHV_Loud_Breakout.mq5` | 88104 | v1.2 (2026-08) | XAUUSD M1 | RETIRED |
| ZeeUHV_M3 "Shop B" | `ZeeUHV_M3.mq5` | 88134 | v1.10 (2026-08-20) | XAUUSD M3 | RETIRED |
| TurtleUHV | `TurtleUHV.mq5` | 88601 | v1.00 (2026-10-09) | XAUUSD | REFUSED (not promoted) |
| ZeeBreakout | `ZeeBreakout.mq5` | 88501 | v1.00 (2026-10-09) | XAUUSD | REFUSED (not promoted) |
| RiskGuardButtons | `RiskGuardButtons.mq5` | 77001 | v1.14 (2026-10-07) | any | LIVE tool (risk buttons) |
| TickSpeedGauge | `TickSpeedGauge.mq5` | — | v1.53 (2026-10-07) | any | research panel, never trades |
| TurtleTradeLogger | `TurtleTradeLogger.mq5` | — | v1.06 (2026-09-25) | any | LIVE logger |
| ShanoExitManager | `ShanoExitManager.mq5` | 77777 | v2.00 | XAUUSD | Shano's account |
| ShanoTickLogger | `ShanoTickLogger.mq5` | — | v1.10 | XAUUSD | logger |

---

## Saad_strategy_15min (magic 88302, XAUUSD M15)

| Version | Date | What changed | Result / note |
|---|---|---|---|
| **v1.18** | 2026-10-13 | Trade comments name the EA: `Saad15 v1.18 BUY` / `SELL` (Zee). No trading change | +$202,221.80, identical to v1.17 |
| v1.17 | 2026-10-13 | Default lot 0.10 → **1.00** (Zee) | +$202,222 at 1 lot, Jan 6 – Oct 8, real ticks |
| v1.16 | 2026-10-12 | **Zee's rule:** close 50% at TP1 + breakeven on the rest (`InpPartialPct 0.5`, `InpTp1Be`) | +$202,222; win rate per deal 48% → 61%; worst day −$3,806 |
| v1.15 | 2026-10-12 | H1/H4 trend filter switch `InpHtfMin`, **off** | tested: costs most of the profit |
| v1.14 | 2026-10-12 | Min candle 0.55 ATR, marubozu body 0.53, choppy filter 0.11 | +$206,705, PF 1.62, DD 5.5%, 0 losing months |
| v1.12–v1.13 | 2026-10-12 | Real-tick test symbol; v1.11 bug fixed; **SL 35**, hammer 2.5, pin wick 0.45; stop-change back-off, quiet tester logs, test switches (all off) | v1.13 Jul–Oct +$48.2k vs v1.09 +$38.0k |
| v1.10–v1.11 | 2026-10-12 | Trade log (Experts tab + CSV); long TP1 = next resistance (later found to cost −$70k, turned off in v1.12) | |
| v1.09 | 2026-10-12 | Marubozu body 0.70 → 0.50 (Zee) | |
| v1.08 | 2026-10-12 | Directional pin bars, tested, left **off** | |
| v1.07 | 2026-10-12 | $2 trails on both sides (Zee); wider trails tested and rejected | |
| v1.06 | 2026-10-12 | TP1 → $3 trail, TP2 → TP3 ladder, longs and shorts | |
| v1.05 | 2026-10-12 | 30-minute no-new-trades rule removed (Zee: cost about $11k at 1 lot) | |
| v1.04 | 2026-10-12 | Zee's long exit: touch the 50 EMA → trail $3 + TP at the last resistance | |
| v1.02–v1.03 | 2026-10-12 | CTC breakeven at 75% of the TP; day-close rules; clearer labels | |
| v1.01 | 2026-10-12 | Chart labels for the visual tester | |
| v1.00 | 2026-10-11 | The 15-minute variant of Saad_strategy v4.03 | |

## Saad_strategy_15min_pyramiding_max_3 (magic 88330, XAUUSD M15)

| Version | Date | What changed | Result / note |
|---|---|---|---|
| v1.01 | 2026-10-13 | Built on v1.18; comments name the EA: `Saad15-PYR3 v1.01 BUY` / `SELL`, add-ons `… ADD` (Zee) | +$479,814.52, identical to v1.00 |
| v1.00 | 2026-10-13 | v1.17 + scale-in pyramid: add 0.75× after each 0.25× ATR move, up to 5 positions (about 3.05 lots), no breakeven lock (Zee's pick) | +$479,815 (random delay +$468,075), max DD $41.8k, worst day −$12,338 |

## Saad_strategy_5min (magic 88320, XAUUSD M5)

| Version | Date | What changed | Result / note |
|---|---|---|---|
| v1.00 | 2026-10-13 | v1.17 rescaled for M5 (risk cap $9, stop 20 pips, choppy window 48) | NOT profitable: best Jan–Jun +$16k, Jul–Oct −$28k. Demo only |

## EA_20USD · EA_40USD · EA_80USD · EA_100USD · EA_200USD (magics 88310–88314, XAUUSD M15)

| Version | Date | What changed | Result / note |
|---|---|---|---|
| v1.14 base | 2026-10-12 | Rebuilt on Saad_strategy_15min v1.14 at a fixed 0.01 lot, 1:1000 | $80, $100 and $200 survived all 9 monthly starts; $20 and $40 did not |
| v1.13 base | 2026-10-12 | First small-account tiers (v1.13 at 0.01 lot) | |

## Saad_strategy (magic 88301, XAUUSD M5)

| Version | Date | What changed | Result / note |
|---|---|---|---|
| v4.03 | 2026-10-11 | More than one trade at a time: tested, left **off** | |
| v4.02 | 2026-10-11 | **Shipped to Axi:** the TradingView indicator, ported and tuned (break +2 pips, SL 30, ATR ×2 trail) | |
| v3.20 | 2026-10-11 | Shipped to Axi: 25-pip stop | |
| v2.00 | 2026-10-11 | Built from `RULES_EMA_SAAD.md`, not shipped | |

## VSISA (magic 88201) · VSISA_Pullbacks (magic 88202)

| EA / Version | Date | What changed |
|---|---|---|
| VSISA v1.28 | 2026-10-10 | The looser fade ships: 288 trades instead of 163 |
| VSISA v1.27 | 2026-10-09 | Other markets, lot-step fix, the more-trades test |
| VSISA v1.26 | 2026-10-09 | Equity-proportional compounding |
| VSISA v1.25 | 2026-10-09 | Optional risk sizing + the Axi receipt |
| VSISA v1.24 | 2026-09-17 | The loud gate was too strict (loosened) |
| VSISA v1.21–v1.23 | 2026-09-17 | Shipped: LAW 14, the fade |
| VSISA v1.20 | 2026-09-17 | Shipped: the night's four answers |
| VSISA v1.19 | 2026-09-16 | Shipped: camel humps on M30 |
| VSISA v1.18 | 2026-09-16 | The camel humps: Zee's own trend reading |
| VSISA v1.17 | 2026-09-16 | Shipped: the ratchet on at 2.0R, 0.28 lots |
| VSISA v1.16 | 2026-09-16 | The ratchet (Zee's ladder) |
| VSISA v1.15 | 2026-09-16 | Shipped: 0.15 lots |
| VSISA v1.14 | 2026-09-16 | Shipped: the fake break on |
| VSISA v1.13 | 2026-09-16 | Shipped: `InpMaxOpen` 10 → 2 |
| VSISA v1.12 | 2026-09-16 | Can the drawdown at 0.20 lots be cut? No |
| VSISA v1.11 | 2026-09-16 | Sizing by reaction spread |
| VSISA v1.10 | 2026-09-16 | Gapped campaign, wide reaction, entering on the test |
| VSISA v1.08–v1.09 | 2026-09-16 | LAW 10, the retracement re-entry |
| VSISA v1.07 | 2026-09-15 | No-supply test as an addition, not a gate |
| VSISA v1.06 | 2026-09-15 | Diagrams 10–12: the no-supply test |
| VSISA v1.05 | 2026-09-15 | Shipped: target runs to 1:5 |
| VSISA v1.04 | 2026-09-15 | Diagram 9: effort per unit of result |
| VSISA v1.03 | 2026-09-15 | Diagrams 3–8 encoded and measured |
| VSISA v1.02 | 2026-09-15 | Target decoupled from the stop |
| VSISA v1.01 | 2026-09-15 | Reaction-volume floor, built and left off |
| VSISA v1.00 | 2026-09-09 | New EA: Sajid Ahmed's volume method |
| VSISA_Pullbacks v1.00 | 2026-09-17 | Second EA, built for frequency |

## ZeeUHV_Diamond (magic 88154, XAUUSD M1)

| Version | Date | What changed |
|---|---|---|
| v1.27 | 2026-09-29 | Shipped: Zee's camel hump, read strictly |
| v1.19–v1.23 | 2026-09-29 | The detection audit |
| v1.17 | 2026-09-09 | Hump budget 3 → 2 |
| v1.16 | 2026-09-09 | The hump budget |
| v1.15 | 2026-09-06 | His eye or no trade |
| v1.14 | 2026-09-01 | His line 42, obeyed |
| v1.12 | 2026-09-01 | The sweep required |
| v1.10 | 2026-08-20 | Built: the untouched streak-era ancestor (commit 718b68a) |
| — | 2026-09-07 | LAW 45 as a gate: tested, not shipped |

## BasedOnLaws (magic 88184, XAUUSD M1)

| Version | Date | What changed |
|---|---|---|
| v1.43 (file says v1.44) | 2026-08-28 | His page restored, on receipts |
| v1.35 | 2026-08-23/24 | Built from Zee's own eye on his marked setups; not attached |
| v1.00 | 2026-08-23 | LAWS.md mechanized whole, every provision a hard gate |

## ZeeUHV (main, magic 88094, XAUUSD M1) and its siblings

| EA / Version | Date | What changed |
|---|---|---|
| ZeeUHV v1.62 | 2026-08 | Latest in the file |
| ZeeUHV v1.61 | 2026-08-23 | The teacher's exits on our entry (all off) |
| ZeeUHV v1.60 | 2026-08-22 | LAW 13, the momentum breakout (off) |
| ZeeUHV v1.58–v1.59 | 2026-08-20/21 | The volume source (`InpVolSource`, OANDA volume) |
| ZeeUHV v1.56–v1.57 | 2026-08-20 | Sticky trend (refused) |
| ZeeUHV v1.53–v1.55 | 2026-08-20 | Pulse-switched target; conviction geometry (refused) |
| **ZeeUHV v1.52** | 2026-08-20 | **Live:** the hour dimmer (hours 02/03/09/10 quarter-sized) |
| ZeeUHV v1.50–v1.51 | 2026-08-20 | Wick-diamond switch; hour dimmer (off) |
| **ZeeUHV v1.49** | 2026-08-19 | **Live:** the diamond season machine |
| ZeeUHV v1.46–v1.48 | 2026-08-19 | Diamond mode, crash-control organs (failed), fast-red dial |
| **ZeeUHV v1.45** | 2026-08-19 | **Live:** the self-aware switch (pulse of the last 20 tickets) |
| ZeeUHV v1.35–v1.44 | 2026-08-18/19 | Census, probe, HTF gate, LAW 11/12, exhaustion tags, Feb-11 exit lab |
| **ZeeUHV v1.34** | 2026-08-18 | **Live:** rank 6 UHV candidates |
| **ZeeUHV v1.30** | 2026-08-18 | **Live:** hold 5 → 3 min |
| **ZeeUHV v1.29** | 2026-08-17 | **Live:** LAW 10c, loud breakout opens ¼ tickets |
| **ZeeUHV v1.26** | 2026-08-17 | **Live:** LAW 9, impulse origin |
| ZeeUHV ≤ v1.23 | 2026-08-10..16 | Diamond era (see `05_AUGUST_DIAMONDS_FINDINGS.md`) |
| ZeeUHV_Loud_Breakout v1.2 | 2026-08 | Counter-experiment: fires on loud breakouts |
| ZeeUHV_M3 v1.10 | 2026-08-20 | The pulse ported to M3 |
| ZeeFade v1.00 (88164) | 2026-08 | Refused |
| ZeeScalp v1.00 (88174) | 2026-08-23 | Refused as standalone |
| ZeeUHV_Bull v1.00 (88144) | 2026-08 | Refused |
| ZeeSimple v1.20 (88111) · ZeeUHV_R1 v1.00 (88121) | 2026-08-18 | Retired |

## Tools and other EAs

| EA / Version | Date | What changed |
|---|---|---|
| TurtleUHV v1.00 (88601) · ZeeBreakout v1.00 (88501) | 2026-10-09 | MT5 port of the TradingView indicator + live bridge: not promoted |
| RandomTouch v1.00 (77101) · SignalReplay v1.00 (77201) | 2026-10-09 | Test EAs (random baseline, indicator replay), rig only |
| RiskGuardButtons v1.00 → v1.14 (77001) | 2026-10-03..07 | Risk buttons, the live one |
| TickSpeedGauge v1.00 → v1.53 | 2026-10-03..07 | Order-flow research panel, never trades |
| TurtleTradeLogger v1.05–v1.06 | 2026-09-25 | The ledger fixed (backfill was appending nothing) |

## Test copies (never attach)

Built to measure ideas; each one reproduces the parent EA exactly when its new switches are off.

| File | Date | Tests |
|---|---|---|
| `Saad_mini`, `Saad_guard`, `Saad_fvg` | 2026-10-12 | M5/M1 variants; min R:R, failure / structure exits; FVG safe zone (report §2, §9) |
| `Saad_cut` | 2026-10-13 | Loss-cutting list: hard $ cut, EMA exit, weekend flat (report §12) |
| `Saad_meta` | 2026-10-13 | Meta-labeling, classifier + regression (report §13–14) |
| `Saad_regime` | 2026-10-13 | GMM market regimes (report §15) |
| `Saad_v118test` | 2026-10-13 | "v1.18" daily loss limit + Friday close, test only (report §16) |
| `Saad_exhaust` | 2026-10-13 | In-trade exhaustion exit (report §17) |
| `Saad_drl` | 2026-10-13 | PPO position sizing (report §19) |
| `Saad_mature` | 2026-10-13 | Mature-runner H1/H4 exit (report §20) |
| `Saad_pyramid` | 2026-10-13 | Pyramiding: spacing, tiers, sizing, locks (report §21–23) |
