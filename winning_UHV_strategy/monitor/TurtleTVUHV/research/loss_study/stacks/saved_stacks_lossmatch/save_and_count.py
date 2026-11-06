"""save_and_count.py - save the three loss-study stacks as Turtle TV saved settings and count which of the base's 172 losses each removes.

PYTHON TICK REPLAY = HYPOTHESIS, NOT PROMOTED (CLAUDE.md; monitor/doctrine.py). Only MT5's Strategy Tester or live fills promote.

  py save_and_count.py           simulate base + the 3 stacks (+ the Friday-cut reference), check every number against the stack
                                 reports, match losses, write results.json in this folder. Writes NOTHING to settings/saved.
  py save_and_count.py --write   the same, then (only if every check passed) writes the 3 saved settings with exclusive create,
                                 reads them back and re-simulates them.

Loss matching: a base loss is REMOVED by a stack when no real stack trade (rows[:,10]==0) has the same side with an entry within 3 s.
Comments (research/loss_study/final/claude_loss_comments.json) are matched to base losses by side + entry time within 3 s (entry_utc
parsed as UTC). Loss-free day = FX day (17:00 NY -> 17:00 NY) with >= 1 real trade and no trade with $ result < 0.
"Random" = the losses a random cut of the same size would remove: per loss, the share of the base's trades in that loss's half
(TRAIN / TEST) that the stack does not take.
"""
import calendar
import collections
import datetime as dt
import hashlib
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
for _p in (ROOT, r"C:/Users/zeesh/turtle/monitor"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np  # noqa: E402

import uhv_engine as U  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.join(ROOT, "settings", "saved")
BASE_FILE = os.path.join(SAVED, "2026-11-05 05-45-38.json")
COMMENTS = os.path.join(ROOT, "research", "loss_study", "final", "claude_loss_comments.json")
STACKS_DIR = os.path.join(ROOT, "research", "loss_study", "stacks")
SPLIT = 1782864000                      # 2026-07-01 00:00 UTC
NY = ZoneInfo("America/New_York")
TOL = 3.0
HASHED = ["uhv_engine.py", "uhv_filters.py", "uhv_diamond.py", "scan.py", "sim.py"]
EXPECT_BASE = (7631, 172, -25525.97)
BAD_NAME = '\\/:*?"<>|'

# the stacks exactly as the stack searches returned them (final_inputs), their reported numbers and the red-team verdicts
STACKS = [
    {"key": "winrate", "file": "2026-11-06 10-00-01",
     "objective": "max TRAIN win rate, >= 600 TRAIN trades (greedy, 8 steps)",
     "final_inputs": {"InpUhvFriCutNY": "10", "InpUhvDeepRet": "0.5", "InpUhvMaxHumps": "3", "InpUhvRunPips": "8", "InpUhvSpikeAtr": "2",
                      "InpUhvHtf5": "1", "InpUhvMaxGapPips": "0.3", "InpUhvBrokeHighs": "5"},
     "expect": {"all": (1374, 12, -448), "train": (610, 5, -63), "test": (764, 7, -385)},
     "name": "97.7% + WIN-RATE stack, 8 loss filters (TRAIN-chosen) - ALL 99.13% TEST 99.08% (base TEST 98.60%) - red team OVERFIT, Python only",
     "redteam": "survives=false: overfit. TEST loss rate 0.92% vs base 1.40% is not clearly lower (random thinning P 0.14, per-day P 0.08, "
                "FX-day bootstrap CI 0.29-1.09); one-grid-step neighbours collapse TRAIN; only step 1 (FriCutNY 10) holds on TEST (P 0.003)."},
    {"key": "cleandays", "file": "2026-11-06 10-00-02",
     "objective": "max TRAIN share of loss-free FX days, >= 400 TRAIN trades and >= 59 TRAIN days (greedy)",
     "final_inputs": {"InpUhvMinHumps": "4", "InpUhvMinTicks": "40", "InpUhvFreshBreak": "8", "InpUhvMaxGapPips": "0.5"},
     "expect": {"all": (828, 14, -1862), "train": (405, 9, -1350), "test": (423, 5, -512)},
     "name": "97.7% + CLEAN-DAYS stack, 4 loss filters (TRAIN-chosen) - ALL 98.31% TEST 98.82% (base TEST 98.60%) - red team OVERFIT, Python only",
     "redteam": "survives=false: overfit. TEST loss rate 1.18% vs base 1.40% (P 0.46); base trades it kept lost at 1.46%, the ones it removed "
                "at 1.39% - no skill at picking trades; a random skip inside the engine matches its loss-free share 47% of the time."},
    {"key": "net", "file": "2026-11-06 10-00-03",
     "objective": "max TRAIN net $, each step +0.05 WR pt and +$200, >= 600 TRAIN trades (greedy)",
     "final_inputs": {"InpUhvSRPips": "5", "InpUhvDeepRet": "0.8", "InpUhvFreshBreak": "1", "InpUhvNoClose": "true", "InpUhvFriCutNY": "15",
                      "InpUhvLoudBrk": "0.95"},
     "expect": {"all": (1006, 20, -2754), "train": (601, 13, -1829), "test": (405, 7, -925)},
     "name": "97.7% + NET stack, 6 loss filters (TRAIN-chosen) - ALL 98.01% TEST 98.27% (WORSE than base TEST 98.60%) - red team OVERFIT, Python only",
     "redteam": "survives=false: overfit. TEST loss rate went UP, 1.73% vs base 1.40% (P 0.79); $ per trade worse (-2.28 vs -1.26); worse than "
                "skipping setups at random on loss rate, $ per trade and loss-free days."},
]
REFERENCES = [{"key": "fricut10_only", "final_inputs": {"InpUhvFriCutNY": "10"},
               "why": "step 1 of the win-rate stack alone: the only cure TEST supports (lift ~2.6-2.7 on both halves, TEST P 0.003)"}]

# FX days (17:00 NY -> 17:00 NY): boundary i = 17:00 NY on _d0 + i days (DST-correct through zoneinfo), labelled by the closing date
_d0 = dt.date(2026, 2, 20)
_BOUNDS = np.asarray([dt.datetime.combine(_d0 + dt.timedelta(days=i), dt.time(17, 0), tzinfo=NY).timestamp() for i in range(300)])


def fxday(ts):
    return np.searchsorted(_BOUNDS, np.asarray(ts, dtype=float), side="right") - 1


def sha1(p):
    with open(os.path.join(ROOT, p), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def base_full_inputs():
    d = {k: v[0] for k, v in U.UHV_DEFAULTS.items()}
    with open(BASE_FILE, encoding="utf-8") as f:
        d.update(json.load(f)["inputs"])
    return d


def real(rows):
    return rows[rows[:, 10] == 0] if len(rows) else np.zeros((0, 20))


def score(r):
    t, pnl = r[:, 1], r[:, 6]
    loss = pnl < 0
    day = fxday(t)
    out = {}
    for part, m in (("train", t < SPLIT), ("test", t >= SPLIT), ("all", np.ones(len(t), bool))):
        n, L = int(m.sum()), int(loss[m].sum())
        days, ldays = np.unique(day[m]), np.unique(day[m & loss])
        out[part] = {"n": n, "L": L, "wr": round(100.0 * (n - L) / n, 2) if n else 0.0, "net": round(float(pnl[m].sum()), 2),
                     "traded_days": int(len(days)), "loss_days": int(len(ldays)), "loss_free_days": int(len(days) - len(ldays)),
                     "loss_rate_pct": round(100.0 * L / n, 3) if n else 0.0}
    return out


def fmt(h, base_days):
    return (f"{h['n']} trades / {h['L']} losses / WR {h['wr']:.2f}% / loss-free days {h['loss_free_days']} of {h['traded_days']} traded "
            f"({h['loss_days']} days with a loss; base traded {base_days}) / net ${h['net']:,.0f}")


def nearest(ts_sorted, x):
    """index of the nearest value in a sorted array, and the gap"""
    if len(ts_sorted) == 0:
        return -1, 1e18
    i = int(np.searchsorted(ts_sorted, x))
    best, gap = -1, 1e18
    for j in (i - 1, i):
        if 0 <= j < len(ts_sorted) and abs(ts_sorted[j] - x) < gap:
            best, gap = j, abs(ts_sorted[j] - x)
    return best, gap


def match(a, b):
    """for each real trade in a: index into b of the same-side trade nearest in entry time within TOL (else -1), and the gap"""
    idx, gaps = np.full(len(a), -1), np.full(len(a), np.inf)
    for side in (1, -1):
        bi = np.where(b[:, 0] == side)[0]
        order = bi[np.argsort(b[bi, 1])]
        bt = b[order, 1]
        for ia in np.where(a[:, 0] == side)[0]:
            j, g = nearest(bt, a[ia, 1])
            if j >= 0 and g <= TOL:
                idx[ia], gaps[ia] = order[j], g
    return idx, gaps


def utc_ts(s):
    return calendar.timegm(dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timetuple())


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main(write=False):
    h0 = {p: sha1(p) for p in HASHED}
    with open(COMMENTS, encoding="utf-8") as f:
        comments = json.load(f)
    base_in = base_full_inputs()
    B = real(U.simulate(base_in)[0])
    bs = score(B)
    got = (bs["all"]["n"], bs["all"]["L"], round(bs["all"]["net"], 2))
    assert got == EXPECT_BASE, f"base does not reproduce: {got} vs {EXPECT_BASE}"
    base_days = {p: bs[p]["traded_days"] for p in ("train", "test", "all")}
    print("BASE")
    for part in ("all", "train", "test"):
        print(f"  {part.upper():5s} {fmt(bs[part], base_days[part])}")

    # ---- base losses <-> the 172 comments (side + entry within 3 s, one-to-one)
    bl = np.where(B[:, 6] < 0)[0]
    assert len(bl) == 172
    used, cause_of, gaps = set(), {}, []
    for ib in bl:
        side = "BUY" if B[ib, 0] > 0 else "SELL"
        cands = [c for c in comments if c["side"] == side and abs(utc_ts(c["entry_utc"]) - B[ib, 1]) <= TOL]
        assert len(cands) == 1, f"base loss at {iso(B[ib, 1])} {side}: {len(cands)} comment matches"
        assert cands[0]["id"] not in used, f"comment {cands[0]['id']} matched twice"
        used.add(cands[0]["id"])
        cause_of[int(ib)] = cands[0]
        gaps.append(abs(utc_ts(cands[0]["entry_utc"]) - B[ib, 1]))
    assert len(used) == 172
    cause_n = collections.Counter(c["cause_class"] for c in cause_of.values())
    print(f"comment match: 172 of 172 base losses, one-to-one (max gap {max(gaps):.2f} s);", dict(cause_n))

    results = {"doctrine": "PYTHON TICK REPLAY = HYPOTHESIS, NOT PROMOTED. MT5 or live fills promote.", "hashes_start": h0,
               "base": {"file": BASE_FILE.replace("\\", "/"), "score": bs}, "cause_totals": dict(cause_n), "stacks": [], "references": []}

    def analyse(entry, is_stack):
        inp = dict(base_in)
        inp.update(entry["final_inputs"])
        R = real(U.simulate(inp)[0])
        sc = score(R)
        bi_idx, bi_gap = match(B, R)                              # base trades -> stack trades
        removed = bi_idx < 0
        half_train = B[:, 1] < SPLIT
        rem_rate = {"train": float(removed[half_train].mean()), "test": float(removed[~half_train].mean()), "all": float(removed.mean())}
        exact = int(((bi_gap == 0) & ~removed).sum())
        approx = int(((bi_gap > 0) & ~removed).sum())
        by = collections.defaultdict(lambda: {"losses": 0, "removed": 0, "still_lost": 0, "turned_winner": 0, "expected_if_random": 0.0})
        byh = {h: collections.defaultdict(lambda: {"losses": 0, "removed": 0, "expected_if_random": 0.0}) for h in ("train", "test")}
        removed_ids, kept_ids, turned = [], [], []
        for ib in bl:
            c = cause_of[int(ib)]
            cc = c["cause_class"]
            by[cc]["losses"] += 1
            hf = "train" if B[ib, 1] < SPLIT else "test"
            by[cc]["expected_if_random"] += rem_rate[hf]
            byh[hf][cc]["losses"] += 1
            byh[hf][cc]["expected_if_random"] += rem_rate[hf]
            byh[hf][cc]["removed"] += int(removed[ib])
            if removed[ib]:
                by[cc]["removed"] += 1
                removed_ids.append(c["id"])
            elif R[bi_idx[ib], 6] < 0:
                by[cc]["still_lost"] += 1
                kept_ids.append(c["id"])
            else:
                by[cc]["turned_winner"] += 1
                turned.append(c["id"])
        ri_idx, _ = match(R, B)                                   # stack losses that are not base losses
        new_free, new_from_winner = [], []
        for ir in np.where(R[:, 6] < 0)[0]:
            j = ri_idx[ir]
            rec = {"entry_utc": iso(R[ir, 1]), "side": "BUY" if R[ir, 0] > 0 else "SELL", "usd": round(float(R[ir, 6]), 2),
                   "half": "train" if R[ir, 1] < SPLIT else "test"}
            if j < 0:
                new_free.append(rec)
            elif B[j, 6] >= 0:
                new_from_winner.append(rec)
        n_rem = sum(v["removed"] for v in by.values())
        n_turn = sum(v["turned_winner"] for v in by.values())
        check = 172 - n_rem - n_turn + len(new_free) + len(new_from_winner)
        assert check == sc["all"]["L"], f"{entry['key']}: loss bookkeeping {check} != {sc['all']['L']}"
        bw = B[:, 6] >= 0
        out = {"key": entry["key"], "final_inputs": entry["final_inputs"], "score": sc,
               "base_trades_removed": {"all": int(removed.sum()), "of": len(B), "share_pct": round(100 * rem_rate["all"], 1),
                                       "train_share_pct": round(100 * rem_rate["train"], 1), "test_share_pct": round(100 * rem_rate["test"], 1)},
               "base_winners_removed": int((removed & bw).sum()), "base_losses_removed": n_rem,
               "base_losses_still_lost": sum(v["still_lost"] for v in by.values()), "base_losses_turned_winner": n_turn,
               "expected_removed_if_random": round(sum(v["expected_if_random"] for v in by.values()), 1),
               "new_losses_freed_slots": new_free, "new_losses_from_base_winners": new_from_winner,
               "stack_trades_not_in_base": int((ri_idx < 0).sum()),
               "match_exact": exact, "match_within_3s_not_exact": approx,
               "by_cause": {k: {**v, "expected_if_random": round(v["expected_if_random"], 1)}
                            for k, v in sorted(by.items(), key=lambda kv: -kv[1]["losses"])},
               "remaining_base_losses": kept_ids, "removed_base_losses": removed_ids, "turned_winner_ids": turned}
        out["by_half"] = {}
        for hf in ("train", "test"):
            d = byh[hf]
            out["by_half"][hf] = {"base_losses": sum(v["losses"] for v in d.values()), "removed": sum(v["removed"] for v in d.values()),
                                  "expected_if_random": round(sum(v["expected_if_random"] for v in d.values()), 1),
                                  "new_losses": sum(1 for x in new_free + new_from_winner if x["half"] == hf),
                                  "by_cause": {k: {**v, "expected_if_random": round(v["expected_if_random"], 1)} for k, v in d.items()}}
        if is_stack:
            ex = entry["expect"]
            for part in ("all", "train", "test"):
                h = sc[part]
                assert (h["n"], h["L"]) == ex[part][:2] and abs(h["net"] - ex[part][2]) < 1.0, \
                    f"{entry['key']} {part}: {(h['n'], h['L'], h['net'])} vs reported {ex[part]}"
            with open(os.path.join(STACKS_DIR, entry["key"], "final_setting.json"), encoding="utf-8") as f:
                fs = json.load(f)["inputs"]                       # the stack's own final_setting.json must say the same thing
            diff = {k: v for k, v in fs.items() if str(base_in.get(k)) != str(v)}
            assert diff == entry["final_inputs"], f"{entry['key']}: final_setting.json differs from final_inputs: {diff}"
            out["inputs_full"] = inp
        return out

    for st in STACKS:
        o = analyse(st, True)
        o.update({k: st[k] for k in ("file", "objective", "name", "redteam")})
        results["stacks"].append(o)
    for rf in REFERENCES:
        o = analyse(rf, False)
        o["why"] = rf["why"]
        results["references"].append(o)

    for o in results["stacks"] + results["references"]:
        sc = o["score"]
        print(f"\n== {o['key']}  {o['final_inputs']}")
        for part in ("all", "train", "test"):
            print(f"  {part.upper():5s} {fmt(sc[part], base_days[part])}")
        bt = o["base_trades_removed"]
        print(f"  base trades removed {bt['all']} of {len(B)} ({bt['share_pct']}%; TRAIN {bt['train_share_pct']}%, TEST {bt['test_share_pct']}%), "
              f"base winners removed {o['base_winners_removed']}; stack trades the base never took {o['stack_trades_not_in_base']}")
        print(f"  base losses removed {o['base_losses_removed']} of 172 (a random cut of the same size: {o['expected_removed_if_random']}), "
              f"still lost {o['base_losses_still_lost']}, turned winner {o['base_losses_turned_winner']}, new losses "
              f"{len(o['new_losses_freed_slots'])} freed-slot + {len(o['new_losses_from_base_winners'])} from base winners; "
              f"matches exact {o['match_exact']}, within 3 s not exact {o['match_within_3s_not_exact']}")
        for k, v in o["by_cause"].items():
            print(f"     {k:22s} {v['removed']:3d} of {v['losses']:3d} removed (random cut: {v['expected_if_random']:5.1f})  still lost {v['still_lost']}")
        for hf in ("train", "test"):
            q = o["by_half"][hf]
            print(f"  {hf.upper():5s} base losses removed {q['removed']} of {q['base_losses']} (random cut: {q['expected_if_random']}), "
                  f"new losses {q['new_losses']} -> " + ", ".join(f"{k} {v['removed']}/{v['losses']} (rnd {v['expected_if_random']:.1f})"
                                                              for k, v in sorted(q["by_cause"].items(), key=lambda kv: -kv[1]["losses"])))
        if o["new_losses_freed_slots"]:
            print("  new freed-slot losses:", o["new_losses_freed_slots"])

    h1 = {p: sha1(p) for p in HASHED}
    assert h0 == h1, f"engine files changed during the run: {h0} -> {h1}"
    results["hashes_end"] = h1

    try:
        import doctrine
        print()
        for o in results["stacks"]:
            doctrine.python_says(f"{o['key']} stack, ALL (haircut measured on another engine/instrument)", o["score"]["all"]["wr"], need_pct=99.3)
    except Exception as e:  # noqa: BLE001
        print("doctrine print failed:", e)

    if write:
        with open(BASE_FILE, encoding="utf-8") as f:
            base = json.load(f)
        written = []
        for o in results["stacks"]:
            rec = json.loads(json.dumps(base))
            rec.pop("result", None)
            rec["name"] = o["name"]
            assert len(rec["name"]) <= 150 and not any(ch in rec["name"] for ch in BAD_NAME), rec["name"]
            rec["inputs"] = o["inputs_full"]
            rec["changed"] = {**base["changed"], **o["final_inputs"]}
            rec["source"] = {"kind": "loss_study_stack", "objective": o["objective"], "promoted": False, "train_until_utc": SPLIT,
                             "redteam": o["redteam"], "stack_folder": os.path.join(STACKS_DIR, o["key"]).replace("\\", "/"),
                             "made_by": os.path.abspath(__file__).replace("\\", "/"),
                             "note": "Python tick replay (Turtle TV UHV) = hypothesis, NOT promoted. Only MT5 or live fills promote."}
            path = os.path.join(SAVED, o["file"] + ".json")
            with open(path, "x", encoding="utf-8") as f:          # exclusive create: never overwrite anything
                json.dump(rec, f, indent=1)
            written.append(path.replace("\\", "/"))
        for o, path in zip(results["stacks"], written):           # read back + re-simulate: the files must reproduce the stacks exactly
            with open(path, encoding="utf-8") as f:
                rb = json.load(f)
            inp = {k: v[0] for k, v in U.UHV_DEFAULTS.items()}
            inp.update(rb["inputs"])
            sc = score(real(U.simulate(inp)[0]))
            assert all((sc[p]["n"], sc[p]["L"], sc[p]["net"]) == (o["score"][p]["n"], o["score"][p]["L"], o["score"][p]["net"])
                       for p in ("all", "train", "test")), f"{path} does not reproduce"
            o["saved_file"] = path
            print("written + re-simulated OK:", path)
        results["written"] = written
    for o in results["stacks"]:
        o.pop("inputs_full", None)
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("\nresults ->", os.path.join(HERE, "results.json").replace("\\", "/"))


if __name__ == "__main__":
    main(write="--write" in sys.argv)
