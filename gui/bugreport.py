"""bugreport.py — let a user send Zee a bug report that is actually useful.

Zee 2026-08-03: *"Settings mein ek button banao — report a bug — jo email kar de mujhe at
zeecitizen@gmail.com ke user ne ye bug dhoonda hai software mein."*

A report that says "it's broken" costs more time than it saves, so this gathers the
diagnostics that answer the first five questions anyone would ask — which build, which
market, is the EA alive, is the data fresh, what did the last run actually say — and packs
them into the mail body automatically.

It uses a mailto: link rather than SMTP on purpose: no credentials to configure, no password
to store on a stranger's machine, and it works with whatever mail client they already use.
A copy is always written to disk first, so nothing is lost if the mail client never opens.
"""
from __future__ import annotations
import json, platform, subprocess, sys, time, urllib.parse, webbrowser
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
REPORTS = REPO / "bug_reports"
TO = "zeecitizen@gmail.com"


def _git_version():
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h %ad %s", "--date=short"],
                           cwd=str(REPO), capture_output=True, text=True, timeout=8)
        return (r.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown (not a git checkout)"


def diagnostics(market="XAU"):
    """The facts worth having before anyone can help."""
    d = {
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds") + " UTC",
        "build": _git_version(),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "market": market,
    }
    try:
        import settings as S
        cfg = S.load()
        d["connection"] = cfg.get("connection")
        d["claude_cli_installed"] = S.cli_available()
        d["api_key_saved"] = S.has_key()
        d["rulebook"] = str(S.rulebook_path() or "—")
        terms = S.find_terminals()
        d["mt5_terminals_found"] = len(terms)
        d["mt5_selected"] = next((t["label"] for t in terms
                                  if t["id"] == cfg.get("mt5_terminal")), "—")
    except Exception as e:
        d["settings_error"] = str(e)[:200]

    try:
        import trade_book as TB
        lv = TB.live(market)
        d["ea_heartbeat"] = lv.get("error") or f"{lv.get('age_sec')}s old"
        if not lv.get("error"):
            d["broker"] = {"bid": lv.get("bid"), "spread": lv.get("spread"),
                           "balance": lv.get("balance"), "equity": lv.get("equity"),
                           "open_positions": len(lv.get("positions") or [])}
        day, cap = TB.day_caption(market)
        rows = TB.book(market, day)
        s = TB.summary(rows)
        d["showing_day"] = f"{day} ({cap})"
        d["session"] = s
    except Exception as e:
        d["trade_book_error"] = str(e)[:200]

    try:
        import claude_judge as J  # noqa
    except Exception:
        sys.path.insert(0, str(MON))
    try:
        import claude_judge as J
        r = J.scan(market)
        d["last_scan"] = ("null (no setup)" if r is None else
                          r.get("error") or f"PENDING {r.get('side')} @ {r.get('entry')}")
    except Exception as e:
        d["last_scan_error"] = str(e)[:200]

    try:
        import lessons as L
        d["lessons_recorded"] = L.count()
    except Exception:
        pass
    try:
        import autolearn as AL
        d["autolearn"] = AL.status()["active"]
    except Exception:
        pass

    for name in ("oanda_m1.csv", "btc_m1.csv"):
        f = COMMON / name
        if f.exists():
            d[f"data_{name}"] = f"{int(time.time() - f.stat().st_mtime)}s old"
    return d


def compose(what, expected, market="XAU", include_diag=True):
    body = ["A user found a bug in Turtle Desktop.", "",
            "WHAT HAPPENED", "-" * 40, (what or "").strip() or "(not described)", "",
            "WHAT WAS EXPECTED", "-" * 40, (expected or "").strip() or "(not described)", ""]
    if include_diag:
        body += ["DIAGNOSTICS", "-" * 40,
                 json.dumps(diagnostics(market), indent=1, default=str), ""]
    return "\n".join(body)


def save(body):
    REPORTS.mkdir(parents=True, exist_ok=True)
    f = REPORTS / f"bug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    f.write_text(body, encoding="utf-8")
    return f


def send(what, expected, market="XAU", include_diag=True):
    """Save a copy, then hand it to whatever mail client the user has.

    Returns (path, opened). `opened` False means they should send it by hand — the file is
    still there, so nothing is lost."""
    body = compose(what, expected, market, include_diag)
    path = save(body)
    subject = "Turtle Desktop bug — " + (what or "no description").strip().splitlines()[0][:60]
    url = ("mailto:" + TO + "?subject=" + urllib.parse.quote(subject)
           + "&body=" + urllib.parse.quote(body[:1800]))   # mailto has a length limit
    opened = False
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    return path, opened, body
