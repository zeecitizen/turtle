"""sim.py - the Turtle TV Tester: Saad_strategy_15min v1.27's rules as a numba-compiled loop over the year (Zee 2026-10-20: "we want a faster
few seconds running optimizer to constantly optimize settings and view their result in turtle tv chart" ... "its ok since we have our own chart
we can rely on python to build an optimizer. this is diff from backtests in python. its about finding best settings").

CLAUDE.md still holds: this engine GENERATES settings; MT5's Strategy Tester (Turtle TV's lower section) is what PROMOTES them. Every number from
here is labelled "Turtle TV Tester" and is checked against MT5 (validate.py: setups, entries, exits, and the RANKING of different settings).

Datasets (simdata/*.npz):
  year - the viewer EA's export of the year on Blueberry real ticks: every M15 candle with the EA's own EMA / ATR / ADX + every M1 candle with
         its spread (build_dataset).
  tv   - TradingView's own 15-min candles (the bridge file, Aug 3 ->) with the same Blueberry M1 candles inside them; candles after the tick data
         ends are one step each (build_tv_dataset). Zee 2026-10-20: "find out why turtle Tv shows different result 62.5% on october and fix it".
The loop walks the M1 candles in MT5's "1 minute OHLC" order (open, low, high, close for a rising minute; open, high, low, close for a falling
one) and makes v1.27's decisions in the EA's order: day-close check, stop / target, then at a new 15-min candle the close-back exits, the waiting
setup's countdown and a new setup, then the break entry.
Extras (X vector, all off by default = v1.27 in MT5): the TradingView chart's own rules (busy-at-close, BUY target above the entry, fixed spread,
no swap, blind inside the entry candle before its 1-minute data, setup warm-up) and the stress tests' execution faults (reversed logic, slippage,
stop overshoot, latency, wider spread, target trade-through, spread-spike rejection, worst-case order inside a minute)."""
import os

os.environ.setdefault("NUMBA_CPU_NAME", "generic")   # this laptop's ARM CPU crashes LLVM's scheduler unless numba targets a generic CPU
from datetime import datetime                          # noqa: E402
from pathlib import Path                               # noqa: E402

import numpy as np                                     # noqa: E402
from numba import njit                                 # noqa: E402

HERE = Path(__file__).resolve().parent
SIMDATA = HERE / "simdata"
DATA = SIMDATA / "year.npz"
COMMON = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
SWAP_LONG, SWAP_SHORT = -61.6, 40.5      # $ per lot per night on Blueberry XAUUSD (measured from MT5's exits); Wednesday night x3
TV_M1_FROM = int((datetime(2026, 10, 12, 1, 1) - datetime(1970, 1, 1)).total_seconds())   # server time: TradingView's 1-minute data starts here

# the parameter vector: EA input -> index
NAMES = ["InpEmaFast", "InpEmaSlow", "InpWickMin", "InpBodyMax", "InpNoseMax", "InpUsePin", "InpPinDir", "InpPinColor", "InpMarubozu", "InpMaruBody",
         "InpHammer", "InpStar", "InpHamRatio", "InpHamNose", "InpMinRangeAtr", "InpLongRule", "InpShortLine", "InpTouchMode", "InpTouchPips",
         "InpLongExitAbove", "InpBreakBars", "InpBreakPips", "InpSlMode", "InpSlPips", "InpSlAtrMult", "InpSlUsd", "InpMaxRiskUsd", "InpSessFrom",
         "InpSessTo", "InpAdxMin", "InpAtrMinUsd", "InpAtrMaxUsd", "InpRangeLook", "InpRangeLookS", "InpBandOff", "InpExitMode", "InpCloseLossMins",
         "InpLots", "InpBuys", "InpSells", "InpGapCancel"]
IX = {n: i for i, n in enumerate(NAMES)}
# the extras vector
XNAMES = ["no_entry_exit_bar", "long_ema_above", "fixed_spread", "swap", "blind_until", "warm_k", "reverse", "slip_entry", "slip_exit", "sl_overshoot",
          "spread_mult", "latency", "tp_through", "reject_mult", "median_spread", "worst_case"]
XDEFAULT = {"swap": 1.0, "spread_mult": 1.0}
# TradingView's way: the Saad indicator's own rules on its own candles
CHART_RULES = {"no_entry_exit_bar": 1.0, "long_ema_above": 1.0, "fixed_spread": 0.17, "swap": 0.0}


def _b(v):
    return 1.0 if str(v).strip().lower() == "true" else 0.0 if str(v).strip().lower() == "false" else float(v)


def pvec(inputs):
    """EA inputs (strings, as in a Turtle TV run / ea_defaults) -> (parameter vector, BUY boxes, SELL boxes)."""
    P = np.array([_b(inputs[n]) for n in NAMES], dtype=np.float64)
    bb = np.array([1 if ch != "0" else 0 for ch in str(inputs["InpBandsB"]).ljust(21, "1")[:21]], dtype=np.int64)
    bs = np.array([1 if ch != "0" else 0 for ch in str(inputs["InpBandsS"]).ljust(21, "1")[:21]], dtype=np.int64)
    return P, bb, bs


