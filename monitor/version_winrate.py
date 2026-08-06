"""version_winrate.py — the version-vs-winrate graph (Zee 2026-08-06):
"draw a graph of software versions against winrate so we can visually track
after which version the winrate dropped and after which one it climbed."

Reads EA load fingerprints (the version timeline) + turtle_fills, scores every
fill against the version active at its moment, and renders a dual-axis chart:
winrate line + net-P&L bars per version. -> monitor/setup_labels/version_winrate.png
"""
import sys, os, glob, re
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8"
TF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/turtle_fills.csv")
OUT = Path(__file__).parent / "setup_labels" / "version_winrate.png"


def _read(p):
    try:
        return Path(p).read_text(encoding="utf-16", errors="ignore").splitlines()
    except Exception:
        return Path(p).read_text(errors="ignore").splitlines()


def build():
    timeline = []
    for lf in sorted(glob.glob(D + "/MQL5/Logs/*.log")):
        day = os.path.basename(lf)[:8]
        if day < "20260804":
            continue
        for l in _read(lf):
            m = re.search(r"(\d\d:\d\d:\d\d).*\[CaseExec\] (v1\.\d+) loaded", l)
            if m:
                timeline.append((datetime.strptime(day + " " + m.group(1), "%Y%m%d %H:%M:%S"),
                                 m.group(2)))
    timeline.sort()

    def version_at(local_dt):
        v = "v1.4x"
        for dt, ver in timeline:
            if dt <= local_dt:
                v = ver
            else:
                break
        return v

    stats = OrderedDict()
    for r in TF.read_text(errors="ignore").splitlines():
        c = r.split(",")
        if len(c) < 8 or c[0] < "2026.08.04 20:00":
            continue
        try:
            lots, pnl = float(c[5]), float(c[7])
        except ValueError:
            continue
        if lots not in (0.10, 0.30, 0.60):
            continue
        local = datetime.strptime(c[0], "%Y.%m.%d %H:%M:%S") + timedelta(hours=2)
        v = version_at(local)
        s = stats.setdefault(v, [0, 0, 0.0])
        s[0] += 1
        s[1] += pnl > 0
        s[2] += pnl

    vers = [v for v, s in stats.items() if s[0] >= 3]      # skip tiny buckets
    wr = [stats[v][1] / stats[v][0] * 100 for v in vers]
    net = [stats[v][2] for v in vers]
    n = [stats[v][0] for v in vers]

    fig, ax1 = plt.subplots(figsize=(14, 7))
    x = range(len(vers))
    colors = ["#2f9e44" if v >= 0 else "#e03131" for v in net]
    ax2 = ax1.twinx()
    ax2.bar(x, net, color=colors, alpha=0.35, width=0.6, zorder=1)
    ax2.set_ylabel("net P&L ($)", fontsize=12)
    ax2.axhline(0, color="#888", lw=0.8)
    ax1.plot(x, wr, "-o", color="#1c7ed6", lw=3, markersize=9, zorder=3)
    for i, (w, cnt) in enumerate(zip(wr, n)):
        ax1.annotate(f"{w:.0f}%\n(n={cnt})", (i, w), textcoords="offset points",
                     xytext=(0, 12), ha="center", fontsize=10, fontweight="bold")
    ax1.axhline(50, color="#aaa", ls="--", lw=0.8)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(vers, fontsize=11, fontweight="bold")
    ax1.set_ylabel("winrate %", fontsize=12, color="#1c7ed6")
    ax1.set_ylim(0, 100)
    ax1.set_title("EA version vs WINRATE (line) and NET P&L (bars) — live fills, Ghost era",
                  fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT, dpi=110)
    plt.close(fig)
    print(f"version graph -> {OUT}")
    return OUT


if __name__ == "__main__":
    build()
