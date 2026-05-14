"""backtest_v349_ticks.py — full tick-by-tick replay of UhvSweepExhaustion
v3.49 (Shano probe-to-trade) on TODAY's real bid/ask ticks, run repeatedly
to sweep the main-trade exit params and find the best bounded-risk control.

Data:
  shano_ticks_2026-05-14.csv : real bid/ask ticks (broker time)
  rev_eng_m1_recent.csv      : M1 OHLCV bars (detector reads just-closed bar)

Each replay is the COMPLETE v3.49 state machine with the given exit params,
so slot timing / which units fire is correct for that param set.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS  = COMMON / "shano_ticks_2026-05-14.csv"
M1     = COMMON / "rev_eng_m1_recent.csv"

PROBE_LOTS, REAL_LOTS = 0.01, 0.40
PROBE_FLOOR = 40.0
MAX_UNITS, RATE_LIMIT_S, CONTRACT = 2, 2, 100.0
MAX_LOOKBACK, MAX_BARS_BACK = 60, 60


def load_m1():
    bars = []
    with open(M1, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            bars.append({"time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                         "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars


def load_ticks():
    out = []
    with open(TICKS, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            out.append({"t": datetime.strptime(r["ts_broker"], "%Y.%m.%d %H:%M:%S"),
                        "bid": float(r["bid"]), "ask": float(r["ask"])})
    return out


def detect_on_bar(bars, idx_bo):
    bo = bars[idx_bo]
    if bo["close"] > bo["open"]:
        ui, uv = -1, -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["high"] >= bo["close"]: continue
            if c["close"] < c["open"] and c["vol"] > uv: ui, uv = k, c["vol"]
        if ui < 0 or (idx_bo - ui) > MAX_BARS_BACK: return 0
        if bo["close"] <= bars[ui]["high"]: return 0
        return +1
    if bo["close"] < bo["open"]:
        ui, uv = -1, -1
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["low"] <= bo["close"]: continue
            if c["close"] > c["open"] and c["vol"] > uv: ui, uv = k, c["vol"]
        if ui < 0 or (idx_bo - ui) > MAX_BARS_BACK: return 0
        if bo["close"] >= bars[ui]["low"]: return 0
        return -1
    return 0


def build_signals(bars):
    sig = {}
    for i, b in enumerate(bars):
        if i < MAX_LOOKBACK + 2: continue
        sig[b["time"] + timedelta(minutes=1)] = detect_on_bar(bars, i)
    return sig


def replay(ticks, sig_for_minute, main_floor, main_bank, main_drop,
           pg_secs=0, pg_peak=0.0, pg_loss=0.0,
           probe_confirm=1.0, confirm_hold_s=0):
    """Full v3.49 replay with the given params. probe_confirm = recovery $
    level to fire the main; confirm_hold_s = probe must STAY >= confirm for
    this many seconds before the main fires (0 = fire instantly on touch)."""
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
                    # confirm-hold: probe must STAY >= confirm for confirm_hold_s
                    if confirm_hold_s > 0:
                        if u.get("confirm_since") is None:
                            u["confirm_since"] = t
                        elif (t - u["confirm_since"]).total_seconds() >= confirm_hold_s:
                            u["state"] = "TRADING"; u["me"] = ask if u["side"] > 0 else bid
                            u["pcp"] = pp; u["peak"] = 0.0; u["locked"] = 0.0
                            u["mopen"] = t
                    else:
                        u["state"] = "TRADING"; u["me"] = ask if u["side"] > 0 else bid
                        u["pcp"] = pp; u["peak"] = 0.0; u["locked"] = 0.0
                        u["mopen"] = t
                else:
                    u["confirm_since"] = None   # fell back below confirm — reset the hold
            else:
                pnl = m_pnl(u, bid, ask)
                if pnl > u["peak"]: u["peak"] = pnl
                es = int((t - u["mopen"]).total_seconds())
                exit_pnl = exit_why = None
                # peak-guard early cut
                if pg_secs > 0 and es >= pg_secs and u["peak"] < pg_peak and pnl <= -pg_loss:
                    exit_pnl, exit_why = pnl, "peak_guard"
                # roll-over trail
                if exit_pnl is None:
                    if u["peak"] >= main_bank:
                        tgt = u["peak"] - main_drop
                        if tgt > u["locked"]: u["locked"] = tgt
                    if u["locked"] > 0 and pnl <= u["locked"]:
                        exit_pnl, exit_why = u["locked"], "rollover"
                # bounded floor
                if exit_pnl is None and pnl <= -main_floor:
                    exit_pnl, exit_why = -main_floor, "main_floor"
                if exit_pnl is not None:
                    u["pnl"] = u["pcp"] + exit_pnl; u["why"] = exit_why
                    done.append(u); units.remove(u)
        # detect + fire
        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        s = sig_for_minute.get(t.replace(second=0), 0)
        if s == 0: continue
        units.append({"state": "PROBING", "side": s,
                      "pe": ask if s > 0 else bid, "open_t": t})
        last_fire = t

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
    by = {}
    for u in done:
        by[u["why"]] = by.get(u["why"], 0) + 1
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr, by=by)


def fmt_by(by):
    order = ["rollover", "peak_guard", "main_floor", "probe_floor", "probe_eod", "main_eod"]
    return " ".join(f"{k}={by[k]}" for k in order if k in by)


def main():
    bars = load_m1()
    ticks = load_ticks()
    sig = build_signals(bars)
    print(f"{len(ticks)} ticks, {ticks[0]['t']:%H:%M}-{ticks[-1]['t']:%H:%M} broker, 2026-05-14\n")

    print("=" * 84)
    r = replay(ticks, sig, 150, 8, 3)
    print(f"v3.49 BASELINE (floor=$150 bank=$8 drop=$3, no peak-guard)")
    print(f"  NET ${r['total']:+.2f}  {r['wins']}W/{r['losses']}L ({r['wr']:.0f}%)  units={r['n']}  [{fmt_by(r['by'])}]")
    print("=" * 84)

    print("\nSWEEP 1 — main floor level (bank=$8 drop=$3):")
    print(f"  {'floor':<9} {'NET':<12} {'WR':<7} {'breakdown'}")
    for fl in (8, 10, 12, 15, 20, 25, 30, 40, 60, 100, 150):
        r = replay(ticks, sig, fl, 8, 3)
        print(f"  -${fl:<7} ${r['total']:<+10.2f} {r['wr']:<5.0f}%  [{fmt_by(r['by'])}]")

    print("\nSWEEP 2 — peak-guard early cut (floor=$150 bank=$8 drop=$3):")
    print("  rule: elapsed>=Ns AND peak<$Pg AND pnl<=-$L -> cut")
    print(f"  {'rule':<26} {'NET':<12} {'WR':<7} {'breakdown'}")
    for (s, pk, l) in [(8,1,4),(15,1,4),(8,1,6),(15,1,6),(8,1,8),(15,1,8),
                       (8,2,6),(15,2,8),(8,3,8)]:
        r = replay(ticks, sig, 150, 8, 3, pg_secs=s, pg_peak=pk, pg_loss=l)
        print(f"  {s}s/pk<${pk}/-${l:<11} ${r['total']:<+10.2f} {r['wr']:<5.0f}%  [{fmt_by(r['by'])}]")

    print("\nSWEEP 3 — floor + peak-guard combined:")
    print(f"  {'config':<30} {'NET':<12} {'WR'}")
    for fl in (12, 15, 20, 30):
        for (s, pk, l) in [(8,1,6),(15,1,8)]:
            r = replay(ticks, sig, fl, 8, 3, pg_secs=s, pg_peak=pk, pg_loss=l)
            print(f"  floor-${fl} + {s}s/pk<${pk}/-${l:<8} ${r['total']:<+10.2f} {r['wr']:.0f}%")

    print("\nSWEEP 4 — roll-over bank/drop (floor=$20):")
    print(f"  {'bank/drop':<14} {'NET':<12} {'WR':<7} {'breakdown'}")
    for bank in (4, 6, 8, 12):
        for drop in (2, 3, 5):
            r = replay(ticks, sig, 20, bank, drop)
            print(f"  bank${bank}/drop${drop:<5} ${r['total']:<+10.2f} {r['wr']:<5.0f}%  [{fmt_by(r['by'])}]")

    print("\nSWEEP 5 — PROBE CONFIRM strength (floor=$150 bank=$8 drop=$3):")
    print("  higher confirm = probe must recover MORE before committing the main")
    print(f"  {'confirm rule':<24} {'NET':<12} {'WR':<7} {'breakdown'}")
    for cf in (1, 2, 3, 5, 8, 12):
        r = replay(ticks, sig, 150, 8, 3, probe_confirm=cf)
        print(f"  +${cf} touch{'':<13} ${r['total']:<+10.2f} {r['wr']:<5.0f}%  [{fmt_by(r['by'])}]")
    for (cf, hold) in [(1, 5), (1, 10), (2, 5), (2, 10), (3, 10), (3, 20)]:
        r = replay(ticks, sig, 150, 8, 3, probe_confirm=cf, confirm_hold_s=hold)
        print(f"  +${cf} held {hold}s{'':<11} ${r['total']:<+10.2f} {r['wr']:<5.0f}%  [{fmt_by(r['by'])}]")

    print("\nSWEEP 6 — best-of-breed combos (confirm + floor + peak-guard):")
    print(f"  {'config':<46} {'NET':<12} {'WR'}")
    for cf in (2, 3, 5):
        for hold in (0, 10):
            for fl in (20, 40, 150):
                r = replay(ticks, sig, fl, 8, 3, probe_confirm=cf, confirm_hold_s=hold)
                cfg = f"confirm+${cf}" + (f"/{hold}s" if hold else "") + f", floor-${fl}"
                print(f"  {cfg:<46} ${r['total']:<+10.2f} {r['wr']:.0f}%")


if __name__ == "__main__":
    main()
