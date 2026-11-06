"""score_final.py - re-scores every rule in rules_final.py with api.report (nothing is taken from the analysts' pasted numbers), audits them,
derives rule_combined greedily and checks it equals rules_final.ACCEPTED. Writes scores_final.txt (everything printed) and scores_final.json.

  1. exceptions: every rule over every blind trade; api.score silently KEEPS a trade when a rule raises, so 0 exceptions are required
  2. look-ahead audit: every rule re-run with all per-bar arrays CUT at bar k (and humps known by k); 0 changed decisions required
  3. api.report line for every rule (the official numbers) + losers on distinct New York days + stop-outs-only lift (the 21 weekly-close
     flattens, why=8, dropped from both the base and the removed set)
  4. greedy union: forward - add the harness-native pre-entry rule whose INCREMENT (trades not yet skipped) passes the strict bar and adds
     the most losers; backward - drop any rule whose UNIQUE contribution (beyond all the others) no longer passes. Repeat. The strict bar:
     lift >= 2 on train AND test, >= 4 losers, >= 2 losers in EACH half, losers on >= 4 distinct days. Fill-time rules never enter; the
     extended-field rule may enter only after, if its increment passes at its threshold AND at the next stricter one.
  5. rule_combined: report, stop-outs only, what it adds beyond the engine's InpUhvNoClose band (20:45-21:15 UTC), Zee's tagged losses,
     and the doctrine.python_says haircut block (CLAUDE.md: the only sanctioned way to quote a Python win rate).
Python tick replay = HYPOTHESIS, NOT PROMOTED. Run (Git Bash): py research/loss_study/final/score_final.py"""
import contextlib
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules_final as R  # noqa: E402
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(LS))))     # turtle/monitor, for doctrine.py - appended, so it cannot shadow api

OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    OUT.append(s)


T = api.TRADES
A = api.A
N = len(T)
BLIND = [api._blind(t) for t in T]
LOSS = np.array([not t["win"] for t in T])
TRAIN = np.array([t["t_in"] < api.SPLIT for t in T])
WHY = np.array([t["why"] for t in T])
PNL = np.array([t["pnl"] for t in T])


