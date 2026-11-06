"""trigger_spread.py - ANALYSIS OUTSIDE api.report (the harness has no trigger-tick ask): the spread (ask - bid) of the breakout
tick itself - the first tick whose bid crosses the UHV level, i.e. the moment the entry is decided (no future information).
The engine fills 0.3 s later (InpUhvLatency), so t['fill'] - t['brk_hi_so_far'] (rule_buy_spread_1p5) = spread at the fill + 0.3 s
of movement; this script measures the clean version, for both sides. Python hypothesis - NOT PROMOTED until MT5."""
import json, os, sys
import numpy as np, pandas as pd
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402
inp = json.load(open(os.path.join(ROOT, 'settings', 'saved', '2026-11-05 05-45-38.json'), encoding='utf-8'))['inputs']
S, TK = U._setups(U.det_file(inp))
S = U._instant_setups(TK, float(inp.get("InpUhvPreBreak") or 0), U.det_file(inp))
st = np.array([s['t'] for s in S]); T, B, A = TK['t'], TK['bid'], TK['ask']
tr = json.load(open(os.path.join(ROOT, 'research', 'loss_study', 'trades.json'), encoding='utf-8'))
SPLIT = 1782864000
rows = []
for t in tr:
    s = S[int(np.searchsorted(st, t['t_in'] + 1e-6)) - 1]
    i = int(np.searchsorted(T, s['t'])); k = i
    while k < len(T) and T[k] == T[i] and B[k] != s['bc']:
        k += 1
    if k >= len(T) or T[k] != T[i]:
        k = i
    rows.append((t['id'], t['side'], int(not t['win']), 'train' if t['t_in'] < SPLIT else 'test', (A[k] - B[k]) / 1e-4))
d = pd.DataFrame(rows, columns=['id', 'side', 'loss', 'half', 'spr_trig'])
d.to_csv(os.path.join(HERE, 'trigger_spread.csv'), index=False)
base = d.groupby('half').loss.mean()
for name, m in [('BUY  trigger spread >= 1.5', (d.side > 0) & (d.spr_trig >= 1.5)), ('SELL trigger spread >= 1.5', (d.side < 0) & (d.spr_trig >= 1.5)),
                ('ANY  trigger spread >= 1.5', d.spr_trig >= 1.5), ('ANY  trigger spread >= 1.0', d.spr_trig >= 1.0), ('ANY  trigger spread >= 2.0', d.spr_trig >= 2.0)]:
    out = []
    for hf in ('train', 'test'):
        mm = m & (d.half == hf)
        out.append(f"{hf} x{d.loss[mm].mean() / base[hf]:.2f} ({int(d.loss[mm].sum())}L/{int(mm.sum() - d.loss[mm].sum())}W)")
    print(f"{name:28s} removes {int(m.sum()):3d} (losers {int(d.loss[m].sum())} / winners {int(m.sum() - d.loss[m].sum())}) lift x{d.loss[m].mean() / d.loss.mean():.2f} | " + '  '.join(out))
b1 = json.load(open(os.path.join(ROOT, 'research', 'loss_study', 'batch_1.json'), encoding='utf-8'))
ids = {c['id'] for c in b1['losses']}
print('batch_1 losses with trigger spread >= 1.0:', d[d.id.isin(ids) & (d.spr_trig >= 1.0)][['id', 'spr_trig']].values.tolist())
