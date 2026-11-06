from _load import *
import pickle
D=sim.data("m15"); t15=D["t15"]; h=D["h15"]; l=D["l15"]; c=D["c15"]; o=D["o15"]; atr=D["atr"]
tr=np.load("trades.npy"); w=tr[:,6]>0; R=pickle.load(open("feat.pkl","rb")); yr=np.array([r["year"] for r in R]); H1=yr<=2024
pre=[];kill=[];vsday=[]
for x in tr:
    i=int(np.searchsorted(t15,x[1],side="right"))-2; j=int(np.searchsorted(t15,x[4],side="right"))-1
    rg=(h-l)/atr[i]
    pre.append(rg[i-16:i+1].max()); kill.append(rg[i+1:j+1].max() if j>i else 0)
    vsday.append((h[i-96:i+1].max()-l[i-96:i+1].min())/atr[i])
pre=np.array(pre); kill=np.array(kill); vsday=np.array(vsday)
print("killer candle (max range / ATR during trade) losers med", np.median(kill[~w]).round(2), "winners med", np.median(kill[w]).round(2))
for nm,v in (("pre4h_maxrange",pre),("dayrange",vsday)):
    for q in (75,90,95):
        t=np.percentile(v,q); m=v>=t
        lr=lambda mm:100*(~w[mm]).mean()
        print(nm, f">=p{q} {t:.2f} n={m.sum()} loss%={lr(m):.1f} H1={lr(m&H1):.1f} H2={lr(m&~H1):.1f}")
