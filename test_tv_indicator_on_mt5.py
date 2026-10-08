"""test_tv_indicator_on_mt5.py - test the TradingView indicator's signals in MT5, on real ticks.

    python test_tv_indicator_on_mt5.py                         # $1 TP, no SL, candle + 1 min
    python test_tv_indicator_on_mt5.py --tp 5 --sl 5 --window 2 --delay 500
    python test_tv_indicator_on_mt5.py --tp 1 2 5 --sl 0 5     # every combination

What it does, every run:
  1. reads every BUY/SELL the indicator on your TradingView chart generated (its full history),
     with the UHV candle each one broke - straight from the indicator's data, nothing re-derived;
  2. finds the broker's server-time offset by matching Prime XBT's 1-minute candles to the
     OANDA candles (re-done each run, so daylight saving can never misalign it);
  3. replays the signals in MT5's Strategy Tester (mt5/SignalReplay.mq5): in each signal's
     minute it waits for Prime XBT's own price to cross that UHV candle's high/low, enters with
     the tester's delay, puts the take-profit and stop on the server from the fill, and closes
     at market when the window ends;
  4. runs RANDOM entries (mt5/RandomTouch.mq5) with exactly the same exits over the same days;
  5. prints both side by side and saves the run to pine/lab/mt5_runs/.
The edge of the indicator is the difference between the two lines - not the win rate alone.

Runs on a separate portable copy of the Prime XBT terminal (C:/mt5_rig_pxbt), never the live one.
"""
import argparse
import datetime as dt
import itertools
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "pine"))
import tv_lab as L  # noqa: E402
from verify_panel import load_history  # noqa: E402

RIG = Path(r"C:/mt5_rig_pxbt")
COMMON = Path(os.environ["APPDATA"]) / "MetaQuotes" / "Terminal" / "Common" / "Files"
SYMBOL = "XAUUSDp"
OUT = REPO / "pine" / "lab" / "mt5_runs"

EXPORT = r"""
(() => {
  const m = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model();
  const bars = m.mainSeries().bars();
  const st = m.dataSources().find(s => s.metaInfo && s.metaInfo().description && s.metaInfo().description.indexOf('Turtle') === 0);
  const mi = st.metaInfo(); const p = {};
  (mi.plots || []).forEach((q, i) => { const t = mi.styles && mi.styles[q.id] && mi.styles[q.id].title; p[t] = i + 1; });
  const d = st.data(); const b = [], sig = [];
  for (let i = bars.firstIndex(); i <= bars.lastIndex(); i++) {
    const v = bars.valueAt(i); if (!v) continue;
    b.push([v[0], v[4]]);
    const s = d.valueAt(i);
    if (s && s[p['test entry']] != null && !isNaN(s[p['test entry']]))
      sig.push([v[0], s[p['test direction']], s[p['test uhv time']], s[p['test entry']]]);
  }
  return JSON.stringify({bars: b, sig, symbol: m.mainSeries().symbol(), res: m.mainSeries().interval()});
})()
"""


def compile_ea(name):
    src = REPO / "mt5" / f"{name}.mq5"
    dst = RIG / "MQL5" / "Experts" / f"{name}.mq5"
    dst.write_bytes(src.read_bytes())
    subprocess.run([str(RIG / "MetaEditor64.exe"), "/portable", f"/compile:{dst}", f"/log:{RIG / 'compile.log'}"])
    log = (RIG / "compile.log").read_text(encoding="utf-16", errors="replace")
    if "0 errors" not in log:
        raise SystemExit(f"{name} did not compile:\n{log[-1500:]}")


def run_tester(ea, inputs, frm, to, delay):
    # text settings take the plain value; numbers/bools the optimiser form value||start||step||stop||N
    ti = "".join((f"{k}={v}\r\n" if isinstance(v, str) and v not in ("true", "false") else f"{k}={v}||{v}||0||{v}||N\r\n")
                 for k, v in inputs.items())
    ini = ("[Tester]\r\n" f"Expert={ea}\r\nSymbol={SYMBOL}\r\nPeriod=M1\r\nModel=4\r\n"
           f"FromDate={frm}\r\nToDate={to}\r\nDeposit=100000\r\nCurrency=USD\r\nLeverage=1:500\r\n"
           f"ExecutionMode={delay}\r\nOptimization=0\r\nReport={ea}_report\r\nReplaceReport=1\r\n"
           "ShutdownTerminal=1\r\nVisual=0\r\n[TesterInputs]\r\n" + ti)
    (RIG / "run.ini").write_text(ini, encoding="utf-16")
    logs = RIG / "Tester" / "logs"
    before = {p: p.stat().st_size for p in logs.glob("*.log")} if logs.exists() else {}
    p = subprocess.Popen([str(RIG / "terminal64.exe"), "/portable", f"/config:{RIG / 'run.ini'}"])
    p.wait(timeout=3600)
    new = ""
    for f in sorted(logs.glob("*.log"), key=lambda q: q.stat().st_mtime):
        raw = f.read_bytes()
        new += raw[before.get(f, 0):].decode("utf-16", errors="replace") if before.get(f, 0) % 2 == 0 else raw.decode("utf-16", errors="replace")
    return new


