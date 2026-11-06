"""overlap.py - what each rule adds outside other rules (the daily-close window 20:45-21:15 first)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
import rules as M  # noqa: E402
BL = [(api._blind(t), t) for t in api.TRADES]
BASE = {True: sum(1 for t in api.TRADES if t["t_in"] < api.SPLIT and not t["win"]) / sum(1 for t in api.TRADES if t["t_in"] < api.SPLIT),
        False: sum(1 for t in api.TRADES if t["t_in"] >= api.SPLIT and not t["win"]) / sum(1 for t in api.TRADES if t["t_in"] >= api.SPLIT)}
def close_win(t, A):
    s = t["t_in"] % 86400
    return 74700 <= s <= 76500
def stat(sel, name):
    out = []
    tot = [0, 0]
    for half in (True, False):
        xs = [t for b, t in BL if (t["t_in"] < api.SPLIT) == half and sel(b)]
        n = len(xs); L = sum(not t["win"] for t in xs); tot[0] += n; tot[1] += L
        out.append(f"{'tr' if half else 'te'} {L:3d}L/{n - L:4d}W x{(L / max(n, 1)) / BASE[half]:5.2f}")
    print(f"{name:52s} all {tot[1]:3d}L/{tot[0] - tot[1]:4d}W  " + "   ".join(out))
if __name__ == "__main__":
    A = api.A
    for n in sys.argv[1:]:
        f = getattr(M, n)
        stat(lambda b, f=f: f(b, A), n)
        stat(lambda b, f=f: f(b, A) and not close_win(b, A), "   " + n + " outside 20:45-21:15")
