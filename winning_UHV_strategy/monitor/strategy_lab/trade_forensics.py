"""Forensics for the PXBT account 1364880 trades of 13-14 Oct 2026 (Saad_strategy_15min v1.17 at 2 lots on the
trading machine; one 0.1-lot trade by an old v1.11 on Claude's PC). Data: PXBT's own XAUUSDp candles
(testing/pxbt_live_M1.csv, _M15.csv: dumped from the broker by BarDumpLiveEA). Server time = UTC; PKT = +5 h.
Rules checked are v1.17's defaults (lifecycle.md): setup candle touches EMA9 (or EMA50 for longs), shape (pin /
hammer / star / marubozu >= 0.53), range >= 0.55 x ATR(14), ER(16) >= 0.11, break by 2 pips within 1 candle,
stop 35 pips ($3.50) beyond the candle, TP1 = exit EMA (longs) / last support (shorts), CTC at 75% of the way."""
import json
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
m1 = pd.read_csv(T / "pxbt_live_M1.csv"); m1["t"] = pd.to_datetime(m1.time, format="%Y.%m.%d %H:%M")
m15 = pd.read_csv(T / "pxbt_live_M15.csv"); m15["t"] = pd.to_datetime(m15.time, format="%Y.%m.%d %H:%M")
m1 = m1.set_index("t"); m15 = m15.set_index("t")

TRADES = [  # from the account statement (server time)
    dict(ticket=67046250, side=-1, lots=2, open="2026-10-13 15:01:06", entry=4165.57, close="2026-10-13 17:01:57", exit=4151.575, pnl=2799.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67082390, side=1, lots=0.1, open="2026-10-13 17:23:13", entry=4156.63, close="2026-10-13 17:25:01", exit=4156.22, pnl=-4.10, src="v1.11 on Claude's PC, M1 chart"),
    dict(ticket=67099697, side=1, lots=2, open="2026-10-13 18:45:34", entry=4162.51, close="2026-10-13 20:55:01", exit=4160.39, pnl=-424.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67111138, side=1, lots=2, open="2026-10-13 22:01:49", entry=4162.39, close="2026-10-13 23:58:51", exit=4154.77, pnl=-1524.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67117659, side=-1, lots=2, open="2026-10-14 00:33:08", entry=4157.62, close="2026-10-14 01:23:49", exit=4157.62, pnl=0.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67138222, side=1, lots=2, open="2026-10-14 03:16:49", entry=4169.02, close="2026-10-14 04:06:51", exit=4158.02, pnl=-2200.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67144848, side=1, lots=2, open="2026-10-14 04:45:08", entry=4166.69, close="2026-10-14 05:28:33", exit=4157.63, pnl=-1812.00, src="v1.17 (2-lot machine)"),
    dict(ticket=67182851, side=-1, lots=2, open="2026-10-14 08:31:12", entry=4149.33, close="2026-10-14 08:46:18", exit=4144.295, pnl=1007.00, src="v1.17 (2-lot machine)"),
]
SL_SHOWN = {67046250: 4152.46, 67082390: 4152.76, 67099697: 4154.20, 67111138: 4154.77, 67117659: 4157.62, 67138222: 4158.12, 67144848: 4157.65, 67182851: 4145.14}


def shape(o, h, l, c):
    rng = h - l
    if rng <= 0: return "flat"
    body = abs(c - o); up = h - max(o, c); lo = min(o, c) - l
    if body <= 0.60 * rng and max(up, lo) >= 0.45 * rng and min(up, lo) <= 0.20 * rng:
        return "PIN BAR (" + ("long lower wick" if lo > up else "long upper wick") + ")"
    if body > 0 and lo >= 2.5 * body and up <= 0.50 * rng: return "HAMMER"
    if body > 0 and up >= 2.5 * body and lo <= 0.50 * rng: return "SHOOTING STAR"
    if body >= 0.53 * rng: return ("GREEN" if c > o else "RED") + " MARUBOZU"
    return "none (no valid shape)"


def last_swing(df, before, side, pivot=3, look=100):
    """Saad's TP for shorts: the most recent swing low (pivot 3 each side) within 100 candles."""
    w = df[df.index < before].tail(look)
    vals = w.low.values if side < 0 else w.high.values
    for i in range(len(w) - 1 - pivot, pivot - 1, -1):
        seg = vals[i - pivot:i + pivot + 1]
        if (side < 0 and vals[i] == seg.min()) or (side > 0 and vals[i] == seg.max()):
            return float(vals[i]), w.index[i]
    return None, None


