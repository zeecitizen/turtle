"""rules.py (batch_3) - loss-fix rules for the 97.7% UHV setting. Each rule: def rule(t, A) -> True = SKIP the trade.
Every rule reads only the setup fields of t and bars <= t["k"] (the last closed candle before the entry); no helper is shared, so each
function can be copied on its own. Times are UTC (server time); dow: 0 Sun .. 5 Fri (1970-01-01 was a Thursday)."""
import math  # noqa: F401

import numpy as np  # noqa: F401


# ---------------------------------------------------------------- 1. the weekly close: late Friday
def fri_late17(t, A):
    """Friday from 17:00 UTC: a trade that does not reach its 1-pip target fast is held into the thin close and force-closed at 20:58."""
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 17 * 3600


def fri_late16(t, A):
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 16 * 3600


def fri_late18(t, A):
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 18 * 3600


def fri_late19(t, A):
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 19 * 3600


def fri_late20(t, A):
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 20 * 3600


def fri_late14(t, A):
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and (t["t_in"] % 86400) >= 14 * 3600


# ---------------------------------------------------------------- 2. the fill is already far past the level (wide spread / spike)
def slip_12(t, A):
    """The fill is 1.2+ pips beyond the UHV level (buy: ask above the high = spread + jump; sell: bid below the low = jump). The 0.1-pip
    target then needs the price to run that much further before it pays; a wide spread is the thin-market signature (rollover, news)."""
    return (t["fill"] - t["level"]) * t["side"] >= 1.2 * A.PIP


def slip_10(t, A):
    return (t["fill"] - t["level"]) * t["side"] >= 1.0 * A.PIP


def slip_15(t, A):
    return (t["fill"] - t["level"]) * t["side"] >= 1.5 * A.PIP


def slip_20(t, A):
    return (t["fill"] - t["level"]) * t["side"] >= 2.0 * A.PIP


def slip_08(t, A):
    return (t["fill"] - t["level"]) * t["side"] >= 0.8 * A.PIP


# ---------------------------------------------------------------- 3. the daily rollover (spread blow-out)
def rollover_2045_2200(t, A):
    s = t["t_in"] % 86400
    return 20 * 3600 + 45 * 60 <= s < 22 * 3600


def rollover_2100_2200(t, A):
    s = t["t_in"] % 86400
    return 21 * 3600 <= s < 22 * 3600


# ---------------------------------------------------------------- 4. thin market
def low_vol60_30(t, A):
    """Mean tick volume of the last 60 closed candles < 30: a dead market where the 1-pip follow-through does not come."""
    k = t["k"]
    return float(np.mean(A.v[k - 59:k + 1])) < 30


def low_vol60_40(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 59:k + 1])) < 40


# ---------------------------------------------------------------- 5. ideas from the charts that the data did NOT confirm (kept so nobody retries)
def struct_broken(t, A):
    """The retracement already went beyond the camel's opposite swing (sell: above the hump's high; buy: below its last low) - the
    camel colour is stale (losses 0417-084606-S, 0427-150215-B)."""
    k = t["k"]
    return (t["extreme"] > A.camHV[k]) if t["side"] < 0 else (t["extreme"] < A.camLV[k])


def struct_broken_2p(t, A):
    k = t["k"]
    d = (t["extreme"] - A.camHV[k]) if t["side"] < 0 else (A.camLV[k] - t["extreme"])
    return d >= 2.0 * A.PIP


def exhaustion(t, A):
    """Selling the fresh low / buying the fresh high after a strong trend leg: ADX >= 40, the last 60 candles moved >= 3 ATR in the trade
    direction and the level sits in the bottom (sell) / top (buy) quarter of the 60-candle range (losses 0409-062811-S, 0409-110305-S,
    0413-064826-S, 0413-120919-S)."""
    k, s, lv = t["k"], t["side"], t["level"]
    atr = max(float(A.atr[k]), 1e-6)
    hi, lo = float(A.h[k - 59:k + 1].max()), float(A.l[k - 59:k + 1].min())
    pos = ((lv - lo) if s < 0 else (hi - lv)) / (hi - lo) if hi > lo else 0.5
    tr = (A.c[k] - A.c[k - 60]) * s / atr
    return A.adx[k] >= 40 and tr >= 3 and pos <= 0.25


