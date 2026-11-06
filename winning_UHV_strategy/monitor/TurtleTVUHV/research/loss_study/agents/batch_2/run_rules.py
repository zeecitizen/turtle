import sys, inspect
sys.path.insert(0, '.'); sys.path.insert(0, 'agents/batch_2')
import api, rules
names = sys.argv[1:] or [n for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith('rule_')]
for n in names:
    api.report(getattr(rules, n), n)
