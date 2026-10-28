"""Tick-replay cures on the ENGINE's own entries of 2026-10-25 05-58-25 (m15 2023->now). Each method acts on real bid/ask ticks
from the engine's entry; when it doesn't fire before the engine's exit, the engine's own result stands. Knock-on (a freed slot
taking a different later trade) is ignored. Tester-family hypothesis only."""
import sys, json, numpy as np
sys.path.insert(0, "research")
from _load import *
tr, st = trades()
D = sim.data("m15"); t15 = D["t15"]; c = D["c15"]; atr = D["atr"]
T = np.memmap("simdata/m15_tick_raw_t.bin", dtype=np.float64, mode="r")
B = np.memmap("simdata/m15_tick_raw_bid.bin", dtype=np.float64, mode="r")
A = np.memmap("simdata/m15_tick_raw_ask.bin", dtype=np.float64, mode="r")
G6 = np.load("research/gates6.npy")                     # pnl, spd, poc_ok, macd_ok, slope, atr, swept, hr, te (same order as tr)
LOT = 100.0
N = len(tr); P0 = tr[:, 6].copy(); TE = tr[:, 1]; MID = np.median(TE)


def stats(name, p, note=""):
    p = np.asarray(p, float); eq = np.cumsum(p); dd = (np.maximum.accumulate(eq) - eq).max(); w = p[p > 0]; l = p[p <= 0]
    r = dict(name=name, n=int(len(p)), wr=round(100 * len(w) / len(p), 1), net=round(p.sum()), worst=round(p.min()), dd=round(dd),
             aw=round(w.mean()) if len(w) else 0, al=round(l.mean()) if len(l) else 0,
             h1=round(p[TE < MID].sum()), h2=round(p[TE >= MID].sum()), note=note)
    print(f"{name:52s} n {r['n']:5d} WR {r['wr']:5.1f}% net {r['net']:+10,} worst {r['worst']:+7,} DD {r['dd']:7,} halves {r['h1']:+9,} {r['h2']:+9,} {note}", flush=True)
    return r


OUT = []
W = []
for x in tr:
    a = np.searchsorted(T, x[1]); b = np.searchsorted(T, x[4], "right"); f = np.searchsorted(T, x[1] + 5 * 86400)
    W.append((a, b, f))


def path(k, full=False):
    a, b, f = W[k]; e = f if full else b
    return np.asarray(T[a:e]), np.asarray(B[a:e]), np.asarray(A[a:e])


def mkt(sd, bb, aa):
    return bb if sd > 0 else aa                          # the price we exit at


def first(mask):
    i = np.flatnonzero(mask); return i[0] if len(i) else -1


OUT.append(stats("baseline (engine)", P0))

# 0 . replay check: TP $2 / engine SL only, capped at the engine exit
rp = []
for k, x in enumerate(tr):
    sd, e, sl = x[0], x[2], x[3]; t, bb, aa = path(k); px = mkt(sd, bb, aa)
    hit = first(((px - e) * sd >= 2.0) | ((px - sl) * sd <= 0))
    rp.append((px[hit] - e) * sd * 2 * LOT if hit >= 0 else P0[k])
OUT.append(stats("replay check (TP $2 + stop only)", rp, "replay vs engine"))

# 1 . Kaplan-Meier: how long winners and losers live
dur = (tr[:, 4] - tr[:, 1]) / 60; win = P0 > 0; big = P0 < -3000
km = {f"p{q}_min_win_vs_loss": [round(float(np.percentile(dur[win], q)), 1), round(float(np.percentile(dur[~win], q)), 1)] for q in (25, 50, 75, 90, 95)}
km["big_losers"] = int(big.sum())
km["big_losers_median_min"] = round(float(np.median(dur[big])), 1)
cross = []
for k in np.flatnonzero(big):
    sd, e = tr[k, 0], tr[k, 2]; t, bb, aa = path(k); px = mkt(sd, bb, aa); i = first((px - e) * sd <= -10)
    cross.append((t[i] - t[0]) / 60 if i >= 0 else np.nan)
km["big_losers_reach_minus10_median_min"] = round(float(np.nanmedian(cross)), 1)
fav = []
for k in np.flatnonzero(win):
    sd, e = tr[k, 0], tr[k, 2]; t, bb, aa = path(k); px = mkt(sd, bb, aa)
    fav.append(((px - e) * sd).min() if len(px) else 0)
km["winners_dip_beyond_10_pct"] = round(100 * float(np.mean(np.array(fav) <= -10)), 1)
print("KM", km, flush=True)


