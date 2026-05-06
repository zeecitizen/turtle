"""
feature_analyzer.py — for each probe, compute features and split by win/loss
to find the strongest predictors of MAIN-trade success.

Goal: identify probe attributes that distinguish winning mains from losing
mains, so we can build pre-trade filters that boost WR from ~75% toward 90%+.

Features computed per probe:
  - hour_utc                 — broker hour-of-day
  - day_of_week              — Mon-Fri index
  - spread_at_confirm        — bid-ask gap at confirm tick (cents)
  - dir_vs_prior_5_wins      — % of last 5 fired mains that were same dir
  - dir_vs_prior_5_losses    — % of last 5 fired mains that were losses (any dir)
  - prior_outcome            — last fired main: win / loss / none
  - prior_dir                — last fired main: same / opposite / none
  - probe_mfe_at_confirm     — favorable move at moment of confirm (cents)
  - probe_mae_before_confirm — adverse move before confirm (cents)
  - time_since_last_main_sec — seconds since last main fired (or inf)
  - confirm_speed_sec        — how fast probe reached confirm threshold
  - body_size_proxy          — entry_price (just for stratification)

For each feature: bin probes, show WR per bin. Largest WR spread = best filter.
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

CONTRACT_SIZE = 100
MAIN_LOTS = 0.40
TRAIL_TRIGGER = 12.0  # using winning-strategy trail
TRAIL_DROP = 4.0
FEAR_IDEAL = 50.0
HORIZON_SEC = 600
PROBE_CONFIRM = 0.45


# ─── Tick reading (cached) ──────────────────────────────────────
_TICK_CACHE = {}

def _load_day(date):
    key = date.strftime("%Y-%m-%d")
    if key in _TICK_CACHE: return _TICK_CACHE[key]
    p = COMMON_DIR / f"shano_ticks_{key}.csv"
    out = []
    if p.exists():
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4: continue
                try:
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    bid = float(parts[2]); ask = float(parts[3])
                    out.append((dt, bid, ask))
                except (ValueError, IndexError):
                    continue
    _TICK_CACHE[key] = out
    return out


def ticks_in_range(t_start, t_end):
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        for tick in _load_day(cur):
            if tick[0] < t_start: continue
            if tick[0] > t_end: break
            out.append(tick)
        cur += timedelta(days=1)
    return out


# ─── Per-probe simulation (returns features + outcome) ──────────
def simulate_with_features(probe_row, prior_history):
    try:
        entry_time = datetime.fromisoformat(probe_row["entry_time"])
        close_time = datetime.fromisoformat(probe_row["close_time"])
        entry_price = float(probe_row["entry_price"])
        dir_sign = 1 if probe_row["dir"] == "buy" else -1
    except (ValueError, KeyError):
        return None

    probe_ticks = ticks_in_range(entry_time, close_time)
    if not probe_ticks: return None

    # Find confirm tick + MAE/MFE before confirm
    confirm_tick = None
    mae_before = 0.0
    confirm_speed = None
    for dt, bid, ask in probe_ticks:
        if dir_sign == 1:
            fav = (bid - entry_price) * 0.01 * CONTRACT_SIZE
            adv = (entry_price - ask) * 0.01 * CONTRACT_SIZE  # NEGATIVE side
        else:
            fav = (entry_price - ask) * 0.01 * CONTRACT_SIZE
            adv = (bid - entry_price) * 0.01 * CONTRACT_SIZE
        if not confirm_tick:
            if adv > mae_before: mae_before = adv
            if fav >= PROBE_CONFIRM:
                confirm_tick = (dt, bid, ask)
                confirm_speed = (dt - entry_time).total_seconds()

    if not confirm_tick:
        return None  # didn't confirm → not relevant for this analysis

    confirm_dt, confirm_bid, confirm_ask = confirm_tick
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid

    # Spread at confirm
    spread_at_confirm = (confirm_ask - confirm_bid) * 100  # cents

    # Simulate main with our trail/fearIdeal
    horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
    main_ticks = ticks_in_range(confirm_dt, horizon_end)
    peak = 0.0; last_profit = 0.0
    for dt, bid, ask in main_ticks:
        if dir_sign == 1:
            profit = (bid - main_entry) * MAIN_LOTS * CONTRACT_SIZE
        else:
            profit = (main_entry - ask) * MAIN_LOTS * CONTRACT_SIZE
        last_profit = profit
        if profit > peak: peak = profit
        if profit <= -FEAR_IDEAL:
            last_profit = profit; break
        if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP:
            last_profit = profit; break
    sim_main_pnl = round(last_profit, 2)
    win = sim_main_pnl > 0

    # Build features from prior_history (last 5 main results)
    last_5 = prior_history[-5:]
    prior_5_same_dir_wins = sum(1 for h in last_5 if h["dir"] == dir_sign and h["pnl"] > 0)
    prior_5_losses = sum(1 for h in last_5 if h["pnl"] <= 0)
    prior = prior_history[-1] if prior_history else None
    prior_outcome = ("win" if prior["pnl"] > 0 else "loss") if prior else "none"
    prior_dir = ("same" if prior["dir"] == dir_sign else "opposite") if prior else "none"
    time_since_last = (entry_time - prior["close_time"]).total_seconds() if prior else 9999
    # Probe MFE at moment of confirm
    probe_mfe_at_confirm = (
        (confirm_bid - entry_price) if dir_sign == 1 else (entry_price - confirm_ask)
    ) * 100  # cents

    return {
        "entry_time": entry_time,
        "dir": probe_row["dir"],
        "dir_sign": dir_sign,
        "entry_price": entry_price,
        "confirm_time": confirm_dt,
        "main_entry_price": main_entry,
        "main_pnl": sim_main_pnl,
        "win": win,
        # Features:
        "hour_utc": entry_time.hour,
        "day_of_week": entry_time.weekday(),
        "spread_at_confirm_cents": round(spread_at_confirm, 1),
        "prior_5_same_dir_wins": prior_5_same_dir_wins,
        "prior_5_losses": prior_5_losses,
        "prior_outcome": prior_outcome,
        "prior_dir": prior_dir,
        "time_since_last_main_sec": int(time_since_last) if time_since_last < 9999 else 9999,
        "confirm_speed_sec": int(confirm_speed),
        "probe_mfe_at_confirm_cents": round(probe_mfe_at_confirm, 1),
        "probe_mae_before_confirm_cents": round(mae_before * 100, 1),
        "entry_price": round(entry_price, 2),
    }


# ─── Run analysis ──────────────────────────────────────────────
def main():
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    print(f"Analyzing {len(rows)} probes...")
    feats = []
    history = []
    for r in rows:
        f = simulate_with_features(r, history)
        if f is None: continue
        feats.append(f)
        # Update history (only mains that confirmed)
        history.append({
            "dir": f["dir_sign"],
            "pnl": f["main_pnl"],
            "close_time": f["confirm_time"] + timedelta(seconds=HORIZON_SEC),  # approx
        })

    if not feats:
        print("no confirmed probes")
        return

    n = len(feats)
    wins = [f for f in feats if f["win"]]
    losses = [f for f in feats if not f["win"]]
    overall_wr = len(wins) / n * 100
    print(f"Confirmed probes: {n}  wins: {len(wins)}  losses: {len(losses)}  overall WR: {overall_wr:.1f}%")
    print()

    # ── Per-feature analysis ──
    def bin_analysis(name, key, bins, labels=None):
        """Bin feats by feature, show WR per bin."""
        groups = defaultdict(list)
        for f in feats:
            v = f[key]
            placed = False
            for i, edge in enumerate(bins):
                if v <= edge:
                    label = labels[i] if labels else f"<= {edge}"
                    groups[label].append(f)
                    placed = True
                    break
            if not placed:
                label = labels[-1] if labels else f"> {bins[-1]}"
                groups[label].append(f)
        print(f"\n  === {name} ===")
        print(f"  {'bin':<25}{'n':<7}{'wins':<7}{'WR%':<8}{'avg P&L':<10}")
        # Preserve label order
        order = labels if labels else [f"<= {e}" for e in bins] + [f"> {bins[-1]}"]
        for label in order:
            grp = groups.get(label, [])
            if not grp: continue
            n_g = len(grp)
            w_g = sum(1 for f in grp if f["win"])
            wr = w_g / n_g * 100
            avg = sum(f["main_pnl"] for f in grp) / n_g
            marker = " <-- HIGH WR" if wr >= overall_wr + 10 else (" <-- LOW WR" if wr <= overall_wr - 10 else "")
            print(f"  {label:<25}{n_g:<7}{w_g:<7}{wr:<8.1f}${avg:+8.2f}{marker}")

    def cat_analysis(name, key):
        groups = defaultdict(list)
        for f in feats:
            groups[str(f[key])].append(f)
        print(f"\n  === {name} ===")
        print(f"  {'value':<25}{'n':<7}{'wins':<7}{'WR%':<8}{'avg P&L':<10}")
        for k in sorted(groups.keys()):
            grp = groups[k]
            n_g = len(grp)
            w_g = sum(1 for f in grp if f["win"])
            wr = w_g / n_g * 100
            avg = sum(f["main_pnl"] for f in grp) / n_g
            marker = " <-- HIGH WR" if wr >= overall_wr + 10 else (" <-- LOW WR" if wr <= overall_wr - 10 else "")
            print(f"  {k:<25}{n_g:<7}{w_g:<7}{wr:<8.1f}${avg:+8.2f}{marker}")

    print("=" * 80)
    print("FEATURE -> WR ANALYSIS - looking for predictors that beat overall WR")
    print("=" * 80)

    bin_analysis("hour_utc (broker)", "hour_utc",
                 [3, 6, 9, 12, 15, 18, 21],
                 ["00-03", "04-06", "07-09", "10-12", "13-15", "16-18", "19-21", "22-23"])
    bin_analysis("spread_at_confirm (cents)", "spread_at_confirm_cents",
                 [15, 25, 40, 60],
                 ["<=15c", "16-25c", "26-40c", "41-60c", ">60c"])
    cat_analysis("prior_outcome", "prior_outcome")
    cat_analysis("prior_dir (vs current probe dir)", "prior_dir")
    bin_analysis("prior_5_same_dir_wins", "prior_5_same_dir_wins",
                 [0, 1, 2, 3],
                 ["0", "1", "2", "3", "4-5"])
    bin_analysis("prior_5_losses", "prior_5_losses",
                 [0, 1, 2, 3],
                 ["0", "1", "2", "3", "4-5"])
    bin_analysis("time_since_last_main_sec", "time_since_last_main_sec",
                 [60, 300, 900, 1800],
                 ["<60s", "60-300s", "5-15min", "15-30min", ">30min"])
    bin_analysis("confirm_speed (probe time to +$0.45)", "confirm_speed_sec",
                 [3, 8, 15, 30],
                 ["<3s", "3-8s", "8-15s", "15-30s", ">30s"])
    bin_analysis("probe_mfe_at_confirm (cents)", "probe_mfe_at_confirm_cents",
                 [50, 60, 80, 120],
                 ["<=50c", "51-60c", "61-80c", "81-120c", ">120c"])
    bin_analysis("probe_mae_before_confirm (cents)", "probe_mae_before_confirm_cents",
                 [10, 25, 50, 100],
                 ["<=10c", "11-25c", "26-50c", "51-100c", ">100c"])
    cat_analysis("dir", "dir")
    cat_analysis("day_of_week (0=Mon)", "day_of_week")

    # ── Combined "danger zone" analysis: overlap of low-WR features ──
    print()
    print("=" * 80)
    print("CANDIDATE FILTERS — combinations of low-WR conditions")
    print("=" * 80)

    candidates = [
        ("prior loss", lambda f: f["prior_outcome"] == "loss"),
        ("prior loss + opposite dir", lambda f: f["prior_outcome"] == "loss" and f["prior_dir"] == "opposite"),
        ("prior loss + same dir", lambda f: f["prior_outcome"] == "loss" and f["prior_dir"] == "same"),
        ("recent has 2+ losses (5)", lambda f: f["prior_5_losses"] >= 2),
        ("recent has 3+ losses (5)", lambda f: f["prior_5_losses"] >= 3),
        ("wide spread >40c", lambda f: f["spread_at_confirm_cents"] > 40),
        ("slow confirm >15s", lambda f: f["confirm_speed_sec"] > 15),
        ("fast confirm <3s", lambda f: f["confirm_speed_sec"] < 3),
        ("high MFE (>80c) at confirm", lambda f: f["probe_mfe_at_confirm_cents"] > 80),
        ("low MFE (<60c) at confirm", lambda f: f["probe_mfe_at_confirm_cents"] <= 60),
        ("MAE before confirm > MFE at confirm", lambda f: f["probe_mae_before_confirm_cents"] > f["probe_mfe_at_confirm_cents"]),
        ("MAE before confirm > 50c", lambda f: f["probe_mae_before_confirm_cents"] > 50),
        ("time since last < 60s", lambda f: f["time_since_last_main_sec"] < 60),
        ("time since last < 30s", lambda f: f["time_since_last_main_sec"] < 30),
    ]

    print(f"  {'condition':<48}{'n':<7}{'wins':<7}{'WR%':<8}{'avg P&L':<10}{'IF SKIP, would-be loss':<8}")
    for name, fn in candidates:
        sub = [f for f in feats if fn(f)]
        if not sub: continue
        n_s = len(sub)
        w_s = sum(1 for f in sub if f["win"])
        wr = w_s / n_s * 100
        avg = sum(f["main_pnl"] for f in sub) / n_s
        avoided = -sum(f["main_pnl"] for f in sub if not f["win"])
        marker = " *** PROMISING ***" if wr <= overall_wr - 15 and n_s >= 5 else ""
        print(f"  {name:<48}{n_s:<7}{w_s:<7}{wr:<8.1f}${avg:+8.2f}  saves=${avoided:+8.2f}{marker}")


if __name__ == "__main__":
    main()
