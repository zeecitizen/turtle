"""backtest_old_turtle_exit.py — test the OLD TURTLE exit stack on our
v3.49 detector against 12 days of real ticks.

From the optimal_settings screenshots (TradingView Pine, April 2026, showed
465/544 = 85% WR backtested):

  Hard SL  override = 15 pips (= 1.5 points on XAU; $15 at 0.10 lots / $60 at 0.40)
  Hard TP  override =  5 pips (= 0.5 points on XAU; $5  at 0.10 lots / $20 at 0.40)
  Invalidation exit = ON  (close when an M1 bar closes back INSIDE the UHV range)

Direct entry — no probe, no main split. Fire ONE position on the just-closed
breakout bar's close, exit on whichever fires first: invalidation / SL / TP.

Variants tested:
  - 0.10 lots (live-scale)
  - 0.40 lots (current v3.49 main scale)
  - With and without the invalidation exit (to isolate its contribution)

Compared to v3.49 baseline (-$2,674 / 4-12 days green).
"""
import csv
import glob
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import (
    COMMON, load_m1_merged, load_ticks, detect_on_bar,
    MAX_UNITS, RATE_LIMIT_S, CONTRACT, MAX_LOOKBACK, MAX_BARS_BACK,
)


PIP_SIZE = 0.10   # XAU: 1 pip = 0.10 price units (15 pips = 1.5 price)


def build_signals_with_uhv(bars):
    """{minute: (side, uhv_high, uhv_low)} — same as multiday but exposed
    here so the replay can know the UHV range for invalidation checks."""
    sig = {}
    for i, b in enumerate(bars):
        if i < MAX_LOOKBACK + 2: continue
        s = detect_on_bar(bars, i, strict=False)   # v3.49 relaxed detector
        sig[b["time"] + timedelta(minutes=1)] = s   # (side, uhv_h, uhv_l)
    return sig


def replay_old_turtle(ticks, bars, sig, lots=0.10,
                      sl_pips=15, tp_pips=5,
                      invalidation=True):
    """One position at a time. Direct entry on breakout candle close.
    SL/TP set as fixed pips. Invalidation: close when an M1 bar closes
    back inside (uhv.low ≤ close ≤ uhv.high)."""
    sl_dist = sl_pips * PIP_SIZE
    tp_dist = tp_pips * PIP_SIZE
    ppp     = lots * CONTRACT
    by_min  = {b["time"]: i for i, b in enumerate(bars)}

    units, last_fire, done = [], None, []

    def pnl_of(u, bid, ask):
        return ((bid - u["e"]) if u["side"] > 0 else (u["e"] - ask)) * ppp

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        cur_min = t.replace(second=0)
        for u in units[:]:
            exit_pnl = exit_why = None
            # SL / TP first (resting stops)
            if u["side"] > 0:
                if bid <= u["sl"]: exit_pnl, exit_why = (u["sl"]-u["e"])*ppp, "sl"
                elif bid >= u["tp"]: exit_pnl, exit_why = (u["tp"]-u["e"])*ppp, "tp"
            else:
                if ask >= u["sl"]: exit_pnl, exit_why = (u["e"]-u["sl"])*ppp, "sl"
                elif ask <= u["tp"]: exit_pnl, exit_why = (u["e"]-u["tp"])*ppp, "tp"
            # Invalidation — only checked once per new M1 bar (when prev bar closes)
            if exit_pnl is None and invalidation and cur_min != u.get("last_chk"):
                u["last_chk"] = cur_min
                prev_min = cur_min - timedelta(minutes=1)
                if prev_min in by_min and prev_min > u["entry_min"]:
                    pb = bars[by_min[prev_min]]
                    if u["uhv_l"] <= pb["close"] <= u["uhv_h"]:
                        # candle closed back inside UHV range → invalidate
                        exit_pnl = pnl_of(u, bid, ask)
                        exit_why = "invalidation"
            if exit_pnl is not None:
                u["pnl"] = exit_pnl; u["why"] = exit_why
                done.append(u); units.remove(u)

        # detect + fire (single position only — closest to the Pine indicator)
        if units: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        s = sig.get(cur_min, (0, 0, 0))
        side, uhv_h, uhv_l = s
        if side == 0: continue
        e = ask if side > 0 else bid
        sl = e - sl_dist if side > 0 else e + sl_dist
        tp = e + tp_dist if side > 0 else e - tp_dist
        units.append({"side": side, "e": e, "sl": sl, "tp": tp,
                      "uhv_h": uhv_h, "uhv_l": uhv_l,
                      "entry_min": cur_min, "last_chk": cur_min})
        last_fire = t

    last = ticks[-1]
    for u in units:
        u["pnl"] = pnl_of(u, last["bid"], last["ask"]); u["why"] = "eod"
        done.append(u)
    return done


def summarize(label, done, nd):
    win_pnls = [u["pnl"] for u in done if u["pnl"] > 0]
    loss_pnls = [u["pnl"] for u in done if u["pnl"] < 0]
    n_w, n_l = len(win_pnls), len(loss_pnls)
    p_win = n_w / (n_w + n_l) if (n_w + n_l) else 0
    w_avg = sum(win_pnls) / n_w if n_w else 0
    l_avg = -sum(loss_pnls) / n_l if n_l else 0
    total = sum(u["pnl"] for u in done)
    ev    = p_win * w_avg - (1 - p_win) * l_avg
    why = {}
    for u in done: why[u["why"]] = why.get(u["why"], 0) + 1
    print(f"  {label:<55}")
    print(f"     n={len(done):<5} P_win={p_win:.3f}  W_avg=${w_avg:.2f}  "
          f"L_avg=${l_avg:.2f}  EV=${ev:+.2f}/trade")
    print(f"     12d total=${total:+.2f}  why={why}")
    return total


def main():
    bars = load_m1_merged()
    sig = build_signals_with_uhv(bars)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"OLD TURTLE exit hypothesis — 12 days real ticks\n")

    configs = [
        ("0.10 lots, 15-pip SL / 5-pip TP, invalidation ON",
            dict(lots=0.10, sl_pips=15, tp_pips=5, invalidation=True)),
        ("0.10 lots, 15-pip SL / 5-pip TP, invalidation OFF (isolate it)",
            dict(lots=0.10, sl_pips=15, tp_pips=5, invalidation=False)),
        ("0.40 lots, 15-pip SL / 5-pip TP, invalidation ON",
            dict(lots=0.40, sl_pips=15, tp_pips=5, invalidation=True)),
        ("0.10 lots, 15-pip SL / 3-pip TP (override-as-shown), invalidation ON",
            dict(lots=0.10, sl_pips=15, tp_pips=3, invalidation=True)),
        ("0.10 lots, TIGHTER 10-pip SL / 5-pip TP, invalidation ON",
            dict(lots=0.10, sl_pips=10, tp_pips=5, invalidation=True)),
        ("0.10 lots, WIDER 20-pip SL / 8-pip TP, invalidation ON",
            dict(lots=0.10, sl_pips=20, tp_pips=8, invalidation=True)),
    ]
    for (label, kw) in configs:
        all_done = []
        nd = 0
        for tf in tick_files:
            ticks = load_ticks(tf)
            if len(ticks) < 100: continue
            nd += 1
            all_done.extend(replay_old_turtle(ticks, bars, sig, **kw))
        summarize(label, all_done, nd)
        print()


if __name__ == "__main__":
    main()
