"""Apply a saved settings md (table rows `| ... | `var` | **value** |`) to the TradingView Saad indicator, by variable name.
Snapshot first; values are typed after the chart's current value (bool / number / text); every value is read back.
    py pine_apply_md.py <settings.md>"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402

md = Path(sys.argv[1])
want = dict(re.findall(r"\|\s*`(\w+)`\s*\|\s*\*\*(.*?)\*\*\s*\|", md.read_text(encoding="utf-8")))
st = server.tv_eval(server.JS_STUDY)
names = server.pine_inputs()
assert "error" not in st and st["symbol"].startswith("BLUEBERRY"), st
assert len(names) == len(st["values"]), (len(names), len(st["values"]))
cur = dict(zip(names, st["values"]))
snap = Path(__file__).resolve().parent.parent / f"saad_snapshot_{time.strftime('%Y-%m-%d_%H%M')}_before_{md.stem.replace('%', '')}.json"
json.dump({"symbol": st["symbol"], "res": st["res"], "values": st["values"], "by_name": cur}, open(snap, "w"), indent=1)
print("snapshot", snap, "|", st["symbol"], st["res"], "min |", len(want), "settings in the file")


def typed(s, like):
    if isinstance(like, bool):
        return s.strip().lower() == "true"
    if isinstance(like, (int, float)):
        v = float(s)
        return int(v) if v.is_integer() and isinstance(like, int) else v
    return s


missing = [k for k in want if k not in cur]
changed = []
for k, s in want.items():
    if k not in cur:
        continue
    v = typed(s, cur[k])
    if cur[k] != v:
        server.set_input(st["id"], names.index(k), v)
        changed.append((k, cur[k], v))
time.sleep(5)
now = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
bad = [(k, now[k], typed(s, cur[k])) for k, s in want.items() if k in now and now[k] != typed(s, cur[k])]
not_in_file = [k for k in names if k not in want]
for k, a, b in changed:
    print(f"  {k}: {a} -> {b}")
print(f"changed {len(changed)} | not on the chart: {missing} | chart settings not in the file (left as they are): "
      f"{[(k, now[k]) for k in not_in_file]} | mismatches after read-back: {bad}")
