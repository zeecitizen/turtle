"""final_rules.py - the batch-2 rules as standalone code strings (def rule(t, A), numpy as np + math only), exactly as returned to the
orchestrator. verify_final.py execs each in a fresh namespace and scores it with api.score."""
RULES = []


def add(rid, idea, code):
    RULES.append({"rule_id": rid, "idea": idea, "code": code.strip() + "\n"})


add("B2-R1-rollover", "Skip 20:30-22:00 UTC, the half hour before and the hour after the 17:00 New York rollover: spreads widen and liquidity vanishes, and a 0.1-pip target must first pay the spread. Covers the Friday weekly close and the Sunday open too.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    return 73800 <= tod < 79200
""")

add("B2-R1b-rollover-beyond-known", "What R1 adds beyond the already known 20:45-21:15 UTC window (harness example / engine InpUhvNoClose): 20:30-20:45 and 21:15-22:00 UTC only.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    return 73800 <= tod < 79200 and not (74700 <= tod <= 76500)
""")

add("B2-R1c-rollover-ny-time", "R1 in New York time (DST-aware): 16:30-18:00 NY = 20:30-22:00 UTC in summer, 21:30-23:00 UTC in winter (before 8 Mar / from 1 Nov 2026).", """
def rule(t, A):
    off = 4 * 3600 if 1772953200 <= t["t_in"] < 1793512800 else 5 * 3600
    tod = (t["t_in"] - off) % 86400
    return 59400 <= tod < 64800
""")

add("B2-R2-buy-spread-2p", "Skip a BUY when the ask fill is 2+ pips above the bid level: the spread alone is 20x the 0.1-pip target. Buys only (a sell fills at the bid, so its spread is invisible in the trade fields). The fill lands 0.3 s after the break, so it mixes spread with post-break movement; live, use ask-bid at the breakout tick.", """
def rule(t, A):
    return t["side"] > 0 and (t["fill"] - t["level"]) / 0.0001 >= 2.0
""")

add("B2-R2b-buy-spread-1.2p", "R2 with a 1.2-pip threshold (0406-143818-B paid 1.3 pips on Easter Monday).", """
def rule(t, A):
    return t["side"] > 0 and (t["fill"] - t["level"]) / 0.0001 >= 1.2
""")

add("B2-R2c-buy-spread-1.2p-beyond-session", "R2b outside the rollover window and Friday after 19:00 UTC.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)
    if 73800 <= tod < 79200 or (dow == 5 and tod >= 68400):
        return False
    return t["side"] > 0 and (t["fill"] - t["level"]) / 0.0001 >= 1.2
""")

add("B2-R3b-camel-old-7", "R3 with a 7-hump threshold (is the exhaustion effect knife-edge at 8?).", """
def rule(t, A):
    return abs(t["camStk"]) >= 7
""")

add("B2-R3c-camel-old-8-beyond-rollover", "R3 outside the rollover window.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    return abs(t["camStk"]) >= 8 and not (73800 <= tod < 79200)
""")

add("B2-R3-camel-old-8","Skip when the camel streak is 8+ humps of the same colour (abs(camStk) >= 8): a trend this mature tends to end in a climax, and the last UHV is often the stopping volume (0320-143152-S RED x8, 0326-120509-S RED x9).", """
def rule(t, A):
    return abs(t["camStk"]) >= 8
""")

add("B2-R4-combined", "R1 OR R2 OR R3: the rollover window, a 2-pip+ buy spread, or an 8+ hump camel streak.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    if 73800 <= tod < 79200:
        return True
    if t["side"] > 0 and (t["fill"] - t["level"]) / 0.0001 >= 2.0:
        return True
    return abs(t["camStk"]) >= 8
""")

add("B2-R4b-spread-or-old-beyond-rollover", "What R2 + R3 add outside the rollover window (each alone has too few losers there: R2 3, R3 4).", """
def rule(t, A):
    tod = t["t_in"] % 86400
    if 73800 <= tod < 79200:
        return False
    return (t["side"] > 0 and (t["fill"] - t["level"]) / 0.0001 >= 2.0) or abs(t["camStk"]) >= 8
""")

add("B2-R5-news-spike-8x", "Skip when the biggest 1-minute candle of the last hour is 8x+ the hour median candle: the market is still digesting a spike (0331-222340-S: one 6-pip candle = 12x the median in a dead post-rollover hour; 0324-205001-S is NOT caught, ratio 5.4, because its whole hour stayed volatile). Mostly overlaps the rollover window.", """
def rule(t, A):
    k = t["k"]
    rr = A.h[k - 59:k + 1] - A.l[k - 59:k + 1]
    return float(rr.max()) / max(float(np.median(rr)), 0.00001) >= 8
""")

add("B2-R5b-news-spike-beyond-rollover", "R5 outside the rollover window.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    if 73800 <= tod < 79200:
        return False
    k = t["k"]
    rr = A.h[k - 59:k + 1] - A.l[k - 59:k + 1]
    return float(rr.max()) / max(float(np.median(rr)), 0.00001) >= 8
""")

