"""camel_gui.py — the camel cockpit: regenerate the humps, look, command the ghost.

Zee 2026-08-04: one click to redraw the camel humps on live candles, view the fresh
image, then press UPTREND / DOWNTREND / RANGE — and that human call gates the ghost:
    UPTREND    -> only BUY lamps may be raided
    DOWNTREND  -> only SELL lamps
    RANGE      -> the ghost waits for the lamps to shine (no trades)
    AUTO       -> no human gate; the matcher runs pure

The call is written to Common\\Files\\trend_call.json and read by oanda_live_matcher
on every cycle. Calls EXPIRE after 30 minutes (an M1 trend goes stale fast) — expired
means AUTO, and the cockpit shows the countdown so a dead call is never invisible.

Run:  py gui/camel_gui.py
"""
from __future__ import annotations
import json, sys, threading, time
from pathlib import Path
import tkinter as tk
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitor"))
import trend_eyes as TE                                     # noqa: E402

CALL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/trend_call.json")
ROVR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/regime_override.json")
PNG = Path(TE.__file__).parent / "setup_labels" / "camel_humps.png"
TTL = 600     # a manual call fades after 10 minutes, then AUTO (Zee 2026-08-04)
BACK = 120

BG, FG, DIM = "#101418", "#e8e8e8", "#8a949e"
COLORS = {"UPTREND": "#2f9e44", "DOWNTREND": "#e03131", "RANGE": "#f08c00", "AUTO": "#4dabf7"}


def current_call():
    try:
        d = json.loads(CALL.read_text(encoding="ascii"))
        age = int(time.time()) - int(d.get("ts", 0))
        if d.get("trend", "AUTO") == "AUTO" or age > TTL:
            return "AUTO", age
        return d["trend"], age
    except Exception:
        return "AUTO", 0




# ── HOW LONG DID THE TRADE LAST? (Zee 2026-08-13) ────────────────────────────────
# "on this page can you add trade duration? so i know how long the trade lasted in
#  minutes there"
#
# turtle_fills.csv records only the CLOSE — broker_time, price, P&L. The OPEN time
# lives in the EA's own log, where every fire prints "[ZEE] BUY @price — N diamond(s)".
# So the duration has to be assembled from two files.
#
# THE TIMEZONE TRAP, and it has bitten this project before: MT5 writes its expert log
# in the machine's LOCAL time (Karachi) while the fills carry BROKER time (UTC+3).
# Karachi is UTC+5, so a fire logged at 03:51 is a broker-time 01:51 entry. Pairing
# them without that shift produced hold times of 221 and 1,130 minutes on trades that
# actually lasted 44 seconds.
LOG_TO_BROKER_H = 2          # Karachi (UTC+5) -> broker (UTC+3)

def _fire_times(logdir):
    """Every moment the EA opened a setup, in BROKER time."""
    import glob, re as _re
    out = []
    for f in sorted(glob.glob(str(Path(logdir) / "*.log"))):
        stem = Path(f).stem
        if not (len(stem) == 8 and stem.isdigit()):
            continue
        day = datetime(int(stem[:4]), int(stem[4:6]), int(stem[6:]))
        try:
            txt = Path(f).read_text(encoding="utf-16", errors="ignore")
        except Exception:
            try: txt = Path(f).read_text(errors="ignore")
            except Exception: continue
        for line in txt.splitlines():
            if "[ZEE]" not in line: continue
            if "BUY" not in line and "SELL" not in line: continue
            m = _re.search(r"(\d\d):(\d\d):(\d\d)", line)
            if not m: continue
            local = day.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                                second=int(m.group(3)))
            out.append(local - timedelta(hours=LOG_TO_BROKER_H))
    return sorted(out)

def _durations(fills_file, logdir):
    """{close_timestamp -> minutes held}. A setup closes all its tickets on the same
    second, so one duration covers the whole stack. Each fire is used once, matched to
    the first close that follows it — anything over 4 hours is left blank rather than
    shown, because a wrong number here is worse than none."""
    import csv as _c
    fires = _fire_times(logdir)
    closes = []
    try:
        for r in _c.DictReader(Path(fills_file).open(errors="ignore")):
            if "XAU" not in (r.get("symbol") or "").upper(): continue
            closes.append(r["broker_time"])
    except Exception:
        return {}
    seen, out, used = [], {}, set()
    for ts in closes:
        if ts in out: continue
        try: ct = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
        except ValueError: continue
        best = None
        for i, ft in enumerate(fires):
            if i in used or ft > ct: continue
            if best is None or ft > fires[best]: best = i
        if best is None: continue
        mins = (ct - fires[best]).total_seconds() / 60.0
        if 0 <= mins <= 240:
            out[ts] = mins
            used.add(best)
    return out

