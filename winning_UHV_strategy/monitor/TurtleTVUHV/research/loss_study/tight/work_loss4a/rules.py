"""work_loss4a/rules.py - cures designed from the charts of the two tight losses 0408-075606-B and 0723-001905-S (and their 3 winning twins
each), scored with api_tight.report on tight / zee100 / secure / base, all / train (before 2026-07-01) / test.
Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). Only MT5's Strategy Tester or live fills may promote anything here.

MY COMMENT ON EACH LOSS (read on charts/tight_<id>.png and its three charts/tight_twin_<id>_*.png; bar numbers relative to k = the last closed
candle before the breakout minute; pips relative to the UHV level)

0408-075606-B  BUY, Wed 8 Apr 07:56:06 UTC (12:56 PKT, one hour into London). humps 2, ER16 0.389, ATR 2.3p, UHV 161 ticks, breakout 15 ticks
  in 6 s, trigger spread 0.6p (the train regime: 0.5 or 0.6), stop 21.6p.
  The chart: a 28-pip, high-volume sell-off (1.1707 -> 1.1679, 11:50-12:13 PKT, bars of 200-280 ticks) and then a 40-minute, quieter
  (130-205 ticks) staircase rally straight back to 1.1700. The buy fires at the top of that rally, under the round figure 1.1700 and under
  the 11:56 breakdown zone, after three rejections at 1.16996-1.17000 in the last ten bars (k-9 +0.6, k-3 +0.7, k-1 +1.0 above the level).
  The UHV (161) is no louder than its neighbours; it is not a climax. The 0.6-pip spread put the fill at 1.16999 and the 0.1-pip target bid
  at 1.17000 - EXACTLY the k-1 rejection high. The bid reached 1.16999 inside the breakout minute, 0.1 pip short, and never printed higher:
  20 pips down in 45 minutes, stop 1.16783.
  Twins: 0407-232607-B (Asia, a clean 90-pip uptrend, breakout at a new high, 60 ticks, target 2.9 pips under the k-1 high) won in 4 s;
  0408-102512-B (a range; target 0.3 pip under the k-1 high, the same +1.0p rejection bar as the loss) won in 3 min; 0408-121316-B (an
  uptrend, target 0.7 under the recent high) got its +0.1 and then fell 19 of its 22 stop pips - a loss with any slower fill.
  What separates the loss from its twins ON THE CHART: the target pinned on the recent rejection high (room 0.0 pip vs 0.3-2.9) and the
  wider spread (0.6 vs 0.5) that put it there. On secure / base neither holds: the room is flat across buckets in both halves (feat.py), and
  the spread effect is the already-guarded rollover / wide-spread effect (rule_spread_upper_mode below). The description of the miss, not
  its cause.

0723-001905-S  SELL, Thu 23 Jul 00:19:05 UTC (05:19 PKT, the Tokyo open). humps 3, ER16 0.370, ATR 0.62p, UHV 86 ticks (at k-1, a GREEN
  bar), breakout 3 ticks in 5 s, trigger spread 0.2p while the last 30 bars' median was 0.1p, stop 19.9p.
  The chart: a slow Asian grind up from 1.1406 to 1.1414 over 75 minutes that ends in a 265-tick bullish spike at 05:01 PKT (the loudest
  bar on the chart, ~5x its neighbours). The sell is the QUIET pullback from that spike (17-65 tick bars) back into the spike's base at
  1.1411. The level had already been pierced 0.5 pip two bars earlier (k-2 low 1.14105) and recovered; the UHV is a buyers' bar; the
  breakout is 3 ticks. The same level was sold 20 minutes earlier (0722-235911-S at 1.14113), which only won after a 2.4-pip squeeze.
  After entry: no tick below the breakout bid, price back up 2 pips at once, chop at 1.1412-1.1414, then 20 pips up to the stop in 3.8 h.
  In Zee's VSA terms: selling a no-supply pullback after a demand spike.
  Twins: 0722-174558-S (a range, 43 ticks at second 59) won +4; 0722-235911-S (the same uptrend, sold BEFORE the spike; 2.4-pip squeeze
  first) won +2; 0723-140845-S (with a down-swing, 142 ticks) won +4 at once.
  What separates the loss from its twins ON THE CHART: the 3-tick breakout, a second sell of the same level within an hour, a spread at
  twice the recent median, and fading the pullback of a volume spike. On secure / base: the tick count / share and the volume-leg tests
  are flat; the re-break holds only in the test half (0723, 1019 and 1023 - three of tight's four losses - are re-breaks; train x1.04-1.17);
  the spread points the right way on both halves but is flat once the existing guards are applied.

VERDICT (2026-11-06; rules_report.txt + robust_spread.py / robust_floor.py / guarded_check2.py / zee_steps.py / box_perm.py)
  NO rule from these two charts generalises. Each deletes the losses it was drawn from (tight 99.44 -> 99.55-100%; four rules make a tight
  half WORSE: counter_last_big_move, fade_counter_spike, rebreak_same_level, spread_wide), but on secure / base the trades a rule removes
  lose no more often than a random skip of the same size, on at least one half (exact hypergeometric p, chance check lines).
  The two near-misses:
   - rule_fade_counter_spike: base train x2.64 (p 0.004) but base test x0.78 and 0 secure losses removed - one half only.
   - rule_spread_upper_mode (skip the regime's upper spread mode: >= 0.6p when the 240-bar median spread is >= 0.35p, else >= 0.2p): the
     ONLY result significant on both halves of full base (x1.30 p 0.007 / x1.39 p 0.035) - but on base AFTER the existing guards (no
     16:45-17:45 NY entries, spread < 1.0) it is x1.22 (p 0.054) / x1.10 (p 0.37), and inside secure p 0.08 / 0.45: its base gain is mostly
     the rollover / 1-pip spread guard re-found. The other spread forms (wide, not-narrow, above-floor) are flat on guarded base (x0.93-1.09).
  The 100% of Zee's 07-33-17 setting: all four tight losses have ER16 0.352-0.442 and the 0.35 cap sits just under the lowest. The cap's
  dropped band loses 0.54% / 1.02% (train / test) vs the kept band's 0 - p 0.61 / 0.29, chance. 0 losses in 308 happens 18% of the time
  at tight's own loss rate; the 95% upper bound on the true loss rate after 0/308 is 0.97% (WR >= 99.03%, under the ~99.3% break-even).

Run:  py work_loss4a/rules.py   (prints api_tight.report lines + an exact hypergeometric check; tees to work_loss4a/rules_report.txt)
Every rule below is a SELF-CONTAINED source string `def rule(t, A): ...` (imports inside, absolute paths to this folder's tables, cache in
rule.__dict__); main() execs each string in a fresh namespace, counts exceptions on every trade of every stack (the harness would swallow
them as 'keep'), and reports exactly that function. Rules read only t's decision-time fields and bars <= t["k"] (never kb), plus
spread_m1.npz (build_spread.py: the median ask-bid of each closed minute, from the ticks) and setups.npz (build_setups.py: every earlier
UHV breakout tick the engine saw, stack-independent)."""
import contextlib
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight  # noqa: E402

