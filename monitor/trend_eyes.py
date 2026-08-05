"""trend_eyes.py — the ghost's compass: HH/HL/LH/LL swing structure, standalone.

Zee 2026-08-04: "let's build the HH HL LH LL feature set in a separate code which is a
python script that checks such trend and outputs whether we can take a trade or not..
we'll perfect it till it detects trends awesomely and then plug it in to our ghost."

Standalone on purpose: NOT imported by the matcher yet. Grade it against the chart with
your own eyes; every threshold below is tunable. When it reads trends the way Zee reads
them, one import line plugs it into oanda_live_matcher ([[ghost-lamp-doctrine]]).

The classic reading, exactly as taught:
    swing highs rising  AND swing lows rising   -> UPTREND    (only BUY allowed)
    swing highs falling AND swing lows falling  -> DOWNTREND  (only SELL allowed)
    anything mixed / flat                       -> RANGE      (no trade — chop is noise;
                                                  both sides of a box lose)

Usage (live OANDA csv):
    py monitor/trend_eyes.py                 # verdict now + the swings behind it
    py monitor/trend_eyes.py --swings 10     # more swing history
    py monitor/trend_eyes.py --replay 180    # verdict at every bar of the last 3 hours
                                             #   (grade me: where am I wrong?)
"""
from __future__ import annotations
import csv, sys
from datetime import datetime, timezone
from pathlib import Path

CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")

# ── the knobs to perfect ──────────────────────────────────────────────────────
METHOD    = "fractal"  # "fractal" (K bars each side) or "zigzag" (reversal threshold —
                       # from the Shreyas trendlines article; confirms faster in fast runs)
PIVOT_K   = 3     # fractal: a swing high = the highest high of K bars on EACH side.
                  # Smaller = more, faster swings; larger = only the big landmarks.
ZZ_TH_PT  = 2.0   # zigzag: a swing is confirmed once price reverses this many points
                  # from the running extreme (their 2% stock threshold, in gold points).
EPS_PT    = 0.30  # two swings closer than this are "equal", not higher/lower —
                  # stops 10-cent noise from flipping the trend call.
SLOPE_N   = 30    # bars for the regression slope — the dying-light meter (pts/bar).
MAX_LOOKB = 180   # how far back (bars) we hunt for swings before giving up.


class Swing:
    __slots__ = ("i", "t", "price", "kind", "label")
    def __init__(self, i, t, price, kind):
        self.i, self.t, self.price, self.kind, self.label = i, t, price, kind, "?"


def load_bars(path=CF):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc)
                         .replace(tzinfo=None),
                         float(r["high"]), float(r["low"]), float(r["close"]),
                         float(r.get("volume", 0))))
    rows.sort()
    return rows


def _swings_fractal(bars, n):
    lo = max(PIVOT_K, n - MAX_LOOKB)
    out = []
    for i in range(lo, n - PIVOT_K):
        hi = bars[i][1]; lw = bars[i][2]
        if all(hi > bars[j][1] for j in range(i - PIVOT_K, i + PIVOT_K + 1) if j != i):
            out.append(Swing(i, bars[i][0], hi, "H"))
        if all(lw < bars[j][2] for j in range(i - PIVOT_K, i + PIVOT_K + 1) if j != i):
            out.append(Swing(i, bars[i][0], lw, "L"))
    return out


def _swings_zigzag(bars, n):
    """Reversal-threshold pivots (the article's engine, in points not percent): ride the
    move, and the moment price backs off ZZ_TH_PT from the running extreme, that extreme
    becomes a confirmed swing. Faster confirmation than fractal in strong runs; quieter
    in chop."""
    lo = max(1, n - MAX_LOOKB)
    out = []
    ext_i, ext_hi, ext_lo = lo, bars[lo][1], bars[lo][2]
    direction = 0                                  # 0 unknown, +1 seeking high, -1 seeking low
    for i in range(lo + 1, n):
        hi, lw = bars[i][1], bars[i][2]
        if direction >= 0:
            if hi > ext_hi: ext_hi, ext_i = hi, i
            if ext_hi - lw >= ZZ_TH_PT:
                out.append(Swing(ext_i, bars[ext_i][0], ext_hi, "H"))
                direction, ext_lo, ext_i = -1, lw, i
        if direction <= 0:
            if lw < ext_lo: ext_lo, ext_i = lw, i
            if hi - ext_lo >= ZZ_TH_PT:
                out.append(Swing(ext_i, bars[ext_i][0], ext_lo, "L"))
                direction, ext_hi, ext_i = 1, hi, i
    return out


