"""classify_feb11.py — which setup was Zee forming on each Feb-11 trade?

For each of Zee's 27 Feb-11 entries, examine the broker M1 bars (rev_eng_m1.csv,
the feed that MATCHES his entry prices) right before the entry and test each setup's
core signature:

  SWEEP (S3 / lesson-10 liquidity-sweep): a recent bar wicked BELOW a prior swing
      low (buy) / ABOVE a prior swing high (sell), then price closed back inside —
      a stop-hunt rejection. The entry follows the reversal.
  UHV-BO (S1): a highest-volume "climax" candle in the lookback, price swept its
      extreme, and the entry breaks back through it.
  NS/ND: a small DEAD-volume candle (low range + low volume) right before entry,
      sitting after a big candle — entry breaks the dead candle.
  UHV (plain): the entry-area candle is itself the volume climax of the window.

Prints per-trade flags + the dominant label, then a tally so we can see which
single setup Zee was running that day.

Run:  py classify_feb11.py
"""
import csv
from datetime import datetime
from pathlib import Path

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1 = COMMON / "rev_eng_m1.csv"
H1 = COMMON / "rev_eng_h1.csv"

ZEE = [
    ("01:32:19","buy",5045.07),("01:59:04","buy",5042.17),("02:09:38","sell",5040.68),
    ("02:29:02","buy",5039.03),("16:49:07","buy",5047.93),("16:52:21","buy",5050.77),
    ("16:54:10","buy",5056.74),("16:58:03","buy",5064.26),("17:02:45","buy",5055.71),
    ("17:36:11","buy",5056.53),("17:36:13","buy",5057.05),("17:37:26","buy",5045.82),
    ("17:49:59","buy",5048.32),("18:24:18","buy",5059.26),("18:41:50","buy",5078.10),
    ("19:08:59","sell",5083.28),("19:11:05","sell",5083.39),("19:11:51","sell",5083.79),
    ("19:20:34","sell",5084.21),("19:26:06","sell",5089.16),("19:29:31","buy",5086.34),
    ("19:32:48","buy",5084.71),("19:36:19","buy",5082.91),("19:38:39","buy",5083.28),
    ("19:38:59","buy",5086.33),("19:41:59","sell",5091.09),("19:42:26","sell",5093.18),
]


