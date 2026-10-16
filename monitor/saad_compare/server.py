"""saad_compare/server.py - TradingView indicator vs the real EA in MT5, trade by trade.

Zee 2026-10-16: "build a web page. that web page should list trades in a table with 2 columns. one from the
tradingview. one from the MT5 strategy tester. this page allows me to see .. as i tune the tradingview indicator..
how it would look like on the real EA.. on AXI MT5 strategy tester.. on all dates"

    py monitor/saad_compare/server.py        ->  http://127.0.0.1:8772

1. "Read TradingView": the Saad indicator's settings (by position, named from pine/saad_15min.pine) and every
   trade it shows (its export table, switched on for a moment and back off).
2. "Run MT5": the same settings as inputs of mt5/Saad_strategy_1min.mq5 on the Axi rig (C:/mt5_rig_axi), on the
   chart's own timeframe, over any dates. Chart-only rules the EA does not have are listed as warnings.
3. The two trade lists side by side, matched by entry minute (UTC) and side.
"""
import json
import re
import subprocess
import sys
import threading
import time
import html as htmlmod
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "monitor" / "strategy_lab"))
import axi_rig  # noqa: E402

NODE = r"C:\Program Files\nodejs\node.exe"
CLI = r"C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js"
PINE = ROOT / "pine" / "saad_15min.pine"
EA = "Saad_strategy_1min"
PORT = 8772
LOCK = threading.Lock()
STATE = {"tv": None, "mt5": None, "busy": ""}

# Pine variable -> EA input (direct copies)
DIRECT = {"iFast": "InpEmaFast", "iSlow": "InpEmaSlow", "iWick": "InpWickMin", "iBodyMax": "InpBodyMax", "iNose": "InpNoseMax",
          "iPinDir": "InpPinDir", "iPinCol": "InpPinColor", "iUsePin": "InpUsePin", "iMaru": "InpMarubozu", "iMaruB": "InpMaruBody",
          "iHammer": "InpHammer", "iStar": "InpStar", "iHamR": "InpHamRatio", "iHamN": "InpHamNose", "iMinAtr": "InpMinRangeAtr",
          "iTouchP": "InpTouchPips", "iLExitAb": "InpLongExitAbove", "iBreakB": "InpBreakBars", "iBreakP": "InpBreakPips",
          "iSlPips": "InpSlPips", "iMaxRisk": "InpMaxRiskUsd", "iLTpP": "InpLongTpPips", "iPivot": "InpSwingPivot",
          "iLook": "InpSwingLook", "iSTpP": "InpShortTpPips", "iMinTp": "InpMinTpPips", "iMaxTp": "InpMaxTpPips",
          "iCloseM": "InpCloseLossMins", "iLTrail": "InpLongTrailUsd", "iSTrail": "InpShortTrailUsd", "iBePct": "InpBeTpPct",
          "iTrAtr": "InpTrailAtr", "iEr": "InpChopEr", "iErLen": "InpChopErLook", "iGap": "InpGapCancel",
          "iPartial": "InpPartialPct", "iTp1Be": "InpTp1Be", "iLots": "InpLots", "iBuys": "InpBuys", "iSells": "InpSells",
          "pkLockAt": "InpLockAtUsd", "pkLockUsd": "InpLockUsd", "pkGap": "InpTrailGapUsd", "adRunN": "InpCutRunN",
          "rpLook": "InpRangeLook", "rpMin": "InpRangeMin", "rpMax": "InpRangeMax",
          "rpLookS": "InpRangeLookS", "rpMinS": "InpRangeMinS", "rpMaxS": "InpRangeMaxS"}
CHOICES = {"iLRule": ("InpLongRule", {"On 9 EMA, exit 50": 0, "On 50 EMA, exit 9": 1, "Both": 2}),
           "iSLine": ("InpShortLine", {"50 EMA": 0, "9 EMA": 1, "Either": 2}),
           "iTouchM": ("InpTouchMode", {"Candle touches": 0, "Wick touches, body on trade side": 1})}
