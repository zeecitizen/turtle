"""funnel.py — why are we missing setups?

Zee 2026-08-03: *"jab main khud trading karta hoon hum 100 setups per day 1-min pe lete
hain. Magar jab EA trade karta hai woh rules ki wajah se sirf 1 ya 2 setups leta hai per
day. Ye button find out karwaye ke kyun valid setups ban bhi rahe hain phir bhi hum miss kar
rahe hain."*

The honest way to answer that is not to argue about it — it is to instrument the detector
and count how many candidates die at each gate. This walks the same loop `detect_full` walks
and records, bar by bar, exactly where each one was thrown away:

    every bar
      -> right colour to be a breakout
        -> a retracement origin exists within the lookback
          -> the trend gate lets it through
            -> the ranging gate lets it through
              -> a UHV exists in the retracement zone   (and if not: why not)
                -> this bar is the FIRST body-cross of that UHV
                  -> a setup
                    -> Claude's verdict

The biggest single drop is the answer. Everything else is commentary.
"""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MON = REPO / "monitor"
sys.path.insert(0, str(MON))
sys.path.insert(0, str(MON / "strategy_lab"))

STAGES = [
    ("bars", "candles examined"),
    ("colour", "right colour to be a breakout"),
    ("origin", "a retracement origin exists"),
    ("trend", "the trend gate lets it through"),
    ("ranging", "the ranging gate lets it through"),
    ("uhv", "a UHV exists in the retracement"),
    ("first", "this candle is the FIRST body-cross"),
]


def run_variant(market, allow_cross=1, peak_rule="strict", bars=None):
    """Re-run the detector with ONE rule relaxed, and count what that alone would give.

    This is the difference between a diagnosis and a recommendation: instead of saying
    "the first-body-cross rule is expensive", it says how many setups the 2nd cross would
    add, on this same data."""
    import claude_judge as J
    import build_entry_review_m5 as B
    if bars is None:
        bars = J.load_bars(J.MARKETS[market]["data"])
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5 * J.MARKETS[market]["k"]; B.TREND_DOM = 0.0
    n = len(bars)
    found = 0
    for i in range(3, n):
        b = bars[i]
        for side in ("BUY", "SELL"):
            if side == "BUY" and not b.is_bull: continue
            if side == "SELL" and not b.is_bear: continue
            o = next((j for j in range(i - 1, max(i - B.LB, 0), -1)
                      if B.is_origin(bars, j, side)), None)
            if o is None or not B.trend_ok(bars, o, side): continue
            rs = B.retr_zone_start(bars, o, side)
            best = None
            for k in range(rs, i):
                c = bars[k]
                if not (c.is_bear if side == "BUY" else c.is_bull): continue
                if peak_rule == "strict":
                    if k - 1 >= 0 and bars[k - 1].v >= c.v: continue
                    if k + 1 < n and bars[k + 1].v >= c.v: continue
                elif peak_rule == "prev_only":
                    if k - 1 >= 0 and bars[k - 1].v >= c.v: continue
                if best is None or c.v > bars[best].v: best = k
            if best is None: continue
            U = bars[best]
            lvl = U.h if side == "BUY" else U.l
            crosses = []
            for k in range(best + 1, i + 1):
                cc = bars[k]
                if side == "BUY" and cc.is_bull and cc.c > lvl: crosses.append(k)
                elif side == "SELL" and cc.is_bear and cc.c < lvl: crosses.append(k)
            if i in crosses[:allow_cross]:
                found += 1
    return found


