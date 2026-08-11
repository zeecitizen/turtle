"""Dashboard server admin: kill, start, status."""

import sys
import time
import subprocess
import urllib.request

import psutil

SERVER_JS = r"C:\Users\zeesh\Documents\GitHub\turtle\dashboard\claude_trader\server.js"
SERVER_DIR = r"C:\Users\zeesh\Documents\GitHub\turtle\dashboard\claude_trader"
CREATE_NO_WINDOW = 0x08000000


def find_server():
    pids = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = p.info['cmdline'] or []
            if any('server.js' in str(x) and 'claude_trader' in str(x) for x in cl):
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def kill():
    killed = []
    for pid in find_server():
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            killed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed


def start():
    proc = subprocess.Popen(
        ['node', SERVER_JS],
        cwd=SERVER_DIR,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return proc.pid


def http_check():
    try:
        r = urllib.request.urlopen('http://localhost:3457/api/shano', timeout=8)
        body = r.read(40000)
        return r.status, len(body)
    except Exception as e:
        return None, str(e)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'restart':
        killed = kill()
        print(f"killed: {killed}")
        time.sleep(1)
        pid = start()
        print(f"started PID: {pid}")
        time.sleep(2)
        st, info = http_check()
        print(f"GET /api/shano -> {st} ({info} bytes)" if st else f"http error: {info}")
    elif cmd == 'kill':
        print(f"killed: {kill()}")
    elif cmd == 'start':
        print(f"started PID: {start()}")
    elif cmd == 'status':
        print(f"running PIDs: {find_server()}")
        st, info = http_check()
        print(f"GET /api/shano -> {st} ({info} bytes)" if st else f"http error: {info}")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