# chart-only rules the EA does not have: (pine var, value that means "off", what it is)
NOT_IN_EA = [("iTightTrail", False, "Tight trail"), ("iSkipBoth", False, "Skip a candle touching both EMAs"),
             ("pkBeUsd", 0, "STOP NEAR PEAK ① breakeven"), ("pkStep", 0, "STOP NEAR PEAK ③ ladder"),
             ("pkGive", 0, "STOP NEAR PEAK ④ giveback"), ("pkTrail", 0, "STOP NEAR PEAK ⑤ $ trail"),
             ("pkAtr", 0, "STOP NEAR PEAK ⑥ ATR trail"), ("pkLowN", 0, "STOP NEAR PEAK ⑦ candle trail"),
             ("pkEma", 0, "STOP NEAR PEAK ⑧ EMA trail"), ("enMode", "Wick break (EA)", "Entry: candle close beyond"),
             ("adBars", 0, "Cut: still in loss after N candles"), ("adEmaX", False, "Cut: close beyond the slow EMA"),
             ("adMaxUsd", 0, "Cut: max loss $"), ("coolN", 0, "Cool-down after an exit"), ("fxOn", False, "Failed entry exit")]
PERIODS = {"1": "M1", "5": "M5", "15": "M15", "30": "M30", "60": "H1"}


def tv(*args):
    r = subprocess.run([NODE, CLI, *args], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120)
    try:
        return json.loads(r.stdout)
    except Exception:
        raise RuntimeError(f"TradingView bridge: {r.stdout[-400:]} {r.stderr[-400:]}")


def tv_eval(js):
    out = tv("ui", "eval", "--expression", js)
    if not out.get("success"):
        raise RuntimeError(f"TradingView eval failed: {out}")
    res = out.get("result")
    return json.loads(res) if isinstance(res, str) else res


def pine_inputs():
    """Variable names of the indicator's inputs, in the order TradingView stores them (in_0, in_1 ...)."""
    src = PINE.read_text(encoding="utf-8")
    return re.findall(r"^(\w+)\s*=\s*input\.", src, re.M)


JS_STUDY = """(() => { const c = window.TradingViewApi.activeChart(); const st = c.getAllStudies().find(x => x.name.includes('Saad'));
 if (!st) return JSON.stringify({error: 'no Saad indicator on the chart'});
 const iv = c.getStudyById(st.id).getInputValues().filter(v => v.id.startsWith('in_')).map(x => x.value);
 return JSON.stringify({id: st.id, symbol: c.symbol(), res: c.resolution(), values: iv}); })()"""


def set_input(study, idx, value):
    tv_eval("(() => { window.TradingViewApi.activeChart().getStudyById('%s').setInputValues([{id: 'in_%d', value: %s}]); return '1'; })()"
            % (study, idx, json.dumps(value)))


def money(s):
    s = s.replace("$", "").replace(",", "").replace("+", "").strip()
    return float(s.replace("−", "-"))


def read_tv():
    st = tv_eval(JS_STUDY)
    if "error" in st:
        raise RuntimeError(st["error"])
    names = pine_inputs()
    vals = st["values"]
    if len(names) != len(vals):
        raise RuntimeError(f"the chart has {len(vals)} settings but pine/saad_15min.pine declares {len(names)} - update the indicator on the chart")
    settings = dict(zip(names, vals))
    ex_idx = names.index("exOn")
    was = settings["exOn"]
    rows = []
    try:
        if not was:
            set_input(st["id"], ex_idx, True)
        deadline = time.time() + 45
        while time.time() < deadline:
            time.sleep(2)
            data = tv("data", "tables", "--filter", "Saad")
            tabs = [t for s in data.get("studies", []) for t in s.get("tables", [])]
            ex = next((t for t in tabs if t["rows"] and t["rows"][0].startswith("# | side")), None)
            if ex:
                rows = ex["rows"][1:]
                break
    finally:
        if not was:
            set_input(st["id"], ex_idx, False)
    trades = []
    for r in rows:
        c = [x.strip() for x in r.split("|")]
        if len(c) < 8:
            continue
        trades.append({"num": c[0], "side": c[1], "in": c[2], "en": float(c[3]), "sl": float(c[4]), "out": c[5],
                       "ex": float(c[6]), "pnl": money(c[7]), "why": c[8] if len(c) > 8 else ""})
    sets, notes = {}, []
    for pv, ea in DIRECT.items():
        v = settings.get(pv)
        sets[ea] = ("true" if v else "false") if isinstance(v, bool) else str(v)
    for pv, (ea, m) in CHOICES.items():
        sets[ea] = str(m.get(settings.get(pv), 0))
    if settings.get("pkLockAt", 0) and settings.get("pkApply") != "All trades":
        notes.append("Lock is set to 'No-TP1 longs only' on the chart; the EA's lock (InpLockAtUsd) applies to ALL trades")
    for pv, off, what in NOT_IN_EA:
        if settings.get(pv, off) != off:
            notes.append(f"{what} is ON on the chart but the EA does not have it - MT5 runs without it")
    sets["InpLogCsv"] = "false"
    return {"symbol": st["symbol"], "res": st["res"], "period": PERIODS.get(st["res"], "M1"), "settings": settings,
            "ea_sets": sets, "notes": notes, "trades": trades, "read_at": datetime.now().strftime("%H:%M:%S")}


