r"""selftest.py - HTTP end-to-end test of the Research page machinery, in DRY mode (no Claude).

    py monitor\saad_view\papers\selftest.py              # against http://127.0.0.1:8773
    py monitor\saad_view\papers\selftest.py --schema     # print the result.json key schema and exit
    py monitor\saad_view\papers\selftest.py --keep       # leave the store entry + saved file behind
    py monitor\saad_view\papers\selftest.py --base http://127.0.0.1:8773 --pdf <file> --timeout 60

Steps (PASS/FAIL each, exit 1 on any FAIL):
  1. GET  /api/research                       -> shape {papers, running, claude, bases, default_base}
  2. POST /api/research_upload {name, b64}    -> {ok, id, title, pages}; store/<id>/paper.pdf, paper.txt non-empty, meta.json
  3. POST /api/research_build {id, dry: true} -> {ok}; the server MUST honour "dry" (job.run(..., dry=True))
  4. poll GET /api/research until the paper's status is done (<= --timeout s)
  5. store/<id>/result.json has every contract key, status done, "dry": true; setting.json present
  6. POST /api/research_save {id}             -> {ok, name}; settings/saved/<name>.json has source.kind == research_paper
  7. GET  /api/saved lists it with the source block (what the 📄 badge renders from)
  8. POST /api/research_delete {id}           -> store entry gone; remove the saved test file (unless --keep)

Never runs the real Claude job. Protocol: papers/README.md.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):                             # Windows console is cp1252; the names carry a 📄
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass

HERE = os.path.dirname(os.path.abspath(__file__))                    # monitor/saad_view/papers
SAAD_VIEW = os.path.dirname(HERE)                                     # monitor/saad_view
STORE = os.path.join(HERE, "store")
SAVED = os.path.join(SAAD_VIEW, "settings", "saved")
REPO = os.path.dirname(os.path.dirname(SAAD_VIEW))                    # C:\Users\zeesh\turtle
EXAMPLE_PDF = os.path.join(REPO, "research", "HierarchicalExecutionArchitecturesinTransformer-DrivenAlgorithmicTrading.pdf")

# ---- the result.json contract (README §3). Top-level keys + the shape of the nested blocks. ----
RESULT_KEYS = ["id", "title", "authors", "year", "summary", "ideas", "base_setting", "setting", "needs_code",
               "tester", "mt5", "base_mt5", "verdict", "status", "built"]
IDEA_KEYS = ["idea", "where", "implementable", "mapping"]
IDEA_WHERE = {"entry", "exit", "sizing", "filter", "other"}
SETTING_KEYS = ["name", "inputs", "changed", "note", "ds", "mode"]
NEEDS_CODE_KEYS = ["required", "version", "files", "inputs", "summary"]
TESTER_KEYS = ["n", "wr", "net", "pf", "worst_loss", "dd", "per_year"]
MT5_KEYS = ["rows", "total_none", "total_random"]
MT5_ROW_KEYS = ["year", "delay", "trades", "net", "wr", "worst", "pf"]
META_KEYS = ["id", "file", "title", "uploaded", "pages", "status"]
RESEARCH_KEYS = ["papers", "running", "claude", "bases", "default_base"]
SOURCE_KEYS = ["kind", "paper", "id", "pdf", "built", "needs_code"]

SCHEMA = {
    "GET /api/research": RESEARCH_KEYS,
    "meta.json": META_KEYS + ["base_setting", "started", "finished", "error", "exit_code"],
    "result.json": RESULT_KEYS,
    "result.ideas[]": IDEA_KEYS,
    "result.ideas[].where": sorted(IDEA_WHERE),
    "result.setting": SETTING_KEYS,
    "result.needs_code": NEEDS_CODE_KEYS,
    "result.tester": TESTER_KEYS,
    "result.mt5 / result.base_mt5": MT5_KEYS,
    "result.mt5.rows[]": MT5_ROW_KEYS,
    "saved file .source": SOURCE_KEYS,
}

RESULTS = []                                                          # (step, ok, detail)
BASE = "http://127.0.0.1:8773"


def report(step, ok, detail=""):
    RESULTS.append((step, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + step + (("  - " + str(detail)) if detail else ""), flush=True)
    return bool(ok)


def http(base, path, body=None, timeout=30):
    """GET when body is None, POST (JSON) otherwise. Returns (status_code, parsed_json_or_text)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        code = e.code
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}
    try:
        return code, json.loads(raw.decode("utf-8"))
    except Exception:                                                 # noqa: BLE001
        return code, raw.decode("utf-8", "replace")


