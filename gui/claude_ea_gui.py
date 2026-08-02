"""claude_ea_gui.py — Turtle Desktop, the control panel (Windows desktop GUI).

Zee 2026-08-02: *"aik windows style setup.exe ho jo ye software windows pe install karay…
waha GUI pe tum loop mein setups ka wait kar rahi ho… what if ye laptop koi chura kr le
jaey?"* — and then the key correction: *"GUI k ander se VS Code ka button bana do jiss se
tumhara session launch hojaey button click pe."* He was right: the GUI does not replace
Claude, it LAUNCHES her. Install on any PC, press one button, and the judging session starts.

What this window gives you:
  • one-click START: bridge + dashboards + a Claude Code session on this repo
  • live status: TradingView CDP, data freshness, symbol, MT5 EA, tunnel
  • the live chart, refreshed automatically
  • the ARMED panel: a retracement+UHV exists, breakout not yet fired, distance to level
  • Claude's recent verdicts and the real broker fills
  • manual TAKE / SKIP buttons for when no Claude session is running

Pure standard library (tkinter) so it packages cleanly with PyInstaller.
"""
from __future__ import annotations
import json, os, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
PY = sys.executable if "python" in Path(sys.executable).name.lower() else \
    r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
PYW = PY.replace("python.exe", "pythonw.exe")
NO_WIN = 0x08000000

BG, PANEL, FG, MUTED = "#0b0f14", "#111826", "#e6edf3", "#8b97a3"
MAX_CHART_H = 300        # a chart must never crowd out the controls
GREEN, RED, BLUE, AMBER = "#4ade80", "#f87171", "#7dd3fc", "#fbbf24"


def run_bg(args, cwd=None, hidden=True):
    subprocess.Popen(args, cwd=cwd or str(REPO),
                     creationflags=NO_WIN if hidden else 0,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def proc_running(needle):
    try:
        out = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "commandline"],
                             capture_output=True, text=True, creationflags=NO_WIN).stdout
        return needle in out
    except Exception:
        return False


def open_file(path):
    """Open a file in whatever the user has set as its default application.

    `cmd /c start` was silently failing behind the CREATE_NO_WINDOW flag, and the modal
    message box ran BEFORE it, so the PDF never appeared and the path could not even be
    copied out of the dialog."""
    try:
        os.startfile(str(path))
        return True
    except Exception:
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
            return True
        except Exception:
            return False


def open_folder(path):
    """Reveal the file in File Explorer with it already selected."""
    try:
        subprocess.Popen(["explorer", "/select,", str(Path(path))])
        return True
    except Exception:
        try:
            os.startfile(str(Path(path).parent))
            return True
        except Exception:
            return False


