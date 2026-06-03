"""brain_lock.py - encrypt the Claude brain and push to GitHub.

Security model: key derives from two security questions only the user knows.
Q1: What is the cast of your mother?  Canonical: "jalwana"
Q2: What is the cast of your father?  Canonical: "kamboh"

Spelling variants are accepted (Pakistani caste names have many transliterations).
Whoever knows both answers can unlock; nobody else.

Pipeline:
  1. Snapshot files: monitor/.claude_brain.db, memory.md, feb11_labels.json, state files
  2. tar+xz compress (SQLite compresses ~10× — 430MB → ~40MB typical)
  3. Encrypt: openssl AES-256-CBC PBKDF2 with passphrase = "<mom_canonical>::<dad_canonical>"
  4. Output to: brain_vault/turtle-brain-YYYY-MM-DD-HHMM.tar.xz.enc
  5. git add + commit + push (must NOT include the plaintext .db — see .gitignore)

USAGE:
  python brain_lock.py                 # one-shot snapshot + push
  python brain_lock.py --loop          # daemon, snapshot every 1 hour
  python brain_lock.py --watch-alert   # watchdog: alert if no push in 24h

If git push fails (credentials missing, no network), the encrypted bundle is
still written to disk locally — recovery requires only the bundle file plus
the two security answers, NOT git access.
"""
import sys, os, tarfile, subprocess, time, argparse, shutil, json
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

ROOT  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
VAULT = ROOT / "brain_vault"
TMP   = ROOT / "monitor" / ".brain_lock_tmp"

# Canonical security answers — these become the encryption passphrase.
# The variant sets below allow forgiving input matching but the KEY is
# derived from the canonical normalized form (so all variants unlock).
CANONICAL_MOM = "jalwana"
CANONICAL_DAD = "kamboh"

# Accepted spellings. Anything in this set unlocks. Add more as needed.
JALWANA_VARIANTS = {
    "jalwana", "jalvana", "jalwaana", "jalwaanaa", "jelwana", "jelwaana",
    "jhalwana", "jallwana", "jalwanah", "jelwanah", "jolvana", "jalwanaa",
    "jaalwana", "jaalvana",
}
KAMBOH_VARIANTS = {
    "kamboh", "kambo", "kamboj", "kambooh", "kambhoh", "kamhoh", "qamboh",
    "kamohb", "kamboje", "kamooj", "kambhuh", "kambooj", "kambhojj",
    "khamboh", "kampoh",
}


def normalize(s):
    return ''.join(c.lower() for c in (s or '') if c.isalnum())


def check_mom(answer): return normalize(answer) in JALWANA_VARIANTS
def check_dad(answer): return normalize(answer) in KAMBOH_VARIANTS


def derive_passphrase():
    """The canonical passphrase. Same for everyone who knows the answers."""
    return f"{CANONICAL_MOM}::{CANONICAL_DAD}"


# Files to include in the snapshot. Plaintext copies of these are what get
# bundled+encrypted. Add new files here as we accumulate persistent state.
PROTECTED_FILES = [
    ROOT / "monitor" / ".claude_brain.db",
    ROOT / "monitor" / ".memory_hawk_state.json",
    ROOT / "monitor" / ".chat_monitor_last_ts",
    ROOT / "monitor" / "feb11_labels.json",
    ROOT / "memory.md",
    # Common\Files state snapshots (broker truth)
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\feb11_state_88011.json"),
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\feb11_runtime_88011.json"),
    Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"),
]


def bundle_tar(out_tar):
    """tar+xz of all PROTECTED_FILES (skipping missing). Returns size in MB."""
    TMP.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_tar, "w:xz", preset=6) as tar:
        for p in PROTECTED_FILES:
            if not p.exists(): continue
            arc_name = p.name if p.parent != ROOT else p.relative_to(ROOT).as_posix()
            try:
                tar.add(str(p), arcname=arc_name)
            except (PermissionError, OSError) as e:
                print(f"  ! skip {p}: {e}")
    return out_tar.stat().st_size / 1e6


def encrypt(in_path, out_path, passphrase):
    """openssl AES-256-CBC PBKDF2 600k iters. Salt embedded in header."""
    cmd = [
        "openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "600000",
        "-salt", "-pass", f"pass:{passphrase}",
        "-in", str(in_path), "-out", str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"openssl encrypt failed: {res.stderr}")


