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
    # GROUND TRUTH FIRST (2026-08-07, Zee: "UHV and BO are both green, impossible"):
    # a signal-path fire prints its id, and the matcher logged exactly what it emitted
    # (side, entry price, setup time) in monitor/oanda_signals.jsonl. Identify the
    # breakout candle by that ENTRY PRICE — timestamps can disagree between the live
    # feed and the archive, prices cannot.
    sig_id = re.search(r"signal #(\d+)", best[1])
    if sig_id:
        try:
            import json as _j
            led = Path(__file__).parent / "oanda_signals.jsonl"
            rec = None
            for ln in led.read_text(encoding="utf-8").splitlines():
                d = _j.loads(ln)
                if str(d.get("id")) == sig_id.group(1):
                    rec = d
            if rec:
                want = float(rec["entry"])
                # the live feed revises a closed bar by a few cents, so match on the
                # NEAREST close rather than an exact one (0.50 sanity cap)
                cands = [x for x in load()
                         if abs((x[0] - entry_utc).total_seconds()) <= 420]
                bo = min(cands, key=lambda x: abs(x[4] - want)) if cands else None
                if bo is not None and abs(bo[4] - want) <= 0.50:
                    entry_utc = bo[0]
                    import oanda_live_matcher as _M2, build_entry_review_m5 as _B2
                    for k3, v3 in _M2.CFG.items():
                        setattr(_B2, k3, v3)
                    bb2 = [_B2.Bar(x[0], x[1], x[2], x[3], x[4], int(x[5])) for x in load()]
                    best2 = None
                    for st2 in _B2.detect_full(bb2):
                        if st2["side"] != side:
                            continue
                        gap = abs((st2["open_t"] - bo[0]).total_seconds())
                        if gap <= 180 and (best2 is None or gap < best2[0]):
                            best2 = (gap, st2)
                    if best2:
                        st2 = best2[1]
                        uhv_utc = st2["uhv_t"]
                        lamp = (bb2[st2["u"]].h if side == "BUY" else bb2[st2["u"]].l)
                    else:
                        # LAST RESORT (2026-08-08, Zee: "second time this bug is
                        # happening"): the archive can differ enough from the live feed
                        # that the detector will not reproduce the setup. Name the UHV
                        # the way the detector would: the loudest counter-coloured
                        # candle in the 15 bars before the breakout.
                        bi2 = next((k for k, x in enumerate(bb2) if x.t == bo[0]), None)
                        if bi2 is not None:
                            zone = [k for k in range(max(0, bi2 - 15), bi2)
                                    if (bb2[k].is_bear if side == "BUY" else bb2[k].is_bull)]
                            if zone:
                                k2 = max(zone, key=lambda k: bb2[k].v)
                                uhv_utc = bb2[k2].t
                                lamp = bb2[k2].h if side == "BUY" else bb2[k2].l
        except Exception:
            pass
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


def draw_context_now(bars_back=180):
    """The same CIRCUMSTANCES panel for the live moment — used under the forming
    setup, so a setup on the way is judged in the same visual frame as a taken
    trade (Zee 2026-08-07)."""
    return draw_context(None, None, bars_back=bars_back,
                        out=Path(__file__).parent / "setup_labels" / "context_now.png")


