"""Transcribe Sajid's CSM tutorial video."""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import yt_dlp
from openai import OpenAI

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
AUDIO_PATH = os.path.join(ROOT, "_csm_audio.webm")
TRANSCRIPT_PATH = os.path.join(ROOT, "_vsa_transcripts", "csm_video.txt")
KEY = open(os.path.join(ROOT, ".openai_api_key")).read().strip()

VIDEO_URL = "https://www.youtube.com/watch?v=cMBlcqlhzok"

# Download
if not os.path.exists(AUDIO_PATH):
    print("Downloading audio...")
    opts = {
        "quiet": True, "no_warnings": True,
        "format": "bestaudio[filesize<25M]/bestaudio[filesize_approx<25M]/worstaudio",
        "outtmpl": AUDIO_PATH.replace(".webm", ".%(ext)s"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(VIDEO_URL, download=False)
        print(f"  Title: {info['title'][:80]}")
        print(f"  Duration: {info['duration']}s ({info['duration']//60}m)")
        ydl.download([VIDEO_URL])
    # Find actual file
    for ext in ("webm", "m4a", "mp3", "opus"):
        cand = AUDIO_PATH.replace(".webm", f".{ext}")
        if os.path.exists(cand):
            AUDIO_PATH = cand
            break
print(f"Audio: {AUDIO_PATH} ({os.path.getsize(AUDIO_PATH)//1024} KB)")

# Transcribe (with retries since rate-limit was a problem)
client = OpenAI(api_key=KEY)
text = None
for attempt in range(5):
    try:
        with open(AUDIO_PATH, "rb") as f:
            text = client.audio.transcriptions.create(
                model="gpt-4o-transcribe", file=f, response_format="text",
            )
        print(f"[ok] transcribed ({len(text)} chars)")
        break
    except Exception as e:
        wait = 15 * (attempt + 1)
        print(f"  retry {attempt+1}/5 after {wait}s: {str(e)[:160]}")
        time.sleep(wait)

if text is None:
    print("FAILED to transcribe")
    sys.exit(1)

os.makedirs(os.path.dirname(TRANSCRIPT_PATH), exist_ok=True)
with open(TRANSCRIPT_PATH, "w", encoding="utf-8") as f:
    f.write(text)
print(f"\nSaved to {TRANSCRIPT_PATH}")
print()
print("=== First 2000 chars ===")
print(text[:2000])