# ── Karachi time in the Trades window ─────────────────────────────────────────────
# Zee, 2026-08-11: "can it show time in timezone of Karachi so its easier to compare
# when the last trade happened."
#
# turtle_fills.csv stores BROKER time. Measured against his own clock on 2026-08-11:
# a fill stamped 13:10:22 broker was written to disk at 15:10:22 local, and he confirmed
# Karachi was 16:11 while the machine read 16:10 — so this machine runs on Karachi time
# and the broker is two hours behind it (broker UTC+3, Karachi UTC+5).
#
# The offset is DETECTED rather than hardcoded, because MT5 brokers commonly move between
# UTC+2 and UTC+3 with European DST while Karachi never changes. Detection compares the
# newest fill's broker stamp against the file's own mtime — the file is written the
# instant the deal closes, so the gap between the two IS the offset. Falls back to +2.
_KARACHI_SHIFT_H = None


def _karachi_shift(fills_path):
    global _KARACHI_SHIFT_H
    if _KARACHI_SHIFT_H is not None:
        return _KARACHI_SHIFT_H
    _KARACHI_SHIFT_H = 2
    try:
        import os
        from datetime import datetime
        last = None
        for line in fills_path.read_text(errors="ignore").splitlines():
            if line[:5].isdigit() or line[:4].isdigit():
                last = line
        if last:
            bt = datetime.strptime(last.split(",")[0], "%Y.%m.%d %H:%M:%S")
            mt = datetime.fromtimestamp(os.path.getmtime(fills_path))
            h = round((mt - bt).total_seconds() / 3600)
            if -12 <= h <= 12:
                _KARACHI_SHIFT_H = h
    except Exception:
        pass
    return _KARACHI_SHIFT_H


def _to_karachi(ts, shift_h):
    """'2026.08.11 13:10:22' broker -> '08.11  3:10:22 pm' Karachi.

    Zee, 2026-08-11: "can u make it show times in 12 hour time format, not 24 hour
    time format.. so its easier to read." The hour is space-padded rather than
    zero-padded so the colons still line up down the column — a list of trades is
    scanned vertically, and ragged columns are what make it hard to read.
    """
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S") + timedelta(hours=shift_h)
        h12 = d.hour % 12 or 12
        return f"{d:%m.%d} {h12:2d}:{d:%M:%S} {'am' if d.hour < 12 else 'pm'}"
    except Exception:
        return ts[5:]



