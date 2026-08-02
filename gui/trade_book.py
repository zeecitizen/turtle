"""trade_book.py — Turtle Desktop's trade book: today's trades, drill-down, grading, PDF.

Zee 2026-08-03: *"har trade jo humne li uss par Double Click karain… pata chalay k is setup
par mere kya comments hain, aur ye setup kyun fail hua, aur game bhi waheen 2 buttons…
aur failed setups ki aik PDF report generate ho."*

Three sources are joined into one row per trade:
  monitor/claude_judgments.jsonl     what Claude decided and WHY (every TAKE and SKIP)
  Common/Files/<mkt>_fills.csv       the broker's truth: real entry, exit and P&L
  monitor/setup_labels/zee_labels.json   Zee's own comments and 0/10 grades

Live price and any running position come from the EA heartbeat (<mkt>_live.json), because
Python cannot query MT5 on this ARM64 machine.
"""
from __future__ import annotations
import csv, json, textwrap
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
LABELS = MON / "setup_labels" / "zee_labels.json"
JOURNAL = MON / "claude_judgments.jsonl"
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

MKT = {"XAU": dict(fills="caseexec_fills.csv", live="xau_live.json", label="XAUUSD"),
       "BTC": dict(fills="btc_fills.csv",      live="btc_live.json", label="BTCUSD")}


# ── live -----------------------------------------------------------------------------
def live(market="XAU"):
    """Broker truth from the EA heartbeat: price, spread, equity, running positions."""
    f = COMMON / MKT[market]["live"]
    if not f.exists():
        return {"error": "no heartbeat — is the EA attached with Algo Trading on?"}
    try:
        d = json.loads(f.read_text(encoding="ascii", errors="replace"))
    except Exception as e:
        return {"error": f"heartbeat unreadable: {e}"}
    d["age_sec"] = int(datetime.now(timezone.utc).timestamp()) - int(d.get("ts", 0))
    if d["age_sec"] > 30:
        d["stale"] = True
    return d


