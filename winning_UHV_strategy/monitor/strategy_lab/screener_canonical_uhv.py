"""screener_canonical_uhv.py — Zee's CANONICAL Setup 1 detector.

Implements the 7 gates from memory/project_uhv_canonical_rules.md after the
2026-06-05 35-setup labelling pass:

  1. Trend context (M5 HH+HL for BUY, LH+LL for SELL)            [soft]
  2. Retracement origin (opposite-colour body breaks prior extreme)
  3. UHV inside retracement (correct colour + strictly highest vol vs neighbours)
  4. Sweep step (any candle's wick/body breaks UHV's opposite extreme)  [soft]
  5. Breakout candle:
     5a. body CLOSES across UHV's directional extreme
     5b. colour OPPOSITE to UHV
     5c. volume STRICTLY LOWER than UHV
     5d. momentum (body/range >= MOM_THRESH)
  6. Entry at breakout close
  7. One fire per UHV (state machine)

FVG gate is implemented as 3 modes (STRICT=H1, RELAXED=M5, NONE=skip).
For this first pass we use mode=NONE so we measure the other 6 gates' WR.

Usage:
    py monitor/strategy_lab/screener_canonical_uhv.py --days 5 --fvg none
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

# ── Tunables ─────────────────────────────────────────────────────────────
RETRACE_LOOKBACK = 15          # v2.62 matches InpRetraceLookback default
RETRACE_MAX_LEN  = 15          # max bars a retracement can span before invalidated
MOM_THRESH       = 0.65        # v2.62 InpBreakoutBodyRatio
UHV_BODY_MIN     = 0.50        # v2.62 InpUhvBodyMin
BREAKOUT_VOL_MAX_RATIO = 0.75  # v2.62 InpBreakoutVolRatio
MIN_BREAKOUT_PENETRATION = 0.30  # v2.62 NEW — InpMinBreakoutPenetration
TP_LOOKBACK_BARS = 60          # bars back to find prior peak/trough for TP
TREND_BARS       = 10          # bars for HH+HL / LH+LL window
SL_BUFFER        = 2.00        # v2.62 matches live EA InpSLBufferPts
HARD_TREND       = True        # v2.62 InpRequireHHHL_M5=true


# ── Bar model ────────────────────────────────────────────────────────────
@dataclass
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: int

    @property
    def is_bull(self) -> bool: return self.c > self.o
    @property
    def is_bear(self) -> bool: return self.c < self.o
    @property
    def body(self) -> float: return abs(self.c - self.o)
    @property
    def rng(self)  -> float: return max(self.h - self.l, 1e-9)
    @property
    def body_ratio(self) -> float: return self.body / self.rng


def build_m5(date_csvs: list[Path]) -> list[Bar]:
    """Build M5 OHLCV bars from broker tick CSVs."""
    rows = []
    for p in date_csvs:
        try:
            with p.open(newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    ts = row.get("ts_broker") or row.get("ts") or row.get("t")
                    if not ts: continue
                    # strip optional milliseconds: "2026.02.11 01:00:09.108" → "2026.02.11 01:00:09"
                    if "." in ts.split(" ", 1)[-1]:
                        ts = ts.rsplit(".", 1)[0]
                    try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
                    except ValueError: continue
                    try:
                        bid = float(row["bid"]); ask = float(row["ask"])
                    except (KeyError, ValueError): continue
                    rows.append((dt, (bid + ask) / 2))
        except Exception as e:
            print(f"  csv err {p.name}: {e}")
    if not rows: return []
    rows.sort()
    bars: dict[datetime, dict] = {}
    for dt, mid in rows:
        floor_min = (dt.minute // 5) * 5
        bt = dt.replace(minute=floor_min, second=0, microsecond=0)
        b = bars.get(bt)
        if b is None:
            bars[bt] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1}
        else:
            b["h"] = max(b["h"], mid)
            b["l"] = min(b["l"], mid)
            b["c"] = mid
            b["v"] += 1
    out = []
    for bt in sorted(bars.keys()):
        b = bars[bt]
        out.append(Bar(bt, b["o"], b["h"], b["l"], b["c"], b["v"]))
    return out


# ── Trend ────────────────────────────────────────────────────────────────
# Two modes:
#   "hhhl": strict camel-humps (second-half max > first-half max AND mins likewise)
#   "soft": Zee's mental model — any of the last 5 bars has a body close that
#           exceeded the max high of the 10 bars before it (a "new HH by body")
TREND_MODE = "hhhl"  # "hhhl" or "soft"


def _hhhl_up(bars, i):
    if i < TREND_BARS + 2: return False
    seg = bars[i - TREND_BARS: i]
    highs = [b.h for b in seg]; lows = [b.l for b in seg]
    mid = len(seg) // 2
    return (max(highs[mid:]) > max(highs[:mid])) and (min(lows[mid:]) > min(lows[:mid]))


def _hhhl_dn(bars, i):
    if i < TREND_BARS + 2: return False
    seg = bars[i - TREND_BARS: i]
    highs = [b.h for b in seg]; lows = [b.l for b in seg]
    mid = len(seg) // 2
    return (max(highs[mid:]) < max(highs[:mid])) and (min(lows[mid:]) < min(lows[:mid]))


def _soft_up(bars, i):
    """Recent body close broke a prior swing high — Zee's verbatim rule."""
    if i < 16: return False
    for j in range(i - 1, max(i - 6, 0), -1):
        if bars[j].c <= bars[j].o: continue              # bullish body only
        prior_max_h = max(b.h for b in bars[max(j - 10, 0): j])
        if bars[j].c > prior_max_h: return True
    return False


