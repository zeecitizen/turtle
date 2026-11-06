"""Print v3.43 fires and Shano fires side-by-side with strict 1-to-1 matching
(each EA trade can match only ONE Shano)."""
from datetime import datetime, timedelta
from v3_43_relax_sim import load_bars, simulate, M1_CSV, SHANO_SETUPS


def main():
    bars = load_bars(M1_CSV)
    start = datetime(2026, 5, 13, 2, 0)
    end = datetime(2026, 5, 13, 3, 0)
    trades = simulate(bars, start, end, {"mode_strict_vol": False, "mode_break": False, "mode_color": True})

    print(f"v3.43 fired {len(trades)} trades in window:")
    for t in trades:
        print(f"  {t['entry_time']:%H:%M:%S}  {t['side']:<5} entry={t['entry']:.2f}  closed={t['close_time']:%H:%M:%S} ${t['close_pnl']:+.2f} ({t['close_reason']})")
    print()

    # Strict 1-to-1 matching
    print(f"Strict 1-to-1 matching (each EA trade used once):")
    used = set()
    captured = 0
    misses = []
    for st, side, lot, pnl in SHANO_SETUPS:
        zt = datetime(2026, 5, 13, int(st[:2]), int(st[3:5]), int(st[6:8]))
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, t in enumerate(trades):
            if i in used: continue
            if t["side"] != side: continue
            gap = abs(t["entry_time"] - zt)
            if gap < timedelta(minutes=3) and gap < best_gap:
                best, best_gap, best_idx = t, gap, i
        if best:
            used.add(best_idx)
            captured += 1
            print(f"  OK  Shano {st} {side:<5} ${pnl:+6.2f}  →  EA {best['entry_time']:%H:%M:%S} (gap={int(best_gap.total_seconds())}s) ${best['close_pnl']:+.2f}")
        else:
            misses.append((st, side, pnl))
            print(f"  MISS Shano {st} {side:<5} ${pnl:+6.2f}")
    print(f"\nCaptured (strict 1-to-1): {captured}/{len(SHANO_SETUPS)}\n")
    print(f"Misses: {len(misses)}")
    for m in misses:
        print(f"  {m[0]} {m[1]} ${m[2]:+.2f}")


if __name__ == "__main__":
    main()
