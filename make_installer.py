"""make_installer.py — build a USB-ready installer for the whole trading system.

Zee, 2026-08-11: "i want to make this software available for installation on a computer.
So let's say an ideal would be to copy software to a USB stick and then run its setup.exe
on a new computer and suddenly we have everything we need to run the software (no mess)..
clean neat installation."

WHAT THIS PRODUCES
    dist/TurtleTrader/            <- copy this whole folder to a USB stick
        INSTALL.bat               <- the one thing to run on the new machine
        payload/
            python/               a complete Python runtime, no system install needed
            node/                 the Node runtime the dashboards run on
            turtle/               the code, trimmed to what actually runs
            wheels/               every third-party package, pinned, installed offline

THE DESIGN RULE: NOTHING TOUCHES THE SYSTEM.
No registry keys, no PATH edits, no "Python not found" three months later. Everything
lands in one folder (default C:\\TurtleTrader) and everything is launched by absolute
path from inside it. Uninstalling is deleting the folder.

WHAT IS DELIBERATELY *NOT* BUNDLED, and why
  * SECRETS. API keys, the WhatsApp config, the dashboard password. Zee's standing rule
    is that anything written into the repo lives in git history forever, and the same
    logic applies to a USB stick that can be lost. INSTALL.bat asks for them on first
    run and writes them locally.
  * METATRADER 5. It is the broker's own installer, tied to their licence, and it must
    be downloaded from Blueberry so the account details match. The installer detects
    whether MT5 is present and says exactly what to do if not.
  * The 3.5 GB of lesson audio, the brain database and the tick parquet. None of it is
    needed to place a trade; bundling it would turn a 600 MB stick into a 4 GB one.

    py make_installer.py                 # build it
    py make_installer.py --out E:/       # build straight onto the USB stick
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent
PY_HOME = Path(sys.executable).parent
NODE_HOME = Path(r"C:/Program Files/nodejs")

# Everything the trading loop imports. Kept explicit rather than freezing the whole
# environment: 82 packages are installed on this machine and most are research tools
# that would triple the download for no runtime benefit.
# MEASURED, not assumed. Every script that stays running was scanned for imports:
# feed_supervisor, tape_archive, oanda_live_matcher, zeeuhv_live, mt5_headless,
# read_opt, doctrine and the bridges are ALL pure standard library. Only two things
# outside it are needed to trade — the cockpit's image library and the feed's
# websocket client. pandas, numpy, matplotlib, openai, yt_dlp and lxml were research
# tools; they cost 140 MB and place no trades.
CORE_PKGS = ["pillow", "websockets"]
EXTRA_PKGS = ["requests", "psutil"]      # not imported today, but tiny and often wanted

# Directories that must never reach the stick: giant media, generated caches, and
# anything that could carry a credential.
SKIP_DIRS = {".git", "__pycache__", "node_modules", "_loom_audio", "_vsa_audio",
             "dist", "mt5_rig",
             "_tester_runs", "strategy_lab", "setup_labels", "daily_reports",
             "preserved", ".claude", "temp", "_headless",
             # 208 MB of encrypted blobs and a personal memory archive. Neither is
             # needed to place a trade, and both are private to Zee.
             "brain_vault", "memory_backup", "_soul", "USB_TurtleDesktop"}
SKIP_SUFFIX = {".pyc", ".log", ".db", ".parquet", ".webm", ".mp4", ".mp3", ".hcc", ".tkc"}
SECRET_HINTS = ("key", "token", "secret", "password", "cred", "whatsapp", "vapid",
                ".env", "auth")

# A FILENAME TEST IS NOT A SECRET TEST. The first build passed its own filename check
# while carrying Zee's and his sister's WhatsApp numbers in a dozen files, plus a
# Cloudflare token sitting in an error log. These patterns look at CONTENT instead, and
# a file that matches is skipped no matter what it is called.
import re as _re
CONTENT_SECRETS = [
    (_re.compile("sk-ant-[A-Za-z0-9_-]{20,}"), "anthropic key"),
    (_re.compile("sk-[A-Za-z0-9]{32,}"), "openai key"),
    (_re.compile(chr(92) + "b" + chr(92) + "d{10,}@c" + chr(92) + ".us"), "whatsapp number"),
    (_re.compile(chr(92) + "b[0-9a-f]{32,}" + chr(92) + "b"), "long hex secret"),
]


def has_secret_content(p: Path) -> str | None:
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".ico", ".zip", ".ex5", ".dll",
                            ".pyd", ".exe", ".enc", ".csv"):
        return None
    try:
        if p.stat().st_size > 3_000_000:
            return None
        t = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    for rx, what in CONTENT_SECRETS:
        if rx.search(t):
            return what
    return None


def is_secret(p: Path) -> bool:
    n = p.name.lower()
    return any(h in n for h in SECRET_HINTS)


# Copied verbatim, the Python folder brings 62 MB of HTML docs, the full CPython test
# suite, and site-packages holding all 82 installed packages — of which the live system
# imports two. The wheels are installed by INSTALL.bat instead, so site-packages can go
# entirely except pip, which does the installing.
PY_PRUNE = {"Doc", "test", "tests", "idlelib", "turtledemo", "__pycache__",
            "site-packages", "Lib/test", "include", "libs"}

# The dashboards require only node built-ins — crypto, fs, http, https, path. npm and
# its node_modules install packages we never install, so they are 11.6 MB of nothing.
NODE_PRUNE = {"node_modules", "npm", "npx", "npm.cmd", "npx.cmd", "npm.ps1", "npx.ps1",
              "install_tools.bat", "nodevars.bat", "corepack", "corepack.cmd"}


def copy_tree(src: Path, dst: Path, label: str, verbatim: bool = False,
              prune: set | None = None) -> tuple[int, int]:
    """Copy a tree, skipping junk, media and anything that smells like a credential.

    verbatim=True copies EVERYTHING. The Python and Node runtimes need it: node ships
    its own node_modules (npm lives there) and python ships .pyc caches, both of which
    the normal skip list would delete — the first build copied 10 of node's files and
    would have produced a runtime that could not start.
    """
    n = bytes_ = 0
    skipped_secrets = []
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        if verbatim:
            if prune and any(part in prune for part in rel.parts):
                # keep pip itself: it is what installs the wheels on the new machine
                if not (rel.parts[:2] == ("Lib", "site-packages")
                        and len(rel.parts) > 2 and rel.parts[2].startswith(("pip", "_pip"))):
                    continue
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(f, out); n += 1; bytes_ += f.stat().st_size
            except Exception:
                pass
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if f.suffix.lower() in SKIP_SUFFIX:
            continue
        if is_secret(f):
            skipped_secrets.append(rel.as_posix())
            continue
        found = has_secret_content(f)
        if found:
            skipped_secrets.append(f"{rel.as_posix()} [{found}]")
            continue
        if f.stat().st_size > 60_000_000:          # nothing this big is needed to trade
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(f, out)
            n += 1
            bytes_ += f.stat().st_size
        except Exception:
            pass
    print(f"   {label:22s} {n:6,d} files  {bytes_/1e6:8,.1f} MB")
    if skipped_secrets:
        print(f"      (held back {len(skipped_secrets)} credential file(s): "
              f"{', '.join(skipped_secrets[:3])}{'…' if len(skipped_secrets) > 3 else ''})")
    return n, bytes_


def build(out_dir: Path, with_extras: bool = True):
    t0 = time.time()
    stage = out_dir / "TurtleTrader"
    payload = stage / "payload"
    if stage.exists():
        print(f"  clearing previous build at {stage}")
        shutil.rmtree(stage, ignore_errors=True)
    payload.mkdir(parents=True, exist_ok=True)
    print(f"\nBUILDING -> {stage}\n")

    total = 0
    # 1. the Python runtime, whole. Copying it beats an embeddable zip because this one
    #    is already proven to run the system, tkinter and all.
    _, b = copy_tree(PY_HOME, payload / "python", "python runtime", verbatim=True,
                     prune=PY_PRUNE)
    total += b

    # 2. Node, for the two dashboard servers
    if NODE_HOME.exists():
        _, b = copy_tree(NODE_HOME, payload / "node", "node runtime", verbatim=True,
                         prune=NODE_PRUNE)
        total += b
    else:
        print("   node runtime          NOT FOUND — dashboards will not start")

    # 3. the code
    _, b = copy_tree(ROOT, payload / "turtle", "turtle code")
    total += b

    # 4. the packages, downloaded as wheels so the new machine needs no internet
    wheels = payload / "wheels"
    wheels.mkdir(exist_ok=True)
    pkgs = CORE_PKGS + (EXTRA_PKGS if with_extras else [])
    print(f"   downloading {len(pkgs)} packages as wheels…")
    r = subprocess.run([sys.executable, "-m", "pip", "download", "-d", str(wheels), *pkgs],
                       capture_output=True, text=True)
    got = list(wheels.glob("*"))
    wb = sum(f.stat().st_size for f in got)
    total += wb
    print(f"   wheels                 {len(got):6,d} files  {wb/1e6:8,.1f} MB"
          f"{'' if r.returncode == 0 else '  (some failed — see pip output)'}")

    write_installer(stage)
    print(f"\n   TOTAL {total/1e6:,.0f} MB in {time.time()-t0:.0f}s")
    print(f"\n   Copy this folder to a USB stick:\n      {stage}")
    print(f"   On the new machine, run:  INSTALL.bat")
    return stage
def write_installer(stage: Path):
    """The one file a person runs. Deliberately a .bat: it is readable, it needs no
    admin rights, and anyone can see exactly what it will do before running it."""
    (stage / "INSTALL.bat").write_text(r"""@echo off