def slope_of(bars, upto=None):
    """The dying-light meter: least-squares slope of the last SLOPE_N closes, pts/bar.
    (The article's 'machine learning' is exactly this line; no sklearn needed.)"""
    n = upto if upto is not None else len(bars)
    ys = [b[3] for b in bars[max(0, n - SLOPE_N):n]]
    m = len(ys)
    if m < 5: return 0.0
    xbar = (m - 1) / 2
    ybar = sum(ys) / m
    num = sum((x - xbar) * (y - ybar) for x, y in enumerate(ys))
    den = sum((x - xbar) ** 2 for x in range(m))
    return num / den


def find_swings(bars, upto=None):
    """Confirmed pivots only — an unconfirmed swing is a guess, and the ghost does not
    raid on guesses. Engine chosen by METHOD."""
    n = upto if upto is not None else len(bars)
    out = _swings_zigzag(bars, n) if METHOD == "zigzag" else _swings_fractal(bars, n)
    # label each swing against the previous swing of its own kind
    prev = {}
    for s in out:
        p = prev.get(s.kind)
        if p is None:
            s.label = s.kind
        elif s.kind == "H":
            s.label = "HH" if s.price > p.price + EPS_PT else ("LH" if s.price < p.price - EPS_PT else "=H")
        else:
            s.label = "HL" if s.price > p.price + EPS_PT else ("LL" if s.price < p.price - EPS_PT else "=L")
        prev[s.kind] = s
    return out


