"""rules.py - batch 6 loss-fix rule candidates. Every rule is self-contained: def rule_x(t, A) -> True = SKIP the trade.
Only bars <= t["k"] (the last closed candle) and the setup fields are read; np / math are module globals (as in the export).
Time: t["t_in"] is UTC seconds; weekday = (int(t_in)//86400 + 3) % 7 (Mon 0 .. Fri 4)."""
import math  # noqa: F401
import numpy as np  # noqa: F401


# ---------------------------------------------------------------- thin tape (no counter-ticks, wide spread)
def rule_thin30_abs40(t, A):
    """30-bar average tick volume below 40 ticks/min (dead market)."""
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 40


def rule_thin30_abs30(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 30


def rule_thin30_abs50(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 50


def rule_thin_rel50(t, A):
    """30-bar average volume below half of the 240-bar average (the tape is drying up)."""
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 0.5 * float(np.mean(A.v[k - 239:k + 1]))


def rule_thin_rel60(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 0.6 * float(np.mean(A.v[k - 239:k + 1]))


def rule_thin10_abs25(t, A):
    """the last 10 closed bars average fewer than 25 ticks/min."""
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 25


# ---------------------------------------------------------------- the daily close / reopen hours (beyond the known 20:45-21:15 UTC)
def rule_close_wide_20_23(t, A):
    """20:00-23:00 UTC (PrimeXBT daily close 21:00 and the dead reopen hour)."""
    s = int(t["t_in"]) % 86400
    return 72000 <= s < 82800


def rule_close_wide_20_23_minus_known(t, A):
    """20:00-23:00 UTC but NOT inside the known InpUhvNoClose window 20:45-21:15 (the increment over what is shipped)."""
    s = int(t["t_in"]) % 86400
    return 72000 <= s < 82800 and not (74700 <= s <= 76500)


def rule_close_2015_2230_minus_known(t, A):
    s = int(t["t_in"]) % 86400
    return 72900 <= s < 81000 and not (74700 <= s <= 76500)


def rule_close_20_2130_minus_known(t, A):
    s = int(t["t_in"]) % 86400
    return 72000 <= s < 77400 and not (74700 <= s <= 76500)


def rule_reopen_2115_23(t, A):
    """21:15-23:00 UTC, the dead hour(s) after the daily close."""
    s = int(t["t_in"]) % 86400
    return 76500 < s < 82800


def rule_preclose_20_2045(t, A):
    """20:00-20:45 UTC, the thinning half-hour before the known close window."""
    s = int(t["t_in"]) % 86400
    return 72000 <= s < 74700


# ---------------------------------------------------------------- Friday afternoon (weekend close)
def rule_friday_after16(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 16 * 3600


def rule_friday_after15(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 15 * 3600


def rule_friday_after17(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 17 * 3600


def rule_friday_after16_minus_known(t, A):
    tin = int(t["t_in"]); s = tin % 86400
    return (tin // 86400 + 3) % 7 == 4 and s >= 16 * 3600 and not (74700 <= s <= 76500)


def rule_friday_any(t, A):
    return (int(t["t_in"]) // 86400 + 3) % 7 == 4


# ---------------------------------------------------------------- scheduled-news clock (summer: US data 12:30 / 14:00 UTC, NYSE 13:30)
def rule_news_us_2m(t, A):
    """within 120 s before / 60 s after 12:30, 13:30 or 14:00 UTC (weekdays)."""
    s = t["t_in"] % 86400
    for m in (45000, 48600, 50400):
        if -120 <= s - m <= 60:
            return True
    return False


def rule_news_us_90s(t, A):
    s = t["t_in"] % 86400
    for m in (45000, 48600, 50400):
        if -90 <= s - m <= 30:
            return True
    return False


def rule_news_any_halfhour_1m(t, A):
    """within 60 s before / 30 s after ANY :00 or :30 between 06:00 and 19:00 UTC."""
    s = t["t_in"] % 86400
    if not (6 * 3600 - 60 <= s <= 19 * 3600 + 30):
        return False
    r = s % 1800
    return r >= 1740 or r <= 30


def rule_news_any_halfhour_2m(t, A):
    s = t["t_in"] % 86400
    if not (6 * 3600 - 120 <= s <= 19 * 3600 + 60):
        return False
    r = s % 1800
    return r >= 1680 or r <= 60


def rule_news_top_of_hour_2m(t, A):
    """within 120 s before / 60 s after any full hour 07:00-18:00 UTC."""
    s = t["t_in"] % 86400
    if not (7 * 3600 - 120 <= s <= 18 * 3600 + 60):
        return False
    r = s % 3600
    return r >= 3480 or r <= 60


# ---------------------------------------------------------------- entry gap / spread (the fill is 0.3 s after the trigger tick)
def rule_overshoot_fill_1p0(t, A):
    """the fill is 1.0+ pip beyond the level (wide spread or gap); implementable as a max-deviation order."""
    return t["side"] * (t["fill"] - t["level"]) >= 1.0 * A.PIP


def rule_overshoot_fill_0p8(t, A):
    return t["side"] * (t["fill"] - t["level"]) >= 0.8 * A.PIP


def rule_overshoot_fill_1p5(t, A):
    return t["side"] * (t["fill"] - t["level"]) >= 1.5 * A.PIP


def rule_overshoot_fill_sided(t, A):
    """buys pay the spread in the fill (bid candles): buy >= 1.0 pip, sell >= 0.7 pip beyond the level."""
    x = t["side"] * (t["fill"] - t["level"]) / A.PIP
    return x >= (1.0 if t["side"] > 0 else 0.7)


def rule_overshoot_brk_0p5(t, A):
    """the breakout minute so far already printed 0.5+ pip beyond the level at the trigger (gap tick) - known at the trigger."""
    x = (t["brk_hi_so_far"] - t["level"]) if t["side"] > 0 else (t["level"] - t["brk_lo_so_far"])
    return x >= 0.5 * A.PIP


def rule_overshoot_brk_0p3(t, A):
    x = (t["brk_hi_so_far"] - t["level"]) if t["side"] > 0 else (t["level"] - t["brk_lo_so_far"])
    return x >= 0.3 * A.PIP


# ---------------------------------------------------------------- exhausted / extended trend
def rule_exhausted_stk5(t, A):
    return abs(t["camStk"]) >= 5


def rule_exhausted_stk4(t, A):
    return abs(t["camStk"]) >= 4


def rule_exhausted_adx60(t, A):
    return float(A.adx[t["k"]]) >= 60


def rule_exhausted_sell_stk3(t, A):
    return t["side"] < 0 and t["camStk"] <= -3


# ---------------------------------------------------------------- the UHV is not ultra-high volume
def rule_weak_uhv_075(t, A):
    """the 'UHV' is quieter than 0.75x the 30-bar average volume."""
    k = t["k"]
    return t["uhv_v"] < 0.75 * float(np.mean(A.v[k - 29:k + 1]))


def rule_weak_uhv_085(t, A):
    k = t["k"]
    return t["uhv_v"] < 0.85 * float(np.mean(A.v[k - 29:k + 1]))


def rule_weak_uhv_abs30(t, A):
    return t["uhv_v"] < 30


# ---------------------------------------------------------------- level already rejected (multi-tested ceiling / floor)
def rule_ceiling_tests3(t, A):
    """3+ separate swing points (p=1) in the last 60 bars within 0.5 pip of the level on the trade side, and no bar has closed 1+ pip beyond
    it: the level is a ceiling (buy) / floor (sell) the market has already refused several times."""
    k, side, lvl, P = t["k"], t["side"], t["level"], A.PIP
    hs, ls = A.pivots(k, 1, 60)
    pts = hs if side > 0 else ls
    n = sum(1 for _, p in pts if abs(p - lvl) <= 0.5 * P)
    c = A.c[k - 59:k + 1]
    beyond = np.any(c > lvl + P) if side > 0 else np.any(c < lvl - P)
    return n >= 3 and not beyond


def rule_ceiling_tests2(t, A):
    k, side, lvl, P = t["k"], t["side"], t["level"], A.PIP
    hs, ls = A.pivots(k, 1, 60)
    pts = hs if side > 0 else ls
    n = sum(1 for _, p in pts if abs(p - lvl) <= 0.5 * P)
    c = A.c[k - 59:k + 1]
    beyond = np.any(c > lvl + P) if side > 0 else np.any(c < lvl - P)
    return n >= 2 and not beyond


def rule_touch_count60_8(t, A):
    """8+ of the last 60 bars reached within 0.3 pip of the level on the trade side without any closing beyond it."""
    k, side, lvl, P = t["k"], t["side"], t["level"], A.PIP
    if side > 0:
        n = int(np.sum(A.h[k - 59:k + 1] >= lvl - 0.3 * P)); beyond = np.any(A.c[k - 59:k + 1] > lvl + 0.5 * P)
    else:
        n = int(np.sum(A.l[k - 59:k + 1] <= lvl + 0.3 * P)); beyond = np.any(A.c[k - 59:k + 1] < lvl - 0.5 * P)
    return n >= 8 and not beyond


# ---------------------------------------------------------------- the counter-move is an impulse, not a retracement
def rule_impulse_against_6b_3atr(t, A):
    """the last 6 closed bars moved 3+ ATR against the trade (sell after a sharp rally / buy after a sharp drop)."""
    k = t["k"]
    return t["side"] * (A.c[k] - A.c[k - 6]) < -3.0 * float(A.atr[k])


def rule_impulse_against_10b_4atr(t, A):
    k = t["k"]
    return t["side"] * (A.c[k] - A.c[k - 10]) < -4.0 * float(A.atr[k])


def rule_counter_trend_60_8p(t, A):
    """price moved 8+ pips against the trade over the last 60 bars (counter-trend entry)."""
    k = t["k"]
    return t["side"] * (A.c[k] - A.c[k - 60]) < -8 * A.PIP


# ---------------------------------------------------------------- micro camel: the hump that set the side is tiny vs the move before it
def rule_micro_camel(t, A):
    """the last known hump's amplitude is < 1/4 of the opposite move over the 60 bars before it (a micro wiggle flipped the side)."""
    k, side = t["k"], t["side"]
    H = A.humps_known(k)
    if not len(H):
        return False
    b0, v0, bh, vh, b1, v1, tr, kn = H[-1]
    amp = vh - min(v0, v1)
    lo = int(max(b0 - 60, 0)); seg_h = A.h[lo:int(b0) + 1]; seg_l = A.l[lo:int(b0) + 1]
    if side > 0:      # green camel after a drop: the drop from the 60-bar high into the hump start
        opp = float(np.max(seg_h)) - v0
    else:             # red camel after a rally
        opp = vh - float(np.min(seg_l))
    return opp > 4 * amp and opp > 8 * A.PIP


# ---------------------------------------------------------------- sell after a climax low / buy after a climax high (V-reversal)
def rule_climax_v(t, A):
    """within the last 45 bars the opposite extreme (for a sell: the low) was printed on the loudest bar of the window, and price has
    since retraced 60%+ of the 45-bar range back toward the trade's stop side."""
    k, side = t["k"], t["side"]
    h, l, v = A.h[k - 44:k + 1], A.l[k - 44:k + 1], A.v[k - 44:k + 1]
    hi, lo = float(np.max(h)), float(np.min(l))
    if hi - lo < 6 * A.PIP:
        return False
    if side < 0:
        i = int(np.argmin(l)); ext_loud = v[max(i - 1, 0):i + 2].max() >= np.max(v)
        rec = (A.c[k] - lo) / (hi - lo)
    else:
        i = int(np.argmax(h)); ext_loud = v[max(i - 1, 0):i + 2].max() >= np.max(v)
        rec = (hi - A.c[k]) / (hi - lo)
    return bool(ext_loud) and rec >= 0.6 and i < 40


# ---------------------------------------------------------------- tiny retracement (no real pullback)
def rule_shallow_retrace_0p5(t, A):
    return abs(t["level"] - t["extreme"]) < 0.5 * A.PIP


# ================================================================ round 2: refinements
def rule_friday_after17_minus_known(t, A):
    tin = int(t["t_in"]); s = tin % 86400
    return (tin // 86400 + 3) % 7 == 4 and s >= 17 * 3600 and not (74700 <= s <= 76500)


def rule_friday_after18(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 18 * 3600


def rule_friday_after1630(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 16 * 3600 + 1800


def rule_thin10_abs20(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 20


def rule_thin10_abs30(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 30


def rule_thin10_abs35(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 35


def rule_thin5_abs20(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 4:k + 1])) < 20


def rule_thin10_rel_day35(t, A):
    """the last 10 bars average below 35% of the last 24 hours' average volume."""
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 0.35 * float(np.mean(A.v[max(k - 1439, 0):k + 1]))


def rule_thin10_rel_day45(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 0.45 * float(np.mean(A.v[max(k - 1439, 0):k + 1]))


def rule_thin10_abs25_minus_known(t, A):
    k = t["k"]; s = int(t["t_in"]) % 86400
    return float(np.mean(A.v[k - 9:k + 1])) < 25 and not (74700 <= s <= 76500)


def rule_spread_buy_0p8(t, A):
    """BUYS: fill (ask) minus the breakout minute's bid high so far >= 0.8 pip = wide spread at the trigger."""
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 0.8 * A.PIP


def rule_spread_buy_1p0(t, A):
    return t["side"] > 0 and (t["fill"] - t["brk_hi_so_far"]) >= 1.0 * A.PIP


def rule_overshoot_fill_1p2(t, A):
    return t["side"] * (t["fill"] - t["level"]) >= 1.2 * A.PIP


def rule_overshoot_fill_2p0(t, A):
    return t["side"] * (t["fill"] - t["level"]) >= 2.0 * A.PIP


def rule_overshoot_brk_0p4(t, A):
    x = (t["brk_hi_so_far"] - t["level"]) if t["side"] > 0 else (t["level"] - t["brk_lo_so_far"])
    return x >= 0.4 * A.PIP


def rule_overshoot_brk_0p6(t, A):
    x = (t["brk_hi_so_far"] - t["level"]) if t["side"] > 0 else (t["level"] - t["brk_lo_so_far"])
    return x >= 0.6 * A.PIP


def rule_weak_uhv_abs40(t, A):
    return t["uhv_v"] < 40


def rule_weak_uhv_abs25(t, A):
    return t["uhv_v"] < 25


def rule_news_us_90s_plus_eu(t, A):
    """as news_us_90s plus the European 08:00 / 09:00 UTC and ECB 12:15 / 12:45 UTC prints."""
    s = t["t_in"] % 86400
    for m in (28800, 32400, 44100, 45000, 45900, 48600, 50400):
        if -90 <= s - m <= 30:
            return True
    return False


def rule_news_1230_1400_only(t, A):
    s = t["t_in"] % 86400
    for m in (45000, 50400):
        if -120 <= s - m <= 60:
            return True
    return False


def rule_env_union(t, A):
    """the environment rules together: Friday >= 17:00 UTC, OR the last 10 bars < 25 ticks/min, OR 20:15-22:30 UTC."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if (tin // 86400 + 3) % 7 == 4 and s >= 17 * 3600:
        return True
    if float(np.mean(A.v[k - 9:k + 1])) < 25:
        return True
    return 72900 <= s < 81000


# ================================================================ round 3: robustness / increments / unions
def rule_thin10_abs15(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 15


def rule_thin10_abs18(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 18


def rule_thin10_abs22(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 22


def rule_thin10_abs20_minus_known(t, A):
    k = t["k"]; s = int(t["t_in"]) % 86400
    return float(np.mean(A.v[k - 9:k + 1])) < 20 and not (74700 <= s <= 76500)


def rule_thin10_abs20_minus_known_minus_fri(t, A):
    """thin10 < 20 that is neither in the known close window nor on Friday >= 18:00 UTC (increment over both)."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if 74700 <= s <= 76500 or ((tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600):
        return False
    return float(np.mean(A.v[k - 9:k + 1])) < 20


def rule_friday_after18_minus_known(t, A):
    tin = int(t["t_in"]); s = tin % 86400
    return (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600 and not (74700 <= s <= 76500)


def rule_friday_after19(t, A):
    tin = int(t["t_in"])
    return (tin // 86400 + 3) % 7 == 4 and (tin % 86400) >= 19 * 3600


def rule_flat_bars10_3(t, A):
    """3+ of the last 10 closed bars have zero range (h == l): the book is empty."""
    k = t["k"]
    return int(np.sum(A.h[k - 9:k + 1] - A.l[k - 9:k + 1] < 0.05 * A.PIP)) >= 3


def rule_dead_range10_1p0(t, A):
    """the last 10 bars average a high-low range under 1.0 pip... and under 30 ticks/min (quiet AND thin)."""
    k = t["k"]
    return float(np.mean(A.h[k - 9:k + 1] - A.l[k - 9:k + 1])) < 0.6 * A.PIP and float(np.mean(A.v[k - 9:k + 1])) < 30


def rule_overshoot_fill_1p2_minus_thin_fri(t, A):
    """fill 1.2+ pip beyond the level, not already thin10<20 / Friday>=18 / known close (the increment)."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if 74700 <= s <= 76500 or ((tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600) or float(np.mean(A.v[k - 9:k + 1])) < 20:
        return False
    return t["side"] * (t["fill"] - t["level"]) >= 1.2 * A.PIP


def rule_env2_union(t, A):
    """Friday >= 18:00 UTC OR the last 10 closed bars average < 20 ticks/min."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    return float(np.mean(A.v[k - 9:k + 1])) < 20


def rule_env3_union(t, A):
    """Friday >= 18:00 UTC OR thin10 < 20 OR the fill 1.2+ pip beyond the level."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    if float(np.mean(A.v[k - 9:k + 1])) < 20:
        return True
    return t["side"] * (t["fill"] - t["level"]) >= 1.2 * A.PIP


def rule_env3_union_minus_known(t, A):
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if 74700 <= s <= 76500:
        return False
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    if float(np.mean(A.v[k - 9:k + 1])) < 20:
        return True
    return t["side"] * (t["fill"] - t["level"]) >= 1.2 * A.PIP


# ================================================================ round 4: relative thinness (feed-independent) and the reopen
def rule_thin10_rel_day20(t, A):
    """the last 10 bars average below 20% of the last 24 hours' average volume (feed-independent dead tape)."""
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 0.20 * float(np.mean(A.v[max(k - 1439, 0):k + 1]))


def rule_thin10_rel_day25(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 0.25 * float(np.mean(A.v[max(k - 1439, 0):k + 1]))


def rule_thin30_rel_day25(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 0.25 * float(np.mean(A.v[max(k - 1439, 0):k + 1]))


def rule_thin30_abs20(t, A):
    k = t["k"]
    return float(np.mean(A.v[k - 29:k + 1])) < 20


def rule_thin_any_abs(t, A):
    """the last 10 bars < 20 ticks/min OR the last 30 bars < 20 ticks/min."""
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 20 or float(np.mean(A.v[k - 29:k + 1])) < 20


# ================================================================ round 5: two more structure ideas from the charts
def rule_uhv_is_range_break(t, A):
    """the UHV candle itself CLOSED beyond the 30-bar range before it, against the trade (buy: a red UHV closing below the prior 30-bar
    low = a breakdown candle; sell: a green UHV closing above the prior 30-bar high). The loudest counter candle broke the range: that is
    counter-pressure, not a retracement (0701-115428-B)."""
    ku = t["ku"]
    if ku - 30 < 0 or ku > t["k"]:
        return False
    if t["side"] > 0:
        return A.c[ku] < float(np.min(A.l[ku - 30:ku]))
    return A.c[ku] > float(np.max(A.h[ku - 30:ku]))


def rule_counter_burst5(t, A):
    """4+ of the last 5 closed bars are counter-coloured, they moved 4+ pips against the trade and their volume rose (the 'retracement'
    is a momentum burst, 0728-145636-S)."""
    k, side = t["k"], t["side"]
    o, c, v = A.o[k - 4:k + 1], A.c[k - 4:k + 1], A.v[k - 4:k + 1]
    cnt = int(np.sum((c - o) * side < 0))
    move = side * (A.c[k] - A.o[k - 4])
    return cnt >= 4 and move <= -4 * A.PIP and float(np.mean(v[-2:])) > float(np.mean(v[:2]))


def rule_fresh_flip_micro(t, A):
    """the camel flipped to the trade side on a single hump (|camStk| == 1) whose amplitude is under 2 pips."""
    k = t["k"]
    if abs(t["camStk"]) != 1:
        return False
    H = A.humps_known(k)
    if not len(H):
        return False
    b0, v0, bh, vh, b1, v1, tr, kn = H[-1]
    return (vh - min(v0, v1)) < 2 * A.PIP


# ================================================================ final unions (the recommended package)
def rule_env_best(t, A):
    """Friday >= 18:00 UTC (last 3 h before the weekend close) OR an empty book (last 10 bars or last 30 bars average < 20 ticks/min)."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    return float(np.mean(A.v[k - 9:k + 1])) < 20 or float(np.mean(A.v[k - 29:k + 1])) < 20


def rule_env_best_plus_gap(t, A):
    """rule_env_best OR the fill lands 1.5+ pip beyond the level (a max-deviation of 1.5 pip on the order)."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    if float(np.mean(A.v[k - 9:k + 1])) < 20 or float(np.mean(A.v[k - 29:k + 1])) < 20:
        return True
    return t["side"] * (t["fill"] - t["level"]) >= 1.5 * A.PIP


def rule_env_best_minus_known(t, A):
    """rule_env_best outside the shipped InpUhvNoClose window 20:45-21:15 UTC (its increment)."""
    k = t["k"]; tin = int(t["t_in"]); s = tin % 86400
    if 74700 <= s <= 76500:
        return False
    if (tin // 86400 + 3) % 7 == 4 and s >= 18 * 3600:
        return True
    return float(np.mean(A.v[k - 9:k + 1])) < 20 or float(np.mean(A.v[k - 29:k + 1])) < 20