def http_ok(url, timeout=3):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "claude-ea-gui"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Turtle Desktop — vision-driven trading")
        self.geometry("1120x760")
        self.configure(bg=BG)
        self.market = tk.StringVar(value="XAU")     # Zee trades gold — open on XAUUSD
        self.market.trace_add("write", lambda *a: self._on_market_change())
        self._build()
        self.after(500, self.refresh_loop)

    # ── layout ────────────────────────────────────────────────────────────
    def _build(self):
        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text="🐢  TURTLE DESKTOP", bg=PANEL, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(head, text="  Claude's eyes decide · the MQL5 EA executes",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        tk.Button(head, text="\u2699  Settings", command=self.open_settings, bg="#334155",
                  fg="#fff", relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=(10, 0))
        ttk.Combobox(head, textvariable=self.market, values=["XAU", "BTC"],
                     width=6, state="readonly").pack(side="right")
        tk.Label(head, text="Market ", bg=PANEL, fg=MUTED).pack(side="right")
        self.conn = tk.Label(head, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.conn.pack(side="right", padx=14)

        bar = tk.Frame(self, bg=BG, padx=12, pady=8); bar.pack(fill="x")
        self._btn(bar, "▶  START EVERYTHING", self.start_all, GREEN, 19)
        self._btn(bar, "🧠  BEGIN AI EA TRADING", self.launch_claude, BLUE, 22)
        self._btn(bar, "📸  Snap", self.snap_now, "#334155", 8)
        self._btn(bar, "⏹  Stop", self.stop_all, "#7f1d1d", 8)

        # ── recovery row (Zee: resume from exactly where it broke) ──
        rec = tk.Frame(self, bg=BG, padx=12, pady=0); rec.pack(fill="x")
        tk.Label(rec, text="RECOVER:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 6))
        self._btn(rec, "⚡  POWER OUTAGE", self.recover_power, AMBER, 17)
        self._btn(rec, "🌐  INTERNET / PC RESTART", self.recover_net, "#a78bfa", 24)
        self.recmsg = tk.Label(rec, text="", bg=BG, fg=MUTED, font=("Consolas", 9))
        self.recmsg.pack(side="left", padx=8)

        # When each market is actually awake. Zee: show the session times the easy way.
        sf = tk.Frame(self, bg=PANEL, padx=12, pady=6); sf.pack(fill="x", padx=12, pady=(8, 0))
        self.clocks = tk.Frame(sf, bg=PANEL); self.clocks.pack(fill="x")
        self.goldnote = tk.Label(sf, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.goldnote.pack(anchor="w", pady=(4, 0))
        self._clock_cells = {}

        # The loud one. Zee wanted no ambiguity about the moment the breakout is live.
        self.banner = tk.Label(self, text="", bg=BG, fg=BG, font=("Segoe UI", 15, "bold"),
                               pady=10, wraplength=1050, justify="center")
        self.banner.pack(fill="x", padx=12, pady=(8, 0))
        self.banner.pack_forget()
        self._blink = 0

        # Everything below the buttons scrolls. Zee: a tall chart used to push the controls
        # off the bottom of the window with no way to reach them.
        outer = tk.Frame(self, bg=BG); outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        hsb.pack(fill="x", side="bottom")

        body = tk.Frame(self._canvas, bg=BG)
        self._body_id = self._canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfigure(self._body_id,
                                                               width=max(e.width, 900)))
        self._canvas.bind_all("<MouseWheel>", self._wheel)

        body.configure(padx=12, pady=6)
        left = tk.Frame(body, bg=BG); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=BG, width=380); right.pack(side="right", fill="y")

        # ── the chart Claude is looking at ──
        cf = tk.Frame(left, bg=PANEL, padx=8, pady=6); cf.pack(fill="x", pady=4)
        self.chart_title = tk.Label(cf, text="LIVE CHART", bg=PANEL, fg=MUTED,
                                    font=("Segoe UI", 9, "bold"))
        self.chart_title.pack(anchor="w")
        self.chart_img = tk.Label(cf, bg="#0b0f14", text="(no chart yet — press Snap)",
                                  fg=MUTED, font=("Segoe UI", 9))
        self.chart_img.pack(fill="both", pady=(4, 0))
        self._imgref = None

        # what Claude SEES in that picture, and Zee's answer to it
        self.vision = tk.Label(cf, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                               justify="left", anchor="w", wraplength=880)
        self.vision.pack(fill="x", pady=(6, 0))
        self.vrow = tk.Frame(cf, bg=PANEL)
        self.vrow.pack(fill="x", pady=(6, 2))
        tk.Button(self.vrow, text="\u2713  Correct \u2014 take it",
                  command=lambda: self.vision_say("correct"), bg=GREEN, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=2)
        tk.Button(self.vrow, text="\u2717  Ummm.. not sure this works",
                  command=lambda: self.vision_say("unsure"), bg=AMBER, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)
        self.vmsg = tk.Label(self.vrow, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.vmsg.pack(side="left", padx=10)
        self.vrow.pack_forget()          # only shown when a fresh reading exists

        self.status = self._card(left, "SYSTEM STATUS", 7)
        self.armed = self._card(left, "ARMED — setup forming", 5)
        self.journal = self._card(right, "CLAUDE'S RECENT VERDICTS", 7, width=44)

        # ---- LIVE from the broker (EA heartbeat) ----
        lf = tk.Frame(right, bg=PANEL, padx=10, pady=8); lf.pack(fill="x", pady=4)
        tk.Label(lf, text="LIVE (from MT5)", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.livebig = tk.Label(lf, text="--", bg=PANEL, fg=FG, font=("Consolas", 20, "bold"))
        self.livebig.pack(anchor="w")
        self.livesub = tk.Label(lf, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9),
                                justify="left", anchor="w")
        self.livesub.pack(fill="x")

        # ---- TODAY'S TRADES (double-click a row for the full story) ----
        tf = tk.Frame(left, bg=PANEL, padx=10, pady=8); tf.pack(fill="both", expand=True, pady=4)
        hdr = tk.Frame(tf, bg=PANEL); hdr.pack(fill="x")
        self.thdr = tk.Label(hdr, text="TRADES   (double-click a row for details)",
                             bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.thdr.pack(side="left")
        tk.Button(hdr, text="PDF: failed setups", command=self.make_pdf, bg="#7f1d1d", fg="#fff",
                  relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=8).pack(side="right")
        tk.Button(hdr, text="\U0001F52C  ANALYZE & RESEARCH TODAY'S TRADES",
                  command=self.open_research, bg="#7dd3fc", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=10).pack(side="right", padx=6)
        drow = tk.Frame(tf, bg=PANEL); drow.pack(fill="x", pady=(4, 0))
        tk.Button(drow, text="\u2753  WHY ARE WE MISSING SETUPS?",
                  command=self.open_funnel, bg="#a78bfa", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=10, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(drow, text="\U0001F551  FIND BEST TIME WINDOW",
                  command=self.open_windows, bg="#fbbf24", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=10, pady=4).pack(side="left", padx=6)
        tk.Button(drow, text="\U0001F517  VIEW TRADE LIFECYCLE",
                  command=self.open_lifecycle, bg="#60a5fa", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=10, pady=4).pack(side="left", padx=6)
        tk.Button(drow, text="\U0001F9E0  WHAT HAVE I LEARNED?",
                  command=self.open_learning, bg="#4ade80", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=10, pady=4).pack(side="left", padx=6)
        self.learn_on = tk.IntVar(value=1)
        tk.Checkbutton(drow, text="keep learning while it runs", variable=self.learn_on,
                       bg=PANEL, fg=MUTED, selectcolor=PANEL, activebackground=PANEL,
                       font=("Segoe UI", 8)).pack(side="left", padx=10)
        self.learn_lbl = tk.Label(drow, text="", bg=PANEL, fg=GREEN,
                                  font=("Consolas", 8))
        self.learn_lbl.pack(side="left", padx=6)
        self.tsum = tk.Label(hdr, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9))
        self.tsum.pack(side="right", padx=10)
        cols = ("id", "time", "side", "verdict", "lots", "entry", "exit", "pnl", "status")
        st = ttk.Style()
        try:
            st.theme_use("clam")
            st.configure("T.Treeview", background="#0b0f14", foreground=FG,
                         fieldbackground="#0b0f14", rowheight=22, font=("Consolas", 9))
            st.configure("T.Treeview.Heading", background=PANEL, foreground=MUTED,
                         font=("Segoe UI", 8, "bold"))
        except Exception:
            pass
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=9, style="T.Treeview")
        for c, w in zip(cols, (44, 62, 44, 58, 44, 70, 70, 66, 92)):
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("win", foreground=GREEN)
        self.tree.tag_configure("loss", foreground=RED)
        self.tree.tag_configure("skip", foreground=MUTED)
        self.tree.pack(fill="both", expand=True, pady=(4, 0))
        self.tree.bind("<Double-1>", self.open_detail)
        self._rows = {}

        act = tk.Frame(right, bg=PANEL, padx=10, pady=10); act.pack(fill="x", pady=(8, 0))
        tk.Label(act, text="DECIDE THIS SETUP YOURSELF", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(act, text="Use these only when no Claude session is judging. They act on the "
                           "setup currently waiting for a verdict.",
                 bg=PANEL, fg="#5b6673", font=("Segoe UI", 8), wraplength=350,
                 justify="left", anchor="w").pack(fill="x", pady=(1, 6))
        self.mbtns = tk.Frame(act, bg=PANEL); self.mbtns.pack(fill="x")
        self._manual_buttons()

        self.foot = tk.Label(self, text="", bg=BG, fg=MUTED, font=("Consolas", 9), anchor="w")
        self.foot.pack(fill="x", padx=14, pady=(0, 8))

    def _btn(self, parent, text, cmd, colour, width):
        tk.Button(parent, text=text, command=cmd, bg=colour, fg="#0b0f14",
                  activebackground=colour, relief="flat", width=width,
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  padx=6, pady=6).pack(side="left", padx=4)

    def _card(self, parent, title, rows, width=None):
        f = tk.Frame(parent, bg=PANEL, padx=10, pady=8); f.pack(fill="both", expand=True, pady=4)
        tk.Label(f, text=title, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        t = tk.Text(f, height=rows, bg="#0b0f14", fg=FG, insertbackground=FG,
                    relief="flat", font=("Consolas", 9), wrap="none",
                    **({"width": width} if width else {}))
        t.pack(fill="both", expand=True, pady=(4, 0))
        t.configure(state="disabled")
        return t

    def _set(self, widget, text):
        widget.configure(state="normal"); widget.delete("1.0", "end")
        widget.insert("1.0", text); widget.configure(state="disabled")

    # ── actions ───────────────────────────────────────────────────────────
    def start_all(self):
        mk = self.market.get()
        data = COMMON / ("btc_m1.csv" if mk == "BTC" else "oanda_m1.csv")
        if not http_ok("http://localhost:9222/json/version"):
            ps1 = REPO / "bootstrap" / "launch_tv.ps1"
            if ps1.exists():
                run_bg(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)])
        if not proc_running("oanda_bridge.py"):
            run_bg([PY, str(MON / "oanda_bridge.py"), "--out", str(data), "--loop", "20"])
        if not proc_running("home_uptime_guard.py"):
            run_bg([PYW, str(MON / "home_uptime_guard.py")])
        if not proc_running("serve_setup_labels.py"):
            run_bg([PYW, str(MON / "serve_setup_labels.py")])
        messagebox.showinfo("Turtle Desktop", "Services starting.\n\nSet the TradingView chart to "
                            + ("COINBASE:BTCUSD" if mk == "BTC" else "OANDA:XAUUSD")
                            + " and attach the matching EA in MT5 (Algo Trading ON, demo).")

    def launch_claude(self):
        """Zee's idea: the GUI does not replace Claude - it LAUNCHES her.

        In API mode there is no session to open, so point the user at Settings instead of
        failing silently."""
        try:
            import settings as S
            if S.load().get("connection") == "api":
                messagebox.showinfo(
                    "Turtle Desktop",
                    "This app is set to API-key mode, so there is no session to launch.\n\n"
                    "The judge runs headless against your key. Switch to 'Claude Code "
                    "subscription' in Settings if you want an interactive session.")
                return
            if not S.cli_available():
                messagebox.showwarning(
                    "Turtle Desktop",
                    "Claude Code CLI is not installed.\n\n"
                    "Install it:\n    npm install -g @anthropic-ai/claude-code\n\n"
                    "Or open Settings and switch to API-key mode.")
                return
        except Exception:
            pass
        try:
            import settings as S
            rb = S.rulebook_path()
            rbname = rb.name if rb and rb.exists() else "CLAUDE_REALTIME_EA.md"
        except Exception:
            rbname = "CLAUDE_REALTIME_EA.md"
        lessons = ""
        try:
            import lessons as L
            n = L.count()
            if n:
                lessons = (" There are " + str(n) + " LESSONS FROM REAL LOSSES at the end of "
                           "it - read those first and treat them as binding.")
        except Exception:
            pass
        prompt = ("Read " + rbname + " before doing anything." + lessons
                  + " Then resume the live judging loop for " + self.market.get() + ".")
        for attempt in (
            ["cmd", "/c", "start", "", "cmd", "/k", f'cd /d "{REPO}" && claude "{prompt}"'],
            ["cmd", "/c", "start", "", "code", str(REPO)],
        ):
            try:
                subprocess.Popen(attempt, cwd=str(REPO)); return
            except Exception:
                continue
        messagebox.showerror("Turtle Desktop",
                             "Could not launch. Install the Claude Code CLI ('claude') or VS Code ('code').")

    # ── recovery: resume from exactly where it broke ──────────────────────
    def _rec(self, msg):
        self.recmsg.configure(text=msg)

    def recover_power(self):
        """Power outage: everything died. Cold-start the whole stack in order."""
        if not messagebox.askyesno("Power outage recovery",
                                   "Full cold start:\n\n"
                                   "1. kill any stale TradingView (no debug port)\n"
                                   "2. relaunch TradingView with CDP :9222\n"
                                   "3. restart the data bridge\n"
                                   "4. restart dashboards + tunnel guard\n"
                                   "5. clear any stale pending setup\n\nProceed?"):
            return
        threading.Thread(target=self._recover, args=(True,), daemon=True).start()

    def recover_net(self):
        """Internet or PC restart: re-establish only what the network broke."""
        threading.Thread(target=self._recover, args=(False,), daemon=True).start()

    def _recover(self, cold):
        mk = self.market.get()
        data = COMMON / ("btc_m1.csv" if mk == "BTC" else "oanda_m1.csv")
        steps = []
        # 1. a stale signal must never be traded after downtime
        pend = COMMON / "pending_setup.json"
        if pend.exists():
            try: pend.unlink(); steps.append("cleared stale pending setup")
            except Exception: pass
        # 2. TradingView + CDP
        if cold or not http_ok("http://localhost:9222/json/version"):
            self._rec("restarting TradingView…")
            if cold:
                subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-Process -Name 'TradingView*' -ErrorAction SilentlyContinue | Stop-Process -Force"],
                               creationflags=NO_WIN)
                time.sleep(3)
            ps1 = REPO / "bootstrap" / "launch_tv.ps1"
            if ps1.exists():
                run_bg(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)])
            for _ in range(24):                       # wait up to ~2 min for CDP
                time.sleep(5)
                if http_ok("http://localhost:9222/json/version"): break
            steps.append("CDP " + ("up" if http_ok("http://localhost:9222/json/version") else "STILL DOWN"))
        else:
            steps.append("CDP already up")
        # 3. cloudflared — the tunnel goes stale on any network change (error 1033)
        self._rec("restarting tunnel…")
        subprocess.run(["taskkill", "/f", "/im", "cloudflared.exe"],
                       capture_output=True, creationflags=NO_WIN)
        time.sleep(2)
        cf = r"C:/Program Files (x86)/cloudflared/cloudflared"
        run_bg([cf, "tunnel", "--config", r"C:/Users/zeesh/.cloudflared/config.yml", "run"])
        steps.append("cloudflared restarted")
        # 4. bridge + dashboards
        self._rec("restarting services…")
        if not proc_running("oanda_bridge.py"):
            run_bg([PY, str(MON / "oanda_bridge.py"), "--out", str(data), "--loop", "20"])
            steps.append("bridge restarted")
        if not proc_running("home_uptime_guard.py"):
            run_bg([PYW, str(MON / "home_uptime_guard.py")]); steps.append("guard restarted")
        if not proc_running("serve_setup_labels.py"):
            run_bg([PYW, str(MON / "serve_setup_labels.py")]); steps.append("setups site restarted")
        time.sleep(12)
        fresh = data.exists() and (time.time() - data.stat().st_mtime) < 120
        steps.append("data " + ("FRESH again" if fresh else "still stale — check the TV chart symbol"))
        self._rec("recovery done")
        messagebox.showinfo("Recovery complete", "\n".join("• " + s for s in steps) +
                            "\n\nStill YOUR job:\n"
                            f"• TradingView chart on {'COINBASE:BTCUSD' if mk=='BTC' else 'OANDA:XAUUSD'}\n"
                            "• MT5 open, EA attached, Algo Trading ON (demo)\n"
                            "• press LAUNCH CLAUDE SESSION to resume judging")

    def snap_now(self):
        threading.Thread(target=lambda: subprocess.run(
            [PY, str(MON / "snap.py"), self.market.get()], cwd=str(REPO),
            capture_output=True, creationflags=NO_WIN), daemon=True).start()

    def manual(self, verdict, mult=1.0):
        if not (COMMON / "pending_setup.json").exists():
            messagebox.showwarning("Turtle Desktop", "No pending setup to judge."); return
        args = [PY, str(MON / "claude_judge.py"), "approve", verdict]
        if verdict == "TAKE": args += [str(mult)]
        args += [f"manual from GUI ({verdict} {mult}x)"]
        out = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True,
                             creationflags=NO_WIN)
        messagebox.showinfo("Turtle Desktop", (out.stdout or out.stderr)[-500:])

    def stop_all(self):
        if not messagebox.askyesno("Turtle Desktop", "Stop bridge and dashboards?"): return
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object { $_.CommandLine -match 'oanda_bridge|serve_setup_labels|home_uptime_guard' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                       creationflags=NO_WIN)

    # ── refresh ───────────────────────────────────────────────────────────
    def _banner_update(self, pend, positions):
        """Three states worth shouting about, and silence otherwise."""
        if positions:
            pnl = sum(q["profit"] for q in positions)
            side = positions[0]["side"]
            if pnl >= 0:
                text = ("\u26a1  EXPERIENCING BREAKOUT TURBULENCE  \u2014  HANG ON, "
                        f"HARVESTING PROFITS   ({side}  ${pnl:+.2f})")
                bg, fg = "#14532d", "#4ade80"
            else:
                text = ("\u26a1  IN THE TRADE  \u2014  RIDING IT OUT   "
                        f"({side}  ${pnl:+.2f})")
                bg, fg = "#7c2d12", "#fbbf24"
        elif pend:
            text = ("\u26a1  BREAKOUT DETECTED  \u2014  "
                    f"{pend.get('side', '')} @ {pend.get('entry', '')}   "
                    "AWAITING CLAUDE'S VERDICT")
            bg, fg = "#78350f", "#fbbf24"
        else:
            self.banner.pack_forget()
            return
        self._blink = (self._blink + 1) % 2
        self.banner.configure(text=text, bg=bg,
                              fg=fg if self._blink else "#f8fafc")
        if not self.banner.winfo_ismapped():
            self.banner.pack(fill="x", padx=12, pady=(8, 0))

    def vision_say(self, verdict):
        """Zee answering Claude's visual reading. This is the training signal."""
        try:
            sys.path.insert(0, str(MON))
            import vision_mark as VM
            VM.feedback(verdict)
            sc = VM.score()
            self.vmsg.configure(
                text=("noted \u2014 taking it" if verdict == "correct"
                      else "noted \u2014 Claude will not act on this reading")
                     + (f"   ({sc['agreed']}/{sc['total']} agreed)" if sc else ""),
                fg=GREEN if verdict == "correct" else AMBER)
            if verdict == "correct" and (COMMON / "pending_setup.json").exists():
                self.manual("TAKE", 1.0)
        except Exception as e:
            self.vmsg.configure(text=str(e)[:70], fg=RED)

    def _manual_buttons(self):
        """Spell the sizes out. "1x" and "2x" told the user nothing about what would
        actually be sent to the broker."""
        for w in self.mbtns.winfo_children():
            w.destroy()
        try:
            import settings as S
            cfg = S.load()
            cap = cfg.get("max_lots_xau" if self.market.get() == "XAU" else "max_lots_btc", 0.10)
        except Exception:
            cap = 0.10
        one = min(0.10, cap)
        two = min(0.20, cap)
        rows = [("BUY / SELL it  —  normal size", f"{one:.2f} lot", GREEN, 1.0),
                ("BUY / SELL it  —  high conviction", f"{two:.2f} lot", "#16a34a", 2.0),
                ("Do NOT trade this setup", "no order is sent", RED, None)]
        for title, sub, colour, mult in rows:
            f = tk.Frame(self.mbtns, bg=PANEL); f.pack(fill="x", pady=2)
            cmd = ((lambda m=mult: self.manual("TAKE", m)) if mult
                   else (lambda: self.manual("SKIP")))
            tk.Button(f, text=title, command=cmd, bg=colour, fg="#0b0f14", relief="flat",
                      font=("Segoe UI", 9, "bold"), anchor="w", padx=10, pady=6,
                      cursor="hand2").pack(side="left", fill="x", expand=True)
            tk.Label(f, text=sub, bg=PANEL, fg=MUTED,
                     font=("Consolas", 8)).pack(side="left", padx=6)
        if two <= one:
            tk.Label(self.mbtns,
                     text=f"both sizes are capped at {cap:.2f} lot for this account "
                          f"(Settings → Trading)",
                     bg=PANEL, fg=AMBER, font=("Segoe UI", 8), wraplength=350,
                     justify="left", anchor="w").pack(fill="x", pady=(4, 0))

    # -- settings ---------------------------------------------------------
    def _on_market_change(self):
        try:
            self._manual_buttons()
        except Exception:
            pass

    def open_settings(self):
        """Connect to Claude (subscription or API key), and set markets, lots and paths."""
        try:
            import settings as S
            S.SettingsDialog(self, on_save=self._applied_settings)
        except Exception as e:
            messagebox.showerror("Turtle Desktop", "Settings unavailable: " + str(e))

    def _applied_settings(self, cfg):
        try:
            self.market.set(cfg.get("market", "XAU"))
        except Exception:
            pass
        self._refresh_conn()
        try:
            self._manual_buttons()
        except Exception:
            pass

    def _refresh_clocks(self):
        """Local time and what happens next, per session."""
        try:
            import sessions as SS
            rows = SS.status()
            if not self._clock_cells:
                for r in rows:
                    c = tk.Frame(self.clocks, bg=PANEL, padx=10)
                    c.pack(side="left", fill="x", expand=True)
                    name = tk.Label(c, text=r["city"], bg=PANEL, fg=FG,
                                    font=("Segoe UI", 10, "bold"))
                    name.pack(anchor="w")
                    loc = tk.Label(c, text="", bg=PANEL, fg=MUTED, font=("Consolas", 11))
                    loc.pack(anchor="w")
                    st = tk.Label(c, text="", bg=PANEL, font=("Segoe UI", 9, "bold"))
                    st.pack(anchor="w")
                    self._clock_cells[r["city"]] = (name, loc, st)
            for r in rows:
                name, loc, st = self._clock_cells[r["city"]]
                loc.configure(text=r["local_12"])
                st.configure(
                    text=("● OPEN · " + r["in"] + " left") if r["open"]
                         else (r["note"] + " " + r["in"]),
                    fg=GREEN if r["open"] else MUTED)
                name.configure(fg=GREEN if r["open"] else FG)
            note = SS.gold_note()
            self.goldnote.configure(
                text=note,
                fg=GREEN if "trading" in note else (AMBER if "quiet" in note else MUTED))
        except Exception as e:
            try:
                self.goldnote.configure(text="clocks unavailable: " + str(e)[:60], fg=RED)
            except Exception:
                pass

    def _wheel(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
            top = w.winfo_toplevel() if w else None
            if top is not None and top is not self:
                return                      # a dialog is under the pointer; leave it alone
            self._canvas.yview_scroll(int(-e.delta / 120), "units")
        except Exception:
            pass

    def _refresh_conn(self):
        try:
            import settings as S
            name, colour, state = S.status_line()
            extra = ""
            try:
                import lessons as L
                n = L.count()
                if n:
                    extra = "  \u00b7  " + str(n) + " lesson" + ("s" if n != 1 else "")
            except Exception:
                pass
            self.conn.configure(text=name + "  \u00b7  " + state + extra, fg=colour)
        except Exception:
            pass

    # -- trade book -------------------------------------------------------
    def _refresh_book(self):
        import trade_book as TB
        mk = self.market.get()
        lv = TB.live(mk)
        if lv.get("error"):
            self.livebig.configure(text="--", fg=MUTED)
            self.livesub.configure(text=lv["error"], fg=MUTED)
        else:
            self.livebig.configure(text=format(lv.get("bid", 0), ",.2f"),
                                   fg=AMBER if lv.get("stale") else FG)
            pos = lv.get("positions") or []
            sub = ("bid {:,.2f}  ask {:,.2f}  spread {:.2f}\n"
                   "balance ${:,.2f}   equity ${:,.2f}\n{}").format(
                lv.get("bid", 0), lv.get("ask", 0), lv.get("spread", 0),
                lv.get("balance", 0), lv.get("equity", 0),
                ("stale " + str(lv.get("age_sec")) + "s") if lv.get("stale") else "live")
            for q in pos:
                sub += "\nOPEN {} {} @ {:.2f}  now {:.2f}  P&L ${:+.2f}".format(
                    q["side"], q["lots"], q["entry"], q["price"], q["profit"])
            self.livesub.configure(
                text=sub,
                fg=GREEN if any(q["profit"] > 0 for q in pos) else (RED if pos else MUTED))
        try:
            pend = None
            pf = COMMON / "pending_setup.json"
            if pf.exists():
                pend = json.loads(pf.read_text(encoding="ascii"))
            self._banner_update(pend, (lv.get("positions") or []) if not lv.get("error") else [])
        except Exception:
            pass
        day, caption = TB.day_caption(mk)
        rows = TB.book(mk, day)
        s = TB.summary(rows)
        txt = "[{}]  judged {} \u00b7 taken {} \u00b7 skipped {} \u00b7 net ${:+.2f}".format(
            caption, s["judged"], s["taken"], s["skipped"], s["net"])
        if s["wr"] is not None:
            txt += " \u00b7 WR {:.0f}%".format(s["wr"])
        self.tsum.configure(text=txt)
        self.thdr.configure(text=("TODAY'S TRADES" if caption in ("today",)
                                  else "TRADES \u2014 " + caption.upper())
                                 + "   (double-click a row for details)")
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for r in rows:
            u = r["usd"] or 0
            tag = "win" if u > 0 else "loss" if u < 0 else "skip"
            iid = self.tree.insert("", "end", values=(
                ("#" + str(r["id"])) if r.get("id") else "-",
                r["time"][-5:], r["side"], r["verdict"], r["lots"], r["entry"], r["exit"],
                ("${:+.2f}".format(r["usd"]) if r["usd"] is not None else "--"),
                r["status"]), tags=(tag,))
            self._rows[iid] = r

    def open_detail(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self._rows.get(sel[0])
        if r:
            TradeDetail(self, r, self.market.get())

    def open_research(self):
        """Study the session and say what to do differently."""
        try:
            ResearchWindow(self, self.market.get())
        except Exception as e:
            messagebox.showerror("Turtle Desktop", "Research failed: " + str(e))

    def open_funnel(self):
        """Why 1-2 setups a day when Zee counts ~100 by eye: count the drop-off at each gate."""
        def build():
            import funnel as F
            return F.to_text(F.diagnose(self.market.get()))
        ReportWindow(self, "Why are we missing setups?", build,
                     "counting how many candidates die at each gate...")

    def open_windows(self):
        def build():
            import windows as W
            return W.to_text(W.analyse(self.market.get()))
        ReportWindow(self, "Best time window", build,
                     "measuring movement and money by hour...")

    def open_lifecycle(self):
        """Grade the selected trade step by step; falls back to the most recent one."""
        sel = self.tree.selection()
        row = self._rows.get(sel[0]) if sel else None
        if row is None and self._rows:
            row = list(self._rows.values())[0]
        if row is None:
            messagebox.showinfo("Turtle Desktop",
                                "No trade to walk through yet. Pick a row once there is one.")
            return
        LifecycleWindow(self, row, self.market.get())

    def open_learning(self):
        def build():
            import autolearn as AL
            AL.run_cycle(self.market.get())
            return AL.to_text(self.market.get())
        ReportWindow(self, "What have I learned?", build,
                     "scoring every signature against real fills...")

    def _learn_tick(self):
        """The loop Zee asked for: it keeps correcting itself while the app is open.

        Cheap and quiet - it only speaks when something actually changed, because a learning
        system that announces non-events is just noise."""
        try:
            if not self.learn_on.get():
                self.learn_lbl.configure(text="learning paused", fg=MUTED)
                return
            import autolearn as AL
            ch = AL.run_cycle(self.market.get())
            st = AL.status()
            bits = []
            if ch["promoted"]:
                bits.append(f"{len(ch['promoted'])} new rule(s)")
            if ch["retired"]:
                bits.append(f"{len(ch['retired'])} retired")
            self.learn_lbl.configure(
                text=(("learned: " + ", ".join(bits)) if bits else
                      f"learning · {st['active']} active · {ch['fills']} fills seen"),
                fg=GREEN if bits else MUTED)
        except Exception as e:
            self.learn_lbl.configure(text=str(e)[:40], fg=RED)

    def make_pdf(self):
        import trade_book as TB
        try:
            day, _ = TB.day_caption(self.market.get())
            out = TB.failed_pdf(self.market.get(), day)
            messagebox.showinfo("Turtle Desktop", "Report written:\n" + str(out))
            subprocess.Popen(["cmd", "/c", "start", "", str(out)], creationflags=NO_WIN)
        except Exception as e:
            messagebox.showerror("Turtle Desktop", "PDF failed: " + str(e))

    def refresh_loop(self):
        self._refresh_clocks()
        threading.Thread(target=self._collect, daemon=True).start()
        self._show_chart()
        if time.time() - getattr(self, "_last_learn", 0) > 120:
            self._last_learn = time.time()
            threading.Thread(target=self._learn_tick, daemon=True).start()
        # keep live.png fresh on its own cadence so the picture is never far behind
        if time.time() - getattr(self, "_last_snap", 0) > 45:
            self._last_snap = time.time(); self.snap_now()
        self.after(5000, self.refresh_loop)

    def _show_chart(self):
        """Show the setup Claude is judging (pending_setup.png) or the live chart."""
        pend_png = MON / "setup_labels" / "pending_setup.png"
        live_png = MON / "setup_labels" / "live.png"
        pend_json = COMMON / "pending_setup.json"
        use, title = None, "LIVE CHART"
        if pend_json.exists() and pend_png.exists():
            use = pend_png
            try:
                p = json.loads(pend_json.read_text(encoding="ascii"))
                title = f"⚠  SETUP AWAITING VERDICT — {p['side']} @ {p['entry']}"
            except Exception:
                title = "⚠  SETUP AWAITING VERDICT"
        elif live_png.exists():
            use = live_png
            age = int(time.time() - live_png.stat().st_mtime)
            title = f"LIVE CHART   ({age}s ago)"

        # Claude's own reading of the picture outranks both: it is what actually beat the
        # rule engine, and Zee needs to see the marks she is arguing from.
        try:
            sys.path.insert(0, str(MON))
            import vision_mark as VM
            rd = VM.latest()
            if rd and rd.get("age_sec", 9999) < 900 and Path(rd.get("png", "")).exists():
                use = Path(rd["png"])
                import vision_mark as _VM
                bits = [_VM.TREND_NAME.get(rd.get("trend", ""),
                                           str(rd.get("trend", "?")).upper())]
                if rd.get("side"):
                    bits.append("no side makes sense" if rd["side"] == "NONE"
                                else f"{rd['side']} makes sense")
                for k in ("ret", "uhv", "brkt"):
                    if rd.get(k):
                        bits.append(f"{k.upper()} {rd[k]}")
                if rd.get("confidence"):
                    bits.append(rd["confidence"] + " confidence")
                txt = "CLAUDE'S EYES:  " + "   \u00b7   ".join(bits)
                if rd.get("note"):
                    txt += "\n" + rd["note"]
                sc = VM.score()
                if sc:
                    txt += (f"\nyou have agreed with {sc['agreed']} of {sc['total']} "
                            f"readings ({sc['pct']:.0f}%)")
                self.vision.configure(text=txt, fg=FG)
                self.vrow.pack(fill="x", pady=(6, 2))
                title = f"LIVE CHART \u2014 CLAUDE'S VISION   ({rd['age_sec']}s ago)"
            else:
                self.vision.configure(
                    text="no fresh visual reading \u2014 ask the Claude session to look "
                         "at the chart and mark it", fg=MUTED)
                self.vrow.pack_forget()
        except Exception:
            pass

        if not use:
            return
        try:
            sig = (use, use.stat().st_mtime)
            if sig == getattr(self, "_imgsig", None):
                self.chart_title.configure(text=title); return
            self._imgsig = sig
            img = tk.PhotoImage(file=str(use))
            # Tk cannot resize, only subsample by an integer factor - so the factor has to
            # satisfy BOTH dimensions. Width alone was not enough: a CDP screenshot is ~3400px
            # wide and a few hundred tall, so a width-only fit left an image taller than the
            # window and pushed every control off-screen.
            avail_w = max(self.chart_img.winfo_width(), 640)
            avail_h = MAX_CHART_H
            factor = max(1,
                         -(-img.width() // avail_w),      # ceil division
                         -(-img.height() // avail_h))
            if factor > 1:
                img = img.subsample(factor, factor)
            self._imgref = img                      # keep a reference or Tk drops it
            self.chart_img.configure(image=img, text="")
            self.chart_title.configure(
                text=title, fg=AMBER if "AWAITING" in title else MUTED)
        except Exception as e:
            self.chart_img.configure(image="", text=f"(chart unavailable: {e})")

    def _collect(self):
        try:
            self._refresh_conn()
        except Exception:
            pass
        try:
            self._refresh_book()
        except Exception as e:
            try:
                self.tsum.configure(text="book error: " + str(e))
            except Exception:
                pass
        mk = self.market.get()
        data = COMMON / ("btc_m1.csv" if mk == "BTC" else "oanda_m1.csv")
        mark = COMMON / ("btc_m1.symbol" if mk == "BTC" else "oanda_m1.symbol")
        L = []
        cdp = http_ok("http://localhost:9222/json/version")
        L.append(f"{'OK ' if cdp else 'DOWN'}  TradingView CDP :9222")
        sym = mark.read_text(encoding="ascii").strip() if mark.exists() else "—"
        want = "BTC" if mk == "BTC" else "XAU"
        L.append(f"{'OK ' if want in sym.upper() else 'BAD'}  data symbol: {sym}")
        if data.exists():
            age = time.time() - data.stat().st_mtime
            L.append(f"{'OK ' if age < 90 else 'OLD'}  data age: {age:.0f}s")
        else:
            L.append("MISS  data file not found")
        L.append(f"{'OK ' if proc_running('oanda_bridge.py') else 'DOWN'}  bridge")
        L.append(f"{'OK ' if http_ok('http://localhost:3457/') else 'DOWN'}  dashboard :3457")
        L.append(f"{'OK ' if http_ok('http://localhost:8765/game.html') else 'DOWN'}  setups site :8765")
        pend = COMMON / "pending_setup.json"
        if pend.exists():
            try:
                p = json.loads(pend.read_text(encoding="ascii"))
                L.append(f"***  PENDING {p['side']} @ {p['entry']} — judge it")
            except Exception:
                pass
        self._set(self.status, "\n".join(L))

        try:
            sys.path.insert(0, str(MON))
            import claude_judge as J
            n = J.near(mk)
            if n.get("armed"):
                self._set(self.armed, "\n".join(
                    f"{c['side']}  breakout {c['breakout_level']}   price {c['price_now']}   "
                    f"{c['distance']} away\n   UHV {c['uhv_time']} vol {c['uhv_vol']} "
                    f"body {c['uhv_body_ratio']}  ({c['bars_since_uhv']} bars ago)"
                    for c in n["candidates"]))
            else:
                self._set(self.armed, n.get("error") or
                          f"nothing armed · price {n.get('price', '—')}")
        except Exception as e:
            self._set(self.armed, f"unavailable: {e}")

        jf = MON / "claude_judgments.jsonl"
        if jf.exists():
            import trade_book as TB
            day, caption = TB.day_caption(mk)
            rows = jf.read_text(encoding="utf-8").strip().splitlines()[-400:]
            out = []
            for r in rows:
                try:
                    d = json.loads(r)
                    if d.get("market") and d.get("market") != mk:
                        continue          # a gold panel must not show BTC verdicts
                    if not str(d.get("judged_utc", "")).startswith(day):
                        continue
                    out.append(f"{d.get('judged_utc','')[11:16]}  {d.get('verdict',''):7} "
                               f"{d.get('side',''):4} @{d.get('entry','')}  "
                               f"{str(d.get('reason',''))[:60]}")
                except Exception:
                    pass
            body = "\n".join(reversed(out[-9:]))
            if not body:
                body = ("waiting for the first verdict of the session"
                        if TB.market_open() else
                        f"nothing judged yet \u2014 {mk} market is closed")
            self._set(self.journal, f"[{caption}]\n" + body)
        else:
            self._set(self.journal, "no verdicts yet")

        self.foot.configure(text=f"  {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC   ·   "
                                 f"repo {REPO}   ·   playbook: CLAUDE_REALTIME_EA.md")


class LifecycleWindow(tk.Toplevel):
    """The trade as a chain, one row per step, each gradeable on its own.

    Grading a whole trade only says it lost. Grading each step says WHERE it lost, and that
    is the only version of the feedback that can be acted on."""

    def __init__(self, parent, row, market):
        super().__init__(parent)
        self.row, self.market = row, market
        self.title("Turtle Desktop - Trade lifecycle")
        self.geometry("1000x860")
        self.configure(bg=BG)

        import lifecycle as LC
        self.LC = LC
        try:
            sys.path.insert(0, str(MON))
            import vision_mark as VM
            vision = VM.latest() or {}
        except Exception:
            vision = {}
        desc = LC.describe(row, vision)
        marks = LC.load_marks().get(self._key(), {})

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        pnl = f"${row['usd']:+.2f}" if row.get("usd") is not None else "no fill"
        u = row.get("usd") or 0
        tk.Label(head, text=f"{row.get('side','')}  {row.get('lots','')} lot @ "
                            f"{row.get('entry','')}", bg=PANEL, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(head, text="   " + pnl, bg=PANEL,
                 fg=GREEN if u > 0 else RED if u < 0 else MUTED,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(head, text=row.get("time", ""), bg=PANEL, fg=MUTED,
                 font=("Consolas", 9)).pack(side="right")

        tk.Label(self, text="Mark each step on its own. The point is to find WHICH link "
                            "breaks, not whether the trade lost.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(8, 2))

        wrap = tk.Frame(self, bg=BG); wrap.pack(fill="both", expand=True, padx=12, pady=4)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=940)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self.notes, self.state = {}, {}
        for key, title, question in LC.STEPS:
            card = tk.Frame(inner, bg=PANEL, padx=12, pady=9)
            card.pack(fill="x", pady=4)
            top = tk.Frame(card, bg=PANEL); top.pack(fill="x")
            tk.Label(top, text=title, bg=PANEL, fg=BLUE,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            lbl = tk.Label(top, text="", bg=PANEL, font=("Segoe UI", 9, "bold"))
            lbl.pack(side="right")
            self.state[key] = lbl
            tk.Label(card, text=question, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9, "italic"), anchor="w").pack(fill="x")
            tk.Label(card, text=desc.get(key, ""), bg=PANEL, fg=FG, font=("Consolas", 9),
                     wraplength=880, justify="left", anchor="w").pack(fill="x", pady=(4, 6))
            row2 = tk.Frame(card, bg=PANEL); row2.pack(fill="x")
            tk.Button(row2, text="\u2713 Correct", command=lambda k=key: self.mark(k, "correct"),
                      bg=GREEN, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                      padx=12, pady=4, cursor="hand2").pack(side="left")
            tk.Button(row2, text="\u26a0 Needs improvement",
                      command=lambda k=key: self.mark(k, "needs_improvement"),
                      bg=AMBER, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                      padx=12, pady=4, cursor="hand2").pack(side="left", padx=6)
            e = tk.Entry(row2, bg="#0b0f14", fg=FG, insertbackground=FG, relief="flat",
                         font=("Consolas", 9))
            e.pack(side="left", fill="x", expand=True, ipady=4, padx=8)
            self.notes[key] = e
            m = marks.get(key)
            if m:
                e.insert(0, m.get("note", ""))
                self._show(key, m.get("verdict"))

        bot = tk.Frame(self, bg=BG, padx=12, pady=10); bot.pack(fill="x")
        tk.Button(bot, text="Which step breaks most often?", command=self.summary,
                  bg=BLUE, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=14, pady=6, cursor="hand2").pack(side="left")
        self.msg = tk.Label(bot, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.msg.pack(side="left", padx=12)

    def _key(self):
        return f"{self.market}:{self.row.get('key') or self.row.get('time')}"

    def _show(self, key, verdict):
        lbl = self.state.get(key)
        if not lbl:
            return
        if verdict == "correct":
            lbl.configure(text="\u2713 correct", fg=GREEN)
        elif verdict == "needs_improvement":
            lbl.configure(text="\u26a0 needs improvement", fg=AMBER)
        else:
            lbl.configure(text="")

    def mark(self, key, verdict):
        self.LC.save_mark(self._key(), key, verdict, self.notes[key].get())
        self._show(key, verdict)
        self.msg.configure(text="saved")

    def summary(self):
        ReportWindow(self, "Which step breaks most often?",
                     lambda: self.LC.summary_text(), "tallying every graded step...")


class ReportWindow(tk.Toplevel):
    """A plain reader for the diagnostic engines. Monospaced on purpose: these are tables of
    counts, and the numbers should line up."""

    def __init__(self, parent, title, build, busy="working..."):
        super().__init__(parent)
        self.build = build
        self.title("Turtle Desktop - " + title)
        self.geometry("1080x820")
        self.configure(bg=BG)

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text=title, bg=PANEL, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.sub = tk.Label(head, text=busy, bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.sub.pack(side="left", padx=12)
        tk.Button(head, text="Re-run", command=self.run, bg=BLUE, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(head, text="Copy", command=self.copy, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)

        self.txt = tk.Text(self, bg="#0b0f14", fg=FG, relief="flat", wrap="none",
                           font=("Consolas", 10), padx=14, pady=10)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True, padx=(12, 0), pady=8)
        self.after(80, self.run)

    def run(self):
        self.txt.configure(state="normal"); self.txt.delete("1.0", "end")
        self.txt.insert("end", "working...\n"); self.update()
        try:
            body = self.build()
        except Exception as e:
            body = "Could not run this: " + str(e)
        self.txt.delete("1.0", "end")
        self.txt.insert("end", body)
        self.txt.configure(state="disabled")
        self.sub.configure(text="")

    def copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.txt.get("1.0", "end"))
            self.sub.configure(text="copied", fg=GREEN)
        except Exception:
            pass


class ResearchWindow(tk.Toplevel):
    """Every finding carries its sample size, and thin samples are labelled as such rather
    than promoted into rules. Confident conclusions from small samples are what cost this
    system six months."""

    def __init__(self, parent, market):
        super().__init__(parent)
        self.market = market
        self.title("Turtle Desktop - Research")
        self.geometry("1040x820")
        self.configure(bg=BG)

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text="\U0001F52C  Research", bg=PANEL, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        self.sub = tk.Label(head, text="studying the session...", bg=PANEL, fg=MUTED,
                            font=("Segoe UI", 9))
        self.sub.pack(side="left", padx=12)
        tk.Button(head, text="Save as PDF", command=self.pdf, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(head, text="Re-run", command=self.run, bg=BLUE, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)

        self.txt = tk.Text(self, bg="#0b0f14", fg=FG, relief="flat", wrap="word",
                           font=("Consolas", 10), padx=14, pady=10)
        self.txt.pack(fill="both", expand=True, padx=12, pady=8)
        self.txt.tag_configure("h", foreground="#7dd3fc",
                               font=("Segoe UI", 12, "bold"), spacing1=10, spacing3=4)
        self.txt.tag_configure("thin", foreground=AMBER, font=("Segoe UI", 9, "italic"))
        self.txt.tag_configure("do", foreground=AMBER, font=("Segoe UI", 11, "bold"),
                               spacing1=12)
        self.txt.tag_configure("head", foreground=FG, font=("Segoe UI", 12, "bold"))

        b = tk.Frame(self, bg=BG, padx=12, pady=8); b.pack(fill="x")
        tk.Button(b, text="Open the losses to comment on", command=self.goto_losses,
                  bg="#7f1d1d", fg="#fff", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=14, pady=6, cursor="hand2").pack(side="left")
        self.msg = tk.Label(b, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.msg.pack(side="left", padx=10)
        self.rep = None
        self.after(100, self.run)

    def run(self):
        import research as RS
        self.txt.configure(state="normal"); self.txt.delete("1.0", "end")
        self.txt.insert("end", "studying...\n")
        self.update()
        try:
            self.rep = RS.analyse(self.market)
        except Exception as e:
            self.txt.delete("1.0", "end")
            self.txt.insert("end", "Could not analyse: " + str(e))
            self.txt.configure(state="disabled")
            return
        r = self.rep
        c = r["counts"]
        self.sub.configure(text=f"{r['market']}  ·  {r['day']}")
        self.txt.delete("1.0", "end")
        self.txt.insert("end", r["headline"] + "\n", "head")
        self.txt.insert("end", f"judged {c['judged']}    taken {c['taken']}    "
                               f"skipped {c['skipped']}    filled {c['filled']}    "
                               f"wins {c['wins']}    losses {c['losses']}\n")
        for s in r["sections"]:
            self.txt.insert("end", "\n" + s["title"] + "\n", "h")
            if not s.get("solid"):
                self.txt.insert("end", f"thin sample (n={s['n']}) — a hint, not a rule\n",
                                "thin")
            self.txt.insert("end", s["body"] + "\n")
        self.txt.insert("end", "\nWHAT TO DO DIFFERENTLY\n", "do")
        for i, s in enumerate(r["suggested"], 1):
            self.txt.insert("end", f"{i}. {s}\n\n")
        self.txt.configure(state="disabled")

    def pdf(self):
        import research as RS
        try:
            out = RS.to_pdf(self.rep or RS.analyse(self.market))
            opened = open_file(out)
            self.msg.configure(
                text=("opened " if opened else "saved (could not open) ") + str(out),
                fg=GREEN if opened else AMBER)
            for txt, fn in (("Show in folder", lambda: open_folder(out)),
                            ("Copy path", lambda: (self.clipboard_clear(),
                                                   self.clipboard_append(str(out))))):
                tk.Button(self.msg.master, text=txt, command=fn, bg="#334155", fg="#fff",
                          relief="flat", font=("Segoe UI", 8, "bold"), padx=10,
                          cursor="hand2").pack(side="left", padx=4)
        except Exception as e:
            self.msg.configure(text=str(e)[:90], fg=RED)

    def goto_losses(self):
        self.msg.configure(
            text="close this window, then double-click a red row and press Derive Learnings",
            fg=AMBER)


class TradeDetail(tk.Toplevel):
    """Everything about one trade: the chart, Claude's reasoning, Zee's comment, and the two
    grading buttons - so the game is played right where the trade is reviewed."""

    def __init__(self, parent, row, market):
        super().__init__(parent)
        self.row, self.market = row, market
        self.title("Trade #{}  ·  {} {}  ({})".format(
            row.get("id", "?"), row["side"], row["time"], row["status"]))
        self.geometry("980x760")
        self.configure(bg=BG)

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        pnl = "${:+.2f}".format(row["usd"]) if row["usd"] is not None else "not filled"
        u = row["usd"] or 0
        col = GREEN if u > 0 else RED if u < 0 else MUTED
        tk.Label(head, text="#{}".format(row.get("id", "?")), bg=PANEL, fg=BLUE,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=(0, 10))
        tk.Label(head, text="{}  {} lot  @ {}".format(row["side"], row["lots"], row["entry"]),
                 bg=PANEL, fg=FG, font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(head, text="   " + pnl, bg=PANEL, fg=col,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(head, text="{}  |  verdict {}  |  mult {}  |  exit {}  |  strength {}  |  "
                            "brk_body {}  |  UHV vol {}".format(
                     row["time"], row["verdict"], row["mult"], row["exit"],
                     row["strength"], row["brk_body"], row["uhv_vol"]),
                 bg=PANEL, fg=MUTED, font=("Consolas", 9)).pack(side="right")

        png = MON / "setup_labels" / ("trade_" + row["key"].replace(":", "") + ".png")
        if not png.exists():
            png = MON / "setup_labels" / "pending_setup.png"
        imgf = tk.Frame(self, bg=PANEL, padx=8, pady=6); imgf.pack(fill="x", padx=12, pady=8)
        lbl = tk.Label(imgf, bg="#0b0f14", fg=MUTED, text="(no chart saved for this trade)")
        lbl.pack()
        if png.exists():
            try:
                im = tk.PhotoImage(file=str(png))
                f = max(1, -(-im.width() // 900), -(-im.height() // 340))
                if f > 1:
                    im = im.subsample(f, f)
                self._img = im
                lbl.configure(image=im, text="")
            except Exception:
                pass

        f2 = tk.Frame(self, bg=PANEL, padx=10, pady=8); f2.pack(fill="x", padx=12, pady=4)
        tk.Label(f2, text="WHY CLAUDE TOOK / SKIPPED IT", bg=PANEL, fg="#7dd3fc",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tx = tk.Text(f2, height=4, bg="#0b0f14", fg=FG, relief="flat",
                     font=("Consolas", 9), wrap="word")
        tx.insert("1.0", row["claude_reason"] or "(none)")
        tx.configure(state="disabled")
        tx.pack(fill="x", pady=(4, 0))

        zf = tk.Frame(self, bg=PANEL, padx=10, pady=8)
        zf.pack(fill="both", expand=True, padx=12, pady=4)
        tk.Label(zf, text="ZEE - kya ghalat tha? (yahan likho, save ho jayega)", bg=PANEL,
                 fg=AMBER, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.note = tk.Text(zf, height=5, bg="#0b0f14", fg=FG, insertbackground=FG,
                            relief="flat", font=("Consolas", 10), wrap="word")
        self.note.insert("1.0", row["zee_comment"] or "")
        self.note.pack(fill="both", expand=True, pady=(4, 0))

        br = tk.Frame(self, bg=BG, padx=12, pady=10); br.pack(fill="x")
        tk.Label(br, text="Claude ka call sahi tha?", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 8))
        for txt, mark, colour in (("10/10 sahi", "10/10", GREEN), ("0/10 ghalat", "0/10", RED)):
            tk.Button(br, text=txt, command=lambda m=mark: self.grade(m), bg=colour,
                      fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                      padx=14, pady=6, cursor="hand2").pack(side="left", padx=4)
        tk.Button(br, text="Save comment", command=lambda: self.grade(None), bg="#334155",
                  fg="#fff", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6,
                  cursor="hand2").pack(side="left", padx=12)
        tk.Button(br, text="\U0001F517  View Trade Lifecycle",
                  command=lambda: LifecycleWindow(self, row, market), bg=BLUE, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=4)
        lost = (row["usd"] or 0) < 0
        tk.Button(br, text=("\U0001F393  Derive Learnings" if lost else "Derive Learnings"),
                  command=self.derive, bg=(AMBER if lost else "#334155"),
                  fg=("#0b0f14" if lost else "#fff"), relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=4)
        self.saved = tk.Label(br, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.saved.pack(side="left", padx=8)
        self.learnt = tk.Label(self, text="", bg=BG, fg=GREEN,
                               font=("Segoe UI", 11, "bold"), pady=6)
        self.learnt.pack(fill="x")

    def derive(self):
        """Zee's comment becomes a binding rule in the playbook Claude reads before judging."""
        note = self.note.get("1.0", "end").strip()
        note = __import__("re").sub(r"^(10/10|0/10)\s*:?\s*", "", note)
        if len(note) < 10:
            self.learnt.configure(
                text="Write what went wrong first \u2014 the lesson comes from your words.",
                fg=AMBER)
            self.note.focus_set()
            return
        self.learnt.configure(text="deriving\u2026", fg=MUTED)
        self.update()
        try:
            import lessons as L
            tr = dict(self.row); tr["market"] = self.market
            e = L.add(tr, note)
            self.grade(None)
            self.learnt.configure(
                text="\u2713  Claude has learnt the lesson  \u2014  \u201c" + e["rule"]
                     + "\u201d   (written into " + L.rulebook_path().name
                     + ", now " + str(L.count()) + " lessons)",
                fg=GREEN, wraplength=940, justify="left")
        except Exception as ex:
            self.learnt.configure(text="Could not save the lesson: " + str(ex), fg=RED)

    def grade(self, mark):
        import trade_book as TB
        note = self.note.get("1.0", "end").strip()
        label = (mark + ": " + note) if mark else note
        try:
            d = json.loads(TB.LABELS.read_text(encoding="utf-8")) if TB.LABELS.exists() else {}
        except Exception:
            d = {}
        d.setdefault("trade_" + self.row["key"], {})["zee"] = label
        TB.LABELS.parent.mkdir(parents=True, exist_ok=True)
        TB.LABELS.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        self.row["zee_comment"] = label
        self.saved.configure(text="saved" + ("  " + mark if mark else ""))


if __name__ == "__main__":
    App().mainloop()
