"""tools/make_fixtures.py - writes static/fixtures/<name>.json: one snapshot (CONTRACT.md section 7) per game state, so the frontend can be
built and screenshotted before the backend exists. Deterministic. Run: python tools/make_fixtures.py
The math (ladder a/b, x, stakes, terrain) follows CONTRACT.md section 5 exactly, so fixtures and the real engine agree."""
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "static", "fixtures")
T0 = 1793677800.0          # 2026-11-03 ~04:50 UTC
BINS = 96


def gen_bars(seed=7, n=330, start=3926.0, vol=0.55):
    rnd = random.Random(seed)
    bars, p, t = [], start, T0 - n * 60
    for i in range(n):
        o = p
        path = [o]
        for _ in range(24):
            p += rnd.gauss(0, vol / 4.5)
            path.append(p)
        bars.append([int(t), round(o, 2), round(max(path), 2), round(min(path), 2), round(p, 2), rnd.randint(150, 450)])
        t += 60
    return bars


def money(usd, risk):
    if risk < 1:
        v = round(usd, 4)
        s = f"{abs(v):.4f}".rstrip("0")
        whole, frac = s.split(".")
        body = "$" + whole + "." + frac.ljust(2, "0")
        return "-" + body if v < 0 else body
    return f"${usd:,.2f}"


def ladder(side, fill, sl, tp, banked=0.0, qty=0.01, qty0=0.01):
    sd0, td0 = abs(fill - sl), abs(tp - fill)
    f = qty / qty0
    span = sd0 + td0
    b = f * side / span
    a = (banked / qty0 - f * side * fill + sd0) / span
    return a, b, sd0, td0


def xp(a, b, p):
    return round(a + b * p, 5)


def pivots(bars, side, k=2, merge=0.25):
    out = []
    for i in range(k, len(bars) - k - 1):          # the last bar is still forming: its neighbours must be closed
        if side > 0:
            v = bars[i][3]
            if all(v < bars[j][3] for j in range(i - k, i + k + 1) if j != i):
                out.append(v)
        else:
            v = bars[i][2]
            if all(v > bars[j][2] for j in range(i - k, i + k + 1) if j != i):
                out.append(v)
    out.sort()
    merged = []
    for v in out:
        if merged and abs(v - merged[-1]) < merge:
            merged[-1] = min(merged[-1], v) if side > 0 else max(merged[-1], v)
        else:
            merged.append(v)
    return merged


def terrain(bars, a, b, x0=-0.3, x1=1.3, chasm_prices=None, extra_scorch=None):
    last = bars[-20:]
    h = []
    for i in range(BINS):
        xn = x0 + (x1 - x0) * (i + 0.5) / BINS
        p = (xn - a) / b
        c = sum(1 for bar in last if bar[3] <= p <= bar[2])
        h.append(round(c / 20.0, 3))
    older = bars[-300:-20]
    weathered, run = [], None
    for i in range(BINS):
        xn = x0 + (x1 - x0) * (i + 0.5) / BINS
        p = (xn - a) / b
        old = any(bar[3] <= p <= bar[2] for bar in older)
        if h[i] == 0 and old:
            run = run or [round(xn, 4), round(xn, 4)]
            run[1] = round(xn, 4)
        elif run:
            weathered.append(run)
            run = None
    if run:
        weathered.append(run)
    scorch = []
    for bar in last:
        rng = bar[2] - bar[3] or 1e-9
        body = abs(bar[4] - bar[1])
        if (bar[2] - max(bar[1], bar[4])) > 0.55 * rng and rng > 0.4:
            scorch.append(xp(a, b, bar[2]))
        if (min(bar[1], bar[4]) - bar[3]) > 0.55 * rng and rng > 0.4:
            scorch.append(xp(a, b, bar[3]))
    scorch += extra_scorch or []
    chasms = [[min(xp(a, b, p0), xp(a, b, p1)), max(xp(a, b, p0), xp(a, b, p1))] for p0, p1 in (chasm_prices or [])]
    return {"x0": x0, "x1": x1, "h": h, "chasms": chasms, "scorch": [s for s in scorch if x0 <= s <= x1], "weathered": weathered}


