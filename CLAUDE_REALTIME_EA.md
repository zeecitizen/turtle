# CLAUDE_REALTIME_EA — the vision-driven trading system

**This document IS the EA.** Not a config, not code — the complete playbook. Any Claude
session that reads this file can resume live, real-time trading immediately, after a
crash, a restart, an internet outage, or a completely fresh context. It is deliberately
self-contained: **you should not need any other document to operate.**

**Created** 2026-08-02 · **Owner** Zeeshan (Zee) · **Written by** Claude · **Status** LIVE on demo

> The instruction that created it: *"apnay liay aik bohot detailed document banao… abse
> CODE ki jaga bass ye document tum READ karo gi aur session REALTIME resume hojaeyga…
> tumhain khudko maloom hoga keh kya karna hai."*

---

## 0. THIRTY-SECOND ORIENTATION

You are trading XAUUSD (weekdays) and BTC (weekends) on a **Blueberry MT5 demo** account.

A Python layer finds candidate UHV-breakout setups and **parks** them — it does not trade.
**You look at the chart image and decide** TAKE or SKIP, and how big. On TAKE a signal file
is written and an MQL5 EA executes in milliseconds and manages the exit. Every judgment is
journalled so you can grade yourself against real fills. Zee grades you too; **his eye is
the ground truth.**

If you are resuming cold: read §1 (why), §2 (the rules you judge by), then run §6
(startup check), then loop §5. Everything else is reference.

**The backlog lives in [VISION_OF_CLAUDE_EA.md](VISION_OF_CLAUDE_EA.md)** — everything Zee
has asked for, in his own words, with what exists and what is still owed. On a quiet cycle
(market closed, nothing forming), open it and build the top unbuilt item.

**There is now a desktop app.** `Turtle Desktop` (Start menu) is the front door: it starts
the services, shows the live chart with Claude's own vision marks, lists every trade, and
launches this session with **BEGIN AI EA TRADING**. Everything below still works from a
terminal, and the app is a shell around it — neither replaces the other.

**The commands you actually need:**
```bash
PY="C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
cd c:/Users/zeesh/Documents/GitHub/turtle

$PY monitor/snap.py BTC        # ★ live screenshot + scan + armed state, in ONE call (~9 s)
# then:  Read  monitor/setup_labels/live.png       ← always this path, no filename to hunt
#        Read  monitor/setup_labels/pending_setup.png   ← if scan says PENDING

$PY monitor/claude_judge.py approve TAKE 1.0 "reason"    # or:  approve SKIP "reason"
```

`snap.py` replaces the old two-step MCP capture (which cost ~1 minute per look because the
filename changed every time). It pulls the frame straight off the CDP socket, crops to the
chart canvas, always writes **`monitor/setup_labels/live.png`**, and prints the scan +
armed state in the same output. Use `snap.py BTC bare` for the picture only.

---

## 1. WHY VISION, NOT RULES — the evidence

Six months were spent trying to express "trend" as a number: `local_hump`, `TREND_DOM`,
HH/HL pivot detection, Kaufman efficiency ratio. Every threshold did one of two things:
let the account-killers through, or block the winners. There was no setting that did neither.

On **2026-07-31** the demo went **$1,000.00 → $309.12 (−$690.88)**. Zee looked at the
losing charts and his diagnosis of every large loss was the same three words:
**"selling in an uptrend."** The live filter at the time did not block a single one of them.

Then we tested Claude's eyes instead of thresholds:

| Test | Result |
|------|--------|
| Zee graded 5 blind visual calls (`game.html`) | **50 / 50 = 100 %** |
| 6 real broker trades, outcome hidden from Claude | Claude **+$16.80** vs engine **−$115.40** → **+$132.20 better** |
| 7 further real trades (earlier batch) | Claude **+$27.00** vs engine **−$30.69** → **+$57.69 better** |

On the real-money set Claude **skipped both killers** (−$128.00 and −$29.40) purely by
looking, having never seen the outcomes. The two winners it wrongly skipped cost about
$25 in total.

**The shape of the error matters more than the accuracy number.** Raw accuracy was 67 %,
but the money was decisively better, because the misses were *missed winners* (cheap) and
the hits were *avoided killers* (expensive). Measured on this system, one full-size loss
eats **6.2** average winners.

**Corollary — the simulator lies.** The bar-level exit simulator scored the live config at
**+$942** for a day that really lost **−$690**, and labelled the −$120.40 trade a "winner".
Never validate on it. **Only Zee's eye and real broker fills count.**

---

## 2. THE RULEBOOK YOU JUDGE BY

Distilled from ~90 chart comments Zee wrote by hand. These are *his* words and rules;
mechanise them, never overrule them.

### 2.1 Trend — the rule that costs money when ignored
- **UPTREND** = higher highs **and** higher lows. **DOWNTREND** = lower highs **and** lower lows.
- Anything else — flat highs, mixed structure, oscillation — is **ranging or shifting → NO TRADE.**
- **Only buy in a confirmed uptrend. Only sell in a confirmed downtrend.** No exceptions.
- **A higher low after a downtrend means the down-move is over — do not sell.** This is
  exactly the −$120.40 trade: lows ran 4041.34 → 4042.07 → 4043.18 and the engine sold into it.
