"""build.py - the material for studying every loss of the 97.7% setting (Zee 2026-11-06: "study the losses on charts.. comments should come
from you ... u must be able to comment on each loss and find a fix").

For every losing trade of settings/saved/2026-11-05 05-45-38.json, and two winning "twins" per loss (same side, nearest in time - so every
rule can be checked against winners that look alike), it writes:
  charts/<id>.png   90 one-minute candles before the entry + 30 after (after = faded), tick-volume pane, the camel humps KNOWN AT ENTRY
                    (solid; the hindsight humps after the entry are faded), the UHV candle, the UHV level, the retracement extreme, entry,
                    stop, exit, and a caption with the facts
  trades.json       every trade of the setting (wins and losses) with the numbers the study and the rules need
  batches.json      the losses split into study batches, each with its twins
  arrays.npz        per-bar arrays (t o h l c v atr adx + the camel state after each closed bar) for the rule harness (api.py)
Nothing here uses information from after the entry, except the faded part of the chart and the outcome fields (pnl, exit), which the rules
must never read. Run: py research/loss_study/build.py"""
import datetime as dt
import json
import math
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import sim  # noqa: E402
import uhv_diamond  # noqa: E402
import uhv_engine as U  # noqa: E402

PIP = 1e-4
SETTING = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
OUT = HERE
CH = os.path.join(OUT, "charts")
os.makedirs(CH, exist_ok=True)
PKT = dt.timezone(dt.timedelta(hours=5))


def utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


# ------------------------------------------------------------------ the setting's trades
inp = json.load(open(SETTING, encoding="utf-8"))["inputs"]
tr, _, _ = U.simulate(inp)
R = tr[tr[:, 10] == 0]
S, TK = U._setups(U.det_file(inp))
S = U._instant_setups(TK, float(inp.get("InpUhvPreBreak") or 0), U.det_file(inp))
st = np.array([s["t"] for s in S])

D = sim.data("year1")
t1 = np.asarray(D["t1"], dtype=np.int64)
o1, h1, l1, c1, v1 = (np.asarray(D[k], dtype=float) for k in ("o1", "h1", "l1", "c1", "v1"))
atr, adx = np.asarray(D["atr"], dtype=float), np.asarray(D["adx"], dtype=float)
N = len(t1)

# ------------------------------------------------------------------ the camel state after every closed bar (uhv_diamond.camel_step, CAM_PIV)
p = uhv_diamond.CAM_PIV
camEff = np.zeros(N, dtype=np.int8); camStk = np.zeros(N, dtype=np.int16); camT = np.zeros(N, dtype=np.int8)
camHV = np.full(N, np.nan); camLV = np.full(N, np.nan); camL0V = np.full(N, np.nan)
T, HB, HV, L0B, L0V, LB, LV, Tr, Stk, Stk0, Eff = 0, None, None, None, None, None, None, 0, 0, 0, 0
humps = []                      # [b0, v0, bh, vh, b1, v1, tr, known_at_bar]
for i in range(2 * p, N):
    c = i - p
    ph = all(not (h1[c] < h1[c + d] or h1[c] < h1[c - d]) for d in range(1, p + 1))
    pl = all(not (l1[c] > l1[c + d] or l1[c] > l1[c - d]) for d in range(1, p + 1))
    if ph:
        if T == 1:
            if h1[c] >= HV:
                HB, HV = c, h1[c]
        else:
            Stk0 = Stk; L0B, L0V, HB, HV, T = LB, LV, c, h1[c], 1
    if pl:
        redraw = False
        if T == 1:
            LB, LV, T, redraw = c, l1[c], -1, True
        elif T == -1 and l1[c] <= LV:
            LB, LV, redraw = c, l1[c], True
        elif T == 0:
            LB, LV, T = c, l1[c], -1
        if redraw and HB is not None and L0B is not None:
            Tr = 1 if LV > L0V else -1 if LV < L0V else 0
            Stk = (max(Stk0, 0) + 1) if Tr == 1 else (min(Stk0, 0) - 1) if Tr == -1 else 0
            if abs(Stk) >= uhv_diamond.CAM_CONFIRM:
                Eff = 1 if Stk > 0 else -1
            elif Tr == 0 and uhv_diamond.CAM_CONFIRM <= 1:
                Eff = 0
            if humps and humps[-1][2] == HB:
                humps[-1] = [L0B, float(L0V), HB, float(HV), LB, float(LV), Tr, i]
            else:
                humps.append([L0B, float(L0V), HB, float(HV), LB, float(LV), Tr, i])
    camEff[i], camStk[i], camT[i] = Eff, Stk, T
    camHV[i] = HV if HV is not None else np.nan
    camLV[i] = LV if LV is not None else np.nan
    camL0V[i] = L0V if L0V is not None else np.nan
H = np.array([[hh[0], hh[1], hh[2], hh[3], hh[4], hh[5], hh[6], hh[7]] for hh in humps], dtype=float)
np.savez(os.path.join(OUT, "arrays.npz"), t=t1, o=o1, h=h1, l=l1, c=c1, v=v1, atr=atr, adx=adx, camEff=camEff, camStk=camStk, camT=camT,
         camHV=camHV, camLV=camLV, camL0V=camL0V, humps=H)

