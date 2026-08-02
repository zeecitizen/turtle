"""philosophy.py — the master's own words, and a way to realign with them.

Zee 2026-08-03: *"aik button Philosophy ka ho jahan master ki batai hoi kaam ki quotes likhi
hon, aur saath button ho interpret Philosophy again (realign with Master)."*

Two ideas, deliberately separate:

  QUOTES     what Zee actually said, kept verbatim. These are the sentences that changed
             the system: each one cost money to learn.
  REALIGN    re-reads the sources (the playbook's doctrine, and Zee's own 147 setup
             comments) and re-derives the list, showing what is new since last time. The
             philosophy is not a frozen copy — it is whatever the master is saying now.
"""
from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

REPO = Path(__file__).resolve().parent.parent
PLAYBOOK = REPO / "CLAUDE_REALTIME_EA.md"
LABELS = REPO / "monitor" / "setup_labels" / "zee_labels.json"
STORE = Path(__file__).resolve().parent / "philosophy.json"

BG, PANEL, FG, MUTED = "#0b0f14", "#111826", "#e6edf3", "#8b97a3"
GREEN, RED, BLUE, AMBER = "#4ade80", "#f87171", "#7dd3fc", "#fbbf24"

# The core, in Zee's words. Each carries what it cost to learn.
CORE = [
    ("Trend is everything",
     "Selling in an uptrend.",
     "His three-word diagnosis of every large loss on 2026-07-31, the day the demo went "
     "$1000 to $309. No numeric trend filter ever caught them; his eyes caught all three."),
    ("Trend is everything",
     "In a strong trend even a weak setup works.",
     "Trend quality outranks candle quality. Judge the context first, the geometry second."),
    ("Trend is everything",
     "This setup is choppy market — we don't take trades in a ranging market.",
     "The most frequent avoidable loss. When highs and lows are flat, stand aside."),
    ("The eye beats the threshold",
     "AI khud kyun ni pakadti trend?",
     "The question that ended six months of tuning. Vision replaced the trend filter the "
     "same day, and beat the rule engine by $132 on the same six real trades."),
    ("The eye beats the threshold",
     "Hum wheel dobara bana rahe hain.",
     "Said while watching another threshold sweep. He was right: no setting both blocked "
     "the killers and kept the winners."),
    ("Risk",
     "Apologies don't pay hospital bills.",
     "Nine EA versions, $0 earned. 'The next version will fix it' IS the failure mode. "
     "Only live receipts count."),
    ("Risk",
     "We ride the wave and surf into profit for 5-6 trades, then when the trend shifts we "
     "make a huge loss.",
     "Measured: one full-size loss eats 6.2 average winners. Avoiding killers beats "
     "catching winners."),
    ("Risk",
     "Greed has no measurement — 40 students, none succeeded.",
     "Every safety rule must be enforced by the machine, never by a human's promise."),
    ("Exit",
     "Master takes the exit, the computer takes the entry.",
     "The strategy is deterministic at entry and judgemental at exit. Nine versions "
     "automated the entry and never assembled the exit."),
    ("Exit",
     "Harvest, then withdraw. The market takes back what it gives.",
     "At the daily target, stop. This was learned on the day of the 94% run."),
    ("Method",
     "UHV means Ultra High Volume — it must be higher than its closest neighbours, and it "
     "must be a strong candle, so that when we mitigate it we are mitigating strong sellers.",
     "A weak-bodied 'UHV' means nobody was exhausted, and the setup has no fuel."),
    ("Method",
     "A valid retracement starts when a candle's BODY breaks the previous candle's extreme.",
     "Not a wick, not a touch. The body."),
    ("Method",
     "The breakout must have LOWER volume than the UHV.",
     "Higher volume on the breakout means the move is being fought, not accepted."),
    ("Evidence",
     "Show me the losing setups so I can comment on them.",
     "Every genuine improvement in this system came from his comments on losers. Not one "
     "came from a parameter sweep."),
    ("Evidence",
     "All backtests hallucinate.",
     "Confirmed the hard way: the simulator scored a -$690 day at +$942 and called a "
     "-$120 trade a winner. Validate on real fills only."),
]


def load_store():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"quotes": [], "realigned": None}


