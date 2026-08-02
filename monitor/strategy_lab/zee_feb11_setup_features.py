"""zee_feb11_setup_features.py — for EACH of Zee's 24 distinct Feb-11 setups,
dump the bar-level features so we can find the COMMON pattern across all of them.

We have rev_eng_m1.csv (matches Zee's prices, per classify_feb11.py).
For each setup, extract:
  - trend direction (M1 30-bar)
  - last 4 M1 bars: o/h/l/c/v/body%/range
  - efficiency ratio (M1, 30-bar)
  - vs-recent-UHV-high (buy) or UHV-low (sell): distance, vol-ratio of entry-bar
  - dead-vol candle right before entry (NS/ND signature)
  - sweep flag: any of last 5 bars wicked beyond recent extreme then closed back

Goal: discover the OR-of-patterns that fires on ALL 24 and few others.
"""
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

# Zee's 24 distinct setups (broker EET = UTC+2 winter)
# (broker_time, side, open_px, close_t, close_px, net_dollars)
ZEE_24 = [
    ("01:32:19","buy",5045.07, "01:47:30",5045.94,  +7.32),
    ("01:59:04","buy",5042.17, "02:00:43",5042.96,  +6.65),
    ("02:09:38","sell",5040.68,"02:10:18",5039.29, +11.69),
    ("02:29:02","buy",5039.03, "02:30:28",5041.41, +20.01),
    ("16:49:07","buy",5047.93, "16:51:03",5049.96, +17.12),
    ("16:52:21","buy",5050.77, "16:52:27",5051.82,  +8.85),
    ("16:54:10","buy",5056.74, "16:54:20",5057.72,  +8.26),
    ("16:58:03","buy",5064.26, "16:58:27",5064.94,  +5.73),
    ("17:02:45","buy",5055.71, "17:03:51",5062.23, +54.93),
    ("17:36:11","buy",5056.53, "17:36:26",5056.92,  +3.29),
    ("17:36:13","buy",5057.05, "17:52:56",5058.77, +14.50),
    ("17:37:26","buy",5045.82, "17:40:02",5046.66,  +7.08),
    ("17:49:59","buy",5048.32, "17:52:33",5054.58, +52.78),
    ("18:24:18","buy",5059.26, "18:28:33",5060.27,  +8.51),
    ("18:41:50","buy",5078.10, "19:06:41",5077.93,  -1.43),
    ("19:08:59","sell",5083.28,"19:09:08",5082.35,  +7.82),
    ("19:11:05","sell",5083.39,"19:11:27",5083.02,  +3.11),
    ("19:11:51","sell",5083.79,"19:19:10",5081.77, +16.99),
    ("19:20:34","sell",5084.21,"19:20:40",5082.52, +14.21),
    ("19:26:06","sell",5089.16,"19:26:50",5087.43, +14.55),
    ("19:29:31","buy",5086.34, "19:39:03",5086.44,  +0.84),
    ("19:32:48","buy",5084.71, "19:37:34",5085.41,  +5.89),
    ("19:36:19","buy",5082.91, "19:37:19",5084.17, +10.60),
    ("19:38:39","buy",5083.28, "19:38:50",5084.59, +11.02),
    ("19:38:59","buy",5086.33, "19:39:03",5086.44,  +0.92),
    ("19:41:59","sell",5091.09,"19:42:54",5090.93,  +1.35),
    ("19:42:26","sell",5093.18,"19:42:40",5092.05,  +9.50),
]
print(f"Zee's distinct setups (deduped on entry minute): {len({(b,s) for b,s,*_ in ZEE_24})}")

# Load Feb 10-12 M1 bars (rev_eng_m1 is broker-time; broker = UTC+2 EET = +2h vs UTC)
# But Zee's broker times above are also EET. So we match HH:MM:SS directly to rev_eng_m1 broker time.
bars = []
for r in csv.DictReader(open(M1, encoding="utf-8")):
    t = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
    if t.date() < datetime(2026, 2, 10).date() or t.date() > datetime(2026, 2, 12).date():
        continue
    bars.append({"t": t, "o": float(r["open"]), "h": float(r["high"]),
                 "l": float(r["low"]), "c": float(r["close"]),
                 "v": float(r["tick_volume"])})
bars.sort(key=lambda b: b["t"])
idx_by_t = {b["t"]: i for i, b in enumerate(bars)}

def feb11_bar(hh, mm):
    """Return index of M1 bar that CONTAINS minute hh:mm of Feb 11. (entry minute bar)"""
    target = datetime(2026, 2, 11, hh, mm)
    return idx_by_t.get(target)


