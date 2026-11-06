"""rules.py - candidate cures for the 30 losses of the angel's SECURE zone (work_secure30, 2026-11-06).

Every rule is   def rule(t, A) -> bool   (True = SKIP), self-contained, reading only t's decision-time fields (the breakout tick) and bars
<= t["k"]. Thresholds were fixed a priori or at the BASE TRAIN half's 20th / 80th percentile (3,335 trades, Mar-Jun) - never tuned on
the 30 secure losses. Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md).
Run:  cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV/research/loss_study/tight/work_secure30 && NUMBA_CPU_NAME=generic py rules.py
      -> api_tight.report for every rule + the doctrine haircut, written to report_lines.txt
Study scripts (same folder): py feats.py && py feats2.py (feat.pkl, ~10 s) | py emp_null.py 60 secure base tight, py emp_null_days.py 40
secure base tight (random-entry nulls) | scan_auc.py, scan_oe.py, scan_oe_days.py, perm_oe.py, perm_oe_days.py (feature scans + their
permutation tests) | news_check.py, engine_check.py, guards_check.py (-> guards_check.txt), carve_check.py, carve_perm.py,
carve_perm_tight.py, carve_perm_tight668.py | per_loss.json.

THE FRAME (rw_null.py, emp_null.py, emp_null_days.py): target 0.1 pip, stop ~20 pips, so a RANDOM entry with the same side, stop and
0.3 s latency wins ~98.3% (random tick within +-90 min) / ~97.9% (same clock on other days). Losses vs random-entry expectation
(+-90-min null / path-free other-days null), PER HALF:
  secure  train 22 vs 26 / 31   test  8 vs 12 / 17        (at or a little better than random)
  base    train 112 vs 87 / 92  test 60 vs 49 / 59        (train worse than random under both nulls; test random under the path-free null)
  tight   train 1 vs 7.4 / 9.6  test 3 vs 4.2 / 5.4       zee100 (harness, 300 trades) 0 vs 4.6 (+-90-min null)
Every one of the 30 losses has best_R <= 0: the bid never climbed spread + 0.1 pip after the fill - the breakout tick was the top (bottom)
of the whole move to the stop. 28 are stop-outs, 2 are the engine's Friday-close flattens (0327-200119-B -$136, 1023-145031-B -$40).
CARVING: if the 30 losses fell on random secure trades, a loss-free humps x ER16 box of >= 287 trades exists in 48% of draws
(carve_perm.py) and a box of >= 668 trades with <= 3 losses (the tight box inside secure) in 20% (carve_perm_tight668.py): neither the
zee100 box nor the tight box is distinguishable from a box drawn after seeing the losses.

GENERALISES (the bar used here, stricter than "WR up on both halves", which three of these pass by hairs): the removed trades' loss rate
above the stack-half's on BOTH halves of secure AND of base once the trades the secure setting already blocks (NY rollover 16:45-17:45,
breakout spread >= 1.0 pip) are taken out (guards_check.txt), significant (binomial p < 0.05) in a cell the rule was NOT read from, and a
secure win-rate gain above the random-20% control (+0.18).
VERDICT (report_lines.txt, guards_check.txt, engine_check.py, perm_oe*.py, news_check.py): NO rule here generalises.
  - the 'extension' family (run120 / mv60 / pos120) has a significant O/E dose-response against the +-90-min null (perm_oe.py: run120
    p=0.003 after 141 features) that VANISHES against the path-free other-days null (perm_oe_days.py: best feature p=0.14) - random entries
    placed inside the same run-up won because of that run-up, which made 'extended' look dangerous. Raw base-test loss rates are flat.
  - rule_range_bound120 is the best on secure (engine: 98.66 -> 99.00%, train 97.92 -> 98.50, test 99.32 -> 99.46) but base test goes
    98.60 -> 98.56 and tight 99.44 -> 99.28: it does not travel.
  - rule_news_clock passes all four cells only because DIFFERENT windows carry different cells (:25-:30 in train only, :56-:03 in base
    test only); its windows were noticed on the 30 losses' clock times => data-snooped, not a cure.
  - the random 20% control moves secure 98.66 -> 98.84 by luck alone: that is the noise floor for 30 losses."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def rule_range_bound120(t, A):
    """RANGE: the last 120 closed candles span fewer than 9.2 ATRs (base-train 20th pct) - a sideways box where the break is a poke at
    its edge. Engine twin: InpUhvSafeRangeAtr=9.2 + InpUhvSafeRangeBars=120 (uhv_filters.secure)."""
    k = t["k"]
    a = float(A.atr[k])
    return a > 0 and float(A.h[k - 119:k + 1].max() - A.l[k - 119:k + 1].min()) < 9.2 * a


def rule_extended_run120(t, A):
    """EXTENSION: the level already sits more than 19.2 pips beyond the 2-hour opposite extreme (base-train 80th pct) - buying the top of
    a 2-hour climb / selling the bottom of a slide."""
    PIP = 1e-4
    k, s, lv = t["k"], t["side"], t["level"]
    run = (lv - float(A.l[k - 119:k + 1].min())) if s > 0 else (float(A.h[k - 119:k + 1].max()) - lv)
    return run / PIP > 19.2


def rule_with_move60(t, A):
    """EXTENSION (momentum form): the last 60 closes moved more than 8.1 pips in the trade's direction (base-train 80th pct)."""
    PIP = 1e-4
    k = t["k"]
    return float(A.c[k] - A.c[k - 60]) * t["side"] / PIP > 8.1


