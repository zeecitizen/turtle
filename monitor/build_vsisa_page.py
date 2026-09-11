"""build_vsisa_page.py — the VSISA page: the laws, the expected setup, every setup taken.

Zee, 2026-09-10:
  "Draw the expected setup and write the rules 1 by 1 of what you found to be the laws
   governing our new EA called VSISA"
  "Draw every setup taken by our EA VSISA. so i can visually inspect it. label (make sure
   the labels dont hide the candles behind) -> label each setup with the components of
   the strategy (selling background / etc)"

LABELS NEVER SIT ON THE CANDLES. That is an explicit instruction and it drives the whole
chart layout: the price axis is given deliberate headroom above and below the actual
price range, every annotation is written into that empty band, and a leader line points
from the text down to the bar it describes. Nothing is ever drawn inside the price
envelope except the candles, the entry/SL/TP levels and the exit marker.

WHERE THE SETUPS COME FROM. Two sources, badged differently on every card because they
are not equally trustworthy:
  TESTER — the 124 trades of the seven-month validation court (broker M5 bars)
  LIVE   — trades the attached EA actually took, read from its own log

    py monitor/build_vsisa_page.py --out dashboard/reviews/vsisa.html
    py monitor/build_vsisa_page.py --limit 30        # fewer cards, faster
"""
from __future__ import annotations

import argparse
import base64
import calendar
import html
import io
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt              # noqa: E402
from matplotlib.patches import Rectangle     # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent.parent
BARS_DIR = ROOT / "monitor" / "_vsisa_bars"
REPORT = ROOT / "mt5" / "_tester_runs" / "headless" / "VSISA_500_075455.htm"
LIVE_LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal"
                    r"\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs")
COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

M5 = 300
PRE = 26          # bars drawn before the entry bar
POST = 14         # bars drawn after
SETUP_BARS = 2  # the shipped default

INK = "#101418"
GRID = "#dfe4ea"
UP = "#1b8f5a"
DOWN = "#c8382f"
CLUSTER = "#b3541e"
REACT = "#1f6feb"
MUTED = "#6b7684"


# ─────────────────────────────────────────────────────────── bars ──
def load_bars(path: Path):
    """time -> (o,h,l,c,vol). Times are BROKER time, seconds since epoch."""
    out = {}
    if not path.exists():
        return out
    with open(path, "r", encoding="ascii", errors="replace") as f:
        first = True
        for line in f:
            if first:
                first = False
                if "time_iso" in line:
                    continue
            p = line.rstrip("\n").split(",")
            if len(p) < 6:
                continue
            try:
                d, t = p[0].split(" ")
                Y, M, D = (int(x) for x in d.split("."))
                h, m, s = (int(x) for x in t.split(":"))
                ts = calendar.timegm((Y, M, D, h, m, s))
                out[ts] = (float(p[1]), float(p[2]), float(p[3]), float(p[4]),
                           int(p[5]))
            except (ValueError, IndexError):
                continue
    return out


def bars_from_ticks(glob="shano_ticks_2026-09-*.csv"):
    """September M5 bars built from OUR recorded ticks — the only source that covers
    the days MT5 never stored. Volume is the tick COUNT, which is exactly what the EA
    judges on (iRealVolume returns 0 for gold CFD)."""
    agg = {}
    for f in sorted(COMMON.glob(glob)):
        with open(f, "r", encoding="ascii", errors="replace") as fh:
            first = True
            for line in fh:
                if first:
                    first = False
                    if "ts_broker" in line:
                        continue
                p = line.rstrip("\n").split(",")
                if len(p) < 4:
                    continue
                try:
                    d, t = p[0].split(" ")
                    Y, M, D = (int(x) for x in d.split("."))
                    h, m, s = (int(x) for x in t.split(":"))
                    ts = calendar.timegm((Y, M, D, h, m, s))
                    bid = float(p[2])
                except (ValueError, IndexError):
                    continue
                k = ts // M5 * M5
                b = agg.get(k)
                if b is None:
                    agg[k] = [bid, bid, bid, bid, 1]
                else:
                    if bid > b[1]:
                        b[1] = bid
                    if bid < b[2]:
                        b[2] = bid
                    b[3] = bid
                    b[4] += 1
    return {k: tuple(v) for k, v in agg.items()}


# ──────────────────────────────────────────────────────── trades ──
def read_report(p: Path) -> str:
    for enc in ("utf-16", "utf-16-le", "utf-8"):
        try:
            t = p.read_text(encoding=enc, errors="replace")
            if "<" in t:
                return t
        except Exception:
            continue
    return ""


def cells(row):
    return [re.sub(r"<[^>]+>", "", x).replace("\u00a0", " ").strip()
            for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]


