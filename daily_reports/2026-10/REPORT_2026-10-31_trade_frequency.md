# 31 October 2026 — more trades from the 99.7% save (trade frequency)

Zee: *"i want to find out if we make it trade more at the same or similar winrate. so it takes 399 trades over the 4 years.. which misses out somedays.. ideally we'd like atleast one trade per day or at max once per two days"*

## 1. The 99.7% save is real in MT5
`2026-10-30 23-08-23`, MT5 on an **M15** chart, Blueberry ticks, 2023 → Oct 2026:

| Delay | Trades | WR | Net |
|---|---|---|---|
| None | 395 | 99.75% | +$162,491 |
| Random | 389 | 99.74% | +$156,881 |

The tester said 399 trades and +$164,148. The one loser (−$990, Nov 3 2023) is a Friday-close exit, not a stop.

It trades on **286 of 983 weekdays (29%)**:

| Year | Weekdays with a trade |
|---|---|
| 2023 | 16% |
| 2024 | 27% |
| 2025 | 34% |
| 2026 | 42% |

The filters are fixed dollar amounts (EMA gap 22.5 pips, ATR ≥ $1.5), so quiet years trade less. The longest gap was 27 Jul → 11 Sep 2023.

## 2. What cuts the trades
`monitor/saad_view/research/freq_funnel.py` switches each filter off on its own:

| Filter switched off | Extra trading days | WR | Losers |
|---|---|---|---|
| Entry boxes (InpBandsB/S) | +195 | 94.6% | 49 |
| Range boxes (TvBox) | +154 | 93.9% | 46 |
| EMA gap 22.5 pips | +109 | 98.25% | 10 |
| Tuesday skip | **+85** | **99.02%** | **5** |
| Session 3–19 | +56 | 95.2% | 24 |
| Keltner / VA box | +45 / +46 | 96.5% / 97.6% | |

Max spread and break pips only change which entries fire, so they aren't cutters.

## 3. Frontier: loosen only, scored on trading days, both halves must improve
`research/freq_grow.py` → saves written by `research/freq_save.py` → verified with `research/mt5_years.py` (M15):

| Save | Change from the 99.7% save | Days, 4 yrs | % of weekdays, 2026 | MT5 trades | MT5 WR | Random-delay WR | MT5 net |
|---|---|---|---|---|---|---|---|
| `2026-10-31 00-17-00 freq 371 days WR 99.0` | Tuesday back | 371 | 52% | 507 | 99.01% | 99.00% | +$185,917 |
| `2026-10-31 00-17-01 freq 402 days WR 98.8` | + entry boxes SELL 19, BUY 12 | 402 | 56% | 564 | 98.76% | 98.39% | +$201,904 |
| `2026-10-31 00-17-02 freq 438 days WR 98.6` | + ATR $1.25, pin body 0.55, hour 11 | 438 | 57% | 617 | 98.54% | 98.36% | +$213,294 |

Every year is profitable for all three. Most of the added losers are full −$5.2k stops:

| Save | Extra losers | Full stops |
|---|---|---|
| 371 days | 4 | 4 |
| 402 days | 6 | 5 |
| 438 days | 8 | 7 (the other is a −$1,296 Friday close, 18 Jul 2025) |

So the drawdown grows from about $1k to about $8k.

Tightening Zee's 504-day save (`2026-10-28 19-27-36`, 97.0%) under the same rule gives fewer days at every WR. At 98.5% it reaches only 354 days.

## 4. Limits and rejected ideas
- **Every other day over all four years (~490 days) costs about 97% WR.** The 19-27-36 save has 504 days at 97.0%.
- **Every day is impossible with this entry.** With every filter off it trades on 66% of weekdays (90% WR, losing money). The 93.8% base reaches 72%.
- **Fitting haircut.** The 99.7% filters were tuned with Tuesday skipped, so Tuesday trades are unseen. On them the same filters scored 96.4% (112 trades, 4 losers). Part of that is Tuesday being a weaker day.
- **Rejected: Tuesday BUYs only.** Tuesday SELLs held 5 of the 8 extra losers in the new saves. But with Tuesday switched on in other settings, Tuesday BUYs lose just as often (90.7–90.8%), so the pattern doesn't hold.
- **Rejected: an ATR-relative EMA gap** (≥ 0.5 ATR instead of 22.5 pips). It gave +31 trades and +3 losers.

## 5. Changed files
- New: `research/freq_funnel.py`, `research/freq_grow.py` (loosen / tighten), `research/freq_save.py`.
- `research/mt5_years.py` now retries an empty report that comes back in under 30 s (MT5 agent "authorization failed (Invalid parameters)").
- The three saves in `settings/saved/` carry the notes and MT5 results.
- Nothing is committed.
