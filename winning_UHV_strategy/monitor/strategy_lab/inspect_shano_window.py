"""Inspect why v3.42 detector skips bars where Shano fired.

For each bar in 02:00-03:00 on 2026-05-13:
  - Show OHLC + body sign + volume
  - For each candidate side (buy if green, sell if red), step through detector:
    - List reds/greens in lookback, why each one passes/fails
    - UHV pick, sl_init
    - close > uhv.high check
    - bo.vol < uhv.vol check
  - Show which Shano timestamps fall on this bar
"""
import csv
import os
from datetime import datetime
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

SHANO = [
    ('02:07:45', 'buy'), ('02:09:06', 'buy'), ('02:09:27', 'sell'),
    ('02:10:01', 'sell'), ('02:10:30', 'sell'), ('02:11:14', 'buy'),
    ('02:14:28', 'sell'), ('02:14:42', 'sell'), ('02:20:05', 'sell'),
    ('02:22:54', 'buy'), ('02:23:42', 'buy'), ('02:24:40', 'buy'),
    ('02:24:50', 'buy'), ('02:27:08', 'sell'), ('02:30:27', 'sell'),
    ('02:30:35', 'sell'), ('02:34:54', 'sell'), ('02:35:54', 'sell'),
]

MAX_LOOKBACK = 60
MAX_BARS_BACK = 60


def load_bars(path):
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            bars.append({
                "time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "vol": int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def shano_in_bar(bar):
    """Return list of ('hh:mm:ss', side) Shano fires within this minute."""
    hits = []
    bar_mm = bar["time"].strftime("%H:%M")
    for t, side in SHANO:
        if t[:5] == bar_mm:
            hits.append((t, side))
    return hits


def analyze_buy(bars, i):
    """Step through buy detector at bar i; returns dict with diagnostic."""
    bo = bars[i]
    if bo["close"] <= bo["open"]:
        return {"ok": False, "reason": "not green"}
    reds = []
    blocked_at = None
    for j in range(1, MAX_LOOKBACK + 1):
        k = i - j
        if k < 0: break
        c = bars[k]
        if c["high"] >= bo["close"]:
            blocked_at = (k, c, "high >= bo.close")
            break
        if c["close"] < c["open"]:
            reds.append((k, c))
    if not reds:
        return {"ok": False, "reason": "no red in lookback", "blocked_at": blocked_at}
    k_uhv, uhv = max(reds, key=lambda kc: kc[1]["vol"])
    bars_back = i - k_uhv
    if bars_back > MAX_BARS_BACK:
        return {"ok": False, "reason": f"bars_back {bars_back} > {MAX_BARS_BACK}", "uhv": uhv}
    if bo["close"] <= uhv["high"]:
        return {"ok": False, "reason": f"close {bo['close']:.2f} <= uhv.high {uhv['high']:.2f}", "uhv": uhv}
    if bo["vol"] >= uhv["vol"]:
        return {"ok": False, "reason": f"bo.vol {bo['vol']} >= uhv.vol {uhv['vol']}", "uhv": uhv}
    return {"ok": True, "uhv": uhv, "bars_back": bars_back}


def analyze_sell(bars, i):
    bo = bars[i]
    if bo["close"] >= bo["open"]:
        return {"ok": False, "reason": "not red"}
    greens = []
    blocked_at = None
    for j in range(1, MAX_LOOKBACK + 1):
        k = i - j
        if k < 0: break
        c = bars[k]
        if c["low"] <= bo["close"]:
            blocked_at = (k, c, "low <= bo.close")
            break
        if c["close"] > c["open"]:
            greens.append((k, c))
    if not greens:
        return {"ok": False, "reason": "no green in lookback", "blocked_at": blocked_at}
    k_uhv, uhv = max(greens, key=lambda kc: kc[1]["vol"])
    bars_back = i - k_uhv
    if bars_back > MAX_BARS_BACK:
        return {"ok": False, "reason": f"bars_back {bars_back} > {MAX_BARS_BACK}", "uhv": uhv}
    if bo["close"] >= uhv["low"]:
        return {"ok": False, "reason": f"close {bo['close']:.2f} >= uhv.low {uhv['low']:.2f}", "uhv": uhv}
    if bo["vol"] >= uhv["vol"]:
        return {"ok": False, "reason": f"bo.vol {bo['vol']} >= uhv.vol {uhv['vol']}", "uhv": uhv}
    return {"ok": True, "uhv": uhv, "bars_back": bars_back}


def main():
    bars = load_bars(M1_CSV)
    start = datetime(2026, 5, 13, 2, 0)
    end = datetime(2026, 5, 13, 3, 0)
    idx_start = next(i for i, b in enumerate(bars) if b["time"] >= start)
    idx_end = next(i for i, b in enumerate(bars) if b["time"] >= end)

    print(f"{'time':<6} {'O':<8} {'H':<8} {'L':<8} {'C':<8} {'body':<6} {'vol':<5} | shano | buy / sell diag")
    print("-" * 130)
    for i in range(idx_start, idx_end):
        b = bars[i]
        body = b["close"] - b["open"]
        sign = "G" if body > 0 else ("R" if body < 0 else "_")
        shano_hits = shano_in_bar(b)
        shano_str = ",".join(f"{t[3:8]}{s[0].upper()}" for t, s in shano_hits) if shano_hits else ""

        # Try both detectors
        buy = analyze_buy(bars, i)
        sell = analyze_sell(bars, i)
        diag = []
        if sign == "G":
            if buy["ok"]:
                diag.append(f"BUY ok (UHV {buy['uhv']['time']:%H:%M} vol={buy['uhv']['vol']} h={buy['uhv']['high']:.2f}, bars_back={buy['bars_back']})")
            else:
                diag.append(f"buy: {buy['reason']}")
        elif sign == "R":
            if sell["ok"]:
                diag.append(f"SELL ok (UHV {sell['uhv']['time']:%H:%M} vol={sell['uhv']['vol']} l={sell['uhv']['low']:.2f}, bars_back={sell['bars_back']})")
            else:
                diag.append(f"sell: {sell['reason']}")

        marker = "** " if shano_hits else "   "
        print(f"{marker}{b['time']:%H:%M:%S}  {b['open']:<8.2f} {b['high']:<8.2f} {b['low']:<8.2f} {b['close']:<8.2f} {abs(body):<5.2f}{sign} {b['vol']:<5} | {shano_str:<6} | {' / '.join(diag)}")


if __name__ == "__main__":
    main()
