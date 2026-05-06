"""
filter_backtester.py — comprehensive what-if engine for the Shano strategy.

Replays every probe in probe_shadow_results.csv through the actual tick stream,
applying:
  (a) configurable params: probeConfirm, fearIdeal, trailTrigger, trailDrop, mainLots
  (b) configurable filters that can SKIP trades:
        F1  postBigLossCooldown (skip N main-trades after each fearIdeal hit)
        F2  directionFlipSkip (after K wins same direction, skip next opposite)
        F3  dailyBigLossHalt (after M big losses today, halt for the day)
        F4  timeFilter (skip if hour-of-broker not in allowed set)
        F5  consecLossSkip (skip after N consecutive any-loss)
        F6  spreadFilter (skip if spread at confirm > threshold cents)
        F7  burstPositionSkip (skip if this would be probe N+ in a burst)

Output: per-day stats + grand total. Lets you compare any strategy vs baseline.
"""

from __future__ import annotations
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

CONTRACT_SIZE = 100
MAIN_HORIZON_SEC = 600


# ─────────────────────────────────────────────────────────────────
#  Tick reading (cached per day)
# ─────────────────────────────────────────────────────────────────
_TICK_CACHE: dict = {}


def _load_day_ticks(date: datetime) -> list:
    key = date.strftime("%Y-%m-%d")
    if key in _TICK_CACHE:
        return _TICK_CACHE[key]
    p = COMMON_DIR / f"shano_ticks_{key}.csv"
    if not p.exists():
        _TICK_CACHE[key] = []
        return []
    out = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        next(f, None)  # header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 4:
                continue
            try:
                dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                bid = float(parts[2])
                ask = float(parts[3])
            except (ValueError, IndexError):
                continue
            out.append((dt, bid, ask))
    _TICK_CACHE[key] = out
    return out


def read_ticks_in_range(t_start: datetime, t_end: datetime) -> list:
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        for tick in _load_day_ticks(cur):
            if tick[0] < t_start: continue
            if tick[0] > t_end: break
            out.append(tick)
        cur += timedelta(days=1)
    return out


# ─────────────────────────────────────────────────────────────────
#  Strategy params + filters
# ─────────────────────────────────────────────────────────────────
@dataclass
class StratConfig:
    probeConfirm: float = 0.45
    fearIdeal: float = 50.0
    trailTrigger: float = 8.0
    trailDrop: float = 2.0
    mainLots: float = 0.40
    horizonSec: int = MAIN_HORIZON_SEC

    # Filters (all default OFF unless specified)
    postBigLossCooldown: int = 0           # F1: skip N mains after fearIdeal
    directionFlipSkip: int = 0             # F2: after K wins same dir, skip next opposite
    dailyBigLossHalt: int = 99             # F3: halt for day after M big losses (99 = off)
    timeFilterAllowedHours: tuple = ()     # F4: empty = all hours allowed
    consecLossSkip: int = 0                # F5: skip after N consecutive losses (0=off)
    burstPositionMax: int = 99             # F7: skip if this would be probe N+ in burst
    burstResetGapSec: int = 60             # how long without a win = burst resets

    name: str = "baseline"


# ─────────────────────────────────────────────────────────────────
#  Single-probe simulator with tick walk
# ─────────────────────────────────────────────────────────────────
def _find_confirm_tick(probe_ticks, entry_price, dir_sign, threshold_dollars):
    """First tick where favorable move (in dollars on 0.01 lot) crossed threshold."""
    for dt, bid, ask in probe_ticks:
        if dir_sign == 1:
            fav = (bid - entry_price) * 0.01 * CONTRACT_SIZE
        else:
            fav = (entry_price - ask) * 0.01 * CONTRACT_SIZE
        if fav >= threshold_dollars:
            return (dt, bid, ask)
    return None


def _simulate_main(entry_price, dir_sign, ticks, cfg: StratConfig):
    if not ticks:
        return 0.0, "no_data"
    peak = 0.0
    last_profit = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry_price) * cfg.mainLots * CONTRACT_SIZE
        else:
            profit = (entry_price - ask) * cfg.mainLots * CONTRACT_SIZE
        last_profit = profit
        if profit > peak:
            peak = profit
        if profit <= -cfg.fearIdeal:
            return round(profit, 2), f"fearIdeal"
        if peak >= cfg.trailTrigger and (peak - profit) >= cfg.trailDrop:
            return round(profit, 2), f"trail"
    return round(last_profit, 2), "horizon_end"


