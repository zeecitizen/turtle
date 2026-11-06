"""s15_chart_mt5.py - Zee 2026-10-19: "take the current settings from tradingview and test them in MT5 on saad_ea_15min (just test, if
implementation needed make a test copy)". The chart's settings -> Saad_strategy_15min_chart_test (v1.25 + range boxes + stand-aside ghost),
full year XAUUSD_BB M15, random delay, $100k; variants + plain v1.23 at the same lots; a no-delay sanity run (test copy, all off = v1.25).
The compare page's auto re-run is paused meanwhile. Writes s15_chart_mt5.json."""
import json
import random
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402
import axi_rig  # noqa: E402

HERE = Path(__file__).resolve().parent
TEST = "Saad_strategy_15min_chart_test"
API = "http://127.0.0.1:8772/api/year"
st, settings, sets, notes = server.read_settings()
dfl = axi_rig.ea_defaults(TEST)
chart = {k: v for k, v in sets.items() if k in dfl}
chart["InpExitMode"] = {"Next EMA beyond the entry (touch, close all)": "1", "Candle closes back across the slow EMA (close all)": "2"}.get(settings["tpMode"], "0")
chart["InpBandOff"] = "1" if str(settings.get("rpOff", "")).startswith("Stand aside") else "0"
chart["InpLogCsv"] = "false"
lots = chart.get("InpLots", "1")
print(f"chart {st['symbol']} {st['res']} min | TP1 {settings['tpMode'][:30]} | boxes B {chart['InpBandsB']} S {chart['InpBandsS']} | off-mode {chart['InpBandOff']} | lots {lots}", flush=True)
RUNS = [("1 YOUR CHART (new exit + boxes + stand aside)", TEST, chart, -1, "axi"),
        ("2 ... boxes skip instead of stand aside", TEST, dict(chart, InpBandOff="0"), -1, "axi2"),
        ("3 ... no boxes", TEST, dict(chart, InpBandsB="1" * 21, InpBandsS="1" * 21), -1, "axi3"),
        ("4 ... normal TP1 (v1.23 exits)", TEST, dict(chart, InpExitMode="0"), -1, "axi4"),
        (f"5 plain v1.23 at {lots} lots", "Saad_strategy_15min", {"InpLots": lots, "InpLogCsv": "false"}, -1, "axi5"),
        ("6 YOUR CHART + max risk $20", TEST, dict(chart, InpMaxRiskUsd="20"), -1, "axi6")]


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e, flush=True)
    return {}


t0 = time.time()
while page().get("running") and time.time() - t0 < 1800:
    time.sleep(10)
was = page().get("auto", True)
page(False)
res = {}


def one(name, ea, s, delay, rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea(ea, rig=rig)
    for a in range(3):
        r = axi_rig.run(ea, "XAUUSD_BB", "M15", s, frm="2026.01.01", to="2026.10.17", deposit=100000, rig=rig, tag=f"chartmt5_{rig}", exec_mode=delay)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    mo = r.get("months") or {}
    res[name] = {"ea": ea, "sets": s, "net": net, "pf": r.get("pf"), "wr": wr, "n": n, "deals": r.get("trades"), "dd": r.get("dd"), "months": mo,
                 "days": r.get("day_stats"), "err": r.get("error")}
    print(f"{name}: net {net:+,.2f} PF {r.get('pf')} WR {wr:.1f}% trades {n} deals {r.get('trades')} DD {r.get('dd')} | "
          + " ".join(f"{k[5:]}:{v:+,.0f}" for k, v in mo.items()), flush=True)


ths = []
for x in RUNS:
    th = threading.Thread(target=one, args=x); th.start(); ths.append(th); time.sleep(5)
[th.join() for th in ths]
json.dump({"chart_settings": settings, "res": res}, open(HERE / "s15_chart_mt5_now.json", "w"), indent=1)
page(bool(was))
print("DONE", flush=True)
