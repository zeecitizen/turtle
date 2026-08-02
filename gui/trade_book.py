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

MKT = {"XAU": dict(fills="caseexec_fills.csv", live="xau_live.json",
                   hist="xau_history.csv", label="XAUUSD"),
       "BTC": dict(fills="btc_fills.csv", live="btc_live.json",
                   hist="btc_history.csv", label="BTCUSD")}


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


def history(market="XAU"):
    """MT5's OWN closed trades, exported by the EA. This is where the real 2026-07-31 gold
    trades live -- no CSV in the repo ever had them, only the terminal's History tab."""
    f = COMMON / MKT[market]["hist"]
    if not f.exists():
        return []
    out = []
    try:
        for r in csv.DictReader(f.open(encoding="utf-8", errors="replace")):
            if not r.get("close_time"):
                continue
            out.append({"close_time": r["close_time"].strip(),
                        "side": (r.get("side") or "").strip().upper(),
                        "lots": r.get("lots", ""), "entry": r.get("entry", ""),
                        "exit": r.get("exit", ""), "pts": r.get("pts", ""),
                        "usd": _num(r.get("usd")), "magic": r.get("magic", ""),
                        "comment": (r.get("comment") or "").strip()})
    except Exception:
        return []
    out.sort(key=lambda x: x["close_time"], reverse=True)
    return out


def market_open():
    """FX/metals week: Sun 21:00 UTC -> Fri 21:00 UTC."""
    n = datetime.now(timezone.utc)
    d = (n.weekday() + 1) % 7
    m = n.hour * 60 + n.minute
    if d == 6:
        return False
    if d == 0:
        return m >= 21 * 60
    if d == 5:
        return m < 21 * 60
    return True


def judged_days(market="XAU"):
    """Days Claude actually judged something, newest first."""
    days = []
    for j in _judgments():
        if j.get("market") != market:
            continue
        d = str(j.get("judged_utc", ""))[:10]
        if d and d not in days:
            days.append(d)
    return sorted(days, reverse=True)


def last_session(market="XAU"):
    """The day the panels should show: today if it has anything, else the most recent day
    that does. Zee: an empty panel should say 'Friday's verdicts', not 'nothing yet'."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    have = set(judged_days(market)) | set(trading_days(market))
    if today in have:
        return today, "today", False
    prev = sorted(have, reverse=True)
    if prev:
        d = prev[0]
        try:
            name = datetime.strptime(d, "%Y-%m-%d").strftime("%a %d %b")
        except Exception:
            name = d
        return d, name, True
    return today, "today", False


def day_caption(market="XAU"):
    """One phrase for a panel header."""
    day, name, is_old = last_session(market)
    if not is_old:
        return day, ("waiting for the first verdict" if market_open() else "today")
    return day, f"last session \u2014 {name}"


def trading_days(market="XAU"):
    """Days that actually have trades, newest first — so the panel can default to the last
    session rather than an empty 'today' over a weekend."""
    days = []
    for h in history(market):
        d = h["close_time"][:10].replace(".", "-")
        if d not in days:
            days.append(d)
    return days


def book(market="XAU", day=None):
    """One row per judged setup, joined to its broker fill and Zee's comment.

    Rows also include REAL MT5 trades that Claude never judged (anything traded before this
    system existed, e.g. 2026-07-31), so the panel shows the account's actual history."""
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
    # real MT5 trades for that day that have no Claude judgment behind them
    seen = {(r["side"], round(_num(r["entry"]), 2)) for r in rows}
    for h in history(market):
        d = h["close_time"][:10].replace(".", "-")
        if d != day:
            continue
        if (h["side"], round(_num(h["entry"]), 2)) in seen:
            continue
        key = f"{h['close_time']}_{h['side']}"
        lab = labels.get(f"trade_{key}", {})
        rows.append({
            "key": key, "time": h["close_time"][-8:-3] or h["close_time"],
            "side": h["side"], "verdict": "(pre-Claude)", "mult": "",
            "lots": h["lots"], "entry": h["entry"], "exit": h["exit"],
            "usd": h["usd"],
            "status": "WIN" if h["usd"] > 0 else "LOSS" if h["usd"] < 0 else "flat",
            "claude_reason": f"Traded by the EA before Claude judged setups"
                             f"{' (magic ' + h['magic'] + ')' if h['magic'] else ''}."
                             f"{' ' + h['comment'] if h['comment'] else ''}",
            "zee_comment": (lab.get("zee") or ""),
            "strength": "", "brk_body": "", "uhv_vol": "",
            "judged_utc": h["close_time"].replace(".", "-").replace(" ", "T"),
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
