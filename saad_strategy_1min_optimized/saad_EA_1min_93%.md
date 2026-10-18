# Saad EA 1-min — TradingView indicator settings ("93%" chart)

Saved 2026-10-18 from the Saad indicator on **BLUEBERRY:XAUUSD, 1 minute** (TradingView, study `Saad 15min v1.23 — mirror of the EA`).
To restore: set each value below on the indicator (the names are as shown in its settings dialog), or ask Claude to re-apply this file.

## MT5 check of these exact settings (Saad_strategy_1min v1.35, XAUUSD_BB = Blueberry real ticks, M1, Jan 1 – Oct 16 2026, random delay, 2 lots)

| | |
|---|---|
| Net | **−$92,690** |
| Win rate (whole trades) | 45.8% |
| Profit factor | 0.85 |
| Max drawdown | $130,811 |
| Trades | 2,016 |
| Days green / red | 71 / 119 |

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct 1–16 |
|---|---|---|---|---|---|---|---|---|---|
| +17.6k | −9.8k | −4.1k | −19.3k | −16.4k | −13.0k | −41.9k | −0.1k | −14.5k | +8.9k |

Note: the TradingView chart only holds ~1 week of 1-minute history, so its win rate covers those days only. "Stand aside" (unticked ranges) cannot run in MT5: the EA skips those trades instead.

## Every setting

