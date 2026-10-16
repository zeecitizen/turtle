"""axi_rig.py - run MT5 Strategy Tester passes on the portable Axi copy (C:\\mt5_rig_axi).

Never touches the live Axi terminal. Each pass: compile (once), write an ini with EVERY
input pinned (MT5 reuses cached inputs when [TesterInputs] is empty), run, parse the report.

    py axi_rig.py --ea VSISA --symbol XAUUSD.pro --period M5 --set InpCompoundBase=0
"""
import argparse, re, subprocess, shutil, html, json, sys, time
from pathlib import Path

RIG = Path(r"C:\mt5_rig_axi")
SRC = Path(r"C:\Users\zeesh\turtle\mt5")
RIGS = {"axi": r"C:\mt5_rig_axi", "axi2": r"C:\mt5_rig_axi2", "axi3": r"C:\mt5_rig_axi3", "axi4": r"C:\mt5_rig_axi4",
        "axi5": r"C:\mt5_rig_axi5", "axi6": r"C:\mt5_rig_axi6", "axi7": r"C:\mt5_rig_axi7",
        "bb": r"C:\mt5_rig_bb", "pxbt": r"C:\mt5_rig_pxbt",
        "rig1": r"C:\mt5_rig_axi"}   # rig1 = the compare page's own test copy (Zee 2026-10-17: no "Axi" on the page)


NO_WINDOW = 0x08000000        # CREATE_NO_WINDOW: no console flashing up when called from a windowless server (pythonw)


def _quiet():
    """Start a rig's MetaEditor / terminal minimised and without taking the focus (the year view starts 6 at once)."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7            # SW_SHOWMINNOACTIVE
    return si


def _R(rig=None):
    """rig=None -> the rig chosen with use(); otherwise a name or path. Pass it explicitly from threads
    (saad_compare/year_runner.py drives several rigs at once; use() is one global)."""
    return Path(RIGS.get(rig, rig)) if rig else RIG


def use(rig):
    """Point every call at another portable rig: 'axi', 'bb', 'pxbt' or a path."""
    global RIG
    RIG = Path(RIGS.get(rig, rig))


def compile_ea(ea, rig=None):
    R = _R(rig)
    shutil.copy(SRC / f"{ea}.mq5", R / "MQL5" / "Experts" / f"{ea}.mq5")
    log = R / "compile.log"
    subprocess.run([str(R / "MetaEditor64.exe"), "/portable",
                    f"/compile:{R / 'MQL5' / 'Experts' / (ea + '.mq5')}", f"/log:{log}"], creationflags=NO_WINDOW, startupinfo=_quiet())
    txt = log.read_text(encoding="utf-16", errors="ignore")
    if not re.search(r"Result: 0 errors", txt):
        sys.exit("compile failed:\n" + txt[-2000:])


def ea_defaults(ea):
    """Every `input` default straight from the source, so nothing is left to the cache."""
    out = {}
    src = (SRC / f"{ea}.mq5").read_text(encoding="utf-8", errors="ignore")
    # inputs declared in local include files too (engine .mqh): unpinned, MT5 reuses the LAST run's values
    for inc in re.findall(r'^#include\s+"([^"]+\.mqh)"', src, re.M):
        if (SRC / inc).exists():
            src = (SRC / inc).read_text(encoding="utf-8", errors="ignore") + "\n" + src
    for m in re.finditer(r"^input\s+\w+\s+(\w+)\s*=\s*([^;]+);", src, re.M):
        v = m.group(2).strip().strip('"')
        out[m.group(1)] = {"PERIOD_M1": "1", "PERIOD_M5": "5", "PERIOD_M15": "15", "PERIOD_M30": "30", "PERIOD_H1": "16385"}.get(v, v)
    return out


def kill_rig(rig=None):
    """Kill ONLY the rig's own terminal / tester agents (never a live terminal)."""
    R = _R(rig)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | "
                    f"Where-Object {{ $_.Path -like '{R}\*' }} | Stop-Process -Force"], capture_output=True, creationflags=NO_WINDOW)


