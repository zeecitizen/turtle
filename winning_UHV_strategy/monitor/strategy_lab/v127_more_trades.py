"""v127_more_trades.py - Zee 2026-10-19: "check if some of these changes can help increase the number of trades taken safely? because currently
we don't take a single trade on some days" + "the changes i did on the indicator resulted in a 96% winrate. mainly because of setting target to a
fixed target". Each trade-adding change ALONE on v1.27 (full year, random delay, 2 lots), with the number of days that had a trade; plus the
chart's fixed +$1 / +$2 target (test copy Saad_strategy_15min_betest = v1.26 + InpX1TpUsd, nose 0.35 = v1.27). Writes v127_more_trades.json."""
import json
import queue
import random
import sys
import threading
import time
from pathlib import Path

sys.argv = sys.argv[:1]
import axi_rig  # noqa: E402
import v127_night_run as v  # noqa: E402  (page)

MAIN, BET = "Saad_strategy_15min", "Saad_strategy_15min_betest"
N35 = {"InpNoseMax": "0.35"}
JOBS = [("v1.27", MAIN, {}),
        ("wick 0.45 -> 0.35", MAIN, {"InpWickMin": "0.35"}), ("wick 0.45 -> 0.30", MAIN, {"InpWickMin": "0.30"}),
        ("setup candle >= 0.45 ATR (was 0.55)", MAIN, {"InpMinRangeAtr": "0.45"}), ("setup candle >= 0.35 ATR", MAIN, {"InpMinRangeAtr": "0.35"}),
        ("touch tolerance 2 pips (was 1)", MAIN, {"InpTouchPips": "2"}), ("touch tolerance 3 pips", MAIN, {"InpTouchPips": "3"}),
        ("2 candles to break (was 1)", MAIN, {"InpBreakBars": "2"}), ("ADX 30 -> 25", MAIN, {"InpAdxMin": "25"}),
        ("SELL setups on either EMA", MAIN, {"InpShortLine": "2"}), ("unticked box: skip instead of stand aside", MAIN, {"InpBandOff": "0"}),
        ("2 positions at once", MAIN, {"InpMaxPos": "2"}),
        ("fixed target +$1 (the chart's 96%)", BET, dict(N35, InpX1TpUsd="1")), ("fixed target +$2", BET, dict(N35, InpX1TpUsd="2"))]
RIGS = ["axi", "axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
was = v.page().get("auto", True)
v.page(False)
q = queue.Queue()
for j in JOBS:
    q.put(j)
res, lock = {}, threading.Lock()


def worker(rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea(MAIN, rig=rig)
    axi_rig.compile_ea(BET, rig=rig)
    while True:
        try:
            name, ea, s = q.get_nowait()
        except queue.Empty:
            return
        for a in range(3):
            r = axi_rig.run(ea, "XAUUSD_BB", "M15", dict(s, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17", deposit=100000, rig=rig,
                            tag=f"more_{rig}", exec_mode=-1)
            if r.get("error") not in ("authorization failed", "no report"):
                break
            axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
        ts = r.get("trade_stats") or {}
        n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
        wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
        dd = float(str(r.get("dd") or "0").split("(")[0].replace(" ", "") or 0)
        mo = r.get("months") or {}
        ds = r.get("day_stats") or {}
        with lock:
            res[name] = {"ea": ea, "sets": s, "net": net, "pf": float(r.get("pf") or 0), "wr": wr, "n": n, "dd": dd, "months": mo, "days": ds,
                         "h1": round(sum(x for k, x in mo.items() if k <= "2026.06")), "h2": round(sum(x for k, x in mo.items() if k >= "2026.07")),
                         "red": [k[5:] for k, x in mo.items() if x < 0], "err": r.get("error")}
            print(f"{name}: net {net:+,.0f} PF {res[name]['pf']:.2f} WR {wr:.1f}% trades {n} days-with-trades {ds.get('days')} (green {ds.get('green')}) "
                  f"DD {dd:,.0f} | Jan-Jun {res[name]['h1']:+,} Jul-Oct {res[name]['h2']:+,} | red {res[name]['red']}", flush=True)


ths = [threading.Thread(target=worker, args=(g,)) for g in RIGS]
for th in ths:
    th.start(); time.sleep(5)
for th in ths:
    th.join()
json.dump(res, open(Path(__file__).with_name("v127_more_trades.json"), "w"), indent=1)
v.page(bool(was))
print("DONE", flush=True)
