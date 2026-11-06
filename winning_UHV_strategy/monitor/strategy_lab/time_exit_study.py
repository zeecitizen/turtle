"""time_exit_study.py — is the harvest dimension TIME, not distance? (Zee 2026-08-06)

"test from 1 tick onwards till X minutes, where X is the avg hold of Feb 11.
maybe 0.2 is the noise floor but maybe we need to count in seconds/minutes."

Method: for every detected setup whose breakout moment lands in a clean tick zone,
walk the real ticks and record the favourable move at checkpoints from 1 tick to
10 minutes. Two exit families:
  A) PURE TIME EXIT: close at market after exactly T (whatever the P&L)
  B) TIME + GHOST:   same, but bail at -1.0pt if it hits first (the realistic ghost)
Costs shown at Raw (0.07pt) and Standard (0.20pt).

Benchmarks from the Feb-11 broker report (69 positions, +835 EUR, 94% WR):
median hold 65s · mean hold computed below · median win +1.01pt.
"""
from __future__ import annotations
import re, csv, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timezone, timedelta
from bisect import bisect_left
from pathlib import Path

sys.path.insert(0, "monitor"); sys.path.insert(0, "monitor/strategy_lab")
import oanda_live_matcher as M
import build_entry_review_m5 as B
for k, v in M.CFG.items(): setattr(B, k, v)

HERE = Path(__file__).parent
OUT = HERE / "_TIME_EXIT_STUDY.md"
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

# ── Feb-11 hold-time benchmark (from the broker report, seconds) ──
FEB11_HOLDS = [911,910,99,99,40,39,86,86,116,116,116,6,10,10,24,24,24,66,65,64,
               15,15,1003,156,155,154,154,154,255,254,254,1491,1491,1491,1490,1490,1490,
               9,9,9,9,22,22,21,439,439,438,438,6,6,6,5,44,44,44,572,572,571,286,286,
               60,60,11,4,4,55,55,14,13]

TICK_PAT = re.compile(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}),\d+,(\d{4}\.\d{3}),(\d{4}\.\d{3})")
CHECKPOINTS = [("1 tick", None), ("5s", 5), ("10s", 10), ("20s", 20), ("30s", 30),
               ("45s", 45), ("65s*", 65), ("2min", 120), ("3min", 180),
               ("5min", 300), ("10min", 600)]


def load_ticks(day):
    p = COMMON / f"shano_ticks_{day}.csv"
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8", errors="ignore")
    out = []
    for m in TICK_PAT.finditer(raw):
        bid, ask = float(m.group(2)), float(m.group(3))
        if 3900 < bid < 4400 and 0 <= ask - bid < 2.0:
            out.append((datetime.strptime(m.group(1), "%Y.%m.%d %H:%M:%S"),
                        (bid + ask) / 2))
    return out


def load_bars():
    seen = {}
    for src in (HERE / "oanda_m1_history.csv", COMMON / "oanda_m1.csv"):
        try:
            for r in csv.DictReader(open(src, encoding="utf-8")):
                seen[r["time_unix"]] = r
        except FileNotFoundError:
            pass
    bars = []
    for k in sorted(seen, key=int):
        r = seen[k]
        bars.append(B.Bar(datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc)
                          .replace(tzinfo=None),
                          float(r["open"]), float(r["high"]), float(r["low"]),
                          float(r["close"]), int(float(r["volume"]))))
    return bars