def xvec(extra):
    X = np.zeros(len(XNAMES))
    for k, v in dict(XDEFAULT, **(extra or {})).items():
        X[XNAMES.index(k)] = float(v)
    return X


# ---------------------------------------------------------------- data
def _srv(s):
    return datetime.strptime(s.strip(), "%Y.%m.%d %H:%M")


def _ep(d):
    return int((d - datetime(1970, 1, 1)).total_seconds())


def _timeline(t15, t1):
    """k1 (M15 candle of each minute), first1, m2c (seconds to the session's end), roll (swap nights at a new server day)."""
    k1 = np.searchsorted(t15, t1, side="right") - 1
    first = np.ones(len(t1), dtype=np.int64)
    first[1:] = (k1[1:] != k1[:-1]).astype(np.int64)
    day = t1 // 86400
    end = np.zeros(len(t1), dtype=np.int64)
    for d in np.unique(day):
        idx = np.where(day == d)[0]
        end[idx] = t1[idx[-1]] + 60
    roll = np.zeros(len(t1), dtype=np.int64)
    for j in range(1, len(t1)):
        if day[j] != day[j - 1]:
            wd = (int(t1[j - 1]) // 86400 + 3) % 7                    # 1970-01-01 was a Thursday -> 0 = Monday
            roll[j] = 3 if wd == 2 else 0 if wd >= 4 else 1
    return k1, first, end - t1, roll


def build_dataset(tag="simdata"):
    """The viewer EA's export (InpExportM1) -> simdata/year.npz. Server time throughout (Blueberry = New York + 7)."""
    bars = [l.split("\t") for l in (COMMON / f"saadview_{tag}_bars.csv").read_text().splitlines()[1:]]
    m1 = [l.split("\t") for l in (COMMON / f"saadview_{tag}_m1.csv").read_text().splitlines()[1:]]
    ev = (COMMON / f"saadview_{tag}_events.csv").read_text().splitlines()
    seen, B = set(), []
    for f in bars:
        t = _srv(f[0])
        if t not in seen and len(f) >= 9:
            seen.add(t); B.append((_ep(t), t.hour, *[float(x) for x in f[1:9]]))
    B.sort()
    B = np.array(B, dtype=np.float64)
    M = np.array([(_ep(_srv(f[0])), float(f[1]), float(f[2]), float(f[3]), float(f[4]), int(f[5]) * 0.01) for f in m1 if len(f) >= 7], dtype=np.float64)
    M = M[np.argsort(M[:, 0], kind="stable")]
    t15 = B[:, 0].astype(np.int64)
    t1 = M[:, 0].astype(np.int64)
    kk = np.searchsorted(t15, t1, side="right") - 1
    keep = (kk >= 0) & (t1 < t15[np.maximum(kk, 0)] + 900)       # a minute after the last exported candle has no candle (the export writes a candle when the next opens)
    M, t1 = M[keep], t1[keep]
    k1, first, m2c, roll = _timeline(t15, t1)
    SIMDATA.mkdir(exist_ok=True)
    np.savez_compressed(DATA, t15=t15, hr15=B[:, 1].astype(np.int64), o15=B[:, 2], h15=B[:, 3], l15=B[:, 4], c15=B[:, 5], ef=B[:, 6], es=B[:, 7],
                        adx=B[:, 8], atr=B[:, 9], t1=t1, o1=M[:, 1], h1=M[:, 2], l1=M[:, 3], c1=M[:, 4], sp1=M[:, 5], k1=k1, first1=first,
                        m2c=m2c, roll=roll, events=np.array(ev, dtype=object))
    return DATA


def _atr_adx(o, h, l, c, n=14):
    """TradingView's ta.sma(ta.tr(true), 14) (= MT5 iATR) and the indicator's mtAdx() (= MT5 iADX) on these candles."""
    m = len(c)
    tr = np.empty(m)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])
    cs = np.cumsum(tr)
    atr = np.empty(m)
    for i in range(m):
        a = max(0, i - n + 1)
        atr[i] = (cs[i] - (cs[a - 1] if a > 0 else 0.0)) / (i - a + 1)
    k = 2.0 / (n + 1)
    adx = np.zeros(m)
    pdi = ndi = ax = 0.0
    for i in range(m):
        pdm = ndm = 0.0
        if i > 0:
            pdm, ndm = max(h[i] - h[i - 1], 0.0), max(l[i - 1] - l[i], 0.0)
            if pdm > ndm:
                ndm = 0.0
            elif ndm > pdm:
                pdm = 0.0
            else:
                pdm = ndm = 0.0
        pd, nd = (100 * pdm / tr[i], 100 * ndm / tr[i]) if tr[i] != 0 else (0.0, 0.0)
        pdi = pd if i == 0 else pdi + k * (pd - pdi)
        ndi = nd if i == 0 else ndi + k * (nd - ndi)
        s = pdi + ndi
        dx = 100 * abs(pdi - ndi) / s if s != 0 else 0.0
        ax = dx if i == 0 else ax + k * (dx - ax)
        adx[i] = ax
    return atr, adx


