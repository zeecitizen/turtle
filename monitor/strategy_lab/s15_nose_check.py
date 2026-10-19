"""s15_chart_vs_v126.py - Zee 2026-10-19: "test the current settings from indicator on tradingview on MT5 as tuned upon on v1.26 -> and compare
its results to v1.26". The chart's settings -> Saad_strategy_15min v1.26 inputs; v1.26 pure defaults vs the chart, full year, twice each
(random delay), XAUUSD_BB M15, $100k. The compare page's auto re-run is paused meanwhile. Writes s15_chart_vs_v126.json."""
import json
import random
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402
import axi_rig  # noqa: E402

HERE = Path(__file__).resolve().parent
EA = "Saad_strategy_15min"
API = "http://127.0.0.1:8772/api/year"
st, settings, sets, notes = server.read_settings()
dfl = axi_rig.ea_defaults(EA)
chart = {k: v for k, v in sets.items() if k in dfl}
chart["InpExitMode"] = {"Next EMA beyond the entry (touch, close all)": "1", "Candle closes back across the slow EMA (close all)": "2"}.get(settings["tpMode"], "0")
chart["InpBandOff"] = "1" if str(settings.get("rpOff", "")).startswith("Stand aside") else "0"
chart["InpLogCsv"] = "false"


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip('"').lower() == str(b).strip('"').lower()


diff = {k: (dfl[k], v) for k, v in chart.items() if k != "InpLogCsv" and not same(dfl[k], v)}
print(f"chart {st['symbol']} {st['res']} min | TP1 {settings['tpMode']} | unticked range: {settings.get('rpOff')}")
print("CHART vs v1.26 defaults:", json.dumps(diff, ensure_ascii=False))
print("chart-only / not in the EA:", notes)


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e, flush=True)
    return {}


RUNS = [("nose 0.35 #2", {"InpNoseMax": "0.35", "InpLogCsv": "false"}, "axi"), ("nose 0.35 #3", {"InpNoseMax": "0.35", "InpLogCsv": "false"}, "axi2"),
        ("nose 0.30", {"InpNoseMax": "0.30", "InpLogCsv": "false"}, "axi3"), ("nose 0.40", {"InpNoseMax": "0.40", "InpLogCsv": "false"}, "axi4"),
        ("nose 0.25", {"InpNoseMax": "0.25", "InpLogCsv": "false"}, "axi5"), ("nose 0.45", {"InpNoseMax": "0.45", "InpLogCsv": "false"}, "axi6"),
        ("v1.26 #3", {"InpLogCsv": "false"}, "axi7")]
t0 = time.time()
while page().get("running") and time.time() - t0 < 1800:
    time.sleep(10)
was = page().get("auto", True)
page(False)
res = {}


def one(name, s, rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea(EA, rig=rig)
    for a in range(3):
        r = axi_rig.run(EA, "XAUUSD_BB", "M15", s, frm="2026.01.01", to="2026.10.17", deposit=100000, rig=rig, tag=f"cmp126_{rig}", exec_mode=-1)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    dd = float(str(r.get("dd") or "0").split("(")[0].replace(" ", "") or 0)
    mo = r.get("months") or {}
    res[name] = {"net": net, "pf": float(r.get("pf") or 0), "wr": wr, "n": n, "dd": dd, "months": mo, "day_stats": r.get("day_stats"), "err": r.get("error"),
                 "h1": sum(v for k, v in mo.items() if k <= "2026.06"), "h2": sum(v for k, v in mo.items() if k >= "2026.07")}
    print(f"{name}: net {net:+,.0f} PF {res[name]['pf']:.2f} WR {wr:.1f}% trades {n} DD {dd:,.0f} | Jan-Jun {res[name]['h1']:+,.0f} Jul-Oct {res[name]['h2']:+,.0f} | "
          + " ".join(f"{k[5:]}:{v / 1000:+.1f}k" for k, v in mo.items()), flush=True)


ths = []
for x in RUNS:
    th = threading.Thread(target=one, args=x); th.start(); ths.append(th); time.sleep(5)
[th.join() for th in ths]
json.dump({"chart_settings": settings, "chart_inputs": chart, "diff_vs_v126": diff, "notes": notes, "res": res}, open(HERE / "s15_nose_check.json", "w"), indent=1)
page(bool(was))
print("DONE", flush=True)