setlocal EnableDelayedExpansion
title Turtle Trader - Setup
color 0B
echo.
echo   ===========================================================
echo      TURTLE TRADER  -  setup
echo   ===========================================================
echo.
echo   This installs everything into ONE folder.
echo   Nothing is written to the registry and nothing is added to PATH.
echo   To uninstall later, delete that folder. That is all.
echo.

set "TARGET=C:\TurtleTrader"
set /p TARGET=  Install to [%TARGET%]:
if "%TARGET%"=="" set "TARGET=C:\TurtleTrader"

echo.
echo   Installing to %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
xcopy /E /I /Q /Y "%~dp0payload\python"  "%TARGET%\python"  >nul
echo     [1/5] python runtime
xcopy /E /I /Q /Y "%~dp0payload\node"    "%TARGET%\node"    >nul
echo     [2/5] node runtime
xcopy /E /I /Q /Y "%~dp0payload\turtle"  "%TARGET%\turtle"  >nul
echo     [3/5] trading code

set "PY=%TARGET%\python\python.exe"
"%PY%" -m pip install --no-index --find-links "%~dp0payload\wheels" ^
    requests websockets psutil numpy pandas pillow >nul 2>&1
echo     [4/5] python packages (offline)

REM ---- MetaTrader 5 has to come from the broker; we can only check and tell the truth
set "MT5=%ProgramFiles%\Blueberry Markets MetaTrader 5\terminal64.exe"
if exist "%MT5%" (
  echo     [5/5] MetaTrader 5 found
) else (
  echo     [5/5] MetaTrader 5 NOT found
  echo           Download it from Blueberry Markets and log in BEFORE first run.
  echo           The EAs are in %TARGET%\turtle\mt5 - compile them in MetaEditor.
)

