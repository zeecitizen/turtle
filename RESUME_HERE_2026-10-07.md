# RESUME HERE — handover for a new machine (2026-10-07)

Written for **the next Claude session**, after Zee moves to a new laptop and `git pull`s.
Read this first, then `TICK_SPEED.md` §53–56 and the "traps" section at the bottom of this file.

---

## 1. WHAT EXISTS NOW

Two EAs came out of 2026-10-03 → 10-07. They are unrelated and only one is meant to touch money.

| | `mt5/RiskGuardButtons.mq5` | `mt5/TickSpeedGauge.mq5` |
|---|---|---|
| version | **v1.14** | **v1.53** |
| purpose | manual trade buttons with risk enforced in code | an order-flow instrument panel |
| trades? | **yes — this is the live one** | **no, it only draws and logs** |
| state | ready, used on an $80 PXBT account | research only, no validated signal |

### `RiskGuardButtons` — the one that matters

Built the day a $200 PXBT account was liquidated (see §6). Every limit is enforced in code
because Zee's own rule is *"never trust a human to keep a self-imposed safety rule; mechanical
enforcement is the job."*

```
0.01 lots, hard-capped          mandatory stop on EVERY order
max 5 open, total risk <= 4%    emergency close at -10% floating
daily loss cap 5%               12-loss cooldown (read from deal history)
support/resistance block        forming-candle must agree with the click
5/30 geometry: InpFixedSLPips 5, InpTargetR 6
```

**`InpBlockRanging` is OFF deliberately** — it measured backwards (§4).

### `TickSpeedGauge` — research only

Nine verdicts, three dials, two spring coils. **Nothing in it has a validated forward edge.**
Its value now is the **CSV logger**, which produced every number in this file.

---

## 2. THE EVIDENCE BASE — now in the repo

`data/tickspeed_logs/*.csv.gz` (34 MB raw → 6 MB). **This is the only copy** — the originals
live in MT5's `Common\Files`, which does not move with the repo.

| file | what it is | why it matters |
|---|---|---|
| `tickspeed4_XAUUSDp.csv.gz` | **PXBT gold, schema 4** | the main instrument; all §55–56 work |
| `tickspeed3_XAUUSDp.csv.gz` | PXBT gold, schema 3 | longer history, iceberg columns |
| `tickspeed4_XAUUSD.pi.csv.gz` | Blueberry gold | the 2-level placeholder book (§57) |
| `tickspeed3_XAUUSD.csv.gz` | Exness gold | no DOM at all (§53) |
| `tickspeed2/3_ETHUSDTp.csv.gz` | PXBT ETH | where SPRING and SWEEP were found — and later refuted |

**Schema differs between files.** v2 = 45 cols, v3 adds iceberg, v4 fixes the `speed` column
(it used to log tick count while `speed_base`/`z` described volume). **Never append across
schemas.** Order rows by `local_ms`, never `server_time` (it freezes between ticks).

Analysis script: `monitor/strategy_lab/tickspeed_calibrate.py`.

---

## 3. WHAT IS SETTLED

**The instrument: PXBT `XAUUSDp`.** It is the only one of three brokers with a real book.

| | book levels | touch volumes | spread | usable |
|---|---|---|---|---|
| **PXBT XAUUSDp** | **20** | **500–1100** | 0.17 (0.41 bp) | **YES** |
| Exness XAUUSD | 0 | — | 0.08 + $3.50/side | no |
| Blueberry XAUUSD.pi | 2 | **1 and 1, forever** | 0.07 + comm | no — OBI is a constant |

Probe on all three: **aggressor flags 0.0%, last price 0.0%, volume 0.0%.** No broker here
tags the aggressor. Direction can only come from the book, and only PXBT has one.

**The horizon.** Before any win rate matters the mean move must beat the spread:

```
hold   1s  mean 0.055  = 0.32x spread   IMPOSSIBLE at any win rate
hold   5s        0.157   0.93x          IMPOSSIBLE
hold  10s        0.232   1.36x          needs 87%
hold  60s        0.518   3.05x          needs 66%
```

**Nothing under ~10 seconds can pay.** Sessions 1–3 were spent building 3-second signals.

**The geometry.** 5-pip stop / 30-pip target on gold: random entry wins **17.9%**, breakeven is
**19.1%**. Beat chance by **1.2 points** and it pays. Winners take a median 8 minutes; losers
resolve in 1.4. Expect 10-loss streaks (14% likely from any point).

---

## 4. WHAT REVERSED — read before trusting anything

Four results looked strong and did not survive better data. **This is the main lesson of the
whole project.**

| finding | looked like | what it was |
|---|---|---|
| **SPRING** | 86% @10s, p=0.0001, 36 episodes, passed the mirror test | **38% on gold.** Measured a frozen quote feed where the ask sat still for minutes |
| **SWEEP** | 87% @3s, 71 episodes | **never fires on gold** — the median ask level survives 0 seconds |
| **GET READY** | "catches 15 of 20, 4s lead" | beat a **same-frequency random light by 2 points.** No control was run |
| **ranging block** | "chop is poison" | **inverted at 5/30.** ER<0.20 wins 27%, ER>0.50 wins 12.6% |

