import json, numpy as np
R = json.load(open('agents/batch_2/feat_table.json'))
F = {k: np.array([r.get(k, np.nan) for r in R], dtype=float) for k in R[0].keys() if k not in ('id',)}
L = ~F['win'].astype(bool); TR = F['train'].astype(bool)
bt, be = L[TR].mean(), L[~TR].mean()
def ev(m, lab):
    m = m.astype(bool)
    lt = L[m & TR].sum(); nt = (m & TR).sum(); le = L[m & ~TR].sum(); ne = (m & ~TR).sum()
    print(f"{lab:60s} n={m.sum():4d} L={L[m].sum():3d} | tr {lt}/{nt} x{(lt/max(nt,1))/bt:5.2f}  te {le}/{ne} x{(le/max(ne,1))/be:5.2f}")
