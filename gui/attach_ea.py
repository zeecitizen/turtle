"""attach_ea.py — walk the user through getting the right EA onto the right chart.

Zee 2026-08-03: *"Settings mein ek setting ho: Drag-Attach EA to Chart — jo instructions /
practical dikhaye ke kaunsa EA attach karna padega in MT5."*

This is not decoration. On 2026-08-02 an entire session judged twenty setups and traded
nothing, and the reason was mechanical: the EA in the terminal was an older build. The
window therefore does not just print steps — it CHECKS, in this order:

    1. is the source .mq5 in the terminal's Experts folder at all?
    2. is the compiled .ex5 there, and is it NEWER than the source?      <- the silent killer
    3. is the EA actually alive right now (a fresh heartbeat)?

and it copies the source across for you, because that is the step people forget.
"""
from __future__ import annotations
import json, os, shutil, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MT5_SRC = REPO / "mt5"
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
NO_WIN = 0x08000000

EA = {
    "XAU": {"name": "CaseSignalExecutor", "symbol": "XAUUSD", "magic": 88020,
            "chart": "XAUUSD, M1", "heartbeat": "xau_live.json",
            "feed": "OANDA:XAUUSD"},
    "BTC": {"name": "BtcCaseExecutor", "symbol": "BTCUSD", "magic": 88022,
            "chart": "BTCUSD, M1", "heartbeat": "btc_live.json",
            "feed": "COINBASE:BTCUSD"},
}


def terminal_dir():
    """The MT5 data folder Settings is pointing at (falls back to the one holding our EA)."""
    try:
        import settings as S
        cfg = S.load()
        tid = cfg.get("mt5_terminal")
        for t in S.find_terminals():
            if t["id"] == tid:
                return Path(t["path"])
        for t in S.find_terminals():
            if t["has_ea"]:
                return Path(t["path"])
        ts = S.find_terminals()
        if ts:
            return Path(ts[0]["path"])
    except Exception:
        pass
    return None


def check(market="XAU"):
    """Everything that has to be true, each answered separately."""
    e = EA[market]
    td = terminal_dir()
    src = MT5_SRC / (e["name"] + ".mq5")
    steps = []

    steps.append({
        "ok": src.exists(),
        "title": "the EA source exists in this install",
        "detail": str(src) if src.exists() else f"missing: {src}",
        "fix": None if src.exists() else "Reinstall Turtle Desktop — mt5\\ was not copied.",
    })

    if td is None:
        steps.append({"ok": False, "title": "an MT5 data folder was found",
                      "detail": "no MetaTrader 5 data folder detected",
                      "fix": "Install MetaTrader 5 and log into a DEMO account, then reopen "
                             "this window."})
        return {"market": market, "ea": e, "terminal": None, "steps": steps}

    exp = td / "MQL5" / "Experts"
    dst = exp / (e["name"] + ".mq5")
    ex5 = exp / (e["name"] + ".ex5")

    steps.append({
        "ok": dst.exists(),
        "title": "the EA source is in the terminal's Experts folder",
        "detail": str(dst) if dst.exists() else f"not there yet: {dst}",
        "fix": None if dst.exists() else "Press “Copy EA into MT5” below.",
    })

    if dst.exists() and ex5.exists():
        stale = ex5.stat().st_mtime < dst.stat().st_mtime - 2
        steps.append({
            "ok": not stale,
            "title": "the compiled .ex5 is up to date",
            "detail": (f"compiled {datetime.fromtimestamp(ex5.stat().st_mtime):%d %b %H:%M}"
                       f", source {datetime.fromtimestamp(dst.stat().st_mtime):%d %b %H:%M}"
                       + ("  →  the compile is OLDER than the source" if stale else "")),
            "fix": ("Open MetaEditor, open " + e["name"] + ".mq5 and press F7, then drag it "
                    "onto the chart again. This exact step being skipped is why a whole "
                    "session once traded nothing.") if stale else None,
        })
    else:
        steps.append({
            "ok": False, "title": "the compiled .ex5 is up to date",
            "detail": "no compiled .ex5 found",
            "fix": "Open MetaEditor, open " + e["name"] + ".mq5 and press F7 to compile.",
        })

    hb = COMMON / e["heartbeat"]
    alive, age = False, None
    if hb.exists():
        try:
            d = json.loads(hb.read_text(encoding="ascii", errors="replace"))
            age = int(time.time()) - int(d.get("ts", 0))
            alive = age < 30
        except Exception:
            pass
    steps.append({
        "ok": alive,
        "title": "the EA is running right now",
        "detail": (f"heartbeat {age}s old" if age is not None else "no heartbeat file yet"),
        "fix": None if alive else
               (f"Drag {e['name']} onto a {e['chart']} chart and switch Algo Trading ON. "
                "If it is already attached, it is an older build — recompile with F7."),
    })

    return {"market": market, "ea": e, "terminal": str(td), "experts": str(exp),
            "steps": steps, "ready": all(s["ok"] for s in steps)}


def copy_ea(market="XAU"):
    """Copy the source into the terminal. The step people forget, and the one that makes
    every later step possible."""
    e = EA[market]
    td = terminal_dir()
    if td is None:
        raise RuntimeError("No MT5 data folder found.")
    exp = td / "MQL5" / "Experts"
    exp.mkdir(parents=True, exist_ok=True)
    done = []
    for name in (e["name"] + ".mq5",):
        s = MT5_SRC / name
        if s.exists():
            shutil.copy2(s, exp / name)
            done.append(name)
    return exp, done


def open_experts(market="XAU"):
    td = terminal_dir()
    if td is None:
        raise RuntimeError("No MT5 data folder found.")
    exp = td / "MQL5" / "Experts"
    subprocess.Popen(["explorer", str(exp)])
    return exp


def instructions(market="XAU"):
    e = EA[market]
    return [
        ("1", f"Open MetaTrader 5 and log into a DEMO account.",
         "Never a live account until this has proved itself to you."),
        ("2", f"Open a {e['chart']} chart.",
         "One-minute timeframe — the whole strategy is built on M1 candles."),
        ("3", "Press “Copy EA into MT5” in this window.",
         f"That puts {e['name']}.mq5 where MetaEditor can see it."),
        ("4", "In MT5 press F4 to open MetaEditor, open "
              f"{e['name']}.mq5, and press F7 to compile.",
         "Skipping this is why a session once judged twenty setups and traded none — the "
         "terminal was still running an older build."),
        ("5", f"Drag {e['name']} from the Navigator onto the {e['chart']} chart.",
         "Navigator → Expert Advisors. Allow algo trading in the dialog."),
        ("6", "Switch the Algo Trading button ON (it turns green).",
         "Nothing executes while it is off."),
        ("7", "Check back here — the last line should turn green.",
         f"The EA publishes a heartbeat every second; magic {e['magic']}."),
        ("8", f"Set the TradingView chart to {e['feed']}.",
         "Price and volume come from there, not from MT5 — MT5's tick volume is not the "
         "volume this strategy needs."),
    ]