def read_trend(bars, upto=None):
    """The verdict. Returns dict: trend, allowed sides, and the two swing pairs it used."""
    swings = find_swings(bars, upto)
    highs = [s for s in swings if s.kind == "H"][-2:]
    lows = [s for s in swings if s.kind == "L"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return dict(trend="UNKNOWN", allow=[], why="fewer than 2 confirmed swings per side",
                    swings=swings)
    hh = highs[1].price > highs[0].price + EPS_PT
    lh = highs[1].price < highs[0].price - EPS_PT
    hl = lows[1].price > lows[0].price + EPS_PT
    ll = lows[1].price < lows[0].price - EPS_PT
    if hh and hl:
        return dict(trend="UPTREND", allow=["BUY"], why="HH + HL", swings=swings)
    if lh and ll:
        return dict(trend="DOWNTREND", allow=["SELL"], why="LH + LL", swings=swings)
    return dict(trend="RANGE", allow=[],
                why=f"mixed: highs {'HH' if hh else 'LH' if lh else '='} "
                    f"/ lows {'HL' if hl else 'LL' if ll else '='}", swings=swings)


def trend_allows(bars, side, upto=None):
    """THE PLUG for the ghost (when Zee approves): True if this side may trade now."""
    return side in read_trend(bars, upto)["allow"]


SLANT_EPS = 0.03   # pts/bar — flatter than this, the peak-line is "flat" -> RANGE


def auto_call(bars, upto=None):
    """AUTO mode (Zee 2026-08-04): "auto should be the gradient / slant of the line
    connecting the PEAKS of the humps. slanting upwards -> uptrend, downwards ->
    downtrend." Least-squares line through the last 3 confirmed swing highs; its
    slope sign is the verdict, near-flat is RANGE (the ghost waits)."""
    swings = find_swings(bars, upto)
    hs = [s for s in swings if s.kind == "H"][-3:]
    if len(hs) < 2:
        return dict(trend="RANGE", allow=[], slant=0.0, why="fewer than 2 peaks")
    xs = [s.i for s in hs]; ys = [s.price for s in hs]
    xb = sum(xs) / len(xs); yb = sum(ys) / len(ys)
    den = sum((x - xb) ** 2 for x in xs) or 1
    sl = sum((x - xb) * (y - yb) for x, y in zip(xs, ys)) / den
    n = upto if upto is not None else len(bars)
    # THE GUARD LOW / GUARD HIGH (Zee 2026-08-04): "until previous lows are safe we
    # can keep buying.. if there were two previous lows in a row, the deepest point,
    # the lowest low is considered.. we stop buying if the last low is broken —
    # we say the trend has shifted from BUYS now." Mirror with highs for SELLs.
    recent_low = min(bars[k][2] for k in range(max(0, n - 2), n))
    recent_high = max(bars[k][1] for k in range(max(0, n - 2), n))
    # EARLY-TREND ON GUARD BREAK (Zee 2026-08-05): "the last higher high was broken,
    # with a new high — that's a sign of uptrend." A broken guard doesn't mean
    # no-man's-land; it means the trend has SHIFTED. The confirmed-peak slant lags a
    # fresh V-turn by design (peaks need 3 closed bars); the guard break is the
    # earliest honest signal of the flip, so it takes command until the peaks catch up.
    if sl > SLANT_EPS:
        lows = [s for s in find_swings(bars, upto) if s.kind == "L"][-2:]
        guard = min(s.price for s in lows) if lows else None
        if guard is not None and recent_low < guard:
            return dict(trend="DOWNTREND", allow=["SELL"], slant=sl,
                        why=f"EARLY SHIFT: guard low {guard:.2f} broken by a new low "
                            f"— trend shifted from BUYS")
        return dict(trend="UPTREND", allow=["BUY"], slant=sl,
                    why=f"peak-line slants up {sl:+.3f} pts/bar"
                        + (f", guard low {guard:.2f} safe" if guard else ""))
    if sl < -SLANT_EPS:
        guard = max(s.price for s in hs[-2:]) if len(hs) >= 2 else None
        if guard is not None and recent_high > guard:
            return dict(trend="UPTREND", allow=["BUY"], slant=sl,
                        why=f"EARLY SHIFT: guard high {guard:.2f} broken by a new high "
                            f"— trend shifted from SELLS")
        return dict(trend="DOWNTREND", allow=["SELL"], slant=sl,
                    why=f"peak-line slants down {sl:+.3f} pts/bar"
                        + (f", guard high {guard:.2f} safe" if guard else ""))
    return dict(trend="RANGE", allow=[], slant=sl,
                why=f"peak-line flat ({sl:+.3f} pts/bar)")


def _print_state(bars, n_swings):
    r = read_trend(bars)
    px = bars[-1][3]
    sl = slope_of(bars)
    light = ("STRONG " + ("UP" if sl > 0 else "DOWN")) if abs(sl) >= 0.10 else "faint"
    print(f"\n  [{METHOD}]  price {px:.2f}   TREND: {r['trend']}   ({r['why']})")
    print(f"  slope {sl:+.3f} pts/bar — light: {light}")
    print(f"  allowed: {', '.join(r['allow']) if r['allow'] else 'NO TRADE — stand aside'}\n")
    print("  recent swings (oldest first):")
    for s in r["swings"][-n_swings:]:
        print(f"    {s.t:%H:%M}Z  {s.kind}  {s.price:9.2f}   {s.label}")


def _replay(bars, back):
    print(f"\n  verdict at each bar, last {back} bars — grade me against the chart:")
    last = None
    for u in range(len(bars) - back, len(bars) + 1):
        r = read_trend(bars, upto=u)
        if r["trend"] != last:
            t = bars[u - 1][0]
            print(f"    {t:%H:%M}Z  {bars[u-1][3]:9.2f}   -> {r['trend']:9s} ({r['why']})")
            last = r["trend"]


def session_label():
    """Zee 2026-08-04: 'at 6:00 PM Pakistani time there begins the NY session…
    ideal time to make trades, lots of good moves expected.' PKT = UTC+5; the NY
    window runs 18:00 PKT until 01:00 PKT."""
    from datetime import timedelta
    hh = (datetime.now(timezone.utc) + timedelta(hours=5)).hour
    if hh >= 18 or hh < 1:
        return ("NY SESSION LIVE (opened 6:00 PM PKT) — IDEAL TIME TO TRADE: "
                "lots of good moves expected", "#0a7d33")
    return ("quiet hours — NY session (the ideal window) opens 6:00 PM PKT", "#86868b")


def draw(bars, back=120, out=None):
    """CAMEL HUMPS (Zee 2026-08-04, drawn by hand on the chart): one red line riding
    over the swings so the eye instantly sees whether the humps walk up or down.
    The line is the swing polyline — every confirmed H and L in time order."""
    import matplotlib
    matplotlib.use("Agg")          # headless: safe from GUI worker threads (camel_gui)
    import pandas as pd, mplfinance as mpf
    out = out or (Path(__file__).parent / "setup_labels" / "camel_humps.png")
    n = len(bars); lo = max(0, n - back)
    seg = bars[lo:]
    # Chart axis in KARACHI time (Zee 2026-08-05: TV + computer + cockpit must agree).
    # Internal bar times stay UTC everywhere else — only the DISPLAY shifts.
    from datetime import timedelta as _td
    idx = pd.DatetimeIndex([b[0] + _td(hours=5) for b in seg])
    df = pd.DataFrame({"Open": [b[3] for b in seg], "High": [b[1] for b in seg],
                       "Low": [b[2] for b in seg], "Close": [b[3] for b in seg],
                       "Volume": [b[4] if len(b) > 4 else 0 for b in seg]}, index=idx)
    # rebuild Open properly: previous close is close enough for M1 rendering
    df["Open"] = df["Close"].shift(1).fillna(df["Close"])
    swings = [s for s in find_swings(bars) if s.i >= lo + 1]
    swings.sort(key=lambda s: s.i)
    humps = [(bars[s.i][0] + _td(hours=5), s.price) for s in swings]
    r = read_trend(bars)
    a = auto_call(bars)
    # THE SLANT LINE (Zee): fitted through the last 3 peaks, extended to the current
    # bar, coloured by its own verdict — green up, red down, blue near-horizontal.
    lines, colors, widths = [], [], []
    if len(humps) >= 2:
        lines.append(humps); colors.append("#868e96"); widths.append(2.0)
    hs = [s for s in swings if s.kind == "H"][-3:]
    if len(hs) >= 2:
        xs = [s.i for s in hs]; ys = [s.price for s in hs]
        xb = sum(xs) / len(xs); yb = sum(ys) / len(ys)
        den = sum((x - xb) ** 2 for x in xs) or 1
        m = sum((x - xb) * (y - yb) for x, y in zip(xs, ys)) / den
        c = yb - m * xb
        x0, x1 = hs[0].i, n - 1
        lines.append([(bars[x0][0] + _td(hours=5), m * x0 + c),
                      (bars[x1][0] + _td(hours=5), m * x1 + c)])
        # Line colour = the SLOPE's geometry (Zee: blue is ONLY for near-horizontal).
        # The verdict (which may be RANGE because a guard broke) lives in the title.
        colors.append("#2f9e44" if a["slant"] > SLANT_EPS else
                      "#e03131" if a["slant"] < -SLANT_EPS else "#4dabf7")
        widths.append(4.0)
    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    kw = dict(type="candle", style=style, figsize=(16, 9), volume=True,
              title=f"camel humps [{METHOD}] — structure: {r['trend']}  |  "
                    f"AUTO: {a['trend']} ({a['why']})")
    if lines:
        kw["alines"] = dict(alines=lines, colors=colors, linewidths=widths, alpha=0.9)
    # THE UHV BOX (Zee): the moment a UHV forms in a retracement, two black lines
    # frame it — top = the lamp, bottom = the sweep line. DASHED while the sweep is
    # pending, SOLID once the apparition is concrete.
    diamonds_png = None
    try:
        import json as _json
        wd = _json.loads((CF.parent / "case_watch.json").read_text(encoding="ascii"))
        ls = "-" if wd.get("swept") else "--"
        kw["hlines"] = dict(hlines=[wd["level"], wd["sweep"]], colors=["k", "k"],
                            linestyle=ls, linewidths=[2.0, 2.0], alpha=0.9)
        kw["title"] = kw["title"] + (
            "  |  Law of Conviction: SATISFIED" if wd.get("swept")
            else "  |  Law of Conviction: pending") + (
            "  +  2nd Law (NS/ND)" if wd.get("law2") else "") + (
            "  +  3rd Law (EMA5)" if wd.get("law3") else "") + (
            "  +  4th Law (RSI div)" if wd.get("law4") else "") + (
            "  +  5th Law (wick/vol)" if wd.get("law5") else "")
        # 💎 DIAMONDS OF CONVICTION (Zee): one diamond above the box per satisfied
        # Law. "two diamonds means two convictions.. the more conviction we have the
        # more diamonds we add." Rendered with Zee's own diamond.png (2026-08-05,
        # "so our diamonds look coolest"); gold scatter only as fallback.
        n_laws = (int(bool(wd.get("swept"))) + int(bool(wd.get("law2")))
                  + int(bool(wd.get("law3"))) + int(bool(wd.get("law4")))
                  + int(bool(wd.get("law5"))))
        if n_laws:
            _dpos = [len(df) - 3 - d * 2 for d in range(n_laws)]
            _dpos = [p for p in _dpos if 0 <= p < len(df)]
            _dtop = max(wd["level"], wd["sweep"]) + 0.6
            dpng = Path(__file__).parent / "setup_labels" / "diamond.png"
            if dpng.exists():
                diamonds_png = (str(dpng), _dpos, _dtop)
            else:
                ys = [float("nan")] * len(df)
                for p in _dpos: ys[p] = _dtop
                kw["addplot"] = mpf.make_addplot(ys, type="scatter", markersize=160,
                                                 marker="D", color="#f5b301",
                                                 edgecolors="#8a6d00")
    except Exception:
        pass
    kw["returnfig"] = True
    fig, _axes = mpf.plot(df, **kw)
    if diamonds_png:
        from matplotlib.offsetbox import OffsetImage, AnnotationBbox
        import matplotlib.image as mimg
        gem = mimg.imread(diamonds_png[0])
        zoom = 34.0 / max(gem.shape[0], gem.shape[1])   # ~34px tall on the figure
        ax = _axes[0]
        for p in diamonds_png[1]:
            ax.add_artist(AnnotationBbox(OffsetImage(gem, zoom=zoom),
                                         (p, diamonds_png[2]), frameon=False))
    # session banner beneath the chart (Zee: mark the NY window as the ideal time)
    stext, scol = session_label()
    fig.text(0.5, 0.005, stext, ha="center", fontsize=13, fontweight="bold", color=scol)
    fig.savefig(str(out), dpi=110, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    print(f"  camel humps drawn -> {out}   structure: {r['trend']}   slant: {a['trend']}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--method" in args:
        METHOD = args[args.index("--method") + 1]
    bars = load_bars()
    if "--draw" in args:
        i = args.index("--draw")
        back = int(args[i + 1]) if i + 1 < len(args) and args[i + 1].isdigit() else 120
        draw(bars, back)
    elif "--replay" in args:
        _replay(bars, int(args[args.index("--replay") + 1]))
    else:
        n = int(args[args.index("--swings") + 1]) if "--swings" in args else 6
        _print_state(bars, n)
