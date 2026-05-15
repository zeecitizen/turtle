"""backtest_mvts.py — multi-day validation of the Momentum-Validity Time Stop
hypothesis from the deep-research report.

Rule under test:
  if MAIN has been open >= N seconds AND main_peak < InpMainBankUSD ($8)
    → force-close at current market price ('mvts' exit)
  optionally: after an MVTS trigger, suspend new probe fires for `cooldown` seconds

Sweeps: cut-time N in {15, 25, 30, 45, 60}, cooldown in {0, 60, 180, 300}.
Compares each config to the v3.49 baseline (no MVTS, floor $150) across all
12 days of real bid/ask tick data.

Important: we report not just net P&L but the DISTRIBUTION of MVTS exits —
the report assumes 'cuts will average ~-$35'. We measure it.
"""
import csv
import glob
import statistics
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import (
    COMMON, load_m1_merged, load_ticks, build_signals,
    PROBE_LOTS, REAL_LOTS, PROBE_FLOOR, MAX_UNITS, RATE_LIMIT_S, CONTRACT,
)


def replay_mvts(ticks, sig, probe_confirm=1.0,
                main_floor=150.0, main_bank=8.0, main_drop=3.0,
                mvts_secs=0, cooldown_secs=0):
    """Full v3.49 replay + optional MVTS exit + optional post-MVTS cooldown."""
    units, last_fire, last_mvts, done = [], None, None, []
    mvts_pnls = []   # capture the P&L at the moment MVTS fires

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
                    u["state"] = "TRADING"
                    u["me"] = ask if u["side"] > 0 else bid
                    u["pcp"] = pp; u["peak"] = 0.0; u["locked"] = 0.0
                    u["mopen"] = t
            else:
                pnl = m_pnl(u, bid, ask)
                if pnl > u["peak"]: u["peak"] = pnl
                exit_pnl = exit_why = None
                elapsed = (t - u["mopen"]).total_seconds()

                # MVTS check FIRST (the hypothesis under test)
                if mvts_secs > 0 and elapsed >= mvts_secs and u["peak"] < main_bank:
                    exit_pnl, exit_why = pnl, "mvts"
                    mvts_pnls.append(pnl)

                # roll-over trail
                if exit_pnl is None:
                    if u["peak"] >= main_bank:
                        tgt = u["peak"] - main_drop
                        if tgt > u["locked"]: u["locked"] = tgt
                    if u["locked"] > 0 and pnl <= u["locked"]:
                        exit_pnl, exit_why = u["locked"], "rollover"

                # bounded floor (fallback only — MVTS should fire first)
                if exit_pnl is None and pnl <= -main_floor:
                    exit_pnl, exit_why = -main_floor, "main_floor"

                if exit_pnl is not None:
                    u["pnl"] = u["pcp"] + exit_pnl; u["why"] = exit_why
                    done.append(u); units.remove(u)
                    if exit_why == "mvts" and cooldown_secs > 0:
                        last_mvts = t

        # detect + fire
        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        if last_mvts and cooldown_secs > 0 and (t - last_mvts).total_seconds() < cooldown_secs:
            continue
        s = sig.get(t.replace(second=0), (0, 0, 0))[0]
        if s == 0: continue
        units.append({"state": "PROBING", "side": s,
                      "pe": ask if s > 0 else bid, "open_t": t})
        last_fire = t

    # close remaining at EOD
    last = ticks[-1]
    for u in units:
        if u["state"] == "PROBING":
            u["pnl"] = p_pnl(u, last["bid"], last["ask"]); u["why"] = "probe_eod"
        else:
            u["pnl"] = u["pcp"] + m_pnl(u, last["bid"], last["ask"]); u["why"] = "main_eod"
        done.append(u)

    total = sum(u["pnl"] for u in done)
    wins = sum(1 for u in done if u["pnl"] > 0)
    losses = sum(1 for u in done if u["pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    floor_hits = sum(1 for u in done if u["why"] == "main_floor")
    mvts_hits  = sum(1 for u in done if u["why"] == "mvts")
    rollover   = sum(1 for u in done if u["why"] == "rollover")
    worst = min((u["pnl"] for u in done), default=0.0)
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr,
                worst=worst, floor_hits=floor_hits, mvts_hits=mvts_hits,
                rollover=rollover, mvts_pnls=mvts_pnls)


def run_config(label, tick_files, sig, **kw):
    agg = {"total": 0.0, "n": 0, "wins": 0, "losses": 0,
           "floor": 0, "mvts": 0, "rollover": 0, "worst": 0.0}
    days_green = 0; nd = 0
    all_mvts_pnls = []
    for tf in tick_files:
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        nd += 1
        r = replay_mvts(ticks, sig, **kw)
        agg["total"]    += r["total"]
        agg["n"]        += r["n"]
        agg["wins"]     += r["wins"]
        agg["losses"]   += r["losses"]
        agg["floor"]    += r["floor_hits"]
        agg["mvts"]     += r["mvts_hits"]
        agg["rollover"] += r["rollover"]
        agg["worst"] = min(agg["worst"], r["worst"])
        all_mvts_pnls.extend(r["mvts_pnls"])
        if r["total"] > 0: days_green += 1
    wr = 100 * agg["wins"] / (agg["wins"] + agg["losses"]) if (agg["wins"] + agg["losses"]) else 0
    mvts_stats = ""
    if all_mvts_pnls:
        avg = statistics.mean(all_mvts_pnls)
        med = statistics.median(all_mvts_pnls)
        mvts_stats = (f"  MVTS cuts: avg=${avg:+.2f} med=${med:+.2f} "
                      f"min=${min(all_mvts_pnls):+.2f} max=${max(all_mvts_pnls):+.2f}")
    print(f"  {label:<38} ${agg['total']:<+10.2f} {days_green}/{nd}d  WR{wr:.0f}%  "
          f"worst${agg['worst']:<+8.2f}  [roll {agg['rollover']} | mvts {agg['mvts']} | floor {agg['floor']}]")
    if mvts_stats: print(mvts_stats)
    return agg["total"], days_green, agg["mvts"], all_mvts_pnls


def main():
    bars = load_m1_merged()
    sig = build_signals(bars, strict=False)   # current v3.50 detector
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"Tick files: {len(tick_files)}  Signals: {sum(1 for v in sig.values() if v[0] != 0)}\n")

    print("=" * 100)
    print("BASELINE (no MVTS, $150 floor) — what we already know")
    print("=" * 100)
    run_config("baseline ($150 floor)", tick_files, sig, mvts_secs=0)

    print("\n" + "=" * 100)
    print("MVTS sweep — cut-time, NO cooldown")
    print("=" * 100)
    for n in (15, 20, 25, 30, 45, 60):
        run_config(f"MVTS {n}s, no cooldown",
                   tick_files, sig, mvts_secs=n, cooldown_secs=0)

    print("\n" + "=" * 100)
    print("MVTS sweep — cut-time + post-MVTS cooldown (the report's full spec)")
    print("=" * 100)
    for (n, cd) in [(25, 60), (25, 180), (25, 300), (30, 60), (30, 300), (45, 300)]:
        run_config(f"MVTS {n}s + {cd}s cooldown",
                   tick_files, sig, mvts_secs=n, cooldown_secs=cd)


if __name__ == "__main__":
    main()