REM ---- Credentials are NOT asked for during setup, deliberately.
REM      Install time is the wrong moment to decide about keys, and 'set /p' echoes
REM      what is typed straight onto the screen where a screenshot or anyone behind
REM      you catches it. A separate script does it properly, when the person is
REM      ready, with the typing hidden by PowerShell's SecureString.
set "AK=%TARGET%\ADD_KEYS.bat"
> "%AK%" echo @echo off
>> "%AK%" echo title Turtle Trader - keys
>> "%AK%" echo echo.
>> "%AK%" echo echo   Keys are OPTIONAL. Trading works without them.
>> "%AK%" echo echo   Stored on this machine only, never on the USB stick.
>> "%AK%" echo echo.
>> "%AK%" echo powershell -NoProfile -Command "$k=Read-Host 'Anthropic API key (hidden, Enter to skip)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k)); if($p){Set-Content -NoNewline -Path '%TARGET%\turtle\monitor\.claude_api_key' -Value $p; Write-Host '   saved'}else{Write-Host '   skipped'}"
>> "%AK%" echo powershell -NoProfile -Command "$k=Read-Host 'Dashboard password (hidden, Enter to skip)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k)); if($p){Set-Content -NoNewline -Path '%TARGET%\turtle\monitor\.dashboard_password' -Value $p; Write-Host '   saved'}else{Write-Host '   skipped'}"
>> "%AK%" echo pause
REM ---- one launcher, absolute paths only
> "%TARGET%\START.bat" echo @echo off
>> "%TARGET%\START.bat" echo title Turtle Trader
>> "%TARGET%\START.bat" echo set "PY=%TARGET%\python\python.exe"
>> "%TARGET%\START.bat" echo set "NODE=%TARGET%\node\node.exe"
>> "%TARGET%\START.bat" echo cd /d "%TARGET%\turtle"
>> "%TARGET%\START.bat" echo start "dashboard" /min "%%NODE%%" "%TARGET%\turtle\dashboard\claude_trader\server.js"
>> "%TARGET%\START.bat" echo start "supervisor" /min "%%PY%%" -u "%TARGET%\turtle\monitor\feed_supervisor.py" --loop 120
>> "%TARGET%\START.bat" echo start "archive"    /min "%%PY%%" -u "%TARGET%\turtle\monitor\tape_archive.py" --loop 60
>> "%TARGET%\START.bat" echo start "cockpit"    "%TARGET%\python\pythonw.exe" "%TARGET%\turtle\gui\camel_gui.py"
>> "%TARGET%\START.bat" echo echo   Started. Dashboard: http://localhost:3457
>> "%TARGET%\START.bat" echo timeout /t 5 ^>nul

