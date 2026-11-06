"""match_causes.py - attach the loss study's cause label (../../final/claude_loss_comments.json) to each losing row of ../features.csv.
The comment ids are ENTRY-tick ids, features ids are DECISION-tick ids (same date + side, 0-3 s apart), so match by side + nearest time.
Output: causes_by_id.json {features_id: cause_class}. Outcome labels only - never a model input."""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
F = list(csv.DictReader(open(os.path.join(HERE, "..", "features.csv"), encoding="utf-8")))
C = json.load(open(os.path.join(HERE, "..", "..", "final", "claude_loss_comments.json"), encoding="utf-8"))

def secs(i):
    d, t, s = i.split("-")
    return (int(d[:2]) * 31 + int(d[2:])) * 86400 + int(t[:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:]), s

losses = [r for r in F if r["win"] == "0"]
used, out, gaps = set(), {}, []
for c in C:
    tc, sc = secs(c["id"])
    best = None
    for r in losses:
        tr, sr = secs(r["id"])
        if sr != sc or r["id"] in used:
            continue
        d = tc - tr
        if -2 <= d <= 30 and (best is None or abs(d) < abs(best[0])):
            best = (d, r["id"])
    if best is None:
        print("NO MATCH", c["id"]); continue
    used.add(best[1]); out[best[1]] = c["cause_class"]; gaps.append(best[0])
print(f"matched {len(out)} of {len(C)} comments to {len(losses)} losses; entry-decision gap s: min {min(gaps)} max {max(gaps)}")
print("unmatched losses:", [r["id"] for r in losses if r["id"] not in out])
json.dump(out, open(os.path.join(HERE, "causes_by_id.json"), "w"), indent=1)
