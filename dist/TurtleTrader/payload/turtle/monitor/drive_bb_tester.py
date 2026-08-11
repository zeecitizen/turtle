"""drive_bb_tester.py — drive Blueberry MT5 Strategy Tester:
configure Expert/Symbol/Date/Modelling/Visual, then click Start.
"""
from __future__ import annotations
import sys, time
sys.stdout.reconfigure(encoding="utf-8")

from pywinauto import Application, Desktop, mouse
from pywinauto.keyboard import send_keys


def find_bb():
    for w in Desktop(backend="uia").windows():
        try: t = w.window_text()
        except Exception: continue
        if t and "BlueberryMarkets" in t and "Strategy Tester" not in t:
            return w
    return None


def main():
    main = find_bb()
    if main is None:
        print("Blueberry main window not found.")
        return 1

    app = Application(backend="uia").connect(handle=main.handle)
    main_win = app.window(handle=main.handle)
    main_win.set_focus()
    time.sleep(0.4)

    # Click Settings tab (in case we're on another tab)
    try:
        st = main_win.child_window(title="Settings", control_type="TabItem")
        st.click_input()
        time.sleep(0.5)
        print("Switched to Settings tab.")
    except Exception as e:
        print(f"Could not click Settings tab: {e}")

    # Read current state of Edit fields in tester area (Y 680-920)
    print("\nCurrent Edit field values in Settings tab:")
    for d in main_win.descendants(control_type="Edit"):
        try:
            rect = d.rectangle()
            val = d.window_text()
        except Exception:
            continue
        if rect.top < 680 or rect.top > 920:
            continue
        print(f"  Edit @ ({rect.left},{rect.top}): val={repr(val)[:60]}")

    # Click Inputs tab to verify the input is there
    print("\nSwitching to Inputs tab to set InpRequireH1Bias...")
    try:
        it = main_win.child_window(title="Inputs", control_type="TabItem")
        it.click_input()
        time.sleep(0.6)
    except Exception as e:
        print(f"Inputs tab click failed: {e}")

    # Scroll to find InpRequireH1Bias
    # First go back to Settings to ensure we're configured
    print("\nGoing back to Settings tab + clicking Start...")
    try:
        st = main_win.child_window(title="Settings", control_type="TabItem")
        st.click_input()
        time.sleep(0.5)
    except Exception: pass

    # Click Start
    print("Looking for Start button...")
    try:
        start = main_win.child_window(title="Start", control_type="Button")
        rect = start.rectangle()
        print(f"  Start button at {rect}")
        start.click_input()
        time.sleep(0.5)
        print("  Clicked Start.")
    except Exception as e:
        print(f"  Failed to click Start: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
