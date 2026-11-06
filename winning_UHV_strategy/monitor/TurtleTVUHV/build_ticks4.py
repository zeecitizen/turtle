"""build_ticks4.py - the 2022-2026 Blueberry tick file as binary arrays (epoch seconds f64, bid f64, ask f64).
A row updates only one side: the other side keeps its last value (MT5's quote rule). py build_ticks4.py"""
import numpy as np, pandas as pd
from pathlib import Path
SRC = Path("C:/Users/zeesh/turtle/data_15min_2015_onwards_xauusd/XAUUSD_202201030100_202610232021.csv")
OUT = Path(__file__).resolve().parent / "simdata"
ft = {k: open(OUT / f"ticks4_{k}.bin", "wb") for k in ("t", "bid", "ask")}
lb, la = np.nan, np.nan
n = 0
for ch in pd.read_csv(SRC, sep="\t", usecols=[0, 1, 2, 3], chunksize=5_000_000, dtype={"<DATE>": str, "<TIME>": str}):
    d = pd.to_datetime(ch["<DATE>"] + " " + ch["<TIME>"], format="%Y.%m.%d %H:%M:%S.%f")
    t = (d - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy(np.float64)
    b = ch["<BID>"].to_numpy(np.float64); a = ch["<ASK>"].to_numpy(np.float64)
    b = pd.Series(b).ffill().to_numpy(); a = pd.Series(a).ffill().to_numpy()
    if np.isnan(b[0]): b = np.where(np.isnan(b), lb, b)
    if np.isnan(a[0]): a = np.where(np.isnan(a), la, a)
    ok = ~(np.isnan(b) | np.isnan(a))                  # ticks before the first full quote are dropped
    t, b, a = t[ok], b[ok], a[ok]
    if len(t):
        lb, la = b[-1], a[-1]
        ft["t"].write(t.tobytes()); ft["bid"].write(b.tobytes()); ft["ask"].write(a.tobytes())
    n += len(ch)
    print(n, flush=True)
for f in ft.values(): f.close()
print("done", n, flush=True)
