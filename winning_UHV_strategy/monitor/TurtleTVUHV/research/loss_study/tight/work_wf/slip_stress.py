"""slip_stress.py (work_wf) - execution stress on Zee's zone: InpUhvFixTp 0.1 -> 0.15..1.0 pips means the price must move that much in favour
of the replay's fill before the ~21-pip stop - roughly what 0.05..0.9 pips of extra entry slippage would demand. Counts LOSSES (fragility);
the net is not comparable (bigger wins)."""
import os

from common import run, summ, SPLIT, OUT

lines = []
for tp in ("0.1", "0.15", "0.2", "0.3", "0.5", "1.0"):
    for lat in ("0.3", "0.6"):
        r = run({"InpUhvFixTp": tp, "InpUhvLatency": lat})
        a, m, j = summ(r), summ(r, hi=SPLIT), summ(r, lo=SPLIT)
        s = f"FixTp {tp:>4s} pip, latency {lat}: {a['n']} tr {a['L']} L  WR {a['wr']:.2f}%  net {a['net']:+.2f}  (Mar-Jun {m['L']}/{m['n']}, Jul-Nov {j['L']}/{j['n']})"
        print(s, flush=True); lines.append(s)
open(os.path.join(OUT, "slip_stress.txt"), "w").write("\n".join(lines))
