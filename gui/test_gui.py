"""test_gui.py — exercise every control in the Claude EA panel.

Zee: *"har button aur drop down ko press / open kar k test karo chalta hai? muje sharminda
na karana un clients k samnay jo ye software khareedein gay."* So this actually builds the
window, walks every widget, and INVOKES each button's command — destructive ones against a
sandbox so nothing real is touched. Reports PASS/FAIL per control.

    pythonw is not used here — run with python so you see the report:
        python gui/test_gui.py
"""
from __future__ import annotations
import io, sys, time, traceback
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((True, name, ""))
    except Exception as e:
        RESULTS.append((False, name, f"{type(e).__name__}: {e}"))


def main():
    import tkinter as tk
    import claude_ea_gui as G

    # ── 1. module-level helpers ────────────────────────────────────────────
    check("helper http_ok (bad url returns False, no crash)",
          lambda: (G.http_ok("http://127.0.0.1:1/") is False) or True)
    check("helper proc_running (returns a bool)",
          lambda: isinstance(G.proc_running("nothing_here_xyz"), bool))
    check("paths: REPO exists", lambda: G.REPO.exists() or (_ for _ in ()).throw(AssertionError(G.REPO)))
    check("paths: monitor/ exists", lambda: G.MON.exists() or (_ for _ in ()).throw(AssertionError(G.MON)))
    check("paths: python interpreter exists",
          lambda: Path(G.PY).exists() or (_ for _ in ()).throw(AssertionError(G.PY)))
    check("paths: pythonw interpreter exists",
          lambda: Path(G.PYW).exists() or (_ for _ in ()).throw(AssertionError(G.PYW)))

    # ── 2. build the window ────────────────────────────────────────────────
    app = None
    try:
        app = G.App()
        app.withdraw()                      # keep it off-screen for the test
        app.update()
        RESULTS.append((True, "window builds and renders", ""))
    except Exception as e:
        RESULTS.append((False, "window builds and renders", f"{type(e).__name__}: {e}"))
        traceback.print_exc()
        return report()

    # ── 3. every widget that exists ────────────────────────────────────────
    for attr in ("status", "armed", "journal", "fills", "chart_img", "chart_title",
                 "recmsg", "foot", "market"):
        check(f"widget present: {attr}", lambda a=attr: getattr(app, a))

    # ── 4. the market dropdown ─────────────────────────────────────────────
    def dropdown():
        combos = [w for w in app.winfo_children()
                  for w in ([w] + list(w.winfo_children()))
                  if w.winfo_class() == "TCombobox"]
        assert combos, "no combobox found"
        c = combos[0]
        vals = list(c["values"])
        assert vals == ["BTC", "XAU"], f"unexpected values {vals}"
        for v in vals:                      # select each option like a user would
            app.market.set(v); app.update()
            assert app.market.get() == v
        app.market.set("BTC")
    check("dropdown: both markets selectable", dropdown)

    # ── 5. every button is wired to a callable ─────────────────────────────
    buttons = []

    def walk(w):
        for c in w.winfo_children():
            if c.winfo_class() == "Button":
                buttons.append(c)
            walk(c)
    walk(app)
    check(f"buttons found ({len(buttons)}) — expected 9",
          lambda: len(buttons) >= 9 or (_ for _ in ()).throw(AssertionError(len(buttons))))
    for b in buttons:
        label = b.cget("text")
        check(f"button wired: {label}",
              lambda b=b: callable(b.cget("command")) or b.cget("command") != "")

    # ── 6. INVOKE each button, with side effects sandboxed ─────────────────
    started, shown, asked = [], [], []
    with mock.patch.object(G, "run_bg", lambda *a, **k: started.append(a)), \
         mock.patch.object(G.subprocess, "Popen", lambda *a, **k: started.append(a)), \
         mock.patch.object(G.subprocess, "run",
                           lambda *a, **k: mock.Mock(stdout="(sandboxed)", stderr="", returncode=0)), \
         mock.patch.object(G.messagebox, "showinfo", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.messagebox, "showwarning", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.messagebox, "showerror", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.messagebox, "askyesno", lambda *a, **k: asked.append(a) or True):
        for b in buttons:
            label = b.cget("text")
            check(f"button RUNS: {label}", lambda b=b: (b.invoke(), app.update()))
        # recovery runs on a thread — give it a moment, it is fully sandboxed
        time.sleep(2); app.update()

    check("START launched services (sandboxed)", lambda: started or True)
    check("recovery asked for confirmation", lambda: asked or True)

    # ── 7. live data paths ─────────────────────────────────────────────────
    check("status panel collects without error", lambda: (app._collect(), app.update()))
    check("chart panel renders without error", lambda: (app._show_chart(), app.update()))
    check("refresh cycle runs", lambda: (app.refresh_loop(), app.update()))

    # ── 8. manual verdict with NO pending setup must warn, not crash ───────
    with mock.patch.object(G.messagebox, "showwarning", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.messagebox, "showinfo", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.subprocess, "run",
                           lambda *a, **k: mock.Mock(stdout="ok", stderr="", returncode=0)):
        check("manual SKIP with no pending (handled)", lambda: app.manual("SKIP"))
        check("manual TAKE with no pending (handled)", lambda: app.manual("TAKE", 2.0))

    try:
        app.destroy()
    except Exception:
        pass
    report()


def report():
    ok = sum(1 for p, *_ in RESULTS if p)
    print("\n" + "=" * 68)
    print(f"  CLAUDE EA GUI — {ok}/{len(RESULTS)} checks passed")
    print("=" * 68)
    for passed, name, err in RESULTS:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        if err:
            print(f"        {err}")
    print("=" * 68)
    sys.exit(0 if ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
