"""mlx/data.py - builds the Machine Learning tab's data files from the tester's M15 candles (sim.data("m15"), Blueberry 2023 -> now):
  simdata/mlx_dataset.npz   X float32 (rows x features), names, t15, k15, label (1 / -1 / 0), touch_k, atr, close (+ ret_fwd_24)
  simdata/mlx_features.json {"all": names, "kept": names, "scaler": null}  (the model side fills kept / scaler after SHAP)
  simdata/mlx_entries.npz   the EA's trades for setting B and for the setup UNIVERSE (B with its entry filters off): k15, side, entry_t, pnl,
                            reason, src (0 = B, 1 = universe) + exit_t, exit_k15, entry, exit, sl, lots, swap
plus the checks the data must pass before anyone trains on it: the ADX parity with the tester's column, the lookahead test (features
recomputed on a truncated history are bit-identical), label counts per year.
CLI: py -m mlx.data  (from monitor/saad_view)  or  py mlx/data.py   [--no-entries | --only-entries] [--no-checks] [--picks 5] [--seed 1]
CLAUDE.md: everything here is a hypothesis-generator; MT5's Strategy Tester promotes."""
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
from mlx import features, labels                       # noqa: E402

SIMDATA = VIEW / "simdata"
DATASET = SIMDATA / "mlx_dataset.npz"
ENTRIES = SIMDATA / "mlx_entries.npz"
FEATURES = SIMDATA / "mlx_features.json"
B_FILE = VIEW / "settings" / "saved" / "2026-10-30 23-08-23.json"       # setting B (the 99.7% save)
BARRIERS = {"up": 1.5, "dn": 1.5, "bars": 24}
# the UNIVERSE = B with every entry filter off (the model, not the filters, decides); every TvBox_* mask becomes all-'1'
UNIVERSE = {"InpEmaGapPips": "0", "InpChopEr": "0", "InpSessFrom": "0", "InpSessTo": "24", "InpSkipDow": "-1", "InpAtrMinUsd": "0",
            "InpAtrMaxUsd": "0", "InpMinRangeAtr": "0", "InpMaxSpreadPts": "0", "InpAdxMin": "0", "InpBandsB": "1" * 21, "InpBandsS": "1" * 21,
            "InpBandOff": "0", "InpHours": "1" * 24, "InpDayTargetUsd": "0", "InpDayLossPct": "0", "InpMaxPos": "8"}
_LAST = {}                                             # the last full feature matrix (build_dataset) for the checks


def _iso(t):
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%d %H:%M")


def years_of(t15):
    """server-time year of each bar open (t15 is the server clock as if UTC)"""
    return np.array([datetime.fromtimestamp(int(t), timezone.utc).year for t in t15], dtype=np.int64)


def label_by_year(t15, label):
    out, yrs = {}, years_of(t15)
    for y in np.unique(yrs):
        m = yrs == y
        out[str(int(y))] = {"n": int(m.sum()), "up": int((label[m] == 1).sum()), "down": int((label[m] == -1).sum()), "none": int((label[m] == 0).sum())}
    return out


