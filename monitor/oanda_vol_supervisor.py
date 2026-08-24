"""oanda_vol_supervisor.py — keeps HIS eye's volume flowing, hang-proof.

2026-08-21. ZeeUHV v1.58 is LIVE on OANDA volume (Zee + Zainab). The EA re-reads
Common\\Files\\oanda_vol.csv every M1 bar and falls back to broker volume for any
minute the table lacks — so a frozen collector does not break trading, it SILENTLY
reverts the whole feature. That failure has now happened twice in one day:

  * oanda_volume_bridge.py --loop : process alive, file frozen 22 h
  * oanda_vol_tv.py --loop 60     : process alive, first cycle never returned

Both are the same fault: tvDatafeed opens a websocket per cycle and can block with
no timeout, and an in-process loop cannot rescue itself once blocked. The cure is
to never let a cycle own the loop — run the collector as a ONE-SHOT subprocess with
a hard timeout, every cycle a fresh process. A hang costs one cycle, not the feed.

Also watches freshness and shouts when the table is stale, so the silent-fallback
failure becomes a loud one.
"""
from __future__ import annotations
import subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
COLLECTOR = ROOT / "monitor" / "oanda_vol_tv.py"
# 2026-08-21 (Zee: "ensure that the candles AND volume are taken from tradingview"):
# the CANDLES need the same websocket. oanda_m1.csv had rotted 22 h since the CDP
# bridge died, so every decision surface silently read BROKER bars.
M1_COLLECTOR = ROOT / "monitor" / "oanda_m1_tv.py"
VOL_F = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_vol.csv")
LOG = ROOT / "monitor" / "oanda_vol_supervisor.log"
HEARTBEAT = ROOT / "monitor" / "oanda_vol_heartbeat.json"
# 2026-08-24: was 60. On an M1 EA a 60-second cycle means the just-closed candle can
# be up to a minute late, and the EA either waits (entering a minute after the signal,
# at a materially different price) or judges a half-written bar. The first live
# BasedOnLaws trade did the latter: it read the breakout as vol 788 when the finished
# candle was 2109, which flipped his "breakout quieter than the UHV" law from REFUSE
# to PASS. 15s bounds the staleness to a few seconds.
CYCLE_SEC = 5
HARD_TIMEOUT = 45          # a cycle that outlives this is a hang: kill it
STALE_WARN_MIN = 5         # table older than this = the EA is silently on broker vol


def say(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def table_age_min():
    if not VOL_F.exists():
        return None
    return (time.time() - VOL_F.stat().st_mtime) / 60.0


def _find_python():
    """The interpreter that actually HAS tvDatafeed. 2026-08-21: both collector
    failures today were one cause — the daemons ran under the ARM64 python while
    tvDatafeed lives in the x64 one, so every cycle died on ImportError inside a
    hidden console. Never assume sys.executable again; prove it."""
    cands = [sys.executable,
             r"C:\Users\zeesh\AppData\Local\Python\pythoncore-3.14-64\python.exe",
             r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe",
             "py"]
    for exe in cands:
        try:
            r = subprocess.run([exe, "-c", "import tvDatafeed"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return exe
        except Exception:
            continue
    return None


PY_EXE = None


def cycle():
    global PY_EXE
    if PY_EXE is None:
        PY_EXE = _find_python()
        if PY_EXE is None:
            say("ALERT: no interpreter has tvDatafeed — feed cannot run")
            return
        say(f"interpreter: {PY_EXE}")
    t0 = time.time()
    try:
        r = subprocess.run([PY_EXE, str(COLLECTOR)],
                           capture_output=True, text=True, timeout=HARD_TIMEOUT)
        out = (r.stdout or "").strip().splitlines()
        tail = out[-1] if out else (r.stderr or "").strip()[:120]
        ok = "-> oanda_vol.csv" in (r.stdout or "")
        say(f"{'ok ' if ok else 'RUN'} {time.time()-t0:4.1f}s · {tail}")
    except subprocess.TimeoutExpired:
        say(f"HANG — collector killed after {HARD_TIMEOUT}s (this cycle lost, feed intact)")
    except Exception as e:
        say(f"ERROR {e}")
    # the candles, from the same source
    try:
        # --fast on routine cycles (150 bars, ~1.3s); a FULL 5,000-bar pull every
        # 20th cycle keeps the archive/backfill honest. 2026-08-24: the EA waits for
        # the forming candle before judging the one before it, so this pull's latency
        # IS the entry latency — it was running 40s late.
        globals()["_n"] = globals().get("_n", 0) + 1
        args = [PY_EXE, str(M1_COLLECTOR)] + ([] if globals()["_n"] % 20 == 1 else ["--fast"])
        r2 = subprocess.run(args,
                            capture_output=True, text=True, timeout=HARD_TIMEOUT)
        o2 = (r2.stdout or "").strip().splitlines()
        say("m1 " + (o2[-1] if o2 else (r2.stderr or "").strip()[:110]))
    except subprocess.TimeoutExpired:
        say(f"m1 HANG — killed after {HARD_TIMEOUT}s")
    except Exception as e:
        say(f"m1 ERROR {e}")
    age = table_age_min()
    if age is None:
        say("ALERT: oanda_vol.csv MISSING — ZeeUHV is silently on BROKER volume")
    elif age > STALE_WARN_MIN:
        say(f"ALERT: table {age:.1f} min stale — ZeeUHV is silently on BROKER volume")
    try:
        HEARTBEAT.write_text(
            '{"ts": %d, "table_age_min": %.2f}' % (int(time.time()), age if age else -1),
            encoding="ascii")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    say("supervisor up — one-shot collector every "
        f"{CYCLE_SEC}s, hard timeout {HARD_TIMEOUT}s")
    while True:
        cycle()
        time.sleep(CYCLE_SEC)
