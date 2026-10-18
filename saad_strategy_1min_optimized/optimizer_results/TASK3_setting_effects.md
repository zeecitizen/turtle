# Task 3 — what each setting does on 1 minute (TradingView chart week vs MT5 full year)

Chart: BLUEBERRY:XAUUSD 1 min, the indicator's own trades over the history the chart holds (about one week, Oct 12–16). Unchanged settings on the chart: **161 trades, win rate 62.1%, net +34,356, max drawdown 7,114**.
Each line changes ONE setting and keeps everything else as it was; every setting was put back afterwards.

The last columns show the same change over the **full year in MT5** (Task 5: XAUUSD_BB real ticks, Jan 1 – Oct 16, from the same base) where it exists. A setting that helps on the chart week but not over the year is fitted to that week.

| # | Setting | Chart value | Tried | Chart week: trades / WR / net / max DD | vs unchanged (net) | MT5 year: PF / WR / net |
|---|---|---|---|---|---|---|
| 1 | rpOff (chart-only) | Stand aside while it would have run | **Skip it and take the next setup** | 217 / 52.1% / -1,231 / 21,182 | -35,587 | – |
| 2 | iMaxRisk | 4.5 | **2** | 0 / 0.0% / +0 / 0 | -34,356 | – |
| 3 | tpMode | Partial: close a share at a fixed $ target, trail the rest | **Normal: BUY = touch of the other EMA · SELL = last swing low** | 163 / 48.5% / +813 / 15,301 | -33,543 | – |
| 4 | tpPart | 0.1 | **1** | 265 / 54.0% / +3,364 / 9,300 | -30,992 | – |
| 5 | iBreakP | 5 | **8** | 159 / 55.3% / +5,980 / 11,205 | -28,376 | – |
| 6 | iBreakP | 5 | **0** | 189 / 52.4% / +6,433 / 12,111 | -27,922 | – |
| 7 | pkAtr (chart-only) | 0 | **1** | 320 / 45.9% / +6,611 / 8,710 | -27,745 | – |
| 8 | htReq | Off | **4 hour** | 112 / 55.4% / +7,251 / 7,627 | -27,105 | – |
| 9 | iSlPips | 15 | **5** | 221 / 49.3% / +7,813 / 12,224 | -26,543 | – |
| 10 | htReq | Off | **1 hour** | 127 / 51.2% / +8,506 / 9,294 | -25,850 | – |
| 11 | iUsePin | True | **False** | 140 / 55.0% / +8,962 / 6,961 | -25,394 | – |
| 12 | rpOff (chart-only) | Stand aside while it would have run | **Pause N candles (MT5 can do this)** | 207 / 56.5% / +11,262 / 13,382 | -23,094 | – |
| 13 | enMode (chart-only) | Wick break (EA) | **Candle close beyond** | 32 / 53.1% / +11,545 / 4,510 | -22,810 | – |
| 14 | iBreakB | 1 | **3** | 172 / 52.9% / +11,566 / 8,172 | -22,790 | – |
| 15 | iBreakP | 5 | **2** | 181 / 50.3% / +11,971 / 8,172 | -22,384 | – |
| 16 | tpMode | Partial: close a share at a fixed $ target, trail the rest | **Fixed $ target** | 231 / 54.5% / +12,416 / 9,108 | -21,940 | – |
| 17 | tpPartTr | 5.6 | **0.3** | 241 / 53.1% / +12,698 / 8,986 | -21,657 | – |
| 18 | pkLowN (chart-only) | 0 | **3** | 317 / 45.1% / +12,704 / 12,885 | -21,652 | – |
| 19 | htReq | Off | **5 min** | 130 / 56.9% / +12,941 / 7,800 | -21,415 | – |
| 20 | pkTrail (chart-only) | 0 | **1** | 248 / 55.2% / +13,840 / 4,905 | -20,515 | – |
| 21 | rpLook (chart-only) | 7 | **12** | 158 / 55.1% / +14,733 / 5,655 | -19,622 | – |
| 22 | iSlMode | Pips beyond the setup candle | **ATR x from the entry** | 324 / 39.2% / +14,808 / 10,234 | -19,548 | – |
| 23 | iMinAtr | 0.35 | **0.6** | 153 / 54.9% / +14,842 / 6,876 | -19,514 | – |
| 24 | htReq | Off | **30 min** | 113 / 56.6% / +15,441 / 6,628 | -18,915 | – |
| 25 | iBreakB | 1 | **2** | 171 / 58.5% / +15,758 / 5,936 | -18,597 | – |
| 26 | tpMode | Partial: close a share at a fixed $ target, trail the rest | **Fibonacci extension of the setup candle** | 322 / 66.5% / +16,096 / 5,120 | -18,259 | – |
| 27 | iTouchP | 5 | **0** | 159 / 56.0% / +16,583 / 8,374 | -17,773 | – |
| 28 | iLExitAb | False | **True** | 129 / 56.6% / +16,764 / 5,491 | -17,592 | – |
| 29 | iSlPips | 15 | **10** | 187 / 53.5% / +16,775 / 6,913 | -17,580 | – |
| 30 | iTouchM | Candle touches | **Wick touches, body on trade side** | 145 / 55.2% / +16,940 / 7,593 | -17,415 | – |
| 31 | iBePct | 0.8 | **0.5** | 190 / 51.6% / +17,047 / 6,898 | -17,309 | – |
| 32 | iEr | 0.02 | **0.2** | 149 / 57.0% / +17,467 / 7,526 | -16,888 | – |
| 33 | adEmaX (chart-only) | False | **True** | 254 / 40.2% / +19,809 / 5,144 | -14,547 | – |
| 34 | iMaru | True | **False** | 129 / 55.0% / +19,836 / 5,708 | -14,520 | – |
| 35 | tpFixS | 2.5 | **4** | 146 / 58.9% / +20,955 / 6,947 | -13,401 | – |
| 36 | iEr | 0.02 | **0.1** | 161 / 54.7% / +21,341 / 8,481 | -13,015 | – |
| 37 | iFast | 3 | **8** | 153 / 61.4% / +22,109 / 8,374 | -12,247 | – |
| 38 | adBars (chart-only) | 0 | **10** | 194 / 54.1% / +22,201 / 5,585 | -12,154 | – |
| 39 | htReq | Off | **15 min** | 116 / 62.1% / +22,971 / 5,423 | -11,385 | – |
| 40 | coolN | 1 | **3** | 160 / 62.5% / +23,290 / 5,631 | -11,066 | – |
| 41 | iSLine | Either | **50 EMA** | 154 / 59.1% / +24,092 / 8,374 | -10,264 | – |
| 42 | adRunN | 0 | **3** | 197 / 54.3% / +24,820 / 5,806 | -9,535 | – |
| 43 | rpLookS (chart-only) | 7 | **5** | 159 / 62.9% / +43,140 / 6,927 | +8,784 | – |
| 44 | fxOn (chart-only) | False | **True** | 176 / 60.2% / +27,184 / 6,746 | -7,172 | – |
| 45 | iFast | 3 | **5** | 152 / 58.6% / +27,263 / 8,374 | -7,093 | – |
| 46 | iTouchP | 5 | **2** | 160 / 58.1% / +27,393 / 7,114 | -6,962 | – |
| 47 | coolDir | Same direction | **Both directions** | 156 / 60.9% / +27,786 / 7,381 | -6,569 | – |
| 48 | reBars | 18 | **5** | 167 / 62.3% / +27,806 / 7,007 | -6,550 | – |
| 49 | iWick | 0.4 | **0.6** | 149 / 63.1% / +28,224 / 4,899 | -6,131 | – |
| 50 | iWick | 0.4 | **0.3** | 158 / 64.6% / +40,247 / 7,114 | +5,891 | – |
| 51 | tpPart | 0.1 | **0.5** | 161 / 62.1% / +28,642 / 6,555 | -5,714 | – |
| 52 | iMaxRisk | 4.5 | **0** | 174 / 62.6% / +39,889 / 7,373 | +5,534 | – |
| 53 | iMaruB | 0.53 | **0.45** | 162 / 63.0% / +39,733 / 6,486 | +5,377 | – |
| 54 | tpFixB | 2.5 | **1** | 190 / 67.9% / +29,005 / 6,532 | -5,351 | – |
| 55 | reOn | True | **False** | 163 / 63.2% / +39,559 / 7,703 | +5,203 | – |
| 56 | iSlPips | 15 | **25** | 97 / 64.9% / +29,314 / 5,053 | -5,042 | – |
| 57 | adMaxUsd (chart-only) | 0 | **3** | 228 / 51.3% / +29,477 / 7,230 | -4,878 | – |
| 58 | iPinDir | False | **True** | 152 / 59.2% / +29,523 / 7,314 | -4,833 | – |
| 59 | iNose | 0.21 | **0.1** | 151 / 61.6% / +29,641 / 5,328 | -4,714 | – |
| 60 | iNose | 0.21 | **0.35** | 165 / 57.6% / +29,870 / 6,253 | -4,485 | – |
| 61 | tpFixS | 2.5 | **1** | 192 / 71.4% / +30,005 / 3,828 | -4,351 | – |
| 62 | iHamN | 0.35 | **0.2** | 159 / 61.0% / +30,110 / 6,465 | -4,246 | – |
| 63 | iHammer | True | **False** | 159 / 61.0% / +30,110 / 6,465 | -4,246 | – |
| 64 | iErLen | 16 | **8** | 160 / 60.6% / +30,262 / 6,812 | -4,093 | – |
| 65 | iHamN | 0.35 | **0.5** | 169 / 60.4% / +30,605 / 7,155 | -3,751 | – |
| 66 | iErLen | 16 | **24** | 152 / 60.5% / +30,939 / 5,901 | -3,416 | – |
| 67 | iBePct | 0.8 | **0** | 151 / 65.6% / +30,945 / 5,498 | -3,411 | – |
| 68 | iBePct | 0.8 | **1** | 151 / 65.6% / +30,945 / 5,498 | -3,411 | – |
| 69 | iEr | 0.02 | **0** | 159 / 61.0% / +31,056 / 6,812 | -3,299 | – |
| 70 | iMaxRisk | 4.5 | **8** | 175 / 61.7% / +37,560 / 7,638 | +3,204 | – |
| 71 | rpLook (chart-only) | 7 | **5** | 166 / 62.0% / +31,370 / 5,582 | -2,986 | – |
| 72 | coolN | 1 | **0** | 157 / 62.4% / +31,755 / 7,114 | -2,600 | – |
| 73 | tpPartTr | 5.6 | **1.5** | 224 / 59.4% / +31,855 / 8,667 | -2,501 | – |
| 74 | iMaruB | 0.53 | **0.65** | 150 / 61.3% / +36,777 / 6,973 | +2,421 | – |
| 75 | adRunN | 0 | **6** | 162 / 62.3% / +32,665 / 7,114 | -1,691 | – |
| 76 | rpLookS (chart-only) | 7 | **12** | 146 / 58.2% / +32,719 / 7,895 | -1,637 | – |
| 77 | iLRule | Both | **On 50 EMA, exit 9** | 158 / 62.7% / +32,801 / 7,114 | -1,555 | – |
| 78 | coolWin | False | **True** | 161 / 62.1% / +33,060 / 7,114 | -1,296 | – |
| 79 | iStar | False | **True** | 163 / 60.7% / +33,192 / 6,834 | -1,164 | – |
| 80 | iCloseM | 1 | **0** | 161 / 61.5% / +33,196 / 7,114 | -1,160 | – |
| 81 | iFast | 3 | **2** | 159 / 61.6% / +33,278 / 7,114 | -1,078 | – |
| 82 | iHamR | 2 | **1.5** | 164 / 61.6% / +35,385 / 7,114 | +1,029 | – |
| 83 | iHamR | 2 | **3** | 160 / 62.5% / +35,369 / 7,114 | +1,013 | – |
| 84 | iWick | 0.4 | **0.5** | 158 / 63.3% / +33,505 / 5,844 | -851 | – |
| 85 | iCloseM | 1 | **5** | 162 / 61.7% / +34,718 / 7,114 | +362 | – |
| 86 | tpFixB | 2.5 | **4** | 150 / 58.0% / +34,704 / 5,921 | +349 | – |
| 87 | reBars | 18 | **60** | 153 / 64.1% / +34,690 / 5,638 | +335 | – |
| 88 | iMinAtr | 0.35 | **0** | 163 / 62.6% / +34,610 / 7,114 | +255 | – |
| 89 | iMinAtr | 0.35 | **0.2** | 163 / 62.6% / +34,610 / 7,114 | +255 | – |
| 90 | iBodyMax | 0.6 | **0.4** | 159 / 62.9% / +34,537 / 6,404 | +181 | – |
| 91 | pkBeUsd (chart-only) | 0 | **1** | 176 / 58.0% / +34,381 / 5,299 | +25 | – |
| 92 | iSlow | 6 | **4** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 93 | iSlow | 6 | **10** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 94 | iSlow | 6 | **20** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 95 | iBodyMax | 0.6 | **0.8** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 96 | iTouchP | 5 | **8** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 97 | iSlAtrM | 1 | **1.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 98 | iSlAtrM | 1 | **2.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 99 | tpFib | 161.8 | **300** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 100 | iPartial | 0.65 | **0.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 101 | iPartial | 0.65 | **0.95** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 102 | iLTrail | 1 | **0.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 103 | iLTrail | 1 | **2** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 104 | iSTrail | 1.5 | **1** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 105 | iSTrail | 1.5 | **3** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 106 | iTrAtr | 0.1 | **0.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 107 | iTrAtr | 0.1 | **2** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 108 | pkGap | 0.1 | **0** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 109 | pkGap | 0.1 | **0.5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 110 | iMinTp | 1 | **0** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 111 | iMinTp | 1 | **10** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 112 | iLTpP | 0 | **5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 113 | iSTpP | 0 | **5** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 114 | rpPause | 1 | **3** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 115 | htEma | 9 | **20** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 116 | htEma | 9 | **50** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 117 | pkLockAt (chart-only) | 0 | **2** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 118 | iPinCol | False | **True** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 119 | iTp1Be | True | **False** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 120 | iGap | False | **True** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 121 | iLRule | Both | **On 9 EMA, exit 50** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 122 | iSLine | Either | **9 EMA** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |
| 123 | tpNoFix | Use the normal TP1 | **Skip the trade** | 161 / 62.1% / +34,356 / 7,114 | +0 | – |

