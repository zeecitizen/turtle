"""backtest_s4b_95wr.py — Hunt for 95% WR on S4b (TP5/SL6).

Current S4b: 65% WR OOS at TP5/SL6. To reach 95% we need to SELECT only
the highest-quality entries. Possible filters to test:

1. ER threshold sweep (0.15 → 0.50) — stronger trend = more directional
2. UHV volume dominance — UHV vol must be N× average (stronger institutional)
3. Breakout candle body ratio — require very clean momentum (body/range ≥ 0.7, 0.8)
4. Breakout volume ratio — how much lower than UHV vol the breakout must be
5. Time-of-day — London, NY, overlap only
6. Trend magnitude — not just HH/HL structure but how FAR the structure moved
7. Retracement depth — how deep the pullback was before the UHV
8. Multi-filter combos — stack the best individual filters

Run:  py backtest_s4b_95wr.py
"""
import sys, glob
from datetime import timedelta, datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
TP = 5.0
SL = 6.0


def trend_dir(win):
    h = len(win) // 2
    older, recent = win[:h], win[h:]
    if not older or not recent: return 0
    hh = max(b["high"] for b in recent) > max(b["high"] for b in older)
    hl = min(b["low"] for b in recent) > min(b["low"] for b in older)
    lh = max(b["high"] for b in recent) < max(b["high"] for b in older)
    ll = min(b["low"] for b in recent) < min(b["low"] for b in older)
    if hh and hl: return 1
    if lh and ll: return -1
    return 0


def trend_magnitude(win):
    """How much the structure moved (recent_mid - older_mid) in price units."""
    h = len(win) // 2
    older, recent = win[:h], win[h:]
    if not older or not recent: return 0.0
    r_mid = (max(b["high"] for b in recent) + min(b["low"] for b in recent)) / 2
    o_mid = (max(b["high"] for b in older) + min(b["low"] for b in older)) / 2
    return r_mid - o_mid  # positive = uptrend, negative = downtrend


def efficiency_ratio(seg):
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0


def detect_rich(m1, er_min=0.15, mom_body_frac=0.55, uhv_vol_mult=1.0,
                bo_vol_ratio_max=1.0, trend_mag_min=0.0, hour_filter=None):
    """Like detect() but returns richer signal dicts with quality metrics,
    and accepts additional filter parameters."""
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        body_frac = body / rng
        if body_frac < mom_body_frac: continue

        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue

        tw = m1[i - TREND_LB:i]
        er = efficiency_ratio(tw)
        if er_min > 0 and er < er_min: continue

        td = trend_dir(tw)
        if td == 0: continue  # always require trend for S4b

        tmag = trend_magnitude(tw)

        # trend magnitude filter
        if trend_mag_min > 0 and abs(tmag) < trend_mag_min: continue

        # time-of-day filter
        if hour_filter is not None:
            h = bo["time"].hour
            if h not in hour_filter: continue

        # avg volume in window
        avg_vol = sum(b["vol"] for b in win) / len(win) if win else 1

        # BUY
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds:
                uhv = max(reds, key=lambda b: b["vol"])
                # UHV volume dominance: must be uhv_vol_mult × average
                if uhv["vol"] < avg_vol * uhv_vol_mult: continue
                # Breakout vol ratio: bo_vol / uhv_vol must be < threshold
                vol_ratio = bo["vol"] / uhv["vol"] if uhv["vol"] > 0 else 1.0
                if vol_ratio > bo_vol_ratio_max: continue
                if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                    sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1),
                                 "er": er, "body_frac": body_frac, "vol_ratio": vol_ratio,
                                 "tmag": tmag, "uhv_dom": uhv["vol"] / avg_vol if avg_vol > 0 else 0})
                    continue
        # SELL
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens:
                uhv = max(greens, key=lambda b: b["vol"])
                if uhv["vol"] < avg_vol * uhv_vol_mult: continue
                vol_ratio = bo["vol"] / uhv["vol"] if uhv["vol"] > 0 else 1.0
                if vol_ratio > bo_vol_ratio_max: continue
                if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                    sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1),
                                 "er": er, "body_frac": body_frac, "vol_ratio": vol_ratio,
                                 "tmag": tmag, "uhv_dom": uhv["vol"] / avg_vol if avg_vol > 0 else 0})
    return sigs


