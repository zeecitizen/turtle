"""brain_lock.py — encrypt the Claude brain and push to GitHub.

Security model
--------------
The encryption passphrase is derived from TWO answers to security questions
that only the user (Zee) knows. These answers are NEVER stored in this repo
or any committed file. They live ONLY in:

  1. Zee's head, and
  2. A local file `monitor/.brain_key` (gitignored, never pushed) that
     caches the canonical spellings for unattended snapshot runs.

A new AI / collaborator who wants to decrypt MUST ask Zee for the two
answers. See `DEAR_AI_START_HERE.md` at the repo root for the protocol.

Key derivation:
  - Both answers are normalized: lowercase + alphanumeric only.
  - Passphrase = "<q1_normalized>::<q2_normalized>".
  - openssl AES-256-CBC PBKDF2 with 600k iterations.

Usage
-----
  python brain_lock.py                 # one-shot snapshot + push
  python brain_lock.py --loop          # daemon, snapshot every 1 hour
  python brain_lock.py --watch-alert   # watchdog: alert if no push in 24h
  python brain_lock.py --set-key       # prompt for both answers and cache locally
"""
import sys, os, tarfile, subprocess, time, argparse, json, getpass
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

ROOT     = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
VAULT    = ROOT / "brain_vault"
TMP      = ROOT / "monitor" / ".brain_lock_tmp"
KEY_FILE = ROOT / "monitor" / ".brain_key"   # GITIGNORED — never committed.


def normalize(s):
    """Lowercase + alphanumeric only. Forgives caps + whitespace + punctuation."""
    return ''.join(c.lower() for c in (s or '') if c.isalnum())


def derive_passphrase_from_answers(q1_answer, q2_answer):
    """Build the openssl passphrase from two raw answers."""
    a = normalize(q1_answer)
    b = normalize(q2_answer)
    if not a or not b:
        raise ValueError("Both answers must be non-empty after normalization.")
    return f"{a}::{b}"


def load_cached_key():
    """Return passphrase from local-only cache file, or None if absent."""
    if not KEY_FILE.exists():
        return None
    try:
        raw = KEY_FILE.read_text(encoding="utf-8").strip()
        if "::" not in raw:
            return None
        q1, q2 = raw.split("::", 1)
        return derive_passphrase_from_answers(q1, q2)
    except Exception:
        return None


def prompt_for_key():
    """Interactively ask the user for both answers. Saves to KEY_FILE."""
    print("\n=== Brain Lock setup ===")
    print("Two security questions. The combined answers become the encryption")
    print("passphrase. Spelling is normalized (lowercase, alphanumeric).\n")
    q1 = input("Q1: What is the caste/family name of your mother?  ").strip()
    q2 = input("Q2: What is the caste/family name of your father?  ").strip()
    p = derive_passphrase_from_answers(q1, q2)
    # cache the RAW answers (still local-only) for unattended runs
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(f"{normalize(q1)}::{normalize(q2)}\n", encoding="utf-8")
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    print(f"Cached locally at {KEY_FILE} (gitignored). Done.\n")
    return p


def get_passphrase():
    """Cache-first, then interactive prompt. Never returns the secret to the repo."""
    p = load_cached_key()
    if p:
        return p
    return prompt_for_key()


# Files included in the snapshot.
PROTECTED_FILES = [
    ROOT / "monitor" / ".claude_brain.db",
    ROOT / "monitor" / ".memory_hawk_state.json",
    ROOT / "monitor" / ".chat_monitor_last_ts",
    ROOT / "monitor" / "feb11_labels.json",
    ROOT / "memory.md",
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\feb11_state_88011.json"),
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\feb11_runtime_88011.json"),
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"),
]


def bundle_tar(out_tar):
    TMP.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_tar, "w:xz", preset=6) as tar:
        for p in PROTECTED_FILES:
            if not p.exists():
                continue
            arc_name = p.name if p.parent != ROOT else p.relative_to(ROOT).as_posix()
            try:
                tar.add(str(p), arcname=arc_name)
            except (PermissionError, OSError) as e:
                print(f"  ! skip {p}: {e}")
    return out_tar.stat().st_size / 1e6


