"""
smart_filter_test.py — apply the predictor-based filters discovered in
feature_analyzer.py and measure the lift in WR / P&L.
"""
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from feature_analyzer import simulate_with_features, SHADOW_CSV, HORIZON_SEC


def run_with_filter(name, predicate):
    """predicate(features) → True means SKIP (don't fire main).
    Returns dict with stats."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    feats = []
    history = []
    fired = []
    skipped = []
    for r in rows:
        f = simulate_with_features(r, history)
        if f is None:
            continue
        feats.append(f)
        if predicate and predicate(f):
            skipped.append(f)
            # don't update history — skipped trade doesn't count as a fired main
        else:
            fired.append(f)
            history.append({
                "dir": f["dir_sign"],
                "pnl": f["main_pnl"],
                "close_time": f["confirm_time"] + timedelta(seconds=HORIZON_SEC),
            })

    n_total = len(feats)
    n_fired = len(fired)
    n_skipped = len(skipped)
    wins = [f for f in fired if f["win"]]
    losses = [f for f in fired if not f["win"]]
    big_losses = [f for f in fired if f["main_pnl"] <= -30]
    total = sum(f["main_pnl"] for f in fired)
    avoided = sum(f["main_pnl"] for f in skipped if not f["win"])  # losses we dodged

    by_day = defaultdict(float)
    for f in fired:
        by_day[f["entry_time"].strftime("%Y-%m-%d")] += f["main_pnl"]

    return {
        "name": name,
        "n_total": n_total,
        "fired": n_fired,
        "skipped": n_skipped,
        "wins": len(wins),
        "losses": len(losses),
        "wr": len(wins) / max(n_fired, 1) * 100,
        "total": round(total, 2),
        "big_losses": len(big_losses),
        "avg_win": round(sum(f["main_pnl"] for f in wins) / max(len(wins), 1), 2),
        "avg_loss": round(sum(f["main_pnl"] for f in losses) / max(len(losses), 1), 2),
        "daily": {d: round(p, 2) for d, p in by_day.items()},
        "loss_avoided": round(-avoided, 2),
    }


# ─── Define predicates ────────────────────────────────────────
def f_prior_loss_opposite(f):
    return f["prior_outcome"] == "loss" and f["prior_dir"] == "opposite"


def f_prior_5_losses_ge_3(f):
    return f["prior_5_losses"] >= 3


def f_bad_hours(f):
    return f["hour_utc"] in (22, 23, 4, 5, 6)


def f_prior_5_losses_ge_2(f):
    return f["prior_5_losses"] >= 2


def f_prior_loss_any(f):
    return f["prior_outcome"] == "loss"


def f_combo_strict(f):
    return f_prior_loss_opposite(f) or f_prior_5_losses_ge_3(f) or f_bad_hours(f)


def f_combo_medium(f):
    return f_prior_loss_opposite(f) or f_prior_5_losses_ge_3(f)


def f_combo_loose(f):
    return f_prior_loss_opposite(f)


def f_bad_hours_wide(f):
    return f["hour_utc"] in (19, 20, 21, 22, 23, 4, 5, 6)


def f_low_mfe(f):
    """Skip if probe MFE at confirm is in the dead-zone 60-80c (bad WR per analysis)."""
    return 60 < f["probe_mfe_at_confirm_cents"] <= 80


def f_slow_confirm(f):
    """Skip if confirm took 3-8s (the bad WR bin)."""
    return 3 <= f["confirm_speed_sec"] <= 8


def f_keep_only_winners(f):
    """Best filter — combines positive features that boost WR."""
    # Must NOT be a whipsaw, NOT in bad hours, NOT in dead-zone MFE
    return f_prior_loss_opposite(f) or f_bad_hours_wide(f) or f_low_mfe(f) or f_slow_confirm(f)


def f_chop_or_whipsaw(f):
    return f_prior_5_losses_ge_2(f) or f_prior_loss_opposite(f)


# Also a stateful daily-halt filter as belt+suspenders
class DailyHaltState:
    def __init__(self, halt_after=1):
        self.halt_after = halt_after
        self.bigs_today = 0
        self.last_day = None
    def should_skip(self, f):
        d = f["entry_time"].strftime("%Y-%m-%d")
        if d != self.last_day:
            self.last_day = d
            self.bigs_today = 0
        return self.bigs_today >= self.halt_after
    def update(self, f):
        if f["main_pnl"] <= -45:  # near fearIdeal=50
            self.bigs_today += 1


def make_combined_with_halt(static_filter, halt_after=1):
    state = DailyHaltState(halt_after)
    def combined(f):
        if state.should_skip(f):
            return True
        if static_filter and static_filter(f):
            return True
        return False
    # Need to update state AFTER each fired trade
    combined._state = state
    return combined


def run_with_filter_and_halt(name, static_filter, halt_after=1):
    """Like run_with_filter but also halts the day after N big losses fire through."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    feats = []
    history = []
    fired = []
    skipped = []
    bigs_today = 0
    last_day = None
    halted = False

    for r in rows:
        f = simulate_with_features(r, history)
        if f is None: continue
        feats.append(f)

        # Day rollover
        d = f["entry_time"].strftime("%Y-%m-%d")
        if d != last_day:
            last_day = d
            bigs_today = 0
            halted = False

        # Apply filters
        if halted or (static_filter and static_filter(f)):
            skipped.append(f)
            continue

        # Fire
        fired.append(f)
        history.append({
            "dir": f["dir_sign"],
            "pnl": f["main_pnl"],
            "close_time": f["confirm_time"] + timedelta(seconds=HORIZON_SEC),
        })
        if f["main_pnl"] <= -45:
            bigs_today += 1
            if bigs_today >= halt_after:
                halted = True

    n_total = len(feats); n_fired = len(fired); n_skipped = len(skipped)
    wins = [f for f in fired if f["win"]]
    losses = [f for f in fired if not f["win"]]
    big_losses = [f for f in fired if f["main_pnl"] <= -30]
    total = sum(f["main_pnl"] for f in fired)
    by_day = defaultdict(float)
    for f in fired:
        by_day[f["entry_time"].strftime("%Y-%m-%d")] += f["main_pnl"]
    return {
        "name": name,
        "fired": n_fired, "skipped": n_skipped,
        "wins": len(wins), "losses": len(losses),
        "wr": len(wins) / max(n_fired, 1) * 100,
        "total": round(total, 2),
        "big_losses": len(big_losses),
        "daily": {d: round(p, 2) for d, p in by_day.items()},
    }


