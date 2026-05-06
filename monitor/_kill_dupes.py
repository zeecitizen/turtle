"""One-shot cleanup: keep oldest vscode_watchdog, kill duplicates."""
import psutil
import subprocess
import time

wds = []
for p in psutil.process_iter(['pid', 'cmdline', 'create_time']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'vscode_watchdog' in cmd:
            wds.append((p.info['create_time'], p.info['pid']))
    except Exception:
        pass

wds.sort()
print(f"Found {len(wds)} watchdog(s): {[p for _, p in wds]}")

if len(wds) <= 1:
    print("No duplicates to clean")
else:
    keep = wds[0][1]
    print(f"Keeping pid {keep} (oldest)")
    for _, pid in wds[1:]:
        r = subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                           capture_output=True, text=True)
        print(f"  kill {pid}: rc={r.returncode} | {r.stdout.strip()}{r.stderr.strip()}")

time.sleep(2)
remaining = [p.info['pid'] for p in psutil.process_iter(['pid', 'cmdline'])
             if 'vscode_watchdog' in ' '.join(p.info['cmdline'] or [])]
print(f"After: {len(remaining)} watchdog(s) — pids {remaining}")
