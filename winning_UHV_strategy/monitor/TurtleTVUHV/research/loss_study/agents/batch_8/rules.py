"""rules.py (batch_8) - loss-fix rule candidates for the 97.7% UHV setting. Each rule is  def rule(t, A) -> True = SKIP the trade.
Every rule reads ONLY the setup fields of t (no outcome) and bars <= t["k"], and is SELF-CONTAINED (helpers inlined, so the source can be
pasted alone as `def rule(t, A)`). verify_rules.py execs each function's own source in a fresh namespace and scores it with api.report.
Market time is New York time: the FX day ends 17:00 New York = 21:00 UTC in US summer time, 22:00 UTC in winter. 2026 US DST:
2026-03-08 07:00 UTC (1772953200) .. 2026-11-01 06:00 UTC (1793512800)."""
import math  # noqa: F401  (used inside the rules)

import numpy as np  # noqa: F401


# ================================================================== 1. THE CLOCK: the end of the trading week and the daily rollover
def fri_after_14ny(t, A):
    """Friday after 14:00 New York (18:00 UTC in summer, 19:00 UTC in winter): the last 3 hours of the week. Liquidity drains, and a round
    still open at the weekly close (16:58 NY) is closed there at a loss."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0          # dow 0 = Monday
    return dow == 4 and hr >= 14.0


def fri_after_13ny(t, A):
    """Friday after 13:00 New York (17:00 UTC in summer)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 13.0


def fri_after_12ny(t, A):
    """Friday after 12:00 New York (16:00 UTC in summer)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 12.0


def fri_after_08ny(t, A):
    """Friday after 08:00 New York (12:00 UTC in summer): the whole Friday US session - the US data hour (08:30 NY: NFP, PCE ...) plus the
    afternoon drain into the weekly close. Catches more losses at a lower lift than fri_after_14ny."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 8.0


def last_15min_of_week(t, A):
    """Friday 16:45-17:00 New York: the last 15 minutes before the weekly close - the round cannot even finish."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 16.75


def rollover_mon_thu(t, A):
    """Sunday-Thursday 16:45-18:00 New York (20:45-22:00 UTC in summer), incl. Sunday's weekly-open hour: the daily rollover - the broker's
    day break, spreads blow out and the book is thin; a 'breakout' there is a quote wobble, not a move."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0


def close_and_rollover(t, A):
    """THE CLOCK RULE: Friday after 14:00 New York OR the daily rollover 16:45-18:00 New York (Sun-Thu)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return (dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0)


def fri14_beyond_noclose_band(t, A):
    """What fri_after_14ny adds BEYOND the engine's existing InpUhvNoClose band (20:45-21:15 UTC every day, api's example)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    band = 74700 <= ts % 86400 <= 76500
    return dow == 4 and hr >= 14.0 and not band


def rollover_beyond_noclose_band(t, A):
    """What rollover_mon_thu adds BEYOND the existing 20:45-21:15 UTC band."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    band = 74700 <= ts % 86400 <= 76500
    return dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0 and not band


def last15_beyond_noclose_band(t, A):
    """What last_15min_of_week adds BEYOND the existing 20:45-21:15 UTC band (only the winter-time weeks can differ)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    band = 74700 <= ts % 86400 <= 76500
    return dow == 4 and hr >= 16.75 and not band


def clock_beyond_noclose_band(t, A):
    """What the whole clock rule (close_and_rollover) adds BEYOND the existing 20:45-21:15 UTC band."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    band = 74700 <= ts % 86400 <= 76500
    return ((dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0)) and not band


def sunday_open(t, A):
    """Sunday evening New York (the first hours after the weekly open, thin book). Batch 8: 10-04 23:03 UTC buy."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    return int(((x // 86400) + 3) % 7) == 6


def pre_us_data(t, A):
    """The 30 minutes before 08:30 New York on weekdays (US data releases). Batch 8: 10-02 12:19 UTC (NFP), 10-30 12:24 UTC."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow <= 4 and 8.0 <= hr < 8.5


def pre_us_data_10(t, A):
    """The 10 minutes before 08:30 New York on weekdays."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow <= 4 and 8.0 + 20 / 60.0 <= hr < 8.5


