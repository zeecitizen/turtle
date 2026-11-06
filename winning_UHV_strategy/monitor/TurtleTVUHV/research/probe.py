# HYPOTHESIS SCREEN (Python, NOT PROMOTED): probe 0.01 at entry, add 2 lots when confirmed. Same stop / TP as the trade.
from _load import *
D=sim.data("m15"); t1=D["t1"]; h1=D["h1"]; l1=D["l1"]
tr=np.load("trades.npy"); w=tr[:,6]>0
def run(X, mode):
    nW=nL=0; pn=0.0
    for x,win in zip(tr,w):
        s=x[0]; en=x[2]; sl=abs(en-x[3]); a=np.searchsorted(t1,x[1]); b=np.searchsorted(t1,x[4])+1
        fav = (h1[a:b]-en) if s>0 else (en-l1[a:b]); adv=(en-l1[a:b]) if s>0 else (h1[a:b]-en)
        if mode=="run":                      # goes X in our direction at any time
            hit=np.where(fav>=X)[0]
        else:                                # first dips X against, then comes back to the entry
            d=np.where(adv>=X)[0]
            hit=d[:0] if not len(d) else d[0]+np.where(fav[d[0]:]>=0)[0]
        probe=x[6]/200*1                    # 0.01 lot ~ pnl/200
        if len(hit)==0 or (not win and False): pn+=probe; continue
        add_en = X if mode=="run" else 0.0  # add price relative to entry
        if win: pn+=probe+(2-add_en)*200; nW+=1
        else:   pn+=probe-(sl+add_en)*200; nL+=1
    return nW,nL,pn
print("BASE (2 lots from the start): WR %.1f%% net %+.0f" % (100*w.mean(), tr[:,6].sum()))
for X in (0.25,0.5,1.0,1.5):
    nW,nL,pn=run(X,"run"); print(f"add after +${X} in our favour : adds {nW+nL:4d}  WR of adds {100*nW/max(1,nW+nL):5.1f}%  net {pn:+9.0f}")
for X in (2,4,6,10):
    nW,nL,pn=run(X,"back"); print(f"add when back at entry after -${X} dip: adds {nW+nL:4d}  WR of adds {100*nW/max(1,nW+nL):5.1f}%  net {pn:+9.0f}")
