"""papers/job.py - run ONE research paper through a headless Claude Fable 5.1 (Claude Code CLI, print mode, Fable 5.1 low effort, no ultracode since 2026-11-02) and keep every trace of it.

Zee 2026-11-01: "when i press the button, it calls Claude Fable 5.1 at high with Ultra Code to build an EA from our default saved setting + new
knowledge from the research paper (e.g. new exit etc) -> then it validates its implemented EA settings extracted from research paper in MT5".

No server import: the server (monitor/saad_view/server.py) calls run() in a daemon thread and reads state(); the CLI below does the same by hand.

    python papers/job.py <id> [--base NAME] [--dry] [--notes TEXT] [--assist]

Store: papers/store/<id>/   paper.pdf, paper.txt, meta.json, prompt.md, log.jsonl (claude stream-json, one JSON per line), log.txt (assistant text +
tool names), result.json + setting.json (written BY THE CLAUDE JOB - contract in PROMPT.md and README.md).
--dry skips Claude and writes a plausible fake result.json / setting.json (marked "dry": true) in well under 2 s, so the page can be tested.
--assist runs the second job (PROMPT_ASSIST.md): implement the EA code the candidate needs (log_assist.jsonl / log_assist.txt, meta.assist).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent                     # monitor/saad_view/papers
VIEW = HERE.parent                                        # monitor/saad_view
ROOT = HERE.parents[2]                                    # the repo: C:\Users\zeesh\turtle
STORE = HERE / "store"
SAVED = VIEW / "settings" / "saved"
PROMPT_FILE = HERE / "PROMPT.md"
ASSIST_FILE = HERE / "PROMPT_ASSIST.md"
MT5_YEARS = VIEW / "research" / "mt5_years.py"
MT5_ROWS = VIEW / "research" / "mt5_years.json"
EA_SRC = ROOT / "mt5" / "Saad_strategy_15min.mq5"
PYTHON = Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe")
MODEL = "claude-fable-5-1"
EFFORT = "low"                                              # Zee 2026-11-02: "Fable 5.1 Low (no ultracode) as its eating up Fable credits very fast"
ALLOWED_TOOLS = "Bash Read Write Edit Glob Grep Workflow Agent ToolSearch WebSearch WebFetch"
DISALLOWED_TOOLS = "Bash(git commit*) Bash(git push*)"
LIVE_TERMINAL_PID = 19700
FALLBACK_BASE = "2026-11-01 08-38-10"
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}-[A-Za-z0-9._-]{1,40}$")
LIMIT_RE = re.compile(r"hit your 5.hour limit|5.hour (usage )?limit|usage limit (reached|hit)|you've reached your .*limit|rate.?limit", re.I)
NO_WINDOW = 0x08000000                                    # CREATE_NO_WINDOW: never a console flashing up from the windowless server
PHASE_EVERY = 2.0                                          # seconds between meta.json rewrites while streaming

LOCK = threading.Lock()
CURRENT = {"id": None, "kind": None, "phase": "", "t0": None, "proc": None, "stop": False}   # one job at a time (the server shows it)


# ---------------------------------------------------------------- helpers
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def paper_dir(pid):
    if not ID_RE.match(pid or ""):
        raise ValueError(f"bad paper id: {pid!r}")
    return STORE / pid


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p, obj):
    Path(p).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def load_meta(pid):
    m = read_json(paper_dir(pid) / "meta.json")
    if not m:
        raise FileNotFoundError(f"no meta.json for {pid}")
    return m


def update_meta(pid, **kw):
    d = paper_dir(pid)
    m = read_json(d / "meta.json", {}) or {}
    m.update(kw)
    write_json(d / "meta.json", m)
    return m


def find_claude():
    """The newest Claude Code CLI in VS Code's extensions (anthropic.claude-code-<ver>-win32-*), else 'claude' on PATH, else None."""
    cands = []
    for p in Path.home().glob(".vscode/extensions/anthropic.claude-code-*-win32-*/resources/native-binary/claude.exe"):
        m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", str(p))
        cands.append((tuple(int(x) for x in m.groups()) if m else (0, 0, 0), p))
    if cands:
        return str(sorted(cands)[-1][1])
    w = shutil.which("claude")
    return w


