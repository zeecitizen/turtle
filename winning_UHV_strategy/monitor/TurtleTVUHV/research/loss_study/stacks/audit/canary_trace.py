"""canary_trace.py - look-ahead audit, READ-TRACE: every array uhv_filters.skip() / secure() can read is wrapped so each read logs the
highest bar index it touched. For EVERY setup the engine sends to the filters (both entry paths: instant InpUhvEntry=1 and candle-close
InpUhvEntry=0) and EVERY scanner grid value of every loss setting (+ companions), the reads must stay within what is known at the decision:
  h l c v stk end5 atr : index <= k            (k = the last closed candle before the entry)
  lastH lastL          : index <= k - 1        (lastH[i] includes a pivot AT i, which needs bar i+1 to be confirmed)
plus no negative index (wrap-around to the END of the data) and no empty slice. A positive control (a deliberately leaky _swings that reads
lastH[k]) must be caught through the same path, or the canary is blind.  Output: out_trace.json"""
import time, json, os
from _common import *          # noqa: F401,F403  (sets sys.path / cwd)
import numpy as np
import sim, uhv_filters

LIM = {"h": 0, "l": 0, "c": 0, "v": 0, "t": 0, "stk": 0, "end5": 0, "atr": 0, "lastH": -1, "lastL": -1}
MX, FL = {}, []


def note(nm, key, n):
    if isinstance(key, (int, np.integer)):
        i = int(key)
        if i < 0:
            FL.append((nm, "negative index", i)); i += n
        MX[nm] = max(MX.get(nm, -10**9), i)
    elif isinstance(key, slice):
        if key.start is not None and key.start < 0:
            FL.append((nm, "negative slice start", key.start))
        a, b, st = key.indices(n)
        if b <= a:
            FL.append((nm, "empty slice", (key.start, key.stop)))
        else:
            MX[nm] = max(MX.get(nm, -10**9), b - 1)
    else:
        arr = np.asarray(key)
        if arr.dtype == bool:
            FL.append((nm, "boolean mask", None)); MX[nm] = max(MX.get(nm, -10**9), n - 1)
        elif arr.size:
            if (arr < 0).any():
                FL.append((nm, "negative fancy index", int(arr.min())))
            MX[nm] = max(MX.get(nm, -10**9), int(arr.max()))


class Tr(np.ndarray):
    def __getitem__(self, key):
        note(self._nm, key, len(self))
        return np.ndarray.__getitem__(self.view(np.ndarray), key)


def wrap(a, nm):
    x = np.asarray(a).view(Tr); x._nm = nm
    return x


def traced_D():
    D = sim.data("year1")
    Dw = dict(D); Dw["atr"] = wrap(D["atr"], "atr")
    clear_caches()
    C = uhv_filters._prep(Dw)
    for nm in ("h", "l", "c", "v", "t", "stk", "end5", "lastH", "lastL"):
        C[nm] = wrap(C[nm], nm)
    assert C["key"] == id(Dw)
    return Dw


def run(calls, secs, cfgs, scfgs, label):
    Dw = traced_D()
    out = {}
    nviol = 0
    for main, d in cfgs:
        r = out.setdefault(main, {"configs": 0, "calls": 0, "skips": 0, "max_off": {}, "violations": 0, "flags": {}})
        r["configs"] += 1
        for a in calls:
            MX.clear(); FL.clear()
            why = uhv_filters.skip(fv, d, Dw, a["side"], a["k"], a["px"], a["atr_k"], a["extreme"], level=a["level"], ku=a["ku"], ts=a["ts"],
                                   uhv_v=a["uhv_v"], brk_ticks=a["brk_ticks"], brk_px=a["brk_px"])
            r["calls"] += 1; r["skips"] += why is not None
            k = a["k"]
            for nm, i in MX.items():
                off = i - k
                r["max_off"][nm] = max(r["max_off"].get(nm, -10**9), off)
                if off > LIM[nm]:
                    r["violations"] += 1; nviol += 1
            for f in FL:
                r["flags"][f[1]] = r["flags"].get(f[1], 0) + 1
    r = out.setdefault("RiskMgr secure()", {"configs": 0, "calls": 0, "skips": 0, "max_off": {}, "violations": 0, "flags": {}})
    for d in scfgs:
        r["configs"] += 1
        for side, k in secs:
            MX.clear(); FL.clear()
            ok = uhv_filters.secure(fv, d, Dw, int(side), int(k))
            r["calls"] += 1; r["skips"] += (not ok)
            for nm, i in MX.items():
                off = i - int(k)
                r["max_off"][nm] = max(r["max_off"].get(nm, -10**9), off)
                if off > LIM[nm]:
                    r["violations"] += 1; nviol += 1
            for f in FL:
                r["flags"][f[1]] = r["flags"].get(f[1], 0) + 1
    print(f"[{label}] total violations: {nviol}")
    return out, nviol


if __name__ == "__main__":
    t0 = time.time()
    cfgs, scfgs = skip_configs(), secure_configs()
    print("skip configs:", len(cfgs), " secure configs:", len(scfgs))
    res = {"files_sha1": {}, "paths": {}}
    import hashlib
    for f in ("uhv_filters.py", "uhv_engine.py"):
        res["files_sha1"][f] = hashlib.sha1(open(os.path.join(ROOT, f), "rb").read()).hexdigest()
    for label, extra in (("instant (InpUhvEntry=1, the base)", {}), ("candle close (InpUhvEntry=0)", {"InpUhvEntry": "0"})):
        calls, secs, cnt = record_calls(extra)
        ks = [a["k"] for a in calls]
        print(f"[{label}] calls {len(calls)}, min k {min(ks)}, {time.time() - t0:.0f}s")
        out, nv = run(calls, secs, cfgs, scfgs, label)
        res["paths"][label] = {"calls": len(calls), "min_k": int(min(ks)), "violations": nv, "per_setting": out}
        for main, r in out.items():
            print(f"   {main:22s} cfg {r['configs']:3d} skips {r['skips']:8d}  max(index-k) {r['max_off']}  viol {r['violations']}  flags {r['flags']}")
    # ---- positive control: a leaky _swings (reads lastH[k] = a pivot AT k, unconfirmed) must be caught by the same path
    real = uhv_filters._swings

    def leaky(last, k, n):
        out, j = [], (last[k] if k >= 0 else -1)
        while j >= 0 and len(out) < n:
            out.append(j); j = last[j - 1] if j >= 1 else -1
        return out[::-1]
    uhv_filters._swings = leaky
    try:
        calls, secs, cnt = record_calls({})
        pc = [c for c in cfgs if c[0] in ("InpUhvStruct", "InpUhvSRAhead")][:6]
        out, nv = run(calls[:3000], [], pc, [], "positive control: leaky _swings")
        res["positive_control_leaky_swings"] = {"violations": nv, "per_setting": out}
    finally:
        uhv_filters._swings = real
    print("positive control caught:", nv > 0)
    res["secs"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(HERE, "out_trace.json"), "w"), indent=1, default=str)
    print("done in %.0fs" % (time.time() - t0))
