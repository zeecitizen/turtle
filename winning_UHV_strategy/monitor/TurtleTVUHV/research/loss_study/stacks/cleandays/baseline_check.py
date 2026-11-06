import time, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import uhv_engine as U
B = C.base_inputs()
t0 = time.time(); rows, su, cnt = U.simulate(B); t1 = time.time()
s = C.score(rows)
print("first simulate s", round(t1 - t0, 1))
for p in ("train", "test", "all"):
    x = s[p]; print(p, x["n"], x["L"], x["wr"], "days", x["days"], "clean", x["clean"], x["clean_pct"], "net", x["net"])
t0 = time.time(); rows2, _, _ = U.simulate(B); print("second simulate s", round(time.time() - t0, 2))
t0 = time.time(); rows3, _, c3 = U.simulate(dict(B, InpUhvSRPips="3")); print("with a filter s", round(time.time() - t0, 2), c3)
t0 = time.time(); rows3, _, c3 = U.simulate(dict(B, InpUhvSRPips="2")); print("with a filter again s", round(time.time() - t0, 2))
s3 = C.score(rows3)
for p in ("train", "test", "all"):
    x = s3[p]; print(p, x["n"], x["L"], x["wr"], "days", x["days"], "clean", x["clean"], x["clean_pct"], "net", x["net"])
print(cnt)