def near_fresh_extreme(t, A):
    """The level is within 1.5 pips of the 10-candle extreme in the trade direction (selling right above the fresh low)."""
    k, s, lv = t["k"], t["side"], t["level"]
    if s < 0:
        d = lv - float(A.l[k - 9:k + 1].min())
    else:
        d = float(A.h[k - 9:k + 1].max()) - lv
    return 0 <= d <= 1.5 * A.PIP


def counter_trend60(t, A):
    """The last 60 candles moved >= 3 ATR AGAINST the trade (a bounce camel inside a bigger opposite leg: losses 0416-045923-B,
    0421-151800-B, 0423-164516-B)."""
    k, s = t["k"], t["side"]
    return (A.c[k] - A.c[k - 60]) * s / max(float(A.atr[k]), 1e-6) <= -3


def stale_uhv(t, A):
    """The UHV candle is 10+ candles old at the break (losses 0414-025520-S, 0416-045923-B)."""
    return t["k"] - t["ku"] >= 10


def retest_floor(t, A):
    """The level was touched (within 1 pip) by 15+ of the last 30 candles' lows (sell) / highs (buy): selling a floor that keeps holding."""
    k, s, lv = t["k"], t["side"], t["level"]
    seg = A.l[k - 29:k + 1] if s < 0 else A.h[k - 29:k + 1]
    d = ((seg - lv) if s < 0 else (lv - seg)) / A.PIP
    return int(np.sum((d <= 1.0) & (d >= -1.0))) >= 15


def low_atr_asia(t, A):
    """ATR < 0.7 pip between 22:00 and 06:00 UTC (dead Asian tape: losses 0414-025520-S, 0416-045923-B)."""
    h = (t["t_in"] % 86400) // 3600
    return A.atr[t["k"]] < 0.7 * A.PIP and (h >= 22 or h < 6)


def tiny_last_bar(t, A):
    """The last closed candle's range < 0.5 pip (no activity right before the break)."""
    k = t["k"]
    return (A.h[k] - A.l[k]) < 0.5 * A.PIP


