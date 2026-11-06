import json, sys, numpy as np
R = json.load(open('agents/batch_2/feat_table.json'))
L_all = np.array([not r['win'] for r in R]); TR = np.array([r['train'] for r in R])
bt, be = L_all[TR].mean(), L_all[~TR].mean(); base = L_all.mean()
print(f"base all {100*base:.2f}%  train {100*bt:.2f}% (n={TR.sum()})  test {100*be:.2f}% (n={(~TR).sum()})")
def show(name, qs=(0, .05, .1, .25, .5, .75, .9, .95, 1.0), cat=False):
    x = np.array([r[name] for r in R], dtype=float)
    edges = np.unique(x) if cat else np.unique(np.quantile(x, qs))
    print(f"--- {name}")
    pairs = [(e, e) for e in edges] if cat else list(zip(edges[:-1], edges[1:]))
    for a, b in pairs:
        m = (x == a) if cat else ((x >= a) & ((x < b) if b < edges[-1] else (x <= b)))
        if m.sum() == 0: continue
        lt = L_all[m & TR].sum(); nt = (m & TR).sum(); le = L_all[m & ~TR].sum(); ne = (m & ~TR).sum()
        print(f"  [{a:9.3f},{b:9.3f}] n={m.sum():5d} L={L_all[m].sum():3d} rate={100*L_all[m].mean():5.2f}% lift={L_all[m].mean()/base:4.2f} | tr {lt}/{nt} x{(lt/max(nt,1))/bt:4.2f}  te {le}/{ne} x{(le/max(ne,1))/be:4.2f}")
for n in sys.argv[1:]:
    if n.startswith('cat:'): show(n[4:], cat=True)
    else: show(n)
