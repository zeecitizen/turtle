"""zeeuhv_brain.py — ZeeUHV's four laws, judging OANDA bars instead of broker bars.

Zee, 2026-08-12, after v2's volume swap changed nothing:
    "so we can implement this feature branch as on exness as: OANDA prices + OANDA
     volume -> 93.28% +$2,599"

Not literally — XAUUSD_R3 is a custom symbol we built from our own archive, so it can be
backtested and never traded. But the idea behind it is sound and buildable:

    DECIDE on OANDA data. EXECUTE at the broker.

That is what this is. The same four laws that live in mt5/ZeeUHV.mq5, run against
Common/Files/oanda_m1.csv — real OANDA prices AND real OANDA traded volume — with the
resulting setup handed to the broker for filling.

WHY IT MIGHT BEAT THE CHART EA
    XAUUSD_R3  OANDA prices + OANDA volume    93.28%   +$2,599
    XAUUSD     broker prices + broker volume  80-89%   -$3,956
    v2         broker prices + OANDA volume   80.00%   -$2,866   <- volume alone did nothing

Holding prices constant and swapping volume changed nothing, so whatever the edge is,
it lives in the PRICES. This engine is the only way to act on those prices.

WHY IT MIGHT NOT
    The 93.28% assumed fills at OANDA's prices. Real fills happen at the broker's, and
    the gap between the two feeds is larger than our 1-point target. The edge may not
    survive the crossing. That is the whole question, and no backtest can answer it —
    only this engine and the chart EA trading side by side on real fills.

PAPER BY DEFAULT. It logs what it WOULD have done and touches nothing. Zee's live
ZeeUHV is 9-for-9 and must not be disturbed, and two engines firing the same setup on
one account is the double-firing risk we removed from the matcher four days ago.

    py monitor/zeeuhv_brain.py                 # one scan, print what it sees
    py monitor/zeeuhv_brain.py --loop 20       # keep watching (paper)
    py monitor/zeeuhv_brain.py --loop 20 --fire  # actually place orders. Deliberate.
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import zee_uhv as Z                                   # the SAME rules as the EA

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
FEED = COMMON / "oanda_m1.csv"
ARCHIVE = Path(__file__).parent / "tape_archive_xau.csv"
SIGNAL = COMMON / "zeeuhv_brain_signal.json"          # what the executor would read
JOURNAL = Path(__file__).parent / "zeeuhv_brain_paper.jsonl"
SEEN = Path(__file__).parent / ".zeeuhv_brain_seen"
HEARTBEAT = COMMON / "zeeuhv_brain_heartbeat.txt"
LOCK = Path(__file__).parent / ".zeeuhv_brain.lock"

# The shipped ZeeUHV configuration, so the two engines differ ONLY in their data.
STOP_PTS = 20.0
TARGET_PTS = 1.0
UHV_BODY_MIN = 0.5
TREND_LOOK = 20
RETRACE_BACK = 20
MAX_HOLD_MIN = 60
LOTS = 0.10


def only_one_of_me():
    """Three matchers once ran at once, each able to fire the same setup. A second
    brain is the same hazard, so a stale-tolerant PID lock refuses the duplicate."""
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().split()[0])
            os.kill(pid, 0)
            print(f"  another brain is already running (pid {pid}) — exiting")
            return False
        except (ProcessLookupError, ValueError, IndexError):
            pass
        except PermissionError:
            print("  another brain is already running — exiting")
            return False
    LOCK.write_text(f"{os.getpid()} {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    return True


def load_bars(limit=4000):
    """Prefer the live feed; fall back to the archive when the feed is thin, because a
    300-bar window cannot show a 20-bar trend plus a 20-bar retracement plus history."""
    rows = []
    for f in (ARCHIVE, FEED):
        if not f.exists():
            continue
        try:
            rows += [dict(t=int(r["time_unix"]), o=float(r["open"]), h=float(r["high"]),
                          l=float(r["low"]), c=float(r["close"]), v=int(r["volume"]))
                     for r in csv.DictReader(f.open(encoding="utf-8", errors="ignore"))]
        except Exception:
            continue
    seen, out = set(), []
    for b in sorted(rows, key=lambda x: x["t"]):
        if b["t"] in seen:
            continue
        seen.add(b["t"])
        out.append(b)
    return out[-limit:]


def find_setup(bars, now=None):
    """Exactly the EA's sequence: trend, retracement, UHV, breakout on THIS bar.

    2026-08-12: this said "the last CLOSED bar" and took bars[-1], which is the bar
    STILL FORMING. The brain therefore judged a half-built candle on every scan and
    recorded ZERO setups in nine hours, while a replay of the same tape found three
    (13:21, 14:24, 15:33 UTC). The logic was never wrong; it was being fed an
    incomplete bar.

    A bar is complete only once the NEXT minute has begun. Anything else is a
    candle whose high, low and close have not happened yet — and every rule here
    depends on all three.
    """
    import time as _t
    i = len(bars) - 1
    cutoff = (now if now is not None else _t.time()) - 60
    while i > 0 and bars[i]["t"] > cutoff:
        i -= 1                                         # step back to a CLOSED bar
    t = Z.trend_at(bars, i, look=TREND_LOOK)
    if t == 0:
        return None, "ranging — his setup needs a trend"
    side = "buy" if t > 0 else "sell"
    o = Z.retracement_origin(bars, i - 1, side, back=RETRACE_BACK)
    if o is None:
        return None, "no valid retracement"
    u = Z.find_uhv(bars, o, i, side, min_body_frac=UHV_BODY_MIN)
    if u is None:
        return None, "no UHV inside the retracement"
    b = Z.breakout_after(bars, u, side)
    if b is None:
        return None, "UHV found, no lawful breakout"
    if b != i:
        return None, "the breakout was an earlier bar"
    bar = bars[i]
    entry = bar["c"]
    sl = entry - STOP_PTS if side == "buy" else entry + STOP_PTS
    tp = entry + TARGET_PTS if side == "buy" else entry - TARGET_PTS
    return dict(t=bar["t"], side=side, entry=entry, sl=sl, tp=tp,
                uhv_vol=bars[u]["v"], brk_vol=bar["v"],
                diamonds=Z.diamonds_for(bars, u, i, side)), None


def resolve(bars, sig):
    """Walk forward from the signal bar asking WHICH CAME FIRST — the target or the
    stop. Anything that only compares extremes gets the order wrong, which is the exact
    error that cost us the DohaLevel call."""
    start = next((k for k, b in enumerate(bars) if b["t"] == sig["t"]), None)
    if start is None:
        return None
    for k in range(start + 1, len(bars)):
        b = bars[k]
        mins = (b["t"] - sig["t"]) / 60
        if sig["side"] == "buy":
            if b["l"] <= sig["sl"]:
                return dict(outcome="stop", pnl=-STOP_PTS * LOTS * 100, mins=mins)
            if b["h"] >= sig["tp"]:
                return dict(outcome="target", pnl=TARGET_PTS * LOTS * 100, mins=mins)
        else:
            if b["h"] >= sig["sl"]:
                return dict(outcome="stop", pnl=-STOP_PTS * LOTS * 100, mins=mins)
            if b["l"] <= sig["tp"]:
                return dict(outcome="target", pnl=TARGET_PTS * LOTS * 100, mins=mins)
        if mins >= MAX_HOLD_MIN:
            move = (b["c"] - sig["entry"]) if sig["side"] == "buy" else (sig["entry"] - b["c"])
            return dict(outcome="aged", pnl=move * LOTS * 100, mins=mins)
    return None                                        # still open


def scan(fire=False, quiet=False):
    bars = load_bars()
    if len(bars) < 80:
        print(f"  only {len(bars)} bars — not enough to judge a setup")
        return
    HEARTBEAT.write_text(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    sig, why = find_setup(bars)
    newest = datetime.fromtimestamp(bars[-1]["t"], tz=timezone.utc)
    if not sig:
        if not quiet:
            print(f"  {newest:%H:%M} UTC · {len(bars)} bars · no setup — {why}")
        return
    seen = set(SEEN.read_text().split()) if SEEN.exists() else set()
    key = f"{sig['t']}_{sig['side']}"
    if key in seen:
        if not quiet:
            print(f"  {newest:%H:%M} UTC · setup already recorded ({key})")
        return
    SEEN.write_text(" ".join(list(seen)[-400:] + [key]))
    rec = dict(seen_at=f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}",
               bar=f"{datetime.fromtimestamp(sig['t'], tz=timezone.utc):%Y-%m-%d %H:%M}",
               mode="FIRE" if fire else "PAPER", **sig)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"  ★ {newest:%H:%M} UTC  {sig['side'].upper():4s} @ {sig['entry']:.2f}  "
          f"SL {sig['sl']:.2f}  TP {sig['tp']:.2f}  "
          f"{sig['diamonds']}💎  UHV vol {sig['uhv_vol']} vs breakout {sig['brk_vol']}  "
          f"[{rec['mode']}]")
    if fire:
        # Diamonds NEVER gate; they MULTIPLY. Each one buys another ticket, exactly as
        # ZeeUHV.mq5 does — that stack is worth six times the profit of a single ticket,
        # and the brain had been silently trading without it.
        tickets = 1 + max(0, min(sig["diamonds"], 3))
        SIGNAL.write_text(json.dumps(dict(
            ts=int(time.time()), symbol="XAUUSD", side=sig["side"], lots=LOTS,
            tickets=tickets, diamonds=sig["diamonds"],
            sl=round(sig["sl"], 2), tp=round(sig["tp"], 2), source="zeeuhv_brain")))
        print(f"     signal written: {sig['diamonds']} diamond(s) -> {tickets} ticket(s)")


def replay():
    """Score every setup this engine WOULD have taken across the whole archive — the
    only honest way to compare it with the chart EA before either has enough live fills."""
    bars = load_bars(limit=100000)
    print(f"REPLAY — {len(bars):,} OANDA bars, "
          f"{datetime.fromtimestamp(bars[0]['t'], tz=timezone.utc):%d %b} to "
          f"{datetime.fromtimestamp(bars[-1]['t'], tz=timezone.utc):%d %b} UTC\n")
    out = []
    for i in range(80, len(bars)):
        window = bars[:i + 1]
        sig, _ = find_setup(window)
        if not sig:
            continue
        r = resolve(bars, sig)
        if r:
            out.append((sig, r))
    if not out:
        print("  no completed setups in this window")
        return
    w = [x for _, x in out if x["pnl"] > 0]
    print(f"  {len(out)} setups · {len(w)}W/{len(out)-len(w)}L = {len(w)/len(out)*100:.1f}%")
    print(f"  net ${sum(x['pnl'] for _, x in out):+,.2f} at {LOTS} lots, one ticket each")
    import collections
    c = collections.Counter(x["outcome"] for _, x in out)
    print(f"  closed by: {dict(c)}")
    print()
    print("  THIS IS A PYTHON REPLAY. Per CLAUDE.md it is a HYPOTHESIS, never a result.")
    print("  Python has historically overstated the win rate by ~16 points. Only MT5's")
    print("  tester or real fills may promote it.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--fire", action="store_true", help="place real orders (deliberate)")
    ap.add_argument("--replay", action="store_true", help="score the whole archive")
    a = ap.parse_args()
    if a.replay:
        replay()
        raise SystemExit
    if a.loop and not only_one_of_me():
        raise SystemExit
    if a.fire:
        print("  *** FIRE MODE — this will place real orders alongside the chart EA ***")
    while True:
        try:
            scan(fire=a.fire, quiet=bool(a.loop))
        except Exception as e:
            print(f"  scan error: {type(e).__name__}: {e}")
        if not a.loop:
            break
        time.sleep(a.loop)
