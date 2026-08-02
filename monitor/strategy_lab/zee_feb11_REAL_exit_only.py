"""zee_feb11_REAL_exit_only.py — take Zee's EXACT 24 entry timestamps + sides on
REAL Blueberry Feb 11 ticks. Test exit configs to find one that produces +$835/94%.
This isolates the exit problem from the entry problem.
"""
import sys, bisect
from datetime import datetime, timezone, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"

# Zee's 27 distinct entries — broker time on Blueberry (server time UTC offset varies but matches CSV format)
# CSV is stored in broker time directly. Zee's PDF entries are broker time too.
ZEE = [
    ("01:32:19","buy"), ("01:59:04","buy"), ("02:09:38","sell"), ("02:29:02","buy"),
    ("16:49:07","buy"), ("16:52:21","buy"), ("16:54:10","buy"), ("16:58:03","buy"),
    ("17:02:45","buy"), ("17:36:11","buy"), ("17:36:13","buy"), ("17:37:26","buy"),
    ("17:49:59","buy"), ("18:24:18","buy"), ("18:41:50","buy"), ("19:08:59","sell"),
    ("19:11:05","sell"),("19:11:51","sell"),("19:20:34","sell"),("19:26:06","sell"),
    ("19:29:31","buy"), ("19:32:48","buy"), ("19:36:19","buy"), ("19:38:39","buy"),
    ("19:38:59","buy"), ("19:41:59","sell"),("19:42:26","sell"),
]
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
        except (ValueError, IndexError): continue
print(f"  {len(ticks):,} ticks\n")
times = [t["t_ms"] for t in ticks]


def zee_to_ms(hms):
    hh, mm, ss = map(int, hms.split(":"))
    dt = datetime(2026, 2, 11, hh, mm, ss)
    return int(dt.timestamp() * 1000)


def exit_at(entry_k, side, trail_arm, trail_gb, skim, scr_sec, max_loss, max_hold):
    entry_ms = ticks[entry_k]["t_ms"]
    entry_px = ticks[entry_k]["ask"] if side == "buy" else ticks[entry_k]["bid"]
    peak = 0.0; armed = False
    for k in range(entry_k, len(ticks)):
        tk = ticks[k]; t = tk["t_ms"]
        if (t - entry_ms) > max_hold * 1000:
            cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
            return (cur - COST, "EOH", peak)
        cur = (tk["bid"] - entry_px) if side == "buy" else (entry_px - tk["ask"])
        if cur >= skim: return (cur - COST, "SKIM", peak)
        if cur > peak: peak = cur
        if peak >= trail_arm: armed = True
        if armed and cur <= peak - trail_gb: return (cur - COST, "TRAIL", peak)
        if cur <= -max_loss: return (-max_loss - COST, "CB", peak)
        if (t - entry_ms) > scr_sec * 1000 and peak < trail_arm and cur <= 0:
            return (cur - COST, "SCRATCH", peak)
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, "EOD", peak)


# Run Zee's 27 entries through various exits
configs = [
    # (arm, gb, skim, scratch_sec, max_loss, max_hold)
    (1.0, 0.30, 20.0,  90, 2.0,  900),
    (1.0, 0.50, 20.0,  90, 2.0,  900),
    (1.5, 0.50, 20.0,  60, 2.0,  900),
    (1.5, 0.80, 20.0, 120, 3.0, 1200),
    (2.0, 1.00, 20.0, 180, 3.0, 1500),
    (3.0, 2.00, 30.0, 300, 4.0, 1800),
    (5.0, 3.00, 50.0, 600, 5.0, 1800),
    (0.5, 0.20, 15.0,  60, 1.6,  600),   # tight Zee-skim
    (0.5, 0.30, 30.0,  30, 1.6,  600),
    # No trail, just skim+CB
    (99.0, 99.0, 12.0, 60, 1.6, 600),
    (99.0, 99.0, 50.0, 60, 1.6, 1800),
    # Very wide trail
    (1.0, 5.00, 50.0, 1800, 5.0, 1800),
    (2.0, 5.00, 50.0, 1800, 5.0, 1800),
]

print(f"{'arm':>5} {'gb':>5} {'skim':>5} {'scr':>5} {'CB':>5} {'hold':>5} | "
      f"{'n':>3} {'W':>3} {'L':>3} {'WR%':>4} {'NET$':>7} {'avgW':>6} {'avgL':>6}")
best = (-99999, None, None)
for cfg in configs:
    arm, gb, sk, sc, ml, mh = cfg
    pnls = []
    for hms, side in ZEE:
        ms = zee_to_ms(hms)
        k = bisect.bisect_left(times, ms)
        if k >= len(ticks): continue
        pnl, why, peak = exit_at(k, side, arm, gb, sk, sc, ml, mh)
        pnls.append((pnl, why, peak, hms, side))
    n = len(pnls); w = sum(1 for p,*_ in pnls if p>0); l = n - w
    tot = sum(p for p,*_ in pnls)
    aw = sum(p for p,*_ in pnls if p>0)/max(1,w)
    al = sum(p for p,*_ in pnls if p<=0)/max(1,l)
    print(f"{arm:>5.1f} {gb:>5.2f} {sk:>5.1f} {sc:>5} {ml:>5.1f} {mh:>5} | "
          f"{n:>3} {w:>3} {l:>3} {100*w/n:>3.0f}% {tot:>+7.1f} {aw:>+6.2f} {al:>+6.2f}")
    if tot > best[0]: best = (tot, cfg, pnls)

print(f"\n=== BEST: {best[1]} → NET ${best[0]:+.2f} ===")
print(f"\nPer-trade detail (best config):")
print(f"  {'time':>9} {'side':>4} {'pnl':>7} {'why':<8} {'peak':>7}")
for p, why, peak, hms, side in best[2]:
    print(f"  {hms:>9} {side:>4} {p:>+7.2f} {why:<8} {peak:>+7.2f}")

# Zee actual numbers per setup (first fill of each cluster)
zee_actual = {
    "01:32:19": +7.32, "01:59:04": +6.65, "02:09:38": +11.69, "02:29:02": +20.01,
    "16:49:07": +17.12,"16:52:21": +8.85, "16:54:10": +8.26, "16:58:03": +5.73,
    "17:02:45": +54.93,"17:36:11": +3.29, "17:36:13": +14.50,"17:37:26": +7.08,
    "17:49:59": +52.78,"18:24:18": +8.51, "18:41:50": -1.43, "19:08:59": +7.82,
    "19:11:05": +3.11, "19:11:51": +16.99,"19:20:34": +14.21,"19:26:06": +14.55,
    "19:29:31": +0.84, "19:32:48": +5.89, "19:36:19": +10.60,"19:38:39": +11.02,
    "19:38:59": +0.92, "19:41:59": +1.35, "19:42:26": +9.50,
}
zee_total = sum(zee_actual.values())
zee_w = sum(1 for v in zee_actual.values() if v > 0)
print(f"\nZee actual (1 fill per setup): n={len(zee_actual)} W={zee_w} L={len(zee_actual)-zee_w}"
      f" WR={100*zee_w/len(zee_actual):.0f}% NET=${zee_total:+.2f}")
