"""backtest_v349_multiday.py — validate the probe-confirm fix across EVERY
day of available real tick data.

For each day with a shano_ticks_*.csv, replay v3.49 with confirm=$1 (the
shipped value) vs confirm=$2 (the candidate from the today-only sweep) and
see whether +$2 holds up day after day, or was a one-day fluke.

M1 bars for the detector come from BOTH rev_eng_m1.csv (wide/older) and
rev_eng_m1_recent.csv (fresh) merged + deduped.
"""
import csv
import glob
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

PROBE_LOTS, REAL_LOTS = 0.01, 0.40
PROBE_FLOOR = 40.0
MAX_UNITS, RATE_LIMIT_S, CONTRACT = 2, 2, 100.0
MAX_LOOKBACK, MAX_BARS_BACK = 60, 60


def load_m1_merged():
    bars = {}
    for fn in ("rev_eng_m1.csv", "rev_eng_m1_recent.csv"):
        p = COMMON / fn
        if not p.exists():
            continue
        with open(p, encoding="ascii", errors="replace") as f:
            for r in csv.DictReader(f):
                try:
                    tm = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
                except Exception:
                    continue
                bars[tm] = {"time": tm, "open": float(r["open"]), "high": float(r["high"]),
                            "low": float(r["low"]), "close": float(r["close"]),
                            "vol": int(r["tick_volume"])}
    out = sorted(bars.values(), key=lambda b: b["time"])
    return out


