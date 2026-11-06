"""wall_touches.py - Zee 2026-11-06: "If a level was touched 3+ times -> we should also be careful about if a level was touched 2x or 1x times
-> if all we're loosing is that 1 or 2 trades in this region -> we can cut them risky ones off.. coz one day the lossy trade might return but
this time it didnt touch 3x times but maybe 2 x times". The round-figure wall (InpUhvWall) at 1 / 2 / 3 touches, 00 and 50 figures, 60 / 120
candles - in the ENGINE, on the angel zone (setting 2026-11-06 15-00-00) and on the base 97.7% setting, by half, with the trades each variant
removes from / adds to the current angel setting. Run: py research/loss_study/pockets/wall_touches.py"""
import datetime as dt
import json
import os
import sys

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")


def tid(r):
    return dt.datetime.fromtimestamp(float(r[1]), dt.timezone.utc).strftime("%m%d-%H%M%S") + ("-B" if r[0] > 0 else "-S")


def run(fn, x):
    B = json.load(open(os.path.join(SAVED, fn), encoding="utf-8"))["inputs"]
    tr, _, _ = U.simulate(dict(B, **x))
    r = tr[tr[:, 10] == 0]
    return {tid(q): float(q[6]) for q in r}, r


def line(name, d, r, ref=None):
    L = r[:, 6] < 0; a = r[:, 1] < SPLIT
    s = (f"{name:44s} {len(r):5d} tr {int(L.sum()):3d} L WR {100 * (1 - L.mean()):6.2f}% (Mar-Jun {100 * (1 - L[a].mean()):6.2f} / "
         f"Jul-Nov {100 * (1 - L[~a].mean()):6.2f}) net {r[:, 6].sum():+8.0f}")
    if ref is not None:
        gone = [k for k in ref if k not in d]; new = [k for k in d if k not in ref]
        gw = [k for k in gone if ref[k] >= 0]; gl = [k for k in gone if ref[k] < 0]
        s += f" | removes {len(gw)} W {len(gl)} L {gl if gl else ''} adds {len(new)} ({sum(1 for k in new if d[k] < 0)} L)"
        if 0 < len(gw) <= 6:
            s += f" winners cut: {gw}"
    print(s, flush=True)


ANGEL = "2026-11-06 15-00-00.json"
BASE = "2026-11-05 05-45-38.json"
ref, r0 = run(ANGEL, {})
line("ANGEL now (wall 1 pip, 3 touches, 00, 60)", ref, r0)
noW, r1 = run(ANGEL, {"InpUhvWall": "0"})
line("ANGEL without the wall", noW, r1, ref)
for T in (3, 2, 1):
    for fig in (100, 50):
        for N in (60, 120):
            for X in (1, 2):
                if (T, fig, N, X) == (3, 100, 60, 1):
                    continue
                x = {"InpUhvWall": str(X), "InpUhvWallTouches": str(T), "InpUhvWallFig": str(fig), "InpUhvWallBars": str(N)}
                d, r = run(ANGEL, x)
                line(f"ANGEL wall {X}p, {T} touch, fig {fig}, {N} bars", d, r, ref)
print("--- the same family with NO round figure (any level, fig step 1 pip)")
for T in (3, 2):
    for N in (60, 120):
        d, r = run(ANGEL, {"InpUhvWall": "1", "InpUhvWallTouches": str(T), "InpUhvWallFig": "1", "InpUhvWallBars": str(N)})
        line(f"ANGEL wall 1p, {T} touch, ANY level, {N} bars", d, r, ref)
print("--- on the base 97.7% setting (no angel)")
bref, rb = run(BASE, {})
line("BASE", bref, rb)
for T in (3, 2, 1):
    d, r = run(BASE, {"InpUhvWall": "1", "InpUhvWallTouches": str(T)})
    line(f"BASE + wall 1p, {T} touch, fig 100, 60 bars", d, r, bref)
