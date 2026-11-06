"""build_year_ticks.py - Blueberry tick file -> the 1-minute tester's files, for any year range (default 2026).
Writes simdata/<tag>.npz (minute candles), <tag>_sec.npz (per-second bid/ask OHLC + tick ms of highs/lows),
<tag>_tHL.npz (tick high/low second per minute), <tag>_hford.npy (tick order), <tag>_spread.npy (mean spread per minute).
Ticks are read once; a second or minute that spans two chunks is carried over.
py build_year_ticks.py <src.csv> <tag> <from YYYY.MM.DD> <to YYYY.MM.DD>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
SIM = Path(__file__).resolve().parent / "simdata"


def main(src, tag, frm, to):
    # per-second accumulators, flushed when a second is complete
    secs = []        # rows: t, bo, bc, bh, bl, ao, ac, ah, al, n, bh_ms, bl_ms, ah_ms, al_ms
    carry = None     # the open second (list form)
    for ch in pd.read_csv(src, sep="\t", usecols=[0, 1, 2, 3], chunksize=5_000_000, dtype={"<DATE>": str, "<TIME>": str}):
        ch = ch[(ch["<DATE>"] >= frm) & (ch["<DATE>"] <= to)]
        if ch.empty:
            continue
        d = pd.to_datetime(ch["<DATE>"] + " " + ch["<TIME>"], format="%Y.%m.%d %H:%M:%S.%f")
        t = (d - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
        sec = np.floor(t).astype(np.int64)
        ms = np.round((t - sec) * 1000).astype(np.int32)
        b = ch["<BID>"].to_numpy(np.float64); a = ch["<ASK>"].to_numpy(np.float64)
        df = pd.DataFrame({"s": sec, "ms": ms, "b": b, "a": a})
        if carry is not None:
            df = pd.concat([carry, df], ignore_index=True)
        last = df["s"].iloc[-1]
        done = df[df["s"] < last]
        carry = df[df["s"] == last]
        if done.empty:
            continue
        g = done.groupby("s", sort=True)
        bo = g["b"].first(); bc = g["b"].last(); bh = g["b"].max(); bl = g["b"].min()
        ao = g["a"].first(); ac = g["a"].last(); ah = g["a"].max(); al = g["a"].min()
        n = g.size()
        # ms of the first tick that reaches the second's high / low
        bh_ms = done.loc[done["b"] == done["s"].map(bh)].groupby("s")["ms"].first()
        bl_ms = done.loc[done["b"] == done["s"].map(bl)].groupby("s")["ms"].first()
        ah_ms = done.loc[done["a"] == done["s"].map(ah)].groupby("s")["ms"].first()
        al_ms = done.loc[done["a"] == done["s"].map(al)].groupby("s")["ms"].first()
        secs.append(pd.DataFrame({"t": bo.index, "bo": bo.values, "bc": bc.values, "bh": bh.values, "bl": bl.values,
                                  "ao": ao.values, "ac": ac.values, "ah": ah.values, "al": al.values, "n": n.values,
                                  "bh_ms": bh_ms.reindex(bo.index).values, "bl_ms": bl_ms.reindex(bo.index).values,
                                  "ah_ms": ah_ms.reindex(bo.index).values, "al_ms": al_ms.reindex(bo.index).values}))
        print("chunk done, seconds so far", sum(len(s) for s in secs), flush=True)
    if carry is not None and not carry.empty:
        # the final open second
        s0 = carry
        g = s0.groupby("s")
        bo = g["b"].first(); bc = g["b"].last(); bh = g["b"].max(); bl = g["b"].min()
        ao = g["a"].first(); ac = g["a"].last(); ah = g["a"].max(); al = g["a"].min()
        n = g.size()
        secs.append(pd.DataFrame({"t": bo.index, "bo": bo.values, "bc": bc.values, "bh": bh.values, "bl": bl.values,
                                  "ao": ao.values, "ac": ac.values, "ah": ah.values, "al": al.values, "n": n.values,
                                  "bh_ms": 0, "bl_ms": 0, "ah_ms": 0, "al_ms": 0}))
    S = pd.concat(secs, ignore_index=True)
    np.savez_compressed(SIM / f"{tag}_sec.npz", **{k: S[k].to_numpy() for k in S.columns})
    print("seconds", len(S), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