def replay(ticks, sigs, tp_pts=TP, sl_pts=SL, max_conc=3):
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            s = u["side"]
            if s > 0:
                if bid <= u["e"] - sl_pts:
                    u["pnl"] = -sl_pts * ppp; u["result"] = "L"; done.append(u); units.remove(u); continue
                if bid >= u["e"] + tp_pts:
                    u["pnl"] = tp_pts * ppp; u["result"] = "W"; done.append(u); units.remove(u); continue
            else:
                if ask >= u["e"] + sl_pts:
                    u["pnl"] = -sl_pts * ppp; u["result"] = "L"; done.append(u); units.remove(u); continue
                if ask <= u["e"] - tp_pts:
                    u["pnl"] = tp_pts * ppp; u["result"] = "W"; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                units.append({"side": pend["side"], "e": ask if pend["side"] > 0 else bid,
                              "open_t": t, "sig": pend})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            p = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            u["pnl"] = p; u["result"] = "W" if p > 0 else "L"
            done.append(u)
    return done


def stat(trades, nd):
    n = len(trades)
    if not n: return "n=0"
    w = sum(1 for t in trades if t.get("result") == "W")
    tot = sum(t["pnl"] for t in trades)
    wr = w / n if n > 0 else 0
    return f"n={n:>4} {n/nd:>5.1f}/d  WR={wr:>5.1%}  TOT=${tot:>+9.1f}"


