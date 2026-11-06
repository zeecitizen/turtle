"""mlx/features.py - the per-bar features of mlx/FEATURE_SPEC.md on the tester's M15 candles (sim.data("m15")), one column per table row.

Every value at bar i uses bars <= i only (data.check_lookahead proves it by truncation). NAMES is the column order the MQL5 side
(mt5/MlxFeatures.mqh) mirrors; the ONNX tensor follows it after SHAP pruning. ATR = D["atr"] (MT5's iATR: SMA(14) of the true range,
the tester's own column). ADX = MT5's iADX algorithm (ADX.mq5: the per-bar DI = 100 * DM / TR smoothed by an EMA with alpha 2/15, DX smoothed
the same way, bar 0 = 0) - NOT Wilder's 1/14 running sums; adx_wilder() is here only so data.check_adx can show the difference.
Interpretations where the spec leaves a choice (the MQL5 side must pick the same):
  since_hi20 / since_lo20 - on equal highs / lows the MOST RECENT bar wins (iHighest's strict '>' scanning from the newest bar).
  pivots                  - bar p is a pivot high when h[p] >= every high in p-3..p+3 (ties count); the most recent confirmed one is used.
  vs_pclose / prng        - "previous date" = the date of the bar just before today's first bar (the last trading day, not calendar day - 1).
  ib_u                    - IB1 = the first 4 bars of today with hour 10..14, IB2 = the first 4 with hour >= 15; "completed" = 4 bars closed.
  spread_pts              - sp1 is dollars (points x 0.01): spread_pts = round(sp1 * 100).
The spec's table numbers 85 columns (its text says 86): NAMES follows the table; len(NAMES) is the width everywhere."""
import os

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np                                     # noqa: E402
from numba import njit                                 # noqa: E402

WARMUP = 600                                           # bars of history a row needs (the spec: not exported)
EMA_N = (8, 16, 32, 64, 128, 256)
SHAPE = ("range", "body", "uwick", "lwick", "clpos", "dir")
NAMES = (["ret_%d" % n for n in (1, 2, 4, 8, 16, 32, 64, 96)]
         + ["c%d_%s" % (k, s) for k in (0, 1, 2) for s in SHAPE]
         + ["gap_0", "atr_r96", "atr_r480", "atr_pct480", "rng_m4", "rng_m16", "rv_16", "rv_64"]
         + ["ema_%d" % n for n in EMA_N]
         + ["slope16_4", "slope16_16", "slope64_4", "slope64_16", "disp_16_64", "disp_64_256", "adx", "di_diff", "adx_d4"]
         + ["pos_7", "pos_20", "pos_50", "pos_100", "dhi_20", "dhi_50", "dhi_100", "dlo_20", "dlo_50", "dlo_100", "since_hi20", "since_lo20"]
         + ["hour", "minute", "dow", "bar_of_day", "day_rng", "day_pos", "vs_dopen", "vs_pclose", "prng", "kelt_u", "expn", "h1_pos", "asia_u", "ib_u"]
         + ["piv_hi_d", "piv_lo_d", "piv_hi_age", "piv_lo_age", "hh_10", "ll_10", "inside_3", "up_streak", "dn_streak", "spread_pts"])
IX = {n: i for i, n in enumerate(NAMES)}


# ---------------------------------------------------------------- indicators
@njit(cache=True)
def ema(c, n):
    """iMA(..., MODE_EMA): alpha 2/(n+1), seeded on the first close, MT5's price*a + prev*(1-a) form"""
    a = 2.0 / (n + 1.0)
    e = np.empty_like(c)
    e[0] = c[0]
    for i in range(1, c.shape[0]):
        e[i] = c[i] * a + e[i - 1] * (1.0 - a)
    return e


