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

        self.regime = tk.Label(self.root, text="", font=("Segoe UI", 20, "bold"),
                               bg=BG, fg="#e03131")
        self.regime.pack(pady=(10, 0))
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
