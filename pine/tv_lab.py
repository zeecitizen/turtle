"""tv_lab.py - drive turtle.pine on TradingView Desktop from the command line.

    python pine/tv_lab.py push                  # inject + save + make sure the CHART runs it
    python pine/tv_lab.py set camStrong=1 rULV=false
    python pine/tv_lab.py get [name ...]        # chart values by Pine variable name
    python pine/tv_lab.py score                 # the panel's scorecard + simulated-trade rows

Why each step exists (all learned the hard way, 2026-10-08):
  * inject_pine.py's Save click often does not land in a narrow Pine Editor; Ctrl+S with the
    Monaco textarea focused, or the bridge's `pine save`, does - so push retries both and
    checks the editor footer for "Unsaved version".
  * The chart's copy of the indicator frequently keeps running an OLD version after a save.
    push then adds a fresh copy ("Add to chart"), copies every setting across BY NAME, checks
    them, and removes the stale copy.
  * The chart stores settings by position (in_0..in_N). Names are mapped through the source
    that copy was built from (cached in pine/.tv_lab_last_pushed.pine), so inserting or
    removing an input never shifts values onto the wrong setting.
  * TradingView needs a few seconds to recompute after any change - reads wait for it.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "turtle.pine"
CACHE = REPO / "pine" / ".tv_lab_last_pushed.pine"
NODE = r"C:\Program Files\nodejs\node.exe"
CLI = r"C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js"
PY = sys.executable
STUDY = "Turtle Trader Desk"
DECL = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*input(?:\.\w+)?\(", re.M)


def tv(*args, timeout=120):
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    r = subprocess.run([NODE, CLI, *args], capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"bridge gave no JSON for {args[:2]}: {r.stdout[:300]} {r.stderr[:300]}")


def js(expr):
    out = tv("ui", "eval", "--expression", expr)
    if not out.get("success"):
        raise SystemExit(f"js failed: {out}")
    return out.get("result")


def names(src_text):
    return [m.group(1) for m in DECL.finditer(src_text)]


def study_ids():
    st = tv("state")
    return [s["id"] for s in st.get("studies", []) if s.get("name", "").startswith(STUDY)]


def inputs_of(sid):
    d = tv("indicator", "get", sid)
    return {i["id"]: i["value"] for i in d.get("inputs", [])}


def the_study():
    ids = study_ids()
    if len(ids) != 1:
        raise SystemExit(f"expected one {STUDY} on the chart, found {ids}")
    return ids[0]


def unsaved():
    return bool(js("/Unsaved version/.test(document.body.innerText)"))


def save():
    for attempt in range(6):
        if not unsaved():
            return True
        if attempt % 2 == 0:
            js("(() => { const t = document.querySelector('.monaco-editor textarea'); t && t.focus(); return 1; })()")
            tv("ui", "keyboard", "s", "--ctrl")
        else:
            tv("pine", "save")
        time.sleep(4)
    return not unsaved()


def by_name(values, src_names):
    return {n: values.get(f"in_{i}") for i, n in enumerate(src_names)}


def set_by_name(sid, src_names, wanted):
    idx = {n: i for i, n in enumerate(src_names)}
    payload = {}
    for n, v in wanted.items():
        if n not in idx:
            raise SystemExit(f"no input named {n}")
        payload[f"in_{idx[n]}"] = v
    if payload:
        tv("indicator", "set", sid, "-i", json.dumps(payload))
    return payload


def push():
    new_src = SRC.read_text(encoding="utf-8")
    old_src = CACHE.read_text(encoding="utf-8") if CACHE.exists() else new_src
    r = subprocess.run([PY, str(REPO / "pine" / "inject_pine.py")], capture_output=True, text=True,
                       encoding="utf-8")
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    if r.returncode != 0:
        raise SystemExit("inject failed:\n" + r.stdout[-1500:] + r.stderr[-500:])
    sid = the_study()
    before = inputs_of(sid)
    v0 = before.get("pineVersion")
    if not save():
        raise SystemExit("could not save the script (editor still says Unsaved version)")
    for _ in range(6):
        time.sleep(3)
        cur = inputs_of(sid)
        if cur.get("pineVersion") != v0:
            print(f"chart copy updated itself: {v0} -> {cur.get('pineVersion')}")
            fix_positions(sid, old_src, new_src, before)
            CACHE.write_text(new_src, encoding="utf-8")
            return sid
    print(f"chart copy stuck on {v0} - adding a fresh copy")
    clicked = js("(() => { const b = [...document.querySelectorAll('[title]')].find(e => e.getAttribute('title') === 'Add to chart'); if (!b) return false; b.click(); return true; })()")
    if not clicked:
        raise SystemExit("could not find the Pine Editor 'Add to chart' button")
    new_id = None
    for _ in range(10):
        time.sleep(2)
        ids = [i for i in study_ids() if i != sid]
        if ids:
            new_id = ids[0]
            break
    if not new_id:
        raise SystemExit("no new copy appeared")
    time.sleep(3)
    want = by_name(before, names(old_src))
    new_names = names(new_src)
    want = {n: v for n, v in want.items() if n in new_names and v is not None}
    cur = by_name(inputs_of(new_id), new_names)
    diff = {n: v for n, v in want.items() if cur.get(n) != v}
    set_by_name(new_id, new_names, diff)
    time.sleep(3)
    cur = by_name(inputs_of(new_id), new_names)
    bad = [n for n, v in want.items() if cur.get(n) != v]
    if bad:
        raise SystemExit(f"settings did not carry over: {bad} - old copy {sid} left in place")
    tv("indicator", "remove", sid)
    CACHE.write_text(new_src, encoding="utf-8")
    print(f"swapped {sid} -> {new_id}; {len(want)} settings carried over, {len(diff)} re-applied")
    return new_id


def fix_positions(sid, old_src, new_src, before):
    """The copy updated in place: if inputs moved, put the old values back by name."""
    if names(old_src) == names(new_src):
        return
    want = {n: v for n, v in by_name(before, names(old_src)).items() if n in names(new_src) and v is not None}
    set_by_name(sid, names(new_src), want)
    time.sleep(3)
    print(f"inputs moved - re-applied {len(want)} settings by name")


def score(wait=4.0):
    time.sleep(wait)
    t = tv("data", "tables", "-f", STUDY)
    rows = []
    for st in t.get("studies", []):
        for tb in st.get("tables", []):
            rows += tb.get("rows", [])
    return rows


def parse_score(rows):
    txt = "\n".join(str(r) for r in rows)
    m = re.search(r"(\d+) / (\d+) labels won\s+=\s+(\d+|—)%?", txt)
    if not m:
        return None
    w, n = int(m.group(1)), int(m.group(2))
    halves = re.search(r"[Oo]lder half (\S+)\s+\|\s+newer half (\S+)", txt)
    sim = re.search(r"P&L ([+-]\$[\d.,]+)", txt)
    rnd = re.search(r"random entry scores (\d+)%.*?edge ([+-]?[\d.]+) pts", txt)
    return {"won": w, "n": n, "wr": round(100.0 * w / n, 1) if n else 0.0,
            "older": halves.group(1) if halves else "?", "newer": halves.group(2) if halves else "?",
            "sim_pnl": sim.group(1) if sim else "?", "random": rnd.group(1) if rnd else "?", "edge": float(rnd.group(2)) if rnd else None}


def coerce(v):
    lv = v.lower()
    if lv in ("true", "false"):
        return lv == "true"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"
    if cmd == "push":
        push()
    elif cmd == "set":
        sid = the_study()
        src_names = names(SRC.read_text(encoding="utf-8"))
        current = by_name(inputs_of(sid), src_names)
        wanted = {}
        for a in sys.argv[2:]:
            k, v = a.split("=", 1)
            # keep the setting's own type: a string option like uHTD="15" must stay a string,
            # or TradingView fails the whole script ("Calculation failed")
            wanted[k] = v if isinstance(current.get(k), str) else coerce(v)
        print(set_by_name(sid, src_names, wanted))
    elif cmd == "get":
        sid = the_study()
        vals = by_name(inputs_of(sid), names(SRC.read_text(encoding="utf-8")))
        keys = sys.argv[2:] or list(vals)
        for k in keys:
            print(k, vals.get(k))
    elif cmd == "score":
        rows = score()
        for r in rows:
            print(r)
        print(parse_score(rows))
