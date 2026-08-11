"""Force-kill all shano_hawk + start exactly one. Reports parent PIDs."""
import subprocess, time, psutil

PY = r'C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe'
SCRIPT = r'C:\Users\zeesh\Documents\GitHub\turtle\monitor\shano_hawk.py'

def list_hawks():
    out = []
    for p in psutil.process_iter(['pid','ppid','create_time','cmdline']):
        try:
            cl = p.info['cmdline'] or []
            if any('shano_hawk' in str(x) for x in cl):
                out.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out

before = list_hawks()
print(f"Before: {len(before)} hawks")
for h in before:
    try:
        parent = psutil.Process(h['ppid']).name()
    except: parent = '?'
    print(f"  PID {h['pid']} parent={h['ppid']} ({parent})")

for h in before:
    try:
        p = psutil.Process(h['pid'])
        p.terminate()
        try: p.wait(timeout=3)
        except psutil.TimeoutExpired: p.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

time.sleep(2)
mid = list_hawks()
print(f"After kill: {len(mid)} hawks")

subprocess.Popen([PY, SCRIPT],
    cwd=r'C:\Users\zeesh\Documents\GitHub\turtle\monitor',
    creationflags=0x08000000,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    close_fds=True)
time.sleep(3)

after = list_hawks()
print(f"After start: {len(after)} hawks")
for h in after:
    try: parent = psutil.Process(h['ppid']).name()
    except: parent = '?'
    print(f"  PID {h['pid']} parent={h['ppid']} ({parent})")
