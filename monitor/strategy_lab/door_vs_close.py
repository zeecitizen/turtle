"""door_vs_close.py — INTRABAR vs CANDLE-CLOSE entries, thoroughly (Zee 2026-08-07).

Same UHV lamps, three entry rules, the CURRENT exit model (v1.74: 2-bar grace,
3pt parachute during grace, 1pt ghost after, ratchet trail):

  A) DOOR      — enter the moment price crosses the lamp intrabar (price = lamp)
  B) CLOSE     — enter at the close of the first candle that CLOSES beyond the lamp
                 in the right colour (price = that close, i.e. a worse fill)
  C) LAW       — B plus Zee's fundamental law: momentum body (>=0.5) AND breakout
                 volume LOWER than the UHV's

Also splits the door by what its candle eventually did, so we can see how much of
the door's edge was really "trades that were lawful anyway".
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

GRACE = 2


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


def sim(bars, i, side, entry, cost):
    """v1.74 exits: grace bars with only the 3pt parachute, then 1pt ghost, ratchet."""
    buy = side == "BUY"
    armed, peak = False, 0.0
    for k, b in enumerate(bars[i + 1:], 1):
        adv = (entry - b.l) if buy else (b.h - entry)
        fav = (b.h - entry) if buy else (entry - b.l)
        if k <= GRACE and adv >= 3.0:
            return -3.0 - cost
        if k > GRACE and not armed and adv >= 1.0:
            return -1.0 - cost
        if fav >= 0.3:
            armed = True
        if armed:
            peak = max(peak, fav)
            if peak - ((b.l - entry) if buy else (entry - b.h)) >= max(0.2, 0.3 * peak):
                return peak - max(0.2, 0.3 * peak) - cost
    return None


def rep(name, vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        print(f"  {name:38s}  (none)")
        return
    w = sum(1 for v in vals if v > 0)
    print(f"  {name:38s} n={len(vals):3d}  WR {w/len(vals)*100:3.0f}%  "
          f"avg {statistics.mean(vals)*10:+6.2f}$  net {sum(vals)*10:+8.2f}$")


if __name__ == "__main__":
    bars = load_bars()
    setups = list({(s["open_t"], s["side"]): s for s in B.detect_full(bars)}.values())
    print(f"tape {len(bars)} bars ({bars[0].t:%m-%d %H:%M}Z -> {bars[-1].t:%m-%d %H:%M}Z) · "
          f"{len(setups)} UHV lamps\n")

    for cost, label in ((0.07, "RAW-account cost 0.07pt"), (0.20, "STANDARD cost 0.20pt")):
        door, close, law = [], [], []
        door_lawful, door_unlawful = [], []
        for s in setups:
            u = next((k for k, b in enumerate(bars) if b.t == s["uhv_t"]), None)
            ci = next((k for k, b in enumerate(bars) if b.t == s["open_t"]), None)
            if u is None or ci is None:
                continue
            side = s["side"]
            lamp = bars[u].h if side == "BUY" else bars[u].l
            # A) DOOR — first wick-cross after the UHV, filled AT the lamp
            di = None
            for k in range(u + 1, min(u + 20, len(bars) - 3)):
                if (bars[k].h > lamp) if side == "BUY" else (bars[k].l < lamp):
                    di = k
                    break
            if di is not None:
                r = sim(bars, di, side, lamp, cost)
                door.append(r)
                bk = bars[di]
                lawful = ((bk.is_bull if side == "BUY" else bk.is_bear)
                          and ((bk.c > lamp) if side == "BUY" else (bk.c < lamp))
                          and bk.body_ratio >= 0.5 and bk.v < bars[u].v)
                (door_lawful if lawful else door_unlawful).append(r)
            # B) CLOSE — the detector's own entry (closes beyond, right colour)
            close.append(sim(bars, ci, side, s["entry"], cost))
            # C) LAW — B + momentum body + lower volume than the UHV
            if bars[ci].body_ratio >= 0.5 and s["b_vol"] < s["uhv_vol"]:
                law.append(sim(bars, ci, side, s["entry"], cost))

        print(f"── {label} ──")
        rep("A) DOOR — intrabar cross at the lamp", door)
        rep("     ...whose candle was LAWFUL", door_lawful)
        rep("     ...whose candle was UNLAWFUL", door_unlawful)
        rep("B) CLOSE — closes beyond, right colour", close)
        rep("C) LAW — close + momentum + lower vol", law)
        print()
