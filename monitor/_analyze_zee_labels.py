"""Analyze Zee's 98 labels to find what the EA is missing.

Goal: extract recurring reasons-for-invalidity, count them, and map each
to a specific gate in S1Trader.mq5.
"""
import json, sys, re
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/setup_labels/zee_labels.json")
data = json.loads(p.read_text(encoding="utf-8"))

# Patterns to detect — keywords that signal a specific rejection reason
patterns = {
    "uhv_not_largest_volume": [
        r"not larger than", r"not (?:the )?largest", r"smaller than",
        r"not (?:a )?(?:valid )?(?:U?HV|ultra high volume)", r"not (?:a )?(?:real )?uhv",
        r"vol(?:ume)? (?:is )?(?:not|smaller)", r"larger volume",
    ],
    "breakout_no_body_break": [
        r"(?:donot|does ?n[o']t|don.t) (?:at all )?break",
        r"not break.*body", r"body.*not break", r"no body break",
        r"not a (?:valid )?breakout",
    ],
    "no_retracement": [
        r"not (?:a )?(?:valid )?retracement",
        r"not inside (?:a )?(?:valid )?retracement",
        r"retracement.*invalid", r"invalid retracement",
        r"no retracement",
    ],
    "wrong_uhv_color": [
        r"wrong color", r"not green", r"not red",
        r"(?:should be|must be) (?:green|red)",
        r"green colored.*sell", r"red colored.*buy",
    ],
    "no_trend": [
        r"not (?:a )?(?:valid )?(?:down|up).?trend",
        r"no (?:up|down).?trend", r"trend (?:is )?(?:not|missing)",
        r"chop", r"ranging", r"range.bound", r"sideways",
        r"counter.?trend",
    ],
    "wick_only_break": [
        r"only.*wick", r"wick.*only", r"wick.*break",
        r"not.*body break", r"only.*shadow",
    ],
    "stale_setup": [
        r"too late", r"too far past", r"already moved", r"stale",
        r"too far from", r"past (?:the )?(?:UHV|breakout)",
    ],
    "wrong_breakout_candle": [
        r"wrong breakout", r"not (?:the )?(?:correct )?breakout",
        r"breakout candle (?:is )?(?:invalid|wrong)",
    ],
    "valid_setup": [
        r"^\s*(?:yes|valid|good|correct)", r"this is (?:a )?(?:valid|good|correct)",
        r"(?:looks|seems) (?:good|valid|correct)",
    ],
}

# Count per-label patterns
results = []
reason_counts = Counter()
verdict_counts = Counter()
for key, val in data.items():
    if not isinstance(val, dict): continue
    text = (val.get("zee") or "").lower()
    if not text.strip(): continue
    matched = []
    for reason, pats in patterns.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                matched.append(reason)
                reason_counts[reason] += 1
                break
    is_invalid = any(w in text for w in [
        "invalid", "not valid", "not correct", "wrong", "not at all",
        "donot", "doesn't", "doesnot", "isn't a", "not a uhv", "not a retracement"
    ])
    is_valid = any(text.strip().startswith(p) for p in ["yes", "valid", "correct", "good"]) or \
               ("looks good" in text or "looks valid" in text or "looks correct" in text or
                "this is a valid" in text or "this is correct" in text)
    if is_invalid and not is_valid:
        verdict = "INVALID"
    elif is_valid:
        verdict = "VALID"
    else:
        verdict = "UNCLEAR"
    verdict_counts[verdict] += 1
    results.append({"key": key, "verdict": verdict, "reasons": matched,
                    "preview": text[:120].replace("\n", " ")})

print(f"=== Zee's 98 labelled setups — analysis ===\n")
print(f"Total: {len(results)}")
print(f"Verdict breakdown:")
for v, c in verdict_counts.most_common():
    print(f"  {v:>10s}: {c} ({100*c/len(results):.0f}%)")
print()
print(f"Reasons mentioned across all labels (overlapping):")
for reason, c in reason_counts.most_common():
    print(f"  {reason:>28s}: {c:3d} setups ({100*c/len(results):.0f}%)")

# Show a few example invalid + valid setups
print()
print(f"=== Examples ===")
print("VALID setups:")
for r in results:
    if r["verdict"] == "VALID":
        print(f"  #{r['key']}: {r['preview']}")
print()
print("INVALID setups with reasons (first 10):")
for r in results[:30]:
    if r["verdict"] == "INVALID" and r["reasons"]:
        print(f"  #{r['key']}: reasons={r['reasons']}")
        print(f"     {r['preview']}")
