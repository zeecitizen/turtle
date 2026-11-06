"""evaluate_pockets.py - METHOD C step 3: apply the FROZEN train-tuned pockets (chosen_pockets.json from tune_pockets.py, and the relaxed
chosen_pockets_x2.json sensitivity) to both halves. Nothing here is tuned: the union is built on TRAIN by leave-one-out (a pocket stays
only if what it adds beyond the others still has marginal lift >= the bar on train), then shown on TEST untouched.
Per pocket and per half: share of trades, losses in it (of the half's total), loss rate, lift vs the half's own base and vs 2.26%,
the untouched zone's WR when the pocket is skipped entirely, own-cause capture, distinct loss days, and on test observed vs expected
losses (expected = test share x test losses: what a pocket with no skill would hold).
Output: evaluation.txt, evaluation.json. Python engine outcomes = HYPOTHESIS, NOT PROMOTED (CLAUDE.md); only MT5 / live fills promote."""
import csv, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pocket_defs import CLUSTERS, mask_of, describe  # noqa: E402

ROWS = list(csv.DictReader(open(os.path.join(HERE, "..", "features.csv"), encoding="utf-8")))
CAUSE = json.load(open(os.path.join(HERE, "causes_by_id.json")))
FEATS = [k for k in ROWS[0] if k not in ("id", "win", "pnl", "half")]
A = {f: np.array([float(r[f]) for r in ROWS]) for f in FEATS}
loss = np.array([r["win"] == "0" for r in ROWS])
cause = np.array([CAUSE.get(r["id"], "") for r in ROWS])
day = np.array([r["id"][:4] for r in ROWS])
HALF = {"train": np.array([r["half"] == "train" for r in ROWS])}
HALF["test"] = ~HALF["train"]
BASE_ALL = loss.mean()
NEED_WR = 99.3
out, J = [], {}


def say(s=""):
    print(s); out.append(s)


def st(m, h):
    hm_ = HALF[h]; N = int(hm_.sum()); L = int((hm_ & loss).sum())
    mm = m & hm_; n = int(mm.sum()); l = int((mm & loss).sum())
    rate = l / n if n else 0.0
    unt_wr = 100 * (1 - (L - l) / (N - n)) if N > n else float("nan")
    return {"n": n, "N": N, "share": n / N, "l": l, "L": L, "lshare": l / L if L else 0.0, "rate": rate,
            "lift_half": rate / (L / N) if n else 0.0, "lift_all": rate / BASE_ALL if n else 0.0, "untouched_wr": unt_wr,
            "base_wr": 100 * (1 - L / N), "days": len(set(day[mm & loss])), "expected_l": n / N * L}


def fmt(s):
    return (f"{100*s['share']:4.1f}% of trades ({s['n']}/{s['N']}), {s['l']}/{s['L']} losses = {100*s['lshare']:4.1f}% of losses, "
            f"loss rate {100*s['rate']:5.2f}% (lift x{s['lift_half']:.2f} vs half base, x{s['lift_all']:.2f} vs 2.26%), "
            f"untouched WR {s['untouched_wr']:.2f}% (base {s['base_wr']:.2f}%), loss days {s['days']}")


def bar_line(s):
    # losses the union would have to hold for the untouched zone to reach 0.7% loss rate at this union share
    allowed = 0.007 * (s["N"] - s["n"]); need = max(0.0, s["L"] - allowed)
    return (f"bar: at {100*s['share']:.1f}% share the untouched zone may keep {allowed:.1f} losses -> pockets must hold {need:.1f} of "
            f"{s['L']} ({100*need/s['L']:.0f}%, lift x{(need/max(s['n'],1))/(s['L']/s['N']):.1f}); they hold {s['l']}")


