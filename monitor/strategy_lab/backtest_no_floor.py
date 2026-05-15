"""backtest_no_floor.py — what if we DON'T have the -$150 main floor and
hold the main "indefinitely" (Shano-style, no per-trade loss cut)?

Reuses backtest_v349_multiday.replay() with main_floor effectively disabled
(set to a huge number so the catastrophe SL never triggers). The main only
exits on roll-over (peak >= $8, lock at peak - $3) or stays open to EOD.

Compares head-to-head against the v3.49 baseline (floor = $150) on all 12
days of real tick data. Surfaces the worst single unit per config too —
that's the true cost of "unbounded."
"""
import glob
import sys
from pathlib import Path

# import from the multiday script
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import (
    COMMON, load_m1_merged, load_ticks, build_signals, replay,
)


def replay_capture_worst(ticks, sig, probe_confirm, main_floor, main_bank=8.0, main_drop=3.0):
    """Same as replay() but returns the worst single unit P&L too."""
    # We patch by running replay then inspecting `done` — easier: re-implement
    # tiny version that records each unit's final P&L.
    from backtest_v349_multiday import (
        PROBE_LOTS, REAL_LOTS, PROBE_FLOOR, MAX_UNITS, RATE_LIMIT_S, CONTRACT,
    )
    from datetime import timedelta

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
        units.append({"state": "PROBING", "side": s, "pe": ask if s > 0 else bid, "open_t": t})
        last_fire = t

    last = ticks[-1]
    for u in units:
        if u["state"] == "PROBING":
            u["pnl"] = p_pnl(u, last["bid"], last["ask"]); u["why"] = "probe_eod"
        else:
            u["pnl"] = u["pcp"] + m_pnl(u, last["bid"], last["ask"]); u["why"] = "main_eod"
        done.append(u)

    total = sum(u["pnl"] for u in done)
    worst = min((u["pnl"] for u in done), default=0.0)
    best  = max((u["pnl"] for u in done), default=0.0)
    eod_main = sum(1 for u in done if u["why"] == "main_eod")
    rollover = sum(1 for u in done if u["why"] == "rollover")
    floor_hits = sum(1 for u in done if u["why"] == "main_floor")
    return dict(total=total, worst=worst, best=best, n=len(done),
                rollover=rollover, eod_main=eod_main, floor_hits=floor_hits)


def main():
    bars = load_m1_merged()
    sig  = build_signals(bars, strict=False)   # current v3.50 detector = relaxed
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    print(f"{'day':<12} | {'WITH -$150 floor':<28} | {'NO floor (Shano forever)'}")
    print(f"{'':12} | {'NET    wins/losses worst':<28} | {'NET    wins/losses worst   eod-still-open'}")
    print("-" * 100)
    agg_f = {"total": 0.0, "worst": 0.0, "wins": 0, "losses": 0, "eod": 0}
    agg_n = {"total": 0.0, "worst": 0.0, "wins": 0, "losses": 0, "eod": 0}
    days_pos_f = days_pos_n = 0
    nd = 0
    for tf in tick_files:
        day = Path(tf).stem.replace("shano_ticks_", "")
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        nd += 1
        r_f = replay_capture_worst(ticks, sig, probe_confirm=1.0, main_floor=150.0)
        r_n = replay_capture_worst(ticks, sig, probe_confirm=1.0, main_floor=1e9)  # effectively infinite

        # WR per branch using sign of unit pnl
        # (the replay returns aggregate; rebuild W/L for display by re-running we'd be redundant — use counts)
        # we have rollover/eod/floor counts; approximate W/L from aggregate sign per unit isn't returned.
        # The new replay returns just totals — that's enough for the comparison.

        agg_f["total"] += r_f["total"]; agg_f["worst"] = min(agg_f["worst"], r_f["worst"])
        agg_n["total"] += r_n["total"]; agg_n["worst"] = min(agg_n["worst"], r_n["worst"])
        agg_n["eod"]  += r_n["eod_main"]
        if r_f["total"] > 0: days_pos_f += 1
        if r_n["total"] > 0: days_pos_n += 1

        print(f"{day:<12} | "
              f"${r_f['total']:<+10.2f} n={r_f['n']:<3} worst${r_f['worst']:<+8.2f} | "
              f"${r_n['total']:<+10.2f} n={r_n['n']:<3} worst${r_n['worst']:<+8.2f} eod-open={r_n['eod_main']}")

    print("-" * 100)
    print(f"{'TOTAL':<12} | "
          f"${agg_f['total']:<+10.2f}        worst${agg_f['worst']:<+8.2f} | "
          f"${agg_n['total']:<+10.2f}        worst${agg_n['worst']:<+8.2f} eod-still-open={agg_n['eod']}")
    print()
    print(f"  WITH -$150 floor : {days_pos_f}/{nd} days green, total ${agg_f['total']:+.2f}, deepest single loss ${agg_f['worst']:+.2f}")
    print(f"  NO floor (forever): {days_pos_n}/{nd} days green, total ${agg_n['total']:+.2f}, deepest single loss ${agg_n['worst']:+.2f}")
    diff = agg_n["total"] - agg_f["total"]
    print(f"\n  Removing the floor changes the 12-day total by ${diff:+.2f}")


if __name__ == "__main__":
    main()