W = HERE.replace("\\", "/")        # absolute folder of the decision-time tables, baked into the source strings

RULE_SRC = {}

# ------------------------------------------------------------------------------------------- from loss 0408-075606-B
RULE_SRC["rule_target_on_rejection_high"] = '''def rule(t, A):
    """0408: the decision-time target (breakout bid + spread + 0.1 pip) sits 0-0.2 pip UNDER the extreme of the last 10 closed bars - the
    0.1-pip win needs price to retake a high (low) it just rejected (loss 0.0 pip, loss 2 0.1; twins 0.3-2.9)."""
    import numpy as np
    k, s = t["k"], t["side"]
    tgt = t["brk_bid"] + s * (t["trig_spread_pips"] + 0.1) * 1e-4
    ext = float(np.max(A.h[k - 9:k + 1])) if s > 0 else float(np.min(A.l[k - 9:k + 1]))
    room = s * (ext - tgt) / 1e-4
    return 0.0 <= room < 0.2
'''

RULE_SRC["rule_triple_test"] = '''def rule(t, A):
    """0408: the TARGET zone was tested and rejected 3+ times in the last 12 bars - bar highs (buy) / lows (sell) inside [target - 0.4,
    target + 0.2] pip with no close beyond the target (k-9 +0.6, k-3 +0.7, k-1 +1.0 vs a +1.0 target: the 1.1700 triple top)."""
    import numpy as np
    k, s = t["k"], t["side"]
    tgt = t["brk_bid"] + s * (t["trig_spread_pips"] + 0.1) * 1e-4
    ext = A.h[k - 11:k + 1] if s > 0 else A.l[k - 11:k + 1]
    cl = A.c[k - 11:k + 1]
    d = s * (ext - tgt) / 1e-4
    hit = (d >= -0.4 - 1e-9) & (d <= 0.2 + 1e-9)
    return int(np.sum(hit)) >= 3 and bool(np.all(s * (cl - tgt) <= 0))
'''

