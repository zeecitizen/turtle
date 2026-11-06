"""mlx/meta_seq.py - agent S: can a SEQUENCE model "read the candles more fluently" than the if-else filters?

META-LABELLING head-to-head on UNIVERSE-C (simdata/mlx_meta.npz src 1: setting C with every hand entry filter off, 12,579 trades, WR 92.2%):
a small 1D-CNN (torch, CPU, < 200k params) on the RAW path of the last L = 48 closed M15 candles before the entry bar (o/h/l/c and the EA's
EMA 20 / 62, side-relative, normalised by the last close and the tester's ATR; range and ATR ratio as extra channels) plus a static vector
(hour / dow one-hot, side, minute-in-bar; optionally the 75-column setup-state block of mlx/meta_features.py), trained to predict y_win.

LOYO PROTOCOL (every out-of-sample number): hold out one calendar year of entry_t (2022's 27 Dec-29/30 rows are folded into 2023), train on
the other years minus (a) trades whose exit_t falls inside the held-out year, (b) trades whose entry_t is within a 2-day embargo of either
end of the held-out year; early stopping on an inner time split (the last 15 % of the training trades, with its own 2-day embargo); seeds
fixed, 3 seeds, the ensemble mean is the reported P and the per-seed spread is reported too.

COMMON EVALUATION (shared with agent T so the approaches compare): pooled OOS AUC(win) and log-loss vs the class-frequency baseline; the
FRONTIER (thresholds on P and top-N by P: n / WR / net / worst / full stops, pooled and per year); BASELINES: random subset of the same size,
an hour/dow-only model (the same learner, static branch only on hour, dow, bar_of_day, side), setting C's hand filters IN-SAMPLE (Zee's
standard: 1,615 / 97.2 % / +$402,831 / 43 full stops), the ML's top-1615 per year beside C's per-year n / WR / net; b_scores (where C's own
trades sit in the ML's ranking, what the ML's picks do on the trades C rejected); feature signal (grouped permutation importance, OOS).
THE CANDLE CLAIM: the same CNN trained on the same windows to predict the NEXT bar's direction and the next-24-bar sign (all 89k dataset
bars, LOYO), accuracy / AUC vs 0.5 - the honest answer to "can we predict candles fluently".

Outputs (agent S owns them): simdata/mlx_meta_results_seq.json, simdata/mlx_meta_pred_seq.npz (P, entry_t, side, src), simdata/mlx_meta_seq_models/
(win model trained on all four years, ONNX opset 15, inputs seq [1, L, C] + static [1, S], onnxruntime verified against torch).
CLI: py -m mlx.meta_seq [--quick] [--seeds 3] [--epochs 60] [--no-candles] [--no-onnx]   (from monitor/saad_view)
CLAUDE.md: every P&L / WR here is a Turtle TV Tester HYPOTHESIS (the universe's pnl column is the tester's); nothing is promoted until MT5."""
import argparse
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
import torch                                           # noqa: E402
import torch.nn as nn                                  # noqa: E402
import torch.nn.functional as F                        # noqa: E402
from sklearn.metrics import log_loss, roc_auc_score   # noqa: E402

SIMDATA = VIEW / "simdata"
META = SIMDATA / "mlx_meta.npz"
DATASET = SIMDATA / "mlx_dataset.npz"
OUT_JSON = SIMDATA / "mlx_meta_results_seq.json"
OUT_NPZ = SIMDATA / "mlx_meta_pred_seq.npz"
OUT_DIR = SIMDATA / "mlx_meta_seq_models"
FULL_STOP = -4000.0
DAY = 86400
EMBARGO_S = 2 * DAY
L = 48                                                  # closed M15 candles before the entry bar
CHANNELS = ["o_rel", "h_rel", "l_rel", "c_rel", "ef_rel", "es_rel", "range_atr", "log_atr_ratio"]
THRESHOLDS = [0.90, 0.93, 0.95, 0.96, 0.97, 0.98, 0.985, 0.99]
TOPS = [800, 1000, 1200, 1615, 2000, 2500, 3000, 4000]
DROP_STATIC = {"on_fast", "stop_pips", "stop_usd", "tp_over_stop", "buy_rule", "hour", "minute", "dow", "side"}   # constants + the time block (given separately)
C_STD = {"n": 1615, "wr": 97.15, "net": 402831.0, "full_stops": 43, "worst": -5574.0,
         "per_year": {"2023": {"n": 256, "wr": 97.3, "net": 64756}, "2024": {"n": 432, "wr": 97.2, "net": 107117},
                      "2025": {"n": 498, "wr": 96.4, "net": 97679}, "2026": {"n": 424, "wr": 97.9, "net": 130926}}}

torch.set_num_threads(max(1, min(8, os.cpu_count() or 4)))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- inputs
def load_meta():
    z = np.load(META, allow_pickle=True)
    M = {k: z[k] for k in z.files}
    yr = M["year"].copy()
    yr[yr == 2022] = 2023                                # 27 universe + 5 C rows of Dec 29-30 2022: folded into 2023
    M["fold_year"] = yr
    return M


def load_bars():
    import sim
    D = sim.data("m15")
    return {k: np.asarray(D[k], dtype=np.float64) for k in ("o15", "h15", "l15", "c15", "ef", "es", "atr")} | {"t15": np.asarray(D["t15"], dtype=np.int64),
                                                                                                                 "hr15": np.asarray(D["hr15"], dtype=np.int64)}


def ema(c, n):
    a = 2.0 / (n + 1)
    e = np.empty_like(c)
    e[0] = c[0]
    for i in range(1, len(c)):
        e[i] = e[i - 1] + a * (c[i] - e[i - 1])
    return e


