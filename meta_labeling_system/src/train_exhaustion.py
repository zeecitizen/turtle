"""In-trade exhaustion classifier for Saad_strategy_15min (Zee 2026-10-13).

Data = ONLY what Saad_exhaust.mq5 logged in the MT5 Strategy Tester (InpExhLog + InpMetaLog), no mock data:
    Common\\Files\\saad_exh_<tag>.csv         every open position's state at each M15 candle close
    Common\\Files\\saad_meta_<tag>_out.csv    each position's final result
Label (per row): 1 if closing the position AT THAT CANDLE would have made more than the way the trade
really ended:  realized_so_far + open_profit_now  >  final profit   (commission cancels out).
Like the pasted spec only rows with open profit > 0 are used (the EA only judges those).
Walk-forward: train on rows before --cutoff; threshold picked inside the training window by replaying
"close at the first candle where P >= t" on the LOGGED values (a hypothesis; MT5 decides).
Writes models/exhaustion_model.pkl and mt5/SaadExhaustModel.mqh (trees compiled for the Strategy Tester).
    py train_exhaustion.py [--tag 5] [--cutoff 2026-07-01] [--depth 3] [--trees 150]"""
import argparse, json, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
import joblib
from sklearn.model_selection import TimeSeriesSplit
from train_metalabel import base_margin, ROOT, REPO

COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
EXH_NAMES = ["x_side", "x_bars", "x_float_r", "x_mfe_r", "x_giveback_r", "x_er", "x_ema50_dist", "x_ema9_dist",
             "x_atr_ratio", "x_stage", "x_room_r", "x_body", "x_hour", "x_vol_left"]


def load(tag):
    fe, fo = COMMON / f"saad_exh_{tag}.csv", COMMON / f"saad_meta_{tag}_out.csv"
    for f in (fe, fo):
        if not f.exists(): sys.exit(f"missing {f}: run Saad_exhaust with InpExhLog=true, InpMetaLog=true, InpMetaTag={tag}, InpExhMode=0")
    shutil.copy(fe, ROOT / "data" / "open_trades_tracking.csv")
    E, O = pd.read_csv(fe), pd.read_csv(fo)
    if (E.prob >= 0).any(): sys.exit("this log came from a run WITH the exhaustion exit on: train only on an InpExhMode=0 run")
    df = E.merge(O[["pos_id", "profit"]], on="pos_id", how="inner")
    df["time"] = pd.to_datetime(df.time, format="%Y.%m.%d %H:%M:%S")
    df["now"] = df.realized_usd + df.float_usd                # what closing now would have booked
    df["gain"] = df.now - df.profit                           # + = closing now beats holding
    df["y"] = (df.gain > 0).astype(int)
    df = df[df.float_usd > 0].sort_values("time").reset_index(drop=True)
    print(f"[+] {len(E)} position-candles logged, {len(df)} in profit (used), {df.pos_id.nunique()} positions")
    return df


def model(depth, trees):
    return xgb.XGBClassifier(n_estimators=trees, learning_rate=0.05, max_depth=depth, subsample=0.8, colsample_bytree=0.8,
                             min_child_weight=10, objective="binary:logistic", eval_metric="auc", random_state=42, n_jobs=2)


def replay(d, p, t):
    """$ change if each position were closed at its FIRST candle with P >= t (logged values only)."""
    hit = d.assign(p=p)[p >= t].groupby("pos_id").head(1)
    return float(hit.gain.sum()), len(hit)


def pick(df, a):
    grid = [0.55, 0.65, 0.75, 0.85, 0.90, 0.95]
    tot = {t: [0.0, 0] for t in grid}
    pos = df.pos_id.unique()
    for tr, va in TimeSeriesSplit(n_splits=4).split(pos):     # split by POSITION (rows of one trade stay together)
        dtr, dva = df[df.pos_id.isin(pos[tr])], df[df.pos_id.isin(pos[va])]
        m = model(a.depth, a.trees).fit(dtr[EXH_NAMES], dtr.y)
        p = m.predict_proba(dva[EXH_NAMES])[:, 1]
        for t in grid:
            g, n = replay(dva, p, t); tot[t][0] += g; tot[t][1] += n
    print("\n[+] Threshold inside the training window (4-fold time-series CV by position; replay of logged values)")
    for t in grid: print(f"    P >= {t:.2f}: would close {tot[t][1]:4d} positions early, $ change vs holding {tot[t][0]:>+10,.0f}")
    best = max(grid, key=lambda t: tot[t][0])
    print(f"    -> {best:.2f}  (a HYPOTHESIS; MT5 decides)")
    return best


