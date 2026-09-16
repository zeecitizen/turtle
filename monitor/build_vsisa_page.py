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
# AXI, AND THE CORRECTED BUILD (2026-09-15). The page used to draw the old
# Blueberry seven-month run, which used a FIXED 2-bar setup, a fixed volume
# lookback and the stop under the whole setup. All three are wrong now, so it
# was drawing setups the EA would no longer take. Both sources below are Axi
# and both are the current logic.
# v1.20 AS SHIPPED, Jan 1 -> Sep 16 2026, Axi real ticks, 0.15 lots. Every card below is
# a trade this exact build took - the fake break is ON, so these are only the setups that
# swept a recent extreme and closed back inside it.
REPORT = ROOT / "mt5" / "_tester_runs" / "axi" / "AXI_bt_073213.htm"
LIVE_LOG_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal"
                    r"\6FBEE76C719DC78AB2AE839B5A0C7442\MQL5\Logs")
COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

M5 = 300
PRE = 26          # bars drawn before the entry bar
POST = 14         # bars drawn after
# The run is COUNTED now, not fixed - these mirror InpSetupMin / InpSetupMax and
# the swing yardstick, so a card marks exactly the bars the EA judged.
SETUP_MIN, SETUP_MAX = 2, 10
SWING_PIVOT, SWING_MIN, SWING_CAP = 3, 5, 200

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
    """Recompute what the EA saw. The run length and the volume window are DERIVED the
    same way the EA derives them, so a card marks the bars it actually judged rather
    than a fixed two."""
    t = tr["ts"]
    side = tr["side"]
    react = bars.get(t - M5)

    # THE RUN: walk back while the bars keep closing the setup's way.
    run = []
    for k in range(2, 2 + SETUP_MAX):
        b = bars.get(t - M5 * k)
        if not b:
            break
        ours = (b[3] < b[0]) if side > 0 else (b[3] > b[0])
        if not ours:
            break
        run.append(b)
    nb = max(SETUP_MIN, len(run))
    d = {"react": react, "setup": run, "nb": nb}

    # THE SWING: back to the pivot that started this leg.
    first = 2 + nb
    span = SWING_CAP
    for k in range(first + SWING_PIVOT, first + SWING_CAP):
        piv = True
        for q in range(1, SWING_PIVOT + 1):
            a = bars.get(t - M5 * k)
            l = bars.get(t - M5 * (k - q))
            r = bars.get(t - M5 * (k + q))
            if not a or not l or not r:
                piv = False
                break
            if side > 0:
                if a[1] <= l[1] or a[1] <= r[1]:
                    piv = False
            else:
                if a[2] >= l[2] or a[2] >= r[2]:
                    piv = False
            if not piv:
                break
        if piv and (k - first + 1) >= SWING_MIN:
            span = k - first + 1
            break
    d["span"] = span

    look = [bars[t - M5 * k] for k in range(first, first + span)
            if (t - M5 * k) in bars]
    if look:
        vols = [b[4] for b in look]
        d["vmax"] = max(vols)
        d["vavg"] = sum(vols) / len(vols)
        d["n_look"] = len(look)
    if run:
        d["vsetup"] = sum(b[4] for b in run) / len(run)
        if d.get("vmax"):
            d["loudest"] = max(b[4] for b in run) / d["vmax"]
    if react and d.get("vsetup"):
        d["quiet"] = react[4] / d["vsetup"]

    # THE READ (replaces the old "Distribution warning", 2026-09-17).
    #
    # Zee: "can we maybe make that more informative / relevant?" — and measuring it first
    # showed the old warning was not merely vague, it was BACKWARDS. It flagged a loud bar
    # whose next bar closed the other way as suspicious; across the 54 v1.20 setups the
    # flagged ones ran 73% WR and +$227 a trade against 52% and +$74 for the unflagged.
    # Of course they did: a loud bar followed by a reversal IS the absorption this strategy
    # is built on. It was labelling the best setups as a defect.
    #
    # What follows instead is the four things that actually decide a v1.20 trade, in the
    # EA's own terms, so the card can be checked against the laws by eye.
    read = []

    # 1. THE SWEEP - LAW 13, now the strongest filter on the project.
    line = None
    look = [bars[t - M5 * k] for k in range(first, first + 30) if (t - M5 * k) in bars]
    if look and react:
        if side > 0:
            line = min(b[2] for b in look)
            ext = min(b[2] for b in d["setup"]) if d["setup"] else react[2]
            if ext < line:
                read.append("swept the 30-bar low by %.2f and closed back above it"
                            % (line - ext))
        else:
            line = max(b[1] for b in look)
            ext = max(b[1] for b in d["setup"]) if d["setup"] else react[1]
            if ext > line:
                read.append("swept the 30-bar high by %.2f and closed back inside"
                            % (ext - line))

    # 2. HOW QUIET the reaction was - LAW 3, the trigger itself.
    if d.get("quiet") is not None:
        read.append("reaction %.2fx the setup's volume" % d["quiet"])

    # 3. HOW FAR IT RAN, in R - the only unit the exit understands.
    risk = abs(tr["entry"] - tr["sl"]) if tr.get("sl") else 0
    if risk > 0:
        best = None
        k = 0
        while True:
            b = bars.get(tr["ts"] + M5 * k)
            if not b or (tr.get("exit_ts") and tr["ts"] + M5 * k > tr["exit_ts"]):
                break
            fav = (b[1] - tr["entry"]) if side > 0 else (tr["entry"] - b[2])
            best = fav if best is None else max(best, fav)
            k += 1
            if k > 600:
                break
        if best is not None:
            r = best / risk
            if r >= 2.0:
                read.append("ran to %.1fR, so the ratchet locked 2R" % r)
            else:
                # two decimals below the lock, so a 1.96R near-miss cannot round to
                # "2.0R" and then claim it never reached 2R
                read.append("peaked at %.2fR - short of the 2R lock" % r)

    d["read"] = " · ".join(read) if read else None
    d["warn"] = None
    return d


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
    for i in range(comp.get("nb", 2)):
        tag(t - M5 * (2 + i), "C%d" % (i + 1), CLUSTER, not below, i % 2)
    tag(t - M5, "R", REACT, not below, comp.get("nb", 2) % 2)

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
        col = CLUSTER if ts in [t - M5 * (2 + j) for j in range(comp.get("nb", 2))] \
            else (REACT if ts == t - M5 else (UP if c >= o else DOWN))
        a = 1.0 if col in (CLUSTER, REACT) else 0.40
        av.bar(i, vols[i], width=0.66, color=col, alpha=a, zorder=3)
    if comp.get("vmax"):
        av.axhline(comp["vmax"], color=MUTED, lw=0.8, ls=":", alpha=0.8)
        av.text(len(seq) + 0.2, comp["vmax"], " swing max", fontsize=7,
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
     "Big volume down + next bar UP = that volume was BUYING, so we buy. Mirror for "
     "sells. This is what picks the side."),
    (3, "The reaction must arrive on LOW volume — THE TRIGGER", "CONFIRMED",
     "The lower the volume on it, the stronger the signal. If a big volume comes, SKIP "
     "it, wait more.",
     "reaction volume ≤ 1.00 × the setup's volume. A veto, not a score."),
    (4, "The setup — counted, not fixed", "CORRECTED 2026-09-13",
     "we wait until the red reds keep appearing.. we wait until the reaction candle "
     "becomes bullish (blue).. it could be three or more reds",
     "The EA now WAITS for the turn instead of assuming 2 or 3 bars: it walks back while "
     "the bars keep closing the setup's way (2 to 10). A card showing \"setup 7 bars\" is "
     "a run a fixed length would have missed entirely."),
    (4.5, "Big, not incrementally increasing", "CORRECTED 2026-09-14",
     "big volumes show increased transactions, i don't think we need in specific "
     "'increasing' volumes, they can just be big (not incrementally increasing)",
     "Requiring a rising sequence was reading a description as a rule; it refused 136 "
     "setups in September alone. Now only bigness is required."),
    (5, "\"Big\" is judged against THE CURRENT SWING", "CORRECTED 2026-09-13",
     "i think the 24 hour was for 1D chart.. on 5 min chart we can just see the current "
     "swing",
     "The yardstick runs back to the pivot that began this leg — a swing high for a buy, "
     "a swing low for a sell — so a fast leg gets a short window and a grind a long one. "
     "It replaced a fixed 10-bar window (50 minutes), which let a bar qualify as the "
     "climax for being loudest of three-quarters of an hour."),
    (6, "The wick does NOT rescue a loud reaction", "REFUTED 2026-09-17, now OFF",
     "since the fourth bullish blue candle has still somewhat bigger volume .. if there "
     "were no lower wick we wouldn't buy immediately, we would wait .. and here we see a "
     "lower wick",
     "This was ON for four days and it was losing money. Diagram 4's loud reaction is "
     "acceptable because it also has the capped bar before it, not because of the wick "
     "alone — and diagrams 3 and 5 say plainly that a loud reaction is a WEAK setup. "
     "Measured: the LOUD+wick group ran 25% win rate and −$11.12 a trade. Switching it "
     "off improved every metric in both walk-forward halves."),
    (8, "Entry at the reaction candle's close", "CONFIRMED — his ruling",
     "it doesnot mean a stop order above its high.. it means same as line 16",
     "Zee settled the ambiguity on 2026-09-12: lines 16 and 33 describe the same trade. "
     "The EA was already correct."),
    (8.5, "Stop 2-3 pips below THE BLUE CANDLE", "CORRECTED 2026-09-12",
     "Stop loss 2-3 pips below the bullish blue candle.",
     "The EA had been measuring from the lowest low of the WHOLE setup, and since the "
     "setup bars are the down-move their lows sit far below — every stop came out too "
     "wide (the two live trades risked 526 and 876 points). Now 30 points (3 gold pips) "
     "below the reaction candle only. This changed the R multiple of every trade."),
    (8.6, "The risk cap", "ADDED — earns its place",
     "(not his rule — a safety rail)",
     "Setups whose stop exceeds 900 points are refused, so risk per trade stays uniform. "
     "Tested: raising it to 3000 adds 58 trades and destroys $1,476 of profit."),
    (9, "Trade with the higher-timeframe trend", "OFF on his instruction",
     "That setup comes on H1, and we take entry on M5... take the trade in trend "
     "direction. Do not catch the top.",
     "Built (InpTrendTF) and currently OFF at Zee's request. Worth recording what it "
     "cost when it was measured: with it ON the EA made the same money on HALF the "
     "trades and seven more points of win rate."),
    (10, "Never chase — trade the retracement", "BUILT 2026-09-16, OFF",
     "if we miss such a breakout on low volume, then we wait for a retracement to the same "
     "low .. that retracement low when it touches the low line of the missed setup is also "
     "a valid setup .. sometimes it can touch several times",
     "Built at last (InpRetrace). The price-only version is REFUTED on a clean 409-trade "
     "sample: −$9.46 a trade against the base setup's +$13.35. Requiring the retest to "
     "arrive QUIET flips the sign, but its best value is an isolated spike with worse "
     "results either side, so it ships OFF."),
    (12, "Falling volume on a fall is NOT automatically bullish", "STRUCTURAL",
     "Rising prices rising volume, falling prices falling volume is bullish — this is "
     "wrong. This is incomplete.",
     "Encoded by making the engine SETUP-FIRST: quiet volume only means anything "
     "straight after effort. The EA never scans for low volume on its own."),
    (0, "The BASE CASE — effort against result", "TESTED, NOT PROVEN",
     "if the candle is getting smaller it means that supply is getting hit more.. and "
     "price is getting capped",
     "Diagram 9 states it exactly — two candles of THE SAME SPREAD, and the one with more "
     "volume is where supply was hit. That is volume-per-range, and it is now built twice "
     "(InpCapVol, InpEffortMin). Both are OFF: the strict setting reaches 67% on 15 trades "
     "and decays to the 43% baseline as soon as the sample grows."),
    (13, "THE FAKE BREAK — his tier-3 case, now LIVE", "SHIPPED 2026-09-16",
     "case 3. 2 bar setup + fake break of this support + forms a wick + closing again "
     "inside support .. (strongest)",
     "The setup must SWEEP a recent extreme and the reaction must close back INSIDE it. "
     "Built early, tested OFF on the old broken build, and only re-examined after the "
     "geometry was fixed. It is the best filter on this project: win rate 25% → 33% and "
     "the worst losing streak 15 → 9, holding in BOTH walk-forward halves at EVERY sweep "
     "length. It costs 75% of the trades to get it."),
    (8.7, "THE EXIT IS A LOCK AT 2R — the target never pays", "CORRECTED 2026-09-17",
     "SL should not be tied to TP .. TP can be very high up until 1:7 / if 2R is reached "
     "we breakeven to 2R / if XR is reached we breakeven to XR",
     "Both of his instructions, and the second one overtook the first. EVERY trade now "
     "closes at the STOP and not one reaches the target — the average stop-exit is "
     "+$136.68, because the stop has been RATCHETED above entry. So the 1:5 target that "
     "was shipped on 15 Sep is decorative; it is set to 10R purely so the ratchet cannot "
     "collide with it. And the ratchet is ONE LOCK, not a trail: stepping it at 8R and at "
     "20R gives identical results, which proves no second rung is ever reached. Lock 2R, "
     "hands off."),
    (9.5, "THE CAMEL HUMPS — his own trend reading", "SHIPPED 2026-09-16",
     "we identify trend by drawing camel humps .. we call it an uptrend if we're breaking "
     "above previous highs. and forming new higher lows",
     "Ported from LAWS.md and the UHV compass. Higher highs AND higher lows for up, the "
     "mirror for down, anything mixed is a range and gates nothing. It beat the 20-bar "
     "slope at EVERY timeframe — M30 went 3.29 to 9.16 — and on M30 it improved win rate, "
     "drawdown, streak and risk-adjusted return in BOTH halves. March, which was 0-for-7 "
     "without it, turned positive."),
    (9, "Trade with the higher-timeframe trend", "OFF on his instruction",
     "That setup comes on H1, and we take entry on M5... take the trade in trend "
     "direction. Do not catch the top.",
     "Built (InpTrendTF) and currently OFF at Zee's request. Worth recording what it "
     "cost when it was measured: with it ON the EA made the same money on HALF the "
     "trades and seven more points of win rate."),
    (10, "Never chase — trade the retracement", "BUILT 2026-09-16, OFF",
     "if we miss such a breakout on low volume, then we wait for a retracement to the same "
     "low .. that retracement low when it touches the low line of the missed setup is also "
     "a valid setup .. sometimes it can touch several times",
     "Built at last (InpRetrace). The price-only version is REFUTED on a clean 409-trade "
     "sample: −$9.46 a trade against the base setup's +$13.35. Requiring the retest to "
     "arrive QUIET flips the sign, but its best value is an isolated spike with worse "
     "results either side, so it ships OFF."),
    (12, "Falling volume on a fall is NOT automatically bullish", "STRUCTURAL",
     "Rising prices rising volume, falling prices falling volume is bullish — this is "
     "wrong. This is incomplete.",
     "Encoded by making the engine SETUP-FIRST: quiet volume only means anything "
     "straight after effort. The EA never scans for low volume on its own."),
    (0, "The BASE CASE — effort against result", "TESTED, NOT PROVEN",
     "if the candle is getting smaller it means that supply is getting hit more.. and "
     "price is getting capped",
     "Diagram 9 states it exactly — two candles of THE SAME SPREAD, and the one with more "
     "volume is where supply was hit. That is volume-per-range, and it is now built twice "
     "(InpCapVol, InpEffortMin). Both are OFF: the strict setting reaches 67% on 15 trades "
     "and decays to the 43% baseline as soon as the sample grows."),
    (13, "THE FAKE BREAK — his tier-3 case, now LIVE", "SHIPPED 2026-09-16",
     "case 3. 2 bar setup + fake break of this support + forms a wick + closing again "
     "inside support .. (strongest)",
     "The setup must SWEEP a recent extreme and the reaction must close back INSIDE it. "
     "Built early, tested OFF on the old broken build, and only re-examined after the "
     "geometry was fixed. It is the best filter on this project: win rate 25% → 33% and "
     "the worst losing streak 15 → 9, holding in BOTH walk-forward halves at EVERY sweep "
     "length. It costs 75% of the trades to get it."),
    (8.7, "THE TARGET IS 1:5, AND IT IS NOT TIED TO THE STOP", "SHIPPED 2026-09-15",
     "SL should not be tied to TP. SL can be below the first reaction candle's low .. and "
     "TP can be very high up until 1:7",
     "Zee was right and my 2.0R was a LOCAL peak — the curve dips at 2.5R and climbs to a "
     "second, higher one. 5.0R earns +48% more than 2.0R for IDENTICAL drawdown, and the "
     "two walk-forward halves land within 1% of each other. The stop never moved: it is "
     "still 120 points under the reaction candle."),
]