def claude_version(exe=None):
    exe = exe or find_claude()
    m = re.search(r"claude-code-(\d+\.\d+\.\d+)", exe or "")
    return m.group(1) if m else ("on PATH" if exe else "not found")


def ea_version():
    try:
        m = re.search(r'#property version\s+"([^"]+)"', EA_SRC.read_text(encoding="utf-8", errors="ignore"))
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def saved_names():
    SAVED.mkdir(parents=True, exist_ok=True)
    return sorted((p.stem for p in SAVED.glob("*.json")), reverse=True)


def default_base():
    """The newest saved setting whose name contains 'standard', else the fixed fallback, else the newest save."""
    names = saved_names()
    std = [n for n in names if "standard" in n.lower()]
    if std:
        return std[0]
    if FALLBACK_BASE in names:
        return FALLBACK_BASE
    return names[0] if names else None


def load_base(name):
    p = SAVED / f"{name}.json"
    d = read_json(p)
    if not d or not isinstance(d.get("inputs"), dict):
        raise FileNotFoundError(f"saved setting not found or has no inputs: {name}")
    return d


def candidate_name(pid):
    return f"{pid} candidate"


def safe_text(s, n=400):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


# ---------------------------------------------------------------- the prompt
def build_prompt(meta, base_setting, notes="", template=None):
    """Fill papers/PROMPT.md: every {PLACEHOLDER} (capitals, underscores) is replaced; JSON braces in the template are left alone."""
    pid = meta["id"]
    d = STORE / pid
    base = base_setting or {}
    exe = find_claude()
    vals = {
        "ID": pid,
        "TITLE": safe_text(meta.get("title") or meta.get("file"), 300),
        "FILE": meta.get("file", "paper.pdf"),
        "PAGES": str(meta.get("pages", "?")),
        "STORE_DIR": str(d),
        "PDF": str(d / "paper.pdf"),
        "TXT": str(d / "paper.txt"),
        "RESULT_JSON": str(d / "result.json"),
        "SETTING_JSON": str(d / "setting.json"),
        "LOG_TXT": str(d / "log.txt"),
        "REPO": str(ROOT),
        "VIEW": str(VIEW),
        "PYTHON": str(PYTHON),
        "MT5_YEARS": str(MT5_YEARS),
        "MT5_ROWS": str(MT5_ROWS),
        "SAVED_DIR": str(SAVED),
        "EA_SRC": str(EA_SRC),
        "EA_VERSION": ea_version(),
        "CLAUDE_VERSION": claude_version(exe),
        "BASE_NAME": base.get("name", "?"),
        "BASE_FILE": str(SAVED / f"{base.get('name', '?')}.json"),
        "BASE_CHANGED": json.dumps(base.get("changed", {}), ensure_ascii=False),
        "BASE_RESULT": json.dumps(base.get("result", {}), ensure_ascii=False),
        "BASE_NOTE": safe_text(base.get("note") or base.get("lab_describe") or "-", 600),
        "NOTES": (notes or "").strip() or "(none)",
        "CANDIDATE_NAME": candidate_name(pid),
        "CANDIDATE_FILE": str(SAVED / f"{candidate_name(pid)}.json"),
        "LIVE_PID": str(LIVE_TERMINAL_PID),
        "NOW": now(),
    }
    t = template if template is not None else PROMPT_FILE.read_text(encoding="utf-8")
    missing = set()

    def sub(m):
        k = m.group(1)
        if k in vals:
            return vals[k]
        missing.add(k)
        return m.group(0)
    out = re.sub(r"\{([A-Z][A-Z0-9_]{2,})\}", sub, t)
    if missing:
        out += "\n\n<!-- unfilled placeholders: " + ", ".join(sorted(missing)) + " -->\n"
    return out


def build_assist_prompt(meta, result):
    nc = (result or {}).get("needs_code") or {}
    base = {"name": (result or {}).get("base_setting", {}).get("name", meta.get("base_setting", "?"))}
    t = ASSIST_FILE.read_text(encoding="utf-8")
    t = t.replace("{NEEDS_CODE}", json.dumps(nc, indent=1, ensure_ascii=False))
    t = t.replace("{IDEAS}", json.dumps((result or {}).get("ideas") or [], indent=1, ensure_ascii=False))
    t = t.replace("{SETTING_CHANGED}", json.dumps(((result or {}).get("setting") or {}).get("changed") or {}, ensure_ascii=False))
    return build_prompt(meta, base, notes=meta.get("notes", ""), template=t)


