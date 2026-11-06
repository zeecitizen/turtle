"""angel_final.py - Zee 2026-11-06: the round-figure wall at 1 touch ("be careful about if a level was touched 2x or 1x times") + the Friday
cut-off for EVERY trade (InpUhvFriCutAllNY, the last angel loss 1023-145031-B) - in the ENGINE on the angel zone (setting 2026-11-06 15-00-00),
by half, with the trades each variant removes from / adds to the current angel. Run: py research/loss_study/pockets/angel_final.py"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
NY = ZoneInfo("America/New_York")
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
    days = len({dt.datetime.fromtimestamp(float(q[1]), NY).date() for q in r})
    s = (f"{name:44s} {len(r):4d} tr ({len(r) / max(days, 1):.1f}/day on {days} days) {int(L.sum())} L WR {100 * (1 - L.mean()):6.2f}% "
         f"(Mar-Jun {100 * (1 - L[a].mean()):6.2f} / Jul-Nov {100 * (1 - L[~a].mean()):6.2f}) net {r[:, 6].sum():+7.0f}")
    if ref is not None:
        gone = [k for k in ref if k not in d]; new = [k for k in d if k not in ref]
        gw = [k for k in gone if ref[k] >= 0]; gl = [k for k in gone if ref[k] < 0]
        s += f" | removes {len(gw)} W {len(gl)} L {gl if gl else ''} adds {len(new)} ({sum(1 for k in new if d[k] < 0)} L)"
    print(s, flush=True)


ANGEL = "2026-11-06 15-00-00.json"
ref, r0 = run(ANGEL, {})
line("ANGEL now (wall 3 touches)", ref, r0)
w1, r1 = run(ANGEL, {"InpUhvWallTouches": "1"})
line("+ wall 1 touch", w1, r1, ref)
for H in (8, 9, 10, 11, 12, 13):
    d, r = run(ANGEL, {"InpUhvWallTouches": "1", "InpUhvFriCutAllNY": str(H)})
    line(f"+ wall 1 touch + Friday from {H} NY (all trades)", d, r, ref)
fri = [k for k in ref if dt.datetime.strptime("2026" + k[:11], "%Y%m%d-%H%M%S").replace(tzinfo=dt.timezone.utc).astimezone(NY).weekday() == 4]
print(f"angel trades on Fridays: {len(fri)} ({sum(1 for k in fri if ref[k] < 0)} L)")