def early(name, fire, note=""):
    p = P0.copy()
    for k, x in enumerate(tr):
        sd, e = x[0], x[2]; t, bb, aa = path(k)
        if len(t) < 2: continue
        px = mkt(sd, bb, aa); i = fire(k, t, px, sd, e, x)
        if i >= 0: p[k] = (px[i] - e) * sd * 2 * LOT
    return stats(name, p, note)


# 2 . kinetic decay: ticks in the last 60 s < kf x the normal rate (4 h before entry) -> flatten, after the first 5 min
base_rate = np.array([(np.searchsorted(T, x[1]) - np.searchsorted(T, x[1] - 14400)) / 240 for x in tr])   # ticks per minute


def kin(kf, only_loss):
    def f(k, t, px, sd, e, x):
        cnt = np.arange(len(t)) - np.searchsorted(t, t - 60)
        ok = (t - t[0] >= 300) & (cnt < kf * base_rate[k])
        if only_loss: ok &= (px - e) * sd < 0
        return first(ok)
    return f


for kf in (0.25, 0.4, 0.6):
    for ol in (False, True):
        OUT.append(early(f"kinetic stop: 60s ticks < {kf}x normal{' (in loss)' if ol else ''}", kin(kf, ol)))


# 3 . exponential stop: allowed loss = $25 x exp(-minutes / tau)
def expo(tau):
    def f(k, t, px, sd, e, x):
        d = 25.0 * np.exp(-(t - t[0]) / 60 / tau)
        return first((px - e) * sd <= -d)
    return f


for tau in (15, 30, 60, 120, 240, 480):
    OUT.append(early(f"exponential stop: $25 x e^(-t/{tau}min)", expo(tau)))

# 4 . ghost stop: hidden from the broker, fires only when the MID price crosses it (spread spikes ignored); + 10 s confirmation
pg = P0.copy(); pg10 = P0.copy(); saved = [0, 0]
for k, x in enumerate(tr):
    if not (P0[k] < -3000): continue
    sd, e, sl = x[0], x[2], x[3]; t, bb, aa = path(k, True)
    mid = (bb + aa) / 2; px = mkt(sd, bb, aa)
    beyond = (mid - sl) * sd <= 0
    for ci, (conf, arr) in enumerate(((0, pg), (10, pg10))):
        if conf:
            i = -1
            for j in np.flatnonzero(beyond)[:20000]:
                m = np.searchsorted(t, t[j] + conf)
                if m < len(t) and beyond[j:m + 1].all(): i = m; break
        else:
            i = first(beyond)
        h = first((px - e) * sd >= 2.0)
        if h >= 0 and (i < 0 or h < i): arr[k] = 2.0 * 2 * LOT; saved[ci] += 1
        elif i >= 0: arr[k] = (px[i] - e) * sd * 2 * LOT
OUT.append(stats("ghost stop on MID price", pg, f"{saved[0]} big losers became wins"))
OUT.append(stats("ghost stop on MID + 10 s confirmation", pg10, f"{saved[1]} big losers became wins"))


# 5 . pyramiding on a 40-pip target (full replay: TP $4 + the engine's stop; the add has its stop at the original entry)
def pyr(name, add_at, add_lots, gate=None):
    p = []
    for k, x in enumerate(tr):
        sd, e, sl = x[0], x[2], x[3]; t, bb, aa = path(k, True); px = mkt(sd, bb, aa); ent = aa if sd > 0 else bb
        fv = (px - e) * sd
        end = first((fv >= 4.0) | ((px - sl) * sd <= 0)); end = end if end >= 0 else len(px) - 1
        r = fv[end] * 2 * LOT
        thr = add_at(k)
        if thr is not None and (gate is None or gate(k)):
            j = first(fv[:end + 1] >= thr)
            if j >= 0:
                fv2 = (px[j:] - ent[j]) * sd
                z = [q for q in (first((px[j:] - e) * sd <= 0), first(fv[j:] >= 4.0)) if q >= 0]
                z = min(z) if z else len(fv2) - 1
                r += fv2[z] * add_lots * LOT
        p.append(r)
    return stats(name, p)


bar = np.array([np.searchsorted(t15, te, "right") - 2 for te in TE])
OUT.append(pyr("TP 40 pips, no add (replay)", lambda k: None, 0))
OUT.append(pyr("ATR pyramid: +0.5 lot after +1 ATR (TP 40)", lambda k: max(0.3, atr[bar[k]]), 0.5))
atr_up = atr[bar] > atr[bar - 4]
OUT.append(pyr("momentum pyramid: +1 lot at +$2 if H1 MACD + ATR rising (TP 40)", lambda k: 2.0, 1.0, lambda k: G6[k, 3] > 0.5 and atr_up[k]))


