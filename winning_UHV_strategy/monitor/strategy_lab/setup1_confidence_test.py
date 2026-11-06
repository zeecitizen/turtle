"""setup1_confidence_test.py — hybrid: Shano probe entry + Setup 1 M1 as confidence multiplier.

Model:
  - Probe still fires from PineConnector (Shano-Zee BIG STACK applies all filters)
  - At probe-confirm moment, check if Setup 1 M1 was matching in last K M1 bars
  - If yes → full descending ladder 0.70→0.10, max 7 bursts (high confidence)
  - If no → smaller chain (e.g., constant 0.30, max 3 bursts) — low confidence
  - Optional HARD-GATE variant: no Setup 1 = no trade

Setup 1 (M1 buys-only, the strongest variant):
  - Find UHV red M1 bar in last N
  - Sweep: intermediate bar broke its low
  - Trigger: green M1 bar that closed above UHV high
  - Direction: BUY (sells underperformed)
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas, compute_ema,
)

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def aggregate_to_tf(bars_1m, minutes):
    if minutes == 1: return list(bars_1m)
    out = []
    cur = None; o = h = l = c = None; v = 0
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c, b_v = b[0], b[1], b[2], b[3], b[4], b[5]
        anchor = dt.minute - (dt.minute % minutes)
        bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur is None:
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        elif bm != cur:
            out.append((cur, o, h, l, c, v))
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c; v += b_v
    if cur is not None: out.append((cur, o, h, l, c, v))
    return out


def trend_at(when, ema_f, ema_s, bar_idx_2m, tf=2):
    anchor = when.minute - (when.minute % tf)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_2m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf * d)
            idx = bar_idx_2m.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_f[idx]; s = ema_s[idx]; fp = ema_f[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def get_uhv_bar(when, bars_1m, bar_idx_1m, lookback=20):
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None, None
    trigger_idx = idx - 1
    lookback_bars = bars_1m[max(0, trigger_idx - lookback):trigger_idx]
    if not lookback_bars: return None, None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    uhv_global_idx = bars_1m.index(uhv)
    return uhv, uhv_global_idx, trigger_idx


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback=20):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv is None: return False
    if dir_sign == 1 and price <= uhv[2]: return False
    if dir_sign == -1 and price >= uhv[3]: return False
    return True


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
              fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              uhv_lookback=20, horizon_sec=HORIZON_SEC):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign):
    start = max(0, idx - lookback)
    cands = []
    for i in range(start, idx):
        bar = bars_1m[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: cands.append(i)
        elif dir_sign == -1 and is_green: cands.append(i)
    if not cands: return None
    return max(cands, key=lambda i: bars_1m[i][5])


def setup1_at_m1(bars_1m, idx, dir_sign, lookback=10):
    """Setup 1 match at M1 bar idx (treating idx as the trigger bar)."""
    if idx < 3: return False
    uhv_idx = find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = bars_1m[uhv_idx]
    swept = False
    for i in range(uhv_idx + 1, idx):
        if dir_sign == 1 and bars_1m[i][3] < uhv[3]: swept = True; break
        if dir_sign == -1 and bars_1m[i][2] > uhv[2]: swept = True; break
    if not swept: return False
    cur = bars_1m[idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[4] <= uhv[2]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[4] >= uhv[3]: return False
    return True


def setup1_active_recently(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=5, setup_lookback=10):
    """Was Setup 1 matching on any M1 bar in the last `lookback_bars` minutes before probe?"""
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return False
    start = max(setup_lookback, idx - lookback_bars)
    for i in range(start, idx + 1):
        if setup1_at_m1(bars_1m, i, dir_sign, setup_lookback):
            return True
    return False


def run(label, *, full_chain_lots_start=0.70, full_chain_lots_step=-0.10, full_chain_max_burst=7,
         small_chain_lots_start=0.30, small_chain_lots_step=-0.05, small_chain_max_burst=3,
         hard_gate=False, setup1_lookback_bars=5, setup1_pattern_lookback=10):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    chains = []
    full_count = 0; small_count = 0
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Standard Shano-Zee filters (same as BIG STACK base)
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # ── Setup 1 confidence check ──
        setup1_active = setup1_active_recently(entry_time, dir_sign, bars_1m, bar_idx_1m,
                                                setup1_lookback_bars, setup1_pattern_lookback)
        if hard_gate and not setup1_active:
            continue  # skip if no Setup 1 in HARD-GATE mode

        # Pick chain size based on confidence
        if setup1_active:
            ls, st, mb = full_chain_lots_start, full_chain_lots_step, full_chain_max_burst
            ladder_max = full_chain_lots_start
            full_count += 1
        else:
            ls, st, mb = small_chain_lots_start, small_chain_lots_step, small_chain_max_burst
            ladder_max = small_chain_lots_start
            small_count += 1

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=mb,
                          ladder_start=ls, ladder_step=st, ladder_max=ladder_max,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append((entry_time, dir_sign, chain, setup1_active))

    n = len(chains); all_mains = [m for _, _, c, _ in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for _, _, c, _ in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    full_chains = sum(1 for _, _, _, s in chains if s)
    small_chains = n - full_chains
    full_pnl = sum(sum(m[1] for m in c) for _, _, c, s in chains if s)
    small_pnl = sum(sum(m[1] for m in c) for _, _, c, s in chains if not s)
    print(f"  {label:<70}chains={n:<3}  WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}")
    print(f"    setup1_active: {full_chains} chains, ${full_pnl:+.2f}  | no setup1: {small_chains} chains, ${small_pnl:+.2f}")


print("=" * 200)
print("HYBRID: Shano probe entry + Setup 1 M1 as CONFIDENCE FLAG")
print("Probe + Shano-Zee BIG STACK filters apply. Setup 1 detected on M1 in last K bars before probe-time.")
print("Sizing: full = descending 0.70->0.10 max 7  | small = descending 0.30->0.10 max 3 (when no Setup 1)")
print("=" * 200)
print()

print("--- BASELINE for reference (current Shano-Zee BIG STACK = same chain regardless) ---")
run("Always full descending (no Setup 1 distinction)",
    full_chain_lots_start=0.70, full_chain_max_burst=7,
    small_chain_lots_start=0.70, small_chain_lots_step=-0.10, small_chain_max_burst=7)

print()
print("--- OPTION C: Setup 1 confidence flag (lookback=5 m1 bars) ---")
run("Full when Setup 1, small (0.30->0.10 max 3) when no Setup 1",
    full_chain_lots_start=0.70, full_chain_max_burst=7,
    small_chain_lots_start=0.30, small_chain_lots_step=-0.05, small_chain_max_burst=3,
    setup1_lookback_bars=5)
run("Full when Setup 1, MICRO (0.10 max 1) when no Setup 1",
    small_chain_lots_start=0.10, small_chain_lots_step=0, small_chain_max_burst=1,
    setup1_lookback_bars=5)

print()
print("--- VARYING setup1 lookback (how many M1 bars to look back for setup match) ---")
for lb in [3, 5, 10, 15, 20]:
    run(f"Setup 1 lookback={lb} bars (full vs small 0.30/3)",
        small_chain_lots_start=0.30, small_chain_lots_step=-0.05, small_chain_max_burst=3,
        setup1_lookback_bars=lb)

print()
print("--- HARD GATE: Setup 1 REQUIRED (no Setup 1 = no trade) ---")
for lb in [3, 5, 10, 15]:
    run(f"HARD GATE Setup 1 lookback={lb} (full chain only when matched)",
        hard_gate=True, setup1_lookback_bars=lb)

print()
print("--- ASYMMETRIC: smaller chains for no-setup ---")
run("Full+ (0.80->0.10 max 8) vs small (0.20 max 2)",
    full_chain_lots_start=0.80, full_chain_lots_step=-0.10, full_chain_max_burst=8,
    small_chain_lots_start=0.20, small_chain_lots_step=-0.05, small_chain_max_burst=2)
