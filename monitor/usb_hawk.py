"""usb_hawk.py - watch for USB inserts and auto-pack the repo to them.

Polls every 10s. When a NEW removable drive appears (one not seen before),
runs pack_to_usb.py against it automatically. Zee plugs the USB, walks away,
returns to find a fresh full backup on the stick.

State is tracked in monitor/.usb_hawk_seen.json so the same drive doesn't
re-pack on every poll.
"""
import sys, time, json, subprocess, argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

ROOT = Path(__file__).resolve().parent.parent
SEEN_FILE = ROOT / "monitor" / ".usb_hawk_seen.json"
LOG_FILE  = ROOT / "monitor" / ".usb_hawk.log"
PY = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"


def log(msg):
    line = f"[{datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_usb_drives():
    """Drive letter + volume serial (so same physical USB isn't re-packed)."""
    drives = []
    try:
        import ctypes
        from ctypes import wintypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if not (bitmask & (1 << i)): continue
            letter = chr(ord("A") + i) + ":"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(letter + "\\") != 2:
                    continue
                serial = wintypes.DWORD()
                if ctypes.windll.kernel32.GetVolumeInformationW(
                    letter + "\\", None, 0, ctypes.byref(serial),
                    None, None, None, 0):
                    drives.append({"letter": letter, "serial": serial.value})
            except: pass
    except Exception as e:
        log(f"usb scan err: {e}")
    return drives


def load_seen():
    if SEEN_FILE.exists():
        try: return set(json.loads(SEEN_FILE.read_text()))
        except: pass
    return set()


def save_seen(s):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(list(s), indent=2))


def loop(interval_sec=10):
    log("usb_hawk starting — polling for new USB drives")
    seen = load_seen()
    while True:
        try:
            drives = find_usb_drives()
            for d in drives:
                key = f"{d['letter']}:{d['serial']}"
                if key in seen: continue
                log(f"new USB detected: {d['letter']} (serial 0x{d['serial']:08X}) — packing")
                # Run pack_to_usb.py with explicit --to
                try:
                    res = subprocess.run(
                        [PY, str(ROOT / "monitor" / "pack_to_usb.py"),
                         "--to", d['letter'], "--quiet"],
                        capture_output=True, text=True, timeout=1800)
                    if res.returncode == 0:
                        log(f"pack OK for {d['letter']}: {res.stdout.strip().splitlines()[-1] if res.stdout else ''}")
                        seen.add(key); save_seen(seen)
                    else:
                        log(f"pack FAILED for {d['letter']}: {res.stderr}")
                except subprocess.TimeoutExpired:
                    log(f"pack TIMEOUT for {d['letter']} (>30 min)")
                except Exception as e:
                    log(f"pack crashed for {d['letter']}: {e}")
        except Exception as e:
            log(f"loop err: {e}")
        time.sleep(interval_sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--clear-seen", action="store_true",
                    help="Forget all previously-seen drives (will re-pack on next detect)")
    args = ap.parse_args()
    if args.clear_seen:
        save_seen(set()); print("cleared"); return
    loop(args.interval)


if __name__ == "__main__":
    main()
