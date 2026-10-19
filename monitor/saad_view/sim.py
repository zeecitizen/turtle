"""sim.py - the Turtle TV Tester: Saad_strategy_15min v1.27's rules as a numba-compiled loop over the year (Zee 2026-10-20: "we want a faster
few seconds running optimizer to constantly optimize settings and view their result in turtle tv chart" ... "its ok since we have our own chart
we can rely on python to build an optimizer. this is diff from backtests in python. its about finding best settings").

CLAUDE.md still holds: this engine GENERATES settings; MT5's Strategy Tester (Turtle TV's lower section) is what PROMOTES them. Every number from
here is labelled "Turtle TV Tester" and is checked against MT5 (validate.py: setups, entries, exits, and the RANKING of different settings).

Data (build_dataset): the viewer EA's export of the year on Blueberry real ticks - every M15 candle with the EA's own EMA / ATR / ADX, and every
M1 candle with its spread. The loop walks the M1 candles in MT5's "1 minute OHLC" order (open, low, high, close for a rising minute; open, high,
low, close for a falling one) and makes v1.27's decisions in the EA's order: day-close check, stop / target, then at a new 15-min candle the
close-back exits, the waiting setup's countdown and a new setup, then the break entry.
Only v1.27's live paths are implemented: entry mode 0, stop modes 0/1/2, exit modes 1/2, range boxes with skip / stand aside."""
import os

os.environ.setdefault("NUMBA_CPU_NAME", "generic")   # this laptop's ARM CPU crashes LLVM's scheduler unless numba targets a generic CPU
import json                                            # noqa: E402
from datetime import datetime, timedelta               # noqa: E402
from pathlib import Path                               # noqa: E402

import numpy as np                                     # noqa: E402
from numba import njit                                 # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "simdata" / "year.npz"
COMMON = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
SWAP_LONG, SWAP_SHORT = -61.6, 40.5      # $ per lot per night on Blueberry XAUUSD (measured from MT5's exits); Wednesday night x3

# the parameter vector: EA input -> index
NAMES = ["InpEmaFast", "InpEmaSlow", "InpWickMin", "InpBodyMax", "InpNoseMax", "InpUsePin", "InpPinDir", "InpPinColor", "InpMarubozu", "InpMaruBody",
         "InpHammer", "InpStar", "InpHamRatio", "InpHamNose", "InpMinRangeAtr", "InpLongRule", "InpShortLine", "InpTouchMode", "InpTouchPips",
         "InpLongExitAbove", "InpBreakBars", "InpBreakPips", "InpSlMode", "InpSlPips", "InpSlAtrMult", "InpSlUsd", "InpMaxRiskUsd", "InpSessFrom",
         "InpSessTo", "InpAdxMin", "InpAtrMinUsd", "InpAtrMaxUsd", "InpRangeLook", "InpRangeLookS", "InpBandOff", "InpExitMode", "InpCloseLossMins",
         "InpLots", "InpBuys", "InpSells", "InpGapCancel"]
IX = {n: i for i, n in enumerate(NAMES)}


def _b(v):
    return 1.0 if str(v).strip().lower() == "true" else 0.0 if str(v).strip().lower() == "false" else float(v)


def pvec(inputs):
    """EA inputs (strings, as in a Turtle TV run / ea_defaults) -> (parameter vector, BUY boxes, SELL boxes)."""
    P = np.array([_b(inputs[n]) for n in NAMES], dtype=np.float64)
    bb = np.array([1 if ch != "0" else 0 for ch in str(inputs["InpBandsB"]).ljust(21, "1")[:21]], dtype=np.int64)
    bs = np.array([1 if ch != "0" else 0 for ch in str(inputs["InpBandsS"]).ljust(21, "1")[:21]], dtype=np.int64)
    return P, bb, bs


# ---------------------------------------------------------------- data
def _srv(s):
    return datetime.strptime(s.strip(), "%Y.%m.%d %H:%M")


