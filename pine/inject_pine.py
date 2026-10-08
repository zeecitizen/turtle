"""inject_pine.py - push turtle.pine into TradingView Desktop, compile, save, verify.

One call instead of five bridge commands:

    python pine/inject_pine.py                      # inject turtle.pine
    python pine/inject_pine.py --set uDev=false     # ...and set chart inputs BY NAME
    python pine/inject_pine.py path/to/other.pine --expect "Other Script"

What it does, in order (stops at the first failure):
  1. TradingView must be bridged (CDP :9222)       -> else: run launch_tv_bridge.bat
  2. The Pine Editor must already hold THIS script -> never paste over a different one
  3. No alerts may exist                           -> a save leaves alerts on the OLD code
                                                      (pine/save_and_refresh_alert.md)
  4. set source, compile+save, read errors         -> errors printed with line numbers
  5. read the editor back and compare to the file  -> proves what TradingView now holds
  6. optional --set NAME=VALUE                      -> the chart keeps its OWN saved inputs
                                                      after a save, so a new default does
                                                      not reach it; this sets them directly

Drives the tradesdontlie/tradingview-mcp CLI. Start TradingView with launch_tv_bridge.bat.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRIDGE_CLI = Path(r"C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js")
NODE = Path(r"C:\Program Files\nodejs\node.exe")
CDP_URL = "http://127.0.0.1:9222/json/version"

# Same pattern the input numbering was verified with on 2026-10-08: 140 declarations in the
# source, 140 in_N inputs on the chart, uDev = in_139.
INPUT_DECL = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*input(?:\.\w+)?\(", re.M)


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def tv(*args):
    """Run one bridge CLI command and return its parsed JSON."""
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)   # VS Code sets it; keep it away from anything Electron
    r = subprocess.run([str(NODE), str(BRIDGE_CLI), *args], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        fail(f"bridge gave no JSON for {' '.join(args)}:\n{r.stdout}{r.stderr}")


def normalise(src):
    return src.lstrip("\ufeff").replace("\r\n", "\n").rstrip()


def script_name(src):
    m = re.search(r'^\s*(?:indicator|strategy|library)\(\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else None


def parse_value(raw):
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def main():
    ap = argparse.ArgumentParser(description="Inject a Pine script into TradingView Desktop.")
    ap.add_argument("file", nargs="?", default=str(REPO / "turtle.pine"))
    ap.add_argument("--expect", help="script title the editor must already hold "
                                     "(default: the title declared in the file)")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="set a chart input by its Pine variable name, e.g. uDev=false")
    ap.add_argument("--force", action="store_true",
                    help="skip the editor-holds-this-script and no-alerts checks")
    args = ap.parse_args()

    path = Path(args.file).resolve()
    if not path.exists():
        fail(f"{path} not found")
    for p in (NODE, BRIDGE_CLI):
        if not p.exists():
            fail(f"{p} not found - is the bridge installed?")
    src = path.read_text(encoding="utf-8")
    want = args.expect or script_name(src)
    print(f"Injecting {path.name}  ({len(src.splitlines())} lines, script \"{want}\")")

    # 1. bridged?
    try:
        urllib.request.urlopen(CDP_URL, timeout=3).read()
    except OSError:
        fail("TradingView is not bridged (no CDP on :9222). Run launch_tv_bridge.bat first.")

    # 2. the editor must already hold this script
    current = tv("pine", "get")
    if not current.get("success"):
        fail(f"could not read the Pine Editor: {current}")
    held = script_name(current.get("source", ""))
    if not args.force and want and held != want:
        fail(f"the Pine Editor holds \"{held}\", not \"{want}\". Open the right script in the "
             f"Pine Editor (or pass --force).")
    if normalise(current.get("source", "")) == normalise(src):
        print("  editor already holds this exact source - re-saving anyway")

    # 3. alerts would keep running the old version after a save
    alerts = tv("alert", "list")
    n_alerts = alerts.get("alert_count", 0)
    if n_alerts and not args.force:
        fail(f"{n_alerts} alert(s) exist. Saving leaves them on the OLD code and they must be "
             f"recreated by hand (pine/save_and_refresh_alert.md). Pass --force if you accept that.")

    # 4. set, compile+save, errors
    r = tv("pine", "set", "--file", str(path))
    if not r.get("success"):
        fail(f"pine set failed: {r}")
    print(f"  [OK] source set ({r.get('lines_set')} lines)")
    r = tv("pine", "compile")
    errs = tv("pine", "errors")
    # Monaco severities: 8 = error, 4 = warning, 2 = info. The bridge counts warnings as errors,
    # and turtle.pine carries ~26 long-standing ones (Pine v5, shorttitle length, ta.* in scopes).
    markers = errs.get("errors", []) or r.get("errors", [])
    real = [e for e in markers if e.get("severity", 8) >= 8]
    if not r.get("success") or real:
        print("[FAIL] compile errors:")
        for e in real or markers:
            print(f"    line {e.get('line')}:{e.get('column')}  {e.get('message')}")
        sys.exit(1)
    warn = len(markers) - len(real)
    print(f"  [OK] compiled, no errors ({warn} warnings) - clicked \"{r.get('button_clicked')}\"")

    # 5. what does TradingView hold now?
    after = tv("pine", "get")
    if normalise(after.get("source", "")) != normalise(src):
        fail("the editor does NOT match the file after injecting - check the Pine Editor")
    print("  [OK] editor matches the file")

    # 6. chart inputs, by name
    if args.set:
        names = [m.group(1) for m in INPUT_DECL.finditer(src)]
        state = tv("state")
        study = next((s for s in state.get("studies", []) if want and want in s.get("name", "")),
                     None)
        if not study:
            fail(f"\"{want}\" is not on the chart - cannot set inputs")
        ind = tv("indicator", "get", study["id"])
        chart_n = sum(1 for i in ind.get("inputs", []) if re.fullmatch(r"in_\d+", i.get("id", "")))
        if chart_n != len(names):
            fail(f"the source declares {len(names)} inputs but the chart has {chart_n} - the "
                 f"numbering cannot be trusted, inputs NOT set")
        overrides = {}
        for item in args.set:
            name, _, raw = item.partition("=")
            if name not in names:
                fail(f"no input named {name} in {path.name}")
            overrides[f"in_{names.index(name)}"] = parse_value(raw)
        r = tv("indicator", "set", study["id"], "-i", json.dumps(overrides))
        if not r.get("success"):
            fail(f"indicator set failed: {r}")
        print(f"  [OK] chart inputs set: {', '.join(args.set)}")

    print("Done - the indicator on the chart is running the new code.")


if __name__ == "__main__":
    main()