def to_ts(s):
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})", s)
    if not m:
        return None
    v = [int(x) for x in m.groups()]
    return calendar.timegm((v[0], v[1], v[2], v[3], v[4], v[5]))


def num(s):
    try:
        return float(re.sub(r"[^0-9.+-]", "", s))
    except (ValueError, TypeError):
        return 0.0


def tester_trades(p: Path):
    """Join ORDERS (which carry S/L and T/P) with DEALS (entry, exit, profit)."""
    t = read_report(p)
    if not t:
        return []
    sl_tp = {}
    i = t.lower().find(">orders<")
    if i >= 0:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t[i:], re.S | re.I):
            c = cells(row)
            if len(c) < 11 or not c[10].startswith("vsisa_"):
                continue
            ts = to_ts(c[0])
            if ts:
                sl_tp[c[10]] = (ts, num(c[6]), num(c[7]))

    out, pend = [], {}
    i = t.lower().find(">deals<")
    if i < 0:
        return []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t[i:], re.S | re.I):
        c = cells(row)
        if len(c) < 13:
            continue
        ts = to_ts(c[0])
        if ts is None:
            continue
        direction, kind, comment = c[4].lower(), c[3].lower(), c[12]
        if direction == "in" and comment.startswith("vsisa_"):
            s, sl, tp = sl_tp.get(comment, (ts, 0.0, 0.0))
            pend[comment] = {
                "src": "TESTER", "tag": comment, "ts": ts,
                "side": 1 if kind == "buy" else -1,
                "entry": num(c[6]), "sl": sl, "tp": tp,
            }
        elif direction == "out" and pend:
            # the exit closes the oldest still-open decision
            k = sorted(pend, key=lambda x: pend[x]["ts"])[0]
            d = pend.pop(k)
            d["exit_ts"] = ts
            d["exit"] = num(c[6])
            d["profit"] = num(c[8]) + num(c[9]) + num(c[10])
            d["how"] = "TP" if comment.lower().startswith("tp") else (
                       "SL" if comment.lower().startswith("sl") else comment or "closed")
            out.append(d)
    return out


def live_trades():
    """The attached EA prints a complete fire line; that is the record of what it did
    and why, and it needs no broker file to be readable."""
    out = []
    for log in sorted(LIVE_LOG_DIR.glob("2026*.log")):
        try:
            txt = log.read_bytes().decode("utf-16-le", errors="replace")
        except Exception:
            continue
        day = log.stem  # YYYYMMDD
        for line in txt.splitlines():
            if "[VSISA] #" not in line:
                continue
            m = re.search(r"#(\d+)\s+(BUY|SELL)\s+@\s+([\d.]+)\s+SL\s+([\d.]+)\s+"
                          r"\((\d+)\s+pts\)\s+TP\s+([\d.]+)", line)
            if not m:
                continue
            hm = re.match(r"[A-Z]{2}\s+\d+\s+(\d{2}):(\d{2}):(\d{2})", line.strip())
            if not hm:
                continue
            Y, Mo, D = int(day[:4]), int(day[4:6]), int(day[6:8])
            # The terminal logs in PKT; the EA and the charts are on BROKER time, which
            # is PKT minus two hours. Getting this wrong slides every marker two hours
            # along the chart, which is exactly the bug that cost a day on the Diamond.
            ts = calendar.timegm((Y, Mo, D, int(hm.group(1)), int(hm.group(2)),
                                  int(hm.group(3)))) - 2 * 3600
            out.append({
                "src": "LIVE", "tag": "live_%s_%s" % (day, m.group(1)),
                "ts": ts // M5 * M5,
                "side": 1 if m.group(2) == "BUY" else -1,
                "entry": float(m.group(3)), "sl": float(m.group(4)),
                "tp": float(m.group(6)),
                "exit_ts": None, "exit": None, "profit": None, "how": "",
            })
    return out