def build_tv_dataset(path=None):
    """TradingView's 15-min candles (tv_bars_bridge.py --export, server time) + the Blueberry M1 candles inside them -> simdata/tv.npz.
    TradingView candles after the tick data ends become one step each (one 'minute' = the whole candle, spread 0.17)."""
    path = Path(path or COMMON / "tv_bars_XAUUSD_M15.csv")
    rows = {}
    for line in path.read_text().splitlines():
        f = line.split(",")
        if len(f) >= 5 and f[0][:4].isdigit():
            rows[_ep(_srv(f[0]))] = [float(x) for x in f[1:5]]
    t15 = np.array(sorted(rows), dtype=np.int64)
    B = np.array([rows[t] for t in t15])
    Y = data("year")
    t1, o1, h1, l1, c1, sp1 = Y["t1"], Y["o1"], Y["h1"], Y["l1"], Y["c1"], Y["sp1"]
    m = (t1 >= t15[0])
    t1, o1, h1, l1, c1, sp1 = t1[m], o1[m], h1[m], l1[m], c1[m], sp1[m]
    last = int(t1[-1])
    tail = t15 > last                                               # no tick data yet: one step per candle
    t1 = np.concatenate([t1, t15[tail]])
    o1 = np.concatenate([o1, B[tail, 0]]); h1 = np.concatenate([h1, B[tail, 1]]); l1 = np.concatenate([l1, B[tail, 2]]); c1 = np.concatenate([c1, B[tail, 3]])
    sp1 = np.concatenate([sp1, np.full(int(tail.sum()), 0.17)])
    k1, first, m2c, roll = _timeline(t15, t1)
    atr, adx = _atr_adx(B[:, 0], B[:, 1], B[:, 2], B[:, 3])
    hr = np.array([datetime.utcfromtimestamp(int(t)).hour for t in t15], dtype=np.int64)
    out = SIMDATA / "tv.npz"
    np.savez_compressed(out, t15=t15, hr15=hr, o15=B[:, 0], h15=B[:, 1], l15=B[:, 2], c15=B[:, 3], ef=np.zeros(len(t15)), es=np.zeros(len(t15)),
                        adx=adx, atr=atr, t1=t1, o1=o1, h1=h1, l1=l1, c1=c1, sp1=sp1, k1=k1, first1=first, m2c=m2c, roll=roll,
                        ticks_until=np.array([last]), events=np.array([], dtype=object))
    _D.pop("tv", None)
    return out


_D = {}


def data(name="year"):
    if name not in _D:
        z = np.load(SIMDATA / f"{name}.npz", allow_pickle=True)
        _D[name] = {k: z[k] for k in z.files}
    return _D[name]


def ema(c, n, seed):
    a = 2.0 / (n + 1)
    e = np.empty_like(c)
    e[0] = seed
    for i in range(1, len(c)):
        e[i] = e[i - 1] + a * (c[i] - e[i - 1])
    return e


_EMA = {}


def emas(nf, ns, ds="year"):
    """The EMAs on the M15 closes. 'year': seeded with the EA's own value at the first candle for its default 16 / 32 (MT5 had history before),
    with the first close otherwise. 'tv': seeded with the chart's first close, like TradingView's ta.ema."""
    D = data(ds)
    out = []
    for n, col in ((int(nf), "ef"), (int(ns), "es")):
        key = (ds, n)
        if key not in _EMA:
            seed = D["c15"][0]
            if ds == "year" and n == 16:
                seed = D["ef"][0]
            elif ds == "year" and n == 32:
                seed = D["es"][0]
            _EMA[key] = ema(D["c15"], n, seed)
        out.append(_EMA[key])
    return out


# ---------------------------------------------------------------- the engine
@njit(cache=True)
def _setup_shape(o, h, l, c, atr, P):
    rng = h - l
    if rng <= 0:
        return 0, 0
    if P[14] > 0 and rng < P[14] * atr:
        return 0, 0
    body = abs(c - o)
    up = h - max(o, c)
    lo = min(o, c) - l
    pinBull = body <= P[3] * rng and lo >= P[2] * rng and up <= P[4] * rng
    pinBear = body <= P[3] * rng and up >= P[2] * rng and lo <= P[4] * rng
    isPin = pinBull or pinBear
    hamBull = (not isPin) and lo >= P[12] * body and lo > 0 and up <= P[13] * rng
    hamBear = (not isPin) and up >= P[12] * body and up > 0 and lo <= P[13] * rng
    maru = (not isPin) and (not hamBull) and (not hamBear) and body >= P[9] * rng
    if isPin:
        if P[5] < 0.5:
            return 0, 0
        if P[6] < 0.5:
            return 2, 1
        if P[7] > 0.5 and ((c < o) if pinBull else (c > o)):
            return 0, 0
        return (1 if pinBull else -1), 1
    if hamBull:
        return (1 if P[10] > 0.5 else 0), 2
    if hamBear:
        return (-1 if P[11] > 0.5 else 0), 2
    if maru:
        if P[8] < 0.5:
            return 0, 0
        return (1 if c > o else -1), 3
    return 0, 0


