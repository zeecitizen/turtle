"""make_ea_from_settings.py - the "MT5 EA maker" end of the settings hand-off (Zee 2026-10-20: "maybe we can make TV generate a json turtle can
read, and turtle export a json the mt5 EA maker can read.. a json of settings").

Reads a turtle-settings/1 JSON (written by Turtle TV: settings/tradingview_latest.json, settings/turtletv_export_latest.json or
settings/<EA>_TurtleTV_<run>.json) and writes a copy of the EA whose input DEFAULTS are those settings (Zee's rule: settings live in the
EA's defaults, not in the inputs dialog). Every changed default is printed old -> new. It never touches the ledger: shipping a version
still means VERSION.md + VERSION_HISTORY.md in the same commit.

   py monitor/saad_view/make_ea_from_settings.py settings/turtletv_export_latest.json --out Saad_strategy_15min_candidate
   py monitor/saad_view/make_ea_from_settings.py <json> --out Saad_strategy_15min --version 1.28 --in-place     (a release: overwrites the EA)
Options: --magic N (default: keep the EA's) · --version X.YY (sets #property version and the trade comment)"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def num(x):
    try:
        return float(x)
    except ValueError:
        return None


ap = argparse.ArgumentParser()
ap.add_argument("json")
ap.add_argument("--out", required=True, help="new EA file name in mt5/ (without .mq5)")
ap.add_argument("--version")
ap.add_argument("--magic", type=int)
ap.add_argument("--in-place", action="store_true", help="allow --out to be the source EA itself (a release)")
a = ap.parse_args()

doc = json.loads(Path(a.json).read_text(encoding="utf-8"))
if doc.get("format") != "turtle-settings/1":
    sys.exit(f"not a turtle-settings/1 file: {a.json}")
src = ROOT / "mt5" / f"{doc['ea']}.mq5"
dst = ROOT / "mt5" / f"{a.out}.mq5"
if dst.resolve() == src.resolve() and not a.in_place:
    sys.exit(f"--out {a.out} would overwrite {src.name}; add --in-place for a release")
t = src.read_text(encoding="utf-8")
declared = {m.group(1) for m in re.finditer(r"^input\s+\w+\s+(\w+)\s*=\s*[^;]+;", t, re.M)}
provided = set(doc.get("ea_inputs") or {})
missing_values = sorted(declared - provided)
unknown_values = sorted(provided - declared)
if missing_values or unknown_values:
    details = []
    if missing_values:
        details.append("missing EA inputs: " + ", ".join(missing_values))
    if unknown_values:
        details.append("unknown EA inputs: " + ", ".join(unknown_values))
    sys.exit("; ".join(details))
changes, missing = [], []
for name, val in doc["ea_inputs"].items():
    m = re.search(rf"^(input\s+(\w+)\s+{name}\s*=\s*)([^;]+)(;)", t, re.M)
    if not m:
        missing.append(name)
        continue
    typ, old = m.group(2), m.group(3).strip()
    new = f'"{val}"' if typ == "string" else str(val).lower() if typ == "bool" else str(val)
    if old == new or (typ in ("double", "int") and num(old) is not None and num(old) == num(new)):
        continue
    t = t[:m.start(3)] + new + t[m.end(3):]
    changes.append((name, old, new))
if missing:
    sys.exit("could not map settings to EA inputs: " + ", ".join(missing))
if a.magic is not None:
    t, count = re.subn(r"^(input\s+int\s+InpMagicNumber\s*=\s*)\d+", rf"\g<1>{a.magic}", t, count=1, flags=re.M)
    if count != 1:
        sys.exit("could not find the InpMagicNumber input to update")
version_match = re.search(r'^#property version\s+"([^"]+)"', t, re.M)
if a.version:
    t, count = re.subn(r'^#property version\s+"[^"]+"', f'#property version   "{a.version}"', t, count=1, flags=re.M)
    if count != 1:
        sys.exit("could not find #property version to update")
    version = a.version
else:
    version = version_match.group(1) if version_match else None
if version:
    t = re.sub(r'^(#define EA_COMMENT "[^"]*?\bv)[\d.]+(")', rf'\g<1>{version}\2', t, count=1, flags=re.M)
res = doc.get("mt5_result") or {}
head = (f"// Defaults from {Path(a.json).name} ({doc.get('written_by')}, {doc.get('written_at')})"
        + (f" - MT5 {res.get('from')} - {res.get('to')} {res.get('delay')} delay: net {res.get('net')}, PF {res.get('profit_factor')}, "
           f"WR {res.get('win_rate')}%, {res.get('trades')} trades" if res else "") + "\n")
t = t.replace("#include <Trade/Trade.mqh>", head + "#include <Trade/Trade.mqh>", 1)
dst.write_text(t, encoding="utf-8")
print(f"written {dst}: {len(changes)} default(s) changed from {src.name}")
for n, o, v in changes:
    print(f"  {n}: {o} -> {v}")
for n in doc.get("chart_only") or []:
    print("  chart only (the EA has no such setting):", n)
if dst.resolve() == src.resolve():
    print("RELEASE: add the version's rows to VERSION.md and VERSION_HISTORY.md in the same commit, and compile it in the terminal.")