def nfp_window(t, A):
    """The US payrolls window: the FIRST Friday of the month, 08:00-09:30 New York (the market-correct version of pre_us_data). The day of
    the month comes from integer civil-date maths (no imports)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    z = int(x // 86400) + 719468                                          # days -> civil date (H. Hinnant)
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    return dow == 4 and day <= 7 and 8.0 <= hr < 9.5


# ================================================================== 2. ROUND NUMBERS: a big figure right in front of the entry
def big_figure_ahead(t, A):
    """The UHV level sits less than 1.0 pip short of a big figure (1.1200, 1.1300 ...) in the trade direction: the breakout must push
    through the resting orders at the figure to make even 0.1 pip + spread. Batch 8: 10-26 15:59 buy at 1.11996 (0.4 pip under 1.1200),
    10-09 sell at 1.12003 (0.3 pip above 1.1200)."""
    px, s, g = t["level"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    return 0.0 < d <= 1.0


def big_figure_ahead_15(t, A):
    """big_figure_ahead with 1.5 pips."""
    px, s, g = t["level"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    return 0.0 < d <= 1.5


def big_figure_ahead_fill05(t, A):
    """A big figure less than 0.5 pip in front of the FILL."""
    px, s, g = t["fill"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    return 0.0 < d <= 0.5


def big_figure_beyond_clock(t, A):
    """big_figure_ahead on the trades the clock rule does NOT already skip - its own contribution."""
    px, s, g = t["level"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    clock = (dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0)
    return 0.0 < d <= 1.0 and not clock


def ten_pip_line_ahead(t, A):
    """Any 10-pip line (1.1210, 1.1220 ...) less than 0.3 pip in front of the level."""
    px, s, g = t["level"], t["side"], 0.001
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    return 0.0 < d <= 0.3


def half_figure_ahead(t, A):
    """A half figure (x.xx50, not a big figure) less than 1 pip in front of the level."""
    px, s = t["level"], t["side"]
    d50 = (math.ceil(px / 0.005 - 1e-9) * 0.005 - px) / 1e-4 if s > 0 else (px - math.floor(px / 0.005 + 1e-9) * 0.005) / 1e-4
    d100 = (math.ceil(px / 0.01 - 1e-9) * 0.01 - px) / 1e-4 if s > 0 else (px - math.floor(px / 0.01 + 1e-9) * 0.01) / 1e-4
    return 0.0 < d50 <= 1.0 and not (0.0 < d100 <= 1.0)


# ================================================================== 3. THE FILL: a breakout that arrives as a spike / through a wide spread
def fill_overshoot_15(t, A):
    """The fill came more than 1.5 pips beyond the UHV level (ask-over-level for a buy = spread + the 0.3 s jump; level-over-bid for a
    sell = the jump). Implementable as the order's max deviation."""
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 > 1.5


def fill_overshoot_10(t, A):
    """fill_overshoot with 1.0 pip."""
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 > 1.0


def fill_overshoot_20(t, A):
    """fill_overshoot with 2.0 pips."""
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 > 2.0


def fill_overshoot_beyond_clock(t, A):
    """fill_overshoot_15 on the trades the clock rule does NOT already skip - its own contribution."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    clock = (dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0)
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 > 1.5 and not clock


# ================================================================== 4. STRUCTURE seen on the charts (all proved NOT selective)
def ceiling_just_ahead(t, A):
    """A swing (p=2) high (buy) / low (sell) of the last 60 closed bars sits -0.2..0.6 pip from the level: a double top / bottom right in
    front of the entry (batch 8: 10-01 11:18 buy under 1.13250-52, 10-08 11:46 buy under 1.12047, 10-26 07:48 buy under 1.12266)."""
    k, s, lv, ku = t["k"], t["side"], t["level"], t["ku"]
    h, l = A.h, A.l
    for j in range(max(2, k - 60), k - 1):
        if j == ku:
            continue
        if s > 0 and h[j] >= h[j - 1] and h[j] >= h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
            d = (h[j] - lv) / 1e-4
        elif s < 0 and l[j] <= l[j - 1] and l[j] <= l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
            d = (lv - l[j]) / 1e-4
        else:
            continue
        if -0.2 <= d <= 0.6:
            return True
    return False


def hump_needs_hh(t, A):
    """Zee's camel fix as a skip filter (pivot version): the last two p=1 swing highs and lows must step up (buy: higher high AND higher
    low) / down (sell)."""
    k, s = t["k"], t["side"]
    hs, ls = A.pivots(k, 1, 240)
    if len(hs) < 2 or len(ls) < 2:
        return False
    h1, h2, l1, l2 = hs[-2][1], hs[-1][1], ls[-2][1], ls[-1][1]
    if s > 0:
        return not (h2 > h1 and l2 > l1)
    return not (h2 < h1 and l2 < l1)


def hump_camel_replay(t, A):
    """Zee's camel fix as a skip filter (camel-replay version): replays build.py's camel (pivot 1) over the 600 closed bars up to k, takes
    the latest COMPLETED hump (low0 -> high -> low1) and the hump before it; skip unless the hump is a higher low AND a higher high (buy) /
    lower low AND lower high (sell)."""
    k, s = t["k"], t["side"]
    h, l = A.h, A.l
    T, HB, HV, L0B, L0V, LB, LV = 0, None, None, None, None, None, None
    comp = []
    for i in range(max(2, k - 600), k + 1):
        c = i - 1
        ph = not (h[c] < h[c + 1] or h[c] < h[c - 1])
        pl = not (l[c] > l[c + 1] or l[c] > l[c - 1])
        if ph:
            if T == 1:
                if h[c] >= HV:
                    HB, HV = c, h[c]
            else:
                L0B, L0V, HB, HV, T = LB, LV, c, h[c], 1
        if pl:
            redraw = False
            if T == 1:
                LB, LV, T, redraw = c, l[c], -1, True
            elif T == -1 and l[c] <= LV:
                LB, LV, redraw = c, l[c], True
            elif T == 0:
                LB, LV, T = c, l[c], -1
            if redraw and HB is not None and L0B is not None:
                row = (L0V, HV, LV, HB)
                if comp and comp[-1][3] == HB:
                    comp[-1] = row
                else:
                    comp.append(row)
    if len(comp) < 2:
        return False
    l0, hh, l1, _ = comp[-1]
    ph_prev = comp[-2][1]
    if s > 0:
        return not (l1 > l0 and hh > ph_prev)
    return not (l1 < l0 and hh < ph_prev)


def counter_trend_60(t, A):
    """A fresh x1 camel against the hour: price moved more than 10 pips AGAINST the trade over the last 60 closed bars."""
    k = t["k"]
    return (A.c[k] - A.c[k - 60]) * t["side"] / 1e-4 < -10.0 and abs(t["camStk"]) == 1


def mature_trend(t, A):
    """Six or more humps of the trade's colour in a row (an old trend)."""
    return abs(t["camStk"]) >= 6


