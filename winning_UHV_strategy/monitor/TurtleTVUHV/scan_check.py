"""scan_check.py - "Scan every setting", checked against its own promises.

   py monitor/saad_view/scan_check.py

1. the scan's numbers for a move = the bench's numbers after picking that move (the page's path: explicit Exit Lab form + EA settings)
2. the scan's "now" = the bench
3. exit mode 0: no Exit Lab moves, nothing forced to mode 1, "now" = the plain run
4. no move that cannot trade (slow EMA <= fast, session end <= start)
5. only moves that can act (no fallback in exit mode 2 / with a lab target, no sweep settings without the sweep entry)
6. choice settings carry names; every move changes something
7. a broken worker pool is dropped and the next scan gets a fresh one"""
import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
sys.path.insert(0, str(Path(__file__).parent))

BAD = []


def ok(name, cond, detail=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        BAD.append(name)


def main():
    import random
    import exitlab
    import scan
    import server
    inp = server.full_inputs({})
    D = dict(exitlab.DEFAULT)
    for ds in ("year",):
        for nm, sets, form in (("defaults, mode 1", {}, dict(D)), ("a lab exit on the bench", {"InpSlAtrMult": "1.4"}, dict(D, tgt=2, tgt_k=3, be_r=1, tr=7, tr_k=10)),
                               ("exit mode 2", {"InpExitMode": "2"}, dict(D, p1_r=1, p1_frac=0.5))):
            j = exitlab.Job("sweep", inp, ds, lab=form, sets=sets)
            j.run()
            ok(f"[{nm}] scan ran", j.error is None, getattr(j, "tb", ""))
            if j.error:
                continue
            R = j.result
            bench, _ = exitlab.Job("test", inp, ds).eval(lab=form, sets=sets)
            now = R["now"]
            ok(f"[{nm}] scan 'now' = the bench", abs(now["net"] - bench["total"]) < 1 and now["n"] == bench["all"]["n"] and abs(now["wr"] - bench["all"]["wr"]) < 0.05,
               f"scan {now['net']} / {now['n']} vs bench {bench['total']} / {bench['all']['n']}")
            rnd = random.Random(7)
            sample = [m for m in R["moves"] if m["group"] == "Exit Lab"][:6] + rnd.sample([m for m in R["moves"] if m["group"] != "Exit Lab"], 10)
            mism = []
            for m in sample:
                s, _ = exitlab.Job("test", inp, ds).eval(lab=dict(form, **m["lab"]), sets=dict(sets, **m["sets"]))
                if abs(s["total"] - m["r"]["net"]) >= 1 or s["all"]["n"] != m["r"]["n"]:
                    mism.append(f"{m['label']} {m['from']}->{m['to']}: scan {m['r']['net']}/{m['r']['n']} vs bench {s['total']}/{s['all']['n']}")
            ok(f"[{nm}] {len(sample)} moves: the scan's numbers = the bench after the pick", not mism, "; ".join(mism[:3]))
            groups = {m["group"] for m in R["moves"]}
            mode = str(dict(inp, **sets).get("InpExitMode"))
            if mode == "2":
                ok(f"[{nm}] no fallback moves in exit mode 2", not [m for m in R["moves"] if m["key"] in ("fb", "fb_buf", "fb_n")])
            if form.get("tgt", 0):
                ok(f"[{nm}] no fallback moves with a lab target", not [m for m in R["moves"] if m["key"] in ("fb", "fb_buf", "fb_n")])
            ok(f"[{nm}] no sweep / retest settings without their entry mode", not [m for m in R["moves"] if m["key"] in ("InpSweepPips", "InpRetestFrac")])
            ok(f"[{nm}] Exit Lab moves present (modes 1-2)", "Exit Lab" in groups)
            ok(f"[{nm}] choice settings carry names", all(not m["to"].replace(".", "").isdigit() for m in R["moves"] if m["key"] in ("tgt", "tr", "cx", "fb", "cx_when")),
               str([(m["key"], m["to"]) for m in R["moves"] if m["key"] in ("tgt", "tr")][:3]))
            ok(f"[{nm}] every move changes something", all(m["from"] != m["to"] for m in R["moves"]))
            bad = []
            for m in R["moves"]:
                c = dict(dict(inp, **sets), **m["sets"])
                if float(c["InpEmaSlow"]) <= float(c["InpEmaFast"]) or float(c["InpSessTo"]) <= float(c["InpSessFrom"]):
                    bad.append(m["label"] + " " + m["to"])
            ok(f"[{nm}] no move that cannot trade", not bad, ", ".join(bad[:4]))
            print(f"      {R['n']} moves in {R['seconds']} s, groups: {sorted(groups)}")
    # exit mode 0
    j = exitlab.Job("sweep", inp, "year", lab=dict(D), sets={"InpExitMode": "0"})
    j.run()
    R = j.result
    plain, _ = exitlab.Job("test", inp, "year").eval(sets={"InpExitMode": "0"})
    ok("[mode 0] no Exit Lab moves", not [m for m in R["moves"] if m["group"] == "Exit Lab"])
    ok("[mode 0] 'now' = the plain mode-0 run (nothing forced to mode 1)", abs(R["now"]["net"] - plain["total"]) < 1, f"{R['now']['net']} vs {plain['total']}")
    ok("[mode 0] v1.23 exit settings offered", any(m["group"] == "v1.23 exits" for m in R["moves"]))
    # a broken pool recovers
    pool = scan._pool()
    for p in list(pool._processes.values()):
        p.terminate()
    j = exitlab.Job("sweep", inp, "year", lab=dict(D), sets={})
    j.run()
    ok("a killed worker: the scan still finishes", j.error is None and j.result and j.result["now"], getattr(j, "tb", ""))
    fresh = scan._pool()
    ok("a killed worker: the next scan gets a fresh pool", fresh is not pool)
    j = exitlab.Job("sweep", inp, "year", lab=dict(D), sets={})
    j.run()
    ok("the fresh pool works", j.error is None and j.result["n"] > 100, f"{j.result and j.result['seconds']} s")
    print("\nALL CHECKS PASS" if not BAD else f"\n{len(BAD)} CHECK(S) FAILED: {BAD}")
    scan._drop_pool()
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
