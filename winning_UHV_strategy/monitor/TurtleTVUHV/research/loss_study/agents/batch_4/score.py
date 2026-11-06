"""score.py - run api.report on every rule in rules.py (or the names given). Run from research/loss_study."""
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

names = sys.argv[1:] or [n for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith("r_")]
for n in names:
    api.report(getattr(rules, n), n)