@njit(cache=True)
def _online(o, h, l, c, e, side, P):
    tol = P[18] * 0.1
    if e <= 0:
        return False
    if P[17] < 0.5:
        return l - tol <= e and h + tol >= e
    if side > 0:
        return l - tol <= e and min(o, c) >= e
    return h + tol >= e and max(o, c) <= e


@njit(cache=True)
def _pt(o1, h1, l1, c1, j, q):
    """The price at path point q of minute j (q past 3 walks into the next minutes) - latency."""
    n = o1.shape[0]
    while q > 3 and j + 1 < n:
        q -= 4
        j += 1
    if q > 3:
        q = 3
    if q == 0:
        return o1[j]
    if q == 3:
        return c1[j]
    up = c1[j] >= o1[j]
    if q == 1:
        return l1[j] if up else h1[j]
    return h1[j] if up else l1[j]


@njit(cache=True)
def _rec(out, nt, side, tin, en, sl, tout, xp, lots, swp, bkt, nx, ghost, kin, kout, why):
    if nt < out.shape[0]:
        out[nt, 0] = side; out[nt, 1] = tin; out[nt, 2] = en; out[nt, 3] = sl; out[nt, 4] = tout; out[nt, 5] = xp
        out[nt, 6] = (xp - en) * side * lots * 100 + swp; out[nt, 7] = swp; out[nt, 8] = bkt; out[nt, 9] = nx; out[nt, 10] = ghost
        out[nt, 11] = kin; out[nt, 12] = kout; out[nt, 13] = why
    return nt + 1


