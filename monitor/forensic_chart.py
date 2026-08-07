"""forensic_chart.py — draw ONE trade with its UHV, trigger lines, BO candle,
entry and exit clearly marked (Zee 2026-08-07: "a photograph of the clearly marked
UHV / BO candle that led to the trade").

Usage:
  py monitor/forensic_chart.py --from 00:30 --to 01:12 --uhv 00:41 --bo 00:59 \
     --lamp 4230.40 --entry 4229.90 --exit 4232.95 --side SELL --out forensic_0359.png
All times UTC (the chart axis is drawn in Karachi = UTC+5, matching Zee's TV).
"""
from __future__ import annotations
import argparse, csv, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # detached GUI process: sys.stdout is None
    pass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf

HIST = Path(__file__).parent / "strategy_lab" / "oanda_m1_history.csv"
LIVE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")


def load(day="08-07"):
    seen = {}
    for src in (HIST, LIVE):
        try:
            for r in csv.DictReader(open(src, encoding="utf-8")):
                seen[r["time_unix"]] = r
        except FileNotFoundError:
            pass
    rows = []
    for k in sorted(seen, key=int):
        r = seen[k]
        t = datetime.fromtimestamp(int(k), tz=timezone.utc).replace(tzinfo=None)
        rows.append((t, float(r["open"]), float(r["high"]), float(r["low"]),
                     float(r["close"]), float(r["volume"])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    for a in ("from", "to", "uhv", "bo"):
        ap.add_argument(f"--{a}", required=True)
    ap.add_argument("--lamp", type=float, required=True)
    ap.add_argument("--entry", type=float, default=None)
    ap.add_argument("--exit", dest="exitp", type=float, default=None)
    ap.add_argument("--side", default="SELL")
    ap.add_argument("--day", default="08-07")
    ap.add_argument("--out", default="forensic.png")
    A = ap.parse_args()

    rows = [r for r in load() if f"{A.day} {getattr(A, 'from')}" <= r[0].strftime("%m-%d %H:%M")
            <= f"{A.day} {A.to}"]
    if not rows:
        print("no bars in that window"); return
    idx = pd.DatetimeIndex([r[0] + timedelta(hours=5) for r in rows])     # Karachi axis
    df = pd.DataFrame({"Open": [r[1] for r in rows], "High": [r[2] for r in rows],
                       "Low": [r[3] for r in rows], "Close": [r[4] for r in rows],
                       "Volume": [r[5] for r in rows]}, index=idx)

    uhv_i = next((i for i, r in enumerate(rows) if r[0].strftime("%H:%M") == A.uhv), None)
    bo_i = next((i for i, r in enumerate(rows) if r[0].strftime("%H:%M") == A.bo), None)
    uhv = rows[uhv_i]

    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    hl = dict(hlines=[uhv[2], uhv[3]], colors=["k", "k"], linestyle="--", linewidths=[2.0, 2.0])
    fig, axes = mpf.plot(df, type="candle", style=style, volume=True, figsize=(17, 9.5),
                         hlines=hl, returnfig=True,
                         title=f"FORENSIC — the {A.side} that entered at "
                               f"{(rows[bo_i][0] + timedelta(hours=5)):%H:%M} PKT")
    ax = axes[0]
    # mark the UHV and the BO candle
    ax.annotate("UHV\n(trigger lines = its high & low)", xy=(uhv_i, uhv[2]),
                xytext=(uhv_i - 6, uhv[2] + 3.2), fontsize=13, fontweight="bold",
                color="#7048e8", ha="center",
                arrowprops=dict(arrowstyle="->", lw=2.2, color="#7048e8"))
    ax.axvspan(uhv_i - 0.45, uhv_i + 0.45, color="#7048e8", alpha=0.16)
    if bo_i is not None:
        ax.annotate("BO candle\n(door fired here)", xy=(bo_i, rows[bo_i][3]),
                    xytext=(bo_i - 3, rows[bo_i][3] - 3.4), fontsize=13, fontweight="bold",
                    color="#e03131", ha="center",
                    arrowprops=dict(arrowstyle="->", lw=2.2, color="#e03131"))
        ax.axvspan(bo_i - 0.45, bo_i + 0.45, color="#e03131", alpha=0.16)
    if A.entry:
        ax.axhline(A.entry, color="#1c7ed6", lw=1.6, ls="-")
        ax.text(len(rows) - 1, A.entry, f"  entry {A.entry:.2f}", color="#1c7ed6",
                fontsize=12, fontweight="bold", va="center")
    if A.exitp:
        ax.axhline(A.exitp, color="#f08c00", lw=1.6, ls="-")
        ax.text(len(rows) - 1, A.exitp, f"  exit {A.exitp:.2f}", color="#f08c00",
                fontsize=12, fontweight="bold", va="center")
    ax.text(0.5, 4235.0, "", fontsize=1)
    ax.text(uhv_i, uhv[3] - 0.6, f"lamp {uhv[3]:.2f}", color="k", fontsize=11,
            fontweight="bold", ha="center")
    ax.text(uhv_i, uhv[2] + 0.4, f"upper line {uhv[2]:.2f}", color="k", fontsize=11,
            fontweight="bold", ha="center")
    out = Path(__file__).parent / "setup_labels" / A.out
    fig.savefig(str(out), dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"forensic chart -> {out}")


# ── AUTO-RESOLVER: given a fill, find its lamp / UHV / BO candle and draw it ──
# (Zee 2026-08-07: "make this forensic a button against every trade listed on the
#  GUI, so i can visually inspect every trade's uhv/breakout/trigger lines")
import glob, os, re

MT5D = r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8"
BROKER_TO_LOCAL_H = 2


def _read_log(p):
    try:
        return Path(p).read_text(encoding="utf-16", errors="ignore").splitlines()
    except Exception:
        return Path(p).read_text(errors="ignore").splitlines()


def resolve_trade(broker_ts, side):
    """Return dict(entry_utc, lamp, uhv_utc, entry_px, exit_px) for one fill."""
    close_local = datetime.strptime(broker_ts, "%Y.%m.%d %H:%M:%S") + timedelta(hours=BROKER_TO_LOCAL_H)
    best = None
    for lf in sorted(glob.glob(MT5D + "/MQL5/Logs/*.log"), key=os.path.getmtime)[-4:]:
        # BUGFIX 2026-08-07 (Zee spotted a chart with no UHV): the log line's date
        # must come from the LOG FILENAME (20260807.log), not from the fill's date —
        # otherwise a fire from a previous day matched by time-of-day alone and
        # handed back a lamp 150 points away from the market.
        stem = os.path.basename(lf)[:8]
        if not stem.isdigit():
            continue
        day = datetime.strptime(stem, "%Y%m%d").date()
        for l in _read_log(lf):
            if "CaseExec" not in l or side not in l:
                continue
            if "GHOST-DOOR" not in l and "signal #" not in l:
                continue
            m = re.search(r"(\d\d:\d\d:\d\d)", l)
            if not m:
                continue
            lt = datetime.combine(day, datetime.strptime(m.group(1), "%H:%M:%S").time())
            # 45min -> 3h (2026-08-07): trades held through the grace period and the
            # 25-minute campaign window closed well after their fire, so the old
            # window said "no EA fire line found" on perfectly good trades.
            if timedelta(0) <= (close_local - lt) <= timedelta(hours=3):
                if best is None or lt > best[0]:
                    best = (lt, l)
    if best is None:
        return None
    lamp = None
    lm = re.search(r"lamp (\d+\.\d+)", best[1])
    if lm:
        lamp = float(lm.group(1))
    else:
        # the chosen line is a signal-path fire (no lamp printed). If a DOOR fire for
        # the same setup sits within 2 minutes, borrow its lamp — that is the same
        # setup seen by the other path. (2026-08-07: this was the real reason two
        # trades reported "no EA fire line found".)
        for lf in sorted(glob.glob(MT5D + "/MQL5/Logs/*.log"), key=os.path.getmtime)[-4:]:
            stem = os.path.basename(lf)[:8]
            if not stem.isdigit():
                continue
            day2 = datetime.strptime(stem, "%Y%m%d").date()
            for l in _read_log(lf):
                if "GHOST-DOOR" not in l or side not in l:
                    continue
                m2 = re.search(r"(\d\d:\d\d:\d\d)", l)
                lm2 = re.search(r"lamp (\d+\.\d+)", l)
                if not m2 or not lm2:
                    continue
                lt2 = datetime.combine(day2, datetime.strptime(m2.group(1), "%H:%M:%S").time())
                if abs((lt2 - best[0]).total_seconds()) <= 120:
                    lamp = float(lm2.group(1))
                    best = (lt2, l)
                    break
            if lamp is not None:
                break
    entry_utc = best[0] - timedelta(hours=5)          # local (Karachi) -> UTC
    rows = load()
    # the UHV: the most recent candle before entry whose low (SELL) / high (BUY)
    # equals the lamp — that is the candle whose trigger line the door crossed.
    uhv_utc = None
    if lamp is not None:
        cands = [r for r in rows if r[0] <= entry_utc]
        for r in reversed(cands[-90:]):
            edge = r[3] if side == "SELL" else r[2]
            if abs(edge - lamp) < 0.06:
                uhv_utc = r[0]
                break
    if lamp is None:
        # a pure signal-path fire: its printed parachute sits InpHardSLPts (3.0) beyond
        # the entry, so the entry candle's close is recoverable from the bars instead.
        pm = re.search(r"parachute=(\d+\.\d+)", best[1])
        if pm:
            para = float(pm.group(1))
            for x in load():
                if abs((x[0] - entry_utc).total_seconds()) <= 90:
                    if abs(abs(x[4] - para) - 3.0) < 0.35:
                        lamp = x[4]
                        break
    if uhv_utc is None:
        # signal-path fire (no lamp in the line): ask the detector which UHV that
        # breakout candle belonged to.
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
            import oanda_live_matcher as _M, build_entry_review_m5 as _B
            for k2, v2 in _M.CFG.items():
                setattr(_B, k2, v2)
            # the ARCHIVE, not the rolling live window — older trades live there
            bb = [_B.Bar(x[0], x[1], x[2], x[3], x[4], int(x[5])) for x in load()]
            for st in _B.detect_full(bb):
                if st["side"] == side and abs((st["open_t"] - entry_utc).total_seconds()) <= 120:
                    uhv_utc = st["uhv_t"]
                    if lamp is None:
                        lamp = (bb[st["u"]].h if side == "BUY" else bb[st["u"]].l)
                    break
        except Exception:
            pass
    return dict(entry_utc=entry_utc, lamp=lamp, uhv_utc=uhv_utc, fire=best[1].strip())


def draw_trade(broker_ts, side, exit_px, out=None):
    """Render the forensic chart for one fill; returns the PNG path (or None)."""
    r = resolve_trade(broker_ts, side)
    if not r:
        # no fire line at all: still draw the price window around the close so the
        # trade can be inspected (Zee 2026-08-07 — a dead end is worse than a chart)
        rows0 = load()
        ct = datetime.strptime(broker_ts, "%Y.%m.%d %H:%M:%S") - timedelta(hours=3)
        win0 = [x for x in rows0 if abs((x[0] - ct).total_seconds()) <= 1500]
        if len(win0) < 8:
            return None
        idx0 = pd.DatetimeIndex([x[0] + timedelta(hours=5) for x in win0])
        df0 = pd.DataFrame({"Open": [x[1] for x in win0], "High": [x[2] for x in win0],
                            "Low": [x[3] for x in win0], "Close": [x[4] for x in win0],
                            "Volume": [x[5] for x in win0]}, index=idx0)
        st0 = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
        fig0, ax0 = mpf.plot(df0, type="candle", style=st0, volume=True, figsize=(16, 9),
                             returnfig=True,
                             title=f"{side} closed {broker_ts[11:]} broker — no EA fire "
                                   f"line in the logs, so no UHV/trigger lines to draw")
        if exit_px:
            ax0[0].axhline(exit_px, color="#f08c00", lw=1.6)
        out2 = Path(__file__).parent / "setup_labels" / f"forensic_{broker_ts[11:].replace(':','')}.png"
        fig0.savefig(str(out2), dpi=100, bbox_inches="tight"); plt.close(fig0)
        return out2
    if r["lamp"] is None:
        r["lamp"] = exit_px          # last resort: anchor the chart on the exit
    rows = load()
    e_utc = r["entry_utc"]
    u_utc = r["uhv_utc"] or (e_utc - timedelta(minutes=10))
    lo = min(u_utc, e_utc) - timedelta(minutes=8)
    hi = e_utc + timedelta(minutes=10)
    win = [x for x in rows if lo <= x[0] <= hi]
    if len(win) < 8:
        return None
    idx = pd.DatetimeIndex([x[0] + timedelta(hours=5) for x in win])
    df = pd.DataFrame({"Open": [x[1] for x in win], "High": [x[2] for x in win],
                       "Low": [x[3] for x in win], "Close": [x[4] for x in win],
                       "Volume": [x[5] for x in win]}, index=idx)
    ui = next((i for i, x in enumerate(win) if x[0] == u_utc), None)
    bi = next((i for i, x in enumerate(win)
               if x[0] <= e_utc < x[0] + timedelta(minutes=1)), None)
    uhv = win[ui] if ui is not None else None
    if uhv is None:
        # The UHV bar may be missing from the drawn window (a bridge gap, or a tape
        # that had not caught up when the GUI drew it). Zee 2026-08-07: "it doesn't
        # mark the UHV / trigger lines — maybe it drew off screen?" Find the bar
        # anywhere in the tape and STILL draw its two trigger lines, so a chart is
        # never silently missing the thing it exists to show.
        uhv = next((x for x in rows if x[0] == u_utc), None)
        if uhv is None:
            near = sorted(rows, key=lambda x: abs((x[0] - u_utc).total_seconds()))
            uhv = near[0] if near and abs((near[0][0] - u_utc).total_seconds()) <= 300 else None
    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    hl = dict(hlines=[uhv[2], uhv[3]] if uhv else [r["lamp"]],
              colors=["k"] * (2 if uhv else 1), linestyle="--", linewidths=[2.0, 2.0])
    off = " (UHV outside the drawn window - lines shown)" if (ui is None and uhv) else ""
    ttl = (f"FORENSIC — {side} entered "
           f"{(e_utc + timedelta(hours=5)):%H:%M} PKT · closed {broker_ts[11:]} broker{off}")
    fig, axes = mpf.plot(df, type="candle", style=style, volume=True, figsize=(16, 9),
                         hlines=hl, returnfig=True, title=ttl)
    ax = axes[0]
    if ui is not None:
        # Zee 2026-08-07: the UHV band was too faint and its label clipped off the
        # top — now a solid band + full-height dashed line + an always-drawn label.
        ax.axvspan(ui - 0.5, ui + 0.5, color="#7048e8", alpha=0.30, zorder=0)
        ax.axvline(ui, color="#7048e8", lw=1.6, ls="--", alpha=0.9, zorder=1)
        # offset-POINT labels never stretch the y-axis (Zee 2026-08-07: the candles
        # were squeezed into a corner because data-coordinate text expanded the scale)
        ax.annotate("UHV", xy=(ui, uhv[3]), textcoords="offset points", xytext=(0, -26),
                    fontsize=14, fontweight="bold", color="white", ha="center",
                    annotation_clip=False, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#7048e8", ec="none"),
                    arrowprops=dict(arrowstyle="->", lw=2.4, color="#7048e8"))
    if bi is not None:
        ax.axvspan(bi - 0.5, bi + 0.5, color="#e03131", alpha=0.30, zorder=0)
        ax.axvline(bi, color="#e03131", lw=1.6, ls="--", alpha=0.9, zorder=1)
        ax.annotate("BO", xy=(bi, win[bi][2]), textcoords="offset points", xytext=(0, 26),
                    fontsize=14, fontweight="bold", color="white", ha="center",
                    annotation_clip=False, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#e03131", ec="none"),
                    arrowprops=dict(arrowstyle="->", lw=2.4, color="#e03131"))
    if exit_px:
        ax.axhline(exit_px, color="#f08c00", lw=1.6)
        ax.text(len(win) - 1, exit_px, f"  exit {exit_px:.2f}", color="#f08c00",
                fontsize=11, fontweight="bold", va="center")
    ax.axhline(r["lamp"], color="#1c7ed6", lw=1.2, ls=":")
    # TIGHT Y-RANGE: candles fill the pane instead of clumping (Zee's catch)
    lo = min(x[3] for x in win); hi = max(x[2] for x in win)
    if exit_px: lo, hi = min(lo, exit_px), max(hi, exit_px)
    pad = max((hi - lo) * 0.16, 0.35)   # room for the UHV/BO labels
    ax.set_ylim(lo - pad, hi + pad)
    out = out or (Path(__file__).parent / "setup_labels" /
                  f"forensic_{broker_ts[11:].replace(':', '')}.png")
    fig.savefig(str(out), dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out


WATCH_F = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_watch.json")


def draw_forming(out=None):
    """THE SETUP ON THE WAY (Zee 2026-08-07): draw the UHV currently under
    consideration and its trigger lines BEFORE any breakout — so the forming setup
    can be inspected while it is still forming. Source: case_watch.json, which the
    matcher keeps current every cycle."""
    import json as _json
    try:
        w = _json.loads(WATCH_F.read_text(encoding="ascii"))
    except Exception:
        return None, "no setup is forming right now (no UHV boxed)"
    side = w["side"]; lamp = float(w["level"]); sweep = float(w["sweep"])
    hi_line, lo_line = (max(lamp, sweep), min(lamp, sweep))
    rows = load()
    if not rows:
        return None, "no bars"
    # the UHV is the candle whose HIGH and LOW are the two trigger lines
    ui_t = None
    for x in reversed(rows[-180:]):
        if abs(x[2] - hi_line) < 0.06 and abs(x[3] - lo_line) < 0.06:
            ui_t = x[0]; break
    win = [x for x in rows if (ui_t is None or x[0] >= ui_t - timedelta(minutes=10))][-70:]
    if len(win) < 8:
        return None, "not enough bars"
    idx = pd.DatetimeIndex([x[0] + timedelta(hours=5) for x in win])
    df = pd.DataFrame({"Open": [x[1] for x in win], "High": [x[2] for x in win],
                       "Low": [x[3] for x in win], "Close": [x[4] for x in win],
                       "Volume": [x[5] for x in win]}, index=idx)
    ui = next((i for i, x in enumerate(win) if x[0] == ui_t), None)
    laws = sum(int(bool(w.get(k))) for k in ("swept", "law3", "law4", "law5"))
    hearts = ("  +L6" if w.get("law6") else "") + ("  +SC3" if w.get("s3") else "")
    need = "CLOSE above" if side == "BUY" else "CLOSE below"
    ttl = (f"FORMING - {side} setup on the way   |   diamonds: {laws}{hearts}"
           f"   ·   waiting for a {need} {lamp:.2f} (momentum body, volume < UHV)")
    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    hl = dict(hlines=[hi_line, lo_line], colors=["k", "k"], linestyle="--", linewidths=[2.0, 2.0])
    fig, axes = mpf.plot(df, type="candle", style=style, volume=True, figsize=(16, 9),
                         hlines=hl, returnfig=True, title=ttl)
    ax = axes[0]
    if ui is not None:
        ax.axvspan(ui - 0.5, ui + 0.5, color="#7048e8", alpha=0.30, zorder=0)
        ax.axvline(ui, color="#7048e8", lw=1.6, ls="--", alpha=0.9, zorder=1)
        ax.annotate("UHV", xy=(ui, win[ui][3]), textcoords="offset points", xytext=(0, -26),
                    fontsize=14, fontweight="bold", color="white", ha="center",
                    annotation_clip=False, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#7048e8", ec="none"),
                    arrowprops=dict(arrowstyle="->", lw=2.4, color="#7048e8"))
    ax.axhline(lamp, color="#1c7ed6", lw=1.8)
    ax.text(len(win) - 1, lamp, f"  trigger {lamp:.2f}", color="#1c7ed6",
            fontsize=12, fontweight="bold", va="center")
    px = win[-1][4]
    ax.axhline(px, color="#f08c00", lw=1.2, ls=":")
    ax.text(len(win) - 1, px, f"  now {px:.2f}", color="#f08c00",
            fontsize=11, fontweight="bold", va="center")
    lo = min(x[3] for x in win); hi = max(x[2] for x in win)
    pad = max((hi - lo) * 0.14, 0.35)
    ax.set_ylim(min(lo, lamp) - pad, max(hi, lamp) + pad)
    out = out or (Path(__file__).parent / "setup_labels" / "forming_now.png")
    fig.savefig(str(out), dpi=100, bbox_inches="tight")
    plt.close(fig)
    swept_txt = "sweep DONE ✓" if w.get("swept") else "sweep pending"
    return out, f"{side} · trigger {lamp:.2f} · {swept_txt} · {laws} diamond(s)"


if __name__ == "__main__":
    main()