def mql(node, ind="   "):
    if "leaf" in node: return f"{ind}return {float(np.float32(node['leaf'])):.9g};\n"
    i = EXH_NAMES.index(node["split"]); thr = float(np.float32(node["split_condition"]))
    yes = next(c for c in node["children"] if c["nodeid"] == node["yes"]); no = next(c for c in node["children"] if c["nodeid"] == node["no"])
    return f"{ind}if ((float)x[{i}] < (float){thr:.9g}) {{  // {node['split']}\n" + mql(yes, ind + "   ") + f"{ind}}} else {{\n" + mql(no, ind + "   ") + f"{ind}}}\n"


def leaf(node, x):
    while "leaf" not in node:
        go = node["yes"] if np.float32(x[EXH_NAMES.index(node["split"])]) < np.float32(node["split_condition"]) else node["no"]
        node = next(c for c in node["children"] if c["nodeid"] == go)
    return float(np.float32(node["leaf"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="5"); ap.add_argument("--cutoff", default="2026-07-01")
    ap.add_argument("--depth", type=int, default=3); ap.add_argument("--trees", type=int, default=150)
    a = ap.parse_args()
    df = load(a.tag)
    tr, te = df[df.time < a.cutoff], df[df.time >= a.cutoff]
    print(f"[+] train {len(tr)} rows / {tr.pos_id.nunique()} positions; unseen {len(te)} rows / {te.pos_id.nunique()} positions")
    print(f"    share of rows where closing now beat holding: train {tr.y.mean():.1%}, unseen {te.y.mean():.1%}")
    thr = pick(tr, a)
    m = model(a.depth, a.trees).fit(tr[EXH_NAMES], tr.y)
    trained = f"{tr.time.min():%Y-%m-%d}..{tr.time.max():%Y-%m-%d} ({tr.pos_id.nunique()} positions)"
    joblib.dump({"model": m, "features": EXH_NAMES, "trigger_threshold": thr, "trained": trained}, ROOT / "models" / "exhaustion_model.pkl")
    b = m.get_booster(); b.feature_names = EXH_NAMES
    trees = [json.loads(t) for t in b.get_dump(dump_format="json")]; bm = base_margin(b)
    names = ",".join(f'"{n}"' for n in EXH_NAMES)
    out = ["// SaadExhaustModel.mqh - GENERATED by meta_labeling_system/src/train_exhaustion.py — do not edit.",
           f"// XGBoost {xgb.__version__}: {len(trees)} trees, depth {a.depth}, trained on {trained}; suggested threshold {thr:.2f}",
           f"#define EXH_NF {len(EXH_NAMES)}", f'#define EXH_TRAINED "{trained}"', f"string EXH_NAMES[EXH_NF] = {{{names}}};"]
    out += [f"double ExhTree{k}(const double &x[])\n{{\n{mql(t)}}}" for k, t in enumerate(trees)]
    body = "\n".join(f"   m += ExhTree{k}(x);" for k in range(len(trees)))
    out.append(f"double ExhModelProb(const double &x[])\n{{\n   double m = {bm:.12g};\n{body}\n   return 1.0 / (1.0 + MathExp(-m));\n}}")
    mqh = REPO / "mt5" / "SaadExhaustModel.mqh"; mqh.write_text("\n".join(out) + "\n", encoding="utf-8"); shutil.copy(mqh, ROOT / "mql5" / mqh.name)
    X = df[EXH_NAMES].to_numpy(); px = m.predict_proba(df[EXH_NAMES])[:, 1]
    pdump = 1 / (1 + np.exp(-(bm + np.array([sum(leaf(t, x) for t in trees) for x in X]))))
    gap = float(np.abs(px - pdump).max())
    print(f"\n[+] parity xgboost vs exported trees: max |diff| {gap:.2e}  {'OK' if gap < 1e-5 else 'MISMATCH'}")
    g, n = replay(te.reset_index(drop=True), m.predict_proba(te[EXH_NAMES])[:, 1], thr)
    print(f"[+] replay on the unseen period at P >= {thr:.2f}: {n} positions closed early, $ change vs holding {g:+,.0f}  (NOT PROMOTED - MT5 decides)")
    imp = sorted(zip(EXH_NAMES, m.feature_importances_), key=lambda z: -z[1])
    print("[+] importance:", ", ".join(f"{k[2:]} {v:.2f}" for k, v in imp[:7]))
    print(f"[+] saved models/exhaustion_model.pkl and {mqh}")
