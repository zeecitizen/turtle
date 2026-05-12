"""Zee's 10-lesson trading course (Loom) — download + transcribe + index.

Outputs:
  monitor/_loom_audio/lessonNN.mp4      - downloaded video/audio
  monitor/_loom_audio/lessonNN.txt      - Urdu/Hindi/English transcript
  monitor/_loom_audio/_index.md         - master index
"""
import os, sys, io, time, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import yt_dlp
from openai import OpenAI

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
OUT = os.path.join(ROOT, "_loom_audio")
os.makedirs(OUT, exist_ok=True)

FFMPEG_EXE = r"C:\Users\zeesh\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

KEY = open(os.path.join(ROOT, ".openai_api_key")).read().strip()
client = OpenAI(api_key=KEY)

LESSONS = [
    (1,  "86ecbbb5db794705bb7a3728f120a4b2", "Introduction to Trading"),
    (2,  "a14bb57b109e42a389fed253a4e5ff83", "Introduction to Our Strategy"),
    (3,  "f668522c5c3f4e6d959da0247dbded96", "Understanding Fair Value Gaps"),
    (4,  "1a4fade48d60435c80ac158d3a0b88a5", "Where to trade? Entry/Exit points of interest"),
    (5,  "6499a1696b8b477aae57e5edbfc07c84", "Lesson 5"),
    (6,  "4cfefdc95a4d4fdf8f10955a122d9ca6", "Lesson 6"),
    (7,  "4e69d70344ff48e7b4e56a540559c59a", "Lesson 7"),
    (8,  "9e59f85441b344c78292f9df16981279", "Lesson 8"),
    (9,  "433d5ce6b38c4e71a290e90721c8f629", "Lesson 9"),
    (10, "8dac2f4d653e4a2a91b5301027ed5434", "Lesson 10"),
]


def download(share_id: str, lesson: int):
    mp3_path = os.path.join(OUT, f"lesson{lesson:02d}.mp3")
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1024:
        return mp3_path
    video_template = os.path.join(OUT, f"lesson{lesson:02d}.raw.%(ext)s")
    # Find existing raw download
    raw_path = None
    for ext in ("mp4", "webm", "m4a", "mp3", "opus", "ts"):
        cand = os.path.join(OUT, f"lesson{lesson:02d}.raw.{ext}")
        if os.path.exists(cand):
            raw_path = cand; break
        # Also check legacy filenames from earlier runs
        cand2 = os.path.join(OUT, f"lesson{lesson:02d}.{ext}")
        if os.path.exists(cand2) and not cand2.endswith(".mp3"):
            raw_path = cand2; break
    if not raw_path:
        opts = {
            "quiet": True, "no_warnings": True,
            "format": "hls-cdn-audio-audio/hls-raw-audio-audio/bestaudio/best",
            "outtmpl": video_template,
            "ffmpeg_location": FFMPEG_EXE,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.loom.com/share/{share_id}"])
        for ext in ("mp4", "webm", "m4a", "mp3", "opus", "ts"):
            cand = os.path.join(OUT, f"lesson{lesson:02d}.raw.{ext}")
            if os.path.exists(cand):
                raw_path = cand; break
        if not raw_path:
            raise FileNotFoundError(f"no raw file for lesson{lesson:02d}")
    # Extract audio to mp3 16kbps mono (small, Whisper-friendly, well under 25MB)
    print(f"  extracting audio: {os.path.basename(raw_path)} -> lesson{lesson:02d}.mp3", flush=True)
    subprocess.run(
        [FFMPEG_EXE, "-y", "-i", raw_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", mp3_path],
        check=True, capture_output=True,
    )
    return mp3_path


def _api_call(path):
    last = None
    for attempt in range(4):
        try:
            with open(path, "rb") as f:
                return client.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=f, response_format="text",
                )
        except Exception as e:
            last = e
            m = str(e).lower()
            if "rate" in m or "429" in m:
                wait = 15 * (attempt + 1)
                print(f"    retry in {wait}s ({str(e)[:80]})")
                time.sleep(wait)
                continue
            raise
    raise last


def transcribe(audio_path: str):
    """Transcribe, splitting into 20-min chunks if > 1300s (model limit is 1400s)."""
    # Probe duration via ffprobe (shipped with ffmpeg)
    ffprobe = FFMPEG_EXE.replace("ffmpeg.exe", "ffprobe.exe")
    r = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(r.stdout.strip() or 0)
    print(f"    duration: {duration:.0f}s", flush=True)
    if duration <= 1300:
        return _api_call(audio_path)
    # Split into 1200s chunks
    chunk_dur = 1200
    n = int(duration // chunk_dur) + 1
    print(f"    splitting into {n} x {chunk_dur}s chunks", flush=True)
    chunks_dir = os.path.dirname(audio_path)
    base = os.path.splitext(os.path.basename(audio_path))[0]
    parts = []
    for i in range(n):
        chunk_path = os.path.join(chunks_dir, f"{base}.chunk{i:02d}.mp3")
        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) < 1024:
            subprocess.run(
                [FFMPEG_EXE, "-y", "-i", audio_path,
                 "-ss", str(i * chunk_dur), "-t", str(chunk_dur),
                 "-acodec", "copy", chunk_path],
                check=True, capture_output=True,
            )
        size_kb = os.path.getsize(chunk_path) / 1024
        print(f"      chunk {i+1}/{n}: {size_kb:.0f} KB transcribing...", flush=True)
        text = _api_call(chunk_path)
        parts.append(text)
    return "\n\n[--- chunk boundary ---]\n\n".join(parts)


def main():
    t0 = time.time()
    index = ["# Zee's Trading Course — Transcript Index", ""]
    total = 0
    for num, share_id, title in LESSONS:
        print(f"\n=== Lesson {num:02d}: {title} ===", flush=True)
        tx_path = os.path.join(OUT, f"lesson{num:02d}.txt")
        if os.path.exists(tx_path) and os.path.getsize(tx_path) > 100:
            existing = open(tx_path, encoding="utf-8").read()
            print(f"  [skip] already transcribed ({len(existing)} chars)")
            index.append(f"- **Lesson {num:02d}** — {title} — {len(existing)} chars  `{tx_path}`")
            total += len(existing)
            continue
        try:
            print("  downloading...", flush=True)
            audio = download(share_id, num)
            mb = os.path.getsize(audio) / 1024 / 1024
            print(f"  audio: {os.path.basename(audio)} ({mb:.1f} MB)", flush=True)
        except Exception as e:
            print(f"  [DOWNLOAD FAIL] {e}", flush=True)
            index.append(f"- **Lesson {num:02d}** — {title} — DOWNLOAD FAILED")
            continue
        try:
            print("  transcribing...", flush=True)
            text = transcribe(audio)
        except Exception as e:
            print(f"  [TRANSCRIBE FAIL] {e}", flush=True)
            index.append(f"- **Lesson {num:02d}** — {title} — TRANSCRIBE FAILED")
            continue
        with open(tx_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  saved: {len(text)} chars -> lesson{num:02d}.txt", flush=True)
        index.append(f"- **Lesson {num:02d}** — {title} — {len(text)} chars  `{tx_path}`")
        total += len(text)
        time.sleep(3)

    elapsed = time.time() - t0
    index.append("")
    index.append(f"**Total**: {total:,} chars / {elapsed/60:.1f} min")
    with open(os.path.join(OUT, "_index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index))
    print(f"\n[DONE] {total:,} chars / {elapsed/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
