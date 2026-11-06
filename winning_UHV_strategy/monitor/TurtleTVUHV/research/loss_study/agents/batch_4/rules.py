"""rules.py - batch 4 loss-fix rules (def rule(t, A) -> True = SKIP). Every rule reads only the setup fields of t and bars <= t["k"].
Score: cd research/loss_study && py agents/batch_4/score.py"""
import numpy as np

PIP = 1e-4


def _utc_sec(t):
    return t["t_in"] % 86400


# ---------------------------------------------------------------- time of day
def r_close_2030_2200(t, A):
    """the NY close + daily rollover: 20:30-22:00 UTC (spreads blow out, liquidity vanishes)."""
    s = _utc_sec(t)
    return 73800 <= s < 79200


def r_close_2045_2130(t, A):
    s = _utc_sec(t)
    return 74700 <= s < 77400


# ---------------------------------------------------------------- spread / jump at the entry
def r_spread_buy_1p0(t, A):
    """buy: the ask we got (0.3 s after the break) minus the bid that broke the level >= 1.0 pip = a spread blow-out;
    the bid must climb a whole spread + 0.1 pip before the target - in a thin market it often never does."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) / PIP >= 1.0


def r_spread_buy_0p8(t, A):
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) / PIP >= 0.8


def r_jump_1p0(t, A):
    """the fill is >= 1 pip beyond the level (buy: includes the spread; sell: the bid gapped through)."""
    return (t["fill"] - t["level"]) * t["side"] / PIP >= 1.0


def r_spread_buy_1p5(t, A):
    """threshold read off the TRAIN spread table (>=1.5 pip: 5/28 lost on train)."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) / PIP >= 1.5


def r_spread_buy_1p0_outside_close(t, A):
    """the spread blow-out rule on trades OUTSIDE 20:30-22:00 UTC - is it new information or the rollover again?"""
    return r_spread_buy_1p0(t, A) and not r_close_2030_2200(t, A)


def r_spread_buy_1p5_outside_close(t, A):
    return r_spread_buy_1p5(t, A) and not r_close_2030_2200(t, A)


def r_thin_market(t, A):
    """union: the rollover window OR a buy filled at a blown-out spread (>= 1.0 pip)."""
    return r_close_2030_2200(t, A) or r_spread_buy_1p0(t, A)


# ---------------------------------------------------------------- structure (camel humps known at k)
def r_hump_no_hh(t, A):
    """buy: the latest known hump's high is BELOW the previous hump's high (a higher low but a lower high = no uptrend);
    sell: the latest known hump's high is ABOVE the previous hump's high (a lower low but a higher high). Seen on
    0429-032518, 0501-161803, 0513-071801, 0514-125507, 0429-162638 (buys inside lower-high sequences)."""
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    last, prev = H[-1], H[-2]
    if t["side"] > 0:
        return last[3] < prev[3]
    return last[3] > prev[3]


# ---------------------------------------------------------------- double bottom / double top right beyond the level
def r_prior_swing_within_1pip(t, A):
    """a confirmed swing low (sell) / high (buy) from BEFORE the UHV candle, in the last 30 bars, sits 0-1.0 pip beyond the
    level: the target (spread + 0.1 pip beyond the fill) needs that old low / high to break (0505-051831, 0508-170307,
    0518-010308, 0519-151057 sells; 0429-032518, 0512-195506 buys)."""
    hs, ls = A.pivots(t["k"], 1, 30)
    lev = t["level"]
    if t["side"] < 0:
        return any(b < t["ku"] and 0 <= (lev - p) / PIP <= 1.0 for b, p in ls)
    return any(b < t["ku"] and 0 <= (p - lev) / PIP <= 1.0 for b, p in hs)


# ---------------------------------------------------------------- volume climax before the entry
def r_volume_burst_2x(t, A):
    """the last 10 closed bars' median tick volume >= 2x the median of the 110 bars before them: a burst / climax
    (0504-035759: a 15-pip vertical spike on 4-6x volume, bought at the top)."""
    k, v = t["k"], A.v
    return np.median(v[k - 9:k + 1]) >= 2.0 * max(np.median(v[k - 120:k - 9]), 1)