@njit(cache=True)
def adx_mt5(h, l, c, n):
    """MT5's ADX.mq5 (= iADX, = the tester's D["adx"]): returns (ADX main line, +DI, -DI)"""
    m = h.shape[0]
    pr = 2.0 / (n + 1.0)
    adx = np.zeros(m)
    pdi = np.zeros(m)
    ndi = np.zeros(m)
    for i in range(1, m):
        up = h[i] - h[i - 1]
        dn = l[i - 1] - l[i]
        if up < 0.0:
            up = 0.0
        if dn < 0.0:
            dn = 0.0
        if up > dn:
            dn = 0.0
        elif up < dn:
            up = 0.0
        else:
            up = 0.0
            dn = 0.0
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        pd = 100.0 * up / tr if tr != 0.0 else 0.0
        nd = 100.0 * dn / tr if tr != 0.0 else 0.0
        pdi[i] = pd * pr + pdi[i - 1] * (1.0 - pr)
        ndi[i] = nd * pr + ndi[i - 1] * (1.0 - pr)
        s = pdi[i] + ndi[i]
        dx = 100.0 * abs((pdi[i] - ndi[i]) / s) if s != 0.0 else 0.0
        adx[i] = dx * pr + adx[i - 1] * (1.0 - pr)
    return adx, pdi, ndi


@njit(cache=True)
def adx_wilder(h, l, c, n):
    """textbook Wilder ADX (running sums smoothed s - s/n + x, first ADX = mean of the first n DX) - for the comparison report only"""
    m = h.shape[0]
    adx = np.zeros(m)
    str_ = 0.0
    spd = 0.0
    snd = 0.0
    dxs = 0.0
    cnt = 0
    for i in range(1, m):
        up = max(h[i] - h[i - 1], 0.0)
        dn = max(l[i - 1] - l[i], 0.0)
        if up > dn:
            dn = 0.0
        elif dn > up:
            up = 0.0
        else:
            up = 0.0
            dn = 0.0
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i <= n:
            str_ += tr
            spd += up
            snd += dn
        else:
            str_ = str_ - str_ / n + tr
            spd = spd - spd / n + up
            snd = snd - snd / n + dn
        if i < n:
            continue
        pdi = 100.0 * spd / str_ if str_ != 0.0 else 0.0
        ndi = 100.0 * snd / str_ if str_ != 0.0 else 0.0
        s = pdi + ndi
        dx = 100.0 * abs(pdi - ndi) / s if s != 0.0 else 0.0
        if cnt < n:
            dxs += dx
            cnt += 1
            adx[i] = dxs / cnt
        else:
            adx[i] = (adx[i - 1] * (n - 1) + dx) / n
    return adx


# ---------------------------------------------------------------- scans
@njit(cache=True)
def _rolling(h, l, c, atr, rng):
    """the window statistics (NaN while the window is incomplete): ATR means / rank, range means, change std, highs / lows, bars since"""
    n = h.shape[0]
    nan = np.nan
    atr_m96 = np.full(n, nan)
    atr_m480 = np.full(n, nan)
    atr_pct = np.full(n, nan)
    rng_m4 = np.full(n, nan)
    rng_m16 = np.full(n, nan)
    rv16 = np.full(n, nan)
    rv64 = np.full(n, nan)
    hi = np.full((5, n), nan)                      # windows 7, 20, 50, 100, 10
    lo = np.full((5, n), nan)
    hi10p = np.full(n, nan)                        # bars i-19..i-10
    lo10p = np.full(n, nan)
    since_hi = np.full(n, nan)
    since_lo = np.full(n, nan)
    W = (7, 20, 50, 100, 10)
    for i in range(n):
        if i >= 95:
            s = 0.0
            for j in range(i - 95, i + 1):
                s += atr[j]
            atr_m96[i] = s / 96.0
        if i >= 479:
            s = 0.0
            k = 0
            for j in range(i - 479, i + 1):
                s += atr[j]
                if j < i and atr[j] < atr[i]:
                    k += 1
            atr_m480[i] = s / 480.0
            atr_pct[i] = k / 479.0
        if i >= 3:
            s = 0.0
            for j in range(i - 3, i + 1):
                s += rng[j]
            rng_m4[i] = s / 4.0
        if i >= 15:
            s = 0.0
            for j in range(i - 15, i + 1):
                s += rng[j]
            rng_m16[i] = s / 16.0
        if i >= 16:
            mu = 0.0
            for j in range(i - 15, i + 1):
                mu += c[j] - c[j - 1]
            mu /= 16.0
            v = 0.0
            for j in range(i - 15, i + 1):
                d = c[j] - c[j - 1] - mu
                v += d * d
            rv16[i] = np.sqrt(v / 16.0)
        if i >= 64:
            mu = 0.0
            for j in range(i - 63, i + 1):
                mu += c[j] - c[j - 1]
            mu /= 64.0
            v = 0.0
            for j in range(i - 63, i + 1):
                d = c[j] - c[j - 1] - mu
                v += d * d
            rv64[i] = np.sqrt(v / 64.0)
        for w in range(5):
            m = W[w]
            if i >= m - 1:
                mx = h[i]
                mn = l[i]
                for j in range(i - m + 1, i):
                    if h[j] > mx:
                        mx = h[j]
                    if l[j] < mn:
                        mn = l[j]
                hi[w, i] = mx
                lo[w, i] = mn
        if i >= 19:
            mx = h[i - 10]
            mn = l[i - 10]
            for j in range(i - 19, i - 10):
                if h[j] > mx:
                    mx = h[j]
                if l[j] < mn:
                    mn = l[j]
            hi10p[i] = mx
            lo10p[i] = mn
            # bars since the highest high / lowest low of the last 20 (ties: the most recent bar)
            mx = h[i]
            mn = l[i]
            kh = i
            kl = i
            for j in range(i - 1, i - 20, -1):
                if h[j] > mx:
                    mx = h[j]
                    kh = j
                if l[j] < mn:
                    mn = l[j]
                    kl = j
            since_hi[i] = i - kh
            since_lo[i] = i - kl
    return atr_m96, atr_m480, atr_pct, rng_m4, rng_m16, rv16, rv64, hi, lo, hi10p, lo10p, since_hi, since_lo


