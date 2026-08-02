"""live_rule_ledger.py — forward-test each teacher rule-STEP on live candles.

For every closed M5 candle in today's live tick file, evaluate the atomic
rule-steps (the building blocks of S1/S3/NSND from the videos), then use the
SUBSEQUENT real ticks to score whether a BUY/SELL taken on that signal would
have hit +TP before -SL. Accumulate per-rule and per-combo confirmation rates.

This is FORWARD evidence on live candles (Zee's request). It complements the
12-day historical backtest (the statistical engine) and catches live drift.

Idempotent: rebuilds the ledger from the whole day's tick file each run, so
the hourly loop just re-runs it as the day's ticks grow.
Outputs: monitor/strategy_lab/live_rule_ledger.json (+ printed summary)
"""
import csv, sys, json, glob
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path("C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
OUT = Path(__file__).parent / "live_rule_ledger.json"
TP = 7.5      # bracket used to score a signal's forward outcome ($ at price pts)
SL = 7.5
FWD_MIN = 90  # minutes of forward ticks to resolve the bracket


def load_ticks(path):
    ticks = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
                bid = float(row["bid"]); ask = float(row["ask"])
            except Exception:
                continue
            ticks.append((t, bid, ask))
    return ticks


def build_m1(ticks):
    buckets = {}
    for t, bid, ask in ticks:
        key = t.replace(second=0, microsecond=0)
        mid = (bid + ask) / 2
        if key not in buckets:
            buckets[key] = {"time": key, "open": mid, "high": mid, "low": mid,
                            "close": mid, "vol": 0}
        b = buckets[key]
        b["high"] = max(b["high"], mid); b["low"] = min(b["low"], mid)
        b["close"] = mid; b["vol"] += 1
    return sorted(buckets.values(), key=lambda x: x["time"])


def aggregate(m1, k):
    out = {}
    for b in m1:
        bm = (b["time"].minute // k) * k
        bt = b["time"].replace(minute=bm, second=0, microsecond=0)
        if bt not in out:
            out[bt] = dict(time=bt, open=b["open"], high=b["high"],
                           low=b["low"], close=b["close"], vol=b["vol"])
        else:
            x = out[bt]
            x["high"] = max(x["high"], b["high"]); x["low"] = min(x["low"], b["low"])
            x["close"] = b["close"]; x["vol"] += b["vol"]
    return sorted(out.values(), key=lambda x: x["time"])


def find_bull_fvgs(bars):
    fv = []
    for i in range(2, len(bars)):
        gl, gh = bars[i-2]["high"], bars[i]["low"]
        if gh <= gl: continue
        filled = next((bars[j]["time"] for j in range(i+1, len(bars)) if bars[j]["low"] < gl), None)
        fv.append((bars[i]["time"], gl, gh, filled))
    return fv


def avg_range(m5, idx, n=10):
    js = range(max(0, idx-n), idx)
    rs = [m5[j]["high"]-m5[j]["low"] for j in js]
    return sum(rs)/len(rs) if rs else 0


# ── Atomic rule-steps for a BUY context at m5[idx] (the just-closed candle) ──
def eval_buy_rules(m5, idx, m5_fvgs):
    bo = m5[idx]
    R = {}
    R["is_green"] = bo["close"] > bo["open"]
    R["uptrend"] = idx >= 24 and (bo["close"] - m5[idx-24]["close"]) > 1.0
    start = max(0, idx-15)
    reds = [j for j in range(start, idx) if m5[j]["close"] < m5[j]["open"]]
    R["has_retrace_reds"] = len(reds) > 0
    uhv = max(reds, key=lambda j: m5[j]["vol"]) if reds else None
    R["uhv_big_spread"] = bool(uhv is not None and
        (m5[uhv]["high"]-m5[uhv]["low"]) >= 1.3*avg_range(m5, uhv))
    R["swept_uhv_low"] = bool(uhv is not None and
        any(m5[j]["low"] < m5[uhv]["low"] for j in range(uhv+1, idx+1)))
    # wick-reclaim (S3): green wicks below some retrace red low, closes inside, higher vol
    wick = False
    for j in reds:
        r = m5[j]
        if bo["low"] < r["low"] and bo["close"] > r["low"] and bo["vol"] > r["vol"]:
            wick = True; break
    R["wick_reclaim"] = wick
    rng = bo["high"]-bo["low"]
    R["small_upper_wick"] = rng > 0 and (bo["high"]-max(bo["open"],bo["close"]))/rng <= 0.35
    # M5 FVG tap during retracement
    tap = False
    for (t0, gl, gh, filled) in m5_fvgs:
        if t0 >= bo["time"]: continue
        if filled is not None and filled <= bo["time"]: continue
        for j in range(start, idx+1):
            if m5[j]["low"] <= gh and m5[j]["high"] >= gl: tap = True; break
        if tap: break
    R["m5_fvg_tap"] = tap
    return R


def eval_sell_rules(m5, idx, m5_fvgs_bear):
    bo = m5[idx]
    R = {}
    R["is_red"] = bo["close"] < bo["open"]
    R["downtrend"] = idx >= 24 and (m5[idx-24]["close"] - bo["close"]) > 1.0
    start = max(0, idx-15)
    greens = [j for j in range(start, idx) if m5[j]["close"] > m5[j]["open"]]
    R["has_retrace_greens"] = len(greens) > 0
    uhv = max(greens, key=lambda j: m5[j]["vol"]) if greens else None
    R["uhv_big_spread"] = bool(uhv is not None and
        (m5[uhv]["high"]-m5[uhv]["low"]) >= 1.3*avg_range(m5, uhv))
    R["swept_uhv_high"] = bool(uhv is not None and
        any(m5[j]["high"] > m5[uhv]["high"] for j in range(uhv+1, idx+1)))
    wick = False
    for j in greens:
        g = m5[j]
        if bo["high"] > g["high"] and bo["close"] < g["high"] and bo["vol"] > g["vol"]:
            wick = True; break
    R["wick_reclaim"] = wick
    rng = bo["high"]-bo["low"]
    R["small_lower_wick"] = rng > 0 and (min(bo["open"],bo["close"])-bo["low"])/rng <= 0.35
    tap = False
    for (t0, gl, gh, filled) in m5_fvgs_bear:
        if t0 >= bo["time"]: continue
        if filled is not None and filled <= bo["time"]: continue
        for j in range(start, idx+1):
            if m5[j]["low"] <= gh and m5[j]["high"] >= gl: tap = True; break
        if tap: break
    R["m5_fvg_tap"] = tap
    return R


def find_bear_fvgs(bars):
    fv = []
    for i in range(2, len(bars)):
        gh, gl = bars[i-2]["low"], bars[i]["high"]   # bearish gap: older.low > newer.high
        if gh <= gl: continue
        filled = next((bars[j]["time"] for j in range(i+1, len(bars)) if bars[j]["high"] > gh), None)
        fv.append((bars[i]["time"], gl, gh, filled))
    return fv


def score_forward(m5, idx, ticks_by_min, side):
    """After candle idx closes, scan forward ticks; did +TP hit before -SL?
    Returns +1 win, -1 loss, 0 unresolved (not enough forward data)."""
    entry_t = m5[idx]["time"] + timedelta(minutes=5)
    entry = m5[idx]["close"]
    end_t = entry_t + timedelta(minutes=FWD_MIN)
    tp = entry + TP if side > 0 else entry - TP
    sl = entry - SL if side > 0 else entry + SL
    t = entry_t
    while t < end_t:
        bar = ticks_by_min.get(t)
        if bar:
            if side > 0:
                if bar["low"] <= sl: return -1
                if bar["high"] >= tp: return +1
            else:
                if bar["high"] >= sl: return -1
                if bar["low"] <= tp: return +1
        t += timedelta(minutes=1)
    return 0


def main():
    files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-05-2*.csv")))
    if not files:
        print("[no live tick file yet]"); return
    ticks = []
    for f in files[-2:]:  # today + maybe prior day for M5 history
        ticks += load_ticks(f)
    if len(ticks) < 200:
        print(f"[only {len(ticks)} ticks — too early]"); return
    m1 = build_m1(ticks)
    m5 = aggregate(m1, 5)
    m5_fvgs = find_bull_fvgs(m5)
    m5_fvgs_bear = find_bear_fvgs(m5)
    m1_by = {b["time"]: b for b in m1}
    print(f"live candles: {len(m1)} M1 -> {len(m5)} M5  ({m5[0]['time']} .. {m5[-1]['time']})")

    rule_stats = defaultdict(lambda: {"n":0,"win":0,"loss":0})
    combo_stats = defaultdict(lambda: {"n":0,"win":0,"loss":0})
    last_resolved = len(m5)
    for idx in range(30, len(m5)):
        # only score candles with enough forward ticks
        if m5[idx]["time"] + timedelta(minutes=5+FWD_MIN) > m5[-1]["time"]:
            last_resolved = idx; break
        # BUY-context rules
        Rb = eval_buy_rules(m5, idx, m5_fvgs)
        ob = None
        for name, fired in Rb.items():
            if not fired: continue
            if ob is None:
                ob = score_forward(m5, idx, m1_by, +1)
                if ob == 0: break
            s = rule_stats["BUY:"+name]; s["n"] += 1
            if ob > 0: s["win"] += 1
            elif ob < 0: s["loss"] += 1
        if ob is not None and ob != 0:
            if Rb["uptrend"] and Rb["is_green"] and Rb["wick_reclaim"] and Rb["m5_fvg_tap"]:
                c = combo_stats["S3_liq_sweep(M5fvg)"]; c["n"]+=1; c["win"]+= (ob>0); c["loss"]+= (ob<0)
            if Rb["uptrend"] and Rb["uhv_big_spread"] and Rb["swept_uhv_low"]:
                c = combo_stats["S1_bigspread_climax"]; c["n"]+=1; c["win"]+= (ob>0); c["loss"]+= (ob<0)
        # SELL-context rules
        Rs = eval_sell_rules(m5, idx, m5_fvgs_bear)
        os_ = None
        for name, fired in Rs.items():
            if not fired: continue
            if os_ is None:
                os_ = score_forward(m5, idx, m1_by, -1)
                if os_ == 0: break
            s = rule_stats["SELL:"+name]; s["n"] += 1
            if os_ > 0: s["win"] += 1
            elif os_ < 0: s["loss"] += 1
        if os_ is not None and os_ != 0:
            if Rs["downtrend"] and Rs["uhv_big_spread"] and Rs["swept_uhv_high"]:
                c = combo_stats["S1sell_bigspread_climax"]; c["n"]+=1; c["win"]+= (os_>0); c["loss"]+= (os_<0)
            if Rs["downtrend"] and Rs["is_red"] and Rs["wick_reclaim"] and Rs["m5_fvg_tap"]:
                c = combo_stats["S3sell_liq_sweep(M5fvg)"]; c["n"]+=1; c["win"]+= (os_>0); c["loss"]+= (os_<0)

    def wr(d):
        tot = d["win"]+d["loss"]
        return (d["win"]/tot*100) if tot else 0
    print("\n  ATOMIC RULE-STEPS (live forward-confirmation, BUY bracket +/-$%.1f over %dm):" % (TP, FWD_MIN))
    print(f"  {'rule':<20} {'n':>4} {'win':>4} {'loss':>4} {'WR%':>6}")
    for name in sorted(rule_stats, key=lambda k: -wr(rule_stats[k])):
        d = rule_stats[name]
        print(f"  {name:<20} {d['n']:>4} {d['win']:>4} {d['loss']:>4} {wr(d):>5.0f}%")
    print("\n  NAMED COMBOS:")
    for name, d in combo_stats.items():
        print(f"  {name:<26} n={d['n']} W={d['win']} L={d['loss']} WR={wr(d):.0f}%")

    led = {"updated": datetime.now().isoformat(timespec="seconds"),
           "candles_scored": last_resolved-30,
           "rules": {k: dict(v, wr=round(wr(v),1)) for k,v in rule_stats.items()},
           "combos": {k: dict(v, wr=round(wr(v),1)) for k,v in combo_stats.items()}}
    OUT.write_text(json.dumps(led, indent=2))
    print(f"\n  ledger -> {OUT}")


if __name__ == "__main__":
    main()