def prune_logs(max_mb=50, rig=None):
    """Agent logs grew to 381-866 MB (the $2 trail modifies the stop on most ticks); drop the big ones."""
    R = _R(rig)
    for f in list((R / "Tester").glob("Agent-*/logs/*.log")) + list((R / "Tester" / "logs").glob("*.log")):
        try:
            if f.stat().st_size > max_mb * 1024 * 1024 and f.resolve().is_relative_to(R.resolve()):
                f.unlink()
        except Exception:
            pass


def ini_input(k, v):
    """One [TesterInputs] line. Numbers / bools take the optimiser form "v||v||0||v||N"; a string input must be
    plain "k=v" - the range form became the string's value itself (Saad_strategy_1min v1.04 InpTvFile)."""
    s = str(v)
    try:
        float(s)
        num = True
    except ValueError:
        num = s.lower() in ("true", "false")
    return f"{k}={s}||{s}||0||{s}||N\r\n" if num else f"{k}={s}\r\n"


def run(ea, symbol, period, sets, frm="2026.01.01", to="2026.10.08", deposit=25000,
        exec_mode=-1, tag=None, timeout=21600, model=4, leverage="1:400", watchdog=True, rig=None, cancel=None):
    """rig: run on this rig instead of the use() one. cancel: a callable; when it returns True the pass is
    killed and {"error": "cancelled"} returned (the year view drops a run the moment a chart setting changes)."""
    R = _R(rig)
    inputs = ea_defaults(ea)
    inputs.update(sets)
    tag = tag or f"{ea}_{symbol}_{period}".replace(".", "_")
    ti = "".join(ini_input(k, v) for k, v in inputs.items())
    ini = (f"[Tester]\r\nExpert={ea}\r\nSymbol={symbol}\r\nPeriod={period}\r\nModel={model}\r\n"
           f"FromDate={frm}\r\nToDate={to}\r\nDeposit={deposit}\r\nCurrency=USD\r\n"
           f"Leverage={leverage}\r\nExecutionMode={exec_mode}\r\nOptimization=0\r\n"
           f"Report=reports\\{tag}\r\nReplaceReport=1\r\nShutdownTerminal=1\r\nVisual=0\r\n"
           f"[TesterInputs]\r\n{ti}")
    (R / "reports").mkdir(exist_ok=True)
    (R / "run.ini").write_text(ini, encoding="utf-16")
    prune_logs(rig=R)
    t0 = time.time()
    rep = R / "reports" / f"{tag}.htm"
    auth0 = _auth_fails(R)
    proc = subprocess.Popen([str(R / "terminal64.exe"), "/portable", f"/config:{R / 'run.ini'}"], startupinfo=_quiet())
    last_size, stable = -1, 0
    while True:
        time.sleep(1)
        done = proc.poll() is not None
        if rep.exists() and rep.stat().st_mtime >= t0:
            sz = rep.stat().st_size
            stable = stable + 1 if sz == last_size and sz > 0 else 0
            last_size = sz
            if watchdog and stable >= 2:          # report written and no longer growing: stop waiting
                break
        if done:
            break
        if cancel is not None and cancel():
            kill_rig(R)
            return {"tag": tag, "error": "cancelled"}
        if time.time() - t0 > timeout:
            kill_rig(R)
            return {"tag": tag, "error": f"timeout {timeout}s"}
    if proc.poll() is None:
        time.sleep(1)
        kill_rig(R)
    if not rep.exists() or rep.stat().st_mtime < t0:
        return {"tag": tag, "error": "no report"}
    if _auth_fails(R) > auth0:                     # the agent never ran: MT5 still writes an empty report that reads as $0
        return {"tag": tag, "error": "authorization failed"}
    r = parse(rep, comm_per_lot=4.0 if symbol.endswith("_TK") else 0.0)
    r["comm_added"] = symbol.endswith("_TK")
    r.update(tag=tag, symbol=symbol, period=period, sets=sets, secs=round(time.time() - t0))
    return r


def _auth_fails(R):
    """Count of 'authorization failed' lines in the rig's newest tester log (2026-10-17: axi7 failed this way and the
    pass was reported as a quiet $0 week)."""
    logs = sorted((Path(R) / "Tester" / "logs").glob("*.log"), key=lambda f: f.stat().st_mtime)
    return logs[-1].read_text(encoding="utf-16", errors="ignore").count("authorization failed") if logs else 0


