"""s4_feb11_sweep.py — try various TP/SL/ER configs ONLY on Feb 11 to see if anything
mechanizes Zee's day. M1-bar level, bar-conservative SL-before-TP."""
import csv, sys
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

ERLB = 30; TRENDLB = 30; TRENDMIN = 7.0; RETRO = 12; MOM = 0.55
COST = 0.20

all_m1 = []
for r in csv.DictReader(open(M1, encoding="utf-8")):
    t = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
    if t.date() < datetime(2026, 2, 10).date() or t.date() > datetime(2026, 2, 12).date():
        continue
    all_m1.append({"t": t, "open": float(r["open"]), "high": float(r["high"]),
                   "low": float(r["low"]), "close": float(r["close"]),
                   "vol": float(r["tick_volume"])})
all_m1.sort(key=lambda b: b["t"])
m1c = [b["close"] for b in all_m1]


def trend_dir(i):
    half = TRENDLB // 2
    if i - 2 * half < 0: return 0
    wr = all_m1[i - half + 1:i + 1]; wo = all_m1[i - 2 * half + 1:i - half + 1]
    rHi = max(b["high"] for b in wr); rLo = min(b["low"] for b in wr)
    oHi = max(b["high"] for b in wo); oLo = min(b["low"] for b in wo)
    if rHi > oHi and rLo > oLo: return 1
    if rHi < oHi and rLo < oLo: return -1
    return 0


def er_at(i):
    if i < ERLB: return 0.0
    net = abs(m1c[i] - m1c[i - ERLB])
    path = sum(abs(m1c[j] - m1c[j - 1]) for j in range(i - ERLB + 1, i + 1))
    return net / path if path > 1e-9 else 0.0


def detect(i, buy, ermin):
    if i < max(TRENDLB, RETRO + 1, 25): return None
    bo = all_m1[i]
    rng = bo["high"] - bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"] - bo["open"])
    if body / rng < MOM: return None
    avgbody = sum(abs(all_m1[s]["close"] - all_m1[s]["open"]) for s in range(i - RETRO, i + 1)) / (RETRO + 1)
    if body < avgbody: return None
    if er_at(i) < ermin: return None
    td24 = bo["close"] - all_m1[i - 24]["close"]
    td = trend_dir(i)
    if buy:
        if not (bo["close"] > bo["open"] and td == 1 and td24 >= TRENDMIN): return None
        uhv_v = -1; uhv_h = 0
        for s in range(i - RETRO, i):
            b = all_m1[s]
            if b["close"] < b["open"] and b["vol"] > uhv_v:
                uhv_v = b["vol"]; uhv_h = b["high"]
        if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
            return ("buy", bo["close"])
    else:
        if not (bo["close"] < bo["open"] and td == -1 and td24 <= -TRENDMIN): return None
        uhv_v = -1; uhv_l = 0
        for s in range(i - RETRO, i):
            b = all_m1[s]
            if b["close"] > b["open"] and b["vol"] > uhv_v:
                uhv_v = b["vol"]; uhv_l = b["low"]
        if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
            return ("sell", bo["close"])
    return None


def walk(i_entry, side, entry, sl_dist, tp_dist):
    sl = entry - sl_dist if side == "buy" else entry + sl_dist
    tp = entry + tp_dist if side == "buy" else entry - tp_dist
    for j in range(i_entry + 1, min(i_entry + 1 + 500, len(all_m1))):
        b = all_m1[j]
        if side == "buy":
            if b["low"] <= sl: return -sl_dist - COST
            if b["high"] >= tp: return tp_dist - COST
        else:
            if b["high"] >= sl: return -sl_dist - COST
            if b["low"] <= tp: return tp_dist - COST
    last = all_m1[min(i_entry + 500, len(all_m1) - 1)]
    px = last["close"]
    return (px - entry - COST) if side == "buy" else (entry - px - COST)


feb11 = datetime(2026, 2, 11).date()
print("FEB 11 ONLY — config sweep (M1 bar sim, bar-conservative)\n")
print(f"  {'TP':>4} {'SL':>4} {'ER':>5}   {'n':>3} {'WR%':>5} {'NET$':>8} {'EV':>7}")

for ER in [0.00, 0.10, 0.15, 0.20]:
    for TP in [3.0, 5.0, 8.0, 12.0]:
        for SL in [0.5, 1.0, 1.5, 2.0, 3.0, 6.0]:
            fills = []
            for i in range(len(all_m1)):
                if all_m1[i]["t"].date() != feb11: continue
                for buy in (True, False):
                    sig = detect(i, buy, ER)
                    if sig is None: continue
                    side, entry = sig
                    p = walk(i, side, entry, SL, TP)
                    fills.append(p)
            if not fills: continue
            n = len(fills); tot = sum(fills); w = sum(1 for p in fills if p > 0)
            print(f"  {TP:>4.1f} {SL:>4.1f} {ER:>5.2f}   {n:>3} {100*w/n:>4.0f}% {tot:>+8.2f} {tot/n:>+7.2f}")
