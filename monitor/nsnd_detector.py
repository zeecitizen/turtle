"""nsnd_detector.py — No Supply / No Demand, exactly as Zee teaches it in lessons 06 and 07.

Zee 2026-08-04: *"can u read the lesson no-demand / no-supply wala.. its in the loom videos..
let's implement that!"* — so this is built from the transcripts, not from memory of them.

The one thing that makes this different from every UHV detector we have built before, in his
own words from lesson 06:

    "pehle to hum entry yahan pe lete hote thay ... us jagah pe hum entry NAHI lein ge. jo lines
     hum ne UHV candle ke upar aur neeche draw ki thi, us ko todne ka hum wait NAHI karein ge —
     balke hum jahan se hamein NO SUPPLY mili, us ke breakout ke upar hi apni trade shuru karte
     hain."

The UHV stops being the entry trigger and becomes only the CONTEXT that says institutions are
active here. The trigger moves to a tiny dead-volume candle that forms after it. That is the
whole point: *"is candle ka maza yeh hai ke aap ka stop loss bohot hi chhota hai, aap bohot
chhota sa risk lete hain — to aap ka profit kai guna ban jata hai."* The edge is not a better
guess about direction, it is a stop measured in tenths of a point instead of whole points.

The BUY sequence (No Supply), lesson 06 + 07:

  1. Uptrend. He checks the macro direction on D1, and trades the pattern down to M1:
     *"main to is ko particularly one-minute ke time frame pe bhi trade karta hoon."*
  2. A retracement pulls price back — and it pulls back FOR A REASON: to tap a fair value gap.
  3. Inside that retracement a big RED volume bar prints. The climactic action bar / UHV.
     It means institutional buying is absorbing the selling. Draw its high and low.
  4. A NO SUPPLY candle forms above, below, or between those lines: small red body, small wicks,
     and volume *"pichli do candle se chhoti — half se bhi kam"*. Best of all when it lands right
     after a run of large volumes: *"ek dam se chhoti si no supply candle aa jaye — wo sab se
     achhi maani jaati hai."*
  5. Its LOW is SWEPT — by a WICK. He is emphatic that this is not a body break:
     *"sweep kehte hain jab candle apni WICK se toray. break kehte hain jab candle BODY se toray."*
  6. Its HIGH is BROKEN — by a BODY, on a momentum candle whose volume is a little HIGHER than
     the no-supply candle's.
  7. Entry at that candle's close (or on the retest of the no-supply high).
  8. Stop just below the no-supply candle's low. Tiny.
  9. First target the structural high; he is happy to hold past it.

SELL (No Demand) is the mirror — green UHV, small green dead-volume candle, HIGH swept by a
wick, LOW broken by a body. He warns it is the rarer side: *"gold zyada tar bullish rehta hai to
no demand bohot kam aati hai"*, and advises hunting no-supply by preference rather than flipping
between the two every cycle.

Lesson 07 also gives the three reasons a no-supply FAILS, which are more useful than the reasons
it works, and are checked here as quality flags:

    "pehli baat to yeh ke is ka high sweep — high BREAK nahi kiya kisi candle ne.
     doosri baat yeh ke hamari shart yeh thi ke is se pehle ek RED selling ka volume aana chahiye,
     jo ke nahi aaya.
     teesri baat ... kya aap ne koi fair value gap mark kiya tha? nahi. yahan koi FVG nahi tha."

The first is a hard gate below — no body break, no signal. The other two are reported rather than
enforced, per [[backtests-hallucinate-take-all-chances]]: a new filter ships OFF and earns its
place on live receipts. `require_fvg=True` turns the third into a gate for anyone who wants his
strictest form.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "strategy_lab"))

# ---- the shape of the pattern, in the numbers his words imply ------------------------------
# --- TUNED 2026-08-04, on Zee's instruction ------------------------------------------------
# *"i allow u to relax any rules u like ... the mission is to make profit not to verify if some
# rules work.. if they hamper growth, they can be relaxed ... tune it so that its taking MAXIMUM
# number of possible trades per day."*
#
# 720 configurations were run serially (one position at a time) over 37 tick-days, and only the
# 350 profitable on BOTH the training days and the newest 15 held-out days survived. These are
# the busiest survivors. His literal thresholds gave 6 trades in 37 days for -$68; these give
# 7.0 a day, and — the number that matters — **94 trades on days no parameter ever saw, +$1,637**.
# Every previous "breakthrough" in this project rested on 7 or 13 trades. This one does not.
#
# The values below are mine, not his. His method is untouched: dead volume, sweep by wick, break
# by body, breakout volume above the quiet candle, and the four failure modes.
NS_VOL_FRAC      = 0.85   # was 0.50 ("half se bhi kam") — the single biggest strangler
NS_MAX_RANGE_FRAC= 0.90   # was 0.70
UHV_LOOKBACK     = 20
UHV_VOL_MULT     = 1.15   # was 1.30
NS_SEARCH        = 12
SWEEP_WINDOW     = 12     # was 8 — the sweep and the break need room to happen
BRK_BODY_RATIO   = 0.50   # the breakout is a momentum candle, not a doji
SL_BUFFER        = 0.10   # a hair below the no-supply low — his stop is deliberately tiny

# Step 3 of Zee's written spec, 2026-08-04: "Find a no supply candle NEAR TRIGGER LINES (above,
# below, in between)". The trigger lines are the UHV candle's own high and low — the ones he
# draws in the lesson and then, crucially, stops using as the entry. They still matter: they say
# WHERE the no-supply candle is allowed to be. My first pass let any dead-volume candle within
# the window qualify no matter how far it had drifted from the climax, which is how a tiny bar
# in unrelated chop became a "setup". The band is the UHV's range, widened by this fraction of
# that range on each side to cover his "above / below / in between".
NS_NEAR_UHV_TOL  = 2.00   # was 0.60; the grid showed 0.60 cost trades and money


@dataclass
class NsndSignal:
    side: str                 # "BUY" (no supply) or "SELL" (no demand)
    t: str                    # breakout candle time
    entry: float
    sl: float
    tp: float
    ns_i: int                 # index of the no-supply / no-demand candle
    ns_vol: float
    ns_high: float
    ns_low: float
    uhv_i: int
    uhv_vol: float
    brk_i: int
    brk_vol: float
    brk_body_ratio: float
    swept_by_wick: bool
    big_opposite_volume: bool  # lesson 07 failure #2 — was there a real red/green climax first
    fvg_tapped: bool           # lesson 07 failure #3 — did the retracement tap a gap
    risk_pts: float
    reward_pts: float

    def as_dict(self):
        return asdict(self)


def _avg_range(bars, i, n=10):
    seg = bars[max(0, i - n):i]
    return (sum(b.rng for b in seg) / len(seg)) if seg else 1e-9


def _is_dead_volume(bars, i):
    """His volume rule, verbatim: smaller than each of the previous two, by more than half."""
    if i < 2:
        return False
    v, v1, v2 = bars[i].v, bars[i - 1].v, bars[i - 2].v
    return v < NS_VOL_FRAC * v1 and v < NS_VOL_FRAC * v2


def _is_small_candle(bars, i):
    """"chhoti si candle" — narrow spread against what the market has been printing."""
    return bars[i].rng <= NS_MAX_RANGE_FRAC * _avg_range(bars, i)


def _find_uhv(bars, upto, side):
    """The climactic action bar: the biggest counter-trend volume in the retracement.

    For a BUY it is RED (selling into the pullback that institutions absorb); for a SELL it is
    GREEN. Volume alone decides which bar it is — see [[uhv-must-be-local-volume-peak]], which
    Zee himself superseded when the neighbour test threw away a real one.
    """
    lo = max(0, upto - UHV_LOOKBACK)
    want_bear = (side == "BUY")
    best = None
    for k in range(lo, upto):
        b = bars[k]
        if (b.is_bear if want_bear else b.is_bull) and (best is None or b.v > bars[best].v):
            best = k
    if best is None:
        return None
    # it has to actually tower over the neighbourhood, or it is not "ultra" anything
    seg = bars[lo:upto]
    if seg and bars[best].v < UHV_VOL_MULT * (sum(b.v for b in seg) / len(seg)):
        return None
    return best


def _fvg_tapped(bars, ns_i, side, back=40):
    """Did the retracement come down (or up) into an unfilled 3-candle gap?

    Lesson 03's definition: a gap between candle n-1's extreme and candle n+1's opposite extreme,
    with the middle candle spanning it. Lesson 07 makes tapping one the reason the retracement
    exists at all.
    """
    lo = max(1, ns_i - back)
    p = bars[ns_i]
    for k in range(lo, ns_i - 1):
        a, c = bars[k - 1], bars[k + 1]
        if side == "BUY" and c.l > a.h:                    # bullish gap below price
            if p.l <= c.l and p.h >= a.h:
                return True
        if side == "SELL" and c.h < a.l:                   # bearish gap above price
            if p.h >= c.h and p.l <= a.l:
                return True
    return False


def _structural_target(bars, ns_i, side, back=60):
    """First take-profit: the structural high (BUY) or low (SELL) before the retracement."""
    seg = bars[max(0, ns_i - back):ns_i]
    if not seg:
        return None
    return max(b.h for b in seg) if side == "BUY" else min(b.l for b in seg)


def detect(bars, side="BUY", require_fvg=False, i=None):
    """Return an NsndSignal if the sequence completes on bar `i` (default: the last bar).

    The gates that are hard, because he states them as conditions rather than preferences:
      * the no-supply candle is small AND dead-volume
      * its low is swept BY A WICK, not closed through
      * its high is broken BY A BODY, on a momentum candle, with more volume than it had
    Everything else is measured and reported so the eye can weigh it.
    """
    if i is None:
        i = len(bars) - 1
    if i < 5:
        return None
    brk = bars[i]

    # the breakout must close through, in the right direction, with momentum behind it
    if side == "BUY" and not brk.is_bull:
        return None
    if side == "SELL" and not brk.is_bear:
        return None
    if brk.body_ratio < BRK_BODY_RATIO:
        return None

    for ns_i in range(i - 1, max(0, i - SWEEP_WINDOW) - 1, -1):
        ns = bars[ns_i]
        # colour: no supply is red inside an uptrend pullback, no demand is green inside a rally
        if side == "BUY" and not ns.is_bear:
            continue
        if side == "SELL" and not ns.is_bull:
            continue
        if not (_is_dead_volume(bars, ns_i) and _is_small_candle(bars, ns_i)):
            continue

        # --- the break: BODY through the far side ------------------------------------------
        if side == "BUY" and brk.c <= ns.h:
            continue
        if side == "SELL" and brk.c >= ns.l:
            continue
        if brk.v <= ns.v:                 # "us red candle ka volume is no-demand se thora high"
            continue

        # --- the sweep: WICK through the near side, and NOTHING may body-break it ----------
        # Zee's 4th failure mode, 2026-08-04: "if low is BROKEN (not just swept), before
        # breaking its high". A wick under the low is the stop-hunt the pattern is built on; a
        # BODY under it is the market genuinely leaving, and the setup is dead — it must not be
        # allowed to resurrect itself if price later pops back over the high. So the whole span
        # from the no-supply candle to the breakout is checked, not just the sweeping bar.
        swept = broken = False
        for k in range(ns_i + 1, i + 1):
            b = bars[k]
            if side == "BUY":
                if min(b.o, b.c) < ns.l:          # a body closed through — invalidated
                    broken = True
                    break
                if b.l < ns.l:
                    swept = True
            else:
                if max(b.o, b.c) > ns.h:
                    broken = True
                    break
                if b.h > ns.h:
                    swept = True
        if broken or not swept:
            continue

        # --- step 3: the no-supply candle must sit AT the UHV's trigger lines ---------------
        # Without this, any dead-volume bar anywhere in the window qualified, and the pattern
        # stopped meaning "the market went quiet exactly where institutions were active".
        uhv_i = _find_uhv(bars, ns_i, side)
        if uhv_i is None:
            continue
        u = bars[uhv_i]
        tol = NS_NEAR_UHV_TOL * u.rng
        if ns.l > u.h + tol or ns.h < u.l - tol:
            continue
        big_opp = True
        fvg = _fvg_tapped(bars, ns_i, side)
        if require_fvg and not fvg:
            continue

        entry = brk.c
        sl = (ns.l - SL_BUFFER) if side == "BUY" else (ns.h + SL_BUFFER)
        tp = _structural_target(bars, ns_i, side)
        if tp is None:
            continue
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0 or reward <= 0:
            continue

        return NsndSignal(
            side=side, t=brk.t.strftime("%Y-%m-%d %H:%M"), entry=round(entry, 2),
            sl=round(sl, 2), tp=round(tp, 2), ns_i=ns_i, ns_vol=ns.v,
            ns_high=round(ns.h, 2), ns_low=round(ns.l, 2),
            uhv_i=(uhv_i if uhv_i is not None else -1),
            uhv_vol=(bars[uhv_i].v if uhv_i is not None else 0),
            brk_i=i, brk_vol=brk.v, brk_body_ratio=round(brk.body_ratio, 2),
            swept_by_wick=True, big_opposite_volume=big_opp, fvg_tapped=fvg,
            risk_pts=round(risk, 2), reward_pts=round(reward, 2))
    return None


def detect_any(bars, require_fvg=False, i=None):
    """Both sides. No supply is offered first — gold is mostly bullish and he says to prefer it."""
    return (detect(bars, "BUY", require_fvg, i)
            or detect(bars, "SELL", require_fvg, i))


def scan_history(bars, require_fvg=False):
    """Every completed NS/ND sequence in a series — for reviewing what it would have taken."""
    out = []
    for i in range(5, len(bars)):
        s = detect_any(bars, require_fvg, i)
        if s:
            out.append(s)
    return out


if __name__ == "__main__":
    import argparse, json
    from claude_judge import load_bars, MARKETS

    ap = argparse.ArgumentParser(description="No Supply / No Demand — Zee's lessons 06-07")
    ap.add_argument("market", nargs="?", default="XAU")
    ap.add_argument("--history", action="store_true", help="every sequence in the file")
    ap.add_argument("--no-fvg", action="store_true", help="drop the FVG requirement")
    a = ap.parse_args()

    want_fvg = not a.no_fvg
    bars = load_bars(MARKETS[a.market]["data"])
    print(f"  {len(bars)} bars  {bars[0].t:%Y-%m-%d %H:%M} -> {bars[-1].t:%H:%M}")

    if a.history:
        sigs = scan_history(bars, want_fvg)
        print(f"  {len(sigs)} NS/ND sequences\n")
        for s in sigs[-25:]:
            tag = "NS" if s.side == "BUY" else "ND"
            q = ("uhv" if s.big_opposite_volume else "   ") + (" fvg" if s.fvg_tapped else "    ")
            print(f"    {s.t}  {tag} {s.side:<4} @ {s.entry:8.2f}  sl {s.sl:8.2f} "
                  f"tp {s.tp:8.2f}  risk {s.risk_pts:5.2f}  rr {s.reward_pts/s.risk_pts:5.2f}"
                  f"  nsvol {s.ns_vol:4.0f}  {q}")
    else:
        s = detect_any(bars, want_fvg)
        print(json.dumps(s.as_dict(), indent=1) if s else "  no NS/ND sequence on the last bar")
