"""lessons.py — turn a loss into a rule the next trade obeys.

Zee 2026-08-03: *"har loss ke baad ek button ho — Derive Learnings → Zeeshan ka comment →
phir likha aaye 'Claude has learnt the lesson' → aur woh rulebook mein enter ho jaye future
trades ke liye. Aur rulebook har startup pe Claude read kar ke trading start kare."*

The loop this closes: every genuine improvement in this system came from Zee commenting on
a losing chart, and every one of those comments used to live only in a JSON file that
nothing read at decision time. A lesson written here is appended to the playbook itself —
the document Claude reads before judging anything — so the next trade is bound by it.

Lessons are append-only. A rule that cost money is never quietly deleted.
"""
from __future__ import annotations
import json, re, shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_JSON = REPO / "monitor" / "lessons.json"
SECTION = "## LESSONS FROM REAL LOSSES"
HEADER = f"""
{SECTION}

Written by Zee after a real losing trade, appended automatically by Turtle Desktop. These
are binding: read them before judging, and let them override anything above that disagrees.
Append-only — a rule that cost money is never quietly deleted.
"""


def rulebook_path():
    try:
        import settings as S
        p = S.rulebook_path()
        if p and Path(p).exists():
            return Path(p)
    except Exception:
        pass
    return REPO / "CLAUDE_REALTIME_EA.md"


def load():
    try:
        return json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


def count():
    return len(load())


def _rule_from(comment, trade):
    """Distil Zee's sentence into an imperative rule.

    With an API key configured this asks Claude to compress it; without one it keeps his own
    words and states the situation they apply to. Either way his sentence is preserved
    verbatim underneath, because the paraphrase is never the authority."""
    situation = []
    if trade.get("side"):
        situation.append(f"a {trade['side']}")
    if trade.get("usd") is not None:
        situation.append(f"that lost ${abs(trade['usd']):.2f}")
    ctx = " ".join(situation) or "this setup"

    try:
        import settings as S
        cfg = S.load()
        if cfg.get("connection") == "api" and S.has_key():
            import anthropic
            c = anthropic.Anthropic(api_key=S.KEYFILE.read_text(encoding="utf-8").strip())
            m = c.messages.create(
                model=cfg.get("model", "claude-sonnet-4-5"), max_tokens=120,
                system=("You turn a trader's note about a losing trade into ONE imperative "
                        "rule for a future trade. Keep his meaning exactly. One sentence, "
                        "under 25 words, starting with a verb (Do not / Only / Wait / Require). "
                        "No preamble."),
                messages=[{"role": "user", "content":
                           f"Losing trade: {ctx}. Entry {trade.get('entry')}, "
                           f"exit {trade.get('exit')}.\nHis note: {comment}"}])
            r = m.content[0].text.strip().strip('"')
            if 10 < len(r) < 220:
                return r, "claude"
    except Exception:
        pass

    first = re.split(r"(?<=[.!?])\s", comment.strip())[0].strip()
    if not re.match(r"^(do not|don't|never|only|wait|require|avoid|skip)\b", first, re.I):
        first = f"On {ctx}: {first}"
    return first[:220], "verbatim"


def add(trade, comment):
    """Record the lesson and write it into the rulebook. Returns the stored entry."""
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("Write what went wrong first — the lesson comes from your words.")

    rule, how = _rule_from(comment, trade)
    entry = {
        "id": datetime.now(timezone.utc).strftime("L%Y%m%d%H%M%S"),
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "market": trade.get("market", ""),
        "trade": {k: trade.get(k) for k in
                  ("time", "side", "lots", "entry", "exit", "usd", "verdict")},
        "claude_reason": trade.get("claude_reason", ""),
        "zee_comment": comment,
        "rule": rule,
        "derived_by": how,
    }
    all_ = load()
    all_.append(entry)
    LESSONS_JSON.parent.mkdir(parents=True, exist_ok=True)
    LESSONS_JSON.write_text(json.dumps(all_, indent=1, ensure_ascii=False), encoding="utf-8")

    write_to_rulebook(entry)
    return entry


def write_to_rulebook(entry):
    """Append the lesson to the playbook, creating the section the first time."""
    rb = rulebook_path()
    txt = rb.read_text(encoding="utf-8", errors="replace") if rb.exists() else ""
    shutil.copy2(rb, rb.with_suffix(".md.bak")) if rb.exists() else None

    t = entry["trade"]
    pnl = f"${t['usd']:+.2f}" if t.get("usd") is not None else "no fill"
    block = (f"\n### {entry['id']}  ·  {t.get('time','')}  ·  {t.get('side','')} "
             f"{t.get('lots','')} @ {t.get('entry','')}  →  {pnl}\n\n"
             f"**RULE — {entry['rule']}**\n\n"
             f"*Zee:* \"{entry['zee_comment']}\"\n\n")
    if entry.get("claude_reason"):
        block += f"*What Claude thought at the time:* {entry['claude_reason']}\n\n"

    if SECTION in txt:
        txt = txt.rstrip() + "\n" + block
    else:
        txt = txt.rstrip() + "\n\n---\n" + HEADER + block
    rb.write_text(txt, encoding="utf-8")
    return rb


def as_prompt_block(limit=20):
    """The lessons, ready to paste into a session prompt."""
    ls = load()[-limit:]
    if not ls:
        return ""
    out = ["LESSONS FROM REAL LOSSES (binding — these override any general rule):"]
    for e in ls:
        out.append(f"  - {e['rule']}   [{e['id']}]")
    return "\n".join(out)