def quiet_hour(t, A):
    """The median tick volume of the last 60 closed bars is under 40 (a dead market)."""
    k = t["k"]
    return float(np.median(A.v[k - 59:k + 1])) < 40


def uhv_is_last_candle(t, A):
    """The UHV is the very last closed candle (k == ku): the 'retracement' is one bounce candle (batch 8: 10-02 17:19 sell)."""
    return t["k"] == t["ku"]


def shallow_retracement(t, A):
    """The UHV level is less than 0.8 pip from the retracement extreme (a microscopic pullback, batch 8: 10-12 07:37 buy)."""
    return abs(t["level"] - t["extreme"]) / 1e-4 < 0.8


def fri_after_15ny(t, A):
    """Friday after 15:00 New York (19:00 UTC in summer): the last 2 hours of the week."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 15.0


def fri_after_16ny(t, A):
    """Friday after 16:00 New York (20:00 UTC in summer): the last hour of the week."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    return dow == 4 and hr >= 16.0


def fill_overshoot20_beyond_clock(t, A):
    """fill_overshoot_20 on the trades the clock rule does NOT already skip - its own contribution."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    clock = (dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0)
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 > 2.0 and not clock


# ================================================================== the shortlist
def clock_bigfig_overshoot(t, A):
    """close_and_rollover OR big_figure_ahead OR fill_overshoot_15 (everything selective from batch 8 together)."""
    ts = t["t_in"]
    x = ts + (-4 * 3600 if 1772953200 <= ts < 1793512800 else -5 * 3600)
    dow, hr = int(((x // 86400) + 3) % 7), (x % 86400) / 3600.0
    if (dow == 4 and hr >= 14.0) or (dow in (0, 1, 2, 3, 6) and 16.75 <= hr < 18.0):
        return True
    px, s, g = t["level"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / 1e-4 if s > 0 else (px - math.floor(px / g + 1e-9) * g) / 1e-4
    if 0.0 < d <= 1.0:
        return True
    return (t["fill"] - t["level"]) * s / 1e-4 > 1.5


ALL = [fri_after_16ny, fri_after_15ny, fri_after_14ny, fri_after_13ny, fri_after_12ny, fri_after_08ny, last_15min_of_week, rollover_mon_thu, close_and_rollover,
       fri14_beyond_noclose_band, rollover_beyond_noclose_band, last15_beyond_noclose_band, clock_beyond_noclose_band, sunday_open,
       pre_us_data, pre_us_data_10, nfp_window, big_figure_ahead, big_figure_ahead_15, big_figure_ahead_fill05, big_figure_beyond_clock,
       ten_pip_line_ahead, half_figure_ahead, fill_overshoot_15, fill_overshoot_10, fill_overshoot_20, fill_overshoot_beyond_clock, fill_overshoot20_beyond_clock,
       ceiling_just_ahead, hump_needs_hh, hump_camel_replay, counter_trend_60, mature_trend, quiet_hour, uhv_is_last_candle,
       shallow_retracement, clock_bigfig_overshoot]