def seq_windows(B, k_last, side, L=L, ef=None, es=None):
    """[n, L, C] float32: bars k_last-L+1 .. k_last, prices side-relative to the last close in ATR units; k clamped at 0 (warm-up rows)"""
    ef = B["ef"] if ef is None else ef
    es = B["es"] if es is None else es
    idx = k_last[:, None] - np.arange(L - 1, -1, -1)[None, :]
    idx = np.clip(idx, 0, len(B["c15"]) - 1)
    cl = B["c15"][k_last][:, None]
    a = np.maximum(B["atr"][k_last], 1e-6)[:, None]
    s = side.astype(np.float64)[:, None]
    X = np.empty((len(k_last), L, len(CHANNELS)), dtype=np.float32)
    for j, col in enumerate(("o15", "h15", "l15", "c15")):
        X[:, :, j] = (B[col][idx] - cl) * s / a
    X[:, :, 4] = (ef[idx] - cl) * s / a
    X[:, :, 5] = (es[idx] - cl) * s / a
    X[:, :, 6] = (B["h15"][idx] - B["l15"][idx]) / a
    X[:, :, 7] = np.log(np.maximum(B["atr"][idx], 1e-6) / a)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def time_static(hour, dow, side, minute=None):
    """hour one-hot (24) + dow one-hot (7) + side + sin/cos hour + minute-in-bar/15 -> [n, 36]"""
    n = len(hour)
    S = np.zeros((n, 36), dtype=np.float32)
    S[np.arange(n), hour.astype(int) % 24] = 1
    S[np.arange(n), 24 + dow.astype(int) % 7] = 1
    S[:, 31] = side
    S[:, 32] = np.sin(2 * np.pi * hour / 24)
    S[:, 33] = np.cos(2 * np.pi * hour / 24)
    S[:, 34] = 0 if minute is None else (minute % 15) / 15.0
    S[:, 35] = 1
    return S


TIME_NAMES = [f"hour_{h}" for h in range(24)] + [f"dow_{d}" for d in range(7)] + ["side", "hour_sin", "hour_cos", "min_in_bar", "bias"]


def setup_static(M):
    names = [str(x) for x in M["setup_names"]]
    keep = [i for i, nm in enumerate(names) if nm not in DROP_STATIC]
    return M["X_setup"][:, keep].astype(np.float32), [names[i] for i in keep]


# ---------------------------------------------------------------- the model
class SeqNet(nn.Module):
    """1D-CNN over [B, L, C] (channel-last input, as the ONNX contract) + an MLP on the static vector; one logit"""

    def __init__(self, n_ch, n_static, width=32, use_seq=True, use_static=True, drop=0.2):
        super().__init__()
        self.use_seq, self.use_static = use_seq, use_static
        if use_seq:
            self.c1 = nn.Conv1d(n_ch, width, 5, padding=2)
            self.c2 = nn.Conv1d(width, 2 * width, 5, padding=4, dilation=2)
            self.c3 = nn.Conv1d(2 * width, 2 * width, 3, padding=1)
            self.seq_out = 4 * width
        else:
            self.seq_out = 0
        if use_static:
            self.s1 = nn.Linear(n_static, 2 * width)
            self.st_out = 2 * width
        else:
            self.st_out = 0
        self.h1 = nn.Linear(self.seq_out + self.st_out, 2 * width)
        self.h2 = nn.Linear(2 * width, 1)
        self.drop = nn.Dropout(drop)

    def forward(self, seq, static):
        parts = []
        if self.use_seq:
            x = seq.permute(0, 2, 1)
            x = F.gelu(self.c1(x))
            x = F.gelu(self.c2(x))
            x = F.gelu(self.c3(x))
            parts.append(torch.cat([x.mean(dim=2), x.amax(dim=2)], dim=1))
        if self.use_static:
            parts.append(F.gelu(self.s1(static)))
        h = torch.cat(parts, dim=1) if len(parts) > 1 else parts[0]
        h = self.drop(F.gelu(self.h1(self.drop(h))))
        return self.h2(h).squeeze(1)


def n_params(m):
    return sum(p.numel() for p in m.parameters())


class Scaler:
    def __init__(self, X):
        self.mean = X.mean(0)
        self.scale = X.std(0)
        self.scale[self.scale < 1e-8] = 1.0

    def __call__(self, X):
        return ((X - self.mean) / self.scale).astype(np.float32)


def fit(seq, st, y, tr, va, seed, use_seq=True, use_static=True, epochs=60, patience=8, lr=2e-3, batch=256, width=32):
    """train on tr, early-stop on va (log-loss); returns the model at its best va epoch and the trace"""
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = SeqNet(seq.shape[2], st.shape[1], width=width, use_seq=use_seq, use_static=use_static)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    Xs, Xt, Y = torch.from_numpy(seq), torch.from_numpy(st), torch.from_numpy(y.astype(np.float32))
    tr_t = torch.from_numpy(tr)
    best, best_state, bad, trace = 1e9, None, 0, []
    g = torch.Generator().manual_seed(seed)
    for ep in range(epochs):
        model.train()
        perm = tr_t[torch.randperm(len(tr_t), generator=g)]
        for i in range(0, len(perm), batch):
            b = perm[i:i + batch]
            opt.zero_grad()
            loss = F.binary_cross_entropy_with_logits(model(Xs[b], Xt[b]), Y[b])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()
        model.eval()
        with torch.no_grad():
            lv = F.binary_cross_entropy_with_logits(model(Xs[va], Xt[va]), Y[va]).item()
        trace.append(round(lv, 5))
        if lv < best - 1e-5:
            best, bad = lv, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, {"best_val_logloss": round(best, 5), "epochs_run": len(trace), "best_epoch": int(np.argmin(trace)) + 1}


def predict(model, seq, st, idx, batch=4096):
    out = np.empty(len(idx), dtype=np.float64)
    with torch.no_grad():
        for i in range(0, len(idx), batch):
            b = idx[i:i + batch]
            out[i:i + len(b)] = torch.sigmoid(model(torch.from_numpy(seq[b]), torch.from_numpy(st[b]))).numpy()
    return out


# ---------------------------------------------------------------- LOYO
def year_bounds(y):
    a = int(datetime(y, 1, 1, tzinfo=timezone.utc).timestamp())
    b = int(datetime(y + 1, 1, 1, tzinfo=timezone.utc).timestamp())
    return a, b