def sunday_open(t, A):
    """The first 3 hours after the Sunday open (thin, gap-fill tape: loss 0426-222526-S)."""
    return int((t["t_in"] // 86400 + 4) % 7) == 0


def late_ny(t, A):
    """19:00-23:00 UTC any day (late New York / pre-rollover)."""
    h = (t["t_in"] % 86400) // 3600
    return 19 <= h < 23


# ---------------------------------------------------------------- 6. the big figure in the way of the 1-pip target
def bigfig_ahead10(t, A):
    """A 100-pip round number (1.1700, 1.1800 ...) lies 0-1.0 pip beyond the UHV level in the trade direction: the take-profit (spread + 0.1
    pip past the level) must pierce the big figure, where resting orders sit (loss 0408-075606-B: target exactly 1.17000)."""
    lv, s = t["level"], t["side"]
    near = round(lv / 0.01) * 0.01
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 1.0


def bigfig_ahead08(t, A):
    lv, s = t["level"], t["side"]
    near = round(lv / 0.01) * 0.01
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 0.8


def bigfig_ahead15(t, A):
    lv, s = t["level"], t["side"]
    near = round(lv / 0.01) * 0.01
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 1.5


def bigfig_ahead20(t, A):
    lv, s = t["level"], t["side"]
    near = round(lv / 0.01) * 0.01
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 2.0


def fig50_ahead10(t, A):
    """Same with every 50-pip number (1.1750 too)."""
    lv, s = t["level"], t["side"]
    near = round(lv / 0.005) * 0.005
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 1.0


def fig20_ahead10(t, A):
    lv, s = t["level"], t["side"]
    near = round(lv / 0.002) * 0.002
    d = round((near - lv) * s / A.PIP, 1)
    return 0.0 <= d <= 1.0


# ---------------------------------------------------------------- 7. combined session rule (weekly close + daily rollover)
def session_close(t, A):
    """Skip Friday from 17:00 UTC (held into the weekly close) and every day 20:45-22:00 UTC (rollover: spread blow-out, dead tape)."""
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    return (fri and s >= 17 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600)


def session_close19(t, A):
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    return (fri and s >= 19 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600)


# ---------------------------------------------------------------- 8. the combined liquidity guard (the recommended rule)
def liquidity_guard(t, A):
    """Stand aside when the 1-pip follow-through cannot be trusted: (a) Friday from 17:00 UTC (held into the weekly close), (b) every day
    20:45-22:00 UTC (rollover spread blow-out), (c) the fill is already 1.5+ pips past the UHV level (wide spread / spike fill),
    (d) the last 60 closed candles averaged < 30 ticks (dead tape)."""
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    if (fri and s >= 17 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600):
        return True
    if (t["fill"] - t["level"]) * t["side"] >= 1.5 * A.PIP:
        return True
    k = t["k"]
    return float(np.mean(A.v[k - 59:k + 1])) < 30


def liquidity_guard_bigfig(t, A):
    """liquidity_guard + a 100-pip big figure 0-1 pip beyond the level."""
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    if (fri and s >= 17 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600):
        return True
    if (t["fill"] - t["level"]) * t["side"] >= 1.5 * A.PIP:
        return True
    k = t["k"]
    if float(np.mean(A.v[k - 59:k + 1])) < 30:
        return True
    near = round(t["level"] / 0.01) * 0.01
    d = round((near - t["level"]) * t["side"] / A.PIP, 1)
    return 0.0 <= d <= 1.0


def liquidity_guard_strict(t, A):
    """The tighter variant: Friday from 19:00, rollover 20:45-22:00, fill 2+ pips past the level, 60-candle mean < 30 ticks."""
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    if (fri and s >= 19 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600):
        return True
    if (t["fill"] - t["level"]) * t["side"] >= 2.0 * A.PIP:
        return True
    k = t["k"]
    return float(np.mean(A.v[k - 59:k + 1])) < 30


# ---------------------------------------------------------------- 9. the corrected structure test (colour-setting hump as known at its redraw bar)
def struct_broken_colour(t, A):
    """The retracement went beyond the hump that SET the camel colour (as the per-bar camel state showed it at that hump's last redraw,
    bar j <= k): sell - above that red hump's high; buy - below that green hump's end low. Losses 0417-084606-S (+6.5 pips) and
    0427-150215-B (+2.0). (camHV[k] itself can already be the retracement's own high, so struct_broken mis-measured the sells.)"""
    k = t["k"]
    LV, ST = A.camLV, A.camStk
    j = k
    while j > k - 400 and LV[j] == LV[k] and ST[j] == ST[k]:
        j -= 1
    j += 1
    if t["side"] < 0:
        return t["extreme"] - float(A.camHV[j]) >= 2.0 * A.PIP
    return float(A.camLV[j]) - t["extreme"] >= 2.0 * A.PIP


def micro_hump_flip(t, A):
    """The camel's colour comes from ONE hump (camStk +-1) whose smaller leg is under 1 pip: a noise flip, not a trend (losses
    0416-045923-B, 0423-164516-B, 0414-025520-S, 0426-222526-S)."""
    k = t["k"]
    if abs(t["camStk"]) != 1:
        return False
    LV, ST = A.camLV, A.camStk
    j = k
    while j > k - 400 and LV[j] == LV[k] and ST[j] == ST[k]:
        j -= 1
    j += 1
    hv, lv, l0 = float(A.camHV[j]), float(A.camLV[j]), float(A.camL0V[j])
    return min(hv - lv, hv - l0) < 1.0 * A.PIP


# ---------------------------------------------------------------- 10. final candidates (simplest form)
def session_slip20(t, A):
    """session_close + the fill already 2+ pips past the level (a spike / blown spread outside the close windows)."""
    s = t["t_in"] % 86400
    fri = int((t["t_in"] // 86400 + 4) % 7) == 5
    if (fri and s >= 17 * 3600) or (20 * 3600 + 45 * 60 <= s < 22 * 3600):
        return True
    return (t["fill"] - t["level"]) * t["side"] >= 2.0 * A.PIP


def fri_17_19(t, A):
    """Only the Friday 17:00-19:00 UTC slice (to show the 17:00 start is not riding on the close itself)."""
    s = t["t_in"] % 86400
    return int((t["t_in"] // 86400 + 4) % 7) == 5 and 17 * 3600 <= s < 19 * 3600


def rollover_2115_2200(t, A):
    """Only the part of the rollover hour that the existing 20:45-21:15 example window does not cover."""
    s = t["t_in"] % 86400
    return 21 * 3600 + 15 * 60 < s < 22 * 3600