def build_dataset(tag="simdata"):
    """The viewer EA's export (InpExportM1) -> simdata/year.npz. Server time throughout (Blueberry = New York + 7)."""
    bars = [l.split("\t") for l in (COMMON / f"saadview_{tag}_bars.csv").read_text().splitlines()[1:]]
    m1 = [l.split("\t") for l in (COMMON / f"saadview_{tag}_m1.csv").read_text().splitlines()[1:]]
    ev = (COMMON / f"saadview_{tag}_events.csv").read_text().splitlines()
    ep = lambda d: int((d - datetime(1970, 1, 1)).total_seconds())
    seen, B = set(), []
    for f in bars:
        t = _srv(f[0])
        if t not in seen and len(f) >= 9:
            seen.add(t); B.append((ep(t), t.hour, *[float(x) for x in f[1:9]]))
    B.sort()
    B = np.array(B, dtype=np.float64)
    M = np.array([(ep(_srv(f[0])), float(f[1]), float(f[2]), float(f[3]), float(f[4]), int(f[5]) * 0.01) for f in m1 if len(f) >= 7], dtype=np.float64)
    M = M[np.argsort(M[:, 0], kind="stable")]
    t15 = B[:, 0].astype(np.int64)
    t1 = M[:, 0].astype(np.int64)
    k1 = np.searchsorted(t15, t1, side="right") - 1                     # the M15 candle each minute belongs to
    keep = k1 >= 0
    M, t1, k1 = M[keep], t1[keep], k1[keep]
    first = np.ones(len(t1), dtype=np.int64)
    first[1:] = (k1[1:] != k1[:-1]).astype(np.int64)
    # the session's end for each server day = its last minute + 60 s; minutes left at each minute's open
    day = t1 // 86400
    end = np.zeros(len(t1), dtype=np.int64)
    for d in np.unique(day):
        idx = np.where(day == d)[0]
        end[idx] = t1[idx[-1]] + 60
    m2c = end - t1
    # rollover: a new server day -> swap nights (Wednesday x3, Friday -> Monday none)
    roll = np.zeros(len(t1), dtype=np.int64)
    for j in range(1, len(t1)):
        if day[j] != day[j - 1]:
            wd = (int(t1[j - 1]) // 86400 + 3) % 7                         # 1970-01-01 was a Thursday -> 0 = Monday
            roll[j] = 3 if wd == 2 else 0 if wd >= 4 else 1
    DATA.parent.mkdir(exist_ok=True)
    np.savez_compressed(DATA, t15=t15, hr15=B[:, 1].astype(np.int64), o15=B[:, 2], h15=B[:, 3], l15=B[:, 4], c15=B[:, 5], ef=B[:, 6], es=B[:, 7],
                        adx=B[:, 8], atr=B[:, 9], t1=t1, o1=M[:, 1], h1=M[:, 2], l1=M[:, 3], c1=M[:, 4], sp1=M[:, 5], k1=k1, first1=first,
                        m2c=m2c, roll=roll, events=np.array(ev, dtype=object))
    return DATA


_D = None


def data():
    global _D
    if _D is None:
        z = np.load(DATA, allow_pickle=True)
        _D = {k: z[k] for k in z.files}
    return _D


def ema(c, n, seed):
    a = 2.0 / (n + 1)
    e = np.empty_like(c)
    e[0] = seed
    for i in range(1, len(c)):
        e[i] = e[i - 1] + a * (c[i] - e[i - 1])
    return e


_EMA = {}


def emas(nf, ns):
    """The EA's iMA EMAs on the M15 closes. Seeded with the EA's own value at the first candle for its default 16 / 32 (MT5 had history before),
    with the first close otherwise (converged within a couple of days)."""
    D = data()
    out = []
    for n, col in ((int(nf), "ef"), (int(ns), "es")):
        key = n
        if key not in _EMA:
            seed = D["ef"][0] if n == 16 else D["es"][0] if n == 32 else D["c15"][0]
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
def run(t15, hr15, o15, h15, l15, c15, ef, es, atr, adx, t1, o1, h1, l1, c1, sp1, k1, first1, m2c, roll, P, bandB, bandS, out, setups, stats):
    """out rows: side, entry_t, entry, sl, exit_t, exit, pnl, swap, bucket, nxE, ghost, entry_k15, exit_k15, reason (1 stop 2 target 3 close-back 4 day close)
       setups rows: k15, side, kind   stats: [n_setups, no_break, risk, adx, atr_band, band_skip, gap]"""
    n1 = t1.shape[0]
    af = 2.0 / (P[0] + 1.0)
    asl = 2.0 / (P[1] + 1.0)
    lots = P[37]
    pip = 0.1
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
    pts = np.empty(4)
    for j in range(n1):
        k = k1[j]
        spr = sp1[j]
        o = o1[j]
        if roll[j] > 0 and pos != 0:
            swp += (-61.6 if pos > 0 else 40.5) * lots * roll[j]
        pts[0] = o
        if c1[j] >= o:
            pts[1] = l1[j]
            pts[2] = h1[j]
        else:
            pts[1] = h1[j]
            pts[2] = l1[j]
        pts[3] = c1[j]
        for q in range(4):
            cur = pts[q]
            prv = pts[q - 1] if q > 0 else cur
            tq = t1[j] + q * 15
            # 1. DayCloseCheck: InpCloseLossMins before the session's end, a trade in loss is shut
            inwin = P[36] > 0 and (m2c[j] < (P[36] + 1) * 60 or (m2c[j] == (P[36] + 1) * 60 and q > 0))
            if inwin and pos != 0:
                lossy = (cur < en) if pos > 0 else (cur + spr > en)
                if lossy:
                    xp = cur if pos > 0 else cur + spr
                    if nt < out.shape[0]:
                        out[nt, 0] = pos; out[nt, 1] = posT; out[nt, 2] = en; out[nt, 3] = sl; out[nt, 4] = tq; out[nt, 5] = xp
                        out[nt, 6] = (xp - en) * pos * lots * 100 + swp; out[nt, 7] = swp; out[nt, 8] = bkt; out[nt, 9] = nx; out[nt, 10] = 0
                        out[nt, 11] = posK; out[nt, 12] = k; out[nt, 13] = 4
                        nt += 1
                    pos = 0
            if inwin and gh != 0:
                if (cur < gEn) if gh > 0 else (cur + spr > gEn):
                    xp = cur if gh > 0 else cur + spr
                    if nt < out.shape[0]:
                        out[nt, 0] = gh; out[nt, 1] = gT; out[nt, 2] = gEn; out[nt, 3] = gSl; out[nt, 4] = tq; out[nt, 5] = xp
                        out[nt, 6] = (xp - gEn) * gh * lots * 100; out[nt, 7] = 0; out[nt, 8] = gB; out[nt, 9] = gNx; out[nt, 10] = 1
                        out[nt, 11] = gK; out[nt, 12] = k; out[nt, 13] = 4
                        nt += 1
                    gh = 0
            # 2. stop / target (ManageTick, GhostTick) - also run again right after an entry inside this segment
            for rep in range(2):
                for who in range(2):
                    sd = pos if who == 0 else gh
                    if sd == 0:
                        continue
                    e_ = en if who == 0 else gEn
                    s_ = sl if who == 0 else gSl
                    n_ = nx if who == 0 else gNx
                    xp = 0.0
                    hit = False
                    code = 1
                    if sd > 0:
                        if cur <= s_:
                            hit = True
                            xp = s_ if prv > s_ else cur
                        elif n_ > 0 and k >= 1:
                            ep = ef[k - 1] if n_ == 9 else es[k - 1]
                            if cur >= ep:
                                hit = True
                                code = 2
                                xp = ep if prv < ep else cur
                    else:
                        if cur + spr >= s_:
                            hit = True
                            xp = s_ if prv + spr < s_ else cur + spr
                        elif n_ > 0 and k >= 1:
                            a_ = af if n_ == 9 else asl
                            ep = ef[k - 1] if n_ == 9 else es[k - 1]
                            thr = ep - spr / (1.0 - a_)
                            if cur <= thr:
                                hit = True
                                code = 2
                                xp = (thr if prv > thr else cur) + spr
                    if hit:
                        if nt < out.shape[0]:
                            out[nt, 0] = sd; out[nt, 1] = posT if who == 0 else gT; out[nt, 2] = e_; out[nt, 3] = s_; out[nt, 4] = tq; out[nt, 5] = xp
                            out[nt, 6] = (xp - e_) * sd * lots * 100 + (swp if who == 0 else 0.0); out[nt, 7] = swp if who == 0 else 0.0
                            out[nt, 8] = bkt if who == 0 else gB; out[nt, 9] = n_; out[nt, 10] = who; out[nt, 11] = posK if who == 0 else gK; out[nt, 12] = k; out[nt, 13] = code
                            nt += 1
                        if who == 0:
                            pos = 0
                        else:
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
                                xp = cur if sd > 0 else cur + spr
                                e_ = en if who == 0 else gEn
                                if nt < out.shape[0]:
                                    out[nt, 0] = sd; out[nt, 1] = posT if who == 0 else gT; out[nt, 2] = e_; out[nt, 3] = sl if who == 0 else gSl
                                    out[nt, 4] = tq; out[nt, 5] = xp; out[nt, 6] = (xp - e_) * sd * lots * 100 + (swp if who == 0 else 0.0)
                                    out[nt, 7] = swp if who == 0 else 0.0; out[nt, 8] = bkt if who == 0 else gB; out[nt, 9] = n_; out[nt, 10] = who
                                    out[nt, 11] = kk; out[nt, 12] = k; out[nt, 13] = 3
                                    nt += 1
                                if who == 0:
                                    pos = 0
                                else:
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
                    if shape != 0 and hr >= P[27] and hr < P[28]:
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
                        if (longOk or shortOk) and pos == 0 and gh == 0 and pSide == 0:
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
                        else:
                            e_ = be + spr if side > 0 else be
                            a_ = atr[k - 1]
                            if P[22] == 1:
                                s_ = e_ - P[24] * a_ if side > 0 else e_ + P[24] * a_
                            elif P[22] == 2:
                                s_ = e_ - P[25] if side > 0 else e_ + P[25]
                            else:
                                s_ = pLow - P[23] * pip if side > 0 else pHigh + P[23] * pip
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
                                    b9 = l9 > e_ if side > 0 else l9 < e_
                                    b50 = l50 > e_ if side > 0 else l50 < e_
                                    if b9 and b50:
                                        n_ = 9 if abs(l9 - e_) <= abs(l50 - e_) else 50
                                    elif b9:
                                        n_ = 9
                                    elif b50:
                                        n_ = 50
                                    else:
                                        n_ = -1
                                if off:
                                    gh = side; gEn = e_; gSl = s_; gNx = n_; gK = k; gT = tq; gB = bk + (0 if side > 0 else 21)
                                else:
                                    pos = side; en = e_; sl = s_; nx = n_; posK = k; posT = tq; swp = 0.0; bkt = bk + (0 if side > 0 else 21)
                                prv = be                                  # the rest of this move happens after the entry
                                continue
                break
    return nt, ns


def simulate(inputs, frm=None, to=None):
    """Run the year (or [frm, to) server time) with these EA inputs -> (trades list, setups, stats dict)."""
    D = data()
    P, bb, bs = pvec(inputs)
    ef, es = emas(P[0], P[1])
    out = np.zeros((4000, 14))
    setups = np.zeros((40000, 3))
    stats = np.zeros(8)
    nt, ns = run(D["t15"], D["hr15"], D["o15"], D["h15"], D["l15"], D["c15"], ef, es, D["atr"], D["adx"], D["t1"], D["o1"], D["h1"], D["l1"],
                 D["c1"], D["sp1"], D["k1"], D["first1"], D["m2c"], D["roll"], P, bb, bs, out, setups, stats)
    tr = out[:nt]
    if frm is not None or to is not None:
        a = 0 if frm is None else frm
        b = 1 << 62 if to is None else to
        tr = tr[(tr[:, 1] >= a) & (tr[:, 1] < b)]
    return tr, setups[:ns], dict(zip(["setups", "no_break", "risk", "adx", "atr_band", "band_skip", "gap"], stats[:7].astype(int).tolist()))


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
    return {"n": n, "net": round(net, 2), "pf": round(gw / gl, 3) if gl > 0 else 99.0, "wr": round(100.0 * (p > 0).mean(), 1), "dd": round(dd, 2),
            "ret_dd": (net / max(dd, 1.0)) if n >= min_trades else -1e9 + n}


if __name__ == "__main__":
    import sys
    import time
    if "--build" in sys.argv:
        print("dataset:", build_dataset())
    sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
    import axi_rig
    dfl = axi_rig.ea_defaults("Saad_strategy_15min")
    t0 = time.time(); tr, su, st = simulate(dfl); t1 = time.time()
    tr, su, st = simulate(dfl); t2 = time.time()
    print(f"first call {t1 - t0:.2f}s (compile), then {1000 * (t2 - t1):.1f} ms per year")
    print("v1.27 defaults:", score(tr), st)
