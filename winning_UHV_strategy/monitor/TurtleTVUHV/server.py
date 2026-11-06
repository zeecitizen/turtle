"""Turtle TV - Zee 2026-10-20: "i want to build a tradingview's copy web app which can show the entire year's candles and my MT5 EA's code
applied to the candles" ... "i make a settings change on tradingview -> our tradingview call it "turtle tv" picks up the new settings and
reflects them on its own chart's candles -> then there's an export to MT5 button which puts all the optimized settings to an MT5 EA and runs
the tests and brings the result and publishes the result below the chart on turtle tv".

A TradingView-style chart of the WHOLE year (Blueberry real ticks, XAUUSD_BB) with MT5's OWN results on it. The Strategy Tester runs the real
EA (mt5/Saad_strategy_15min_view.mq5 = v1.27 verbatim + an export, built by make_view_ea.py); this app only SHOWS what it exported - every
candle with the EA's EMAs / ADX / ATR, every setup, skip, entry, exit and stand-aside ghost. No strategy logic lives here (CLAUDE.md: Python
may never stand in for the Strategy Tester).

Follow TradingView: the Saad indicator's settings are read from the open TradingView chart (the compare page's reader, monitor/saad_compare)
and mapped to the EA's inputs; a change (steady for 5 s) runs MT5 again, a newer change cancels a run still going.
Export to MT5: the run's settings as a preset (.set) in every MT5 terminal that has Saad_strategy_15min, plus a random-delay result.

   py monitor/saad_view/server.py            -> http://127.0.0.1:8773
API: GET /api/inputs · /api/runs · /api/run?id= · /api/status · /api/tv
     GET /api/mt5_report?id= · POST /api/run {sets, from, to, delay, label} · /api/follow {on, delay} · /api/tv_take {delay}
     POST /api/export {id} · /api/delete {id}"""
import base64
import importlib.util
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "monitor" / "strategy_lab"))
import axi_rig  # noqa: E402
import numpy as np  # noqa: E402
sys.path.insert(0, str(HERE))
import sim  # noqa: E402  (the Turtle TV Tester: numba, sets NUMBA_CPU_NAME itself)
import optimizer  # noqa: E402
import exitlab  # noqa: E402
import tplab  # noqa: E402
import lifecycle  # noqa: E402
import xlife
import probe  # noqa: E402
import dexlab  # noqa: E402
import ml  # noqa: E402
import mission  # noqa: E402
import stress  # noqa: E402
import sim_full  # noqa: E402

_spec = importlib.util.spec_from_file_location("saad_compare_server", ROOT / "monitor" / "saad_compare" / "server.py")
CMP = importlib.util.module_from_spec(_spec)      # the compare page's TradingView reader (no server is started by importing it)
_spec.loader.exec_module(CMP)

PORT = 8774                                 # TurtleTVUHV: the UHV copy (the original Turtle TV keeps 8773)
EA = "Saad_strategy_15min_view"
LIVE_EA = "Saad_strategy_15min"                # the EA the preset is for
SYMBOL, PERIOD = "XAUUSD_BB", "M15"           # Blueberry's real ticks (Zee's chart broker), Jan 1 - Oct 17 2026
RIG = "axi7"                                  # one of the compare page's year-view rigs (idle while its 10-month view is off)
DEPOSIT = 100000
FROM, TO = "2026.01.01", "2026.10.17"
DEXTER_REFERENCE_ID = "r20261024_235213"
RUNS = HERE / "runs"
DEXTER_FILE = RUNS / "dexter_experiments.json"
SETTINGS = HERE / "settings"
PRIMARY = HERE / "settings" / "primary.txt"         # the save that loads on every page start (Zee 2026-10-21)
SAVED = HERE / "settings" / "saved"                   # the page's saved chart settings, one JSON per save                  # the JSON hand-off files (format "turtle-settings/1"; see settings_doc)
STATIC = HERE / "static"
EA_MAKER = HERE / "make_ea_from_settings.py"
TERMINALS = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"
COMMON = TERMINALS / "Common" / "Files"
HIDE = {"InpExport", "InpExportTag", "InpMagicNumber", "InpVerbose", "InpDraw", "InpLog", "InpLogCsv", "InpShowEmas", "InpDrawSkips",
        "InpOptScore", "InpOptMinTrades"}
RUNS.mkdir(exist_ok=True)
SETTINGS.mkdir(exist_ok=True)
STATE = {"busy": False, "id": None, "label": "", "started": None, "phase": "", "error": None, "last": None, "cancel": False, "source": ""}
DEXTER_LOCK = threading.Lock()
DEXTER = {"busy": False, "cancel": False, "phase": "ready", "current": 0, "total": 5, "reference_id": DEXTER_REFERENCE_ID,
          "settings": {"risk_pct": 0.5, "pin_buffer": 0.5, "atr_mult": 1.7, "decay_bars": 4, "decay_r": -0.5, "tight_stop": 12.0, "time_bars": 4}, "results": [], "error": None}
if DEXTER_FILE.is_file():
    _saved_dexter = json.loads(DEXTER_FILE.read_text(encoding="utf-8"))
    if isinstance(_saved_dexter, dict):
        DEXTER.update(_saved_dexter)
        DEXTER.update(busy=False, cancel=False, phase="saved results loaded")
        if DEXTER.get("current") < DEXTER.get("total", 5) and DEXTER.get("results"):
            DEXTER["error"] = "The server restarted before the experiment batch finished."
# follow TradingView: delay "none" while tuning, so the same settings always give the same number (Export adds the random-delay result)
FOLLOW = {"on": False, "delay": "none", "connected": False, "err": None, "at": None, "tv": None, "key": None, "changed_at": 0,
          "pending": None, "msg": ""}
LOCK = threading.Lock()
EXPORT_LOCK = threading.Lock()
EXPORT_JOB = {"id": None, "busy": False, "phase": "", "error": None, "result": None, "started": None}


LOG = HERE / "server.log"


