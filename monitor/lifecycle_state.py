"""lifecycle_state.py — where in the setup are we, right now?

Zee 2026-08-03 gave the states himself:

    1  trend is up, waiting for retracement
    2  retracement — is it proven valid?
    3  yes, we're in retracement now
    4  waiting for the final UHV to form in this retracement
    5  UHV formed, its high is locked, tracking the breakout of that level
    6  candle approaching the breakout
    7  breakout crossing the level
    8  breakout candle is momentum, low volume, and has closed beyond the UHV high
    9  breakout confirmed
   10  opening the trade
   11  monitoring the open trade

Until now the system only ever said "armed" or "pending", which collapses nine distinct
situations into one word — so neither of us could see *why* nothing was happening, or how
close it was. Each state below is decided from the same bars and the same helpers the
detector uses, so this cannot drift away from what actually fires.

State 0 is the honest answer when there is no trend at all: standing aside is a state too.
"""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_entry_review_m5 as B          # noqa: E402
from claude_judge import load_bars, MARKETS, PENDING, COMMON   # noqa: E402

# how close the price must be to the locked level before it counts as "approaching"
NEAR_PTS = {"XAU": 1.0, "BTC": 60.0}

# How big a turn has to be before it counts as a swing, as a fraction of the recent range.
# This is the one number that decides whether the ladder agrees with what Zee is looking at,
# and he should never have to name it — "pt mujhe nahi pata, ye aapki language hai." So it
# is calibrated FROM his readings: calibrate() searches for the fraction that reproduces the
# trend he says he sees, and stores it. He speaks in structure; the number is my problem.
SWING_CAL = Path(__file__).resolve().parent / "setup_labels" / "swing_scale.json"
try:
    SWING_FRAC = float(json.loads(SWING_CAL.read_text(encoding="utf-8"))["frac"])
except Exception:
    SWING_FRAC = 0.16

STATES = {
    0:  "no trend — standing aside",
    1:  "trend established, waiting for a retracement",
    2:  "a pullback started — is it a valid retracement?",
    3:  "in a valid retracement",
    4:  "waiting for the final UHV to form in this retracement",
    5:  "UHV formed — level locked, tracking the breakout",
    6:  "candle approaching the breakout level",
    7:  "breakout crossing the level (candle still open)",
    8:  "breakout candle closed beyond — checking momentum and volume",
    9:  "breakout confirmed — awaiting the verdict",
    10: "opening the trade",
    11: "monitoring the open trade",
}


def _pivots(bars, min_leg=None, look=120):
    """Swing highs and lows, as a zigzag: highs and lows must ALTERNATE, and each leg has
    to be at least `min_leg` big before it counts as a turn.

    The first version took any bar that was the extreme of seven, which on M1 gold marks
    every small wiggle. Zee caught it live: price had run 4046.68 -> 4058.28, pulled back,
    and he read that plainly as an uptrend in retracement — while the panel said "no trend",
    because a 0.35 blip at 09:56 had been counted as a second, lower swing high inside the
    very same push. A swing is a turn of a real size, not a bar with three smaller
    neighbours."""
    n = len(bars); lo = max(0, n - look)
    if min_leg is None:
        # A "real" turn is sized against how far this market has actually been travelling.
        # A fixed number is wrong twice over: too small in a fast hour (every wiggle is a
        # swing), too large in a quiet one (nothing is). A quarter of the recent range
        # tracks both.
        seg = bars[max(0, n - 60):]
        rng = max(b.h for b in seg) - min(b.l for b in seg)
        min_leg = max(1.0, SWING_FRAC * rng)
    hi, ln = [], []
    # walk forward tracking the running extreme, and commit a pivot when price reverses
    # by at least min_leg from it
    up = None                      # True = currently seeking a high, False = seeking a low
    ext_i = lo
    for i in range(lo + 1, n):
        b = bars[i]
        if up is None:
            if b.h - bars[ext_i].l >= min_leg:
                up, ln_i = True, ext_i; ln.append(ln_i); ext_i = i
            elif bars[ext_i].h - b.l >= min_leg:
                up, hi_i = False, ext_i; hi.append(hi_i); ext_i = i
            else:
                if b.h > bars[ext_i].h or b.l < bars[ext_i].l:
                    pass
            continue
        if up:
            if b.h >= bars[ext_i].h:
                ext_i = i
            elif bars[ext_i].h - b.l >= min_leg:
                hi.append(ext_i); up = False; ext_i = i
        else:
            if b.l <= bars[ext_i].l:
                ext_i = i
            elif b.h - bars[ext_i].l >= min_leg:
                ln.append(ext_i); up = True; ext_i = i
    return hi, ln