def loyo_split(entry_t, exit_t, fold_year, year):
    """held-out = fold_year == year; train = the rest minus exits inside the year and entries within 2 days of its ends; inner val = last 15 % of train by entry_t (2-day gap)"""
    held = fold_year == year
    a, b = year_bounds(year)
    if year == 2023:                                     # 2022's Dec rows are in this fold
        a = int(datetime(2022, 12, 1, tzinfo=timezone.utc).timestamp())
    bad = held | ((exit_t >= a) & (exit_t < b)) | ((entry_t >= a - EMBARGO_S) & (entry_t < b + EMBARGO_S))
    train = np.nonzero(~bad)[0]
    train = train[np.argsort(entry_t[train], kind="stable")]
    cut = int(len(train) * 0.85)
    t_cut = entry_t[train[cut]]
    inner_tr = train[entry_t[train] < t_cut - EMBARGO_S]
    inner_va = train[cut:]
    return np.nonzero(held)[0], inner_tr, inner_va, train


def loyo_run(name, seq, st_raw, y, M, years, seeds, use_seq, use_static, epochs, static_cols=None, progress=True):
    """OOS P for every universe trade (ensemble mean over seeds) + per-seed / per-year diagnostics"""
    n = len(y)
    P_seeds = np.full((len(seeds), n), np.nan)
    diag = {"per_year": {}, "per_seed_auc": {}, "fit": {}}
    for year in years:
        held, itr, iva, train = loyo_split(M["entry_t"], M["exit_t"], M["fold_year"], year)
        sc = Scaler(st_raw[train]) if use_static else None
        st = sc(st_raw) if use_static else np.zeros((n, 1), dtype=np.float32)
        if use_static and static_cols is not None:
            st = st[:, static_cols]
        fits = []
        for si, seed in enumerate(seeds):
            model, info = fit(seq, st, y, itr, iva, seed, use_seq=use_seq, use_static=use_static, epochs=epochs)
            P_seeds[si, held] = predict(model, seq, st, held)
            fits.append(info)
        diag["fit"][str(year)] = {"n_train": int(len(train)), "n_inner_val": int(len(iva)), "n_held": int(len(held)), "fits": fits, "n_params": n_params(model)}
        Pm = np.nanmean(P_seeds[:, held], axis=0)
        yr_auc = roc_auc_score(y[held], Pm) if 0 < y[held].mean() < 1 else float("nan")
        diag["per_year"][str(year)] = {"auc": round(float(yr_auc), 4), "n": int(len(held)),
                                       "seed_auc": [round(float(roc_auc_score(y[held], P_seeds[si, held])), 4) for si in range(len(seeds))]}
        if progress:
            log(f"  [{name}] held {year}: n_train {len(train)} n_held {len(held)} AUC {yr_auc:.4f} seeds {diag['per_year'][str(year)]['seed_auc']} "
                f"epochs {[f['epochs_run'] for f in fits]}")
    P = np.nanmean(P_seeds, axis=0)
    for si in range(len(seeds)):
        diag["per_seed_auc"][str(seeds[si])] = round(float(roc_auc_score(y, P_seeds[si])), 4)
    diag["seed_spread_auc"] = round(float(np.std([v for v in diag["per_seed_auc"].values()])), 4)
    diag["seed_pairwise_corr_P"] = round(float(np.mean([np.corrcoef(P_seeds[i], P_seeds[j])[0, 1] for i in range(len(seeds)) for j in range(i + 1, len(seeds))])), 4) if len(seeds) > 1 else None
    return P, P_seeds, diag


# ---------------------------------------------------------------- evaluation
def summ(pnl):
    n = len(pnl)
    if n == 0:
        return {"n": 0, "wr": None, "net": 0.0, "worst": None, "full_stops": 0}
    return {"n": int(n), "wr": round(float((pnl > 0).mean() * 100), 2), "net": round(float(pnl.sum()), 0), "worst": round(float(pnl.min()), 0),
            "full_stops": int((pnl <= FULL_STOP).sum())}


def frontier(P, pnl, fold_year, years):
    rows = []
    order = np.argsort(-P, kind="stable")
    for thr in THRESHOLDS:
        sel = P >= thr
        r = {"kind": "thr", "value": thr, **summ(pnl[sel]), "per_year": {str(y): summ(pnl[sel & (fold_year == y)]) for y in years}}
        rows.append(r)
    for N in TOPS:
        sel = np.zeros(len(P), bool)
        sel[order[:min(N, len(P))]] = True
        r = {"kind": "top", "value": N, **summ(pnl[sel]), "per_year": {str(y): summ(pnl[sel & (fold_year == y)]) for y in years}}
        rows.append(r)
    return rows


