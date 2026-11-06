"""run.py - score rules from rules.py with the official harness. usage: py run.py rule_a rule_b ...  (no args = all rule_*)"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402
names = sys.argv[1:] or [n for n in dir(rules) if n.startswith("rule_")]
for n in names:
    api.report(getattr(rules, n), n)
