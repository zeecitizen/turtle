"""law_trade_diagram.py — THE LIVE TRADE, drawn in the same grammar as the sanity diagram.

Zee 2026-08-24: "there's a trade active right now zlaw_buy.. can you tell its
retracement start, the uhv etc?" and then: "in the camel cockpit gui can you add a
button Visualize Live trade so i can see the live trade's drawing (ditto similar to
the line diagram)".

BasedOnLaws stamps its three anchors the instant it fires ([LAWX] in the terminal log).
This reads the newest stamp, pulls the same OANDA candles the EA judged, and draws:

    the retracement start · THE UHV (bold, its high extended as the trigger line)
    · the BREAKOUT candle · entry / stop / target · the volume story underneath,
    with the numbers the laws actually turn on printed on the candles.

    render()           -> (png_path, caption)   newest trade
    render(index=-2)   -> the one before it
"""
from __future__ import annotations
import csv
import datetime as dt
import re
from pathlib import Path

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOGDIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/"
              r"DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Logs")
HIST = Path(__file__).parent / "strategy_lab" / "oanda_m1_history.csv"
OUT_DEFAULT = Path(__file__).parent / "setup_labels" / "law_trade.png"
BROKER_OFF = dt.timedelta(hours=3)      # broker clock = UTC+3
PKT_OFF = dt.timedelta(hours=2)         # PKT = broker + 2

GREEN, RED, INK, DIM = "#2f9e44", "#e03131", "#222222", "#8a949e"
BLUE, ORANGE = "#1d6fbf", "#f08c00"

LAWX = re.compile(
    r"\[LAWX\] (BUY|SELL)\s*\| origin green (\d\d:\d\d).*?\| UHV (\d\d:\d\d) "
    r"\(vol (\d+), high ([\d.]+)\).*?\| breakout (\d\d:\d\d) "
    r"\(close ([\d.]+), vol (\d+)(?:, HELD (\d+)%[^)]*)?\).*?"
    r"entry ([\d.]+) stop ([\d.]+) target ([\d.]+)")


def _trades():
    out = []
    for f in sorted(LOGDIR.glob("*.log"), key=lambda x: x.stat().st_mtime)[-4:]:
        day = f.stem
        if len(day) != 8 or not day.isdigit():
            continue
        date = f"{day[:4]}.{day[4:6]}.{day[6:]}"
        raw = f.read_bytes()
        txt = (raw.decode("utf-16-le", "ignore") if raw[:2] == b"\xff\xfe"
               else raw.decode("utf-8", "ignore"))
        for ln in txt.splitlines():
            m = LAWX.search(ln)
            if m:
                (side, org, uhv, uvol, uhigh, brk, bclose, bvol, held,
                 entry, stop, target) = m.groups()
                out.append(dict(date=date, side=side.lower(),
                                origin=f"{date} {org}", uhv=f"{date} {uhv}",
                                breakout=f"{date} {brk}",
                                uhv_vol=int(uvol), uhv_high=float(uhigh),
                                brk_vol=int(bvol),
                                held=int(held) if held else None,
                                entry=float(entry), stop=float(stop),
                                target=float(target)))
    return out


def _bars():
    rows = {}
    for src in (HIST, COMMON / "oanda_m1.csv"):
        if not src.exists():
            continue
        for r in csv.DictReader(src.open(encoding="utf-8", errors="replace")):
            u = r.get("time_unix")
            if not u:
                continue
            srv = dt.datetime.fromtimestamp(int(u), dt.UTC).replace(tzinfo=None) + BROKER_OFF
            rows.setdefault(srv.strftime("%Y.%m.%d %H:%M"),
                            (float(r["open"]), float(r["high"]), float(r["low"]),
                             float(r["close"]), int(float(r["volume"]))))
    return rows


