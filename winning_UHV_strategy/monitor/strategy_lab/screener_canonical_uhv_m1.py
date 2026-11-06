"""screener_canonical_uhv_m1.py — same 7-gate canonical detector but on M1 bars.

Per Zee's lesson02 (2026-06-06 reminder): "this thing also applies on 1 minute scale,
if we apply it on 1 minute candles, then we get trades very quickly, every 5 minutes,
every 5 minutes we get a trade." → expected ~5× the fires vs M5.

Bars are aggregated per minute from broker tick CSVs. Volume = tick-count/min.

Usage: py monitor/strategy_lab/screener_canonical_uhv_m1.py --days 10
"""
from __future__ import annotations
import argparse, csv, json, sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"C:/Users/zeesh/Documents/GitHub/turtle")
TICK_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
OUT_DIR = REPO / "monitor" / "strategy_lab" / "_canonical"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Tunables (scaled for M1) ─────────────────────────────────────────────
RETRACE_LOOKBACK = 60          # bars = 60 min lookback (matches M5×5 since M1 is 5× smaller)
RETRACE_MAX_LEN  = 40          # max bars (40 min) for breakout window
MOM_THRESH       = 0.65        # v2.62 matches MQL5 InpBreakoutBodyRatio
UHV_BODY_MIN     = 0.5        # v2.62 matches MQL5 InpUhvBodyMin
BREAKOUT_VOL_MAX_RATIO = 0.85  # v2.62 InpBreakoutVolRatio
MIN_BREAKOUT_PENETRATION = 0.30 # v2.62 NEW InpMinBreakoutPenetration
TP_LOOKBACK_BARS = 240         # ~4h on M1 for prior peak/trough
TREND_BARS       = 30          # 30 min trend window (HH+HL second-half-vs-first-half)
SL_BUFFER        = 1.5        # v2.62 matches live EA InpSLBufferPts
HARD_TREND       = True
TP_FIXED_PTS     = 3.0        # v2.62 InpRequireHHHL_M5=true


@dataclass
class Bar:
    t: datetime
    o: float; h: float; l: float; c: float
    v: int
    @property
    def is_bull(self): return self.c > self.o
    @property
    def is_bear(self): return self.c < self.o
    @property
    def body(self): return abs(self.c - self.o)
    @property
    def rng(self):  return max(self.h - self.l, 1e-9)
    @property
    def body_ratio(self): return self.body / self.rng