def draw_context(broker_ts, side, bars_back=180, out=None):
    """THE CIRCUMSTANCES (Zee 2026-08-07): a zoomed-out view under the close-up —
    candles + volume over a wide window, the trade's entry marked, and the compass
    line drawn through the swing peaks, so it is obvious at a glance what the trend
    and slope looked like when this trade was taken."""
    import trend_eyes as _TE
    rows = load()
    if not rows:
        return None
    live = broker_ts is None
    r = None if live else resolve_trade(broker_ts, side)
    if live:
        e_utc = rows[-1][0]
    else:
        e_utc = r["entry_utc"] if r else (datetime.strptime(broker_ts, "%Y.%m.%d %H:%M:%S")
                                          - timedelta(hours=3))
    ei = next((i for i, x in enumerate(rows)
               if x[0] <= e_utc < x[0] + timedelta(minutes=1)), None)
    if ei is None:
        near = sorted(range(len(rows)), key=lambda i: abs((rows[i][0] - e_utc).total_seconds()))
        ei = near[0] if near else None
    if ei is None:
        return None
    lo = max(0, ei - bars_back)
    hi = min(len(rows), ei + 40)
    win = rows[lo:hi]
    if len(win) < 20:
        return None
    idx = pd.DatetimeIndex([x[0] + timedelta(hours=5) for x in win])
    df = pd.DataFrame({"Open": [x[1] for x in win], "High": [x[2] for x in win],
                       "Low": [x[3] for x in win], "Close": [x[4] for x in win],
                       "Volume": [x[5] for x in win]}, index=idx)
    tb = [(x[0], x[2], x[3], x[4], x[5]) for x in rows]
    a = _TE.auto_call(tb, upto=ei + 1)
    slope = _TE.slope_of(tb, upto=ei + 1)
    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    ttl = ((f"THE CIRCUMSTANCES NOW — compass says {a['trend']} · 30-bar slope "
            f"{slope:+.3f} pts/bar   ({a['why'][:58]})") if live else
           (f"THE CIRCUMSTANCES — compass said {a['trend']} · 30-bar slope "
            f"{slope:+.3f} pts/bar   ({a['why'][:60]})"))
    fig, axes = mpf.plot(df, type="candle", style=style, volume=True, figsize=(19, 7),
                         returnfig=True, title=ttl)
    ax = axes[0]
    epos = ei - lo
    ax.axvline(epos, color="#1c7ed6", lw=2.2, ls="-", alpha=0.9, zorder=5)
    # the badge sits ABOVE the whole window, never over the candles (Zee 2026-08-07:
    # "the label is hiding candles") — anchored to the window's high, not the bar's.
    _top = max(x[2] for x in win)
    ax.annotate("now" if live else "this trade", xy=(epos, win[epos][2]),
                xytext=(epos, _top), textcoords="data",
                fontsize=13, fontweight="bold", color="white",
                ha="center", va="bottom", annotation_clip=False, zorder=6,
                bbox=dict(boxstyle="round,pad=0.35", fc="#1c7ed6", ec="none"),
                arrowprops=dict(arrowstyle="->", lw=2.2, color="#1c7ed6"))
    # the compass line through the swing peaks
    sw = _TE.find_swings(tb, upto=ei + 1)
    pk = [x for x in sw if x.kind == ("H" if a["trend"] != "DOWNTREND" else "H")][-3:]
    pts = [(x.i - lo, x.price) for x in pk if lo <= x.i < hi]
    if len(pts) >= 2:
        col = {"UPTREND": "#2f9e44", "DOWNTREND": "#e03131"}.get(a["trend"], "#1c7ed6")
        ax.plot([q[0] for q in pts], [q[1] for q in pts], "-o", color=col, lw=2.4,
                markersize=7, alpha=0.95, zorder=4)
    lo_p = min(x[3] for x in win); hi_p = max(x[2] for x in win)
    rng_p = hi_p - lo_p
    ax.set_ylim(lo_p - max(rng_p * 0.06, 0.3), hi_p + max(rng_p * 0.16, 0.6))
    out = out or (Path(__file__).parent / "setup_labels" /
                  f"context_{(broker_ts or 'now')[11:].replace(':', '') or 'now'}.png")
    fig.savefig(str(out), dpi=95, bbox_inches="tight")
    plt.close(fig)
    return out


# ─────────────────────────────────────────────────────────────────────────────────
# EVERY POSSIBLE SETUP, AND WHERE EACH ONE DIED
#
# Zee, 2026-08-13: "i wanna see how many possible setups did we prune through on a
# chart."
#
# The EA only ever reports what it FIRED. This walks the same rules over every bar
# on screen and records the stage each candidate reached, so the pruning is visible
# instead of invisible. The rules are imported from zee_uhv.py — never re-implemented
# here, because a second copy of the rules would drift from the first.
# ─────────────────────────────────────────────────────────────────────────────────
def _probe(Z, bars, i):
    """Run the pipeline at bar i and report HOW FAR it got, not just pass/fail."""
    t = Z.trend_at(bars, i)
    if t == 0:
        return "ranging", None, None
    side = "buy" if t > 0 else "sell"
    origin = Z.retracement_origin(bars, i - 1, side)
    if origin is None:
        return "no retracement", side, None
    uhv = Z.find_uhv(bars, origin, i, side)
    if uhv is None or uhv == i:
        return "no lawful UHV", side, None
    brk = Z.breakout_after(bars, uhv, side)
    if brk is None:
        return "UHV never broken", side, uhv
    if brk != i:
        return "broke on another bar", side, uhv
    return "FIRED", side, uhv


