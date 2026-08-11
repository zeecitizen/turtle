"""Read all 98 labels in full, group by distinct master rule, output structured findings."""
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/setup_labels/zee_labels.json")
data = json.loads(p.read_text(encoding="utf-8"))

# Sort by numeric key
def keynum(k):
    try: return int(k)
    except: return 9999

ordered = sorted(data.items(), key=lambda kv: keynum(kv[0]))

for k, v in ordered:
    text = (v.get("zee") if isinstance(v, dict) else "") or ""
    if not text.strip(): continue
    print(f"━━━━━━ #{k} ━━━━━━")
    print(text.strip())
    print()
