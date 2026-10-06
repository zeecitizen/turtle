"""Confirmation: mode 0 vs mode 1 on two INDEPENDENT earlier windows.

The 8-17 Sep result was one window and 74 trades. Before recommending that a LIVE EA's
trend engine be switched, the same comparison has to hold on periods it was not observed
on. The OANDA table starts 2026.08.05, so two clean windows exist before September.
"""
import sys

sys.path.insert(0, 'monitor/strategy_lab')
sys.stdout.reconfigure(encoding='utf-8')

import diamond_lab as D
from diamond_lab import evaluate, report

WINDOWS = [
    ("AUG-A", "2026.08.10", "2026.08.19"),
    ("AUG-B", "2026.08.20", "2026.08.29"),
]

res = []
for label, frm, to in WINDOWS:
    D.FULL = (frm, to)
    res.append(evaluate("%s mode0 shipped" % label, {"InpTrendMode": 0}, halves=False))
    res.append(evaluate("%s mode1 CAMEL" % label,
                        {"InpTrendMode": 1, "InpHighTest": 1}, halves=False))

report("Diamond trend reader — two INDEPENDENT August windows", res)
