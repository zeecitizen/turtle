"""vision_state.py — the lifecycle step as Claude's EYES report it, not as arithmetic derives it.

Zee 2026-08-04: *"ap setup life cycle k har step ko VISION based bana do. takay koi hard fixed
rules na hon lekin apki EYES hon bass."* Then, checking: *"ab setup lifecycle eyes based hai
na?"* — and the honest answer was only half yes. I had started reading the chart myself, but the
SETUP LIFECYCLE panel he actually looks at on Turtle Desktop was still being computed by
lifecycle_state.py: pivot scales, retracement-depth thresholds, volume-peak tests. He was
watching arithmetic and being told it was vision.

This closes that gap. Each cycle I look at the plain chart from chart_now.py and write what I
see here; the desktop panel prefers this over the computed ladder while it is fresh. The eleven
steps stay as shared vocabulary — Zee and I both know what "step 5" means — but which step we
are on, and why, is now a sentence I wrote after looking, not a threshold that fired.

Freshness matters and is deliberate. A vision note older than STALE_SEC is ignored and the
computed ladder shows through again, so if I stop looking the panel degrades to arithmetic
instead of freezing on a stale opinion and pretending I am still watching.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

VIS = Path(__file__).resolve().parent / "setup_labels" / "vision_now.json"
STALE_SEC = 210          # ~3 cycles; after this the panel stops claiming I am looking

STEPS = {
    1: "trend confirmed — waiting for a retracement",
    2: "pullback started — is it a valid retracement?",
    3: "in a valid retracement",
    4: "waiting for the UHV (highest-volume counter candle)",
    5: "UHV formed — level locked",
    6: "candle approaching the level",
    7: "crossing the level (candle still open)",
    8: "closed beyond — checking momentum + volume",
    9: "breakout confirmed — awaiting the verdict",
    10: "opening the trade",
    11: "monitoring the open trade",
}


def see(step, side, seeing, waiting_for="", trend=None, market="XAU"):
    """Record what I see. `seeing` is my sentence, not a computed string."""
    VIS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"market": market, "n": int(step), "name": STEPS.get(int(step), ""),
           "side": side, "trend": trend, "seeing": seeing.strip(),
           "waiting_for": waiting_for.strip(),
           "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "claude-eyes"}
    VIS.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def read(market="XAU"):
    """The current vision note, or None if absent, stale, or for another market."""
    try:
        rec = json.loads(VIS.read_text(encoding="utf-8"))
    except Exception:
        return None
    if rec.get("market") != market:
        return None
    try:
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(rec["when"])).total_seconds()
    except Exception:
        return None
    if age > STALE_SEC:
        return None
    rec["age_sec"] = round(age)
    return rec


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        print(read() or "  no fresh vision note — the panel is showing computed arithmetic")
    else:
        print(f"  {VIS}\n  usage: from vision_state import see; see(step, side, 'what I see')")
