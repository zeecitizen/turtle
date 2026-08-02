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
    "mt5_terminal": "",               # which installed terminal we are wired to
    "tv_port": 9222,                  # TradingView remote-debug port the bridge attaches to
    "tv_symbol_xau": "OANDA:XAUUSD",
    "tv_symbol_btc": "COINBASE:BTCUSD",
    "tv_poll_sec": 20,
    "rulebook": "",                   # the .md Claude reads before judging
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


# ── MT5 discovery ────────────────────────────────────────────────────────────────────
def find_terminals():
    """Every MetaTrader 5 data folder on this PC, with the broker(s) it is logged into.

    Zee: *"pata ni konsa konsa MT5 hota hai system mein installed"* - Exness, Blueberry and
    the rest each get their own hashed folder under %APPDATA%\\MetaQuotes\\Terminal, and the
    server names appear as sub-folders of bases\\. That is how we name them."""
    import os
    root = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal"
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.lower() in ("common",) or len(d.name) < 16:
            continue
        brokers = []
        bases = d / "bases"
        if bases.exists():
            for b in bases.iterdir():
                if b.is_dir() and b.name not in ("Custom", "Default", "Embedded"):
                    brokers.append(b.name)
        install = ""
        try:
            install = (d / "origin.txt").read_text(encoding="utf-16", errors="ignore").strip()
        except Exception:
            try:
                install = (d / "origin.txt").read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                pass
        has_ea = (d / "MQL5" / "Experts" / "CaseSignalExecutor.mq5").exists()
        out.append({"id": d.name, "path": str(d),
                    "brokers": brokers or ["(not logged in)"],
                    "install": install, "has_ea": has_ea,
                    "label": (", ".join(brokers) if brokers else "(no account)")
                             + "   [" + d.name[:8] + "]" + ("   * our EA" if has_ea else "")})
    # the one carrying our EA first
    out.sort(key=lambda x: (not x["has_ea"], x["label"]))
    return out


def test_tradingview(port):
    """Is TradingView reachable on its debug port, and what is on the chart?"""
    import json as _j, urllib.request
    try:
        pages = _j.load(urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5))
    except Exception as e:
        return False, (f"Nothing answering on port {port}.\n\n"
                       f"Start TradingView through START EVERYTHING (it needs "
                       f"--remote-debugging-port={port}); if it is already open without the "
                       f"port, close it completely first.\n\n{e}")
    tv = [p for p in pages if "tradingview" in (p.get("url", "") + p.get("title", "")).lower()]
    if not tv:
        return False, f"Port {port} answers, but no TradingView page is open there."
    return True, f"TradingView connected on {port}.\n{tv[0].get('title', '')[:90]}"


def default_rulebook():
    for c in (REPO / "CLAUDE_REALTIME_EA.md", Path(__file__).resolve().parent.parent / "CLAUDE_REALTIME_EA.md"):
        if c.exists():
            return str(c)
    return ""


def rulebook_path():
    p = (load().get("rulebook") or "").strip() or default_rulebook()
    return Path(p) if p else None


