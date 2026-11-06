"""diamond.py - Zee's UHV Diamond (his LAWS.md setup) read on the game's own 1-minute bars. A HINT for the street, never an order and
never a promise (Zee 2026-11-04: "use that to build game elements that support us in this game").

Ported rule for rule from mt5/DiamondEngineM1.mqh - the Diamond engine inside Trinity_1min, which judged volume on the broker's tick
volume, the same kind of volume PXTrader's bars carry - at its shipped defaults (pivot 3, trend look 20, retracement fix on, UHV body
>= 0.5, hump budget 3, cooldown 3 bars), plus Trinity's chop filter from report section 34: the 15-minute efficiency ratio over 16
candles. On gold that filter is what lifted the Diamond from ~76% to ~94% wins at ITS OWN geometry (a ~1 target against a ~5 stop);
on EUR/USD at the game's 2-pip / 2-pip geometry nothing is measured yet - only MT5 may say what it is worth here.

Index convention, as in MQL: k is a shift over CLOSED bars, k = 1 is the bar that just closed. Bars are [t, o, h, l, c, v].

  camel     the trend read from camel humps (higher highs that BREAK the last top + higher lows), the hump count on it, tired at 3
  rough     a retracement in that trend has its UHV (the loudest counter-coloured candle) - waiting for the breakout
  cut       the breakout candle just closed beyond the UHV's extreme on lower volume: the Diamond fires
  royal     ...and the 15-minute market is moving cleanly (ER >= 0.45), the section-34 condition
"""

PIVOT = 3
TREND_LOOK = 20
RETRACE_BACK = 20
UHV_BODY_MIN = 0.5
MAX_HUMPS = 3
COOLDOWN_BARS = 3
MAX_GAP_S = 300
ER_N = 16
ER_ROYAL = 0.45
CUT_LIFE_S = 40.0           # Zee 2026-11-04: "bright and shining and last only for 40 seconds beginning at a breakout" - then it vanishes
NEED = TREND_LOOK + PIVOT + 2
CAM_PIV = 1                 # Zee's camel hump size (Turtle Trader Desk camPiv: 1 = every swing counts)
CAM_CONFIRM = 1             # humps in a row of the new colour before the camel trend flips (1 = the latest hump decides, as the Pine)
CAM_STRONG = 0              # Zee 2026-11-05 (LAWS.md clause b): the breakout must ALWAYS be quieter than the UHV - the Pine strong-trend exception is off
MOMENTUM_BODY = 0.70        # Zee 2026-11-05 (LAWS.md clause a): the breakout is a momentum candle, |close - open| / (high - low) >= 0.70


def efficiency_ratio(closes, n=ER_N):
    """Kaufman efficiency ratio of the last n moves: net move / path walked (1 = a straight line, 0 = pure chop)."""
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1):]
    path = sum(abs(seg[i + 1] - seg[i]) for i in range(n))
    return abs(seg[-1] - seg[0]) / path if path > 0 else 0.0


def m15_closes(bars, forming_t):
    """Closes of the COMPLETED 15-minute candles (the bucket the forming bar sits in is not complete)."""
    out, cur = [], None
    for b in bars:
        g = int(b[0]) // 900
        if g >= int(forming_t) // 900:
            break
        if g != cur:
            out.append(b[4]); cur = g
        else:
            out[-1] = b[4]
    return out