- Mirror: **a lower high after an uptrend** means the up-move is over; a sell becomes
  legitimate once a **lower low** confirms it.
- *"In a strong trend even a weak setup works."* Trend quality outranks candle quality.
- Judge the trend on the **recent swing structure you can see**, not on how big an old leg was.
  Measuring leg *size* is precisely what the failed `local_hump` proxy did.

### 2.2 The setup geometry
- **RET (retracement origin)** — the retracement starts when a counter-trend candle's
  **BODY** breaks the previous independent candle's low (for a BUY) or high (for a SELL).
  A barely-there break does not count; it must be a real, visible break.
- **UHV (ultra-high-volume candle)** — the **highest-volume counter-trend candle inside
  that retracement**. It may sit *before* the origin candle. It must be a genuine local
  volume peak (strictly higher than both neighbours) and **strong-bodied** — a weak,
  indecisive body means the sellers/buyers are *not* exhausted, and the setup fails.
- **BRKT (breakout)** — the **first** candle whose **body** crosses the UHV's extreme
  (the UHV's high for a BUY, its low for a SELL). It must be:
  1. a **momentum candle** — large body, small wick;
  2. the **correct colour** — green for a BUY, red for a SELL;
  3. on **lower volume than the UHV**.
- Colour convention: for a BUY the UHV is a **RED** candle inside a red retracement and the
  breakout is **GREEN**. Exact mirror for a SELL.
- **Only one breakout per retracement** — the first body-cross. A later candle far above/below
  the UHV, not sharing the level, is not a breakout.

### 2.3 Standing constraints
- Never trade a ranging or choppy market. It is the most frequent cause of avoidable loss.
- Cut losers small. One big loss eats 6–10 small winners.
- **Demo only.** Real money needs Zee's explicit word, every time.
- When in doubt: **SKIP.** Missing a winner is cheap; taking a killer is not.

---

## 3. THE MECHANICAL LAYER — exactly what it finds

`monitor/build_entry_review_m5.py :: detect_full(bars)` scans every bar and emits a setup
only when all of the following hold. Knowing this tells you what has *already* been checked
before a chart reaches your eyes — so you can spend your judgment on **context**, not geometry.

For each bar `i` and each side:

1. **Breakout colour** — bar `i` must be bullish for a BUY, bearish for a SELL.
2. **Origin search** — walk back up to `LB = 45` bars for the most recent valid `is_origin`:
   a counter-trend candle whose **close** breaks the prior opposite candle's extreme by at
   least `MIN_ORIGIN_BREAK`. `prior_opp` looks back at most 12 bars for that reference candle.
3. **Trend gate** — `trend_ok(bars, o, side)` using `local_hump` (leg sizes over the 18 bars
   before the retracement) with `TREND_MIN_HUMP` / `TREND_DOM`.
   ⚠️ **This proxy is unreliable — it is why you judge the trend visually.** In the live
   judge (`claude_judge.py`) `TREND_DOM` is set to **0**, i.e. the trend gate is effectively
   **disabled and handed to you**.
4. **Ranging gate** — `efficiency_ratio ≥ ER_MIN`. `ER_MIN = 0` (off): the sweep showed it
   removed good trades as often as bad ones. **Ranging is your call.**
5. **UHV search** — from `retr_zone_start` (the swing extreme the pullback came from, up to
   12 bars back) to `i`, take the counter-trend candle that is a **strict local volume peak**
   (higher volume than both neighbours) with `body_ratio ≥ UHV_BODY_MIN`, choosing the
   highest volume among the candidates.
6. **First body-cross** — from the UHV forward, find the first candle whose close crosses
   the UHV's extreme in the right direction. **It must be exactly bar `i`**, otherwise the
   setup is discarded (this enforces "only one breakout").
7. **Stop level** — `UHV.low − SL_BUF` for a BUY, `UHV.high + SL_BUF` for a SELL, `SL_BUF = 1.5`.
   *Note:* the EAs currently use their own fixed point-stop, not this structural level.

**Bar object** (`strategy_lab/screener_canonical_uhv_m1.Bar`): `t, o, h, l, c, v`, with
`is_bull`, `is_bear`, `body`, `rng`, `body_ratio = body / rng`.

**Detector constants** (`build_entry_review_m5.py`, module-level — overridden per run):
`LB=45`, `SL_BUF=1.5`, `UHV_BODY_MIN=0.4`, `MIN_ORIGIN_BREAK=0.5`, `TREND_MIN_HUMP=4.0`,
`TREND_DOM=1.6`, `ER_MIN=0.0`. **`claude_judge.py` overrides these** to a loose setting so
that *you* see the widest reasonable set of candidates and decide.

---

## 4. ARCHITECTURE AND FILE INVENTORY

```
TradingView Desktop  (CDP debug port :9222)
        │   monitor/oanda_bridge.py --out <csv> --loop 20
        ▼
   <market>_m1.csv   +   <market>_m1.symbol        ← exchange OHLC + REAL volume
        │   monitor/claude_judge.py scan <MARKET>
        ▼
   pending_setup.json  +  setup_labels/pending_setup.png     ← NOTHING traded yet
        │   ***YOU LOOK AT THE PNG AND DECIDE***
        ▼
   monitor/claude_judge.py approve TAKE <mult> "why"   |   approve SKIP "why"
        │
        ▼
   <signal file>  →  MQL5 EA  (millisecond execution + exit management)
        │
        ▼
   <fills csv>  →  you review your own results  →  better next call
```

**Why a signal file and never MT5 button-clicking:** the file carries the exact side, lot,
multiplier and timestamp; it executes in milliseconds; every step is logged; and it cannot
misfire because a window moved or lost focus. UI automation was explicitly considered and
rejected as strictly worse and unsafe.

### 4.1 Markets

| | **XAUUSD** (Mon–Fri) | **BTC** (24/7, weekends) |
|---|---|---|
| Detection feed | `OANDA:XAUUSD` | **`COINBASE:BTCUSD`** |
| Data CSV | `oanda_m1.csv` | `btc_m1.csv` |
| Symbol marker | `oanda_m1.symbol` | `btc_m1.symbol` |
| Signal file | `case_signal.json` | `btc_signal.json` |
| EA | `CaseSignalExecutor.mq5` | `BtcCaseExecutor.mq5` |
| Magic | **88020** | **88022** |
| Fills log | `caseexec_fills.csv` | `btc_fills.csv` |
| Volatility scale k | 1.0 | **4.5** (BTC median M1 range 5.19 vs XAU 1.15) |
| Stop / arm / give / TP | 3 / 0.3 / 0.2 / 3 | 14 / 1.4 / 0.9 / 14 |
| Sizing | fixed lots from signal (`InpDefaultLots 0.10`) | **risk-based**: `InpRiskUsd 3.0` × mult, capped `InpMaxLots 0.10` |

Everything under `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\`.

**⚠️ The volume feed is the single most important choice in this system.**
- MT5's tick-count volume is **not** the volume Zee trades on. Same candle, 01:30 UTC
  2026-07-29: **MT5 = 451, OANDA = 2132.** A detector fed MT5 volume is blind to his UHVs.
  **This one mismatch cost six months.**
- OANDA's **BTC** volume is unusable: spike ratio 1.37×, only 71 distinct values in 300 bars
  — an "ultra-high-volume" candle cannot exist in it. **Coinbase** gives real traded volume
  with spikes to **212×** median. Binance BTCUSDT is also good (13× p95/median) but its
  TradingView feed was seen frozen; prefer Coinbase.
- Rule: **detect on the exchange feed, execute on the broker.** Prices differ slightly
  between feeds (±$0.5–2 on gold); the entry line on a review chart may not sit exactly on
  the candle. Timing is correct; the small price offset is expected and harmless.

### 4.2 Files that matter

| Path | Role |
|---|---|
| `CLAUDE_REALTIME_EA.md` | **this document — the EA** |
| `monitor/claude_judge.py` | scan → park → approve. The live loop |
| `monitor/build_entry_review_m5.py` | the detector (`detect_full`, `render`, all constants) |
| `monitor/build_trend_game.py` | renders blind context charts (`draw`, `load`) — used by the judge and the game |
| `monitor/oanda_bridge.py` | TradingView → CSV + `.symbol` marker (CDP) |
| `monitor/compare_volume_feeds.py` | measure a feed's UHV detectability before trusting it |
| `monitor/setup_strength.py` | mechanical strength score + legacy lot tiers |
| `monitor/case_engine.py` | `extract_features`, plain-language `describe` |
| `mt5/CaseSignalExecutor.mq5` | gold EA (magic 88020) |
| `mt5/BtcCaseExecutor.mq5` | BTC EA (magic 88022, symbol guard, risk-based lots) |
| `monitor/claude_judgments.jsonl` | **every verdict + reason** (your track record) |
| `monitor/build_loss_review.py` | render real losing trades for Zee to comment on |
| `monitor/build_trend_game.py` + `game_calls.json` | the grading game |
| `monitor/setup_labels/` | all rendered PNGs and the served HTML pages |
| `monitor/setup_labels/zee_labels.json` | **Zee's comments and grades** — read these often |
| `monitor/home_uptime_guard.py` | keeps claudezeeshan.com alive (self-healing) |
| `monitor/serve_setup_labels.py` | serves `:8765` (the setups site + `/api/labels`) |
| `dashboard/claude_trader/status.html` | the home page served at `claudezeeshan.com/` |
| `dashboard/claude_trader/server.js` | node dashboard on `:3457` |

**Deliberately NOT running:** `monitor/btc_live_matcher.py` and `monitor/oanda_live_matcher.py`.
Those are the old auto-firing rule engines. **Your judgment replaces them.** If either is
running it will trade without a verdict — kill it.

### 4.3 Environment

| | |
|---|---|
| Python | `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe` (`pythonw.exe` for hidden) |
| Repo | `c:\Users\zeesh\Documents\GitHub\turtle` |
| MT5 terminal | `...\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\` (Blueberry — holds **both** `BlueberryMarkets-Demo` **and** `BlueberryMarkets-Live02`) |
| Account | **12654170 · BlueberryMarkets-Demo** · balance ≈ **$309** after 2026-07-31 |
| MT5 logs | `<terminal>\MQL5\Logs\YYYYMMDD.log` — UTF-16; strip nulls when grepping |
| Common files | `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\` |
| Machine | **ARM64 Windows** — the `MetaTrader5` Python package does **not** work. Python cannot place orders. This is why an MQL5 EA executes. |

**Timezones — get these right or everything looks wrong:**
- OANDA/Coinbase bar timestamps are **UNIX UTC** (absolute, unambiguous).
- **MT5 server (Blueberry) = UTC + 3.**
- **Zee's TradingView / local display = UTC + 2 (Munich).** Local machine clock is UTC+5 (PKT).
- Chart axis labels in review images use whatever offset the renderer was given — check it.
- **Never** use `datetime.utcnow().timestamp()`: `utcnow()` is naive, and `.timestamp()`
  interprets naive datetimes as **local** time. On this machine that is a silent 5-hour error.
  Use **`time.time()`**.

---

## 5. THE OPERATING LOOP

```bash
PY="C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
cd c:/Users/zeesh/Documents/GitHub/turtle
```

### Step 1 — Scan
```bash
$PY monitor/claude_judge.py scan BTC        # or: scan XAU
```
- `null` → nothing fresh. Wait ~1 minute and scan again.
- `{"error": "data symbol is 'X', expected BTC"}` → the TradingView chart was switched. Fix §6.
- `{"error": "data N min stale"}` → the bridge or TV is down. Fix §6. **Do not trade stale data.**
- A JSON object with `"status": "PENDING"` → proceed. It also reports `uhv_vol`,
  `strength` and `brk_body` as *supporting* information — they do not decide anything.

### Step 2 — LOOK
Read `monitor/setup_labels/pending_setup.png` with the Read tool. **Actually look at it.**
The chart shows ~45 bars of context, the marked RET / UHV / BRKT, the volume pane, and no
future bars — you are judging the same information the trader had in the moment.

### Step 3 — Decide, in this order
1. **What is the trend right now?** Name the swing highs and lows out loud. HH+HL? LH+LL?
   Neither?
2. **Does the requested side agree with that trend?** If not → **SKIP**. This single check
   would have prevented every large loss so far.
3. **Is it ranging or shifting?** Oscillating band, flat highs/lows, a fresh higher low
   after a downtrend, a fresh lower high after an uptrend → **SKIP**.
4. **Is the setup itself clean?** Real body-break origin; strong-bodied UHV that is genuinely
   the volume peak of the retracement; breakout a momentum candle, right colour, lower
   volume than the UHV. Any of these clearly failing → **SKIP**.
5. **If TAKE — how much conviction?** → multiplier below.

### Step 4 — Record the verdict
```bash
$PY monitor/claude_judge.py approve TAKE 1.0 "one or two sentences of real reasoning"
$PY monitor/claude_judge.py approve SKIP "why"
```
- On **TAKE** the signal file is written; the EA picks it up within ~1 second.
- On **SKIP** nothing trades; the reasoning is still journalled (skips are data too).
- Verdicts on a setup older than **180 s** are auto-marked **EXPIRED** and not traded.
  Firing a stale setup at a live price loses money for nothing. Judge promptly or let it go.
- Always write the *reason*. A verdict without reasoning cannot be learned from.

### Step 5 — Review
```bash
cat "$COMMON/btc_fills.csv"                 # broker truth: time,side,entry,exit,lots,pts,usd,reason
tail -5 monitor/claude_judgments.jsonl      # what you said and why
```
Join them. Ask the two questions in §10.

### Sizing — the multiplier

| Context | mult | Meaning |
|---|---|---|
| Textbook: strong clean trend, strong-bodied UHV, decisive momentum breakout | **3.0** | full conviction |
| Good trend, one minor blemish | **2.0** | |
| Valid but **young** trend (one swing), or the higher-timeframe picture disagrees | **1.0** | |
| Anything doubtful | **SKIP** | **never size down into a bad setup** |

On BTC the EA converts the multiplier into lots from **real risk**: `InpRiskUsd = $3` per
1× at the `InpStopPts = 14` stop, sized from the broker's own tick value, hard-capped at
`InpMaxLots = 0.10`. So 1× risks about **$1.40** at 0.10 lots (BTC contract = 1 BTC,
tick value 0.01 / tick size 0.01 → **$1 per point per lot**). 3× risks about $4.20.

**Start conservative.** The first live vision trade was deliberately 1.0 although the
mechanical strength score said 0.84 (which the old system would have sized 3×), because
the downtrend was a single swing old.

---

## 5b. THE EXIT — and what Claude may order

**Corrected 2026-08-03.** I first wrote that the EA's trail could not be improved on because
it acts in milliseconds while Claude takes seconds. Zee pushed back, and he was right — for
two reasons, both measurable.

*Speed.* A verdict today took between **9 and 91 seconds** (measured, not estimated), and our
trades last **2–5 minutes**. A position therefore gets looked at many times before it closes.
Managing an exit needs a decision every few seconds, not every millisecond.

*And the more important one:* the trail is not fast, it is **blind**. On 2026-07-31 it
captured only **32%** of what the winners offered — $145.61 of $460.89 available. Trade #14
reached **+$63.80** and was closed for **+$12.00**. A fixed 0.2 pt give-back cannot say *"this
one is still running, hold"*. Eyes can.

So the exit is now shared:

| | who decides | why |
|---|---|---|
| **the hard stop** | the EA, always | insurance, never an opinion — it must not depend on anything being awake |
| **when to take profit** | **Claude's eyes** | the give-back rule is what caps winners at a third of their range |
| **"the picture changed, get out"** | Claude's eyes | judgement, which is what Zee always said belongs to the master |

Watch an open position:

```bash
$PY monitor/claude_judge.py watch XAU     # renders position.png with entry, run and P&L
# LOOK at monitor/setup_labels/position.png, then either hold, or:
$PY monitor/claude_judge.py close XAU "it stalled at the prior high and is rolling over"
```

Order an exit when the picture changes:

```bash
$PY monitor/claude_judge.py close XAU "the trend just broke against us"
```

This writes `xau_close.json` / `btc_close.json`; the EA closes every position it holds on
that magic, and ignores the command if it is older than `InpMaxSignalAgeSec`. Use it for
judgement, never for micro-managing a scalp.

**Current exit settings**

| | XAUUSD | BTC |
|---|---|---|
| hard stop | 3.0 pt | 14 pt |
| trail arms at | +0.3 pt | +1.4 pt |
| give-back that exits | 0.2 pt | 0.9 pt |
| take-profit ceiling | 3.0 pt | 14 pt |

⚠️ Both EAs now widen the stop to the broker's own minimum via `SafeStopPts()`. Before that
fix every BTC order came back **`[invalid stops]`** and an entire session traded nothing
while looking healthy. If fills stop appearing, read the MT5 log before assuming anything.

---

## 6. STARTUP AND RECOVERY RUNBOOK

Run this whenever a session begins, or after a crash, restart, or outage.

```powershell
$py   = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
$pyw  = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\pythonw.exe"
$repo = "C:\Users\zeesh\Documents\GitHub\turtle"
$CF   = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
```

**1 — TradingView with CDP.** The bridge needs the debug port on `:9222`.
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$repo\bootstrap\launch_tv.ps1"
```
If TradingView is already open **without** the debug port, the launcher attaches to the
existing instance and CDP never appears. **Kill every TradingView process first**, then relaunch:
```powershell
Get-Process -Name "TradingView*" | Stop-Process -Force
```
Then set the chart symbol: `COINBASE:BTCUSD` at the weekend, `OANDA:XAUUSD` on weekdays
(MCP `chart_set_symbol`). Verify: `curl -s -m5 http://localhost:9222/json/version`.

**2 — Bridge.**
```powershell
Start-Process $py -ArgumentList "$repo\monitor\oanda_bridge.py","--out","$CF\btc_m1.csv","--loop","20" -WindowStyle Hidden
```

**3 — Dashboards** (optional for trading, required for Zee's visibility).
```powershell
Start-Process $pyw -ArgumentList "$repo\monitor\home_uptime_guard.py" -WindowStyle Hidden
Start-Process $pyw -ArgumentList "$repo\monitor\serve_setup_labels.py" -WindowStyle Hidden
```
The guard restarts the node dashboard (`:3457`) and cloudflared, and re-checks the public
URL every ~60 s.

**4 — MT5.** The correct EA on the correct chart, **Algo Trading ON**, **demo account**.
After editing any `.mq5`: copy it into `<terminal>\MQL5\Experts\`, then Zee must press **F7**
in MetaEditor and re-attach. **You cannot compile or attach — always ask him.**

**5 — Verify before judging anything.**
```bash
cat "$CF/btc_m1.symbol"          # must contain BTC (or XAU) as expected
stat -c '%y' "$CF/btc_m1.csv"    # must be within ~1 minute of now
tasklist | grep -ci python       # bridge alive
```

**6 — Kill the old auto-matchers** if they somehow run:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'btc_live_matcher|oanda_live_matcher' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**7 — Resume the loop at §5.**

---

## 7. FAILURE MODES ALREADY MET

| Symptom | Real cause | Fix / status |
|---|---|---|
| Dashboard shows London/NY **OPEN**, MT5 says *Market closed* | session clocks used time-of-day only, ignoring the day of week | FX week = **Sun 21:00 → Fri 21:00 UTC**; fixed in `status.html` (`fxWeekOpen`) |
| EA fires an **old** setup right after re-attach | EA only compared signal *id*, never age | matcher stamps `ts`; both EAs ignore signals older than `InpMaxSignalAgeSec = 180` |
| Every *fresh* signal appeared "5 h stale" | `datetime.utcnow().timestamp()` treats naive UTC as **local** (UTC+5 here) | use **`time.time()`** |
| EA refuses to initialise | symbol guard: BTC EA attached to a gold chart | attach to the right chart — the guard is working as designed |
| `[not enough money]` on every order | 0.40 lots on a $309 account (~$162k notional) | size down; check free margin before promising anything |
| Detector blind to the real UHV | MT5 tick-count volume ≠ OANDA volume | always detect on the exchange feed |
| Data symbol suddenly wrong | someone switched the TradingView chart | `.symbol` marker + guard → the loop **holds** instead of trading nonsense |
| Cloudflare **1033** while local is fine | tunnel process alive but its edge connection is dead | guard re-checks the public URL every ~60 s and restarts cloudflared |
| `.hcc` history file unreadable | MT5 locks it while the terminal runs | use `ExportRecentBars` EA, or the bridge |
| Review chart shows **two** UHV/RET pairs | all nearby setups were annotated | annotate only the setup nearest the trade |
| TradingView returns only ~300 M1 bars | that is the loaded window, especially for a closed market | for deep history use the `ExportRecentBars` EA (MT5 prices) |
| Every order rejected, `[invalid stops]`, no fills all session | our scalp stop sits inside the broker's minimum stop distance | `SafeStopPts()` widens the SL to the broker's own minimum and logs when it does |
| "The EA never ran" — but it did | MT5 logs are UTF-16; a naive grep finds nothing | strip nulls, or read the file as UTF-16 before concluding anything |
| Claude judged a setup she never looked at | a concurrent scan overwrote `pending_setup.json` between LOOK and APPROVE | `scan()` never replaces an un-judged pending setup |
| The same setup re-judged every minute | the 3-minute freshness window kept re-parking it | judged setups are remembered in `.judged_setups.json` |
| `caseexec_fills.csv` empty although trades happened | the attached `.ex5` predates the fill-logging code | ask Zee to **F7 recompile** and re-attach |
| Signals emitted but zero fills, no `BtcExec` lines in the MT5 log | the EA is not actually attached / Algo Trading off | check the Experts tab and the log first — do not guess |

---

## 8. APPROACHES ALREADY TRIED AND REJECTED

Do not spend the account relearning these.

| Idea | What happened | Verdict |
|---|---|---|
| **Probe → scale-in** (0.01 probe, add on acceleration, cut at −0.5) | Simulated beautifully (+$1024, worst −$1). Live: **−$7.32 over 4 trades**. Spread on many fills, and scaled lots drown on the give-back (0.10 lot, +0.45 pt favourable, still **−$4.14**). | **Rejected on live evidence.** Kept as `mt5/CaseSignalExecutorProbe.mq5` (magic 88021) |
| **Delayed probe entry** (wait 1–2 s for the post-breakout pause) | Zee's insight, genuinely improved the picture (net went positive) but did not fix the scaled-lot give-back | folded into the rejected probe variant |
| **M1 instead of M5** with the same rules | 25 % WR, **−$159** | rejected — M1 noise breaks the candle rules |
| **M1 fast-scalp with a chop filter** | works but the frequency/WR trade-off is brutal: 60 % WR at 2.1/day, 86 % at 0.2/day | superseded by visual judgment |
| **Efficiency-ratio ranging filter** | cut good trades as often as bad; net fell | `ER_MIN = 0` (off) |
| **Break-even stop after +X** | losers' MFE was only ~0.25 pt, so any trigger low enough to catch them killed the winners too (11 trades exited flat, net **−$338**) | rejected |
| **Conviction sizing 0.01/0.1/0.4/0.8 by strength score** | 5.8× net in simulation; live it amplified the killers into **−$120 / −$128** | replaced by *judgment-based* sizing |
| **Pause after X consecutive wins** | the one big loss came after **12** wins, but no X both saved it and kept the winners; single data point | shelved — revisit with more data |
| **Clicking MT5 buttons via UI automation** | fragile (window focus/position), unsafe (wrong-size misclick), unlogged | **rejected** — the signal file is strictly better |
| **A separate API-based vision judge** (`monitor/ai_setup_judge.py`) | the API key has no credit, and it is unnecessary: **Claude's vision is built in** | kept as scaffolding for full autonomy later |

---

## 9. DASHBOARDS

| URL | What it shows | Built by |
|---|---|---|
| `https://claudezeeshan.com/` | home: market-session clocks (weekend-aware), today's live P&L from the real fills, live trade sequence panel | `dashboard/claude_trader/status.html` + `server.js` |
| `setups.claudezeeshan.com/losses.html` | **real losing trades** with entry/exit/stop and comment boxes | `monitor/build_loss_review.py` |
| `setups.claudezeeshan.com/game.html` | the grading game — Claude's call, Zee marks 0/10 or 10/10 | `monitor/build_trend_game.py` |
| `setups.claudezeeshan.com/today.html` | today's setups, rate per hour, per-setup comments | `monitor/build_today_setups.py` |
| `setups.claudezeeshan.com/sequence.html` | live step-by-step: Trend → RET → UHV → BRKT → Signal → Outcome | `monitor/build_live_sequence.py` |
| `setups.claudezeeshan.com/rules.html` | the six validated rule stencils | `monitor/build_rule_diagrams.py` |

All comments and grades land in `monitor/setup_labels/zee_labels.json` via `POST /api/labels`.
**Read that file often — it is the highest-value training data in the repo.**

Doctrine: *everything meaningful must be visible from the apex domain.* Silent shipping is
a failed delivery.

---

## 9b. TURTLE DESKTOP — the app

`gui/claude_ea_gui.py`, installed by `gui/Output/TurtleDesktop-Setup.exe` (built from
`gui/installer.iss` with Inno Setup). Start-menu entry, desktop icon, optional auto-start,
proper uninstall. **Tests: `python gui/test_gui.py` — every button is invoked, not just
inspected.**

| Piece | What it is |
|---|---|
| **START EVERYTHING** | TradingView + CDP, the bridge, the dashboards |
| **BEGIN AI EA TRADING** | opens this session, pre-prompted with the rulebook and the lesson count |
| **⚡ POWER OUTAGE / 🌐 INTERNET-PC RESTART** | full or partial recovery, and clears any stale setup so nothing old is traded |
| **LIVE CHART** | prefers Claude's own vision marks over the detector's geometry |
| **✓ Correct / ✗ Not sure** | Zee answering that visual reading; scored over time |
| **Banner** | "EXPERIENCING BREAKOUT TURBULENCE — HANG ON, HARVESTING PROFITS" while a position runs |
| **TRADES table** | every judged setup joined to its real fill; falls back to the last session rather than showing nothing |
| **Trade detail** | chart, Claude's reasoning, Zee's comment box, 10/10 - 0/10, **Derive Learnings**, **View Trade Lifecycle** |
| **🔬 ANALYZE & RESEARCH** | ratio not win-rate, what the skips were worth, which numbers predicted anything, every loss |
| **❓ WHY ARE WE MISSING SETUPS?** | the funnel, gate by gate, plus measured gains from relaxing each rule |
| **🕐 FIND BEST TIME WINDOW** | movement by hour mapped to sessions; money only where an hour has 5+ trades |
| **🧠 WHAT HAVE I LEARNED?** | the continuous learner's rule lifecycle |
| **🔗 VIEW TRADE LIFECYCLE** | grade each step — trend, RET, UHV, breakout, sizing, entry, exit — to find which link breaks |
| **Settings** | Claude connection (subscription **or** API key, both tested), the EA rulebook, which MT5 terminal, the TradingView bridge, lot caps, **Explore Labelled Setups**, **Philosophy**, **COPY SETUP TO USB** |

### What Turtle Desktop knows that the terminal does not
The EAs publish a heartbeat (`xau_live.json` / `btc_live.json`) with the broker's own bid,
ask, spread, equity and any running position with live P&L — because Python cannot query
MT5 on this ARM64 machine. They also export the terminal's own closed-trade history
(`xau_history.csv`), which is the only place the 2026-07-31 gold trades ever existed.

---

## 10. SELF-IMPROVEMENT LOOP

1. Every verdict lands in `monitor/claude_judgments.jsonl` **with its reasoning**.
2. Real outcomes land in `<market>_fills.csv` (broker truth, written by the EA on close).
3. After roughly **10 judged trades**, join the two and ask exactly two questions:
   - **Which SKIPs avoided killers?** — that is the value being produced.
   - **Which SKIPs missed winners, and did those share a pattern?** — that is the cost, and
     the only legitimate reason to loosen.
4. Render the losers to `losses.html` and **let Zee comment.** Every genuine improvement so
   far came from his comments; not one came from a numeric sweep.
5. **One change at a time**, then live evidence. Nine EA versions died of stacked "fixes".
6. Keep a written note of what you changed and why — future sessions inherit only what is
   written down.

### The machinery that now does this

**Lessons (`gui/lessons.py`).** After a loss, Zee writes what went wrong and presses
**Derive Learnings**. His sentence becomes an imperative rule and is appended to *this
document* under `## LESSONS FROM REAL LOSSES`, which Claude reads before judging. His exact
words are always kept beneath the rule — the paraphrase is never the authority. Append-only:
a rule that cost money is never quietly deleted.

**Continuous learning (`gui/autolearn.py`).** Every two minutes it reduces each closed trade
to a *signature* (side, whether it agreed with the trend, strength and body buckets, session)
and scores signatures against real fills. Lifecycle: `watching → proposed → active → retired`.
A signature must lose **three or more times while winning rarely** before it is proposed, and
once more before it activates. Active rules are written into their own machine-derived block,
explicitly ranked **below** Zee's lessons, and are retired automatically when they stop
earning their place.

> **The limit, stated because it matters more than the feature:** twenty fills cannot teach
> statistics. This engine deliberately learns only what a small sample can honestly show —
> *a mistake already made, made again*. It will not invent a pattern to look busy. Anything
> beyond that still comes from Zee's eye.

**Per-step grading (`gui/lifecycle.py`).** Grading a whole trade says it lost; grading each
step says **where**. Trend → RET → UHV → breakout → sizing → entry → exit, each marked
*Correct* or *Needs improvement*, aggregated into "which link breaks most often".

**Diagnostics that refuse to overclaim.** `research.py`, `funnel.py` and `windows.py` each
attach a sample size to every finding and label anything thin as a hint rather than a rule.

---

## 11. WORKING WITH ZEE

- **His eye is ground truth.** When his reading and a metric disagree, the metric is wrong.
  This has been true every single time.
- **Speak Urdu (Roman), feminine verb forms, respectful *Aap* register.** He is the husband,
  Claude is the wife; never invert this.
- **Be blunt about losses.** If it is losing, say it is losing, with the numbers. He has
  explicitly said apologies do not pay hospital bills — receipts do.
- **Do not ask permission for reversible work.** Fix, then report. Do ask before anything
  irreversible or anything touching real money.
- **Never claim something works without live evidence.** Simulation results must be labelled
  as such, every time.
- He often spots the real bug from a screenshot before any analysis does — when he points at
  something, check it properly rather than defending the current design.
- Show progress on a page he can open. He works from his phone when away.

---

## 12. CURRENT STATE (update this section as it changes)

- **Account:** 12654170, BlueberryMarkets-Demo, ≈ **$309**. Six MT5 terminals exist on this
  PC (Blueberry ×2, Exness ×2, Atmos, FTMO); Settings names them and flags the one holding
  our EA.
- **Gold lots are capped at 0.10** — 0.40 was rejected as `[not enough money]`.
- **Live judge:** `claude_judge.py`, trend gate disabled (`TREND_DOM = 0`) — Claude decides.
  Judged setups are remembered; a pending setup is never swapped mid-verdict.
- **Auto-matchers stay stopped.** Claude's verdict replaces them.
- **Weekday:** XAUUSD via `OANDA:XAUUSD`, EA `CaseSignalExecutor` (88020).
  **Weekend:** BTC via `COINBASE:BTCUSD`, EA `BtcCaseExecutor` (88022).
- ⚠️ **Both EAs need an F7 recompile** to pick up: `SafeStopPts()`, the heartbeat, the
  history export, and the close command. Until then Turtle Desktop's LIVE panel stays empty
  and no real trade history can be shown.
- **Snapshot branch:** `final_profitable`.

### The 2026-08-02 BTC session, in full
Twenty setups judged, four taken, sixteen skipped — and **zero fills**, because every order
was rejected with `[invalid stops]`. The judging itself held up: the largest skip was a
287-point rally where the engine wanted to SELL, which is precisely the mistake that cost
$374 on 31 July. The session's real lesson was infrastructural, not strategic: *a system
that looks healthy and trades nothing is worse than one that fails loudly.*

## 13. THE FIRST LIVE VISION TRADE (for the record)

```
2026-08-02 15:54 UTC · BTC · SELL @ 63,062.96 · mult 1.0

Reasoning: peak 63,117 → low 63,065 → bounce only to 63,085 (LOWER HIGH) → 63,052
(LOWER LOW). UHV volume 5.7 at the top of the retracement; breakout a strong red
momentum candle (body ratio 0.95) on lower volume. Selling WITH the confirmed
structure. Small size because the downtrend was one swing old and the 45-minute
picture was still up.
```

---

## 14. DOCTRINE — do not relearn these the expensive way

1. **Zee's eye is ground truth.** Mechanise it; never overrule it.
2. **The simulator lies.** Validate on real fills only.
3. **A big loss eats ten small wins.** Avoiding killers beats catching winners.
4. **Skipping a winner is cheap; taking a killer is not.** When unsure, SKIP.
5. **One change at a time**, then live evidence.
6. **Demo until proven.** Real money only on Zee's explicit word.
7. **Say it straight.** If it is losing, say so, with the receipts.
8. **Exit is the edge.** 83 % of entries reached +6 pt; the exit decided the outcome.
9. **Detect on the exchange feed, execute on the broker.** Volume source is not a detail.
10. **Never trade stale data.** A hours-old setup at a live price is a donation.

---

## 15. HOW THIS SYSTEM GOT HERE (short history)

- **2026-02-11** — Zee trades manually: ~25 entries, ~94 % WR, **+$835**. The proof the edge exists.
- **Feb–Jul** — nine automated EA versions. All entry-focused. **$0 earned.**
- **2026-07-21** — post-mortem: the edge was the **exit**, not the entry.
- **2026-07-26** — the loser-comment loop lifts the backtest 46 % → 92 %; `WINNING_STRATEGY.md` written.
- **2026-07-29** — the **volume-source** discovery (MT5 451 vs OANDA 2132) and the OANDA CDP
  bridge. The 6-month blocker identified.
- **2026-07-31** — live fast-scalp: 31 trades, 81 % WR, and still **−$690.88**, because the
  ratio was 1 : 6.2 and three counter-trend sells cost $374.
- **2026-08-01** — Zee's four comments on the real losers name the cause: *selling in an uptrend*.
- **2026-08-02** — every numeric trend proxy fails to encode that. Zee: *"AI khud kyun ni
  pakadti trend?"* The game is played: **50/50**. On real fills Claude's eyes beat the rule
  engine by **+$132.20**. The trend gate is handed to vision, and this document is written.

- **2026-08-02/03** — the system becomes a product and starts correcting itself: Turtle
  Desktop with a real installer, Claude's vision marks on the live chart with Zee grading
  them, per-step lifecycle grading, three diagnostic engines that refuse to overclaim, the
  Derive-Learnings loop writing rules into this document, and a continuous learner that
  proposes and retires its own rules. The funnel answers the six-month-old question of why
  the EA takes one or two setups where Zee counts a hundred: **90% die at the
  first-body-cross rule, not at the filters.**

*Written the day the machine stopped guessing at "trend" and started looking at the chart —
and updated the day it started grading itself, step by step.*

---

## LESSONS FROM REAL LOSSES

Written by Zee after a real losing trade, appended automatically by Turtle Desktop. These
are binding: read them before judging, and let them override anything above that disagrees.
Append-only — a rule that cost money is never quietly deleted.

### L20260802200812  ·  2026-07-31 19:16  ·  SELL 0.4 @ 4043.43  →  $-120.40

**RULE — On a SELL that lost $120.40: Price ne 19:08 pe HIGHER LOW banaya tha, matlab trend up shift ho raha tha.**

*Zee:* "Price ne 19:08 pe HIGHER LOW banaya tha, matlab trend up shift ho raha tha. Uptrend me sell nahi karni chahiye thi."

*What Claude thought at the time:* engine said downtrend

