"""Saad v4 court: the EA port of the TradingView indicator (Zee's chart settings = defaults).
Axi rig, XAUUSD.pro M5, real ticks, $25k, 0.10 lots. Each arm = a set of input overrides.
    py saad_v4.py ARM [ARM ...]     arms defined in ARMS or as k=v,k=v strings
    --from/--to  period (default Jan 1 -> Oct 8)   --rig axi|pxbt   --nocompile"""
import json, sys, argparse
from pathlib import Path
import axi_rig
OUT = Path(__file__).with_name("saad_v4.jsonl")
ARMS = {"base": {}}

def line(r):
    ds = r.get("day_stats", {}); m = r.get("months", {})
    td = r.get("trade_days") or 1
    if "net" not in r: return f"{r['arm']:34s} ERROR {r.get('error')}"
    return (f"{r['arm']:34s} net {r.get('net'):>9} tr {r.get('trades'):>4} ({r.get('trades',0)/td:.1f}/day) WR {r.get('wr'):>7} PF {r.get('pf'):>5} "
            f"DD {r.get('dd')} | days {ds.get('green')}/{ds.get('days')} green, worst {ds.get('worst')}, median {ds.get('median')} "
            f"| losing months {sum(v < 0 for v in m.values())} {r.get('error','')}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("arms", nargs="*")
    ap.add_argument("--from", dest="frm", default="2026.01.01"); ap.add_argument("--to", default="2026.10.08")
    ap.add_argument("--rig", default="axi"); ap.add_argument("--symbol", default=None); ap.add_argument("--nocompile", action="store_true"); ap.add_argument("--exec", type=int, default=-1)
    a = ap.parse_args()
    axi_rig.use(a.rig)
    sym = a.symbol or {"axi": "XAUUSD.pro", "pxbt": "XAUUSDp"}.get(a.rig, "XAUUSD")
    if not a.nocompile: axi_rig.compile_ea("Saad_strategy")
    for n in a.arms or ["base"]:
        sets = ARMS.get(n) if n in ARMS else dict(kv.split("=", 1) for kv in n.split(",") if kv)
        for attempt in range(3):
          try:
            r = axi_rig.run("Saad_strategy", sym, "M5", sets, frm=a.frm, to=a.to, tag="saad4_" + a.rig, timeout=240, exec_mode=a.exec)
            if "net" in r: break
          except Exception as e:
            r = {"error": str(e)[:80]}
            import subprocess   # kill only the RIG's terminal, never a live one
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{axi_rig.RIG}*' }} | Stop-Process -Force"])
        r.update(arm=n, rig=a.rig, frm=a.frm, to=a.to, exec=a.exec)
        with OUT.open("a") as f: f.write(json.dumps(r) + "\n")
        print(line(r), flush=True)
