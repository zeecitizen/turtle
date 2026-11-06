"""summarize.py - gathers every canary's output into out_summary.json (verdict per loss-cure setting + the evidence + non-look-ahead bugs)."""
import json, hashlib
from _common import *          # noqa: F401,F403


def J(name):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


tr, pr, at, tk, sp, rg, sc, hk, tg, pt = (J(x) for x in ("out_trace.json", "out_prep.json", "out_atr.json", "out_ticks.json", "out_sp_exact.json",
                                                          "out_rough.json", "out_side_checks.json", "out_harness_k.json", "out_side_tags.json",
                                                          "out_perturb.json"))
live = {f: hashlib.sha1(open(os.path.join(ROOT, f), "rb").read()).hexdigest() for f in ("uhv_filters.py", "uhv_engine.py")}
snap = {f: hashlib.sha1(open(os.path.join(HERE, "snapshot", f), "rb").read()).hexdigest() for f in ("uhv_filters.py", "uhv_engine.py")}
inst = tr["paths"]["instant (InpUhvEntry=1, the base)"]["per_setting"]
clo = tr["paths"]["candle close (InpUhvEntry=0)"]["per_setting"]
per = {}
for s, r in inst.items():
    per[s] = {"max_index_minus_k_instant": r["max_off"], "max_index_minus_k_close": clo[s]["max_off"], "trace_violations": r["violations"] + clo[s]["violations"],
              "flags": {**r["flags"], **clo[s]["flags"]}, "skips_instant": r["skips"], "skips_close": clo[s]["skips"],
              "perturb_changed": None if not pt else pt["main"]["changed"]["perturb"].get(s, 0),
              "trunc_changed": None if not pt else pt["main"]["changed"]["trunc"].get(s, 0)}
out = {"files_sha1_audited": snap, "files_sha1_live_now": live, "unchanged_since_audit": snap == live, "per_setting_trace": per,
       "trace_positive_control_violations": tr["positive_control_leaky_swings"]["violations"],
       "perturb": pt, "prep": pr, "atr": at, "ticks": tk, "sp_exact": sp, "rough": rg, "side_checks": sc, "harness_k": hk, "side_tags": tg}
json.dump(out, open(os.path.join(HERE, "out_summary.json"), "w"), indent=1, default=str)
print("unchanged since audit:", snap == live, live)
for s, r in per.items():
    print(f"{s:20s} viol {r['trace_violations']}  perturb {r['perturb_changed']}  trunc {r['trunc_changed']}  max(i-k) {r['max_index_minus_k_instant']}")
