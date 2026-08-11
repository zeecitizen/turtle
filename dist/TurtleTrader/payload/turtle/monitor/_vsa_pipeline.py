"""VSA video pipeline: download all 22 audios, transcribe with gpt-4o-transcribe.

Outputs:
  monitor/_vsa_audio/partNN.webm   - downloaded audio
  monitor/_vsa_transcripts/partNN.txt  - Urdu/Hindi transcript (verbatim)
  monitor/_vsa_transcripts/_index.md   - master index with summary line per file
"""
import os
import sys
import io
import time
import yt_dlp
from openai import OpenAI

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
AUDIO_DIR = os.path.join(ROOT, "_vsa_audio")
TRANSCRIPT_DIR = os.path.join(ROOT, "_vsa_transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

KEY = open(os.path.join(ROOT, ".openai_api_key")).read().strip()
client = OpenAI(api_key=KEY)

# Part-number -> video ID (sorted)
VIDEOS = [
    (1,  "Sjpho2hqHvU"),
    (2,  "xWKT3wLmCXM"),  # Part 2 (was missing in earlier mapping; correcting)
    (3,  "f4RzHjYzQjA"),
    (4,  "oXzX3ohkQ7I"),
    (5,  "Zg5thlZU920"),
    (6,  "Kq8LtzlTUCc"),
    (7,  "Zo57wbdu_PQ"),
    (8,  "rksfDgBUauc"),
    (9,  "f6uc0c-cKgA"),
    (10, "tltsjLtD_GQ"),
    (11, "cB8zmMIBhMc"),
    (12, "5yJy-LBNbbU"),
    (13, "M4VHwKhP4EU"),
    (14, "z5FKl4Bo7uQ"),
    (15, "RwxQwzlvBhc"),
    (16, "u2Qv6F8Y1QE"),
    (17, "LE2VfM1lIhg"),
    (18, "gywHFOUdf-k"),
    (19, "E7gktA2AFXg"),
    (20, "LsB13M674h8"),
    (21, "Dv0tzFdnegc"),
    (22, "rEOkATLuDmw"),
]


def download_audio(video_id: str, part_num: int) -> str:
    """Download audio. Returns the audio file path."""
    out_template = os.path.join(AUDIO_DIR, f"part{part_num:02d}.%(ext)s")
    # Skip if already downloaded
    for ext in ("webm", "m4a", "mp3", "opus"):
        candidate = os.path.join(AUDIO_DIR, f"part{part_num:02d}.{ext}")
        if os.path.exists(candidate):
            return candidate
    opts = {
        "quiet": True,
        "no_warnings": True,
        # Constrain to <25MB (Whisper API limit)
        "format": "bestaudio[filesize<25M]/bestaudio[filesize_approx<25M]/worstaudio",
        "outtmpl": out_template,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    # Find the actual extension downloaded
    for ext in ("webm", "m4a", "mp3", "opus"):
        candidate = os.path.join(AUDIO_DIR, f"part{part_num:02d}.{ext}")
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"no downloaded file for part{part_num:02d}")


def transcribe(audio_path: str, max_retries: int = 4) -> str:
    """Transcribe Urdu/Hindi audio. Retries on 403 (rate-limit-style block) with backoff."""
    last_err = None
    for attempt in range(max_retries):
        try:
            with open(audio_path, "rb") as f:
                return client.audio.transcriptions.create(
                    model="gpt-4o-transcribe",
                    file=f,
                    response_format="text",
                )
        except Exception as e:
            last_err = e
            msg = str(e)
            if "model_not_found" in msg or "rate" in msg.lower() or "429" in msg:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s
                print(f"    retry {attempt+1}/{max_retries} after {wait}s ({msg[:80]})")
                time.sleep(wait)
                continue
            raise
    raise last_err


def main():
    index_lines = ["# VSA Course Transcripts — Index", ""]
    total_chars = 0
    t_start = time.time()
    for part, vid in VIDEOS:
        print(f"\n=== Part {part:02d} (video {vid}) ===")
        transcript_path = os.path.join(TRANSCRIPT_DIR, f"part{part:02d}.txt")
        if os.path.exists(transcript_path):
            existing = open(transcript_path, encoding="utf-8").read()
            if len(existing) > 100:
                print(f"  [skip] already transcribed ({len(existing)} chars)")
                index_lines.append(f"- **Part {part:02d}**: {len(existing)} chars  `{transcript_path}`")
                total_chars += len(existing)
                continue

        print("  downloading audio...")
        try:
            audio = download_audio(vid, part)
        except Exception as e:
            print(f"  [FAIL download] {e}")
            index_lines.append(f"- **Part {part:02d}**: DOWNLOAD FAILED ({e})")
            continue
        size_mb = os.path.getsize(audio) / 1024 / 1024
        print(f"  audio: {os.path.basename(audio)} ({size_mb:.1f} MB)")

        print("  transcribing...")
        try:
            text = transcribe(audio)
        except Exception as e:
            print(f"  [FAIL transcribe] {e}")
            index_lines.append(f"- **Part {part:02d}**: TRANSCRIBE FAILED ({e})")
            continue

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  saved: {len(text)} chars -> {transcript_path}")
        index_lines.append(f"- **Part {part:02d}**: {len(text)} chars  `{transcript_path}`")
        total_chars += len(text)

        # Pace requests to avoid rate-limit-style 403s on Tier 1.
        time.sleep(5)

    elapsed = time.time() - t_start
    index_lines.append("")
    index_lines.append(f"**Total**: {total_chars:,} chars across {len(VIDEOS)} videos | elapsed {elapsed/60:.1f} min")

    index_path = os.path.join(TRANSCRIPT_DIR, "_index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))
    print(f"\nDone. Index at {index_path}")
    print(f"Total: {total_chars:,} chars / {elapsed/60:.1f} min")


if __name__ == "__main__":
    main()