def ny_day(ts):
    a, b = R._us_dst(R.dt.datetime.fromtimestamp(ts, R._UTC).year)
    return int((ts - (4 if a <= ts < b else 5) * 3600) // 86400)


DAY = np.array([ny_day(t["t_in"]) for t in T])
BASE = {"train": LOSS[TRAIN].mean(), "test": LOSS[~TRAIN].mean(), "all": LOSS.mean()}
STOP_POP = ~(LOSS & (WHY == 8))
BASE_STOP = {"train": LOSS[STOP_POP & TRAIN].mean(), "test": LOSS[STOP_POP & ~TRAIN].mean()}


# ------------------------------------------------------------------------------------------ 1 + 2: exceptions and look-ahead audit
class Cut:
    """A with every per-bar array cut at bar k (a view, no copy) and only the humps known by k: a rule that reads k+1 raises or changes."""
    PER_BAR = ("t", "o", "h", "l", "c", "v", "atr", "adx", "camEff", "camStk", "camT", "camHV", "camLV", "camL0V")

    def __init__(self, k):
        for nm in self.PER_BAR:
            setattr(self, nm, getattr(A, nm)[:k + 1])
        self.humps = A.humps[:int(np.searchsorted(HK, k, side="right"))] if len(A.humps) else A.humps     # a view: humps known by k
        self.PIP = A.PIP

    def pivots(self, k, p=1, look=120):
        h, l = self.h, self.l
        hs, ls = [], []
        for j in range(max(p, k - look), k - p + 1):
            if all(h[j] >= h[j - d] and h[j] >= h[j + d] for d in range(1, p + 1)):
                hs.append((j, float(h[j])))
            if all(l[j] <= l[j - d] and l[j] <= l[j + d] for d in range(1, p + 1)):
                ls.append((j, float(l[j])))
        return hs, ls

    def humps_known(self, k):
        H = self.humps
        return H[H[:, 7] <= k] if len(H) else H


HK = A.humps[:, 7] if len(A.humps) else np.zeros(0)
assert np.all(np.diff(HK) >= 0), "humps are not ordered by known_at_bar"


def evaluate(rule):
    m = np.zeros(N, bool)
    exc = diff = 0
    for i, t in enumerate(BLIND):
        try:
            full = bool(rule(t, A))
        except Exception:                                   # noqa: BLE001
            exc += 1
            full = False
        try:
            cut = bool(rule(t, Cut(t["k"])))
        except Exception:                                   # noqa: BLE001
            cut = None
        if cut is None or cut != full:
            diff += 1
        m[i] = full
    return m, exc, diff


# ------------------------------------------------------------------------------------------ stats helpers
def half_stats(m, pop=None, base=None):
    pop = np.ones(N, bool) if pop is None else pop
    base = base or BASE
    r = {}
    for nm, h in (("train", TRAIN), ("test", ~TRAIN)):
        mm = m & pop & h
        n, L = int(mm.sum()), int((mm & LOSS).sum())
        r[nm] = {"L": L, "W": n - L, "lift": round(L / n / base[nm], 2) if n else None}
    mm = m & pop
    n, L = int(mm.sum()), int((mm & LOSS).sum())
    r["all"] = {"L": L, "W": n - L, "lift": round(L / n / BASE["all"], 2) if n else None}
    r["days"] = len(set(DAY[mm & LOSS].tolist()))
    return r


def passes(r):
    tr, te = r["train"], r["test"]
    return (r["all"]["L"] >= 4 and tr["L"] >= 2 and te["L"] >= 2 and (tr["lift"] or 0) >= 2 and (te["lift"] or 0) >= 2 and r["days"] >= 4)


def line(name, r):
    a, tr, te = r["all"], r["train"], r["test"]
    return (f"{name:42s} {a['L']:3d}L/{a['W']:4d}W x{a['lift']} | train {tr['L']}L/{tr['W']}W x{tr['lift']} | test {te['L']}L/{te['W']}W x{te['lift']}"
            f" | {r['days']} days | {'PASS' if passes(r) else 'fail'}")


# ------------------------------------------------------------------------------------------ run every rule
say("=" * 150)
say("score_final.py - every rule of rules_final.py re-scored with api.report. Python tick replay = HYPOTHESIS, NOT PROMOTED.")
say(f"{N} trades, {int(LOSS.sum())} losses; base loss rate all {100 * BASE['all']:.2f}% train {100 * BASE['train']:.2f}% test {100 * BASE['test']:.2f}%;"
    f" api.TAGGED (Zee's commented losses) = {len(api.TAGGED)} entries (the report column still says 'Zee's 22')")
say("=" * 150)
MASK, INFO = {}, {}
for rule in R.ALL_RULES:
    nm = rule.__name__
    m, exc, diff = evaluate(rule)
    MASK[nm] = m
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rep = api.report(rule, nm)
    rep_line = buf.getvalue().rstrip()
    hs = half_stats(m)
    so = half_stats(m, STOP_POP, BASE_STOP)
    status = ("ACCEPTED" if rule in R.ACCEPTED else "COMBINED" if rule is R.rule_combined else "CANDIDATE" if rule in R.CANDIDATES else "REJECTED")
    kind = "fill-time" if rule in R.FILL_TIME else "extended-field" if rule in R.EXTENDED else "pre-entry"
    INFO[nm] = {"status": status, "kind": kind, "exceptions": exc, "lookahead_diffs": diff, "api_report": rep_line,
                "lift_all": rep["all"]["lift"], "lift_train": rep["train"]["lift"], "lift_test": rep["test"]["lift"],
                "losers_removed": rep["all"]["losers_removed"], "winners_removed": rep["all"]["winners_removed"],
                "wr_after": rep["all"]["wr_after"], "net_change_usd_1lot": rep["all"]["net_change_usd_1lot"], "zee_tagged_removed": rep["tagged_out"],
                "train_L": rep["train"]["losers_removed"], "test_L": rep["test"]["losers_removed"], "days": hs["days"], "passes_strict": passes(hs),
                "stop_only": {"L": so["all"]["L"], "train_lift": so["train"]["lift"], "test_lift": so["test"]["lift"], "train_L": so["train"]["L"],
                              "test_L": so["test"]["L"]}}
    say(f"[{status:9s}|{kind:14s}] exc {exc} look-ahead diffs {diff} | {rep_line}")
    say(f"{'':28s} distinct loser days {hs['days']} | strict bar {'PASS' if passes(hs) else 'fail'} | stop-outs only (why=1): {so['all']['L']}L "
        f"train x{so['train']['lift']} ({so['train']['L']}L) test x{so['test']['lift']} ({so['test']['L']}L)")
bad = {k: (v["exceptions"], v["lookahead_diffs"]) for k, v in INFO.items() if v["exceptions"] or v["lookahead_diffs"]}
say(f"\nAUDIT: rules with exceptions or look-ahead diffs: {bad if bad else 'none'}")

# ------------------------------------------------------------------------------------------ 4: greedy union (forward + backward)
say("\n" + "=" * 150)
say("GREEDY UNION - pool = harness-native pre-entry rules (fill-time and extended-field rules excluded); strict bar on increments")
say("=" * 150)
pool = [r for r in R.ACCEPTED + R.CANDIDATES + R.REJECTED if r not in R.FILL_TIME and r not in R.EXTENDED]
U, step, LOG = [], 0, []


def union_mask(rules):
    m = np.zeros(N, bool)
    for r in rules:
        m |= MASK[r.__name__]
    return m


while True:
    step += 1
    taken = union_mask(U)
    rows = []
    for r in pool:
        if r in U:
            continue
        inc = half_stats(MASK[r.__name__] & ~taken)
        rows.append((r, inc))
    rows.sort(key=lambda x: (-x[1]["all"]["L"], x[1]["all"]["W"]))
    say(f"\n-- step {step}: increments beyond {[r.__name__ for r in U] or 'nothing'}")
    for r, inc in rows:
        say("   " + line(r.__name__, inc))
    ok = [(r, inc) for r, inc in rows if passes(inc)]
    if not ok:
        say("   -> no candidate passes: stop")
        break
    best, inc = max(ok, key=lambda x: (x[1]["all"]["L"], min(x[1]["train"]["lift"], x[1]["test"]["lift"])))
    U.append(best)
    say(f"   -> ADD {best.__name__}")
    LOG.append({"step": step, "add": best.__name__, "increment": inc})
    while True:                                                          # backward: every member's UNIQUE contribution must still pass
        weak = []
        for r in U:
            uniq = half_stats(MASK[r.__name__] & ~union_mask([x for x in U if x is not r]))
            say("      unique " + line(r.__name__, uniq))
            if not passes(uniq):
                weak.append((uniq["all"]["L"], r))
        if not weak:
            break
        _, drop = min(weak, key=lambda x: x[0])
        U.remove(drop)
        pool.remove(drop)
        say(f"   <- DROP {drop.__name__} (its unique contribution fails the strict bar)")
        LOG.append({"step": step, "drop": drop.__name__})
say(f"\nGREEDY RESULT: {[r.__name__ for r in U]}   rules_final.ACCEPTED: {[r.__name__ for r in R.ACCEPTED]}")
assert [r.__name__ for r in U] == [r.__name__ for r in R.ACCEPTED], "rules_final.ACCEPTED is out of date - update it"

# the extended-field step: the breakout-tick spread, only as an increment beyond the harness union, with a threshold-robustness check
say("\n-- extended field (breakout-tick spread, pre-entry but not a harness field): increment beyond rule_combined by threshold")
spr = np.array([R._trigger_spread(t["id"]) for t in T])
comb = union_mask(U)
EXT = {}
for q in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 2.0, 3.0):
    inc = half_stats((spr >= q - 1e-9) & ~comb)
    EXT[q] = inc
    say("   " + line(f"trigger spread >= {q} beyond combined", inc))