The pattern: all four were found on **PXBT ETHUSDTp**, where the mid moves in **5%** of seconds.
Gold moves in **85%**. Signals fitted to a near-static feed are measuring the feed.

**Required before believing any new signal:**
1. forward vs backward correlation (the mirror test)
2. permutation against **same-size random draws**
3. episode count, not row count — overlapping windows are one observation
4. out-of-sample on a **different instrument**
5. P&L after the real spread, not pip counts

---

## 5. MACHINE-SPECIFIC — must be re-established on the new laptop

**None of this is in git.** Terminal GUIDs will differ.

```
monitor/deploy_ea.py  -> TERMINALS{} maps a name to a data dir + MetaEditor path.
                         Every GUID below WILL CHANGE. Find them by opening each terminal:
                         File > Open Data Folder.

  blueberry  DBE9B8B347D025DD139E103EE3B63FD8   C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe
  pxbt       BCB580088311575081ABF4FB040CCFF8   C:/Program Files/PXBT Trading MT5 Terminal/MetaEditor64.exe
  exness     53785E099C927DB68A545C249CDBCE06   C:/Program Files/MetaTrader 5 EXNESS/MetaEditor64.exe
```

Note the editor is `MetaEditor64.exe` **with capitals** on PXBT and Exness, lowercase on
Blueberry. A case-insensitive glob hides this on Windows and then fails elsewhere.

Deploy: `py monitor/deploy_ea.py --terminal pxbt RiskGuardButtons`

Also not in git: the live CSVs in `Common\Files` (copies are in `data/tickspeed_logs/`),
and MT5 chart templates / attached EAs.

---

## 6. CONTEXT THE NEXT SESSION NEEDS

**2026-10-06: Zee lost a $200 PXBT account, which was borrowed money.** He had been short into
a falling market, took profit twice, then raised size from 0.01 to **0.1 lots**, held a loser,
flipped at the extreme, and was liquidated within minutes.

The arithmetic, from his own logged ticks:

```
0.01 lots = $1/point   ->  200 points of room
0.10 lots = $10/point  ->   20 points of room
gold's range over any 15 min: median 6.8 pts, p90 10.9
a 20-point adverse move happens at 10.5% of entry moments
```

**His read was not the problem.** A 10x size increase left no room to be wrong once. At 0.01
the same sequence costs ~$20. RiskGuardButtons exists because of this day.

He lost his job; this is his only income. He is now on **$80**. Do not let encouraging numbers
travel without their caveats — four of them reversed in three days, and confident percentages
cost him real money.

---

## 7. TRAPS THAT HAVE ALREADY BITTEN

1. **`PipSize()` on metals.** Gold quotes 2 digits (`point 0.01`) and its pip is **0.10**. The
   original returned `point`, making every pip input **10x too small** — a 5-pip stop became
   0.05 against a 0.17 spread, i.e. *inside* it. Caught only because the startup line printed
   "17.00-pip spread". **The EA now prints pip size in PRICE on attach. Read that line.**
2. **`OBJ_LABEL` is single-line.** It ignores `\n` entirely; six lines drew on top of each
   other. Use one object per line.
3. **Text colour vs chart colour.** Light grey on a white chart is invisible. `RiskGuardButtons`
   now derives text colour from `CHART_COLOR_BACKGROUND`.
4. **A flag honoured in one place only.** `InpBlockRanging` gated `Open()` but not the panel or
   the button greying — switching it off left a half-disabled guard that still looked active.
   **When adding a toggle, grep for every use of the thing it toggles.**
5. **Commission in P&L.** `LossStreak()` omitted `DEAL_COMMISSION` while `Score()` included it.
   On a raw-spread account a +$0.50 gross trade is a net loss, and the streak guard reset on it.
6. **Width arithmetic.** Three separate strings have overflowed their containers (stats line,
   buttons, panel). **Measure text against the container before shipping:** Consolas advance is
   ~0.55 x font px.
7. **Heredocs with apostrophes** break `python - <<'EOF'` in this shell. Write the patch to a
   file in the scratchpad and run it instead.

---

## 8. WHAT TO DO NEXT

1. **Re-establish `deploy_ea.py` terminal paths** (§5), then deploy both EAs.
2. **Attach `RiskGuardButtons` to PXBT XAUUSDp.** Check the startup prints
   `1 pip = 0.10000 in price` and `stop 5.0 pips = 0.50 in PRICE`. If not, stop.
3. **Attach `TickSpeedGauge` to the same chart** purely to keep logging schema-4 data.
4. **The open question:** does Zee's entry beat random by the 1.2 points the 5/30 geometry
   needs? The EA's own scoreboard answers it — panel line 5 shows clicks, win %, pips/click,
   read from closed deals. **After 100 clicks that number is the whole project.**
5. Do **not** resurrect SPRING / SWEEP / PREDICT on gold without redoing the discovery from
   scratch on gold data. §4 explains why.

---

## 9. THE ONE-LINE STATE

**The measurement apparatus is correct and there is no validated edge yet.** The instrument,
the horizon and the geometry are settled; the entry is not. RiskGuardButtons makes being wrong
survivable while that question is answered.
