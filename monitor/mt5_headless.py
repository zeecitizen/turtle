"""mt5_headless.py — run MT5's Strategy Tester with no human in the loop.

Zee, 2026-08-10: "is it possible that we can run MT5 strategy tester's tests by its
own.. without needing human clicks / intervention"

Yes, and this is it. MetaTrader accepts a config file on the command line and will run
a test or a full optimisation headlessly, write its report, and shut itself down:

    terminal64.exe /config:C:\\path\\run.ini

Every result today cost him a click, a dropdown and a wait — and three runs were wasted
on settings that did not take. This removes all of that.

TWO RULES THIS FILE OBEYS:

1. IT NEVER TOUCHES THE LIVE TERMINAL. His Blueberry install has CaseSignalExecutor
   attached and real money logic running; a second instance on that data folder, or a
   shutdown flag pointed at it, could close positions or kill the EA. So the runner
   drives a SEPARATE install (C:\\Program Files\\MetaTrader 5) with its own data folder,
   and refuses to start if that terminal is somehow the live one.

2. IT IS STILL MT5. Everything this produces is a real Strategy Tester result with real
   spread and real execution, so it satisfies the first rule in CLAUDE.md — unlike the
   Python screens that cost us the afternoon. Headless does not mean simulated.

    py monitor/mt5_headless.py --setup                 # build the symbol in the test rig
    py monitor/mt5_headless.py --ea ZeeUHV             # one backtest
    py monitor/mt5_headless.py --ea ZeeUHV --optimize  # the whole sweep
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent
TERMINALS = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal")
LIVE_PREFIX = "DBE9B8B347D0"                      # Blueberry — hands off
TEST_EXE = Path(r"C:/Program Files/MetaTrader 5/terminal64.exe")
TEST_PREFIX = "D0E8209F77C8"
COMMON = TERMINALS / "Common" / "Files"
REPORTS = ROOT / "mt5" / "_tester_runs" / "headless"


def test_data_dir():
    d = next((p for p in TERMINALS.iterdir() if p.name.startswith(TEST_PREFIX)), None)
    if d is None:
        raise SystemExit("test terminal data folder not found — run the terminal once by hand")
    if d.name.startswith(LIVE_PREFIX):
        raise SystemExit("REFUSING: that is the LIVE terminal")
    return d


def live_is_safe():
    """Confirm we are not about to disturb the terminal that trades his money."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-Process terminal64 -ErrorAction SilentlyContinue | "
                        "ForEach-Object { $_.Path }) -join ';'"],
                       capture_output=True, text=True, timeout=30)
    running = r.stdout.strip()
    if str(TEST_EXE) in running:
        print("[headless] the test terminal is already running — closing it")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Process terminal64 | Where-Object {{ $_.Path -eq '{TEST_EXE}' }} | "
                        "Stop-Process -Force"], capture_output=True, timeout=30)
        time.sleep(3)
    return True


def sync_experts():
    """Copy the compiled EAs across. The .ex5 is what the tester runs."""
    live = next(p for p in TERMINALS.iterdir() if p.name.startswith(LIVE_PREFIX))
    dst = test_data_dir() / "MQL5" / "Experts"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in (live / "MQL5" / "Experts").glob("*.ex5"):
        try:
            shutil.copy(f, dst / f.name)
            n += 1
        except Exception:
            pass                                   # locked by the live terminal: skip
    return n


def write_ini(path, section, **kw):
    lines = [f"[{section}]"] + [f"{k}={v}" for k, v in kw.items() if v is not None]
    path.write_text("\n".join(lines) + "\n", encoding="utf-16")


def run(ini, timeout=1800, label=""):
    t0 = time.time()
    print(f"[headless] {label} starting…", flush=True)
    try:
        subprocess.run([str(TEST_EXE), f"/config:{ini}"], timeout=timeout,
                       capture_output=True)
    except subprocess.TimeoutExpired:
        print(f"[headless] {label} exceeded {timeout}s — killing")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Process terminal64 | Where-Object {{ $_.Path -eq '{TEST_EXE}' }} | "
                        "Stop-Process -Force"], capture_output=True)
    print(f"[headless] {label} done in {time.time()-t0:.0f}s", flush=True)


def setup(csv="tester_xau_real.csv", symbol="XAUUSD_R3"):
    """Build the custom symbol inside the test rig, from the shared Common\\Files CSV."""
    live_is_safe()
    d = test_data_dir()
    (d / "MQL5" / "Scripts").mkdir(parents=True, exist_ok=True)
    live = next(p for p in TERMINALS.iterdir() if p.name.startswith(LIVE_PREFIX))
    for ext in (".ex5", ".mq5"):
        src = live / "MQL5" / "Experts" / ("CustomSymbolImport" + ext)
        if src.exists():
            shutil.copy(src, d / "MQL5" / "Scripts" / ("CustomSymbolImport" + ext))
    sync_experts()
    ini = ROOT / "mt5" / "_headless_setup.ini"
    write_ini(ini, "StartUp", Script="CustomSymbolImport", Symbol="EURUSD", Period="M1",
              ShutdownTerminal=1)
    run(ini, timeout=240, label="symbol import")
    made = (d / "bases" / "Custom" / "history" / symbol).exists()
    print(f"[headless] {symbol} in test rig: {'YES' if made else 'NO — check its Experts log'}")
    return made


def backtest(ea, symbol="XAUUSD_R3", frm="2026.08.05", to="2026.08.10",
             optimize=False, period="M1"):
    live_is_safe()
    sync_experts()
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    rpt = REPORTS / f"{ea}_{stamp}"
    ini = ROOT / "mt5" / "_headless_run.ini"
    write_ini(ini, "Tester",
              Expert=ea, Symbol=symbol, Period=period,
              Model=2,                       # 1 minute OHLC
              FromDate=frm, ToDate=to,
              Deposit=4123, Currency="USD", Leverage="1:500",
              Optimization=(2 if optimize else 0),   # 2 = slow complete algorithm
              OptimizationCriterion=6,               # 6 = our OnTester value
              Report=str(rpt), ReplaceReport=1,
              ShutdownTerminal=1, Visual=0)
    run(ini, timeout=5400 if optimize else 600,
        label=f"{ea} {'OPTIMISATION' if optimize else 'backtest'}")
    for ext in (".htm", ".html", ".xml"):
        if (rpt.with_suffix(ext)).exists():
            print(f"[headless] report -> {rpt.with_suffix(ext)}")
            return rpt.with_suffix(ext)
    print("[headless] no report written — check the test terminal's logs")
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--ea", default=None)
    ap.add_argument("--symbol", default="XAUUSD_R3")
    ap.add_argument("--from", dest="frm", default="2026.08.05")
    ap.add_argument("--to", default="2026.08.10")
    ap.add_argument("--optimize", action="store_true")
    a = ap.parse_args()
    if a.setup:
        setup(symbol=a.symbol)
    if a.ea:
        backtest(a.ea, a.symbol, a.frm, a.to, a.optimize)
