"""tickcheck.py (work_redteam) - recompute loss4b's tick features for a sample of trades with the tick arrays CUT at the breakout tick
(T <= t_dec): identical values = the features use nothing after the decision. Python replay = HYPOTHESIS."""
import importlib.util, json, os, random, sys
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
sys.path.insert(0, r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV")
import numpy as np

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

F1 = load(os.path.join(TIGHT, "work_loss4b", "tickfeats.py"), "tf1")
F2 = load(os.path.join(TIGHT, "work_loss4b", "tickfeats2.py"), "tf2")
TF = json.load(open(os.path.join(TIGHT, "work_loss4b", "tickfeats.json")))
T0, B0, A0 = F1.T, F1.B, F1.AS
trades = {}
for st in ("tight", "secure", "base"):
    for t in json.load(open(os.path.join(TIGHT, f"trades_{st}.json"), encoding="utf-8")):
        trades.setdefault(t["id"], t)
random.seed(7)
must = ["0408-075606-B", "0723-001905-S", "1019-171329-S", "1023-145031-B"]
sample = must + random.sample(sorted(trades), 76)
nbad, ncmp = 0, 0
for i in sample:
    t = trades[i]
    jb = int(np.searchsorted(T0, t["t_dec"], side="right"))         # keep ticks with T <= t_dec (the breakout tick is the decision tick)
    for M in (F1, F2):
        M.T, M.B, M.AS = T0[:jb], B0[:jb], A0[:jb]
    f = F1.one(t)
    f = F2.one(t, f)
    for k, v in f.items():
        ncmp += 1
        if not np.isclose(float(v), float(TF[i][k]), atol=1e-9):
            nbad += 1
            if nbad <= 10:
                print("DIFF", i, k, v, TF[i][k])
print(f"tick features recomputed on ticks cut at the breakout tick: {len(sample)} trades, {ncmp} values compared, {nbad} differ")
