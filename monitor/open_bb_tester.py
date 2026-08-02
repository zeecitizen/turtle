"""open_bb_tester.py — drive Blueberry MT5 to open Strategy Tester in Visual mode
and preload the S1Trader v2.53 config (H1Bias=true) for a backtest replay.

We don't try to click "Start" — that's the one human action that confirms what
runs. Everything before that is automated.
"""
from __future__ import annotations
import sys, time
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

from pywinauto import Desktop, Application
from pywinauto.keyboard import send_keys


def find_bb():
    for w in Desktop(backend="uia").windows():
        try:
            t = w.window_text()
        except Exception:
            continue
        if not t: continue
        if "Strategy Tester" in t or "Visualization" in t: continue
        # Blueberry-Demo / Blueberry-Live02
        if "BlueberryMarkets" in t or "Blueberry" in t:
            return t, w
    return None, None


def main():
    title, w = find_bb()
    if w is None:
        print("Blueberry MT5 main window not found. Is it running?")
        return 1
    print(f"Found: {title}")
    w.set_focus()
    time.sleep(0.4)
    # Ctrl+R toggles the Strategy Tester panel
    print("Sending Ctrl+R to open Strategy Tester panel...")
    send_keys("^r")
    time.sleep(0.6)
    print("Done. Strategy Tester panel should now be visible at bottom of Blueberry MT5.")
    print()
    print("Suggested tester settings for the v2.53 H1Bias backtest replay:")
    print("  - Settings tab → Expert: S1Trader, Symbol: XAUUSD, Period: M5")
    print("  - Dates: 2026.06.03 → 2026.06.04 (or wider)")
    print("  - Modeling: Every tick based on real ticks")
    print("  - Visual mode: ON (so you see the markers as the chart replays)")
    print("  - Inputs tab → InpRequireH1Bias = true (others as defaults)")
    print("  - Click START")
    return 0


if __name__ == "__main__":
    sys.exit(main())
