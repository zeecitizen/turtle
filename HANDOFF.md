# Turtle Trader Desk — Full Session Handoff
Last updated: 2026-04-02 (Session 34 end)
For: Claude on new computer — read this first before anything else.

---

## What This Project Is
An automated Gold (XAUUSD) scalping system. Pine Script v5 indicator on TradingView 1m chart.
Signals fire via `alert()` → TradingView webhook → PineConnector EA → MT5 broker (Blueberry Markets demo).
One strategy only: **UHV Breakout** (Ultra High Volume candle breakout).

---

## The Trading Logic (plain English)
1. Find the highest-volume candle in a retracement (the "UHV candle")
2. When price breaks out above (bull) or below (bear) that candle, fire a signal
3. SL = below the breakout candle wick (Breakout Wick mode)
4. TP = 2× SL distance (R:R Ratio 2 mode)
5. BE = move SL to lock in 33% of TP when price reaches 33% of TP distance
6. Invalidation = if a 1-min candle closes BACK inside the UHV candle range, exit early

---

## Current Live Setup (Blueberry Markets Demo)
- Broker: Blueberry Markets, MT5, demo account
- Symbol: XAUUSD (no suffix needed)
- PineConnector License ID: 8778286989525
- Signal format confirmed working:
  `8778286989525,buy,XAUUSD,vol_lots=0.03,sl_pips=50,tp_pips=8,...`
- Close format confirmed working:
  `8778286989525,closelong,XAUUSD` (buys) / `8778286989525,closeshort,XAUUSD` (sells)

---

## Architecture (turtle.pine)
- **~2300 lines**, Pine Script v5
- Inputs: lines 1–135
- Types/vars: 136–300
- Strategy logic + signal fire: 300–1480
- Trade monitoring loop (SL/TP/BE/Invalidation checks): 1480–2000
- Stats + fDP() panel: 2000–2340
- Alerts/plots: 2340+

### Key arrays (always in sync, pushed together at signal fire):
- `_tEn, _tSl, _tTP` — entry/SL/TP prices
- `_tEL` — lots; `_tBl` — bull/bear; `_tTy` — "uhv"
- `_tSH, _tTH` — SL-hit / TP-hit flags
- `_tBE` — breakeven triggered flag
- `_tIL` — invalidation level per trade (UHV candle high for bull, low for bear)
- `_tEB` — entry bar index; `_tN` — trade number; `_tLbl` — signal label ref

### Key inputs:
- `pPip = 0.10` — XAUUSD pip size (CRITICAL — must be 0.10, not 0.01)
- `pcBrkPip = 0.10` — PineConnector broker pip size
- `uBEon` — breakeven ON/OFF; `uBEPct = 10` — trigger at 10% of TP (early protection)
- `uBELkTP = false` — SL moves to entry+spread only (not locked at trigger — lets runners breathe)
- `useInvalidation = true` — invalidation exit ON
- `iExHSL = 50` — hard disaster SL sent to MT5 (50 pips = ~$20 max disaster loss at typical lots)
- `iExOff = 0.3` — $0.30 tolerance buffer for invalidation trigger
- `uTVOn = true` — Tick Velocity Filter ON; `uTVK = 1.2` — 1.2× threshold; `uTVN = 20` — 20-bar SMA
- `aTS = true` — avoid trading when trend is shifting
- `uT1 = 10.0` — R:R Ratio 10 (runner mode)
- `pcTTrig = 100` — trail activates after 100 pips profit; `pcTDist = 40` — 40-pip leash

---

## Session 31 Changes (2026-03-31)

### 1. All 33 live settings baked as code defaults
Settings import (CSV) was intermittently failing in TradingView. All live values now match code defaults exactly — fresh indicator load works without import. See `settings.md` for the full list.

### 2. iExHSL reduced 150 → 50 pips
Old 150-pip hard SL was causing -$60/-$75 disaster losses on fast moves. Reduced to 50 pips (~$20 max disaster loss at typical lots). Safe to do because current structural TPs are only 8-14 pips (much narrower than the old 48-63 pips that originally forced the 50→150 change).

