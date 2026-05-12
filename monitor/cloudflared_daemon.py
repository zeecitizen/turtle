"""cloudflared_daemon.py — keeps a public tunnel to localhost:3457 alive.

Pattern matches the rest of the hawk daemons (auto_uhv_trader, sniper, etc.):
  - PID lockfile: only one instance
  - heartbeat JSON every loop
  - log file we can tail
  - WhatsApp Zee whenever the public URL changes (quick tunnels rotate)
  - posts the URL to /me chat too so it shows up in his pinned page

Spawns:
    cloudflared.exe tunnel --url http://localhost:3457

Captures the printed URL (`https://<random>.trycloudflare.com`), writes it
to `cloudflared_url.txt`, then sits and tails the process. If cloudflared
dies, sleeps 5s and respawns. URL change → notify.

Sheriff Hawk will see this via the heartbeat freshness, same as other hawks.
"""
import json, os, re, signal, subprocess, sys, threading, time, urllib.request, base64
from datetime import datetime, timezone
from pathlib import Path

HERE          = Path(__file__).parent
ROOT          = HERE.parent
PID_FILE      = HERE / "cloudflared_daemon.pid"
URL_FILE      = HERE / "cloudflared_url.txt"
HEARTBEAT     = HERE / "cloudflared_heartbeat.json"
LOG_FILE      = HERE / "cloudflared_daemon.log"
WHATSAPP_CFG  = HERE / ".whatsapp_config.json"
DASHBOARD_PW  = HERE / ".dashboard_password"
CC_CHAT_FILE  = HERE / "cc_chat.jsonl"
CHAT_STATE    = HERE / ".cloudflared_chat_watchdog.json"  # tracks last-nudge to avoid spam

CLOUDFLARED   = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
LOCAL_TARGET  = "http://localhost:3457"
ZEE_CHAT_ID   = "4915119175329@c.us"
CHROME_PATHS  = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\zeesh\AppData\Local\Google\Chrome\Application\chrome.exe",
]

# Named-tunnel mode: stable URL via Cloudflare DNS. Set up 2026-05-10.
# Domain: claudezeeshan.com (Zee's). Tunnel name: zee-claude.
# To revert to quick-tunnel mode (random URL), set NAMED_TUNNEL = "" below.
NAMED_TUNNEL = "zee-claude"
NAMED_URL    = "https://me.claudezeeshan.com"

URL_RE = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
RESTART_BACKOFF_SEC = 5
HEARTBEAT_INTERVAL_SEC = 15
HEALTH_PROBE_INTERVAL_SEC = 60       # poll the public URL once a minute
HEALTH_FAIL_LIMIT = 3                # consecutive failed probes before forced restart

# Chat-staleness watchdog: if Zee's most-recent /me message is older than this
# without a claude_code reply, WhatsApp him a nudge to ping again in the terminal.
# This is the OUT-OF-BAND safety net that survives Claude session death.
CHAT_STALENESS_THRESHOLD_SEC = 300   # 5 minutes
CHAT_NUDGE_COOLDOWN_SEC      = 1800  # don't nudge more than once per 30 min for the same stale msg

# Cloudflare WAF blocks default Python-urllib UA on the named tunnel — use a browser-like UA
# for any outbound requests that traverse the tunnel back to us.
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# Shared state mutated by stdout-reader thread, watched by main loop
_state = {
    "url": "",
    "stdout_eof": False,
    "last_line_ts": 0.0,
}
_state_lock = threading.Lock()


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_heartbeat(state: str, url: str, extra: dict | None = None) -> None:
    body = {
        "state": state,
        "url": url,
        "t": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    }
    if extra:
        body.update(extra)
    try:
        HEARTBEAT.write_text(json.dumps(body, indent=2), encoding="utf-8")
    except Exception:
        pass


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_pid_lock() -> None:
    if PID_FILE.exists():
        try:
            other = int(PID_FILE.read_text().strip() or "0")
            if pid_alive(other):
                log(f"another instance running pid={other} — exiting")
                sys.exit(0)
        except ValueError:
            pass
    PID_FILE.write_text(str(os.getpid()))


