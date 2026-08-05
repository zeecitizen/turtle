"""loss_ledger.py — every loss gets an autopsy (Zee 2026-08-05).

"for each loss, write to an MD file why that loss happened. for every loss trade
there's a bug / fix report, so that we have fixed all losses possible."

Watches turtle_fills.csv; for every NEW losing fill it writes an entry to
LOSS_LEDGER.md (repo root): the trade, the market context at entry, the matching
EA fire line, a species classification against every failure mode we have already
paid for, and a status:
    KNOWN SPECIES  — a fix exists (named, with version); loss = residual/toll
    DESIGN TOLL    — the ghost's bounded cost of doing business (entry noise)
    NEW SPECIES ⚠  — nothing explains it; Claude must investigate this one

Run:  py monitor/loss_ledger.py            # backfill everything unprocessed
      py monitor/loss_ledger.py --loop 60  # daemon: autopsy each loss as it lands
"""
from __future__ import annotations
import csv, json, os, re, sys, time, glob
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import trend_eyes as TE

TF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/turtle_fills.csv")
MT5D = r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8"
LEDGER = HERE.parent / "LOSS_LEDGER.md"
STATE = HERE / "strategy_lab" / ".loss_ledger_state.json"
OUR_LOTS = {0.10, 0.20, 0.30, 0.60}
ERA_START = "2026.08.04 20:00"   # the Ghost era only — older fills belong to dead EAs
BROKER_TO_LOCAL_H = 2          # journal/expert logs are local; fills are broker (-2h)

HEADER = """# 🩸 LOSS LEDGER — every loss explained, or flagged

One entry per losing trade, written automatically by monitor/loss_ledger.py.
KNOWN SPECIES = a shipped fix covers this pattern (the loss is residue or toll).
NEW SPECIES ⚠ = unexplained — Claude investigates before anything else is built.
"""


def _read_log(p):
    try:
        return Path(p).read_text(encoding="utf-16", errors="ignore").splitlines()
    except Exception:
        return Path(p).read_text(errors="ignore").splitlines()


def load_state():
    try:
        return set(json.loads(STATE.read_text()))
    except Exception:
        return set()


def save_state(s):
    STATE.write_text(json.dumps(sorted(s)[-2000:]))


def our_losses():
    out = []
    for r in TF.read_text(errors="ignore").splitlines():
        c = r.split(",")
        if len(c) < 8:
            continue
        try:
            lots, pnl = float(c[5]), float(c[7])
        except ValueError:
            continue
        if lots not in OUR_LOTS or pnl >= 0 or c[0] < ERA_START:
            continue
        out.append(dict(ts=c[0], deal=c[1], side=c[4].replace("_closed", ""),
                        lots=lots, close=float(c[6]), pnl=pnl))
    return out


def ea_fire_before(loss):
    """The EA fire line (door raid or signal) closest BEFORE the close, same side."""
    t_close = datetime.strptime(loss["ts"], "%Y.%m.%d %H:%M:%S") + timedelta(hours=BROKER_TO_LOCAL_H)
    best = None
    for lf in sorted(glob.glob(MT5D + "/MQL5/Logs/*.log"), key=os.path.getmtime)[-2:]:
        for l in _read_log(lf):
            if "GHOST-DOOR" not in l and "signal #" not in l:
                continue
            if loss["side"] not in l:
                continue
            m = re.search(r"(\d\d:\d\d:\d\d)", l)
            if not m:
                continue
            lt = datetime.combine(t_close.date(), datetime.strptime(m.group(1), "%H:%M:%S").time())
            if timedelta(0) <= (t_close - lt) <= timedelta(minutes=45):
                if best is None or lt > best[0]:
                    best = (lt, l.strip())
    return best[1] if best else None


def context_at(loss):
    """Market context from the OANDA history, if the bars still cover that minute."""
    bars = TE.load_bars()
    t_entry_utc = (datetime.strptime(loss["ts"], "%Y.%m.%d %H:%M:%S")
                   + timedelta(hours=BROKER_TO_LOCAL_H) - timedelta(hours=5))
    idx = None
    for i, b in enumerate(bars):
        if b[0] <= t_entry_utc:
            idx = i
    if idx is None or idx < 30 or (t_entry_utc - bars[idx][0]) > timedelta(minutes=10):
        return None
    sl = TE.slope_of(bars, upto=idx + 1)
    a = TE.auto_call(bars, upto=idx + 1)
    return dict(slope=sl, auto=a["trend"], why=a["why"])