# 6 . Kelly-style sizing by Kaufman ER(16): top third 3 lots, bottom third 0.5 (thresholds from the first half)
def er(i, n=16):
    return abs(c[i] - c[i - n]) / max(1e-9, np.abs(np.diff(c[i - n:i + 1])).sum())


ER = np.array([er(i) for i in bar])
lo, hi = np.percentile(ER[TE < MID], [33.3, 66.7])
OUT.append(stats("ER sizing: clean (high ER) 3 lots, messy 0.5", P0 * np.where(ER >= hi, 1.5, np.where(ER <= lo, 0.25, 1.0))))
OUT.append(stats("ER sizing reversed: high ER 0.5, low ER 3", P0 * np.where(ER >= hi, 0.25, np.where(ER <= lo, 1.5, 1.0))))

# 7 . exit agent (PPO stand-in: learned on half 1, judged on half 2). Every 5 min it sees floating P&L, minutes in trade,
#     worst dip so far, tick velocity vs normal; actions hold / close 50% / close 100%
from sklearn.ensemble import GradientBoostingClassifier
CK = 300; ROWS = []
for k, x in enumerate(tr):
    sd, e = x[0], x[2]; t, bb, aa = path(k); px = mkt(sd, bb, aa)
    if len(t) < 2: continue
    fv = (px - e) * sd; mae = np.minimum.accumulate(fv)
    for s in np.arange(t[0] + CK, t[-1], CK)[:48]:
        j = np.searchsorted(t, s) - 1
        vel = (j - np.searchsorted(t, t[j] - 60)) / max(1e-9, base_rate[k])
        ROWS.append((k, j, fv[j], (s - t[0]) / 60, mae[j], vel, 1.0 if x[1] < MID else 0.0))
R = np.array(ROWS); Y = (P0[R[:, 0].astype(int)] <= 0).astype(int)
trm = R[:, 6] > 0.5
clf = GradientBoostingClassifier(n_estimators=150, max_depth=3).fit(R[trm][:, 2:6], Y[trm])
PR = clf.predict_proba(R[:, 2:6])[:, 1]


def agent(thf, thh):
    p = P0.copy(); done = set()
    for row, pr in zip(R, PR):
        k = int(row[0]); j = int(row[1])
        if k in done: continue
        sd, e = tr[k, 0], tr[k, 2]; t, bb, aa = path(k); px = mkt(sd, bb, aa)
        if pr >= thf: p[k] = (px[j] - e) * sd * 2 * LOT; done.add(k)
        elif pr >= thh: p[k] = (px[j] - e) * sd * 1 * LOT + P0[k] / 2; done.add(k)
    return p


best = None
for thf in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    for thh in (thf, thf - 0.1, thf - 0.2):
        p = agent(thf, thh); trn = p[TE < MID].sum()
        if best is None or trn > best[0]: best = (trn, thf, thh, p)
OUT.append(stats(f"exit agent (fit on half 1; close p>{best[1]}, half p>{round(best[2], 2)})", best[3], "judge on half 2"))


# 8 . liquidation reversal: after each big stop-out, open the OPPOSITE way at the stop time with 3x / 4x the lots
def rev(mult, tp, sl):
    p = P0.copy(); n = 0
    for k, x in enumerate(tr):
        if P0[k] > -3000: continue
        sd = -x[0]; a = np.searchsorted(T, x[4]); f = np.searchsorted(T, x[4] + 5 * 86400)
        bb, aa = np.asarray(B[a:f]), np.asarray(A[a:f])
        if len(bb) < 2: continue
        e = aa[0] if sd > 0 else bb[0]; px = bb if sd > 0 else aa; fv = (px - e) * sd
        z = first((fv >= tp) | (fv <= -sl)); z = z if z >= 0 else len(fv) - 1
        p[k] += fv[z] * 2 * mult * LOT; n += 1
    return stats(f"reversal {mult}x lots after a stop-out (TP ${tp} / SL ${sl})", p, f"{n} reversals")


for mult in (3, 4):
    for tp, sl in ((2, 25), (5, 5), (10, 10), (25, 25)):
        OUT.append(rev(mult, tp, sl))
json.dump({"rows": OUT, "km": km}, open("research/cure_overlay.json", "w"), indent=1)
