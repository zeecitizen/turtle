# Research: keep 93.8% WR, cut the $5,000 loss — setting "2026-10-25 05-58-25" (2026-10-27)

Python = hypothesis only. MT5 rows are the only promoted numbers. Scripts + charts: this folder (`research/`).

## 0. MT5 verdict first (Jan–Oct 2026, rig, M1, no delay)
| Run | MT5 net | trades | worst | avg win | avg loss | DD |
|---|---|---|---|---|---|---|
| 93.8% base | **−$4,101** | 793 | −$5,182 | $376 | −$5,025 | $48.3k (40.7%) |
| stop $15 | −$8,346 | 816 | −$3,434 | $375 | −$3,008 | $36.1k |
| stop $20 | −$6,328 | 755 | −$4,220 | $377 | −$4,030 | $37.9k |
| no Friday close | identical to base (input had no effect in MT5 — check) | | | | | |
| session to 20 | identical to base (same — check) | | | | | |
| **TP 25 pips** | **+$17,977** | 678 | −$5,388 | $447 | −$5,031 | $46.2k |

* MT5's 2026 WR is still ~92.9% (737 of 793 by the avg win/loss), but the money is **negative**: breakeven at $376 / $5,025 needs 93.0%.
* The 4-year m15 tester said 2026 = +$64.8k. year1 (tick-matched) said −$1.7k. **MT5 sided with year1.** The +$264k / 93.8% headline comes from the m15 dataset and is not real for 2026.

## 1. Geometry (why the loss exists)
TP 20 pips = $2 (+$400 at 2 lots); stop $25 (−$5,000). 12.5 : 1. Breakeven WR 92.6%.
Winners dip deep before winning: median MAE $1.78, 10% go beyond $9, 5% beyond $13. **The wide stop IS the win rate.**
Stop $X keeps: $5 → 78% of winners, $10 → 91%, $15 → 96%. Every tighter stop turns winners into losers at nearly the rate it shrinks losses.

## 2. Losses (114 in the m15 run: 80 full stops, 33 Friday close, 1 close-based)
Charts: `research/sheets/loss_*.png` (all 114), `win_*.png` (24 random winners, same style, for comparison).
Chart observation: most losers die on 1–3 violent candles (shock), not a slow drift. Killer candle median 2.16×ATR vs 1.48 inside winners.
Many are sells inside a rising staircase / buys at a top — but the random winners show the same pictures.

## 3. Filters tested (pre-registered; filter pays only if removed trades lose > 9.5%, in BOTH halves)
| Family | Variants | Result |
|---|---|---|
| Camel humps (Zee's, ported from BasedOnLaws.mq5 CamelTrend) | pivot 2/3, look 48/96/192 M15 bars | with-trend 6.5–6.7% loss rate, against-trend 6.5–6.7%. **No separation.** |
| EMA slopes | EMA 19/66/200/264/800 slope + price side | 4.3–8.1%, never >9.5 in both halves |
| EMA alignment (19 vs 66) | | 5.7% vs 6.5% |
| Chop: CHOP 14/48, Kaufman ER 16/48, ADX, VHF 28, R² 32 | top/bottom 10/25% | max 8.1%. none |
| Volatility / shock: ATR, ATR vs 24h, biggest candle in last 4h, day range | | none (big-range days lose LESS) |
| Hour 20–21 UTC | | 12–17% both halves but only 83 trades; SessTo 20 = no change in MT5 |
| Friday | | 10.6% (14.5 / 8.3) — fails H2 |

Conclusion: on this setup, nothing known at entry predicts the losers. It is a mean-reversion bounce; trend direction is irrelevant to it.

## 4. Exits tested (tester m15)
* Checkpoint study: at 60 min, trades ≥$10 underwater are 59% losers — looked like an early-cut edge.
* Engine: decay stop (2–12 bars × −0.3…−0.6R) **loses money in every cell** (best +$188k vs +$264k). Exit interference again.
* ATR stops 2–6×: worse net, worse worst loss.
* Bigger TP: 25 pips best — and MT5 agrees (+$18k vs −$4k).

## 5. Answer to "make the win big enough"
Only lever with MT5 support: TP 25 pips (avg win $376 → $447, WR ~92%). The loss stays ~$5k.

## Next
* Re-run TP 25/30/35/40 in MT5; the tester's m15 dataset must not be used to rank this setting (it overstates 2026 by ~$66k).
* Investigate why InpXFriHour / InpSessTo changed nothing in MT5.

## 6. MT5 TP ladder (2026, WR derived from avg win/loss)
| TP | MT5 net | trades | WR | avg win | worst | DD |
|---|---|---|---|---|---|---|
| 20 (saved) | -4,101 | 793 | 92.9% | 376 | -5,182 | 48.3k |
| 25 | +17,977 | 678 | 92.3% | 447 | -5,388 | 46.2k |
| 30 | +5,290 | 627 | 90.9% | 513 | -5,388 | 47.8k |
| 35 | +26,722 | 552 | 90.6% | 577 | -5,388 | 44.5k |
| 40 | +29,101 | 537 | 89.8% | 634 | -5,388 | 44.4k |
Noisy (30 dips) and DD stays ~28%: a larger win helps but does not make this a strong strategy. 35-40 keeps ~90% WR.
