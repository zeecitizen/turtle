"""rules.py - batch_1 loss-study rules for the 97.7% setting (EUR/USD 1-min UHV engine).

Every rule is   def rule_x(t, A) -> bool   (True = SKIP the trade). Each function is SELF-CONTAINED (only numpy as np and
math, no helpers), so its source can be shipped on its own as `def rule(t, A)`. Rules read only the setup fields of t and
bars <= t["k"]. Python tick replay = HYPOTHESIS ONLY; nothing here is promoted until MT5's Strategy Tester confirms it.

Time handling: US DST 2026 runs 2026-03-08 07:00 UTC (1772953200) -> 2026-11-01 06:00 UTC (1793512800); New York = UTC-4
inside, UTC-5 outside. The FX day rolls at 17:00 New York (the weekly close is Friday 17:00 NY, the engine flattens at 16:58).
Weekday from an epoch: (floor(ts / 86400) + 3) % 7 -> Monday = 0 ... Friday = 4.
"""
import math

import numpy as np


# ======================================================================================= GOOD candidates (time / liquidity)

def rule_rollover_2h(t, A):
    """The hour before and the hour after the 17:00 New York rollover (NY 16:00-18:00): spreads blow out, liquidity
    vanishes, and on Fridays this is the forced weekly close."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    m = (ny % 86400) / 60.0
    return 960.0 <= m < 1080.0


def rule_friday_last4h(t, A):
    """Friday after 13:00 New York (the last 4 hours of the week): London has gone home, the US afternoon is thin, and any
    trade that has not reached its 0.1-pip target is flattened at 16:58 NY - it cannot wait out a dip."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    return wd == 4 and 780.0 <= m < 1020.0


def rule_time_windows(t, A):
    """OR of rule_rollover_2h and rule_friday_last4h."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    return (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0)


def rule_buy_spread_1p5(t, A):
    """BUY entered while the spread is blown out: the fill (ask) is >= 1.5 pips above the breakout bid (brk_hi_so_far is
    the breakout tick's bid for a buy). The 0.1-pip target needs the bid to climb over the whole spread. Visible on buys only
    (a sell fills at the bid, so its spread is not in the setup fields). 1.5 pips is well above both spread regimes
    (Mar-May median ~0.5, Jun-Nov ~0.1)."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 1.5e-4


def rule_slip_1p5(t, A):
    """Symmetric version: the fill is >= 1.5 pips beyond the UHV level in the trade direction (for buys this includes the
    spread, for sells it is the breakout tick's jump)."""
    return (t["fill"] - t["level"]) * t["side"] >= 1.5e-4


def rule_time_or_spread(t, A):
    """The combined keeper: rollover hours OR Friday's last 4 hours OR a blown-out buy spread."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    if (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0):
        return True
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 1.5e-4


def rule_example_utc_close(t, A):
    """The api.py docstring example, for comparison: 20:45-21:15 UTC."""
    x = t["t_in"] % 86400
    return 74700 <= x <= 76500


# ---------------------------------------------------------------- variants of the time windows (reported, not cherry-picked)

def rule_rollover_tight(t, A):
    """Variant: 16:30-18:00 NY (30 min before + 60 min after the rollover)."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    m = (ny % 86400) / 60.0
    return 990.0 <= m < 1080.0


def rule_friday_last3h(t, A):
    """Variant: Friday after 14:00 New York."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    return wd == 4 and 840.0 <= m < 1020.0


def rule_friday_last6h(t, A):
    """Variant: Friday after 11:00 New York (London close onwards)."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    return wd == 4 and 660.0 <= m < 1020.0


def rule_buy_spread_1p0(t, A):
    """Variant: buy spread >= 1.0 pip (expected to fire mostly in the wide-spread Mar-May regime)."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 1.0e-4


def rule_buy_spread_2p0(t, A):
    """Variant: buy spread >= 2.0 pips."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 2.0e-4


# ======================================================================================= thin-market ideas (raw + residual)

def rule_thin_hour(t, A):
    """The last hour's tick volume is < 40% of the last 10 hours' average (a dead market)."""
    k = t["k"]
    v = A.v
    a = float(np.mean(v[max(k - 59, 0):k + 1]))
    b = float(np.mean(v[max(k - 599, 0):k + 1]))
    return b > 0 and a / b < 0.4


def rule_thin_hour_resid(t, A):
    """rule_thin_hour on trades OUTSIDE the time windows (is it more than the clock in disguise?)."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    if (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0):
        return False
    k = t["k"]
    v = A.v
    a = float(np.mean(v[max(k - 59, 0):k + 1]))
    b = float(np.mean(v[max(k - 599, 0):k + 1]))
    return b > 0 and a / b < 0.4


def rule_small_uhv(t, A):
    """The UHV candle has fewer than 50 ticks (the 'loudest' candle is quiet - thin market)."""
    return t["uhv_v"] < 50


def rule_small_uhv_resid(t, A):
    """rule_small_uhv outside the time windows."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    if (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0):
        return False
    return t["uhv_v"] < 50


def rule_brk_ratio_0p9(t, A):
    """The breakout minute already has >= 90% of the UHV's ticks - the 'quieter breakout' is barely quieter."""
    return t["brk_ticks_so_far"] >= 0.9 * max(t["uhv_v"], 1.0)


def rule_dead_last_bar(t, A):
    """The last closed candle's range is < 0.35 ATR (a dead candle right before the breakout)."""
    k = t["k"]
    a = A.atr[k]
    return a > 0 and (A.h[k] - A.l[k]) < 0.35 * a


# ======================================================================================= chart ideas from batch_1 (structure)

def rule_sr_at_fill(t, A):
    """Sell into an older swing low / buy into an older swing high: a p=2 pivot from the last 180 bars, formed before the UHV,
    within 0.3 pip of the fill (0310-141312-S, 0311-135106-S, 0316-163307-S, 0309-080004-B, 0312-172306-B)."""
    k, s, f = t["k"], t["side"], t["fill"]
    h, l = A.h, A.l
    lim = t["ku"] - 1
    for j in range(max(2, k - 180), min(k - 2, lim)):
        if s < 0:
            if l[j] <= l[j - 1] and l[j] <= l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2] and abs(f - l[j]) <= 0.3e-4:
                return True
        else:
            if h[j] >= h[j - 1] and h[j] >= h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2] and abs(f - h[j]) <= 0.3e-4:
                return True
    return False


