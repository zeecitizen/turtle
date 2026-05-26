"""activity_26th.py — would the CURRENT EAs have traded Tue 26 May, if attached all day?

The live EAs took 0 trades on the 26th because they were only attached ~21:32 (then
the daily market break). This replays the day from the broker tick file and counts how
many signals each current config WOULD have produced — to confirm the EAs aren't
silent because of over-filtering.

Builds M5 from shano_ticks_2026-05-26.csv (the live Exness feed).
"""
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_s3_teacher_spec import aggregate_to_tf, detect_signals

TICKS = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-26.csv")


def build_m1(path):
    buckets = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            if len(row) < 4:
                continue
            try:
                t = datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S")
                bid = float(row[2]); ask = float(row[3])
            except Exception:
                continue
            mid = (bid + ask) / 2.0
            key = t.replace(second=0, microsecond=0)
            b = buckets.get(key)
            if b is None:
                buckets[key] = {"time": key, "open": mid, "high": mid, "low": mid, "close": mid, "vol": 1}
            else:
                b["high"] = max(b["high"], mid); b["low"] = min(b["low"], mid)
                b["close"] = mid; b["vol"] += 1
    return [buckets[k] for k in sorted(buckets)]


# ── S4 faithful detector (v2.00: M5 UHV breakout + HH/HL structure) ──
def trend_dir(seg):
    h = len(seg) // 2
    o, rec = seg[:h], seg[h:]
    if not o or not rec:
        return 0
    hh = max(b["high"] for b in rec) > max(b["high"] for b in o)
    hl = min(b["low"] for b in rec) > min(b["low"] for b in o)
    lh = max(b["high"] for b in rec) < max(b["high"] for b in o)
    ll = min(b["low"] for b in rec) < min(b["low"] for b in o)
    return 1 if (hh and hl) else (-1 if (lh and ll) else 0)


def s4_count(m5, TREND_LB=30, RETRACE=12, MOM=0.55):
    n_buy = n_sell = 0
    for i in range(TREND_LB + RETRACE + 2, len(m5)):
        bo = m5[i]; rng = bo["high"] - bo["low"]
        if rng <= 0:
            continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < MOM:
            continue
        win = m5[i - RETRACE:i]
        if body < sum(abs(b["close"] - b["open"]) for b in win) / len(win):
            continue
        td = trend_dir(m5[i - TREND_LB:i])
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                u = max(reds, key=lambda b: b["vol"])
                if bo["vol"] < u["vol"] and bo["close"] > u["high"] and bo["open"] <= u["high"]:
                    n_buy += 1; continue
        if bo["close"] < bo["open"] and td == -1:
            grns = [b for b in win if b["close"] > b["open"]]
            if grns:
                u = max(grns, key=lambda b: b["vol"])
                if bo["vol"] < u["vol"] and bo["close"] < u["low"] and bo["open"] >= u["low"]:
                    n_sell += 1
    return n_buy, n_sell


def main():
    if not TICKS.exists():
        print("no tick file for 26th"); return
    m1 = build_m1(TICKS)
    m5 = aggregate_to_tf(m1, 5)
    span = f"{m1[0]['time']:%H:%M} → {m1[-1]['time']:%H:%M}" if m1 else "?"
    print(f"26 May: {len(m1)} M1 bars, {len(m5)} M5 bars  (broker {span})\n")

    # S4 (current v2.00 config)
    b, s = s4_count(m5)
    print(f"  S4 (M5 UHV breakout + HH/HL):   {b} buy + {s} sell = {b+s} signals")

    # S3 (current v2.31: M5, FVG off, sells on, SL buf 5, peak TP) — BUY via detect_signals
    s3_buys = detect_signals(m5, [], 5.0, 1.0, 24, False, 10, 5)
    print(f"  S3 (M5 wicking, peak-TP):       {len(s3_buys)} buy signals (sells ~similar → ~{len(s3_buys)*2} total)")
    print(f"\n  S1 fires ~1-2/day by design (rare). Bottom line below.")


if __name__ == "__main__":
    main()
