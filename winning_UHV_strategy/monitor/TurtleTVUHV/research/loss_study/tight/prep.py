"""prep.py - material for pushing the angel's TIGHT secure zone towards 100% (Zee 2026-11-06: "the tight secure one.. can u try everything u
can to bring this winrate to 100%? try ur best.. its just inches away").

Three stacks on the 97.7% base, all from the engine (settings/saved):
  tight   = 2026-11-06 09-00-00.json  (RiskMgr 2, humps 2-3, ER 0.30-0.45, NY rollover, breakout spread 1.0)  ~714 trades / 4 losses
  secure  = 2026-11-06 09-10-00.json  (RiskMgr 2, humps 2-5, ER 0.15-0.45, NY rollover, spread 1.0)         ~2238 trades / 30 losses
  base    = 2026-11-05 05-45-38.json  (no risk manager)                                                   7631 trades / 172 losses
For every trade it records the DECISION-TIME facts (the breakout tick: setup time, k = the last closed candle before the breakout minute,
UHV bar, level, extreme, breakout spread / ticks / lo / hi, camel humps at k) and the outcome. Writes trades_<stack>.json and charts of every
tight loss + 3 winning twins each, and every secure loss + 1 twin each (charts/<stack>_<id>.png). Rules are scored with api_tight.py.
Run: py research/loss_study/tight/prep.py"""
import datetime as dt
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import sim  # noqa: E402
import uhv_engine as U  # noqa: E402
import uhv_filters  # noqa: E402

PIP = 1e-4
PKT = dt.timezone(dt.timedelta(hours=5))
SAVED = os.path.join(ROOT, "settings", "saved")
STACKS = {"tight": "2026-11-06 09-00-00.json", "secure": "2026-11-06 09-10-00.json", "base": "2026-11-05 05-45-38.json"}
CH = os.path.join(HERE, "charts")
os.makedirs(CH, exist_ok=True)

D = sim.data("year1")
t1 = np.asarray(D["t1"], dtype=np.int64)
o1, h1, l1, c1, v1 = (np.asarray(D[k], dtype=float) for k in ("o1", "h1", "l1", "c1", "v1"))
atr = np.asarray(D["atr"], dtype=float)
Z = np.load(os.path.join(os.path.dirname(HERE), "arrays.npz"))
H = Z["humps"]
STK = uhv_filters._prep(D)["stk"]


def utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


def er(k, n=16):
    cc = c1[k - n:k + 1]
    p = float(np.abs(np.diff(cc)).sum())
    return abs(float(cc[-1] - cc[0])) / p if p > 0 else 0.0


