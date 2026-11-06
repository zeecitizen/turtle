"""rules_final.py - the merged, deduplicated loss-fix rules for the 97.7% EUR/USD UHV setting (research/loss_study/final, 2026-11-06).

Eight analysts each studied ~21 of the 172 losses on the charts and tried ~300 rule variants. This file keeps ONE function per idea (the
best-argued representative), and score_final.py re-scores every one of them with api.report - nothing below is copied from the analysts'
numbers. A rule is

    rule(t, A) -> True = SKIP the trade

and reads only bars <= t["k"] plus the setup fields of t (the one EXTENDED-FIELD rule also reads the breakout tick's spread, a value known at
the moment the entry is decided - see rule_trigger_spread). score_final.py audits every rule with the arrays cut at bar k (0 diffs allowed)
and counts exceptions (0 allowed: api.score silently keeps a trade when a rule raises).

STATUS (from score_final.py; strict bar = lift >= 2 on BOTH halves, >= 4 losers, >= 2 losers in EACH half, losers on >= 4 distinct days;
an increment beyond rule_combined must pass the same bar on its own):
  ACCEPTED, in rule_combined .... rule_rollover_ny
  MT5 CANDIDATES (selective alone, NOT proven beyond rule_combined) .... rule_trigger_spread, rule_friday_close_ny, rule_empty_book
  REJECTED .... everything else below (each docstring says why)

Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). Only MT5's Strategy Tester (or live fills) may promote any of this. The harness also
ignores one-position blocking: skipping a trade can free a later setup that this trade list never shows."""
import csv
import datetime as dt
import math
import os

import numpy as np

PIP = 1e-4
_HERE = os.path.dirname(os.path.abspath(__file__))
_UTC = dt.timezone.utc
_DST = {}


def _us_dst(year):
    """US daylight time for `year` as (start, end) UTC seconds: 2nd Sunday of March 07:00 UTC .. 1st Sunday of November 06:00 UTC."""
    if year not in _DST:
        m = dt.datetime(year, 3, 1, 7, tzinfo=_UTC)
        n = dt.datetime(year, 11, 1, 6, tzinfo=_UTC)
        _DST[year] = ((m + dt.timedelta(days=(6 - m.weekday()) % 7 + 7)).timestamp(), (n + dt.timedelta(days=(6 - n.weekday()) % 7)).timestamp())
    return _DST[year]


