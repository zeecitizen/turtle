"""zee_feb11_REAL_zeexit.py — model Zee's actual exit behavior: NO HARD STOP.
Hold through floating losses, scratch near breakeven (-$2 to +$0.5) when ready.
Skim peak with a generous trail. Test on his EXACT 27 entries.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"

ZEE = [
    ("01:32:19","buy"), ("01:59:04","buy"), ("02:09:38","sell"), ("02:29:02","buy"),
    ("16:49:07","buy"), ("16:52:21","buy"), ("16:54:10","buy"), ("16:58:03","buy"),
    ("17:02:45","buy"), ("17:36:11","buy"), ("17:36:13","buy"), ("17:37:26","buy"),
    ("17:49:59","buy"), ("18:24:18","buy"), ("18:41:50","buy"), ("19:08:59","sell"),
    ("19:11:05","sell"),("19:11:51","sell"),("19:20:34","sell"),("19:26:06","sell"),
    ("19:29:31","buy"), ("19:32:48","buy"), ("19:36:19","buy"), ("19:38:39","buy"),
    ("19:38:59","buy"), ("19:41:59","sell"),("19:42:26","sell"),
]
ZEE_ACTUAL = {
    "01:32:19": +7.32, "01:59:04": +6.65, "02:09:38": +11.69, "02:29:02": +20.01,
    "16:49:07": +17.12,"16:52:21": +8.85, "16:54:10": +8.26, "16:58:03": +5.73,
    "17:02:45": +54.93,"17:36:11": +3.29, "17:36:13": +14.50,"17:37:26": +7.08,
    "17:49:59": +52.78,"18:24:18": +8.51, "18:41:50": -1.43, "19:08:59": +7.82,
    "19:11:05": +3.11, "19:11:51": +16.99,"19:20:34": +14.21,"19:26:06": +14.55,
    "19:29:31": +0.84, "19:32:48": +5.89, "19:36:19": +10.60,"19:38:39": +11.02,
    "19:38:59": +0.92, "19:41:59": +1.35, "19:42:26": +9.50,
}
COST = 0.20

print("Loading...")
ticks = []
with open(TICKS, encoding="utf-8") as f:
    next(f)
    for line in f:
        parts = line.strip().split(",")
        if len(parts) < 3: continue
        try:
            t_str = parts[0]
            date_p, time_p = t_str.split(" ")
            hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
            dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
            t_ms = int(dt.timestamp() * 1000) + int(ms_str)
            ticks.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
        except: continue
print(f"  {len(ticks):,} ticks\n")
times = [t["t_ms"] for t in ticks]


def zee_to_ms(hms):
    hh, mm, ss = map(int, hms.split(":"))
    return int(datetime(2026, 2, 11, hh, mm, ss).timestamp() * 1000)


def zee_exit(entry_k, side, trail_arm, trail_gb, scratch_floor, max_hold):
    """ZEE EXIT MODEL:
       - NO hard SL — let it float
       - Peak-trail: arm at trail_arm, give back trail_gb when in profit
       - SCRATCH: when MAE has been < scratch_floor for at least 30s, exit
         at current price IF current >= scratch_floor (waiting for "near breakeven")
       - Max hold: max_hold seconds (then exit at market)"""
    entry_ms = ticks[entry_k]["t_ms"]
    entry_px = ticks[entry_k]["ask"] if side == "buy" else ticks[entry_k]["bid"]
    peak = 0.0; armed = False
    deepest_mae = 0.0
    in_scratch_zone = False
    in_scratch_since_ms = None
    for k in range(entry_k, len(ticks)):
        tk = ticks[k]; t = tk["t_ms"]
        cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
        # max hold
        if (t - entry_ms) > max_hold * 1000:
            return (cur - COST, "EOH", peak, deepest_mae)
        # peak / trail (only if positive)
        if cur > peak: peak = cur
        if peak >= trail_arm: armed = True
        if armed and cur <= peak - trail_gb:
            return (cur - COST, "TRAIL", peak, deepest_mae)
        # MAE
        if cur < deepest_mae: deepest_mae = cur
        # scratch logic: trigger when price comes BACK to scratch_floor after being below
        if not armed:
            # never been in profit zone
            if cur <= scratch_floor:
                # we're in scratch zone
                if not in_scratch_zone:
                    in_scratch_zone = True
                    in_scratch_since_ms = t
            else:
                # came back above scratch_floor: exit
                if in_scratch_zone:
                    return (cur - COST, "SCRATCH", peak, deepest_mae)
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, "EOD", peak, deepest_mae)


# Sweep
print(f"  {'arm':>5} {'gb':>5} {'scrFlr':>7} {'hold_s':>7} | "
      f"{'W':>3} {'L':>3} {'WR%':>4} {'NET$':>8} {'avgW':>6} {'avgL':>6}")
configs = [
    (1.0, 0.50, -0.5, 1800),
    (1.5, 0.80, -1.0, 1800),
    (2.0, 1.00, -1.5, 1800),
    (3.0, 1.50, -1.5, 1800),
    (5.0, 2.00, -2.0, 1800),
    (5.0, 3.00, -2.0, 1800),
    (3.0, 2.00, -2.0, 1800),
    (2.0, 1.50, -2.0, 1500),
    (1.5, 1.00, -2.0, 1500),
    (1.0, 0.50, -2.0, 1500),
    (1.0, 0.30, -1.5, 1500),
    (0.5, 0.30, -1.5, 1500),
    (1.0, 0.50, -3.0, 1800),
]
best = (-999, None, None)
for cfg in configs:
    arm, gb, sf, mh = cfg
    pnls = []
    for hms, side in ZEE:
        ms = zee_to_ms(hms)
        k = bisect.bisect_left(times, ms)
        if k >= len(ticks): continue
        pnl, why, peak, mae = zee_exit(k, side, arm, gb, sf, mh)
        pnls.append((hms, side, pnl, why, peak, mae))
    n = len(pnls); w = sum(1 for *_, p, _, _, _ in [(x[0], x[1], x[2], x[3], x[4], x[5]) for x in pnls] if p > 0)
    w = sum(1 for x in pnls if x[2] > 0)
    l = n - w
    tot = sum(x[2] for x in pnls)
    aw = sum(x[2] for x in pnls if x[2]>0)/max(1,w)
    al = sum(x[2] for x in pnls if x[2]<=0)/max(1,l)
    print(f"  {arm:>5.1f} {gb:>5.2f} {sf:>+7.2f} {mh:>7} | "
          f"{w:>3} {l:>3} {100*w/n:>3.0f}% {tot:>+8.2f} {aw:>+6.2f} {al:>+6.2f}")
    if tot > best[0]: best = (tot, cfg, pnls)

print(f"\n=== BEST: arm={best[1][0]} gb={best[1][1]} scrFlr={best[1][2]} hold={best[1][3]} → ${best[0]:+.2f} ===\n")

print(f"  {'time':>9} {'side':>4} {'mine$':>+8} {'zee$':>+7} {'why':<8} {'peak':>+7} {'mae':>+7}")
for hms, side, pnl, why, peak, mae in best[2]:
    zee_p = ZEE_ACTUAL.get(hms, 0)
    print(f"  {hms:>9} {side:>4} {pnl:>+8.2f} {zee_p:>+7.2f} {why:<8} {peak:>+7.2f} {mae:>+7.2f}")

print(f"\nZee actual total (per-setup): ${sum(ZEE_ACTUAL.values()):+.2f}, WR {sum(1 for v in ZEE_ACTUAL.values() if v>0)*100/len(ZEE_ACTUAL):.0f}%")
print(f"My best mechanical:           ${best[0]:+.2f}")
