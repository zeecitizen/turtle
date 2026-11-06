import os, pandas as pd, numpy as np, time, sys
t0=time.time()
src=r'C:\Users\zeesh\turtle\EURUSD_tick_data\EURUSD.i_202601020000_202611040757.csv'
df=pd.read_csv(src,sep='\t',usecols=[0,1,2,3],names=['d','t','bid','ask'],header=0,dtype={'d':str,'t':str})
print('rows',len(df),round(time.time()-t0))
df['bid']=df['bid'].ffill(); df['ask']=df['ask'].ffill()
df=df.dropna(subset=['bid','ask'])
ts=pd.to_datetime(df['d']+' '+df['t'],format='%Y.%m.%d %H:%M:%S.%f')
sec=ts.to_numpy().astype('datetime64[ms]').astype('int64')/1000.0
sec=np.asarray(sec,dtype=np.float64); bid=df['bid'].to_numpy(np.float64); ask=df['ask'].to_numpy(np.float64)
assert np.all(np.diff(sec)>=0), 'not sorted'
sp=ask-bid
print('sec range',sec[0],sec[-1]); print('ticks',len(sec),'first',ts.iloc[0],'last',ts.iloc[-1])
print('spread pips: median',np.median(sp)*1e4,'p90',np.percentile(sp,90)*1e4,'neg',(sp<0).sum())
hr=ts.dt.hour.to_numpy()
m=(hr>=9)&(hr<21)
print('spread pips 09-21 server: median',np.median(sp[m])*1e4,'mean',sp[m].mean()*1e4)
out=sys.argv[1]
for name,a in (('eur_t.bin',sec),('eur_bid.bin',bid),('eur_ask.bin',ask)):
    a.astype(np.float64).tofile(os.path.join(out,name))
print('done',round(time.time()-t0))