### 3. Hard SL simulation block added to Pine
**Root cause fixed**: Pine stats showed 100% win rate while MT5 had real losses. The gap was because:
- Pine used structural wick SL (wide) for P&L tracking
- MT5 used iExHSL=150 pip hard SL (narrow) for actual execution
- Fast moves blew through $60+ before any bar closed → MT5 closed as loss, Pine showed as open/win

**Fix**: Added a hard SL simulation block in the trade monitoring loop (inserted between the invalidation exit check and the wick SL check, ~line 1782):
- Only runs when `useInvalidation = true`
- Computes `_hardSLPrice = entry ± iExHSL * pPip`
- If price touches this level, marks trade as closed with 🔴 Hard SL label
- Updates all stats arrays exactly like a real loss (P&L, streaks, durations, uPnL, etc.)
- The downstream wick SL check guards with `not _hardSLExited`

Result: Pine stats panel now reflects true realized P&L matching MT5 reality.

---

## Critical Bugs Fixed (know these — they may resurface)

### Bug 1: pPip=0.01 (MOST DANGEROUS)
- **What happened**: pPip was set to 0.01 instead of 0.10
- **Effect**: `sl_pips = round(iExHSL × 0.01 / 0.10) = round(150 × 0.1) = 15` instead of 150
- **Symptom**: MT5 places SL only 1.5pts from entry → instant stop-outs
- **Fix**: "MT5 pip size" input must be 0.10 for XAUUSD
- **Rule**: pPip and pcBrkPip must BOTH be 0.10

### Bug 2: closebuy/closesell invalid
- **What happened**: PineConnector v3 doesn't accept `closebuy`/`closesell`
- **Effect**: "Invalid Command" in PineConnector dashboard, trade never closed
- **Fix**: use `closelong`/`closeshort` instead
- **Verified**: dummy account test confirmed closelong reaches MT5 Experts tab

### Bug 3: Hard SL = TP distance (1:1 R:R trap)
- **What happened**: iExHSL=50 pips, but structural TPs were also ~48-63 pips
- **Effect**: wins ~$15, losses ~$15 → strategy depends purely on win rate
- **Root cause**: 50-pip hard SL fires before 1-min bar close in fast moves
- **Fix**: iExHSL=150 → hard SL is now truly a disaster backstop, not normal exit
- **Result expected**: losses drop to -$3 to -$4 (invalidation exit fires first)

### Bug 4: BE direction wrong (historical, fixed session 28)
- SL was placed in profit zone instead of loss zone → fake 98% win rate
- Fixed: `_bull ? _en - uSpread : _en + uSpread`

### Bug 5: TradingView alert caching
- Changing indicator settings does NOT update existing alert webhooks
- Must DELETE and RECREATE the alert after any settings change
- Labels on chart update (Pine reruns), but webhook payload is frozen at alert creation

---

## The Invalidation Exit (most important recent feature)
When a trade is open and a 1-min candle CLOSES back inside the UHV candle range:
1. Pine sets `_tSH[i] = true` (marks as closed)
2. Sends `closelong` or `closeshort` to PineConnector via `alert()`
3. Pine label shows ⚡ for loss, ✅ for profit
4. MT5 receives the close command and closes the position

**Hard SL role**: MT5 has a 150-pip hard SL as disaster insurance.
- If connection fails → hard SL protects the account
- If price spikes >150 pips in <60 seconds (rare news event) → hard SL catches it
- Normal exits: invalidation fires at bar close (primary), or BE locks in profit, or TP hit

**Post-BE deactivation**: once breakeven fires (`_tBE[i]=true`), invalidation is disabled.
The trade is already protected at BE level — no need to exit early.

**Verified pipeline** (2026-03-27):
PineConnector dashboard showed: "Attempt to close Order #47739821" ✅

---

## PineConnector Signal Details
Full signal format:
```
8778286989525,buy,XAUUSD,vol_lots=0.03,sl_pips=150,tp_pips=54,
spread=30,betrigger=18,beoffset=18,traildist=15,trailtrig=25,trailstep=5,
comment=0.03#sl=150#tp=54#sd=30#bt=18#bo=18#td=15#tt=25#ts=5
```

