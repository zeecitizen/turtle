"""backtest_pdf_recommendations.py — Test ALL ideas from "Optimizing S4b" PDF.

Tests:
  1. Higher ER threshold (0.30, 0.40)
  2. Multi-timeframe alignment (M5/M15 trend must agree with M1)
  3. VSA volume logic: flip to high-volume breakouts
  4. "No Supply" test bar between UHV and breakout
  5. ATR-based dynamic exits (replace fixed TP/SL)
  6. Max spread filter
  7. S/R proximity filter ("clear air")

Run: python backtest_pdf_recommendations.py
"""
import sys, glob, math
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import group_bars_by_day

CONTRACT = 100.0
LOTS = 0.10
TREND_LB = 30
RETRACE_LB = 12
UHV_RANGE_MIN = 1.0  # v1.01 filter


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def trend_dir(bars, lb=None):
    if lb is None: lb = len(bars)
    if len(bars) < lb: return 0
    seg = bars[-lb:]
    h = lb // 2
    recent = seg[h:]
    older = seg[:h]
    if not older or not recent: return 0
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0


def efficiency_ratio(bars, lb=TREND_LB):
    seg = bars[-lb:]
    if len(seg) < 2: return 0.0
    net = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0


def atr(bars, period=7):
    """Average True Range over the last `period` bars."""
    if len(bars) < period + 1: return 0.0
    trs = []
    for i in range(-period, 0):
        h = bars[i]["high"]
        l = bars[i]["low"]
        pc = bars[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def build_htf_bars(m1_bars, period=5):
    """Aggregate M1 bars into higher timeframe (M5 or M15)."""
    htf = []
    for i in range(0, len(m1_bars) - period + 1, period):
        chunk = m1_bars[i:i+period]
        htf.append({
            "time": chunk[0]["time"],
            "open": chunk[0]["open"],
            "high": max(b["high"] for b in chunk),
            "low": min(b["low"] for b in chunk),
            "close": chunk[-1]["close"],
            "vol": sum(b["vol"] for b in chunk),
        })
    return htf


def find_nearest_sr(bars, direction, lookback=60):
    """Find nearest S/R level from recent swing highs/lows."""
    if len(bars) < lookback: return None
    seg = bars[-lookback:]
    levels = []
    for i in range(2, len(seg) - 2):
        # Swing high
        if seg[i]["high"] > seg[i-1]["high"] and seg[i]["high"] > seg[i-2]["high"] and \
           seg[i]["high"] > seg[i+1]["high"] and seg[i]["high"] > seg[i+2]["high"]:
            levels.append(seg[i]["high"])
        # Swing low
        if seg[i]["low"] < seg[i-1]["low"] and seg[i]["low"] < seg[i-2]["low"] and \
           seg[i]["low"] < seg[i+1]["low"] and seg[i]["low"] < seg[i+2]["low"]:
            levels.append(seg[i]["low"])
    if not levels: return None
    current = bars[-1]["close"]
    if direction == 1:  # BUY — find nearest resistance above
        above = [l for l in levels if l > current]
        return min(above) if above else None
    else:  # SELL — find nearest support below
        below = [l for l in levels if l < current]
        return max(below) if below else None


# ═══════════════════════════════════════════════════════════════
# DETECT — Flexible signal detection with all PDF params
# ═══════════════════════════════════════════════════════════════

def detect(m1, er_min=0.15, bo_body_frac=0.55, uhv_range_min=UHV_RANGE_MIN,
           require_high_vol_breakout=False, require_no_supply=False,
           mtf_m5=False, mtf_m15=False, sr_filter=False, sr_min_distance=5.0,
           spread_max=None, tick_data=None):
    """
    Flexible signal detection.
    
    require_high_vol_breakout: if True, breakout vol must be HIGHER than UHV (PDF recommendation)
                               if False, breakout vol must be LOWER (current S4b)
    require_no_supply: if True, require a narrow-range low-vol "test" bar between UHV and breakout
    mtf_m5: require M5 trend alignment
    mtf_m15: require M15 trend alignment
    sr_filter: skip trades near S/R levels
    """
    sigs = []
    start = TREND_LB + RETRACE_LB + 2

    # Build HTF bars for multi-timeframe
    m5_bars = build_htf_bars(m1, 5) if (mtf_m5 or mtf_m15) else []
    m15_bars = build_htf_bars(m1, 15) if mtf_m15 else []

    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < bo_body_frac: continue

        win = m1[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue

        tw = m1[i - TREND_LB:i]
        if er_min > 0 and efficiency_ratio(tw) < er_min: continue
        td = trend_dir(tw)
        if td == 0: continue

        # Multi-timeframe check
        if mtf_m5 and m5_bars:
            # Find the M5 bar that corresponds to this M1 bar's time
            m5_before = [b for b in m5_bars if b["time"] <= bo["time"]]
            if len(m5_before) >= 6:
                m5_td = trend_dir(m5_before[-6:], 6)
                if m5_td != td: continue  # M5 must agree
            else:
                continue

        if mtf_m15 and m15_bars:
            m15_before = [b for b in m15_bars if b["time"] <= bo["time"]]
            if len(m15_before) >= 4:
                m15_td = trend_dir(m15_before[-4:], 4)
                if m15_td != td: continue  # M15 must agree
            else:
                continue

        # S/R proximity filter
        if sr_filter:
            sr = find_nearest_sr(m1[:i], td, lookback=60)
            if sr is not None:
                dist = abs(sr - bo["close"])
                if dist < sr_min_distance:
                    continue  # too close to S/R, skip

        # BUY: green breakout over UHV red
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"]]
            qualified = [r for r in reds if (r["high"] - r["low"]) >= uhv_range_min]
            if not qualified: continue
            uhv = max(qualified, key=lambda b: b["vol"])

            # Volume check
            if require_high_vol_breakout:
                if bo["vol"] <= uhv["vol"]: continue  # breakout must be HIGHER vol
            else:
                if bo["vol"] >= uhv["vol"]: continue  # breakout must be LOWER vol (current)

            if bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                # No Supply test bar check
                if require_no_supply:
                    # Look for a narrow-range, low-vol bar between UHV and breakout
                    uhv_idx = None
                    for j, b in enumerate(win):
                        if b["time"] == uhv["time"]: uhv_idx = j; break
                    if uhv_idx is None: continue
                    found_ns = False
                    avg_vol = sum(b["vol"] for b in win) / len(win)
                    for k in range(uhv_idx + 1, len(win)):
                        tb = win[k]
                        tb_rng = tb["high"] - tb["low"]
                        tb_body = abs(tb["close"] - tb["open"])
                        # Narrow range + low volume + dips into UHV zone
                        if tb["vol"] < 0.5 * avg_vol and tb_rng < rng * 0.6:
                            found_ns = True; break
                    if not found_ns: continue

                fire_t = bo["time"] + timedelta(minutes=1)
                cur_atr = atr(m1[:i+1], 7)
                sigs.append({"side": +1, "fire_time": fire_t, "atr": cur_atr})
                continue

        # SELL: red breakout under UHV green
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"]]
            qualified = [g for g in greens if (g["high"] - g["low"]) >= uhv_range_min]
            if not qualified: continue
            uhv = max(qualified, key=lambda b: b["vol"])

            if require_high_vol_breakout:
                if bo["vol"] <= uhv["vol"]: continue
            else:
                if bo["vol"] >= uhv["vol"]: continue

            if bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                if require_no_supply:
                    uhv_idx = None
                    for j, b in enumerate(win):
                        if b["time"] == uhv["time"]: uhv_idx = j; break
                    if uhv_idx is None: continue
                    found_ns = False
                    avg_vol = sum(b["vol"] for b in win) / len(win)
                    for k in range(uhv_idx + 1, len(win)):
                        tb = win[k]
                        tb_rng = tb["high"] - tb["low"]
                        if tb["vol"] < 0.5 * avg_vol and tb_rng < rng * 0.6:
                            found_ns = True; break
                    if not found_ns: continue

                fire_t = bo["time"] + timedelta(minutes=1)
                cur_atr = atr(m1[:i+1], 7)
                sigs.append({"side": -1, "fire_time": fire_t, "atr": cur_atr})

    return sigs


def replay(ticks, sigs, tp_pts=5.0, sl_pts=6.0, use_atr=False,
           atr_sl_mult=1.5, atr_tp_mult=2.5, atr_trail=False, atr_trail_mult=1.5,
           breakeven_at_atr=1.0, max_spread=None, max_conc=3):
    """Replay with optional ATR-based exits, trailing, breakeven, and spread filter."""
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        spread = ask - bid

        # Manage existing positions
        for u in units[:]:
            s = u["side"]
            if s > 0:
                cur_prof = bid - u["e"]
                # Breakeven logic
                if atr_trail and u.get("atr_val", 0) > 0:
                    be_dist = breakeven_at_atr * u["atr_val"]
                    if cur_prof >= be_dist and u.get("sl_price") is not None:
                        u["sl_price"] = max(u["sl_price"], u["e"])  # move SL to breakeven
                    # Trailing
                    if cur_prof > u.get("peak", 0):
                        u["peak"] = cur_prof
                        trail_sl = bid - atr_trail_mult * u["atr_val"]
                        if trail_sl > u.get("sl_price", 0):
                            u["sl_price"] = trail_sl

                sl_price = u.get("sl_price", u["e"] - u["sl"])
                tp_price = u.get("tp_price", u["e"] + u["tp"])
                if bid <= sl_price:
                    u["pnl"] = (sl_price - u["e"]) * ppp
                    u["result"] = "W" if u["pnl"] > 0 else "L"
                    done.append(u); units.remove(u); continue
                if bid >= tp_price:
                    u["pnl"] = (tp_price - u["e"]) * ppp
                    u["result"] = "W"
                    done.append(u); units.remove(u); continue
            else:
                cur_prof = u["e"] - ask
                if atr_trail and u.get("atr_val", 0) > 0:
                    be_dist = breakeven_at_atr * u["atr_val"]
                    if cur_prof >= be_dist and u.get("sl_price") is not None:
                        u["sl_price"] = min(u["sl_price"], u["e"])
                    if cur_prof > u.get("peak", 0):
                        u["peak"] = cur_prof
                        trail_sl = ask + atr_trail_mult * u["atr_val"]
                        if trail_sl < u.get("sl_price", 1e18):
                            u["sl_price"] = trail_sl

                sl_price = u.get("sl_price", u["e"] + u["sl"])
                tp_price = u.get("tp_price", u["e"] - u["tp"])
                if ask >= sl_price:
                    u["pnl"] = (u["e"] - sl_price) * ppp
                    u["result"] = "W" if u["pnl"] > 0 else "L"
                    done.append(u); units.remove(u); continue
                if ask <= tp_price:
                    u["pnl"] = (u["e"] - tp_price) * ppp
                    u["result"] = "W"
                    done.append(u); units.remove(u); continue

        # Fire new signals
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < max_conc:
                # Spread filter
                if max_spread is not None and spread > max_spread:
                    pend = next(it, None)
                    continue

                entry = ask if pend["side"] > 0 else bid
                sig_atr = pend.get("atr", 0)

                if use_atr and sig_atr > 0:
                    sl_val = atr_sl_mult * sig_atr
                    tp_val = atr_tp_mult * sig_atr
                else:
                    sl_val = sl_pts
                    tp_val = tp_pts

                u = {
                    "side": pend["side"], "e": entry, "open_t": t,
                    "sl": sl_val, "tp": tp_val, "peak": 0,
                    "atr_val": sig_atr,
                }
                if pend["side"] > 0:
                    u["sl_price"] = entry - sl_val
                    u["tp_price"] = entry + tp_val
                else:
                    u["sl_price"] = entry + sl_val
                    u["tp_price"] = entry - tp_val
                units.append(u)
            pend = next(it, None)

    # EOD close
    if ticks:
        last = ticks[-1]
        for u in units:
            p = ((last["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - last["ask"])) * ppp
            u["pnl"] = p; u["result"] = "W" if p > 0 else "L"
            done.append(u)
    return done


def stat(trades, nd):
    n = len(trades)
    if not n: return "n=0", 0, 0, 0
    w = sum(1 for t in trades if t.get("result") == "W")
    wr = w / n
    tot = sum(t["pnl"] for t in trades)
    avg_w = sum(t["pnl"] for t in trades if t["pnl"] > 0) / w if w else 0
    avg_l = sum(t["pnl"] for t in trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
    s = f"n={n:>4} {n/nd:>5.1f}/d  WR={wr:>5.1%}  W=${avg_w:>5.1f}  L=${avg_l:>+5.1f}  TOT=${tot:>+9.1f}"
    return s, wr, tot, n


def run_test(label, days, cache, nd, mid, detect_kwargs=None, replay_kwargs=None):
    """Run a single test configuration and print results."""
    dk = detect_kwargs or {}
    rk = replay_kwargs or {}
    train, test = [], []
    for k, d in enumerate(days):
        sigs = detect(cache[d]["m1"], **dk)
        tr = replay(cache[d]["ticks"], sigs, **rk)
        (train if k < mid else test).extend(tr)
    a = sum(t["pnl"] for t in train)
    b = sum(t["pnl"] for t in test)
    all_t = train + test
    s1, wr1, t1, n1 = stat(all_t, nd)
    s2, wr2, t2, n2 = stat(test, nd - mid)
    wf = "✓" if a > 0 and b > 0 else " "
    flag = ""
    if wr1 >= 0.75: flag = " ★★★"
    elif wr1 >= 0.65: flag = " ★★"
    elif wr1 >= 0.58: flag = " ★"
    print(f"  [{wf}] {label:<55} ALL: {s1}{flag}")
    print(f"      {'':55} OOS: {s2}")
    return {"label": label, "wr": wr1, "total": t1, "train": a, "test": b, "n": n1, "wr_oos": wr2}


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

    print(f"PDF RECOMMENDATIONS TEST — {nd} broker-tick days, {LOTS} lots")
    print(f"{'='*120}\n")

    # ══════════════════════════════════════════════════════════
    # BASELINE
    # ══════════════════════════════════════════════════════════
    print("=== BASELINE (current S4b v1.01) ===")
    run_test("S4b v1.01: TP5/SL6, ER>=0.15, low-vol breakout", days, cache, nd, mid)
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 1: ER THRESHOLD (PDF recommends 0.30-0.40)
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 1: ER Threshold (PDF says raise to 0.30-0.40)")
    print("=" * 120)
    for er in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
        run_test(f"ER>={er:.2f}", days, cache, nd, mid, detect_kwargs={"er_min": er})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 2: MULTI-TIMEFRAME ALIGNMENT
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 2: Multi-Timeframe Alignment (PDF: M5+M15 must agree)")
    print("=" * 120)
    run_test("M1 only (baseline)", days, cache, nd, mid)
    run_test("M1 + M5 alignment", days, cache, nd, mid,
             detect_kwargs={"mtf_m5": True})
    run_test("M1 + M15 alignment", days, cache, nd, mid,
             detect_kwargs={"mtf_m15": True})
    run_test("M1 + M5 + M15 alignment", days, cache, nd, mid,
             detect_kwargs={"mtf_m5": True, "mtf_m15": True})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 3: VSA VOLUME LOGIC (PDF says FLIP to high-vol breakout)
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 3: VSA Volume Logic (PDF: high-vol breakout, not low-vol)")
    print("=" * 120)
    run_test("LOW-vol breakout (current S4b)", days, cache, nd, mid,
             detect_kwargs={"require_high_vol_breakout": False})
    run_test("HIGH-vol breakout (PDF recommendation)", days, cache, nd, mid,
             detect_kwargs={"require_high_vol_breakout": True})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 4: "NO SUPPLY" TEST BAR
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 4: No Supply Test Bar (PDF: require low-vol pullback before breakout)")
    print("=" * 120)
    run_test("No test bar required (current)", days, cache, nd, mid)
    run_test("+ No Supply test bar (low-vol narrow)", days, cache, nd, mid,
             detect_kwargs={"require_no_supply": True})
    run_test("HIGH-vol breakout + No Supply test bar", days, cache, nd, mid,
             detect_kwargs={"require_high_vol_breakout": True, "require_no_supply": True})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 5: ATR-BASED DYNAMIC EXITS
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 5: ATR-Based Dynamic Exits (PDF: replace fixed TP/SL)")
    print("=" * 120)
    run_test("Fixed TP5/SL6 (current)", days, cache, nd, mid)
    for sl_m, tp_m in [(1.5, 2.0), (1.5, 2.5), (1.5, 3.0), (2.0, 2.5), (2.0, 3.0), (2.0, 4.0)]:
        run_test(f"ATR(7): SL={sl_m}x, TP={tp_m}x", days, cache, nd, mid,
                 replay_kwargs={"use_atr": True, "atr_sl_mult": sl_m, "atr_tp_mult": tp_m})
    # ATR with trailing
    for sl_m, trail_m in [(1.5, 1.0), (1.5, 1.5), (2.0, 1.5), (2.0, 2.0)]:
        run_test(f"ATR(7): SL={sl_m}x, trail={trail_m}x, BE@1.0xATR", days, cache, nd, mid,
                 replay_kwargs={"use_atr": True, "atr_sl_mult": sl_m, "atr_tp_mult": 99,
                                "atr_trail": True, "atr_trail_mult": trail_m, "breakeven_at_atr": 1.0})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 6: MAX SPREAD FILTER
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 6: Max Spread Filter (PDF: skip trades with wide spreads)")
    print("=" * 120)
    run_test("No spread filter (current)", days, cache, nd, mid)
    for ms in (0.20, 0.30, 0.40, 0.50, 0.70, 1.00):
        run_test(f"Max spread <= {ms:.2f} pts", days, cache, nd, mid,
                 replay_kwargs={"max_spread": ms})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 7: S/R PROXIMITY FILTER ("CLEAR AIR")
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 7: S/R Proximity Filter (PDF: need 'clear air' to profit target)")
    print("=" * 120)
    run_test("No S/R filter (current)", days, cache, nd, mid)
    for sr_d in (2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
        run_test(f"Skip if S/R within {sr_d:.1f} pts", days, cache, nd, mid,
                 detect_kwargs={"sr_filter": True, "sr_min_distance": sr_d})
    print()

    # ══════════════════════════════════════════════════════════
    # TEST 8: COMBINED — best ideas together
    # ══════════════════════════════════════════════════════════
    print("=" * 120)
    print("TEST 8: Combined — best ideas stacked together")
    print("=" * 120)
    combos = [
        ("Baseline S4b v1.01", {}, {}),
        ("+ M5 alignment", {"mtf_m5": True}, {}),
        ("+ M5 + spread<=0.40", {"mtf_m5": True}, {"max_spread": 0.40}),
        ("+ M5 + S/R 5pts", {"mtf_m5": True, "sr_filter": True, "sr_min_distance": 5.0}, {}),
        ("+ M5 + ATR SL1.5x TP2.5x", {"mtf_m5": True}, {"use_atr": True, "atr_sl_mult": 1.5, "atr_tp_mult": 2.5}),
        ("+ M5 + ATR SL2x trail1.5x", {"mtf_m5": True}, {"use_atr": True, "atr_sl_mult": 2.0, "atr_tp_mult": 99, "atr_trail": True, "atr_trail_mult": 1.5}),
        ("+ M5 + M15 + spread<=0.40", {"mtf_m5": True, "mtf_m15": True}, {"max_spread": 0.40}),
        ("Full PDF: M5+S/R+ATR trail+spread", {"mtf_m5": True, "sr_filter": True, "sr_min_distance": 5.0},
         {"use_atr": True, "atr_sl_mult": 1.5, "atr_tp_mult": 99, "atr_trail": True, "atr_trail_mult": 1.5, "max_spread": 0.40}),
        ("Full PDF + ER>=0.25", {"mtf_m5": True, "sr_filter": True, "sr_min_distance": 5.0, "er_min": 0.25},
         {"use_atr": True, "atr_sl_mult": 1.5, "atr_tp_mult": 99, "atr_trail": True, "atr_trail_mult": 1.5, "max_spread": 0.40}),
    ]
    results = []
    for lbl, dk, rk in combos:
        r = run_test(lbl, days, cache, nd, mid, detect_kwargs=dk, replay_kwargs=rk)
        results.append(r)
    print()

    # Summary
    print("=" * 120)
    print("COMBINED RESULTS SUMMARY (sorted by OOS WR)")
    print("=" * 120)
    results.sort(key=lambda r: (-r["wr_oos"], -r["test"]))
    print(f"  {'Label':<55} {'WR':>6} {'WR_OOS':>7} {'n':>4} {'TRAIN':>9} {'TEST':>9} {'TOTAL':>9} {'WF':>3}")
    for r in results:
        wf = "✓" if r["train"] > 0 and r["test"] > 0 else " "
        print(f"  {r['label']:<55} {r['wr']:>5.1%} {r['wr_oos']:>6.1%} {r['n']:>4} ${r['train']:>+7.0f} ${r['test']:>+7.0f} ${r['total']:>+7.0f}  {wf}")


if __name__ == "__main__":
    main()