VERDICT_CLASS = {
    "CONFIRMED": "ok", "SHIPPED 2026-09-16": "ok", "SHIPPED 2026-09-15": "ok",
    "BUILT 2026-09-16, OFF": "warn", "TESTED, NOT PROVEN": "warn", "CONFIRMED — now ON": "ok",
    "CONFIRMED — his ruling": "ok",
    "CORRECTED 2026-09-12": "ok", "CORRECTED 2026-09-13": "ok",
    "CORRECTED 2026-09-14": "ok", "ADDED — earns its place": "ok",
    "OFF on his instruction": "warn",
    "NOT IMPLEMENTED / REJECTED": "muted", "CONFIRMED at 2": "ok", "CONFIRMED at 2.5R + BE": "ok",
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
.read{background:#eef5ff;border:1px solid #cfe0f7;color:#1c4a80;border-radius:8px;
      padding:8px 11px;margin-top:9px;font-size:12.5px;line-height:1.5}
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
                     "target %.2f (2.0R)" % (risk, risk * 0.10, tr["sl"], tr["tp"])))
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
    warn = ('<div class="read"><b>The read:</b> %s</div>' % esc(comp["read"])
            ) if comp.get("read") else ""

    return (
        '<div class="card" id="%s">'
        '<h3>%s &nbsp;%s%s</h3>'
        '<img src="data:image/png;base64,%s" alt="setup">'
        '<div class="legend">'
        '<span><span class="dot" style="background:%s"></span><b>C1 C2</b> the 2 bar setup</span>'
        '<span><span class="dot" style="background:%s"></span><b>R</b> reaction</span>'
        '<span><span class="dot" style="background:%s"></span>up bar</span>'
        '<span><span class="dot" style="background:%s"></span>down bar</span>'
        '<span>dotted line = loudest bar of the swing</span></div>'
        '<table class="k">%s</table>%s</div>'
        % (esc(tr["tag"]),
           esc(time.strftime("%a %d %b %Y  %H:%M", time.gmtime(tr["ts"]))) + " broker",
           badge, res, png, CLUSTER, REACT, UP, DOWN,
           "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(a), b) for a, b in rows),
           warn))


