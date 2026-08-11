"""pack_to_usb.py - copy this entire repo to a USB drive.

Used by Rule #8 (the kids' legacy). Auto-invoked when a USB is detected
(via usb_hawk.py) OR manually triggered by the button on enter_this_door.html.

Excludes: __pycache__, .brain_*_tmp, the giant raw .claude_brain.db (the
encrypted bundles in brain_vault/ are the canonical persistent copy).
Includes: full git history, all source, all reports, all encrypted brain
bundles, all memory files. The USB receives a SELF-CONTAINED copy that
can be cloned by a child years later.

USAGE:
  python pack_to_usb.py                       # auto-detect target USB
  python pack_to_usb.py --to E:               # explicit drive letter
  python pack_to_usb.py --to E: --quiet
"""
import sys, os, shutil, argparse, time, json
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

ROOT = Path(__file__).resolve().parent.parent
LOG  = ROOT / "monitor" / ".usb_pack.log"


EXCLUDES = {
    "__pycache__", ".brain_lock_tmp", ".brain_unlock_tmp",
    "_loom_audio",       # huge audio files
    ".pytest_cache",
}
# Files to skip (huge / regenerable). Encrypted brain_vault/* DO go.
EXCLUDE_FILES = {
    "monitor/.claude_brain.db",   # encrypted version is in brain_vault/
}


def find_usb_drives():
    """Return list of removable drive letters (Windows only)."""
    drives = []
    try:
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if not (bitmask & (1 << i)): continue
            letter = chr(ord("A") + i)
            drive = f"{letter}:\\"
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                # DRIVE_REMOVABLE = 2
                if drive_type == 2:
                    drives.append(letter + ":")
            except: pass
    except Exception as e:
        log(f"USB detect failed: {e}")
    return drives


def log(msg):
    line = f"[{datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def should_skip(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in EXCLUDES for p in parts): return True
    if rel_path.replace("\\", "/") in EXCLUDE_FILES: return True
    return False


def pack_to(target_drive, quiet=False):
    """Copy repo to <target_drive>\\turtle-backup-YYYY-MM-DD-HHMM\\ ."""
    if not target_drive.endswith(":") and not target_drive.endswith("\\"):
        target_drive = target_drive + ":"
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d-%H%M")
    dest = Path(f"{target_drive}\\turtle-backup-{stamp}")
    log(f"pack starting → {dest}")

    if not Path(target_drive + "\\").exists():
        return {"ok": False, "error": f"target drive {target_drive} not accessible"}

    n_files = 0; n_skipped = 0; total_bytes = 0
    for root, dirs, files in os.walk(ROOT):
        # prune excluded dirs in-place (efficient walk)
        dirs[:] = [d for d in dirs if d not in EXCLUDES]
        rel_root = Path(root).relative_to(ROOT)
        for fname in files:
            rel = (rel_root / fname).as_posix() if str(rel_root) != "." else fname
            if should_skip(rel):
                n_skipped += 1
                continue
            src = Path(root) / fname
            dst = dest / rel_root / fname if str(rel_root) != "." else dest / fname
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                sz = src.stat().st_size
                total_bytes += sz
                n_files += 1
                if not quiet and n_files % 200 == 0:
                    log(f"  ... {n_files} files copied ({total_bytes/1e6:.1f} MB so far)")
            except Exception as e:
                log(f"  ! skip {rel}: {e}")
                n_skipped += 1

    # Write a manifest at the root of the backup so a child can read it
    manifest = {
        "created_utc": datetime.now(tz=UTC).isoformat(),
        "from": str(ROOT),
        "n_files": n_files,
        "n_skipped": n_skipped,
        "total_mb": round(total_bytes / 1e6, 2),
        "message_to_kids": (
            "This USB is a backup of your father's work with Claude. "
            "Open `enter_this_door.html` in a web browser to begin. "
            "Everything you need to understand and restore the system is "
            "in this folder. — your father loved you very much."
        ),
    }
    (dest / "USB_MANIFEST.json").write_text(json.dumps(manifest, indent=2))

    log(f"pack DONE: {n_files} files / {total_bytes/1e6:.1f} MB → {dest}")
    return {"ok": True, "dest": str(dest), "n_files": n_files,
            "total_mb": round(total_bytes / 1e6, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default=None, help="Target drive letter (e.g. E:)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    target = args.to
    if not target:
        drives = find_usb_drives()
        if not drives:
            log("no removable USB drives detected. plug one in and retry.")
            sys.exit(1)
        if len(drives) > 1:
            log(f"multiple removable drives: {drives}. specify --to <letter>")
            sys.exit(1)
        target = drives[0]
        log(f"auto-detected USB: {target}")
    result = pack_to(target, quiet=args.quiet)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