def save_store(d):
    STORE.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def realign():
    """Re-read the sources and re-derive the philosophy.

    Returns (quotes, note). Quotes are CORE plus anything strong found in the playbook's
    doctrine section and in Zee's own setup comments, so the list follows the master rather
    than a snapshot of him."""
    found = [{"theme": t, "quote": q, "why": w, "src": "core"} for t, q, w in CORE]
    seen = {q.lower()[:48] for _, q, _ in CORE}

    # doctrine from the playbook
    try:
        txt = PLAYBOOK.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^##\s*\d+\.\s*DOCTRINE.*?$(.*?)^##", txt,
                      re.S | re.M | re.I)
        if m:
            for line in m.group(1).splitlines():
                line = line.strip()
                mm = re.match(r"^\d+\.\s*\*\*(.+?)\*\*\s*(.*)$", line)
                if mm:
                    q = mm.group(1).strip().rstrip(".")
                    if q.lower()[:48] not in seen:
                        seen.add(q.lower()[:48])
                        found.append({"theme": "Doctrine", "quote": q,
                                      "why": mm.group(2).strip(), "src": "playbook"})
    except Exception:
        pass

    # the master's own setup comments: keep the ones that read like a rule
    try:
        d = json.loads(LABELS.read_text(encoding="utf-8"))
        rulish = re.compile(r"\b(never|always|must|should|don'?t|we don'?t|invalid because|"
                            r"valid retracement|rule)\b", re.I)
        cands = []
        for k, v in d.items():
            t = (v.get("zee") or "").strip()
            t = re.sub(r"^(10/10|0/10)\s*:?\s*", "", t)
            if 40 <= len(t) <= 240 and rulish.search(t):
                first = re.split(r"(?<=[.!?])\s", t)[0].strip()
                if 30 <= len(first) <= 200 and first.lower()[:48] not in seen:
                    seen.add(first.lower()[:48])
                    cands.append({"theme": "From his own labels", "quote": first,
                                  "why": f"written on setup {k}", "src": "labels"})
        found.extend(cands[:12])
    except Exception:
        pass

    old = load_store()
    old_set = {q["quote"].lower()[:48] for q in old.get("quotes", [])}
    new = [q for q in found if q["quote"].lower()[:48] not in old_set] if old_set else []
    save_store({"quotes": found, "realigned": datetime.now().isoformat(timespec="seconds")})
    note = (f"{len(found)} principles"
            + (f"  ·  {len(new)} new since last realign" if old_set else "  ·  first realign"))
    return found, note


class PhilosophyWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Turtle Desktop — Philosophy")
        self.geometry("980x780")
        self.configure(bg=BG)

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text="📜  Philosophy", bg=PANEL, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(head, text="  the master's words — each one cost money to learn",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=8)
        tk.Button(head, text="↻  Interpret again (realign with Master)", command=self.realign,
                  bg=AMBER, fg="#0b0f14", relief="flat", font=("Segoe UI", 9, "bold"),
                  padx=14, pady=6, cursor="hand2").pack(side="right")
        self.note = tk.Label(head, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9))
        self.note.pack(side="right", padx=12)

        wrap = tk.Frame(self, bg=BG); wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", width=920)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

        st = load_store()
        self.render(st.get("quotes") or [{"theme": t, "quote": q, "why": w, "src": "core"}
                                         for t, q, w in CORE])
        if st.get("realigned"):
            self.note.configure(text="last realigned " + st["realigned"][:16].replace("T", " "))

    def render(self, quotes):
        for w in self.inner.winfo_children():
            w.destroy()
        theme = None
        for q in quotes:
            if q["theme"] != theme:
                theme = q["theme"]
                tk.Label(self.inner, text=theme.upper(), bg=BG, fg=BLUE, anchor="w",
                         font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(14, 4), padx=4)
            card = tk.Frame(self.inner, bg=PANEL, padx=14, pady=10)
            card.pack(fill="x", pady=3, padx=4)
            tk.Label(card, text="“" + q["quote"] + "”", bg=PANEL, fg=FG,
                     font=("Georgia", 12, "italic"), wraplength=850, justify="left",
                     anchor="w").pack(fill="x")
            if q.get("why"):
                tk.Label(card, text=q["why"], bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                         wraplength=850, justify="left", anchor="w").pack(fill="x", pady=(5, 0))
            if q.get("src") and q["src"] != "core":
                tk.Label(card, text="source: " + q["src"], bg=PANEL, fg="#4b5563",
                         font=("Consolas", 8), anchor="w").pack(fill="x")

    def realign(self):
        self.note.configure(text="re-reading the sources…")
        self.update()
        quotes, note = realign()
        self.render(quotes)
        self.note.configure(text=note, fg=GREEN)


if __name__ == "__main__":
    r = tk.Tk(); r.withdraw()
    PhilosophyWindow(r)
    r.mainloop()
