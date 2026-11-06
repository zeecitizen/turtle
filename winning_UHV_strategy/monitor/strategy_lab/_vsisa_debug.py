"""Self-contained diagnostic for VSISA detection."""
import os, csv, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path
from datetime import datetime, timedelta

TICKS_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

def load_ticks(date_str):
    f = TICKS_DIR / f"shano_ticks_{date_str}.csv"
    if not f.exists(): return []
    out = []
    with f.open(encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            try:
                ts = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S")
                mid = (float(row[2]) + float(row[3])) / 2.0
                out.append((ts, mid))
            except: pass
    return out

def aggregate(ticks, minutes):
    bars = {}
    for ts, mid in ticks:
        b_ts = ts.replace(second=0, microsecond=0)
        b_ts = b_ts.replace(minute=(b_ts.minute // minutes) * minutes)
        b = bars.setdefault(b_ts, {"o": mid, "h": mid, "l": mid, "c": mid, "v": 0, "ts": b_ts})
        b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid; b["v"] += 1
    return [bars[k] for k in sorted(bars)]

dates = ["2026-04-29","2026-04-30","2026-05-01","2026-05-04","2026-05-05","2026-05-06","2026-05-07"]
all_ticks = []
for d in dates:
    all_ticks.extend(load_ticks(d))

m5 = aggregate(all_ticks, 5)
print(f"M5 bars: {len(m5)}")

vols = sorted(b["v"] for b in m5)
print(f"\nM5 volume distribution:")
for pct in [10, 25, 50, 75, 90, 95, 99]:
    print(f"  {pct}%: {vols[int(len(vols)*pct/100)]}")

# Stage-by-stage funnel
opp_dir = engulf = engulf_lowvol = engulf_bigvol_q75 = engulf_bigvol_q90 = engulf_low_q60 = engulf_low_q40 = 0

# precompute "big vol" threshold = top quartile of all M5 vols
threshold_q75 = vols[int(len(vols)*0.75)]
threshold_q90 = vols[int(len(vols)*0.90)]
print(f"\n75th pct vol = {threshold_q75}, 90th pct = {threshold_q90}")

for idx in range(1, len(m5)):
    e, r = m5[idx-1], m5[idx]
    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir: continue
    opp_dir += 1
    eb_lo, eb_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    rb_lo, rb_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    if not (rb_lo <= eb_lo and rb_hi >= eb_hi): continue
    engulf += 1
    # Different low-vol ratios
    if r["v"] < 0.6 * e["v"]: engulf_low_q60 += 1
    if r["v"] < 0.4 * e["v"]: engulf_low_q40 += 1
    # Different big-vol thresholds
    if e["v"] >= threshold_q75 and r["v"] < 0.6 * e["v"]: engulf_bigvol_q75 += 1
    if e["v"] >= threshold_q90 and r["v"] < 0.6 * e["v"]: engulf_bigvol_q90 += 1
    if r["v"] < 0.6 * e["v"]:  # any vol on effort, low on reaction
        engulf_lowvol += 1

print(f"\n=== Pattern detection funnel ===")
print(f"  Opposite-dir consecutive: {opp_dir}")
print(f"  + Full-body engulf:       {engulf}  ({100*engulf/max(1,opp_dir):.1f}%)")
print(f"  + Reaction vol < 60% effort: {engulf_lowvol}  ({100*engulf_lowvol/max(1,engulf):.1f}%)")
print(f"  + Reaction vol < 40% effort: {engulf_low_q40}  ({100*engulf_low_q40/max(1,engulf):.1f}%)")
print(f"  + Effort >= 75th pct vol AND reaction < 60%: {engulf_bigvol_q75}")
print(f"  + Effort >= 90th pct vol AND reaction < 60%: {engulf_bigvol_q90}")
