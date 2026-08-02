"""Quick daemon health check — counts python procs by script name."""
import psutil, os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

NEEDED = [
    "memory_hawk.py", "claude_brain.py", "brain_lock.py",
    "daily_report_hawk.py", "usb_hawk.py", "morning_brief_hawk.py",
    "_chat_monitor_oneline.py", "_atmos_dd_watch.py",
]

me = os.getpid()
hits = {n: [] for n in NEEDED}
for p in psutil.process_iter(["pid", "cmdline"]):
    if p.info["pid"] == me:
        continue
    try:
        cl = " ".join(p.info["cmdline"] or [])
        if "python" not in cl.lower():
            continue
        # Skip self + tmp inline-c scripts
        if "-c " in cl or " -c\n" in cl:
            continue
        for n in NEEDED:
            if n in cl:
                hits[n].append(p.info["pid"])
    except Exception:
        pass

for n, pids in hits.items():
    status = "OK  " if pids else "DOWN"
    print(f"  [{status}] {n:<32} PIDs: {pids}")