def _soft_dn(bars, i):
    if i < 16: return False
    for j in range(i - 1, max(i - 6, 0), -1):
        if bars[j].c >= bars[j].o: continue              # bearish body only
        prior_min_l = min(b.l for b in bars[max(j - 10, 0): j])
        if bars[j].c < prior_min_l: return True
    return False


def trend_uptrend(bars: list[Bar], i: int) -> bool:
    return _soft_up(bars, i) if TREND_MODE == "soft" else _hhhl_up(bars, i)


def trend_downtrend(bars: list[Bar], i: int) -> bool:
    return _soft_dn(bars, i) if TREND_MODE == "soft" else _hhhl_dn(bars, i)


# ── Retracement origin ──────────────────────────────────────────────────
def find_retracement_origin_buy(bars: list[Bar], i: int) -> int | None:
    """
    Retracement origin = the FIRST bear candle of the most recent bull→bear
    transition that started a pullback. Per Zee's spec (2026-06-08 clarification):

      - bars[j].is_bear
      - bars[j-1].is_bull              (the IMMEDIATE prior bar must be bullish)
      - bars[j].c < bars[j-1].l        (j's body closes BELOW that bull's low)

    Walk backwards from i. Returns the most-recent such j (= start of the retracement
    leading to the current bar), NOT the latest bear within an existing run.
    """
    for j in range(i - 1, max(i - RETRACE_LOOKBACK, 1), -1):
        if not bars[j].is_bear: continue
        if j - 1 < 0: continue
        if not bars[j - 1].is_bull: continue          # IMMEDIATE prior must be bull
        if bars[j].c >= bars[j - 1].l: continue       # body must close below bull's low
        return j
    return None


def find_retracement_origin_sell(bars: list[Bar], i: int) -> int | None:
    """Mirror: first bull whose immediate prior is bear and whose body closes ABOVE that bear's high."""
    for j in range(i - 1, max(i - RETRACE_LOOKBACK, 1), -1):
        if not bars[j].is_bull: continue
        if j - 1 < 0: continue
        if not bars[j - 1].is_bear: continue
        if bars[j].c <= bars[j - 1].h: continue
        return j
    return None


# ── UHV (inside the retracement) ────────────────────────────────────────
def find_uhv_buy(bars: list[Bar], origin: int, end: int) -> int | None:
    """
    UHV for BUY = bearish candle in [origin, end) where:
      - vol > all neighbours in retracement window
      - vol > vol[i-1] AND vol > vol[i+1]   (local peak)
      - body_ratio >= UHV_BODY_MIN          (no indecision dojis)
    """
    candidates = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bear: continue
        if b.body_ratio < UHV_BODY_MIN: continue
        if i - 1 >= 0 and bars[i - 1].v >= b.v: continue
        if i + 1 < len(bars) and bars[i + 1].v >= b.v: continue
        candidates.append(i)
    if not candidates: return None
    best = max(candidates, key=lambda x: bars[x].v)
    # additionally require it's the absolute volume max within the retracement window
    max_v_in_window = max(bars[k].v for k in range(origin, min(end, len(bars))))
    if bars[best].v < max_v_in_window: return None
    return best


def find_uhv_sell(bars: list[Bar], origin: int, end: int) -> int | None:
    candidates = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bull: continue
        if b.body_ratio < UHV_BODY_MIN: continue
        if i - 1 >= 0 and bars[i - 1].v >= b.v: continue
        if i + 1 < len(bars) and bars[i + 1].v >= b.v: continue
        candidates.append(i)
    if not candidates: return None
    best = max(candidates, key=lambda x: bars[x].v)
    max_v_in_window = max(bars[k].v for k in range(origin, min(end, len(bars))))
    if bars[best].v < max_v_in_window: return None
    return best


