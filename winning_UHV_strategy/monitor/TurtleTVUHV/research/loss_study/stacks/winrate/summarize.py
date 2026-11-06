"""summarize.py - reads results.json of stack_winrate.py and prints the step table plus the honesty checks (TEST never chose anything):

  lift       loss rate among the trades a stack removed (net: base losses - stack losses over base trades - stack trades) / the base loss rate.
             > 1 = it removes losers faster than winners. (Approximate: freed slots let a few new trades in.)
  hyper p    P(this few TEST losses) if the stack had kept the same number of TEST trades AT RANDOM from the base's TEST trades
             (hypergeometric, 4,295 trades / 60 losses). Small = the TEST improvement is unlikely to be luck. Losses cluster by day, so this is
             optimistic.
Run: py research/loss_study/stacks/winrate/summarize.py"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json"), encoding="utf-8"))


def hyper_le(x, N, K, n):
    """P(X <= x), X = losses among n trades drawn at random without replacement from N trades holding K losses"""
    n = min(n, N)
    tot = 0.0
    den = math.comb(N, n)
    for i in range(max(0, n - (N - K)), min(x, K, n) + 1):
        tot += math.comb(K, i) * math.comb(N - K, n - i) / den
    return min(1.0, tot)


def lift(b, s):
    dn, dL = b["n"] - s["n"], b["L"] - s["L"]
    if dn <= 0:
        return None
    return (dL / dn) / (b["L"] / b["n"])


def line(h):
    return f"{h['n']:5d} / {h['L']:3d} / {h['wr']:6.2f}% / lfd {h['lfd_pct']:5.1f}% ({h['lfd']:2d}/{h['den']}, {h['days']:2d} traded) / {h['net']:+9,.0f}"


B = R["base"]
print(f"objective: {R['objective']}\nstop: {R.get('stop_reason')}\n")
print(f"{'step':4s} {'move':28s} {'TRAIN n / L / WR / loss-free days / net':62s} | {'TEST n / L / WR / loss-free days / net':62s} | lift tr/te | hyper p (TEST)")
print(f"{'0':4s} {'(base 97.7%)':28s} {line(B['train']):62s} | {line(B['test']):62s} |")
same_dir = 0
prev = B
for s in R["steps"]:
    tr, te = s["train"], s["test"]
    lt, le = lift(B["train"], tr), lift(B["test"], te)
    hp = hyper_le(te["L"], B["test"]["n"], B["test"]["L"], te["n"])
    d_tr, d_te = tr["wr"] - prev["train"]["wr"], te["wr"] - prev["test"]["wr"]
    same_dir += (d_te > 0)
    print(f"{s['step']:<4d} {s['setting'] + '=' + s['value']:28s} {line(tr):62s} | {line(te):62s} | "
          f"{(f'{lt:.2f}' if lt else ' -  ')}/{(f'{le:.2f}' if le else ' -  ')} | {hp:.3g}   (TRAIN {d_tr:+.3f}, TEST {d_te:+.3f})")
    prev = {"train": tr, "test": te}
if "final" in R:
    F = R["final"]
    print("\nFINAL stack:", F["stack"])
    for p in ("train", "test", "all"):
        print(f"  {p.upper():5s} {line(F[p])}")
    te = F["test"]
    print(f"\nTEST: base {B['test']['wr']:.2f}% -> {te['wr']:.2f}% ({te['n']} of {B['test']['n']} trades kept = {100 * te['n'] / B['test']['n']:.0f}%); "
          f"expected losses at the base rate {te['n'] * B['test']['L'] / B['test']['n']:.1f}, got {te['L']}; "
          f"hypergeometric p {hyper_le(te['L'], B['test']['n'], B['test']['L'], te['n']):.3g}, binomial p {F['test_p_vs_base_rate']:.3g}")
    tr = F["train"]
    print(f"TRAIN: base {B['train']['wr']:.2f}% -> {tr['wr']:.2f}% ({tr['n']} of {B['train']['n']} kept = {100 * tr['n'] / B['train']['n']:.0f}%); "
          f"expected losses at the base rate {tr['n'] * B['train']['L'] / B['train']['n']:.1f}, got {tr['L']} (chosen on TRAIN: in-sample)")
    print(f"steps where TEST WR rose with TRAIN: {same_dir} of {len(R['steps'])}")
    if "verify" in R:
        print("fresh-process verify:", R["verify"])
