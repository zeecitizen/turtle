import pickle, numpy as np
R=pickle.load(open("research/feat.pkl","rb")); BE=0.095
win=np.array([r["win"] for r in R]); pnl=np.array([r["pnl"] for r in R]); yr=np.array([r["year"] for r in R]); H1=yr<=2024
print(f"ALL n={len(R)} lossrate={100*(~win).mean():.1f}%  H1 {100*(~win[H1]).mean():.1f}% H2 {100*(~win[~H1]).mean():.1f}%  (filter pays only if removed trades lose > {BE*100:.1f}%)")
def show(name, mask):
    for lab,m in (("H1",H1),("H2",~H1),("all",np.ones_like(H1))):
        pass
    m=mask; a=m.sum()
    if a<15: return
    lr=lambda mm: 100*(~win[mm]).mean() if mm.sum() else float('nan')
    flag = "  <== CANDIDATE" if lr(m&H1)>BE*100 and lr(m&~H1)>BE*100 else ""
    print(f"  {name:28s} n={a:4d} losses={int((~win[m]).sum()):3d} lossrate={lr(m):5.1f}% H1={lr(m&H1):5.1f}% H2={lr(m&~H1):5.1f}% net={pnl[m].sum():+9.0f}{flag}")
keys=[k for k in R[0] if k not in ("pnl","win","t")]
for k in keys:
    v=np.array([r[k] for r in R],float); print(k)
    u=np.unique(v)
    if len(u)<=24:
        for x in u: show(f"={x:g}", v==x)
    else:
        q=np.percentile(v,[10,25,50,75,90])
        show(f"<= p10 {q[0]:.2f}", v<=q[0]); show(f"<= p25 {q[1]:.2f}", v<=q[1]); show(f">= p75 {q[3]:.2f}", v>=q[3]); show(f">= p90 {q[4]:.2f}", v>=q[4])