def build(out_path: Path, limit=0):
    t0 = time.time()
    bars = load_bars(BARS_DIR / "vsisa_bars_axi.csv")
    print("[vsisa-page] %d broker M5 bars" % len(bars), flush=True)
    sep = bars_from_ticks()
    print("[vsisa-page] %d September M5 bars from our ticks" % len(sep), flush=True)
    merged = dict(bars)
    for k, v in sep.items():
        merged.setdefault(k, v)

    # LIVE CARDS OFF (Zee, 2026-09-17): "remove the LIVE trades .. and keep only the ones
    # from the current EA version (tested ones)". He is right that they were misleading —
    # the only two live fills on record were taken by v1.00/v1.01 at 2.0R and 2.5R, before
    # the stop correction, the fake break, the ratchet and the camel filter existed. Drawn
    # beside v1.20 cards they read as examples of the current strategy, and they are not.
    #
    # Flip this back to True once v1.20 has real fills of its own; the reader is worth
    # nothing if the page cannot show what the EA actually did.
    INCLUDE_LIVE = False
    trades = tester_trades(REPORT) + (live_trades() if INCLUDE_LIVE else [])
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
        "<tr><td>Stop</td><td>120 points beyond the reaction candle "
        "(60-point floor).</td></tr>"
        "<tr><td>Target</td><td>2.0 × risk, with no breakeven move - it was cutting winners.</td></tr>"
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
