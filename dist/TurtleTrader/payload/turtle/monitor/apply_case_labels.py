"""apply_case_labels.py — fold Zee's Correct/Wrong clicks back into the case DB.

Reads zee_labels.json (case_NNN -> "correct"/"wrong"), reconstructs the same
candidate setups build_case_review generated, computes the final verdict
(Claude's guess if "correct", flipped if "wrong"), and appends each confirmed
case to cases.json. Then reports the new DB size + leave-one-out accuracy.

Run after Zee finishes clicking:  py monitor/apply_case_labels.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5, detect_full
from case_engine import build_cases, extract_features, knn_verdict, CASES_FILE
import screener_canonical_uhv_m1 as S

LABELS = Path(__file__).parent / "setup_labels" / "zee_labels.json"
FROM_DAY, TO_DAY, MAX = 20, 9, 40


def main():
    seed = build_cases()
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {}
    all_csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))
    bars = build_m5(all_csvs[-FROM_DAY:-TO_DAY])
    setups = detect_full(bars)[:MAX]

    added = 0; agree = 0
    db = list(seed)
    for k, s in enumerate(setups, 1):
        lid = f"case_{k:03d}"
        v = (labels.get(lid) or {}).get("zee") or ""
        if not (v == "correct" or v.startswith("wrong")): continue
        is_correct = (v == "correct")
        why = v[6:].strip() if v.startswith("wrong:") else ""
        f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
        guess, near, conf = knn_verdict(f, seed, k=3, side=s["side"])
        final = ("valid" if guess else "invalid") if is_correct else ("invalid" if guess else "valid")
        agree += is_correct
        reason = (f"zee confirmed (claude guessed {'valid' if guess else 'invalid'})" if is_correct
                  else (why or f"zee: wrong (claude guessed {'valid' if guess else 'invalid'})"))
        db.append({"id": f"Z{k:03d}", "side": s["side"], "verdict": final,
                   "reason": reason, "source": "zee_confirmed", "features": f})
        added += 1

    CASES_FILE.write_text(json.dumps({"version": 2, "cases": db}, indent=2), encoding="utf-8")
    print(f"added {added} confirmed cases (Claude was right {agree}/{added}) -> DB now {len(db)} cases")

    # leave-one-out on the grown DB
    ok = 0
    for i, c in enumerate(db):
        rest = db[:i] + db[i+1:]
        valid, _, _ = knn_verdict(c["features"], rest, k=3)
        ok += (valid == (c["verdict"] == "valid"))
    print(f"leave-one-out case-match accuracy on grown DB: {ok}/{len(db)} ({100*ok/len(db):.0f}%)")


if __name__ == "__main__":
    main()
