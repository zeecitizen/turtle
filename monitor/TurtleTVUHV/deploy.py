"""deploy.py - Zee 2026-11-02: "create a deploy page where one can input the settings for server / folder path etc to deploy to.. and then in
settings add a button next to Download MT5 -> Deploy EA to Server which when clicked compiles the current strategy in list of saved settings
into an EA file and deploys". A saved setting -> turtle-settings/1 JSON -> make_ea_from_settings.py (its inputs become the EA's defaults) ->
MetaEditor compile in a rig -> scp (.ex5 + .mq5 + the .mqh includes) into the target terminal's MQL5\\Experts over ssh with the saved password
(Windows OpenSSH + an SSH_ASKPASS .cmd; paramiko has no ARM64 wheel here). Target settings live in settings/deploy_target.json (git-ignored).
One deployment at a time; the page polls GET /api/deploy."""
import json, os, re, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "monitor" / "strategy_lab"))
import axi_rig                                                   # noqa: E402

CFG = HERE / "settings" / "deploy_target.json"
DEFAULT_CFG = {"name": "AWS VM · PXBT MT5", "host": "51.20.122.18", "user": "Administrator", "password": "",
               "remote_dir": r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\BCB580088311575081ABF4FB040CCFF8\MQL5\Experts",
               "rig": "axi4", "ea_prefix": "Saad_", "include_source": True, "log_skips": True,
               "remote_common": r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\Common\Files"}
NO_WINDOW = 0x08000000
ST = {"running": False, "phase": "", "log": [], "done": False, "error": None, "ea": None, "target": None, "started": None, "secs": 0, "setting": None, "history": []}
LOCK = threading.Lock()


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if CFG.is_file():
        try:
            cfg.update(json.loads(CFG.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return cfg


def save_cfg(body):
    cfg = load_cfg()
    for k in DEFAULT_CFG:
        if k in body:
            cfg[k] = body[k]
    CFG.parent.mkdir(exist_ok=True)
    CFG.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return cfg


def public_cfg():
    cfg = load_cfg()
    return {**cfg, "password": "", "has_password": bool(cfg.get("password"))}


def _askpass(cfg):
    f = HERE / "settings" / ".deploy_askpass.cmd"
    f.write_text("@echo off\r\necho " + str(cfg.get("password", "")).replace("%", "%%") + "\r\n", encoding="ascii", errors="replace")
    return f


def _env(cfg):
    env = dict(os.environ)
    env.update({"SSH_ASKPASS": str(_askpass(cfg)), "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": "x"})
    return env


def _opts():
    return ["-o", "ConnectTimeout=25", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=NUL", "-o", "PreferredAuthentications=password"]


def _clean(stderr):
    return "\n".join(l for l in (stderr or "").splitlines() if l and "quantum" not in l and "vulnerable" not in l and "upgraded" not in l and "Permanently added" not in l)


def ssh(cfg, cmd, timeout=90):
    r = subprocess.run(["ssh", *_opts(), f"{cfg['user']}@{cfg['host']}", cmd], capture_output=True, text=True, env=_env(cfg), timeout=timeout, creationflags=NO_WINDOW)
    return r.returncode, r.stdout.strip(), _clean(r.stderr)


def test_target(body=None):
    """POST /api/deploy_test -> can we log in, does the folder exist, is a terminal running there"""
    cfg = load_cfg() if not body else {**load_cfg(), **{k: v for k, v in body.items() if k in DEFAULT_CFG and v != ""}}
    if not cfg.get("password"):
        return {"ok": False, "error": "no password saved for the target"}
    t0 = time.time()
    try:
        rc, out, err = ssh(cfg, f'if exist "{cfg["remote_dir"]}" (echo DIR_OK) else (echo DIR_MISSING) & tasklist /FI "IMAGENAME eq terminal64.exe" /NH', timeout=60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ssh timed out (host down, port 22 closed, or wrong IP)"}
    if rc != 0:
        return {"ok": False, "error": (err or f"ssh exit {rc}")[-400:], "secs": round(time.time() - t0, 1)}
    return {"ok": True, "login": True, "dir_ok": "DIR_OK" in out, "terminal_running": "terminal64.exe" in out, "secs": round(time.time() - t0, 1), "out": out[-400:]}


def _log(msg):
    ST["phase"] = msg
    ST["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")


def _slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return s[:40] or "setting"


def start(name, saved_dir, rig_busy=lambda: False):
    """POST /api/deploy {name} -> a thread: saved setting -> EA defaults -> compile -> scp to the target. Returns {ok, ea} or {error}."""
    cfg = load_cfg()
    if ST["running"]:
        return {"error": "a deployment is already running"}
    if not cfg.get("password"):
        return {"error": "no deploy target password saved - fill the Deploy page first"}
    p = Path(saved_dir) / f"{name}.json"
    if not p.is_file():
        return {"error": f"saved setting not found: {name}"}
    saved = json.loads(p.read_text(encoding="utf-8"))
    ea = cfg.get("ea_prefix", "Saad_") + _slug(name)
    ST.update(running=True, phase="starting", log=[], done=False, error=None, ea=ea, target=f"{cfg['user']}@{cfg['host']}:{cfg['remote_dir']}", started=time.time(), secs=0, setting=name)

    def go():
        try:
            src_ea = "Saad_strategy_15min"
            dfl = axi_rig.ea_defaults(src_ea)
            inputs = {k: str(v) for k, v in saved.get("inputs", {}).items() if k in dfl}
            for k, v in dfl.items():
                inputs.setdefault(k, str(v))
            if cfg.get("log_skips", True):                            # the Fetch History button reads these two CSVs from the server's Common\Files
                inputs["InpLogCsv"] = "true"
                if "InpSkipLog" in dfl:
                    inputs["InpSkipLog"] = "true"
            doc = {"format": "turtle-settings/1", "written_by": "Turtle TV deploy", "written_at": time.strftime("%Y-%m-%d %H:%M:%S"), "ea": src_ea,
                   "ea_version": re.search(r'#property version\s+"([^"]+)"', (ROOT / "mt5" / f"{src_ea}.mq5").read_text(encoding="utf-8", errors="ignore")).group(1),
                   "ea_inputs": inputs, "changed_from_defaults": {k: v for k, v in inputs.items() if str(dfl[k]) != v}, "chart_only": [], "chart": {}, "tradingview": {}, "mt5_result": None}
            jpath = HERE / "settings" / f"deploy_{_slug(name)}.json"
            jpath.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            _log(f"1/5 writing the EA '{ea}' with the setting's {len(doc['changed_from_defaults'])} changed inputs as defaults")
            g = subprocess.run([sys.executable, str(HERE / "make_ea_from_settings.py"), str(jpath), "--out", ea, "--version", doc["ea_version"]],
                               capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW)
            if g.returncode or not (ROOT / "mt5" / f"{ea}.mq5").is_file():
                raise RuntimeError("EA generation failed: " + (g.stderr or g.stdout).strip()[-600:])
            _log("2/5 waiting for the compile rig" if rig_busy() else "2/5 compiling in MetaEditor (rig %s)" % cfg.get("rig", "axi4"))
            for _ in range(300):
                if not rig_busy():
                    break
                time.sleep(2)
            c = axi_rig.compile_ea(ea, rig=cfg.get("rig", "axi4"))
            _log(f"3/5 compiled: {c['errors']} errors, {c['warnings']} warnings")
            rig_root = Path(axi_rig.RIGS.get(cfg.get("rig", "axi4"), cfg.get("rig", "axi4")))
            ex5 = rig_root / "MQL5" / "Experts" / f"{ea}.ex5"
            files = [ex5]
            if cfg.get("include_source", True):
                files.append(ROOT / "mt5" / f"{ea}.mq5")
                for inc in re.findall(r'#include\s+"([^"]+)"', (ROOT / "mt5" / f"{ea}.mq5").read_text(encoding="utf-8", errors="ignore")):
                    if (ROOT / "mt5" / inc).is_file():
                        files.append(ROOT / "mt5" / inc)
            _log(f"4/5 copying {len(files)} files to {cfg['user']}@{cfg['host']} ({cfg['remote_dir']})")
            rc, out, err = ssh(cfg, f'if not exist "{cfg["remote_dir"]}" mkdir "{cfg["remote_dir"]}"', timeout=60)
            if rc != 0:
                raise RuntimeError("ssh login / folder check failed: " + (err or f"exit {rc}")[-400:])
            remote = cfg["remote_dir"].replace("\\", "/")
            r = subprocess.run(["scp", *_opts(), *[str(f) for f in files], f"{cfg['user']}@{cfg['host']}:{remote}/"], capture_output=True, text=True, env=_env(cfg), timeout=300, creationflags=NO_WINDOW)
            if r.returncode:
                raise RuntimeError("scp failed: " + (_clean(r.stderr) or r.stdout)[-400:])
            rc, out, err = ssh(cfg, f'dir /-C "{cfg["remote_dir"]}\\{ea}.*"', timeout=60)
            size = re.search(rf"(\d+)\s+{re.escape(ea)}\.ex5", out)
            if not size or int(size.group(1)) != ex5.stat().st_size:
                raise RuntimeError(f"the copied {ea}.ex5 does not match ({out[-300:]})")
            _log(f"5/5 verified on the server: {ea}.ex5 {ex5.stat().st_size:,} bytes" + (" · terminal64.exe is running there - refresh the Navigator, then drag the EA onto the XAUUSD M15 chart" if "terminal64.exe" in (ssh(cfg, 'tasklist /FI "IMAGENAME eq terminal64.exe" /NH', 60)[1]) else " · no MT5 terminal running there right now"))
            ST["done"] = True
            ST["history"].insert(0, {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "setting": name, "ea": ea, "target": ST["target"], "files": [f.name for f in files], "secs": round(time.time() - ST["started"])})
            ST["history"] = ST["history"][:20]
        except Exception as e:                                    # noqa: BLE001
            ST["error"] = str(e)[:600]
            _log("FAILED: " + ST["error"])
        finally:
            ST["secs"], ST["running"] = round(time.time() - ST["started"]), False
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True, "ea": ea, "target": ST["target"]}


def state():
    out = {k: v for k, v in ST.items()}
    if ST["running"] and ST["started"]:
        out["secs"] = round(time.time() - ST["started"])
    return out


# ---------------------------------------------------------------- Fetch History (Zee 2026-11-03): the deployed EA's real trades + its skipped setups
HIST_DIR = HERE / "settings" / "deploy_history"


def _csv_rows(path):
    import csv
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch_history():
    r"""POST /api/deploy_history -> scp Common\Files\Saad15_trades_*.csv + Saad15_skips_*.csv from the target, parse, summarise per skip reason"""
    cfg = load_cfg()
    if not cfg.get("password"):
        return {"error": "no deploy target password saved"}
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    remote = cfg.get("remote_common", DEFAULT_CFG["remote_common"])
    t0 = time.time()
    rc, out, err = ssh(cfg, 'dir /B "' + remote + '\\Saad15_*.csv"', timeout=60)
    names = [l.strip() for l in out.splitlines() if l.strip().lower().endswith(".csv")] if rc == 0 else []
    if rc != 0 and "File Not Found" not in (out + err):
        return {"error": "ssh failed: " + (err or out or f"exit {rc}")[-300:]}
    got = []
    for n in names:
        r = subprocess.run(["scp", *_opts(), f"{cfg['user']}@{cfg['host']}:{remote.replace(chr(92), '/')}/{n}", str(HIST_DIR / n)], capture_output=True, text=True, env=_env(cfg), timeout=120, creationflags=NO_WINDOW)
        if r.returncode == 0:
            got.append(n)
    trades, skips = [], []
    for n in got:
        rows = _csv_rows(HIST_DIR / n)
        if n.startswith("Saad15_trades_"):
            for r in rows:
                trades.append({**r, "file": n, "net_f": _num(r.get("net")), "profit_f": _num(r.get("profit"))})
        elif n.startswith("Saad15_skips_"):
            for r in rows:
                skips.append({**r, "file": n, "pnl_f": _num(r.get("pnl_usd"))})
    trades.sort(key=lambda r: r.get("entry_time", "")); skips.sort(key=lambda r: r.get("skip_time", ""))
    # the verdict per skip reason: what the skipped trades would have made (virtual outcome at the EA's lots)
    by = {}
    for r in skips:
        key = re.sub(r"[\d.]+", "#", r.get("reason", "").split("|")[0]).strip()[:60] or "?"
        b = by.setdefault(key, {"reason": key, "skips": 0, "resolved": 0, "tp": 0, "stop": 0, "timeout": 0, "pending": 0, "pnl": 0.0, "never_triggered": 0})
        b["skips"] += 1
        oc = (r.get("outcome") or "").lower()
        if "never" in oc:
            b["never_triggered"] += 1
        elif r["pnl_f"] is None:
            b["pending"] += 1
        else:
            b["resolved"] += 1; b["pnl"] += r["pnl_f"]
            b["tp" if "take" in oc else "stop" if "stop" in oc else "timeout"] += 1
    for b in by.values():
        b["pnl"] = round(b["pnl"], 2)
        b["verdict"] = ("no resolved skip yet" if not b["resolved"] else
                        f"skipping these COST ${b['pnl']:,.0f} - {b['tp']} of {b['resolved']} would have hit TP" if b["pnl"] > 0 else
                        f"skipping these SAVED ${-b['pnl']:,.0f} - {b['stop']} of {b['resolved']} would have hit the stop" if b["pnl"] < 0 else "neutral")
    closed = [t for t in trades if t.get("net_f") is not None]
    summary = {"trades": len(trades), "closed": len(closed), "wins": sum(1 for t in closed if t["net_f"] > 0), "net": round(sum(t["net_f"] for t in closed), 2),
               "skips": len(skips), "skips_resolved": sum(1 for r in skips if r["pnl_f"] is not None), "skips_pnl": round(sum(r["pnl_f"] for r in skips if r["pnl_f"] is not None), 2),
               "skips_pending": sum(1 for r in skips if r["pnl_f"] is None and "never" not in (r.get("outcome") or "").lower()),
               "files": got, "fetched": time.strftime("%Y-%m-%d %H:%M:%S"), "secs": round(time.time() - t0, 1), "remote": remote}
    out = {"summary": summary, "trades": trades[-300:], "skips": skips[-500:], "by_reason": sorted(by.values(), key=lambda b: -abs(b["pnl"]))}
    (HIST_DIR / "last_fetch.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def last_history():
    f = HIST_DIR / "last_fetch.json"
    if not f.is_file():
        return {"summary": None}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"summary": None}
