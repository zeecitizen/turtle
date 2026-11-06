"""final_rules.py - batch 7: the rules as STANDALONE source strings (each defines def rule(t, A) and imports what it needs inside),
exec'd in a fresh namespace and scored with api.report, so the pasted code reproduces the pasted numbers. Writes final_scores.json."""
import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402

NY = (
    "\n"
    "    import datetime as dt\n"
    "    ts = t[\"t_in\"]\n"
    "    y = dt.datetime.fromtimestamp(ts, dt.timezone.utc).year\n"
    "    m3 = dt.datetime(y, 3, 1, tzinfo=dt.timezone.utc); dst0 = m3 + dt.timedelta(days=(6 - m3.weekday()) % 7 + 7)\n"
    "    n11 = dt.datetime(y, 11, 1, tzinfo=dt.timezone.utc); dst1 = n11 + dt.timedelta(days=(6 - n11.weekday()) % 7)\n"
    "    off = -4 if dst0.timestamp() + 7 * 3600 <= ts < dst1.timestamp() + 6 * 3600 else -5\n"
    "    d = dt.datetime.fromtimestamp(ts + off * 3600, dt.timezone.utc)\n"
    "    m, wd = d.hour * 60 + d.minute + d.second / 60.0, d.weekday()      # New York minute of day, weekday 0=Mon .. 4=Fri .. 6=Sun\n"
)
EMA = (
    "\n"
    "    k = t[\"k\"]; n = 240; a = 2.0 / (n + 1); j0 = max(0, k - 4 * n); e = float(A.c[j0])\n"
    "    for i in range(j0 + 1, k + 1):\n"
    "        e = a * float(A.c[i]) + (1 - a) * e                           # causal EMA(240) of closes up to k\n"
)
RULES = {
    # ------------------------------------------------ selective
    "B7_ROLLOVER_HOUR": ("def rule(t, A):\n    # skip New York 16:45-17:45, any day: 15 min before the 17:00 rollover + the first trades after the daily break" + NY +
                         "    return 16 * 60 + 45 <= m < 17 * 60 + 45\n"),
    "B7_FRIDAY_LAST_HOUR": ("def rule(t, A):\n    # skip Friday from New York 16:00: the last hour before the weekend flatten (16:58 NY)" + NY +
                            "    return wd == 4 and m >= 16 * 60\n"),
    "B7_SLIP_1P2": ("def rule(t, A):\n    # skip if the breakout tick is already 1.2+ pips beyond the UHV level (spike / gap / wide-spread tick)\n"
                    "    return t[\"side\"] * (t[\"fill\"] - t[\"level\"]) >= 1.2 * 1e-4\n"),
    "B7_THIN_VM30": ("def rule(t, A):\n    # skip if the last 30 closed 1-min candles averaged fewer than 20 ticks (dead market)\n"
                     "    k = t[\"k\"]\n    return A.v[k - 29:k + 1].mean() < 20\n"),
    "B7_TIME_UNION": ("def rule(t, A):\n    # the two time rules together: New York 16:45-17:45 any day, or Friday from New York 16:00" + NY +
                      "    return (16 * 60 + 45 <= m < 17 * 60 + 45) or (wd == 4 and m >= 16 * 60)\n"),
    "B7_ALL4_UNION": ("def rule(t, A):\n    # rollover hour | Friday last hour | breakout tick 1.2+ pips beyond the level | 30-min average < 20 ticks" + NY +
                      "    k = t[\"k\"]\n"
                      "    return ((16 * 60 + 45 <= m < 17 * 60 + 45) or (wd == 4 and m >= 16 * 60)\n"
                      "            or t[\"side\"] * (t[\"fill\"] - t[\"level\"]) >= 1.2 * 1e-4 or A.v[k - 29:k + 1].mean() < 20)\n"),
    # ------------------------------------------------ variants (same ideas, other thresholds)
    "B7v_ROLLOVER_1640_1730": ("def rule(t, A):" + NY + "    return 16 * 60 + 40 <= m < 17 * 60 + 30\n"),
    "B7v_FRIDAY_1615": ("def rule(t, A):" + NY + "    return wd == 4 and m >= 16 * 60 + 15\n"),
    "B7v_REOPEN_ONLY": ("def rule(t, A):\n    # Mon-Thu/Sun, New York 17:00-17:45 only (first trades after the daily break)" + NY +
                        "    return wd != 4 and 17 * 60 <= m < 17 * 60 + 45\n"),
    "B7v_SLIP_1P0": ("def rule(t, A):\n    return t[\"side\"] * (t[\"fill\"] - t[\"level\"]) >= 1.0 * 1e-4\n"),
    "B7v_SLIP_2P0": ("def rule(t, A):\n    return t[\"side\"] * (t[\"fill\"] - t[\"level\"]) >= 2.0 * 1e-4\n"),
    "B7v_THIN_VMIN10": ("def rule(t, A):\n    # a candle of <= 6 ticks among the last 10\n    k = t[\"k\"]\n    return A.v[k - 9:k + 1].min() <= 6\n"),
    # ------------------------------------------------ structural ideas from the charts (failed)
    "B7x_HTF_AGAINST": ("def rule(t, A):\n    # close > 6 pips on the wrong side of EMA(240)" + EMA +
                        "    return t[\"side\"] * (A.c[k] - e) < -6 * 1e-4\n"),
    "B7x_COUNTER_HTF_BOUNCE": ("def rule(t, A):\n    # 2+ humps of the trade colour but > 5 pips on the wrong side of EMA(240)" + EMA +
                               "    return t[\"side\"] * t[\"camStk\"] >= 2 and t[\"side\"] * (A.c[k] - e) < -5 * 1e-4\n"),
    "B7x_EXHAUSTED_RUN": ("def rule(t, A):\n    # the last 30 min already ran 8+ pips in the trade direction\n    k = t[\"k\"]\n"
                          "    return t[\"side\"] * (A.c[k] - A.c[k - 30]) > 8 * 1e-4\n"),
    "B7x_CLIMAX_CHASE": ("def rule(t, A):\n    # a 2x-volume candle in the last 10 and 8+ pips run in 30 min\n    k = t[\"k\"]\n"
                         "    return A.v[k - 9:k + 1].max() >= 2 * A.v[k - 59:k + 1].mean() and t[\"side\"] * (A.c[k] - A.c[k - 30]) > 8 * 1e-4\n"),
    "B7x_RANGE_EDGE60": ("def rule(t, A):\n    # fill in the outer 5% of the 60-min range in the trade direction\n    k = t[\"k\"]\n"
                         "    hi, lo = A.h[k - 59:k + 1].max(), A.l[k - 59:k + 1].min(); r = max(hi - lo, 1e-9)\n"
                         "    pos = (t[\"fill\"] - lo) / r if t[\"side\"] > 0 else (hi - t[\"fill\"]) / r\n    return pos > 0.95\n"),
    "B7x_FLAT_BOX_EDGE": ("def rule(t, A):\n    # 2-hour box < 10 pips and the fill in its outer 15% in the trade direction\n    k = t[\"k\"]\n"
                          "    hi, lo = A.h[k - 119:k + 1].max(), A.l[k - 119:k + 1].min(); r = hi - lo\n"
                          "    if r <= 0 or r >= 10 * 1e-4:\n        return False\n"
                          "    pos = (t[\"fill\"] - lo) / r if t[\"side\"] > 0 else (hi - t[\"fill\"]) / r\n    return pos > 0.85\n"),
    "B7x_OLD_TREND": ("def rule(t, A):\n    # 4+ humps of the trade colour in a row\n    return t[\"side\"] * t[\"camStk\"] >= 4\n"),
    "B7x_OLD_UHV": ("def rule(t, A):\n    # the UHV candle is 10+ minutes old at the breakout\n    return t[\"kb\"] - t[\"ku\"] >= 10\n"),
    "B7x_RETESTED_LEVEL": ("def rule(t, A):\n    # price traded at/through the fill 3+ times in the last 30 min (excl. last 2 candles)\n    k, f = t[\"k\"], t[\"fill\"]\n"
                           "    n = int((A.h[k - 30:k - 1] >= f).sum()) if t[\"side\"] > 0 else int((A.l[k - 30:k - 1] <= f).sum())\n    return n >= 3\n"),
    "B7x_NEWS_MINUTE": ("def rule(t, A):\n    # first 2 minutes of the 08:30 / 10:00 New York data releases" + NY +
                        "    return wd < 5 and ((8 * 60 + 30 <= m < 8 * 60 + 32) or (10 * 60 <= m < 10 * 60 + 2))\n"),
    "B7x_POST_SPIKE": ("def rule(t, A):\n    # a candle of 6+ ATR range in the last 60 min\n    k = t[\"k\"]\n"
                       "    return (A.h[k - 59:k + 1] - A.l[k - 59:k + 1]).max() >= 6 * A.atr[k]\n"),
    "B7x_LOUD_BREAKOUT": ("def rule(t, A):\n    # breakout minute ticks so far >= 0.9 x UHV ticks\n    return t[\"brk_ticks_so_far\"] >= 0.9 * t[\"uhv_v\"]\n"),
    "B7x_OPPOSITE_CANDLE": ("def rule(t, A):\n    # last closed candle body >= 1 ATR against the trade\n    k = t[\"k\"]\n"
                            "    return t[\"side\"] * (A.c[k] - A.o[k]) <= -1.0 * A.atr[k]\n"),
    "B7x_HH_AGAINST": ("def rule(t, A):\n    # retracement extreme beyond the last known hump (higher high for a sell / lower low for a buy)\n    k = t[\"k\"]\n"
                       "    H = A.humps[A.humps[:, 7] <= k]\n    if not len(H):\n        return False\n"
                       "    b0, v0, bh, vh, b1, v1, tr, kn = H[-1]\n    return (t[\"extreme\"] > vh) if t[\"side\"] < 0 else (t[\"extreme\"] < v0)\n"),
}


def load(code):
    ns = {}
    exec(code, {"np": __import__("numpy"), "math": __import__("math")}, ns)
    return ns["rule"]


if __name__ == "__main__":
    out = {}
    for rid, code in RULES.items():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = api.report(load(code), rid)
        line = buf.getvalue().strip()
        print(line)
        out[rid] = {"code": code, "line": line, "score": r}
    json.dump(out, open(os.path.join(HERE, "final_scores.json"), "w", encoding="utf-8"), indent=1)
