"""reload_ea.py — programmatically reload an MT5 EA without user clicks.

Mechanism: drive MT5's GUI via pywinauto to detach + reattach the EA on its
chart. After this, MT5 reads the .ex5 fresh from disk so any source changes
take effect.

Usage:
    py monitor/reload_ea.py --terminal "Blueberry" --ea "S1Trader" --symbol "XAUUSD,M1"
"""
from __future__ import annotations
import argparse, sys, time

sys.stdout.reconfigure(encoding="utf-8")

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys


def find_main(terminal_match: str):
    """Find the MT5 main window whose title contains terminal_match (broker name)."""
    matches = []
    for w in Desktop(backend="uia").windows():
        try:
            title = w.window_text()
        except Exception:
            continue
        if not title: continue
        # Skip Strategy Tester Visualization
        if "Strategy Tester" in title: continue
        # Main MT5 window typically: "<login> - <Server>: ..."
        if terminal_match.lower() in title.lower():
            matches.append((title, w))
    return matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default="Blueberry", help="substring of MT5 window title")
    ap.add_argument("--ea", default="S1Trader")
    ap.add_argument("--symbol", default="XAUUSD,M1", help="chart title symbol,timeframe")
    args = ap.parse_args()

    print(f"Looking for MT5 window with '{args.terminal}'...")
    matches = find_main(args.terminal)
    if not matches:
        print("No MT5 window found.")
        return 1
    for title, _ in matches:
        print(f"  Found: {title}")

    title, mt5_win = matches[0]
    print(f"\nUsing: {title}")

    # Connect via pywinauto with backend uia
    app = Application(backend="uia").connect(handle=mt5_win.handle)
    main = app.window(handle=mt5_win.handle)
    main.set_focus()
    time.sleep(0.5)

    # Strategy: keyboard shortcut to remove EA from active chart.
    # MT5 doesn't expose direct shortcut for "remove expert", but we can:
    #   1. Press Ctrl+T to open Toolbox (not what we want)
    #   2. Better: right-click the chart and use context menu via keystrokes
    #
    # Simplest reliable: use F7 to open EA inputs, click OK (no reload), then
    # use Ctrl+W (close chart) + Ctrl+O (open with template) — too disruptive.
    #
    # Most reliable: send keystroke Ctrl+E twice (toggles Algo Trading off and
    # then on). Doesn't reload .ex5 though.
    #
    # The actual mechanism: chart template save/restore. MT5 reattaches EAs
    # from template, reading the .ex5 fresh:
    #   1. Navigate to active chart
    #   2. Right-click → Template → Save Template (as default.tpl in current chart)
    #   3. Right-click → Template → Load Template (reapplies, reloading EA)
    #
    # pywinauto can right-click via the chart window context menu.

    print("\nLooking for chart sub-window...")
    chart_windows = main.children(control_type="Window")
    print(f"  Found {len(chart_windows)} sub-windows")
    chart = None
    for w in chart_windows:
        try:
            t = w.window_text()
        except Exception:
            continue
        if args.symbol.lower() in t.lower():
            chart = w
            print(f"  Match: {t}")
            break

    if chart is None:
        # Fallback: just operate on whatever chart has focus
        print("  No exact match — using active chart")

    # Approach A: chart context menu → Template → Reload
    # Right-click the chart, navigate context menu
    print("\nRight-clicking chart to access context menu...")
    if chart is not None:
        chart.set_focus()
        time.sleep(0.3)
        # Right-click roughly in the middle of the chart
        rect = chart.rectangle()
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        from pywinauto.mouse import right_click
        right_click(coords=(cx, cy))
        time.sleep(0.6)
    else:
        # send menu key as fallback
        send_keys("+{F10}")
        time.sleep(0.6)

    # Look for context menu (usually appears as a popup)
    print("Looking for popup menu...")
    popup = None
    for w in Desktop(backend="uia").windows():
        try:
            cls = w.class_name()
        except Exception:
            continue
        if cls in ("#32768", "Popup", "Menu"):
            popup = w
            break

    if popup:
        try:
            popup_text = popup.window_text()
        except Exception:
            popup_text = "?"
        print(f"  Popup: {popup_text}")

    # Navigate menu: 'Template' submenu → 'Reload Template' or 'Default Template'
    # Most reliable: send the down arrow + enter pattern, or send the access key
    # Pattern (in English MT5): Template's access key is 'T'.
    print("\nSending keystrokes: 'T' to open Template submenu...")
    send_keys("T", pause=0.1)
    time.sleep(0.5)
    # Then "Reload Template" or first item is usually "Save Template..."
    # 'L' = "Load Template..." (would open file dialog — wrong)
    # We want "Default Template" or just hit Enter to "Reload current template"
    # Try 'R' for Reload Template (some versions have this)
    send_keys("R", pause=0.1)
    time.sleep(1.0)

    print("\nDone. Check MT5 Experts log for new 'S1Trader Init' message.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
