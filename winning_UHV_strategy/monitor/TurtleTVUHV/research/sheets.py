from _load import *
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from datetime import datetime, timezone
D=sim.data("m15"); t15=D["t15"]; o=D["o15"]; h=D["h15"]; l=D["l15"]; c=D["c15"]
e19=sim.ema(c,19,c[0]); e66=sim.ema(c,66,c[0])
tr=np.load("trades.npy"); w=tr[:,6]>0
rng=np.random.default_rng(7)
L=np.where(~w)[0]; W=rng.choice(np.where(w)[0], 24, replace=False)
def draw(ax, x, tag):
    i=int(np.searchsorted(t15,x[1],side="right"))-1; j=int(np.searchsorted(t15,x[4],side="right"))-1
    a=max(0,i-60); b=min(len(c),max(j,i)+12)
    for k in range(a,b):
        col="#26a69a" if c[k]>=o[k] else "#ef5350"
        ax.plot([k,k],[l[k],h[k]],color=col,lw=.6); ax.add_patch(plt.Rectangle((k-.35,min(o[k],c[k])),.7,abs(c[k]-o[k])+1e-6,color=col))
    ax.plot(range(a,b),e19[a:b],color="#ffb300",lw=.8); ax.plot(range(a,b),e66[a:b],color="#5c6bc0",lw=.8)
    for k in range(a+3,b-3):
        if h[k]>h[k-3:k].max() and h[k]>h[k+1:k+4].max(): ax.plot(k,h[k]+.3,"v",ms=3,color="#888")
        if l[k]<l[k-3:k].min() and l[k]<l[k+1:k+4].min(): ax.plot(k,l[k]-.3,"^",ms=3,color="#888")
    s=x[0]; en=x[2]; ax.axhline(en,color="k",lw=.6); ax.axhline(x[3],color="r",lw=.6,ls="--"); ax.axhline(en+s*2,color="g",lw=.6,ls="--")
    ax.axvline(i,color="k",lw=.4); ax.axvline(j,color="m",lw=.4)
    ax.set_title(f"{tag} {'BUY' if s>0 else 'SELL'} {datetime.fromtimestamp(x[1],timezone.utc):%Y-%m-%d %a %H:%M} {x[6]:+.0f} why{int(x[13])}",fontsize=6)
    ax.tick_params(labelsize=4)
def sheet(idx, name, tag):
    for p in range(0,len(idx),12):
        f,axs=plt.subplots(3,4,figsize=(16,9))
        for ax,k in zip(axs.flat, idx[p:p+12]): draw(ax, tr[k], tag)
        f.tight_layout(); f.savefig(f"sheets/{name}_{p//12:02d}.png",dpi=110); plt.close(f)
import os; os.makedirs("sheets",exist_ok=True)
sheet(L,"loss","L"); sheet(W,"win","W"); print(len(L))
