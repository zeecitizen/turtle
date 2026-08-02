"""autolearn.py — the system correcting itself, without waiting for a human.

Zee 2026-08-03: *"main nahi chahta ye software static ho… isko apni ghaltiyon se seekhna
chahiye… sirf ek learning system hi ensure kar sakta hai ke hum profitable hon."*

He is right about the principle and I owe him the limit as well: a night of trading is
perhaps ten to twenty fills. Nothing statistically real can be learned from twenty samples,
and pretending otherwise is exactly how six months were lost to confident backtests. So this
engine deliberately learns only the thing that IS learnable from small numbers:

    a mistake that has already been made, made again.

How it works
------------
Every closed trade is reduced to a SIGNATURE — the handful of facts that were true when it
was taken (side, whether it agreed with the trend Claude saw, how strong the setup was, what
the breakout body looked like, the hour). Signatures are cheap to compare.

When one signature has lost REPEATEDLY and won rarely, that is not statistics, it is a
pattern of behaviour — and it becomes a PROPOSED rule. Proposed rules do nothing. They only
become ACTIVE when they clear `MIN_LOSSES` repeats and a losing majority, and even then they
are written into the playbook marked as machine-derived so Claude weighs them below Zee's
own words.

Every active rule is re-scored continuously. One that stops earning its place is RETIRED
automatically. Nothing here is permanent except Zee's lessons, which this never touches.

What it cannot do
-----------------
It cannot manufacture an edge that is not there, and it will say so rather than invent one.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORE = REPO / "monitor" / "autolearn.json"

MIN_LOSSES = 3          # the same mistake three times is a habit, not chance
MAX_WIN_RATE = 0.34     # ... and it must be losing most of the time
REVIEW_AFTER = 6        # re-score an active rule once it has seen this many more trades


# ── signature ────────────────────────────────────────────────────────────────────────
def _bucket(v, edges, names):
    try:
        v = float(v)
    except Exception:
        return "unknown"
    for e, n in zip(edges, names):
        if v < e:
            return n
    return names[-1]


def signature(row, vision=None):
    """The few facts that were true when the trade was taken."""
    parts = [f"side={row.get('side', '?')}"]

    trend = (vision or {}).get("trend") or row.get("trend")
    if trend:
        agrees = ((trend == "up" and row.get("side") == "BUY")
                  or (trend == "down" and row.get("side") == "SELL"))
        parts.append("with_trend" if agrees else
                     ("against_trend" if trend in ("up", "down") else f"trend={trend}"))

    parts.append("strength=" + _bucket(row.get("strength"), [0.55, 0.7],
                                       ["low", "mid", "high"]))
    parts.append("body=" + _bucket(row.get("brk_body"), [0.6, 0.85],
                                   ["weak", "ok", "strong"]))
    h = (row.get("time") or "")[:2]
    if h.isdigit():
        parts.append("hour=" + ("asia" if int(h) < 7 else
                                "london" if int(h) < 13 else
                                "ny" if int(h) < 21 else "late"))
    return " · ".join(parts)


def _readable(sig):
    out = []
    for p in sig.split(" · "):
        if p.startswith("side="):
            out.append(p[5:] + "s")
        elif p == "against_trend":
            out.append("taken against the trend")
        elif p == "with_trend":
            out.append("taken with the trend")
        elif p.startswith("strength="):
            out.append(p[9:] + "-strength setups")
        elif p.startswith("body="):
            out.append("a " + p[5:] + " breakout body")
        elif p.startswith("hour="):
            out.append("during the " + p[5:].upper() + " session")
        else:
            out.append(p)
    return ", ".join(out)


# ── store ────────────────────────────────────────────────────────────────────────────
def load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {"rules": [], "history": {}, "cycles": 0, "last_run": None}


def save(d):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


# ── the cycle ────────────────────────────────────────────────────────────────────────
def run_cycle(market="XAU", write_rulebook=True):
    """Score every signature against real fills, propose, promote and retire.

    Returns a summary of what changed, so the caller can show it or stay silent."""
    import trade_book as TB
    st = load()
    st["cycles"] = st.get("cycles", 0) + 1
    st["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # every fill we have, across every day we know about
    fills = []
    days = set(TB.judged_days(market)) | set(TB.trading_days(market))
    for d in sorted(days):
        for r in TB.book(market, d):
            if r.get("usd") is not None and r.get("verdict") in ("TAKE", "(pre-Claude)"):
                fills.append(r)

    by_sig = defaultdict(list)
    for r in fills:
        by_sig[signature(r)].append(r)

    changes = {"proposed": [], "promoted": [], "retired": [], "fills": len(fills)}
    known = {r["signature"]: r for r in st["rules"]}

    for sig, rs in by_sig.items():
        losses = [r for r in rs if r["usd"] < 0]
        wins = [r for r in rs if r["usd"] > 0]
        net = sum(r["usd"] for r in rs)
        wr = len(wins) / len(rs) if rs else 0.0
        rec = known.get(sig)

        qualifies = len(losses) >= MIN_LOSSES and wr <= MAX_WIN_RATE and net < 0

        if rec is None:
            if len(losses) >= 2:            # watch it before believing it
                rec = {"signature": sig, "state": "watching",
                       "first_seen": st["last_run"], "rule": None}
                st["rules"].append(rec)
                known[sig] = rec
            else:
                continue

        rec.update({"trades": len(rs), "wins": len(wins), "losses": len(losses),
                    "net": round(net, 2), "win_rate": round(wr, 3),
                    "last_seen": st["last_run"]})

        if rec["state"] in ("watching", "proposed") and qualifies:
            rec["rule"] = (f"Do not take {_readable(sig)} — "
                           f"{len(losses)} losses against {len(wins)} wins, "
                           f"${net:+.2f} in total.")
            if rec["state"] != "proposed":
                rec["state"] = "proposed"
                changes["proposed"].append(rec)
            # promote only once it is unambiguous
            if len(losses) >= MIN_LOSSES + 1 and wr <= MAX_WIN_RATE:
                rec["state"] = "active"
                rec["activated"] = st["last_run"]
                rec["trades_at_activation"] = len(rs)
                changes["promoted"].append(rec)

        elif rec["state"] == "active":
            since = len(rs) - rec.get("trades_at_activation", len(rs))
            if since >= REVIEW_AFTER and (wr > MAX_WIN_RATE or net >= 0):
                rec["state"] = "retired"
                rec["retired"] = st["last_run"]
                rec["retired_because"] = (f"win rate recovered to {100 * wr:.0f}% "
                                          f"and net is now ${net:+.2f}")
                changes["retired"].append(rec)

    save(st)
    if write_rulebook and (changes["promoted"] or changes["retired"]):
        _sync_rulebook(st)
    return changes


MARK = "## MACHINE-DERIVED RULES (auto, provisional)"


def _sync_rulebook(st):
    """Keep a single auto-maintained block in the playbook. Zee's own lessons are in a
    different section and are never touched by this."""
    import lessons as L
    rb = L.rulebook_path()
    txt = rb.read_text(encoding="utf-8", errors="replace") if rb.exists() else ""
    active = [r for r in st["rules"] if r["state"] == "active" and r.get("rule")]

    block = [MARK, "",
             "Derived automatically from real fills, and rewritten on every learning cycle.",
             "These are PROVISIONAL: they exist because the same mistake repeated, not",
             "because anything was proven. Zee's own lessons above outrank every line here,",
             "and any rule that stops earning its place is removed by the machine itself.", ""]
    if active:
        for r in active:
            block.append(f"- {r['rule']}  _(auto, {r['losses']}L/{r['wins']}W, "
                         f"${r['net']:+.2f})_")
    else:
        block.append("- *(nothing has repeated often enough yet — this is normal early on)*")
    block.append("")
    new = "\n".join(block)

    if MARK in txt:
        head, _, rest = txt.partition(MARK)
        after = rest.split("\n## ", 1)
        tail = ("\n## " + after[1]) if len(after) > 1 else ""
        txt = head + new + tail
    else:
        txt = txt.rstrip() + "\n\n---\n\n" + new
    rb.write_text(txt, encoding="utf-8")


def status():
    st = load()
    rules = st.get("rules", [])
    by = defaultdict(list)
    for r in rules:
        by[r["state"]].append(r)
    return {"cycles": st.get("cycles", 0), "last_run": st.get("last_run"),
            "watching": len(by["watching"]), "proposed": len(by["proposed"]),
            "active": len(by["active"]), "retired": len(by["retired"]),
            "rules": rules}


def to_text(market="XAU"):
    st = status()
    out = ["CONTINUOUS LEARNING", "=" * 72, ""]
    out.append(f"cycles run: {st['cycles']}    last: {st['last_run'] or 'never'}")
    out.append(f"watching {st['watching']}   ·   proposed {st['proposed']}   ·   "
               f"ACTIVE {st['active']}   ·   retired {st['retired']}")
    out.append("")
    if not st["rules"]:
        out += ["Nothing learned yet.", "",
                "That is the correct state after a handful of trades. This engine only acts",
                "when the SAME mistake repeats at least three times and keeps losing — which",
                "is the one thing a small sample can honestly show. It will not invent a",
                "pattern to look busy."]
        return "\n".join(out)

    for state, title in (("active", "ACTIVE — Claude is bound by these"),
                         ("proposed", "PROPOSED — one more repeat and they activate"),
                         ("watching", "WATCHING — seen losing twice, not yet a pattern"),
                         ("retired", "RETIRED — stopped earning their place")):
        rs = [r for r in st["rules"] if r["state"] == state]
        if not rs:
            continue
        out += ["", title, "-" * len(title)]
        for r in sorted(rs, key=lambda x: x.get("net", 0)):
            out.append(f"  {r['losses']}L/{r['wins']}W  ${r.get('net', 0):+8.2f}   "
                       f"{r.get('rule') or _readable(r['signature'])}")
            if r.get("retired_because"):
                out.append(f"        retired: {r['retired_because']}")
    out += ["", "-" * 40,
            "Honest limit: this cannot create an edge that is not in the data. It removes",
            "repetition of known mistakes. Everything else still comes from Zee's eye."]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    mk = sys.argv[1].upper() if len(sys.argv) > 1 else "XAU"
    ch = run_cycle(mk)
    print(f"cycle done — {ch['fills']} fills, "
          f"{len(ch['proposed'])} proposed, {len(ch['promoted'])} promoted, "
          f"{len(ch['retired'])} retired\n")
    print(to_text(mk))