Key params:
- `sl_pips=150` — hard disaster SL (wide — NOT the Pine wick SL)
- `tp_pips=N` — structural TP from Pine (varies per trade: 43-200+ pips)
- `betrigger=N` — pips profit to trigger BE (= tp_pips × 0.33)
- `beoffset=N` — same as betrigger when uBELkTP=true (locks SL at trigger price)
- `traildist=15, trailtrig=25, trailstep=5` — trailing stop settings

Close commands:
- `8778286989525,closelong,XAUUSD` — close buy position
- `8778286989525,closeshort,XAUUSD` — close sell position

---

## Stats Panel (16 rows)
- Row 0: Header + signal integrity
- Row 1: STANDING BY / SETUP IN PROGRESS / SIGNAL FIRED
- Row 2: Trend direction + strength + next signal ETA
- Row 3: TODAY divider
- Row 4: Today P&L + balance (large font, green)
- Row 5: UHV subtotals + avg trade duration
- Row 6: Trade count + streak
- Row 7: Last hour P&L + next hour EV
- Row 8: STRATEGIES divider
- Rows 9-10: UHV W/L%, all-time, today, avg win/loss
- Row 11: ALL-TIME divider
- Row 12: All-time P&L + accuracy + EV
- Row 13: To-double + washout + yesterday %
- Row 14: OPTIMIZER & TOOLS divider
- Row 15: Top 2 optimizer recommendations

---

## No-Trade Windows
4 checkboxes to block signals during dangerous UTC hours:
- ntW1: 21:00–23:00 UTC (NY Rollover — spreads spike)
- ntW2: 23:00–03:00 UTC (Late Asia lull)
- ntW3: 04:00–07:00 UTC (Pre-London trap)
- ntW4: 19:00–21:00 UTC (Volume fade)
All OFF by default (London/NY session trades unaffected).

---

## Live Performance (last seen 2026-03-27)
- 82% win rate, 1150+ trades all-time
- EV $9.24/trade (Pine simulation)
- Today peak: +$686 in one session
- Avg trade duration: 1.3 min
- ~89 signals/day

---

## Session 32 Changes (2026-04-01)

### 1. Tick Velocity Filter compile error fixed
`_uIOE` was used on line 1475 before it was declared on line 1478. Fixed by replacing `_uIOE` with inline `uOE == "Instant at Breakout"` — semantically identical, no forward reference.

### 2. Tick Velocity Filter confirmed working + enabled
Tested at multipliers 1.0, 1.05, 1.1, 1.2, 3.0. Results:
- 1.2× is the confirmed sweet spot: 64% signal reduction, win rate 23%→27%, EV $9.95→$14.10/trade
- Quality cliff exists between 1.1 and 1.2: trades filtered in that band only earn $5.10/trade vs $14.10 for 1.2+ trades
- Default set to ON, multiplier 1.2, lookback 20

### 3. uT1 default corrected: 2.0 → 10.0 (R:R Ratio)
Code was still defaulting to 2.0 even though live setting has been 10.0 since Session 31.

### 4. Avoid trading when trend is shifting → ON
Zee observed strategy was catching sells right at downtrend exhaustion / trend reversal points. Turning this filter ON suppresses signals when trend momentum is fading.

### 5. Runner mode confirmed working live
Trade #48010319: sell 0.04 lots at 4692.12, trail activated at 100 pips, trail SL followed price down 4683.43→4682.34, closed +$39.08 when 1-pip bounce hit trail. Without runner setup would have been BE stop at -$1.50.

## Session 33 Changes (2026-04-01)

### 1. Three invalidation exit modes added (`iExMode`)
New input with three options (default preserved as "UHV Range"):
- **UHV Range** — original behaviour: close re-enters the full UHV candle range
- **UHV Midpoint** — VSA rule: close crosses `(uhv_high + uhv_low) / 2`. If price cannot hold above the UHV candle's halfway point, the effort-vs-result test fails — the candle was absorption not accumulation. **Now the live default.**
- **Breakout Body** — Prop-firm structural failure rule: close crosses the midpoint of the breakout candle body `(open + close) / 2`. If the breakout candle loses >50% of its body, the structure has failed regardless of the UHV candle.

Two new per-trade arrays pushed at signal fire: `_tILM` (UHV midpoint) and `_tBrkMid` (breakout body midpoint). Exit label tags the mode when non-default fires e.g. `[UHV Midpoint]`.