def base_snap(bars, quote_mid, spread=0.33, mode="sim", weather="active", session="london", day_frac=0.36, balance=25.0, coin=0.01):
    bid, ask = round(quote_mid - spread / 2, 2), round(quote_mid + spread / 2, 2)
    risk = coin * 1.0
    return {
        "v": 1, "t": T0, "mode": mode,
        "feed": {"ok": True, "age_s": 0.3, "reason": None, "tick_count": 18231, "ticks_per_s": 2.4, "market_open": True},
        "account": {"id": "SIM-1" if mode == "sim" else "L1869984", "type": {"sim": "SIM", "live": "LIVE", "replay": "REPLAY"}[mode],
                    "balance": balance, "equity": balance, "currency": "USD"},
        "quote": {"bid": bid, "ask": ask, "mid": round(quote_mid, 3), "spread": spread, "ts": T0 - 0.2},
        "market": {"session": session, "day_frac": day_frac, "weather": weather, "vol": {"dead": 0.05, "calm": 0.25, "active": 0.55, "storm": 0.95}[weather],
                   "lightning": weather == "storm", "season": 0.35, "tilt_raw": 0.2, "h24": 3970.2, "l24": 3891.13,
                   "shutters": {"down": False, "reason": None, "until": None},
                   "bell": {"last_t": T0 - 3200, "session": "london", "next_t": T0 + 16000},
                   "news": [{"t": T0 + 5400, "title": "US ISM Manufacturing PMI", "impact": "high"}]},
        "settings": {"coin_oz": coin, "stop_dist": 1.0, "stop_choices": [1, 2, 3], "target": 1.2, "targets": [1, 1.2, 1.5, 2, 3], "side": 1,
                     "live_enabled": False, "twin_invited": False, "twin_unlocked": False, "sound": True, "plain_line": True,
                     "eject_words": "the street said no", "risk_usd": risk, "money_unit": "cents" if risk < 1 else "dollars",
                     "can_split": coin >= 0.02, "min_qty": 0.01},
        "limits": {"rounds_today": 3, "rounds_max": 30, "loss_today_coins": 2.0, "loss_max_coins": 10, "stops_in_row": 1,
                   "jam_until": None, "locked_until": None, "alley_done": 2, "alley_needed": 5, "alley_eject_done": False,
                   "alley_machete_needed": coin >= 0.02, "live_allowed": False, "why_not_live": "alley"},
        "lobby": {"jar_usd": 0.0132, "jar_bites": 14,
                  "cabinet": [{"t": T0 - 86400, "usd": 0.012, "kind": "wooden"}, {"t": T0 - 3600, "usd": 0.012, "kind": "wooden"}],
                  "trophies": [{"key": "first_wooden", "title": "First wooden coin", "t": T0 - 90000}],
                  "tallies": {"by_session": {"asia": {"n": 3, "wins": 1, "net_usd": -0.008}, "london": {"n": 5, "wins": 2, "net_usd": 0.004},
                                             "newyork": {"n": 4, "wins": 1, "net_usd": -0.011}, "dead": {"n": 0, "wins": 0, "net_usd": 0}},
                              "by_weather": {"calm": {"n": 6, "wins": 2, "net_usd": -0.006}, "active": {"n": 5, "wins": 2, "net_usd": 0.001},
                                             "storm": {"n": 1, "wins": 0, "net_usd": -0.01}, "dead": {"n": 0, "wins": 0, "net_usd": 0}},
                              "by_patience": {"quick": {"n": 8, "wins": 2, "net_usd": -0.017}, "patient": {"n": 4, "wins": 2, "net_usd": 0.002}},
                              "wooden": {"n": 12, "wins": 4, "net_usd": -0.015}, "live": {"n": 0, "wins": 0, "net_usd": 0},
                              "ejected": {"n": 2, "wins": 1, "net_usd": -0.003, "would_have_usd": -0.008}, "twin": {"n": 0, "wins": 0, "net_usd": 0}},
                  "rounds_total": 12, "live_rounds_total": 0},
        "phase": "lobby", "preview": None, "round": None, "settlement": None, "freeze": False,
    }