# ---------------------------------------------------------------- weekend / Friday afternoon
def _dow(t):
    return int(((t["t_in"] // 86400) + 4) % 7)          # 0 Sun .. 5 Fri (1970-01-01 was a Thursday)


def r_friday_pm_16(t, A):
    """Friday from 16:00 UTC (London gone, weekend positioning; a trade that cannot reach its target can be carried into the
    weekend close). Every Friday 20:55-21:00 UTC buy in the data lost."""
    return _dow(t) == 5 and _utc_sec(t) >= 57600


def r_friday_pm_16_outside_close(t, A):
    return r_friday_pm_16(t, A) and not r_close_2030_2200(t, A)


# ---------------------------------------------------------------- trend age / counter-trend / second attempt
def r_camstk_ge4(t, A):
    """an old trend: 4+ humps of the same colour in a row (0428-132716 and 0518-010308 were RED x4 sells at the bottom)."""
    return abs(t["camStk"]) >= 4


def r_counter_trend_90(t, A):
    """the micro camel says one side but the last 90 minutes fell (buy) / rose (sell) by more than 6 ATR
    (0501-161803, 0513-071801: buys on a one-hump green camel inside a 25-30 pip decline)."""
    k = t["k"]
    return (A.c[k] - A.c[k - 90]) * t["side"] < -6.0 * A.atr[k]


def r_second_attempt(t, A):
    """the price already CLOSED beyond the level (buy: above, sell: below) in the 10 bars before the UHV candle and came back:
    this breakout is a re-try of a level that just failed (0512-195506, 0514-070500, 0519-151057: a winner broke the same level
    minutes earlier, then the price fell back and the loss re-broke it)."""
    ku, lev = t["ku"], t["level"]
    c = A.c[ku - 10:ku]
    return bool(np.any(c > lev)) if t["side"] > 0 else bool(np.any(c < lev))


def r_thin_market_plus_friday(t, A):
    """union of the thin-market rules: the 20:30-22:00 UTC rollover window, Friday from 16:00 UTC, or a buy filled at a
    blown-out spread (>= 1.0 pip)."""
    return r_close_2030_2200(t, A) or r_friday_pm_16(t, A) or r_spread_buy_1p0(t, A)


# ---------------------------------------------------------------- a loud breakout (pro rata)
def r_brk_nearly_as_loud(t, A):
    """the breakout minute already has >= 90% of the UHV's ticks at the break (0428-085748: 84 of 85; 0519-151057: 149 of 154).
    The engine's 'quieter breakout' test passes by a tick; Zee's method wants a clearly quieter breakout."""
    return t["brk_ticks_so_far"] >= 0.9 * t["uhv_v"]


def r_brk_projected_louder(t, A):
    """the breakout minute's tick RATE so far, projected to 60 s, is >= 1.2x the UHV's volume (a busy breakout, not a quiet one)."""
    secs = max(t["t_in"] % 60 - 0.3, 0.5)          # seconds into the entry minute (bars are minute-aligned)
    return t["brk_ticks_so_far"] * 60.0 / secs >= 1.2 * t["uhv_v"]


# ---------------------------------------------------------------- order-flow proxy and round figures
def r_counter_volume_dominates(t, A):
    """in the last 10 closed bars, volume on candles closing AGAINST the trade is >= 1.5x the volume on candles closing WITH it
    (0514-070500: 11:55-12:01 PKT red/flat bars on the loudest volume of the window right before a buy)."""
    k, s = t["k"], t["side"]
    o, c, v = A.o[k - 9:k + 1], A.c[k - 9:k + 1], A.v[k - 9:k + 1]
    with_ = v[(c - o) * s > 0].sum()
    against = v[(c - o) * s < 0].sum()
    return against >= 1.5 * max(with_, 1)


def r_round_figure_ahead(t, A):
    """a 50-pip round figure (x.xx00 / x.xx50) lies within 1.5 pip beyond the level, so the target has to cross it
    (0504-193208 and 0514-125507: buys at 1.1699x, rejected at 1.1700)."""
    lev, s = t["level"], t["side"]
    q = 0.0050
    if s > 0:
        rn = np.ceil(lev / q - 1e-9) * q
        return 0 <= (rn - lev) / PIP <= 1.5
    rn = np.floor(lev / q + 1e-9) * q
    return 0 <= (lev - rn) / PIP <= 1.5
