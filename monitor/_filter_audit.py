"""Today's filter funnel analysis: count every SKIP MAIN + reasons + main attempts."""
import re
from collections import Counter
from pathlib import Path
from datetime import datetime

LOG = Path(rf"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\{datetime.now().strftime('%Y%m%d')}.log")
raw = LOG.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="ignore")

skip_lines = []
main_opens = 0
probe_confirms = 0
filter_reasons = Counter()
filter_examples = {}

for line in raw.splitlines():
    if "ShanoEA: SKIP MAIN" in line:
        skip_lines.append(line)
        # Extract filter reason
        m = re.search(r"SKIP MAIN.+?(?:filter|gate|exit)\s*\(([^)]+)\)", line)
        if m:
            cat_match = re.search(r"SKIP MAIN .+?(\w+(?:\s+\w+)?)\s+filter", line)
            if cat_match:
                cat = cat_match.group(1).strip().lower()
                filter_reasons[cat] += 1
                if cat not in filter_examples:
                    filter_examples[cat] = m.group(1)[:120]
        else:
            # Catch-all for non-filter skips (max positions, etc.)
            short = re.search(r"SKIP MAIN.+?(?:—|-)\s*(.+?)(?:\(|$)", line)
            if short:
                filter_reasons[short.group(1).strip().lower()[:50]] += 1
    elif "ShanoEA: MAIN OPENED" in line:
        main_opens += 1
    elif "ShanoEA: PROBE CONFIRMED" in line and "ticket=" in line:
        probe_confirms += 1
    elif "Cannot open main" in line:
        filter_reasons["max positions reached"] += 1

print(f"=== TODAY's MAIN-fire funnel ({datetime.now().strftime('%Y-%m-%d')}) ===")
print(f"Probe confirms (raw):     {probe_confirms} (with new $0.75 threshold)")
print(f"Mains opened:             {main_opens}")
print(f"SKIP MAIN events:         {len(skip_lines)}")
print()
print("=== Block reasons (count) ===")
for reason, count in filter_reasons.most_common():
    ex = filter_examples.get(reason, "")
    print(f"  {count:>4}  {reason}")
    if ex:
        print(f"        e.g. {ex}")

# Sample latest skips (full lines)
print()
print("=== Last 6 SKIP MAIN events (full lines) ===")
for line in skip_lines[-6:]:
    # Extract just the timestamp + ShanoEA part
    m = re.search(r"(\d{2}:\d{2}:\d{2}).*?ShanoEA:\s+(.+)$", line)
    if m:
        print(f"  {m.group(1)}  {m.group(2)[:200]}")
