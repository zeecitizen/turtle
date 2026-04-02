# Turtle Trader Desk — Change Log

## 2026-04-02 — Session 35: 7 New Risk Management Features + Trail Tuning + Structural SL

### 1. Trail stop retuned — 60/20/3 (trigger/distance/step)
Previous settings (100/40/5) meant the trail rarely armed before MAE or kill timer fired. Reduced to `trailtrig=60, traildist=20, trailstep=3`. Confirmed live: trade #48189622 captured +$112.68 in 1m49s with trail arming correctly at +60 pips.

### 2. Structural SL — Layer 4 logic-based exit
When `useInvalidation=true`, MT5 holds a 120-pip hard SL but Pine had no way to close the trade at the structural wick level (typically 20–40 pips). Added a dedicated `STRUCTURAL SL` block:
- Bar-close only (`barstate.isconfirmed`) — prevents false exits from intra-bar wick sweeps
- Fires when `close <= _sl` (bull) or `close >= _sl` (bear)
- Sends `closelong`/`closeshort` to MT5
- Disabled once `_tBE[i]=true`
- `_effectiveSL` override in wick SL block is untouched — wick block still simulates 120-pip hard SL for Pine stats alignment

### 3. Spread Spike Filter (`ssOn`, `ssPips=50`)
Pre-entry block. If the current 1-minute candle range exceeds `ssPips` pips, the entry is blocked. Candle range = (high - low) / pPip. Added `and not _ssBlock` to both `_bBrk` and `_beBrk`.

### 4. Volatility Collapse Exit (`vcOn`, `vcFact=0.6`)
Bar-close monitoring exit. ATR(14) is recorded at entry in new `_tATE` array. If current ATR(14) drops below `vcFact × _tATE`, the breakout momentum has evaporated — close the trade.

### 5. Opposite UHV Candle Exit (`ouOn`, `ouK=2.0`)
Bar-close monitoring exit. If a candle closes in the opposite direction to the trade AND its volume is ≥ `ouK × SMA(volume,20)`, institutional flow has flipped — close the trade.

### 6. Breakout Failure Pattern Exit (`bfOn`, `bfBars=3`, `bfPips=5.0`)
Bar-close monitoring exit. Uses new `_tBFX` bool array (one-shot extension flag). If price fails to extend `bfPips` beyond the breakout level within `bfBars` bars AND closes back inside the level — classic bull/bear trap confirmed, close the trade. Once extension is confirmed, this exit never fires.

### 7. Volume Drop Exit (`vdOn`, `vdFact=0.5`)
Bar-close monitoring exit. Fires on `bar_index > _entryBar + 1` (skips entry bar). If volume < `vdFact × SMA(volume,20)` — institutions aren't following through, close.

### 8. Micro-Structure Break Exit (`msOn`, `msBuf=3.0`, `msLb=3`)
Bar-close monitoring exit. Uses `ta.lowest(low, msLb)` / `ta.highest(high, msLb)` to find the most recent post-entry swing. If close breaks `msBuf` pips past that swing — micro-structure has cracked, close.

### 9. Time-of-Day Kill Switch (`ntKill=false`)
Tick-based monitoring exit. When a no-trade window begins (`_ntKillFire = ntKill and _inNtWindow`), force-close ALL open trades immediately. Does not respect `_tBE` — window boundary is an absolute override. Complements existing no-trade blocks which only prevented new entries.

### 10. New arrays
- `_tATE float[]` — ATR(14) at entry bar (Volatility Collapse Exit)
- `_tBFX bool[]` — breakout extension confirmed one-shot flag (Breakout Failure Exit)

### 11. Monitoring loop exit priority (full updated stack)
```
MAE → Kill Timer → DLL Hard → Partial TP → Invalidation → Structural SL
→ Opposite UHV → BF Pattern → Vol Collapse → Vol Drop → Micro-Structure
→ ToD Kill → Hard SL Sim → Trail → Wick SL → Breakeven → TP
```

### 12. Documentation
Created `risk-management.md` — beginner-friendly deep dive into all 17 exit/protection layers with trading context, VSA theory, and architecture notes.

---

## 2026-04-02 — Session 34: Kill Timer, Risk Management Group, Partial TP + Runner

### 1. Kill Timer (`uKillSec = 90`)
New tick-based max-time-in-trade kill switch. If a trade is still open after `uKillSec` seconds of wall-clock time, it is closed immediately.

```pine
uKillSec = input.int(90, '... Kill timer: close trade if still open after X seconds (0 = off)', group=gU)
```

**How it works**: `(timenow - array.get(_tFT, _ti)) >= uKillSec * 1000` — uses existing `_tFT` array (wall-clock ms at signal fire). No `barstate.isconfirmed` gate — fires every tick. Disabled once `_tBE[i]=true`.

