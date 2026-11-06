"""lock_ride.py - Zee 2026-11-01: "if 100% of the trades are going uptil +400 then ... move the SL to 400 profit price when we reach 400 in profit
and let the trade gather further profits without losing the initial 400 ... keep holding till it makes the target of around 5400 from setting A".

Setting B = "2026-10-30 23-08-23" (399 trades, 99.7%, TP 20 pips = $2 of price = $400 at 2 lots, stop $26 = $5,200, lab target $26 never reached).
Every variant here is a set of REAL EA inputs (Exit Lab, modes 1-2) on top of B's entries, run in the Turtle TV tester on the 4-year m15 data:
    py lock_ride.py all | <family>[,<family>] [--sets '{"InpXBeR": 0.0769, ...}' --name X]     THREADS=4
Rows -> research/lock_ride.json (merged by name). R = $26 (B's InpSlUsd), so $x of price = x/26 R.
Tester hypotheses only: the finalists go to MT5 (mt5_years.py "save:<name>"). The tester reads lab rows 4-8% high vs MT5 (Exit Lab memory)."""
import json, os, sys, time, numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view"); sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab")
import server, sim

HERE = os.path.dirname(os.path.abspath(__file__))
SV = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
NAME_B = "2026-10-30 23-08-23"
B = {k: str(v) for k, v in json.load(open(SV + "\\" + NAME_B + ".json"))["inputs"].items()}
R0 = float(B["InpSlUsd"])                                   # 26: the first stop, $ of price (InpSlMode 2) = 1 R
LOTS = float(B["InpLots"]); PER = 100.0 * LOTS               # $ of P&L per $1 of price
OUT = os.path.join(HERE, "lock_ride.json")
D = sim.data("m15")
DAYS = np.unique((D["t15"] // 86400)[(((D["t15"] // 86400) + 4) % 7 >= 1) & (((D["t15"] // 86400) + 4) % 7 <= 5)])
MID = 1735689600                                             # 2025-01-01: halves 2023-24 / 2025-26


def r(usd):
    """$ of price as a share of R, as the EA input string"""
    return f"{usd / R0:.6f}"


def met(t):
    if not len(t):
        return dict(n=0, net=0)
    p = t[:, 6]; h1 = t[:, 1] < MID
    eq = np.cumsum(p); w = p[p > 0]; l = p[p <= 0]
    dd = float((np.maximum.accumulate(eq) - eq).max())
    td = np.unique(t[:, 1] // 86400)
    why = {int(k): int(v) for k, v in zip(*np.unique(t[:, 13], return_counts=True))}
    return dict(n=len(p), L=int((p <= 0).sum()), wr=round(100 * (p > 0).mean(), 2), net=round(float(p.sum())), pf=round(float(w.sum() / max(1.0, -l.sum())), 2),
                dd=round(dd), worst=round(float(p.min())), avg_win=round(float(w.mean())) if len(w) else 0, avg_loss=round(float(l.mean())) if len(l) else 0,
                full_stops=int((p < -4000).sum()), net1=round(float(p[h1].sum())), net2=round(float(p[~h1].sum())),
                wr1=round(100 * (p[h1] > 0).mean(), 1) if h1.any() else 0, wr2=round(100 * (p[~h1] > 0).mean(), 1) if (~h1).any() else 0,
                days=len(td), hold_med=round(float(np.median((t[:, 4] - t[:, 1]) / 60))), hold_p90=round(float(np.percentile((t[:, 4] - t[:, 1]) / 60, 90))),
                swap=round(float(t[:, 7].sum())), why=why, fri=why.get(15, 0), mfe_med=round(float(np.median(t[:, 15])), 1))


def run(sets):
    inp = {**B, **{k: str(v) for k, v in sets.items()}}
    tr, _, _ = sim.simulate(server.full_inputs(inp), ds="m15")
    return np.array([x for x in tr if x[10] == 0])


# ---- the variants: name -> (family, sets)
NO_TP = {"InpFixTpPips": 0}
TGT26 = {"InpXTgt": 4, "InpXTgtK": 26}                      # B's own lab target ($26 = $5,200)
TGT_NONE = {"InpXTgt": 1}
A_EXITS = {"InpExitMode": 2, "InpXCx": 3, "InpXCxN": 3, "InpXCxWhen": 1, "InpXCxAfter": 2, "InpXCxBuf": 0.1, "InpXTgt": 4, "InpXTgtK": 27, "InpXFriHour": 23,
           "InpXP1R": 2.75, "InpXTr": 4, "InpXTrAct": 1.75}
A_STOP = {"InpSlMode": 1, "InpSlAtrMult": 6.1, "InpXLossCap": 46.5}
V = {}


def add(fam, name, *parts):
    s = {}
    for p in parts:
        s.update(p)
    V[name] = (fam, s)


add("base", "B baseline: TP $2, stop $26", {})
add("base", "B natural path: no TP, no target (stop + Friday)", NO_TP, TGT_NONE)
add("base", "B no TP, target $26", NO_TP, TGT26)
add("base", "B no TP, target $26, trail off", NO_TP, TGT26, {"InpXTr": 0})
# Zee's rule, literally and with a gap: once +$y, the stop to +$2 (InpXBeR = y R, InpXBeOff = 2/26 R); then ride to the $26 target
for y in (2, 2.5, 3, 4, 5, 6, 8, 10):
    add("lock", f"lock +$2 at +${y:g}, target $26", NO_TP, TGT26, {"InpXBeR": r(y), "InpXBeOff": r(2)})
    add("lock", f"lock +$2 at +${y:g}, no target", NO_TP, TGT_NONE, {"InpXBeR": r(y), "InpXBeOff": r(2)})
for y in (2, 3, 4, 6):                                       # breakeven instead of +$2 (nothing lost, nothing banked)
    add("lock", f"breakeven at +${y:g}, target $26", NO_TP, TGT26, {"InpXBeR": r(y), "InpXBeOff": 0})
for lk in (1, 1.5):                                          # lock less than the full $2
    add("lock", f"lock +${lk:g} at +$3, target $26", NO_TP, TGT26, {"InpXBeR": r(3), "InpXBeOff": r(lk)})
for tg in (6, 10, 13, 20, 40):                               # lock +$2 at +$4 with other targets
    add("lock", f"lock +$2 at +$4, target ${tg}", NO_TP, {"InpXTgt": 4, "InpXTgtK": tg, "InpXBeR": r(4), "InpXBeOff": r(2)})
# the ladder: every $s of best, the stop one step behind (at +$2 best -> entry, +$4 -> +$2, ...)
for s in (2, 3, 4, 5, 6, 8, 13):
    add("ladder", f"ladder every ${s:g}, target $26", NO_TP, TGT26, {"InpXLockR": r(s)})
    add("ladder", f"ladder every ${s:g}, no target", NO_TP, TGT_NONE, {"InpXLockR": r(s)})
add("ladder", "ladder every $2 + lock +$2 at +$4, target $26", NO_TP, TGT26, {"InpXLockR": r(2), "InpXBeR": r(4), "InpXBeOff": r(2)})
# $ trail from the best, starting once +$2 (K=2: at +$2 the stop is at the entry; K=4: at +$6 it is at +$2)
for k in (2, 3, 4, 6, 8, 10, 13):
    add("trail$", f"trail ${k:g} from the best after +$2, target $26", NO_TP, TGT26, {"InpXTr": 1, "InpXTrK": k, "InpXTrAct": r(2)})
    add("trail$", f"trail ${k:g} from the best after +$2, no target", NO_TP, TGT_NONE, {"InpXTr": 1, "InpXTrK": k, "InpXTrAct": r(2)})
for k in (4, 6, 8):                                          # lock +$2 at +$4 first, then the $ trail
    add("trail$", f"lock +$2 at +$4 + trail ${k:g} from the best, target $26", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 1, "InpXTrK": k, "InpXTrAct": r(4)})
    add("trail$", f"lock +$2 at +$4 + trail ${k:g} from the best, no target", NO_TP, TGT_NONE, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 1, "InpXTrK": k, "InpXTrAct": r(4)})
# ATR trail / keep-% trail after the lock
for k in (0.5, 1, 1.5, 2, 3):
    add("trailATR", f"lock +$2 at +$4 + trail {k:g} ATR from the best, target $26", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 2, "InpXTrK": k, "InpXTrAct": r(4)})
    add("trailATR", f"lock +$2 at +$4 + trail {k:g} ATR from the best, no target", NO_TP, TGT_NONE, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 2, "InpXTrK": k, "InpXTrAct": r(4)})