# ---------------------------------------------------------------- the stream
def _summ_tool(name, inp):
    inp = inp or {}
    for k in ("command", "file_path", "pattern", "path", "query", "url", "description", "prompt"):
        if k in inp:
            return f"{name} {safe_text(inp[k], 160)}"
    return name


def _handle_line(line, logtxt, st):
    """One stream-json line -> human lines for log.txt, phase + flags in st (dict)."""
    try:
        ev = json.loads(line)
    except ValueError:
        logtxt.write(line.rstrip() + "\n")
        return
    typ = ev.get("type")
    if typ == "system":
        st["session_id"] = ev.get("session_id") or st.get("session_id")
        st["model"] = ev.get("model") or st.get("model")
        logtxt.write(f"[{now()}] system: {ev.get('subtype', '')} model={st.get('model')} session={st.get('session_id')}\n")
        st["phase"] = "started"
    elif typ == "assistant":
        for c in (ev.get("message") or {}).get("content") or []:
            if c.get("type") == "text" and c.get("text", "").strip():
                txt = c["text"].strip()
                logtxt.write(f"[{now()}] {txt}\n")
                st["phase"] = safe_text(txt, 100)
                st["last_text"] = txt[-4000:]
                if LIMIT_RE.search(txt):
                    st["limit"] = txt[:300]
            elif c.get("type") == "tool_use":
                s = _summ_tool(c.get("name", "tool"), c.get("input"))
                logtxt.write(f"[{now()}] >> {s}\n")
                st["phase"] = "tool: " + s[:120]
                st["tools"] = st.get("tools", 0) + 1
    elif typ == "user":
        for c in (ev.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                body = c.get("content")
                if isinstance(body, list):
                    body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
                logtxt.write(f"[{now()}]    !! tool error: {safe_text(body, 300)}\n")
    elif typ == "result":
        st["result_subtype"] = ev.get("subtype")
        st["is_error"] = bool(ev.get("is_error"))
        st["cost_usd"] = ev.get("total_cost_usd")
        st["num_turns"] = ev.get("num_turns")
        st["duration_ms"] = ev.get("duration_ms")
        res = ev.get("result")
        if isinstance(res, str) and res.strip():
            st["final"] = res.strip()
            if LIMIT_RE.search(res):
                st["limit"] = res[:300]
        errs = ev.get("errors") or []
        if errs:
            st["errors"] = [safe_text(e, 300) for e in errs][:5]
            if any(LIMIT_RE.search(str(e)) for e in errs):
                st["limit"] = str(errs[0])[:300]
        logtxt.write(f"[{now()}] result: {ev.get('subtype')} turns={st.get('num_turns')} cost=${st.get('cost_usd')} error={st['is_error']}\n")
        if st.get("final"):
            logtxt.write(st["final"] + "\n")
    logtxt.flush()


def _kill(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW, timeout=30)
    except Exception:                                      # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:                                      # noqa: BLE001
        pass


def _claude_env():
    env = dict(os.environ)
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"):   # a nested-session marker from the parent would make the CLI refuse
        env.pop(k, None)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _run_claude(pid, prompt, kind, exe):
    """Spawn claude.exe in the repo root, stream stdout into log(.assist).jsonl / .txt, keep phase in CURRENT + meta.json. Returns (exit_code, st)."""
    d = paper_dir(pid)
    suffix = "" if kind == "build" else "_assist"
    jsonl = d / f"log{suffix}.jsonl"
    txt = d / f"log{suffix}.txt"
    args = [exe, "-p", "--model", MODEL, "--effort", EFFORT, "--permission-mode", "acceptEdits",
            "--allowedTools", ALLOWED_TOOLS, "--disallowedTools", DISALLOWED_TOOLS,
            "--output-format", "stream-json", "--verbose", "--add-dir", str(d),
            "--append-system-prompt", SYSTEM_SUFFIX]
    st = {"phase": "launching claude", "tools": 0}
    with open(jsonl, "a", encoding="utf-8") as jf, open(txt, "a", encoding="utf-8") as tf:
        tf.write(f"[{now()}] launch {kind}: {exe} (model {MODEL}, effort {EFFORT}); prompt {len(prompt)} chars on stdin; cwd {ROOT}\n")
        tf.flush()
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT),
                                    creationflags=NO_WINDOW, env=_claude_env())
        except OSError as e:
            tf.write(f"[{now()}] could not start claude.exe: {e}\n")
            st["error"] = f"could not start claude.exe: {e}"
            return -1, st
        CURRENT["proc"] = proc
        err_buf = []

        def drain_err():
            for raw in proc.stderr:
                s = raw.decode("utf-8", "replace").rstrip()
                if s:
                    err_buf.append(s)
                    if len(err_buf) > 200:
                        del err_buf[0]
        threading.Thread(target=drain_err, daemon=True).start()
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except OSError as e:
            tf.write(f"[{now()}] stdin: {e}\n")
        last_meta = 0.0
        for raw in proc.stdout:                            # one JSON per line
            line = raw.decode("utf-8", "replace")
            jf.write(line if line.endswith("\n") else line + "\n")
            jf.flush()
            _handle_line(line, tf, st)
            CURRENT["phase"] = st.get("phase", "")
            if time.time() - last_meta > PHASE_EVERY:
                update_meta(pid, phase=CURRENT["phase"], tools=st.get("tools", 0), **({"session_id": st["session_id"]} if st.get("session_id") else {}))
                last_meta = time.time()
            if CURRENT["stop"]:
                _kill(proc)
                break
        code = proc.wait(timeout=60) if proc.poll() is None else proc.returncode
        if err_buf:
            tf.write(f"[{now()}] stderr tail:\n" + "\n".join(err_buf[-30:]) + "\n")
            st["stderr"] = "\n".join(err_buf[-30:])[-2000:]
            if LIMIT_RE.search(st["stderr"]):
                st["limit"] = st["stderr"][-300:]
        tf.write(f"[{now()}] claude exited with code {code}\n")
    return code, st