**Position in monitoring loop**: MAE → **Kill Timer** → DLL Hard Shutdown → Partial TP → Invalidation → Hard SL → Trail → Wick SL.

**Rationale**: Valid Gold entries resolve within 5–20 seconds. 90 seconds is the pro scalper sweet spot — keeps runners but cuts dead trades before they drift into the next news spike.

**Label**: `⏱ #N Kill Timer 93s — -$X.XX` (loss) or `✅ #N Kill Timer 91s — +$X.XX` (win)

### 2. Risk Management group (`gRM`) — three new entry filters

**Volatility Blocker** (`vbOn`, `vbATR=4.0`, `vbSprd=false`, `vbSprdK=3.0`): suppresses entries when `ta.tr(true) / ta.atr(14) > vbATR`. Catches range explosions independent of volume. Optional spread sub-check: also block when `high - low > vbSprdK × atr(14)`.

**Max Trades Per Hour** (`mtphOn`, `mtphMax=3`, `mtphGap=5`): rolling 60-minute window — counts how many entries are in `_tFT` with `timenow - entry_time <= 3_600_000`. Blocks new entries if at or above `mtphMax` OR if gap since last trade `< mtphGap` minutes.

**Daily Loss Limit** (`dllOn`, `dllSoft=2.0%`, `dllHard=5.0%`): soft limit (`_dllSoftBlock`) blocks new entries only. Hard limit (`_dllHardBlock`) closes ALL open positions regardless of `_tBE` status AND blocks further entries. Dollar thresholds: `_pT <= -(dllSoft/100 × iMon)`. Hard shutdown fires as third check in monitoring loop (after MAE and kill timer).

All three new variables (`_vbBlock`, `_mtphBlock`, `_dllBlock`) appended to both `_bBrk` and `_beBrk` breakout conditions: `and not _vbBlock and not _mtphBlock and not _dllBlock`.

### 3. Partial Take-Profit + Runner (`ptpOn`, `ptpPips=40`, `ptpPct=50.0`)
Closes `ptpPct`% of position at `ptpPips` pips profit, then lets the remainder run with breakeven protection.

**Mechanics**:
- Tick-based, fires once per trade (one-shot `_tPTP` bool array, pushed `false` at signal fire)
- Computes close lots: `math.max(math.round(_ptpLots * ptpPct / 100.0, 2), mLot)`
- Remaining lots `< mLot` → closes full position (`_ptpFull=true`)
- On partial close: sets `_tBE[i]=true`, moves SL to `entry ± spread`, updates `_tEL[i]` to remaining lots
- Alert format: `pLid + ",closelong," + pSym + ",vol_lots=X.XX"` — PineConnector partial close syntax
- After partial TP, invalidation is naturally disabled for the runner (`_tBE` guard)