def rule_congested_level(t, A):
    """DOUBLE / TRIPLE TOP: 6 or more confirmed 3-bar swing highs (buy) / lows (sell) from before the UHV, in the last 240 candles, sit
    within 1 pip of the break level (6 = base-train 80th pct) - the price has been turned back there again and again."""
    PIP = 1e-4
    k, ku, s, lv = t["k"], t["ku"], t["side"], t["level"]
    h, l = A.h, A.l
    n = 0
    for j in range(max(3, k - 240), min(k - 3, ku - 1) + 1):          # pivot j is confirmed by bars j+1..j+3 <= k, and is older than the UHV
        if s > 0:
            if h[j] >= h[j - 3:j].max() and h[j] >= h[j + 1:j + 4].max() and abs(h[j] - lv) <= 1.0 * PIP:
                n += 1
        elif l[j] <= l[j - 3:j].min() and l[j] <= l[j + 1:j + 4].min() and abs(l[j] - lv) <= 1.0 * PIP:
            n += 1
    return n >= 6


def rule_news_clock(t, A):
    """NEWS CLOCK (no calendar): the breakout tick lands in minute :56-:03 or :25-:30 of the hour (scheduled data, hourly flow)."""
    import datetime as dt
    m = dt.datetime.fromtimestamp(t["t_dec"], dt.timezone.utc).minute
    return m >= 56 or m <= 3 or 25 <= m <= 30


def rule_chop120(t, A):
    """CHOP: the efficiency ratio of the last 120 closes is below 0.031 (base-train 20th pct) - two hours that went nowhere."""
    import numpy as np
    k = t["k"]
    cc = A.c[k - 120:k + 1]
    path = float(np.abs(np.diff(cc)).sum())
    return path > 0 and abs(float(cc[-1] - cc[0])) / path < 0.031


def rule_wide_spread_now(t, A):
    """SPREAD vs ITS OWN HOUR: the breakout tick's spread is more than 0.05 pip above the median per-minute spread (sim 'sp1') of the last
    60 candles - regime-free (Mar-May ~0.55 pip, Jun-Nov ~0.14). Mechanical: the bid must climb spread + 0.1 pip to reach the target."""
    import numpy as np
    PIP = 1e-4
    if not hasattr(rule_wide_spread_now, "sp1"):
        import os
        import sys
        os.environ.setdefault("NUMBA_CPU_NAME", "generic")
        root = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
        if root not in sys.path:
            sys.path.insert(0, root)
        import sim
        rule_wide_spread_now.sp1 = np.asarray(sim.data("year1")["sp1"], dtype=float)
    k = t["k"]
    return t["trig_spread_pips"] > float(np.median(rule_wide_spread_now.sp1[k - 59:k + 1])) / PIP + 0.05


def control_random20(t, A):
    """CONTROL: skips a pseudo-random 20% of trades (crc32 of the id) - the noise floor any rule must beat."""
    import zlib
    return zlib.crc32(t["id"].encode()) % 5 == 0


RULES = (rule_range_bound120, rule_extended_run120, rule_with_move60, rule_congested_level, rule_news_clock, rule_chop120,
         rule_wide_spread_now, control_random20)


if __name__ == "__main__":
    import contextlib
    import io

    import api_tight as AT
    lines = []
    for r in RULES:
        T = AT.STACKS["secure"]
        hits = sum(1 for t in T if r(AT._blind(t), AT.A))                 # score() swallows exceptions: call directly first
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            AT.report(r, r.__name__)
        line = buf.getvalue().rstrip("\n")
        print(line, flush=True)
        lines.append(f"{line}\n    (direct call on secure: skips {hits} of {len(T)})")
    buf = io.StringIO()
    try:
        sys.path.insert(0, r"C:/Users/zeesh/turtle/monitor")
        from doctrine import python_says
        with contextlib.redirect_stdout(buf):
            print("\nDOCTRINE (monitor/doctrine.py) - avg win ~$1.5 / avg loss ~$-210 -> break-even ~99.3%:")
            python_says("secure zone as saved (engine, Mar-Nov, 2238 trades)", win_pct=98.66, need_pct=99.3)
            python_says("zee100 = 2026-11-06 07-33-17 (engine, 308 trades, 0 losses)", win_pct=100.0, need_pct=99.3)
            python_says("secure + rule_range_bound120 (engine, 1798 trades)", win_pct=99.00, need_pct=99.3)
    except Exception as e:                                                   # noqa: BLE001
        buf.write(f"doctrine import failed: {e}\n")
    print(buf.getvalue(), flush=True)
    open(os.path.join(HERE, "report_lines.txt"), "w", encoding="utf-8").write(
        "api_tight.report - Python tick replay = HYPOTHESIS, NOT PROMOTED\n" + "\n".join(lines) + "\n" + buf.getvalue())
