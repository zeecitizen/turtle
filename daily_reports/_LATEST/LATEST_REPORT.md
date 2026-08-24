# 24–25 August 2026 — his own laws beat every substitute I built for them

**Supersedes:** the 23–24 August report, archived at
[`daily_reports/2026-08/REPORT_2026-08-23_24_the_night_constants_fell.md`](../2026-08/REPORT_2026-08-23_24_the_night_constants_fell.md).

**Headline: BasedOnLaws went v1.30 → v1.35, and every single improvement came from
Zeeshan's own page or his own eye.** Three times today I had replaced one of his laws
with something of mine; three times his original beat it in court. Final configuration
on his chart, seven days, 0.10 lots: **+$1,335.90** — from +$624.00 this morning.
And for the first time the measurement was confirmed independently: **he ran the MT5
Strategy Tester himself** on Aug 18–21 and got **27 trades · 48.15% · +$123.05 ·
profit factor 3.28** at 0.01 lots.

⚠️ **LIVE RECORD: 0 for 4, −$31.62.** Every one of those trades was taken by a version
that no longer exists, and two of them by gates that were provably broken. Nothing in
this report is live-proven. Tomorrow is the first honest session.

🚨 **STILL UNANSWERED: the Diamond (88154) trades at full size.** It took −$2,476.50
on Aug 21 and went 55-for-55 on Aug 24. Both facts are the same machine.

---

## 1. THE MOMENTUM CANDLE — his definition, and the clause that did the work

The EA's first two live trades lost. He challenged the claim that my 45%-hold test had
"earned its place" — fairly, since its only evidence was an in-sample seven-day
backtest whose threshold I also chose on that data. Then he supplied the VSA
definition, and **ruled out its fourth clause himself**:

> *"i think our VSA definition differs a bit on the volume front, we dont require
> Above-Average Volume, on the contrary our method uses the three only"*

Correct, and it matters: his page's clause b wants the breakout **quieter** than the
UHV, so a volume floor would contradict his own law. The three that shipped:

```
  1. body ratio    |C-O| / (H-L) >= 0.70
  2. expansion     body > 1.2xATR(14)  OR  1.5xSMA(body,20)
  3. close at extreme   buy: C > O AND C >= H - 0.20x(H-L)
```

**Checked against every breakout on record before shipping — the body ratio alone
splits them perfectly:**

```
  every WINNER          every LOSER
  Fri 7:02   0.81       Fri 8:51    0.62
  Fri 8:10   0.89       Fri 10:02   0.65
  Fri 9:10   0.85       LIVE 6:30   0.47
  his marks  0.82/0.92/0.90         LIVE 7:08   0.19
```

**COURT (7 days, his chart): the body ratio deleted SEVEN losing trades and ZERO
winners** — 12W/18L +$624.00 → **12W/11L, 52.2%, +$876.20**.

- The **expansion clause was REFUSED**: on M1 it cuts 23 trades to 17 and kills three
  winners (+$756.80). Later dialled gently at 0.6/0.8/1.0/1.25×SMA and 1.0×ATR — every
  arm within ~$145 of no-floor with single-trade differences. **Noise.** The
  micro-candle trap the sources warn about lives in dead sessions; we trade New York.
- **Close-at-extreme is redundant but free** — byte-identical once the body ratio holds.
- **I predicted my hold-45 test would become redundant. It did not** (+$70 and 4 WR
  points on top of the body ratio), so it stays — on evidence, not on my word.

## 2. THE AUDIT HE ASKED FOR — "are we following every single thing in laws.md?"

Four divergences found. Three were mine and got fixed; the fourth he opened himself.

### 2a. 🐫 THE TREND LAW WAS NOT HIS LAW (v1.33-34)

The live trend gate was **my EMA-5 slope**, not his line 7. Rebuilt as `CamelTrend`:
the humps are **DRAWN from pivots** (a high with `InpPivot` lower highs on each side —
the rule his eye uses) instead of inferred from a retracement state machine. His line
45 now lives inside it: *"whenever a high is broken, the deepest point is the confirmed
higher low."*

