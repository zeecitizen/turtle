"""audit_leak.py - adversarial LOOK-AHEAD audit of rules_final.py (research/loss_study/final, 2026-11-06).

score_final.py's audit re-runs every rule with the per-bar arrays CUT at t["k"]. That proves a rule reads nothing after t["k"]; it cannot
prove that t["k"] itself, the setup fields, the clock field t["t_in"] or the precomputed hump table were known when the entry was DECIDED
(the breakout tick). This file checks those channels against the engine itself (uhv_engine._instant_setups on the setting's ticks) and
re-scores every rule leak-free with api.report:

  K      build.py sets k from the FILL minute: kb = minute(t_in), k = kb - 1, with t_in = the fill tick (>= 0.3 s after the breakout tick,
         seconds later on a thin tape). The engine's own filters read the candle before the BREAKOUT minute (s["bar"] - 60). When the fill
         lands in a later minute, t["k"] is the still-forming breakout minute - and t["camEff"] / t["camStk"] were read there too.
  SETUP  build.py matched each trade to the LAST setup (any side) whose breakout tick is <= the fill time; a setup that broke out inside the
         latency gap would be taken instead of the traded one. Here each trade is matched to the setup that reproduces its fill tick, fill
         price, stop distance and range box exactly (the engine's own geometry), and level / extreme / UHV / brk_* come from that setup.
  CLOCK  clock rules read t["t_in"] = the FILL time; the decision is the breakout tick (s["t"]).
  HUMPS  arrays.npz keeps each camel hump only in its LAST version, stamped with the bar of its last redraw (a lower low extends the same
         hump). humps_known(k) therefore DROPS a hump that existed at k whenever a lower low comes after k: future price decides what the rule
         sees. Here every version is replayed and humps_known(k) returns the latest version of each hump known by k.
  FILL   t["fill"] is the first tick 0.3 s AFTER the decision - a skip cannot read it. The leak-free analogue reads the decision tick.

Every *_lf rule below is the leak-free rewrite of its rules_final.py namesake. decision_by_id.csv (built on the first run from the ticks,
no outcome column) carries the decision-time fields. Run (Git Bash):
    cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV/research/loss_study/final && py audit_leak.py
Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md)."""
import contextlib
import csv
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(LS))
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules_final as R  # noqa: E402

A = api.A
T = api.TRADES
N = len(T)
PIP = 1e-4
SETTING = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
DEC_CSV = os.path.join(HERE, "decision_by_id.csv")
INP = json.load(open(SETTING, encoding="utf-8"))["inputs"]
LAT, BEYOND = float(INP["InpUhvLatency"]), float(INP["InpUhvSlBeyond"])
assert str(INP["InpUhvStopMode"]) == "1" and str(INP["InpUhvEntry"]) == "1" and float(INP.get("InpUhvPreBreak") or 0) == 0
COLS = ("id", "t_dec", "bar", "k_true", "n_cand", "build_match", "level", "extreme", "uhv_t", "ku", "uhv_v", "lo", "hi", "bv", "bc", "spr_pips")


def _fv(k, d):
    try:
        return float(INP.get(k, d))
    except (TypeError, ValueError):
        return float(d)


def _box(side, k, level):
    """the engine's range box (uhv_engine.simulate): where the break level sits in the last N closed candles' range, 21 boxes of 5%"""
    nb = int(_fv("InpRangeLook" if side > 0 else "InpRangeLookS", 7))
    hi_, lo_ = float(A.h[max(0, k - nb + 1):k + 1].max()), float(A.l[max(0, k - nb + 1):k + 1].min())
    pct = ((level - lo_) if side > 0 else (hi_ - level)) / (hi_ - lo_) if hi_ > lo_ else 0.5
    return min(20, max(0, int(pct * 20))) if pct <= 1.0 else 20