RULE_SRC["rule_vsa_weak_leg"] = '''def rule(t, A):
    """0408 (and 0723): the leg in the trade direction carries less volume than the opposite leg before it (a quiet rally after a loud
    sell-off / a quiet pullback after a loud spike). Legs from the 60-bar extreme against the trade and the extreme before it; skip when
    the current leg's mean volume < 0.85 x the prior leg's."""
    import numpy as np
    k, s, N = t["k"], t["side"], 60
    if s > 0:
        jL = k - N + 1 + int(np.argmin(A.l[k - N + 1:k + 1])); a = max(jL - N, 0); jH = a + int(np.argmax(A.h[a:jL + 1]))
    else:
        jL = k - N + 1 + int(np.argmax(A.h[k - N + 1:k + 1])); a = max(jL - N, 0); jH = a + int(np.argmin(A.l[a:jL + 1]))
    if jL >= k - 1 or jH >= jL:
        return False
    return float(np.mean(A.v[jL:k + 1])) < 0.85 * float(np.mean(A.v[jH:jL + 1]))
'''

RULE_SRC["rule_counter_last_big_move"] = '''def rule(t, A):
    """0408 / 0723: the later of the 90-bar high and low is AGAINST the trade (a buy bouncing inside a sell-off, a sell pulling back inside
    a rally) and the trade's leg has retraced at least 30% of that move."""
    import numpy as np
    k, s, N = t["k"], t["side"], 90
    hh, ll = A.h[k - N + 1:k + 1], A.l[k - N + 1:k + 1]
    jh, jl = int(np.argmax(hh)), int(np.argmin(ll))
    H, L = float(hh[jh]), float(ll[jl])
    if H <= L:
        return False
    if s > 0 and jl > jh:
        return (t["level"] - L) / (H - L) >= 0.3
    if s < 0 and jh > jl:
        return (H - t["level"]) / (H - L) >= 0.3
    return False
'''

# ------------------------------------------------------------------------------------------- from loss 0723-001905-S
RULE_SRC["rule_quiet_breakout_share"] = '''def rule(t, A):
    """0723 (and 0408): the breakout minute had under 10% of the UHV's ticks at the break - price drifted across the level (0723 3/86,
    0408 15/161; twins 0.17-0.80). The opposite end of the existing LoudBrk filter."""
    return t["brk_ticks"] < 0.10 * max(t["uhv_v"], 1.0)
'''

RULE_SRC["rule_early_thin_break"] = '''def rule(t, A):
    """0723 / 0408: the break came in the first 8 seconds of the minute with fewer than 16 ticks (0723 3 ticks at 5.4 s, 0408 15 at 6.2 s)."""
    return (t["t_dec"] % 60) < 8.0 and t["brk_ticks"] < 16
'''

RULE_SRC["rule_fade_counter_spike"] = '''def rule(t, A):
    """0723: the loudest bar of the last 30 closed bars (UHV excluded) is AGAINST the trade, >= 2.5x the 30-bar median volume, and closed
    BEHIND the level (the trade sells back into a bullish spike / buys back into a bearish one) - 0723's 265-tick spike at k-17."""
    import numpy as np
    k, s, ku = t["k"], t["side"], t["ku"]
    idx = np.arange(k - 29, k + 1)
    idx = idx[idx != ku]
    j = int(idx[int(np.argmax(A.v[idx]))])
    against = (A.c[j] - A.o[j]) * s < 0
    loud = A.v[j] >= 2.5 * float(np.median(A.v[k - 29:k + 1]))
    return bool(against and loud and s * (A.c[j] - t["level"]) < 0)
'''

