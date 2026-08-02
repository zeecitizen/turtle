"""zee_feb11_REAL_timed.py — restrict entries to Zee's actual Feb 11 trading windows:
01:30-02:30 (Asian) + 16:45-19:45 (London close + NY) broker EET.
Then sweep entry/exit params within those 4 hours.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"
COST = 0.20; TREND_LB = 30; RETRO = 12

def in_zee_window(t):
    """Broker EET. True during 01:30-02:30 OR 16:45-19:45."""
    mins = t.hour * 60 + t.minute
    return (90 <= mins <= 150) or (1005 <= mins <= 1185)

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
print(f"  {len(ticks):,} ticks")
m1 = []; cur = None
for tk in ticks:
    m_key = tk["t_ms"] // 60000
    mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1, "t_end_ms": (m_key + 1) * 60000 - 1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid); cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
print(f"  {len(m1)} M1 bars  ({sum(1 for b in m1 if in_zee_window(b['t']))} in Zee windows)\n")

N = len(m1); tick_times = [t["t_ms"] for t in ticks]


def trend_dir(i, lb=TREND_LB):
    if i < lb: return 0
    W = m1[i - lb:i]; h = lb // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0

def er_at(i):
    if i < TREND_LB: return 0.0
    cs = [b["c"] for b in m1[i - TREND_LB:i + 1]]
    net = abs(cs[-1] - cs[0])
    path = sum(abs(cs[k] - cs[k-1]) for k in range(1, len(cs)))
    return net / path if path > 1e-9 else 0.0

def detect(i, side, params):
    """params = (er_min, body_pct_min, body_min, n_pats_req, allow_counter_trend)"""
    er_min, bp_min, body_min, n_req, allow_ct = params
    if i < TREND_LB + 5: return None
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i]; R = m1[i - RETRO:i]; L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    body = abs(bar["c"] - bar["o"])
    body_pct = body / (bar["h"] - bar["l"]) if (bar["h"] - bar["l"]) > 0 else 0
    green = bar["c"] > bar["o"]
    td = trend_dir(i); er = er_at(i)

    if er < er_min: return None
    if body_pct < bp_min: return None
    if body < body_min: return None
    if side == "buy" and not green: return None
    if side == "sell" and green: return None
    if not allow_ct:
        if side == "buy" and td != +1: return None
        if side == "sell" and td != -1: return None

    patterns = []
    strong = False
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] > uhv["h"] and bar["o"] <= uhv["h"] + 0.5:
                patterns.append("UHV")
                if uhv["v"] >= 2.0 * avgv: strong = True
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] > 1.2 * avgv and bar["c"] < uhv["l"] and bar["o"] >= uhv["l"] - 0.5:
                patterns.append("UHV")
                if uhv["v"] >= 2.0 * avgv: strong = True
    dead = None
    for b in [prev, prev2, prev3]:
        if b["v"] < 0.6 * avgv and (b["h"] - b["l"]) < 0.6 * avgr:
            dead = b; break
    if dead is not None:
        if side == "buy" and bar["c"] > dead["h"]: patterns.append("NSND")
        elif side == "sell" and bar["c"] < dead["l"]: patterns.append("NSND")
    prior = m1[i - 30:i - 2]
    if prior:
        if side == "buy":
            plo = min(b["l"] for b in prior)
            for b in [prev, bar]:
                if b["l"] < plo and b["c"] > plo: patterns.append("SWEEP"); break
        else:
            phi = max(b["h"] for b in prior)
            for b in [prev, bar]:
                if b["h"] > phi and b["c"] < phi: patterns.append("SWEEP"); break
    if body > 1.3 * avgbody:
        if side == "buy" and td == +1: patterns.append("MOM")
        elif side == "sell" and td == -1: patterns.append("MOM")

    if len(patterns) >= n_req or strong:
        return patterns
    return None


def simulate(signal_ms, side, trail_arm, trail_gb, max_loss, max_hold=1800, skim=50.0):
    k0 = bisect.bisect_left(tick_times, signal_ms)
    if k0 >= len(ticks): return None
    entry_ms = ticks[k0]["t_ms"]
    entry_px = ticks[k0]["ask"] if side == "buy" else ticks[k0]["bid"]
    peak = 0.0; armed = False
    for k in range(k0, len(ticks)):
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
    last = ticks[-1]
    cur = (last["bid"] - entry_px) if side == "buy" else (entry_px - last["ask"])
    return (cur - COST, "EOD", peak)


def run(det_params, trail_arm, trail_gb, max_loss, cooldown):
    fills = []
    last_ms = {"buy": 0, "sell": 0}
    for i in range(N):
        if not in_zee_window(m1[i]["t"]): continue
        for side in ("buy", "sell"):
            h = detect(i, side, det_params)
            if not h: continue
            sig = m1[i]["t_end_ms"]
            if sig - last_ms[side] < cooldown * 1000: continue
            r = simulate(sig, side, trail_arm, trail_gb, max_loss)
            if r is None: continue
            pnl, why, peak = r
            fills.append({"t": m1[i]["t"], "side": side, "pnl": pnl, "why": why, "peak": peak, "pats": ",".join(h)})
            last_ms[side] = sig
    return fills


# Sweep
print(f"  {'ER':>4} {'bp':>4} {'body':>5} {'n_p':>3} {'ct?':>3} {'gb':>4} {'CB':>4} {'cool':>4} | "
      f"{'n':>3} {'W':>3} {'L':>3} {'WR%':>4} {'raw$':>7} {'dol$':>7} {'cap':>3}")
ZEE_MIN = [("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
           ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
           ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
           ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
           ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
           ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell")]

configs = []
for er in [0.05, 0.10, 0.15]:
    for bp in [0.30, 0.40]:
        for body in [0.30, 0.50]:
            for n_req in [1, 2]:
                for ct in [True, False]:
                    for gb in [3.0, 5.0]:
                        for ml in [3.0, 5.0]:
                            for cd in [60, 120]:
                                configs.append(((er,bp,body,n_req,ct), 1.0, gb, ml, cd))

best = (-9999, None, None)
for cfg in configs:
    det_p, arm, gb, ml, cd = cfg
    fills = run(det_p, arm, gb, ml, cd)
    n = len(fills); w = sum(1 for f in fills if f["pnl"]>0); l = n - w
    tot = sum(f["pnl"] for f in fills)
    matched = 0
    for hm, sd in ZEE_MIN:
        hh, mm = map(int, hm.split(":")); tmin = hh*60+mm
        for f in fills:
            if f["side"] == sd and abs(f["t"].hour*60 + f["t"].minute - tmin) <= 3:
                matched += 1; break
    if 5 <= n <= 100:
        print(f"  {det_p[0]:>4.2f} {det_p[1]:>4.2f} {det_p[2]:>5.2f} {det_p[3]:>3} "
              f"{str(det_p[4])[0]:>3} {gb:>4.1f} {ml:>4.1f} {cd:>4} | "
              f"{n:>3} {w:>3} {l:>3} {100*w/max(1,n):>3.0f}% {tot:>+7.1f} {tot*10:>+7.0f} {matched:>3}")
    if tot > best[0]:
        best = (tot, cfg, fills, matched)

print(f"\n=== BEST: {best[1]} ===")
print(f"  raw NET ${best[0]:+.2f} = ${best[0]*10:+.0f} dollars at 0.10 lots, captured {best[3]}/24 Zee setups")
print(f"\n  Per-fill:")
print(f"  {'t':>9} {'side':>4} {'raw$':>7} {'dol$':>7} {'why':<8} {'peak':>7} {'pats':<15}")
for f in best[2]:
    print(f"  {f['t'].strftime('%H:%M:%S'):>9} {f['side']:>4} {f['pnl']:>+7.2f} {f['pnl']*10:>+7.1f} {f['why']:<8} {f['peak']:>+7.2f} {f['pats']:<15}")
