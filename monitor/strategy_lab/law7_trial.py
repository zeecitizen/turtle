"""law7_trial.py — Law 7 candidate exam (Zee 2026-08-05, hand-drawn):
3 same-colour candles — momentum / DOJI (body < wicks) / momentum — entry on the
first close beyond the doji's extreme (high for green, low for red).

DAY 1 (2026-08-05 tape): FAILED — best variant (loose doji + slant-aligned)
avg +0.28pt vs ordinary-setup benchmark +0.30..+0.55. Strict doji negative.
Standalone entry is structurally LATE (2-3 candles of fuel already spent).
Same promotion rule as Law 6: 3 passing days incl. a non-trending one.
Untested redemption idea: as CONFLUENCE at an existing lamp's black lines.
Run:  py monitor/strategy_lab/law7_trial.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "monitor"); sys.path.insert(0, "monitor/strategy_lab")
import oanda_live_matcher as M
import trend_eyes as TE
bars = M.load_bars()
tb = [(b.t, b.h, b.l, b.c, b.v) for b in bars]

def find(doji_max=0.50):
    out = []
    for i in range(2, len(bars) - 1):
        c1, c2, c3 = bars[i - 2], bars[i - 1], bars[i]
        same = (c1.is_bull and c2.is_bull and c3.is_bull) or                (c1.is_bear and c2.is_bear and c3.is_bear)
        if not same or c1.body_ratio < 0.5 or c3.body_ratio < 0.5: continue
        if c2.body_ratio >= doji_max: continue
        side = "BUY" if c1.is_bull else "SELL"
        lvl = c2.h if side == "BUY" else c2.l
        for j in range(i, min(i + 4, len(bars))):
            b = bars[j]
            if (side == "BUY" and b.c > lvl) or (side == "SELL" and b.c < lvl):
                out.append(dict(i=j, side=side, entry=b.c)); break
    return out

def sim(e):
    entry = e["entry"]; buy = e["side"] == "BUY"
    armed = False; peak = 0.0
    for b in bars[e["i"] + 1:]:
        adverse = (entry - b.l) if buy else (b.h - entry)
        favor = (b.h - entry) if buy else (entry - b.l)
        if not armed and adverse >= 1.0: return -1.0
        if favor >= 0.3: armed = True
        if armed:
            peak = max(peak, favor)
            if peak - ((b.l - entry) if buy else (entry - b.h)) >= max(0.2, 0.3 * peak):
                return peak - max(0.2, 0.3 * peak)
    return None

res = []
for e in find():
    a = TE.auto_call(tb, upto=e["i"] + 1)
    if e["side"] not in a["allow"]: continue
    r = sim(e)
    if r is not None: res.append(r)
if res:
    w = sum(1 for x in res if x > 0)
    avg = sum(res) / len(res)
    print(f"  Law7 (aligned): n={len(res)}  WR {w/len(res)*100:.0f}%  avg {avg:+.2f}pt  net {sum(res):+.2f}pt")
    print("  DAY VERDICT:", "PASS" if avg >= 0.30 else "FAIL (below ordinary-setup benchmark +0.30)")
else:
    print("  no qualifying entries on this tape")
