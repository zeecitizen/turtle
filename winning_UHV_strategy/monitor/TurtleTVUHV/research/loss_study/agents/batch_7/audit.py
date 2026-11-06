"""audit.py - batch 7 look-ahead audit: every rule is re-run on EVERY trade with all per-bar arrays truncated to bars <= k (and humps
to known_at_bar <= k). Any read of bar k+1 or later raises (truncated array) or changes the decision; both are counted."""
import sys
sys.path.insert(0, '../..')
import api  # noqa: E402
from final_rules import RULES, load  # noqa: E402

A = api.A
NAMES = ['t', 'o', 'h', 'l', 'c', 'v', 'atr', 'adx', 'camEff', 'camStk', 'camT', 'camHV', 'camLV', 'camL0V']


class Cut:
    pass


fns = {rid: load(code) for rid, code in RULES.items()}
bad = {rid: 0 for rid in RULES}
for t in api.TRADES:
    k = t['k']; P = Cut(); P.PIP = A.PIP
    for nm in NAMES:
        setattr(P, nm, getattr(A, nm)[:k + 1])            # views, no copy: index k+1 does not exist
    P.humps = A.humps[A.humps[:, 7] <= k]
    tb = api._blind(t)
    for rid, f in fns.items():
        a = bool(f(tb, A))
        try:
            b = bool(f(tb, P))
        except Exception:                                   # noqa: BLE001
            b = None
        if a != b:
            bad[rid] += 1
print('trades whose decision changes when bars > k are removed:', bad)
print('ALL CLEAN' if not any(bad.values()) else 'LOOK-AHEAD FOUND')