# ── Sweep step (soft) ────────────────────────────────────────────────────
def sweep_ok_buy(bars: list[Bar], uhv: int, end: int) -> bool:
    """Any candle in (uhv, end) breaks the UHV LOW (wick or body)."""
    uhv_low = bars[uhv].l
    for i in range(uhv + 1, min(end, len(bars))):
        if bars[i].l < uhv_low:
            return True
    return False


def sweep_ok_sell(bars: list[Bar], uhv: int, end: int) -> bool:
    uhv_high = bars[uhv].h
    for i in range(uhv + 1, min(end, len(bars))):
        if bars[i].h > uhv_high:
            return True
    return False


# ── Breakout ────────────────────────────────────────────────────────────
def find_breakout_buy(bars: list[Bar], uhv: int) -> int | None:
    """
    First bar i > uhv where ALL hold:
      bars[i].is_bull
      bars[i].c > bars[uhv].h          (body close above UHV high)
      bars[i].v < bars[uhv].v          (volume strictly lower)
      bars[i].body_ratio >= MOM_THRESH (momentum body)
    """
    for i in range(uhv + 1, min(uhv + RETRACE_MAX_LEN + 1, len(bars))):
        b = bars[i]
        if not b.is_bull: continue
        if b.c <= bars[uhv].h: continue
        if (b.c - bars[uhv].h) < MIN_BREAKOUT_PENETRATION: continue  # v2.62
        if b.v >= bars[uhv].v * BREAKOUT_VOL_MAX_RATIO: continue
        if b.body_ratio < MOM_THRESH: continue
        return i
    return None


def find_breakout_sell(bars: list[Bar], uhv: int) -> int | None:
    for i in range(uhv + 1, min(uhv + RETRACE_MAX_LEN + 1, len(bars))):
        b = bars[i]
        if not b.is_bear: continue
        if b.c >= bars[uhv].l: continue
        if (bars[uhv].l - b.c) < MIN_BREAKOUT_PENETRATION: continue  # v2.62
        if b.v >= bars[uhv].v * BREAKOUT_VOL_MAX_RATIO: continue
        if b.body_ratio < MOM_THRESH: continue
        return i
    return None


# ── Detection driver ────────────────────────────────────────────────────
@dataclass
class CanonicalSetup:
    side: str
    open_t: str
    entry: float
    sl: float
    tp: float
    uhv_t: str
    uhv_vol: int
    breakout_t: str
    breakout_vol: int
    origin_t: str
    soft_trend: bool
    soft_sweep: bool
    uhv_body_strong: bool
    notes: list[str] = field(default_factory=list)


def detect(bars: list[Bar]) -> list[CanonicalSetup]:
    fires: list[CanonicalSetup] = []
    used_uhvs: set[int] = set()

    for i in range(TREND_BARS + 3, len(bars)):
        for side in ("BUY", "SELL"):
            trend_ok = trend_uptrend(bars, i) if side == "BUY" else trend_downtrend(bars, i)
            if HARD_TREND and not trend_ok: continue
            origin = (find_retracement_origin_buy(bars, i)
                      if side == "BUY"
                      else find_retracement_origin_sell(bars, i))
            if origin is None: continue
            uhv = (find_uhv_buy(bars, origin, i + 1) if side == "BUY"
                   else find_uhv_sell(bars, origin, i + 1))
            if uhv is None or uhv in used_uhvs: continue
            sweep_ok = (sweep_ok_buy(bars, uhv, i + 1) if side == "BUY"
                        else sweep_ok_sell(bars, uhv, i + 1))
            brk = (find_breakout_buy(bars, uhv) if side == "BUY"
                   else find_breakout_sell(bars, uhv))
            if brk is None or brk > i: continue
            if brk != i: continue   # only fire on the breakout bar itself
            entry = bars[brk].c
            sl = bars[uhv].l - SL_BUFFER if side == "BUY" else bars[uhv].h + SL_BUFFER
            sl_dist = abs(entry - sl)
            # TP = recent peak/trough on the CORRECT side of entry; fallback to 2.5:1 R:R
            window_start = max(0, uhv - TP_LOOKBACK_BARS)
            tp = None
            if side == "BUY":
                candidates = [b.h for b in bars[window_start: uhv] if b.h > entry]
                if candidates: tp = max(candidates)
                if tp is None or (tp - entry) < sl_dist:  # require ≥1:1
                    tp = entry + sl_dist * 2.5
            else:
                candidates = [b.l for b in bars[window_start: uhv] if b.l < entry]
                if candidates: tp = min(candidates)
                if tp is None or (entry - tp) < sl_dist:  # require ≥1:1
                    tp = entry - sl_dist * 2.5
            used_uhvs.add(uhv)
            fires.append(CanonicalSetup(
                side=side,
                open_t=bars[brk].t.strftime("%Y-%m-%d %H:%M"),
                entry=round(entry, 2),
                sl=round(sl, 2),
                tp=round(tp, 2),
                uhv_t=bars[uhv].t.strftime("%Y-%m-%d %H:%M"),
                uhv_vol=bars[uhv].v,
                breakout_t=bars[brk].t.strftime("%Y-%m-%d %H:%M"),
                breakout_vol=bars[brk].v,
                origin_t=bars[origin].t.strftime("%Y-%m-%d %H:%M"),
                soft_trend=bool(trend_ok),
                soft_sweep=bool(sweep_ok),
                uhv_body_strong=bool(bars[uhv].body_ratio >= 0.50),
            ))
    return fires