add("B2-R6-dead-market", "Skip when the 60-candle average tick volume is under 30 a minute: no market (0331-222340-S post-rollover, the four 0403 Good Friday close trades; 0322-214022-S at the Sunday open had 57 and is caught by R1 / R7 instead).", """
def rule(t, A):
    k = t["k"]
    return float(A.v[k - 59:k + 1].mean()) < 30
""")

add("B2-R6b-dead-market-beyond-session", "R6 outside the rollover window and Friday after 19:00 UTC.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)
    if 73800 <= tod < 79200 or (dow == 5 and tod >= 68400):
        return False
    k = t["k"]
    return float(A.v[k - 59:k + 1].mean()) < 30
""")

add("B2-R7-volume-dryup", "Skip when the last 3 closed candles carry under 40% of the 60-candle average volume: the calm before the storm (0324-201018-S: 38, 36, 15 ticks after 100-170, then a 45-pip spike).", """
def rule(t, A):
    k = t["k"]
    return float(A.v[k - 2:k + 1].mean()) < 0.4 * float(A.v[k - 59:k + 1].mean())
""")

add("B2-R7b-volume-dryup-beyond-session", "R7 outside the rollover window and Friday after 19:00 UTC.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)
    if 73800 <= tod < 79200 or (dow == 5 and tod >= 68400):
        return False
    k = t["k"]
    return float(A.v[k - 2:k + 1].mean()) < 0.4 * float(A.v[k - 59:k + 1].mean())
""")

add("B2-R8-friday-after-20", "Skip Friday after 20:00 UTC (the weekly close).", """
def rule(t, A):
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)
    return dow == 5 and tod >= 72000
""")

add("B2-R8b-friday-after-19-beyond-rollover", "Friday 19:00-20:30 UTC only (what a Friday rule adds beyond R1).", """
def rule(t, A):
    tod = t["t_in"] % 86400
    dow = int(((t["t_in"] // 86400) + 4) % 7)
    return dow == 5 and tod >= 68400 and not (73800 <= tod < 79200)
""")

add("B2-R9-rollover-2200-2230", "Extending R1 to 22:30 UTC: the 22:00-22:30 slice alone.", """
def rule(t, A):
    tod = t["t_in"] % 86400
    return 79200 <= tod < 81000
""")

add("B2-X1-zee-camel-hh", "Zee camel fix as a filter: the latest hump must also make a higher high (green) / lower high (red); skip if it did not.", """
def rule(t, A):
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    return (H[-1][3] - H[-2][3]) * t["side"] < 0
""")

add("B2-X2-camel-thin-margin", "The latest hump colour was decided by under 0.3 pip - a double bottom / top read as a trend (0325-132000-B: GREEN from a 0.2-pip higher low; 0406-183009-B: 0.1 pip).", """
def rule(t, A):
    H = A.humps_known(t["k"])
    if not len(H):
        return False
    return abs(H[-1][5] - H[-1][1]) / 0.0001 < 0.3
""")

add("B2-X3-under-prior-high", "Buy 0.3-1.5 pips under the 40-candle high (sell 0.3-1.5 pips above the 40-candle low): buying into fresh resistance (0319-022714-B, 0406-183009-B).", """
def rule(t, A):
    k = t["k"]
    if t["side"] > 0:
        room = (float(A.h[k - 39:k + 1].max()) - t["level"]) / 0.0001
    else:
        room = (t["level"] - float(A.l[k - 39:k + 1].min())) / 0.0001
    return 0.3 <= room <= 1.5
""")

