"""Restart sheriff_hawk so it picks up source changes."""
import subprocess, time
import psutil

PY = r'C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe'
SCRIPT = r'C:\Users\zeesh\Documents\GitHub\turtle\monitor\sheriff_hawk.py'

killed = []
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cl = p.info['cmdline'] or []
        if any('sheriff_hawk' in str(x) for x in cl):
            p.terminate()
            try: p.wait(timeout=3)
            except psutil.TimeoutExpired: p.kill()
            killed.append(p.info['pid'])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print(f"killed sheriff: {killed}")
time.sleep(1)

subprocess.Popen(
    [PY, SCRIPT, '--loop'],
    cwd=r'C:\Users\zeesh\Documents\GitHub\turtle\monitor',
    creationflags=0x08000000,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    close_fds=True,
)
time.sleep(2)

alive = []
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cl = p.info['cmdline'] or []
        if any('sheriff_hawk' in str(x) for x in cl):
            alive.append(p.info['pid'])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
print(f"sheriff alive: {alive}")
