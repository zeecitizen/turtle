"""btc_live_matcher.py — LIVE fast-scalp signals for BTC (weekend market).

Same validated recipe as the XAUUSD matcher, but:
  - VOLUME FEED = COINBASE:BTCUSD. OANDA's BTC volume is unusable (spike ratio 1.37x,
    71 distinct values / 300 bars -> no detectable UHV). Coinbase is real exchange
    volume with spikes up to 212x median.
  - THRESHOLDS SCALED 4.5x (BTC median M1 range 5.19 vs XAUUSD 1.15).
  - Writes btc_signal.json (BtcCaseExecutor.mq5, magic 88022) — never the gold file.
  - VERIFIES the data file's .symbol marker contains BTC before firing, so a chart
    switch can never make us trade gold setups as BTC (or vice-versa).

Pipeline: oanda_bridge --out btc_m1.csv  ->  THIS  ->  btc_signal.json  ->  BtcCaseExecutor
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from case_engine import extract_features
from setup_strength import strength

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
CF = COMMON / "btc_m1.csv"
SYMBOL_MARK = COMMON / "btc_m1.symbol"
SIGNAL = COMMON / "btc_signal.json"
LOG = Path(__file__).parent / "btc_signals.jsonl"

K = 4.5   # BTC / XAUUSD volatility scale (median M1 range 5.19 vs 1.15)
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0,
           TREND_MIN_HUMP=0.5 * K, TREND_DOM=1.2)   # trend filter ON (Zee's rule)
BRK_BODY_MIN = 0.5                                   # momentum breakout (Zee's rule)
# conviction multiplier by strength (EA turns this into risk-based lots)
TIERS = [(0.66, 3.0, "3x STRONGEST"), (0.58, 2.0, "2x strong"), (0.50, 1.0, "1x normal")]


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.utcfromtimestamp(int(r["time_unix"]))
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]),
                              float(r["close"]), float(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def tier_for(st):
    for lo, mult, name in TIERS:
        if st >= lo: return mult, name
    return 0.25, "weak"


def write_signal(seq, s, mult, tier, st):
    body = ('{"id":%d,"side":"%s","entry":%.2f,"mult":%.2f,"ts":%d,"time":"%s"}'
            % (seq, s["side"], s["entry"], mult, int(datetime.utcnow().timestamp()),
               s["open_t"].strftime("%Y-%m-%d %H:%M")))
    SIGNAL.write_text(body, encoding="ascii")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": seq, "side": s["side"], "entry": s["entry"],
                             "mult": mult, "tier": tier, "strength": round(st, 2),
                             "time": s["open_t"].strftime("%Y-%m-%d %H:%M"),
                             "emitted_utc": datetime.utcnow().isoformat(timespec="seconds")}) + "\n")


def main():
    for k, v in CFG.items(): setattr(B, k, v)
    seen = set(); seq = 0
    print(f"[btc_matcher] live — Coinbase volume, thresholds x{K}, trend filter ON")
    while True:
        try:
            # SYMBOL GUARD: never fire on non-BTC data
            sym = SYMBOL_MARK.read_text(encoding="ascii").strip() if SYMBOL_MARK.exists() else ""
            if "BTC" not in sym.upper():
                print(f"[btc_matcher] data symbol is '{sym}' — not BTC, holding")
                time.sleep(20); continue
            bars = load_bars()
            if len(bars) > 30:
                stale_min = (datetime.utcnow() - bars[-1].t).total_seconds() / 60
                if stale_min > 3:
                    print(f"[btc_matcher] data stale ({stale_min:.0f} min) — holding")
                    time.sleep(20); continue
                last_closed = bars[-2].t
                for s in B.detect_full(bars):
                    key = f"{s['open_t']}_{s['side']}"
                    if key in seen or s["open_t"] < last_closed - timedelta(minutes=3):
                        continue
                    f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
                    seen.add(key)
                    if f["brk_body"] < BRK_BODY_MIN:
                        print(f"[btc_matcher] SKIP {s['side']} {s['open_t'].strftime('%H:%M')} — weak breakout {f['brk_body']:.2f}")
                        continue
                    st = strength(f); mult, tier = tier_for(st)
                    seq += 1
                    write_signal(seq, s, mult, tier, st)
                    print(f"[btc_matcher] SIGNAL #{seq} {s['side']} @{s['entry']:.2f} mult={mult} ({tier}) str {st:.2f}")
        except Exception as e:
            print("[btc_matcher] err:", e, file=sys.stderr)
        time.sleep(20)


if __name__ == "__main__":
    main()
