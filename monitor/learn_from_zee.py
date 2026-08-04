"""learn_from_zee.py — supervised learning where the labels are Zee's own eyes.

Zee 2026-08-03: *"meri eyes setups pe train hui hain. Bas yahi farq hai. Aap bhi training
karo — supervised, unsupervised, jaisi bhi. Magar aapka neural network meri jaisi trades kar
sakta hai."*

He is right that this is a learning problem, and right about where the labels come from. He
has written 147 comments on rendered setups — not scores, sentences: *"invalid setup because
the UHV is not a valid UHV"*, *"a valid retracement starts when a red candle breaks the high
of the previous green candle"*. Those sentences are the training signal. The features are the
numbers the detector already computes for the same setups.

Two questions this answers, both with the data rather than with an opinion:

  1. Does Zee's verdict predict the OUTCOME better than the machine's own numbers do? If his
     eye adds nothing over uhv_vol and the rest, there is nothing to learn from him and the
     honest thing is to say so.
  2. Which measurable feature separates the setups he approved from the ones he rejected? A
     rule I can state in numbers is a rule the detector can enforce at 3am without him.

Small data is treated as small: with tens of labels, not hundreds, every split is reported
with its count and nothing is called a rule below MIN_N.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

LAB = Path(__file__).resolve().parent / "setup_labels"
MIN_N = 5          # below this a difference is an anecdote, not a finding

APPROVE = re.compile(r"\b(valid setup|correct|good|perfect|nice|yes|agreed)\b", re.I)
REJECT = re.compile(r"\b(invalid|not correct|not a valid|not valid|wrong|shouldn't|"
                    r"should not|don'?t understand|no setup)\b", re.I)


def verdict(text):
    """Zee wrote sentences, not scores. Read the sentence."""
    t = (text or "").strip()
    if not t:
        return None
    rej, app = bool(REJECT.search(t)), bool(APPROVE.search(t))
    if rej and not app:
        return "reject"
    if app and not rej:
        return "approve"
    return None                      # genuinely mixed — do not force it


def rows():
    """Join his comments to the setup features by index."""
    labels = json.loads((LAB / "zee_labels.json").read_text(encoding="utf-8"))
    meta = json.loads((LAB / "setups_meta.json").read_text(encoding="utf-8"))
    by_idx = {m["idx"]: m for m in meta}
    out = []
    for k, v in labels.items():
        if not str(k).isdigit():
            continue
        m = by_idx.get(int(k))
        if not m:
            continue                 # labelled in a batch whose features we no longer hold
        txt = (v or {}).get("zee") if isinstance(v, dict) else str(v)
        vd = verdict(txt)
        t = m.get("trade") or {}
        out.append({"idx": int(k), "zee": vd, "text": (txt or "").strip(),
                    "side": t.get("side"), "uhv_vol": t.get("uhv_vol"),
                    "uhv_shift": t.get("uhv_shift"), "outcome": t.get("outcome"),
                    "pnl": t.get("pnl_pts"),
                    "risk": (abs(t["entry"] - t["sl"]) if t.get("entry") and t.get("sl")
                             else None),
                    "reward": (abs(t["tp"] - t["entry"]) if t.get("entry") and t.get("tp")
                               else None)})
    return out


def does_his_eye_help(rs):
    """Question 1: on the setups he judged, did his verdict track the money?"""
    judged = [r for r in rs if r["zee"] and r["outcome"]]
    if len(judged) < MIN_N:
        return {"n": len(judged), "verdict": "too few labelled setups to say"}
    app = [r for r in judged if r["zee"] == "approve"]
    rej = [r for r in judged if r["zee"] == "reject"]
    def wr(g):
        w = sum(1 for r in g if r["outcome"] == "WIN")
        return (w, len(g), (w / len(g) * 100) if g else 0.0)
    aw, an, ap = wr(app)
    rw, rn, rp = wr(rej)
    base_w, base_n, base_p = wr(judged)
    return {"n": len(judged),
            "approved": {"win": aw, "of": an, "wr": ap},
            "rejected": {"win": rw, "of": rn, "wr": rp},
            "all": {"win": base_w, "of": base_n, "wr": base_p},
            "edge_pts": ap - rp,
            "thin": an < MIN_N or rn < MIN_N}


def what_he_objects_to(rs):
    """Question 2, part one: name the objection in his own vocabulary."""
    from collections import Counter
    c = Counter()
    for r in rs:
        if r["zee"] != "reject":
            continue
        t = r["text"].lower()
        for name, pat in (("the UHV itself", "uhv"),
                          ("the retracement", "retracement"),
                          ("the breakout candle", "breakout"),
                          ("volume", "volume"),
                          ("the candle body", "body"),
                          ("the trend", "trend")):
            if pat in t:
                c[name] += 1
    return c.most_common()


def numeric_split(rs):
    """Question 2, part two: does any number separate approve from reject?"""
    out = []
    for feat in ("uhv_vol", "uhv_shift", "risk", "reward"):
        app = [r[feat] for r in rs if r["zee"] == "approve" and r.get(feat) is not None]
        rej = [r[feat] for r in rs if r["zee"] == "reject" and r.get(feat) is not None]
        if len(app) < MIN_N or len(rej) < MIN_N:
            out.append({"feature": feat, "n_app": len(app), "n_rej": len(rej),
                        "note": "thin sample — not a rule"})
            continue
        a, r = sum(app) / len(app), sum(rej) / len(rej)
        out.append({"feature": feat, "n_app": len(app), "n_rej": len(rej),
                    "approved_avg": round(a, 2), "rejected_avg": round(r, 2),
                    "gap": round(a - r, 2)})
    return out


def report():
    rs = rows()
    lines = ["ZEE KI AANKH SE SEEKHNA", "=" * 62, ""]
    lines.append(f"  {len(rs)} labelled setups jinke features bhi maujood hain")
    lines.append(f"  approve {sum(1 for r in rs if r['zee']=='approve')} · "
                 f"reject {sum(1 for r in rs if r['zee']=='reject')} · "
                 f"mila-jula {sum(1 for r in rs if not r['zee'])}")
    lines.append("")

    h = does_his_eye_help(rs)
    lines.append("1. KYA ZEE KA FAISLA PAISE SE MEL KHATA HAI?")
    lines.append("-" * 62)
    if h.get("verdict"):
        lines.append(f"   {h['verdict']} (n={h['n']})")
    else:
        a, r, al = h["approved"], h["rejected"], h["all"]
        lines.append(f"   us ne SAHI kaha  : {a['win']}/{a['of']} jeete  ({a['wr']:.0f}%)")
        lines.append(f"   us ne GHALAT kaha: {r['win']}/{r['of']} jeete  ({r['wr']:.0f}%)")
        lines.append(f"   sab mila kar     : {al['win']}/{al['of']} jeete ({al['wr']:.0f}%)")
        lines.append(f"   farq: {h['edge_pts']:+.0f} points"
                     + ("   [thin sample — abhi rule nahi]" if h["thin"] else ""))
    lines.append("")

    lines.append("2. WOH KIS CHEEZ PE AITRAZ KARTA HAI")
    lines.append("-" * 62)
    for name, n in what_he_objects_to(rs):
        lines.append(f"   {name:<24} {n:>3} baar")
    lines.append("")

    lines.append("3. KYA KOI NUMBER US KE FAISLE KO ALAG KARTA HAI?")
    lines.append("-" * 62)
    for s in numeric_split(rs):
        if "note" in s:
            lines.append(f"   {s['feature']:<12} {s['note']} "
                         f"(approve {s['n_app']}, reject {s['n_rej']})")
        else:
            lines.append(f"   {s['feature']:<12} approve avg {s['approved_avg']:>9} · "
                         f"reject avg {s['rejected_avg']:>9} · farq {s['gap']:+.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