def build_m1(date_csvs: list[Path]) -> list[Bar]:
    rows = []
    for p in date_csvs:
        try:
            with p.open(newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    ts = row.get("ts_broker") or row.get("ts") or row.get("t")
                    if not ts: continue
                    if "." in ts.split(" ", 1)[-1]:
                        ts = ts.rsplit(".", 1)[0]
                    try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
                    except ValueError: continue
                    try:
                        bid = float(row["bid"]); ask = float(row["ask"])
                    except (KeyError, ValueError): continue
                    rows.append((dt, (bid + ask) / 2))
        except Exception: continue
    if not rows: return []
    rows.sort()
    bars: dict = {}
    for dt, mid in rows:
        bt = dt.replace(second=0, microsecond=0)  # M1 bucketing
        b = bars.get(bt)
        if b is None:
            bars[bt] = [mid, mid, mid, mid, 1]
        else:
            b[1] = max(b[1], mid); b[2] = min(b[2], mid); b[3] = mid; b[4] += 1
    out = []
    for bt in sorted(bars.keys()):
        b = bars[bt]
        out.append(Bar(bt, b[0], b[1], b[2], b[3], b[4]))
    return out


def trend_uptrend(bars, i):
    if i < TREND_BARS + 2: return False
    seg = bars[i - TREND_BARS: i]
    mid = len(seg) // 2
    return (max(b.h for b in seg[mid:]) > max(b.h for b in seg[:mid])) and \
           (min(b.l for b in seg[mid:]) > min(b.l for b in seg[:mid]))

def trend_downtrend(bars, i):
    if i < TREND_BARS + 2: return False
    seg = bars[i - TREND_BARS: i]
    mid = len(seg) // 2
    return (max(b.h for b in seg[mid:]) < max(b.h for b in seg[:mid])) and \
           (min(b.l for b in seg[mid:]) < min(b.l for b in seg[:mid]))


def find_retracement_origin_buy(bars, i):
    for j in range(i - 1, max(i - RETRACE_LOOKBACK, 1), -1):
        if not bars[j].is_bear: continue
        for k in range(j - 1, max(j - 15, -1), -1):
            if bars[k].is_bull and bars[j].c < bars[k].l:
                return j
    return None

def find_retracement_origin_sell(bars, i):
    for j in range(i - 1, max(i - RETRACE_LOOKBACK, 1), -1):
        if not bars[j].is_bull: continue
        for k in range(j - 1, max(j - 15, -1), -1):
            if bars[k].is_bear and bars[j].c > bars[k].h:
                return j
    return None


def find_uhv_buy(bars, origin, end):
    cands = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bear: continue
        if b.body_ratio < UHV_BODY_MIN: continue
        if i - 1 >= 0 and bars[i - 1].v >= b.v: continue
        if i + 1 < len(bars) and bars[i + 1].v >= b.v: continue
        cands.append(i)
    if not cands: return None
    best = max(cands, key=lambda x: bars[x].v)
    if bars[best].v < max(bars[k].v for k in range(origin, min(end, len(bars)))): return None
    return best

def find_uhv_sell(bars, origin, end):
    cands = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bull: continue
        if b.body_ratio < UHV_BODY_MIN: continue
        if i - 1 >= 0 and bars[i - 1].v >= b.v: continue
        if i + 1 < len(bars) and bars[i + 1].v >= b.v: continue
        cands.append(i)
    if not cands: return None
    best = max(cands, key=lambda x: bars[x].v)
    if bars[best].v < max(bars[k].v for k in range(origin, min(end, len(bars)))): return None
    return best


def sweep_ok_buy(bars, uhv, end):
    lo = bars[uhv].l
    return any(bars[i].l < lo for i in range(uhv + 1, min(end, len(bars))))

def sweep_ok_sell(bars, uhv, end):
    hi = bars[uhv].h
    return any(bars[i].h > hi for i in range(uhv + 1, min(end, len(bars))))


def find_breakout_buy(bars, uhv):
    for i in range(uhv + 1, min(uhv + RETRACE_MAX_LEN + 1, len(bars))):
        b = bars[i]
        if not b.is_bull: continue
        if b.c <= bars[uhv].h: continue
        if (b.c - bars[uhv].h) < MIN_BREAKOUT_PENETRATION: continue  # v2.62
        if b.v >= bars[uhv].v * BREAKOUT_VOL_MAX_RATIO: continue
        if b.body_ratio < MOM_THRESH: continue
        return i
    return None

def find_breakout_sell(bars, uhv):
    for i in range(uhv + 1, min(uhv + RETRACE_MAX_LEN + 1, len(bars))):
        b = bars[i]
        if not b.is_bear: continue
        if b.c >= bars[uhv].l: continue
        if (bars[uhv].l - b.c) < MIN_BREAKOUT_PENETRATION: continue  # v2.62
        if b.v >= bars[uhv].v * BREAKOUT_VOL_MAX_RATIO: continue
        if b.body_ratio < MOM_THRESH: continue
        return i
    return None


@dataclass
class CanonicalSetup:
    side: str
    open_t: str
    entry: float; sl: float; tp: float
    uhv_t: str; uhv_vol: int
    breakout_t: str; breakout_vol: int
    origin_t: str
    soft_trend: bool; soft_sweep: bool; uhv_body_strong: bool


def detect(bars):
    fires = []
    used = set()
    for i in range(TREND_BARS + 3, len(bars)):
        for side in ("BUY", "SELL"):
            trend_ok = trend_uptrend(bars, i) if side == "BUY" else trend_downtrend(bars, i)
            if HARD_TREND and not trend_ok: continue
            origin = (find_retracement_origin_buy(bars, i) if side == "BUY"
                      else find_retracement_origin_sell(bars, i))
            if origin is None: continue
            uhv = (find_uhv_buy(bars, origin, i + 1) if side == "BUY"
                   else find_uhv_sell(bars, origin, i + 1))
            if uhv is None or uhv in used: continue
            sweep_ok = (sweep_ok_buy(bars, uhv, i + 1) if side == "BUY"
                        else sweep_ok_sell(bars, uhv, i + 1))
            brk = (find_breakout_buy(bars, uhv) if side == "BUY"
                   else find_breakout_sell(bars, uhv))
            if brk is None or brk != i: continue
            entry = bars[brk].c
            sl = bars[uhv].l - SL_BUFFER if side == "BUY" else bars[uhv].h + SL_BUFFER
            sl_dist = abs(entry - sl)
            window_start = max(0, uhv - TP_LOOKBACK_BARS)
            tp = None
            if side == "BUY":
                cands = [b.h for b in bars[window_start: uhv] if b.h > entry]
                tp = entry + TP_FIXED_PTS
            else:
                cands = [b.l for b in bars[window_start: uhv] if b.l < entry]
                tp = entry - TP_FIXED_PTS
            used.add(uhv)
            fires.append(CanonicalSetup(
                side=side,
                open_t=bars[brk].t.strftime("%Y-%m-%d %H:%M"),
                entry=round(entry, 2), sl=round(sl, 2), tp=round(tp, 2),
                uhv_t=bars[uhv].t.strftime("%Y-%m-%d %H:%M"),
                uhv_vol=bars[uhv].v,
                breakout_t=bars[brk].t.strftime("%Y-%m-%d %H:%M"),
                breakout_vol=bars[brk].v,
                origin_t=bars[origin].t.strftime("%Y-%m-%d %H:%M"),
                soft_trend=bool(trend_ok), soft_sweep=bool(sweep_ok),
                uhv_body_strong=bool(bars[uhv].body_ratio >= 0.55),
            ))
    return fires


def simulate(setup, bars):
    open_dt = datetime.strptime(setup.open_t, "%Y-%m-%d %H:%M")
    f_idx = None
    for i, b in enumerate(bars):
        if b.t > open_dt: f_idx = i; break
    if f_idx is None: return {"outcome": "OPEN", "pnl_usd": None, "close_t": None}
    for j in range(f_idx, min(f_idx + 1200, len(bars))):  # 20h max on M1 (wider so SL/TP resolve)
        b = bars[j]
        if setup.side == "BUY":
            if b.l <= setup.sl: return {"outcome": "LOSS", "pnl_usd": round(setup.sl - setup.entry, 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
            if b.h >= setup.tp: return {"outcome": "WIN",  "pnl_usd": round(setup.tp - setup.entry, 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
        else:
            if b.h >= setup.sl: return {"outcome": "LOSS", "pnl_usd": round(setup.entry - setup.sl, 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
            if b.l <= setup.tp: return {"outcome": "WIN",  "pnl_usd": round(setup.entry - setup.tp, 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
    return {"outcome": "OPEN", "pnl_usd": None, "close_t": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()

    tick_csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    if not tick_csvs: print("no csvs"); return
    print(f"Loading {len(tick_csvs)} CSVs")

    bars = build_m1(tick_csvs)
    print(f"Built {len(bars)} M1 bars from {bars[0].t} to {bars[-1].t}")

    fires = detect(bars)
    print(f"Detected {len(fires)} M1 canonical setups")

    out_rows = []
    wins = losses = open_ = 0
    pnl_total = 0.0
    for s in fires:
        sim = simulate(s, bars)
        row = {**asdict(s), **sim}
        out_rows.append(row)
        if sim["outcome"] == "WIN": wins += 1; pnl_total += sim["pnl_usd"]
        elif sim["outcome"] == "LOSS": losses += 1; pnl_total += sim["pnl_usd"]
        else: open_ += 1
    closed = wins + losses
    wr = (wins / closed * 100) if closed else 0
    pos = sum(r["pnl_usd"] for r in out_rows if r.get("pnl_usd",0) and r["pnl_usd"] > 0)
    neg = sum(r["pnl_usd"] for r in out_rows if r.get("pnl_usd",0) and r["pnl_usd"] < 0)
    pf = (pos / abs(neg)) if neg < 0 else float("inf")

    print(f"\n=== M1 CANONICAL RESULTS ===")
    print(f"  Setups:       {len(fires)}")
    print(f"  Closed:       {closed} (W={wins} L={losses} OPEN={open_})")
    print(f"  WR:           {wr:.1f}%")
    print(f"  Net PNL:      {pnl_total:+.2f} pts")
    print(f"  PF:           {pf:.2f}")
    print(f"  Days:         {args.days}")
    print(f"  Fires/day:    {len(fires)/args.days:.1f}")

    p = OUT_DIR / f"results_m1_{args.days}d.json"
    p.write_text(json.dumps({
        "timeframe": "M1", "days": args.days, "bars": len(bars),
        "setups": len(fires), "wins": wins, "losses": losses, "open": open_,
        "wr_pct": wr, "pnl_pts": pnl_total, "pf": pf,
        "fires": out_rows,
    }, indent=2, default=str), encoding="utf-8")
    print(f"Saved → {p}")


if __name__ == "__main__":
    main()