def random_baseline(pnl, fold_year, years, sizes, draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    out = {}
    for N in sizes:
        N = min(N, len(pnl))
        wr, net, worst, fs = [], [], [], []
        for _ in range(draws):
            pick = rng.choice(len(pnl), N, replace=False)
            s = pnl[pick]
            wr.append((s > 0).mean() * 100); net.append(s.sum()); worst.append(s.min()); fs.append((s <= FULL_STOP).sum())
        out[str(N)] = {"n": int(N), "wr": round(float(np.mean(wr)), 2), "wr_p95": round(float(np.percentile(wr, 95)), 2), "wr_p99": round(float(np.percentile(wr, 99)), 2),
                       "net": round(float(np.mean(net)), 0), "net_p95": round(float(np.percentile(net, 95)), 0), "worst": round(float(np.mean(worst)), 0),
                       "full_stops": round(float(np.mean(fs)), 1)}
    return out


def oos_metrics(P, y, fold_year, years, M_train_rates):
    base = np.empty(len(y))
    for yv in years:
        base[fold_year == yv] = M_train_rates[yv]
    return {"auc": round(float(roc_auc_score(y, P)), 4), "logloss": round(float(log_loss(y, np.clip(P, 1e-6, 1 - 1e-6))), 5),
            "logloss_class_freq": round(float(log_loss(y, np.clip(base, 1e-6, 1 - 1e-6))), 5),
            "per_year": {str(yv): {"auc": round(float(roc_auc_score(y[fold_year == yv], P[fold_year == yv])), 4),
                                   "logloss": round(float(log_loss(y[fold_year == yv], np.clip(P[fold_year == yv], 1e-6, 1 - 1e-6))), 5),
                                   "logloss_class_freq": round(float(log_loss(y[fold_year == yv], np.clip(base[fold_year == yv], 1e-6, 1 - 1e-6))), 5)} for yv in years}}


def train_rates(M, U, years):
    out = {}
    for yv in years:
        _, _, _, train = loyo_split(M["entry_t"][U], M["exit_t"][U], M["fold_year"][U], yv)
        out[yv] = float(M["y_win"][U][train].mean())
    return out


def b_scores(P, M, U, Cidx, pnl_u, fold_year_u, years):
    """where setting C's own trades sit in the universe ranking; what the ML adds on the trades C rejected"""
    key_u = {(int(t), int(s)): i for i, (t, s) in enumerate(zip(M["entry_t"][U], M["side"][U]))}
    pos = np.array([key_u.get((int(t), int(s)), -1) for t, s in zip(M["entry_t"][Cidx], M["side"][Cidx])])
    matched = pos >= 0
    inC = np.zeros(len(U), bool)
    inC[pos[matched]] = True
    rank_pct = (np.argsort(np.argsort(-P)) / len(P))                       # 0 = highest P
    order = np.argsort(-P, kind="stable")
    top = np.zeros(len(P), bool)
    top[order[:1615]] = True
    rej = ~inC
    out = {"c_matched_in_universe": int(matched.sum()), "c_unmatched": int((~matched).sum()),
           "P_mean_C": round(float(P[inC].mean()), 4), "P_mean_rest": round(float(P[rej].mean()), 4),
           "P_median_C": round(float(np.median(P[inC])), 4), "P_median_rest": round(float(np.median(P[rej])), 4),
           "C_rank_pct_median": round(float(np.median(rank_pct[inC])), 4),
           "auc_C_vs_rest": round(float(roc_auc_score(inC.astype(int), P)), 4),
           "C_in_top1615": int((inC & top).sum()),
           "C_trades_oos_by_ML_P": summ(pnl_u[inC]),
           "top1615_on_C_rejected": summ(pnl_u[top & rej]),
           "top1615_on_C_accepted": summ(pnl_u[top & inC]),
           "C_rejected_universe": summ(pnl_u[rej]),
           "C_accepted_universe": summ(pnl_u[inC]),
           "union_C_plus_top1615": summ(pnl_u[inC | top]),
           "per_year_union": {str(y): summ(pnl_u[(inC | top) & (fold_year_u == y)]) for y in years}}
    # add-on frontier: C's trades + the best-P rejected trades, in steps
    rej_order = order[rej[order]]
    add = {}
    for k in (200, 400, 800, 1200, 2000):
        sel = inC.copy()
        sel[rej_order[:k]] = True
        add[str(k)] = {**summ(pnl_u[sel]), "added_only": summ(pnl_u[rej_order[:k]])}
    out["C_plus_topk_rejected"] = add
    return out, inC


def perm_importance(models_by_year, seq, st_scaled_by_year, y, M, U, years, groups, seq_groups, seed=0):
    """grouped permutation importance OOS: drop in AUC when a group of static columns (or a seq channel / time half) is shuffled across the held-out year"""
    rng = np.random.default_rng(seed)
    imp = {}
    for gname, cols in list(groups.items()) + list(seq_groups.items()):
        drops = []
        for year in years:
            held = np.nonzero(M["fold_year"] == year)[0]
            st = st_scaled_by_year[year]
            model = models_by_year[year]
            base = roc_auc_score(y[held], predict(model, seq, st, held))
            seq2, st2 = seq, st
            if gname in seq_groups:
                seq2 = seq.copy()
                kind, spec = cols
                perm = rng.permutation(len(held))
                if kind == "chan":
                    seq2[held, :, spec] = seq[held][perm][:, :, spec]
                else:                                                     # time slice
                    seq2[held, spec[0]:spec[1], :] = seq[held][perm][:, spec[0]:spec[1], :]
            else:
                st2 = st.copy()
                perm = rng.permutation(len(held))
                st2[np.ix_(held, cols)] = st[held][perm][:, cols]
            drops.append(base - roc_auc_score(y[held], predict(model, seq2, st2, held)))
        imp[gname] = round(float(np.mean(drops)), 4)
    return dict(sorted(imp.items(), key=lambda kv: -kv[1]))



# ---------------------------------------------------------------- label diagnostics (is there ANY learnable structure in y_win?)
def label_diagnostics(M, U, y, pnl_u, fy, MU, st_setup, st_time, years):
    """XGBoost on bar85+setup: LOYO vs contiguous 5-block purged CV (within-year structure?), y_win vs full_stop label; hour-WR transfer across years"""
    import xgboost as xgb
    X = np.concatenate([M["X_bar"][U], st_setup, st_time[:, 31:35]], axis=1)
    out = {}

    def xgbc():
        return xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.6, min_child_weight=20, reg_lambda=5.0, n_jobs=8, random_state=0)

    for lab_name, lab in (("y_win", y), ("full_stop", M["full_stop"][U].astype(np.int8))):
        P = np.full(len(lab), np.nan)
        Pin = []
        for yv in years:
            held, itr, iva, train = loyo_split(MU["entry_t"], MU["exit_t"], MU["fold_year"], yv)
            clf = xgbc().fit(X[train], lab[train])
            P[held] = clf.predict_proba(X[held])[:, 1]
            Pin.append(roc_auc_score(lab[train], clf.predict_proba(X[train])[:, 1]))
        out[f"xgb_loyo_{lab_name}"] = {"oos_auc": round(float(roc_auc_score(lab, P)), 4), "train_auc_mean": round(float(np.mean(Pin)), 4),
                                       "per_year_oos_auc": {str(yv): round(float(roc_auc_score(lab[fy == yv], P[fy == yv])), 4) for yv in years}}
        # contiguous 5 blocks by entry_t, 2-day embargo, exits inside the block purged
        order = np.argsort(MU["entry_t"], kind="stable")
        P2 = np.full(len(lab), np.nan)
        for blk in np.array_split(order, 5):
            a, b = MU["entry_t"][blk[0]], MU["entry_t"][blk[-1]]
            bad = np.zeros(len(lab), bool)
            bad[blk] = True
            bad |= (MU["exit_t"] >= a) & (MU["exit_t"] <= b)
            bad |= (MU["entry_t"] >= a - EMBARGO_S) & (MU["entry_t"] <= b + EMBARGO_S)
            tr = np.nonzero(~bad)[0]
            P2[blk] = xgbc().fit(X[tr], lab[tr]).predict_proba(X[blk])[:, 1]
        out[f"xgb_5block_{lab_name}"] = {"oos_auc": round(float(roc_auc_score(lab, P2)), 4)}
    hour = st_time[:, :24].argmax(1)
    tr_auc = {}
    for yv in years:
        tr, te = fy != yv, fy == yv
        hw = {h: y[tr & (hour == h)].mean() for h in range(24) if (tr & (hour == h)).sum() > 30}
        p = np.array([hw.get(h, y[tr].mean()) for h in hour[te]])
        tr_auc[str(yv)] = round(float(roc_auc_score(y[te], p)), 4)
    out["hour_wr_transfer_auc"] = tr_auc
    # loss clustering: WR of the universe conditioned on the previous universe trade's result (the strategy's own autocorrelation)
    prev = M["X_setup"][U, [str(x) for x in M["setup_names"]].index("prev1_win")]
    out["wr_after_prev_win"] = round(float(y[prev == 1].mean() * 100), 2)
    out["wr_after_prev_loss"] = round(float(y[prev == 0].mean() * 100), 2)
    return out


