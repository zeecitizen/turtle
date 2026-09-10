"""vsisa_export_bars.py — pull M5 bars out of the test rig so the setups can be drawn.

The VSISA page has to show the candles the EA actually judged, which means the BROKER's
M5 bars and their tick_volume — the same number BarVolume() reads. Those live inside the
rig's history, not in any CSV we already keep, so a script is run there to dump them.

Two symbols, because the seven-month court and the live trade sit on different data:
  XAUUSD     — broker tick history, Feb..Aug, what the validation court ran on
  XAUUSD_TK  — the custom symbol built from OUR recorded September ticks

Never touches the live terminal.

    py monitor/strategy_lab/vsisa_export_bars.py
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
SCRIPT = "ExportBarsRange"
OUT = ROOT / "monitor" / "_vsisa_bars"

JOBS = [
    # symbol,      from,           to,             file
    ("XAUUSD",    "2026.02.01", "2026.09.01", "vsisa_bars_xauusd.csv"),
    ("XAUUSD_TK", "2026.09.01", "2026.09.11", "vsisa_bars_sep.csv"),
]


def stage_script():
    sdir = RIG / "MQL5" / "Scripts"
    sdir.mkdir(parents=True, exist_ok=True)
    ok = False
    for ext in (".ex5", ".mq5"):
        s = LIVE / "MQL5" / "Experts" / (SCRIPT + ext)
        if s.exists():
            shutil.copy(s, sdir / (SCRIPT + ext))
            ok = ok or ext == ".ex5"
    if not ok:
        sys.exit("[bars] %s.ex5 missing — run: py monitor/deploy_ea.py %s"
                 % (SCRIPT, SCRIPT))


def run_job(symbol, frm, to, fname):
    ini = ROOT / "mt5" / "_vsisa_bars.ini"
    ini.write_text("\n".join([
        "[StartUp]",
        "Script=" + SCRIPT,
        "Symbol=XAUUSD",
        "Period=M5",
        "ShutdownTerminal=1",
        "",
        "[StartUpInputs]" if False else "",
    ]).rstrip() + "\n", encoding="utf-16")

    # A startup SCRIPT takes its inputs from a <name>.set file beside it, not from the
    # ini — MT5 offers no [ScriptInputs] section. Writing the .set is the only way to
    # parameterise it headlessly.
    sset = RIG / "MQL5" / "Presets" / (SCRIPT + ".set")
    sset.parent.mkdir(parents=True, exist_ok=True)
    sset.write_text("\n".join([
        "InpSymbol=" + symbol,
        "InpTfMin=5",
        "InpFrom=" + frm,
        "InpTo=" + to,
        "InpFile=" + fname,
    ]) + "\n", encoding="utf-16")

    block_autoupdate()
    kill_stubs()
    print("[bars] %s %s -> %s …" % (symbol, frm, to), flush=True)
    t0 = time.time()
    try:
        subprocess.run([str(TEST_EXE), "/portable", "/config:" + str(ini)],
                       timeout=1800, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[bars] TIMED OUT")

    src = RIG / "Common" / "Files" / fname
    OUT.mkdir(parents=True, exist_ok=True)
    if src.exists() and src.stat().st_size > 200:
        dst = OUT / fname
        shutil.copy(src, dst)
        n = sum(1 for _ in open(dst)) - 1
        print("[bars]   %d bars -> %s  (%.0fs)" % (n, dst, time.time() - t0))
        return True
    print("[bars]   NO OUTPUT for %s  (%.0fs)" % (symbol, time.time() - t0))
    for d in (RIG / "MQL5" / "Logs", RIG / "logs"):
        fs = sorted(d.glob("*.log"), key=lambda f: f.stat().st_mtime) if d.exists() else []
        if not fs:
            continue
        txt = fs[-1].read_bytes()[-200000:].decode("utf-16-le", errors="replace")
        for l in [x for x in txt.splitlines() if "[bars]" in x][-6:]:
            print("        " + l.split("\t")[-1].strip()[:150])
        break
    return False


def main():
    live_is_safe()
    stage_script()
    for symbol, frm, to, fname in JOBS:
        run_job(symbol, frm, to, fname)


if __name__ == "__main__":
    main()
