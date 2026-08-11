# 💎 05 August — The Diamonds Day (findings & full system record)

**Branch snapshot: `05_August_successful_diamonds`** — built 2026-08-04 → 05 in one
continuous session, Zee + Claude. This document is the retrieval point: everything the
Ghost system is, why each rule exists, and what the live receipts taught. If context is
ever lost, read THIS first, then `monitor/oanda_live_matcher.py` and
`mt5/CaseSignalExecutor.mq5` — every rule is commented with Zee's own words.

---

## 1. What runs (the pipeline)

```
TradingView (OANDA:XAUUSD M1, REAL volume)
  → oanda_bridge --loop 20        → Common/Files/oanda_m1.csv
  → oanda_live_matcher.py (5s)    → case_watch.json  (the UHV box, for the eyes)
                                  → case_armed.json  (lamp level, for tick-fire)
                                  → case_signal.json (closed-candle backup path)
  → CaseSignalExecutor.mq5 v1.62  → Blueberry DEMO 12654799, magic 88020
  → TurtleTradeLogger             → turtle_fills.csv (the receipts)
Cockpits: gui/camel_gui.py (desktop) + claudezeeshan.com (status.html, Apple-white)
```

## 2. The Ghost-Lamp doctrine (Zee's metaphor = the spec)

The strategy is a ghost stealing lamps from a room guarded by the ghost-buster-baba:
evaporate IN at tick speed, take the small guaranteed pop (~$3/click), evaporate OUT.
Injuries must be tiny and pre-paid by the 3-wishes payoff. Feb-11 receipts (+€835,
65W/4L): profit = burst size × small pop, harvested fast — never distance.

## 3. The compass (trend_eyes.py)

- **Camel humps**: fractal swings (PIVOT_K=3) drawn as a gray polyline; zigzag engine
  available (`--method zigzag`).
- **AUTO slant**: least-squares line through the last 3 swing HIGHS. Up → BUY only,
  down → SELL only, |slope| < 0.03 → RANGE (ghost waits). Line colour = geometry ONLY
  (green/red/blue); verdicts live in words.
- **Guard low/high**: uptrend dies when the deepest of the last 2 swing lows breaks
  ("trend has shifted from BUYS"); mirror for downtrends.
- **Command**: AUTO always. Cockpit buttons (UPTREND/DOWNTREND/RANGE) are a rare
  manual decree lasting **10 minutes**, then AUTO. No AUTO button — it's the resting
  state. Web buttons PIN-guarded (`/api/trend-call`, .dashboard_password).

## 4. The UHV box & the FIVE LAWS OF CONVICTION 💎

Box = two black lines on the UHV candle (colour opposite the trend: red UHV in
up-pullback, green in down-bounce; strong same-colour neighbour ≤2 bars before
overrides). Dashed = law pending, solid = concrete. **Laws NEVER gate entry — they
set the raid allowance** (0💎→1 raid, 1💎→3, 2+💎→6) and grow the burst.

1. **The Sweep** — price breaks the FAR line before the lamp (liquidity grab).
2. **NS/ND** — dead-volume candle (<0.75× each of prev two) closing within 0.8pt of
   a line. Doubles the burst.
3. **EMA-5 close** — momentum candle (body ≥0.5) closing CLEARLY (±0.10) beyond
   exponential EMA-5 (never SMA).
4. **RSI-14 divergence** — two swings: price LL + RSI HL from oversold <30 (mirror >70).
5. **Wick & volume** — no large wick (≤25% range) on the breakout nose AND breakout
   volume < UHV volume.

Diamonds drawn with Zee's own `setup_labels/diamond.png` above the box.

## 5. Entry & exit mechanics (EA v1.62)

- **Ghost at the door**: OnTick fires the ms price crosses the armed lamp; chase 1pt
  (3pt when dying-light run). Bursts 0.10 / 0.30 / 0.60 (Feb-11 click counts).
- **Repeat apparitions**: up to 6 raids per lamp, BUT **harvest-and-return** (v1.61:
  price must re-touch the lamp between raids) and **a losing raid retires the lamp**
  (v1.62: clicks are added to WINNERS only).
- **Stacking**: join only when every open click already armed (+0.3); same direction;
  ≤1.20 lots total (code ceiling).
- **Exits**: arm +0.3 → trail 0.2 give-back, no TP ceiling; un-armed −GhostCap →
  evaporate (lot-scaled: 0.10→1.0pt, 0.30→1.0, 0.60→0.5 ≈ $10–30); structural broker
  SL beyond last swing (clamped 0.4–3.0pt); **breakeven at +1R**.
- **Guards**: 180s staleness (no reattach refires), monotonic epoch ids (the %100000
  wrap once swallowed a signal silently), slope-opposition (no fire against 30-bar
  slope steeper than ±0.10).

## 6. The day's live tuition (receipts, broker time)

