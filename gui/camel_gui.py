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


class Cockpit:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🐫 Camel Cockpit — the ghost obeys")
        self.root.configure(bg=BG)
        self.photo = None

        self.stage = tk.Label(self.root, text="", font=("Segoe UI", 26, "bold"),
                              bg=BG, fg=DIM)
        self.stage.pack(pady=(10, 0))
        self.regime = tk.Label(self.root, text="", font=("Segoe UI", 20, "bold"),
                               bg=BG, fg="#e03131")
        self.regime.pack(pady=(2, 0))
        self.clocks = tk.Label(self.root, text="", font=("Segoe UI", 12), bg=BG, fg=DIM)
        self.clocks.pack(pady=(0, 2))
        self.machine = tk.Label(self.root, text="machine: …", font=("Segoe UI", 13, "bold"),
                                bg=BG, fg=DIM)
        self.machine.pack(pady=(4, 2))
        self.img = tk.Label(self.root, bg=BG)
        self.img.pack(padx=10, pady=4)

        row = tk.Frame(self.root, bg=BG); row.pack(pady=6)
        tk.Button(row, text="🔄  Regenerate humps", font=("Segoe UI", 13, "bold"),
                  bg="#343a40", fg=FG, padx=16, pady=8, relief="flat",
                  command=self.regen).pack(side="left", padx=6)
        # No AUTO button (Zee): AUTO is the resting state — every manual call fades
        # back to it after 10 minutes on its own.
        tk.Button(row, text="📊 Versions", font=("Segoe UI", 12, "bold"),
                  bg="#1c7ed6", fg="white", padx=12, pady=8, relief="flat",
                  command=self.show_versions).pack(side="left", padx=6)
        tk.Button(row, text="⚡ START REGIME (30 min)", font=("Segoe UI", 12, "bold"),
                  bg="#7048e8", fg="white", padx=12, pady=8, relief="flat",
                  command=self.force_regime).pack(side="left", padx=6)
        for name, label in [("UPTREND", "📈 UPTREND — buy lamps"),
                            ("DOWNTREND", "📉 DOWNTREND — sell lamps"),
                            ("RANGE", "📦 RANGE — ghost waits")]:
            tk.Button(row, text=label, font=("Segoe UI", 12, "bold"),
                      bg=COLORS[name], fg="white", padx=12, pady=8, relief="flat",
                      command=lambda n=name: self.set_call(n)).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="", font=("Segoe UI", 12), bg=BG, fg=FG)
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
            im.thumbnail((1250, 620))
            self.photo = ImageTk.PhotoImage(im)
        except Exception:
            self.photo = tk.PhotoImage(file=str(PNG))
        self.img.config(image=self.photo)

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
        im = Image.open(png); im.thumbnail((1250, 640))
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

        def line_dt(l):
            m = re.search(r"(\d\d:\d\d:\d\d)", l)
            if not m: return None
            t = datetime.strptime(m.group(1), "%H:%M:%S")
            return now.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)

        last_fire = last_exit = None
        for l in lines:
            d = line_dt(l)
            if d is None or d > now + timedelta(minutes=1): continue
            if "GHOST-DOOR" in l or "signal #" in l or "BURST sibling" in l:
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