## The settings that move the chart's results the most

- **rpOff**: Skip it and take the next setup → net -35,587, win rate -10.0 pts, drawdown +14,068 on the chart week
- **iMaxRisk**: 2 → net -34,356, win rate -62.1 pts, drawdown -7,114 on the chart week
- **tpMode**: Normal: BUY = touch of the other EMA · SELL = last swing low → net -33,543, win rate -13.6 pts, drawdown +8,187 on the chart week
- **tpPart**: 1 → net -30,992, win rate -8.1 pts, drawdown +2,186 on the chart week
- **iBreakP**: 8 → net -28,376, win rate -6.8 pts, drawdown +4,091 on the chart week
- **pkAtr**: 1 → net -27,745, win rate -16.2 pts, drawdown +1,596 on the chart week
- **htReq**: 4 hour → net -27,105, win rate -6.8 pts, drawdown +513 on the chart week
- **iSlPips**: 5 → net -26,543, win rate -12.8 pts, drawdown +5,110 on the chart week
- **iUsePin**: False → net -25,394, win rate -7.1 pts, drawdown -153 on the chart week
- **enMode**: Candle close beyond → net -22,810, win rate -9.0 pts, drawdown -2,604 on the chart week
- **iBreakB**: 3 → net -22,790, win rate -9.2 pts, drawdown +1,058 on the chart week