def swing_trend(bars):
    """The newest swing decides the trend.

    Zee 2026-08-03, deleting my earlier rule outright: "iss rule ko mita do — 'lower low AUR
    lower high, dono chahiye'." He had pointed at a fresh higher low and asked why nothing
    was moving, and he is right that waiting for both halves means the ladder only wakes up
    after the move is already under way.

    So: take whichever pivot happened LAST and compare it with the previous pivot of the
    same kind. A fresh higher low is an uptrend. A fresh lower high is a downtrend. One is
    enough.

    Returns (direction, human-readable proof)."""
    hi, ln = _pivots(bars)
    if not hi and not ln:
        return None, "no swings yet"
    last_hi = hi[-1] if hi else -1
    last_ln = ln[-1] if ln else -1
    if last_ln > last_hi:                      # the newest turn was a LOW
        if len(ln) < 2:
            return None, "only one swing low so far"
        l1, l2 = bars[ln[-2]].l, bars[ln[-1]].l
        if l2 > l1:
            return "up", f"fresh HIGHER LOW {l2:.2f} > {l1:.2f}"
        if l2 < l1:
            return "down", f"fresh LOWER LOW {l2:.2f} < {l1:.2f}"
        return None, f"the last two lows are equal ({l2:.2f})"
    if len(hi) < 2:
        return None, "only one swing high so far"
    h1, h2 = bars[hi[-2]].h, bars[hi[-1]].h
    if h2 > h1:
        return "up", f"fresh HIGHER HIGH {h2:.2f} > {h1:.2f}"
    if h2 < h1:
        return "down", f"fresh LOWER HIGH {h2:.2f} < {h1:.2f}"
    return None, f"the last two highs are equal ({h2:.2f})"


def calibrate(market, says):
    """Zee says the trend is `says` ("up"/"down"). Find the swing scale that agrees.

    He reads structure, not numbers. When the ladder disagrees with his eye, this searches
    the scales and keeps the one that reproduces his reading — so a correction from him is
    a single sentence, never a parameter."""
    global SWING_FRAC
    bars = load_bars(MARKETS[market]["data"])
    seg = bars[max(0, len(bars) - 60):]
    rng = max(b.h for b in seg) - min(b.l for b in seg)
    for frac in [round(x / 100, 2) for x in range(6, 51)]:
        hi, ln = _pivots(bars, min_leg=max(1.0, frac * rng))
        if len(hi) < 2 or len(ln) < 2:
            continue
        h1, h2 = bars[hi[-2]].h, bars[hi[-1]].h
        l1, l2 = bars[ln[-2]].l, bars[ln[-1]].l
        got = ("up" if (h2 > h1 and l2 > l1) else
               "down" if (h2 < h1 and l2 < l1) else None)
        if got == says:
            SWING_FRAC = frac
            SWING_CAL.parent.mkdir(parents=True, exist_ok=True)
            SWING_CAL.write_text(json.dumps({"frac": frac, "says": says,
                                             "range": round(rng, 2),
                                             "min_leg": round(max(1.0, frac * rng), 2)}),
                                 encoding="utf-8")
            return {"ok": True, "frac": frac, "min_leg": round(max(1.0, frac * rng), 2),
                    "highs": [round(h1, 2), round(h2, 2)],
                    "lows": [round(l1, 2), round(l2, 2)]}
    return {"ok": False, "reason": f"koi paimana '{says}' nahi dikhata"}


