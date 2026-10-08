"""tv_armed_bridge.py - hand the indicator's ARMED setup from TradingView to the MT5 EA, live.

    python pine/tv_armed_bridge.py            # runs until stopped (Ctrl+C)

Every ~0.5 s it reads, from the Turtle indicator on the TradingView chart, the setup armed at the
close of the last finished candle (side, UHV candle, trigger) and writes it atomically to
    %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\tv_armed.csv
as one line:  armed_candle_open_utc, side(+1 BUY / -1 SELL / 0), uhv_candle_open_utc, trigger,
              written_utc, status
The EA trades only when status is OK and written_utc is fresh, so if TradingView, the chart or
this script stops, the EA stops opening trades by itself.

Status is not OK unless: the chart is OANDA:XAUUSD, 1 minute, the indicator is on it, and it is
in "Instant at Breakout" mode (the mode the MT5 tests used).
Nothing here can trade early: the EA enters only when the BROKER'S OWN price crosses the BROKER'S
OWN high/low of that UHV candle (Blueberry's latency-arbitrage rule).
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tv_lab as L  # noqa: E402

OUT = Path(os.environ["APPDATA"]) / "MetaQuotes" / "Terminal" / "Common" / "Files" / "tv_armed.csv"

READ = r"""
(() => {
  const m = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model();
  const ms = m.mainSeries(); const bars = ms.bars();
  const st = m.dataSources().find(s => s.metaInfo && s.metaInfo().description && s.metaInfo().description.indexOf('Turtle') === 0);
  if (!st) return JSON.stringify({err: 'indicator not on the chart'});
  const mi = st.metaInfo(); const p = {};
  (mi.plots || []).forEach((q, i) => { const t = mi.styles && mi.styles[q.id] && mi.styles[q.id].title; p[t] = i + 1; });
  if (!p['live armed side']) return JSON.stringify({err: 'indicator has no live armed export - push the latest turtle.pine'});
  const last = bars.lastIndex(); const i = last - 1;          // last FINISHED candle
  const b = bars.valueAt(i); const v = st.data().valueAt(i);
  return JSON.stringify({sym: ms.symbol(), res: ms.interval(), t: b ? b[0] : null,
                         side: v ? v[p['live armed side']] : null, uhv: v ? v[p['live armed uhv time']] : null,
                         trig: v ? v[p['live armed trigger']] : null, now: Date.now() / 1000});
})()
"""


def mode_ok():
    """The chart's copy must be in Instant at Breakout mode (checked once a minute)."""
    vals = L.by_name(L.inputs_of(L.the_study()), L.names(L.SRC.read_text(encoding="utf-8")))
    return vals.get("uOE") == "Instant at Breakout"


def write(line):
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(line + "\n", encoding="ascii")
    os.replace(tmp, OUT)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    last_mode, mode = 0.0, False
    last_line = ""
    print(f"writing {OUT}  (Ctrl+C to stop)")
    while True:
        status, t, side, uhv, trig = "OK", 0, 0, 0, 0.0
        try:
            if time.time() - last_mode > 60:
                mode, last_mode = mode_ok(), time.time()
            import json
            d = json.loads(L.js(READ))
            if d.get("err"):
                status = d["err"]
            elif d["sym"] != "OANDA:XAUUSD":
                status = f"chart is {d['sym']}, not OANDA:XAUUSD"
            elif d["res"] != "1":
                status = f"chart is on {d['res']}, not 1 minute"
            elif not mode:
                status = "indicator is not in Instant at Breakout mode"
            else:
                # a plot with no value (nothing armed) is simply missing from the JSON
                t = int(d.get("t") or 0)
                side = int(d.get("side") or 0)
                uhv = int((d.get("uhv") or 0) // 1000)
                trig = float(d.get("trig") or 0)
        except Exception as e:  # TradingView closed, bridge down, ...
            status = f"error: {str(e)[:80]}"
        status = status.replace(",", ";")
        line = f"{t},{side},{uhv},{trig},{int(time.time())},{status}"
        write(line)
        core = line.split(",", 4)[:4] + [status]
        if core != last_line:
            print(time.strftime("%H:%M:%S"), line, flush=True)
            last_line = core
        time.sleep(0.5)


if __name__ == "__main__":
    main()