def release_pid_lock() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def whatsapp_url(url: str, is_change: bool) -> None:
    if not WHATSAPP_CFG.exists():
        return
    try:
        cfg = json.loads(WHATSAPP_CFG.read_text(encoding="utf-8"))
        host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]
    except Exception as e:
        log(f"whatsapp config error: {e}")
        return
    prefix = "🔄 New" if is_change else "🟢"
    msg = (
        f"{prefix} /me tunnel URL:\n"
        f"{url}/me\n\n"
        f"Username: zee\nPassword: 28973\n\n"
        f"Bookmark this — quick tunnels rotate when daemon restarts. "
        f"Daemon auto-WhatsApps you the new URL each time."
    )
    api = f"{host}/waInstance{iid}/sendMessage/{tok}"
    body = json.dumps({"chatId": ZEE_CHAT_ID, "message": msg}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(api, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            log(f"whatsapp sent: {r.read().decode('utf-8')[:80]}")
    except Exception as e:
        log(f"whatsapp send error: {e}")


def post_to_me_chat(url: str, is_change: bool) -> None:
    """Drop a message into the /me chat itself so it shows when Zee opens the page."""
    if not DASHBOARD_PW.exists():
        return
    try:
        pw = DASHBOARD_PW.read_text(encoding="utf-8").strip()
    except Exception:
        return
    auth = base64.b64encode(f"zee:{pw}".encode("utf-8")).decode("ascii")
    api = f"{url}/api/cc-chat/send"
    text = (
        f"🔄 Tunnel rotated — new URL:\n{url}/me"
        if is_change else
        f"🟢 Tunnel daemon up — public URL active:\n{url}/me"
    )
    body = json.dumps({"text": text, "from": "claude_code"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api, data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Basic {auth}",
            "User-Agent": BROWSER_UA,
        },
    )
    # DNS for fresh trycloudflare.com hostnames takes 5-10s to propagate.
    # Retry the post-to-me 3 times with backoff so first-launch lands cleanly.
    last_err = None
    for attempt, wait in enumerate([8, 6, 6], start=1):
        time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                log(f"posted to /me (attempt {attempt}): {r.read().decode('utf-8')[:80]}")
                return
        except Exception as e:
            last_err = e
            log(f"post-to-me attempt {attempt} failed: {e}")
    log(f"post-to-me gave up after 3 attempts: {last_err}")


def chat_watchdog_check() -> None:
    """OOB safety net: if Zee's last /me message is unanswered for >5 min,
    WhatsApp him a nudge. Survives Claude session death (this daemon is independent).
    Tracks last nudge timestamp in .cloudflared_chat_watchdog.json to avoid spam.

    Algorithm:
      1. Tail cc_chat.jsonl, find latest 'from: zee' entry and latest 'from: claude_code' entry
      2. If latest is from zee AND > threshold age AND no claude reply since AND we haven't
         already nudged for this exact message → WhatsApp Zee
    """
    if not CC_CHAT_FILE.exists():
        return
    try:
        # Read last 30 lines (more than enough to find latest of each role)
        with open(CC_CHAT_FILE, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            f.seek(max(0, file_size - 8192), 0)
            tail = f.read().decode("utf-8", errors="ignore").splitlines()
        last_zee = None
        last_claude_ts = 0
        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except Exception:
                continue
            if m.get("from") == "zee":
                last_zee = m
            elif m.get("from") == "claude_code":
                last_claude_ts = max(last_claude_ts, int(m.get("ts", 0)))
        if not last_zee:
            return
        zee_ts = int(last_zee.get("ts", 0))
        # Already replied to?
        if last_claude_ts > zee_ts:
            return
        age_sec = (time.time() * 1000 - zee_ts) / 1000.0
        if age_sec < CHAT_STALENESS_THRESHOLD_SEC:
            return
        # Nudge cooldown — same zee message shouldn't trigger > 1 nudge per cooldown window
        last_nudge_ts = 0
        last_nudge_for_msg_ts = 0
        if CHAT_STATE.exists():
            try:
                st = json.loads(CHAT_STATE.read_text(encoding="utf-8"))
                last_nudge_ts = int(st.get("last_nudge_ts_ms", 0))
                last_nudge_for_msg_ts = int(st.get("nudged_for_zee_msg_ts_ms", 0))
            except Exception:
                pass
        # Already nudged for THIS exact message? Skip until cooldown expires.
        if last_nudge_for_msg_ts == zee_ts:
            since_nudge = (time.time() * 1000 - last_nudge_ts) / 1000.0
            if since_nudge < CHAT_NUDGE_COOLDOWN_SEC:
                return
        # Send WhatsApp nudge
        if not WHATSAPP_CFG.exists():
            return
        try:
            cfg = json.loads(WHATSAPP_CFG.read_text(encoding="utf-8"))
            host = cfg["api_host"]; iid = cfg["instance_id"]; tok = cfg["api_token"]
        except Exception as e:
            log(f"watchdog whatsapp config error: {e}")
            return
        zee_text_preview = (last_zee.get("text") or "")[:90]
        msg = (
            f"⚠️ Claude hasn't replied to your /me chat in {int(age_sec/60)} min.\n\n"
            f"Your last msg: \"{zee_text_preview}\"\n\n"
            f"Possible reasons: Claude session ended, monitor task expired, or Claude is busy.\n"
            f"Fix: ping Claude in the terminal — say \"check /me chat\" — Claude will read all "
            f"missed messages and reply.\n\n"
            f"https://me.claudezeeshan.com/me"
        )
        api = f"{host}/waInstance{iid}/sendMessage/{tok}"
        body = json.dumps({"chatId": ZEE_CHAT_ID, "message": msg}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(api, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                log(f"watchdog nudge sent (msg age {int(age_sec/60)}m): {r.read().decode('utf-8')[:80]}")
            CHAT_STATE.write_text(json.dumps({
                "last_nudge_ts_ms": int(time.time() * 1000),
                "nudged_for_zee_msg_ts_ms": zee_ts,
                "stale_msg_preview": zee_text_preview,
            }), encoding="utf-8")
        except Exception as e:
            log(f"watchdog whatsapp send error: {e}")
    except Exception as e:
        log(f"chat_watchdog_check exception: {e}")


def open_in_default_browser(url: str) -> None:
    """Open the URL in Chrome (Zee's preference). Falls back to system default if
    chrome.exe missing. Waits a few seconds for DNS to propagate before opening
    so Chrome doesn't show DNS_PROBE_FINISHED_NXDOMAIN."""
    chrome = next((p for p in CHROME_PATHS if Path(p).exists()), None)
    # Wait for DNS — fresh trycloudflare hostnames take 5-10s
    time.sleep(10)
    try:
        if chrome:
            subprocess.Popen([chrome, "--new-tab", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            log(f"opened in Chrome: {url}")
        else:
            os.startfile(url)
            log(f"opened via shell (chrome not found): {url}")
    except Exception as e:
        log(f"browser-open failed: {e}")


def previous_url() -> str:
    try:
        return URL_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def save_url(url: str) -> None:
    try:
        URL_FILE.write_text(url, encoding="utf-8")
    except Exception:
        pass


def stdout_reader_thread(proc, last_url_box, on_new_url):
    """Reads cloudflared stdout in a dedicated thread so the main loop is free
    to update heartbeat + probe URL health on its own schedule."""
    url_for_this_session = ""
    try:
        for line in proc.stdout:
            line = line.rstrip()
            with _state_lock:
                _state["last_line_ts"] = time.time()
            if not url_for_this_session:
                m = URL_RE.search(line)
                if m:
                    url_for_this_session = m.group(0)
                    with _state_lock:
                        _state["url"] = url_for_this_session
                    on_new_url(url_for_this_session, last_url_box[0])
                    last_url_box[0] = url_for_this_session
    except Exception as e:
        log(f"stdout reader exception: {e}")
    finally:
        with _state_lock:
            _state["stdout_eof"] = True


def probe_url_alive(url: str) -> bool:
    """Quick HEAD-style health check on the public URL. Returns True on 2xx/3xx/401
    (401 = gate works = tunnel works), False on DNS/network/5xx errors."""
    if not url:
        return False
    req = urllib.request.Request(url + "/api/state", method="GET",
                                 headers={"User-Agent": BROWSER_UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        # 401/403 = tunnel reachable, gate working — that's healthy
        return e.code < 500
    except Exception:
        return False


def main() -> None:
    if not Path(CLOUDFLARED).exists():
        log(f"FATAL: cloudflared not found at {CLOUDFLARED}")
        write_heartbeat("missing_binary", "")
        sys.exit(1)

    acquire_pid_lock()
    log(f"daemon starting pid={os.getpid()} target={LOCAL_TARGET}")
    write_heartbeat("starting", "")

    last_url = previous_url()
    last_url_box = [last_url]   # mutable box so thread can update
    consecutive_spawn_failures = 0
    proc = None

    def on_new_url(new_url: str, prev: str) -> None:
        is_change = (new_url != prev)
        log(f"URL detected: {new_url} (changed={is_change})")
        save_url(new_url)
        whatsapp_url(new_url, is_change)
        post_to_me_chat(new_url, is_change)
        open_in_default_browser(new_url + "/me")

    try:
        while True:
            # Reset shared state for this cloudflared lifecycle
            with _state_lock:
                _state["url"] = ""
                _state["stdout_eof"] = False
                _state["last_line_ts"] = time.time()

            mode = "named" if NAMED_TUNNEL else "quick"
            log(f"spawning cloudflared ({mode} mode)")
            try:
                if NAMED_TUNNEL:
                    args = [CLOUDFLARED, "tunnel", "--no-autoupdate", "run", NAMED_TUNNEL]
                else:
                    args = [CLOUDFLARED, "tunnel", "--url", LOCAL_TARGET, "--no-autoupdate"]
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as e:
                log(f"spawn failed: {e}")
                consecutive_spawn_failures += 1
                write_heartbeat("spawn_error", last_url, {"error": str(e), "fails": consecutive_spawn_failures})
                if consecutive_spawn_failures >= 5:
                    log("5 consecutive spawn failures — giving up")
                    sys.exit(2)
                time.sleep(RESTART_BACKOFF_SEC)
                continue

            consecutive_spawn_failures = 0

            # Named-tunnel mode: URL is fixed, seed it immediately. Quick mode: wait for stdout.
            if NAMED_TUNNEL:
                with _state_lock:
                    _state["url"] = NAMED_URL
                # First-launch announcement (skip if URL identical to last run = silent restart)
                if NAMED_URL != last_url_box[0]:
                    on_new_url(NAMED_URL, last_url_box[0])
                    last_url_box[0] = NAMED_URL
                else:
                    log(f"named tunnel back up — URL unchanged, no notify spam")

            # Start dedicated stdout reader thread — doesn't block heartbeat
            reader = threading.Thread(
                target=stdout_reader_thread,
                args=(proc, last_url_box, on_new_url),
                daemon=True,
            )
            reader.start()

            write_heartbeat("running", last_url_box[0], {"child_pid": proc.pid, "mode": mode})
            last_health_probe = 0.0
            health_fail_count = 0
            need_restart = False

            # Main supervisor loop — runs INDEPENDENTLY of stdout reads.
            # Heartbeat refreshes every loop. URL health probed every minute.
            while True:
                time.sleep(HEARTBEAT_INTERVAL_SEC)

                # Did cloudflared process exit?
                rc = proc.poll()
                if rc is not None:
                    log(f"cloudflared exited code={rc}")
                    write_heartbeat("respawning", last_url_box[0], {"last_exit_code": rc})
                    need_restart = True
                    break

                # Heartbeat refresh
                with _state_lock:
                    cur_url = _state["url"] or last_url_box[0]
                write_heartbeat("running", cur_url, {
                    "child_pid": proc.pid,
                    "health_fails": health_fail_count,
                })

                # Out-of-band chat watchdog — independent of Monitor task in Claude session
                chat_watchdog_check()

                # Periodic URL health probe — catches "process alive but tunnel dead on edge"
                if cur_url and (time.time() - last_health_probe) >= HEALTH_PROBE_INTERVAL_SEC:
                    last_health_probe = time.time()
                    healthy = probe_url_alive(cur_url)
                    if healthy:
                        if health_fail_count > 0:
                            log(f"URL health recovered after {health_fail_count} fails")
                        health_fail_count = 0
                    else:
                        health_fail_count += 1
                        log(f"URL health probe FAILED ({health_fail_count}/{HEALTH_FAIL_LIMIT}) for {cur_url}")
                        if health_fail_count >= HEALTH_FAIL_LIMIT:
                            log(f"URL dead {HEALTH_FAIL_LIMIT}x — killing cloudflared to force fresh tunnel")
                            try:
                                proc.terminate()
                                proc.wait(timeout=5)
                            except Exception:
                                try: proc.kill()
                                except Exception: pass
                            need_restart = True
                            break

            if need_restart:
                # Update last_url tracker from current state before respawning
                with _state_lock:
                    if _state["url"]:
                        last_url_box[0] = _state["url"]
                last_url = last_url_box[0]
                time.sleep(RESTART_BACKOFF_SEC)
                continue

    except KeyboardInterrupt:
        log("interrupted by user")
    finally:
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
        write_heartbeat("stopped", last_url_box[0] if last_url_box else "")
        release_pid_lock()


if __name__ == "__main__":
    main()
