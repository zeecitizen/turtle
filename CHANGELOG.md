# Turtle Trader Desk — Change Log

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