ok_ext = passes(EXT[1.0]) and passes(EXT[1.2])
say(f"   -> rule_trigger_spread (1.0) {'ENTERS' if ok_ext else 'does NOT enter'} rule_combined: increment at 1.0 "
    f"{'passes' if passes(EXT[1.0]) else 'fails'}, at the next stricter 1.2 {'passes' if passes(EXT[1.2]) else 'fails'}")
ext_union = half_stats(comb | (spr >= 1.0 - 1e-9))
say("   " + line("for reference: rule_combined OR spread >= 1.0", ext_union))
say("   losers the spread guard adds beyond rule_combined (spread >= 1.0):")
for i in np.nonzero((spr >= 1.0 - 1e-9) & ~comb & LOSS)[0]:
    d, mm = R.ny_clock(T[i]["t_in"])
    say(f"      {T[i]['id']}  NY {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d]} {int(mm // 60):02d}:{int(mm % 60):02d}  spread {spr[i]:.1f} pip  "
        f"pnl {T[i]['pnl']:+.0f}$  exit {'stop' if T[i]['why'] == 1 else 'weekly-close flatten' if T[i]['why'] == 8 else T[i]['why']}")

say("\n-- fill-time guards (execution side, read t['fill']): increment beyond rule_combined")
for r in R.FILL_TIME:
    say("   " + line(r.__name__ + " beyond combined", half_stats(MASK[r.__name__] & ~comb)))
