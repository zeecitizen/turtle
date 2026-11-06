"""features.py (batch_1 study) - one row per trade of the 97.7% setting with features known at the entry
(bars <= k and the setup fields only), plus the outcome columns for ANALYSIS ONLY (loss, pnl, half).
The rules in rules.py never read the outcome; this table only helps decide which ideas to try.
Run: py features.py  -> writes feat.pkl next to this file."""
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, STUDY)
import api  # noqa: E402

A = api.A
PIP = api.PIP
o, h, l, c, v, atr, adx = A.o, A.h, A.l, A.c, A.v, A.atr, A.adx
N = len(c)


def ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


E30, E60, E120, E240 = ema(c, 30), ema(c, 60), ema(c, 120), ema(c, 240)
RNG = h - l


def us_dst(ts):
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    return dt.datetime(2026, 3, 8, 7, tzinfo=dt.timezone.utc) <= d < dt.datetime(2026, 11, 1, 6, tzinfo=dt.timezone.utc)


rows = []
for t in api.TRADES:
    k, kb, ku, s = t["k"], t["kb"], t["ku"], t["side"]
    a = atr[k]
    tin = t["t_in"]
    ny = tin - (4 if us_dst(tin) else 5) * 3600                      # New York local clock
    nyd = dt.datetime.fromtimestamp(ny, dt.timezone.utc)
    ny_min = nyd.hour * 60 + nyd.minute + nyd.second / 60
    to_roll = (17 * 60 - ny_min) % 1440                               # minutes until 17:00 NY (daily rollover)
    since_roll = (ny_min - 17 * 60) % 1440
    fxday = (nyd + dt.timedelta(hours=7)).weekday()                    # FX day: starts 17:00 NY; 4 = Friday session
    r = {"id": t["id"], "side": s, "half": "train" if tin < api.SPLIT else "test", "loss": int(not t["win"]), "pnl": t["pnl"],
         "why": t["why"], "utc_min": (tin % 86400) / 60, "ny_min": ny_min, "to_roll": to_roll, "since_roll": since_roll, "fxday": fxday,
         "sec": tin % 60}
    r["fri_to_close"] = to_roll if fxday == 4 else 9999
    r["slip"] = (t["fill"] - t["level"]) * s / PIP
    r["uhv_age"] = kb - ku
    r["depth"] = abs(t["level"] - t["extreme"]) / PIP
    r["depth_atr"] = abs(t["level"] - t["extreme"]) / a
    r["stop_pips"] = t["stop_pips"]
    r["brk"] = t["brk_ticks_so_far"]
    r["uhv_v"] = t["uhv_v"]
    r["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    r["brk_rate"] = t["brk_ticks_so_far"] / max(r["sec"], 1)
    r["atr_p"] = a / PIP
    r["adx"] = adx[k]
    r["atr_ratio"] = a / max(np.mean(RNG[max(k - 239, 0):k + 1]), 1e-9)
    r["rng5_ratio"] = np.mean(RNG[max(k - 4, 0):k + 1]) / max(np.mean(RNG[max(k - 119, 0):k + 1]), 1e-9)
    r["v5_60"] = np.mean(v[max(k - 4, 0):k + 1]) / max(np.mean(v[max(k - 59, 0):k + 1]), 1)
    r["v60_600"] = np.mean(v[max(k - 59, 0):k + 1]) / max(np.mean(v[max(k - 599, 0):k + 1]), 1)
    r["uhv_rel"] = t["uhv_v"] / max(np.mean(v[max(k - 59, 0):k + 1]), 1)
    r["uhv_rng_atr"] = (h[ku] - l[ku]) / a
    r["uhv_body_atr"] = abs(c[ku] - o[ku]) / a
    for n in (5, 15, 30, 60, 120, 240):
        r[f"tr{n}"] = (c[k] - c[max(k - n, 0)]) * s / a                       # + = price moved WITH the trade over n bars
    for n in (30, 60, 120, 240):
        hi, lo = h[max(k - n + 1, 0):k + 1].max(), l[max(k - n + 1, 0):k + 1].min()
        r[f"pos{n}"] = ((t["fill"] - lo) / (hi - lo) if s > 0 else (hi - t["fill"]) / (hi - lo)) if hi > lo else 0.5
        r[f"room{n}"] = ((hi - t["fill"]) if s > 0 else (t["fill"] - lo)) / PIP   # pips to the n-bar extreme the trade runs into
        r[f"back{n}"] = ((t["fill"] - lo) if s > 0 else (hi - t["fill"])) / PIP   # pips from the opposite n-bar extreme
        r[f"rng{n}_atr"] = (hi - lo) / a
    for n, e in ((30, E30), (60, E60), (120, E120), (240, E240)):
        r[f"ema{n}"] = (c[k] - e[k]) * s / a
    r["ema_slope60"] = (E60[k] - E60[k - 15]) * s / a
    r["ema_slope240"] = (E240[k] - E240[k - 30]) * s / a
    # counter-move in the last bars (the retracement's thrust, against the trade)
    r["ctr6"] = ((t["extreme"] - l[max(k - 5, 0):k + 1].min()) if s < 0 else (h[max(k - 5, 0):k + 1].max() - t["extreme"])) / a
    bodies = (c[max(k - 2, 0):k + 1] - o[max(k - 2, 0):k + 1]) * (-s)                    # + = body against the trade
    r["ctr_body3"] = bodies.max() / a
    r["k_body"] = (c[k] - o[k]) * s / a                                  # + = last closed bar went with the trade
    r["k_rng"] = RNG[k] / a
    r["max_rng10"] = RNG[max(k - 9, 0):k + 1].max() / a
    # camel
    r["camStk"] = abs(t["camStk"])
    r["camT"] = int(A.camT[k]) * s
    Hk = A.humps_known(k)
    last = Hk[-8:]
    r["opp_humps8"] = int(np.sum(last[:, 6] == -s))
    r["same_humps8"] = int(np.sum(last[:, 6] == s))
    r["last_hump_h"] = (last[-1, 3] - min(last[-1, 1], last[-1, 5])) / a if len(last) else 0
    r["hump_age"] = k - int(last[-1, 7]) if len(last) else 999
    # bigger-swing structure (pivots p=5 over 240 bars)
    hs, ls = A.pivots(k, p=5, look=240)
    if s > 0:
        r["lh"] = int(len(hs) >= 2 and hs[-1][1] < hs[-2][1])        # lower highs against a buy
        r["ll"] = int(len(ls) >= 2 and ls[-1][1] < ls[-2][1])
    else:
        r["lh"] = int(len(ls) >= 2 and ls[-1][1] > ls[-2][1])        # higher lows against a sell
        r["ll"] = int(len(hs) >= 2 and hs[-1][1] > hs[-2][1])
    rows.append(r)

df = pd.DataFrame(rows)
df.to_pickle(os.path.join(HERE, "feat.pkl"))
print(df.shape)
print(df.groupby("half")["loss"].agg(["count", "sum", "mean"]))