SYSTEM_SUFFIX = (
    "You are Claude Fable 5.1 (claude-fable-5-1) at LOW effort running HEADLESS from Turtle TV's Research page (Zee is not watching; nobody "
    "answers questions - decide and go on). Work alone and economically: no Workflow tool, no sub-agents (Zee: credits). "
    "HARD RULES: never `git commit` or `git push` (the human commits); never touch the live MetaTrader terminal (PID " + str(LIVE_TERMINAL_PID) +
    " - use only the portable rigs named in the prompt); never edit LAWS.md (read-only, Zeeshan's own); a Python / Turtle-TV-tester number is a "
    "HYPOTHESIS, only MT5's Strategy Tester with random delay judges; new EA behaviour defaults OFF. Finish by writing the files the prompt names."
)


# ---------------------------------------------------------------- dry run
def _dry_outputs(pid, meta, base, notes):
    """A complete, plausible fake: the base setting's inputs with ONE input changed, marked dry: true. Written in milliseconds."""
    d = paper_dir(pid)
    inputs = dict(base.get("inputs") or {})
    changed = dict(base.get("changed") or {})
    key = "InpAdxMin" if "InpAdxMin" in inputs else next(iter(inputs), "InpAdxMin")
    old = inputs.get(key, "0")
    try:
        new = str(int(float(old)) + 5)
    except ValueError:
        new = old
    inputs[key] = new
    changed[key] = new
    title = meta.get("title") or meta.get("file")
    base_res = base.get("result") or {}
    name = candidate_name(pid)
    note = f"DRY RUN (no Claude) - {title}: {key} {old} -> {new} on top of {base.get('name')}; numbers below are invented placeholders"
    setting = {"name": name, "inputs": inputs, "changed": changed, "ds": "m15", "mode": "ea",
               "result": {"n": base_res.get("n", 0), "net": base_res.get("net", 0), "pf": base_res.get("pf", 0), "wr": base_res.get("wr", 0),
                          "avg_loss": base_res.get("avg_loss", 0), "worst_loss": base_res.get("worst_loss", 0), "dd": base_res.get("dd", 0),
                          "ret_dd": base_res.get("ret_dd", 0)},
               "lab": {}, "lab_describe": "", "note": note, "dry": True,
               "source": {"kind": "research_paper", "paper": title, "id": pid, "pdf": meta.get("file"), "built": now(), "dry": True}}
    years = {"2023": {"n": 40, "wr": 95.0, "net": 15000}, "2024": {"n": 90, "wr": 96.7, "net": 36000},
             "2025": {"n": 130, "wr": 96.9, "net": 50000}, "2026": {"n": 125, "wr": 97.6, "net": 53000}}
    rows = []
    for y in years:
        for dl in ("none", "random"):
            rows.append({"year": int(y), "delay": dl, "trades": years[y]["n"], "net": years[y]["net"] * (1.0 if dl == "none" else 0.97),
                         "wr": years[y]["wr"] - (0 if dl == "none" else 0.4), "worst": -5500, "pf": 2.5})
    tot = lambda dl: {"trades": sum(r["trades"] for r in rows if r["delay"] == dl), "net": round(sum(r["net"] for r in rows if r["delay"] == dl), 1),
                      "wr": round(sum(r["wr"] * r["trades"] for r in rows if r["delay"] == dl) / max(1, sum(r["trades"] for r in rows if r["delay"] == dl)), 2)}
    mt5 = {"rows": rows, "total_none": tot("none"), "total_random": tot("random"), "dry": True}
    base_mt5 = mt5_rows_for(f"save:{base.get('name')}") or {"rows": [], "total_none": None, "total_random": None, "note": "no MT5 rows for the base yet"}
    result = {"id": pid, "title": title, "authors": "(dry run - not read)", "year": None,
              "summary": f"DRY RUN. Claude was not called. This placeholder stands in for the paper '{title}' so the Research page can be exercised "
                         f"end to end: upload, build, poll, save, delete. Nothing here was read from the PDF." + (f" Zee's notes: {notes}" if notes else ""),
              "ideas": [{"idea": f"(dry) nudge {key}", "where": "filter", "implementable": True, "mapping": f"{key} {old} -> {new}"},
                        {"idea": "(dry) an exit idea that would need new EA code", "where": "exit", "implementable": "needs_code",
                         "mapping": "a new input InpPaperExit (default false) - not implemented in a dry run"}],
              "base_setting": {"name": base.get("name"), "result": base_res},
              "setting": {k: setting[k] for k in ("name", "inputs", "changed", "note", "ds", "mode")},
              "needs_code": {"required": False, "version": None, "files": [], "inputs": [], "summary": "dry run: nothing implemented"},
              "tester": {"n": base_res.get("n"), "wr": base_res.get("wr"), "net": base_res.get("net"), "pf": base_res.get("pf"),
                         "worst_loss": base_res.get("worst_loss"), "dd": base_res.get("dd"),
                         "per_year": {y: {"n": v["n"], "wr": v["wr"], "net": v["net"]} for y, v in years.items()}, "hypothesis": True, "dry": True},
              "mt5": mt5, "base_mt5": base_mt5,
              "verdict": "DRY RUN - no paper was read, no tester ran, no MT5 pass ran. These numbers are placeholders. Run the real build for a verdict.",
              "status": "done", "built": now(), "dry": True, "notes": notes or ""}
    write_json(d / "setting.json", setting)
    write_json(d / "result.json", result)
    SAVED.mkdir(parents=True, exist_ok=True)
    write_json(SAVED / f"{name}.json", setting)           # the real job drops its candidate here too (mt5_years.py's save: gate reads it)
    with open(d / "log.txt", "a", encoding="utf-8") as tf:
        tf.write(f"[{now()}] DRY RUN: wrote result.json, setting.json and {SAVED / (name + '.json')} without calling Claude\n")
    return result


