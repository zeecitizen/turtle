"""'trigger spread above the recent floor' - regime-free upper-mode rule; also scored on base AFTER the existing guards (loss4a)."""
import io, os, sys, contextlib, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import api_tight
from rules import chance, p_hyper
M = np.load(os.path.join(HERE, 'spread_m1.npz'))['med']
NY = ZoneInfo('America/New_York')
def guarded(t):
    d = dt.datetime.fromtimestamp(t['t_dec'], NY); m = d.hour * 60 + d.minute
    return not (16 * 60 + 45 <= m < 17 * 60 + 45) and t['trig_spread_pips'] < 1.0 - 1e-9
api_tight.STACKS['base_g'] = [t for t in api_tight.STACKS['base'] if guarded(t)]
def chance_g(rule):
    r = api_tight.score(rule, 'base_g'); out = []
    for part in ('train', 'test'):
        c = r[part]; N, K, n, x = c['trades'], c['losses'], c['removed'], c['losses_removed']; e = n * K / max(N, 1)
        out.append(f"{part} WR {c['wr_before']}->{c['wr_after']} {x}L/{n} (exp {e:.1f}, x{x / e if e else 0:.2f}, p {p_hyper(N, K, n, x):.3f})")
    return 'base_guarded (no rollover, spread<1.0): ' + ', '.join(out)
def mk_floor(N, q):
    def r(t, A):
        k = t['k']; fl = float(np.quantile(M[k - N + 1:k + 1], q)); return t['trig_spread_pips'] > fl + 0.05
    return r
print('base_guarded:', len(api_tight.STACKS['base_g']), 'trades', sum(1 for t in api_tight.STACKS['base_g'] if not t['win']), 'losses')
for N in (60, 120, 240, 480):
    for q in (0.05, 0.1, 0.25):
        r = mk_floor(N, q); nm = f'above floor N{N} q{q}'
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            api_tight.report(r, nm)
        line = buf.getvalue().strip()
        sec = line.split('| secure: ')[1].split(' | base: ')[0]; base = line.split(' | base: ')[1]; tight = line.split('tight: ')[1].split(' | zee100')[0]
        print(f"{nm:24s} tight {tight} || secure {sec} || base {base}")
        print(f"{'':24s} {chance(r)}")
        print(f"{'':24s} {chance_g(r)}")
