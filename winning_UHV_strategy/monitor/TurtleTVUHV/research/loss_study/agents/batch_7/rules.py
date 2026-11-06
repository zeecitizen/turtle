"""rules.py - batch 7 loss-fix rules for the 97.7% EUR/USD UHV setting.  def rule(t, A) -> True = SKIP the trade.
Every rule reads only the setup fields of t (side, t_in, fill, level, extreme, uhv_v, brk_ticks_so_far, ...) and bars <= t["k"].
Time rules are written in New York time (DST aware) because the broker's daily rollover and the weekend close are New York 17:00
(the data's weekend gap starts at 20:58 UTC in summer and 21:58 UTC before DST)."""
import datetime as _dt

import numpy as np

PIP = 1e-4


def _ny(ts):
    """(minute of the New York day, weekday 0=Mon..6=Sun) for a UTC timestamp. US DST: 2nd Sunday of March .. 1st Sunday of November."""
    y = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).year
    m = _dt.datetime(y, 3, 1, tzinfo=_dt.timezone.utc); s = m + _dt.timedelta(days=(6 - m.weekday()) % 7 + 7)
    n = _dt.datetime(y, 11, 1, tzinfo=_dt.timezone.utc); e = n + _dt.timedelta(days=(6 - n.weekday()) % 7)
    off = -4 if s.timestamp() + 7 * 3600 <= ts < e.timestamp() + 6 * 3600 else -5
    d = _dt.datetime.fromtimestamp(ts + off * 3600, _dt.timezone.utc)
    return d.hour * 60 + d.minute + d.second / 60.0, d.weekday()


# ---------------------------------------------------------------- time: the weekend close and the daily rollover
def rule_friday_close(t, A):
    """Friday after New York 16:15 - the last 45 minutes before the weekend close: spreads widen, liquidity leaves, and a trade
    that cannot get its 0.1 pip is flattened at the close (or sits over a thin market)."""
    m, wd = _ny(t["t_in"])
    return wd == 4 and m >= 16 * 60 + 15


def rule_friday_close_30(t, A):
    m, wd = _ny(t["t_in"])
    return wd == 4 and m >= 16 * 60 + 30


def rule_friday_close_60(t, A):
    m, wd = _ny(t["t_in"])
    return wd == 4 and m >= 16 * 60


def rule_rollover(t, A):
    """Any day, New York 16:40-17:30: the daily rollover - the spread blows out and 1-minute candles are a handful of ticks."""
    m, wd = _ny(t["t_in"])
    return 16 * 60 + 40 <= m < 17 * 60 + 30


def rule_rollover_wide(t, A):
    m, wd = _ny(t["t_in"])
    return 16 * 60 + 40 <= m < 18 * 60 + 30


# ---------------------------------------------------------------- liquidity
def rule_thin_vm30(t, A):
    """The last 30 closed candles averaged fewer than 20 ticks a minute: a dead market where the spread is wide relative to the
    0.1 pip target."""
    k = t["k"]
    return A.v[k - 29:k + 1].mean() < 20


def rule_thin_vmin10(t, A):
    """A candle of 6 ticks or fewer among the last 10: the book is empty."""
    k = t["k"]
    return A.v[k - 9:k + 1].min() <= 6


# ---------------------------------------------------------------- the breakout tick itself
def rule_slip(t, A):
    """The breakout tick is already 1.2+ pips beyond the UHV level: a spike / gap tick - we would buy the top of a 1-second
    stop-run (or sell its bottom), with no-one left to carry it 0.1 pip further."""
    return t["side"] * (t["fill"] - t["level"]) >= 1.2 * PIP


def rule_slip_10(t, A):
    return t["side"] * (t["fill"] - t["level"]) >= 1.0 * PIP


# ================================================================ structural ideas from the charts (most expected to fail; kept so nobody retries)
def _ema_last(x, n, k, warm=None):
    """EMA(n) of x[..k] computed causally from k - warm .. k."""
    warm = warm or 4 * n
    a = 2.0 / (n + 1)
    e = float(x[max(0, k - warm)])
    for i in range(max(0, k - warm) + 1, k + 1):
        e = a * float(x[i]) + (1 - a) * e
    return e


def rule_htf_against(t, A):
    """Trade against the 4-hour trend: close more than 6 pips on the wrong side of EMA(240) (losses 0812, 0821, 0923 looked like this)."""
    k = t["k"]
    return t["side"] * (A.c[k] - _ema_last(A.c, 240, k)) < -6 * PIP


def rule_exhausted_run(t, A):
    """Chasing: the last 30 minutes already ran 8+ pips in the trade direction (loss 0827 bought the top of a 20-pip spike)."""
    k = t["k"]
    return t["side"] * (A.c[k] - A.c[k - 30]) > 8 * PIP


def rule_range_edge60(t, A):
    """Buying the top (selling the bottom) of the last-60-minute range: fill in the top 5% of the range in the trade direction."""
    k = t["k"]
    hi, lo = A.h[k - 59:k + 1].max(), A.l[k - 59:k + 1].min()
    r = max(hi - lo, 1e-9)
    pos = (t["fill"] - lo) / r if t["side"] > 0 else (hi - t["fill"]) / r
    return pos > 0.95


