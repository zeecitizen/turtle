"""verify_probes_vs_bars.py — RIGOROUS cross-check of recent [PROBE] fires
against actual M1 OHLCV (rev_eng_m1_recent.csv).

Two-stage:
  STAGE 1 — pin the broker-time offset exactly. For each probe the EA logged
    an entry FILL price. That fill must fall inside the OHLC range of the
    *forming* bar at fire time. We test offsets 58..62 min and pick the one
    where the most entry prices land inside their forming bar.
  STAGE 2 — with the pinned offset, for each probe identify rates[1] (the
    just-closed bar = the detector's breakout candle) and verify:
      a. breakout colour (green=BUY, red=SELL)
      b. breakout.close > UHV.high (BUY) / < UHV.low (SELL)
      c. UHV bar colour, volume == logged, catSL == UHV.low/high
      d. UHV is the volume-peak of its colour within MaxLookback, with the
         detector's overlap rule (skip bars whose high>=bo.close for buy).
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\rev_eng_m1_recent.csv")

# (fire_pc, side, entry, uhv_hhmm, uhv_vol, R, catSL)
PROBES = [
    ("13:03:56", "sell", 4695.11, "13:11", 403, 10.32, 4705.43),
    ("13:09:40", "buy",  4696.83, "14:06", 223,  3.98, 4692.85),
    ("13:09:41", "buy",  4697.42, "14:06", 223,  4.57, 4692.85),
    ("13:21:11", "buy",  4696.68, "14:06", 223,  3.83, 4692.85),
    ("13:21:12", "buy",  4696.50, "14:06", 223,  3.65, 4692.85),
    ("13:26:58", "sell", 4689.94, "13:54", 364,  7.78, 4697.72),
    ("13:32:44", "sell", 4691.78, "13:54", 364,  5.94, 4697.72),
    ("13:32:46", "sell", 4691.80, "13:54", 364,  5.92, 4697.72),
    ("13:38:28", "buy",  4693.78, "13:52", 214,  2.54, 4691.24),
    ("13:38:29", "buy",  4693.75, "13:52", 214,  2.51, 4691.24),
    ("13:42:04", "buy",  4697.39, "14:25", 251,  7.63, 4689.76),
    ("13:42:05", "buy",  4697.47, "14:25", 251,  7.71, 4689.76),
    ("13:42:54", "buy",  4696.44, "14:25", 251,  6.68, 4689.76),
    ("13:42:55", "buy",  4696.19, "14:25", 251,  6.43, 4689.76),
]
MAX_LOOKBACK = 60


def load_bars():
    bars = []
    with open(CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            bars.append({
                "time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "vol": int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def main():
    bars = load_bars()
    by_time = {b["time"]: i for i, b in enumerate(bars)}
    today = bars[-1]["time"].date()
    print(f"Loaded {len(bars)} M1 bars: {bars[0]['time']} -> {bars[-1]['time']}\n")

    # ---- STAGE 1: pin the offset ----
    print("STAGE 1 — pinning broker-time offset (entry fill must be inside forming bar):")
    best_off, best_hits = None, -1
    for off in range(57, 63):
        hits = 0
        for (ft, side, entry, *_ ) in PROBES:
            pc = datetime.combine(today, datetime.strptime(ft, "%H:%M:%S").time())
            broker = pc + timedelta(minutes=off)
            forming = broker.replace(second=0)
            b = bars[by_time[forming]] if forming in by_time else None
            if b and (b["low"] - 0.05) <= entry <= (b["high"] + 0.05):
                hits += 1
        print(f"   offset +{off}min : {hits}/{len(PROBES)} entry prices inside their forming bar")
        if hits > best_hits:
            best_hits, best_off = hits, off
    print(f"   => pinned offset = +{best_off} min ({best_hits}/{len(PROBES)} fits)\n")
    off = timedelta(minutes=best_off)

    # ---- STAGE 2: rigorous per-probe verification ----
    print("STAGE 2 — verifying each probe's breakout candle + UHV against real bars:\n")
    ok = 0
    for (ft, side, entry, uhv_hhmm, uhv_vol, R, catSL) in PROBES:
        pc = datetime.combine(today, datetime.strptime(ft, "%H:%M:%S").time())
        broker = pc + off
        forming_t = broker.replace(second=0)
        bo_t = forming_t - timedelta(minutes=1)          # rates[1] = just-closed
        uhv_t = datetime.combine(today, datetime.strptime(uhv_hhmm, "%H:%M").time())

        bo = bars[by_time[bo_t]] if bo_t in by_time else None
        uhv = bars[by_time[uhv_t]] if uhv_t in by_time else None
        problems = []

        if not bo: problems.append(f"breakout bar {bo_t:%H:%M} missing")
        if not uhv: problems.append(f"UHV bar {uhv_t:%H:%M} missing")

        if bo and uhv:
            bo_green = bo["close"] > bo["open"]
            bo_red   = bo["close"] < bo["open"]
            # a. breakout colour
            if side == "buy"  and not bo_green: problems.append(f"breakout {bo_t:%H:%M} not green")
            if side == "sell" and not bo_red:   problems.append(f"breakout {bo_t:%H:%M} not red")
            # b. breakout condition
            if side == "buy"  and not bo["close"] > uhv["high"]:
                problems.append(f"close {bo['close']:.2f} !> UHV.high {uhv['high']:.2f}")
            if side == "sell" and not bo["close"] < uhv["low"]:
                problems.append(f"close {bo['close']:.2f} !< UHV.low {uhv['low']:.2f}")
            # c. UHV colour + volume + catSL
            if side == "buy"  and not uhv["close"] < uhv["open"]:
                problems.append(f"UHV {uhv_t:%H:%M} not RED")
            if side == "sell" and not uhv["close"] > uhv["open"]:
                problems.append(f"UHV {uhv_t:%H:%M} not GREEN")
            if uhv["vol"] != uhv_vol:
                problems.append(f"UHV vol {uhv['vol']} != logged {uhv_vol}")
            exp_cat = uhv["low"] if side == "buy" else uhv["high"]
            if abs(exp_cat - catSL) > 0.05:
                problems.append(f"catSL {catSL} != UHV {'low' if side=='buy' else 'high'} {exp_cat:.2f}")
            # d. UHV is the volume-peak of its colour in the lookback window
            bo_idx = by_time[bo_t]
            want_red = (side == "buy")
            peak_vol, peak_t = -1, None
            for k in range(bo_idx - 1, max(-1, bo_idx - 1 - MAX_LOOKBACK), -1):
                c = bars[k]
                if side == "buy"  and c["high"] >= bo["close"]: continue
                if side == "sell" and c["low"]  <= bo["close"]: continue
                is_red, is_green = c["close"] < c["open"], c["close"] > c["open"]
                if (want_red and is_red) or (not want_red and is_green):
                    if c["vol"] > peak_vol:
                        peak_vol, peak_t = c["vol"], c["time"]
            if peak_t != uhv_t:
                pt = f"{peak_t:%H:%M}" if peak_t else "none"
                problems.append(f"vol-peak in lookback is {pt} (vol {peak_vol}), not {uhv_t:%H:%M}")

        verdict = "VALID" if not problems else "ISSUE"
        if not problems: ok += 1
        bod = f"bo {bo_t:%H:%M} O{bo['open']:.2f} C{bo['close']:.2f} {'G' if bo and bo['close']>bo['open'] else 'R'}" if bo else "bo ?"
        uhd = f"uhv {uhv_t:%H:%M} H{uhv['high']:.2f} L{uhv['low']:.2f} v{uhv['vol']}" if uhv else "uhv ?"
        print(f"  {ft} {side.upper():<4} @{entry:.2f} | {bod} | {uhd} | {verdict}")
        for p in problems:
            print(f"        - {p}")

    print(f"\n{ok}/{len(PROBES)} probes verified VALID against actual M1 bars (offset +{best_off}min)")


if __name__ == "__main__":
    main()