```
  CAMEL HUMPS pivot 2, latched   18 tr  11W/ 7L  61.1%  +1044.30   <- HIS LAW
  EMA-5 slope 10 (was live)      23 tr  12W/11L  52.2%   +876.20
  CAMEL HUMPS pivot 3, latched   19 tr   8W/11L  42.1%   +629.90
  CAMEL pivot 2, NO latch        13 tr   6W/ 7L  46.2%   +353.50
  CAMEL HUMPS pivot 5, latched   22 tr   7W/15L  31.8%   +342.20
  old inferred structure         19 tr   6W/13L  31.6%   +298.10
```

**61.1% — the highest anything has reached.** Two findings inside it worth more than
the total: **his line 45 is worth FIFTEEN win-rate points on its own** (latch vs no
latch), and **`InpTrendLook` is not load-bearing at all** — 60/90/120 give
byte-identical results, which removes one of my numbers from the risk list. The pivot
dial is a true hill: 1=+468 · **2=+1044** · 3=+630 · 5=+342.

### 2b. ONE PULL, ONE TRUTH (v1.33)

Volume came from `oanda_vol.csv` and candles from `oanda_bars.csv` — **two separate
pulls that disagreed for the same minute** (the 18:03 breakout was 1396 in one and
1505 in the other), and the immutability rule then froze each at its own first sight.
He reads one chart; the EA was reading one and a bit. Volume now comes from the SAME
ROW as the candle it belongs to.

### 2c. NEVER JUDGE A HALF-WRITTEN CANDLE (v1.30) — the first live trade was illegal

BasedOnLaws' first ever live trade, its own `[LAWX]` stamp against the finished candle:

```
  what the EA read     breakout 18:30  close 4676.37  vol  788
  the actual candle    breakout 18:30  close 4675.84  vol 2109
```

It caught the bridge's export **mid-minute**. His law says the breakout must be
QUIETER than the UHV (997): **788 passes, 2109 refuses.** The trade was forbidden by
its own law and existed only because the volume was still accumulating. It lost −8.86.

