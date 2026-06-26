"""Remap laptop paths to VPS paths in server.js (run on VPS)."""
import sys
from pathlib import Path

f = Path(r"C:\turtle\dashboard\claude_trader\server.js")
content = f.read_text(encoding="utf-8")
orig_len = len(content)
zeesh_count_before = content.count("zeesh")

replacements = [
    # Path style 1: escaped Windows backslashes (JS source)
    (r"C:\\Users\\zeesh\\Documents\\GitHub\\turtle\\", r"C:\\turtle\\"),
    (r"C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\", r"C:\\Users\\Administrator\\AppData\\Roaming\\MetaQuotes\\"),
    (r"C:\\Users\\zeesh\\AppData\\Local\\Programs\\Python\\Python313-arm64\\python.exe", "python"),

    # Path style 2: forward slashes
    ("C:/Users/zeesh/Documents/GitHub/turtle/", "C:/turtle/"),
    ("C:/Users/zeesh/AppData/Roaming/MetaQuotes/", "C:/Users/Administrator/AppData/Roaming/MetaQuotes/"),
    ("C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe", "python"),
]

for src, dst in replacements:
    n = content.count(src)
    if n:
        content = content.replace(src, dst)
        print(f"  replaced {n}x: {src[:60]}... -> {dst[:30]}")

f.write_text(content, encoding="utf-8")
zeesh_count_after = content.count("zeesh")
print(f"\nRemap done.")
print(f"  Original 'zeesh' refs: {zeesh_count_before}")
print(f"  Remaining 'zeesh' refs: {zeesh_count_after}")
print(f"  File length: {orig_len} -> {len(content)}")