@njit(cache=True)
def run(t15, hr15, o15, h15, l15, c15, ef, es, atr, adx, t1, o1, h1, l1, c1, sp1, k1, first1, m2c, roll, P, X, bandB, bandS, out, setups, stats):
    """out rows: side, entry_t, entry, sl, exit_t, exit, pnl, swap, bucket, nxE, ghost, entry_k15, exit_k15, reason (1 stop 2 target 3 close-back 4 day close)
       setups rows: k15, side, kind   stats: [n_setups, no_break, risk, adx, atr_band, band_skip, gap, spread_reject]"""
    n1 = t1.shape[0]
    af = 2.0 / (P[0] + 1.0)
    asl = 2.0 / (P[1] + 1.0)
    lots = P[37]
    pip = 0.1
    lat = int(X[11])
    nt = 0
    ns = 0
    pSide = 0
    pHigh = 0.0
    pLow = 0.0
    pLeft = 0
    pK = -1
    pos = 0
    en = 0.0
    sl = 0.0
    nx = 0
    posK = -1
    posT = 0
    swp = 0.0
    bkt = -1
    gh = 0
    gEn = 0.0
    gSl = 0.0
    gNx = 0
    gK = -1
    gT = 0
    gB = -1
    busy0 = False
    pts = np.empty(4)
    for j in range(n1):
        k = k1[j]
        spr = X[2] if X[2] > 0 else sp1[j] * X[10]
        o = o1[j]
        if roll[j] > 0 and pos != 0 and X[3] > 0.5:
            swp += (-61.6 if pos > 0 else 40.5) * lots * roll[j]
        pts[0] = o
        sd0 = pos if pos != 0 else gh
        if X[15] > 0.5 and sd0 != 0:                        # worst case: the adverse extreme first
            pts[1] = l1[j] if sd0 > 0 else h1[j]
            pts[2] = h1[j] if sd0 > 0 else l1[j]
        elif c1[j] >= o:
            pts[1] = l1[j]
            pts[2] = h1[j]
        else:
            pts[1] = h1[j]
            pts[2] = l1[j]
        pts[3] = c1[j]
        blind = t1[j] < X[4]
        for q in range(4):
            cur = pts[q]
            prv = pts[q - 1] if q > 0 else cur
            tq = t1[j] + q * 15
            if q == 0 and first1[j] == 1:
                busy0 = pos != 0 or gh != 0                 # still in a trade when the last candle closed (the chart's busy rule)
            # 1. DayCloseCheck: InpCloseLossMins before the session's end, a trade in loss is shut
            inwin = (not blind) and P[36] > 0 and (m2c[j] < (P[36] + 1) * 60 or (m2c[j] == (P[36] + 1) * 60 and q > 0))
            if inwin and pos != 0:
                if (cur < en) if pos > 0 else (cur + spr > en):
                    xp = (cur if pos > 0 else cur + spr) - pos * X[8]
                    nt = _rec(out, nt, pos, posT, en, sl, tq, xp, lots, swp, bkt, nx, 0, posK, k, 4)
                    pos = 0
            if inwin and gh != 0:
                if (cur < gEn) if gh > 0 else (cur + spr > gEn):
                    xp = cur if gh > 0 else cur + spr
                    nt = _rec(out, nt, gh, gT, gEn, gSl, tq, xp, lots, 0.0, gB, gNx, 1, gK, k, 4)
                    gh = 0
            # 2. stop / target (ManageTick, GhostTick) - also run again right after an entry inside this segment
            for rep in range(2):
                for who in range(2):
                    sd = pos if who == 0 else gh
                    if sd == 0:
                        continue
                    if blind and (posK if who == 0 else gK) == k:
                        continue                                  # the chart cannot see inside its entry candle here
                    e_ = en if who == 0 else gEn
                    s_ = sl if who == 0 else gSl
                    n_ = nx if who == 0 else gNx
                    xp = 0.0
                    hit = False
                    code = 1
                    if sd > 0:
                        if cur <= s_:
                            hit = True
                            xp = (s_ if prv > s_ else cur) - X[9]
                        elif n_ > 0 and k >= 1:
                            ep = ef[k - 1] if n_ == 9 else es[k - 1]
                            if cur >= ep + X[12] and (X[1] < 0.5 or ep > e_):
                                hit = True
                                code = 2
                                xp = ep if prv < ep else cur
                    else:
                        if cur + spr >= s_:
                            hit = True
                            xp = (s_ if prv + spr < s_ else cur + spr) + X[9]
                        elif n_ > 0 and k >= 1:
                            a_ = af if n_ == 9 else asl
                            ep = ef[k - 1] if n_ == 9 else es[k - 1]
                            thr = ep - spr / (1.0 - a_)
                            if cur <= thr - X[12]:
                                hit = True
                                code = 2
                                xp = (thr if prv > thr else cur) + spr
                    if hit:
                        if code == 2 and lat > 0:
                            p_ = _pt(o1, h1, l1, c1, j, q + lat)
                            xp = p_ if sd > 0 else p_ + spr
                        if who == 0:
                            xp -= sd * X[8]
                            nt = _rec(out, nt, sd, posT, e_, s_, tq, xp, lots, swp, bkt, n_, 0, posK, k, code)
                            pos = 0
                        else:
                            nt = _rec(out, nt, sd, gT, e_, s_, tq, xp, lots, 0.0, gB, n_, 1, gK, k, code)
                            gh = 0
                # 3. the new 15-min candle (first tick): close-back exits, countdown, setup on the candle that closed
                if rep == 0 and q == 0 and first1[j] == 1 and k >= 1:
                    i = k - 1
                    for who in range(2):
                        sd = pos if who == 0 else gh
                        n_ = nx if who == 0 else gNx
                        kk = posK if who == 0 else gK
                        if sd != 0 and n_ < 0 and kk < i:
                            e_ce = ef[i] if n_ == -1 else es[i]
                            if (c15[i] < e_ce) if sd > 0 else (c15[i] > e_ce):
                                p_ = _pt(o1, h1, l1, c1, j, lat) if lat > 0 else cur
                                xp = p_ if sd > 0 else p_ + spr
                                if who == 0:
                                    nt = _rec(out, nt, sd, posT, en, sl, tq, xp - sd * X[8], lots, swp, bkt, n_, 0, kk, k, 3)
                                    pos = 0
                                else:
                                    nt = _rec(out, nt, sd, gT, gEn, gSl, tq, xp, lots, 0.0, gB, n_, 1, kk, k, 3)
                                    gh = 0
                    if pSide != 0:
                        if P[40] > 0.5 and t15[k] - t15[i] > 1350:
                            pSide = 0
                            stats[6] += 1
                        else:
                            pLeft -= 1
                            if pLeft <= 0:
                                pSide = 0
                                stats[1] += 1
                    # DetectSetup on candle i
                    shape, kind = _setup_shape(o15[i], h15[i], l15[i], c15[i], atr[i], P)
                    hr = hr15[i]
                    if shape != 0 and hr >= P[27] and hr < P[28] and i >= X[5]:
                        e9 = ef[i]
                        e50 = es[i]
                        on9 = _online(o15[i], h15[i], l15[i], c15[i], e9, 1, P)
                        on50 = _online(o15[i], h15[i], l15[i], c15[i], e50, 1, P)
                        rulesOk = P[15] != 1 and on9 and not (P[19] > 0.5 and e50 <= h15[i])
                        invOk = P[15] != 0 and on50 and not (P[19] > 0.5 and e9 <= h15[i])
                        if P[16] == 0:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e50, -1, P)
                        elif P[16] == 1:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e9, -1, P)
                        else:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e50, -1, P) or _online(o15[i], h15[i], l15[i], c15[i], e9, -1, P)
                        longOk = P[38] > 0.5 and (rulesOk or invOk) and (shape == 1 or (shape == 2 and ((not shortLine) or c15[i] >= o15[i])))
                        shortOk = P[39] > 0.5 and shortLine and (shape == -1 or shape == 2) and not longOk
                        free = pos == 0 and gh == 0 and pSide == 0 and not (X[0] > 0.5 and busy0)
                        if (longOk or shortOk) and free:
                            pSide = 1 if longOk else -1
                            pHigh = h15[i]
                            pLow = l15[i]
                            pLeft = int(P[20])
                            pK = i
                            if ns < setups.shape[0]:
                                setups[ns, 0] = i; setups[ns, 1] = pSide; setups[ns, 2] = kind
                            ns += 1
                            stats[0] += 1
                # 4. TryEntry: the break of the setup candle (judged on the bid)
                if rep == 0 and pSide != 0 and pos == 0 and gh == 0 and k > pK:
                    lvl = pHigh + P[21] * pip if pSide > 0 else pLow - P[21] * pip
                    crossed = cur > lvl if pSide > 0 else cur < lvl
                    if crossed:
                        if pSide > 0:
                            be = lvl + 0.01 if prv <= lvl else cur
                        else:
                            be = lvl - 0.01 if prv >= lvl else cur
                        side = pSide
                        pSide = 0
                        look = int(P[32]) if side > 0 else int(P[33])
                        hi = -1e18
                        lo = 1e18
                        for s in range(1, look + 1):
                            if k - s >= 0:
                                hi = max(hi, h15[k - s])
                                lo = min(lo, l15[k - s])
                        px = max(lvl + 0.01, o15[k]) if side > 0 else min(lvl - 0.01, o15[k])
                        chase = 50.0
                        if hi > lo:
                            chase = ((px - lo) / (hi - lo) if side > 0 else (hi - px) / (hi - lo)) * 100.0
                        bk = 20 if chase > 100 else (0 if chase <= 0 else min(int(np.floor(chase / 5.0)), 19))
                        off = (bandB[bk] == 0) if side > 0 else (bandS[bk] == 0)
                        if off and P[34] < 0.5:
                            stats[5] += 1
                        elif X[13] > 0 and spr > X[13] * X[14]:
                            stats[7] += 1                         # spread spike: the order is refused
                        else:
                            ts_ = -side if X[6] > 0.5 else side   # reversed logic: the opposite trade on the same signal
                            if lat > 0:
                                be = _pt(o1, h1, l1, c1, j, q + lat)
                            e_ = (be + spr if ts_ > 0 else be) + ts_ * X[7]
                            a_ = atr[k - 1]
                            if P[22] == 1:
                                s_ = e_ - P[24] * a_ if ts_ > 0 else e_ + P[24] * a_
                            elif P[22] == 2:
                                s_ = e_ - P[25] if ts_ > 0 else e_ + P[25]
                            else:
                                s_ = pLow - P[23] * pip if ts_ > 0 else pHigh + P[23] * pip
                            if P[26] > 0 and abs(e_ - s_) > P[26]:
                                stats[2] += 1
                            elif P[29] > 0 and adx[k - 1] < P[29]:
                                stats[3] += 1
                            elif (P[30] > 0 and a_ < P[30]) or (P[31] > 0 and a_ > P[31]):
                                stats[4] += 1
                            else:
                                n_ = -2
                                if P[35] == 1:
                                    l9 = ef[k - 1] + af * (be - ef[k - 1])
                                    l50 = es[k - 1] + asl * (be - es[k - 1])
                                    b9 = l9 > e_ if ts_ > 0 else l9 < e_
                                    b50 = l50 > e_ if ts_ > 0 else l50 < e_
                                    if b9 and b50:
                                        n_ = 9 if abs(l9 - e_) <= abs(l50 - e_) else 50
                                    elif b9:
                                        n_ = 9
                                    elif b50:
                                        n_ = 50
                                    else:
                                        n_ = -1
                                if off:
                                    gh = ts_; gEn = e_; gSl = s_; gNx = n_; gK = k; gT = tq; gB = bk + (0 if side > 0 else 21)
                                else:
                                    pos = ts_; en = e_; sl = s_; nx = n_; posK = k; posT = tq; swp = 0.0; bkt = bk + (0 if side > 0 else 21)
                                prv = be                                  # the rest of this move happens after the entry
                                continue
                break
    return nt, ns