def run(tag, fn):
    P = json.load(open(os.path.join(HERE, fn)))
    bar = P.get("lift_bar", 3.5)
    say("=" * 150)
    say(f"[{tag}] pockets from {fn} (tuned on TRAIN only, marginal-lift bar x{bar:g}); base loss rate train "
        f"{100*loss[HALF['train']].mean():.2f}%  test {100*loss[HALF['test']].mean():.2f}%  all {100*BASE_ALL:.2f}%")
    say("=" * 150)
    masks, res = {}, {}
    for cl in CLUSTERS:
        if cl not in P["pockets"]:
            continue
        c = P["pockets"][cl]
        m = mask_of(c["family"], c["params"], A); masks[cl] = m
        r = {"condition": describe(c["family"], c["params"]), "viable_on_train": c["viable"], "plateau": c["plateau"]}
        say(f"\n-- {cl}: {r['condition']}   [{'VIABLE on train' if c['viable'] else 'NOT VIABLE on train (kept for the record)'}; "
            f"same-family plateau {c['plateau']}]")
        for h in ("train", "test"):
            s = st(m, h); own = int((HALF[h] & loss & (cause == cl)).sum()); ownin = int((m & HALF[h] & loss & (cause == cl)).sum())
            s["own_cause_in"] = ownin; s["own_cause_total"] = own; r[h] = s
            say(f"   {h:5s}: {fmt(s)} | own cause {ownin}/{own}")
        s = r["test"]
        say(f"   test observed {s['l']} vs expected-if-no-skill {s['expected_l']:.1f}; share drift test/train "
            f"{(s['share'] / r['train']['share']) if r['train']['share'] else float('nan'):.2f}")
        res[cl] = r
    # ---- union of the train-viable pockets, pruned by leave-one-out on TRAIN
    tr = HALF["train"]; BASE_TR = loss[tr].mean(); lam = bar * BASE_TR
    keep = [cl for cl in res if res[cl]["viable_on_train"]]
    say(f"\n-- leave-one-out on TRAIN (pocket kept if what it adds beyond the other kept pockets has marginal lift >= x{bar:g})")
    while True:
        worst = None
        for cl in keep:
            others = np.zeros(len(ROWS), bool)
            for o in keep:
                if o != cl:
                    others |= masks[o]
            add = masks[cl] & ~others & tr
            n_add, l_add = int(add.sum()), int((add & loss).sum())
            sc = l_add - lam * n_add
            say(f"   {cl:20s} adds N {n_add:4d}, L {l_add:3d} (marginal rate {100*l_add/max(n_add,1):5.1f}%, "
                f"x{(l_add/max(n_add,1))/BASE_TR:.2f}) score {sc:6.2f}")
            if worst is None or sc < worst[1]:
                worst = (cl, sc)
        if worst is None or worst[1] > 0:
            break
        say(f"   -> drop {worst[0]} (adds too little beyond the others), re-check")
        keep.remove(worst[0])
    U = np.zeros(len(ROWS), bool)
    for cl in keep:
        U |= masks[cl]
    UA = np.zeros(len(ROWS), bool)
    for cl in res:
        UA |= masks[cl]
    J[tag] = {"pockets": res, "union_kept": keep}
    for nm, um in ((f"UNION of kept pockets ({', '.join(keep)})", U), ("UNION of ALL chosen pockets incl. non-viable", UA)):
        say(f"\n-- {nm}")
        J[tag][nm[:12]] = {}
        for h in ("train", "test"):
            s = st(um, h); J[tag][nm[:12]][h] = s
            say(f"   {h:5s}: {fmt(s)}")
            say(f"          {bar_line(s)}")
        s = J[tag][nm[:12]]["test"]
        say(f"   test observed {s['l']} vs expected-if-no-skill {s['expected_l']:.1f}")
    return U


U = run("STRICT x3.5", "chosen_pockets.json")
if os.path.exists(os.path.join(HERE, "chosen_pockets_x2.json")):
    run("RELAXED x2 (sensitivity)", "chosen_pockets_x2.json")

# own-cause composition of the losses left untouched (strict union): what the angel never sees
say("\n-- causes of the losses LEFT in the untouched zone (strict union), train / test")
for cl in CLUSTERS + ["bad_fill"]:
    a = int((HALF["train"] & loss & ~U & (cause == cl)).sum()); b = int((HALF["test"] & loss & ~U & (cause == cl)).sum())
    ta = int((HALF["train"] & loss & (cause == cl)).sum()); tb = int((HALF["test"] & loss & (cause == cl)).sum())
    say(f"   {cl:20s} train {a:3d} of {ta:3d} left   test {b:3d} of {tb:3d} left")

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))))   # turtle/monitor
try:
    import doctrine  # noqa: E402
    say("\n-- doctrine.python_says (CLAUDE.md: the only sanctioned way to quote a Python win rate)")
    import io, contextlib
    for h in ("train", "test"):
        s = J["STRICT x3.5"]["UNION of kep"][h]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            doctrine.python_says(f"untouched zone outside the strict Method-C pockets ({h})", s["untouched_wr"], need_pct=NEED_WR)
        say(buf.getvalue().rstrip())
except ImportError as e:
    say(f"(doctrine.py not importable: {e}) - Python engine outcomes = HYPOTHESIS, NOT PROMOTED")
open(os.path.join(HERE, "evaluation.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
json.dump(J, open(os.path.join(HERE, "evaluation.json"), "w"), indent=1, default=float)
