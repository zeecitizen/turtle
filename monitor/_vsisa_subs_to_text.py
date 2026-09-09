"""json3 captions -> readable timestamped transcript, one file per VSISA part.

YouTube's json3 is word-level: hundreds of fragments a minute, each with its own
offset. Read raw it is unusable. This stitches fragments back into sentences and
stamps each with the clock time the sentence STARTED, so "7:25 part 5" in
LAWS_VSISA.md lands on the right line.

    py monitor/_vsisa_subs_to_text.py
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SUBS = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\_vsisa_transcripts\_subs")
OUT = SUBS.parent

# a sentence gets cut here, whichever comes first
MAX_CHARS = 220
MAX_SEC = 12.0


def stamp(ms: float) -> str:
    s = int(ms / 1000)
    return f"{s // 60}:{s % 60:02d}"


def events(path: Path):
    """(start_ms, text) for every word fragment, in order."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        base = ev.get("tStartMs", 0)
        for s in segs:
            t = s.get("utf8", "")
            if not t or t == "\n":
                continue
            yield base + s.get("tOffsetMs", 0), t


def sentences(path: Path):
    """Glue fragments until a sentence ends or the line gets too long."""
    out, buf, start, last = [], "", None, None
    for ms, frag in events(path):
        if start is None:
            start = ms
        buf += frag
        last = ms
        clean = re.sub(r"\s+", " ", buf).strip()
        long_enough = len(clean) >= MAX_CHARS or (last - start) / 1000.0 >= MAX_SEC
        ends = clean.endswith((".", "?", "!"))
        if clean and (ends or long_enough):
            out.append((start, clean))
            buf, start = "", None
    clean = re.sub(r"\s+", " ", buf).strip()
    if clean:
        out.append((start or 0, clean))
    return out


def main():
    files = sorted(SUBS.glob("*.json3"))
    if not files:
        sys.exit("[subs] nothing in %s" % SUBS)
    index = []
    for f in files:
        m = re.match(r"(\d+)_", f.name)
        part = int(m.group(1)) if m else 0
        lines = sentences(f)
        if not lines:
            print(f"[part {part:02d}] EMPTY caption track — skipped")
            continue
        end = lines[-1][0]
        body = "\n".join(f"[{stamp(t)}] {txt}" for t, txt in lines)
        head = (f"# VSISA Part {part} — English (YouTube auto-translated captions)\n\n"
                f"Source: `{f.name}` · length ~{stamp(end)} · {len(lines)} lines\n\n"
                f"> Machine ASR of Urdu/Hindi speech, machine-translated. Trading terms\n"
                f"> are often mangled — read for MEANING, cross-check anything load-bearing\n"
                f"> against the chart being discussed.\n\n---\n\n")
        dest = OUT / f"part{part:02d}.md"
        dest.write_text(head + body + "\n", encoding="utf-8")
        index.append((part, len(lines), stamp(end), dest.name))
        print(f"[part {part:02d}] {len(lines):4d} lines  ~{stamp(end):>6}  -> {dest.name}")

    idx = ["# VSISA transcripts — index\n",
           "English auto-translated captions for the *Volume Spread Imbalance Shift",
           "Analysis* course (Sajid Ahmed, 22 parts).\n",
           "| part | lines | length | file |", "|---|---|---|---|"]
    for part, n, dur, name in sorted(index):
        idx.append(f"| {part} | {n} | {dur} | [{name}]({name}) |")
    missing = sorted({i for i in range(1, 23)} - {p for p, _, _, _ in index})
    if missing:
        idx.append("\n**Missing:** parts %s — YouTube returned HTTP 429 on the caption\n"
                   "track and the OpenAI key has no credits for local ASR.\n"
                   % ", ".join(str(m) for m in missing))
    (OUT / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"\n{len(index)} transcripts -> {OUT}")


if __name__ == "__main__":
    main()
