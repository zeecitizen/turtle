"""turtle_nsnd_gui.py — Turtle NS/ND, a desktop dedicated to Zee's No Supply / No Demand method.

Zee 2026-08-04: *"jaan write a copy of turtle desktop and call it turtle ns nd"* — after handing
me the eight steps and the four failure modes in his own words, the same hour I built the
detector from his lesson-06 and lesson-07 transcripts.

It is a copy in what it does, not in its source. Duplicating 1,500 lines of Turtle Desktop would
have meant every future fix needing to be made twice and, in practice, being made once. This is
built around the one thing that window cannot show him: the NS/ND sequence as a sequence — which
of his eight steps the market has satisfied right now, and when a candidate dies, WHICH of his
four failure modes killed it.

That last part is the reason the window exists. In the lesson he spends as long on why a no-supply
FAILS as on why it works, and his four reasons are testable one at a time:

    "if low is swept but high is not broken
     if there's no FVG tap
     if there is no big volume in the background (sell ka bara volume ni tha)
     if low is broken (not just swept), before breaking its high"

So when the panel says nothing is here, it says why — "no supply found, low swept, high never
broken" — instead of going quiet. A silent window teaches him nothing; a window that names the
missing condition trains the eye, which is what he says the whole method is for: *"jab aap ki
aankhein train ho jaati hain to phir aap ko ek intuition ban jaati hai."*

Run:  python gui/turtle_nsnd_gui.py
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "monitor"))

# the palette and the process helpers are Turtle Desktop's — one look, one set of behaviours
from claude_ea_gui import (BG, PANEL, FG, MUTED, GREEN, RED, BLUE, AMBER,   # noqa: E402
                           MAX_CHART_H, PY, run_bg)
import nsnd_detector as NS                                                  # noqa: E402
from claude_judge import load_bars, MARKETS                                 # noqa: E402
import trade_book as TB                                                     # noqa: E402

# Turtle Desktop writes now.png; this window needs its own file or the two would
# fight over one image at different sizes every refresh cycle.
NSND_PNG = REPO / "monitor" / "setup_labels" / "now_nsnd.png"

# His eight steps, in his numbering, so the window and the man are speaking the same language.
STEPS = [
    "price retraces toward an FVG (point of interest)",
    "big counter-volume candle found — the UHV / climactic bar",
    "trigger lines drawn at that candle's high and low",
    "a no-supply candle appears AT those lines (tiny, dead volume)",
    "its volume is lower than each of the previous two",
    "its low is SWEPT by a wick — never closed through",
    "its high is BROKEN by a body, on higher volume",
    "entry at that close · stop under the no-supply low · target the prior peak",
]

FAILURES = [
    "low swept but high never broken",
    "no FVG tap behind the retracement",
    "no big background volume (koi bara sell volume nahi tha)",
    "low BROKEN, not just swept, before the high went",
]


class NsndApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Turtle NS/ND — No Supply / No Demand")
        self.geometry("1180x820")
        self.configure(bg=BG)
        self.market = tk.StringVar(value="XAU")
        self._imgref = None
        self._build()
        self._last_size = (0, 0)
        self.bind("<Configure>", self._on_resize)
        self.after(400, self.refresh)

    def _on_resize(self, ev):
        """Redraw at the new size — but only after the drag stops, not on every pixel."""
        if ev.widget is not self:
            return
        size = (ev.width, ev.height)
        if size == self._last_size:
            return
        self._last_size = size
        if getattr(self, "_resize_job", None):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(250, lambda: self._draw_chart(
            self.market.get(), load_bars(MARKETS[self.market.get()]["data"])))

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        head = tk.Frame(self, bg=PANEL, padx=14, pady=10)
        head.pack(fill="x")
        col = tk.Frame(head, bg=PANEL); col.pack(side="left")
        tk.Label(col, text="🕯  TURTLE NS/ND", bg=PANEL, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.big = tk.Label(col, text="STEP  --/8", bg=PANEL, fg=MUTED,
                            font=("Consolas", 22, "bold"))
        self.big.pack(anchor="w")
        self.sub = tk.Label(col, text="", bg=PANEL, fg=MUTED,
                            font=("Segoe UI", 11), justify="left")
        self.sub.pack(anchor="w")
        tk.Label(head, text="  Zee's own method — lessons 06 & 07",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        ttk.Combobox(head, textvariable=self.market, values=["XAU", "BTC"],
                     width=6, state="readonly").pack(side="right")
        tk.Label(head, text="Market ", bg=PANEL, fg=MUTED).pack(side="right")
        self.acct = tk.Label(head, text="", bg=PANEL, fg=MUTED, font=("Consolas", 10))
        self.acct.pack(side="right", padx=14)

        body = tk.Frame(self, bg=BG, padx=12, pady=8)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=BG); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=BG, width=430)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        # the chart, plain — the same discipline as chart_now.py: no markers to think for me
        cf = tk.Frame(left, bg=PANEL, padx=8, pady=6)
        cf.pack(fill="both", expand=True)
        self.chart_title = tk.Label(cf, text="LIVE CHART", bg=PANEL, fg=MUTED,
                                    font=("Segoe UI", 9, "bold"))
        self.chart_title.pack(anchor="w")
        self.chart = tk.Label(cf, bg="#0b0f14", text="(loading…)", fg=MUTED)
        # expand=True is what lets the label claim the whole panel; the render
        # then sizes itself to whatever that turns out to be.
        self.chart.pack(fill="both", expand=True, pady=(4, 0))

        self._steps_panel(right)
        self._signal_panel(right)
        self._fail_panel(right)

        bar = tk.Frame(self, bg=BG, padx=12, pady=8); bar.pack(fill="x")
        for txt, cmd, col_, w in (("🔄  Refresh now", self.refresh, "#334155", 15),
                                  ("📜  Today's sequences", self.show_history, BLUE, 20),
                                  ("🧠  Open Claude session", self.launch_claude, GREEN, 22)):
            tk.Button(bar, text=txt, command=cmd, bg=col_, fg="#fff", relief="flat",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=5, width=w,
                      cursor="hand2").pack(side="left", padx=(0, 8))
        self.msg = tk.Label(bar, text="", bg=BG, fg=MUTED, font=("Consolas", 9))
        self.msg.pack(side="left", padx=8)

    def _steps_panel(self, parent):
        f = tk.Frame(parent, bg=PANEL, padx=12, pady=8)
        f.pack(fill="x", pady=(0, 8))
        tk.Label(f, text="THE EIGHT STEPS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.step_rows = []
        for n, text in enumerate(STEPS, 1):
            row = tk.Frame(f, bg=PANEL); row.pack(fill="x", pady=1)
            mark = tk.Label(row, text="·", bg=PANEL, fg=MUTED, font=("Consolas", 11, "bold"),
                            width=2)
            mark.pack(side="left")
            lab = tk.Label(row, text=f"{n}. {text}", bg=PANEL, fg=MUTED,
                           font=("Segoe UI", 9), justify="left", wraplength=360, anchor="w")
            lab.pack(side="left", fill="x")
            self.step_rows.append((mark, lab))

    def _signal_panel(self, parent):
        f = tk.Frame(parent, bg=PANEL, padx=12, pady=8)
        f.pack(fill="x", pady=(0, 8))
        tk.Label(f, text="CURRENT SEQUENCE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.sig = tk.Label(f, text="watching like a hawk", bg=PANEL, fg=MUTED,
                            font=("Consolas", 10), justify="left", anchor="w")
        self.sig.pack(anchor="w", pady=(4, 0))

    def _fail_panel(self, parent):
        f = tk.Frame(parent, bg=PANEL, padx=12, pady=8)
        f.pack(fill="x")
        tk.Label(f, text="WHY IT FAILS  (Zee's four)", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.fail_rows = []
        for text in FAILURES:
            lab = tk.Label(f, text=f"·  {text}", bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                           wraplength=380, justify="left", anchor="w")
            lab.pack(anchor="w", pady=1)
            self.fail_rows.append(lab)

    # ── the read ────────────────────────────────────────────────────────────
    def _diagnose(self, bars):
        """How far the sequence got, and which of his four conditions is missing.

        Deliberately a walk through his steps in his order rather than a single boolean: the
        point of the window is to show WHERE it stopped, not merely that it did.
        """
        if len(bars) < 20:
            return 0, "not enough bars yet", None
        sig = NS.detect_any(bars)
        if sig:
            return 8, "", sig

        # nothing complete — find the furthest a candidate got, and name the wall it hit
        best_step, best_why = 0, "no retracement with a climactic bar yet"
        i = len(bars) - 1
        for side in ("BUY", "SELL"):
            for ns_i in range(i - 1, max(0, i - NS.SWEEP_WINDOW) - 1, -1):
                ns = bars[ns_i]
                if side == "BUY" and not ns.is_bear:
                    continue
                if side == "SELL" and not ns.is_bull:
                    continue
                if not NS._is_dead_volume(bars, ns_i):
                    continue
                step, why = 5, "a dead-volume candle is here, but not small enough in spread"
                if not NS._is_small_candle(bars, ns_i):
                    if step > best_step:
                        best_step, best_why = step, why
                    continue
                uhv = NS._find_uhv(bars, ns_i, side)
                if uhv is None:
                    step, why = 5, FAILURES[2]
                    if step > best_step:
                        best_step, best_why = step, why
                    continue
                u = bars[uhv]
                if ns.l > u.h + NS.NS_NEAR_UHV_TOL * u.rng or \
                   ns.h < u.l - NS.NS_NEAR_UHV_TOL * u.rng:
                    step, why = 4, "the quiet candle is too far from the trigger lines"
                    if step > best_step:
                        best_step, best_why = step, why
                    continue
                if not NS._fvg_tapped(bars, ns_i, side):
                    step, why = 5, FAILURES[1]
                    if step > best_step:
                        best_step, best_why = step, why
                    continue
                swept = broken = False
                for k in range(ns_i + 1, i + 1):
                    b = bars[k]
                    if side == "BUY":
                        if min(b.o, b.c) < ns.l:
                            broken = True; break
                        if b.l < ns.l:
                            swept = True
                    else:
                        if max(b.o, b.c) > ns.h:
                            broken = True; break
                        if b.h > ns.h:
                            swept = True
                if broken:
                    step, why = 6, FAILURES[3]
                elif not swept:
                    step, why = 5, "waiting for the low to be swept by a wick"
                else:
                    step, why = 7, FAILURES[0]
                if step > best_step:
                    best_step, best_why = step, why
        return best_step, best_why, None

    def refresh(self):
        try:
            mkt = self.market.get()
            bars = load_bars(MARKETS[mkt]["data"])
            step, why, sig = self._diagnose(bars)

            self.big.configure(text=f"STEP  {step}/8" if step else "STEP  --/8",
                               fg=GREEN if sig else (AMBER if step >= 5 else MUTED))
            self.sub.configure(text=(STEPS[step - 1] if step else "watching like a hawk"))

            for n, (mark, lab) in enumerate(self.step_rows, 1):
                done = n <= step
                mark.configure(text="✓" if done else "·", fg=GREEN if done else MUTED)
                lab.configure(fg=FG if done else MUTED)

            if sig:
                rr = sig.reward_pts / sig.risk_pts if sig.risk_pts else 0
                kind = "NO SUPPLY" if sig.side == "BUY" else "NO DEMAND"
                self.sig.configure(
                    text=(f"{kind} · {sig.side}\n"
                          f"entry {sig.entry:>9.2f}\n"
                          f"stop  {sig.sl:>9.2f}   risk {sig.risk_pts:.2f} pt\n"
                          f"target{sig.tp:>9.2f}   R:R  {rr:.2f}\n"
                          f"ns vol {sig.ns_vol:.0f}  ·  uhv vol {sig.uhv_vol:.0f}  ·  "
                          f"brk vol {sig.brk_vol:.0f}"),
                    fg=GREEN if sig.side == "BUY" else RED)
            else:
                self.sig.configure(text=f"watching like a hawk\n\nfurthest: {why}", fg=MUTED)

            for lab, text in zip(self.fail_rows, FAILURES):
                hit = (not sig) and why == text
                lab.configure(fg=RED if hit else MUTED,
                              text=("▸  " if hit else "·  ") + text)

            self._draw_chart(mkt, bars)
            lv = TB.live(mkt)
            if not lv.get("error"):
                self.acct.configure(
                    text=f"balance ${lv.get('balance', 0):,.2f}   equity ${lv.get('equity', 0):,.2f}")
        except Exception as e:
            self.msg.configure(text=f"refresh: {e}")
        self.after(20_000, self.refresh)

    def _draw_chart(self, mkt, bars):
        """Render the chart AT the size of the space it has, rather than shrinking to fit it.

        Zee 2026-08-04: *"can you make the live chart occupy as much width as is available."*
        Subsampling could only ever make the picture smaller in whole steps, so the panel kept
        most of its area empty. Measuring the widget and building the figure to match fills it
        exactly — and because the render is native, the candles get sharper as the window grows
        instead of blurrier.
        """
        try:
            import chart_now
            self.update_idletasks()                  # sizes are 1x1 until the layout settles
            w = max(self.chart.winfo_width(), 700)
            h = max(self.chart.winfo_height(), 420)
            png, _ = chart_now.render(mkt, 55, out=NSND_PNG, width_px=w, height_px=h)
            img = tk.PhotoImage(file=str(png))
            self._imgref = img                       # Tk drops un-referenced images
            self.chart.configure(image=img, text="")
            self.chart_title.configure(
                text=f"LIVE CHART · {mkt} M1 · {bars[0].t:%H:%M}Z–{bars[-1].t:%H:%M}Z · "
                     f"last {bars[-1].c:.2f}   ({w}×{h})")
        except Exception as e:
            self.chart.configure(image="", text=f"(chart unavailable: {e})")

    # ── actions ─────────────────────────────────────────────────────────────
    def show_history(self):
        try:
            bars = load_bars(MARKETS[self.market.get()]["data"])
            sigs = NS.scan_history(bars)
        except Exception as e:
            self.msg.configure(text=f"history: {e}"); return
        w = tk.Toplevel(self); w.title("NS/ND sequences in this session"); w.configure(bg=BG)
        w.geometry("760x420")
        tk.Label(w, text=f"{len(sigs)} completed sequences", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=8)
        box = tk.Text(w, bg=PANEL, fg=FG, font=("Consolas", 9), relief="flat", padx=10, pady=8)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        if not sigs:
            box.insert("end", "  none yet — the pattern is meant to be rare.\n"
                              "  Four gates have to agree before it counts.")
        for s in sigs:
            rr = s.reward_pts / s.risk_pts if s.risk_pts else 0
            box.insert("end", f"  {s.t}  {'NS' if s.side=='BUY' else 'ND'} {s.side:<4} "
                              f"entry {s.entry:9.2f}  stop {s.sl:9.2f}  target {s.tp:9.2f}  "
                              f"risk {s.risk_pts:4.2f}pt  R:R {rr:4.2f}\n")
        box.configure(state="disabled")

    def launch_claude(self):
        run_bg(["cmd", "/c", "start", "", "code", str(REPO)], hidden=False)
        self.msg.configure(text="VS Code opening — start a Claude session there")


if __name__ == "__main__":
    NsndApp().mainloop()
