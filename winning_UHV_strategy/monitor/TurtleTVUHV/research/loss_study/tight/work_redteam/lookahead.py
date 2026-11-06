"""lookahead.py (work_redteam) - MECHANICAL look-ahead test of all 25 proposed cures (+ control), and of the trade fields they read.
1. alignment: t1[kb] == floor(t_dec/60)*60, t1[k] < that minute (k = last CLOSED bar), ku <= k, for every trade of every stack.
2. truncation: every rule is called (directly, never through api_tight.score which swallows exceptions) twice per unique trade:
   with the full arrays, and with every bar array cut to [:k+1] (and its cached side tables cut the same way: spread_m1 'M' to [:k+1],
   sim sp1 to [:k+1], setups.npz to breakouts strictly before t_dec). A changed decision or an exception = the rule reads the future.
3. ATR causality: D['atr'] == sim._atr_adx(o1,h1,l1,c1) (trailing 14-bar SMA of true range).
4. outcome fields: the blinded trade dict has none of api_tight.OUTCOME; tickfeats.json keys contain no outcome names.
Python tick replay = HYPOTHESIS, NOT PROMOTED."""
import importlib.util, json, os, sys, time
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
for p in (TIGHT, ROOT):
    sys.path.insert(0, p)
import numpy as np
import api_tight
import sim

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

A4 = load(os.path.join(TIGHT, "work_loss4a", "rules.py"), "r4a")
B4 = load(os.path.join(TIGHT, "work_loss4b", "rules.py"), "r4b")
S30 = load(os.path.join(TIGHT, "work_secure30", "rules.py"), "r30")
RULES = [("loss4a", n, A4.compile_rule(s)) for n, s in A4.RULE_SRC.items()] + [("loss4b", f.__name__, f) for f in B4.RULES] + \
        [("secure30", f.__name__, f) for f in S30.RULES]
A = api_tight.A
t1 = A.t.astype(np.int64)

# ---------------- 1. alignment
bad = {"kb": 0, "k": 0, "ku": 0, "ku_eq_k": 0}
uniq = {}
for nm in ("tight", "secure", "base"):
    for t in api_tight.STACKS[nm]:
        m0 = int(t["t_dec"] // 60) * 60
        bad["kb"] += int(t1[t["kb"]] != m0)
        bad["k"] += int(not (t1[t["k"]] < m0 and t["k"] == t["kb"] - 1))
        bad["ku"] += int(t["ku"] > t["k"])
        bad["ku_eq_k"] += int(t["ku"] == t["k"])
        uniq.setdefault(t["id"], t)
print("1. alignment over all stack trades:", bad, "| unique trade ids:", len(uniq), flush=True)

# ---------------- 3. ATR causality
D = sim.data("year1")
o1, h1, l1, c1 = (np.asarray(D[k], dtype=float) for k in ("o1", "h1", "l1", "c1"))
atr_re, adx_re = sim._atr_adx(o1, h1, l1, c1)
print("3. ATR is the trailing 14-bar SMA of TR on the same M1 bars:", bool(np.allclose(atr_re, A.atr)), "| ADX recomputed equal:", bool(np.allclose(adx_re, A.adx)), flush=True)

# ---------------- 4. outcome fields
OUT = set(api_tight.OUTCOME)
leak = [k for t in list(uniq.values())[:50] for k in api_tight._blind(t) if k in OUT]
TF = json.load(open(os.path.join(TIGHT, "work_loss4b", "tickfeats.json")))
tfkeys = set(k for v in list(TF.values())[:200] for k in v)
sus = [k for k in tfkeys if any(w in k.lower() for w in ("win", "pnl", "fill", "stop", "exit", "out", "best", "worst"))]
print("4. outcome keys in blinded trade:", leak, "| tickfeats keys:", sorted(tfkeys), "| suspicious:", sus, flush=True)

# ---------------- 2. truncation
class TA:
    __slots__ = ("t", "o", "h", "l", "c", "v", "atr", "adx")
def trunc(k):
    x = TA()
    for f in TA.__slots__:
        setattr(x, f, getattr(A, f)[:k + 1])
    return x

M_full = np.load(os.path.join(TIGHT, "work_loss4a", "spread_m1.npz"))["med"]
Z_full = dict(np.load(os.path.join(TIGHT, "work_loss4a", "setups.npz")))
sp1_full = np.asarray(D["sp1"], dtype=float)
# make sure the cached side tables are the full ones first
for src, name, r in RULES:
    if "M" in getattr(r, "__dict__", {}) or name in ("rule_spread_wide", "rule_spread_not_narrow", "rule_spread_upper_mode"):
        r.__dict__["M"] = M_full
    if name == "rule_rebreak_same_level":
        r.__dict__["Z"] = Z_full
    if name == "rule_wide_spread_now":
        r.sp1 = sp1_full

ids = sorted(uniq)
res = {}
t0 = time.time()
for src, name, r in RULES:
    diff = exc_full = exc_tr = 0; ex = []
    for i in ids:
        t = api_tight._blind(uniq[i]); k = t["k"]
        # full
        if name in ("rule_spread_wide", "rule_spread_not_narrow", "rule_spread_upper_mode"):
            r.__dict__["M"] = M_full
        if name == "rule_rebreak_same_level":
            r.__dict__["Z"] = Z_full
        if name == "rule_wide_spread_now":
            r.sp1 = sp1_full
        try:
            a = bool(r(t, A))
        except Exception:
            a = None; exc_full += 1
        # truncated
        if name in ("rule_spread_wide", "rule_spread_not_narrow", "rule_spread_upper_mode"):
            r.__dict__["M"] = M_full[:k + 1]
        if name == "rule_rebreak_same_level":
            m = Z_full["t"] < t["t_dec"]
            r.__dict__["Z"] = {kk: vv[m] for kk, vv in Z_full.items()}
        if name == "rule_wide_spread_now":
            r.sp1 = sp1_full[:k + 1]
        try:
            b = bool(r(t, trunc(k)))
        except Exception as e:
            b = None; exc_tr += 1
            if len(ex) < 3: ex.append(f"{i}: {type(e).__name__} {e}")
        if a != b:
            diff += 1
            if len(ex) < 3: ex.append(f"{i}: full {a} vs truncated {b}")
    res[f"{src}:{name}"] = dict(diff=diff, exc_full=exc_full, exc_trunc=exc_tr, examples=ex)
    print(f"2. {src}:{name:32s} changed decisions {diff:5d}  exceptions full {exc_full} / truncated {exc_tr}  {ex[:2]}", flush=True)
# restore
for src, name, r in RULES:
    if name in ("rule_spread_wide", "rule_spread_not_narrow", "rule_spread_upper_mode"):
        r.__dict__["M"] = M_full
print(f"truncation test done in {time.time()-t0:.0f}s over {len(ids)} unique trades x {len(RULES)} rules")
json.dump(res, open(os.path.join(HERE, "lookahead.json"), "w"), indent=1)
