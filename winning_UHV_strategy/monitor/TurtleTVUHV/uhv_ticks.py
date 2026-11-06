"""uhv_ticks.py - PrimeXBT's whole EUR/USD tick stream, read once from the tick export and kept in simdata/uhv_ticks_all.npz, so the UHV
engine (uhv_engine.py) can replay any exit on every setup - for as long as the round lasts (Zee 2026-11-05: LAWS.md stops 5-7 pips beyond
the retracement, 1:2 targets: rounds run for hours, not the 2-pip game's minutes).

Arrays: t (UTC seconds, float64), bid, ask (float32: 1e-7 precision on 1.1x prices). Run: py monitor/TurtleTVUHV/uhv_ticks.py"""
import datetime as dt
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TICKS = Path(r"C:\Users\zeesh\turtle\EURUSD_tick_data\PrimeXBTMT5Downloads\EURUSDp_202603060000_202611042359.csv")
OUT = HERE / "simdata" / "uhv_ticks_all.npz"


def build():
    n_est = 28_000_000
    T = np.empty(n_est, dtype=np.float64); B = np.empty(n_est, dtype=np.float32); A = np.empty(n_est, dtype=np.float32)
    n, bid, ask = 0, None, None
    with TICKS.open(encoding="utf-8", errors="replace") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4:
                continue
            if p[2]:
                bid = float(p[2])
            if p[3]:
                ask = float(p[3])
            if bid is None or ask is None:
                continue
            d, t = p[0], p[1]
            ts = dt.datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]), int(t[0:2]), int(t[3:5]), int(t[6:8]),
                             int((t[9:12] or "0").ljust(3, "0")) * 1000, tzinfo=dt.timezone.utc).timestamp()
            if n >= len(T):
                T = np.resize(T, n + 2_000_000); B = np.resize(B, n + 2_000_000); A = np.resize(A, n + 2_000_000)
            T[n], B[n], A[n] = ts, bid, ask
            n += 1
    np.savez(OUT, t=T[:n], bid=B[:n], ask=A[:n])
    return n


def load():
    if not OUT.exists():
        build()
    z = np.load(OUT)
    return {k: z[k] for k in z.files}


if __name__ == "__main__":
    print("ticks:", build())
