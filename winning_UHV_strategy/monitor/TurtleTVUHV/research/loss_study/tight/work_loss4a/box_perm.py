"""How surprising is a 0-loss box? Zee's 100% setting = humps 2-3 x ER16 [0.30, 0.35). Within the secure stack (humps 2-5, ER 0.15-0.45,
2237 trades / 30 losses) search every box humps [2, hmax] x ER [lo, hi) on a 0.05 grid; count boxes with >= 300 trades and 0 losses.
Then shuffle the 30 loss labels 2000 times: how often does SOME such box exist by luck? (loss4a; Python, hypothesis-level statistics)"""
import json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TIGHT = os.path.dirname(HERE)
S = json.load(open(os.path.join(TIGHT, 'trades_secure.json')))
er = np.array([r['er16'] for r in S]); hu = np.array([r['humps'] for r in S]); L = np.array([not r['win'] for r in S])
grid = np.round(np.arange(0.15, 0.4501, 0.05), 2)
boxes = []
for hmax in (2, 3, 4, 5):
    for i, lo in enumerate(grid):
        for hi in grid[i + 1:]:
            m = (hu >= 2) & (hu <= hmax) & (er >= lo - 1e-9) & (er < hi - 1e-9)
            if m.sum() >= 300:
                boxes.append((hmax, lo, hi, m))
print('candidate boxes with >= 300 trades:', len(boxes))
real = [(h, lo, hi, int(m.sum())) for h, lo, hi, m in boxes if not L[m].any()]
print('0-loss boxes in the REAL labels:', real)
print('loss rate of the secure stack: %.2f%%' % (100 * L.mean()))
rng = np.random.default_rng(7)
hits = 0; best = []
M = np.array([m for _, _, _, m in boxes])
for _ in range(2000):
    Lp = rng.permutation(L)
    z = ~((M & Lp).any(axis=1))
    if z.any():
        hits += 1
print(f'shuffled labels: some >= 300-trade 0-loss box exists in {hits}/2000 = {100 * hits / 2000:.1f}% of shuffles')
# the same with the base stack (humps 2-5 subset of base, still post-hoc)
B = json.load(open(os.path.join(TIGHT, 'trades_base.json')))
erb = np.array([r['er16'] for r in B]); hub = np.array([r['humps'] for r in B]); Lb = np.array([not r['win'] for r in B])
m = (hub >= 2) & (hub <= 3) & (erb >= 0.30) & (erb < 0.35)
print('base stack, humps 2-3 x ER [0.30, 0.35):', int(m.sum()), 'trades,', int(Lb[m].sum()), 'losses')
for lo in grid[:-1]:
    hi = round(lo + 0.05, 2)
    mm = (hub >= 2) & (hub <= 3) & (erb >= lo - 1e-9) & (erb < hi - 1e-9)
    ms = (hu >= 2) & (hu <= 3) & (er >= lo - 1e-9) & (er < hi - 1e-9)
    print(f'  humps 2-3 ER [{lo:.2f},{hi:.2f}): base {int(mm.sum())}/{int(Lb[mm].sum())}L   secure {int(ms.sum())}/{int(L[ms].sum())}L')
p_t = (1 - 4 / 714) ** 308; p_s = (1 - 30 / 2237) ** 308
print(f'P(0 losses in 308) at tight rate 4/714: {100 * p_t:.1f}%  | at secure rate 30/2237: {100 * p_s:.1f}%  | 95% upper bound on the loss rate after 0/308: {100 * (1 - 0.05 ** (1 / 308)):.2f}% (WR >= {100 * 0.05 ** (1 / 308):.2f}%)')

# matched to the observed box size in the secure stack (287 trades)
boxes2 = []
for hmax in (2, 3, 4, 5):
    for i, lo in enumerate(grid):
        for hi in grid[i + 1:]:
            m = (hu >= 2) & (hu <= hmax) & (er >= lo - 1e-9) & (er < hi - 1e-9)
            if m.sum() >= 280:
                boxes2.append(m)
M2 = np.array(boxes2)
print('boxes with >= 280 trades:', len(boxes2), '| 0-loss ones in the real labels:', int((~((M2 & L).any(axis=1))).sum()))
hits2 = sum(1 for _ in range(4000) if (~((M2 & rng.permutation(L)).any(axis=1))).any())
print(f'shuffled labels: some >= 280-trade 0-loss box exists in {hits2}/4000 = {100 * hits2 / 4000:.1f}% of shuffles')
