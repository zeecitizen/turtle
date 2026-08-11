"""refresh_eas.py — one-command EA deploy + compile across MT5 terminals.

The MT5 auto-reload feature picks up new .ex5 files automatically while the EA
is attached to a chart — so this script just needs to:
  1. Copy the .mq5 from the turtle/ repo to the target terminal's Experts folder
  2. Compile via MetaEditor command-line
  3. Parse the compile log and report errors/warnings cleanly
The user does nothing in MT5 — the running EA reloads itself.

Usage:
    python refresh_eas.py                                  # default: refresh all EAs on Atmos
    python refresh_eas.py --ea Feb11TickMedium             # one EA on Atmos
    python refresh_eas.py --terminal ftmo                  # all EAs on FTMO
    python refresh_eas.py -e Feb11TickMedium -t atmos      # one EA on one terminal
    python refresh_eas.py --terminal all                   # everywhere we have a terminal
    python refresh_eas.py --list                           # show what's known

CAVEAT: changing input DEFAULTS in source (e.g. InpLots = 0.05) won't update
a running EA's effective inputs — MT5 saves the user-chosen inputs in the chart
template. For those changes the user must edit inputs in MT5's Properties
dialog (right-click chart → Expert Advisors → Properties) or detach+reattach.
This script handles everything else (logic changes, bug fixes, new versions).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Each MT5 terminal lives at AppData\Roaming\MetaQuotes\Terminal\<GUID>\
# Maps friendly name → GUID.
TERMINALS = {
    "atmos":     "997C47BF6122E1564BE4267B96E7F5C7",  # AtmosGlobal-LIVE (real prop firm challenge)
    "ftmo":      "81A933A9AFC5DE3C23B15CAB19C63850",  # FTMO-Demo (validation paper account)
    "exness":    "53785E099C927DB68A545C249CDBCE06",  # Exness live (Shano's micro)
    "blueberry": "D0E8209F77C8CF37AD8BF550E51FF075",  # Blueberry MT5
}

# EAs we deploy via this script. Add new ones here.
ALL_EAS = [
    "Feb11TickMedium",
    "Feb11TickTrader",
    "TurtleTradeLogger",
    "ShanoTickLogger",
]

REPO_ROOT      = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
SRC_DIR        = REPO_ROOT / "mt5"
TERMINAL_ROOT  = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal")
LOG_DIR        = SRC_DIR

# MetaEditor candidates — try each until one exists.
# Any MT5 MetaEditor can compile any MT5 .mq5; they produce the same .ex5.
METAEDITOR_CANDIDATES = [
    Path(r"C:\Program Files\Atmos Global MT5 Terminal\MetaEditor64.exe"),
    Path(r"C:\Program Files\Blueberry Markets MetaTrader 5\MetaEditor64.exe"),
    Path(r"C:\Program Files\FTMO Global Markets MT5 Terminal\MetaEditor64.exe"),
    Path(r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"),
    Path(r"C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe"),
]


def find_metaeditor():
    for p in METAEDITOR_CANDIDATES:
        if p.exists():
            return p
    return None


def parse_compile_log(log_path: Path):
    """Parse MetaEditor log (UTF-16 LE encoded) and extract the 'Result:' line."""
    try:
        text = log_path.read_text(encoding="utf-16-le", errors="ignore")
    except Exception as e:
        return None, f"log read failed: {e}"
    for line in text.split("\n"):
        if "Result:" in line:
            return line.strip().lstrip("﻿"), None
    return None, "no Result line in log"


def refresh_one(ea_name: str, terminal_name: str, metaeditor: Path) -> bool:
    src = SRC_DIR / f"{ea_name}.mq5"
    if not src.exists():
        print(f"  ✗ {ea_name}: source not in repo ({src})")
        return False
    guid = TERMINALS[terminal_name]
    dst_dir = TERMINAL_ROOT / guid / "MQL5" / "Experts"
    if not dst_dir.exists():
        print(f"  ⊘ {ea_name}: {terminal_name} terminal folder not found, skipping")
        return False
    dst = dst_dir / f"{ea_name}.mq5"
    log = LOG_DIR / f"{ea_name}_{terminal_name}.compile.log"
    shutil.copy2(src, dst)
    try:
        subprocess.run(
            [str(metaeditor), f"/compile:{dst}", f"/log:{log}"],
            capture_output=True, text=True, timeout=120, check=False
        )
    except subprocess.TimeoutExpired:
        print(f"  ✗ {ea_name}: compile timed out (>120s)")
        return False
    except Exception as e:
        print(f"  ✗ {ea_name}: compile crashed: {e}")
        return False
    result, err = parse_compile_log(log)
    if err:
        print(f"  ⚠ {ea_name}: {err}")
        return False
    # Result line: "Result: 0 errors, 0 warnings, NNN ms elapsed, ..."
    if "0 errors" in result:
        warns = "0 warnings" not in result
        tag = "✓" if not warns else "⚠"
        print(f"  {tag} {ea_name}: {result}")
        return True
    else:
        print(f"  ✗ {ea_name}: {result}")
        return False


def list_state():
    print("Terminals (✓ = installed):")
    for name, guid in TERMINALS.items():
        path = TERMINAL_ROOT / guid
        exists = "✓" if path.exists() else "✗"
        experts = path / "MQL5" / "Experts"
        ex5_count = len(list(experts.glob("*.ex5"))) if experts.exists() else 0
        print(f"  {exists} {name:11s} ({ex5_count} .ex5 files)  GUID {guid}")
    print()
    print("EA sources in repo:")
    for ea in ALL_EAS:
        src = SRC_DIR / f"{ea}.mq5"
        exists = "✓" if src.exists() else "✗"
        size = f"{src.stat().st_size:,} bytes" if src.exists() else "—"
        print(f"  {exists} {ea}.mq5  ({size})")
    print()
    me = find_metaeditor()
    print(f"MetaEditor: {me if me else 'NOT FOUND — install MT5 first'}")


def main():
    ap = argparse.ArgumentParser(
        description="Refresh + compile EAs in MT5. MT5 auto-reloads attached EAs on .ex5 change.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--terminal", "-t", default="atmos",
                    choices=list(TERMINALS.keys()) + ["all"],
                    help="Target terminal (default: atmos)")
    ap.add_argument("--ea", "-e", default="all",
                    help=f"EA name without .mq5, or 'all' (default: all). Available: {', '.join(ALL_EAS)}")
    ap.add_argument("--list", action="store_true",
                    help="List available terminals + EA sources and exit")
    args = ap.parse_args()

    if args.list:
        list_state()
        return 0

    metaeditor = find_metaeditor()
    if not metaeditor:
        print("ERROR: no MetaEditor64.exe found. Tried:")
        for p in METAEDITOR_CANDIDATES:
            print(f"  - {p}")
        return 2

    if args.ea == "all":
        eas = ALL_EAS
    elif args.ea in ALL_EAS:
        eas = [args.ea]
    else:
        print(f"ERROR: unknown EA '{args.ea}'. Known: {', '.join(ALL_EAS)}")
        return 2

    terminals = list(TERMINALS.keys()) if args.terminal == "all" else [args.terminal]

    print(f"Using MetaEditor: {metaeditor}")
    print(f"Refreshing {len(eas)} EA(s) on {len(terminals)} terminal(s)")
    print()

    fails = []
    for terminal in terminals:
        guid = TERMINALS[terminal]
        if not (TERMINAL_ROOT / guid).exists():
            print(f"=== {terminal} === SKIP (not installed)\n")
            continue
        print(f"=== {terminal} ===")
        for ea in eas:
            if not refresh_one(ea, terminal, metaeditor):
                fails.append(f"{ea}/{terminal}")
        print()

    if fails:
        print(f"⚠  {len(fails)} failure(s): {', '.join(fails)}")
        return 1
    print("✓ All refreshes successful.")
    print("  Attached EAs will auto-reload on next tick. Input defaults changes")
    print("  require manual Inputs-dialog edit or detach+reattach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
