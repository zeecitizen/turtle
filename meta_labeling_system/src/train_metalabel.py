"""Meta-labeling trainer for Saad_strategy_15min (Zee 2026-10-13, from the "Meta-Labeling" PDFs).

Reads ONLY what the EA itself logged in the MT5 Strategy Tester (Saad_meta.mq5, InpMetaLog=true):
    Common\\Files\\saad_meta_<tag>_feat.csv   features at the moment of entry (+ position id)
    Common\\Files\\saad_meta_<tag>_out.csv    the position's final net $ (partials, swap, $4/lot)
There is NO synthetic-data fallback: no real log -> no model.

Label = 1 if the trade's net > 0. Train on trades entered before --cutoff only (walk-forward);
the threshold is picked inside that window with a time-series split, by the summed net of the
trades the model would have approved (not by precision).

Writes:
    models/meta_model_xauusd.pkl       XGBoost model + feature names + threshold (for api_server.py)
    mt5/SaadMetaModel.mqh              the same trees as MQL5 code, so the Strategy Tester can judge it
    data/python_probs.csv              Python's probability per logged row (parity check vs the EA)

Python here only GENERATES a hypothesis. Only the MT5 Strategy Tester run of the gated EA on
the unseen period may promote it (CLAUDE.md).
    py train_metalabel.py [--tag 1] [--cutoff 2026-07-01] [--depth 2] [--trees 100]"""
import argparse, json, re, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
import joblib
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
sys.path.insert(0, str(REPO / "monitor"))
import doctrine  # the only sanctioned way to print a Python win rate

META_NAMES = ["f_side", "f_shape", "f_line", "f_risk_atr", "f_tp_r", "f_er", "f_atr_ratio", "f_ema50_dist",
              "f_ema9_dist", "f_ema_gap", "f_range_atr", "f_hour", "f_dow", "f_spread", "f_slope50"]


def load(tag):
    feat, out = COMMON / f"saad_meta_{tag}_feat.csv", COMMON / f"saad_meta_{tag}_out.csv"
    for f in (feat, out):
        if not f.exists():
            sys.exit(f"missing {f}\nRun Saad_meta in the Strategy Tester with InpMetaLog=true, InpMetaTag={tag}, InpMetaMode=0 first.")
    (ROOT / "data").mkdir(exist_ok=True)
    shutil.copy(feat, ROOT / "data" / "xauusd_signals_log.csv")
    shutil.copy(out, ROOT / "data" / "xauusd_outcomes_log.csv")
    F, O = pd.read_csv(feat), pd.read_csv(out)
    F = F[F.veto == 0]
    if (F.prob >= 0).any():
        sys.exit("this log came from a GATED run (InpMetaMode>0): train only on an ungated run, or the model learns its own filter")
    df = F.merge(O, on="pos_id", how="inner")
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df["y"] = (df["net"] > 0).astype(int)
    print(f"[+] {len(F)} entries logged, {len(O)} outcomes, {len(df)} joined  ({df.time.min():%Y-%m-%d} .. {df.time.max():%Y-%m-%d})")
    return df


def make_model(depth, trees):
    return xgb.XGBClassifier(n_estimators=trees, learning_rate=0.05, max_depth=depth, subsample=0.8,
                             colsample_bytree=0.8, min_child_weight=10, objective="binary:logistic",
                             eval_metric="auc", random_state=42, n_jobs=1)


def pick_threshold(df, depth, trees):
    """Time-series CV inside the training window: for each threshold, the summed net of approved trades."""
    grid = np.round(np.arange(0.40, 0.76, 0.05), 2)
    tot = {t: 0.0 for t in grid}; base = 0.0; kept = {t: 0 for t in grid}; n = 0
    for tr, va in TimeSeriesSplit(n_splits=4).split(df):
        m = make_model(depth, trees).fit(df.loc[tr, META_NAMES], df.loc[tr, "y"])
        p = m.predict_proba(df.loc[va, META_NAMES])[:, 1]
        net = df.loc[va, "net"].to_numpy(); base += net.sum(); n += len(va)
        for t in grid: tot[t] += net[p >= t].sum(); kept[t] += int((p >= t).sum())
    print(f"\n[+] Threshold choice inside the training window (4-fold time-series CV, {n} validation trades)")
    print(f"    take everything : net {base:>10,.0f}  ({n} trades)")
    for t in grid: print(f"    p >= {t:.2f}      : net {tot[t]:>10,.0f}  ({kept[t]} trades)")
    best = max(grid, key=lambda t: tot[t])
    print(f"    -> {best:.2f}  (Python replay of fixed trades: a HYPOTHESIS only)")
    return float(best)


# ---- trees -> MQL5 ---------------------------------------------------------------------------
def base_margin(booster):
    cfg = json.loads(booster.save_config())
    bs = cfg["learner"]["learner_model_param"]["base_score"]
    p = float(re.findall(r"[-+0-9.eE]+", str(bs))[0])
    return float(np.log(p / (1 - p)))


def tree_eval(node, x):
    while "leaf" not in node:
        v = np.float32(x[META_NAMES.index(node["split"])])
        go = node["yes"] if v < np.float32(node["split_condition"]) else node["no"]
        node = next(c for c in node["children"] if c["nodeid"] == go)
    return np.float32(node["leaf"])


