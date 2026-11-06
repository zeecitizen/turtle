"""mlx/meta_features.py - the META-LABELLING table: one row per trade of simdata/mlx_entries_C.npz (src 0 = setting C, src 1 = UNIVERSE-C),
the STRATEGY STATE at the entry moment (the setup candle, where it sits on the EMAs, the breakout, the stop, the universe's own recent
results) beside the 85 per-bar features of the last closed bar, and the trade's label (win / pnl / full stop / R-multiple).

Everything is computable at the ENTRY minute: closed-bar values use bars <= entry bar - 1 (the setup bar is always earlier); the entry bar's
open, the breakout level and the fill are known at entry; universe state uses trades that ENTERED before this entry (open count) or CLOSED
before it (recent results, day P&L). check_leakage() proves it by truncation (bars after the entry bar's open removed, later entries removed,
still-open trades' exits and pnl hidden) - every setup feature must come back bit-identical.

Conventions: side-relative values ("_rel") are multiplied by the trade's side (+1 buy / -1 sell), so positive = in the trade's favour;
ATR units divide by the tester's own iATR column: atr[setup bar] for setup-candle values, atr[entry bar - 1] for entry-time values;
pips = 0.1 (InpPipPts 10 x 0.01). The EMAs are the EA's (sim.emas: InpEmaFast / InpEmaSlow, seeded with the first close), the 64 / 256
proxies are mlx.features.ema (the same seeds as the 85). NaN / inf -> 0 (counted).

Outputs: simdata/mlx_meta.npz (X_setup float32, setup_names, X_bar float32 (the 85), bar_names, side, entry_t, exit_t, k15, src, pnl, y_win,
full_stop, reason, year, + k_setup, kind, setup_ok, r_mult, entry, sl, lots, bar_row_ok, exit_k15, same_tick_exit) and simdata/mlx_meta_spec.json (each setup feature, one line).
CLI: py -m mlx.meta_features [--picks 5] [--seed 1] [--no-check]   (from monitor/saad_view)
CLAUDE.md: a hypothesis-generator's input; nothing here is evidence until MT5's Strategy Tester says so."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEW = HERE.parent
if str(VIEW) not in sys.path:
    sys.path.insert(0, str(VIEW))
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np                                     # noqa: E402
import sim                                             # noqa: E402
import sim_full                                        # noqa: E402
from mlx import features                               # noqa: E402
from mlx import data as mdata                          # noqa: E402

SIMDATA = VIEW / "simdata"
C_FILE = VIEW / "settings" / "saved" / "2026-11-01 08-38-10.json"       # setting C (Zee's standard, 2026-11-01)
ENTRIES_C = SIMDATA / "mlx_entries_C.npz"
DATASET = SIMDATA / "mlx_dataset.npz"
OUT = SIMDATA / "mlx_meta.npz"
SPEC = SIMDATA / "mlx_meta_spec.json"
PIP = 0.1
FULL_STOP = -4000.0
KIND = {0: "none", 1: "pin", 2: "hammer/star", 3: "marubozu", 4: "lego"}

# (name, one-line definition) - the column order of X_setup; the MQL5 side mirrors it
SPEC_ROWS = [
    ("kind", "setup candle kind from the tester's setups array: 1 pin, 2 hammer / star, 3 marubozu"),
    ("kind_pin", "1 if kind == 1"),
    ("kind_ham", "1 if kind == 2 (hammer / shooting star)"),
    ("kind_maru", "1 if kind == 3 (marubozu)"),
    ("on_fast", "1 if the setup candle is 'online' with the fast EMA (sim_full._online, the trade's side, InpTouchMode / InpTouchPips)"),
    ("on_slow", "1 if the setup candle is 'online' with the slow EMA (same test)"),
    ("ema_which", "which EMA the setup sits on: 1 fast only, 2 slow only, 3 both, 0 neither"),
    ("buy_rule", "buys: 1 = the normal rule (fast EMA, rulesOk), 2 = the inverted rule only (slow EMA, invOk); sells 0"),
    ("bars_to_entry", "entry bar - setup bar (1 .. InpBreakBars)"),
    ("entry_min_in_bar", "minutes from the entry bar's open to the entry fill"),
    ("s_range_atr", "setup candle (high - low) / atr[setup bar]"),
    ("s_body", "setup candle |close - open| / range"),
    ("s_uwick", "setup candle upper wick / range"),
    ("s_lwick", "setup candle lower wick / range"),
    ("s_clpos", "setup candle (close - low) / range"),
    ("s_dir_rel", "setup candle direction sign(close - open) x side"),
    ("s_c_ef_rel", "setup candle (close - fast EMA) x side / atr[setup bar]"),
    ("s_h_ef_rel", "setup candle (high - fast EMA) x side / atr[setup bar]"),
    ("s_l_ef_rel", "setup candle (low - fast EMA) x side / atr[setup bar]"),
    ("s_c_es_rel", "setup candle (close - slow EMA) x side / atr[setup bar]"),
    ("s_h_es_rel", "setup candle (high - slow EMA) x side / atr[setup bar]"),
    ("s_l_es_rel", "setup candle (low - slow EMA) x side / atr[setup bar]"),
    ("s_gap_atr", "|fast EMA - slow EMA| / atr at the setup bar"),
    ("s_gap_pips", "|fast EMA - slow EMA| / 0.1 at the setup bar"),
    ("s_align_rel", "(fast EMA - slow EMA) x side / atr at the setup bar (positive = EMAs aligned with the trade)"),
    ("e_gap_atr", "|fast EMA - slow EMA| / atr at the bar before entry"),
    ("e_gap_pips", "|fast EMA - slow EMA| / 0.1 at the bar before entry"),
    ("e_align_rel", "(fast EMA - slow EMA) x side / atr at the bar before entry"),
    ("s_ef_slope4_rel", "(fast EMA[s] - fast EMA[s-4]) x side / atr[s], s = setup bar"),
    ("s_ef_slope16_rel", "(fast EMA[s] - fast EMA[s-16]) x side / atr[s]"),
    ("s_es_slope4_rel", "(slow EMA[s] - slow EMA[s-4]) x side / atr[s]"),
    ("s_es_slope16_rel", "(slow EMA[s] - slow EMA[s-16]) x side / atr[s]"),
    ("e_ef_slope4_rel", "(fast EMA[e-1] - fast EMA[e-5]) x side / atr[e-1], e = entry bar"),
    ("e_ef_slope16_rel", "(fast EMA[e-1] - fast EMA[e-17]) x side / atr[e-1]"),
    ("e_es_slope4_rel", "(slow EMA[e-1] - slow EMA[e-5]) x side / atr[e-1]"),
    ("e_es_slope16_rel", "(slow EMA[e-1] - slow EMA[e-17]) x side / atr[e-1]"),
    ("s_chop_er10", "efficiency ratio at the setup bar over 10 bars: |c[s] - c[s-10]| / sum |c[j] - c[j-1]| (the EA's InpChopEr test)"),
    ("s_chop_er16", "the same over 16 bars (setting C's InpChopErLook)"),
    ("s_chop_er20", "the same over 20 bars"),
    ("s_ema64_rel", "setup bar (close - EMA64) x side / atr[s] (HTF trend proxy; EMA64 = mlx.features.ema)"),
    ("s_ema256_rel", "setup bar (close - EMA256) x side / atr[s]"),
    ("s_disp_64_256_rel", "setup bar (EMA64 - EMA256) x side / atr[s]"),
    ("s_adx", "the tester's ADX (iADX 14) at the setup bar"),
    ("s_atr_r_e", "atr[setup bar] / atr[entry bar - 1] (volatility change while waiting for the break)"),
    ("level_rel", "the breakout level (setup high + InpBreakPips for buys / setup low - InpBreakPips for sells) minus the setup extreme, / atr[e-1]"),
    ("brk_dist_atr", "(entry - setup high) for buys / (setup low - entry) for sells, / atr[e-1] (how far past the setup extreme the fill is)"),
    ("brk_dist_pips", "the same in pips"),
    ("open_vs_level_rel", "(entry bar open - breakout level) x side / atr[e-1] (did the bar open already through the level)"),
    ("entry_vs_sclose_rel", "(entry - setup close) x side / atr[e-1]"),
    ("s_risk_atr", "the setup candle's protective extreme: (entry - setup low) for buys / (setup high - entry) for sells, / atr[e-1] (the 'natural' stop)"),
    ("s_risk_pips", "the same in pips"),
    ("stop_atr", "|entry - sl| / atr[e-1] (sl = the tester's stop column; constant 260 pips for setting C's InpSlMode 2 / InpSlUsd 26)"),
    ("stop_pips", "|entry - sl| / 0.1"),
    ("stop_usd", "|entry - sl| x lots x 100 (the dollars at the full stop)"),
    ("tp_over_stop", "InpFixTpPips x 0.1 / |entry - sl| (the trade's reward : risk)"),
    ("n_open", "universe trades open at entry: entered strictly before entry_t and not yet closed (exit_t > entry_t); never counts the trade itself"),
    ("n_open_same", "of those, the trade's side"),
    ("n_open_opp", "of those, the opposite side"),
    ("prev1_pnl", "pnl of the last universe trade CLOSED before entry_t (exit_t < entry_t); 0 if none"),
    ("prev1_win", "1 if that trade won, 0 otherwise / none"),
    ("prev3_pnl", "sum pnl of the last 3 universe trades closed before entry_t"),
    ("prev3_wr", "win share of those (count of available in prev_n3)"),
    ("prev10_pnl", "sum pnl of the last 10 universe trades closed before entry_t"),
    ("prev10_wr", "win share of those"),
    ("prev_n10", "how many of the last 10 exist (history start)"),
    ("since_close_min", "minutes from the last universe close to the entry (0 if none, capped 7 days)"),
    ("day_pnl", "universe P&L realised today (server day of entry_t) by trades closed before entry_t"),
    ("day_closed_n", "universe trades closed today before entry_t"),
    ("day_opened_n", "universe trades entered today before entry_t (open or closed)"),
    ("setups_20", "universe setups (any side) in bars entry-20 .. entry-1"),
    ("setups_opp_20", "of those, the opposite side"),
    ("hour", "server hour of entry_t (the data clock, as hr15)"),
    ("minute", "minute of hour of entry_t"),
    ("dow", "weekday of entry_t: 0 Sunday .. 6 Saturday (MqlDateTime.day_of_week)"),
    ("side", "+1 buy / -1 sell"),
]
SETUP_NAMES = [n for n, _ in SPEC_ROWS]


def _iso(t):
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%d %H:%M")


def years_of(t):
    return np.array([datetime.fromtimestamp(int(v), timezone.utc).year for v in t], dtype=np.int64)


# ---------------------------------------------------------------- the tester's setups
def run_setups(c_file=C_FILE, ds="m15"):
    """sim.simulate exactly as data.build_entries(b_file=c_file): -> {0: (trades, setups), 1: (trades, setups)}, P (the universe's vector)"""
    c = json.loads(Path(c_file).read_text(encoding="utf-8"))["inputs"]
    out, P = {}, None
    for src, inputs in ((0, c), (1, mdata.universe_inputs(c))):
        t0 = time.time()
        full = mdata._full_inputs(inputs)
        tr, setups, stats = sim.simulate(full, ds=ds)
        tr = tr[tr[:, 10] == 0]
        tr = tr[np.argsort(tr[:, 1], kind="stable")]
        Pv, _, _ = sim.pvec_all(full)
        geo = [i for i in range(22) if i != 14]                        # 14 = InpMinRangeAtr is a hand filter (C 0.75, universe 0)
        if P is not None and not np.array_equal(P[geo], Pv[geo]):
            raise RuntimeError("C and UNIVERSE-C differ in the shape / EMA / touch inputs - the setup geometry must be the same")
        P = Pv
        out[src] = {"trades": tr, "setups": setups[:, :].copy(), "stats": stats, "secs": round(time.time() - t0, 1)}
    return out, P


def check_entries(runs, E):
    """the re-run must reproduce simdata/mlx_entries_C.npz trade for trade"""
    rep = {}
    for src in (0, 1):
        m = E["src"] == src
        tr = runs[src]["trades"]
        rep[str(src)] = {"n_file": int(m.sum()), "n_rerun": int(len(tr)),
                         "entry_t_equal": bool(len(tr) == m.sum() and np.array_equal(tr[:, 1].astype(np.int64), E["entry_t"][m])),
                         "k15_equal": bool(len(tr) == m.sum() and np.array_equal(tr[:, 11].astype(np.int64), E["k15"][m])),
                         "pnl_equal": bool(len(tr) == m.sum() and np.allclose(tr[:, 6], E["pnl"][m]))}
    return rep


def match_setups(ek, side, setups, pleft):
    """per trade: the last setups row (k15, side, kind) with k15 < entry k15 and the same side.
    -> k_setup (-1 none), kind (0 none), ok (within pleft bars), last_any (that row is also the last setup of any side)"""
    sk = setups[:, 0].astype(np.int64)
    ss = setups[:, 1].astype(np.int64)
    kd = setups[:, 2].astype(np.int64)
    n = len(ek)
    k_setup = np.full(n, -1, np.int64)
    kind = np.zeros(n, np.int64)
    last_any = np.zeros(n, bool)
    for sd in (1, -1):
        rows = np.nonzero(ss == sd)[0]
        tr = np.nonzero(side == sd)[0]
        if len(rows) == 0 or len(tr) == 0:
            continue
        j = np.searchsorted(sk[rows], ek[tr], side="left") - 1
        has = j >= 0
        r = rows[np.maximum(j, 0)]
        k_setup[tr[has]] = sk[r[has]]
        kind[tr[has]] = kd[r[has]]
        ja = np.searchsorted(sk, ek[tr], side="left") - 1
        last_any[tr[has]] = sk[np.maximum(ja, 0)][has] == sk[r[has]]
    ok = (k_setup >= 0) & (ek - k_setup >= 1) & (ek - k_setup <= pleft)
    return k_setup, kind, ok, last_any


# ---------------------------------------------------------------- the features
def _ema_rec(c, n):
    """the EA's EMA as sim.emas builds it for ds m15: sim.ema seeded with the first close (bit-identical to the tester's ef / es)"""
    return sim.ema(np.ascontiguousarray(c, dtype=np.float64), int(n), float(c[0]))


def _chop(c, i, el):
    """efficiency ratio at bars i over el bars, the EA's loop: net / path (0 when path <= 0 or i - el < 0)"""
    d = np.zeros(len(c))
    d[1:] = np.abs(np.diff(c))
    cs = np.concatenate([[0.0], np.cumsum(d)])          # cs[j] = sum d[0..j-1]
    i = np.asarray(i, np.int64)
    okm = i - el >= 0
    ii = np.maximum(i, el)
    net = np.abs(c[ii] - c[ii - el])
    path = cs[ii + 1] - cs[ii - el + 1]                  # sum d[ii-el+1 .. ii] = sum |c[ii-s] - c[ii-s-1]|, s = 0..el-1
    er = np.where((path > 0) & okm, net / np.where(path > 0, path, 1.0), 0.0)
    return er


def _online_v(o, h, l, c, e, side, P):
    """sim_full._online, vectorised"""
    tol = P[18] * 0.1
    if P[17] < 0.5:
        r = (l - tol <= e) & (h + tol >= e)
    else:
        r = np.where(side > 0, (l - tol <= e) & (np.minimum(o, c) >= e), (h + tol >= e) & (np.maximum(o, c) <= e))
    return r & (e > 0)


def setup_features(D, P, T, U, SK, ef=None, es=None):
    """the setup-state table for the trades T (dict of arrays: k15, side, entry_t, entry, sl, lots, k_setup, kind) with the universe
    U (entry_t, exit_t, pnl, side; exit_t may be hidden as a huge number with pnl NaN for trades still open) and the universe setups
    SK (k15, side). D may be truncated: bars > entry bar - 1 are never read except o15[entry bar].  -> X float64 [n x len(SETUP_NAMES)]"""
    o, h, l, c = (np.asarray(D[k], dtype=np.float64) for k in ("o15", "h15", "l15", "c15"))
    t15 = np.asarray(D["t15"], dtype=np.int64)
    atr = np.asarray(D["atr"], dtype=np.float64)
    adx = np.asarray(D["adx"], dtype=np.float64)
    if ef is None:
        ef, es = _ema_rec(c, P[0]), _ema_rec(c, P[1])
    e64, e256 = features.ema(np.ascontiguousarray(c), 64), features.ema(np.ascontiguousarray(c), 256)
    ke = np.asarray(T["k15"], np.int64)
    ks = np.asarray(T["k_setup"], np.int64)
    side = np.asarray(T["side"], np.float64)
    et = np.asarray(T["entry_t"], np.int64)
    en = np.asarray(T["entry"], np.float64)
    sl = np.asarray(T["sl"], np.float64)
    lots = np.asarray(T["lots"], np.float64)
    kind = np.asarray(T["kind"], np.float64)
    n = len(ke)
    s = np.maximum(ks, 0)
    e1 = ke - 1
    a_s = np.maximum(atr[s], 1e-6)
    a_e = np.maximum(atr[e1], 1e-6)
    rng = np.maximum(h[s] - l[s], 1e-6)
    F = {}
    F["kind"] = kind
    F["kind_pin"] = (kind == 1) * 1.0
    F["kind_ham"] = (kind == 2) * 1.0
    F["kind_maru"] = (kind == 3) * 1.0
    on_f = _online_v(o[s], h[s], l[s], c[s], ef[s], side, P)
    on_s = _online_v(o[s], h[s], l[s], c[s], es[s], side, P)
    F["on_fast"] = on_f * 1.0
    F["on_slow"] = on_s * 1.0
    F["ema_which"] = on_f * 1.0 + on_s * 2.0
    rules_ok = (P[15] != 1) & on_f & ~((P[19] > 0.5) & (es[s] <= h[s]))
    inv_ok = (P[15] != 0) & on_s & ~((P[19] > 0.5) & (ef[s] <= h[s]))
    F["buy_rule"] = np.where(side > 0, np.where(rules_ok, 1.0, np.where(inv_ok, 2.0, 0.0)), 0.0)
    F["bars_to_entry"] = (ke - ks).astype(np.float64)
    F["entry_min_in_bar"] = (et - t15[ke]) / 60.0
    F["s_range_atr"] = (h[s] - l[s]) / a_s
    F["s_body"] = np.abs(c[s] - o[s]) / rng
    F["s_uwick"] = (h[s] - np.maximum(o[s], c[s])) / rng
    F["s_lwick"] = (np.minimum(o[s], c[s]) - l[s]) / rng
    F["s_clpos"] = (c[s] - l[s]) / rng
    F["s_dir_rel"] = np.sign(c[s] - o[s]) * side
    for nm, px in (("c", c), ("h", h), ("l", l)):
        F["s_%s_ef_rel" % nm] = (px[s] - ef[s]) * side / a_s
        F["s_%s_es_rel" % nm] = (px[s] - es[s]) * side / a_s
    F["s_gap_atr"] = np.abs(ef[s] - es[s]) / a_s
    F["s_gap_pips"] = np.abs(ef[s] - es[s]) / PIP
    F["s_align_rel"] = (ef[s] - es[s]) * side / a_s
    F["e_gap_atr"] = np.abs(ef[e1] - es[e1]) / a_e
    F["e_gap_pips"] = np.abs(ef[e1] - es[e1]) / PIP
    F["e_align_rel"] = (ef[e1] - es[e1]) * side / a_e
    for lb in (4, 16):
        F["s_ef_slope%d_rel" % lb] = (ef[s] - ef[np.maximum(s - lb, 0)]) * side / a_s
        F["s_es_slope%d_rel" % lb] = (es[s] - es[np.maximum(s - lb, 0)]) * side / a_s
        F["e_ef_slope%d_rel" % lb] = (ef[e1] - ef[np.maximum(e1 - lb, 0)]) * side / a_e
        F["e_es_slope%d_rel" % lb] = (es[e1] - es[np.maximum(e1 - lb, 0)]) * side / a_e
    for el in (10, 16, 20):
        F["s_chop_er%d" % el] = _chop(c, s, el)
    F["s_ema64_rel"] = (c[s] - e64[s]) * side / a_s
    F["s_ema256_rel"] = (c[s] - e256[s]) * side / a_s
    F["s_disp_64_256_rel"] = (e64[s] - e256[s]) * side / a_s
    F["s_adx"] = adx[s]
    F["s_atr_r_e"] = atr[s] / a_e
    ext = np.where(side > 0, h[s], l[s])                             # the setup extreme the entry breaks
    lvl = ext + side * P[21] * PIP
    F["level_rel"] = (lvl - ext) * side / a_e
    F["brk_dist_atr"] = (en - ext) * side / a_e
    F["brk_dist_pips"] = (en - ext) * side / PIP
    F["open_vs_level_rel"] = (o[ke] - lvl) * side / a_e
    F["entry_vs_sclose_rel"] = (en - c[s]) * side / a_e
    oth = np.where(side > 0, l[s], h[s])                             # the setup candle's other extreme
    F["s_risk_atr"] = (en - oth) * side / a_e
    F["s_risk_pips"] = (en - oth) * side / PIP
    risk = np.abs(en - sl)
    F["stop_atr"] = risk / a_e
    F["stop_pips"] = risk / PIP
    F["stop_usd"] = risk * lots * 100.0
    F["tp_over_stop"] = np.where(risk > 0, P[sim_full.F["InpFixTpPips"]] * PIP / np.where(risk > 0, risk, 1.0), 0.0)
    # universe state: trades entered before / closed before this entry
    u_et = np.asarray(U["entry_t"], np.int64)
    u_xt = np.asarray(U["exit_t"], np.int64)
    u_pnl = np.asarray(U["pnl"], np.float64)
    u_sd = np.asarray(U["side"], np.int64)
    for tag, msk in (("", np.ones(len(u_et), bool)), ("_b", u_sd > 0), ("_s", u_sd < 0)):
        es_ = np.sort(u_et[msk])
        xs_ = np.sort(u_xt[msk])
        same = np.sort(u_et[msk & (u_xt == u_et)])                  # entered and exited in the same second (exit_t <= t but entry_t == t: not 'before')
        closed = np.searchsorted(xs_, et, side="right") - (np.searchsorted(same, et, side="right") - np.searchsorted(same, et, side="left"))
        F["_nopen" + tag] = (np.searchsorted(es_, et, side="left") - closed).astype(np.float64)
    F["n_open"] = F.pop("_nopen")
    nb, nsl = F.pop("_nopen_b"), F.pop("_nopen_s")
    F["n_open_same"] = np.where(side > 0, nb, nsl)
    F["n_open_opp"] = np.where(side > 0, nsl, nb)
    order = np.argsort(u_xt, kind="stable")
    xs, ps = u_xt[order], u_pnl[order]
    ws = (ps > 0) * 1.0
    cp = np.concatenate([[0.0], np.cumsum(ps)])
    cw = np.concatenate([[0.0], np.cumsum(ws)])
    idx = np.searchsorted(xs, et, side="left")                       # closed strictly before entry_t: xs[:idx]
    for N in (1, 3, 10):
        j0 = np.maximum(idx - N, 0)
        cnt = (idx - j0).astype(np.float64)
        sp = cp[idx] - cp[j0]
        sw = cw[idx] - cw[j0]
        if N == 1:
            F["prev1_pnl"], F["prev1_win"] = sp, sw
        else:
            F["prev%d_pnl" % N] = sp
            F["prev%d_wr" % N] = np.where(cnt > 0, sw / np.where(cnt > 0, cnt, 1.0), 0.0)
        if N == 10:
            F["prev_n10"] = cnt
    last_x = np.where(idx > 0, xs[np.maximum(idx - 1, 0)], et)
    F["since_close_min"] = np.minimum((et - last_x) / 60.0, 7 * 1440.0)
    day0 = (et // 86400) * 86400
    jd = np.searchsorted(xs, day0, side="left")
    F["day_pnl"] = np.where(idx > jd, cp[idx] - cp[np.minimum(jd, idx)], 0.0)
    F["day_closed_n"] = np.maximum(idx - jd, 0).astype(np.float64)
    es_all = np.sort(u_et)
    F["day_opened_n"] = (np.searchsorted(es_all, et, side="left") - np.searchsorted(es_all, day0, side="left")).astype(np.float64)
    sk = np.asarray(SK["k15"], np.int64)
    ssd = np.asarray(SK["side"], np.int64)
    for tag, msk in (("", np.ones(len(sk), bool)), ("_b", ssd > 0), ("_s", ssd < 0)):
        kk = np.sort(sk[msk])
        F["_st" + tag] = (np.searchsorted(kk, ke, side="left") - np.searchsorted(kk, ke - 20, side="left")).astype(np.float64)
    F["setups_20"] = F.pop("_st")
    stb, sts = F.pop("_st_b"), F.pop("_st_s")
    F["setups_opp_20"] = np.where(side > 0, sts, stb)
    F["hour"] = ((et // 3600) % 24).astype(np.float64)
    F["minute"] = ((et // 60) % 60).astype(np.float64)
    F["dow"] = ((et // 86400 + 4) % 7).astype(np.float64)
    F["side"] = side
    X = np.empty((n, len(SETUP_NAMES)))
    for j, name in enumerate(SETUP_NAMES):
        X[:, j] = F[name]
    return X


# ---------------------------------------------------------------- build
def build(c_file=C_FILE, entries=ENTRIES_C, dataset=DATASET, out=OUT, spec=SPEC, ds="m15"):
    T0 = time.time()
    E = {k: v for k, v in np.load(entries).items()}
    rep = {"entries_file": str(entries), "n": int(len(E["k15"])), "by_src": {str(s): int((E["src"] == s).sum()) for s in (0, 1)}}
    t0 = time.time()
    runs, P = run_setups(c_file, ds)
    rep["sim_s"] = round(time.time() - t0, 1)
    rep["rerun_matches_file"] = check_entries(runs, E)
    rep["setups"] = {str(s): int(len(runs[s]["setups"])) for s in (0, 1)}
    D = sim.data(ds)
    ef, es = sim.emas(P[0], P[1], ds)
    pleft = int(P[20])
    n = rep["n"]
    k_setup = np.full(n, -1, np.int64)
    kind = np.zeros(n, np.int64)
    ok = np.zeros(n, bool)
    last_any = np.zeros(n, bool)
    rep["setup_match"] = {}
    for src in (0, 1):
        m = E["src"] == src
        ks, kd, okm, la = match_setups(E["k15"][m], E["side"][m], runs[src]["setups"], pleft)
        k_setup[m], kind[m], ok[m], last_any[m] = ks, kd, okm, la
        # the recorded setup must be the shape the tester saw: re-run _shape on that candle
        kk = np.maximum(ks, 0)
        sh = np.array([sim_full._shape(D["o15"][i], D["h15"][i], D["l15"][i], D["c15"][i], D["atr"][i], P)[1] for i in kk])
        rep["setup_match"][str(src)] = {"trades": int(m.sum()), "no_setup": int((ks < 0).sum()), "beyond_pleft": int(((ks >= 0) & ~okm).sum()),
                                        "pleft": pleft, "kind_agrees": int((sh == kd)[ks >= 0].sum()), "not_last_any_side": int((~la)[ks >= 0].sum()),
                                        "bars_to_entry_hist": {str(b): int(((E["k15"][m] - ks) == b)[ks >= 0].sum()) for b in range(1, pleft + 1)}}
    T = {"k15": E["k15"], "side": E["side"], "entry_t": E["entry_t"], "entry": E["entry"], "sl": E["sl"], "lots": E["lots"], "k_setup": k_setup, "kind": kind}
    um = E["src"] == 1
    U = {k: E[k][um] for k in ("entry_t", "exit_t", "pnl", "side")}
    SK = {"k15": runs[1]["setups"][:, 0].astype(np.int64), "side": runs[1]["setups"][:, 1].astype(np.int64)}
    t0 = time.time()
    Xs = setup_features(D, P, T, U, SK, ef, es)
    rep["features_s"] = round(time.time() - t0, 2)
    bad = ~np.isfinite(Xs)
    rep["setup_nan_inf_fixed"] = int(bad.sum())
    rep["setup_nan_by_feature"] = {SETUP_NAMES[j]: int(bad[:, j].sum()) for j in range(bad.shape[1]) if bad[:, j].any()}
    Xs = np.where(bad, 0.0, Xs).astype(np.float32)
    # the 85 bar features of the last closed bar (k15 == entry k15 - 1)
    Z = np.load(dataset)
    row_of = np.full(int(Z["k15"].max()) + 2, -1, np.int64)
    row_of[Z["k15"]] = np.arange(len(Z["k15"]))
    want = E["k15"] - 1
    rows = np.where((want >= 0) & (want < len(row_of)), row_of[np.clip(want, 0, len(row_of) - 1)], -1)
    bar_ok = rows >= 0
    Xb = np.zeros((n, Z["X"].shape[1]), np.float32)
    Xb[bar_ok] = Z["X"][rows[bar_ok]]
    rep["bar_join"] = {"joined": int(bar_ok.sum()), "missing_filled_0": int((~bar_ok).sum())}
    # labels
    pnl = E["pnl"].astype(np.float64)
    risk_usd = np.abs(E["entry"] - E["sl"]) * E["lots"] * 100.0
    r_mult = np.where(risk_usd > 0, pnl / np.where(risk_usd > 0, risk_usd, 1.0), 0.0)
    y_win = (pnl > 0).astype(np.int8)
    full_stop = (pnl <= FULL_STOP).astype(np.int8)
    year = years_of(E["entry_t"])
    same_tick = (E["exit_t"] == E["entry_t"]).astype(np.int8)        # opened and closed in the same second (a tester artefact: unlearnable from the setup)
    rep["same_tick_exit"] = {"n": int(same_tick.sum()), "by_src": {str(s): int(same_tick[E["src"] == s].sum()) for s in (0, 1)},
                             "net": round(float(pnl[same_tick == 1].sum()), 0), "wins": int(((pnl > 0) & (same_tick == 1)).sum())}
    rep["constant_features"] = [SETUP_NAMES[j] for j in range(Xs.shape[1]) if Xs[:, j].min() == Xs[:, j].max()]
    rep["n_open_range"] = [float(Xs[:, SETUP_NAMES.index("n_open")].min()), float(Xs[:, SETUP_NAMES.index("n_open")].max())]
    np.savez_compressed(out, X_setup=Xs, setup_names=np.array(SETUP_NAMES), X_bar=Xb, bar_names=Z["names"], side=E["side"].astype(np.int8),
                        entry_t=E["entry_t"].astype(np.int64), exit_t=E["exit_t"].astype(np.int64), k15=E["k15"].astype(np.int64),
                        src=E["src"].astype(np.int8), pnl=pnl, y_win=y_win, full_stop=full_stop, reason=E["reason"].astype(np.int8), year=year,
                        k_setup=k_setup, kind=kind.astype(np.int8), setup_ok=ok.astype(np.int8), r_mult=r_mult.astype(np.float32),
                        entry=E["entry"], sl=E["sl"], lots=E["lots"], bar_row_ok=bar_ok.astype(np.int8), exit_k15=E["exit_k15"].astype(np.int64),
                        same_tick_exit=same_tick)
    spec_doc = {"file": str(out), "built": datetime.now().strftime("%Y-%m-%d %H:%M"), "setting_c": str(c_file), "n_rows": n,
                "conventions": {"_rel": "multiplied by side (+1 buy / -1 sell): positive = in the trade's favour", "atr": "the tester's iATR column (D['atr'])",
                                "pip": PIP, "ema_fast": int(P[0]), "ema_slow": int(P[1]), "break_pips": float(P[21]), "break_bars": pleft,
                                "universe": "src 1 = UNIVERSE-C (setting C with every hand entry filter off, InpMaxPos 8); state features use src 1 for both srcs",
                                "label": {"y_win": "pnl > 0", "full_stop": "pnl <= %.0f" % FULL_STOP, "r_mult": "pnl / (|entry - sl| x lots x 100)"}},
                "setup_features": [{"i": i, "name": nm, "def": d} for i, (nm, d) in enumerate(SPEC_ROWS)],
                "bar_features": "the 85 of mlx/FEATURE_SPEC.md at bar k15 - 1 (X_bar, bar_names)"}
    Path(spec).write_text(json.dumps(spec_doc, indent=1), encoding="utf-8")
    rep["label"] = {"y_win": int(y_win.sum()), "full_stops": int(full_stop.sum()), "worst": float(pnl.min()),
                    "by_src": {str(s): {"n": int((E["src"] == s).sum()), "wr": round(100.0 * float(y_win[E["src"] == s].mean()), 2),
                                        "net": round(float(pnl[E["src"] == s].sum()), 0), "full_stops": int(full_stop[E["src"] == s].sum()),
                                        "worst": float(pnl[E["src"] == s].min())} for s in (0, 1)},
                    "by_year_universe": {str(y): {"n": int(((year == y) & um).sum()), "wr": round(100.0 * float(y_win[(year == y) & um].mean()), 2),
                                                  "net": round(float(pnl[(year == y) & um].sum()), 0)} for y in np.unique(year)},
                    "reasons": {str(int(r)): int((E["reason"] == r).sum()) for r in np.unique(E["reason"])}}
    rep["shape"] = {"X_setup": list(Xs.shape), "X_bar": list(Xb.shape)}
    rep["files"] = [str(out), str(spec)]
    rep["total_s"] = round(time.time() - T0, 1)
    _CTX.update({"D": D, "P": P, "T": T, "U": U, "SK": SK, "ef": ef, "es": es, "Xs_raw": None})
    return rep


_CTX = {}


# ---------------------------------------------------------------- leakage check
def check_leakage(picks=5, seed=1, out=OUT):
    """for `picks` random trades: every setup feature recomputed with the world truncated at the entry minute - bars after the entry bar's
    open removed (the entry bar keeps only its open), universe entries with entry_t >= this entry_t removed, still-open trades' exit_t hidden
    (2^62) and their pnl set to NaN - must equal the saved row bit for bit"""
    if not _CTX:
        raise RuntimeError("build() first (the context of the full computation is needed)")
    D, P, T, U, SK = _CTX["D"], _CTX["P"], _CTX["T"], _CTX["U"], _CTX["SK"]
    Z = np.load(out)
    Xs = Z["X_setup"]
    rng = np.random.default_rng(seed)
    n = len(T["k15"])
    res = []
    for i in sorted(int(v) for v in rng.choice(n, size=picks, replace=False)):
        ke, et = int(T["k15"][i]), int(T["entry_t"][i])
        Dt = {k: np.asarray(D[k])[:ke + 1].copy() for k in ("t15", "hr15", "o15", "h15", "l15", "c15", "atr", "adx")}
        for k in ("h15", "l15", "c15", "atr", "adx"):
            Dt[k][ke] = np.nan                                       # the entry bar is still forming: only its open is known
        keep = U["entry_t"] < et
        Ut = {k: U[k][keep].copy() for k in U}
        openm = Ut["exit_t"] >= et
        Ut["exit_t"] = np.where(openm, np.int64(2 ** 62), Ut["exit_t"])
        Ut["pnl"] = np.where(openm, np.nan, Ut["pnl"])
        SKt = {k: SK[k][SK["k15"] < ke] for k in SK}
        Tt = {k: np.asarray(T[k])[i:i + 1] for k in T}
        row = setup_features(Dt, P, Tt, Ut, SKt)[0]
        row = np.where(np.isfinite(row), row, 0.0).astype(np.float32)
        full = Xs[i]
        diff = np.abs(row.astype(np.float64) - full.astype(np.float64))
        res.append({"i": i, "src": int(Z["src"][i]), "t": _iso(et), "k15": ke, "k_setup": int(T["k_setup"][i]), "identical": bool(np.array_equal(row, full)),
                    "max_abs_diff": float(diff.max()), "differing": [SETUP_NAMES[j] for j in np.nonzero(diff > 0)[0]][:10],
                    "universe_rows_used": int(keep.sum()), "hidden_open": int(openm.sum())})
    return res


# ---------------------------------------------------------------- CLI
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--picks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args(argv)
    rep = build()
    print(json.dumps(rep, indent=1, default=str), flush=True)
    if not a.no_check:
        t0 = time.time()
        chk = check_leakage(picks=a.picks, seed=a.seed)
        print(json.dumps({"leakage": chk, "check_s": round(time.time() - t0, 1)}, indent=1), flush=True)
        rep["leakage"] = chk
    return rep


if __name__ == "__main__":
    main()
