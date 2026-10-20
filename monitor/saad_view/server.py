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
     POST /api/run {sets, from, to, delay, label} · /api/follow {on, delay} · /api/tv_take {delay} · /api/export {id} · /api/delete {id}"""
import importlib.util
import json
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
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
import ml  # noqa: E402
import mission  # noqa: E402
import sim_full  # noqa: E402

_spec = importlib.util.spec_from_file_location("saad_compare_server", ROOT / "monitor" / "saad_compare" / "server.py")
CMP = importlib.util.module_from_spec(_spec)      # the compare page's TradingView reader (no server is started by importing it)
_spec.loader.exec_module(CMP)

PORT = 8773
EA = "Saad_strategy_15min_view"
LIVE_EA = "Saad_strategy_15min"                # the EA the preset is for
SYMBOL, PERIOD = "XAUUSD_BB", "M15"           # Blueberry's real ticks (Zee's chart broker), Jan 1 - Oct 17 2026
RIG = "axi7"                                  # one of the compare page's year-view rigs (idle while its 10-month view is off)
DEPOSIT = 100000
FROM, TO = "2026.01.01", "2026.10.17"
RUNS = HERE / "runs"
SETTINGS = HERE / "settings"
SAVED = HERE / "settings" / "saved"                   # the page's saved chart settings, one JSON per save                  # the JSON hand-off files (format "turtle-settings/1"; see settings_doc)
STATIC = HERE / "static"
TERMINALS = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"
COMMON = TERMINALS / "Common" / "Files"
HIDE = {"InpExport", "InpExportTag", "InpMagicNumber", "InpVerbose", "InpDraw", "InpLog", "InpLogCsv", "InpShowEmas", "InpDrawSkips",
        "InpOptScore", "InpOptMinTrades"}
RUNS.mkdir(exist_ok=True)
SETTINGS.mkdir(exist_ok=True)
STATE = {"busy": False, "id": None, "label": "", "started": None, "phase": "", "error": None, "last": None, "cancel": False, "source": ""}
# follow TradingView: delay "none" while tuning, so the same settings always give the same number (Export adds the random-delay result)
FOLLOW = {"on": False, "delay": "none", "connected": False, "err": None, "at": None, "tv": None, "key": None, "changed_at": 0,
          "pending": None, "msg": ""}
LOCK = threading.Lock()


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
        print(line, flush=True)


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


# ---------- the EA's inputs, straight from its source (groups, defaults, comments) ----------
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
        out.append({"name": name, "type": typ, "default": dflt, "comment": com, "group": group})
    ver = re.search(r'#property version\s+"([^"]+)"', src)
    return {"ea": EA, "version": ver.group(1) if ver else "?", "inputs": out}


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
    full = {i["name"]: str(inputs.get(i["name"], dfl.get(i["name"], i["default"]))) for i in info["inputs"] if i["name"] in dfl}
    return {"format": "turtle-settings/1", "written_by": "Turtle TV", "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ea": LIVE_EA, "ea_version": info["version"], "ea_inputs": full,
            "changed_from_defaults": {k: v for k, v in full.items() if not same(v, dfl.get(k))},
            "chart_only": notes or [], "chart": chart, "tradingview": raw, "mt5_result": result}


def run_matching(sets, delay):
    """The newest run that already has exactly these settings (and delay) - no need to run MT5 again. Every input is compared: the ones
    not in `sets` must be at the EA's defaults (a run with an extra change from the settings form is not a match)."""
    dfl = axi_rig.ea_defaults(EA)
    for p in sorted(RUNS.glob("r*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        if d.get("delay") == delay and all(same(v, sets.get(k, dfl.get(k, v))) for k, v in d["inputs"].items()):
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
            have = run_matching(p["sets"], FOLLOW["delay"])
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


def run_job(rid, sets, frm, to, delay, label, notes):
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
            r = axi_rig.run(EA, SYMBOL, PERIOD, run_sets, frm=frm, to=to, deposit=DEPOSIT, rig=RIG, tag=f"view_{rid}",
                            exec_mode=0 if delay == "none" else -1, cancel=lambda: STATE["cancel"])
            if r.get("error") not in ("authorization failed", "no report"):
                break
            axi_rig.kill_rig(RIG); time.sleep(5)
        if r.get("error"):
            raise RuntimeError("cancelled" if r.get("error") == "cancelled" else f"MT5: {r.get('error')}")
        STATE.update(phase="reading the EA's export")
        rep = {k: r.get(k) for k in ("net", "pf", "trades", "dd", "quality", "months", "trade_stats", "day_stats")}
        info = ea_inputs()
        meta = {"id": rid, "label": label, "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "ea": EA, "version": info["version"],
                "symbol": SYMBOL, "period": PERIOD, "from": frm, "to": to, "delay": delay, "deposit": DEPOSIT, "changed": sets,
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
        rid = "r" + datetime.now().strftime("%Y%m%d_%H%M%S")
        defaults = axi_rig.ea_defaults(EA)
        sets = {k: str(v) for k, v in (body.get("sets") or {}).items() if k not in HIDE and not same(v, defaults.get(k))}
        label = (body.get("label") or "").strip() or ("v" + ea_inputs()["version"] + (" defaults" if not sets else " + " + ", ".join(f"{k[3:]} {v}" for k, v in sets.items())))
        STATE.update(busy=True, id=rid, label=label, started=time.time(), phase="starting", error=None, cancel=False, source=source,
                     tv_raw=body.get("tv_raw"), tv_chart=body.get("tv_chart"))
        threading.Thread(target=run_job, args=(rid, sets, body.get("from") or FROM, body.get("to") or TO, body.get("delay") or "random", label,
                                               body.get("notes")), daemon=True).start()
        return rid, None


def list_runs():
    out = []
    for p in sorted(RUNS.glob("r*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({k: d.get(k) for k in ("id", "label", "created", "from", "to", "delay", "changed", "source")} |
                       {"net": d["report"].get("net"), "pf": d["report"].get("pf"), "trades": d["report"].get("trades")})
        except Exception:                                   # noqa: BLE001
            continue
    return out


# ---------- Export to MT5: the run's settings as a preset for the real EA (+ a random-delay result) ----------
def export(rid):
    d = json.loads((RUNS / f"{rid}.json").read_text(encoding="utf-8"))
    live = axi_rig.ea_defaults(LIVE_EA)
    lines = [f"; {LIVE_EA} - settings from Turtle TV run {rid} '{d['label']}' ({d['created']})",
             f"; MT5 {d['symbol']} {d['from']} - {d['to']}, delay {d['delay']}: net {d['report'].get('net')}, PF {d['report'].get('pf')}, trades {d['report'].get('trades')}"]
    lines += [f"{k}={v}" for k, v in d["inputs"].items() if k in live]
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
    rep = d["report"]
    n = sum(1 for e in d["events"] if e["type"] == "exit")
    w = sum(1 for e in d["events"] if e["type"] == "exit" and (e["v1"] or 0) > 0)
    doc = settings_doc(d["inputs"], d.get("notes"), raw=d.get("tradingview"), chart=d.get("chart"),
                       result={"run": rid, "label": d["label"], "symbol": d["symbol"], "period": d["period"], "from": d["from"], "to": d["to"],
                               "delay": d["delay"], "deposit": d["deposit"], "net": rep.get("net"), "profit_factor": rep.get("pf"),
                               "trades": n, "win_rate": round(100 * w / n, 1) if n else None, "max_drawdown": rep.get("dd"), "months": rep.get("months")})
    jf = SETTINGS / f"{LIVE_EA}_TurtleTV_{rid}.json"
    jf.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (SETTINGS / "turtletv_export_latest.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    written.insert(0, str(jf))
    res = {"preset": name, "json": jf.name, "written": written, "run": None}
    if d["delay"] != "random":
        have = run_matching({k: v for k, v in d["inputs"].items()}, "random")
        if have:
            res["run"], res["existing"] = have, True
        else:
            rid2, err = start_run({"sets": d["inputs"], "delay": "random", "label": f"Export: {d['label']}", "notes": d.get("notes")}, source="export")
            res["run"], res["error"] = rid2, err
    return res


# ---------- the Turtle TV Tester (sim.py): instant results for any settings ----------
def _utc(e):
    return int((server_to_utc(datetime(1970, 1, 1) + timedelta(seconds=int(e))) - datetime(1970, 1, 1)).total_seconds())


_BARS = {}


def bars_json(ds="year"):
    """The M15 candles of a dataset ('year' = the Blueberry MT5 candles the EA trades on, 'tv' = TradingView's own candles), UTC, with ADX / ATR."""
    if ds not in _BARS:
        D = sim.data(ds)
        r2 = lambda a: [round(float(x), 2) for x in a]
        _BARS[ds] = json.dumps({"ds": ds, "t": [_utc(x) for x in D["t15"]], "o": r2(D["o15"]), "h": r2(D["h15"]), "l": r2(D["l15"]), "c": r2(D["c15"]),
                                "adx": r2(D["adx"]), "atr": [round(float(x), 3) for x in D["atr"]],
                                "ticks_until": _utc(int(D["ticks_until"][0])) if "ticks_until" in D else None}, separators=(",", ":"))
    return _BARS[ds]


def full_inputs(sets):
    dfl = axi_rig.ea_defaults(EA)
    return {i["name"]: str(sets.get(i["name"], dfl.get(i["name"], i["default"]))) for i in ea_inputs()["inputs"]}


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
                ds = body.get("ds") if body.get("ds") in ("year", "m15") else "year"
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


def sim_result(sets, want_ema=True, want_setups=True, ds="year", mode="ea", lab=None):
    """ds 'year' (Blueberry MT5 candles) / 'tv' (TradingView's candles); mode 'ea' (v1.27's rules, real spread + swap), 'chart' (the indicator's
    rules, $0.17 spread, no swap), 'chart_blind' (and blind inside the entry candle before Oct 12, like TradingView without 1-minute data)."""
    ds = ds if ds in ("year", "tv", "m15") else "year"
    inp = full_inputs(sets)
    lab = exitlab.clean(lab) if lab else None
    lab = lab if lab and [f for f in lab if f != "pess"] else None
    if lab and str(inp.get("InpExitMode")) not in ("1", "2"):
        inp["InpExitMode"] = "1"                          # the Exit Lab's exits sit on top of exit modes 1-2
    t0 = time.time()
    tr, su, st = sim.simulate(inp, ds=ds, lab=lab, **MODES.get(mode, {}))
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
            ev.append({"type": "ghost", "t": _utc(x[1]), "side": side, "price": round(x[2], 2), "sl": round(x[3], 2), "v1": nx, "v2": b, "ref": None, "num": 0, "text": tgt(nx)})
            ev.append({"type": "ghost_end", "t": _utc(x[4]), "side": side, "price": round(x[5], 2), "sl": round(x[2], 2), "v1": 0, "v2": 0, "ref": None, "num": 0,
                       "text": why.get(int(x[13]), "")})
            continue
        num += 1
        ev.append({"type": "entry", "t": _utc(x[1]), "side": side, "price": round(x[2], 2), "sl": round(x[3], 2), "v1": nx, "v2": b, "ref": None, "num": num, "text": tgt(nx)})
        ev.append({"type": "exit", "t": _utc(x[4]), "side": side, "price": round(x[5], 2), "sl": round(x[3], 2), "v1": round(x[6], 2), "v2": round(x[7], 2),
                   "ref": _utc(x[1]), "num": num, "text": why.get(int(x[13]), "")})
    brk = float(inp["InpBreakPips"]) * 0.1
    for k, side, kind in (su if want_setups else []):
        k = int(k)
        ev.append({"type": "setup", "t": _utc(D["t15"][k]), "side": int(side), "price": float(D["h15"][k]), "sl": float(D["l15"][k]),
                   "v1": round(float(D["h15"][k] + brk if side > 0 else D["l15"][k] - brk), 2), "v2": int(kind), "ref": None, "num": 0, "text": ""})
    ev.sort(key=lambda e: e["t"])
    trn, tst = tr[tr[:, 1] < optimizer.TRAIN_END], tr[tr[:, 1] >= optimizer.TRAIN_END]
    out = {"inputs": inp, "ms": ms, "events": ev, "stats": st, "year": sim.score(tr), "train": sim.score(trn, 1), "test": sim.score(tst, 1), "ds": ds, "mode": mode}
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
        out["ef"] = [round(float(x), 3) for x in ef]
        out["es"] = [round(float(x), 3) for x in es]
    return out


OPT = {"o": None}

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
    if OPT["o"] and OPT["o"].running:
        OPT["o"].stop()
        time.sleep(0.2)
    if body.get("objective") == "ranges":                         # grow the number of 100%-win range boxes
        o = optimizer.RangeOpt(full_inputs(body.get("start") or {}), ds=body.get("ds") if body.get("ds") in ("year", "m15") else "year")
        OPT["o"] = o
        threading.Thread(target=o.run, daemon=True).start()
        return {"ok": True}
    if body.get("objective") in ("entries", "exits"):            # survey: every entry / exit setting one at a time, all results listed
        o = optimizer.Survey(full_inputs(body.get("start") or {}), body["objective"], ds=body.get("ds") if body.get("ds") in ("year", "m15") else "year")
        OPT["o"] = o
        threading.Thread(target=o.run, daemon=True).start()
        return {"ok": True}
    o = optimizer.Optimizer(full_inputs(body.get("start") or {}), objective=body.get("objective") or "ret_dd", boxes=bool(body.get("boxes")),
                            keep_going=bool(body.get("keep")), ds=body.get("ds") if body.get("ds") in ("year", "m15") else "year")
    OPT["o"] = o
    threading.Thread(target=opt_run_and_check, args=(o,), daemon=True).start()
    return {"ok": True}


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
    if action not in ("diagnose", "test", "catalogue", "search", "heatmap"):
        return {"error": "unknown action"}
    slot = "tjob" if action in ("test", "diagnose") else "job"
    if LAB[slot] and LAB[slot].running:
        LAB[slot].stop()
    inputs = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv") else "year"
    kw = {k: body.get(k) for k in ("lab", "sets", "objective", "fx", "fy", "xs", "ys") if body.get(k) is not None}
    key = json.dumps([inputs, "year" if ds == "tv" else ds], sort_keys=True)
    if action == "search" and LAB["cat"] and LAB["cat"][0] == key:
        kw["cat_rows"] = LAB["cat"][1]                    # the catalogue of the same settings: the search starts from it
    j = exitlab.Job(action, inputs, ds, **kw)
    j.key = key
    j.req = {"inputs": body.get("inputs") or {}, "ds": "year" if ds == "tv" else ds}     # what the page asked for: it warns when its settings moved on
    LAB[slot] = j
    threading.Thread(target=j.run, daemon=True).start()
    return {"ok": True}


def lab_state(full=False):
    out = {}
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
        out[name] = j.state()
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
    ds = body.get("ds") if body.get("ds") in ("year", "m15") else "year"
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
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv") else "year"
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


# ---------------------------------------------------------------- Strategy Lego (lego.py): replace the core pieces of the strategy
def lego_test(body):
    inputs = full_inputs(dict(body.get("inputs") or {}, **(body.get("sets") or {})))
    base_in = full_inputs(body.get("inputs") or {})
    ds = body.get("ds") if body.get("ds") in ("year", "m15") else "year"
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
    ds = body.get("ds") if body.get("ds") in ("year", "m15", "tv") else "year"
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


# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else (json.dumps(body) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
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
        if u.path == "/api/bars":
            return self.send(200, bars_json((q.get("ds") or ["year"])[0]))
        if u.path == "/api/saved":                       # Zee: "save current chart settings ... shows all saved settings at the bottom"
            SAVED.mkdir(parents=True, exist_ok=True)
            rows = []
            for f in sorted(SAVED.glob("*.json"), reverse=True):
                try:
                    rows.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:                                # noqa: BLE001
                    pass
            return self.send(200, rows)
        if u.path == "/api/opt":
            return self.send(200, OPT["o"].state() if OPT["o"] else {})
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
        if u.path == "/api/exitlab":
            return self.send(200, lab_state(bool(q.get("full"))))
        if u.path == "/api/exitlab_research":
            return self.send(200, _research_list())
        if u.path == "/api/ml":
            return self.send(200, ml_state())
        if u.path == "/api/mission":
            return self.send(200, mission_state())
        if u.path == "/api/ml_algos":
            return self.send(200, {"algos": ml.ALGOS})
        if u.path == "/api/exitlab_spec":
            return self.send(200, _jsonable({"groups": exitlab.GROUPS, "default": exitlab.DEFAULT, "why": exitlab.WHY, "trust": exitlab.ea_trust()}))
        if u.path == "/api/hyp_job":
            j = HJOBS.get((q.get("id") or [""])[0])
            return self.send(200 if j else 404, j or {"error": "no such job"})
        if u.path == "/api/trade_notes":
            return self.send(200, _notes())
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
            if u.path == "/api/saved_delete":
                n = str(body.get("name", ""))
                if re.fullmatch(r"[\d\- ]+", n):
                    (SAVED / f"{n}.json").unlink(missing_ok=True)
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
                return self.send(200, {"ok": True})
            if u.path == "/api/exitlab_feature":
                return self.send(200, lab_feature(body))
            if u.path == "/api/exitlab_research":
                return self.send(200, lab_research(body))
            if u.path == "/api/ml":
                return self.send(200, ml_start(body))
            if u.path == "/api/lego_test":
                return self.send(200, lego_test(body))
            if u.path == "/api/mission":
                return self.send(200, mission_start(body))
            if u.path == "/api/sim":
                return self.send(200, sim_result(body.get("inputs") or {}, bool(body.get("ema", True)), bool(body.get("setups", True)),
                                                 body.get("ds") or "year", body.get("mode") or "ea", body.get("lab")))
            if u.path == "/api/optimize":
                return self.send(200, opt_start(body))
            if u.path == "/api/opt_stop":
                if OPT["o"]:
                    OPT["o"].stop()
                return self.send(200, {"ok": True})
            if u.path == "/api/follow":
                FOLLOW.update(on=bool(body.get("on")), delay=body.get("delay") or FOLLOW["delay"], key=None, pending=None, msg="")
                return self.send(200, {"ok": True})
            if u.path == "/api/tv_take":                     # one read of TradingView's settings -> run (or the run that already has them)
                info = tv_settings()
                delay = body.get("delay") or "none"
                have = run_matching(info["sets"], delay)
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
                return self.send(200, {"ok": True})
        except Exception as e:                              # noqa: BLE001
            log("POST " + self.path + " failed:\n" + traceback.format_exc())
            return self.send(500, {"error": str(e)[:400]})
        return self.send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=follow_loop, daemon=True).start()
    if not list(RUNS.glob("r*.json")):
        log("no runs yet - starting v1.27 with its defaults (random delay) so the page has a year to show")
        start_run({})
    log(f"Turtle TV on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