def calibrate(tv_bars, frm, to):
    """Server offset (hours) at which Prime XBT's closes best match the OANDA closes."""
    f = COMMON / "pxbt_m1.csv"
    if f.exists():
        f.unlink()
    run_tester("SignalReplay", {"InpExportBars": "true", "InpFile": "tv_signals.csv"}, frm, to, 0)
    px = {}
    for line in f.read_text(encoding="ascii", errors="ignore").splitlines():
        a = line.split(",")
        if len(a) >= 5:
            px[int(a[0])] = float(a[4])
    tv = {t: c for t, c in tv_bars}
    best = None
    for h in range(-12, 13):
        diffs = [abs(px[t + h * 3600] - c) for t, c in tv.items() if t + h * 3600 in px]
        if len(diffs) > 500:
            m = sum(diffs) / len(diffs)
            if best is None or m < best[1]:
                best = (h, m, len(diffs))
    if not best:
        raise SystemExit("could not match Prime XBT candles to the TradingView candles")
    print(f"clock: broker server = UTC{best[0]:+d} h  (mean close difference ${best[1]:.3f} over {best[2]} candles)")
    return best[0] * 3600


def parse(log, tag):
    lines = [l.split("\t")[-1] for l in log.splitlines() if tag in l]
    return lines[-1] if lines else "(no result line - see the tester log)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tp", type=float, nargs="+", default=[1.0], help="take-profit, $ on 0.1 lot")
    ap.add_argument("--sl", type=float, nargs="+", default=[0.0], help="stop-loss, $ on 0.1 lot (0 = none)")
    ap.add_argument("--window", type=int, nargs="+", default=[1], help="extra minutes after the signal candle")
    ap.add_argument("--delay", type=int, default=-1, help="tester delay: -1 random, 0 none, N ms")
    ap.add_argument("--lots", type=float, default=0.1)
    ap.add_argument("--rig", default=r"C:/mt5_rig_pxbt", help="portable test terminal (C:/mt5_rig_bb = Blueberry)")
    ap.add_argument("--symbol", default="XAUUSDp", help="broker gold symbol (Blueberry: XAUUSD.pi)")
    ap.add_argument("--no-random", action="store_true", help="skip the random-entry comparison")
    ap.add_argument("--signals", help="replay a saved signal file (t,dir,uhv_t,entry) instead of reading TradingView")
    ap.add_argument("--offset-hours", type=int, help="broker server time minus UTC; skips the calibration run")
    a = ap.parse_args()
    global RIG, SYMBOL
    RIG, SYMBOL = Path(a.rig), a.symbol

    if a.signals:
        rows = [l.split(",") for l in Path(a.signals).read_text(encoding="ascii").split("\n") if l.strip()]
        sig = [[int(r[0]), int(r[1]), int(r[2]) * 1000, float(r[3])] for r in rows]
        data = {"bars": [], "symbol": f"saved file {a.signals}"}
        if a.offset_hours is None:
            raise SystemExit("--signals needs --offset-hours (no TradingView candles to calibrate against)")
    else:
        load_history(11000)
        data = json.loads(L.js(EXPORT))
        if data["res"] != "1":
            raise SystemExit(f"the TradingView chart must be on 1 minute (it is on {data['res']})")
        sig = [s for s in data["sig"] if s[2] is not None]
    if not sig:
        raise SystemExit("no signals found - is the indicator's 'test uhv time' export there? run `python pine/tv_lab.py push`")
    COMMON.mkdir(parents=True, exist_ok=True)
    csv = "".join(f"{int(t)},{int(d)},{int(u // 1000)},{e}\n" for t, d, u, e in sig)
    keep = OUT / f"signals_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"   # every export is kept for reuse
    OUT.mkdir(parents=True, exist_ok=True)
    keep.write_text(csv, encoding="ascii")
    (COMMON / "tv_signals.csv").write_text(csv, encoding="ascii")
    (RIG / "MQL5" / "Files").mkdir(parents=True, exist_ok=True)
    (RIG / "MQL5" / "Files" / "tv_signals.csv").write_text(csv, encoding="ascii")   # #property tester_file
    t0 = dt.datetime.fromtimestamp(sig[0][0], dt.timezone.utc).date()
    t1 = dt.datetime.fromtimestamp(sig[-1][0], dt.timezone.utc).date() + dt.timedelta(days=1)
    frm, to = t0.strftime("%Y.%m.%d"), t1.strftime("%Y.%m.%d")
    print(f"{len(sig)} signals from TradingView ({data['symbol']}), {frm} -> {to}")

    compile_ea("SignalReplay")
    compile_ea("RandomTouch")
    off = a.offset_hours * 3600 if a.offset_hours is not None else calibrate(data["bars"], frm, to)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    for tp, sl, w in itertools.product(a.tp, a.sl, a.window):
        common = {"InpLots": a.lots, "InpTargetUSD": tp, "InpSLUSD": sl, "InpExtraBars": w}
        rlog = run_tester("SignalReplay", {**common, "InpOffsetSec": off, "InpExportBars": "false", "InpFile": "tv_signals.csv"}, frm, to, a.delay)
        blog = "" if a.no_random else run_tester("RandomTouch", {**common, "InpEveryN": 1, "InpServerTP": "true", "InpDir": 0, "InpSeed": 42}, frm, to, a.delay)
        ours, rnd = parse(rlog, "[REPLAY] signals"), parse(blog, "[RANDOMTOUCH] trades")
        print(f"\nTP ${tp:g}  SL ${sl:g}  window candle+{w}  delay {a.delay}")
        print("  INDICATOR:", ours)
        print("  RANDOM   :", rnd)
        results.append({"tp": tp, "sl": sl, "window": w, "delay": a.delay, "indicator": ours, "random": rnd})
    (OUT / f"run_{stamp}.json").write_text(json.dumps({"signals": len(sig), "from": frm, "to": to,
                                                       "offset_s": off, "results": results}, indent=1))
    print(f"\nsaved: pine/lab/mt5_runs/run_{stamp}.json")


if __name__ == "__main__":
    main()