# ---------------------------------------------------------------- MT5 rows (research/mt5_years.json) for a gate, in the page's shape
def _row_wr(r):
    t = r.get("trade_stats") or {}
    n = t.get("n") or 0
    aw, al = t.get("avg_win") or 0, t.get("avg_loss") or 0
    if r.get("wr") not in (None, ""):
        try:
            return round(float(str(r["wr"]).rstrip("%")), 2)
        except ValueError:
            pass
    if n and aw != al:
        return round(100 * (r["net"] - n * al) / (aw - al) / n, 2)
    return None


def mt5_rows_for(gate, period="M15"):
    """{rows: [{year, delay, trades, net, wr, worst, pf}], total_none, total_random} from research/mt5_years.json, or None when no rows."""
    rows = read_json(MT5_ROWS, []) or []
    out = []
    for r in rows:
        if r.get("gate") != gate or r.get("period", "M1") != period or r.get("error"):
            continue
        t = r.get("trade_stats") or {}
        try:
            pf = float(str(r.get("pf") or "0").replace(",", ""))
        except ValueError:
            pf = None
        out.append({"year": r["year"], "delay": r["delay"], "trades": t.get("n") or r.get("trades"), "net": r.get("net"),
                    "wr": _row_wr(r), "worst": t.get("largest_loss"), "pf": pf})
    if not out:
        return None
    out.sort(key=lambda x: (x["year"], x["delay"]))

    def tot(dl):
        rs = [x for x in out if x["delay"] == dl]
        if not rs:
            return None
        n = sum(x["trades"] or 0 for x in rs)
        wrs = [x for x in rs if x["wr"] is not None and x["trades"]]
        return {"trades": n, "net": round(sum(x["net"] or 0 for x in rs), 1),
                "wr": round(sum(x["wr"] * x["trades"] for x in wrs) / max(1, sum(x["trades"] for x in wrs)), 2) if wrs else None,
                "years": len(rs)}
    return {"rows": out, "total_none": tot("none"), "total_random": tot("random"), "gate": gate}


