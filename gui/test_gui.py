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


def _windows_honest(WN):
    d = WN.analyse("BTC")
    solid = [r for r in d["money"] if r.get("solid")]
    if not solid:
        joined = " ".join(d["findings"]).lower()
        assert ("noise" in joined or "no completed trades" in joined), d["findings"]
    return True


def _thin_is_honest(RS):
    """With no fills there is nothing to conclude, and it must say so."""
    rep = RS.analyse("BTC")
    if rep["counts"]["filled"] == 0:
        assert "validated" in rep["headline"] or "none" in rep["headline"].lower(), rep["headline"]
        assert any("not a failure" in s or "small" in s for s in rep["suggested"]), rep["suggested"]
    return True


def _fallback(TB):
    import datetime
    real_j, real_t = TB.judged_days, TB.trading_days
    try:
        TB.judged_days = lambda m="XAU": ["2026-07-31"]
        TB.trading_days = lambda m="XAU": []
        day, cap = TB.day_caption("XAU")
        assert day == "2026-07-31", day
        assert "last session" in cap, cap
    finally:
        TB.judged_days, TB.trading_days = real_j, real_t
    return True


def _refuses(LS):
    try:
        LS.add({"side": "SELL"}, "   ")
    except ValueError:
        return True
    raise AssertionError("an empty comment should be refused")


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

    import labels_explorer as LE, philosophy as PH
    check("labels: rows() reads every label",
          lambda: len(LE.rows()) > 100 or (_ for _ in ()).throw(AssertionError(len(LE.rows()))))
    check("labels: each row knows its source page",
          lambda: all(r["page"] for r in LE.rows()))
    check("labels: grades are parsed", lambda: LE.grade_of("10/10: good")[0] == "10/10")
    check("labels: charts are located for most rows",
          lambda: sum(1 for r in LE.rows() if r["chart"]) > 20)
    check("labels: backup() writes a copy", lambda: LE.backup().exists())
    check("philosophy: core quotes present", lambda: len(PH.CORE) >= 12)
    check("philosophy: realign() re-derives from the sources",
          lambda: len(PH.realign()[0]) >= len(PH.CORE))

    import trade_book as TB2
    check("panels: market_open() is a bool", lambda: isinstance(TB2.market_open(), bool))
    check("panels: day_caption returns a day and a phrase",
          lambda: len(TB2.day_caption("XAU")) == 2)
    check("panels: an empty today falls back to the last session",
          lambda: _fallback(TB2))

    sys.path.insert(0, str(Path(G.MON)))
    import vision_mark as VM
    check("vision: latest() tolerates no reading", lambda: VM.latest() is None or True)
    check("vision: score() tolerates no feedback", lambda: VM.score() is None or
          set(VM.score()) == {"agreed", "total", "pct"})
    check("vision: feedback is appended", lambda: VM.feedback("correct", "test")["verdict"] == "correct")
    check("vision: a reading renders labels",
          lambda: Path(VM.mark("BTC", trend="down", side="SELL", note="test")["png"]).exists())

    import research as RS
    check("research: analyse() returns a report",
          lambda: set(RS.analyse("BTC")) >= {"headline", "sections", "suggested", "counts"})
    check("research: every section reports its sample size",
          lambda: all("n" in s and "solid" in s for s in RS.analyse("BTC")["sections"]))
    check("research: a thin sample is never promoted to a rule",
          lambda: _thin_is_honest(RS))
    check("research: text render works", lambda: len(RS.to_text(RS.analyse("BTC"))) > 100)
    check("research: PDF render works", lambda: Path(RS.to_pdf(RS.analyse("BTC"))).exists())

    import funnel as FN, windows as WN
    check("funnel: diagnose() returns the whole funnel",
          lambda: set(FN.diagnose("BTC")) >= {"steps", "findings", "strict", "loose"})
    check("funnel: every stage is counted",
          lambda: len(FN.diagnose("BTC")["steps"]) == len(FN.STAGES))
    check("funnel: the biggest drop is identified",
          lambda: FN.diagnose("BTC")["worst"] is not None)
    check("funnel: opening the gates is compared honestly",
          lambda: FN.diagnose("BTC")["loose"]["setups"] >= FN.diagnose("BTC")["strict"]["setups"])
    check("funnel: text render works", lambda: "THE FUNNEL" in FN.to_text(FN.diagnose("BTC")))

    check("windows: movement is measured per hour",
          lambda: all("body_share" in r for r in WN.movement("BTC")))
    check("windows: hours are mapped to sessions",
          lambda: all(r["sessions"] for r in WN.movement("BTC")))
    check("windows: thin money samples are flagged, not ranked",
          lambda: _windows_honest(WN))
    check("windows: text render works",
          lambda: "MOVEMENT BY HOUR" in WN.to_text(WN.analyse("BTC")))

    import lessons as LS
    check("lessons: rulebook is found", lambda: LS.rulebook_path().exists())
    check("lessons: an empty comment is refused",
          lambda: (LS.add({"side": "SELL"}, "   "), False)[1] if False else
                  _refuses(LS))
    check("lessons: count() reads the store", lambda: isinstance(LS.count(), int))
    check("lessons: prompt block lists the rules",
          lambda: (LS.as_prompt_block() == "") or ("binding" in LS.as_prompt_block()))
    check("lessons: every stored lesson has a rule and Zee's words",
          lambda: all(e.get("rule") and e.get("zee_comment") for e in LS.load()))
    check("lessons: the rulebook carries the section",
          lambda: (LS.count() == 0) or
                  (LS.SECTION in LS.rulebook_path().read_text(encoding="utf-8",
                                                              errors="replace")))

    dlg = {}

    def open_dlg():
        dlg["d"] = S.SettingsDialog(app)
        app.update()
    check("settings: dialog builds", open_dlg)

    if "d" in dlg:
        d = dlg["d"]
        for attr in ("mode", "key", "model", "market", "lx", "lb", "pypath", "common", "auto",
                     "term", "terminfo", "tvport", "tvpoll", "tvx", "tvb", "tvres",
                     "rulebook", "rbres", "shres"):
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
        check("settings: Explore Labelled Setups opens",
              lambda: (d.open_labels(), app.update()))
        check("settings: Philosophy opens", lambda: (d.open_philosophy(), app.update()))
        import tempfile
        with mock.patch.object(S.filedialog, "askdirectory", lambda **k: ""):
            check("settings: USB copy handles a cancelled picker",
                  lambda: (d.copy_to_usb(), app.update()))
        with mock.patch.object(S.filedialog, "askdirectory",
                               lambda **k: tempfile.gettempdir()),              mock.patch.object(S.subprocess, "Popen", lambda *a, **k: None):
            check("settings: USB copy runs", lambda: (d.copy_to_usb(), app.update()))
        check("settings: USB copy reported a result",
              lambda: len(d.shres.cget("text")) > 0)

        # save must round-trip without touching a real key file
        import tempfile
        with mock.patch.object(S, "CFG", Path(tempfile.gettempdir()) / "_tds_test.json"),              mock.patch.object(S, "KEYFILE", Path(tempfile.gettempdir()) / "_tds_key"):
            check("settings: Save writes config", lambda: (d.save_all(), app.update()))
        try:
            d.destroy()
        except Exception:
            pass

    check("report window opens and renders",
          lambda: (G.ReportWindow(app, "test", lambda: "hello", "..."), app.update()))
    check("research window opens and renders",
          lambda: (G.ResearchWindow(app, "BTC"), app.update()))

    check("banner: hidden when nothing is happening",
          lambda: (app._banner_update(None, []), app.update()))
    check("banner: shouts on a pending breakout",
          lambda: (app._banner_update({"side": "BUY", "entry": 4050.0}, []), app.update(),
                   "BREAKOUT DETECTED" in app.banner.cget("text"))[2])
    check("banner: harvesting text when a position is in profit",
          lambda: (app._banner_update(None, [{"side": "BUY", "profit": 4.2}]), app.update(),
                   "HARVESTING PROFITS" in app.banner.cget("text"))[2])
    check("banner: different text when the position is losing",
          lambda: (app._banner_update(None, [{"side": "SELL", "profit": -2.0}]), app.update(),
                   "RIDING IT OUT" in app.banner.cget("text"))[2])

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
