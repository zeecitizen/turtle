"""Transcribe the 15 local VSISA videos (Sajid Ahmed, "Volume Spread Imbalance
Shift Analysis") into timestamped ENGLISH.

The teaching is in Urdu/Hindi. Zee's LAWS_VSISA.md cites moments as "7:25 part 5",
so the transcript is useless without timestamps that line up with the video clock.
whisper-1's TRANSLATION endpoint returns English plus per-segment start times, which
is exactly that.

    py monitor/_vsisa_transcribe.py            # all parts, skips finished ones
    py monitor/_vsisa_transcribe.py 5 6 7      # only these parts

Writes monitor/_vsisa_transcripts/partNN.md   ([m:ss] one line per segment).
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from openai import OpenAI  # noqa: E402

ROOT = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
VIDEOS = Path(r"C:\Users\zeesh\Downloads\VSISA")
OUT = ROOT / "monitor" / "_vsisa_transcripts"
WORK = Path(r"C:\Users\zeesh\AppData\Local\Temp\claude\vsisa_audio")
FFMPEG = Path(r"C:\Users\zeesh\AppData\Local\Microsoft\WinGet\Packages"
              r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
              r"\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe")

# 25 MB is the API's hard ceiling; leave room so a chunk never lands on it
CHUNK_SEC = 900
API_LIMIT = 24 * 1024 * 1024

# Whisper drifts on unfamiliar jargon unless it is primed with the vocabulary.
PROMPT = ("Volume Spread Analysis trading lecture: volume, spread, candle, bullish, "
          "bearish, supply, demand, imbalance, liquidity, no supply, no demand, "
          "wick, body, stop loss, entry, support, resistance, gold, XAUUSD.")


def part_no(name: str) -> int:
    m = re.search(r"Part\s*(\d+)", name, re.I)
    return int(m.group(1)) if m else 0


def audio_for(video: Path, part: int) -> Path:
    """One 16 kHz mono mp3 per video. Speech only — no reason to ship the picture
    or a second channel to the API."""
    mp3 = WORK / f"part{part:02d}.mp3"
    if mp3.exists() and mp3.stat().st_size > 4096:
        return mp3
    subprocess.run([str(FFMPEG), "-y", "-i", str(video), "-vn", "-ac", "1",
                    "-ar", "16000", "-b:a", "32k", str(mp3)],
                   check=True, capture_output=True)
    return mp3


def chunks_of(mp3: Path, part: int) -> list[tuple[Path, float]]:
    """(file, offset_seconds). A whole file under the limit stays whole so its
    timestamps need no arithmetic."""
    if mp3.stat().st_size <= API_LIMIT:
        return [(mp3, 0.0)]
    out = []
    i = 0
    while True:
        piece = WORK / f"part{part:02d}_c{i}.mp3"
        if not piece.exists():
            r = subprocess.run(
                [str(FFMPEG), "-y", "-ss", str(i * CHUNK_SEC), "-t", str(CHUNK_SEC),
                 "-i", str(mp3), "-c", "copy", str(piece)], capture_output=True)
            if r.returncode != 0:
                break
        if not piece.exists() or piece.stat().st_size < 4096:
            try:
                piece.unlink()
            except OSError:
                pass
            break
        out.append((piece, float(i * CHUNK_SEC)))
        i += 1
        if i > 12:
            break
    return out


def translate(client: OpenAI, path: Path):
    """English + segment timestamps. Retries: a 15-video batch will meet a 429."""
    for attempt in range(6):
        try:
            with open(path, "rb") as f:
                return client.audio.translations.create(
                    model="whisper-1", file=f, prompt=PROMPT,
                    response_format="verbose_json")
        except Exception as e:  # noqa: BLE001
            wait = 20 * (attempt + 1)
            print(f"      retry {attempt + 1}/6 in {wait}s — {type(e).__name__}: "
                  f"{str(e)[:120]}", flush=True)
            time.sleep(wait)
    return None


def stamp(sec: float) -> str:
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    want = {int(a) for a in sys.argv[1:] if a.isdigit()}

    vids = sorted((p, part_no(p.name)) for p in VIDEOS.glob("*.mp4"))
    vids = [(p, n) for p, n in vids if n]
    vids.sort(key=lambda x: x[1])
    client = OpenAI(api_key=(ROOT / "monitor" / ".openai_api_key").read_text().strip())

    for video, part in vids:
        if want and part not in want:
            continue
        dest = OUT / f"part{part:02d}.md"
        if dest.exists() and dest.stat().st_size > 500:
            print(f"[skip] part {part:02d} already transcribed", flush=True)
            continue
        t0 = time.time()
        print(f"[part {part:02d}] extracting audio…", flush=True)
        try:
            mp3 = audio_for(video, part)
        except subprocess.CalledProcessError as e:
            print(f"[part {part:02d}] ffmpeg FAILED: {e.stderr[-300:]}", flush=True)
            continue

        lines, total = [], 0.0
        for piece, offset in chunks_of(mp3, part):
            print(f"[part {part:02d}] translating {piece.name} "
                  f"({piece.stat().st_size // 1024} KB)…", flush=True)
            r = translate(client, piece)
            if r is None:
                print(f"[part {part:02d}] GAVE UP on {piece.name}", flush=True)
                continue
            segs = getattr(r, "segments", None) or []
            if segs:
                for s in segs:
                    txt = (s.text if hasattr(s, "text") else s["text"]).strip()
                    st = s.start if hasattr(s, "start") else s["start"]
                    if txt:
                        lines.append(f"[{stamp(offset + st)}] {txt}")
                    total = max(total, offset + (s.end if hasattr(s, "end")
                                                 else s["end"]))
            else:
                lines.append(f"[{stamp(offset)}] {r.text.strip()}")

        if not lines:
            print(f"[part {part:02d}] nothing transcribed — skipped", flush=True)
            continue
        header = (f"# VSISA Part {part} — English translation\n\n"
                  f"Source: `{video.name}`\n"
                  f"Length: {stamp(total)} · {len(lines)} segments\n\n---\n\n")
        dest.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"[part {part:02d}] DONE {len(lines)} segments, {stamp(total)} long, "
              f"{time.time() - t0:.0f}s -> {dest.name}", flush=True)

    done = sorted(OUT.glob("part*.md"))
    print(f"\n=== {len(done)} transcripts in {OUT} ===", flush=True)
    for d in done:
        print(f"  {d.name}  {d.stat().st_size // 1024} KB", flush=True)


if __name__ == "__main__":
    main()
