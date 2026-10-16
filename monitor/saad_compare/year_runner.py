"""year_runner.py - the compare page's "10 months in MT5" view: every chart setting change, re-run on Jan-Oct 2026.

Zee 2026-10-16: "if i tune settings on tradingview. they're showing on chart the result of 5 days only ... we need a
tool that runs MT5 automatically on 1 year of data using the tradingview chart's settings. and individually display
every month's winrate/total profit .. this way i can make changes on tradingview -> see their effect on all months ->
but we need to make this effect fastest auto sync so that i can see the effect by changing 1 setting"  /  "10 months is
enough for us"

How it is fast:
  * one MT5 pass per MONTH (ToDate is exclusive: 1st -> next 1st), ~19 s each on real ticks
  * the 10 months run in parallel on 6 portable rigs (C:/mt5_rig_axi2 .. axi7, XAUUSD_TK real ticks) -> ~40 s
  * a watcher reads the chart's settings every 2 s; a change (stable for one more poll) cancels the passes still
    running and starts the new batch at once
  * results are cached by (settings, delay, EA build): going back to a setting shows its months instantly
The EA runs on its own MT5 candles here (InpBarSource=0): the chart only holds ~5 days of 1-min candles.
"""
import hashlib
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import server                 # first: it puts monitor/strategy_lab on the path
import axi_rig