class Diamond:
    def __init__(self, unit=1.0):
        self.unit = float(unit)            # one gold dollar in this symbol's price (the engine's 0.10 / 0.50 constants scale by it)
        self.reset()

    def reset(self):
        self.last_t = None
        self.first_t = None
        self.hump_dir = 0
        self.hump_n = 0
        self.hump_last = None
        self.last_fire_t = None
        # Zee's camel humps, ported from his Turtle Trader Desk indicator (pine, CAMEL-HUMP TREND block, 2026-10-08)
        self.cz = {"T": 0, "HB": None, "HV": None, "L0B": None, "L0V": None, "LB": None, "LV": None, "Tr": 0, "Stk": 0, "Stk0": 0, "Eff": 0}
        self.camel = {"dir": 0, "humps": 0, "guard": None}
        self.rough = None
        self.cut = None
        self.er = None

    # ------------------------------------------------------------------ accessors over closed bars (k = 1 the newest)
    def _set(self, bars, vols):
        self.B, self.V, self.n = bars, vols, len(bars)

    def t(self, k): return self.B[self.n - k][0]
    def o(self, k): return self.B[self.n - k][1]
    def h(self, k): return self.B[self.n - k][2]
    def l(self, k): return self.B[self.n - k][3]
    def c(self, k): return self.B[self.n - k][4]
    def v(self, k): return self.V[self.n - k]
    def colour(self, k):
        d = self.c(k) - self.o(k)
        return 1 if d > 0 else (-1 if d < 0 else 0)
    def body_hi(self, k): return max(self.o(k), self.c(k))
    def body_lo(self, k): return min(self.o(k), self.c(k))

    # ------------------------------------------------------------------ 0. the regime: camel humps (D_CamelTrendD, HighTest 1)
    def camel_trend(self):
        p = PIVOT
        hs, hidx, ls, lidx = [], [], [], []
        for k in range(TREND_LOOK, p, -1):                      # oldest -> newest
            ph = pl = True
            for q in range(1, p + 1):
                if self.h(k) <= self.h(k - q) or self.h(k) <= self.h(k + q):
                    ph = False
                if self.l(k) >= self.l(k - q) or self.l(k) >= self.l(k + q):
                    pl = False
            if ph:
                hs.append(self.h(k)); hidx.append(k)
            if pl:
                ls.append(self.l(k)); lidx.append(k)
        if len(hs) < 2 or len(ls) < 2:
            return 0, None
        higher_low = ls[-1] > ls[-2]
        broke_top = any(self.body_hi(q) > hs[-1] for q in range(hidx[-1] - 1, 0, -1))      # "we are BREAKING ABOVE previous highs"
        lower_high = hs[-1] < hs[-2]
        broke_bottom = any(self.body_lo(q) < ls[-1] for q in range(lidx[-1] - 1, 0, -1))
        up, down = broke_top and higher_low, broke_bottom and lower_high
        if up == down:
            return 0, None
        if up:
            defend, peak_bar, peak = ls[-1], hidx[-1], hs[-1]
            if any(self.h(q) > peak for q in range(peak_bar - 1, 0, -1)):
                deep = min(self.l(q) for q in range(1, peak_bar + 1))
                defend = max(defend, deep)
            return 1, defend
        defend, trough_bar, trough = hs[-1], lidx[-1], ls[-1]
        if any(self.l(q) < trough for q in range(trough_bar - 1, 0, -1)):
            peak = max(self.h(q) for q in range(1, trough_bar + 1))
            defend = min(defend, peak)
        return -1, defend

    def hump_update(self, trend):
        """D_HumpUpdate: a direction flip starts a new budget; a flicker to 0 (inside a pullback) does not."""
        if trend != 0 and trend != self.hump_dir:
            self.hump_dir, self.hump_n, self.hump_last = trend, 0, None
        if self.hump_dir:
            self.hump_last, self.hump_n = self._swing(self.hump_dir, self.hump_last, self.hump_n)

    def _swing(self, d, last, n):
        """Count the newest confirmed swing (a pivot high in an uptrend, a pivot low in a downtrend) once."""
        p = PIVOT
        for k in range(p + 1, TREND_LOOK + 1):
            ok = True
            for q in range(1, p + 1):
                if d > 0 and (self.h(k) <= self.h(k - q) or self.h(k) <= self.h(k + q)):
                    ok = False
                if d < 0 and (self.l(k) >= self.l(k - q) or self.l(k) >= self.l(k + q)):
                    ok = False
            if not ok:
                continue
            if self.t(k) != last:                               # the NEWEST confirmed swing only
                return self.t(k), n + 1
            break
        return last, n

    def camel_step(self):
        """One closed bar of Zee's camel humps (his Turtle Trader Desk indicator): a swing is confirmed CAM_PIV candles after it prints - a
        high no lower than the CAM_PIV candles on each side, ties counting (a low mirrors it). Highs and lows alternate; two highs in a row
        merge into the taller one. A hump = swing low -> swing high -> next swing low; it is GREEN when it ends higher than it started
        (uptrend), RED when it ends lower (downtrend). The trend = the colour of the latest hump; Stk counts trend humps in a row."""
        p, z = CAM_PIV, self.cz
        if self.n < 2 * p + 1:
            return
        c = p + 1                                                  # the candidate, p candles before the bar that just closed
        ph = all(not (self.h(c) < self.h(c - d) or self.h(c) < self.h(c + d)) for d in range(1, p + 1))
        pl = all(not (self.l(c) > self.l(c - d) or self.l(c) > self.l(c + d)) for d in range(1, p + 1))
        tb = self.t(c)
        if ph:
            v = self.h(c)
            if z["T"] == 1:
                if v >= z["HV"]:
                    z["HB"], z["HV"] = tb, v
            else:
                z["Stk0"] = z["Stk"]; z["L0B"], z["L0V"] = z["LB"], z["LV"]; z["HB"], z["HV"] = tb, v; z["T"] = 1
        if pl:
            v = self.l(c); redraw = False
            if z["T"] == 1:
                z["LB"], z["LV"], z["T"] = tb, v, -1; redraw = True
            elif z["T"] == -1 and v <= z["LV"]:
                z["LB"], z["LV"] = tb, v; redraw = True
            elif z["T"] == 0:
                z["LB"], z["LV"], z["T"] = tb, v, -1
            if redraw and z["HB"] is not None and z["L0B"] is not None:
                z["Tr"] = 1 if z["LV"] > z["L0V"] else -1 if z["LV"] < z["L0V"] else 0
                z["Stk"] = (max(z["Stk0"], 0) + 1) if z["Tr"] == 1 else (min(z["Stk0"], 0) - 1) if z["Tr"] == -1 else 0
                if abs(z["Stk"]) >= CAM_CONFIRM:                    # the trend flips only after CAM_CONFIRM humps of the new colour in a row
                    z["Eff"] = 1 if z["Stk"] > 0 else -1
                elif z["Tr"] == 0 and CAM_CONFIRM <= 1:
                    z["Eff"] = 0

    # ------------------------------------------------------------------ 1. the retracement (D_RetracementOrigin, the 2026-09-29 fix)
    def origin(self, side):
        want_red = side > 0
        ext, best = -1, 0.0
        for k in range(2, RETRACE_BACK + 1):                     # where the impulse ended
            x = self.h(k) if want_red else self.l(k)
            if ext < 0 or (x > best if want_red else x < best):
                best, ext = x, k
        if ext < 2:
            return -1
        g = -1
        for k in range(ext, min(ext + 8, RETRACE_BACK + 8) + 1):  # "the last green candle in an uptrend"
            if k > self.n:
                break
            if (self.colour(k) > 0) if want_red else (self.colour(k) < 0):
                g = k
                break
        if g < 2:
            return -1
        lvl = self.l(g) if want_red else self.h(g)
        for k in range(g - 1, 0, -1):                            # the FIRST body to break it: where the retracement began
            if (self.colour(k) < 0) if want_red else (self.colour(k) > 0):
                if (self.body_lo(k) < lvl) if want_red else (self.body_hi(k) > lvl):
                    return k
        return -1

    # ------------------------------------------------------------------ 2. the UHV (D_FindUhv)
    def uhv(self, origin, side, strict=True):
        want_red = side > 0
        best, bestv = -1, -1
        for k in range(origin, 0, -1):
            if (self.colour(k) < 0) if want_red else (self.colour(k) > 0):
                if self.v(k) > bestv:
                    bestv, best = self.v(k), k
        if best < 1:
            return -1
        if not strict:
            return best                                          # LAWS.md: the loudest counter-coloured candle of the retracement
        rng = self.h(best) - self.l(best)
        if rng <= 0 or abs(self.c(best) - self.o(best)) / rng < UHV_BODY_MIN:
            return -1
        if best + 1 <= self.n and self.v(best + 1) > bestv:       # louder than its neighbours
            return -1
        if best > 1 and self.v(best - 1) > bestv:
            return -1
        return best

    # ------------------------------------------------------------------ 3. the breakout (D_BreakoutIsBar1) -> (fired, crossed_already)
    def breakout(self, u, side, loud_ok=False):
        if u <= 1:
            return False, False
        want_green = side > 0
        for k in range(u - 1, 0, -1):
            if (self.colour(k) > 0) if want_green else (self.colour(k) < 0):
                crossed = (self.body_hi(k) > self.h(u)) if want_green else (self.body_lo(k) < self.l(u))
                if not crossed:
                    continue
                if self.v(k) >= self.v(u) and not loud_ok:       # must be quieter than the UHV (Zee: a strong trend allows a louder one)
                    return False, True
                rk = self.h(k) - self.l(k)                       # LAWS.md (a): a momentum candle - its body fills at least 70% of its range
                if MOMENTUM_BODY > 0 and (rk <= 0 or abs(self.c(k) - self.o(k)) / rk < MOMENTUM_BODY):
                    return False, True
                return k == 1, True
        return False, False

    def laws(self, u, side):
        """D_DiamondsFor's three counted laws: the sweep before the UHV, the close beyond EMA-5, a clean quiet breakout."""
        d = 0
        for k in range(u + 1, min(u + 20, self.n) + 1):
            if (side > 0 and self.l(k) < self.l(u)) or (side < 0 and self.h(k) > self.h(u)):
                d += 1
                break
        if self.n >= 31:
            kk, e = 2.0 / 6.0, self.c(31)
            for i in range(30, 0, -1):
                e = self.c(i) * kk + e * (1.0 - kk)
            if (side > 0 and self.colour(1) > 0 and self.c(1) > e + 0.10 * self.unit) or \
               (side < 0 and self.colour(1) < 0 and self.c(1) < e - 0.10 * self.unit):
                d += 1
        rng = max(self.h(1) - self.l(1), 1e-12)
        wick = (self.h(1) - self.body_hi(1)) / rng if side > 0 else (self.body_lo(1) - self.l(1)) / rng
        if wick <= 0.25 and self.v(1) < self.v(u):
            d += 1
        return d

    def retrace_extreme(self, origin, side):
        ks = range(1, origin + 1)
        return min(self.l(k) for k in ks) if side > 0 else max(self.h(k) for k in ks)

    def continuous(self, nbars):
        return all(self.t(k) - self.t(k + 1) <= 60 + MAX_GAP_S for k in range(1, min(nbars, self.n - 1)))

    # ------------------------------------------------------------------ one closed bar (D_TryFire, as a reading)
    def _step(self, bars, vols, forming_t):
        self._set(bars, vols)
        trend, guard = self.camel_trend()
        self.hump_update(trend)                                   # the EA's own tally (only for the royal test)
        self.camel_step()
        z = self.cz
        self.camel = {"dir": z["Eff"], "humps": abs(z["Stk"]), "guard": None, "now": z["Eff"]}
        self.rough = None
        self.er = efficiency_ratio(m15_closes(bars, forming_t))
        if None in vols[-(TREND_LOOK + RETRACE_BACK + 8):]:
            return None                                           # a minute with no volume reading: no judgement on it
        if not self.continuous(TREND_LOOK + 5):
            return None
        # Zee 2026-11-04: "we must show all qualifying setups of this strategy" + "obviously we also need the camel humps first -> then comes
        # the retracement -> then the UHV inside that retracement -> then the wait for its breakout". Every setup on the side of HIS trend
        # gets a diamond; the EA's extra gates (a fresh trend reading on the breakout bar, the hump budget, the cooldown, the UHV's body
        # and neighbours) no longer hide one - they decide only whether it is ROYAL.
        side = self.cz["Eff"]                                      # Zee: buys only under a green hump, sells only under a red one (CAM_CONFIRM: in a row)
        strong = CAM_STRONG > 0 and (self.cz["Stk"] >= CAM_STRONG if side > 0 else self.cz["Stk"] <= -CAM_STRONG)
        fires, roughs = [], []
        if side:
            o = self.origin(side)
            u = self.uhv(o, side, strict=False) if o >= 0 else -1
            if u >= 0:
                fired, crossed = self.breakout(u, side, loud_ok=strong)
                if not crossed:
                    roughs.append((True, self.t(u), side, o, u))
                elif fired:
                    fires.append((True, self.t(u), side, o, u))
        if roughs:
            _a, _t, side, o, u = max(roughs)                      # the camel's side first, then the newest UHV
            self.rough = {"side": side, "level": self.h(u) if side > 0 else self.l(u), "uhv_t": self.t(u),
                          "extreme": self.retrace_extreme(o, side), "uhv_v": self.v(u)}
        if not fires:
            return None
        _a, _t, side, o, u = max(fires)
        ea = trend == side and self.hump_n < MAX_HUMPS and self.uhv(o, side, strict=True) == u and             (self.last_fire_t is None or self.t(1) - self.last_fire_t >= COOLDOWN_BARS * 60)
        if ea:
            self.last_fire_t = self.t(1)                          # the EA's own cooldown, kept for the royal test only
        ext = self.retrace_extreme(o, side)
        return {"side": side, "t": self.t(1) + 60, "level": self.h(u) if side > 0 else self.l(u), "uhv_t": self.t(u),
                "extreme": ext, "stop": ext - side * 0.50 * self.unit, "laws": self.laws(u, side), "er": self.er,
                "ea": ea, "royal": ea and self.er is not None and self.er >= ER_ROYAL}

    def update(self, bars, vol_of, now):
        """bars: the feed's 1-minute bars, the LAST one still forming. vol_of(bar) -> volume or None. Steps every newly closed bar once
        (the whole history on the first call, so the hump tally is right from the start). Returns the reading for the street."""
        if len(bars) < NEED + 2:
            return self.reading(now)
        closed, forming_t = bars[:-1], bars[-1][0]
        if self.first_t is not None and closed[0][0] < self.first_t - 1200:
            self.reset()                                          # older history arrived in front: replay it all, so the hump tally is right
        if self.last_t is not None and closed[-1][0] == self.last_t:
            return self.reading(now, bars[-1][4])               # no new closed bar: nothing to step (this runs ~10 times a second)
        vols = [vol_of(b) for b in closed]
        start = 0
        if self.last_t is not None:
            start = next((i for i in range(len(closed) - 1, -1, -1) if closed[i][0] <= self.last_t), -1) + 1
        for i in range(max(start, NEED), len(closed)):
            fire = self._step(closed[:i + 1], vols[:i + 1], closed[i + 1][0] if i + 1 < len(closed) else forming_t)
            if fire:
                self.cut = fire
        if closed:
            self.last_t = closed[-1][0]
            self.first_t = closed[0][0] if self.first_t is None else min(self.first_t, closed[0][0])
        return self.reading(now, bars[-1][4])

    def reading(self, now, price=None):
        cut = self.cut
        if cut is not None:
            age = now - cut["t"]
            broken = price is not None and (price - cut["extreme"]) * cut["side"] < 0     # back through the retracement's extreme
            if broken and not cut.get("shattered"):
                cut["shattered"] = now
            if age > CUT_LIFE_S or (cut.get("shattered") and now - cut["shattered"] > 4.0) or age < -120:
                self.cut = cut = None
        out = {"camel": self.camel["dir"], "humps": self.camel["humps"], "camel_now": self.camel.get("now", 0),
               "er": None if self.er is None else round(self.er, 3), "clean": self.er is not None and self.er >= ER_ROYAL}
        if self.rough and not cut:
            out["rough"] = self.rough["side"]
        if cut:
            out["cut"] = cut["side"]
            out["id"] = int(cut["t"])
            out["royal"] = bool(cut["royal"])
            out["ea"] = bool(cut.get("ea"))
            out["laws"] = cut["laws"]
            out["age"] = round(max(0.0, now - cut["t"]), 1)
            if cut.get("shattered"):
                out["shattered"] = True
        return out
