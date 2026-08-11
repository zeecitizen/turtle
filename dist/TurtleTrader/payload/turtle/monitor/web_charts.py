"""web_charts.py — one entry point the dashboard can call to draw any cockpit chart
(Zee 2026-08-07: "make sure the web page also has same buttons and images as the GUI").

    py monitor/web_charts.py forming            -> forming_now.png + context_now.png
    py monitor/web_charts.py context-now        -> context_now.png
    py monitor/web_charts.py versions           -> version_winrate.png
    py monitor/web_charts.py trade <ts> <side> <exit>   -> forensic_*.png + context_*.png

Prints the produced paths, one per line. Never raises to the caller.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # detached process: sys.stdout is None
    pass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    if len(sys.argv) < 2:
        print("usage: web_charts.py forming|context-now|versions|trade <ts> <side> <exit>")
        return
    what = sys.argv[1]
    import forensic_chart as F
    if what == "forming":
        p, msg = F.draw_forming()
        print(p or "")
        print(F.draw_context_now() or "" if p else "")
        print(msg)
    elif what == "context-now":
        print(F.draw_context_now() or "")
    elif what == "versions":
        import version_winrate as V
        print(V.build())
    elif what == "trade":
        ts, side, px = sys.argv[2], sys.argv[3], float(sys.argv[4])
        print(F.draw_trade(ts, side, px) or "")
        print(F.draw_context(ts, side) or "")
    else:
        print("unknown: " + what)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:            # the web must never see a stack trace
        print("ERR " + str(e))