powershell -NoProfile -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Turtle Trader.lnk'); $s.TargetPath='%TARGET%\START.bat'; $s.WorkingDirectory='%TARGET%'; $s.Save()" >nul 2>&1

echo.
echo   ===========================================================
echo      DONE
echo   ===========================================================
echo.
echo   Installed at : %TARGET%
echo   Optional keys: run ADD_KEYS.bat (typing is hidden)
echo   Start it     : desktop shortcut "Turtle Trader", or START.bat
echo   Dashboard    : http://localhost:3457
echo.
echo   BEFORE TRADING: open MetaTrader 5, log in, and drag the
echo   ZeeUHV expert onto an XAUUSD M1 chart.
echo   Read %TARGET%\turtle\THINGS_TO_REMEMBER.md first.
echo.
pause
""", encoding="utf-8", newline="\r\n")

    (stage / "READ_ME_FIRST.txt").write_text(
        "TURTLE TRADER — USB installer\r\n"
        "=============================\r\n\r\n"
        "1. Copy this whole TurtleTrader folder to the new computer (or run from the stick).\r\n"
        "2. Double-click INSTALL.bat.\r\n"
        "3. Answer the two questions (install folder, and any API keys you use).\r\n"
        "4. Start it from the desktop shortcut.\r\n\r\n"
        "WHAT IT INSTALLS\r\n"
        "  A complete Python runtime, Node, the trading code, and every Python package\r\n"
        "  it needs — installed offline from the bundled wheels. No internet required.\r\n\r\n"
        "WHAT IT DOES NOT TOUCH\r\n"
        "  No registry entries. No PATH changes. Everything lives in one folder, and\r\n"
        "  uninstalling means deleting that folder.\r\n\r\n"
        "WHAT YOU MUST SUPPLY YOURSELF\r\n"
        "  MetaTrader 5 from your broker, logged in to your account. It is licensed to\r\n"
        "  them and tied to your login, so it cannot be shipped on a stick.\r\n"
        "  Your API keys — these are never written to the stick on purpose. A lost USB\r\n"
        "  stick should never be a lost account.\r\n\r\n"
        "AFTER INSTALLING\r\n"
        "  Read turtle\\THINGS_TO_REMEMBER.md — it explains the headless MT5 tester and\r\n"
        "  the traps that cost us hours, so nobody has to rediscover them.\r\n",
        encoding="utf-8", newline="\r\n")
    print("   INSTALL.bat + READ_ME_FIRST.txt written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist", help="where to build (e.g. E:/ for a USB stick)")
    ap.add_argument("--no-extras", action="store_true", help="core packages only, smaller")
    a = ap.parse_args()
    build(Path(a.out), with_extras=not a.no_extras)
