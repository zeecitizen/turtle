"""bb3_install.py - build XAUUSD_BB3 (Blueberry real ticks 2023-2025) in Axi test rigs with mt5/BbTickLoad.mq5 (2026-10-28).
Needs Common\\Files\\bb3_{t,bid,ask}.bin (hard links to monitor/saad_view/simdata/m15_tick_raw_*.bin) and XAUUSD_BB already in the rig.

    py bb3_install.py axi6 axi5
"""
import subprocess, sys, time
from pathlib import Path
import axi_rig

FROM, TO = 162876, 316938156                     # tick indices: 2023-01-01 00:00 -> 2026-01-01 00:00 server time
NO_WINDOW = 0x08000000


def install(rig):
    R = Path(axi_rig.RIGS[rig])
    axi_rig.kill_rig(rig)
    src = (axi_rig.SRC / "BbTickLoad.mq5").read_text(encoding="utf-8")
    src = src.replace("input long   InpFrom   = 0;", f"input long   InpFrom   = {FROM};").replace("input long   InpTo     = 0;", f"input long   InpTo     = {TO};")
    scripts = R / "MQL5" / "Scripts"; scripts.mkdir(exist_ok=True)
    (scripts / "BbTickLoad.mq5").write_text(src, encoding="utf-8")
    log = R / "compile.log"
    subprocess.run([str(R / "MetaEditor64.exe"), "/portable", f"/compile:{scripts / 'BbTickLoad.mq5'}", f"/log:{log}"], creationflags=NO_WINDOW)
    if "Result: 0 errors" not in log.read_text(encoding="utf-16", errors="ignore"):
        return f"{rig}: compile failed"
    (R / "script.ini").write_text("[StartUp]\r\nScript=BbTickLoad\r\nSymbol=XAUUSD_BB\r\nPeriod=M1\r\n", encoding="utf-16")
    t0 = time.time()
    proc = subprocess.Popen([str(R / "terminal64.exe"), "/portable", f"/config:{R / 'script.ini'}"])
    while proc.poll() is None and time.time() - t0 < 7200:
        time.sleep(10)
    axi_rig.kill_rig(rig)
    logs = sorted((R / "MQL5" / "Logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
    lines = [l.split("\t")[-1] for l in logs[-1].read_text(encoding="utf-16", errors="ignore").splitlines() if "[bbload]" in l]
    return f"{rig} ({time.time() - t0:.0f} s): " + " | ".join(lines[-2:])


if __name__ == "__main__":
    for r in sys.argv[1:]:
        print(install(r), flush=True)
