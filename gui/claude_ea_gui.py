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
        self._btn(bar, "🧠  LAUNCH CLAUDE SESSION", self.launch_claude, BLUE, 23)
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

        body = tk.Frame(self, bg=BG); body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
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
        tk.Label(hdr, text="TODAY'S TRADES   (double-click a row for details)", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="PDF: failed setups", command=self.make_pdf, bg="#7f1d1d", fg="#fff",
                  relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2",
                  padx=8).pack(side="right")
        self.tsum = tk.Label(hdr, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9))
        self.tsum.pack(side="right", padx=10)
        cols = ("time", "side", "verdict", "lots", "entry", "exit", "pnl", "status")
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
        for c, w in zip(cols, (66, 46, 60, 46, 74, 74, 70, 96)):
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("win", foreground=GREEN)
        self.tree.tag_configure("loss", foreground=RED)
        self.tree.tag_configure("skip", foreground=MUTED)
        self.tree.pack(fill="both", expand=True, pady=(4, 0))
        self.tree.bind("<Double-1>", self.open_detail)
        self._rows = {}

        act = tk.Frame(right, bg=PANEL, padx=10, pady=10); act.pack(fill="x", pady=(8, 0))
        tk.Label(act, text="MANUAL OVERRIDE (no Claude session)", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        row = tk.Frame(act, bg=PANEL); row.pack(fill="x", pady=6)
        self._btn(row, "TAKE 1x", lambda: self.manual("TAKE", 1.0), GREEN, 9)
        self._btn(row, "TAKE 2x", lambda: self.manual("TAKE", 2.0), "#16a34a", 9)
        self._btn(row, "SKIP", lambda: self.manual("SKIP"), RED, 9)

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
        prompt = ("Read " + rbname + " and resume the live judging loop for "
                  + self.market.get() + ".")
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
    # -- settings ---------------------------------------------------------
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

    def _refresh_conn(self):
        try:
            import settings as S
            name, colour, state = S.status_line()
            self.conn.configure(text=name + "  \u00b7  " + state, fg=colour)
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
        rows = TB.book(mk)
        s = TB.summary(rows)
        txt = "judged {} \u00b7 taken {} \u00b7 skipped {} \u00b7 net ${:+.2f}".format(
            s["judged"], s["taken"], s["skipped"], s["net"])
        if s["wr"] is not None:
            txt += " \u00b7 WR {:.0f}%".format(s["wr"])
        self.tsum.configure(text=txt)
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for r in rows:
            u = r["usd"] or 0
            tag = "win" if u > 0 else "loss" if u < 0 else "skip"
            iid = self.tree.insert("", "end", values=(
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

    def make_pdf(self):
        import trade_book as TB
        try:
            out = TB.failed_pdf(self.market.get())
            messagebox.showinfo("Turtle Desktop", "Report written:\n" + str(out))
            subprocess.Popen(["cmd", "/c", "start", "", str(out)], creationflags=NO_WIN)
        except Exception as e:
            messagebox.showerror("Turtle Desktop", "PDF failed: " + str(e))

    def refresh_loop(self):
        threading.Thread(target=self._collect, daemon=True).start()
        self._show_chart()
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
        if not use:
            return
        try:
            sig = (use, use.stat().st_mtime)
            if sig == getattr(self, "_imgsig", None):
                self.chart_title.configure(text=title); return
            self._imgsig = sig
            img = tk.PhotoImage(file=str(use))
            # Tk has no resize; subsample by an integer factor to fit the panel
            target = max(self.chart_img.winfo_width(), 700)
            factor = max(1, round(img.width() / target))
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
            rows = jf.read_text(encoding="utf-8").strip().splitlines()[-200:]
            out = []
            for r in rows:
                try:
                    d = json.loads(r)
                    if d.get("market") and d.get("market") != mk:
                        continue          # a gold panel must not show BTC verdicts
                    out.append(f"{d.get('judged_utc','')[11:16]}  {d.get('verdict',''):7} "
                               f"{d.get('side',''):4} @{d.get('entry','')}  {str(d.get('reason',''))[:60]}")
                except Exception:
                    pass
            self._set(self.journal, "\n".join(reversed(out[-9:])) or f"no {mk} verdicts yet")
        else:
            self._set(self.journal, "no verdicts yet")

        self.foot.configure(text=f"  {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC   ·   "
                                 f"repo {REPO}   ·   playbook: CLAUDE_REALTIME_EA.md")


class TradeDetail(tk.Toplevel):
    """Everything about one trade: the chart, Claude's reasoning, Zee's comment, and the two
    grading buttons - so the game is played right where the trade is reviewed."""

    def __init__(self, parent, row, market):
        super().__init__(parent)
        self.row, self.market = row, market
        self.title("{} {}  ({})".format(row["side"], row["time"], row["status"]))
        self.geometry("980x760")
        self.configure(bg=BG)

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        pnl = "${:+.2f}".format(row["usd"]) if row["usd"] is not None else "not filled"
        u = row["usd"] or 0
        col = GREEN if u > 0 else RED if u < 0 else MUTED
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
                f = max(1, round(im.width() / 900))
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
        self.saved = tk.Label(br, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.saved.pack(side="left", padx=8)

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
