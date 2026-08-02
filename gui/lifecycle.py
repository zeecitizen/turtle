"""lifecycle.py — grade a trade one step at a time.

Zee 2026-08-03: *"View Trade Lifecycle — user ko lifecycle of trade dikhai jaye, takay woh
click kar sake Correct / Needs Improvement on this step. Trend detect → Ret. → UHV →
Breakout → Scaling etc."*

Grading a whole trade tells you it lost. Grading each step tells you WHERE it lost — and
those are completely different pieces of information. A trade can die because the trend was
misread, or because the trend was right and the UHV was rubbish, or because both were right
and the size was wrong. Only the second kind of feedback can be acted on.

Marks are stored per step, so the panel can answer the question that matters:
which link in the chain breaks most often?
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
MARKS = MON / "lifecycle_marks.json"

STEPS = [
    ("trend",    "1 · TREND DETECTED",   "Was the market read correctly before anything else?"),
    ("ret",      "2 · RETRACEMENT",      "Did the pullback really begin where we said it did?"),
    ("uhv",      "3 · UHV",              "Was that the right ultra-high-volume candle?"),
    ("breakout", "4 · BREAKOUT",         "Was the entry candle a genuine momentum break?"),
    ("sizing",   "5 · SIZING / SCALING", "Was the size right for how good the setup was?"),
    ("entry",    "6 · ENTRY",            "Did we get in where we intended?"),
    ("exit",     "7 · EXIT",             "Did we leave at the right moment?"),
]


def load_marks():
    try:
        return json.loads(MARKS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_mark(trade_key, step, verdict, note=""):
    d = load_marks()
    d.setdefault(trade_key, {})[step] = {
        "verdict": verdict, "note": note.strip(),
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    MARKS.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    return d[trade_key][step]


def weakest_link():
    """Which step is marked 'needs improvement' most often, across every trade graded."""
    d = load_marks()
    tally = defaultdict(Counter)
    for _, steps in d.items():
        for step, m in steps.items():
            tally[step][m.get("verdict", "?")] += 1
    rows = []
    for key, title, _ in STEPS:
        c = tally.get(key)
        if not c:
            continue
        bad, good = c.get("needs_improvement", 0), c.get("correct", 0)
        tot = bad + good
        rows.append({"step": key, "title": title, "good": good, "bad": bad, "total": tot,
                     "bad_rate": (100.0 * bad / tot) if tot else 0.0})
    rows.sort(key=lambda r: (-r["bad_rate"], -r["total"]))
    return rows


def describe(row, vision=None):
    """What actually happened at each step, in the trade's own numbers."""
    v = vision or {}
    usd = row.get("usd")
    side = row.get("side", "?")

    def f(x, d="—"):
        return d if x in (None, "", "?") else x

    trend = v.get("trend")
    agree = None
    if trend in ("up", "down"):
        agree = (trend == "up" and side == "BUY") or (trend == "down" and side == "SELL")

    out = {
        "trend": ("Claude read " + (trend.upper() + " TREND" if trend else "no recorded trend")
                  + (f" and the trade was a {side}, "
                     + ("which agrees." if agree else "which goes AGAINST it.")
                     if agree is not None else f"; the trade was a {side}.")),
        "ret": ("Retracement start marked at " + str(f(v.get("ret")))
                + ". The rule: a counter-trend candle whose BODY breaks the previous "
                  "candle's extreme."),
        "uhv": (f"UHV volume {f(row.get('uhv_vol'))}"
                + (f", marked at {v['uhv']}" if v.get("uhv") else "")
                + ". It must be the volume peak of the retracement AND strong-bodied."),
        "breakout": (f"Breakout body ratio {f(row.get('brk_body'))}"
                     + (f", marked at {v['brkt']}" if v.get("brkt") else "")
                     + ". It must be momentum, correct colour, and on LOWER volume than "
                       "the UHV."),
        "sizing": (f"Taken at {f(row.get('mult'))}x → {f(row.get('lots'))} lot"
                   + (f" (strength was {row['strength']})" if row.get("strength") else "")
                   + "."),
        "entry": (f"{side} at {f(row.get('entry'))}"
                  + (f", verdict {row['verdict']}" if row.get("verdict") else "") + "."),
        "exit": ("Closed at " + str(f(row.get("exit")))
                 + (f" for ${usd:+.2f}." if usd is not None else
                    " — no fill recorded, so the exit cannot be judged.")
                 + " The EA trails: it arms on a small move and leaves on a small give-back."),
    }
    return out


def summary_text():
    rows = weakest_link()
    out = ["WHICH STEP BREAKS MOST OFTEN", "=" * 60, ""]
    if not rows:
        return "\n".join(out + [
            "Nothing graded yet.",
            "",
            "Open a trade, press View Trade Lifecycle, and mark each step. Grading the whole",
            "trade only says it lost; grading the steps says where it lost — and only the",
            "second can be acted on."])
    out.append(f"  {'step':<24} {'ok':>4} {'needs work':>11} {'weak%':>7}")
    for r in rows:
        out.append(f"  {r['title']:<24} {r['good']:>4} {r['bad']:>11} {r['bad_rate']:>6.0f}%")
    worst = rows[0]
    out += ["", "-" * 60]
    if worst["bad_rate"] >= 50 and worst["total"] >= 3:
        out.append(f"The weakest link is “{worst['title']}” — marked as needing work in "
                   f"{worst['bad']} of {worst['total']} trades. Fix that before anything else.")
    else:
        out.append("No single step is clearly the weakest yet. Grade a few more trades.")
    return "\n".join(out)