def load_ticks(path):
    out = []
    with open(path, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                out.append({"t": datetime.strptime(r["ts_broker"], "%Y.%m.%d %H:%M:%S"),
                            "bid": float(r["bid"]), "ask": float(r["ask"])})
            except Exception:
                continue
    return out


def detect_on_bar(bars, idx_bo, strict=False):
    """Returns (side, uhv_high, uhv_low) or (0,0,0).
       strict=False : v3.43 RELAXED (drop vol-check, non-fatal overlap).
       strict=True  : v3.42 STRICT (require bo.vol<uhv.vol, fatal overlap break,
                      require a swing-back)."""
    bo = bars[idx_bo]
    if bo["close"] > bo["open"]:
        ui, uv = -1, -1
        found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["high"] >= bo["close"]:
                if strict: found_swing = True; break
                else: continue
            if c["close"] < c["open"] and c["vol"] > uv: ui, uv = k, c["vol"]
        if ui < 0 or (idx_bo - ui) > MAX_BARS_BACK: return (0, 0, 0)
        if bo["close"] <= bars[ui]["high"]: return (0, 0, 0)
        if strict and not found_swing: return (0, 0, 0)
        if strict and bo["vol"] >= uv: return (0, 0, 0)
        return (+1, bars[ui]["high"], bars[ui]["low"])
    if bo["close"] < bo["open"]:
        ui, uv = -1, -1
        found_swing = False
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["low"] <= bo["close"]:
                if strict: found_swing = True; break
                else: continue
            if c["close"] > c["open"] and c["vol"] > uv: ui, uv = k, c["vol"]
        if ui < 0 or (idx_bo - ui) > MAX_BARS_BACK: return (0, 0, 0)
        if bo["close"] >= bars[ui]["low"]: return (0, 0, 0)
        if strict and not found_swing: return (0, 0, 0)
        if strict and bo["vol"] >= uv: return (0, 0, 0)
        return (-1, bars[ui]["high"], bars[ui]["low"])
    return (0, 0, 0)


def build_signals(bars, strict=False):
    """{minute: (side, uhv_high, uhv_low)} — side 0 means no signal."""
    sig = {}
    for i, b in enumerate(bars):
        if i < MAX_LOOKBACK + 2: continue
        sig[b["time"] + timedelta(minutes=1)] = detect_on_bar(bars, i, strict=strict)
    return sig


# ── SIMPLE-EXIT replay: strict detector + a basic (non-probe) exit ──
def replay_simple(ticks, sig, exit_mode, lots,
                  rr_mult=1.0, sc_loss=2.0, sc_peak=1.0,
                  bank=1.0, drop=0.5, cap_floor=30.0):
    """Fire ONE position of `lots` on each strict signal. Exits:
       'rr'         : SL=UHV level, TP=entry + rr_mult * R   (lesson-2 style)
       'peak_trail' : smart-cut (pnl<=-sc_loss & peak<sc_peak) + peak-trail
                      (peak>=bank -> lock peak-drop) + catastrophe SL at UHV.
    All $ thresholds scale by lots/0.10 so point distances stay constant."""
    ppp = lots * CONTRACT
    scale = lots / 0.10
    units, last_fire, done = [], None, []

    def pnl_of(u, bid, ask):
        return ((bid - u["e"]) if u["side"] > 0 else (u["e"] - ask)) * ppp

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            pnl = pnl_of(u, bid, ask)
            if pnl > u["peak"]: u["peak"] = pnl
            exit_pnl = why = None
            cur = bid if u["side"] > 0 else ask   # side we mark/exit against
            # catastrophic UHV-level stop (both modes)
            if u["side"] > 0 and cur <= u["cat_sl"]:
                exit_pnl, why = (u["cat_sl"] - u["e"]) * ppp, "cat_sl"
            elif u["side"] < 0 and cur >= u["cat_sl"]:
                exit_pnl, why = (u["e"] - u["cat_sl"]) * ppp, "cat_sl"
            if exit_pnl is None and exit_mode == "rr":
                if u["side"] > 0 and cur >= u["tp"]:
                    exit_pnl, why = (u["tp"] - u["e"]) * ppp, "tp"
                elif u["side"] < 0 and cur <= u["tp"]:
                    exit_pnl, why = (u["e"] - u["tp"]) * ppp, "tp"
            if exit_pnl is None and exit_mode == "peak_trail":
                # smart-cut
                if u["peak"] < sc_peak * scale and pnl <= -sc_loss * scale:
                    exit_pnl, why = pnl, "smart_cut"
                else:
                    # peak-trail lock
                    if u["peak"] >= bank * scale:
                        tgt = u["peak"] - drop * scale
                        if tgt > u["locked"]: u["locked"] = tgt
                    if u["locked"] > 0 and pnl <= u["locked"]:
                        exit_pnl, why = u["locked"], "trail"
            if exit_pnl is not None:
                u["pnl"] = exit_pnl; u["why"] = why
                done.append(u); units.remove(u)
        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        s = sig.get(t.replace(second=0), (0, 0, 0))
        side, uhv_h, uhv_l = s
        if side == 0: continue
        e = ask if side > 0 else bid
        cat = uhv_l if side > 0 else uhv_h
        r = abs(e - cat)
        if r < 0.10 or r > 30.0: continue   # min/max R reject (lesson-2)
        tp = e + rr_mult * r if side > 0 else e - rr_mult * r
        units.append({"side": side, "e": e, "cat_sl": cat, "tp": tp,
                      "peak": 0.0, "locked": 0.0})
        last_fire = t

    last = ticks[-1]
    for u in units:
        u["pnl"] = pnl_of(u, last["bid"], last["ask"]); u["why"] = "eod"
        done.append(u)
    total = sum(u["pnl"] for u in done)
    wins = sum(1 for u in done if u["pnl"] > 0)
    losses = sum(1 for u in done if u["pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr)


def run_strict_simple_sweep(tick_files, bars):
    print("\n" + "=" * 80)
    print("STRICT detector (v3.42: vol-check + momentum candle) + SIMPLE exits")
    print("  this is the combination that was NEVER multi-day-tested")
    print("=" * 80)
    sig = build_signals(bars, strict=True)
    configs = [
        ("rr",          0.10, dict(rr_mult=1.0)),
        ("rr",          0.10, dict(rr_mult=1.5)),
        ("rr",          0.10, dict(rr_mult=2.0)),
        ("peak_trail",  0.10, dict(sc_loss=2.0, sc_peak=1.0, bank=1.0, drop=0.5)),
        ("peak_trail",  0.10, dict(sc_loss=3.0, sc_peak=1.0, bank=2.0, drop=1.0)),
        ("peak_trail",  0.10, dict(sc_loss=4.0, sc_peak=1.0, bank=3.0, drop=1.5)),
        ("rr",          0.40, dict(rr_mult=1.0)),
        ("peak_trail",  0.40, dict(sc_loss=2.0, sc_peak=1.0, bank=1.0, drop=0.5)),
    ]
    for (mode, lots, kw) in configs:
        agg = 0.0; gw = gl = 0; days_green = 0; nd = 0
        for tf in tick_files:
            ticks = load_ticks(tf)
            if len(ticks) < 100: continue
            r = replay_simple(ticks, sig, mode, lots, **kw)
            agg += r["total"]; gw += r["wins"]; gl += r["losses"]
            if r["total"] > 0: days_green += 1
            nd += 1
        wr = 100 * gw / (gw + gl) if (gw + gl) else 0
        kws = ",".join(f"{k}={v}" for k, v in kw.items())
        print(f"  {mode:<11} {lots:.2f}lot [{kws:<42}] "
              f"${agg:<+10.2f} {days_green}/{nd}d green WR{wr:.0f}%")


def replay(ticks, sig, probe_confirm, main_floor=150.0, main_bank=8.0, main_drop=3.0):
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
    wins = sum(1 for u in done if u["pnl"] > 0)
    losses = sum(1 for u in done if u["pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    floor_hits = sum(1 for u in done if u["why"] == "main_floor")
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr, floor_hits=floor_hits)


def replay_single(ticks, sig, lots, floor_usd, bank_usd, drop_usd):
    """SINGLE-POSITION variant (Zee's idea, corrected): no probe/main split.
    Fire ONE position of `lots` at the breakout, hold it through drawdown to
    a -floor_usd catastrophe SL, exit on roll-over (peak>=bank → lock peak-drop).
    This is 'the probe, held from the breakout, sized up and made the trade'.
    """
    ppp = lots * CONTRACT
    units, last_fire, done = [], None, []

    def pnl_of(u, bid, ask):
        return ((bid - u["e"]) if u["side"] > 0 else (u["e"] - ask)) * ppp

    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            pnl = pnl_of(u, bid, ask)
            if pnl > u["peak"]: u["peak"] = pnl
            exit_pnl = exit_why = None
            if u["peak"] >= bank_usd:
                tgt = u["peak"] - drop_usd
                if tgt > u["locked"]: u["locked"] = tgt
            if u["locked"] > 0 and pnl <= u["locked"]:
                exit_pnl, exit_why = u["locked"], "rollover"
            if exit_pnl is None and pnl <= -floor_usd:
                exit_pnl, exit_why = -floor_usd, "floor"
            if exit_pnl is not None:
                u["pnl"] = exit_pnl; u["why"] = exit_why
                done.append(u); units.remove(u)
        if len(units) >= MAX_UNITS: continue
        if last_fire and (t - last_fire).total_seconds() < RATE_LIMIT_S: continue
        s = sig.get(t.replace(second=0), (0, 0, 0))[0]
        if s == 0: continue
        units.append({"side": s, "e": ask if s > 0 else bid,
                      "peak": 0.0, "locked": 0.0})
        last_fire = t

    last = ticks[-1]
    for u in units:
        u["pnl"] = pnl_of(u, last["bid"], last["ask"]); u["why"] = "eod"
        done.append(u)

    total = sum(u["pnl"] for u in done)
    wins = sum(1 for u in done if u["pnl"] > 0)
    losses = sum(1 for u in done if u["pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    floor_hits = sum(1 for u in done if u["why"] == "floor")
    return dict(total=total, n=len(done), wins=wins, losses=losses, wr=wr, floor_hits=floor_hits)


def run_single_sweep(tick_files, sig):
    print("\n" + "=" * 80)
    print("SINGLE-POSITION variant — no probe/main split (Zee's idea, corrected)")
    print("  fire ONE position at the breakout, hold to floor, exit on roll-over")
    print("=" * 80)
    # configs: (lots, floor, bank, drop)
    configs = [
        (0.10,  20, 8, 3),
        (0.10,  40, 8, 3),
        (0.10,  80, 8, 3),
        (0.20,  40, 16, 6),
        (0.20,  80, 16, 6),
        (0.40,  80, 32, 12),
        (0.40, 150, 32, 12),
    ]
    for (lots, floor, bank, drop) in configs:
        agg = 0.0; gw = 0; gl = 0; gf = 0; days_green = 0; nd = 0
        for tf in tick_files:
            ticks = load_ticks(tf)
            if len(ticks) < 100: continue
            r = replay_single(ticks, sig, lots, floor, bank, drop)
            agg += r["total"]; gw += r["wins"]; gl += r["losses"]; gf += r["floor_hits"]
            if r["total"] > 0: days_green += 1
            nd += 1
        wr = 100 * gw / (gw + gl) if (gw + gl) else 0
        print(f"  {lots:.2f} lot  floor-${floor:<4} bank${bank}/drop${drop:<3} : "
              f"total ${agg:<+10.2f}  {days_green}/{nd} days green  WR {wr:.0f}%  floor-hits {gf}")


def main():
    bars = load_m1_merged()
    print(f"Merged M1 bars: {len(bars)}  ({bars[0]['time'].date()} -> {bars[-1]['time'].date()})\n")
    sig = build_signals(bars)

    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    print(f"{'day':<12} {'ticks':<8} | {'confirm +$1':<24} | {'confirm +$2':<24}")
    print(f"{'':12} {'':8} | {'NET':<10} {'WR':<6} {'floor':<6} | {'NET':<10} {'WR':<6} {'floor'}")
    print("-" * 80)

    agg1 = {"total": 0.0, "wins": 0, "losses": 0, "floor": 0, "n": 0}
    agg2 = {"total": 0.0, "wins": 0, "losses": 0, "floor": 0, "n": 0}
    rows = []
    for tf in tick_files:
        day = Path(tf).stem.replace("shano_ticks_", "")
        ticks = load_ticks(tf)
        if len(ticks) < 100:
            continue
        r1 = replay(ticks, sig, probe_confirm=1.0)
        r2 = replay(ticks, sig, probe_confirm=2.0)
        rows.append((day, len(ticks), r1, r2))
        for agg, r in ((agg1, r1), (agg2, r2)):
            agg["total"] += r["total"]; agg["wins"] += r["wins"]
            agg["losses"] += r["losses"]; agg["floor"] += r["floor_hits"]; agg["n"] += r["n"]
        print(f"{day:<12} {len(ticks):<8} | "
              f"${r1['total']:<+9.2f} {r1['wr']:<5.0f}% {r1['floor_hits']:<6} | "
              f"${r2['total']:<+9.2f} {r2['wr']:<5.0f}% {r2['floor_hits']}")

    print("-" * 80)
    wr1 = 100 * agg1["wins"] / (agg1["wins"] + agg1["losses"]) if (agg1["wins"]+agg1["losses"]) else 0
    wr2 = 100 * agg2["wins"] / (agg2["wins"] + agg2["losses"]) if (agg2["wins"]+agg2["losses"]) else 0
    print(f"{'TOTAL':<12} {'':8} | "
          f"${agg1['total']:<+9.2f} {wr1:<5.0f}% {agg1['floor']:<6} | "
          f"${agg2['total']:<+9.2f} {wr2:<5.0f}% {agg2['floor']}")
    print()
    days_pos_1 = sum(1 for (_, _, r1, _) in rows if r1["total"] > 0)
    days_pos_2 = sum(1 for (_, _, _, r2) in rows if r2["total"] > 0)
    print(f"confirm +$1 : {days_pos_1}/{len(rows)} days green, total ${agg1['total']:+.2f}, "
          f"{agg1['floor']} catastrophic main-floor hits")
    print(f"confirm +$2 : {days_pos_2}/{len(rows)} days green, total ${agg2['total']:+.2f}, "
          f"{agg2['floor']} catastrophic main-floor hits")

    run_single_sweep(tick_files, sig)

    # ── STRICT detector (v3.42) — the one untested lever ──
    print("\n" + "=" * 80)
    print("STRICT detector (v3.42: vol-check + fatal-overlap + swing-back) — probe+main")
    print("  far more selective: fires only on the cleanest UHV breakouts")
    print("=" * 80)
    sig_strict = build_signals(bars, strict=True)
    n_relaxed = sum(1 for v in sig.values() if v[0] != 0)
    n_strict = sum(1 for v in sig_strict.values() if v[0] != 0)
    print(f"  signal-bars: relaxed={n_relaxed}  strict={n_strict}  "
          f"({100*n_strict/n_relaxed:.0f}% as many)\n")
    print(f"  {'day':<12} | {'confirm +$1':<22} | {'confirm +$2'}")
    sa1 = {"total": 0.0, "wins": 0, "losses": 0, "floor": 0}
    sa2 = {"total": 0.0, "wins": 0, "losses": 0, "floor": 0}
    sd1 = sd2 = 0
    for tf in tick_files:
        day = Path(tf).stem.replace("shano_ticks_", "")
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        r1 = replay(ticks, sig_strict, probe_confirm=1.0)
        r2 = replay(ticks, sig_strict, probe_confirm=2.0)
        for a, r in ((sa1, r1), (sa2, r2)):
            a["total"] += r["total"]; a["wins"] += r["wins"]
            a["losses"] += r["losses"]; a["floor"] += r["floor_hits"]
        sd1 += 1 if r1["total"] > 0 else 0
        sd2 += 1 if r2["total"] > 0 else 0
        print(f"  {day:<12} | ${r1['total']:<+9.2f} {r1['wr']:<4.0f}% fl{r1['floor_hits']:<4} | "
              f"${r2['total']:<+9.2f} {r2['wr']:.0f}% fl{r2['floor_hits']}")
    swr1 = 100*sa1["wins"]/(sa1["wins"]+sa1["losses"]) if (sa1["wins"]+sa1["losses"]) else 0
    swr2 = 100*sa2["wins"]/(sa2["wins"]+sa2["losses"]) if (sa2["wins"]+sa2["losses"]) else 0
    print(f"  {'TOTAL':<12} | ${sa1['total']:<+9.2f} {swr1:<4.0f}% fl{sa1['floor']:<4} | "
          f"${sa2['total']:<+9.2f} {swr2:.0f}% fl{sa2['floor']}")
    print(f"\n  strict+confirm$1: {sd1}/12 green, ${sa1['total']:+.2f}")
    print(f"  strict+confirm$2: {sd2}/12 green, ${sa2['total']:+.2f}")

    run_strict_simple_sweep(tick_files, bars)


if __name__ == "__main__":
    main()