def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 200: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[d] = {"m1": days_b[d], "ticks": ticks}
    days = sorted(cache)
    nd = len(days); mid = nd // 2

    print(f"S4b 95% WR HUNT — {nd} broker-tick days, TP${TP}/SL${SL}, 0.10 lots")
    print(f"{'='*90}\n")

    # ── BASELINE ──
    print("=== BASELINE (deployed S4b: ER>=0.15, body>=0.55, trend ON) ===")
    sig = {d: detect_rich(cache[d]["m1"]) for d in days}
    allt, testt = [], []
    for k, d in enumerate(days):
        tr = replay(cache[d]["ticks"], sig[d])
        allt += tr
        if k >= mid: testt += tr
    print(f"  ALL:  {stat(allt, nd)}")
    print(f"  OOS:  {stat(testt, nd-mid)}\n")

    # ── FILTER 1: Efficiency Ratio sweep ──
    print("=== FILTER 1: Efficiency Ratio threshold ===")
    for er in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50):
        sig = {d: detect_rich(cache[d]["m1"], er_min=er) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  ER>={er:.2f}  ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── FILTER 2: Breakout candle body ratio ──
    print("=== FILTER 2: Breakout body/range ratio ===")
    for bf in (0.55, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        sig = {d: detect_rich(cache[d]["m1"], mom_body_frac=bf) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  body>={bf:.2f}  ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── FILTER 3: UHV volume dominance ──
    print("=== FILTER 3: UHV must be Nx average volume ===")
    for mult in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        sig = {d: detect_rich(cache[d]["m1"], uhv_vol_mult=mult) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  UHV>={mult:.1f}x  ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── FILTER 4: Breakout volume ratio (lower = more conviction) ──
    print("=== FILTER 4: Breakout vol / UHV vol ratio (lower = more empty breakout) ===")
    for vr in (1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2):
        sig = {d: detect_rich(cache[d]["m1"], bo_vol_ratio_max=vr) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  bo/uhv<={vr:.1f}  ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── FILTER 5: Trend magnitude (structure must have moved at least N pts) ──
    print("=== FILTER 5: Trend magnitude (structure moved >= N pts) ===")
    for tm in (0, 1, 2, 3, 4, 5, 7, 10):
        sig = {d: detect_rich(cache[d]["m1"], trend_mag_min=tm) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  mag>={tm}  ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── FILTER 6: Time-of-day (broker time = GMT+3) ──
    print("=== FILTER 6: Time-of-day (broker GMT+3) ===")
    london = set(range(10, 17))       # London 07:00-14:00 UTC = 10:00-17:00 GMT+3
    ny     = set(range(15, 22))       # NY 12:00-19:00 UTC = 15:00-22:00 GMT+3
    overlap = london & ny             # 15:00-17:00 GMT+3
    asian  = set(range(0, 10))        # Asian 21:00-07:00 UTC = 00:00-10:00 GMT+3
    for lbl, hf in [("All hours", None), ("London", london), ("NY", ny),
                     ("Overlap", overlap), ("Asian", asian),
                     ("London+NY", london | ny)]:
        sig = {d: detect_rich(cache[d]["m1"], hour_filter=hf) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        print(f"  {lbl:<12} ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}")
    print()

    # ── STACKED COMBOS: combine the best individual filters ──
    print("=== STACKED COMBOS (best individual filters combined) ===")
    combos = [
        ("ER>=0.25 + body>=0.70",               dict(er_min=0.25, mom_body_frac=0.70)),
        ("ER>=0.30 + body>=0.70",               dict(er_min=0.30, mom_body_frac=0.70)),
        ("ER>=0.25 + UHV>=2x",                  dict(er_min=0.25, uhv_vol_mult=2.0)),
        ("ER>=0.30 + UHV>=2x",                  dict(er_min=0.30, uhv_vol_mult=2.0)),
        ("ER>=0.25 + bo/uhv<=0.5",              dict(er_min=0.25, bo_vol_ratio_max=0.5)),
        ("ER>=0.30 + bo/uhv<=0.5",              dict(er_min=0.30, bo_vol_ratio_max=0.5)),
        ("ER>=0.25 + body>=0.70 + UHV>=2x",     dict(er_min=0.25, mom_body_frac=0.70, uhv_vol_mult=2.0)),
        ("ER>=0.30 + body>=0.70 + UHV>=2x",     dict(er_min=0.30, mom_body_frac=0.70, uhv_vol_mult=2.0)),
        ("ER>=0.35 + body>=0.70 + UHV>=2x",     dict(er_min=0.35, mom_body_frac=0.70, uhv_vol_mult=2.0)),
        ("ER>=0.25 + body>=0.75 + bo/uhv<=0.5", dict(er_min=0.25, mom_body_frac=0.75, bo_vol_ratio_max=0.5)),
        ("ER>=0.30 + body>=0.75 + bo/uhv<=0.5", dict(er_min=0.30, mom_body_frac=0.75, bo_vol_ratio_max=0.5)),
        ("ER>=0.25 + body>=0.70 + UHV>=2x + mag>=3", dict(er_min=0.25, mom_body_frac=0.70, uhv_vol_mult=2.0, trend_mag_min=3)),
        ("ER>=0.30 + body>=0.70 + UHV>=2x + mag>=3", dict(er_min=0.30, mom_body_frac=0.70, uhv_vol_mult=2.0, trend_mag_min=3)),
        ("ER>=0.25 + body>=0.80 + UHV>=3x",     dict(er_min=0.25, mom_body_frac=0.80, uhv_vol_mult=3.0)),
        ("ER>=0.30 + body>=0.80 + UHV>=3x",     dict(er_min=0.30, mom_body_frac=0.80, uhv_vol_mult=3.0)),
        ("ER>=0.35 + body>=0.80 + UHV>=3x",     dict(er_min=0.35, mom_body_frac=0.80, uhv_vol_mult=3.0)),
        # kitchen sink
        ("ER>=0.30 + body>=0.75 + UHV>=2x + bo/uhv<=0.5 + mag>=3",
         dict(er_min=0.30, mom_body_frac=0.75, uhv_vol_mult=2.0, bo_vol_ratio_max=0.5, trend_mag_min=3)),
        ("ER>=0.35 + body>=0.75 + UHV>=2x + bo/uhv<=0.5 + mag>=3",
         dict(er_min=0.35, mom_body_frac=0.75, uhv_vol_mult=2.0, bo_vol_ratio_max=0.5, trend_mag_min=3)),
        # London+NY time with quality
        ("ER>=0.25 + body>=0.70 + UHV>=2x + London+NY",
         dict(er_min=0.25, mom_body_frac=0.70, uhv_vol_mult=2.0, hour_filter=london|ny)),
        ("ER>=0.30 + body>=0.70 + UHV>=2x + London+NY",
         dict(er_min=0.30, mom_body_frac=0.70, uhv_vol_mult=2.0, hour_filter=london|ny)),
        ("ER>=0.30 + body>=0.75 + UHV>=2x + bo/uhv<=0.5 + London+NY",
         dict(er_min=0.30, mom_body_frac=0.75, uhv_vol_mult=2.0, bo_vol_ratio_max=0.5, hour_filter=london|ny)),
    ]

    best_wr_90 = None  # best combo with WR >= 90% and n >= 10
    for lbl, kw in combos:
        sig = {d: detect_rich(cache[d]["m1"], **kw) for d in days}
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig[d])
            allt += tr
            if k >= mid: testt += tr
        n_all = len(allt)
        w_all = sum(1 for t in allt if t.get("result") == "W")
        wr_all = w_all / n_all if n_all > 0 else 0
        tot = sum(t["pnl"] for t in allt)
        n_oos = len(testt)
        w_oos = sum(1 for t in testt if t.get("result") == "W")
        wr_oos = w_oos / n_oos if n_oos > 0 else 0
        flag = ""
        if wr_all >= 0.90 and n_all >= 10: flag = " ★★★ 90%+ WR"
        elif wr_all >= 0.80 and n_all >= 10: flag = " ★★ 80%+"
        elif wr_all >= 0.70 and n_all >= 15: flag = " ★ 70%+"
        print(f"  {lbl:<55} ALL: {stat(allt, nd):<45} OOS: {stat(testt, nd-mid)}{flag}")
        if wr_all >= 0.90 and n_all >= 10 and (best_wr_90 is None or wr_all > best_wr_90[0]):
            best_wr_90 = (wr_all, lbl, kw, allt, testt)

    if best_wr_90:
        print(f"\n  ★ BEST >=90% WR combo: {best_wr_90[1]}")
        print(f"    ALL: {stat(best_wr_90[3], nd)}")
        print(f"    OOS: {stat(best_wr_90[4], nd-mid)}")
        # per-day
        wr_all, lbl, kw, _, _ = best_wr_90
        sig = {d: detect_rich(cache[d]["m1"], **kw) for d in days}
        print(f"\n    Per-day breakdown:")
        for d in days:
            tr = replay(cache[d]["ticks"], sig[d])
            n = len(tr); w = sum(1 for t in tr if t.get("result") == "W")
            tot = sum(t["pnl"] for t in tr)
            print(f"      {d}: {n:>3} tr  {w}W/{n-w}L  ${tot:>+8.1f}")
    print()

    # ── POST-TRADE QUALITY: analyze which signal metrics predict wins ──
    print("=== POST-TRADE ANALYSIS: which signal features predict wins? ===")
    sig = {d: detect_rich(cache[d]["m1"]) for d in days}
    all_trades = []
    for d in days:
        all_trades += replay(cache[d]["ticks"], sig[d])

    # Bucket trades by signal quality metrics
    for metric, label, buckets in [
        ("er", "ER at entry", [(0, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 0.60), (0.60, 1.0)]),
        ("body_frac", "Body/Range", [(0.55, 0.65), (0.65, 0.75), (0.75, 0.85), (0.85, 1.0)]),
        ("vol_ratio", "BO/UHV vol", [(0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0)]),
        ("uhv_dom", "UHV/avg vol", [(0, 1.5), (1.5, 2.5), (2.5, 4.0), (4.0, 100)]),
    ]:
        print(f"\n  {label}:")
        for lo, hi in buckets:
            bucket = [t for t in all_trades if "sig" in t and lo <= t["sig"].get(metric, 0) < hi]
            if not bucket: continue
            w = sum(1 for t in bucket if t.get("result") == "W")
            wr = w / len(bucket) if bucket else 0
            tot = sum(t["pnl"] for t in bucket)
            print(f"    [{lo:.2f}–{hi:.2f}): n={len(bucket):>3}  WR={wr:.1%}  TOT=${tot:>+8.1f}")


if __name__ == "__main__":
    main()
