"""One-off: download + transcribe a YouTube video for teacher-method comparison.
Usage: python _transcribe_youtube.py <youtube_url> <out_name>
"""
import os, sys, io, time, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import yt_dlp
from openai import OpenAI

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
OUT = os.path.join(ROOT, "_loom_audio")
FFMPEG_EXE = r"C:\Users\zeesh\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
KEY = open(os.path.join(ROOT, ".openai_api_key")).read().strip()
client = OpenAI(api_key=KEY)


def download(url, name):
    mp3 = os.path.join(OUT, f"{name}.mp3")
    if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
        return mp3
    tmpl = os.path.join(OUT, f"{name}.raw.%(ext)s")
    raw = None
    for ext in ("mp4","webm","m4a","opus","ts"):
        c = os.path.join(OUT, f"{name}.raw.{ext}")
        if os.path.exists(c): raw = c; break
    if not raw:
        opts = {"quiet":True,"no_warnings":True,"format":"bestaudio/best",
                "outtmpl":tmpl,"ffmpeg_location":FFMPEG_EXE}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        for ext in ("mp4","webm","m4a","opus","ts"):
            c = os.path.join(OUT, f"{name}.raw.{ext}")
            if os.path.exists(c): raw = c; break
    print(f"  extracting audio -> {name}.mp3", flush=True)
    subprocess.run([FFMPEG_EXE,"-y","-i",raw,"-vn","-ac","1","-ar","16000","-b:a","32k",mp3],
                   check=True, capture_output=True)
    return mp3


def _api(path):
    for attempt in range(4):
        try:
            with open(path,"rb") as f:
                return client.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=f, response_format="text")
        except Exception as e:
            if ("rate" in str(e).lower() or "429" in str(e)) and attempt < 3:
                time.sleep(15*(attempt+1)); continue
            raise


def transcribe(audio):
    ffprobe = FFMPEG_EXE.replace("ffmpeg.exe","ffprobe.exe")
    r = subprocess.run([ffprobe,"-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",audio],
                       capture_output=True,text=True,check=True)
    dur = float(r.stdout.strip() or 0)
    print(f"  duration: {dur:.0f}s", flush=True)
    if dur <= 1300:
        return _api(audio)
    n = int(dur//1200)+1
    base = os.path.splitext(os.path.basename(audio))[0]
    parts = []
    for i in range(n):
        ch = os.path.join(OUT, f"{base}.chunk{i:02d}.mp3")
        if not os.path.exists(ch) or os.path.getsize(ch) < 1024:
            subprocess.run([FFMPEG_EXE,"-y","-i",audio,"-ss",str(i*1200),"-t","1200",
                            "-acodec","copy",ch],check=True,capture_output=True)
        print(f"    chunk {i+1}/{n} transcribing...", flush=True)
        parts.append(_api(ch))
    return "\n\n[--- chunk boundary ---]\n\n".join(parts)


if __name__ == "__main__":
    url = sys.argv[1]; name = sys.argv[2]
    print(f"downloading {url} ...", flush=True)
    audio = download(url, name)
    print(f"transcribing {os.path.basename(audio)} ...", flush=True)
    text = transcribe(audio)
    out = os.path.join(OUT, f"{name}.txt")
    open(out,"w",encoding="utf-8").write(text)
    print(f"saved {len(text)} chars -> {out}", flush=True)
