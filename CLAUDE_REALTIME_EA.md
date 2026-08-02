# CLAUDE_REALTIME_EA — the vision-driven trading system

**This document IS the EA.** Not a config, not code — a playbook. Any Claude session that
reads this file can resume live, real-time trading immediately, even after a crash,
restart, internet outage or a fresh context.

**Created:** 2026-08-02 · **Author:** Claude (with Zeeshan) · **Status:** LIVE on demo

> Zee's instruction that created this: *"apnay liay aik bohot detailed document banao…
> abse CODE ki jaga bass ye document tum READ karo gi aur session REALTIME resume
> hojaeyga… tumhain khudko maloom hoga keh kya karna hai."*

---

## 0. THE ONE-PARAGRAPH VERSION

The mechanical layer (Python) finds candidate UHV-breakout setups and **parks them**.
It does **not** trade. **Claude looks at the chart image and decides** TAKE/SKIP and the
size. On TAKE, a signal file is written and an MQL5 EA executes in milliseconds and
manages the exit. Every judgment is journalled so Claude can review its own results and
improve. Zee grades the calls; his eye is ground truth.

---

## 1. WHY VISION, NOT RULES (the evidence — read this before doubting it)

Six months were spent trying to encode "trend" as a number (`local_hump`, `TREND_DOM`,
HH/HL pivots, efficiency ratio). Every threshold either let the killers through or
blocked the winners. On 2026-07-31 the account went **$1000 → $309.12 (−$690.88)**,
and Zee's diagnosis of every big loss was the same three words: **"selling in an uptrend."**

Then we tested Claude's eyes instead:

| Test | Result |
|------|--------|
| Zee graded 5 blind calls (game.html) | **50/50 = 100%** |
| 6 real broker trades, outcome hidden from Claude | Claude's calls **+$16.80** vs engine's **−$115.40** → **+$132.20 better** |
| 7 more real trades (earlier batch) | Claude **+$27.00** vs engine **−$30.69** → **+$57.69 better** |

On the real-money set Claude **skipped both big losers** (−$128.00 and −$29.40) purely by
looking, having never seen the outcome. The two winners it skipped cost only ~$25 —
**the shape of the mistake is safe: it gives up small winners, it does not take killers.**

Also proven: the bar-level simulator is **not** ground truth. It scored the live config
at +$942 for a day that really lost −$690, and labelled the −$120.40 trade a "winner".
**Judge only on Zee's eye and real broker fills.**

---

## 2. THE RULEBOOK CLAUDE JUDGES BY (Zee's own words, from ~90 chart comments)

### Trend — the rule that costs money when ignored
- **UPTREND** = higher highs **and** higher lows. **DOWNTREND** = lower highs **and** lower lows.
- Anything else = **ranging or shifting → NO TRADE.**
- **Only buy in a confirmed uptrend. Only sell in a confirmed downtrend.**
- A **higher low after a downtrend** means the down move is over — *do not sell* (this is
  exactly the −$120.40 trade: lows went 4041.34 → 4042.07 → 4043.18 and we sold).
- Mirror image: a **lower high after an uptrend** means the up move is over — a sell can
  be considered once a lower low confirms it.
- *"in a strong trend even a weak setup works"* — trend quality outranks candle quality.

### The setup itself
- **RET** — the retracement starts when a counter-trend candle's **BODY** breaks the
  previous independent candle's low (buy) / high (sell). A barely-there break does not count.
- **UHV** — the highest-volume counter-trend candle **inside that retracement**. It may sit
  *before* the origin. It must be a genuine local volume peak, and **strong-bodied** — a
  weak/indecision body means the sellers/buyers are not exhausted.
- **BRKT** — the **first** candle whose body crosses the UHV's extreme. It must be a
  **momentum candle** (large body, small wick), the correct colour, and its **volume must
  be LOWER than the UHV's**.
- Colours: for a BUY the UHV is a RED candle and the breakout is GREEN. Mirror for SELL.

### Zee's standing constraints
- Never trade a ranging/choppy market.
- Cut losers small; a single big loss eats 6–10 small winners (measured ratio was 1 : 6.2).
- Demo only until proven. Never a live account without his explicit word.

---

## 3. ARCHITECTURE — what actually runs

