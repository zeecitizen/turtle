"""
ensure_daemon.py — idempotent, resilient launcher for long-running Python daemons.

Modes:
  python ensure_daemon.py <script.py> [args...]
      Ensure the daemon is running. Skip if already up; spawn detached if not.
      Always exits 0 (callers should never crash on its failure).

  python ensure_daemon.py --check <script.py>
      Exit 0 if a Python process running <script.py> is found.
      Exit 1 otherwise.

Detection is by Python interpreter + script-basename match in cmdline.
Spawned children get DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP so they
survive parent exit and have no console window.
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MON = ROOT / "monitor"
PY = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"


def _lockfile_path(script_name: str) -> Path:
    """Per-script lockfile: monitor/.<script>.lock holding the daemon's PID."""
    return MON / f".{Path(script_name).stem}.lock"


def _read_lockfile_pid(script_name: str):
    f = _lockfile_path(script_name)
    if not f.exists():
        return None
    try:
        return int(f.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_lockfile(script_name: str, pid: int) -> None:
    try:
        _lockfile_path(script_name).write_text(str(pid))
    except OSError:
        pass


def _pid_is_alive(pid: int, script_name: str) -> bool:
    """Verify pid is alive AND its cmdline references our script (not a recycled pid)."""
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        p = psutil.Process(pid)
        cmd = " ".join(p.cmdline() or []).lower()
        return script_name.lower() in cmd
    except Exception:
        return False


def find_running_pid(script_name: str):
    # Lockfile fast-path: if a fresh PID is recorded for this script and it's alive, use it.
    # Atomic spawn-then-record means concurrent ensure_daemon calls can't both spawn.
    locked = _read_lockfile_pid(script_name)
    if locked and _pid_is_alive(locked, script_name):
        return locked

    try:
        import psutil
    except ImportError:
        print(f"  [WARN] psutil not installed - cannot detect existing {script_name}; will spawn unconditionally")
        return None

    me = os.getpid()
    parent = os.getppid() if hasattr(os, "getppid") else None
    target = script_name.lower()

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pid = proc.info["pid"]
            if pid == me or pid == parent:
                continue
            cmd = proc.info.get("cmdline") or []
            cmdstr = " ".join(str(c) for c in cmd).lower()
            if "ensure_daemon" in cmdstr:
                continue
            pname = (proc.info.get("name") or "").lower()
            if "python" not in pname:
                continue
            if target in cmdstr:
                # Heal lockfile so future calls hit the fast-path.
                _write_lockfile(script_name, pid)
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    return None


def spawn_detached(script_path: Path, extra_args):
    # CREATE_NO_WINDOW gives the child a hidden console — its own children
    # (subprocess.run calls inside the daemon) inherit the hidden console
    # instead of being given a fresh visible one. CREATE_NEW_PROCESS_GROUP
    # lets the daemon survive parent (this script) exiting.
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

    log_path = MON / f".{script_path.stem}_stdout.log"
    try:
        log = open(log_path, "ab", buffering=0)
        log.write(b"\n=== ensure_daemon spawn ===\n")
    except OSError:
        log = subprocess.DEVNULL

    proc = subprocess.Popen(
        [PY, str(script_path), *extra_args],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
        cwd=str(MON),
    )
    return proc.pid


def main():
    args = sys.argv[1:]
    if not args:
        print("  [WARN] ensure_daemon: no script specified")
        return 0

    check_only = False
    if args[0] == "--check":
        check_only = True
        args = args[1:]
        if not args:
            print("  [WARN] ensure_daemon --check: no script specified")
            return 1

    script_name = args[0]
    extra_args = args[1:]
    script_path = MON / script_name
    label = script_path.stem

    if not script_path.exists():
        if check_only:
            return 1
        print(f"  [SKIP] {label}: script not found at {script_path}")
        return 0

    try:
        pid = find_running_pid(script_name)
    except Exception as e:
        if check_only:
            return 1
        print(f"  [WARN] {label}: process scan failed ({e}); attempting spawn")
        pid = None

    if check_only:
        return 0 if pid else 1

    if pid:
        print(f"  [OK] {label} already running (pid {pid})")
        return 0

    if not Path(PY).exists():
        print(f"  [WARN] {label}: python interpreter not found at {PY}")
        return 0

    try:
        new_pid = spawn_detached(script_path, extra_args)
        _write_lockfile(script_name, new_pid)
        suffix = f" {' '.join(extra_args)}" if extra_args else ""
        print(f"  [OK] {label}{suffix} launched (pid {new_pid})")
    except PermissionError as e:
        print(f"  [WARN] {label}: permission denied - {e}")
    except FileNotFoundError as e:
        print(f"  [WARN] {label}: file missing - {e}")
    except Exception as e:
        print(f"  [WARN] {label}: spawn failed - {e}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"  [WARN] ensure_daemon: unhandled error - {e}")
        sys.exit(0)
