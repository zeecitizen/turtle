from _load import *
D=sim.data("m15"); t1=D["t1"]; h1=D["h1"]; l1=D["l1"]; c1=D["c1"]
tr=np.load("research/trades.npy"); w=tr[:,6]>0
print("t1 step", np.median(np.diff(t1[:1000])))
CK=(5,15,30,60,120)
res={k:[] for k in CK}; maeck={k:[] for k in CK}
for x in tr:
    s=x[0]; en=x[2]; a=np.searchsorted(t1,x[1]); 
    for k in CK:
        b=np.searchsorted(t1,x[1]+k*60)
        if x[4] <= x[1]+k*60: res[k].append(np.nan); maeck[k].append(np.nan); continue
        seg=slice(a,b)
        res[k].append(s*(c1[b-1]-en)); maeck[k].append((en-l1[seg].min()) if s>0 else (h1[seg].max()-en))
for k in CK:
    r=np.array(res[k]); m=np.array(maeck[k]); o=~np.isnan(r)
    print(f"\n== still open at {k} min: winners {int((o&w).sum())} losers {int((o&~w).sum())}")
    for thr in (-2,-4,-6,-8,-10,-12,-15):
        cw=int(((r<=thr)&o&w).sum()); cl=int(((r<=thr)&o&~w).sum())
        print(f"   underwater <= {thr:4d}$ at {k}m: winners {cw:4d}  losers {cl:3d}   loser share {100*cl/max(1,cw+cl):5.1f}%")