out = []
for tr in TRADES:
    t_open, t_close = pd.Timestamp(tr["open"]), pd.Timestamp(tr["close"])
    tf = m1 if tr["ticket"] == 67082390 else m15          # the v1.11 copy ran on an M1 chart
    step = pd.Timedelta(minutes=1 if tr["ticket"] == 67082390 else 15)
    setup_t = t_open.floor(step) - step
    if setup_t not in tf.index:
        out.append({**tr, "error": f"no candle {setup_t}"}); continue
    s = tf.loc[setup_t]
    e9, e50, atr, er = (s.get("ema9", np.nan), s.get("ema50", np.nan), s.get("atr14", np.nan), s.get("er16", np.nan))
    o, h, l, c = s.open, s.high, s.low, s.close
    touches9 = (not np.isnan(e9)) and l <= e9 <= h
    touches50 = (not np.isnan(e50)) and l <= e50 <= h
    trig = h + 0.20 if tr["side"] > 0 else l - 0.20
    sl_rule = l - 3.50 if tr["side"] > 0 else h + 3.50
    # context: the trend of the last 2-4 hours of M15
    ctx = m15[(m15.index <= setup_t)].tail(16)
    trend_move = float(ctx.close.iloc[-1] - ctx.close.iloc[0]) if len(ctx) else np.nan
    # path after entry (M1)
    path = m1[(m1.index >= t_open.floor("1min")) & (m1.index <= t_close.floor("1min"))]
    if tr["side"] > 0:
        mfe = float(path.high.max() - tr["entry"]); mae = float(tr["entry"] - path.low.min())
        t_mfe = path.high.idxmax(); t_mae = path.low.idxmin()
    else:
        mfe = float(tr["entry"] - path.low.min()); mae = float(path.high.max() - tr["entry"])
        t_mfe = path.low.idxmin(); t_mae = path.high.idxmax()
    # the EA's TP1
    tp1, tp1_note = None, ""
    if tr["side"] > 0:
        exit_ema = e50 if touches9 else e9
        if exit_ema - tr["entry"] >= 0.5:
            tp1 = exit_ema; tp1_note = "the exit EMA (%s) %.2f above entry" % ("50" if touches9 else "9", exit_ema - tr["entry"])
        else:
            tp1_note = "exit EMA %.2f is BELOW / too close to the entry -> no TP1, the 2xATR trail from candle 2 (path B)" % exit_ema
    else:
        sup, sup_t = last_swing(m15, setup_t + step, -1)
        if sup is not None and sup < tr["entry"] - 0.5:
            tp1 = sup; tp1_note = f"last support {sup:.2f} (swing low at {sup_t})"
    ctc = None
    if tp1 is not None:
        ctc = tr["entry"] + tr["side"] * 0.75 * abs(tp1 - tr["entry"])
    reached_ctc = bool(tp1 is not None and ((tr["side"] > 0 and path.high.max() >= ctc) or (tr["side"] < 0 and path.low.min() <= ctc)))
    # after the exit: did price later go our way? (what the trade missed)
    after = m1[(m1.index > t_close) & (m1.index <= t_close + pd.Timedelta(hours=3))]
    after_best = float((after.high.max() - tr["entry"]) if tr["side"] > 0 else (tr["entry"] - after.low.min())) if len(after) else None
    rec = {**tr, "setup_time": str(setup_t), "setup_ohlc": [o, h, l, c], "shape": shape(o, h, l, c), "ema9": round(e9, 2) if not np.isnan(e9) else None,
           "ema50": round(e50, 2) if not np.isnan(e50) else None, "atr14": round(atr, 2) if not np.isnan(atr) else None, "er16": round(er, 3) if not np.isnan(er) else None,
           "range": round(h - l, 2), "range_atr": round((h - l) / atr, 2) if atr and not np.isnan(atr) else None,
           "touches9": touches9, "touches50": touches50, "trigger": round(trig, 2), "sl_rule": round(sl_rule, 2), "sl_shown": SL_SHOWN[tr["ticket"]],
           "risk_usd": round(abs(tr["entry"] - sl_rule) * tr["lots"] * 100, 0), "tp1": round(tp1, 2) if tp1 else None, "tp1_note": tp1_note,
           "ctc_level": round(ctc, 2) if ctc else None, "reached_ctc": reached_ctc, "mfe": round(mfe, 2), "t_mfe": str(t_mfe), "mae": round(mae, 2), "t_mae": str(t_mae),
           "trend16_move": round(trend_move, 2), "ema_trend": ("UP (EMA9 > EMA50)" if e9 > e50 else "DOWN (EMA9 < EMA50)") if not np.isnan(e9) else None,
           "after3h_best": round(after_best, 2) if after_best is not None else None, "minutes": round((t_close - t_open).total_seconds() / 60, 1)}
    out.append(rec)
    print(f"\n#{tr['ticket']} {'BUY' if tr['side'] > 0 else 'SELL'} {tr['lots']} @ {tr['entry']} -> {tr['exit']} = {tr['pnl']:+.2f} ({tr['src']})")
    for k in ("setup_time", "setup_ohlc", "shape", "ema9", "ema50", "atr14", "range", "range_atr", "er16", "touches9", "touches50", "trigger", "sl_rule", "sl_shown",
              "risk_usd", "tp1", "tp1_note", "ctc_level", "reached_ctc", "mfe", "t_mfe", "mae", "t_mae", "trend16_move", "ema_trend", "after3h_best", "minutes"):
        print(f"   {k:14} {rec[k]}")
json.dump(out, open(T / "pxbt_trade_forensics.json", "w"), indent=1, default=str)
