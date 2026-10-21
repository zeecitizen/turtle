"""sim_full.py - the Turtle TV Tester with EVERY input of Saad_strategy_15min (Zee 2026-10-20: "some of the settings say MT5 only ... can u make them
have an effect" -> "yes do them all"). Same walk as sim.run (MT5's 1-minute OHLC order, the EA's order of decisions) plus:
  exit mode 0 (v1.23's exits): LONG target = the exit EMA (touch or close), SHORT target = the last support (swing low), TP1 touch -> partial
  close + breakeven + $ trail + TP2 / TP3 = next resistance / support, CTC at a share of the way, ride + lock at the TP, ATR / candle / pip
  trails, BE at $X, profit lock at $X, fixed TP, time exit;
  entry modes 1 (dip after the break) and 2 (liquidity sweep); several positions (InpMaxPos, InpReplace, InpExtraDir);
  filters: chop (efficiency ratio), HTF trend EMA, EMA alignment / price side / slope / gap, max spread, weekday, no new trades before the close,
  cool-down after a loss, daily loss / target / loss %; sizing: InpRiskPct with minimum-lot and maximum-lot rules; ADX of any length.
Every number is the EA's own rule, written from mt5/Saad_strategy_15min.mq5; MT5's Strategy Tester stays the judge (validate.py)."""
import os

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np                                     # noqa: E402
from numba import njit                                 # noqa: E402

FULL = ["InpTrigBid", "InpLongExit", "InpLongTpPips", "InpSwingPivot", "InpSwingLook", "InpShortTpPips", "InpMinTpPips", "InpMaxTpPips", "InpBeUsd",
        "InpNoNewMins", "InpLongTouch", "InpLongTrailUsd", "InpLongResTp", "InpLongResTp1", "InpResTp1Ride", "InpShortTouch", "InpTrailStepUsd",
        "InpShortTrailUsd", "InpBeTpPct", "InpTrail", "InpTrailSide", "InpRide", "InpTrailMode", "InpTrailN", "InpTrailPips", "InpTrailAtr",
        "InpTrailStart", "InpRideLock", "InpLockPips", "InpChopEr", "InpChopErLook", "InpHtfMin", "InpHtfEma", "InpTrendAlign", "InpPriceSide",
        "InpSlopePips", "InpSlopeLook", "InpEmaGapPips", "InpMaxSpreadPts", "InpSkipDow", "InpLockAtUsd", "InpLockUsd", "InpFixTpPips",
        "InpMaxBars", "InpCoolBars", "InpMaxPos", "InpReplace", "InpExtraDir", "InpDayLossUsd", "InpDayTargetUsd", "InpEntryMode",
        "InpRetestFrac", "InpRetestBars", "InpSweepPips", "InpSweepBars", "InpSweepEntry", "InpSweepSlPips", "InpPartialPct", "InpTp1Be",
        "InpRiskPct", "InpMinLotRiskPct", "InpMaxLots", "InpDayLossPct", "InpAdxPeriod", "InpSkipBothEma"]
F = {n: 41 + i for i, n in enumerate(FULL)}            # indices in the parameter vector after sim.NAMES (41 entries)
MAXP = 8
# position fields
SD, EN, SL, TP, EXE, NOTP, RIDE, EK, ET, BEST, USD, TPN, STG, RES1, NX, LOTS, REAL, SWP, BKT, BTP, CTC = range(21)
# Exit Lab fields (exitlab.py): initial risk, ATR at entry, best / worst price reached, partials done, lab target, original lots, close counters
R0, ATE, MFP, MAP, P1D, P2D, LTP, ORL, CXN, FBN, LPD = range(21, 32)          # LPD (v1.31): the loss cut (partial at -R) done
NPS = 32
# the Exit Lab's parameter vector E (all zero = the engine exactly as before). Only for exit modes 1 and 2 (the v1.25 exits).
(E_ON, E_TGT, E_TGTK, E_FB, E_FBB, E_FBN, E_CX, E_CXB, E_CXN, E_CXW, E_CXA, E_P1R, E_P1F, E_P1BE, E_P2R, E_P2F, E_BER, E_BEO, E_LOCK,
 E_TR, E_TRK, E_TRA, E_TRB, E_MAXB, E_STB, E_STR, E_ADX, E_FRI, E_PESS, E_LCAP, E_LPR, E_LPF, E_DCB, E_DCR) = range(34)
NE = 36
# EA inputs that only act with InpExitMode 0 (the v1.23 exits): in exit modes 1-2 the EA's ManageTrade / ManageBar return before reading them
MODE0_ONLY = {"InpLongExit", "InpLongTpPips", "InpSwingPivot", "InpSwingLook", "InpShortTpPips", "InpMinTpPips", "InpMaxTpPips", "InpBeUsd",
              "InpLongTouch", "InpLongTrailUsd", "InpLongResTp", "InpLongResTp1", "InpResTp1Ride", "InpShortTouch", "InpTrailStepUsd",
              "InpShortTrailUsd", "InpBeTpPct", "InpTrail", "InpTrailSide", "InpRide", "InpTrailMode", "InpTrailN", "InpTrailPips", "InpTrailAtr",
              "InpTrailStart", "InpRideLock", "InpLockPips", "InpLockAtUsd", "InpLockUsd", "InpMaxBars", "InpPartialPct", "InpTp1Be"}
# (InpFixTpPips is NOT here: the EA sends it as the order's broker TP in every exit mode)
EFIELDS = ["on", "tgt", "tgt_k", "fb", "fb_buf", "fb_n", "cx", "cx_buf", "cx_n", "cx_when", "cx_after", "p1_r", "p1_frac", "p1_be", "p2_r",
           "p2_frac", "be_r", "be_off", "lock_r", "tr", "tr_k", "tr_act", "tr_buf", "max_bars", "stale_bars", "stale_r", "adx_exit", "fri_hour",
           "pess", "lcap", "lp_r", "lp_frac", "dc_bars", "dc_r"]
# v1.31 loss cutters (Zee 2026-10-21: "make it the most intelligent loss cutter possible"): lcap = the stop never further than $X from the entry
# (the tighter of the setup's stop and this), lp_r / lp_frac = close a share when the trade is lp_r R in loss, dc_bars / dc_r = after N candles
# the stop tightens to the entry + dc_r R (negative = still in loss)


# v1.30: the Exit Lab as EA inputs (InpX*) - the same building blocks, so an exit is just settings
XMAP = {"InpXTgt": "tgt", "InpXTgtK": "tgt_k", "InpXFb": "fb", "InpXFbBuf": "fb_buf", "InpXFbN": "fb_n", "InpXCx": "cx", "InpXCxBuf": "cx_buf", "InpXCxN": "cx_n",
        "InpXCxWhen": "cx_when", "InpXCxAfter": "cx_after", "InpXP1R": "p1_r", "InpXP1Frac": "p1_frac", "InpXP1Be": "p1_be", "InpXP2R": "p2_r", "InpXP2Frac": "p2_frac",
        "InpXBeR": "be_r", "InpXBeOff": "be_off", "InpXLockR": "lock_r", "InpXTr": "tr", "InpXTrK": "tr_k", "InpXTrAct": "tr_act", "InpXTrBuf": "tr_buf",
        "InpXMaxBars": "max_bars", "InpXStaleBars": "stale_bars", "InpXStaleR": "stale_r", "InpXAdxExit": "adx_exit", "InpXFriHour": "fri_hour",
        "InpXLossCap": "lcap", "InpXLpR": "lp_r", "InpXLpFrac": "lp_frac", "InpXDecayBars": "dc_bars", "InpXDecayR": "dc_r"}
XFIELDS = {v: k for k, v in XMAP.items()}


def _xv(v):
    s = str(v).strip().lower()
    return 1.0 if s == "true" else 0.0 if s in ("false", "") else float(s)