**Stats**: full stats update at partial close (P&L accurate; trade count slightly inflated — runner's final close counts remaining lots separately).

**New array**: `_tPTP bool[]` — added alongside all other trade arrays.

**Label**: `💰 #N Partial TP +40p — +$X.XX (50%) → Runner at BE`

---

## 2026-04-01 — Session 33: Three Invalidation Modes, SL Mismatch Fix, Script Reorder, MAE Stop

### 1. Three invalidation exit modes (`iExMode`)
New `input.string` with options `["UHV Range", "UHV Midpoint", "Breakout Body"]`. Default changed to **UHV Midpoint** in live settings.

- **UHV Range** (original): close re-enters the full UHV candle range
- **UHV Midpoint** (VSA rule): close crosses `(uhv_high + uhv_low) / 2` — if price can't hold above the UHV candle halfway point, the candle was absorption not accumulation
- **Breakout Body** (prop-firm rule): close crosses `(breakout_open + breakout_close) / 2` — if the breakout candle loses >50% of its body, structure has failed

Two new per-trade arrays: `_tILM` (UHV midpoint), `_tBrkMid` (breakout body midpoint). Both pushed at signal fire alongside existing `_tIL`. Exit label appends `[UHV Midpoint]` or `[Breakout Body]` tag when non-default mode fires.

### 2. Stale `fPTS` removed from signal labels
`fPTS(_uPT)` was frozen into label text at `label.new()` creation. After midnight daily reset zeroed `_uPT`, labels still showed yesterday's P&L. Removed `"\n" + fPTS(_uPT)` from all three label-building paths (bull IOE ~line 1554, bear IOE ~line 1617, deferred block ~line 1636).

### 3. `_effectiveSL` — Pine/MT5 SL alignment
When `useInvalidation=true`, the wick SL check block now computes:
```pine
float _effectiveSL = useInvalidation ? (_bull ? entry - iExHSL * pPip : entry + iExHSL * pPip) : _sl
```
Structural wick crossings are ignored when invalidation is on — Pine now only simulates SL at the same price MT5 uses (hard SL pips). The hard SL simulation block still fires first; the wick block is a clean fallback for non-invalidation mode.

### 4. 21 code defaults updated to match live settings
Key changes: `rULV` true, `uOE` Candle Close, `uPBD` 0, `uRp` 4%, `uT1` 7, `uSBf` 0.4, `iExHSL` 120, `iExMode` UHV Midpoint, `uTVOn` false, `uTVN` 5, `aTS` false, `aTSU` true, `rngTh` 14, `ntW4` true, `bRWW` false, `pcSL`/`pcTP` Pips. Full list in settings.md.

### 5. Script reorder — closelong alert priority fix
**Root cause of -$240 / -$168 losses**: TradingView delivers ONE `alert()` per bar execution. With Candle Close mode, entry signal (STEP 5) and invalidation closelong competed on the same bar-close execution. Entry fired first → closelong was silently dropped by TradingView → MT5 never received the close command → trade ran to 120-pip hard SL.

**Fix**: Moved entire `// TRADE MONITORING` block to before STEP 5 (BREAKOUT). Closelong/closeshort now always wins the alert slot. `_uIOE` forward reference resolved by inlining `uOE == "Instant at Breakout"` as `_isIOE` (same pattern as Session 32 Tick Velocity Filter fix).

Verified: "There are no closelong commands" in PineConnector log confirmed the bug. After reorder, closelong should appear in every invalidation/MAE exit.

### 6. MAE (Max Adverse Excursion) emergency tick-based stop
Added two new inputs and emergency close as the **first** check in the monitoring loop (no `barstate.isconfirmed` gate — fires on every realtime tick):

```pine
uMAEPips = input.int(60,    '... close if trade moves X pips against entry (0=off)', group=gU)
uMAEDol  = input.float(40.0, '... close if unrealised loss > $X (0=off)', group=gU)
```

Logic: `_maeAdv >= uMAEPips` (pip excursion) OR `_maePnl <= -uMAEDol` (dollar loss) → sets `_tSH[i]=true`, updates P&L/streak/duration stats, draws 🚨 label, fires `closelong`/`closeshort`.

Disabled once BE fires (`_tBE[i]=true`). All downstream checks (invalidation, hard SL, trail, wick SL) gated with `not _maeExited`.

Combined with script reorder: MAE fires tick-by-tick as the first alert in the loop, before any entry signal can compete. Expected improvement: -$240 → max ~$120 (60 pips × lots).

---

## 2026-03-20 — Alert = Label (1:1 Parity), Settings Backup, Architecture Notes

### Context for Claude resuming on another machine

This is a Pine Script v5 trading indicator (`turtle.pine`, ~2670 lines) running on TradingView.
It sends signals to MT5 via PineConnector webhooks.
Active strategy: **UHV (Ultra High Volume) Breakout** on 1-minute XAUUSD chart.
Two indicator instances run simultaneously — one per account (main: $869, small: $67).

---

### Change 1 — Alert = Label (1:1 parity) for UHV signals

**Problem being solved:**
Previously, a Pine Script signal label was created whenever conditions were met AND the trade
was within margin limits (`_safe = true`), regardless of whether the alert actually fired.
The alert gate (`uAlGt`) could block the actual MT5 alert while the label still appeared —
causing the chart to show signals that MT5 never received. This made the "98% win rate"
stat misleading (counted labels, not actual MT5 alerts).

**The fix (both bull `if _bBrk` and bear `if _beBrk` blocks):**

- Label creation, polyline, sCH highlight boxes — all moved INSIDE `if _gateOkU` / `if _gateOkUe`
- Rule enforced: **IF alert fires → draw label. IF alert gated/blocked → draw nothing.**
- `_alNoteU` / `_alNoteUe` string (the "✅/❌ alert status" note) removed — now the label
  only appears when alert was sent, so it always reads `✅ Alert sent to MT5` (hardcoded).
- `_devNote` (dev mode bits string) moved inside the gate block.
- Timestamp uses `fTS()` — `timenow` at the exact second the alert fires, Berlin timezone.
  This is stable because Pine does NOT re-execute on eye-icon hide/show; the string is
  baked into the label at creation time.

**Files changed:** `turtle.pine` lines ~1583–1622 (bull), ~1673–1715 (bear)

---

### Change 2 — Settings backed up to CSV

**File:** `settings_backup_2026-03-20.csv`

All ~120 TradingView indicator settings captured as Name,Value pairs.
TradingView has no native settings export; this file is the source of truth for restoring
the exact configuration after switching computers or accounts.

Key settings at time of backup:
- `iMon = 869` (starting capital, main account)
- `uOE = IOE` (Instant at Breakout — fires intra-bar when price crosses trigger)
- `uPBD = 4` (pre-breakout offset: fires $4 BEFORE the breakout level)
- `uPBsD = 2` (post-breakout offset: combined with pre-offset)
- `uPBCo = true` (co-exist: if pre-offset missed, fire at actual breakout instead)
- `uRp = 7` (risk 7% of capital per trade)
- `uTPPips = 5` (fixed 5-pip TP override)
- `uST = Prev Candle` (SL method: previous candle high/low)
- `uSBf = 4` (SL buffer: $4 offset from reference level)
- `uSMn = 0.2` (SL minimum floor: $0.20)
- `uCd = 22` (22-bar cooldown between signals)
- `uAlGt = -0.05` (alert gate: always fire, even if -5¢ past TP)
- `uIOEGrd = 1` (IOE TP guard: rebase if TP within 1× spread of close)
- `pE = true` (send PineConnector alerts)
- `pcSL = Price`, `pcTP = Price` (SL/TP sent as exact price levels, not pips)
- `bRW = true` (bypass retracement — fires whenever red candle breaks green low)
- `uBrkBody = true` (require body breakout, not just wick)
- `uDev = true` (developer mode: show condition bitmask on labels)

---

### Previously completed changes (same session, earlier today)

#### IOE TP Guard configurable strictness (`uIOEGrd`)
Added `input.float uIOEGrd` (default 1.0) to UHV settings group.
- `0` = guard off
- `1` = rebase TP when it's within 1× spread of close (original behavior)
- `2+` = stricter (rebase when TP within 2× spread, etc.)
Used in bull guard: `if _uIOE and pcOT != "Limit" and uIOEGrd > 0 and _tp1 <= close + uSpread * uIOEGrd`
And bear guard: `... and _tp1 >= close - uSpread * uIOEGrd`

#### Price format for SL/TP (pcSL = Price, pcTP = Price)
Switched from pips format to price format for PineConnector alerts.
- **Pips format** (`sl_pips=`, `tp_pips=`): applied from MT5 fill price → different levels than Pine computed
- **Price format** (`sl_price=`, `tp_price=`): sends exact computed price → MT5 honors them exactly
- After switching, Pine Script labels matched MT5 actual trades to the cent (verified on 4 trades)

#### IOE TP guard uses uTPPips when set
When `uTPPips > 0`, the guard rebases TP using `close ± uTPPips * pPip` instead of RR/Dollar formula.
Previously the guard always used the dollar/RR formula regardless of `uTPPips`.

---

### Open issues / next investigations

1. **`_uF` re-fire bug**: Signal #601 fired 3 times (15:25, 15:35, 15:36 UTC) from the same
   setup, opening 3 MT5 positions while Pine shows 1 label. Root cause: with `bRW=true`,
   a new retracement can start on any bar (resetting `_uF=false`). The `(bar_index - _luSB) >= _euCd`
   cooldown in `_bBrk` should block re-fires within 22 bars — but the 3 fires happened only
   10 bars apart. This needs deeper investigation. Candidate: `_luSB` may not be updating
   correctly when `_safe=false` (margin risk) blocks the fire path.

2. **Ghost labels investigation**: With the 1:1 alert=label change above, the label count
   should now match the MT5 alert count. This needs live verification — run the indicator,
   compare alert log entries to label count on chart.

3. **Win rate reality check**: The 98% Pine Script win rate included gate-blocked signals
   counted as wins (instant TP hit = win, even when no alert sent). With 1:1 gating, the
   real win rate on *alerts actually sent* may differ. Needs observation over more live trades.

---

### Architecture reference

```
TradingView (Pine Script) → alert() → PineConnector webhook → MT5 market order
```

Alert format (PineConnector):
```
87782869895251,buy,XAUUSD,vol_lots=1.04,sl_price=4655.12,tp_price=4660.00,comment=UHV@4659.09_16:25:37_#42#0110100001100000
```

16-bit condition bitmask in comment (bit0=direction, bit1=IOE, bit2-3=strategy, bit4=strict trend on,
bit5=strict trend ok, bit6=sweep req, bit7=sweep confirmed, bit8=pre-offset on, bit9=co-exist path,
bit10=trend direction, bit11=in-session, bit12=vol filter on, bit13=vol filter ok, bit14=OC filter on,
bit15=OC filter ok).

T1 settings export string in stats panel row 18 — pipe-delimited, all ~120 settings, copy-paste
to save/restore configuration.

Timezones:
- TradingView chart: UTC+1 Berlin (Europe/Berlin)
- PineConnector logs: Berlin time (UTC+1)
- MT5 server: UTC (1 hour behind Berlin)
- `fTS()` function: `timenow` in Europe/Berlin → exact second label timestamp

Two indicator instances:
- Main account: license `87782869895251`, symbol `XAUUSD`, capital $869
- Small account: license `8778286989525`, symbol `XAUUSDm`, capital $67
- Each has independent state (separate `var`/`varip` variables, trade counters diverge)
```
