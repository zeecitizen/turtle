"""Kill duplicates of any monitored daemon. Keeps the OLDEST instance per script."""
import psutil
import subprocess
import time
from collections import defaultdict

DAEMONS = ["shano_hawk", "sheriff_hawk", "silver_hawk", "vscode_watchdog",
           "sexy_hawk", "meeting_hawks", "patriarch", "intern_hawks",
           "forward_tester"]

# Group instances per daemon
groups = defaultdict(list)
for p in psutil.process_iter(['pid', 'cmdline', 'create_time']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        for d in DAEMONS:
            if d in cmd and 'ensure_daemon' not in cmd and '_kill_' not in cmd:
                groups[d].append((p.info['create_time'], p.info['pid']))
    except Exception:
        pass

# For each daemon: keep oldest, kill rest
killed = 0
for d, instances in groups.items():
    instances.sort()
    if len(instances) <= 1:
        print(f"  {d}: {len(instances)} (no action)")
        continue
    keep_pid = instances[0][1]
    print(f"  {d}: {len(instances)} instances - keeping pid {keep_pid}")
    for ct, pid in instances[1:]:
        r = subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                           capture_output=True, text=True)
        status = 'killed' if r.returncode == 0 else f'failed rc={r.returncode}'
        print(f"    pid {pid}: {status}")
        if r.returncode == 0:
            killed += 1

time.sleep(2)

# Verify
print()
print("After cleanup:")
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        for d in DAEMONS:
            if d in cmd and 'ensure_daemon' not in cmd and '_kill_' not in cmd:
                pass  # would print but skip noise
    except Exception:
        pass

remaining = defaultdict(int)
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        for d in DAEMONS:
            if d in cmd and 'ensure_daemon' not in cmd and '_kill_' not in cmd:
                remaining[d] += 1
    except Exception:
        pass
for d, c in remaining.items():
    print(f"  {d}: {c}")
print(f"\nTotal killed: {killed}")
