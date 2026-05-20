"""Batch-transcribe an entire YouTube channel. Skips videos already done
(yt_<id>.txt present). Resilient: logs failures and continues. Writes a
running index to _yt_channel_index.md.

Usage: python _transcribe_channel.py <channel_videos_url>
"""
import os, sys, io, time, subprocess, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import yt_dlp
from openai import OpenAI

ROOT = r"C:\Users\zeesh\Documents\GitHub\turtle\monitor"
OUT = os.path.join(ROOT, "_loom_audio")
os.makedirs(OUT, exist_ok=True)
FFMPEG = r"C:\Users\zeesh\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
client = OpenAI(api_key=open(os.path.join(ROOT, ".openai_api_key")).read().strip())
INDEX = os.path.join(OUT, "_yt_channel_index.md")


def safe(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:60]


def download(vid):
    mp3 = os.path.join(OUT, f"yt_{vid}.mp3")
    if os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
        return mp3
    raw = None
    for ext in ("mp4","webm","m4a","opus","ts"):
        c = os.path.join(OUT, f"yt_{vid}.raw.{ext}")
        if os.path.exists(c): raw = c; break
    if not raw:
        opts = {"quiet":True,"no_warnings":True,"format":"bestaudio/best",
                "outtmpl":os.path.join(OUT, f"yt_{vid}.raw.%(ext)s"),
                "ffmpeg_location":FFMPEG}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://youtu.be/{vid}"])
        for ext in ("mp4","webm","m4a","opus","ts"):
            c = os.path.join(OUT, f"yt_{vid}.raw.{ext}")
            if os.path.exists(c): raw = c; break
    subprocess.run([FFMPEG,"-y","-i",raw,"-vn","-ac","1","-ar","16000","-b:a","32k",mp3],
                   check=True, capture_output=True)
    # clean raw to save disk
    try: os.remove(raw)
    except: pass
    return mp3


def _api(path):
    for a in range(4):
        try:
            with open(path,"rb") as f:
                return client.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=f, response_format="text")
        except Exception as e:
            if ("rate" in str(e).lower() or "429" in str(e)) and a < 3:
                time.sleep(15*(a+1)); continue
            raise


def transcribe(audio):
    ffprobe = FFMPEG.replace("ffmpeg.exe","ffprobe.exe")
    r = subprocess.run([ffprobe,"-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",audio],
                       capture_output=True,text=True,check=True)
    dur = float(r.stdout.strip() or 0)
    if dur <= 1300:
        return _api(audio)
    n = int(dur//1200)+1
    base = os.path.splitext(os.path.basename(audio))[0]
    parts=[]
    for i in range(n):
        ch = os.path.join(OUT, f"{base}.chunk{i:02d}.mp3")
        if not os.path.exists(ch) or os.path.getsize(ch) < 1024:
            subprocess.run([FFMPEG,"-y","-i",audio,"-ss",str(i*1200),"-t","1200",
                            "-acodec","copy",ch],check=True,capture_output=True)
        parts.append(_api(ch))
        try: os.remove(ch)
        except: pass
    return "\n\n[--- chunk boundary ---]\n\n".join(parts)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/@theforexguide8863/videos"
    opts = {"quiet":True,"no_warnings":True,"extract_flat":True,"skip_download":True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
    ents = info.get("entries") or []
    print(f"[channel] {len(ents)} videos", flush=True)
    done = skipped = failed = 0
    idx_lines = [f"# Channel transcripts — {len(ents)} videos\n"]
    for n, e in enumerate(ents, 1):
        vid = e.get("id"); title = (e.get("title") or "").strip()
        tx = os.path.join(OUT, f"yt_{vid}.txt")
        if os.path.exists(tx) and os.path.getsize(tx) > 100:
            print(f"[{n}/{len(ents)}] skip (done): {title[:50]}", flush=True)
            idx_lines.append(f"- [{vid}] {title} — {os.path.getsize(tx)}B (done)")
            skipped += 1; continue
        print(f"[{n}/{len(ents)}] {vid}  {title[:50]}", flush=True)
        try:
            audio = download(vid)
            text = transcribe(audio)
            open(tx,"w",encoding="utf-8").write(f"TITLE: {title}\n\n{text}")
            print(f"    saved {len(text)} chars", flush=True)
            idx_lines.append(f"- [{vid}] {title} — {len(text)} chars")
            done += 1
            time.sleep(2)
        except Exception as ex:
            print(f"    [FAIL] {str(ex)[:120]}", flush=True)
            idx_lines.append(f"- [{vid}] {title} — FAILED: {str(ex)[:80]}")
            failed += 1
        # rewrite index each iteration so progress is visible
        open(INDEX,"w",encoding="utf-8").write("\n".join(idx_lines))
    print(f"\n[DONE] new={done} skipped={skipped} failed={failed}", flush=True)


if __name__ == "__main__":
    main()