def rule_impulse_bar_against(t, A):
    """Fading an impulse: one of the last 3 closed candles is a wide-range bar (>= 2.5 ATR) whose body points AGAINST the
    trade (0311-001150-S, 0316-132404-S)."""
    k, s = t["k"], t["side"]
    a = A.atr[k]
    if not a > 0:
        return False
    for j in range(k - 2, k + 1):
        if (A.c[j] - A.o[j]) * (-s) > 0 and (A.h[j] - A.l[j]) >= 2.5 * a:
            return True
    return False


def rule_fresh_flip_after_opp(t, A):
    """First hump of a new colour after >= 3 humps of the other colour in a row: a camel flip on a micro-bounce inside an
    older trend (0313-195816-B, 0316-052008-B, 0306-102926-B, 0312-062215-S)."""
    s = t["side"]
    if abs(t["camStk"]) != 1:
        return False
    H = A.humps
    H = H[H[:, 7] <= t["k"]]
    tr = H[:, 6][::-1]
    i = 0
    while i < len(tr) and tr[i] == s:
        i += 1
    j = i
    while j < len(tr) and tr[j] == -s:
        j += 1
    return (j - i) >= 3


def rule_structure_against(t, A):
    """The last two p=2 swing highs AND lows both point against the trade (lower highs + lower lows for a buy)."""
    k, s = t["k"], t["side"]
    h, l = A.h, A.l
    hs, ls = [], []
    for j in range(max(2, k - 120), k - 1):
        if h[j] >= h[j - 1] and h[j] >= h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
            hs.append(h[j])
        if l[j] <= l[j - 1] and l[j] <= l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
            ls.append(l[j])
    if len(hs) < 2 or len(ls) < 2:
        return False
    if s > 0:
        return hs[-1] < hs[-2] and ls[-1] < ls[-2]
    return hs[-1] > hs[-2] and ls[-1] > ls[-2]


def rule_exhausted_streak(t, A):
    """A mature trend: >= 6 humps of the same colour in a row (0317-062554-S was RED x8)."""
    return abs(t["camStk"]) >= 6


def rule_trend_against_120(t, A):
    """Price moved >= 12 ATR against the trade over the last 120 candles (buying a 2-hour downtrend's first bounce)."""
    k, s = t["k"], t["side"]
    a = A.atr[k]
    return a > 0 and (A.c[k] - A.c[max(k - 120, 0)]) * s <= -12 * a