# ── the book -------------------------------------------------------------------------
def _labels():
    try:
        return json.loads(LABELS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _judgments(day=None):
    out = []
    if not JOURNAL.exists():
        return out
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if day and not str(d.get("judged_utc", "")).startswith(day):
            continue
        out.append(d)
    return out


def _fills(market):
    """Broker fills. Header-tolerant: match by name when present, else by position."""
    f = COMMON / MKT[market]["fills"]
    if not f.exists():
        return []
    rows = []
    try:
        txt = f.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except Exception:
        return []
    if not txt:
        return []
    head = [h.strip().lower() for h in txt[0].split(",")]
    named = "time" in head or "usd" in head or "profit" in head
    for line in txt[1:] if named else txt:
        c = [x.strip() for x in line.split(",")]
        if len(c) < 4:
            continue
        d = dict(zip(head, c)) if named else {}
        def g(*names, idx=None):
            for n in names:
                if n in d and d[n]:
                    return d[n]
            return c[idx] if idx is not None and idx < len(c) else ""
        rows.append({"time": g("time", "close_time", idx=0),
                     "side": g("side", "type", idx=1).upper(),
                     "lots": g("lots", "volume", idx=2),
                     "entry": g("entry", "open_price", idx=3),
                     "exit": g("exit", "close_price", idx=4),
                     "usd": g("usd", "profit", "pnl", idx=6),
                     "reason": g("reason", "comment", idx=7)})
    return rows


def _num(x, d=0.0):
    try:
        return float(str(x).replace("$", "").replace("+", ""))
    except Exception:
        return d


def book(market="XAU", day=None):
    """One row per judged setup, joined to its broker fill and Zee's comment."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    labels = _labels()
    fills = _fills(market)
    rows = []
    for j in _judgments(day):
        if j.get("market") != market:
            continue
        key = f"{j.get('time', '')}_{j.get('side', '')}"
        # match a fill by side + closest entry price
        fill, best = None, 9e9
        for f in fills:
            if f["side"] != j.get("side"):
                continue
            d = abs(_num(f["entry"]) - _num(j.get("entry")))
            if d < best and d < 5:
                fill, best = f, d
        lab = labels.get(f"trade_{key}", {})
        usd = _num(fill["usd"]) if fill else None
        rows.append({
            "key": key,
            "time": j.get("time", ""),
            "side": j.get("side", ""),
            "verdict": j.get("verdict", ""),
            "mult": j.get("mult", ""),
            "lots": j.get("lots", fill["lots"] if fill else ""),
            "entry": j.get("entry", ""),
            "exit": fill["exit"] if fill else "",
            "usd": usd,
            "status": ("WIN" if usd and usd > 0 else "LOSS" if usd and usd < 0 else
                       ("open/not filled" if j.get("verdict") == "TAKE" else "skipped")),
            "claude_reason": j.get("reason", ""),
            "zee_comment": (lab.get("zee") or ""),
            "strength": j.get("strength", ""),
            "brk_body": j.get("brk_body", ""),
            "uhv_vol": j.get("uhv_vol", ""),
            "judged_utc": j.get("judged_utc", ""),
        })
    rows.sort(key=lambda r: r["judged_utc"], reverse=True)
    return rows


def summary(rows):
    took = [r for r in rows if r["verdict"] == "TAKE"]
    filled = [r for r in took if r["usd"] is not None]
    net = sum(r["usd"] for r in filled)
    wins = [r for r in filled if r["usd"] > 0]
    return {"judged": len(rows), "taken": len(took), "skipped": len(rows) - len(took),
            "filled": len(filled), "net": net,
            "wr": (100.0 * len(wins) / len(filled)) if filled else None}


# ── PDF ------------------------------------------------------------------------------
def failed_pdf(market="XAU", day=None, out=None):
    """One page per losing trade: its chart, Claude's reasoning, Zee's comment, the numbers.
    Written with matplotlib so no extra dependency is needed."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.image as mpimg

    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [r for r in book(market, day) if r["usd"] is not None and r["usd"] < 0]
    out = Path(out or (REPO / "daily_reports" / f"failed_setups_{market}_{day}.pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(out) as pdf:
        # cover
        fig = plt.figure(figsize=(11.7, 8.3)); fig.patch.set_facecolor("white")
        fig.text(0.5, 0.72, "Failed setups", ha="center", size=30, weight="bold")
        fig.text(0.5, 0.65, f"{MKT[market]['label']}   ·   {day}", ha="center", size=15, color="#555")
        s = summary(book(market, day))
        fig.text(0.5, 0.50,
                 f"{len(rows)} losing trade(s)\n\n"
                 f"judged {s['judged']}   ·   taken {s['taken']}   ·   skipped {s['skipped']}\n"
                 f"net ${s['net']:+.2f}" + (f"   ·   win rate {s['wr']:.0f}%" if s["wr"] is not None else ""),
                 ha="center", size=13, color="#333", linespacing=1.8)
        fig.text(0.5, 0.14, "Every page: what Claude saw, why it was taken, and what Zee says went wrong.",
                 ha="center", size=10, color="#777")
        pdf.savefig(fig); plt.close(fig)

        if not rows:
            fig = plt.figure(figsize=(11.7, 8.3))
            fig.text(0.5, 0.5, "No losing trades today.", ha="center", size=20, color="#16a34a")
            pdf.savefig(fig); plt.close(fig)

        for r in rows:
            fig = plt.figure(figsize=(11.7, 8.3)); fig.patch.set_facecolor("white")
            fig.text(0.06, 0.94, f"{r['side']}  {r['lots']} lot  @ {r['entry']}   ->   ${r['usd']:+.2f}",
                     size=17, weight="bold", color="#dc2626")
            fig.text(0.06, 0.905, f"{r['time']}   ·   exit {r['exit']}   ·   mult {r['mult']}   ·   "
                                  f"strength {r['strength']}   ·   brk_body {r['brk_body']}   ·   UHV vol {r['uhv_vol']}",
                     size=9.5, color="#555")
            png = MON / "setup_labels" / f"trade_{r['key'].replace(':', '')}.png"
            if not png.exists():
                png = MON / "setup_labels" / "pending_setup.png"
            if png.exists():
                ax = fig.add_axes([0.06, 0.44, 0.88, 0.44]); ax.axis("off")
                try:
                    ax.imshow(mpimg.imread(str(png)))
                except Exception:
                    pass
            y = 0.38
            for title, body, col in (("Claude's reasoning", r["claude_reason"] or "(none)", "#1d4ed8"),
                                     ("Zee's comment", r["zee_comment"] or "(not commented yet)", "#b45309")):
                fig.text(0.06, y, title, size=11, weight="bold", color=col); y -= 0.028
                for line in textwrap.wrap(body, 118)[:7]:
                    fig.text(0.06, y, line, size=9.5, color="#222"); y -= 0.022
                y -= 0.02
            pdf.savefig(fig); plt.close(fig)
    return out


if __name__ == "__main__":
    import sys
    mk = sys.argv[1].upper() if len(sys.argv) > 1 else "XAU"
    if len(sys.argv) > 2 and sys.argv[2] == "pdf":
        print(failed_pdf(mk))
    else:
        rows = book(mk)
        print(json.dumps({"live": live(mk), "summary": summary(rows), "rows": rows[:5]},
                         indent=1, default=str))
