"""target_vs_trail.py — should our best setups AIM at the last structural high
instead of trailing? (Zee 2026-08-06, from his 6:16 PM example: the ratchet banked
$20.93 while the structural target would have banked $266.)

Also tests the tip from a REAL PERSON: "no-supply candle WITH SELLING BACKGROUND
works awesome" — i.e. Law 6 (climactic/selling background) + no-supply together.

Exits compared on IDENTICAL entries:
  A) RATCHET      arm +0.3, give back max(0.2, 30% of peak)      [the machine today]
  B) TARGET       TP = last confirmed structural high/low, SL = the UHV sweep line
  C) TARGET+GHOST same, but evaporate at -1.0 if it never armed  [hybrid]
Buckets: by diamond count, and by (no-supply x selling-background).
"""
from __future__ import annotations
import csv, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "monitor"); sys.path.insert(0, "monitor/strategy_lab")
import oanda_live_matcher as M
import build_entry_review_m5 as B
import trend_eyes as TE
for k, v in M.CFG.items():
    setattr(B, k, v)

COST = 0.07


def load_bars():
    seen = {}
    for src in ("monitor/strategy_lab/oanda_m1_history.csv",
                r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv"):
        try:
            for r in csv.DictReader(open(src, encoding="utf-8")):
                seen[r["time_unix"]] = r
        except FileNotFoundError:
            pass
    out = []
    for k in sorted(seen, key=int):
        r = seen[k]
        out.append(B.Bar(datetime.fromtimestamp(int(k), tz=timezone.utc).replace(tzinfo=None),
                         float(r["open"]), float(r["high"]), float(r["low"]),
                         float(r["close"]), int(float(r["volume"]))))
    return out


def structural_target(bars, tb, i, side, entry):
    """The last CONFIRMED structural swing beyond entry (trend_eyes pivots)."""
    sw = TE.find_swings(tb, upto=i)
    if side == "BUY":
        highs = [s.price for s in sw if s.kind == "H" and s.price > entry + 0.3]
        return highs[-1] if highs else None
    lows = [s.price for s in sw if s.kind == "L" and s.price < entry - 0.3]
    return lows[-1] if lows else None


def sim_ratchet(bars, i, side, entry):
    buy = side == "BUY"
    armed, peak = False, 0.0
    for b in bars[i + 1:]:
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


def sim_target(bars, i, side, entry, sl, tgt, ghost=False):
    if tgt is None or sl is None:
        return None
    buy = side == "BUY"
    armed = False
    for b in bars[i + 1:]:
        adverse = (entry - b.l) if buy else (b.h - entry)
        favor = (b.h - entry) if buy else (entry - b.l)
        if favor >= 0.3:
            armed = True
        if ghost and not armed and adverse >= 1.0:
            return -1.0 - COST
        if buy:
            if b.l <= sl:
                return -(entry - sl) - COST
            if b.h >= tgt:
                return (tgt - entry) - COST
        else:
            if b.h >= sl:
                return -(sl - entry) - COST
            if b.l <= tgt:
                return (entry - tgt) - COST
    return None


def report(name, rows):
    rows = [r for r in rows if r is not None]
    if not rows:
        print(f"    {name:16s}  —")
        return
    w = sum(1 for r in rows if r > 0)
    print(f"    {name:16s} n={len(rows):3d}  WR {w/len(rows)*100:3.0f}%  "
          f"avg {statistics.mean(rows)*10:+6.2f}$  net {sum(rows)*10:+8.2f}$")


if __name__ == "__main__":
    bars = load_bars()
    tb = [(b.t, b.h, b.l, b.c, b.v) for b in bars]
    setups = list({(s["open_t"], s["side"]): s for s in B.detect_full(bars)}.values())
    print(f"tape {len(bars)} bars · {len(setups)} setups\n")

    rec = []
    for s in setups:
        i = next(idx for idx, b in enumerate(bars) if b.t == s["open_t"])
        u = next((idx for idx, b in enumerate(bars) if b.t == s["uhv_t"]), None)
        if u is None or i < 30:
            continue
        side, entry = s["side"], s["entry"]
        sweep = bars[u].l if side == "BUY" else bars[u].h
        sl = sweep - 0.1 if side == "BUY" else sweep + 0.1
        tgt = structural_target(bars, tb, i, side, entry)
        # conviction pieces
        dia = int(M.swept(bars, u, i, side))
        ns = any(M.no_supply_bar(bars, k, side) for k in range(u + 1, i))
        look = bars[max(0, u - 20):u]
        avgv = sum(b.v for b in look) / max(len(look), 1)
        prev = bars[max(0, u - 4):u]
        heavy = sum(1 for b in prev
                    if (b.is_bear if side == "BUY" else b.is_bull) and b.v >= avgv)
        bg = heavy >= 2                      # the "selling background"
        rec.append(dict(i=i, side=side, entry=entry, sl=sl, tgt=tgt, dia=dia, ns=ns, bg=bg,
                        A=sim_ratchet(bars, i, side, entry),
                        Bx=sim_target(bars, i, side, entry, sl, tgt),
                        C=sim_target(bars, i, side, entry, sl, tgt, ghost=True)))

    print("── ALL SETUPS ──")
    for nm, key in (("A ratchet", "A"), ("B target", "Bx"), ("C target+ghost", "C")):
        report(nm, [r[key] for r in rec])

    print("\n── SWEPT (Law 1 satisfied) ──")
    sw = [r for r in rec if r["dia"]]
    for nm, key in (("A ratchet", "A"), ("B target", "Bx"), ("C target+ghost", "C")):
        report(nm, [r[key] for r in sw])

    print("\n── THE REAL-PERSON TIP: no-supply WITH selling background ──")
    tip = [r for r in rec if r["ns"] and r["bg"]]
    print(f"    (n={len(tip)} of {len(rec)})")
    for nm, key in (("A ratchet", "A"), ("B target", "Bx"), ("C target+ghost", "C")):
        report(nm, [r[key] for r in tip])

    print("\n── no-supply WITHOUT selling background (the control) ──")
    ctl = [r for r in rec if r["ns"] and not r["bg"]]
    for nm, key in (("A ratchet", "A"), ("B target", "Bx"), ("C target+ghost", "C")):
        report(nm, [r[key] for r in ctl])