RULE_SRC["rule_rebreak_same_level"] = '''def rule(t, A):
    """0723: the same level was already broken the same way within the last 60 minutes (+-0.5 pip; 0722-235911-S sold 1.14113 at 23:59,
    0723 sold 1.1411 at 00:19) - the first break failed back through the level. Earlier breakouts from setups.npz (stack-independent)."""
    import numpy as np
    if "Z" not in rule.__dict__:
        rule.__dict__["Z"] = np.load("%(W)s/setups.npz")
    Z = rule.__dict__["Z"]
    St, Ss, Sl = Z["t"], Z["side"], Z["level"]
    a, b = int(np.searchsorted(St, t["t_dec"] - 3600)), int(np.searchsorted(St, t["t_dec"] - 0.5))
    return bool(np.any((Ss[a:b] == t["side"]) & (np.abs(Sl[a:b] - t["level"]) <= 0.5e-4 + 1e-9)))
''' % {"W": W}

RULE_SRC["rule_spread_wide"] = '''def rule(t, A):
    """0723 (0.2 vs a 0.1 median): the breakout-tick spread is WIDER than the median spread of the last 120 closed minutes (+0.05 pip)."""
    import numpy as np
    if "M" not in rule.__dict__:
        rule.__dict__["M"] = np.load("%(W)s/spread_m1.npz")["med"]
    M, k = rule.__dict__["M"], t["k"]
    return t["trig_spread_pips"] > float(np.median(M[k - 119:k + 1])) + 0.05
''' % {"W": W}

RULE_SRC["rule_spread_not_narrow"] = '''def rule(t, A):
    """Both losses: trade ONLY when the breakout-tick spread is NARROWER than the median of the last 60 closed minutes (by > 0.05 pip);
    skip 'usual' and 'wide' (0408 0.6 = median, 0723 0.2 vs 0.1; 4 of 6 twins were narrow)."""
    import numpy as np
    if "M" not in rule.__dict__:
        rule.__dict__["M"] = np.load("%(W)s/spread_m1.npz")["med"]
    M, k = rule.__dict__["M"], t["k"]
    return t["trig_spread_pips"] >= float(np.median(M[k - 59:k + 1])) - 0.05
''' % {"W": W}

RULE_SRC["rule_spread_upper_mode"] = '''def rule(t, A):
    """Both losses sat at their regime's UPPER spread mode (0408: 0.6 in the 0.5/0.6 train regime; 0723: 0.2 in the 0.1/0.2 test regime).
    Skip >= 0.6 pip when the last 240 closed minutes' median spread is >= 0.35 pip (wide regime), else skip >= 0.2 pip."""
    import numpy as np
    if "M" not in rule.__dict__:
        rule.__dict__["M"] = np.load("%(W)s/spread_m1.npz")["med"]
    M, k = rule.__dict__["M"], t["k"]
    m = float(np.median(M[k - 239:k + 1]))
    return t["trig_spread_pips"] >= (0.55 if m >= 0.35 else 0.15)
''' % {"W": W}


def compile_rule(src):
    ns = {}
    exec(src, ns)                                                 # noqa: S102 - our own source strings
    return ns["rule"]


# ------------------------------------------------------------------------------------------- an exact chance check
def p_hyper(N, K, n, x):
    """P(a random skip set of n trades out of N, K of them losses, removes >= x losses) - exact hypergeometric tail."""
    if n <= 0 or x <= 0:
        return 1.0
    den = math.comb(N, n)
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(x, min(K, n) + 1)) / den


def chance(rule):
    out = []
    for st in ("secure", "base"):
        r = api_tight.score(rule, st)
        cells = []
        for part in ("train", "test"):
            c = r[part]
            N, K, n, x = c["trades"], c["losses"], c["removed"], c["losses_removed"]
            exp = n * K / max(N, 1)
            cells.append(f"{part} {x}L/{n} (exp {exp:.1f}, lift x{x / exp if exp else 0:.2f}, p {p_hyper(N, K, n, x):.3f})")
        out.append(f"{st}: " + ", ".join(cells))
    return " | ".join(out)


def exceptions(rule):
    bad = 0
    for st in ("tight", "secure", "base"):
        for t in api_tight.STACKS[st]:
            try:
                rule(api_tight._blind(t), api_tight.A)
            except Exception:                                    # noqa: BLE001
                bad += 1
    return bad


if __name__ == "__main__":
    lines = []
    for name, src in RULE_SRC.items():
        rule = compile_rule(src)
        nexc = exceptions(rule)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            api_tight.report(rule, name)
        line = buf.getvalue().strip().splitlines()[-1]
        ch = chance(rule)
        for x in (line, f"    exceptions on all stacks: {nexc} | chance check: " + ch):
            print(x, flush=True)
            lines.append(x)
    with open(os.path.join(HERE, "rules_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
