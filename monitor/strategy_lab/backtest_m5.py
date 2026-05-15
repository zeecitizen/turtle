"""backtest_m5.py — test Zee's M5 hypothesis: same v3.49 strategy, but
the detector reads M5 bars instead of M1.

Builds M5 bars by aggregating M1 (5 M1 → 1 M5: open=first, close=last,
high=max, low=min, vol=sum). The probe-to-trade lifecycle and all $
thresholds stay unchanged — direct apples-to-apples comparison.

Runs across all 12 days of real bid/ask ticks.
"""
import csv
import glob
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import (
    COMMON, load_m1_merged, load_ticks, detect_on_bar,
    PROBE_LOTS, REAL_LOTS, PROBE_FLOOR, MAX_UNITS, RATE_LIMIT_S, CONTRACT,
    MAX_LOOKBACK, MAX_BARS_BACK,
)


def aggregate_to_m5(bars_m1):
    """5 M1 bars → 1 M5 bar. M5 bucket keyed by minute floored to /5."""
    m5 = {}
    for b in bars_m1:
        key = b["time"].replace(minute=(b["time"].minute // 5) * 5, second=0)
        if key not in m5:
            m5[key] = {"time": key, "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            m5[key]["high"]  = max(m5[key]["high"], b["high"])
            m5[key]["low"]   = min(m5[key]["low"],  b["low"])
            m5[key]["close"] = b["close"]
            m5[key]["vol"]  += b["vol"]
    return sorted(m5.values(), key=lambda b: b["time"])


def build_signals_m5(bars_m5):
    """For each M5 bar that closes at t = bar.time + 5min, the signal is
    live during the 5-minute window AFTER close. We fan that out to per-
    minute keys so the existing replay() lookup works unchanged."""
    sig = {}
    for i, b in enumerate(bars_m5):
        if i < MAX_LOOKBACK + 2: continue
        s = detect_on_bar(bars_m5, i, strict=False)   # v3.49 relaxed detector
        close_t = b["time"] + timedelta(minutes=5)
        for k in range(5):
            sig[close_t + timedelta(minutes=k)] = s
    return sig


def replay(ticks, sig, probe_confirm=1.0, main_floor=150.0,
           main_bank=8.0, main_drop=3.0):
    units, last_fire, done = [], None, []

    def p_pnl(u, bid, ask):
        return ((bid - u["pe"]) if u["side"] > 0 else (u["pe"] - ask)) * PROBE_LOTS * CONTRACT
    def m_pnl(u, bid, ask):
        return ((bid - u["me"]) if u["side"] > 0 else (u["me"] - ask)) * REAL_LOTS * CONTRACT

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["state"] == "PROBING":
                pp = p_pnl(u, bid, ask)
                if pp <= -PROBE_FLOOR:
                    u["pnl"] = -PROBE_FLOOR; u["why"] = "probe_floor"
                    done.append(u); units.remove(u)
                elif pp >= probe_confirm:
                    u["state"] = "TRADING"; u["me"] = ask if u["side"] > 0 else bid
                    u["pcp"] = pp; u["peak"] = 0.0; u["locked"] = 0.0; u["mopen"] = t
            else:
                pnl = m_pnl(u, bid, ask)
                if pnl > u["peak"]: u["peak"] = pnl
                exit_pnl = exit_why = None
                if u["peak"] >= main_bank:
                    tgt = u["peak"] - main_drop
                    if tgt > u["locked"]: u["locked"] = tgt
                if u["locked"] > 0 and pnl <= u["locked"]:
                    exit_pnl, exit_why = u["locked"], "rollover"
                if exit_pnl is None and pnl <= -main_floor:
                    exit_pnl, exit_why = -main_floor, "main_floor"
                if exit_pnl is not None:
                    u["pnl"] = u["pcp"] + exit_pnl; u["why"] = exit_why
                    done.append(u); units.remove(u)
        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        s = sig.get(t.replace(second=0), (0, 0, 0))[0]
        if s == 0: continue
        units.append({"state": "PROBING", "side": s,
                      "pe": ask if s > 0 else bid, "open_t": t})
        last_fire = t

    last = ticks[-1]
    for u in units:
        if u["state"] == "PROBING":
            u["pnl"] = p_pnl(u, last["bid"], last["ask"]); u["why"] = "probe_eod"
        else:
            u["pnl"] = u["pcp"] + m_pnl(u, last["bid"], last["ask"]); u["why"] = "main_eod"
        done.append(u)
    total = sum(u["pnl"] for u in done)
    wins   = sum(1 for u in done if u["pnl"] > 0)
    losses = sum(1 for u in done if u["pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    floor_hits = sum(1 for u in done if u["why"] == "main_floor")
    rollover   = sum(1 for u in done if u["why"] == "rollover")
    worst = min((u["pnl"] for u in done), default=0.0)
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr,
                worst=worst, floor=floor_hits, rollover=rollover)


def main():
    bars_m1 = load_m1_merged()
    bars_m5 = aggregate_to_m5(bars_m1)
    print(f"M1 bars: {len(bars_m1)}   M5 bars: {len(bars_m5)}")

    # M1 signals (the v3.50 deployed config)
    from backtest_v349_multiday import build_signals as build_m1_sigs
    sig_m1 = build_m1_sigs(bars_m1, strict=False)
    sig_m5 = build_signals_m5(bars_m5)
    sig_m1_count = sum(1 for v in sig_m1.values()  if v[0] != 0)
    sig_m5_count = sum(1 for v in sig_m5.values() if v[0] != 0)
    print(f"Signal-minutes : M1={sig_m1_count}   M5={sig_m5_count}  "
          f"(M5 fires ~{100*sig_m5_count/max(sig_m1_count,1):.0f}% as often)\n")

    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"{'day':<12} | {'M1 (current v3.50)':<32} | {'M5 (Zee hypothesis)':<32}")
    print(f"{'':12} | {'NET    n  WR worst    floor':<32} | {'NET    n  WR worst    floor'}")
    print("-" * 100)
    agg_m1 = {"t": 0.0, "n": 0, "w": 0, "l": 0, "floor": 0, "worst": 0.0}
    agg_m5 = {"t": 0.0, "n": 0, "w": 0, "l": 0, "floor": 0, "worst": 0.0}
    days_m1 = days_m5 = 0; nd = 0
    for tf in tick_files:
        day = Path(tf).stem.replace("shano_ticks_", "")
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        nd += 1
        r1 = replay(ticks, sig_m1)
        r5 = replay(ticks, sig_m5)
        for a, r in ((agg_m1, r1), (agg_m5, r5)):
            a["t"] += r["total"]; a["n"] += r["n"]; a["w"] += r["w" if False else "wins"]
            a["l"] += r["losses"]; a["floor"] += r["floor"]
            a["worst"] = min(a["worst"], r["worst"])
        if r1["total"] > 0: days_m1 += 1
        if r5["total"] > 0: days_m5 += 1
        print(f"{day:<12} | ${r1['total']:<+8.0f} {r1['n']:<3} {r1['wr']:.0f}% ${r1['worst']:<+5.0f} fl{r1['floor']:<3} | "
              f"${r5['total']:<+8.0f} {r5['n']:<3} {r5['wr']:.0f}% ${r5['worst']:<+5.0f} fl{r5['floor']}")
    wr1 = 100*agg_m1["w"]/(agg_m1["w"]+agg_m1["l"]) if (agg_m1["w"]+agg_m1["l"]) else 0
    wr5 = 100*agg_m5["w"]/(agg_m5["w"]+agg_m5["l"]) if (agg_m5["w"]+agg_m5["l"]) else 0
    print("-" * 100)
    print(f"{'TOTAL':<12} | ${agg_m1['t']:<+8.0f} {agg_m1['n']:<3} {wr1:.0f}% ${agg_m1['worst']:<+5.0f} fl{agg_m1['floor']:<3} | "
          f"${agg_m5['t']:<+8.0f} {agg_m5['n']:<3} {wr5:.0f}% ${agg_m5['worst']:<+5.0f} fl{agg_m5['floor']}")
    print(f"\n  M1 : {days_m1}/{nd} days green, total ${agg_m1['t']:+.2f}")
    print(f"  M5 : {days_m5}/{nd} days green, total ${agg_m5['t']:+.2f}")
    print(f"\n  Switching M1 → M5 changes the 12-day total by ${agg_m5['t']-agg_m1['t']:+.2f}")


if __name__ == "__main__":
    main()
