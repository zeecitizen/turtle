"""halves.py (work_redteam) - per rule x stack x half: losses / trades removed, lift, p (from my rerun rescore.json); flags literal passes
whose gain in a half rests on <= 2 removed losses; and the POWER of the strict bar (what lift a skip needs to reach p < 0.05).
Python replay = HYPOTHESIS, NOT PROMOTED."""
import json, os
from scipy.stats import hypergeom
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "rescore.json")))
lines = []
def say(s=""):
    print(s); lines.append(s)
say("rule | literal | per-half removed losses (x of K, n skipped of N, lift, p): secure / base_g-clean(strict) | flags")
nflag = 0
for name, r in R.items():
    tab, strict = r["table"], r["strict"]
    lit = r["literal_on"]
    flags = []
    for st in lit:                                   # the stack(s) where WR went up on both halves
        for h in ("train", "test"):
            c = tab[st][h]
            if c["x"] <= 2:
                flags.append(f"{st}-{h} gain rests on {c['x']} loss(es)")
    # design-loss share: losses removed on secure that are the rule's own design losses
    s_tr, s_te = tab["secure"]["train"], tab["secure"]["test"]
    cells = []
    for st in ("secure", "base_g"):
        if st in strict:
            for h in ("train", "test"):
                c = strict[st][h]
                cells.append(f"{st}*{h} {c['x']}/{c['K']}L n{c['n']}/{c['N']} x{c['lift']} p{c['p']}")
        else:
            for h in ("train", "test"):
                c = tab[st][h]
                cells.append(f"{st}(in-sample){h} {c['x']}/{c['K']}L n{c['n']}/{c['N']} x{c['lift']} p{c['p']}")
    if flags:
        nflag += 1
    say(f"{name:42s} | {'+'.join(lit) or '-':12s} | " + " ; ".join(cells) + (" | FLAG: " + "; ".join(flags) if flags else ""))
say(f"\nliteral passes with a half resting on <= 2 removed losses: {nflag} rules")

say("\nPOWER of the strict bar (one-sided hypergeometric, p < 0.05): the smallest losses-removed count x and the lift it implies")
for st, N, K in (("secure train (clean of 0408)", 1058, 21), ("secure test (clean of 1019/1023)", 1177, 6), ("secure test (clean of 0723)", 1178, 7),
                 ("base_g train", None, None), ("base_g test", None, None)):
    if N is None:
        # read N, K from any rule's strict base_g cell (design losses out differ by <= 2)
        c = R["loss4a:rule_early_thin_break"]["strict"]["base_g"]["train" if "train" in st else "test"]
        N, K = c["N"], c["K"]
    out = []
    for f in (0.05, 0.10, 0.15, 0.30):
        n = round(f * N)
        exp = n * K / N
        x = next(x for x in range(0, K + 2) if x > K or hypergeom.sf(x - 1, N, K, n) < 0.05)
        out.append(f"skip {int(f*100)}%: need {x} of {K} (exp {exp:.1f}, lift x{x/exp:.1f})" if x <= K else f"skip {int(f*100)}%: impossible")
    say(f"  {st:34s} N {N} K {K}: " + " | ".join(out))
open(os.path.join(HERE, "halves_out.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
