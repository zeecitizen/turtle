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

CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
SIGNAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_signal.json")
LOG = Path(__file__).parent / "oanda_signals.jsonl"
LOT = 0.10
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=0.0)


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def write_signal(seq, s):
    # EA sets its own 3pt SL (InpHardSLPts); we still send sl for reference.
    body = ('{"id":%d,"side":"%s","entry":%.2f,"sl":%.2f,"lots":%.2f,"time":"%s"}'
            % (seq, s["side"], s["entry"], s["sl"], LOT, s["open_t"].strftime("%Y-%m-%d %H:%M")))
    SIGNAL.write_text(body, encoding="ascii")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": seq, "side": s["side"], "entry": s["entry"],
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
                for s in B.detect_full(bars):
                    key = f"{s['open_t']}_{s['side']}"
                    # only fire setups whose breakout is on the last few CLOSED bars (fresh)
                    if key in seen or s["open_t"] < last_closed - timedelta(minutes=3):
                        continue
                    seen.add(key)
                    seq += 1
                    write_signal(seq, s)
                    print(f"[oanda_matcher] SIGNAL #{seq} {s['side']} @{s['entry']} ({s['open_t'].strftime('%H:%M')}UTC)")
        except Exception as e:
            print("[oanda_matcher] err:", e, file=sys.stderr)
        time.sleep(20)


if __name__ == "__main__":
    main()