# ---------------------------------------------------------------- state / run / stop
def busy():
    return CURRENT["id"] is not None


def state():
    """{id, kind, phase, seconds} of the running job, or None."""
    if not CURRENT["id"]:
        return None
    return {"id": CURRENT["id"], "kind": CURRENT["kind"], "phase": CURRENT["phase"],
            "seconds": round(time.time() - CURRENT["t0"], 1) if CURRENT["t0"] else 0}


def stop(pid):
    """Kill the running job for this paper (the whole claude.exe tree). Returns True if something was running."""
    if CURRENT["id"] != pid:
        return False
    CURRENT["stop"] = True
    _kill(CURRENT["proc"])
    return True


def _finish_meta(pid, kind, code, st, ok, error):
    fields = {"finished": now(), "exit_code": code, "phase": "done" if ok else "failed"}
    if kind == "build":
        fields.update(status="done" if ok else "failed", error=error)
    else:
        m = load_meta(pid)
        a = dict(m.get("assist") or {})
        a.update(status="done" if ok else "failed", error=error, finished=fields["finished"], exit_code=code)
        fields = {"assist": a, "phase": fields["phase"]}
    extra = {k: st.get(k) for k in ("session_id", "cost_usd", "num_turns", "duration_ms", "tools") if st.get(k) is not None}
    if kind == "build":
        fields.update(extra)
    update_meta(pid, **fields)


