"""dia_winrate.py — the win-rate loop for ZeeUHV_Diamond, run entirely in MT5's tester.

Zee, 2026-09-29: "try to increase the Winrate of the EA to maximum possible. On Feb 11 Zee
used the same strategy of ultra high volume breakout to get a winrate of 94% .. don't care
about drawdown etc for now ... i expect you to have a 90%+ winrate"

Every number this prints comes from MT5's Strategy Tester on REAL BROKER TICKS (Model 4)
with the recorded spread and a 163 ms execution delay. No Python simulates a fill here;
this file only writes .ini files, launches the rig, and reads the reports back.

WHAT IT ADDS OVER diamond_lab.py
  * a persistent ledger, so a loop that spans hours never re-runs a config it has already
    measured, and never loses a result to a crashed session
  * batches supplied as JSON on the command line, so a new hypothesis needs no new file
  * WR reported beside NET AND the loss distribution, because a win rate bought with a
    wider stop is not a better strategy - it is the same strategy with a bigger cliff, and
    the standing goal says to show both in the same table

THE THING THIS IS FOR IS ALSO ITS MAIN TRAP. Win rate in this EA is mostly GEOMETRY: a
1-point target against a 20-point stop wins ~92% from ANY entry (NullEntry proved it, 103
days, 1,716 trades, 92.42% on no rules at all). So widening the stop WILL raise the win
rate and that is not a discovery. Every row therefore carries avg loss and worst loss, and
the ledger keeps them, so the cost of each point of win rate stays visible.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import diamond_lab as D   # noqa: E402  - reuse its rig plumbing, unchanged

LEDGER = HERE / "_winrate_ledger.json"

# v1.18 AS SHIPPED AND AS IT RAN LIVE: diamond_lab.SHIPPED pins InpTrendMode to 0 because
# it was written to compare the two; the EA's own default - and the version that traded on
# Blueberry 21-23 Sep - is mode 1, CamelTrend. Starting anywhere else would measure a
# configuration nobody ships.
CAMEL = {"InpTrendMode": "1", "InpHighTest": "1"}


def load_ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_ledger(led: dict) -> None:
    LEDGER.write_text(json.dumps(led, indent=1, sort_keys=True), encoding="utf-8")


def ea_stamp() -> str:
    """Identify the COMPILED BINARY in the cache key.

    v1.24's InpOandaPrice was a silent no-op (a guard compared PERIOD_CURRENT against
    PERIOD_M1). After fixing it in v1.25 the ledger would have served the v1.24 result for the
    v1.25 question, because the key described only the inputs. A result belongs to the binary
    that produced it.
    """
    f = D.RIG / "MQL5" / "Experts" / (D.EA + ".ex5")
    try:
        st = f.stat()
        return "%d.%d" % (int(st.st_mtime), st.st_size)
    except OSError:
        return "no-ex5"


def key_of(over: dict, frm: str, to: str, deposit: int) -> str:
    cfg = dict(D.SHIPPED)
    cfg.update(CAMEL)
    cfg.update({k: str(v) for k, v in over.items()})
    # deposit is IN THE KEY: two runs differing only in funding are different
    # measurements, and without it the ledger would serve a censored result for
    # a well-funded question.
    return "%s|%s|%s|%s|%s" % (frm, to, deposit, ea_stamp(),
                               json.dumps(cfg, sort_keys=True))


def losses_from(stem: str) -> dict:
    """Re-read the report for the loss distribution stats() does not keep.

    WHY IT MATTERS HERE: the whole search is pointed at win rate, and win rate is the one
    statistic in this strategy that can be bought. The average and worst loss are what it
    is bought WITH, so they travel in the same row.
    """
    p = D.REPORTS / (stem + ".htm")
    raw = p.read_bytes()
    try:
        h = raw.decode("utf-16-le")
    except Exception:
        h = raw.decode("utf-8", errors="replace")
    pnl = []
    for row in re.findall(r'<tr bgcolor="#[0-9A-F]{6}" align=right>(.*?)</tr>', h, re.S):
        c = [re.sub("<.*?>", "", x).replace("\xa0", "").strip()
             for x in re.findall(r"<td.*?>(.*?)</td>", row, re.S)]
        if len(c) >= 13 and c[3] in ("buy", "sell") and c[4] == "out":
            pnl.append(float(c[10].replace(" ", "")))
    lo = [x for x in pnl if x <= 0]
    wi = [x for x in pnl if x > 0]
    flat = re.sub(r"\s+", " ", re.sub("<.*?>", " ", h)).replace("\xa0", "")
    mb = re.search(r"Bars:\s*(\d+)", flat)
    mt = re.search(r"Ticks:\s*(\d+)", flat)
    return {
        "avg_loss": (sum(lo) / len(lo)) if lo else 0.0,
        "worst": min(pnl) if pnl else 0.0,
        "avg_win": (sum(wi) / len(wi)) if wi else 0.0,
        "n_loss": len(lo),
        "bars": int(mb.group(1)) if mb else 0,
        "ticks": int(mt.group(1)) if mt else 0,
    }


def measure(name: str, over: dict, frm: str, to: str, led: dict, redo: bool = False,
            deposit: int = 4123) -> dict | None:
    k = key_of(over, frm, to, deposit)
    if not redo and k in led:
        r = dict(led[k])
        r["name"] = name
        r["cached"] = True
        return r
    over = dict(CAMEL, **{kk: str(vv) for kk, vv in over.items()})
    t0 = datetime.now()
    stem = D.run(over, frm, to, deposit=deposit)
    st = D.stats(stem) if stem else None
    if not st:
        print("  %-34s NO TRADES / NO REPORT" % name[:34], flush=True)
        return None
    st.update(losses_from(stem))
    st["secs"] = (datetime.now() - t0).total_seconds()
    st["over"] = {kk: str(vv) for kk, vv in over.items()}
    st["window"] = [frm, to]
    st["deposit"] = deposit
    led[k] = st
    save_ledger(led)
    r = dict(st)
    r["name"] = name
    r["cached"] = False
    return r


def show(title: str, rows: list) -> None:
    print("\n" + "=" * 112)
    print(title)
    print("=" * 112)
    print("%-34s | %3s | %6s | %8s | %7s | %8s | %7s | %6s" %
          ("config", "WR", "trades", "net", "avgWin", "avgLoss", "worst", "maxDD"))
    print("-" * 112)
    for r in sorted([x for x in rows if x], key=lambda x: (-x["wr"], -x["net"])):
        print("%-34s | %2.0f%% | %6d | %+8.0f | %+7.2f | %+8.2f | %+7.0f | $%-5.0f%s" %
              (r["name"][:34], r["wr"], r["n"], r["net"], r["avg_win"], r["avg_loss"],
               r["worst"], r["dd"], "  (cached)" if r.get("cached") else ""))


LOCK = HERE / "_winrate.lock"


def take_lock() -> None:
    """ONE BATCH AT A TIME. Two batches share one rig, one _diamond_run.ini and one report
    folder, so each kill_rig() kills the other's terminal and both write NO REPORT - which
    reads exactly like "this config found no trades". That cost three configs on 2026-09-29,
    and it is the same failure the matcher had when three of them ran at once."""
    import os
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
        except Exception:
            pid = -1
        alive = False
        if pid > 0:
            import subprocess
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True,
                                 text=True).stdout
            alive = str(pid) in out
        if alive:
            raise SystemExit("[loop] REFUSING: batch already running as pid %d. "
                             "Stop it first, or delete %s if it is stale." % (pid, LOCK))
        print("[loop] clearing a stale lock from pid %s" % pid)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")


def main() -> None:
    take_lock()
    batch = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    frm, to = batch["window"]
    led = load_ledger()
    D.sync_ea()
    print("[loop] %s  window %s -> %s  ·  %d configs"
          % (batch.get("title", "batch"), frm, to, len(batch["configs"])), flush=True)
    rows = []
    for c in batch["configs"]:
        # A config may carry its OWN window. Out-of-sample validation needs the candidate AND
        # its control measured in one batch: if the unseen period is simply easy, the untouched
        # baseline wins there too, and without the control in the same table that is invisible.
        cf, ct = (c["window"] if "window" in c else [frm, to])
        r = measure(c["name"], c.get("over", {}), cf, ct, led,
                    redo=bool(c.get("redo", batch.get("redo"))),
                    deposit=int(batch.get("deposit", 4123)))
        if r:
            print("    %-34s WR %2.0f%%  net %+7.0f  n=%-4d  bars=%-6d %s"
                  % (r["name"][:34], r["wr"], r["net"], r["n"], r["bars"],
                     "cached" if r.get("cached") else "%.0fs" % r["secs"]), flush=True)
        rows.append(r)
    show(batch.get("title", "batch") + "   (MT5 real ticks, spread + 163ms delay)", rows)


if __name__ == "__main__":
    try:
        main()
    finally:
        LOCK.unlink(missing_ok=True)
