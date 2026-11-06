"""vsisa_sep_build.py — build the September custom symbol inside the test rig.

Runs VsisaTickImport as a STARTUP SCRIPT in the portable rig, which loads the real
recorded ticks (built by vsisa_sep_ticks.py) into a custom symbol the Strategy Tester
can then replay. Never touches the live terminal: the rig has its own portable
Common\\Files, so the tick CSV is copied across rather than shared.

    py monitor/strategy_lab/vsisa_sep_build.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import RIG, TEST_EXE, live_is_safe  # noqa: E402
from trend_lab import block_autoupdate, kill_stubs  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
LIVE = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal"
            r"\DBE9B8B347D025DD139E103EE3B63FD8")
LIVE_COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SCRIPT = "VsisaTickImport"
TICKS = "vsisa_ticks.csv"
SYMBOL = "XAUUSD_TK"


def main():
    live_is_safe()

    src_csv = LIVE_COMMON / TICKS
    if not src_csv.exists():
        sys.exit("[build] %s missing — run vsisa_sep_ticks.py first" % src_csv)

    # The rig runs /portable, so its Common\Files is its OWN folder, not the shared one.
    dst_dir = RIG / "Common" / "Files"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_csv = dst_dir / TICKS
    if (not dst_csv.exists()) or dst_csv.stat().st_size != src_csv.stat().st_size:
        print("[build] copying %.1f MB of ticks into the rig…"
              % (src_csv.stat().st_size / 1e6), flush=True)
        shutil.copy(src_csv, dst_csv)

    # A script must live under MQL5\Scripts to be launched by [StartUp].
    sdir = RIG / "MQL5" / "Scripts"
    sdir.mkdir(parents=True, exist_ok=True)
    found = False
    for ext in (".ex5", ".mq5"):
        s = LIVE / "MQL5" / "Experts" / (SCRIPT + ext)
        if s.exists():
            shutil.copy(s, sdir / (SCRIPT + ext))
            found = found or ext == ".ex5"
    if not found:
        sys.exit("[build] %s.ex5 not compiled — run: py monitor/deploy_ea.py %s"
                 % (SCRIPT, SCRIPT))

    ini = ROOT / "mt5" / "_vsisa_sep_build.ini"
    ini.write_text("\n".join([
        "[StartUp]",
        "Script=" + SCRIPT,
        "Symbol=XAUUSD",
        "Period=M5",
        "ShutdownTerminal=1",
    ]) + "\n", encoding="utf-16")

    block_autoupdate()
    kill_stubs()
    print("[build] importing ticks into %s …" % SYMBOL, flush=True)
    t0 = time.time()
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=3600, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[build] TIMED OUT")

    made = (RIG / "bases" / "Custom" / "history" / SYMBOL).exists()
    print("[build] %s in rig: %s   (%.0fs)"
          % (SYMBOL, "YES" if made else "NO", time.time() - t0))

    # The script's own Print lines are the only place a failure explains itself.
    for d in (RIG / "MQL5" / "Logs", RIG / "logs"):
        fs = sorted(d.glob("*.log"), key=lambda f: f.stat().st_mtime) if d.exists() else []
        if not fs:
            continue
        txt = fs[-1].read_bytes()[-400000:].decode("utf-16-le", errors="replace")
        hits = [l.split("\t")[-1].strip() for l in txt.splitlines()
                if "tickimport" in l]
        for l in hits[-14:]:
            print("        " + l[:160])
        if hits:
            break


if __name__ == "__main__":
    main()