def _simulate_probe(probe_row, cfg: StratConfig):
    """Returns (sim_main_pnl, exit_reason, did_confirm) or (0, 'skipped_no_confirm', False)."""
    try:
        entry_time = datetime.fromisoformat(probe_row["entry_time"])
        close_time = datetime.fromisoformat(probe_row["close_time"])
        entry_price = float(probe_row["entry_price"])
        dir_sign = 1 if probe_row["dir"] == "buy" else -1
    except (ValueError, KeyError):
        return None

    probe_ticks = read_ticks_in_range(entry_time, close_time)
    if not probe_ticks:
        return None

    confirm = _find_confirm_tick(probe_ticks, entry_price, dir_sign, cfg.probeConfirm)
    if not confirm:
        return (0.0, "no_confirm", False, entry_time, dir_sign, None)

    confirm_dt, confirm_bid, confirm_ask = confirm
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    main_horizon_end = confirm_dt + timedelta(seconds=cfg.horizonSec)
    main_ticks = read_ticks_in_range(confirm_dt, main_horizon_end)

    pnl, reason = _simulate_main(main_entry, dir_sign, main_ticks, cfg)
    return (pnl, reason, True, confirm_dt, dir_sign, main_entry)


# ─────────────────────────────────────────────────────────────────
#  Filter state machine — runs across all probes chronologically
# ─────────────────────────────────────────────────────────────────
@dataclass
class RunState:
    cooldown_remaining: int = 0
    consec_same_dir_wins: int = 0
    consec_same_dir: int = 0  # +1 = buy streak, -1 = sell streak
    consec_losses: int = 0
    big_losses_today: int = 0
    today_date: Optional[str] = None
    halted_today: bool = False
    last_win_time: Optional[datetime] = None
    burst_count: int = 0


def run_strategy(rows, cfg: StratConfig):
    state = RunState()
    main_results = []      # (date, time, dir, pnl, reason, confirmed, skipped_reason)
    no_confirm = 0

    for row in rows:
        sim = _simulate_probe(row, cfg)
        if sim is None:
            continue
        pnl, reason, confirmed, when, dir_sign, main_entry = sim

        # Daily reset
        when_date = when.strftime("%Y-%m-%d")
        if state.today_date != when_date:
            state.today_date = when_date
            state.halted_today = False
            state.big_losses_today = 0

        if not confirmed:
            no_confirm += 1
            continue

        # ── Apply filters ──
        skip_reason = None

        # F4: time filter
        if cfg.timeFilterAllowedHours:
            if when.hour not in cfg.timeFilterAllowedHours:
                skip_reason = f"time({when.hour})"

        # F3: daily big-loss halt
        if not skip_reason and state.halted_today:
            skip_reason = "halted_today"

        # F1: post-bigloss cooldown
        if not skip_reason and state.cooldown_remaining > 0:
            skip_reason = f"cooldown({state.cooldown_remaining})"

        # F5: consecutive losses skip
        if not skip_reason and cfg.consecLossSkip > 0 and state.consec_losses >= cfg.consecLossSkip:
            skip_reason = f"consec_loss({state.consec_losses})"

        # F2: direction-flip skip — if streak of K wins in opposite direction, skip
        if not skip_reason and cfg.directionFlipSkip > 0:
            current_streak_dir = 1 if state.consec_same_dir > 0 else -1 if state.consec_same_dir < 0 else 0
            streak_size = abs(state.consec_same_dir)
            if streak_size >= cfg.directionFlipSkip and current_streak_dir != dir_sign and state.consec_same_dir_wins >= cfg.directionFlipSkip:
                skip_reason = f"flip_after_{streak_size}_wins"

        # F7: burst position
        if not skip_reason and cfg.burstPositionMax < 99:
            # Reset burst if gap > burstResetGapSec from last win
            if state.last_win_time and (when - state.last_win_time).total_seconds() > cfg.burstResetGapSec:
                state.burst_count = 0
            if state.burst_count >= cfg.burstPositionMax:
                skip_reason = f"burst_{state.burst_count}"

        if skip_reason:
            main_results.append((when, dir_sign, 0.0, "SKIPPED:" + skip_reason, False))
            # decrement cooldown even when skipping
            if state.cooldown_remaining > 0:
                state.cooldown_remaining -= 1
            continue

        # ── Trade actually fired — record outcome ──
        main_results.append((when, dir_sign, pnl, reason, True))

        # Update state
        if pnl > 0:
            if dir_sign == 1 and state.consec_same_dir > 0:
                state.consec_same_dir += 1
                state.consec_same_dir_wins += 1
            elif dir_sign == -1 and state.consec_same_dir < 0:
                state.consec_same_dir -= 1
                state.consec_same_dir_wins += 1
            else:
                state.consec_same_dir = dir_sign
                state.consec_same_dir_wins = 1
            state.consec_losses = 0
            state.last_win_time = when
            state.burst_count += 1
        else:
            state.consec_losses += 1
            state.consec_same_dir = 0
            state.consec_same_dir_wins = 0
            state.burst_count = 0
            if pnl <= -cfg.fearIdeal * 0.85:  # treat near-fearIdeal as big loss
                state.big_losses_today += 1
                state.cooldown_remaining = cfg.postBigLossCooldown
                if state.big_losses_today >= cfg.dailyBigLossHalt:
                    state.halted_today = True

        # Decrement cooldown after a real trade (not a skip)
        if state.cooldown_remaining > 0:
            state.cooldown_remaining -= 1

    return main_results, no_confirm


