"""validation_run.py - Exit Lab's Validation: every setting the scan suggests, one at a time, run in the tester AND in MT5 (2026, 1-minute,
invisible rig). A setting "matches" when MT5 and the tester agree on the trades (within 10%) and on the sign of the net.
Writes simdata/validation.json (read by the page's Exit Lab's Validation tab).   py validation_run.py [--limit N]"""
import json, os, sys, time, collections, urllib.request as u, datetime as dt
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import server, sim, scan, exitlab
OUT = r"C:\Users\zeesh\turtle\monitor\saad_view\simdata\validation.json"
API = "http://127.0.0.1:8773"

def api(p, b=None):
    r = u.Request(API + p, data=json.dumps(b).encode() if b else None, headers={"Content-Type": "application/json"})
    return json.load(u.urlopen(r, timeout=120))

def mt5(sets, label):
    dfl = server.full_inputs({}); ch = {k: v for k, v in sets.items() if k in dfl and str(v) != str(dfl[k])}
    while api("/api/status")["busy"]: time.sleep(5)
    rid = api("/api/run", {"sets": ch, "delay": "none", "period": "M1", "label": label})["id"]; time.sleep(8)
    while True:
        st = api("/api/status")
        if not st["busy"] and (st["last"] == rid or st["error"]): break
        time.sleep(5)
    if st["error"]: return rid, None, None
    d = api("/api/run?id=" + rid); P = collections.defaultdict(float)
    for e in d["events"]:
        if e["type"] == "exit": P[e["num"]] += e["v1"]
    return rid, len(P), round(sum(P.values()))

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9
    base = server.full_inputs(json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-21 05-55-20.json"))["inputs"])
    base["InpXEntryWait"] = "true"
    mv = scan.moves(base, dict(exitlab.DEFAULT), {})
    seen, picks = set(), []
    for m in mv:                                   # the first suggestion of each setting (the one the scan would offer)
        if m["key"] in seen: continue
        seen.add(m["key"]); picks.append(m)
    import os
    res = json.load(open(OUT))["rows"] if os.path.exists(OUT) else []     # resume: a stopped batch continues where it left off
    done = {x["key"] for x in res}
    # MT5 vs MT5: the primary save as it is, once; each suggestion is then judged on how MT5 moves against that baseline
    if os.path.exists(OUT + ".base"):
        bl = json.load(open(OUT + ".base"))
    else:
        b0 = dict(base); rid0, n0, p0 = mt5(b0, "validation baseline (primary save, MT5)")
        bl = {"run": rid0, "trades": n0, "net": p0}; json.dump(bl, open(OUT + ".base", "w"))
        print("baseline MT5", bl, flush=True)
    for i, m in enumerate(picks[:limit]):
        if m["key"] in done: continue
        s = dict(base, **m["sets"], **m["xs"])
        tr, _, _ = sim.simulate(s, ds="year1"); r = tr[tr[:, 10] == 0]
        tn, tp = int(len(r)), round(float(r[:, 6].sum()))
        rid, mn, mp = mt5(s, f"validation {m['key']} {m['to']}")
        d_mt5 = None if mp is None else mp - bl["net"]
        rec = {"key": m["key"], "label": m["label"], "group": m["group"], "from": m["from"], "to": m["to"], "tester": {"trades": tn, "net": tp},
               "mt5": {"trades": mn, "net": mp, "run": rid}, "baseline": {"trades": bl["trades"], "net": bl["net"], "run": bl["run"]},
               "delta_mt5": d_mt5, "match": bool(d_mt5 is not None and d_mt5 > 0), "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
        res.append(rec)
        json.dump({"base": "2026-10-21 05-55-20", "count": len(res), "of": len(picks), "rows": res}, open(OUT, "w"), indent=1)
        print(i + 1, len(picks), m["key"], "MT5", mp, "vs baseline", bl["net"], "=", d_mt5, "IMPROVED" if rec["match"] else "NOT IMPROVED", flush=True)

if __name__ == "__main__":
    main()