| Section | Setting (as on the indicator) | Variable | Value |
|---|---|---|---|
| EA · EMAs | InpEmaFast | `iFast` | **3** |
| EA · EMAs | InpEmaSlow | `iSlow` | **6** |
| EA · ① setup candle | InpWickMin — pin: long wick >= x range | `iWick` | **0.4** |
| EA · ① setup candle | InpBodyMax — pin: body <= x range | `iBodyMax` | **0.6** |
| EA · ① setup candle | InpNoseMax — pin: short wick <= x range | `iNose` | **0.21** |
| EA · ① setup candle | InpPinDir — pin must point the trade way | `iPinDir` | **False** |
| EA · ① setup candle | InpPinColor — pin body must close the trade way (with PinDir) | `iPinCol` | **False** |
| EA · ① setup candle | InpUsePin — accept pin bars | `iUsePin` | **True** |
| EA · ① setup candle | InpMarubozu — accept a marubozu | `iMaru` | **True** |
| EA · ① setup candle | InpMaruBody — marubozu: body >= x range | `iMaruB` | **0.53** |
| EA · ① setup candle | InpHammer — accept hammers (LONG) | `iHammer` | **True** |
| EA · ① setup candle | InpStar — accept shooting stars (SHORT) | `iStar` | **True** |
| EA · ① setup candle | InpHamRatio — hammer: long wick >= x body | `iHamR` | **2** |
| EA · ① setup candle | InpHamNose — hammer: opposite wick <= x range | `iHamN` | **0.35** |
| EA · ① setup candle | InpMinRangeAtr — candle range >= x ATR(14) (0 = off) | `iMinAtr` | **0.35** |
| EA · ① on the EMA | InpLongRule — LONG setups | `iLRule` | **Both** |
| EA · ① on the EMA | InpShortLine — SHORT setups on | `iSLine` | **Either** |
| EA · ① on the EMA | InpTouchMode | `iTouchM` | **Candle touches** |
| EA · ① on the EMA | InpTouchPips — touch tolerance | `iTouchP` | **1** |
| EA · ① on the EMA | InpLongExitAbove — LONG only when its exit EMA is above the candle | `iLExitAb` | **False** |
| ② ENTRY - the break of the setup candle's high (BUY) / low (SELL) | InpBreakBars — candles allowed for the break | `iBreakB` | **1** |
| ② ENTRY - the break of the setup candle's high (BUY) / low (SELL) | InpBreakPips — break must clear the high / low by | `iBreakP` | **5** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Stop distance beyond the setup candle, in pips (1 pip = $0.10, so 35 = $3.50) | `iSlPips` | **15** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Skip the trade if that stop is more than $X away from the entry (0 = never skip) | `iMaxRisk` | **3** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | BUY · TP1 this many pips BEFORE the EMA (0 = exactly on the EMA) | `iLTpP` | **0** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | SELL · a swing low = a low with X higher candles on each side | `iPivot` | **7** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | SELL · look back at most X candles for that swing low | `iLook` | **32** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | SELL · TP1 this many pips BEFORE (above) the swing low (0 = exactly on it) | `iSTpP` | **0** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | BUY + SELL · TP1 must be at least X pips from the entry (closer: a BUY gets no TP1, a SELL is skipped) | `iMinTp` | **1** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | SELL · skip the trade if the swing low is more than X pips away (0 = off) | `iMaxTp` | **0** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Day close: shut trades still in LOSS this many minutes before the close (0 = off) | `iCloseM` | **1** |
| ⑤ AFTER TP1 - a share is closed at TP1, the rest rides a $ trailing stop | BUY · after TP1 the stop trails $X under the best price | `iLTrail` | **1** |
| ⑤ AFTER TP1 - a share is closed at TP1, the rest rides a $ trailing stop | SELL · after TP1 the stop trails $X over the best price | `iSTrail` | **1.5** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Breakeven (CTC): move the stop to the entry once price has covered X of the way to TP1 (0.75 = 75% · 0 = off) | `iBePct` | **0.95** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | BUY with no TP1 (the exit EMA is not above the entry) · trailing stop X x ATR behind the best price | `iTrAtr` | **0.1** |
| EA · ✖ filters | InpChopEr — skip if the efficiency ratio is below (0 = off) | `iEr` | **0.02** |
| EA · ✖ filters | InpChopErLook — efficiency ratio length | `iErLen` | **16** |
| EA · ✖ filters | InpGapCancel — cancel a waiting setup across the daily close / weekend | `iGap` | **False** |
| ⑤ AFTER TP1 - a share is closed at TP1, the rest rides a $ trailing stop | Close this share at TP1 (0.5 = half · 0.95 = 95% · 1 = everything), the rest keeps running | `iPartial` | **0.65** |
| ⑤ AFTER TP1 - a share is closed at TP1, the rest rides a $ trailing stop | After TP1 the stop is never worse than the entry | `iTp1Be` | **True** |
| EA · partial · money · display | InpLots | `iLots` | **2** |
| EA · partial · money · display | InpBuys | `iBuys` | **True** |
| EA · partial · money · display | InpSells | `iSells` | **True** |
| EA · partial · money · display | InpDrawSkips — also label skipped setups | `iSkips` | **True** |
| CHART ONLY (not in the EA) | Day close (EA reads it from the broker: PXBT 20:59, Axi 23:59 = 4:59 PM New York) | `iCloseT` | **16:59** |
| CHART ONLY (not in the EA) | Day close timezone | `iCloseTz` | **America/New_York** |
| CHART ONLY (not in the EA) | Contract size ($ per $1 per lot) | `iCs` | **100** |
| CHART ONLY (not in the EA) | Spread, $ of price (PXBT XAUUSDp 0.17) | `iSpread` | **0.17** |
| CHART ONLY (not in the EA) | Commission per lot, round trip $ | `iComm` | **0** |
| CHART ONLY (not in the EA) | Show the stats panel | `iPanel` | **True** |
| CHART ONLY (not in the EA) | Write every setup / entry / stop move / exit to the Pine Logs | `iLog` | **False** |
| CHART ONLY (not in the EA) | Draw labels only up to this time (0 = all; TradingView keeps the newest 500 labels) | `iDrawTo` | **0** |
| CHART ONLY (not in the EA) | Show today's trades box (top right) | `iShowRules` | **True** |
| CHART ONLY (not in the EA) | Today's trades box: MT5 server timezone (PXBT = UTC+0) | `iDayTz` | **UTC+0** |
| CHART ONLY (not in the EA) | Detail tags (setups, skips, BE/TP, exit X) only for the last N days - TradingView keeps 500 labels, so the BUY/SELL + EXIT labels of the whole month always fit | `iDetailDays` | **3** |
| CHART ONLY (not in the EA) | Skip a setup candle that touches BOTH EMAs (9 and 50) - not in the EA | `iSkipBoth` | **False** |
| CHART ONLY (not in the EA) | Tight trail: when InpTrailAtr would put the stop above the price, put it 1 pip under the candle close instead of not moving it - not in the EA yet | `iTightTrail` | **False** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | Apply to | `pkApply` | **All trades** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | Start: giveback / $ trail / ATR / candle / EMA only once the trade is this many $ in profit | `pkStart` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ① Breakeven: stop to the entry once $X in profit (0 = off) | `pkBeUsd` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit |     ...and lock this many $ beyond the entry | `pkBeOff` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ② Lock: once $X in profit... (0 = off) | `pkLockAt` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit |     ...lock the stop this many $ beyond the entry | `pkLockUsd` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ③ Ladder (with ②): every further $X of profit raises the lock by $X (0 = off) | `pkStep` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ④ Giveback: keep (100 - X)% of the best profit, e.g. 30 = give back 30% (0 = off) | `pkGive` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ⑤ $ trail: stop this many $ behind the best price (0 = off) | `pkTrail` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ⑥ ATR trail: stop this many x ATR behind the best price (0 = off) | `pkAtr` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ⑦ Candle trail: stop under the lowest low of the last N closed candles (0 = off) | `pkLowN` | **0** |
| ⑥ STOP NEAR PEAK - more ways to move the stop up while in profit | ⑧ EMA trail: stop 1 pip under this EMA of the closed candle (0 = off) | `pkEma` | **0** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | BUY with no TP1 · keep that trailing stop at least $X under the candle close (0 = off) | `pkGap` | **0.1** |
| ⑦ CUT LOSERS EARLY (chart-only) + entry on a candle close | Entry: wick break of the setup candle, or wait for a candle CLOSE beyond it (enter at the next open) | `enMode` | **Wick break (EA)** |
| ⑦ CUT LOSERS EARLY (chart-only) + entry on a candle close | Cut: N candles in a row against the trade while in loss -> close at the next open (0 = off) | `adRunN` | **0** |
| ⑦ CUT LOSERS EARLY (chart-only) + entry on a candle close | Cut: still in loss after N candles -> close at the next open (0 = off) | `adBars` | **0** |
| ⑦ CUT LOSERS EARLY (chart-only) + entry on a candle close | Cut: a candle closes beyond the slow EMA against the trade while in loss -> close at the next open | `adEmaX` | **False** |
| ⑦ CUT LOSERS EARLY (chart-only) + entry on a candle close | Cut: max loss - stop no further than $X from the entry (0 = off, the EA's stop) | `adMaxUsd` | **0** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY · how many recent candles make the range (their low = 0%, their high = 100%) | `rpLook` | **7** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY 0-5% | `rpB00` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 5-10% | `rpB01` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 10-15% | `rpB02` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 15-20% | `rpB03` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 20-25% | `rpB04` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY 25-30% | `rpB05` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 30-35% | `rpB06` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 35-40% | `rpB07` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 40-45% | `rpB08` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 45-50% | `rpB09` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY 50-55% | `rpB10` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 55-60% | `rpB11` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 60-65% | `rpB12` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 65-70% | `rpB13` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 70-75% | `rpB14` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY 75-80% | `rpB15` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 80-85% | `rpB16` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 85-90% | `rpB17` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 90-95% | `rpB18` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 95-100% | `rpB19` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | BUY over 100% | `rpB20` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | Show the diagnostics table: this month's trades grouped by where in the range they entered (BUY from the low, SELL from the high) | `rpDiag` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | When a range is unticked | `rpOff` | **Stand aside while it would have run** |
| COOL-DOWN AFTER AN EXIT (chart-only, not in the EA yet) | No new trade for N candles after a trade closes (0 = off; 2 = the exit candle + the next 2) | `coolN` | **0** |
| COOL-DOWN AFTER AN EXIT (chart-only, not in the EA yet) | ...blocks | `coolDir` | **Same direction** |
| COOL-DOWN AFTER AN EXIT (chart-only, not in the EA yet) | ...only after a WINNING exit | `coolWin` | **False** |
| FAILED ENTRY EXIT (chart-only, not in the EA yet) | Exit when the candle AFTER the entry candle closes beyond it: BUY below its low, SELL above its open/high -> out at the next open | `fxOn` | **False** |
| FAILED ENTRY EXIT (chart-only, not in the EA yet) | ...SELL: the line it must close above | `fxSellRef` | **Never (BUY only)** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | Top-right box: list the days from this date (0 = the last 30 days) | `lsFrom` | **0** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | ...up to this date (0 = now) | `lsTo` | **0** |
| CHART ONLY (not in the EA) | Detail tags (setups, skips, BE/TP, exit X): keep at most N - the rest of TradingView's 500 labels stays for BUY / SELL / EXIT | `iDetMax` | **200** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | Trade export table (bottom centre): every trade with entry / exit times (UTC), for comparing with MT5 - uses the date range above, else all trades | `exOn` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL · how many recent candles make the range (their high = 0%, their low = 100%) | `rpLookS` | **7** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL 0-5% | `rpS00` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 5-10% | `rpS01` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 10-15% | `rpS02` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 15-20% | `rpS03` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 20-25% | `rpS04` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL 25-30% | `rpS05` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 30-35% | `rpS06` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 35-40% | `rpS07` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 40-45% | `rpS08` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 45-50% | `rpS09` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL 50-55% | `rpS10` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 55-60% | `rpS11` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 60-65% | `rpS12` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 65-70% | `rpS13` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 70-75% | `rpS14` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL 75-80% | `rpS15` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 80-85% | `rpS16` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 85-90% | `rpS17` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 90-95% | `rpS18` | **False** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | 95-100% | `rpS19` | **True** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | SELL over 100% | `rpS20` | **False** |
| HIGHER-TIMEFRAME TREND (EA: InpHtfMin / InpHtfEma) | Require trend alignment with | `htReq` | **Off** |
| HIGHER-TIMEFRAME TREND (EA: InpHtfMin / InpHtfEma) | ...trend EMA length on that timeframe | `htEma` | **9** |
| EXIT LAB (chart-only sketch) | Show the EXIT LAB table: this month's SAME entries with ~20 other ways to take profit, BUY and SELL apart | `xDiag` | **True** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | Trades of one month: a centre panel listing every trade (off by default) | `mtOn` | **False** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | ...which month | `mtMonth` | **This month** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | TP1 METHOD | `tpMode` | **Partial: close a share at a fixed $ target, trail the rest** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Fixed $ target / Partial · BUY: TP1 $X above the entry | `tpFixB` | **2.5** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Fixed $ target / Partial · SELL: TP1 $X below the entry | `tpFixS` | **2.5** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Fibonacci · TP1 at X% of the setup candle's range (161.8 = the EXIT LAB row) | `tpFib` | **161.8** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Partial · close this share at the target (0.5 = half) | `tpPart` | **0.1** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Partial · the rest trails $X behind the best price | `tpPartTr` | **5.6** |
| ④ TAKE PROFIT (TP1) - pick the TP1 METHOD at the bottom of this section. Normal: BUY: the touch of the OTHER EMA (set up on the fast EMA -> TP1 at the slow one, set up on the slow -> at the fast) · SELL: the last swing LOW (support) below the entry | Fixed $ / Fibonacci / Partial · target not far enough beyond the entry | `tpNoFix` | **Use the normal TP1** |
| TOP / BOTTOM FILTER - which part of the recent candles' range may a trade enter in | ...with Pause: no new trade for N candles after a trade is skipped in an unticked range | `rpPause` | **1** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | Debug: event export table (every setup and skip with its reason, UTC) - for the compare page's sync check | `skEx` | **True** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | ...events from (0 = the last 300) | `skFrom` | **1792181880000** |
| TRADES BOX (top right) AND THE MONTH'S TRADES (chart-only) | ...events up to (0 = now) | `skTo` | **1792182360000** |
| ② ENTRY - the break of the setup candle's high (BUY) / low (SELL) | No new trades while the broker is closed (Blueberry: 4:59 PM to 6:01 PM New York) | `bcOn` | **True** |
| ② ENTRY - the break of the setup candle's high (BUY) / low (SELL) | ...closed from (New York time) | `bcFrom` | **16:59** |
| ② ENTRY - the break of the setup candle's high (BUY) / low (SELL) | ...open again at (New York time) | `bcTo` | **18:01** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Stop loss type | `iSlMode` | **Pips beyond the setup candle** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | ...ATR multiple (with 'ATR x from the entry') | `iSlAtrM` | **2.5** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | Re-entry after a stop loss: when the ORIGINAL stop is hit, re-arm the same setup and re-enter if price breaks back through its break level | `reOn` | **True** |
| ③ STOP LOSS - it starts X pips beyond the setup candle: a BUY's stop under its LOW, a SELL's stop over its HIGH | ...re-arm window: candles after the stop-out | `reBars` | **18** |

## The same settings as EA inputs (Saad_strategy_1min)

```
InpEmaFast=3
InpEmaSlow=6
InpWickMin=0.4
InpBodyMax=0.6
InpNoseMax=0.21
InpPinDir=false
InpPinColor=false
InpUsePin=true
InpMarubozu=true
InpMaruBody=0.53
InpHammer=true
InpStar=true
InpHamRatio=2
InpHamNose=0.35
InpMinRangeAtr=0.35
InpTouchPips=1
InpLongExitAbove=false
InpBreakBars=1
InpBreakPips=5
InpSlPips=15
InpMaxRiskUsd=3
InpLongTpPips=0
InpSwingPivot=7
InpSwingLook=32
InpShortTpPips=0
InpMinTpPips=1
InpMaxTpPips=0
InpCloseLossMins=1
InpLongTrailUsd=1
InpShortTrailUsd=1.5
InpBeTpPct=0.95
InpTrailAtr=0.1
InpChopEr=0.02
InpChopErLook=16
InpGapCancel=false
InpPartialPct=0.65
InpTp1Be=true
InpLots=2
InpBuys=true
InpSells=true
InpLockAtUsd=0
InpLockUsd=0
InpTrailGapUsd=0.1
InpCutRunN=0
InpRangeLook=7
InpRangeLookS=7
InpHtfEma=9
InpChartSpread=0.17
InpTpFixUsdB=2.5
InpTpFixUsdS=2.5
InpTpFibPct=161.8
InpTpPartPct=0.1
InpTpPartTrailUsd=5.6
InpSlAtrMult=2.5
InpReEntry=true
InpReEntryBars=18
InpLongRule=2
InpShortLine=2
InpTouchMode=0
InpTpMode=3
InpTpNoFixSkip=false
InpHtfMin=0
InpSlMode=0
InpRangeMin=0
InpRangeMax=0
InpRangeMinS=0
InpRangeMaxS=0
InpBandsB=111101110000100010001
InpBandsS=111110001101000011010
InpClosedRetryMins=0
InpBandPauseBars=0
InpLogCsv=false
```