### 2. Signal label stale P&L fix (`fPTS` removed)
`fPTS(_uPT)` was frozen into label text at `label.new()` time. After midnight daily reset zeroed `_uPT`, chart labels still showed yesterday's P&L contradicting the live panel. Removed from all three label-building paths (bull IOE, bear IOE, deferred block).

### 3. Pine/MT5 SL mismatch fixed (`_effectiveSL`)
When `useInvalidation=true`, the wick SL check now uses `_effectiveSL = entry ± iExHSL * pPip` instead of the structural wick `_sl`. A wick through the structural SL level no longer triggers a Pine "SL Hit" when MT5's 120-pip hard SL hasn't been reached.

### 4. All live settings baked as code defaults
21 values updated to match live screenshots (see settings.md for full list). Key changes vs Session 32:
- `rULV`: false → true (breakout candle must have lower volume than UHV)
- `uOE`: Instant at Breakout → Candle Close
- `uPBD`: 5.0 → 0.0 (no pre-breakout offset)
- `uRp`: 1% → 4% capital risk per trade
- `uT1`: 10 → 7 R:R
- `uSBf`: 0.7 → 0.4 SL offset
- `iExHSL`: 50 → 120 pips hard SL
- `iExMode`: "UHV Range" → "UHV Midpoint"
- `uTVOn`: true → false (Tick Velocity Filter OFF)
- `ntW4`: false → true (block 19:00–21:00 UTC)
- `bRWW`: true → false (wick trigger OFF)
- `pcSL`/`pcTP`: Price → Pips format

### 5. Trail stop win counting verified
Profitable trail stops are correctly counted as wins in all panel metrics. `_trWin = _trPnl > 0` drives both `_wC` and `_uWn` increments. `fDP()` win rate is P&L-sign-based from `_tPA` array — the 🏃 emoji is cosmetic only.

### 6. Script reorder — closelong alert priority fix
**Root cause of -$240 and -$168 losses**: Both were exactly 120 pips × lots = hard SL hit. Pine showed smaller losses (invalidation fired and drew labels), but MT5 never received closelong.

**Why**: TradingView delivers **ONE `alert()` per bar execution**. With Candle Close mode, the entry signal (STEP 5, ~line 1511) and the invalidation closelong (~line 1793) competed on the same bar-close execution. The entry `alert()` fired first → TradingView dropped the closelong → MT5 never closed → price kept moving → hit 120-pip hard SL.

**Fix**: Moved the entire `// TRADE MONITORING` block to run **before** STEP 5 (BREAKOUT). Closelong/closeshort alerts now always fire before any entry signal on the same bar. Entry may occasionally drop on the same bar as a close — acceptable tradeoff.

**`_uIOE` forward reference**: After reorder, `_uIOE` (declared inside STEP 5) was not yet defined. Fixed by inlining `uOE == "Instant at Breakout"` as `_isIOE` — same pattern as Session 32 Tick Velocity Filter fix.

### 7. MAE (Max Adverse Excursion) emergency tick-based stop
Added two new inputs and a tick-based emergency close as the **first** check in the monitoring loop:

```pine
uMAEPips = input.int(60,   '... Emergency MAE stop: close if trade moves X pips against entry (0=off)', ...)
uMAEDol  = input.float(40.0, '... Emergency MAE stop: close if unrealised loss exceeds $X (0=off)', ...)
```

**How it works**:
- Runs on every realtime tick (NO `barstate.isconfirmed` gate) — fires immediately when price moves
- `_maeAdv` = pips adverse: `_bull ? (entry - close) / pPip : (close - entry) / pPip`
- `_maePnl` = unrealised P&L: `(close - entry) × lots × contractSize` (negative = loss)
- Fires if `_maeAdv >= uMAEPips` OR `_maePnl <= -uMAEDol`
- Disabled once breakeven fires (`_tBE[i] = true`) — trade is already protected
- Sets `_tSH[i] = true`, updates all stats, draws 🚨 label, fires `closelong`/`closeshort`
- All downstream checks (invalidation, hard SL, trail, wick SL) gated with `not _maeExited`

