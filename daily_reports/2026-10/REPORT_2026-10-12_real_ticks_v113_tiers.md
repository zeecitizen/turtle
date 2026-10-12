# 12 October 2026 — real-tick court: Saad_strategy_15min v1.13, the small-account tiers, M5 rejected

**Supersedes:** [REPORT_2026-10-11_12_saad_15min.md](REPORT_2026-10-11_12_saad_15min.md). Its headline
numbers (+$207k, +$178–181k) were measured on half-synthetic data — see §1.

## 1. THE DATA (read first)
- Around Oct 10–11, Axi revised its gold history. Since then the MT5 tester on **XAUUSD.pro** discards real
  ticks for ~135k of 272k Jan–Oct minutes and invents ticks from the candles. This happens in the rigs and in
  Zee's own terminal.
- **Test on XAUUSD_TK** in C:\mt5_rig_axi / C:\mt5_rig_axi2. It is a custom symbol made from Axi's 60.4M real
  ticks (mt5/AxiTickClone.mq5), with Axi's sessions and specs. The harness adds $4/lot commission.
- **On real ticks, v1.09 = +$151.9k at 1 lot (Jan 6–Oct 8), not +$207k.**
- Delay (200 ms or random) costs only ~0.3% on real ticks.

## 2. What ships
- **`Saad_strategy_15min` v1.13** (magic 88302):
  - Defaults: SL 35 pips, hammer ratio 2.5, pin wick 0.45, `InpLongResTp1` OFF, default lot 0.10.
  - **1 lot, random delay: +$165–167k**, PF 1.43, DD ~9.5%.
  - **0.10 lot: +$17.2k (≈ +$92/day), DD 2%, worst day −$440.**
  - Beat the v1.09 control on Jan–Jun, on the Jul–Oct holdout (+$48.2k vs +$38.0k) and over the full
    period (+$167.5k vs +$150.9k).
  - Caveat: the holdout also chose v1.13 from 20 candidates, so read the full-period +11% as the realistic gain.
- **v1.11 bug fixed in v1.12.** The resistance rule was set and then reset, which cost ~$39k. Fixed, the rule
  still loses −$70k, so it is off.
- **EA_20USD … EA_200USD:** v1.13 at a fixed 0.01 lot, survival stats in each header.
  - Only **$200** survived all 9 monthly starts (median month end $383, worst $136).
  - $80 and $100 were wiped out in 2 of 9.
  - **$20 and $40 are not viable** (median month end $3.82 / $0.93).
  - 0.01 lot is the minimum on Axi and PXBT. Leverage does not shrink a loss.

## 3. Tested and rejected on real ticks
- **Tighter stops:** 5–25 pips, ATR 0.5–1.5, fixed $2–10.
- **Wait for a dip after the break:** 4 depths × 1–3 candles.
- **Liquidity sweep then enter:** 20 variants, all losing.
- **Partial close at TP1.**
- **Break 0 pips.**
- **2×ATR stop:** good on Jan–Jun, failed the holdout.
- **Shorts with the old exit:** good on Jan–Jun, failed the holdout.
- **Resistance TP1 for longs.**
- **M5 "frequent" engine:** 24 variants, 6–26 trades/day, best PF 1.04, most losing.

## 4. Running / next
- Tuning round 2 around v1.13 on Jan–Jun (`zee_g.jsonl`). Promote only if Jul–Oct also beats v1.13.
- Then v1.13 on the PXBT rig, after checking its discard count.

Logs: `monitor/strategy_lab/zee_*.jsonl`. Rank them with `python saad_rank.py FILE`.
