# Saad_strategy_15min v1.26

**Gold (XAUUSD) on 15-minute candles. Magic number 88302. Released 2026-10-19.**

v1.26 is the Saad 15-min EA with Zeeshan's TradingView chart setup built in as its default settings. Attach it to a XAUUSD M15 chart without changing anything and it trades exactly what the chart showed.

| | v1.26, pure defaults | v1.23 (the previous settings), same lots |
|---|---|---|
| Net, Jan 1 – Oct 16 2026 | **+$213,915** | +$238,448 |
| Profit factor | **2.54** | 1.30 |
| Win rate (whole trades) | **53.9%** | 45.4% |
| Trades | 191 | 932 |
| Average per trade | **≈ +$1,120** | ≈ +$256 |
| Max drawdown | $35,172 (13.8%) | $30,724 (11.3%) |
| Red months | June only (−$11.0k) | October only (−$5.1k) |

All of these are MT5 Strategy Tester results: Blueberry's real XAUUSD ticks (custom symbol `XAUUSD_BB`), every tick, random execution delay, $100,000 account, 2 lots.

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct 1–16 |
|---|---|---|---|---|---|---|---|---|---|
| +4.1k | +15.7k | +52.0k | +28.3k | +37.3k | **−11.0k** | +4.6k | +63.9k | +7.9k | +11.0k |

**Going back to v1.23's behaviour:** set EMA 9/50, InpExitMode 0, all boxes to 1 and lots to 1. v1.23's file is also in the git history.

---

## What is in this folder

| File | What it is |
|---|---|
| `README.md` | This description |
| `Saad_strategy_15min_v1.26.mq5` | The EA source code exactly as released (the live copy is `mt5/Saad_strategy_15min.mq5`) |
| `saad_15min_indicator.pine` | The TradingView indicator code the setup was built on, for studying later |
| `indicator_settings.md` | Every indicator setting at the moment of release (160 settings), as a table |
| `indicator_settings.json` | The same settings as data (and their EA input names), so Claude can re-apply them to the chart |

---

## How we got here

### 1. One minute did not work

The goal for weeks was a working EA on the **1-minute** chart. Everything we tried was tested in MT5 on Blueberry's real ticks, and none of it held up over the whole year:

- **Zee's "93%" 1-minute chart** (93% win rate over the chart's last week) lost **−$92,690** over the year in MT5, PF 0.85.
- **The random-entry test** settled it. A random entry with the same stop and target wins about the same share of trades as the Saad entry. On 1 minute the Saad entry has **no edge**: the spread eats a ~$0.77 target. On 15 minutes the Saad entry earns **+$190 a trade** where random earns +$0.40.
- **The defended genetic search on 1 minute** (session hours, sweep entry, cost gate, ADX, ATR band, hard TP, Fibonacci targets…) found settings with PF up to 1.69 on Jan–Jun. Of the top 150, **5 made money on Jul–Oct**, and none by much (PF ≤ 1.05).
- **The "V1" best-drivers setting** made +$30,096 on 1 minute in Jan–Jun and lost −$4,956 in Jul–Oct. On 5 minutes it roughly broke even.

So we went back to **15 minutes**, where the entry has a real edge.

### 2. The 15-minute baseline: v1.23

