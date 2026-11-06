"""uhv_ticktest.py - every UHV Diamond setup (simdata/uhv_setups.json) played as one of Zee's game rounds on PrimeXBT's REAL ticks.

Zee 2026-11-05: "let's test for the game's 2 pip / 2 pip ... turn each setup into a trade with the tick tester and show wins and losses".
  entry   the first tick at least LATENCY_S after the breakout candle closed (the game's order delay); a buy fills at the ask, a sell at the bid
  exit    +TP / -SL from that fill, whichever real tick reaches it first; a buy exits on the bid, a sell on the ask (the spread is paid)
  limit   a round still open after MAX_HOLD_S closes at the tick price then (rare at 2 pips)
One pass over the tick export (tab-separated DATE TIME BID ASK ...; a blank field = unchanged; the file's clock = PrimeXBT server = UTC).
Writes simdata/uhv_trades.json. Run: py monitor/TurtleTVUHV/uhv_ticktest.py [tp_pips] [sl_pips]"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TICKS = Path(r"C:\Users\zeesh\turtle\EURUSD_tick_data\PrimeXBTMT5Downloads\EURUSDp_202603060000_202611042359.csv")
LATENCY_S = 0.3
MAX_HOLD_S = 4 * 3600
PIP = 0.0001
LOT_EUR = 1000                                   # one game coin = 1,000 EUR -> 1 pip = $0.10


def run(tp_pips=2.0, sl_pips=2.0, setups=None, out_name="uhv_trades.json"):
    setups = setups if setups is not None else json.loads((HERE / "simdata" / "uhv_setups.json").read_text(encoding="utf-8"))["setups"]
    pend = sorted(setups, key=lambda s: s["t"])
    tp, sl = tp_pips * PIP, sl_pips * PIP
    live, done, k = [], [], 0
    bid = ask = None
    with TICKS.open(encoding="utf-8", errors="replace") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4:
                continue
            if p[2]:
                bid = float(p[2])
            if p[3]:
                ask = float(p[3])
            if bid is None or ask is None:
                continue
            d, t = p[0], p[1]
            ts = dt.datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]), int(t[0:2]), int(t[3:5]), int(t[6:8]),
                             int((t[9:12] or "0").ljust(3, "0")) * 1000, tzinfo=dt.timezone.utc).timestamp()
            while k < len(pend) and ts >= pend[k]["t"] + LATENCY_S:          # open every setup whose entry time has come
                s = pend[k]; k += 1
                if ts - s["t"] > 300:                                          # no tick for 5 minutes after the setup (a gap): skip it
                    continue
                fill = ask if s["side"] > 0 else bid
                live.append({**s, "fill": fill, "t_in": ts, "spread_in": round((ask - bid) / PIP, 2)})
            if not live:
                continue
            keep = []
            for r in live:
                side, fill = r["side"], r["fill"]
                px = bid if side > 0 else ask                                  # what closing would get now
                move = (px - fill) * side
                why = "tp" if move >= tp - 1e-9 else "sl" if move <= -sl + 1e-9 else "time" if ts - r["t_in"] >= MAX_HOLD_S else None
                if why:
                    r.update(exit=px, t_out=ts, why=why, pips=round(move / PIP, 2), usd=round(move * LOT_EUR, 3), secs=round(ts - r["t_in"], 1))
                    done.append(r)
                else:
                    keep.append(r)
            live = keep
    done.sort(key=lambda r: r["t_in"])
    busy_until, game = 0.0, []                                                 # the game plays one round at a time
    for r in done:
        if r["t_in"] >= busy_until:
            game.append(r["t"]); busy_until = r["t_out"]
    gset = set(game)
    for r in done:
        r["game"] = r["t"] in gset
    out = {"tp_pips": tp_pips, "sl_pips": sl_pips, "latency_s": LATENCY_S, "lot_eur": LOT_EUR, "trades": done, "unfinished": len(live),
           "made": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
    (HERE / "simdata" / out_name).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def stats(rows):
    n = len(rows); w = sum(1 for r in rows if r["pips"] > 0)
    return {"n": n, "wins": w, "wr": round(100.0 * w / n, 1) if n else None, "pips": round(sum(r["pips"] for r in rows), 1),
            "usd": round(sum(r["usd"] for r in rows), 2), "per_round_usd": round(sum(r["usd"] for r in rows) / n, 4) if n else None}


if __name__ == "__main__":
    a = [float(x) for x in sys.argv[1:3]] or [2.0, 2.0]
    o = run(*a) if len(a) == 2 else run(a[0], a[0])
    T = o["trades"]
    for name, rows in (("every setup", T), ("one at a time (the game)", [r for r in T if r["game"]]), ("the EA v1.27 would take", [r for r in T if r["ea"]]),
                       ("royal", [r for r in T if r["royal"]]), ("buys", [r for r in T if r["side"] > 0]), ("sells", [r for r in T if r["side"] < 0])):
        print(f"{name:28s}", stats(rows))