def parse(path, comm_per_lot=0.0):
    """comm_per_lot: charge this $ per lot per round trip on exit deals when the report shows no commission
    (custom tick symbols carry none; Axi XAUUSD.pro charges ~$4/lot round trip)."""
    t = Path(path).read_text(encoding="utf-16", errors="ignore").replace("\xa0", " ")
    num = lambda s: float(s.replace(" ", ""))

    def field(label):
        m = re.search(re.escape(label) + r"[^<]*:</td>\s*<td[^>]*><b>([^<]*)", t)
        return m.group(1) if m else ""
    deals = re.findall(r"<tr[^>]*><td>(\d{4}\.\d\d\.\d\d) [\d:]+</td><td>\d+</td><td>[^<]+</td>"
                       r"<td>(?:buy|sell)</td><td>(in|out)</td><td>([\d.]+)</td><td>[\d.]+</td>"
                       r"<td>\d+</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td>", t)
    has_comm = any(num(c) != 0 for d, io, vol, c, s, p in deals)
    extra = 0.0
    if comm_per_lot and not has_comm:
        fixed = []
        for d, io, vol, c, s, p in deals:
            cc = -comm_per_lot * float(vol) if io == "out" else 0.0
            extra += cc
            fixed.append((d, io, vol, str(cc), s, p))
        deals = fixed
    months, days, daily = {}, set(), {}
    for d, io, vol, c, s, p in deals:
        v = num(c) + num(s) + num(p)
        months[d[:7]] = months.get(d[:7], 0) + v
        daily[d] = daily.get(d, 0) + v
        if io == "in":
            days.add(d)
    # per trade (one position at a time): its entry commission + all its exit deals (partial closes included)
    tr, cur = [], None
    for d, io, vol, c, s, p in deals:
        v = num(c) + num(s) + num(p)
        if io == "in":
            if cur is not None:
                tr.append(cur)
            cur = v
        else:
            cur = (cur or 0) + v
    if cur is not None:
        tr.append(cur)
    streak = mx = 0
    for v in tr:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    wins = [v for v in tr if v > 0]; losses = [v for v in tr if v < 0]
    trade_stats = {"n": len(tr), "largest_loss": round(min(tr), 2) if tr else 0, "largest_win": round(max(tr), 2) if tr else 0,
                   "avg_win": round(sum(wins) / len(wins), 2) if wins else 0, "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
                   "max_loss_streak": mx, "per_trade": round(sum(tr) / len(tr), 2) if tr else 0}
    dv = list(daily.values())
    day_stats = {"days": len(dv), "green": sum(v > 0 for v in dv), "red": sum(v < 0 for v in dv),
                 "worst": round(min(dv), 2) if dv else 0, "best": round(max(dv), 2) if dv else 0,
                 "median": round(sorted(dv)[len(dv) // 2], 2) if dv else 0}
    dd = field("Equity Drawdown Maximal")
    net = num(field("Total Net Profit") or "0") + extra
    ddv = num(dd.split("(")[0]) if dd else 0
    trades = int(field("Total Trades") or 0)
    pt = field("Profit Trades")
    return {"net": net, "pf": field("Profit Factor"), "trades": trades,
            "wr": pt.split("(")[-1].rstrip(")") if pt else "",
            "dd": dd, "net_per_dd": round(net / ddv, 2) if ddv else None,
            "quality": field("History Quality"), "trade_days": len(days), "day_stats": day_stats, "trade_stats": trade_stats,
            "daily": {k: round(v, 2) for k, v in sorted(daily.items())},
            "months": {k: round(v, 2) for k, v in sorted(months.items())}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ea", default="VSISA")
    ap.add_argument("--symbol", default="XAUUSD.pro")
    ap.add_argument("--period", default="M5")
    ap.add_argument("--from", dest="frm", default="2026.01.01")
    ap.add_argument("--to", default="2026.10.08")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--tag")
    ap.add_argument("--nocompile", action="store_true")
    a = ap.parse_args()
    if not a.nocompile:
        compile_ea(a.ea)
    sets = dict(kv.split("=", 1) for kv in a.set)
    print(json.dumps(run(a.ea, a.symbol, a.period, sets, a.frm, a.to, tag=a.tag), indent=1))