def run(market="XAU", config=None, bars=None):
    """Count the drop-off at every gate. `config` overrides the detector constants so the
    same data can be re-run with the gates opened."""
    import claude_judge as J
    import build_entry_review_m5 as B

    if bars is None:
        bars = J.load_bars(J.MARKETS[market]["data"])
    if len(bars) < 20:
        raise RuntimeError(f"only {len(bars)} bars of {market} data")

    cfg = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0,
               TREND_MIN_HUMP=0.5 * J.MARKETS[market]["k"], TREND_DOM=0.0, LB=B.LB)
    cfg.update(config or {})
    for k, v in cfg.items():
        setattr(B, k, v)

    n = len(bars)
    count = Counter()
    uhv_fail = Counter()
    survivors = []

    for i in range(3, n):
        b = bars[i]
        count["bars"] += 1
        for side in ("BUY", "SELL"):
            if side == "BUY" and not b.is_bull:
                continue
            if side == "SELL" and not b.is_bear:
                continue
            count["colour"] += 1

            o = None
            for j in range(i - 1, max(i - B.LB, 0), -1):
                if B.is_origin(bars, j, side):
                    o = j
                    break
            if o is None:
                continue
            count["origin"] += 1

            if not B.trend_ok(bars, o, side):
                continue
            count["trend"] += 1

            if B.efficiency_ratio(bars, o) < B.ER_MIN:
                continue
            count["ranging"] += 1

            rs = B.retr_zone_start(bars, o, side)
            best = None
            saw_colour = saw_body = saw_peak = 0
            for k in range(rs, i):
                c = bars[k]
                if not (c.is_bear if side == "BUY" else c.is_bull):
                    continue
                saw_colour += 1
                if c.body_ratio < B.UHV_BODY_MIN:
                    saw_body += 1
                    continue
                if k - 1 >= 0 and bars[k - 1].v >= c.v:
                    continue
                if k + 1 < n and bars[k + 1].v >= c.v:
                    continue
                saw_peak += 1
                if best is None or c.v > bars[best].v:
                    best = k
            if best is None:
                if saw_colour == 0:
                    uhv_fail["no counter-trend candle in the retracement at all"] += 1
                elif saw_body and saw_body == saw_colour:
                    uhv_fail["every candidate failed the strong-body rule"] += 1
                elif saw_peak == 0:
                    uhv_fail["no candidate was a strict local volume peak"] += 1
                else:
                    uhv_fail["other"] += 1
                continue
            count["uhv"] += 1

            U = bars[best]
            lvl = U.h if side == "BUY" else U.l
            first = None
            for k in range(best + 1, i + 1):
                cc = bars[k]
                if side == "BUY" and cc.is_bull and cc.c > lvl:
                    first = k; break
                if side == "SELL" and cc.is_bear and cc.c < lvl:
                    first = k; break
            if first != i:
                continue
            count["first"] += 1
            survivors.append({"i": i, "side": side, "time": bars[i].t,
                              "entry": round(bars[i].c, 2)})

    span_min = max(1, int((bars[-1].t - bars[0].t).total_seconds() // 60))
    return {"market": market, "config": {k: v for k, v in cfg.items() if k != "LB"},
            "bars": n, "span_min": span_min,
            "from": bars[0].t.isoformat(timespec="minutes"),
            "to": bars[-1].t.isoformat(timespec="minutes"),
            "counts": dict(count), "uhv_fail": dict(uhv_fail),
            "setups": len(survivors), "per_hour": 60.0 * len(survivors) / span_min,
            "survivors": survivors[-12:]}


def _verdicts(market):
    """What Claude did with the setups that did survive."""
    f = MON / "claude_judgments.jsonl"
    took = skipped = 0
    why = Counter()
    if not f.exists():
        return took, skipped, why
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("market") != market:
            continue
        if d.get("verdict") == "TAKE":
            took += 1
        elif d.get("verdict") == "SKIP":
            skipped += 1
            r = (d.get("reason") or "").lower()
            for key, label in (("rang", "ranging / chop"),
                               ("chop", "ranging / chop"),
                               ("uptrend me sell", "counter-trend"),
                               ("khilaf", "counter-trend"),
                               ("counter-trend", "counter-trend"),
                               ("risk stack", "already in that trade"),
                               ("already", "already in that trade"),
                               ("uhv volume", "weak UHV"),
                               ("kamzor", "weak UHV / weak momentum"),
                               ("extended", "price already extended"),
                               ("resistance", "price at a level")):
                if key in r:
                    why[label] += 1
                    break
            else:
                why["other"] += 1
    return took, skipped, why


def diagnose(market="XAU"):
    """The full answer, including what happens when the gates are opened."""
    strict = run(market)
    # the same data with every optional gate wide open — the difference IS the cost of rules
    loose = run(market, config=dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0,
                                    TREND_MIN_HUMP=0.0, TREND_DOM=0.0))
    took, skipped, why = _verdicts(market)

    c = strict["counts"]
    steps = []
    prev = None
    for key, label in STAGES:
        v = c.get(key, 0)
        lost = None if prev is None else prev - v
        steps.append({"key": key, "label": label, "count": v, "lost": lost,
                      "pct_lost": (100.0 * lost / prev) if prev else None})
        prev = v

    # the single biggest killer
    worst = max((s for s in steps if s["lost"]), key=lambda s: s["lost"], default=None)

    findings = []
    if worst:
        findings.append(
            f"The biggest loss of candidates is at “{worst['label']}”: "
            f"{worst['lost']:,} of {worst['lost'] + worst['count']:,} died there "
            f"({worst['pct_lost']:.0f}%).")
    if strict["uhv_fail"]:
        top = max(strict["uhv_fail"].items(), key=lambda kv: kv[1])
        findings.append(f"When a UHV could not be found, the usual reason was: {top[0]} "
                        f"({top[1]:,} times).")
    gap = loose["setups"] - strict["setups"]
    if gap > 0:
        findings.append(
            f"Opening every optional gate would give {loose['setups']:,} setups instead of "
            f"{strict['setups']:,} over the same {strict['span_min']} minutes "
            f"({loose['per_hour']:.1f}/hour against {strict['per_hour']:.1f}/hour). "
            f"That difference is what the rules cost in frequency.")
    else:
        findings.append(
            "Opening the optional gates changes nothing here — the shortage is in the "
            "geometry itself, not in the filters. The UHV and first-cross requirements are "
            "doing the limiting.")
    if skipped:
        findings.append(
            f"Of the setups that did survive, Claude judged {took + skipped} and skipped "
            f"{skipped}. Most common reason: "
            + ", ".join(f"{k} ({v})" for k, v in why.most_common(3)) + ".")

    # ---- recommendations: what each relaxation would actually buy ----------------
    import claude_judge as J
    bars = J.load_bars(J.MARKETS[market]["data"])
    base = strict["setups"]
    recs = []
    try:
        for label, kw in (("allow the 2nd body-cross as well", dict(allow_cross=2)),
                          ("allow the first three body-crosses", dict(allow_cross=3)),
                          ("UHV only needs to beat the candle before it",
                           dict(peak_rule="prev_only")),
                          ("both: 2nd cross AND the looser UHV peak",
                           dict(allow_cross=2, peak_rule="prev_only"))):
            got = run_variant(market, bars=bars, **kw)
            if got > base:
                recs.append({"change": label, "setups": got, "base": base,
                             "gain": got - base,
                             "mult": got / base if base else 0.0,
                             "per_hour": 60.0 * got / strict["span_min"]})
    except Exception:
        pass
    d_recs = sorted(recs, key=lambda r: -r["gain"])

    findings.append(
        "Zee counts ~100 setups a day by eye. The detector's definition is much narrower: "
        "it demands a strict local volume peak AND that the entry candle be the very first "
        "body-cross of it. A human counts the move; the machine counts one exact candle.")

    return {"strict": strict, "loose": loose, "steps": steps, "worst": worst,
            "recommendations": d_recs,
            "verdicts": {"took": took, "skipped": skipped, "why": dict(why)},
            "findings": findings,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def to_text(d):
    s = d["strict"]
    out = [f"WHY ARE WE MISSING SETUPS?   {s['market']}",
           "=" * 72,
           f"{s['bars']:,} candles  ·  {s['from']} → {s['to']}  ·  {s['span_min']} minutes",
           ""]
    out.append("THE FUNNEL")
    for st in d["steps"]:
        line = f"  {st['count']:>8,}   {st['label']}"
        if st["lost"] is not None:
            line += f"      (-{st['lost']:,}, {st['pct_lost']:.0f}% lost here)"
        out.append(line)
    out += ["", f"  {s['setups']:>8,}   setups produced   ({s['per_hour']:.1f} per hour)", ""]
    if s["uhv_fail"]:
        out.append("WHY NO UHV WAS FOUND")
        for k, v in sorted(s["uhv_fail"].items(), key=lambda kv: -kv[1]):
            out.append(f"  {v:>8,}   {k}")
        out.append("")
    out += ["WITH EVERY OPTIONAL GATE OPEN",
            f"  {d['loose']['setups']:,} setups ({d['loose']['per_hour']:.1f}/hour) "
            f"against {s['setups']:,} ({s['per_hour']:.1f}/hour) now", ""]
    if d.get("recommendations"):
        out += ["WHAT WOULD ACTUALLY CHANGE IT  (measured on this same data)",
                f"  {'setups':>8} {'vs now':>8} {'per hour':>9}   relaxation"]
        for r in d["recommendations"]:
            out.append(f"  {r['setups']:>8,} {r['gain']:>+8,} {r['per_hour']:>9.1f}   "
                       f"{r['change']}")
        out += ["",
                "  None of these is safe until it is validated on P&L, not on count. More "
                "setups is not the goal; more PROFITABLE setups is.", ""]
    out += ["WHAT THIS MEANS", "-" * 40]
    for i, f in enumerate(d["findings"], 1):
        out.append(f"{i}. {f}")
    return "\n".join(out)


if __name__ == "__main__":
    mk = sys.argv[1].upper() if len(sys.argv) > 1 else "XAU"
    print(to_text(diagnose(mk)))
