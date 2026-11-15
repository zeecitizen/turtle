"""append_ticks.py - extend the Turtle TV UHV data (simdata/year1.npz bars + simdata/uhv_ticks_all.npz ticks) with a newer PrimeXBT tick export.

Zee 2026-11-10: "i saved the latest ticks here.. can u append this data somehow so our chart at http://127.0.0.1:8774/ shows the bars till today".
Recipe = the one year1 was built with (verified on 4,413 overlap minutes, zero diff): minute bars from the BID (open/high/low/close), v1 = tick count,
sp1 = mean ask-bid of the minute rounded to 1e-6; ATR/ADX (sim._atr_adx) recomputed over the whole series; the export's final, partial minute is dropped.
Ticks: blank bid/ask = unchanged (as uhv_ticks.py). Only minutes / ticks AFTER the current last bar are appended, so an export that overlaps is fine.
Afterwards: stale caches are cleared (det_cache/setups_*.json are keyed on detector values only; uhv_setups.json rebuilds itself on the server's
first /api/uhv_setups request because year1.npz is newer), the year1_*.npy memory maps are removed (the server recreates them).

    STOP the 8774 server first (it holds the .npy maps open), then:
    py monitor/TurtleTVUHV/append_ticks.py <EURUSDp_YYYYMMDDhhmm_YYYYMMDDhhmm.csv>
    then start the server again and open http://127.0.0.1:8774/api/uhv_setups?ds=year1 once (about 75 s) before reloading the chart.
"""
import datetime as dt, glob, os, shutil, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import sim  # noqa: E402
SD = HERE / "simdata"


def parse(src):
    T, B, A = [], [], []; bid = ask = None
    with open(src, encoding="utf-8", errors="replace") as f:
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
            T.append(dt.datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]), int(t[0:2]), int(t[3:5]), int(t[6:8]), int((t[9:12] or "0").ljust(3, "0")) * 1000,
                                 tzinfo=dt.timezone.utc).timestamp()); B.append(bid); A.append(ask)
    T, B, A = np.array(T), np.array(B), np.array(A)
    m = (T // 60).astype(np.int64) * 60
    u, first = np.unique(m, return_index=True); last = np.r_[first[1:], len(m)] - 1
    bars = dict(t=u, o=B[first], c=B[last], h=np.array([B[a:b + 1].max() for a, b in zip(first, last)]), l=np.array([B[a:b + 1].min() for a, b in zip(first, last)]),
                v=(last - first + 1).astype(float), sp=np.array([np.round((A[a:b + 1] - B[a:b + 1]).mean(), 6) for a, b in zip(first, last)]))
    return T, B, A, bars


def main(src):
    try:
        for f in glob.glob(str(SD / "year1_*.npy")):
            os.remove(f)
    except PermissionError:
        sys.exit("the 8774 server holds simdata/year1_*.npy open - stop it first")
    T, B, A, N = parse(src)
    z = np.load(SD / "year1.npz", allow_pickle=True); D = {k: z[k] for k in z.files}; z.close()
    t_last = int(D["t1"][-1]); last_full = int(T[-1] // 60) * 60 - 60
    keep = (N["t"] > t_last) & (N["t"] <= last_full)
    if not keep.any():
        sys.exit(f"nothing to append: year1 already ends {dt.datetime.fromtimestamp(t_last, dt.UTC)}")
    bk = SD / "backup"; bk.mkdir(exist_ok=True)
    shutil.copyfile(SD / "year1.npz", bk / "year1_before_append.npz")
    t1 = np.r_[D["t1"], N["t"][keep].astype(np.int64)]
    o, h, l, c = (np.r_[D[k + "1"], N[k][keep]] for k in "ohlc")
    v, sp = np.r_[D["v1"], N["v"][keep]], np.r_[D["sp1"], N["sp"][keep]]
    atr, adx = sim._atr_adx(o, h, l, c, 14)
    k1, first, m2c, roll = sim._timeline(t1, t1)
    np.savez_compressed(SD / "year1.npz", t15=t1, hr15=((t1 // 3600) % 24).astype(np.int64), o15=o, h15=h, l15=l, c15=c, ef=np.zeros(len(t1)), es=np.zeros(len(t1)),
                        adx=adx, atr=atr, t1=t1, o1=o, h1=h, l1=l, c1=c, sp1=sp, k1=k1, first1=first, m2c=m2c, roll=roll, events=D["events"], v1=v)
    print(f"bars +{int(keep.sum())} -> {len(t1)}, last {dt.datetime.fromtimestamp(int(t1[-1]), dt.UTC)}")
    zt = np.load(SD / "uhv_ticks_all.npz"); tt, tb, ta = zt["t"], zt["bid"], zt["ask"]; zt.close()
    m = (T > tt[-1]) & (T < last_full + 60)
    os.replace(SD / "uhv_ticks_all.npz", bk / "uhv_ticks_all_before_append.npz")
    np.savez(SD / "uhv_ticks_all.npz", t=np.r_[tt, T[m]].astype(np.float64), bid=np.r_[tb, B[m]].astype(np.float32), ask=np.r_[ta, A[m]].astype(np.float32))
    print(f"ticks +{int(m.sum())} -> {len(tt) + int(m.sum())}")
    n = 0
    for f in glob.glob(str(SD / "det_cache" / "setups_*.json")):
        os.remove(f); n += 1
    print(f"det_cache cleared ({n}); backups in simdata/backup; start the server and GET /api/uhv_setups?ds=year1 once")


if __name__ == "__main__":
    main(sys.argv[1])
