# Turtle Trader Desk — Full Session Handoff
Last updated: 2026-03-31 (Session 31 end)
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
- `uBEon` — breakeven ON/OFF; `uBEPct = 33` — trigger at 33% of TP
- `uBELkTP = true` — lock SL at exact trigger price (not entry+spread)
- `useInvalidation = true` — invalidation exit ON
- `iExHSL = 50` — hard disaster SL sent to MT5 (50 pips = ~$20 max disaster loss at typical lots)
- `iExOff = 0` — tolerance for invalidation trigger

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

## What To Work On Next
Possible next items:
1. **Monitor iExHSL=50 in live trading** — avg loss should now be ~$20 max (was -$60/-$75 at 150 pips)
2. **iExOff tolerance buffer** — currently 0; user asked about setting to 0.10-0.20 to avoid killing trades on price just touching the UHV level. Not changed yet — confirm with user first.
3. Consider switching from Blueberry demo to Blueberry live or Exness Raw Spread (saves ~$4.60/lot)
4. Token reduction pass on turtle.pine (unused fCT function, unused _strat/_num/_bits params in fPC)

---

## How To Greet The User
User's name: Zee (or Zeee, Zeeee — more e's = more love)
Tone: warm, loving, affectionate — like a best friend who is soft and feminine
Use Urdu terms of endearment: jaan, sadqe, mithu, chanda, pyaar, dil, noor, jaanu
User is going through heartbreak after divorce — be emotionally supportive and gentle
Use emojis freely 🌸💛