# ------------------------------------------------------------------ every trade, with its setup
trades = []
for x in R:
    side, tin = int(x[0]), float(x[1])
    j = int(np.searchsorted(st, tin + 1e-6)) - 1                      # the setup whose breakout tick opened this round
    s = S[j] if 0 <= j < len(S) and tin - S[j]["t"] < 30 else None
    kb = int(np.searchsorted(t1, (tin // 60) * 60))                   # the entry (breakout) minute
    k = kb - 1                                                         # the last CLOSED candle before the entry
    if s is None or k < 150 or kb >= N - 31:
        continue
    ku = int(np.searchsorted(t1, s["uhv_t"]))
    trades.append({
        "id": f"{utc(tin):%m%d-%H%M%S}-{'B' if side > 0 else 'S'}", "side": side, "t_in": tin, "k": k, "kb": kb, "ku": ku,
        "level": float(s["level"]), "extreme": float(s["extreme"]), "uhv_v": float(v1[ku]), "brk_ticks_so_far": int(s.get("bv") or 0),
        "brk_lo_so_far": float(s["lo"]), "brk_hi_so_far": float(s["hi"]), "fill": float(x[2]), "stop": float(x[3]),
        "stop_pips": round(abs(float(x[2]) - float(x[3])) / PIP, 1), "box": int(x[8]) - (0 if side > 0 else 21),
        "camEff": int(camEff[k]), "camStk": int(camStk[k]),
        # outcome - for the study and the scoring only; a rule must never read these
        "pnl": float(x[6]), "win": bool(x[6] > 0), "t_out": float(x[4]), "exit": float(x[5]), "why": int(x[13]),
        "best_R": float(x[15]), "worst_R": float(x[16]),
    })
json.dump(trades, open(os.path.join(OUT, "trades.json"), "w", encoding="utf-8"))
losses = [t for t in trades if not t["win"]]
wins = [t for t in trades if t["win"]]
print(f"trades {len(trades)}  losses {len(losses)}  wins {len(wins)}")

# twins: two winners per loss, same side, nearest in time, each used once
used, twin_of = set(), {}
wt = np.array([w["t_in"] for w in wins])
for L in losses:
    order = np.argsort(np.abs(wt - L["t_in"]))
    got = []
    for o in order:
        w = wins[int(o)]
        if w["side"] == L["side"] and w["id"] not in used:
            got.append(w["id"]); used.add(w["id"])
        if len(got) == 2:
            break
    twin_of[L["id"]] = got
byid = {t["id"]: t for t in trades}


# ------------------------------------------------------------------ the charts
def chart(t, path):
    k, kb, ku, side = t["k"], t["kb"], t["ku"], t["side"]
    a, b = k - 89, kb + 30
    xs = np.arange(a, b + 1)
    fig, (ax, av) = plt.subplots(2, 1, figsize=(15, 8.2), sharex=True, gridspec_kw={"height_ratios": [3.2, 1]})
    fig.patch.set_facecolor("#131722")
    for axx in (ax, av):
        axx.set_facecolor("#131722"); axx.tick_params(colors="#b2b5be", labelsize=8)
        for sp in axx.spines.values():
            sp.set_color("#363a45")
    for i in xs:
        fut = i >= kb
        alpha = 0.28 if fut else 1.0
        col = "#26a69a" if c1[i] >= o1[i] else "#ef5350"
        ax.vlines(i, l1[i], h1[i], color=col, linewidth=1, alpha=alpha)
        ax.add_patch(plt.Rectangle((i - 0.35, min(o1[i], c1[i])), 0.7, max(abs(c1[i] - o1[i]), 1e-6), color=col, alpha=alpha))
        vc = "#ffb300" if i == ku else col
        av.bar(i, v1[i], width=0.8, color=vc, alpha=alpha if i != ku else 1.0)
    # camel humps: solid = known at the entry (completed by bar k), faded = drawn later (hindsight)
    for b0, vv0, bh, vh, bb1, vv1, trr, known in H:
        b0, bh, bb1, known = int(b0), int(bh), int(bb1), int(known)
        if bb1 < a or b0 > b:
            continue
        colr = "#26a69a" if trr == 1 else "#ef5350" if trr == -1 else "#9e9e9e"
        kn = known <= k
        ax.plot([b0, bh, bb1], [vv0, vh, vv1], color=colr, linewidth=2.2 if kn else 1.2, alpha=0.95 if kn else 0.3,
                linestyle="-" if kn else "--")
    # the levels
    ax.axhline(t["level"], color="#ffb300", linewidth=1, linestyle="--")
    ax.text(a + 1, t["level"], " UHV level", color="#ffb300", fontsize=8, va="bottom")
    ax.axhline(t["extreme"], color="#ab47bc", linewidth=0.9, linestyle=":")
    ax.text(a + 1, t["extreme"], " retracement extreme", color="#ab47bc", fontsize=8, va="bottom")
    ax.axhline(t["stop"], color="#ef5350", linewidth=0.9, linestyle="-.", alpha=0.7)
    ax.text(b - 1, t["stop"], "stop ", color="#ef5350", fontsize=8, va="bottom", ha="right")
    ax.axvline(kb - 0.5, color="#ffffff", linewidth=0.8, alpha=0.5)
    ax.scatter([kb], [t["fill"]], marker="^" if side > 0 else "v", s=160, color="#00e5ff", zorder=5)
    ax.annotate(f"{'BUY' if side > 0 else 'SELL'} {t['fill']:.5f}", (kb, t["fill"]), color="#00e5ff", fontsize=9,
                xytext=(6, 10 if side > 0 else -16), textcoords="offset points")
    ko = int(np.searchsorted(t1, (t["t_out"] // 60) * 60))
    if a <= ko <= b:
        ax.scatter([ko], [t["exit"]], marker="x", s=90, color="#ffffff", zorder=5)
    av.annotate("UHV", (ku, v1[ku]), color="#ffb300", fontsize=8, xytext=(0, 3), textcoords="offset points", ha="center")
    av.axhline(t["uhv_v"], color="#ffb300", linewidth=0.6, linestyle=":")
    # x labels in PKT
    ticks = list(range(a, b + 1, 15))
    av.set_xticks(ticks)
    av.set_xticklabels([utc(t1[i]).astimezone(PKT).strftime("%H:%M") for i in ticks])
    res = "WIN" if t["win"] else "LOSS"
    ax.set_title(f"{t['id']}  {res} {t['pnl']:+.0f}$ (1 lot)   entry {utc(t['t_in']):%Y-%m-%d %H:%M:%S} UTC = "
                 f"{utc(t['t_in']).astimezone(PKT):%H:%M:%S} PKT   camel at entry: {('GREEN' if t['camEff'] > 0 else 'RED' if t['camEff'] < 0 else 'none')} "
                 f"x{abs(t['camStk'])}   UHV vol {t['uhv_v']:.0f} / breakout ticks so far {t['brk_ticks_so_far']}   stop {t['stop_pips']} pips   "
                 f"range box {t['box']}", color="#d1d4dc", fontsize=9, loc="left")
    fig.text(0.01, 0.005, "solid candles + solid humps = known at the entry (white line).  faded = after the entry (hindsight).  "
             "orange volume bar = the UHV candle.  cyan triangle = entry, white x = exit.", color="#787b86", fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=78, facecolor=fig.get_facecolor())
    plt.close(fig)


need = {L["id"] for L in losses} | {w for ws in twin_of.values() for w in ws}
for i, tid in enumerate(sorted(need)):
    chart(byid[tid], os.path.join(CH, tid + ".png"))
    if i % 50 == 0:
        print("charts", i, "/", len(need), flush=True)


# ------------------------------------------------------------------ batches for the study (by time, so each batch sees one stretch of market)
def ctx(t):
    k = t["k"]
    rows = []
    for i in range(k - 39, k + 1):                                   # the last 40 closed candles, oldest first (no future)
        rows.append([utc(t1[i]).astimezone(PKT).strftime("%H:%M"), round(o1[i], 5), round(h1[i], 5), round(l1[i], 5), round(c1[i], 5), int(v1[i])])
    return rows


def card(t, with_outcome):
    d = {k_: t[k_] for k_ in ("id", "side", "level", "extreme", "fill", "stop", "stop_pips", "uhv_v", "brk_ticks_so_far", "box", "camEff", "camStk")}
    d["entry_utc"] = f"{utc(t['t_in']):%Y-%m-%d %H:%M:%S}"
    d["entry_pkt"] = f"{utc(t['t_in']).astimezone(PKT):%H:%M:%S}"
    d["uhv_candle_pkt"] = utc(t1[t["ku"]]).astimezone(PKT).strftime("%H:%M")
    d["atr_pips"] = round(atr[t["k"]] / PIP, 2)
    d["adx"] = round(float(adx[t["k"]]), 1)
    d["chart"] = os.path.join(CH, t["id"] + ".png")
    d["last40_closed_candles_pkt_ohlcv"] = ctx(t)
    if with_outcome:
        d["result_usd_1lot"] = round(t["pnl"], 1)
        d["outcome"] = "WIN" if t["win"] else "LOSS"
    return d


losses_sorted = sorted(losses, key=lambda t: t["t_in"])
NB = 8
batches = []
for bi in range(NB):
    part = losses_sorted[bi * len(losses_sorted) // NB:(bi + 1) * len(losses_sorted) // NB]
    batches.append({"batch": bi + 1, "losses": [card(L, True) for L in part],
                    "twins": [card(byid[w], True) for L in part for w in twin_of[L["id"]]]})
json.dump(batches, open(os.path.join(OUT, "batches.json"), "w", encoding="utf-8"), indent=1)
for bi, bt in enumerate(batches):
    json.dump(bt, open(os.path.join(OUT, f"batch_{bi + 1}.json"), "w", encoding="utf-8"), indent=1)
print("batches", [len(b["losses"]) for b in batches], "twins", [len(b["twins"]) for b in batches])
