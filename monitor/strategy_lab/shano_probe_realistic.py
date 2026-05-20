"""shano_probe_realistic.py — HONEST validation of the Shano-probe overlay.

Fixes the optimism in shano_probe_overlay.py:
  * When the probe confirms, we ENTER AT THE CONFIRMED PRICE (entry_ref ± confirm,
    paying real spread via ask/bid), NOT the signal price.
  * Baseline and probe both run through the SAME per-signal tick engine (enter at
    first ask/bid after fire, bracket exit on real bid/ask), so the only difference
    is the probe gate + the realistic delayed entry. Clean apples-to-apples.
  * Walk-forward (train 6d / test 6d) on the best S3 & NSND configs.

SL/TP are the EA's structural PRICE LEVELS (unchanged) — entering later just means
less reward / more SL room, exactly as in live trading.
"""
import sys, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import stats
from shano_probe_overlay import build_cache, gen_sigs

CONTRACT = 100.0
LOTS = 0.02


def replay_one(ticks, sig, ppp, probe=None):
    """Per-signal: optional probe gate, realistic entry at confirm price, bracket exit.
    Returns pnl float or None if skipped (probe failed / never entered)."""
    ft = sig["fire_time"]; side = sig.get("side", +1)
    sl, tp = sig["sl"], sig["tp"]
    entry_ref = None; actual_entry = None; probe_deadline = None
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        if t < ft: continue
        if entry_ref is None:
            entry_ref = ask if side > 0 else bid
            if probe: probe_deadline = t.timestamp() + probe[2]
        # ---- phase 1: waiting to enter ----
        if actual_entry is None:
            if probe is None:
                actual_entry = ask if side > 0 else bid   # enter immediately (baseline)
            else:
                confirm, fail, _ = probe
                if t.timestamp() > probe_deadline: return None      # no momentum
                if side > 0:
                    if bid <= entry_ref - fail: return None          # went against
                    if ask >= entry_ref + confirm: actual_entry = ask  # confirmed -> enter now
                else:
                    if ask >= entry_ref + fail: return None
                    if bid <= entry_ref - confirm: actual_entry = bid
            if actual_entry is None:
                continue
            # don't also exit on the very same tick; continue to next
            continue
        # ---- phase 2: in position, bracket exit on real bid/ask ----
        if side > 0:
            if bid <= sl: return (sl - actual_entry) * ppp
            if bid >= tp: return (tp - actual_entry) * ppp
        else:
            if ask >= sl: return (actual_entry - sl) * ppp
            if ask <= tp: return (actual_entry - tp) * ppp
    # EOD close if still open
    if actual_entry is not None and ticks:
        last = ticks[-1]
        return (last["bid"] - actual_entry) * ppp if side > 0 else (actual_entry - last["ask"]) * ppp
    return None


def run(cache, days, refs, ea, probe=None):
    ppp = LOTS * CONTRACT
    pnls = []
    for day in days:
        if day not in cache: continue
        c = cache[day]
        for sig in gen_sigs(c, ea, *refs):
            p = replay_one(c["ticks"], sig, ppp, probe)
            if p is not None: pnls.append(p)
    return [{"pnl": p} for p in pnls]


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<34} no trades"); return None
    ev = r["pwin"]*r["w_avg"]-(1-r["pwin"])*r["l_avg"]
    print(f"  {label:<34} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% TOT=${r['total']:>+7.1f} EV=${ev:+6.2f}")
    return r


def main():
    print("Loading 12d...")
    cache, h1, m5_bull, h1_bull, h1_bear, m15 = build_cache()
    refs = (h1, m5_bull, h1_bull, h1_bear, m15)
    days = sorted(cache.keys()); mid=len(days)//2
    train, test = days[:mid], days[mid:]
    print(f"  {len(cache)} days. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    plans = [
        ("S3", None, "baseline (realistic entry)"),
        ("S3", (0.30,0.30,30), "probe 0.30/0.30/30s"),
        ("S3", (0.45,0.45,60), "probe 0.45/0.45/60s"),
        ("NSND", None, "baseline (realistic entry)"),
        ("NSND", (0.45,0.45,60), "probe 0.45/0.45/60s"),
        ("NSND", (0.30,0.30,30), "probe 0.30/0.30/30s"),
    ]
    cur_ea=None
    for ea, probe, label in plans:
        if ea != cur_ea:
            print("="*78); print(f"  {ea} — realistic entry + walk-forward"); print("="*78)
            print("  FULL 12d:"); cur_ea=ea
        rfull = rpt("   "+label, run(cache, days, refs, ea, probe))
        rtr = rpt("     TRAIN", run(cache, train, refs, ea, probe))
        rte = rpt("     TEST(OOS)", run(cache, test, refs, ea, probe))
        print()


if __name__ == "__main__":
    main()
