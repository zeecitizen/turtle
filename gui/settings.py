"""settings.py — Turtle Desktop settings, including how the app reaches Claude.

Zee 2026-08-03: *"agar new user ne Claude subscription ni kharidi to wo settings mein ja kar
Claude key wagaira se connect kar sakay."* So there are two supported ways to connect, and
the dialog tests whichever one is chosen before saving:

  1. Claude Code CLI  - for anyone with a Claude subscription. The LAUNCH CLAUDE SESSION
     button opens a session; Claude looks at the charts herself. No key needed.
  2. Anthropic API key - for anyone without one. The judge runs headless through the API
     (monitor/ai_setup_judge.py) and bills that key.

The key is written to monitor/.claude_api_key, which is git-ignored. Everything else lives
in gui/settings.json.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
CFG = Path(__file__).resolve().parent / "settings.json"
KEYFILE = MON / ".claude_api_key"
NO_WIN = 0x08000000

DEFAULTS = {
    "connection": "cli",              # "cli" | "api"
    "model": "claude-sonnet-4-5",
    "market": "XAU",
    "max_lots_xau": 0.10,
    "max_lots_btc": 0.30,
    "python": sys.executable,
    "common_dir": r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files",
    "auto_judge": False,              # API mode only: judge without a human in the loop
}

BG, PANEL, FG, MUTED = "#0b0f14", "#111826", "#e6edf3", "#8b97a3"
GREEN, RED, BLUE, AMBER = "#4ade80", "#f87171", "#7dd3fc", "#fbbf24"


def load():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save(cfg):
    CFG.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return cfg


def has_key():
    try:
        return len(KEYFILE.read_text(encoding="utf-8").strip()) > 20
    except Exception:
        return False


def cli_available():
    return shutil.which("claude") is not None


# ── connection tests ─────────────────────────────────────────────────────────────────
def test_cli():
    exe = shutil.which("claude")
    if not exe:
        return False, ("Claude Code CLI not found.\n\nInstall it, then reopen Settings:\n"
                       "    npm install -g @anthropic-ai/claude-code")
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True,
                           timeout=25, creationflags=NO_WIN)
        v = (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "installed"
        return True, f"Claude Code CLI found.\n{v}\n\n{exe}"
    except Exception as e:
        return False, f"CLI found at {exe} but did not respond: {e}"


def test_api(key, model):
    key = (key or "").strip()
    if len(key) < 20:
        return False, "That does not look like an API key."
    try:
        import anthropic
    except ImportError:
        return False, ("The 'anthropic' package is missing. Install it:\n"
                       "    pip install anthropic")
    try:
        c = anthropic.Anthropic(api_key=key)
        m = c.messages.create(model=model, max_tokens=8,
                              messages=[{"role": "user", "content": "reply with: ok"}])
        return True, f"Key works. {model} replied: {m.content[0].text.strip()[:40]}"
    except Exception as e:
        s = str(e)
        if "credit balance" in s.lower():
            return False, ("The key is valid but the account has no credit.\n"
                           "Add credit at console.anthropic.com -> Plans & Billing.")
        if "authentication" in s.lower() or "401" in s:
            return False, "The key was rejected (authentication error). Check you pasted it whole."
        return False, f"Could not reach the API:\n{s[:300]}"


# ── dialog ───────────────────────────────────────────────────────────────────────────
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.cfg = load()
        self.title("Turtle Desktop — Settings")
        self.geometry("720x680")
        self.configure(bg=BG)
        self.transient(parent)

        tk.Label(self, text="⚙  Settings", bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="How this app reaches Claude, and how it trades.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))

        # ── connection ──
        c = self._box("CONNECT TO CLAUDE")
        self.mode = tk.StringVar(value=self.cfg["connection"])
        for val, title, sub in (
            ("cli", "Claude Code subscription  (recommended)",
             "Claude looks at the charts herself. Press LAUNCH CLAUDE SESSION on the main "
             "window. No API key, no per-trade cost."),
            ("api", "Anthropic API key",
             "For users without a subscription. The judge runs headless and bills this key. "
             "Roughly a fraction of a cent per setup."),
        ):
            tk.Radiobutton(c, text=title, value=val, variable=self.mode, bg=PANEL, fg=FG,
                           selectcolor=PANEL, activebackground=PANEL, activeforeground=FG,
                           font=("Segoe UI", 10, "bold"), anchor="w",
                           command=self._sync).pack(fill="x", pady=(6, 0))
            tk.Label(c, text="      " + sub, bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                     wraplength=640, justify="left", anchor="w").pack(fill="x")

        kf = tk.Frame(c, bg=PANEL); kf.pack(fill="x", pady=(10, 2))
        tk.Label(kf, text="API key", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 8))
        self.key = tk.Entry(kf, show="•", bg="#0b0f14", fg=FG, insertbackground=FG,
                            relief="flat", font=("Consolas", 10))
        self.key.pack(side="left", fill="x", expand=True, ipady=5)
        if has_key():
            try:
                self.key.insert(0, KEYFILE.read_text(encoding="utf-8").strip())
            except Exception:
                pass
        self.show = tk.IntVar(value=0)
        tk.Checkbutton(kf, text="show", variable=self.show, bg=PANEL, fg=MUTED,
                       selectcolor=PANEL, activebackground=PANEL,
                       command=lambda: self.key.configure(show="" if self.show.get() else "•")
                       ).pack(side="left", padx=6)

        mf = tk.Frame(c, bg=PANEL); mf.pack(fill="x", pady=(6, 2))
        tk.Label(mf, text="Model", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 8))
        self.model = ttk.Combobox(mf, values=["claude-sonnet-4-5", "claude-opus-4-5",
                                              "claude-haiku-4-5-20251001"],
                                  state="readonly", width=28)
        self.model.set(self.cfg["model"]); self.model.pack(side="left")
        self.auto = tk.IntVar(value=1 if self.cfg.get("auto_judge") else 0)
        tk.Checkbutton(mf, text="judge automatically (no human in the loop)", variable=self.auto,
                       bg=PANEL, fg=MUTED, selectcolor=PANEL, activebackground=PANEL,
                       font=("Segoe UI", 9)).pack(side="left", padx=12)

        bf = tk.Frame(c, bg=PANEL); bf.pack(fill="x", pady=(10, 2))
        tk.Button(bf, text="Test connection", command=self.test, bg=BLUE, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)
        self.tres = tk.Label(bf, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                             wraplength=470, justify="left")
        self.tres.pack(side="left", padx=8)

        # ── trading ──
        t = self._box("TRADING")
        r1 = tk.Frame(t, bg=PANEL); r1.pack(fill="x", pady=4)
        tk.Label(r1, text="Default market", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 8))
        self.market = ttk.Combobox(r1, values=["XAU", "BTC"], state="readonly", width=8)
        self.market.set(self.cfg["market"]); self.market.pack(side="left")
        tk.Label(r1, text="   Max lots  XAU", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(16, 6))
        self.lx = tk.Entry(r1, width=7, bg="#0b0f14", fg=FG, relief="flat",
                           insertbackground=FG, font=("Consolas", 10))
        self.lx.insert(0, str(self.cfg["max_lots_xau"])); self.lx.pack(side="left", ipady=3)
        tk.Label(r1, text="  BTC", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6))
        self.lb = tk.Entry(r1, width=7, bg="#0b0f14", fg=FG, relief="flat",
                           insertbackground=FG, font=("Consolas", 10))
        self.lb.insert(0, str(self.cfg["max_lots_btc"])); self.lb.pack(side="left", ipady=3)
        tk.Label(t, text="      Lots are capped so a small account cannot be handed an order it "
                         "has no margin for.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                 anchor="w").pack(fill="x")

        # ── paths ──
        p = self._box("PATHS")
        self.pypath = self._path_row(p, "Python", self.cfg["python"])
        self.common = self._path_row(p, "MT5 Common\\Files", self.cfg["common_dir"], folder=True)

        # ── buttons ──
        b = tk.Frame(self, bg=BG); b.pack(fill="x", padx=16, pady=12)
        tk.Button(b, text="Save", command=self.save_all, bg=GREEN, fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=22, pady=7, cursor="hand2").pack(side="left")
        tk.Button(b, text="Cancel", command=self.destroy, bg="#334155", fg="#fff", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=18, pady=7,
                  cursor="hand2").pack(side="left", padx=8)
        self.msg = tk.Label(b, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.msg.pack(side="left", padx=10)
        self._sync()

    # helpers
    def _box(self, title):
        f = tk.Frame(self, bg=PANEL, padx=10, pady=8)
        f.pack(fill="x", padx=16, pady=5)
        tk.Label(f, text=title, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        return f

    def _path_row(self, parent, label, value, folder=False):
        r = tk.Frame(parent, bg=PANEL); r.pack(fill="x", pady=3)
        tk.Label(r, text=label, bg=PANEL, fg=MUTED, width=16, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        e = tk.Entry(r, bg="#0b0f14", fg=FG, relief="flat", insertbackground=FG,
                     font=("Consolas", 9))
        e.insert(0, value); e.pack(side="left", fill="x", expand=True, ipady=4)

        def browse():
            v = (filedialog.askdirectory() if folder
                 else filedialog.askopenfilename(filetypes=[("Executable", "*.exe")]))
            if v:
                e.delete(0, "end"); e.insert(0, v)
        tk.Button(r, text="…", command=browse, bg="#334155", fg="#fff", relief="flat",
                  width=3, cursor="hand2").pack(side="left", padx=4)
        return e

    def _sync(self):
        api = self.mode.get() == "api"
        for w in (self.key, self.model):
            try:
                w.configure(state="normal" if api else "disabled")
            except Exception:
                pass

    def test(self):
        self.tres.configure(text="testing…", fg=MUTED)
        self.update()
        if self.mode.get() == "cli":
            ok, msg = test_cli()
        else:
            ok, msg = test_api(self.key.get(), self.model.get())
        self.tres.configure(text=msg, fg=GREEN if ok else RED)

    def save_all(self):
        cfg = load()
        cfg.update({
            "connection": self.mode.get(),
            "model": self.model.get(),
            "market": self.market.get(),
            "python": self.pypath.get().strip(),
            "common_dir": self.common.get().strip(),
            "auto_judge": bool(self.auto.get()),
        })
        for k, ent, d in (("max_lots_xau", self.lx, 0.10), ("max_lots_btc", self.lb, 0.30)):
            try:
                cfg[k] = max(0.01, float(ent.get()))
            except Exception:
                cfg[k] = d
        save(cfg)
        if self.mode.get() == "api":
            k = self.key.get().strip()
            if k:
                KEYFILE.parent.mkdir(parents=True, exist_ok=True)
                KEYFILE.write_text(k, encoding="utf-8")
                try:
                    os.chmod(KEYFILE, 0o600)
                except Exception:
                    pass
        self.msg.configure(text="saved")
        if self.on_save:
            try:
                self.on_save(cfg)
            except Exception:
                pass
        self.after(700, self.destroy)


def status_line():
    """One-line summary for the main window."""
    cfg = load()
    if cfg["connection"] == "cli":
        return ("Claude Code subscription", GREEN if cli_available() else AMBER,
                "connected" if cli_available() else "CLI not installed — open Settings")
    return ("Anthropic API key", GREEN if has_key() else RED,
            "key saved" if has_key() else "no key — open Settings")