def lab_from_inputs(inputs):
    """the InpX* inputs -> the Exit Lab recipe, or None when they are all off (the EA's XOn())"""
    L = {f: _xv(inputs[k]) for k, f in XMAP.items() if k in inputs}
    g = lambda f, d=0.0: L.get(f, d)  # noqa: E731
    on = (g("tgt") != 0 or g("fb") != 0 or g("fb_buf") > 0 or g("fb_n", 1) > 1 or g("cx") != 0 or g("p1_r") > 0 or g("p2_r") > 0 or g("be_r") > 0 or g("lock_r") > 0
          or g("tr") != 0 or g("max_bars") > 0 or g("stale_bars") > 0 or g("adx_exit") > 0 or g("fri_hour") > 0
          or g("lcap") > 0 or g("lp_r") > 0 or g("dc_bars") > 0)
    return dict(L, pess=1.0) if on else None


def evec(lab):
    """{'tgt': 2, 'tgt_k': 1.5, ...} -> E. None / {} = the Exit Lab off."""
    E = np.zeros(NE)
    if lab:
        for k, v in lab.items():
            if k in EFIELDS:
                E[EFIELDS.index(k)] = float(v)
        E[E_ON] = 1.0
    return E


@njit(cache=True)
def _support(l15, k, below, p, look):
    for s in range(1 + p, 1 + p + look):
        i = k - s
        if i - p < 0:
            break
        l = l15[i]
        if l >= below:
            continue
        piv = True
        for kk in range(1, p + 1):
            if l15[i + kk] <= l or l15[i - kk] < l:
                piv = False
                break
        if piv:
            return l
    return 0.0


@njit(cache=True)
def _resist(h15, k, above, p, look):
    for s in range(1 + p, 1 + p + look):
        i = k - s
        if i - p < 0:
            break
        h = h15[i]
        if h <= above:
            continue
        piv = True
        for kk in range(1, p + 1):
            if h15[i + kk] >= h or h15[i - kk] > h:
                piv = False
                break
        if piv:
            return h
    return 0.0


@njit(cache=True)
def _shape(o, h, l, c, atr, P):
    rng = h - l
    if rng <= 0:
        return 0, 0
    if P[14] > 0 and rng < P[14] * atr:
        return 0, 0
    body = abs(c - o)
    up = h - max(o, c)
    lo = min(o, c) - l
    pinBull = body <= P[3] * rng and lo >= P[2] * rng and up <= P[4] * rng
    pinBear = body <= P[3] * rng and up >= P[2] * rng and lo <= P[4] * rng
    isPin = pinBull or pinBear
    hamBull = (not isPin) and lo >= P[12] * body and lo > 0 and up <= P[13] * rng
    hamBear = (not isPin) and up >= P[12] * body and up > 0 and lo <= P[13] * rng
    maru = (not isPin) and (not hamBull) and (not hamBear) and body >= P[9] * rng
    if isPin:
        if P[5] < 0.5:
            return 0, 0
        if P[6] < 0.5:
            return 2, 1
        if P[7] > 0.5 and ((c < o) if pinBull else (c > o)):
            return 0, 0
        return (1 if pinBull else -1), 1
    if hamBull:
        return (1 if P[10] > 0.5 else 0), 2
    if hamBear:
        return (-1 if P[11] > 0.5 else 0), 2
    if maru:
        if P[8] < 0.5:
            return 0, 0
        return (1 if c > o else -1), 3
    return 0, 0


@njit(cache=True)
def _online(o, h, l, c, e, side, P):
    tol = P[18] * 0.1
    if e <= 0:
        return False
    if P[17] < 0.5:
        return l - tol <= e and h + tol >= e
    if side > 0:
        return l - tol <= e and min(o, c) >= e
    return h + tol >= e and max(o, c) <= e


@njit(cache=True)
def _pt(o1, h1, l1, c1, j, q):
    n = o1.shape[0]
    while q > 3 and j + 1 < n:
        q -= 4
        j += 1
    if q > 3:
        q = 3
    if q == 0:
        return o1[j]
    if q == 3:
        return c1[j]
    up = c1[j] >= o1[j]
    if q == 1:
        return l1[j] if up else h1[j]
    return h1[j] if up else l1[j]


@njit(cache=True)
def _trail_on(P, side):
    return P[F_TRAIL] > 0.5 and (P[F_TSIDE] == 2 or (side > 0 and P[F_TSIDE] == 0) or (side < 0 and P[F_TSIDE] == 1))


F_TRAIL = 41 + FULL.index("InpTrail")
F_BOTH = 41 + FULL.index("InpSkipBothEma")
F_TSIDE = 41 + FULL.index("InpTrailSide")


@njit(cache=True)
def _close(out, nt, ps, x, xp, tq, kout, why, lots_frac):
    """close lots_frac of position x at xp; returns (nt, banked pnl). lots_frac 1 = all (records the trade)."""
    side = ps[x, SD]
    part_lots = ps[x, LOTS] * lots_frac
    pn = (xp - ps[x, EN]) * side * part_lots * 100.0
    if lots_frac >= 0.999:
        tot = ps[x, REAL] + pn + ps[x, SWP]
        if nt < out.shape[0]:
            out[nt, 0] = side; out[nt, 1] = ps[x, ET]; out[nt, 2] = ps[x, EN]; out[nt, 3] = ps[x, SL]; out[nt, 4] = tq; out[nt, 5] = xp
            out[nt, 6] = tot; out[nt, 7] = ps[x, SWP]; out[nt, 8] = ps[x, BKT]; out[nt, 9] = ps[x, NX]; out[nt, 10] = 0
            out[nt, 11] = ps[x, EK]; out[nt, 12] = kout; out[nt, 13] = why; out[nt, 14] = ps[x, LOTS]
            if out.shape[1] >= 20:                     # Exit Lab: best / worst move ($ per ounce), initial risk, original lots, partials
                out[nt, 15] = (ps[x, MFP] - ps[x, EN]) * side; out[nt, 16] = (ps[x, EN] - ps[x, MAP]) * side
                out[nt, 17] = ps[x, R0]; out[nt, 18] = ps[x, ORL]; out[nt, 19] = ps[x, P1D] + ps[x, P2D] + ps[x, LPD]
        ps[x, SD] = 0
        return nt + 1, pn + ps[x, SWP]
    ps[x, REAL] += pn
    ps[x, LOTS] -= part_lots
    return nt, pn


