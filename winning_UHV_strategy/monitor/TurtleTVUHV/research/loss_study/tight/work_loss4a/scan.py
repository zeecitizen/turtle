"""broad decile scan of decision-time features (hypothesis generation only) - loss4a."""
import json, os, sys, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
z = np.load(os.path.join(os.path.dirname(TIGHT), 'arrays.npz'))
t, o, h, l, c, v, atr, adx = (z[k] for k in ('t', 'o', 'h', 'l', 'c', 'v', 'atr', 'adx'))
SM = np.load(os.path.join(HERE, 'spread_m1.npz'))['med']
P = 1e-4; SPLIT = 1782864000
ST = {nm: json.load(open(os.path.join(TIGHT, f'trades_{nm}.json'))) for nm in ('tight', 'secure', 'base')}

def er(k, n, s=None):
    cc = c[k - n:k + 1]; p = np.abs(np.diff(cc)).sum()
    e = (cc[-1] - cc[0]) / p if p > 0 else 0.0
    return e * s if s is not None else abs(e)

def legvol(r, N=60):
    k, s = r['k'], r['side']
    if s > 0:
        jL = k - N + 1 + int(np.argmin(l[k - N + 1:k + 1]))
        a = max(jL - N, 0); jH = a + int(np.argmax(h[a:jL + 1]))
    else:
        jL = k - N + 1 + int(np.argmax(h[k - N + 1:k + 1]))
        a = max(jL - N, 0); jH = a + int(np.argmin(l[a:jL + 1]))
    if jL >= k - 1 or jH >= jL:
        return np.nan
    return float(v[jL:k + 1].mean() / max(v[jH:jL + 1].mean(), 1))

def pos(r, N):
    k, s = r['k'], r['side']; hi, lo = h[k - N + 1:k + 1].max(), l[k - N + 1:k + 1].min()
    if hi <= lo: return 0.5
    return (r['level'] - lo) / (hi - lo) if s > 0 else (hi - r['level']) / (hi - lo)

def order(r, N):
    """+1 if the later of the N-bar extremes is in the trade direction (with the last big move), -1 if against"""
    k, s = r['k'], r['side']
    jh = int(np.argmax(h[k - N + 1:k + 1])); jl = int(np.argmin(l[k - N + 1:k + 1]))
    return (1 if jh > jl else -1) * s

F = {
    'atr_p': lambda r: atr[r['k']] / P,
    'adx': lambda r: adx[r['k']],
    'ret_depth_atr': lambda r: abs(r['level'] - r['extreme']) / max(atr[r['k']], 1e-9),
    'ret_depth_p': lambda r: abs(r['level'] - r['extreme']) / P,
    'uhv_age': lambda r: r['k'] - r['ku'],
    'er8_signed': lambda r: er(r['k'], 8, r['side']),
    'er16_signed': lambda r: er(r['k'], 16, r['side']),
    'er32_signed': lambda r: er(r['k'], 32, r['side']),
    'er64_signed': lambda r: er(r['k'], 64, r['side']),
    'er120_signed': lambda r: er(r['k'], 120, r['side']),
    'mv60_atr': lambda r: r['side'] * (c[r['k']] - c[r['k'] - 60]) / max(atr[r['k']], 1e-9),
    'mv240_atr': lambda r: r['side'] * (c[r['k']] - c[r['k'] - 240]) / max(atr[r['k']], 1e-9),
    'pos60': lambda r: pos(r, 60), 'pos240': lambda r: pos(r, 240),
    'order60': lambda r: order(r, 60), 'order120': lambda r: order(r, 120),
    'legvol60': lambda r: legvol(r, 60),
    'vol10': lambda r: float(v[r['k'] - 9:r['k'] + 1].mean()),
    'vol_trend': lambda r: float(v[r['k'] - 4:r['k'] + 1].mean() / max(v[r['k'] - 34:r['k'] - 4].mean(), 1)),
    'uhv_body': lambda r: abs(c[r['ku']] - o[r['ku']]) / max(h[r['ku']] - l[r['ku']], 1e-9),
    'k_body_signed': lambda r: r['side'] * (c[r['k']] - o[r['k']]) / max(h[r['k']] - l[r['k']], 1e-9),
    'k_close_to_level': lambda r: r['side'] * (c[r['k']] - r['level']) / max(atr[r['k']], 1e-9),
    'stop_p': lambda r: abs(r['brk_bid'] - r['extreme']) / P + 19,
    'box': lambda r: r['box'],
    'humps': lambda r: r['humps'],
    'er16': lambda r: r['er16'],
    'sp_rel': lambda r: r['trig_spread_pips'] - float(np.median(SM[r['k'] - 59:r['k'] + 1])),
    'sp_atr': lambda r: r['trig_spread_pips'] / max(atr[r['k']] / P, 1e-9),
    'gap_brk': lambda r: r['side'] * (r['brk_bid'] - r['level']) / P,
    'brk_range_p': lambda r: (r['brk_hi'] - r['brk_lo']) / P,
    'dow': lambda r: (int(r['t_dec'] // 86400) + 3) % 7,
}

def tails(stack, f):
    T = ST[stack]
    xa = np.array([f(r) for r in T], dtype=float)
    ok = ~np.isnan(xa)
    lo_q, hi_q = np.nanquantile(xa, 0.1), np.nanquantile(xa, 0.9)
    out = {}
    for part, flt in (('tr', lambda r: r['t_dec'] < SPLIT), ('te', lambda r: r['t_dec'] >= SPLIT)):
        idx = np.array([i for i, r in enumerate(T) if flt(r)])
        w = np.array([T[i]['win'] for i in idx]); x = xa[idx]
        base = (~w).mean()
        for tail, m in (('lo', x <= lo_q), ('hi', x >= hi_q)):
            n = m.sum(); L = (~w[m]).sum()
            out[(part, tail)] = (L / max(n, 1)) / max(base, 1e-9), int(n), int(L)
    return out

print(f"{'feature':18s} tail | base tr   base te   | secure tr  secure te   (lift = loss rate in the decile / the half's rate)")
for nm, f in F.items():
    rb, rs = tails('base', f), tails('secure', f)
    for tail in ('lo', 'hi'):
        cells = [rb[('tr', tail)], rb[('te', tail)], rs[('tr', tail)], rs[('te', tail)]]
        flag = ' <==' if all(cc[0] >= 1.3 for cc in cells) else (' <-- (base both)' if cells[0][0] >= 1.3 and cells[1][0] >= 1.3 else '')
        print(f"{nm:18s} {tail}   | " + '  '.join(f"x{cc[0]:.2f}({cc[2]}/{cc[1]})" for cc in cells) + flag)
