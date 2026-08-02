"""labels_explorer.py — browse and edit every setup Zee has ever labelled.

Zee 2026-08-03: *"jo maine webpage pe losers.html aur game etc kheli, woh saray setups
labelling details wahan honi chahiye… aur comments edit karne ki option ho, takay kal ko
cheezain kharab hone lagein to tumhare paas master ke original setups hon."*

zee_labels.json holds 147 hand-written judgements — the single most valuable file in the
repo, because every real improvement in this system came from those comments and none came
from a numeric sweep. Until now they were only reachable through the web pages. This makes
them browsable offline, editable, and — importantly — backed up before any edit is written.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

REPO = Path(__file__).resolve().parent.parent
SETUPS = REPO / "monitor" / "setup_labels"
LABELS = SETUPS / "zee_labels.json"
BACKUPS = SETUPS / "label_backups"
NO_WIN = 0x08000000

BG, PANEL, FG, MUTED = "#0b0f14", "#111826", "#e6edf3", "#8b97a3"
GREEN, RED, BLUE, AMBER = "#4ade80", "#f87171", "#7dd3fc", "#fbbf24"

# where each family of keys came from, so a row can say what it is
SOURCES = [
    (re.compile(r"^loss_"),   "losses.html",  "real losing trade"),
    (re.compile(r"^game_"),   "game.html",    "trend game"),
    (re.compile(r"^blind_"),  "game (blind)", "blind test"),
    (re.compile(r"^trade_"),  "Turtle Desktop", "trade review"),
    (re.compile(r"^case_"),   "setups.html",  "case study"),
    (re.compile(r"^Rule",     re.I), "rules.html", "rule stencil"),
    (re.compile(r"^\d+$"),    "setups.html",  "labelled setup"),
]


def classify(key):
    for rx, page, kind in SOURCES:
        if rx.match(key):
            return page, kind
    return "setups.html", "labelled setup"


def grade_of(text):
    t = (text or "").strip()
    if t.startswith("10/10"):
        return "10/10", GREEN
    if t.startswith("0/10"):
        return "0/10", RED
    if re.match(r"^(correct|sahi|right)\b", t, re.I):
        return "correct", GREEN
    if re.match(r"^(wrong|ghalat|incorrect)\b", t, re.I):
        return "wrong", RED
    return "", MUTED


def load_labels():
    try:
        return json.loads(LABELS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def backup():
    """Never overwrite the master's originals without keeping a copy first."""
    if not LABELS.exists():
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / f"zee_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy2(LABELS, dst)
    keep = sorted(BACKUPS.glob("zee_labels_*.json"))[:-40]   # keep the last 40
    for old in keep:
        try:
            old.unlink()
        except Exception:
            pass
    return dst


def find_chart(key):
    """The image that goes with a label, whatever page produced it."""
    cands = [f"{key}.png"]
    if key.isdigit():
        cands += [f"case_{int(key):03d}.png", f"setup_{int(key):03d}.png"]
    m = re.match(r"^(loss|game|blind|case)_(\d+)$", key)
    if m:
        cands += [f"{m.group(1)}_{int(m.group(2)):02d}.png"]
    for c in cands:
        p = SETUPS / c
        if p.exists():
            return p
    hits = sorted(SETUPS.glob(f"*{key}*.png"))
    return hits[0] if hits else None


def rows():
    out = []
    for k, v in load_labels().items():
        txt = (v.get("zee") or "").strip()
        page, kind = classify(k)
        g, _ = grade_of(txt)
        out.append({"key": k, "text": txt, "page": page, "kind": kind, "grade": g,
                    "chart": find_chart(k), "who": "zee" if v.get("zee") else
                    (", ".join(v.keys()) or "-")})
    out.sort(key=lambda r: (r["page"], r["key"]))
    return out


