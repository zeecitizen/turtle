"""scenario3_trial.py — CLIMACTIC ACTION BAR, SCENARIO 3 (Zee 2026-08-06, verbatim spec).

  1. in a retracement find the UHV = Climatic Action Bar (falling market: big-volume RED)
  2. mark trigger lines at that candle's LOW and HIGH
  3. after it, near the trigger lines, a NO SUPPLY candle appears —
     RED, small spread, volume LESS THAN HALF of the ones before
  4. supply has ended -> demand will build
  5. confirmation: the LOW of the no-supply is swept -> that candle is BO
  6. BO (or a candle within 2-3) breaks the no-supply's HIGH; that green breakout
     must be a MOMENTUM candle with HIGHER volume than the no-supply candle
  8. the upper trigger line does NOT need to break
  9. entry on top of the BO/breakout candle
 10. SL below the no-supply candle
 11. first target = last structural high

Mirror (rising market): green climactic bar, NO DEMAND candle, sweep of its HIGH,
break of its LOW by a red momentum candle.

TRIAL: does this pattern beat the machine's current setups? Both exit models:
  A) Zee's own: SL below no-supply / TP at last structural high
  B) the machine's: ghost + ratchet (so the comparison is apples-to-apples)
"""
from __future__ import annotations
import csv, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "monitor"); sys.path.insert(0, "monitor/strategy_lab")
import oanda_live_matcher as M
import build_entry_review_m5 as B
for k, v in M.CFG.items():
    setattr(B, k, v)

COST = 0.07          # Raw-account round trip, points


