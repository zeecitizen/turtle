"""bb_symbol_install.py - install the custom symbol XAUUSD_BB (Blueberry's real XAUUSD ticks) in Axi test rigs.

Zee 2026-10-17: "maybe we can run these on blueberry instead?" - the 10-month view ran on Axi XAUUSD_TK.

    py bb_symbol_install.py axi2 axi3 axi4 axi5 axi6 axi7

Needs, from Zee's Blueberry terminal (mt5/BbTickClone.mq5 run there once):
  * <Blueberry data>/bases/Custom/ticks|history/XAUUSD_BB   - the ticks and bars
  * Common/Files/bb_symbol_spec.csv                        - Blueberry's specs and sessions
Per rig: mt5/BbSymbolDef.mq5 defines XAUUSD_BB (a copy of the rig's XAUUSD_TK with Blueberry's specs + sessions), then the
tick / bar folders are copied in while the rig's terminal is closed.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import axi_rig

LIVE = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\27280402C90F04230EE7E17540AE21E1\bases\Custom")
NO_WINDOW = 0x08000000


def install(rig):
    R = Path(axi_rig.RIGS[rig])
    axi_rig.kill_rig(rig)
    scripts = R / "MQL5" / "Scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(axi_rig.SRC / "BbSymbolDef.mq5", scripts / "BbSymbolDef.mq5")
    log = R / "compile.log"
    subprocess.run([str(R / "MetaEditor64.exe"), "/portable", f"/compile:{scripts / 'BbSymbolDef.mq5'}", f"/log:{log}"], creationflags=NO_WINDOW)
    if "Result: 0 errors" not in log.read_text(encoding="utf-16", errors="ignore"):
        return f"{rig}: compile failed"
    (R / "script.ini").write_text("[StartUp]\r\nScript=BbSymbolDef\r\nSymbol=XAUUSD_TK\r\nPeriod=M1\r\n", encoding="utf-16")
    proc = subprocess.Popen([str(R / "terminal64.exe"), "/portable", f"/config:{R / 'script.ini'}"])
    for _ in range(120):
        if proc.poll() is not None:
            break
        time.sleep(1)
    axi_rig.kill_rig(rig)
    logs = sorted((R / "MQL5" / "Logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
    lines = [l.split("\t")[-1] for l in logs[-1].read_text(encoding="utf-16", errors="ignore").splitlines() if "[bbdef]" in l]
    for sub in ("ticks", "history"):
        dst = R / "Bases" / "Custom" / sub / "XAUUSD_BB"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(LIVE / sub / "XAUUSD_BB", dst)
    return f"{rig}: " + " | ".join(lines[-2:])


if __name__ == "__main__":
    for r in sys.argv[1:]:
        print(install(r), flush=True)