def features(idx, side, entry_px):
    """Extract every feature we can think of from bar at idx."""
    if idx is None or idx < 35:
        return None
    bar = bars[idx]                  # the entry-minute bar
    prev = bars[idx - 1]
    prev2 = bars[idx - 2]
    prev3 = bars[idx - 3]
    W = bars[idx - 30:idx]           # last 30 bars
    R = bars[idx - 12:idx]           # retracement window
    vols = [b["v"] for b in W]
    avgv = sum(vols) / len(vols)
    rngs = [b["h"] - b["l"] for b in W]
    avgr = sum(rngs) / len(rngs)
    bodies = [abs(b["c"] - b["o"]) for b in W]
    avgbody = sum(bodies) / len(bodies)

    # Trend HH/HL on M1-30
    h = 15
    older, recent = W[:h], W[h:]
    if older and recent:
        rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
        oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
        if rH > oH and rL > oL: td = +1
        elif rH < oH and rL < oL: td = -1
        else: td = 0
    else: td = 0

    # ER on 30 closes
    closes = [b["c"] for b in W + [bar]]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    er = net / path if path > 1e-9 else 0.0

    rng = bar["h"] - bar["l"]
    body = abs(bar["c"] - bar["o"])
    body_pct = body / rng if rng > 0 else 0
    green = bar["c"] > bar["o"]

    # UHV (highest-vol) bar in retracement window
    uhv = max(R, key=lambda b: b["v"])
    uhv_red = uhv["c"] < uhv["o"]
    uhv_grn = uhv["c"] > uhv["o"]
    uhv_mult = uhv["v"] / max(1.0, avgv)
    uhv_high = uhv["h"]; uhv_low = uhv["l"]
    uhv_dist_to_entry = entry_px - uhv_high if side == "buy" else uhv_low - entry_px

    # Dead-volume candle in last 3 bars (NS/ND signature): low body, low vol
    dead_vol_3 = any(b["v"] < 0.6 * avgv and (b["h"] - b["l"]) < 0.6 * avgr for b in [prev, prev2, prev3])

    # Sweep: any of last 5 bars wicked beyond prior extreme, closed back inside
    last5 = bars[idx - 5:idx]
    prior = bars[idx - 30:idx - 5]
    if side == "buy":
        prior_lo = min(b["l"] for b in prior)
        swept = any(b["l"] < prior_lo and b["c"] > prior_lo for b in last5)
    else:
        prior_hi = max(b["h"] for b in prior)
        swept = any(b["h"] > prior_hi and b["c"] < prior_hi for b in last5)

    # Was there a big momentum bar in last 5 closing in trade direction
    if side == "buy":
        mom_bar = any(b["c"] > b["o"] and abs(b["c"] - b["o"]) > 1.5 * avgbody for b in last5)
    else:
        mom_bar = any(b["c"] < b["o"] and abs(b["c"] - b["o"]) > 1.5 * avgbody for b in last5)

    # Continuation: entry-bar IS the momentum candle in direction
    cont = green if side == "buy" else not green
    big_body = body > 1.3 * avgbody

    return {
        "td": td, "er": round(er, 2), "vol_x_avg": round(bar["v"] / avgv, 2),
        "body_pct": round(body_pct, 2), "big_body": big_body, "cont": cont,
        "uhv_dist": round(uhv_dist_to_entry, 2),
        "uhv_red_buy": uhv_red and side == "buy",
        "uhv_grn_sell": uhv_grn and side == "sell",
        "uhv_mult": round(uhv_mult, 1),
        "dead_vol_3": dead_vol_3, "swept": swept, "mom_bar": mom_bar,
    }


print(f"{'broker':>9} {'side':>4} {'entry':>8}  {'td':>3} {'er':>5} {'vol×':>5} {'body%':>6} {'big':>4} {'cont':>5} "
      f"{'uhv_d':>6} {'uhvR':>5} {'uhvX':>5} {'dead3':>6} {'swept':>6} {'mom5':>5}")
hit_flags = []
for broker_t, side, ent, *_ in ZEE_24:
    hh, mm, ss = map(int, broker_t.split(":"))
    idx = feb11_bar(hh, mm)
    if idx is None:
        print(f"{broker_t:>9}  no bar")
        continue
    f = features(idx, side, ent)
    flag = []
    if f["uhv_red_buy"] or f["uhv_grn_sell"]:
        flag.append("UHV")
    if f["dead_vol_3"]:
        flag.append("NSND")
    if f["swept"]:
        flag.append("SWP")
    if f["mom_bar"] or f["big_body"]:
        flag.append("MOM")
    if not flag:
        flag = ["?"]
    hit_flags.append(flag)
    print(f"{broker_t:>9} {side:>4} {ent:>8.2f}  {f['td']:>+3} {f['er']:>5.2f} {f['vol_x_avg']:>5.2f} "
          f"{f['body_pct']:>6.2f} {str(f['big_body']):>4} {str(f['cont']):>5} "
          f"{f['uhv_dist']:>+6.1f} {str(f['uhv_red_buy'] or f['uhv_grn_sell'])[0]:>5} {f['uhv_mult']:>5.1f} "
          f"{str(f['dead_vol_3'])[0]:>6} {str(f['swept'])[0]:>6} {str(f['mom_bar'])[0]:>5}  {','.join(flag)}")

# Coverage: how many of 24 are covered by each pattern
print()
total = len(hit_flags)
for tag in ["UHV", "NSND", "SWP", "MOM"]:
    n = sum(1 for f in hit_flags if tag in f)
    print(f"  {tag}: covers {n}/{total} = {100*n/total:.0f}%")
n_any = sum(1 for f in hit_flags if any(t in f for t in ["UHV","NSND","SWP","MOM"]))
n_unclassified = sum(1 for f in hit_flags if f == ["?"])
print(f"  ANY pattern: {n_any}/{total} = {100*n_any/total:.0f}%   unclassified: {n_unclassified}")