# ────────────────────────────────────────────── strategy read-out ──
def components(tr, bars):
    """Recompute what the EA saw, so each card can name its parts."""
    t = tr["ts"]
    react = bars.get(t - M5)
    cl = [bars.get(t - M5 * (2 + i)) for i in range(SETUP_BARS)]
    cl = [c for c in cl if c]
    look = [bars[t - M5 * k] for k in range(2 + SETUP_BARS,
                                            2 + SETUP_BARS + 100)
            if (t - M5 * k) in bars]
    d = {"react": react, "setup": cl, "n_look": len(look)}
    if look:
        vols = [b[4] for b in look]
        d["vmax"] = max(vols)
        d["vavg"] = sum(vols) / len(vols)
    if cl:
        d["vsetup"] = sum(c[4] for c in cl) / len(cl)
        if d.get("vmax"):
            d["loudest"] = max(c[4] for c in cl) / d["vmax"]
    if react and d.get("vsetup"):
        d["quiet"] = react[4] / d["vsetup"]

    # THE DISTRIBUTION CHECK. Not a rule in the EA — it is the diagnosis of the first
    # live loss, where the loudest bar of the session closed UP and the next bar closed
    # DOWN (the EA's own LAW 2 calling that volume SELLING) twenty minutes before it
    # bought. Shown on every card so the pattern can be counted, not argued about.
    warn = None
    for k in range(2 + SETUP_BARS, 2 + SETUP_BARS + 8):
        b = bars.get(t - M5 * k)
        nxt = bars.get(t - M5 * (k - 1))
        if not b or not nxt or not d.get("vmax"):
            continue
        if b[4] < 0.85 * d["vmax"]:
            continue
        if tr["side"] > 0 and b[3] > b[0] and nxt[3] < nxt[0]:
            warn = "loud UP bar %d bars back, next bar closed DOWN — LAW 2 reads that " \
                   "volume as SELLING, yet this is a BUY" % k
            break
        if tr["side"] < 0 and b[3] < b[0] and nxt[3] > nxt[0]:
            warn = "loud DOWN bar %d bars back, next bar closed UP — LAW 2 reads that " \
                   "volume as BUYING, yet this is a SELL" % k
            break
    d["warn"] = warn
    return d


# ────────────────────────────────────────────────────── drawing ──
def candles(ax, seq, x0):
    for i, (ts, o, h, l, c) in enumerate(seq):
        x = x0 + i
        col = UP if c >= o else DOWN
        ax.plot([x, x], [l, h], color=col, lw=0.9, solid_capstyle="butt", zorder=3)
        lo, hi = min(o, c), max(o, c)
        ax.add_patch(Rectangle((x - 0.32, lo), 0.64, max(hi - lo, 1e-9),
                               facecolor=col, edgecolor=col, lw=0.6, zorder=4))