@njit(cache=True)
def run_full(t15, hr15, dow15, o15, h15, l15, c15, ef, es, atr, adx, htfc, htfe1, htfe2, t1, o1, h1, l1, c1, sp1, k1, first1, m2c, roll, day1,
             P, X, E, bandB, bandS, OS, OL, out, setups, stats):
    """out rows: side, entry_t, entry, sl(final), exit_t, exit, pnl, swap, bucket, nxE, ghost, entry_k15, exit_k15, reason, lots
       reasons: 1 stop 2 next-EMA target 3 close-back 4 day close 5 TP 6 trailing stop 7 breakeven 8 time exit"""
    n1 = t1.shape[0]
    bar = 900                                                # the candle's length (s): 900 on M15, 60 on the 1-minute data (year1)
    for z in range(1, min(200, t15.shape[0])):
        bar = min(bar, t15[z] - t15[z - 1])
    af = 2.0 / (P[0] + 1.0)
    asl = 2.0 / (P[1] + 1.0)
    pip = 0.1
    lat = int(X[11])
    dep = X[16] if X[16] > 0 else 100000.0
    ps = np.zeros((MAXP, NPS))
    nt = 0
    ns = 0
    pSide = 0; pHigh = 0.0; pLow = 0.0; pLeft = 0; pK = -1; pExit = 50
    swept = False; sweepExt = 0.0
    aSide = 0; aLevel = 0.0; aHigh = 0.0; aLow = 0.0; aLeft = 0; aExit = 50
    gh = 0; gEn = 0.0; gSl = 0.0; gNx = 0; gK = -1; gT = 0; gB = -1; gExitE = 50; gTp = 0.0; gNoTp = False
    equity = dep; dayStart = dep; dayPnl = 0.0; curDay = -1
    coolUntil = 0
    busy0 = False
    pts = np.empty(4)
    PEXIT_SLOW = 50
    for j in range(n1):
        k = k1[j]
        spr = X[2] if X[2] > 0 else sp1[j] * X[10]
        o = o1[j]
        flt = 0.0                                            # open trades at this minute's open: MT5's ACCOUNT_EQUITY counts them
        for x in range(MAXP):
            if ps[x, SD] != 0:
                flt += ((o if ps[x, SD] > 0 else o + (X[2] if X[2] > 0 else sp1[j] * X[10])) - ps[x, EN]) * ps[x, SD] * ps[x, LOTS] * 100.0 + ps[x, REAL] + ps[x, SWP]
        if day1[j] != curDay:
            curDay = day1[j]; dayStart = equity + flt; dayPnl = 0.0
        if roll[j] > 0 and X[3] > 0.5:
            for x in range(MAXP):
                if ps[x, SD] != 0:
                    ps[x, SWP] += (-61.6 if ps[x, SD] > 0 else 40.5) * ps[x, LOTS] * roll[j]
        npos = 0
        sd0 = 0
        for x in range(MAXP):
            if ps[x, SD] != 0:
                npos += 1
                if sd0 == 0:
                    sd0 = int(ps[x, SD])
        if sd0 == 0:
            sd0 = gh
        sdt = 0                                               # a trade on a tight $ trail: MT5 moves its stop every tick, so a bounce
        for x in range(MAXP):                                 # inside the minute stops it - favourable extreme first, then the adverse one
            if ps[x, SD] != 0 and ps[x, USD] > 0.5 and sdt == 0:
                sdt = int(ps[x, SD])
        pts[0] = o
        if sdt != 0:
            pts[1] = h1[j] if sdt > 0 else l1[j]
            pts[2] = l1[j] if sdt > 0 else h1[j]
        elif X[15] > 0.5 and sd0 != 0:
            pts[1] = l1[j] if sd0 > 0 else h1[j]
            pts[2] = h1[j] if sd0 > 0 else l1[j]
        elif c1[j] >= o:
            pts[1] = l1[j]; pts[2] = h1[j]
        else:
            pts[1] = h1[j]; pts[2] = l1[j]
        pts[3] = c1[j]
        blind = t1[j] < X[4]
        closed = j == 0 or day1[j] != day1[j - 1]          # the session's first minute: MT5 answers 'market closed'
        for q in range(4):
            cur = pts[q]
            prv = pts[q - 1] if q > 0 else cur
            tq = t1[j] + q * 15
            mins_close = (m2c[j] - q * 15) // 60
            if q == 0 and first1[j] == 1:
                busy0 = gh != 0
                for x in range(MAXP):
                    if ps[x, SD] != 0:
                        busy0 = True
            # 1. DayCloseCheck
            inwin = (not blind) and P[36] > 0 and (m2c[j] < (P[36] + 1) * 60 or (m2c[j] == (P[36] + 1) * 60 and q > 0))
            if inwin:
                for x in range(MAXP):
                    sd = ps[x, SD]
                    if sd != 0:
                        bidask = cur if sd > 0 else cur + spr
                        if (bidask - ps[x, EN]) * sd * ps[x, LOTS] * 100.0 + ps[x, SWP] < 0:
                            nt, pn = _close(out, nt, ps, x, bidask - sd * X[8], tq, k, 4, 1.0)
                            equity += pn; dayPnl += pn
                            if pn < 0:
                                coolUntil = tq + int(P[85]) * bar
                if gh != 0 and ((cur < gEn) if gh > 0 else (cur + spr > gEn)):
                    gh = 0
            for rep in range(2):
                # 2. ManageTick for every position + ghost
                for x in range(MAXP):
                    sd = ps[x, SD]
                    if sd == 0:
                        continue
                    if blind and ps[x, EK] == k:
                        continue
                    bid = cur
                    ask = cur + spr
                    en = ps[x, EN]
                    s_ = ps[x, SL]
                    if sd > 0:
                        ps[x, MFP] = max(ps[x, MFP], bid); ps[x, MAP] = min(ps[x, MAP], bid)
                    else:
                        ps[x, MFP] = min(ps[x, MFP], ask); ps[x, MAP] = max(ps[x, MAP], ask)
                    # v1.31 loss cut: a share closed when the trade is lp_r R in loss - only where that level comes before the stop, never in the
                    # entry minute (the Exit Lab waits for the next minute, as the EA's XTick)
                    if E[E_ON] > 0.5 and E[E_LPR] > 0 and ps[x, NX] != 0 and ps[x, LPD] < 0.5 and ps[x, R0] > 0 and ps[x, ET] < t1[j]:
                        lv = en - sd * E[E_LPR] * ps[x, R0]
                        before = (lv > s_ + 0.005) if sd > 0 else (s_ == 0 or lv < s_ - 0.005)
                        if before and ((bid <= lv) if sd > 0 else (ask >= lv)):
                            if sd > 0:
                                xp = lv if prv > lv else bid
                            else:
                                xp = lv if prv + spr < lv else ask
                            ps[x, LPD] = 1.0
                            cl = np.floor(ps[x, ORL] * E[E_LPF] / 0.01 + 0.5) * 0.01
                            if cl >= 0.01:
                                fr = 1.0 if cl >= ps[x, LOTS] - 0.005 else cl / ps[x, LOTS]
                                nt, pn = _close(out, nt, ps, x, xp - sd * X[8], tq, k, 17, fr)
                                equity += pn; dayPnl += pn
                                if fr >= 0.999:
                                    if pn < 0:
                                        coolUntil = tq + int(P[85]) * bar
                                    continue
                    # broker stop (a trade on the tight $ trail: the minute's whole adverse range counts - MT5 trails tick by tick and a bounce stops it)
                    if ps[x, USD] > 0.5 and s_ != 0 and q > 0 and ((l1[j] <= s_) if sd > 0 else (h1[j] + spr >= s_)) and not (bid <= s_ if sd > 0 else ask >= s_):
                        nt, pn = _close(out, nt, ps, x, s_ - sd * X[9] - sd * X[8], tq, k, 6, 1.0)
                        equity += pn; dayPnl += pn
                        if pn < 0:
                            coolUntil = tq + int(P[85]) * bar
                        continue
                    if s_ != 0 and (bid <= s_ if sd > 0 else ask >= s_):
                        xp = (s_ if (prv > s_ if sd > 0 else prv + spr < s_) else (bid if sd > 0 else ask)) - sd * X[9] - sd * X[8]
                        why = 1
                        if ps[x, USD] > 0.5 or ps[x, RIDE] > 0.5:
                            why = 6
                        if abs(s_ - en) < 0.005:
                            why = 7
                        elif (s_ - en) * sd > 0:
                            why = 6
                        nt, pn = _close(out, nt, ps, x, xp, tq, k, why, 1.0)
                        equity += pn; dayPnl += pn
                        if pn < 0:
                            coolUntil = tq + int(P[85]) * bar
                        continue
                    # broker take profit
                    btp = ps[x, BTP]
                    if btp > 0 and (bid >= btp if sd > 0 else ask <= btp):
                        xp = (btp if (prv < btp if sd > 0 else prv + spr > btp) else (bid if sd > 0 else ask)) - sd * X[8]
                        nt, pn = _close(out, nt, ps, x, xp, tq, k, 5, 1.0)
                        equity += pn; dayPnl += pn
                        continue
                    if sd > 0:
                        ps[x, BEST + 0] = ps[x, BEST]
                    if ps[x, ET] >= t1[j]:
                        continue                                     # entered in this minute: targets wait for the next ticks
                    nx = int(ps[x, NX])
                    if nx != 0:
                        if E[E_ON] > 0.5:
                            # ---- Exit Lab, tick by tick: partial closes, the lab's target, breakeven, profit lock, tick trails
                            r0 = ps[x, R0]
                            fav = (bid - en) if sd > 0 else (en - ask)
                            best = (ps[x, MFP] - en) if sd > 0 else (en - ps[x, MFP])
                            gone = False
                            for pp in range(2):
                                pr = E[E_P1R] if pp == 0 else E[E_P2R]
                                fl = P1D if pp == 0 else P2D
                                if pr > 0 and ps[x, fl] < 0.5 and r0 > 0 and fav >= pr * r0:
                                    lv = en + sd * pr * r0
                                    if sd > 0:
                                        xp = lv if prv < lv else bid
                                    else:
                                        xp = lv if prv + spr > lv else ask
                                    want = ps[x, ORL] * (E[E_P1F] if pp == 0 else E[E_P2F])
                                    cl = np.floor(want / 0.01 + 0.5) * 0.01
                                    ps[x, fl] = 1.0
                                    if cl >= 0.01:
                                        fr = 1.0 if cl >= ps[x, LOTS] - 0.005 else cl / ps[x, LOTS]
                                        nt, pn = _close(out, nt, ps, x, xp - sd * X[8], tq, k, 11 if fr < 0.999 else 9, fr)
                                        equity += pn; dayPnl += pn
                                        if fr >= 0.999:
                                            if pn < 0:
                                                coolUntil = tq + int(P[85]) * bar
                                            gone = True
                                            break
                                        if pp == 0 and E[E_P1BE] > 0.5 and ((en > s_ + 0.005 and en < bid) if sd > 0 else ((s_ == 0 or en < s_ - 0.005) and en > ask)):
                                            ps[x, SL] = en; s_ = en
                            if gone:
                                continue
                            lt = ps[x, LTP]
                            if lt > 0 and ((bid >= lt) if sd > 0 else (ask <= lt)):
                                if sd > 0:
                                    xp = lt if prv < lt else bid
                                else:
                                    xp = lt if prv + spr > lt else ask
                                nt, pn = _close(out, nt, ps, x, xp - sd * X[8], tq, k, 9, 1.0)
                                equity += pn; dayPnl += pn
                                if pn < 0:
                                    coolUntil = tq + int(P[85]) * bar
                                continue
                            if r0 > 0:
                                want = 0.0
                                if E[E_BER] > 0 and best >= E[E_BER] * r0:
                                    want = en + sd * E[E_BEO] * r0
                                if E[E_LOCK] > 0:
                                    nst = np.floor(best / (E[E_LOCK] * r0))
                                    if nst >= 1:
                                        lk = en + sd * (nst - 1) * E[E_LOCK] * r0
                                        if want == 0.0 or (lk > want if sd > 0 else lk < want):
                                            want = lk
                                if want > 0 and ((want > s_ + 0.005 and want < bid) if sd > 0 else ((s_ == 0 or want < s_ - 0.005) and want > ask)):
                                    ps[x, SL] = want; s_ = want
                                tm = int(E[E_TR])
                                if tm >= 1 and tm <= 3 and best > 0 and best >= E[E_TRA] * r0:
                                    lvl = 0.0
                                    if tm == 1:
                                        lvl = ps[x, MFP] - sd * E[E_TRK]
                                    elif tm == 2 and k >= 1:
                                        lvl = ps[x, MFP] - sd * E[E_TRK] * atr[k - 1]
                                    elif tm == 3:
                                        lvl = en + sd * best * E[E_TRK] / 100.0
                                    if lvl > 0 and ((lvl > s_ + 0.005 and lvl < bid) if sd > 0 else ((s_ == 0 or lvl < s_ - 0.005) and lvl > ask)):
                                        ps[x, SL] = lvl; s_ = lvl
                                        if E[E_PESS] > 0.5:
                                            ps[x, USD] = 1.0        # MT5 trails tick by tick: the minute's adverse range counts (as the tight $ trail)
                        # v1.25+ exit modes: the next EMA beyond the entry
                        if nx > 0 and k >= 1 and not (E[E_ON] > 0.5 and E[E_TGT] > 0.5):
                            a_ = af if nx == 9 else asl
                            ep = ef[k - 1] if nx == 9 else es[k - 1]
                            hit = False
                            xp = 0.0
                            if sd > 0:
                                if bid >= ep + X[12] and (X[1] < 0.5 or ep > en):
                                    hit = True
                                    xp = ep if prv < ep else bid
                            else:
                                thr = ep - spr / (1.0 - a_)
                                if bid <= thr - X[12]:
                                    hit = True
                                    xp = (thr if prv > thr else bid) + spr
                            if hit:
                                if lat > 0:
                                    p_ = _pt(o1, h1, l1, c1, j, q + lat)
                                    xp = p_ if sd > 0 else p_ + spr
                                nt, pn = _close(out, nt, ps, x, xp - sd * X[8], tq, k, 2, 1.0)
                                equity += pn; dayPnl += pn
                                if pn < 0:
                                    coolUntil = tq + int(P[85]) * bar
                        continue
                    # ---- exit mode 0: v1.23's exits
                    moved = bid - en if sd > 0 else en - ask
                    if P[81] > 0:
                        want = en + sd * P[82]
                        if moved >= P[81] and ((want > s_ + 0.01) if sd > 0 else (s_ == 0 or want < s_ - 0.01)) and ((want < bid) if sd > 0 else (want > ask)):
                            ps[x, SL] = want; s_ = want
                    if P[84] > 0 and tq - ps[x, ET] >= P[84] * bar:
                        nt, pn = _close(out, nt, ps, x, (bid if sd > 0 else ask) - sd * X[8], tq, k, 8, 1.0)
                        equity += pn; dayPnl += pn
                        if pn < 0:
                            coolUntil = tq + int(P[85]) * bar
                        continue
                    exe = int(ps[x, EXE])
                    a_e = af if exe == 9 else asl
                    ep_e = (ef[k - 1] if exe == 9 else es[k - 1]) if k >= 1 else 0.0
                    live_e = ep_e + a_e * (bid - ep_e)
                    if P[59] > 0 and ps[x, RIDE] < 0.5:
                        if sd < 0 or P[83] > 0:
                            tpRef = ps[x, TP]
                        elif ps[x, NOTP] > 0.5:
                            tpRef = 0.0
                        elif ps[x, RES1] > 0.5:
                            tpRef = ps[x, TP]
                        else:
                            tpRef = live_e - P[43] * pip
                        dist = tpRef - en if sd > 0 else en - tpRef
                        atEntry = s_ >= en if sd > 0 else (s_ > 0 and s_ <= en)
                        if tpRef > 0 and dist > 0 and not atEntry and moved >= P[59] * dist and ((en < bid) if sd > 0 else (en > ask)):
                            ps[x, SL] = en; s_ = en
                    if P[83] > 0:
                        continue
                    if ps[x, USD] > 0.5:
                        dist = (P[52] if sd > 0 else P[58]) + P[57] * max(0.0, ps[x, STG] - 2)
                        want = round((bid - dist) if sd > 0 else (ask + dist), 2)
                        if (want >= s_ + 0.10) if sd > 0 else (s_ == 0 or want <= s_ - 0.10):
                            ps[x, SL] = want
                        tn = ps[x, TPN]
                        if tn > 0 and (bid >= tn if sd > 0 else bid <= tn):
                            ps[x, STG] += 1
                            if sd > 0:
                                ps[x, TPN] = _resist(h15, k, tn + P[47] * pip, int(P[44]), int(P[45]))
                            else:
                                ps[x, TPN] = _support(l15, k, tn - P[47] * pip, int(P[44]), int(P[45]))
                        continue
                    touched = False
                    tlev = 0.0
                    if P[51] == 1 and sd > 0 and (ps[x, RIDE] < 0.5 or ps[x, RES1] > 0.5) and ps[x, NOTP] < 0.5:
                        tgt = ps[x, TP] if ps[x, RES1] > 0.5 else live_e - P[43] * pip
                        if tgt > en and bid >= tgt:
                            touched = True
                            tlev = tgt
                    if not touched and sd < 0 and ps[x, RIDE] < 0.5 and ps[x, TP] > 0 and P[56] == 1 and bid <= ps[x, TP]:
                        touched = True
                        tlev = ps[x, TP]
                    if touched:
                        # TP1 is hit where the price CROSSED the target (not at the minute's extreme)
                        if (prv < tlev) if sd > 0 else (prv > tlev):
                            bid = tlev
                            ask = tlev + spr
                        # TP1 touch: partial close, $ trail from the market, breakeven, aim for the next liquidity
                        pct = P[98]
                        if pct > 0:
                            vol = ps[x, LOTS]
                            part = np.floor(vol * pct / 0.01 + 1e-9) * 0.01
                            if part >= 0.01 and vol - part >= 0.01 - 1e-9:
                                nt, pn = _close(out, nt, ps, x, bid if sd > 0 else ask, tq, k, 5, part / vol)
                                equity += pn; dayPnl += pn
                        ps[x, RIDE] = 1; ps[x, USD] = 1
                        if sd > 0:
                            sl2 = round(max(s_, bid - P[52]), 2)
                            if P[99] > 0.5 and en < bid:
                                sl2 = max(sl2, en)
                            if sl2 >= bid:
                                sl2 = s_
                            ps[x, SL] = sl2
                            ps[x, TPN] = _resist(h15, k, bid + P[47] * pip, int(P[44]), int(P[45])) if P[53] > 0.5 else 0.0
                        else:
                            sl2 = round(min(s_, ask + P[58]) if s_ > 0 else ask + P[58], 2)
                            if P[99] > 0.5 and en > ask:
                                sl2 = min(sl2, en)
                            if sl2 <= ask:
                                sl2 = s_
                            ps[x, SL] = sl2
                            ps[x, TPN] = _support(l15, k, bid - P[47] * pip, int(P[44]), int(P[45]))
                        ps[x, STG] = 2
                        continue
                    if ps[x, RIDE] > 0.5:
                        continue
                    tp_hit = False
                    tpLv = 0.0
                    if sd < 0:
                        if ps[x, TP] > 0 and _trail_on(P, -1) and P[62] > 0.5 and bid <= ps[x, TP]:
                            tp_hit = True; tpLv = ps[x, TP]
                    elif ps[x, NOTP] < 0.5 and P[42] == 0:
                        tgt = live_e - P[43] * pip
                        if tgt > en and bid >= tgt:
                            tp_hit = True; tpLv = tgt
                    if tp_hit:
                        if _trail_on(P, sd) and P[62] > 0.5:
                            ps[x, RIDE] = 1
                            if P[68] != 2:
                                lock = (tpLv - sd * P[69] * pip) if P[68] == 0 else en
                                better = lock > s_ if sd > 0 else (s_ == 0 or lock < s_)
                                if better and ((lock < bid) if sd > 0 else (lock > ask)):
                                    ps[x, SL] = lock
                        else:
                            nt, pn = _close(out, nt, ps, x, (bid if sd > 0 else ask) - sd * X[8], tq, k, 5, 1.0)
                            equity += pn; dayPnl += pn
                # ghost (stand aside)
                if gh != 0 and not (blind and gK == k):
                    end = (cur <= gSl) if gh > 0 else (cur + spr >= gSl)
                    if not end and gNx > 0 and k >= 1:
                        a_ = af if gNx == 9 else asl
                        ep = ef[k - 1] if gNx == 9 else es[k - 1]
                        end = (cur >= ep and (X[1] < 0.5 or ep > gEn)) if gh > 0 else (cur <= ep - spr / (1.0 - a_))
                    if not end and gNx == 0 and k >= 1:
                        if gh > 0 and not gNoTp:
                            a_ = af if gExitE == 9 else asl
                            ep = ef[k - 1] if gExitE == 9 else es[k - 1]
                            tg = ep + a_ * (cur - ep) - P[43] * pip
                            end = tg > gEn and cur >= tg
                        if gh < 0 and gTp > 0:
                            end = cur <= gTp
                    if end:
                        if nt < out.shape[0]:
                            out[nt, 0] = gh; out[nt, 1] = gT; out[nt, 2] = gEn; out[nt, 3] = gSl; out[nt, 4] = tq; out[nt, 5] = cur if gh > 0 else cur + spr
                            out[nt, 6] = ((cur if gh > 0 else cur + spr) - gEn) * gh * P[37] * 100; out[nt, 10] = 1; out[nt, 8] = gB; out[nt, 9] = gNx
                            out[nt, 11] = gK; out[nt, 12] = k; out[nt, 13] = 1
                            nt += 1
                        gh = 0
                # 3. the new 15-min candle
                if rep == 0 and q == 0 and first1[j] == 1 and k >= 1:
                    i = k - 1
                    for x in range(MAXP):
                        sd = ps[x, SD]
                        if sd == 0:
                            continue
                        nx = int(ps[x, NX])
                        en = ps[x, EN]
                        s_ = ps[x, SL]
                        if nx != 0:
                            if E[E_ON] < 0.5:
                                if nx < 0 and ps[x, EK] < i:
                                    e_ce = ef[i] if nx == -1 else es[i]
                                    if (c15[i] < e_ce) if sd > 0 else (c15[i] > e_ce):
                                        p_ = _pt(o1, h1, l1, c1, j, lat) if lat > 0 else cur
                                        nt, pn = _close(out, nt, ps, x, (p_ if sd > 0 else p_ + spr) - sd * X[8], tq, k, 3, 1.0)
                                        equity += pn; dayPnl += pn
                                        if pn < 0:
                                            coolUntil = tq + int(P[85]) * bar
                                continue
                            # ---- Exit Lab at the candle close (never on the entry candle's own close, like the EA's close-back)
                            if ps[x, EK] >= i:
                                continue
                            r0 = ps[x, R0]
                            best = (ps[x, MFP] - en) if sd > 0 else (en - ps[x, MFP])
                            why = 0
                            if nx == -2:                                       # exit mode 2: a close back across the slow EMA
                                if (c15[i] < es[i]) if sd > 0 else (c15[i] > es[i]):
                                    why = 3
                            elif nx == -1 and E[E_TGT] < 0.5 and E[E_FB] < 1.5:   # no EMA beyond the entry: the fallback, with the lab's buffer / closes
                                e_ce = ef[i] if E[E_FB] < 0.5 else es[i]
                                fb_ = E[E_FBB] * atr[i]
                                beyond = (c15[i] < e_ce - fb_) if sd > 0 else (c15[i] > e_ce + fb_)
                                ps[x, FBN] = ps[x, FBN] + 1.0 if beyond else 0.0
                                if ps[x, FBN] >= max(1.0, E[E_FBN]):
                                    why = 3
                            if why == 0 and E[E_CX] > 0.5 and i > ps[x, EK] + E[E_CXA]:
                                cm = int(E[E_CX])
                                cb = E[E_CXB] * atr[i]
                                hitc = False
                                if cm == 1 or cm == 2:
                                    e_c = ef[i] if cm == 1 else es[i]
                                    hitc = (c15[i] < e_c - cb) if sd > 0 else (c15[i] > e_c + cb)
                                elif cm == 3:
                                    hitc = (ef[i] < es[i] - cb) if sd > 0 else (ef[i] > es[i] + cb)
                                elif cm == 4:
                                    shp, kd = _shape(o15[i], h15[i], l15[i], c15[i], atr[i], P)
                                    hitc = (shp == -1 or (shp == 2 and c15[i] < o15[i])) if sd > 0 else (shp == 1 or (shp == 2 and c15[i] > o15[i]))
                                elif cm == 5 and i >= 1:
                                    if sd > 0:
                                        hitc = c15[i] < o15[i] and c15[i - 1] > o15[i - 1] and o15[i] >= c15[i - 1] and c15[i] <= o15[i - 1]
                                    else:
                                        hitc = c15[i] > o15[i] and c15[i - 1] < o15[i - 1] and o15[i] <= c15[i - 1] and c15[i] >= o15[i - 1]
                                elif cm == 6:
                                    hitc = (c15[i] < o15[i]) if sd > 0 else (c15[i] > o15[i])
                                ps[x, CXN] = ps[x, CXN] + 1.0 if hitc else 0.0
                                if ps[x, CXN] >= max(1.0, E[E_CXN]):
                                    pnow = (cur - en) if sd > 0 else (en - cur - spr)
                                    wh = int(E[E_CXW])
                                    if wh == 0 or (wh == 1 and pnow > 0) or (wh == 2 and pnow <= 0):
                                        why = 12
                            tm = int(E[E_TR])
                            if why == 0 and tm >= 4 and r0 > 0 and best >= E[E_TRA] * r0 and (E[E_TRA] <= 0 or best > 0):
                                tb = E[E_TRB]
                                lvl = 0.0
                                if tm == 4:
                                    lvl = ef[i] - sd * tb
                                elif tm == 5:
                                    lvl = es[i] - sd * tb
                                elif tm == 6:
                                    lvl = (l15[i] - tb) if sd > 0 else (h15[i] + tb)
                                elif tm == 7:
                                    nb = max(1, int(E[E_TRK]))
                                    lv2 = 1e18 if sd > 0 else -1e18
                                    for s in range(nb):
                                        if i - s >= 0:
                                            lv2 = min(lv2, l15[i - s]) if sd > 0 else max(lv2, h15[i - s])
                                    lvl = (lv2 - tb) if sd > 0 else (lv2 + tb)
                                elif tm == 8:
                                    sw = _support(l15, k, cur, 2, 60) if sd > 0 else _resist(h15, k, cur + spr, 2, 60)
                                    if sw > 0:
                                        lvl = sw - sd * tb
                                if lvl > 0 and ((lvl > s_ + 0.005) if sd > 0 else (s_ == 0 or lvl < s_ - 0.005)):
                                    if (lvl < cur) if sd > 0 else (lvl > cur + spr):
                                        ps[x, SL] = lvl; s_ = lvl
                                    else:
                                        why = 6                                # the close is already beyond the trail
                            held = i - ps[x, EK]
                            if why == 0 and E[E_MAXB] > 0 and held >= E[E_MAXB]:
                                why = 8
                            if why == 0 and E[E_STB] > 0 and held >= E[E_STB] and r0 > 0 and (c15[i] - en) * sd < E[E_STR] * r0:
                                why = 13
                            if why == 0 and E[E_DCB] > 0 and held >= E[E_DCB] and r0 > 0:   # v1.31 decay stop: after N candles, the stop to entry + dc_r R
                                lvl = en + sd * E[E_DCR] * r0
                                if (lvl > s_ + 0.005) if sd > 0 else (s_ == 0 or lvl < s_ - 0.005):
                                    if (lvl < cur) if sd > 0 else (lvl > cur + spr):
                                        ps[x, SL] = lvl; s_ = lvl
                                    else:
                                        why = 16                               # the price is already beyond it: out now
                            if why == 0 and E[E_ADX] > 0 and adx[i] < E[E_ADX]:
                                why = 14
                            if why == 0 and E[E_FRI] > 0 and dow15[k] == 5 and hr15[k] >= E[E_FRI]:
                                why = 15
                            if why != 0:
                                p_ = _pt(o1, h1, l1, c1, j, lat) if lat > 0 else cur
                                nt, pn = _close(out, nt, ps, x, (p_ if sd > 0 else p_ + spr) - sd * X[8], tq, k, why, 1.0)
                                equity += pn; dayPnl += pn
                                if pn < 0:
                                    coolUntil = tq + int(P[85]) * bar
                            continue
                        if ps[x, USD] > 0.5:
                            continue
                        exe = int(ps[x, EXE])
                        e_x = ef[i] if exe == 9 else es[i]
                        if sd > 0 and ps[x, RIDE] < 0.5 and P[83] <= 0 and P[51] == 0:
                            tgt = e_x - P[43] * pip
                            if ps[x, NOTP] < 0.5 and P[42] == 1 and tgt > en and c15[i] >= tgt:
                                if _trail_on(P, 1) and P[62] > 0.5:
                                    ps[x, RIDE] = 1
                                    if P[68] != 2:
                                        lock = (tgt - P[69] * pip) if P[68] == 0 else en
                                        if lock > s_ and lock < cur:
                                            ps[x, SL] = lock; s_ = lock
                                else:
                                    nt, pn = _close(out, nt, ps, x, cur - X[8], tq, k, 5, 1.0)
                                    equity += pn; dayPnl += pn
                                    continue
                            if ps[x, NOTP] > 0.5 and not _trail_on(P, 1) and c15[i] < e_x:
                                nt, pn = _close(out, nt, ps, x, cur - X[8], tq, k, 3, 1.0)
                                equity += pn; dayPnl += pn
                                if pn < 0:
                                    coolUntil = tq + int(P[85]) * bar
                                continue
                        after = ps[x, EK] < i
                        if _trail_on(P, sd) and after:
                            ps[x, BEST] = max(ps[x, BEST], h15[i]) if sd > 0 else min(ps[x, BEST], l15[i])
                            if P[62] > 0.5:
                                started = ps[x, RIDE] > 0.5
                            else:
                                started = ((ps[x, BEST] - en) if sd > 0 else (en - ps[x, BEST])) >= P[67] * pip
                            if started:
                                if P[63] == 0:
                                    lvl = 1e18 if sd > 0 else 0.0
                                    for kk in range(1, int(P[64]) + 1):
                                        if k - kk >= 0:
                                            lvl = min(lvl, l15[k - kk]) if sd > 0 else max(lvl, h15[k - kk])
                                elif P[63] == 1:
                                    lvl = ps[x, BEST] - sd * P[65] * pip
                                else:
                                    lvl = ps[x, BEST] - sd * P[66] * atr[i]
                                better = (lvl > s_ + 0.01 and lvl < c15[i]) if sd > 0 else ((s_ == 0 or lvl < s_ - 0.01) and lvl > c15[i])
                                if better and ((lvl < cur) if sd > 0 else (lvl > cur + spr)):
                                    ps[x, SL] = lvl; s_ = lvl
                        if P[49] > 0 and after:
                            best = (h15[i] - en) if sd > 0 else (en - l15[i])
                            done = s_ >= en if sd > 0 else (s_ > 0 and s_ <= en)
                            if not done and best > P[49] and ((en < cur) if sd > 0 else (en > cur + spr)):
                                ps[x, SL] = en
                    # ghost close-back
                    if gh != 0 and gK < i:
                        ce = 9 if gNx == -1 else (50 if gNx == -2 else 0)
                        if ce == 0 and gNx == 0 and gh > 0 and gNoTp:
                            ce = 9 if gExitE == 9 else 50       # v1.29 (EA GhostBar): like the trade, a close below its exit EMA; before, it could last forever
                        if ce > 0:
                            e_ce = ef[i] if ce == 9 else es[i]
                            if (c15[i] < e_ce) if gh > 0 else (c15[i] > e_ce):
                                gh = 0
                    # countdowns
                    gap = P[40] > 0.5 and t15[k] - t15[i] > 1.5 * bar
                    if aSide != 0:
                        if gap:
                            aSide = 0
                        else:
                            aLeft -= 1
                            if aLeft <= 0:
                                aSide = 0
                    if pSide != 0:
                        if gap:
                            pSide = 0
                            stats[6] += 1
                        else:
                            pLeft -= 1
                            if pLeft <= 0:
                                pSide = 0
                                stats[1] += 1
                    # DetectSetup on candle i
                    ok = True
                    if P[50] > 0 and mins_close <= P[50]:
                        ok = False
                    if ok and tq < coolUntil:
                        ok = False
                    shape, kind = 0, 0
                    if ok:
                        if OS[i] != 9:                                # Strategy Lego: another setup-candle piece (1 BUY, -1 SELL, 2 either, 0 none)
                            shape = OS[i]; kind = 4 if OS[i] != 0 else 0
                        else:
                            shape, kind = _shape(o15[i], h15[i], l15[i], c15[i], atr[i], P)
                    hr = hr15[i]
                    if shape != 0 and hr >= P[27] and hr < P[28] and i >= X[5] and not (P[80] >= 0 and dow15[i] == P[80]):
                        e9 = ef[i]
                        e50 = es[i]
                        if P[F_BOTH] > 0.5 and min(e9, e50) >= l15[i] - P[18] * 0.1 and max(e9, e50) <= h15[i] + P[18] * 0.1:
                            shape = 0                                     # v1.28 InpSkipBothEma: the candle touches both EMAs
                        on9 = _online(o15[i], h15[i], l15[i], c15[i], e9, 1, P)
                        on50 = _online(o15[i], h15[i], l15[i], c15[i], e50, 1, P)
                        rulesOk = P[15] != 1 and on9 and not (P[19] > 0.5 and e50 <= h15[i])
                        invOk = P[15] != 0 and on50 and not (P[19] > 0.5 and e9 <= h15[i])
                        if P[16] == 0:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e50, -1, P)
                        elif P[16] == 1:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e9, -1, P)
                        else:
                            shortLine = _online(o15[i], h15[i], l15[i], c15[i], e50, -1, P) or _online(o15[i], h15[i], l15[i], c15[i], e9, -1, P)
                        if OL[i] != 9:                                # Strategy Lego: another location piece (bit 1 BUY allowed, bit 2 SELL allowed)
                            rulesOk = (OL[i] & 1) != 0; invOk = False; shortLine = (OL[i] & 2) != 0
                        longOk = P[38] > 0.5 and (rulesOk or invOk) and (shape == 1 or (shape == 2 and ((not shortLine) or c15[i] >= o15[i])))
                        shortOk = P[39] > 0.5 and shortLine and (shape == -1 or shape == 2) and not longOk
                        if longOk or shortOk:
                            side = 1 if longOk else -1
                            good = True
                            el = int(P[71])
                            if P[70] > 0 and i - el >= 0:
                                net = abs(c15[i] - c15[i - el])
                                path = 0.0
                                for s in range(el):
                                    path += abs(c15[i - s] - c15[i - s - 1])
                                if path <= 0 or net / path < P[70]:
                                    good = False
                            if good and P[72] > 0:
                                hc, h1_, h2_ = htfc[i], htfe1[i], htfe2[i]
                                hok = (hc > h1_ and h1_ > h2_) if side > 0 else (hc < h1_ and h1_ < h2_)
                                if h1_ <= 0 or h2_ <= 0 or not hok:
                                    good = False
                            if good:
                                if P[74] > 0.5 and ((e9 <= e50) if side > 0 else (e9 >= e50)):
                                    good = False
                                if P[75] > 0.5 and ((c15[i] <= e50) if side > 0 else (c15[i] >= e50)):
                                    good = False
                                sl_ = int(P[77])
                                if P[76] > 0 and i - sl_ >= 0 and (es[i] - es[i - sl_]) * side < P[76] * pip:
                                    good = False
                                if P[78] > 0 and abs(e9 - e50) < P[78] * pip:
                                    good = False
                            if good and ((P[89] > 0 and dayPnl <= -P[89]) or (P[90] > 0 and dayPnl >= P[90])):
                                good = False
                            if good and P[103] > 0 and equity + flt <= dayStart * (1 - P[103] / 100.0):
                                good = False
                            npos = 0
                            first_side = 0
                            for x in range(MAXP):
                                if ps[x, SD] != 0:
                                    npos += 1
                                    if first_side == 0:
                                        first_side = int(ps[x, SD])
                            if good and (npos >= P[86] or gh != 0 or ((pSide != 0 or aSide != 0) and P[87] < 0.5) or (X[0] > 0.5 and busy0)):
                                good = False
                            if good and npos > 0 and P[88] != 0:
                                same = first_side == side
                                if (P[88] == 1 and not same) or (P[88] == 2 and same):
                                    good = False
                            if good:
                                pSide = side; pHigh = h15[i]; pLow = l15[i]
                                pLeft = int(P[95]) if P[91] == 2 else int(P[20])
                                pK = i; swept = False; aSide = 0
                                pExit = (PEXIT_SLOW if rulesOk else 9) if side > 0 else 0
                                if ns < setups.shape[0]:
                                    setups[ns, 0] = i; setups[ns, 1] = pSide; setups[ns, 2] = kind
                                ns += 1
                                stats[0] += 1
                # 4. entries: TryEntry, TryDip
                npos = 0
                for x in range(MAXP):
                    if ps[x, SD] != 0:
                        npos += 1
                if rep == 0 and closed and pSide != 0 and q == 0:
                    pass
                if rep == 0 and (pSide != 0 or aSide != 0) and npos < P[86] and gh == 0 and k > pK:
                    bid = cur
                    ask = cur + spr
                    side = 0
                    sl_e = 0.0
                    off = False
                    bk = -1
                    be = bid
                    hiP = pHigh
                    loP = pLow
                    go = False
                    if pSide != 0 and P[50] > 0 and mins_close <= P[50]:
                        pSide = 0
                    if pSide != 0 and P[91] == 2:
                        far = pLow - P[94] * pip if pSide > 0 else pHigh + P[94] * pip
                        if not swept and ((bid < far) if pSide > 0 else (ask > far)):
                            swept = True; sweepExt = bid if pSide > 0 else ask
                        if swept:
                            sweepExt = min(sweepExt, bid) if pSide > 0 else max(sweepExt, ask)
                            if P[96] == 0:
                                trig = (bid > pLow) if pSide > 0 else (ask < pHigh)
                            else:
                                trig = (bid > pHigh + P[21] * pip) if pSide > 0 else (bid < pLow - P[21] * pip)
                            if trig and not (P[79] > 0 and spr / 0.01 > P[79]):
                                side = pSide
                                pSide = 0; swept = False
                                sl_e = sweepExt - P[97] * pip if side > 0 else sweepExt + P[97] * pip
                                go = True
                    elif pSide != 0:
                        lvl = pHigh + P[21] * pip if pSide > 0 else pLow - P[21] * pip
                        trigp = (cur if P[41] > 0.5 else cur + spr) if pSide > 0 else cur
                        prvp = (prv if P[41] > 0.5 else prv + spr) if pSide > 0 else prv
                        crossed = trigp > lvl if pSide > 0 else trigp < lvl
                        if crossed and not (P[79] > 0 and spr / 0.01 > P[79]):
                            if pSide > 0:
                                be = (lvl + 0.01 if prvp <= lvl else trigp) - (0.0 if P[41] > 0.5 else spr)
                            else:
                                be = lvl - 0.01 if prvp >= lvl else cur
                            side = pSide
                            pSide = 0
                            if P[91] == 1:
                                aSide = side; aHigh = pHigh; aLow = pLow; aExit = pExit; aLeft = int(P[93])
                                aLevel = pHigh - P[92] * (pHigh - pLow) if side > 0 else pLow + P[92] * (pHigh - pLow)
                                side = 0
                            else:
                                look = int(P[32]) if side > 0 else int(P[33])
                                hi = -1e18
                                lo = 1e18
                                for s in range(1, look + 1):
                                    if k - s >= 0:
                                        hi = max(hi, h15[k - s])
                                        lo = min(lo, l15[k - s])
                                px = max(lvl + 0.01, o15[k]) if side > 0 else min(lvl - 0.01, o15[k])
                                chase = 50.0
                                if hi > lo:
                                    chase = ((px - lo) / (hi - lo) if side > 0 else (hi - px) / (hi - lo)) * 100.0
                                bk = 20 if chase > 100 else (0 if chase <= 0 else min(int(np.floor(chase / 5.0)), 19))
                                off = (bandB[bk] == 0) if side > 0 else (bandS[bk] == 0)
                                if off and P[34] < 0.5:
                                    stats[5] += 1
                                    side = 0
                                elif X[13] > 0 and spr > X[13] * X[14]:
                                    stats[7] += 1
                                    side = 0
                                else:
                                    go = True
                    elif aSide != 0:
                        if (ask <= aLevel) if aSide > 0 else (bid >= aLevel):
                            side = aSide
                            hiP = aHigh; loP = aLow; pExit = aExit
                            aSide = 0
                            go = True
                            be = bid
                    if go and side != 0 and closed:
                        go = False                                   # refused at the open: the setup is gone (TryEntry cleared it)
                    if go and side != 0:
                        ts_ = -side if X[6] > 0.5 else side
                        if lat > 0:
                            be = _pt(o1, h1, l1, c1, j, q + lat)
                        e_ = (be + spr if ts_ > 0 else be) + ts_ * X[7]
                        a_ = atr[k - 1]
                        if P[91] == 2 and sl_e != 0.0 and X[6] < 0.5:
                            s_ = sl_e
                        elif P[22] == 1:
                            s_ = e_ - P[24] * a_ if ts_ > 0 else e_ + P[24] * a_
                        elif P[22] == 2:
                            s_ = e_ - P[25] if ts_ > 0 else e_ + P[25]
                        else:
                            s_ = loP - P[23] * pip if ts_ > 0 else hiP + P[23] * pip
                        dip_bad = P[91] == 1 and ((be <= s_) if ts_ > 0 else (be + spr >= s_))
                        if dip_bad:
                            pass
                        elif P[26] > 0 and abs(e_ - s_) > P[26]:
                            stats[2] += 1
                        elif P[29] > 0 and adx[k - 1] < P[29]:
                            stats[3] += 1
                        elif (P[30] > 0 and a_ < P[30]) or (P[31] > 0 and a_ > P[31]):
                            stats[4] += 1
                        else:
                            n_ = 0
                            tp_ = 0.0
                            noTp = False
                            res1 = False
                            skip = False
                            if P[35] == 1:
                                l9 = ef[k - 1] + af * (be - ef[k - 1])
                                l50 = es[k - 1] + asl * (be - es[k - 1])
                                b9 = l9 > e_ if ts_ > 0 else l9 < e_
                                b50 = l50 > e_ if ts_ > 0 else l50 < e_
                                if b9 and b50:
                                    n_ = 9 if abs(l9 - e_) <= abs(l50 - e_) else 50
                                elif b9:
                                    n_ = 9
                                elif b50:
                                    n_ = 50
                                else:
                                    n_ = -1
                            elif P[35] == 2:
                                n_ = -2
                            elif ts_ < 0:
                                sup = _support(l15, k, be - P[47] * pip, int(P[44]), int(P[45]))
                                if sup <= 0:
                                    skip = True
                                else:
                                    tp_ = sup + P[46] * pip
                                    if P[48] > 0 and be - tp_ > P[48] * pip:
                                        skip = True
                            else:
                                ex9 = pExit == 9
                                a_x = af if ex9 else asl
                                ep_x = ef[k - 1] if ex9 else es[k - 1]
                                livex = ep_x + a_x * (be - ep_x)
                                noTp = livex - P[43] * pip < e_ + P[47] * pip
                                if noTp and P[54] > 0.5 and P[51] == 1:
                                    res = _resist(h15, k, e_ + P[47] * pip, int(P[44]), int(P[45]))
                                    if res > 0:
                                        tp_ = res; noTp = False; res1 = True
                            if not skip:
                                if E[E_ON] > 0.5 and E[E_LCAP] > 0 and n_ != 0 and abs(e_ - s_) > E[E_LCAP]:
                                    s_ = e_ - ts_ * E[E_LCAP]                   # v1.31: the stop never further than $X from the entry
                                rideShort = ts_ < 0 and _trail_on(P, -1) and P[62] > 0.5 and P[83] <= 0
                                if P[83] > 0:
                                    tp_ = e_ + ts_ * P[83] * pip
                                    noTp = False
                                if off:
                                    gh = ts_; gEn = e_; gSl = s_; gNx = n_; gK = k; gT = tq; gB = bk + (0 if side > 0 else 21)
                                    gExitE = pExit; gTp = tp_; gNoTp = noTp
                                else:
                                    lots = P[37]
                                    if P[100] > 0:
                                        perLot = abs(e_ - s_) * 100.0
                                        lots = 0.0
                                        if perLot > 0:
                                            lots = np.floor(equity * P[100] / 100.0 / perLot / 0.01) * 0.01
                                            if lots < 0.01:
                                                if P[101] > 0 and 0.01 * perLot > equity * P[101] / 100.0:
                                                    lots = 0.0
                                                else:
                                                    lots = 0.01
                                            lots = min(lots, P[102])
                                    if lots > 0:
                                        for x in range(MAXP):
                                            if ps[x, SD] == 0:
                                                ps[x, :] = 0.0
                                                ps[x, SD] = ts_; ps[x, EN] = e_; ps[x, SL] = s_; ps[x, TP] = tp_; ps[x, EXE] = pExit
                                                ps[x, NOTP] = 1.0 if noTp else 0.0; ps[x, RES1] = 1.0 if res1 else 0.0; ps[x, NX] = n_
                                                ps[x, EK] = k; ps[x, ET] = tq; ps[x, BEST] = e_; ps[x, LOTS] = lots; ps[x, BKT] = (bk + (0 if side > 0 else 21)) if bk >= 0 else -1
                                                ps[x, STG] = 1
                                                ps[x, R0] = abs(e_ - s_); ps[x, ATE] = a_; ps[x, MFP] = e_; ps[x, MAP] = e_; ps[x, ORL] = lots
                                                if E[E_ON] > 0.5 and E[E_TGT] > 1.5 and n_ != 0:
                                                    dist = E[E_TGTK] * abs(e_ - s_) if E[E_TGT] < 2.5 else (E[E_TGTK] * a_ if E[E_TGT] < 3.5 else E[E_TGTK])
                                                    ps[x, LTP] = e_ + ts_ * dist
                                                ride0 = ts_ > 0 and (noTp or (res1 and P[55] > 0.5)) and _trail_on(P, 1) and P[83] <= 0
                                                ps[x, RIDE] = 1.0 if (ride0 and n_ == 0) else 0.0
                                                if P[83] > 0:                        # InpFixTpPips: the order carries this broker TP in EVERY exit mode
                                                    ps[x, BTP] = tp_                 # (EA DoEntry: trade.Buy/Sell(..., tp)) - it was only set in mode 0
                                                elif n_ == 0 and ts_ < 0 and not rideShort:
                                                    ps[x, BTP] = tp_
                                                break
                            prv = be
                            continue
                break
    if stats.shape[0] >= 10:                                  # still open when the data ends: how many, and the oldest entry (Exit Lab warnings)
        for x in range(MAXP):
            if ps[x, SD] != 0:
                stats[8] += 1
                if stats[9] == 0 or ps[x, ET] < stats[9]:
                    stats[9] = ps[x, ET]
        if gh != 0:                                           # a stand-aside still running blocks every setup the same way
            stats[8] += 1
            if stats[9] == 0 or gT < stats[9]:
                stats[9] = gT
    return nt, ns