def load_bars():
    seen = {}
    for src in ("monitor/strategy_lab/oanda_m1_history.csv",
                r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv"):
        try:
            for r in csv.DictReader(open(src, encoding="utf-8")):
                seen[r["time_unix"]] = r
        except FileNotFoundError:
            pass
    bars = []
    for k in sorted(seen, key=int):
        r = seen[k]
        bars.append(B.Bar(datetime.fromtimestamp(int(k), tz=timezone.utc).replace(tzinfo=None),
                          float(r["open"]), float(r["high"]), float(r["low"]),
                          float(r["close"]), int(float(r["volume"]))))
    return bars


def find_scenario3(bars, side="BUY"):
    """Return list of dicts: the full 11-step pattern instances."""
    out = []
    n = len(bars)
    bear = side == "BUY"                       # BUY: falling market, red climax, red no-supply
    for c in range(30, n - 6):
        C = bars[c]
        # STEP 1 — climactic action bar: big-volume candle of the retracement's colour
        if (C.is_bear if bear else C.is_bull) is False:
            continue
        look = bars[c - 20:c]
        if not look:
            continue
        avg_v = sum(b.v for b in look) / len(look)
        avg_r = sum(b.h - b.l for b in look) / len(look)
        if C.v < 1.5 * avg_v:                  # must be climactic, not ordinary
            continue
        lo_line, hi_line = C.l, C.h            # STEP 2 — the two trigger lines
        # STEP 3 — a NO SUPPLY candle after it, near the lines
        for k in range(c + 1, min(c + 8, n - 4)):
            NS = bars[k]
            if (NS.is_bear if bear else NS.is_bull) is False:
                continue
            if k < 2:
                continue
            # Zee: "lesser than half of the ones before" + small spread
            if NS.v >= 0.5 * bars[k - 1].v or NS.v >= 0.5 * bars[k - 2].v:
                continue
            if (NS.h - NS.l) > 0.8 * avg_r:
                continue
            near = min(abs(NS.c - lo_line), abs(NS.c - hi_line)) <= max(1.0, 0.5 * (hi_line - lo_line))
            if not near:
                continue
            # STEP 5 — the sweep of the no-supply's LOW (BUY) / HIGH (SELL)
            for j in range(k + 1, min(k + 5, n - 1)):
                BO = bars[j]
                swept = (BO.l < NS.l) if bear else (BO.h > NS.h)
                if not swept:
                    continue
                # STEP 6 — BO or a candle within 2-3 breaks the no-supply's HIGH (BUY),
                # green momentum, volume HIGHER than the no-supply
                for m in range(j, min(j + 4, n - 1)):
                    BK = bars[m]
                    broke = (BK.c > NS.h) if bear else (BK.c < NS.l)
                    right_colour = BK.is_bull if bear else BK.is_bear
                    if broke and right_colour and BK.body_ratio >= 0.5 and BK.v > NS.v:
                        out.append(dict(i=m, side=side, entry=BK.c,
                                        sl=(NS.l - 0.1) if bear else (NS.h + 0.1),
                                        ns_i=k, climax_i=c, t=BK.t))
                        break
                break
            break
    # de-dup by entry bar
    uniq = {}
    for s in out:
        uniq[s["i"]] = s
    return sorted(uniq.values(), key=lambda s: s["i"])


def structural_target(bars, i, side):
    """STEP 11 — first target = last structural high (BUY) / low (SELL)."""
    seg = bars[max(0, i - 60):i]
    if not seg:
        return None
    return max(b.h for b in seg) if side == "BUY" else min(b.l for b in seg)


def sim_zee(bars, s):
    """A) Zee's exits: SL below the no-supply, TP at the last structural high."""
    tgt = structural_target(bars, s["i"], s["side"])
    if tgt is None:
        return None
    buy = s["side"] == "BUY"
    if (buy and tgt <= s["entry"]) or (not buy and tgt >= s["entry"]):
        return None
    for b in bars[s["i"] + 1:]:
        if buy:
            if b.l <= s["sl"]:
                return -(s["entry"] - s["sl"]) - COST
            if b.h >= tgt:
                return (tgt - s["entry"]) - COST
        else:
            if b.h >= s["sl"]:
                return -(s["sl"] - s["entry"]) - COST
            if b.l <= tgt:
                return (s["entry"] - tgt) - COST
    return None


def sim_machine(bars, s):
    """B) the machine's exits: 1pt ghost + ratchet trail (apples-to-apples)."""
    buy = s["side"] == "BUY"
    entry = s["entry"]
    armed = False
    peak = 0.0
    for b in bars[s["i"] + 1:]:
        adverse = (entry - b.l) if buy else (b.h - entry)
        favor = (b.h - entry) if buy else (entry - b.l)
        if not armed and adverse >= 1.0:
            return -1.0 - COST
        if favor >= 0.3:
            armed = True
        if armed:
            peak = max(peak, favor)
            if peak - ((b.l - entry) if buy else (entry - b.h)) >= max(0.2, 0.3 * peak):
                return peak - max(0.2, 0.3 * peak) - COST
    return None


def report(name, vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        print(f"  {name:34s}  no resolvable instances")
        return
    w = sum(1 for v in vals if v > 0)
    print(f"  {name:34s} n={len(vals):3d}  WR {w/len(vals)*100:3.0f}%  "
          f"avg {statistics.mean(vals):+.3f}pt  net {sum(vals):+.2f}pt  (${sum(vals)*10:+.0f} @0.10)")


if __name__ == "__main__":
    bars = load_bars()
    print(f"tape: {len(bars)} bars ({bars[0].t:%m-%d %H:%M}Z -> {bars[-1].t:%m-%d %H:%M}Z)\n")
    print("── SCENARIO 3 (Climactic Action Bar) ON TRIAL ──")
    all3 = []
    for side in ("BUY", "SELL"):
        s3 = find_scenario3(bars, side)
        all3 += s3
        print(f"  {side}: {len(s3)} instances found")
    print()
    report("Scenario-3 · ZEE exits (SL/target)", [sim_zee(bars, s) for s in all3])
    report("Scenario-3 · MACHINE exits (ghost+ratchet)", [sim_machine(bars, s) for s in all3])

    # baseline: what the machine's own detector produces on the same tape
    base = list({(s["open_t"], s["side"]): s for s in B.detect_full(bars)}.values())
    bvals = []
    for s in base:
        i0 = next(i for i, b in enumerate(bars) if b.t == s["open_t"])
        bvals.append(sim_machine(bars, dict(i=i0, side=s["side"], entry=s["entry"])))
    print()
    report("BASELINE machine setups (same exits)", bvals)