def ny_clock(ts):
    """(weekday 0=Mon .. 4=Fri .. 6=Sun, minute of the day) in New York time, DST-aware. The broker's daily break and the weekly close follow
    New York (17:00 NY), so every clock rule is written in New York time, never in fixed UTC (a fixed UTC band is an hour off in winter)."""
    a, b = _us_dst(dt.datetime.fromtimestamp(ts, _UTC).year)
    x = ts - (4 if a <= ts < b else 5) * 3600
    return int(((x // 86400) + 3) % 7), (x % 86400) / 60.0


# ============================================================================================ ACCEPTED

def rule_rollover_ny(t, A):
    """THE ROLLOVER GUARD: no new entries from 16:45 to 17:45 New York time, every day - a plain clock window from 15 minutes before the
    17:00 NY daily rollover to 45 minutes after it. In this PrimeXBT data the engine took no trades 17:00-17:30 NY and the tape is nearly
    empty from 17:00 to 18:00 NY (median 6-8 ticks/min against ~41 at 16:45). On Fridays the window also holds the last 15 minutes before
    the weekly close (16:58 NY flatten). Check the live broker's rollover time before using it on another feed.
    Market reason: liquidity providers pull quotes, the spread blows out to several times the 0.1-pip target, and a breakout there is a quote
    wobble, not a move.
    Edges at round offsets from the 17:00 NY rollover; each slice passes on its own (16:45-17:00 11L/66W, 17:30-17:45 5L/20W), the wider
    slices do not (16:30-16:45 2L/52W with 0 test losers; 17:45-18:00 0L/22W), and all 20 start x end combinations from 16:00-16:45 x
    17:30-18:30 pass on both halves (a plateau, not a knife edge). The engine's InpUhvNoClose band (20:45-21:15 UTC) equals 16:45-17:15 NY
    only in summer time; since 1 Nov 2026 it sits an hour early (15:45-16:15 NY), so the guard must be written in New York time.
    Merges: B1 rule_rollover_2h / rule_rollover_tight / rule_time_windows, B2 R1 / R1b / R1c, B3 rollover_2045_2200 / _2100_2200 /
    _2115_2200, B4 r_close_2030_2200 / r_close_2045_2130, B5 rule_daily_break / rule_post_break_hour, B6 close_wide_20_23 /
    close_2015_2230 / reopen_2115_23, B7 B7_ROLLOVER_HOUR (same window) + variants, B8 rollover_mon_thu / close_and_rollover, and the
    api.py example 20:45-21:15 UTC (= the engine's InpUhvNoClose band, OFF in this setting).
    Re-score: 16L/86W, lift x6.95, train x5.29 (8L/37W), test x10.04 (8L/49W), losers on 15 days; stop-outs only (why=1) 9L, x4.59/x4.94."""
    return 16 * 60 + 45 <= ny_clock(t["t_in"])[1] < 17 * 60 + 45


ACCEPTED = (rule_rollover_ny,)


def rule_combined(t, A):
    """The greedy union of every rule that passes the strict bar on its own AND adds losers at that bar beyond the rules already in
    (score_final.py re-derives it and asserts it equals ACCEPTED). Only one rule survives: rule_rollover_ny. Every other candidate's
    increment beyond it fails a half, rests on < 4 losers / < 4 days, or holds at a single threshold only (see the candidates below).
    Pre-entry only: no rule here reads the fill. Re-score = rule_rollover_ny: 16L/86W, x6.95, train x5.29, test x10.04."""
    return any(r(t, A) for r in ACCEPTED)


# ============================================================================================ MT5 CANDIDATES (not in rule_combined)

_SPR = None


def _trigger_spread(tid):
    global _SPR
    if _SPR is None:
        with open(os.path.join(_HERE, "trigger_spread_by_id.csv"), encoding="utf-8") as f:
            _SPR = {r["id"]: float(r["spr_trig_pips"]) for r in csv.DictReader(f)}
    return _SPR[tid]


def rule_trigger_spread(t, A):
    """EXTENDED FIELD (not in the harness's t): skip when ask - bid at the breakout tick (the first tick whose bid crosses the UHV level =
    the moment the entry is decided, no future) is >= 1.0 pip. Read from trigger_spread_by_id.csv (build_trigger_spread.py re-derives it
    from the engine's ticks; identical to agents/batch_1/trigger_spread.csv for all 7,626 trades; the file carries no outcome column).
    Mechanics: with a 0.1-pip target the price must first travel the whole spread, so a random-walk loss chance is about
    (spread + 0.1) / (stop + 0.1): a 1-pip spread roughly doubles it. Works for buys AND sells (the fill-based spread rules see buys only).
    Merges: B1 trigger_spread.py (outside the harness), B1/B4 rule_buy_spread_*, B2 R2, B6 spread_buy_* (their clean pre-entry form).
    Re-score: 16L/73W, x7.97, train x5.67 (8L/34W), test x12.17 (8L/39W), plateau 0.7-2.0 pip alone. BUT beyond rule_rollover_ny it adds
    5L/49W only at 0.8-1.0 pip (1.1-1.2: 1 test loser; >= 1.3: 0 test losers), and those 5 are two Good-Friday minutes (16:41 and 16:44 NY,
    spreads 65-76 pips), two Friday weekly-close flattens of -$65/-$60 and one NFP trade sitting exactly on 1.0 pip; stop-outs only the
    increment is 3L on 2 days. => NOT in rule_combined. Recommended as a separate MT5 switch: the engine's InpMaxSpreadPts reads the last
    closed bar's spread, not the breakout tick's, and is off in this setting."""
    return _trigger_spread(t["id"]) >= 1.0 - 1e-9


def rule_friday_close_ny(t, A):
    """Friday from 16:00 New York: the last hour before the 16:58 NY weekly flatten - a trade that does not get its 0.1 pip at once is
    force-closed (exit reason 8) and cannot wait out a dip; London has gone home.
    Merges: B1 rule_friday_last3h/4h/6h, B2 R8, B3 fri_late14..20, B4 r_friday_pm_16, B5 rule_weekly_close, B6 friday_after15..19,
    B7 B7_FRIDAY_LAST_HOUR / B7v_FRIDAY_1615, B8 fri_after_08ny..16ny / last_15min_of_week.
    Re-score: 11L/46W, x8.56, train x9.40 (6L/13W), test x9.41 (5L/33W), 8 days. BUT 8 of its 11 losers are already inside
    rule_rollover_ny (Friday 16:45-17:00); the Friday 16:00-16:45 slice it adds is 3L/32W, all 3 in train (2 of them Good Friday 3 April),
    0 of 23 in test => NOT in rule_combined. 8 of its 11 losers are the engine's weekly-close flattens (why=8, -$12 to -$525); stop-outs
    only it is 3L, all on Good Friday 3 April - so its MT5 value depends on whether the EA flattens at the close like the sim. Candidate only
    if MT5 shows the EA holding Friday trades into the close."""
    d, m = ny_clock(t["t_in"])
    return d == 4 and m >= 16 * 60


def rule_empty_book(t, A):
    """Dead tape: the last 10 closed one-minute candles averaged fewer than 20 ticks. A time-zone-free proxy for the rollover / reopen /
    holiday-close hours (no counter-ticks, wide spread).
    Merges: B6 thin10_abs15..35 / thin30_* / thin_any_abs, B7 B7_THIN_VM30 / B7v_THIN_VMIN10, B2 R6 (60 bars < 30), B3 low_vol60_30/40,
    B4 (inside r_thin_market), B5 rule_dead_tape, B1 rule_thin_hour.
    Re-score: 11L/95W, x4.60, train x5.10 (6L/29W), test x5.04 (5L/66W), but 8 days only. Beyond rule_rollover_ny it adds 4L/76W on 3 days
    (two of them the Good-Friday 16:41/16:44 minutes); beyond the clock AND the spread guard 2L/56W, 0 in train => NOT in rule_combined.
    (Alone it holds on stop-outs too: 10L, x4.84/x6.03 - it is the rollover seen through the volume.) Useful only if the broker's rollover
    time were unknown."""
    k = t["k"]
    return float(np.mean(A.v[k - 9:k + 1])) < 20


# ============================================================================================ REJECTED (kept so every verdict can be re-run)

def rule_friday_afternoon_ny(t, A):
    """Friday from 13:00 New York (London gone, the weekend drain; B1's a-priori 4-hour window). Merges B1 rule_friday_last4h, B3 fri_late17,
    B4 r_friday_pm_16, B6 friday_after17, B8 fri_after_13ny/14ny.
    Re-score alone: 22L/224W, x3.97, train x4.25, test x3.87 - but the slice it adds beyond rule_rollover_ny (Friday 13:00-16:45) is
    14L/210W, train x3.60 (11L) / test x1.61 (3L): selective on the train half only (Mar-Jun, the wide-spread regime) => REJECTED.
    Stop-outs only it is x1.50 / x0.61: its lift is the engine's weekly-close flattens (why=8), which MT5 may not reproduce."""
    d, m = ny_clock(t["t_in"])
    return d == 4 and m >= 13 * 60


def rule_trigger_gap(t, A):
    """The breakout tick itself already printed >= 0.6 pip beyond the UHV level (a gap tick through the level; known at the trigger, unlike
    the fill). Merges B5 rule_trigger_gap (0.8), B6 overshoot_brk_0p3..0p6.
    Re-score alone: 5L/59W, x3.46, train x2.48 (3L), test x5.11 (2L), 4 days. Beyond rule_rollover_ny: 2L/55W, 0 in test => REJECTED."""
    px = t["brk_hi_so_far"] if t["side"] > 0 else t["brk_lo_so_far"]
    return (px - t["level"]) * t["side"] >= 0.6 * PIP - 1e-9


def rule_fill_slip(t, A):
    """FILL-TIME GUARD (reads t['fill'], the first tick 0.3 s AFTER the decision, InpUhvLatency): the fill landed >= 1.5 pips beyond the
    level (spread + spike for buys, a jump through the level for sells). Live it can only be an eject after a bad fill (costs the spread) or a
    max-deviation order (ignored on market-execution accounts) - never a free skip, so the harness numbers are optimistic.
    Merges B1 rule_slip_1p5 / rule_time_or_slip, B3 slip_08..20, B4 r_jump_1p0, B5 rule_overshoot(_buy/_sell), B6 overshoot_fill_0p8..2p0,
    B7 B7_SLIP_1P2 / B7v_SLIP_*, B8 fill_overshoot_10/15/20.
    Re-score alone: 11L/68W, x6.17, train x4.25 (7L), test x9.54 (4L). Beyond rule_rollover_ny: 4L/57W with 1 test loser (x2.29/x3.25);
    at 1.2 pips 6L/91W, train x1.80 => REJECTED (mostly rollover spreads under another name)."""
    return (t["fill"] - t["level"]) * t["side"] >= 1.5 * PIP - 1e-9


def rule_buy_fill_spread(t, A):
    """FILL-TIME GUARD, buys only: the ask fill minus the breakout bid >= 1.5 pips (the spread paid; a sell's spread is invisible in t).
    Merges B1 rule_buy_spread_1p0/1p5/2p0, B2 R2 / R2b, B4 r_spread_buy_0p8/1p0/1p5, B6 spread_buy_0p8/1p0.
    Re-score alone: 7L/36W, x7.22, train x5.32 (5L), test x9.54 (2L). Beyond rule_rollover_ny: 3L/25W => REJECTED (< 4 losers); its clean
    pre-entry form for both sides is rule_trigger_spread."""
    return t["side"] > 0 and t["fill"] - t["brk_hi_so_far"] >= 1.5 * PIP - 1e-9


def rule_big_figure_ahead(t, A):
    """A 100-pip figure (1.1700, 1.1200 ...) lies 0-1.0 pip beyond the UHV level in the trade direction: the 0.1-pip target must pierce the
    figure's resting orders (loss 0408-075606-B bought 1.16999 under 1.1700; 1026-105900-B 1.11999 under 1.1200).
    Merges B3 bigfig_ahead08/10/15/20 + fig50/fig20, B8 big_figure_ahead(_15/_fill05), B4 r_round_figure_ahead, B5 rule_round_figure.
    Re-score alone: 7L/83W, x3.45, train x2.53 (4L), test x4.99 (3L), 7 days; 0.8 pip 5L x2.48/x4.77, 1.5 pip train x1.73. Beyond
    rule_rollover_ny 5L/83W, train x1.94; stop-outs only 1 test loser => REJECTED (7 losers, found after ~50 grid variants in two
    batches; a market-sensible hypothesis, not a result)."""
    px, s, g = t["level"], t["side"], 0.01
    d = (math.ceil(px / g - 1e-9) * g - px) / PIP if s > 0 else (px - math.floor(px / g + 1e-9) * g) / PIP
    return 0.0 < d <= 1.0


def rule_camel_old(t, A):
    """A mature camel: 8 or more humps of the trade's colour in a row - the last UHV is often the climax / stopping volume (0320-143152-S
    RED x8, 0326-120509-S RED x9). Merges B2 R3 / R3b / R3c, B1 rule_exhausted_streak (>= 6), B4 r_camstk_ge4, B6 exhausted_stk4/5,
    B7 B7x_OLD_TREND, B8 mature_trend.
    Re-score alone: 5L/29W, x6.52, train x6.27 (4L), test x4.77 (1L). The test half rests on ONE loser and the effect is not monotone
    (>= 4: x1.27/x1.11; >= 6: x1.93/x1.05; >= 7: test 1 loser; >= 9: 1 loser in all) => REJECTED as unproven (watch-list)."""
    return abs(int(t["camStk"])) >= 8


def rule_loud_breakout(t, A):
    """The breakout minute already has >= 90% of the UHV's ticks at the break - the 'quieter breakout' passes by a hair (0428-085748-B 84 of
    85, 0519-151057-S 149 of 154). Merges B1 rule_brk_ratio_0p9, B2 X7 / X7b, B4 r_brk_nearly_as_loud, B5 rule_loud_breakout,
    B7 B7x_LOUD_BREAKOUT.
    Re-score: 8L/180W, x1.89, train x1.79, test x2.04 => fails at the analysts' a-priori 0.90 cut.
    Better-tuned retry (final review): 0.91-0.95 pass by the letter (0.95: 5L/60W, x3.19/x3.87; beyond rule_combined 5L/59W), 0.88-0.90 and
    >= 0.96 fail. The effect is the loudest ~1.4% of trades (ratio >= 0.93: 104 trades, 6 losers, 2 in test - test p ~0.2), and the
    loss rate by ratio is U-shaped in train (the quietest breakouts lose more too), not a clean dose-response => REJECTED as a scan winner.
    Watch-list: a stricter 'quieter breakout' input (skip if the minute already has >= 95% of the UHV's ticks) for a separate MT5 run."""
    return t["brk_ticks_so_far"] >= 0.9 * max(float(t["uhv_v"]), 1.0)


_HOLIDAYS = {"2026-04-03", "2026-04-06", "2026-05-01", "2026-05-04", "2026-05-25", "2026-07-03", "2026-08-31", "2026-09-07"}


def rule_holiday(t, A):
    """A-priori market calendar (not mined): Good Friday, Easter Monday, 1 May, UK May bank holidays / US Memorial Day, US Independence Day
    (observed 3 July), UK August bank holiday, US Labor Day - a major centre closed, thin book. (New idea, final review.)
    Re-score: 12L/299W, x1.71, train x1.75 (9L/144W), test x1.36 (3L/155W) => REJECTED (its train losers are mostly the Good-Friday close
    cluster, already in the clock window; ordinary holiday hours trade like any other day)."""
    a, b = _us_dst(dt.datetime.fromtimestamp(t["t_in"], _UTC).year)
    x = t["t_in"] - (4 if a <= t["t_in"] < b else 5) * 3600
    return dt.datetime.fromtimestamp(x, _UTC).strftime("%Y-%m-%d") in _HOLIDAYS


def rule_us_data_minutes(t, A):
    """Scheduled US data: from 90 s before to 30 s after 08:30, 09:30 or 10:00 New York on weekdays (0702-122937-S sold 23 s before NFP;
    0706-140003-S 3 s after a 10:00 print; 0715-132937-S 23 s before the NYSE open). Merges B6 news_us_90s / news_us_2m /
    news_1230_1400_only, B1 rule_us_news_windows, B7 B7x_NEWS_MINUTE, B8 pre_us_data / nfp_window, B2/B3 news-minute checks.
    Re-score: 5L/61W, x3.36, train x0.88 (1L/33W), test x8.94 (4L/28W) => REJECTED (one half only): the clock alone cannot tell a release
    day from a quiet day. The real fix is an economic calendar in the EA (MQL5 CalendarValueHistory), which needs its own MT5 test."""
    d, m = ny_clock(t["t_in"])
    if d > 4:
        return False
    s = m * 60.0
    return any(-90 <= s - c * 60 <= 30 for c in (8 * 60 + 30, 9 * 60 + 30, 10 * 60))


def rule_zee_camel_hh(t, A):
    """Zee's camel fix as an entry filter: the latest known hump must also make a higher high (buy) / lower high (sell) than the hump before
    it - a green hump only after BOTH a higher low and a higher high. Merges B2 X1, B4 r_hump_no_hh, B8 hump_needs_hh / hump_camel_replay,
    B5/B6 micro-hump variants. Re-score: 62L/2557W, x1.05 (train 1.10 / test 0.96) => REJECTED as a filter. As a change to the
    camel DETECTOR it would alter which setups exist at all - only the engine + MT5 can judge that, not this harness."""
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    return (H[-1][3] - H[-2][3]) * t["side"] < 0


def rule_structure_hh_hl(t, A):
    """Zee's 'structure' comment as a rule (research/loss_study/union_test.py): buy only after the last two p=1 swing highs AND lows both
    rose (sell mirrors). Merges union_test 'structure', B1 rule_structure_against, B7 B7x_HH_AGAINST, B8 hump_needs_hh (pivot version).
    Re-score: 100L/4450W, x0.97 (train 0.97 / test 1.01) - 4,550 trades removed at the base loss rate => REJECTED (it 'catches' 24 of Zee's
    37 tagged losses only because it removes 60% of all trades)."""
    hs, ls = A.pivots(t["k"], 1, 120)
    if len(hs) < 2 or len(ls) < 2:
        return False
    if t["side"] > 0:
        return not (hs[-1][1] > hs[-2][1] and ls[-1][1] > ls[-2][1])
    return not (ls[-1][1] < ls[-2][1] and hs[-1][1] < hs[-2][1])


def rule_near_sr(t, A):
    """Support / resistance right ahead: a confirmed swing high (buy) / low (sell) from before the UHV, within the last 30 bars, sits 0-1.0
    pip beyond the level - a double top / bottom the target must break. Merges B4 r_prior_swing_within_1pip, B1 rule_sr_at_fill,
    B5 rule_sr_ahead, B6 ceiling_tests2/3 / touch_count60_8, B7 B7x_FLAT_BOX_EDGE / B7x_RANGE_EDGE60, B8 ceiling_just_ahead, B3
    near_fresh_extreme / retest_floor, union_test 'near support/resistance 3 pips'.
    Re-score: 116L/5373W, x0.94 (train 0.88 / test 1.10) => REJECTED: a level right ahead is the normal geometry of this setup (33 of 44
    batch-4 twins too)."""
    hs, ls = A.pivots(t["k"], 1, 30)
    lev = t["level"]
    if t["side"] < 0:
        return any(b < t["ku"] and 0 <= (lev - p) / PIP <= 1.0 for b, p in ls)
    return any(b < t["ku"] and 0 <= (p - lev) / PIP <= 1.0 for b, p in hs)


def rule_counter_trend(t, A):
    """A one-hump camel against the bigger move: the last 90 minutes moved more than 6 ATR against the trade (bounce buys inside a decline,
    sells inside a rally). Merges B4 r_counter_trend_90, B6 counter_trend_60_8p, B8 counter_trend_60, B2 X10, B3 counter_trend60,
    B5 rule_counter_first_hump, B7 B7x_HTF_AGAINST / B7x_COUNTER_HTF_BOUNCE, B1 rule_trend_against_120 / rule_fresh_flip_after_opp,
    zee_march_rules htf5_against.
    Re-score: 25L/1191W, x0.91 (train 0.89 / test 0.95) => REJECTED: counter-trend entries lose no more often than others."""
    k = t["k"]
    return (A.c[k] - A.c[k - 90]) * t["side"] < -6.0 * float(A.atr[k])


def rule_exhausted_run(t, A):
    """Chasing an extended run: the last 30 minutes already ran >= 8 pips in the trade direction (buying the top of a vertical leg, selling
    the bottom of a slide). Merges B7 B7x_EXHAUSTED_RUN / B7x_CLIMAX_CHASE, B2 X9, B1 rule_extended_at_extreme, B3 exhaustion,
    B4 r_volume_burst_2x, B5 rule_extended / rule_exhaustion_push / rule_climax_*, B6 climax_v / impulse_against_*.
    Re-score: 28L/741W, x1.61, train x1.60, test x1.05 => REJECTED (train half only)."""
    k = t["k"]
    return (A.c[k] - A.c[k - 30]) * t["side"] > 8 * PIP


# ============================================================================================ registry used by score_final.py / build_comments.py

CANDIDATES = (rule_trigger_spread, rule_friday_close_ny, rule_empty_book)
REJECTED = (rule_friday_afternoon_ny, rule_trigger_gap, rule_fill_slip, rule_buy_fill_spread, rule_big_figure_ahead, rule_camel_old,
            rule_loud_breakout, rule_holiday, rule_us_data_minutes, rule_zee_camel_hh, rule_structure_hh_hl, rule_near_sr,
            rule_counter_trend, rule_exhausted_run)
FILL_TIME = (rule_fill_slip, rule_buy_fill_spread)          # read t['fill']: execution-side, never in rule_combined
EXTENDED = (rule_trigger_spread,)                           # read a pre-entry field the harness's t does not carry
ALL_RULES = ACCEPTED + (rule_combined,) + CANDIDATES + REJECTED
