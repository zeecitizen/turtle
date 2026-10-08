# winning_indicator.md — where the TradingView indicator work stands

**Read this first in a new session** (then `LAWS.md` — Zee's, never edit it — and
`VERSION_HISTORY.md`). Last updated 2026-10-09 (PKT night session, 2026-10-08/09).

## 1. What we are building

`turtle.pine` (TradingView, OANDA:XAUUSD, **1-minute**) draws Zee's UHV setups so he can trade
them **by hand**: he enters at the breakout and exits the moment he is in profit. The goal of
the session: a stats panel whose numbers can be trusted, a win rate he can tune himself, and an
MT5 test that proves (or disproves) the edge on real broker ticks.

## 2. The indicator today (what changed this session)

- **Camel humps = the trend.** Rounded arches over every swing (hump size `camPiv` = 1, every
  low counts). Arch colour = trend: **green = the hump ended on a higher low than it started**
  (uptrend, buys only, red retracements, red UHVs), red = mirror. Retracements may only START
  under a matching hump (`camRet`); an unfired setup is cancelled when the camel turns against
  it ("Setup cancelled: trend turned"). Breakout signals need the same trend (`camOn`).
- **Retracements are backdated** to where price really began them (first body close past the
  last opposite candle's low/high), so the UHV is the loudest candle of the whole pullback.
- **Strong trend** (`camStrong`, default 2 humps in a row): a breakout louder than the UHV is
  allowed (Zee: "with the trend, even a high volume breakout can give a great result").
- **UHV body rule off** by default (UHV only needs the highest volume); on the chart it is ON
  (see §4).
- **Removed:** alerts/PineConnector, risk-management group, no-trade windows, the old trend-MA
  paintbrush, the margin-risk block, developer mode, settings snapshot.
- **Labels:** compact BUY/SELL (full details on hover), plain-English "No BUY: <reason>" tags,
  ⏱ timer exits, and each label ends with its breakout-test verdict, e.g. `✅ best +1.41 ($14.1 on 0.1 lot)`.
- **Instant at Breakout is honest on history** (two fixes): it fires when the high/low passes
  the trigger, never on the close; and the trigger is **armed at the previous candle's close**,
  so the breakout candle can no longer change its own setup (before, failed loud breakouts
  silently erased their own signals — losers missing from history). Entry = the trigger, or the
  open if the candle opened beyond it. Rules that need the finished candle (colour, breakout
  volume) are skipped on history in Instant mode; trend/HTF use the finished previous candle.

## 3. The stats panel (verified)

Rows 2-4 are the **BREAKOUT TEST**, Zee's definition: a label WINS if price moved our way by at
least the spread + `scMin` ($ on 0.1 lot) within the rest of the breakout candle + `scN`
minutes. Shown: won/total %, BUY/SELL, today, older/newer half, average best move, and a
**random-entry baseline** on the same test with the **edge** (ours − random). Today = midnight
PKT everywhere. Win counting is the same in every row.

**Checker:** `python pine/verify_panel.py` recomputes every signal from raw candles and compares
every test-row number. PASS on 500, 162 and 193 signals and under three settings; FAILS when fed
a wrong spread (self-test `--mutate`). **Run it after any code change.**

The test is a **zero-delay upper bound** (candles cannot model exit speed). Use it to compare
settings with each other and with random — the absolute number comes from MT5 (§5).

## 4. Results

**Panel (TradingView, 28 Sep – 8 Oct, Instant, $1 on 0.1 lot, candle + 1 min, random = 84%):**

| setup | labels | win | halves | edge |
|---|---|---|---|---|
| pre-loop settings | 500 | 91% | 92/91 | +6.8 |
| **UHV body ≥50% + 1-hour candle aligned (`uUHVBdOn`, `uHTD=60`) — on the chart** | 193 | **94%** | 93/95 | +9.4 |
| structural trend + 1-hour aligned | 124 | 96% | 95/97 | +11.5 |

**MT5, real Prime XBT ticks, random delay, 0.1 lot** (`test_tv_indicator_on_mt5.py`):

| exits | our 193 signals (178 traded) | random entries, same exits |
|---|---|---|
| TP $1, no stop | **77.0%, +$0.96/trade (+$171)** | 73.5%, −$1.74/trade |
| TP $5, no stop | **70.8%, +$0.78/trade (+$139)** | 59.8%, −$1.79/trade |
| TP $1, stop $5 | 47.8%, −$0.45 | 49.4%, −$1.72 |
| TP $5, stop $5 | 43.3%, −$0.30 | 37.6%, −$1.62 |

→ an edge of +$1.3 to +$2.7 per trade over random in every exit setting; profitable without a
stop. **Caveats:** in-sample (the chart filters were chosen on this same history) — the proof
is the NEXT days; 178 trades; losers average about −$9.

**Random entries can never be made positive** (MT5 optimizer, 828 combinations: TP $1-10,
stops none/$1-20, time 1-16 min, random / always-buy / always-sell / follow-colour /
fade-colour, every 3rd or every other candle): **0 profitable**, all ≈ −$1.70/trade = the
$0.17 spread on 0.1 lot. Exits only reshape a random entry's loss; only the entry can carry
an edge. Exit speed matters: random entries "touch" $1 profit 86% of the time, but bank it
80.6% at 0 ms, 72.8% at 200 ms, 58.8% at 1 s, 52% at MT5 random delay; a server-side TP
recovers most of it (72.3%) — and still loses −$2.25/trade (break-even at that payoff ≈ 92%).

Measured broker facts (Prime XBT XAUUSDp): spread $0.17 average, no commission, stop level 0,
server clock = UTC (calibrated each run). The panel still assumes $0.13 spread — consider 0.17.

Earlier this session (superseded, kept for the record): the Candle-Close "in profit exactly
60 s later" loop topped out at ~71% (`pine/lab/WINRATE_LOOP_2026-10-08.md`); Zee preferred the
pre-loop indicator and reverted; the loop version is `pine/lab/turtle_winrate_loop_version.pine`.

## 5. Tools (all on this PC)

| tool | what it does |
|---|---|
| `launch_tv_bridge.bat` | start TradingView Desktop (MSIX) with the CDP bridge on :9222 |
| `pine/inject_pine.py` | put `turtle.pine` into the Pine Editor and compile (save is unreliable — use tv_lab) |
| `python pine/tv_lab.py push` | inject + save (retries) + make sure the CHART runs it (adds a fresh copy and carries every setting over BY NAME if the old copy is stuck) |
| `python pine/tv_lab.py set name=value …` / `get` / `score` | chart settings by Pine name; read the panel |
| `python pine/tv_sweep.py plan.json out.jsonl` | run many settings on the real indicator, log scorecard per run |
| `python pine/verify_panel.py` | independent check of the panel against raw candles (`--mutate` = self-test) |
| `python test_tv_indicator_on_mt5.py [--tp 1 5] [--sl 0 5] [--window 1] [--delay -1]` | **the indicator's signals in MT5 on real ticks vs random entries, same exits** |
| `mt5/SignalReplay.mq5` | replays exported signals (Common\Files\tv_signals.csv): waits for Prime XBT's own cross of the same UHV candle, server TP/SL from the fill, time exit; also exports broker candles for clock calibration |
| `mt5/RandomTouch.mq5` | random-entry baseline (modes: random/buy/sell/follow/fade colour, server TP/SL, time exit) |
| `mt5/run_rig.ps1` | one tester pass (`powershell -ExecutionPolicy Bypass -File mt5\run_rig.ps1 -Ea X -Inputs "a=1;b=2" -Exec -1`) |
| `C:\mt5_rig_pxbt` | portable copy of the Prime XBT terminal used for ALL tests — the live terminal is never touched |

Python here: `C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe`.
PowerShell scripts need `-ExecutionPolicy Bypass`.

## 6. Traps that cost time — do not rediscover

1. The Pine Editor Save click often does not land; the chart's copy often keeps an OLD version
   after a save → always `tv_lab.py push`, which checks both.
2. Chart settings are stored by POSITION (`in_N`): add new inputs at the END; after removing
   one, re-apply by name (tv_lab does it).
3. Setting a string option as a number (uHTD=15 instead of "15") breaks the script ("Calculation
   failed") — tv_lab keeps the setting's own type now.
4. TradingView's 80,000-token compile limit: inject_pine treats it as a warning; save shows it.
5. Pine evaluates both sides of `and`; `for i = a to b` counts DOWN when a > b — guard empty arrays.
6. Writing Pine through a bash heredoc + Python mangled `\n` and emoji — write patch scripts to
   files (see `pine/lab/patch_*.py`).
7. MT5 remembers the last inputs per EA: always pass every input in the tester ini.
8. A candle-based test can't know exit speed; anything "touched within X" is a zero-delay bound.

## 7. Next steps

1. **Out-of-sample:** rerun `test_tv_indicator_on_mt5.py` on days after 2026-10-08 only — the
   real verdict on the +$0.96/trade.
2. Set the panel spread to $0.17 (`uSpread`).
3. Find the loss exit that matches how Zee cuts losers (the −$9 average loss decides it).
4. "No SELL: …" tags for refused sells (only buys have them).
5. Later: a native MQL5 port for live auto-trading (volume from OANDA per LAWS.md).
