"""losslab.py - the loss cutter of Claude's Exit Research Lab (Zee 2026-10-21: "i want you to add a mode which helps reduce loss ... the
suggestions it gives after the "scan every setting" -> are the suggestions which -> help cut down the lossy trades to a minimum -> so ideally
we're trying to find a setting which keeps the winrate while reducing: Loss per trade / Break-even win rate / Avg loss, Worst loss").

  loss_stats(pnl) - the loss side of a list of trades: avg win / loss, worst loss, the worst-5% average (tail), losses per trade (every $ lost
                    / every trade), break-even win rate and the margin (win rate - break-even). The scan returns them for the bench and for
                    every move, so the page can rank loss cuts without scanning again.
  autopsy(...)    - reads the bench's own trades: how far winners go against you before they win (MAE), how long winners and losers stay
                    open, which losers were in profit first, where the losses cluster (side, hour, weekday, candle, stop width, volatility)
                    and what equal-risk sizing would do. Each finding proposes the settings that act on it, with values taken from the trades
                    (scan.py turns them into moves and runs them like every other move).
Python tester numbers are hypotheses until MT5 confirms them (CLAUDE.md)."""
import math

import numpy as np

KIND = {1: "pin bars", 21: "hammers (BUY)", 22: "shooting stars (SELL)", 3: "marubozus", 4: "Lego setups"}
KIND_SWITCH = {1: "InpUsePin", 21: "InpHammer", 22: "InpStar", 3: "InpMarubozu"}
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def loss_stats(p):
    """p = the results of the trades ($). margin = win rate - break-even win rate (points): how many points of win rate real trading can take
    before the strategy stops making money (= expectancy / (avg win + |avg loss|), so it cannot be bought by making every trade smaller)."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    if n == 0:
        return {"n": 0, "wr": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "worst": 0.0, "tail": 0.0, "lpt": 0.0, "be": None, "margin": None, "net": 0.0}
    w, lo = p[p > 0], p[p <= 0]
    aw = float(w.mean()) if len(w) else 0.0
    al = float(lo.mean()) if len(lo) else 0.0
    k = min(n, max(3, int(math.ceil(0.05 * n))))
    tail = float(np.sort(p)[:k].mean())
    wr = 100.0 * len(w) / n
    be = 100.0 * -al / (aw - al) if aw - al > 0 else None
    return {"n": n, "wr": round(wr, 2), "avg_win": round(aw, 1), "avg_loss": round(al, 1), "worst": round(float(p.min()), 1), "tail": round(tail, 1),
            "lpt": round(float(-lo.sum()) / n, 1), "be": round(be, 2) if be is not None else None,
            "margin": round(wr - be, 2) if be is not None else None, "net": round(float(p.sum()), 1)}


def day_stats(real):
    """the day-to-day picture: days with a trade, the share that ended green, the worst and the median day (by the exit's server day)"""
    if not len(real):
        return {"days": 0, "green": 0.0, "worst": 0.0, "median": 0.0}
    d = (real[:, 4] // 86400).astype(np.int64)
    u, inv = np.unique(d, return_inverse=True)
    tot = np.zeros(len(u))
    np.add.at(tot, inv, real[:, 6])
    return {"days": int(len(u)), "green": round(float(100.0 * (tot > 0).mean()), 1), "worst": round(float(tot.min()), 1), "median": round(float(np.median(tot)), 1)}


def _q(a, p):
    return float(np.percentile(a, p)) if len(a) else 0.0


def _up(v, st):
    return round(math.ceil(v / st - 1e-9) * st, 4)


def _money(v):
    return ("-" if v < 0 else "") + f"${abs(v):,.0f}"


def _pkt(h):
    """a server hour (UTC+3 in summer, +2 in winter) as Pakistani time (UTC+5), 12-hour"""
    k = (int(h) + 2) % 24
    return f"{(k % 12) or 12} {'AM' if k < 12 else 'PM'}"


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _setup_of(real, setups):
    """the setup candle of every trade: the last setup on the same side before the entry candle (setups rows: candle, side, kind)
    -> (kind, candle index; -1 when none is found)"""
    kind = np.zeros(len(real), dtype=np.int64)
    cand = np.full(len(real), -1, dtype=np.int64)
    if not len(setups):
        return kind, cand
    si = setups[:, 0]
    for n, x in enumerate(real):
        j = int(np.searchsorted(si, x[11], side="left")) - 1
        while j >= 0 and int(setups[j, 1]) != int(x[0]):
            j -= 1
        if j >= 0:
            kind[n] = int(setups[j, 2])
            cand[n] = int(setups[j, 0])
    return kind, cand


def _buckets(name, labels, keys, p, base, min_n):
    """one row per bucket: trades, win rate, net, avg loss, margin - flagged when a MINORITY of the trades (enough of them, with enough
    trades left outside it to compare with) loses money or has a margin far below the rest"""
    rows = []
    n = len(p)
    for key in sorted(set(keys.tolist())):
        m = keys == key
        s = loss_stats(p[m])
        if s["n"] < 1:
            continue
        rest = loss_stats(p[~m])
        bad = bool(min_n <= s["n"] <= 0.5 * n and rest["n"] >= min_n and
                   (s["net"] < 0 or (s["margin"] is not None and rest["margin"] is not None and s["margin"] < rest["margin"] - 3)))
        rows.append({"dim": name, "key": key if not isinstance(key, (np.integer,)) else int(key), "label": labels(key), "n": s["n"], "wr": s["wr"],
                     "net": s["net"], "avg_loss": s["avg_loss"], "margin": s["margin"], "rest_margin": rest["margin"], "bad": bad})
    return rows


def autopsy(real, setups, D, base_in, labfull):
    """the bench's trades -> {facts, clusters, proposals}. proposals: {sets} (EA settings) or {lab} (Exit Lab fields), with label / from / to /
    why; scan.py turns them into moves (deduplicated against its own) and runs them."""
    p = real[:, 6].astype(float) if len(real) else np.zeros(0)
    n = len(p)
    out = {"n": n, "facts": [], "clusters": [], "proposals": [], "now": loss_stats(p)}
    if n < 20:
        out["facts"].append({"icon": "🔬", "title": "Too few trades", "text": f"{n} trades: the autopsy needs at least 20."})
        return out
    g = lambda k, d="": str(base_in.get(k, d)).strip()  # noqa: E731
    mode = g("InpExitMode", "1")
    lab_ok = mode in ("1", "2")
    L = dict(labfull or {})
    lf = lambda f: _f(L.get(f, 0))  # noqa: E731
    win, los = p > 0, p <= 0
    R = np.maximum(real[:, 17], 0.01)
    mfe, mae = real[:, 15], real[:, 16]
    k_in, k_out = real[:, 11].astype(np.int64), real[:, 12].astype(np.int64)
    held = k_out - k_in                                    # candles after the entry candle (the Exit Lab's time rules count the same way)
    atr = D["atr"]
    a_in = atr[np.clip(k_in - 1, 0, len(atr) - 1)]          # the EA's ATR at the entry: the last closed candle's
    kind, cand = _setup_of(real, setups)
    kind = np.where(kind == 2, np.where(real[:, 0] > 0, 21, 22), kind)
    # the session and weekday filters judge the SETUP candle: its hour / day (the entry's when no setup was found)
    t_set = np.where(cand >= 0, D["t15"][np.clip(cand, 0, len(D["t15"]) - 1)], real[:, 1]).astype(np.int64)
    hr = np.where(cand >= 0, D["hr15"][np.clip(cand, 0, len(D["hr15"]) - 1)], (t_set // 3600) % 24).astype(np.int64)
    dow = ((t_set // 86400 + 4) % 7).astype(np.int64)
    S = out["now"]
    props = out["proposals"]
    nl = int(los.sum())

    # ---- 1. the losses themselves
    lo = np.sort(p[los])
    top = max(1, int(math.ceil(0.1 * nl)))
    share = float(lo[:top].sum() / lo.sum()) if nl and lo.sum() < 0 else 0.0
    out["facts"].append({"icon": "🩸", "title": "Your losses", "text":
                         f"{nl} of {n} trades lost ({100 - S['wr']:.1f}%). Average loss {_money(S['avg_loss'])} against an average win of {_money(S['avg_win'])}: "
                         f"one loss takes back {(-S['avg_loss'] / max(1.0, S['avg_win'])):.1f} wins. Worst {_money(S['worst'])}; the worst 5% of trades average {_money(S['tail'])}. "
                         f"The worst 10% of your losses are {100 * share:.0f}% of every $ lost; losses cost {_money(S['lpt'])} per trade (every $ lost / every trade). "
                         f"Break-even win rate {S['be'] if S['be'] is not None else '–'}%, so the margin is {S['margin'] if S['margin'] is not None else '–'} points."})
    if not nl:
        return out

    # ---- 2. how far winners go against you before they win (MAE): the line beyond which a trade is (nearly) always a loser
    mw, ml = mae[win], mae[los]
    if len(mw) >= 20:
        c = {pc: max(0.5, _up(_q(mw, pc), 0.5)) for pc in (90, 95, 98)}
        lots = np.where(real[:, 18] > 0, real[:, 18], _f(base_in.get("InpLots"), 1.0))
        c95 = c[95]
        hit_w = float((mw >= c95).mean())
        capd = los & (mae >= c95)
        est = p.copy()
        est[(mae >= c95)] = -c95 * lots[(mae >= c95)] * 100.0
        es = loss_stats(est)
        out["facts"].append({"icon": "📏", "title": "How far winners go against you first", "text":
                             f"90% of your winners never went more than ${c[90]:g} against you, 95% not more than ${c95:g}, 98% not more than ${c[98]:g} "
                             f"(the median loser went ${_q(ml, 50):.2f}). A stop ${c95:g} from the entry would turn {100 * hit_w:.1f}% of the winners into losses "
                             f"but cap {int(capd.sum())} of {nl} losses - first estimate: average loss {_money(es['avg_loss'])}, worst {_money(es['worst'])}, "
                             f"break-even {es['be'] if es['be'] is not None else '–'}%, margin {es['margin'] if es['margin'] is not None else '–'} points "
                             f"(the scan below runs it for real)."})
        slm = g("InpSlMode", "1")
        now_stop = {"0": f"{g('InpSlPips')} pips beyond the candle", "1": f"{g('InpSlAtrMult')} x ATR from the entry", "2": f"${g('InpSlUsd')} from the entry"}.get(slm, "")
        for pc in (90, 95, 98):
            v = c[pc]
            why = f"{pc}% of your winners never went more than ${v:g} against you"
            if slm == "2":
                if v < _f(base_in.get("InpSlUsd")) - 0.25:
                    props.append({"sets": {"InpSlUsd": v}, "label": "SlUsd", "from": g("InpSlUsd"), "to": f"{v:g}", "why": why, "group": "the stop"})
            else:
                props.append({"sets": {"InpSlMode": "2", "InpSlUsd": v}, "label": "Stop: a fixed $ from the entry", "from": now_stop, "to": f"${v:g} from the entry",
                              "why": why, "group": "the stop"})
        if slm == "1":                                       # the same line in ATR (the stop the EA uses in mode 1)
            ma = (mae / np.maximum(a_in, 0.01))[win]
            for pc in (95, 98):
                v = max(0.3, _up(_q(ma, pc), 0.1))
                if v < _f(base_in.get("InpSlAtrMult")) - 0.05:
                    props.append({"sets": {"InpSlAtrMult": v}, "label": "SlAtrMult", "from": g("InpSlAtrMult"), "to": f"{v:g}",
                                  "why": f"{pc}% of your winners never went more than {v:g} x ATR against you", "group": "the stop"})

    # ---- 3. time: winners are quick, losers linger
    hw, hl = held[win], held[los]
    if len(hw) >= 20:
        # q[pc] = a real holding time: at least pc% of the winners closed within it. A time rule of N candles first acts at the close of the
        # N-th candle after the entry candle, so a rule at N = q[pc] leaves those winners alone.
        q = {pc: int(np.percentile(hw, pc, method="higher")) for pc in (50, 75, 90, 95, 98)}
        late = float((hl > q[90]).mean())
        c_ = lambda v: f"{v} candle{'' if v == 1 else 's'}"  # noqa: E731
        out["facts"].append({"icon": "⏱️", "title": "How long trades stay open", "text":
                             f"Half your winners closed within {c_(q[50])} of the entry candle, 90% within {c_(q[90])}, 98% within {c_(q[98])}. Your losers stayed "
                             f"{c_(int(round(_q(hl, 50))))} (median) and {100 * late:.0f}% of them were still open after {c_(q[90])}, when 90% of the winners were already done."})
        if lab_ok:
            for pc in (95, 98):
                nb = max(1, q[pc])
                if lf("max_bars") == 0 or lf("max_bars") > nb:
                    props.append({"lab": {"max_bars": nb}, "label": "X: close after N candles", "from": f"{lf('max_bars'):g}" if lf("max_bars") else "off", "to": str(nb),
                                  "why": f"{pc}% of your winners closed within {q[pc]} candles; {100 * float((hl > q[pc]).mean()):.0f}% of the losers lasted longer",
                                  "group": "Exit Lab"})
            if lf("stale_bars") == 0:
                for pc in (75, 90):
                    nb = max(1, q[pc])
                    props.append({"lab": {"stale_bars": nb, "stale_r": 0.0}, "label": "X: out if not in profit after N candles", "from": "off", "to": str(nb),
                                  "why": f"{pc}% of your winners closed within {q[pc]} candles: a trade still in loss after that is mostly a loser",
                                  "group": "Exit Lab"})

    # ---- 4. losers that were in profit first
    fr = (mfe / R)[los]
    lv = [x for x in (0.1, 0.25, 0.5) if (fr >= x).mean() >= 0.2]
    if len(fr):
        out["facts"].append({"icon": "↩️", "title": "Losers that were in profit first", "text":
                             f"{100 * float((fr >= 0.1).mean()):.0f}% of your losers were at least +0.1R in profit before they lost, {100 * float((fr >= 0.25).mean()):.0f}% "
                             f"at least +0.25R, {100 * float((fr >= 0.5).mean()):.0f}% at least +0.5R (R = the distance to the first stop)."})
    if lab_ok and lf("be_r") == 0:
        for x in lv:
            props.append({"lab": {"be_r": x}, "label": "X: breakeven at +R", "from": "off", "to": f"{x:g}",
                          "why": f"{100 * float((fr >= x).mean()):.0f}% of your losers were +{x:g}R in profit before they lost", "group": "Exit Lab"})
    if lab_ok and lf("cx") == 0:                               # a reason to leave a LOSING trade before the stop
        for cm, nm in ((1, "a close back across the fast EMA"), (2, "a close back across the slow EMA"), (3, "the fast EMA crossing the slow"),
                       (4, "an opposite signal candle"), (5, "an engulfing candle against"), (6, "2 candles in a row closing against")):
            d = {"cx": cm, "cx_when": 2}
            if cm == 6:
                d["cx_n"] = 2
            props.append({"lab": d, "label": "X: leave a losing trade on", "from": "off", "to": nm + " (in loss only)",
                          "why": "cuts a trade that is in loss when the reason for it is gone, before it reaches the stop", "group": "Exit Lab"})

    # ---- 5. where the losses live
    min_n = max(15, int(0.03 * n))
    stop_q = np.percentile(R, [20, 40, 60, 80])
    atr_q = np.percentile(a_in, [20, 40, 60, 80])
    rows = []
    rows += _buckets("side", lambda k: "BUY" if k > 0 else "SELL", real[:, 0].astype(np.int64), p, S, min_n)
    rows += _buckets("hour", lambda k: f"setups at {k:02d}:00 server time (about {_pkt(k)} PKT)", hr, p, S, min_n)
    rows += _buckets("weekday", lambda k: DAYS[k], dow, p, S, min_n)
    rows += _buckets("candle", lambda k: KIND.get(int(k), "other"), kind, p, S, min_n)
    # fifths of the stop widths / of the ATR - only when they really differ (a fixed $ stop has one width: no buckets)
    stop_ok = bool(np.all(np.diff(stop_q) > 0.01) and float(stop_q[3] - stop_q[0]) > 0.05 * float(np.median(R)))
    atr_ok = bool(np.all(np.diff(atr_q) > 0.01))
    if stop_ok:
        sb = np.searchsorted(stop_q, R, side="right")
        edges = [round(float(R.min()), 2)] + [round(float(x), 2) for x in stop_q] + [round(float(R.max()), 2)]
        rows += _buckets("stop width", lambda k: f"stop ${edges[k]:g}-${edges[k + 1]:g}", sb, p, S, min_n)
    if atr_ok:
        ab = np.searchsorted(atr_q, a_in, side="right")
        aedges = [round(float(a_in.min()), 2)] + [round(float(x), 2) for x in atr_q] + [round(float(a_in.max()), 2)]
        rows += _buckets("volatility", lambda k: f"ATR ${aedges[k]:g}-${aedges[k + 1]:g}", ab, p, S, min_n)
    out["clusters"] = sorted(rows, key=lambda r: (not r["bad"], r["net"]))
    bad = sorted([r for r in rows if r["bad"]], key=lambda r: r["net"])
    if bad:
        sf, st_ = int(_f(base_in.get("InpSessFrom"), 0)), int(_f(base_in.get("InpSessTo"), 24))
        mid = [r for r in bad if r["dim"] == "hour" and sf < r["key"] < st_ - 1]
        out["facts"].append({"icon": "🗺️", "title": "Where the losses live", "text": "; ".join(
            f"{r['label']} ({r['dim']}): {r['n']} trades, WR {r['wr']}%, {_money(r['net'])}, margin {r['margin']} vs {r['rest_margin']} on the rest"
            for r in bad[:5]) + "." + (" No setting can skip an hour in the middle of the session (only its start and end)." if mid else "")})
    else:
        out["facts"].append({"icon": "🗺️", "title": "Where the losses live", "text":
                             "No side, hour, weekday, candle, stop width or volatility band loses money or stands far below the rest: the losses are spread out."})
    for r in bad:
        d, k = r["dim"], r["key"]
        why = f"{r['label']}: {r['n']} trades, WR {r['wr']}%, {_money(r['net'])} (margin {r['margin']} vs {r['rest_margin']} on the rest)"
        if d == "side":
            props.append({"sets": {"InpBuys" if k > 0 else "InpSells": "false"}, "label": "Buys" if k > 0 else "Sells", "from": "true", "to": "false", "why": why, "group": "filters"})
        elif d == "weekday" and 1 <= k <= 5:
            props.append({"sets": {"InpSkipDow": str(k)}, "label": "SkipDow", "from": g("InpSkipDow"), "to": str(k), "why": why, "group": "filters"})
        elif d == "candle" and k in KIND_SWITCH:
            key = KIND_SWITCH[k]
            props.append({"sets": {key: "false"}, "label": key[3:], "from": "true", "to": "false", "why": why, "group": "the candle"})
        elif d == "hour":
            sf, st_ = int(_f(base_in.get("InpSessFrom"), 0)), int(_f(base_in.get("InpSessTo"), 24))
            if k == sf and sf + 1 < st_:
                props.append({"sets": {"InpSessFrom": str(sf + 1)}, "label": "SessFrom", "from": str(sf), "to": str(sf + 1), "why": why, "group": "filters"})
            if k == st_ - 1 and st_ - 1 > sf:
                props.append({"sets": {"InpSessTo": str(st_ - 1)}, "label": "SessTo", "from": str(st_), "to": str(st_ - 1), "why": why, "group": "filters"})
        elif d == "stop width" and k == 4:
            v = _up(float(stop_q[3]), 0.5)
            props.append({"sets": {"InpMaxRiskUsd": v}, "label": "MaxRiskUsd", "from": g("InpMaxRiskUsd"), "to": f"{v:g}",
                          "why": why + " - skip setups whose stop is wider", "group": "the stop"})
        elif d == "volatility" and k == 4:
            v = _up(float(atr_q[3]), 0.5)
            props.append({"sets": {"InpAtrMaxUsd": v}, "label": "AtrMaxUsd", "from": g("InpAtrMaxUsd"), "to": f"{v:g}", "why": why, "group": "filters"})
        elif d == "volatility" and k == 0:
            v = round(math.floor(float(atr_q[0]) / 0.5) * 0.5, 4)
            if v > 0:
                props.append({"sets": {"InpAtrMinUsd": v}, "label": "AtrMinUsd", "from": g("InpAtrMinUsd"), "to": f"{v:g}", "why": why, "group": "filters"})

    # ---- 6. sizing: every trade risking the same $ (lots sized to the stop) - a what-if on the same trades, not a setting the scan moves
    if len(R) >= 20 and float(R.std()) > 0.05 * float(R.mean()):
        eq = p * (float(np.median(R)) / R)
        e = loss_stats(eq)
        out["facts"].append({"icon": "⚖️", "title": "If every trade risked the same $", "text":
                             f"Your stops range from ${_q(R, 5):.2f} to ${_q(R, 95):.2f} (5th to 95th percentile), so a fixed lot size makes the wide-stop trades your "
                             f"biggest losses. Sizing each trade to the same risk (the median stop's), on these same trades: average loss {_money(e['avg_loss'])}, "
                             f"worst {_money(e['worst'])}, break-even {e['be'] if e['be'] is not None else '–'}%, margin {e['margin'] if e['margin'] is not None else '–'} points "
                             f"(now {S['margin'] if S['margin'] is not None else '–'}). The EA does this with InpRiskPct (a % of the account, so it compounds): "
                             f"Mission Control sets the size."})
    return out