- Fast-scalp revival day-1: 22 trades 18W/4L +$20.90 — but one 0.20-lot loss at a
  FLAT 3pt cap = −$61.20 → lot-scaled caps born.
- **22:19–23:15 window, −$101.90 — three loss species, all cured:**
  | species | example | cure |
  |---|---|---|
  | hover-refire stack | 22:20 −$30.00 | v1.61 harvest-and-return |
  | slant-lag counter-momentum | 22:32 −$11.10, 22:47 −$30.00 (and 22:13 −$13.80) | slope-opposition guard |
  | doubling a losing lamp | 23:13 −$32.40 (0.60 after a loss) | v1.62 lamp retirement |
- Exits were NEVER the failure — every loss cut at design ±slippage. Entries were.

## 7. Ops lessons (hard-won)

- CLI compile: `metaeditor64.exe /compile:… /log:…` works; **exit code = files
  compiled, not 0**; hot-reload of an attached chart is UNRELIABLE — every deploy must
  be verified by a **load fingerprint** (`Print` in OnInit) or reattached by hand.
  `monitor/deploy_ea.py <Name>` does copy+compile+log-parse.
- Journal/expert logs = LOCAL clock; turtle_fills = BROKER clock (local −2h).
- Branch-EA heartbeat/fills differ per era — TurtleTradeLogger is the receipts truth.
- NY session (18:00–01:00 PKT) bannered on the chart — the ideal window.

## 8. Day-two evolution (2026-08-05 — the first GREEN day)

**EA v1.63 RATCHET TRAIL**: give-back = max(0.2, 30% of peak) — scalps harvest fast,
runners ride (first mechanical wins >$15: +17.30, +15.40, +17.20, +13.20).
**EA v1.64 SEND-COOLDOWN**: door+signal paths were double-firing inside the broker's
in-flight blindness (1-second twin entries); 4s cooldown after any send.

**Matcher laws added (all humility-style — laws never gate):**
- **COLOUR-AWARE UHV** (supersedes June local-max): UHV = highest volume among
  SAME-COLOUR counter-trend candles in the zone; supply is never compared against
  trend-side demand volume (the 16:29 858-vs-910 miss, replay-proven fixed).
- **STRETCH HUMILITY**: lamp >6pt beyond the last confirmed swing → lots 0.10
  (the 19:57 −$30.90 diamond at a parabola tip).
- **LAW OF EXHAUSTION**: trends die of old age — M1 census: runs live ~2.1 humps,
  P(next) 70%→29% after hump 2; dying humps carry |slope| 0.87 vs 0.35–0.42 alive.
  |slope|>0.60 or hump-streak ≥4 → lots 0.10. The market died at 4259 minutes after
  the law shipped.
- Humbled lamps are immune to the 3-diamond re-inflation.

**Compass upgrades (all from Zee's live eye-audits):**
- PIVOT_K 3→2 (a smaller middle peak was erased by a taller neighbour's shadow)
- EARLY SHIFT: a broken guard flips the verdict to the breakout side immediately
- WICK IS A SWEEP, CLOSE IS A BREAK: guards fall only to a closed candle's close
  (the 18:50 spring swept the guard by wick and wrongly blocked the 18:52 breakout)
- Early-shift paint: slant line dashed when a guard-break overrules its geometry
- Chart axis in Karachi time; NY-session banner beneath the chart

**THE DIAMOND EXPERIMENT** (Zee lifted the risk cap: "this is exactly what we want
to test on this demo"): tiers 0.10/0.30/0.60 by diamonds. First reading —
0.10 plain clicks: −$0.27/trade avg · 0.30 diamond bursts: 3W/0L, +$9.80/trade.
Conviction outperformed no-conviction ~36× per trade (n=3, keep collecting).

**LOSS LEDGER** (LOSS_LEDGER.md + monitor/loss_ledger.py daemon): every losing fill
auto-autopsied — species vs every shipped fix, NEW-SPECIES ⚠ = mandatory first job.

**The receipts trajectory:** night one −$259.84 → day two −$45 morning, then
post-ratchet green — day closed with 66 trades, 68% WR, **+$30.30**, last 10 trades
8W/2L +$45.90 (losses −$0.40 and $0.00 — ghost + breakeven + humility as the floor).
Milestone: the machine harvested BOTH the parabola's death (SELL run 18:43-18:59)
and the next trend's birth (BUY run 19:35-19:53, +$15.40 ratchet rider).

## 9. Open questions for future sessions

- Slope-opposition threshold (±0.10) and NS/ND nearness (0.8pt) chosen on few
  receipts — tune with data, walk-forward, never on one day.
- Third-diamond raid/burst mapping beyond 6 — unexplored.
- Divergence law is swing-based (K=3); grade it on the cockpit like the humps were.
- The Claude-judge (vision) layer and NS/ND standalone detector still live on `main`.