# ─────────────────────────────────────────────────────────────────
#  Aggregation
# ─────────────────────────────────────────────────────────────────
def summarize(results):
    fired = [r for r in results if r[4]]  # confirmed and not skipped
    skipped = [r for r in results if not r[4]]
    wins = [r for r in fired if r[2] > 0]
    losses = [r for r in fired if r[2] <= 0]
    big_losses = [r for r in fired if r[2] <= -30]

    total = sum(r[2] for r in fired)
    skipped_pnl = sum(r[2] for r in skipped) if skipped else 0  # always 0 for our skip logic

    by_day = {}
    for r in fired:
        d = r[0].strftime("%Y-%m-%d")
        by_day.setdefault(d, []).append(r[2])
    daily = {d: round(sum(p), 2) for d, p in by_day.items()}

    return {
        "fired": len(fired),
        "skipped": len(skipped),
        "wins": len(wins),
        "losses": len(losses),
        "big_losses": len(big_losses),
        "total": round(total, 2),
        "wr": round(len(wins) / max(len(fired), 1) * 100, 1),
        "avg_win": round(sum(r[2] for r in wins) / max(len(wins), 1), 2),
        "avg_loss": round(sum(r[2] for r in losses) / max(len(losses), 1), 2),
        "max_loss": round(min((r[2] for r in losses), default=0), 2),
        "daily": daily,
    }


def load_probes():
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))
    return rows


# ─────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────
def fmt_summary(name, s):
    daily_str = " | ".join(f"{d}:${p:+.0f}" for d, p in sorted(s["daily"].items()))
    return (f"{name:<35}  fired={s['fired']:>3}  skipped={s['skipped']:>3}  "
            f"WR={s['wr']:>5.1f}%  total=${s['total']:+8.2f}  "
            f"avg+=${s['avg_win']:>5.2f}  avg-=${s['avg_loss']:>6.2f}  "
            f"big_L={s['big_losses']:>2}  daily=[{daily_str}]")


def compare(rows, configs):
    print(f"\nLoaded {len(rows)} probes.\n")
    print("=" * 200)
    for cfg in configs:
        results, _ = run_strategy(rows, cfg)
        s = summarize(results)
        print(fmt_summary(cfg.name, s))
    print("=" * 200)


def main():
    rows = load_probes()
    if len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "--baseline":
        compare(rows, [StratConfig(name="baseline (current live)")])
        return
    # default: just run baseline
    compare(rows, [StratConfig(name="baseline pc=0.45 fi=50")])


if __name__ == "__main__":
    main()
