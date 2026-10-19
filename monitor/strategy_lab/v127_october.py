"""v127_october.py - Zee 2026-10-19: "test in MT5 on October only the latest version v1.27". Pure defaults, Oct 1 - Oct 16 (the end of the
XAUUSD_BB ticks), two random-delay runs, $100k. Writes v127_october.json."""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import axi_rig  # noqa: E402
import server  # noqa: E402

API = "http://127.0.0.1:8772/api/year"
EA = "Saad_strategy_15min"


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e)
    return {}


was = page().get("auto", True)
page(False)
res = {}


def one(name, rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea(EA, rig=rig)
    r = axi_rig.run(EA, "XAUUSD_BB", "M15", {"InpLogCsv": "false"}, frm="2026.10.01", to="2026.10.17", deposit=100000, rig=rig, tag=f"oct127_{rig}", exec_mode=-1)
    pos = server.parse_positions(str(Path(axi_rig._R(rig)) / "reports" / f"oct127_{rig}.htm"), 0)
    res[name] = {"net": r.get("net"), "pf": r.get("pf"), "trades": len(pos), "dd": r.get("dd"), "days": r.get("daily"), "pos": pos, "err": r.get("error")}


ths = [threading.Thread(target=one, args=(n, g)) for n, g in (("run 1", "axi"), ("run 2", "axi2"))]
for th in ths:
    th.start(); time.sleep(5)
for th in ths:
    th.join()
page(bool(was))
json.dump(res, open(Path(__file__).with_name("v127_october.json"), "w"), indent=1)
for n, r in res.items():
    w = sum(1 for p in r["pos"] if p["pnl"] > 0)
    print(f"{n}: net {r['net']:+,.2f} PF {r['pf']} trades {r['trades']} wins {w} ({100 * w / max(1, r['trades']):.0f}%) DD {r['dd']} err {r['err']}")
print("\ndays (run 1):", {k: v for k, v in (res["run 1"]["days"] or {}).items()})
print("\ntrades (run 1, server time = PKT - 2):")
for p in res["run 1"]["pos"]:
    print(f"  {p['in']} -> {p['out'][11:]}  {p['side']:4} {p['en']:.2f} -> {p['ex']:.2f}  {p['pnl']:+,.0f}")
