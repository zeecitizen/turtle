"""Are yesterday's failure patterns typical? Split Saad_strategy_15min v1.18 (= v1.17 trades) full-year MT5 trades
(XAUUSD_TK real ticks, 1 lot, Jan 6 - Oct 8: testing/saad_trades_tkfull.csv) by the attributes the PXBT losers
shared. Bars with the EA's indicators: testing/bars_M15_7001.csv (BarDump on the same data). This splits REAL
tester trades; it is not a simulation."""
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
def read_saad_csv(path):
    """The EA doesn't quote fields: 'day close, in loss' in exit_reason adds a comma. Re-join it."""
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    head = lines[0].split(","); rows = []
    for ln in lines[1:]:
        p = ln.split(",")
        while len(p) > len(head):
            p[17:19] = [p[17] + "," + p[18]]
        rows.append(p)
    d = pd.DataFrame(rows, columns=head)
    for c in ("entry", "sl_initial", "risk_usd", "best_price", "sl_final", "exit", "profit", "commission", "swap", "net", "sl_moves"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


tr = read_saad_csv(T / "saad_trades_tkfull.csv")
bars = pd.read_csv(T / "bars_M15_7001.csv"); bars["t"] = pd.to_datetime(bars.time, format="%Y.%m.%d %H:%M")
bars = bars.set_index("t").sort_index()
tr["et"] = pd.to_datetime(tr.entry_time, format="%Y.%m.%d %H:%M:%S")
tr["entry_bar"] = tr.et.dt.floor("15min")
idx = bars.index


def prev_bar(t):
    i = idx.searchsorted(t) - 1
    return idx[i] if i >= 0 else pd.NaT


tr["setup_bar"] = tr.entry_bar.apply(prev_bar)
tr["gap_entry"] = (tr.entry_bar - tr.setup_bar) > pd.Timedelta(minutes=15)      # a market closure between setup and entry candle
s = bars.reindex(tr.setup_bar)
tr["ema9"], tr["ema50"], tr["atr"], tr["er"] = s.ema9.values, s.ema50.values, s.atr14.values, s.er16.values
tr["long"] = tr.side == "BUY"
tr["with_trend"] = np.where(tr.long, tr.ema9 > tr.ema50, tr.ema9 < tr.ema50)
tr["pathB"] = tr.long & tr.tp1_rule.fillna("").str.contains("none|trail|below", case=False)
tr["on50"] = tr.setup.fillna("").str.contains("on the 50 EMA")
tr["hour"] = tr.et.dt.hour
tr["win"] = tr.net > 0
tr["half"] = np.where(tr.et < "2026-07-01", "Jan-Jun", "Jul-Oct")


def tab(by, label):
    g = tr.groupby(by).agg(trades=("net", "size"), WR=("win", "mean"), net=("net", "sum"), avg=("net", "mean"), worst=("net", "min"))
    g["WR"] = (100 * g.WR).round(1); g["net"] = g.net.round(0); g["avg"] = g.avg.round(0); g["worst"] = g.worst.round(0)
    print(f"\n=== {label}"); print(g.to_string())


print(f"{len(tr)} trades, WR {100 * tr.win.mean():.1f}%, net {tr.net.sum():,.0f}")
tab("long", "BUY (True) vs SELL (False)")
tab(["long", "with_trend"], "side x with the M15 EMA trend (EMA9 vs EMA50 at the setup candle)")
tab(["long", "with_trend", "half"], "... by half")
tab(["long", "pathB"], "BUY path B = no TP1 (exit EMA below / too close to the entry)")
tab(["long", "on50"], "BUY on the 50 EMA vs the 9 EMA")
tr["er_band"] = pd.cut(tr.er, [0, 0.15, 0.20, 0.30, 1.0])
tab(["er_band"], "chop: efficiency ratio at the setup candle")
tab(["long", "er_band"], "... by side")
tab("gap_entry", "entry right after a market closure (setup candle before the daily break / weekend)")
tab(["gap_entry", "half"], "... by half")
tr["sess"] = pd.cut(tr.hour, [-1, 6, 12, 17, 21, 24], labels=["00-07 Asia", "07-13 London", "13-18 NY am", "18-22 NY pm", "22-24 reopen"])
tab("sess", "server-hour session (Axi server = New York + 7)")
lw = tr[tr.long & ~tr.with_trend]
print(f"\nBUYS AGAINST THE M15 TREND: {len(lw)} trades, WR {100 * lw.win.mean():.1f}%, net {lw.net.sum():,.0f}")
both = tr[tr.long & ~tr.with_trend & (tr.er < 0.15)]
print(f"... and with ER < 0.15: {len(both)} trades, WR {100 * both.win.mean():.1f}%, net {both.net.sum():,.0f}")
tr.to_csv(T / "saad_trades_tkfull_tagged.csv", index=False)