def tree_mql(node, ind="   "):
    if "leaf" in node:
        return f"{ind}return {float(np.float32(node['leaf'])):.9g};\n"
    i = META_NAMES.index(node["split"])
    yes = next(c for c in node["children"] if c["nodeid"] == node["yes"])
    no = next(c for c in node["children"] if c["nodeid"] == node["no"])
    thr = float(np.float32(node["split_condition"]))
    return (f"{ind}if ((float)f[{i}] < (float){thr:.9g}) {{  // {node['split']}\n" + tree_mql(yes, ind + "   ")
            + f"{ind}}} else {{\n" + tree_mql(no, ind + "   ") + f"{ind}}}\n")


def export_mqh(model, threshold, trained_txt, path):
    b = model.get_booster(); b.feature_names = META_NAMES
    trees = [json.loads(t) for t in b.get_dump(dump_format="json")]
    bm = base_margin(b)
    names = ",".join(f'"{n}"' for n in META_NAMES)
    out = [f"// SaadMetaModel.mqh - GENERATED by meta_labeling_system/src/train_metalabel.py — do not edit.",
           f"// XGBoost {xgb.__version__}: {len(trees)} trees, trained on {trained_txt}; suggested threshold {threshold:.2f}",
           f"#define META_NF {len(META_NAMES)}", f'#define META_TRAINED "{trained_txt}"',
           f"string META_NAMES[META_NF] = {{{names}}};"]
    for k, t in enumerate(trees):
        out.append(f"double MetaTree{k}(const double &f[])\n{{\n{tree_mql(t)}}}")
    body = "\n".join(f"   m += MetaTree{k}(f);" for k in range(len(trees)))
    out.append(f"double MetaModelProb(const double &f[])\n{{\n   double m = {bm:.12g};\n{body}\n   return 1.0 / (1.0 + MathExp(-m));\n}}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    # parity: our own evaluator of the dump must equal xgboost
    return trees, bm


def dump_prob(trees, bm, X):
    return np.array([1 / (1 + np.exp(-(bm + sum(float(tree_eval(t, x)) for t in trees)))) for x in X])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="1"); ap.add_argument("--cutoff", default="2026-07-01")
    ap.add_argument("--depth", type=int, default=2); ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--threshold", type=float, default=None)
    a = ap.parse_args()
    df = load(a.tag)
    tr = df[df.time < a.cutoff].reset_index(drop=True); te = df[df.time >= a.cutoff].reset_index(drop=True)
    print(f"[+] train {len(tr)} trades (< {a.cutoff}), unseen {len(te)} trades (kept for the MT5 check)")
    thr = a.threshold if a.threshold is not None else pick_threshold(tr, a.depth, a.trees)
    model = make_model(a.depth, a.trees).fit(tr[META_NAMES], tr["y"])
    trained_txt = f"{tr.time.min():%Y-%m-%d}..{tr.time.max():%Y-%m-%d} ({len(tr)} trades)"

    (ROOT / "models").mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": META_NAMES, "threshold": thr, "trained": trained_txt}, ROOT / "models" / "meta_model_xauusd.pkl")
    mqh = REPO / "mt5" / "SaadMetaModel.mqh"
    trees, bm = export_mqh(model, thr, trained_txt, mqh)
    shutil.copy(mqh, ROOT / "mql5" / "SaadMetaModel.mqh")

    X = df[META_NAMES].to_numpy()
    px = model.predict_proba(df[META_NAMES])[:, 1]; pd_ = dump_prob(trees, bm, X)
    gap = float(np.abs(px - pd_).max())
    print(f"\n[+] parity xgboost vs exported trees: max |diff| = {gap:.2e}  {'OK' if gap < 1e-5 else 'MISMATCH - do not use the .mqh'}")
    pd.DataFrame({"pos_id": df.pos_id, "time": df.time, "prob": px}).to_csv(ROOT / "data" / "python_probs.csv", index=False)

    imp = sorted(zip(META_NAMES, model.feature_importances_), key=lambda z: -z[1])
    print("[+] feature importance:", ", ".join(f"{n[2:]} {v:.2f}" for n, v in imp[:8]))
    if len(te):
        p = model.predict_proba(te[META_NAMES])[:, 1]; k = p >= thr
        print(f"\n[+] Python replay on the unseen period at p >= {thr:.2f} (fixed trades - NOT what MT5 will do):")
        print(f"    all {len(te)} trades net {te.net.sum():,.0f} | approved {k.sum()} net {te.net[k].sum():,.0f} | vetoed {(~k).sum()} net {te.net[~k].sum():,.0f}")
        doctrine.python_says("win rate of approved trades (unseen period)", 100 * te.y[k].mean() if k.any() else 0)
        doctrine.python_says("win rate of all trades (unseen period)", 100 * te.y.mean())
    print(f"\n[+] saved models/meta_model_xauusd.pkl and {mqh}")
    print("    NEXT: compile Saad_meta, run it in the Strategy Tester on the unseen period with InpMetaMode=1.")