def log(msg):
    """pythonw has no console: everything goes to server.log as well."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if sys.stdout:
        try:
            print(line, flush=True)
        except UnicodeEncodeError:                           # a cp1252 console and a name with an emoji (the Research page's 📄 saves)
            print(line.encode("ascii", "replace").decode(), flush=True)


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


# ---------- the EA's inputs, straight from its source (groups, defaults, comments) ----------
UHV_SAAD_DEFAULTS = {"InpBandsB": "1" * 21, "InpBandsS": "1" * 21}   # TurtleTVUHV: range boxes start all ticked (ranges off) for UHV


def ea_inputs():
    src = (ROOT / "mt5" / f"{EA}.mq5").read_text(encoding="utf-8", errors="ignore")
    out, group = [], "General"
    for line in src.splitlines():
        g = re.match(r"^//---\s*(.+)$", line)
        if g:
            group = re.sub(r"\(.*$", "", g.group(1)).strip(" -·") or group
            continue
        if re.match(r"^// v1\.24", line):                  # v1.24+ inputs sit under plain comments, not //--- headings
            group = "ADX · volatility gates (v1.24)"
        elif re.match(r"^// chart-test", line):
            group = "Range boxes · stand aside · exit (v1.25 - v1.27)"
        m = re.match(r'^input\s+(\w+)\s+(\w+)\s*=\s*([^;]+);\s*(?://\s*(.*))?$', line)
        if not m or m.group(1) == "color" or m.group(2) in HIDE:
            continue
        typ, name, dflt, com = m.group(1), m.group(2), m.group(3).strip().strip('"'), (m.group(4) or "").strip()
        com = re.sub(r"^" + name + r"\s*[—-]\s*", "", com)
        out.append({"name": name, "type": typ, "default": UHV_SAAD_DEFAULTS.get(name, dflt), "comment": com, "group": group})
    import uhv_engine                                       # TurtleTVUHV: the UHV Diamond settings come first; every Saad setting stays below them
    uhv = [{"name": k, "type": "bool" if v[0] in ("true", "false") else "double", "default": v[0], "comment": v[1], "group": "UHV Diamond (v1.27 rules, PrimeXBT)"}
           for k, v in uhv_engine.UHV_DEFAULTS.items()]
    uhv += [{"name": k, "type": "double", "default": f"{uhv_engine.DET_DEFAULT[k]:g}", "comment": c + " - a new value finds every setup again (about a minute, once)",
             "group": "UHV detection (camel humps, UHV + breakout shape)"} for k, (_, c) in uhv_engine.DET.items()]
    import uhv_ttd                                          # Zee 2026-11-05: the Turtle Trader Desk indicator's settings (act only with InpTtdOn)
    uhv += [{"name": k, "type": "bool" if v[1] == "bool" else "double", "default": v[0], "comment": v[2], "group": "Turtle Trader Desk (indicator)"}
            for k, v in uhv_ttd.TTD.items()]
    ver = re.search(r'#property version\s+"([^"]+)"', src)
    return {"ea": EA, "version": ver.group(1) if ver else "?", "inputs": uhv + out}


# ---------- TradingView: the indicator's settings -> the EA's inputs ----------
def tv_settings():
    st, settings, sets, _ = CMP.read_settings()
    dfl = axi_rig.ea_defaults(EA)
    s = {k: v for k, v in sets.items() if k in dfl and k not in HIDE}
    tp = settings.get("tpMode", "")
    s["InpExitMode"] = {"Next EMA beyond the entry (touch, close all)": "1", "Candle closes back across the slow EMA (close all)": "2"}.get(tp, "0")
    rp = str(settings.get("rpOff", ""))
    s["InpBandOff"] = "1" if rp.startswith("Stand aside") else "0"
    notes = []
    if not tp.startswith(("Normal", "Next EMA", "Candle closes back")):
        notes.append(f"TP1 METHOD '{tp}' - the EA has no such exit; MT5 runs the normal TP1")
    if not str(settings.get("xPick", "Off")).startswith("Off"):
        notes.append(f"EXIT preset '{settings.get('xPick')}' - not in the EA")
    if rp.startswith("Pause"):
        notes.append("Range boxes 'Pause N candles' - the EA skips the trade instead (no pause)")
    for pv, what in (("reOn", "Re-entry after a stop"), ("coolN", "Cool-down after a trade"), ("pkGap", "Lock gap"), ("adRunN", "Cut after N candles in loss")):
        if settings.get(pv):
            notes.append(f"{what} is ON on the chart - not in the EA")
    for pv, off, what in CMP.NOT_IN_EA:
        if settings.get(pv, off) != off:
            notes.append(f"{what} is ON on the chart - not in the EA")
    if str(st.get("res")) != "15":
        notes.append(f"the chart is on {st.get('res')} min - Turtle TV runs the EA on 15-min candles")
    info = {"symbol": st.get("symbol"), "res": st.get("res"), "sets": s, "notes": notes, "at": datetime.now().strftime("%H:%M:%S"), "raw": settings}
    doc = settings_doc(s, notes, raw=settings, chart={"symbol": st.get("symbol"), "timeframe": st.get("res"), "read_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    f = SETTINGS / "tradingview_latest.json"
    old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if old.get("tradingview") != settings:
        f.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return info


def settings_doc(inputs, notes=None, raw=None, chart=None, result=None):
    """The settings hand-off (Zee 2026-10-20: "make TV generate a json turtle can read, and turtle export a json the mt5 EA maker can read"):
    one JSON for TradingView -> Turtle TV -> MT5. ea_inputs = every input of the EA (defaults filled in); tradingview = the chart's own
    settings by Pine variable (to put them back on the chart); mt5_result = what the Strategy Tester made with them.
    make_ea_from_settings.py turns it into an EA whose DEFAULTS are these settings."""
    info = ea_inputs()
    dfl = axi_rig.ea_defaults(LIVE_EA)
    full = {name: str(inputs.get(name, default)) for name, default in dfl.items()}
    return {"format": "turtle-settings/1", "written_by": "Turtle TV", "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ea": LIVE_EA, "ea_version": info["version"], "ea_inputs": full,
            "changed_from_defaults": {k: v for k, v in full.items() if not same(v, dfl.get(k))},
            "chart_only": notes or [], "chart": chart, "tradingview": raw, "mt5_result": result}


def run_matching(sets, delay, period=PERIOD):
    """The newest run that already has exactly these settings (and delay) - no need to run MT5 again. Every input is compared: the ones
    not in `sets` must be at the EA's defaults (a run with an extra change from the settings form is not a match)."""
    dfl = axi_rig.ea_defaults(EA)
    for p in sorted(RUNS.glob("r*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        if d.get("delay") == delay and d.get("period", PERIOD) == period and all(same(v, sets.get(k, dfl.get(k, v))) for k, v in d["inputs"].items()):
            return d["id"]
    return None


def follow_loop():
    while True:
        time.sleep(3)
        if not FOLLOW["on"]:
            continue
        try:
            info = tv_settings()
            FOLLOW.update(connected=True, err=None, at=info["at"], tv=info)
        except Exception as e:                              # noqa: BLE001
            FOLLOW.update(connected=False, err=str(e)[:300])
            continue
        key = json.dumps(info["sets"], sort_keys=True)
        if key != FOLLOW["key"]:
            first = FOLLOW["key"] is None
            FOLLOW.update(key=key, changed_at=time.time(), pending=info)
            if not first and STATE["busy"] and STATE.get("source") == "tradingview":
                STATE["cancel"] = True                       # a newer chart setting: drop the run that is going
                FOLLOW["msg"] = "TradingView changed again - the run in progress is dropped"
        p = FOLLOW["pending"]
        if p and not STATE["busy"] and time.time() - FOLLOW["changed_at"] >= 5:
            FOLLOW["pending"] = None
            have = run_matching(p["sets"], FOLLOW["delay"], PERIOD)
            if have:
                FOLLOW["msg"] = f"TradingView settings = run {have} (already in MT5)"
                STATE["last"] = have
                continue
            rid, err = start_run({"sets": p["sets"], "delay": FOLLOW["delay"], "label": f"TradingView {p['at']}", "notes": p["notes"], "tv_raw": p["raw"],
                                  "tv_chart": {"symbol": p["symbol"], "timeframe": p["res"], "read_at": p["at"]}}, source="tradingview")
            FOLLOW["msg"] = f"TradingView change -> MT5 run {rid}" if rid else (err or "")


# ---------- time: Blueberry server = New York + 7 h (UTC+3 in US summer time, else UTC+2) ----------
def _nth_sunday(y, m, n):
    d = datetime(y, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def server_to_utc(dt):
    return dt                                                  # TurtleTVUHV: PrimeXBT's server clock is UTC (rollover spread spike at 21:00 = 17:00 New York)


def _blueberry_server_to_utc(dt):
    a = _nth_sunday(dt.year, 3, 2) + timedelta(hours=9)      # 02:00 New York = 09:00 server
    b = _nth_sunday(dt.year, 11, 1) + timedelta(hours=9)
    return dt - timedelta(hours=3 if a <= dt < b else 2)


def ts(s):
    s = s.strip()
    fmt = "%Y.%m.%d %H:%M:%S" if s.count(":") == 2 else "%Y.%m.%d %H:%M"
    u = server_to_utc(datetime.strptime(s, fmt))
    return int((u - datetime(1970, 1, 1)).total_seconds())


def num(x):
    try:
        return float(x)
    except ValueError:
        return None


# ---------- one run: MT5 Strategy Tester -> export -> chart data ----------
def rig_busy():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{axi_rig._R(RIG)}\\*' }}).Count"],
                       capture_output=True, text=True, creationflags=0x08000000)
    return (r.stdout.strip() or "0") != "0"


def build(rid, meta, rep):
    bars_f, ev_f = COMMON / f"saadview_{rid}_bars.csv", COMMON / f"saadview_{rid}_events.csv"
    B = {k: [] for k in ("t", "o", "h", "l", "c", "ef", "es", "adx", "atr")}
    seen = set()
    for line in bars_f.read_text(encoding="ascii", errors="ignore").splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 9:
            continue
        t = ts(f[0])
        if t in seen:
            continue
        seen.add(t)
        for k, v in zip(("t", "o", "h", "l", "c", "ef", "es", "adx", "atr"), [t] + [num(x) for x in f[1:9]]):
            B[k].append(v)
    order = sorted(range(len(B["t"])), key=lambda i: B["t"][i])
    B = {k: [v[i] for i in order] for k, v in B.items()}
    E = []
    for line in ev_f.read_text(encoding="ascii", errors="ignore").splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 10:
            continue
        E.append({"type": f[0], "t": ts(f[1]), "side": int(f[2]), "price": num(f[3]), "sl": num(f[4]), "v1": num(f[5]), "v2": num(f[6]),
                  "ref": ts(f[7]) if f[7].strip() else None, "num": int(f[8]), "text": f[9]})
    data = dict(meta, bars=B, events=E, report=rep)
    (RUNS / f"{rid}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    for p in (bars_f, ev_f):
        p.unlink(missing_ok=True)


def run_job(rid, sets, frm, to, delay, label, notes, period=PERIOD, symbol=SYMBOL, deposit=DEPOSIT):
    try:
        STATE.update(phase="waiting for the MT5 rig to be free")
        for _ in range(600):
            if not rig_busy() or STATE["cancel"]:
                break
            time.sleep(2)
        if STATE["cancel"]:
            raise RuntimeError("cancelled")
        STATE.update(phase="compiling the EA in MT5")
        axi_rig.kill_rig(RIG)
        axi_rig.compile_ea(EA, rig=RIG)
        STATE.update(phase="MT5 Strategy Tester on Blueberry real ticks")
        defaults = axi_rig.ea_defaults(EA)
        run_sets = dict(sets, InpLogCsv="false", InpExport="true", InpExportTag=rid)
        r = {}
        for attempt in range(3):
            r = axi_rig.run(EA, symbol, period, run_sets, frm=frm, to=to, deposit=deposit, rig=RIG, tag=f"view_{rid}",
                            exec_mode=0 if delay == "none" else -1, cancel=lambda: STATE["cancel"])
            if r.get("error") not in ("authorization failed", "no report"):
                break
            axi_rig.kill_rig(RIG); time.sleep(5)
        if r.get("error"):
            raise RuntimeError("cancelled" if r.get("error") == "cancelled" else f"MT5: {r.get('error')}")
        STATE.update(phase="reading the EA's export")
        rig_root = Path(axi_rig.RIGS.get(RIG, RIG))
        tester_report = rig_root / "reports" / f"view_{rid}.htm"
        if not tester_report.is_file():
            raise RuntimeError(f"MT5 report is missing: {tester_report}")
        (RUNS / f"{rid}.htm").write_bytes(tester_report.read_bytes())
        rep = {k: r.get(k) for k in ("net", "pf", "trades", "dd", "quality", "months", "trade_stats", "day_stats")}
        info = ea_inputs()
        meta = {"id": rid, "label": label, "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "ea": EA, "version": info["version"],
                "symbol": symbol, "period": period, "from": frm, "to": to, "delay": delay, "deposit": deposit, "changed": sets,
                "notes": notes or [], "source": STATE.get("source"), "tradingview": STATE.get("tv_raw"), "chart": STATE.get("tv_chart"),
                "inputs": {i["name"]: sets.get(i["name"], defaults.get(i["name"], i["default"])) for i in info["inputs"]}}
        build(rid, meta, rep)
        STATE.update(last=rid, phase="done")
        log(f"run {rid} done: net {rep.get('net')} PF {rep.get('pf')} trades {rep.get('trades')}")
    except (Exception, SystemExit) as e:                    # noqa: BLE001  (a failed compile raises SystemExit: show it, not a silent stop)
        if str(e) != "cancelled":
            log("run " + rid + " failed:\n" + traceback.format_exc())
        STATE.update(error=None if str(e) == "cancelled" else str(e), phase="dropped (a newer TradingView change)" if str(e) == "cancelled" else "failed")
        for p in (COMMON / f"saadview_{rid}_bars.csv", COMMON / f"saadview_{rid}_events.csv"):
            p.unlink(missing_ok=True)
    finally:
        STATE.update(busy=False, cancel=False)


def start_run(body, source="page"):
    with LOCK:
        if STATE["busy"]:
            return None, "a run is already going"
        if EXPORT_JOB["busy"]:
            return None, "EA export is compiling and testing on the MT5 rig"
        if DEXTER["busy"] and source != "dexter":
            return None, "Dexter's Lab is running a controlled MT5 comparison"
        period = body.get("period") if body.get("period") in ("M1", "M5", "M15") else PERIOD
        symbol = str(body.get("symbol") or SYMBOL).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", symbol):
            return None, "invalid MT5 symbol"
        try:
            deposit = float(body.get("deposit", DEPOSIT))
        except (TypeError, ValueError):
            return None, "invalid MT5 deposit"
        if not math.isfinite(deposit) or deposit <= 0:
            return None, "MT5 deposit must be a positive number"
        delay = body.get("delay") or "random"
        if delay not in ("none", "random"):
            return None, "delay must be 'none' or 'random'"
        frm, to = str(body.get("from") or FROM), str(body.get("to") or TO)
        try:
            if datetime.strptime(frm, "%Y.%m.%d") >= datetime.strptime(to, "%Y.%m.%d"):
                return None, "MT5 test start date must be earlier than its end date"
        except ValueError:
            return None, "MT5 dates must use YYYY.MM.DD"
        rid = "r" + datetime.now().strftime("%Y%m%d_%H%M%S")
        defaults = axi_rig.ea_defaults(EA)
        sets = {k: str(v) for k, v in (body.get("sets") or {}).items() if k not in HIDE and not same(v, defaults.get(k))}
        label = (body.get("label") or "").strip() or ("v" + ea_inputs()["version"] + (" defaults" if not sets else " + " + ", ".join(f"{k[3:]} {v}" for k, v in sets.items())))
        STATE.update(busy=True, id=rid, label=label, started=time.time(), phase="starting", error=None, cancel=False, source=source,
                     tv_raw=body.get("tv_raw"), tv_chart=body.get("tv_chart"))
        if period != PERIOD:
            label = "M1 · " + label
            STATE["label"] = label
        threading.Thread(target=run_job, args=(rid, sets, frm, to, delay, label, body.get("notes"), period, symbol, deposit), daemon=True).start()
        return rid, None


def _persist_dexter():
    with DEXTER_LOCK:
        record = json.loads(json.dumps(DEXTER))
    temporary = DEXTER_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
    temporary.replace(DEXTER_FILE)


def dexter_status():
    with DEXTER_LOCK:
        state = json.loads(json.dumps(DEXTER))
    reference_path = RUNS / f"{DEXTER_REFERENCE_ID}.json"
    if reference_path.is_file():
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        state["reference"] = {key: reference.get(key) for key in ("id", "label", "created", "symbol", "period", "from", "to", "delay", "deposit", "version")}
        state["reference"]["report"] = reference.get("report", {})
    else:
        state["reference"] = None
    return state


def dexter_start(body):
    bounds = {
        "risk_pct": (0.05, 5.0),
        "pin_buffer": (0.0, 10.0),
        "atr_mult": (0.1, 5.0),
        "decay_bars": (1, 48),
        "decay_r": (-2.0, 1.0),
        "tight_stop": (2.0, 40.0),
        "time_bars": (1, 48),
    }
    requested = body.get("settings") or {}
    settings = {}
    for name, (low, high) in bounds.items():
        try:
            value = float(requested.get(name, DEXTER["settings"].get(name, (low + high) / 2)))
        except (TypeError, ValueError):
            return {"error": f"{name} must be numeric"}
        if not math.isfinite(value) or value < low or value > high:
            return {"error": f"{name} must be between {low} and {high}"}
        settings[name] = int(value) if name in ("decay_bars", "time_bars") else value

    reference_path = RUNS / f"{DEXTER_REFERENCE_ID}.json"
    if not reference_path.is_file():
        return {"error": f"MT5 reference run {DEXTER_REFERENCE_ID} is unavailable"}
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if not reference.get("inputs") or not reference.get("report"):
        return {"error": f"MT5 reference run {DEXTER_REFERENCE_ID} has no complete inputs or result"}
    with LOCK:
        if STATE["busy"]:
            return {"error": "an MT5 Strategy Tester run is already in progress"}
        if EXPORT_JOB["busy"]:
            return {"error": "EA export is compiling and testing on the MT5 rig"}
        with DEXTER_LOCK:
            if DEXTER["busy"]:
                return {"error": "Dexter's Lab comparison is already running"}
            DEXTER.update(busy=True, cancel=False, phase="starting controlled MT5 comparison", current=0, total=9,
                          reference_id=DEXTER_REFERENCE_ID, settings=settings, results=[], error=None, started=datetime.now().isoformat(timespec="seconds"))
    _persist_dexter()
    threading.Thread(target=_dexter_worker, args=(reference, settings), daemon=True).start()
    return {"ok": True, "reference_id": DEXTER_REFERENCE_ID}


def _dexter_worker(reference, settings):
    variants = [
        ("baseline", "Baseline", "Current reference settings; experiments disabled.", {}),
        ("risk-sizing", "A · ATR-based risk sizing", "Use OrderCalcProfit sizing at the configured equity-risk percentage; preserve the reference stop and exits.",
         {"InpDexRiskSizing": "true", "InpDexRiskPct": f"{settings['risk_pct']:g}", "InpDexStopMethod": "0"}),
        ("pinbar-stop", "B · Stop beyond signal candle", "Use the signal candle low/high plus the price buffer, sized to the same risk budget.",
         {"InpDexRiskSizing": "true", "InpDexRiskPct": f"{settings['risk_pct']:g}", "InpDexStopMethod": "1",
          "InpDexPinBuffer": f"{settings['pin_buffer']:g}"}),
        ("atr-stop", "C · M15 ATR stop", "Use the last closed M15 ATR(14) × multiplier, sized to the same risk budget.",
         {"InpDexRiskSizing": "true", "InpDexRiskPct": f"{settings['risk_pct']:g}", "InpDexStopMethod": "2",
          "InpDexAtrMult": f"{settings['atr_mult']:g}"}),
        ("time-decay", "D · Risk sizing + time-decay stop", "Combine risk sizing with the existing stop-decay rule after a losing trade stalls.",
         {"InpDexRiskSizing": "true", "InpDexRiskPct": f"{settings['risk_pct']:g}", "InpDexStopMethod": "0",
          "InpXDecayBars": str(settings["decay_bars"]), "InpXDecayR": f"{settings['decay_r']:g}"}),
        # Claude's experiments (dexter_mae.py on the reference's own MT5 trades: winners close in a median 3 minutes and
        # dip a median $3; losers drag a median 105 minutes to the full $25 stop - time and distance separate them)
        ("tight-stop", "E · Tight stop (winners' 90-95% dip)", "Stop at the distance 90-95% of winners never reach; fixed lots, exits unchanged.",
         {"InpSlMode": "2", "InpSlUsd": f"{settings['tight_stop']:g}"}),
        ("time-stop", "F · Time stop", "Close a trade still open after N candles: winners resolve in minutes, losers drag.",
         {"InpXMaxBars": str(settings["time_bars"])}),
        ("tight-time", "G · Tight stop + time stop", "E and F together: caps the worst loss and cuts the slow losers.",
         {"InpSlMode": "2", "InpSlUsd": f"{settings['tight_stop']:g}", "InpXMaxBars": str(settings["time_bars"])}),
        ("tight-time-risk", "H · G + risk sizing", "G with Experiment A's OrderCalcProfit sizing at the same risk percentage.",
         {"InpSlMode": "2", "InpSlUsd": f"{settings['tight_stop']:g}", "InpXMaxBars": str(settings["time_bars"]),
          "InpDexRiskSizing": "true", "InpDexRiskPct": f"{settings['risk_pct']:g}", "InpDexStopMethod": "0"}),
    ]
    with DEXTER_LOCK:
        DEXTER["total"] = len(variants)
    try:
        for index, (key, title, purpose, overrides) in enumerate(variants, 1):
            with DEXTER_LOCK:
                if DEXTER["cancel"]:
                    break
                DEXTER.update(current=index, phase=f"starting {title}")
                DEXTER["results"].append({"key": key, "title": title, "purpose": purpose, "status": "running", "run_id": None})
            _persist_dexter()
            inputs = dict(reference["inputs"])
            inputs.update(overrides)
            run_id, error = start_run({
                "sets": inputs,
                "label": f"Dexter {title} · {DEXTER_REFERENCE_ID}",
                "from": reference.get("from") or FROM,
                "to": reference.get("to") or TO,
                "period": reference.get("period") or PERIOD,
                "symbol": reference.get("symbol") or SYMBOL,
                "deposit": reference.get("deposit") or DEPOSIT,
                "delay": reference.get("delay") or "none",
            }, source="dexter")
            if error:
                with DEXTER_LOCK:
                    DEXTER["results"][-1].update(status="failed", error=error)
                    DEXTER["error"] = error
                break
            with DEXTER_LOCK:
                DEXTER["results"][-1]["run_id"] = run_id
                DEXTER["phase"] = f"MT5 Strategy Tester: {title}"
            _persist_dexter()

            while True:
                with LOCK:
                    running = STATE["busy"] and STATE["id"] == run_id
                    cancelled = STATE["cancel"] or DEXTER["cancel"]
                    run_error = STATE["error"] if STATE["id"] == run_id else None
                if not running:
                    break
                if cancelled:
                    with LOCK:
                        if STATE["id"] == run_id:
                            STATE["cancel"] = True
                time.sleep(1)

            if run_error:
                with DEXTER_LOCK:
                    DEXTER["results"][-1].update(status="failed", error=run_error)
                    DEXTER["error"] = run_error
                break
            run_path = RUNS / f"{run_id}.json"
            if not run_path.is_file():
                error = f"MT5 completed without saving run {run_id}"
                with DEXTER_LOCK:
                    DEXTER["results"][-1].update(status="failed", error=error)
                    DEXTER["error"] = error
                break
            saved = json.loads(run_path.read_text(encoding="utf-8"))
            report = saved.get("report") or {}
            trade_stats = report.get("trade_stats") or {}
            result = {
                "key": key, "title": title, "purpose": purpose, "status": "complete", "run_id": run_id,
                "net": report.get("net"), "pf": report.get("pf"), "drawdown": report.get("dd"),
                "largest_loss": trade_stats.get("largest_loss"), "trades": report.get("trades"),
                "wr": trade_stats.get("wr"), "quality": report.get("quality"), "report_url": f"/api/mt5_report?id={run_id}",
                "settings": overrides,
            }
            with DEXTER_LOCK:
                DEXTER["results"][-1] = result
                DEXTER["phase"] = f"finished {title}"
            _persist_dexter()
        with DEXTER_LOCK:
            DEXTER.update(busy=False, cancel=False, phase="comparison stopped" if DEXTER["cancel"] else "comparison complete")
    except Exception as error:
        with DEXTER_LOCK:
            DEXTER.update(busy=False, cancel=False, phase="comparison failed", error=str(error))
        log("Dexter's Lab comparison failed:\n" + traceback.format_exc())
    finally:
        _persist_dexter()


# ---- Dexter's Lab on the live setting: any experiment verified in MT5 (rig data: 2026), one after another
DEXLAB_MT5_FILE = RUNS / "dexlab_mt5.json"
DEXLAB_MT5 = {"busy": False, "phase": "", "current": 0, "total": 0, "queue": [], "results": [], "error": None, "cancel": False}
if DEXLAB_MT5_FILE.is_file():
    try:
        DEXLAB_MT5["results"] = json.loads(DEXLAB_MT5_FILE.read_text(encoding="utf-8")).get("results", [])
    except Exception:                                            # noqa: BLE001
        pass


def _dexlab_fp(inputs, ds):
    import hashlib
    return hashlib.sha1(json.dumps([diff_from_defaults(inputs), ds], sort_keys=True).encode()).hexdigest()[:16]


def diff_from_defaults(inputs):
    dfl = axi_rig.ea_defaults(EA)
    return {k: str(v) for k, v in inputs.items() if str(dfl.get(k)) != str(v)}


def dexlab_mt5_start(body):
    inputs = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") or "year1"
    items = [x for x in (body.get("items") or []) if isinstance(x, dict) and x.get("key")][:20]
    if not items:
        return {"error": "nothing to verify"}
    with LOCK:
        if STATE["busy"] or DEXTER["busy"] or DEXLAB_MT5["busy"]:
            return {"error": "the MT5 rig is busy - try again when the current test finishes"}
        DEXLAB_MT5.update(busy=True, phase="starting", current=0, total=len(items), queue=[x["key"] for x in items], error=None, cancel=False)
    threading.Thread(target=_dexlab_mt5_worker, args=(inputs, ds, items), daemon=True).start()
    return {"ok": True}


def _dexlab_mt5_worker(inputs, ds, items):
    period = "M1" if ds in ("year1", "m1x") else "M5" if ds == "m5x" else "M15"
    fp = _dexlab_fp(inputs, ds)
    try:
        for i, it in enumerate(items, 1):
            if DEXLAB_MT5["cancel"]:
                break
            title = str(it.get("title") or it["key"])
            DEXLAB_MT5.update(current=i, phase=f"MT5 Strategy Tester: {title}")
            sets = {k: str(v) for k, v in (it.get("sets") or {}).items()}
            run_id, error = start_run({"sets": {**inputs, **sets}, "label": f"Dexter's Lab · {title}", "from": FROM, "to": TO, "period": period,
                                       "symbol": SYMBOL, "deposit": DEPOSIT, "delay": str(it.get("delay") or "none")}, source="dexter")
            rec = {"fp": fp, "key": it["key"], "title": title, "sets": sets, "period": period, "delay": str(it.get("delay") or "none"), "status": "failed", "run_id": run_id,
                   "when": datetime.now().isoformat(timespec="seconds")}
            if error:
                rec["error"] = error
            else:
                while True:
                    with LOCK:
                        running = STATE["busy"] and STATE["id"] == run_id
                        run_error = STATE["error"] if STATE["id"] == run_id else None
                    if not running:
                        break
                    if DEXLAB_MT5["cancel"]:
                        with LOCK:
                            if STATE["id"] == run_id:
                                STATE["cancel"] = True
                    time.sleep(1)
                path = RUNS / f"{run_id}.json"
                if run_error:
                    rec["error"] = run_error
                elif path.is_file():
                    rep = (json.loads(path.read_text(encoding="utf-8")).get("report") or {})
                    ts = rep.get("trade_stats") or {}
                    rec.update(status="complete", net=rep.get("net"), pf=rep.get("pf"), dd=rep.get("dd"), trades=rep.get("trades"),
                               largest_loss=ts.get("largest_loss"), avg_win=ts.get("avg_win"), avg_loss=ts.get("avg_loss"))
                else:
                    rec["error"] = f"MT5 finished without saving run {run_id}"
            DEXLAB_MT5["results"] = [r for r in DEXLAB_MT5["results"] if not (r["fp"] == fp and r["key"] == it["key"])] + [rec]
            DEXLAB_MT5_FILE.write_text(json.dumps({"results": DEXLAB_MT5["results"][-400:]}, indent=1), encoding="utf-8")
    except Exception as ex:                                      # noqa: BLE001
        DEXLAB_MT5["error"] = str(ex)
        log("Dexter's Lab MT5 verification failed: " + traceback.format_exc())
    finally:
        DEXLAB_MT5.update(busy=False, phase="done")


def dexlab_mt5_status(body):
    inputs = full_inputs(body.get("inputs") or {})
    fp = _dexlab_fp(inputs, body.get("ds") or "year1")
    st = {k: v for k, v in DEXLAB_MT5.items() if k != "results"}
    st["results"] = [r for r in DEXLAB_MT5["results"] if r["fp"] == fp]
    return st


def dexter_stop():
    with DEXTER_LOCK:
        if not DEXTER["busy"]:
            return {"error": "Dexter's Lab is not running"}
        DEXTER["cancel"] = True
        DEXTER["phase"] = "stopping after the current MT5 test"
    with LOCK:
        if STATE["source"] == "dexter":
            STATE["cancel"] = True
    _persist_dexter()
    return {"ok": True}


_RUN_WR = {}


def mt5_report_path(rid):
    saved = RUNS / f"{rid}.htm"
    if saved.is_file():
        return saved
    legacy = Path(axi_rig.RIGS.get(RIG, RIG)) / "reports" / f"view_{rid}.htm"
    return legacy if legacy.is_file() else None


def run_wr(p, d):                                           # MT5's win rate: per trade, its exits (partials included) summed, cached per file version
    k = (p.name, p.stat().st_mtime)
    if k not in _RUN_WR:
        pnl = {}
        for e in d.get("events") or []:
            if e.get("type") == "exit":
                pnl[e.get("num")] = pnl.get(e.get("num"), 0) + float(e.get("v1") or 0)
        v = list(pnl.values()); w = [x for x in v if x > 0]; l = [x for x in v if x <= 0]
        aw, al = (sum(w) / len(w) if w else 0), (sum(l) / len(l) if l else 0)
        _RUN_WR[k] = {"wr": round(100 * len(w) / len(v), 1), "avg_win": round(aw), "avg_loss": round(al), "worst": round(min(v)),
                      "be_wr": round(100 * -al / (aw - al), 1) if aw - al else None} if v else {"wr": None}
    return _RUN_WR[k]


def list_runs():
    out = []
    with EXPORT_LOCK:
        active_export = dict(EXPORT_JOB)
    if active_export.get("started"):
        active_export["seconds"] = round(time.time() - active_export["started"], 1)
    for p in sorted(RUNS.glob("r*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            candidate = candidate_metadata(d["id"], d)
            export_state = None
            if active_export.get("id") == d["id"]:
                export_state = {key: active_export.get(key) for key in ("id", "busy", "phase", "error", "candidate", "seconds")}
            out.append({k: d.get(k) for k in ("id", "label", "created", "from", "to", "delay", "period", "changed", "source")} |
                       {"has_report": mt5_report_path(d["id"]) is not None,
                        "has_candidate": bool(candidate and candidate["available"]), "candidate": candidate,
                        "export_state": export_state} |
                       {"net": d["report"].get("net"), "pf": d["report"].get("pf"), "trades": d["report"].get("trades"), "dd": d["report"].get("dd")} | run_wr(p, d))
        except Exception:                                   # noqa: BLE001
            continue
    return out


# ---------- Export to MT5: the run's settings as a preset for the real EA (+ a random-delay result) ----------
def _export_status_update(rid, **updates):
    with EXPORT_LOCK:
        if EXPORT_JOB["id"] == rid:
            EXPORT_JOB.update(updates)


def _export_candidate(rid, d, doc, settings_path, candidate, text):
    try:
        _export_status_update(rid, phase="generating a separate EA from all production inputs")
        generated = subprocess.run(
            [sys.executable, str(EA_MAKER), str(settings_path), "--out", candidate],
            capture_output=True, text=True, timeout=120, creationflags=axi_rig.NO_WINDOW,
        )
        if generated.returncode:
            raise RuntimeError((generated.stderr or generated.stdout or "EA generation failed").strip()[-1200:])
        candidate_src = ROOT / "mt5" / f"{candidate}.mq5"
        if not candidate_src.is_file():
            raise RuntimeError(f"EA generator did not create {candidate_src}")

        _export_status_update(rid, phase="waiting for the isolated MT5 test rig")
        for _ in range(600):
            if not rig_busy():
                break
            time.sleep(2)
        else:
            raise RuntimeError("MT5 test rig stayed busy for 20 minutes")

        _export_status_update(rid, phase="compiling the candidate EA in MetaEditor")
        compile_result = axi_rig.compile_ea(candidate, rig=RIG)
        if compile_result["warnings"]:
            raise RuntimeError(f"MetaEditor reported {compile_result['warnings']} warning(s); see {compile_result['log']}")
        rig_root = Path(axi_rig.RIGS.get(RIG, RIG))
        candidate_ex5 = rig_root / "MQL5" / "Experts" / f"{candidate}.ex5"
        if not candidate_ex5.is_file():
            raise RuntimeError(f"MetaEditor did not create {candidate_ex5}")
        compiled_hash = hashlib.sha256(candidate_ex5.read_bytes()).hexdigest()
        source_hash = hashlib.sha256(candidate_src.read_bytes()).hexdigest()

        _export_status_update(rid, phase="testing the compiled candidate in MT5 Strategy Tester")
        ea_defaults = axi_rig.ea_defaults(candidate)
        test_inputs = dict(doc["ea_inputs"])
        for key, value in (("InpExport", "false"), ("InpLogCsv", "false")):
            if key in ea_defaults:
                test_inputs[key] = value
        tested = axi_rig.run(
            candidate, d["symbol"], d.get("period", PERIOD), test_inputs,
            frm=d["from"], to=d["to"], deposit=d["deposit"],
            exec_mode=0 if d.get("delay") == "none" else -1,
            tag=f"export_{rid}", model=4, rig=RIG, timeout=21600,
        )
        if tested.get("error"):
            raise RuntimeError(f"MT5 Strategy Tester: {tested['error']}")
        report_src = rig_root / "reports" / f"export_{rid}.htm"
        if not report_src.is_file() or report_src.stat().st_size == 0:
            raise RuntimeError(f"MT5 Strategy Tester report is missing: {report_src}")
        report_dst = RUNS / f"{rid}_candidate.htm"
        report_dst.write_bytes(report_src.read_bytes())

        _export_status_update(rid, phase="installing the compiled EA and preset in MT5 terminals")
        installed, install_errors = [], []
        for terminal in TERMINALS.iterdir():
            experts = terminal / "MQL5" / "Experts"
            if not ((experts / f"{LIVE_EA}.ex5").exists() or (experts / f"{LIVE_EA}.mq5").exists()):
                continue
            try:
                experts.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate_src, experts / candidate_src.name)
                shutil.copy2(candidate_ex5, experts / candidate_ex5.name)
                if hashlib.sha256((experts / candidate_ex5.name).read_bytes()).hexdigest() != compiled_hash:
                    raise OSError(f"compiled EA copy verification failed in {terminal.name}")
                (terminal / "MQL5" / "Presets").mkdir(parents=True, exist_ok=True)
                (terminal / "MQL5" / "Presets" / f"{candidate}.set").write_text(text, encoding="utf-16")
                installed.append(str(experts / candidate_ex5.name))
            except OSError as error:
                install_errors.append(f"{terminal.name}: {error}")
        if not installed:
            detail = "; ".join(install_errors) or "no MT5 terminal with the base EA was found"
            raise RuntimeError(f"Candidate compiled and tested, but could not be installed in an attachable terminal: {detail}")

        tester = {key: tested.get(key) for key in ("net", "pf", "trades", "wr", "dd", "quality")}
        tester["avg_win"] = (tested.get("trade_stats") or {}).get("avg_win")
        tester["avg_loss"] = (tested.get("trade_stats") or {}).get("avg_loss")
        version = re.search(r'#property\s+version\s+"([^"]+)"', candidate_src.read_text(encoding="utf-8", errors="replace"))
        compiled_at = datetime.fromtimestamp(candidate_ex5.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        metadata = {
            "run_id": rid,
            "name": candidate,
            "version": version.group(1) if version else "unknown",
            "compiled_at": compiled_at,
            "source_path": str(candidate_src),
            "source_sha256": source_hash,
            "compiled_paths": installed,
            "compiled_sha256": compiled_hash,
            "compiler": {key: compile_result[key] for key in ("errors", "warnings", "process_exit_code", "log")},
            "preset_paths": [str(Path(path).parent.parent / "Presets" / f"{candidate}.set") for path in installed],
            "report_path": str(report_dst),
            "report_url": f"/api/export_report?id={rid}",
            "tester": tester,
            "tester_symbol": d.get("symbol"),
            "tester_period": d.get("period", PERIOD),
            "tester_from": d.get("from"),
            "tester_to": d.get("to"),
            "tester_deposit": d.get("deposit"),
            "settings_changed": d.get("changed") or {},
            "available": True,
        }
        _write_candidate_manifest(rid, metadata)
        _attach_candidate_to_saved(metadata)
        result = {"candidate": candidate, "compiled": True, "tested": True, "tester": tester,
                  "report": f"/api/export_report?id={rid}", "installed": installed, "install_errors": install_errors}
        _export_status_update(rid, busy=False, phase="ready to attach", result=result, error=None)

        if d.get("delay") != "random":
            have = run_matching(doc["ea_inputs"], "random", d.get("period", PERIOD))
            if have:
                result["random_run"] = have
                result["random_existing"] = True
            else:
                random_id, error = start_run(
                    {"sets": doc["ea_inputs"], "delay": "random", "period": d.get("period", PERIOD),
                     "from": d["from"], "to": d["to"], "label": f"Export: {d['label']}", "notes": d.get("notes")},
                    source="export",
                )
                if error:
                    result["random_error"] = error
                else:
                    result["random_run"] = random_id
            _export_status_update(rid, result=result)
    except (Exception, SystemExit) as error:
        log(f"export {rid} failed:\n{traceback.format_exc()}")
        _export_status_update(rid, busy=False, phase="failed", error=str(error), result=None)


def _prepare_export(rid, d):
    live = axi_rig.ea_defaults(LIVE_EA)
    lines = [f"; {LIVE_EA} - settings from Turtle TV run {rid} '{d['label']}' ({d['created']})",
             f"; MT5 {d['symbol']} {d['from']} - {d['to']}, delay {d['delay']}: net {d['report'].get('net')}, PF {d['report'].get('pf')}, trades {d['report'].get('trades')}"]
    doc = settings_doc(d["inputs"], d.get("notes"), raw=d.get("tradingview"), chart=d.get("chart"),
                       result={"run": rid, "label": d["label"], "symbol": d["symbol"], "period": d["period"], "from": d["from"], "to": d["to"],
                               "delay": d["delay"], "deposit": d["deposit"], "net": d["report"].get("net"), "profit_factor": d["report"].get("pf"),
                               "trades": d["report"].get("trades"), "max_drawdown": d["report"].get("dd")})
    missing = sorted(set(live) - set(doc["ea_inputs"]))
    if missing:
        raise RuntimeError("Settings handoff omitted production EA inputs: " + ", ".join(missing))
    lines += [f"{k}={v}" for k, v in doc["ea_inputs"].items()]
    text = "\r\n".join(lines) + "\r\n"
    name = f"{LIVE_EA}_TurtleTV.set"
    written = []
    (HERE / "presets").mkdir(exist_ok=True)
    keep = HERE / "presets" / f"{LIVE_EA}_TurtleTV_{rid}.set"
    keep.write_text(text, encoding="utf-16")
    written.append(str(keep))
    for term in TERMINALS.iterdir():
        exp = term / "MQL5" / "Experts"
        if (exp / f"{LIVE_EA}.ex5").exists() or (exp / f"{LIVE_EA}.mq5").exists():
            pre = term / "MQL5" / "Presets"
            pre.mkdir(exist_ok=True)
            (pre / name).write_text(text, encoding="utf-16")
            written.append(str(pre / name))
    candidate = f"{LIVE_EA}_TurtleTV_{rid}"
    jf = SETTINGS / f"{LIVE_EA}_TurtleTV_{rid}.json"
    jf.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (SETTINGS / "turtletv_export_latest.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    written.insert(0, str(jf))
    return {"preset": name, "json": jf.name, "candidate": candidate, "written": written,
            "candidate_status": "compiling and testing"}, doc, text, candidate, jf


def export(rid):
    run_file = RUNS / f"{rid}.json"
    if not run_file.is_file():
        raise FileNotFoundError(f"MT5 run {rid} is unavailable")
    d = json.loads(run_file.read_text(encoding="utf-8"))
    with LOCK:
        if STATE["busy"]:
            raise RuntimeError("MT5 Strategy Tester is busy; wait for it to finish before exporting")
        with EXPORT_LOCK:
            if EXPORT_JOB["busy"]:
                raise RuntimeError(f"Another EA export is still running ({EXPORT_JOB['id']})")
            EXPORT_JOB.update(id=rid, busy=True, phase="preparing the complete production EA settings",
                              error=None, result=None, started=time.time())
    try:
        response, doc, text, candidate, settings_path = _prepare_export(rid, d)
    except Exception as error:
        _export_status_update(rid, busy=False, phase="failed", error=str(error), result=None)
        raise
    _export_status_update(rid, candidate=candidate)
    threading.Thread(target=_export_candidate, args=(rid, d, doc, settings_path, candidate, text), daemon=True).start()
    return response


def export_status(rid):
    with EXPORT_LOCK:
        if EXPORT_JOB["id"] != rid:
            return {"id": rid, "busy": False, "error": "No active export job for this run"}
        state = dict(EXPORT_JOB)
    state["seconds"] = round(time.time() - state["started"], 1) if state["started"] else 0
    return state


def candidate_files(rid):
    if not re.fullmatch(r"r\d{8}_\d{6}", rid):
        return None
    if not TERMINALS.is_dir():
        return None
    candidate = f"{LIVE_EA}_TurtleTV_{rid}"
    source = ROOT / "mt5" / f"{candidate}.mq5"
    report = RUNS / f"{rid}_candidate.htm"
    if not source.is_file() or not report.is_file() or report.stat().st_size == 0:
        return None
    try:
        for terminal in TERMINALS.iterdir():
            compiled = terminal / "MQL5" / "Experts" / f"{candidate}.ex5"
            if compiled.is_file() and compiled.stat().st_size:
                return {"name": candidate, "source": source, "compiled": compiled, "report": report}
    except OSError:
        return None
    return None


def _candidate_installed_paths(name):
    paths = []
    try:
        for terminal in TERMINALS.iterdir():
            compiled = terminal / "MQL5" / "Experts" / f"{name}.ex5"
            if compiled.is_file() and compiled.stat().st_size:
                paths.append(str(compiled))
    except OSError as error:
        log(f"candidate {name}: could not inspect MT5 terminals: {error}")
    return paths


def _candidate_manifest_path(rid):
    return RUNS / f"candidate_{rid}.json"


def _write_candidate_manifest(rid, record):
    manifest = _candidate_manifest_path(rid)
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
    temporary.replace(manifest)


def _candidate_record_available(record):
    try:
        source = Path(record["source_path"])
        report = Path(record["report_path"])
        if not source.is_file() or not report.is_file() or report.stat().st_size == 0:
            return False
        source_hash = record.get("source_sha256")
        if source_hash and hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            return False
        expected_binary_hash = record.get("compiled_sha256")
        for path in record.get("compiled_paths", []):
            binary = Path(path)
            if binary.is_file() and binary.stat().st_size:
                if not expected_binary_hash or hashlib.sha256(binary.read_bytes()).hexdigest() == expected_binary_hash:
                    return True
        return False
    except (KeyError, OSError, TypeError):
        return False


def candidate_metadata(rid, run=None):
    if not re.fullmatch(r"r\d{8}_\d{6}", rid):
        return None
    manifest = _candidate_manifest_path(rid)
    if manifest.is_file():
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
            record["available"] = _candidate_record_available(record)
            source = Path(record["source_path"])
            compiled = next((Path(path) for path in record.get("compiled_paths", [])
                             if Path(path).is_file() and Path(path).stat().st_size), None)
            changed = False
            if not record.get("source_sha256") and source.is_file():
                record["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
                changed = True
            if not record.get("compiled_sha256") and compiled:
                record["compiled_sha256"] = hashlib.sha256(compiled.read_bytes()).hexdigest()
                changed = True
            compiler = record.get("compiler") or {}
            if "returncode" in compiler and "process_exit_code" not in compiler:
                compiler["process_exit_code"] = compiler.pop("returncode")
                record["compiler"] = compiler
                changed = True
            tester = record.setdefault("tester", {})
            if "avg_win" not in tester or "avg_loss" not in tester:
                try:
                    report = axi_rig.parse(record["report_path"])
                    trade_stats = report.get("trade_stats") or {}
                    tester["avg_win"] = trade_stats.get("avg_win")
                    tester["avg_loss"] = trade_stats.get("avg_loss")
                    changed = True
                except (OSError, ValueError, KeyError) as error:
                    log(f"candidate {rid}: could not refresh tester averages: {error}")
            if changed:
                _write_candidate_manifest(rid, record)
            _attach_candidate_to_saved(record)
            return record
        except (OSError, KeyError, TypeError, ValueError) as error:
            log(f"candidate {rid}: invalid manifest {manifest}: {error}")

    artifacts = candidate_files(rid)
    if not artifacts:
        return None
    try:
        report = axi_rig.parse(artifacts["report"])
    except (OSError, ValueError, KeyError) as error:
        log(f"candidate {rid}: could not read MT5 candidate report: {error}")
        return None
    paths = _candidate_installed_paths(artifacts["name"])
    try:
        compiled_at = datetime.fromtimestamp(Path(paths[0]).stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except (IndexError, OSError, ValueError):
        compiled_at = datetime.fromtimestamp(artifacts["source"].stat().st_mtime).astimezone().isoformat(timespec="seconds")
    source_text = artifacts["source"].read_text(encoding="utf-8", errors="replace")
    version = re.search(r'#property\s+version\s+"([^"]+)"', source_text)
    run = run or {}
    record = {
        "run_id": rid,
        "name": artifacts["name"],
        "version": version.group(1) if version else "unknown",
        "compiled_at": compiled_at,
        "source_path": str(artifacts["source"]),
        "source_sha256": hashlib.sha256(artifacts["source"].read_bytes()).hexdigest(),
        "compiled_paths": paths,
        "compiled_sha256": hashlib.sha256(Path(paths[0]).read_bytes()).hexdigest() if paths else None,
        "report_path": str(artifacts["report"]),
        "report_url": f"/api/export_report?id={rid}",
        "preset_paths": [str(Path(path).parent.parent / "Presets" / f"{artifacts['name']}.set") for path in paths],
        "tester": {key: report.get(key) for key in ("net", "pf", "trades", "wr", "dd", "quality")} | {
            "avg_win": (report.get("trade_stats") or {}).get("avg_win"),
            "avg_loss": (report.get("trade_stats") or {}).get("avg_loss"),
        },
        "tester_symbol": run.get("symbol"),
        "tester_period": run.get("period"),
        "tester_from": run.get("from"),
        "tester_to": run.get("to"),
        "tester_deposit": run.get("deposit"),
        "settings_changed": run.get("changed") or {},
        "available": True,
    }
    try:
        _write_candidate_manifest(rid, record)
        _attach_candidate_to_saved(record)
    except OSError as error:
        log(f"candidate {rid}: could not persist export manifest: {error}")
    return record


def _saved_period(ds):
    return "M5" if ds == "m5x" else "M1" if ds in ("year1", "m1x") else "M15"


def _attach_candidate_to_saved(record):
    changed = record.get("settings_changed") or {}
    period = record.get("tester_period") or "M15"
    for path in SAVED.glob("*.json"):
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if _saved_period(saved.get("ds")) != period:
                continue
            saved_changed = saved.get("changed") or {}
            if len(saved_changed) != len(changed) or not all(
                key in saved_changed and same(saved_changed[key], value) for key, value in changed.items()
            ):
                continue
            exports = saved.get("candidate_exports") or []
            existing = next((item for item in exports if item.get("run_id") == record["run_id"]), None)
            if existing == record:
                continue
            exports = [item for item in exports if item.get("run_id") != record["run_id"]]
            exports.append(record)
            exports.sort(key=lambda item: item.get("compiled_at", ""))
            saved["candidate_exports"] = exports
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            temporary.replace(path)
        except (OSError, ValueError, TypeError) as error:
            log(f"candidate {record.get('run_id')}: could not save metadata to {path}: {error}")


# ---------- the Turtle TV Tester (sim.py): instant results for any settings ----------
def _utc(e):
    return int((server_to_utc(datetime(1970, 1, 1) + timedelta(seconds=int(e))) - datetime(1970, 1, 1)).total_seconds())


_BARS = {}


def bars_json(ds="year"):
    """The M15 candles of a dataset ('year' = the Blueberry MT5 candles the EA trades on, 'tv' = TradingView's own candles), UTC, with ADX / ATR."""
    if ds not in _BARS:
        D = sim.data(ds)
        if ds in ("m1x", "m5x"):                           # 4 years of 1-minute candles is too much to draw: the chart shows 2026 (the tools use all of it)
            i0 = int(np.searchsorted(D["t15"], 1767225600))
            D = {k: (v[i0:] if k in ("t15", "o15", "h15", "l15", "c15", "adx", "atr") else v) for k, v in D.items()}
        r2 = lambda a: [round(float(x), 5) for x in a]          # TurtleTVUHV: EUR/USD needs 5 decimals
        _BARS[ds] = json.dumps({"ds": ds, "t": [_utc(x) for x in D["t15"]], "o": r2(D["o15"]), "h": r2(D["h15"]), "l": r2(D["l15"]), "c": r2(D["c15"]),
                                "adx": r2(D["adx"]), "atr": [round(float(x), 6) for x in D["atr"]], "v": [int(x) for x in D["v1"]] if "v1" in D else [],   # TurtleTVUHV: tick volume per minute
                                "ticks_until": _utc(int(D["ticks_until"][0])) if "ticks_until" in D else None}, separators=(",", ":"))
    return _BARS[ds]


# ---------- TurtleTVUHV: Zee's UHV Diamond (ZeeUHV_Diamond v1.27 rules = TriDia / DiamondEngineM1, OANDA off -> PrimeXBT tick volume) ----------
import uhv_diamond
import uhv_engine  # noqa: E402
sim.simulate = uhv_engine.simulate                         # TurtleTVUHV: every tool's engine (tester, Exit Lab, scans) runs the UHV strategy
UHV_FILE = HERE / "simdata" / "uhv_setups.json"


_ttd_features = uhv_engine.ttd_features          # moved to uhv_engine.py (the detection scan builds setups there too)


def uhv_setups(ds="year1"):
    """Every setup of his rules on the dataset: camel-hump trend -> retracement -> UHV (loudest counter-coloured candle) -> the first quieter
    candle closing beyond it. 'ea' = the EA v1.27 itself would take it (fresh trend reading, hump budget 3, UHV body/neighbours, cooldown);
    'royal' = ea + the 15-minute efficiency ratio >= 0.45. Steps the bars exactly as the game does (a rolling 400-bar window); cached."""
    src = [HERE / "uhv_diamond.py", HERE / "simdata" / f"{ds}.npz"]
    if UHV_FILE.exists() and UHV_FILE.stat().st_mtime > max(f.stat().st_mtime for f in src):
        return UHV_FILE.read_text(encoding="utf-8")
    D = sim.data(ds)
    rows = [[int(t), float(o), float(h), float(l), float(c), float(v)] for t, o, h, l, c, v in zip(D["t1"], D["o1"], D["h1"], D["l1"], D["c1"], D["v1"])]
    dia = uhv_diamond.Diamond(unit=0.00012)
    out, seen, t0, roughs = [], set(), time.time(), []
    for i in range(400, len(rows)):
        win = rows[i - 400:i + 1]
        dia.update(win, lambda b: b[5] or None, win[-1][0] + 30)
        rg = dia.rough
        if rg and not (dia.cut and dia.cut["t"] == win[-1][0]):     # a UHV level waiting during the minute that starts now (instant entry)
            roughs.append([int(win[-1][0]), int(rg["side"]), round(rg["level"], 5), round(rg["extreme"], 5), int(rg["uhv_t"]), float(rg["uhv_v"] or 0)])
        cut = dia.cut
        if cut and cut["t"] not in seen:
            seen.add(cut["t"])
            out.append({"t": int(cut["t"]), "side": cut["side"], "uhv_t": int(cut["uhv_t"]), "level": round(cut["level"], 5),
                        "extreme": round(cut["extreme"], 5), "laws": cut["laws"], "ea": bool(cut["ea"]), "royal": bool(cut["royal"]),
                        "er": None if cut["er"] is None else round(cut["er"], 3)})
    _ttd_features(D, out)                                       # TurtleTVUHV: what the Turtle Trader Desk indicator's filters read, per setup
    js = json.dumps({"ds": ds, "bars": len(rows), "setups": out, "roughs": roughs, "secs": round(time.time() - t0, 1)}, separators=(",", ":"))
    UHV_FILE.write_text(js, encoding="utf-8")
    log(f"UHV setups: {len(out)} on {len(rows)} bars in {time.time() - t0:.0f} s")
    return js


def uhv_camel(ds="year1"):
    """Zee's camel humps for the chart, exactly as his Turtle Trader Desk indicator draws them (pine CAMEL-HUMP TREND block): swings
    confirmed CAM_PIV candles later (a high no lower than its neighbours, ties counting; a low mirrors it), highs and lows alternating (two
    highs in a row merge into the taller), one arch per hump: swing low -> swing high -> next swing low, green when it ends higher than it
    started, red when lower. The same state machine as uhv_diamond.Diamond.camel_step (the tester's trend)."""
    D = sim.data(ds)
    t, h, l = np.asarray(D["t1"], dtype=np.int64), np.asarray(D["h1"]), np.asarray(D["l1"])
    p = uhv_diamond.CAM_PIV
    T, HB, HV, L0B, L0V, LB, LV, Tr = 0, None, None, None, None, None, None, 0
    humps = []
    for i in range(2 * p, len(t)):
        c = i - p
        ph = all(not (h[c] < h[c + d] or h[c] < h[c - d]) for d in range(1, p + 1))
        pl = all(not (l[c] > l[c + d] or l[c] > l[c - d]) for d in range(1, p + 1))
        if ph:
            if T == 1:
                if h[c] >= HV:
                    HB, HV = c, h[c]
            else:
                L0B, L0V, HB, HV, T = LB, LV, c, h[c], 1
        if pl:
            redraw = False
            if T == 1:
                LB, LV, T, redraw = c, l[c], -1, True
            elif T == -1 and l[c] <= LV:
                LB, LV, redraw = c, l[c], True
            elif T == 0:
                LB, LV, T = c, l[c], -1
            if redraw and HB is not None and L0B is not None:
                Tr = 1 if LV > L0V else -1 if LV < L0V else 0
                if humps and humps[-1][2] == HB:
                    humps[-1] = [L0B, float(L0V), HB, float(HV), LB, float(LV), Tr]      # the same hump, its low went deeper
                else:
                    humps.append([L0B, float(L0V), HB, float(HV), LB, float(LV), Tr])
    pts = []                                               # one point per candle: a quarter-sine up into the top, a quarter-cosine down
    for b0, v0, bh, vh, b1, v1, tr in humps:
        col = "#26a69a" if tr == 1 else "#ef5350" if tr == -1 else "#9e9e9e"
        n1, n2 = max(bh - b0, 1), max(b1 - bh, 1)
        for k in range(0, n1 + 1):
            pts.append([int(t[b0 + k]), round(v0 + (vh - v0) * math.sin(k / n1 * math.pi / 2), 5), col])
        for k in range(1, n2 + 1):
            pts.append([int(t[bh + k]), round(vh - (vh - v1) * (1 - math.cos(k / n2 * math.pi / 2)), 5), col])
    seen, out = set(), []
    for q in pts:
        if q[0] not in seen:
            seen.add(q[0]); out.append(q)
    out.sort(key=lambda q: q[0])
    return {"humps": len(humps), "pts": out}


def full_inputs(sets):
    import uhv_engine
    dfl = {**axi_rig.ea_defaults(EA), **{k: v[0] for k, v in uhv_engine.UHV_DEFAULTS.items()}, **{k: v[0] for k, v in __import__("uhv_ttd").TTD.items()}, **{k: f"{v:g}" for k, v in uhv_engine.DET_DEFAULT.items()}, **UHV_SAAD_DEFAULTS}   # TurtleTVUHV
    out = {i["name"]: str(sets.get(i["name"], dfl.get(i["name"], i["default"]))) for i in ea_inputs()["inputs"]}
    out.update({k: str(v) for k, v in sets.items() if str(k).startswith("TvBox_")})   # rbox.py range boxes: Turtle TV tester inputs (not in the EA yet)
    return out


# ---------------------------------------------------------------- ask Claude about ONE trade (Zee 2026-10-20: "on the buy sell label of each candle,
# i want a button ask claude about this trade? ... claude answers that query about that particular setup ... we write it on/above the label")
# Answered by the Claude Code CLI on Zee's own login (the API key has no credits); Claude may read the repo (EA source, LAWS.md, reports), never edit.
NOTES = Path(__file__).parent / "asks" / "trade_notes.json"
CLAUDE_EXE = sorted(Path.home().glob(".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe"))
TRADE_SYSTEM = """You are Claude, inside Turtle TV (Zee's TradingView-style chart for his Saad gold EA, Saad_strategy_15min v1.28, XAUUSD 15-minute
candles, Blueberry real ticks, 2 lots). Zee clicked ONE trade's label on the chart and asks about THAT trade. Below: the trade (entry / stop / exit,
result, why it closed, range box), its setup candle, every candle from 60 before the entry to 10 after the exit with the EA's own EMAs, ADX and ATR,
the EA's decisions in that window, how the same kind of setup did over the whole data, and the settings on screen.

How the EA trades: a pin bar / hammer / shooting star / marubozu touching the fast or slow EMA is a setup; a break of its high (BUY) / low (SELL) by
InpBreakPips within InpBreakBars candles enters; stop = InpSlAtrMult x ATR(14), skipped if over InpMaxRiskUsd; ADX >= InpAdxMin; exit = the nearer EMA
beyond the entry (InpExitMode 1). You may read files in the repo (mt5/Saad_strategy_15min.mq5 is the EA, LAWS.md is Zee's own rulebook - read it, never
edit anything). Inspect the candles yourself: the trend, where price sat between the EMAs, the setup candle's shape, the volatility, what happened
after the entry, and what a skilled discretionary trader would have seen. Be concrete: name candles by Pakistan time (12-hour), quote prices.
House rule: an idea from one trade is a hypothesis; only MT5's Strategy Tester promotes it. Answer in English, short and direct: first a 1-2 sentence
verdict (it is shown ON the chart above the label), then a blank line, then the detail."""


def _notes():
    try:
        return json.loads(NOTES.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}


def ask_trade(body):
    key, q = str(body.get("key", "")), (body.get("question") or "").strip()
    if not re.fullmatch(r"-?\d+_-?1", key) or not q:
        return {"error": "no trade / no question"}
    ctx = json.dumps(body.get("context") or {}, separators=(",", ":"), default=str)[:120000]
    prev = _notes().get(key, [])
    hist = "".join(f"\n\nEarlier, Zee asked: {n['q']}\nYou answered: {n['a']}" for n in prev[-4:])
    prompt = f"{TRADE_SYSTEM}{hist}\n\nZee's question about this trade: {q}\n\nThe trade and the chart around it (JSON):\n{ctx}"
    text, err = None, None
    if CLAUDE_EXE:
        try:
            r = subprocess.run([str(CLAUDE_EXE[-1]), "-p", "--output-format", "text", "--model", "opus", "--allowedTools", "Read", "Grep", "Glob"],
                               input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=900, cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            text = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
            err = None if text else f"Claude Code: {(r.stderr or r.stdout).strip()[:400]}"
        except Exception as e:                                   # noqa: BLE001
            err = f"Claude Code: {e}"
    if text is None:                                             # the API, if it has credits again
        a = ask_claude({"question": f"{TRADE_SYSTEM}{hist}\n\nZee's question about this trade: {q}", "context": body.get("context")})
        text, err = a.get("text"), a.get("error") or err
    if not text:
        return {"error": err or "no answer"}
    allr = _notes()
    allr.setdefault(key, []).append({"q": q, "a": text, "at": datetime.now().strftime("%Y-%m-%d %I:%M %p")})
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    NOTES.write_text(json.dumps(allr, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"ask_trade {key}: {len(q)} chars -> {len(text)} chars")
    return {"text": text, "notes": allr[key]}


# ---------------------------------------------------------------- hypotheses from a trade answer: TEST them on the chart, CONVERT one into an EA feature
# Zee 2026-10-20: "once we show a hypothesis, the chat window should show: Test hypothesis button ... it invokes claude to add the new setting/change
# to the chart and then another button called, convert hypothesis to feature: this button allows us to request claude to add the tested hypothesis
# as a setting/feature"
HJOBS = {}


def _claude(prompt, tools, timeout=900, extra=()):
    if not CLAUDE_EXE:
        raise RuntimeError("Claude Code (claude.exe) not found")
    r = subprocess.run([str(CLAUDE_EXE[-1]), "-p", "--output-format", "text", "--model", "opus", *extra, "--allowedTools", *tools],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"Claude Code: {(r.stderr or r.stdout).strip()[:400]}")
    return r.stdout.strip()


def _note_set(key, idx, field, val):
    allr = _notes()
    if key in allr and 0 <= idx < len(allr[key]):
        allr[key][idx][field] = val
        NOTES.write_text(json.dumps(allr, indent=1, ensure_ascii=False), encoding="utf-8")


def _hyp_test(job, key, idx, cur, ds):
    note = _notes()[key][idx]
    inputs = [{k: i[k] for k in ("name", "type", "default", "comment")} for i in ea_inputs()["inputs"]]
    mode0 = sorted(sim_full.MODE0_ONLY)
    prompt = f"""Below is your earlier answer to Zee about one trade, with hypotheses in it. Turn EACH hypothesis into something Turtle TV can test now:
either changes of the EA's EXISTING inputs ("changes"), or a recipe of the Exit Lab's building blocks ("lab") - the Exit Lab runs extra exits on
top of exit modes 1-2 (targets in R / ATR / $, the no-EMA-beyond fallback's buffer and closes, close-based exits, partials, breakeven, lock ladder,
trails, time / no-progress / ADX / Friday exits). Prefer the Exit Lab for exit ideas: these EA inputs ONLY act with InpExitMode 0 (the v1.23
exits) and do NOTHING in exit modes 1-2 (the settings on screen use exit mode {cur.get('InpExitMode')}): {', '.join(mode0)}.
If neither can express a hypothesis, say so and describe the new setting it needs. Reply with ONLY a JSON array, no prose, no code fence:
[{{"hypothesis": "<short>", "changes": {{"InpName": "value"}} or {{}}, "lab": {{"field": number}} or {{}}, "exact": true|false, "note": "<one line: how it approximates the hypothesis, or the new setting needed>"}}]
Give 1-3 variants per hypothesis when a value is a guess (e.g. two buffer sizes).

Your answer:
{note['a']}

The settings on screen now (only those that differ from the EA's defaults): {json.dumps({k: v for k, v in cur.items() if not same(v, axi_rig.ea_defaults(EA).get(k))})}
The EA's inputs: {json.dumps(inputs, ensure_ascii=False)}
The Exit Lab's building blocks (field names for "lab"; R = the entry-to-first-stop distance):
{exitlab.blocks_text()}"""
    job["phase"] = "Claude is turning the hypotheses into settings"
    txt = _claude(prompt, ["Read", "Grep", "Glob"])
    m = re.search(r"\[.*\]", txt, re.S)
    hyps = json.loads(m.group(0)) if m else []
    names = {i["name"] for i in inputs}
    o = optimizer.Optimizer(cur, ds=ds)
    job["phase"] = "testing on the chart"
    _, a, b, _y = optimizer.evaluate(cur, "net", 1, o.window, ds)
    base = {"train": a, "test": b}
    win = exitlab.window_of(ds, cur)[0]
    for h in hyps:
        ch = {k: str(v) for k, v in (h.get("changes") or {}).items() if k in names}
        lab = exitlab.clean(h.get("lab") or {}) if h.get("lab") else {}
        lab = lab if [f for f in lab if f != "pess"] else {}
        if ch and any(k in sim_full.MODE0_ONLY for k in ch) and str(ch.get("InpExitMode", cur.get("InpExitMode"))) != "0":
            ch["InpExitMode"] = "0"                       # they only act with the v1.23 exits - which the tester and MT5 disagree on
            h["mode0"] = True
        h["changes"], h["lab"] = ch, lab
        if ch or lab:
            inp = dict(cur, **ch)
            if lab:
                sets = {} if str(inp.get("InpExitMode")) in ("1", "2") else {"InpExitMode": "1"}
                _, real, oe = exitlab.run(inp, ds, lab=lab, sets=sets)
                s = exitlab.stats(real, win, open_end=oe)
                h["stuck"], h["open_end"] = s["stuck"], s["open_end"]
                a, b = s["train"], s["test"]
                h["describe"] = exitlab.describe(lab)
            else:
                _, a, b, _y = optimizer.evaluate(inp, "net", 1, o.window, ds)
            if a is None:
                h["invalid"] = True                       # e.g. the slow EMA not above the fast one
                continue
            h["train"], h["test"], h["inputs"] = a, b, inp
            h["noop"] = (abs(a["net"] - base["train"]["net"]) < 1 and abs(b["net"] - base["test"]["net"]) < 1 and a["n"] == base["train"]["n"]
                         and b["n"] == base["test"]["n"])
            h["mode0"] = h.get("mode0") or (str(inp.get("InpExitMode")) == "0" and str(cur.get("InpExitMode")) != "0")
    res = {"labels": list(o.labels), "ds": ds, "base": base, "hyps": hyps, "at": datetime.now().strftime("%Y-%m-%d %I:%M %p")}
    _note_set(key, idx, "test", res)
    return res


def _hyp_feature(job, key, idx, which):
    note = _notes()[key][idx]
    test = note.get("test") or {}
    prompt = f"""Zee pressed "Convert hypothesis to feature" in Turtle TV. Add this hypothesis to the Saad 15-min EA as a NEW SETTING, the way v1.28's
InpSkipBothEma was added (git show 8aee8953 is the template - read it first):

Hypothesis: {which}
(From your answer about one trade: {note['a'][:3000]})
Turtle TV's earlier test with existing settings: {json.dumps(test.get('hyps', []), default=str)[:3000]}

Do all of this, in order:
1. mt5/Saad_strategy_15min.mq5: a new input, OFF by default (with it off, trading must be identical to now), with a clear comment; bump the version
   (#property version, EA_COMMENT, a // vX.YY header line quoting Zee). Keep the EA's style.
2. monitor/saad_view/sim_full.py: mirror it exactly (append the input name to the END of FULL; never reorder), and add it to SURVEY in
   monitor/saad_view/optimizer.py (entries or exits). Run: py monitor/saad_view/make_view_ea.py
3. Check in Python that OFF reproduces the current result (set NUMBA_CPU_NAME=generic; import server, sim; sim.simulate(server.full_inputs({{}}), ds="year")).
   Then test ON (and 1-2 values) on ds "year" and "m15" (train 2023-24 vs unseen 2025-26).
4. MT5: POST http://127.0.0.1:8773/api/run with {{"sets": {{"<name>": "<value>"}}, "label": "..."}} for off and on (one at a time; poll /api/status until
   busy is false; results in monitor/saad_view/runs/<id>.json "report"). If the server is down, say so and skip.
5. Add a row to VERSION.md (the Saad_strategy_15min table + "Which EA is which") and an entry to VERSION_HISTORY.md, then git add ONLY the files you
   changed and commit (end the message with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>).
Never edit LAWS.md. Never push. Python numbers are hypotheses; MT5 decides - say "keep it off" if MT5 does not beat the current version.
Finish with a short report for Zee (plain English, under 15 lines): the setting's name, what it does, the MT5 numbers off vs on, and your verdict."""
    job["phase"] = "Claude is adding the setting to the EA, the chart and MT5 (several minutes)"
    txt = _claude(prompt, ["Read", "Grep", "Glob", "Edit", "Write", "Bash(py:*)", "Bash(python:*)", "Bash(git add:*)", "Bash(git commit:*)",
                           "Bash(git show:*)", "Bash(git diff:*)", "Bash(git status:*)", "Bash(curl:*)", "Bash(sleep:*)"], timeout=3600)
    res = {"which": which, "report": txt, "at": datetime.now().strftime("%Y-%m-%d %I:%M %p")}
    allr = _notes()
    allr[key][idx].setdefault("features", []).append(res)
    NOTES.write_text(json.dumps(allr, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def hyp_start(body):
    key, idx, kind = str(body.get("key", "")), int(body.get("idx", -1)), body.get("kind")
    if key not in _notes() or not (0 <= idx < len(_notes()[key])) or kind not in ("test", "feature"):
        return {"error": "no such answer"}
    if any(j["running"] and j["kind"] == "feature" for j in HJOBS.values()) and kind == "feature":
        return {"error": "Claude is already adding a feature; wait for it to finish"}
    jid = f"h{int(time.time() * 1000)}"
    job = HJOBS[jid] = {"id": jid, "kind": kind, "key": key, "idx": idx, "running": True, "phase": "starting", "result": None, "error": None}

    def go():
        try:
            if kind == "test":
                cur = full_inputs(body.get("inputs") or {})
                ds = body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year"
                job["result"] = _hyp_test(job, key, idx, cur, ds)
            else:
                job["result"] = _hyp_feature(job, key, idx, str(body.get("which") or "the hypothesis"))
        except Exception as e:                                  # noqa: BLE001
            job["error"] = str(e)
            log(f"hyp {kind} {key}: {traceback.format_exc()}")
        finally:
            job["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"id": jid}


MODES = {"ea": {}, "chart": {"chart": True}, "chart_blind": {"chart": True, "blind_until": sim.TV_M1_FROM}}


def _months(tr):
    """win rate per month of the trade's exit, UTC (as TradingView's panel)"""
    m = {}
    for x in tr:
        if x[10] != 0:
            continue
        k = datetime.utcfromtimestamp(_utc(x[4])).strftime("%Y-%m")
        d = m.setdefault(k, [0, 0, 0.0]); d[0] += 1; d[1] += int(x[6] > 0); d[2] += float(x[6])
    return {k: {"n": v[0], "w": v[1], "net": round(v[2])} for k, v in sorted(m.items())}


def uhv_sim_result(sets, want_ema=True, want_setups=True, ds="year1"):
    """TurtleTVUHV: the Turtle TV Tester's answer for Zee's UHV Diamond, in EXACTLY the Saad tester's format (the same trade rows, events,
    year / train / test scores and months), so every original panel - Overview, equity, Months, Weekdays, List of trades - shows UHV unchanged.
    The rounds come from uhv_ticktest.py (PrimeXBT real ticks, game geometry); one round at a time, as the game plays them."""
    f = HERE / "simdata" / "uhv_trades.json"
    T = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"trades": [], "tp_pips": 2, "sl_pips": 2}
    lots = 0.01                                               # 1 game coin = 1,000 EUR = 0.01 lot -> 1 pip = $0.10
    rows = [r for r in T["trades"] if r.get("game")]
    tr = np.zeros((len(rows), 16))
    why = {"tp": 2, "sl": 1, "time": 4}
    for i, r in enumerate(rows):
        tr[i, 0] = r["side"]; tr[i, 1] = r["t_in"]; tr[i, 2] = r["fill"]; tr[i, 3] = r["fill"] - r["side"] * T["sl_pips"] * 0.0001
        tr[i, 4] = r["t_out"]; tr[i, 5] = r["exit"]; tr[i, 6] = round(r["usd"] * lots / 0.01, 2); tr[i, 13] = why.get(r["why"], 0)
    names = {1: "stop loss (-%s pips)" % T["sl_pips"], 2: "target (+%s pips)" % T["tp_pips"], 4: "4-hour limit"}
    ev = []
    for n, (x, r) in enumerate(zip(tr, rows), 1):
        side = int(x[0])
        txt = ("★ ROYAL " if r["royal"] else "★ EA " if r["ea"] else "") + ("UHV buy" if side > 0 else "UHV sell")
        ev.append({"type": "entry", "t": int(x[1]), "side": side, "price": round(x[2], 5), "sl": round(x[3], 5), "v1": 0, "v2": 0, "ref": None, "num": n, "text": txt})
        ev.append({"type": "exit", "t": int(x[4]), "side": side, "price": round(x[5], 5), "sl": round(x[3], 5), "v1": round(x[6], 2), "v2": 0,
                   "ref": int(x[1]), "num": n, "text": names.get(int(x[13]), "")})
    if want_setups:
        for s in json.loads(UHV_FILE.read_text(encoding="utf-8"))["setups"] if UHV_FILE.exists() else []:
            ev.append({"type": "setup", "t": int(s["t"]) - 60, "side": int(s["side"]), "price": s["level"], "sl": s["extreme"], "v1": s["level"],
                       "v2": 1 if s["ea"] else 0, "ref": None, "num": 0, "text": ""})
    ev.sort(key=lambda e: e["t"])
    split = int((datetime(2026, 7, 1) - datetime(1970, 1, 1)).total_seconds())
    allsu = len(json.loads(UHV_FILE.read_text(encoding="utf-8"))["setups"]) if UHV_FILE.exists() else 0
    st = {"setups": allsu, "no_break": 0, "risk": 0, "adx": 0, "atr_band": 0, "band_skip": allsu - len(rows), "gap": 0, "spread_reject": 0,
          "open_at_end": 0, "open_since": None}
    out = {"inputs": full_inputs(sets), "ms": 0, "events": ev, "stats": st, "year": sim.score(tr), "train": sim.score(tr[tr[:, 1] < split], 1),
           "test": sim.score(tr[tr[:, 1] >= split], 1), "ds": "year1", "mode": "ea", "months": _months(tr)}
    if want_ema:
        out["ef"], out["es"] = [], []
    return out


def sim_result(sets, want_ema=True, want_setups=True, ds="year", mode="ea", lab=None, prune=()):
    """ds 'year' (Blueberry MT5 candles) / 'tv' (TradingView's candles); mode 'ea' (v1.27's rules, real spread + swap), 'chart' (the indicator's
    rules, $0.17 spread, no swap), 'chart_blind' (and blind inside the entry candle before Oct 12, like TradingView without 1-minute data)."""
    ds = "year1"                                              # TurtleTVUHV: one dataset, PrimeXBT EUR/USD M1
    inp = full_inputs(sets)
    lab = exitlab.clean(lab) if lab else None
    lab = lab if lab and [f for f in lab if f != "pess"] else None
    if lab and str(inp.get("InpExitMode")) not in ("1", "2"):
        inp["InpExitMode"] = "1"                          # the Exit Lab's exits sit on top of exit modes 1-2
    t0 = time.time()
    tr, su, st = sim.simulate(inp, ds=ds, lab=lab, prune=tuple(int(r) for r in (prune or ())), **MODES.get(mode, {}))   # prune: Trade Lifecycle cuts applied
    ms = round(1000 * (time.time() - t0), 1)
    D = sim.data(ds)
    nf, ns = int(float(inp["InpEmaFast"])), int(float(inp["InpEmaSlow"]))
    why = {**exitlab.WHY, 1: "stop loss", 2: "the next EMA touched (target)", 3: "closed back across the EMA", 4: "day close, in loss"}
    tgt = lambda n: (f"touch of the {nf if n == 9 else ns} EMA, all closed" if n > 0 else
                     f"no EMA beyond the entry: out after a close back across the {nf} EMA" if n == -1 else
                     f"no target: out after a close back across the {ns} EMA")
    ev, num = [], 0
    for x in tr[np.argsort(tr[:, 1], kind="stable")]:
        side, nx, b = int(x[0]), int(x[9]), int(x[8])
        if x[10] == 1:
            ev.append({"type": "ghost", "t": _utc(x[1]), "side": side, "price": round(x[2], 5), "sl": round(x[3], 5), "v1": nx, "v2": b, "ref": None, "num": 0, "text": tgt(nx)})
            ev.append({"type": "ghost_end", "t": _utc(x[4]), "side": side, "price": round(x[5], 5), "sl": round(x[2], 5), "v1": 0, "v2": 0, "ref": None, "num": 0,
                       "text": why.get(int(x[13]), "")})
            continue
        num += 1
        ev.append({"type": "entry", "t": _utc(x[1]), "side": side, "price": round(x[2], 5), "sl": round(x[3], 5), "v1": nx, "v2": b, "ref": None, "num": num, "text": tgt(nx)})
        ev.append({"type": "exit", "t": _utc(x[4]), "side": side, "price": round(x[5], 5), "sl": round(x[3], 5), "v1": round(x[6], 2), "v2": round(x[7], 2),
                   "ref": _utc(x[1]), "num": num, "text": why.get(int(x[13]), "")})
    brk = 0.0
    for k, side, kind in (su if want_setups else []):
        k = int(k)
        ev.append({"type": "setup", "t": _utc(D["t15"][k]), "side": int(side), "price": float(D["h15"][k]), "sl": float(D["l15"][k]),
                   "v1": round(float(D["h15"][k] if side > 0 else D["l15"][k]), 5), "v2": int(kind), "ref": None, "num": 0, "text": ""})
    ev.sort(key=lambda e: e["t"])
    trn, tst = tr[tr[:, 1] < optimizer.TRAIN_END], tr[tr[:, 1] >= optimizer.TRAIN_END]
    out = {"inputs": inp, "ms": ms, "events": ev, "stats": st, "year": sim.score(tr), "train": sim.score(trn, 1), "test": sim.score(tst, 1), "ds": ds, "mode": mode}
    if ds in ("m15", "year", "tv"):                    # rbox.py range-box families: each trade's box (range-boxes page)
        try:
            import rbox
            real = [x for x in tr if x[10] == 0]
            out["rbox"] = {"spec": rbox.spec(), "rows": [[_utc(x[1]), int(x[0])] + b for x, b in zip(real, rbox.label_trades(ds, D, real, *sim.emas(nf, ns, ds)))]}
        except Exception as ex:                       # noqa: BLE001
            out["rbox"] = {"error": str(ex)}
    if mode == "chart_blind":                    # the same settings with 1-minute data everywhere: which trades TradingView scores wrongly
        tr2 = sim.simulate(inp, ds=ds, chart=True)[0]
        real = {(int(x[0]), int(x[1]) // 900): x for x in tr2 if x[10] == 0}
        flips = []
        for x in tr:
            if x[10] != 0:
                continue
            y = real.get((int(x[0]), int(x[1]) // 900))
            if y is not None and (x[6] > 0) != (y[6] > 0):
                flips.append({"t": _utc(x[1]), "side": int(x[0]), "tv": round(float(x[6])), "real": round(float(y[6])), "why": why.get(int(y[13]), "")})
        out["honest"] = {"year": sim.score(tr2), "months": _months(tr2), "flips": flips}
    out["months"] = _months(tr)
    if want_ema:
        ef, es = sim.emas(nf, ns, ds)
        if ds in ("m1x", "m5x"):                           # the chart shows 2026 only (bars_json): the lines must start where its candles do
            i0 = int(np.searchsorted(D["t15"], 1767225600))
            ef, es = ef[i0:], es[i0:]
        out["ef"] = [round(float(x), 3) for x in ef]
        out["es"] = [round(float(x), 3) for x in es]
    return out


OPT = {"o": None}
RISK_OPT = {"o": None}

# ---------- Ask Claude (Zee 2026-10-20: "is there a way i can connect claude to this web page so it can read in realtime all charts and analyse etc
# or suggest improvements in the strategy") - the chart picture + the data behind it go to Claude from here; the API key never reaches the page
CLAUDE_MODEL = "claude-opus-5-5"
ASK_SYSTEM = """You are Claude, built into Turtle TV: Zee's own TradingView-style chart for his Saad gold EA (Saad_strategy_15min, XAUUSD, 15-minute candles,
Blueberry real ticks, 2 lots). You receive a picture of the chart as Zee sees it and the data behind it (JSON): the EA settings and how they differ from
v1.27, the Turtle TV Tester's results (the EA's rules run on every 1-minute candle of the year; on v1.27 it takes 194 of MT5's 198 trades, 190 with the
same result, and ranks different settings in the same order as MT5), the trades and candles in view, MT5 Strategy Tester results and the optimizer's.

The strategy: a pin bar / hammer / shooting star / marubozu candle touching the fast or slow EMA is a setup; a break of its high (BUY) or low (SELL)
by InpBreakPips within InpBreakBars candles enters; the stop is InpSlAtrMult x ATR(14); ADX(14) must be at least InpAdxMin; the target is the nearer
EMA beyond the entry (InpExitMode 1) or a close back across an EMA; range boxes (InpBandsB / InpBandsS, 21 boxes of 5% of the last N candles' range)
decide where an entry is allowed, an unticked box means stand aside.

House rules (Zee's project): a suggestion is a hypothesis until MT5's Strategy Tester confirms it ("Check in MT5"). Guard against fitting the past:
compare Jan - Jun with Jul - Oct; a change that helps only one half is suspect, and the range boxes are the most over-fitted part. Prefer fewer losing
trades at a fixed stop / target over wider stops. The Turtle TV Tester is optimistic for tight stops (it cannot know the order inside a 1-minute candle).

Answer Zee directly and concretely: what you see on the chart (name dates / trades), what the numbers say, and the 2-4 setting changes (exact input
names and values) you would test next and why, with the risk of each. English, short paragraphs or bullets, times in Pakistan time (12-hour)."""


def ask_claude(body):
    key = (ROOT / "monitor" / ".claude_api_key").read_text(encoding="utf-8").strip()
    hist = [m for m in (body.get("history") or []) if m.get("text") and m.get("role") in ("user", "assistant")]
    while hist and hist[0]["role"] != "user":
        hist.pop(0)
    msgs, last = [], None
    for m in hist:                                              # strictly alternating, as the API wants
        if m["role"] == last:
            msgs[-1]["content"] += "\n\n" + m["text"]
        else:
            msgs.append({"role": m["role"], "content": m["text"]})
            last = m["role"]
    if msgs and msgs[-1]["role"] == "user":
        msgs.pop()
    content = []
    if body.get("image"):
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": body["image"]}})
    ctx = json.dumps(body.get("context") or {}, separators=(",", ":"), default=str)[:150000]
    content.append({"type": "text", "text": f"{body.get('question', '').strip()}\n\nThe data behind the chart (JSON):\n{ctx}"})
    msgs.append({"role": "user", "content": content})
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                 data=json.dumps({"model": CLAUDE_MODEL, "max_tokens": 3000, "system": ASK_SYSTEM, "messages": msgs}).encode("utf-8"),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=240).read())
    except urllib.error.HTTPError as e:
        return {"error": f"Claude API {e.code}: {e.read().decode('utf-8', 'ignore')[:400]}"}
    text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    log(f"ask: {len(body.get('question', ''))} chars -> {len(text)} chars ({r.get('usage')})")
    return {"text": text, "model": r.get("model"), "usage": r.get("usage")}


def opt_start(body):
    objective = body.get("objective") or "ret_dd"
    if not isinstance(objective, str) or objective not in (*optimizer.OBJECTIVES, "entries", "exits", "ranges"):
        return {"error": f"Unsupported optimizer objective: {objective}"}
    if RISK_OPT["o"] and RISK_OPT["o"].running:
        return {"error": "The Risk Manager scan is running. Stop it or wait for it to finish."}
    if OPT["o"] and OPT["o"].running:
        OPT["o"].stop()
        time.sleep(0.2)
    if objective == "ranges":                                     # grow the number of 100%-win range boxes
        o = optimizer.RangeOpt(full_inputs(body.get("start") or {}), ds=body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year")
        OPT["o"] = o
        threading.Thread(target=o.run, daemon=True).start()
        return {"ok": True}
    if objective in ("entries", "exits"):                        # survey: every entry / exit setting one at a time, all results listed
        o = optimizer.Survey(full_inputs(body.get("start") or {}), objective, ds=body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year")
        OPT["o"] = o
        threading.Thread(target=o.run, daemon=True).start()
        return {"ok": True}
    o = optimizer.Optimizer(full_inputs(body.get("start") or {}), objective=objective, boxes=bool(body.get("boxes")),
                            keep_going=bool(body.get("keep")), ds=body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year")
    OPT["o"] = o
    threading.Thread(target=opt_run_and_check, args=(o,), daemon=True).start()
    return {"ok": True}


def risk_start(body):
    groups = body.get("groups") or []
    if not isinstance(groups, list) or not groups:
        return {"error": "Select at least one risk-control group to scan."}
    if any(not isinstance(g, str) or g not in optimizer.RISK_SPACE for g in groups):
        return {"error": "The risk scan contains an unsupported control group."}
    if (OPT["o"] and OPT["o"].running) or (RISK_OPT["o"] and RISK_OPT["o"].running):
        return {"error": "Another optimizer scan is already running. Stop it or wait for it to finish."}
    start = full_inputs(body.get("inputs") or {})
    spaces = list(optimizer.RISK_SPACE["stop"] if "stop" in groups else [])
    mode = str(start.get("InpSlMode", "1"))
    if "stop" in groups:
        if mode == "0":
            spaces.insert(0, ("InpSlPips", "num", (5, 95, 5)))
        elif mode == "1":
            spaces.insert(0, ("InpSlAtrMult", "num", (0.5, 3.0, 0.25)))
        else:
            spaces.insert(0, ("InpSlUsd", "num", (5, 25, 2.5)))
    for group in dict.fromkeys(groups):
        if group != "stop":
            spaces.extend(optimizer.RISK_SPACE[group])
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year"
    o = optimizer.Optimizer(start, objective="worst_loss", min_trades=30, ds=ds, space=spaces, trade_floor_ratio=0.70, exhaustive=True)
    o.risk_groups = groups
    RISK_OPT["o"] = o
    threading.Thread(target=o.run, daemon=True).start()
    return {"ok": True, "groups": groups}


def opt_run_and_check(o):
    """The optimizer, then its best straight into one MT5 run (no delay) - the Turtle TV Tester proposes, MT5 decides."""
    o.run()
    o.mt5 = None
    best = o.best
    if not best or not {k: v for k, v in best["inputs"].items() if not same(v, o.start.get(k))}:
        return
    for _ in range(900):                                       # wait for a run that is already going
        if not STATE["busy"]:
            break
        time.sleep(2)
    rid, err = start_run({"sets": best["inputs"], "delay": "none", "label": f"optimizer best {datetime.now():%H:%M}"}, source="optimizer")
    o.mt5 = {"run": rid, "error": err}


# ---------------------------------------------------------------- the Exit Lab (exitlab.py) - Zee 2026-10-20: "create an Exit Lab tab where we can
# test out all the different kinds of exits possible. including trailing, partial close etc."
LAB = {"job": None, "tjob": None, "cat": None, "done": {}}            # job: the long ones (catalogue, search, heatmap) · tjob: one exit, the diagnosis
LAB_FEATURES = Path(__file__).parent / "asks" / "exitlab_features.json"


def _jsonable(x):
    return json.loads(json.dumps(x, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def lab_start(body):
    action = body.get("action")
    if action not in ("diagnose", "test", "catalogue", "search", "heatmap", "sweep"):
        return {"error": "unknown action"}
    slot = "tjob" if action in ("test", "diagnose") else "job"
    if LAB[slot] and LAB[slot].running:
        LAB[slot].stop()
    inputs = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv", "year1", "m1x", "m5x") else "year"
    kw = {k: body.get(k) for k in ("lab", "sets", "objective", "fx", "fy", "xs", "ys", "focus", "priority", "include") if body.get(k) is not None}
    key = json.dumps([inputs, "year" if ds == "tv" else ds], sort_keys=True)
    if action == "search" and LAB["cat"] and LAB["cat"][0] == key:
        kw["cat_rows"] = LAB["cat"][1]                    # the catalogue of the same settings: the search starts from it
    j = exitlab.Job(action, inputs, ds, **kw)
    j.key = key
    j.req = {"inputs": body.get("inputs") or {}, "ds": "year" if ds == "tv" else ds}     # what the page asked for: it warns when its settings moved on
    if action == "sweep":                                     # a scan is of a bench (settings + the bench's changes + its Exit Lab form): a page opened later must know which
        j.req.update(lab=body.get("lab") or {}, sets=body.get("sets") or {}, focus=body.get("focus") or "", priority=body.get("priority") or [], include=body.get("include") or [])
    LAB[slot] = j
    threading.Thread(target=j.run, daemon=True).start()
    return {"ok": True}


def lab_state(full=False, partial=""):
    out = {}
    seen_id, sep, seen_count = partial.rpartition(":")
    for slot, name in (("job", "main"), ("tjob", "quick")):
        j = LAB[slot]
        if not j:
            continue
        if j.done and j.result and not j.error:
            LAB["done"][j.action] = j                      # the latest result of each kind, for a page that opens later
        if j.done and j.action == "catalogue" and j.result and not j.error and not j.result.get("stopped"):
            LAB["cat"] = (j.key, j.result["rows"])               # only a complete catalogue seeds the search
        if j.error and not getattr(j, "logged", False):
            j.logged = True
            log(f"exit lab {j.action}: {getattr(j, 'tb', j.error)}")
        state = j.state()
        if not full and sep and slot == "job" and j.action == "sweep" and seen_id == j.jid and state["partial_result"]:
            try:
                if int(seen_count) >= state["partial_result"]["completed"]:
                    state["partial_result"] = None
            except ValueError:
                pass
        out[name] = state
    if full:
        out["done"] = {a: j.state() for a, j in LAB["done"].items()}
    return _jsonable(out)


def lab_feature(body):
    """'Make it an EA setting': Claude Code builds the lab's exit into the EA (off by default), mirrors it in the tester, tests it in MT5"""
    lab = exitlab.clean(body.get("lab") or {})
    if not lab:
        return {"error": "no exit"}
    if any(j["running"] and j["kind"] == "feature" for j in HJOBS.values()):
        return {"error": "Claude is already adding a feature; wait for it to finish"}
    desc = exitlab.describe(lab)
    jid = f"h{int(time.time() * 1000)}"
    job = HJOBS[jid] = {"id": jid, "kind": "feature", "key": "exitlab", "idx": 0, "running": True, "phase": "starting", "result": None, "error": None}
    prompt = f"""Zee pressed "Make it an EA setting" in Turtle TV's Exit Lab. Build this exit into the Saad 15-min EA as NEW SETTINGS, the way v1.28's
InpSkipBothEma was added (git show 8aee8953 is the template - read it first):

The exit: {desc}
As the Exit Lab's recipe (monitor/saad_view/exitlab.py field names): {json.dumps(lab)}
The Exit Lab's result on {body.get('ds', 'the data')} ({' / '.join(body.get('labels') or [])}): {json.dumps(body.get('stats') or {}, default=str)[:2500]}

The Turtle TV Tester ALREADY runs this exit: monitor/saad_view/sim_full.py, the "Exit Lab" blocks (vector E, fields E_*, built by sim_full.evec
from the recipe). Read those blocks: they are the exact rule to write in MQL5 (only for exit modes 1-2: the v1.25 exits; tick rules in
ManageTick, candle-close rules at the new candle; R = |entry - first stop|).

Do all of this, in order:
1. mt5/Saad_strategy_15min.mq5: new inputs, OFF by default (with them off, trading must be identical to now), clear comments; the rules in the
   same places as the tester runs them; bump the version (#property version, EA_COMMENT, a // vX.YY header line quoting Zee).
2. The tester: append the new input names to the END of FULL in monitor/saad_view/sim_full.py (never reorder), and in sim.simulate build the
   lab vector from them (sim_full.evec({{...}})) when no lab is passed, so the tester runs the same code. Run: py monitor/saad_view/make_view_ea.py
3. py monitor/saad_view/exitlab_regress.py check must print ALL IDENTICAL (set NUMBA_CPU_NAME=generic). Then check in Python that the new inputs ON
   reproduce the Exit Lab's numbers above (sim.simulate(server.full_inputs({{...}}), ds=...)).
4. MT5: POST http://127.0.0.1:8773/api/run with {{"sets": {{...}}, "label": "...", "delay": "none"}} for off and on (one at a time; poll /api/status
   until busy is false; results in monitor/saad_view/runs/<id>.json "report"). If the server is down, say so and skip.
5. A row in VERSION.md (the Saad_strategy_15min table + "Which EA is which") and an entry in VERSION_HISTORY.md, then git add ONLY the files you
   changed and commit (end the message with: Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>).
Never edit LAWS.md. Never push. Python numbers are hypotheses; MT5 decides - say "keep it off" if MT5 does not beat the current version.
Finish with a short report for Zee (plain English, under 15 lines): the settings' names, what they do, the MT5 numbers off vs on, your verdict."""

    def go():
        try:
            job["phase"] = "Claude is building the exit into the EA, the tester and MT5 (several minutes)"
            txt = _claude(prompt, ["Read", "Grep", "Glob", "Edit", "Write", "Bash(py:*)", "Bash(python:*)", "Bash(git add:*)", "Bash(git commit:*)",
                                   "Bash(git show:*)", "Bash(git diff:*)", "Bash(git status:*)", "Bash(curl:*)", "Bash(sleep:*)"], timeout=3600)
            job["result"] = {"which": desc, "report": txt, "at": datetime.now().strftime("%Y-%m-%d %I:%M %p")}
            try:
                prev = json.loads(LAB_FEATURES.read_text(encoding="utf-8"))
            except Exception:                                   # noqa: BLE001
                prev = []
            prev.append(dict(job["result"], lab=lab))
            LAB_FEATURES.parent.mkdir(parents=True, exist_ok=True)
            LAB_FEATURES.write_text(json.dumps(prev, indent=1, ensure_ascii=False), encoding="utf-8")
        except Exception as e:                                  # noqa: BLE001
            job["error"] = str(e)
        finally:
            job["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"id": jid}


# ---------------------------------------------------------------- Claude's exit research (Zee 2026-10-21: "i want it to be a claude intelligence ai based
# lab where the exit's philosophy is refined by claude by doing research and bringing in improvements which matter intelligently rather than just some
# math values being tweaked"). Claude runs the Exit Lab itself (exitlab_cli.py), studies WHY, and proposes exits; every proposal is then re-tested here.
RESEARCH = Path(__file__).parent / "asks" / "exitlab_research.json"


def _research_list():
    try:
        return json.loads(RESEARCH.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return []


def lab_research(body):
    if any(j["running"] and j["kind"] == "research" for j in HJOBS.values()):
        return {"error": "Claude is already researching; wait for it to finish"}
    inputs = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year"
    q = (body.get("question") or "").strip() or "Study my exit and make it better."
    jid = f"r{int(time.time() * 1000)}"
    base_file = RESEARCH.parent / f"research_{jid}_settings.json"
    base_file.parent.mkdir(parents=True, exist_ok=True)
    base_file.write_text(json.dumps(inputs), encoding="utf-8")
    job = HJOBS[jid] = {"id": jid, "kind": "research", "running": True, "phase": "starting", "result": None, "error": None}
    cli = f'py monitor/saad_view/exitlab_cli.py --base "{base_file}" --ds {ds}'
    prompt = f"""You are the head of Turtle TV's Exit Lab, researching the EXIT of Zee's Saad gold EA (XAUUSD, 15-minute candles, 2 lots). The entries
stay as they are; your job is the exit's PHILOSOPHY - understand WHY it leaves money, then design better exits from that understanding, not by
tweaking numbers at random.

Zee's question: {q}

Your instrument (run it as often as you need; JSON out; Python tester numbers are hypotheses until MT5 confirms them):
  {cli} diagnose                       where the exit leaves money (best move vs result, after-exit behaviour, reasons)
  {cli} givebacks --n 30               the winners that gave back the most, with context (hour, ADX, ATR, bars held, how they ended)
  {cli} slice --by mfe_r|bars|hour|weekday|side|year|adx|atr|why     where the giveback / losses sit
  {cli} test --lab '{{...}}' [--sets '{{"InpSlAtrMult": "1.4"}}']     any exit (the fields: py monitor/saad_view/exitlab_cli.py blocks)
The data: {'Blueberry 2023 - now (4 years); choose on 2023-2024, judge on 2025-2026' if ds == 'm15' else '2026; choose on Jan-Jun, judge on Jul-Oct'}.
Settings on screen (differences from the defaults): {json.dumps({k: v for k, v in inputs.items() if not same(v, axi_rig.ea_defaults(EA).get(k))})}
You may read the code (monitor/saad_view/sim_full.py Exit Lab blocks, mt5/Saad_strategy_15min.mq5) and LAWS.md (Zee's rules - never edit anything).

Method:
1. Diagnose. Then find the MECHANISM: which trades give back (by best move, bars, hour, ADX, side...), what the market did at their peak, and why
   the current rules let it go (e.g. the EMA target sits far away while the move fades; the fallback waits for a close across the fast EMA...).
2. Write 2-4 hypotheses about the mechanism, each with the evidence from your runs.
3. Design 2-4 exits that follow from them (not a grid search), test each, and keep the honest result: both halves, the win rate (Zee cares about it),
   BUY vs SELL (2023-2026 was a gold bull market), and "stuck" (an exit that never closes some trades is unusable). Prefer simple, robust ideas;
   say plainly when an idea failed. MT5 evidence on file: rules that close trades between the stop and the target have cost money before.
4. Answer in English, for Zee: the mechanism (short), the evidence, what you propose and why, what failed. Under 40 lines.
5. END with exactly one line `PROPOSALS:` followed by a JSON array, no code fence:
   [{{"name": "<short>", "lab": {{...exit lab fields...}}, "sets": {{...EA inputs, usually {{}}...}}, "philosophy": "<one sentence: the idea>"}}]"""

    def go():
        try:
            job["phase"] = "Claude is studying the exit (runs experiments, several minutes)"
            txt = _claude(prompt, ["Read", "Grep", "Glob", "Bash(py:*)", "Bash(python:*)"], timeout=2400)
            props = []
            if "PROPOSALS:" in txt:
                tail = txt.rsplit("PROPOSALS:", 1)[1]
                m = re.search(r"\[.*\]", tail, re.S)
                if m:
                    try:
                        props = json.loads(m.group(0))
                    except Exception:                       # noqa: BLE001
                        props = []
                txt = txt.rsplit("PROPOSALS:", 1)[0].strip()
            job["phase"] = "re-testing every proposal independently"
            win, labels = exitlab.window_of(ds, inputs)
            _, b, boe = exitlab.run(inputs, ds)
            bs = exitlab.stats(b, win, open_end=boe)
            for pr in props[:6]:
                lab = exitlab.clean(pr.get("lab") or {}) if pr.get("lab") else {}
                lab = lab if [f for f in lab if f != "pess"] else {}
                sets = {k: str(v) for k, v in (pr.get("sets") or {}).items()}
                if lab and str(dict(inputs, **sets).get("InpExitMode")) not in ("1", "2"):
                    sets["InpExitMode"] = "1"
                _, r, oe = exitlab.run(inputs, ds, lab=lab or None, sets=sets)
                s = exitlab.stats(r, win, open_end=oe)
                pr["lab"], pr["sets"], pr["describe"] = lab, sets, exitlab.describe(lab) if lab else "the EA's own exit"
                pr["verified"] = {"train": s["train"], "test": s["test"], "total": s["total"], "wr": s["all"]["wr"], "pf": s["all"]["pf"], "dd": s["all"]["dd"],
                                  "sides": s["sides"], "stuck": s["stuck"]}
            rep = {"id": jid, "at": datetime.now().strftime("%Y-%m-%d %I:%M %p"), "question": q, "ds": ds, "labels": labels, "report": txt, "proposals": props[:6],
                   "base": {"train": bs["train"], "test": bs["test"], "total": bs["total"], "wr": bs["all"]["wr"]}, "inputs": inputs}
            allr = _research_list()
            allr.insert(0, rep)
            RESEARCH.write_text(json.dumps(allr[:30], indent=1, ensure_ascii=False, default=str), encoding="utf-8")
            job["result"] = {"id": jid}
        except Exception as e:                                  # noqa: BLE001
            job["error"] = str(e)
            log("research: " + traceback.format_exc())
        finally:
            job["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"id": jid}


# ---------------------------------------------------------------- the Machine Learning tab (ml.py)
MLJ = {"job": None}


def ml_start(body):
    if MLJ["job"] and MLJ["job"].running:
        MLJ["job"].stop()
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv", "year1", "m1x", "m5x") else "year"
    MLJ["job"] = ml.start(full_inputs(body.get("inputs") or {}), ds, [a for a in (body.get("algos") or []) if a in ml.ALGOS], body.get("thr") or 0.5)
    return {"ok": True}


def ml_state():
    j = MLJ["job"]
    if not j:
        return {}
    if j.error and not getattr(j, "logged", False):
        j.logged = True
        log("ml: " + getattr(j, "tb", j.error))
    return _jsonable(j.state())


# ---------------------------------------------------------------- the Machine Learning tab, first block: the institutional entry filter (mlx/run.py)
# Zee 2026-11-01: Triple Barrier labels -> Purged K-Fold CV (24-bar embargo) -> SHAP pruning -> LightGBM + CatBoost stacked into a
# LogisticRegression -> ONNX -> the EA (OnnxRun at every M15 close, enters only when P > 0.75). The pipeline writes simdata/mlx_results.json;
# this is its remote control: one job at a time, the page polls GET /api/mlx. Until the real file exists the page gets the fixture, "sample": true.
MLX = {"running": False, "phase": "", "progress": 0, "total": 0, "t0": None, "seconds": 0, "error": None}
MLX_RESULTS = HERE / "simdata" / "mlx_results.json"
MLX_SAMPLE = HERE / "simdata" / "mlx_results.sample.json"
MLX_SPEC = HERE / "mlx" / "FEATURE_SPEC.md"


def mlx_state():
    out = {k: MLX[k] for k in ("running", "phase", "progress", "total", "error")}
    out["seconds"] = round(time.time() - MLX["t0"], 1) if MLX["running"] and MLX["t0"] else MLX["seconds"]
    out["result"], out["sample"], out["built_module"] = None, False, (HERE / "mlx" / "run.py").is_file()
    for f, sample in ((MLX_RESULTS, False), (MLX_SAMPLE, True)):
        if f.is_file():
            try:
                out["result"], out["sample"] = json.loads(f.read_text(encoding="utf-8")), sample
                break
            except (OSError, ValueError) as e:
                out["error"] = out["error"] or f"{f.name}: {e}"
    return _jsonable(out)


def mlx_start(body):
    """POST /api/mlx {} -> the whole pipeline in a background thread: mlx.run.run(progress_cb)"""
    if MLX["running"]:
        return {"error": "the pipeline is already running"}
    try:
        import mlx.run as mlx_run                             # lazy: monitor/saad_view/mlx/run.py, built by the pipeline agent
    except Exception as e:                                    # noqa: BLE001
        if not (HERE / "mlx" / "run.py").is_file():
            return {"error": "the pipeline is not built yet"}
        return {"error": f"mlx.run does not import: {e}"[:400]}

    def cb(phase=None, progress=None, total=None, **kw):     # tolerant: cb("phase", i, n) · cb(phase=.., progress=.., total=..) · cb({...})
        if isinstance(phase, dict):
            kw, phase = {**phase, **kw}, phase.get("phase")
        if phase is not None:
            MLX["phase"] = str(phase)[:200]
        progress = kw.get("progress", kw.get("i", progress))
        total = kw.get("total", kw.get("n", total))
        if progress is not None:
            MLX["progress"] = int(progress)
        if total is not None:
            MLX["total"] = int(total)

    def go():
        try:
            res = mlx_run.run(cb)
            if isinstance(res, dict) and res.get("built") and (not MLX_RESULTS.is_file() or MLX_RESULTS.stat().st_mtime < MLX["t0"]):
                MLX_RESULTS.parent.mkdir(exist_ok=True)      # run.py writes the file itself; a returned dict is kept only if it did not
                MLX_RESULTS.write_text(json.dumps(_jsonable(res), indent=1), encoding="utf-8")
            MLX["phase"] = "done"
        except Exception as e:                                # noqa: BLE001
            MLX["error"] = str(e)[:400]
            log("mlx: " + traceback.format_exc())
        finally:
            MLX["seconds"], MLX["running"] = round(time.time() - MLX["t0"], 1), False
    MLX.update(running=True, t0=time.time(), seconds=0, error=None, phase="starting", progress=0, total=0)
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True}


# ---------------------------------------------------------------- Strategy Lego (lego.py): replace the core pieces of the strategy
def lego_test(body):
    inputs = full_inputs(dict(body.get("inputs") or {}, **(body.get("sets") or {})))
    base_in = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "year1", "m1x", "m5x") else "year"
    lego = {k: v for k, v in (body.get("lego") or {}).items() if k in ("ma", "loc", "candle", "loc_k", "mom_body", "mom_atr")}
    win, labels = exitlab.window_of(ds, base_in)
    out = {"labels": labels, "ds": ds}
    for nm, inp, lg in (("lego", inputs, lego), ("yours", base_in, None)):
        tr, _, oe = sim.simulate(inp, ds=ds, lego=lg or None)
        real = tr[tr[:, 10] == 0]
        s = exitlab.stats(real, win)
        out[nm] = {"train": s["train"], "test": s["test"], "total": s["total"], "all": s["all"], "sides": s["sides"], "years": s["years"]}
    return _jsonable(out)


# ---------------------------------------------------------------- Mission Control (mission.py): the size, the days, the futures, the guardrails
MIS = {"job": None}


def mission_start(body):
    lab = exitlab.clean(body.get("lab") or {}) if body.get("lab") else None
    lab = lab if lab and [f for f in lab if f != "pess"] else None
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv", "year1", "m1x", "m5x") else "year"
    MIS["job"] = mission.start(full_inputs(body.get("inputs") or {}), ds, lab, body.get("capital") or 1000, body.get("mode") or "risk", body.get("lots") or 0.01,
                               body.get("risk_pct") or 1, body.get("leverage") or 500, body.get("max_dd") or 20,
                               {k: v for k, v in (body.get("lego") or {}).items() if k in ("ma", "loc", "candle", "loc_k", "mom_body", "mom_atr")} or None)
    return {"ok": True}


def mission_state():
    j = MIS["job"]
    if not j:
        return {}
    if j.error and not getattr(j, "logged", False):
        j.logged = True
        log("mission: " + getattr(j, "tb", j.error))
    return _jsonable(j.state())


# ---------------------------------------------------------------- the Stress Lab (stress.py): 32 robustness tests on the settings on screen
ST = {"running": False, "progress": 0, "total": 32, "phase": "", "result": None, "error": None, "t0": None, "req": None}


def stress_start(body):
    if ST["running"]:
        return {"error": "the stress tests are already running"}
    inp = full_inputs(body.get("inputs") or {})
    ST.update(running=True, progress=0, phase="starting", result=None, error=None, t0=time.time(), req=body.get("inputs") or {})

    def go():
        try:
            def prog(n, name):
                ST["progress"], ST["phase"] = n, name
            ST["result"] = stress.run_all(inp, prog)
        except Exception as e:                                  # noqa: BLE001
            ST["error"] = str(e)
            log("stress: " + traceback.format_exc())
        finally:
            ST["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True}


def stress_state():
    return _jsonable(dict({k: v for k, v in ST.items() if k != "t0"}, seconds=round(time.time() - ST["t0"], 1) if ST["t0"] else 0))


# ---------------------------------------------------------------- Research page (papers/): a PDF -> a headless Claude Fable 5.1 job -> a saved setting
# Zee 2026-11-01: "i zeeshan reads a research paper on the internet -> downloads it -> gives it to claude via this webpage to parse and build into an EA
# and test and validate and finally save the results in a list from which i can then pick it up by clicking Save setting". The runner is
# papers/job.py (no server import); the store is papers/store/<id>/ (pdf, txt, meta, prompt, logs, result.json, setting.json - contract in papers/README.md).
import papers.job as pjob  # noqa: E402
import deploy as deploy_mod  # noqa: E402  (Zee 2026-11-02: the Deploy tab + "Deploy EA to Server")

PAPERS = pjob.STORE
SAVED_NAME_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]|\.\.')      # a saved-setting name is a file name: nothing that leaves the folder


def _safe_saved_name(n):
    n = str(n or "").strip()
    return bool(n) and len(n) <= 150 and not SAVED_NAME_BAD.search(n)


def _paper_slug(name):
    stem = re.sub(r"\.pdf$", "", str(name or "paper"), flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "paper"
    return stem[:40].rstrip("._-") or "paper"


def _pdf_text(path):
    """pypdf text of every page, pages separated by a form feed; ('', 0) when pypdf cannot read it."""
    try:
        import pypdf
        r = pypdf.PdfReader(str(path))
        pages = [(pg.extract_text() or "") for pg in r.pages]
        return "\n\f\n".join(pages), len(pages)
    except Exception as e:                                    # noqa: BLE001
        log(f"research: pypdf failed on {path}: {e}")
        return "", 0


def _pdf_title(text):
    """The title = the first non-empty lines of page 1 joined, until a blank line / an 'Author:' kind of line / 4 lines / 200 chars (pypdf wraps it)."""
    lines = [ln.strip() for ln in text.split("")[0].splitlines()]
    while lines and len(lines[0]) <= 3:
        lines.pop(0)
    out = []
    stop = re.compile(r"^(author|authors|by|abstract|subject|date|keywords|department|university|institute|school|college|\d|.*@.*|.*et al)", re.I)
    for ln in lines[:8]:
        if not ln or (out and stop.match(ln)) or len(" ".join(out + [ln])) > 200 or len(out) >= 4:
            break
        out.append(ln)
    return " ".join(out).strip()


# ---------------------------------------------------------------- Range boxes: B's loser-cutting filters measured on any setting (Zee 2026-11-02)
# Each group = inputs of 2026-10-30 23-08-23 that the setting may not have. For the setting on the chart the tester runs it once per group
# (and once with every entry group on) and attributes every trade that disappears to winner / loser. Turtle TV Tester = hypothesis.
LCF_GROUPS = [                                            # (key, B's values = box ON, neutral values = box OFF) - mirrors static/app.js LCF
    ("gap", {"InpEmaGapPips": "22.5"}, {"InpEmaGapPips": "0"}),
    ("sess", {"InpSessTo": "19", "InpHours": "111111111110111111111111"}, {"InpSessTo": "24", "InpHours": "1" * 24}),
    ("bands", {"InpBandsB": "111111101111001111110", "InpBandsS": "111110100000101001101", "InpBandOff": "1"}, {"InpBandsB": "1" * 21, "InpBandsS": "1" * 21, "InpBandOff": "0"}),
    ("shape", {"InpHamRatio": "2.25", "InpHamNose": "0.8", "InpNoseMax": "0.05", "InpStar": "false"}, {"InpHamRatio": "1.25", "InpHamNose": "0.5", "InpNoseMax": "0.15", "InpStar": "true"}),
    ("touch", {"InpTouchPips": "3.5", "InpMinRangeAtr": "0.8"}, {"InpTouchPips": "6.5", "InpMinRangeAtr": "0.75"}),
    ("day", {"InpDayTargetUsd": "2000", "InpDayLossPct": "2"}, {"InpDayTargetUsd": "0", "InpDayLossPct": "0"}),
    ("tvbox", {"TvBox_kelt_S": "110111111111", "TvBox_vwap_B": "11101111"}, {"TvBox_kelt_S": "1" * 12, "TvBox_vwap_B": "1" * 8}),
    ("exits", {"InpXFriHour": "22", "InpXCx": "0", "InpXCxN": "2"}, {"InpXFriHour": "0", "InpXCx": "0", "InpXCxN": "2"}),
]
LCF = {"running": False, "key": None, "phase": "", "rows": {}, "base": None, "error": None, "secs": 0}
LCF_SCAN = HERE / "research" / "filter_scan_C.json"
LCF_B_NAMES = {"gap": "B · EMA gap ≥ 22.5 pips", "sess": "B · session to 19:00 + hour 11 off", "bands": "B · price bands B/S + BandOff", "shape": "B · stricter hammer shape, no stars",
               "touch": "B · touch 3.5 pips + MinRangeAtr 0.8", "day": "B · day caps $2000 target / 2% loss", "tvbox": "B · TvBox kelt_S / vwap_B masks", "exits": "B · exits (Friday 22h, no candle exit)"}


def lcf_catalog(top=20):
    """GET /api/lcf_catalog -> the boxes of the loser-cutting table: B's 8 groups + the top-N single filters of the all-saves scan on C
    (ranked by the net of the trades they cut; off value = C's value for that input, else the EA default)"""
    groups = [{"key": k, "name": LCF_B_NAMES[k], "set": on, "off": off, "source": "B 2026-10-30 23-08-23"} for k, on, off in LCF_GROUPS]
    scan = None
    if LCF_SCAN.is_file():
        try:
            scan = json.loads(LCF_SCAN.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            scan = None
    if scan:
        rows = [r for r in scan.get("rows", []) if "error" not in r and r.get("cut_losers", 0) >= 2]
        rows.sort(key=lambda r: (r["cut_net"], -(r["selectivity"] or 0)))
        seen = {tuple(sorted(on.items())) for _, on, _ in LCF_GROUPS}
        for r in rows:
            if len([g for g in groups if g["source"] == "scan"]) >= top:
                break
            on = {r["input"]: r["value"]}
            if tuple(on.items()) in seen:
                continue
            groups.append({"key": f"scan_{r['input']}_{re.sub(r'[^A-Za-z0-9]', '', r['value'])[:24]}", "name": f"{r['input'].replace('Inp', '')} = {r['value']} (used by {r['used_by']} saves)",
                           "set": on, "off": {r["input"]: r.get("c_value") if r.get("c_value") not in (None, "None") else r["default"]}, "source": "scan",
                           "on_c": {k: r[k] for k in ("cut_n", "cut_losers", "cut_winners", "cut_net", "d_net", "selectivity")}})
        info = {"candidates": len(scan.get("rows", [])), "secs": scan.get("secs"), "complete": "top20_by_cut_net" in scan}
    else:
        info = {"candidates": 0, "complete": False}
    return {"groups": groups, "scan": info}


def _lcf_trades(inputs, ds):
    tr, _, _ = sim.simulate(full_inputs(inputs), ds=ds)
    tr = tr[tr[:, 10] == 0]
    return {(int(r[11]), 1 if r[0] > 0 else -1): float(r[6]) for r in tr}


def lcf_start(body):
    """POST /api/lcf {inputs, ds} -> runs B's filter groups on these inputs in a thread; GET /api/lcf polls"""
    if body.get("stop"):                                         # the page's "stop auto-measuring": finish the current tester run, skip the rest
        LCF["stop"] = True
        return {"ok": True, "stopping": LCF["running"]}
    if LCF["running"]:
        return {"error": "already measuring"}
    inputs = {k: str(v) for k, v in (body.get("inputs") or {}).items()}
    ds = body.get("ds") or "m15"
    key = hashlib.md5(json.dumps([inputs, ds], sort_keys=True).encode()).hexdigest()[:12]
    if LCF["key"] == key and LCF["rows"]:
        return {"ok": True, "cached": True, "key": key}
    if body.get("probe"):                                        # the page asking "is there a measurement for these inputs?" without starting one
        return {"ok": True, "key": key, "have": False}

    def go():
        t0 = time.time()
        try:
            base = _lcf_trades(inputs, ds)
            losers = {k for k, p in base.items() if p <= 0}; winners = set(base) - losers
            LCF.update(base={"n": len(base), "losers": len(losers), "winners": len(winners), "net": round(sum(base.values()))}, rows={})
            cat = lcf_catalog()["groups"]
            groups = [(g["key"], g["set"], g["off"]) for g in cat] + [("all", {k: v for g in LCF_GROUPS if g[0] != "exits" for k, v in g[1].items()}, {k: v for g in LCF_GROUPS if g[0] != "exits" for k, v in g[2].items()})]
            for i, (name, on, off) in enumerate(groups):
                if LCF.get("stop"):
                    LCF["phase"] = f"stopped after {i} of {len(groups)}"; break
                LCF["phase"] = f"{name} ({i + 1}/{len(groups)})"
                already = all(str(inputs.get(k)) == v for k, v in on.items())
                inp = dict(inputs); inp.update(off if already else on)      # a box the setting already has: measure what it is cutting NOW (run with it off)
                t = _lcf_trades(inp, ds)
                cut = {k: base[k] for k in set(base) - set(t)} if not already else {k: t[k] for k in set(t) - set(base)}   # the trades the box removes
                new = {k: t[k] for k in set(t) - set(base)} if not already else {k: base[k] for k in set(base) - set(t)}   # trades that APPEAR when the box is applied (freed positions)
                cl = {k for k, p in cut.items() if p <= 0}; cw = set(cut) - cl
                nl, nw = (len(losers), len(winners)) if not already else (sum(p <= 0 for p in t.values()), sum(p > 0 for p in t.values()))
                sel = (len(cl) / max(1, nl)) / (len(cw) / max(1, nw)) if cw else (float("inf") if cl else None)
                LCF["rows"][name] = {"added_n": len(new), "added_net": round(sum(new.values())), "cut_n": len(cut), "cut_wr": round(100 * len(cw) / max(1, len(cut)), 1) if cut else None, "cut_net": round(sum(cut.values())),
                                     "removed_losers": len(cl), "removed_winners": len(cw), "with_n": len(t) if not already else len(base), "with_wr": round(100 * sum(p > 0 for p in (t if not already else base).values()) / max(1, len(t if not already else base)), 2),
                                     "with_net": round(sum((t if not already else base).values())), "without_net": round(sum((base if not already else t).values())),
                                     "selectivity": None if sel is None else (999 if sel == float("inf") else round(sel, 2)), "already_on": already}
            if not LCF.get("stop"):
                LCF["phase"] = "done"
        except Exception as e:                                    # noqa: BLE001
            LCF["error"] = str(e)[:300]; log("lcf: " + traceback.format_exc())
        finally:
            LCF["secs"], LCF["running"] = round(time.time() - t0), False
    LCF.update(running=True, key=key, phase="starting", rows={}, base=None, error=None, stop=False)
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True, "key": key}


def research_upload(body):
    """POST /api/research_upload {name, b64} -> store entry (paper.pdf, paper.txt, meta.json) -> {ok, id, title, pages}"""
    name = str(body.get("name") or "paper.pdf")
    raw = base64.b64decode(str(body.get("b64") or "").split(",")[-1] or b"", validate=False)
    if not raw:
        return {"error": "empty upload"}
    return _research_store(name, raw, source_url=None)


RESEARCH_DIR = ROOT / "research"                            # Zee's own folder of downloaded papers (a copy of every URL fetch lands here too)


def research_url(body):
    """POST /api/research_url {url, base?, notes?, start?} -> downloads a .pdf URL, keeps a copy in turtle/research/, stores it like an upload
    and (start true, the default) begins the build at once -> {ok, id, title, pages, saved_copy, build}"""
    url = str(body.get("url") or "").strip()
    if not re.match(r"^https?://", url, flags=re.I):
        return {"error": "the URL must start with http:// or https://"}
    if not re.search(r"\.pdf(\?|#|$)", url, flags=re.I):
        return {"error": "the URL must end with .pdf"}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Turtle TV research fetch)"})
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(61 * 1024 * 1024)
    except Exception as e:                                    # noqa: BLE001
        return {"error": f"download failed: {str(e)[:200]}"}
    name = re.sub(r"[?#].*$", "", url.rsplit("/", 1)[-1]) or "paper.pdf"
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", urllib.parse.unquote(name))[:120]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    out = _research_store(name, raw, source_url=url)
    if out.get("error"):
        return out
    try:                                                      # Zee: "download and keep it in the research folder"
        RESEARCH_DIR.mkdir(exist_ok=True)
        copy = RESEARCH_DIR / name
        if copy.exists():
            copy = RESEARCH_DIR / f"{copy.stem} {out['id'][:19]}{copy.suffix}"
        copy.write_bytes(raw)
        out["saved_copy"] = str(copy)
    except OSError as e:
        out["saved_copy_error"] = str(e)[:200]
    if body.get("start", True):
        out["build"] = research_build({"id": out["id"], "base": body.get("base"), "notes": body.get("notes")})
    return out


def _research_store(name, raw, source_url=None):
    """a PDF's bytes -> papers/store/<id>/ (paper.pdf, paper.txt, meta.json) -> {ok, id, title, pages}"""
    if not raw.startswith(b"%PDF"):
        return {"error": "not a PDF (the file does not start with %PDF)"}
    if len(raw) > 60 * 1024 * 1024:
        return {"error": "PDF over 60 MB"}
    pid = datetime.now().strftime("%Y-%m-%d %H-%M-%S") + "-" + _paper_slug(name)
    d = PAPERS / pid
    for _ in range(3):                                        # two uploads in the same second
        if not d.exists():
            break
        time.sleep(1)
        pid = datetime.now().strftime("%Y-%m-%d %H-%M-%S") + "-" + _paper_slug(name)
        d = PAPERS / pid
    d.mkdir(parents=True, exist_ok=False)
    (d / "paper.pdf").write_bytes(raw)
    text, pages = _pdf_text(d / "paper.pdf")
    (d / "paper.txt").write_text(text, encoding="utf-8")
    title = _pdf_title(text) or re.sub(r"\.pdf$", "", name, flags=re.I)
    title = title.replace(",", " ")
    meta = {"id": pid, "file": name, "title": title, "uploaded": pjob.now(), "pages": pages, "bytes": len(raw), "base_setting": None,
            "status": "uploaded", "started": None, "finished": None, "error": None, "exit_code": None, "phase": "", "notes": "", "source_url": source_url}
    pjob.write_json(d / "meta.json", meta)
    log(f"research: {'fetched ' + source_url if source_url else 'uploaded'} {pid} ({pages} pages, {len(raw)} bytes)")
    return {"ok": True, "id": pid, "title": title, "pages": pages}


def research_list():
    """GET /api/research -> {papers: [meta + result + has_setting], running, claude: {exe, found}, bases, default_base}"""
    PAPERS.mkdir(parents=True, exist_ok=True)
    out = []
    for d in sorted(PAPERS.iterdir(), reverse=True):
        if not d.is_dir() or not (d / "meta.json").is_file():
            continue
        m = pjob.read_json(d / "meta.json") or {"id": d.name}
        res = pjob.read_json(d / "result.json")
        if res and not res.get("base_mt5") and (res.get("base_setting") or {}).get("name"):     # fill the base's MT5 rows from mt5_years.json when the job did not
            res["base_mt5"] = pjob.mt5_rows_for("save:" + res["base_setting"]["name"])
        if res and not res.get("mt5") and not res.get("dry"):
            res["mt5"] = pjob.mt5_rows_for("save:" + pjob.candidate_name(d.name))
        m["result"] = res
        m["has_setting"] = (d / "setting.json").is_file()
        m["has_log"] = (d / "log.txt").is_file()
        m["candidate_saved"] = (SAVED / f"{pjob.candidate_name(d.name)}.json").is_file()
        out.append(m)
    exe = pjob.find_claude()
    return _jsonable({"papers": out, "running": pjob.state(), "claude": {"exe": exe, "found": bool(exe), "version": pjob.claude_version(exe)},
                      "bases": pjob.saved_names(), "default_base": pjob.default_base(), "ea_version": pjob.ea_version()})


def research_build(body):
    """POST /api/research_build {id, base?, notes?, dry?} -> starts papers/job.py in a thread (one job at a time)"""
    pid = str(body.get("id") or "")
    if not pjob.ID_RE.match(pid) or not (PAPERS / pid / "meta.json").is_file():
        return {"error": "no such paper"}
    if pjob.busy():
        return {"error": f"a research job is already running ({pjob.state()['id']}) - one at a time"}
    dry = bool(body.get("dry"))
    base = str(body.get("base") or "") or pjob.default_base()
    if not base or not (SAVED / f"{base}.json").is_file():
        return {"error": f"base saved setting not found: {base}"}
    if not dry and not pjob.find_claude():
        return {"error": "claude.exe not found (no anthropic.claude-code-* VS Code extension and no 'claude' on PATH)"}
    notes = str(body.get("notes") or "")[:4000]

    def go():
        try:
            pjob.run(pid, base, notes, dry=dry)
        except Exception as e:                                # noqa: BLE001
            log("research job: " + traceback.format_exc())
            pjob.update_meta(pid, status="failed", error=str(e)[:400], finished=pjob.now())
    threading.Thread(target=go, daemon=True).start()
    for _ in range(20):                                       # let the thread claim the job so the page's next poll sees it running
        if pjob.busy() or (pjob.read_json(PAPERS / pid / "meta.json") or {}).get("status") in ("done", "failed"):
            break
        time.sleep(0.05)
    return {"ok": True, "id": pid, "base": base, "dry": dry}


def research_assist(body):
    """POST /api/research_assist {id, dry?} -> second Claude job: implement the EA code the candidate needs"""
    pid = str(body.get("id") or "")
    if not pjob.ID_RE.match(pid) or not (PAPERS / pid / "result.json").is_file():
        return {"error": "no such paper or no result.json yet"}
    if pjob.busy():
        return {"error": f"a research job is already running ({pjob.state()['id']}) - one at a time"}
    dry = bool(body.get("dry"))
    if not dry and not pjob.find_claude():
        return {"error": "claude.exe not found"}

    def go():
        try:
            pjob.run(pid, None, (pjob.read_json(PAPERS / pid / "meta.json") or {}).get("notes", ""), dry=dry, kind="assist")
        except Exception as e:                                # noqa: BLE001
            log("research assist: " + traceback.format_exc())
    threading.Thread(target=go, daemon=True).start()
    for _ in range(20):
        if pjob.busy():
            break
        time.sleep(0.05)
    return {"ok": True, "id": pid, "dry": dry}


def research_log(pid, n=200):
    if not pjob.ID_RE.match(pid or "") or not (PAPERS / pid).is_dir():
        return {"error": "no such paper"}
    m = pjob.read_json(PAPERS / pid / "meta.json") or {}
    lines = []
    for f in ("log.txt", "log_assist.txt"):
        p = PAPERS / pid / f
        if p.is_file():
            try:
                lines += p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
            except OSError:
                pass
    st = pjob.state()
    return {"lines": lines[-n:], "status": m.get("status"), "phase": (st or {}).get("phase") or m.get("phase", ""), "error": m.get("error"),
            "running": bool(st and st["id"] == pid), "seconds": (st or {}).get("seconds") if st and st["id"] == pid else None, "assist": m.get("assist")}


def research_save(body):
    """POST /api/research_save {id} -> settings/saved/<stamp> 📄 <short title>.json with "source" provenance -> {ok, name, needs_code}"""
    pid = str(body.get("id") or "")
    d = PAPERS / pid
    if not pjob.ID_RE.match(pid) or not (d / "setting.json").is_file():
        return {"error": "no setting.json for this paper yet (the build has to finish first)"}
    cand = pjob.read_json(d / "setting.json")
    res = pjob.read_json(d / "result.json") or {}
    meta = pjob.read_json(d / "meta.json") or {}
    if not cand or not isinstance(cand.get("inputs"), dict):
        return {"error": "setting.json has no inputs"}
    title = str(res.get("title") or meta.get("title") or meta.get("file") or pid)
    short = re.sub(r"\s+", " ", SAVED_NAME_BAD.sub(" ", title.replace(",", " "))).strip()[:48].strip()
    SAVED.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    name = f"{stamp} 📄 {short}".strip()
    while (SAVED / f"{name}.json").exists():
        time.sleep(1)
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        name = f"{stamp} 📄 {short}".strip()
    dfl = axi_rig.ea_defaults(EA)
    inp = full_inputs(cand["inputs"])
    needs = res.get("needs_code") or cand.get("needs_code") or {"required": False}
    rec = {"name": name, "inputs": inp, "changed": {k: v for k, v in inp.items() if not same(v, dfl.get(k))},
           "ds": cand.get("ds") or "m15", "mode": cand.get("mode") or "ea", "result": cand.get("result") or (res.get("tester") or None),
           "lab": cand.get("lab") or {}, "lab_describe": cand.get("lab_describe") or "",
           "note": cand.get("note") or f"from research paper {title}",
           "source": {"kind": "research_paper", "paper": title, "id": pid, "pdf": meta.get("file"), "built": res.get("built") or meta.get("finished"),
                      "needs_code": needs, "base_setting": (res.get("base_setting") or {}).get("name") or meta.get("base_setting"),
                      "mt5": res.get("mt5"), "verdict": res.get("verdict"), "dry": bool(res.get("dry") or cand.get("dry"))}}
    (SAVED / f"{name}.json").write_text(json.dumps(_jsonable(rec), indent=1, ensure_ascii=False), encoding="utf-8")
    saved_as = list(meta.get("saved_as") or []) + [name]
    pjob.update_meta(pid, saved_as=saved_as, saved_at=pjob.now())
    log(f"research: saved {pid} as {name}")
    return {"ok": True, "name": name, "needs_code": needs}


def research_delete(body):
    pid = str(body.get("id") or "")
    if not pjob.ID_RE.match(pid):
        return {"error": "bad id"}
    st = pjob.state()
    if st and st["id"] == pid:
        pjob.stop(pid)
        time.sleep(1)
    d = PAPERS / pid
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
    (SAVED / f"{pjob.candidate_name(pid)}.json").unlink(missing_ok=True)     # the job's MT5 candidate; the 📄 provenance copies are Zee's and stay
    return {"ok": True, "removed": not d.exists()}


# ---------- HTTP ----------
# ---------------------------------------------------------------- reload speed (Zee 2026-11-03: "if the default setting is not changed ... pick up some
# sort of cached values to quickly load the page"). The tester is deterministic: the encoded /api/sim answer is cached by a key of (inputs, ds, mode, lab,
# prune, ema, setups) + the engine files' and data files' mtimes, in memory and on disk (simdata/sim_cache), so a reload with an unchanged setting
# skips the 5-20 s run. gzip of the big answers is cached too.
import gzip as _gzip
SIM_CACHE_DIR = HERE / "simdata" / "sim_cache"
_SIM_MEM = {}                                               # key -> encoded JSON bytes (newest 16)
_GZ_MEM = {}                                                # id(bytes)/hash -> gzipped bytes


def _engine_stamp():
    files = [HERE / f for f in ("sim.py", "sim_full.py", "exitlab.py", "lifecycle.py", "lego.py", "uhv_engine.py", "simdata/uhv_setups.json")] + sorted((HERE / "simdata").glob("m15*.np*")) + sorted((HERE / "simdata").glob("year*.np*")) + sorted((HERE / "simdata").glob("tv*.np*"))
    return "|".join(f"{f.name}:{int(f.stat().st_mtime)}" for f in files if f.is_file())


def _gz(b):
    h = hashlib.sha1(b).hexdigest()
    g = _GZ_MEM.get(h)
    if g is None:
        g = _gzip.compress(b, compresslevel=3)
        if len(_GZ_MEM) > 24:
            _GZ_MEM.clear()
        _GZ_MEM[h] = g
    return g


def sim_result_cached(inputs, ema, setups, ds, mode, lab, prune):
    key = hashlib.sha1(json.dumps([inputs, ema, setups, ds, mode, lab, prune, _engine_stamp()], sort_keys=True, default=str).encode()).hexdigest()
    b = _SIM_MEM.get(key)
    if b is None:
        f = SIM_CACHE_DIR / f"{key}.json"
        if f.is_file():
            try:
                b = f.read_bytes()
            except OSError:
                b = None
    if b is None:
        t0 = time.time()
        res = sim_result(inputs, ema, setups, ds, mode, lab, prune)
        if isinstance(res, dict) and res.get("error"):
            return res
        b = json.dumps(res).encode("utf-8")
        try:
            SIM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (SIM_CACHE_DIR / f"{key}.json").write_bytes(b)
            old = sorted(SIM_CACHE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime)
            for x in old[:-40]:                                 # keep the newest 40 answers on disk
                x.unlink(missing_ok=True)
        except OSError:
            pass
        log(f"sim cache: computed {len(b) // 1024} KB in {time.time() - t0:.1f}s -> {key[:10]}")
    if len(_SIM_MEM) > 16:
        _SIM_MEM.pop(next(iter(_SIM_MEM)))
    _SIM_MEM[key] = b
    return b



# Zee 2026-11-06: "in front of every LOSS ... put an input box with a save button -> this saves my comment about that loss -> once i'm done
# commenting on each loss we'll ask you to read the comments to find a pattern among the losses". One file, keyed by the trade itself
# (side + entry time + entry price), so a comment stays with its trade across settings that take the same entry.
LOSS_NOTES = HERE / "settings" / "loss_comments.json"


def loss_notes():
    try:
        return json.loads(LOSS_NOTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_loss_note(body):
    key = str(body.get("key") or "").strip()
    if not key:
        return {"error": "no trade key"}
    notes = loss_notes()
    text = str(body.get("comment") or "").strip()
    if text:
        notes[key] = {"comment": text[:2000], "trade": body.get("trade") or {}, "saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    else:
        notes.pop(key, None)
    LOSS_NOTES.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOSS_NOTES.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LOSS_NOTES)
    return {"ok": True, "n": len(notes)}



class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else (json.dumps(body) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if len(b) > 64 * 1024 and "gzip" in (self.headers.get("Accept-Encoding") or ""):     # Zee 2026-11-03: faster reloads - the sim / bars payloads are MBs of JSON
            b = _gz(b)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
            return self._get()
        except Exception:                                   # noqa: BLE001
            log("GET " + self.path + " failed:\n" + traceback.format_exc())
            return self.send(500, {"error": "server error - see monitor/saad_view/server.log"})

    def _get(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/loss_comments":
            return self.send(200, loss_notes())
        if u.path == "/api/claude_loss_comments":                 # Zee 2026-11-06: "comments should come from you" - the loss study's own reading of each loss
            try:
                return self.send(200, json.loads((HERE / "research" / "loss_study" / "final" / "claude_loss_comments.json").read_text(encoding="utf-8")))
            except (OSError, ValueError):
                return self.send(200, [])
        if u.path in ("/", "/index.html"):
            return self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path.startswith("/static/"):
            p = (STATIC / u.path[len("/static/"):]).resolve()
            if STATIC in p.parents and p.is_file():
                ct = {".js": "application/javascript", ".css": "text/css", ".html": "text/html"}.get(p.suffix, "application/octet-stream")
                return self.send(200, p.read_bytes(), ct + "; charset=utf-8")
            return self.send(404, {"error": "not found"})
        if u.path == "/api/inputs":
            info = ea_inputs()
            grid = {n: g for n, k, g in optimizer.SPACE if k in ("int", "num")}
            for i in info["inputs"]:
                i["sim"] = i["name"] in sim.IX or i["name"] in ("InpBandsB", "InpBandsS")
                if i["name"] in grid:                         # slider range = the optimizer's grid (ints slide by 1)
                    lo, hi, st = grid[i["name"]]
                    i["range"] = [lo, hi, 1 if i["type"] == "int" else st]
            return self.send(200, info)
        if u.path == "/api/uhv_trades":                    # TurtleTVUHV: the setups played as game rounds on PrimeXBT ticks (uhv_ticktest.py)
            f = HERE / "simdata" / ((q.get("which") or ["uhv"])[0] == "random" and "uhv_trades_random.json" or "uhv_trades.json")
            return self.send(200, f.read_bytes() if f.exists() else b'{"trades": []}')
        if u.path == "/api/uhv_camel":                     # TurtleTVUHV: Zee's camel humps for the chart
            return self.send(200, uhv_camel((q.get("ds") or ["year1"])[0]))
        if u.path == "/api/uhv_setups":
            return self.send(200, uhv_setups((q.get("ds") or ["year1"])[0]).encode("utf-8"))
        if u.path == "/api/bars":
            return self.send(200, bars_json((q.get("ds") or ["year"])[0]))
        if u.path == "/api/validation":                  # Exit Lab's Validation: every scan suggestion, tested in the tester and in MT5 (validation_run.py)
            VF = HERE / "simdata" / "validation.json"
            data = json.loads(VF.read_text(encoding="utf-8")) if VF.exists() else {"rows": [], "count": 0, "of": 0}
            data["comments"] = {x["name"]: x["comment"] for x in ea_inputs()["inputs"]}
            LF = HERE / "simdata" / "validation_loss.json"
            data["loss"] = json.loads(LF.read_text(encoding="utf-8")) if LF.exists() else {"rows": [], "count": 0, "of": 0}
            return self.send(200, data)
        if u.path == "/api/primary":                     # the primary save's name, kept on the server so every browser starts from it
            return self.send(200, {"name": PRIMARY.read_text(encoding="utf-8").strip() if PRIMARY.exists() else None})
        if u.path == "/api/saved":                       # Zee: "save current chart settings ... shows all saved settings at the bottom"
            SAVED.mkdir(parents=True, exist_ok=True)
            rows = []
            for f in sorted(SAVED.glob("*.json"), reverse=True):
                try:
                    row = json.loads(f.read_text(encoding="utf-8"))
                    row["candidate_exports"] = [
                        item | {"available": _candidate_record_available(item)}
                        for item in row.get("candidate_exports", [])
                    ]
                    rows.append(row)
                except Exception:                                # noqa: BLE001
                    pass
            return self.send(200, rows)
        if u.path == "/api/opt":
            state = OPT["o"].state() if OPT["o"] else {}
            state["objectives"] = list(optimizer.OBJECTIVES)
            return self.send(200, state)
        if u.path == "/api/risk_opt":
            state = RISK_OPT["o"].state() if RISK_OPT["o"] else {}
            if RISK_OPT["o"]:
                state["groups"] = getattr(RISK_OPT["o"], "risk_groups", [])
                state["risk_inputs"] = RISK_OPT["o"].start
                state["space_size"] = len(RISK_OPT["o"].space)
            else:
                state["groups"] = []
            return self.send(200, state)
        if u.path == "/api/risk_reference":
            rid = "r20261024_235213"
            p = RUNS / f"{rid}.json"
            if not p.is_file():
                return self.send(404, {"error": f"MT5 reference run {rid} is unavailable"})
            d = json.loads(p.read_text(encoding="utf-8"))
            return self.send(200, {k: d.get(k) for k in ("id", "label", "created", "period", "deposit", "inputs")} |
                             {"report": {k: d.get("report", {}).get(k) for k in ("net", "pf", "trades", "dd", "trade_stats", "day_stats")},
                              "execution_stats": run_wr(p, d)})
        if u.path == "/api/tv":
            info = tv_settings()
            return self.send(200, {k: info[k] for k in ("symbol", "res", "sets", "notes", "at")})
        if u.path == "/api/runs":
            return self.send(200, list_runs())
        if u.path == "/api/run":
            rid = (q.get("id") or [""])[0]
            p = RUNS / f"{rid}.json"
            if not re.fullmatch(r"r\d{8}_\d{6}", rid) or not p.exists():
                return self.send(404, {"error": "no such run"})
            return self.send(200, p.read_bytes())
        if u.path == "/api/mt5_report":
            rid = (q.get("id") or [""])[0]
            if not re.fullmatch(r"r\d{8}_\d{6}", rid) or not (RUNS / f"{rid}.json").is_file():
                return self.send(404, {"error": "no such MT5 run"})
            report = mt5_report_path(rid)
            if report is None:
                return self.send(404, {"error": "MT5 Strategy Tester HTML report is unavailable for this run"})
            content = report.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-16")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f'attachment; filename="MT5_Strategy_Tester_{rid}.htm"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
            return
        if u.path == "/api/export_status":
            rid = (q.get("id") or [""])[0]
            if not re.fullmatch(r"r\d{8}_\d{6}", rid):
                return self.send(400, {"error": "bad id"})
            state = export_status(rid)
            return self.send(200 if state.get("id") == rid and state.get("phase") else 404, _jsonable(state))
        if u.path == "/api/export_report":
            rid = (q.get("id") or [""])[0]
            report = RUNS / f"{rid}_candidate.htm"
            if not re.fullmatch(r"r\d{8}_\d{6}", rid) or not report.is_file():
                return self.send(404, {"error": "No candidate Strategy Tester report is available"})
            content = report.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-16")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f'attachment; filename="MT5_Candidate_{rid}.htm"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
            return
        if u.path == "/api/export_package":
            rid = (q.get("id") or [""])[0]
            artifacts = candidate_files(rid)
            if not artifacts:
                return self.send(404, {"error": "No compiled and tested candidate EA is available for this run"})
            package = io.BytesIO()
            with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(artifacts["source"], f"{artifacts['name']}/{artifacts['source'].name}")
                archive.write(artifacts["compiled"], f"{artifacts['name']}/{artifacts['compiled'].name}")
            try:
                os.startfile(str(artifacts["compiled"].parent))
            except (AttributeError, OSError) as error:
                log(f"export {rid}: could not open Explorer for {artifacts['compiled']}: {error}")
                return self.send(500, {"error": f"EA package is ready, but Explorer could not be opened: {error}"})
            content = package.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f'attachment; filename="{artifacts["name"]}.zip"')
            self.send_header("X-EA-Location", str(artifacts["compiled"]))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
            return
        if u.path == "/api/exitlab":
            return self.send(200, lab_state(bool(q.get("full")), (q.get("partial") or [""])[0]))
        if u.path == "/api/exitlab_research":
            return self.send(200, _research_list())
        if u.path == "/api/ml":
            return self.send(200, ml_state())
        if u.path == "/api/mission":
            return self.send(200, mission_state())
        if u.path == "/api/stress":
            return self.send(200, stress_state())
        if u.path == "/api/ml_algos":
            return self.send(200, {"algos": ml.ALGOS})
        if u.path == "/api/mlx":                          # the institutional entry filter: job state + simdata/mlx_results.json (or the sample fixture)
            return self.send(200, mlx_state())
        if u.path == "/api/mlx_spec":                     # the fixed feature spec (mlx/FEATURE_SPEC.md); ?raw=1 for the markdown itself
            txt = MLX_SPEC.read_text(encoding="utf-8") if MLX_SPEC.is_file() else ""
            if (q.get("raw") or [""])[0] == "1":
                return self.send(200, txt, "text/markdown; charset=utf-8")
            return self.send(200, {"path": "monitor/saad_view/mlx/FEATURE_SPEC.md", "text": txt})
        if u.path == "/api/dexter":                       # Dexter's Lab: the controlled MT5 comparison's state and results
            return self.send(200, _jsonable(dexter_status()))
        if u.path == "/api/dexter_mae":                   # Dexter's Lab: the reference trades' excursions (dexter_mae.py)
            import dexter_mae
            f = HERE / "simdata" / "dexter_mae.json"
            if (q.get("fresh") or [""])[0] == "1" or not f.is_file():
                dexter_mae.analyse(DEXTER_REFERENCE_ID)
            return self.send(200, json.loads(f.read_text(encoding="utf-8")))
        if u.path == "/api/exitlab_spec":
            return self.send(200, _jsonable({"groups": exitlab.GROUPS, "default": exitlab.DEFAULT, "why": exitlab.WHY, "trust": exitlab.ea_trust()}))
        if u.path == "/api/hyp_job":
            j = HJOBS.get((q.get("id") or [""])[0])
            return self.send(200 if j else 404, j or {"error": "no such job"})
        if u.path == "/api/trade_notes":
            return self.send(200, _notes())
        if u.path == "/api/research":                     # the Research page: papers + results + the running job
            return self.send(200, research_list())
        if u.path == "/api/deploy_target":
            return self.send(200, deploy_mod.public_cfg())
        if u.path == "/api/deploy":
            return self.send(200, _jsonable(deploy_mod.state()))
        if u.path == "/api/deploy_history":
            return self.send(200, _jsonable(deploy_mod.last_history()))
        if u.path == "/api/lcf_catalog":
            return self.send(200, _jsonable(lcf_catalog()))
        if u.path == "/api/lcf":                          # Range boxes: B's loser-cutting filters measured on the setting on the chart (?key= from POST: rows only when they match)
            k = (q.get("key") or [""])[0]
            out = {kk: v for kk, v in LCF.items() if kk != "thread"}
            if not k or LCF["key"] != k:                      # no key (old page JS) or another setting's measurement: never show someone else's rows
                out.update(rows={}, base=None, stale=True)
            return self.send(200, _jsonable(out))
        if u.path == "/api/mlx_meta":                     # the meta-labelling study (mlx/meta_train.py, mlx/meta_seq.py) for the Machine Learning tab
            out = {}
            for k, f in (("tab", "mlx_meta_results_tab.json"), ("seq", "mlx_meta_results_seq.json"), ("spec", "mlx_meta_spec.json")):
                fp = HERE / "simdata" / f
                try:
                    out[k] = json.loads(fp.read_text(encoding="utf-8")) if fp.is_file() else None
                except (OSError, ValueError) as e:
                    out[k] = {"error": str(e)[:200]}
            return self.send(200, _jsonable(out))
        if u.path == "/api/research_log":
            r = research_log((q.get("id") or [""])[0])
            return self.send(404 if r.get("error") else 200, r)
        if u.path == "/api/status":
            s = dict(STATE)
            s["elapsed"] = round(time.time() - s["started"]) if s.get("started") and s.get("busy") else None
            s["follow"] = {k: FOLLOW[k] for k in ("on", "delay", "connected", "err", "at", "msg")} | {
                "notes": (FOLLOW["tv"] or {}).get("notes", []), "symbol": (FOLLOW["tv"] or {}).get("symbol"),
                "waiting": bool(FOLLOW["pending"])}
            return self.send(200, s)
        return self.send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if u.path == "/api/loss_comment":
                return self.send(200, save_loss_note(body))
            if u.path == "/api/run":
                rid, err = start_run(body)
                return self.send(409 if err else 200, {"error": err} if err else {"id": rid})
            if u.path == "/api/save":
                SAVED.mkdir(parents=True, exist_ok=True)
                name = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                dfl = axi_rig.ea_defaults(EA)
                inp = full_inputs(body.get("inputs") or {})
                rec = {"name": name, "inputs": inp, "changed": {k: v for k, v in inp.items() if not same(v, dfl.get(k))}, "ds": body.get("ds"),
                       "mode": body.get("mode"), "result": body.get("result"),
                       "lab": exitlab.clean(body.get("lab") or {}) if body.get("lab") else {}, "lab_describe": exitlab.describe(body.get("lab")) if body.get("lab") else ""}
                (SAVED / f"{name}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
                return self.send(200, {"name": name})
            if u.path == "/api/primary":
                n = body.get("name")
                if n and re.fullmatch(r"[\d\- ]+", str(n)):
                    PRIMARY.write_text(str(n), encoding="utf-8")
                else:
                    PRIMARY.unlink(missing_ok=True)
                return self.send(200, {"ok": True})
            if u.path == "/api/saved_delete":
                n = str(body.get("name", ""))
                if _safe_saved_name(n):
                    (SAVED / f"{n}.json").unlink(missing_ok=True)
                    if PRIMARY.exists() and PRIMARY.read_text(encoding="utf-8").strip() == n:
                        PRIMARY.unlink()
                return self.send(200, {"ok": True})
            if u.path == "/api/ask":
                return self.send(200, ask_claude(body))
            if u.path == "/api/ask_trade":
                return self.send(200, ask_trade(body))
            if u.path == "/api/hyp":
                return self.send(200, hyp_start(body))
            if u.path == "/api/exitlab":
                return self.send(200, lab_start(body))
            if u.path == "/api/exitlab_stop":
                if LAB["job"]:
                    LAB["job"].stop()
                killed = __import__("scan").kill_pool() if body.get("kill") else 0     # TurtleTVUHV: STOP SCAN also ends the workers
                return self.send(200, {"ok": True, "killed": killed})
            if u.path == "/api/exitlab_feature":
                return self.send(200, lab_feature(body))
            if u.path == "/api/exitlab_research":
                return self.send(200, lab_research(body))
            if u.path == "/api/ml":
                return self.send(200, ml_start(body))
            if u.path == "/api/mlx":
                return self.send(200, mlx_start(body))
            if u.path == "/api/research_upload":
                r = research_upload(body)
                return self.send(400 if r.get("error") else 200, r)
            if u.path == "/api/lcf":
                return self.send(200, lcf_start(body))
            if u.path == "/api/deploy_target":
                deploy_mod.save_cfg(body)
                return self.send(200, deploy_mod.public_cfg())
            if u.path == "/api/deploy_test":
                return self.send(200, deploy_mod.test_target(body))
            if u.path == "/api/deploy_history":
                r = deploy_mod.fetch_history()
                return self.send(400 if r.get("error") else 200, _jsonable(r))
            if u.path == "/api/deploy":
                r = deploy_mod.start(str(body.get("name") or ""), SAVED, rig_busy)
                return self.send(409 if r.get("error") else 200, r)
            if u.path == "/api/research_url":               # Zee: "input a pdf URL ending with .pdf to download and keep it in the research folder and begin processing"
                r = research_url(body)
                return self.send(400 if r.get("error") else 200, r)
            if u.path == "/api/research_build":
                r = research_build(body)
                return self.send(409 if r.get("error") else 200, r)
            if u.path == "/api/research_stop":
                return self.send(200, {"ok": True, "stopped": pjob.stop(str(body.get("id") or ""))})
            if u.path == "/api/research_save":
                r = research_save(body)
                return self.send(400 if r.get("error") else 200, r)
            if u.path == "/api/research_assist":
                r = research_assist(body)
                return self.send(409 if r.get("error") else 200, r)
            if u.path == "/api/research_delete":
                r = research_delete(body)
                return self.send(400 if r.get("error") else 200, r)
            if u.path == "/api/lego_test":
                return self.send(200, lego_test(body))
            if u.path == "/api/mission":
                return self.send(200, mission_start(body))
            if u.path == "/api/stress":
                return self.send(200, stress_start(body))
            if u.path == "/api/sim":
                return self.send(200, sim_result_cached(body.get("inputs") or {}, bool(body.get("ema", True)), bool(body.get("setups", True)),
                                                        body.get("ds") or "year", body.get("mode") or "ea", body.get("lab"), body.get("prune") or []))
            if u.path == "/api/dexlab_spec":                  # Dexter's Lab on the live setting
                return self.send(200, _jsonable({"exps": dexlab.spec()}))
            if u.path == "/api/dexlab_diag":
                return self.send(200, _jsonable(dexlab.diagnose(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea")))
            if u.path == "/api/dexlab_one":
                return self.send(200, _jsonable(dexlab.run(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea",
                                                           body.get("key") or "baseline", body.get("params") or {})))
            if u.path == "/api/dexlab_sets":
                return self.send(200, _jsonable({"stats": dexlab.run_sets(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1",
                                                                          body.get("mode") or "ea", body.get("sets") or {})}))
            if u.path == "/api/dexlab_start":
                return self.send(200, _jsonable(dexlab.start(body, full_inputs)))
            if u.path == "/api/dexlab_job":
                return self.send(200, _jsonable(dexlab.job_state()))
            if u.path == "/api/dexlab_stop":
                return self.send(200, _jsonable(dexlab.stop()))
            if u.path == "/api/dexlab_mt5":
                return self.send(200, _jsonable(dexlab_mt5_start(body)))
            if u.path == "/api/dexlab_mt5_status":
                return self.send(200, _jsonable(dexlab_mt5_status(body)))
            if u.path == "/api/dexlab_mt5_stop":
                DEXLAB_MT5["cancel"] = True
                return self.send(200, {"ok": True})
            if u.path == "/api/dexter_start":                # Dexter's Lab: baseline + experiments in MT5, one after another
                return self.send(200, _jsonable(dexter_start(body)))
            if u.path == "/api/dexter_stop":
                return self.send(200, _jsonable(dexter_stop()))
            if u.path == "/api/tplab_controls":             # the tuner's list: every take-profit setting, its range and its choices
                return self.send(200, _jsonable({"controls": tplab.TP_CONTROLS, "mode1_controls": tplab.MODE1_CONTROLS,
                                                 "mode2_controls": tplab.MODE2_CONTROLS}))
            if u.path == "/api/tplab_set":                  # the tuner: one setting changed, the tester's result
                return self.send(200, _jsonable(tplab.one_set(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea", body.get("overrides") or {})))
            if u.path == "/api/tplab_one":                  # Take Profit Lab slider: one run with the slider's target
                return self.send(200, _jsonable(tplab.one(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea", body.get("overrides") or {})))
            if u.path == "/api/tplab_paths":                # Take Profit Lab analysis: each trade's excursions and the target curve
                return self.send(200, _jsonable(tplab.paths(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea")))
            if u.path == "/api/tplab_scan":                 # Take Profit Lab scan: every take-profit setting
                return self.send(200, _jsonable(tplab.scan_start(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea")))
            if u.path == "/api/tplab_tune":
                result = tplab.tune_start(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1",
                                           body.get("mode") or "ea", body.get("name"), body.get("overrides") or {})
                return self.send(409 if result.get("busy") else 400 if not result.get("ok") else 200, _jsonable(result))
            if u.path.startswith("/api/xlife_"):           # the EXTENDED Trade Lifecycle: every exit as a switch
                inp, ds_, md_ = full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea"
                act = u.path[len("/api/xlife_"):]
                if act == "spec":
                    return self.send(200, _jsonable(xlife.spec(inp, ds_)))
                if act == "eval":
                    return self.send(200, _jsonable(xlife.evaluate(inp, ds_, md_, body.get("sel") or {})))
                if act == "impacts":
                    return self.send(200, _jsonable(xlife.impacts_start(inp, ds_, md_, body.get("sel") or {}, body.get("objective") or "net", body.get("guard", True))))
                if act == "optimise":
                    return self.send(200, _jsonable(xlife.optimise_start(inp, ds_, md_, body.get("objective") or "net", body.get("guard", True),
                                                                         tuple(int(m) for m in (body.get("modes") or [1, 2])), body.get("sel"))))
                if act == "job":
                    return self.send(200, _jsonable(xlife.job()))
                if act == "stop":
                    return self.send(200, _jsonable(xlife.stop()))
            if u.path == "/api/lifecycle":                  # Trade Lifecycle tree: branches per exit, prune forecasts
                return self.send(200, _jsonable(lifecycle.tree(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1",
                                                               body.get("mode") or "ea", body.get("pruned") or [])))
            if u.path == "/api/probe_eval":                  # Risk Manager · Probe entry: the loaded setting with / without the probe
                return self.send(200, _jsonable(probe.evaluate(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea", body.get("probe") or {})))
            if u.path == "/api/probe_tune":
                return self.send(200, _jsonable(probe.tune(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea", body.get("probe") or {})))
            if u.path == "/api/tplab_auto":                 # auto-tune one box (group) or every box + the best combination
                return self.send(200, _jsonable(tplab.auto_start(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1",
                                                                 body.get("mode") or "ea", body.get("group"), body.get("start") or {},
                                                                 body.get("guard", True))))
            if u.path == "/api/tplab_auto_progress":
                return self.send(200, _jsonable(tplab.auto_progress()))
            if u.path == "/api/tplab_auto_stop":
                return self.send(200, _jsonable(tplab.auto_stop()))
            if u.path == "/api/tplab_tune_progress":
                return self.send(200, _jsonable(tplab.tune_progress()))
            if u.path == "/api/tplab_progress":             # the scan's progress: runs done, the setting now, the result when finished
                return self.send(200, _jsonable(tplab.progress()))
            if u.path == "/api/tplab":                       # Take Profit Lab: the tester at each take-profit distance
                return self.send(200, _jsonable(tplab.run(full_inputs(body.get("inputs") or {}), body.get("ds") or "year1", body.get("mode") or "ea")))
            if u.path == "/api/optimize":
                return self.send(200, opt_start(body))
            if u.path == "/api/opt_stop":
                if OPT["o"]:
                    OPT["o"].stop()
                return self.send(200, {"ok": True})
            if u.path == "/api/risk_scan":
                result = risk_start(body)
                return self.send(409 if result.get("error") else 200, result)
            if u.path == "/api/risk_stop":
                if RISK_OPT["o"]:
                    RISK_OPT["o"].stop()
                return self.send(200, {"ok": True})
            if u.path == "/api/follow":
                FOLLOW.update(on=bool(body.get("on")), delay=body.get("delay") or FOLLOW["delay"], key=None, pending=None, msg="")
                return self.send(200, {"ok": True})
            if u.path == "/api/tv_take":                     # one read of TradingView's settings -> run (or the run that already has them)
                info = tv_settings()
                delay = body.get("delay") or "none"
                have = run_matching(info["sets"], delay, PERIOD)
                if have:
                    return self.send(200, {"id": have, "existing": True, "notes": info["notes"]})
                rid, err = start_run({"sets": info["sets"], "delay": delay, "label": f"TradingView {info['at']}", "notes": info["notes"], "tv_raw": info["raw"],
                                      "tv_chart": {"symbol": info["symbol"], "timeframe": info["res"], "read_at": info["at"]}}, source="tradingview")
                return self.send(409 if err else 200, {"error": err} if err else {"id": rid, "notes": info["notes"]})
            if u.path == "/api/export":
                rid = body.get("id", "")
                if not re.fullmatch(r"r\d{8}_\d{6}", rid):
                    return self.send(400, {"error": "bad id"})
                return self.send(200, export(rid))
            if u.path == "/api/delete":
                rid = body.get("id", "")
                if re.fullmatch(r"r\d{8}_\d{6}", rid):
                    (RUNS / f"{rid}.json").unlink(missing_ok=True)
                    (RUNS / f"{rid}.htm").unlink(missing_ok=True)
                return self.send(200, {"ok": True})
        except Exception as e:                              # noqa: BLE001
            log("POST " + self.path + " failed:\n" + traceback.format_exc())
            return self.send(500, {"error": str(e)[:400]})
        return self.send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=follow_loop, daemon=True).start()
    if not list(RUNS.glob("r*.json")):
        log("no runs yet (TurtleTVUHV does not start one by itself)")
        pass   # TurtleTVUHV: never start an MT5 run by itself - the MT5 rigs are shared with the original Turtle TV
    log(f"Turtle TV on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