def missing(d, keys):
    return [k for k in keys if not isinstance(d, dict) or k not in d]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_paper(research, pid):
    for p in (research or {}).get("papers") or []:
        if isinstance(p, dict) and p.get("id") == pid:
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8773")
    ap.add_argument("--pdf", default=EXAMPLE_PDF)
    ap.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for the dry build")
    ap.add_argument("--keep", action="store_true", help="do not delete the store entry / saved file at the end")
    ap.add_argument("--schema", action="store_true", help="print the key schema this test asserts and exit")
    a = ap.parse_args()

    if a.schema:
        print(json.dumps(SCHEMA, indent=2, ensure_ascii=False))
        return 0

    global BASE
    base = BASE = a.base.rstrip("/")
    pid = None
    saved_name = None
    saved_path = None

    # ---- 0. preflight: server up, PDF present ----------------------------------------------------------
    if not report("0. example PDF exists", os.path.isfile(a.pdf), a.pdf):
        return finish()
    code, st = http(base, "/api/status")
    if not report("0. server answers /api/status", code == 200 and isinstance(st, dict), f"{code} {str(st)[:120]}"):
        return finish()

    # ---- 1. GET /api/research shape --------------------------------------------------------------------
    code, res = http(base, "/api/research")
    ok = code == 200 and isinstance(res, dict) and not missing(res, RESEARCH_KEYS)
    report("1. GET /api/research shape", ok, f"{code} missing={missing(res, RESEARCH_KEYS)}" if not ok else
           f"{len(res.get('papers') or [])} papers · claude.found={(res.get('claude') or {}).get('found')} · bases={len(res.get('bases') or [])}")
    if ok:
        report("1. claude block {exe, found}", not missing(res.get("claude"), ["exe", "found"]), str(res.get("claude"))[:160])
        report("1. bases is a list of saved names", isinstance(res.get("bases"), list) and all(isinstance(b, str) for b in res["bases"]),
               f"default_base={res.get('default_base')!r}")
        if res.get("running"):
            report("1. no research job already running", False, f"running={res['running']} - a build is in progress; the dry build would be refused")
            return finish()
    else:
        return finish()

    # ---- 2. upload ---------------------------------------------------------------------------------------
    with open(a.pdf, "rb") as f:
        pdf_bytes = f.read()
    name = os.path.basename(a.pdf)
    code, up = http(base, "/api/research_upload", {"name": name, "b64": base64.b64encode(pdf_bytes).decode("ascii")}, timeout=120)
    ok = code == 200 and isinstance(up, dict) and up.get("ok") and up.get("id")
    if not report("2. POST /api/research_upload -> {ok, id, title, pages}", ok and not missing(up, ["ok", "id", "title", "pages"]),
                  f"{code} {str(up)[:200]}"):
        return finish()
    pid = up["id"]
    report("2. id has no commas and starts with a stamp", ("," not in pid) and len(pid) >= 19 and pid[4] == "-" and pid[10] == " ",
           pid)
    report("2. pages == 11 for the example paper", (name != os.path.basename(EXAMPLE_PDF)) or up.get("pages") == 11, f"pages={up.get('pages')}")
    sdir = os.path.join(STORE, pid)
    report("2. store/<id>/ exists", os.path.isdir(sdir), sdir)
    report("2. paper.pdf byte-identical to the upload",
           os.path.isfile(os.path.join(sdir, "paper.pdf")) and open(os.path.join(sdir, "paper.pdf"), "rb").read() == pdf_bytes)
    txt_path = os.path.join(sdir, "paper.txt")
    txt = open(txt_path, encoding="utf-8", errors="replace").read() if os.path.isfile(txt_path) else ""
    report("2. paper.txt non-empty (pypdf text)", len(txt.strip()) > 200, f"{len(txt)} chars")
    meta_path = os.path.join(sdir, "meta.json")
    meta = read_json(meta_path) if os.path.isfile(meta_path) else {}
    report("2. meta.json has the contract keys", not missing(meta, META_KEYS), f"missing={missing(meta, META_KEYS)} status={meta.get('status')}")
    report("2. meta.status == uploaded", meta.get("status") == "uploaded", meta.get("status"))
    report("2. title non-empty and echoed by the upload", bool(up.get("title")) and up.get("title") == meta.get("title"),
           repr(up.get("title"))[:100])
    code, res = http(base, "/api/research")
    report("2. GET /api/research lists the new paper", bool(find_paper(res, pid)))

    # ---- 3. dry build ------------------------------------------------------------------------------------
    body = {"id": pid, "dry": True, "notes": "selftest - dry run, no Claude"}
    if res.get("default_base"):
        body["base"] = res["default_base"]
    code, bd = http(base, "/api/research_build", body)
    ok = code == 200 and isinstance(bd, dict) and bd.get("ok") and not bd.get("error")
    if not report("3. POST /api/research_build {id, dry: true} -> {ok}", ok,
                  f"{code} {str(bd)[:200]}" + ("" if ok else "   <- S must honour body.dry (job.run(dry=True))")):
        return finish(pid, a.keep)

    # ---- 4. poll -----------------------------------------------------------------------------------------
    t0 = time.time()
    status = None
    seen_running = False
    p = {}
    while time.time() - t0 < a.timeout:
        code, res = http(base, "/api/research")
        p = find_paper(res, pid) or {}
        status = p.get("status")
        if (res or {}).get("running") and (res["running"] or {}).get("id") == pid:
            seen_running = True
        if status in ("done", "failed"):
            break
        time.sleep(1.0)
    took = round(time.time() - t0, 1)
    if not report(f"4. dry build reaches status done within {a.timeout:.0f}s", status == "done",
                  f"status={status} after {took}s" + (f" error={p.get('error')!r}" if status == "failed" else "")):
        return finish(pid, a.keep)
    report("4. running block showed {id, phase, seconds} during the job (informational)", True,
           "seen" if seen_running else "not observed (job finished between polls) - fine")
    code, res = http(base, "/api/research")
    report("4. running is null after the job", (res or {}).get("running") in (None, {}), str((res or {}).get("running")))
    meta = read_json(meta_path) if os.path.isfile(meta_path) else {}
    report("4. meta.json status done · finished · exit_code present", meta.get("status") == "done" and meta.get("finished") and "exit_code" in meta,
           f"status={meta.get('status')} exit_code={meta.get('exit_code')} dry={meta.get('dry')}")
    for fn in ("prompt.md", "log.txt"):
        report(f"4. store/<id>/{fn} written", os.path.isfile(os.path.join(sdir, fn)) and os.path.getsize(os.path.join(sdir, fn)) > 0)
    code, lg = http(base, f"/api/research_log?id={urllib.request.quote(pid)}")
    report("4. GET /api/research_log -> {lines, status}", code == 200 and isinstance(lg, dict) and isinstance(lg.get("lines"), list) and "status" in lg,
           f"{code} lines={len((lg or {}).get('lines') or []) if isinstance(lg, dict) else '?'} status={(lg or {}).get('status') if isinstance(lg, dict) else '?'}")

    # ---- 5. result.json / setting.json contract -----------------------------------------------------------
    rpath = os.path.join(sdir, "result.json")
    if not report("5. result.json exists", os.path.isfile(rpath), rpath):
        return finish(pid, a.keep)
    r = read_json(rpath)
    report("5. result.json top-level keys", not missing(r, RESULT_KEYS), f"missing={missing(r, RESULT_KEYS)}")
    report("5. result.status == done", r.get("status") == "done", r.get("status"))
    report("5. result.id == store id", r.get("id") == pid, r.get("id"))
    report('5. dry result marked "dry": true', r.get("dry") is True, f"dry={r.get('dry')!r}")
    report("5. summary <= 120 words", isinstance(r.get("summary"), str) and 0 < len(r["summary"].split()) <= 120,
           f"{len(str(r.get('summary', '')).split())} words")
    ideas = r.get("ideas")
    ideas_ok = isinstance(ideas, list) and len(ideas) > 0 and all(not missing(i, IDEA_KEYS) for i in ideas)
    report("5. ideas[] non-empty with {idea, where, implementable, mapping}", ideas_ok,
           f"{len(ideas) if isinstance(ideas, list) else '?'} ideas" + (f" missing={[missing(i, IDEA_KEYS) for i in ideas]}" if isinstance(ideas, list) and not ideas_ok else ""))
    if ideas_ok:
        report("5. ideas[].where in entry|exit|sizing|filter|other", all(i.get("where") in IDEA_WHERE for i in ideas),
               str([i.get("where") for i in ideas]))
        report("5. ideas[].implementable in true|false|needs_code", all(i.get("implementable") in (True, False, "needs_code") for i in ideas),
               str([i.get("implementable") for i in ideas]))
    report("5. base_setting {name, result}", not missing(r.get("base_setting"), ["name", "result"]), str((r.get("base_setting") or {}).get("name")))
    setting = r.get("setting") or {}
    report("5. setting block keys", not missing(setting, SETTING_KEYS), f"missing={missing(setting, SETTING_KEYS)}")
    report("5. setting.name has no commas", isinstance(setting.get("name"), str) and "," not in setting["name"], repr(setting.get("name"))[:80])
    report("5. setting.ds == m15 and mode == ea", setting.get("ds") == "m15" and setting.get("mode") == "ea", f"ds={setting.get('ds')} mode={setting.get('mode')}")
    n_inputs = len(setting.get("inputs") or {})
    report("5. setting.inputs is a full EA input set (>= 150 keys, string values)",
           isinstance(setting.get("inputs"), dict) and n_inputs >= 150 and all(isinstance(v, str) for v in setting["inputs"].values()),
           f"{n_inputs} inputs")
    report("5. setting.changed is a dict", isinstance(setting.get("changed"), dict), f"{len(setting.get('changed') or {})} changed")
    nc = r.get("needs_code") or {}
    report("5. needs_code keys · required is bool", not missing(nc, NEEDS_CODE_KEYS) and isinstance(nc.get("required"), bool),
           f"missing={missing(nc, NEEDS_CODE_KEYS)} required={nc.get('required')!r}")
    tester = r.get("tester") or {}
    report("5. tester keys (hypothesis block)", not missing(tester, TESTER_KEYS), f"missing={missing(tester, TESTER_KEYS)}")
    report("5. tester.per_year is a dict keyed by year", isinstance(tester.get("per_year"), dict) and
           all(str(k).isdigit() and not missing(v, ["n", "wr", "net"]) for k, v in tester["per_year"].items()),
           str(list((tester.get("per_year") or {}).keys())))
    for blk in ("mt5", "base_mt5"):
        m = r.get(blk) or {}
        # totals may be null when there are no rows yet (e.g. the base has no MT5 rows in mt5_years.json); the page renders them as '–'
        tot_ok = (lambda t: (t is None and not m.get("rows")) or not missing(t, ["trades", "net", "wr"]))
        okb = not missing(m, MT5_KEYS) and isinstance(m.get("rows"), list) and all(not missing(x, MT5_ROW_KEYS) for x in m["rows"]) \
            and tot_ok(m.get("total_none")) and tot_ok(m.get("total_random"))
        report(f"5. {blk} {{rows[], total_none, total_random}} shape", okb,
               f"{len(m.get('rows') or []) if isinstance(m.get('rows'), list) else '?'} rows · missing={missing(m, MT5_KEYS)}")
        if okb and m["rows"]:
            report(f"5. {blk}.rows[].delay in none|random · year int", all(x.get("delay") in ("none", "random") and isinstance(x.get("year"), int) for x in m["rows"]),
                   str([(x.get("year"), x.get("delay")) for x in m["rows"]])[:160])
    report("5. verdict is a non-empty paragraph", isinstance(r.get("verdict"), str) and len(r["verdict"].strip()) > 20, f"{len(str(r.get('verdict', '')))} chars")
    report("5. built is set", bool(r.get("built")), str(r.get("built")))
    spath = os.path.join(sdir, "setting.json")
    if report("5. setting.json exists", os.path.isfile(spath), spath):
        s = read_json(spath)
        report("5. setting.json = saved-setting schema (name, inputs, changed, ds, mode, result)",
               not missing(s, ["name", "inputs", "changed", "ds", "mode", "result"]), f"missing={missing(s, ['name', 'inputs', 'changed', 'ds', 'mode', 'result'])}")
        report("5. setting.json carries source.kind research_paper", (s.get("source") or {}).get("kind") == "research_paper", str(s.get("source"))[:120])
    code, res = http(base, "/api/research")
    p = find_paper(res, pid) or {}
    # the server nests result.json under "result" (what research.js reads: p.result.verdict); a merged top-level copy is also accepted
    pres = p.get("result") if isinstance(p.get("result"), dict) else {}
    has_verdict = "verdict" in pres or "verdict" in p
    report("5. GET /api/research carries result (p.result) + has_setting", p.get("has_setting") is True and p.get("status") == "done" and has_verdict,
           f"has_setting={p.get('has_setting')} status={p.get('status')} verdict={has_verdict}")

    # ---- 6. save -----------------------------------------------------------------------------------------
    code, sv = http(base, "/api/research_save", {"id": pid})
    ok = code == 200 and isinstance(sv, dict) and sv.get("ok") and sv.get("name")
    if not report("6. POST /api/research_save -> {ok, name, needs_code}", ok and "needs_code" in sv, f"{code} {str(sv)[:200]}"):
        return finish(pid, a.keep)
    saved_name = sv["name"]
    saved_path = os.path.join(SAVED, saved_name + ".json")
    report("6. saved name has no commas and the 📄 marker", "," not in saved_name and "📄" in saved_name, saved_name)
    if report("6. settings/saved/<name>.json exists", os.path.isfile(saved_path), saved_path):
        sf = read_json(saved_path)
        report("6. saved file name field == file name", sf.get("name") == saved_name, repr(sf.get("name"))[:80])
        src = sf.get("source") or {}
        report("6. saved file source.kind == research_paper", src.get("kind") == "research_paper", str(src)[:160])
        report("6. saved file source {paper, id, pdf, built, needs_code}", not missing(src, SOURCE_KEYS) and src.get("id") == pid,
               f"missing={missing(src, SOURCE_KEYS)} id_ok={src.get('id') == pid}")
        report("6. saved file is loadable by the page (inputs, result, ds m15, mode ea)",
               isinstance(sf.get("inputs"), dict) and isinstance(sf.get("result"), dict) and sf.get("ds") == "m15" and sf.get("mode") == "ea")
    # save must also work when the "<id> candidate" file exists (the job may leave it) - a second save must not fail
    code, sv2 = http(base, "/api/research_save", {"id": pid})
    report("6. second save is idempotent / does not error", code == 200 and isinstance(sv2, dict) and sv2.get("ok"), f"{code} {str(sv2)[:160]}")
    extra_saved = sv2.get("name") if isinstance(sv2, dict) and sv2.get("name") and sv2.get("name") != saved_name else None

    # ---- 7. GET /api/saved lists it -----------------------------------------------------------------------
    code, rows = http(base, "/api/saved")
    row = next((x for x in (rows if isinstance(rows, list) else []) if isinstance(x, dict) and x.get("name") == saved_name), None)
    report("7. GET /api/saved returns the research save", row is not None, f"{code} {len(rows) if isinstance(rows, list) else '?'} rows")
    if row is not None:
        src = row.get("source") or {}
        report("7. row.source.kind research_paper · paper · id · built (badge data)",
               src.get("kind") == "research_paper" and src.get("paper") and src.get("id") == pid and src.get("built"), str(src)[:160])

    # ---- 8. delete + cleanup -------------------------------------------------------------------------------
    if a.keep:
        report("8. --keep: leaving store entry and saved file", True, f"{sdir} · {saved_path}")
        return finish()
    code, dl = http(base, "/api/research_delete", {"id": pid})
    report("8. POST /api/research_delete -> {ok}", code == 200 and isinstance(dl, dict) and dl.get("ok"), f"{code} {str(dl)[:120]}")
    report("8. store/<id>/ removed", not os.path.isdir(sdir), sdir)
    code, res = http(base, "/api/research")
    report("8. GET /api/research no longer lists it", find_paper(res, pid) is None)
    report("8. delete left the saved-settings copy alone", os.path.isfile(saved_path), saved_path)
    removed = []
    for nm in [saved_name, extra_saved, f"{pid} candidate"]:
        if not nm:
            continue
        pth = os.path.join(SAVED, nm + ".json")
        if os.path.isfile(pth):
            try:
                os.remove(pth)
                removed.append(nm)
            except OSError as e:
                report(f"8. remove saved test file {nm}", False, str(e))
    report("8. saved test file(s) removed", not os.path.isfile(saved_path), ", ".join(removed) or "nothing to remove")
    return finish()


def finish(pid=None, keep=False):
    """Print the tally; attempt a best-effort cleanup of a half-finished store entry; return the exit code."""
    if pid and not keep:
        sdir = os.path.join(STORE, pid)
        if os.path.isdir(sdir):
            http(BASE, "/api/research_delete", {"id": pid})
            print(f"      (cleanup: research_delete {pid}: {'removed' if not os.path.isdir(sdir) else 'STILL PRESENT - remove by hand'})")
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    n_bad = len(RESULTS) - n_ok
    print(f"\n{'ALL PASS' if n_bad == 0 else 'FAILED'}  {n_ok} passed · {n_bad} failed · {len(RESULTS)} steps")
    if n_bad:
        for step, ok, detail in RESULTS:
            if not ok:
                print("   x " + step + ("  - " + str(detail) if detail else ""))
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