def simulate(inputs, ds="year", chart=False, **extra):
    """Run the year with these EA inputs -> (trades, setups, stats). ds 'year' (Blueberry MT5 candles) or 'tv' (TradingView's candles);
    chart=True = the TradingView indicator's own rules (and its warm-up on 'tv'); extra = any X switch (see XNAMES)."""
    D = data(ds)
    P, bb, bs = pvec(inputs)
    ef, es = emas(P[0], P[1], ds)
    ex = dict(CHART_RULES) if chart else {}
    if ds == "tv":
        ex["warm_k"] = 2 * P[1] + 19                                  # the indicator detects setups from bar_index >= iSlow * 2 + 19
    ex.update(extra)
    X = xvec(ex)
    out = np.zeros((6000, 14))
    setups = np.zeros((40000, 3))
    stats = np.zeros(8)
    nt, ns = run(D["t15"], D["hr15"], D["o15"], D["h15"], D["l15"], D["c15"], ef, es, D["atr"], D["adx"], D["t1"], D["o1"], D["h1"], D["l1"],
                 D["c1"], D["sp1"], D["k1"], D["first1"], D["m2c"], D["roll"], P, X, bb, bs, out, setups, stats)
    return out[:nt], setups[:ns], dict(zip(["setups", "no_break", "risk", "adx", "atr_band", "band_skip", "gap", "spread_reject"], stats.astype(int).tolist()))


