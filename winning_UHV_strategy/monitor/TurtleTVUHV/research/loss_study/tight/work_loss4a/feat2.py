"""quantile tables of decision-time features vs loss rate (base / secure / tight, train / test) - loss4a."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TIGHT = os.path.dirname(HERE)
z = np.load(os.path.join(os.path.dirname(TIGHT), 'arrays.npz'))
t, o, h, l, c, v, atr = (z[k] for k in ('t', 'o', 'h', 'l', 'c', 'v', 'atr'))
P = 1e-4
SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('tight', 'secure', 'base')}

def sec(r): return r['t_dec'] % 60
F = {
    'share': lambda r: r['brk_ticks'] / max(r['uhv_v'], 1),
    'sec_in_min': sec,
    'rate_ratio': lambda r: (r['brk_ticks'] / max(sec(r), 0.5)) / (r['uhv_v'] / 60.0),
    'brk_ticks': lambda r: r['brk_ticks'],
    'opp_vol30': lambda r: (lambda k, s: float(v[k-29:k+1][((c[k-29:k+1] - o[k-29:k+1]) * s) < 0].sum() / max(v[k-29:k+1].sum(), 1)))(r['k'], r['side']),
    'opp_vol60': lambda r: (lambda k, s: float(v[k-59:k+1][((c[k-59:k+1] - o[k-59:k+1]) * s) < 0].sum() / max(v[k-59:k+1].sum(), 1)))(r['k'], r['side']),
    'uhv_rel30': lambda r: r['uhv_v'] / max(float(v[r['k']-29:r['k']+1].mean()), 1),
    'uhv_vs_max30': lambda r: r['uhv_v'] / max(float(v[r['k']-29:r['k']+1].max()), 1),
}

def qtable(stack, f, q=(0, .1, .2, .4, .6, .8, .9, 1.0)):
    T = ST[stack]
    xa = np.array([f(r) for r in T])
    edges = np.unique(np.quantile(xa, q))
    edges[0] -= 1e-9; edges[-1] += 1e-9
    out = []
    for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
        idx = [i for i, r in enumerate(T) if flt(r)]
        x = xa[idx]; w = np.array([T[i]['win'] for i in idx])
        base = 100 * (~w).mean()
        row = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (x >= a) & (x < b)
            n = int(m.sum()); L = int((~w[m]).sum())
            row.append(f"<{b:.3g}: {n}/{L}L x{(100*L/max(n,1))/max(base,1e-9):.1f}")
        out.append(f"{part}(base {base:.2f}%) " + ' | '.join(row))
    return out

if __name__ == '__main__':
    names = sys.argv[1:] or list(F)
    for nm in names:
        print('---', nm)
        for st in ('tight', 'secure', 'base'):
            for line in qtable(st, F[nm]):
                print(f'  {st:6s} {line}')
    # the two studied losses and their twins
    T = {r['id']: r for r in ST['tight']}
    print()
    for tid in ('0408-075606-B', '0407-232607-B', '0408-102512-B', '0408-121316-B', '0723-001905-S', '0722-174558-S', '0722-235911-S', '0723-140845-S', '1019-171329-S', '1023-145031-B'):
        r = T[tid]
        print(tid, 'W' if r['win'] else 'L', ' '.join(f"{nm}={F[nm](r):.3f}" for nm in names))