def draw_setup(tr, bars, comp):
    """One card's chart. Everything written stays OUT of the price envelope."""
    t = tr["ts"]
    keys = [t + M5 * k for k in range(-PRE, POST + 1)]
    seq, vols, idx = [], [], {}
    for k in keys:
        b = bars.get(k)
        if not b:
            continue
        idx[k] = len(seq)
        seq.append((k, b[0], b[1], b[2], b[3]))
        vols.append(b[4])
    if len(seq) < 8 or t not in idx:
        return None

    fig, (ax, av) = plt.subplots(
        2, 1, figsize=(11.6, 6.3), dpi=104, sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.0], "hspace": 0.06})
    fig.patch.set_facecolor("white")

    candles(ax, seq, 0)

    lows = [s[3] for s in seq]
    highs = [s[2] for s in seq]
    lvl = [x for x in (tr["entry"], tr["sl"], tr["tp"]) if x]
    ylo, yhi = min(lows + lvl), max(highs + lvl)
    span = max(yhi - ylo, 0.01)
    # THE HEADROOM. 30% of the range above and 22% below is reserved as empty space so
    # every label has somewhere to live that is not on top of a candle.
    ax.set_ylim(ylo - span * 0.30, yhi + span * 0.34)
    band_hi = yhi + span * 0.055
    band_lo = ylo - span * 0.055

    e = idx[t]
    # LEVELS. The text is written into a right-hand gutter reserved by set_xlim below,
    # never over the candles; without the gutter matplotlib clipped it at the frame.
    for name, price, col, ls in (("ENTRY", tr["entry"], INK, "-"),
                                 ("STOP", tr["sl"], DOWN, "--"),
                                 ("TARGET", tr["tp"], UP, "--")):
        if not price:
            continue
        # plot(), not axhline(): the line has to STOP before the gutter or it runs
        # straight through its own label.
        ax.plot([-0.8, len(seq) - 0.2], [price, price], color=col, lw=1.0, ls=ls,
                alpha=0.75, zorder=2)
        ax.text(len(seq) + 0.3, price, "%s %.2f" % (name, price), color=col,
                fontsize=8, va="center", ha="left", zorder=6)

    # THE ENTRY BAR gets a vertical rule instead of a tag, so it cannot collide with
    # the setup labels sitting on the bars right beside it.
    ax.axvline(e, color=INK, lw=0.8, ls=":", alpha=0.45, zorder=2)
    ax.text(e, yhi + span * 0.245, "ENTRY", ha="center", va="bottom", fontsize=8.2,
            color=INK, fontweight="bold", zorder=7)

    # C1 / C2 / R sit in the band on the far side of the trade, STAGGERED across two
    # rows: they mark adjacent bars, so a single row overlapped every time.
    def tag(bar_ts, label, colour, above, row):
        if bar_ts not in idx:
            return
        x = idx[bar_ts]
        b = bars[bar_ts]
        y_bar = b[1] if above else b[2]
        off = span * (0.085 + 0.105 * row)
        y_txt = (band_hi + off) if above else (band_lo - off)
        ax.annotate(label, xy=(x, y_bar), xytext=(x, y_txt),
                    ha="center", va="bottom" if above else "top",
                    fontsize=8.2, color=colour, fontweight="bold", zorder=7,
                    arrowprops=dict(arrowstyle="-", color=colour, lw=0.8, alpha=0.5,
                                    shrinkA=1, shrinkB=3))

    below = tr["side"] > 0          # for a BUY the setup extreme is underneath
    for i in range(len(comp["setup"])):
        tag(t - M5 * (2 + i), "C%d" % (i + 1), CLUSTER, not below, i % 2)
    tag(t - M5, "R", REACT, not below, len(comp["setup"]) % 2)

    # the exit, if it is known
    if tr.get("exit_ts"):
        xk = tr["exit_ts"] // M5 * M5
        if xk in idx and tr.get("exit"):
            ax.plot([idx[xk]], [tr["exit"]], marker="X", ms=9,
                    color=UP if (tr.get("profit") or 0) > 0 else DOWN, zorder=8)

    # right gutter for the level labels
    ax.set_xlim(-0.8, len(seq) + 7.5)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(labelsize=7.5, colors=MUTED)

    # ── volume, coloured to match, with the setup bars and reaction called out
    for i, (ts, o, h, l, c) in enumerate(seq):
        col = CLUSTER if ts in [t - M5 * (2 + j) for j in range(len(comp["setup"]))] \
            else (REACT if ts == t - M5 else (UP if c >= o else DOWN))
        a = 1.0 if col in (CLUSTER, REACT) else 0.40
        av.bar(i, vols[i], width=0.66, color=col, alpha=a, zorder=3)
    if comp.get("vmax"):
        av.axhline(comp["vmax"], color=MUTED, lw=0.8, ls=":", alpha=0.8)
        av.text(len(seq) + 0.2, comp["vmax"], " 100 bar max", fontsize=7,
                color=MUTED, va="center")
    if comp.get("vavg"):
        av.axhline(comp["vavg"], color=MUTED, lw=0.8, ls="--", alpha=0.5)
        av.text(len(seq) + 0.2, comp["vavg"], " avg", fontsize=7, color=MUTED,
                va="center")
    av.set_ylim(0, max(vols) * 1.30)
    av.grid(True, color=GRID, lw=0.5, alpha=0.7)
    av.set_axisbelow(True)
    for s in av.spines.values():
        s.set_color(GRID)
    av.tick_params(labelsize=7.5, colors=MUTED)
    av.set_ylabel("ticks", fontsize=7.5, color=MUTED)

    step = max(1, len(seq) // 9)
    av.set_xticks(range(0, len(seq), step))
    av.set_xticklabels([time.strftime("%d %b\n%H:%M", time.gmtime(seq[i][0]))
                        for i in range(0, len(seq), step)], fontsize=7)

    ax.set_title("%s  %s  ·  entry %s broker  ·  %s"
                 % ("BUY" if tr["side"] > 0 else "SELL", tr["tag"],
                    time.strftime("%Y-%m-%d %H:%M", time.gmtime(t)), tr["src"]),
                 fontsize=9.5, color=INK, loc="left", pad=8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def draw_schematic(side):
    """The EXPECTED setup, drawn rather than described. Idealised bars, so the shape is
    unmistakable: effort into the move, then a quiet reaction the other way."""
    up = side > 0
    # (open, close, volume) — a down setup then a quiet up-reaction, or the mirror
    base = 100.0
    if up:
        seq = [(base + 6, base + 5, 30), (base + 5, base + 4.4, 26),
               (base + 4.4, base + 2.0, 88), (base + 2.0, base - 0.6, 96),
               (base - 0.6, base + 1.6, 34), (base + 1.6, base + 4.2, 30)]
    else:
        seq = [(base - 6, base - 5, 30), (base - 5, base - 4.4, 26),
               (base - 4.4, base - 2.0, 88), (base - 2.0, base + 0.6, 96),
               (base + 0.6, base - 1.6, 34), (base - 1.6, base - 4.2, 30)]
    labels = ["", "", "C2", "C1", "R", ""]

    fig, (ax, av) = plt.subplots(2, 1, figsize=(7.4, 4.6), dpi=104, sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1], "hspace": 0.07})
    fig.patch.set_facecolor("white")
    lo = min(min(o, c) for o, c, _ in seq)
    hi = max(max(o, c) for o, c, _ in seq)
    span = hi - lo
    ax.set_ylim(lo - span * 0.55, hi + span * 0.45)

    for i, (o, c, v) in enumerate(seq):
        col = UP if c >= o else DOWN
        ax.plot([i, i], [min(o, c) - span * 0.03, max(o, c) + span * 0.03],
                color=col, lw=1.0, zorder=3)
        ax.add_patch(Rectangle((i - 0.30, min(o, c)), 0.60, abs(c - o) or 1e-9,
                               facecolor=col, edgecolor=col, zorder=4))
        colv = CLUSTER if labels[i].startswith("C") else (
            REACT if labels[i] == "R" else (UP if c >= o else DOWN))
        av.bar(i, v, width=0.62, color=colv,
               alpha=1.0 if labels[i] else 0.4, zorder=3)
        if labels[i]:
            y = max(o, c) + span * 0.10 if up else min(o, c) - span * 0.10
            ty = hi + span * 0.30 if up else lo - span * 0.38
            ax.annotate(labels[i], xy=(i, y), xytext=(i, ty), ha="center",
                        va="bottom" if up else "top", fontsize=9, fontweight="bold",
                        color=CLUSTER if labels[i][0] == "C" else REACT,
                        arrowprops=dict(arrowstyle="-", lw=0.8, alpha=0.5,
                                        color=CLUSTER if labels[i][0] == "C" else REACT))

    entry = seq[4][1]
    stop = (min(min(o, c) for o, c, _ in seq[2:5]) - span * 0.06) if up else \
           (max(max(o, c) for o, c, _ in seq[2:5]) + span * 0.06)
    risk = abs(entry - stop)
    target = entry + 2.5 * risk if up else entry - 2.5 * risk
    ax.set_ylim(min(lo, stop, target) - span * 0.35,
                max(hi, stop, target) + span * 0.35)
    for nm, p, col in (("ENTRY", entry, INK), ("STOP", stop, DOWN),
                       ("TARGET 2.5R", target, UP)):
        ax.axhline(p, color=col, lw=1.0, ls="--" if nm != "ENTRY" else "-", alpha=0.75)
        ax.text(len(seq) - 0.3, p, "  " + nm, color=col, fontsize=8, va="center")

    ax.set_xlim(-0.8, len(seq) + 1.6)
    ax.set_xticks([])
    ax.set_yticks([])
    av.set_xticks([])
    av.set_yticks([])
    av.set_ylabel("volume", fontsize=8, color=MUTED)
    for a in (ax, av):
        for s in a.spines.values():
            s.set_color(GRID)
    ax.set_title("Expected %s setup" % ("BUY" if up else "SELL"),
                 fontsize=10, color=INK, loc="left", pad=6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ─────────────────────────────────────────────────────────── laws ──
LAWS = [
    (1, "Big volume is a QUESTION, never an answer", "STRUCTURAL",
     "Whenever you see a big volume on a bullish candle, never say straight away whether "
     "this is buying or selling. 50% chance it is aggressive buying. 50% chance there is "
     "supply. That means you are not sure.",
     "A loud bar never fires a trade by itself. It only ARMS a setup."),
    (2, "The next bar's REACTION resolves it", "STRUCTURAL",
     "Reaction to that candle will determine whether it was supply or demand.",
     "Big volume down + next bar UP = that volume was BUYING → we buy. Mirror for sells. "
     "This is what picks the side."),
    (3, "The reaction must arrive on LOW volume — THE TRIGGER", "CONFIRMED",
     "The lower the volume on it, the stronger the signal. If a big volume comes, SKIP "
     "it, wait more.",
     "reaction volume ≤ 1.00 × the 2 bar setup's volume. A veto, not a score. Receipt: leaving it "
     "unconstrained scored +$621 against +$1,024 constrained on the same window."),
    (3.5, "\"Low\" means low against the CLIMAX, not against the market", "CONFIRMED",
     "This low volume — do not call it no demand. Call it low supply.",
     "Measured against the setup just seen. Receipt: that reading swept every top row; "
     "measuring against the rolling average appeared once, at rank 22, on 2 trades."),
    (4, "The 2 bar setup: two bars of effort", "CONFIRMED at 2",
     "This three-bar formation is stronger compared to the two-bar.",
     "2 same-direction bars carrying big volume. Receipt: 2-bar beat 3-bar on net in "
     "every sweep; 3-bar wins on profit factor with a third of the trades."),
    (5, "\"Big\" is relative to the recent past — never a VSA band", "CONFIRMED",
     "These bands are misleading. The more you get rid of them, the better you perform. "
     "Compare with the big volumes of the previous two or three days.",
     "Loudest setup bar ≥ 0.80 × the lookback maximum, and every setup bar ≥ 1.20 × "
     "the 100-bar average. Receipt: net is a PLATEAU across lookbacks 30–105, not a "
     "spike — which is what a real effect looks like."),
    (6, "The wick tells aggression from absorption", "REJECTED",
     "If this lower wick had not been there, this could be a supply.",
     "Built as an input, tested, and it loses: WickMode=0 beats both \"require\" and "
     "\"override\" in every paired comparison. Shipped OFF."),
    (7, "Anomaly — tiny spread on huge volume", "REJECTED",
     "Such a small candle, such a big volume — this is the most powerful signal. Bag "
     "holding.",
     "Every pass requiring it collapsed to 1–4 trades; best +$305. Shipped OFF."),
    (8, "Tight stop, R-multiple target", "CONFIRMED at 2.5R + BE",
     "There is no need to keep extra pips of stop loss. Just 2 or 3 pips maximum. Entry "
     "on the closing of that bullish candle.",
     "Stop 30 points beyond the setup extreme (60-point floor), target 2.5R, stop to "
     "entry at 1R. Receipt: breakeven ON +$1,386 vs OFF +$1,213, otherwise identical."),
    (8.5, "His 2–3 pip stop did NOT transfer", "ADAPTED",
     "your SL should be from 3 pips up to 8 pips",
     "Those are FX-major pips. A stop narrower than gold's spread is a guaranteed loss "
     "on entry, so we use 30 points with a 60-point floor. Results were insensitive "
     "across 10/30/50/70, which is reassuring."),
    (9, "Trade with the higher-timeframe trend", "CONFIRMED — biggest single win",
     "That setup comes on H1, and we take entry on M5... take the trade in trend "
     "direction. Do not catch the top.",
     "H1 close now vs 20 bars back. Receipt: the SAME net for HALF the trades and seven "
     "more points of win rate — 27% → 34% at identical geometry."),
    (10, "Never chase — trade the retracement", "NOT IMPLEMENTED",
     "Never chase the market. Always catch the market on a retracement.",
     "Not built into v1.00. The base engine has to earn its keep first."),
    (12, "Falling volume on a fall is NOT automatically bullish", "STRUCTURAL",
     "Rising prices rising volume, falling prices falling volume is bullish — this is "
     "wrong. This is incomplete.",
     "Encoded by making the engine SETUP-FIRST: quiet volume only means anything "
     "straight after effort. The EA never scans for low volume on its own."),
    (13, "The fake break of a level", "REJECTED",
     "the previous support is broken by a pinbar... this is even the strongest setup",
     "Zee's own tier-3 \"strongest\" case. Absent from all 30 top rows of a 336-pass "
     "sweep. Shipped OFF."),
    (0, "The no-supply TEST (his confirmed entry)", "REJECTED after a repair",
     "after this they did a testing, we call it a no supply test... wait for the next bar "
     "to be bullish, then the setup is confirmed",
     "First implementation compared the test bar to the already-quiet reaction bar and "
     "fired ZERO trades in 48 passes — my arithmetic, not his rule. Re-measured against "
     "the climax it fires properly, and then genuinely loses: +$233 best against +$3,213 "
     "for the aggressive entry."),
]

VERDICT_CLASS = {
    "CONFIRMED": "ok", "CONFIRMED at 2": "ok", "CONFIRMED at 2.5R + BE": "ok",
    "CONFIRMED — biggest single win": "ok", "STRUCTURAL": "core", "ADAPTED": "warn",
    "REJECTED": "bad", "REJECTED after a repair": "bad", "NOT IMPLEMENTED": "muted",
}


# ─────────────────────────────────────────────────────────── html ──
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f4f6f8;color:#101418;
 font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:26px 18px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.2px}