def rule_old_trend(t, A):
    """A mature camel: 4+ humps of the trade colour in a row (loss 0923 had 8)."""
    return t["side"] * t["camStk"] >= 4


def rule_old_uhv(t, A):
    """The UHV candle is 10+ minutes old at the breakout (0902: 16, 0925: 11, 0908: 9)."""
    return t["kb"] - t["ku"] >= 10


def rule_retested_level(t, A):
    """Bar proxy for 'third attempt at the same level': within the last 30 minutes (excluding the last 2 candles) price already traded
    at/through the fill 3+ times and came back."""
    k, f = t["k"], t["fill"]
    seg_h, seg_l = A.h[k - 30:k - 1], A.l[k - 30:k - 1]
    n = int((seg_h >= f).sum()) if t["side"] > 0 else int((seg_l <= f).sum())
    return n >= 3


def rule_news_minute(t, A):
    """Entry in the first 2 minutes of the 08:30 or 10:00 New York data releases (0831 sold 13 s into the 10:00 minute)."""
    m, wd = _ny(t["t_in"])
    return wd < 5 and ((8 * 60 + 30 <= m < 8 * 60 + 32) or (10 * 60 <= m < 10 * 60 + 2))


def rule_loud_breakout(t, A):
    """The breakout minute is already nearly as loud as the UHV (ticks so far >= 0.9 x UHV) - against the 'quieter breakout' premise
    (0814: 76 vs 80)."""
    return t["brk_ticks_so_far"] >= 0.9 * t["uhv_v"]


def rule_opposite_candle(t, A):
    """The last closed candle is a strong body against the trade (>= 1 ATR) - momentum just turned (0821 had -1.3 pips)."""
    k = t["k"]
    return t["side"] * (A.c[k] - A.o[k]) <= -1.0 * A.atr[k]


def rule_post_spike(t, A):
    """A news-size candle (range >= 6 x ATR) in the last 60 minutes - the camel is still reading the spike while the market
    recovers (0904 sold the recovery 45 minutes after a 35-pip release candle)."""
    k = t["k"]
    return (A.h[k - 59:k + 1] - A.l[k - 59:k + 1]).max() >= 6 * A.atr[k]


def rule_hh_against(t, A):
    """Structure break: the retracement extreme went beyond the last camel swing in the wrong direction (a sell whose retracement
    made a higher high than the last known hump high; a buy whose retracement made a lower low than the last hump's start low)."""
    k = t["k"]
    H = A.humps[A.humps[:, 7] <= k]
    if not len(H):
        return False
    b0, v0, bh, vh, b1, v1, tr, kn = H[-1]
    return (t["extreme"] > vh) if t["side"] < 0 else (t["extreme"] < v0)


def rule_rollover_hour(t, A):
    """Any day, New York 16:45-17:45: the quarter-hour before the 17:00 rollover and the first 45 minutes after the daily break, when
    1-minute candles are a few ticks and the spread is several times the 0.1 pip target (0820 and 0914 were at NY 17:31 / 17:35)."""
    m, wd = _ny(t["t_in"])
    return 16 * 60 + 45 <= m < 17 * 60 + 45


def rule_reopen(t, A):
    """Mon-Thu/Sun only, New York 17:00-17:45: the first trades after the daily break (no trades happen 17:00-17:30)."""
    m, wd = _ny(t["t_in"])
    return wd != 4 and 17 * 60 <= m < 17 * 60 + 45


def rule_friday_last_hour(t, A):
    """Friday from New York 16:00: the last hour of the week (weekend flatten at 16:58 NY)."""
    m, wd = _ny(t["t_in"])
    return wd == 4 and m >= 16 * 60


def rule_flat_box_edge(t, A):
    """Selling the floor / buying the ceiling of a flat 2-hour box: the last 120 minutes span under 10 pips and the fill sits in the
    outer 15% of that box in the trade direction (0807-0836 sold the bottom of a 6-pip, 10-hour range; 0908 the floor of a base;
    0911 and 0814 bought a triple-top ceiling)."""
    k = t["k"]
    hi, lo = A.h[k - 119:k + 1].max(), A.l[k - 119:k + 1].min()
    r = hi - lo
    if r <= 0 or r >= 10 * PIP:
        return False
    pos = (t["fill"] - lo) / r if t["side"] > 0 else (hi - t["fill"]) / r
    return pos > 0.85


def rule_counter_htf_bounce(t, A):
    """A mature counter-trend bounce: 2+ humps of the trade colour, but price more than 5 pips on the wrong side of EMA(240)
    (0923 bought the 8th green hump of a bounce inside a 10-hour downtrend; 0812, 0821 bought bear-flag bounces)."""
    k = t["k"]
    return t["side"] * t["camStk"] >= 2 and t["side"] * (A.c[k] - _ema_last(A.c, 240, k)) < -5 * PIP


def rule_climax_chase(t, A):
    """Buying a volume climax: a candle in the last 10 with 2x+ the 60-minute average ticks, and 8+ pips already run in the trade
    direction over 30 minutes (0827 bought 0.7 pip under a 20-pip spike that peaked on a 320-tick candle)."""
    k = t["k"]
    vavg = A.v[k - 59:k + 1].mean()
    return A.v[k - 9:k + 1].max() >= 2 * vavg and t["side"] * (A.c[k] - A.c[k - 30]) > 8 * PIP