class Cockpit:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🐫 Camel Cockpit — the ghost obeys")
        self.root.configure(bg=BG)
        self.photo = None

        # SCROLLABLE BODY (Zee 2026-08-07: "I can't see the bottom buttons"): every
        # widget below lives inside this canvas, so a tall chart can never push the
        # controls off-screen. Mouse wheel scrolls; the window opens at 92% height.
        sw0, sh0 = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{int(sw0 * 0.92)}x{int(sh0 * 0.92)}+20+10")
        _outer = tk.Frame(self.root, bg=BG); _outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(_outer, bg=BG, highlightthickness=0)
        _vsb = tk.Scrollbar(_outer, orient="vertical", command=self._canvas.yview)
        self.body = tk.Frame(self._canvas, bg=BG)
        self.body.bind("<Configure>",
                       lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._win_id = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        _hsb = tk.Scrollbar(_outer, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=_vsb.set, xscrollcommand=_hsb.set)
        # grid so both bars sit correctly around the canvas (pack cannot do this cleanly)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        _vsb.grid(row=0, column=1, sticky="ns")
        _hsb.grid(row=1, column=0, sticky="ew")
        _outer.rowconfigure(0, weight=1); _outer.columnconfigure(0, weight=1)
        self._wheel_target = self._canvas
        # GUARDED WHEEL (Zee 2026-08-07 — the console filled with TclError "invalid
        # command name .!toplevel.!canvas"): bind_all is global, so a child window's
        # binding outlived the window and kept scrolling a destroyed canvas. Every
        # wheel event now checks the target still exists, and closing a child window
        # hands the wheel back to the cockpit.
        def _wheel(e, axis="y"):
            t = getattr(self, "_wheel_target", None)
            try:
                if t is not None and t.winfo_exists():
                    (t.yview_scroll if axis == "y" else t.xview_scroll)(
                        int(-e.delta / 120), "units")
            except Exception:
                pass
        self.root.bind_all("<MouseWheel>", _wheel)
        self.root.bind_all("<Shift-MouseWheel>", lambda e: _wheel(e, "x"))

        self.stage = tk.Label(self.body, text="", font=("Segoe UI", 26, "bold"),
                              bg=BG, fg=DIM)
        self.stage.pack(pady=(8, 0))
        srow = tk.Frame(self.body, bg=BG); srow.pack(pady=(2, 0))
        tk.Button(srow, text="👀 draw the setup forming now", font=("Segoe UI", 11, "bold"),
                  bg="#7048e8", fg="white", padx=12, pady=5, relief="flat",
                  command=self.show_forming).pack()
        self.regime = tk.Label(self.body, text="", font=("Segoe UI", 20, "bold"),
                               bg=BG, fg="#e03131")
        self.regime.pack(pady=(2, 0))
        self.clocks = tk.Label(self.body, text="", font=("Segoe UI", 12), bg=BG, fg=DIM)
        self.clocks.pack(pady=(0, 2))
        self.machine = tk.Label(self.body, text="machine: …", font=("Segoe UI", 13, "bold"),
                                bg=BG, fg=DIM)
        self.machine.pack(pady=(4, 2))
        self.img = tk.Label(self.body, bg=BG)
        self.img.pack(padx=10, pady=4)

        # TWO ROWS (Zee 2026-08-07): tools on top, the trend calls beneath — one long
        # line forced horizontal scrolling every time.
        row = tk.Frame(self.body, bg=BG); row.pack(pady=(6, 2))
        row2 = tk.Frame(self.body, bg=BG); row2.pack(pady=(0, 6))
        tk.Button(row, text="🔄  Regenerate humps", font=("Segoe UI", 13, "bold"),
                  bg="#343a40", fg=FG, padx=16, pady=8, relief="flat",
                  command=self.regen).pack(side="left", padx=6)
        # No AUTO button (Zee): AUTO is the resting state — every manual call fades
        # back to it after 10 minutes on its own.
        tk.Button(row, text="🔄 refresh build", font=("Segoe UI", 11, "bold"),
                  bg="#e8590c", fg="white", padx=10, pady=8, relief="flat",
                  command=self.refresh_app).pack(side="left", padx=6)
        tk.Button(row, text="📜 Trades", font=("Segoe UI", 12, "bold"),
                  bg="#0b7285", fg="white", padx=12, pady=8, relief="flat",
                  command=self.show_trades).pack(side="left", padx=6)
        tk.Button(row, text="📊 Versions", font=("Segoe UI", 12, "bold"),
                  bg="#1c7ed6", fg="white", padx=12, pady=8, relief="flat",
                  command=self.show_versions).pack(side="left", padx=6)
        tk.Button(row2, text="⚡ START REGIME (30 min)", font=("Segoe UI", 12, "bold"),
                  bg="#7048e8", fg="white", padx=12, pady=8, relief="flat",
                  command=self.force_regime).pack(side="left", padx=6)
        for name, label in [("UPTREND", "📈 UPTREND — buy lamps"),
                            ("DOWNTREND", "📉 DOWNTREND — sell lamps"),
                            ("RANGE", "📦 RANGE — ghost waits")]:
            tk.Button(row2, text=label, font=("Segoe UI", 12, "bold"),
                      bg=COLORS[name], fg="white", padx=12, pady=8, relief="flat",
                      command=lambda n=name: self.set_call(n)).pack(side="left", padx=6)

        self.status = tk.Label(self.body, text="", font=("Segoe UI", 12), bg=BG, fg=FG)
        self.status.pack(pady=(2, 10))

        self.tick()
        self.tick_stage()
        self._busy = False
        self.auto_loop()

    def auto_loop(self):
        """Zee 2026-08-05: the humps must redraw THEMSELVES — he caught the cockpit
        only refreshing on the button. Auto-regen every 60s, button still works."""
        self.regen()
        self.root.after(60000, self.auto_loop)

    def regen(self):
        if self._busy:
            return
        self._busy = True
        self.machine.config(text="machine: redrawing…")
        def work():
            try:
                bars = TE.load_bars()
                TE.draw(bars, BACK, PNG)
                r = TE.read_trend(bars)
                a = TE.auto_call(bars)
                txt = (f"structure: {r['trend']} ({r['why']})    "
                       f"AUTO/peak-slant: {a['trend']} ({a['why']})")
                rtxt, rcol = self._regime_text(bars)
                self.root.after(0, lambda: self.regime.config(text=rtxt, fg=rcol))
            except Exception as e:
                txt = f"machine error: {e}"
            self.root.after(0, lambda: self.show(txt))
        threading.Thread(target=work, daemon=True).start()

    def show(self, machine_txt):
        self._busy = False
        self.machine.config(text=machine_txt)
        try:
            from PIL import Image, ImageTk
            im = Image.open(PNG)
            sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
            im.thumbnail((int(sw * 0.86), int(sh * 0.66)))   # fill the real screen
            self.photo = ImageTk.PhotoImage(im)
        except Exception:
            self.photo = tk.PhotoImage(file=str(PNG))
        self.img.config(image=self.photo)

    # ── THE TRADE LIST with a forensic button per trade (Zee 2026-08-07) ──
    def show_trades(self):
        import csv as _csv
        top = tk.Toplevel(self.root); top.title("📜 Trades — click 🔍 to inspect the setup")
        top.configure(bg=BG)
        head = tk.Label(top, text="XAUUSD fills (Karachi time) · held · — 🔍 draws the UHV, trigger lines, BO candle",
                        font=("Segoe UI", 13, "bold"), bg=BG, fg=FG)
        head.pack(pady=(10, 6))
        canvas = tk.Canvas(top, bg=BG, highlightthickness=0,
                           width=760, height=min(700, int(self.root.winfo_screenheight() * 0.6)))
        sb = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        sb.pack(side="right", fill="y", pady=(0, 10))
        self._wheel_target = canvas
        top.bind("<Destroy>", lambda e, t=top: (
            setattr(self, "_wheel_target", self._canvas) if e.widget is t else None))

        # how long each setup was held — assembled from the EA's log, see _durations
        try:
            durs = _durations(self.FILLS_F,
                              Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                                   r"/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Logs"))
        except Exception:
            durs = {}

        rows = []
        try:
            for r in self.FILLS_F.read_text(errors="ignore").splitlines():
                c = r.split(",")
                if len(c) < 8 or not c[0].startswith("2026."): continue
                try: lots, pnl = float(c[5]), float(c[7])
                except ValueError: continue
                if lots not in (0.10, 0.20, 0.30, 0.60): continue
                # SYMBOL FILTER (Zee 2026-08-10: "are these XAUUSD?" — they were not.
                # turtle_fills.csv carries every instrument the terminal trades, so the
                # gold cockpit was listing Bitcoin fills as if they were ours. A cockpit
                # that shows another instrument's P&L is worse than one showing nothing.
                if "XAU" not in c[3].upper(): continue
                rows.append((c[0], c[4].replace("_closed", ""), lots, float(c[6]), pnl))
        except Exception:
            pass
        for ts, side, lots, closepx, pnl in reversed(rows[-40:]):
            r = tk.Frame(frame, bg=BG); r.pack(fill="x", pady=1)
            col = "#2f9e44" if pnl > 0 else "#e03131"
            tk.Label(r, text=_to_karachi(ts, _karachi_shift(self.FILLS_F)), font=("Consolas", 11), bg=BG, fg=DIM,
                     width=20, anchor="w").pack(side="left")
            tk.Label(r, text=side, font=("Consolas", 11, "bold"), bg=BG,
                     fg="#4dabf7" if side == "BUY" else "#f08c00", width=5).pack(side="left")
            tk.Label(r, text=f"{lots:.2f}", font=("Consolas", 11), bg=BG, fg=DIM,
                     width=6).pack(side="left")
            tk.Label(r, text=f"{pnl:+8.2f}", font=("Consolas", 12, "bold"), bg=BG,
                     fg=col, width=10).pack(side="left")
            # HELD FOR — blank when the open time cannot be established, never guessed.
            d = durs.get(ts)
            held = (f"{d:.0f}m" if d is not None and d >= 1 else
                    (f"{d*60:.0f}s" if d is not None else "—"))
            tk.Label(r, text=held, font=("Consolas", 11), bg=BG,
                     fg="#f59f00" if (d is not None and d > 30) else DIM,
                     width=7, anchor="e").pack(side="left")
            tk.Button(r, text="🔍 forensic", font=("Segoe UI", 10, "bold"),
                      bg="#343a40", fg=FG, relief="flat", padx=8,
                      command=lambda t=ts, s2=side, x=closepx: self.forensic(t, s2, x)
                      ).pack(side="left", padx=8)

            # ── TEACH THE MACHINE (Zee 2026-08-10) ──────────────────────────────
            # "you can add a comment field under each trade we take wherein i can
            #  save my responses for you to read on the trades taken."
            # His 146 labels on setup_labeller are the most valuable training data
            # this project owns — they are the only place the UHV rule is stated in
            # his own words. This puts the same channel on REAL fills, where the
            # money actually was, so the lesson arrives attached to a receipt.
            note = self.notes.get(ts, "")
            e = tk.Entry(r, font=("Segoe UI", 10), bg="#0f1216",
                         fg="#e6edf3", insertbackground="#e6edf3",
                         relief="flat", width=52)
            e.insert(0, note)
            e.pack(side="left", padx=(4, 6), ipady=3)
            mark = tk.Label(r, text="✓" if note else "", font=("Segoe UI", 11, "bold"),
                            bg=BG, fg="#2f9e44", width=2)
            mark.pack(side="left")
            e.bind("<Return>", lambda ev, t=ts, w=e, m=mark: self.save_note(t, w, m))
            e.bind("<FocusOut>", lambda ev, t=ts, w=e, m=mark: self.save_note(t, w, m))

    # ── the note store ─────────────────────────────────────────────────────────
    NOTES_F = Path(__file__).resolve().parent.parent / "monitor" / "zee_trade_notes.json"

    @property
    def notes(self):
        """Load lazily and keep it on disk, never only in memory: the whole point is
        that Claude reads these later, possibly in another session."""
        if getattr(self, "_notes", None) is None:
            try:
                self._notes = json.loads(self.NOTES_F.read_text(encoding="utf-8"))
            except Exception:
                self._notes = {}
        return self._notes

    def save_note(self, ts, widget, mark=None):
        txt = widget.get().strip()
        cur = self.notes.get(ts, "")
        if txt == cur:
            return
        if txt:
            self.notes[ts] = txt
        else:
            self.notes.pop(ts, None)
        try:
            self.NOTES_F.parent.mkdir(parents=True, exist_ok=True)
            self.NOTES_F.write_text(json.dumps(self.notes, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
            if mark:
                mark.config(text="✓" if txt else "", fg="#2f9e44")
            self.status.config(text=f"📝 saved your note on {ts[5:]} — Claude will read it",
                               fg="#2f9e44")
        except Exception as ex:
            if mark:
                mark.config(text="✗", fg="#e03131")
            self.status.config(text=f"could not save note: {ex}", fg="#e03131")

    def refresh_app(self):
        """Restart the whole stack on the CURRENT code: the matcher (so the newest
        laws are live) and this cockpit itself (so the newest UI is live). Zee should
        never have to wait for Claude to relaunch anything."""
        import subprocess, os
        self.status.config(text="🔄 restarting the stack on the latest build…", fg="#e8590c")
        self.root.update_idletasks()
        py = sys.executable
        root = Path(__file__).resolve().parent.parent
        DETACHED = 0x00000008 | 0x00000200          # DETACHED_PROCESS | NEW_PROCESS_GROUP
        # 1) matcher: kill any running one, start a fresh one on the current code
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                            "Where-Object { $_.CommandLine -match 'oanda_live_matcher' } | "
                            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }"],
                           capture_output=True, timeout=25)
            subprocess.Popen([py, "-u", str(root / "monitor" / "oanda_live_matcher.py")],
                             cwd=str(root), creationflags=DETACHED,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        # 2) this cockpit: launch a fresh copy, then close this one
        try:
            subprocess.Popen([py, str(Path(__file__).resolve())], cwd=str(root),
                             creationflags=DETACHED)
        except Exception as ex:
            self.status.config(text=f"could not restart: {ex}", fg="#e03131")
            return
        self.root.after(900, self.root.destroy)

    def show_forming(self):
        """Zee 2026-08-07: draw the INCOMPLETE setup — which UHV is being considered
        right now and its trigger lines, before any breakout happens."""
        win = tk.Toplevel(self.root); win.title("👀 the setup forming now")
        win.configure(bg=BG)
        lbl = tk.Label(win, text="drawing…", font=("Segoe UI", 14), bg=BG, fg=DIM)
        lbl.pack(padx=20, pady=20)
        def work():
            try:
                sys.path.insert(0, str(Path(TE.__file__).parent))
                import forensic_chart as FC
                import importlib; importlib.reload(FC)
                p, msg = FC.draw_forming()
                ctx = FC.draw_context_now() if p else None
            except Exception as ex:
                p, msg, ctx = None, f"error: {ex}", None
            if p:
                self.root.after(0, lambda: (self._show_pngs(win, lbl, p, ctx),
                                            win.title(f"👀 forming — {msg}")))
            else:
                self.root.after(0, lambda: lbl.config(text=msg))
        threading.Thread(target=work, daemon=True).start()

    def forensic(self, ts, side, exit_px):
        """Draw and show one trade's UHV / trigger lines / BO candle."""
        win = tk.Toplevel(self.root); win.title(f"🔍 {ts} {side}")
        win.configure(bg=BG)
        lbl = tk.Label(win, text="drawing…", font=("Segoe UI", 14), bg=BG, fg=DIM)
        lbl.pack(padx=20, pady=20)

        def work():
            # the real exception must reach the window (2026-08-07) — the old version
            # overwrote every error with "no EA fire line found".
            import traceback
            try:
                sys.path.insert(0, str(Path(TE.__file__).parent))
                import forensic_chart as FC
                import importlib; importlib.reload(FC)
                p = FC.draw_trade(ts, side, exit_px)
                ctx = FC.draw_context(ts, side)        # the circumstances, zoomed out
            except Exception:
                err = traceback.format_exc().strip().splitlines()[-1]
                self.root.after(0, lambda: lbl.config(text="could not draw: " + err))
                return
            if p:
                self.root.after(0, lambda: self._show_pngs(win, lbl, p, ctx))
            else:
                self.root.after(0, lambda: lbl.config(
                    text="this trade has no matching EA fire line in the logs"))
        threading.Thread(target=work, daemon=True).start()

    def _show_pngs(self, win, lbl, path, ctx=None):
        """Zee 2026-08-07: the anatomy on top, THE CIRCUMSTANCES (zoomed-out trend +
        volume) underneath, the whole thing scrollable."""
        from PIL import Image, ImageTk
        lbl.destroy()
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        win.geometry(f"{int(sw*0.86)}x{int(sh*0.86)}")
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._wheel_target = canvas                      # the wheel follows the window
        win.bind("<Destroy>", lambda e, c=canvas: (
            setattr(self, "_wheel_target", self._canvas) if e.widget is win else None))
        win._imgs = []
        maxw = int(sw * 0.80)
        forming = "forming_now" in str(path)
        cap1 = ("👀 THE SETUP FORMING — UHV and its trigger lines, breakout still to come"
                if forming else "🔍 THE SETUP — UHV, trigger lines, breakout candle")
        cap2 = ("🌄 THE CIRCUMSTANCES NOW — trend, slope and volume right now" if forming
                else "🌄 THE CIRCUMSTANCES — trend, slope and volume around this trade")
        for pth, cap in ((path, cap1), (ctx, cap2)):
            if not pth:
                continue
            tk.Label(frame, text=cap, font=("Segoe UI", 13, "bold"),
                     bg=BG, fg=FG).pack(pady=(12, 4))
            im = Image.open(pth); im.thumbnail((maxw, int(sh * 0.75)))
            ph = ImageTk.PhotoImage(im); win._imgs.append(ph)
            l2 = tk.Label(frame, image=ph, bg=BG); l2.image = ph
            l2.pack(padx=8)
            l2.bind("<Button-1>", lambda e, q=pth: self._copy_image(note, q))
        note = tk.Label(frame, text=f"🖱️ click either chart to COPY IT   ·   {Path(path).name}",
                        font=("Segoe UI", 12), bg=BG, fg=DIM)
        note.pack(pady=(8, 4))
        tk.Button(frame, text="📋 copy filename instead", font=("Segoe UI", 11, "bold"),
                  bg="#343a40", fg=FG, relief="flat", padx=10, pady=6,
                  command=lambda: (self.root.clipboard_clear(),
                                   self.root.clipboard_append(str(path)),
                                   note.config(text=f"📋 path copied · {Path(path).name}",
                                               fg="#1c7ed6"))).pack(pady=(0, 14))

    def _copy_image(self, note, path):
        import subprocess
        ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
              f"$i=[System.Drawing.Image]::FromFile('{path}'); "
              "[System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                           capture_output=True, timeout=25, check=True)
            note.config(text=f"✅ image copied — paste it in chat · {Path(path).name}",
                        fg="#2f9e44")
        except Exception as ex:
            note.config(text=f"could not copy ({ex}) · {Path(path).name}", fg="#e03131")

    def _show_png(self, win, lbl, path):
        from PIL import Image, ImageTk
        im = Image.open(path)
        im.thumbnail((int(self.root.winfo_screenwidth() * 0.8),
                      int(self.root.winfo_screenheight() * 0.72)))
        ph = ImageTk.PhotoImage(im)
        lbl.config(image=ph, text=""); lbl.image = ph
        # Zee 2026-08-07: clicking the anatomy copies the IMAGE to the clipboard
        # (paste straight into chat); the button copies the filename as a fallback.
        note = tk.Label(win, text=f"🖱️ click the chart to COPY THE IMAGE   ·   {Path(path).name}",
                        font=("Segoe UI", 12), bg=BG, fg=DIM)
        note.pack(pady=(0, 4))
        def copy_image(_evt=None):
            import subprocess
            ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                  f"$i=[System.Drawing.Image]::FromFile('{path}'); "
                  "[System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()")
            try:
                subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                               capture_output=True, timeout=25, check=True)
                note.config(text=f"✅ image copied — paste it in chat   ·   {Path(path).name}",
                            fg="#2f9e44")
            except Exception as ex:
                note.config(text=f"could not copy image ({ex}) — filename: {Path(path).name}",
                            fg="#e03131")
        lbl.bind("<Button-1>", copy_image)
        def copy_name():
            self.root.clipboard_clear(); self.root.clipboard_append(str(path))
            note.config(text=f"📋 path copied as text   ·   {Path(path).name}", fg="#1c7ed6")
        tk.Button(win, text="📋 copy filename instead", font=("Segoe UI", 11, "bold"),
                  bg="#343a40", fg=FG, relief="flat", padx=10, pady=6,
                  command=copy_name).pack(pady=(0, 10))

    def show_versions(self):
        """Zee: the version-vs-winrate graph — after which version did WR drop/climb."""
        def work():
            import subprocess
            subprocess.run([r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe",
                            str(Path(TE.__file__).parent / "version_winrate.py")],
                           capture_output=True, timeout=60)
            self.root.after(0, self._show_versions_win)
        threading.Thread(target=work, daemon=True).start()

    def _show_versions_win(self):
        png = Path(TE.__file__).parent / "setup_labels" / "version_winrate.png"
        if not png.exists(): return
        top = tk.Toplevel(self.root)
        top.title("📊 version vs winrate")
        top.configure(bg=BG)
        from PIL import Image, ImageTk
        im = Image.open(png)
        im.thumbnail((int(self.root.winfo_screenwidth() * 0.8),
                      int(self.root.winfo_screenheight() * 0.7)))
        ph = ImageTk.PhotoImage(im)
        lbl = tk.Label(top, image=ph, bg=BG); lbl.image = ph
        lbl.pack(padx=8, pady=8)

    # ── THE STAGE BANNER (Zee 2026-08-06): where the ghost is, in large type ──
    STAGES = {
        "JUMPING":  ("🏃 JUMPING OUT OF TRADE", "#f08c00"),
        "TRADE":    ("🔥 TRADE ON", "#2f9e44"),
        "TAKING":   ("🚪 TAKING SETUP", "#1c7ed6"),
        "APPROACH": ("👀 APPROACHING SETUP", "#7048e8"),
        "HUNT":     ("👻 hunting — no setup yet", DIM),
    }
    EALOG = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Logs")
    ARMED_F = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_armed.json")
    WATCH_F = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/case_watch.json")
    FILLS_F = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/turtle_fills.csv")

    def _ea_tail(self):
        import glob, os
        try:
            f = sorted(glob.glob(str(self.EALOG / "*.log")), key=os.path.getmtime)[-1]
            try:
                txt = Path(f).read_text(encoding="utf-16", errors="ignore")
            except Exception:
                txt = Path(f).read_text(errors="ignore")
            return [l for l in txt.splitlines()[-400:] if "CaseExec" in l]
        except Exception:
            return []

    def stage_now(self):
        import re, os
        from datetime import datetime, timedelta
        lines = self._ea_tail()
        now = datetime.now()

        def line_dt(l, logday=None):
            """Zee, 2026-08-12: "isnt it saying Trade ON when no trade is ON inside
            Blueberry?" It was. This took HH:MM:SS and stamped TODAY on it, so a line
            written at 00:25 in YESTERDAY's log file read as 21 minutes old instead of
            six hours. Past midnight the whole banner became fiction. The date now
            comes from the log FILE's name (MT5 names them yyyymmdd)."""
            m = re.search(r"(\d\d:\d\d:\d\d)", l)
            if not m: return None
            t = datetime.strptime(m.group(1), "%H:%M:%S")
            base = logday or now
            return base.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)

        # which DAY does this log belong to? MT5 names them yyyymmdd.
        logday = now
        try:
            import glob as _g
            _f = sorted(_g.glob(str(self.EALOG / "*.log")), key=os.path.getmtime)[-1]
            _st = Path(_f).stem
            if len(_st) == 8 and _st.isdigit():
                logday = datetime.strptime(_st, "%Y%m%d")
        except Exception:
            pass

        last_fire = last_exit = None
        for l in lines:
            d = line_dt(l, logday)
            if d is None or d > now + timedelta(minutes=1): continue
            # ZeeUHV is the engine on the chart now and writes [ZEE] lines. The
            # banner was only watching the ghost's markers, so it could not see the
            # EA that is actually trading — and reported on one that had stopped.
            if ("GHOST-DOOR" in l or "signal #" in l or "BURST sibling" in l
                    or ("[ZEE]" in l and ("BUY" in l or "SELL" in l))):
                last_fire = d
            if "BASKET FLOOR" in l or "CLOSE ALL PROFITABLE" in l:
                last_exit = d
        # freshest exit in the last 25s -> jumping out
        if last_exit and (now - last_exit).total_seconds() <= 25:
            return "JUMPING"
        # a fire more recent than the last recorded close -> position open
        try:
            rows = [r for r in self.FILLS_F.read_text(errors="ignore").splitlines() if r.strip()]
            last_close = datetime.strptime(rows[-1].split(",")[0], "%Y.%m.%d %H:%M:%S") + timedelta(hours=2)
        except Exception:
            last_close = None
        if last_fire and (last_close is None or last_fire > last_close)                 and (now - last_fire).total_seconds() < 1800:
            return "TRADE"
        import time as _t
        if self.ARMED_F.exists() and _t.time() - os.path.getmtime(self.ARMED_F) < 120:
            return "TAKING"
        if self.WATCH_F.exists() and _t.time() - os.path.getmtime(self.WATCH_F) < 120:
            return "APPROACH"
        return "HUNT"

    def clock_line(self):
        """Zee 2026-08-06: show the MT5-vs-Karachi offset, measured live from the
        broker's own fill timestamps against this machine's clock (never hardcoded,
        so a broker DST change can't quietly lie to us)."""
        import os
        from datetime import datetime
        off = None
        try:
            rows = [r for r in self.FILLS_F.read_text(errors="ignore").splitlines() if r.strip()]
            bt = datetime.strptime(rows[-1].split(",")[0], "%Y.%m.%d %H:%M:%S")
            lt = datetime.fromtimestamp(os.path.getmtime(self.FILLS_F))
            off = round((lt - bt).total_seconds() / 3600)
        except Exception:
            pass
        now = datetime.now()
        if off is None:
            return f"local (Karachi) {now:%H:%M:%S}  ·  MT5 offset unknown"
        mt5 = now.replace() if off == 0 else None
        from datetime import timedelta
        mt5t = now - timedelta(hours=off)
        word = "behind" if off > 0 else ("ahead of" if off < 0 else "same as")
        return (f"MT5 (broker) {mt5t:%H:%M:%S}  is  {abs(off)}h {word}  local Karachi "
                f"{now:%H:%M:%S}   ·   chart times = Karachi")

    def tick_stage(self):
        try:
            self.clocks.config(text=self.clock_line())
        except Exception:
            pass
        try:
            txt, col = self.STAGES[self.stage_now()]
        except Exception:
            txt, col = "", DIM
        self.stage.config(text=txt, fg=col)
        self.root.after(3000, self.tick_stage)

    def force_regime(self):
        ROVR.write_text(json.dumps({"until": int(time.time()) + 1800, "by": "zee"}),
                        encoding="ascii")

    def _regime_text(self, bars):
        closed = bars[:-1]
        if len(closed) < 22:
            return "", ""
        seg = [b[3] for b in closed[-21:]]
        net = abs(seg[-1] - seg[0])
        tot = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
        er = net / max(tot, 1e-9)
        forced_left = 0
        try:
            forced_left = max(0, int(json.loads(ROVR.read_text()).get("until", 0)) - int(time.time()))
        except Exception:
            pass
        if forced_left > 0:
            return (f"⚡ REGIME FORCED — trading through chop, {forced_left//60}m {forced_left%60:02d}s left "
                    f"(ER {er:.2f})", "#7048e8")
        try:
            import re as _re
            src = Path(TE.__file__).parent.joinpath("oanda_live_matcher.py").read_text(encoding="utf-8")
            lifted = bool(_re.search(r"^GATES_LIFTED = True", src, _re.M))
        except Exception:
            lifted = False
        if lifted:
            tag = "chop" if er < 0.25 else "trending"
            return (f"⚖️ GATES LIFTED (trial) — trading 24/7 · tape {tag} (ER {er:.2f})", "#f08c00")
        if er < 0.25:
            return (f"⛔ REGIME HALT — tape not trending (ER {er:.2f} < 0.25) — ghost rests", "#e03131")
        return (f"✅ regime OK — tape trending (ER {er:.2f})", "#2f9e44")

    def set_call(self, name):
        CALL.write_text(json.dumps({"trend": name,
                                    "allow": {"UPTREND": ["BUY"], "DOWNTREND": ["SELL"],
                                              "RANGE": [], "AUTO": ["BUY", "SELL"]}[name],
                                    "ts": int(time.time()), "by": "zee"}), encoding="ascii")
        self.tick()

    def tick(self):
        call, age = current_call()
        left = max(0, TTL - age)
        extra = ("  (humps decide the direction)" if call == "AUTO" else
                 f"  — expires in {left // 60}m {left % 60:02d}s, then humps decide")
        self.status.config(text=f"YOUR CALL: {call}{extra}", fg=COLORS[call])
        self.root.after(1000, self.tick)


if __name__ == "__main__":
    Cockpit().root.mainloop()