# ---------------------------------------------------------------- the dataset
def build_dataset(ds="m15", warmup=features.WARMUP, out=DATASET, **barriers):
    D = sim.data(ds)
    n = len(D["t15"])
    t0 = time.time()
    X, names = features.build(D)
    t_feat = time.time() - t0
    t0 = time.time()
    st = {}
    label, touch, ret = labels.triple_barrier(D, stats=st, **{**BARRIERS, **barriers})
    t_lab = time.time() - t0
    keep = (np.arange(n) >= warmup) & (touch >= 0)
    Xk, nbad = features.clean(X[keep])
    k15 = np.nonzero(keep)[0].astype(np.int64)
    np.savez_compressed(out, X=Xk, names=np.array(names), t15=D["t15"][keep].astype(np.int64), k15=k15, label=label[keep].astype(np.int8),
                        touch_k=touch[keep].astype(np.int64), atr=D["atr"][keep].astype(np.float32), close=D["c15"][keep].astype(np.float32),
                        ret_fwd_24=ret[keep].astype(np.float32))
    FEATURES.write_text(json.dumps({"all": names, "kept": names, "scaler": None}, indent=1), encoding="utf-8")
    _LAST.update({"X": X, "names": names, "ds": ds})
    yrs = years_of(D["t15"][keep])
    return {"bars": int(n), "rows": int(keep.sum()), "features": len(names), "dropped_warmup": int(warmup), "dropped_no_forward": int((touch < 0).sum()),
            "nan_inf_fixed": nbad, "from": _iso(D["t15"][keep][0]), "to": _iso(D["t15"][keep][-1]),
            "label_by_year": label_by_year(D["t15"][keep], label[keep]), "ties": st,
            "label_total": {"up": int((label[keep] == 1).sum()), "down": int((label[keep] == -1).sum()), "none": int((label[keep] == 0).sum())},
            "train_years": sorted(set(int(y) for y in yrs)), "timings": {"features_s": round(t_feat, 1), "labels_s": round(t_lab, 1)},
            "files": [str(out), str(FEATURES)]}


# ---------------------------------------------------------------- the checks
def check_adx(D, warmup=features.WARMUP):
    """our ADX (MT5's iADX algorithm) against the tester's D["adx"] after the warm-up; the textbook Wilder variant beside it"""
    h, l, c = (np.ascontiguousarray(D[k], dtype=np.float64) for k in ("h15", "l15", "c15"))
    adx, _, _ = features.adx_mt5(h, l, c, 14)
    wil = features.adx_wilder(h, l, c, 14)
    ref = np.asarray(D["adx"], dtype=np.float64)
    s = slice(warmup, None)
    return {"corr": float(np.corrcoef(adx[s], ref[s])[0, 1]), "max_abs_diff": float(np.abs(adx[s] - ref[s]).max()),
            "wilder_corr": float(np.corrcoef(wil[s], ref[s])[0, 1]), "wilder_max_abs_diff": float(np.abs(wil[s] - ref[s]).max()),
            "note": "D['adx'] (= iADX) is MT5's ADX.mq5: EMA(alpha 2/15) of the per-bar DI and DX - textbook Wilder (1/14 running sums) differs"}


def truncate(D, i):
    """the data as it stood at the close of bar i: bars <= i and their minutes"""
    m = np.asarray(D["k1"]) <= i
    T = {k: np.asarray(D[k])[:i + 1] for k in ("t15", "hr15", "o15", "h15", "l15", "c15", "atr", "adx")}
    T.update({k: np.asarray(D[k])[m] for k in ("t1", "o1", "h1", "l1", "c1", "sp1", "k1")})
    return T


def check_lookahead(D, X=None, picks=5, seed=1, warmup=features.WARMUP):
    """features recomputed on the history truncated at bar i must equal row i of the full build, bit for bit"""
    if X is None:
        X = _LAST["X"] if _LAST.get("X") is not None else features.build(D)[0]
    n = len(D["t15"])
    rng = np.random.default_rng(seed)
    out = []
    for i in sorted(int(v) for v in rng.integers(warmup, n, size=picks)):
        Xt, _ = features.build(truncate(D, i))
        a, b = Xt[i], X[i]
        fin = np.isfinite(a) & np.isfinite(b)
        diff = float(np.abs(a[fin] - b[fin]).max()) if fin.any() else 0.0
        out.append({"i": i, "t": _iso(D["t15"][i]), "identical": bool(np.array_equal(a, b, equal_nan=True)), "max_abs_diff": diff,
                    "nan_cells": int((~np.isfinite(b)).sum())})
    return out


# ---------------------------------------------------------------- the EA's trades
def universe_inputs(b):
    u = dict(b)
    u.update(UNIVERSE)
    for k, v in b.items():
        if str(k).startswith("TvBox_"):
            u[k] = "1" * len(str(v))
    return u


