"""oanda_live_matcher.py — LIVE fast-scalp signal writer (OANDA volume).

Reads the OANDA M1 CSV (kept fresh by oanda_bridge --loop), runs the dom=0 fast-scalp
detector, and when a NEW setup completes on the last CLOSED bar writes
Common/Files/case_signal.json for CaseSignalExecutor.mq5 to execute on the Blueberry
demo. Poll fast (~20s) so seconds-scalp setups aren't missed.

Pipeline:  oanda_bridge --loop 20  ->  oanda_m1.csv  ->  THIS  ->  case_signal.json  ->  EA
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from case_engine import extract_features
from setup_strength import strength, lot_for

CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
SIGNAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_signal.json")
LOG = Path(__file__).parent / "oanda_signals.jsonl"
LOT = 0.10
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=1.2)  # TREND FILTER ON (Zee: "selling in an uptrend" caused all 3 big losses)
BRK_BODY_MIN = 0.5   # breakout must be a MOMENTUM candle (Zee on loss #2: "brkt candle
                      # not momentum candle"). body/range >= this.


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def write_signal(seq, s, lots, tier, st):
    # EA sets its own 3pt SL (InpHardSLPts); we still send sl for reference.
    body = ('{"id":%d,"side":"%s","entry":%.2f,"sl":%.2f,"lots":%.2f,"ts":%d,"time":"%s"}'
            % (seq, s["side"], s["entry"], s["sl"], lots, int(datetime.utcnow().timestamp()),
               s["open_t"].strftime("%Y-%m-%d %H:%M")))
    SIGNAL.write_text(body, encoding="ascii")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": seq, "side": s["side"], "entry": s["entry"], "lots": lots,
                             "tier": tier, "strength": round(st, 2),
                             "time": s["open_t"].strftime("%Y-%m-%d %H:%M"),
                             "emitted_utc": datetime.utcnow().isoformat(timespec="seconds")}) + "\n")


def main():
    for k, v in CFG.items(): setattr(B, k, v)
    seen = set(); seq = 0
    print("[oanda_matcher] live fast-scalp — watching oanda_m1.csv")
    while True:
        try:
            bars = load_bars()
            if len(bars) > 30:
                last_closed = bars[-2].t     # -1 may still be forming
                # WALL-CLOCK freshness guard: if the data edge is stale (internet/feed
                # outage), do NOT fire — else we'd trade a hours-old setup at live price.
                stale_min = (datetime.utcnow() - bars[-1].t).total_seconds() / 60
                if stale_min > 3:
                    print(f"[oanda_matcher] data stale ({stale_min:.0f} min behind) — holding, no fire")
                    time.sleep(20); continue
                for s in B.detect_full(bars):
                    key = f"{s['open_t']}_{s['side']}"
                    # only fire setups whose breakout is on the last few CLOSED bars (fresh)
                    if key in seen or s["open_t"] < last_closed - timedelta(minutes=3):
                        continue
                    f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
                    if f["brk_body"] < BRK_BODY_MIN:      # Zee: breakout must be momentum
                        seen.add(key)
                        print(f"[oanda_matcher] SKIP {s['side']} {s['open_t'].strftime('%H:%M')} — weak breakout body {f['brk_body']:.2f}")
                        continue
                    seen.add(key)
                    seq += 1
                    st = strength(f); lots, tier = lot_for(st)
                    write_signal(seq, s, lots, tier, st)
                    print(f"[oanda_matcher] SIGNAL #{seq} {s['side']} @{s['entry']} lots={lots} ({tier}) ({s['open_t'].strftime('%H:%M')}UTC)")
        except Exception as e:
            print("[oanda_matcher] err:", e, file=sys.stderr)
        time.sleep(20)


if __name__ == "__main__":
    main()