def draw_possible(bars_back=180, out=None):
    """Draw every UHV the rules considered on the recent chart, and mark which ones
    survived to a trade. Returns (png_path, summary_line)."""
    import importlib, collections
    sys.path.insert(0, str(Path(__file__).parent))
    Z = importlib.import_module("zee_uhv")

    # load() reads the rolling live window plus the old history file — together only
    # a few hundred recent bars. tape_archive_xau.csv is the permanent record (it exists
    # precisely because the bridge used to keep only 300 bars), so it is merged in here
    # to give this view real depth. Deduped by timestamp; other forensic functions are
    # deliberately left on load() alone so this cannot disturb them.
    rows = {x[0]: x for x in load()}
    arch = Path(__file__).parent / "tape_archive_xau.csv"
    if arch.exists():
        for r in csv.DictReader(open(arch, encoding="utf-8")):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            rows.setdefault(t, (t, float(r["open"]), float(r["high"]), float(r["low"]),
                                float(r["close"]), float(r["volume"])))
    rows = [rows[k] for k in sorted(rows)]
    if not rows:
        return None, "no bars"
    win = rows[-bars_back:]
    if len(win) < 80:
        return None, f"only {len(win)} bars — need at least 80"
    bars = [{"o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5]} for x in win]

    stage = collections.Counter()
    considered = {}        # uhv bar index -> [side, fired?]
    fires = []
    for i in range(60, len(bars)):
        st, side, uhv = _probe(Z, bars, i)
        stage[st] += 1
        if uhv is not None:
            rec = considered.setdefault(uhv, [side, False])
            if st == "FIRED":
                rec[1] = True
                fires.append((i, uhv, side))

    idx = pd.DatetimeIndex([x[0] + timedelta(hours=5) for x in win])   # Karachi
    df = pd.DataFrame({"Open": [x[1] for x in win], "High": [x[2] for x in win],
                       "Low": [x[3] for x in win], "Close": [x[4] for x in win],
                       "Volume": [x[5] for x in win]}, index=idx)

    n_uhv = len(considered)
    n_fired = sum(1 for v in considered.values() if v[1])
    pruned = n_uhv - n_fired
    # THE TITLE MUST WRAP. Zee, 2026-08-13: "make text above it multiline that way chart
    # size grows". With bbox_inches="tight" a single long title stretches the whole image
    # to fit the text, so once the GUI scales it down to the screen the CHART is what
    # shrinks. Three short lines keep the figure the width of the plot.
    ttl = (f"EVERY POSSIBLE SETUP - last {len(win)} bars\n"
           f"{n_uhv} UHV candidate(s) considered  ->  {n_fired} traded, {pruned} pruned\n"
           f"bars: {stage['ranging']} ranging · {stage['no retracement']} no-retracement · "
           f"{stage['no lawful UHV']} no-UHV · {stage['UHV never broken']} UHV-never-broke"
           "        (OANDA feed - the live EA reads Blueberry and can differ)")

    style = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":")
    fig, axes = mpf.plot(df, type="candle", style=style, volume=True, figsize=(19, 11),
                         returnfig=True, title=ttl, panel_ratios=(4, 1))
    ax = axes[0]

    # labels stagger, because candidates cluster and a pile of overlapping badges is
    # unreadable — which defeats the entire point of this view
    last_u, tier = -99, 0
    for u, (side, fired) in sorted(considered.items()):
        tier = (tier + 1) % 3 if u - last_u < 12 else 0
        last_u = u
        col = "#2f9e44" if fired else "#f08c00"          # green traded, amber pruned
        lvl = bars[u]["h"] if side == "buy" else bars[u]["l"]
        ax.axvspan(u - 0.5, u + 0.5, color=col, alpha=0.30 if fired else 0.16, zorder=0)
        ax.plot([u - 0.5, u + 0.5], [lvl, lvl], color=col, lw=2.2 if fired else 1.2,
                zorder=3)
        base = -20 if side == "buy" else 14
        off = base + (-14 * tier if side == "buy" else 14 * tier)
        ax.annotate(("TRADED" if fired else "pruned") + f" {side}",
                    xy=(u, bars[u]["l"] if side == "buy" else bars[u]["h"]),
                    textcoords="offset points", xytext=(0, off),
                    fontsize=7.5, fontweight="bold", color="white", ha="center",
                    annotation_clip=False, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.22", fc=col, ec="none"))

    for i, u, side in fires:
        ax.axvline(i, color="#1c7ed6", lw=1.4, ls="--", alpha=0.85, zorder=2)

    lo = min(x[3] for x in win); hi = max(x[2] for x in win)
    pad = max((hi - lo) * 0.10, 0.30)
    ax.set_ylim(lo - pad, hi + pad)
    out = out or (Path(__file__).parent / "setup_labels" / "possible_setups.png")
    fig.savefig(str(out), dpi=150, bbox_inches="tight")   # 150 dpi so zooming has pixels
    plt.close(fig)
    kept = f"{100.0 * n_fired / n_uhv:.0f}%" if n_uhv else "n/a"
    return out, (f"{n_uhv} candidates -> {n_fired} traded ({kept} kept), {pruned} pruned "
                 f"· {stage['ranging']} of {sum(stage.values())} bars were ranging")


if __name__ == "__main__":
    main()
