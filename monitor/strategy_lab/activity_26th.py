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
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from backtest_s3_teacher_spec import aggregate_to_tf, detect_signals

TICKS = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_ticks_2026-05-26.csv")
LOTS = 0.01
PPP = LOTS * 100.0   # $ per 1.0 price-point at 0.01 lots on XAU = $1


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 4:
                continue
            try:
                out.append({"t": datetime.strptime(row[0], "%Y.%m.%d %H:%M:%S"),
                            "bid": float(row[2]), "ask": float(row[3])})
            except Exception:
                pass
    return out


def replay(ticks, sigs, max_conc=3):
    """sigs: {side, fire_time, sl_abs?, tp_abs?, sl_off?, tp_off?}. Entry at next tick
    ask(buy)/bid(sell); exit on SL/TP; EOD close. Returns list of pnl ($ at 0.01)."""
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] > 0:
                if bid <= u["sl"]: u["pnl"] = (u["sl"] - u["e"]) * PPP; done.append(u); units.remove(u)
                elif bid >= u["tp"]: u["pnl"] = (u["tp"] - u["e"]) * PPP; done.append(u); units.remove(u)
            else:
                if ask >= u["sl"]: u["pnl"] = (u["e"] - u["sl"]) * PPP; done.append(u); units.remove(u)
                elif ask <= u["tp"]: u["pnl"] = (u["e"] - u["tp"]) * PPP; done.append(u); units.remove(u)
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                if pend.get("sl_abs") is not None:
                    sl, tp = pend["sl_abs"], pend["tp_abs"]
                else:
                    sl = e - pend["sl_off"] if pend["side"] > 0 else e + pend["sl_off"]
                    tp = e + pend["tp_off"] if pend["side"] > 0 else e - pend["tp_off"]
                units.append({"side": pend["side"], "e": e, "sl": sl, "tp": tp})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * PPP
            done.append(u)
    return [u["pnl"] for u in done]


def pl_line(name, pnls):
    if not pnls:
        return f"  {name:<22} 0 trades"
    w = sum(1 for p in pnls if p > 0); l = sum(1 for p in pnls if p < 0)
    return f"  {name:<22} {len(pnls)} trades · {w}W/{l}L · P&L ${sum(pnls):+.2f}"


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


def s4_signals(m5, TREND_LB=30, RETRACE=12, MOM=0.55, TP=2.0, SL=7.5):
    """Current S4 v2.00: M5 UHV breakout + HH/HL, fixed TP$2/SL$7.5."""
    sigs = []
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
        ft = bo["time"] + timedelta(minutes=5)
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                u = max(reds, key=lambda b: b["vol"])
                if bo["vol"] < u["vol"] and bo["close"] > u["high"] and bo["open"] <= u["high"]:
                    sigs.append({"side": +1, "fire_time": ft, "tp_off": TP, "sl_off": SL}); continue
        if bo["close"] < bo["open"] and td == -1:
            grns = [b for b in win if b["close"] > b["open"]]
            if grns:
                u = max(grns, key=lambda b: b["vol"])
                if bo["vol"] < u["vol"] and bo["close"] < u["low"] and bo["open"] >= u["low"]:
                    sigs.append({"side": -1, "fire_time": ft, "tp_off": TP, "sl_off": SL})
    return sigs


def main():
    if not TICKS.exists():
        print("no tick file for 26th"); return
    m1 = build_m1(TICKS)
    m5 = aggregate_to_tf(m1, 5)
    span = f"{m1[0]['time']:%H:%M} → {m1[-1]['time']:%H:%M}" if m1 else "?"
    print(f"26 May: {len(m1)} M1 bars, {len(m5)} M5 bars  (broker {span})\n")

    ticks = load_ticks(TICKS)
    print(f"  ({len(ticks)} ticks loaded for replay, 0.01 lots)\n")

    # S4 — current v2.00 (TP$2/SL$7.5)
    s4 = s4_signals(m5)
    s4_pl = replay(ticks, s4)
    print(pl_line("S4 (UHV breakout 2:1.. err TP2/SL7.5)", s4_pl))

    # S3 — current v2.31 (peak-TP, SL buffer $5), BUY side via detect_signals
    s3_buys = detect_signals(m5, [], 5.0, 1.0, 24, False, 10, 5)
    s3_sigs = [{"side": +1, "fire_time": s["fire_time"], "sl_abs": s["sl"], "tp_abs": s["tp"]} for s in s3_buys]
    s3_pl = replay(ticks, s3_sigs)
    print(pl_line("S3 (wicking, peak-TP, buy)", s3_pl))

    total = sum(s4_pl) + sum(s3_pl)
    print(f"\n  >>> Combined (S4 + S3-buy) on 26 May @ 0.01 lots: ${total:+.2f}")
    print(f"      (S1 ~1-2 trades not modeled here; S3 sells not modeled — small)")


if __name__ == "__main__":
    main()