def score(tr, min_trades=40):
    """Stats of the REAL trades (ghosts excluded): net, PF, WR, trades, max drawdown on closed trades, net / DD."""
    r = tr[tr[:, 10] == 0]
    r = r[np.argsort(r[:, 4])]
    n = len(r)
    if n == 0:
        return {"n": 0, "net": 0.0, "pf": 0.0, "wr": 0.0, "dd": 0.0, "ret_dd": -1e9}
    p = r[:, 6]
    gw, gl = p[p > 0].sum(), -p[p <= 0].sum()
    eq = np.cumsum(p)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq))
    net = float(p.sum())
    return {"n": n, "net": round(net, 2), "pf": round(float(gw / gl), 3) if gl > 0 else 99.0, "wr": round(float(100.0 * (p > 0).mean()), 1),
            "dd": round(dd, 2), "ret_dd": (net / max(dd, 1.0)) if n >= min_trades else -1e9 + n}


if __name__ == "__main__":
    import sys
    import time
    if "--build" in sys.argv:
        print("dataset:", build_dataset())
    if "--build-tv" in sys.argv:
        print("dataset:", build_tv_dataset())
    sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
    import axi_rig
    dfl = axi_rig.ea_defaults("Saad_strategy_15min")
    t0 = time.time(); tr, su, st = simulate(dfl); t1 = time.time()
    tr, su, st = simulate(dfl); t2 = time.time()
    print(f"first call {t1 - t0:.2f}s (compile), then {1000 * (t2 - t1):.1f} ms per year")
    print("v1.27 defaults:", score(tr), st)


