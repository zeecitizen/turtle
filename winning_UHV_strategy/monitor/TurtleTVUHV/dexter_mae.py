"""dexter_mae.py - Dexter's Lab analysis: why does a high win rate end in one big loss?
Reads an MT5 run's own trades (runs/<id>.json events), measures each trade's excursions from the 2026 1-minute
candles (MAE = furthest against us, MFE = furthest for us, both in $ of price), and estimates what a tighter stop
or a different target would have done to THOSE trades. An estimate to choose what MT5 should test next - never a result.
py dexter_mae.py [run_id]   -> prints a report and writes simdata/dexter_mae.json"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sim  # noqa: E402

DST = datetime(2026, 3, 8, tzinfo=timezone.utc).timestamp()       # MT5 event clock: 2 h behind the candles before, 3 h after


def tc(t):
    return t + (7200 if t < DST else 10800)


def trades_of(run):
    ent = {e["num"]: e for e in run["events"] if e["type"] == "entry"}
    out = []
    for e in run["events"]:
        if e["type"] == "exit" and e["num"] in ent:
            n = ent[e["num"]]
            out.append({"side": int(n["side"]), "tin": tc(n["t"]), "en": float(n["price"]), "sl": float(n["sl"]),
                        "tout": tc(e["t"]), "pnl": float(e["v1"]), "why": e.get("text", "")})
    return out


def analyse(run_id):
    run = json.loads((HERE / "runs" / f"{run_id}.json").read_text(encoding="utf-8"))
    lots = float(run["inputs"].get("InpLots", 1))
    per = 100.0 * lots                                            # $ of P&L per $1 of gold price
    D = sim.data("year1")
    t1, h1, l1 = np.asarray(D["t1"]), np.asarray(D["h1"]), np.asarray(D["l1"])
    T = trades_of(run)
    for x in T:
        a = int(np.searchsorted(t1, x["tin"] - 59, side="left")); b = int(np.searchsorted(t1, x["tout"], side="right"))
        if b <= a:
            x["mae"] = x["mfe"] = 0.0
            continue
        hi, lo = float(h1[a:b].max()), float(l1[a:b].min())
        x["mae"] = max(0.0, (x["en"] - lo) if x["side"] > 0 else (hi - x["en"]))
        x["mfe"] = max(0.0, (hi - x["en"]) if x["side"] > 0 else (x["en"] - lo))
        x["mins"] = (x["tout"] - x["tin"]) / 60.0
        x["hour"] = int((x["tin"] // 3600) % 24)
    pnl = np.array([x["pnl"] for x in T]); mae = np.array([x["mae"] for x in T]); mfe = np.array([x["mfe"] for x in T])
    win = pnl > 0
    res = {"run": run_id, "trades": len(T), "net": round(float(pnl.sum())), "wr": round(100 * float(win.mean()), 1),
           "avg_win": round(float(pnl[win].mean())), "avg_loss": round(float(pnl[~win].mean())),
           "breakeven_wr": round(100 * abs(pnl[~win].mean()) / (abs(pnl[~win].mean()) + pnl[win].mean()), 1),
           "worst5": sorted(pnl.tolist())[:5]}
    # how far winners went against us before winning
    q = [50, 75, 90, 95, 98, 99, 100]
    res["winner_mae_pct"] = {f"p{p}": round(float(np.percentile(mae[win], p)), 2) for p in q}
    res["loser_mae_pct"] = {f"p{p}": round(float(np.percentile(mae[~win], p)), 2) for p in q}
    # tighter stop S ($ of price): a trade whose MAE reached S is stopped at -S (plus the spread); the rest keep their result
    spread = 0.2
    rows = []
    for S in [2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25]:
        hit = mae >= S
        new = np.where(hit, -(S + spread) * per, pnl)
        w = new > 0
        rows.append({"stop": S, "net": round(float(new.sum())), "wr": round(100 * float(w.mean()), 1),
                     "worst": round(float(new.min())), "winners_lost": int((hit & win).sum()),
                     "avg_loss": round(float(new[~w].mean())) if (~w).any() else 0})
    res["stop_curve"] = rows
    # time stop N minutes: a trade still open after N minutes closes at that minute's close; the rest keep their result
    c1 = np.asarray(D["c1"])
    trows = []
    for N in [5, 10, 15, 20, 30, 45, 60, 90]:
        new = pnl.copy()
        for i, x in enumerate(T):
            if x.get("mins", 0) > N:
                k = int(np.searchsorted(t1, x["tin"] + N * 60, side="right")) - 1
                px = float(c1[k])
                new[i] = ((px - x["en"]) * x["side"] - spread) * per
        w = new > 0
        trows.append({"minutes": N, "net": round(float(new.sum())), "wr": round(100 * float(w.mean()), 1),
                      "worst": round(float(new.min())), "avg_loss": round(float(new[~w].mean())) if (~w).any() else 0,
                      "avg_win": round(float(new[w].mean())) if w.any() else 0})
    res["time_curve"] = trows
    # where are the big losses: hour of entry and time in trade
    big = pnl < np.percentile(pnl, 10)
    res["big_loss_hours"] = {str(h): int(sum(1 for x, b in zip(T, big) if b and x.get("hour") == h)) for h in range(24)}
    res["big_loss_minutes_median"] = round(float(np.median([x["mins"] for x, b in zip(T, big) if b])), 1)
    res["win_minutes_median"] = round(float(np.median([x["mins"] for x, w_ in zip(T, win) if w_])), 1)
    (HERE / "simdata" / "dexter_mae.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = analyse(sys.argv[1] if len(sys.argv) > 1 else "r20261024_235213")
    print(json.dumps({k: v for k, v in r.items() if k not in ("big_loss_hours",)}, indent=1))