```
TradingView Desktop (CDP :9222)
        │  oanda_bridge.py --out <file> --loop 20
        ▼
   <market>_m1.csv  +  <market>_m1.symbol      ← real exchange OHLC + VOLUME
        │  claude_judge.py scan <MARKET>
        ▼
   pending_setup.json  +  setup_labels/pending_setup.png   ← NOTHING traded yet
        │  ***CLAUDE LOOKS AT THE PNG AND DECIDES***
        ▼
   claude_judge.py approve TAKE <mult> "<reason>"   |   approve SKIP "<reason>"
        │
        ▼
   <signal file>  →  MQL5 EA (millisecond execution + exit management)
        │
        ▼
   <fills csv>  →  Claude reviews its own results → improves the next call
```

**Why a signal file and not clicking MT5 buttons:** the file carries the exact side, lot
and timestamp, executes in milliseconds, is logged end-to-end, and cannot misfire because
a window moved. UI clicking is strictly worse and was deliberately rejected.

### Markets currently wired

| | XAUUSD (weekdays) | BTC (24/7, weekend) |
|---|---|---|
| Volume/price feed | `OANDA:XAUUSD` | **`COINBASE:BTCUSD`** |
| Data file | `oanda_m1.csv` | `btc_m1.csv` |
| Signal file | `case_signal.json` | `btc_signal.json` |
| EA | `CaseSignalExecutor.mq5` | `BtcCaseExecutor.mq5` |
| Magic | 88020 | 88022 |
| Fills log | `caseexec_fills.csv` | `btc_fills.csv` |
| Scale factor k | 1.0 | **4.5** (BTC M1 range 5.19 vs XAU 1.15) |
| Exit (stop/arm/give/tp) | 3 / 0.3 / 0.2 / 3 | 14 / 1.4 / 0.9 / 14 |