# ---------------------------------------------------------------- the candle claim
def candle_test(B, years, seeds, epochs, quick=False):
    """next-bar direction and next-24-bar sign from the same 48-candle windows, LOYO by year of the bar; accuracy / AUC vs 0.5"""
    d = np.load(DATASET, allow_pickle=True)
    k = d["k15"].astype(np.int64)
    t = d["t15"].astype(np.int64)
    c = B["c15"]
    ok = k + 24 < len(c)
    k, t = k[ok], t[ok]
    r1 = c[k + 1] - c[k]
    r24 = c[k + 24] - c[k]
    keep = (r1 != 0) & (r24 != 0)
    k, t, r1, r24 = k[keep], t[keep], r1[keep], r24[keep]
    if quick:
        k, t, r1, r24 = k[::4], t[::4], r1[::4], r24[::4]
    side = np.ones(len(k), dtype=np.int8)
    seq = seq_windows(B, k, side)
    yr = np.array([datetime.fromtimestamp(int(x), timezone.utc).year for x in t])
    hour = B["hr15"][k]
    dow = np.array([datetime.fromtimestamp(int(x), timezone.utc).weekday() for x in t])
    dow = (dow + 1) % 7                                   # MqlDateTime: 0 Sunday
    st = time_static(hour.astype(np.float64), dow.astype(np.float64), side.astype(np.float32))
    res = {}
    for lab_name, r, horizon in (("next_bar_dir", r1, 1), ("next_24_sign", r24, 24)):
        y = (r > 0).astype(np.int8)
        P_all = np.full(len(y), np.nan)
        per_year = {}
        for year in years:
            a, b = year_bounds(year)
            held = (yr == year) if year != 2023 else (yr <= 2023)
            # purge: training bars whose label window reaches into the held-out year, plus a 2-day embargo both sides
            t_end = t + horizon * 900
            bad = held | ((t_end >= a) & (t_end < b)) | ((t >= a - EMBARGO_S) & (t < b + EMBARGO_S))
            train = np.nonzero(~bad)[0]
            train = train[np.argsort(t[train], kind="stable")]
            cut = int(len(train) * 0.85)
            itr = train[t[train] < t[train[cut]] - EMBARGO_S]
            iva = train[cut:]
            Ps = []
            for seed in seeds:
                model, _ = fit(seq, st, y, itr, iva, seed, epochs=epochs, patience=4, batch=1024, lr=3e-3)
                Ps.append(predict(model, seq, st, np.nonzero(held)[0]))
            Pm = np.mean(Ps, axis=0)
            P_all[held] = Pm
            yh = y[held]
            per_year[str(year)] = {"n": int(held.sum()), "auc": round(float(roc_auc_score(yh, Pm)), 4), "acc": round(float(((Pm > 0.5) == yh).mean() * 100), 2),
                                   "majority_acc": round(float(max(yh.mean(), 1 - yh.mean()) * 100), 2), "base_rate_up": round(float(yh.mean() * 100), 2)}
            log(f"  [candles {lab_name}] held {year}: AUC {per_year[str(year)]['auc']} acc {per_year[str(year)]['acc']} (majority {per_year[str(year)]['majority_acc']})")
        m = ~np.isnan(P_all)
        # top-decile confidence: does being sure help?
        conf = np.abs(P_all[m] - 0.5)
        q = np.quantile(conf, 0.9)
        sure = conf >= q
        res[lab_name] = {"n": int(m.sum()), "auc": round(float(roc_auc_score(y[m], P_all[m])), 4), "acc": round(float(((P_all[m] > 0.5) == y[m]).mean() * 100), 2),
                         "majority_acc": round(float(max(y[m].mean(), 1 - y[m].mean()) * 100), 2),
                         "top_decile_confidence_acc": round(float(((P_all[m][sure] > 0.5) == y[m][sure]).mean() * 100), 2), "per_year": per_year}
    return res