@njit(cache=True)
def _sessions(t15, hr15, o, h, l, c):
    """one pass over the days: today's range / open, the previous date's close and range, the developing H1 candle, Asia, the Initial Balance"""
    n = t15.shape[0]
    nan = np.nan
    bod = np.zeros(n)
    dhi = np.empty(n)
    dlo = np.empty(n)
    dop = np.empty(n)
    pcl = np.full(n, nan)
    prg = np.full(n, nan)
    h1h = np.empty(n)
    h1l = np.empty(n)
    ash = np.full(n, nan)
    asl = np.full(n, nan)
    ibh = np.full(n, nan)
    ibl = np.full(n, nan)
    day = -1
    first = 0
    cur_hour = -1
    dh = 0.0
    dl = 0.0
    do = 0.0
    pc = nan
    pr = nan
    hh = 0.0
    hl = 0.0
    ah = 0.0
    al = 0.0
    asia = False
    i1n = 0
    i1h = 0.0
    i1l = 0.0
    i2n = 0
    i2h = 0.0
    i2l = 0.0
    for i in range(n):
        d = t15[i] // 86400
        if d != day:
            if day >= 0:
                pc = c[i - 1]
                pr = dh - dl
            day = d
            first = i
            dh = h[i]
            dl = l[i]
            do = o[i]
            cur_hour = -1
            asia = False
            i1n = 0
            i2n = 0
        else:
            if h[i] > dh:
                dh = h[i]
            if l[i] < dl:
                dl = l[i]
        bod[i] = i - first
        dhi[i] = dh
        dlo[i] = dl
        dop[i] = do
        pcl[i] = pc
        prg[i] = pr
        hr = hr15[i]
        if hr != cur_hour:
            cur_hour = hr
            hh = h[i]
            hl = l[i]
        else:
            if h[i] > hh:
                hh = h[i]
            if l[i] < hl:
                hl = l[i]
        h1h[i] = hh
        h1l[i] = hl
        if hr <= 7:
            if not asia:
                asia = True
                ah = h[i]
                al = l[i]
            else:
                if h[i] > ah:
                    ah = h[i]
                if l[i] < al:
                    al = l[i]
        if asia:
            ash[i] = ah
            asl[i] = al
        if hr >= 15:
            if i2n < 4:
                if i2n == 0:
                    i2h = h[i]
                    i2l = l[i]
                else:
                    if h[i] > i2h:
                        i2h = h[i]
                    if l[i] < i2l:
                        i2l = l[i]
                i2n += 1
        elif hr >= 10:
            if i1n < 4:
                if i1n == 0:
                    i1h = h[i]
                    i1l = l[i]
                else:
                    if h[i] > i1h:
                        i1h = h[i]
                    if l[i] < i1l:
                        i1l = l[i]
                i1n += 1
        if i2n == 4:
            ibh[i] = i2h
            ibl[i] = i2l
        elif i1n == 4:
            ibh[i] = i1h
            ibl[i] = i1l
    return bod, dhi, dlo, dop, pcl, prg, h1h, h1l, ash, asl, ibh, ibl


