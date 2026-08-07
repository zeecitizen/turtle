"""oanda_live_matcher.py — LIVE fast-scalp signal writer (OANDA volume).

Reads the OANDA M1 CSV (kept fresh by oanda_bridge --loop), runs the dom=0 fast-scalp
detector, and when a NEW setup completes on the last CLOSED bar writes
Common/Files/case_signal.json for CaseSignalExecutor.mq5 to execute on the Blueberry
demo. Poll fast (~20s) so seconds-scalp setups aren't missed.

Pipeline:  oanda_bridge --loop 20  ->  oanda_m1.csv  ->  THIS  ->  case_signal.json  ->  EA
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B

CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
SIGNAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_signal.json")
ARMED = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_armed.json")
WATCH = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_watch.json")
CALL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/trend_call.json")
CALL_TTL = 600    # Zee 2026-08-04: a manual call fades after 10 minutes, then AUTO
LOG = Path(__file__).parent / "oanda_signals.jsonl"


import trend_eyes as TE

def _te_bars(bars):
    """trend_eyes speaks (t, high, low, close, volume) tuples; we speak Bar objects."""
    return [(b.t, b.h, b.l, b.c, b.v) for b in bars]

ALLOW = ["BUY", "SELL"]        # refreshed every cycle by update_gate()
_gate_src = ""


def update_gate(bars):
    """The camel cockpit gate (gui/camel_gui.py). Zee's pressed call (UPTREND /
    DOWNTREND / RANGE) rules while fresh (30 min). AUTO — or an expired/absent call —
    is NOT no-gate: the humps decide (Zee 2026-08-04): the slant of the line through
    the peaks. Up-slant -> BUY only, down-slant -> SELL only, flat -> the ghost waits."""
    global ALLOW, _gate_src
    src = None
    try:
        d = json.loads(CALL.read_text(encoding="ascii"))
        if d.get("trend", "AUTO") != "AUTO" and time.time() - d.get("ts", 0) <= CALL_TTL:
            ALLOW, src = d.get("allow", []), f"ZEE:{d['trend']}"
    except Exception:
        pass
    if src is None:
        a = TE.auto_call(_te_bars(bars))
        ALLOW, src = a["allow"], f"AUTO:{a['trend']} ({a['why']})"
    if src != _gate_src:
        print(f"[oanda_matcher] gate -> {src}  allow={ALLOW or 'NONE - ghost waits'}")
        _gate_src = src


def zee_allows(side):
    return side in ALLOW
LOT = 0.10
# RISK CAP history: set to 0.10 after the -$259 night (bursts amplified entry
# losses). LIFTED 2026-08-05 by Zee's explicit instruction: "let the diamonds
# multiply the trades.. this is exactly what we want to test on this demo account —
# whether the diamonds giving conviction result in multiplied profit." The burst-
# night species are all cured since (v1.61 harvest-return, v1.62 lamp-retirement,
# v1.64 send-cooldown, slope guard, ratchet trail); the demo now runs the diamond
# experiment at full tiers 0.10/0.30/0.60. Evaluation: per-tier expectancy from
# turtle_fills (lots self-identify the tier).
# 2026-08-06 THE DIAMOND EXPERIMENT'S VERDICT (n=14): big lots 36% WR, -$219.90;
# 0.10 flat 71% WR, +$76.60 — conviction sizing as currently timed multiplies
# losses (diamonds align late, when trends are old). Cap returns to 0.10.
# Diamonds/hearts REMAIN as labels + raid allowance: at equal size the fills now
# measure pure selection quality — if diamond-labeled trades out-WIN plain ones
# over the coming days, sizing can be re-earned with better timing.
RISK_CAP = 0.10
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=0.0)


def feb11_lots(bars, s):
    """FEB-11 conviction tiers (2026-08-04). On Feb 11 Zee sized by CLICK COUNT —
    2 orders when okay, 3 when good, 6 when certain, 0.10 each. Mechanical proxy,
    using the two signals his own loss reviews validated:
      * momentum breakout body (Aug-1 rule: 'brkt candle not momentum candle')
      * a UHV that truly towers over recent participation
    Tiers STOP at 0.30: the Jul-31 skulls (-$126/-$120/-$128) were 0.4-0.8 lots.
    The EA shrinks its stop-cap as lots grow, so worst case stays ~$30 per tier."""
    b = bars[s["i"]]
    lookback = bars[max(0, s["i"] - 20):s["i"]]
    avg_v = sum(x.v for x in lookback) / max(1, len(lookback))
    tower = s["uhv_vol"] / max(avg_v, 1)
    # Zee's real Feb-11 click counts: 2 / 3 / 6 clicks of 0.10 each. The EA's
    # ghost exit scales with the burst, so the exit money stays ~$10-$30 per tier.
    lots = LOT                                             # 0.10 — single scout click
    if b.body_ratio >= 0.60 and tower >= 1.5:
        lots = 0.30                                        # good: his 3-click burst
    if b.body_ratio >= 0.70 and tower >= 2.5 and s["b_vol"] < s["uhv_vol"]:
        lots = 0.60                                        # certain: his 6-click burst
    return lots


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def selling_climax_tip(bars, s):
    """THE REAL-PERSON TIP, PROMOTED TO A DIAMOND (Zee 2026-08-07): a no-supply /
    no-demand candle in the retracement WITH a heavy counter-trend (selling)
    background before the UHV. Two independent trials on separate tape lengths:
    83% WR / +$31.33 and 75% WR / +$21.76 per trade, against a control of the same
    pattern WITHOUT the background at 43% and 53% (i.e. nothing). The background is
    the entire signal; the bare no-supply candle is worthless. This diamond also
    unlocks the STRUCTURAL TARGET — the one subset whose targets actually get hit."""
    u, i, side = s["u"], s["i"], s["side"]
    if not any(no_supply_bar(bars, k, side) for k in range(u + 1, i)):
        return 0
    look = bars[max(0, u - 20):u]
    if not look:
        return 0
    avgv = sum(b.v for b in look) / len(look)
    prev = bars[max(0, u - 4):u]
    heavy = sum(1 for b in prev
                if (b.is_bear if side == "BUY" else b.is_bull) and b.v >= avgv)
    return int(heavy >= 2)


def structural_target(bars, i, side, entry):
    """First target = the last CONFIRMED structural swing beyond entry (Zee step 11)."""
    sw = TE.find_swings(_te_bars(bars), upto=i)
    if side == "BUY":
        hs = [x.price for x in sw if x.kind == "H" and x.price > entry + 0.3]
        return round(hs[-1], 2) if hs else 0.0
    ls = [x.price for x in sw if x.kind == "L" and x.price < entry - 0.3]
    return round(ls[-1], 2) if ls else 0.0


def diamonds_for(bars, s):
    """The laws of conviction, counted on a LAWFUL completed setup (2026-08-07,
    Zee: 'reconnect the multiplier to the lawful path'). Diamonds never gate — they
    buy CLICKS: 0-1 diamond -> 1 click, 2 -> 2 clicks, 3+ -> 3 clicks, 0.10 each."""
    u, i = s["u"], s["i"]
    side = s["side"]
    d = 0
    d += int(swept(bars, u, i, side))                      # Law 1 — the sweep
    closed = bars[:i]
    if len(closed) >= 6:
        e5 = _ema5([b.c for b in closed[-40:]])
        lc = closed[-1]
        d += int((lc.is_bull and lc.c > e5 + 0.10) if side == "BUY"
                 else (lc.is_bear and lc.c < e5 - 0.10))   # Law 3 — EMA-5 close
    bk = bars[i]
    rng = max(bk.h - bk.l, 1e-9)
    wick = (bk.h - max(bk.o, bk.c)) / rng if side == "BUY" else (min(bk.o, bk.c) - bk.l) / rng
    d += int(wick <= 0.25 and s["b_vol"] < s["uhv_vol"])   # Law 5 — wick & volume
    d += selling_climax_tip(bars, s)                       # THE TIP — promoted 08-07
    return d


def clicks_for(d):
    return 1 if d <= 1 else (2 if d == 2 else 3)


def write_signal(seq, s, lots):
    # id = epoch seconds: MONOTONIC across restarts. A plain counter reset to 1 on
    # every restart while the EA's g_last_id stayed high -> signals silently dropped
    # (and the reverse re-fired old ones). ts feeds the EA's 180s staleness guard.
    now = int(time.time())
    body = ('{"id":%d,"side":"%s","entry":%.2f,"sl":%.2f,"lots":%.2f,"clicks":%d,'
            '"target":%.2f,"ts":%d,"time":"%s"}'
            % (now, s["side"], s["entry"], s["sl"], lots, s.get("clicks", 1),
               s.get("target", 0.0), now, s["open_t"].strftime("%Y-%m-%d %H:%M")))
    SIGNAL.write_text(body, encoding="ascii")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": seq, "id": now, "side": s["side"], "entry": s["entry"],
                             "lots": lots, "time": s["open_t"].strftime("%Y-%m-%d %H:%M"),
                             "emitted_utc": datetime.utcnow().isoformat(timespec="seconds")}) + "\n")


STRETCH_PT = 6.0   # STRETCH HUMILITY (2026-08-05, 3rd receipt: the 19:57 -$30.90
                    # diamond at the tip of a 14pt/40min climb): when the lamp sits
                    # more than this many points beyond the last confirmed swing
                    # (low for BUY, high for SELL), conviction CANNOT be "sure" —
                    # entry stays (trash hides gems) but lots humble to 0.10.


def stretch_of(bars, lvl, side):
    sw = TE.find_swings(_te_bars(bars))
    if side == "BUY":
        lows = [s for s in sw if s.kind == "L"]
        return (lvl - lows[-1].price) if lows else 0.0
    highs = [s for s in sw if s.kind == "H"]
    return (highs[-1].price - lvl) if highs else 0.0


def law6_probation(bars, u, side):
    """LAW 6 IN PROBATION (Zee 2026-08-05): Selling-Climax UHV — heavy counter-trend
    VOLUMES before the UHV (2+ bars >= avg20) + big-spread UHV (>=1.5x avg range).
    Day-1 exam PASSED (+0.54 vs +0.30 avg/trade); needs 3 passing days to become a
    diamond. Until then it grants NO lots/raids — only a heart on the chart:
    'this setup has a chance greater than others.'"""
    look = bars[max(0, u - 20):u]
    if not look: return 0
    avg_v = sum(b.v for b in look) / len(look)
    avg_r = sum(b.h - b.l for b in look) / len(look)
    prev = bars[max(0, u - 4):u]
    col = (lambda b: b.is_bear) if side == "BUY" else (lambda b: b.is_bull)
    heavy = sum(1 for b in prev if col(b) and b.v >= avg_v)
    U = bars[u]
    return int(heavy >= 2 and (U.h - U.l) >= 1.5 * avg_r)


def night_window():
    """NIGHT GATE (2026-08-06): three nights of receipts (-$130, -$43, -$69.30) and
    Zee's revocation of the trash-hides-gems doctrine the same day ("its not holding
    true"). 21:30-01:00 broker (18:30-22:00 UTC): NO new entries at all — chop +
    2-6x slippage made the window negative in every configuration tried."""
    if GATES_LIFTED:
        return False                       # hanging free — trial 2026-08-07
    from datetime import datetime, timezone
    t = datetime.now(timezone.utc)
    mins = t.hour * 60 + t.minute
    return 18 * 60 + 30 <= mins < 22 * 60


def no_supply_bar(bars, k, side):
    """NO SUPPLY / NO DEMAND candle — CALIBRATED to Zee's three labelled examples
    (2026-08-06, 5:18 / 6:16 / 6:53 PM PKT; all three detected by this rule):
    counter-trend colour · spread < 0.8x avg20 range · volume below the IMMEDIATELY
    PRECEDING candle (the supply bar) and below the 20-bar average. (v1 demanded
    'below both previous' and missed his 1:51 PM textbook case by ONE unit of
    volume; his spoken 'less than half' is the feel — his eye picks 0.65-0.9x with
    a notably small spread right after a heavy bar. All FOUR labelled examples —
    1:51 / 5:18 / 6:16 / 6:53 PM PKT — are detected by this rule.)"""
    if k < 22 or k >= len(bars): return False
    NS = bars[k]
    if (NS.is_bear if side == "BUY" else NS.is_bull) is False: return False
    look = bars[k - 20:k]
    avg_v = sum(b.v for b in look) / len(look)
    avg_r = sum(b.h - b.l for b in look) / len(look)
    return ((NS.h - NS.l) < 0.8 * avg_r and NS.v < bars[k - 1].v and NS.v < avg_v)


def scenario3(bars, u, i, side):
    """CLIMACTIC ACTION BAR — SCENARIO 3 (Zee's 11-step spec, 2026-08-06).
    Climactic UHV -> no-supply candle near the trigger lines -> its low swept ->
    a momentum candle of the trade's colour breaks its high on HIGHER volume.
    TRIAL (27h, n=9): 56% WR / +0.297pt per trade vs baseline 49% / +0.110pt —
    promising but small; rides as a PROBATION HEART (no lots, no raids) until it
    passes 3 separate days. Zee's own exits (SL/structural target) scored 14% at
    M1 scale — the pattern travels, that target does not."""
    if u is None: return 0
    look = bars[max(0, u - 20):u]
    if not look: return 0
    if bars[u].v < 1.5 * (sum(b.v for b in look) / len(look)): return 0
    for k in range(u + 1, min(u + 10, i)):
        if not no_supply_bar(bars, k, side): continue
        NS = bars[k]
        for j in range(k + 1, min(k + 5, i + 1)):
            BO = bars[j]
            swept = (BO.l < NS.l) if side == "BUY" else (BO.h > NS.h)
            if not swept: continue
            for m in range(j, min(j + 4, i + 1)):
                BK = bars[m]
                broke = (BK.c > NS.h) if side == "BUY" else (BK.c < NS.l)
                rc = BK.is_bull if side == "BUY" else BK.is_bear
                if broke and rc and BK.body_ratio >= 0.5 and BK.v > NS.v:
                    return 1
            break
    return 0


def no_demand(bars, side):
    """THE NO-DEMAND VETO (2026-08-06, Law 2 reborn with correct polarity — trial:
    NS/ND-as-confirmation scored 44%/+0.126 vs 50%/+0.193 without; but as Zee's
    original VSA warning it kills the 17:19 species): a BUY is refused when the
    approach is a falling-volume same-colour drift (greens shrinking after heavy
    reds = a rally nobody funds). Mirror for SELL."""
    closed = bars[:-1]
    if len(closed) < 8: return False
    a, b2 = closed[-2], closed[-1]
    col = (lambda c: c.is_bull) if side == "BUY" else (lambda c: c.is_bear)
    if not (col(a) and col(b2)): return False
    if not (b2.v < a.v): return False
    prior = closed[-7:-2]
    opp = [c.v for c in prior if (c.is_bear if side == "BUY" else c.is_bull)]
    return bool(opp) and b2.v < sum(opp) / len(opp)


CHOP_ER = 0.25   # CHOP SELECTIVITY (Zee-approved 2026-08-06): Kaufman efficiency
                  # ratio of the last 20 CLOSED bars. The 21:07 BUY fired at ER 0.04
                  # (9.2pt of wandering, zero net) — the canonical chop-meter had sat
                  # DISABLED (ER_MIN=0) since the pure-config day. Below CHOP_ER only
                  # diamond-bearing setups may enter. Conviction may hunt in the
                  # washing machine; boredom may not.


REGIME_OVR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/regime_override.json")


# ── THE GATES-LIFTED TRIAL (Zee 2026-08-07: "lift them, let them hang free") ──
# The night gate and the regime/chop switch were bought with receipts from the
# IMPATIENT machine (1pt floor). Under the v1.74 grace period the same buckets
# now simulate profitable: night 82% WR/+$117, chop 75%/+$333, asia 72%/+$181,
# with trending tape still 3.3x better per trade. So both blocks hang free for a
# full 24h cycle; the live receipts are the judge. Flip back to False to restore.
GATES_LIFTED = True

# ── THE FUNDAMENTAL LAW OF THE BREAKOUT (Zee 2026-08-07, verbatim) ──
# "a breakout candle must CLOSE above the high of the UHV (for buy) and should be
#  a MOMENTUM candle with LOWER VOLUME than the UHV."
# This cannot be satisfied by an intrabar tick-cross — a candle can cross the level
# and still close a doji on the wrong side (the 12:37 PKT SELL: 2%-body green doji,
# 0.83x volume). So the tick-DOOR is retired: entries now come only from a CLOSED
# candle that satisfies all three clauses. Cost: we lose the ms-speed entry (it
# tested +$921 vs +$213 on wick-crosses in the old exit model). Zee's law outranks
# that trial — it is a stated rule, not a tuning knob. DOOR_ENABLED flips it back.
DOOR_ENABLED = False


def regime_forced():
    """Zee's START REGIME button (cockpit): force trading through chop for 30 min
    so he can test in non-regime times. File written by gui/camel_gui.py."""
    try:
        import json as _j
        return time.time() < _j.loads(REGIME_OVR.read_text()).get("until", 0)
    except Exception:
        return False


def choppy(bars):
    closed = bars[:-1]
    if len(closed) < 22: return False
    seg = [b.c for b in closed[-21:]]
    net = abs(seg[-1] - seg[0])
    tot = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
    return (net / max(tot, 1e-9)) < CHOP_ER


DEAD_TAPE_FRAC = 0.50  # DEAD-TAPE SELECTIVITY (Zee 2026-08-05, shipped on his word):
                        # when the last 10 bars' average volume falls below half the
                        # session's average, only diamond-bearing setups may enter —
                        # zero-diamond entries wait for the market to breathe.
                        # "Conviction may hunt in the dark; boredom may not."
                        # (The 20:49 -$15.80 and 20:57 -$11.70 post-peak drift fades.)


def dead_tape(bars):
    # (audit fix B, 2026-08-06): closed candles only — the forming bar's partial
    # volume made this gate flicker with the wall clock (false dead-tape at :05
    # of every minute).
    closed = bars[:-1]
    if len(closed) < 40: return False
    recent = sum(b.v for b in closed[-10:]) / 10
    session = sum(b.v for b in closed) / len(closed)
    return recent < DEAD_TAPE_FRAC * session


EXHAUST_SLOPE = 0.60   # LAW OF EXHAUSTION (Zee 2026-08-05): trends die of old age.
EXHAUST_HUMPS = 4      # Today's census: avg life 2.1 humps; P(next) 70%->29% after
                       # hump 2; avg |slope| at DYING humps 0.87 vs 0.35-0.42 alive —
                       # steepness is the blow-off, not strength. The 19:57 -$30.90
                       # fired at slope +0.791 (death zone). Humility, not a gate.


def exhausted(bars, side):
    if abs(TE.slope_of(_te_bars(bars))) > EXHAUST_SLOPE:
        return True
    sw = TE.find_swings(_te_bars(bars))
    seq = [s for s in sw if s.kind == ("H" if side == "BUY" else "L")]
    streak = 0
    for s in reversed(seq):
        if s.label == ("HH" if side == "BUY" else "LL"): streak += 1
        else: break
    return streak >= EXHAUST_HUMPS


ARMED_IDS: dict = {}     # armed-setup key -> the id first assigned (stable across polls)


def swept(bars, u, i, side):
    """THE LAW OF CONVICTION (Zee 2026-08-04, named by him): two horizontal lines box
    the UHV candle. UPTREND/BUY: price must first BREAK the BOTTOM line (dip under
    the UHV low — the sweep, the liquidity grab) before it breaks the top line (the
    lamp). DOWNTREND/SELL, the mirror: "if in downtrend the higher black line is
    crossed, it adds to conviction, before it breaks the lower black line to go
    downwards." Only then the ghost leaves saying 'Haah — I'm sure this ends with
    the lamp in my hand.' His own canonical rule: sweep, THEN break."""
    U = bars[u]
    if side == "BUY":
        return any(bars[k].l < U.l for k in range(u + 1, min(i + 1, len(bars))))
    return any(bars[k].h > U.h for k in range(u + 1, min(i + 1, len(bars))))


def find_armed(bars):
    """GHOST-AT-THE-DOOR (Zee 2026-08-04): the whole pattern is present EXCEPT the
    breakout — origin, trend, a towering UHV — and price is standing near the trigger
    line. Instead of waiting for the M1 candle to CLOSE beyond it (up to a minute late,
    plus polling), we hand the level to the EA, whose OnTick fires the millisecond the
    live price crosses. The slow eyes find the lamp; the tick-speed hands grab it."""
    n = len(bars); i = n - 1                      # bars[i] is the FORMING candle
    found = []
    for side in ("BUY", "SELL"):                  # both sides; gating happens at ARM time
        o = None
        for j in range(i - 1, max(i - B.LB, 0), -1):
            if B.is_origin(bars, j, side): o = j; break
        if o is None or not B.trend_ok(bars, o, side): continue
        if B.efficiency_ratio(bars, o) < B.ER_MIN: continue
        rs = B.retr_zone_start(bars, o, side)
        best = None
        for k in range(rs, i):
            c = bars[k]
            if not (c.is_bear if side == "BUY" else c.is_bull): continue
            if c.body_ratio < B.UHV_BODY_MIN: continue
            if B.UHV_VOL_MIN > 0:                          # optional absolute floor
                _lk = bars[max(0, k - 20):k]
                if _lk and c.v < B.UHV_VOL_MIN * (sum(x.v for x in _lk) / len(_lk)): continue
            # COLOUR-AWARE UHV (Zee 2026-08-05, Option B) — see build_entry_review_m5
            if best is None or c.v > bars[best].v: best = k
        if best is None: continue
        # STRONG-NEIGHBOUR OVERRIDE (Zee 2026-08-04): "the detected UHV has 2 candles
        # before a very strong UHV that can override this UHV for added confirmation,
        # thus the black lines can mark the high/low of THAT UHV." If a bigger-volume
        # candle sits within the 2 bars before the chosen one, it rules the box —
        # but ONLY if it wears the retracement's colour (Zee: green UHV in a red
        # downtrend, red UHV in a green uptrend). Wrong-colour giants don't count.
        col_ok = (lambda c: c.is_bear) if side == "BUY" else (lambda c: c.is_bull)
        eligible = [k for k in range(max(0, best - 2), best + 1)
                    if k == best or col_ok(bars[k])]
        best = max(eligible, key=lambda k: bars[k].v)
        U = bars[best]
        lvl = U.h if side == "BUY" else U.l
        # a CLOSED candle already broke it -> the completed-signal path owns this one
        if any((bars[k].is_bull and bars[k].c > lvl) if side == "BUY"
               else (bars[k].is_bear and bars[k].c < lvl) for k in range(best + 1, i)):
            continue
        # NOTE: no distance filter here — the box must be VISIBLE from the moment the
        # UHV forms (Zee). The 2pt "near" rule applies only to ARMING (write_armed).
        sw = swept(bars, best, i, side)            # concrete? (box is DRAWN either way)
        # conviction without a breakout candle to read: UHV towering only, capped at
        # 0.30 — the 6-click certainty needs the confirmed break, which the completed-
        # signal path still carries.
        lb = bars[max(0, best - 20):best]
        tower = U.v / max(sum(x.v for x in lb) / max(1, len(lb)), 1)
        lots = 0.30 if tower >= 1.5 else LOT
        # DYING LAMP (Zee 2026-08-04): "if the trend is looking strongly in our
        # direction we can enter a bit late too... catching a lamp with dying light
        # before it dies." When the last 5 closed bars are running hard the trade's
        # way, the EA may fire up to 3pt past the lamp instead of 1pt.
        last5 = bars[-6:-1]
        net = last5[-1].c - last5[0].o
        run = net if side == "BUY" else -net
        same = sum(1 for c in last5 if (c.is_bull if side == "BUY" else c.is_bear))
        chase = 3.0 if (run >= 2.0 and same >= 3) else 1.0
        sweep_line = U.l if side == "BUY" else U.h
        # SECOND LAW OF CONVICTION (Zee 2026-08-04): "near the black lines if a
        # no supply / no demand appears, we treat it as the second law of conviction."
        # NS (for BUY): a red candle on DEAD volume — < 0.75x of EACH of the previous
        # two (last night's tuned threshold that survived the walk-forward) — closing
        # within 0.8pt of either black line. ND for SELL: the green mirror. The crowd
        # has nothing left to throw at the level; conviction doubles the burst.
        law2 = 0
        # (audit fix A, 2026-08-06): closed candles only — the forming bar's
        # half-born volume always looks 'dead' and minted false NS/ND diamonds.
        for k in range(max(best + 1, 2), i):
            c = bars[k]
            if not (c.is_bear if side == "BUY" else c.is_bull): continue
            if c.v >= 0.75 * bars[k - 1].v or c.v >= 0.75 * bars[k - 2].v: continue
            if min(abs(c.c - lvl), abs(c.c - sweep_line)) <= 0.8:
                law2 = 1
                break
        # (law2 demoted 2026-08-06: no burst effects — see no_demand veto)
        # THIRD LAW OF CONVICTION (Zee, sharpened 2026-08-05): the momentum candle is
        # "a strong big candle without a wick on top and closing CLEARLY above EMA 5"
        # (BUY; mirror below for SELL). EMA = exponential smoothing, never SMA.
        closed = bars[:i]
        e5 = _ema5([b.c for b in closed[-40:]])
        lc = closed[-1]
        rng = max(lc.h - lc.l, 1e-9)
        if side == "BUY":
            law3 = int(lc.is_bull and lc.body_ratio >= 0.5
                       and lc.c > e5 + 0.10)                        # clearly above EMA5
        else:
            law3 = int(lc.is_bear and lc.body_ratio >= 0.5
                       and lc.c < e5 - 0.10)                        # clearly below EMA5
        # FOURTH LAW OF CONVICTION (Zee 2026-08-05): RSI-14 regular divergence at the
        # extremes, "we need two swings". Oversold BUY: price makes a LOWER low across
        # the last two swing lows while RSI makes a HIGHER low, with RSI in/near the
        # oversold zone (<30). Overbought SELL: the mirror above 70. Filters the false.
        law4 = 0
        c80 = closed[-80:]
        rr = _rsi14([b.c for b in c80])
        if side == "BUY":
            piv = _swing_idx(c80, "L")[-2:]
            if len(piv) == 2:
                p1, p2 = piv
                law4 = int(c80[p2].l < c80[p1].l and rr[p2] > rr[p1] + 1.0
                           and min(rr[p1], rr[p2]) < 30)
        else:
            piv = _swing_idx(c80, "H")[-2:]
            if len(piv) == 2:
                p1, p2 = piv
                law4 = int(c80[p2].h > c80[p1].h and rr[p2] < rr[p1] - 1.0
                           and max(rr[p1], rr[p2]) > 70)
        # FIFTH LAW OF CONVICTION (Zee 2026-08-05): "there should not be a large wick
        # on top of the breakout candle.. and the breakout candle's volume must be
        # lower than the UHV candle" (mirror wick below for SELL). Fifth diamond.
        if side == "BUY":
            law5 = int((lc.h - max(lc.o, lc.c)) / rng <= 0.25 and lc.v < U.v)
        else:
            law5 = int((min(lc.o, lc.c) - lc.l) / rng <= 0.25 and lc.v < U.v)
        # STRUCTURAL SL (Zee): "few points below the last low (before the breakout
        # candle) — in case the ghost is stuck." Mirror above the last high for SELL.
        sl_px = (min(b.l for b in closed[-3:]) - 0.5) if side == "BUY" \
            else (max(b.h for b in closed[-3:]) + 0.5)
        humble = int(stretch_of(bars, lvl, side) > STRETCH_PT or exhausted(bars, side))
        if humble:
            lots = 0.10                            # stretched top/bottom: humble size
        found.append(dict(side=side, level=round(lvl, 2), lots=lots, chase=chase,
                          humble=humble, law6=law6_probation(bars, best, side),
                          sweep=round(sweep_line, 2), swept=int(sw), law2=law2,
                          law3=law3, law4=law4, law5=law5, sl=round(sl_px, 2),
                          s3=scenario3(bars, best, i, side),
                          key=f"{side}_{U.t}_{round(lvl, 2)}",
                          dist=abs(lvl - bars[-1].c)))
    return sorted(found, key=lambda a: a["dist"])


def _ema5(vals, n=5):
    """True EXPONENTIAL smoothing (Zee: 'smoothing method as EMA, not SMA')."""
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def _rsi14(closes, n=14):
    """Wilder RSI-14 series for the 4th Law (divergence)."""
    if len(closes) < n + 2:
        return [50.0] * len(closes)
    out = [50.0] * len(closes)
    gains = sum(max(closes[k] - closes[k - 1], 0) for k in range(1, n + 1))
    losses = sum(max(closes[k - 1] - closes[k], 0) for k in range(1, n + 1))
    ag, al = gains / n, losses / n
    out[n] = 100 - 100 / (1 + (ag / al if al else 1e9))
    for k in range(n + 1, len(closes)):
        d = closes[k] - closes[k - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        out[k] = 100 - 100 / (1 + (ag / al if al else 1e9))
    return out


def _swing_idx(seg, kind, k=3):
    """Confirmed price pivots (fractal K=3) inside a bar segment — the 'two swings'."""
    out = []
    for j in range(k, len(seg) - k):
        if kind == "L" and all(seg[j].l < seg[m].l for m in range(j - k, j + k + 1) if m != j):
            out.append(j)
        if kind == "H" and all(seg[j].h > seg[m].h for m in range(j - k, j + k + 1) if m != j):
            out.append(j)
    return out


def write_armed(bars):
    cands = find_armed(bars)
    if not cands:
        ARMED.unlink(missing_ok=True)
        WATCH.unlink(missing_ok=True)
        return None
    # ONE AUTHORITY RULES ALL (Zee 2026-08-04): "make it AUTO mode always UNLESS and
    # until I mark something (rare, once a day maybe)." The gate (fresh manual call,
    # else the humps' slant — see update_gate) decides the hunting side for BOTH the
    # box and the arming. Red slant -> green UHVs only; wrong-direction UHVs are
    # invisible and unfired. A manual press rules alone for 10 min, then AUTO forever.
    vis = [c for c in cands if zee_allows(c["side"])]
    if not vis:
        WATCH.unlink(missing_ok=True)              # no setup on the hunting side -> NO box
        w = None
    else:
        w = vis[0]                                 # the nearest lamp on the hunting side
    # WATCH file: the UHV box is visible from the moment the UHV forms — dashed on
    # the cockpit chart while the sweep is pending, solid once concrete.
    if w is not None:
        WATCH.write_text(json.dumps({k: w[k] for k in
                                     ("side", "level", "sweep", "swept", "law2", "law3", "law4", "law5", "law6", "s3")}
                                    | {"ts": int(time.time())}),
                         encoding="ascii")
    # ARM the nearest hunting-side setup — the Laws do NOT gate the apparition
    # (Zee 2026-08-04): "even without them, if no diamonds exist, we go forward
    # depending on our AUTO slant line.. the laws only allow us to take multiple
    # trades confidently." Diamonds set the RAID ALLOWANCE, not the permission:
    #     0 diamonds -> 1 apparition    1 -> 3    2 -> 6 (Zee's full burst)
    # SLOPE-OPPOSITION GUARD (2026-08-05): three losses today (-13.80, -11.10,
    # -30.00) were BUYs fired while the 30-bar slope was falling hard — the 3-peak
    # slant lags a fresh turn. Never fire against a strongly opposed slope.
    slope = TE.slope_of(_te_bars(bars))
    # THE REGIME SWITCH (Zee-approved 2026-08-06, receipts-backtested on both days:
    # today -306.90 -> -95.60, yesterday's slice -11.20 -> +32.20 at 72% WR):
    # ER < 0.25 = the tape is not trending -> NO entries for ANYONE, diamonds
    # included. The machine trades only when the tape moves like February moved.
    if choppy(bars) and not regime_forced() and not GATES_LIFTED:
        ARMED.unlink(missing_ok=True)
        return w
    dt = dead_tape(bars)
    if night_window():
        ARMED.unlink(missing_ok=True)              # night gate: the ghost rests
        return w
    if not DOOR_ENABLED:
        ARMED.unlink(missing_ok=True)   # THE DOOR IS RETIRED — never arm, ever.
        return w                        # (the WATCH box above still feeds the cockpit)
    ready = [c for c in cands if c["dist"] <= 2.0 and zee_allows(c["side"])
             and not no_demand(bars, c["side"])
             and not (dt and (int(c["swept"]) + int(c.get("law2", 0)) + int(c.get("law3", 0))
                              + int(c.get("law4", 0)) + int(c.get("law5", 0))) == 0)
             and not (c["side"] == "BUY" and slope < -0.10)
             and not (c["side"] == "SELL" and slope > 0.10)]
    if not ready:
        ARMED.unlink(missing_ok=True)              # nothing in striking distance
        return w
    a = ready[0]
    diamonds = (int(a["swept"]) + int(a.get("law3", 0))
                + int(a.get("law4", 0)) + int(a.get("law5", 0)))
    a["raids"] = {0: 1, 1: 3}.get(diamonds, 6)     # 2+ diamonds -> the full 6-raid burst
    # THE CLICK-BURST MULTIPLIER (Zee 2026-08-06, his real Feb-11 mechanic): "buy buy
    # buy multiple times 0.1 lots.. spread many ghosts into the room.. that's how the
    # multiplier should work — not with larger lot size but with more trades of 0.1
    # each." Conviction sets the CLICK COUNT; every click stays 0.10 and exits on its
    # own trail/ghost. (Big-lot tiers are dead: n=14, 36% WR, -$219.90.)
    # 2026-08-06 THE SIBLING RECKONING: era table on real fills — yesterday's
    # single-click machine +$35.70 (avg win $16.80) vs bracket siblings -$116.30
    # (avg win $6) vs 65s siblings -$206.10 (avg win $3). Multiplying tickets
    # multiplied the machine's timing errors and booked scraps by design.
    # CLICKS = 1, ALWAYS, until entry timing earns crowds back. Diamonds remain
    # as labels + raid allowance (sequential harvest-and-return, the proven kind).
    a["clicks"] = 1
    # ASIA DISCIPLINE (2026-08-06, the overnight -$110.80): chop hours 01:00-07:00
    # broker (22:00-04:00 UTC) get single clicks only — bursts need drift to harvest.
    from datetime import datetime as _dt, timezone as _tz
    if _dt.now(_tz.utc).hour >= 22 or _dt.now(_tz.utc).hour < 4:
        a["clicks"] = 1
    a["lots"] = 0.10

    a["diamonds"] = diamonds
    a["lots"] = min(a["lots"], RISK_CAP)
    # BUG3 fix (2026-08-06 audit): ids were minted from the clock at first sight,
    # so every MATCHER restart gave the same lamp a NEW id -> the EA saw a "new
    # lamp" and reset its raid counter. Deterministic id from the key: same lamp,
    # same id, across any number of restarts.
    import zlib
    aid = ARMED_IDS.setdefault(a["key"], int(zlib.crc32(a["key"].encode())) or 1)
    if len(ARMED_IDS) > 400:                       # keep the id map from growing forever
        for k in list(ARMED_IDS)[:200]: ARMED_IDS.pop(k)
    ARMED.write_text('{"id":%d,"side":"%s","level":%.2f,"lots":%.2f,"chase":%.2f,'
                     '"sweep":%.2f,"raids":%d,"clicks":%d,"sl":%.2f,"ts":%d}'
                     % (aid, a["side"], a["level"], a["lots"], a["chase"], a["sweep"],
                        a["raids"], a["clicks"], a["sl"], int(time.time())), encoding="ascii")
    return a


def main():
    for k, v in CFG.items(): setattr(B, k, v)
    # RESTART-REFIRE FIX (2026-08-06, the 18:33 late SELL): the dedup set lived in
    # memory, so every matcher restart re-emitted any setup still inside the 3-min
    # freshness window — and this matcher was restarted ~15 times today. The dedup
    # now persists to disk across restarts.
    _SEEN_F = Path(__file__).parent / ".emitted_setups.json"
    seq = 0                     # BUGFIX 2026-08-07: seq was ONLY initialised in the
                                # except branch, so whenever the dedup file loaded
                                # successfully every signal emission died with
                                # "cannot access local variable seq" — the machine
                                # could not fire at all once the door was retired.
    try:
        seen = set(tuple(x) for x in json.loads(_SEEN_F.read_text()))
    except Exception:
        seen = set()
    last_armed_key = None
    print("[oanda_matcher] live fast-scalp — watching oanda_m1.csv (ghost-door armed mode)")
    while True:
        try:
            bars = load_bars()
            if len(bars) > 30:
                last_closed = bars[-2].t     # -1 may still be forming
                # WALL-CLOCK freshness guard: if the data edge is stale (internet/feed
                # outage), do NOT fire — else we'd trade a hours-old setup at live price.
                stale_min = (datetime.utcnow() - bars[-1].t).total_seconds() / 60
                if stale_min > 3:
                    print(f"[oanda_matcher] data stale ({stale_min:.0f} min behind) — holding, no fire")
                    time.sleep(20); continue
                update_gate(bars)
                for s in B.detect_full(bars):
                    key = f"{s['open_t']}_{s['side']}"
                    # only fire setups whose breakout is on the last few CLOSED bars (fresh)
                    if key in seen or s["open_t"] < last_closed - timedelta(minutes=3):
                        continue
                    seen.add(key)
                    try:
                        _SEEN_F.write_text(json.dumps([list(k) for k in list(seen)[-200:]], default=str))
                    except Exception:
                        pass
                    if not zee_allows(s["side"]):
                        print(f"[oanda_matcher] cockpit gate: {s['side']} blocked by Zee's call")
                        continue
                    # THE BREAKOUT CANDLE'S CONDITIONS (Zee 2026-08-04):
                    #   1. momentum candle (strong body)
                    #   2. LOW volume — lower than the UHV's volume
                    _sl = TE.slope_of(_te_bars(bars))
                    if (s["side"] == "BUY" and _sl < -0.10) or                        (s["side"] == "SELL" and _sl > 0.10):
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"slope {_sl:+.2f} strongly opposed")
                        continue
                    if no_demand(bars, s["side"]):
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"no-demand rally / no-supply dip (a move nobody funds)")
                        continue
                    if choppy(bars) and not regime_forced() and not GATES_LIFTED:
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"REGIME SWITCH: tape not trending (ER < 0.25)")
                        continue
                    if dead_tape(bars) and not swept(bars, s["u"], s["i"], s["side"]):
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"dead tape and no conviction (boredom may not hunt)")
                        continue
                    bb = bars[s["i"]]
                    if bb.body_ratio < 0.5:
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"breakout not a momentum candle (body {bb.body_ratio:.2f})")
                        continue
                    if s["b_vol"] >= s["uhv_vol"]:
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"breakout volume {s['b_vol']} >= UHV {s['uhv_vol']} "
                              f"(the fundamental law needs LOWER)")
                        continue
                    seq += 1
                    lots = min(feb11_lots(bars, s), RISK_CAP)
                    _d = diamonds_for(bars, s)
                    s["clicks"] = clicks_for(_d)
                    _tip = selling_climax_tip(bars, s)
                    if _tip:
                        s["clicks"] = 3                    # full conviction
                        s["target"] = structural_target(bars, s["i"], s["side"], s["entry"])
                    if night_window():
                        print(f"[oanda_matcher] {s['side']} @{s['entry']} skipped — "
                              f"night gate (21:30-01:00 broker rests)")
                        continue
                    if stretch_of(bars, s["entry"], s["side"]) > STRETCH_PT                             or exhausted(bars, s["side"]):
                        lots = 0.10                # stretch/exhaustion humility
                    print(f"[oanda_matcher] {'*' * _d or 'no'} diamond(s)"
                          f"{' [TIP: selling-climax]' if _tip else ''} -> "
                          f"{s['clicks']} click(s) of {lots:.2f}"
                          f"{f' target {s.get(chr(34)+chr(34)) or s.get(_x)}' if False else ''}")
                    write_signal(seq, s, lots)
                    print(f"[oanda_matcher] SIGNAL #{seq} {s['side']} @{s['entry']} "
                          f"lots={lots:.2f} ({s['open_t'].strftime('%H:%M')}UTC)")
                a = write_armed(bars)
                if a and a["key"] != last_armed_key:
                    d = (int(a["swept"]) + int(a.get("law3", 0))
                         + int(a.get("law4", 0)) + int(a.get("law5", 0)))
                    hearts = (" ❤(L6)" if a.get("law6") else "") + (" ❤(SC3)" if a.get("s3") else "")
                    print(f"[oanda_matcher] {'💎' * d or 'no diamonds'}{hearts} — "
                          f"{a['side']} lamp @{a['level']} sweep line @{a['sweep']} "
                          f"clicks={a.get('clicks', 1)}x0.10 raids={a.get('raids', 1)}")
                last_armed_key = a["key"] if a else None
        except Exception as e:
            print("[oanda_matcher] err:", e, file=sys.stderr)
        time.sleep(5)   # local csv poll is free; the bridge refreshes it every 20s


if __name__ == "__main__":
    main()
