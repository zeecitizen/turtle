"""run_rules.py - check every rule raises nothing on any trade (score() swallows exceptions), then api.report each one."""
import inspect, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
import rules as M  # noqa: E402
names = sys.argv[1:] or [n for n, f in inspect.getmembers(M, inspect.isfunction) if f.__module__ == M.__name__]
blind = [api._blind(t) for t in api.TRADES]
for n in names:
    f = getattr(M, n)
    for b in blind:
        f(b, api.A)                    # raises if buggy
for n in names:
    api.report(getattr(M, n), n)