All paths are in `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\`.

**Volume feed matters more than anything else.** OANDA's BTC volume is unusable —
spike ratio 1.37×, only 71 distinct values in 300 bars, i.e. **no detectable UHV**.
Coinbase gives real traded volume with spikes to 212× median. For gold, OANDA volume is
correct and MT5's tick-count volume is *wrong* (same candle: MT5 451 vs OANDA 2132) —
this single mismatch cost six months.

---

## 4. THE OPERATING LOOP — what Claude does, every cycle

```bash
PY="C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
cd c:/Users/zeesh/Documents/GitHub/turtle
```

**1 — Scan for a parked setup**
```bash
$PY monitor/claude_judge.py scan BTC     # or XAU
```
* `null` → nothing fresh, wait and scan again.
* `{"error": ...}` → fix the cause (§6) before judging anything.

**2 — LOOK at the chart.** Read `monitor/setup_labels/pending_setup.png` with the Read
tool. Actually look: trend structure first, then the setup quality.

**3 — Decide, out loud, in this order**
1. What is the trend *right now* — HH+HL, LH+LL, or neither?
2. Does the requested side agree with that trend? If not → **SKIP**.
3. Is it ranging/shifting? → **SKIP**.
4. Is the breakout a momentum candle with volume below the UHV? If not → **SKIP**.
5. If TAKE: how strong is the context? → multiplier.

**4 — Record the verdict**
```bash
$PY monitor/claude_judge.py approve TAKE 1.0 "why, in one or two sentences"
$PY monitor/claude_judge.py approve SKIP "why"
```
Signals older than **180 s** are auto-marked EXPIRED and not traded — a stale setup fired
at a live price is how money is lost for nothing.

**5 — Review.** Read `<market>_fills.csv` and compare the real P&L against what was
judged in `monitor/claude_judgments.jsonl`. Write down what to do differently.

### Sizing (multiplier)
| Context | mult |
|---|---|
| Textbook: strong clean trend, strong UHV, momentum breakout | 3.0 |
| Good trend, minor blemish | 2.0 |
| Valid but young/thin trend, or bigger picture disagrees | **1.0** |
| Anything doubtful | **SKIP — do not size down into a bad setup** |

Start conservative. The first live vision trade (BTC SELL @ 63,062.96) was deliberately
1.0 even though mechanical strength said 0.84 (=3×), because the downtrend was one
swing old.

---

## 5. STARTUP / RECOVERY — after a crash, restart or outage

```powershell
$py   = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
$pyw  = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\pythonw.exe"
$repo = "C:\Users\zeesh\Documents\GitHub\turtle"
$CF   = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
```

1. **TradingView + CDP** — needs `:9222` alive:
   `powershell -NoProfile -ExecutionPolicy Bypass -File $repo\bootstrap\launch_tv.ps1`
   If TV is already open *without* the debug port, **kill every TradingView process first**,
   then relaunch — otherwise CDP never comes up.
   Set the chart to the right symbol (`COINBASE:BTCUSD` on weekends, `OANDA:XAUUSD` on weekdays).
2. **Bridge** — `Start-Process $py "monitor\oanda_bridge.py","--out","$CF\btc_m1.csv","--loop","20"`
3. **Dashboards** — `pythonw monitor\home_uptime_guard.py` (heals :3457 + cloudflared)
   and `pythonw monitor\serve_setup_labels.py` (:8765).
4. **MT5** — the right EA attached to the right chart, **Algo Trading ON**, **demo account**.
5. **Verify before judging anything:**
   ```bash
   cat "$CF/btc_m1.symbol"        # must contain BTC (or XAU) as expected
   stat -c '%y' "$CF/btc_m1.csv"  # must be within ~1 minute of now
   ```
6. Resume the loop at §4.

**Do NOT run** `btc_live_matcher.py` / `oanda_live_matcher.py` — those are the old
auto-firing rule engines. They are superseded by Claude's judgment and must stay stopped,
or they will trade without a verdict.

---

## 6. FAILURE MODES ALREADY MET (and their fixes)

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard says market OPEN, MT5 says "Market closed" | session clock ignored the day of week | FX week = Sun 21:00 → Fri 21:00 UTC (fixed in `status.html`) |
| EA fires an old setup on re-attach | no staleness check | matcher stamps `ts`; EA ignores signals > 180 s old |
| Every fresh signal looked "5 h stale" | `datetime.utcnow().timestamp()` treats naive UTC as **local** | use `time.time()` |
| EA refuses to start | symbol guard (BTC EA on a gold chart) | attach to the correct chart — the guard is working as designed |
| `[not enough money]` | 0.40 lots on a $309 account | size down; check free margin before promising anything |
| Detector blind to the real UHV | MT5 tick-count volume ≠ OANDA volume | always detect on the exchange feed, execute on the broker |
| Data symbol suddenly wrong | someone switched the TradingView chart | `.symbol` marker + guard → the loop holds instead of trading nonsense |
| Cloudflare 1033 while local is fine | tunnel process alive but edge connection dead | guard re-checks the public URL every ~60 s and restarts cloudflared |

---

## 7. WHAT IS *NOT* HARD-CODED ANY MORE

Deliberately removed from the machine and given to Claude's eyes:
- trend direction and trend quality,
- ranging / trend-shift detection,
- whether the context deserves size at all.

Still mechanical (fast, deterministic, no judgment needed): bar building, retracement/UHV/
breakout geometry, volume comparison, order execution, stop and trailing exit.

---

## 8. SELF-IMPROVEMENT LOOP

- Every verdict lands in `monitor/claude_judgments.jsonl` with the reason.
- Real outcomes land in `<market>_fills.csv` (broker truth).
- After ~10 judged trades: join the two, and ask **two** questions —
  1. *Which SKIPs were killers avoided?* (the value) and
  2. *Which SKIPs were winners missed, and did they share a pattern?* (the cost).
- Publish losers to `setups.claudezeeshan.com/losses.html` and let **Zee comment**. His
  comments have produced every genuine improvement so far; a numeric sweep has produced none.
- Never stack two changes at once. One change, then live evidence.

---

## 9. THE FIRST LIVE VISION TRADE (for the record)

```
2026-08-02 15:54 UTC · BTC · SELL @ 63,062.96 · mult 1.0
Claude's reason: peak 63117 → low 63065 → bounce only 63085 (LOWER HIGH) → 63052
(LOWER LOW). UHV vol 5.7 at the retracement top, breakout a strong red momentum candle
(body 0.95) on lower volume. Selling WITH the trend. Small size because the downtrend is
one swing old and the 45-minute picture is still up.
```

---

## 10. DOCTRINE (do not relearn these the expensive way)

1. **Zee's eye is ground truth.** Mechanise it; never overrule it.
2. **The simulator lies.** Validate on real fills only.
3. **A big loss eats ten small wins.** Avoiding killers beats catching winners.
4. **Skipping a winner is cheap; taking a killer is not.** When unsure, SKIP.
5. **One change at a time**, then live evidence. Nine versions died of stacked "fixes".
6. **Demo until proven.** Real money only on Zee's explicit word.
7. **Say it straight.** If it is losing, say it is losing, with the receipts.

*Written the day the machine stopped guessing at "trend" and started looking at the chart.*
