"""law6_trial.py — the Sixth Law's daily exam (Selling Climax UHV, Zee 2026-08-05).

Law 6 candidate: a 2nd TYPE of UHV — in-trend retracement where (a) LARGE
counter-trend VOLUMES precede the UHV (2+ bars >= 1.0x avg20, Zee's refinement:
"selling background should mean large selling volumes") and (b) the UHV is a
BIG-SPREAD candle (range >= 1.5x avg20).

PROMOTION CRITERION (fixed 2026-08-05, day 1 PASSED: SC avg +0.54 vs +0.30):
refined-SC expectancy >= ordinary on 3 separate days incl. one non-trending day.
Run daily on fresh tape: py monitor/strategy_lab/law6_trial.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "monitor"); sys.path.insert(0, "monitor/strategy_lab")
import oanda_live_matcher as M
import build_entry_review_m5 as B
for k, v in M.CFG.items(): setattr(B, k, v)
bars = M.load_bars()
setups = list({(s["open_t"], s["side"]): s for s in B.detect_full(bars)}.values())

def sim(s):
    i0 = next(i for i, b in enumerate(bars) if b.t == s["open_t"])
    entry = s["entry"]; buy = s["side"] == "BUY"
    armed = False; peak = 0.0
    for b in bars[i0 + 1:]:
        adverse = (entry - b.l) if buy else (b.h - entry)
        favor = (b.h - entry) if buy else (entry - b.l)
        if not armed and adverse >= 1.0: return -1.0
        if favor >= 0.3: armed = True
        if armed:
            peak = max(peak, favor)
            if peak - ((b.l - entry) if buy else (entry - b.h)) >= max(0.2, 0.3 * peak):
                return peak - max(0.2, 0.3 * peak)
    return None

def is_sc(s):
    u = next(i for i, b in enumerate(bars) if b.t == s["uhv_t"])
    look = bars[max(0, u - 20):u]
    avg_v = sum(b.v for b in look) / max(len(look), 1)
    avg_r = sum(b.h - b.l for b in look) / max(len(look), 1)
    prev = bars[max(0, u - 4):u]
    col = (lambda b: b.is_bear) if s["side"] == "BUY" else (lambda b: b.is_bull)
    heavy = sum(1 for b in prev if col(b) and b.v >= avg_v)
    U = bars[u]
    return heavy >= 2 and (U.h - U.l) >= 1.5 * avg_r

sc, ordi = [], []
for s in setups:
    r = sim(s)
    if r is None: continue
    (sc if is_sc(s) else ordi).append(r)
for name, v in (("SC (Law 6)", sc), ("ordinary", ordi)):
    if v:
        w = sum(1 for x in v if x > 0)
        print(f"  {name:12s} n={len(v):3d}  WR {w/len(v)*100:.0f}%  avg {sum(v)/len(v):+.2f}  net {sum(v):+.2f}")
verdict = (sc and ordi and sum(sc)/len(sc) >= sum(ordi)/len(ordi))
print("  DAY VERDICT:", "PASS — SC >= ordinary" if verdict else "fail on this tape")
