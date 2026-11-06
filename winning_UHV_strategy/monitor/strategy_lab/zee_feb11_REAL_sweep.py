"""zee_feb11_REAL_sweep.py — grid sweep entry-tightness × exit params on real Feb 11.
Goal: find config that produces +$300-$800 NET (dollars at 0.10 lots) on full day.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS = COMMON / "shano_ticks_2026-02-11.csv"

TREND_LB = 30; RETRO = 12
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
print(f"  {len(ticks):,} ticks")

m1 = []; cur = None
for tk in ticks:
    m_key = tk["t_ms"] // 60000
    mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
               "t_end_ms": (m_key + 1) * 60000 - 1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
        cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
print(f"  {len(m1)} M1 bars\n")

N = len(m1)
tick_times = [t["t_ms"] for t in ticks]


def trend_dir(i):
    if i < TREND_LB: return 0
    W = m1[i - TREND_LB:i]; h = TREND_LB // 2
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


def detect(i, side, er_min, body_pct_min, body_min, n_patterns_req):
    if i < TREND_LB + 5: return None
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i]; R = m1[i - RETRO:i]; L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
    green = bar["c"] > bar["o"]
    td = trend_dir(i); er = er_at(i)
    if er < er_min: return None
    if body_pct < body_pct_min: return None
    if body < body_min: return None
    if side == "buy" and not green: return None
    if side == "sell" and green: return None

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

    if len(patterns) >= n_patterns_req or strong:
        return patterns
    return None


def simulate(signal_ms, side, trail_arm, trail_gb, max_loss, max_hold, skim=50.0):
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


def run(er_min, body_pct, body_min, n_req, trail_arm, trail_gb, max_loss, cooldown):
    fills = []
    last_ms = {"buy": 0, "sell": 0}
    for i in range(N):
        for side in ("buy", "sell"):
            h = detect(i, side, er_min, body_pct, body_min, n_req)
            if not h: continue
            sig = m1[i]["t_end_ms"]
            if sig - last_ms[side] < cooldown * 1000: continue
            r = simulate(sig, side, trail_arm, trail_gb, max_loss, 1800)
            if r is None: continue
            pnl, why, peak = r
            fills.append({"t": m1[i]["t"], "side": side, "pnl": pnl, "why": why})
            last_ms[side] = sig
    return fills


print(f"  {'ER':>4} {'bp%':>4} {'body':>5} {'#pat':>4} {'arm':>4} {'gb':>4} {'CB':>4} {'cool':>4} | "
      f"{'n':>3} {'W':>3} {'L':>3} {'WR%':>4} {'raw$':>7} {'dol$':>7}")

configs = []
for er_min in [0.10, 0.15, 0.20]:
    for bp_min in [0.40, 0.50]:
        for n_req in [1, 2]:
            for trail_gb in [3.0, 5.0]:
                for max_loss in [3.0, 5.0]:
                    for cooldown in [120, 300]:
                        configs.append((er_min, bp_min, 0.40, n_req, 1.0, trail_gb, max_loss, cooldown))

best = (-9999, None, None)
for cfg in configs:
    fills = run(*cfg)
    n = len(fills); w = sum(1 for f in fills if f["pnl"]>0); l = n - w
    tot = sum(f["pnl"] for f in fills)
    if n < 10 or n > 200: continue  # focus on reasonable fire counts
    print(f"  {cfg[0]:>4.2f} {cfg[1]:>4.2f} {cfg[2]:>5.2f} {cfg[3]:>4} {cfg[4]:>4.1f} {cfg[5]:>4.1f} {cfg[6]:>4.1f} {cfg[7]:>4} | "
          f"{n:>3} {w:>3} {l:>3} {100*w/max(1,n):>3.0f}% {tot:>+7.1f} {tot*10:>+7.0f}")
    if tot > best[0]: best = (tot, cfg, fills)

print(f"\n=== BEST: {best[1]} → raw ${best[0]:+.2f} = ${best[0]*10:+.0f} dollars at 0.10 lots ===")
fills = best[2]
print(f"\n  Per-fill (best config):")
print(f"  {'t':>9} {'side':>4} {'raw$':>7} {'dol$':>7} {'why':<8}")
for f in fills:
    print(f"  {f['t'].strftime('%H:%M:%S'):>9} {f['side']:>4} {f['pnl']:>+7.2f} {f['pnl']*10:>+7.1f} {f['why']:<8}")
