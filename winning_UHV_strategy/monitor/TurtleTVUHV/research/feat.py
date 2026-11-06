"""entry features for every trade of 2026-10-25 05-58-25 (m15). Pre-registered hypotheses: HTF trend against the side, camel humps against,
chop measures (CHOP, ER, ADX, VHF, R2), volatility. Bar = last CLOSED M15 candle before entry."""
from _load import *
D = sim.data("m15"); t15=D["t15"]; o=D["o15"]; h=D["h15"]; l=D["l15"]; c=D["c15"]; atr=D["atr"]; adx=D["adx"]
def ema(x,n): return sim.ema(x,n,x[0])
E = {n: ema(c,n) for n in (19,66,200,264,800)}
tr=np.load("research/trades.npy")
def pivots(i, look, p):
    hs=[];ls=[]
    for k in range(i-look, i-p+1):
        if k-p<0: continue
        if all(h[k]>h[k-q] and h[k]>h[k+q] for q in range(1,p+1)): hs.append(h[k])
        if all(l[k]<l[k-q] and l[k]<l[k+q] for q in range(1,p+1)): ls.append(l[k])
    return hs, ls
def camel(i, look, p):
    hs,ls=pivots(i,look,p)
    if len(hs)<2 or len(ls)<2: return 0
    bh=max(o[hs and 0 or 0:0] if False else [0]) if False else None
    up = (hs[-1]>hs[-2] or c[i]>hs[-1]) and ls[-1]>ls[-2]
    dn = (ls[-1]<ls[-2] or c[i]<ls[-1]) and hs[-1]<hs[-2]
    return 0 if up==dn else (1 if up else -1)
def er(i,n): return abs(c[i]-c[i-n])/max(1e-9,np.abs(np.diff(c[i-n:i+1])).sum())
def chop(i,n):
    tr_=np.maximum(h[i-n+1:i+1],c[i-n:i])-np.minimum(l[i-n+1:i+1],c[i-n:i])
    return 100*np.log10(tr_.sum()/max(1e-9,h[i-n+1:i+1].max()-l[i-n+1:i+1].min()))/np.log10(n)
def vhf(i,n): return (c[i-n:i+1].max()-c[i-n:i+1].min())/max(1e-9,np.abs(np.diff(c[i-n:i+1])).sum())
def r2(i,n):
    y=c[i-n+1:i+1]; x=np.arange(n); return np.corrcoef(x,y)[0,1]**2*np.sign(np.corrcoef(x,y)[0,1])
rows=[]
for x in tr:
    s=int(x[0]); i=int(np.searchsorted(t15, x[1], side="right"))-2   # t15 = bar open; entry bar is i+1 -> last closed = i
    f=dict(side=s, pnl=x[6], win=x[6]>0, t=x[1], year=int(1970+x[1]//31557600), hour=int((x[1]//3600)%24), dow=int(((x[1]//86400)+4)%7))
    for n in (66,200,264,800):
        f[f"sl{n}"]=s*(E[n][i]-E[n][i-8])/atr[i]          # slope in the trade's direction, ATR units
        f[f"px{n}"]=s*(c[i]-E[n][i])/atr[i]
    f["sl19"]=s*(E[19][i]-E[19][i-5])/atr[i]
    f["align"]= s*np.sign(E[19][i]-E[66][i])
    for look,p in ((48,2),(96,2),(96,3),(192,3)): f[f"camel{look}_{p}"]=s*camel(i,look,p)
    f["er16"]=er(i,16); f["er48"]=er(i,48); f["chop14"]=chop(i,14); f["chop48"]=chop(i,48); f["adx"]=adx[i]; f["vhf28"]=vhf(i,28)
    f["r2_32"]=s*r2(i,32); f["atr"]=atr[i]; f["atrrel"]=atr[i]/np.mean(atr[i-96:i])
    f["dir16"]=s*(c[i]-c[i-16])/atr[i]; f["dir96"]=s*(c[i]-c[i-96])/atr[i]
    rows.append(f)
import pickle; pickle.dump(rows, open("research/feat.pkl","wb")); print(len(rows))