add("B2-X4-rejection-wick", "A candle of the last 10 poked 0-3 pips beyond the level and was rejected with a wick >= 60% of its range (0406-143818-B upthrust at 19:35 PKT).", """
def rule(t, A):
    k, lvl, side = t["k"], t["level"], t["side"]
    for j in range(k - 9, k + 1):
        rng = A.h[j] - A.l[j]
        if rng <= 0:
            continue
        if side > 0:
            beyond, wick = (A.h[j] - lvl) / 0.0001, (A.h[j] - max(A.o[j], A.c[j])) / rng
        else:
            beyond, wick = (lvl - A.l[j]) / 0.0001, (min(A.o[j], A.c[j]) - A.l[j]) / rng
        if 0 <= beyond <= 3 and wick >= 0.6:
            return True
    return False
""")

add("B2-X5-stale-uhv", "The UHV is 10+ candles old at the breakout (0324-165033-B 15, 0325-011150-B 12).", """
def rule(t, A):
    return t["k"] + 1 - t["ku"] >= 10
""")

add("B2-X6-level-retested", "2+ candles between the UHV and the entry already reached the level: a second / third attempt (0325-132000-B, 0406-183009-B; 0324-165033-B had only one such candle).", """
def rule(t, A):
    k, ku, lvl = t["k"], t["ku"], t["level"]
    if t["side"] > 0:
        return int((A.h[ku + 1:k + 1] >= lvl).sum()) >= 2
    return int((A.l[ku + 1:k + 1] <= lvl).sum()) >= 2
""")

add("B2-X7-loud-breakout", "The breakout minute is already >= 90% as loud as the UHV, so it is not the quiet breakout of the method (0320-143152-S 94%; 0319-155047-S was 87%, just under).", """
def rule(t, A):
    return t["brk_ticks_so_far"] >= 0.9 * t["uhv_v"]
""")

add("B2-X7b-loud-breakout-0.91", "X7 with the 0.91 cut that the residual scan picked (threshold chosen from the data).", """
def rule(t, A):
    return t["brk_ticks_so_far"] >= 0.91 * t["uhv_v"]
""")

add("B2-X8-climax-counter-uhv", "Sell in the bottom 30% of the 40-candle range (buy in the top 30%; pos = 1 at the trade-direction extreme) after a strong counter UHV (body > 60%, closed at its far end): selling into support after a bullish climax (0319-155047-S; 0320-143152-S misses, its UHV closed at 80% of its range).", """
def rule(t, A):
    k, ku, side = t["k"], t["ku"], t["side"]
    hi, lo = float(A.h[k - 39:k + 1].max()), float(A.l[k - 39:k + 1].min())
    if hi <= lo:
        return False
    pos = (t["level"] - lo) / (hi - lo) if side > 0 else (hi - t["level"]) / (hi - lo)
    rng = A.h[ku] - A.l[ku]
    if rng <= 0:
        return False
    body = abs(A.c[ku] - A.o[ku]) / rng
    against = (A.h[ku] - A.c[ku]) / rng if side > 0 else (A.c[ku] - A.l[ku]) / rng
    return pos > 0.7 and body > 0.6 and against > 0.85
""")

add("B2-X9-extended-move", "The last 30 candles already moved 8+ pips in the trade direction: late in the leg (0319-022714-B 9.3, 0406-183009-B 9.0).", """
def rule(t, A):
    k = t["k"]
    return (A.c[k] - A.c[k - 30]) * t["side"] / 0.0001 >= 8
""")

add("B2-X10-against-2h-drift", "The trade is 10+ pips against the 2-hour drift (0325-132000-B buy inside a downtrend, 0319-184909-S sell inside an uptrend).", """
def rule(t, A):
    k = t["k"]
    return (A.c[k] - A.c[k - 120]) * t["side"] / 0.0001 <= -10
""")

add("B2-X11-round-number-ahead", "A 10-pip round number less than 1 pip ahead of the level (0319-022714-B 0.2 pip under 1.1490, 0325-132000-B 0.1 pip under 1.1590; 0319-155047-S sold 3.5 pips above 1.1500, outside the 1-pip reach).", """
def rule(t, A):
    lvl, side = t["level"], t["side"]
    x = lvl / 0.001
    nxt = (math.ceil(x + 1e-9) if side > 0 else math.floor(x - 1e-9)) * 0.001
    return (nxt - lvl) * side / 0.0001 < 1.0
""")

add("B2-X12-hump-lower-high", "The latest hump high is 2.7+ pips below the previous hump high (buy) / above it (sell): a weak camel.", """
def rule(t, A):
    H = A.humps_known(t["k"])
    if len(H) < 2:
        return False
    return (H[-1][3] - H[-2][3]) / 0.0001 * t["side"] < -2.7
""")
