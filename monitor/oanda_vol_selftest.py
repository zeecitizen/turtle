"""oanda_vol_selftest.py — proves HIS eye's volume is really reaching the EA.

Zee 2026-08-21: "make the fix so this error does not surface again, add checks,
error catchers etc."

The failure this exists to kill: ZeeUHV v1.58 asks for OANDA volume, the table goes
stale or missing, and the EA falls back to BROKER volume — trading continues, logs
look healthy, and the whole switch has quietly reverted. It happened twice in one
day (both times: daemon launched under an interpreter without tvDatafeed).

Seven checks, end to end. Exit code 0 = the chain is intact, 1 = it is broken.
Run it any time:  py monitor/oanda_vol_selftest.py
"""
from __future__ import annotations
import json, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
VOL_F = COMMON / "oanda_vol.csv"
HEARTBEAT = ROOT / "monitor" / "oanda_vol_heartbeat.json"
LOGS = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Logs")
INTERPRETERS = [r"C:\Users\zeesh\AppData\Local\Python\pythoncore-3.14-64\python.exe",
                r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"]
STALE_MIN = 5

results = []


def quick_status(miss_window_min=5):
    """Fast, subprocess-free health read for the cockpit (Zee 2026-08-21: "maybe we
    can display the error on the GUI camel"). Returns (ok, headline, detail)."""
    try:
        if not VOL_F.exists():
            return (False, "OANDA VOLUME MISSING — EA on BROKER volume",
                    "oanda_vol.csv not found")
        age = (time.time() - VOL_F.stat().st_mtime) / 60.0
        last = VOL_F.read_text(encoding="ascii", errors="ignore").splitlines()[-1]
        newest = datetime.strptime(last.split(",")[0], "%Y.%m.%d %H:%M")
        lag = (datetime.utcnow() + timedelta(hours=3) - newest).total_seconds() / 60.0
        misses = 0
        try:
            lg = max(LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime)
            raw = lg.read_bytes()
            txt = (raw.decode("utf-16-le", "ignore") if raw[:2] == b"\xff\xfe"
                   else raw.decode("utf-8", "ignore"))
            cutoff = (datetime.now() - timedelta(minutes=miss_window_min)).strftime("%H:%M:%S")
            for l in txt.splitlines()[-600:]:
                p = l.split("\t")
                if "OANDA VOLUME MISS" in l and len(p) > 2 and p[2][:8] >= cutoff:
                    misses += 1
        except Exception:
            pass
        if age > STALE_MIN or lag > STALE_MIN:
            return (False, f"OANDA VOLUME STALE {max(age, lag):.0f} min — EA fell back to BROKER volume",
                    f"file {age:.1f} min old · newest minute {lag:.1f} min behind")
        if misses:
            return (False, f"OANDA VOLUME MISSES ×{misses} in {miss_window_min} min — some bars used BROKER volume",
                    f"table fresh ({age:.1f} min) but the EA could not find those minutes")
        return (True, f"OANDA volume LIVE · table {age:.1f} min fresh",
                f"newest minute {lag:.1f} min behind the server clock")
    except Exception as e:
        return (False, "OANDA volume status unreadable", str(e)[:90])


def check(name, ok, detail=""):
    results.append((ok, name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main():
    print("OANDA VOLUME CHAIN — self test\n")

    # 1. every interpreter that might launch the collector must HAVE tvDatafeed.
    #    (The 2026-08-21 root cause: ARM64 python lacked it, the daemon died on
    #    ImportError inside a hidden console, twice, silently.)
    missing = []
    for exe in INTERPRETERS:
        if not Path(exe).exists():
            continue
        try:
            r = subprocess.run([exe, "-c", "import tvDatafeed"],
                               capture_output=True, timeout=40)
            if r.returncode != 0:
                missing.append(Path(exe).parent.name)
        except Exception:
            missing.append(Path(exe).parent.name)
    check("tvDatafeed importable by every interpreter", not missing,
          "missing in: " + ", ".join(missing) if missing else "all OK")

    # 2. the supervisor process is alive
    alive = False
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name LIKE '%python%'\" "
                            "| Where-Object { $_.CommandLine -like '*oanda_vol_supervisor*' } "
                            "| Select-Object -First 1 -ExpandProperty ProcessId"],
                           capture_output=True, text=True, timeout=60)
        alive = bool(r.stdout.strip())
    except Exception:
        pass
    check("supervisor process running", alive,
          "start: py monitor/oanda_vol_supervisor.py" if not alive else "")

    # 3. the table file exists
    if not check("oanda_vol.csv exists", VOL_F.exists(), str(VOL_F)):
        return finish()

    # 4. it is FRESH (the silent-revert tell)
    age = (time.time() - VOL_F.stat().st_mtime) / 60.0
    check(f"table fresh (<{STALE_MIN} min)", age < STALE_MIN, f"{age:.1f} min old")

    # 5. it parses, is sorted, and carries plausible volumes
    rows, bad = [], 0
    for ln in VOL_F.read_text(encoding="ascii", errors="ignore").splitlines():
        p = ln.split(",")
        if len(p) != 2:
            bad += 1; continue
        try:
            rows.append((datetime.strptime(p[0], "%Y.%m.%d %H:%M"), int(p[1])))
        except Exception:
            bad += 1
    ok_parse = bool(rows) and bad == 0 and all(
        rows[i][0] < rows[i + 1][0] for i in range(len(rows) - 1))
    check("table parses, sorted, no bad rows", ok_parse,
          f"{len(rows)} rows, {bad} bad")

    # 6. its newest minute is close to NOW in SERVER time (server = UTC+3).
    #    A file written recently but carrying old minutes = feed stalled upstream.
    if rows:
        newest = rows[-1][0]
        server_now = datetime.utcnow() + timedelta(hours=3)
        lag = (server_now - newest).total_seconds() / 60.0
        check(f"newest minute current (<{STALE_MIN} min behind server clock)",
              lag < STALE_MIN, f"{newest:%Y-%m-%d %H:%M} server, {lag:.1f} min behind")

    # 7. the LIVE EA is not quietly eating misses
    try:
        lg = max(LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime)
        raw = lg.read_bytes()
        txt = raw.decode("utf-16-le", "ignore") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", "ignore")
        # only misses in the LAST 10 MINUTES matter — historical ones are the
        # scars of an outage already fixed, and counting them would make this
        # check fail forever (it did, on its first run: 10 lines from the stale
        # window at 17:36 while the feed was healthy again by 17:37).
        cutoff = (datetime.now() - timedelta(minutes=10)).strftime("%H:%M:%S")
        fresh_miss, loaded = [], []
        for l in txt.splitlines()[-800:]:
            parts = l.split("\t")
            stamp = parts[2][:8] if len(parts) > 2 else ""
            if "OANDA VOLUME MISS" in l and stamp >= cutoff:
                fresh_miss.append(l)
            if "OANDA volume table loaded" in l and stamp >= cutoff:
                loaded.append(l)
        check("EA taking OANDA volume now (no misses in last 10 min)", not fresh_miss,
              f"{len(fresh_miss)} miss(es) in the last 10 min — EA is on BROKER volume"
              if fresh_miss else
              (f"{len(loaded)} table reload(s) in the last 10 min" if loaded
               else "EA quiet (no reloads logged — is ZeeUHV attached and v1.58?)"))
    except Exception as e:
        check("EA log readable", False, str(e)[:80])

    return finish()


def finish():
    bad = [r for r in results if not r[0]]
    print()
    if bad:
        print(f"CHAIN BROKEN — {len(bad)} check(s) failed. ZeeUHV may be silently on BROKER volume.")
        for _, name, detail in bad:
            print(f"   · {name} — {detail}")
        return 1
    print("CHAIN INTACT — the EA is judging UHVs on OANDA volume.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
