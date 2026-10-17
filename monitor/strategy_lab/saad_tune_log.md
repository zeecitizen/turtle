# Saad 1-min EA - one setting at a time (MT5 optimizer, Blueberry XAUUSD_BB, Jan 1 - Oct 17 2026)

Zee 2026-10-17: *"run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> ... set it in tradingview indicator -> and keep going till all are optimized"*

Score = net / max drawdown (OnTester). Execution delay 0 while searching. A value wins only if it beats the chart's value with its neighbours averaged in, and on profit.

| # | Setting | Was | Now | Profit was → now | Why |
|---|---|---|---|---|---|
| 1 | tpMode (InpTpMode) | Partial: close a share at a fixed $ target, trail the rest | **Fibonacci extension of the setup candle** | +45,607 → +63,325 | better: score 4.55 vs 2.70 (with neighbours), profit +63,325 vs +45,607 |
| 2 | tpFixB (InpTpFixUsdB) | 2 | **2.0** | +63,325 → ? | no clear gain (best 0.5: 4.55 vs 4.55) - kept |
| 3 | tpFixS (InpTpFixUsdS) | 2 | **2.0** | +63,325 → ? | no clear gain (best 0.5: 4.55 vs 4.55) - kept |
| 4 | tpFib (InpTpFibPct) | 161.8 | **161.8** | +63,325 → +63,325 | no clear gain (best 171.8: 4.33 vs 3.94) - kept |
| 5 | tpPart (InpTpPartPct) | 0.8 | **0.8** | +63,325 → +63,325 | no clear gain (best 0.1: 4.55 vs 4.55) - kept |
| 6 | tpPartTr (InpTpPartTrailUsd) | 2 | **2.0** | +63,325 → ? | no clear gain (best 0.5: 4.55 vs 4.55) - kept |
| 7 | tpNoFix (InpTpNoFixSkip) | Use the normal TP1 | **Use the normal TP1** | +63,325 → +63,325 | the chart's value is already the best |
| 8 | iSlPips (InpSlPips) | 34 | **36.0** | +63,325 → +67,665 | better: score 4.91 vs 4.65 (with neighbours), profit +67,665 vs +63,325 |
| 9 | iMaxRisk (InpMaxRiskUsd) | 11 | **20.0** | +67,665 → +177,318 | better: score 6.95 vs 4.10 (with neighbours), profit +177,318 vs +67,665 |
| 10 | iPartial (InpPartialPct) | 0.95 | **0.95** | +177,318 → +177,318 | no clear gain (best 1.00: 6.67 vs 6.57) - kept |
| 11 | iBePct (InpBeTpPct) | 1 | **1.0** | +177,318 → ? | no clear gain (best 0.95: 6.40 vs 6.37) - kept |
| 12 | iTp1Be (InpTp1Be) | True | **True** | +177,318 → +177,318 | no clear gain (best false: 6.46 vs 6.46) - kept |
| 13 | iLTrail (InpLongTrailUsd) | 1 | **1.0** | +177,318 → ? | no clear gain (best 3.0: 6.52 vs 6.45) - kept |
| 14 | iSTrail (InpShortTrailUsd) | 2 | **2.0** | +177,318 → ? | no clear gain (best 0.5: 6.49 vs 6.46) - kept |
| 15 | iTrAtr (InpTrailAtr) | 0.2 | **0.2** | +177,318 → +177,318 | no clear gain (best 0.1: 6.46 vs 6.46) - kept |
| 16 | pkGap (InpTrailGapUsd) | 0.1 | **0.1** | +177,318 → ? | the chart's value is already the best |
| 17 | pkLockAt (InpLockAtUsd) | 0 | **0.0** | +177,318 → +177,318 | no clear gain (best 7.5: 6.46 vs 5.84) - kept |
| 18 | pkLockUsd (InpLockUsd) | 0 | **0.0** | +177,318 → +177,318 | the chart's value is already the best |
| 19 | iCloseM (InpCloseLossMins) | 1 | **1** | +177,318 → +177,318 | no clear gain (best 0: 6.68 vs 6.63) - kept |
| 20 | iMinTp (InpMinTpPips) | 1 | **10.0** | +177,318 → +181,012 | better: score 6.59 vs 6.46 (with neighbours), profit +181,012 vs +177,318 |
| 21 | iLTpP (InpLongTpPips) | 0 | **0.0** | +181,012 → +181,012 | the chart's value is already the best |
| 22 | iSTpP (InpShortTpPips) | 0 | **0.0** | +181,012 → +181,012 | the chart's value is already the best |
| 23 | iPivot (InpSwingPivot) | 8 | **8** | +181,012 → +181,012 | no clear gain (best 7: 6.55 vs 6.53) - kept |
| 24 | iLook (InpSwingLook) | 32 | **32** | +181,012 → +181,012 | no clear gain (best 57: 6.62 vs 6.60) - kept |
| 25 | iMaxTp (InpMaxTpPips) | 0 | **0.0** | +181,012 → +181,012 | the chart's value is already the best |
| 26 | iBreakP (InpBreakPips) | 5 | **5.0** | +181,012 → +181,012 | no clear gain (best 0: 5.87 vs 5.52) - kept |
| 27 | iBreakB (InpBreakBars) | 1 | **1** | +181,012 → +181,012 | the chart's value is already the best |
| 28 | iTouchP (InpTouchPips) | 1 | **1.0** | +181,012 → +181,012 | no clear gain (best 5: 7.38 vs 6.49) - kept |
| 29 | iTouchM (InpTouchMode) | Candle touches | **Candle touches** | +181,012 → +181,012 | the chart's value is already the best |
| 30 | iLRule (InpLongRule) | Both | **Both** | +181,012 → +181,012 | no clear gain (best 0: 7.39 vs 6.60) - kept |
| 31 | iSLine (InpShortLine) | Either | **Either** | +181,012 → +181,012 | the chart's value is already the best |
| 32 | iLExitAb (InpLongExitAbove) | False | **False** | +181,012 → +181,012 | the chart's value is already the best |
| 33 | iUsePin (InpUsePin) | True | **True** | +181,012 → +181,012 | the chart's value is already the best |
| 34 | iPinDir (InpPinDir) | False | **False** | +181,012 → +181,012 | the chart's value is already the best |
| 35 | iPinCol (InpPinColor) | False | **False** | +181,012 → +181,012 | the chart's value is already the best |
| 36 | iMaru (InpMarubozu) | True | **True** | +181,012 → +181,012 | the chart's value is already the best |
| 37 | iMaruB (InpMaruBody) | 0.53 | **0.53** | +181,012 → +181,012 | the chart's value is already the best |
| 38 | iHammer (InpHammer) | True | **True** | +181,012 → +181,012 | the chart's value is already the best |
| 39 | iStar (InpStar) | True | **True** | +181,012 → +181,012 | the chart's value is already the best |
| 40 | iHamR (InpHamRatio) | 2 | **2.0** | +181,012 → ? | no clear gain (best 2.25: 6.54 vs 6.47) - kept |
| 41 | iHamN (InpHamNose) | 0.35 | **0.35** | +181,012 → +181,012 | no clear gain (best 0.40: 6.51 vs 6.39) - kept |
| 42 | iMinAtr (InpMinRangeAtr) | 0.35 | **0.35** | +181,012 → +181,012 | the chart's value is already the best |
| 43 | iEr (InpChopEr) | 0.01 | **0.0** | +181,012 → +188,638 | better: score 6.91 vs 6.63 (with neighbours), profit +188,638 vs +181,012 |
| 44 | iErLen (InpChopErLook) | 16 | **16** | +188,638 → +188,638 | no clear gain (best 4: 7.22 vs 7.22) - kept |
| 45 | iGap (InpGapCancel) | False | **False** | +188,638 → +188,638 | the chart's value is already the best |
| 46 | adRunN (InpCutRunN) | 0 | **5** | +188,638 → +192,276 | better: score 7.43 vs 5.79 (with neighbours), profit +192,276 vs +188,638 |
| 47 | htReq (InpHtfMin) | Off | **Off** | +192,276 → +192,276 | the chart's value is already the best |
| 48 | htEma (InpHtfEma) | 9 | **9** | +192,276 → +192,276 | no clear gain (best 4: 7.55 vs 7.55) - kept |
| 49 | rpPause (InpBandPauseBars) | 3 | **1** | +192,276 → +199,413 | better: score 7.91 vs 6.95 (with neighbours), profit +199,413 vs +192,276 |
| 50 | rpB00 (InpB00) | True | **True** | +199,413 → +199,413 | no clear gain (best false: 7.43 vs 7.43) - kept |
| 51 | rpB01 (InpB01) | True | **True** | +199,413 → +199,413 | no clear gain (best false: 7.43 vs 7.43) - kept |
| 52 | rpB02 (InpB02) | True | **True** | +199,413 → +199,413 | the chart's value is already the best |
| 53 | rpB03 (InpB03) | True | **False** | +199,413 → +200,160 | better: score 7.82 vs 7.43 (with neighbours), profit +200,160 vs +199,413 |
| 54 | rpB04 (InpB04) | True | **True** | +200,160 → +200,160 | no clear gain (best false: 7.86 vs 7.82) - kept |
| 55 | rpB05 (InpB05) | False | **False** | +200,160 → +200,160 | the chart's value is already the best |
| 56 | rpB06 (InpB06) | True | **True** | +200,160 → +200,160 | the chart's value is already the best |
| 57 | rpB07 (InpB07) | True | **True** | +200,160 → +200,160 | the chart's value is already the best |
| 58 | rpB08 (InpB08) | False | **False** | +200,160 → +200,160 | the chart's value is already the best |
| 59 | rpB09 (InpB09) | False | **False** | +200,160 → +200,160 | the chart's value is already the best |
| 60 | rpB10 (InpB10) | False | **True** | +200,160 → +205,058 | better: score 8.01 vs 7.82 (with neighbours), profit +205,058 vs +200,160 |
| 61 | rpB11 (InpB11) | False | **False** | +205,058 → +205,058 | the chart's value is already the best |
| 62 | rpB12 (InpB12) | True | **True** | +205,058 → +205,058 | the chart's value is already the best |
| 63 | rpB13 (InpB13) | False | **True** | +171,195 → +184,944 | better: score 7.32 vs 7.17 (with neighbours), profit +184,944 vs +171,195 |
| 64 | rpB14 (InpB14) | False | **False** | +140,515 → +140,515 | the chart's value is already the best |
| 65 | rpB15 (InpB15) | False | **False** | +140,515 → +140,515 | the chart's value is already the best |
| 66 | rpB16 (InpB16) | True | **True** | +140,515 → +140,515 | the chart's value is already the best |
