from _load import *
import itertools
def st(inp, ds="m15"):
    tr,_=trades(inp, ds=ds); p=tr[:,6]; eq=np.cumsum(p); dd=float((np.maximum.accumulate(eq)-eq).max())
    yr=1970+tr[:,1]//31557600; h1=p[yr<=2024].sum(); h2=p[yr>2024].sum()
    return f"n={len(p):4d} WR={100*(p>0).mean():5.1f}% net={p.sum():+9.0f} avgL={p[p<=0].mean():6.0f} worst={p.min():6.0f} DD={dd:6.0f} H1={h1:+8.0f} H2={h2:+8.0f}"
def V(**kv):
    d=dict(INP); d.update({k:str(v) for k,v in kv.items()}); return d
if __name__=="__main__":
    print("BASE        ", st(INP))
    for b,r in itertools.product((2,4,6,8,12),(-0.3,-0.4,-0.5,-0.6)):
        print(f"decay {b:2d} {r:4}", st(V(InpXDecayBars=b, InpXDecayR=r)))
    for f in (0,17,18,20,21): print("fri",f, st(V(InpXFriHour=f)))
    for s in (19,20): print("sessTo",s, st(V(InpSessTo=s)))
    for sl in (15,18,20,30,35): print("slUsd",sl, st(V(InpSlUsd=sl)))
    for tp in (15,25,30,40): print("tp",tp, st(V(InpFixTpPips=tp)))
