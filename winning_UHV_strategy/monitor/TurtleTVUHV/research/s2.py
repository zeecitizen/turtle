import numpy as np
tr=np.load("research/trades.npy"); p=tr[:,6]; w=p>0
mins=(tr[:,4]-tr[:,1])/60; mfe=tr[:,15]; mae=tr[:,16]
print("cols sample", tr[0])
for nm,m in (("win",w),("loss",~w)):
    print(nm, int(m.sum()), "mins q", np.percentile(mins[m],[10,50,75,90,95,99]).round(1), "MAE q", np.percentile(mae[m],[50,75,90,95,99,100]).round(2), "MFE q", np.percentile(mfe[m],[10,50,90]).round(2))
print("loss pnl", np.sort(p[~w]).round(0))
# keep-share: winners with MAE below X
for X in (2,3,4,5,6,8,10,12,15,20):
    print(X, "winners kept", round((mae[w]<X).mean()*100,1), "losers w/ mae>=X", int((mae[~w]>=X).sum()))
for T in (5,10,15,20,30,45,60,90,120):
    print("T",T,"winners done by T", round((mins[w]<=T).mean()*100,1), "losers still open at T", int((mins[~w]>T).sum()))
