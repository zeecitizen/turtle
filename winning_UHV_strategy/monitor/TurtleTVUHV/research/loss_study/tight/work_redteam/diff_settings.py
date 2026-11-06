import json, os, sys
D = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV/settings/saved"
names = ["2026-11-05 05-45-38", "2026-11-06 09-10-00", "2026-11-06 09-00-00", "2026-11-06 07-33-17",
         "2026-11-06 10-00-01", "2026-11-06 10-00-02", "2026-11-06 10-00-03", "2026-11-06 13-00-00", "2026-11-06 07-01-10", "2026-11-06 08-00-00", "2026-11-06 05-00-00"]
S = {}
for n in names:
    S[n] = json.load(open(os.path.join(D, n + ".json"), encoding="utf-8"))
ref = S["2026-11-06 07-33-17"]
print("keys in zee100:", list(ref.keys()))
for n in names:
    s = S[n]
    print("=====", n, "top keys:", [k for k in s.keys()])
    for k in s:
        if k != "inputs":
            v = s[k]
            txt = json.dumps(v)
            print("   ", k, ":", txt[:1500])
allk = set()
for n in names:
    allk |= set(S[n]["inputs"].keys())
print()
print("INPUT DIFFS (vs zee100 07-33-17):")
for k in sorted(allk):
    vals = [S[n]["inputs"].get(k, "<absent>") for n in names]
    if len(set(map(str, vals))) > 1:
        print(f"{k:28s}", " | ".join(f"{str(v):>8s}" for v in vals))
print("columns:", names)
