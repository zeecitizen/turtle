"""claude_judge.py — the CLAUDE EA: Claude's eyes decide, the MQL5 EA executes.

Zee 2026-08-02: stop hard-coding trend rules; let Claude LOOK at the chart and judge.
Proven on real broker P&L: Claude's visual calls turned -$115.40 into +$16.80 on the
same 6 trades (both big losers skipped), and scored 50/50 on Zee's own grading.

Flow:
    matcher (mechanical)  ->  PENDING setup + chart PNG   [nothing is traded yet]
    Claude (vision)       ->  approve.py TAKE <mult> | SKIP <why>
    EA (millisecond)      ->  executes + manages the exit
    fills                 ->  reviewed by Claude to improve the next call

Why not click MT5 buttons: a signal file is deterministic, carries the exact lot and SL,
executes in milliseconds and logs every step. UI clicking can misfire on a moved window
and place the wrong size — strictly worse.

Files (Common\\Files):
    pending_setup.json   what the mechanical layer found, waiting for a verdict
    pending_setup.png    the chart Claude looks at
    <signal file>        written ONLY after Claude says TAKE
"""
from __future__ import annotations
import csv, json, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
import build_trend_game as G
from case_engine import extract_features
from setup_strength import strength

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
PENDING = COMMON / "pending_setup.json"
PENDING_PNG = Path(__file__).parent / "setup_labels" / "pending_setup.png"
JOURNAL = Path(__file__).parent / "claude_judgments.jsonl"

MARKETS = {
    "BTC": dict(data=COMMON / "btc_m1.csv", mark=COMMON / "btc_m1.symbol",
                signal=COMMON / "btc_signal.json", tz=2, must="BTC", k=4.5),
    "XAU": dict(data=COMMON / "oanda_m1.csv", mark=COMMON / "oanda_m1.symbol",
                signal=COMMON / "case_signal.json", tz=2, must="XAU", k=1.0),
}


