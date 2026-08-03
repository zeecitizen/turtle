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
JUDGED  = Path(__file__).parent / ".judged_setups.json"   # keys already ruled on

MARKETS = {
    "BTC": dict(data=COMMON / "btc_m1.csv", mark=COMMON / "btc_m1.symbol",
                signal=COMMON / "btc_signal.json", close=COMMON / "btc_close.json",
                tz=2, must="BTC", k=4.5, max_lots=0.30),
    "XAU": dict(data=COMMON / "oanda_m1.csv", mark=COMMON / "oanda_m1.symbol",
                signal=COMMON / "case_signal.json", close=COMMON / "xau_close.json",
                tz=2, must="XAU", k=1.0, max_lots=0.10),
}


def _judged():
    """Setups already ruled on. Without this the 3-minute freshness window re-parks the
    same setup every scan and Claude re-judges it over and over."""
    try:
        return set(json.loads(JUDGED.read_text(encoding="ascii")))
    except Exception:
        return set()


def _mark_judged(key):
    s = _judged(); s.add(key)
    try:
        JUDGED.write_text(json.dumps(sorted(s)[-200:]), encoding="ascii")
    except Exception:
        pass


def load_bars(path):
    bars = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            bars.append(B.Bar(datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None),
                              float(r["open"]), float(r["high"]), float(r["low"]),
                              float(r["close"]), float(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def scan(market="XAU", max_age_min=3):
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
    # A weekend or holiday leaves a hole in the data: the last Friday bars sit directly
    # beside the first Sunday bar, tens of points away. The detector reads that gap as a
    # breakout off a "UHV" that is really just Friday's closing candle. Refuse to judge
    # until enough genuinely new bars exist to form a shape.
    gap = None
    for i in range(len(bars) - 1, max(len(bars) - 60, 0), -1):
        if (bars[i].t - bars[i - 1].t).total_seconds() > 30 * 60:
            gap = i
            break
    if gap is not None:
        fresh_bars = len(bars) - gap
        if fresh_bars < 30:
            return {"error": f"only {fresh_bars} bars since the session gap "
                             f"({bars[gap - 1].t:%a %H:%M} -> {bars[gap].t:%a %H:%M} UTC) "
                             f"- need 30 before any setup here is real"}

    # A setup already parked and still inside its judging window is returned UNCHANGED.
    # Replacing it would let a concurrent scan swap the chart out from under a verdict.
    if PENDING.exists():
        try:
            cur = json.loads(PENDING.read_text(encoding="ascii"))
            age = int(time.time()) - cur.get("created", 0)
            if age <= 180:
                return cur
            # An expired pending means a setup went UNJUDGED. Record it, loudly - a silent
            # miss is the same failure class as the [invalid stops] session that traded
            # nothing while every light was green.
            rec = {**cur, "verdict": "MISSED", "age_sec": age,
                   "reason": "expired before a verdict was recorded",
                   "judged_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            try:
                with JOURNAL.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
            except Exception:
                pass
            PENDING.unlink(missing_ok=True)          # expired -> make room for a new one
        except Exception:
            PENDING.unlink(missing_ok=True)
    k = m["k"]
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    # The trend rule is mechanical, not a judgement call. It used to be left entirely to me
    # ("Claude judges that"), and the result was a SELL offered in a plainly rising market.
    # Zee 2026-08-03: "humara setup sirf ya to SELL ki indication deta hai agar trend down
    # ho, ya BUY ki agar uptrend strong ho." DOM = 1.0 means the move in the trade's own
    # direction must be at least as large as the move against it.
    B.TREND_MIN_HUMP = 0.5 * k; B.TREND_DOM = 1.0
    last_closed = bars[-2].t
    done = _judged()
    fresh = [s for s in B.detect_full(bars)
             if s["open_t"] >= last_closed - timedelta(minutes=max_age_min)
             and f'{s["open_t"]}_{s["side"]}' not in done]
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


def near(market="XAU", back=14):
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
        # The trend decides the side. Without this the same picture armed BUY *and* SELL,
        # which the setup never does: a SELL needs a downtrend, a BUY needs an uptrend.
        # R=1.0 means the move in the trade's own direction must be at least as large as
        # the move against it.
        if not B.trend_ok(bars, o, side, R=1.0):
            continue
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
        lots = min(round(0.10 * mult, 2), m.get("max_lots", 0.10))
        body = ('{"id":%d,"side":"%s","entry":%.2f,"mult":%.2f,"lots":%.2f,"ts":%d,"time":"%s"}'
                % (int(time.time()) % 100000, p["side"], p["entry"], mult,
                   lots, int(time.time()), p["time"]))
        m["signal"].write_text(body, encoding="ascii")
        rec = {**p, "verdict": "TAKE", "mult": mult, "lots": lots, "reason": reason, "age_sec": age}
    else:
        rec = {**p, "verdict": "SKIP", "reason": reason, "age_sec": age}
    _mark_judged(f'{p["time"]}:00_{p["side"]}')
    _mark_judged(f'{p["time"]}_{p["side"]}')
    rec["judged_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    PENDING.unlink(missing_ok=True)
    return rec


def fire(market="XAU", side="SELL", mult=1.0, reason=""):
    """Open a trade with no pending signal behind it.

    Zee, watching a breakout the engine would not re-signal: "is time breakout ho raha hai,
    apne SELL nahi kholna?" The detector allows one UHV per retracement, so once a weak
    candle has already crossed the level it will not fire again even if a proper momentum
    candle closes beyond a minute later. That rule is right for the machine and wrong for
    the moment — this is the door for when the human is looking straight at it.

    Every firing is journalled as manual with the reason, so these never get quietly mixed
    into the engine's own record."""
    m = MARKETS[market]
    bars = load_bars(m["data"])
    px = bars[-1].c
    lots = min(round(0.10 * mult, 2), m.get("max_lots", 0.10))
    body = ('{"id":%d,"side":"%s","entry":%.2f,"mult":%.2f,"lots":%.2f,"ts":%d,"time":"%s"}'
            % (int(time.time()) % 100000, side.upper(), px, mult, lots, int(time.time()),
               bars[-1].t.strftime("%Y-%m-%d %H:%M")))
    m["signal"].write_text(body, encoding="ascii")
    rec = {"market": market, "side": side.upper(), "entry": round(px, 2), "mult": mult,
           "lots": lots, "verdict": "TAKE", "source": "manual",
           "reason": reason or "fired by hand",
           "time": bars[-1].t.strftime("%Y-%m-%d %H:%M"),
           "judged_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + chr(10))
    return rec


def watch(market="XAU"):
    """Render the OPEN position so Claude can manage the exit with her eyes.

    Zee, correcting me: *"tum candle form hote har second dekh sakti ho... tumhari speed
    ENOUGH hai trade ko open/close karne ke liye. Masla ye hai tum EA pe depend karti ho
    jabke tumhare paas EYES hain."* He is right, and the measurements agree with him: a
    verdict today took 9-91 seconds while our trades last 2-5 minutes, so a position gets
    looked at many times before it closes.

    The evidence is stronger than the speed argument, though. The EA's fixed 0.2pt give-back
    captured only 32% of what the winners offered ($145.61 of $460.89 on 2026-07-31). That
    trail is not fast — it is BLIND. It cannot say "this one is still running, hold".

    The hard stop stays where it is. It is insurance, not an opinion."""
    m = MARKETS[market]
    hb = COMMON / ("xau_live.json" if market == "XAU" else "btc_live.json")
    if not hb.exists():
        return {"error": "no EA heartbeat — nothing to watch"}
    try:
        d = json.loads(hb.read_text(encoding="ascii", errors="replace"))
    except Exception as e:
        return {"error": f"heartbeat unreadable: {e}"}
    pos = d.get("positions") or []
    if not pos:
        return {"open": 0, "price": d.get("bid"), "note": "no open position"}

    bars = load_bars(m["data"])
    import build_trend_game as G
    out = Path(__file__).parent / "setup_labels" / "position.png"
    i = len(bars) - 1
    s = {"i": i, "o": max(0, i - 6), "u": max(0, i - 3), "side": pos[0]["side"]}
    G.draw(bars, s, out, m["tz"])

    # annotate the entry, the current price and how far it has run
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
        fig = plt.figure(figsize=(12, 6.6))
        ax = fig.add_axes([0, 0.08, 1, 0.92]); ax.axis("off")
        ax.imshow(mpimg.imread(str(out)))
        p0 = pos[0]
        run = (p0["price"] - p0["entry"]) if p0["side"] == "BUY" else (p0["entry"] - p0["price"])
        fig.text(0.02, 0.03,
                 f"OPEN {p0['side']} {p0['lots']} @ {p0['entry']:.2f}   "
                 f"now {p0['price']:.2f}   ({run:+.2f} pt)   "
                 f"P&L ${p0['profit']:+.2f}   SL {p0['sl']:.2f}",
                 fontsize=13, fontweight="bold",
                 color=("#16a34a" if p0["profit"] >= 0 else "#dc2626"))
        fig.savefig(out, dpi=85, bbox_inches="tight")
        plt.close(fig)
    except Exception:
        pass

    for q in pos:
        q["run_pts"] = round((q["price"] - q["entry"]) if q["side"] == "BUY"
                             else (q["entry"] - q["price"]), 2)
    return {"open": len(pos), "positions": pos, "price": d.get("bid"),
            "png": str(out), "heartbeat_age": d.get("age_sec")}


def close(market="XAU", reason=""):
    """Order the EA to exit everything it holds on this market.

    The EA's trail is faster than any judgement call on the mechanical give-back, so this is
    NOT for micro-managing a scalp. It is for the moment the picture changes and the trade no
    longer makes sense - the part Zee has always said belongs to the master."""
    m = MARKETS[market]
    body = ('{"cmd":"close","market":"%s","ts":%d,"reason":"%s"}'
            % (market, int(time.time()), (reason or "").replace('"', "'")[:200]))
    m["close"].write_text(body, encoding="ascii")
    rec = {"market": market, "verdict": "CLOSE", "reason": reason,
           "judged_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "fire":
        mk = sys.argv[2] if len(sys.argv) > 2 else "XAU"
        sd = sys.argv[3] if len(sys.argv) > 3 else "SELL"
        ml = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
        rs = sys.argv[5] if len(sys.argv) > 5 else ""
        print(json.dumps(fire(mk, sd, ml, rs), indent=1)); raise SystemExit
    if cmd == "watch":
        print(json.dumps(watch(sys.argv[2].upper() if len(sys.argv) > 2 else "XAU"),
                         indent=1, default=str))
    elif cmd == "close":
        mk = sys.argv[2].upper() if len(sys.argv) > 2 else "XAU"
        why = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(close(mk, why), indent=1))
    elif cmd == "scan":
        print(json.dumps(scan(sys.argv[2] if len(sys.argv) > 2 else "XAU"), indent=1))
    elif cmd == "near":
        print(json.dumps(near(sys.argv[2] if len(sys.argv) > 2 else "XAU"), indent=1))
    else:   # approve TAKE 2.0 "reason"  |  approve SKIP "reason"
        v = sys.argv[2]
        mult = float(sys.argv[3]) if v.upper() == "TAKE" and len(sys.argv) > 3 else 1.0
        why = sys.argv[4] if len(sys.argv) > 4 else (sys.argv[3] if v.upper() == "SKIP" and len(sys.argv) > 3 else "")
        print(json.dumps(approve(v, mult, why), indent=1))
