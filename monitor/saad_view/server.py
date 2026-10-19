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
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "monitor" / "strategy_lab"))
import axi_rig  # noqa: E402

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
SETTINGS = HERE / "settings"                  # the JSON hand-off files (format "turtle-settings/1"; see settings_doc)
STATIC = HERE / "static"
TERMINALS = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"
COMMON = TERMINALS / "Common" / "Files"
HIDE = {"InpExport", "InpExportTag", "InpMagicNumber", "InpVerbose", "InpDraw", "InpLog", "InpLogCsv", "InpShowEmas", "InpDrawSkips",
        "InpOptScore", "InpOptMinTrades"}
RUNS.mkdir(exist_ok=True)
SETTINGS.mkdir(exist_ok=True)
STATE = {"busy": False, "id": None, "label": "", "started": None, "phase": "", "error": None, "last": None, "cancel": False, "source": ""}
FOLLOW = {"on": False, "delay": "random", "connected": False, "err": None, "at": None, "tv": None, "key": None, "changed_at": 0,
          "pending": None, "msg": ""}
LOCK = threading.Lock()


def log(msg):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


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
    """The newest run that already has exactly these settings (and delay) - no need to run MT5 again."""
    for p in sorted(RUNS.glob("r*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        if d.get("delay") == delay and all(same(d["inputs"].get(k, v), v) for k, v in sets.items()):
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
    except Exception as e:                                  # noqa: BLE001
        if str(e) != "cancelled":
            traceback.print_exc()
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
            return self.send(200, ea_inputs())
        if u.path == "/api/runs":
            return self.send(200, list_runs())
        if u.path == "/api/run":
            rid = (q.get("id") or [""])[0]
            p = RUNS / f"{rid}.json"
            if not re.fullmatch(r"r\d{8}_\d{6}", rid) or not p.exists():
                return self.send(404, {"error": "no such run"})
            return self.send(200, p.read_bytes())
        if u.path == "/api/status":
            s = {k: v for k, v in STATE.items()}
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
            if u.path == "/api/follow":
                FOLLOW.update(on=bool(body.get("on")), delay=body.get("delay") or FOLLOW["delay"], key=None, pending=None, msg="")
                return self.send(200, {"ok": True})
            if u.path == "/api/tv_take":                     # one read of TradingView's settings -> run (or the run that already has them)
                info = tv_settings()
                delay = body.get("delay") or "random"
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
            return self.send(500, {"error": str(e)[:400]})
        return self.send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=follow_loop, daemon=True).start()
    if not list(RUNS.glob("r*.json")):
        log("no runs yet - starting v1.27 with its defaults (random delay) so the page has a year to show")
        start_run({})
    log(f"Turtle TV on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