def load_bars(path):
    bars = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            bars.append(B.Bar(datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None),
                              float(r["open"]), float(r["high"]), float(r["low"]),
                              float(r["close"]), float(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def scan(market="BTC", max_age_min=3):
    """Find a FRESH mechanical setup and park it as PENDING (nothing is traded).
    Returns the pending dict, or None."""
    m = MARKETS[market]
    sym = m["mark"].read_text(encoding="ascii").strip() if m["mark"].exists() else ""
    if m["must"] not in sym.upper():
        return {"error": f"data symbol is '{sym}', expected {m['must']} — chart switched?"}
    bars = load_bars(m["data"])
    if len(bars) < 40:
        return {"error": f"only {len(bars)} bars"}
    stale = (datetime.now(timezone.utc).replace(tzinfo=None) - bars[-1].t).total_seconds() / 60
    if stale > max_age_min:
        return {"error": f"data {stale:.0f} min stale"}
    k = m["k"]
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5 * k; B.TREND_DOM = 0.0      # NO trend rule — Claude judges that
    last_closed = bars[-2].t
    fresh = [s for s in B.detect_full(bars) if s["open_t"] >= last_closed - timedelta(minutes=max_age_min)]
    if not fresh:
        return None
    s = fresh[-1]
    G.draw(bars, s, PENDING_PNG, m["tz"])
    f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
    pend = {"market": market, "side": s["side"], "entry": round(s["entry"], 2),
            "time": s["open_t"].strftime("%Y-%m-%d %H:%M"),
            "uhv_vol": bars[s["u"]].v, "strength": round(strength(f), 2),
            "brk_body": round(f["brk_body"], 2),
            "png": str(PENDING_PNG), "created": int(time.time()), "status": "PENDING"}
    PENDING.write_text(json.dumps(pend), encoding="ascii")
    return pend


def near(market="BTC", back=14):
    """ARMED state: a valid retracement with a UHV exists but the breakout has NOT
    happened yet. Zee: "agar setup k hum qareeb hain to Claude EA die out na ho" — the
    loop must stay awake and study the picture instead of sleeping through the entry.
    Returns dict with armed=True/False (+ the level the breakout must cross)."""
    m = MARKETS[market]
    sym = m["mark"].read_text(encoding="ascii").strip() if m["mark"].exists() else ""
    if m["must"] not in sym.upper():
        return {"error": f"data symbol is '{sym}', expected {m['must']}"}
    bars = load_bars(m["data"])
    if len(bars) < 40:
        return {"error": f"only {len(bars)} bars"}
    stale = (datetime.now(timezone.utc).replace(tzinfo=None) - bars[-1].t).total_seconds() / 60
    k = m["k"]
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5 * k; B.TREND_DOM = 0.0
    n = len(bars); px = bars[-1].c
    out = []
    for side in ("BUY", "SELL"):
        # most recent valid retracement origin
        o = next((j for j in range(n - 1, max(n - 1 - B.LB, 0), -1) if B.is_origin(bars, j, side)), None)
        if o is None: continue
        rs = B.retr_zone_start(bars, o, side)
        best = None
        for kk in range(rs, n):
            c = bars[kk]
            if not (c.is_bear if side == "BUY" else c.is_bull): continue
            if kk - 1 >= 0 and bars[kk - 1].v >= c.v: continue
            if kk + 1 < n and bars[kk + 1].v >= c.v: continue
            if best is None or c.v > bars[best].v: best = kk
        if best is None or best < n - 1 - back: continue
        U = bars[best]
        lvl = U.h if side == "BUY" else U.l
        crossed = any((bars[z].is_bull and bars[z].c > lvl) if side == "BUY"
                      else (bars[z].is_bear and bars[z].c < lvl) for z in range(best + 1, n))
        if crossed: continue                       # already broken out — not "armed"
        out.append({"side": side, "uhv_time": U.t.strftime("%H:%M") + "Z",
                    "uhv_vol": round(U.v, 2), "uhv_body_ratio": round(U.body_ratio, 2),
                    "breakout_level": round(lvl, 2), "price_now": round(px, 2),
                    "distance": round(abs(px - lvl), 2),
                    "bars_since_uhv": n - 1 - best})
    return {"market": market, "armed": bool(out), "stale_min": round(stale, 1),
            "price": round(px, 2), "candidates": out}


def approve(verdict, mult=1.0, reason="", max_age_sec=180):
    """Claude's verdict. TAKE -> write the signal the EA executes. SKIP -> log only."""
    if not PENDING.exists():
        return {"error": "no pending setup"}
    p = json.loads(PENDING.read_text(encoding="ascii"))
    age = int(time.time()) - p.get("created", 0)
    if age > max_age_sec:
        rec = {**p, "verdict": "EXPIRED", "age_sec": age, "reason": "judged too late"}
    elif verdict.upper() == "TAKE":
        m = MARKETS[p["market"]]
        body = ('{"id":%d,"side":"%s","entry":%.2f,"mult":%.2f,"lots":%.2f,"ts":%d,"time":"%s"}'
                % (int(time.time()) % 100000, p["side"], p["entry"], mult,
                   round(0.10 * mult, 2), int(time.time()), p["time"]))
        m["signal"].write_text(body, encoding="ascii")
        rec = {**p, "verdict": "TAKE", "mult": mult, "reason": reason, "age_sec": age}
    else:
        rec = {**p, "verdict": "SKIP", "reason": reason, "age_sec": age}
    rec["judged_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    PENDING.unlink(missing_ok=True)
    return rec


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        print(json.dumps(scan(sys.argv[2] if len(sys.argv) > 2 else "BTC"), indent=1))
    elif cmd == "near":
        print(json.dumps(near(sys.argv[2] if len(sys.argv) > 2 else "BTC"), indent=1))
    else:   # approve TAKE 2.0 "reason"  |  approve SKIP "reason"
        v = sys.argv[2]
        mult = float(sys.argv[3]) if v.upper() == "TAKE" and len(sys.argv) > 3 else 1.0
        why = sys.argv[4] if len(sys.argv) > 4 else (sys.argv[3] if v.upper() == "SKIP" and len(sys.argv) > 3 else "")
        print(json.dumps(approve(v, mult, why), indent=1))