def parse_positions(path, offset_h):
    t = Path(path).read_text(encoding="utf-16", errors="ignore").replace("\xa0", " ")
    deals = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [htmlmod.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if len(c) >= 13 and re.match(r"\d{4}\.\d\d\.\d\d \d\d:\d\d", c[0]) and c[4] in ("in", "out"):
            deals.append(c)
    num = lambda s: float(s.replace(" ", "") or 0)
    utc = lambda s: (datetime.strptime(s[:16], "%Y.%m.%d %H:%M") - timedelta(hours=offset_h)).strftime("%Y-%m-%d %H:%M")
    pos, cur = [], None
    for c in deals:
        tm, _, _, typ, io, vol, px, _, comm, swap, prof = c[:11]
        if io == "in":
            cur = {"side": "BUY" if typ == "buy" else "SELL", "in": utc(tm), "en": float(px), "vol": float(vol),
                   "outs": [], "pnl": num(comm)}
            pos.append(cur)
        elif cur is not None:
            cur["outs"].append((utc(tm), float(px), float(vol)))
            cur["pnl"] += num(prof) + num(comm) + num(swap)
    for p in pos:
        tot = sum(v for _, _, v in p["outs"]) or 1
        p["out"] = p["outs"][-1][0] if p["outs"] else ""
        p["ex"] = round(sum(px * v for _, px, v in p["outs"]) / tot, 2) if p["outs"] else 0
        p["pnl"] = round(p["pnl"], 2)
        del p["outs"]
    return pos


BB_EXE = Path(r"C:\Program Files\Blueberry Markets MetaTrader 5 Terminal\terminal64.exe")
BB_DATA = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\27280402C90F04230EE7E17540AE21E1")


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120).stdout.strip()


def bb_live_run(sets, period, frm, to, delay, tag):
    """Zee 2026-10-16: "can you use the blueberry demo account already logged in. its ok to use the blueberry already open".
    The Strategy Tester of his OWN Blueberry terminal (demo 12665564, symbol XAUUSD = TradingView's BLUEBERRY:XAUUSD feed).
    MT5 runs one copy per data folder, so the open terminal is closed first (gracefully), the test runs with
    ShutdownTerminal=1, and the terminal is opened again afterwards."""
    me = BB_EXE.with_name("MetaEditor64.exe")
    for src, sub in ((ROOT / "mt5" / "SaadEMAs.mq5", "Indicators"), (ROOT / "mt5" / f"{EA}.mq5", "Experts")):
        dst = BB_DATA / "MQL5" / sub / src.name
        dst.write_bytes(src.read_bytes())
        log = BB_DATA / "compare_compile.log"
        subprocess.run([str(me), f"/compile:{dst}", f"/log:{log}"], timeout=180)
        txt = log.read_text(encoding="utf-16", errors="ignore")
        if "Result: 0 errors" not in txt:
            raise RuntimeError(f"compile of {src.name} in the Blueberry terminal failed: {txt[-600:]}")
    exe = str(BB_EXE).replace("'", "''")
    _ps(f"Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq '{exe}' }} | ForEach-Object {{ $_.CloseMainWindow() | Out-Null }}")
    for _ in range(30):
        if not _ps(f"Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq '{exe}' }} | Select-Object -ExpandProperty Id"):
            break
        time.sleep(1)
    else:
        raise RuntimeError("the Blueberry terminal did not close (a dialog open?) - close it and run again")
    inputs = axi_rig.ea_defaults(EA)
    inputs.update(sets)
    ti = "".join(axi_rig.ini_input(k, v) for k, v in inputs.items())
    ini = (f"[Tester]\r\nExpert={EA}\r\nSymbol=XAUUSD\r\nPeriod={period}\r\nModel=4\r\nFromDate={frm}\r\nToDate={to}\r\n"
           f"Deposit=100000\r\nCurrency=USD\r\nLeverage=1:500\r\nExecutionMode={delay}\r\nOptimization=0\r\n"
           f"Report=reports\\{tag}\r\nReplaceReport=1\r\nShutdownTerminal=1\r\nVisual=0\r\n[TesterInputs]\r\n{ti}")
    (BB_DATA / "reports").mkdir(exist_ok=True)     # MT5 writes no report at all when this folder is missing
    cfg = BB_DATA / "compare_run.ini"
    cfg.write_text(ini, encoding="utf-16")
    cands = [BB_DATA / "reports" / f"{tag}.htm", BB_EXE.parent / "reports" / f"{tag}.htm"]
    t0 = time.time()
    try:
        subprocess.run([str(BB_EXE), f"/config:{cfg}"], timeout=3600)
    finally:
        subprocess.Popen([str(BB_EXE)], creationflags=0x00000008)   # give Zee his terminal back (detached)
    rep = next((c for c in cands if c.exists() and c.stat().st_mtime >= t0), None)
    if rep is None:
        raise RuntimeError("the Blueberry tester wrote no report - see the terminal's Journal")
    r = axi_rig.parse(rep)
    r.update(tag=tag, symbol="XAUUSD", period=period)
    return r, rep