@njit(cache=True)
def _pivots(h, l, c, a, look, w):
    """the last confirmed pivot high / low (bar p <= i-w whose high / low is the extreme of p-w..p+w), within look bars; 0 when none"""
    n = h.shape[0]
    phd = np.zeros(n)
    pld = np.zeros(n)
    pha = np.zeros(n)
    pla = np.zeros(n)
    last_hi = -1
    last_lo = -1
    for i in range(n):
        p = i - w
        if p >= w:
            is_hi = True
            is_lo = True
            for k in range(p - w, p + w + 1):
                if h[k] > h[p]:
                    is_hi = False
                if l[k] < l[p]:
                    is_lo = False
            if is_hi:
                last_hi = p
            if is_lo:
                last_lo = p
        if last_hi >= 0 and i - last_hi <= look:
            phd[i] = (h[last_hi] - c[i]) / a[i]
            pha[i] = i - last_hi
        if last_lo >= 0 and i - last_lo <= look:
            pld[i] = (c[i] - l[last_lo]) / a[i]
            pla[i] = i - last_lo
    return phd, pld, pha, pla


@njit(cache=True)
def _streaks(o, c):
    n = o.shape[0]
    up = np.zeros(n)
    dn = np.zeros(n)
    for i in range(n):
        if c[i] > o[i]:
            up[i] = 1.0 if i == 0 else up[i - 1] + 1.0
        elif c[i] < o[i]:
            dn[i] = 1.0 if i == 0 else dn[i - 1] + 1.0
    return up, dn


# ---------------------------------------------------------------- the table
def _shift(x, n):
    y = np.full_like(x, np.nan)
    y[n:] = x[:-n] if n > 0 else x
    return y


def _shape(o, h, l, c, rng):
    """the six candle numbers of a bar: range (raw, the caller divides by ATR), body, upper wick, lower wick, close position, direction"""
    hi = np.maximum(o, c)
    lo = np.minimum(o, c)
    return [h - l, np.abs(c - o) / rng, (h - hi) / rng, (lo - l) / rng, (c - l) / rng, np.sign(c - o)]


def _rsum(b, m):
    """count of the m bars j in i-m+1..i with flag b[j] (b[j] uses bar j-1, so NaN until i >= m)"""
    cs = np.cumsum(b)
    out = np.full(len(b), np.nan)
    out[m:] = cs[m:] - cs[:-m]
    return out