say("\n-- candidates and rejected rules: increment beyond rule_combined")
INC = {}
for r in R.CANDIDATES + R.REJECTED:
    inc = half_stats(MASK[r.__name__] & ~comb)
    INC[r.__name__] = inc
    INFO[r.__name__]["beyond_combined"] = {"L": inc["all"]["L"], "W": inc["all"]["W"], "train_lift": inc["train"]["lift"],
                                           "test_lift": inc["test"]["lift"], "train_L": inc["train"]["L"], "test_L": inc["test"]["L"],
                                           "days": inc["days"], "passes": passes(inc)}
    say("   " + line(r.__name__, inc))

# ------------------------------------------------------------------------------------------ 5: rule_combined
say("\n" + "=" * 150)
say("RULE_COMBINED")
say("=" * 150)
cm = MASK["rule_combined"]
say(INFO["rule_combined"]["api_report"])
so = half_stats(cm, STOP_POP, BASE_STOP)
say(f"stop-outs only (why=1): {so['all']['L']}L/{so['all']['W']}W train x{so['train']['lift']} ({so['train']['L']}L) test x{so['test']['lift']} ({so['test']['L']}L), "
    f"{so['days']} days; weekly-close flattens among its losers: {int((cm & LOSS & (WHY == 8)).sum())} of {int((LOSS & (WHY == 8)).sum())}")
band = np.array([74700 <= t["t_in"] % 86400 <= 76500 for t in T])
say(line("beyond the engine's InpUhvNoClose band", half_stats(cm & ~band)))
say(line("the InpUhvNoClose band itself (UTC 20:45-21:15)", half_stats(band)))
say(f"$ of the removed losers (Python replay, hypothesis): {PNL[cm & LOSS].sum():+,.0f}; of all 172 losses: {PNL[LOSS].sum():+,.0f}")
wins = PNL[~LOSS]; losses_ = PNL[LOSS]
need = 100 * abs(losses_.mean()) / (abs(losses_.mean()) + wins.mean())
say(f"geometry: average win {wins.mean():+.2f}$, average loss {losses_.mean():+.1f}$ -> break-even win rate {need:.2f}%")
import doctrine  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    doctrine.python_says("97.7% setting, all trades (python replay)", 100 * (1 - BASE["all"]), need_pct=need)
    doctrine.python_says("after rule_combined (rollover guard)", INFO["rule_combined"]["wr_after"], need_pct=need)
for ln in buf.getvalue().rstrip().splitlines():
    say(ln)

# ------------------------------------------------------------------------------------------ 5b: sensitivity - the task's LITERAL bar
def passes_literal(r):
    """the task's own bar only: lift >= 2 on both halves and >= 4 losers (no per-half minimum, no distinct-day minimum)"""
    return r["all"]["L"] >= 4 and (r["train"]["lift"] or 0) >= 2 and (r["test"]["lift"] or 0) >= 2


