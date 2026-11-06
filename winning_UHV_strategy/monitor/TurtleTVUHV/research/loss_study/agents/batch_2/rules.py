"""rules.py - batch 2 loss-study rules. Each rule(t, A) returns True to SKIP the trade. Every rule reads only the setup fields of t and
bars <= t['k'] (the last closed candle before the entry). Scored with api.report (see run_rules.py)."""
import numpy as np

PIP = 1e-4


def _tod(t):
    return t["t_in"] % 86400                      # seconds after 00:00 UTC (server time = UTC)


def _dow(t):
    return int(((t["t_in"] // 86400) + 4) % 7)    # 0 Sun, 1 Mon ... 5 Fri, 6 Sat (1970-01-01 was a Thursday)


# ---------------------------------------------------------------- 1. the New York 17:00 rollover (spreads widen, liquidity vanishes)
def rule_rollover(t, A):
    """20:30-22:00 UTC: the half hour before and the hour after the 17:00 New York rollover."""
    return 73800 <= _tod(t) < 79200


def rule_rollover_2030_2130(t, A):
    return 73800 <= _tod(t) < 77400


def rule_rollover_2030_2230(t, A):
    return 73800 <= _tod(t) < 81000


def rule_rollover_2000_2200(t, A):
    return 72000 <= _tod(t) < 79200


# ---------------------------------------------------------------- 2. Friday afternoon into the weekly close
def rule_friday_late_17(t, A):
    return _dow(t) == 5 and _tod(t) >= 17 * 3600


def rule_friday_late_19(t, A):
    return _dow(t) == 5 and _tod(t) >= 19 * 3600


def rule_friday_late_20(t, A):
    return _dow(t) == 5 and _tod(t) >= 20 * 3600


# ---------------------------------------------------------------- 3. the spread paid at the fill (buy: ask fill - bid level)
def rule_buy_spread_15(t, A):
    return t["side"] > 0 and (t["fill"] - t["level"]) / PIP >= 1.5


def rule_buy_spread_20(t, A):
    return t["side"] > 0 and (t["fill"] - t["level"]) / PIP >= 2.0


def rule_buy_spread_12(t, A):
    return t["side"] > 0 and (t["fill"] - t["level"]) / PIP >= 1.2


# ---------------------------------------------------------------- 4. dead market (no participation)
def rule_dead_v20_40(t, A):
    k = t["k"]
    return A.v[k - 19:k + 1].mean() < 40


def rule_dead_uhv_40(t, A):
    return t["uhv_v"] < 40


# ---------------------------------------------------------------- 5. trend too old (many same-coloured humps in a row)
def _same_humps(t, A):
    H = A.humps_known(t["k"])
    n = 0
    for row in H[::-1]:
        if int(row[6]) == t["side"]:
            n += 1
        else:
            break
    return n


def rule_old_trend_7(t, A):
    return _same_humps(t, A) >= 7


def rule_old_trend_8(t, A):
    return _same_humps(t, A) >= 8


# ---------------------------------------------------------------- 6. the latest hump made a lower high (green) / higher high (red)
def rule_hump_no_hh(t, A):
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    return (H[-1][3] - H[-2][3]) / PIP * t["side"] < -2.7


# ---------------------------------------------------------------- 7. volume dry-up: the calm before the storm
def rule_dryup(t, A):
    """the last 3 closed candles carry < 40% of the 60-candle average tick volume: participation has vanished right before the break."""
    k = t["k"]
    return A.v[k - 2:k + 1].mean() < 0.4 * A.v[k - 59:k + 1].mean()


def rule_dryup_35(t, A):
    k = t["k"]
    return A.v[k - 2:k + 1].mean() < 0.35 * A.v[k - 59:k + 1].mean()


def rule_dryup_45(t, A):
    k = t["k"]
    return A.v[k - 2:k + 1].mean() < 0.45 * A.v[k - 59:k + 1].mean()


def rule_dead_v60_30(t, A):
    """the 60-candle average is under 30 ticks a minute: no market."""
    k = t["k"]
    return A.v[k - 59:k + 1].mean() < 30


def rule_dead_v60_35(t, A):
    k = t["k"]
    return A.v[k - 59:k + 1].mean() < 35


def rule_cam_old_8(t, A):
    """the camel streak is 8+ humps old (abs(camStk) >= 8): a trend this mature is due a turn."""
    return abs(t["camStk"]) >= 8


# ---------------------------------------------------------------- combined
def rule_session(t, A):
    """rollover window OR Friday after 19:00 UTC."""
    return rule_rollover(t, A) or rule_friday_late_19(t, A)


def rule_session_spread(t, A):
    return rule_session(t, A) or rule_buy_spread_20(t, A)


def rule_session_spread_vol(t, A):
    return rule_session(t, A) or rule_buy_spread_20(t, A) or rule_dryup(t, A) or rule_dead_v60_30(t, A)


def rule_vol_outside_session(t, A):
    """the volume rules only where the session rule does not already act - what they add."""
    return (not rule_session(t, A)) and (rule_dryup(t, A) or rule_dead_v60_30(t, A))


def rule_dryup_outside_session(t, A):
    return (not rule_session(t, A)) and rule_dryup(t, A)


def rule_dead_outside_session(t, A):
    return (not rule_session(t, A)) and rule_dead_v60_30(t, A)


# ---------------------------------------------------------------- increments over what is already known
def _example(t):
    return 74700 <= _tod(t) <= 76500               # the harness example / engine InpUhvNoClose: 20:45-21:15 UTC


def rule_rollover_not_example(t, A):
    return rule_rollover(t, A) and not _example(t)


def rule_friday19_not_rollover(t, A):
    return rule_friday_late_19(t, A) and not rule_rollover(t, A)


def rule_friday17_not_rollover(t, A):
    return rule_friday_late_17(t, A) and not rule_rollover(t, A)


def rule_spread20_not_session(t, A):
    return rule_buy_spread_20(t, A) and not rule_session(t, A)


def rule_spread15_not_session(t, A):
    return rule_buy_spread_15(t, A) and not rule_session(t, A)


def rule_spread12_not_session(t, A):
    return rule_buy_spread_12(t, A) and not rule_session(t, A)


def rule_camold8_not_rollover(t, A):
    return rule_cam_old_8(t, A) and not rule_rollover(t, A)


def _spike60(t, A):
    k = t["k"]
    rr = A.h[k - 59:k + 1] - A.l[k - 59:k + 1]
    return rr.max() / max(np.median(rr), 0.1 * PIP)


def rule_spike8(t, A):
    """the biggest candle of the last hour is 8x+ the hour's median candle: the market is still digesting a news spike."""
    return _spike60(t, A) >= 8


def rule_spike8_not_rollover(t, A):
    return rule_spike8(t, A) and not rule_rollover(t, A)


# ---------------------------------------------------------------- chart-structure ideas from the 22 charts (scored; most fail)
def rule_zee_camel_hh(t, A):
    """Zee's camel fix: the latest hump must make a higher high (green) / lower low high (red) as well as the higher / lower low."""
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    return (H[-1][3] - H[-2][3]) * t["side"] < 0


def rule_camel_thin_margin(t, A):
    """the latest hump's colour decided by under 0.3 pip (0320-194940-S: a double bottom read as a red lower low)."""
    H = A.humps_known(t["k"])
    if not len(H):
        return False
    return abs(H[-1][5] - H[-1][1]) / PIP < 0.3


def rule_under_prior_high(t, A):
    """buy within 1.5 pips under the 40-candle high / sell within 1.5 pips above the 40-candle low (0319-022714-B, 0406-183009-B)."""
    k = t["k"]
    if t["side"] > 0:
        room = (A.h[k - 39:k + 1].max() - t["level"]) / PIP
    else:
        room = (t["level"] - A.l[k - 39:k + 1].min()) / PIP
    return 0.3 <= room <= 1.5


def rule_rejection_wick(t, A):
    """a candle of the last 10 poked 0-3 pips beyond the level and was rejected with a wick >= 60% of its range (0406-143818-B upthrust)."""
    k, lvl, side = t["k"], t["level"], t["side"]
    for j in range(k - 9, k + 1):
        rng = A.h[j] - A.l[j]
        if rng <= 0:
            continue
        if side > 0:
            beyond, wick = (A.h[j] - lvl) / PIP, (A.h[j] - max(A.o[j], A.c[j])) / rng
        else:
            beyond, wick = (lvl - A.l[j]) / PIP, (min(A.o[j], A.c[j]) - A.l[j]) / rng
        if 0 <= beyond <= 3 and wick >= 0.6:
            return True
    return False


def rule_stale_uhv(t, A):
    """the UHV is 10+ candles old at the breakout (0324-165033-B 15, 0325-011150-B 12)."""
    return t["k"] + 1 - t["ku"] >= 10


def rule_level_retested(t, A):
    """the level was already reached by 2+ candles between the UHV and the entry: a second / third attempt (0324-165033-B, 0325-132000-B)."""
    k, ku, lvl = t["k"], t["ku"], t["level"]
    if t["side"] > 0:
        return int((A.h[ku + 1:k + 1] >= lvl).sum()) >= 2
    return int((A.l[ku + 1:k + 1] <= lvl).sum()) >= 2


def rule_loud_breakout(t, A):
    """the breakout minute is already >= 90% as loud as the UHV: not the quiet breakout of the method (0320-143152-S 94%, 0319-155047-S 87%)."""
    return t["brk_ticks_so_far"] >= 0.9 * t["uhv_v"]


def rule_climax_counter_uhv(t, A):
    """sell in the bottom 30% of the 40-candle range (buy in the top 30%; pos = 1 at the trade-direction extreme) after a strong counter UHV that closed at its far end (0319-155047-S, 0320-143152-S)."""
    k, ku, side = t["k"], t["ku"], t["side"]
    hi, lo = A.h[k - 39:k + 1].max(), A.l[k - 39:k + 1].min()
    if hi <= lo:
        return False
    pos = (t["level"] - lo) / (hi - lo) if side > 0 else (hi - t["level"]) / (hi - lo)
    rng = A.h[ku] - A.l[ku]
    if rng <= 0:
        return False
    body = abs(A.c[ku] - A.o[ku]) / rng
    against = (A.h[ku] - A.c[ku]) / rng if side > 0 else (A.c[ku] - A.l[ku]) / rng
    return pos > 0.7 and body > 0.6 and against > 0.85


def rule_extended_move(t, A):
    """the last 30 candles already moved 8+ pips in the trade direction: late in the leg (0322-233112-B, 0406-183009-B)."""
    k = t["k"]
    return (A.c[k] - A.c[k - 30]) * t["side"] / PIP >= 8


def rule_against_120(t, A):
    """the trade is against the 2-hour drift by 10+ pips (0325-132000-B buy in a downtrend, 0319-184909-S sell in an uptrend)."""
    k = t["k"]
    return (A.c[k] - A.c[k - 120]) * t["side"] / PIP <= -10


def rule_round10_ahead(t, A):
    """a 10-pip round number less than 1 pip ahead of the level (0319-155047-S sold into 1.1500)."""
    lvl, side = t["level"], t["side"]
    x = lvl / (10 * PIP)
    nxt = (np.ceil(x + 1e-9) if side > 0 else np.floor(x - 1e-9)) * 10 * PIP
    return (nxt - lvl) * side / PIP < 1.0
