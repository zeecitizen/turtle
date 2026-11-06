"""audit_robust.py - ADVERSARIAL robustness audit of every rule in rules_final.py (research/loss_study/final, 2026-11-06).

Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). This audit can only FAIL a rule; it can never promote one - only MT5's Strategy
Tester (or live fills) may promote. Every rule is re-implemented below with its thresholds as parameters; at the default parameters each copy
is ASSERTED to give exactly the original rule's mask with 0 exceptions, so a perturbation moves a threshold and nothing else.

VERDICT RULES - written down BEFORE any result of this script was looked at. A rule survives only if it meets every one:
  (0) PRE-ENTRY. A rule that reads t['fill'] (the first tick 0.3 s AFTER the decision) cannot be a pre-entry skip -> survives=false regardless.
  (i) DEFAULT passes the task bar: lift >= 2 on train AND on test (api.score's lift: loss rate among removed / the half's base rate),
      >= 4 losers removed, and >= 2 losers in EACH half (a half's lift resting on one loser does not count).
  (ii) PERTURBATION. Every one-at-a-time +-25% variant of every threshold keeps lift >= 2 on both halves. A half whose lift falls below 2 is a
      COLLAPSE when the variant removes enough trades there that, at the DEFAULT rule's own loss rate in that half, >= 2 losers would be
      expected; otherwise that half is THIN (too few trades to judge: reported, not a fail). One COLLAPSE fails (ii).
      What +-25% means: numeric thresholds x0.75 / x1.25; integer counts and look-backs x0.75 / x1.25 rounded; clock windows - each edge moved
      by 25% of the window LENGTH (rollover 16:45-17:45 NY -> start 16:30 / 17:00, end 17:30 / 18:00; Friday-from-16:00 -> 15:45 / 16:15;
      Friday-from-13:00 -> 12:00 / 14:00; US-data -90 s..+30 s -> start -120 / -60 s, end 0 / +60 s); a ratio capped at 1.0 (loud breakout,
      max observed 0.995) - 25% of the gap to 1.0 (0.875 / 0.925; the literal 0.675 / 1.125 are printed for information). Rules with no
      numeric threshold (holiday, zee_camel_hh): n/a - the date checks of (iv) stand in.
  (iii) MONTHS. The lift must not be carried by one or two months. Month-stratified O/E (observed losers / expected, expected = sum over months
      of the removed trades x the loss rate of that month - base rates run ~4% Mar-May and ~1.3% Jun-Nov; Nov folded into Oct) with the TWO
      months of largest excess (L - E) dropped must stay >= 2 with >= 4 losers left.
  (iv) DATES. The removed losers must not come mostly from one batch of dates: the top analyst batch (batches.json - 8 chronological stretches
      of the losses, one per analyst, i.e. the stretch a rule was mined from) holds <= 50% of them and O/E with the whole date span of that
      batch dropped stays >= 2; and O/E with the single busiest New-York day dropped stays >= 2.
Context only (never gates): the null scan of every 60-minute daily window, binomial tails per half, the stop-outs-only lifts from
scores_final.json, the increment of each rule beyond rule_combined, and the full two-knob grids.
Run (Git Bash): cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV/research/loss_study/final && py audit_robust.py
                -> prints everything, writes audit_robust.txt and audit_robust.json next to it."""
import datetime as dt
import itertools
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules_final as R  # noqa: E402

PIP = 1e-4
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


# ------------------------------------------------------------------ per-trade arrays: blind setup fields (rules) + outcomes (scoring only)
T, A, N = api.TRADES, api.A, len(api.TRADES)
BLIND = [api._blind(t) for t in T]
LOSS = np.array([not t["win"] for t in T])
TRAIN = np.array([t["t_in"] < api.SPLIT for t in T])
WHY = np.array([t["why"] for t in T])
PNL = np.array([t["pnl"] for t in T], dtype=float)
TIN = [t["t_in"] for t in T]
IDS = [t["id"] for t in T]
K = np.array([t["k"] for t in T], dtype=np.int64)
SIDE = np.array([t["side"] for t in T], dtype=float)
LEVEL = np.array([t["level"] for t in T], dtype=float)
FILL = np.array([t["fill"] for t in T], dtype=float)
BHI = np.array([t["brk_hi_so_far"] for t in T], dtype=float)
BLO = np.array([t["brk_lo_so_far"] for t in T], dtype=float)
BTK = np.array([t["brk_ticks_so_far"] for t in T], dtype=float)
UHVV = np.array([max(float(t["uhv_v"]), 1.0) for t in T])
CSTK = np.array([abs(int(t["camStk"])) for t in T])
SPR = np.array([R._trigger_spread(t["id"]) for t in T])
_CLK = [R.ny_clock(ts) for ts in TIN]
NYD = np.array([d for d, _ in _CLK])
NYM = np.array([m for _, m in _CLK])
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _ny_shift(ts):
    a, b = R._us_dst(dt.datetime.fromtimestamp(ts, R._UTC).year)
    return ts - (4 if a <= ts < b else 5) * 3600