**Expected improvement**: -$240 loss → max ~$120 (60 pips × 0.20 lots × $100). MAE fires as first alert in the loop, combined with script reorder means it wins the TradingView alert slot before any entry signal.

**Defaults**: `uMAEPips = 60`, `uMAEDol = 40.0`

### 8. Kill Timer — max time in trade
New `uKillSec` input (default 90, 0 = off). Closes any trade still open after 90 seconds of wall-clock time.

**Logic**: `(timenow - array.get(_tFT, _ti)) >= uKillSec * 1000` — uses `_tFT` (already stored at signal fire). Tick-based (no `barstate.isconfirmed` gate). Disabled once BE fires.

**Position in loop**: MAE → **Kill Timer** → DLL Hard Shutdown → Partial TP → INVALIDATION → Hard SL → Trail → Wick SL.

**Why 90 seconds**: Gold moves within 5–20 seconds on valid entries. Stagnant past 90s = drifting into noise or next volatility spike.

**Label**: `⏱ #N Kill Timer 93s — -$X.XX` (loss) or `✅ #N Kill Timer 91s — +$X.XX` (win)

### 9. Risk Management group (`gRM`)
Three new entry-blocking filters, all OFF by default:

**Volatility Blocker** (`vbOn`, `vbATR=4.0`, `vbSprd=false`, `vbSprdK=3.0`): blocks entries when `ta.tr(true) / ta.atr(14) > vbATR` (current bar true range is chaotic relative to recent baseline). Optional synthetic-spread sub-check (`vbSprd`). Prevents entering into range explosions.

**Max Trades Per Hour** (`mtphOn`, `mtphMax=3`, `mtphGap=5`): counts trades fired within the rolling 60-minute window (uses `_tFT` array). Blocks new entries if `_mtphCount >= mtphMax` OR gap since last trade `< mtphGap` minutes. Note: historical replay accuracy limited (uses real-time `timenow`).

**Daily Loss Limit** (`dllOn`, `dllSoft=2.0%`, `dllHard=5.0%`): soft limit blocks new entries only; hard limit triggers `_dllHardBlock` which closes ALL open trades (does NOT respect `_tBE` — entire book closes when day is lost) and blocks further entries. Dollar thresholds computed from `iMon`.

Both `_bBrk` and `_beBrk` conditions updated: `and not _vbBlock and not _mtphBlock and not _dllBlock` appended before the timing gate.

### 10. Partial Take-Profit + Runner
New inputs `ptpOn` (default false), `ptpPips=40`, `ptpPct=50.0%`. Fires once per trade (one-shot `_tPTP` flag) when profit reaches `ptpPips` pips.

**Mechanics**:
- Closes `ptpPct`% of position via `closelong`/`closeshort,vol_lots=X`
- Sets `_tBE[i]=true` and moves SL to `entry ± spread` (runner protected at BE)
- Updates `_tEL[i]` to remaining lots
- Edge case: if remaining lots `< mLot`, closes entire position (`_ptpFull=true`, sets `_tSH`)
- After partial TP fires, invalidation naturally disables (already guarded by `not _tBE`)

**Stats**: full stats update at partial close (increments `_cTr`, `_wC` etc.) — trade count slightly inflated but P&L accurate. Runner's final close then counts its remaining lots.

**Label**: `💰 #N Partial TP +40p — +$X.XX (50%) → Runner at BE`

**New array**: `_tPTP` (bool) — pushed `false` at signal fire alongside all other trade arrays.

## What To Work On Next
1. **Recreate TradingView alert** — script was significantly modified; must delete and recreate alert or closelong/kill timer/MAE changes won't take effect
2. **Verify closelong commands appear** in PineConnector dashboard (previously zero closelong commands seen)
3. **Monitor UHV Midpoint invalidation live** — compare exit quality vs old UHV Range mode
4. **Test Partial TP live** — suggested first run: ptpPips=40, ptpPct=50%; compare daily P&L over one week vs no partial TP
5. Consider switching from Blueberry demo to Blueberry live or Exness Raw Spread (saves ~$4.60/lot)
6. Token reduction pass on turtle.pine (unused fCT function, unused _strat/_num/_bits params in fPC)
7. Trail stop width tuning — consider widening pcTDist 40→60/80 pips to let runners breathe