def build(D):
    """D = sim.data("m15") (or a truncation of it) -> (X float64 [n x len(NAMES)], NAMES). Undefined values (incomplete history) are NaN;
    the dataset drops the first WARMUP bars and zeroes what is left (data.build_dataset)."""
    o, h, l, c = (np.ascontiguousarray(D[k], dtype=np.float64) for k in ("o15", "h15", "l15", "c15"))
    t15 = np.ascontiguousarray(D["t15"], dtype=np.int64)
    hr15 = np.ascontiguousarray(D["hr15"], dtype=np.int64)
    atr = np.ascontiguousarray(D["atr"], dtype=np.float64)
    n = len(c)
    a = np.maximum(atr, 1e-6)
    rng = np.maximum(h - l, 1e-6)
    F = {}
    for m in (1, 2, 4, 8, 16, 32, 64, 96):
        F["ret_%d" % m] = (c - _shift(c, m)) / a
    sh = _shape(o, h, l, c, rng)
    for k in (0, 1, 2):
        for s, v in zip(SHAPE, sh):
            v = _shift(v, k)
            F["c%d_%s" % (k, s)] = v / a if s == "range" else v
    F["gap_0"] = (o - _shift(c, 1)) / a
    atr_m96, atr_m480, atr_pct, rng_m4, rng_m16, rv16, rv64, hi, lo, hi10p, lo10p, since_hi, since_lo = _rolling(h, l, c, atr, rng)
    F["atr_r96"] = atr / np.maximum(atr_m96, 1e-6)
    F["atr_r480"] = atr / np.maximum(atr_m480, 1e-6)
    F["atr_pct480"] = atr_pct
    F["rng_m4"] = rng_m4 / a
    F["rng_m16"] = rng_m16 / a
    F["rv_16"] = rv16 / a
    F["rv_64"] = rv64 / a
    E = {m: ema(c, m) for m in EMA_N + (20,)}
    for m in EMA_N:
        F["ema_%d" % m] = (c - E[m]) / a
    F["slope16_4"] = (E[16] - _shift(E[16], 4)) / a
    F["slope16_16"] = (E[16] - _shift(E[16], 16)) / a
    F["slope64_4"] = (E[64] - _shift(E[64], 4)) / a
    F["slope64_16"] = (E[64] - _shift(E[64], 16)) / a
    F["disp_16_64"] = (E[16] - E[64]) / a
    F["disp_64_256"] = (E[64] - E[256]) / a
    adx, pdi, ndi = adx_mt5(h, l, c, 14)
    F["adx"] = adx
    F["di_diff"] = pdi - ndi
    F["adx_d4"] = adx - _shift(adx, 4)
    for w, m in enumerate((7, 20, 50, 100)):
        F["pos_%d" % m] = (c - lo[w]) / np.maximum(hi[w] - lo[w], 1e-6)
        if m >= 20:
            F["dhi_%d" % m] = (hi[w] - c) / a
            F["dlo_%d" % m] = (c - lo[w]) / a
    F["since_hi20"] = since_hi
    F["since_lo20"] = since_lo
    F["hour"] = hr15.astype(np.float64)
    F["minute"] = ((t15 // 60) % 60).astype(np.float64)
    F["dow"] = ((t15 // 86400 + 4) % 7).astype(np.float64)
    bod, dhi, dlo, dop, pcl, prg, h1h, h1l, ash, asl, ibh, ibl = _sessions(t15, hr15, o, h, l, c)
    F["bar_of_day"] = bod
    F["day_rng"] = (dhi - dlo) / a
    F["day_pos"] = (c - dlo) / np.maximum(dhi - dlo, 1e-6)
    F["vs_dopen"] = (c - dop) / a
    F["vs_pclose"] = np.where(np.isnan(pcl), 0.0, (c - np.nan_to_num(pcl)) / a)
    F["prng"] = np.where(np.isnan(prg), 0.0, np.nan_to_num(prg) / a)
    F["kelt_u"] = (c - E[20]) / (2.0 * a)
    F["expn"] = np.minimum((hi[4] - lo[4]) / np.maximum(hi10p - lo10p, 1e-6), 10.0)
    F["h1_pos"] = (c - h1l) / np.maximum(h1h - h1l, 1e-6)
    F["asia_u"] = np.where(np.isnan(ash), 0.5, (c - np.nan_to_num(asl)) / np.maximum(np.nan_to_num(ash) - np.nan_to_num(asl), 1e-6))
    F["ib_u"] = np.where(np.isnan(ibh), 0.5, (c - np.nan_to_num(ibl)) / np.maximum(np.nan_to_num(ibh) - np.nan_to_num(ibl), 1e-6))
    phd, pld, pha, pla = _pivots(h, l, c, a, 100, 3)
    F["piv_hi_d"], F["piv_lo_d"], F["piv_hi_age"], F["piv_lo_age"] = phd, pld, pha, pla
    hup = np.zeros(n)
    hup[1:] = h[1:] > h[:-1]
    ldn = np.zeros(n)
    ldn[1:] = l[1:] < l[:-1]
    ins = np.zeros(n)
    ins[1:] = (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])
    F["hh_10"] = _rsum(hup, 10)
    F["ll_10"] = _rsum(ldn, 10)
    F["inside_3"] = _rsum(ins, 3)
    F["up_streak"], F["dn_streak"] = _streaks(o, c)
    k1 = np.asarray(D["k1"], dtype=np.int64)
    last = np.searchsorted(k1, np.arange(n), side="right") - 1          # the bar's last minute (k1 is sorted)
    has = (last >= 0) & (k1[np.maximum(last, 0)] == np.arange(n))
    sp = np.zeros(n)
    sp[has] = np.rint(np.asarray(D["sp1"], dtype=np.float64)[last[has]] * 100.0)
    F["spread_pts"] = sp
    X = np.empty((n, len(NAMES)))
    for j, name in enumerate(NAMES):
        X[:, j] = F[name]
    return X, list(NAMES)


def clean(X):
    """NaN / inf -> 0; returns (X float32, how many cells were fixed)"""
    bad = ~np.isfinite(X)
    X = np.where(bad, 0.0, X).astype(np.float32)
    return X, int(bad.sum())
