"""brain_unlock.py - DISASTER RECOVERY: restore Claude's memory from GitHub.

If the laptop is stolen / on fire / OS reinstalled:

  1. On any new machine:
       git clone https://github.com/zeecitizen/turtle
       cd turtle
  2. Run this script:
       python monitor/brain_unlock.py
  3. It asks the two security questions:
       Q1: What is the cast of your mother?  (answer: Jalwana)
       Q2: What is the cast of your father?  (answer: Kamboh)
  4. If both answered correctly, decrypts the latest brain bundle in
     brain_vault/ and restores files to their original paths.
     Claude can then resume from the EXACT second the laptop was lost.
"""
import sys, os, tarfile, subprocess, json, argparse, getpass
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
UTC = timezone.utc

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "brain_vault"
TMP   = ROOT / "monitor" / ".brain_unlock_tmp"


# Match brain_lock.py exactly:
CANONICAL_MOM = "jalwana"
CANONICAL_DAD = "kamboh"
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


def ask_questions(provided_mom=None, provided_dad=None):
    """Ask the two security questions. Returns canonical passphrase or None."""
    print("="*60)
    print("DISASTER RECOVERY — verify identity to unlock Claude's brain")
    print("="*60)
    mom = provided_mom or input("Q1: What is the cast of your mother? ").strip()
    if normalize(mom) not in JALWANA_VARIANTS:
        print("[unlock] mother's cast did not match any known variant.")
        return None
    print("[unlock] Q1 OK")
    dad = provided_dad or input("Q2: What is the cast of your father? ").strip()
    if normalize(dad) not in KAMBOH_VARIANTS:
        print("[unlock] father's cast did not match any known variant.")
        return None
    print("[unlock] Q2 OK")
    return f"{CANONICAL_MOM}::{CANONICAL_DAD}"


def latest_bundle():
    if not VAULT.exists(): return None
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
        raise RuntimeError(f"openssl decrypt failed: {res.stderr}")


def extract_to(out_tar, dest_root):
    """Extract tarball into dest_root using each file's archive name.
    Some entries are absolute paths (Common\\Files\\...) — those go back to
    their original absolute path. Repo-relative entries go under dest_root."""
    COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
    with tarfile.open(out_tar, "r:xz") as tar:
        for member in tar.getmembers():
            target = None
            name = member.name
            # heuristic: filenames we know live in Common\Files
            if name.startswith("feb11_state_") or name == "feb11_runtime_88011.json" or name == "turtle_fills.csv":
                target = COMMON / name
            elif name.startswith("monitor/") or name == "memory.md":
                target = dest_root / name
            else:
                target = dest_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src:
                if src is None: continue
                with open(target, "wb") as dst:
                    while True:
                        chunk = src.read(64 * 1024)
                        if not chunk: break
                        dst.write(chunk)
            print(f"  restored: {target}")


def unlock(provided_mom=None, provided_dad=None):
    TMP.mkdir(parents=True, exist_ok=True)
    bundle = latest_bundle()
    if not bundle:
        print("[unlock] no encrypted bundles found in brain_vault/")
        print("[unlock] If you've just cloned this repo, run `git pull` first.")
        return False
    print(f"[unlock] latest bundle: {bundle.name}")
    passphrase = ask_questions(provided_mom, provided_dad)
    if not passphrase: return False
    tar_tmp = TMP / "unlocked.tar.xz"
    try:
        decrypt(bundle, tar_tmp, passphrase)
        print(f"[unlock] decrypt OK, restoring files...")
        extract_to(tar_tmp, ROOT)
        print(f"[unlock] DONE — Claude's brain restored from {bundle.name}.")
        print(f"[unlock] Recent memory.md tail:")
        try:
            from itertools import islice
            with open(ROOT / "memory.md", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    print("    " + line.rstrip())
        except: pass
        return True
    except Exception as e:
        print(f"[unlock] FAILED: {e}")
        return False
    finally:
        try: tar_tmp.unlink()
        except: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mom", default=None, help="mother's cast (skip prompt)")
    ap.add_argument("--dad", default=None, help="father's cast (skip prompt)")
    args = ap.parse_args()
    ok = unlock(args.mom, args.dad)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