def run(pid, base=None, notes="", dry=False, kind="build"):
    """The whole job for one paper. Returns the exit code (0 = result.json says done). Raises RuntimeError when another job runs."""
    d = paper_dir(pid)
    meta = load_meta(pid)
    with LOCK:
        if CURRENT["id"]:
            raise RuntimeError(f"a job is already running ({CURRENT['id']})")
        CURRENT.update(id=pid, kind=kind, phase="starting", t0=time.time(), proc=None, stop=False)
    code, st, error, ok = -1, {}, None, False
    try:
        base_name = base or meta.get("base_setting") or default_base()
        if kind == "build":
            update_meta(pid, status="running", started=now(), finished=None, error=None, exit_code=None, phase="starting",
                        base_setting=base_name, notes=notes or meta.get("notes", ""), dry=bool(dry))
            try:
                base_setting = load_base(base_name)
            except FileNotFoundError as e:
                raise RuntimeError(str(e))
            prompt = build_prompt(meta, base_setting, notes)
            (d / "prompt.md").write_text(prompt, encoding="utf-8")
            if dry:
                CURRENT["phase"] = "dry run"
                _dry_outputs(pid, meta, base_setting, notes)
                code, ok = 0, True
            else:
                exe = find_claude()
                if not exe:
                    raise RuntimeError("claude.exe not found (no anthropic.claude-code-* extension and no 'claude' on PATH)")
                code, st = _run_claude(pid, prompt, kind, exe)
                res = read_json(d / "result.json")
                ok = bool(res) and res.get("status") == "done" and (d / "setting.json").is_file() and not CURRENT["stop"]
        else:                                             # assist: implement the EA code the candidate needs
            res = read_json(d / "result.json") or {}
            a = {"status": "running", "started": now(), "finished": None, "error": None, "exit_code": None}
            update_meta(pid, assist=a, phase="assist: starting")
            prompt = build_assist_prompt(meta, res)
            (d / "prompt_assist.md").write_text(prompt, encoding="utf-8")
            if dry:
                CURRENT["phase"] = "assist dry run"
                with open(d / "log_assist.txt", "a", encoding="utf-8") as tf:
                    tf.write(f"[{now()}] DRY RUN: assist prompt written, Claude not called\n")
                code, ok = 0, True
            else:
                exe = find_claude()
                if not exe:
                    raise RuntimeError("claude.exe not found")
                code, st = _run_claude(pid, prompt, kind, exe)
                ok = code == 0 and not st.get("is_error") and not CURRENT["stop"]
        if not ok and not error:
            if CURRENT["stop"]:
                error = "stopped by Zee"
            elif st.get("limit"):
                error = "Claude's 5-hour usage limit was hit: " + safe_text(st["limit"], 200) + " - retry when it resets"
            elif st.get("errors"):
                error = "; ".join(st["errors"])[:400]
            elif st.get("is_error") and st.get("final"):
                error = safe_text(st["final"], 400)
            elif kind == "build" and code == 0 and not (d / "result.json").is_file():
                error = "Claude finished but wrote no result.json (see log.txt)"
            elif kind == "build" and (read_json(d / "result.json") or {}).get("status") == "failed":
                error = safe_text((read_json(d / "result.json") or {}).get("error") or "the job reported status failed", 400)
            else:
                error = f"claude.exe exited with code {code}" + (f": {safe_text(st.get('stderr'), 200)}" if st.get("stderr") else "")
    except Exception as e:                                 # noqa: BLE001
        error = safe_text(e, 400)
        ok = False
        with open(d / ("log.txt" if kind == "build" else "log_assist.txt"), "a", encoding="utf-8") as tf:
            tf.write(f"[{now()}] job error: {e}\n")
    finally:
        try:
            _finish_meta(pid, kind, code, st, ok, error)
        finally:
            with LOCK:
                CURRENT.update(id=None, kind=None, phase="", t0=None, proc=None, stop=False)
    return 0 if ok else (code if code not in (0, None) else 1)


# ---------------------------------------------------------------- CLI
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", help="paper id = folder name under papers/store/")
    ap.add_argument("--base", default=None, help="saved setting name (default: newest containing 'standard', else " + FALLBACK_BASE + ")")
    ap.add_argument("--dry", action="store_true", help="no Claude: write a fake result.json / setting.json")
    ap.add_argument("--notes", default="", help="Zee's free-text notes for the prompt")
    ap.add_argument("--assist", action="store_true", help="run the 'implement the EA code' job instead of the build")
    ap.add_argument("--prompt-only", action="store_true", help="write prompt.md and print it, run nothing")
    a = ap.parse_args()
    if a.prompt_only:
        m = load_meta(a.id)
        p = build_prompt(m, load_base(a.base or m.get("base_setting") or default_base()), a.notes)
        (paper_dir(a.id) / "prompt.md").write_text(p, encoding="utf-8")
        print(p)
        sys.exit(0)
    rc = run(a.id, a.base, a.notes, dry=a.dry, kind="assist" if a.assist else "build")
    m = load_meta(a.id)
    print(json.dumps({"id": a.id, "exit": rc, "status": m.get("status"), "error": m.get("error"), "phase": m.get("phase"),
                      "assist": m.get("assist")}, ensure_ascii=False))
    sys.exit(rc)
