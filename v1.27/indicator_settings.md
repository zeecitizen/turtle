# Indicator settings for v1.27

Chart: **BLUEBERRY:XAUUSD, 15 min**, indicator *Saad 15min v1.23 — mirror of the EA* (code: `saad_15min_indicator.pine` in this folder). Saved 2026-10-19.

= the v1.26 settings with **nose 0.35** (`iNose`). Restore: ask Claude to re-apply `indicator_settings.json`.

| # | Setting | Variable | Value |
|---|---|---|---|
| 0 |  | `iFast` | **16** |
| 1 |  | `iSlow` | **32** |
| 2 |  | `iWick` | **0.45** |
| 3 |  | `iBodyMax` | **0.6** |
| 4 |  | `iNose` | **0.35** |
| 5 |  | `iPinDir` | **False** |
| 6 |  | `iPinCol` | **False** |
| 7 |  | `iUsePin` | **True** |
| 8 |  | `iMaru` | **True** |
| 9 |  | `iMaruB` | **0.53** |
| 10 |  | `iHammer` | **True** |
| 11 |  | `iStar` | **True** |
| 12 |  | `iHamR` | **2.5** |
| 13 |  | `iHamN` | **0.5** |
| 14 |  | `iMinAtr` | **0.55** |
| 15 |  | `iLRule` | **Both** |
| 16 |  | `iSLine` | **9 EMA** |
| 17 |  | `iTouchM` | **Candle touches** |
| 18 |  | `iTouchP` | **1** |
| 19 |  | `iLExitAb` | **False** |
| 20 |  | `iBreakB` | **1** |
| 21 |  | `iBreakP` | **3** |
| 22 | Stop distance beyond the setup candle, in pips (1 pip = $0.10, so 35 = $3.50) | `iSlPips` | **31** |
| 23 | Skip the trade if that stop is more than $X away from the entry (0 = never skip) | `iMaxRisk` | **20** |
| 24 | BUY · TP1 this many pips BEFORE the EMA (0 = exactly on the EMA) | `iLTpP` | **0** |
| 25 | SELL · a swing low = a low with X higher candles on each side | `iPivot` | **3** |
| 26 | SELL · look back at most X candles for that swing low | `iLook` | **100** |
| 27 | SELL · TP1 this many pips BEFORE (above) the swing low (0 = exactly on it) | `iSTpP` | **0** |
| 28 | BUY + SELL · TP1 must be at least X pips from the entry (closer: a BUY gets no TP1, a SELL is skipped) | `iMinTp` | **5** |
| 29 | SELL · skip the trade if the swing low is more than X pips away (0 = off) | `iMaxTp` | **0** |
| 30 | Day close: shut trades still in LOSS this many minutes before the close (0 = off) | `iCloseM` | **3** |
| 31 | BUY · after TP1 the stop trails $X under the best price | `iLTrail` | **2** |
| 32 | SELL · after TP1 the stop trails $X over the best price | `iSTrail` | **2** |
| 33 | Breakeven (CTC): move the stop to the entry once price has covered X of the way to TP1 (0.75 = 75% · 0 = off) | `iBePct` | **0.75** |
| 34 | BUY with no TP1 (the exit EMA is not above the entry) · trailing stop X x ATR behind the best price | `iTrAtr` | **2** |
| 35 |  | `iEr` | **0** |
| 36 |  | `iErLen` | **16** |
| 37 |  | `iGap` | **True** |
| 38 | Close this share at TP1 (0.5 = half · 0.95 = 95% · 1 = everything), the rest keeps running | `iPartial` | **0.5** |
| 39 | After TP1 the stop is never worse than the entry | `iTp1Be` | **True** |
| 40 |  | `iLots` | **2** |
| 41 |  | `iBuys` | **True** |
| 42 |  | `iSells` | **True** |
| 43 |  | `iSkips` | **True** |
| 44 |  | `iCloseT` | **16:59** |
| 45 |  | `iCloseTz` | **America/New_York** |
| 46 |  | `iCs` | **100** |
| 47 |  | `iSpread` | **0.17** |
| 48 |  | `iComm` | **0** |
| 49 |  | `iPanel` | **True** |
| 50 |  | `iLog` | **False** |
| 51 |  | `iDrawTo` | **0** |
| 52 | Show today's trades box (top right) | `iShowRules` | **True** |
| 53 | Today's trades box: MT5 server timezone (PXBT = UTC+0) | `iDayTz` | **UTC+0** |
| 54 |  | `iDetailDays` | **3** |
| 55 |  | `iSkipBoth` | **False** |
| 56 |  | `iTightTrail` | **False** |
| 57 | Apply to | `pkApply` | **All trades** |
| 58 | Start: giveback / $ trail / ATR / candle / EMA only once the trade is this many $ in profit | `pkStart` | **0** |
| 59 | ① Breakeven: stop to the entry once $X in profit (0 = off) | `pkBeUsd` | **0** |
| 60 |     ...and lock this many $ beyond the entry | `pkBeOff` | **0** |
| 61 | ② Lock: once $X in profit... (0 = off) | `pkLockAt` | **0** |
| 62 |     ...lock the stop this many $ beyond the entry | `pkLockUsd` | **0** |
| 63 | ③ Ladder (with ②): every further $X of profit raises the lock by $X (0 = off) | `pkStep` | **0** |
| 64 | ④ Giveback: keep (100 - X)% of the best profit, e.g. 30 = give back 30% (0 = off) | `pkGive` | **0** |
| 65 | ⑤ $ trail: stop this many $ behind the best price (0 = off) | `pkTrail` | **0** |
| 66 | ⑥ ATR trail: stop this many x ATR behind the best price (0 = off) | `pkAtr` | **0** |
| 67 | ⑦ Candle trail: stop under the lowest low of the last N closed candles (0 = off) | `pkLowN` | **0** |
| 68 | ⑧ EMA trail: stop 1 pip under this EMA of the closed candle (0 = off) | `pkEma` | **0** |
| 69 | BUY with no TP1 · keep that trailing stop at least $X under the candle close (0 = off) | `pkGap` | **0** |
| 70 | Entry: wick break of the setup candle, or wait for a candle CLOSE beyond it (enter at the next open) | `enMode` | **Wick break (EA)** |
| 71 | Cut: N candles in a row against the trade while in loss -> close at the next open (0 = off) | `adRunN` | **0** |
| 72 | Cut: still in loss after N candles -> close at the next open (0 = off) | `adBars` | **0** |
| 73 | Cut: a candle closes beyond the slow EMA against the trade while in loss -> close at the next open | `adEmaX` | **False** |
| 74 | Cut: max loss - stop no further than $X from the entry (0 = off, the EA's stop) | `adMaxUsd` | **0** |
| 75 | BUY · how many recent candles make the range (their low = 0%, their high = 100%) | `rpLook` | **7** |
| 76 | BUY 0-5% | `rpB00` | **True** |
| 77 | 5-10% | `rpB01` | **True** |
| 78 | 10-15% | `rpB02` | **True** |
| 79 | 15-20% | `rpB03` | **True** |
| 80 | 20-25% | `rpB04` | **True** |
| 81 | BUY 25-30% | `rpB05` | **False** |
| 82 | 30-35% | `rpB06` | **False** |
| 83 | 35-40% | `rpB07` | **True** |
| 84 | 40-45% | `rpB08` | **False** |
| 85 | 45-50% | `rpB09` | **True** |
| 86 | BUY 50-55% | `rpB10` | **False** |
| 87 | 55-60% | `rpB11` | **False** |
| 88 | 60-65% | `rpB12` | **False** |
| 89 | 65-70% | `rpB13` | **False** |
| 90 | 70-75% | `rpB14` | **True** |
| 91 | BUY 75-80% | `rpB15` | **False** |
| 92 | 80-85% | `rpB16` | **True** |
| 93 | 85-90% | `rpB17` | **False** |
| 94 | 90-95% | `rpB18` | **True** |
| 95 | 95-100% | `rpB19` | **True** |
| 96 | BUY over 100% | `rpB20` | **True** |
| 97 | Show the diagnostics table: this month's trades grouped by where in the range they entered (BUY from the low, SELL from the high) | `rpDiag` | **True** |
| 98 | When a range is unticked | `rpOff` | **Stand aside while it would have run** |
| 99 | No new trade for N candles after a trade closes (0 = off; 2 = the exit candle + the next 2) | `coolN` | **0** |
| 100 | ...blocks | `coolDir` | **Same direction** |
| 101 | ...only after a WINNING exit | `coolWin` | **False** |
| 102 | Exit when the candle AFTER the entry candle closes beyond it: BUY below its low, SELL above its open/high -> out at the next open | `fxOn` | **False** |
| 103 | ...SELL: the line it must close above | `fxSellRef` | **Never (BUY only)** |
| 104 | Top-right box: list the days from this date (0 = the last 30 days) | `lsFrom` | **0** |
| 105 | ...up to this date (0 = now) | `lsTo` | **0** |
| 106 | Detail tags (setups, skips, BE/TP, exit X): keep at most N - the rest of TradingView's 500 labels stays for BUY / SELL / EXIT | `iDetMax` | **200** |
| 107 | Trade export table (bottom centre): every trade with entry / exit times (UTC), for comparing with MT5 - uses the date range above, else all trades | `exOn` | **False** |
| 108 | SELL · how many recent candles make the range (their high = 0%, their low = 100%) | `rpLookS` | **7** |
| 109 | SELL 0-5% | `rpS00` | **True** |
| 110 | 5-10% | `rpS01` | **True** |
| 111 | 10-15% | `rpS02` | **True** |
| 112 | 15-20% | `rpS03` | **True** |
| 113 | 20-25% | `rpS04` | **True** |
| 114 | SELL 25-30% | `rpS05` | **True** |
| 115 | 30-35% | `rpS06` | **True** |
| 116 | 35-40% | `rpS07` | **False** |
| 117 | 40-45% | `rpS08` | **False** |
| 118 | 45-50% | `rpS09` | **False** |
| 119 | SELL 50-55% | `rpS10` | **True** |
| 120 | 55-60% | `rpS11` | **False** |
| 121 | 60-65% | `rpS12` | **False** |
| 122 | 65-70% | `rpS13` | **False** |
| 123 | 70-75% | `rpS14` | **True** |
| 124 | SELL 75-80% | `rpS15` | **False** |
| 125 | 80-85% | `rpS16` | **False** |
| 126 | 85-90% | `rpS17` | **True** |
| 127 | 90-95% | `rpS18` | **True** |
| 128 | 95-100% | `rpS19` | **True** |
| 129 | SELL over 100% | `rpS20` | **False** |
| 130 | Require trend alignment with | `htReq` | **Off** |
| 131 | ...trend EMA length on that timeframe | `htEma` | **90** |
| 132 | Show the EXIT LAB table: this month's SAME entries with ~20 other ways to take profit, BUY and SELL apart | `xDiag` | **True** |
| 133 | Trades of one month: a centre panel listing every trade (off by default) | `mtOn` | **False** |
| 134 | ...which month | `mtMonth` | **October** |
| 135 | TP1 METHOD | `tpMode` | **Next EMA beyond the entry (touch, close all)** |
| 136 | Fixed $ target / Partial · BUY: TP1 $X above the entry | `tpFixB` | **2.5** |
| 137 | Fixed $ target / Partial · SELL: TP1 $X below the entry | `tpFixS` | **2.5** |
| 138 | Fibonacci · TP1 at X% of the setup candle's range (161.8 = the EXIT LAB row) | `tpFib` | **161.8** |
| 139 | Partial · close this share at the target (0.5 = half) | `tpPart` | **0.6** |
| 140 | Partial · the rest trails $X behind the best price | `tpPartTr` | **1** |
| 141 | Fixed $ / Fibonacci / Partial · target not far enough beyond the entry | `tpNoFix` | **Use the normal TP1** |
| 142 | ...with Pause: no new trade for N candles after a trade is skipped in an unticked range | `rpPause` | **1** |
| 143 | Debug: event export table (every setup and skip with its reason, UTC) - for the compare page's sync check | `skEx` | **True** |
| 144 | ...events from (0 = the last 300) | `skFrom` | **1792181880000** |
| 145 | ...events up to (0 = now) | `skTo` | **1792182360000** |
| 146 | No new trades while the broker is closed (Blueberry: 4:59 PM to 6:01 PM New York) | `bcOn` | **True** |
| 147 | ...closed from (New York time) | `bcFrom` | **16:59** |
| 148 | ...open again at (New York time) | `bcTo` | **18:01** |
| 149 | Stop loss type | `iSlMode` | **ATR x from the entry** |
| 150 | ...ATR multiple (with 'ATR x from the entry') | `iSlAtrM` | **1.6** |
| 151 | Re-entry after a stop loss: when the ORIGINAL stop is hit, re-arm the same setup and re-enter if price breaks back through its break level | `reOn` | **False** |
| 152 | ...re-arm window: candles after the stop-out | `reBars` | **23** |
| 153 | EXIT · quick pick (one click = a whole exit; overrides the TP1 METHOD and the AFTER TP1 share) | `xPick` | **Off - use the TP1 METHOD and AFTER TP1 settings below** |
| 154 | Custom session only: from this broker-server hour (server = New York + 7 = PKT - 2 in summer, PKT - 3 in winter) | `fSessFrom` | **2** |
| 155 | Custom session only: ...until this server hour (not included; 24 = end of the day) | `fSessTo` | **16** |
| 156 | Trade only when ADX(14) of the last closed candle is at least (0 = off) | `fAdxMin` | **30** |
| 157 | Trade only when ATR(14) of the last closed candle is at least $X (0 = off) | `fAtrMin` | **0** |
| 158 | ...and at most $X (0 = off) | `fAtrMax` | **0** |
| 159 | Trading session | `fSess` | **All hours** |
