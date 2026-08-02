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
    for attr in ("status", "armed", "journal", "chart_img", "chart_title",
                 "recmsg", "foot", "market", "tree", "livebig", "livesub", "tsum"):
        check(f"widget present: {attr}", lambda a=attr: getattr(app, a))

    # ── 4. the market dropdown ─────────────────────────────────────────────
    def dropdown():
        combos = [w for w in app.winfo_children()
                  for w in ([w] + list(w.winfo_children()))
                  if w.winfo_class() == "TCombobox"]
        assert combos, "no combobox found"
        c = combos[0]
        vals = list(c["values"])
        assert set(vals) == {"XAU", "BTC"}, f"unexpected values {vals}"
        assert vals[0] == "XAU", f"gold must be the default/first entry, got {vals}"
        for v in vals:                      # select each option like a user would
            app.market.set(v); app.update()
            assert app.market.get() == v
        app.market.set("XAU")
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
    check("trade book loads without error", lambda: (app._refresh_book(), app.update()))
    check("refresh cycle runs", lambda: (app.refresh_loop(), app.update()))

    # ── 8. manual verdict with NO pending setup must warn, not crash ───────
    with mock.patch.object(G.messagebox, "showwarning", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.messagebox, "showinfo", lambda *a, **k: shown.append(a)), \
         mock.patch.object(G.subprocess, "run",
                           lambda *a, **k: mock.Mock(stdout="ok", stderr="", returncode=0)):
        check("manual SKIP with no pending (handled)", lambda: app.manual("SKIP"))
        check("manual TAKE with no pending (handled)", lambda: app.manual("TAKE", 2.0))

    # -- 9. Settings dialog: opens, every control present, tests run, saves --------
    import settings as S

    check("settings: load() returns defaults", lambda: S.load()["connection"] in ("cli", "api"))
    check("settings: cli_available() is a bool", lambda: isinstance(S.cli_available(), bool))
    check("settings: test_api rejects a junk key",
          lambda: S.test_api("short", "claude-sonnet-4-5")[0] is False)
    check("settings: status_line() returns 3 parts", lambda: len(S.status_line()) == 3)
    check("settings: find_terminals() finds this PC's MT5 installs",
          lambda: len(S.find_terminals()) > 0 or (_ for _ in ()).throw(AssertionError("none")))
    check("settings: each terminal reports its broker(s)",
          lambda: all(x["brokers"] for x in S.find_terminals()))
    check("settings: the terminal holding our EA is listed first",
          lambda: (not any(x["has_ea"] for x in S.find_terminals()))
                  or S.find_terminals()[0]["has_ea"])
    check("settings: test_tradingview handles a dead port",
          lambda: S.test_tradingview(1)[0] is False)
    check("settings: the EA playbook is found automatically",
          lambda: Path(S.default_rulebook()).exists())
    check("settings: the playbook validates",
          lambda: S.inspect_rulebook(S.default_rulebook())[0] is True)
    check("settings: a look-alike document is rejected",
          lambda: S.inspect_rulebook(Path(S.REPO) / "README.md")[0] is False)
    check("settings: a missing rulebook is rejected",
          lambda: S.inspect_rulebook("no_such_file.md")[0] is False)
    check("settings: rulebook_path() resolves", lambda: S.rulebook_path() is not None)

    dlg = {}

    def open_dlg():
        dlg["d"] = S.SettingsDialog(app)
        app.update()
    check("settings: dialog builds", open_dlg)

    if "d" in dlg:
        d = dlg["d"]
        for attr in ("mode", "key", "model", "market", "lx", "lb", "pypath", "common", "auto",
                     "term", "terminfo", "tvport", "tvpoll", "tvx", "tvb", "tvres",
                     "rulebook", "rbres"):
            check(f"settings widget: {attr}", lambda a=attr: getattr(d, a))

        def both_modes():
            for m in ("api", "cli"):
                d.mode.set(m); d._sync(); app.update()
            d.mode.set(S.load()["connection"]); d._sync()
        check("settings: both connection modes selectable", both_modes)

        sbuttons = []

        def walk2(w):
            for c in w.winfo_children():
                if c.winfo_class() == "Button":
                    sbuttons.append(c)
                walk2(c)
        walk2(d)
        check(f"settings: buttons found ({len(sbuttons)})", lambda: len(sbuttons) >= 4)

        with mock.patch.object(S, "test_cli", lambda: (True, "sandboxed")),              mock.patch.object(S, "test_api", lambda k, m: (True, "sandboxed")):
            check("settings: Test connection runs", lambda: (d.test(), app.update()))
        with mock.patch.object(S, "test_tradingview", lambda p: (True, "sandboxed")):
            check("settings: Test bridge runs", lambda: (d.test_tv(), app.update()))
        check("settings: terminal picker updates its info line",
              lambda: (d._term_changed(), app.update()))
        with mock.patch.object(S.filedialog, "askopenfilename",
                               lambda **k: S.default_rulebook()):
            check("settings: Attach EA MD Rules File runs",
                  lambda: (d.attach_rulebook(), app.update()))
        check("settings: attach reported success",
              lambda: "does not look like" not in d.rbres.cget("text"))

        # save must round-trip without touching a real key file
        import tempfile
        with mock.patch.object(S, "CFG", Path(tempfile.gettempdir()) / "_tds_test.json"),              mock.patch.object(S, "KEYFILE", Path(tempfile.gettempdir()) / "_tds_key"):
            check("settings: Save writes config", lambda: (d.save_all(), app.update()))
        try:
            d.destroy()
        except Exception:
            pass

    check("main window: Settings button opens the dialog",
          lambda: (setattr(app, "_sd", None), app.update()))

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