DAY = np.array([int(_ny_shift(ts) // 86400) for ts in TIN])                     # New-York calendar day number
NYDATE = np.array([dt.datetime.fromtimestamp(_ny_shift(ts), R._UTC).strftime("%Y-%m-%d") for ts in TIN])
MON = np.array([dt.datetime.fromtimestamp(ts, R._UTC).strftime("%Y-%m") for ts in TIN])
MON[MON == "2026-11"] = "2026-10"                                               # 170 trades in Nov: folded into Oct
MONTHS = sorted(set(MON.tolist()))

_B = json.load(open(os.path.join(LS, "batches.json"), encoding="utf-8"))
_TIN_OF = dict(zip(IDS, TIN))
LOSS_BATCH = {c["id"]: b["batch"] for b in _B for c in b["losses"]}
_STARTS = np.array([min(_TIN_OF[c["id"]] for c in b["losses"]) for b in _B], dtype=float)
BATCH = np.maximum(np.searchsorted(_STARTS, np.array(TIN, dtype=float), side="right"), 1)    # each trade -> the batch whose span holds it
assert all(LOSS_BATCH[IDS[i]] == BATCH[i] for i in np.nonzero(LOSS)[0]), "batch spans do not reproduce batches.json"
BATCH_SPAN = {b["batch"]: (b["losses"][0]["entry_utc"][:10], b["losses"][-1]["entry_utc"][:10]) for b in _B}
BASE = {"train": LOSS[TRAIN].mean(), "test": LOSS[~TRAIN].mean(), "all": LOSS.mean()}
_SF = json.load(open(os.path.join(HERE, "scores_final.json"), encoding="utf-8"))["rules"]


def hm(m):
    return f"{int(m // 60):02d}:{int(round(m % 60)):02d}" if abs(m % 1) < 1e-9 else f"{int(m // 60):02d}:{m % 60:05.2f}"


# ------------------------------------------------------------------ every rule with its thresholds as parameters
def loop_mask(fn):
    m = np.zeros(N, bool)
    exc = 0
    for i, t in enumerate(BLIND):
        try:
            m[i] = bool(fn(t, A))
        except Exception:                       # noqa: BLE001  (api.score keeps a trade when a rule raises - so must we)
            exc += 1
    return m, exc


def m_rollover(start=16 * 60 + 45, end=17 * 60 + 45):
    return (NYM >= start) & (NYM < end)


def m_friday_from(start=16 * 60):
    return (NYD == 4) & (NYM >= start)


def m_trigger_spread(q=1.0):
    return SPR >= q - 1e-9


_CSV = np.concatenate([[0.0], np.cumsum(A.v)])


def m_empty_book(w=10, thr=20.0):
    return (_CSV[K + 1] - _CSV[K + 1 - w]) / w < thr                           # mean ticks of the last w CLOSED candles k-w+1 .. k


def m_trigger_gap(q=0.6):
    return (np.where(SIDE > 0, BHI, BLO) - LEVEL) * SIDE >= q * PIP - 1e-9


def m_fill_slip(q=1.5):
    return (FILL - LEVEL) * SIDE >= q * PIP - 1e-9


def m_buy_fill_spread(q=1.5):
    return (SIDE > 0) & (FILL - BHI >= q * PIP - 1e-9)


def m_big_figure(dmax=1.0):
    out = np.zeros(N, bool)
    g = 0.01
    for i in range(N):
        px, s = float(LEVEL[i]), SIDE[i]
        d = (math.ceil(px / g - 1e-9) * g - px) / PIP if s > 0 else (px - math.floor(px / g + 1e-9) * g) / PIP
        out[i] = 0.0 < d <= dmax
    return out


def m_camel_old(n=8):
    return CSTK >= n


def m_loud(r=0.9):
    return BTK >= r * UHVV


def m_holiday():
    return np.isin(NYDATE, sorted(R._HOLIDAYS))


def m_us_data(pre=90, post=30):
    s = NYM * 60.0
    hit = np.zeros(N, bool)
    for c in (8 * 60 + 30, 9 * 60 + 30, 10 * 60):
        dl = s - c * 60
        hit |= (dl >= -pre) & (dl <= post)
    return hit & (NYD <= 4)


def m_zee_camel_hh():
    return loop_mask(R.rule_zee_camel_hh)


def m_structure(look=120):
    def f(t, A_):
        hs, ls = A_.pivots(t["k"], 1, look)
        if len(hs) < 2 or len(ls) < 2:
            return False
        if t["side"] > 0:
            return not (hs[-1][1] > hs[-2][1] and ls[-1][1] > ls[-2][1])
        return not (ls[-1][1] < ls[-2][1] and hs[-1][1] < hs[-2][1])
    return loop_mask(f)


def m_near_sr(look=30, dist=1.0):
    def f(t, A_):
        hs, ls = A_.pivots(t["k"], 1, look)
        lev = t["level"]
        if t["side"] < 0:
            return any(b < t["ku"] and 0 <= (lev - p) / PIP <= dist for b, p in ls)
        return any(b < t["ku"] and 0 <= (p - lev) / PIP <= dist for b, p in hs)
    return loop_mask(f)


def m_counter_trend(look=90, mult=6.0):
    return (A.c[K] - A.c[K - look]) * SIDE < -mult * A.atr[K]


def m_exhausted_run(look=30, pips=8.0):
    return (A.c[K] - A.c[K - look]) * SIDE > pips * PIP


H = 60
ROLL = dict(fn=m_rollover, d=dict(start=16 * H + 45, end=17 * H + 45), k=dict(start=(16 * H + 30, 17 * H), end=(17 * H + 30, 18 * H)),
            clock=True, info={"offset +-25% (start -15 -> -11.25/-18.75 min, end +45 -> +33.75/+56.25 min)":
                              [dict(start=16 * H + 48.75), dict(start=16 * H + 41.25), dict(end=17 * H + 33.75), dict(end=17 * H + 56.25)]})
SPEC = {
    "rule_rollover_ny": ROLL,
    "rule_combined": ROLL,
    "rule_trigger_spread": dict(fn=m_trigger_spread, d=dict(q=1.0), k=dict(q=(0.75, 1.25))),
    "rule_friday_close_ny": dict(fn=m_friday_from, d=dict(start=16 * H), k=dict(start=(15 * H + 45, 16 * H + 15)), clock=True),
    "rule_empty_book": dict(fn=m_empty_book, d=dict(w=10, thr=20.0), k=dict(w=(8, 12), thr=(15.0, 25.0))),
    "rule_friday_afternoon_ny": dict(fn=m_friday_from, d=dict(start=13 * H), k=dict(start=(12 * H, 14 * H)), clock=True),
    "rule_trigger_gap": dict(fn=m_trigger_gap, d=dict(q=0.6), k=dict(q=(0.45, 0.75))),
    "rule_fill_slip": dict(fn=m_fill_slip, d=dict(q=1.5), k=dict(q=(1.125, 1.875))),
    "rule_buy_fill_spread": dict(fn=m_buy_fill_spread, d=dict(q=1.5), k=dict(q=(1.125, 1.875))),
    "rule_big_figure_ahead": dict(fn=m_big_figure, d=dict(dmax=1.0), k=dict(dmax=(0.75, 1.25))),
    "rule_camel_old": dict(fn=m_camel_old, d=dict(n=8), k=dict(n=(6, 10))),
    "rule_loud_breakout": dict(fn=m_loud, d=dict(r=0.9), k=dict(r=(0.875, 0.925)), info={"literal x0.75 / x1.25": [dict(r=0.675), dict(r=1.125)]}),
    "rule_holiday": dict(fn=m_holiday, d=dict(), k=dict()),
    "rule_us_data_minutes": dict(fn=m_us_data, d=dict(pre=90, post=30), k=dict(pre=(120, 60), post=(0, 60))),
    "rule_zee_camel_hh": dict(fn=m_zee_camel_hh, d=dict(), k=dict()),
    "rule_structure_hh_hl": dict(fn=m_structure, d=dict(look=120), k=dict(look=(90, 150))),
    "rule_near_sr": dict(fn=m_near_sr, d=dict(look=30, dist=1.0), k=dict(look=(22, 38), dist=(0.75, 1.25))),
    "rule_counter_trend": dict(fn=m_counter_trend, d=dict(look=90, mult=6.0), k=dict(look=(68, 112), mult=(4.5, 7.5))),
    "rule_exhausted_run": dict(fn=m_exhausted_run, d=dict(look=30, pips=8.0), k=dict(look=(22, 38), pips=(6.0, 10.0))),
}
assert set(SPEC) == {r.__name__ for r in R.ALL_RULES}, "SPEC must cover every rule in rules_final.ALL_RULES"
_CACHE = {}


def mask(name, **p):
    fn = SPEC[name]["fn"]
    key = (fn.__name__, tuple(sorted(p.items())))
    if key not in _CACHE:
        r = fn(**p)
        _CACHE[key] = r if isinstance(r, tuple) else (np.asarray(r, bool), 0)
    return _CACHE[key]


def plabel(name, p):
    clock = SPEC[name].get("clock")
    return ", ".join(f"{k}={hm(v) if clock and k in ('start', 'end') else v}" for k, v in p.items())


# ------------------------------------------------------------------ statistics
def halves(m):
    r = {}
    for nm, h in (("train", TRAIN), ("test", ~TRAIN), ("all", np.ones(N, bool))):
        mm = m & h
        n, L = int(mm.sum()), int((mm & LOSS).sum())
        r[nm] = {"n": n, "L": L, "W": n - L, "lift": round(L / n / BASE[nm], 2) if n else None}
    return r


def task_bar(r):
    return (r["all"]["L"] >= 4 and r["train"]["L"] >= 2 and r["test"]["L"] >= 2
            and (r["train"]["lift"] or 0) >= 2 and (r["test"]["lift"] or 0) >= 2)


def classify(rv, rd):
    """PASS / THIN / COLLAPSE of a variant against the default (verdict rule ii)"""
    st, why = "PASS", []
    for nm in ("train", "test"):
        v, d = rv[nm], rd[nm]
        if v["lift"] is not None and v["lift"] >= 2:
            if v["L"] < 2:
                st = "THIN" if st == "PASS" else st
                why.append(f"{nm} rests on {v['L']}L")
            continue
        exp = v["n"] * (d["L"] / d["n"] if d["n"] else 0.0)
        if exp >= 2:
            st = "COLLAPSE"
            why.append(f"{nm} x{v['lift']} where {exp:.1f}L were expected at the default rate")
        else:
            st = "THIN" if st == "PASS" else st
            why.append(f"{nm} x{v['lift']} on {v['n']} trades ({exp:.1f}L expected at the default rate)")
    if st == "PASS" and rv["all"]["L"] < 4:
        st = "THIN"
        why.append(f"{rv['all']['L']}L in all")
    return st, why


def hline(r):
    a, tr, te = r["all"], r["train"], r["test"]
    return f"{a['L']:3d}L/{a['W']:4d}W x{a['lift']} | train {tr['L']}L/{tr['W']}W x{tr['lift']} | test {te['L']}L/{te['W']}W x{te['lift']}"


def oe(m, keep=None):
    """month-stratified observed/expected losers among the removed; the base rate of each month from the KEPT trades of that month"""
    keep = np.ones(N, bool) if keep is None else keep
    O, E = 0, 0.0
    for mo in MONTHS:
        pop = keep & (MON == mo)
        if not pop.any():
            continue
        sel = m & pop
        O += int((sel & LOSS).sum())
        E += float(sel.sum()) * float(LOSS[pop].mean())
    return {"O": O, "E": round(E, 2), "oe": round(O / E, 2) if E > 0 else None}


def month_rows(m):
    rows = []
    for mo in MONTHS:
        pop = MON == mo
        base = float(LOSS[pop].mean())
        sel = m & pop
        n, L = int(sel.sum()), int((sel & LOSS).sum())
        rows.append({"month": mo, "n": n, "L": L, "E": round(n * base, 2), "base_pct": round(100 * base, 2),
                     "oe": round(L / (n * base), 2) if n else None})
    return rows


def binom_sf(L, n, p):
    if n == 0 or L <= 0:
        return 1.0
    lg = math.lgamma
    s = sum(math.exp(lg(n + 1) - lg(x + 1) - lg(n - x + 1) + x * math.log(p) + (n - x) * math.log1p(-p)) for x in range(L, n + 1))
    return min(1.0, s)


def _oekey(x):
    return x["oe"] if x["oe"] is not None else 9e9


# ------------------------------------------------------------------ the audit
say("=" * 150)
say("audit_robust.py - ADVERSARIAL robustness audit of rules_final.py. Python tick replay = HYPOTHESIS, NOT PROMOTED (an audit can only FAIL a rule).")
say(f"{N} trades, {int(LOSS.sum())} losses; base loss rate all {100 * BASE['all']:.2f}% train {100 * BASE['train']:.2f}% test {100 * BASE['test']:.2f}%")
say("months (Nov folded into Oct): " + "  ".join(f"{r['month']} {r['n']}tr {r['L']}L {r['base_pct']}%" for r in month_rows(np.ones(N, bool))))
say("analyst batches (chronological stretches of the losses): " + "  ".join(f"B{b} {s[5:]}..{e[5:]}" for b, (s, e) in BATCH_SPAN.items()))
say("=" * 150)

COMB, _ = mask("rule_combined", **SPEC["rule_combined"]["d"])
RES = {}
for rule in R.ALL_RULES:
    nm = rule.__name__
    spec = SPEC[nm]
    status = ("ACCEPTED" if rule in R.ACCEPTED else "COMBINED" if rule is R.rule_combined else "CANDIDATE" if rule in R.CANDIDATES else "REJECTED")
    kind = "fill-time" if rule in R.FILL_TIME else "extended-field" if rule in R.EXTENDED else "pre-entry"
    orig, exc_o = loop_mask(rule)
    md, exc_d = mask(nm, **spec["d"])
    assert exc_o == 0 and exc_d == 0, f"{nm}: exceptions {exc_o} / {exc_d}"
    assert np.array_equal(orig, md), f"{nm}: the parameterised copy differs from rules_final at the default"
    rd = halves(md)
    say(f"\n#### {nm}  [{status} | {kind}]   parameterised copy == rules_final at default: yes (0 exceptions)   default: {plabel(nm, spec['d']) or 'no threshold'}")
    v1 = task_bar(rd)
    say(f" (i)   default  {hline(rd)}  -> task bar {'PASS' if v1 else 'FAIL'}")

    # (ii) perturbation
    var_rows, collapse = [], []
    if spec["k"]:
        for knob, vals in spec["k"].items():
            for v in vals:
                p = dict(spec["d"])
                p[knob] = v
                mv, ev = mask(nm, **p)
                rv = halves(mv)
                st, why = classify(rv, rd)
                var_rows.append({"params": plabel(nm, p), "stats": rv, "status": st, "why": why, "exceptions": ev})
                if st == "COLLAPSE":
                    collapse.append(plabel(nm, p))
                say(f" (ii)  {plabel(nm, p):38s} {hline(rv)}  {st}{'  (' + '; '.join(why) + ')' if why else ''}")
    else:
        say(" (ii)  n/a - no numeric threshold; the date checks of (iv) stand in")
    for lab, plist in spec.get("info", {}).items():
        for q in plist:
            p = dict(spec["d"])
            p.update(q)
            rv = halves(mask(nm, **p)[0])
            st, why = classify(rv, rd)
            say(f"   info [{lab}] {plabel(nm, p):30s} {hline(rv)}  {st}")
    grid = []
    if len(spec["k"]) == 2:
        (k1, a1), (k2, a2) = spec["k"].items()
        for x1, x2 in itertools.product((a1[0], spec["d"][k1], a1[1]), (a2[0], spec["d"][k2], a2[1])):
            p = dict(spec["d"])
            p[k1], p[k2] = x1, x2
            rv = halves(mask(nm, **p)[0])
            grid.append({"params": plabel(nm, p), "status": classify(rv, rd)[0], "train_lift": rv["train"]["lift"], "test_lift": rv["test"]["lift"],
                         "L": rv["all"]["L"]})
        say("   info [full 3x3 grid] " + " | ".join(f"{g['params']}: {g['L']}L x{g['train_lift']}/x{g['test_lift']} {g['status']}" for g in grid))
    v2 = not collapse
    say(f"       -> (ii) {'no collapse' if v2 else 'COLLAPSE at ' + '; '.join(collapse)}")

    # (iii) months
    mrows = month_rows(md)
    tot = oe(md)
    say(" (iii) months  " + "  ".join(f"{r['month'][2:]}: {r['L']}L/{r['n']}tr E{r['E']}" for r in mrows) + f"   | stratified O/E {tot['O']}/{tot['E']} = x{tot['oe']}")
    ex = sorted(mrows, key=lambda r: (-(r["L"] - r["E"]), -r["L"]))
    top2 = [r["month"] for r in ex[:2]]
    d2 = oe(md, ~np.isin(MON, top2))
    lomo = min(((mo, oe(md, MON != mo)) for mo in MONTHS), key=lambda x: _oekey(x[1]))
    pairs = [((a, b), oe(md, ~np.isin(MON, [a, b]))) for a, b in itertools.combinations(MONTHS, 2)]
    wp = min(pairs, key=lambda x: _oekey(x[1]))
    months_with_L = sum(1 for r in mrows if r["L"] > 0)
    v3 = d2["oe"] is not None and d2["oe"] >= 2 and d2["O"] >= 4
    say(f"       top-2 excess months {top2} dropped -> O/E {d2['O']}/{d2['E']} = x{d2['oe']} ({d2['O']}L left)  | worst single drop {lomo[0]} "
        f"-> x{lomo[1]['oe']} | worst pair {wp[0]} -> x{wp[1]['oe']} ({wp[1]['O']}L left) | months with a loser removed: {months_with_L} of {len(MONTHS)}"
        f"  -> (iii) {'PASS' if v3 else 'FAIL'}")

    # (iv) dates
    sel = md & LOSS
    Lb = {b: int((sel & (BATCH == b)).sum()) for b in range(1, 9)}
    totL = int(sel.sum())
    bdrop = {b: oe(md, BATCH != b) for b in range(1, 9)}
    topb = max(range(1, 9), key=lambda b: (Lb[b], -_oekey(bdrop[b])))
    share = Lb[topb] / totL if totL else 1.0
    if totL:
        days, cnt = np.unique(DAY[sel], return_counts=True)
        cand = [d for d, c in zip(days, cnt) if c == cnt.max()]
        ddrop = {d: oe(md, DAY != d) for d in cand}
        topd = min(cand, key=lambda d: _oekey(ddrop[d]))
        topd_n, topd_oe = int(cnt.max()), ddrop[topd]
        topd_s = str(NYDATE[np.nonzero(DAY == topd)[0][0]])
    else:
        days = np.array([], int)
        topd_n, topd_oe, topd_s = 0, {"O": 0, "E": 0, "oe": None}, "-"
    v4 = (totL > 0 and share <= 0.5 and bdrop[topb]["oe"] is not None and bdrop[topb]["oe"] >= 2
          and topd_oe["oe"] is not None and topd_oe["oe"] >= 2)
    say(f" (iv)  losers by batch {Lb} | top batch B{topb} {BATCH_SPAN[topb][0][5:]}..{BATCH_SPAN[topb][1][5:]} holds {Lb[topb]}/{totL} = {100 * share:.0f}%"
        f" -> O/E without it {bdrop[topb]['O']}/{bdrop[topb]['E']} = x{bdrop[topb]['oe']} | {len(days)} distinct NY days, busiest {topd_s} ({topd_n}L)"
        f" -> O/E without it x{topd_oe['oe']}  -> (iv) {'PASS' if v4 else 'FAIL'}")

    # context
    btr = binom_sf(rd["train"]["L"], rd["train"]["n"], BASE["train"])
    bte = binom_sf(rd["test"]["L"], rd["test"]["n"], BASE["test"])
    so = _SF.get(nm, {}).get("stop_only", {})
    inc = halves(md & ~COMB)
    say(f"   ctx binomial P(>=L | n, half base): train {btr:.2g}  test {bte:.2g} | stop-outs only (scores_final.json): {so.get('L')}L train x{so.get('train_lift')}"
        f" ({so.get('train_L')}L) test x{so.get('test_lift')} ({so.get('test_L')}L) | beyond rule_combined: {hline(inc)} {'PASS' if task_bar(inc) else 'fail'}")
    lst = []
    for i in np.nonzero(sel)[0]:
        d_, m_ = _CLK[i]
        lst.append(f"{IDS[i]}(NY {NYDATE[i][5:]} {WD[d_]} {hm(int(m_))} B{BATCH[i]} "
                   f"{'stop' if WHY[i] == 1 else 'wk-close' if WHY[i] == 8 else WHY[i]} {PNL[i]:+.0f}$)")
    if len(lst) <= 30:
        say("   losers removed: " + ", ".join(lst))
    else:
        say(f"   losers removed: {len(lst)} (list omitted)")

    reasons = []
    if kind == "fill-time":
        reasons.append("(0) reads t['fill'] - not a pre-entry skip")
    if not v1:
        reasons.append("(i) default fails the task bar")
    if not v2:
        reasons.append("(ii) collapses at " + "; ".join(collapse))
    if not v3:
        reasons.append(f"(iii) top-2 months {top2} dropped -> x{d2['oe']} with {d2['O']}L")
    if not v4:
        reasons.append(f"(iv) top batch B{topb} {100 * share:.0f}% (O/E without x{bdrop[topb]['oe']}), busiest day {topd_s} (O/E without x{topd_oe['oe']})")
    surv = not reasons
    say(f" VERDICT {nm}: {'SURVIVES the audit (MT5 candidate, NOT PROMOTED)' if surv else 'FAILS: ' + ' | '.join(reasons)}")
    RES[nm] = {"status": status, "kind": kind, "default": rd, "task_bar": v1, "variants": var_rows, "grid": grid, "collapse": collapse,
               "months": mrows, "oe_all": tot, "top2_months": top2, "oe_without_top2": d2, "worst_single_month_drop": [lomo[0], lomo[1]],
               "worst_pair_drop": [list(wp[0]), wp[1]], "months_with_loser": months_with_L, "losers_by_batch": Lb, "top_batch": int(topb),
               "top_batch_share": round(share, 3), "oe_without_top_batch": bdrop[topb], "distinct_days": int(len(days)), "busiest_day": topd_s,
               "busiest_day_L": topd_n, "oe_without_busiest_day": topd_oe, "binom_train": btr, "binom_test": bte, "stop_only": so,
               "beyond_combined": inc, "checks": {"pre_entry": kind != "fill-time", "i": v1, "ii": v2 if spec["k"] else "n/a", "iii": v3, "iv": v4},
               "survives": surv, "reasons": reasons}

# ------------------------------------------------------------------ context: re-derive the rollover plateau, and the null scan of clock windows
say("\n" + "=" * 150)
say("CONTEXT (never gates)")
say("=" * 150)
say("rollover plateau claimed in rules_final (start 16:00-16:45 x end 17:30-18:30, 15-min steps), re-derived:")
plat = []
for s in (16 * H, 16 * H + 15, 16 * H + 30, 16 * H + 45):
    for e in (17 * H + 30, 17 * H + 45, 18 * H, 18 * H + 15, 18 * H + 30):
        r = halves(m_rollover(s, e))
        plat.append((hm(s), hm(e), task_bar(r)))
        say(f"   {hm(s)}-{hm(e)}  {hline(r)}  {'PASS' if task_bar(r) else 'fail'}")
say(f"   -> {sum(p[2] for p in plat)} of {len(plat)} pass the task bar")
say("slices of the rollover window:")
for s, e in ((16 * H + 30, 16 * H + 45), (16 * H + 45, 17 * H), (17 * H, 17 * H + 30), (17 * H + 30, 17 * H + 45), (17 * H + 45, 18 * H)):
    say(f"   {hm(s)}-{hm(e)}  {hline(halves(m_rollover(s, e)))}")
say("null scan - every 60-minute New-York window at 15-minute steps, all weekdays (96 windows): which pass the task bar?")
scan = []
for s in range(0, 24 * H, 15):
    e = s + 60
    mm = ((NYM >= s) & (NYM < e)) if e <= 24 * H else ((NYM >= s) | (NYM < e - 24 * H))
    r = halves(mm)
    if task_bar(r):
        scan.append(f"{hm(s)}-{hm(e % (24 * H))} ({r['all']['L']}L x{r['train']['lift']}/x{r['test']['lift']})")
say(f"   {len(scan)} of 96 pass: " + ", ".join(scan))
say("null scan - every 60-minute window on FRIDAYS only, 15-minute steps (96 windows):")
scanf = []
for s in range(0, 24 * H, 15):
    e = s + 60
    mm = (NYD == 4) & (((NYM >= s) & (NYM < e)) if e <= 24 * H else ((NYM >= s) | (NYM < e - 24 * H)))
    r = halves(mm)
    if task_bar(r):
        scanf.append(f"{hm(s)}-{hm(e % (24 * H))} ({r['all']['L']}L x{r['train']['lift']}/x{r['test']['lift']})")
say(f"   {len(scanf)} of 96 pass: " + ", ".join(scanf))
say("rollover window by weekday (Mon..Fri):")
for d in range(5):
    say(f"   {WD[d]}  {hline(halves(COMB & (NYD == d)))}")
say("trigger spread sweep (information):")
for q in (0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25, 1.5, 2.0, 3.0):
    r = halves(m_trigger_spread(q))
    say(f"   >= {q:<4}  {hline(r)}  {'PASS' if task_bar(r) else 'fail'}")
say("Friday-close start sweep (information):")
for s in range(14 * H, 16 * H + 46, 15):
    r = halves(m_friday_from(s))
    say(f"   Fri from {hm(s)}  {hline(r)}  {'PASS' if task_bar(r) else 'fail'}")
say("empty-book sweep (information): window x threshold -> L, train lift / test lift, P(ass)/f(ail)")
for w in (5, 8, 10, 12, 15, 20):
    cells = []
    for thr in (10, 15, 20, 25, 30):
        r = halves(m_empty_book(w, thr))
        cells.append(f"<{thr}: {r['all']['L']}L x{r['train']['lift']}/x{r['test']['lift']} {'P' if task_bar(r) else 'f'}")
    say(f"   w={w:<2d} " + " | ".join(cells))

# ------------------------------------------------------------------ supplementary (context, never gates): survivors on stop-outs only, by side, by weekday
POP_STOP = ~(LOSS & (WHY == 8))


def halves_pop(m, pop):
    """halves() inside a sub-population, against that sub-population's own base rate per half"""
    r = {}
    for nm, h in (("train", TRAIN), ("test", ~TRAIN), ("all", np.ones(N, bool))):
        P = pop & h
        base = float(LOSS[P].mean()) if P.any() else 0.0
        mm = m & P
        n, L = int(mm.sum()), int((mm & LOSS).sum())
        r[nm] = {"n": n, "L": L, "W": n - L, "lift": round(L / n / base, 2) if n and base else None}
    return r


say("\n" + "=" * 150)
say("SUPPLEMENTARY (context, never gates): each survivor on STOP-OUTS ONLY (the 21 weekly-close flattens, why=8, dropped from the base and the"
    " removed), by side, and not-Friday vs Friday - each against that group's own base rate")
say("=" * 150)
SUPP = {}
for nm, r in RES.items():
    if not r["survives"]:
        continue
    md = mask(nm, **SPEC[nm]["d"])[0]
    so = halves_pop(md, POP_STOP)
    mrow = []
    for mo in MONTHS:
        pop = POP_STOP & (MON == mo)
        sel = md & pop
        mrow.append((mo, int((sel & LOSS).sum()), float(sel.sum()) * float(LOSS[pop].mean())))
    top2 = [x[0] for x in sorted(mrow, key=lambda x: (-(x[1] - x[2]), -x[1]))[:2]]
    d2 = oe(md, POP_STOP & ~np.isin(MON, top2))
    sel = md & LOSS & POP_STOP
    Lb = {b: int((sel & (BATCH == b)).sum()) for b in range(1, 9) if (sel & (BATCH == b)).any()}
    nd = len(set(DAY[sel].tolist()))
    say(f"{nm:26s} stop-outs only {hline(so)} {'PASS' if task_bar(so) else 'fail'} | O/E {oe(md, POP_STOP)['oe']} | top-2 months {top2} out -> "
        f"x{d2['oe']} ({d2['O']}L) | {nd} days | batches {Lb}")
    SUPP[nm] = {"stop_only": so, "stop_only_pass": task_bar(so), "stop_only_top2_out": d2, "stop_only_days": nd, "stop_only_batches": Lb}
    for lab, sub in (("buys", SIDE > 0), ("sells", SIDE < 0), ("not Friday", NYD != 4), ("Friday", NYD == 4)):
        rr = halves_pop(md, sub)
        rs = halves_pop(md, sub & POP_STOP)
        say(f"   {lab:10s} all losses {hline(rr)} {'PASS' if task_bar(rr) else 'fail'}   || stop-outs only {hline(rs)} {'PASS' if task_bar(rs) else 'fail'}")
        SUPP[nm][lab] = {"all": rr, "stop_only": rs}

# ------------------------------------------------------------------ verdict table
say("\n" + "=" * 150)
say("VERDICTS  (survivor = MT5 candidate, NOT PROMOTED; Python can only fail a rule)")
say("=" * 150)
for nm, r in RES.items():
    c = r["checks"]
    c2 = ("Y" if c["ii"] else "N") if SPEC[nm]["k"] else "n/a"
    say(f"{nm:28s} {'SURVIVES' if r['survives'] else 'fails   '}  pre-entry {'Y' if c['pre_entry'] else 'N'} (i) {'Y' if c['i'] else 'N'} (ii) {c2:3s}"
        f" (iii) {'Y' if c['iii'] else 'N'} (iv) {'Y' if c['iv'] else 'N'}  | default x{r['default']['train']['lift']}/x{r['default']['test']['lift']} "
        f"{r['default']['all']['L']}L | top-2-months-out x{r['oe_without_top2']['oe']} ({r['oe_without_top2']['O']}L) | top batch {100 * r['top_batch_share']:.0f}%")
json.dump({"results": RES, "plateau": plat, "null_scan_all_days": scan, "null_scan_fridays": scanf, "supplementary_survivors": SUPP},
          open(os.path.join(HERE, "audit_robust.json"), "w", encoding="utf-8"), indent=1, default=str)
open(os.path.join(HERE, "audit_robust.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
say("\nwrote audit_robust.txt and audit_robust.json")