def greedy_quiet(pool_rules, extra_masks, bar):
    """the same forward/backward selection, silent; extra_masks = {name: mask} for non-function candidates (the extended field)"""
    cand = {r.__name__: MASK[r.__name__] for r in pool_rules}
    cand.update(extra_masks)
    UU = []
    while True:
        taken = np.zeros(N, bool)
        for nm in UU:
            taken |= cand[nm]
        ok = [(nm, half_stats(m & ~taken)) for nm, m in cand.items() if nm not in UU]
        ok = [(nm, r) for nm, r in ok if bar(r)]
        if not ok:
            return UU
        UU.append(max(ok, key=lambda x: (x[1]["all"]["L"], min(x[1]["train"]["lift"], x[1]["test"]["lift"])))[0])
        while True:
            weak = []
            for nm in UU:
                others = np.zeros(N, bool)
                for o in UU:
                    if o != nm:
                        others |= cand[o]
                uq = half_stats(cand[nm] & ~others)
                if not bar(uq):
                    weak.append((uq["all"]["L"], nm))
            if not weak:
                break
            drop = min(weak)[1]
            UU.remove(drop)
            cand.pop(drop)


say("")
say("-- sensitivity: the same greedy under the task's LITERAL bar (lift >= 2 both halves, >= 4 losers; no per-half / distinct-day minimum)")
harness_pool = [r for r in R.ACCEPTED + R.CANDIDATES + R.REJECTED if r not in R.FILL_TIME and r not in R.EXTENDED]
SENS = {}
for label, extra in (("harness fields only", {}), ("+ extended breakout-tick spread >= 1.0", {"rule_trigger_spread": spr >= 1.0 - 1e-9})):
    UU = greedy_quiet(harness_pool, extra, passes_literal)
    um = np.zeros(N, bool)
    for nm in UU:
        um |= MASK[nm] if nm in MASK and nm != "rule_trigger_spread" else extra.get(nm, MASK.get(nm))
    SENS[label] = {"rules": UU, "stats": half_stats(um)}
    say(f"   {label:40s} -> {UU}")
    say("   " + line("      union", half_stats(um)))
    say("   " + line("      union, stop-outs only (why=1)", half_stats(um, STOP_POP, BASE_STOP)))

# ------------------------------------------------------------------------------------------ 6: geometry check (why no chart rule can work)
say("")
say("-- geometry: a driftless random walk loses with p = (spread + 0.1) / (stop + 0.1) (target 0.1 pip past the fill on the far side;")
say("   stop measured from the fill), spread = the breakout tick's. If the entry had an edge, actual stop-outs would sit BELOW this.")
stopp = np.array([t["stop_pips"] for t in T])
prw = (spr + 0.1) / (stopp + 0.1)
GEO = {}
for nm, h in (("all", np.ones(N, bool)), ("train", TRAIN), ("test", ~TRAIN), ("outside rule_combined", ~comb), ("inside rule_combined", comb)):
    GEO[nm] = {"trades": int(h.sum()), "expected_random_walk": round(float(prw[h].sum()), 1), "stop_outs": int((LOSS & (WHY == 1) & h).sum()),
               "all_losses": int((LOSS & h).sum()), "median_spread": float(np.median(spr[h])), "median_stop": float(np.median(stopp[h]))}
    g = GEO[nm]
    say(f"   {nm:22s} trades {g['trades']:5d}  random-walk expected losses {g['expected_random_walk']:6.1f}  actual stop-outs {g['stop_outs']:3d}"
        f"  all losses {g['all_losses']:3d}  (median spread {g['median_spread']:.2f} pip, stop {g['median_stop']:.1f} pip)")
json.dump({"rules": INFO, "greedy_log": LOG, "accepted": [r.__name__ for r in U], "geometry": GEO, "sensitivity_literal_bar": SENS,
           "extended_increment": {str(q): v for q, v in EXT.items()}, "extended_union": ext_union, "break_even_wr": round(need, 2)},
          open(os.path.join(HERE, "scores_final.json"), "w", encoding="utf-8"), indent=1, default=str)
open(os.path.join(HERE, "scores_final.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
say("\nwrote scores_final.txt and scores_final.json")
