"""s4_feb11_check.py — Run S4's CURRENT reverted config (TP=$12, SL=$6, ER>=0.15)
on Feb 11, 2026 specifically. Feb 11 was Zee's 65W/4L = 94% WR / +$835 manual day,
the original inspiration AND validation basis for S4.

No tick file exists for Feb 11 (shano_ticks_*.csv only goes back to 2026-04-29), so
we simulate at M1 bar level against rev_eng_m1.csv (the canonical broker M1 feed
that matches Zee's actual entries: classify_feb11.py confirmed it).

Method: S4 detector mirror (UHV breakout, M1 timeframe, HH/HL trend, ER>=0.15
chop filter). For each fill: enter at the breakout bar's CLOSE; walk forward
M1-bar-by-M1-bar; SL = entry - $6 (buy) / entry + $6 (sell); TP = entry ± $12.
Bar-conservative: SL checked before TP on same bar (worst-case fill).
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"

# S4's current REVERTED config
TP = 12.0
SL = 6.0
ERMIN = 0.15
ERLB = 30
TRENDLB = 30
TRENDMIN = 7.0
RETRO = 12
MOM = 0.55
COST = 0.20   # per-trade spread/commission proxy

# Load M1 bars for Feb 11 ± buffer (need TRENDLB lookback)
print("Loading rev_eng_m1.csv for Feb 11 ± buffer...")
all_m1 = []
for r in csv.DictReader(open(M1, encoding="utf-8")):
    t = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
    if t.date() < datetime(2026, 2, 10).date() or t.date() > datetime(2026, 2, 12).date():
        continue
    all_m1.append({
        "t": t,
        "open": float(r["open"]), "high": float(r["high"]),
        "low": float(r["low"]), "close": float(r["close"]),
        "vol": float(r["tick_volume"]),
    })
all_m1.sort(key=lambda b: b["t"])
print(f"  {len(all_m1)} M1 bars (Feb 10-12 window)\n")

m1_close = [b["close"] for b in all_m1]


def trend_dir(i):
    half = TRENDLB // 2
    if i - 2 * half < 0:
        return 0
    win_r = all_m1[i - half + 1:i + 1]
    win_o = all_m1[i - 2 * half + 1:i - half + 1]
    rHi = max(b["high"] for b in win_r); rLo = min(b["low"] for b in win_r)
    oHi = max(b["high"] for b in win_o); oLo = min(b["low"] for b in win_o)
    if rHi > oHi and rLo > oLo: return 1
    if rHi < oHi and rLo < oLo: return -1
    return 0


def er_at(i):
    if i < ERLB:
        return 0.0
    net = abs(m1_close[i] - m1_close[i - ERLB])
    path = sum(abs(m1_close[j] - m1_close[j - 1]) for j in range(i - ERLB + 1, i + 1))
    return net / path if path > 1e-9 else 0.0


def detect(i, buy):
    if i < max(TRENDLB, RETRO + 1, 25):
        return None
    bo = all_m1[i]
    rng = bo["high"] - bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"] - bo["open"])
    if body / rng < MOM: return None
    avgbody = sum(abs(all_m1[s]["close"] - all_m1[s]["open"]) for s in range(i - RETRO, i + 1)) / (RETRO + 1)
    if body < avgbody: return None
    er = er_at(i)
    if er < ERMIN: return None
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
            return ("buy", bo["close"], er)
    else:
        if not (bo["close"] < bo["open"] and td == -1 and td24 <= -TRENDMIN): return None
        uhv_v = -1; uhv_l = 0
        for s in range(i - RETRO, i):
            b = all_m1[s]
            if b["close"] > b["open"] and b["vol"] > uhv_v:
                uhv_v = b["vol"]; uhv_l = b["low"]
        if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
            return ("sell", bo["close"], er)
    return None


def walk_exit(i_entry, side, entry, sl, tp):
    """Walk M1 bars from i_entry+1, return (pnl, exit_reason, bars_held)."""
    for j in range(i_entry + 1, min(i_entry + 1 + 500, len(all_m1))):
        b = all_m1[j]
        if side == "buy":
            if b["low"] <= sl: return (sl - entry - COST, "SL", j - i_entry)
            if b["high"] >= tp: return (tp - entry - COST, "TP", j - i_entry)
        else:
            if b["high"] >= sl: return (entry - sl - COST, "SL", j - i_entry)
            if b["low"] <= tp: return (entry - tp - COST, "TP", j - i_entry)
    # session end
    last = all_m1[min(i_entry + 500, len(all_m1) - 1)]
    px = last["close"]
    pnl = (px - entry - COST) if side == "buy" else (entry - px - COST)
    return (pnl, "EOD", min(500, len(all_m1) - 1 - i_entry))


# Run on Feb 11 only (filter by date when emitting fills)
fills = []
feb11 = datetime(2026, 2, 11).date()
for i in range(len(all_m1)):
    if all_m1[i]["t"].date() != feb11:
        continue
    for buy in (True, False):
        sig = detect(i, buy)
        if sig is None:
            continue
        side, entry, er = sig
        if side == "buy":
            sl = entry - SL; tp = entry + TP
        else:
            sl = entry + SL; tp = entry - TP
        pnl, reason, held = walk_exit(i, side, entry, sl, tp)
        fills.append((all_m1[i]["t"], side, entry, pnl, reason, held, er))

print(f"=== S4 REVERTED CONFIG ON FEB 11 (TP=$12, SL=$6, ER>={ERMIN}) ===")
print(f"  Note: M1 BAR sim (no tick data exists for Feb 11). Bar-conservative: SL before TP on same bar.\n")
if not fills:
    print("  No S4 signals fired on Feb 11.")
else:
    print(f"  {'broker_t':>9}  {'side':<5}  {'entry':>8}  {'pnl':>8}  {'why':<4}  {'held_m':>6}  {'ER':>5}")
    for t, side, e, p, why, h, er in fills:
        print(f"  {t.strftime('%H:%M:%S'):>9}  {side:<5}  {e:>8.2f}  {p:>+8.2f}  {why:<4}  {h:>6d}  {er:>5.2f}")
    n = len(fills); pnl_tot = sum(p for _, _, _, p, _, _, _ in fills)
    w = sum(1 for _, _, _, p, _, _, _ in fills if p > 0)
    avg_w = sum(p for _, _, _, p, _, _, _ in fills if p > 0) / max(1, w)
    l = n - w
    avg_l = sum(p for _, _, _, p, _, _, _ in fills if p <= 0) / max(1, l)
    print(f"\n  Total: n={n}  WR={100*w/n:.0f}%  NET=${pnl_tot:+.2f}  avgW=${avg_w:+.2f}  avgL=${avg_l:+.2f}")

# Zee's actual Feb 11 fills (24 distinct setups) — for comparison
ZEE_SETUPS = [
    ("01:32:19","buy","23:32:19"),("01:59:04","buy","23:59:04"),("02:09:38","sell","00:09:38"),
    ("02:29:02","buy","00:29:02"),("16:49:07","buy","14:49:07"),("16:52:21","buy","14:52:21"),
    ("16:54:10","buy","14:54:10"),("16:58:03","buy","14:58:03"),("17:02:45","buy","15:02:45"),
    ("17:36:11","buy","15:36:11"),("17:36:13","buy","15:36:13"),("17:37:26","buy","15:37:26"),
    ("17:49:59","buy","15:49:59"),("18:24:18","buy","16:24:18"),("18:41:50","buy","16:41:50"),
    ("19:08:59","sell","17:08:59"),("19:11:05","sell","17:11:05"),("19:11:51","sell","17:11:51"),
    ("19:20:34","sell","17:20:34"),("19:26:06","sell","17:26:06"),("19:29:31","buy","17:29:31"),
    ("19:32:48","buy","17:32:48"),("19:36:19","buy","17:36:19"),("19:38:39","buy","17:38:39"),
    ("19:38:59","buy","17:38:59"),("19:41:59","sell","17:41:59"),("19:42:26","sell","17:42:26"),
]
# rev_eng_m1.csv is broker time = UTC (per dashboard timezone work); Zee's fills above
# are broker EET (UTC+2 winter). Convert broker fills to UTC for matching.
print(f"\n=== ZEE'S ACTUAL FEB 11 — {len(ZEE_SETUPS)} distinct setups (UTC times) ===")
zee_utc_min = set()
for broker_t, side, utc_t in ZEE_SETUPS:
    hh, mm, _ = utc_t.split(":")
    zee_utc_min.add((int(hh), int(mm), side))

# Match S4 fills to Zee within ±5 min same side
s4_min = [(t.hour, t.minute, side) for t, side, _, _, _, _, _ in fills]
matched = 0
for hh, mm, side in zee_utc_min:
    total = hh * 60 + mm
    for sh, sm, ss in s4_min:
        if ss != side: continue
        if abs((sh * 60 + sm) - total) <= 5:
            matched += 1; break

print(f"  S4 captured {matched} of {len(zee_utc_min)} Zee setups within ±5 min same-side")
print(f"  Zee total: 65W / 4L / 94% WR / +$835.16 across 69 fills (24 distinct setups)")
