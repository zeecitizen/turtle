"""rbox.py - extra range boxes for the range-boxes page (Zee 2026-10-28: "on the range boxes page add the following as tickable ranges").
Six families, each judged at the ENTRY against the last closed M15 candle:
  vwap  daily VWAP +-1/2/3 standard deviations          ib    the session's Initial Balance (London 10:00, NY 15:00 server, first hour)
  prem  premium / discount of the last 50 candles      kelt  Keltner channel EMA20 +- 2 ATR(14)
  expn  range of the last 10 candles / the 10 before    va    volume value area (70%) of the last 40 candles around its POC
Each box = how many of the family's edges the entry is at or above: u = (entry - c) / s, per candle (c, s) in FB[j, f]. s = 0 -> "no data" box.
Volume = ticks per minute (real ticks on the 4-year m15 data; other datasets weigh every minute the same).
Turtle TV tester only: the EA does not have these yet (TvBox* inputs). Tester = hypothesis; MT5 decides."""
import numpy as np
from numba import njit

FAM = [
    ("vwap", "VWAP bands (daily VWAP, standard deviations)", [-3, -2, -1, 0, 1, 2, 3],
     ["below −3 SD", "−3 to −2", "−2 to −1", "−1 to VWAP", "VWAP to +1", "+1 to +2", "+2 to +3", "above +3 SD"]),
    ("ib", "Initial Balance (first hour of London / New York)", [-1, 0, 0.25, 0.5, 0.75, 1, 2],
     ["far below (>1 IB)", "just below", "IB 0–25%", "IB 25–50%", "IB 50–75%", "IB 75–100%", "just above", "far above (>1 IB)", "no IB yet (Asia)"]),
    ("prem", "Premium / discount (last 50 candles' range)", [0.25, 0.5, 0.75],
     ["discount 0–25%", "discount 25–50%", "premium 50–75%", "premium 75–100%"]),
    ("kelt", "Keltner channel (EMA 20 ± 2 ATR)", [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
     ["below the channel", "0–10%", "10–20%", "20–30%", "30–40%", "40–50%", "50–60%", "60–70%", "70–80%", "80–90%", "90–100%", "above the channel"]),
    ("expn", "Expansion / contraction (last 10 candles' range ÷ the 10 before)", [0.5, 0.75, 1, 1.5, 2, 3],
     ["< 0.5 squeezed", "0.5–0.75", "0.75–1", "1–1.5", "1.5–2", "2–3", "> 3 exhausted"]),
    ("va", "Value area (last 40 candles, around the POC)", [-1, -0.5, -0.1, 0.1, 0.5, 1],
     ["below the value area", "low edge", "low inside", "AT the POC", "high inside", "high edge", "above the value area"]),
    ("h1", "Developing H1 candle (thirds of its range so far)", [0, 1 / 3, 2 / 3, 1],
     ["below its low", "bottom third (the wick)", "middle third", "top third", "above its high", "no H1 range yet"]),
    ("fvg", "Fair Value Gap (newest gap of the last 20 candles)", [-1, 0, 1, 2],
     ["far below (>1 gap)", "just below", "INSIDE the gap", "just above", "far above (>1 gap)", "no gap in 20 candles"]),
    ("asia", "Asian range (00:00–08:00 server)", [-0.5, 0, 0.25, 0.75, 1, 1.5],
     ["far below", "sweep below", "inside, low edge", "inside, middle", "inside, high edge", "sweep above", "far above", "Asia still forming"]),
    ("disp", "EMA dispersion: (fast EMA − slow EMA) ÷ ATR", [-2, -0.5, 0.5, 2],
     ["fast far below slow (< −2)", "below (−2 to −0.5)", "ENTWINED (±0.5)", "above (0.5 to 2)", "fast far above slow (> 2)"]),
]
NF, NB = len(FAM), 16
EDGES = np.full((NF, NB), np.inf)
for f, (_, _, e, _) in enumerate(FAM):
    EDGES[f, :len(e)] = e
NE = np.array([len(x[2]) for x in FAM], dtype=np.int64)
_CACHE = {}


def keys():
    return [f"TvBox_{k}_{s}" for k, *_ in FAM for s in "BS"]


def masks(inputs):
    """(2 sides, NF, NB) int64, 1 = trade; and on = any box unticked"""
    M = np.ones((2, NF, NB), dtype=np.int64)
    for f, (k, _, e, lab) in enumerate(FAM):
        for si, s in enumerate("BS"):
            v = str(inputs.get(f"TvBox_{k}_{s}", "") or "")
            for b, ch in enumerate(v[:len(lab)]):
                M[si, f, b] = 0 if ch == "0" else 1
    return M, int((M == 0).any())


@njit(cache=True)
def box_of(FB, EDGES, NE, j, f, e):
    s = FB[j, f, 1]
    if s == 0.0 or j < 0:
        return NE[f] + 1                                   # no data (IB before London)
    u = (e - FB[j, f, 0]) / s
    b = 0
    for q in range(NE[f]):
        if u >= EDGES[f, q]:
            b = q + 1
    return b


@njit(cache=True)
def _build(t15, o15, h15, l15, c15, atr, t1, h1, l1, c1, w1, m15end, FB):
    n = t15.shape[0]
    # Keltner EMA20
    em = np.empty(n); em[0] = c15[0]; a = 2.0 / 21.0
    for i in range(1, n):
        em[i] = em[i - 1] + a * (c15[i] - em[i - 1])
    # daily VWAP from the minutes (broker day)
    sw = 0.0; swp = 0.0; swp2 = 0.0; day = -1; m = 0; n1 = t1.shape[0]
    for j in range(n):
        end = m15end[j]
        while m <= end and m < n1:
            d = t1[m] // 86400
            if d != day:
                day = d; sw = 0.0; swp = 0.0; swp2 = 0.0
            tp = (h1[m] + l1[m] + c1[m]) / 3.0; w = w1[m]
            sw += w; swp += w * tp; swp2 += w * tp * tp
            m += 1
        if sw > 0:
            v = swp / sw; var = max(swp2 / sw - v * v, 0.0)
            FB[j, 0, 0] = v; FB[j, 0, 1] = np.sqrt(var) if var > 1e-12 else 0.0
        # Keltner
        if atr[j] > 0:
            FB[j, 3, 0] = em[j] - 2 * atr[j]; FB[j, 3, 1] = 4 * atr[j]
        # premium / discount, expansion
        if j >= 50:
            hi = -1e18; lo = 1e18
            for q in range(j - 49, j + 1):
                hi = max(hi, h15[q]); lo = min(lo, l15[q])
            if hi > lo:
                FB[j, 2, 0] = lo; FB[j, 2, 1] = hi - lo
        if j >= 20:
            hi = -1e18; lo = 1e18; hi2 = -1e18; lo2 = 1e18
            for q in range(j - 9, j + 1):
                hi = max(hi, h15[q]); lo = min(lo, l15[q])
            for q in range(j - 19, j - 9):
                hi2 = max(hi2, h15[q]); lo2 = min(lo2, l15[q])
            if hi2 > lo2:
                FB[j, 4, 0] = -(hi - lo) / (hi2 - lo2) * 1e9; FB[j, 4, 1] = 1e9
    # Initial Balance: London 10:00-11:00, NY 15:00-16:00 server time
    for j in range(n):
        h = (t15[j] // 3600) % 24; d0 = t15[j] - t15[j] % 86400
        st = -1
        if h >= 16:
            st = d0 + 15 * 3600
        elif h >= 11:
            st = d0 + 10 * 3600
        if st < 0:
            continue
        hi = -1e18; lo = 1e18; q = j
        while q >= 0 and t15[q] >= st:
            if t15[q] < st + 3600:
                hi = max(hi, h15[q]); lo = min(lo, l15[q])
            q -= 1
        if hi > lo:
            FB[j, 1, 0] = lo; FB[j, 1, 1] = hi - lo
    # developing H1 candle (closed M15 candles of the entry's hour so far; at the top of the hour: the hour that just closed)
    for j in range(n):
        hs = (t15[j] + 900) - (t15[j] + 900) % 3600
        if hs > t15[j]:
            hs -= 3600
        hi = -1e18; lo = 1e18; q = j
        while q >= 0 and t15[q] >= hs:
            hi = max(hi, h15[q]); lo = min(lo, l15[q]); q -= 1
        if hi > lo:
            FB[j, 6, 0] = lo; FB[j, 6, 1] = hi - lo
    # newest fair value gap in the last 20 candles
    for j in range(22, n):
        for q in range(j, j - 18, -1):
            if l15[q] > h15[q - 2]:
                FB[j, 7, 0] = h15[q - 2]; FB[j, 7, 1] = l15[q] - h15[q - 2]; break
            if h15[q] < l15[q - 2]:
                FB[j, 7, 0] = h15[q]; FB[j, 7, 1] = l15[q - 2] - h15[q]; break
    # Asian range 00:00-08:00 server, from 08:00 on
    for j in range(n):
        h = (t15[j] // 3600) % 24
        if h < 8:
            continue
        d0 = t15[j] - t15[j] % 86400
        hi = -1e18; lo = 1e18; q = j
        while q >= 0 and t15[q] >= d0:
            if t15[q] < d0 + 8 * 3600:
                hi = max(hi, h15[q]); lo = min(lo, l15[q])
            q -= 1
        if hi > lo:
            FB[j, 8, 0] = lo; FB[j, 8, 1] = hi - lo
    # value area of the last 40 candles (minutes weighted by ticks), 0.10 bins
    for j in range(40, n):
        a0 = m15end[j - 40] + 1; a1 = m15end[j]
        if a1 - a0 < 30:
            continue
        lo = 1e18; hi = -1e18
        for m in range(a0, a1 + 1):
            lo = min(lo, l1[m]); hi = max(hi, h1[m])
        nb = int((hi - lo) / 0.1) + 1
        if nb < 3 or nb > 20000:
            continue
        hist = np.zeros(nb); tot = 0.0
        for m in range(a0, a1 + 1):
            b = int(((h1[m] + l1[m] + c1[m]) / 3.0 - lo) / 0.1)
            hist[b] += w1[m]; tot += w1[m]
        poc = 0
        for b in range(nb):
            if hist[b] > hist[poc]:
                poc = b
        lo_b = poc; hi_b = poc; acc = hist[poc]
        while acc < 0.7 * tot and (lo_b > 0 or hi_b < nb - 1):
            up = hist[hi_b + 1] if hi_b < nb - 1 else -1.0
            dn = hist[lo_b - 1] if lo_b > 0 else -1.0
            if up >= dn:
                hi_b += 1; acc += up
            else:
                lo_b -= 1; acc += dn
        half = (hi_b - lo_b + 1) * 0.1 / 2.0
        if half > 0:
            FB[j, 5, 0] = lo + (poc + 0.5) * 0.1; FB[j, 5, 1] = half


def features(ds, D):
    if ds in _CACHE:
        return _CACHE[ds]
    if ds in ("year1", "m1x"):     # the EA judges its range boxes on M15 candles on any chart (PERIOD_M15): each minute gets the last M15 candle closed by its end
        import sim
        D15 = sim.data("m15"); F15 = features("m15", D15)
        t1 = np.asarray(D["t15"]).astype(np.int64)
        j15 = np.searchsorted(D15["t15"], t1 + 60 - 900, "right") - 1
        _CACHE[ds] = np.where((j15 >= 0)[:, None, None], F15[np.clip(j15, 0, None)], 0.0)
        return _CACHE[ds]
    from pathlib import Path
    fn = Path(__file__).parent / "simdata" / f"rbox{NF}_{ds}_{len(D['t15'])}_{int(D['t15'][-1])}.npy"   # disk cache: building takes ~2 min on m15
    if fn.exists():
        _CACHE[ds] = np.load(fn)
        return _CACHE[ds]
    t15, t1 = D["t15"], D["t1"]
    w1 = np.ones(len(t1))
    if ds == "m15":
        try:
            from pathlib import Path
            T = np.memmap(Path(__file__).parent / "simdata" / "m15_tick_raw_t.bin", dtype=np.float64, mode="r")
            ix = np.searchsorted(T, np.r_[t1, t1[-1] + 60].astype(np.float64))
            w1 = np.maximum(np.diff(ix).astype(np.float64), 1.0)
        except Exception:                                   # noqa: BLE001
            pass
    m15end = (np.searchsorted(t1, t15 + 900) - 1).astype(np.int64)
    FB = np.zeros((len(t15), NF, 2))
    _build(t15.astype(np.int64), D["o15"], D["h15"], D["l15"], D["c15"], D["atr"], t1.astype(np.int64), D["h1"], D["l1"], D["c1"], w1, m15end, FB)
    _CACHE[ds] = FB
    np.save(fn, FB)
    return FB


def with_disp(FB, ef, es, atr):
    """the run's own EMAs: dispersion (fast - slow) / ATR, independent of the entry price"""
    FB = FB.copy()
    v = np.where(atr > 0, (ef - es) / np.where(atr > 0, atr, 1), 0.0)
    FB[:, 9, 0] = -v * 1e9; FB[:, 9, 1] = np.where(atr > 0, 1e9, 0.0)
    return FB


def label_trades(ds, D, trades, ef=None, es=None):
    """box per family for each trade row (side x[0], entry time x[1], entry x[2]) -> list of NF ints"""
    FB = features(ds, D); t15 = D["t15"]
    if ef is not None:
        FB = with_disp(FB, ef, es, D["atr"])
    out = []
    for x in trades:
        j = int(np.searchsorted(t15, x[1], "right")) - 2
        out.append([int(box_of(FB, EDGES, NE, j, f, float(x[2]))) for f in range(NF)])
    return out


def spec():
    return [{"key": k, "title": t, "boxes": lab} for k, t, _, lab in FAM]