.sub{color:#6b7684;margin:0 0 22px;font-size:13.5px}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;
 font-weight:700;letter-spacing:.4px;vertical-align:middle}
.b-live{background:#e8f5ee;color:#1b8f5a}.b-test{background:#eef2f7;color:#55606e}
.b-win{background:#e8f5ee;color:#1b8f5a}.b-loss{background:#fdeceb;color:#c8382f}
.card{background:#fff;border:1px solid #e3e8ee;border-radius:12px;padding:16px 18px;
 margin:0 0 16px;box-shadow:0 1px 2px rgba(16,20,24,.04)}
.card h3{margin:0 0 10px;font-size:15px}
.sec{margin:34px 0 14px;font-size:12px;font-weight:700;letter-spacing:1.2px;
 color:#6b7684;text-transform:uppercase}
img{max-width:100%;height:auto;display:block;border-radius:8px}
table.k{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}
table.k td{padding:6px 8px;border-bottom:1px solid #eef1f5;vertical-align:top}
table.k td:first-child{color:#6b7684;width:210px;white-space:nowrap}
.law{display:flex;gap:14px;align-items:flex-start;padding:14px 0;
 border-bottom:1px solid #eef1f5}
.law:last-child{border-bottom:0}
.lawn{flex:0 0 42px;font-weight:800;font-size:17px;color:#c9d1da;text-align:right}
.lawb{flex:1}
.lawt{font-weight:700;margin-bottom:4px}
.quote{border-left:3px solid #dfe4ea;padding:2px 0 2px 11px;margin:8px 0;color:#55606e;
 font-style:italic;font-size:13px}
.how{font-size:13px;color:#39424e}
.v{display:inline-block;padding:2px 8px;border-radius:99px;font-size:10.5px;
 font-weight:800;letter-spacing:.4px;margin-left:8px}
.v.ok{background:#e8f5ee;color:#1b8f5a}.v.bad{background:#fdeceb;color:#c8382f}
.v.core{background:#eef2f7;color:#55606e}.v.warn{background:#fff5e6;color:#a1620a}
.v.muted{background:#f2f4f7;color:#8b95a1}
.warn{background:#fff8e8;border:1px solid #f2dcae;color:#8a5d00;border-radius:8px;
 padding:9px 12px;margin-top:12px;font-size:13px}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0 2px;font-size:12.5px;
 color:#55606e}
.legend b{color:#101418}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;
 vertical-align:-1px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:860px){.grid2{grid-template-columns:1fr}}
.note{color:#6b7684;font-size:12.5px;margin-top:10px}
"""


def esc(s):
    return html.escape(str(s))


def card_html(tr, comp, png):
    side = "BUY" if tr["side"] > 0 else "SELL"
    bg = ("SELLING BACKGROUND — the 2 bar setup: two down bars on big volume, effort DOWN that failed"
          if tr["side"] > 0 else
          "BUYING BACKGROUND — the 2 bar setup: two up bars on big volume, effort UP that failed")
    react_txt = ("REACTION bullish — supply is gone" if tr["side"] > 0
                 else "REACTION bearish — demand is gone")
    risk = abs(tr["entry"] - tr["sl"]) * 100 if tr["sl"] else 0
    rows = [
        ("Setup", "<b>%s</b> · %s" % (side, esc(bg))),
        ("Reaction (R)", "%s%s" % (
            esc(react_txt),
            (" · volume <b>%.2f×</b> the setup %s" % (
                comp["quiet"],
                "— QUIET, trigger satisfied" if comp["quiet"] <= 1.0 else "— LOUD")
             ) if comp.get("quiet") else "")),
    ]
    if comp.get("loudest") and comp.get("vsetup"):
        rows.append(("2 bar setup volume (C1,C2)",
                     "avg <b>%d</b> ticks · loudest bar <b>%.2f×</b> the lookback max "
                     "(needs ≥ 0.80×)" % (comp["vsetup"], comp["loudest"])))
    if comp.get("vmax"):
        rows.append(("Recent yardstick",
                     "lookback max <b>%d</b> · average <b>%d</b>"
                     % (comp["vmax"], comp["vavg"])))
    if risk:
        rows.append(("Geometry",
                     "risk <b>%.0f points</b> ($%.2f at 0.10 lots) · stop %.2f · "
                     "target %.2f (2.5R)" % (risk, risk * 0.10, tr["sl"], tr["tp"])))
    if tr.get("profit") is not None:
        rows.append(("Outcome", "<b>%s</b> at %.2f · <b>%+.2f</b>"
                     % (esc(tr.get("how") or ""), tr.get("exit") or 0, tr["profit"])))
    else:
        rows.append(("Outcome", "<i>open / not recorded</i>"))

    badge = ('<span class="badge b-live">LIVE</span>' if tr["src"] == "LIVE"
             else '<span class="badge b-test">TESTER</span>')
    res = ""
    if tr.get("profit") is not None:
        res = ' <span class="badge %s">%+.2f</span>' % (
            "b-win" if tr["profit"] > 0 else "b-loss", tr["profit"])
    warn = ('<div class="warn"><b>Distribution warning:</b> %s</div>' % esc(comp["warn"])
            ) if comp.get("warn") else ""

    return (
        '<div class="card" id="%s">'
        '<h3>%s &nbsp;%s%s</h3>'
        '<img src="data:image/png;base64,%s" alt="setup">'
        '<div class="legend">'
        '<span><span class="dot" style="background:%s"></span><b>C1 C2</b> the 2 bar setup</span>'
        '<span><span class="dot" style="background:%s"></span><b>R</b> reaction</span>'
        '<span><span class="dot" style="background:%s"></span>up bar</span>'
        '<span><span class="dot" style="background:%s"></span>down bar</span>'
        '<span>dotted line = lookback volume max</span></div>'
        '<table class="k">%s</table>%s</div>'
        % (esc(tr["tag"]),
           esc(time.strftime("%a %d %b %Y  %H:%M", time.gmtime(tr["ts"]))) + " broker",
           badge, res, png, CLUSTER, REACT, UP, DOWN,
           "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(a), b) for a, b in rows),
           warn))


def build(out_path: Path, limit=0):
    t0 = time.time()
    bars = load_bars(BARS_DIR / "vsisa_bars_xauusd.csv")
    print("[vsisa-page] %d broker M5 bars" % len(bars), flush=True)
    sep = bars_from_ticks()
    print("[vsisa-page] %d September M5 bars from our ticks" % len(sep), flush=True)
    merged = dict(bars)
    for k, v in sep.items():
        merged.setdefault(k, v)

    trades = tester_trades(REPORT) + live_trades()
    trades.sort(key=lambda x: -x["ts"])
    print("[vsisa-page] %d trades (%d live)"
          % (len(trades), sum(1 for t in trades if t["src"] == "LIVE")), flush=True)
    if limit:
        trades = trades[:limit]

    cards, drawn, skipped = [], 0, 0
    for tr in trades:
        comp = components(tr, merged)
        png = draw_setup(tr, merged, comp)
        if not png:
            skipped += 1
            continue
        cards.append(card_html(tr, comp, png))
        drawn += 1
        if drawn % 20 == 0:
            print("[vsisa-page]   %d drawn…" % drawn, flush=True)

    law_rows = []
    for n, title, verdict, quote, how in LAWS:
        num_txt = "—" if n == 0 else ("%g" % n)
        law_rows.append(
            '<div class="law"><div class="lawn">%s</div><div class="lawb">'
            '<div class="lawt">%s<span class="v %s">%s</span></div>'
            '<div class="quote">%s</div><div class="how">%s</div></div></div>'
            % (esc(num_txt), esc(title), VERDICT_CLASS.get(verdict, "muted"),
               esc(verdict), esc(quote), esc(how)))

    live_n = sum(1 for t in trades if t["src"] == "LIVE")
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>VSISA — laws and every setup</title><style>%s</style></head><body>"
        "<div class='wrap'>"
        "<h1>VSISA</h1>"
        "<p class='sub'>Volume Spread Imbalance Shift Analysis · magic 88201 · "
        "XAUUSD M5 · built %s PKT</p>"

        "<div class='sec'>1 · The expected setup</div>"
        "<div class='card'><div class='grid2'>"
        "<div><img src='data:image/png;base64,%s' alt='buy schematic'></div>"
        "<div><img src='data:image/png;base64,%s' alt='sell schematic'></div>"
        "</div>"
        "<table class='k'>"
        "<tr><td>C1, C2 — the 2 bar setup</td><td>Two bars closing the SAME way on big "
        "volume. That is <b>effort</b>: somebody is transacting hard. For a BUY they "
        "close DOWN (the selling background); for a SELL they close UP.</td></tr>"
        "<tr><td>R — the reaction</td><td>The next bar closes the OTHER way. This names "
        "which side the big volume really was.</td></tr>"
        "<tr><td>The trigger</td><td>R arrives on <b>LOW volume</b> — no louder than the "
        "the setup. The resting orders are gone; price can now travel cheaply. If R is "
        "loud the setup is <b>cancelled</b>, not weakened.</td></tr>"
        "<tr><td>Entry</td><td>At R's close.</td></tr>"
        "<tr><td>Stop</td><td>30 points beyond the extreme the setup defended "
        "(60-point floor).</td></tr>"
        "<tr><td>Target</td><td>2.5 × risk, with the stop moved to entry at 1R.</td></tr>"
        "<tr><td>Filter</td><td>Only in the direction of the H1 trend.</td></tr>"
        "</table>"
        "<div class='note'>Volume here is the <b>tick count</b> per M5 bar. Measured, "
        "not assumed: iRealVolume returns 0 reads for gold CFD and the tick-count "
        "fallback was used 8,006,496 times over the seven-month court.</div>"
        "</div>"

        "<div class='sec'>2 · The laws, one by one</div>"
        "<div class='card'>%s</div>"

        "<div class='sec'>3 · Every setup — %d drawn (%d live, %d tester)</div>"
        "<div class='card'><div class='note'>Labels sit in the empty margin above and "
        "below the price, with a leader line down to the bar — nothing is written over "
        "a candle. <b>C1/C2</b> mark the 2 bar setup, <b>R</b> the reaction, and the volume "
        "panel highlights those same bars against the lookback maximum (dotted) and "
        "average (dashed). Tester setups are drawn on broker M5 bars; September ones on "
        "our own recorded ticks, which have gaps.</div></div>"
        "%s"
        "</div></body></html>"
        % (CSS, time.strftime("%Y-%m-%d %H:%M"),
           draw_schematic(1), draw_schematic(-1),
           "".join(law_rows),
           drawn, live_n, drawn - live_n,
           "".join(cards)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    print("[vsisa-page] %d cards, %d skipped (no bars), %.1f MB, %.0fs -> %s"
          % (drawn, skipped, out_path.stat().st_size / 1e6, time.time() - t0, out_path),
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dashboard" / "reviews" / "vsisa.html"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    build(Path(a.out), a.limit)


if __name__ == "__main__":
    main()