def preview(bars, snap, side=1, patience=12.0, at_door=True):
    q = snap["quote"]
    entry = q["ask"] if side > 0 else q["bid"]
    sd = snap["settings"]["stop_dist"]
    td = snap["settings"]["target"]
    sl, tp = entry - side * sd, entry + side * td
    a, b, _, _ = ladder(side, entry, sl, tp)
    mark = q["bid"] if side > 0 else q["ask"]
    st = [{"price": p, "x": xp(a, b, p - 0.01 * side), "lit": True} for p in pivots(bars, side) if -0.05 <= xp(a, b, p) <= 1.05]
    return {"entry": entry, "stop": round(sl, 2), "target_price": round(tp, 2), "side": side, "a": round(a, 6), "b": round(b, 6),
            "x_entry": xp(a, b, entry), "x_mark": xp(a, b, mark), "tilt": 0.2 * side, "patience_s": patience, "at_door": at_door,
            "stakes": st, "terrain": terrain(bars, a, b), "pit": {"x0": min(xp(a, b, mark), xp(a, b, entry)), "x1": max(xp(a, b, mark), xp(a, b, entry)), "depth": 0.55}}


def make_round(bars, snap, side=1, move=0.0, age=42.0, kind="wooden", walls=None, sl_override=None, anvil_kind="vault", haggles=0,
               machete=False, qty0=0.01, night=False, golden_hour=False, twin=False, ghosts=True, tilt=0.3):
    q = snap["quote"]
    coin = qty0
    risk = coin * 1.0
    fill = round((q["ask"] if side > 0 else q["bid"]) - move * side, 2)       # the trade was opened `move` ago
    sl0, tp0 = round(fill - side * 1.0, 2), round(fill + side * 1.2, 2)
    mark = q["bid"] if side > 0 else q["ask"]
    qty = qty0 / 2 if machete else qty0
    banked = 0.0
    if machete:
        banked = round(qty0 / 2 * 0.55, 6)                                      # half banked at +0.55
    a, b, sd0, td0 = ladder(side, fill, sl0, tp0, banked, qty, qty0)
    tp = round(tp0 + side * 0.1 * haggles, 2)
    sl = sl_override if sl_override is not None else sl0
    pnl = round(side * (mark - fill) * qty, 6)
    result = round(banked + pnl, 6)
    value = round(risk + result, 6)
    stakes_p = pivots(bars, side)
    stakes = []
    for p in stakes_p:
        x = xp(a, b, p - 0.01 * side)
        if -0.05 <= x <= 1.05:
            stakes.append({"price": round(p, 2), "x": x, "lit": True, "passed": side * (mark - p) > 0.05, "used": abs(p - 0.01 * side - sl) < 0.005})
    wall_list = [{"price": w, "x": xp(a, b, w)} for w in (walls or [])]
    golden = None
    if machete:
        golden = {"price": sl, "x": xp(a, b, sl), "usd": round(banked - (qty0 / 2) * abs(fill - sl), 6)}
        golden["text"] = money(golden["usd"], risk)
    xr = xp(a, b, mark)
    rd = {
        "id": "20261103-045012-sim", "kind": kind, "side": side, "qty": qty, "qty0": qty0, "opened_t": T0 - age, "age_s": age, "patience_s": 12.0,
        "fill": fill, "sl": sl, "tp": tp, "stop_dist0": sd0, "target_dist0": td0, "target_dist": round(td0 + 0.1 * haggles, 2),
        "mark": mark, "spread": q["ask"] - q["bid"], "a": round(a, 6), "b": round(b, 6),
        "x": xr, "x_entry": xp(a, b, fill), "x_sl": xp(a, b, sl), "x_tp": xp(a, b, tp), "tilt": tilt,
        "pnl_usd": pnl, "banked_usd": banked, "result_usd": result, "value_usd": value, "risk_usd": risk,
        "value_text": money(value, risk), "tag_text": money(risk + qty * abs(tp - fill) + banked, risk),
        "anvil": {"price": sl, "x": xp(a, b, sl), "kind": anvil_kind, "pending": False},
        "stakes": stakes, "walls": wall_list, "walls_left": 2 - len(wall_list), "golden": golden,
        "haggles": haggles, "haggle_max": 3, "can_haggle": xr > xp(a, b, tp) - 0.12 and tilt > 0, "can_wall": len(wall_list) < 2,
        "can_anvil": any(s["passed"] and side * (s["price"] - sl) > 0 for s in stakes), "can_machete": (qty >= 0.02) and not machete,
        "machete_done": machete,
        "merchant": {"x": min(1.0, xr + 0.25), "visible": True, "dir": -1, "insists": False},
        "terrain": terrain(bars, a, b), "pit": {"x0": min(xp(a, b, fill - side * 0.33), xp(a, b, fill)), "x1": max(xp(a, b, fill - side * 0.33), xp(a, b, fill)), "depth": 0.55},
        "night": night, "golden_hour": golden_hour, "tarnish": min(1.0, age / 900.0),
        "twin": {"x": round(xr - 0.04, 4), "anvil_x": xp(a, b, sl), "state": "running", "result_usd": None} if twin else None,
        "ghosts": [{"id": "r-11", "path": [[i, round(0.30 + 0.25 * math.sin(i / 9.0), 4)] for i in range(0, 120, 2)]},
                   {"id": "r-10", "path": [[i, round(0.30 - 0.004 * i, 4)] for i in range(0, 75, 2)]}] if ghosts else [],
        "rat": [{"t": T0 - age, "usd": round(0.33 * qty0, 6), "why": "spread"}],
        "pending": None, "last_refusal": None,
    }
    return rd