def main():
    print("Running smart-filter scenarios on 64 confirmed probes...")
    print()
    scenarios = [
        ("baseline (no filter)", None),
        ("F1: skip prior-loss+opposite (whipsaw)", f_prior_loss_opposite),
        ("F2: skip prior_5_losses>=3 (chop regime)", f_prior_5_losses_ge_3),
        ("F3: skip prior_5_losses>=2 (chop regime softer)", f_prior_5_losses_ge_2),
        ("F4: skip bad hours narrow (22-23, 04-06)", f_bad_hours),
        ("F4w: skip bad hours wide (19-23, 04-06)", f_bad_hours_wide),
        ("F5: skip ANY prior loss (very strict)", f_prior_loss_any),
        ("F6: F1 + F2 (medium combo)", f_combo_medium),
        ("F8: skip MFE 60-80c dead zone", f_low_mfe),
        ("F9: skip 3-8s confirm dead zone", f_slow_confirm),
        ("F10: F4 + F8 + F9 (feature-based, no chop filter)", f_keep_only_winners),
        ("F11: F1 + F3 (chop OR whipsaw)", f_chop_or_whipsaw),
    ]

    print(f"  {'scenario':<48}{'fired':<7}{'skip':<7}{'WR%':<8}{'total':<11}{'big_L':<7}{'avoided':<10}{'daily':<25}")
    print("  " + "-" * 130)
    for name, pred in scenarios:
        s = run_with_filter(name, pred)
        daily = " | ".join(f"{d[-5:]}:${p:+.0f}" for d, p in sorted(s["daily"].items()))
        print(f"  {s['name']:<48}{s['fired']:<7}{s['skipped']:<7}{s['wr']:<8.1f}${s['total']:+10.2f}  {s['big_losses']:<7}${s['loss_avoided']:+10.2f}  [{daily}]")

    print()
    print("--- with daily big-loss halt added ---")
    halt_scenarios = [
        ("F4 + halt=1", f_bad_hours, 1),
        ("F4w + halt=1", f_bad_hours_wide, 1),
        ("F4 + halt=2", f_bad_hours, 2),
        ("F4w + halt=2", f_bad_hours_wide, 2),
        ("F10 + halt=1", f_keep_only_winners, 1),
        ("F10 + halt=2", f_keep_only_winners, 2),
        ("F11 + halt=1", f_chop_or_whipsaw, 1),
        ("just halt=1 (no other filter)", None, 1),
        ("just halt=2 (no other filter)", None, 2),
    ]
    print(f"  {'scenario':<48}{'fired':<7}{'skip':<7}{'WR%':<8}{'total':<11}{'big_L':<7}{'daily':<25}")
    print("  " + "-" * 120)
    for name, pred, halt in halt_scenarios:
        s = run_with_filter_and_halt(name, pred, halt)
        daily = " | ".join(f"{d[-5:]}:${p:+.0f}" for d, p in sorted(s["daily"].items()))
        print(f"  {s['name']:<48}{s['fired']:<7}{s['skipped']:<7}{s['wr']:<8.1f}${s['total']:+10.2f}  {s['big_losses']:<7}[{daily}]")


if __name__ == "__main__":
    main()
