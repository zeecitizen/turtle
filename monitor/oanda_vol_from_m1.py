"""oanda_vol_from_m1.py — oanda_vol.csv for ZeeUHV, derived from the CDP feed.

Zee 2026-08-20: ZUHV1 (ZeeUHV v1.58) must read HIS eye's volume, not Blueberry's
tick-count. The EA reads Common\\Files\\oanda_vol.csv; the only writer of that file
was oanda_volume_bridge.py, which needs tvDatafeed. This derives the same file from
the oanda_m1.csv the CDP bridge already produces, so there is exactly ONE producer
of OANDA bars on this machine and this script never writes oanda_m1.csv.

Two jobs, because the chart will not stay fresh on its own:

  1. RELOAD THE CHART. Measured 2026-08-20: TradingView's web chart loads its bar
     history once and then never streams — with the window hidden AND with it
     visible. It sat 3h24m stale while the bridge faithfully re-exported the same
     306 rows every 20s (fresh mtime, dead content). A Page.reload pulls it current
     immediately (20:59 -> 22:05 UTC in one reload). So we reload on a cycle.

  2. CONVERT. oanda_m1.csv is keyed in TRUE UTC epoch; the EA's lookup is keyed in
     BROKER SERVER time and compared against iTime() with an exact-match binary
     search. Blueberry server = UTC+3, established by close-price alignment over
     233 bars (mean |diff| 0.1166; the next-best shift was 13.34 — see the audit).
     A wrong offset here does not fail loudly, it silently returns broker volume
     for every bar, so the offset is asserted, not assumed.

Output format, matching what ZeeUHV.LoadOandaVol() parses:
    ASCII, no header, sorted ascending, one line per minute:
        2026.08.20 23:58,78
        ^ server time (UTC+3)   ^ OANDA volume

Usage:
    python monitor/oanda_vol_from_m1.py            # one cycle
    python monitor/oanda_vol_from_m1.py --loop 45  # keep chart + file fresh
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CDP_HTTP = "http://localhost:9222/json"
SERVER_OFFSET = timedelta(hours=3)          # Blueberry = UTC+3 (verified by alignment)

_COMMON = Path(os.environ.get("APPDATA", r"C:/Users/zeesh/AppData/Roaming")) / \
          "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_IN = _COMMON / "oanda_m1.csv"            # READ ONLY — owned by oanda_bridge.py
VOL_OUT = _COMMON / "oanda_vol.csv"         # the EA's lookup table

PROBE_JS = ("(function(){try{var b=window._exposed_chartWidgetCollection"
            ".activeChartWidget.value().model().mainSeries().data().m_bars._items;"
            "return String(b[b.length-1].value[0]);}catch(e){return '';}})()")


async def _reload_chart():
    """Page.reload the XAU chart so the bridge's next pull sees current bars."""
    try:
        pages = json.load(urllib.request.urlopen(CDP_HTTP, timeout=5))
    except Exception as e:
        return f"CDP unreachable ({e})"
    targets = [p for p in pages
               if p.get("type") == "page" and p.get("webSocketDebuggerUrl")
               and "tradingview" in (p.get("url") or "").lower()]
    if not targets:
        return "no TradingView page on :9222"
    try:
        import websockets
    except ImportError:
        return "websockets not installed"
    try:
        async with websockets.connect(targets[0]["webSocketDebuggerUrl"],
                                      max_size=None) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Page.reload",
                                      "params": {"ignoreCache": False}}))
            await asyncio.sleep(0.5)
        return "reloaded"
    except Exception as e:
        return f"reload failed ({e})"


def read_m1():
    """oanda_m1.csv -> [(server_dt, volume)], sorted. Never writes."""
    rows = {}
    try:
        with M1_IN.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                utc = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc) \
                              .replace(tzinfo=None)
                rows[utc + SERVER_OFFSET] = int(float(r["volume"]))
    except FileNotFoundError:
        return []
    return [(t, rows[t]) for t in sorted(rows)]


def write_vol(rows):
    """Rewrite the EA's table. Sorted ascending — LoadOandaVol binary-searches it."""
    if not rows:
        return 0
    VOL_OUT.write_text("".join(f"{t:%Y.%m.%d %H:%M},{v}\n" for t, v in rows),
                       encoding="ascii")
    return len(rows)


def cycle(do_reload=True):
    note = asyncio.run(_reload_chart()) if do_reload else "skipped"
    if do_reload:
        time.sleep(30)          # chart rebuild (~20s) + one bridge cycle (20s)
    rows = read_m1()
    n = write_vol(rows)
    if n:
        newest, vol = rows[-1]
        age = (datetime.utcnow() + SERVER_OFFSET - newest).total_seconds() / 60
        print(f"[VOL] {n} minutes -> oanda_vol.csv · newest server "
              f"{newest:%Y.%m.%d %H:%M} (vol {vol}, {age:.1f} min old) · chart {note}",
              flush=True)
    else:
        print(f"[VOL] nothing to write (oanda_m1.csv empty/missing) · chart {note}",
              flush=True)
    return n


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between cycles")
    ap.add_argument("--no-reload", action="store_true")
    a = ap.parse_args()
    while True:
        try:
            cycle(do_reload=not a.no_reload)
        except Exception as e:
            print(f"[VOL] error: {e}", flush=True)
        if not a.loop:
            break
        time.sleep(a.loop)
