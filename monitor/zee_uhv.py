"""zee_uhv.py — the UHV detector rebuilt from Zee's own 146 labels.

Zee, 2026-08-10: "i labelled more than a 100 setups for you to see which one is UHV
which one is not."

He had. `monitor/setup_labels/zee_labels.json` holds 146 setups annotated in his own
words, and only 27 of them say the machine's drawing was right — roughly 18%. Every
detector we have ever shipped encoded MY reading of "ultra high volume". This one
encodes his, rule by rule, with his sentence quoted above each check so the next person
to touch it can see whose authority it carries.

Nothing here is invented. Where his words are ambiguous the code takes the reading that
appears most often across the 146 and says so in the comment.

DOCTRINE: this file DETECTS. It does not simulate P&L. Python may generate a
hypothesis; only MT5's tester or live fills may promote one (CLAUDE.md, first section).
"""
import statistics
from dataclasses import dataclass


@dataclass
class Setup:
    origin: int      # bar that STARTED the retracement
    uhv: int         # the ultra-high-volume candle inside it
    brk: int         # the breakout candle
    side: str        # "buy" | "sell"
    why: str = ""


def _green(b):
    return b["c"] > b["o"]


def _red(b):
    return b["c"] < b["o"]


def _body_hi(b):
    return max(b["o"], b["c"])


def _body_lo(b):
    return min(b["o"], b["c"])


# ── 0. REGIME ────────────────────────────────────────────────────────────────────
#   "we cannot sell in an uptrend, we only buy in an uptrend"            (#e027)
#   "we only taken buys during uptrend's retracement"                    (#m2)
#   "our setup only works if the market is not in a ranging condition"   (#e012)
#   "price was making lower lows prio to cyan so it was not in an uptrend,
#    therefore we cannot buy unless a proper uptrend is confirmed"       (#m15)
def trend_at(bars, i, look=40, pivot=2):
    """Higher highs AND higher lows = uptrend; the mirror = downtrend; else ranging.

    He judges trend by structure, not by a moving average — every one of his trend
    complaints is phrased as 'price made a lower low' or 'formed HH'. So this reads
    swing pivots, and returns 0 (ranging) when the structure does not agree, because
    a ranging tape disqualifies the setup outright.
    """
    lo = max(1, i - look)
    seg = bars[lo:i]
    if len(seg) < 12:
        return 0
    highs, lows = [], []
    for k in range(pivot, len(seg) - pivot):
        w = seg[k - pivot:k + pivot + 1]
        if seg[k]["h"] == max(x["h"] for x in w):
            highs.append(seg[k]["h"])
        if seg[k]["l"] == min(x["l"] for x in w):
            lows.append(seg[k]["l"])
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return +1
        if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return -1
    return 0


# ── 1. THE RETRACEMENT, and where it STARTS ──────────────────────────────────────
#   BUY  (uptrend): the retracement is made of RED candles.
#     "In uptrend we take a buy -> in uptrend we find a retracement OF RED COLORED
#      CANDLES"                                                          (#8)
#     "the origin candle was a valid retracement itself as it broke the low of
#      previous green"                                                   (#e025)
#     "its not a valid retracement as the last green's low wasn't broken by the
#      origin, so no retracement started"                                (#e014)
#   SELL (downtrend): the mirror, in GREEN.
#     "a valid retracement starts when a [candle] breaks the high of the previous
#      [opposite] candle WITH ITS BODY"                                  (#2)
#     "the green arrow on 16:35 candle is not a valid retracement as the body of
#      green candle doesnot break above the last red at 1630"            (#c4)
def retracement_origin(bars, i, side, back=15):
    """Return the index of the candle that STARTED the current retracement, or None.

    The body requirement is the part every previous detector missed: he rejects a
    retracement whose candle only pokes past the previous extreme with a wick.
    """
    want_red = (side == "buy")
    for k in range(i, max(0, i - back), -1):
        b = bars[k]
        if want_red and not _red(b):
            continue
        if (not want_red) and not _green(b):
            continue
        prev = None                      # the last candle of the OPPOSITE colour
        for j in range(k - 1, max(0, k - 8), -1):
            if _green(bars[j]) if want_red else _red(bars[j]):
                prev = bars[j]
                break
        if prev is None:
            continue
        if want_red:
            if _body_lo(b) < prev["l"]:          # body must clear the green's LOW
                return k
        else:
            if _body_hi(b) > prev["h"]:          # body must clear the red's HIGH
                return k
    return None