def run_mt5(frm, to, symbol, offset_h, delay):
    tvd = STATE["tv"]
    if not tvd:
        raise RuntimeError("read TradingView first")
    rig, _, symbol = symbol.partition("|") if "|" in symbol else ("axi", "", symbol)
    tag = "compare_page"
    # Saad_strategy_1min v1.04 InpBarSource 1: the EA judges the chart's own candles - refresh them from TradingView first
    if str(tvd["ea_sets"].get("InpBarSource", axi_rig.ea_defaults(EA).get("InpBarSource", "0"))) == "1":
        import tv_bars_bridge
        tv_bars_bridge.export(tv_bars_bridge.COMMON / "tv_bars_XAUUSD.csv", more=2)
    if rig == "bblive":
        r, rep = bb_live_run(tvd["ea_sets"], tvd["period"], frm.replace("-", "."), to.replace("-", "."), int(delay), tag)
        pos = parse_positions(rep, offset_h)
        r.pop("daily", None)
        return {"summary": r, "positions": pos, "symbol": "Blueberry demo XAUUSD (your terminal)", "frm": frm, "to": to,
                "offset": offset_h, "delay": delay, "ran_at": datetime.now().strftime("%H:%M:%S")}
    axi_rig.use(rig)               # 'axi' = C:/mt5_rig_axi, 'bb' = C:/mt5_rig_bb (Blueberry)
    axi_rig.compile_ea(EA)
    r = axi_rig.run(EA, symbol, tvd["period"], tvd["ea_sets"], frm=frm.replace("-", "."), to=to.replace("-", "."),
                    deposit=100000, exec_mode=int(delay), tag=tag)
    if r.get("error"):
        raise RuntimeError(f"MT5: {r['error']}")
    pos = parse_positions(axi_rig.RIG / "reports" / f"{tag}.htm", offset_h)
    r.pop("daily", None)
    return {"summary": r, "positions": pos, "symbol": symbol, "frm": frm, "to": to, "offset": offset_h,
            "delay": delay, "ran_at": datetime.now().strftime("%H:%M:%S")}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, (HERE / "index.html").read_text(encoding="utf-8"), "text/html")
        if self.path == "/api/state":
            return self.send(200, json.dumps(STATE))
        self.send(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        q = json.loads(self.rfile.read(n) or b"{}")
        if not LOCK.acquire(blocking=False):
            return self.send(409, json.dumps({"error": f"busy: {STATE['busy']}"}))
        try:
            if self.path == "/api/tv":
                STATE["busy"] = "reading TradingView"
                STATE["tv"] = read_tv()
                return self.send(200, json.dumps(STATE))
            if self.path == "/api/mt5":
                STATE["busy"] = "running the MT5 Strategy Tester"
                if q.get("refresh_tv", True):
                    STATE["tv"] = read_tv()
                STATE["mt5"] = run_mt5(q["from"], q["to"], q.get("symbol", "XAUUSD.pro"), float(q.get("offset", 3)), q.get("delay", -1))
                return self.send(200, json.dumps(STATE))
            self.send(404, "{}")
        except Exception as e:
            self.send(500, json.dumps({"error": str(e)}))
        finally:
            STATE["busy"] = ""
            LOCK.release()


if __name__ == "__main__":
    print(f"Saad compare page: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
