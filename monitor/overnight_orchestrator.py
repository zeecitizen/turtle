"""overnight_orchestrator.py — runs MT5 Strategy Tester headlessly + iterates.

Headless backtest via MT5 command-line:
  terminal64.exe /config:tester.ini  with ShutdownTerminal=1
  blocks until tester completes + MT5 shuts down

USAGE (called by Claude during overnight loop):
  py overnight_orchestrator.py --tester-ini path/to/tester.ini
  → returns final balance + trade count from logs

  py overnight_orchestrator.py --restart-live
  → relaunches MT5 (Blueberry) so live trading resumes
"""
import sys, os, time, subprocess, json, re, argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

MT5_EXE = r"C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
TERMINAL_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8")
LOG_DIR = TERMINAL_DIR / "Tester" / "logs"
JOURNAL = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\overnight_loop.jsonl")


def log(event: dict):
    event["ts_utc"] = datetime.now(timezone.utc).isoformat()
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def kill_mt5():
    """Forcibly kill running terminal64.exe instances."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "terminal64.exe"],
                       capture_output=True, timeout=10)
        time.sleep(2)
        log({"action": "kill_mt5", "ok": True})
    except Exception as e:
        log({"action": "kill_mt5", "ok": False, "err": str(e)})


def run_headless_tester(ini_path: str, timeout_sec: int = 900) -> dict:
    """Launch MT5 with /config flag, wait for shutdown. Returns parsed result."""
    # First force-close any running terminal
    kill_mt5()
    # Make sure ini has ShutdownTerminal=1
    ini = Path(ini_path).read_text(encoding="utf-8")
    if "ShutdownTerminal=0" in ini:
        ini = ini.replace("ShutdownTerminal=0", "ShutdownTerminal=1")
        Path(ini_path).write_text(ini, encoding="utf-8")
    elif "ShutdownTerminal=" not in ini:
        # Add it after [Tester] section
        ini = ini.replace("[Tester]", "[Tester]\nShutdownTerminal=1", 1)
        Path(ini_path).write_text(ini, encoding="utf-8")

    log({"action": "tester_start", "ini": str(ini_path)})
    start = time.time()
    try:
        # Use subprocess to launch + wait for it to exit
        proc = subprocess.Popen([MT5_EXE, f"/config:{ini_path}"])
        proc.wait(timeout=timeout_sec)
        elapsed = time.time() - start
        log({"action": "tester_done", "elapsed_sec": round(elapsed, 1)})
    except subprocess.TimeoutExpired:
        proc.kill()
        log({"action": "tester_timeout", "elapsed_sec": timeout_sec})
        return {"ok": False, "err": "timeout"}
    except Exception as e:
        log({"action": "tester_crash", "err": str(e)})
        return {"ok": False, "err": str(e)}

    # Parse latest log file for results
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return {"ok": False, "err": "no_log"}
    with logs[0].open("rb") as f:
        content = f.read().decode("utf-16le", errors="ignore")

    test_ends = list(re.finditer(r"Test passed in", content))
    if not test_ends:
        return {"ok": False, "err": "test_didnt_complete", "log": logs[0].name}

    # Last run
    last_start = test_ends[-2].end() if len(test_ends) >= 2 else 0
    chunk = content[last_start:test_ends[-1].end() + 500]
    fb = re.findall(r"final balance ([\d.]+)", chunk)
    duration = re.findall(r"Test passed in ([\d:.]+)", chunk)
    filled = re.findall(r"\[FILLED\] ticket=", chunk)
    tick_revs = re.findall(r"TICK-REV[^\n]*banked \+([\d.]+)pts", chunk)

    result = {
        "ok": True,
        "ini": Path(ini_path).name,
        "final_balance": float(fb[-1]) if fb else None,
        "starting_balance": 2058,
        "net_pnl": float(fb[-1]) - 2058 if fb else None,
        "trades": len(filled),
        "trail_exits": len(tick_revs),
        "duration": duration[-1] if duration else None,
        "log_file": logs[0].name,
    }
    log({"action": "tester_result", **result})
    return result


def restart_live():
    """Relaunch MT5 normally so live EA can resume."""
    kill_mt5()
    time.sleep(2)
    subprocess.Popen([MT5_EXE])
    log({"action": "live_relaunch"})
    print(f"Relaunched MT5 — live EA should resume from saved chart state.")
    # Give it time to boot
    time.sleep(20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tester-ini", help="Run MT5 headless tester with this ini")
    ap.add_argument("--timeout", type=int, default=900, help="Max test duration sec")
    ap.add_argument("--restart-live", action="store_true", help="Relaunch MT5 normally")
    args = ap.parse_args()

    if args.tester_ini:
        r = run_headless_tester(args.tester_ini, args.timeout)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1

    if args.restart_live:
        restart_live()
        return 0

    print("Specify --tester-ini PATH or --restart-live")
    return 2


if __name__ == "__main__":
    sys.exit(main())