# ── 2. THE UHV ───────────────────────────────────────────────────────────────────
#   "a correct UHV should have been the largest volume at 5:30"          (#1)
#   "Y has the lowest volume among its neighbors, its not a valid uhv because its
#    not having highest volume"                                          (#5)
#   "for a buy setup the uhv should be a red candle"                     (#11)
#   "uhv candle for sell case must be a green"                           (#24)
#   "Y is not a UHV as its not in a valid retracement"                   (#6)
#   "i think UHV should also be a strong candle, so that when we mitigate it we are
#    mitigating strong sellers (winning the war with a lowvolume breakout)"
#                                                                        (#loser_001)
def find_uhv(bars, origin, i, side, min_body_frac=0.30):
    """The loudest candle of the RIGHT COLOUR inside the retracement.

    Scope matters and is his, not ours: the search runs from the origin forward, so a
    louder candle outside the retracement can never be chosen. That single constraint
    is what most of his 'not in a valid retracement' complaints are about.
    """
    want_red = (side == "buy")
    best, bestv = None, -1
    for k in range(origin, i):
        b = bars[k]
        if want_red and not _red(b):
            continue
        if (not want_red) and not _green(b):
            continue
        if b["v"] > bestv:
            best, bestv = k, b["v"]
    if best is None:
        return None
    b = bars[best]
    rng = b["h"] - b["l"]
    if rng <= 0 or abs(b["c"] - b["o"]) / rng < min_body_frac:
        return None                              # "should also be a strong candle"
    # louder than its immediate neighbours — his "largest among its neighbors"
    if best > 0 and bars[best - 1]["v"] > b["v"]:
        return None
    if best + 1 < len(bars) and bars[best + 1]["v"] > b["v"]:
        return None
    return best


# ── 3. THE BREAKOUT ──────────────────────────────────────────────────────────────
#   "for a buy setup the breakout should be with a green colored candle"  (#8)
#   "breakout candle in sell case must be red"                            (#24)
#   "the B is not breaking above the HIGH of the Y"                       (#5)
#   "the R cannot be considered as breakout candle since its body doesnot break/cross
#    below the Y's lowest point (wick's end)"                             (#33)
#   "14:50 would be a valid breakout candle if its volume were lower than the Y
#    which it is not"                                                     (#15)
#   "we mark only 1 Breakout (as the high of the UHV is crossed by a breakout candle
#    only once)"                                                          (#13)
#   "B cannot be same candle as Y"                                        (#17)
def breakout_after(bars, uhv, side, limit=12):
    """The FIRST candle that truly breaks the UHV — colour, body, and quieter."""
    u = bars[uhv]
    want_green = (side == "buy")
    for k in range(uhv + 1, min(len(bars), uhv + 1 + limit)):
        b = bars[k]
        if want_green and not _green(b):
            continue
        if (not want_green) and not _red(b):
            continue
        # the BODY must clear the UHV's wick end, not merely its body
        crossed = _body_hi(b) > u["h"] if want_green else _body_lo(b) < u["l"]
        if not crossed:
            continue
        if b["v"] >= u["v"]:
            return None        # "only if the Bs volume was lesser than the Y" (#7)
        return k               # the first true crossing, and only that one
    return None


# ── the whole spec, in order ─────────────────────────────────────────────────────
def detect(bars, i):
    """Ask, at bar i, whether Zee would call this a setup. Returns a Setup or None."""
    t = trend_at(bars, i)
    if t == 0:
        return None                                    # ranging disqualifies
    side = "buy" if t > 0 else "sell"
    origin = retracement_origin(bars, i - 1, side)
    if origin is None:
        return None
    uhv = find_uhv(bars, origin, i, side)
    if uhv is None or uhv == i:
        return None
    brk = breakout_after(bars, uhv, side)
    if brk is None or brk != i:                        # fire on the breakout bar itself
        return None
    return Setup(origin, uhv, brk, side,
                 f"{side} · origin {origin} · uhv {uhv} (vol {bars[uhv]['v']}) · "
                 f"brk {brk} (vol {bars[brk]['v']})")


def scan(bars, start=60):
    out = []
    for i in range(start, len(bars)):
        s = detect(bars, i)
        if s:
            out.append(s)
    return out