def encrypt(in_path, out_path, passphrase):
    cmd = [
        "openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "600000",
        "-salt", "-pass", f"pass:{passphrase}",
        "-in", str(in_path), "-out", str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"openssl encrypt failed: {res.stderr}")


def git_add_commit_push(rel_path, msg):
    log = []
    try:
        subprocess.run(["git", "add", str(rel_path)], cwd=ROOT, check=True,
                       capture_output=True, text=True)
        log.append(f"git add OK ({rel_path})")
        r = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.append("git commit OK")
        else:
            if "nothing to commit" in (r.stdout + r.stderr).lower():
                return True, "\n".join(log + ["nothing to commit"])
            return False, "\n".join(log + [f"git commit FAIL: {r.stderr}"])
        r = subprocess.run(["git", "push"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return True, "\n".join(log + ["git push OK"])
        return False, "\n".join(log + [f"git push FAIL: {r.stderr}"])
    except subprocess.TimeoutExpired:
        return False, "git push TIMEOUT"
    except Exception as e:
        return False, f"git op crashed: {e}"


def lock_once():
    now = datetime.now(tz=UTC)
    stamp = now.strftime("%Y-%m-%d-%H%M")
    VAULT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    passphrase = get_passphrase()

    tar_tmp = TMP / f"brain-{stamp}.tar.xz"
    enc_out = VAULT / f"turtle-brain-{stamp}.tar.xz.enc"

    print(f"[brain-lock] {now.isoformat()} — bundling...")
    size_mb = bundle_tar(tar_tmp)
    print(f"[brain-lock] tar+xz: {size_mb:.1f} MB")

    print(f"[brain-lock] encrypting...")
    encrypt(tar_tmp, enc_out, passphrase)
    enc_size = enc_out.stat().st_size / 1e6
    print(f"[brain-lock] encrypted: {enc_size:.1f} MB → {enc_out.name}")

    try: tar_tmp.unlink()
    except: pass

    manifest_path = VAULT / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try: manifest = json.loads(manifest_path.read_text())
        except: pass
    manifest[stamp] = {
        "ts_utc": now.isoformat(),
        "file": enc_out.name,
        "size_mb": round(enc_size, 2),
    }
    if len(manifest) > 200:
        keys = sorted(manifest.keys())[-200:]
        manifest = {k: manifest[k] for k in keys}
    manifest_path.write_text(json.dumps(manifest, indent=2))

    rel_vault = VAULT.relative_to(ROOT)
    ok, log = git_add_commit_push(str(rel_vault), f"brain backup {stamp}")
    print(f"[brain-lock] {log}")
    return ok


def watch_alert():
    manifest_path = VAULT / "manifest.json"
    if not manifest_path.exists():
        print("[brain-watchdog] NO MANIFEST"); return False
    m = json.loads(manifest_path.read_text())
    if not m:
        print("[brain-watchdog] empty"); return False
    latest = max(m.keys())
    ts = datetime.fromisoformat(m[latest]["ts_utc"])
    age_h = (datetime.now(tz=UTC) - ts).total_seconds() / 3600
    if age_h > 24:
        print(f"[brain-watchdog] STALE — {age_h:.1f}h ago"); return False
    print(f"[brain-watchdog] healthy — {age_h:.1f}h ago"); return True


def loop(interval_sec=3600):
    while True:
        try: lock_once()
        except Exception as e: print(f"[brain-lock] crash: {e}")
        time.sleep(interval_sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=3600)
    ap.add_argument("--watch-alert", action="store_true")
    ap.add_argument("--set-key", action="store_true",
                    help="(Re)prompt for the two security answers and cache locally.")
    args = ap.parse_args()
    if args.set_key:
        prompt_for_key()
        return
    if args.watch_alert: sys.exit(0 if watch_alert() else 1)
    if args.loop: loop(args.interval)
    else: lock_once()


if __name__ == "__main__":
    main()