# ------------------------------------------------------------------------------------------ the decision-time table (built once from the ticks)
def build_decisions():
    sys.path.insert(0, ROOT)
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    import uhv_engine as U  # noqa: E402
    S, TK = U._setups(U.det_file(INP))
    S = U._instant_setups(TK, float(INP.get("InpUhvPreBreak") or 0), U.det_file(INP))
    st = np.array([s["t"] for s in S])
    assert np.all(np.diff(st) >= 0)
    TT, BB, AA = TK["t"], TK["bid"], TK["ask"]
    t1 = A.t
    rows, nst = [], {"no_cand": 0, "multi": 0, "mismatch": 0, "mismatch_side": 0}
    for t in T:
        tin, side, fill = float(t["t_in"]), int(t["side"]), float(t["fill"])
        jb = int(np.searchsorted(st, tin + 1e-6)) - 1                       # build.py's match (no side check there)
        cands = []
        for j in range(int(np.searchsorted(st, tin - 60.0)), jb + 1):
            s = S[j]
            if int(s["side"]) != side:
                continue
            j0 = int(np.searchsorted(TT, s["t"]))
            while j0 < len(TT) and TT[j0] - s["t"] < LAT:                   # the engine's fill: first tick >= LAT s after the breakout tick
                j0 += 1
            if j0 >= len(TT) or abs(TT[j0] - tin) > 1e-5:
                continue
            f0 = float(AA[j0] if side > 0 else BB[j0])
            if abs(f0 - fill) > 1e-9:
                continue
            sl_t = max(max((f0 - s["extreme"]) * side / PIP, 0.0) + BEYOND, 0.1)
            if abs(sl_t - t["stop_pips"]) > 0.06:
                continue
            k = int(np.searchsorted(t1, s["bar"] - 60))
            if k >= len(t1) or t1[k] != s["bar"] - 60 or _box(side, k, s["level"]) != t["box"]:
                continue
            cands.append(j)
        if not cands:
            nst["no_cand"] += 1
            j = jb
        else:
            nst["multi"] += len(cands) > 1
            j = cands[0]                                                    # the engine walks the setups in time order
        s = S[j]
        if j != jb:
            nst["mismatch"] += 1
            nst["mismatch_side"] += int(S[jb]["side"]) != side
        k = int(np.searchsorted(t1, s["bar"] - 60))
        i = int(np.searchsorted(TT, s["t"]))
        q = i
        while q < len(TT) and TT[q] == TT[i] and BB[q] != s["bc"]:          # the breakout tick (as build_trigger_spread.py)
            q += 1
        if q >= len(TT) or TT[q] != TT[i]:
            q = i
        ku = int(np.searchsorted(t1, s["uhv_t"]))
        rows.append((t["id"], repr(float(s["t"])), int(s["bar"]), k, len(cands), int(j == jb), repr(float(s["level"])), repr(float(s["extreme"])),
                     int(s["uhv_t"]), ku, float(A.v[ku]), repr(float(s["lo"])), repr(float(s["hi"])), int(s["bv"]), repr(float(s["bc"])),
                     repr(round(float(AA[q] - BB[q]) / PIP, 4))))
    with open(DEC_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    print(f"built {DEC_CSV}: {len(rows)} trades; setup match: {nst}")


if not os.path.exists(DEC_CSV):
    build_decisions()
DEC = {}
for r_ in csv.DictReader(open(DEC_CSV, encoding="utf-8")):
    DEC[r_["id"]] = {"t_dec": float(r_["t_dec"]), "bar": int(r_["bar"]), "k_true": int(r_["k_true"]), "n_cand": int(r_["n_cand"]),
                     "build_match": int(r_["build_match"]), "level": float(r_["level"]), "extreme": float(r_["extreme"]), "uhv_t": int(r_["uhv_t"]),
                     "ku": int(r_["ku"]), "uhv_v": float(r_["uhv_v"]), "lo": float(r_["lo"]), "hi": float(r_["hi"]), "bv": int(r_["bv"]),
                     "bc": float(r_["bc"]), "spr": float(r_["spr_pips"])}
assert len(DEC) == N


# ------------------------------------------------------------------------------------------ the camel humps, every version (causal)
def replay_camel():
    """build.py's camel loop, unchanged, but every hump version is kept with the bar it became known: (hump id, known bar, row)."""
    sys.path.insert(0, ROOT)
    import uhv_diamond  # noqa: E402
    h1, l1 = A.h, A.l
    n = len(h1)
    p = uhv_diamond.CAM_PIV
    camEff = np.zeros(n, dtype=np.int8)
    camStk = np.zeros(n, dtype=np.int16)
    T_, HB, HV, L0B, L0V, LB, LV, Tr, Stk, Stk0, Eff = 0, None, None, None, None, None, None, 0, 0, 0, 0
    final, vh, vk, vr = [], [], [], []
    for i in range(2 * p, n):
        c = i - p
        ph = all(not (h1[c] < h1[c + d] or h1[c] < h1[c - d]) for d in range(1, p + 1))
        pl = all(not (l1[c] > l1[c + d] or l1[c] > l1[c - d]) for d in range(1, p + 1))
        if ph:
            if T_ == 1:
                if h1[c] >= HV:
                    HB, HV = c, h1[c]
            else:
                Stk0 = Stk
                L0B, L0V, HB, HV, T_ = LB, LV, c, h1[c], 1
        if pl:
            redraw = False
            if T_ == 1:
                LB, LV, T_, redraw = c, l1[c], -1, True
            elif T_ == -1 and l1[c] <= LV:
                LB, LV, redraw = c, l1[c], True
            elif T_ == 0:
                LB, LV, T_ = c, l1[c], -1
            if redraw and HB is not None and L0B is not None:
                Tr = 1 if LV > L0V else -1 if LV < L0V else 0
                Stk = (max(Stk0, 0) + 1) if Tr == 1 else (min(Stk0, 0) - 1) if Tr == -1 else 0
                if abs(Stk) >= uhv_diamond.CAM_CONFIRM:
                    Eff = 1 if Stk > 0 else -1
                elif Tr == 0 and uhv_diamond.CAM_CONFIRM <= 1:
                    Eff = 0
                row = [L0B, float(L0V), HB, float(HV), LB, float(LV), Tr, i]
                if final and final[-1][2] == HB:
                    final[-1] = row
                else:
                    final.append(row)
                vh.append(len(final) - 1)
                vk.append(i)
                vr.append(row)
        camEff[i], camStk[i] = Eff, Stk
    return np.array(final, dtype=float), np.array(vh), np.array(vk), np.array(vr, dtype=float), camEff, camStk


H_FINAL, V_HID, V_KNOWN, V_ROWS, _ce, _cs = replay_camel()
assert np.array_equal(H_FINAL, A.humps), "camel replay does not reproduce arrays.npz humps"
assert np.array_equal(_ce, A.camEff) and np.array_equal(_cs, A.camStk), "camel replay does not reproduce camEff / camStk"
N_REDRAWN = int(len(V_HID) - len(H_FINAL))


def humps_known_causal(k):
    """every hump as it stood after bar k closed: the final version of each hump superseded by k + the latest version of the newest one"""
    m = int(np.searchsorted(V_KNOWN, k, side="right"))
    if m == 0:
        return H_FINAL[:0]
    hmax = int(V_HID[m - 1])
    return np.vstack([H_FINAL[:hmax], V_ROWS[m - 1][None, :]])


PER_BAR = ("t", "o", "h", "l", "c", "v", "atr", "adx", "camEff", "camStk", "camT", "camHV", "camLV", "camL0V")


class CausalA:
    """A with a causal humps_known; every per-bar array as in api.A (they are the state after each closed bar)"""
    def __init__(self):
        for nm in PER_BAR:
            setattr(self, nm, getattr(A, nm))
        self.humps = A.humps
        self.PIP = PIP

    pivots = api.Arrays.pivots

    def humps_known(self, k):
        return humps_known_causal(k)


CA = CausalA()


class Cut:
    """CausalA cut at bar k (views): a rule reading k+1 raises or changes (score_final.py's test, with the causal humps)"""
    def __init__(self, k):
        for nm in PER_BAR:
            setattr(self, nm, getattr(A, nm)[:k + 1])
        self._hk = humps_known_causal(k)
        self.humps = self._hk
        self.PIP = PIP

    pivots = api.Arrays.pivots

    def humps_known(self, k):
        H = self._hk
        return H[H[:, 7] <= k] if len(H) else H


# ------------------------------------------------------------------------------------------ the leak-free trade view
ALL_CH = ("K", "SETUP", "CLOCK", "HUMPS")


def view(t, ch=ALL_CH):
    d = DEC[t["id"]]
    u = dict(t)
    if "SETUP" in ch:
        u.update(level=d["level"], extreme=d["extreme"], ku=d["ku"], uhv_v=d["uhv_v"], brk_lo_so_far=d["lo"], brk_hi_so_far=d["hi"],
                 brk_ticks_so_far=d["bv"])
    if "K" in ch:
        k = d["k_true"]
        u.update(k=k, kb=k + 1, camEff=int(A.camEff[k]), camStk=int(A.camStk[k]))
    if "CLOCK" in ch:
        u["t_in"] = d["t_dec"]
    return u


def lf(rule, ch=ALL_CH):
    """the leak-free form of a harness-native rule: the same code on the decision-time view, with the causal humps (a Cut - already causal,
    cut at the true k - is passed straight through, so cut_audit really tests the rule on arrays that end at the decision)"""
    def r(t, A_):
        return rule(view(t, ch), A_ if isinstance(A_, Cut) else (CA if "HUMPS" in ch else A_))
    r.__name__ = f"{rule.__name__}_lf"
    return r


# ------------------------------------------------------------------------------------------ the leak-free rewrites (named, importable)
rule_rollover_ny_lf = lf(R.rule_rollover_ny)
rule_combined_lf = lf(R.rule_combined)
rule_friday_close_ny_lf = lf(R.rule_friday_close_ny)
rule_empty_book_lf = lf(R.rule_empty_book)
rule_friday_afternoon_ny_lf = lf(R.rule_friday_afternoon_ny)
rule_trigger_gap_lf = lf(R.rule_trigger_gap)
rule_big_figure_ahead_lf = lf(R.rule_big_figure_ahead)
rule_camel_old_lf = lf(R.rule_camel_old)
rule_loud_breakout_lf = lf(R.rule_loud_breakout)
rule_holiday_lf = lf(R.rule_holiday)
rule_us_data_minutes_lf = lf(R.rule_us_data_minutes)
rule_zee_camel_hh_lf = lf(R.rule_zee_camel_hh)
rule_structure_hh_hl_lf = lf(R.rule_structure_hh_hl)
rule_near_sr_lf = lf(R.rule_near_sr)
rule_counter_trend_lf = lf(R.rule_counter_trend)
rule_exhausted_run_lf = lf(R.rule_exhausted_run)


def rule_trigger_spread_lf(t, A_):
    """ask - bid at the breakout tick of the setup that was really traded (decision_by_id.csv), >= 1.0 pip"""
    return DEC[t["id"]]["spr"] >= 1.0 - 1e-9


def rule_fill_slip_lf(t, A_):
    """decision-tick analogue of rule_fill_slip: the price executable AT the breakout tick (ask for a buy = crossing bid + its spread, the
    crossing bid for a sell) is >= 1.5 pips beyond the level. Not the same rule - the 0.3 s of slippage it used to see is gone."""
    d = DEC[t["id"]]
    px = d["bc"] + d["spr"] * PIP if t["side"] > 0 else d["bc"]
    return (px - d["level"]) * t["side"] >= 1.5 * PIP - 1e-9


def rule_buy_fill_spread_lf(t, A_):
    """decision-tick analogue of rule_buy_fill_spread: a buy whose breakout-tick spread (ask - bid) is >= 1.5 pips"""
    return t["side"] > 0 and DEC[t["id"]]["spr"] >= 1.5 - 1e-9


LF = {R.rule_rollover_ny: rule_rollover_ny_lf, R.rule_combined: rule_combined_lf, R.rule_trigger_spread: rule_trigger_spread_lf,
      R.rule_friday_close_ny: rule_friday_close_ny_lf, R.rule_empty_book: rule_empty_book_lf, R.rule_friday_afternoon_ny: rule_friday_afternoon_ny_lf,
      R.rule_trigger_gap: rule_trigger_gap_lf, R.rule_fill_slip: rule_fill_slip_lf, R.rule_buy_fill_spread: rule_buy_fill_spread_lf,
      R.rule_big_figure_ahead: rule_big_figure_ahead_lf, R.rule_camel_old: rule_camel_old_lf, R.rule_loud_breakout: rule_loud_breakout_lf,
      R.rule_holiday: rule_holiday_lf, R.rule_us_data_minutes: rule_us_data_minutes_lf, R.rule_zee_camel_hh: rule_zee_camel_hh_lf,
      R.rule_structure_hh_hl: rule_structure_hh_hl_lf, R.rule_near_sr: rule_near_sr_lf, R.rule_counter_trend: rule_counter_trend_lf,
      R.rule_exhausted_run: rule_exhausted_run_lf}
assert set(LF) == set(R.ALL_RULES)

# ================================================================================================== MAIN (the audit report)
BLIND = [api._blind(t) for t in T]
LOSS = np.array([not t["win"] for t in T])
TRAIN = np.array([t["t_in"] < api.SPLIT for t in T])
FILL_RULES = (R.rule_fill_slip, R.rule_buy_fill_spread)


def mask(rule, A_=A, ts=BLIND):
    m, exc = np.zeros(N, bool), 0
    for i, t in enumerate(ts):
        try:
            m[i] = bool(rule(t, A_))
        except Exception:                                   # noqa: BLE001  (api.score keeps the trade)
            exc += 1
    return m, exc


def cut_audit(rule):
    """the leak-free rule re-run with every array cut at the TRUE k and the causal humps: 0 changed decisions required"""
    diff = 0
    for t in BLIND:
        try:
            full = bool(rule(t, A))
        except Exception:                                   # noqa: BLE001
            full = False
        u = view(t)
        try:
            cut = bool(rule(t, Cut(u["k"])))
        except Exception:                                   # noqa: BLE001
            cut = None
        diff += cut is None or cut != full
    return diff


def stats(m):
    r = {}
    for nm, h in (("train", TRAIN), ("test", ~TRAIN), ("all", np.ones(N, bool))):
        n, L = int((m & h).sum()), int((m & h & LOSS).sum())
        base = LOSS[h].mean()
        r[nm] = (L, n - L, round(L / n / base, 2) if n else None)
    return r


def grade(r):
    tr, te, al = r["train"][2] or 0, r["test"][2] or 0, r["all"][0]
    return "EXCELLENT" if (tr >= 4 and te >= 4 and al >= 4) else "GOOD" if (tr >= 2 and te >= 2 and al >= 4) else "not good"


def flips(a, b):
    d = a != b
    return f"{int(d.sum())} ({int((d & LOSS).sum())}L/{int((d & ~LOSS).sum())}W; +{int((b & ~a).sum())} skip -{int((a & ~b).sum())} skip)"


if __name__ == "__main__":
    k = np.array([t["k"] for t in T])
    kt = np.array([DEC[t["id"]]["k_true"] for t in T])
    lag = np.array([t["t_in"] - DEC[t["id"]]["t_dec"] for t in T])
    print("=" * 150)
    print("audit_leak.py - look-ahead audit of rules_final.py. Python tick replay = HYPOTHESIS, NOT PROMOTED.")
    print("=" * 150)
    print(f"SETUP : every trade re-matched to the setup reproducing its fill tick, fill price, stop and box: "
          f"{sum(d['n_cand'] == 1 for d in DEC.values())}/{N} exactly one candidate, build.py's match differs on {sum(1 - d['build_match'] for d in DEC.values())}")
    sp_old = {}
    with open(os.path.join(HERE, "trigger_spread_by_id.csv"), encoding="utf-8") as f:
        sp_old = {r_["id"]: float(r_["spr_trig_pips"]) for r_ in csv.DictReader(f)}
    print(f"SPREAD: trigger_spread_by_id.csv vs the true breakout tick: {sum(abs(sp_old[i] - d['spr']) > 1e-6 for i, d in DEC.items())} differences")
    print(f"K     : t['k'] - k_true = {dict(zip(*[x.tolist() for x in np.unique(k - kt, return_counts=True)]))}; the shifted trades read the UNCLOSED "
          f"breakout minute as bar k ({int((LOSS & (k != kt)).sum())}L/{int((~LOSS & (k != kt)).sum())}W); bar k closes after the decision on "
          f"{int((A.t[k] + 60 > np.array([DEC[t['id']]['t_dec'] for t in T])).sum())} trades")
    print(f"CLOCK : fill - decision lag: median {np.median(lag):.2f} s, p99 {np.percentile(lag, 99):.1f} s, max {lag.max():.1f} s")
    print(f"HUMPS : {N_REDRAWN} of {len(V_HID)} hump versions are later redrawn; arrays.npz keeps only the last. Trades where humps_known(k) "
          f"differs from the causal list: {sum(1 for t in T if not np.array_equal(A.humps_known(DEC[t['id']]['k_true']), humps_known_causal(DEC[t['id']]['k_true'])))}")
    print(f"BLIND : api._blind strips only {api.OUTCOME}; still visible to a rule and fill-derived (>= 0.3 s after the decision): fill, stop, stop_pips")
    print("HARNESS FIXES for every future rule: decision_by_id.csv (k_true, t_dec, the true setup's fields, the breakout-tick spread) and "
          "audit_leak.CausalA / humps_known_causal (the humps as known at k). Bars align with the ticks at offset 0; ATR / ADX are causal.")
    def _canary(t, A_):                                     # deliberately reads bar k+1: the cut audit MUST flag it
        return A_.c[t["k"] + 1] > A_.c[t["k"]]
    print(f"CANARY: a rule reading bar k+1 -> cut-at-true-k diffs {cut_audit(lf(_canary))} of {N} (must be > 0, else the audit is blind)")
    print()
    rows = []
    for rule in R.ALL_RULES:
        nm = rule.__name__
        m0, e0 = mask(rule)
        r0 = stats(m0)
        out = {"name": nm, "orig": r0, "exc": e0}
        if rule in FILL_RULES:
            out["chan"] = "reads t['fill'] (first tick >= 0.3 s AFTER the decision): every decision depends on post-decision data"
        else:
            parts = []
            for ch in ("K", "SETUP", "CLOCK", "HUMPS"):
                mc, _ = mask(lf(rule, (ch,)))
                parts.append(f"{ch} {flips(m0, mc)}")
            out["chan"] = " | ".join(parts)
        g = LF[rule]
        m1, e1 = mask(g)
        r1 = stats(m1)
        out.update(lf=r1, lf_exc=e1, all_flips=flips(m0, m1), cut=cut_audit(g), identical=bool(np.array_equal(m0, m1)) and rule not in FILL_RULES)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            api.report(g, g.__name__)
        out["report"] = buf.getvalue().rstrip()
        rows.append(out)
        o, n_ = r0, r1
        print(f"{nm}")
        print(f"   original  : {o['all'][0]}L/{o['all'][1]}W x{o['all'][2]} | train {o['train'][0]}L x{o['train'][2]} | test {o['test'][0]}L x{o['test'][2]}"
              f" | {grade(o)} | exc {e0}")
        print(f"   channels  : {out['chan']}")
        print(f"   leak-free : {n_['all'][0]}L/{n_['all'][1]}W x{n_['all'][2]} | train {n_['train'][0]}L x{n_['train'][2]} | test {n_['test'][0]}L x{n_['test'][2]}"
              f" | {grade(n_)} | exc {e1} | flips vs original {out['all_flips']} | cut-at-true-k diffs {out['cut']}"
              f" | {'IDENTICAL -> survives' if out['identical'] else 'CHANGED / leaky -> does not survive as written'}")
        print(f"   api.report: {out['report']}")
    print()
    print("SUMMARY (survives = the leak-free decisions are identical to the original's on all 7,626 trades)")
    for o in rows:
        print(f"   {o['name']:28s} {'SURVIVES' if o['identical'] else 'LEAKS   '}  original {grade(o['orig']):9s} -> leak-free {grade(o['lf']):9s}  flips {o['all_flips']}")