# ---------------------------------------------------------------- ONNX
def export_onnx(model, seq_shape, n_static, static_mean, static_scale, static_names, seq_check, st_check, tag):
    import onnx
    import onnxruntime as ort
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{tag}.onnx"
    model.eval()
    dummy = (torch.zeros(1, seq_shape[0], seq_shape[1]), torch.zeros(1, n_static))
    torch.onnx.export(model, dummy, str(path), opset_version=15, input_names=["seq", "static"], output_names=["logit"], dynamo=False)
    onnx.checker.check_model(onnx.load(str(path)))
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = model(torch.from_numpy(seq_check), torch.from_numpy(st_check)).numpy()
    got = np.concatenate([sess.run(None, {"seq": seq_check[i:i + 1], "static": st_check[i:i + 1]})[0] for i in range(len(seq_check))])
    diff = float(np.abs(ref - got).max())
    meta = {"file": path.name, "opset": 15, "inputs": {"seq": [1, int(seq_shape[0]), int(seq_shape[1])], "static": [1, int(n_static)]}, "output": "logit (P = sigmoid)",
            "channels": CHANNELS, "channel_def": "bars k-L+1..k (k = entry bar - 1), prices (x - close[k]) x side / atr[k]; range (h-l)/atr[k]; log(atr[j]/atr[k])",
            "static_names": static_names, "static_mean": [float(x) for x in static_mean], "static_scale": [float(x) for x in static_scale],
            "static_def": "(raw - mean) / scale; raw = time one-hots + side + sin/cos hour + minute-in-bar/15 + bias, then the setup-state block",
            "n_params": n_params(model), "ort_vs_torch_max_abs_diff_logit": diff, "verified_rows": int(len(seq_check))}
    (OUT_DIR / f"{tag}.json").write_text(json.dumps(meta, indent=1))
    torch.save(model.state_dict(), OUT_DIR / f"{tag}.pt")
    return meta


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-candles", action="store_true")
    ap.add_argument("--no-onnx", action="store_true")
    ap.add_argument("--no-xgb", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    seeds = list(range(a.seeds))
    years = [2023, 2024, 2025, 2026]
    M = load_meta()
    B = load_bars()
    U = np.nonzero(M["src"] == 1)[0]
    Cidx = np.nonzero(M["src"] == 0)[0]
    pnl_u = M["pnl"][U]
    y = M["y_win"][U].astype(np.int8)
    fy = M["fold_year"][U]
    side = M["side"][U].astype(np.float32)
    k_last = M["k15"][U] - 1
    log(f"universe {len(U)} trades, WR {y.mean()*100:.2f}%, C {len(Cidx)}; building {L}-candle windows")
    seq = seq_windows(B, k_last, side)
    names = [str(x) for x in M["setup_names"]]
    col = {nm: i for i, nm in enumerate(names)}
    hour = M["X_setup"][U, col["hour"]]
    minute = M["X_setup"][U, col["minute"]]
    dow = M["X_setup"][U, col["dow"]]
    st_time = time_static(hour, dow, side, minute)
    st_setup, setup_names = setup_static(M)
    st_setup = st_setup[U]
    st_full = np.concatenate([st_time, st_setup], axis=1)
    full_names = TIME_NAMES + setup_names
    rates = train_rates(M, U, years)
    MU = {k: M[k][U] for k in ("entry_t", "exit_t", "fold_year")}
    results = {"approach": "SEQUENCE (agent S): 1D-CNN on the raw last-48-M15-candle path (o/h/l/c/EMA20/EMA62 side-relative in ATR units, range, ATR ratio) + static vector; "
                           "meta-labelling on UNIVERSE-C (src 1); LOYO by calendar year with 2-day embargo + exit-in-year purge; inner 15% time split for early stopping; "
                           f"{len(seeds)} seeds ensembled",
               "built": time.strftime("%Y-%m-%d %H:%M"), "window_L": L, "channels": CHANNELS, "n_universe": int(len(U)), "universe_wr": round(float(y.mean() * 100), 2),
               "universe": summ(pnl_u), "universe_per_year": {str(yv): summ(pnl_u[fy == yv]) for yv in years}, "variants": {}, "notes": [], "problems": []}
    ep = 8 if a.quick else a.epochs

    # ---- variants
    variants = {
        "seq_time": dict(use_seq=True, use_static=True, st=st_time, names=TIME_NAMES, desc="candles + hour/dow/side (Zee's 'read the candles' model)"),
        "seq_time_setup": dict(use_seq=True, use_static=True, st=st_full, names=full_names, desc="candles + time + the 70-column setup-state block"),
        "static_setup_only": dict(use_seq=False, use_static=True, st=st_full, names=full_names, desc="ablation: NO candles, the same MLP on time + setup state"),
        "time_only": dict(use_seq=False, use_static=True, st=st_time, names=TIME_NAMES, desc="BASELINE (ii): hour/dow/side only, same learner"),
    }
    P_by = {}
    for vname, v in variants.items():
        log(f"variant {vname}: {v['desc']}")
        P, P_seeds, diag = loyo_run(vname, seq, v["st"], y, MU, years, seeds, v["use_seq"], v["use_static"], ep)
        P_by[vname] = (P, P_seeds)
        results["variants"][vname] = {"desc": v["desc"], "oos": oos_metrics(P, y, fy, years, rates), "diag": diag,
                                      "frontier": frontier(P, pnl_u, fy, years)}
        log(f"  {vname}: pooled AUC {results['variants'][vname]['oos']['auc']} logloss {results['variants'][vname]['oos']['logloss']} "
            f"(class-freq {results['variants'][vname]['oos']['logloss_class_freq']}); top-1615: {results['variants'][vname]['frontier'][11]}")

    # pick the best sequence variant by pooled OOS AUC (between the two that use candles)
    best = max(("seq_time", "seq_time_setup"), key=lambda k: results["variants"][k]["oos"]["auc"])
    P = P_by[best][0]
    results["best_variant"] = best
    results["oos"] = results["variants"][best]["oos"]
    results["frontier"] = results["variants"][best]["frontier"]
    results["seed_variance"] = {k: {"per_seed_auc": results["variants"][k]["diag"]["per_seed_auc"], "spread": results["variants"][k]["diag"]["seed_spread_auc"],
                                    "pairwise_corr_P": results["variants"][k]["diag"]["seed_pairwise_corr_P"],
                                    "top1615_per_seed": [summ(pnl_u[np.argsort(-P_by[k][1][si], kind="stable")[:1615]]) for si in range(len(seeds))]}
                                for k in variants}

    # ---- baselines
    bl = {"random_same_size": random_baseline(pnl_u, fy, years, TOPS, draws=500 if a.quick else 2000),
          "time_only_model": {"oos": results["variants"]["time_only"]["oos"], "frontier": results["variants"]["time_only"]["frontier"]},
          "setting_C_hand_filters_IN_SAMPLE": {**C_STD, "note": "Zee's standard; hand-optimised on these same 4 years, so IN-SAMPLE - not comparable 1:1 with an OOS row"},
          "ml_top1615_oos_per_year_vs_C": {}}
    top1615 = results["frontier"][11]
    for yv in years:
        bl["ml_top1615_oos_per_year_vs_C"][str(yv)] = {"ml_top1615_pooled_pick": top1615["per_year"][str(yv)], "C_in_sample": C_STD["per_year"][str(yv)]}
    # per-year matched-N: top n_C(year) by P inside each year (OOS)
    matched = {}
    for yv in years:
        m = np.nonzero(fy == yv)[0]
        nC = C_STD["per_year"][str(yv)]["n"]
        pick = m[np.argsort(-P[m], kind="stable")[:nC]]
        matched[str(yv)] = summ(pnl_u[pick])
    bl["ml_top_nC_within_year"] = {**matched, "pooled": summ(pnl_u[np.concatenate([np.nonzero(fy == yv)[0][np.argsort(-P[fy == yv], kind="stable")[:C_STD['per_year'][str(yv)]['n']]] for yv in years])])}
    # XGBoost reference on the 85 bar features + side (the scout, re-run on UNIVERSE-C) and on setup+bar
    if not a.no_xgb:
        try:
            import xgboost as xgb
            Xb = np.concatenate([M["X_bar"][U], side[:, None]], axis=1)
            Xsb = np.concatenate([M["X_bar"][U], st_setup, st_time[:, 31:35]], axis=1)
            for tag, X in (("xgb_bar85_side", Xb), ("xgb_bar85_setup", Xsb)):
                Px = np.full(len(y), np.nan)
                for yv in years:
                    held, itr, iva, train = loyo_split(MU["entry_t"], MU["exit_t"], MU["fold_year"], yv)
                    clf = xgb.XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.6, min_child_weight=20,
                                            reg_lambda=5.0, n_jobs=8, random_state=0, eval_metric="logloss", early_stopping_rounds=40)
                    clf.fit(X[itr], y[itr], eval_set=[(X[iva], y[iva])], verbose=False)
                    Px[held] = clf.predict_proba(X[held])[:, 1]
                bl[tag] = {"oos": oos_metrics(Px, y, fy, years, rates), "top1615": summ(pnl_u[np.argsort(-Px, kind="stable")[:1615]]),
                           "top1000": summ(pnl_u[np.argsort(-Px, kind="stable")[:1000]])}
                P_by[tag] = (Px, None)
                log(f"  {tag}: AUC {bl[tag]['oos']['auc']} top-1615 {bl[tag]['top1615']}")
        except Exception as e:                            # noqa: BLE001
            results["problems"].append(f"xgboost reference failed: {e!r}")
    # blend: best CNN + xgb (rank average) - does the sequence add to the tabular model?
    if "xgb_bar85_setup" in P_by:
        from scipy.stats import rankdata
        Pbl = (rankdata(P) + rankdata(P_by["xgb_bar85_setup"][0])) / (2 * len(P))
        bl["blend_cnn_xgb_rankavg"] = {"auc": round(float(roc_auc_score(y, Pbl)), 4), "top1615": summ(pnl_u[np.argsort(-Pbl, kind="stable")[:1615]]),
                                       "corr_P_cnn_xgb": round(float(np.corrcoef(P, P_by["xgb_bar85_setup"][0])[0, 1]), 4)}
    results["baselines"] = bl

    # ---- label diagnostics
    try:
        results["label_diagnostics"] = label_diagnostics(M, U, y, pnl_u, fy, MU, st_setup, st_time, years)
        log(f"  label diagnostics: {results['label_diagnostics']}")
    except Exception as e:                                # noqa: BLE001
        results["problems"].append(f"label diagnostics failed: {e!r}")

    # ---- b_scores
    results["b_scores"], inC = b_scores(P, M, U, Cidx, pnl_u, fy, years)
    results["b_scores"]["C_mean_P_by_variant"] = {k: {"C": round(float(P_by[k][0][inC].mean()), 4), "rest": round(float(P_by[k][0][~inC].mean()), 4)} for k in P_by}

    # ---- same-tick artefacts: the frontier with them removed
    ste = M["same_tick_exit"][U] == 1
    P_nost = P.copy()
    P_nost[ste] = -1
    results["frontier_excl_same_tick_exits"] = {"n_removed": int(ste.sum()), "removed_pnl": summ(pnl_u[ste]),
                                                "top1615": summ(pnl_u[np.argsort(-P_nost, kind="stable")[:1615]]),
                                                "top1000": summ(pnl_u[np.argsort(-P_nost, kind="stable")[:1000]])}

    # ---- feature signal: refit the best variant (seed 0) per year and permute groups OOS
    log("feature signal: grouped permutation importance (best variant, seed 0)")
    v = variants[best]
    models_by_year, st_by_year = {}, {}
    for yv in years:
        held, itr, iva, train = loyo_split(MU["entry_t"], MU["exit_t"], MU["fold_year"], yv)
        sc = Scaler(v["st"][train])
        st_by_year[yv] = sc(v["st"])
        models_by_year[yv], _ = fit(seq, st_by_year[yv], y, itr, iva, 0, use_seq=True, use_static=True, epochs=ep)
    vn = v["names"]
    groups = {"time_hour": [i for i, n_ in enumerate(vn) if n_.startswith("hour")], "time_dow": [i for i, n_ in enumerate(vn) if n_.startswith("dow")],
              "side": [vn.index("side")], "min_in_bar": [vn.index("min_in_bar")]}
    if best == "seq_time_setup":
        gdef = {"setup_candle_shape": ["kind", "kind_pin", "kind_ham", "kind_maru", "s_range_atr", "s_body", "s_uwick", "s_lwick", "s_clpos", "s_dir_rel"],
                "setup_vs_emas": ["on_slow", "ema_which", "s_c_ef_rel", "s_h_ef_rel", "s_l_ef_rel", "s_c_es_rel", "s_h_es_rel", "s_l_es_rel", "s_gap_atr", "s_gap_pips", "s_align_rel"],
                "entry_emas": ["e_gap_atr", "e_gap_pips", "e_align_rel", "e_ef_slope4_rel", "e_ef_slope16_rel", "e_es_slope4_rel", "e_es_slope16_rel"],
                "setup_slopes": ["s_ef_slope4_rel", "s_ef_slope16_rel", "s_es_slope4_rel", "s_es_slope16_rel"],
                "chop_htf": ["s_chop_er10", "s_chop_er16", "s_chop_er20", "s_ema64_rel", "s_ema256_rel", "s_disp_64_256_rel", "s_adx", "s_atr_r_e"],
                "breakout": ["bars_to_entry", "entry_min_in_bar", "level_rel", "brk_dist_atr", "brk_dist_pips", "open_vs_level_rel", "entry_vs_sclose_rel"],
                "risk_geometry": ["s_risk_atr", "s_risk_pips", "stop_atr"],
                "open_positions": ["n_open", "n_open_same", "n_open_opp"],
                "recent_results": ["prev1_pnl", "prev1_win", "prev3_pnl", "prev3_wr", "prev10_pnl", "prev10_wr", "prev_n10", "since_close_min"],
                "day_state": ["day_pnl", "day_closed_n", "day_opened_n"], "setup_density": ["setups_20", "setups_opp_20"]}
        for g, cols in gdef.items():
            groups[g] = [vn.index(c) for c in cols if c in vn]
    seq_groups = {f"seq_chan_{c}": ("chan", i) for i, c in enumerate(CHANNELS)}
    seq_groups["seq_oldest_half_bars"] = ("time", (0, L // 2))
    seq_groups["seq_last_8_bars"] = ("time", (L - 8, L))
    seq_groups["seq_last_2_bars"] = ("time", (L - 2, L))
    results["features"] = {"method": "grouped permutation importance: mean over held-out years of AUC drop when the group is shuffled across the held-out rows (seed-0 models of the best variant)",
                           "importance_auc_drop": perm_importance(models_by_year, seq, st_by_year, y, MU, U, years, groups, seq_groups)}
    log(f"  importance: {results['features']['importance_auc_drop']}")

    # ---- the candle claim
    if not a.no_candles:
        log("candle claim: next-bar direction / next-24 sign on all dataset bars (LOYO)")
        results["candle_prediction"] = candle_test(B, years, seeds[:1], 15 if not a.quick else 4, quick=a.quick)
        results["candle_prediction"]["note"] = "the same CNN on the same 48-candle windows, every bar of mlx_dataset.npz (bars with a zero move dropped), LOYO with 2-day embargo + label-window purge; AUC 0.50 = no skill"

    # ---- ONNX: the best variant trained on all four years (deployment model; in-sample by construction)
    if not a.no_onnx:
        log("ONNX export: best variant refit on all years (inner 15% time split for early stopping)")
        order = np.argsort(MU["entry_t"], kind="stable")
        cut = int(len(order) * 0.85)
        itr = order[MU["entry_t"][order] < MU["entry_t"][order[cut]] - EMBARGO_S]
        iva = order[cut:]
        sc = Scaler(v["st"])
        st_all = sc(v["st"])
        model, info = fit(seq, st_all, y, itr, iva, 0, use_seq=True, use_static=True, epochs=ep)
        chk = np.random.default_rng(0).choice(len(y), 300, replace=False)
        meta = export_onnx(model, (L, len(CHANNELS)), st_all.shape[1], sc.mean, sc.scale, vn, seq[chk], st_all[chk], f"meta_seq_{best}_all_years")
        meta["fit"] = info
        meta["in_sample_auc_all_years"] = round(float(roc_auc_score(y, predict(model, seq, st_all, np.arange(len(y))))), 4)
        results["onnx"] = meta
        log(f"  onnx ok: {meta['file']} params {meta['n_params']} ort-vs-torch max |dlogit| {meta['ort_vs_torch_max_abs_diff_logit']:.2e}")

    # ---- predictions file
    np.savez_compressed(OUT_NPZ, P=P, entry_t=MU["entry_t"], side=M["side"][U], src=M["src"][U], y_win=y, pnl=pnl_u, fold_year=fy, variant=best,
                        **{f"P_{k}": P_by[k][0] for k in P_by})

    # ---- notes
    tv = results["variants"]
    results["notes"] += [
        "Every WR / P&L is a Turtle TV Tester hypothesis (the universe's pnl is the tester's real-tick fill P&L); setting C's figures are IN-SAMPLE (hand-optimised on these 4 years); the ML rows are LOYO out-of-sample.",
        f"Pooled OOS AUC(win): seq+time {tv['seq_time']['oos']['auc']}, seq+time+setup {tv['seq_time_setup']['oos']['auc']}, setup-only (no candles) {tv['static_setup_only']['oos']['auc']}, "
        f"time-only {tv['time_only']['oos']['auc']}; class-frequency log-loss {tv[best]['oos']['logloss_class_freq']} vs model {tv[best]['oos']['logloss']}.",
        f"Top-1615 OOS by P ({best}): {top1615['n']} / {top1615['wr']}% / ${top1615['net']:,.0f} / worst ${top1615['worst']:,.0f} / {top1615['full_stops']} full stops "
        f"vs C in-sample 1,615 / 97.15% / $402,831 / -$5,574 / 43; random 1615 expected WR {bl['random_same_size']['1615']['wr']}% (p99 {bl['random_same_size']['1615']['wr_p99']}%).",
        "Stop / TP untouched (InpSlMode 2 / InpSlUsd 26 = 260 pips, TP 20 pips): the model only chooses which universe trades to take.",
        "Seeds: " + json.dumps(results["seed_variance"][best]["per_seed_auc"]) + f" (spread {results['seed_variance'][best]['spread']}); ensemble = mean P over seeds.",
    ]
    results["problems"] += [
        "2022's 27 universe rows (Dec 29-30) are folded into the 2023 fold; 48-candle windows for k15 < 49 are clamped at bar 0 (warm-up rows only).",
        "The ONNX model is trained on all four years (in-sample by construction) - it is the deployment candidate, not an evidence row; its P threshold must come from the LOYO frontier.",
        "The time-only baseline shares the learner's static branch; the hour/dow block is also present in every CNN variant, so a CNN that only matches time-only has learned nothing from the candles.",
        f"Same-tick exits (opened and closed in one tick): {int(ste.sum())} universe trades; the frontier excluding them is in frontier_excl_same_tick_exits.",
    ]
    results["runtime_s"] = round(time.time() - t0, 1)
    OUT_JSON.write_text(json.dumps(results, indent=1, default=float))
    log(f"wrote {OUT_JSON} and {OUT_NPZ} in {results['runtime_s']} s")


if __name__ == "__main__":
    main()