def build_m15_dataset(path=r"C:\Users\zeesh\turtle\data_15min_2015_onwards_xauusd\XAUUSD_M15_201502040000_202610200300.csv", frm="2022.12.29"):
    """Zee 2026-10-20: the Blueberry M15 export (MT5 'Export bars', tab separated). Only real 15-minute candles (from Dec 29 2022; earlier rows are
    one candle a day). No 1-minute data: each candle is one step walked open, low, high, close (MT5's OHLC order) -> simdata/m15.npz."""
    rows = []
    for line in Path(path).read_text().splitlines()[1:]:
        f = line.split("\t")
        if len(f) >= 9 and f[0] >= frm:
            rows.append((_ep(datetime.strptime(f[0] + " " + f[1][:5], "%Y.%m.%d %H:%M")), *[float(x) for x in f[2:6]], int(f[8]) * 0.01))
    B = np.array(sorted(rows), dtype=np.float64)
    t15 = B[:, 0].astype(np.int64)
    k1, first, m2c, roll = _timeline(t15, t15.copy())
    m2c = np.maximum(m2c - 840, 0)                                  # the candle is one step: its time is its last minute
    atr, adx = _atr_adx(B[:, 1], B[:, 2], B[:, 3], B[:, 4])
    hr = ((t15 // 3600) % 24).astype(np.int64)
    out = SIMDATA / "m15.npz"
    np.savez_compressed(out, t15=t15, hr15=hr, o15=B[:, 1], h15=B[:, 2], l15=B[:, 3], c15=B[:, 4], ef=np.zeros(len(t15)), es=np.zeros(len(t15)),
                        adx=adx, atr=atr, t1=t15.copy(), o1=B[:, 1], h1=B[:, 2], l1=B[:, 3], c1=B[:, 4], sp1=np.maximum(B[:, 5], 0.10), k1=k1,
                        first1=first, m2c=m2c, roll=roll, events=np.array([], dtype=object))
    _D.pop("m15", None)
    return out


def build_m15m1_dataset(m15=r"C:\Users\zeesh\turtle\data_15min_2015_onwards_xauusd\XAUUSD_M15_201502040000_202610200300.csv",
                        m1=r"C:\Users\zeesh\turtle\data_15min_2015_onwards_xauusd\XAUUSD_M1_202212290100_202610200315.csv", frm="2022.12.29"):
    """Zee 2026-10-20: Blueberry M15 + M1 exports (MT5 'Export bars'), Dec 29 2022 -> now: the 15-min candles with their real 1-minute candles
    inside (spread per minute from the export, points x 0.01) -> simdata/m15.npz (replaces the one-step version)."""
    def rd(path):
        out = []
        for line in Path(path).read_text().splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 9 and f[0] >= frm:
                out.append((_ep(datetime.strptime(f[0] + " " + f[1][:5], "%Y.%m.%d %H:%M")), *[float(x) for x in f[2:6]], max(int(f[8]), 10) * 0.01))
        return np.array(sorted(out), dtype=np.float64)
    B, M = rd(m15), rd(m1)
    t15, t1 = B[:, 0].astype(np.int64), M[:, 0].astype(np.int64)
    kk = np.searchsorted(t15, t1, side="right") - 1
    keep = (kk >= 0) & (t1 < t15[np.maximum(kk, 0)] + 900)
    M, t1 = M[keep], t1[keep]
    k1, first, m2c, roll = _timeline(t15, t1)
    atr, adx = _atr_adx(B[:, 1], B[:, 2], B[:, 3], B[:, 4])
    out = SIMDATA / "m15.npz"
    np.savez_compressed(out, t15=t15, hr15=((t15 // 3600) % 24).astype(np.int64), o15=B[:, 1], h15=B[:, 2], l15=B[:, 3], c15=B[:, 4],
                        ef=np.zeros(len(t15)), es=np.zeros(len(t15)), adx=adx, atr=atr, t1=t1, o1=M[:, 1], h1=M[:, 2], l1=M[:, 3], c1=M[:, 4],
                        sp1=M[:, 5], k1=k1, first1=first, m2c=m2c, roll=roll, events=np.array([], dtype=object))
    _D.pop("m15", None)
    return out


# ---------------------------------------------------------------- every EA input (sim_full.py)
import sim_full  # noqa: E402

NAMES_ALL = NAMES + sim_full.FULL
_ADX, _HTF = {}, {}


def pvec_all(inputs):
    dfl = {"InpTrigBid": "true", "InpMaxPos": "1", "InpSkipDow": "-1", "InpAdxPeriod": "14", "InpMaxLots": "50"}
    P = np.array([_b(inputs.get(n, dfl.get(n, "0"))) for n in NAMES_ALL], dtype=np.float64)
    _, bb, bs = pvec(inputs)
    return P, bb, bs


def adx_for(ds, n):
    D = data(ds)
    if ds == "year" and n == 14:
        return D["adx"]
    if (ds, n) not in _ADX:
        tr = np.empty(len(D["c15"])); h, l, c = D["h15"], D["l15"], D["c15"]
        _ADX[(ds, n)] = _atr_adx(D["o15"], h, l, c, n)[1]
    return _ADX[(ds, n)]


def htf_for(ds, minutes, n):
    """at each candle's close: the last CLOSED higher-timeframe candle's close and its EMA (and the one before), as iClose(htf,1) / iMA buffers 1, 2"""
    key = (ds, int(minutes), int(n))
    if key not in _HTF:
        D = data(ds)
        t, c = D["t15"], D["c15"]
        if minutes <= 0:
            z = np.zeros(len(t)); _HTF[key] = (z, z, z)
        else:
            H = int(minutes) * 60
            hid = t // H
            ids, last = np.unique(hid, return_index=False), None
            ends = np.r_[np.where(np.diff(hid) != 0)[0], len(hid) - 1]
            hc = c[ends]
            he = ema(hc, int(n), hc[0])
            pos = np.searchsorted(ids, (t + 900) // H) - 1          # the HTF bar before the one running when candle i closes
            hcv = np.where(pos >= 0, hc[np.maximum(pos, 0)], 0.0)
            e1 = np.where(pos >= 0, he[np.maximum(pos, 0)], 0.0)
            e2 = np.where(pos >= 1, he[np.maximum(pos - 1, 0)], 0.0)
            _HTF[key] = (hcv, e1, e2)
    return _HTF[key]


def simulate(inputs, ds="year", chart=False, **extra):
    """Every EA input (sim_full.run_full). ds 'year' (Blueberry MT5 candles), 'tv' (TradingView's), 'm15' (Blueberry 2023 -> now)."""
    D = data(ds)
    P, bb, bs = pvec_all(inputs)
    ef, es = emas(P[0], P[1], ds)
    ex = dict(CHART_RULES) if chart else {}
    if ds == "tv":
        ex["warm_k"] = 2 * P[1] + 19
    ex.update(extra)
    X = np.zeros(17)
    X[:16] = xvec(ex)
    X[16] = float(ex.get("deposit", 100000))
    hc, h1_, h2_ = htf_for(ds, P[sim_full.F["InpHtfMin"]], P[sim_full.F["InpHtfEma"]])
    dow = ((D["t15"] // 86400 + 4) % 7).astype(np.int64)          # 0 Sunday .. 6 Saturday (MqlDateTime.day_of_week)
    day1 = (D["t1"] // 86400).astype(np.int64)
    out = np.zeros((8000, 15)); setups = np.zeros((60000, 3)); stats = np.zeros(8)
    nt, ns = sim_full.run_full(D["t15"], D["hr15"], dow, D["o15"], D["h15"], D["l15"], D["c15"], ef, es, D["atr"],
                               adx_for(ds, int(P[sim_full.F["InpAdxPeriod"]])), hc, h1_, h2_, D["t1"], D["o1"], D["h1"], D["l1"], D["c1"],
                               D["sp1"], D["k1"], D["first1"], D["m2c"], D["roll"], day1, P, X, bb, bs, out, setups, stats)
    return out[:nt], setups[:ns], dict(zip(["setups", "no_break", "risk", "adx", "atr_band", "band_skip", "gap", "spread_reject"], stats.astype(int).tolist()))