def _full_inputs(sets):
    """server.full_inputs (every EA input, defaults from the view EA's source) - a local copy when the server module cannot load"""
    try:
        import server
        return server.full_inputs(sets)
    except Exception:                                            # noqa: BLE001
        lab = VIEW.parent / "strategy_lab"
        if str(lab) not in sys.path:
            sys.path.insert(0, str(lab))
        import axi_rig
        dfl = axi_rig.ea_defaults("Saad_strategy_15min_view")
        out = {k: str(sets.get(k, v)) for k, v in dfl.items()}
        out.update({k: str(v) for k, v in sets.items() if str(k).startswith("TvBox_")})
        return out


def build_entries(ds="m15", out=ENTRIES, b_file=B_FILE):
    """the tester's trades (ghost probes dropped) for setting B (src 0) and the UNIVERSE (src 1), sorted by entry time"""
    b = json.loads(Path(b_file).read_text(encoding="utf-8"))["inputs"]
    info, parts = {}, []
    for src, (name, inputs) in enumerate((("B", b), ("universe", universe_inputs(b)))):
        t0 = time.time()
        tr, setups, stats = sim.simulate(_full_inputs(inputs), ds=ds)
        tr = tr[tr[:, 10] == 0]
        tr = tr[np.argsort(tr[:, 1], kind="stable")]
        info[name] = {"trades": int(len(tr)), "buys": int((tr[:, 0] > 0).sum()), "sells": int((tr[:, 0] < 0).sum()),
                      "wr": round(100.0 * float((tr[:, 6] > 0).mean()), 1) if len(tr) else 0.0, "net": round(float(tr[:, 6].sum()), 2),
                      "setups": int(len(setups)), "stats": stats, "secs": round(time.time() - t0, 1)}
        parts.append((src, tr))
    cat = lambda col, dt: np.concatenate([tr[:, col].astype(dt) for _, tr in parts])            # noqa: E731
    np.savez(out, k15=cat(11, np.int64), side=cat(0, np.int8), entry_t=cat(1, np.int64), pnl=cat(6, np.float64), reason=cat(13, np.int8),
             src=np.concatenate([np.full(len(tr), src, np.int8) for src, tr in parts]), exit_t=cat(4, np.int64), exit_k15=cat(12, np.int64),
             entry=cat(2, np.float64), exit=cat(5, np.float64), sl=cat(3, np.float64), lots=cat(14, np.float64), swap=cat(7, np.float64))
    info["files"] = [str(out)]
    return info


# ---------------------------------------------------------------- CLI
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-entries", action="store_true")
    ap.add_argument("--only-entries", action="store_true")
    ap.add_argument("--no-checks", action="store_true")
    ap.add_argument("--picks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    rep, T = {}, time.time()
    if not a.only_entries:
        rep["dataset"] = build_dataset()
        print(json.dumps({"dataset": rep["dataset"]}, indent=1), flush=True)
        if not a.no_checks:
            D = sim.data("m15")
            t0 = time.time()
            rep["adx_parity"] = check_adx(D)
            rep["lookahead"] = check_lookahead(D, picks=a.picks, seed=a.seed)
            rep["checks_s"] = round(time.time() - t0, 1)
            print(json.dumps({"adx_parity": rep["adx_parity"], "lookahead": rep["lookahead"], "checks_s": rep["checks_s"]}, indent=1), flush=True)
    if not a.no_entries:
        t0 = time.time()
        rep["entries"] = build_entries()
        rep["entries"]["secs_total"] = round(time.time() - t0, 1)
        print(json.dumps({"entries": rep["entries"]}, indent=1), flush=True)
    rep["total_s"] = round(time.time() - T, 1)
    print("total %.1fs" % rep["total_s"])
    return rep


if __name__ == "__main__":
    main()
