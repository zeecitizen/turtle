"""verify_panel.py - check the indicator's BREAKOUT TEST panel against raw candles, independently.

    python pine/verify_panel.py

What it does
  1. loads the chart's full 1-minute history (asks TradingView for more until it matches the
     number of candles the panel says it computed on);
  2. reads every signal the indicator recorded (its "test entry" / "test direction" data series:
     entry price and BUY/SELL on the entry candle);
  3. recomputes each signal's best move our way from the raw candles, exactly as defined on the
     panel: Instant = the entry candle's high (BUY) / low (SELL) and the next scN candles;
     Candle Close = the next scN candles only; win if best move - spread >= scMin/10;
  4. checks each entry is possible (Instant BUY: open <= entry <= high; SELL mirrored;
     Candle Close: entry == that candle's close);
  5. compares every number on the panel's test rows (won/total, %, BUY, SELL, today, halves,
     average best move) and prints PASS or each mismatch.
It never uses the indicator's own verdicts to compute anything - only to compare.
"""
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tv_lab as L  # noqa: E402

EXPORT = r"""
(() => {
  const m = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model();
  const bars = m.mainSeries().bars();
  const st = m.dataSources().find(s => s.metaInfo && s.metaInfo().description && s.metaInfo().description.indexOf('Turtle') === 0);
  const mi = st.metaInfo();
  const pIdx = {};
  (mi.plots || []).forEach((p, i) => { const t = mi.styles && mi.styles[p.id] && mi.styles[p.id].title; pIdx[t] = i + 1; });
  const d = st.data();
  const b = [], sig = [];
  for (let i = bars.firstIndex(); i <= bars.lastIndex(); i++) {
    const v = bars.valueAt(i); if (!v) continue;
    b.push([v[0], v[1], v[2], v[3], v[4]]);
    const s = d.valueAt(i);
    if (s && s[pIdx['test entry']] != null && !isNaN(s[pIdx['test entry']])) sig.push([v[0], s[pIdx['test entry']], s[pIdx['test direction']]]);
  }
  return JSON.stringify({bars: b, sig});
})()
"""


def load_history(want):
    for _ in range(30):
        n = L.js("window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().bars().size()")
        if n >= want:
            return n
        L.js("(() => { window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().requestMoreData(20000); return 1; })()")
        time.sleep(3)
    return n


def pct(w, n):
    return f"{round(w * 100.0 / n)}%" if n else "—"


def main():
    rows = L.score(wait=1)
    txt = "\n".join(map(str, rows))
    want = int(re.search(r"\((\d+) candles\)", txt).group(1))
    got = load_history(want)
    vals = L.by_name(L.inputs_of(L.the_study()), L.names(L.SRC.read_text(encoding="utf-8")))
    spread, sc_min, sc_n, inst = float(vals["uSpread"]), float(vals["scMin"]), int(vals["scN"]), vals["uOE"] == "Instant at Breakout"
    if "--mutate" in sys.argv:          # self-test: a wrong spread must be caught
        spread += 0.05
    data = json.loads(L.js(EXPORT))
    bars, sigs = data["bars"], data["sig"]
    idx = {b[0]: i for i, b in enumerate(bars)}
    last_closed = len(bars) - 2          # the newest candle is still forming
    problems = []
    res = []
    for t, e, d in sigs:
        i = idx[t]
        o, h, l, c = bars[i][1:5]
        buy = d > 0
        if inst:
            ok = (o - 1e-9 <= e <= h + 1e-9) if buy else (l - 1e-9 <= e <= o + 1e-9)
        else:
            ok = abs(e - c) < 1e-6
        if not ok:
            problems.append(f"impossible entry {e} on {dt.datetime.utcfromtimestamp(t)} (o{o} h{h} l{l} c{c})")
        end = i + sc_n
        if end > last_closed:
            continue                      # window still open: the panel must not count it yet
        span = range(i if inst else i + 1, end + 1)
        best = max((bars[k][2] - e) if buy else (e - bars[k][3]) for k in span)
        res.append((t, buy, best, best - spread >= sc_min / 10.0 - 1e-9))
    n = len(res)
    w = sum(r[3] for r in res)
    bn = sum(1 for r in res if r[1])
    bw = sum(1 for r in res if r[1] and r[3])
    sn, sw = n - bn, w - bw
    k = dt.datetime.now(dt.timezone(dt.timedelta(hours=5)))
    day0 = int(k.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    tn = sum(1 for r in res if r[0] >= day0)
    tw = sum(1 for r in res if r[0] >= day0 and r[3])
    h = n // 2
    ow = sum(r[3] for r in res[:h])
    avg = sum(r[2] - spread for r in res) / n if n else 0
    mine = {
        "won/total": f"{w} / {n} labels won  =  {pct(w, n)}",
        "BUY": f"BUY {bw}/{bn} ({pct(bw, bn)})",
        "SELL": f"SELL {sw}/{sn} ({pct(sw, sn)})",
        "today": f"today {tw}/{tn} ({pct(tw, tn)})",
        "older half": f"older half {pct(ow, h)}",
        "newer half": f"newer half {pct(w - ow, n - h)}",
    }
    print(f"history: panel {want} candles, loaded {got}; signals recorded {len(sigs)}, judged {n}")
    print(f"settings: entry {'instant' if inst else 'candle close'}, window {sc_n}, min profit ${sc_min} on 0.1 lot, spread {spread}")
    fails = list(problems)
    for name, s in mine.items():
        if s is None:
            continue
        if s not in txt:
            fails.append(f"{name}: mine '{s}' not on the panel")
    # random baseline: every candle as a pretend BUY and SELL, same rule (panel: "a random entry scores")
    rbn = rbw = 0
    for j in range(sc_n + 2, last_closed + 1):
        i = j - sc_n
        if inst:
            e = bars[i][1]; hi = max(b[2] for b in bars[i:j + 1]); lo = min(b[3] for b in bars[i:j + 1])
        else:
            if sc_n == 0:
                continue
            e = bars[i][4]; hi = max(b[2] for b in bars[i + 1:j + 1]); lo = min(b[3] for b in bars[i + 1:j + 1])
        rbn += 2
        rbw += (hi - e - spread >= sc_min / 10.0 - 1e-9) + (e - lo - spread >= sc_min / 10.0 - 1e-9)
    if f"a random entry scores {pct(rbw, rbn)} on this same test" not in txt:
        fails.append(f"random baseline: mine {pct(rbw, rbn)} ({rbw}/{rbn}) not on the panel")
    m = re.search(r"avg best move after spread: \$(-?[\d.]+)", txt)
    if not m or abs(float(m.group(1)) - avg) > 0.006:
        fails.append(f"avg best move: mine {avg:.4f}, panel {m.group(1) if m else '?'}")
    for f in fails:
        print("MISMATCH", f)
    print("PASS - every breakout-test number on the panel matches the raw candles" if not fails else f"{len(fails)} problem(s)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
