"""latency_flips.py (work_wf) - which trades of Zee's zone turn into losses when only InpUhvLatency changes (engine rows)."""
import datetime as dt
import os

import numpy as np


from common import ZEE, OUT, run
import uhv_engine as U

PIP = 1e-4
lines = []


def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)


def rows(over):
    inp = dict(ZEE); inp.update({k: str(v) for k, v in over.items()})
    r, _, _ = U.simulate(inp)
    return r[r[:, 10] == 0]


for lat in ("0.0", "0.1", "0.2", "0.6", "1.0"):
    R = rows({"InpUhvLatency": lat})
    for x in R[R[:, 6] <= 0]:
        P(f"latency {lat}: LOSS {dt.datetime.fromtimestamp(x[1], dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC side {int(x[0]):+d} fill {x[2]:.5f} stop {x[3]:.5f} "
          f"({abs(x[2]-x[3])/PIP:.1f} p) exit {x[5]:.5f} after {x[4]-x[1]:.0f} s  ${x[6]:+.2f}  best {x[15]:.3f} R  worst {x[16]:.2f} R")
# the same trades at the default latency
R = rows({})
P("default 0.3 s: smallest results " + ", ".join(f"{dt.datetime.fromtimestamp(x[1], dt.timezone.utc):%m-%d %H:%M:%S} ${x[6]:+.2f} (held {x[4]-x[1]:.0f} s, worst {x[16]:.2f} R)" for x in R[np.argsort(R[:, 6])][:5]))
hold = R[:, 4] - R[:, 1]
P(f"default 0.3 s: holding time median {np.median(hold):.1f} s, 90th pct {np.percentile(hold, 90):.0f} s, max {hold.max():.0f} s; "
  f"deepest dip before the target: median {np.median(R[:,16]):.3f} R, worst {R[:,16].min():.2f} R; trades that dipped below -0.25 R: {int((R[:,16] < -0.25).sum())}")
open(os.path.join(OUT, "latency_flips.txt"), "w").write("\n".join(lines))