class LabelsExplorer(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Turtle Desktop — Labelled setups")
        self.geometry("1180x800")
        self.configure(bg=BG)
        self.all = rows()
        self.cur = None

        head = tk.Frame(self, bg=PANEL, padx=14, pady=10); head.pack(fill="x")
        tk.Label(head, text="🏷  Labelled setups", bg=PANEL, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.count = tk.Label(head, text="", bg=PANEL, fg=MUTED, font=("Consolas", 9))
        self.count.pack(side="left", padx=14)
        tk.Button(head, text="Backup now", command=self.do_backup, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(head, text="Export all…", command=self.export, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4,
                  cursor="hand2").pack(side="right", padx=4)

        fr = tk.Frame(self, bg=BG, padx=12, pady=6); fr.pack(fill="x")
        tk.Label(fr, text="Search", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 6))
        self.q = tk.Entry(fr, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                          font=("Consolas", 10))
        self.q.pack(side="left", fill="x", expand=True, ipady=5)
        self.q.bind("<KeyRelease>", lambda e: self.fill())
        self.only = tk.StringVar(value="all")
        for lbl, val in (("all", "all"), ("10/10", "10/10"), ("0/10", "0/10"),
                         ("losses", "losses.html"), ("game", "game.html")):
            tk.Radiobutton(fr, text=lbl, value=val, variable=self.only, bg=BG, fg=MUTED,
                           selectcolor=BG, activebackground=BG, font=("Segoe UI", 9),
                           command=self.fill).pack(side="left", padx=3)

        body = tk.Frame(self, bg=BG); body.pack(fill="both", expand=True, padx=12, pady=6)
        left = tk.Frame(body, bg=BG, width=430); left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = tk.Frame(body, bg=BG); right.pack(side="right", fill="both", expand=True)

        st = ttk.Style()
        try:
            st.theme_use("clam")
            st.configure("L.Treeview", background="#0b0f14", foreground=FG,
                         fieldbackground="#0b0f14", rowheight=22, font=("Consolas", 9))
            st.configure("L.Treeview.Heading", background=PANEL, foreground=MUTED,
                         font=("Segoe UI", 8, "bold"))
        except Exception:
            pass
        cols = ("key", "grade", "page")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", style="L.Treeview")
        for c, w in zip(cols, (150, 60, 190)):
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("g10", foreground=GREEN)
        self.tree.tag_configure("g0", foreground=RED)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.show)

        self.title_lbl = tk.Label(right, text="select a setup", bg=PANEL, fg=FG, anchor="w",
                                  font=("Segoe UI", 11, "bold"), padx=10, pady=6)
        self.title_lbl.pack(fill="x")
        self.img = tk.Label(right, bg="#0b0f14", fg=MUTED, text="")
        self.img.pack(fill="both", pady=4)
        tk.Label(right, text="ZEE'S COMMENT  (editable — a backup is written before every save)",
                 bg=BG, fg=AMBER, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(6, 2))
        self.note = tk.Text(right, height=8, bg=PANEL, fg=FG, insertbackground=FG,
                            relief="flat", font=("Consolas", 10), wrap="word")
        self.note.pack(fill="both", expand=True)

        b = tk.Frame(right, bg=BG, pady=8); b.pack(fill="x")
        tk.Button(b, text="Save comment", command=self.save, bg=GREEN, fg="#0b0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=18, pady=6,
                  cursor="hand2").pack(side="left")
        for txt, mark, colour in (("10/10", "10/10", GREEN), ("0/10", "0/10", RED)):
            tk.Button(b, text=txt, command=lambda m=mark: self.save(m), bg=colour, fg="#0b0f14",
                      relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6,
                      cursor="hand2").pack(side="left", padx=4)
        tk.Button(b, text="Open chart", command=self.open_chart, bg="#334155", fg="#fff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6,
                  cursor="hand2").pack(side="left", padx=12)
        self.msg = tk.Label(b, text="", bg=BG, fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.msg.pack(side="left", padx=10)

        self.fill()

    # -- list -------------------------------------------------------------
    def filtered(self):
        q = self.q.get().strip().lower()
        f = self.only.get()
        out = []
        for r in self.all:
            if f == "10/10" and r["grade"] != "10/10":
                continue
            if f == "0/10" and r["grade"] != "0/10":
                continue
            if f.endswith(".html") and r["page"] != f:
                continue
            if q and q not in r["key"].lower() and q not in r["text"].lower():
                continue
            out.append(r)
        return out

    def fill(self):
        rs = self.filtered()
        self.tree.delete(*self.tree.get_children())
        self._map = {}
        for r in rs:
            tag = "g10" if r["grade"] == "10/10" else "g0" if r["grade"] == "0/10" else ""
            iid = self.tree.insert("", "end", values=(r["key"], r["grade"] or "-", r["page"]),
                                   tags=(tag,) if tag else ())
            self._map[iid] = r
        self.count.configure(text=f"{len(rs)} of {len(self.all)} labelled setups")

    def show(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self._map.get(sel[0])
        if not r:
            return
        self.cur = r
        self.title_lbl.configure(text=f"{r['key']}   ·   {r['kind']}   ·   from {r['page']}")
        self.note.delete("1.0", "end")
        self.note.insert("1.0", r["text"])
        self.img.configure(image="", text="")
        self._im = None
        if r["chart"] and r["chart"].exists():
            try:
                im = tk.PhotoImage(file=str(r["chart"]))
                f = max(1, round(im.width() / 640))
                if f > 1:
                    im = im.subsample(f, f)
                self._im = im
                self.img.configure(image=im)
            except Exception as e:
                self.img.configure(text=f"(chart unreadable: {e})")
        else:
            self.img.configure(text="(no chart saved for this label)")
        self.msg.configure(text="")

    # -- edit -------------------------------------------------------------
    def save(self, mark=None):
        if not self.cur:
            return
        txt = self.note.get("1.0", "end").strip()
        if mark:
            txt = re.sub(r"^(10/10|0/10)\s*:?\s*", "", txt)
            txt = f"{mark}: {txt}" if txt else mark
        b = backup()
        d = load_labels()
        d.setdefault(self.cur["key"], {})["zee"] = txt
        LABELS.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        self.cur["text"] = txt
        self.cur["grade"] = grade_of(txt)[0]
        self.note.delete("1.0", "end"); self.note.insert("1.0", txt)
        self.fill()
        self.msg.configure(text="saved" + (f" · backup {b.name}" if b else ""))

    def do_backup(self):
        b = backup()
        messagebox.showinfo("Turtle Desktop",
                            f"Backed up to:\n{b}" if b else "Nothing to back up yet.")

    def export(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="zee_labels_export.json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt")])
        if not f:
            return
        if f.lower().endswith(".txt"):
            lines = []
            for r in self.all:
                lines.append(f"### {r['key']}   [{r['grade'] or '-'}]   ({r['page']})")
                lines.append(r["text"] or "(empty)")
                lines.append("")
            Path(f).write_text("\n".join(lines), encoding="utf-8")
        else:
            Path(f).write_text(json.dumps(load_labels(), indent=1, ensure_ascii=False),
                               encoding="utf-8")
        messagebox.showinfo("Turtle Desktop", f"Exported {len(self.all)} labels to:\n{f}")

    def open_chart(self):
        if self.cur and self.cur["chart"] and self.cur["chart"].exists():
            try:
                os.startfile(str(self.cur["chart"]))
            except Exception as e:
                self.msg.configure(text=str(e), fg=RED)
        else:
            self.msg.configure(text="no chart for this label", fg=MUTED)


if __name__ == "__main__":
    r = tk.Tk(); r.withdraw()
    LabelsExplorer(r)
    r.mainloop()
