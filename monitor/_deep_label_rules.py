"""Deep-mine all 98 labels: extract every distinct rule master invokes that we
haven't yet mechanized. Group by rule category, show frequency + verbatim.
"""
import json, sys, re
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
p = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/setup_labels/zee_labels.json")
data = json.loads(p.read_text(encoding="utf-8"))

# Detailed pattern catalog — searches for ALL distinct phrasings
patterns = {
    # ─── Implemented in v2.95-v2.97 ───
    "trend_HHHL_required":           [r"hh ?hl", r"higher high.*higher low", r"lower high.*lower low", r"confirmed.*uptrend", r"confirmed.*downtrend"],
    "ranging_market_no_trade":       [r"ranging", r"sideways", r"don.t trade.*ranging"],
    "no_against_trend":              [r"can.?t (?:buy|sell) in", r"selling in.*uptrend", r"buying in.*downtrend", r"counter.?trend"],
    "uhv_must_be_largest":           [r"largest volume", r"lowest volume among", r"not.*largest", r"smaller than (?:previous|neighbor|its|next)"],
    "uhv_correct_color":             [r"not red", r"not green", r"should be (?:red|green)", r"green colored.*sell", r"red.*for.*buy"],
    "retracement_valid_origin":      [r"valid retracement", r"breaks.*high of.*previous", r"breaks.*low of.*previous", r"retracement.*begin"],
    "breakout_body_close":           [r"body.*close above", r"body.*close below", r"crossed by.*body", r"body.*not break", r"doesn.t break.*body"],
    "stale_breakout":                [r"too late", r"too far past", r"missed.*breakout", r"breakout was earlier", r"breakout was at"],
    "h1_bias_required":              [r"h1.*trend", r"weekly.*trend", r"higher.?timeframe.*bias"],
    "breakout_low_volume":           [r"low (?:er )?volume.*breakout", r"breakout.*low.*vol", r"volume.*higher than.*uhv", r"breakout.*should.*lower.*vol"],
    "breakout_momentum":             [r"momentum.*candle", r"large body.*candle", r"strong.*body.*break"],

    # ─── NEW potential rules not yet mechanized ───
    "strong_bodied_uhv":             [r"strong.*bodied uhv", r"weak.*body", r"weak.?bodied", r"indecision"],
    "rejection_wicks":               [r"strong.*(?:bottom|top) wick", r"long.*wick", r"rejection", r"failed.*push"],
    "session_window":                [r"time window", r"session", r"hours? (?:work|matters)", r"during.*open"],
    "sweep_depth":                   [r"sweep", r"liquidity", r"wick.*below.*uhv", r"wick.*above.*uhv"],
    "fvg_required":                  [r"fvg", r"fair value gap", r"imbalance"],
    "single_candle_retracement":     [r"single candle retracement", r"only.*candle.*retracement", r"standalone.*retracement"],
    "breakout_color_correct":        [r"breakout.*green.*buy", r"breakout.*red.*sell", r"green for.*buy", r"red for.*sell"],
    "uhv_just_after_retracement":    [r"uhv.*right after", r"first.*after", r"immediately after.*retracement"],
    "no_premature_breakout":         [r"breakout.*before.*uhv", r"already broken.*before"],
    "h1_or_higher_levels":           [r"daily.*peak", r"weekly.*peak", r"prior.*high", r"prior.*low"],
    "structure_break":               [r"broke.*last.*peak", r"broke.*last.*low", r"new (?:hh|ll|higher high|lower low)"],
    "buy_only_in_uptrend":           [r"buy only.*uptrend", r"only buy.*uptrend"],
    "sell_only_in_downtrend":        [r"sell only.*downtrend", r"only sell.*downtrend"],
    "data_quality_complaint":        [r"loss.*written.*wrongly", r"clearly moved.*direction", r"why.*loss", r"impossible.*loss"],
    "sl_buffer_needed":              [r"sl.*buffer", r"buffer.*sl", r"if.*buffer.*sl"],
    "missed_correct_breakout":       [r"correct breakout was at", r"breakout candle was the one"],
    "weak_trend_skip":               [r"weak.*trend", r"weak.*uptrend", r"weak.*downtrend"],
    "uhv_size_must_dominate":        [r"ultra high volume", r"uhv means.*high", r"clearly visible.*ultra"],
}

# Tally each pattern + collect verbatim phrases for examples
counts = defaultdict(int)
examples = defaultdict(list)
for k, v in data.items():
    if not isinstance(v, dict): continue
    text = (v.get("zee") or "").lower()
    if not text.strip(): continue
    for cat, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                counts[cat] += 1
                if len(examples[cat]) < 2:
                    # capture surrounding 80 chars
                    s = max(0, m.start() - 20); e = min(len(text), m.end() + 60)
                    examples[cat].append(f"#{k}: ...{text[s:e]}...")
                break

# Sort and print
print(f"=== Master's rules from 98 labels (frequency-ranked) ===\n")
sorted_rules = sorted(counts.items(), key=lambda x: -x[1])
implemented = {
    "trend_HHHL_required", "ranging_market_no_trade", "no_against_trend",
    "uhv_must_be_largest", "uhv_correct_color", "retracement_valid_origin",
    "breakout_body_close", "stale_breakout", "h1_bias_required",
    "breakout_low_volume", "breakout_momentum", "session_window",
    "sweep_depth", "strong_bodied_uhv",
}
for cat, n in sorted_rules:
    status = "✓ done" if cat in implemented else "✗ MISSING"
    print(f"  {status:<11s}  {cat:<32s}: {n:3d} setups")

print()
print("=== NEW RULES not yet in EA ===")
for cat, n in sorted_rules:
    if cat in implemented: continue
    if n == 0: continue
    print(f"\n  ▸ {cat} ({n} setups)")
    for ex in examples[cat]:
        print(f"      {ex}")
