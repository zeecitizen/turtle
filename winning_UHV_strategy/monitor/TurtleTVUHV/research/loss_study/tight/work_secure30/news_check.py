"""news_check.py - the news-clock windows one by one, raw and against both random-entry nulls (HYPOTHESIS ONLY)."""
import datetime as dt
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402

N1 = pickle.load(open(os.path.join(HERE, "emp_null_K60.pkl"), "rb"))
N2 = pickle.load(open(os.path.join(HERE, "emp_null_days_K40.pkl"), "rb"))
WIN = {"top :56-:03": lambda m: m >= 56 or m <= 3, "half :25-:30": lambda m: 25 <= m <= 30, "rest": lambda m: not (m >= 56 or m <= 3 or 25 <= m <= 30),
       ":00-:03": lambda m: m <= 3, ":56-:59": lambda m: m >= 56, ":10-:20": lambda m: 10 <= m <= 20, ":40-:50": lambda m: 40 <= m <= 50}
for st in ("secure", "base"):
    p1 = {r[0]: r[4] / max(r[5], 1) for r in N1[st]}
    p2 = {r[0]: r[4] / max(r[5], 1) for r in N2[st]}
    for part, f in (("tr", lambda t: t["t_dec"] < AT.SPLIT), ("te", lambda t: t["t_dec"] >= AT.SPLIT)):
        T = [t for t in AT.STACKS[st] if f(t)]
        out = []
        for name, w in WIN.items():
            S = [t for t in T if w(dt.datetime.fromtimestamp(t["t_dec"], dt.timezone.utc).minute)]
            L = sum(1 for t in S if not t["win"])
            e1 = sum(p1[t["id"]] for t in S); e2 = sum(p2[t["id"]] for t in S)
            out.append(f"{name}: {L}/{len(S)} {100 * L / max(len(S), 1):.1f}% oe90 {L / max(e1, 1e-9):.2f} oeDays {L / max(e2, 1e-9):.2f} nullDays {100 * e2 / max(len(S), 1):.2f}%")
        print(st, part, " | ".join(out))
