from grid import st, V, INP
for m in (2,3,4,5,6): print("atrSL",m, st(V(InpSlMode=1, InpSlAtrMult=m)))
print("fri0+sess20", st(V(InpXFriHour=0, InpSessTo=20)))
print("sl20+fri0", st(V(InpSlUsd=20, InpXFriHour=0)))
print("year1 BASE", st(INP, ds="year1"))
print("year1 sl15", st(V(InpSlUsd=15), ds="year1"))
