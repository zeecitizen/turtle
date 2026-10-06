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

# MORE THAN ONE MT5 NOW (2026-09-12). Zee: "i want to move our VSISA EA from Blueberry
# MT5 to AXI MT5 ... this enables us to use AXI volume which happens to be more accurate
# on the VSISA strategy." An EA deployed to the wrong terminal looks like a successful
# deploy and simply never runs, so the target is named rather than assumed.
TERMINALS = {
    "blueberry": {
        "data": Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                     r"/DBE9B8B347D025DD139E103EE3B63FD8"),
        "editor": Path(r"C:/Program Files/Blueberry Markets MetaTrader 5"
                       r"/metaeditor64.exe"),
    },
    # Axi REINSTALLED itself into Program Files on 2026-09-12, which gave it a NEW
    # data folder and orphaned everything in the old one. The previous pair is kept
    # below so an older deploy can still be found if it is ever needed.
    "axi": {
        "data": Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                     r"/6FBEE76C719DC78AB2AE839B5A0C7442"),
        "editor": Path(r"C:/Program Files/Axi MetaTrader 5 Terminal"
                       r"/MetaEditor64.exe"),
    },
    # PXBT (Zee 2026-10-03: "have you placed the EA in the prime XBT folders"). Note the
    # editor here is MetaEditor64.exe with capitals - a lowercase glob misses it.
    "pxbt": {
        "data": Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                     r"/BCB580088311575081ABF4FB040CCFF8"),
        "editor": Path(r"C:/Program Files/PXBT Trading MT5 Terminal"
                       r"/MetaEditor64.exe"),
    },
    # EXNESS, added 2026-10-05. This is the first feed in the project with gold OPEN and a
    # real DOM, which is what every "test it on gold" note in TICK_SPEED.md has been waiting
    # for. Editor is MetaEditor64.exe with capitals, same as PXBT.
    "exness": {
        "data": Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                     r"/53785E099C927DB68A545C249CDBCE06"),
        "editor": Path(r"C:/Program Files/MetaTrader 5 EXNESS"
                       r"/MetaEditor64.exe"),
    },
    "axi-old": {
        "data": Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                     r"/0FE5F202FCDE117C6EFAB41A7BC984CD"),
        "editor": Path(r"C:/Users/zeesh/AppData/Roaming/Axi MetaTrader 5 Terminal"
                       r"/metaeditor64.exe"),
    },
}
DEFAULT_TERMINAL = "blueberry"

# An EA that lives on a particular broker must FOLLOW it. VSISA and its pullback
# sibling were moved to Axi for the volume feed; deploying them with the default
# target silently compiled them into Blueberry, where nothing ever ran them.
# An explicit --terminal still wins.
EA_HOME = {
    "VSISA": "axi",
    "VSISA_Pullbacks": "axi",
}

TERMINAL = TERMINALS[DEFAULT_TERMINAL]["data"]
EXPERTS = TERMINAL / "MQL5" / "Experts"
METAEDITOR = TERMINALS[DEFAULT_TERMINAL]["editor"]


def use_terminal(key: str):
    """Point the module at one of the installs above."""
    global TERMINAL, EXPERTS, METAEDITOR
    if key not in TERMINALS:
        raise SystemExit("unknown terminal %r — have %s"
                         % (key, ", ".join(TERMINALS)))
    TERMINAL = TERMINALS[key]["data"]
    EXPERTS = TERMINAL / "MQL5" / "Experts"
    METAEDITOR = TERMINALS[key]["editor"]
    if not METAEDITOR.exists():
        raise SystemExit("MetaEditor missing for %r at %s" % (key, METAEDITOR))
    EXPERTS.mkdir(parents=True, exist_ok=True)
    print("[deploy] target: %s  ->  %s" % (key, EXPERTS))


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
    args = sys.argv[1:]
    # --terminal axi | --terminal blueberry   (default: blueberry)
    explicit_terminal = "--terminal" in args
    if "--terminal" in args:
        i = args.index("--terminal")
        use_terminal(args[i + 1])
        del args[i:i + 2]
    names = args or ["CaseSignalExecutor"]
    results = []
    for n in names:
        n = n.removesuffix(".mq5")
        if not explicit_terminal:
            use_terminal(EA_HOME.get(n, DEFAULT_TERMINAL))
        results.append(deploy(n))
    sys.exit(0 if all(results) else 1)