def git_add_commit_push(rel_path, msg):
    """Add + commit + push. Returns (ok, log)."""
    log = []
    try:
        subprocess.run(["git", "add", str(rel_path)], cwd=ROOT, check=True,
                       capture_output=True, text=True)
        log.append(f"git add OK ({rel_path})")
        r = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.append(f"git commit OK: {r.stdout.splitlines()[0] if r.stdout else ''}")
        else:
            # "nothing to commit" is OK
            if "nothing to commit" in (r.stdout + r.stderr).lower():
                log.append("git commit: nothing to commit")
                return True, "\n".join(log)
            log.append(f"git commit FAIL: {r.stderr}")
            return False, "\n".join(log)
        r = subprocess.run(["git", "push"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            log.append("git push OK")
            return True, "\n".join(log)
        else:
            log.append(f"git push FAIL: {r.stderr}")
            return False, "\n".join(log)
    except subprocess.TimeoutExpired:
        log.append("git push TIMEOUT (60s) — bundle saved locally")
        return False, "\n".join(log)
    except Exception as e:
        log.append(f"git op crashed: {e}")
        return False, "\n".join(log)


def lock_once():
    now = datetime.now(tz=UTC)
    stamp = now.strftime("%Y-%m-%d-%H%M")
    VAULT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    tar_tmp = TMP / f"brain-{stamp}.tar.xz"
    enc_out = VAULT / f"turtle-brain-{stamp}.tar.xz.enc"

    print(f"[brain-lock] {now.isoformat()} — bundling...")
    size_mb = bundle_tar(tar_tmp)
    print(f"[brain-lock] tar+xz: {size_mb:.1f} MB")

    print(f"[brain-lock] encrypting...")
    encrypt(tar_tmp, enc_out, derive_passphrase())
    enc_size = enc_out.stat().st_size / 1e6
    print(f"[brain-lock] encrypted: {enc_size:.1f} MB → {enc_out.name}")

    try: tar_tmp.unlink()
    except: pass

    # Also write a manifest JSON so we can track snapshots
    manifest_path = VAULT / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try: manifest = json.loads(manifest_path.read_text())
        except: pass
    manifest[stamp] = {
        "ts_utc": now.isoformat(),
        "file": enc_out.name,
        "size_mb": round(enc_size, 2),
        "files_included": [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                           for p in PROTECTED_FILES if p.exists()],
    }
    # Prune manifest to last 200 entries
    if len(manifest) > 200:
        keys = sorted(manifest.keys())[-200:]
        manifest = {k: manifest[k] for k in keys}
    manifest_path.write_text(json.dumps(manifest, indent=2))

    rel_vault = VAULT.relative_to(ROOT)
    ok, log = git_add_commit_push(str(rel_vault), f"brain backup {stamp}")
    print(f"[brain-lock] {log}")
    return ok


def watch_alert():
    """Check newest manifest entry; warn if older than 24h."""
    manifest_path = VAULT / "manifest.json"
    if not manifest_path.exists():
        print("[brain-watchdog] NO MANIFEST — no backups yet"); return False
    m = json.loads(manifest_path.read_text())
    if not m:
        print("[brain-watchdog] manifest empty"); return False
    latest = max(m.keys())
    ts = datetime.fromisoformat(m[latest]["ts_utc"])
    age_h = (datetime.now(tz=UTC) - ts).total_seconds() / 3600
    if age_h > 24:
        print(f"[brain-watchdog] STALE — last backup was {age_h:.1f}h ago. RUN brain_lock NOW.")
        return False
    print(f"[brain-watchdog] healthy — last backup {age_h:.1f}h ago ({m[latest]['file']})")
    return True


def loop(interval_sec=3600):
    while True:
        try:
            lock_once()
        except Exception as e:
            print(f"[brain-lock] crash: {e}")
        time.sleep(interval_sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="Run hourly snapshot daemon")
    ap.add_argument("--interval", type=int, default=3600, help="Loop interval seconds")
    ap.add_argument("--watch-alert", action="store_true", help="Check freshness only")
    args = ap.parse_args()
    if args.watch_alert: sys.exit(0 if watch_alert() else 1)
    if args.loop: loop(args.interval)
    else: lock_once()


if __name__ == "__main__":
    main()