def settlement(rd, outcome, exit_price, extra=None):
    risk = rd["risk_usd"]
    res = round(rd["banked_usd"] + rd["side"] * (exit_price - rd["fill"]) * rd["qty"], 6)
    value = round(risk + res, 6)                        # the coin's final value (the engine's settlement carries it too)
    names = {"buyer": "the take profit sold it", "anvil": "the stop loss sold it", "barrel": "the stop loss filled through a gap",
             "merchant": "you sold it at market", "eject": "you ejected at market"}
    verb = "Bought" if rd["side"] > 0 else "Sold"
    st = {"id": rd["id"], "kind": rd["kind"], "side": rd["side"], "outcome": outcome, "result_usd": res,
          "result_text": ("+" if res > 0 else "") + money(res, risk), "value_usd": value, "value_text": money(value, risk),
          "costs": {"spread_usd": round(0.33 * rd["qty0"], 6), "slippage_usd": 0.0002 if outcome == "barrel" else 0.0, "fee_usd": 0.0, "financing_usd": 0.0},
          "fill": rd["fill"], "exit": exit_price, "qty0": rd["qty0"], "age_s": rd["age_s"], "chasm": None, "balance_after": 25.0 + res,
          "twin_result_usd": None, "would_have_usd": None, "t": T0,
          "plain": f"{verb} {rd['qty0']:.2f} oz of gold at {rd['fill']:,.2f}; {names.get(outcome, outcome)} at {exit_price:,.2f}: {money(res, risk)} after a {money(0.33 * rd['qty0'], risk)} spread."}
    st.update(extra or {})
    rd["x"] = xp(rd["a"], rd["b"], exit_price)          # the round ends where the exit price sits on the ladder
    rd["mark"] = exit_price
    rd["result_usd"], rd["pnl_usd"], rd["value_usd"] = res, round(res - rd["banked_usd"], 6), value     # frozen at the end, as the engine
    rd["value_text"] = money(value, risk)
    rd["tilt"] = 0.0                                    # a settled street is level (the engine sends tilt 0 once the round is final)
    return st


def write(name, snap, events=None):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"snap": snap, "events": events or []}, f, indent=1)


