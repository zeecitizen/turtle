"""One-off Whisper test on Part 1."""
import os
import glob
from openai import OpenAI

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
key = open(os.path.join(ROOT, ".openai_api_key")).read().strip()
client = OpenAI(api_key=key)

audio_files = glob.glob(os.path.join(ROOT, "_vsa_audio", "part01.*"))
if not audio_files:
    print("No audio file found")
    raise SystemExit(1)

audio_path = audio_files[0]
size_mb = os.path.getsize(audio_path) / 1024 / 1024
print(f"Submitting {audio_path} ({size_mb:.2f}MB) to Whisper translations...")

# Try multiple models; newer projects may not have whisper-1 enabled.
# gpt-4o-mini-transcribe: $0.003/min, supports auto-language detection.
# Use /audio/transcriptions (translations endpoint only supports whisper-1).
# We'll then translate the Hindi text via GPT in a second pass if needed.
candidates = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
result = None
last_err = None
for model in candidates:
    try:
        with open(audio_path, "rb") as f:
            if model == "whisper-1":
                # whisper-1 supports translations endpoint (transcribe + translate to EN)
                result = client.audio.translations.create(
                    model=model, file=f, response_format="text",
                )
            else:
                # gpt-4o models only support transcriptions (same-language)
                result = client.audio.transcriptions.create(
                    model=model, file=f, response_format="text", language="hi",
                )
        print(f"[ok] used model: {model}")
        break
    except Exception as e:
        print(f"[!!] {model}: {type(e).__name__}: {str(e)[:200]}")
        last_err = e
if result is None:
    raise last_err

out_dir = os.path.join(ROOT, "_vsa_transcripts")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "part01.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(result)

print(f"Got {len(result)} chars; saved to {out_path}")
print()
print("=== First 1500 chars of English translation ===")
print(result[:1500])
