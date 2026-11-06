"""rules.py - batch 5 loss-fix rules.  def rule(t, A) -> True = SKIP the trade.
Every rule is STANDALONE (no imports, no module-level helpers) so its source can be pasted and exec'd alone, and it reads only the
setup fields of t and bars <= t["k"] (the last closed candle before the entry). Scored by run.py, which execs each function's source in a
fresh namespace and passes it to api.report - so the printed numbers belong to exactly this code.
New York time uses the 2026 US DST boundaries, hardcoded (2026-03-08 07:00 UTC .. 2026-11-01 06:00 UTC) - all of the data is 2026."""


# =============================================================== clock rules (the daily 17:00 New York break)
def rule_daily_break(t, A):
    """New York 16:45-18:00, every day: the last 15 minutes before the 17:00 NY break (on Friday = the weekly close, when anything open
    is force-closed at 20:58:58 UTC before the spread lets a 0.1-pip target fill) and the dead hour after it (median 5-9 ticks a minute,
    widest spreads of the day). Market reason: no liquidity, the spread decides the trade, not the setup."""
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    sod = loc % 86400
    return 16 * 3600 + 45 * 60 <= sod < 18 * 3600


def rule_weekly_close(t, A):
    """Friday from 16:45 New York (20:45 UTC in summer) - the subset of rule_daily_break that is the weekly close."""
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    return (int(loc // 86400) + 3) % 7 == 4 and loc % 86400 >= 16 * 3600 + 45 * 60


def rule_post_break_hour(t, A):
    """New York 17:00-18:00 (the first hour after the daily break) - the other subset of rule_daily_break."""
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    return 17 * 3600 <= loc % 86400 < 18 * 3600


def rule_friday_afternoon(t, A):
    """FAILED extension: Friday New York 15:00-16:45 (the thin Friday afternoon before the last 15 minutes)."""
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    sod = loc % 86400
    return (int(loc // 86400) + 3) % 7 == 4 and 15 * 3600 <= sod < 16 * 3600 + 45 * 60


# =============================================================== tape / execution rules
def rule_dead_tape(t, A):
    """the last 30 closed candles averaged <= 25 ticks a minute: nobody is trading - the 'breakout' is noise and the spread is large
    against the moves (losses 0602-024909-S UHV 35 ticks, 0603-051526-B UHV 48, 0522-192405-B UHV 41)."""
    k = int(t["k"])
    return float(A.v[k - 29:k + 1].mean()) <= 25


def rule_dead_tape_outside_break(t, A):
    """rule_dead_tape OUTSIDE the New York 16:45-18:00 window - what the dead-tape rule adds on top of rule_daily_break."""
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    sod = loc % 86400
    if 16 * 3600 + 45 * 60 <= sod < 18 * 3600:
        return False
    k = int(t["k"])
    return float(A.v[k - 29:k + 1].mean()) <= 25


def rule_overshoot(t, A):
    """the order FILLED 1.2+ pips beyond the UHV level. CAUTION - the fill is the first tick 0.3 s AFTER the breakout tick (buy at the ask,
    sell at the bid), so this reads a price the EA only learns once it is in: the EA form is a max-spread / max-gap check on the trigger tick.
    For buys it is mostly the spread (ask vs the bid-based level). (loss 0527-123601-B filled 3.9 pips past the level at a news-spike top)"""
    return (t["fill"] - t["level"]) * t["side"] / 1e-4 >= 1.2


def rule_overshoot_buy(t, A):
    """rule_overshoot on buys only (ask fill: spread + 0.3 s drift)."""
    return t["side"] > 0 and (t["fill"] - t["level"]) / 1e-4 >= 1.2


def rule_overshoot_sell(t, A):
    """rule_overshoot on sells only (bid fill: the gap + 0.3 s drift, no spread)."""
    return t["side"] < 0 and (t["level"] - t["fill"]) / 1e-4 >= 1.2


def rule_trigger_gap(t, A):
    """the BREAKOUT TICK itself (known at the decision) printed 0.8+ pips beyond the level: the price jumped through the level."""
    px = t["brk_hi_so_far"] if t["side"] > 0 else t["brk_lo_so_far"]
    return (px - t["level"]) * t["side"] / 1e-4 >= 0.8


def rule_loud_breakout(t, A):
    """the breakout minute had already printed >= 90% of the UHV's ticks when the level broke - not a quiet breakout
    (loss 0526-111253-B: 46 ticks vs UHV 48)."""
    return t["brk_ticks_so_far"] >= 0.9 * t["uhv_v"]


# =============================================================== chart-structure ideas from the batch-5 charts (one shot each)
def rule_round_figure(t, A):
    """the level sits within 1.5 pips of a 100-pip figure (1.1500, 1.1600 ...) on either side
    (losses 0604-074634-S 1.15998, 0528-060001-S 1.15988, 0617-205108-S 1.15007, 0608-094151-S bounce off 1.1500)."""
    x = t["level"] / 0.01
    return abs(x - round(x)) * 100 <= 1.5


def rule_sr_ahead(t, A):
    """two or more confirmed swing points (highs for a buy, lows for a sell) from the last 60 candles, before the UHV, sit within 1 pip
    of the level: the breakout runs straight into a tested level (losses 0605-061830-S double bottom, 0618-132315-S range floor x4)."""
    k, ku, side, lvl = int(t["k"]), int(t["ku"]), t["side"], t["level"]
    hs, ls = A.pivots(k, 1, 60)
    pts = hs if side > 0 else ls
    return sum(1 for j, x in pts if j < ku and abs(x - lvl) <= 1e-4) >= 2


def rule_extended(t, A):
    """the price already ran 25+ pips from the opposite 60-candle extreme to the level: a late entry in an old move
    (losses 0522-142204-S after a 30-pip fall, 0604-074634-S red x5)."""
    k, side, lvl = int(t["k"]), t["side"], t["level"]
    run = (lvl - A.l[k - 59:k + 1].min()) if side > 0 else (A.h[k - 59:k + 1].max() - lvl)
    return run / 1e-4 >= 25


def rule_chop(t, A):
    """10+ of the last 20 closed candles straddle the level: a range, not a breakout (losses 0521-184100-B, 0526-155742-S)."""
    k, lvl = int(t["k"]), t["level"]
    return int(((A.h[k - 19:k + 1] >= lvl) & (A.l[k - 19:k + 1] <= lvl)).sum()) >= 10


def rule_climax_uhv(t, A):
    """the UHV printed 2.2x+ the average of the last 30 candles: a climax / stopping volume, not a pullback
    (loss 0608-094151-S: 517 ticks off 1.1500)."""
    k = int(t["k"])
    return t["uhv_v"] >= 2.2 * float(A.v[k - 29:k + 1].mean())


def rule_climax_at_extreme(t, A):
    """the UHV is loud (1.8x the 30-candle average) AND its far end is the 60-candle extreme behind the trade (a loud green candle at the
    low before a sell, a loud red one at the top before a buy): stopping volume at the turn (losses 0608-094151-S, 0604-074634-S)."""
    k, ku, side = int(t["k"]), int(t["ku"]), t["side"]
    if t["uhv_v"] < 1.8 * float(A.v[k - 29:k + 1].mean()):
        return False
    if side < 0:
        return A.l[ku] <= A.l[k - 59:k + 1].min() + 0.5e-4
    return A.h[ku] >= A.h[k - 59:k + 1].max() - 0.5e-4


def rule_drying_volume(t, A):
    """the last 10 candles traded at half (or less) the pace of the 50 before: the move is running out of fuel
    (losses 0615-152117-B, 0529-012744-B)."""
    k = int(t["k"])
    return float(A.v[k - 9:k + 1].mean()) <= 0.5 * float(A.v[k - 59:k - 9].mean())


def rule_exhaustion_push(t, A):
    """the level is within 2 pips of the 60-candle extreme in the trade direction AND the last 10 candles are 30% quieter than the 50
    before: a fresh low/high made on fading volume (losses 0522-142204-S, 0605-061830-S, 0610-231702-S)."""
    k, side, lvl = int(t["k"]), t["side"], t["level"]
    room = (A.h[k - 59:k + 1].max() - lvl) if side > 0 else (lvl - A.l[k - 59:k + 1].min())
    return room / 1e-4 <= 2 and float(A.v[k - 9:k + 1].mean()) <= 0.7 * float(A.v[k - 59:k - 9].mean())


def rule_old_red_trend(t, A):
    """five or more red humps in a row (old downtrend) - scan showed camStk <= -5 at x2.2; sells only."""
    return t["camStk"] <= -5


def rule_counter_first_hump(t, A):
    """the first hump of the new colour (|camStk| == 1) while the last 90 candles moved 10+ pips against the trade: a counter-trend flip
    (losses 0528-060001-S, 0529-094113-S, 0605-132528-B, 0615-152117-B)."""
    k, side = int(t["k"]), t["side"]
    return abs(t["camStk"]) == 1 and (A.c[k] - A.c[k - 90]) * side / 1e-4 <= -10


# =============================================================== microstructure ideas (one shot each)
def rule_news_minute(t, A):
    """the breakout came in the first 10 seconds of a :00 minute (scheduled data / hourly fixes; loss 0528-060001-S broke at 06:00:01)."""
    ts = float(t["t_in"])
    return int((ts % 3600) // 60) == 0 and ts % 60 < 10


def rule_early_tick_break(t, A):
    """the level broke within the first 6 ticks of the minute - the new candle opened through the level (losses 0522-142204-S 5 ticks,
    0528-060001-S 6, 0602-024909-S 6, 0610-231702-S 9)."""
    return t["brk_ticks_so_far"] <= 6


def rule_daily_break_beyond_example(t, A):
    """what rule_daily_break adds on top of the api.py example window (20:45-21:15 UTC): New York 16:45-18:00 minus that window."""
    ts = float(t["t_in"])
    u = ts % 86400
    if 74700 <= u <= 76500:
        return False
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    return 16 * 3600 + 45 * 60 <= loc % 86400 < 18 * 3600


def rule_union_daily_break_overshoot(t, A):
    """the recommended pair: New York 16:45-18:00 OR filled 1.2+ pips past the level."""
    if (t["fill"] - t["level"]) * t["side"] / 1e-4 >= 1.2:
        return True
    ts = float(t["t_in"])
    loc = ts + (-14400 if 1772953200 <= ts < 1793512800 else -18000)   # New York: US DST 2026-03-08 07:00 .. 2026-11-01 06:00 UTC
    return 16 * 3600 + 45 * 60 <= loc % 86400 < 18 * 3600


def rule_weak_uhv(t, A):
    """the 'UHV' traded at <= 80% of the median candle of the last 30: not an ultra-high-volume candle at all (14 of the 21 batch-5 losses
    had a UHV below the 30-candle average vs 8 of their 42 twins - checked on all trades below)."""
    k = int(t["k"])
    x = sorted(float(q) for q in A.v[k - 29:k + 1])
    return t["uhv_v"] <= 0.8 * (x[14] + x[15]) / 2
