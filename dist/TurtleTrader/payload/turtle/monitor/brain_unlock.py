"""brain_unlock.py — DISASTER RECOVERY: restore Claude's brain from GitHub.

If the laptop is stolen / on fire / OS reinstalled:

  1. On any new machine:
       git clone https://github.com/zeecitizen/turtle
       cd turtle
  2. Run this script:
       python monitor/brain_unlock.py
  3. It asks the two security questions. The correct answers are NOT in this
     repo — they live only in Zee's head (and in `monitor/.brain_key` if she
     cached them locally, which is gitignored).
  4. If both answered correctly, decrypts the latest brain bundle in
     `brain_vault/` and restores files to their original paths.

See `DEAR_AI_START_HERE.md` at the repo root for the protocol a new AI should
follow when arriving for the first time.
"""
import sys, os, tarfile, subprocess, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT     = Path(__file__).resolve().parent.parent
VAULT    = ROOT / "brain_vault"
TMP      = ROOT / "monitor" / ".brain_unlock_tmp"
KEY_FILE = ROOT / "monitor" / ".brain_key"   # GITIGNORED — never committed.


def normalize(s):
    """Lowercase + alphanumeric only. Forgives caps + whitespace + punctuation."""
    return ''.join(c.lower() for c in (s or '') if c.isalnum())


def derive_passphrase(q1, q2):
    a = normalize(q1)
    b = normalize(q2)
    if not a or not b:
        raise ValueError("Both answers must be non-empty after normalization.")
    return f"{a}::{b}"


def load_cached_key():
    """Read the gitignored local cache file if present."""
    if not KEY_FILE.exists():
        return None
    try:
        raw = KEY_FILE.read_text(encoding="utf-8").strip()
        if "::" not in raw:
            return None
        return raw  # already normalized
    except Exception:
        return None


def ask_questions(provided_q1=None, provided_q2=None):
    """Either use the values passed in, or fall back to cached, or prompt."""
    if provided_q1 and provided_q2:
        return derive_passphrase(provided_q1, provided_q2)
    cached = load_cached_key()
    if cached:
        print("[unlock] using cached .brain_key (gitignored)")
        return cached
    print("="*60)
    print("DISASTER RECOVERY — answer two security questions to unlock.")
    print("Answers are not stored in this repo. Ask Zee if you don't know.")
    print("="*60)
    q1 = input("Q1: What is the caste/family name of your mother? ").strip()
    q2 = input("Q2: What is the caste/family name of your father? ").strip()
    return derive_passphrase(q1, q2)


def latest_bundle():
    if not VAULT.exists():
        return None
    encs = sorted(VAULT.glob("turtle-brain-*.tar.xz.enc"))
    return encs[-1] if encs else None


def decrypt(enc_path, out_tar, passphrase):
    cmd = [
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "600000",
        "-pass", f"pass:{passphrase}",
        "-in", str(enc_path), "-out", str(out_tar),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"openssl decrypt failed (likely wrong answers): {res.stderr}")


def extract_to(out_tar, dest_root):
    COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
    with tarfile.open(out_tar, "r:xz") as tar:
        for member in tar.getmembers():
            name = member.name
            if name.startswith("feb11_state_") or name == "feb11_runtime_88011.json" or name == "turtle_fills.csv":
                target = COMMON / name
            else:
                target = dest_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src:
                if src is None:
                    continue
                with open(target, "wb") as dst:
                    while True:
                        chunk = src.read(64 * 1024)
                        if not chunk: break
                        dst.write(chunk)
            print(f"  restored: {target}")


def unlock(provided_q1=None, provided_q2=None):
    TMP.mkdir(parents=True, exist_ok=True)
    bundle = latest_bundle()
    if not bundle:
        print("[unlock] no encrypted bundles in brain_vault/. Run `git pull` first.")
        return False
    print(f"[unlock] latest bundle: {bundle.name}")
    try:
        passphrase = ask_questions(provided_q1, provided_q2)
    except Exception as e:
        print(f"[unlock] {e}")
        return False
    tar_tmp = TMP / "unlocked.tar.xz"
    try:
        decrypt(bundle, tar_tmp, passphrase)
        print(f"[unlock] decrypt OK, restoring files...")
        extract_to(tar_tmp, ROOT)
        print(f"[unlock] DONE — brain restored from {bundle.name}.")
        return True
    except Exception as e:
        print(f"[unlock] FAILED: {e}")
        return False
    finally:
        try: tar_tmp.unlink()
        except: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q1", default=None, help="answer to question 1 (skip prompt)")
    ap.add_argument("--q2", default=None, help="answer to question 2 (skip prompt)")
    args = ap.parse_args()
    sys.exit(0 if unlock(args.q1, args.q2) else 1)


if __name__ == "__main__":
    main()