def load(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.append({"t": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                    "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                    "c": float(r["close"]), "v": float(r["tick_volume"])})
    return out


def h1_trend(h1, dt):
    """last-3-H1-close structure at dt: +1 up (HH+HL), -1 down, 0 mixed."""
    prior = [b for b in h1 if b["t"] <= dt][-3:]
    if len(prior) < 3:
        return 0
    c = [b["c"] for b in prior]
    if c[2] > c[1] > c[0]:
        return 1
    if c[2] < c[1] < c[0]:
        return -1
    return 0


def classify(m1, idx, side):
    """idx = entry-minute bar. Setup formed on bars before it; entry triggers in idx."""
    W = m1[max(0, idx - 14):idx + 1]      # ~15-bar context incl entry bar
    if len(W) < 8:
        return [], "n/a"
    vols = [b["v"] for b in W]
    rngs = [b["h"] - b["l"] for b in W]
    avgv = sum(vols) / len(vols)
    avgr = sum(rngs) / len(rngs)
    pre = W[:-1]                          # bars before the entry bar
    entry = W[-1]
    flags = []

    # UHV climax candle present in window
    uhv = max(pre, key=lambda b: b["v"])
    has_uhv = uhv["v"] >= 1.5 * avgv
    if has_uhv:
        flags.append("UHV")

    # SWEEP (liquidity grab + rejection) in the last ~6 bars
    last6 = W[-6:]
    if side == "buy":
        prior_low = min(b["l"] for b in pre[:-2]) if len(pre) > 2 else min(b["l"] for b in pre)
        swept = any(b["l"] < prior_low for b in last6)
        rejected = entry["c"] > prior_low
        if swept and rejected:
            flags.append("SWEEP")
    else:
        prior_high = max(b["h"] for b in pre[:-2]) if len(pre) > 2 else max(b["h"] for b in pre)
        swept = any(b["h"] > prior_high for b in last6)
        rejected = entry["c"] < prior_high
        if swept and rejected:
            flags.append("SWEEP")

    # UHV-BREAKOUT (S1): swept the UHV climax extreme then broke back through it
    if has_uhv:
        if side == "buy":
            swept_uhv = any(b["l"] < uhv["l"] for b in W[W.index(uhv) + 1:])
            broke = entry["c"] > uhv["h"] or entry["h"] > uhv["h"]
        else:
            swept_uhv = any(b["h"] > uhv["h"] for b in W[W.index(uhv) + 1:])
            broke = entry["c"] < uhv["l"] or entry["l"] < uhv["l"]
        if swept_uhv and broke:
            flags.append("UHV-BO")

    # NS/ND: a small dead-volume candle just before entry, after a bigger candle
    dead = W[-2]
    dead_small = (dead["h"] - dead["l"]) < 0.6 * avgr and dead["v"] < 0.7 * avgv
    after_big = (W[-3]["h"] - W[-3]["l"]) > avgr if len(W) >= 3 else False
    if dead_small and after_big:
        flags.append("NSND")

    # dominant label: prefer the most specific
    if "UHV-BO" in flags:
        lab = "UHV-BO (S1)"
    elif "NSND" in flags:
        lab = "NS/ND"
    elif "SWEEP" in flags:
        lab = "SWEEP (S3)"
    elif "UHV" in flags:
        lab = "plain UHV"
    else:
        lab = "?"
    return flags, lab


def feats(m1, idx, side):
    """Richer, descriptive features around the entry bar (idx)."""
    W = m1[max(0, idx - 14):idx + 1]
    pre, entry = W[:-1], W[-1]
    avgv = sum(b["v"] for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    vols = sorted((b["v"] for b in W), reverse=True)
    vrank = vols.index(entry["v"]) + 1                       # 1 = highest-vol bar in window
    prior_hi = max(b["h"] for b in pre)
    prior_lo = min(b["l"] for b in pre)
    fresh_hi = entry["h"] > prior_hi                         # broke to a new high (momentum/continuation)
    fresh_lo = entry["l"] < prior_lo
    body = "grn" if entry["c"] > entry["o"] else "red"
    big = (entry["h"] - entry["l"]) > 1.3 * avgr
    return dict(vrank=vrank, n=len(W), fresh_hi=fresh_hi, fresh_lo=fresh_lo,
                body=body, big=big, avgv=avgv,
                entry_v=entry["v"], hi_break=("HIbrk" if fresh_hi else ""),
                lo_break=("LObrk" if fresh_lo else ""))


def ctx_line(m1, idx):
    """3 bars before + the entry bar: 'o>c (range) v=NN' each."""
    parts = []
    for b in m1[idx - 3:idx + 1]:
        d = "grn" if b["c"] > b["o"] else "red"
        parts.append(f"[{b['o']:.1f}>{b['c']:.1f} {d} v{int(b['v'])}]")
    return " ".join(parts)


def main():
    m1 = load(M1)
    h1 = load(H1)
    by_min = {b["t"]: i for i, b in enumerate(m1)}
    tally = {}
    print(f"{'time':>9} {'side':>4} {'entry':>8} {'trnd':>4} {'vrank':>5} {'brk':>6} {'body':>4}  "
          f"{'flags':<18} {'dominant':<12}")
    print("-" * 96)
    rows = []
    for hms, side, px in ZEE:
        dt = datetime.strptime(f"2026.02.11 {hms}", "%Y.%m.%d %H:%M:%S").replace(second=0)
        idx = by_min.get(dt)
        if idx is None:
            print(f"{hms:>9} {side:>4} {px:>8.2f}   BAR MISSING"); continue
        tr = {1: "up", -1: "dn", 0: "mix"}[h1_trend(h1, dt)]
        flags, lab = classify(m1, idx, side)
        f = feats(m1, idx, side)
        brk = f["hi_break"] or f["lo_break"] or "-"
        print(f"{hms:>9} {side:>4} {px:>8.2f} {tr:>4} {f['vrank']:>5} {brk:>6} {f['body']:>4}  "
              f"{','.join(flags):<18} {lab:<12}")
        tally[lab] = tally.get(lab, 0) + 1
        rows.append((hms, side, idx))
    print("-" * 96)
    print("TALLY:", "  ".join(f"{k}={v}" for k, v in sorted(tally.items(), key=lambda x: -x[1])))

    # Detailed bar context for the mysterious downtrend-buy cluster + one evening sell
    print("\n=== BAR CONTEXT (3 bars before + entry bar) for key entries ===")
    for hms, side, idx in rows:
        if hms in ("16:49:07", "16:54:10", "17:02:45", "18:41:50", "19:08:59", "19:36:19"):
            print(f"{hms} {side}:  {ctx_line(m1, idx)}")


if __name__ == "__main__":
    main()
