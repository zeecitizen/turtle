"""backtest_mvts.py — multi-day validation of the Momentum-Validity Time
Stop hypothesis, with full EV(t) decomposition.

Hypothesis under test (from the deep-research report):
  if MAIN open >= N seconds AND main_peak < InpMainBankUSD ($8)
    → force-close at current market price ('mvts' exit)
  optionally suspend new probe fires for `cooldown` seconds after an MVTS exit

For each (cut-time, cooldown) we report not just total P&L but the explicit
EV decomposition — P_win(t), W_avg(t), L_avg(t), EV per trade — so the
multivariate function EV(t) = P_win·W_avg - P_loss·L_avg is visible.
"""
import csv
import glob
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import (
    COMMON, load_m1_merged, load_ticks, build_signals,
    PROBE_LOTS, REAL_LOTS, PROBE_FLOOR, MAX_UNITS, RATE_LIMIT_S, CONTRACT,
)


def replay_full(ticks, sig, probe_confirm=1.0,
                main_floor=150.0, main_bank=8.0, main_drop=3.0,
                mvts_secs=0, cooldown_secs=0):
    """Returns the FULL list of closed units (each with pnl + why) so the
    caller can compute any stat. Handles MVTS + post-MVTS cooldown."""
    units, last_fire, last_mvts_t, done = [], None, None, []

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
                elapsed = (t - u["mopen"]).total_seconds()
                if mvts_secs > 0 and elapsed >= mvts_secs and u["peak"] < main_bank:
                    exit_pnl, exit_why = pnl, "mvts"
                if exit_pnl is None:
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
                    if exit_why == "mvts": last_mvts_t = t

        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        if last_mvts_t and cooldown_secs > 0 and (t - last_mvts_t).total_seconds() < cooldown_secs:
            continue
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
    return done


def ev_decomposition(tick_files, sig, mvts_secs, cooldown_secs):
    """Run all 12 days at this config, return EV components."""
    win_pnls, loss_pnls = [], []
    mvts_pnls = []
    total = 0.0
    days_green = 0; nd = 0
    why_counts = {"rollover": 0, "mvts": 0, "main_floor": 0,
                  "probe_floor": 0, "probe_eod": 0, "main_eod": 0}
    for tf in tick_files:
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        nd += 1
        done = replay_full(ticks, sig, mvts_secs=mvts_secs, cooldown_secs=cooldown_secs)
        day_total = 0.0
        for u in done:
            day_total += u["pnl"]
            if u["pnl"] > 0: win_pnls.append(u["pnl"])
            elif u["pnl"] < 0: loss_pnls.append(u["pnl"])
            why_counts[u["why"]] = why_counts.get(u["why"], 0) + 1
            if u["why"] == "mvts": mvts_pnls.append(u["pnl"] - u.get("pcp", 0))
        total += day_total
        if day_total > 0: days_green += 1
    n_w, n_l = len(win_pnls), len(loss_pnls)
    p_win = n_w / (n_w + n_l) if (n_w + n_l) else 0
    w_avg = sum(win_pnls) / n_w if n_w else 0
    l_avg = -sum(loss_pnls) / n_l if n_l else 0   # positive
    ev = p_win * w_avg - (1 - p_win) * l_avg
    return dict(total=total, n=n_w+n_l, days_green=days_green, nd=nd,
                p_win=p_win, w_avg=w_avg, l_avg=l_avg, ev=ev,
                why=why_counts, mvts_pnls=mvts_pnls)


def main():
    bars = load_m1_merged()
    sig = build_signals(bars, strict=False)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"12 days × full v3.49 replay × MVTS grid — measuring EV(t,cd) decomposition\n")

    # Baseline
    print("=" * 100)
    print("BASELINE (no MVTS, $150 floor):")
    print("=" * 100)
    r = ev_decomposition(tick_files, sig, mvts_secs=0, cooldown_secs=0)
    print(f"  n={r['n']:<5} P_win={r['p_win']:.3f}  W_avg=${r['w_avg']:.2f}  "
          f"L_avg=${r['l_avg']:.2f}  EV=${r['ev']:+.2f}/trade  "
          f"total=${r['total']:+.2f}  days_green={r['days_green']}/{r['nd']}")
    baseline_ev = r['ev']; baseline_total = r['total']

    # Full Cartesian grid
    print("\n" + "=" * 100)
    print("MVTS grid: cut-time {15, 25, 30, 45, 60}s × cooldown {0, 60, 300}s")
    print("=" * 100)
    print(f"{'cut':<5} {'cd':<5} {'n':<5} {'P_win':<7} {'W_avg':<9} {'L_avg':<9} "
          f"{'EV/trade':<11} {'12d total':<12} {'green':<8} {'mvts-cut $ avg'}")
    print("-" * 100)
    results = []
    for cut in (15, 25, 30, 45, 60):
        for cd in (0, 60, 300):
            r = ev_decomposition(tick_files, sig, mvts_secs=cut, cooldown_secs=cd)
            mvts_avg = (statistics.mean(r["mvts_pnls"])
                        if r["mvts_pnls"] else 0.0)
            print(f"{cut:<5} {cd:<5} {r['n']:<5} {r['p_win']:.3f}  "
                  f"${r['w_avg']:<7.2f} ${r['l_avg']:<7.2f} "
                  f"${r['ev']:<+9.2f} ${r['total']:<+10.2f} {r['days_green']}/{r['nd']:<5} "
                  f"${mvts_avg:+.2f}")
            results.append((cut, cd, r))

    # Decay analysis: holding cooldown=0, how does each component move with cut-time?
    print("\n" + "=" * 100)
    print("EV(t) decay analysis @ cooldown=0 — how each component shifts vs baseline:")
    print("=" * 100)
    print(f"{'cut t':<7} {'ΔP_win':<10} {'ΔW_avg':<10} {'ΔL_avg':<10} {'ΔEV/trade':<12} {'verdict'}")
    print("-" * 80)
    base = ev_decomposition(tick_files, sig, mvts_secs=0, cooldown_secs=0)
    for cut, cd, r in results:
        if cd != 0: continue
        d_pwin = r['p_win'] - base['p_win']
        d_wavg = r['w_avg'] - base['w_avg']
        d_lavg = r['l_avg'] - base['l_avg']
        d_ev   = r['ev']   - base['ev']
        verdict = "BETTER" if d_ev > 0 else "worse"
        print(f"{cut}s    {d_pwin:+.3f}     ${d_wavg:+.2f}    "
              f"${d_lavg:+.2f}    ${d_ev:+.2f}      {verdict}")


if __name__ == "__main__":
    main()