out = {}
for name, fn in STACKS.items():
    inp = json.load(open(os.path.join(SAVED, fn), encoding="utf-8"))["inputs"]
    tr, _, _ = U.simulate(inp)
    R = tr[tr[:, 10] == 0]
    S, TK = U._setups(U.det_file(inp))
    S = U._instant_setups(TK, float(inp.get("InpUhvPreBreak") or 0), U.det_file(inp))
    st = np.array([s["t"] for s in S])
    rows = []
    for x in R:
        side, tin = int(x[0]), float(x[1])
        j = int(np.searchsorted(st, tin + 1e-6)) - 1
        if j < 0 or tin - S[j]["t"] > 30:
            continue
        s = S[j]
        kb = int(np.searchsorted(t1, (s["t"] // 60) * 60))           # the breakout minute (of the DECISION tick, not the fill)
        k = kb - 1
        if k < 200 or kb >= len(t1) - 31:
            continue
        ku = int(np.searchsorted(t1, s["uhv_t"]))
        rows.append({
            "id": f"{utc(s['t']):%m%d-%H%M%S}-{'B' if side > 0 else 'S'}", "side": side, "t_dec": float(s["t"]), "k": k, "kb": kb, "ku": ku,
            "level": float(s["level"]), "extreme": float(s["extreme"]), "uhv_v": float(v1[ku]), "brk_ticks": int(s.get("bv") or 0),
            "brk_lo": float(s["lo"]), "brk_hi": float(s["hi"]), "brk_bid": float(s.get("bc") or 0), "trig_spread_pips": round(float(s.get("sp", 0)) / PIP, 2),
            "box": int(x[8]) - (0 if side > 0 else 21), "humps": int(STK[k]) * side, "er16": round(er(k), 3), "atr_pips": round(atr[k] / PIP, 2),
            # outcome - for the study only; a rule must never read these
            "win": bool(x[6] > 0), "pnl": float(x[6]), "fill": float(x[2]), "stop": float(x[3]), "t_out": float(x[4]), "exit": float(x[5]),
            "best_R": float(x[15]), "worst_R": float(x[16]),
        })
    out[name] = rows
    json.dump(rows, open(os.path.join(HERE, f"trades_{name}.json"), "w", encoding="utf-8"))
    L = sum(1 for r in rows if not r["win"])
    print(f"{name}: {len(rows)} trades, {L} losses, WR {100 * (1 - L / len(rows)):.2f}%", flush=True)


def chart(t, path, tag):
    k, kb, ku, side = t["k"], t["kb"], t["ku"], t["side"]
    a, b = k - 89, kb + 30
    fig, (ax, av) = plt.subplots(2, 1, figsize=(15, 8.2), sharex=True, gridspec_kw={"height_ratios": [3.2, 1]})
    fig.patch.set_facecolor("#131722")
    for axx in (ax, av):
        axx.set_facecolor("#131722"); axx.tick_params(colors="#b2b5be", labelsize=8)
        for sp in axx.spines.values():
            sp.set_color("#363a45")
    for i in range(a, b + 1):
        alpha = 0.28 if i >= kb else 1.0
        col = "#26a69a" if c1[i] >= o1[i] else "#ef5350"
        ax.vlines(i, l1[i], h1[i], color=col, linewidth=1, alpha=alpha)
        ax.add_patch(plt.Rectangle((i - 0.35, min(o1[i], c1[i])), 0.7, max(abs(c1[i] - o1[i]), 1e-6), color=col, alpha=alpha))
        av.bar(i, v1[i], width=0.8, color="#ffb300" if i == ku else col, alpha=1.0 if i == ku else alpha)
    for b0, vv0, bh, vh, bb1, vv1, trr, known in H:
        b0, bh, bb1, known = int(b0), int(bh), int(bb1), int(known)
        if bb1 < a or b0 > b:
            continue
        colr = "#26a69a" if trr == 1 else "#ef5350" if trr == -1 else "#9e9e9e"
        kn = known <= k
        ax.plot([b0, bh, bb1], [vv0, vh, vv1], color=colr, linewidth=2.2 if kn else 1.2, alpha=0.95 if kn else 0.3, linestyle="-" if kn else "--")
    ax.axhline(t["level"], color="#ffb300", linewidth=1, linestyle="--")
    ax.axhline(t["extreme"], color="#ab47bc", linewidth=0.9, linestyle=":")
    lo_v = min(l1[a:b + 1].min(), t["extreme"]); hi_v = max(h1[a:b + 1].max(), t["level"])
    pad = (hi_v - lo_v) * 0.08
    ax.set_ylim(lo_v - pad, hi_v + pad)                               # zoom on the candles (the 20-pip stop is in the caption)
    ax.axvline(kb - 0.5, color="#ffffff", linewidth=0.8, alpha=0.5)
    ax.scatter([kb], [t["fill"]], marker="^" if side > 0 else "v", s=160, color="#00e5ff", zorder=5)
    ko = int(np.searchsorted(t1, (t["t_out"] // 60) * 60))
    if a <= ko <= b:
        ax.scatter([ko], [min(max(t["exit"], lo_v), hi_v)], marker="x", s=90, color="#ffffff", zorder=5)
    ticks = list(range(a, b + 1, 15))
    av.set_xticks(ticks); av.set_xticklabels([utc(t1[i]).astimezone(PKT).strftime("%H:%M") for i in ticks])
    ax.set_title(f"[{tag}] {t['id']}  {'WIN' if t['win'] else 'LOSS'} {t['pnl']:+.0f}$/lot  {utc(t['t_dec']):%Y-%m-%d %H:%M:%S} UTC  humps {t['humps']}  "
                 f"ER16 {t['er16']}  ATR {t['atr_pips']}p  UHV {t['uhv_v']:.0f} / brk {t['brk_ticks']} ticks  spread {t['trig_spread_pips']}p  box {t['box']}  "
                 f"stop {abs(t['fill'] - t['stop']) / PIP:.1f}p", color="#d1d4dc", fontsize=9, loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=78, facecolor=fig.get_facecolor()); plt.close(fig)


for name, ntwin in (("tight", 3), ("secure", 1)):
    rows = out[name]
    wins = [r for r in rows if r["win"]]
    wt = np.array([w["t_dec"] for w in wins])
    used = set()
    for L in [r for r in rows if not r["win"]]:
        chart(L, os.path.join(CH, f"{name}_{L['id']}.png"), name + " LOSS")
        got = 0
        for o in np.argsort(np.abs(wt - L["t_dec"])):
            w = wins[int(o)]
            if w["side"] == L["side"] and w["id"] not in used:
                used.add(w["id"]); chart(w, os.path.join(CH, f"{name}_twin_{L['id']}_{w['id']}.png"), name + " twin WIN"); got += 1
            if got >= ntwin:
                break
print("charts done:", len(os.listdir(CH)))