def inspect_rulebook(path):
    """Confirm the attached file really is the playbook, and summarise it."""
    p = Path(path or "")
    if not p.exists():
        return False, "No file at that path."
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return False, f"Could not read it: {e}"
    heads = [l.strip("# ").strip() for l in txt.splitlines() if l.startswith("## ")]
    kb = p.stat().st_size / 1024.0
    if len(txt) < 400:
        return False, f"{p.name} is only {kb:.1f} KB - that does not look like the playbook."
    # Generic words like "trend" appear in any trading README. The playbook is the document
    # that actually drives the loop, so require the things only it contains.
    low = txt.lower()
    need = {"the judging commands": "claude_judge.py",
            "the TAKE verdict": "take",
            "the SKIP verdict": "skip",
            "the UHV rule": "uhv",
            "a recovery section": "recover"}
    missing = [name for name, token in need.items() if token not in low]
    if missing:
        return False, (f"{p.name} does not look like the EA playbook - it is missing "
                       f"{', '.join(missing)}. Attach CLAUDE_REALTIME_EA.md (or your own "
                       f"copy of it).")
    return True, (f"{p.name}  ({kb:.0f} KB, {len(txt.splitlines())} lines, "
                  f"{len(heads)} sections)\n"
                  + " | ".join(h[:26] for h in heads[:6]) + (" ..." if len(heads) > 6 else ""))


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

        # ── rulebook ──
        rb = self._box("EA RULEBOOK  (the document that IS the EA)")
        r9 = tk.Frame(rb, bg=PANEL); r9.pack(fill="x", pady=4)
        tk.Label(r9, text="Rules file", bg=PANEL, fg=MUTED, width=16, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        self.rulebook = tk.Entry(r9, bg="#0b0f14", fg=FG, relief="flat", insertbackground=FG,
                                 font=("Consolas", 9))
        self.rulebook.insert(0, self.cfg.get("rulebook") or default_rulebook())
        self.rulebook.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(r9, text="Open", command=self.open_rulebook, bg="#334155", fg="#fff",
                  relief="flat", cursor="hand2", padx=8).pack(side="left", padx=4)
        r10 = tk.Frame(rb, bg=PANEL); r10.pack(fill="x", pady=(6, 2))
        tk.Button(r10, text="\U0001F4D6  Attach EA MD Rules File", command=self.attach_rulebook,
                  bg=AMBER, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)
        self.rbres = tk.Label(r10, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                              wraplength=470, justify="left")
        self.rbres.pack(side="left", padx=8)
        tk.Label(rb, text="      Claude reads this before judging anything: the trend rules, the "
                          "setup geometry, the sizing, and the recovery steps. Attach your own "
                          "copy if you keep it elsewhere.", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), justify="left", wraplength=650, anchor="w").pack(fill="x")

        # ── MT5 ──
        m5 = self._box("METATRADER 5")
        self.terms = find_terminals()
        r0 = tk.Frame(m5, bg=PANEL); r0.pack(fill="x", pady=4)
        tk.Label(r0, text="Terminal", bg=PANEL, fg=MUTED, width=16, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        self.term = ttk.Combobox(r0, values=[x["label"] for x in self.terms] or ["(none found)"],
                                 state="readonly", width=52)
        cur = self.cfg.get("mt5_terminal", "")
        idx = next((i for i, x in enumerate(self.terms) if x["id"] == cur), 0)
        if self.terms:
            self.term.current(idx)
        self.term.pack(side="left")
        self.term.bind("<<ComboboxSelected>>", lambda e: self._term_changed())
        self.terminfo = tk.Label(m5, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9),
                                 justify="left", anchor="w", wraplength=640)
        self.terminfo.pack(fill="x", padx=6, pady=(2, 4))
        self.common = self._path_row(m5, "Common\\Files", self.cfg["common_dir"], folder=True)
        ra = tk.Frame(m5, bg=PANEL); ra.pack(fill="x", pady=(8, 2))
        tk.Button(ra, text="📌  Drag-Attach EA to Chart",
                  command=self.open_attach, bg=AMBER, fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)
        self.atres = tk.Label(ra, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                              wraplength=430, justify="left")
        self.atres.pack(side="left", padx=8)
        tk.Label(m5, text="      Common\\Files is shared by every terminal - it is where the EA "
                          "reads signals and writes fills.", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")

        # ── TradingView bridge ──
        tv = self._box("TRADINGVIEW BRIDGE  (price and volume come from here, not MT5)")
        r1 = tk.Frame(tv, bg=PANEL); r1.pack(fill="x", pady=4)
        tk.Label(r1, text="Debug port", bg=PANEL, fg=MUTED, width=16, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        self.tvport = tk.Entry(r1, width=8, bg="#0b0f14", fg=FG, relief="flat",
                               insertbackground=FG, font=("Consolas", 10))
        self.tvport.insert(0, str(self.cfg.get("tv_port", 9222)))
        self.tvport.pack(side="left", ipady=3)
        tk.Label(r1, text="   Poll every", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(14, 4))
        self.tvpoll = tk.Entry(r1, width=6, bg="#0b0f14", fg=FG, relief="flat",
                               insertbackground=FG, font=("Consolas", 10))
        self.tvpoll.insert(0, str(self.cfg.get("tv_poll_sec", 20)))
        self.tvpoll.pack(side="left", ipady=3)
        tk.Label(r1, text="sec", bg=PANEL, fg=MUTED).pack(side="left", padx=3)
        tk.Button(r1, text="Test bridge", command=self.test_tv, bg=BLUE, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="left", padx=14)
        r2 = tk.Frame(tv, bg=PANEL); r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Chart symbols", bg=PANEL, fg=MUTED, width=16, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 4))
        tk.Label(r2, text="XAU", bg=PANEL, fg=MUTED).pack(side="left")
        self.tvx = tk.Entry(r2, width=20, bg="#0b0f14", fg=FG, relief="flat",
                            insertbackground=FG, font=("Consolas", 9))
        self.tvx.insert(0, self.cfg.get("tv_symbol_xau", "OANDA:XAUUSD"))
        self.tvx.pack(side="left", ipady=3, padx=6)
        tk.Label(r2, text="BTC", bg=PANEL, fg=MUTED).pack(side="left")
        self.tvb = tk.Entry(r2, width=22, bg="#0b0f14", fg=FG, relief="flat",
                            insertbackground=FG, font=("Consolas", 9))
        self.tvb.insert(0, self.cfg.get("tv_symbol_btc", "COINBASE:BTCUSD"))
        self.tvb.pack(side="left", ipady=3, padx=6)
        self.tvres = tk.Label(tv, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                              wraplength=640, justify="left", anchor="w")
        self.tvres.pack(fill="x", padx=6, pady=(4, 0))
        tk.Label(tv, text="      MT5 tick volume is not the volume the strategy needs; the "
                          "exchange feed is. Gold: OANDA. Bitcoin: Coinbase (OANDA's BTC "
                          "volume has no usable spikes).", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), justify="left", wraplength=650,
                 anchor="w").pack(fill="x")

        # ── paths ──
        p = self._box("PATHS")
        self.pypath = self._path_row(p, "Python", self.cfg["python"])

        # ── knowledge ──
        kb = self._box("MASTER'S KNOWLEDGE")
        rk = tk.Frame(kb, bg=PANEL); rk.pack(fill="x", pady=4)
        tk.Button(rk, text="🏷  Explore Labelled Setups", command=self.open_labels,
                  bg=BLUE, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)
        tk.Button(rk, text="📜  Philosophy", command=self.open_philosophy,
                  bg="#a78bfa", fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)
        self.kbres = tk.Label(rk, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.kbres.pack(side="left", padx=8)
        tk.Label(kb, text="      Every setup Zee ever labelled on losers.html, game.html and the "
                          "rest - browsable, searchable and editable, with a backup written "
                          "before each save. Philosophy keeps his own words, and can re-derive "
                          "them from the sources.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                 justify="left", wraplength=650, anchor="w").pack(fill="x")

        # ── share ──
        sh = self._box("GIVE IT TO SOMEONE")
        rs = tk.Frame(sh, bg=PANEL); rs.pack(fill="x", pady=4)
        tk.Button(rs, text="🐛  REPORT A BUG", command=self.report_bug,
                  bg="#f87171", fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=16, pady=7,
                  cursor="hand2").pack(side="right", padx=6)
        tk.Button(rs, text="💾  COPY SETUP TO USB TO GIVE TO FRIEND",
                  command=self.copy_to_usb, bg=GREEN, fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=16, pady=7,
                  cursor="hand2").pack(side="left", padx=6)
        self.shres = tk.Label(rs, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                              wraplength=440, justify="left")
        self.shres.pack(side="left", padx=8)
        tk.Label(sh, text="      Copies TurtleDesktop-Setup.exe and a short read-me onto a "
                          "drive you pick. Your friend runs the setup, then needs Python, "
                          "MetaTrader 5 and TradingView on their own PC - and their own "
                          "Claude subscription or API key.", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), justify="left", wraplength=650,
                 anchor="w").pack(fill="x")

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
        self._term_changed()
        ok, msg = inspect_rulebook(self.rulebook.get().strip())
        self.rbres.configure(text=msg, fg=GREEN if ok else AMBER)

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

    def open_attach(self):
        """Which EA, onto which chart - and whether it is actually running."""
        try:
            import attach_ea as AE
            AttachWindow(self, self.market.get())
            r = AE.check(self.market.get())
            self.atres.configure(
                text=("everything checks out" if r.get("ready") else
                      "something needs doing - see the window"),
                fg=GREEN if r.get("ready") else AMBER)
        except Exception as e:
            self.atres.configure(text=str(e)[:70], fg=RED)

    def report_bug(self):
        BugWindow(self, self.market.get())

    def copy_to_usb(self):
        """Put the installer somewhere a friend can run it from."""
        import shutil
        exe = REPO / "gui" / "Output" / "TurtleDesktop-Setup.exe"
        if not exe.exists():
            self.shres.configure(
                text=("TurtleDesktop-Setup.exe has not been built yet.\n"
                      "Build it by compiling gui/installer.iss in Inno Setup."), fg=RED)
            return
        dest = filedialog.askdirectory(title="Choose the USB drive (or any folder)")
        if not dest:
            return
        try:
            out = Path(dest) / "TurtleDesktop"
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(exe, out / exe.name)
            readme = REPO / "gui" / "FIRST_RUN.txt"
            if readme.exists():
                shutil.copy2(readme, out / "READ ME FIRST.txt")
            howto = [
                "TURTLE DESKTOP",
                "==============",
                "",
                "1. Double-click TurtleDesktop-Setup.exe and follow the wizard.",
                "2. Open \"Turtle Desktop\" from the Start menu.",
                "3. Read READ ME FIRST.txt - it lists what else this PC needs:",
                "     Python 3.12+",
                "     MetaTrader 5, logged into a DEMO account",
                "     TradingView Desktop",
                "     a Claude subscription, or an Anthropic API key",
                "",
                "This trades a real market. Keep it on a demo account until it has",
                "proven itself to you. It is not a promise of profit.",
            ]
            (out / "HOW TO INSTALL.txt").write_text("\n".join(howto), encoding="utf-8")
            mb = exe.stat().st_size / 1048576
            self.shres.configure(
                text=(f"Copied to {out}\n{exe.name} ({mb:.1f} MB) plus the read-me. "
                      "Hand over the whole TurtleDesktop folder."), fg=GREEN)
            try:
                subprocess.Popen(["explorer", str(out)])
            except Exception:
                pass
        except Exception as e:
            self.shres.configure(text=f"Copy failed: {e}", fg=RED)

    def open_labels(self):
        try:
            import labels_explorer as LE
            LE.LabelsExplorer(self)
            n = len(LE.rows())
            self.kbres.configure(text=f"{n} labelled setups", fg=GREEN)
        except Exception as e:
            self.kbres.configure(text=str(e)[:70], fg=RED)

    def open_philosophy(self):
        try:
            import philosophy as PH
            PH.PhilosophyWindow(self)
            self.kbres.configure(text="philosophy open", fg=GREEN)
        except Exception as e:
            self.kbres.configure(text=str(e)[:70], fg=RED)

    def attach_rulebook(self):
        f = filedialog.askopenfilename(title="Attach the EA rules document",
                                       initialdir=str(REPO),
                                       filetypes=[("Markdown", "*.md"), ("All files", "*.*")])
        if f:
            self.rulebook.delete(0, "end"); self.rulebook.insert(0, f)
        ok, msg = inspect_rulebook(self.rulebook.get().strip())
        self.rbres.configure(text=msg, fg=GREEN if ok else RED)

    def open_rulebook(self):
        p = Path(self.rulebook.get().strip())
        if not p.exists():
            self.rbres.configure(text="No file at that path.", fg=RED); return
        try:
            os.startfile(str(p))
        except Exception as e:
            self.rbres.configure(text=str(e), fg=RED)

    def _term_changed(self):
        i = self.term.current()
        if not (0 <= i < len(self.terms)):
            return
        x = self.terms[i]
        self.terminfo.configure(
            text="broker(s): " + ", ".join(x["brokers"]) + "\n" + x["path"]
                 + ("\nour EA is installed here" if x["has_ea"]
                    else "\nCaseSignalExecutor.mq5 is NOT in this terminal - copy it from mt5\\ "
                         "and press F7"),
            fg=GREEN if x["has_ea"] else AMBER)

    def test_tv(self):
        self.tvres.configure(text="testing...", fg=MUTED)
        self.update()
        try:
            port = int(self.tvport.get())
        except Exception:
            self.tvres.configure(text="Port must be a number.", fg=RED); return
        ok, msg = test_tradingview(port)
        self.tvres.configure(text=msg, fg=GREEN if ok else RED)

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
            "tv_symbol_xau": self.tvx.get().strip() or "OANDA:XAUUSD",
            "tv_symbol_btc": self.tvb.get().strip() or "COINBASE:BTCUSD",
            "rulebook": self.rulebook.get().strip(),
        })
        i = self.term.current()
        if 0 <= i < len(self.terms):
            cfg["mt5_terminal"] = self.terms[i]["id"]
        for k, ent, d in (("tv_port", self.tvport, 9222), ("tv_poll_sec", self.tvpoll, 20)):
            try:
                cfg[k] = int(ent.get())
            except Exception:
                cfg[k] = d
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


