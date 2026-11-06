"""feats.py - per-trade features computed ONLY from the setup fields and bars <= t['k'] (no future), for exploring
which chart observations separate losers from winners. Used for exploration; the rules in rules.py are self-contained."""
import numpy as np

PIP = 1e-4


def feats(t, A):
    k, ku, side = t["k"], t["ku"], t["side"]
    o, h, l, c, v = A.o, A.h, A.l, A.c, A.v
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)          # 0 = Monday ... 4 = Friday, 5 Sat, 6 Sun
    f = {"side": side, "tod_h": tod / 3600.0, "dow": dow}
    f["atr_p"] = A.atr[k] / PIP
    f["adx"] = float(A.adx[k])
    f["uhv_v"] = t["uhv_v"]
    f["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    f["stop_p"] = t["stop_pips"]
    f["camStk"] = abs(t["camStk"])
    f["age"] = k + 1 - ku                              # bars from UHV to the breakout minute
    v20 = v[k - 19:k + 1].mean(); v60 = v[k - 59:k + 1].mean(); v5 = v[k - 4:k + 1].mean(); v3 = v[k - 2:k + 1].mean()
    f["v20"] = v20; f["v60"] = v60; f["v3_v60"] = v3 / max(v60, 1); f["v5_v60"] = v5 / max(v60, 1)
    f["uhv_rel60"] = t["uhv_v"] / max(v60, 1)
    f["uhv_rank90"] = int((v[k - 89:k + 1] > t["uhv_v"]).sum())     # how many of the last 90 bars were louder than the UHV
    # UHV candle shape
    rng = h[ku] - l[ku]
    f["uhv_rng_p"] = rng / PIP
    f["uhv_body"] = abs(c[ku] - o[ku]) / rng if rng > 0 else 0
    # close location against the trade: for a buy (red UHV) 1 = closed at its low; for a sell (green UHV) 1 = closed at its high
    f["uhv_cl_against"] = ((h[ku] - c[ku]) / rng if side > 0 else (c[ku] - l[ku]) / rng) if rng > 0 else 0.5
    # room to the recent extreme in the trade direction (pips): buy -> N-bar high above the level; sell -> level above N-bar low
    for N in (20, 40, 90):
        hi, lo = h[k - N + 1:k + 1].max(), l[k - N + 1:k + 1].min()
        f[f"room{N}"] = ((hi - t["level"]) if side > 0 else (t["level"] - lo)) / PIP
        f[f"pos{N}"] = ((t["level"] - lo) / (hi - lo) if side > 0 else (hi - t["level"]) / (hi - lo)) if hi > lo else 0.5
        f[f"rng{N}"] = (hi - lo) / PIP
    # move over the last N bars in the trade direction (pips)
    for N in (30, 60, 120):
        f[f"mv{N}"] = (c[k] - c[k - N]) * side / PIP
    # level touched between the UHV and the entry (a re-break): bars ku+1..k with high >= level (buy) / low <= level (sell)
    seg_h, seg_l = h[ku + 1:k + 1], l[ku + 1:k + 1]
    f["touch"] = int((seg_h >= t["level"]).sum()) if side > 0 else int((seg_l <= t["level"]).sum())
    f["spread_b"] = (t["fill"] - t["level"]) / PIP * side   # buy: ask fill - bid level ~ spread; sell: level - fill
    return f


def feats2(t, A):
    """camel-hump quality, rejection wicks beyond the level, exhaustion - all from bars <= k."""
    k, ku, side = t["k"], t["ku"], t["side"]
    o, h, l, c, v = A.o, A.h, A.l, A.c, A.v
    f = {}
    H = A.humps_known(k)
    if len(H) >= 2:
        b0, v0, bh, vh, b1, v1, tr, kn = H[-1]
        pb0, pv0, pbh, pvh, pb1, pv1, ptr, pkn = H[-2]
        f["hump_tr"] = int(tr)
        f["hump_margin"] = (v1 - v0) / PIP * side            # >0 = the latest hump agrees with the trade side, size of the higher low (pips)
        f["hump_hh"] = (vh - pvh) / PIP * side               # buy: this hump's high above the previous hump's high (pips); sell: lower high
        f["hump_age"] = k - int(kn)                          # bars since the latest hump was confirmed
        f["hump_len"] = int(b1 - b0)
        f["hump_size"] = (vh - min(v0, v1)) / PIP
    else:
        f.update(hump_tr=0, hump_margin=0, hump_hh=0, hump_age=0, hump_len=0, hump_size=0)
    # rejection wick just beyond the level in the last 10 closed bars: buy -> a bar whose high is above the level by 0..3 pips with an upper wick
    # >= 50% of its range; sell -> mirror (lower wick below the level)
    best = 0.0
    for j in range(k - 9, k + 1):
        rng = h[j] - l[j]
        if rng <= 0:
            continue
        if side > 0:
            beyond = (h[j] - t["level"]) / PIP; wick = (h[j] - max(o[j], c[j])) / rng
        else:
            beyond = (t["level"] - l[j]) / PIP; wick = (min(o[j], c[j]) - l[j]) / rng
        if 0 <= beyond <= 3 and wick >= 0.5:
            best = max(best, wick)
    f["rej_wick"] = best
    # exhaustion: the move into the retracement extreme from the 60-bar opposite extreme, in ATRs
    f["ext60_atr"] = ((h[k - 59:k + 1].max() - t["level"]) if side < 0 else (t["level"] - l[k - 59:k + 1].min())) / max(A.atr[k], 1e-6)
    # loudest bar of the last 60 (excluding the UHV): ratio of UHV volume to it
    vv = v[k - 59:k + 1].copy()
    f["uhv_vs_max60"] = t["uhv_v"] / max(vv.max(), 1)
    # trend age: bars since the last opposite-colour hump among the known humps
    n_same = 0
    for row in H[::-1]:
        if int(row[6]) == side:
            n_same += 1
        else:
            break
    f["same_humps"] = n_same
    return f


def feats3(t, A):
    k, side = t["k"], t["side"]
    f = {}
    f["sec"] = t["t_in"] % 60                                           # seconds into the breakout minute
    f["brk_ticks"] = t["brk_ticks_so_far"]
    f["dip"] = (t["level"] - t["brk_lo_so_far"]) / PIP if side > 0 else (t["brk_hi_so_far"] - t["level"]) / PIP   # adverse excursion in the minute before the break
    f["mrng"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
    f["prev_gap"] = (t["level"] - A.c[k]) / PIP * side                 # how far the last closed candle closed short of the level
    f["prev_dir"] = 1 if (A.c[k] - A.o[k]) * side > 0 else (-1 if (A.c[k] - A.o[k]) * side < 0 else 0)   # last closed candle with (+1) / against (-1) the trade
    f["tick_rate"] = t["brk_ticks_so_far"] / max(f["sec"], 1)          # ticks per second in the breakout minute so far
    f["rate_vs_uhv"] = f["tick_rate"] / max(t["uhv_v"] / 60.0, 0.01)
    f["rate_vs_v20"] = f["tick_rate"] / max(A.v[k - 19:k + 1].mean() / 60.0, 0.01)
    return f


def feats4(t, A):
    """larger context: the day so far (UTC day), round numbers, news-spike aftermath."""
    k, side, lvl = t["k"], t["side"], t["level"]
    h, l, c, v = A.h, A.l, A.c, A.v
    f = {}
    day0 = (int(A.t[k]) // 86400) * 86400
    j0 = int(np.searchsorted(A.t, day0))
    j0 = min(j0, k)
    dh, dl = h[j0:k + 1].max(), l[j0:k + 1].min()
    f["day_rng"] = (dh - dl) / PIP
    f["day_room"] = ((dh - lvl) if side > 0 else (lvl - dl)) / PIP        # room to the day's extreme in the trade direction
    f["day_pos"] = ((lvl - dl) / (dh - dl) if side > 0 else (dh - lvl) / (dh - dl)) if dh > dl else 0.5
    # previous 24h range for scale
    a24 = max(0, k - 1439)
    f["d24_rng"] = (h[a24:k + 1].max() - l[a24:k + 1].min()) / PIP
    f["day_used"] = f["day_rng"] / max(f["d24_rng"], 1e-6)
    # round numbers ahead of the trade (50-pip and 10-pip), distance in pips (999 if none within 10 pips)
    def ahead(step):
        x = lvl / (step * PIP)
        nxt = (np.floor(x) + 1) * step * PIP if side > 0 else np.ceil(x - 1) * step * PIP
        if side > 0:
            nxt = np.ceil(x + 1e-9) * step * PIP
        else:
            nxt = np.floor(x - 1e-9) * step * PIP
        d = (nxt - lvl) / PIP * side
        return d
    f["rn50"] = ahead(50)
    f["rn10"] = ahead(10)
    # news aftermath: biggest candle range of the last 60 vs the median range of the last 60
    rr = (h[k - 59:k + 1] - l[k - 59:k + 1]) / PIP
    f["spike60"] = rr.max() / max(np.median(rr), 0.1)
    f["spike_age"] = 59 - int(np.argmax(rr))
    return f