Saad_strategy_15min v1.23 (Zee's 15-min settings, EMA 9/50) was already the steady performer: about +$121k a year at 1 lot, PF 1.31, only October slightly red. Two attempts to tune it **failed on months they had not seen**:

- **The self-tuner** (a tree search pruned month by month, then an ensemble vote): every tuned set lost on Sep–Oct, while v1.23 stayed green.
- **The MT5 genetic optimizer on 15 minutes**, 1,500 passes before a PC restart stopped it. Its top 30 Jan–Jun results were run on Jul–Oct: **0 of 30 beat v1.23.**

The lesson: tuning entry filters on past months finds settings that only fit those months.

### 3. What changed the picture: Zee's chart, with new tools

The breakthrough came from Zee tuning the TradingView indicator by eye, with features we added to the indicator during this work:

| Feature added | What it does | Where |
|---|---|---|
| **EXIT LAB** (whole chart) | Runs ~20 different exits on the same entries, so the best exit is visible | Indicator, bottom left |
| **TP1 METHOD "Next EMA beyond the entry"** | The EXIT LAB's best exit as a real setting | Indicator → EA v1.25 `InpExitMode` 1 |
| **Entry position in the range** (whole chart) | Which part of the recent range each entry came from, and how those trades did | Indicator, top left |
| **Range boxes + "stand aside"** | Untick the parts of the range that lose; "stand aside" sits out while such a trade would have run | Indicator; EA chart-test copy → v1.26 |
| **EA FILTERS** | Trading session (London / New York / both / overlap), ADX, ATR band, all calculated the MT5 way | Indicator; EA v1.24 |
| **Win rate by weekday** | Showed Fridays are among the best days, not the worst | Indicator, top right |
| **Every day on the chart** | The daily list now shows every day, including days with no trades | Indicator, top right |

Zee's chart settings were then tested in MT5 through a **test copy** of the EA that added what the EA lacked (range boxes and stand aside). Each step was checked in MT5 over the **full year**:

| Step (full year, MT5, 2 lots) | Net | PF | Max DD | Red months |
|---|---|---|---|---|
| Chart settings, first try | +$228,316 | 1.92 | $52,950 | Jan −$40.5k (the Jan 30 gold crash), Jun |
| Chart settings after Zee's next changes | +$188,894 | 2.42 | $30,604 | Jun |
| **+ Zee's updated range boxes = v1.26** | **+$213,915** | **2.54** | $35,172 | Jun |

What each piece is worth (same entries, one piece removed, MT5 full year):

| Without… | Net | PF |
|---|---|---|
| the new exit (normal TP1 instead) | +$75,619 | 1.57 |
| the range boxes | +$113,144 | 1.31 |
| "stand aside" (skip instead) | +$175,054 | 2.16 |
| *(the full v1.26 setup, for comparison)* | *+$188,894* | *2.42* |

(These comparisons used the chart settings one step before the final boxes.)

### 4. Things we tested and did NOT add

| Idea | Result in MT5 | Why it was left out |
|---|---|---|
| Max risk $20 to fix January | Fixed the old January (+$2.2k) | Kept at $20: it is Zee's own rule, and with the final settings it changes almost nothing |
| Trend filter (30 min / 1 h / 4 h) to fix June | Only the 30-min one turned June green | Cut trades from 181 to 84 and profit from +$189k to +$87k, and turned three other months red |
| ATR ceiling ($10 – $20) | Similar to max risk | Not needed with the final settings |
| "Close back across the slow EMA" exit | Big profits but a 26% win rate | Too lumpy, 5 red months |
| Skipping Fridays | Fridays were among the best days | Would have cost about −$43.7k a year |

---

## How v1.26 trades

### Entry (unchanged Saad setup, Zee's 15-min numbers)

1. **Setup candle**: a pin bar, hammer / shooting star or marubozu (wick ≥ 0.45 of the range, body ≤ 0.60, range ≥ 0.55 × ATR).
2. **On the EMA**: the candle touches the **fast EMA 16** or **slow EMA 32**, within a 1-pip ($0.10) tolerance. LONG setups use either EMA; SHORT setups use the fast EMA.
3. **The break**: price must break the setup candle's high (BUY) or low (SELL) by **3 pips** ($0.30) within **1 candle**. The entry is at market on that break.
4. **Filters** that must pass:
   - **ADX(14) ≥ 30** on the last closed candle. This is MT5's own ADX formula.
   - **Range boxes**: the entry's position in the last **7 closed candles'** range must be in a ticked box (5% buckets):
     - BUY boxes `111110010100001010111`
     - SELL boxes `111111100010001001110` (1 = trade, 0 = unticked)
   - **All hours.** There is no session filter, because the London + New York filter tested worse.
   - **No chop filter.**
5. **One trade at a time.** While a trade runs, or while a "stand aside" ghost runs, new setups are ignored.

### TP method: "Next EMA beyond the entry" (`InpExitMode` = 1)

- **At the entry** the EA looks at the two EMAs, live on the forming candle:
  - For a **BUY**, it finds the EMAs **above** the entry price.
  - For a **SELL**, it finds the EMAs **below** the entry price.
  - If both qualify, it takes the **nearer** one. That EMA is the target.
- **The whole position closes** when price touches that EMA. A BUY closes when the bid reaches it, a SELL when the ask reaches it. The EMA moves with every candle, so the target follows it.
- **No EMA beyond the entry?** Then there is no target. The trade closes at the next candle's open after a 15-min candle **closes back across the fast EMA** against the trade.
- **No partial close, no TP2/TP3 and no broker-side TP.** The EA watches the target itself, tick by tick.

This is the exit that made the difference: on the same entries it took the year from **+$76k (PF 1.57)** with the old TP1 to **+$189k (PF 2.42)**.

### SL method: ATR stop (`InpSlMode` = 1)

- The stop is **1.6 × ATR(14)** of the last closed candle away from the entry. It is sent to the broker with the order.
  - With gold's 15-min ATR around $5–8, that is about **$8–13**.
- The stop **widens when gold moves fast** and **tightens when it is quiet**.
- **Max risk $20:** if 1.6 × ATR would put the stop more than **$20** away, the trade is **skipped**. This is Zee's rule: "not more than $20 at risk on a 2-lot trade". It keeps the EA out of crash candles like January 30th, where a $125 stop cost −$25k before the cap existed.

### Breakeven policy

- **No breakeven.** Once the trade is open, the stop **never moves**: no breakeven, no lock and no trailing. This matches the EXIT LAB row the method came from: the first stop stays until the target or the stop is hit.
- The older v1.23 rules (breakeven at 75% of the way to TP1, a partial close at TP1, a $2 trail after TP1) apply only with `InpExitMode` 0.
- **Day close:** 3 minutes before the broker's daily close, a trade that is **in loss** is shut. A trade in profit is kept (`InpCloseLossMins` 3).

### Stand aside (`InpBandOff` = 1)

- When an entry falls in an **unticked range box**, the EA does **not** open a real trade.
- Instead it follows a **ghost trade** with the same stop and the same exit. Until that ghost would have closed, **no new trade is taken.**
- Why it matters: right after a bad-zone entry, the market is often still in the same bad state.
- MT5 full year: "stand aside" beat simply skipping by about **+$14k** and had a lower drawdown.

### Risk management

| Rule | Setting | Value |
|---|---|---|
| Lot size | `InpLots` (fixed, `InpRiskPct` 0) | **2 lots**; change it for smaller accounts |
| Skip trades with a far stop | `InpMaxRiskUsd` | **$20** of price distance (= $4,000 at 2 lots) |
| Positions at once | `InpMaxPos` | 1 |
| Shut losers before the daily close | `InpCloseLossMins` | 3 minutes |
| Cancel a waiting setup across the close / weekend | `InpGapCancel` | on |
| Daily loss / profit stop | `InpDayLossUsd`, `InpDayTargetUsd`, `InpDayLossPct` | off (0) |
| Spread filter | `InpMaxSpreadPts` | off (0) |

What to expect at **2 lots on $100k** (MT5 full year):
- **Worst drawdown:** $35,172 (13.8%).
- **Worst month:** June, −$11.0k. Gold fell all month and the BUY setups kept getting stopped out. A trend filter fixes June but costs far more than it saves, so it was left out.
- **Average trade:** about +$1,120. **Win rate:** 54%. **Profit factor:** 2.54.

Scale everything with the lot size: at 0.20 lots, divide the dollar figures by 10.

---

## Honest caveats

- **Part of this setup was tuned on the same year it was tested on.** The chart only holds about Aug–Oct, so Zee tuned by eye on those months. Two SELL boxes were chosen after seeing the full-year range table. **Jan–Jul were never on the chart**, and the setup made money in 6 of those 7 months. That is encouraging, but live results should be expected to come in **below** the tester.
- **Fewer trades means more luck per trade.** 191 trades a year is a smaller sample than v1.23's 932, and a few big wins (for example the SELL 85–90% box) carry weight.
- **Spread and execution:** the tester used Blueberry's real spread plus random delay. With about 190 trades a year instead of 930, costs matter less than for v1.23.
- **Demo first.** v1.26 shares magic number 88302 with v1.23. To run them side by side, give one of them another `InpMagicNumber`.

---

## Receipts

- MT5 report of the release test: rig `C:\mt5_rig_axi\reports\v126_defaults.htm`, run with pure defaults and random delay.
- Months: `monitor/strategy_lab/v126_defaults.json`.
- Step-by-step tests:
  - `monitor/strategy_lab/s15_chart_mt5.py`, `s15_chart_mt5_now.py`, `s15_chart_newranges.py` (chart setups)
  - `s15_chart_janfix.py` (max risk / ATR caps)
  - `s15_chart_htf.py` (trend filters for June)
  - `s15_rangetable.py` (the full-year range table)
- Ledger: `VERSION.md` and `VERSION_HISTORY.md`, entry *Saad_strategy_15min v1.26*.
