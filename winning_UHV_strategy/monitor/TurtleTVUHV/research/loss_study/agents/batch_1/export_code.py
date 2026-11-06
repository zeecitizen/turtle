"""export_code.py - turn every rule in rules.py into a standalone `def rule(t, A):` string (docstring stripped), check that
each string runs on its own (namespace = np + math only) and gives the same answer as the original on every blind trade.
Writes codes.json."""
import ast, inspect, json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, STUDY); sys.path.insert(0, HERE)
import api, rules as R
BLIND = [api._blind(t) for t in api.TRADES]
codes = {}
for f in R.ALL:
    src = inspect.getsource(f)
    tree = ast.parse(src)
    fn = tree.body[0]
    if isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], 'value', None), ast.Constant):
        fn.body = fn.body[1:]
    fn.name = 'rule'
    code = ast.unparse(tree)
    ns = {'np': np, 'math': math}
    exec(code, ns)
    g = ns['rule']
    bad = sum(1 for t in BLIND if bool(g(t, api.A)) != bool(f(t, api.A)))
    codes[f.__name__] = code
    print(f"{f.__name__:28s} standalone ok, mismatches {bad}")
json.dump(codes, open(os.path.join(HERE, 'codes.json'), 'w', encoding='utf-8'), indent=1)
