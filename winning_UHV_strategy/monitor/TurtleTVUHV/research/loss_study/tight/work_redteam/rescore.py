"""rescore.py (work_judge) - an independent re-score of every cure proposed by work_loss4a (11 rules), work_loss4b (6) and work_secure30
(7 + the random-20% control) for the angel's secure zones. Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md).

For each rule:
  1. exceptions: the rule is called directly on every trade of every stack (api_tight.score silently counts an exception as 'keep').
  2. the official api_tight.report line.
  3. a per stack x half table: losses / winners removed, WR before -> after, lift (loss rate of the skipped trades / the stack-half's),
     exact one-sided hypergeometric p (the chance that a RANDOM skip of the same number of trades removes at least as many losses).
     Stacks: tight, zee100, secure, base, and base_g = base with the two guards every angel setting already carries (no entries
     16:45-17:45 New York on t_dec, breakout spread < 1.0 pip) - a gain on raw base can be those guards found again.
  4. two verdicts, the bar FIXED BEFORE the table was read:
     LITERAL = the task's bar: WR after > WR before on BOTH halves of secure, or of base.
     STRICT  = on secure or base_g, with the rule's own design losses taken out of the stack (0408-075606-B / 0723-001905-S for loss4a,
               1019-171329-S / 1023-145031-B for loss4b; for secure30, which read all 30 secure losses, secure is in-sample, so only
               base_g minus those 30 ids counts): lift > 1 AND p < 0.05 on BOTH halves. (25 rules x 2 stacks at p < 0.10 per half would
               give a spurious both-halves pass ~40% of the time; at p < 0.05 the expected false passes are ~0.1.)
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_judge/rescore.py
Writes rescore_out.txt and rescore.json next to this file.

RESULT (2026-11-06; rescore_out.txt, null_bar_out.txt, engine_runs_out.txt, engine_extra_out.txt):
  0 exceptions, 0 cross-stack disagreements for all 25 rules.
  LITERAL bar: 17 of the 24 real rules pass it - and so does control_random20. null_bar.py: a random skip passes the literal bar 31-44% of
    the time (any skip size). Most of the excess comes from rules removing their own design losses (0408 is a secure-train loss, 1019 and
    1023 are secure-test losses) and from re-finding the rollover / >= 1-pip guards on raw base. With those taken out, 8 of 24 still pass,
    about what chance gives.
  STRICT bar (fixed before reading, p < 0.05 both halves, design losses out, base_g): 0 of 24 pass; even at p < 0.10, 0 of 24.
    A random rule passes the strict bar 0.07-0.30% of the time.
  Engine (only two cures have an existing input that acts under InpUhvRiskMgr 2; every uhv_filters.skip() filter is INERT under RiskMgr 2,
    receipt: InpUhvRunPips 8.1/60 and InpUhvNewsNY 1 give identical rows on tight and zee100):
    InpUhvMaxTrigSpread 0.5: tight 714/4 -> 528/3 (test 382/3 unchanged); zee100 308/0 -> 241/0 (test 183/0 unchanged); secure 30 -> 12 L,
      all of it in Mar-Jun (no breakout spreads between 0.5 and 1.0 after June). It insures against a wide-spread regime and cures nothing.
    InpUhvSafeRangeAtr 9.2 / Bars 120: secure 98.66 -> 99.00% but tight test 99.21 -> 98.96% and base_g test lift x0.66. It does not carry.
  SAVE GATE (zee100 TEST 183/0): no setting-backed variant has 0 test losses with more test trades -> NOTHING SAVED.
  Python tick replay = HYPOTHESIS, NOT PROMOTED; doctrine: python 99-100% -> expect ~83-84% in MT5 vs ~99.3% needed -> would LOSE."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
TIGHT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TIGHT)))
for p in (TIGHT, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
import api_tight  # noqa: E402
from scipy.stats import hypergeom  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = api_tight.SPLIT
P_STRICT = 0.05


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


A4 = load(os.path.join(TIGHT, "work_loss4a", "rules.py"), "rules_loss4a")
B4 = load(os.path.join(TIGHT, "work_loss4b", "rules.py"), "rules_loss4b")
S30 = load(os.path.join(TIGHT, "work_secure30", "rules.py"), "rules_secure30")
RULES = [("loss4a", n, A4.compile_rule(src)) for n, src in A4.RULE_SRC.items()]
RULES += [("loss4b", f.__name__, f) for f in B4.RULES]
RULES += [("secure30", f.__name__, f) for f in S30.RULES]

ST = dict(api_tight.STACKS)


def guarded(t):
    ny = dt.datetime.fromtimestamp(t["t_dec"], NY)
    m = ny.hour * 60 + ny.minute
    return (16 * 60 + 45 <= m < 17 * 60 + 45) or t["trig_spread_pips"] >= 1.0 - 1e-9


ST["base_g"] = [t for t in ST["base"] if not guarded(t)]
SECURE_LOSS_IDS = {t["id"] for t in ST["secure"] if not t["win"]}
DESIGN = {"loss4a": {"0408-075606-B", "0723-001905-S"}, "loss4b": {"1019-171329-S", "1023-145031-B"}, "secure30": SECURE_LOSS_IDS}
ORDER = ("tight", "zee100", "secure", "base", "base_g")


def pval(N, K, n, x):
    if n <= 0 or x <= 0:
        return 1.0
    return float(hypergeom.sf(x - 1, N, K, n))


def cell(trades, skip):
    N = len(trades); K = sum(1 for t in trades if not t["win"])
    n = sum(1 for t in trades if skip[t["id"]]); x = sum(1 for t in trades if skip[t["id"]] and not t["win"])
    wr0 = 100 * (1 - K / max(N, 1)); wr1 = 100 * (1 - (K - x) / max(N - n, 1))
    exp = n * K / max(N, 1)
    return {"N": N, "K": K, "n": n, "x": x, "wr0": round(wr0, 2), "wr1": round(wr1, 2), "lift": round(x / exp, 2) if exp > 0 else None,
            "p": round(pval(N, K, n, x), 4)}


def halves(trades):
    return {"all": trades, "train": [t for t in trades if t["t_dec"] < SPLIT], "test": [t for t in trades if t["t_dec"] >= SPLIT]}


def main():
    out_lines, res = [], {}

    def say(s=""):
        print(s, flush=True)
        out_lines.append(s)

    say("RE-SCORE of every proposed cure (work_judge). Python tick replay = HYPOTHESIS, NOT PROMOTED.")
    for nm in ORDER:
        T = ST[nm]
        say(f"  stack {nm:7s}: {len(T)} trades, {sum(1 for t in T if not t['win'])} losses "
            f"(train {sum(1 for t in T if t['t_dec'] < SPLIT)}/{sum(1 for t in T if t['t_dec'] < SPLIT and not t['win'])}, "
            f"test {sum(1 for t in T if t['t_dec'] >= SPLIT)}/{sum(1 for t in T if t['t_dec'] >= SPLIT and not t['win'])})")
    say(f"  STRICT bar fixed in advance: lift > 1 and hypergeometric p < {P_STRICT} on BOTH halves of secure or base_g, design losses removed")
    say("")
    for src, name, rule in RULES:
        sk, exc = {}, {}
        for nm in ("tight", "secure", "base"):
            e, d = 0, {}
            for t in ST[nm]:
                try:
                    v = bool(rule(api_tight._blind(t), api_tight.A))
                except Exception:                                   # noqa: BLE001
                    v = False; e += 1                               # an exception = keep, exactly as api_tight.score counts it
                d[t["id"]] = v
            sk[nm], exc[nm] = d, e
        sk["zee100"], sk["base_g"] = sk["tight"], sk["base"]
        # the same trade id in two stacks = the same setup and decision-time facts: the decisions must agree
        dis = sum(1 for a in ("tight", "secure") for i, v in sk[a].items() if i in sk["base"] and sk["base"][i] != v)
        exc["disagree"] = dis
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            api_tight.report(rule, f"{src}:{name}")
        official = buf.getvalue().strip().splitlines()[-1]
        tab = {}
        for nm in ORDER:
            tab[nm] = {h: cell(Tt, sk[nm]) for h, Tt in halves(ST[nm]).items()}
        strict = {}
        for nm in ("secure", "base_g"):
            if src == "secure30" and nm == "secure":
                continue
            Tx = [t for t in ST[nm] if t["id"] not in DESIGN[src]]
            hh = halves(Tx)
            strict[nm] = {h: cell(hh[h], sk[nm]) for h in ("train", "test")}
        literal = any(tab[nm]["train"]["wr1"] > tab[nm]["train"]["wr0"] and tab[nm]["test"]["wr1"] > tab[nm]["test"]["wr0"] for nm in ("secure", "base"))
        literal_on = [nm for nm in ("secure", "base") if tab[nm]["train"]["wr1"] > tab[nm]["train"]["wr0"] and tab[nm]["test"]["wr1"] > tab[nm]["test"]["wr0"]]
        strict_on = [nm for nm, c in strict.items() if all((c[h]["lift"] or 0) > 1 and c[h]["p"] < P_STRICT for h in ("train", "test"))]
        weak_on = [nm for nm, c in strict.items() if all((c[h]["lift"] or 0) > 1 and c[h]["p"] < 0.10 for h in ("train", "test"))]
        res[f"{src}:{name}"] = {"official": official, "exceptions": exc, "table": tab, "strict": strict, "literal": literal, "literal_on": literal_on,
                                "strict_on": strict_on, "weak_on": weak_on}
        say(official)
        say(f"    exceptions: {exc}")
        for nm in ORDER:
            c = tab[nm]
            say(f"    {nm:7s} " + "  ".join(f"{h} -{c[h]['x']}L/-{c[h]['n'] - c[h]['x']}W {c[h]['wr0']}->{c[h]['wr1']} lift {c[h]['lift']} p {c[h]['p']}"
                                       for h in ("train", "test")))
        for nm, c in strict.items():
            say(f"    STRICT {nm:7s} (design losses out) " + "  ".join(
                f"{h} {c[h]['x']}L/{c[h]['n']} of {c[h]['K']}L/{c[h]['N']} lift {c[h]['lift']} p {c[h]['p']}" for h in ("train", "test")))
        say(f"    LITERAL {'PASS on ' + '+'.join(literal_on) if literal else 'fail'} | STRICT {'PASS on ' + '+'.join(strict_on) if strict_on else 'fail'}"
            f" | (weak p<0.10 both halves: {'+'.join(weak_on) if weak_on else 'none'})")
        say("")
    say("SUMMARY")
    for k, r in res.items():
        say(f"  {k:45s} literal {'PASS ' + '+'.join(r['literal_on']) if r['literal'] else 'fail':22s} strict {'PASS ' + '+'.join(r['strict_on']) if r['strict_on'] else 'fail':14s}"
            f" weak {'+'.join(r['weak_on']) or '-'}")
    open(os.path.join(HERE, "rescore_out.txt"), "w", encoding="utf-8").write("\n".join(out_lines) + "\n")
    json.dump(res, open(os.path.join(HERE, "rescore.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
