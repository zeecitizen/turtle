from _load import *
import time; t=time.time()
tr, st = trades()
p = tr[:,6]
print(time.time()-t, tr.shape, len(p), p.sum(), (p>0).mean(), p[p<=0].mean(), p.min())
D = sim.data("m15"); print({k: getattr(D[k],'shape',None) for k in D})
from collections import Counter; print(Counter(tr[:,13].astype(int)))
print(Counter(tr[p<=0,13].astype(int)))
np.save("research/trades.npy", tr)