for k in (50, 65, 80):
    add("trailATR", f"lock +$2 at +$4 + keep {k}% of the best profit, target $26", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 3, "InpXTrK": k, "InpXTrAct": r(6)})
# candle-structure trails after the lock (4 fast EMA, 5 slow EMA, 6 previous candle, 7 N candles, 8 last swing) - at the candle close
for tr, lab, k in ((4, "fast EMA", 25.75), (5, "slow EMA", 25.75), (6, "previous candle", 25.75), (7, "last 2 candles", 2), (7, "last 3 candles", 3), (8, "last swing", 25.75)):
    add("trailBar", f"lock +$2 at +$4 + trail {lab}, target $26", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": tr, "InpXTrK": k, "InpXTrAct": r(4)})
    add("trailBar", f"lock +$2 at +$4 + trail {lab}, no target", NO_TP, TGT_NONE, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": tr, "InpXTrK": k, "InpXTrAct": r(4)})
# bank part at +$2 and ride the rest
for be in (False, True):
    for tg in (26, 13, 40):
        add("partial", f"half off at +$2{' + BE' if be else ''}, rest to target ${tg}", NO_TP, {"InpXTgt": 4, "InpXTgtK": tg, "InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": str(be).lower()})
    add("partial", f"half off at +$2{' + BE' if be else ''}, rest no target", NO_TP, TGT_NONE, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": str(be).lower()})
add("partial", "half off at +$2 + BE, rest: lock +$2 at +$4, target $26", NO_TP, TGT26, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpXBeR": r(4), "InpXBeOff": r(2)})
add("partial", "half off at +$2 + BE, rest: trail $6 from the best, target $26", NO_TP, TGT26, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpXTr": 1, "InpXTrK": 6, "InpXTrAct": r(4)})
add("partial", "half off at +$2 + BE, rest: trail fast EMA, no target", NO_TP, TGT_NONE, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpXTr": 4, "InpXTrAct": r(2)})
add("partial", "half off at +$2, quarter at +$10 + BE, rest to $26", NO_TP, TGT26, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpXP2R": r(10), "InpXP2Frac": 0.5})
# barbell: the broker TP stays for the whole trade, half banked at +$2 first
for tp in (30, 40, 60, 100, 150, 260):
    add("barbell", f"half off at +$2 + BE, broker TP ${tp / 10:g}", {"InpFixTpPips": tp, "InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", **TGT_NONE})
for tp in (30, 40, 60):
    add("barbell", f"broker TP ${tp / 10:g} only (no lock)", {"InpFixTpPips": tp, **TGT_NONE})
    add("barbell", f"lock +$2 at +$3, broker TP ${tp / 10:g}", {"InpFixTpPips": tp, "InpXBeR": r(3), "InpXBeOff": r(2), **TGT_NONE})
# A's exits on B's entries
add("Aexits", "A's exits (mode 2, EMA cross, $27 target), B's $26 stop", NO_TP, A_EXITS)
add("Aexits", "A's exits + A's stop (6.1 ATR capped $46.5)", NO_TP, A_EXITS, A_STOP)
add("Aexits", "A's exits, B's stop, lock +$2 at +$4", NO_TP, A_EXITS, {"InpXBeR": r(4), "InpXBeOff": r(2)})
add("Aexits", "A's exits, B's stop, half off at +$2 + BE", NO_TP, A_EXITS, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true"})
add("Aexits", "mode 2 close-back only, B's stop, lock +$2 at +$4, target $26", NO_TP, TGT26, {"InpExitMode": 2, "InpXBeR": r(4), "InpXBeOff": r(2)})
add("Aexits", "EMA cross exit (A's) + lock +$2 at +$4, target $26, mode 1", NO_TP, TGT26, {"InpXCx": 3, "InpXCxN": 3, "InpXCxWhen": 1, "InpXCxAfter": 2, "InpXBeR": r(4), "InpXBeOff": r(2)})
# more positions, so B's $400 pops keep flowing while a runner is held
for mp in (2, 3):
    add("maxpos", f"B baseline with {mp} positions", {"InpMaxPos": mp})
    add("maxpos", f"lock +$2 at +$4, target $26, {mp} positions", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpMaxPos": mp})
    add("maxpos", f"half off at +$2 + BE, rest to $26, {mp} positions", NO_TP, TGT26, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpMaxPos": mp})
    add("maxpos", f"lock +$2 at +$4 + trail $6 from the best, target $26, {mp} positions", NO_TP, TGT26, {"InpXBeR": r(4), "InpXBeOff": r(2), "InpXTr": 1, "InpXTrK": 6, "InpXTrAct": r(4), "InpMaxPos": mp})
    add("maxpos", f"half off at +$2 + BE, broker TP $6, {mp} positions", {"InpFixTpPips": 60, "InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true", "InpMaxPos": mp, **TGT_NONE})
    add("maxpos", f"ladder every $4, target $26, {mp} positions", NO_TP, TGT26, {"InpXLockR": r(4), "InpMaxPos": mp})


# Zee 2026-11-01: "instead of 400 each win could bring 800 .. that would also be a great improvement": a bigger broker TP, with a protection
# for the trades that reach +$2 but not the TP (naked, the 6-10% that stall between +$2 and +$4 die at the full stop)
MP3 = {"InpMaxPos": 3, "InpExtraDir": 1}
for tp in (30, 40, 50, 60):
    T = {"InpFixTpPips": tp}; d = f"${tp / 10:g}"
    add("tp800", f"TP {d} only", T)
    add("tp800", f"TP {d}, BE at +$2", T, {"InpXBeR": r(2), "InpXBeOff": 0})
    add("tp800", f"TP {d}, BE at +$1.5", T, {"InpXBeR": r(1.5), "InpXBeOff": 0})
    add("tp800", f"TP {d}, lock +$1 at +$2", T, {"InpXBeR": r(2), "InpXBeOff": r(1)})
    add("tp800", f"TP {d}, lock +$1 at +$1.5", T, {"InpXBeR": r(1.5), "InpXBeOff": r(1)})
    add("tp800", f"TP {d}, lock +$0.5 at +$1.5", T, {"InpXBeR": r(1.5), "InpXBeOff": r(0.5)})
    add("tp800", f"TP {d}, lock +$1.5 at +$2.5", T, {"InpXBeR": r(2.5), "InpXBeOff": r(1.5)})
    add("tp800", f"TP {d}, ladder every $1", T, {"InpXLockR": r(1)})
    add("tp800", f"TP {d}, ladder every $1.5", T, {"InpXLockR": r(1.5)})
    add("tp800", f"TP {d}, half off at +$2 (no BE)", T, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "false"})
    add("tp800", f"TP {d}, half off at +$2 + lock +$1 at +$2", T, {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "false", "InpXBeR": r(2), "InpXBeOff": r(1)})
    for lab, s in (("BE at +$2", {"InpXBeR": r(2), "InpXBeOff": 0}), ("lock +$1 at +$2", {"InpXBeR": r(2), "InpXBeOff": r(1)}),
                   ("lock +$1 at +$1.5", {"InpXBeR": r(1.5), "InpXBeOff": r(1)}), ("ladder every $1", {"InpXLockR": r(1)}),
                   ("half off at +$2 + BE", {"InpXP1R": r(2), "InpXP1Frac": 0.5, "InpXP1Be": "true"})):
        add("tp800", f"TP {d}, {lab}, 3 positions same-side", T, s, MP3)


def load():
    return {x["name"]: x for x in json.load(open(OUT))} if os.path.exists(OUT) else {}


class _lock:
    """several processes add rows at once (the refiners' --sets runs): one writer at a time"""
    def __enter__(self):
        for _ in range(600):
            try:
                self.fd = os.open(OUT + ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY); return self
            except FileExistsError:
                time.sleep(0.1)
        raise TimeoutError("lock_ride.json.lock is stuck: delete it")

    def __exit__(self, *a):
        os.close(self.fd); os.remove(OUT + ".lock")


def save(new):
    """merge these rows into the file under the lock (other processes' rows are kept)"""
    with _lock():
        rows = load(); rows.update(new)
        json.dump(sorted(rows.values(), key=lambda x: -x["m"].get("net", 0)), open(OUT, "w"), indent=1)
    return rows


def one(name, fam, sets):
    t0 = time.time(); m = met(run(sets))
    return {"name": name, "family": fam, "sets": {k: str(v) for k, v in sets.items()}, "m": m, "secs": round(time.time() - t0, 1)}


def line(x):
    m = x["m"]
    if not m.get("n"):
        return f"{x['name'][:64]:64s} no trades"
    return (f"{x['name'][:64]:64s} n={m['n']:4d} WR={m['wr']:6.2f} net={m['net']:+9,d} PF={m['pf']:6.2f} DD={m['dd']:7,d} worst={m['worst']:7,d} "
            f"W={m['avg_win']:6,d} L={m['avg_loss']:7,d} stops={m['full_stops']:3d} h1={m['net1']:+8,d} h2={m['net2']:+8,d} days={m['days']:3d} hold={m['hold_med']:5d}m fri={m['fri']:3d}")


if __name__ == "__main__":
    args = sys.argv[1:]
    rows = load()
    if "--sets" in args:
        sets = json.loads(args[args.index("--sets") + 1]); name = args[args.index("--name") + 1] if "--name" in args else json.dumps(sets, sort_keys=True)
        x = one(name, "adhoc", sets); save({name: x}); print(line(x)); print(json.dumps(x["m"])); sys.exit()
    fams = set(args[0].split(",")) if args and args[0] != "all" else None
    todo = [(n, f, s) for n, (f, s) in V.items() if (fams is None or f in fams) and n not in rows]
    print(f"{len(todo)} variants to run ({len(rows)} already in {os.path.basename(OUT)})", flush=True)
    run({})                                                    # warm the caches before the pool
    with ThreadPoolExecutor(int(os.environ.get("THREADS", "4"))) as ex:
        for x in ex.map(lambda a: one(*a), todo):
            rows = save({x["name"]: x}); print(line(x), flush=True)
    print("\n==== all rows by net ====")
    for x in sorted(rows.values(), key=lambda x: -x["m"].get("net", 0)):
        if fams is None or x["family"] in fams or x["family"] == "base":
            print(f"[{x['family']:8s}] " + line(x))
