"""losslab_check.py - the loss cutter, checked against its own promises (Zee 2026-10-21: "proof-read, reverify and fix all bugs in your
implementation of this loss research lab").

   py monitor/saad_view/losslab_check.py            (both data sets: the 2026 ticks and the 4 years)

1. loss_stats / day_stats on hand-made trade lists (every edge: no losses, no wins, no trades, the 5% tail)
2. the loss scan runs; its "now" = the bench (net, trades) and its loss numbers = loss_stats of the bench's own trades
3. a sample of moves (every data move + random others): the scan's loss numbers = the bench after picking the move
4. data moves: each changes something, can trade, can act, and no two moves change the same thing
5. the autopsy: the groups add up to every trade, the percentiles are in order, the facts carry no NaN / None
6. the page's ranking (lossCuts in static/exitlab_research.js, run by node on this scan): every suggestion keeps the limits it promises,
   the order is by score, and the page's HTML carries no "undefined" / "NaN"
7. the plain scan (no loss focus) has no autopsy and no data moves; the loss scan is a superset of its moves"""
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

BAD = []


def ok(name, cond, detail=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        BAD.append(name)


def close(a, b, tol=0.6):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def unit():
    import numpy as np
    import losslab as LL
    s = LL.loss_stats([100, 100, -300])
    ok("loss_stats: 2 wins 1 loss", close(s["wr"], 66.67, 0.01) and s["avg_win"] == 100 and s["avg_loss"] == -300 and close(s["be"], 75, 0.01)
       and close(s["margin"], -8.33, 0.01) and close(s["lpt"], 100, 0.01) and close(s["tail"], -33.3, 0.1) and s["worst"] == -300 and s["net"] == -100, str(s))
    s = LL.loss_stats([50, 60])
    ok("loss_stats: no losses -> break-even 0, margin = WR", s["be"] == 0 and s["margin"] == 100 and s["avg_loss"] == 0 and s["lpt"] == 0, str(s))
    s = LL.loss_stats([-50, -10])
    ok("loss_stats: no wins -> break-even 100", s["be"] == 100 and s["margin"] == -100 and s["wr"] == 0, str(s))
    s = LL.loss_stats([])
    ok("loss_stats: no trades", s["n"] == 0 and s["be"] is None and s["margin"] is None, str(s))
    s = LL.loss_stats([0.0, 10.0, 10.0])
    ok("loss_stats: a $0 trade counts as a loss (as the EA's win rate)", close(s["wr"], 66.67, 0.01) and s["avg_loss"] == 0, str(s))
    p = np.array([10.0] * 95 + [-1.0, -2, -3, -4, -100])
    s = LL.loss_stats(p)
    ok("loss_stats: tail = the worst 5% (5 of 100)", close(s["tail"], -22.0, 0.01), str(s))
    real = np.zeros((4, 20))
    real[:, 4] = [86400 * 10 + 5, 86400 * 10 + 99, 86400 * 11 + 1, 86400 * 12]
    real[:, 6] = [100, -300, 50, -10]
    d = LL.day_stats(real)
    ok("day_stats", d["days"] == 3 and close(d["green"], 33.3, 0.1) and d["worst"] == -200 and d["median"] == -10, str(d))


def run_scan(inp, ds, focus):
    import exitlab
    j = exitlab.Job("sweep", inp, ds, lab={}, sets={}, focus=focus)
    j.run()
    return j


def check_ds(inp, ds):
    import numpy as np
    import exitlab
    import losslab as LL
    import scan
    j = run_scan(inp, ds, "loss")
    ok(f"[{ds}] loss scan ran", j.error is None, getattr(j, "tb", ""))
    if j.error:
        return None
    R = j.result
    ok(f"[{ds}] it carries the autopsy and says it is a loss scan", R.get("focus") == "loss" and isinstance(R.get("autopsy"), dict))
    # the bench, independently: the Exit Lab test of the same settings
    lab = {k: v for k, v in (exitlab.sim_full.lab_from_inputs(inp) or {}).items() if k != "pess"}
    form = dict(exitlab.DEFAULT, **lab)
    bench, real = exitlab.Job("test", inp, ds).eval(lab=form, sets={})
    now = R["now"]
    ok(f"[{ds}] 'now' = the bench", abs(now["net"] - bench["total"]) < 1 and now["n"] == bench["all"]["n"], f"{now['net']}/{now['n']} vs {bench['total']}/{bench['all']['n']}")
    L = LL.loss_stats(real[:, 6])
    ok(f"[{ds}] the bench's loss numbers = loss_stats of its trades", all(close(now["L"][k], L[k]) for k in ("wr", "avg_win", "avg_loss", "worst", "tail", "lpt", "be", "margin")),
       f"{now['L']} vs {L}")
    a0, a1, b0, b1 = j.window
    t = real[:, 1]
    halves = [LL.loss_stats(real[(t >= a0) & (t < a1), 6]), LL.loss_stats(real[(t >= b0) & (t < b1), 6])]
    ok(f"[{ds}] the halves' loss numbers", all(close(now["Lh"][h]["margin"], halves[h]["margin"]) and now["Lh"][h]["n"] == halves[h]["n"] for h in (0, 1)))
    inside = int(((t >= a0) & (t < a1)).sum() + ((t >= b0) & (t < b1)).sum())       # the data can start before the first half (warm-up days)
    ok(f"[{ds}] the halves add up to the trades inside them", now["Lh"][0]["n"] + now["Lh"][1]["n"] == inside, f"{now['Lh'][0]['n']} + {now['Lh'][1]['n']} vs {inside}")
    # the moves: the scan's numbers = the bench after the pick
    data = [m for m in R["moves"] if m.get("data")]
    rnd = random.Random(11)
    sample = data + rnd.sample([m for m in R["moves"] if not m.get("data")], 8)
    mism = []
    for m in sample:
        s, rl = exitlab.Job("test", inp, ds).eval(lab=dict(form, **m["lab"]), sets=dict(m["sets"]))
        Lm = LL.loss_stats(rl[:, 6])
        if abs(s["total"] - m["r"]["net"]) >= 1 or s["all"]["n"] != m["r"]["n"] or not all(close(m["r"]["L"][k], Lm[k]) for k in ("avg_loss", "worst", "tail", "be", "margin")):
            mism.append(f"{m['label']} {m['from']}->{m['to']}: scan {m['r']['net']}/{m['r']['n']}/{m['r']['L']['avg_loss']} vs bench {s['total']}/{s['all']['n']}/{Lm['avg_loss']}")
    ok(f"[{ds}] {len(sample)} moves ({len(data)} from the autopsy): the scan's loss numbers = the bench after the pick", not mism, "; ".join(mism[:3]))
    # data moves: valid, acting, no twins
    base_in = dict(inp, **scan.lab_sets(form))
    sigs = [scan._sig(m["sets"], m["lab"]) for m in R["moves"]]
    ok(f"[{ds}] no two moves change the same thing", len(sigs) == len(set(sigs)), f"{len(sigs) - len(set(sigs))} twins")
    bad = [m["label"] for m in data if not (m["sets"] or m["lab"]) or m["from"] == m["to"]]
    ok(f"[{ds}] every data move changes something", not bad, str(bad[:3]))
    bad = [m["label"] for m in data if m["sets"] and not scan._valid(dict(base_in, **m["sets"]))]
    ok(f"[{ds}] no data move that cannot trade", not bad, str(bad[:3]))
    bad = [m["label"] for m in data if any(not scan._relevant(k, dict(base_in, **m["sets"])) for k in m["sets"])]
    ok(f"[{ds}] every data move can act", not bad, str(bad[:3]))
    bad = [m["label"] for m in data if m["lab"] and str(base_in.get("InpExitMode")) not in ("1", "2")]
    ok(f"[{ds}] Exit Lab data moves only in exit modes 1-2", not bad, str(bad[:3]))
    ok(f"[{ds}] every data move says why", all(m.get("why") for m in data))
    # the autopsy
    A = R["autopsy"]
    for dim in ("side", "hour", "weekday", "candle"):
        rows = [c for c in A["clusters"] if c["dim"] == dim]
        ok(f"[{ds}] autopsy: the {dim} groups add up to every trade", sum(c["n"] for c in rows) == now["n"], f"{sum(c['n'] for c in rows)} vs {now['n']}")
    for dim in ("stop width", "volatility"):
        rows = [c for c in A["clusters"] if c["dim"] == dim]
        ok(f"[{ds}] autopsy: the {dim} groups add up (or there are none)", not rows or sum(c["n"] for c in rows) == now["n"])
    txt = json.dumps(A)
    ok(f"[{ds}] autopsy: no NaN / None / inf in the text", not any(x in txt for x in ("NaN", "None", "nan%", "Infinity")))
    bad = [c for c in A["clusters"] if c["bad"] and not (15 <= c["n"] <= 0.5 * now["n"])]
    ok(f"[{ds}] autopsy: a flagged group is a minority with enough trades", not bad, str(bad[:2]))
    mae = real[real[:, 6] > 0, 16]
    if len(mae) >= 20:
        q = [float(np.percentile(mae, x)) for x in (90, 95, 98)]
        ok(f"[{ds}] autopsy: the MAE percentiles in the fact match the trades", all(f"${max(0.5, -(-v // 0.5) * 0.5):g}" in A["facts"][1]["text"] for v in q),
           A["facts"][1]["text"][:160])
    return R


def check_page(R, ds):
    """the page's own ranking, run by node on this scan"""
    tmp = Path(tempfile.mkdtemp())
    (tmp / "scan.json").write_text(json.dumps(R), encoding="utf-8")
    harness = r"""
const fs = require('fs');
global.localStorage = { getItem: () => null, setItem: () => {} };
global.document = { addEventListener: () => {} };
global.CUR = {}; global.LABS = { form: {}, spec: { default: {} } }; global.TAB = { tt: 'lab' };
global.money = (v) => (v < 0 ? '-' : '') + '$' + Math.round(Math.abs(v)).toLocaleString('en-US');
global.esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
global.cls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
global.table = (h, rows) => '<table>' + h.join('|') + rows.join('') + '</table>';
eval(fs.readFileSync(process.argv[2], 'utf8') + '\nglobal.lossCuts = lossCuts; global.lossTips = lossTips; global.RS = RS;');
const W = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')); W._id = 'x';
const out = [];
for (const [tol, keep] of [[1.5, 85], [0.5, 95], [5, 50], [10, 50]]) {
  RS.loss = true; RS.lossTol = tol; RS.lossKeep = keep; RS.lossDrop = 13;
  const { list, over } = lossCuts(W);
  const html = lossTips(W, false);
  out.push({ tol, keep, n: list.length, over, html_bad: (html.match(/undefined|NaN|\[object/g) || []).length,
    rows: list.map((m) => ({ s: m.lscore, wr: m.r.L.wr, n: m.r.n, avg: m.lc.avg, tail: m.lc.tail, lpt: m.lc.lpt, worst: m.lc.worst, dm: m.dm, train: m.r.train, test: m.r.test })) });
}
console.log(JSON.stringify(out));
"""
    (tmp / "h.js").write_text(harness, encoding="utf-8")
    p = subprocess.run(["node", str(tmp / "h.js"), str(HERE / "static" / "exitlab_research.js"), str(tmp / "scan.json")], capture_output=True, text=True, encoding="utf-8")
    ok(f"[{ds}] page: lossCuts / lossTips run in node", p.returncode == 0, p.stderr[-600:])
    if p.returncode:
        return
    res = json.loads(p.stdout)
    now = R["now"]
    for r in res:
        rows = r["rows"]
        tag = f"[{ds}] page tol {r['tol']} keep {r['keep']}%"
        ok(f"{tag}: every suggestion keeps the win rate within the limit", all(x["wr"] >= now["L"]["wr"] - r["tol"] - 1e-9 for x in rows))
        ok(f"{tag}: every suggestion keeps the trades", all(x["n"] >= r["keep"] / 100 * now["n"] - 1e-9 for x in rows))
        ok(f"{tag}: every suggestion cuts a loss number and makes none bigger",
           all((x["avg"] >= 0.02 or x["tail"] >= 0.03 or x["lpt"] >= 0.02 or x["worst"] >= 0.05) and x["avg"] > -0.05 and x["tail"] > -0.05 and x["dm"] >= -0.3 for x in rows))
        ok(f"{tag}: no half that made money turns into a loss", all(not (now["train"] > 0 and x["train"] <= 0) and not (now["test"] > 0 and x["test"] <= 0) for x in rows))
        ok(f"{tag}: ranked by score", all(rows[i]["s"] >= rows[i + 1]["s"] for i in range(len(rows) - 1)))
        ok(f"{tag}: the page's HTML has no undefined / NaN", r["html_bad"] == 0, str(r["html_bad"]))
        print(f"      {tag}: {r['n']} suggestions, left out {r['over']}")


def main():
    import server
    import scan
    unit()
    name = (HERE / "settings" / "primary.txt").read_text(encoding="utf-8").strip() if (HERE / "settings" / "primary.txt").exists() else ""
    saved = json.loads((HERE / "settings" / "saved" / f"{name}.json").read_text(encoding="utf-8"))["inputs"] if name else {}
    for label, sets in (("your primary save", saved), ("v1.27 defaults", {})):
        inp = server.full_inputs(sets)
        for ds in ("year", "m15"):
            print(f"--- {label} · {ds}")
            R = check_ds(inp, ds)
            if R:
                check_page(R, ds)
                if ds == "year":
                    P = run_scan(inp, ds, None).result
                    ok(f"[{ds}] the plain scan has no autopsy and no data moves", P.get("autopsy") is None and not any(m.get("data") for m in P["moves"]))
                    lsig = {scan._sig(m["sets"], m["lab"]) for m in R["moves"]}
                    ok(f"[{ds}] the loss scan holds every move of the plain scan", all(scan._sig(m["sets"], m["lab"]) in lsig for m in P["moves"]))
    scan._drop_pool()
    print("\nALL CHECKS PASS" if not BAD else f"\n{len(BAD)} CHECK(S) FAILED: {BAD}")
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
