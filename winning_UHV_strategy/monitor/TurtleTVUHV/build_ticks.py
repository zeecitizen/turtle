"""build_ticks.py - the 2026 Blueberry tick file as three binary arrays (tester clock, seconds+ms as float64, bid, ask float32),
read in place by the engine's tick-level exit fills. py build_ticks.py"""
import numpy as np, pandas as pd
from datetime import datetime, timezone
from pathlib import Path
SRC = Path("C:/Users/zeesh/turtle/data_15min_2015_onwards_xauusd/XAUUSD_BB_202601020100_202610162357.csv")
OUT = Path(__file__).resolve().parent / "simdata"
ft = [open(OUT / f"ticks2026_{k}.bin", "wb") for k in ("t", "bid", "ask")]
n = 0
for ch in pd.read_csv(SRC, sep="\t", usecols=[0, 1, 2, 3], chunksize=5_000_000, dtype={"<DATE>": str, "<TIME>": str}):
    d = pd.to_datetime(ch["<DATE>"] + " " + ch["<TIME>"], format="%Y.%m.%d %H:%M:%S.%f", utc=True)
    t = (d - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().to_numpy()   # epoch seconds (UTC); the engine compares in this clock
    ft[0].write(t.astype(np.float64).tobytes())
    ft[1].write(ch["<BID>"].to_numpy(np.float64).tobytes())
    ft[2].write(ch["<ASK>"].to_numpy(np.float64).tobytes())
    n += len(ch)
    print(n, flush=True)
for f in ft: f.close()
print("done", n)
