"""deploy_ea.py — repo .mq5 -> MT5 Experts -> CLI compile -> verified, one command.

Encodes the pipeline proven 2026-08-04: copy the source, compile headless via
MetaEditor, parse the log for "0 errors". If the EA is already ATTACHED to a chart,
MT5 hot-reloads the new build in place (observed: removed->loaded within the same
second), so no drag/F7 is needed for an EA that lives on the chart. The staleness
guard in CaseSignalExecutor v1.10 makes that reload safe (no stale-signal refire).

The old flow this replaces: edit repo file -> ask Zee to copy -> F7 -> drag.
[[feedback-modify-ea-defaults-not-inputs]] still applies: change SOURCE defaults
and bump #property version; never ask for input-dialog edits.

Usage:
    py monitor/deploy_ea.py CaseSignalExecutor          # copy + compile + verify
    py monitor/deploy_ea.py NsndTrader TurtleTradeLogger
Exit code 0 = every EA compiled clean; 1 = something failed (details printed).

GOTCHA: metaeditor64.exe's own exit code is the NUMBER OF FILES COMPILED, not 0 —
never test it for success. The log line "Result: N errors" is the truth.
"""
from __future__ import annotations
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO_MQ5 = Path(__file__).resolve().parent.parent / "mt5"
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")
EXPERTS = TERMINAL / "MQL5" / "Experts"
METAEDITOR = Path(r"C:/Program Files/Blueberry Markets MetaTrader 5/metaeditor64.exe")


def deploy(name: str) -> bool:
    src = REPO_MQ5 / f"{name}.mq5"
    if not src.exists():
        print(f"  {name}: NO SOURCE at {src}")
        return False
    dst = EXPERTS / src.name
    shutil.copy2(src, dst)
    log = Path(tempfile.gettempdir()) / f"compile_{name}.log"
    log.unlink(missing_ok=True)
    subprocess.run([str(METAEDITOR), f"/compile:{dst}", f"/log:{log}"],
                   capture_output=True, timeout=120)   # exit code = files compiled, ignore
    try:
        text = log.read_text(encoding="utf-16", errors="ignore")
    except Exception:
        text = log.read_text(errors="ignore")
    m = re.search(r"Result:\s*(\d+)\s*errors?,\s*(\d+)\s*warnings?", text)
    if not m:
        print(f"  {name}: compile log unreadable — treat as FAILED\n{text[-400:]}")
        return False
    errs, warns = int(m.group(1)), int(m.group(2))
    ok = errs == 0
    print(f"  {name}: {'OK' if ok else 'FAILED'} — {errs} errors, {warns} warnings"
          + ("  (hot-reload NOT guaranteed — reattach and verify the load fingerprint)" if ok else ""))
    if not ok:
        for line in text.splitlines():
            if ": error" in line:
                print("    ", line.strip()[:120])
    return ok


if __name__ == "__main__":
    names = sys.argv[1:] or ["CaseSignalExecutor"]
    results = [deploy(n.removesuffix(".mq5")) for n in names]
    sys.exit(0 if all(results) else 1)