class BugWindow(tk.Toplevel):
    """A bug report Zee can act on: what happened, what was expected, and the diagnostics
    that answer the first questions anyone would ask."""

    def __init__(self, parent, market="XAU"):
        super().__init__(parent)
        self.market = market
        self.title("Turtle Desktop - Report a bug")
        self.geometry("820x680")
        self.configure(bg=BG)
        import bugreport as BR
        self.BR = BR

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text="🐛  Report a bug", bg=PANEL, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(head, text="   goes to " + BR.TO, bg=PANEL, fg=MUTED,
                 font=("Consolas", 9)).pack(side="left", padx=10)

        for title, attr, hint in (
                ("What happened?", "what",
                 "What you did, and what the software did. Exact wording of any message helps."),
                ("What did you expect instead?", "expected",
                 "One line is enough - it is often the most useful line in the report.")):
            tk.Label(self, text=title, bg=BG, fg=AMBER, font=("Segoe UI", 10, "bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 0))
            tk.Label(self, text=hint, bg=BG, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=16)
            box = tk.Text(self, height=6 if attr == "what" else 3, bg=PANEL, fg=FG,
                          insertbackground=FG, relief="flat", font=("Consolas", 10),
                          wrap="word")
            box.pack(fill="x", padx=16, pady=4)
            setattr(self, attr, box)

        self.diag = tk.IntVar(value=1)
        tk.Checkbutton(self, text="include diagnostics (build, EA heartbeat, data freshness, "
                                  "last scan) - strongly recommended",
                       variable=self.diag, bg=BG, fg=MUTED, selectcolor=BG,
                       activebackground=BG, font=("Segoe UI", 9)).pack(anchor="w", padx=14)

        b = tk.Frame(self, bg=BG, padx=16, pady=12); b.pack(fill="x")
        tk.Button(b, text="Send", command=self.send, bg=GREEN, fg="#0b0f14", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=22, pady=7,
                  cursor="hand2").pack(side="left")
        tk.Button(b, text="Preview", command=self.preview, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=7,
                  cursor="hand2").pack(side="left", padx=8)
        tk.Button(b, text="Copy to clipboard", command=self.copy, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=7,
                  cursor="hand2").pack(side="left")
        self.msg = tk.Label(self, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9),
                            wraplength=760, justify="left")
        self.msg.pack(fill="x", padx=16)

    def _fields(self):
        return (self.what.get("1.0", "end").strip(),
                self.expected.get("1.0", "end").strip())

    def send(self):
        w, e = self._fields()
        if len(w) < 5:
            self.msg.configure(text="Describe what happened first - even one sentence.",
                               fg=AMBER)
            self.what.focus_set()
            return
        self.msg.configure(text="gathering diagnostics...", fg=MUTED); self.update()
        path, opened, _ = self.BR.send(w, e, self.market, bool(self.diag.get()))
        note = ("Your mail app should be open with the report ready to send."
                if opened else
                "No mail app opened. The report is saved - attach it to an email yourself.")
        self.msg.configure(text=note + "\nSaved a copy at: " + str(path),
                           fg=GREEN if opened else AMBER)

    def preview(self):
        w, e = self._fields()
        body = self.BR.compose(w, e, self.market, bool(self.diag.get()))
        top = tk.Toplevel(self); top.title("Preview"); top.geometry("860x640")
        top.configure(bg=BG)
        tx = tk.Text(top, bg="#0b0f14", fg=FG, relief="flat", font=("Consolas", 9),
                     wrap="word", padx=12, pady=10)
        tx.pack(fill="both", expand=True)
        tx.insert("1.0", body); tx.configure(state="disabled")

    def copy(self):
        w, e = self._fields()
        try:
            self.clipboard_clear()
            self.clipboard_append(self.BR.compose(w, e, self.market, bool(self.diag.get())))
            self.msg.configure(text="copied - paste it into an email to " + self.BR.TO,
                               fg=GREEN)
        except Exception as ex:
            self.msg.configure(text=str(ex)[:90], fg=RED)
