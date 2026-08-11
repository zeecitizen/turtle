"""Re-remap remaining laptop paths in watchdog + keepalive scripts on VPS."""
from pathlib import Path

replacements = [
    (r"C:\Users\zeesh\Documents\GitHub\turtle", r"C:\turtle"),
    (r"C:/Users/zeesh/Documents/GitHub/turtle", "C:/turtle"),
    (r"C:\Users\zeesh\AppData\Roaming\MetaQuotes", r"C:\Users\Administrator\AppData\Roaming\MetaQuotes"),
    (r"C:/Users/zeesh/AppData/Roaming/MetaQuotes", "C:/Users/Administrator/AppData/Roaming/MetaQuotes"),
]

files = [
    Path(r"C:\turtle\monitor\ea_health_watchdog.py"),
    Path(r"C:\turtle\monitor\node_keepalive.py"),
]

for f in files:
    if not f.exists():
        print(f"SKIP {f} (missing)")
        continue
    c = f.read_text(encoding="utf-8")
    n0 = c.count("zeesh")
    for src, dst in replacements:
        c = c.replace(src, dst)
    f.write_text(c, encoding="utf-8")
    n1 = c.count("zeesh")
    print(f"{f.name}: zeesh refs {n0} -> {n1}")
print("done")