def main():
    bars = gen_bars()
    mid = bars[-1][4]

    s = base_snap(bars, mid); s["phase"] = "lobby"; s["preview"] = preview(bars, s, at_door=False)
    write("lobby", s, [{"type": "bell", "session": "london"}])

    s = base_snap(bars, mid); s["phase"] = "aiming"; s["preview"] = preview(bars, s, patience=34.0)
    write("aiming", s)

    s = base_snap(bars, mid); s["phase"] = "open"; s["round"] = make_round(bars, s, move=0.9, tilt=0.6)
    write("open_profit", s, [{"type": "stake", "x": 0.5}])

    s = base_snap(bars, mid); s["phase"] = "open"; s["round"] = make_round(bars, s, move=-0.45, tilt=-0.7)
    write("open_loss", s, [{"type": "rat", "usd": 0.0003, "why": "slippage"}])

    s = base_snap(bars, mid); s["phase"] = "open"
    r = make_round(bars, s, move=0.6, tilt=-0.2)
    wall = round(r["mark"] - 0.30, 2)
    r = make_round(bars, s, move=0.6, tilt=-0.2, walls=[min(wall, r["fill"])], sl_override=min(wall, r["fill"]), anvil_kind="wall")
    s["round"] = r
    write("open_wall", s, [{"type": "wall", "ok": True, "x": r["anvil"]["x"]}])

    s = base_snap(bars, mid); s["phase"] = "open"
    r = make_round(bars, s, move=1.15, tilt=0.5, haggles=1, anvil_kind="haggle")
    r["can_haggle"] = True
    s["round"] = r
    write("open_haggle", s, [{"type": "haggle", "ok": True}])

    s = base_snap(bars, mid, coin=0.02); s["phase"] = "open"
    s["round"] = make_round(bars, s, move=0.7, tilt=0.3, machete=True, qty0=0.02)
    write("open_machete", s, [{"type": "machete", "ok": True, "usd": 0.0055}])

    s = base_snap(bars, mid); s["phase"] = "open"; s["settings"]["side"] = -1
    s["round"] = make_round(bars, s, side=-1, move=0.5, tilt=0.4)
    write("open_short", s)

    s = base_snap(bars, mid, weather="storm", spread=0.62); s["phase"] = "open"
    r = make_round(bars, s, move=0.2, tilt=-0.9)
    r["terrain"] = terrain(bars, r["a"], r["b"], chasm_prices=[(r["fill"] - 0.75, r["fill"] - 0.35)])
    s["round"] = r; s["market"]["news"] = [{"t": T0 - 60, "title": "US Non-Farm Payrolls", "impact": "high"}]
    write("open_storm", s, [{"type": "lightning"}])

    s = base_snap(bars, mid, session="newyork", day_frac=0.8); s["phase"] = "open"
    s["round"] = make_round(bars, s, move=0.3, age=690, night=True, tilt=0.1, twin=True)
    write("open_night", s)

    s = base_snap(bars, mid); s["phase"] = "open"; s["round"] = make_round(bars, s, move=0.4, tilt=0.0)
    s["freeze"] = True; s["feed"]["ok"] = False; s["feed"]["age_s"] = 7.5; s["feed"]["reason"] = "page socket closed"
    write("freeze", s, [{"type": "freeze", "on": True}])

    s = base_snap(bars, mid); s["phase"] = "settled"
    r = make_round(bars, s, move=1.2, age=180, tilt=0.8); s["round"] = r
    s["settlement"] = settlement(r, "buyer", r["tp"])
    write("settled_buyer", s, [{"type": "settled", "outcome": "buyer"}])

    s = base_snap(bars, mid); s["phase"] = "settled"
    r = make_round(bars, s, move=-0.66, age=95, tilt=-0.8); s["round"] = r
    s["settlement"] = settlement(r, "anvil", r["sl"])
    write("settled_anvil", s, [{"type": "settled", "outcome": "anvil"}])

    s = base_snap(bars, mid, weather="storm", spread=0.7); s["phase"] = "settled"
    r = make_round(bars, s, move=-0.9, age=60, tilt=-1.0); s["round"] = r
    gap_fill = round(r["sl"] - r["side"] * 0.65, 2)
    s["settlement"] = settlement(r, "barrel", gap_fill, {"chasm": sorted([xp(r["a"], r["b"], r["sl"]), xp(r["a"], r["b"], gap_fill)])})
    write("settled_barrel", s, [{"type": "settled", "outcome": "barrel"}])

    s = base_snap(bars, mid); s["phase"] = "lobby"; s["preview"] = preview(bars, s, at_door=False)
    s["limits"]["stops_in_row"] = 3; s["limits"]["jam_until"] = T0 + 540
    s["market"]["shutters"] = {"down": True, "reason": "jam", "until": T0 + 540}
    write("jammed", s)

    s = base_snap(bars, mid); s["phase"] = "lobby"; s["preview"] = preview(bars, s, at_door=False)
    s["limits"]["loss_today_coins"] = 10.0; s["limits"]["locked_until"] = T0 + 68000
    s["market"]["shutters"] = {"down": True, "reason": "locked", "until": T0 + 68000}
    write("locked", s)

    s = base_snap(bars, mid, weather="dead", session="dead", day_frac=0.9); s["phase"] = "lobby"; s["preview"] = preview(bars, s, at_door=False)
    s["market"]["shutters"] = {"down": True, "reason": "dead_hours", "until": T0 + 6000}
    write("shutters_dead", s)

    s = base_snap(bars, mid, session="asia", day_frac=0.1, weather="calm"); s["phase"] = "open"
    s["round"] = make_round(bars, s, move=0.35, kind="wooden", tilt=0.25, twin=True)
    write("alley_wooden", s)

    s = base_snap(bars, mid, mode="replay"); s["phase"] = "open"
    s["round"] = make_round(bars, s, move=0.5, kind="wooden", tilt=0.3)
    write("replay", s)
    print("fixtures:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