def _uhv_in_zone(bars, rs, side):
    """The highest-volume counter-trend candle in the retracement that is a local peak.

    Same rule the detector uses: strictly higher volume than both neighbours, so a flat
    stretch of equal volume never produces a phantom UHV."""
    best = None
    for k in range(rs, len(bars)):
        c = bars[k]
        if not (c.is_bear if side == "BUY" else c.is_bull):
            continue
        if k - 1 >= 0 and bars[k - 1].v >= c.v:
            continue
        if k + 1 < len(bars) and bars[k + 1].v >= c.v:
            continue
        if best is None or c.v > bars[best].v:
            best = k
    return best


def state(market="XAU"):
    """Return the current state as a dict: n, name, side, and whatever is known so far."""
    m = MARKETS[market]
    out = {"market": market, "when": datetime.now(timezone.utc).strftime("%H:%M:%SZ")}

    # 11 first — an open position outranks everything the chart might be doing
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gui"))
        import trade_book as TB
        lv = TB.live(market)
        pos = lv.get("positions") or []
        if pos:
            p = pos[0]
            run = (p["price"] - p["entry"]) if p["side"] == "BUY" else (p["entry"] - p["price"])
            return {**out, "n": 11, "name": STATES[11], "side": p["side"],
                    "entry": p["entry"], "price": p["price"], "sl": p.get("sl"),
                    "run_pts": round(run, 2), "profit": p.get("profit"),
                    "detail": f"{p['side']} {p['entry']} · now {p['price']} "
                              f"({run:+.2f} pt)"}
    except Exception:
        pass

    # 9 / 10 — a setup is on the table
    if PENDING.exists():
        try:
            p = json.loads(PENDING.read_text(encoding="ascii"))
            if p.get("market") == market:
                age = int(time.time()) - p.get("created", 0)
                n = 10 if p.get("status") == "APPROVED" else 9
                return {**out, "n": n, "name": STATES[n], "side": p.get("side"),
                        "entry": p.get("entry"), "age_sec": age,
                        "strength": p.get("strength"), "brk_body": p.get("brk_body"),
                        "uhv_vol": p.get("uhv_vol"),
                        "detail": f"{p.get('side')} @ {p.get('entry')} · {age}s old · "
                                  f"body {p.get('brk_body')} · UHV {p.get('uhv_vol')}"}
        except Exception:
            pass

    bars = load_bars(m["data"])
    if len(bars) < 40:
        return {**out, "n": 0, "name": "not enough data",
                "detail": f"only {len(bars)} bars"}

    k = m["k"]
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5 * k; B.TREND_DOM = 1.0     # the trend picks the side
    n = len(bars); px = bars[-1].c
    near_pts = NEAR_PTS.get(market, 1.0)

    direction, proof = swing_trend(bars)
    want = {"up": "BUY", "down": "SELL"}.get(direction)
    best_state = {**out, "n": 0, "name": STATES[0], "price": round(px, 2),
                  "detail": proof}
    per_side = {}

    for side in ("BUY", "SELL"):
        trend = "up" if side == "BUY" else "down"
        if want is None:
            # No trend, no side. The guard only skipped the *wrong* side before, so when
            # the structure named neither, BOTH columns kept advancing - the very thing
            # Zee objected to: "humara setup iss tarah do tarfa nahi banta."
            per_side[side] = {**out, "n": 0, "name": STATES[0], "side": side,
                              "detail": proof}
            continue
        if side != want:
            per_side[side] = {**out, "n": 0, "name": STATES[0], "side": side,
                              "detail": f"structure says {direction} — this side is idle"}
            continue                     # the swing structure names one side only
        o = next((j for j in range(n - 1, max(n - 1 - B.LB, 0), -1)
                  if B.is_origin(bars, j, side)), None)
        if o is None:
            # a trend may exist even with no pullback yet — check the hump directly
            if want == side:
                pull = "downward pull in RED candles" if side == "BUY"                     else "upward pull in GREEN candles"
                cand = {**out, "n": 1, "name": STATES[1], "side": side, "trend": trend,
                        "price": round(px, 2), "proof": proof,
                        "detail": f"{proof} — waiting for a {pull}"}
                if cand["n"] > best_state["n"]:
                    best_state = cand
            continue

        rs = B.retr_zone_start(bars, o, side)
        depth = (bars[rs].h - min(b.l for b in bars[rs:]) if side == "BUY"
                 else max(b.h for b in bars[rs:]) - bars[rs].l)
        cand = {**out, "side": side, "trend": trend, "price": round(px, 2),
                "retr_from": round(bars[rs].h if side == "BUY" else bars[rs].l, 2),
                "retr_depth": round(depth, 2)}

        if depth < 0.5 * k:
            cand.update(n=2, name=STATES[2],
                        detail=f"pullback only {depth:.2f} pt deep — not yet a retracement")
        else:
            u = _uhv_in_zone(bars, rs, side)
            if u is None:
                colour = "RED" if side == "BUY" else "GREEN"
                cand.update(n=4, name=STATES[4],
                            detail=f"retracement started {bars[rs].t:%H:%M}Z — waiting for "
                                   f"the {colour} candle with the highest volume")
            else:
                U = bars[u]
                lvl = U.h if side == "BUY" else U.l
                dist = (lvl - px) if side == "BUY" else (px - lvl)
                cand.update(uhv_vol=round(U.v, 2), uhv_time=U.t.strftime("%H:%MZ"),
                            level=round(lvl, 2), distance=round(abs(dist), 2),
                            bars_since_uhv=n - 1 - u)
                last = bars[-1]
                crossed_close = (last.is_bull and last.c > lvl) if side == "BUY" \
                    else (last.is_bear and last.c < lvl)
                crossed_wick = (last.h > lvl) if side == "BUY" else (last.l < lvl)
                if crossed_close:
                    ok_body = last.body_ratio >= 0.5
                    ok_vol = last.v < U.v
                    cand.update(n=8, name=STATES[8],
                                brk_body=round(last.body_ratio, 2),
                                brk_vol=round(last.v, 2),
                                detail=(f"UHV {U.t:%H:%M}Z  ·  {last.t:%H:%M}Z closed "
                                        f"beyond {lvl:.2f} · body {last.body_ratio:.2f} "
                                        f"{'ok' if ok_body else 'TOO WEAK'} · vol "
                                        f"{last.v:.0f} vs {U.v:.0f} "
                                        f"{'ok' if ok_vol else 'TOO HIGH'}"))
                elif crossed_wick:
                    cand.update(n=7, name=STATES[7],
                                detail=f"UHV {U.t:%H:%M}Z · {lvl:.2f} chhu liya, "
                                       f"{last.t:%H:%M}Z candle abhi band nahi hui")
                elif abs(dist) <= near_pts:
                    cand.update(n=6, name=STATES[6],
                                detail=f"UHV {U.t:%H:%M}Z · level {lvl:.2f} · "
                                       f"{abs(dist):.2f} away")
                else:
                    cand.update(n=5, name=STATES[5],
                                detail=f"UHV {U.t:%H:%M}Z (vol {U.v:.0f}) · level "
                                       f"{lvl:.2f} locked · {abs(dist):.2f} away")
        per_side[side] = cand
        if cand["n"] > best_state["n"]:
            best_state = cand
    best_state["sides"] = per_side
    best_state["trend_proof"] = proof
    best_state["trend_dir"] = direction
    return best_state


def to_text(market="XAU"):
    s = state(market)
    bar = "".join("#" if i <= s["n"] else "." for i in range(1, 12))
    lines = [f"  STATE {s['n']:>2}/11  [{bar}]  {s['name']}"]
    if s.get("side"):
        lines.append(f"            side {s['side']}"
                     + (f" · {s['trend']}trend" if s.get("trend") else ""))
    if s.get("detail"):
        lines.append(f"            {s['detail']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mk = sys.argv[1] if len(sys.argv) > 1 else "XAU"
    if "--json" in sys.argv:
        print(json.dumps(state(mk), indent=1, default=str))
    else:
        print(to_text(mk))