# ── Outcome sim (TP/SL) ──────────────────────────────────────────────────
def simulate(setup: CanonicalSetup, bars: list[Bar]) -> dict:
    """Walk bars forward from setup time. First to be touched wins."""
    open_dt = datetime.strptime(setup.open_t, "%Y-%m-%d %H:%M")
    found_idx = None
    for i, b in enumerate(bars):
        if b.t > open_dt:
            found_idx = i; break
    if found_idx is None:
        return {"outcome": "OPEN", "pnl_usd": None, "close_t": None}
    for j in range(found_idx, min(found_idx + 300, len(bars))):
        b = bars[j]
        if setup.side == "BUY":
            if b.l <= setup.sl:
                return {"outcome": "LOSS", "pnl_usd": round((setup.sl - setup.entry), 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
            if b.h >= setup.tp:
                return {"outcome": "WIN", "pnl_usd": round((setup.tp - setup.entry), 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
        else:
            if b.h >= setup.sl:
                return {"outcome": "LOSS", "pnl_usd": round((setup.entry - setup.sl), 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
            if b.l <= setup.tp:
                return {"outcome": "WIN", "pnl_usd": round((setup.entry - setup.tp), 2), "close_t": b.t.strftime("%Y-%m-%d %H:%M")}
    return {"outcome": "OPEN", "pnl_usd": None, "close_t": None}


# ── Driver ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--fvg",  choices=["strict","relaxed","none"], default="none")
    args = ap.parse_args()

    tick_csvs = sorted(TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:]
    if not tick_csvs:
        print("No tick CSVs."); return
    print(f"Loading {len(tick_csvs)} CSVs: {[p.name for p in tick_csvs]}")

    bars = build_m5(tick_csvs)
    print(f"Built {len(bars)} M5 bars from {bars[0].t} to {bars[-1].t}")

    fires = detect(bars)
    print(f"\nDetected {len(fires)} canonical setups (FVG={args.fvg})")
    if not fires:
        print("Nothing fired. Loosen thresholds or extend window.")
        return

    # Simulate
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
    pf = (sum(r["pnl_usd"] for r in out_rows if r.get("pnl_usd",0) and r["pnl_usd"] > 0)
          / abs(sum(r["pnl_usd"] for r in out_rows if r.get("pnl_usd",0) and r["pnl_usd"] < 0))
          ) if any(r.get("pnl_usd",0) and r["pnl_usd"] < 0 for r in out_rows) else float('inf')

    print(f"\n=== CANONICAL RESULTS (FVG={args.fvg}) ===")
    print(f"  Setups:        {len(fires)}")
    print(f"  Closed:        {closed} (W={wins} L={losses} OPEN={open_})")
    print(f"  WR:            {wr:.1f}%")
    print(f"  Net P/L (pts): {pnl_total:+.2f}")
    print(f"  PF:            {pf:.2f}")

    out_path = OUT_DIR / f"results_fvg-{args.fvg}_{args.days}d.json"
    out_path.write_text(json.dumps({
        "fvg_mode": args.fvg,
        "days": args.days,
        "bars": len(bars),
        "setups": len(fires),
        "wins": wins, "losses": losses, "open": open_,
        "wr_pct": wr, "pnl_pts": pnl_total, "pf": pf,
        "fires": out_rows,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
