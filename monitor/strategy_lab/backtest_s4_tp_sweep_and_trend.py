"""backtest_s4_tp_sweep_and_trend.py — TWO PENDING TESTS for S4Trader:

TEST 1 — SMALL-TP / HIGH-WR:
  Sweep TP from $0.5 to $12 (with SL = TP, 2*TP, and fixed $6), ER>=0.15, trend ON.
  Does WR climb toward ~95% at tiny TPs? And is total P&L positive (or does spread eat it)?
  This tests Zee's hypothesis: "small small wins on higher lots = high profit + high winrate."

TEST 2 — RELAX TREND FILTER:
  Run with trend OFF + various ER thresholds to push frequency toward 100+ trades/day.
  Does the ER regime filter alone produce a profitable, higher-frequency signal?
  This tests: "can relaxing HH/HL give us 100+ trades/day like I do manually?"

Run:  py backtest_s4_tp_sweep_and_trend.py
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
MOM_BODY_FRAC = 0.55


def trend_dir(win):
    h = len(win) // 2
    older, recent = win[:h], win[h:]
    if not older or not recent:
        return 0
    hh = max(b["high"] for b in recent) > max(b["high"] for b in older)
    hl = min(b["low"] for b in recent) > min(b["low"] for b in older)
    lh = max(b["high"] for b in recent) < max(b["high"] for b in older)
    ll = min(b["low"] for b in recent) < min(b["low"] for b in older)
    if hh and hl: return 1
    if lh and ll: return -1
    return 0


def efficiency_ratio(seg):
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0


def detect(m1, require_trend=True, er_min=0.0):
    sigs = []
    start = TREND_LB + RETRACE_LB + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < MOM_BODY_FRAC: continue
        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        if er_min > 0 and efficiency_ratio(m1[i - TREND_LB:i]) < er_min:
            continue
        td = trend_dir(m1[i - TREND_LB:i])
        if bo["close"] > bo["open"]:
            reds = [b for b in win if b["close"] < b["open"]]
            if reds and (not require_trend or td == 1):
                uhv = max(reds, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                    sigs.append({"side": +1, "fire_time": bo["time"] + timedelta(minutes=1)})
                    continue
        if bo["close"] < bo["open"]:
            greens = [b for b in win if b["close"] > b["open"]]
            if greens and (not require_trend or td == -1):
                uhv = max(greens, key=lambda b: b["vol"])
                if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                    sigs.append({"side": -1, "fire_time": bo["time"] + timedelta(minutes=1)})
    return sigs


def replay(ticks, sigs, tp_pts, sl_pts, max_conc=3):
    """Fixed TP/SL exit. BUY+SELL."""
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
                    u["pnl"] = -sl_pts * ppp; done.append(u); units.remove(u); continue
                if bid >= u["e"] + tp_pts:
                    u["pnl"] = tp_pts * ppp; done.append(u); units.remove(u); continue
            else:
                if ask >= u["e"] + sl_pts:
                    u["pnl"] = -sl_pts * ppp; done.append(u); units.remove(u); continue
                if ask <= u["e"] - tp_pts:
                    u["pnl"] = tp_pts * ppp; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                units.append({"side": pend["side"],
                              "e": ask if pend["side"] > 0 else bid,
                              "open_t": t})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            done.append(u)
    return done


def stat(trades, ndays):
    n = len(trades)
    if not n: return "n=0"
    w = [x["pnl"] for x in trades if x["pnl"] > 0]
    l = [x["pnl"] for x in trades if x["pnl"] < 0]
    tot = sum(x["pnl"] for x in trades)
    wr = len(w) / (len(w) + len(l)) if (w or l) else 0
    return (f"n={n:>4} {n/ndays:>5.1f}/d  WR={wr:>5.1%}  "
            f"W=${(sum(w)/len(w) if w else 0):>5.1f}  L=${(-sum(l)/len(l) if l else 0):>5.1f}  "
            f"TOT=${tot:>+9.1f}")


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
    nd = len(days)
    mid = nd // 2
    print(f"S4 TWO-TEST SUITE — {nd} broker-tick days, {LOTS} lots, BUY+SELL\n")

    # ═══════════════════════════════════════════════════════════════════
    # TEST 1: SMALL-TP / HIGH-WR SWEEP (trend ON, ER>=0.15 = deployed config)
    # ═══════════════════════════════════════════════════════════════════
    sig_deployed = {d: detect(cache[d]["m1"], require_trend=True, er_min=0.15) for d in days}
    nsig = sum(len(sig_deployed[d]) for d in days)
    print(f"{'='*80}")
    print(f"TEST 1: SMALL-TP SWEEP  (trend ON + ER>=0.15 = deployed S4 config)")
    print(f"  Signals: {nsig} over {nd} days = {nsig/nd:.1f}/day")
    print(f"  Question: does tiny TP push WR toward 95%? Is it net positive?")
    print(f"{'='*80}\n")

    # Sweep: TP from $0.5 to $12, SL fixed at $6 (deployed), then also SL=TP (1:1)
    print(f"--- SL fixed at $6 (deployed) ---")
    print(f"  {'TP':>4}  {'ALL':<50} {'OOS (test half)'}")
    for tp in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig_deployed[d], tp_pts=tp, sl_pts=6.0)
            allt += tr
            if k >= mid: testt += tr
        print(f"  ${tp:<4.1f} {stat(allt, nd):<50} {stat(testt, nd-mid)}")
    print()

    print(f"--- SL = TP (1:1 risk/reward) ---")
    print(f"  {'TP':>4}  {'ALL':<50} {'OOS (test half)'}")
    for tp in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0):
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig_deployed[d], tp_pts=tp, sl_pts=tp)
            allt += tr
            if k >= mid: testt += tr
        print(f"  ${tp:<4.1f} {stat(allt, nd):<50} {stat(testt, nd-mid)}")
    print()

    print(f"--- SL = 2*TP (Zee's 'small win, tiny loss' idea) ---")
    print(f"  {'TP':>4}  {'ALL':<50} {'OOS (test half)'}")
    for tp in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        sl = min(tp * 2, 12)
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay(cache[d]["ticks"], sig_deployed[d], tp_pts=tp, sl_pts=sl)
            allt += tr
            if k >= mid: testt += tr
        print(f"  ${tp:<4.1f} {stat(allt, nd):<50} {stat(testt, nd-mid)}")

    # ═══════════════════════════════════════════════════════════════════
    # TEST 2: RELAX TREND FILTER (push toward 100+ trades/day)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*80}")
    print(f"TEST 2: RELAX HH/HL TREND FILTER  (can we get 100+ trades/day?)")
    print(f"  Sweeping: trend ON/OFF × ER thresholds × best TP/SL combos")
    print(f"{'='*80}\n")

    combos = [
        ("trend ON,  ER>=0.15 (deployed)", True, 0.15),
        ("trend ON,  ER OFF",              True, 0.0),
        ("trend OFF, ER>=0.15",            False, 0.15),
        ("trend OFF, ER>=0.20",            False, 0.20),
        ("trend OFF, ER>=0.25",            False, 0.25),
        ("trend OFF, ER>=0.30",            False, 0.30),
        ("trend OFF, ER OFF (max freq)",   False, 0.0),
    ]

    tp_sl_combos = [
        ("TP12/SL6 (2:1)", 12, 6),
        ("TP8/SL4 (2:1)",   8, 4),
        ("TP6/SL3 (2:1)",   6, 3),
        ("TP3/SL3 (1:1)",   3, 3),
        ("TP2/SL3",         2, 3),
        ("TP1/SL2",         1, 2),
    ]

    for label, req_trend, er_min in combos:
        sig = {d: detect(cache[d]["m1"], require_trend=req_trend, er_min=er_min) for d in days}
        nsig = sum(len(sig[d]) for d in days)
        nb = sum(1 for d in days for s in sig[d] if s["side"] > 0)
        ns = sum(1 for d in days for s in sig[d] if s["side"] < 0)
        print(f"--- {label} --- {nb} buy + {ns} sell = {nsig/nd:.1f}/day")
        print(f"  {'exit':<20} {'ALL':<50} {'OOS (test half)'}")
        for tp_lbl, tp, sl in tp_sl_combos:
            allt, testt = [], []
            for k, d in enumerate(days):
                tr = replay(cache[d]["ticks"], sig[d], tp_pts=tp, sl_pts=sl)
                allt += tr
                if k >= mid: testt += tr
            print(f"  {tp_lbl:<20} {stat(allt, nd):<50} {stat(testt, nd-mid)}")
        print()

    # ── Per-day breakdown for the most promising high-freq config ──
    print(f"--- PER-DAY: trend OFF + ER>=0.15, TP12/SL6 vs TP2/SL3 ---")
    sig_relaxed = {d: detect(cache[d]["m1"], require_trend=False, er_min=0.15) for d in days}
    for tp_lbl, tp, sl in [("TP12/SL6", 12, 6), ("TP2/SL3", 2, 3)]:
        print(f"\n  {tp_lbl}:")
        pos = 0
        for d in days:
            tr = replay(cache[d]["ticks"], sig_relaxed[d], tp_pts=tp, sl_pts=sl)
            tot = sum(x["pnl"] for x in tr)
            if tot > 0: pos += 1
            print(f"    {d}: {len(tr):>3} tr  ${tot:>+8.1f}")
        print(f"    => {pos}/{nd} green days")


if __name__ == "__main__":
    main()