def render(out=None, index=-1, pad_before=14, pad_after=10, near=None):
    """near="YYYY.MM.DD HH:MM" (broker time, e.g. a fill's close) picks the trade whose
    breakout is the latest one at or before it — so the cockpit's Trades list can hand
    a row straight to this drawing (Zee 2026-08-25)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    out = Path(out) if out else OUT_DEFAULT
    tr = _trades()
    if not tr:
        return None, "the EA has not fired yet — no [LAWX] stamp in the logs"
    if near:
        earlier = [x for x in tr if x["breakout"] <= near]
        if not earlier:
            return None, f"no [LAWX] stamp at or before {near}"
        t = earlier[-1]
    else:
        t = tr[index]
    bars = _bars()
    keys = sorted(bars)
    if t["breakout"] not in bars or t["origin"] not in bars:
        return None, "its candles are not in the OANDA window any more"
    i_o, i_b = keys.index(t["origin"]), keys.index(t["breakout"])
    lo_i = max(0, i_o - pad_before)
    hi_i = min(len(keys) - 1, i_b + pad_after)
    win = keys[lo_i:hi_i + 1]
    buy = t["side"] == "buy"

    def pkt(k):
        return (dt.datetime.strptime(k, "%Y.%m.%d %H:%M") + PKT_OFF).strftime("%H:%M")

    fig, (ax, av) = plt.subplots(
        2, 1, figsize=(15, 9), sharex=True,
        gridspec_kw=dict(height_ratios=[3, 1], hspace=0.06))
    fig.patch.set_facecolor("white")
    for a in (ax, av):
        a.set_facecolor("white")
        for sp in a.spines.values():
            sp.set_color("#dddddd")
        a.tick_params(colors=DIM, labelsize=9)

    vmax = max(bars[k][4] for k in win) or 1
    for x, k in enumerate(win):
        o, h, l, c, v = bars[k]
        up = c >= o
        col = GREEN if up else RED
        role = ("origin" if k == t["origin"] else
                "uhv" if k == t["uhv"] else
                "breakout" if k == t["breakout"] else None)
        ax.plot([x, x], [l, h], color=col, lw=1.1, zorder=2)
        ax.add_patch(Rectangle((x - 0.34, min(o, c)), 0.68, max(abs(c - o), 0.01),
                               facecolor=col, edgecolor=col, zorder=3))
        av.add_patch(Rectangle((x - 0.34, 0), 0.68, v,
                               facecolor=col, alpha=.40, edgecolor="none", zorder=2))
        if role:
            hue = {"origin": BLUE, "uhv": RED, "breakout": GREEN}[role]
            for a in (ax, av):
                a.axvline(x, color=hue, lw=1.1, alpha=.45,
                          ls="-" if role == "uhv" else "--", zorder=1)
            ax.add_patch(Rectangle((x - 0.5, l), 1.0, h - l, fill=False,
                                   edgecolor=hue, lw=2.0, zorder=4))
            av.add_patch(Rectangle((x - 0.5, 0), 1.0, v, fill=False,
                                   edgecolor=hue, lw=2.0, zorder=3))
            label = {"origin": "RETRACEMENT\nSTARTS AFTER",
                     "uhv": "THE UHV", "breakout": "BREAKOUT"}[role]
            ax.annotate(f"{label}\n{pkt(k)}", (x, h), xytext=(0, 12),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color=hue)
            av.annotate(f"vol {v}", (x, v), xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=9, fontweight="bold", color=hue)
            if role == "breakout":
                rng, body = h - l, abs(c - o)
                ratio = body / rng if rng else 0
                ax.annotate(f"body {ratio:.2f} of range"
                            + (f"\nheld {t['held']}%" if t["held"] is not None else ""),
                            (x, l), xytext=(0, -26), textcoords="offset points",
                            ha="center", fontsize=9, color=INK)

    # the level the breakout had to close its body through
    ib = win.index(t["uhv"]) if t["uhv"] in win else 0
    ax.plot([ib, len(win) - 1], [t["uhv_high"]] * 2, color=ORANGE, lw=1.8, ls="--", zorder=5)
    ax.annotate(f"  the level {t['uhv_high']:.2f}  (UHV {'high' if buy else 'low'})",
                (len(win) - 1, t["uhv_high"]), fontsize=10, color=ORANGE,
                fontweight="bold", va="bottom", ha="right")
    # the trade's own geometry
    for price, lab, col, ls in ((t["entry"], "entry", INK, "-"),
                                (t["stop"], "stop", RED, ":"),
                                (t["target"], "target", GREEN, ":")):
        ax.axhline(price, color=col, lw=1.3, ls=ls, alpha=.85, zorder=5)
        ax.annotate(f"{lab} {price:.2f}", (0, price), xytext=(4, 3),
                    textcoords="offset points", fontsize=9.5, color=col,
                    fontweight="bold")

    risk = abs(t["entry"] - t["stop"])
    rr = abs(t["target"] - t["entry"]) / risk if risk else 0
    quiet = "quieter ✓" if t["brk_vol"] < t["uhv_vol"] else "LOUDER ✗"
    ax.set_title(
        f"{t['side'].upper()}  ·  {t['date']}  ·  breakout {pkt(t['breakout'])} PKT   "
        f"|  UHV vol {t['uhv_vol']} → breakout vol {t['brk_vol']} ({quiet})   "
        f"|  risk {risk:.2f} pts, target {rr:.1f}R",
        fontsize=12, fontweight="bold", color=INK, pad=14)
    av.set_ylabel("OANDA volume", color=DIM, fontsize=9)
    av.set_ylim(0, vmax * 1.25)
    ax.set_xlim(-1, len(win))
    step = max(1, len(win) // 12)
    av.set_xticks(range(0, len(win), step))
    av.set_xticklabels([pkt(win[i]) for i in range(0, len(win), step)], fontsize=9)
    av.set_xlabel("PKT", color=DIM, fontsize=9)
    ax.grid(axis="y", color="#eeeeee", lw=.8, zorder=0)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    caption = (f"{t['side'].upper()} {pkt(t['breakout'])} PKT · UHV {pkt(t['uhv'])} "
               f"vol {t['uhv_vol']} · breakout vol {t['brk_vol']}")
    return out, caption


if __name__ == "__main__":
    p, msg = render()
    print(msg if not p else f"{msg}\n  -> {p}")
