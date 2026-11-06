import time
t0 = time.time()
from common import run, summ, SPLIT
print("import", round(time.time() - t0, 1), flush=True)
r = run()
print("first run", r["secs"], summ(r), "train", summ(r, hi=SPLIT), "test", summ(r, lo=SPLIT), "ghosts", r["ghosts"], flush=True)
r = run()
print("second run", r["secs"], summ(r), flush=True)
r = run({"InpUhvSafeErMax": "0.45"})
print("tight run", r["secs"], summ(r), flush=True)