RIGS = ["axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]      # "axi" stays free for the compare page's own runs
SYMBOL = "XAUUSD_TK"
MONTHS = [f"2026.{m:02d}" for m in range(1, 11)]             # XAUUSD_TK real ticks: Jan - Oct 8 2026
CACHE = server.HERE / "why_out" / "year_cache.json"
EA_SRC = server.ROOT / "mt5" / f"{server.EA}.mq5"
POLL = 2.0


def _next(m):
    y, mo = int(m[:4]), int(m[5:])
    return f"{y + (mo == 12)}.{(mo % 12) + 1:02d}.01"


class YearRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.gen = 0
        self.auto = True
        self.delay = "-1"
        self.sets = None            # EA inputs of the batch on screen
        self.prev = None            # the batch before it (for the change column)
        self.changed = []           # what changed between them
        self.months = {}            # month -> {"status", "result", "rig", "secs"}
        self.started = self.finished = None
        self.error = ""
        self.notes = []
        self.seen = None            # last settings read from the chart
        self.q = queue.Queue()
        self.compiled = {}          # rig -> EA source mtime compiled there
        self.cache = {}
        try:
            self.cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
        for r in RIGS:
            threading.Thread(target=self._worker, args=(r,), daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    # ── keys / cache ───────────────────────────────────────────────────────
    def _key(self, sets, m):
        blob = json.dumps({"s": sets, "d": self.delay, "ea": int(EA_SRC.stat().st_mtime), "m": m}, sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()

    def _save(self):
        CACHE.parent.mkdir(exist_ok=True)
        if len(self.cache) > 3000:
            for k in list(self.cache)[:1000]:
                del self.cache[k]
        CACHE.write_text(json.dumps(self.cache), encoding="utf-8")

    # ── the watcher: the chart's settings every 2 s ─────────────────────────
    def _watch(self):
        pending = None
        while True:
            time.sleep(POLL)
            if not self.auto:
                pending = None
                continue
            try:
                _, _, sets, notes = server.read_settings()
            except Exception as e:
                self.error = f"cannot read the chart: {e}"
                continue
            self.error = ""
            sets = self._run_sets(sets)
            if sets == self.sets:
                pending = None
                continue
            if sets != pending:          # wait one more poll: Zee may still be typing / clicking
                pending = sets
                continue
            pending = None
            self.notes = notes
            self.start(sets)

    def _run_sets(self, sets):
        s = dict(sets)
        s["InpBarSource"] = "0"          # MT5's own candles: the chart has no 1-min history this far back
        return s

    # ── a batch ────────────────────────────────────────────────────────────
    def start(self, sets=None):
        if sets is None:
            _, _, sets, notes = server.read_settings()
            self.notes = notes
            sets = self._run_sets(sets)
        with self.lock:
            self.gen += 1
            g = self.gen
            if self.sets is not None and self.sets != sets:
                done = {m: v["result"] for m, v in self.months.items() if v.get("result")}
                if done:
                    self.prev = {"sets": self.sets, "months": done}
                self.changed = [{"k": k, "was": self.sets.get(k), "now": sets.get(k)}
                                for k in sorted(set(self.sets) | set(sets)) if self.sets.get(k) != sets.get(k)]
            self.sets = sets
            self.started, self.finished = time.time(), None
            self.months = {}
            for m in MONTHS:
                hit = self.cache.get(self._key(sets, m))
                if hit:
                    self.months[m] = {"status": "done", "result": hit, "cached": True}
                else:
                    self.months[m] = {"status": "queued"}
                    self.q.put((g, m, sets))
            if all(v["status"] == "done" for v in self.months.values()):
                self.finished = time.time()

    def _worker(self, rig):
        while True:
            g, m, sets = self.q.get()
            if g != self.gen:
                continue
            try:
                mt = EA_SRC.stat().st_mtime
                if self.compiled.get(rig) != mt:
                    axi_rig.compile_ea(server.EA, rig=rig)
                    self.compiled[rig] = mt
                with self.lock:
                    if g != self.gen:
                        continue
                    self.months[m] = {"status": "running", "rig": rig, "since": time.time()}
                t0 = time.time()
                for attempt in range(3):
                    r = axi_rig.run(server.EA, SYMBOL, "M1", sets, frm=f"{m}.01", to=_next(m), deposit=100000,
                                    exec_mode=int(self.delay), tag=f"year_{m.replace('.', '_')}", rig=rig,
                                    cancel=lambda: g != self.gen)
                    # 16 Oct: with 6 rigs starting together a pass sometimes processes NO ticks (quality "100%" without
                    # "real ticks", 0 trades) - April once on axi6, once on axi2; the same pass again is fine
                    if r.get("error") or "real ticks" in str(r.get("quality")) or r.get("trades"):
                        break
                    time.sleep(2)
                else:
                    r = {"error": "the tester processed no ticks 3 times - press Run now"}
                if r.get("error") == "cancelled":
                    continue
                res = {"error": r["error"]} if r.get("error") else {
                    "net": r.get("net"), "trades": r.get("trades"), "wr": r.get("wr"), "pf": r.get("pf"), "dd": r.get("dd"),
                    "quality": r.get("quality"), "days": (r.get("day_stats") or {}).get("days"),
                    "green": (r.get("day_stats") or {}).get("green"), "n": (r.get("trade_stats") or {}).get("n"),
                    "avg_win": (r.get("trade_stats") or {}).get("avg_win"), "avg_loss": (r.get("trade_stats") or {}).get("avg_loss")}
                with self.lock:
                    if not res.get("error") and "real ticks" in str(res.get("quality")):
                        self.cache[self._key(sets, m)] = res
                        self._save()
                    if g == self.gen:
                        self.months[m] = {"status": "error" if res.get("error") else "done", "result": res, "rig": rig,
                                          "secs": round(time.time() - t0)}
                        if all(v["status"] in ("done", "error") for v in self.months.values()):
                            self.finished = time.time()
            except BaseException as e:          # compile_ea uses sys.exit on a failed compile
                with self.lock:
                    if g == self.gen:
                        self.months[m] = {"status": "error", "result": {"error": str(e)[-300:]}, "rig": rig}

    # ── for the page ───────────────────────────────────────────────────────
    def state(self):
        with self.lock:
            now = time.time()
            return {"auto": self.auto, "delay": self.delay, "months": self.months, "order": MONTHS,
                    "prev": (self.prev or {}).get("months"), "changed": self.changed, "notes": self.notes,
                    "error": self.error, "rigs": len(RIGS), "symbol": SYMBOL,
                    "elapsed": round((self.finished or now) - self.started) if self.started else None,
                    "running": bool(self.started and not self.finished),
                    "at": datetime.fromtimestamp(self.started).strftime("%H:%M:%S") if self.started else ""}

    def configure(self, q):
        if "auto" in q:
            self.auto = bool(q["auto"])
        restart = False
        if "delay" in q and str(q["delay"]) != self.delay:
            self.delay = str(q["delay"])
            restart = True
        if q.get("run"):
            self.start(None)                 # read the chart now (cached months show at once)
        elif restart and self.sets is not None:
            self.start(self.sets)            # same settings, other delay: other cache keys
