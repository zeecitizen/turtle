"""edges.py (work_wf) - the losses just outside Zee's box (engine): which trades enter at ER min 0.28 / ER max 0.38, and their half."""
import datetime as dt
import os

from common import ZEE, OUT
import uhv_engine as U

lines = []
for lab, o in (("ER min 0.28", {"InpUhvSafeErMin": "0.28"}), ("ER max 0.38", {"InpUhvSafeErMax": "0.38"}), ("humps 2-4", {"InpUhvSafeHumpsMax": "4"}),
               ("humps 1-3", {"InpUhvSafeHumpsMin": "1"})):
    inp = dict(ZEE); inp.update(o)
    r, _, _ = U.simulate(inp); r = r[r[:, 10] == 0]
    for x in r[r[:, 6] <= 0]:
        s = f"{lab}: LOSS {dt.datetime.fromtimestamp(x[1], dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC side {int(x[0]):+d} ${x[6]:+.2f}"
        print(s, flush=True); lines.append(s)
open(os.path.join(OUT, "edges.txt"), "w").write("\n".join(lines))