def rule_extended_at_extreme(t, A):
    """The trade enters at the 60-candle extreme after a >= 20-pip run (buying the top of a run / selling the bottom of a
    slide: 0310-004311-B, 0310-141312-S, 0316-163307-S)."""
    k, s, f = t["k"], t["side"], t["fill"]
    hi = float(np.max(A.h[max(k - 59, 0):k + 1]))
    lo = float(np.min(A.l[max(k - 59, 0):k + 1]))
    if s > 0:
        return (f - lo) >= 20e-4 and (hi - f) <= 1e-4
    return (hi - f) >= 20e-4 and (f - lo) <= 1e-4


def rule_uhv_last_bar(t, A):
    """The UHV is the last closed candle (the breakout comes in the very next minute - the retracement's loudest candle has
    had no time to be absorbed)."""
    return t["ku"] == t["k"]


def rule_old_uhv(t, A):
    """The UHV candle is >= 10 minutes old at the breakout (0312-172306-B 15 min, 0318-205350-S 13, 0318-230007-S 16)."""
    return t["kb"] - t["ku"] >= 10


def rule_top_of_hour(t, A):
    """The breakout happens in minute :00 of an hour (session opens and scheduled releases fall on the hour:
    0309-080004-B at 08:00:04 UTC, 0318-230007-S at 23:00:07)."""
    return int((t["t_in"] % 3600) // 60) == 0


def rule_deep_retracement(t, A):
    """The retracement extreme is >= 5 pips beyond the level (a deep pullback -> stop >= 24 pips: 0306-102926-B 6.4 pips,
    0312-172306-B 10.4 pips)."""
    return abs(t["level"] - t["extreme"]) >= 5e-4


ALL = [
    rule_rollover_2h, rule_friday_last4h, rule_time_windows, rule_buy_spread_1p5, rule_slip_1p5, rule_time_or_spread,
    rule_example_utc_close,
    rule_rollover_tight, rule_friday_last3h, rule_friday_last6h, rule_buy_spread_1p0, rule_buy_spread_2p0,
    rule_thin_hour, rule_thin_hour_resid, rule_small_uhv, rule_small_uhv_resid, rule_brk_ratio_0p9, rule_dead_last_bar,
    rule_sr_at_fill, rule_impulse_bar_against, rule_fresh_flip_after_opp, rule_structure_against, rule_exhausted_streak,
    rule_trend_against_120, rule_extended_at_extreme, rule_uhv_last_bar, rule_old_uhv, rule_top_of_hour, rule_deep_retracement,
]


# ======================================================================================= second round (after the first scores)

def rule_dead_last_bar_resid(t, A):
    """rule_dead_last_bar outside the time windows (is the dead candle more than the clock?)."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    if (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0):
        return False
    k = t["k"]
    a = A.atr[k]
    return a > 0 and (A.h[k] - A.l[k]) < 0.35 * a


def rule_sell_slip_1p5(t, A):
    """Sells only: the breakout bid is >= 1.5 pips below the level (a jump through the level)."""
    return t["side"] < 0 and (t["level"] - t["fill"]) >= 1.5e-4


def rule_time_or_slip(t, A):
    """THE KEEPER: rollover hours (NY 16:00-18:00) OR Friday's last 4 hours (NY 13:00-17:00) OR a fill >= 1.5 pips beyond the
    UHV level (blown-out spread on a buy / a jump through the level)."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    wd = (math.floor(ny / 86400) + 3) % 7
    m = (ny % 86400) / 60.0
    if (960.0 <= m < 1080.0) or (wd == 4 and 780.0 <= m < 1020.0):
        return True
    return (t["fill"] - t["level"]) * t["side"] >= 1.5e-4


ALL += [rule_dead_last_bar_resid, rule_sell_slip_1p5, rule_time_or_slip]


def rule_us_news_windows(t, A):
    """Scheduled US data: NY 08:20-08:40 (8:30 releases) or 09:50-10:10 (10:00 releases). 0311-135106-S sold 9 minutes before
    a 10:00 NY spike that ran 30 pips."""
    ts = t["t_in"]
    ny = ts - (4 if 1772953200 <= ts < 1793512800 else 5) * 3600
    m = (ny % 86400) / 60.0
    return (500.0 <= m < 520.0) or (590.0 <= m < 610.0)


ALL += [rule_us_news_windows]