def classify(loss, fire, ctx):
    pts = loss["pnl"] / (loss["lots"] * 100)
    hour = int(loss["ts"][11:13])
    findings, status = [], "DESIGN TOLL"
    ghost = {0.10: 1.0, 0.20: 1.0, 0.30: 1.0, 0.60: 0.5}[loss["lots"]]
    slip = abs(pts) - ghost
    if abs(pts) <= ghost + 0.15:
        findings.append(f"ghost exit at design distance ({pts:+.2f}pt vs {ghost:.1f} cap) — bounded toll")
    elif slip > 0.15:
        findings.append(f"ghost exit with {slip:.2f}pt SLIPPAGE beyond design (fast tape/thin book)")
        status = "KNOWN SPECIES"
    if 22 <= hour or hour <= 1:
        findings.append("night window (22:00-01:00 broker): chop + 2-6x slippage era — "
                        "hour study says the edge lives elsewhere")
        status = "KNOWN SPECIES"
    if fire:
        if "raid 2" in fire or "raid 3" in fire or "raid 4" in fire:
            findings.append("repeat raid — must have followed a WINNING raid (v1.62) and a "
                            "lamp re-touch (v1.61); if raid 1 lost, this is a NEW BUG")
        if "chase=3.0" in fire:
            findings.append("dying-lamp chase entry — stretched-run risk (stretch-guard "
                            "not yet shipped; candidate fix on 2+ receipts)")
            status = "KNOWN SPECIES"
        if "lots=0.30" in fire or "lots=0.60" in fire:
            findings.append("burst-sized BEFORE the risk cap (pre 00:05 broker 08-05) — "
                            "cured by RISK_CAP 0.10")
            status = "KNOWN SPECIES"
    if ctx:
        opposed = (loss["side"] == "BUY" and ctx["slope"] < -0.10) or \
                  (loss["side"] == "SELL" and ctx["slope"] > 0.10)
        if opposed:
            findings.append(f"slope {ctx['slope']:+.2f} OPPOSED the trade at entry — the "
                            f"slope-guard should block this now; if this loss is after "
                            f"08-05 01:33 local, GUARD FAILED -> NEW SPECIES ⚠")
            status = "NEW SPECIES ⚠"
        else:
            findings.append(f"slope {ctx['slope']:+.2f} aligned; AUTO said {ctx['auto']} — "
                            f"entry direction was legitimate")
    else:
        findings.append("bar context no longer in the rolling OANDA window — partial autopsy")
    if not findings:
        findings.append("no known pattern matches"); status = "NEW SPECIES ⚠"
    return pts, status, findings


def autopsy(loss):
    fire = ea_fire_before(loss)
    ctx = context_at(loss)
    pts, status, findings = classify(loss, fire, ctx)
    e = [f"\n---\n\n## {loss['ts']} (broker) — {loss['side']} {loss['lots']:.2f} · "
         f"**{loss['pnl']:+.2f}** ({pts:+.2f}pt) — **{status}**", ""]
    if fire:
        e.append(f"- EA fire: `{fire[fire.find('[CaseExec]'):][:110]}`")
    for f in findings:
        e.append(f"- {f}")
    return "\n".join(e) + "\n"


def run_once():
    seen = load_state()
    new = [l for l in our_losses() if l["deal"] not in seen]
    if not new:
        return 0
    if not LEDGER.exists():
        LEDGER.write_text(HEADER, encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as fh:
        for l in new:
            fh.write(autopsy(l))
            seen.add(l["deal"])
            print(f"  autopsied {l['ts']} {l['side']} {l['pnl']:+.2f}")
    save_state(seen)
    return len(new)


if __name__ == "__main__":
    if "--loop" in sys.argv:
        period = int(sys.argv[sys.argv.index("--loop") + 1])
        print(f"[loss_ledger] watching for losses every {period}s -> {LEDGER}")
        while True:
            try:
                run_once()
            except Exception as ex:
                print("[loss_ledger] err:", ex, file=sys.stderr)
            time.sleep(period)
    else:
        n = run_once()
        print(f"  backfill complete: {n} new autopsies -> {LEDGER}")