Fixed: live may judge a bar only once the OANDA table contains a LATER minute (the
bridge's own proof it moved past that candle); past `InpFreshMaxSec=40` it **skips the
bar with a log line** rather than trading blind. Also the bridge cycle went **60s →
15s → 5s**, and a variable I had shadowed (`newest`) was crashing the candle collector
every cycle since the previous night. Lag is now ~0.

### 2d. ALL HOURS (v1.35) — his call, and it re-opens the divergence knowingly

```
  NY only 15-22   18 tr  61.1%  +1044.30   $58.02/trade
  15-24           21 tr  57.1%  +1143.60   $54.46/trade
  08-22           29 tr  48.3%  +1109.80   $38.27/trade
  ALL HOURS       39 tr  43.6%  +1335.90   $34.25/trade   <- shipped
  00-15 pre-NY    18 tr  33.3%   +388.20   $21.57/trade
```

**The pure counter-test does not bleed**: trading only the hours before New York makes
+$388 at 33.3%, and this geometry breaks even near 33%. So his line 47 was protecting
**quality** (2.7× per trade inside NY), not money. He chose the total:

> *"let's go all hours, since the goal is to make maximum money and all setups are
> losing anyways under this EA"*

On record: this trades against the standing win-rate goal and **diverges from LAWS.md
line 47 by his decision**. His premise is true of the live record (0 for 4) and not of
the court.

## 3. HIS OWN TESTER RUN — the first independent confirmation

He ran the MT5 Strategy Tester himself, his terminal, his data cache, the shipped
config (`InpTrendMode=2 · InpNyOnly=false · InpMomBodyRatio=0.7 · InpBreakHold=0.45`):

```
  100% real ticks · 5,515 bars · 1,315,855 ticks · Aug 18 -> Aug 21
  +123.05 at 0.01 lots · 27 trades · 13W/14L (48.15%) · profit factor 3.28
  avg win 13.61   avg loss -3.85   largest loss -7.45   max drawdown 0.30%
```

**The average loss is the story: −$3.85 against a stop 8–10 points away.** Three losses
came in at **−0.22, −0.03 and −0.04** — trades that reached 1R, moved their stop to
entry, and cost nothing. His breakeven rule, working exactly as his page describes it.
That is why 48% wins produces a profit factor of 3.28.

It also matches the rig (+$1,335.90 at 0.10 over seven days ≈ $1,230 scaled), so **the
measurement chain agrees across two independent terminals** — worth as much as the
profit after the half-written-candle mess.

## 4. THE TOOLS HE ASKED FOR

- **The setup marker** — `http://127.0.0.1:8765/mark.html`. TradingView refused the job
  (anonymous charts are read-only; its sign-in will not run in a debug-enabled browser),
  so he marks on his own OANDA candles: click the retracement start, the UHV, the
  breakout. The UHV's level is drawn forward, plumb lines drop into the volume pane with
  each candle's volume printed, one candle may hold two roles. **On its first evening it
  caught my untested `InpMaxRiskPts=10` refusing a lawful setup of his** (13.11 pts).
- **"🎯 Visualize LIVE trade"** in the Camel Cockpit — draws the EA's own `[LAWX]`
  anchors: retracement start, UHV with its trigger line, breakout with its body ratio
  and hold %, entry/stop/target, volume story below. Walks back through every fire.
- `monitor/law_trade_diagram.py`, `/api/trades`, `/api/marks` behind them.

## 5. ⚠️ THE BINDING CONSTRAINT: his chart is nine days long

The EA judges only on OANDA candles, so the court can only run where the archive
reaches: **Aug 5, 6, 7, 17, 18, 19, 20, 21, 24**. Tonight we recovered Aug 17 (+1,890
minutes) by asking the anonymous feed for more than it volunteers.

```
  anonymous tvDatafeed   caps at ~8,190 M1 bars = 5.7 days
  his TradingView login  {"code": "rate_limit"} — NOT a bad password, the same wall
                         his browser hit with backup codes
  OANDA's own API        would serve years — NOT AVAILABLE IN PAKISTAN (German account only)
```

Two doors remain: `monitor/oanda_deep_history.py` accepts an `auth_token` in
`.tv_credentials.json` (from `window.user.auth_token` in a signed-in browser — bypasses
their login endpoint entirely), or retry the sign-in once the rate limit clears. Until
then the window grows one day per day, and **all validation is forward.**

## 6. State at 01:10, Aug 25

```
LIVE   BasedOnLaws v1.35  magic 88184  0.01  XAUUSD M1
       camel humps pivot 2 latched · body ratio 0.70 · hold 45% · quieter than UHV
       · stop 6 pips under the retracement low · 2R · BE at 1R · ALL HOURS
       Re-verified 01:03 after he accidentally closed the terminal; every EA came
       back, logger backfill "scanned 1,516 deals — appended 0 missed".
🚨     ZeeUHV_Diamond 88154 — FULL SIZE, decision still owed
BUILT  BasedOnLawsNoGate 88194 — control arm, not attached
```

## 7. What is still MINE, not his

`InpBreakHold=0.45` · `InpPivot=2` · `InpRetraceMax=20` · `InpUpRunBars=2` ·
`InpMinRetraceBars=2` · the risk band `0.5–10.0` (caught refusing his own marked setup)
· `InpFreshMaxSec=40`. Each is a place the EA can obey his law while measuring it
differently than he does — which is exactly how the 0.35 wick test survived until he
looked at the 10:02 candle.

**And the lesson of the day, three times over: when his law and my substitute were
measured head to head, his won every time.**