def run():
    print(f"Feb-11 benchmark: median hold {statistics.median(FEB11_HOLDS):.0f}s · "
          f"mean {statistics.mean(FEB11_HOLDS):.0f}s · "
          f"75th pct {sorted(FEB11_HOLDS)[int(len(FEB11_HOLDS)*0.75)]}s")
    bars = load_bars()
    setups = list({(s["open_t"], s["side"]): s for s in B.detect_full(bars)}.values())
    print(f"bars {len(bars)} · detected setups {len(setups)}")

    ticks_by_day = {}
    profiles = []          # per setup: list of favor at each checkpoint (pure time)
    ghosted = []           # same but ghost-interrupted at -1.0
    for s in setups:
        day = (s["open_t"] + timedelta(hours=3)).strftime("%Y-%m-%d")
        if day not in ticks_by_day:
            ticks_by_day[day] = load_ticks(day)
        ticks = ticks_by_day[day]
        if len(ticks) < 1000:
            continue
        t0 = s["open_t"] + timedelta(hours=3)
        keys = [t[0] for t in ticks]
        j0 = bisect_left(keys, t0)
        if j0 < 10 or j0 >= len(ticks) - 500:
            continue
        if abs((keys[j0] - t0).total_seconds()) > 120:
            continue
        entry = ticks[j0][1]
        buy = s["side"] == "BUY"
        prof_row, ghost_row = [], []
        ghost_hit_at = None
        ci = 0
        favor_1tick = ((ticks[j0 + 1][1] - entry) if buy else (entry - ticks[j0 + 1][1]))
        for j in range(j0 + 1, len(ticks)):
            el = (keys[j] - keys[j0]).total_seconds()
            fav = (ticks[j][1] - entry) if buy else (entry - ticks[j][1])
            if ghost_hit_at is None and fav <= -1.0:
                ghost_hit_at = el
            while ci < len(CHECKPOINTS):
                name, T = CHECKPOINTS[ci]
                if T is None:                       # 1 tick
                    prof_row.append(favor_1tick)
                    ghost_row.append(favor_1tick)
                    ci += 1
                    continue
                if el >= T:
                    prof_row.append(fav)
                    ghost_row.append(-1.0 if (ghost_hit_at is not None and ghost_hit_at <= T) else fav)
                    ci += 1
                else:
                    break
            if ci >= len(CHECKPOINTS):
                break
        if ci >= len(CHECKPOINTS):
            profiles.append(prof_row)
            ghosted.append(ghost_row)

    n = len(profiles)
    print(f"setups with full 10-min tick coverage: {n}\n")
    lines = ["# TIME-EXIT STUDY — is the harvest dimension time, not distance?", "",
             f"Setups: {n} (tick-verified breakout moments) · "
             f"Feb-11 benchmark: median hold 65s, mean "
             f"{statistics.mean(FEB11_HOLDS):.0f}s, median win +1.01pt", "",
             "| hold | mean pts | median | WR>0 | EV Raw | EV Std | ghost-EV Raw |",
             "|---|---|---|---|---|---|---|"]
    hdr = f"{'hold':>7s} {'mean':>7s} {'med':>7s} {'WR':>5s} {'EVraw':>7s} {'EVstd':>7s} {'ghostEV':>8s}"
    print(hdr)
    best = None
    for i, (name, T) in enumerate(CHECKPOINTS):
        col = [p[i] for p in profiles]
        gcol = [g[i] for g in ghosted]
        mean = statistics.mean(col); med = statistics.median(col)
        wr = sum(1 for x in col if x > 0) / n
        ev_raw = mean - 0.07; ev_std = mean - 0.20
        gev = statistics.mean(gcol) - 0.07
        star = ""
        if best is None or gev > best[1]:
            best = (name, gev)
        print(f"{name:>7s} {mean:+7.3f} {med:+7.3f} {wr*100:4.0f}% {ev_raw:+7.3f} {ev_std:+7.3f} {gev:+8.3f}")
        lines.append(f"| {name} | {mean:+.3f} | {med:+.3f} | {wr*100:.0f}% | "
                     f"{ev_raw:+.3f} | {ev_std:+.3f} | {gev:+.3f} |")
    lines += ["", f"**Best time-exit (ghost-protected, Raw costs): {best[0]} "
              f"(EV {best[1]:+.3f} pt/click)**", "",
              "*65s = the Feb-11 median hold. Ghost-EV = bail at −1.0pt if hit first "
              "(the realistic ghost), else exit at the time mark.*"]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nBest (ghost-protected @Raw): {best[0]}  EV {best[1]:+.3f} pt/click")
    print(f"written -> {OUT}")


if __name__ == "__main__":
    run()
