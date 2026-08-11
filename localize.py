"""localize.py — rewrite absolute paths for the machine the software just landed on.

Zee, 2026-08-11: "will the setup when run, work and install the software as expected?"

Not without this. The bundle installed cleanly and reported success, and then 7 of the 8
scripts that must run would have failed silently — because 119 python files carry
C:/Users/zeesh baked into them, and a new computer has C:/Users/<somebody else>. The
installer would have looked perfect and delivered nothing, which is the worst kind of
failure: one that announces itself as a success.

WHAT THIS REWRITES, and to what
    C:/Users/zeesh/AppData/Roaming/MetaQuotes   ->  this user's own %APPDATA%/MetaQuotes
    C:/Users/zeesh/Documents/GitHub/turtle      ->  wherever the code was just installed
    C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe
                                                ->  the python that shipped in the bundle
    C:/Users/zeesh                              ->  this user's profile folder (last resort)

Both slash styles are handled, because the repo uses forward slashes in raw strings and
backslashes in .bat files, often in the same directory.

It is safe to run twice: paths already pointing at this machine simply do not match.

    py localize.py                 # rewrite in place, reporting what changed
    py localize.py --check         # report only, change nothing
"""
import argparse
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OLD_USER = "C:/Users/zeesh"
EXTS = {".py", ".bat", ".json", ".js", ".md", ".txt", ".ps1", ".mq5"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", "_tester_runs"}


def variants(p: str) -> list[str]:
    """The same path as the repo actually writes it: forward, back, and escaped-back."""
    fwd = p.replace("\\", "/")
    back = fwd.replace("/", "\\")
    return [fwd, back, back.replace("\\", "\\\\")]


def build_map(root: Path) -> list[tuple[str, str]]:
    home = str(Path.home()).replace("\\", "/")
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")).replace("\\", "/")
    py = (root / "python" / "python.exe")
    if not py.exists():                       # running from the repo, not an install
        py = Path(sys.executable)
    pairs = [
        (f"{OLD_USER}/AppData/Roaming/MetaQuotes", f"{appdata}/MetaQuotes"),
        (f"{OLD_USER}/Documents/GitHub/turtle", str(root / "turtle").replace("\\", "/")),
        (f"{OLD_USER}/AppData/Local/Programs/Python/Python313-arm64/python.exe",
         str(py).replace("\\", "/")),
        (f"{OLD_USER}/AppData/Local/Programs/Python/Python313-arm64/pythonw.exe",
         str(py.with_name("pythonw.exe")).replace("\\", "/")),
        (OLD_USER, home),                      # last, so the specific ones win first
    ]
    out = []
    for old, new in pairs:
        for a, b in zip(variants(old), variants(new)):
            out.append((a, b))
    return out


def run(root: Path, check_only: bool = False) -> int:
    mapping = build_map(root)
    target = root / "turtle" if (root / "turtle").exists() else root
    print(f"  localising {target}")
    print(f"     user folder -> {Path.home()}")
    print(f"     MetaQuotes  -> {os.environ.get('APPDATA')}\\MetaQuotes\n")
    changed = files = 0
    for f in target.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in EXTS:
            continue
        if any(part in SKIP_DIRS for part in f.relative_to(target).parts):
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        orig, hits = t, 0
        for old, new in mapping:
            if old and old in t:
                hits += t.count(old)
                t = t.replace(old, new)
        if hits and t != orig:
            files += 1
            changed += hits
            if not check_only:
                try:
                    f.write_text(t, encoding="utf-8")
                except Exception as e:
                    print(f"     could not write {f.name}: {e}")
    verb = "would change" if check_only else "changed"
    print(f"  {verb} {changed:,} path(s) across {files:,} file(s)")
    return files


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="the install folder (contains turtle/ and python/)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    run(Path(a.root).resolve(), a.check)
